from __future__ import annotations  # 启用延迟类型注解，保证方法列表类型稳定。
import argparse  # 解析代码计划与可选真实执行参数。
import json  # 写出统一比较计划和运行结果。
from pathlib import Path  # 管理项目根目录、方法工作目录和结果路径。
from typing import Any  # 标注异质比较结果字典。
from comparison.amber_adapter import AmberAdapter  # 导入AMBER式迭代尺寸场基线。
from comparison.amber_adapter import AmberConfig  # 导入AMBER迭代配置。
from comparison.amber_adapter import SubprocessAmberPredictor  # 导入外部AMBER检查点适配器。
from comparison.contracts import BenchmarkContext  # 导入统一粗解比较上下文。
from comparison.contracts import MethodProposal  # 导入统一方法输出对象。
from comparison.contracts import action_to_dict  # 导入动作JSON转换函数。
from comparison.local_prediction_afem import LocalPredictionAFEM  # 导入局部预测型h-AFEM基线。
from comparison.local_prediction_afem import LocalPredictionConfig  # 导入局部预测AFEM配置。
from comparison.local_prediction_afem import SubprocessLocalReductionPredictor  # 导入外部局部问题适配器。
from comparison.vlm_micro_pso import MicroPSOConfig  # 导入五粒子一次更新PSO配置。
from comparison.vlm_micro_pso import VLMMicroPSO  # 导入VLM留痕驱动的极小PSO执行器。
from tbeam_fem_core import Geometry  # 导入默认三维T梁几何。
from tbeam_fem_core import Load  # 导入默认自由端载荷。
from tbeam_fem_core import Material  # 导入默认线弹性材料。
from tbeam_fem_core import coarse_action  # 导入统一粗网格动作。
from tbeam_fem_core import metrics  # 导入统一终局指标汇总函数。
from tbeam_fem_core import plot_surface  # 导入粗解视觉状态绘图函数。
from tbeam_fem_core import solve_case  # 导入真实三维T梁编译、求解和ZZ恢复链。
def method_plan(project_root: Path) -> dict[str, Any]:  # 构造不执行有限元的代码交付计划。
    return {"execution_default": "code_only", "shared_protocol": {"geometry": "same parametric 3D solid T-beam", "coarse_state": "same coarse mesh, coarse FEM solution, recovered stress and ZZ field", "target_budget": "same target DOF and three-percent upper tolerance", "mesh_compiler": "same deterministic five-action C3D4 compiler", "terminal_evaluation": "same full FEM solve and recovered ZZ metrics", "reported_costs": ["offline labels and training", "surrogate evaluations", "mesh compilations", "local patch predictions", "internal full FEM solves", "terminal full FEM solve"]}, "methods": {"vlm_trace_micro_pso": {"status": "implemented", "visual_source": str(project_root / "comparison" / "vlm_trace.json"), "executor": "five initial particles in two latent coordinates plus one update of four particles", "maximum_surrogate_evaluations": 9, "full_fem_inside_executor": 0}, "amber_iterative_sizing_field": {"status": "adapter_only", "external_requirement": "task-specific or multi-task AMBER checkpoint command", "protocol": "current mesh graph -> node sizing field -> deterministic mesher -> repeat", "no_fake_checkpoint": True}, "local_prediction_h_afem": {"status": "adapter_and_runner_only", "external_requirement": "low-dimensional local enrichment or replacement predictor command", "protocol": "six local candidates -> predicted globally effective error reduction -> exact added DOF -> cost-aware Dörfler marking -> global resolve", "no_zz_substitution_for_local_prediction": True}}, "commands": {"code_only": "python -m comparison.benchmark_driver --output-dir comparison_plan", "execute_vlm_only": "python -m comparison.benchmark_driver --execute --methods vlm --output-dir comparison_run", "execute_all": "python -m comparison.benchmark_driver --execute --methods vlm amber local --amber-command 'python amber_infer.py --request {request} --response {response}' --local-command 'python local_patch_predict.py --request {request} --response {response}' --output-dir comparison_run"}}  # 返回完整公平比较计划。
def proposal_to_dict(proposal: MethodProposal) -> dict[str, Any]:  # 将统一方法输出转换为JSON字典。
    return {"method": proposal.method, "status": proposal.status, "action": action_to_dict(proposal.action), "surrogate_evaluations": int(proposal.surrogate_evaluations), "mesh_compilations": int(proposal.mesh_compilations), "local_predictions": int(proposal.local_predictions), "internal_full_fem_solves": int(proposal.internal_full_fem_solves), "offline_training_required": bool(proposal.offline_training_required), "terminal_solve_required": bool(proposal.terminal_solve_required), "audit": proposal.audit}  # 返回完整方法记录。
def execute_comparison(arguments: argparse.Namespace, project_root: Path, output_dir: Path) -> dict[str, Any]:  # 在显式请求时执行统一粗解和可用方法。
    geometry = Geometry()  # 创建默认三维T梁几何。
    material = Material()  # 创建默认钢材线弹性材料。
    load = Load()  # 创建默认自由端向下载荷。
    coarse_bundle = solve_case("shared_coarse", coarse_action(), geometry, material, load)  # 执行所有方法共享且只计算一次的粗解。
    state_image = output_dir / "shared_coarse_state.png"  # 定义共享粗解视觉状态图路径。
    plot_surface(state_image, coarse_bundle[0], geometry, "Shared coarse visual state for benchmark", coarse_bundle[1])  # 生成供外部检查和VLM留痕更新的粗解图。
    context = BenchmarkContext(geometry, material, load, arguments.goal, arguments.budget_dof, coarse_action(), coarse_bundle[0], coarse_bundle[1], coarse_bundle[2], state_image, output_dir / "method_work")  # 构造统一粗解比较上下文。
    selected = set(arguments.methods)  # 将方法参数转换为集合。
    methods: list[Any] = []  # 创建待执行方法列表。
    if "vlm" in selected:  # 检查是否执行VLM留痕极小PSO。
        methods.append(VLMMicroPSO(project_root / "comparison" / "vlm_trace.json", project_root, MicroPSOConfig(seed=arguments.seed)))  # 加入五粒子一次更新执行器。
    if "amber" in selected:  # 检查是否执行AMBER基线。
        amber_predictor = SubprocessAmberPredictor(arguments.amber_command) if arguments.amber_command else None  # 根据命令是否存在创建外部AMBER适配器。
        methods.append(AmberAdapter(amber_predictor, AmberConfig(iterations=arguments.amber_iterations)))  # 加入AMBER式迭代尺寸场基线。
    if "local" in selected:  # 检查是否执行局部预测型AFEM基线。
        local_predictor = SubprocessLocalReductionPredictor(arguments.local_command) if arguments.local_command else None  # 根据命令是否存在创建外部局部问题适配器。
        methods.append(LocalPredictionAFEM(local_predictor, LocalPredictionConfig(theta=arguments.theta, max_rounds=arguments.local_rounds)))  # 加入局部预测h-AFEM基线。
    method_results: list[dict[str, Any]] = []  # 创建全部方法结果列表。
    for method in methods:  # 逐一执行所选比较方法。
        proposal = method.propose(context)  # 从完全相同的粗解输入获取方法动作或外部组件状态。
        record = proposal_to_dict(proposal)  # 将方法输出转换为结构化记录。
        if proposal.action is not None and proposal.terminal_solve_required:  # 检查方法是否返回尚未求解的终局动作。
            terminal_bundle = solve_case(f"terminal_{proposal.method}", proposal.action, geometry, material, load)  # 用相同有限元环境执行统一终局求解。
            terminal_metric = metrics(proposal.method, terminal_bundle[0], terminal_bundle[1], terminal_bundle[2], geometry)  # 汇总统一终局指标。
            record["terminal_metrics"] = {"nodes": terminal_metric.nodes, "elements": terminal_metric.elements, "dof": terminal_metric.dof, "zz": terminal_metric.zz, "tip_z": terminal_metric.tip_z, "compliance": terminal_metric.compliance, "root_p95_vm": terminal_metric.root_p95_vm, "max_vm": terminal_metric.max_vm, "min_quality": terminal_metric.min_quality, "mean_quality": terminal_metric.mean_quality, "solve_seconds": terminal_metric.solve_seconds}  # 写入统一终局指标。
            record["terminal_full_fem_solves"] = 1  # 记录统一终局完整求解一次。
        else:  # 处理外部组件未接入或AFEM已内部求解的情况。
            record["terminal_full_fem_solves"] = 0  # 不重复计算终局求解成本。
        method_results.append(record)  # 将当前方法结果加入比较列表。
    return {"shared_coarse_full_fem_solves": 1, "shared_coarse_metrics": {"nodes": coarse_bundle[3].nodes, "elements": coarse_bundle[3].elements, "dof": coarse_bundle[3].dof, "zz": coarse_bundle[3].zz, "tip_z": coarse_bundle[3].tip_z, "solve_seconds": coarse_bundle[3].solve_seconds}, "goal": arguments.goal, "target_dof": arguments.budget_dof, "methods": method_results, "warning": "No numerical comparison is scientifically complete until the external AMBER checkpoint and local variational predictor are connected under this common protocol."}  # 返回统一比较结果。
def parser() -> argparse.ArgumentParser:  # 创建代码计划与可选执行命令行解析器。
    argument_parser = argparse.ArgumentParser(description="三维T梁VLM微型PSO、AMBER和局部预测型AFEM统一比较代码")  # 定义程序说明。
    argument_parser.add_argument("--output-dir", type=Path, default=Path("comparison_plan"), help="比较计划或运行结果目录")  # 添加输出目录参数。
    argument_parser.add_argument("--execute", action="store_true", help="显式执行共享粗解和已接入的方法；默认只写代码计划")  # 添加真实执行开关。
    argument_parser.add_argument("--methods", nargs="+", choices=["vlm", "amber", "local"], default=["vlm", "amber", "local"], help="选择比较方法")  # 添加方法选择参数。
    argument_parser.add_argument("--budget-dof", type=int, default=3500, help="统一终局自由度预算")  # 添加统一预算参数。
    argument_parser.add_argument("--goal", type=str, default="在约3500自由度预算下，优先降低固定端腹板—翼缘交界的应力误差，同时保持自由端竖向位移精度。", help="统一自然语言任务目标")  # 添加语言目标参数。
    argument_parser.add_argument("--seed", type=int, default=7, help="VLM微型PSO随机种子")  # 添加极小PSO种子参数。
    argument_parser.add_argument("--amber-command", type=str, default=None, help="外部AMBER命令模板，必须包含{request}和{response}")  # 添加AMBER外部模型命令。
    argument_parser.add_argument("--amber-iterations", type=int, default=3, help="AMBER尺寸场迭代次数")  # 添加AMBER迭代参数。
    argument_parser.add_argument("--local-command", type=str, default=None, help="外部局部预测命令模板，必须包含{request}和{response}")  # 添加局部问题外部命令。
    argument_parser.add_argument("--local-rounds", type=int, default=8, help="局部预测AFEM最大全局重解轮数")  # 添加局部AFEM轮数参数。
    argument_parser.add_argument("--theta", type=float, default=0.50, help="局部预测收益Dörfler覆盖比例")  # 添加Dörfler标记参数。
    return argument_parser  # 返回配置完成的命令行解析器。
def main() -> None:  # 提供统一比较代码入口。
    arguments = parser().parse_args()  # 解析命令行参数。
    project_root = Path(__file__).resolve().parents[1]  # 定位包含三维T梁核心程序的项目根目录。
    output_dir = arguments.output_dir.resolve()  # 将输出目录解析为绝对路径。
    output_dir.mkdir(parents=True, exist_ok=True)  # 创建输出目录。
    result = execute_comparison(arguments, project_root, output_dir) if arguments.execute else method_plan(project_root)  # 根据显式开关执行比较或只写计划。
    output_path = output_dir / ("benchmark_results.json" if arguments.execute else "benchmark_plan.json")  # 根据模式选择结果文件名。
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")  # 写出结构化比较计划或结果。
    print(json.dumps({"mode": "execute" if arguments.execute else "code_only", "output": str(output_path)}, ensure_ascii=False, indent=2))  # 打印最小运行收据。
if __name__ == "__main__":  # 检查模块是否作为命令行入口执行。
    main()  # 启动统一比较驱动程序。
