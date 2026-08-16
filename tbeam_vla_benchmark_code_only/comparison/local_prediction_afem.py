from __future__ import annotations  # 启用延迟类型注解，保证协议与数据类引用稳定。
import json  # 写出局部预测请求和读取外部预测响应。
import shlex  # 将外部局部问题命令安全拆分为参数列表。
import subprocess  # 调用独立patch富集或低维局部问题求解器。
from dataclasses import dataclass  # 定义局部预测记录与AFEM配置。
from dataclasses import replace  # 用新网格和新解更新不可变比较上下文。
from pathlib import Path  # 管理局部请求、响应和轮次目录。
from typing import Protocol  # 定义可替换局部误差下降预测器接口。
import numpy as np  # 执行候选排序、Dörfler标记和数组序列化。
from comparison.common import MeshCompilerCache  # 复用真实网格编译缓存。
from comparison.common import clip_action  # 将局部组合动作投影到安全域。
from comparison.common import enforce_budget_upper  # 仅在局部组合动作超过预算时执行最小回缩。
from comparison.contracts import BenchmarkContext  # 导入统一比较上下文。
from comparison.contracts import MethodProposal  # 导入统一方法输出对象。
from tbeam_fem_core import Action  # 导入五维网格动作。
from tbeam_fem_core import Metrics  # 导入统一方案指标对象。
from tbeam_fem_core import action_array  # 将动作转换为固定顺序数组。
from tbeam_fem_core import action_object  # 将数组转换为五维动作。
from tbeam_fem_core import solve_case  # 执行真实三维T梁全局求解和ZZ恢复。
@dataclass(frozen=True)  # 将局部预测型AFEM配置定义为不可变对象。
class LocalPredictionConfig:  # 描述h-only局部候选、标记和停止规则。
    theta: float = 0.50  # 设置Dörfler预测收益覆盖比例。
    refinement_factor: float = 0.62  # 设置单次局部h细化尺度因子。
    max_rounds: int = 8  # 设置最多全局自适应轮数。
    target_budget_fraction: float = 0.97  # 设置达到目标预算的停止比例。
    minimum_predicted_reduction: float = 1.0e-10  # 设置无有效局部收益时的停止阈值。
    cost_aware_marking: bool = True  # 启用预测收益除以真实新增DOF的强基线排序。
    budget_tolerance: float = 0.03  # 设置终局自由度预算容差。
@dataclass(frozen=True)  # 将一个局部候选的预测结果定义为不可变对象。
class LocalPrediction:  # 保存局部低维问题对全局误差下降的预测。
    region: str  # 保存候选物理区域名称。
    predicted_global_error_reduction: float  # 保存预测的全局能量误差平方下降量。
    confidence: float  # 保存外部局部求解器给出的置信度或一致性指标。
    local_problem_dofs: int  # 保存局部富集或替换问题自由度。
    local_problem_seconds: float  # 保存局部问题墙钟时间。
    notes: list[str]  # 保存公开可审计的局部预测说明。
class LocalReductionPredictor(Protocol):  # 定义局部低维预测器协议。
    def predict(self, request_path: Path, response_path: Path) -> LocalPrediction:  # 要求预测器读取当前解和候选动作并返回全局误差下降预测。
        ...  # 仅定义协议，不提供虚假数值实现。
class SubprocessLocalReductionPredictor:  # 通过独立进程调用patch富集或局部替换求解器。
    def __init__(self, command_template: str) -> None:  # 初始化含请求和响应占位符的命令模板。
        self.command_template = command_template  # 保存外部局部预测命令。
    def predict(self, request_path: Path, response_path: Path) -> LocalPrediction:  # 执行一次局部低维问题预测。
        command = self.command_template.format(request=str(request_path), response=str(response_path))  # 将交换文件路径填入命令模板。
        subprocess.run(shlex.split(command), check=True)  # 调用外部局部问题求解器并传播失败状态。
        if not response_path.is_file():  # 检查外部求解器是否写出响应JSON。
            raise FileNotFoundError(f"local prediction response not found: {response_path}")  # 对不完整外部实现立即失败。
        payload = json.loads(response_path.read_text(encoding="utf-8"))  # 读取局部预测响应。
        return LocalPrediction(str(payload["region"]), float(payload["predicted_global_error_reduction"]), float(payload.get("confidence", 1.0)), int(payload.get("local_problem_dofs", 0)), float(payload.get("local_problem_seconds", 0.0)), [str(item) for item in payload.get("notes", [])])  # 返回类型化局部预测。
REGION_NAMES = ["root_web", "root_flange", "mid_web", "mid_flange", "tip_web", "tip_flange"]  # 固定六个局部预测区域顺序。
def local_candidate(action: Action, region_index: int, factor: float) -> Action:  # 为一个物理区域生成h-only局部细化候选。
    values = action_array(action)  # 读取当前五维网格尺寸。
    zone_index = region_index // 2  # 将六区域编号映射到根部、中段或端部纵向维度。
    component_index = 3 + (region_index % 2)  # 将偶数区域映射到腹板尺寸并将奇数区域映射到翼缘尺寸。
    values[zone_index] *= factor  # 对候选区域的纵向尺寸执行局部细化。
    values[component_index] *= factor  # 对候选区域的截面尺寸执行局部细化。
    return action_object(values)  # 返回尚未执行安全投影的候选动作。
def merge_candidates(current: Action, selected: list[Action]) -> Action:  # 将多个标记区域的局部细化组合成单一相容五维动作。
    merged = action_array(current)  # 从当前动作开始组合。
    for candidate in selected:  # 遍历所有被Dörfler标记的局部候选。
        merged = np.minimum(merged, action_array(candidate))  # 对每个受影响维度采用最细目标尺寸。
    return action_object(merged)  # 返回组合后的五维动作。
def write_local_request(context: BenchmarkContext, region_index: int, candidate: Action, request_path: Path) -> dict[str, object]:  # 写出局部富集或替换问题所需当前状态。
    stiffness = context.coarse_solution.stiffness.tocsr()  # 将当前全局刚度矩阵转换为CSR格式。
    np.savez_compressed(request_path, nodes=context.coarse_mesh.nodes, tets=context.coarse_mesh.tets, regions=context.coarse_mesh.regions, displacement=context.coarse_solution.displacement, stress=context.coarse_solution.stress, strain=context.coarse_solution.strain, volume=context.coarse_solution.volume, element_energy=context.coarse_solution.energy, element_zz_error_squared=context.coarse_zz.element_error_squared, recovered_nodal_stress=context.coarse_zz.recovered_nodal_stress, stiffness_data=stiffness.data, stiffness_indices=stiffness.indices, stiffness_indptr=stiffness.indptr, stiffness_shape=np.asarray(stiffness.shape, dtype=int), force=context.coarse_solution.force, fixed_dofs=context.coarse_solution.fixed_dofs, current_action=action_array(context.coarse_action), candidate_action=action_array(candidate), target_region=np.array([region_index], dtype=int), target_dof=np.array([context.target_dof], dtype=int))  # 保存外部局部问题所需完整当前解与候选定义。
    metadata = {"method": "locally predicted h-AFEM baseline", "region": REGION_NAMES[region_index], "region_index": int(region_index), "candidate_action": {"hx_root": candidate.hx_root, "hx_mid": candidate.hx_mid, "hx_tip": candidate.hx_tip, "h_web": candidate.h_web, "h_flange": candidate.h_flange}, "expected_response": {"format": "JSON", "required": ["region", "predicted_global_error_reduction"], "optional": ["confidence", "local_problem_dofs", "local_problem_seconds", "notes"]}, "implementation_note": "The external solver should construct a low-dimensional local enrichment or replacement space and predict its globally effective energy-error reduction without a full candidate remesh solve."}  # 构造局部预测请求说明。
    request_path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")  # 写出人类可读局部请求元数据。
    return metadata  # 返回请求元数据供审计记录使用。
def metric_to_dict(metric: Metrics) -> dict[str, float | int | str]:  # 将终局指标转换为JSON可序列化字典。
    return {"name": metric.name, "nodes": int(metric.nodes), "elements": int(metric.elements), "dof": int(metric.dof), "zz": float(metric.zz), "tip_z": float(metric.tip_z), "compliance": float(metric.compliance), "root_p95_vm": float(metric.root_p95_vm), "max_vm": float(metric.max_vm), "min_quality": float(metric.min_quality), "mean_quality": float(metric.mean_quality), "solve_seconds": float(metric.solve_seconds)}  # 返回统一指标字典。
class LocalPredictionAFEM:  # 实现Bammer式局部预测思想在当前C3D4环境中的h-only比较框架。
    name = "local_prediction_h_afem"  # 定义统一方法名称。
    def __init__(self, predictor: LocalReductionPredictor | None, config: LocalPredictionConfig | None = None) -> None:  # 初始化外部局部问题预测器和AFEM配置。
        self.predictor = predictor  # 保存局部低维问题求解器或空值。
        self.config = config or LocalPredictionConfig()  # 使用显式配置或默认强基线设置。
    def propose(self, context: BenchmarkContext) -> MethodProposal:  # 执行多轮局部预测、标记、重网格和完整重解框架。
        method_dir = context.work_dir / self.name  # 定义局部预测AFEM隔离目录。
        method_dir.mkdir(parents=True, exist_ok=True)  # 创建方法工作目录。
        if self.predictor is None:  # 检查局部富集或替换求解器是否已接入。
            audit = {"status_reason": "No local patch prediction command was supplied.", "required_interface": "For each of six regional h-refinement candidates, read the current global solution and return the predicted globally effective energy-error reduction.", "scientific_scope": "The code implements candidate generation, exact compiled-DOF accounting, cost-aware Dörfler marking, global resolve loops and audit logging; it does not replace the missing low-dimensional local variational solve with a ZZ heuristic."}  # 构造诚实的未接入说明。
            return MethodProposal(self.name, None, "external_component_required", audit, 0, 0, 0, 0, False, False)  # 返回等待局部预测器的比较项。
        current_context = context  # 从统一粗解上下文开始自适应循环。
        current_action = context.coarse_action  # 保存当前全局网格动作。
        rounds: list[dict[str, object]] = []  # 创建全部AFEM轮次审计记录。
        total_local_predictions = 0  # 初始化局部预测总次数。
        total_mesh_compilations = 0  # 初始化候选网格编译总次数。
        internal_full_solves = 0  # 初始化方法内部完整全局求解次数。
        final_metric: Metrics | None = None  # 初始化最后一次全局求解指标。
        for round_index in range(self.config.max_rounds):  # 执行最多指定轮数的局部预测AFEM。
            round_dir = method_dir / f"round_{round_index:02d}"  # 定义当前轮交换目录。
            round_dir.mkdir(parents=True, exist_ok=True)  # 创建当前轮目录。
            cache = MeshCompilerCache(current_context)  # 创建当前轮真实网格编译缓存。
            candidate_rows: list[dict[str, object]] = []  # 创建当前轮六个候选记录。
            for region_index, region_name in enumerate(REGION_NAMES):  # 遍历六个物理区域候选。
                candidate = clip_action(current_context, local_candidate(current_action, region_index, self.config.refinement_factor))  # 构造并投影当前区域h细化候选。
                candidate_mesh, _, _ = cache.get(candidate)  # 编译候选真实网格以获得实际新增DOF。
                current_dof = 3 * len(current_context.coarse_mesh.nodes)  # 计算当前网格自由度。
                candidate_dof = 3 * len(candidate_mesh.nodes)  # 计算候选网格自由度。
                added_dof = candidate_dof - current_dof  # 计算候选相对当前网格的真实新增自由度。
                if added_dof <= 0:  # 检查整数网格台阶是否使当前局部动作没有产生新自由度。
                    candidate_rows.append({"region": region_name, "region_index": int(region_index), "action": candidate, "candidate_dof": int(candidate_dof), "added_dof": int(added_dof), "predicted_reduction": 0.0, "ranking_score": 0.0, "confidence": 0.0, "local_problem_dofs": 0, "local_problem_seconds": 0.0, "notes": ["integer mesh compiler produced no additional DOF; local problem was skipped"], "request_metadata": None})  # 将无实际网格变化的候选记录为零收益。
                    continue  # 跳过无效局部预测请求。
                request_path = round_dir / f"candidate_{region_index:02d}_{region_name}.npz"  # 定义当前局部预测请求文件。
                response_path = round_dir / f"candidate_{region_index:02d}_{region_name}.json"  # 定义当前局部预测响应文件。
                metadata = write_local_request(current_context, region_index, candidate, request_path)  # 写出当前解与候选动作请求。
                prediction = self.predictor.predict(request_path, response_path)  # 调用局部低维问题求解器。
                if prediction.region != region_name:  # 检查外部响应区域是否与请求一致。
                    raise ValueError(f"local prediction region mismatch: expected {region_name}, got {prediction.region}")  # 对错配响应立即失败。
                reduction = max(float(prediction.predicted_global_error_reduction), 0.0)  # 将非物理负下降裁剪为零。
                ranking_score = reduction / float(added_dof) if self.config.cost_aware_marking else reduction  # 计算成本感知或原始预测收益排序分数。
                candidate_rows.append({"region": region_name, "region_index": int(region_index), "action": candidate, "candidate_dof": int(candidate_dof), "added_dof": int(added_dof), "predicted_reduction": float(reduction), "ranking_score": float(ranking_score), "confidence": float(prediction.confidence), "local_problem_dofs": int(prediction.local_problem_dofs), "local_problem_seconds": float(prediction.local_problem_seconds), "notes": prediction.notes, "request_metadata": metadata})  # 记录当前局部候选完整信息。
                total_local_predictions += 1  # 累加局部预测次数。
            total_mesh_compilations += cache.compilations  # 累加当前轮候选网格编译次数。
            total_reduction = float(sum(float(row["predicted_reduction"]) for row in candidate_rows))  # 计算六候选预测下降总量。
            if total_reduction <= self.config.minimum_predicted_reduction:  # 检查是否已无可用局部下降。
                rounds.append({"round": int(round_index), "stop_reason": "no_positive_predicted_reduction", "candidates": [{key: value for key, value in row.items() if key != "action"} | {"action": {"hx_root": row["action"].hx_root, "hx_mid": row["action"].hx_mid, "hx_tip": row["action"].hx_tip, "h_web": row["action"].h_web, "h_flange": row["action"].h_flange}} for row in candidate_rows]})  # 保存停止轮次记录。
                break  # 结束自适应循环。
            ordered = sorted(candidate_rows, key=lambda row: float(row["ranking_score"]), reverse=True)  # 按预测收益或单位DOF收益降序排列候选。
            selected_rows: list[dict[str, object]] = []  # 创建Dörfler标记候选集合。
            accumulated = 0.0  # 初始化已覆盖预测下降量。
            for row in ordered:  # 遍历排序后的局部候选。
                selected_rows.append(row)  # 将当前候选加入标记集合。
                accumulated += float(row["predicted_reduction"])  # 累加原始预测下降量。
                if accumulated >= self.config.theta * total_reduction:  # 检查是否达到Dörfler覆盖比例。
                    break  # 达到覆盖比例后停止继续标记。
            combined = merge_candidates(current_action, [row["action"] for row in selected_rows])  # 合并所有标记区域的局部h细化动作。
            projected = enforce_budget_upper(current_context, clip_action(current_context, combined), cache, self.config.budget_tolerance)  # 仅在组合动作超预算时执行最小整体回缩。
            bundle = solve_case(f"local_prediction_round_{round_index:02d}", projected, current_context.geometry, current_context.material, current_context.load)  # 执行当前轮唯一完整全局重解和ZZ恢复。
            internal_full_solves += 1  # 累加方法内部完整全局求解次数。
            final_metric = bundle[3]  # 保存当前轮终局指标。
            rounds.append({"round": int(round_index), "current_dof_before": int(3 * len(current_context.coarse_mesh.nodes)), "selected_regions": [str(row["region"]) for row in selected_rows], "theta": float(self.config.theta), "predicted_reduction_covered": float(accumulated), "predicted_reduction_total": float(total_reduction), "projected_action": {"hx_root": projected.hx_root, "hx_mid": projected.hx_mid, "hx_tip": projected.hx_tip, "h_web": projected.h_web, "h_flange": projected.h_flange}, "terminal_metrics": metric_to_dict(bundle[3]), "candidates": [{key: value for key, value in row.items() if key != "action"} | {"action": {"hx_root": row["action"].hx_root, "hx_mid": row["action"].hx_mid, "hx_tip": row["action"].hx_tip, "h_web": row["action"].h_web, "h_flange": row["action"].h_flange}} for row in candidate_rows]})  # 保存当前轮完整审计记录。
            current_action = projected  # 将当前网格动作更新为已执行动作。
            current_context = replace(current_context, coarse_action=projected, coarse_mesh=bundle[0], coarse_solution=bundle[1], coarse_zz=bundle[2])  # 将新网格、新解和新ZZ状态作为下一轮当前状态。
            if bundle[3].dof >= int(self.config.target_budget_fraction * context.target_dof):  # 检查是否已使用目标比例的自由度预算。
                rounds[-1]["stop_reason"] = "target_budget_fraction_reached"  # 在当前轮记录预算停止原因。
                break  # 结束自适应循环。
        if final_metric is None:  # 检查是否尚未执行任何全局重解。
            audit = {"rounds": rounds, "status_reason": "The local predictor returned no positive candidate before any refinement solve."}  # 构造无动作结果说明。
            return MethodProposal(self.name, current_action, "ready_without_refinement", audit, 0, total_mesh_compilations, total_local_predictions, 0, False, True)  # 返回当前粗动作并要求统一终局处理。
        audit = {"protocol": "local low-dimensional error-reduction prediction -> exact candidate DOF accounting -> cost-aware Dörfler marking -> global remesh and resolve", "specialization": "h-only C3D4 specialization because the present T-beam core has no p-enrichment space", "rounds": rounds, "final_metrics_already_solved": metric_to_dict(final_metric), "terminal_action": {"hx_root": current_action.hx_root, "hx_mid": current_action.hx_mid, "hx_tip": current_action.hx_tip, "h_web": current_action.h_web, "h_flange": current_action.h_flange}}  # 构造局部预测AFEM完整审计记录。
        return MethodProposal(self.name, current_action, "ready", audit, 0, total_mesh_compilations, total_local_predictions, internal_full_solves, False, False)  # 返回已完成多轮全局重解的最终动作与成本记账。
