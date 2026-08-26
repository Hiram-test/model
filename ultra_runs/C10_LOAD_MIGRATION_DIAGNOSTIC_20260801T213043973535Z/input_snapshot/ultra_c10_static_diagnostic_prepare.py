from __future__ import annotations  # 启用延迟类型注解，避免运行时解析 Path 等注解造成额外依赖。

import argparse  # 解析是否生成三迭代非线性残差定位包，禁止通过手改输入切换诊断范围。
import hashlib  # 提供 SHA-256 摘要，用于冻结父输入、微验证结果和新诊断工件身份。
import json  # 读写保持机器可解析的运行清单、状态和变更审计文件。
import math  # 验证 S10 平衡轴力和换算初始应力均为有限正值，拒绝 NaN、无穷和非拉力数据。
import re  # 严格解析 S10 两列轴力 CSV 的整数单元号与科学计数值。
import shutil  # 将已冻结的 C10 求解依赖逐字节复制到新的独立诊断目录。
from datetime import datetime, timezone  # 生成 UTC 时间戳，保证运行目录和 MAPDL 作业身份唯一。
from pathlib import Path  # 用跨平台路径对象安全处理包含中文的工程目录。
from typing import Any  # 标注 JSON 字典可容纳的异构值类型。


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 取 ultra_tools 的父目录作为本分析包根目录。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 冻结所有不可覆盖运行包所在目录。
PARENT_RUN_NAME = "C10_MPC_ONLY_20260801T190630474559Z"  # 指定已删除 3,124 条串联链并通过静态生成门的单层 TYPE72 父运行。
MICRO_RUN_NAME = "C10_MICRO_VALIDATION_20260801T190634755506Z"  # 指定 12/12 通过且方程数恒定的权威单层拓扑微验证运行。
S10_FORCE_RUN_NAME = "S10_SECTION_SHEAR_20260716T050342389124Z"  # 指定已完成 LS2 平衡且 73,692 根 LINK180 全正拉力的旧连接参考运行。
S10_FORCE_AUDIT_NAME = "S10_LINK180_POSTONLY_20260716T092014206694Z"  # 指定从 S10 LS2 只读导出的轴力审计子运行。
S10_FORCE_CSV_NAME = "s10_link180_axial_force_n.csv"  # 指定含单元号和 LS2 轴力 N 的两列纯数值权威文件名。
S10_FORCE_CSV_SHA256 = "80bf13d4648d23ca064ef3a8d1fe8f79be8092d8274e3ecfe9954da52485c47b"  # 冻结已通过 73,692 条全正拉力审计的 CSV 字节身份。
S10_SEED_INCLUDE_NAME = "apply_s10_ls2_force_seed_override_link180.inp"  # 指定只删除旧 TYPE4 初态并按 S10 LS2 轴力重建初始应力的覆盖 include。
PARENT_MAIN_NAME = "c10_mpc_only_main.inp"  # 指定父运行中含静力与模态控制流的主输入文件名。
DIAGNOSTIC_MAIN_NAME = "c10_static_diagnostic_main.inp"  # 指定新运行只执行静力门禁的主输入文件名。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 冻结本机 MAPDL 2026 R1 可执行文件路径。
MIN_MICRO_CASES = 12  # 要求单层直接消元连接完整执行三项 UXYZ、三项有限转动和六项 ALL 微验证。
FORCE_TOLERANCE = "5.0E-3"  # 固定力残差相对容限为 0.5%，与 MAPDL 默认工程尺度一致但禁止自动放宽。
MOMENT_TOLERANCE = "5.0E-3"  # 固定力矩残差相对容限为 0.5%，覆盖含转动自由度的平衡方程。
DISPLACEMENT_TOLERANCE = "5.0E-2"  # 固定位移修正相对容限为 5%，用于补充力与力矩收敛判断。
ROTATION_TOLERANCE = "5.0E-2"  # 固定转角修正相对容限为 5%，覆盖 TYPE72 master 的转动独立自由度。
RESIDUAL_MAX_ITERATIONS = 3  # 非线性残差定位只执行三次完整 Newton 迭代，足以生成两代 NRRE 文件且避免已证伪路径空转。
EXPECTED_LINK180_COUNT = 73692  # 冻结两幅猫道 73,688 根实体索加四根下拉索的全部 LINK180 数量。
BOTTOM_LAST_ELEMENT = 68960  # 单元 1 至 68,960 使用每根底索的 MCT 等效截面 30。
GANTRY_LAST_ELEMENT = 73688  # 单元 68,961 至 73,688 使用每根门架索的 MCT 等效截面 32。
BOTTOM_AREA_MM2 = 1393.668228093791  # 截面 30 面积，单位 mm²，来源为 MCT 等效底索面积除以 16。
GANTRY_AREA_MM2 = 1400.496622996084  # 截面 32 面积，单位 mm²，来源为 MCT 等效门架索面积除以 6。
DOWNPULL_AREA_MM2 = 22298.69164950066  # 截面 33 面积，单位 mm²，来源为 MCT 单根等效下拉索截面。


def require(condition: bool, message: str) -> None:  # 输入布尔条件和失败说明；条件不满足时阻断生成且不返回业务值。
    if not condition:  # 仅在证据或唯一性门禁失败时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确异常，防止生成可误启动的不完整运行包。


def sha256_bytes(data: bytes) -> str:  # 输入任意字节并返回六十四位小写 SHA-256 十六进制摘要。
    return hashlib.sha256(data).hexdigest()  # 一次性计算摘要并返回，供文件身份闭合使用。


def sha256_file(path: Path) -> str:  # 输入必须存在的文件路径并返回其完整内容 SHA-256 摘要。
    digest = hashlib.sha256()  # 建立独立摘要器，避免大文件一次性加载占用额外内存。
    with path.open("rb") as handle:  # 以只读二进制方式打开文件，确保换行和编码不被改写。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 以每块一 MiB 流式读取直至文件结束。
            digest.update(chunk)  # 将当前原始字节块加入连续摘要计算。
    return digest.hexdigest()  # 返回最终小写十六进制摘要。


def load_json(path: Path) -> dict[str, Any]:  # 输入 UTF-8 JSON 文件并返回顶层对象字典。
    require(path.is_file(), f"缺少 JSON 证据文件：{path}")  # 在读取前拒绝缺失路径。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 按 UTF-8 解析完整机器工件。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充运行清单。
    return payload  # 返回已验证的顶层字典供后续门禁使用。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # 输入目标路径和对象字典，输出稳定缩进的 UTF-8 JSON。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"  # 保留中文并添加唯一末尾换行方便审计。
    path.write_text(rendered, encoding="utf-8", newline="\n")  # 使用 LF 写入且不在无注释格式中插入非法注释。


def replace_once(text: str, old: str, new: str, label: str) -> str:  # 输入文本、唯一旧段、新段和标签并返回单次替换结果。
    count = text.count(old)  # 统计旧段出现次数，验证补丁锚点没有漂移或重复。
    require(count == 1, f"{label} 锚点出现 {count} 次，预期恰为 1 次")  # 只有唯一命中才允许修改控制流。
    return text.replace(old, new, 1)  # 在唯一锚点处执行一次确定性替换。


def parse_args() -> argparse.Namespace:  # 无业务输入；解析命令行并返回是否启用残差定位的命名空间。
    parser = argparse.ArgumentParser(description="生成唯一 C10 静力或非线性残差定位诊断包")  # 建立只控制诊断子类型且不接受路径猜测的解析器。
    mode_group = parser.add_mutually_exclusive_group()  # 建立互斥模式组，防止残差定位与 S10 平衡力种子在同一运行中混用。
    mode_group.add_argument("--residual-localization", action="store_true", help="把 LS1 限为三次迭代并输出 NRRE/EFLG 诊断文件")  # 布尔开关只改变诊断输出和迭代上限，不改变模型、荷载或四项收敛准则。
    mode_group.add_argument("--s10-force-seed", action="store_true", help="用已审计 S10 LS2 轴力覆盖原始 MCT INISTATE 后执行完整形成态诊断")  # 布尔开关只改变初始应力种子，并保留 corrected-MPC、完整恒载和全部收敛硬门。
    return parser.parse_args()  # 返回已验证的参数对象供主流程冻结到清单。


def load_s10_force_seed(path: Path) -> dict[int, float]:  # 输入已冻结的两列 S10 CSV 路径并返回单元号到轴力 N 的完整映射。
    require(path.is_file(), f"缺少 S10 LS2 轴力 CSV：{path}")  # 在读取前拒绝缺失或被移动的参考结果。
    require(sha256_file(path) == S10_FORCE_CSV_SHA256, "S10 LS2 轴力 CSV SHA-256 漂移")  # 防止使用未经审计的旧约束结果种子。
    pattern = re.compile(r"^\s*(\d+)\.,\s*([+\-0-9.Ee]+)\s*$")  # 只接受整数单元号加一个科学计数轴力值的冻结文本格式。
    forces: dict[int, float] = {}  # 初始化单元号唯一映射，重复记录必须被拒绝而不是覆盖。
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # 按实际行号逐条解析 73,692 条纯数值记录。
        match = pattern.fullmatch(line)  # 对当前整行执行严格格式匹配，拒绝额外字段或注释混入权威 CSV。
        require(match is not None, f"S10 轴力 CSV 第 {line_number} 行格式异常")  # 任一格式漂移即停止准备。
        element_id = int(match.group(1))  # 将第一列转换为 MAPDL LINK180 单元号。
        force_n = float(match.group(2))  # 将第二列转换为单位 N 的 LS2 轴力。
        require(element_id not in forces, f"S10 轴力 CSV 重复单元号：{element_id}")  # 保证每根索只有一个终态轴力来源。
        require(math.isfinite(force_n) and force_n > 0.0, f"S10 轴力不是有限正拉力：{element_id}")  # 禁止压缩、零值、NaN 或无穷进入 tension-only 初态。
        forces[element_id] = force_n  # 保存通过格式和物理符号门的轴力。
    expected_ids = set(range(1, GANTRY_LAST_ELEMENT + 1)) | {400000, 400001, 400002, 400003}  # 构造 73,688 根实体索和四根下拉索的精确单元集合。
    require(set(forces) == expected_ids, "S10 轴力单元集合不是完整 73,692 根 LINK180")  # 拒绝缺项、多项或编号族漂移。
    require(len(forces) == EXPECTED_LINK180_COUNT, "S10 轴力记录数不是 73,692")  # 以独立数量门再次关闭完整性。
    return forces  # 返回已通过身份、数量、集合和正拉力门的轴力映射。


def link_area_mm2(element_id: int) -> float:  # 输入冻结 LINK180 单元号并返回对应截面面积 mm²。
    if 1 <= element_id <= BOTTOM_LAST_ELEMENT:  # 底索实体单元使用截面 30。
        return BOTTOM_AREA_MM2  # 返回 MCT 等效面积除以 16 的每根底索面积。
    if BOTTOM_LAST_ELEMENT < element_id <= GANTRY_LAST_ELEMENT:  # 门架索实体单元使用截面 32。
        return GANTRY_AREA_MM2  # 返回 MCT 等效面积除以 6 的每根门架索面积。
    require(element_id in {400000, 400001, 400002, 400003}, f"未知 LINK180 截面族：{element_id}")  # 只允许四根冻结下拉索进入末分支。
    return DOWNPULL_AREA_MM2  # 返回 MCT 单根等效下拉索面积。


def render_s10_seed_include(forces: dict[int, float]) -> tuple[bytes, dict[str, Any]]:  # 输入完整 S10 轴力映射并返回逐行注释的 APDL 覆盖 include 与机器审计。
    lines: list[str] = []  # 初始化确定性 LF 文本行列表，避免平台换行改变摘要。
    lines.append("! S10 LS2 平衡轴力种子覆盖：只用于 corrected-MPC 静力诊断，不构成生产初始状态签认。")  # 声明来源、目标拓扑和使用边界。
    lines.append("! 源轴力来自已审计 S10 LS2/substep1/time=1.001；原始 MCT INISTATE 先由父 include 建模，再在此完整删除并替换。")  # 说明为何保留父截面转换而只覆盖应力数据。
    lines.append("! 每个 INISTATE 命令前均记录单元、轴力、面积和应力，单位依次为 N、mm2 和 N/mm2。")  # 固定生成行字段语义。
    lines.append("! 进入前处理器以编辑 TYPE4 LINK180 的初始状态表。")  # 为下一条处理器命令提供逐行中文说明。
    lines.append("/PREP7")  # 进入前处理器，允许删除和重建初始应力数据。
    lines.append("! 恢复全部节点与单元选择，避免父 include 的局部选择状态影响删除范围。")  # 为下一条选择命令说明作用域。
    lines.append("ALLSEL,ALL")  # 恢复完整模型选择。
    lines.append("! 只选择 TYPE4 LINK180，禁止删除 BEAM188、MASS21 或 MPC184 的任何状态。")  # 为下一条类型选择命令说明安全边界。
    lines.append("ESEL,S,TYPE,,4")  # 选择全部 73,692 根索单元。
    lines.append("! 删除当前选中 TYPE4 的原始 MCT 初始状态，确保新种子不是叠加应力。")  # 为下一条删除命令说明覆盖语义。
    lines.append("INISTATE,DELE")  # 删除全部选中 LINK180 的既有初态数据。
    lines.append("! 恢复全部实体选择，随后按显式单元号逐根定义新初始应力。")  # 为下一条选择恢复命令说明后续作用。
    lines.append("ALLSEL,ALL")  # 恢复完整模型选择。
    lines.append("! 指定后续 INISTATE,DEFINE 数据类型为轴向应力 STRE。")  # 为下一条数据类型命令说明物理量。
    lines.append("INISTATE,SET,DTYP,STRE")  # 将初始状态数据类型设为应力。
    stresses: list[float] = []  # 收集换算应力供范围和有限性审计。
    for element_id in sorted(forces):  # 按单元号稳定递增生成 73,692 组注释和定义命令。
        force_n = forces[element_id]  # 读取当前单元的 S10 LS2 正轴力，单位 N。
        area_mm2 = link_area_mm2(element_id)  # 按冻结单元族读取截面面积，单位 mm²。
        stress_n_mm2 = force_n / area_mm2  # 用 N/mm² 计算与目标轴力严格对应的常截面初始应力。
        require(math.isfinite(stress_n_mm2) and stress_n_mm2 > 0.0, f"换算初始应力无效：{element_id}")  # 独立拒绝非法面积或数值溢出。
        stresses.append(stress_n_mm2)  # 保存当前应力供整体范围审计。
        lines.append(f"! 单元 {element_id}：S10_LS2_FORCE_N={force_n:.15E}，AREA_MM2={area_mm2:.15E}，SEED_STRESS_N_MM2={stress_n_mm2:.15E}。")  # 在每条可执行定义前记录完整可复算来源。
        lines.append(f"INISTATE,DEFINE,{element_id},,,,{stress_n_mm2:.15E}")  # 为当前 LINK180 全部积分点定义正向轴向初始应力。
    lines.append("! 恢复全部实体选择，避免覆盖 include 向后泄漏局部选择状态。")  # 为下一条选择恢复命令说明目的。
    lines.append("ALLSEL,ALL")  # 恢复完整模型选择。
    lines.append("! 离开前处理器并把控制权返回主诊断输入。")  # 为下一条结束命令说明流程去向。
    lines.append("FINISH")  # 结束本覆盖 include 的前处理阶段。
    rendered = ("\n".join(lines) + "\n").encode("utf-8")  # 使用 UTF-8 与唯一末尾 LF 生成确定性字节内容。
    audit = {"schema_version": 1, "status": "PASSED", "source_run": S10_FORCE_RUN_NAME, "source_audit": S10_FORCE_AUDIT_NAME, "source_csv": S10_FORCE_CSV_NAME, "source_csv_sha256": S10_FORCE_CSV_SHA256, "element_count": len(forces), "minimum_force_n": min(forces.values()), "maximum_force_n": max(forces.values()), "minimum_seed_stress_n_mm2": min(stresses), "maximum_seed_stress_n_mm2": max(stresses), "all_forces_positive": True, "old_initial_state_deleted_before_redefinition": True, "include_sha256": sha256_bytes(rendered), "valid_for_production": False}  # 汇总种子来源、数量、范围、覆盖语义和禁止生产外推边界。
    return rendered, audit  # 返回可写入 solver 的 APDL 字节和伴随机器审计。


def validate_parent(parent_dir: Path, micro_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:  # 输入父运行和微验证目录，返回通过身份门的两份清单。
    parent_manifest = load_json(parent_dir / "manifest.json")  # 读取直接消元 C10 父运行清单。
    require(parent_manifest.get("run_name") == PARENT_RUN_NAME, "父运行名称与冻结常量不一致")  # 防止误取其他候选。
    require(parent_manifest.get("constraint_imposition") == "DIRECT_ELIMINATION", "父运行不是直接消元连接方案")  # 禁止罚函数方案进入诊断。
    require(parent_manifest.get("penalty_n_per_mm") is None, "父运行仍含罚刚度参数")  # 直接拒绝任何隐含罚刚度。
    require(parent_manifest.get("aux_node_count") == 0, "父运行仍含 UXYZ 辅助节点")  # 阻断旧 master—TYPE72—aux—TYPE73—slave 串联链。
    require(parent_manifest.get("type73_count") == 0, "父运行仍含 TYPE73 第二层约束")  # 全桥诊断只允许一条逻辑连接对应一个 TYPE72。
    expected_topology = parent_manifest.get("expected_topology")  # 读取父运行预注册的全桥候选拓扑计数。
    require(isinstance(expected_topology, dict), "父运行缺少 expected_topology 对象")  # 后续节点、单元和类型计数门要求字典。
    require(expected_topology.get("nodes") == 109086 and expected_topology.get("elements") == 178072, "父运行节点或单元总数不是单层拓扑预期")  # 固定删除 3,124 个辅助节点与 3,124 个 TYPE73 后的模型规模。
    require(expected_topology.get("TYPE72") == 5078 and expected_topology.get("TYPE73") == 0, "父运行 MPC184 类型计数不是 5078/0")  # 固定 1,954 条 ALL 与 3,124 条 UXYZ 均为单 TYPE72。
    dependencies = parent_manifest.get("dependencies")  # 读取父运行十二项输入身份记录。
    require(isinstance(dependencies, list) and len(dependencies) == 12, "父运行依赖清单不是冻结的十二项")  # 固定依赖覆盖范围。
    for record in dependencies:  # 逐项复算父 solver 目录中的真实字节身份。
        require(isinstance(record, dict), "父运行依赖项不是对象")  # 拒绝畸形依赖记录。
        name = str(record.get("name"))  # 取得当前依赖文件名用于定位。
        expected_hash = str(record.get("solver_sha256"))  # 取得父清单冻结的 solver 摘要。
        source_path = parent_dir / "solver" / name  # 构造当前父求解文件的绝对路径。
        require(source_path.is_file(), f"父 solver 缺少冻结依赖：{name}")  # 拒绝缺失或被移动的输入。
        require(sha256_file(source_path) == expected_hash, f"父 solver 依赖哈希漂移：{name}")  # 拒绝任何未登记修改。
    micro_results = load_json(micro_dir / "unit_test_results.json")  # 读取权威微验证汇总。
    require(micro_results.get("prepare_run") == PARENT_RUN_NAME, "微验证不属于指定父运行")  # 连接候选与验证结果必须同源。
    require(micro_results.get("status") == "MICRO_VALIDATION_PASSED_FULL_BRIDGE_NOT_RUN", "微验证状态未通过")  # 只接受已通过且尚未冒充全桥的状态。
    require(micro_results.get("schema_version") == 3, "微验证不是单层拓扑 schema 3")  # 阻断旧十五案例串联链验收结果。
    require(micro_results.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "微验证拓扑不是单 TYPE72")  # 要求数值验证对象与全桥候选一致。
    require(int(micro_results.get("planned_case_count", 0)) == MIN_MICRO_CASES, "微验证计划案例数不是十二")  # 固定测试覆盖。
    require(int(micro_results.get("passed_case_count", 0)) == MIN_MICRO_CASES, "微验证通过案例数不是十二")  # 要求全数通过。
    require(int(micro_results.get("failed_case_count", -1)) == 0, "微验证仍有失败案例")  # 不允许带失败进入全桥。
    return parent_manifest, micro_results  # 返回通过门禁的父清单和微验证结果。


def transform_main(source_bytes: bytes, old_jobname: str, new_jobname: str) -> tuple[bytes, dict[str, Any]]:  # 输入父主控字节和新旧作业名，返回静力专用主控与变更审计。
    source_text = source_bytes.decode("utf-8")  # 严格按父文件实际 UTF-8 编码解码，不容忍替代字符。
    newline = "\r\n" if "\r\n" in source_text else "\n"  # 保留父文件原有 CRLF 或 LF 换行风格。
    require(source_text.count(old_jobname) == 5, "父主控作业名前缀引用数不是冻结的五处")  # 验证主作业、结果读取和数据库保存身份。
    candidate = source_text.replace(old_jobname, new_jobname)  # 先改写全部五处作业身份，再执行控制流截断。
    candidate = replace_once(candidate, "/TITLE,C10 MPC184 CONNECTION PATCH FULL BRIDGE PRESTRESSED MODAL", "/TITLE,C10 DIRECT MPC STATIC FULL-FORMED-STATE EQUILIBRIUM-PAIR DIAGNOSTIC", "诊断标题")  # 明确本运行验证全量初始内力与全量恒载在首个平衡步直接配对，且仍只限静力诊断。
    convergence_anchor = "! 每个 LS1 子步最多允许 100 次平衡迭代。" + newline + "NEQIT,100" + newline  # 构造唯一收敛控制插入锚点。
    convergence_block = convergence_anchor + "! 显式固定力残差相对容限为 0.5%，防止 MAPDL 因收敛困难自动放宽默认标准。" + newline + f"CNVTOL,F,,{FORCE_TOLERANCE},2" + newline + "! 显式固定力矩残差相对容限为 0.5%，并用二范数覆盖含转动自由度的平衡方程。" + newline + f"CNVTOL,M,,{MOMENT_TOLERANCE},2" + newline + "! 显式启用位移修正相对容限 5%，以无穷范数约束局部异常增量。" + newline + f"CNVTOL,U,,{DISPLACEMENT_TOLERANCE},0" + newline + "! 显式启用转角修正相对容限 5%，以无穷范数约束 TYPE72 master 的局部异常增量。" + newline + f"CNVTOL,ROT,,{ROTATION_TOLERANCE},0" + newline  # 组装力、力矩、平移和转角四项不可自动放宽的收敛准则。
    candidate = replace_once(candidate, convergence_anchor, convergence_block, "显式 CNVTOL")  # 在首个 SOLVE 前插入并让 LS2 继承同一准则。
    ls1_kbc_source = "! LS1 从零到完整重力采用斜坡加载。" + newline + "KBC,0" + newline  # 冻结父主控中造成全量 INISTATE 与部分恒载非物理叠加的唯一 LS1 斜坡片段。
    ls1_kbc_target = "! LS1 将完整恒载一步施加，与从 t=0 已存在的完整 INISTATE 直接组成形成态平衡对。" + newline + "KBC,1" + newline  # 用阶跃加载消除 1% 至 4% 恒载与全量初始内力并存的虚构中间路径。
    candidate = replace_once(candidate, ls1_kbc_source, ls1_kbc_target, "LS1 形成态恒载配对")  # 只修改首个物理平衡步，保留 LS2 的零增量保持控制。
    ls1_autots_source = "! LS1 允许自动时间步在收敛困难时细分。" + newline + "AUTOTS,ON" + newline  # 冻结父主控中会再次生成部分恒载中间态的自动细分片段。
    ls1_autots_target = "! LS1 禁止自动细分，避免求解器把形成态平衡对重新拆成无物理含义的部分恒载路径。" + newline + "AUTOTS,OFF" + newline  # 强制形成态配对作为一个完整平衡点求解。
    candidate = replace_once(candidate, ls1_autots_source, ls1_autots_target, "LS1 形成态固定步长")  # 仅关闭 LS1 自动细分且不改变非线性迭代算法。
    ls1_nsubst_source = "! 采用父静力实际封板配置：初始 20、最多 200、最少 20 子步，单步不大于 0.05。" + newline + "NSUBST,20,200,20" + newline  # 冻结父主控中二十个斜坡子步的唯一配置片段。
    ls1_nsubst_target = "! 形成态平衡对只允许一个完整子步；三个参数均为 1，禁止扩大或缩小子步数量。" + newline + "NSUBST,1,1,1" + newline  # 将 LS1 固定为一个完整恒载平衡点而不是渐增加载历史。
    candidate = replace_once(candidate, ls1_nsubst_source, ls1_nsubst_target, "LS1 形成态单子步")  # 受控替换 LS1 子步配置并保留 LS2 原有单步保持状态。
    candidate = replace_once(candidate, "! 离开后处理器，静力门禁全部通过后才允许进入扰动。", "! 离开后处理器；静力门禁已全部通过，本诊断按限定范围不进入扰动分析。", "静力后处理结束说明")  # 删除会误导为继续模态的旧说明。
    candidate = replace_once(candidate, "! 把静力门禁通过但模态未完成的阶段写入唯一 gate 状态。", "! 把静力诊断全部门禁通过的终态写入唯一 gate 状态。", "静力状态说明")  # 明确该状态是静力诊断终点。
    candidate = replace_once(candidate, "! 该阶段不是最终结果通过，仅允许开始线性扰动。", "! 该状态只表示静力诊断通过，仍不包含任何模态或生产结论。", "静力结论边界说明")  # 禁止把静力通过外推为模态或生产通过。
    candidate = replace_once(candidate, "/COM,STATUS=STATIC_GATES_PASSED PHASE=PERTURB_MODAL", "/COM,STATUS=STATIC_DIAGNOSTIC_GATES_PASSED PHASE=STATIC_ONLY_COMPLETE", "静力通过状态")  # 禁止把静力诊断包描述成已进入模态。
    candidate = replace_once(candidate, "! 恢复主输出，准备扰动求解。", "! 恢复主输出，准备结束静力专用 MAPDL 会话。", "静力退出说明")  # 使末端注释与主动截断模态的行为一致。
    modal_anchor = "! 进入求解处理器并从 LS2 最高收敛帧建立线性扰动。"  # 使用父主控中唯一的模态入口注释作为截断锚点。
    require(candidate.count(modal_anchor) == 1, "模态截断锚点不是唯一一次")  # 防止错误截断静力 QA 或保留部分模态命令。
    candidate = candidate.split(modal_anchor, 1)[0]  # 保留静力求解、全部静力 QA、状态输出和数据库保存，删除全部模态阶段。
    candidate += "! 静力诊断在全部门禁通过后结束；本运行不生成或宣称任何模态结果。" + newline  # 记录静力专用边界。
    candidate += "/EXIT,NOSAVE" + newline  # 正常退出 MAPDL，会保留已写出的 RST、数据库和审计文本。
    require("PERTURB,MODAL" not in candidate and "MODOPT," not in candidate, "静力诊断输入仍残留模态求解命令")  # 确认模态控制流完全移除。
    require(candidate.count("KBC,0") == 1 and candidate.count("KBC,1") == 1, "LS1 形成态阶跃与 LS2 零增量保持的 KBC 配置不唯一")  # 确认只有 LS1 使用完整恒载阶跃，LS2 仍使用原有保持设置。
    require("NSUBST,20,200,20" not in candidate and candidate.count("NSUBST,1,1,1") == 2, "LS1/LS2 未同时固定为各一个完整子步")  # 排除旧二十段斜坡并固定两步各一个收敛结果点。
    require("AUTOTS,ON" not in candidate and candidate.count("AUTOTS,OFF") == 2, "LS1/LS2 未同时关闭自动时间步")  # 禁止求解器通过自动切分重建部分恒载中间路径。
    require(candidate.count("CNVTOL,") == 4, "显式收敛准则数量不是四项")  # 确认力、力矩、平移和转角准则都已冻结。
    require(candidate.count(new_jobname) == 3, "截断后作业名引用数不是预期三处")  # 诊断包只应保留 FILNAME、RST 读取和静力数据库保存。
    audit = {"schema_version": 3, "status": "PASSED", "source_sha256": sha256_bytes(source_bytes), "candidate_sha256": sha256_bytes(candidate.encode("utf-8")), "parent_jobname_reference_count": 5, "diagnostic_jobname_reference_count": 3, "change_families": ["UNIQUE_DIAGNOSTIC_IDENTITY", "EXPLICIT_NONRELAXING_CONVERGENCE_CRITERIA", "FULL_FORMED_STATE_LOAD_PAIRED_WITH_INISTATE", "STATIC_ONLY_TRUNCATION"], "load_path_change_allowed": True, "load_path_physical_basis": "MCT_FORMED_STAGE_ALOAD_AND_INITIAL_STATE_BALANCE_REQUIRE_FULL_BALANCING_LOAD_AT_FIRST_POINT", "load_path_physical_approval": "DIAGNOSTIC_HYPOTHESIS_PENDING_FULL_RECONCILIATION", "ls1": {"kbc": 1, "autots": False, "nsubst": [1, 1, 1], "time": 1.0, "physical_role": "FULL_PERMANENT_LOAD_PAIRED_WITH_FULL_INISTATE"}, "ls2": {"kbc": 0, "autots": False, "nsubst": [1, 1, 1], "time": 1.001, "physical_load_increment": 0.0, "physical_role": "ZERO_INCREMENT_EQUILIBRIUM_HOLD"}, "cnvtol": {"force_relative": float(FORCE_TOLERANCE), "moment_relative": float(MOMENT_TOLERANCE), "displacement_relative": float(DISPLACEMENT_TOLERANCE), "rotation_relative": float(ROTATION_TOLERANCE), "automatic_relaxation_allowed": False, "ignored_command_allowed": False}, "modal_commands_present": False, "production_claim_allowed": False}  # 汇总本次唯一物理路径诊断、四项不可放宽准则、静力截断范围和禁止生产外推边界。
    return candidate.encode("utf-8"), audit  # 返回保持原换行风格的诊断主控字节和审计对象。


def main() -> None:  # 无输入参数；验证冻结谱系并生成一个新的静力诊断运行包，无业务返回值。
    args = parse_args()  # 解析本次是否生成三迭代残差定位包，默认仍为完整静力诊断。
    residual_localization = bool(args.residual_localization)  # 将命令行布尔值规范化为清单和控制流共用的唯一模式标志。
    s10_force_seed = bool(args.s10_force_seed)  # 将 S10 LS2 轴力种子开关规范化为机器清单和输入变换共用标志。
    parent_dir = RUNS_ROOT / PARENT_RUN_NAME  # 定位直接消元连接父运行目录。
    micro_dir = RUNS_ROOT / MICRO_RUN_NAME  # 定位权威十二案例单层拓扑微验证目录。
    parent_manifest, micro_results = validate_parent(parent_dir, micro_dir)  # 先关闭父输入和微验证证据门。
    require(MAPDL_EXE.is_file(), f"缺少冻结 MAPDL 可执行文件：{MAPDL_EXE}")  # 生成启动合同前验证求解器路径。
    created_at = datetime.now(timezone.utc)  # 记录本次准备动作的精确 UTC 时间。
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")  # 生成含微秒的目录时间戳，防止覆盖并发或历史运行。
    run_name = f"C10_STATIC_DIAGNOSTIC_{stamp}"  # 派生只用于静力诊断的唯一运行名。
    run_dir = RUNS_ROOT / run_name  # 构造新运行根目录。
    solver_dir = run_dir / "solver"  # 构造 MAPDL 独立工作目录。
    qa_dir = run_dir / "qa"  # 构造数值与变更审计目录。
    input_snapshot_dir = run_dir / "input_snapshot"  # 构造父主控只读快照目录。
    require(not run_dir.exists(), f"目标运行目录已存在，禁止覆盖：{run_dir}")  # 强制每次诊断创建全新目录。
    solver_dir.mkdir(parents=True)  # 一次建立运行根目录和 solver 子目录。
    qa_dir.mkdir()  # 建立 QA 工件目录。
    input_snapshot_dir.mkdir()  # 建立输入快照目录。
    source_solver_dir = parent_dir / "solver"  # 定位已通过哈希门的父求解目录。
    for source_path in sorted(source_solver_dir.iterdir(), key=lambda item: item.name):  # 按文件名稳定顺序复制全部十二项求解输入。
        require(source_path.is_file(), f"父 solver 含非文件对象：{source_path.name}")  # 禁止目录或链接混入求解依赖。
        shutil.copy2(source_path, solver_dir / source_path.name)  # 保留时间和字节内容复制到独立工作目录。
    seed_audit: dict[str, Any] | None = None  # 初始化可选 S10 种子审计；非种子模式保持空值且不生成额外 include。
    if s10_force_seed:  # 只有显式种子模式才读取旧连接参考结果并生成覆盖文件。
        s10_force_csv = RUNS_ROOT / S10_FORCE_RUN_NAME / S10_FORCE_AUDIT_NAME / S10_FORCE_CSV_NAME  # 定位已审计 S10 LS2 全部 LINK180 轴力 CSV。
        s10_forces = load_s10_force_seed(s10_force_csv)  # 关闭源哈希、记录集合和全正拉力门并取得轴力映射。
        seed_bytes, seed_audit = render_s10_seed_include(s10_forces)  # 把轴力除以冻结截面面积生成逐行可复算初始应力覆盖 include。
        seed_include_path = solver_dir / S10_SEED_INCLUDE_NAME  # 构造本唯一运行内的覆盖 include 目标路径。
        seed_include_path.write_bytes(seed_bytes)  # 写入确定性 UTF-8/LF APDL 字节且不修改任何源运行。
        write_json(qa_dir / "s10_force_seed_audit.json", seed_audit)  # 保存源轴力、应力范围、数量和非生产边界的机器审计。
    old_jobname = str(parent_manifest.get("jobname"))  # 读取父主控冻结作业名前缀。
    new_jobname = f"cw_C10s_{created_at.strftime('%m%dt%H%M%S')}_d1"  # 派生不超过 32 字符的唯一 ASCII 诊断作业名。
    require(len(new_jobname) <= 32, "诊断 MAPDL 作业名超过 32 字符")  # 遵守 MAPDL 文件前缀长度限制。
    copied_parent_main = solver_dir / PARENT_MAIN_NAME  # 定位刚复制到新目录的父主控。
    parent_main_bytes = copied_parent_main.read_bytes()  # 读取父主控原始字节用于受控变换。
    require(sha256_bytes(parent_main_bytes) == str(parent_manifest.get("main_input_sha256")), "父主控摘要与清单不一致")  # 再次闭合主控身份。
    diagnostic_bytes, change_audit = transform_main(parent_main_bytes, old_jobname, new_jobname)  # 生成完整初始内力与完整恒载首步配对、保留四项收敛准则并截断模态的静力专用输入。
    if residual_localization:  # 只在显式请求残差定位时收紧迭代上限并启用求解器原生非线性诊断文件。
        diagnostic_text = diagnostic_bytes.decode("utf-8")  # 严格解码已通过结构变换门的完整形成态诊断输入。
        diagnostic_newline = "\r\n" if "\r\n" in diagnostic_text else "\n"  # 保留诊断输入继承的 CRLF 或 LF 换行风格。
        iteration_source = "! 每个 LS1 子步最多允许 100 次平衡迭代。" + diagnostic_newline + "NEQIT,100" + diagnostic_newline  # 冻结完整诊断中唯一百次迭代控制片段。
        iteration_target = f"! 残差定位仅允许 {RESIDUAL_MAX_ITERATIONS} 次完整 Newton 迭代，超过后由 MAPDL 正常拒绝该未平衡状态。" + diagnostic_newline + f"NLDIAG,NRRE,ON,{RESIDUAL_MAX_ITERATIONS}" + diagnostic_newline + f"NLDIAG,EFLG,ON,{RESIDUAL_MAX_ITERATIONS}" + diagnostic_newline + f"NEQIT,{RESIDUAL_MAX_ITERATIONS}" + diagnostic_newline  # 同时保存节点残差和异常单元文件，且不放宽任何收敛标准。
        diagnostic_text = replace_once(diagnostic_text, iteration_source, iteration_target, "三迭代 NRRE/EFLG 定位控制")  # 受控替换迭代合同并保留 FULL Newton、线搜索和四项 CNVTOL。
        diagnostic_text = replace_once(diagnostic_text, "/TITLE,C10 DIRECT MPC STATIC FULL-FORMED-STATE EQUILIBRIUM-PAIR DIAGNOSTIC", "/TITLE,C10 DIRECT MPC FULL-STATE NRRE RESIDUAL-LOCALIZATION DIAGNOSTIC", "残差定位标题")  # 使求解器输出明确声明本运行不追求可发布静力终态。
        diagnostic_bytes = diagnostic_text.encode("utf-8")  # 重新编码保持内容确定性的残差定位主输入。
        change_audit["candidate_sha256"] = sha256_bytes(diagnostic_bytes)  # 用最终残差输入摘要替换完整静力候选摘要，保证 manifest 与真实入口一致。
        change_audit["change_families"] = [*change_audit["change_families"], "NLDIAG_NRRE_EFLG_THREE_ITERATION_LOCALIZATION"]  # 在既有变更族后追加唯一诊断输出变更，不掩盖形成态路径身份。
        change_audit["residual_localization"] = {"enabled": True, "maximum_equilibrium_iterations": RESIDUAL_MAX_ITERATIONS, "nrre_max_files": RESIDUAL_MAX_ITERATIONS, "eflg_max_files": RESIDUAL_MAX_ITERATIONS, "converged_static_result_expected": False, "model_or_load_change": False}  # 冻结三迭代诊断范围、文件上限和非结果用途边界。
    elif s10_force_seed:  # S10 种子模式只覆盖初始应力来源，不改变完整形成态恒载、corrected-MPC 或收敛标准。
        require(seed_audit is not None, "S10 种子模式缺少已生成审计对象")  # 防止输入引用未成功生成或未通过门禁的覆盖 include。
        diagnostic_text = diagnostic_bytes.decode("utf-8")  # 严格解码已完成形成态路径变换的静力诊断输入。
        diagnostic_newline = "\r\n" if "\r\n" in diagnostic_text else "\n"  # 保留父主控的换行风格。
        seed_anchor = "/INPUT,apply_mct_authoritative_initial_state_link180,inp" + diagnostic_newline  # 冻结原始 MCT 初态 include 的唯一调用锚点。
        seed_insertion = seed_anchor + "! 用已审计 S10 LS2 轴力完整覆盖 TYPE4 初始应力；该种子仍须在 corrected-MPC 上重新平衡。" + diagnostic_newline + f"/INPUT,{Path(S10_SEED_INCLUDE_NAME).stem},inp" + diagnostic_newline  # 在截面/类型转换完成后立即删除旧初态并加载新种子。
        diagnostic_text = replace_once(diagnostic_text, seed_anchor, seed_insertion, "S10 LS2 轴力种子 include")  # 保证种子调用唯一且先于有限门架、质量和恒载装配。
        diagnostic_text = replace_once(diagnostic_text, "/TITLE,C10 DIRECT MPC STATIC FULL-FORMED-STATE EQUILIBRIUM-PAIR DIAGNOSTIC", "/TITLE,C10 DIRECT MPC S10-LS2-FORCE-SEED FULL-STATE DIAGNOSTIC", "S10 种子诊断标题")  # 使 OUT 明确区分原始 MCT 初态与旧平衡力种子。
        diagnostic_bytes = diagnostic_text.encode("utf-8")  # 编码最终 S10 种子诊断主输入。
        change_audit["candidate_sha256"] = sha256_bytes(diagnostic_bytes)  # 用种子调用后的真实主控摘要更新输入身份。
        change_audit["change_families"] = [*change_audit["change_families"], "S10_LS2_LINK180_FORCE_SEED_OVERRIDE"]  # 登记唯一初态来源变化且不掩盖形成态路径和静力截断。
        change_audit["initial_state_seed"] = seed_audit  # 把源 CSV、记录数、轴力/应力范围和覆盖语义嵌入主控审计。
        change_audit["load_path_physical_basis"] = "S10_LS2_FULL_SPATIAL_MASS_EQUILIBRIUM_FORCE_STATE_TRANSFERRED_TO_KINEMATICALLY_VERIFIED_CORRECTED_MPC"  # 记录种子转移的工程依据。
        change_audit["load_path_physical_approval"] = "DIAGNOSTIC_TRANSFER_PENDING_CORRECTED_MPC_REEQUILIBRATION_AND_INDEPENDENT_CHECK"  # 明确旧连接结果只能作为迭代种子而非批准状态。
    diagnostic_main = solver_dir / DIAGNOSTIC_MAIN_NAME  # 构造诊断主输入目标路径。
    diagnostic_main.write_bytes(diagnostic_bytes)  # 写入变换后的 UTF-8 原始字节。
    copied_parent_main.unlink()  # 删除 solver 中未授权启动的全模态父主控，避免误选错误入口。
    shutil.copy2(parent_dir / "solver" / PARENT_MAIN_NAME, input_snapshot_dir / PARENT_MAIN_NAME)  # 在快照目录保留未修改父主控供差分复核。
    write_json(qa_dir / "diagnostic_control_audit.json", change_audit)  # 保存形成态首步配对、收敛准则和静力截断范围的机器审计。
    write_json(qa_dir / "micro_validation_reference.json", {"schema_version": 2, "status": micro_results["status"], "run_name": MICRO_RUN_NAME, "unit_test_results_sha256": sha256_file(micro_dir / "unit_test_results.json"), "constraint_topology": micro_results["constraint_topology"], "planned_case_count": micro_results["planned_case_count"], "passed_case_count": micro_results["passed_case_count"], "failed_case_count": micro_results["failed_case_count"]})  # 冻结本诊断所依赖的 12/12 单层 TYPE72 微验证证据。
    launch_argv = [str(MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", new_jobname, "-dir", str(solver_dir), "-i", str(diagnostic_main), "-o", str(solver_dir / f"{new_jobname}.out")]  # 构造静力诊断专用单进程参数，不含 DMP/MPI 和模态。
    launch_command = "& " + " ".join("'" + part.replace("'", "''") + "'" for part in launch_argv) + "\n"  # 生成可直接审计的 PowerShell 引号命令文本。
    (run_dir / "launch_command_smp1.txt").write_text(launch_command, encoding="utf-8", newline="\n")  # 写出命令但本准备脚本本身不启动 MAPDL。
    if residual_localization:  # 为残差定位选择不期望静力通过的机器合同。
        diagnostic_subtype = "FULL_STATE_NRRE_RESIDUAL_LOCALIZATION"  # 标识三迭代 NRRE/EFLG 定位子类型。
        analysis_scope = "FULL_BRIDGE_LS1_THREE_ITERATION_NRRE_EFLG_LOCALIZATION_ONLY"  # 明确该模式预期止于 LS1 未平衡诊断。
        next_action = "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_AND_POSTPROCESS_NRRE_WITHOUT_STATIC_CLAIM"  # 冻结运行后只允许残差后处理。
        full_bridge_static_status = "RESIDUAL_LOCALIZATION_PREPARED_NOT_A_STATIC_RESULT"  # 阻止准备状态被误读为静力候选。
        load_path_mode = "FULL_FORMED_STATE_STEP_PAIRED_WITH_INISTATE"  # 保持本次被定位的原始 MCT 初态形成态路径身份。
        initial_state_load_path = "FULL_FORMED_STATE_STEP_PAIRED_WITH_INISTATE"  # 记录初态与恒载配对方式未被诊断输出命令改变。
        initial_state_audit = "DIAGNOSTIC_PAIRING_TEST_PENDING_FULL_PHYSICAL_RECONCILIATION"  # 保持原始初态物理对账待决。
        static_result_expected = False  # 三迭代模式不允许发布静力结果。
    elif s10_force_seed:  # 为 S10 LS2 轴力种子选择完整静力重平衡合同。
        diagnostic_subtype = "S10_LS2_FORCE_SEED_CORRECTED_MPC_REEQUILIBRATION"  # 标识旧平衡力向 corrected-MPC 转移的诊断子类型。
        analysis_scope = "FULL_BRIDGE_STATIC_LS1_LS2_AND_STATIC_GATES_WITH_S10_FORCE_SEED"  # 允许 LS1、零增量 LS2 和全部静力硬门执行。
        next_action = "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_S10_SEED_REEQUILIBRATION_WITH_MONITORING"  # 冻结启动后的唯一动作。
        full_bridge_static_status = "S10_FORCE_SEED_REEQUILIBRATION_PREPARED_NOT_STARTED"  # 明确种子尚未在新拓扑上求解。
        load_path_mode = "FULL_FORMED_STATE_STEP_PAIRED_WITH_S10_LS2_FORCE_SEED"  # 区分原始 MCT INIFORCE 与 S10 终态轴力种子。
        initial_state_load_path = "S10_LS2_LINK180_FORCE_SEED_PLUS_FULL_PERMANENT_LOAD_SINGLE_STEP"  # 记录完整恒载与转移种子在 LS1 唯一点配对。
        initial_state_audit = "S10_FORCE_SEED_TRANSFER_PENDING_CORRECTED_MPC_REEQUILIBRATION"  # 禁止把旧连接平衡直接外推为新拓扑批准状态。
        static_result_expected = True  # 该模式允许求解器尝试完整静力门，但仍不保证通过。
    else:  # 为默认原始 MCT 初态形成态诊断选择完整静力合同。
        diagnostic_subtype = "FULL_STATE_STATIC_EQUILIBRIUM_PAIR"  # 标识不含额外种子或残差输出变更的默认子类型。
        analysis_scope = "FULL_BRIDGE_STATIC_LS1_LS2_AND_STATIC_GATES_ONLY"  # 允许完整静力求解与门禁。
        next_action = "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_STATIC_ONLY_WITH_MONITORING"  # 冻结默认启动动作。
        full_bridge_static_status = "PREPARED_NOT_STARTED"  # 明确尚未产生求解结果。
        load_path_mode = "FULL_FORMED_STATE_STEP_PAIRED_WITH_INISTATE"  # 记录原始 MCT 初态形成态路径。
        initial_state_load_path = "FULL_FORMED_STATE_STEP_PAIRED_WITH_INISTATE"  # 记录初态与恒载单步配对方式。
        initial_state_audit = "DIAGNOSTIC_PAIRING_TEST_PENDING_FULL_PHYSICAL_RECONCILIATION"  # 保持物理对账待决。
        static_result_expected = True  # 默认模式允许完整静力求解尝试。
    status = {"schema_version": 1, "run_name": run_name, "jobname": new_jobname, "status": "STATIC_DIAGNOSTIC_PREPARED", "diagnostic_subtype": diagnostic_subtype, "created_at_utc": created_at.isoformat(), "parent_run": PARENT_RUN_NAME, "micro_validation_run": MICRO_RUN_NAME, "mapdl_execution_attempted": False, "mapdl_started": False, "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "resource_gate": "FORMAL_8_GIB_FAILED_DIAGNOSTIC_EXCEPTION_REQUIRES_RUNTIME_RECHECK", "launch_allowed_for_diagnostic": True, "launch_allowed_for_production": False, "full_bridge_static_status": full_bridge_static_status, "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "next_action": next_action}  # 明确准备完成、残差定位或种子重平衡范围均不等于工程通过。
    manifest = {"schema_version": 4, "run_name": run_name, "jobname": new_jobname, "status": status["status"], "diagnostic_subtype": diagnostic_subtype, "created_at_utc": created_at.isoformat(), "parent_run": PARENT_RUN_NAME, "parent_main_sha256": change_audit["source_sha256"], "micro_validation_run": MICRO_RUN_NAME, "micro_validation_status": micro_results["status"], "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "expected_topology": parent_manifest["expected_topology"], "main_input": f"solver/{DIAGNOSTIC_MAIN_NAME}", "main_input_sha256": change_audit["candidate_sha256"], "mapdl_executable": str(MAPDL_EXE), "mapdl_executable_sha256": sha256_file(MAPDL_EXE), "execution_mode": status["execution_mode"], "analysis_scope": analysis_scope, "load_path_mode": load_path_mode, "initial_state_load_path": initial_state_load_path, "initial_state_equilibrium_audit": initial_state_audit, "initial_state_seed_include": f"solver/{S10_SEED_INCLUDE_NAME}" if s10_force_seed else None, "initial_state_seed_include_sha256": str(seed_audit["include_sha256"]) if seed_audit is not None else None, "initial_state_seed_source_csv_sha256": S10_FORCE_CSV_SHA256 if s10_force_seed else None, "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None, "modal_requested": False, "production_claim_allowed": False, "static_result_expected": static_result_expected, "runtime_equation_count_change_allowed": False, "runtime_small_zero_negative_pivot_allowed": False, "runtime_ignored_or_reset_cnvtol_allowed": False, "launch_argv": launch_argv}  # 汇总求解器、单层拓扑、初态种子身份、静力子类型、运行时硬门和待闭合物理审计。
    write_json(run_dir / "C10_static_status.json", status)  # 保存根级运行状态。
    write_json(run_dir / "manifest.json", manifest)  # 保存完整诊断运行清单。
    mode_description = f"`diagnostic_subtype=FULL_STATE_NRRE_RESIDUAL_LOCALIZATION` 时，`NEQIT={RESIDUAL_MAX_ITERATIONS}` 且 `NLDIAG,NRRE/EFLG,ON,{RESIDUAL_MAX_ITERATIONS}`；该模式预期以未收敛终止来定位节点残差和异常单元，不生成静力结果。" if residual_localization else ("`diagnostic_subtype=S10_LS2_FORCE_SEED_CORRECTED_MPC_REEQUILIBRATION` 时，原始 MCT 初态先完整删除，再用已审计 S10 LS2 轴力除以冻结截面面积重建 73,692 条正初始应力；该状态只是迭代种子。" if s10_force_seed else "`diagnostic_subtype=FULL_STATE_STATIC_EQUILIBRIUM_PAIR` 时，允许完整 LS1、LS2 和静力门禁执行。")  # 为 JSON 无注释字段提供与三种互斥子类型严格一致的伴随说明。
    field_dictionary = f"# 静力诊断机器字段说明\n\nJSON 不支持注释，因此字段语义集中记录于此。`STATIC_DIAGNOSTIC_PREPARED` 仅表示输入已生成且证据门通过，不表示 MAPDL 已启动。`SMP_SERIAL_NP1_DIAGNOSTIC_ONLY` 是低内存条件下的诊断例外，不替代正式 DMP4 运行。父连接拓扑为 5,078 个单层 TYPE72，辅助节点和 TYPE73 均为零。LS1 使用 `KBC=1`、`AUTOTS=false`、`NSUBST=[1,1,1]`，把完整恒载与本清单指定的完整初始状态在一个形成态平衡点直接配对；LS2 使用 `KBC=0`、`AUTOTS=false`、`NSUBST=[1,1,1]` 做零物理增量保持。{mode_description} 初始状态转移不代表物理审计已经闭合；S10 旧约束警告、MCT INIFORCE/EQUI-MFORCE 与 APDL INISTATE 的逐项对账仍须独立处理。力、力矩、平移和转角四项 `CNVTOL` 均保留并禁止 MAPDL 自动放宽或忽略。运行后所有 `Number of equations` 必须恒定，small/zero/negative pivot 必须为零。`modal_requested=false` 表示本包主动截断全部模态命令。力单位为 N，长度为 mm，力矩为 N·mm，质量为 tonne，时间为 s。\n"  # 解释无注释格式中全部关键配置、初态种子、残差子类型、硬门和结论边界。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出伴随字段字典。
    result_scope_line = f"- 残差定位：只允许 {RESIDUAL_MAX_ITERATIONS} 次 Newton 迭代并保存 NRRE/EFLG；预期未收敛终止，不执行 LS2，也不生成静力结果。" if residual_localization else ("- 初态种子：使用 S10 LS2 的 73,692 条全正轴力重建初始应力，只作为 corrected-MPC 重新平衡的起点；允许执行 LS1、LS2 和全部静力门禁。" if s10_force_seed else "- 分析范围：允许执行 LS1、LS2 和全部静力门禁，但仍不执行模态。")  # 生成与三种清单子类型一致的单行人读范围说明。
    result_packet = f"# C10 全桥单层 TYPE72 形成态配平诊断准备结果\n\n状态：`STATIC_DIAGNOSTIC_PREPARED`；子类型：`{diagnostic_subtype}`。\n\n- 父连接方案：`{PARENT_RUN_NAME}`，5,078 个单层 TYPE72；辅助节点=0、TYPE73=0、罚刚度=`null`。\n- 微验证：`{MICRO_RUN_NAME}`，12/12 通过，三类案例方程数均恒定。\n- 初始状态路径：`{initial_state_load_path}`；LS1 固定 `KBC=1`、`AUTOTS=OFF`、`NSUBST=1`，LS2 保持零物理增量。\n- 未删判据：力、力矩、平移和转角四项 `CNVTOL` 全部保留，不允许以残差偶然过线冒充稳定平衡。\n{result_scope_line}\n- 运行后硬门：方程总数全程恒定，small/zero/negative pivot 为零，MAPDL error 为零。\n- 已截断：全部模态命令；本运行不得产生模态结论。\n- 待决项：S10 旧约束局限、MCT `INIFORCE/EQUI-MFORCE` 与 APDL `INISTATE` 的物理平衡仍须独立对账，本诊断也不等于生产批准。\n- 资源边界：正式 8 GiB RAM 门未通过；只允许 SMP1 受控诊断例外，不能作为生产结果。\n- 当前未启动 MAPDL，静力和模态均没有结果结论。\n"  # 生成供人工快速审阅且区分残差定位、S10 种子和默认静力的准备结论。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出用户可读结果包。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用摘要表外的全部生成工件。
    artifact_lines = [f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 生成稳定排序的相对路径摘要行。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 写出准备阶段完整工件哈希账本。
    print(str(run_dir))  # 向调用者输出唯一新运行目录，便于后续启动和监控。


if __name__ == "__main__":  # 仅在作为脚本直接执行时进入生成流程。
    main()  # 执行一次可审计静力诊断准备，不自动调用求解器。
