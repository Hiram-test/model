from __future__ import annotations  # 启用延迟类型注解，保证协议与数据类引用稳定。
import json  # 写出外部AMBER模型请求元数据。
import shlex  # 将可配置外部命令安全拆分为参数列表。
import subprocess  # 调用独立AMBER环境或官方检查点推理脚本。
from dataclasses import dataclass  # 定义AMBER迭代配置。
from pathlib import Path  # 管理请求、响应和方法工作目录。
from typing import Protocol  # 定义可替换的节点尺寸场预测器接口。
import numpy as np  # 构造图特征、边集合和尺寸场统计。
from scipy.spatial import cKDTree  # 将统一粗解物理特征投影到AMBER中间网格节点。
from comparison.common import MeshCompilerCache  # 复用确定性网格编译缓存。
from comparison.common import clip_action  # 将节点尺寸场压缩动作投影到安全域。
from comparison.common import project_action_to_budget  # 将AMBER终局动作统一投影到自由度预算。
from comparison.contracts import BenchmarkContext  # 导入统一比较上下文。
from comparison.contracts import MethodProposal  # 导入统一方法输出对象。
from tbeam_fem_core import Action  # 导入五维网格动作对象。
from tbeam_fem_core import Mesh  # 导入三维T梁网格对象。
from tbeam_fem_core import action_array  # 将动作转换为固定顺序数组。
from tbeam_fem_core import von_mises  # 将恢复节点应力转换为等效应力特征。
@dataclass(frozen=True)  # 将AMBER式迭代推理配置定义为不可变对象。
class AmberConfig:  # 描述中间网格次数与尺寸裁剪规则。
    iterations: int = 3  # 设置AMBER式尺寸场迭代次数。
    minimum_size_ratio: float = 0.22  # 设置相对粗网格尺寸的最小允许比例。
    maximum_size_ratio: float = 1.35  # 设置相对粗网格尺寸的最大允许比例。
    budget_tolerance: float = 0.03  # 设置终局自由度预算容差。
class AmberNodeSizingPredictor(Protocol):  # 定义外部AMBER节点尺寸预测器协议。
    def predict(self, request_path: Path, response_path: Path) -> np.ndarray:  # 要求预测器读取NPZ请求并返回逐节点标量尺寸。
        ...  # 仅定义协议，不提供默认模型实现。
class SubprocessAmberPredictor:  # 通过独立进程调用官方或用户训练的AMBER检查点。
    def __init__(self, command_template: str) -> None:  # 初始化含请求和响应占位符的命令模板。
        self.command_template = command_template  # 保存外部推理命令模板。
    def predict(self, request_path: Path, response_path: Path) -> np.ndarray:  # 执行一次外部AMBER尺寸场推理。
        command = self.command_template.format(request=str(request_path), response=str(response_path))  # 将请求和响应路径填入命令模板。
        subprocess.run(shlex.split(command), check=True)  # 在独立环境中执行AMBER推理并传播失败状态。
        if not response_path.is_file():  # 检查外部模型是否写出约定响应文件。
            raise FileNotFoundError(f"AMBER response not found: {response_path}")  # 对不完整外部集成立即失败。
        response = np.load(response_path, allow_pickle=False)  # 读取外部模型返回的逐节点尺寸数组。
        if isinstance(response, np.lib.npyio.NpzFile):  # 检查响应是否为NPZ容器。
            if "node_sizes" not in response.files:  # 检查约定字段是否存在。
                raise KeyError("AMBER NPZ response must contain 'node_sizes'")  # 对错误响应模式立即失败。
            values = np.asarray(response["node_sizes"], dtype=float)  # 读取NPZ中的节点尺寸字段。
            response.close()  # 关闭NPZ文件句柄。
            return values  # 返回逐节点标量尺寸。
        return np.asarray(response, dtype=float)  # 返回NPY中的逐节点标量尺寸。
def mesh_edges(mesh: Mesh) -> np.ndarray:  # 从四面体连接构造唯一无向图边。
    local_pairs = np.array([[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]], dtype=int)  # 定义四面体六条局部边。
    expanded = np.vstack([mesh.tets[:, pair] for pair in local_pairs])  # 展开全部单元边。
    ordered = np.sort(expanded, axis=1)  # 将每条边节点编号排序以忽略方向。
    return np.unique(ordered, axis=0)  # 返回唯一无向边集合。
def node_resolution(mesh: Mesh, edges: np.ndarray) -> np.ndarray:  # 计算当前中间网格每个节点的平均邻边长度。
    lengths = np.linalg.norm(mesh.nodes[edges[:, 1]] - mesh.nodes[edges[:, 0]], axis=1)  # 计算全部唯一边长度。
    sums = np.zeros(len(mesh.nodes), dtype=float)  # 初始化节点邻边长度和。
    counts = np.zeros(len(mesh.nodes), dtype=float)  # 初始化节点邻边计数。
    np.add.at(sums, edges[:, 0], lengths)  # 将边长累加到第一端节点。
    np.add.at(sums, edges[:, 1], lengths)  # 将边长累加到第二端节点。
    np.add.at(counts, edges[:, 0], 1.0)  # 将边计数累加到第一端节点。
    np.add.at(counts, edges[:, 1], 1.0)  # 将边计数累加到第二端节点。
    return sums / np.maximum(counts, 1.0)  # 返回逐节点平均邻边长度。
def build_amber_request(context: BenchmarkContext, mesh: Mesh, iteration: int, request_path: Path) -> dict[str, object]:  # 构造与官方AMBER概念一致的图和尺寸场推理请求。
    edges = mesh_edges(mesh)  # 构造当前中间网格图边。
    current_size = node_resolution(mesh, edges)  # 计算当前节点局部分辨率。
    coarse_tree = cKDTree(context.coarse_mesh.nodes)  # 建立统一粗网格节点最近邻树。
    _, nearest = coarse_tree.query(mesh.nodes, k=1)  # 将粗解节点物理特征投影到当前中间网格。
    coarse_nodal_vm = von_mises(context.coarse_zz.recovered_nodal_stress)  # 计算粗解恢复节点等效应力。
    projected_vm = coarse_nodal_vm[np.asarray(nearest, dtype=int)]  # 投影粗解等效应力到当前节点。
    degree = np.zeros(len(mesh.nodes), dtype=float)  # 初始化当前图节点度。
    np.add.at(degree, edges[:, 0], 1.0)  # 累加第一端节点度。
    np.add.at(degree, edges[:, 1], 1.0)  # 累加第二端节点度。
    coordinates = mesh.nodes.copy()  # 复制当前节点坐标。
    coordinate_scale = np.array([context.geometry.length, context.geometry.flange_width, context.geometry.total_height], dtype=float)  # 定义三轴归一化尺度。
    normalized_coordinates = coordinates / coordinate_scale  # 将坐标缩放到近似零到一范围。
    root_flag = (coordinates[:, 0] <= context.geometry.root_fraction * context.geometry.length + 1.0e-12).astype(float)  # 标记固定端纵向区域。
    tip_flag = (coordinates[:, 0] >= (1.0 - context.geometry.tip_fraction) * context.geometry.length - 1.0e-12).astype(float)  # 标记自由端纵向区域。
    web_top = context.geometry.total_height - context.geometry.flange_thickness  # 计算腹板与翼缘分界高度。
    flange_flag = (coordinates[:, 2] >= web_top - 1.0e-12).astype(float)  # 标记翼缘节点。
    web_flag = 1.0 - flange_flag  # 标记腹板节点。
    characteristic = max(float(np.median(current_size)), 1.0e-12)  # 计算当前网格特征尺寸。
    vm_scale = max(float(np.quantile(projected_vm, 0.95)), 1.0)  # 计算鲁棒应力归一化尺度。
    features = np.column_stack([normalized_coordinates, current_size / characteristic, degree / max(float(np.max(degree)), 1.0), root_flag, tip_flag, web_flag, flange_flag, projected_vm / vm_scale])  # 组装节点几何、网格与粗解物理特征。
    np.savez_compressed(request_path, nodes=mesh.nodes, edges=edges, node_features=features, current_node_sizes=current_size, iteration=np.array([iteration], dtype=int))  # 写出不依赖深度学习框架的AMBER请求NPZ。
    metadata = {"method": "AMBER-style iterative sizing-field baseline", "iteration": int(iteration), "language_goal": context.goal, "target_dof": int(context.target_dof), "node_feature_columns": ["x_normalized", "y_normalized", "z_normalized", "current_size_normalized", "degree_normalized", "root_flag", "tip_flag", "web_flag", "flange_flag", "coarse_recovered_vm_normalized"], "expected_response": {"format": "NPY or NPZ", "shape": [len(mesh.nodes)], "field": "node_sizes", "units": "meter"}}  # 构造外部模型请求说明。
    request_path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")  # 写出人类可读请求元数据。
    return metadata  # 返回请求元数据供审计记录使用。
def robust_median(values: np.ndarray, fallback: float) -> float:  # 对区域节点尺寸计算带空集回退的鲁棒中位数。
    finite = np.asarray(values, dtype=float)  # 将输入转换为浮点数组。
    finite = finite[np.isfinite(finite) & (finite > 0.0)]  # 仅保留正有限尺寸。
    return float(np.median(finite)) if len(finite) else float(fallback)  # 返回中位数或指定回退值。
def sizing_field_to_action(context: BenchmarkContext, mesh: Mesh, node_sizes: np.ndarray, config: AmberConfig) -> Action:  # 将AMBER逐节点标量尺寸压缩为统一五维T梁动作。
    sizes = np.asarray(node_sizes, dtype=float).reshape(-1)  # 将外部尺寸场压平成一维数组。
    if len(sizes) != len(mesh.nodes):  # 检查节点尺寸数量与当前网格一致。
        raise ValueError("AMBER node sizing length does not match the current mesh")  # 对错误模型输出立即失败。
    coarse_values = action_array(context.coarse_action)  # 读取统一粗网格五维尺寸。
    lower_scalar = float(np.min(coarse_values) * config.minimum_size_ratio)  # 按配置计算节点尺寸绝对下界。
    upper_scalar = float(np.max(coarse_values) * config.maximum_size_ratio)  # 按配置计算节点尺寸绝对上界。
    sizes = np.clip(sizes, lower_scalar, upper_scalar)  # 裁剪异常外部尺寸预测。
    x = mesh.nodes[:, 0]  # 读取节点纵向坐标。
    z = mesh.nodes[:, 2]  # 读取节点高度坐标。
    root_end = context.geometry.root_fraction * context.geometry.length  # 计算固定端区域终点。
    tip_start = (1.0 - context.geometry.tip_fraction) * context.geometry.length  # 计算自由端区域起点。
    web_top = context.geometry.total_height - context.geometry.flange_thickness  # 计算腹板与翼缘分界高度。
    root_mask = x <= root_end + 1.0e-12  # 构造固定端节点掩码。
    mid_mask = (x > root_end) & (x < tip_start)  # 构造中段节点掩码。
    tip_mask = x >= tip_start - 1.0e-12  # 构造自由端节点掩码。
    web_mask = z < web_top - 1.0e-12  # 构造腹板节点掩码。
    flange_mask = ~web_mask  # 构造翼缘节点掩码。
    action = Action(robust_median(sizes[root_mask], coarse_values[0]), robust_median(sizes[mid_mask], coarse_values[1]), robust_median(sizes[tip_mask], coarse_values[2]), robust_median(sizes[web_mask], coarse_values[3]), robust_median(sizes[flange_mask], coarse_values[4]))  # 将五类区域中位数组织为统一动作。
    return clip_action(context, action)  # 返回经过安全域投影的五维动作。
class AmberAdapter:  # 将官方AMBER式迭代尺寸场预测接入统一三维T梁编译器。
    name = "amber_iterative_sizing_field"  # 定义统一方法名称。
    def __init__(self, predictor: AmberNodeSizingPredictor | None, config: AmberConfig | None = None) -> None:  # 初始化外部预测器和迭代配置。
        self.predictor = predictor  # 保存外部AMBER模型或空值。
        self.config = config or AmberConfig()  # 使用显式配置或默认三次迭代。
    def propose(self, context: BenchmarkContext) -> MethodProposal:  # 从统一粗网格提出AMBER终局动作。
        method_dir = context.work_dir / self.name  # 定义AMBER隔离交换目录。
        method_dir.mkdir(parents=True, exist_ok=True)  # 创建AMBER工作目录。
        if self.predictor is None:  # 检查官方或用户训练的AMBER模型是否已接入。
            audit = {"status_reason": "No AMBER checkpoint command was supplied.", "required_interface": "The external model reads amber_request_XX.npz and writes a one-dimensional node_sizes array in meters.", "scientific_scope": "This adapter follows AMBER's iterative graph-to-sizing-field-to-mesher protocol but does not fabricate a trained checkpoint."}  # 构造诚实的未接入说明。
            return MethodProposal(self.name, None, "external_component_required", audit, 0, 0, 0, 0, True, True)  # 返回等待外部模型的比较项。
        cache = MeshCompilerCache(context)  # 创建AMBER中间网格编译缓存。
        current_mesh = context.coarse_mesh  # 从统一粗网格开始AMBER迭代。
        current_action = context.coarse_action  # 从统一粗动作开始AMBER迭代。
        iterations: list[dict[str, object]] = []  # 创建AMBER迭代审计记录。
        for iteration in range(self.config.iterations):  # 执行配置的尺寸场预测与重网格循环。
            request_path = method_dir / f"amber_request_{iteration:02d}.npz"  # 定义当前AMBER请求文件。
            response_path = method_dir / f"amber_response_{iteration:02d}.npz"  # 定义当前AMBER响应文件。
            metadata = build_amber_request(context, current_mesh, iteration, request_path)  # 构造当前图与节点特征请求。
            node_sizes = self.predictor.predict(request_path, response_path)  # 调用外部AMBER模型预测逐节点尺寸。
            current_action = sizing_field_to_action(context, current_mesh, node_sizes, self.config)  # 将尺寸场压缩到统一五维动作。
            current_mesh, _, _ = cache.get(current_action)  # 用相同确定性编译器生成并缓存下一中间网格。
            iterations.append({"iteration": int(iteration), "request": str(request_path), "response": str(response_path), "request_metadata": metadata, "predicted_node_size_min": float(np.min(node_sizes)), "predicted_node_size_median": float(np.median(node_sizes)), "predicted_node_size_max": float(np.max(node_sizes)), "compressed_action": {"hx_root": current_action.hx_root, "hx_mid": current_action.hx_mid, "hx_tip": current_action.hx_tip, "h_web": current_action.h_web, "h_flange": current_action.h_flange}, "compiled_dof": int(3 * len(current_mesh.nodes))})  # 记录当前AMBER迭代。
        final_action = project_action_to_budget(context, current_action, cache, self.config.budget_tolerance)  # 将最终尺寸场动作统一投影到同一自由度预算。
        audit = {"protocol": "iterative graph prediction -> scalar node sizing field -> deterministic mesher", "iterations": iterations, "terminal_action": {"hx_root": final_action.hx_root, "hx_mid": final_action.hx_mid, "hx_tip": final_action.hx_tip, "h_web": final_action.h_web, "h_flange": final_action.h_flange}, "training_note": "A task-specific or multi-task AMBER checkpoint and its expert-mesh labels are external offline costs."}  # 构造完整AMBER审计记录。
        return MethodProposal(self.name, final_action, "ready", audit, self.config.iterations, cache.compilations, 0, 0, True, True)  # 返回统一终局求解动作。
