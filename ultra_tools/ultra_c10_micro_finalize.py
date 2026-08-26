"""复核 C10 单层 TYPE72 微算例，并在执行子运行内生成不可覆盖的验收工件。"""  # 本模块只读 prepare 与原始求解结果，不启动 MAPDL，也不修改封板输入。

from __future__ import annotations  # 延迟解析类型注解，保持与项目现有 Python 版本兼容。

import argparse  # 解析 prepare 运行名与微算例执行运行名两个受控参数。
import hashlib  # 计算输入、输出、结果和验收工件的 SHA-256 摘要。
import json  # 读取计划与运行记录，并写合法机器验收 JSON。
import math  # 计算有限转动解析值并拒绝非有限数值。
import re  # 严格解析 MAPDL 文本结果向量和日志摘要。
from pathlib import Path  # 安全定位项目目录、运行目录和原始结果文件。
from typing import Any  # 描述 JSON 字典、异构案例记录和数值向量。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前 finalizer 绝对路径，供源码哈希和目录推导使用。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是当前 finalizer 的所属目录。
PROJECT_DIR = TOOLS_DIR.parent  # 项目目录包含 ultra_runs 与全部求解工件。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 所有输入和执行子运行必须位于统一运行目录。
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"  # MAPDL 科学计数、整数和小数的严格有限数词法。
OFFSET_VECTOR_MM = (800.0, -600.0, 500.0)  # 三类微算例共用的非共线偏置向量，单位 mm。
EXPECTED_CASE_COUNT = 12  # 三个生产拓扑 UXYZ、三个受矩有限转动和六个 ALL 案例的封板总数。


def require(condition: bool, message: str) -> None:  # 输入门禁条件与失败说明；条件为假时立即抛错且无返回值。
    """统一实现路径、哈希、日志、数值和输出的 fail-closed 门禁。"""  # 调用方不得捕获后继续发布通过结论。
    if not condition:  # 只有当前门禁不成立时进入拒绝路径。
        raise RuntimeError(message)  # 抛出可定位原因并终止 finalizer。


def sha256_file(path: Path) -> str:  # 输入普通文件路径并返回 64 位小写 SHA-256。
    """以 1 MiB 分块读取，避免把 MAPDL OUT 一次性装入哈希缓冲。"""  # 文件缺失时由 open 直接抛错。
    digest = hashlib.sha256()  # 创建空 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读模式打开，禁止编码和换行转换。
        while True:  # 持续读取直到到达文件末尾。
            chunk = stream.read(1024 * 1024)  # 每块 1 MiB，用于限制哈希峰值内存。
            if not chunk:  # 空字节块表示已经到达文件末尾。
                break  # 结束当前文件的分块读取循环。
            digest.update(chunk)  # 把当前原始字节纳入摘要。
    return digest.hexdigest()  # 返回全部字节闭合后的摘要。


def read_json(path: Path) -> dict[str, Any]:  # 输入 JSON 路径并返回顶层对象字典。
    """严格要求 UTF-8 JSON 顶层为对象。"""  # 非法编码、非法 JSON 或数组顶层均拒绝。
    value = json.loads(path.read_text(encoding="utf-8"))  # 以 UTF-8 读取并解析完整 JSON。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 后续字段访问要求字典语义。
    return value  # 返回已验证顶层类型的对象。


def write_new_text(path: Path, value: str) -> None:  # 输入新路径与文本；目标存在时拒绝且无返回值。
    """所有 finalizer 工件采用 UTF-8、LF 和不可覆盖写入。"""  # 保留先前验收结果并防止静默改写。
    require(not path.exists(), f"拒绝覆盖既有验收工件：{path}")  # 同名结果一旦存在必须换新执行运行。
    with path.open("x", encoding="utf-8", newline="\n") as stream:  # 使用 x 模式提供操作系统级不可覆盖保证。
        stream.write(value)  # 一次写出已经在内存完成验证的文本。


def write_new_json(path: Path, value: dict[str, Any]) -> None:  # 输入新路径与 JSON 对象并写合法 UTF-8 文件。
    """JSON 使用两空格缩进且保留中文，不向无注释语法中注入伪注释。"""  # 字段含义同时写入 result_packet.md。
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 禁止 NaN/Infinity 并固定末尾换行。
    write_new_text(path, text)  # 复用不可覆盖 UTF-8 写入。


def resolve_run(name: str, expected_prefix: str) -> Path:  # 输入运行名与前缀并返回位于 ultra_runs 的绝对目录。
    """拒绝路径分隔符、父目录跳转和错误模型线。"""  # 返回目录存在且已经 resolve。
    require(name == Path(name).name, f"运行名包含路径字符：{name}")  # 只允许单个目录名而非任意路径。
    require(name.startswith(expected_prefix), f"运行名前缀错误：{name}")  # 区分 prepare 与 execution 两类运行。
    path = (ULTRA_RUNS_DIR / name).resolve()  # 解析绝对目录并消除可能的相对段。
    require(path.parent == ULTRA_RUNS_DIR.resolve(), f"运行目录越出 ultra_runs：{path}")  # 限定唯一允许的父目录。
    require(path.is_dir(), f"运行目录不存在：{path}")  # finalizer 只接受既有运行目录。
    return path  # 返回已通过边界检查的目录。


def parse_vector(text: str, label: str) -> tuple[float, float, float]:  # 输入机器结果文本和字段标签并返回三分量浮点向量。
    """字段必须唯一且三项均为有限数。"""  # MAPDL 结果用逗号分隔并允许科学计数法。
    number = f"({NUMBER_PATTERN})"  # 为三分量正则创建一个捕获数值词法。
    pattern = re.compile(rf"{re.escape(label)}\s*=\s*{number}\s*,\s*{number}\s*,\s*{number}\s*,", re.ASCII)  # 构造标签和三个数值的完整模式。
    matches = list(pattern.finditer(text))  # 收集全部匹配以拒绝字段缺失或重复。
    require(len(matches) == 1, f"结果字段 {label} 匹配数为 {len(matches)}，预期 1")  # 每个向量只能出现一次。
    values = tuple(float(matches[0].group(index)) for index in (1, 2, 3))  # 把三个捕获组转换为浮点数。
    require(all(math.isfinite(value) for value in values), f"结果字段 {label} 含非有限数")  # 禁止 NaN 与无穷进入误差计算。
    return values  # 返回已验证的三分量向量。


def vector_add(*vectors: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入任意数量三分量向量并返回逐项和。
    """空输入返回零向量；当前调用至少有两个向量。"""  # 数值单位由调用上下文决定。
    return tuple(sum(vector[index] for vector in vectors) for index in range(3))  # 对 X、Y、Z 三项分别求和。


def vector_subtract(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入左右向量并返回 left-right。
    """用于计算接口滑移、解析误差和转角误差。"""  # 两向量必须使用相同单位。
    return tuple(left[index] - right[index] for index in range(3))  # 对三项执行有符号差。


def vector_cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入位置与力向量并返回右手叉积。
    """当前用于计算偏置力关于 master 的力矩，单位 N·mm。"""  # 输入顺序固定为 r×F。
    return (left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0])  # 按右手笛卡尔公式返回三分量。


def max_abs(vector: tuple[float, float, float]) -> float:  # 输入三分量向量并返回最大绝对值。
    """统一形成滑移、平衡和解析误差的无符号标量。"""  # 返回值单位与输入一致。
    return max(abs(value) for value in vector)  # 取三个绝对值中的最大值。


def load_vectors(label: str, value: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:  # 输入 APDL 荷载标签和值并返回力与力矩向量。
    """只允许 FX/FY/FZ/MX/MY/MZ 六个单位工况。"""  # 力单位 N，力矩单位 N·mm。
    require(label in {"FX", "FY", "FZ", "MX", "MY", "MZ"}, f"不支持的荷载标签：{label}")  # 拒绝计划外自由度。
    force = [0.0, 0.0, 0.0]  # 初始化全局力零向量，单位 N。
    moment = [0.0, 0.0, 0.0]  # 初始化全局力矩零向量，单位 N·mm。
    axis = {"X": 0, "Y": 1, "Z": 2}[label[1]]  # 把第二字符的全局轴映射为向量下标。
    if label[0] == "F":  # F 前缀表示当前值属于力向量。
        force[axis] = value  # 在目标轴写入当前力值。
    else:  # 唯一剩余前缀 M 表示当前值属于力矩向量。
        moment[axis] = value  # 在目标轴写入当前力矩值。
    return tuple(force), tuple(moment)  # 返回不可变三分量力与力矩向量。


def rodrigues_displacement(rotation_label: str, angle_rad: float) -> tuple[float, float, float]:  # 输入转轴标签与角度并返回偏置点解析位移。
    """对全局 X/Y/Z 单轴转动使用等价 Rodrigues 旋转矩阵。"""  # 初始偏置固定为 OFFSET_VECTOR_MM。
    x_value, y_value, z_value = OFFSET_VECTOR_MM  # 读取初始偏置三个坐标分量，单位 mm。
    cosine = math.cos(angle_rad)  # 计算当前角度余弦。
    sine = math.sin(angle_rad)  # 计算当前角度正弦。
    if rotation_label == "ROTX":  # 绕全局 X 轴按右手规则旋转。
        rotated = (x_value, y_value * cosine - z_value * sine, y_value * sine + z_value * cosine)  # 形成绕 X 旋转后的坐标。
    elif rotation_label == "ROTY":  # 绕全局 Y 轴按右手规则旋转。
        rotated = (x_value * cosine + z_value * sine, y_value, -x_value * sine + z_value * cosine)  # 形成绕 Y 旋转后的坐标。
    elif rotation_label == "ROTZ":  # 绕全局 Z 轴按右手规则旋转。
        rotated = (x_value * cosine - y_value * sine, x_value * sine + y_value * cosine, z_value)  # 形成绕 Z 旋转后的坐标。
    else:  # 任何其他标签均越出冻结三轴测试合同。
        raise RuntimeError(f"不支持的有限转动标签：{rotation_label}")  # 拒绝生成无解析基准的结论。
    return vector_subtract(rotated, OFFSET_VECTOR_MM)  # 返回旋转后坐标减初始坐标得到的位移，单位 mm。


def rodrigues_displacement_vector(rotation_vector_rad: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入三分量旋转向量并返回固定偏置点的有限转动位移。
    """使用轴角 Rodrigues 公式；零转角返回严格零向量。"""  # 该函数覆盖 UXYZ 荷载案例的小三轴组合转角和单轴有限转动。
    angle_rad = math.sqrt(sum(value * value for value in rotation_vector_rad))  # 计算旋转向量欧氏模，单位 rad。
    if angle_rad == 0.0:  # 仅在三个旋转分量均严格为零时进入无转动路径。
        return (0.0, 0.0, 0.0)  # 返回严格零位移，避免用零角度归一化旋转轴。
    axis = tuple(value / angle_rad for value in rotation_vector_rad)  # 将旋转向量归一化为右手单位转轴。
    cosine = math.cos(angle_rad)  # 计算轴角旋转矩阵的余弦项。
    sine = math.sin(angle_rad)  # 计算轴角旋转矩阵的正弦项。
    axis_cross_offset = vector_cross(axis, OFFSET_VECTOR_MM)  # 计算单位轴与初始偏置的叉积，单位 mm。
    axis_dot_offset = sum(axis[index] * OFFSET_VECTOR_MM[index] for index in range(3))  # 计算偏置在旋转轴上的投影标量，单位 mm。
    rotated = tuple(OFFSET_VECTOR_MM[index] * cosine + axis_cross_offset[index] * sine + axis[index] * axis_dot_offset * (1.0 - cosine) for index in range(3))  # 按 Rodrigues 公式形成旋转后的偏置坐标。
    return vector_subtract(rotated, OFFSET_VECTOR_MM)  # 返回旋转后坐标减初始坐标得到的刚体偏心位移，单位 mm。


def common_log_checks(record: dict[str, Any], output_text: str) -> dict[str, Any]:  # 输入运行记录和 OUT 文本并返回共同日志门禁。
    """成功必须同时满足进程、MAPDL 摘要、结果文件和数值警戒标志。"""  # 警告数量单独报告但不要求为零。
    output_upper = output_text.upper()  # 统一大写日志以执行不区分大小写的固定短语检查。
    checks = {  # 初始化共同日志布尔门禁对象。
        "exit_code_zero": record.get("exit_code") == 0,  # 外部进程必须正常退出。
        "not_timed_out": record.get("timed_out") is False,  # 五分钟案例硬上限不得触发。
        "run_completed": record.get("run_completed") is True and "RUN COMPLETED" in output_upper,  # OUT 与运行记录必须同时含完成标记。
        "error_count_zero": record.get("error_count") == 0,  # MAPDL 摘要必须为零错误。
        "fatal_marker_absent": record.get("fatal_marker") is False and "*** ERROR ***" not in output_upper and "PROBLEM TERMINATED" not in output_upper,  # 禁止任何终止错误文本。
        "output_file_present": record.get("output_exists") is True,  # MAPDL 标准输出必须存在且已登记哈希。
        "result_file_present": record.get("result_exists") is True,  # 预注册机器结果文件必须存在。
        "automatic_cnvtol_reset_absent": record.get("automatic_cnvtol_reset") is False and "INTERNALLY RESET TO CNVTOL" not in output_upper,  # 禁止自动放宽收敛标准。
        "ignored_cnvtol_command_absent": "CNVTOL COMMAND IS IGNORED" not in output_upper,  # 禁止参数错位等原因让显式收敛命令失效。
        "zero_pivot_absent": record.get("zero_pivot") is False and re.search(r"zero pivot", output_text, re.IGNORECASE) is None,  # 禁止零主元或其同义文本。
        "small_pivot_absent": record.get("small_pivot") is False and re.search(r"small(?: equation solver)? pivot", output_text, re.IGNORECASE) is None,  # 禁止旧全桥失败中出现的小主元。
        "negative_pivot_absent": record.get("negative_pivot") is False and re.search(r"negative pivot", output_text, re.IGNORECASE) is None,  # 禁止负主元或其同义文本。
        "equation_count_constant": record.get("equation_count_constant") is True and len(record.get("unique_equation_counts", [])) == 1,  # 每案例必须实际报告且只报告一个方程总数。
    }  # 完成共同日志门禁对象。
    checks["passed"] = all(checks.values())  # 共同日志结论要求以上每项均为真。
    return checks  # 返回逐项布尔值供案例结果与总报告引用。


def finalize(prepare_name: str, execution_name: str) -> Path:  # 输入 prepare 与 execution 运行名并返回已写验收 JSON 路径。
    """执行哈希、日志、方程数、刚体运动学和反力平衡复核。"""  # 任一案例数值失败仍写 FAIL 报告，但输入契约损坏会立即抛错。
    prepare_dir = resolve_run(prepare_name, "C10_MPC_ONLY_")  # 解析并验证单层 TYPE72 prepare 运行目录。
    execution_dir = resolve_run(execution_name, "C10_MICRO_VALIDATION_")  # 解析并验证微算例执行目录。
    plan_path = prepare_dir / "qa" / "connection_unit_test_plan.json"  # 定位封板十二案例计划。
    record_path = execution_dir / "solver_run_record.json"  # 定位独立执行器的原始运行记录。
    plan = read_json(plan_path)  # 读取 prepare 案例合同与预注册验收阈值。
    run_record = read_json(record_path)  # 读取每案例外部进程、日志和方程数记录。
    require(plan.get("schema_version") == 3, "prepare 计划不是单层拓扑 schema 3")  # 阻断旧双层链十五案例计划。
    require(run_record.get("schema_version") == 3, "执行记录不是单层拓扑 schema 3")  # 阻断旧执行器账本。
    require(plan.get("planned_case_count") == EXPECTED_CASE_COUNT, "prepare 计划案例数不是 12")  # 固定三加三加六合同。
    require(run_record.get("planned_case_count") == EXPECTED_CASE_COUNT, "执行记录计划案例数不是 12")  # 执行范围必须等于 prepare。
    require(run_record.get("completed_case_count") == EXPECTED_CASE_COUNT, "执行记录完成案例数不是 12")  # 禁止部分执行冒充完整验证。
    require(run_record.get("status") == "RAW_EXECUTION_COMPLETED_PENDING_NUMERICAL_FINALIZATION", "执行记录状态不是待数值验收")  # 只接受十二个进程均已返回的原始账本。
    require(run_record.get("prepare_run") == prepare_name, "执行记录引用的 prepare 运行不一致")  # 防止结果错配到另一输入包。
    require(run_record.get("prepare_plan_sha256") == sha256_file(plan_path), "执行记录中的计划哈希不匹配")  # 计划字节必须从执行到 finalizer 保持不变。
    formulation = plan.get("formulation")  # 读取约束公式对象以再次关闭旧链门禁。
    require(isinstance(formulation, dict), "prepare formulation 不是对象")  # 后续字段访问要求字典。
    require(formulation.get("aux_node_count") == 0 and formulation.get("type73_count") == 0, "prepare 仍含辅助节点或 TYPE73")  # 验收对象必须是一条逻辑连接对应一个 TYPE72。
    plan_cases = plan.get("cases")  # 读取 prepare 的十二个案例对象。
    record_cases = run_record.get("cases")  # 读取执行记录的十二个案例对象。
    require(isinstance(plan_cases, list) and len(plan_cases) == EXPECTED_CASE_COUNT, "prepare cases 不是十二项数组")  # 保证计划案例可稳定迭代。
    require(isinstance(record_cases, list) and len(record_cases) == EXPECTED_CASE_COUNT, "执行 cases 不是十二项数组")  # 保证运行记录可稳定映射。
    record_by_id = {str(item.get("case_id")): item for item in record_cases if isinstance(item, dict)}  # 建立稳定 CASE-ID 到执行记录映射。
    require(len(record_by_id) == EXPECTED_CASE_COUNT, "执行案例 ID 缺失或重复")  # 每个 CASE-ID 必须恰好一条记录。
    acceptance = plan.get("acceptance")  # 读取封板数值验收阈值对象。
    require(isinstance(acceptance, dict), "prepare acceptance 不是对象")  # 后续阈值访问要求字典。
    rigid_translation_limit = float(acceptance["max_rigid_body_translation_error_mm"])  # 读取生产拓扑刚体偏心平移误差上限，单位 mm。
    rodrigues_limit = float(acceptance["finite_rotation_rodrigues_displacement_error_mm"])  # 读取有限转动 Rodrigues 位移误差上限，单位 mm。
    target_angle_limit = float(acceptance["finite_rotation_target_angle_error_rad"])  # 读取受矩弹簧终态相对 0.1 rad 目标的误差上限。
    algebraic_rotation_limit = float(acceptance["slave_algebraic_rotation_error_rad"])  # 读取 solver-only slave 与 master 代数转角一致性上限。
    force_limit = float(acceptance["force_equilibrium_absolute_tolerance_n"])  # 读取全局力平衡绝对容差，单位 N。
    moment_limit = float(acceptance["moment_equilibrium_absolute_tolerance_n_mm"])  # 读取全局矩平衡绝对容差，单位 N·mm。
    all_motion_limit = float(acceptance["all_slave_translation_and_rotation_max_abs"])  # 读取 ALL 从节点六自由度最大允许运动。
    case_results: list[dict[str, Any]] = []  # 初始化十二项数值验收结果。
    raw_manifest_rows: list[dict[str, Any]] = []  # 初始化三十六项输入、OUT 和机器结果哈希清单。
    for plan_case in plan_cases:  # 按 prepare 稳定顺序逐案例复核。
        require(isinstance(plan_case, dict), "prepare 案例不是对象")  # 当前案例必须提供字段字典。
        case_id = str(plan_case["case_id"])  # 读取稳定案例编号。
        family = str(plan_case["case_family"])  # 读取 UXYZ、FINITE 或 ALL 案例族。
        require(case_id in record_by_id, f"执行记录缺少案例 {case_id}")  # 在索引前拒绝漏跑案例。
        record = record_by_id[case_id]  # 读取与当前 CASE-ID 对应的唯一执行记录。
        input_path = Path(str(record["input_file"])).resolve()  # 解析本案例实际使用的冻结 APDL 输入路径。
        output_path = Path(str(record["output_file"])).resolve()  # 解析本案例 MAPDL OUT 路径。
        result_path = Path(str(record["result_file"])).resolve()  # 解析本案例机器结果文本路径。
        require(input_path.is_file(), f"案例 {case_id} 输入文件缺失")  # 实际输入必须仍可读。
        require(output_path.is_file(), f"案例 {case_id} OUT 文件缺失")  # MAPDL 原始日志必须仍可读。
        require(result_path.is_file(), f"案例 {case_id} 机器结果文件缺失")  # 数值向量来源必须仍可读。
        input_hash = sha256_file(input_path)  # 复算当前输入 SHA-256。
        output_hash = sha256_file(output_path)  # 复算当前 OUT SHA-256。
        result_hash = sha256_file(result_path)  # 复算当前机器结果 SHA-256。
        require(input_hash == str(plan_case["input_sha256"]), f"案例 {case_id} 输入哈希不匹配 prepare")  # 实际求解输入必须命中封板计划。
        require(input_hash == str(record["input_sha256"]), f"案例 {case_id} 输入哈希不匹配执行记录")  # finalizer 与 runner 必须读取同一输入。
        require(output_hash == str(record["output_sha256"]), f"案例 {case_id} OUT 哈希不匹配执行记录")  # 原始日志不得在运行后漂移。
        require(result_hash == str(record["result_sha256"]), f"案例 {case_id} 结果哈希不匹配执行记录")  # 机器结果不得在运行后漂移。
        output_text = output_path.read_text(encoding="utf-8", errors="replace")  # 读取 ASCII 为主的 MAPDL OUT，并替换不可解码本地字符。
        result_text = result_path.read_text(encoding="utf-8", errors="strict")  # 严格读取 finalizer 依赖的机器结果文本。
        log_checks = common_log_checks(record, output_text)  # 计算本案例进程、错误、主元、容限和方程数共同门禁。
        metrics: dict[str, Any] = {}  # 初始化当前案例族专用数值指标。
        numeric_checks: dict[str, bool] = {}  # 初始化当前案例族专用通过条件。
        if family == "UXYZ_PRODUCTION_TOPOLOGY_TRANSLATION_LOAD":  # 处理柔性 master、单 TYPE72、预拉双索和仅平移质量的生产同类拓扑。
            master_u = parse_vector(result_text, "MASTER_U")  # 读取 master 平移，单位 mm。
            master_rot = parse_vector(result_text, "MASTER_ROT")  # 读取 master 旋转向量，单位 rad。
            slave_u = parse_vector(result_text, "SLAVE_U")  # 读取原索 slave 平移，单位 mm。
            slave_rot = parse_vector(result_text, "SLAVE_ROT")  # 读取 solver-only slave 代数转角，单位 rad。
            ground_force = parse_vector(result_text, "GROUND_RF_F")  # 读取三个真实支承的合反力，单位 N。
            applied_force, applied_moment = load_vectors(str(plan_case["load_label"]), float(plan_case["load_value"]))  # 构造当前单位平移力和零力矩向量。
            require(max_abs(applied_moment) == 0.0, f"案例 {case_id} 意外包含节点力矩")  # UXYZ slave 源审计禁止任何物理转动力矩消费者。
            expected_slave_u = vector_add(master_u, rodrigues_displacement_vector(master_rot))  # 由 master 实际六自由度计算单 TYPE72 刚体偏心目标位移。
            rigid_translation_error = vector_subtract(slave_u, expected_slave_u)  # 计算原 slave 相对精确刚体映射的位移误差，单位 mm。
            algebraic_rotation_error = vector_subtract(slave_rot, master_rot)  # 计算 solver-only 从节点与 master 的代数转角差，单位 rad。
            force_residual = vector_add(ground_force, applied_force)  # 计算包括双索锚点和梁根部的全局力平衡残差，单位 N。
            metrics = {"master_translation_xyz_mm": list(master_u), "master_rotation_xyz_rad": list(master_rot), "expected_slave_translation_xyz_mm": list(expected_slave_u), "slave_translation_xyz_mm": list(slave_u), "rigid_body_translation_error_xyz_mm": list(rigid_translation_error), "max_rigid_body_translation_error_mm": max_abs(rigid_translation_error), "slave_algebraic_rotation_error_xyz_rad": list(algebraic_rotation_error), "max_slave_algebraic_rotation_error_rad": max_abs(algebraic_rotation_error), "force_residual_xyz_n": list(force_residual), "max_force_residual_n": max_abs(force_residual)}  # 保存单层 UXYZ 刚体映射、代数转角和全局力平衡指标。
            numeric_checks = {"rigid_body_translation_within_limit": max_abs(rigid_translation_error) <= rigid_translation_limit, "slave_algebraic_rotation_within_limit": max_abs(algebraic_rotation_error) <= algebraic_rotation_limit, "force_equilibrium_within_limit": max_abs(force_residual) <= force_limit}  # 应用生产拓扑 UXYZ 三项数值硬门。
        elif family == "UXYZ_SINGLE_MPC_FINITE_ROTATION_KINEMATICS":  # 处理三轴受矩转动弹簧驱动的单 TYPE72 约 0.1 rad 案例。
            master_u = parse_vector(result_text, "MASTER_U")  # 读取 master 平移，单位 mm。
            master_rot = parse_vector(result_text, "MASTER_ROT")  # 读取受矩求解得到的 master 实际转角，单位 rad。
            slave_u = parse_vector(result_text, "SLAVE_U")  # 读取原索 slave 平移，单位 mm。
            slave_rot = parse_vector(result_text, "SLAVE_ROT")  # 读取 solver-only slave 代数转角，单位 rad。
            rotation_label = str(plan_case["rotation_label"])  # 读取当前目标转轴标签。
            target_angle = float(plan_case["rotation_value_rad"])  # 读取当前预注册目标角度，单位 rad。
            target_rotation = tuple(target_angle if label == rotation_label else 0.0 for label in ("ROTX", "ROTY", "ROTZ"))  # 构造目标三分量旋转向量。
            expected_slave_u = vector_add(master_u, rodrigues_displacement_vector(master_rot))  # 使用求解所得实际转角计算精确 Rodrigues 偏心位移。
            rodrigues_error = vector_subtract(slave_u, expected_slave_u)  # 计算 TYPE72 终态相对解析刚体映射的位移误差，单位 mm。
            target_angle_error = vector_subtract(master_rot, target_rotation)  # 计算受矩弹簧终态相对约 0.1 rad 目标的误差。
            algebraic_rotation_error = vector_subtract(slave_rot, master_rot)  # 计算 solver-only slave 与 master 的代数转角差。
            metrics = {"target_rotation_xyz_rad": list(target_rotation), "master_rotation_xyz_rad": list(master_rot), "master_target_rotation_error_xyz_rad": list(target_angle_error), "max_master_target_rotation_error_rad": max_abs(target_angle_error), "expected_slave_translation_xyz_mm": list(expected_slave_u), "slave_translation_xyz_mm": list(slave_u), "rodrigues_displacement_error_xyz_mm": list(rodrigues_error), "max_rodrigues_displacement_error_mm": max_abs(rodrigues_error), "slave_algebraic_rotation_error_xyz_rad": list(algebraic_rotation_error), "max_slave_algebraic_rotation_error_rad": max_abs(algebraic_rotation_error)}  # 保存目标角、实际角、Rodrigues 位移和代数转角一致性指标。
            numeric_checks = {"target_rotation_within_limit": max_abs(target_angle_error) <= target_angle_limit, "rodrigues_displacement_within_limit": max_abs(rodrigues_error) <= rodrigues_limit, "slave_algebraic_rotation_within_limit": max_abs(algebraic_rotation_error) <= algebraic_rotation_limit}  # 应用有限转动三项硬门。
        elif family == "ALL_SIX_AXIS_LOAD_TRANSFER":  # 处理单个 TYPE72 六自由度刚梁案例。
            slave_u = parse_vector(result_text, "SLAVE_U")  # 读取固定 master 约束下 slave 位移，单位 mm。
            slave_rot = parse_vector(result_text, "SLAVE_ROT")  # 读取固定 master 约束下 slave 转角，单位 rad。
            master_force = parse_vector(result_text, "MASTER_RF_F")  # 读取 master 反力，单位 N。
            master_moment = parse_vector(result_text, "MASTER_RF_M")  # 读取 master 反力矩，单位 N·mm。
            ground_force = parse_vector(result_text, "GROUND_RF_F")  # 读取可变形支撑梁地基反力，单位 N。
            ground_moment = parse_vector(result_text, "GROUND_RF_M")  # 读取可变形支撑梁地基反力矩，单位 N·mm。
            applied_force, applied_moment = load_vectors(str(plan_case["load_label"]), float(plan_case["load_value"]))  # 构造当前外力和外力矩向量。
            force_residual = vector_add(master_force, ground_force, applied_force)  # 计算包含支撑梁地基的全局力平衡残差，单位 N。
            moment_residual = vector_add(master_moment, ground_moment, applied_moment, vector_cross(OFFSET_VECTOR_MM, applied_force), vector_cross((800.0, 400.0, 500.0), ground_force))  # 计算关于 master 的完整全局矩平衡残差，单位 N·mm。
            maximum_motion = max(max_abs(slave_u), max_abs(slave_rot))  # 计算 ALL 从节点六自由度最大绝对运动。
            metrics = {"slave_translation_xyz_mm": list(slave_u), "slave_rotation_xyz_rad": list(slave_rot), "max_slave_six_dof_motion": maximum_motion, "force_residual_xyz_n": list(force_residual), "max_force_residual_n": max_abs(force_residual), "moment_residual_xyz_n_mm": list(moment_residual), "max_moment_residual_n_mm": max_abs(moment_residual)}  # 保存 ALL 零运动和完整全局平衡指标。
            numeric_checks = {"all_slave_six_dof_within_limit": maximum_motion <= all_motion_limit, "force_equilibrium_within_limit": max_abs(force_residual) <= force_limit, "moment_equilibrium_within_limit": max_abs(moment_residual) <= moment_limit}  # 应用 ALL 三项硬门禁。
        else:  # 任何计划外案例族都无法应用冻结验收公式。
            raise RuntimeError(f"不支持的案例族：{family}")  # 拒绝遗漏或拼写漂移的案例。
        numeric_checks["passed"] = all(numeric_checks.values())  # 当前案例数值结论要求所有专用门禁通过。
        passed = bool(log_checks["passed"] and numeric_checks["passed"])  # 案例总通过要求日志和数值同时通过。
        warning_disposition = "ACCEPTED_MICRO_FIXTURE_STIFFNESS_CONTRAST_NUMERICAL_AND_PIVOT_GATES_PASSED" if record.get("coefficient_ratio_warning") and passed else "NO_COEFFICIENT_RATIO_WARNING_OR_CASE_NOT_ACCEPTED"  # 仅在所有硬门均通过时把条件比警告限定为微模型刚度对比现象。
        case_results.append({"case_id": case_id, "case_family": family, "status": "PASSED" if passed else "FAILED", "warning_count": record.get("warning_count"), "coefficient_ratio_warning": bool(record.get("coefficient_ratio_warning")), "warning_disposition": warning_disposition, "equation_counts": record.get("equation_counts"), "unique_equation_counts": record.get("unique_equation_counts"), "log_checks": log_checks, "numeric_checks": numeric_checks, "metrics": metrics, "input_sha256": input_hash, "output_sha256": output_hash, "result_sha256": result_hash})  # 保存当前案例完整证据和结论。
        raw_manifest_rows.extend([{"case_id": case_id, "role": "FROZEN_INPUT", "path": str(input_path), "sha256": input_hash}, {"case_id": case_id, "role": "MAPDL_OUT", "path": str(output_path), "sha256": output_hash}, {"case_id": case_id, "role": "MACHINE_RESULT", "path": str(result_path), "sha256": result_hash}])  # 保存三项原始工件哈希行。
    passed_count = sum(item["status"] == "PASSED" for item in case_results)  # 统计十二项通过数量。
    failed_count = EXPECTED_CASE_COUNT - passed_count  # 由总数减通过数得到失败数量。
    overall_status = "MICRO_VALIDATION_PASSED_FULL_BRIDGE_NOT_RUN" if failed_count == 0 else "MICRO_VALIDATION_FAILED"  # 形成不越权到全桥的总状态。
    summary = {"schema_version": 3, "status": overall_status, "prepare_run": prepare_name, "execution_run": execution_name, "planned_case_count": EXPECTED_CASE_COUNT, "completed_case_count": EXPECTED_CASE_COUNT, "passed_case_count": passed_count, "failed_case_count": failed_count, "mapdl_execution_attempted": True, "mapdl_started": True, "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None, "full_bridge_static_status": "NOT_RUN", "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "thresholds": acceptance, "cases": case_results, "next_action": "FULL_BRIDGE_STATIC_DIAGNOSTIC_WITH_CONSTANT_EQUATION_COUNT_GATE" if failed_count == 0 else "FIX_FAILED_MICRO_CASES_BEFORE_ANY_FULL_BRIDGE_RUN"}  # 汇总十二项结果并明确全桥与生产边界。
    raw_manifest = {"schema_version": 2, "prepare_run": prepare_name, "execution_run": execution_name, "file_count": len(raw_manifest_rows), "files": raw_manifest_rows}  # 汇总三十六项输入、OUT 和机器结果哈希。
    raw_manifest_path = execution_dir / "raw_result_manifest.json"  # 定位原始工件清单输出路径。
    summary_path = execution_dir / "unit_test_results.json"  # 定位微算例数值验收输出路径。
    write_new_json(raw_manifest_path, raw_manifest)  # 先写原始工件清单供摘要引用。
    write_new_json(summary_path, summary)  # 写完整十二案例数值验收结果。
    maximum_rigid_error = max(float(item["metrics"].get("max_rigid_body_translation_error_mm", 0.0)) for item in case_results)  # 汇总三个生产拓扑 UXYZ 的最大刚体平移误差。
    maximum_rodrigues_error = max(float(item["metrics"].get("max_rodrigues_displacement_error_mm", 0.0)) for item in case_results)  # 汇总三轴受矩有限转动的最大 Rodrigues 位移误差。
    maximum_rotation_error = max(float(item["metrics"].get("max_slave_algebraic_rotation_error_rad", 0.0)) for item in case_results)  # 汇总 UXYZ 和有限转动的最大代数转角差。
    maximum_force_residual = max(float(item["metrics"].get("max_force_residual_n", 0.0)) for item in case_results)  # 汇总所有提供反力向量案例的最大力残差。
    maximum_moment_residual = max(float(item["metrics"].get("max_moment_residual_n_mm", 0.0)) for item in case_results)  # 汇总 ALL 六向案例的最大矩残差。
    packet_lines = ["# C10 单层 TYPE72 微算例验收", "", f"状态：`{overall_status}`。", "", f"- prepare：`{prepare_name}`", f"- execution：`{execution_name}`", f"- 真实运行：{EXPECTED_CASE_COUNT}/{EXPECTED_CASE_COUNT}；通过：{passed_count}；失败：{failed_count}。", "- 生产候选与 UXYZ 微测均为一条 TYPE72；辅助节点=0、TYPE73=0、罚刚度参数=`null`。", "- 三个受矩有限转动案例各有 1 个独立方程；三个生产拓扑 UXYZ 各有 18 个；六个 ALL 各有 12 个，案例内均恒定。", "- 本工件只关闭单连接运动学、装配秩警戒和六向传力门禁；全桥静力、初始状态路径和模态仍为 `NOT_RUN`。", "", "## 数值控制值", "", f"- 最大生产拓扑刚体平移误差：{maximum_rigid_error:.6e} mm。", f"- 最大有限转动 Rodrigues 位移误差：{maximum_rodrigues_error:.6e} mm。", f"- 最大 solver-only 代数转角差：{maximum_rotation_error:.6e} rad。", f"- 最大全局力平衡残差：{maximum_force_residual:.6e} N。", f"- 最大全局矩平衡残差：{maximum_moment_residual:.6e} N·mm。", "", "原始工件哈希见 `raw_result_manifest.json`，逐案例门禁见 `unit_test_results.json`。", ""]  # 初始化人读结果包并避免宣称全桥完成。
    packet_path = execution_dir / "result_packet.md"  # 定位人读结果包输出路径。
    write_new_text(packet_path, "\n".join(packet_lines))  # 写不可覆盖的人读验收说明。
    ledger_sources = [record_path, raw_manifest_path, summary_path, packet_path, SCRIPT_PATH, plan_path]  # 定义最终发布账本覆盖的核心六项工件。
    ledger_text = "\n".join(f"{sha256_file(path)} *{path}" for path in ledger_sources) + "\n"  # 生成固定 LF 的 SHA-256 账本。
    write_new_text(execution_dir / "artifact_hashes.sha256", ledger_text)  # 最后写发布账本，之后不再修改核心验收工件。
    return summary_path  # 返回已生成微算例验收 JSON 路径。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回两个必需运行名参数。
    """命令行不提供执行开关，因此本脚本结构上无法启动 MAPDL。"""  # 返回 argparse 命名空间。
    parser = argparse.ArgumentParser(description="Finalize C10 direct-elimination micro validation without starting MAPDL.")  # 创建只读数值复核接口。
    parser.add_argument("--prepare-run", required=True, help="C10_MPC_ONLY prepare run name used by the micro execution.")  # 指定封板输入包运行名。
    parser.add_argument("--execution-run", required=True, help="C10_MICRO_VALIDATION execution run name containing raw outputs.")  # 指定含原始结果的执行子运行名。
    return parser.parse_args()  # 解析并返回命令行参数。


def main() -> None:  # 无输入和返回值；执行验收并向标准输出写机器摘要。
    """唯一入口只读取既有结果并生成验收工件。"""  # 异常时 Python 返回非零退出码。
    arguments = parse_arguments()  # 读取两个受控运行名。
    summary_path = finalize(str(arguments.prepare_run), str(arguments.execution_run))  # 执行全部哈希、日志和数值门禁。
    summary = read_json(summary_path)  # 重新读取落盘摘要以确认输出可解析。
    print(json.dumps({"summary_path": str(summary_path), "status": summary["status"], "passed_case_count": summary["passed_case_count"], "failed_case_count": summary["failed_case_count"]}, ensure_ascii=False))  # 输出单行机器摘要供调用者确认。


if __name__ == "__main__":  # 仅直接执行本文件时进入程序入口。
    main()  # 调用只读 finalizer 主函数。
