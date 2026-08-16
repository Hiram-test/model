from pathlib import Path  # 管理项目根目录和比较文件路径。
import sys  # 将项目根目录加入测试导入路径。
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 确保测试直接导入本地源码。
from comparison.benchmark_driver import method_plan  # 导入无有限元执行的比较计划构造器。
from comparison.local_prediction_afem import local_candidate  # 导入局部区域h细化候选生成器。
from comparison.vlm_micro_pso import load_trace  # 导入VLM留痕读取与哈希验证函数。
from tbeam_fem_core import Action  # 导入五维网格动作对象。
def test_vlm_trace_is_bound_to_supplied_image() -> None:  # 验证VLM留痕与实际粗解图像通过SHA256绑定。
    project_root = Path(__file__).resolve().parents[2]  # 定位项目根目录。
    trace = load_trace(project_root / "comparison" / "vlm_trace.json", project_root)  # 读取并验证VLM留痕。
    assert trace.image_sha256 == "a81540997c2a51ac49442c25796238e2cb2566af4f350079a8075d29a2c00852"  # 确认留痕对应指定粗解图像。
    assert trace.priorities.shape == (6,)  # 确认六区域优先级完整。
    assert trace.contrast_direction.shape == (5,)  # 确认五维低秩动作方向完整。
def test_code_only_plan_exposes_three_fair_methods() -> None:  # 验证默认计划包含VLM、AMBER和局部预测AFEM三类方法。
    project_root = Path(__file__).resolve().parents[2]  # 定位项目根目录。
    plan = method_plan(project_root)  # 构造不运行有限元的比较计划。
    assert plan["execution_default"] == "code_only"  # 确认默认不执行正式数值比较。
    assert set(plan["methods"]) == {"vlm_trace_micro_pso", "amber_iterative_sizing_field", "local_prediction_h_afem"}  # 确认三种方法接口齐全。
    assert plan["methods"]["vlm_trace_micro_pso"]["maximum_surrogate_evaluations"] == 9  # 确认PSO已压缩为最多九次低成本评价。
def test_local_candidates_modify_only_region_dimensions() -> None:  # 验证六区域候选只改变对应纵向和截面尺寸。
    action = Action(0.4, 0.5, 0.6, 0.2, 0.25)  # 创建可辨识的五维测试动作。
    root_web = local_candidate(action, 0, 0.5)  # 生成根部腹板局部细化候选。
    tip_flange = local_candidate(action, 5, 0.5)  # 生成端部翼缘局部细化候选。
    assert root_web == Action(0.2, 0.5, 0.6, 0.1, 0.25)  # 确认根部腹板只修改hx_root和h_web。
    assert tip_flange == Action(0.4, 0.5, 0.3, 0.2, 0.125)  # 确认端部翼缘只修改hx_tip和h_flange。
def test_new_python_source_has_line_comments() -> None:  # 验证新增Python代码每条非空非纯注释代码行都带有注释符号。
    comparison_root = Path(__file__).resolve().parents[1]  # 定位comparison源码目录。
    paths = list(comparison_root.glob("*.py")) + [comparison_root.parents[0] / "tbeam_compare_code_only.py", comparison_root.parents[0] / "tbeam_fem_core.py"] + list((comparison_root.parents[0] / "external_templates").glob("*.py"))  # 收集比较源码、独立有限元核心和外部接口模板。
    for path in paths:  # 遍历全部新增Python源文件。
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # 逐行读取源码。
            stripped = line.strip()  # 去除行首尾空白。
            if not stripped or stripped.startswith("#"):  # 跳过空行和纯注释行。
                continue  # 继续检查下一行。
            assert "#" in line, f"missing line comment: {path}:{number}"  # 要求每条代码行包含可见注释。
