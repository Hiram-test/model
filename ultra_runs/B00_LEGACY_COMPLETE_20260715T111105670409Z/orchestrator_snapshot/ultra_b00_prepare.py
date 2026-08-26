"""只准备 B00_LEGACY_COMPLETE 独立全桥输入快照，绝不启动 MAPDL。"""  # 模块说明明确本文件只有封板职责，没有任何求解执行路径。

from __future__ import annotations  # 启用延迟类型注解，避免运行期解析复杂容器类型造成额外依赖。

import argparse  # 仅用于解析显式 U01 目录名和模态阶数两个命令行参数。
import ctypes  # 仅用于调用 Windows GlobalMemoryStatusEx 获取实时物理内存快照。
import hashlib  # 仅用于流式计算 SHA-256，完成源文件、复制件和账本闭合。
import json  # 仅用于读取 U00/U01 机器证据并写出 B00 机器清单。
import re  # 仅用于校验安全目录名及统计封板 APDL 命令身份。
import secrets  # 仅用于生成两位十六进制作业名后缀，避免同秒作业名冲突。
import shutil  # 仅用于不改源文件的逐字节复制及磁盘容量查询。
from datetime import datetime, timezone  # 仅用于生成带微秒的 UTC run 名和证据时间。
from pathlib import Path  # 统一处理 Windows 路径、相对路径和不可覆盖目标目录。
from typing import Any  # 为 JSON 动态字段提供明确但不过度收窄的类型标注。


SCRIPT_PATH = Path(__file__).resolve()  # 当前编排器绝对路径用于源码哈希和 lineage 快照。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 目录是编排器及 U01 模板所在目录。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录承载 builder、质量文件和 ultra_runs。
ULTRA_RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 所有 U00、U01、B00 独立 run 的唯一父目录。
U00_RUN_NAME = "U00_SOURCE_GATE_20260715T024455Z"  # 固定使用已经人工复核的 U00 门禁，不通配最新目录。
U00_RUN = ULTRA_RUNS_ROOT / U00_RUN_NAME  # 固定 U00 证据目录用于状态、环境、图和哈希核验。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 固定使用 U00 审核的 2026 R1 可执行文件。
MAPDL_SHA256 = "6c6327f6b906db8e6dd498bd38c97685d7e3e4acf52fccbf243b2dff7ed7af1b"  # 固定可执行程序摘要，任何字节变化均拒绝准备。
RUN_ID = "B00_LEGACY_COMPLETE"  # 唯一允许准备的运行标识，同时作为新目录的固定前缀。
MODEL_LINE = "LEGACY"  # manifest 模型线固定为 LEGACY，禁止把 C10/MPC 诊断线混入。
GRAPH_SOURCE_ID = "GENERATED:B00_LEGACY_COMPLETE_main.inp"  # U00 依赖图中 B00 主输入的固定虚拟源节点。
GRAPH_RELATION = "/INPUT LEGACY_FROZEN_APDL"  # U00 图中唯一允许提取的 legacy 冻结依赖关系。
DEPENDENCY_COUNT = 11  # B00 冻结装配必须恰好包含 order 1 至 11 共十一项。
DEFAULT_MODES = 80  # 默认提取 80 阶，覆盖本轮完整低频分支诊断的最低规模。
MODE_MULTIPLE = 40  # 用户阶数必须按 40 阶批次递增，保持资源预算和审计口径一致。
MINIMUM_MODES = 80  # 少于 80 阶不满足 B00 完整求解准备范围。
UPPER_FREQUENCY_HZ = 0.35  # Block Lanczos 上限固定 0.35 Hz，覆盖附件目标并保留分支裕量。
PROCESS_COUNT = 4  # 未来命令固定使用四进程 DMP，与 U01 DMP4 已通过配置一致。
MPI_NAME = "intelmpi"  # 未来 DMP 命令固定使用 U01 已验证的 Intel MPI。
MINIMUM_MEMORY_BYTES = 8 * 1024**3  # 全桥执行期最低可用物理内存门槛为 8 GiB，仅记录不触发执行。
COMFORTABLE_MEMORY_BYTES = 10 * 1024**3  # 全桥舒适可用物理内存参考值为 10 GiB，用于人工排程。
MINIMUM_DISK_BYTES = 32 * 1024**3  # 执行期保守磁盘门槛为 32 GiB，按 80 阶和双份节点文本约四倍历史预算。
EXPECTED_NODE_COUNT = 109086  # 完整 B00 装配后的节点总数必须与封板拓扑一致。
EXPECTED_ELEMENT_COUNT = 172994  # 完整 B00 装配后的单元总数必须与封板拓扑一致。
EXPECTED_TYPE_COUNTS = {4: 73692, 6: 48620, 70: 17679, 71: 33003}  # 四类单元计数共同闭合全部 172994 个单元。
EXPECTED_CERIG_COUNT = 5078  # 根 builder 冻结输入必须包含 5078 条 CERIG 刚性连接。
EXPECTED_TOTAL_D_COUNT = 3968  # downpull、支承和 ROTY 三个冻结文件的 D 命令合计必须为 3968。
EXPECTED_MASS_TONNE = 4108.46690758  # 全模 X 向平动质量封板基准，单位 tonne。
MASS_ABSOLUTE_TOLERANCE_TONNE = 1.0e-6  # 执行期总质量绝对误差上限，单位 tonne。
EXPECTED_UZ_SUPPORT_COUNT = 464  # 完整静力模型施加 UZ 位移约束的支承节点必须恰为 464。
REACTION_RELATIVE_TOLERANCE = 1.0e-4  # 完整重力与竖向支反力的相对闭合误差上限。
LS1_ENERGY_RATIO_LIMIT = 1.0e-2  # LS1 稳定化能与势能比硬上限为百分之一。
LS2_ENERGY_RATIO_LIMIT = 1.0e-8  # LS2 关闭稳定化后的残余能量比硬上限。
GRAVITY_MM_S2 = 9806.0  # N-mm-tonne-s 单位制中的标准重力加速度，单位 mm/s²。
NEXT_ACTION = "B00_PREFLIGHT_MEMORY_AND_INDEPENDENT_AUDIT_REQUIRED"  # 准备完成后的固定下一动作，不因实时资源真假改变。
STATUS_VALUE = "PREPARED_NOT_STARTED"  # 本脚本唯一允许写出的状态，明确 MAPDL 尚未启动。
U01_NAME_PATTERN = re.compile(r"U01_UNIT_TESTS_\d{8}T\d{12}Z\Z", re.ASCII)  # 只接受 ultra_runs 下标准 U01 微秒目录名。
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)  # 哈希账本摘要必须为 64 位小写十六进制。
FORBIDDEN_PATH_TOKENS = ("regenerated", "mpc", "c10")  # B00 源路径严禁出现再生成线、MPC 线或 C10 线标识。
MAIN_INPUT_NAME = "b00_legacy_complete_main.inp"  # solver 目录中的唯一 B00 主 APDL 输入文件名。


class MemoryStatusEx(ctypes.Structure):  # 定义 Windows GlobalMemoryStatusEx 所需的固定二进制结构。
    """承载 Windows 物理内存和页文件计数，所有容量字段单位均为 byte。"""  # 类说明给出输入来源、输出单位和用途约束。

    _fields_ = [  # 字段顺序严格遵循 Windows MEMORYSTATUSEX ABI，不能调整或删减。
        ("dwLength", ctypes.c_ulong),  # 结构长度字段由调用前写入 sizeof，单位 byte。
        ("dwMemoryLoad", ctypes.c_ulong),  # 当前物理内存负载百分比，范围 0 至 100。
        ("ullTotalPhys", ctypes.c_ulonglong),  # 总物理内存容量，单位 byte。
        ("ullAvailPhys", ctypes.c_ulonglong),  # 当前可用物理内存容量，单位 byte。
        ("ullTotalPageFile", ctypes.c_ulonglong),  # 总提交容量，单位 byte。
        ("ullAvailPageFile", ctypes.c_ulonglong),  # 当前可用提交容量，单位 byte。
        ("ullTotalVirtual", ctypes.c_ulonglong),  # 当前进程可见总虚拟地址空间，单位 byte。
        ("ullAvailVirtual", ctypes.c_ulonglong),  # 当前进程可见可用虚拟地址空间，单位 byte。
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),  # 扩展虚拟地址空间容量；现代 64 位 Windows 通常为零。
    ]  # 结束 ABI 字段定义，后续只读快照不得更改结构布局。


def require(condition: bool, message: str) -> None:  # 定义 fail-closed 断言，输入条件和错误说明，无成功返回值。
    """条件为假时抛出 RuntimeError；条件为真时不改变任何状态。"""  # 函数说明明确失败行为和无副作用约束。
    if not condition:  # 只有硬门禁未满足时才进入异常路径。
        raise RuntimeError(message)  # 立即中止准备，禁止在不完整证据上创建 B00 run。


def utc_now() -> datetime:  # 定义统一 UTC 时钟函数，无输入，返回带时区 datetime。
    """返回当前 UTC 时间，供 run 名、jobname 和清单共享同一时间源。"""  # 函数说明限定时区和复用目的。
    return datetime.now(timezone.utc)  # 使用系统 UTC 实时时钟并保留微秒精度。


def sha256_file(path: Path) -> str:  # 定义流式文件摘要函数，输入现存普通文件，输出小写 SHA-256。
    """以 1 MiB 块读取文件，避免大型 APDL 和 MAPDL 可执行程序占满内存。"""  # 函数说明给出块策略和返回值。
    require(path.is_file(), f"待哈希文件不存在：{path}")  # 哈希前确认目标是普通文件，拒绝目录或缺件。
    digest = hashlib.sha256()  # 初始化新的 SHA-256 状态，禁止复用其他文件的摘要状态。
    with path.open("rb") as stream:  # 以二进制只读方式打开源文件，绝不修改源字节。
        while True:  # 持续读取固定块，直至读到空字节串表示 EOF。
            chunk = stream.read(1024 * 1024)  # 每次最多读取 1 MiB，在吞吐和内存之间取稳定折中。
            if not chunk:  # 空块只会在正常文件尾出现。
                break  # 结束读取循环并保留累计摘要。
            digest.update(chunk)  # 把当前原始字节块加入摘要，不做编码或换行转换。
    return digest.hexdigest()  # 返回 64 位小写十六进制摘要供账本比较。


def read_json(path: Path) -> dict[str, Any]:  # 定义 UTF-8 JSON 对象读取函数，输入路径，输出字典。
    """读取并验证顶层为对象的 JSON；不接受数组、标量或静默编码替换。"""  # 函数说明给出格式约束。
    require(path.is_file(), f"缺少 JSON 证据：{path}")  # 读取前硬门禁文件存在性。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 允许可选 UTF-8 BOM，但不容忍乱码替换。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 顶层必须为具名字段对象，便于审计。
    return value  # 返回已经验证类型的 JSON 字典。


def write_new_text(path: Path, text: str) -> None:  # 定义禁止覆盖的 UTF-8 文本写入函数。
    """仅在目标不存在时以 LF 写入完整文本；存在同名文件即抛错。"""  # 函数说明强调不可覆盖和换行口径。
    require(not path.exists(), f"拒绝覆盖既有文件：{path}")  # 写入前再次检查目标，防止程序逻辑重名。
    path.parent.mkdir(parents=True, exist_ok=True)  # 只创建新 run 内所需父目录，不删除任何已有路径。
    with path.open("x", encoding="utf-8", newline="\n") as stream:  # x 模式提供操作系统级同名拒绝并固定 LF。
        stream.write(text)  # 一次写出完整内容，避免自行执行脚本时产生半行证据。


def write_new_json(path: Path, value: dict[str, Any]) -> None:  # 定义禁止覆盖的 JSON 对象写入函数。
    """以 UTF-8、两空格缩进和末尾换行写出机器证据。"""  # 函数说明给出序列化约定。
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"  # 保留中文字段值并生成稳定可读格式。
    write_new_text(path, rendered)  # 复用 x 模式写入，确保 JSON 也绝不覆盖。


def copy_new_verified(source: Path, destination: Path) -> str:  # 定义逐字节复制及双哈希核验函数。
    """复制普通文件到新目标并返回摘要；源、目标摘要不一致即中止。"""  # 函数说明明确输入、输出和失败条件。
    require(source.is_file(), f"待复制源文件不存在：{source}")  # 禁止缺件或目录进入复制流程。
    require(not destination.exists(), f"拒绝覆盖复制目标：{destination}")  # 目标必须尚不存在。
    destination.parent.mkdir(parents=True, exist_ok=True)  # 只在新 run 内建立目标父目录。
    source_hash = sha256_file(source)  # 复制前计算源摘要，捕获源身份。
    shutil.copy2(source, destination)  # 保留文件元数据且不对源内容做任何修改。
    destination_hash = sha256_file(destination)  # 复制后重新读取目标字节，验证存储闭合。
    require(destination_hash == source_hash, f"复制后字节哈希不一致：{source} -> {destination}")  # 任一字节差异均拒收。
    return source_hash  # 返回已同时代表源和复制件的摘要。


def parse_hash_ledger(path: Path) -> list[tuple[str, str]]:  # 定义 SHA-256 账本解析函数。
    """解析每行“摘要、两个空格、标签”格式并返回有序二元组。"""  # 函数说明固定账本语法和顺序语义。
    require(path.is_file(), f"缺少哈希账本：{path}")  # 账本缺失时不允许继续。
    rows: list[tuple[str, str]] = []  # 按文件原顺序保存摘要和标签，便于后续闭合审计。
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):  # 逐行解析并保留一基行号。
        require(bool(raw_line), f"哈希账本含空行：{path}:{line_number}")  # 空行可能隐藏截断或拼接错误，直接拒绝。
        pieces = raw_line.split("  ", 1)  # 只按第一个双空格分隔，允许 Windows 路径本身含单空格。
        require(len(pieces) == 2, f"哈希账本格式错误：{path}:{line_number}")  # 每行必须恰有摘要段和标签段。
        digest, label = pieces  # 拆出摘要和可为绝对路径或 run 相对路径的标签。
        require(bool(SHA256_PATTERN.fullmatch(digest)), f"哈希摘要格式错误：{path}:{line_number}")  # 摘要必须为规范小写 SHA-256。
        require(bool(label), f"哈希账本标签为空：{path}:{line_number}")  # 空标签无法绑定实际文件，直接拒绝。
        rows.append((digest, label))  # 保存经过语法验证的有序账本行。
    require(bool(rows), f"哈希账本不得为空：{path}")  # 空账本无法形成来源闭环。
    return rows  # 返回全部有序账本项供实际文件复算。


def is_within(path: Path, parent: Path) -> bool:  # 定义路径包含关系检查函数。
    """解析路径后判断其是否严格位于或等于指定父目录，防止相对路径逃逸。"""  # 函数说明给出安全目的。
    resolved_path = path.resolve()  # 消解点段和符号链接，得到实际目标。
    resolved_parent = parent.resolve()  # 消解允许父目录，建立统一比较基准。
    return resolved_path == resolved_parent or resolved_parent in resolved_path.parents  # 仅允许父目录本身或其真实后代。


def resolve_ledger_label(base_dir: Path, label: str) -> Path:  # 定义 U00/U01 账本标签到文件路径的解析函数。
    """SOURCE:: 标签和绝对路径直接绑定源文件；其余标签只允许位于账本 run 内。"""  # 函数说明区分两种标签语义。
    normalized_label = label[len("SOURCE::") :] if label.startswith("SOURCE::") else label  # 去掉 U01 源标签前缀但保留路径字节含义。
    candidate = Path(normalized_label)  # 将标签转换为 Windows Path，不做通配或环境变量展开。
    if candidate.is_absolute():  # U00 源账本及 U01 SOURCE:: 项使用绝对路径。
        return candidate  # 绝对源路径由后续存在性和哈希门禁约束。
    relative_candidate = base_dir / candidate  # 普通相对标签只能从当前证据 run 根解析。
    require(is_within(relative_candidate, base_dir), f"哈希账本相对路径逃逸：{label}")  # 拒绝 .. 或符号链接越界。
    return relative_candidate  # 返回已限定在 run 内的相对文件路径。


def verify_hash_ledger(path: Path, base_dir: Path) -> list[dict[str, Any]]:  # 定义逐项复算账本函数。
    """复算账本每个标签的实际 SHA-256，并返回可写入 preflight 的闭合明细。"""  # 函数说明给出副作用和返回结构。
    verified: list[dict[str, Any]] = []  # 保存每一行的标签、预期摘要和通过状态。
    for expected_hash, label in parse_hash_ledger(path):  # 按账本原顺序验证全部条目，不抽样。
        target = resolve_ledger_label(base_dir, label)  # 把安全标签解析为实际文件。
        actual_hash = sha256_file(target)  # 从当前磁盘字节重新计算摘要。
        require(actual_hash == expected_hash, f"哈希账本不闭合：{path} -> {label}")  # 任一摘要变化均中止。
        verified.append({"label": label, "sha256": actual_hash, "passed": True})  # 记录该行已闭合，供机器审计。
    return verified  # 返回全部通过的逐项结果。


def verify_artifact_closure(run_dir: Path) -> dict[str, Any]:  # 定义 U01 artifact 账本集合与摘要双闭合检查。
    """要求账本覆盖 run 内除账本自身外的每个文件，且不含不存在的多余标签。"""  # 函数说明强调集合和字节两层闭合。
    ledger_path = run_dir / "artifact_hashes.sha256"  # U01 固定 artifact 账本路径。
    rows = parse_hash_ledger(ledger_path)  # 先完成语法解析再检查标签集合。
    labels = [label for _, label in rows]  # 保留账本相对标签，用于唯一性和集合比较。
    require(len(labels) == len(set(labels)), f"artifact 账本含重复标签：{ledger_path}")  # 重复标签会掩盖漏项，直接拒绝。
    require(all(not Path(label).is_absolute() for label in labels), f"artifact 账本必须仅用相对路径：{ledger_path}")  # artifact 必须自包含于 U01 run。
    actual_labels = sorted(path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file() and path != ledger_path)  # 枚举除自引用账本外全部实际文件。
    require(sorted(labels) == actual_labels, f"U01 artifact 文件集合不闭合：{ledger_path}")  # 缺项、多项或路径大小写差异均拒绝。
    verified = verify_hash_ledger(ledger_path, run_dir)  # 集合闭合后逐文件复算全部摘要。
    return {"ledger_entry_count": len(rows), "actual_file_count_excluding_ledger": len(actual_labels), "passed": True, "verified": verified}  # 返回可审计统计和明细。


def validate_modes(value: str) -> int:  # 定义 argparse 模态阶数类型转换函数。
    """只接受不小于 80 且能被 40 整除的十进制整数。"""  # 函数说明给出完整数值约束。
    try:  # 捕获非整数输入并转换为 argparse 可读错误。
        parsed = int(value, 10)  # 强制十进制解释，避免 0x 或其他隐式进制。
    except ValueError as exc:  # 只有字符串不是合法十进制整数时进入。
        raise argparse.ArgumentTypeError("--modes 必须为十进制整数。") from exc  # 向用户报告参数错误且保留原异常链。
    if parsed < MINIMUM_MODES or parsed % MODE_MULTIPLE != 0:  # 同时执行下限和 40 倍数门禁。
        raise argparse.ArgumentTypeError("--modes 必须 >= 80 且为 40 的整数倍。")  # 参数不合规时在创建 run 前退出。
    return parsed  # 返回已经通过全部阶数约束的整数。


def validate_u01_run_name(value: str) -> str:  # 定义 argparse U01 目录名类型检查函数。
    """只接受 ultra_runs 直接子目录的标准 U01 名称，不接受路径、点段或绝对地址。"""  # 函数说明给出路径安全边界。
    if Path(value).name != value or "/" in value or "\\" in value:  # 拒绝任何目录分隔符和路径包装。
        raise argparse.ArgumentTypeError("--u01-run 只接受 ultra_runs 下的目录名，不接受路径。")  # 给出明确修正提示。
    if not U01_NAME_PATTERN.fullmatch(value):  # 目录名还必须符合标准 U01 微秒时间戳协议。
        raise argparse.ArgumentTypeError("--u01-run 必须形如 U01_UNIT_TESTS_YYYYMMDDTHHMMSSffffffZ。")  # 拒绝非 U01 或无微秒封板名。
    return value  # 返回已确认只是安全目录名的原字符串。


def count_apdl_commands(text: str, command: str) -> int:  # 定义冻结 APDL 行首命令计数函数。
    """按大小写不敏感的严格行首“COMMAND,”统计，不忽略前导空格。"""  # 函数说明对应用户要求的 ^COMMAND, 身份口径。
    pattern = re.compile(rf"^{re.escape(command)},", re.IGNORECASE | re.MULTILINE)  # 构造只匹配真实行首命令的表达式。
    return len(pattern.findall(text))  # 返回全部严格行首命令出现次数。


def read_apdl_text(path: Path) -> str:  # 定义冻结 APDL 严格文本读取函数。
    """以 UTF-8-sig 解码 APDL；编码错误直接传播并阻止准备。"""  # 函数说明禁止 errors=replace 造成身份误判。
    return path.read_text(encoding="utf-8-sig")  # 只读源文件并允许可选 BOM，不写回或规范化换行。


def memory_snapshot() -> dict[str, int | bool]:  # 定义 Windows 实时物理内存快照函数。
    """返回容量、负载和两档门禁；门禁真假均不会触发 MAPDL。"""  # 函数说明明确资源信息只用于记录。
    status = MemoryStatusEx()  # 分配零初始化 ABI 结构供 Windows API 填充。
    status.dwLength = ctypes.sizeof(MemoryStatusEx)  # 按 API 契约写入结构字节长度。
    success = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)))  # 调用只读系统 API 获取实时容量。
    require(success, "GlobalMemoryStatusEx 调用失败，无法记录实时内存快照。")  # 资源证据缺失时拒绝生成声称完整的 preflight。
    available = int(status.ullAvailPhys)  # 把 ctypes 数值转为可 JSON 序列化的 Python 整数。
    return {  # 返回全部单位明确的内存快照和非执行门禁。
        "available": True,  # 表示本次 Windows API 快照读取成功。
        "total_physical_bytes": int(status.ullTotalPhys),  # 记录总物理内存，单位 byte。
        "available_physical_bytes": available,  # 记录准备瞬间可用物理内存，单位 byte。
        "available_page_file_bytes": int(status.ullAvailPageFile),  # 记录可用提交容量，单位 byte。
        "memory_load_percent": int(status.dwMemoryLoad),  # 记录物理内存负载百分比。
        "minimum_available_memory_bytes": MINIMUM_MEMORY_BYTES,  # 记录执行期最低 8 GiB 门槛。
        "comfortable_available_memory_bytes": COMFORTABLE_MEMORY_BYTES,  # 记录执行期舒适 10 GiB 参考值。
        "memory_ready": available >= MINIMUM_MEMORY_BYTES,  # 只计算布尔值，不据此执行或拒绝 prepare。
        "memory_comfortable": available >= COMFORTABLE_MEMORY_BYTES,  # 只供人工排程判断舒适余量。
        "execution_attempted": False,  # 明确本脚本无论门禁真假均未执行 MAPDL。
    }  # 结束内存快照对象。


def disk_snapshot() -> dict[str, int | bool | str]:  # 定义项目所在卷的实时磁盘空间快照函数。
    """返回 D 盘容量和 32 GiB 执行门禁；不足不影响 prepare-only 封板。"""  # 函数说明给出门禁用途和非阻断语义。
    usage = shutil.disk_usage(PROJECT_ROOT)  # 查询项目实际所在卷，避免硬编码盘符后项目迁移失真。
    return {  # 返回可直接写入 preflight 的磁盘证据。
        "volume_anchor": PROJECT_ROOT.anchor,  # 记录被查询卷的根锚点，当前预期为 D:\。
        "total_bytes": int(usage.total),  # 记录卷总容量，单位 byte。
        "used_bytes": int(usage.used),  # 记录卷已用容量，单位 byte。
        "free_bytes": int(usage.free),  # 记录准备瞬间可用容量，单位 byte。
        "minimum_free_bytes_for_execution": MINIMUM_DISK_BYTES,  # 记录 32 GiB 保守执行门槛。
        "disk_ready": int(usage.free) >= MINIMUM_DISK_BYTES,  # 只记录资源真假，不阻止本脚本准备输入。
        "budget_basis": "historical_incomplete_40_mode_attempt_7.857_GiB_times_about_4",  # 说明 32 GiB 来自历史规模外推。
        "execution_attempted": False,  # 明确磁盘是否充足都不会由本脚本启动求解。
    }  # 结束磁盘快照对象。


def validate_u00() -> dict[str, Any]:  # 定义固定 U00、依赖图、冻结源和根审计联合门禁。
    """验证 PASS_A、MAPDL 身份、11 项 B00 图边、源哈希和 legacy 反混线指标。"""  # 函数说明涵盖所有输入与输出契约。
    require(U00_RUN.is_dir(), f"缺少固定 U00 目录：{U00_RUN}")  # 固定门禁目录不存在时不得改选其他 U00。
    status = read_json(U00_RUN / "U00_status.json")  # 读取 U00 三态状态证据。
    manifest = read_json(U00_RUN / "manifest.json")  # 读取 U00 执行环境和模型线清单。
    environment = read_json(U00_RUN / "mapdl_environment.json")  # 读取 U00 MAPDL 路径与版本封板。
    graph = read_json(U00_RUN / "input_dependency_graph.json")  # 读取唯一依赖图并从中提取 B00 顺序。
    require(status.get("status") == "PASS_A", "固定 U00 状态不是 PASS_A。")  # 只有 A 级完整源门禁允许进入 B00。
    require(manifest.get("status") == "PASSED", "固定 U00 manifest 状态不是 PASSED。")  # 清单自身也必须声明通过。
    require(environment.get("executable_sha256") == MAPDL_SHA256, "U00 environment 的 MAPDL 哈希不匹配。")  # 环境摘要必须等于固定值。
    require(manifest.get("executable_sha256") == MAPDL_SHA256, "U00 manifest 的 MAPDL 哈希不匹配。")  # manifest 摘要必须与环境一致。
    require(Path(str(environment.get("executable", ""))).resolve() == MAPDL_EXE.resolve(), "U00 environment 的 MAPDL 路径不匹配。")  # 禁止换用其他安装路径。
    executable_hash = sha256_file(MAPDL_EXE)  # 从当前可执行文件字节重新计算摘要。
    require(executable_hash == MAPDL_SHA256, "当前 MAPDL 可执行文件字节哈希不匹配固定 U00。")  # 安装文件变化时 fail-closed。
    u00_source_ledger = verify_hash_ledger(U00_RUN / "source_hashes.sha256", U00_RUN)  # 复算 U00 全部源账本条目。
    raw_nodes = graph.get("nodes")  # 读取依赖图节点数组以建立 target 到摘要映射。
    raw_edges = graph.get("generated_edges")  # 读取依赖图生成边数组以筛选 B00 冻结关系。
    require(isinstance(raw_nodes, list), "U00 dependency graph 缺少 nodes 数组。")  # 图节点必须为数组。
    require(isinstance(raw_edges, list), "U00 dependency graph 缺少 generated_edges 数组。")  # 图边必须为数组。
    node_hashes: dict[str, str] = {}  # 按节点 id 保存图中唯一 SHA-256。
    for node in raw_nodes:  # 遍历全部图节点，防止目标节点重复身份。
        require(isinstance(node, dict), "U00 dependency graph 含非对象节点。")  # 每个节点必须为对象。
        node_id = node.get("id")  # 取出图节点的绝对路径或虚拟标识。
        node_hash = node.get("sha256")  # 取出图节点封存的摘要。
        require(isinstance(node_id, str) and bool(node_id), "U00 dependency graph 节点 id 无效。")  # 节点必须有非空字符串 id。
        require(isinstance(node_hash, str) and bool(SHA256_PATTERN.fullmatch(node_hash)), f"U00 图节点哈希无效：{node_id}")  # 节点摘要必须规范。
        require(node_id not in node_hashes, f"U00 dependency graph 节点 id 重复：{node_id}")  # 重复节点会造成摘要歧义。
        node_hashes[node_id] = node_hash  # 保存经过验证的节点摘要。
    selected_edges: list[dict[str, Any]] = []  # 保存精确匹配 B00 legacy 关系的十一条边。
    for edge in raw_edges:  # 遍历所有 B00 和 C10 等生成边。
        require(isinstance(edge, dict), "U00 dependency graph 含非对象边。")  # 每条边必须是字段对象。
        if edge.get("source") == GRAPH_SOURCE_ID and edge.get("relation") == GRAPH_RELATION:  # 只选择固定源和固定 legacy 关系。
            selected_edges.append(edge)  # 保留 B00 边，其他模型线绝不进入依赖列表。
    require(len(selected_edges) == DEPENDENCY_COUNT, f"B00 legacy 图边必须恰为 {DEPENDENCY_COUNT} 条。")  # 边数量不多不少。
    selected_edges.sort(key=lambda edge: int(edge.get("order", -1)))  # 按显式 order 排序，不依赖 JSON 原始排列。
    orders = [edge.get("order") for edge in selected_edges]  # 提取排序后的阶次供连续性检查。
    require(orders == list(range(1, DEPENDENCY_COUNT + 1)), "B00 legacy 图边 order 必须严格为 1..11。")  # 拒绝缺号、重复或乱序。
    expected_builder = (PROJECT_ROOT / "builder" / "generated" / "apply_finite_gates_and_passages_v2.inp").resolve()  # 第六项必须绑定根 builder/generated 冻结文件。
    expected_mass = (PROJECT_ROOT / "apply_dynamic_mass21_spatialized_v2.inp").resolve()  # 第十项必须绑定项目根 MASS21 冻结文件。
    basenames: set[str] = set()  # 使用大小写折叠 basename 集合检查 solver 复制冲突。
    dependencies: list[dict[str, Any]] = []  # 保存十一项经过图哈希和当前字节双验证的依赖。
    for edge in selected_edges:  # 按 order 1..11 逐项验证目标。
        order = int(edge["order"])  # 将已验证连续的阶次转换为整数。
        target_value = edge.get("target")  # 读取图边目标路径字符串。
        require(isinstance(target_value, str) and bool(target_value), f"B00 order {order} 缺少 target。")  # 每条边必须有非空目标。
        lowered_path = target_value.casefold()  # 对完整路径做大小写折叠供反混线检查。
        require(not any(token in lowered_path for token in FORBIDDEN_PATH_TOKENS), f"B00 order {order} 命中禁用 regenerated/MPC/C10 路径：{target_value}")  # 诊断或再生成路径一律拒绝。
        target = Path(target_value)  # 把图目标转为本机绝对 Path。
        require(target.is_absolute(), f"B00 order {order} 图目标不是绝对路径：{target}")  # U00 图目标必须显式绑定绝对源。
        require(target.is_file(), f"B00 order {order} 源文件不存在：{target}")  # 缺少任何 include 均不得准备。
        require(target_value in node_hashes, f"B00 order {order} 目标缺少图节点摘要：{target}")  # 每条边必须由图节点提供哈希。
        graph_hash = node_hashes[target_value]  # 读取该目标的 U00 图摘要。
        actual_hash = sha256_file(target)  # 复算当前源文件字节摘要。
        require(actual_hash == graph_hash, f"B00 order {order} 当前源哈希与 U00 图不匹配：{target}")  # 任一源被改写立即拒绝。
        folded_basename = target.name.casefold()  # Windows solver 目录按大小写不敏感检查同名。
        require(folded_basename not in basenames, f"B00 solver basename 冲突：{target.name}")  # 防止复制时同名覆盖。
        basenames.add(folded_basename)  # 登记本项 basename 供后续冲突检测。
        dependencies.append({"order": order, "source": str(target.resolve()), "basename": target.name, "sha256": actual_hash, "graph_sha256": graph_hash})  # 保存完整有序身份。
    require(Path(dependencies[5]["source"]).resolve() == expected_builder, "B00 第 6 项不是根 builder/generated 冻结输入。")  # 强制 legacy CERIG 根源。
    require(Path(dependencies[9]["source"]).resolve() == expected_mass, "B00 第 10 项不是项目根 MASS21 冻结输入。")  # 强制 legacy MASS21 根源。
    texts = [read_apdl_text(Path(item["source"])) for item in dependencies]  # 严格解码十一项 APDL 供命令身份扫描。
    scan_counts = {  # 保存分项和合计命令计数，供 preflight 与 manifest 同时引用。
        "order_3_cp": count_apdl_commands(texts[2], "CP"),  # 第三项 downpull 的 CP 行首命令数。
        "order_3_d": count_apdl_commands(texts[2], "D"),  # 第三项 downpull 的 D 行首命令数。
        "order_4_d": count_apdl_commands(texts[3], "D"),  # 第四项 constraints 的 D 行首命令数。
        "order_6_cerig": count_apdl_commands(texts[5], "CERIG"),  # 第六项根 builder 的 CERIG 行首命令数。
        "order_7_d": count_apdl_commands(texts[6], "D"),  # 第七项 ROTY 文件的 D 行首命令数。
        "order_10_en": count_apdl_commands(texts[9], "EN"),  # 第十项 MASS21 文件的 EN 行首命令数。
    }  # 结束源扫描计数字典。
    scan_counts["d_total_orders_3_4_7"] = scan_counts["order_3_d"] + scan_counts["order_4_d"] + scan_counts["order_7_d"]  # 计算三项 D 命令总数闭合。
    builder_word_counts = {  # 使用全文单词边界执行额外反混线扫描。
        "CERIG": len(re.findall(r"\bCERIG\b", texts[5], re.IGNORECASE)),  # builder 文本中 CERIG 单词总数必须恰等于真实命令数。
        "MPC184": len(re.findall(r"\bMPC184\b", texts[5], re.IGNORECASE)),  # legacy builder 文本中不得出现 MPC184。
        "PNLT": len(re.findall(r"\bPNLT\b", texts[5], re.IGNORECASE)),  # legacy builder 文本中不得出现 PNLT 罚参数。
    }  # 结束 builder 全文反混线计数。
    require(scan_counts["order_3_cp"] == 12, "B00 第 3 项 ^CP, 数量必须为 12。")  # downpull CP 身份门禁。
    require(scan_counts["order_3_d"] == 12, "B00 第 3 项 ^D, 数量必须为 12。")  # downpull D 身份门禁。
    require(scan_counts["order_4_d"] == 1096, "B00 第 4 项 ^D, 数量必须为 1096。")  # constraints D 身份门禁。
    require(scan_counts["order_7_d"] == 2860, "B00 第 7 项 ^D, 数量必须为 2860。")  # ROTY D 身份门禁。
    require(scan_counts["d_total_orders_3_4_7"] == EXPECTED_TOTAL_D_COUNT, "B00 第 3/4/7 项 D 命令合计必须为 3968。")  # 分项之外再做总量闭合。
    require(scan_counts["order_6_cerig"] == EXPECTED_CERIG_COUNT, "B00 第 6 项 ^CERIG, 数量必须为 5078。")  # 根 builder 命令门禁。
    require(scan_counts["order_10_en"] == EXPECTED_TYPE_COUNTS[71], "B00 第 10 项 ^EN, 数量必须为 33003。")  # MASS21 单元生成命令门禁。
    require(builder_word_counts == {"CERIG": EXPECTED_CERIG_COUNT, "MPC184": 0, "PNLT": 0}, "根 builder 全文 CERIG/MPC184/PNLT 反混线门禁失败。")  # 全文身份必须完全匹配。
    build_audit_path = PROJECT_ROOT / "builder" / "generated" / "build_audit.json"  # 根 builder 审计是 legacy 拓扑唯一旁证。
    mass_audit_path = PROJECT_ROOT / "mass21_spatialization_audit_v2.json"  # 项目根质量审计是 legacy MASS21 唯一旁证。
    build_audit = read_json(build_audit_path)  # 读取根 builder 审计。
    mass_audit = read_json(mass_audit_path)  # 读取根质量空间化审计。
    require(build_audit.get("status") == "PASS", "根 build_audit 状态不是 PASS。")  # builder 审计必须通过。
    build_audit_body = build_audit.get("audit")  # 读取 builder 详细计数对象。
    require(isinstance(build_audit_body, dict), "根 build_audit 缺少 audit 对象。")  # 审计明细必须存在。
    require(build_audit_body.get("generated_constraint_count") == EXPECTED_CERIG_COUNT, "根 build_audit generated_constraint_count 不是 5078。")  # CERIG 旁证必须闭合。
    require(mass_audit.get("status") == "PASS", "根 mass audit 状态不是 PASS。")  # 质量审计必须通过。
    mass_after = mass_audit.get("after_spatialized_mass21")  # 读取空间化后 MASS21 指标。
    mass_closure = mass_audit.get("mass_closure")  # 读取全模质量闭合指标。
    input_binding = mass_audit.get("input_binding")  # 读取质量生成输入绑定对象。
    require(isinstance(mass_after, dict) and mass_after.get("node_count") == EXPECTED_TYPE_COUNTS[71], "根 mass audit MASS21 节点数不是 33003。")  # 质量节点规模必须闭合。
    require(isinstance(mass_closure, dict) and mass_closure.get("predicted_full_model_mass_tonne") == EXPECTED_MASS_TONNE, "根 mass audit 全模质量不是 4108.46690758 tonne。")  # 质量基准必须逐值匹配。
    require(isinstance(input_binding, dict), "根 mass audit 缺少 input_binding。")  # 质量 lineage 绑定必须存在。
    authoritative_items = input_binding.get("authoritative_items")  # 读取质量审计中其他权威输入绑定，用于确认结构完整。
    require(isinstance(authoritative_items, dict), "根 mass audit 缺少 authoritative_items。")  # 权威输入集合必须为对象。
    generated_nodes_binding = input_binding.get("generated_nodes")  # generated_nodes 与 authoritative_items 同级，读取其路径、大小和摘要绑定。
    require(isinstance(generated_nodes_binding, dict), "根 mass audit 缺少 generated_nodes 绑定。")  # generated_nodes 绑定不得缺失。
    root_generated_nodes = (PROJECT_ROOT / "builder" / "generated" / "generated_nodes.csv").resolve()  # legacy 质量只能绑定根 builder/generated 节点表。
    require(Path(str(generated_nodes_binding.get("path", ""))).resolve() == root_generated_nodes, "mass audit 的 generated_nodes 未绑定根 builder/generated。")  # 路径必须指向根冻结节点表。
    require(int(generated_nodes_binding.get("size_bytes", -1)) == root_generated_nodes.stat().st_size, "mass audit 的 generated_nodes size 不闭合。")  # 大小旁证必须匹配当前文件。
    require(str(generated_nodes_binding.get("sha256", "")) == sha256_file(root_generated_nodes), "mass audit 的 generated_nodes 哈希不闭合。")  # 字节摘要旁证必须匹配。
    return {  # 返回后续复制、清单和 preflight 需要的全部已验证上下文。
        "status": status,  # 保留 U00 状态对象供 lineage 摘要引用。
        "manifest": manifest,  # 保留 U00 manifest 供 MAPDL 版本和单位引用。
        "environment": environment,  # 保留 U00 环境对象供执行配置引用。
        "dependencies": dependencies,  # 返回 order 1..11 的冻结源清单。
        "scan_counts": scan_counts,  # 返回分项和合计源扫描计数。
        "builder_word_counts": builder_word_counts,  # 返回 builder 全文反混线计数。
        "build_audit_path": build_audit_path.resolve(),  # 返回需复制的根 builder 审计路径。
        "mass_audit_path": mass_audit_path.resolve(),  # 返回需复制的根质量审计路径。
        "u00_source_ledger_entry_count": len(u00_source_ledger),  # 返回 U00 源账本闭合条目数。
        "mapdl_executable_sha256": executable_hash,  # 返回当前实际 MAPDL 摘要。
    }  # 结束 U00 验证上下文。


def validate_u01(run_name: str) -> dict[str, Any]:  # 定义显式 U01 运行及两份哈希账本联合门禁。
    """要求指定目录 PASSED 8/8、parent 固定 U00，且 source/artifact 账本完全闭合。"""  # 函数说明给出全部输入契约。
    run_dir = ULTRA_RUNS_ROOT / run_name  # 只从 ultra_runs 根拼接已验证的纯目录名。
    require(run_dir.is_dir(), f"显式 U01 目录不存在：{run_dir}")  # 不按最新目录回退。
    require(run_dir.resolve().parent == ULTRA_RUNS_ROOT.resolve(), f"U01 目录不是 ultra_runs 直接子目录：{run_dir}")  # 拒绝符号链接或路径逃逸。
    status = read_json(run_dir / "U01_status.json")  # 读取 U01 八项门禁状态。
    manifest = read_json(run_dir / "manifest.json")  # 读取 U01 lineage 与执行环境清单。
    require(status.get("status") == "PASSED", "显式 U01 状态不是 PASSED。")  # 套件必须整体通过。
    require(status.get("passed_count") == 8 and status.get("required_count") == 8, "显式 U01 不是 PASSED 8/8。")  # 通过数与要求数必须都为八。
    tests = status.get("tests")  # 读取逐测试状态数组。
    require(isinstance(tests, list) and len(tests) == 8, "显式 U01 tests 数组不是 8 项。")  # 不允许缺项或额外项。
    require(all(isinstance(test, dict) and test.get("passed") is True for test in tests), "显式 U01 至少一项 test 未通过。")  # 八项逐项布尔值必须为真。
    require(status.get("suite_id") == run_name, "U01_status suite_id 与 --u01-run 不一致。")  # 防止目录和内容错配。
    require(manifest.get("suite_id") == run_name, "U01 manifest suite_id 与 --u01-run 不一致。")  # manifest 也必须绑定同一目录。
    require(manifest.get("status") == "PASSED", "U01 manifest 状态不是 PASSED。")  # 最终 manifest 必须完成回写。
    require(manifest.get("parent_run") == U00_RUN_NAME, "U01 parent_run 不是固定 U00。")  # lineage 必须直接指向固定 U00。
    require(manifest.get("executable_sha256") == MAPDL_SHA256, "U01 MAPDL 哈希与固定 U00 不一致。")  # U01 执行程序必须同源。
    source_verified = verify_hash_ledger(run_dir / "source_hashes.sha256", run_dir)  # 复算 U01 源与输入快照账本。
    artifact_closure = verify_artifact_closure(run_dir)  # 同时核对 U01 artifact 文件集合和全部摘要。
    return {  # 返回 B00 lineage 所需的 U01 已验证信息。
        "run_name": run_name,  # 保留显式目录名。
        "run_dir": run_dir.resolve(),  # 保留解析后的直接子目录绝对路径。
        "status": status,  # 保留 U01 状态对象。
        "manifest": manifest,  # 保留 U01 manifest 对象。
        "source_ledger_entry_count": len(source_verified),  # 记录复算通过的 source 行数。
        "artifact_ledger_entry_count": artifact_closure["ledger_entry_count"],  # 记录 artifact 闭合文件数。
        "artifact_actual_file_count_excluding_ledger": artifact_closure["actual_file_count_excluding_ledger"],  # 记录实际集合规模。
    }  # 结束 U01 验证上下文。


def add_apdl(lines: list[str], command: str, explanation: str) -> None:  # 定义普通 APDL 命令与中文前置注释追加函数。
    """先写独立中文注释行，再写不带行尾注释的命令，避免命令字段被注释污染。"""  # 函数说明明确生成顺序和输出约束。
    lines.append(f"! {explanation}")  # 每条生成命令前写用途、条件或单位说明。
    lines.append(command)  # 紧接注释写入原生 APDL 命令，不添加可能改变解析的尾注。


def add_vwrite(lines: list[str], command: str, format_line: str, explanation: str) -> None:  # 定义 *VWRITE 与 Fortran 格式行的安全追加函数。
    """中文说明写在 *VWRITE 之前；命令和裸格式行必须绝对相邻。"""  # 函数说明强调 MAPDL 对格式行相邻性的硬要求。
    lines.append(f"! {explanation}")  # 在 *VWRITE 之前说明字段、单位、精度和用途。
    lines.append("! 下一条 *VWRITE 与其后裸 Fortran 格式行必须相邻，二者之间不得插入注释。")  # 显式记录相邻规则但不插到命令和格式之间。
    lines.append(command)  # 写入 *VWRITE 命令及全部参数。
    lines.append(format_line)  # 立即写入无注释的裸格式行，避免 warning 或被当作普通命令。


def add_reject_gate(lines: list[str], parameter: str, operator: str, threshold: str, reason: str, explanation: str) -> None:  # 定义单参数 fail-closed APDL 门禁生成函数。
    """条件成立时覆盖唯一 gate 状态、恢复主输出并立即 /EXIT,NOSAVE。"""  # 函数说明给出输入含义和拒绝路径。
    add_apdl(lines, f"*IF,{parameter},{operator},{threshold},THEN", explanation)  # 生成明确比较条件并进入拒绝分支。
    add_apdl(lines, "/OUTPUT,b00_gate_status,txt", "把本次唯一拒绝原因写入 b00_gate_status.txt，覆盖先前 RUNNING 阶段状态。")  # 打开唯一状态文件。
    add_apdl(lines, f"/COM,STATUS=REJECTED REASON={reason}", f"固定拒绝原因 {reason} 供外部审计按字段解析。")  # 写出机器可读拒绝状态。
    add_apdl(lines, "/OUTPUT", "恢复 MAPDL 主输出，避免退出摘要滞留在 gate 状态文件。")  # 关闭状态重定向。
    add_apdl(lines, "/EXIT,NOSAVE", "门禁失败时立即退出且不保存数据库，禁止错误基态进入后续阶段。")  # 立即停止批处理。
    add_apdl(lines, "*ENDIF", "结束当前 fail-closed 条件分支；通过时继续下一门禁。")  # 闭合条件结构。


def build_main_input(jobname: str, modes: int, dependencies: list[dict[str, Any]]) -> str:  # 定义完整 B00 静力—扰动模态主输入构造函数。
    """返回未执行的 UTF-8 APDL 文本；十一项 /INPUT 严格按 U00 order 1..11。"""  # 函数说明给出输入、输出和不可执行约束。
    require(len(dependencies) == DEPENDENCY_COUNT, "构造主输入时依赖数量不是 11。")  # 防止调用方绕过 U00 验证。
    require([item["order"] for item in dependencies] == list(range(1, DEPENDENCY_COUNT + 1)), "构造主输入时依赖 order 不是 1..11。")  # 防止装配次序漂移。
    lines: list[str] = []  # 按实际 MAPDL 执行顺序累积注释和命令。
    lines.append("! ============================================================================")  # 写入输入头分隔线便于人工审阅。
    lines.append("! B00_LEGACY_COMPLETE：只使用 U00 图封存的十一项 legacy APDL。")  # 声明唯一模型线和依赖来源。
    lines.append("! 坐标为 X 顺桥、Y 横桥、Z 竖向；单位为 N、mm、tonne、s。")  # 声明坐标和一致单位制。
    lines.append("! 本文件由 prepare-only 编排器生成；生成动作本身未启动 MAPDL。")  # 区分准备与未来执行。
    lines.append("! ============================================================================")  # 结束输入头分隔线。
    add_apdl(lines, "/CLEAR,START", "清空未来 MAPDL 会话并按封板要求读取标准启动设置。")  # 使用用户指定的 /CLEAR,START。
    add_apdl(lines, f"/FILNAME,{jobname}", "设置本 run 唯一 ASCII jobname，所有 RST/RSTP/MODE/FULL 文件均由此绑定。")  # 绑定唯一作业前缀。
    add_apdl(lines, "/TITLE,B00 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL", "设置可辨识英文标题，避免依赖本地代码页。")  # 标记作业用途。
    add_apdl(lines, "/OUTPUT,b00_gate_status,txt", "初始化未来求解器唯一 gate 状态文件。")  # 打开初始状态输出。
    add_apdl(lines, "/COM,STATUS=RUNNING PHASE=ASSEMBLY", "RUNNING 仅表示未来 MAPDL 已读入主输入，不表示任何工程门禁通过。")  # 写入初始阶段状态。
    add_apdl(lines, "/OUTPUT", "恢复未来 MAPDL 主输出文件。")  # 关闭初始状态重定向。
    for item in dependencies:  # 按 order 1..11 逐项写出 solver 内同 basename include。
        stem = Path(str(item["basename"])).stem  # /INPUT 使用不含扩展名的 ASCII 文件干名。
        add_apdl(lines, f"/INPUT,{stem},inp", f"按 U00 dependency graph order {item['order']} 读取冻结 include；其 SHA-256 已在准备期复算闭合。")  # 写入有序 include。
    add_apdl(lines, "/PREP7", "进入前处理器读取完整装配后的节点和单元身份。")  # 开始装配规模门禁。
    add_apdl(lines, "ALLSEL,ALL", "恢复全部节点和单元选择，保证计数覆盖完整模型。")  # 防止 include 遗留局部选择。
    add_apdl(lines, "*GET,B00_NCOUNT,NODE,0,COUNT", "读取完整节点总数，预期 109086。")  # 获取节点规模。
    add_apdl(lines, "*GET,B00_ECOUNT,ELEM,0,COUNT", "读取完整单元总数，预期 172994。")  # 获取单元规模。
    for type_id in (4, 6, 70, 71):  # 依次统计 LINK180、BEAM188 和 legacy 新增构件/质量类型。
        add_apdl(lines, f"ESEL,S,TYPE,,{type_id}", f"只选择 TYPE {type_id} 单元，用于封板分类型计数。")  # 建立当前类型选择。
        add_apdl(lines, f"*GET,B00_T{type_id},ELEM,0,COUNT", f"读取 TYPE {type_id} 单元数，预期 {EXPECTED_TYPE_COUNTS[type_id]}。")  # 获取当前类型规模。
    add_apdl(lines, "ALLSEL,ALL", "类型计数后恢复全部实体，避免选择状态影响静力求解。")  # 恢复完整选择。
    add_apdl(lines, "/OUTPUT,b00_topology_counts,txt", "把节点、单元和四类 TYPE 数量写入独立拓扑证据。")  # 打开拓扑输出。
    add_vwrite(lines, "*VWRITE,B00_NCOUNT,B00_ECOUNT,B00_T4,B00_T6", "('NODE_COUNT=',F12.0,', ELEMENT_COUNT=',F12.0,', TYPE4=',F12.0,', TYPE6=',F12.0)", "第一行写节点、单元、TYPE4 和 TYPE6 计数，全部为整数型数量。")  # 输出第一组拓扑数。
    add_vwrite(lines, "*VWRITE,B00_T70,B00_T71", "('TYPE70=',F12.0,', TYPE71=',F12.0)", "第二行写 TYPE70 有限构件和 TYPE71 MASS21 计数。")  # 输出第二组拓扑数。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束拓扑计数文件。")  # 关闭拓扑输出。
    add_apdl(lines, "/OUTPUT,b00_constraint_equations,txt", "把全部约束方程写入独立审计文件，供执行后确认 CERIG 展开结果。")  # 打开约束方程证据。
    add_apdl(lines, "CELIST,ALL", "列出全部当前约束方程；MAPDL 不提供可靠的通用 CE COUNT 查询。")  # 输出约束方程。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束约束方程证据文件。")  # 关闭约束输出。
    add_apdl(lines, "/OUTPUT,b00_coupled_dof,txt", "把全部 CP 耦合自由度写入独立执行期审计文件。")  # 打开 CP 列表证据。
    add_apdl(lines, "CPLIST,ALL", "列出全部当前 CP 定义，供执行后与准备期 12 条 CP 身份闭合。")  # 输出全部 CP。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束 CP 列表证据文件。")  # 关闭 CP 输出。
    add_apdl(lines, "/OUTPUT,b00_displacement_constraints,txt", "把全部显式位移约束写入独立执行期审计文件。")  # 打开 D 列表证据。
    add_apdl(lines, "DLIST,ALL", "列出全部当前 D 定义，供执行后与准备期 3968 条 D 身份闭合。")  # 输出全部 D。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束 D 列表证据文件。")  # 关闭 D 输出。
    add_reject_gate(lines, "B00_NCOUNT", "NE", str(EXPECTED_NODE_COUNT), "TOPOLOGY_NODE_COUNT_MISMATCH", "节点总数不等于 109086 时拒绝，防止缺 include 或模型线混入。")  # 节点总数硬门禁。
    add_reject_gate(lines, "B00_ECOUNT", "NE", str(EXPECTED_ELEMENT_COUNT), "TOPOLOGY_ELEMENT_COUNT_MISMATCH", "单元总数不等于 172994 时拒绝。")  # 单元总数硬门禁。
    for type_id in (4, 6, 70, 71):  # 对四类封板 TYPE 分别生成硬门禁。
        add_reject_gate(lines, f"B00_T{type_id}", "NE", str(EXPECTED_TYPE_COUNTS[type_id]), f"TYPE_{type_id}_COUNT_MISMATCH", f"TYPE {type_id} 单元数不等于封板值 {EXPECTED_TYPE_COUNTS[type_id]} 时拒绝。")  # 分类型硬门禁。
    add_apdl(lines, "FINISH", "离开前处理器；全部装配身份门禁通过后才允许建立静力基态。")  # 结束拓扑阶段。
    add_apdl(lines, "/SOLU", "进入求解处理器，开始从零荷载加载的 LS1 非线性静力。")  # 开始 LS1。
    add_apdl(lines, "ANTYPE,STATIC", "选择静力分析类型，禁止复用任何既有数据库或重启动文件。")  # 明确全新静力。
    add_apdl(lines, "STABILIZE,OFF", "LS1 显式关闭稳定化，与 legacy 从零物理链一致并使全历程 STEN 目标为零。")  # 明确 LS1 不使用人工稳定化。
    add_apdl(lines, "NLGEOM,ON", "启用大变形几何非线性，更新索网平衡和切线刚度。")  # 启用几何非线性。
    add_apdl(lines, "PSTRES,ON", "保留预应力效应供后续线性扰动模态使用。")  # 启用预应力。
    add_apdl(lines, "NROPT,FULL", "每次平衡迭代使用完整 Newton-Raphson 切线更新。")  # 选择完整牛顿法。
    add_apdl(lines, "KBC,0", "LS1 从零到完整重力采用斜坡加载。")  # 设置斜坡加载。
    add_apdl(lines, "AUTOTS,ON", "LS1 允许自动时间步在收敛困难时细分。")  # 启用自动步长。
    add_apdl(lines, "LNSRCH,ON", "启用线搜索抑制高刚度约束下的 Newton 过冲。")  # 启用线搜索。
    add_apdl(lines, "PRED,OFF", "关闭位移预测器，避免索网初始加载阶段预测放大。")  # 关闭预测。
    add_apdl(lines, "NEQIT,100", "每个 LS1 子步最多允许 100 次平衡迭代。")  # 设置迭代上限。
    add_apdl(lines, f"ACEL,0,0,{GRAVITY_MM_S2:g}", "施加 +Z 参考加速度 9806 mm/s²，使结构承受 -Z 重力。")  # 施加完整重力。
    add_apdl(lines, "TIME,1", "把完整重力加载终点定义为伪时间 1.0。")  # 设置 LS1 终点。
    add_apdl(lines, "NSUBST,20,200,20", "采用父静力实际封板配置：初始 20、最多 200、最少 20 子步，单步不大于 0.05。")  # 使用更正后的实际配置。
    add_apdl(lines, "OUTRES,ALL,LAST", "仅保存 LS1 末完整场，控制全桥结果体积。")  # 设置静力结果输出。
    add_apdl(lines, "OUTRES,VENG,LAST", "显式保存 LS1 末 SENE/STEN 单元能量供硬门禁。")  # 保存能量结果。
    add_apdl(lines, "OUTRES,RSOL,LAST", "显式保存 LS1 末约束反力供重力闭合。")  # 保存反力。
    add_apdl(lines, "RESCONTROL,DEFINE,ALL,LAST", "只保留每载荷步末重启动帧，确保 LS2 扰动点可追溯。")  # 设置重启动帧。
    add_apdl(lines, "SOLVE", "执行 LS1 从零到完整重力的非线性静力求解。")  # 未来执行 LS1。
    add_apdl(lines, "*GET,B00_CNVG1,ACTIVE,0,SOLU,CNVG", "读取 LS1 最后一次求解收敛标志；数值 1 才可继续。")  # 获取 LS1 收敛状态。
    add_reject_gate(lines, "B00_CNVG1", "NE", "1", "LS1_SOLVE_NOT_CONVERGED", "LS1 CNVG 不等于 1 时立即拒绝。")  # LS1 收敛硬门禁。
    add_apdl(lines, "FINISH", "离开求解处理器，LS1 已通过收敛门禁。")  # 结束 LS1。
    add_apdl(lines, "/SOLU", "重新进入求解处理器，建立无新增外载的 LS2 保持步。")  # 开始 LS2。
    add_apdl(lines, "STABILIZE,OFF", "显式关闭 LS2 稳定化，验证完整重力平衡可以独立保持。")  # 关闭稳定化。
    add_apdl(lines, "TIME,1.001", "把 LS2 终点设为单调递增伪时间 1.001。")  # 设置 LS2 终点。
    add_apdl(lines, f"ACEL,0,0,{GRAVITY_MM_S2:g}", "重发同一重力加速度，明确 LS2 没有新增物理外载。")  # 保持重力不变。
    add_apdl(lines, "KBC,0", "保持斜坡定义；因起终点重力相同，实际外载增量为零。")  # 重发加载方式。
    add_apdl(lines, "AUTOTS,OFF", "关闭 LS2 自动步长，禁止 cutback 掩盖保持步失稳。")  # 按硬更正关闭自动步长。
    add_apdl(lines, "NSUBST,1,1,1", "LS2 固定单一子步，不允许细分、放大或缩减。")  # 固定保持步规模。
    add_apdl(lines, "OUTRES,ALL,LAST", "保存 LS2 末完整场作为唯一扰动基态。")  # 保存保持步结果。
    add_apdl(lines, "OUTRES,VENG,LAST", "保存 LS2 末 SENE/STEN 供关闭稳定化后的残余能量门禁。")  # 保存 LS2 能量。
    add_apdl(lines, "OUTRES,RSOL,LAST", "保存 LS2 末支反力供质量—重力闭合。")  # 保存 LS2 反力。
    add_apdl(lines, "SOLVE", "执行 LS2 单子步、无稳定化、无新增外载保持求解。")  # 未来执行 LS2。
    add_apdl(lines, "*GET,B00_CNVG2,ACTIVE,0,SOLU,CNVG", "读取 LS2 最后一次求解收敛标志；数值 1 才可继续。")  # 获取 LS2 收敛状态。
    add_reject_gate(lines, "B00_CNVG2", "NE", "1", "LS2_HOLD_NOT_CONVERGED", "LS2 CNVG 不等于 1 时立即拒绝，不允许 cutback。")  # LS2 收敛硬门禁。
    add_apdl(lines, "FINISH", "离开求解处理器，开始只读静力结果门禁。")  # 结束 LS2。
    add_apdl(lines, "/POST1", "进入通用后处理器读取 LS1 与 LS2 末结果。")  # 开始静力 QA。
    add_apdl(lines, f"FILE,{jobname},rst", "显式指定本 job 的静力 RST，避免 FILE 状态歧义。")  # 绑定静力结果。
    add_apdl(lines, "ALLSEL,ALL", "恢复全部节点和单元选择以计算全模能量和质量。")  # 恢复全选。
    add_apdl(lines, "SET,1,LAST", "读取 LS1 最后收敛结果集作为稳定化端点。")  # 激活 LS1 结果。
    add_apdl(lines, "ETABLE,ERAS", "清空旧单元表定义，避免标签或结果集残留。")  # 清空 ETABLE。
    add_apdl(lines, "ETABLE,B0SENE,SENE", "建立 LS1 全单元势能列，单位 N·mm。")  # 建立势能列。
    add_apdl(lines, "ETABLE,B0STEN,STEN", "建立 LS1 全单元稳定化耗散能列，单位 N·mm。")  # 建立稳定化能列。
    add_apdl(lines, "SSUM", "对当前全部单元的 B0SENE 和 B0STEN 列求和。")  # 求 LS1 总能量。
    add_apdl(lines, "*GET,B00_SENE1,SSUM,0,ITEM,B0SENE", "读取 LS1 全模型势能总和。")  # 获取 LS1 SENE。
    add_apdl(lines, "*GET,B00_STEN1,SSUM,0,ITEM,B0STEN", "读取 LS1 全模型稳定化能总和。")  # 获取 LS1 STEN。
    add_apdl(lines, "B00_DEN1=ABS(B00_SENE1)", "以 LS1 势能绝对值构造稳定化能量比分母。")  # 计算 LS1 分母。
    add_apdl(lines, "*IF,B00_DEN1,LT,1.0E-30,THEN", "LS1 势能绝对值过小时进入除零保护。")  # 开始 LS1 分母保护。
    add_apdl(lines, "B00_DEN1=1.0E-30", "把 LS1 数值保护分母设为 1E-30 N·mm。")  # 设置极小分母。
    add_apdl(lines, "*ENDIF", "结束 LS1 势能分母保护。")  # 结束 LS1 保护。
    add_apdl(lines, "B00_RATIO1=ABS(B00_STEN1)/B00_DEN1", "计算 LS1 端点绝对 STEN/SENE 比。")  # 计算 LS1 能量比。
    add_apdl(lines, "SET,2,LAST", "读取 LS2 无稳定化保持步的最后收敛结果。")  # 激活 LS2 结果。
    add_apdl(lines, "ETABLE,REFL", "按 LS2 当前结果刷新 B0SENE 与 B0STEN 单元表。")  # 刷新 ETABLE。
    add_apdl(lines, "SSUM", "对 LS2 当前全部单元的能量列重新求和。")  # 求 LS2 总能量。
    add_apdl(lines, "*GET,B00_SENE2,SSUM,0,ITEM,B0SENE", "读取 LS2 全模型势能总和。")  # 获取 LS2 SENE。
    add_apdl(lines, "*GET,B00_STEN2,SSUM,0,ITEM,B0STEN", "读取 LS2 全模型稳定化能总和。")  # 获取 LS2 STEN。
    add_apdl(lines, "B00_DEN2=ABS(B00_SENE2)", "以 LS2 势能绝对值构造残余能量比分母。")  # 计算 LS2 分母。
    add_apdl(lines, "*IF,B00_DEN2,LT,1.0E-30,THEN", "LS2 势能绝对值过小时进入除零保护。")  # 开始 LS2 分母保护。
    add_apdl(lines, "B00_DEN2=1.0E-30", "把 LS2 数值保护分母设为 1E-30 N·mm。")  # 设置 LS2 极小分母。
    add_apdl(lines, "*ENDIF", "结束 LS2 势能分母保护。")  # 结束 LS2 保护。
    add_apdl(lines, "B00_RATIO2=ABS(B00_STEN2)/B00_DEN2", "计算 LS2 当前绝对 STEN/SENE 比。")  # 计算 LS2 能量比。
    add_apdl(lines, "*GET,B00_LS2,ACTIVE,0,SET,LSTP", "读取当前结果集载荷步编号，预期为 2。")  # 获取 LS2 编号。
    add_apdl(lines, "*GET,B00_TIME2,ACTIVE,0,SET,TIME", "读取当前结果集伪时间，预期为 1.001。")  # 获取 LS2 时间。
    add_apdl(lines, "B00_TERR2=ABS(B00_TIME2-1.001)", "计算 LS2 当前时间与 1.001 的绝对误差。")  # 计算时间误差。
    add_apdl(lines, "*GET,B00_MTOT,ELEM,0,MTOT,X", "读取完整模型 X 向平动质量，单位 tonne。")  # 获取总质量。
    add_apdl(lines, f"B00_MEXP={EXPECTED_MASS_TONNE:.11f}", "设置封板全模质量 4108.46690758 tonne。")  # 写入质量基准。
    add_apdl(lines, "B00_MERR=ABS(B00_MTOT-B00_MEXP)", "计算当前质量与封板值的绝对误差，单位 tonne。")  # 计算质量绝对误差。
    add_apdl(lines, "NSEL,S,D,UZ", "只选择施加 UZ 位移约束的支承节点。")  # 建立 UZ 支承选择。
    add_apdl(lines, "*GET,B00_QN,NODE,0,COUNT", "读取 UZ 支承节点数，预期恰为 464。")  # 获取支承数。
    add_reject_gate(lines, "B00_QN", "NE", str(EXPECTED_UZ_SUPPORT_COUNT), "UZ_SUPPORT_COUNT_MISMATCH", "UZ 支承节点数不等于 464 时拒绝，避免空或错支承反力闭合。")  # 支承数先行门禁。
    add_apdl(lines, "*GET,B00_NODE,NODE,0,NUM,MIN", "读取当前 UZ 支承集合的最小节点号作为遍历起点。")  # 初始化支承遍历。
    add_apdl(lines, "B00_RFZ=0", "初始化全部 UZ 支承 Z 向约束反力累计值为 0 N。")  # 初始化反力总和。
    add_apdl(lines, "*DO,B00_I,1,B00_QN", "遍历恰 464 个 UZ 支承节点并逐项累加 RF,FZ。")  # 开始支承循环。
    add_apdl(lines, "*GET,B00_RF,NODE,B00_NODE,RF,FZ", "读取当前支承节点的 Z 向约束反力，单位 N。")  # 获取单节点反力。
    add_apdl(lines, "B00_RFZ=B00_RFZ+B00_RF", "把当前节点反力加入全模型竖向支反力总和。")  # 累加反力。
    add_apdl(lines, "*GET,B00_NODE,NODE,B00_NODE,NXTH", "读取所选支承集合中的下一节点号。")  # 推进节点迭代。
    add_apdl(lines, "*ENDDO", "结束 UZ 支承节点反力累加循环。")  # 闭合支承循环。
    add_apdl(lines, f"B00_RFEXP=B00_MTOT*{GRAVITY_MM_S2:g}", "以当前 tonne 质量乘 9806 mm/s² 得到理论重力反力，单位 N。")  # 计算理论反力。
    add_apdl(lines, "B00_RFDEN=ABS(B00_RFEXP)", "以理论反力绝对值构造相对误差分母。")  # 计算反力分母。
    add_apdl(lines, "*IF,B00_RFDEN,LT,1.0,THEN", "理论反力小于 1 N 时进入除零保护。")  # 开始反力分母保护。
    add_apdl(lines, "B00_RFDEN=1.0", "把反力误差数值保护分母设为 1 N。")  # 设置反力分母。
    add_apdl(lines, "*ENDIF", "结束反力相对误差分母保护。")  # 结束反力保护。
    add_apdl(lines, "B00_RFERR=B00_RFZ-B00_RFEXP", "计算实际支反力与理论重力反力的有符号差，单位 N。")  # 计算反力差。
    add_apdl(lines, "B00_RFREL=ABS(B00_RFERR)/B00_RFDEN", "计算竖向支反力相对闭合误差。")  # 计算反力相对误差。
    add_apdl(lines, "ALLSEL,ALL", "恢复全部节点和单元选择，避免支承选择影响后续保存和模态。")  # 恢复全选。
    add_apdl(lines, "/OUTPUT,b00_static_energy_mass_reaction,txt", "输出 LS1/LS2 收敛、能量、质量、支承和反力完整静力门禁证据。")  # 打开静力证据。
    add_vwrite(lines, "*VWRITE,B00_CNVG1,B00_CNVG2,B00_LS2,B00_TIME2", "('LS1_CNVG=',F4.0,', LS2_CNVG=',F4.0,', LS2=',F8.0,', TIME2=',E24.16)", "写出两步收敛标志、当前载荷步和 LS2 时间。")  # 输出求解身份。
    add_vwrite(lines, "*VWRITE,B00_SENE1,B00_STEN1,B00_RATIO1", "('SENE1=',E24.16,', STEN1=',E24.16,', RATIO1=',E24.16)", "写出 LS1 势能、稳定化能和无量纲比值。")  # 输出 LS1 能量。
    add_vwrite(lines, "*VWRITE,B00_SENE2,B00_STEN2,B00_RATIO2", "('SENE2=',E24.16,', STEN2=',E24.16,', RATIO2=',E24.16)", "写出 LS2 势能、稳定化能和无量纲比值。")  # 输出 LS2 能量。
    add_vwrite(lines, "*VWRITE,B00_MTOT,B00_MEXP,B00_MERR,B00_QN", "('MASS=',E24.16,', EXPECTED=',E24.16,', ABS_ERROR=',E24.16,', UZ=',F12.0)", "写出当前质量、封板质量、绝对误差和 UZ 支承数。")  # 输出质量证据。
    add_vwrite(lines, "*VWRITE,B00_RFEXP,B00_RFZ,B00_RFERR,B00_RFREL", "('RF_EXPECTED=',E24.16,', RF_ACTUAL=',E24.16,', ERROR=',E24.16,', REL=',E24.16)", "写出理论重力反力、实际支反力、绝对差和相对误差。")  # 输出反力证据。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束静力门禁证据文件。")  # 关闭静力输出。
    add_reject_gate(lines, "B00_LS2", "NE", "2", "LS2_RESULT_LOADSTEP_MISMATCH", "最终静力结果不在载荷步 2 时拒绝。")  # LS2 结果集编号门禁。
    add_reject_gate(lines, "B00_TERR2", "GT", "1.0E-10", "LS2_TIME_MISMATCH", "LS2 时间与 1.001 的绝对误差超过 1E-10 时拒绝。")  # LS2 时间门禁。
    add_reject_gate(lines, "B00_RATIO1", "GT", f"{LS1_ENERGY_RATIO_LIMIT:.1E}", "LS1_STABILIZATION_ENERGY_HIGH", "LS1 绝对 STEN/SENE 超过 1E-2 时拒绝。")  # LS1 能量比门禁。
    add_reject_gate(lines, "B00_RATIO2", "GT", f"{LS2_ENERGY_RATIO_LIMIT:.1E}", "LS2_STABILIZATION_ENERGY_NOT_ZERO", "LS2 绝对 STEN/SENE 超过 1E-8 时拒绝。")  # LS2 能量比门禁。
    add_reject_gate(lines, "B00_MERR", "GT", f"{MASS_ABSOLUTE_TOLERANCE_TONNE:.1E}", "TOTAL_MASS_MISMATCH", "总质量绝对误差超过 1E-6 tonne 时拒绝。")  # 质量绝对误差门禁。
    add_reject_gate(lines, "B00_RFREL", "GT", f"{REACTION_RELATIVE_TOLERANCE:.1E}", "GRAVITY_REACTION_MISMATCH", "竖向支反力相对误差超过 1E-4 时拒绝。")  # 反力闭合门禁。
    add_apdl(lines, f"SAVE,{jobname}_eq,db", "唯一一次以本 run jobname 派生名称保存无稳定化平衡数据库。")  # 唯一 equilibrium SAVE。
    add_apdl(lines, "FINISH", "离开后处理器，静力门禁全部通过后才允许进入扰动。")  # 结束静力 QA。
    add_apdl(lines, "/OUTPUT,b00_gate_status,txt", "把静力门禁通过但模态未完成的阶段写入唯一 gate 状态。")  # 打开阶段状态。
    add_apdl(lines, "/COM,STATUS=STATIC_GATES_PASSED PHASE=PERTURB_MODAL", "该阶段不是最终结果通过，仅允许开始线性扰动。")  # 写入阶段状态。
    add_apdl(lines, "/OUTPUT", "恢复主输出，准备扰动求解。")  # 关闭阶段状态。
    add_apdl(lines, "/SOLU", "进入求解处理器并从 LS2 最高收敛帧建立线性扰动。")  # 开始扰动。
    add_apdl(lines, "ANTYPE,,RESTART,2,,PERTURB", "从载荷步 2 的最高可用子步进入线性扰动重启动。")  # 绑定 LS2 扰动点。
    add_apdl(lines, "PERTURB,MODAL,AUTO,CURRENT,PARKEEP", "使用当前接触/材料切线并保留参数、位移与约束定义。")  # 选择 modal perturbation。
    add_apdl(lines, "SOLVE,ELFORM", "重建最终静力状态的切线刚度矩阵。")  # 执行 ELFORM。
    add_apdl(lines, "LUMPM,OFF", "使用一致质量矩阵，避免集中近似改变低阶频率。")  # 关闭 lumped mass。
    add_apdl(lines, f"MODOPT,LANB,{modes},0,{UPPER_FREQUENCY_HZ:.2f}", f"用 Block Lanczos 在 0 至 {UPPER_FREQUENCY_HZ:.2f} Hz 最多提取 {modes} 阶。")  # 配置特征值提取。
    add_apdl(lines, f"MXPAND,{modes},,,YES", f"展开最多 {modes} 阶并计算单元结果及官方模态质量信息。")  # 按要求保留 Elcalc YES。
    add_apdl(lines, "OUTRES,ALL,NONE", "先关闭默认模态结果输出以控制文件体积。")  # 清空默认输出。
    add_apdl(lines, "OUTRES,NSOL,ALL", "为每个实际提取模态保留全部节点解。")  # 保存节点模态解。
    add_apdl(lines, "SOLVE", "执行最终预应力切线模态求解。")  # 未来执行模态。
    add_apdl(lines, "FINISH", "离开求解处理器并触发 DMP 结果合并。")  # 完成求解阶段。
    add_apdl(lines, "/POST1", "进入通用后处理器读取线性扰动 RSTP。")  # 开始模态导出。
    add_apdl(lines, f"FILE,{jobname},rstp", "显式指定本 job 的线性扰动结果文件。")  # 绑定 RSTP。
    add_apdl(lines, "SET,LAST", "激活 RSTP 最后一个真实结果集后读取结果集总数。")  # 激活最后模态。
    add_apdl(lines, "*GET,B00_AVAILABLE,ACTIVE,0,SET,NSET", "读取 RSTP 实际可用模态结果集数。")  # 获取可用阶数。
    add_apdl(lines, f"B00_REQUESTED={modes}", f"记录用户请求的 {modes} 阶。")  # 设置请求阶数。
    add_apdl(lines, "B00_EXPORTED=B00_REQUESTED", "先把计划导出阶数设为请求阶数。")  # 初始化导出阶数。
    add_apdl(lines, "*IF,B00_AVAILABLE,LT,B00_EXPORTED,THEN", "实际可用阶数少于请求数时进入截断分支。")  # 开始导出数截断。
    add_apdl(lines, "B00_EXPORTED=B00_AVAILABLE", "把导出数截断为 RSTP 实际可用结果集数。")  # 应用截断。
    add_apdl(lines, "*ENDIF", "结束实际可用阶数截断分支。")  # 闭合截断条件。
    add_reject_gate(lines, "B00_AVAILABLE", "LT", "1", "NO_AVAILABLE_MODAL_RESULTS", "RSTP 实际可用结果少于 1 阶时拒绝。")  # 空模态门禁。
    add_apdl(lines, "/OUTPUT,b00_modal_export_manifest,txt", "输出 requested、available、exported 三项闭合计数。")  # 打开导出清单。
    add_vwrite(lines, "*VWRITE,B00_REQUESTED,B00_AVAILABLE,B00_EXPORTED", "('REQUESTED=',F12.0,', AVAILABLE=',F12.0,', EXPORTED=',F12.0)", "写出请求、可用和实际导出阶数，三者均为整数计数。")  # 输出导出计数。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束模态导出计数文件。")  # 关闭导出清单。
    add_apdl(lines, "/OUTPUT,b00_modal_set_list,txt", "把 RSTP 原生 SET 列表封存为独立证据。")  # 打开 SET LIST 输出。
    add_apdl(lines, "SET,LIST", "列出全部实际模态结果集、频率和载荷步信息。")  # 输出 SET LIST。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束 SET LIST 文件。")  # 关闭 SET LIST 输出。
    add_apdl(lines, "/OUTPUT,b00_modal_properties,csv", "打开无标题纯数值 CSV；列定义由 qa/field_dictionary.md 固定。")  # 打开 modal properties CSV。
    directions = (("X", "X"), ("Y", "Y"), ("Z", "Z"), ("ROTX", "RX"), ("ROTY", "RY"), ("ROTZ", "RZ"))  # 六个官方 DIREC 标签及短参数后缀映射。
    for mode_index in range(1, modes + 1):  # 静态展开每一请求阶，避免动态 SET 或缺阶访问。
        index_text = f"{mode_index:04d}"  # 参数名使用四位序号，支持超过 99 阶且保持唯一。
        add_apdl(lines, f"*IF,B00_EXPORTED,GE,{mode_index},THEN", f"只有实际导出阶数覆盖第 {mode_index} 阶时才读取频率和模态质量。")  # 缺阶 IF 保护。
        add_apdl(lines, f"*GET,B00_F{index_text},MODE,{mode_index},FREQ", f"读取第 {mode_index} 阶频率，单位 Hz。")  # 获取双精度频率。
        add_apdl(lines, f"*GET,B00_G{index_text},MODE,{mode_index},GENM", f"读取第 {mode_index} 阶官方 generalized mass。")  # 获取广义质量。
        for direction, suffix in directions:  # 对六个全局平动/转动方向提取参与因子和有效质量。
            add_apdl(lines, f"*GET,B00_P{suffix}{index_text},MODE,{mode_index},PFACT,,DIREC,{direction}", f"读取第 {mode_index} 阶 {direction} 方向官方 participation factor。")  # 获取参与因子。
        for direction, suffix in directions:  # 第二遍按固定列顺序提取六方向有效质量。
            add_apdl(lines, f"*GET,B00_E{suffix}{index_text},MODE,{mode_index},EFFM,,DIREC,{direction}", f"读取第 {mode_index} 阶 {direction} 方向官方 effective mass。")  # 获取有效质量。
        vwrite_parameters = [str(mode_index), f"B00_F{index_text}", f"B00_G{index_text}"]  # CSV 前三列依次为阶次、频率和广义质量。
        vwrite_parameters.extend(f"B00_P{suffix}{index_text}" for _, suffix in directions)  # 第四至第九列依次加入六方向 PFACT。
        vwrite_parameters.extend(f"B00_E{suffix}{index_text}" for _, suffix in directions)  # 第十至第十五列依次加入六方向 EFFM。
        add_vwrite(lines, "*VWRITE," + ",".join(vwrite_parameters), "(F8.0,14(',',E24.16))", f"写出第 {mode_index} 阶十五列纯数值 CSV；频率及全部质量量采用 E24.16 双精度文本。")  # 输出当前阶 modal properties。
        add_apdl(lines, "*ENDIF", f"结束第 {mode_index} 阶模态属性缺阶保护。")  # 闭合属性 IF。
    add_apdl(lines, "/OUTPUT", "恢复主输出，结束 b00_modal_properties.csv。")  # 关闭属性 CSV。
    for mode_index in range(1, modes + 1):  # 逐阶静态展开位移和转角全节点文本导出。
        mode_label = f"{mode_index:02d}"  # 文件名至少两位序号，超过 99 时自然扩展。
        add_apdl(lines, f"*IF,B00_EXPORTED,GE,{mode_index},THEN", f"只有第 {mode_index} 阶真实存在时才 SET 并创建两份节点文本。")  # 缺阶向量保护。
        add_apdl(lines, f"SET,1,{mode_index}", f"显式选择线性扰动第 {mode_index} 阶结果集。")  # 激活当前模态。
        add_apdl(lines, "ALLSEL,ALL", "恢复全部节点选择，覆盖索网、门架、通道和 MASS21 节点。")  # 全选节点。
        add_apdl(lines, f"/OUTPUT,mode_{mode_label}_all_nodes,txt", f"打开第 {mode_index} 阶全节点位移文件。")  # 打开位移输出。
        add_apdl(lines, "PRNSOL,U,COMP", "输出当前阶全部节点 UX、UY、UZ 位移分量。")  # 输出位移。
        add_apdl(lines, "/OUTPUT", "恢复主输出，关闭当前阶位移文件。")  # 关闭位移输出。
        add_apdl(lines, f"/OUTPUT,mode_{mode_label}_rotations,txt", f"打开第 {mode_index} 阶全节点转角文件。")  # 打开转角输出。
        add_apdl(lines, "PRNSOL,ROT,COMP", "输出当前阶全部可用节点 ROTX、ROTY、ROTZ 转角分量。")  # 输出转角。
        add_apdl(lines, "/OUTPUT", "恢复主输出，关闭当前阶转角文件。")  # 关闭转角输出。
        add_apdl(lines, "*ENDIF", f"结束第 {mode_index} 阶位移和转角导出缺阶保护。")  # 闭合向量 IF。
    add_apdl(lines, "ALLSEL,ALL", "最终恢复全部节点和单元选择。")  # 恢复全选。
    add_apdl(lines, f"SAVE,{jobname}_modal,db", "唯一一次以本 run jobname 派生名称保存完成导出的模态数据库。")  # 唯一 modal SAVE。
    add_apdl(lines, "FINISH", "离开通用后处理器，全部内置导出已完成。")  # 结束后处理。
    add_apdl(lines, "/OUTPUT,b00_gate_status,txt", "把求解与内置导出完成状态写入唯一 gate 文件；外部 QA 仍必需。")  # 打开最终 solver 状态。
    add_apdl(lines, "/COM,STATUS=SOLVER_EXPORT_COMPLETED PHASE=EXTERNAL_QA_REQUIRED", "该状态不等于最终工程通过，必须核对主 out、文件数和哈希闭环。")  # 写入最终阶段。
    add_apdl(lines, "/OUTPUT", "恢复主输出以记录正常退出摘要。")  # 关闭最终状态。
    add_apdl(lines, "/EXIT,NOSAVE", "正常结束未来批处理；数据库已由两次唯一 SAVE 显式命名保存。")  # 正常退出且不覆盖默认数据库。
    return "\n".join(lines) + "\n"  # 返回 LF 结尾的完整 APDL 文本供新 run 写盘，绝不在此执行。


def powershell_quote(value: str) -> str:  # 定义只用于 launch_command.txt 的 PowerShell 单引号函数。
    """返回安全可读的 PowerShell 单引号字面量；本函数绝不执行返回文本。"""  # 函数说明限定输出用途和无执行副作用。
    return "'" + value.replace("'", "''") + "'"  # 按 PowerShell 规则把内部单引号翻倍后包裹。


def build_launch_command(jobname: str, solver_dir: Path, main_input_path: Path) -> tuple[str, list[str]]:  # 定义未来 DMP4 命令文本和参数清单构造函数。
    """返回明显标记未执行的命令证据；只生成字符串，不调用任何进程 API。"""  # 函数说明强调 prepare-only 边界。
    output_path = solver_dir / f"{jobname}.out"  # 未来主 out 固定在隔离 solver 目录并与唯一 jobname 绑定。
    argv = [  # 构造未来人工批准后可使用的 DMP4 参数数组。
        str(MAPDL_EXE),  # 第一项是 U00 哈希封存的 MAPDL 2026 R1 可执行路径。
        "-b",  # 批处理模式不打开交互 GUI。
        "-dis",  # 启用 Distributed Memory Parallel 模式。
        "-mpi",  # 下一参数指定 MPI 实现。
        MPI_NAME,  # 使用 U01 DMP4 已通过的 intelmpi。
        "-np",  # 下一参数指定进程数。
        str(PROCESS_COUNT),  # 固定使用四个 DMP 进程。
        "-j",  # 下一参数指定 MAPDL 作业名前缀。
        jobname,  # 使用本 run 唯一 ASCII jobname。
        "-dir",  # 下一参数指定隔离工作目录。
        str(solver_dir),  # 所有二进制和文本结果只能写入本 run solver 目录。
        "-i",  # 下一参数指定唯一主输入。
        str(main_input_path),  # 使用准备期生成但尚未执行的 B00 主 INP。
        "-o",  # 下一参数指定主输出证据。
        str(output_path),  # 主 out 文件供未来错误、警告和完成标志 QA。
    ]  # 结束未来 argv 数组；本模块没有执行该数组的任何函数。
    rendered_command = "& " + " ".join(powershell_quote(argument) for argument in argv)  # 仅把参数序列渲染为可人工复制的 PowerShell 文本。
    launch_text = "\n".join(  # 生成带醒目标记和前置门禁说明的 launch_command.txt。
        [
            "STATUS=NOT_EXECUTED_PREPARED_COMMAND_ONLY",  # 首行明确该命令从未由本脚本执行。
            "EXECUTION_ATTEMPTED=false",  # 第二行提供机器可读布尔语义。
            f"REQUIRED_NEXT_ACTION={NEXT_ACTION}",  # 固定要求内存、磁盘和独立审计后再决定是否执行。
            "RESOURCE_POLICY=DO_NOT_RUN_UNLESS_MEMORY_READY_AND_DISK_READY",  # 说明未来执行必须同时满足两类资源门禁。
            "INDEPENDENT_AUDIT_POLICY=REVIEW_MAIN_INP_AND_LINEAGE_BEFORE_LAUNCH",  # 说明未来执行前必须独立审阅。
            "FUTURE_DMP4_COMMAND_BEGIN",  # 标记未来命令文本起点。
            rendered_command,  # 写入仅供未来人工批准后使用的完整 DMP4 命令。
            "FUTURE_DMP4_COMMAND_END",  # 标记未来命令文本终点。
            "THIS_FILE_IS_EVIDENCE_ONLY_AND_WAS_NOT_EXECUTED_BY_ULTRA_B00_PREPARE",  # 末行再次防止把命令存在误判为已启动。
            "",  # 保证文本以 LF 结束，便于哈希和逐行解析。
        ]
    )  # 完成 launch 文本渲染。
    return launch_text, argv  # 返回文本和参数列表供写盘及 manifest 记录。


def build_result_packet(run_name: str, jobname: str, modes: int, memory: dict[str, int | bool], disk: dict[str, int | bool | str]) -> str:  # 定义用户可读准备结果包生成函数。
    """返回只陈述已准备、未启动和下一门禁的 Markdown 摘要。"""  # 函数说明限制不得把准备状态描述为求解成功。
    return f"""# B00 prepare-only Result Packet

- Run：{run_name}
- Jobname：{jobname}
- 状态：{STATUS_VALUE}
- 模型线：{MODEL_LINE}（CERIG 5078 legacy frozen）
- 请求阶数：{modes}
- MAPDL 启动：否
- 任何子进程启动：否
- 准备期 U00/U01/source/artifact/lineage 门禁：通过
- 实时可用物理内存：{memory['available_physical_bytes']} byte
- memory_ready：{str(memory['memory_ready']).lower()}
- D 盘实时可用空间：{disk['free_bytes']} byte
- disk_ready（32 GiB）：{str(disk['disk_ready']).lower()}
- 无论上述资源门禁为真或假，本脚本都不会执行 MAPDL。
- 下一动作：{NEXT_ACTION}
- 未来执行后仍需独立核对主 out、RST/RSTP/MODE、导出文件数、频率/向量哈希和 LINK180 非正轴力；prepare 不宣告工程结果有效。
"""  # 返回带末尾换行的结果摘要。


def make_source_ledger(run_dir: Path, dependencies: list[dict[str, Any]], lineage_sources: list[tuple[Path, Path]], evidence_sources: list[Path]) -> str:  # 定义 B00 来源与复制件账本生成函数。
    """复算源、两套依赖复制件、lineage 复制件和父门禁证据并返回账本文本。"""  # 函数说明给出覆盖范围。
    rows: list[tuple[str, str]] = []  # 保存摘要和标签，后续按逻辑顺序写出。
    seen_labels: set[str] = set()  # 防止同一标签重复造成来源账本歧义。
    def append_row(path: Path, label: str) -> None:  # 定义当前函数内部的唯一行追加器。
        require(label not in seen_labels, f"B00 source 账本标签重复：{label}")  # 重复标签立即拒绝。
        rows.append((sha256_file(path), label))  # 复算当前文件摘要并保存标签。
        seen_labels.add(label)  # 登记标签以约束后续行。
    for item in dependencies:  # 按 U00 order 记录源和两套逐字节复制件。
        source = Path(str(item["source"]))  # 还原当前依赖绝对源路径。
        basename = str(item["basename"])  # 读取 solver 与 input_snapshot 共同 basename。
        append_row(source, f"SOURCE::{source}")  # 记录不可修改的源文件实际摘要。
        append_row(run_dir / "input_snapshot" / basename, f"input_snapshot/{basename}")  # 记录审阅快照摘要。
        append_row(run_dir / "solver" / basename, f"solver/{basename}")  # 记录未来 /INPUT 复制件摘要。
    for source, destination in lineage_sources:  # 记录根审计和编排器源码的源/复制对。
        append_row(source, f"SOURCE::{source}")  # 记录 lineage 原始证据。
        append_row(destination, destination.relative_to(run_dir).as_posix())  # 记录 run 内 lineage 快照。
    for source in evidence_sources:  # 记录固定 U00、显式 U01 和 MAPDL 可执行证据。
        append_row(source, f"EVIDENCE::{source}")  # 使用 EVIDENCE 前缀区分未复制父证据。
    return "".join(f"{digest}  {label}\n" for digest, label in rows)  # 返回规范双空格分隔账本并保证末尾换行。


def write_artifact_ledger(run_dir: Path) -> None:  # 定义 B00 run 最终 artifact 集合封板函数。
    """枚举除账本自身外全部文件并写摘要；调用后不得再修改 run。"""  # 函数说明强调必须最后调用。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 固定根级 artifact 账本目标。
    require(not ledger_path.exists(), f"拒绝覆盖 artifact 账本：{ledger_path}")  # 自身不得预先存在。
    artifacts = sorted(path for path in run_dir.rglob("*") if path.is_file() and path != ledger_path)  # 按绝对路径稳定排序全部已生成文件。
    require(bool(artifacts), "B00 artifact 集合不得为空。")  # 空 run 不能封板。
    text = "".join(f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}\n" for path in artifacts)  # 复算每个产物并生成相对标签。
    write_new_text(ledger_path, text)  # 以不可覆盖模式最后写入 artifact 账本。


def build_field_dictionary() -> str:  # 定义 JSON、TXT 和 CSV 配套字段说明生成函数。
    """返回 qa/field_dictionary.md，说明机器文件字段、单位、门槛和自引用排除。"""  # 函数说明满足不可注释格式的配套文档规则。
    return """# B00 字段字典

本文件解释同一 run 内 JSON、SHA-256、TXT 与 CSV 机器文件。JSON 和 CSV 语法本身不支持注释，因此字段含义、单位和门槛集中记录在这里。

## manifest.json 与 B00_status.json

- schema_version：整数 1 表示首版 B00 prepare-only 契约。
- run_id：固定 B00_LEGACY_COMPLETE，也是不可覆盖目录前缀。
- model_line：固定 LEGACY，表示 CERIG 5078 冻结模型线。
- status：固定 PREPARED_NOT_STARTED；不表示 MAPDL 已启动或结果有效。
- next_action：固定 B00_PREFLIGHT_MEMORY_AND_INDEPENDENT_AUDIT_REQUIRED。
- created_utc：准备动作的 UTC ISO-8601 时间，含微秒。
- run_dir_name：B00_LEGACY_COMPLETE 加 UTC 微秒时间戳的目录名。
- jobname：唯一 ASCII MAPDL 前缀，格式 cw_B00_MMDDtHHMMSS_xx，长度不超过 28。
- parent_u00 / parent_u01：固定 U00 与用户显式指定且通过 8/8 的 U01 lineage。
- modes_requested：Block Lanczos 请求阶数；不小于 80 且为 40 的倍数。
- upper_frequency_hz：频率搜索上限，固定 0.35 Hz。
- prepare_only：固定 true；mapdl_execution_attempted、mapdl_started、process_started、execution_attempted 均固定 false。
- memory_snapshot：准备瞬间 Windows 物理内存；容量字段单位 byte，布尔门禁不触发执行。
- disk_snapshot：项目所在卷实时容量；minimum_free_bytes_for_execution 固定 32 GiB。
- dependencies：U00 图 order 1 至 11 的绝对源、basename、图哈希、input_snapshot 和 solver 复制件。
- topology_expectations：未来装配后的节点、单元及 TYPE 4、6、70、71 硬门禁。
- static_solution_contract：LS1、LS2、能量、质量、支承和反力门槛；两步 stabilization 均为 OFF。
- modal_solution_contract：扰动重启动、Lanczos、MXPAND 与导出协议。
- execution_qa_required：运行后仍需人工或独立程序完成的检查，包括 LINK180 非正轴力审查。
- future_launch.argv：只记录未来 DMP4 参数，不是已执行进程。

## qa/preflight.json

- prepare_gate_passed：U00、U01、源图、哈希、命令计数、审计与复制闭合全部通过后为 true。
- checks：准备期硬门禁列表；每项含 check_id、passed、actual 和 expected。
- u00_source_ledger_entry_count：从磁盘复算通过的 U00 source 账本行数。
- u01_source_ledger_entry_count：复算通过的显式 U01 source 账本行数。
- u01_artifact_ledger_entry_count：U01 artifact 账本覆盖文件数；账本自身因自引用悖论排除。
- resource_gate_is_nonexecuting：固定 true，说明资源真假都不会由本脚本启动 MAPDL。
- memory_ready：可用物理内存是否至少 8 GiB。
- disk_ready：项目所在 D 盘可用空间是否至少 32 GiB。

## b00_modal_properties.csv

该文件没有标题行，避免 APDL 字符串写出差异。每个实际存在的模态一行，共 15 列：

1. mode：一基模态序号，整数。
2. freq_hz：官方 MODE/FREQ 频率，单位 Hz，文本精度 E24.16。
3. genm：官方 MODE/GENM generalized mass。
4 至 9. pfact_x、pfact_y、pfact_z、pfact_rotx、pfact_roty、pfact_rotz：六方向 participation factor。
10 至 15. effm_x、effm_y、effm_z、effm_rotx、effm_roty、effm_rotz：六方向 effective mass。

六方向 PFACT/EFFM 使用 v261 已验证的 MODE、PFACT 或 EFFM、DIREC、方向参数序列。本输入不使用不存在的 PRMASS 命令。

## 其他求解器文本

- b00_topology_counts.txt：NODE、ELEMENT、TYPE4、TYPE6、TYPE70、TYPE71 装配计数。
- b00_constraint_equations.txt：原生 CELIST,ALL 约束方程审计。
- b00_coupled_dof.txt：原生 CPLIST,ALL，执行后与准备期 12 条 CP 闭合。
- b00_displacement_constraints.txt：原生 DLIST,ALL，执行后与准备期 3968 条 D 闭合。
- b00_static_energy_mass_reaction.txt：两步 CNVG、SENE/STEN 比、总质量、UZ 支承和反力闭合。
- b00_modal_export_manifest.txt：requested、available、exported 三项阶数。
- b00_modal_set_list.txt：RSTP 原生 SET,LIST。
- mode_XX_all_nodes.txt：第 XX 阶 PRNSOL,U,COMP 全节点位移。
- mode_XX_rotations.txt：第 XX 阶 PRNSOL,ROT,COMP 全节点转角。
- jobname.out：未来 MAPDL 主输出；prepare 阶段不存在，执行后必须检查 ERROR、WARNING 和完成状态。

## SHA-256 账本

- source_hashes.sha256：源路径和关键复制件摘要；格式为 64 位摘要、两个空格、标签。
- artifact_hashes.sha256：run 内除该账本自身外的全部文件；排除自身是避免自引用哈希悖论。
"""  # 返回完整 Markdown，末尾保留换行供稳定哈希。


def prepare_run(u01_run_name: str, modes: int) -> Path:  # 定义 B00 prepare-only 主流程，输入显式 U01 名和合法阶数，返回新 run 路径。
    """完成全部只读门禁、新目录复制和证据封板；任何路径都不会启动 MAPDL。"""  # 函数说明给出唯一允许的写入和严格非执行边界。
    require(ULTRA_RUNS_ROOT.is_dir(), f"缺少 ultra_runs 根目录：{ULTRA_RUNS_ROOT}")  # 创建 B00 前必须已有权威 run 根。
    u00 = validate_u00()  # 在任何 B00 目录写入前完成固定 U00、源图和 legacy 审计硬门禁。
    u01 = validate_u01(u01_run_name)  # 在任何 B00 目录写入前完成显式 U01 8/8 和两账本闭合。
    memory = memory_snapshot()  # 记录准备瞬间实时内存；真假均不改变 prepare-only 行为。
    disk = disk_snapshot()  # 记录项目所在 D 盘实时空间及 32 GiB 执行门禁。
    created = utc_now()  # 取得唯一 UTC 时间源供 run 名、jobname 和清单共享。
    run_stamp = created.strftime("%Y%m%dT%H%M%S%fZ")  # 生成包含六位微秒的 UTC 目录时间戳。
    run_name = f"{RUN_ID}_{run_stamp}"  # 按固定 B00_LEGACY_COMPLETE 前缀构造不可覆盖 run 名。
    run_dir = ULTRA_RUNS_ROOT / run_name  # 新 run 只能是 ultra_runs 的直接子目录。
    require(run_dir.resolve().parent == ULTRA_RUNS_ROOT.resolve(), f"B00 run 目录越界：{run_dir}")  # 防止路径构造逃逸。
    require(not run_dir.exists(), f"拒绝覆盖既有 B00 run：{run_dir}")  # 微秒目录若碰撞也不重用或清理。
    suffix = secrets.token_hex(1)  # 生成两位小写十六进制随机后缀以消除同秒 jobname 冲突。
    jobname = f"cw_B00_{created.strftime('%m%d')}t{created.strftime('%H%M%S')}_{suffix}"  # 生成规定格式的唯一 ASCII 作业名。
    require(jobname.isascii(), f"jobname 必须为 ASCII：{jobname}")  # MAPDL jobname 不得含本地代码页字符。
    require(len(jobname) <= 28, f"jobname 超过 28 字符：{jobname}")  # 遵守任务书长度上限。
    require(re.fullmatch(r"cw_B00_\d{4}t\d{6}_[0-9a-f]{2}", jobname, re.ASCII) is not None, f"jobname 格式错误：{jobname}")  # 强制新前缀和稳定时间结构。
    require(not jobname.casefold().startswith(("attachment23", "a23v2", "cw_u01")), f"jobname 命中旧前缀：{jobname}")  # 明确拒绝历史作业前缀。
    dependencies = [dict(item) for item in u00["dependencies"]]  # 复制已验证依赖对象，避免修改 U00 上下文原值。
    require(MAIN_INPUT_NAME.casefold() not in {str(item["basename"]).casefold() for item in dependencies}, "主输入 basename 与十一项依赖冲突。")  # 主 INP 不得覆盖 solver include。
    main_input_text = build_main_input(jobname, modes, dependencies)  # 在内存中构造完整 APDL，不运行或调用外部程序。
    launch_output_path = run_dir / "solver" / f"{jobname}.out"  # 提前构造未来主 out 路径供 manifest 记录。
    run_dir.mkdir(parents=False, exist_ok=False)  # 以操作系统级不可覆盖语义创建唯一 B00 根目录。
    input_snapshot_dir = run_dir / "input_snapshot"  # 定义十一项人工审阅快照目录。
    solver_dir = run_dir / "solver"  # 定义十一项 solver 复制件、主输入及未来结果目录。
    lineage_dir = run_dir / "lineage"  # 定义根 builder 和质量审计复制目录。
    orchestrator_snapshot_dir = run_dir / "orchestrator_snapshot"  # 定义编排器源码快照目录。
    qa_dir = run_dir / "qa"  # 定义 preflight 和字段字典目录。
    for directory in (input_snapshot_dir, solver_dir, lineage_dir, orchestrator_snapshot_dir, qa_dir):  # 逐个建立固定证据子目录。
        directory.mkdir(parents=False, exist_ok=False)  # 每个子目录必须首次创建且不得覆盖同名路径。
    prepared_dependencies: list[dict[str, Any]] = []  # 保存复制后路径和双哈希闭合结果。
    for item in dependencies:  # 按 order 1..11 复制两套冻结 include。
        source = Path(str(item["source"]))  # 还原依赖源绝对路径。
        basename = str(item["basename"])  # 使用已完成大小写冲突检查的原 basename。
        snapshot_destination = input_snapshot_dir / basename  # input_snapshot 保留同 basename 便于逐项比较。
        solver_destination = solver_dir / basename  # solver 同 basename 供主 INP 直接 /INPUT。
        snapshot_hash = copy_new_verified(source, snapshot_destination)  # 复制第一套并复算源/目标摘要。
        solver_hash = copy_new_verified(source, solver_destination)  # 复制第二套并再次复算摘要。
        require(snapshot_hash == str(item["sha256"]) and solver_hash == str(item["sha256"]), f"B00 order {item['order']} 两套复制件未与图哈希闭合。")  # 三方摘要必须一致。
        prepared = dict(item)  # 建立不修改源对象的 manifest 依赖行。
        prepared["input_snapshot"] = snapshot_destination.relative_to(run_dir).as_posix()  # 记录 run 相对审阅快照路径。
        prepared["solver_copy"] = solver_destination.relative_to(run_dir).as_posix()  # 记录 run 相对求解复制路径。
        prepared["input_snapshot_sha256"] = snapshot_hash  # 记录第一套复制件摘要。
        prepared["solver_copy_sha256"] = solver_hash  # 记录第二套复制件摘要。
        prepared_dependencies.append(prepared)  # 保存完整复制闭合行。
    input_snapshot_files = sorted(path for path in input_snapshot_dir.iterdir() if path.is_file())  # 枚举第一套复制件实际文件。
    solver_dependency_files = sorted(path for path in solver_dir.iterdir() if path.is_file())  # 主 INP 写入前枚举 solver 十一项复制件。
    require(len(input_snapshot_files) == DEPENDENCY_COUNT, "input_snapshot 实际文件数不是 11。")  # 第一套必须恰为十一项。
    require(len(solver_dependency_files) == DEPENDENCY_COUNT, "solver 依赖复制件实际文件数不是 11。")  # 第二套在主输入前必须恰为十一项。
    build_audit_source = Path(str(u00["build_audit_path"]))  # 读取已验证根 builder 审计源。
    mass_audit_source = Path(str(u00["mass_audit_path"]))  # 读取已验证根质量审计源。
    build_audit_destination = lineage_dir / "root_builder_build_audit.json"  # 使用无冲突名称复制根 builder 审计。
    mass_audit_destination = lineage_dir / "root_mass21_spatialization_audit_v2.json"  # 使用无冲突名称复制根质量审计。
    orchestrator_destination = orchestrator_snapshot_dir / SCRIPT_PATH.name  # 按契约保存 ultra_b00_prepare.py 源码快照。
    build_audit_hash = copy_new_verified(build_audit_source, build_audit_destination)  # 复制并闭合 builder 审计。
    mass_audit_hash = copy_new_verified(mass_audit_source, mass_audit_destination)  # 复制并闭合质量审计。
    orchestrator_hash = copy_new_verified(SCRIPT_PATH, orchestrator_destination)  # 复制并闭合当前实际执行源码。
    main_input_path = solver_dir / MAIN_INPUT_NAME  # 固定 solver 主输入目标路径。
    write_new_text(main_input_path, main_input_text)  # 仅写入 APDL 文本，不调用 MAPDL。
    main_input_hash = sha256_file(main_input_path)  # 复算生成主输入摘要供 manifest 和 source 账本绑定。
    solver_inp_files = sorted(path for path in solver_dir.glob("*.inp") if path.is_file())  # 枚举十一 include 加唯一主输入。
    require(len(solver_inp_files) == DEPENDENCY_COUNT + 1, "solver 准备后的 INP 文件数不是 12。")  # solver 应含十一复制件和一个主 INP。
    launch_text, launch_argv = build_launch_command(jobname, solver_dir.resolve(), main_input_path.resolve())  # 只构造未来命令字符串和参数数组。
    write_new_text(run_dir / "launch_command.txt", launch_text)  # 写入明显标记 NOT_EXECUTED 的未来命令证据。
    write_new_text(qa_dir / "field_dictionary.md", build_field_dictionary())  # 写入 JSON/CSV/TXT 字段配套说明。
    lineage_sources = [  # 绑定三组必须复制的 lineage 源和目标。
        (build_audit_source, build_audit_destination),  # 根 builder PASS 审计源与快照。
        (mass_audit_source, mass_audit_destination),  # 根质量 PASS 审计源与快照。
        (SCRIPT_PATH, orchestrator_destination),  # prepare-only 编排器源码与运行快照。
    ]  # 结束 lineage 源/目标列表。
    u01_run_dir = Path(str(u01["run_dir"]))  # 还原显式 U01 已验证绝对目录。
    evidence_sources = [  # 记录无需再复制但必须复算绑定的父证据和可执行文件。
        U00_RUN / "U00_status.json",  # 固定 U00 PASS_A 状态。
        U00_RUN / "manifest.json",  # 固定 U00 manifest。
        U00_RUN / "mapdl_environment.json",  # 固定 MAPDL 环境。
        U00_RUN / "input_dependency_graph.json",  # 十一项 order 来源图。
        U00_RUN / "source_hashes.sha256",  # U00 已复算闭合源账本。
        u01_run_dir / "U01_status.json",  # 显式 U01 PASSED 8/8 状态。
        u01_run_dir / "manifest.json",  # 显式 U01 parent 与可执行身份清单。
        u01_run_dir / "source_hashes.sha256",  # 显式 U01 已复算 source 账本。
        u01_run_dir / "artifact_hashes.sha256",  # 显式 U01 已复算 artifact 账本。
        MAPDL_EXE,  # 当前实际 MAPDL 可执行程序。
    ]  # 结束父证据绝对路径列表。
    source_ledger_text = make_source_ledger(run_dir, prepared_dependencies, lineage_sources, evidence_sources)  # 生成源与复制件闭合账本。
    source_ledger_text += f"{main_input_hash}  GENERATED::solver/{MAIN_INPUT_NAME}\n"  # 把生成主 INP 摘要作为明确 GENERATED 项追加。
    write_new_text(run_dir / "source_hashes.sha256", source_ledger_text)  # 以不可覆盖方式封存 B00 source 账本。
    checks = [  # 构造全部准备期硬门禁的机器可读通过清单。
        {"check_id": "U00_STATUS_PASS_A", "passed": True, "actual": "PASS_A", "expected": "PASS_A"},  # 固定 U00 状态门禁。
        {"check_id": "MAPDL_EXECUTABLE_SHA256", "passed": True, "actual": u00["mapdl_executable_sha256"], "expected": MAPDL_SHA256},  # 可执行字节身份门禁。
        {"check_id": "U01_PASSED_8_OF_8", "passed": True, "actual": "8/8", "expected": "8/8"},  # 显式 U01 全套通过门禁。
        {"check_id": "U01_PARENT_U00", "passed": True, "actual": u01["manifest"]["parent_run"], "expected": U00_RUN_NAME},  # U01 lineage 门禁。
        {"check_id": "U00_SOURCE_HASH_LEDGER", "passed": True, "actual": u00["u00_source_ledger_entry_count"], "expected": "all ledger entries hash-match"},  # U00 source 账本闭合。
        {"check_id": "U01_SOURCE_HASH_LEDGER", "passed": True, "actual": u01["source_ledger_entry_count"], "expected": "all ledger entries hash-match"},  # U01 source 账本闭合。
        {"check_id": "U01_ARTIFACT_HASH_CLOSURE", "passed": True, "actual": u01["artifact_ledger_entry_count"], "expected": u01["artifact_actual_file_count_excluding_ledger"]},  # U01 artifact 集合和摘要闭合。
        {"check_id": "LEGACY_DEPENDENCIES_EXACTLY_11", "passed": True, "actual": len(prepared_dependencies), "expected": DEPENDENCY_COUNT},  # 图边数量门禁。
        {"check_id": "LEGACY_ORDER_1_TO_11", "passed": True, "actual": [item["order"] for item in prepared_dependencies], "expected": list(range(1, 12))},  # 图边顺序门禁。
        {"check_id": "SOURCE_COMMAND_COUNTS", "passed": True, "actual": u00["scan_counts"], "expected": {"order_3_cp": 12, "order_3_d": 12, "order_4_d": 1096, "order_6_cerig": 5078, "order_7_d": 2860, "order_10_en": 33003, "d_total_orders_3_4_7": 3968}},  # 分项和总和源扫描门禁。
        {"check_id": "BUILDER_ANTI_MIX_WORD_COUNTS", "passed": True, "actual": u00["builder_word_counts"], "expected": {"CERIG": 5078, "MPC184": 0, "PNLT": 0}},  # legacy builder 全文反混线门禁。
        {"check_id": "INPUT_SNAPSHOT_COPY_COUNT", "passed": True, "actual": len(input_snapshot_files), "expected": DEPENDENCY_COUNT},  # 第一套复制数量门禁。
        {"check_id": "SOLVER_DEPENDENCY_COPY_COUNT", "passed": True, "actual": len(solver_dependency_files), "expected": DEPENDENCY_COUNT},  # 第二套复制数量门禁。
        {"check_id": "SOLVER_INP_COUNT_WITH_MAIN", "passed": True, "actual": len(solver_inp_files), "expected": DEPENDENCY_COUNT + 1},  # 主输入加入后数量门禁。
        {"check_id": "PREPARE_ONLY_NO_EXECUTION", "passed": True, "actual": False, "expected": False},  # 进程执行标志硬固定为假。
    ]  # 结束准备期 checks 列表。
    manifest = {  # 构造根级 B00 机器清单。
        "schema_version": 1,  # 首版 B00 prepare-only 清单结构。
        "run_id": RUN_ID,  # 固定运行标识 B00_LEGACY_COMPLETE。
        "model_line": MODEL_LINE,  # 固定模型线 LEGACY。
        "status": STATUS_VALUE,  # 固定 PREPARED_NOT_STARTED。
        "next_action": NEXT_ACTION,  # 固定要求资源和独立审计。
        "created_utc": created.isoformat(),  # 记录带时区和微秒的 UTC 时间。
        "run_dir_name": run_name,  # 记录不可覆盖 run 目录名。
        "run_dir": str(run_dir.resolve()),  # 记录本机绝对 run 路径。
        "jobname": jobname,  # 记录唯一 ASCII jobname。
        "jobname_length": len(jobname),  # 记录长度供 <=28 审计。
        "parent_u00": U00_RUN_NAME,  # 固定父 U00。
        "parent_u01": u01_run_name,  # 用户显式父 U01。
        "u01_status": "PASSED",  # 记录 U01 全套状态。
        "u01_passed_count": 8,  # 记录 U01 通过数。
        "u01_required_count": 8,  # 记录 U01 要求数。
        "mapdl_version": u00["environment"].get("ansys_release"),  # 沿用 U00 封板版本字符串。
        "mapdl_executable": str(MAPDL_EXE),  # 记录固定可执行路径。
        "mapdl_executable_sha256": MAPDL_SHA256,  # 记录当前复算通过摘要。
        "parallel_mode": "DMP",  # 未来执行并行模式为 DMP。
        "processes": PROCESS_COUNT,  # 未来执行进程数固定为 4。
        "mpi": MPI_NAME,  # 未来执行 MPI 固定 intelmpi。
        "units": "N-mm-tonne-s",  # 记录一致单位制。
        "coordinate_system": "X longitudinal, Y transverse, Z vertical",  # 记录全局坐标方向。
        "modes_requested": modes,  # 记录合法请求阶数。
        "upper_frequency_hz": UPPER_FREQUENCY_HZ,  # 记录 0.35 Hz 上限。
        "prepare_only": True,  # 明确脚本仅准备。
        "mapdl_execution_attempted": False,  # 明确没有执行 MAPDL。
        "process_started": False,  # 明确没有启动任何求解进程。
        "execution_policy": "NEVER_EXECUTE_MAPDL_REGARDLESS_OF_MEMORY_OR_DISK_BOOLEAN",  # 明确资源真假均不执行。
        "memory_snapshot": memory,  # 写入实时内存证据。
        "disk_snapshot": disk,  # 写入实时磁盘证据。
        "dependencies": prepared_dependencies,  # 写入 order 1..11 双复制闭合清单。
        "input_snapshot_dependency_count": len(input_snapshot_files),  # 记录第一套恰 11 项。
        "solver_dependency_copy_count": len(solver_dependency_files),  # 记录第二套恰 11 项。
        "solver_prepared_inp_count_including_main": len(solver_inp_files),  # 记录 solver 共 12 个 INP。
        "main_input": main_input_path.relative_to(run_dir).as_posix(),  # 记录主 INP 相对路径。
        "main_input_sha256": main_input_hash,  # 记录主 INP 摘要。
        "future_main_output": launch_output_path.relative_to(run_dir).as_posix(),  # 记录未来主 out 相对路径。
        "orchestrator_source": str(SCRIPT_PATH),  # 记录实际编排器源路径。
        "orchestrator_sha256": orchestrator_hash,  # 记录实际编排器摘要。
        "orchestrator_snapshot": orchestrator_destination.relative_to(run_dir).as_posix(),  # 记录源码快照相对路径。
        "lineage_evidence": [  # 记录两份根审计复制身份。
            {"role": "root_builder_build_audit", "source": str(build_audit_source), "copy": build_audit_destination.relative_to(run_dir).as_posix(), "sha256": build_audit_hash},  # builder lineage。
            {"role": "root_mass21_audit", "source": str(mass_audit_source), "copy": mass_audit_destination.relative_to(run_dir).as_posix(), "sha256": mass_audit_hash},  # mass lineage。
        ],  # 结束 lineage 列表。
        "source_scan_counts": u00["scan_counts"],  # 记录 CP/D/CERIG/EN 分项和合计。
        "builder_anti_mix_counts": u00["builder_word_counts"],  # 记录 CERIG/MPC184/PNLT 全文计数。
        "topology_expectations": {"node_count": EXPECTED_NODE_COUNT, "element_count": EXPECTED_ELEMENT_COUNT, "element_type_counts": {str(key): value for key, value in EXPECTED_TYPE_COUNTS.items()}},  # 记录未来组装硬门禁。
        "static_solution_contract": {"ls1": {"time": 1.0, "nsubst": [20, 200, 20], "autots": True, "stabilization": "OFF", "cnvg_required": 1}, "ls2": {"time": 1.001, "nsubst": [1, 1, 1], "autots": False, "cutback_allowed": False, "stabilization": "OFF", "cnvg_required": 1}, "gravity_mm_s2": GRAVITY_MM_S2, "ls1_abs_sten_over_sene_max": LS1_ENERGY_RATIO_LIMIT, "ls2_abs_sten_over_sene_max": LS2_ENERGY_RATIO_LIMIT, "mass_expected_tonne": EXPECTED_MASS_TONNE, "mass_absolute_tolerance_tonne": MASS_ABSOLUTE_TOLERANCE_TONNE, "uz_support_count": EXPECTED_UZ_SUPPORT_COUNT, "reaction_relative_tolerance": REACTION_RELATIVE_TOLERANCE},  # 记录完整静力契约。
        "modal_solution_contract": {"restart": "ANTYPE,,RESTART,2,,PERTURB", "perturb": "PERTURB,MODAL,AUTO,CURRENT,PARKEEP", "eigensolver": "LANB", "lumped_mass": False, "mxpand_element_calculation": True, "node_solution_output": "NSOL,ALL", "frequency_precision": "E24.16", "modal_properties": ["FREQ", "GENM", "PFACT_X_Y_Z_ROTX_ROTY_ROTZ", "EFFM_X_Y_Z_ROTX_ROTY_ROTZ"], "prmass_command_used": False, "displacement_export": "mode_XX_all_nodes.txt PRNSOL,U,COMP", "rotation_export": "mode_XX_rotations.txt PRNSOL,ROT,COMP"},  # 记录模态及导出契约。
        "execution_qa_required": ["independent review of main INP before launch", "memory_ready and disk_ready must both be true at launch time", "main OUT must have zero ERROR and reviewed WARNING", "requested/available/exported and frequency/vector file counts must close", "RST RSTP MODE FULL and main OUT hashes must be sealed after execution", "LINK180 nonpositive axial force review is required after execution and is intentionally not an unverified APDL gate"],  # 记录执行后必审项且不引入未知 LINK 命令。
        "future_launch": {"status": "NOT_EXECUTED_PREPARED_COMMAND_ONLY", "execution_attempted": False, "argv": launch_argv, "launch_command_file": "launch_command.txt"},  # 记录未来 DMP4 命令但明确未执行。
    }  # 结束 manifest 对象。
    preflight = {  # 构造 qa/preflight.json。
        "schema_version": 1,  # 首版 preflight 结构。
        "run_id": RUN_ID,  # 绑定 B00 run_id。
        "model_line": MODEL_LINE,  # 绑定 LEGACY 模型线。
        "generated_utc": created.isoformat(),  # 记录同一准备 UTC 时间。
        "status": STATUS_VALUE,  # 明确尚未开始求解。
        "prepare_gate_passed": True,  # 所有准备期硬门禁已通过。
        "checks": checks,  # 写入逐项硬门禁。
        "u00_source_ledger_entry_count": u00["u00_source_ledger_entry_count"],  # 记录 U00 源账本复算规模。
        "u01_source_ledger_entry_count": u01["source_ledger_entry_count"],  # 记录 U01 源账本复算规模。
        "u01_artifact_ledger_entry_count": u01["artifact_ledger_entry_count"],  # 记录 U01 artifact 账本规模。
        "u01_artifact_actual_file_count_excluding_ledger": u01["artifact_actual_file_count_excluding_ledger"],  # 记录 U01 实际闭合集合规模。
        "memory_snapshot": memory,  # 写入实时物理内存。
        "disk_snapshot": disk,  # 写入实时磁盘空间。
        "execution_resources_ready": bool(memory["memory_ready"]) and bool(disk["disk_ready"]),  # 仅计算未来执行资源联合布尔值。
        "resource_gate_is_nonexecuting": True,  # 明确资源门禁不触发本脚本执行。
        "mapdl_execution_attempted": False,  # 再次明确没有启动求解器。
        "next_action": NEXT_ACTION,  # 固定下一动作。
    }  # 结束 preflight 对象。
    status_payload = {  # 构造根级 B00_status.json。
        "run_id": RUN_ID,  # 固定运行标识。
        "run_dir_name": run_name,  # 绑定唯一 run 目录。
        "jobname": jobname,  # 绑定唯一 MAPDL jobname。
        "model_line": MODEL_LINE,  # 固定 LEGACY。
        "generated_utc": created.isoformat(),  # 记录准备 UTC 时间。
        "status": STATUS_VALUE,  # 固定 PREPARED_NOT_STARTED。
        "prepare_gate_passed": True,  # 表示准备期证据完整。
        "mapdl_started": False,  # 明确 MAPDL 没有启动。
        "process_started": False,  # 明确任何进程都没有启动。
        "execution_attempted": False,  # 明确未来命令未执行。
        "memory_ready": bool(memory["memory_ready"]),  # 记录准备瞬间内存门禁。
        "disk_ready": bool(disk["disk_ready"]),  # 记录准备瞬间磁盘门禁。
        "next_action": NEXT_ACTION,  # 固定下一动作。
    }  # 结束状态对象。
    write_new_json(run_dir / "manifest.json", manifest)  # 写入根 manifest。
    write_new_json(qa_dir / "preflight.json", preflight)  # 写入 qa/preflight。
    write_new_json(run_dir / "B00_status.json", status_payload)  # 写入根状态。
    write_new_text(run_dir / "result_packet.md", build_result_packet(run_name, jobname, modes, memory, disk))  # 写入用户可读结果包。
    write_artifact_ledger(run_dir)  # 最后枚举并哈希全部产物；此调用后严禁再写 run 内文件。
    return run_dir.resolve()  # 返回已完整封板的新 B00 run 绝对路径。


def parse_arguments() -> argparse.Namespace:  # 定义命令行解析函数，无输入，返回受约束参数对象。
    """解析必填 --u01-run 和可选 --modes；帮助页不创建任何 run。"""  # 函数说明强调显式 lineage 和帮助无副作用。
    parser = argparse.ArgumentParser(description="Prepare-only B00_LEGACY_COMPLETE isolated run; never starts MAPDL.")  # 创建只描述准备职责的解析器。
    parser.add_argument("--u01-run", required=True, type=validate_u01_run_name, help="Exact U01_UNIT_TESTS_<UTC-microseconds>Z directory name directly under ultra_runs.")  # 要求用户显式给出 U01 直接子目录名。
    parser.add_argument("--modes", type=validate_modes, default=DEFAULT_MODES, help="Requested mode count; default 80, must be >=80 and divisible by 40.")  # 提供受约束模态阶数参数。
    return parser.parse_args()  # 让 argparse 处理 --help 和参数错误，不触发 prepare_run。


def main() -> int:  # 定义脚本主入口，无输入，返回进程退出码。
    """参数有效时只准备新 run；成功返回 0，门禁失败返回 2。"""  # 函数说明给出返回值语义。
    arguments = parse_arguments()  # 首先解析参数；--help 在此正常退出且不会创建 run。
    try:  # 捕获所有准备期硬门禁和文件系统异常，避免无堆栈的静默失败。
        run_dir = prepare_run(arguments.u01_run, arguments.modes)  # 执行只读验证、复制和证据封板，不启动 MAPDL。
    except Exception as exc:  # 任一门禁、哈希或不可覆盖异常都进入统一失败路径。
        print(f"B00 prepare-only FAILED: {exc}")  # 向标准输出报告具体失败原因，不伪造状态文件。
        return 2  # 返回非零退出码表示没有完成可接受的 B00 封板。
    print(f"B00 prepare-only completed without MAPDL execution: {run_dir}")  # 成功时报告新 run 绝对路径和未执行事实。
    return 0  # 返回零表示准备证据完整，不表示求解或工程结果通过。


if __name__ == "__main__":  # 只有直接调用脚本时才进入命令行主流程。
    raise SystemExit(main())  # 把 main 返回码交给操作系统；导入模块时无任何 run 写入。
