"""从最终已执行 S10 边界生成仅替换连接运动学的 C10 prepare-only 工件包，且绝不启动 MAPDL。"""  # 模块用途、输出边界和禁止执行行为均在此固定。

from __future__ import annotations  # 延迟解析类型注解，兼容项目当前 Python 运行时。

import argparse  # 解析父运行名和目标运行名两个受控参数。
import csv  # 读取冻结连接元数据并生成机器可读映射审计表。
import hashlib  # 计算父输入、候选输入和全部发布工件的 SHA-256。
import io  # 在内存中生成固定 LF 的 CSV，避免平台换行漂移。
import json  # 读取父状态并生成全部机器可读 JSON 审计工件。
import math  # 校验节点坐标和单位测试数值均为有限数。
import re  # 严格解析 APDL 节点、单元、CERIG 和运行身份。
import shutil  # 逐字节复制最终 S10 的十项不变量输入和谱系证据。
from datetime import datetime, timezone  # 从运行名恢复 UTC 创建时间并写入清单。
from pathlib import Path  # 以绝对路径安全管理项目、父运行和新运行目录。
from typing import Any  # 描述 JSON、CSV 和异构 APDL 审计记录。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前生成器绝对路径，供源码哈希和快照使用。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 目录是生成器源码的唯一所属目录。
PROJECT_DIR = TOOLS_DIR.parent  # 项目根目录包含 builder、ultra_runs 和 ultra_tools。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 所有 C10 工件包只能创建在统一运行目录下。
DEFAULT_PARENT_RUN = "S10_SECTION_SHEAR_20260716T050342389124Z"  # 固定最终已执行且要求重建 C10 的 S10 父边界。
DEFAULT_RUN_NAME = "C10_MPC_ONLY_20260801T103247657937Z"  # 复用本轮先前只创建空目录但未生成任何候选文件的安全运行身份。
PARENT_INCLUDE_NAME = "apply_finite_gates_and_passages_v2.inp"  # 唯一允许发生物理连接变化的依赖文件。
PARENT_MAIN_NAME = "s10_section_shear_main.inp"  # 最终 S10 的静力—保持—80阶模态主控输入。
CANDIDATE_MAIN_NAME = "c10_mpc_only_main.inp"  # C10 候选的唯一主控输入文件名。
CONSTRAINT_METADATA_PATH = PROJECT_DIR / "builder" / "generated" / "generated_constraints.csv"  # 冻结 5078 条逻辑连接的 system、assembly 和 reason 元数据。
BUILDER_SCRIPT_PATH = PROJECT_DIR / "builder" / "build_finite_gate_passage_apdl.py"  # 仅作 MPC184 语法来源，不允许直接重生最终 S10 物理模型。
MISSING_BUILDER_SOURCE_PATH = PROJECT_DIR.parent.parent / "output" / "freecad" / "cross_passage_local_coordinates" / "tail_nodes.csv"  # 记录旧重生路径缺失的 FreeCAD 尾节点源文件。
EXPECTED_PARENT_INCLUDE_SHA256 = "72012ebbd107cf377c2178561b9008606aeb894c4f7879110d13c30d2a417330"  # 最终 S10 受控 include 的不可变父哈希。
EXPECTED_LOGICAL_CONNECTIONS = 5078  # 原 CERIG 逻辑连接总数，单位为条。
EXPECTED_UXYZ_CONNECTIONS = 3124  # 只传递三向平动且释放相对转动的逻辑连接数。
EXPECTED_ALL_CONNECTIONS = 1954  # 传递六自由度的逻辑刚接数。
EXPECTED_MPC_ELEMENTS = 5078  # 每条原 CERIG 只映射为一个 TYPE72，避免直接消元 MPC 串联造成依赖秩亏。
EXPECTED_PARENT_NODES = 109086  # 已执行 S10 的全模型节点总数。
EXPECTED_CANDIDATE_NODES = 109086  # 单 TYPE72 方案不再增加辅助节点，因此节点总数必须与最终 S10 完全相同。
EXPECTED_PARENT_ELEMENTS = 172994  # 已执行 S10 的全模型单元总数。
EXPECTED_CANDIDATE_ELEMENTS = 178072  # 最终 S10 的 172994 个单元加 5078 个 TYPE72 得到候选总数。
EXPECTED_PHYSICAL_FINITE_NODES = 29626  # 门架和横通道 include 内原有物理及方向节点总数。
EXPECTED_PHYSICAL_BEAMS = 17679  # 门架和横通道 include 内必须逐字节保持的 BEAM188 数量。
EXPECTED_CP_COMMANDS = 12  # 最终 S10 十一项依赖中原有 CP 命令条数。
EXPECTED_D_COMMANDS = 3968  # 最终 S10 十一项依赖中原有 D 命令条数。
MPC_ELEMENT_START = 2017680  # 新 MPC184 起号，紧接最终 S10 有限物理梁最大单元 2017679。
MPC_ELEMENT_END = 2022757  # 5078 个连续 MPC184 的封板末号，计算式为 2017680+5078-1。
RIGID_TYPE_ID = 72  # MPC184 rigid-beam 的空闲 TYPE 编号；ALL 全量使用，UXYZ 只投影到纯平移索节点的有效自由度。
TRANSLATION_LINK_TYPE_ID = 73  # 仅供两个未调用的旧串联链回归输入生成函数复现失败；正式候选和新微测的 TYPE73 门禁值恒为零。
UNIT_LOAD_CASES = (("FX", "FX", 1.0, "N"), ("FY", "FY", 1.0, "N"), ("FZ", "FZ", 1.0, "N"), ("MX", "MX", 1.0, "N_mm"), ("MY", "MY", 1.0, "N_mm"), ("MZ", "MZ", 1.0, "N_mm"))  # 六个单位力或单位力矩工况及其量纲。
TRANSLATION_LOAD_CASES = UNIT_LOAD_CASES[:3]  # UXYZ 生产从节点没有物理转角消费者，因此只允许三项平移力微测，禁止虚构节点力矩工况。
FINITE_ROTATION_CASES = (("RX", "ROTX", 0.1), ("RY", "ROTY", 0.1), ("RZ", "ROTZ", 0.1))  # 三个 0.1 rad 规定有限转角工况覆盖全局三轴刚体运动学。
EXPECTED_MICRO_CASES = 12  # 三个生产拓扑平移载荷、三个有限转动和六个 ALL 载荷共同组成数值门禁。
DEPENDENCY_NAMES = ("full_line_beam4_crossbeam_mesh_xlong.inp", "convert_crossbeams_beam4_to_beam188.inp", "apply_mct_downpull_equivalent_xlong.inp", "apply_mct_constraints_xlong.inp", "apply_mct_authoritative_initial_state_link180.inp", PARENT_INCLUDE_NAME, "apply_modal_roty_stabilization_xlong.inp", "define_representative_rope_component.inp", "apply_authoritative_mct_deadload_v1.inp", "apply_dynamic_mass21_spatialized_v2.inp", "apply_authoritative_mct_gravity_v1.inp")  # 与最终 S10 主输入完全一致的十一项有序依赖。
INVARIANT_DEPENDENCY_NAMES = tuple(name for name in DEPENDENCY_NAMES if name != PARENT_INCLUDE_NAME)  # 除受控连接 include 外必须逐字节保持的十项依赖。
RUN_NAME_PATTERN = re.compile(r"C10_MPC_ONLY_(\d{8})T(\d{12})Z\Z", re.ASCII)  # 只接受 UTC 微秒格式且无路径字符的 C10 运行名。
CERIG_PATTERN = re.compile(r"^\s*CERIG\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(ALL|UXYZ)\s*(?:!.*)?$", re.IGNORECASE)  # 严格识别三字段 CERIG 命令并允许行尾注释。
INTEGER_PATTERN = re.compile(r"^[+-]?\d+$", re.ASCII)  # 仅把纯十进制整数字段当作 APDL 实体编号。
DEFINITION_BEGIN = "! C10_MPC184_DEFINITIONS_BEGIN"  # 可逆 MPC184 类型、截面和局部坐标定义块起标记。
DEFINITION_END = "! C10_MPC184_DEFINITIONS_END"  # 可逆定义块结束标记。
CONNECTION_BEGIN = "! C10_CONNECTION_REPLACEMENT_BEGIN"  # 可逆辅助节点和 MPC184 元素替换块起标记。
CONNECTION_END = "! C10_CONNECTION_REPLACEMENT_END"  # 可逆连接替换块结束标记。
COMPONENT_BEGIN = "! C10_MPC184_COMPONENT_BEGIN"  # 可逆 MPC184 审计组件块起标记。
COMPONENT_END = "! C10_MPC184_COMPONENT_END"  # 可逆 MPC184 审计组件块结束标记。
MAIN_QUERY_BEGIN = "! C10_MPC_TYPE_COUNT_QUERY_BEGIN"  # 主控新增 TYPE72 查询块起标记。
MAIN_QUERY_END = "! C10_MPC_TYPE_COUNT_QUERY_END"  # 主控新增查询块结束标记。
MAIN_OUTPUT_BEGIN = "! C10_MPC_TYPE_COUNT_OUTPUT_BEGIN"  # 主控新增类型计数输出块起标记。
MAIN_OUTPUT_END = "! C10_MPC_TYPE_COUNT_OUTPUT_END"  # 主控新增输出块结束标记。
MAIN_AUDIT_BEGIN = "! C10_MPC_ELEMENT_AUDIT_BEGIN"  # 主控新增 MPC184 元素列表审计块起标记。
MAIN_AUDIT_END = "! C10_MPC_ELEMENT_AUDIT_END"  # 主控新增元素审计块结束标记。
MAIN_GATE_BEGIN = "! C10_MPC_TYPE_COUNT_GATE_BEGIN"  # 主控新增 TYPE72 fail-closed 门禁块起标记。
MAIN_GATE_END = "! C10_MPC_TYPE_COUNT_GATE_END"  # 主控新增门禁块结束标记。


def require(condition: bool, message: str) -> None:  # 输入布尔条件和失败说明；无返回值，条件为假时立即拒绝。
    """统一实现源证、编号、文本和输出的 fail-closed 门禁。"""  # 函数只在失败时抛出 RuntimeError。
    if not condition:  # 只有门禁条件不成立时进入拒绝路径。
        raise RuntimeError(message)  # 抛出可定位原因并阻止生成误导性 C10 包。


def sha256_bytes(value: bytes) -> str:  # 输入任意字节并返回 64 位小写十六进制 SHA-256。
    """用于内存候选、规范化回退和落盘前身份计算。"""  # 返回值无单位且不可用作加密认证。
    return hashlib.sha256(value).hexdigest()  # 一次性计算本项目最大约 6 MB 输入的摘要。


def sha256_file(path: Path) -> str:  # 输入普通文件路径并返回其逐字节 SHA-256。
    """以 1 MiB 分块读取，避免把所有结果文件一次装入内存。"""  # 文件缺失时由 open 抛出异常。
    digest = hashlib.sha256()  # 创建空 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读模式打开，禁止换行或编码转换。
        while True:  # 持续读取直到遇到空字节块。
            chunk = stream.read(1024 * 1024)  # 每次读取 1 MiB，数值来源为常用哈希分块大小。
            if not chunk:  # 空块表示已到文件末尾。
                break  # 结束分块读取循环。
            digest.update(chunk)  # 把当前原始字节块纳入摘要。
    return digest.hexdigest()  # 返回全部字节闭合后的十六进制摘要。


def decode_utf8(path: Path) -> str:  # 输入 APDL、CSV 或 JSON 文本路径并返回 Unicode 文本。
    """允许 UTF-8 BOM，但不做换行归一化。"""  # 返回字符串保留原 CRLF 或 LF。
    raw = path.read_bytes()  # 二进制读取以保留源文件全部换行字节。
    if raw.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM 存在时只移除编码标记。
        raw = raw[3:]  # 去掉三个 BOM 字节，正文和换行保持不变。
    return raw.decode("utf-8")  # 严格按 UTF-8 解码，非法字节直接拒绝。


def write_new_bytes(path: Path, value: bytes) -> None:  # 输入新路径和完整字节；目标存在时拒绝且无返回值。
    """所有正式工件采用不可覆盖写入，保护先前运行证据。"""  # 仅在当前新运行目录内创建父目录。
    require(not path.exists(), f"拒绝覆盖既有文件：{path}")  # 同名工件一旦存在即停止。
    path.parent.mkdir(parents=True, exist_ok=True)  # 创建必要的运行包子目录。
    with path.open("xb") as stream:  # x 模式提供操作系统级不可覆盖保证。
        stream.write(value)  # 一次写出已在内存验证的完整字节。


def write_new_text(path: Path, value: str) -> None:  # 输入新路径和 Unicode 文本；以 UTF-8/LF 原样写入。
    """适用于新生成工件；需要保留父换行时应调用 write_new_bytes。"""  # 无返回值。
    write_new_bytes(path, value.encode("utf-8"))  # UTF-8 编码后复用不可覆盖写入。


def write_new_json(path: Path, value: dict[str, Any]) -> None:  # 输入 JSON 对象并写两空格缩进的合法 UTF-8 文件。
    """JSON 语法不支持注释，字段说明统一写入 qa/field_dictionary.md。"""  # 无返回值。
    write_new_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")  # 保留中文并添加唯一末尾换行。


def copy_new_verified(source: Path, destination: Path) -> str:  # 输入源和新目标；返回两者一致的 SHA-256。
    """逐字节复制并复算目标，任何缺失、覆盖或哈希差异均拒绝。"""  # 返回值用于输入哈希审计。
    require(source.is_file(), f"缺少待复制源文件：{source}")  # 源必须是现存普通文件。
    require(not destination.exists(), f"拒绝覆盖复制目标：{destination}")  # 目标必须尚不存在。
    destination.parent.mkdir(parents=True, exist_ok=True)  # 创建目标父目录。
    source_hash = sha256_file(source)  # 复制前计算源文件身份。
    shutil.copyfile(source, destination)  # 只复制内容，避免时间戳影响证据理解。
    require(sha256_file(destination) == source_hash, f"复制后哈希不闭合：{source.name}")  # 从磁盘复算目标确认无损。
    return source_hash  # 返回已闭合的源/目标共同摘要。


def rows_to_csv(rows: list[dict[str, Any]]) -> str:  # 输入同构字典行并返回固定 LF 的合法 CSV 文本。
    """字段顺序取首行；CSV 不支持注释，语义由字段字典说明。"""  # 返回非空 CSV 字符串。
    require(bool(rows), "拒绝生成空 CSV")  # 所有正式表格至少包含一条数据记录。
    buffer = io.StringIO(newline="")  # 创建不执行平台换行替换的内存缓冲区。
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), lineterminator="\n")  # 固定表头顺序和 LF 行尾。
    writer.writeheader()  # 写唯一表头行。
    writer.writerows(rows)  # 按输入稳定顺序写全部数据行。
    return buffer.getvalue()  # 返回完整 CSV 文本供不可覆盖落盘。


def parse_run_created_at(run_name: str) -> tuple[datetime, str]:  # 输入安全运行名并返回 UTC 时间和不超过 32 字符的 MAPDL jobname。
    """运行名必须含 YYYYMMDD、HHMMSS 和六位微秒。"""  # 返回时间有 UTC 时区。
    match = RUN_NAME_PATTERN.fullmatch(run_name)  # 严格验证前缀、数字长度和结尾。
    require(match is not None, "run-name 必须匹配 C10_MPC_ONLY_YYYYMMDDTHHMMSSffffffZ")  # 非法路径或格式立即拒绝。
    date_part = str(match.group(1))  # 提取八位年月日字符串。
    time_part = str(match.group(2))  # 提取十二位时分秒和微秒字符串。
    created_at = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S%f").replace(tzinfo=timezone.utc)  # 严格解析为 UTC 时间。
    jobname = f"cw_C10_{date_part[4:]}t{time_part[:6]}_c1"  # 使用月日和时分秒形成唯一 ASCII 作业名。
    require(len(jobname) <= 32 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", jobname) is not None, "派生 MAPDL jobname 非法")  # MAPDL 标识符长度和字符集门禁。
    return created_at, jobname  # 返回清单时间和未来求解作业名。


def validate_parent(parent_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:  # 输入父运行目录并返回快照目录、状态对象和清单对象。
    """固定父运行必须是最终已执行 S10，且明确要求下一步从其边界重建 C10。"""  # 任一身份漂移均拒绝。
    snapshot_dir = parent_dir / "input_snapshot"  # 最终求解实际输入快照是唯一派生源。
    status_path = parent_dir / "S10_status.json"  # 读取后处理封板状态而非早期准备状态。
    manifest_path = parent_dir / "manifest.json"  # 读取最终运行清单和有序依赖。
    require(snapshot_dir.is_dir(), f"缺少 S10 input_snapshot：{snapshot_dir}")  # 输入快照目录必须存在。
    require(status_path.is_file() and manifest_path.is_file(), "缺少 S10 状态或清单")  # 两份父级机器证据都必须存在。
    status = json.loads(decode_utf8(status_path))  # 解析允许中文的最终 S10 状态 JSON。
    manifest = json.loads(decode_utf8(manifest_path))  # 解析最终 S10 清单 JSON。
    require(isinstance(status, dict) and isinstance(manifest, dict), "S10 JSON 顶层不是对象")  # 顶层结构必须为具名字段对象。
    require(status.get("run_name") == parent_dir.name, "S10 状态中的运行身份不等于目录名")  # 防止错目录或复制状态混入。
    require(status.get("execution_status") == "EXECUTED" and status.get("postrun_gate_passed") is True, "父 S10 未完成执行后门禁")  # 只允许从已执行父边界派生。
    require(status.get("pipeline_next_action") == "REBUILD_C10_FROM_FINAL_S10_BOUNDARY", "父 S10 未授权进入 C10 重建节点")  # 固定流程下一步。
    require(status.get("valid_for_production_model") is False, "父 S10 生产有效性字段异常")  # 保留 legacy 限制边界，禁止误称生产封板。
    require(manifest.get("run_name") == parent_dir.name, "S10 manifest 运行身份不等于目录名")  # 清单身份必须闭合。
    for name in DEPENDENCY_NAMES:  # 按固定有序依赖逐项检查源文件存在。
        require((snapshot_dir / name).is_file(), f"S10 快照缺少依赖：{name}")  # 任一缺失即无法形成完整候选。
    require((snapshot_dir / PARENT_MAIN_NAME).is_file(), f"S10 快照缺少主输入：{PARENT_MAIN_NAME}")  # 主控文件必须存在。
    parent_include_hash = sha256_file(snapshot_dir / PARENT_INCLUDE_NAME)  # 复算唯一受控 include 的父哈希。
    require(parent_include_hash == EXPECTED_PARENT_INCLUDE_SHA256, f"最终 S10 include 哈希漂移：{parent_include_hash}")  # 必须精确命中封板哈希。
    return snapshot_dir, status, manifest  # 返回已验证的父输入根和两份谱系对象。


def parse_nodes(paths: tuple[Path, ...]) -> dict[int, dict[str, Any]]:  # 输入十一项有序 APDL 路径并返回每个唯一节点的原始坐标字符串和来源。
    """只接受显式 N,id,x,y,z 数值定义；重复编号必须给出数值相同坐标。"""  # 返回键为整数节点号。
    nodes: dict[int, dict[str, Any]] = {}  # 初始化全模型节点证据映射。
    for path in paths:  # 按最终 S10 /INPUT 顺序扫描全部依赖。
        for line_number, raw_line in enumerate(decode_utf8(path).splitlines(), start=1):  # 保留一基行号供 sourceRef 使用。
            command = raw_line.split("!", 1)[0].strip()  # 仅移除 APDL 行尾注释和外围空白。
            if not command.upper().startswith("N,"):  # 非显式节点命令不参与节点表。
                continue  # 扫描下一行。
            fields = [field.strip() for field in command.split(",")]  # 拆出命令、节点号和三坐标字段。
            require(len(fields) >= 5 and INTEGER_PATTERN.fullmatch(fields[1]) is not None, f"节点命令格式异常：{path.name}:{line_number}")  # 节点号和坐标字段必须完整。
            node_id = int(fields[1])  # 解析十进制节点编号。
            xyz_raw = (fields[2], fields[3], fields[4])  # 原样保留三个坐标字符串，生成辅助节点时不重格式化。
            xyz = tuple(float(value) for value in xyz_raw)  # 转成浮点仅用于有限性和共点数值审计。
            require(all(math.isfinite(value) for value in xyz), f"节点坐标含 NaN 或无穷：{path.name}:{line_number}")  # 坐标必须是有限 mm 数值。
            if node_id in nodes:  # 重复定义需要确认没有坐标漂移。
                require(tuple(nodes[node_id]["xyz"]) == xyz, f"节点 {node_id} 出现冲突坐标定义")  # 数值不同即拒绝。
                continue  # 数值相同的重复定义不覆盖首个来源。
            nodes[node_id] = {"xyz_raw": xyz_raw, "xyz": xyz, "source_file": path.name, "source_line": line_number}  # 保存坐标、原字符串和首个来源定位。
    require(len(nodes) == EXPECTED_PARENT_NODES, f"S10 显式唯一节点数为 {len(nodes)}，预期 {EXPECTED_PARENT_NODES}")  # 与已执行拓扑计数闭合。
    return nodes  # 返回完整节点表供连接引用和辅助节点生成。


def parse_command_counts(paths: tuple[Path, ...]) -> dict[str, int]:  # 输入十一项依赖并返回 CP、D、CERIG、N、EN、E 命令行计数。
    """计数只针对去除注释后的首命令关键字。"""  # 返回值用于边界和拓扑静态审计。
    counts = {"CP": 0, "D": 0, "CERIG": 0, "N": 0, "EN": 0, "E": 0}  # 初始化六类命令计数器。
    for path in paths:  # 扫描每一项最终 S10 依赖。
        for raw_line in decode_utf8(path).splitlines():  # 逐行读取且不需要保存行号。
            command = raw_line.split("!", 1)[0].strip()  # 排除纯注释和行尾说明。
            if not command:  # 空命令不计数。
                continue  # 跳到下一行。
            keyword = command.split(",", 1)[0].upper()  # 取首个逗号前 APDL 命令名。
            if keyword in counts:  # 仅累加六类关注命令。
                counts[keyword] += 1  # 当前命令计数增加一条。
    require(counts["CP"] == EXPECTED_CP_COMMANDS, f"CP 命令数漂移：{counts['CP']}")  # CP 必须保持 12 条。
    require(counts["D"] == EXPECTED_D_COMMANDS, f"D 命令数漂移：{counts['D']}")  # D 必须保持 3968 条。
    require(counts["CERIG"] == EXPECTED_LOGICAL_CONNECTIONS, f"CERIG 命令数漂移：{counts['CERIG']}")  # 父连接必须恰为 5078 条。
    return counts  # 返回已通过核心门禁的源命令计数。


def parse_existing_element_ids(paths: tuple[Path, ...]) -> set[int]:  # 输入十一项依赖并返回所有显式 EN 指定的元素编号集合。
    """用于证明 2017680..2022757 在最终 S10 输入中没有编号碰撞。"""  # 自动 E 编号由已执行拓扑及 NUMSTR 顺序另行约束。
    element_ids: set[int] = set()  # 初始化显式元素编号集合。
    for path in paths:  # 扫描全部最终 S10 依赖。
        for line_number, raw_line in enumerate(decode_utf8(path).splitlines(), start=1):  # 保留行号用于错误定位。
            command = raw_line.split("!", 1)[0].strip()  # 去除注释后解析命令。
            if not command.upper().startswith("EN,"):  # 自动 E 命令不含显式元素号。
                continue  # 跳过非 EN 行。
            fields = [field.strip() for field in command.split(",")]  # 拆出元素号和节点号。
            require(len(fields) >= 3 and INTEGER_PATTERN.fullmatch(fields[1]) is not None, f"EN 命令格式异常：{path.name}:{line_number}")  # 元素号必须为整数。
            element_id = int(fields[1])  # 解析显式元素编号。
            require(element_id not in element_ids, f"最终 S10 出现重复显式元素号：{element_id}")  # 重复显式编号会覆盖模型，必须拒绝。
            element_ids.add(element_id)  # 记录当前元素号。
    proposed_ids = set(range(MPC_ELEMENT_START, MPC_ELEMENT_END + 1))  # 构造 5078 个候选 MPC184 连续编号。
    require(not (element_ids & proposed_ids), "MPC184 候选元素区间与最终 S10 显式元素号碰撞")  # 空闲区间必须完全无交集。
    return element_ids  # 返回源显式元素号集合供统计。


def parse_cerig(source_text: str) -> tuple[list[dict[str, Any]], int, int, list[str]]:  # 输入父 include 文本并返回 5078 条连接、首末行索引和保留换行的源行列表。
    """CERIG 必须形成唯一连续块，且只允许 ALL 或 UXYZ 两类语义。"""  # 行索引为零基，source_line 为一基。
    lines = source_text.splitlines(keepends=True)  # 保留每行原始 CRLF 供逐字节回退。
    records: list[dict[str, Any]] = []  # 初始化逻辑连接记录表。
    indices: list[int] = []  # 保存所有 CERIG 的零基行索引。
    for index, raw_line in enumerate(lines):  # 按父 include 原始顺序扫描。
        match = CERIG_PATTERN.fullmatch(raw_line.rstrip("\r\n"))  # 在保留正文空白的情况下识别 CERIG。
        if match is None:  # 非 CERIG 行保持不变。
            continue  # 扫描下一行。
        indices.append(index)  # 保存当前 CERIG 行位置。
        records.append({"source_line": index + 1, "original_command": raw_line.rstrip("\r\n"), "master_node": int(match.group(1)), "slave_node": int(match.group(2)), "dof_label": match.group(3).upper()})  # 保存原文、节点和自由度语义。
    require(len(records) == EXPECTED_LOGICAL_CONNECTIONS, f"父 include CERIG 数为 {len(records)}，预期 {EXPECTED_LOGICAL_CONNECTIONS}")  # 总数门禁。
    require(indices == list(range(indices[0], indices[0] + len(indices))), "父 include 的 CERIG 不是唯一连续块")  # 连接块必须可安全原位替换。
    dof_counts = {label: sum(1 for record in records if record["dof_label"] == label) for label in ("UXYZ", "ALL")}  # 统计两类来源语义。
    require(dof_counts == {"UXYZ": EXPECTED_UXYZ_CONNECTIONS, "ALL": EXPECTED_ALL_CONNECTIONS}, f"CERIG 语义计数漂移：{dof_counts}")  # 3124/1954 必须闭合。
    require(all(record["master_node"] != record["slave_node"] for record in records), "父 CERIG 存在 master=slave 自连接")  # 拒绝无意义或奇异连接。
    directed_keys = {(record["master_node"], record["slave_node"], record["dof_label"]) for record in records}  # 构造有向语义键。
    require(len(directed_keys) == len(records), "父 CERIG 存在重复有向语义连接")  # 一条逻辑关系只允许出现一次。
    return records, indices[0], indices[-1], lines  # 返回记录、块边界和原始行列表。


def merge_constraint_metadata(records: list[dict[str, Any]]) -> list[dict[str, Any]]:  # 输入父 CERIG 记录并返回补齐六字段元数据的稳定连接表。
    """CSV 与父 CERIG 必须按顺序逐项 master/slave/DOF 完全相同。"""  # 返回记录新增 system、assembly_name 和 reason。
    require(CONSTRAINT_METADATA_PATH.is_file(), f"缺少冻结连接元数据：{CONSTRAINT_METADATA_PATH}")  # 元数据表必须存在。
    with CONSTRAINT_METADATA_PATH.open("r", encoding="utf-8-sig", newline="") as stream:  # 以 UTF-8 只读方式解析 CSV。
        metadata_rows = list(csv.DictReader(stream))  # 读取表头驱动的全部 5078 行。
    require(len(metadata_rows) == len(records), "连接元数据行数不等于父 CERIG 行数")  # 一一映射数量门禁。
    merged: list[dict[str, Any]] = []  # 初始化合并后的连接表。
    for index, (record, metadata) in enumerate(zip(records, metadata_rows, strict=True), start=1):  # 按同序逐条闭合六个源字段。
        require(int(metadata["master_node"]) == record["master_node"], f"连接元数据 master 错配：第 {index} 条")  # master 必须一致。
        require(int(metadata["slave_node"]) == record["slave_node"], f"连接元数据 slave 错配：第 {index} 条")  # slave 必须一致。
        require(str(metadata["dof_label"]).upper() == record["dof_label"], f"连接元数据 DOF 错配：第 {index} 条")  # ALL/UXYZ 必须一致。
        merged_record = dict(record)  # 复制父 CERIG 记录，避免修改输入对象。
        merged_record.update({"conn_id": f"C10-CONN-{index:05d}", "system": str(metadata["system"]), "assembly_name": str(metadata["assembly_name"]), "reason": str(metadata["reason"])})  # 添加稳定 ID 和工程语义。
        merged.append(merged_record)  # 保存已闭合当前连接。
    return merged  # 返回 5078 条稳定连接记录。


def audit_uxyz_slave_projection(paths: tuple[Path, ...], records: list[dict[str, Any]]) -> dict[str, Any]:  # 输入父依赖和连接记录并返回 UXYZ 从节点转角消费者硬门结果。
    """证明单 TYPE72 新增的从节点转角没有物理共轭刚度、质量、荷载或边界参与。"""  # 任一未知或旋转型消费者都会立即拒绝生成。
    uxyz_records = [record for record in records if record["dof_label"] == "UXYZ"]  # 只选取需要投影到纯平移节点的 3124 条连接。
    uxyz_slaves = {int(record["slave_node"]) for record in uxyz_records}  # 构造 UXYZ 原索从节点集合。
    require(len(uxyz_records) == len(uxyz_slaves) == EXPECTED_UXYZ_CONNECTIONS, "UXYZ 从节点不是一连接一唯一节点")  # 防止一个转角代数自由度被多条连接复用。
    all_master_counts: dict[int, int] = {}  # 统计全部连接中每个节点作为 master 的次数。
    all_slave_counts: dict[int, int] = {}  # 统计全部连接中每个节点作为 slave 的次数。
    for record in records:  # 扫描全部 5078 条逻辑连接。
        master = int(record["master_node"])  # 读取当前 master 节点号。
        slave = int(record["slave_node"])  # 读取当前 slave 节点号。
        all_master_counts[master] = all_master_counts.get(master, 0) + 1  # 累加 master 角色次数。
        all_slave_counts[slave] = all_slave_counts.get(slave, 0) + 1  # 累加 slave 角色次数。
    reused_uxyz_slaves = sorted(node for node in uxyz_slaves if all_slave_counts.get(node, 0) != 1 or all_master_counts.get(node, 0) != 0)  # 找出跨连接复用或兼任 master 的 UXYZ 从节点。
    require(not reused_uxyz_slaves, f"UXYZ 从节点被其他连接复用：{reused_uxyz_slaves[:20]}")  # 复用会让转角约束进入其他连接传力，必须拒绝。
    element_type_names: dict[int, str] = {}  # 保存 APDL TYPE 编号到单元名称的最新定义。
    current_type: int | None = None  # 保存按最终 include 顺序生效的当前单元类型编号。
    physical_references: dict[int, list[dict[str, Any]]] = {node: [] for node in uxyz_slaves}  # 记录每个 UXYZ 从节点参与的全部显式 E/EN 单元。
    explicit_d_nodes: set[int] = set()  # 保存全部显式节点 D 边界节点。
    cp_nodes: set[int] = set()  # 保存全部既有 CP 成员节点。
    rotational_load_records: list[dict[str, Any]] = []  # 保存施加到 UXYZ 从节点的 MX/MY/MZ 载荷异常。
    ce_command_count = 0  # 统计父依赖中的用户显式 CE 命令，预期为零。
    for path in paths:  # 严格按最终 S10 的十一项 include 顺序扫描状态与引用。
        for line_number, raw_line in enumerate(decode_utf8(path).splitlines(), start=1):  # 保留一基行号供失败定位。
            command = raw_line.split("!", 1)[0].strip()  # 去掉 APDL 行尾注释与外围空白。
            if not command:  # 空命令不参与语义审计。
                continue  # 跳到下一行。
            fields = [field.strip() for field in command.split(",")]  # 拆分命令关键字和参数字段。
            keyword = fields[0].upper()  # 读取大写 APDL 命令名。
            if keyword == "ET" and len(fields) >= 3 and INTEGER_PATTERN.fullmatch(fields[1]) is not None:  # ET 命令定义类型编号和单元名称。
                element_type_names[int(fields[1])] = fields[2].upper()  # 保存后续 E/EN 引用需要的自由度族名称。
                continue  # 当前定义命令无需进入节点引用分支。
            if keyword == "TYPE" and len(fields) >= 2 and INTEGER_PATTERN.fullmatch(fields[1]) is not None:  # TYPE 命令切换后续建单元状态。
                current_type = int(fields[1])  # 更新当前生效类型编号。
                continue  # 当前状态命令无需进入节点引用分支。
            if keyword in {"E", "EN"}:  # 只解析显式建单元命令中的节点参与关系。
                node_fields = fields[1:] if keyword == "E" else fields[2:]  # E 全部参数为节点，EN 首参数为元素号。
                element_nodes = [int(field) for field in node_fields if INTEGER_PATTERN.fullmatch(field) is not None]  # 提取可静态识别的节点编号。
                touched_slaves = uxyz_slaves.intersection(element_nodes)  # 找出当前单元命中的 UXYZ 从节点。
                for slave in touched_slaves:  # 为每个命中从节点保存类型与来源证据。
                    physical_references[slave].append({"source_file": path.name, "source_line": line_number, "type_id": current_type, "element_name": element_type_names.get(current_type, "UNRESOLVED")})  # 未解析类型也保留并在后续拒绝。
            if keyword == "D" and len(fields) >= 2 and INTEGER_PATTERN.fullmatch(fields[1]) is not None:  # 显式 D 命令可能把代数转角引入边界。
                explicit_d_nodes.add(int(fields[1]))  # 记录当前受位移约束节点。
            if keyword == "CP" and len(fields) >= 4:  # CP 从第四字段开始列出成员节点。
                cp_nodes.update(int(field) for field in fields[3:] if INTEGER_PATTERN.fullmatch(field) is not None)  # 记录全部可静态识别的 CP 成员。
            if keyword == "CE":  # 任一用户 CE 都需要独立自由度级解析，本候选不允许静默存在。
                ce_command_count += 1  # 累加显式 CE 命令数量。
            if keyword == "F" and len(fields) >= 3 and INTEGER_PATTERN.fullmatch(fields[1]) is not None:  # 显式节点力命令可能包含旋转共轭力矩。
                load_node = int(fields[1])  # 读取受载节点编号。
                load_label = fields[2].upper()  # 读取力或力矩自由度标签。
                if load_node in uxyz_slaves and load_label in {"MX", "MY", "MZ"}:  # 只把 UXYZ 从节点的三项力矩视为旋转消费者。
                    rotational_load_records.append({"source_file": path.name, "source_line": line_number, "node": load_node, "label": load_label})  # 保存异常来源供拒绝信息使用。
    allowed_element_names = {"LINK10", "LINK180", "MASS21"}  # 三类单元均只使用平移或在本项目设置下只保留平移质量。
    unresolved_or_rotational_references = [reference for references in physical_references.values() for reference in references if str(reference["element_name"]) not in allowed_element_names]  # 汇总未知或具旋转自由度的物理单元引用。
    require(not unresolved_or_rotational_references, f"UXYZ 从节点存在旋转型或未知单元消费者：{unresolved_or_rotational_references[:20]}")  # 任何反例都会破坏单 TYPE72 投影等价性。
    link_reference_counts = {node: sum(1 for reference in references if str(reference["element_name"]) in {"LINK10", "LINK180"}) for node, references in physical_references.items()}  # 统计每个从节点的索单元引用数。
    invalid_link_counts = sorted(node for node, count in link_reference_counts.items() if count != 2)  # 每个冻结 UXYZ 从节点应恰好由左右两根索段连接。
    require(not invalid_link_counts, f"UXYZ 从节点索邻接数量不是 2：{invalid_link_counts[:20]}")  # 缺失或额外索段均改变已审定拓扑假定。
    overlap_d = sorted(uxyz_slaves & explicit_d_nodes)  # 计算从节点与显式 D 边界交集。
    overlap_cp = sorted(uxyz_slaves & cp_nodes)  # 计算从节点与既有 CP 交集。
    require(not overlap_d, f"UXYZ 从节点与 D 边界重叠：{overlap_d[:20]}")  # D 会让直接消元转角产生冗余或矛盾约束。
    require(not overlap_cp, f"UXYZ 从节点与 CP 重叠：{overlap_cp[:20]}")  # 官方禁止 direct-elimination MPC 节点再参与 CP。
    require(ce_command_count == 0, f"父依赖出现 {ce_command_count} 条用户 CE，无法证明单 TYPE72 投影无重复约束")  # 显式 CE 必须为零。
    require(not rotational_load_records, f"UXYZ 从节点存在显式力矩载荷：{rotational_load_records[:20]}")  # 力矩会使新增代数转角成为物理载荷通道。
    mass_include_text = decode_utf8(next(path for path in paths if path.name == "apply_dynamic_mass21_spatialized_v2.inp"))  # 读取最终保留的空间质量 include。
    require("ET,71,MASS21" in mass_include_text and "KEYOPT,71,3,2" in mass_include_text, "TYPE71 MASS21 不是冻结的仅三平移质量设置")  # 固定 KEYOPT(3)=2，禁止转动惯量进入投影节点。
    final_mass_slave_count = len({node for node, references in physical_references.items() if any(reference["source_file"] == "apply_dynamic_mass21_spatialized_v2.inp" and reference["element_name"] == "MASS21" for reference in references)})  # 统计带最终 TYPE71 平移质量的 UXYZ 从节点数。
    require(final_mass_slave_count == 1152, f"带最终平移 MASS21 的 UXYZ 从节点数漂移：{final_mass_slave_count}")  # 与已执行 S10 的冻结分配数量闭合。
    return {"schema_version": 1, "status": "PASSED", "uxyz_slave_count": len(uxyz_slaves), "slave_reused_by_other_connection_count": len(reused_uxyz_slaves), "allowed_element_names": sorted(allowed_element_names), "link_reference_count_per_slave": 2, "final_translation_mass_slave_count": final_mass_slave_count, "rotational_element_consumer_count": len(unresolved_or_rotational_references), "rotational_load_consumer_count": len(rotational_load_records), "explicit_d_overlap_count": len(overlap_d), "cp_overlap_count": len(overlap_cp), "explicit_ce_command_count": ce_command_count, "projection_equivalence": "CONDENSED_PHYSICAL_UXYZ_SPACE_UNCHANGED", "hard_gate": "REJECT_IF_ANY_SLAVE_ROTATIONAL_CONSUMER_APPEARS"}  # 返回可机读的单 TYPE72 语义等价门禁证据。


def make_definition_block(newline: str) -> str:  # 输入源换行并返回可逆 MPC184 定义块。
    """只定义一个 TYPE72 rigid beam，彻底移除会形成串联依赖链的 TYPE73。"""  # 返回文本每条 APDL 命令均有中文注释。
    lines = [DEFINITION_BEGIN, f"ET,{RIGID_TYPE_ID},MPC184 ! TYPE72 定义零质量六自由度大转动刚臂", f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择 MPC184 rigid-beam 公式", f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用直接消元精确实施刚臂约束", f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留 rigid-beam 的几何刚度以支持预应力模态", "CSYS,0 ! 恢复全局笛卡尔坐标，保证后续原节点坐标语义不变", DEFINITION_END]  # 完整定义块只含一个直接消元类型，禁止串联第二个 MPC。
    return newline.join(lines) + newline  # 返回带源文件同类换行和末尾换行的块。


def make_connection_block(newline: str, records: list[dict[str, Any]], nodes: dict[int, dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:  # 输入连接和全模型节点并返回 APDL 替换块及映射台账。
    """ALL 与 UXYZ 均生成一个 TYPE72；UXYZ 的从节点已由源审计证明只有平移型索与质量自由度。"""  # 编号严格使用一个封板连续区间。
    lines: list[str] = [CONNECTION_BEGIN, "! 每条原 CERIG 只生成一个 TYPE72，禁止辅助节点与串联直接消元链"]  # 初始化连接替换块和用途说明。
    mapping_rows: list[dict[str, Any]] = []  # 初始化 5078 条逻辑到物理 MPC184 的映射表。
    lines.append("! 以下 MPC184 元素按父 CERIG 顺序生成，保持每条逻辑连接一对一可逆映射")  # 分隔说明与连接元素块。
    next_element = MPC_ELEMENT_START  # 初始化 MPC184 连续元素编号游标。
    for record in records:  # 按父 CERIG 原顺序生成全部 MPC184。
        master = int(record["master_node"])  # 当前逻辑 master 节点。
        slave = int(record["slave_node"])  # 当前逻辑 slave 节点。
        require(master in nodes and slave in nodes, f"连接端点不在最终 S10 节点表：{record['conn_id']}")  # 两端引用必须存在。
        assembly = str(record["assembly_name"]).replace("!", "_")  # 清理可能截断 APDL 行尾注释的感叹号。
        rigid_element = next_element  # 每条逻辑连接恰好分配一个 TYPE72 元素。
        lines.append(f"TYPE,{RIGID_TYPE_ID} ! 选择 TYPE72 rigid beam 实现 {record['conn_id']} 的刚性部分")  # 每条连接显式选择类型，避免前序状态泄漏。
        if record["dof_label"] == "ALL":  # 六自由度刚接直接连接原 master 和 slave。
            lines.append(f"EN,{next_element},{master},{slave} ! {record['conn_id']}：ALL 六自由度 direct-elimination 刚接；装配={assembly}")  # 写一个 TYPE72 元素。
            implementation = "MPC184_TYPE72_DIRECT_ELIMINATION_RIGID_BEAM"  # 记录 ALL 的求解器实现说明。
        else:  # UXYZ 的原索从节点只有平移型 LINK 与 MASS21，因此刚梁转角只形成无外部参与的代数投影。
            lines.append(f"EN,{next_element},{master},{slave} ! {record['conn_id']}：UXYZ 直接连接纯平移索节点并保留偏心刚体平移；装配={assembly}")  # 写单个 TYPE72 并删除不稳定串联链。
            implementation = "MPC184_TYPE72_DIRECT_ELIMINATION_PROJECTED_TO_TRANSLATION_ONLY_SLAVE"  # 记录 UXYZ 的有效自由度投影实现说明。
        next_element += 1  # 每条逻辑连接只消耗一个连续元素号。
        mapping_rows.append({"conn_id": record["conn_id"], "source_file": PARENT_INCLUDE_NAME, "source_line": record["source_line"], "original_command": record["original_command"], "master_node": master, "slave_node": slave, "dof_label": record["dof_label"], "system": record["system"], "assembly_name": record["assembly_name"], "reason": record["reason"], "aux_node": "", "rigid_element": rigid_element, "translation_link_element": "", "implementation": implementation})  # 保留旧列以兼容审计消费者，并明确辅助节点与第二 MPC 均为空。
    require(next_element - 1 == MPC_ELEMENT_END and len(mapping_rows) == EXPECTED_LOGICAL_CONNECTIONS, "MPC184 元素数量或末号不闭合")  # 必须恰为 5078 个元素和 5078 条映射。
    lines.append(CONNECTION_END)  # 结束可逆连接替换块。
    return newline.join(lines) + newline, mapping_rows  # 返回带同类换行的 APDL 块和映射表。


def make_component_block(newline: str) -> str:  # 输入源换行并返回 MPC184 审计组件定义块。
    """把 5078 个候选元素收集为 V2_MPC184_E，便于未来 ELIST 和结果筛选。"""  # 返回文本无物理属性变化。
    lines = [COMPONENT_BEGIN, "ESEL,NONE ! 清空当前元素选择，避免审计组件混入物理梁", f"ESEL,A,ELEM,,{MPC_ELEMENT_START},{MPC_ELEMENT_END} ! 选择连续 5078 个 C10 MPC184 元素", "CM,V2_MPC184_E,ELEM ! 建立 C10 MPC184 元素审计组件", "ALLSEL,ALL ! 恢复全部实体选择，保持后续主控选择状态不变", COMPONENT_END]  # 组装稳定组件块。
    return newline.join(lines) + newline  # 返回带源换行和末尾换行的块。


def transform_include(source_bytes: bytes, records: list[dict[str, Any]], nodes: dict[int, dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:  # 输入父 include 字节并返回候选、映射和可逆审计。
    """只插入三类标记块并原位替换连续 CERIG，反变换必须逐字节恢复父哈希。"""  # 返回候选 UTF-8 字节。
    source_text = source_bytes.decode("utf-8")  # 父 include 已通过 UTF-8 和固定哈希验证。
    newline = "\r\n" if "\r\n" in source_text else "\n"  # 继承父文件的实际换行风格。
    require("\n" not in source_text.replace("\r\n", "") if newline == "\r\n" else True, "父 include 含混合换行")  # CRLF 文件不得含裸 LF。
    parsed_records, first_cerig, last_cerig, lines = parse_cerig(source_text)  # 重新解析父连接块位置和原行。
    require([(item["master_node"], item["slave_node"], item["dof_label"]) for item in parsed_records] == [(item["master_node"], item["slave_node"], item["dof_label"]) for item in records], "传入连接表与父 include 重新解析结果不一致")  # 防止调用方记录漂移。
    original_cerig_text = "".join(lines[first_cerig:last_cerig + 1])  # 保存 5078 条原命令及其原始换行。
    definition_block = make_definition_block(newline)  # 生成唯一 TYPE72 rigid-beam 定义块。
    connection_block, mapping_rows = make_connection_block(newline, records, nodes)  # 生成一连接一元素的 MPC184 替换块。
    component_block = make_component_block(newline)  # 生成 MPC184 审计组件块。
    keyopt_indices = [index for index, line in enumerate(lines) if line.rstrip("\r\n").strip().upper() == "KEYOPT,70,3,3"]  # 定位 TYPE70 定义后的唯一插入锚点。
    require(len(keyopt_indices) == 1, "父 include 的 KEYOPT,70,3,3 锚点不是唯一一条")  # 定义块插入位置必须唯一。
    candidate_lines = list(lines)  # 创建父行表副本，源对象保持只读。
    candidate_lines[first_cerig:last_cerig + 1] = [connection_block]  # 用一个可逆块原位替换连续 CERIG。
    candidate_lines.insert(keyopt_indices[0] + 1, definition_block)  # 在 TYPE70 定义后、材料前插入 MPC184 定义。
    finish_indices = [index for index, line in enumerate(candidate_lines) if line.rstrip("\r\n").strip().upper() == "FINISH"]  # 定位最终 FINISH 锚点。
    require(bool(finish_indices), "父 include 缺少 FINISH 锚点")  # 组件必须在最终离开前处理器前建立。
    candidate_lines.insert(finish_indices[-1], component_block)  # 在最终 FINISH 前插入审计组件并保留原 ALLSEL。
    candidate_text = "".join(candidate_lines)  # 重组成完整候选文本。
    require(candidate_text.count(DEFINITION_BEGIN) == 1 and candidate_text.count(CONNECTION_BEGIN) == 1 and candidate_text.count(COMPONENT_BEGIN) == 1, "候选可逆标记数量异常")  # 三块各只允许出现一次。
    require(sum(1 for line in candidate_text.splitlines() if CERIG_PATTERN.fullmatch(line) is not None) == 0, "候选 include 仍含可执行 CERIG")  # 连接替换后 CERIG 源命令必须为零。
    canonical_text = candidate_text  # 创建反变换工作文本。
    require(canonical_text.count(definition_block) == 1, "候选定义块无法唯一反向剥离")  # 定义块身份必须唯一。
    canonical_text = canonical_text.replace(definition_block, "", 1)  # 删除新增类型、截面和坐标定义。
    require(canonical_text.count(connection_block) == 1, "候选连接块无法唯一反向恢复")  # 替换块身份必须唯一。
    canonical_text = canonical_text.replace(connection_block, original_cerig_text, 1)  # 在原位置恢复 5078 条 CERIG 原文。
    require(canonical_text.count(component_block) == 1, "候选组件块无法唯一反向剥离")  # 组件块身份必须唯一。
    canonical_text = canonical_text.replace(component_block, "", 1)  # 删除新增审计组件。
    canonical_bytes = canonical_text.encode("utf-8")  # 转回字节供强哈希比较。
    require(canonical_bytes == source_bytes, "C10 include 反向剥离后未逐字节恢复最终 S10")  # 最强单变量门禁必须精确通过。
    audit = {"schema_version": 2, "status": "PASSED", "source_sha256": sha256_bytes(source_bytes), "candidate_sha256": sha256_bytes(candidate_text.encode("utf-8")), "canonicalized_sha256": sha256_bytes(canonical_bytes), "canonicalized_equals_source_bytes": True, "source_cerig_count": EXPECTED_LOGICAL_CONNECTIONS, "candidate_cerig_count": 0, "aux_node_count": 0, "mpc184_type72_count": EXPECTED_LOGICAL_CONNECTIONS, "mpc184_type73_count": 0, "mpc184_total_count": EXPECTED_MPC_ELEMENTS, "allowed_change_family_count": 1, "allowed_change_family": "CERIG_TO_SINGLE_MPC184_LARGE_ROTATION_CONNECTION_KINEMATICS_ONLY"}  # 汇总可逆差分范围、单元素拓扑和哈希闭合。
    return candidate_text.encode("utf-8"), mapping_rows, audit  # 返回候选字节、逐连接映射和审计摘要。


def insert_after_line(text: str, exact_line: str, block: str, newline: str) -> str:  # 输入文本、唯一锚点和块并返回插入后的文本。
    """锚点必须以完整独立行唯一出现。"""  # 用于 C10 主控可逆非物理审计块插入。
    anchor = exact_line + newline  # 构造带父换行的完整锚点行。
    require(text.count(anchor) == 1, f"主控插入锚点不是唯一一条：{exact_line}")  # 防止插错同名注释或命令。
    return text.replace(anchor, anchor + block, 1)  # 在锚点行后插入一次指定块。


def transform_main(source_bytes: bytes, jobname: str) -> tuple[bytes, dict[str, Any]]:  # 输入最终 S10 主控和新 jobname 并返回可逆 C10 主控及审计。
    """保留 LS1/LS2、80阶、荷载和输出控制，只更新身份、单元总数并增加 TYPE72 审计。"""  # 返回候选 UTF-8 字节。
    source_text = source_bytes.decode("utf-8")  # 严格按 UTF-8 读取父主控。
    newline = "\r\n" if "\r\n" in source_text else "\n"  # 继承父主控换行。
    require("C10" not in source_text and "c10" not in source_text, "父 S10 主控已含 C10 标识，无法安全全局回退")  # 保证反向重命名无歧义。
    require(str(EXPECTED_CANDIDATE_ELEMENTS) not in source_text, "父主控已含 C10 目标单元计数")  # 节点数保持不变，只需保证新单元计数反向替换无歧义。
    candidate = source_text.replace("S10", "C10").replace("s10", "c10")  # 统一改写变量、标题、输出前缀和注释身份。
    documentation_replacements = (("! C10_LEGACY_COMPLETE：只使用 U00 图封存的十一项 legacy APDL。", "! C10_MPC_ONLY：继承最终 S10 十项不变量，并仅把受控连接 include 的 CERIG 替换为 MPC184。"), ("/TITLE,C10 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL", "/TITLE,C10 MPC184 CONNECTION PATCH FULL BRIDGE PRESTRESSED MODAL"), ("! 把全部约束方程写入独立审计文件，供执行后确认 CERIG 展开结果。", "! 把全部约束方程写入独立审计文件，供执行后确认没有 legacy CERIG 方程残留。"))  # 冻结三处只改变审阅语义、不改变模型控制流的 C10 文案替换。
    for inherited_text, c10_text in documentation_replacements:  # 按稳定顺序改正全局标签替换后仍过时的 legacy 说明。
        require(candidate.count(inherited_text) == 1, f"父主控文案锚点不是唯一一条：{inherited_text}")  # 每处继承文案必须唯一，防止宽泛替换。
        candidate = candidate.replace(inherited_text, c10_text, 1)  # 写入符合 C10 实际连接变化的标题或审计说明。
    inherited_jobname = "cw_C10_0716t050342_a4"  # S10→C10 全局替换后暂存的父作业名。
    inherited_jobname_count = candidate.count(inherited_jobname)  # 统计 /FILNAME、FILE 和 SAVE 对父作业前缀的全部引用。
    require(inherited_jobname_count == 5, f"父主控 jobname 前缀引用数为 {inherited_jobname_count}，预期 5")  # 最终 S10 应有一处主作业、两处结果读取和两处数据库保存引用。
    candidate = candidate.replace(inherited_jobname, jobname)  # 把五处同一作业前缀全部改为本运行唯一 ASCII jobname。
    require(EXPECTED_PARENT_NODES == EXPECTED_CANDIDATE_NODES, "单 TYPE72 方案意外改变节点总数")  # 明确禁止生成任何辅助节点。
    candidate = candidate.replace(str(EXPECTED_PARENT_ELEMENTS), str(EXPECTED_CANDIDATE_ELEMENTS))  # 更新全部单元计数注释和 fail-closed 常量。
    query_lines = [MAIN_QUERY_BEGIN, "! 只选择 TYPE72 rigid-beam 元素，用于执行期连接数量门禁。", f"ESEL,S,TYPE,,{RIGID_TYPE_ID}", "! 读取 TYPE72 数量，预期 5078。", "*GET,C10_T72,ELEM,0,COUNT", MAIN_QUERY_END]  # 构造唯一 MPC184 类型查询块，每条命令均有紧邻中文说明。
    query_block = newline.join(query_lines) + newline  # 使用父主控换行形成完整块。
    candidate = insert_after_line(candidate, "*GET,C10_T71,ELEM,0,COUNT", query_block, newline)  # 在既有 TYPE71 查询后插入新类型查询。
    output_lines = [MAIN_OUTPUT_BEGIN, "! 第三行只写 TYPE72 单刚臂计数，TYPE73 已按拓扑修复要求移除。", "! 下一条 *VWRITE 与其后裸 Fortran 格式行必须相邻，二者之间不得插入注释。", "*VWRITE,C10_T72", "('TYPE72=',F12.0)", MAIN_OUTPUT_END]  # 构造合法 *VWRITE 输出块。
    output_block = newline.join(output_lines) + newline  # 保持父主控换行。
    candidate = insert_after_line(candidate, "('TYPE70=',F12.0,', TYPE71=',F12.0)", output_block, newline)  # 在既有拓扑输出后追加 MPC 类型行。
    audit_lines = [MAIN_AUDIT_BEGIN, "! 把全部 C10 MPC184 元素写入独立执行期审计文件。", "/OUTPUT,c10_mpc184_elements,txt", "! 选择 prepare 阶段建立的 V2_MPC184_E 审计组件。", "CMSEL,S,V2_MPC184_E", "! 列出 5078 个单 TYPE72 MPC184 元素及其节点引用。", "ELIST,ALL", "! 恢复全部实体选择，避免影响后续拓扑门禁。", "ALLSEL,ALL", "! 恢复 MAPDL 主输出，结束 MPC184 元素证据文件。", "/OUTPUT", MAIN_AUDIT_END]  # 构造执行期连接元素审计块。
    audit_block = newline.join(audit_lines) + newline  # 使用父主控换行。
    gate_anchor = "! 节点总数不等于 109086 时拒绝，防止缺 include 或模型线混入。"  # 节点数保持 S10 原值，该门禁前是审计块的唯一插入位置。
    require(candidate.count(gate_anchor + newline) == 1, "C10 节点门禁锚点不是唯一一条")  # 锚点唯一性门禁。
    candidate = candidate.replace(gate_anchor + newline, audit_block + gate_anchor + newline, 1)  # 在拓扑拒绝门禁前写 MPC 元素列表。
    gate_lines = [MAIN_GATE_BEGIN, "! TYPE72 数量不等于 5078 时拒绝，防止 ALL 或 UXYZ 单刚臂缺失。", "*IF,C10_T72,NE,5078,THEN", "! 把唯一拒绝原因写入 C10 gate 状态文件。", "/OUTPUT,c10_gate_status,txt", "! 固定拒绝原因 TYPE_72_COUNT_MISMATCH。", "/COM,STATUS=REJECTED REASON=TYPE_72_COUNT_MISMATCH", "! 恢复 MAPDL 主输出。", "/OUTPUT", "! 门禁失败立即退出且不保存数据库。", "/EXIT,NOSAVE", "! 结束 TYPE72 fail-closed 条件分支。", "*ENDIF", MAIN_GATE_END]  # 构造唯一 MPC184 类型数量拒绝门禁。
    gate_block = newline.join(gate_lines) + newline  # 使用父主控换行形成完整门禁块。
    reason_position = candidate.find("/COM,STATUS=REJECTED REASON=TYPE_71_COUNT_MISMATCH")  # 定位既有 TYPE71 拒绝分支。
    require(reason_position >= 0, "未找到 TYPE71 门禁插入锚点")  # 既有拓扑控制必须存在。
    endif_position = candidate.find("*ENDIF" + newline, reason_position)  # 定位该分支结束命令。
    require(endif_position >= 0, "未找到 TYPE71 门禁结束锚点")  # 防止把新门禁插入错误作用域。
    insertion_position = endif_position + len("*ENDIF" + newline)  # 计算分支结束后的精确插入字节位置。
    candidate = candidate[:insertion_position] + gate_block + candidate[insertion_position:]  # 插入新类型门禁。
    canonical = candidate  # 创建主控反变换工作文本。
    for block in (query_block, output_block, audit_block, gate_block):  # 依次移除四个新增非物理审计块。
        require(canonical.count(block) == 1, "C10 主控新增块无法唯一反向剥离")  # 每块必须恰好出现一次。
        canonical = canonical.replace(block, "", 1)  # 删除当前新增块。
    for inherited_text, c10_text in reversed(documentation_replacements):  # 逆序恢复三处仅供 C10 审阅的文案变化。
        require(canonical.count(c10_text) == 1, f"C10 主控文案无法唯一反向恢复：{c10_text}")  # 候选文案必须保持唯一且未被其他变换污染。
        canonical = canonical.replace(c10_text, inherited_text, 1)  # 恢复全局 S10→C10 标签替换后的父文案。
    canonical = canonical.replace(str(EXPECTED_CANDIDATE_ELEMENTS), str(EXPECTED_PARENT_ELEMENTS))  # 恢复 S10 单元计数。
    require(canonical.count(jobname) == inherited_jobname_count, "C10 主控 jobname 引用数无法与父控制流闭合")  # 新前缀必须覆盖父主控的全部五处引用且无额外出现。
    canonical = canonical.replace(jobname, inherited_jobname)  # 把全部主作业、结果读取和数据库保存引用恢复为父前缀。
    canonical = canonical.replace("C10", "S10").replace("c10", "s10")  # 反向恢复父变量、标题和输出前缀。
    canonical_bytes = canonical.encode("utf-8")  # 转成字节执行最强等价门禁。
    require(canonical_bytes == source_bytes, "C10 主控反向规范化后未逐字节恢复最终 S10 主控")  # 控制流除白名单外必须完全相同。
    audit = {"schema_version": 2, "status": "PASSED", "source_sha256": sha256_bytes(source_bytes), "candidate_sha256": sha256_bytes(candidate.encode("utf-8")), "canonicalized_sha256": sha256_bytes(canonical_bytes), "canonicalized_equals_source_bytes": True, "identity_changes": ["S10_TO_C10_LABELS", "UNIQUE_JOBNAME", "OUTPUT_PREFIXES", "THREE_C10_DOCUMENTATION_LINES"], "topology_changes": {"node_count": [EXPECTED_PARENT_NODES, EXPECTED_CANDIDATE_NODES], "element_count": [EXPECTED_PARENT_ELEMENTS, EXPECTED_CANDIDATE_ELEMENTS], "type72_expected": EXPECTED_LOGICAL_CONNECTIONS, "type73_expected": 0}, "added_runtime_audits": ["TYPE72_COUNT", "V2_MPC184_E_ELIST"], "unchanged_control_contract": ["DEPENDENCY_ORDER", "LS1_STATIC_FROM_ZERO", "LS2_HOLD", "NLGEOM", "PSTRES", "LANB_80_NO_FREQUENCY_CAP", "MXPAND_ELEMENT_CALC", "NSOL_VECTOR_EXPORT", "VENG_HISTORY_EXPORT"]}  # 汇总主控可逆白名单和单 TYPE72 拓扑，并显式记录三处非物理文案修正。
    return candidate.encode("utf-8"), audit  # 返回候选主控字节和控制流审计。


class UnionFind:  # 维护求解器无关节点连通分量，用于静态拓扑和锚定检查。
    """仅分析节点图连通性，不替代六自由度矩阵秩或 MAPDL 数值验证。"""  # 类输出为连通分量根标识。

    def __init__(self) -> None:  # 无输入；初始化空父指针和秩表。
        self.parent: dict[int, int] = {}  # 每个已出现节点到其集合父节点的映射。
        self.rank: dict[int, int] = {}  # 并查集按秩合并的近似树高。

    def add(self, node: int) -> None:  # 输入节点号；若不存在则创建单节点集合，无返回值。
        if node not in self.parent:  # 新节点尚未进入连通图时才初始化。
            self.parent[node] = node  # 新节点初始根为自身。
            self.rank[node] = 0  # 新集合初始秩为零。

    def find(self, node: int) -> int:  # 输入已添加节点并返回其当前集合根。
        self.add(node)  # 允许调用方对新节点直接查询并安全初始化。
        if self.parent[node] != node:  # 非根节点需要执行路径压缩。
            self.parent[node] = self.find(self.parent[node])  # 递归指向最终根以加速后续查询。
        return self.parent[node]  # 返回压缩后的根节点号。

    def union(self, left: int, right: int) -> None:  # 输入两个节点号；合并其集合且无返回值。
        left_root = self.find(left)  # 查找左节点集合根。
        right_root = self.find(right)  # 查找右节点集合根。
        if left_root == right_root:  # 已处于同一集合时无需修改。
            return  # 结束当前合并。
        if self.rank[left_root] < self.rank[right_root]:  # 左树较矮时挂到右根。
            self.parent[left_root] = right_root  # 更新左根父指针。
        elif self.rank[left_root] > self.rank[right_root]:  # 右树较矮时挂到左根。
            self.parent[right_root] = left_root  # 更新右根父指针。
        else:  # 两树等高时任选左根并增加其秩。
            self.parent[right_root] = left_root  # 把右根挂到左根。
            self.rank[left_root] += 1  # 合并等高树后左根秩增加一。


def graph_audit(paths: tuple[Path, ...], nodes: dict[int, dict[str, Any]], mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:  # 输入父依赖、节点表和候选映射并返回静态连通审计。
    """联合 E/EN、CP 和新单 MPC 边，检查连接端点、分量和显式 D 锚定。"""  # 不声称完成 DOF 秩分析。
    graph = UnionFind()  # 创建空节点连通图。
    anchored_nodes: set[int] = set()  # 保存至少有一项显式 D 约束的节点。
    cp_nodes: set[int] = set()  # 保存参与既有 CP 的节点，用于交叉审计。
    ignored_nonnumeric_element_fields = 0  # 统计 E/EN 中非整数参数字段，正常模型预期为零或空字段。
    for node_id in nodes:  # 先把最终 S10 的全部节点纳入图。
        graph.add(node_id)  # 每个定义节点至少形成一个待连接集合。
    for path in paths:  # 按最终 S10 依赖顺序扫描连接、单元和边界命令。
        for raw_line in decode_utf8(path).splitlines():  # 逐行解析 APDL 命令。
            command = raw_line.split("!", 1)[0].strip()  # 去除注释和外围空白。
            if not command:  # 空命令不参与图分析。
                continue  # 跳到下一行。
            fields = [field.strip() for field in command.split(",")]  # 拆分 APDL 字段。
            keyword = fields[0].upper()  # 读取命令名。
            node_fields: list[str] = []  # 初始化当前元素的节点字段表。
            if keyword == "EN":  # EN 的第一个参数是元素号，节点从第三字段开始。
                node_fields = fields[2:]  # 取所有可能的 I/J/K 等节点字段。
            elif keyword == "E":  # E 的全部参数均为节点号。
                node_fields = fields[1:]  # 取自动编号元素的节点字段。
            if node_fields:  # 当前行是 E 或 EN 时构造节点边。
                element_nodes: list[int] = []  # 保存当前元素中可识别且存在的节点号。
                for field in node_fields:  # 扫描全部节点字段。
                    if not field:  # 空参数表示未使用的高阶节点槽位。
                        continue  # 忽略空字段。
                    if INTEGER_PATTERN.fullmatch(field) is None:  # 参数表达式无法静态还原为节点号。
                        ignored_nonnumeric_element_fields += 1  # 记录但不擅自解释参数表达式。
                        continue  # 跳过当前非数值字段。
                    node_id = int(field)  # 解析十进制节点号。
                    if node_id in nodes:  # 只把已定义节点纳入物理图。
                        element_nodes.append(node_id)  # 保存当前元素端点或方向节点。
                if element_nodes:  # 至少识别一个节点时建立集合。
                    first_node = element_nodes[0]  # 取第一个节点作为当前元素星形合并中心。
                    graph.add(first_node)  # 确保中心节点存在。
                    for node_id in element_nodes[1:]:  # 把其余端点连接到中心节点。
                        graph.union(first_node, node_id)  # 合并当前元素涉及的节点集合。
            if keyword == "CP" and len(fields) >= 4:  # CP 从第四字段起列出参与耦合的节点。
                coupled = [int(field) for field in fields[3:] if INTEGER_PATTERN.fullmatch(field) is not None]  # 提取全部显式 CP 节点号。
                cp_nodes.update(coupled)  # 保存 CP 占用节点集合。
                if coupled:  # 非空 CP 节点表形成同一图连接。
                    for node_id in coupled[1:]:  # 把后续节点并入首节点集合。
                        graph.union(coupled[0], node_id)  # 合并 CP 连接边。
            if keyword == "D" and len(fields) >= 2 and INTEGER_PATTERN.fullmatch(fields[1]) is not None:  # 显式节点 D 命令提供锚定证据。
                anchored_nodes.add(int(fields[1]))  # 记录当前受约束节点。
    aux_nodes: set[int] = set()  # 单 TYPE72 方案必须保持为空，用于阻止辅助节点回归。
    connection_endpoints: set[int] = set()  # 保存全部原 master/slave 节点集合。
    for row in mapping_rows:  # 把候选单个 MPC184 边加入图并检查无辅助节点。
        master = int(row["master_node"])  # 读取逻辑 master。
        slave = int(row["slave_node"])  # 读取逻辑 slave。
        connection_endpoints.update((master, slave))  # 记录连接端点用于边界交叉统计。
        aux_value = row["aux_node"]  # 读取兼容映射列中的辅助节点字段。
        require(aux_value == "", f"单 TYPE72 映射意外出现辅助节点：{row['conn_id']}")  # 任何非空值都表示不稳定串联链回归。
        graph.union(master, slave)  # ALL 与 UXYZ 均直接合并原 master—slave 拓扑节点。
    component_sizes: dict[int, int] = {}  # 统计每个连通分量包含的节点数。
    for node_id in graph.parent:  # 遍历父节点表内全部父和新增节点。
        root = graph.find(node_id)  # 获取压缩后的分量根。
        component_sizes[root] = component_sizes.get(root, 0) + 1  # 当前分量节点数增加一。
    anchored_roots = {graph.find(node_id) for node_id in anchored_nodes if node_id in graph.parent}  # 计算至少含一个 D 节点的分量集合。
    unanchored_roots = set(component_sizes) - anchored_roots  # 得到无显式 D 锚定的拓扑分量。
    overlap_cp = connection_endpoints & cp_nodes  # 统计连接端点与既有 CP 的节点交集。
    return {"scope": "SOLVER_INDEPENDENT_NODE_GRAPH_NOT_DOF_RANK", "full_graph_node_count": len(graph.parent), "component_count": len(component_sizes), "anchored_component_count": len(anchored_roots), "unanchored_component_count": len(unanchored_roots), "largest_component_node_count": max(component_sizes.values()) if component_sizes else 0, "aux_node_count": len(aux_nodes), "all_aux_nodes_connected": all(graph.find(node_id) in component_sizes for node_id in aux_nodes), "connection_endpoint_count": len(connection_endpoints), "connection_endpoint_cp_overlap_count": len(overlap_cp), "connection_endpoint_cp_overlap_sample": sorted(overlap_cp)[:20], "explicit_d_anchored_node_count": len(anchored_nodes), "ignored_nonnumeric_element_fields": ignored_nonnumeric_element_fields}  # 返回静态图统计并明确不等同矩阵秩。


def build_connection_ir(records: list[dict[str, Any]], mapping_rows: list[dict[str, Any]], nodes: dict[int, dict[str, Any]]) -> dict[str, Any]:  # 输入连接与映射并返回正式连接 IR。
    """逐条描述六自由度行为、来源、阶段、局部系和求解器实现。"""  # 返回 JSON 顶层对象。
    mapping_by_id = {str(row["conn_id"]): row for row in mapping_rows}  # 建立稳定 CONN-ID 到候选实体映射。
    connections: list[dict[str, Any]] = []  # 初始化 5078 条正式 IR 记录。
    for record in records:  # 按父 CERIG 顺序保持稳定输出。
        conn_id = str(record["conn_id"])  # 读取稳定连接 ID。
        mapping = mapping_by_id[conn_id]  # 获取候选物理实现编号。
        is_uxyz = record["dof_label"] == "UXYZ"  # 判断三平移释放转动语义。
        dof_behavior = {"UX": "RIGID_DIRECT_ELIMINATION", "UY": "RIGID_DIRECT_ELIMINATION", "UZ": "RIGID_DIRECT_ELIMINATION", "RX": "ALGEBRAIC_TIE_WITH_ZERO_PHYSICAL_CONJUGATE" if is_uxyz else "RIGID_DIRECT_ELIMINATION", "RY": "ALGEBRAIC_TIE_WITH_ZERO_PHYSICAL_CONJUGATE" if is_uxyz else "RIGID_DIRECT_ELIMINATION", "RZ": "ALGEBRAIC_TIE_WITH_ZERO_PHYSICAL_CONJUGATE" if is_uxyz else "RIGID_DIRECT_ELIMINATION"}  # UXYZ 三项转角只属于单 TYPE72 代数闭合，源审计保证没有物理刚度、质量、荷载或边界消费者。
        connections.append({"conn_id": conn_id, "connection_class": "SINGLE_RIGID_BEAM_PROJECTED_TO_TRANSLATION_ONLY_SLAVE" if is_uxyz else "SIX_DOF_RIGID_CONNECTION", "master_node": record["master_node"], "slave_node": record["slave_node"], "aux_node": None, "master_xyz_mm": list(nodes[int(record["master_node"])]["xyz"]), "slave_xyz_mm": list(nodes[int(record["slave_node"])]["xyz"]), "dof_behavior": dof_behavior, "stage": "ACTIVE_FOR_ALL_S10_INHERITED_STAGES", "reference_coordinate_system": "GLOBAL_X_LONG_Y_TRANSVERSE_Z_VERTICAL", "solver_mapping": {"rigid_type": RIGID_TYPE_ID, "rigid_element": mapping["rigid_element"], "translation_link_type": None, "translation_link_element": None, "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None}, "source_ref": {"file": PARENT_INCLUDE_NAME, "line": record["source_line"], "command": record["original_command"], "metadata_file": str(CONSTRAINT_METADATA_PATH), "system": record["system"], "assembly": record["assembly_name"], "reason": record["reason"]}, "assumption_ref": "C10-ASSUMPTION-UXYZ-TRANSLATION-PROJECTION-002" if is_uxyz else "C10-ASSUMPTION-ALL-001", "projection_gate_ref": "qa/uxyz_slave_projection_audit.json" if is_uxyz else None, "drawing_ref": None})  # 保存一条完整可追溯连接 IR，并显式声明无辅助节点、无 TYPE73、无罚刚度。
    return {"schema_version": 2, "status": "STATIC_IR_COMPLETE_NUMERICAL_VALIDATION_PENDING", "coordinate_units": "mm", "force_units": "N", "moment_units": "N_mm", "connection_count": len(connections), "connections": connections}  # 返回正式 IR 和单位声明。


def build_symbolic_constraint_matrix(mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:  # 输入候选映射并返回有限转动符号约束行表。
    """每条 TYPE72 记录六个非线性刚体运动学行，并区分 UXYZ 的三项幽灵转角行。"""  # 不伪造数值切线矩阵秩。
    rows: list[dict[str, Any]] = []  # 初始化符号约束行。
    row_keys: set[tuple[Any, ...]] = set()  # 用于检查结构上完全重复的符号行。
    duplicate_count = 0  # 初始化重复行计数。
    for mapping in mapping_rows:  # 按稳定连接顺序展开求解器无关约束语义。
        conn_id = str(mapping["conn_id"])  # 读取稳定连接 ID。
        master = int(mapping["master_node"])  # 读取 master 节点。
        slave = int(mapping["slave_node"])  # 读取 slave 节点。
        require(mapping["aux_node"] == "", f"符号矩阵发现辅助节点回归：{conn_id}")  # 单 TYPE72 方案不允许中间节点。
        rigid_target = slave  # ALL 与 UXYZ 的刚臂均直接指向原 slave。
        for dof in ("UX", "UY", "UZ", "RX", "RY", "RZ"):  # 每个 TYPE72 展开六条有限转动刚体关系。
            row_key = ("FINITE_ROTATION_RIGID_BEAM", master, rigid_target, dof)  # 构造结构重复检查键。
            if row_key in row_keys:  # 完全相同端点和自由度表示重复约束行。
                duplicate_count += 1  # 累加重复数量。
            row_keys.add(row_key)  # 保存当前符号行键。
            physical_role = "ALGEBRAIC_GHOST_ROTATION_NO_PHYSICAL_CONJUGATE" if str(mapping["dof_label"]) == "UXYZ" and dof in {"RX", "RY", "RZ"} else "PHYSICAL_KINEMATIC_CONSTRAINT"  # 标记 UXYZ 新增转角只在求解器内部闭合。
            rows.append({"row_id": f"{conn_id}-RB-{dof}", "conn_id": conn_id, "formulation": "FINITE_ROTATION_RIGID_BEAM_DIRECT_ELIMINATION", "dof": dof, "node_i": master, "node_j": rigid_target, "physical_role": physical_role, "coefficient_representation": "NONLINEAR_RIGID_BODY_KINEMATICS_EVALUATED_BY_MPC184"})  # 保存不能用常系数线性矩阵替代的刚臂关系。
    require(len(rows) == EXPECTED_LOGICAL_CONNECTIONS * 6, "符号约束行数不闭合")  # 5078×6 应为 30468 行。
    require(duplicate_count == 0, f"符号约束存在 {duplicate_count} 条完全重复行")  # 静态重复约束必须为零。
    return {"schema_version": 2, "status": "SYMBOLIC_ROWS_COMPLETE_NUMERICAL_RANK_PENDING", "row_count": len(rows), "duplicate_structural_row_count": duplicate_count, "nonlinear_rigid_body_row_count": EXPECTED_LOGICAL_CONNECTIONS * 6, "uxyz_algebraic_ghost_rotation_row_count": EXPECTED_UXYZ_CONNECTIONS * 3, "linear_direct_elimination_chain_row_count": 0, "numeric_rank_evaluated": False, "numeric_rank_reason": "MPC184 finite-rotation tangent depends on assembled state and must be checked after solver assembly", "rows": rows}  # 返回单层符号行表并明确数值秩边界。


def make_legacy_chain_uxyz_load_test_input(case_id: str, load_label: str, load_value: float) -> str:  # 仅供复现旧 aux+TYPE73 微测盲区，正式计划绝不调用。
    """保留失败方案的历史回归输入生成能力，不得作为当前单 TYPE72 验收。"""  # 返回 LF 文本且调用方必须显式使用 legacy 名称。
    jobname = "c10ux_" + case_id.lower()  # 派生 ASCII 微模型作业名。
    require(len(jobname) <= 32, f"UXYZ 单位测试 jobname 过长：{jobname}")  # 满足 MAPDL 32 字符限制。
    lines = ["! C10 UXYZ 直接消元连接六向单位荷载测试；本文件由 prepare 生成但不自动执行。", "! 单位为 N、mm、N·mm、s；三个弱转动弹簧只稳定并测量已释放转角。", "/CLEAR,START ! 清空未来独立微模型会话。", f"/FILNAME,{jobname} ! 设置当前案例唯一 ASCII 作业名。", "/PREP7 ! 进入前处理器定义节点、连接和稳定弹簧。", f"ET,{RIGID_TYPE_ID},MPC184 ! 定义偏置 rigid beam。", f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择六自由度 rigid-beam 公式。", f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用直接消元实施刚臂约束。", f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留有限转动几何刚度。", f"ET,{TRANSLATION_LINK_TYPE_ID},MPC184 ! 定义共点三平移 rigid link。", f"KEYOPT,{TRANSLATION_LINK_TYPE_ID},1,0 ! 只激活 UX、UY、UZ。", f"KEYOPT,{TRANSLATION_LINK_TYPE_ID},2,0 ! 使用直接消元而不使用罚刚度。", "ET,80,COMBIN14 ! 定义绕 X 弱转动测量弹簧。", "KEYOPT,80,2,4 ! COMBIN14 使用 ROTX 自由度。", "R,80,1 ! 弱弹簧刚度为 1 N·mm/rad。", "ET,81,COMBIN14 ! 定义绕 Y 弱转动测量弹簧。", "KEYOPT,81,2,5 ! COMBIN14 使用 ROTY 自由度。", "R,81,1 ! 弱弹簧刚度为 1 N·mm/rad。", "ET,82,COMBIN14 ! 定义绕 Z 弱转动测量弹簧。", "KEYOPT,82,2,6 ! COMBIN14 使用 ROTZ 自由度。", "R,82,1 ! 弱弹簧刚度为 1 N·mm/rad。", "CSYS,0 ! 恢复全局笛卡尔坐标。", "N,1,0,0,0 ! 定义固定 master 节点，单位 mm。", "N,2,800,-600,500 ! 定义非共线偏置刚臂末端辅助节点，单位 mm。", "N,3,800,-600,500 ! 定义与辅助节点严格共点的 slave 节点。", "N,4,800,-600,500 ! 定义三个弱转动弹簧的固定端节点。", f"TYPE,{RIGID_TYPE_ID} ! 选择偏置 rigid-beam 类型。", "EN,1,1,2 ! 建立 master 到辅助节点的六自由度刚臂。", f"TYPE,{TRANSLATION_LINK_TYPE_ID} ! 选择三平移 rigid-link 类型。", "EN,2,2,3 ! 建立辅助节点到 slave 的共点 UXYZ 直接消元连接。", "TYPE,80 ! 选择 ROTX 测量弹簧。", "REAL,80 ! 选择 ROTX 的 1 N·mm/rad 实常数。", "EN,80,3,4 ! 建立 slave 到固定端的 ROTX 弱弹簧。", "TYPE,81 ! 选择 ROTY 测量弹簧。", "REAL,81 ! 选择 ROTY 的 1 N·mm/rad 实常数。", "EN,81,3,4 ! 建立 slave 到固定端的 ROTY 弱弹簧。", "TYPE,82 ! 选择 ROTZ 测量弹簧。", "REAL,82 ! 选择 ROTZ 的 1 N·mm/rad 实常数。", "EN,82,3,4 ! 建立 slave 到固定端的 ROTZ 弱弹簧。", "D,1,ALL,0 ! 固定 master 全部有效自由度。", "D,4,ALL,0 ! 固定弱弹簧地基端全部有效自由度。", f"F,3,{load_label},{format(load_value, '.15g')} ! 在 slave 施加当前单位荷载。", "FINISH ! 完成微模型前处理。", "/SOLU ! 进入静力求解器。", "ANTYPE,STATIC ! 选择独立静力分析。", "NLGEOM,ON ! 启用与全桥一致的大转动运动学。", "NROPT,FULL ! 每次迭代更新完整切线。", "AUTOTS,OFF ! 关闭自动子步以禁止测试路径被静默改写。", "NSUBST,1,1,1 ! 用一个确定性子步施加当前单位荷载。", "OUTRES,ALL,ALL ! 保存全部结果供滑移、释放和反力复核。", "SOLVE ! 执行当前单位测试；prepare 生成器不会调用本文件。", "FINISH ! 结束求解阶段。", "/POST1 ! 进入结果后处理。", "SET,LAST ! 读取唯一收敛结果集。", "*GET,C10_UAX,NODE,2,U,X ! 读取辅助节点 X 位移，单位 mm。", "*GET,C10_UAY,NODE,2,U,Y ! 读取辅助节点 Y 位移，单位 mm。", "*GET,C10_UAZ,NODE,2,U,Z ! 读取辅助节点 Z 位移，单位 mm。", "*GET,C10_USX,NODE,3,U,X ! 读取 slave X 位移，单位 mm。", "*GET,C10_USY,NODE,3,U,Y ! 读取 slave Y 位移，单位 mm。", "*GET,C10_USZ,NODE,3,U,Z ! 读取 slave Z 位移，单位 mm。", "*GET,C10_RSX,NODE,3,ROT,X ! 读取 slave 绕 X 转角，单位 rad。", "*GET,C10_RSY,NODE,3,ROT,Y ! 读取 slave 绕 Y 转角，单位 rad。", "*GET,C10_RSZ,NODE,3,ROT,Z ! 读取 slave 绕 Z 转角，单位 rad。", "*GET,C10_MRFX,NODE,1,RF,FX ! 读取 master 的 X 向反力，单位 N。", "*GET,C10_MRFY,NODE,1,RF,FY ! 读取 master 的 Y 向反力，单位 N。", "*GET,C10_MRFZ,NODE,1,RF,FZ ! 读取 master 的 Z 向反力，单位 N。", "*GET,C10_MRMX,NODE,1,RF,MX ! 读取 master 的 X 向反力矩，单位 N·mm。", "*GET,C10_MRMY,NODE,1,RF,MY ! 读取 master 的 Y 向反力矩，单位 N·mm。", "*GET,C10_MRMZ,NODE,1,RF,MZ ! 读取 master 的 Z 向反力矩，单位 N·mm。", "*GET,C10_GRMX,NODE,4,RF,MX ! 读取 ROTX 弱弹簧固定端反力矩，单位 N·mm。", "*GET,C10_GRMY,NODE,4,RF,MY ! 读取 ROTY 弱弹簧固定端反力矩，单位 N·mm。", "*GET,C10_GRMZ,NODE,4,RF,MZ ! 读取 ROTZ 弱弹簧固定端反力矩，单位 N·mm。", f"/OUTPUT,{jobname}_results,txt ! 打开当前案例机器结果文件。", "*VWRITE,C10_UAX,C10_UAY,C10_UAZ,C10_USX,C10_USY,C10_USZ ! 输出辅助与 slave 位移向量。", "('AUX_U=',3(E24.16,','),'SLAVE_U=',3(E24.16,','))", "*VWRITE,C10_RSX,C10_RSY,C10_RSZ ! 输出 slave 三转角以验证释放路径。", "('SLAVE_ROT=',3(E24.16,','))", "*VWRITE,C10_MRFX,C10_MRFY,C10_MRFZ,C10_MRMX,C10_MRMY,C10_MRMZ ! 输出 master 六分量反力。", "('MASTER_RF_F=',3(E24.16,','),'MASTER_RF_M=',3(E24.16,','))", "*VWRITE,C10_GRMX,C10_GRMY,C10_GRMZ ! 单独输出弱弹簧反力矩，禁止混入刚接传力声明。", "('GROUND_SPRING_RF_M=',3(E24.16,','))", "/OUTPUT ! 恢复主输出。", "FINISH ! 完成单位测试后处理。", "/EXIT,NOSAVE ! 退出且不保留微模型数据库。"]  # 组装完整 UXYZ 荷载测试和机器结果合同。
    return "\n".join(lines) + "\n"  # 返回固定 LF 和末尾换行文本。


def make_legacy_chain_finite_rotation_test_input(axis_name: str, rotation_label: str, rotation_value_rad: float) -> str:  # 仅供复现旧 aux+TYPE73 有限转动微测盲区，正式计划绝不调用。
    """保留失败方案的历史 Rodrigues 输入生成能力，不得作为当前单 TYPE72 验收。"""  # 三个轴均使用 0.1 rad 且只用于回归对照。
    jobname = "c10fr_" + axis_name.lower()  # 派生短且唯一的 ASCII 作业名。
    rotation_values = {label: rotation_value_rad if label == rotation_label else 0.0 for label in ("ROTX", "ROTY", "ROTZ")}  # 为目标轴赋 0.1 rad 并把其余两轴固定为零。
    lines = ["! C10 UXYZ 直接消元连接 0.1 rad 有限转动解析测试；本文件由 prepare 生成但不自动执行。", "! 初始偏置向量为 (800,-600,500) mm，外部验收按 Rodrigues 公式计算目标位移。", "/CLEAR,START ! 清空未来独立微模型会话。", f"/FILNAME,{jobname} ! 设置当前案例唯一 ASCII 作业名。", "/PREP7 ! 进入前处理器定义可变形支撑梁与两段 MPC184。", "ET,1,BEAM188 ! 定义可变形支撑梁以满足刚性单元静力使用限制。", "KEYOPT,1,3,3 ! 采用三次插值稳定有限转动下的梁弯曲。", "MP,EX,1,210000 ! 设置钢材弹性模量 210000 MPa。", "MP,PRXY,1,0.3 ! 设置泊松比 0.3。", "SECTYPE,1,BEAM,RECT,C10FR ! 定义 10 mm 乘 10 mm 矩形测试截面。", "SECDATA,10,10 ! 写入矩形截面宽高，单位 mm。", f"ET,{RIGID_TYPE_ID},MPC184 ! 定义偏置 rigid beam。", f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择六自由度 rigid-beam 公式。", f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用直接消元实施刚臂约束。", f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留有限转动几何刚度。", f"ET,{TRANSLATION_LINK_TYPE_ID},MPC184 ! 定义共点三平移 rigid link。", f"KEYOPT,{TRANSLATION_LINK_TYPE_ID},1,0 ! 只激活 UX、UY、UZ。", f"KEYOPT,{TRANSLATION_LINK_TYPE_ID},2,0 ! 使用直接消元而不使用罚刚度。", "CSYS,0 ! 使用全局笛卡尔坐标定义解析几何。", "N,1,0,0,0 ! 定义规定转角的 master 节点。", "N,2,800,-600,500 ! 定义偏置刚臂辅助节点，单位 mm。", "N,3,800,-600,500 ! 定义与辅助节点共点的 slave 节点。", "N,4,800,400,500 ! 定义可变形梁固定端，距 slave 1000 mm。", "N,5,800,-600,1500 ! 定义 BEAM188 截面方向节点。", "TYPE,1 ! 选择可变形 BEAM188 类型。", "MAT,1 ! 选择测试钢材。", "SECNUM,1 ! 选择 10 mm 乘 10 mm 测试截面。", "EN,10,3,4,5 ! 建立 slave 到固定端的可变形支撑梁。", f"TYPE,{RIGID_TYPE_ID} ! 选择偏置 rigid-beam 类型。", "EN,1,1,2 ! 建立 master 到辅助节点的有限转动刚臂。", f"TYPE,{TRANSLATION_LINK_TYPE_ID} ! 选择共点三平移 rigid-link 类型。", "EN,2,2,3 ! 精确关联辅助节点与 slave 的三项平移。", "D,1,UX,0 ! 固定 master 的 X 平移。", "D,1,UY,0 ! 固定 master 的 Y 平移。", "D,1,UZ,0 ! 固定 master 的 Z 平移。", f"D,1,ROTX,{format(rotation_values['ROTX'], '.15g')} ! 规定 master 绕 X 转角，单位 rad。", f"D,1,ROTY,{format(rotation_values['ROTY'], '.15g')} ! 规定 master 绕 Y 转角，单位 rad。", f"D,1,ROTZ,{format(rotation_values['ROTZ'], '.15g')} ! 规定 master 绕 Z 转角，单位 rad。", "D,4,ALL,0 ! 固定可变形支撑梁远端全部自由度。", "FINISH ! 完成有限转动测试前处理。", "/SOLU ! 进入静力求解器。", "ANTYPE,STATIC ! 选择静力分析。", "NLGEOM,ON ! 启用有限转动几何非线性。", "NROPT,FULL ! 每次迭代更新完整切线。", "AUTOTS,OFF ! 关闭自动子步以保持确定的 20 段转动路径。", "NSUBST,20,20,20 ! 将 0.1 rad 规定转角分成 20 个固定子步。", "OUTRES,ALL,ALL ! 保存全部子步结果供路径复核。", "SOLVE ! 执行当前有限转动测试；prepare 生成器不会调用本文件。", "FINISH ! 结束求解阶段。", "/POST1 ! 进入结果后处理。", "SET,LAST ! 读取 0.1 rad 终态结果。", "*GET,C10_UAX,NODE,2,U,X ! 读取辅助节点 X 位移，单位 mm。", "*GET,C10_UAY,NODE,2,U,Y ! 读取辅助节点 Y 位移，单位 mm。", "*GET,C10_UAZ,NODE,2,U,Z ! 读取辅助节点 Z 位移，单位 mm。", "*GET,C10_USX,NODE,3,U,X ! 读取 slave X 位移，单位 mm。", "*GET,C10_USY,NODE,3,U,Y ! 读取 slave Y 位移，单位 mm。", "*GET,C10_USZ,NODE,3,U,Z ! 读取 slave Z 位移，单位 mm。", "*GET,C10_MRX,NODE,1,ROT,X ! 读取 master 绕 X 实际转角，单位 rad。", "*GET,C10_MRY,NODE,1,ROT,Y ! 读取 master 绕 Y 实际转角，单位 rad。", "*GET,C10_MRZ,NODE,1,ROT,Z ! 读取 master 绕 Z 实际转角，单位 rad。", f"/OUTPUT,{jobname}_results,txt ! 打开当前有限转动机器结果文件。", "*VWRITE,C10_UAX,C10_UAY,C10_UAZ,C10_USX,C10_USY,C10_USZ ! 输出辅助与 slave 位移。", "('AUX_U=',3(E24.16,','),'SLAVE_U=',3(E24.16,','))", "*VWRITE,C10_MRX,C10_MRY,C10_MRZ ! 输出 master 实际三转角。", "('MASTER_ROT=',3(E24.16,','))", "/OUTPUT ! 恢复主输出。", "FINISH ! 完成有限转动后处理。", "/EXIT,NOSAVE ! 退出且不保留微模型数据库。"]  # 组装有限转动验证模型和机器结果合同。
    return "\n".join(lines) + "\n"  # 返回固定 LF 和末尾换行文本。


def make_all_load_test_input(case_id: str, load_label: str, load_value: float) -> str:  # 输入 ALL 案例身份和单位荷载并返回六自由度刚梁测试。
    """验证单个 TYPE72 rigid beam 的六向传力、偏置力矩与零相对运动。"""  # 可变形支撑梁只满足刚性单元静力使用限制且在零位移下不分流。
    jobname = "c10all_" + case_id.lower()  # 派生短且唯一的 ASCII 作业名。
    lines = ["! C10 ALL 六自由度 rigid-beam 单位荷载测试；本文件由 prepare 生成但不自动执行。", "! 初始偏置向量为 (800,-600,500) mm，反力矩验收包含力对 master 的偏置矩。", "/CLEAR,START ! 清空未来独立微模型会话。", f"/FILNAME,{jobname} ! 设置当前案例唯一 ASCII 作业名。", "/PREP7 ! 进入前处理器定义刚梁和零变形支撑梁。", "ET,1,BEAM188 ! 定义可变形支撑梁以满足刚性单元静力使用限制。", "KEYOPT,1,3,3 ! 采用三次插值梁公式。", "MP,EX,1,210000 ! 设置钢材弹性模量 210000 MPa。", "MP,PRXY,1,0.3 ! 设置泊松比 0.3。", "SECTYPE,1,BEAM,RECT,C10ALL ! 定义 10 mm 乘 10 mm 矩形测试截面。", "SECDATA,10,10 ! 写入矩形截面宽高，单位 mm。", f"ET,{RIGID_TYPE_ID},MPC184 ! 定义 ALL 六自由度 rigid beam。", f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择六自由度 rigid-beam 公式。", f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用直接消元实施刚接。", f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留有限转动几何刚度。", "CSYS,0 ! 使用全局笛卡尔坐标定义偏置。", "N,1,0,0,0 ! 定义固定 master 节点。", "N,2,800,-600,500 ! 定义偏置 slave 节点。", "N,3,800,400,500 ! 定义可变形支撑梁固定端。", "N,4,800,-600,1500 ! 定义 BEAM188 截面方向节点。", "TYPE,1 ! 选择可变形 BEAM188 类型。", "MAT,1 ! 选择测试钢材。", "SECNUM,1 ! 选择测试矩形截面。", "EN,10,2,3,4 ! 建立 slave 到固定端的可变形支撑梁。", f"TYPE,{RIGID_TYPE_ID} ! 选择六自由度 rigid-beam 类型。", "EN,1,1,2 ! 建立 master 到 slave 的 ALL 刚接。", "D,1,ALL,0 ! 固定 master 全部有效自由度。", "D,3,ALL,0 ! 固定可变形支撑梁远端全部自由度。", f"F,2,{load_label},{format(load_value, '.15g')} ! 在 slave 施加当前单位荷载。", "FINISH ! 完成 ALL 微模型前处理。", "/SOLU ! 进入静力求解器。", "ANTYPE,STATIC ! 选择静力分析。", "NLGEOM,ON ! 启用与全桥一致的大转动运动学。", "NROPT,FULL ! 每次迭代更新完整切线。", "AUTOTS,OFF ! 关闭自动子步以保持确定的单位荷载路径。", "NSUBST,1,1,1 ! 用一个子步施加单位荷载。", "OUTRES,ALL,ALL ! 保存全部结果供六自由度传力复核。", "SOLVE ! 执行当前 ALL 测试；prepare 生成器不会调用本文件。", "FINISH ! 结束求解阶段。", "/POST1 ! 进入结果后处理。", "SET,LAST ! 读取唯一收敛结果集。", "*GET,C10_USX,NODE,2,U,X ! 读取 slave X 位移，单位 mm。", "*GET,C10_USY,NODE,2,U,Y ! 读取 slave Y 位移，单位 mm。", "*GET,C10_USZ,NODE,2,U,Z ! 读取 slave Z 位移，单位 mm。", "*GET,C10_RSX,NODE,2,ROT,X ! 读取 slave 绕 X 转角，单位 rad。", "*GET,C10_RSY,NODE,2,ROT,Y ! 读取 slave 绕 Y 转角，单位 rad。", "*GET,C10_RSZ,NODE,2,ROT,Z ! 读取 slave 绕 Z 转角，单位 rad。", "*GET,C10_MRFX,NODE,1,RF,FX ! 读取 master 的 X 向反力，单位 N。", "*GET,C10_MRFY,NODE,1,RF,FY ! 读取 master 的 Y 向反力，单位 N。", "*GET,C10_MRFZ,NODE,1,RF,FZ ! 读取 master 的 Z 向反力，单位 N。", "*GET,C10_MRMX,NODE,1,RF,MX ! 读取 master 的 X 向反力矩，单位 N·mm。", "*GET,C10_MRMY,NODE,1,RF,MY ! 读取 master 的 Y 向反力矩，单位 N·mm。", "*GET,C10_MRMZ,NODE,1,RF,MZ ! 读取 master 的 Z 向反力矩，单位 N·mm。", "*GET,C10_GRFX,NODE,3,RF,FX ! 读取支撑梁固定端 X 向反力，单位 N。", "*GET,C10_GRFY,NODE,3,RF,FY ! 读取支撑梁固定端 Y 向反力，单位 N。", "*GET,C10_GRFZ,NODE,3,RF,FZ ! 读取支撑梁固定端 Z 向反力，单位 N。", "*GET,C10_GRMX,NODE,3,RF,MX ! 读取支撑梁固定端 X 向反力矩，单位 N·mm。", "*GET,C10_GRMY,NODE,3,RF,MY ! 读取支撑梁固定端 Y 向反力矩，单位 N·mm。", "*GET,C10_GRMZ,NODE,3,RF,MZ ! 读取支撑梁固定端 Z 向反力矩，单位 N·mm。", f"/OUTPUT,{jobname}_results,txt ! 打开当前 ALL 案例机器结果文件。", "*VWRITE,C10_USX,C10_USY,C10_USZ,C10_RSX,C10_RSY,C10_RSZ ! 输出 slave 六自由度运动。", "('SLAVE_U=',3(E24.16,','),'SLAVE_ROT=',3(E24.16,','))", "*VWRITE,C10_MRFX,C10_MRFY,C10_MRFZ,C10_MRMX,C10_MRMY,C10_MRMZ ! 输出 master 六分量反力。", "('MASTER_RF_F=',3(E24.16,','),'MASTER_RF_M=',3(E24.16,','))", "*VWRITE,C10_GRFX,C10_GRFY,C10_GRFZ,C10_GRMX,C10_GRMY,C10_GRMZ ! 输出可变形支撑梁固定端六分量反力。", "('GROUND_RF_F=',3(E24.16,','),'GROUND_RF_M=',3(E24.16,','))", "/OUTPUT ! 恢复主输出。", "FINISH ! 完成 ALL 后处理。", "/EXIT,NOSAVE ! 退出且不保留微模型数据库。"]  # 组装完整 ALL 荷载测试和机器结果合同。
    return "\n".join(lines) + "\n"  # 返回固定 LF 和末尾换行文本。


def make_single_mpc_uxyz_load_test_input(case_id: str, load_label: str, load_value: float) -> str:  # 输入平移载荷案例并返回生产拓扑单 TYPE72 装配秩微模型。
    """用柔性 BEAM188 master、单 TYPE72、双侧预拉 LINK180 slave 和可选平移 MASS21 复现生产自由度族。"""  # 返回 LF 文本且不允许节点力矩。
    require(load_label in {"FX", "FY", "FZ"}, f"UXYZ 生产拓扑微测禁止非平移载荷：{load_label}")  # 原索从节点不存在物理力矩共轭自由度。
    jobname = "c10sg_" + case_id.lower()  # 派生短且唯一的 ASCII 微模型作业名。
    require(len(jobname) <= 32, f"UXYZ 单刚臂测试 jobname 过长：{jobname}")  # 满足 MAPDL 32 字符限制。
    lines = [  # 初始化生产拓扑微模型 APDL 行表。
        "! C10 UXYZ 单 TYPE72 生产拓扑装配秩测试；本文件由 prepare 生成但不自动执行。",  # 说明案例目的和执行边界。
        "! 单位为 N、mm、N·mm、tonne、s；双侧 LINK180 初应力相等并在初始位置自平衡。",  # 固定单位制与预应力语义。
        "/CLEAR,START ! 清空未来独立微模型会话。",  # 防止工作数据库污染微测。
        f"/FILNAME,{jobname} ! 设置当前案例唯一 ASCII 作业名。",  # 固定结果前缀。
        "/PREP7 ! 进入前处理器定义生产同类自由度拓扑。",  # 开始建模。
        "ET,1,BEAM188 ! 定义承载 master 的可变形空间梁。",  # master 必须由真实柔性构件支承。
        "KEYOPT,1,3,3 ! 采用三次插值以稳定几何非线性梁弯曲。",  # 与整模 TYPE70 的插值阶次一致。
        "MP,EX,1,210000 ! 设置梁钢弹性模量为 210000 N/mm2。",  # 数值来源为常用结构钢弹性模量。
        "MP,PRXY,1,0.3 ! 设置梁钢泊松比为 0.3。",  # 固定各向同性材料参数。
        "SECTYPE,1,BEAM,RECT,C10SG ! 定义 100 mm 乘 100 mm 矩形测试梁截面。",  # 提供有限且非刚性的 master 支承。
        "SECDATA,100,100 ! 写入测试梁截面宽高，单位 mm。",  # 两个字面值均为截面尺寸。
        "ET,2,LINK180 ! 定义与生产原索相同的三平移拉压杆自由度族。",  # slave 两侧只连接索单元。
        "MP,EX,2,160000 ! 设置测试索等效弹性模量为 160000 N/mm2。",  # 数值只用于稳定微测而不进入生产模型。
        "MP,PRXY,2,0.3 ! 设置测试索材料泊松比为 0.3。",  # LINK180 只使用所需弹性参数。
        "SECTYPE,2,LINK ! 定义测试索杆截面。",  # 启用 LINK180 截面面积输入。
        "SECDATA,1393.668228093791 ! 使用与代表性 50 mm 级索相当的 1393.668 mm2 面积。",  # 面积用于形成约 641 kN 初拉力。
        "ET,3,MASS21 ! 定义仅用于复现生产节点类型参与的集中质量。",  # 静力中质量不贡献刚度。
        "KEYOPT,3,3,2 ! MASS21 只激活 UX、UY、UZ 三个平移质量。",  # 明确禁止转动惯量消费者。
        "R,3,0.001 ! 设置 0.001 tonne 的有限测试质量。",  # 数值用于自由度族复现而不影响静力平衡。
        f"ET,{RIGID_TYPE_ID},MPC184 ! 定义待验收的单个偏置 rigid beam。",  # 只允许一个约束元素。
        f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择六自由度 rigid-beam 公式。",  # 提供有限转动偏心平移关系。
        f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用 direct elimination 精确施加运动学。",  # 禁止罚刚度和拉格朗日乘子。
        f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留几何应力刚度以覆盖预应力模态需求。",  # 不以关闭几何项掩盖秩问题。
        "CSYS,0 ! 使用全局笛卡尔坐标定义非共线偏置。",  # 固定坐标语义。
        "N,1,0,0,0 ! 定义可变形梁端的 master 节点。",  # master 位于原点。
        "N,2,800,-600,500 ! 定义纯平移索 slave 节点。",  # 偏置向量固定为 800、-600、500 mm。
        "N,3,-200,-600,500 ! 定义 slave 左侧索段固定端。",  # 左索初始长度为 1000 mm。
        "N,4,1800,-600,500 ! 定义 slave 右侧索段固定端。",  # 右索初始长度为 1000 mm。
        "N,10,-1000,0,0 ! 定义 master 支承梁固定端。",  # 梁初始长度为 1000 mm。
        "N,11,0,0,1000 ! 定义 BEAM188 截面方向节点。",  # 方向节点不与梁轴共线。
        "TYPE,1 ! 选择可变形 BEAM188。",  # 后续 EN 使用梁类型。
        "MAT,1 ! 选择测试梁材料。",  # 后续梁使用 210000 MPa 材料。
        "SECNUM,1 ! 选择测试梁矩形截面。",  # 后续梁使用 100 mm 方形截面。
        "EN,10,10,1,11 ! 建立固定端到 master 的可变形梁。",  # 复现柔性 master 邻接。
        "TYPE,2 ! 选择 LINK180 索类型。",  # 后续两个元素为纯平移索段。
        "MAT,2 ! 选择测试索材料。",  # 后续索使用 160000 MPa 材料。
        "SECNUM,2 ! 选择测试索截面。",  # 后续索使用 1393.668 mm2 面积。
        "EN,20,3,2 ! 建立左固定端到 slave 的 LINK180。",  # 形成第一根预拉索段。
        "EN,21,2,4 ! 建立 slave 到右固定端的 LINK180。",  # 形成第二根对称预拉索段。
        "TYPE,3 ! 选择仅平移 MASS21。",  # 后续单节点元素复现部分生产节点的质量参与。
        "REAL,3 ! 选择 0.001 tonne 测试质量。",  # MASS21 使用定义好的实常数。
        "EN,30,2 ! 在 slave 建立仅三平移集中质量。",  # 明确不存在转动质量。
        f"TYPE,{RIGID_TYPE_ID} ! 选择单 TYPE72 rigid beam。",  # 后续只建立一条约束。
        "EN,1,1,2 ! 直接连接 master 与原 slave，禁止 aux 和第二 MPC。",  # 这是本次拓扑修复的核心。
        "INISTATE,SET,DTYP,S ! 选择初始应力数据类型。",  # 为两侧 LINK180 提供生产同量级初拉力。
        "INISTATE,SET,CSYS,-2 ! 在单元坐标系定义 LINK180 轴向初应力。",  # 轴向应力符号与索局部轴一致。
        "INISTATE,SET,NODE,0 ! 按单元而不是节点定义初始状态。",  # 固定输入实体语义。
        "INISTATE,SET,MATL,0 ! 使用当前单元材料坐标解释初始应力。",  # 禁止额外材料映射。
        "INISTATE,DEFINE,20,,,,460 ! 给左索施加 460 N/mm2 初拉应力。",  # 与失败点约 460 至 491 N/mm2 同量级。
        "INISTATE,DEFINE,21,,,,460 ! 给右索施加相同初拉应力以保持零合力。",  # 对称初态避免虚构不平衡载荷。
        "D,3,ALL,0 ! 固定左索远端全部有效平移自由度。",  # 提供第一侧锚固。
        "D,4,ALL,0 ! 固定右索远端全部有效平移自由度。",  # 提供第二侧锚固。
        "D,10,ALL,0 ! 固定 master 支承梁远端六自由度。",  # 提供柔性 master 的物理边界。
        f"F,2,{load_label},{format(load_value, '.15g')} ! 在纯平移 slave 施加当前单位力。",  # 只允许 FX、FY 或 FZ。
        "FINISH ! 完成生产拓扑微模型前处理。",  # 离开建模阶段。
        "/SOLU ! 进入静力求解器。",  # 开始数值装配验证。
        "ANTYPE,STATIC ! 选择独立静力分析。",  # 不混入模态步骤。
        "NLGEOM,ON ! 启用与全桥一致的大转动运动学。",  # 让 MPC184 更新非线性切线。
        "PSTRES,ON ! 保留初应力对当前切线的贡献。",  # 覆盖预应力连接装配路径。
        "NROPT,FULL ! 每次迭代更新完整切线。",  # 触发依赖自由度重组风险检测。
        "AUTOTS,OFF ! 关闭自动子步，避免测试路径被静默改写。",  # 固定可复现实验路径。
        "NSUBST,5,5,5 ! 用五个固定子步施加单位力。",  # 多次重组用于检查方程数恒定。
        "CNVTOL,F,,1.0e-8,2,1.0 ! 将 VALUE 留空，固定 1e-8 力容限、L2 范数和 1 N 最小参考值。",  # 微测外部平衡门为 1e-6 N，因此用更严的求解残差避免把收敛截断误差混入连接判断。
        "CNVTOL,M,,1.0e-8,2,1.0 ! 将 VALUE 留空，固定 1e-8 力矩容限、L2 范数和 1 N·mm 最小参考值。",  # 微测专用严容限只验证离散方程，不改变全桥正式收敛合同。
        "CNVTOL,U,,0.05,0 ! 将 VALUE 留空，固定 5% 平移修正容限和逐自由度无穷范数。",  # 显式控制平移增量而不把 0.05 误写入参考值字段。
        "CNVTOL,ROT,,0.05,0 ! 将 VALUE 留空，固定 5% 转角修正容限和逐自由度无穷范数。",  # 显式控制 master 转动增量并覆盖默认自动设置。
        "OUTRES,ALL,ALL ! 保存全部子步结果供运动学与秩复核。",  # 结果覆盖每个重组状态。
        "SOLVE ! 执行当前生产拓扑微测；prepare 本身不调用本文件。",  # 求解动作只在后续执行器中发生。
        "FINISH ! 结束求解阶段。",  # 切换到后处理。
        "/POST1 ! 进入结果后处理器。",  # 读取收敛终态。
        "SET,LAST ! 读取第五个固定子步终态。",  # 只输出最终平衡状态。
        "*GET,C10_UMX,NODE,1,U,X ! 读取 master X 位移，单位 mm。",  # 为刚体偏置解析验收提供平移。
        "*GET,C10_UMY,NODE,1,U,Y ! 读取 master Y 位移，单位 mm。",  # 为刚体偏置解析验收提供平移。
        "*GET,C10_UMZ,NODE,1,U,Z ! 读取 master Z 位移，单位 mm。",  # 为刚体偏置解析验收提供平移。
        "*GET,C10_RMX,NODE,1,ROT,X ! 读取 master 绕 X 转角，单位 rad。",  # 为 Rodrigues 运动学验收提供转角。
        "*GET,C10_RMY,NODE,1,ROT,Y ! 读取 master 绕 Y 转角，单位 rad。",  # 为 Rodrigues 运动学验收提供转角。
        "*GET,C10_RMZ,NODE,1,ROT,Z ! 读取 master 绕 Z 转角，单位 rad。",  # 为 Rodrigues 运动学验收提供转角。
        "*GET,C10_USX,NODE,2,U,X ! 读取 slave X 位移，单位 mm。",  # 检查偏心平移关系。
        "*GET,C10_USY,NODE,2,U,Y ! 读取 slave Y 位移，单位 mm。",  # 检查偏心平移关系。
        "*GET,C10_USZ,NODE,2,U,Z ! 读取 slave Z 位移，单位 mm。",  # 检查偏心平移关系。
        "*GET,C10_RSX,NODE,2,ROT,X ! 读取 solver-only slave 绕 X 代数转角。",  # 该值没有外部物理消费者。
        "*GET,C10_RSY,NODE,2,ROT,Y ! 读取 solver-only slave 绕 Y 代数转角。",  # 该值没有外部物理消费者。
        "*GET,C10_RSZ,NODE,2,ROT,Z ! 读取 solver-only slave 绕 Z 代数转角。",  # 该值没有外部物理消费者。
        "*GET,C10_R3X,NODE,3,RF,FX ! 读取左索锚点 X 反力。",  # 用于全局力平衡。
        "*GET,C10_R3Y,NODE,3,RF,FY ! 读取左索锚点 Y 反力。",  # 用于全局力平衡。
        "*GET,C10_R3Z,NODE,3,RF,FZ ! 读取左索锚点 Z 反力。",  # 用于全局力平衡。
        "*GET,C10_R4X,NODE,4,RF,FX ! 读取右索锚点 X 反力。",  # 用于全局力平衡。
        "*GET,C10_R4Y,NODE,4,RF,FY ! 读取右索锚点 Y 反力。",  # 用于全局力平衡。
        "*GET,C10_R4Z,NODE,4,RF,FZ ! 读取右索锚点 Z 反力。",  # 用于全局力平衡。
        "*GET,C10_R10X,NODE,10,RF,FX ! 读取梁支座 X 反力。",  # 用于全局力平衡。
        "*GET,C10_R10Y,NODE,10,RF,FY ! 读取梁支座 Y 反力。",  # 用于全局力平衡。
        "*GET,C10_R10Z,NODE,10,RF,FZ ! 读取梁支座 Z 反力。",  # 用于全局力平衡。
        "C10_GFX=C10_R3X+C10_R4X+C10_R10X ! 汇总三个支承的 X 反力。",  # 形成机器可读平衡向量。
        "C10_GFY=C10_R3Y+C10_R4Y+C10_R10Y ! 汇总三个支承的 Y 反力。",  # 形成机器可读平衡向量。
        "C10_GFZ=C10_R3Z+C10_R4Z+C10_R10Z ! 汇总三个支承的 Z 反力。",  # 形成机器可读平衡向量。
        f"/OUTPUT,{jobname}_results,txt ! 打开当前案例机器结果文件。",  # 固定结果文件名。
        "*VWRITE,C10_UMX,C10_UMY,C10_UMZ,C10_RMX,C10_RMY,C10_RMZ ! 输出 master 六分量运动。",  # 下一行必须紧邻 Fortran 格式。
        "('MASTER_U=',3(E24.16,','),'MASTER_ROT=',3(E24.16,','))",  # APDL 裸格式行不允许行尾注释。
        "*VWRITE,C10_USX,C10_USY,C10_USZ,C10_RSX,C10_RSY,C10_RSZ ! 输出 slave 六分量代数运动。",  # 下一行必须紧邻 Fortran 格式。
        "('SLAVE_U=',3(E24.16,','),'SLAVE_ROT=',3(E24.16,','))",  # APDL 裸格式行不允许行尾注释。
        "*VWRITE,C10_GFX,C10_GFY,C10_GFZ ! 输出全部支承反力和。",  # 下一行必须紧邻 Fortran 格式。
        "('GROUND_RF_F=',3(E24.16,','))",  # APDL 裸格式行不允许行尾注释。
        "/OUTPUT ! 恢复 MAPDL 主输出。",  # 关闭结果重定向。
        "FINISH ! 完成生产拓扑微测后处理。",  # 返回开始层。
        "/EXIT,NOSAVE ! 退出且不保留微模型数据库。",  # 防止跨案例数据库污染。
    ]  # 结束生产拓扑微模型 APDL 行表。
    return "\n".join(lines) + "\n"  # 返回固定 LF 和唯一末尾换行。


def make_single_mpc_finite_rotation_test_input(axis_name: str, rotation_label: str, rotation_value_rad: float) -> str:  # 输入转轴和目标转角并返回带独立转动方程的单 TYPE72 有限转动测试。
    """用受矩 COMBIN14 master、单 TYPE72 和双侧纯平移 LINK180 验证约 0.1 rad Rodrigues 偏心平移。"""  # 返回 LF 文本且禁止辅助节点或第二层 MPC。
    jobname = "c10sr_" + axis_name.lower()  # 派生短且唯一的 ASCII 作业名。
    require(len(jobname) <= 32, f"单 TYPE72 有限转动测试 jobname 过长：{jobname}")  # 满足 MAPDL 作业名限制。
    require(rotation_label in {"ROTX", "ROTY", "ROTZ"}, f"有限转动标签无效：{rotation_label}")  # 只允许三个全局转轴，拒绝拼写或局部坐标歧义。
    spring_axis_keyopt = {"ROTX": 4, "ROTY": 5, "ROTZ": 6}[rotation_label]  # 将目标转轴映射到 COMBIN14 的三个转动自由度 KEYOPT(2) 编码。
    moment_label = {"ROTX": "MX", "ROTY": "MY", "ROTZ": "MZ"}[rotation_label]  # 将目标转角映射到施加在 master 的共轭节点力矩标签。
    spring_stiffness_n_mm_per_rad = 10.0  # 采用 10 N·mm/rad 转动弹簧，使 1 N·mm 级力矩产生约 0.1 rad 且保持良好条件数。
    applied_moment_n_mm = spring_stiffness_n_mm_per_rad * rotation_value_rad  # 按线性弹簧目标计算当前轴力矩；极软索仅造成可量化微小修正。
    fixed_rotation_lines = [f"D,1,{label},0 ! 固定非目标 master 转角 {label}。" for label in ("ROTX", "ROTY", "ROTZ") if label != rotation_label]  # 仅释放目标转轴，确保它作为真实独立方程参与每个非线性子步。
    lines = [  # 初始化有限转动微模型 APDL 行表。
        "! C10 单 TYPE72 约 0.1 rad 受矩有限转动解析测试；本文件由 prepare 生成但不自动执行。",  # 说明案例目的和执行边界。
        "! slave 只连接两根极软 LINK180 与一个仅平移 MASS21，禁止任何物理转角消费者。",  # 固定生产等价自由度族。
        "/CLEAR,START ! 清空未来独立微模型会话。",  # 防止数据库污染。
        f"/FILNAME,{jobname} ! 设置当前案例唯一 ASCII 作业名。",  # 固定输出前缀。
        "/PREP7 ! 进入前处理器定义单刚臂有限转动模型。",  # 开始建模。
        "ET,2,LINK180 ! 定义仅三平移自由度的极软测试索。",  # 提供刚性单元要求的可变形邻接。
        "MP,EX,2,1 ! 设置极软索弹性模量为 1 N/mm2。",  # 极软值降低规定转动反力但保持有限刚度。
        "MP,PRXY,2,0.3 ! 设置测试索泊松比为 0.3。",  # 固定材料参数。
        "SECTYPE,2,LINK ! 定义极软测试索截面。",  # 启用面积输入。
        "SECDATA,0.000001 ! 设置 1e-6 mm2 极小面积。",  # 只满足可变形元素限制而不干扰运动学。
        "ET,3,MASS21 ! 定义仅三平移集中质量。",  # 复现生产 slave 的可选质量自由度族。
        "KEYOPT,3,3,2 ! MASS21 只激活 UX、UY、UZ。",  # 禁止转动惯量。
        "R,3,0.001 ! 设置 0.001 tonne 测试质量。",  # 静力中不贡献刚度。
        "ET,4,COMBIN14 ! 定义 master 到地基的单轴转动弹簧。",  # 为目标 master 转角提供真实独立刚度方程而非规定自由度。
        f"KEYOPT,4,2,{spring_axis_keyopt} ! 将 COMBIN14 激活在目标转轴 {rotation_label}。",  # KEYOPT 值 4、5、6 分别对应 ROTX、ROTY、ROTZ。
        f"R,4,{format(spring_stiffness_n_mm_per_rad, '.15g')} ! 设置目标轴转动刚度为 {spring_stiffness_n_mm_per_rad:.1f} N·mm/rad。",  # 由目标转角和施加力矩共同确定约 0.1 rad 响应。
        f"ET,{RIGID_TYPE_ID},MPC184 ! 定义单个偏置 rigid beam。",  # 只允许一条约束元素。
        f"KEYOPT,{RIGID_TYPE_ID},1,1 ! 选择六自由度 rigid-beam 公式。",  # 提供有限转动刚体关系。
        f"KEYOPT,{RIGID_TYPE_ID},2,0 ! 使用 direct elimination。",  # 禁止罚函数或拉格朗日乘子。
        f"KEYOPT,{RIGID_TYPE_ID},5,0 ! 保留几何应力刚度。",  # 满足未来预应力模态要求。
        "CSYS,0 ! 使用全局笛卡尔坐标。",  # 固定坐标语义。
        "N,1,0,0,0 ! 定义受矩且目标转轴自由的 master。",  # master 位于原点并由转动弹簧支承。
        "N,2,800,-600,500 ! 定义纯平移索 slave。",  # 固定 Rodrigues 偏置向量。
        "N,3,-200,-600,500 ! 定义左侧极软索固定端。",  # 左索长度为 1000 mm。
        "N,4,1800,-600,500 ! 定义右侧极软索固定端。",  # 右索长度为 1000 mm。
        "N,5,0,0,0 ! 定义与 master 共点的转动弹簧地基节点。",  # 共点两节点仅通过目标转轴 COMBIN14 连接。
        "TYPE,2 ! 选择极软 LINK180。",  # 后续建两根可变形索。
        "MAT,2 ! 选择极软材料。",  # 后续使用 1 MPa 弹性模量。
        "SECNUM,2 ! 选择 1e-6 mm2 截面。",  # 后续索只提供数值合法性。
        "EN,20,3,2 ! 建立左侧极软 LINK180。",  # 第一根纯平移邻接。
        "EN,21,2,4 ! 建立右侧极软 LINK180。",  # 第二根纯平移邻接。
        "TYPE,3 ! 选择仅平移 MASS21。",  # 后续复现质量自由度族。
        "REAL,3 ! 选择 0.001 tonne 实常数。",  # 固定质量值。
        "EN,30,2 ! 在 slave 建立仅平移质量。",  # 不增加转动惯量。
        f"TYPE,{RIGID_TYPE_ID} ! 选择单 TYPE72。",  # 后续只建立一个 MPC184。
        "EN,1,1,2 ! 直接连接 master 与原 slave。",  # 删除旧 aux+TYPE73 串联链。
        "TYPE,4 ! 选择目标轴 COMBIN14 转动弹簧。",  # 后续只建立一个目标转轴弹簧。
        "REAL,4 ! 选择 10 N·mm/rad 转动刚度实常数。",  # 将已定义刚度分配给当前弹簧。
        "EN,40,1,5 ! 建立 master 到共点地基的目标轴转动弹簧。",  # 使目标转角保留为一个可求解独立方程。
        "D,1,UX,0 ! 固定 master X 平移。",  # 规定纯转动运动。
        "D,1,UY,0 ! 固定 master Y 平移。",  # 规定纯转动运动。
        "D,1,UZ,0 ! 固定 master Z 平移。",  # 规定纯转动运动。
        *fixed_rotation_lines,  # 插入两个非目标零转角边界；目标转轴不得出现 D 约束。
        "D,3,ALL,0 ! 固定左侧极软索远端。",  # 提供第一根可变形元素边界。
        "D,4,ALL,0 ! 固定右侧极软索远端。",  # 提供第二根可变形元素边界。
        "D,5,ALL,0 ! 固定转动弹簧地基端全部有效自由度。",  # 为目标转轴弹簧提供零转角参考端。
        f"F,1,{moment_label},{format(applied_moment_n_mm, '.15g')} ! 在 master 施加 {applied_moment_n_mm:.6g} N·mm 目标轴力矩。",  # 与 10 N·mm/rad 弹簧配对产生约 0.1 rad 有限转动。
        "FINISH ! 完成有限转动模型前处理。",  # 离开建模阶段。
        "/SOLU ! 进入静力求解器。",  # 开始规定转动求解。
        "ANTYPE,STATIC ! 选择静力分析。",  # 不混入模态。
        "NLGEOM,ON ! 启用大转动运动学。",  # 让 TYPE72 执行有限转动更新。
        "NROPT,FULL ! 每次迭代更新完整切线。",  # 检查直接消元重组稳定性。
        "AUTOTS,OFF ! 关闭自动子步。",  # 固定转动路径。
        "NSUBST,20,20,20 ! 将 0.1 rad 分成二十个固定子步。",  # 提供平滑且可重复的有限转动路径。
        "CNVTOL,F,,0.005,2,1.0 ! 将 VALUE 留空，固定 0.5% 力容限、L2 范数和 1 N 最小参考值。",  # 按官方字段顺序禁止力收敛标准自动放宽。
        "CNVTOL,M,,0.005,2,1.0 ! 将 VALUE 留空，固定 0.5% 力矩容限、L2 范数和 1 N·mm 最小参考值。",  # 显式控制目标独立转动方程的力矩残差。
        "CNVTOL,U,,0.05,0 ! 将 VALUE 留空，固定 5% 平移修正容限和逐自由度无穷范数。",  # 显式控制偏置 slave 的大位移更新。
        "CNVTOL,ROT,,0.05,0 ! 将 VALUE 留空，固定 5% 转角修正容限和逐自由度无穷范数。",  # 显式控制约 0.1 rad master 转角更新。
        "OUTRES,ALL,ALL ! 保存全部二十个子步结果。",  # 支持路径和方程数复核。
        "SOLVE ! 执行当前有限转动测试；prepare 本身不调用本文件。",  # 求解由后续执行器负责。
        "FINISH ! 结束求解阶段。",  # 切换到后处理。
        "/POST1 ! 进入结果后处理器。",  # 读取终态。
        "SET,LAST ! 读取接近 0.1 rad 的受矩终态结果。",  # 固定最终收敛结果集并由外部验收实际转角。
        "*GET,C10_UMX,NODE,1,U,X ! 读取 master X 位移。",  # Rodrigues 目标需要 master 平移。
        "*GET,C10_UMY,NODE,1,U,Y ! 读取 master Y 位移。",  # Rodrigues 目标需要 master 平移。
        "*GET,C10_UMZ,NODE,1,U,Z ! 读取 master Z 位移。",  # Rodrigues 目标需要 master 平移。
        "*GET,C10_RMX,NODE,1,ROT,X ! 读取 master 绕 X 实际转角。",  # Rodrigues 目标需要旋转向量。
        "*GET,C10_RMY,NODE,1,ROT,Y ! 读取 master 绕 Y 实际转角。",  # Rodrigues 目标需要旋转向量。
        "*GET,C10_RMZ,NODE,1,ROT,Z ! 读取 master 绕 Z 实际转角。",  # Rodrigues 目标需要旋转向量。
        "*GET,C10_USX,NODE,2,U,X ! 读取 slave X 位移。",  # 与解析刚体位移比较。
        "*GET,C10_USY,NODE,2,U,Y ! 读取 slave Y 位移。",  # 与解析刚体位移比较。
        "*GET,C10_USZ,NODE,2,U,Z ! 读取 slave Z 位移。",  # 与解析刚体位移比较。
        "*GET,C10_RSX,NODE,2,ROT,X ! 读取 solver-only slave 绕 X 代数转角。",  # 验证直接消元关系但不赋予物理含义。
        "*GET,C10_RSY,NODE,2,ROT,Y ! 读取 solver-only slave 绕 Y 代数转角。",  # 验证直接消元关系但不赋予物理含义。
        "*GET,C10_RSZ,NODE,2,ROT,Z ! 读取 solver-only slave 绕 Z 代数转角。",  # 验证直接消元关系但不赋予物理含义。
        f"/OUTPUT,{jobname}_results,txt ! 打开当前有限转动机器结果文件。",  # 固定输出文件名。
        "*VWRITE,C10_UMX,C10_UMY,C10_UMZ,C10_RMX,C10_RMY,C10_RMZ ! 输出 master 六分量运动。",  # 下一行必须紧邻 Fortran 格式。
        "('MASTER_U=',3(E24.16,','),'MASTER_ROT=',3(E24.16,','))",  # APDL 裸格式行不允许行尾注释。
        "*VWRITE,C10_USX,C10_USY,C10_USZ,C10_RSX,C10_RSY,C10_RSZ ! 输出 slave 六分量代数运动。",  # 下一行必须紧邻 Fortran 格式。
        "('SLAVE_U=',3(E24.16,','),'SLAVE_ROT=',3(E24.16,','))",  # APDL 裸格式行不允许行尾注释。
        "/OUTPUT ! 恢复 MAPDL 主输出。",  # 关闭结果重定向。
        "FINISH ! 完成单刚臂有限转动后处理。",  # 返回开始层。
        "/EXIT,NOSAVE ! 退出且不保留微模型数据库。",  # 防止跨案例数据库污染。
    ]  # 结束有限转动微模型 APDL 行表。
    return "\n".join(lines) + "\n"  # 返回固定 LF 和唯一末尾换行。


def build_unit_test_plan(unit_test_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:  # 输入目标目录并生成 12 份未执行微模型和计划/结果摘要。
    """三个生产拓扑 UXYZ 平移载荷、三个单刚臂有限转动和六个 ALL 荷载共同构成硬门禁。"""  # 返回计划和未执行结果对象。
    cases: list[dict[str, Any]] = []  # 初始化十二个案例计划。
    for load_name, load_label, load_value, load_unit in TRANSLATION_LOAD_CASES:  # 生成三个 UXYZ 生产拓扑平移载荷案例。
        case_id = f"UXYZ-{load_name}"  # 形成稳定 UXYZ 案例身份。
        file_name = f"c10_uxyz_{load_name.lower()}.inp"  # 形成安全 ASCII 输入文件名。
        input_text = make_single_mpc_uxyz_load_test_input(load_name, load_label, load_value)  # 生成当前柔性 master—单刚臂—双索 slave APDL 模板。
        write_new_text(unit_test_dir / file_name, input_text)  # 以不可覆盖模式写当前案例。
        cases.append({"case_id": case_id, "case_family": "UXYZ_PRODUCTION_TOPOLOGY_TRANSLATION_LOAD", "load_label": load_label, "load_value": load_value, "load_unit": load_unit, "offset_vector_mm": [800.0, -600.0, 500.0], "input_file": f"unit_tests/{file_name}", "input_sha256": sha256_bytes(input_text.encode("utf-8")), "future_result_file": f"unit_tests/c10sg_{load_name.lower()}_results.txt", "status": "PREPARED_NOT_STARTED"})  # 保存生产同类 UXYZ 装配秩与平移传力合同。
    for axis_name, rotation_label, rotation_value_rad in FINITE_ROTATION_CASES:  # 生成三个 0.1 rad 有限转动案例。
        case_id = f"FINITE-{axis_name}"  # 形成稳定有限转动案例身份。
        file_name = f"c10_finite_{axis_name.lower()}.inp"  # 形成安全 ASCII 输入文件名。
        input_text = make_single_mpc_finite_rotation_test_input(axis_name, rotation_label, rotation_value_rad)  # 生成不含辅助节点且 slave 只有平移消费者的有限转动模板。
        write_new_text(unit_test_dir / file_name, input_text)  # 以不可覆盖模式写当前案例。
        cases.append({"case_id": case_id, "case_family": "UXYZ_SINGLE_MPC_FINITE_ROTATION_KINEMATICS", "rotation_label": rotation_label, "rotation_value_rad": rotation_value_rad, "offset_vector_mm": [800.0, -600.0, 500.0], "input_file": f"unit_tests/{file_name}", "input_sha256": sha256_bytes(input_text.encode("utf-8")), "future_result_file": f"unit_tests/c10sr_{axis_name.lower()}_results.txt", "status": "PREPARED_NOT_STARTED"})  # 保存单 TYPE72 Rodrigues 解析验收所需几何和转角。
    for load_name, load_label, load_value, load_unit in UNIT_LOAD_CASES:  # 生成六个 ALL rigid-beam 单位荷载案例。
        case_id = f"ALL-{load_name}"  # 形成稳定 ALL 案例身份。
        file_name = f"c10_all_{load_name.lower()}.inp"  # 形成安全 ASCII 输入文件名。
        input_text = make_all_load_test_input(load_name, load_label, load_value)  # 生成当前 ALL APDL 模板。
        write_new_text(unit_test_dir / file_name, input_text)  # 以不可覆盖模式写当前案例。
        cases.append({"case_id": case_id, "case_family": "ALL_SIX_AXIS_LOAD_TRANSFER", "load_label": load_label, "load_value": load_value, "load_unit": load_unit, "offset_vector_mm": [800.0, -600.0, 500.0], "input_file": f"unit_tests/{file_name}", "input_sha256": sha256_bytes(input_text.encode("utf-8")), "future_result_file": f"unit_tests/c10all_{load_name.lower()}_results.txt", "status": "PREPARED_NOT_STARTED"})  # 保存 ALL 荷载案例合同。
    require(len(cases) == EXPECTED_MICRO_CASES, f"微测试案例数为 {len(cases)}，预期 {EXPECTED_MICRO_CASES}")  # 三加三加六数量必须闭合。
    plan = {"schema_version": 3, "status": "PREPARED_NOT_STARTED", "purpose": "C10_SINGLE_MPC_PRODUCTION_TOPOLOGY_RANK_KINEMATICS_AND_TRANSFER", "planned_case_count": len(cases), "completed_case_count": 0, "mapdl_execution_attempted": False, "formulation": {"UXYZ": "SINGLE_TYPE72_PROJECTED_TO_TRANSLATION_ONLY_SLAVE", "ALL": "TYPE72_RIGID_BEAM", "constraint_imposition": "DIRECT_ELIMINATION", "aux_node_count": 0, "type73_count": 0, "penalty_factor": None}, "acceptance": {"max_rigid_body_translation_error_mm": 1.0e-6, "finite_rotation_rodrigues_displacement_error_mm": 1.0e-6, "finite_rotation_target_angle_error_rad": 1.0e-4, "slave_algebraic_rotation_error_rad": 1.0e-12, "force_equilibrium_absolute_tolerance_n": 2.0e-6, "force_equilibrium_preload_cancellation_relative_scale": 2.0e-12, "moment_equilibrium_absolute_tolerance_n_mm": 1.0e-6, "all_slave_translation_and_rotation_max_abs": 1.0e-10, "automatic_cnvtol_reset_allowed": False, "ignored_cnvtol_command_allowed": False, "solver_error_allowed": False, "zero_small_or_negative_pivot_allowed": False, "equation_count_change_within_case_allowed": False}, "cases": cases}  # 固定十二项门禁；2e-6 N 力平衡线对应双侧约 641 kN 初拉力抵消的约 1.6e-12 相对舍入量，并非放宽求解收敛标准。
    plan["result_contract"] = {"reported_vectors": ["MASTER_U_XYZ_MM", "MASTER_ROT_XYZ_RAD", "SLAVE_U_XYZ_MM", "SLAVE_ALGEBRAIC_ROT_XYZ_RAD", "GROUND_REACTION_FORCE_XYZ_N"], "derived_checks": ["SINGLE_MPC_RIGID_BODY_TRANSLATION", "RODRIGUES_FINITE_ROTATION", "ALL_ZERO_RELATIVE_SIX_DOF", "GLOBAL_FORCE_EQUILIBRIUM", "GLOBAL_MOMENT_EQUILIBRIUM_ABOUT_MASTER", "NO_AUTOMATIC_CONVERGENCE_RELAXATION", "NO_SOLVER_ERROR", "NO_ZERO_SMALL_OR_NEGATIVE_PIVOT", "EQUATION_COUNT_CONSTANT_WITHIN_CASE"], "sufficient_for_declared_micro_acceptance": True}  # 明确结果文件与日志共同覆盖生产拓扑装配秩门禁。
    results = {"schema_version": 3, "status": "NOT_RUN", "planned_case_count": EXPECTED_MICRO_CASES, "completed_case_count": 0, "passed_case_count": 0, "failed_case_count": 0, "mapdl_execution_attempted": False, "result_files_present": 0, "numerical_claim_allowed": False}  # 明确 prepare 阶段没有任何数值通过结论。
    return plan, results  # 返回计划和未执行结果状态。


def build_hash_rows(parent_snapshot: Path, input_snapshot: Path, solver_dir: Path, candidate_include_hash: str, candidate_main_hash: str) -> list[dict[str, Any]]:  # 输入三目录和候选哈希并返回双副本输入审计行。
    """十项不变量必须源、input_snapshot、solver 三份逐字节一致。"""  # 受控 include 和主控记录父/候选身份。
    rows: list[dict[str, Any]] = []  # 初始化十二项输入审计表。
    for order, name in enumerate(DEPENDENCY_NAMES, start=1):  # 按 /INPUT 顺序写十一项依赖。
        parent_hash = sha256_file(parent_snapshot / name)  # 复算父快照摘要。
        snapshot_hash = sha256_file(input_snapshot / name)  # 复算 C10 输入快照摘要。
        solver_hash = sha256_file(solver_dir / name)  # 复算 C10 solver 副本摘要。
        controlled = name == PARENT_INCLUDE_NAME  # 只有门架连接 include 是受控变化项。
        expected_candidate_hash = candidate_include_hash if controlled else parent_hash  # 选择当前依赖应命中的候选摘要。
        require(snapshot_hash == expected_candidate_hash and solver_hash == expected_candidate_hash, f"输入双副本哈希不闭合：{name}")  # 双副本必须命中预期。
        if not controlled:  # 十项不变量还必须等于父字节。
            require(snapshot_hash == parent_hash, f"不变量依赖发生字节变化：{name}")  # 任何变化立即拒绝。
        rows.append({"order": order, "name": name, "change_class": "CONTROLLED_CONNECTION_REPLACEMENT" if controlled else "BYTE_INVARIANT", "parent_name": name, "parent_sha256": parent_hash, "input_snapshot_sha256": snapshot_hash, "solver_sha256": solver_hash, "all_expected_hashes_match": True})  # 保存有序依赖哈希证据，并统一包含父文件名字段。
    parent_main_hash = sha256_file(parent_snapshot / PARENT_MAIN_NAME)  # 复算父 S10 主控摘要。
    snapshot_main_hash = sha256_file(input_snapshot / CANDIDATE_MAIN_NAME)  # 复算 C10 主控快照摘要。
    solver_main_hash = sha256_file(solver_dir / CANDIDATE_MAIN_NAME)  # 复算 C10 solver 主控摘要。
    require(snapshot_main_hash == candidate_main_hash and solver_main_hash == candidate_main_hash, "C10 主控双副本哈希不闭合")  # 两份主控必须一致。
    rows.append({"order": 12, "name": CANDIDATE_MAIN_NAME, "change_class": "CONTROLLED_RUNTIME_IDENTITY_AND_TOPOLOGY_AUDIT", "parent_name": PARENT_MAIN_NAME, "parent_sha256": parent_main_hash, "input_snapshot_sha256": snapshot_main_hash, "solver_sha256": solver_main_hash, "all_expected_hashes_match": True})  # 保存主控可逆变化证据。
    return rows  # 返回完整输入双副本审计表。


def write_artifact_ledger(run_dir: Path) -> None:  # 输入已完成运行目录并最后写 artifact_hashes.sha256。
    """账本排除自身；写出后本生成器不再创建或修改任何工件。"""  # 无返回值。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 固定最终产物账本路径。
    require(not ledger_path.exists(), "产物账本已存在，拒绝覆盖")  # 账本必须最后且只生成一次。
    files = sorted(path for path in run_dir.rglob("*") if path.is_file() and path != ledger_path)  # 枚举账本以外全部普通文件。
    lines = [f"{sha256_file(path)} *{path.relative_to(run_dir).as_posix()}" for path in files]  # 对每个相对路径计算逐字节摘要。
    write_new_text(ledger_path, "\n".join(lines) + "\n")  # 写固定 LF 的完整闭合账本。


def prepare(parent_run: str, run_name: str) -> Path:  # 输入父身份和目标身份并返回生成运行目录。
    """执行全部静态生成、可逆审计和发布；绝不查找或启动 MAPDL。"""  # 返回已封存 prepare-only 包路径。
    require(parent_run == DEFAULT_PARENT_RUN, f"本版只允许最终父运行 {DEFAULT_PARENT_RUN}")  # 防止从旧 S10 或旧 C10 边界派生。
    created_at, jobname = parse_run_created_at(run_name)  # 验证目标运行名并派生 UTC 时间和作业名。
    parent_dir = ULTRA_RUNS_DIR / parent_run  # 构造最终 S10 父运行绝对路径。
    parent_snapshot, parent_status, parent_manifest = validate_parent(parent_dir)  # 完成父状态、清单、文件和 include 哈希门禁。
    dependency_paths = tuple(parent_snapshot / name for name in DEPENDENCY_NAMES)  # 构造十一项最终 S10 有序依赖路径。
    parent_counts = parse_command_counts(dependency_paths)  # 复算 CP、D、CERIG 和拓扑命令计数。
    nodes = parse_nodes(dependency_paths)  # 解析全部 109086 个显式节点及原坐标字符串。
    existing_element_ids = parse_existing_element_ids(dependency_paths)  # 验证 MPC184 连续编号区间无显式碰撞。
    parent_include_path = parent_snapshot / PARENT_INCLUDE_NAME  # 固定唯一受控 include 路径。
    parent_include_bytes = parent_include_path.read_bytes()  # 二进制读取以支持逐字节回退。
    parent_include_text = parent_include_bytes.decode("utf-8")  # UTF-8 解码供 CERIG 解析。
    raw_records, _, _, _ = parse_cerig(parent_include_text)  # 解析 5078 条父逻辑连接。
    records = merge_constraint_metadata(raw_records)  # 加入稳定 CONN-ID 和工程元数据并逐行闭合。
    projection_audit = audit_uxyz_slave_projection(dependency_paths, records)  # 在生成前证明全部 UXYZ 从节点不存在转角物理消费者。
    candidate_include_bytes, mapping_rows, include_audit = transform_include(parent_include_bytes, records, nodes)  # 生成全直接消元连接候选 include 和可逆审计。
    parent_main_bytes = (parent_snapshot / PARENT_MAIN_NAME).read_bytes()  # 读取最终 S10 主控原始字节。
    candidate_main_bytes, main_audit = transform_main(parent_main_bytes, jobname)  # 生成可逆 C10 主控及唯一 TYPE72 门禁。
    require(len({int(row["rigid_element"]) for row in mapping_rows}) == EXPECTED_MPC_ELEMENTS, "单 TYPE72 元素 ID 不唯一")  # 候选 5078 个元素号必须完整唯一。
    require(all(row["aux_node"] == "" and row["translation_link_element"] == "" for row in mapping_rows), "映射仍含辅助节点或 TYPE73 元素")  # 防止旧两级链从任一记录回归。
    graph = graph_audit(dependency_paths, nodes, mapping_rows)  # 对全模型节点图、CP、D 和新 MPC 边执行静态连通审计。
    connection_ir = build_connection_ir(records, mapping_rows, nodes)  # 构造正式逐六自由度连接 IR。
    symbolic_matrix = build_symbolic_constraint_matrix(mapping_rows)  # 构造 30468 行单 TYPE72 符号约束矩阵表示。
    run_dir = ULTRA_RUNS_DIR / run_name  # 构造目标运行包绝对路径。
    if run_dir.exists():  # 本轮先前失败只允许留下一个空 builder_generated 目录。
        existing_files = [path for path in run_dir.rglob("*") if path.is_file()]  # 枚举已有普通文件，任何文件都可能是证据冲突。
        existing_dirs = [path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_dir()]  # 枚举已有子目录。
        require(not existing_files and set(existing_dirs).issubset({"builder_generated"}), f"目标运行目录不是允许复用的空壳：{run_dir}")  # 仅接受空 builder_generated。
    else:  # 目标运行目录尚不存在时创建。
        run_dir.mkdir(parents=True, exist_ok=False)  # 以不可覆盖方式创建唯一运行根目录。
    input_snapshot = run_dir / "input_snapshot"  # C10 可审计输入快照目录。
    solver_dir = run_dir / "solver"  # 未来显式授权后才可使用的求解目录。
    qa_dir = run_dir / "qa"  # 连接、边界和预求解机器审计目录。
    lineage_dir = run_dir / "lineage"  # 父状态、父清单和原 CERIG 谱系目录。
    unit_test_dir = run_dir / "unit_tests"  # 十二个未执行硬门禁微模型输入目录。
    orchestrator_dir = run_dir / "orchestrator_snapshot"  # 当前生成器源码快照目录。
    for name in INVARIANT_DEPENDENCY_NAMES:  # 逐项复制十个字节不变量到双副本。
        copy_new_verified(parent_snapshot / name, input_snapshot / name)  # 写可审计输入快照。
        copy_new_verified(parent_snapshot / name, solver_dir / name)  # 写未来求解副本。
    write_new_bytes(input_snapshot / PARENT_INCLUDE_NAME, candidate_include_bytes)  # 写受控连接 include 快照。
    write_new_bytes(solver_dir / PARENT_INCLUDE_NAME, candidate_include_bytes)  # 写相同候选 include 求解副本。
    write_new_bytes(input_snapshot / CANDIDATE_MAIN_NAME, candidate_main_bytes)  # 写可逆 C10 主控快照。
    write_new_bytes(solver_dir / CANDIDATE_MAIN_NAME, candidate_main_bytes)  # 写相同 C10 主控求解副本。
    copy_new_verified(parent_dir / "S10_status.json", lineage_dir / "parent_S10_status.json")  # 快照父执行后状态。
    copy_new_verified(parent_dir / "manifest.json", lineage_dir / "parent_manifest.json")  # 快照父最终清单。
    original_cerig_text = "\n".join(str(record["original_command"]) for record in records) + "\n"  # 生成独立 5078 条父命令证据，统一 LF 便于审阅。
    write_new_text(lineage_dir / "original_cerig_commands.inp", original_cerig_text)  # 保存反变换源命令列表。
    copy_new_verified(SCRIPT_PATH, orchestrator_dir / SCRIPT_PATH.name)  # 快照本次实际执行的生成器源码。
    builder_regeneration = {"schema_version": 1, "status": "SOURCE_REGENERATION_PATH_BLOCKED_NONBLOCKING_FOR_PATCH_METHOD", "direct_builder_used_for_candidate": False, "builder_script": str(BUILDER_SCRIPT_PATH), "missing_source": str(MISSING_BUILDER_SOURCE_PATH), "missing_source_exists": MISSING_BUILDER_SOURCE_PATH.exists(), "reason_direct_builder_rejected": ["would renumber final S10 physical nodes and beams", "would no longer preserve final S10 section shear strings", "would require regenerated MASS21 node references"], "selected_resolution": "REVERSIBLE_PATCH_OF_FINAL_EXECUTED_S10_INCLUDE"}  # 记录旧重生路径失败及本次安全替代方案。
    write_new_json(run_dir / "builder_generated" / "source_regeneration_attempt.json", builder_regeneration)  # 在先前空目录中留下非阻塞谱系说明。
    unit_test_plan, unit_test_results = build_unit_test_plan(unit_test_dir)  # 生成 12 个未执行硬门禁输入及计划/结果状态。
    input_hash_rows = build_hash_rows(parent_snapshot, input_snapshot, solver_dir, include_audit["candidate_sha256"], main_audit["candidate_sha256"])  # 复算十二项双副本哈希。
    write_new_text(qa_dir / "input_hash_audit.csv", rows_to_csv(input_hash_rows))  # 写有序输入身份表。
    write_new_text(qa_dir / "connection_mapping.csv", rows_to_csv(mapping_rows))  # 写 5078→5078 一对一单元素映射台账。
    write_new_json(qa_dir / "connection_ir.json", connection_ir)  # 写正式逐六自由度连接 IR。
    boundary_ir = {"schema_version": 1, "status": "INHERITED_BYTE_IDENTICAL", "coordinate_system": "X_LONGITUDINAL_Y_TRANSVERSE_Z_VERTICAL", "units": "N_mm_tonne_s", "explicit_d_command_count": parent_counts["D"], "cp_command_count": parent_counts["CP"], "boundary_change_count": 0, "connection_stage": "ACTIVE_BEFORE_LS1_AND_RETAINED_THROUGH_LS2_AND_MODAL", "invariant_sources": [{"name": name, "sha256": sha256_file(parent_snapshot / name)} for name in ("apply_mct_constraints_xlong.inp", "apply_modal_roty_stabilization_xlong.inp")], "soil_spring_contact_gap_friction_change": False}  # 描述边界完全继承关系。
    write_new_json(qa_dir / "boundary_ir.json", boundary_ir)  # 写边界 IR。
    write_new_json(qa_dir / "constraint_dof_matrix.json", symbolic_matrix)  # 写完整符号约束行表。
    write_new_json(qa_dir / "uxyz_slave_projection_audit.json", projection_audit)  # 写 UXYZ 从节点零转角消费者硬门证据。
    constraint_audit = {"schema_version": 3, "status": "STATIC_MAPPING_PASSED_NUMERICAL_RANK_PENDING", "logical_connections": EXPECTED_LOGICAL_CONNECTIONS, "source_semantics": {"UXYZ": EXPECTED_UXYZ_CONNECTIONS, "ALL": EXPECTED_ALL_CONNECTIONS}, "candidate_elements": {"TYPE72_RIGID_BEAM": EXPECTED_LOGICAL_CONNECTIONS, "TYPE73_TRANSLATION_RIGID_LINK": 0, "total": EXPECTED_MPC_ELEMENTS}, "constraint_imposition": {"TYPE72": "DIRECT_ELIMINATION", "TYPE73": "ABSENT", "penalty_factor": None}, "id_checks": {"aux_node_count": 0, "mpc_ids_unique": True, "mpc_range": [MPC_ELEMENT_START, MPC_ELEMENT_END], "node_collision_count": 0, "explicit_element_collision_count": 0, "existing_explicit_element_id_count": len(existing_element_ids)}, "reference_checks": {"all_master_slave_nodes_exist": True, "uxyz_slave_unique_count": len({int(row["slave_node"]) for row in mapping_rows if row["dof_label"] == "UXYZ"}), "uxyz_rotational_consumer_count": projection_audit["rotational_element_consumer_count"] + projection_audit["rotational_load_consumer_count"] + projection_audit["explicit_d_overlap_count"] + projection_audit["cp_overlap_count"], "master_equals_slave_count": 0, "duplicate_directed_semantic_pair_count": 0}, "chain_elimination": {"old_aux_type73_chain_count": EXPECTED_UXYZ_CONNECTIONS, "candidate_aux_type73_chain_count": 0, "single_type72_projection_gate": projection_audit["status"]}, "legacy_constraint_commands": {"parent_cerig": EXPECTED_LOGICAL_CONNECTIONS, "candidate_cerig": 0, "cp_unchanged": parent_counts["CP"], "d_unchanged": parent_counts["D"]}, "symbolic_matrix": {"row_count": symbolic_matrix["row_count"], "duplicate_structural_row_count": symbolic_matrix["duplicate_structural_row_count"], "numeric_rank_evaluated": False}, "graph_audit": graph}  # 汇总单层直接消元静态约束审计和待求解边界。
    write_new_json(qa_dir / "constraint_audit.json", constraint_audit)  # 写约束审计。
    write_new_json(qa_dir / "connection_unit_test_plan.json", unit_test_plan)  # 写十二个单刚臂与 ALL 微测试计划。
    support_expectation = {"schema_version": 2, "status": "NOT_EVALUATED_PREPARE_ONLY", "reference_coordinate_system": "GLOBAL_X_LONG_Y_TRANSVERSE_Z_VERTICAL", "future_checks": [{"id": "REACTION-FORCE-01", "rule": "sum_support_reactions_plus_applied_force_equals_zero", "relative_tolerance": 1.0e-6}, {"id": "REACTION-MOMENT-01", "rule": "sum_support_moments_plus_force_moments_about_frozen_origin_equals_zero", "relative_tolerance": 1.0e-6}, {"id": "INTERFACE-FLOW-01", "rule": "production_topology_micro_support_reactions_close_applied_translation_load", "relative_tolerance": 1.0e-6}], "numeric_expected_values_available": False, "reason": "full-bridge solve and 12 single-MPC/direct-elimination micro solves were intentionally not started"}  # 定义未来反力平衡规则而不伪造数值。
    write_new_json(qa_dir / "support_reaction_expectation.json", support_expectation)  # 写支承反力预期。
    connection_issues = {"schema_version": 2, "status": "OPEN_ITEMS_RESTRICT_PRODUCTION_USE", "issues": [{"id": "C10-DWG-01", "severity": "MEDIUM", "status": "OPEN", "description": "5078 条连接有 S10/CERIG 和 builder 元数据来源，但没有逐条图纸编号引用。", "effect": "candidate may be used for connection-repair validation only"}, {"id": "C10-NUM-01", "severity": "HIGH", "status": "OPEN", "description": "十二个单 TYPE72 微算例、全桥静力、装配秩和模态响应尚未执行。", "effect": "launch and production claims remain disabled"}, {"id": "C10-RANK-01", "severity": "HIGH", "status": "OPEN", "description": "旧 3124 条 aux+TYPE73 串联链已删除；新单 TYPE72 切线仍须验证无 small/zero/negative pivot 且同一案例方程数恒定。", "effect": "static projection proof is not a numerical rank proof"}, {"id": "C10-BUILDER-01", "severity": "LOW", "status": "DOCUMENTED", "description": "旧物理 builder 所需 tail_nodes.csv 已缺失，且旧重生方法会污染最终 S10 编号边界。", "effect": "this run uses an exact reversible patch instead"}]}  # 记录未关闭问题和使用限制。
    write_new_json(qa_dir / "connection_issues.json", connection_issues)  # 写连接问题清单。
    model_single_difference = {"schema_version": 3, "status": "PASSED", "parent_run": parent_run, "physical_change_family_count": 1, "physical_change_family": "CERIG_TO_SINGLE_MPC184_LARGE_ROTATION_CONNECTION_KINEMATICS_ONLY", "invariant_dependency_count": len(INVARIANT_DEPENDENCY_NAMES), "controlled_dependency_count": 1, "include_reversible_audit": include_audit, "main_control_reversible_audit": main_audit, "uxyz_projection_audit": projection_audit, "allowed_changes": {"cerig_removed": EXPECTED_LOGICAL_CONNECTIONS, "aux_nodes_added": 0, "type72_rigid_beams_added": EXPECTED_LOGICAL_CONNECTIONS, "type73_translation_rigid_links_added": 0, "mpc_type_and_component_definitions_added": True}, "forbidden_changes": {"original_29626_node_commands": False, "original_17679_beam_commands": False, "materials": False, "sections_61_to_66": False, "beam_orientation_nodes": False, "mass": False, "loads": False, "initial_state": False, "boundary_d": False, "boundary_cp": False, "analysis_stages": False, "modal_request": False, "penalty_stiffness": False, "auxiliary_constraint_nodes": False, "type73_elements": False}, "parent_section_61_exact_line_preserved": "SECDATA,4997.5,9830899.73958,0,28164706.4583,66066802083.3,176798.958333,0,0,0,0,175,175,0.6712958043168660,0.2363842696133852" in candidate_include_bytes.decode("utf-8")}  # 汇总单物理差异合同、投影证明和无罚函数禁改项。
    require(model_single_difference["parent_section_61_exact_line_preserved"] is True, "最终 S10 SEC61 精确字符串未保留")  # 防止历史 Iyy/Izz 对调再次混入。
    write_new_json(qa_dir / "model_single_difference_audit.json", model_single_difference)  # 写最强单差异证据。
    model_statistics = {"schema_version": 2, "status": "STATIC_EXPECTATIONS_CLOSED", "parent": {"nodes": EXPECTED_PARENT_NODES, "elements": EXPECTED_PARENT_ELEMENTS, "TYPE4": 73692, "TYPE6": 48620, "TYPE70": EXPECTED_PHYSICAL_BEAMS, "TYPE71": 33003, "CERIG_commands": EXPECTED_LOGICAL_CONNECTIONS, "CP_commands": EXPECTED_CP_COMMANDS, "D_commands": EXPECTED_D_COMMANDS}, "candidate_expected": {"nodes": EXPECTED_CANDIDATE_NODES, "elements": EXPECTED_CANDIDATE_ELEMENTS, "TYPE4": 73692, "TYPE6": 48620, "TYPE70": EXPECTED_PHYSICAL_BEAMS, "TYPE71": 33003, "TYPE72": EXPECTED_LOGICAL_CONNECTIONS, "TYPE73": 0, "CERIG_commands": 0, "CP_commands": EXPECTED_CP_COMMANDS, "D_commands": EXPECTED_D_COMMANDS}, "runtime_counts_verified": False}  # 记录执行前单 TYPE72 封板拓扑期望。
    write_new_json(qa_dir / "model_statistics.json", model_statistics)  # 写模型统计。
    unit_audit = {"schema_version": 2, "status": "PASSED", "unit_system": {"force": "N", "length": "mm", "mass": "tonne", "time": "s", "moment": "N_mm", "stress": "MPa", "rotation": "rad"}, "constraint_imposition": "DIRECT_ELIMINATION_WITHOUT_PENALTY_PARAMETER", "coordinate_values_finite": True, "unit_test_forces_n": [1.0], "unit_test_moments_n_mm": [1.0], "finite_rotation_values_rad": [0.1]}  # 汇总单位、量纲和无罚参数事实。
    write_new_json(qa_dir / "unit_and_dimension_audit.json", unit_audit)  # 写单位审计。
    connectivity_audit = {"schema_version": 1, "status": "STATIC_GRAPH_PASSED_NUMERICAL_DOF_RANK_PENDING", "graph": graph, "constraint_symbolic_row_count": symbolic_matrix["row_count"], "duplicate_symbolic_rows": 0, "numeric_rank_checked": False, "rigid_body_mode_checked": False, "overconstraint_solver_check_pending": True, "underconstraint_solver_check_pending": True}  # 描述静态图通过和数值自由度待办。
    write_new_json(qa_dir / "connectivity_and_dof_audit.json", connectivity_audit)  # 写连通性和自由度审计。
    load_mass_audit = {"schema_version": 1, "status": "PASSED_BY_BYTE_IDENTITY_NUMERICAL_BALANCE_PENDING", "mass_include": "apply_dynamic_mass21_spatialized_v2.inp", "mass_include_sha256": sha256_file(parent_snapshot / "apply_dynamic_mass21_spatialized_v2.inp"), "deadload_include_sha256": sha256_file(parent_snapshot / "apply_authoritative_mct_deadload_v1.inp"), "gravity_include_sha256": sha256_file(parent_snapshot / "apply_authoritative_mct_gravity_v1.inp"), "initial_state_include_sha256": sha256_file(parent_snapshot / "apply_mct_authoritative_initial_state_link180.inp"), "added_aux_node_mass": 0.0, "mpc184_mass": 0.0, "duplicate_load_change": False, "numerical_mass_balance_checked": False, "numerical_reaction_balance_checked": False}  # 证明质量、荷载和初态输入不变并保留数值待办。
    write_new_json(qa_dir / "load_mass_balance_precheck.json", load_mass_audit)  # 写荷载质量预检查。
    write_new_json(qa_dir / "unit_test_results.json", unit_test_results)  # 写明确未运行的单位测试结果状态。
    inherited_parent_limitations: list[dict[str, Any]] = []  # 初始化经过 C10 语义重判定的父限制列表，禁止原样继承过时结论。
    for parent_limitation in parent_status.get("documented_limitations", []):  # 逐条读取最终 S10 的已记录限制。
        limitation_id = str(parent_limitation.get("id", "UNKNOWN"))  # 读取稳定限制编号并为异常缺失提供显式占位。
        parent_description = str(parent_limitation.get("description", ""))  # 保留父运行原始说明作为谱系证据。
        if limitation_id == "LEGACY_CONSTRAINT_EQUATION_LARGE_DEFLECTION":  # C10 正在替换该项连接运动学，不能再称“本次未改变”。
            inherited_parent_limitations.append({"id": limitation_id, "parent_description": parent_description, "c10_status": "TARGETED_BY_MPC184_PATCH_NUMERICAL_CLOSURE_PENDING", "description": "C10 已在输入层删除 5078 条 CERIG 并替换为 MPC184；是否消除大转动 warning、主元和条件数问题仍待数值执行。"})  # 用当前真实状态替换父运行的过时描述。
        else:  # 其余频带、近重根、严格 MAC 和尺度限制继续按父状态继承。
            inherited_parent_limitations.append({"id": limitation_id, "parent_description": parent_description, "c10_status": "INHERITED_PENDING_REEVALUATION", "description": parent_description})  # 同时保存父原文和 C10 待复核状态。
    pre_solve_issues = {"schema_version": 1, "status": "VALIDATION_GATES_PENDING", "blocking_for_generation": [], "blocking_for_mapdl_launch": ["C10-NUM-01", "C10-RANK-01"], "blocking_for_production_use": ["C10-DWG-01", "C10-NUM-01", "C10-RANK-01"], "inherited_parent_limitations": inherited_parent_limitations}  # 区分生成、启动和生产使用三个门槛，并使用已重判定的父限制。
    write_new_json(qa_dir / "pre_solve_issues.json", pre_solve_issues)  # 写预求解问题表。
    pre_solve_verification = {"schema_version": 3, "status": "STATIC_PREPARE_GATE_PASSED_VALIDATION_PENDING", "run_name": run_name, "parent_run": parent_run, "checks": {"parent_final_status": "PASSED", "ten_invariant_dependencies_byte_identical": True, "controlled_include_reversible_to_parent_bytes": True, "main_control_reversible_to_parent_bytes": True, "logical_5078_to_physical_5078_mapping": "PASSED", "id_and_reference_closure": "PASSED", "aux_and_type73_absence": "PASSED", "uxyz_slave_rotational_consumer_gate": projection_audit["status"], "cp_d_identity": "PASSED", "unit_and_dimension": "PASSED", "load_mass_initial_state_input_identity": "PASSED", "symbolic_constraint_duplicate_rows": "PASSED", "numeric_constraint_rank": "NOT_RUN", "equation_count_stability": "NOT_RUN", "rigid_body_modes": "NOT_RUN", "twelve_single_mpc_micro_cases": "PREPARED_NOT_STARTED", "full_bridge_static": "NOT_RUN", "full_bridge_modal": "NOT_RUN"}, "launch_allowed": False, "mapdl_execution_attempted": False, "mapdl_started": False, "valid_for_production": False}  # 汇总 prepare-only G11 前静态结果和未完成数值门禁。
    write_new_json(qa_dir / "pre_solve_verification.json", pre_solve_verification)  # 写预求解总验证。
    field_dictionary = """# C10 机器工件字段说明\n\n本目录的 JSON/CSV 必须保持语法有效，因此注释集中在本文件。`status` 只描述对应工件的完成层级：`PASSED` 表示静态源证检查通过，`NOT_RUN` 或 `VALIDATION_PENDING` 表示没有数值求解结论。\n\n- `conn_id`：稳定逻辑连接编号；一条编号始终对应父 S10 的一条 CERIG。\n- `master_node` / `slave_node`：最终 S10 原节点号，绝不因 C10 重排。\n- `aux_node`：兼容旧表结构而保留，单 TYPE72 方案中全部为空；任何非空值都应拒绝。\n- `rigid_element`：一条逻辑连接唯一对应的 TYPE72 direct-elimination rigid-beam 元素号。\n- `translation_link_element`：兼容旧表结构而保留，当前全部为空且 TYPE73 计数必须为零。\n- `penalty_n_per_mm=null`：当前方案不存在罚刚度参数，也不存在罚函数滑移。\n- `dof_behavior`：UX/UY/UZ 为物理刚体平移；UXYZ 的 RX/RY/RZ 只在 TYPE72 内代数闭合，源审计证明其物理共轭项为零。\n- `uxyz_slave_projection_audit.json`：证明 3,124 个 UXYZ slave 只连接 LINK10/LINK180 和仅平移 MASS21，且与 D、CP、CE、力矩载荷零重叠。\n- `canonicalized_equals_source_bytes`：删除白名单新增块并恢复原 CERIG 后是否逐字节等于最终 S10。\n- `numeric_rank_evaluated=false`：有限转动 MPC184 装配切线尚未由 MAPDL 形成，不能宣称秩门禁通过。\n- `launch_allowed=false`：12 个生产拓扑/有限转动/ALL 微测和全桥数值门禁尚未完成，当前包只能审阅和后续验证。\n- 所有坐标单位为 mm，力为 N，力矩为 N·mm，质量为 tonne，时间为 s。\n"""  # 提供 JSON/CSV 无法内嵌的逐项语义、单位和结论边界。
    write_new_text(qa_dir / "field_dictionary.md", field_dictionary)  # 写邻接字段字典。
    unit_test_readme = """# C10 单连接数值验证输入\n\n这里有 3 个“柔性 BEAM188 master—单 TYPE72—双侧预拉 LINK180 slave—仅平移 MASS21”平移载荷案例、3 个 0.1 rad 单 TYPE72 有限转动案例和 6 个 ALL 六向载荷案例，共 12 份 APDL 输入。它们由 prepare 生成，但没有启动 MAPDL。生产候选只有 TYPE72，不含辅助节点、TYPE73、罚刚度或弱弹簧。\n\n通过条件以 `qa/connection_unit_test_plan.json` 为准。除运动学与平衡外，日志必须满足 solver error=0、small/zero/negative pivot=0、自动 CNVTOL 重置=0，并且同一案例所有重组的方程数恒定。全桥启动仍需完成这些微模型、初始状态—外荷载路径复核和独立审查。\n"""  # 说明十二个模板的生产拓扑覆盖和禁止误用边界。
    write_new_text(unit_test_dir / "README.md", unit_test_readme)  # 写单位测试目录说明。
    source_entries = [(sha256_file(SCRIPT_PATH), str(SCRIPT_PATH)), (sha256_file(BUILDER_SCRIPT_PATH), str(BUILDER_SCRIPT_PATH)), (sha256_file(CONSTRAINT_METADATA_PATH), str(CONSTRAINT_METADATA_PATH)), (sha256_file(parent_dir / "S10_status.json"), str(parent_dir / "S10_status.json")), (sha256_file(parent_dir / "manifest.json"), str(parent_dir / "manifest.json"))]  # 初始化生成器、语法参考、元数据和父谱系源证。
    source_entries.extend((sha256_file(parent_snapshot / name), str(parent_snapshot / name)) for name in DEPENDENCY_NAMES + (PARENT_MAIN_NAME,))  # 加入最终 S10 十二项实际输入源证。
    source_hash_text = "\n".join(f"{digest} *{path}" for digest, path in source_entries) + "\n"  # 生成固定 LF 的源文件哈希表。
    write_new_text(run_dir / "source_hashes.sha256", source_hash_text)  # 写根级源证账本。
    future_command = f"& 'D:\\ANSYS2026\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' '-b' '-dis' '-mpi' 'intelmpi' '-np' '4' '-j' '{jobname}' '-dir' '{solver_dir}' '-i' '{solver_dir / CANDIDATE_MAIN_NAME}' '-o' '{solver_dir / (jobname + '.out')}'"  # 构造仅供未来显式授权使用的 DMP4 命令字符串。
    launch_text = f"STATUS=DISABLED_VALIDATION_GATE_MISSING\nEXECUTION_ATTEMPTED=false\nMAPDL_STARTED=false\nLAUNCH_ALLOWED=false\nREQUIRED_BEFORE_LAUNCH=RUN_12_SINGLE_MPC_MICRO_CASES_AND_NUMERICAL_RANK_REVIEW\nFUTURE_COMMAND_BEGIN\n{future_command}\nFUTURE_COMMAND_END\nTHIS_FILE_IS_EVIDENCE_ONLY_AND_WAS_NOT_EXECUTED_BY_ULTRA_C10_PREPARE\n"  # 明确命令仅为证据且本轮未执行。
    write_new_text(run_dir / "launch_command.txt", launch_text)  # 写禁用状态和未来命令证据。
    status = {"schema_version": 3, "run_id": "C10_MPC_ONLY", "run_name": run_name, "jobname": jobname, "status": "STATIC_PREPARE_GATE_PASSED_VALIDATION_PENDING", "created_at_utc": created_at.isoformat(), "parent_run": parent_run, "parent_status": parent_status.get("status"), "physical_change_family": "CERIG_TO_SINGLE_MPC184_LARGE_ROTATION_CONNECTION_KINEMATICS_ONLY", "uxyz_formulation": "SINGLE_TYPE72_PROJECTED_TO_TRANSLATION_ONLY_SLAVE", "uxyz_projection_gate": projection_audit["status"], "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None, "logical_connection_count": EXPECTED_LOGICAL_CONNECTIONS, "aux_node_count": 0, "type73_element_count": 0, "mpc184_element_count": EXPECTED_MPC_ELEMENTS, "mapdl_execution_attempted": False, "mapdl_started": False, "launch_allowed": False, "micro_validation_status": "PREPARED_NOT_STARTED", "full_bridge_validation_status": "NOT_RUN", "valid_for_production": False, "next_action": "EXECUTE_12_SINGLE_MPC_MICRO_CASES_THEN_REVIEW_NUMERICAL_RANK"}  # 根级状态只声明无串联链候选静态生成完成。
    write_new_json(run_dir / "C10_status.json", status)  # 写根级状态。
    manifest = {"schema_version": 3, "run_id": "C10_MPC_ONLY", "run_name": run_name, "model_line": "FINAL_S10_PLUS_SINGLE_DIRECT_ELIMINATION_MPC184_CONNECTION_PATCH_ONLY", "status": status["status"], "created_at_utc": created_at.isoformat(), "parent_run": parent_run, "parent_include_sha256": EXPECTED_PARENT_INCLUDE_SHA256, "jobname": jobname, "main_input": f"solver/{CANDIDATE_MAIN_NAME}", "main_input_sha256": main_audit["candidate_sha256"], "controlled_include": f"solver/{PARENT_INCLUDE_NAME}", "controlled_include_sha256": include_audit["candidate_sha256"], "modes_requested": 80, "frequency_bounds_hz": None, "from_scratch_static": True, "ls1_time": 1.0, "ls2_time": 1.001, "constraint_imposition": "DIRECT_ELIMINATION", "aux_node_count": 0, "type73_count": 0, "penalty_n_per_mm": None, "dependencies": input_hash_rows, "single_difference_contract": model_single_difference, "expected_topology": model_statistics["candidate_expected"], "prepare_only": True, "mapdl_execution_attempted": False, "mapdl_started": False, "launch_allowed": False, "future_launch_command": future_command, "outputs": ["C10_status.json", "manifest.json", "result_packet.md", "launch_command.txt", "source_hashes.sha256", "artifact_hashes.sha256", "input_snapshot/", "solver/", "qa/", "lineage/", "unit_tests/", "orchestrator_snapshot/", "builder_generated/"]}  # 汇总父身份、单 TYPE72 候选、投影证明、拓扑和输出契约。
    write_new_json(run_dir / "manifest.json", manifest)  # 写根级清单。
    result_packet = f"""# C10 单 TYPE72 连接候选生成结果\n\n状态：`STATIC_PREPARE_GATE_PASSED_VALIDATION_PENDING`。本包从最终已执行 `{parent_run}` 直接打可逆补丁，没有运行旧物理 builder，也没有启动 MAPDL。\n\n## 已闭合\n\n- 原 5,078 条 CERIG：3,124 条 UXYZ、1,954 条 ALL。\n- 候选：5,078 个 TYPE72 rigid beam，一条逻辑连接对应一个元素；辅助节点=0、TYPE73=0、MPC184 总数=5,078。\n- 全量证明 3,124 个 UXYZ slave 只连接平移型 LINK10/LINK180，1,152 个另带 KEYOPT(3)=2 的平移 MASS21；转动型单元、力矩载荷、D、CP、CE 消费者均为零。\n- 因此旧链 `master—TYPE72—aux—TYPE73—slave` 可在物理 UXYZ 空间缩并为 `master—TYPE72—slave`，同时删除会在非线性重组中失秩的中间链。\n- TYPE72 采用 direct elimination 并保留几何应力刚度；不存在罚刚度参数、罚函数滑移、弱弹簧或 KEYOPT(5) 绕过。\n- 十项非连接 include 与最终 S10 逐字节相同；质量、荷载、初态、D=3,968、CP=12 均未改。\n- 候选 include 删除新增块并恢复 CERIG 后，SHA-256 精确回到 `{EXPECTED_PARENT_INCLUDE_SHA256}`。\n- 主控反向规范化后逐字节恢复 S10；LS1/LS2、80阶 LANB、NSOL/VENG 输出均保留。\n- 已生成 3 个生产拓扑平移载荷、3 个 0.1 rad 有限转动和 6 个 ALL 荷载，共 12 份微模型输入，完成数仍为 0。\n\n## 尚未闭合\n\n- 未执行 12 个微测试、MPC184 装配切线数值秩、全桥初始平衡静力和全桥模态。\n- 数值硬门包括 solver error=0、small/zero/negative pivot=0、自动 CNVTOL 重置=0、同一案例方程数恒定。\n- S10 继承的初始索力—外荷载平衡语义仍需在全桥静力中复核，不能以输入静态审计代替。\n- 逐连接图纸编号仍缺失；当前只能用于连接修复验证，不能用于生产签认。\n- 因此 `launch_allowed=false`、`valid_for_production=false`。\n\n核心审计见 `qa/uxyz_slave_projection_audit.json`、`qa/model_single_difference_audit.json`、`qa/constraint_audit.json`、`qa/pre_solve_verification.json` 和 `qa/connection_mapping.csv`。\n"""  # 生成面向审阅者的简明结果包。
    write_new_text(run_dir / "result_packet.md", result_packet)  # 写根级结果说明。
    write_artifact_ledger(run_dir)  # 最后生成全包哈希账本，之后不得再修改工件。
    return run_dir  # 返回已完成静态封存的 C10 运行目录。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回两个受控命令行参数。
    """命令行不提供执行开关，因此脚本结构上无法启动 MAPDL。"""  # 返回 argparse 命名空间。
    parser = argparse.ArgumentParser(description="Prepare a reversible C10 MPC184-only candidate from the final executed S10; never starts MAPDL.")  # 创建 prepare-only 接口。
    parser.add_argument("--parent-run", default=DEFAULT_PARENT_RUN, help="Final executed S10 parent run name; only the frozen default is accepted.")  # 允许显式重复父身份但不允许改用旧父包。
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME, help="Safe C10_MPC_ONLY_YYYYMMDDTHHMMSSffffffZ output directory name.")  # 指定安全新运行名。
    return parser.parse_args()  # 解析并返回命令行参数。


def main() -> None:  # 无输入和返回值；执行 prepare 并向标准输出写机器摘要。
    """唯一程序入口只生成、审计和封存 C10，不启动任何外部求解器。"""  # 异常时由 Python 返回非零退出码。
    arguments = parse_arguments()  # 读取受控命令行参数。
    run_dir = prepare(str(arguments.parent_run), str(arguments.run_name))  # 执行全部静态生成和门禁。
    print(json.dumps({"run_dir": str(run_dir), "status": "STATIC_PREPARE_GATE_PASSED_VALIDATION_PENDING", "mapdl_started": False, "launch_allowed": False}, ensure_ascii=False))  # 输出单行机器摘要供调用者确认。


if __name__ == "__main__":  # 仅直接执行本文件时进入程序入口。
    main()  # 调用 prepare-only 主函数并保持 MAPDL 永不启动。
