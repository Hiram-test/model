from __future__ import annotations  # 启用延迟类型注解，保证返回类型引用稳定。
import math  # 提供对数、平方根和标量幂运算。
from dataclasses import dataclass  # 定义低成本候选评价对象。
import numpy as np  # 执行动作变换、误差外推和数组运算。
from comparison.contracts import BenchmarkContext  # 导入统一比较上下文。
from tbeam_fem_core import Action  # 导入五维网格动作。
from tbeam_fem_core import Mesh  # 导入确定性网格对象。
from tbeam_fem_core import action_array  # 将动作转换为固定顺序数组。
from tbeam_fem_core import action_bounds  # 读取安全动作边界。
from tbeam_fem_core import action_object  # 将五维数组转换为动作对象。
from tbeam_fem_core import compile_mesh  # 将动作编译为真实三维T梁网格。
from tbeam_fem_core import mesh_signature  # 计算动作对应的整数网格签名。
from tbeam_fem_core import tetra_quality  # 计算真实四面体质量。
@dataclass(frozen=True)  # 将一次低成本候选评价定义为不可变记录。
class CandidateScore:  # 保存代理目标、编译网格和约束分量。
    objective: float  # 保存含约束罚项的总目标值。
    predicted_zz: float  # 保存由粗解区域误差外推的相对ZZ指标。
    dof: int  # 保存真实编译网格自由度。
    minimum_quality: float  # 保存最小四面体质量。
    mean_quality: float  # 保存平均四面体质量。
    aspect_proxy: float  # 保存纵横尺寸比例代理。
    signature: tuple[int, int, int, int, int, int, int]  # 保存整数网格签名。
    action: Action  # 保存请求动作。
    realized_action: Action  # 保存整数分段实际动作。
class MeshCompilerCache:  # 缓存重复动作对应的整数网格和质量。
    def __init__(self, context: BenchmarkContext) -> None:  # 初始化方法级网格缓存。
        self.context = context  # 保存统一比较上下文。
        self.data: dict[tuple[int, int, int, int, int, int, int], tuple[Mesh, float, float]] = {}  # 创建签名到网格统计映射。
        self.compilations = 0  # 初始化真实网格编译计数。
    def get(self, action: Action) -> tuple[Mesh, float, float]:  # 获取或编译给定动作。
        signature = mesh_signature(self.context.geometry, action)  # 计算动作的整数分段签名。
        if signature not in self.data:  # 检查签名是否首次出现。
            mesh = compile_mesh(self.context.geometry, action)  # 编译真实相容四面体网格。
            quality = tetra_quality(mesh.nodes, mesh.tets)  # 计算真实四面体质量。
            self.data[signature] = (mesh, float(np.min(quality)), float(np.mean(quality)))  # 缓存网格与质量统计。
            self.compilations += 1  # 累加真实编译次数。
        return self.data[signature]  # 返回缓存结果。
def normalized_region_error(context: BenchmarkContext) -> np.ndarray:  # 计算六区域归一化粗解误差贡献。
    contributions = np.array([float(np.sum(context.coarse_zz.element_error_squared[context.coarse_mesh.regions == region])) for region in range(6)], dtype=float)  # 汇总六区域误差平方贡献。
    return contributions / max(float(np.sum(contributions)), 1.0e-30)  # 归一化为和为一的区域份额。
def clip_action(context: BenchmarkContext, action: Action) -> Action:  # 将动作投影到现有几何编译器的安全域。
    lower, upper = action_bounds(context.coarse_action, context.geometry)  # 读取五维安全边界。
    return action_object(np.clip(action_array(action), lower, upper))  # 返回经过逐维裁剪的动作。
def latent_action(context: BenchmarkContext, center: Action, contrast_direction: np.ndarray, scale: float, contrast: float) -> Action:  # 将二维微型PSO坐标解码为五维动作。
    lower, upper = action_bounds(context.coarse_action, context.geometry)  # 读取五维动作安全边界。
    center_values = np.clip(action_array(center), lower, upper)  # 保证VLM中心位于安全域。
    direction = np.asarray(contrast_direction, dtype=float)  # 将对比方向转换为浮点数组。
    if direction.shape != (5,):  # 检查低秩动作方向维数。
        raise ValueError("contrast_direction must contain five values")  # 对错误VLM留痕立即失败。
    direction_norm = float(np.linalg.norm(direction))  # 计算方向欧氏范数。
    if direction_norm <= 1.0e-12:  # 检查方向是否退化。
        raise ValueError("contrast_direction must be non-zero")  # 禁止无法形成资源转移的方向。
    normalized_direction = direction / direction_norm  # 将方向归一化以稳定对比坐标尺度。
    log_values = np.log(center_values) + float(scale) + float(contrast) * normalized_direction  # 在对数尺寸空间施加整体尺度和区域对比。
    return action_object(np.clip(np.exp(log_values), lower, upper))  # 解码并投影为合法五维动作。
def evaluate_surrogate(context: BenchmarkContext, action: Action, priorities: np.ndarray, cache: MeshCompilerCache) -> CandidateScore:  # 用粗解物理量和真实网格编译评价候选动作。
    priority_values = np.asarray(priorities, dtype=float)  # 将六区域优先级转换为浮点数组。
    if priority_values.shape != (6,):  # 检查VLM区域优先级维数。
        raise ValueError("priorities must contain six values")  # 对错误留痕格式立即失败。
    mesh, minimum_quality, mean_quality = cache.get(clip_action(context, action))  # 编译候选网格并读取质量统计。
    regional_error = np.array([float(np.sum(context.coarse_zz.element_error_squared[context.coarse_mesh.regions == region])) for region in range(6)], dtype=float)  # 汇总六区域粗解误差贡献。
    weighted_error = regional_error * np.maximum(priority_values, 1.0e-6)  # 将VLM语义优先级作用于粗解物理贡献。
    baseline = action_array(context.coarse_action)  # 读取粗网格五维实际尺度。
    realized = action_array(mesh.realized_action)  # 读取候选整数网格实际尺度。
    hx = np.repeat(realized[:3], 2)  # 将三个纵向尺度展开到六个物理区域。
    cross = np.tile(realized[3:], 3)  # 将腹板与翼缘尺度展开到六个物理区域。
    baseline_hx = np.repeat(baseline[:3], 2)  # 将粗网格纵向尺度展开到六个物理区域。
    baseline_cross = np.tile(baseline[3:], 3)  # 将粗网格截面尺度展开到六个物理区域。
    effective_ratio = np.power((hx * cross ** 2) / np.maximum(baseline_hx * baseline_cross ** 2, 1.0e-30), 1.0 / 3.0)  # 计算三维等效尺度比。
    predicted_zz = context.coarse_zz.relative_error * math.sqrt(float(np.sum(weighted_error * effective_ratio ** 2)) / max(float(np.sum(weighted_error)), 1.0e-30))  # 外推候选相对ZZ指标。
    dof = 3 * len(mesh.nodes)  # 计算真实编译网格总自由度。
    budget_ratio = dof / float(context.target_dof)  # 计算候选预算占用比例。
    penalty = 0.90 * abs(budget_ratio - 1.0)  # 对预算偏离施加对称轻罚。
    penalty += 18.0 * max(0.0, budget_ratio - 1.03) ** 2  # 对超过百分之三预算施加强罚。
    penalty += 3.0 * max(0.0, 0.94 - budget_ratio) ** 2  # 对明显闲置预算施加罚项。
    penalty += 15.0 * max(0.0, 0.30 - minimum_quality) ** 2  # 对最差四面体质量不足施加罚项。
    penalty += 4.0 * max(0.0, 0.50 - mean_quality) ** 2  # 对平均四面体质量不足施加罚项。
    aspect_proxy = max(max(longitudinal / transverse, transverse / longitudinal) for longitudinal in realized[:3] for transverse in realized[3:])  # 计算最大纵横尺寸比例代理。
    penalty += 0.15 * max(0.0, aspect_proxy - 3.0) ** 2  # 对过强各向异性代理施加罚项。
    penalty += 0.04 * ((math.log(realized[0] / realized[1])) ** 2 + (math.log(realized[2] / realized[1])) ** 2)  # 对纵向区域尺寸突变施加平滑罚项。
    penalty += 0.20 * (math.log(realized[3] / realized[4])) ** 2  # 对腹板与翼缘分辨率失衡施加界面罚项。
    return CandidateScore(float(predicted_zz + penalty), float(predicted_zz), int(dof), float(minimum_quality), float(mean_quality), float(aspect_proxy), mesh.signature, action, mesh.realized_action)  # 返回完整候选评价。
def project_action_to_budget(context: BenchmarkContext, action: Action, cache: MeshCompilerCache, tolerance: float = 0.03) -> Action:  # 用单一整体缩放将任意动作投影到目标预算附近。
    lower, upper = action_bounds(context.coarse_action, context.geometry)  # 读取五维安全动作边界。
    base = np.clip(action_array(action), lower, upper)  # 裁剪初始动作到安全域。
    lo = -1.5  # 设置对数整体细化的搜索下界。
    hi = 1.5  # 设置对数整体粗化的搜索上界。
    best_action = action_object(base)  # 初始化最佳预算动作。
    best_gap = float("inf")  # 初始化最佳预算差距。
    for _ in range(50):  # 执行固定次数单调二分以适应整数网格台阶。
        mid = 0.5 * (lo + hi)  # 计算当前对数缩放中点。
        candidate = action_object(np.clip(base * math.exp(mid), lower, upper))  # 生成整体缩放候选动作。
        mesh, _, _ = cache.get(candidate)  # 编译候选真实整数网格。
        dof = 3 * len(mesh.nodes)  # 计算候选真实自由度。
        gap = abs(dof / float(context.target_dof) - 1.0)  # 计算预算相对差距。
        if gap < best_gap:  # 检查当前候选是否更接近预算。
            best_gap = gap  # 更新最佳预算差距。
            best_action = candidate  # 更新最佳预算动作。
        if dof > context.target_dof:  # 检查候选是否过细。
            lo = mid  # 增大尺寸以降低自由度。
        else:  # 处理候选未超过预算的情况。
            hi = mid  # 减小尺寸以增加自由度。
    best_mesh, _, _ = cache.get(best_action)  # 读取最佳动作的真实网格。
    if 3 * len(best_mesh.nodes) > int(math.floor((1.0 + tolerance) * context.target_dof)):  # 检查最佳动作是否仍超过容差上限。
        raise RuntimeError("unable to project action into the requested DOF tolerance")  # 对不可行预算显式失败。
    return best_action  # 返回预算投影后的五维动作。
def enforce_budget_upper(context: BenchmarkContext, action: Action, cache: MeshCompilerCache, tolerance: float = 0.03) -> Action:  # 仅在候选超过预算上限时执行最小整体回缩。
    candidate = clip_action(context, action)  # 先将候选动作投影到当前安全域。
    candidate_mesh, _, _ = cache.get(candidate)  # 编译候选真实整数网格。
    budget_limit = int(math.floor((1.0 + tolerance) * context.target_dof))  # 计算允许的自由度预算上限。
    if 3 * len(candidate_mesh.nodes) <= budget_limit:  # 检查局部细化候选是否尚未超过预算。
        return candidate  # 对预算内候选保持原有局部细化幅度而不强行吃满预算。
    lower, upper = action_bounds(context.coarse_action, context.geometry)  # 读取当前轮允许的动作边界。
    base = np.clip(action_array(candidate), lower, upper)  # 取得待整体回缩的五维动作。
    lo = 0.0  # 将零设为原始过细候选的对数缩放。
    hi = 1.5  # 设置足以回缩到当前网格附近的对数上界。
    feasible_action: Action | None = None  # 初始化预算内最细可行动作。
    for _ in range(50):  # 执行固定次数二分以处理整数网格台阶。
        mid = 0.5 * (lo + hi)  # 计算当前整体回缩尺度。
        trial = action_object(np.clip(base * math.exp(mid), lower, upper))  # 生成保留相对资源分配的整体回缩候选。
        trial_mesh, _, _ = cache.get(trial)  # 编译候选真实整数网格。
        if 3 * len(trial_mesh.nodes) <= budget_limit:  # 检查候选是否进入预算上限。
            feasible_action = trial  # 保存当前预算内候选。
            hi = mid  # 向更细方向继续寻找最小必要回缩。
        else:  # 处理候选仍然超过预算的情况。
            lo = mid  # 增大尺寸以继续降低自由度。
    if feasible_action is None:  # 检查当前动作边界内是否存在预算可行点。
        raise RuntimeError("unable to enforce the requested DOF upper bound")  # 对不可行预算显式失败。
    return feasible_action  # 返回不强制吃满预算的最细可行局部动作。
