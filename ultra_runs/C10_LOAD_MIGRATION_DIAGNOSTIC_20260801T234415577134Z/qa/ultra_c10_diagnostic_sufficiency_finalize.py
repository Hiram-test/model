"""严格封存 C10 自适应迁移因诊断充分而用有效原生 ABT 停止、但尚未取得 beta=0 的失败运行。"""  # 本模块只读验证既有运行并排他新增封存工件，不启动、停止、恢复或修改 MAPDL。

from __future__ import annotations  # 延迟解析类型标注，保证复杂 JSON 容器在当前 Python 版本中稳定运行。

import argparse  # 解析显式运行目录、只验证模式和完全离线自测模式三个命令行入口。
import ast  # 在离线自测中解析本源码并阻断任何主动进程终止调用或漏注释代码行。
import hashlib  # 复算准备、启动、监控、停机恢复、原生日志和追加账本的 SHA-256 内容身份。
import json  # 严格读取机器证据并渲染最终审计、根状态和标准输出摘要。
import math  # 检查 MNTR 耗时、迁移增量、主元和七天投影均为有限有效数值。
import os  # 对排他暂存文件执行磁盘同步，并用同卷硬链接完成不可覆盖批量发布。
import re  # 从准备账本、MAPDL OUT/ERR 和 MNTR 中提取固定格式的数值与终止签名。
import tempfile  # 仅在 --self-test 下创建操作系统临时目录验证排他发布，不接触任何项目运行。
import time  # 在正式验证时执行短稳定窗口复核，证明退出后的原生日志不再增长。
from datetime import datetime, timezone  # 比较恢复动作与监控事件的 UTC 顺序，区分动作前硬事件和动作后预期中止。
from pathlib import Path  # 规范化含中文的项目、运行、solver、QA 和临时测试路径。
from typing import Any  # 标注异构机器 JSON、MNTR 行、监控事件和验证上下文的数据结构。

import psutil  # 只读复核冻结主进程与携带本 job/solver 身份的全部求解进程已经退出。

SCRIPT_PATH = Path(__file__).resolve()  # 冻结实际执行终结器源码路径，供发布快照和源码摘要使用。
PROJECT_ROOT = SCRIPT_PATH.parents[1]  # 取 ultra_tools 的父目录作为唯一项目分析包根目录。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 限定正式目标必须是统一运行证据根的直接子目录。
EXPECTED_RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_"  # 只允许恒总荷载位置迁移诊断族使用本终结器。
EXPECTED_RUN_NAME = "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T234415577134Z"  # 将事故终结器进一步绑定到当前唯一自适应诊断运行，禁止跨运行套用。
EXPECTED_JOBNAME = "cw_C10madp_0801t234415577134_d1"  # 冻结当前 MAPDL jobname 供全部控制文件和原生日志身份闭合。
EXPECTED_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结唯一批准的自适应诊断子类型。
EXPECTED_SINGLE_CHANGE = "LS2_NSBMX_200_TO_2000_ONLY"  # 冻结相对固定步基准的唯一工程命令差异。
EXPECTED_LOAD_PATH = "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 冻结恒总荷载位置迁移语义。
EXPECTED_INITIAL_PATH = "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_CONTINUOUS_POSITION_MIGRATION"  # 冻结初态与迁移顺序。
EXPECTED_INITIAL_AUDIT = "PENDING_FULL_STATIC_SOLUTION_AND_INDEPENDENT_BALANCE_CHECK"  # 冻结准备态尚未闭合的物理审计边界。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结单层 TYPE72、无辅助节点、无 TYPE73 全桥独立方程总数。
EXPECTED_LS1_PIVOT = 25.3126539  # 冻结健康 LS1 首次稀疏分解的最小正主元基准。
MINIMUM_INCREMENT = 5.0e-7  # NSBMX=2000 对总伪时间 0.001 规定的最小增量，对应 0.05% 迁移。
MIGRATION_DURATION = 1.0e-3  # LS2 从总时间 1.0 到 1.001 的完整无量纲迁移时长。
MINIMUM_ACCEPTED_LS2_STEPS = 2  # 诊断充分性至少要求两个自然接受的连续最小迁移步。
EXPECTED_ACCEPTED_LS2_STEPS = 2  # 当前事故封存只接受恰好两个 LS2 接受步，任何第三步都会改变诊断状态与投影基准。
MINIMUM_LATER_STEP_ITERATIONS = 20  # 最近两步中的后一步至少二十次 Newton 迭代，排除偶发快步。
SUFFICIENCY_HORIZON_SECONDS = 7.0 * 24.0 * 60.0 * 60.0  # 七天停止阈值换算为 604800 秒并要求严格超过。
FLOAT_TOLERANCE = 1.0e-12  # 比较无量纲时间和增量时仅允许科学计数解析尾差。
ABT_PAYLOAD = b"nonlinear\n"  # 冻结 MAPDL 非线性原生停机请求的唯一有效 ASCII 字节序列。
ABT_PAYLOAD_LENGTH = 10  # 冻结上述九字母关键字加单一 LF 的总字节数。
ABT_PAYLOAD_HEX = "6e6f6e6c696e6561720a"  # 冻结有效 ABT 的十六进制表示，避免文本换行归一化歧义。
ABT_PAYLOAD_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结有效 ABT 完整字节摘要。
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()  # 记录旧停机工具空 ABT 的摘要，用于证明恢复动作确有必要。
FINAL_STATUS = "STATIC_DIAGNOSTIC_SUFFICIENCY_CONTROLLED_STOPPED_BEFORE_BETA_ZERO"  # 冻结诊断充分但静力端点未完成的最终状态。
OLD_OPERATOR_FINAL_STATUS = "OPERATOR_SUFFICIENCY_STOP_REQUESTED_EXIT_NOT_CONFIRMED_TIMEOUT_NO_FORCE"  # 冻结旧空 ABT 未获确认的终态。
RECOVERY_CLAIM_STATUS = "OPERATOR_STOP_RECOVERY_CLAIMED_BEFORE_VALID_NATIVE_ABORT"  # 冻结有效 ABT 恢复动作的先行认领状态。
RECOVERY_PLAN_STATUS = "OPERATOR_STOP_RECOVERY_NATIVE_ABORT_PLANNED_NOT_CREATED"  # 冻结任何有效 ABT 字节落盘前的动作计划状态。
RECOVERY_EXECUTED_STATUS = "OPERATOR_STOP_RECOVERY_NATIVE_ABORT_CREATED_AND_SYNCED"  # 冻结排他创建、写入、fsync 和回读完成状态。
RECOVERY_FINAL_STATUS = "OPERATOR_STOP_RECOVERY_VALID_NATIVE_ABORT_REQUESTED_PROCESS_TREE_EXITED_STABLE"  # 冻结有效 ABT 后进程树稳定退出状态。
OLD_STOP_TOOL_PATH = SCRIPT_PATH.parent / "ultra_c10_diagnostic_sufficiency_stop.py"  # 定位产生旧空 ABT 事故链的不可变工具源码。
OLD_STOP_TOOL_SHA256 = "5d8b17fe76a66cebe67ad1a2f3e6f681bb0e0453f830a666528861c624e92828"  # 冻结旧工具已审查字节身份，防止其他空文件事故借用本结论。
RECOVERY_TOOL_PATH = SCRIPT_PATH.parent / "ultra_c10_diagnostic_sufficiency_stop_recovery.py"  # 定位提交有效十字节 ABT 的恢复工具源码。
RECOVERY_TOOL_SHA256 = "6dc4e2aef1e18910b91feaef159fb1ac4d3abedbc827d8d4f5ba14230c0bab7d"  # 冻结双回执、fsync、回读且无进程信号版本的恢复工具摘要。
OLD_OPERATOR_CLAIM_STATUS = "OPERATOR_SUFFICIENCY_STOP_CLAIMED_BEFORE_NATIVE_ABORT"  # 冻结旧空 ABT 动作前认领状态。
OLD_OPERATOR_BLOCK_REASON = "PROCESS_TREE_OR_FILES_NOT_STABLE_WITHIN_1800_SECONDS_NO_FORCE_ACTION_TAKEN"  # 冻结旧控制器等待超时且绝无强制动作的唯一原因。
MONITOR_FINAL_STATUS = "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP"  # 冻结持续监控器在 operator ABT 后观察到的干净退出状态。
RECOVERY_INVALID_ABORT_PREFIX = "C10_ADAPTIVE_MONITOR_HARD_STOP "  # 冻结监控器自身非法 ABT 首行风险，证明恢复工具没有调用该分支。
NUMBER_PATTERN = r"[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?"  # 覆盖 MAPDL 整数、小数和科学计数法的有限数词法。
LEDGER_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})\s{2}(.+)$")  # 只接受小写 SHA-256、双空格和相对路径的标准账本行。
MNTR_ROW_PATTERN = re.compile(rf"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})(?:\s+|$)", re.IGNORECASE)  # 匹配 MNTR 五个整数及增量、总时间、耗时八列。
EQUATION_PATTERN = re.compile(r"NUMBER\s+OF\s+EQUATIONS\s*=\s*(\d+)", re.IGNORECASE)  # 提取每次直接求解器组装报告的方程总数。
PIVOT_PATTERN = re.compile(rf"SPARSE\s+SOLVER\s+MINIMUM\s+PIVOT\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 提取有符号稀疏分解最小主元。
COMPLETED_STEP_PATTERN = re.compile(r"\*\*\*\s+LOAD\s+STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED\.", re.IGNORECASE)  # 提取 MAPDL 已自然接受的载荷步与子步。
ABORT_ACK_PATTERNS = [("TERMINATED_FROM_ABT_FILE", re.compile(r"TERMINAT(?:ED|ING|ION)[\s\S]{0,160}FROM\s+THE\s+ABT\s+FILE", re.IGNORECASE)), ("JOBNAME_ABT_ABORTED", re.compile(r"(?:SOLVER\s+)?WAS\s+ABORTED\s+BY\s+(?:THE\s+)?JOBNAME\.ABT", re.IGNORECASE)), ("FILE_ABT_ABORTED", re.compile(r"(?:SOLVER\s+)?WAS\s+ABORTED\s+BY\s+(?:THE\s+)?FILE\.ABT", re.IGNORECASE)), ("SOLUTION_STOP_BUTTON_PRESSED", re.compile(r"SOLUTION\s+STOP\s+BUTTON\s+PRESSED", re.IGNORECASE)), ("ABT_OR_USER_TERMINATION", re.compile(r"(?:NONLINEAR|USER|OPERATOR|ABORT\s+FILE|\.ABT)[\s\S]{0,240}(?:ABORT(?:ED|ING)?|TERMINAT(?:ED|ING|ION))|(?:ABORT(?:ED|ING)?|TERMINAT(?:ED|ING|ION))[\s\S]{0,240}(?:NONLINEAR|USER|OPERATOR|ABORT\s+FILE|\.ABT)", re.IGNORECASE))]  # 覆盖 2026 R1 实际 terminated-from-ABT、二进制 jobname.abt/STOP 签名及等价用户终止措辞。
FORBIDDEN_NATIVE_PATTERNS = [("MAPDL_FATAL", re.compile(r"^\s*\*\*\*\s+FATAL\s+\*\*\*", re.IGNORECASE | re.MULTILINE)), ("SMALL_PIVOT", re.compile(r"(?:VERY\s+)?SMALL\s+(?:EQUATION\s+SOLVER\s+)?PIVOT", re.IGNORECASE)), ("ZERO_PIVOT", re.compile(r"ZERO\s+PIVOT", re.IGNORECASE)), ("NEGATIVE_PIVOT", re.compile(r"NEGATIVE\s+PIVOT", re.IGNORECASE)), ("CNVTOL_IGNORED", re.compile(r"CNVTOL\s+COMMAND\s+IS\s+IGNORED", re.IGNORECASE)), ("CNVTOL_RESET", re.compile(r"INTERNALLY\s+RESET\s+TO\s+CNVTOL", re.IGNORECASE))]  # 冻结不得被操作员 ABT 掩盖的数值硬事件集合。
SOLVER_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 限定只读进程扫描的求解器映像集合。
FORBIDDEN_PROCESS_CALL_NAMES = {"kill", "terminate", "send_signal", "killpg", "taskkill"}  # 离线 AST 自审计禁止出现的主动进程处置调用名集合。


def require(condition: bool, message: str) -> None:  # 接收必须成立的条件和失败原因；失败时不发布任何最终工件。
    if not condition:  # 仅在谱系、数值、动作、监控或发布门不闭合时进入异常路径。
        raise RuntimeError(message)  # 抛出明确错误并保持运行目录原有字节不变。


def utc_now() -> str:  # 无输入并返回带 UTC 偏移的微秒级 ISO-8601 当前时刻。
    return datetime.now(timezone.utc).isoformat()  # 使用时区感知 UTC 避免本地时区和夏令时歧义。


def parse_utc(value: Any, label: str) -> datetime:  # 接收时间字段和标签并返回规范 UTC 时间对象。
    require(isinstance(value, str) and bool(value.strip()), f"{label} 缺少非空 UTC 时间")  # 拒绝缺失、空串和非字符串时间。
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # 兼容标准 Z 后缀并解析 ISO-8601 文本。
    require(parsed.tzinfo is not None, f"{label} 不含时区")  # 无时区时无法证明跨工具动作先后顺序。
    return parsed.astimezone(timezone.utc)  # 统一转换为 UTC 供严格比较。


def sha256_bytes(payload: bytes) -> str:  # 接收内存字节并返回六十四位小写 SHA-256。
    return hashlib.sha256(payload).hexdigest()  # 对精确字节序列一次性计算稳定摘要。


def sha256_file(path: Path) -> str:  # 接收普通文件并返回完整二进制内容 SHA-256。
    digest = hashlib.sha256()  # 为当前文件建立独立摘要累加器。
    with path.open("rb") as handle:  # 使用二进制只读模式避免编码或换行转换。
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):  # 每次读取八 MiB 兼顾大型 OUT 吞吐和内存峰值。
            digest.update(block)  # 按原始字节顺序累加当前数据块。
    return digest.hexdigest()  # 返回可写入标准账本的固定长度摘要。


def read_json(path: Path) -> dict[str, Any]:  # 接收 JSON 路径并返回经严格 UTF-8 和顶层对象检查的字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 在解析前拒绝缺失、目录或错误路径。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 严格解析完整 UTF-8 文档而不替换坏字节。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充具名机器工件。
    return payload  # 返回通过存在、编码、语法和类型门的对象。


def render_json(payload: dict[str, Any]) -> str:  # 接收机器对象并返回稳定、保留中文且禁止 NaN 的 JSON 文本。
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 固定两空格缩进和末尾单一 LF 供哈希复核。


def parse_hash_ledger(path: Path, root: Path, minimum_entries: int = 29) -> dict[str, str]:  # 接收账本、根目录和最低条目数并返回唯一相对路径摘要映射。
    require(path.is_file(), f"缺少哈希账本：{path}")  # 无字节谱系时禁止形成失败封存结论。
    entries: dict[str, str] = {}  # 初始化保持输入顺序的唯一条目映射。
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()  # 严格读取全部标准账本行。
    require(len(lines) >= minimum_entries, f"账本条目不足：{len(lines)} < {minimum_entries}")  # 冻结 29 为当前准备包最低完整规模。
    for line_number, line in enumerate(lines, start=1):  # 按真实行号逐项核对格式、边界、存在性和摘要。
        match = LEDGER_LINE_PATTERN.fullmatch(line)  # 对完整行应用六十四位摘要与双空格分隔词法。
        require(match is not None, f"账本第 {line_number} 行格式无效")  # 空行、宽松摘要或错误分隔均拒绝。
        relative_text = match.group(2).replace("\\", "/")  # 统一 Windows 与 POSIX 分隔符供唯一比较。
        require(relative_text not in entries, f"账本重复路径：{relative_text}")  # 阻断后行覆盖同一工件先前摘要。
        artifact_path = (root / Path(relative_text)).resolve()  # 将当前相对路径投影到规范根目录。
        require(artifact_path.is_relative_to(root.resolve()), f"账本路径越界：{relative_text}")  # 阻断绝对路径和父目录逃逸。
        require(artifact_path.is_file(), f"账本工件缺失：{relative_text}")  # 每个冻结条目必须仍为普通文件。
        require(sha256_file(artifact_path) == match.group(1), f"账本工件哈希漂移：{relative_text}")  # 当前字节必须与账本逐项一致。
        entries[relative_text] = match.group(1)  # 保存通过全部门禁的唯一条目。
    return entries  # 返回供启动链、监控链和最终追加账本复核的映射。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收完整命令数组和标志并返回其唯一相邻值。
    indexes = [index for index, value in enumerate(arguments) if value.casefold() == flag.casefold()]  # 忽略标志大小写收集全部出现位置。
    require(len(indexes) == 1, f"启动参数 {flag} 出现 {len(indexes)} 次，预期 1")  # 缺失或重复都会造成真实执行身份歧义。
    index = indexes[0]  # 读取已经确认唯一的参数下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止末尾孤立标志造成越界。
    return arguments[index + 1]  # 返回求解器实际采用的字符串值。


def snapshot_file(path: Path) -> dict[str, Any]:  # 接收可能不存在的文件并返回存在、大小和纳秒修改时刻快照。
    if not path.is_file():  # MAPDL 消费 ABT 或移除 lock 后允许目标不存在。
        return {"exists": False, "size_bytes": 0, "mtime_ns": None}  # 用固定字段表达缺失状态。
    stat = path.stat()  # 取得普通文件当前元数据。
    return {"exists": True, "size_bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}  # 返回可与监控/恢复终态逐项比较的快照。


def require_files_stable(paths: list[Path], wait_seconds: float) -> None:  # 接收文件列表和稳定窗口秒数并要求全部状态在窗口内不变。
    require(all(path.is_file() for path in paths), "稳定性检查包含缺失文件")  # 三项原生日志必须全部存在。
    before = {path: snapshot_file(path) for path in paths}  # 一次冻结窗口起点状态。
    if wait_seconds > 0.0:  # 正式运行使用两秒，离线单元测试可传零避免无意义等待。
        time.sleep(wait_seconds)  # 等待退出缓冲和监控终态提交完成。
    after = {path: snapshot_file(path) for path in paths}  # 一次冻结窗口终点状态。
    require(before == after, "OUT、ERR 或 MNTR 在稳定窗口仍发生变化")  # 防止尾部追加后旧哈希被封存。


def resolve_run(run_dir_value: Path, runs_root: Path = RUNS_ROOT) -> Path:  # 接收目标和批准运行根并返回规范直接子目录。
    run_dir = run_dir_value.resolve()  # 消除相对段、符号路径和当前目录歧义。
    require(run_dir.is_dir(), f"运行目录不存在：{run_dir}")  # 拒绝缺失或普通文件路径。
    require(run_dir.parent == runs_root.resolve(), f"运行目录越出批准 ultra_runs 根：{run_dir}")  # 只允许证据根直接子运行。
    require(run_dir.name.startswith(EXPECTED_RUN_PREFIX), f"运行不属于 C10 迁移诊断族：{run_dir.name}")  # 阻断其他模型线。
    return run_dir  # 返回已通过边界和族名检查的唯一目标。


def parse_mntr_bytes(payload: bytes) -> list[dict[str, float | int]]:  # 接收冻结 MNTR 字节并返回全部已接受子步的八项字段。
    rows: list[dict[str, float | int]] = []  # 初始化保持原生文件顺序的接受行列表。
    for line in payload.decode("latin-1", errors="strict").splitlines():  # Latin-1 一一映射字节并逐行扫描。
        match = MNTR_ROW_PATTERN.match(line)  # 尝试识别八列真实数值行而不是页眉。
        if match is not None:  # 只有完整数值前缀才属于已接受子步。
            row = {"load_step": int(match.group(1)), "substep": int(match.group(2)), "attempt": int(match.group(3)), "iterations": int(match.group(4)), "total_iterations": int(match.group(5)), "increment": float(match.group(6)), "total_time_printed": float(match.group(7)), "elapsed_seconds": float(match.group(8))}  # 转换为具名机器字段。
            require(all(math.isfinite(float(value)) for value in row.values()), f"MNTR 行含非有限值：{line}")  # 禁止 NaN 或无穷进入充分性结论。
            rows.append(row)  # 保存当前已接受子步且不混入失败尝试。
    return rows  # 返回可与 OUT 完成事件交叉验证的顺序列表。


def evaluate_sufficiency(rows: list[dict[str, float | int]]) -> dict[str, Any]:  # 接收 MNTR 接受行并返回两个最小步与严格七天投影摘要。
    require(len(rows) >= 3, "MNTR 未包含 LS1 和至少两个 LS2 接受步")  # 最低证据为一个 LS1 加两个 LS2 行。
    ls1 = rows[0]  # 读取第一行作为旧荷位平衡端点。
    require((int(ls1["load_step"]), int(ls1["substep"]), int(ls1["attempt"]), int(ls1["iterations"]), int(ls1["total_iterations"])) == (1, 1, 1, 4, 4), f"MNTR 首行不是健康 LS1 1/1/1/4/4：{ls1}")  # 冻结已复现基准。
    require(math.isclose(float(ls1["increment"]), 1.0, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE), "MNTR LS1 增量不是 1.0")  # 固定 LS1 单子步时长。
    ls2_rows = [row for row in rows if int(row["load_step"]) == 2]  # 提取全部自然接受的迁移子步。
    require(len(ls2_rows) == EXPECTED_ACCEPTED_LS2_STEPS, f"当前事故要求恰好两个 LS2 接受步，实际为：{len(ls2_rows)}")  # 同时关闭样本不足和 ABT 前后又接受第三步的状态漂移。
    require(len(rows) == 1 + len(ls2_rows), "MNTR 含 LS1/LS2 之外的接受阶段或顺序异常")  # 禁止后续模态/其他载荷步混入。
    require([int(row["substep"]) for row in ls2_rows] == list(range(1, len(ls2_rows) + 1)), "LS2 接受子步未从 1 连续递增")  # 防止删行或跨尝试拼接。
    require(all(math.isclose(float(row["increment"]), MINIMUM_INCREMENT, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE) for row in ls2_rows), "LS2 接受步存在非 5E-7 增量")  # 只允许冻结最小步速度外推。
    latest_two = ls2_rows[-2:]  # 使用最近两个连续接受步作为最接近停止时刻的速度窗口。
    require(int(latest_two[1]["iterations"]) >= MINIMUM_LATER_STEP_ITERATIONS, f"后一个接受步迭代数不足 20：{latest_two[1]['iterations']}")  # 排除偶发快速接受步。
    seconds_per_step = float(latest_two[1]["elapsed_seconds"]) - float(latest_two[0]["elapsed_seconds"])  # 由原生 Elap(s) 差计算完整最小步耗时。
    require(math.isfinite(seconds_per_step) and seconds_per_step > 0.0, "最近两个接受步耗时差不是有限正数")  # 阻断时钟回退或错序。
    accepted_migration = sum(float(row["increment"]) for row in ls2_rows)  # 独立累计已经自然接受的迁移伪时间。
    require(0.0 < accepted_migration < MIGRATION_DURATION - FLOAT_TOLERANCE, f"LS2 已接受迁移不再是未完成端点：{accepted_migration}")  # 明确 beta=0 尚未到达。
    remaining_migration = MIGRATION_DURATION - accepted_migration  # 计算到 beta=0 仍需完成的迁移伪时间。
    remaining_steps = int(math.ceil(max(0.0, remaining_migration - FLOAT_TOLERANCE) / MINIMUM_INCREMENT))  # 按最小步向上取整避免低估。
    projected_seconds = seconds_per_step * float(remaining_steps)  # 线性投影所有剩余最小步耗时。
    require(math.isfinite(projected_seconds) and projected_seconds > SUFFICIENCY_HORIZON_SECONDS, f"剩余投影未严格超过七天：{projected_seconds:.3f} 秒")  # 关闭唯一充分性停止门。
    return {"accepted_ls2_substep_count": len(ls2_rows), "accepted_ls2_rows": ls2_rows, "latest_two_ls2_rows": latest_two, "later_step_iterations": int(latest_two[1]["iterations"]), "measured_seconds_per_minimum_step": seconds_per_step, "accepted_migration_time": accepted_migration, "remaining_migration_time": remaining_migration, "remaining_minimum_step_count": remaining_steps, "projected_remaining_seconds": projected_seconds, "projection_threshold_seconds": SUFFICIENCY_HORIZON_SECONDS, "projection_strictly_exceeds_seven_days": True, "beta_zero_reached": False}  # 返回机器审计和中文报告共同使用的统一摘要。


def process_identity_is_alive(identity: dict[str, Any]) -> bool:  # 接收冻结主进程身份并只读判断完全相同的 PID、时刻、映像和命令行是否仍存活。
    pid = int(identity.get("pid", 0))  # 读取启动器记录的主 PID，非正值不可能形成合法活动身份。
    if pid <= 0:  # 缺失或非正 PID 表示身份工件无效而不是活动进程。
        return False  # 返回不存在，后续独立字段门仍会拒绝损坏身份。
    try:  # PID 可能已退出、被系统回收或在读取期间消失。
        process = psutil.Process(pid)  # 取得当前同号进程对象供防 PID 回收四项核对。
        same_time = abs(float(process.create_time()) - float(identity.get("create_time_epoch_seconds", -1.0))) <= 1.0e-3  # 以一毫秒容差比较操作系统创建时刻。
        same_executable = str(Path(process.exe()).resolve()).casefold() == str(Path(str(identity.get("executable", ""))).resolve()).casefold()  # 比较规范映像绝对路径且忽略 Windows 大小写。
        same_command = [str(value) for value in process.cmdline()] == [str(value) for value in identity.get("command_line", [])]  # 比较完整参数数组而不是易碰撞的拼接字符串。
        return process.is_running() and same_time and same_executable and same_command  # 只有四项完全相同才认定原主身份仍活动。
    except (psutil.NoSuchProcess, psutil.ZombieProcess):  # 原身份自然退出或已成为僵尸时视为不再活动。
        return False  # 返回已退出事实供终结门使用。
    except psutil.AccessDenied as error:  # 无权读取时不能把未知状态宽松解释为已退出。
        raise RuntimeError(f"无法只读复核主进程身份：{pid}") from error  # 失败关闭并保留权限原因链。


def active_job_processes(jobname: str, solver_dir: Path) -> list[dict[str, Any]]:  # 接收 job 与 solver 目录并返回仍同时携带两项身份的求解进程摘要。
    records: list[dict[str, Any]] = []  # 初始化活动进程证据列表供退出门和错误消息使用。
    for process in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):  # 枚举本机进程以覆盖包装器退出但 worker 仍存活的情形。
        try:  # 进程可能在枚举期间自然消失或拒绝读取命令行。
            process_name = str(process.info.get("name") or "").casefold()  # 归一化当前映像名供求解器候选筛选。
            command_values = [str(value) for value in process.info.get("cmdline") or []]  # 保留完整参数供 job 与工作目录双条件识别。
            command_text = " ".join(command_values).casefold()  # 构造只用于包含判断的大小写无关命令行视图。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # 瞬态退出或拒绝访问对象不形成可稳定认领记录。
            continue  # 继续扫描其他候选而不对任何进程采取动作。
        solver_candidate = process_name in SOLVER_PROCESS_NAMES or process_name.startswith("ansys") or process_name.startswith("mapdl")  # 只保留 MAPDL、ANSYS 或其批准并行包装映像。
        belongs_to_run = jobname.casefold() in command_text and str(solver_dir).casefold() in command_text  # 同时命中唯一 job 与规范 solver 目录才属于本运行。
        if solver_candidate and belongs_to_run:  # 两层筛选均通过时保存活动身份供严格拒绝。
            records.append({"pid": int(process.info["pid"]), "name": process_name, "create_time_epoch_seconds": float(process.info.get("create_time") or -1.0), "command_line": command_values})  # 保存足以人工辨识且不含可变资源字段的摘要。
    return records  # 返回空列表表示本 job 相关求解进程已经全部退出。


def parse_jsonl_bytes(payload: bytes) -> tuple[list[dict[str, Any]], list[bytes]]:  # 接收完整监控 JSONL 字节并返回严格对象列表与保留换行的原始记录列表。
    raw_lines = [line for line in payload.splitlines(keepends=True) if line.strip()]  # 保留每条记录原始换行，供历史决策前缀摘要精确复算。
    require(bool(raw_lines), "监控样本流水为空")  # 至少一个持续监控样本才能证明运行期间没有硬事件。
    require(all(line.endswith((b"\n", b"\r")) for line in raw_lines), "监控 JSONL 最后一条或中间记录缺少完整换行")  # 阻断半写末行被误当完整样本。
    objects = [json.loads(line.decode("utf-8", errors="strict")) for line in raw_lines]  # 逐行严格解码解析，任一坏字节或语法错误立即失败。
    require(all(isinstance(item, dict) for item in objects), "监控 JSONL 含非对象记录")  # 冻结每行必须是具名机器对象的合同。
    return objects, raw_lines  # 返回结构化对象和精确原始行供语义与哈希两类复核。


def jsonl_prefix_sha256(raw_lines: list[bytes], count: int) -> str:  # 接收完整原始记录与历史样本数并返回当时完整前缀字节摘要。
    require(1 <= count <= len(raw_lines), f"历史监控样本数越界：{count}/{len(raw_lines)}")  # 阻断空前缀或引用未来不存在样本。
    return sha256_bytes(b"".join(raw_lines[:count]))  # 按原始换行拼接前 count 条并复算历史工具记录的摘要。


def classify_monitor_events(events: list[Any], action_time: datetime, allowed_kinds: frozenset[str]) -> dict[str, Any]:  # 接收硬事件、有效 ABT 时刻和批准类别并严格区分动作前后与预期性。
    expected: list[dict[str, Any]] = []  # 初始化仅允许动作后且类别明确批准的事件集合。
    unexpected: list[Any] = []  # 初始化错型、错时、未批准和不可解析事件集合。
    for event in events:  # 不丢弃地审查每个监控硬事件。
        if not isinstance(event, dict):  # 非对象记录无法提供类别和带时区检测时刻。
            unexpected.append(event)  # 原样保留错型值供机器审计。
            continue  # 结束当前事件分类并处理下一项。
        try:  # 检测时刻必须可解析且含时区才能与动作建立因果顺序。
            detected_time = parse_utc(event.get("detected_at_utc"), "监控硬事件 detected_at_utc")  # 解析并规范为 UTC。
        except (RuntimeError, TypeError, ValueError):  # 错时刻不得降级为预期 operator abort 签名。
            unexpected.append(event)  # 保留完整原对象供失败原因审查。
            continue  # 处理下一项而不隐藏其他事件。
        if str(event.get("kind", "")) in allowed_kinds and detected_time >= action_time:  # 类别获批且发生在有效 ABT 后才可列为预期。
            expected.append(event)  # 保留通过时序和类别双门的完整事件。
        else:  # 动作前事件或未批准类别均属于独立硬错误。
            unexpected.append(event)  # 保留为失败关闭原因，禁止用 operator ABT 掩盖。
    return {"expected_operator_abort_events": expected, "unexpected_hard_events": unexpected}  # 返回两类完整集合供恢复链和自测使用。


def match_abort_acknowledgements(text_value: str) -> list[dict[str, Any]]:  # 接收动作后原生日志文本并返回所有命中的 ABT/STOP 原生确认签名。
    matches: list[dict[str, Any]] = []  # 初始化可审计签名、偏移和短上下文列表。
    for name, pattern in ABORT_ACK_PATTERNS:  # 逐项应用固定 2026 R1 与等价确认模式。
        match = pattern.search(text_value)  # 只需当前签名首次命中即可证明存在，不把多次重复当成额外动作。
        if match is not None:  # 当前原生签名在动作后文本中真实出现。
            start = max(0, match.start() - 80)  # 向前保留八十字符供人工识别上下文且限制报告体积。
            end = min(len(text_value), match.end() + 120)  # 向后保留一百二十字符供辨识终止原因。
            context_text = re.sub(r"\s+", " ", text_value[start:end]).strip()  # 压缩原生分页和换行形成单行审计片段。
            matches.append({"signature": name, "text_offset_in_post_action_tail": int(match.start()), "context": context_text})  # 保存模式名、相对偏移和受限上下文。
    return matches  # 返回空列表时上层必须拒绝把进程退出单独当作 ABT 因果证明。


def write_new_batch(payloads: dict[Path, str]) -> None:  # 接收全部待发布文本并执行统一预检、fsync 暂存、不可覆盖硬链接和身份安全回滚。
    require(bool(payloads), "批量发布列表为空")  # 禁止无工件调用被误认为封存成功。
    staging_paths = {path: path.with_name(f"{path.name}.codex_staging") for path in payloads}  # 为每个目标构造同目录唯一暂存路径以保证同卷发布。
    published_identities: dict[Path, tuple[int, int, int]] = {}  # 保存本调用创建目标的卷号、文件 ID 和大小供异常回滚。
    for target_path, staging_path in staging_paths.items():  # 在写出任何字节前统一关闭全部目标和暂存路径门。
        require(target_path.parent.is_dir(), f"最终工件父目录不存在：{target_path.parent}")  # 禁止隐式创建错误目录层级。
        require(not target_path.exists(), f"拒绝覆盖既有最终工件：{target_path}")  # 同一运行只允许一次不可覆盖封存。
        require(not staging_path.exists(), f"发现遗留暂存工件：{staging_path}")  # 防止上次异常内容混入本批次。
    try:  # 任一暂存、同步或链接异常都进入只清理本调用对象的回滚分支。
        for target_path, rendered_text in payloads.items():  # 先把全部已验证文本写入对应同目录暂存文件。
            staging_path = staging_paths[target_path]  # 取得当前目标唯一暂存路径。
            with staging_path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用排他创建、UTF-8 和 LF 写入完整暂存内容。
                handle.write(rendered_text)  # 一次写出内存中已经完成渲染且无 NaN 的文本。
                handle.flush()  # 把 Python 文本缓冲全部交给操作系统。
                os.fsync(handle.fileno())  # 请求操作系统把暂存字节同步到磁盘后再发布名称。
        for target_path, staging_path in staging_paths.items():  # 全部暂存成功后按字典顺序逐一发布最终名称。
            os.link(staging_path, target_path)  # 目标若迟到存在则由操作系统拒绝，避免检查与创建竞态覆盖。
            published_stat = target_path.stat()  # 取得本调用新建目标的数据对象身份。
            published_identities[target_path] = (int(published_stat.st_dev), int(published_stat.st_ino), int(published_stat.st_size))  # 冻结卷、文件 ID 和大小三元组。
            staging_path.unlink()  # 删除暂存名称并保留指向同一已同步字节对象的最终名称。
    except Exception:  # 捕获任何 I/O、同步或竞态异常并恢复调用前无本批次最终工件状态。
        for staging_path in staging_paths.values():  # 遍历只属于本次命名规则的尚未发布暂存路径。
            if staging_path.exists():  # 已成功发布的暂存名称已删除，只有残余才进入。
                staging_path.unlink()  # 删除本次未发布碎片而不触碰任何既有结果。
        for target_path, expected_identity in reversed(list(published_identities.items())):  # 逆序处理本调用已创建的部分目标。
            if target_path.is_file():  # 只有目标仍为普通文件时才允许读取身份。
                current_stat = target_path.stat()  # 取得当前路径的数据对象身份以防外部替换。
                current_identity = (int(current_stat.st_dev), int(current_stat.st_ino), int(current_stat.st_size))  # 构造与发布时相同格式的三元组。
                if current_identity == expected_identity:  # 仅当仍指向本调用创建的同一对象时允许删除。
                    target_path.unlink()  # 回滚本次部分发布，避免半套封存被下游误读。
        raise  # 原样重新抛出异常，禁止把回滚后的失败冒充成功。


def build_appended_ledger(run_dir: Path, prepared_entries: dict[str, str], virtual_texts: dict[Path, str], ledger_path: Path) -> tuple[str, int]:  # 接收运行、准备谱系、待发布文本和非自引用账本路径并返回完整追加账本。
    target_paths = {path.resolve() for path in virtual_texts} | {ledger_path.resolve()}  # 构造尚未存在或将在本批次发布的全部目标集合。
    existing_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.resolve() not in target_paths and not path.name.endswith(".codex_staging")]  # 收集运行内全部既有普通文件并排除本批次目标、账本自身和暂存名。
    ledger_entries: dict[str, str] = {}  # 初始化相对路径到内容摘要的完整最终映射。
    for path in existing_paths:  # 对准备、启动、监控、操作员链、恢复链和求解原件逐项计算当前摘要。
        relative_text = path.relative_to(run_dir).as_posix()  # 转换为稳定 POSIX 运行内相对路径。
        require(relative_text not in ledger_entries, f"最终账本既有路径重复：{relative_text}")  # 防止枚举或大小写异常造成歧义覆盖。
        ledger_entries[relative_text] = sha256_file(path)  # 把当前普通文件完整二进制摘要写入映射。
    for relative_text, prepared_sha256 in prepared_entries.items():  # 逐项证明启动前账本的路径和字节在最终账本中原样保留。
        require(ledger_entries.get(relative_text) == prepared_sha256, f"最终追加账本未保持准备条目：{relative_text}")  # 阻断准备工件漂移、缺失或被虚拟目标遮蔽。
    for path, rendered_text in virtual_texts.items():  # 对尚未发布的源码快照、审计、报告和根状态预先计算摘要。
        relative_text = path.resolve().relative_to(run_dir).as_posix()  # 将目标限制并转换为运行内 POSIX 路径。
        require(relative_text not in ledger_entries, f"最终账本虚拟路径与既有工件冲突：{relative_text}")  # 发布前关闭重名和覆盖风险。
        ledger_entries[relative_text] = sha256_bytes(rendered_text.encode("utf-8"))  # 按实际 UTF-8 写出字节预先计算摘要。
    ordered_lines = [f"{ledger_entries[relative_text]}  {relative_text}" for relative_text in sorted(ledger_entries)]  # 按相对路径稳定排序生成标准双空格账本行。
    require(len(ordered_lines) > len(prepared_entries), "诊断充分性追加账本未覆盖准备账本之外的运行与终态工件")  # 必须新增启动、运行、恢复和封存证据。
    return "\n".join(ordered_lines) + "\n", len(ordered_lines)  # 返回末尾单一 LF 的非自引用账本文本和条目数。


def validate_preparation_and_launch(run_dir_value: Path, runs_root: Path = RUNS_ROOT) -> dict[str, Any]:  # 接收事故运行与可测试根目录并返回准备、启动和退出身份全部闭合的上下文。
    run_dir = resolve_run(run_dir_value, runs_root)  # 规范化并关闭直接子目录与运行族边界门。
    require(run_dir.name == EXPECTED_RUN_NAME, f"终结器仅批准当前事故运行 {EXPECTED_RUN_NAME}，实际为 {run_dir.name}")  # 阻断其他同族诊断借用固定恢复合同。
    manifest_path = run_dir / "manifest.json"  # 定位启动前冻结的求解身份、输入和许可清单。
    root_status_path = run_dir / "C10_static_status.json"  # 定位必须保持准备态且不可生产的原根状态。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位启动前完整准备字节谱系。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他创建的启动认领。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后立即提交的最小 PID 记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位 PID、创建时刻、映像和真实命令行增强身份。
    manifest = read_json(manifest_path)  # 读取准备态 manifest 原件且绝不覆盖它。
    root_status = read_json(root_status_path)  # 读取准备态根状态原件且绝不伪造成功字段。
    launch_claim = read_json(launch_claim_path)  # 读取进程创建前冻结的唯一执行权和资源快照。
    launch = read_json(launch_path)  # 读取真实 Popen PID、完整参数和摘要链。
    identity = read_json(identity_path)  # 读取防 PID 回收的操作系统进程身份。
    require(manifest.get("schema_version") == 8 and root_status.get("schema_version") == 3, "manifest 或准备根状态 schema 不是当前冻结版本")  # 拒绝历史固定步包或未知版本。
    require(manifest.get("run_name") == run_dir.name and root_status.get("run_name") == run_dir.name, "manifest 或准备根状态运行名不一致")  # 关闭目录复制和改名错配。
    require(manifest.get("jobname") == root_status.get("jobname") == launch_claim.get("jobname") == launch.get("jobname") == identity.get("jobname") == EXPECTED_JOBNAME, "准备与启动五段 jobname 不一致")  # 固定唯一 MAPDL 文件族身份。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "准备 manifest 或根状态已经被覆盖/终结")  # 本工具采用追加式新根状态而不修改旧工件。
    require(manifest.get("diagnostic_subtype") == root_status.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "运行不是批准的 0.05% 自适应迁移子类型")  # 阻断固定步或其他诊断。
    require(manifest.get("single_variable_change") == root_status.get("single_variable_change") == EXPECTED_SINGLE_CHANGE, "唯一工程变量不是 LS2 NSBMX 200→2000")  # 保持诊断因果路径不变。
    require(manifest.get("load_path_mode") == EXPECTED_LOAD_PATH and manifest.get("initial_state_load_path") == EXPECTED_INITIAL_PATH and manifest.get("initial_state_equilibrium_audit") == EXPECTED_INITIAL_AUDIT, "迁移载荷路径或准备态物理审计身份漂移")  # 固定恒总荷载位置迁移且初态仍待完整静力复核。
    require(manifest.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73" and manifest.get("mpc184_keyopt5_static") == 0, "拓扑或 TYPE72 KEYOPT(5) 不是批准值")  # 阻断旧串联约束和已证伪 K5 分支。
    require(manifest.get("prestressed_modal_requires_keyopt5_restore_to_zero") is False, "manifest 意外要求恢复 KEYOPT(5)，表明输入谱系不属于当前诊断")  # 维持 K5=0 单一差异语义。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and root_status.get("valid_for_production") is False, "准备工件意外允许模态或生产声明")  # 失败封存不得放宽任何用途门。
    increment_change = manifest.get("migration_increment_change")  # 读取准备态冻结的 NSUBST 三参数与比例说明对象。
    require(isinstance(increment_change, dict), "manifest 缺少 migration_increment_change 对象")  # 后续字段只接受具名对象。
    require(increment_change.get("nsbstp") == 200 and increment_change.get("nsbmx") == 2000 and increment_change.get("nsbmn") == 200, "manifest NSUBST 三参数不是 200/2000/200")  # 固定初始、最大和最小子步数合同。
    require(float(increment_change.get("new_initial_fraction", -1.0)) == 0.005 and float(increment_change.get("new_minimum_fraction", -1.0)) == 0.0005, "manifest 初始或最小迁移比例不是 0.5%/0.05%")  # 防止说明与真实命令分叉。
    prepared_entries = parse_hash_ledger(prepared_ledger_path, run_dir)  # 逐项复算全部启动前工件的当前字节。
    require(len(prepared_entries) == 29, f"当前事故准备账本不是固定二十九项：{len(prepared_entries)}")  # 冻结已复审准备包规模并阻断增删行。
    prepared_ledger_sha256 = sha256_file(prepared_ledger_path)  # 计算准备账本自身摘要供三段启动与恢复链交叉核对。
    manifest_sha256 = sha256_file(manifest_path)  # 计算受准备账本保护的 manifest 摘要。
    require(launch_claim.get("schema_version") == 1 and launch_claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED", "启动认领 schema 或状态不符合 Popen 前合同")  # 只接受当前不可覆盖启动器。
    require(launch.get("schema_version") == 1 and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "最小启动记录 schema 或状态不符合 Popen 后合同")  # PID 后增强身份必须位于独立工件。
    require(identity.get("schema_version") == 1 and identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED", "增强进程身份 schema 或状态错误")  # 身份捕获失败运行不能封存为受控退出。
    require(launch_claim.get("run_name") == launch.get("run_name") == identity.get("run_name") == run_dir.name, "启动三段链运行名不一致")  # 关闭跨运行启动工件复制。
    require(launch_claim.get("diagnostic_subtype") == launch.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "启动链诊断子类型漂移")  # 认领和真实执行必须保持同一诊断身份。
    require(launch_claim.get("single_variable_change") == launch.get("single_variable_change") == EXPECTED_SINGLE_CHANGE, "启动链唯一变量漂移")  # 证明启动时仍只有 NSBMX 差异。
    require(launch_claim.get("manifest_sha256") == launch.get("manifest_sha256") == manifest_sha256, "启动链 manifest 摘要不一致")  # 关闭认领前后清单变化。
    require(launch_claim.get("prepared_ledger_sha256") == launch.get("prepared_ledger_sha256") == prepared_ledger_sha256, "启动链准备账本摘要不一致")  # 关闭认领前后输入谱系变化。
    require(int(launch_claim.get("prepared_ledger_entry_count", -1)) == int(launch.get("prepared_ledger_entry_count", -1)) == len(prepared_entries), "启动链准备条目数不一致")  # 防止只核对账本文件而遗漏截断条目。
    require(launch.get("launch_claim_sha256") == sha256_file(launch_claim_path) and identity.get("runtime_launch_sha256") == sha256_file(launch_path), "Popen 前认领、最小记录和增强身份摘要链断裂")  # 三段不可覆盖启动链必须连续。
    require(launch_claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "认领与启动记录的资源快照不一致")  # 防止启动门在 Popen 两侧改写。
    require(launch_claim.get("production_claim_allowed") is False and launch.get("production_claim_allowed") is False, "启动链意外允许生产声明")  # 诊断资源例外不得升级用途。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 从已核对 manifest 恢复完整批准命令数组。
    require(launch_argv == [str(value) for value in launch_claim.get("launch_argv", [])] == [str(value) for value in launch.get("launch_argv", [])] == [str(value) for value in identity.get("command_line", [])], "清单、认领、启动和操作系统命令行数组不一致")  # 固定真实执行入口。
    solver_dir = (run_dir / "solver").resolve()  # 定位本运行唯一 MAPDL 工作目录。
    require(solver_dir.is_dir(), f"缺少 solver 目录：{solver_dir}")  # 在解析参数路径前关闭目录存在门。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and argument_value(launch_argv, "-np") == "1", "启动参数不是唯一批处理 SMP1")  # 固定批准单进程诊断模式。
    require(argument_value(launch_argv, "-j") == EXPECTED_JOBNAME, "启动 -j 与固定 jobname 不一致")  # 固定结果文件族名称。
    require(Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir, "启动 -dir 未指向本运行 solver 目录")  # 阻断跨运行输出污染。
    input_path = Path(argument_value(launch_argv, "-i")).resolve()  # 定位实际传入 MAPDL 的主控输入。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 定位命令行指定的权威 OUT 原件。
    require(input_path == (run_dir / str(manifest.get("main_input"))).resolve() and input_path.parent == solver_dir, "启动主输入与 manifest 或 solver 目录不一致")  # 证明求解确实使用冻结主控。
    require(output_path.parent == solver_dir and output_path.name.casefold() == f"{EXPECTED_JOBNAME}.out".casefold(), "启动 OUT 不属于固定 job")  # 固定权威输出文件。
    mapdl_path = Path(launch_argv[0]).resolve()  # 以 argv 首项定位实际 MAPDL 二进制。
    require(mapdl_path == Path(str(manifest.get("mapdl_executable"))).resolve() and mapdl_path.is_file(), "MAPDL 可执行文件路径漂移或缺失")  # 固定批准 2026 R1 版本位置。
    require(sha256_file(mapdl_path) == str(manifest.get("mapdl_executable_sha256")), "MAPDL 可执行文件 SHA-256 漂移")  # 固定实际二进制字节身份。
    input_relative = input_path.relative_to(run_dir).as_posix()  # 形成准备账本内主控相对路径。
    require(input_relative in prepared_entries and prepared_entries[input_relative] == manifest.get("main_input_sha256") == sha256_file(input_path), "主控输入在准备账本、manifest 和当前字节间不一致")  # 三方关闭输入漂移。
    commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 去除中文注释并规范化实际 APDL 命令。
    require(commands.count("NSUBST,200,2000,200") == 1 and commands.count("NSUBST,200,200,200") == 0, "实际主控未唯一采用 NSUBST,200,2000,200")  # 固定自适应最小步合同。
    require(commands.count("KEYOPT,72,5,1") == 0 and commands.count("KBC,1") == 1 and commands.count("KBC,0") == 1, "实际主控 K5 或两步 KBC 合同漂移")  # 保持默认 K5 和阶跃/斜坡顺序。
    require(commands.count("/INPUT,APPLY_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_V1,INP") == 2 and sum(1 for command in commands if command.startswith("CNVTOL,")) == 4, "实际主控迁移 include 或四项 CNVTOL 数量漂移")  # 防止载荷或收敛门被修改。
    require("PERTURB,MODAL" not in commands and not any(command.startswith("MODOPT,") for command in commands), "实际主控包含模态命令")  # 诊断静力运行绝不能尝试模态。
    require(identity.get("pid") == launch.get("main_pid") and str(Path(str(identity.get("executable", ""))).resolve()).casefold() == str(mapdl_path).casefold(), "增强进程 PID 或二进制身份与启动记录不一致")  # 关闭 PID 和映像身份门。
    require(not process_identity_is_alive(identity), f"原 MAPDL 主进程身份仍存活：{identity.get('pid')}")  # 求解运行中禁止执行终结器。
    remaining_processes = active_job_processes(EXPECTED_JOBNAME, solver_dir)  # 独立枚举本 job 全部包装器和 worker。
    require(not remaining_processes, f"仍有本 job 求解器进程活动：{remaining_processes}")  # 只有完整进程树退出后才能封存。
    error_path = solver_dir / f"{EXPECTED_JOBNAME}.err"  # 定位本 job 独立 ERR 原件。
    mntr_path = solver_dir / f"{EXPECTED_JOBNAME}.mntr"  # 定位本 job 原生已接受子步 MNTR。
    require(output_path.is_file() and output_path.stat().st_size > 1_000_000, "主 OUT 缺失或异常过小")  # 全桥装配与两个最小步必须产生充分原始输出。
    require(error_path.is_file(), "独立 ERR 原件缺失")  # 受控 ABT 可留下空 ERR，但文件本身必须属于当前 job。
    require(mntr_path.is_file() and mntr_path.stat().st_size > 0, "原生 MNTR 缺失或为空")  # 至少 LS1 和两个 LS2 接受行必须存在。
    return {"run_dir": run_dir, "manifest": manifest, "root_status": root_status, "manifest_path": manifest_path, "root_status_path": root_status_path, "prepared_ledger_path": prepared_ledger_path, "prepared_entries": prepared_entries, "prepared_ledger_sha256": prepared_ledger_sha256, "manifest_sha256": manifest_sha256, "launch_claim_path": launch_claim_path, "launch_path": launch_path, "identity_path": identity_path, "launch_claim": launch_claim, "launch": launch, "identity": identity, "launch_argv": launch_argv, "mapdl_path": mapdl_path, "input_path": input_path, "solver_dir": solver_dir, "output_path": output_path, "error_path": error_path, "mntr_path": mntr_path, "jobname": EXPECTED_JOBNAME}  # 返回后续监控、事故、恢复、原生结果和发布共同使用的闭合上下文。


def validate_file_snapshot(snapshot: Any, path: Path, label: str) -> None:  # 接收监控或恢复终态快照、当前原件和标签并逐项核对存在、大小与纳秒时刻。
    require(isinstance(snapshot, dict), f"{label} 快照不是对象")  # 错型快照无法证明退出时原件身份。
    stat = path.stat()  # 读取当前普通文件元数据供终态提交后漂移检查。
    require(snapshot.get("exists") is True and int(snapshot.get("size_bytes", -1)) == int(stat.st_size) and int(snapshot.get("mtime_ns", -1)) == int(stat.st_mtime_ns), f"{label} 在终态提交后发生变化")  # 三项完全一致才接受当前原件。


def validate_monitor_chain(context: dict[str, Any]) -> dict[str, Any]:  # 接收准备启动上下文并返回由完整 JSONL 独立复算的干净 operator ABT 后监控摘要。
    run_dir = context["run_dir"]  # 读取唯一事故运行根供固定 QA 路径定位。
    claim_path = run_dir / "qa" / "runtime_hard_stop_monitor_claim.json"  # 定位监控器在首次采样和任何动作前排他提交的认领。
    samples_path = run_dir / "qa" / "runtime_hard_stop_monitor_samples.jsonl"  # 定位持续刷盘的进程、资源和日志增量流水。
    final_path = run_dir / "qa" / "runtime_hard_stop_monitor_final.json"  # 定位进程树稳定退出后提交的监控终态。
    require(claim_path.is_file() and samples_path.is_file() and final_path.is_file(), "缺少监控 claim、samples 或 final 工件")  # 三件缺一均不能证明持续无硬事件退出。
    claim = read_json(claim_path)  # 读取冻结监控代码、启动链摘要和初始进程绑定。
    samples_payload = samples_path.read_bytes()  # 一次读取完整最终 JSONL 原件供逐行和历史前缀复核。
    samples, raw_lines = parse_jsonl_bytes(samples_payload)  # 严格解析对象序列并保留每条原始字节。
    final = read_json(final_path)  # 读取资源极值、硬事件、控制器动作和终态文件快照。
    indexes = [int(sample.get("sample_index", -1)) for sample in samples]  # 提取样本序号供连续性复算。
    available_ram = [int(sample.get("physical_memory_available_bytes", -1)) for sample in samples]  # 提取每轮可用物理内存供最小值复算。
    disk_free = [int(sample.get("disk_free_bytes", -1)) for sample in samples]  # 提取每轮运行盘余量供最小值复算。
    related_rss = [int(sample.get("related_rss_bytes", -1)) for sample in samples]  # 提取本 job 进程合计工作集供峰值复算。
    low_ram_seconds = [float(sample.get("low_ram_continuous_seconds", -1.0)) for sample in samples]  # 提取连续低内存计时供六十秒硬线复算。
    sample_equations = [int(value) for sample in samples for value in sample.get("new_equation_counts", [])]  # 按流水顺序重建监控观察到的全部方程数。
    sample_hard_events = [event for sample in samples for event in sample.get("new_hard_events", [])]  # 按流水顺序重建控制器全部硬事件。
    require(all(sample.get("schema_version") == 1 for sample in samples), "监控样本存在未知 schema")  # 只接受冻结第一版对象记录。
    require(indexes == list(range(1, len(samples) + 1)), "监控样本序号未从 1 连续递增")  # 防止删行、插入或重排。
    require(claim.get("schema_version") == 1 and claim.get("status") == "MONITOR_CLAIMED", "监控认领 schema 或状态错误")  # 只接受采样前冻结的第一版认领语义。
    require(claim.get("run_name") == run_dir.name and claim.get("jobname") == EXPECTED_JOBNAME, "监控认领运行或 job 身份错配")  # 关闭跨运行工件复制。
    require(claim.get("runtime_launch_sha256") == sha256_file(context["launch_path"]) and claim.get("runtime_launch_claim_sha256") == sha256_file(context["launch_claim_path"]), "监控认领引用的启动链摘要不一致")  # 证明监控附着当前不可覆盖启动链。
    require(claim.get("runtime_process_identity_sha256") == sha256_file(context["identity_path"]), "监控认领引用的增强进程身份摘要不一致")  # 证明监控绑定当前防 PID 回收身份。
    monitor_relative = str(context["manifest"].get("runtime_monitor_script", "")).replace("\\", "/")  # 规范化 manifest 声明的冻结监控器路径。
    require(monitor_relative == "input_snapshot/ultra_c10_adaptive_monitor.py" and monitor_relative in context["prepared_entries"], "准备账本未冻结批准监控器快照")  # 固定持续监控代码属于启动前谱系。
    require(claim.get("monitor_script_sha256") == context["manifest"].get("runtime_monitor_script_sha256") == context["prepared_entries"][monitor_relative], "监控代码在 claim、manifest 和准备账本间不一致")  # 三方闭合实际执行代码字节身份。
    require(final.get("schema_version") == 1 and final.get("status") == MONITOR_FINAL_STATUS, "监控终态不是无硬停的自然稳定退出")  # 任何硬停、缺失或不完整状态均拒绝封存。
    require(final.get("run_name") == run_dir.name and final.get("jobname") == EXPECTED_JOBNAME, "监控终态运行或 job 身份错配")  # 关闭其他运行终态复制。
    require(final.get("monitor_claim_sha256") == sha256_file(claim_path), "监控终态引用的 claim 摘要不一致")  # 防止终态提交后替换初始认领。
    require(final.get("samples_path") is not None and Path(str(final.get("samples_path"))).resolve() == samples_path.resolve(), "监控终态引用的 samples 路径不属于当前运行")  # 关闭跨运行 JSONL 借用。
    require(final.get("samples_sha256") == sha256_bytes(samples_payload), "监控终态引用的完整 samples 摘要不一致")  # 补上样本内容身份门而非只核计数。
    require(int(final.get("sample_count", -1)) == len(samples), "监控终态 sample_count 不能由 JSONL 复算")  # 防止尾部删行或终态少计。
    require(final.get("hard_events") == sample_hard_events == [], "监控流水或终态记录了硬事件")  # 当前冻结监控器没有任何批准的正常 operator abort 事件类别。
    controller_abort = final.get("controller_abort")  # 读取监控器自己的 ABT 与进程处置对象。
    require(isinstance(controller_abort, dict) and controller_abort.get("requested") is False, "监控器请求过独立中止或 controller_abort 错型")  # operator 恢复工具必须是唯一中止提交者。
    process_disposition = controller_abort.get("process_disposition")  # 读取可能记录 terminate/kill PID 的处置对象。
    terminate_pids = process_disposition.get("terminate_sent_pids", []) if isinstance(process_disposition, dict) else []  # 将无处置对象规范为空 terminate 列表。
    kill_pids = process_disposition.get("kill_sent_pids", []) if isinstance(process_disposition, dict) else []  # 将无处置对象规范为空 kill 列表。
    require(terminate_pids == [] and kill_pids == [], "监控器发送过 terminate 或 kill 进程动作")  # 不允许把强制处置误归为原生 ABT 停机。
    require(final.get("monitor_block_reason") is None and final.get("final_related_processes") == [], "监控终态仍有阻断或本 job 进程")  # 退出证据必须闭合且进程树清空。
    require(isinstance(final.get("final_lock_file"), dict) and final["final_lock_file"].get("exists") is False and not any(context["solver_dir"].glob("*.lock")), "监控终态或当前 solver 仍存在 lock")  # 双向证明数据库已经关闭。
    require(all(value > 0 for value in available_ram) and min(available_ram) == int(final.get("minimum_physical_memory_available_bytes", -1)), "监控最小可用内存不能由流水复算")  # 独立复算资源极值。
    require(all(value > 0 for value in disk_free) and min(disk_free) == int(final.get("minimum_disk_free_bytes", -1)), "监控最小磁盘余量不能由流水复算")  # 独立复算磁盘极值。
    require(all(value >= 0 for value in related_rss) and max(related_rss) == int(final.get("maximum_related_rss_bytes", -1)), "监控最大工作集不能由流水复算")  # 独立复算本 job 内存峰值。
    require(all(math.isfinite(value) and 0.0 <= value < 60.0 for value in low_ram_seconds), "监控出现持续六十秒低内存或无效计时")  # 资源硬线不得被 operator ABT 掩盖。
    require(sample_equations == final.get("observed_equation_counts") and final.get("unique_equation_counts") == [EXPECTED_EQUATION_COUNT], "监控方程数流水缺失、漂移或摘要不一致")  # 保持单层拓扑方程秩不变。
    require(int(final.get("minimum_physical_memory_available_bytes", 0)) >= 512 * 1024**2 and int(final.get("minimum_disk_free_bytes", 0)) >= 32 * 1024**3, "监控资源极值越过硬停线却未形成事件")  # 独立复核控制器资源动作合同。
    validate_file_snapshot(final.get("final_out_file"), context["output_path"], "监控 final OUT")  # 证明监控终态后 OUT 未增长或被替换。
    validate_file_snapshot(final.get("final_err_file"), context["error_path"], "监控 final ERR")  # 证明监控终态后 ERR 未增长或被替换。
    validate_file_snapshot(final.get("final_mntr_file"), context["mntr_path"], "监控 final MNTR")  # 证明监控终态后 MNTR 未新增接受步。
    return {"claim_path": claim_path, "samples_path": samples_path, "final_path": final_path, "claim": claim, "samples": samples, "raw_lines": raw_lines, "samples_payload": samples_payload, "final": final, "claim_sha256": sha256_file(claim_path), "samples_sha256": sha256_bytes(samples_payload), "final_sha256": sha256_file(final_path), "sample_count": len(samples), "minimum_physical_memory_available_bytes": min(available_ram), "minimum_disk_free_bytes": min(disk_free), "maximum_related_rss_bytes": max(related_rss), "maximum_low_ram_continuous_seconds": max(low_ram_seconds), "observed_equation_counts": sample_equations, "hard_events": [], "controller_abort_requested": False, "terminate_sent_pids": [], "kill_sent_pids": [], "files_stable_at_monitor_commit": True}  # 返回全部由原始流水重算的持续监控、资源、方程和无强制动作摘要。


def validate_old_operator_chain(context: dict[str, Any], monitor_audit: dict[str, Any], mntr_rows: list[dict[str, float | int]]) -> dict[str, Any]:  # 接收运行、最终监控与 MNTR 并闭合旧空 ABT claim、说明和超时 final 事故事实。
    run_dir = context["run_dir"]  # 读取唯一事故运行根供旧 QA 工件定位。
    claim_path = run_dir / "qa" / "runtime_operator_stop_claim.json"  # 定位旧工具在空 ABT 前提交的机器认领。
    explanation_path = run_dir / "qa" / "runtime_operator_stop_claim.md"  # 定位旧动作相邻中文说明。
    final_path = run_dir / "qa" / "runtime_operator_stop_final.json"  # 定位旧空 ABT 未获退出确认后的追加式终态。
    require(claim_path.is_file() and explanation_path.is_file() and explanation_path.stat().st_size > 0 and final_path.is_file(), "缺少旧 operator claim、说明或 final")  # 三件缺一不能说明为何需要恢复工具。
    require(OLD_STOP_TOOL_PATH.is_file(), "旧 operator 工具当前源码路径缺失")  # 当前源码允许在事故后被新版替代，执行时字节由旧 claim 与恢复工具固定摘要共同证明。
    current_old_tool_sha256 = sha256_file(OLD_STOP_TOOL_PATH)  # 记录事故后当前源码摘要并与执行时固定摘要明确区分。
    claim = read_json(claim_path)  # 读取动作前进程、MNTR、OUT 和投影冻结事实。
    final = read_json(final_path)  # 读取空 ABT 消费、等待超时和绝无强制动作事实。
    claim_sha256 = sha256_file(claim_path)  # 计算旧 claim 当前摘要供恢复链逐段闭合。
    final_sha256 = sha256_file(final_path)  # 计算旧 final 当前摘要供恢复 claim、plan、executed 和 final 引用。
    require(claim.get("schema_version") == 2 and claim.get("status") == OLD_OPERATOR_CLAIM_STATUS, "旧 operator claim schema 或状态不符合空 ABT 事故分支")  # 只接受已知第二版认领。
    require(claim.get("run_name") == run_dir.name and claim.get("jobname") == EXPECTED_JOBNAME, "旧 operator claim 运行或 job 身份错配")  # 阻断跨运行旧认领复制。
    require(claim.get("tool_sha256") == OLD_STOP_TOOL_SHA256, "旧 operator claim 未引用冻结空 ABT 工具摘要")  # 闭合真实动作实现身份。
    require(claim.get("prepared_ledger_sha256") == context["prepared_ledger_sha256"] and int(claim.get("prepared_ledger_entry_count", -1)) == len(context["prepared_entries"]), "旧 operator claim 准备账本身份不一致")  # 证明停机决策针对当前冻结输入。
    require(claim.get("runtime_launch_claim_sha256") == sha256_file(context["launch_claim_path"]) and claim.get("runtime_launch_sha256") == sha256_file(context["launch_path"]) and claim.get("runtime_process_identity_sha256") == sha256_file(context["identity_path"]), "旧 operator claim 启动身份链断裂")  # 关闭跨进程动作复制。
    require(claim.get("runtime_monitor_claim_sha256") == monitor_audit["claim_sha256"], "旧 operator claim 引用的监控 claim 摘要不一致")  # 固定持续监控附着身份。
    decision_sample_count = int(claim.get("runtime_monitor_sample_count_at_decision", -1))  # 读取旧决策时完整监控样本数供最终 JSONL 前缀复算。
    require(claim.get("runtime_monitor_samples_sha256_at_decision") == jsonl_prefix_sha256(monitor_audit["raw_lines"], decision_sample_count), "旧 operator claim 的监控决策前缀摘要不能由最终 JSONL 复算")  # 证明最终流水保留旧决策时所有字节。
    require(int(claim.get("latest_monitor_sample_index", -1)) == decision_sample_count, "旧 operator claim 最新样本序号与决策计数不一致")  # 防止借用不同样本时刻的 OUT 偏移。
    require(claim.get("sufficiency_branch") == "A_TWO_ACCEPTED_MINIMUM_STEPS" and claim.get("accepted_pair_gate_satisfied") is True and claim.get("in_progress_lower_bound_gate_satisfied") is False, "旧 operator claim 不是两个完整接受步的门 A")  # 当前事故只允许完成步实测速率，不接受在途下界分支。
    require(int(claim.get("accepted_ls2_substep_count", -1)) == EXPECTED_ACCEPTED_LS2_STEPS, "旧 operator claim 不是恰好两个 LS2 接受步")  # 冻结动作前状态规模。
    claimed_ls2_rows = claim.get("accepted_ls2_rows")  # 读取旧 claim 保存的全部 LS2 接受行。
    require(isinstance(claimed_ls2_rows, list) and claimed_ls2_rows == mntr_rows[1:], "旧 operator claim 的 LS2 行与最终 MNTR 恰好两行不一致")  # 证明 ABT 前后没有接受第三步或改写行。
    claimed_sufficiency = evaluate_sufficiency([mntr_rows[0], *claimed_ls2_rows])  # 独立重算旧 claim 的完整步耗时与七天投影。
    require(claim.get("latest_two_ls2_rows") == claimed_ls2_rows, "旧 operator claim 的 latest_two 与完整两行不一致")  # 当前恰好两行时两个视图必须完全相同。
    require(int(claim.get("later_step_completed_iterations", -1)) == claimed_sufficiency["later_step_iterations"], "旧 operator claim 后一步迭代数不能由 MNTR 复算")  # 固定至少二十次 Newton 迭代事实。
    require(math.isclose(float(claim.get("measured_or_lower_bound_seconds_per_minimum_step", -1.0)), float(claimed_sufficiency["measured_seconds_per_minimum_step"]), rel_tol=0.0, abs_tol=1.0e-9), "旧 operator claim 实测单步秒数不能由 MNTR 复算")  # 阻断投影基数漂移。
    require(int(claim.get("remaining_minimum_step_count", -1)) == claimed_sufficiency["remaining_minimum_step_count"] and math.isclose(float(claim.get("projected_remaining_seconds", -1.0)), float(claimed_sufficiency["projected_remaining_seconds"]), rel_tol=0.0, abs_tol=1.0e-6), "旧 operator claim 剩余步数或七天投影不能复算")  # 重算而不是照抄决策结论。
    require(claim.get("projection_strictly_exceeds_seven_days") is True and claim.get("modal_execution_allowed") is False and claim.get("production_claim_allowed") is False, "旧 operator claim 未保持七天门或用途禁令")  # 关闭停机授权边界。
    require(claim.get("mntr_path") == f"solver/{EXPECTED_JOBNAME}.mntr" and claim.get("mntr_sha256_at_decision") == sha256_file(context["mntr_path"]), "旧 operator claim 的 MNTR 路径或摘要与最终原件不一致")  # 恰好两行意味着动作后 MNTR 不得增长。
    prefix_size = int(claim.get("sampled_out_prefix_size_bytes", -1))  # 读取旧最后监控样本已经扫描的 OUT 字节数。
    output_payload = context["output_path"].read_bytes()  # 读取最终 OUT 供旧决策前缀身份复算。
    require(0 < prefix_size <= len(output_payload), "旧 operator claim 的 OUT 前缀大小越界")  # 阻断负值、空值或超出最终原件。
    require(claim.get("sampled_out_prefix_sha256") == sha256_bytes(output_payload[:prefix_size]), "旧 operator claim 的 OUT 前缀摘要不能由最终 OUT 复算")  # 证明终止消息位于决策后新增尾部而非预先存在。
    decision_sample = monitor_audit["samples"][decision_sample_count - 1]  # 定位旧 claim 同一轮最后监控样本。
    require(int(decision_sample.get("out_offset_bytes", -1)) == prefix_size, "旧 operator claim OUT 前缀大小与同轮监控样本偏移不一致")  # 闭合 elapsed、进程与日志时刻。
    require(claim.get("native_abort_path_planned") == f"solver/{EXPECTED_JOBNAME}.abt", "旧 operator claim 计划的 ABT 路径不属于固定 job")  # 固定错误空控制文件目标。
    require(final.get("schema_version") == 1 and final.get("status") == OLD_OPERATOR_FINAL_STATUS, "旧 operator final 不是批准的一千八百秒无强制动作超时状态")  # 仅该事故分支允许后续有效恢复。
    require(final.get("run_name") == run_dir.name and final.get("jobname") == EXPECTED_JOBNAME, "旧 operator final 运行或 job 身份错配")  # 阻断跨运行终态复制。
    require(final.get("operator_stop_claim_path") == "qa/runtime_operator_stop_claim.json" and final.get("operator_stop_claim_sha256") == claim_sha256, "旧 operator final 未引用当前旧 claim")  # 闭合动作前认领到旧终态。
    require(final.get("operator_stop_explanation_path") == "qa/runtime_operator_stop_claim.md" and final.get("operator_stop_explanation_sha256") == sha256_file(explanation_path), "旧 operator final 未引用当前中文说明")  # 闭合人工说明身份。
    require(math.isfinite(float(final.get("wait_seconds", -1.0))) and float(final.get("wait_seconds", -1.0)) >= 1795.0, "旧 operator final 实际等待不足一千八百秒容差")  # 允许五秒轮询边界但拒绝提前伪封板。
    require(final.get("exact_process_tree_exit_confirmed") is False and final.get("block_reason") == OLD_OPERATOR_BLOCK_REASON, "旧 operator final 错误声明退出或超时原因漂移")  # 固定空 ABT 未生效事实。
    require(final.get("native_abort_created_exclusively") is True and final.get("native_abort_initial_sha256") == EMPTY_SHA256 and final.get("native_abort_exists_at_finalization") is False, "旧 operator final 未如实记录排他空 ABT 及其已被消费")  # 闭合事故根因是零字节载荷。
    require(final.get("operator_tool_process_terminate_api_called") is False and final.get("operator_tool_process_kill_api_called") is False and final.get("operator_tool_forced_process_action_allowed") is False, "旧 operator 工具未证明绝无进程强制处置")  # 任何主动动作都会污染后续因果链。
    require(final.get("valid_static_result_obtained") is False and final.get("modal_execution_allowed") is False and final.get("production_claim_allowed") is False, "旧 operator final 意外允许静力、模态或生产使用")  # 保持失败关闭用途边界。
    old_out_snapshot = final.get("final_out_file")  # 读取旧超时终态所见 OUT 大小供动作后确认尾部切分。
    old_err_snapshot = final.get("final_err_file")  # 读取旧超时终态所见 ERR 大小供动作后确认尾部切分。
    require(isinstance(old_out_snapshot, dict) and old_out_snapshot.get("exists") is True and isinstance(old_err_snapshot, dict) and old_err_snapshot.get("exists") is True, "旧 operator final 缺少 OUT/ERR 超时快照")  # 无动作前基线时不能定位恢复后原生终止消息。
    return {"claim_path": claim_path, "explanation_path": explanation_path, "final_path": final_path, "claim": claim, "final": final, "claim_sha256": claim_sha256, "explanation_sha256": sha256_file(explanation_path), "final_sha256": final_sha256, "decision_sample_count": decision_sample_count, "sampled_out_prefix_size_bytes": prefix_size, "old_final_out_size_bytes": int(old_out_snapshot.get("size_bytes", -1)), "old_final_err_size_bytes": int(old_err_snapshot.get("size_bytes", -1)), "sufficiency": claimed_sufficiency, "executed_old_tool_sha256": OLD_STOP_TOOL_SHA256, "current_old_tool_source_sha256": current_old_tool_sha256, "current_old_tool_source_matches_executed_version": current_old_tool_sha256 == OLD_STOP_TOOL_SHA256, "executed_version_proven_by_claim_and_recovery_pre_action_hash_gate": True, "empty_abort_incident_proven": True, "operator_force_actions": False}  # 返回恢复链、源码替代披露、原生日志切分和最终报告共同使用的旧事故审计。


def validate_artifact_receipt(receipt: Any, path: Path, label: str) -> None:  # 接收恢复 final 内嵌工件回执、真实路径和标签并核对存在、大小与摘要。
    require(isinstance(receipt, dict), f"{label} 工件回执不是对象")  # 错型回执无法证明追加式工件身份。
    require(receipt.get("path") == path.name and receipt.get("exists") is True, f"{label} 工件回执路径或存在性错误")  # 恢复工具按 basename 记录固定 QA 工件。
    require(int(receipt.get("size_bytes", -1)) == int(path.stat().st_size) and receipt.get("sha256") == sha256_file(path), f"{label} 工件回执大小或摘要漂移")  # 逐字节闭合恢复 final 与先行回执。


def validate_recovery_chain(context: dict[str, Any], monitor_audit: dict[str, Any], old_audit: dict[str, Any], mntr_rows: list[dict[str, float | int]]) -> dict[str, Any]:  # 接收完整前置上下文并闭合有效 nonlinear ABT 的 claim、说明、计划、执行和 final 五件链。
    run_dir = context["run_dir"]  # 读取唯一事故运行根供固定恢复 QA 工件定位。
    qa_dir = run_dir / "qa"  # 定位准备期已存在且承载全部操作员证据的 QA 目录。
    claim_path = qa_dir / "runtime_operator_stop_recovery_claim.json"  # 定位有效 ABT 前先行机器认领。
    explanation_path = qa_dir / "runtime_operator_stop_recovery_claim.md"  # 定位事故恢复中文说明。
    plan_path = qa_dir / "runtime_operator_stop_recovery_action_plan.json"  # 定位有效字节落盘前动作计划回执。
    executed_path = qa_dir / "runtime_operator_stop_recovery_action_executed.json"  # 定位排他创建、fsync 和回读后的执行回执。
    final_path = qa_dir / "runtime_operator_stop_recovery_final.json"  # 定位进程树、lock、原件和监控均稳定后的恢复终态。
    recovery_paths = [claim_path, explanation_path, plan_path, executed_path, final_path]  # 汇总固定五件链供存在性和报告使用。
    require(all(path.is_file() and path.stat().st_size > 0 for path in recovery_paths), "有效 ABT 恢复 claim、说明、plan、executed 或 final 缺失/为空")  # 五件缺一均不能声明受控停机。
    require(RECOVERY_TOOL_PATH.is_file() and sha256_file(RECOVERY_TOOL_PATH) == RECOVERY_TOOL_SHA256, "有效 ABT 恢复工具源码缺失或摘要漂移")  # 固定双回执、同步和无进程信号实现字节。
    claim = read_json(claim_path)  # 读取恢复授权、历史链与有效载荷计划。
    plan = read_json(plan_path)  # 读取任何有效字节落盘前提交的动作回执。
    executed = read_json(executed_path)  # 读取同一创建者句柄仍打开时形成的动作后回执。
    final = read_json(final_path)  # 读取自然退出、监控闭环和绝无强制处置终态。
    claim_sha256 = sha256_file(claim_path)  # 计算恢复 claim 当前摘要供 plan、executed 和 final 交叉核对。
    plan_sha256 = sha256_file(plan_path)  # 计算动作计划当前摘要供执行回执交叉核对。
    executed_sha256 = sha256_file(executed_path)  # 计算执行回执当前摘要供 final 工件审计核对。
    final_sha256 = sha256_file(final_path)  # 计算恢复终态当前摘要供最终追加账本与根状态引用。
    require(claim.get("schema_version") == 1 and claim.get("status") == RECOVERY_CLAIM_STATUS, "恢复 claim schema 或状态错误")  # 只接受有效 ABT 前先行认领状态。
    require(claim.get("run_name") == run_dir.name and claim.get("jobname") == EXPECTED_JOBNAME, "恢复 claim 运行或 job 身份错配")  # 阻断跨运行有效载荷回执复制。
    require(claim.get("recovery_tool_sha256") == RECOVERY_TOOL_SHA256 and claim.get("prior_tool_sha256") == OLD_STOP_TOOL_SHA256, "恢复 claim 的新旧工具摘要不一致")  # 闭合事故与修复两段源码身份。
    require(claim.get("prior_operator_claim_path") == "qa/runtime_operator_stop_claim.json" and claim.get("prior_operator_claim_sha256") == old_audit["claim_sha256"], "恢复 claim 未引用当前旧 operator claim")  # 闭合旧动作前认领。
    require(claim.get("prior_operator_final_path") == "qa/runtime_operator_stop_final.json" and claim.get("prior_operator_final_sha256") == old_audit["final_sha256"], "恢复 claim 未引用当前旧 operator final")  # 闭合空 ABT 超时终态。
    require(claim.get("prior_controller_exact_identity_absent") is True, "恢复 claim 未证明旧控制器精确身份已退出")  # 防止两个操作员控制器并发竞争。
    require(claim.get("prepared_ledger_sha256") == context["prepared_ledger_sha256"] and int(claim.get("prepared_ledger_entry_count", -1)) == len(context["prepared_entries"]), "恢复 claim 准备账本身份不一致")  # 固定有效动作仍针对同一启动前字节。
    require(claim.get("runtime_launch_claim_sha256") == sha256_file(context["launch_claim_path"]) and claim.get("runtime_launch_sha256") == sha256_file(context["launch_path"]) and claim.get("runtime_process_identity_sha256") == sha256_file(context["identity_path"]), "恢复 claim 启动身份链断裂")  # 关闭跨进程恢复动作复制。
    require(claim.get("runtime_monitor_claim_sha256") == monitor_audit["claim_sha256"], "恢复 claim 引用的监控 claim 摘要不一致")  # 绑定同一持续监控器。
    recovery_sample_count = int(claim.get("runtime_monitor_sample_count_at_recovery_decision", -1))  # 读取有效动作决策时完整监控样本数。
    require(claim.get("runtime_monitor_samples_sha256_at_recovery_decision") == jsonl_prefix_sha256(monitor_audit["raw_lines"], recovery_sample_count), "恢复 claim 的监控决策前缀摘要不能由最终 JSONL 复算")  # 证明动作前所有监控字节被最终流水保留。
    require(claim.get("mntr_sha256_at_recovery_decision") == sha256_file(context["mntr_path"]), "恢复 claim 的 MNTR 摘要与最终恰好两步原件不一致")  # 有效 ABT 前后不得接受第三步。
    require(int(claim.get("accepted_ls2_substep_count", -1)) == EXPECTED_ACCEPTED_LS2_STEPS and claim.get("latest_two_ls2_rows") == mntr_rows[1:], "恢复 claim 未冻结最终 MNTR 的恰好两个 LS2 行")  # 固定动作状态未跨接受步变化。
    sufficiency = evaluate_sufficiency(mntr_rows)  # 再次从最终 MNTR 独立重算七天门供恢复字段核对。
    require(math.isclose(float(claim.get("measured_seconds_per_minimum_step", -1.0)), float(sufficiency["measured_seconds_per_minimum_step"]), rel_tol=0.0, abs_tol=1.0e-9), "恢复 claim 实测最小步秒数不能复算")  # 防止动作前后投影基数漂移。
    require(int(claim.get("remaining_minimum_step_count", -1)) == sufficiency["remaining_minimum_step_count"] and math.isclose(float(claim.get("projected_remaining_seconds", -1.0)), float(sufficiency["projected_remaining_seconds"]), rel_tol=0.0, abs_tol=1.0e-6), "恢复 claim 剩余步数或七天投影不能复算")  # 固定充分性门的算术证据。
    abort_relative = f"solver/{EXPECTED_JOBNAME}.abt"  # 构造当前 job 唯一有效控制文件相对路径。
    require(claim.get("native_abort_target_path") == abort_relative and claim.get("native_abort_created_at_claim_time") is False, "恢复 claim 的 ABT 目标或动作前存在性错误")  # 先认领后动作必须有明确时序。
    require(claim.get("native_abort_payload_text_planned") == ABT_PAYLOAD.decode("ascii") and int(claim.get("native_abort_payload_length_bytes_planned", -1)) == ABT_PAYLOAD_LENGTH and claim.get("native_abort_payload_hex_planned") == ABT_PAYLOAD_HEX and claim.get("native_abort_payload_sha256_planned") == ABT_PAYLOAD_SHA256, "恢复 claim 的计划 ABT 字节合同错误")  # 同时核对文本、长度、十六进制和摘要。
    monitor_relative = str(context["manifest"].get("runtime_monitor_script", "")).replace("\\", "/")  # 取得冻结监控器运行内路径供已知风险字段核对。
    monitor_script_path = (run_dir / Path(monitor_relative)).resolve()  # 规范化实际冻结监控器源码路径。
    require(claim.get("frozen_monitor_path") == monitor_relative and claim.get("frozen_monitor_sha256") == sha256_file(monitor_script_path), "恢复 claim 的冻结监控器路径或摘要不一致")  # 披露风险必须由真实源码字节支持。
    require(claim.get("frozen_monitor_native_abort_payload_contract_valid") is False and claim.get("frozen_monitor_invalid_abort_first_line_prefix") == RECOVERY_INVALID_ABORT_PREFIX and claim.get("recovery_tool_will_not_invoke_frozen_monitor_abort_function") is True, "恢复 claim 未披露监控器非法 ABT 分支或隔离承诺")  # 证明有效动作没有调用旧危险函数。
    require(claim.get("all_monitor_hard_events_before_valid_abort_required_empty") is True and claim.get("post_action_monitor_events_require_explicit_expected_vs_unexpected_classification") is True, "恢复 claim 未冻结监控事件时序分类规则")  # 不允许 ABT 掩盖动作前硬错误。
    require(claim.get("operator_tool_forced_process_action_allowed") is False and claim.get("modal_execution_allowed") is False and claim.get("production_claim_allowed") is False, "恢复 claim 意外允许强制动作、模态或生产")  # 维持动作与用途边界。
    claim_time = parse_utc(claim.get("claimed_at_utc"), "恢复 claim claimed_at_utc")  # 解析恢复认领真实 UTC 时刻供双回执顺序核对。
    require(plan.get("schema_version") == 1 and plan.get("status") == RECOVERY_PLAN_STATUS and plan.get("run_name") == run_dir.name and plan.get("jobname") == EXPECTED_JOBNAME, "恢复 action plan schema、状态或身份错误")  # 固定动作前计划回执。
    plan_time = parse_utc(plan.get("planned_at_utc"), "恢复 plan planned_at_utc")  # 解析计划时刻供动作先后门。
    require(plan_time == claim_time and plan.get("recovery_tool_sha256") == RECOVERY_TOOL_SHA256 and plan.get("recovery_claim_sha256") == claim_sha256, "恢复 plan 时刻、工具或 claim 摘要不一致")  # 闭合认领与计划由同一决策形成。
    require(plan.get("prior_operator_claim_sha256") == old_audit["claim_sha256"] and plan.get("prior_operator_final_sha256") == old_audit["final_sha256"], "恢复 plan 的旧 operator 链摘要不一致")  # 防止计划切换事故上下文。
    require(plan.get("native_abort_target_path") == abort_relative and plan.get("payload_text") == ABT_PAYLOAD.decode("ascii") and int(plan.get("payload_length_bytes", -1)) == ABT_PAYLOAD_LENGTH and plan.get("payload_hex") == ABT_PAYLOAD_HEX and plan.get("payload_sha256") == ABT_PAYLOAD_SHA256, "恢复 plan 的有效 ABT 精确字节合同错误")  # 四重验证动作计划。
    require(plan.get("exclusive_create_planned") is True and plan.get("native_abort_created") is False and plan.get("payload_written") is False and plan.get("flush_and_fsync_completed") is False and plan.get("readback_matches") is False, "恢复 plan 没有明确保持动作前全 false")  # 防止事后回填计划回执。
    require(plan.get("operator_tool_forced_process_action_allowed") is False, "恢复 plan 意外允许强制进程动作")  # 动作计划只能创建控制文件。
    require(executed.get("schema_version") == 1 and executed.get("status") == RECOVERY_EXECUTED_STATUS and executed.get("run_name") == run_dir.name and executed.get("jobname") == EXPECTED_JOBNAME, "恢复 executed schema、状态或身份错误")  # 只接受有效字节完成后的执行回执。
    created_time = parse_utc(executed.get("created_at_utc"), "恢复 executed created_at_utc")  # 解析排他创建成功真实时刻。
    receipt_time = parse_utc(executed.get("executed_receipt_written_at_utc"), "恢复 executed receipt time")  # 解析同句柄回执完成时刻。
    require(claim_time <= created_time <= receipt_time, "恢复 claim、ABT 创建和执行回执时序倒置")  # 证明计划先于动作且回执后于完整写入。
    require(executed.get("recovery_tool_sha256") == RECOVERY_TOOL_SHA256 and executed.get("recovery_claim_sha256") == claim_sha256 and executed.get("recovery_action_plan_sha256") == plan_sha256, "恢复 executed 的工具、claim 或 plan 摘要不一致")  # 闭合三段追加式动作链。
    require(executed.get("prior_operator_claim_sha256") == old_audit["claim_sha256"] and executed.get("prior_operator_final_sha256") == old_audit["final_sha256"], "恢复 executed 的旧 operator 链摘要不一致")  # 防止动作回执切换历史上下文。
    require(executed.get("native_abort_target_path") == abort_relative and executed.get("payload_text") == ABT_PAYLOAD.decode("ascii") and int(executed.get("payload_length_bytes", -1)) == ABT_PAYLOAD_LENGTH and executed.get("payload_hex") == ABT_PAYLOAD_HEX and executed.get("payload_sha256") == ABT_PAYLOAD_SHA256, "恢复 executed 的实际 ABT 字节合同错误")  # 由回读字节同时闭合四种表示。
    require(executed.get("exclusive_create_succeeded") is True and executed.get("payload_written_fully") is True and executed.get("flush_and_fsync_completed") is True and executed.get("readback_matches_contract") is True and executed.get("abort_path_visible_while_creator_handle_open") is True, "恢复 executed 未证明排他创建、完整写入、fsync、回读或句柄内可见")  # 五项动作事实必须全 true。
    require(executed.get("operator_tool_forced_process_action_allowed") is False, "恢复 executed 意外允许强制进程动作")  # 执行回执只证明文件控制动作。
    require(final.get("schema_version") == 1 and final.get("status") == RECOVERY_FINAL_STATUS and final.get("run_name") == run_dir.name and final.get("jobname") == EXPECTED_JOBNAME, "恢复 final 不是有效 ABT 后进程树稳定退出状态")  # 任何 NOT_CLEAN、TIMEOUT 或 INCOMPLETE 分支都失败关闭。
    finalized_time = parse_utc(final.get("finalized_at_utc"), "恢复 final finalized_at_utc")  # 解析恢复终态提交时刻。
    require(finalized_time >= receipt_time and final.get("recovery_tool_sha256") == RECOVERY_TOOL_SHA256 and final.get("prior_tool_sha256") == OLD_STOP_TOOL_SHA256, "恢复 final 时序或新旧工具摘要不一致")  # 固定动作后终态与源码身份。
    require(final.get("prior_operator_claim_sha256") == old_audit["claim_sha256"] and final.get("prior_operator_final_sha256") == old_audit["final_sha256"], "恢复 final 的旧 operator 摘要链不一致")  # 闭合事故根因到最终退出。
    validate_artifact_receipt(final.get("recovery_claim"), claim_path, "恢复 claim")  # 复算恢复 final 内嵌 claim 工件回执。
    validate_artifact_receipt(final.get("recovery_explanation"), explanation_path, "恢复说明")  # 复算恢复 final 内嵌中文说明回执。
    validate_artifact_receipt(final.get("recovery_action_plan"), plan_path, "恢复 plan")  # 复算恢复 final 内嵌动作前回执。
    validate_artifact_receipt(final.get("recovery_action_executed"), executed_path, "恢复 executed")  # 复算恢复 final 内嵌动作后回执。
    require(final.get("native_abort_path") == abort_relative and final.get("native_abort_payload_text") == ABT_PAYLOAD.decode("ascii") and int(final.get("native_abort_payload_length_bytes", -1)) == ABT_PAYLOAD_LENGTH and final.get("native_abort_payload_hex") == ABT_PAYLOAD_HEX and final.get("native_abort_payload_sha256") == ABT_PAYLOAD_SHA256, "恢复 final 的有效 ABT 精确字节合同错误")  # 不允许 final 用概述替代动作回执字节。
    require(final.get("native_abort_created_exclusively") is True and parse_utc(final.get("native_abort_created_at_utc"), "恢复 final native_abort_created_at_utc") == created_time, "恢复 final 的排他创建或真实动作时刻不一致")  # 闭合执行回执与终态的同一动作。
    require(final.get("native_abort_payload_written_fully") is True and final.get("native_abort_flush_and_fsync_completed") is True and final.get("native_abort_readback_matches_contract") is True, "恢复 final 未证明完整写入、同步和回读")  # 三项动作后事实必须保持 true。
    abort_path = context["solver_dir"] / f"{EXPECTED_JOBNAME}.abt"  # 定位已经由 MAPDL 消费的有效 ABT 路径。
    require(final.get("native_abort_exists_at_finalization") is False and not abort_path.exists(), "有效 ABT 未被 MAPDL 消费或当前又出现控制文件")  # 消费事实与当前路径双向闭合。
    require(final.get("exact_process_tree_exit_confirmed") is True and final.get("block_reason") is None, "恢复 final 未确认进程树退出或仍有阻断原因")  # 只接受无阻断稳定退出。
    require(final.get("operator_tool_process_terminate_api_called") is False and final.get("operator_tool_process_kill_api_called") is False and final.get("operator_tool_process_send_signal_api_called") is False and final.get("operator_tool_forced_process_action_allowed") is False, "恢复工具调用过进程信号、terminate 或 kill")  # 原生 ABT 必须是唯一退出动作。
    require(final.get("valid_static_result_obtained") is False and final.get("modal_execution_allowed") is False and final.get("production_claim_allowed") is False, "恢复 final 意外声明有效静力、模态或生产用途")  # 受控停止不等于静力端点完成。
    require(final.get("causal_native_abort_acknowledgement_proven_by_process_exit_alone") is False, "恢复 final 错把进程退出单独当作 ABT 因果证明")  # 原生日志签名由最终终结器另行补强。
    require(final.get("frozen_monitor_path") == monitor_relative and final.get("frozen_monitor_sha256") == sha256_file(monitor_script_path), "恢复 final 的冻结监控器路径或摘要不一致")  # 保留已知风险实现身份。
    require(final.get("frozen_monitor_native_abort_payload_contract_valid") is False and final.get("frozen_monitor_invalid_abort_first_line_prefix") == RECOVERY_INVALID_ABORT_PREFIX and final.get("recovery_tool_called_frozen_monitor_abort_function") is False, "恢复 final 未证明隔离冻结监控器非法 ABT 分支")  # 有效 nonlinear 必须由恢复工具直接写入。
    validate_file_snapshot(final.get("final_out_file"), context["output_path"], "恢复 final OUT")  # 证明恢复终态后 OUT 未增长或替换。
    validate_file_snapshot(final.get("final_err_file"), context["error_path"], "恢复 final ERR")  # 证明恢复终态后 ERR 未增长或替换。
    validate_file_snapshot(final.get("final_mntr_file"), context["mntr_path"], "恢复 final MNTR")  # 证明恢复终态后未接受第三个 LS2 步。
    require(isinstance(final.get("final_lock_file"), dict) and final["final_lock_file"].get("exists") is False, "恢复 final 的 lock 终态不是不存在")  # 数据库关闭必须由恢复工具独立观察。
    embedded = final.get("frozen_monitor_final")  # 读取恢复工具对真实监控 final 的完整稳定审计摘要。
    require(isinstance(embedded, dict), "恢复 final 缺少冻结监控终态审计")  # 无独立监控闭环不得声明干净退出。
    require(embedded.get("path") == "qa/runtime_hard_stop_monitor_final.json" and embedded.get("sha256") == monitor_audit["final_sha256"], "恢复 final 内嵌监控路径或摘要不一致")  # 绑定当前真实 monitor final 字节。
    require(embedded.get("schema_version") == 1 and embedded.get("run_name") == run_dir.name and embedded.get("jobname") == EXPECTED_JOBNAME and embedded.get("status") == MONITOR_FINAL_STATUS, "恢复内嵌监控 schema、身份或状态错误")  # 闭合独立监控语义。
    require(int(embedded.get("sample_count", -1)) == monitor_audit["sample_count"] == int(embedded.get("actual_sample_line_count", -1)) and embedded.get("sample_sequence_valid") is True, "恢复内嵌监控样本计数或序号不一致")  # 独立复算完整 JSONL 规模。
    require(embedded.get("samples_path_matches") is True and embedded.get("samples_sha256_claimed") == embedded.get("samples_sha256_actual") == monitor_audit["samples_sha256"], "恢复内嵌监控 samples 路径或摘要不一致")  # 闭合终态到完整流水。
    require(embedded.get("hard_events") == [] and embedded.get("controller_abort") == monitor_audit["final"].get("controller_abort") and embedded.get("final_related_processes") == [] and embedded.get("monitor_block_reason") is None, "恢复内嵌监控记录硬事件、控制器动作、进程或阻断")  # 保持 operator ABT 是唯一中止动作。
    classification = embedded.get("operator_abort_event_classification")  # 读取有效动作时刻与硬事件预期性分类。
    require(isinstance(classification, dict), "恢复内嵌监控缺少 operator abort 事件分类")  # 不允许笼统清空事件而不说明时序规则。
    require(parse_utc(classification.get("effective_abort_created_at_utc"), "监控分类有效 ABT 时刻") == created_time and classification.get("approved_expected_event_kinds_for_this_frozen_monitor") == [], "监控分类动作时刻或批准类别错误")  # 当前冻结监控器没有正常 ABT 硬事件类别。
    require(classification.get("expected_operator_abort_events") == [] and classification.get("unexpected_hard_events") == [] and classification.get("all_pre_action_samples_required_clean") is True, "监控分类仍含预期/未预期事件或未要求动作前干净")  # 所有真实硬事件均应阻断 clean 状态。
    risk = embedded.get("frozen_monitor_independent_abort_contract_risk")  # 读取监控器非法首行与进程处置风险披露。
    require(isinstance(risk, dict) and risk.get("request_native_abort_first_line_prefix") == RECOVERY_INVALID_ABORT_PREFIX and risk.get("native_abort_payload_contract_valid") is False and risk.get("recovery_tool_invoked_frozen_monitor_abort_function") is False, "监控器独立 ABT 合同风险披露不完整")  # 固定错误实现且证明未调用。
    require(risk.get("monitor_controller_abort_requested") is False and risk.get("monitor_terminate_sent_pids") == [] and risk.get("monitor_kill_sent_pids") == [], "冻结监控器请求过中止或发送进程处置")  # 排除第二控制者和强制退出。
    return {"claim_path": claim_path, "explanation_path": explanation_path, "plan_path": plan_path, "executed_path": executed_path, "final_path": final_path, "claim": claim, "plan": plan, "executed": executed, "final": final, "claim_sha256": claim_sha256, "explanation_sha256": sha256_file(explanation_path), "plan_sha256": plan_sha256, "executed_sha256": executed_sha256, "final_sha256": final_sha256, "recovery_sample_count": recovery_sample_count, "created_at_utc": executed["created_at_utc"], "created_time": created_time, "payload_contract": {"bytes_length": ABT_PAYLOAD_LENGTH, "hex": ABT_PAYLOAD_HEX, "sha256": ABT_PAYLOAD_SHA256, "exclusive_create_succeeded": True, "payload_written_fully": True, "flush_and_fsync_completed": True, "readback_matches_contract": True, "consumed_by_mapdl": True}, "exact_process_tree_exit_confirmed": True, "monitor_event_classification": classification, "operator_force_actions": False}  # 返回原生日志因果确认和最终封存共同使用的完整有效恢复审计。


def validate_native_files(context: dict[str, Any], old_audit: dict[str, Any], recovery_audit: dict[str, Any], mntr_rows: list[dict[str, float | int]]) -> dict[str, Any]:  # 接收已闭合事故与恢复链并验证 OUT、ERR、MNTR 的原生 ABT 确认、拓扑健康和未达端点事实。
    output_path = context["output_path"]  # 读取命令行冻结的权威 MAPDL OUT 路径。
    error_path = context["error_path"]  # 读取固定 job 独立 ERR 路径。
    mntr_path = context["mntr_path"]  # 读取固定 job 原生接受步历史路径。
    require_files_stable([output_path, error_path, mntr_path], 2.0)  # 在最终监控和恢复快照后再用两秒窗口确认三项原件不增长。
    output_payload = output_path.read_bytes()  # 一次读取完整 OUT 原始字节供前缀、数值和终止签名复核。
    error_payload = error_path.read_bytes()  # 一次读取完整 ERR 原始字节供硬错误与 ABT 确认补充复核。
    mntr_payload = mntr_path.read_bytes()  # 一次读取完整 MNTR 原始字节供调用方解析结果摘要闭合。
    require(parse_mntr_bytes(mntr_payload) == mntr_rows, "稳定窗口后 MNTR 解析结果发生变化")  # 防止验证阶段跨过迟到接受行。
    output_text = output_payload.decode("latin-1", errors="strict")  # Latin-1 一一映射每个 OUT 字节且保留英文数值证据。
    error_text = error_payload.decode("latin-1", errors="strict")  # 以相同策略读取 ERR，避免系统代码页替换。
    combined_text = output_text + "\n" + error_text  # 合并两项原生日志供硬事件全集检查。
    forbidden_matches = [name for name, pattern in FORBIDDEN_NATIVE_PATTERNS if pattern.search(combined_text) is not None]  # 收集 FATAL、病态主元和 CNVTOL 失效类别。
    if re.search(r"PROBLEM\s+TERMINATED\s+DUE\s+TO\s+A\s+FATAL", combined_text, re.IGNORECASE) is not None:  # 捕获无标准星号页眉的等价 MAPDL FATAL 终止摘要。
        forbidden_matches.append("MAPDL_FATAL_TERMINATION")  # 将等价原生致命终止加入统一拒绝列表。
    require(not forbidden_matches, f"OUT/ERR 含不得被 operator ABT 掩盖的硬事件：{forbidden_matches}")  # 任何类别均只能封存为独立硬失败而非诊断充分。
    equation_counts = [int(value) for value in EQUATION_PATTERN.findall(output_text)]  # 提取全部装配/求解阶段报告的独立方程总数。
    pivots = [float(value) for value in PIVOT_PATTERN.findall(output_text)]  # 提取全部稀疏分解最小主元供正性审计。
    require(equation_counts and sorted(set(equation_counts)) == [EXPECTED_EQUATION_COUNT], "OUT 方程数缺失、漂移或不是 1,234,834")  # 阻断运行时拓扑变化和旧双层约束。
    require(pivots and all(math.isfinite(value) and value > 0.0 for value in pivots), "OUT 最小主元缺失、非有限或非正")  # 拒绝 small、zero、negative 或解析坏值。
    require(math.isclose(pivots[0], EXPECTED_LS1_PIVOT, rel_tol=0.0, abs_tol=1.0e-6), f"LS1 首个正主元与健康基准不一致：{pivots[0]}")  # 证明旧荷位起始分解仍与修复后全桥一致。
    completed_steps = [(int(step), int(substep)) for step, substep in COMPLETED_STEP_PATTERN.findall(output_text)]  # 提取 MAPDL 所有自然接受的载荷步/子步结果集标志。
    expected_completed = [(1, 1), (2, 1), (2, 2)]  # 当前事故只允许 LS1 与恰好两个最小迁移步被接受。
    require(completed_steps == expected_completed, f"OUT 接受步路径不是唯一 LS1/1、LS2/1、LS2/2：{completed_steps}")  # 阻断重复、漏步、第三步或后续阶段。
    require([(int(row["load_step"]), int(row["substep"])) for row in mntr_rows] == expected_completed, "MNTR 接受步与 OUT 完成标志不一致")  # 独立历史和主输出必须逐项同序。
    out_post_offset = max(old_audit["sampled_out_prefix_size_bytes"], old_audit["old_final_out_size_bytes"])  # 以旧超时终态或已哈希监控前缀中较晚位置切分有效恢复后 OUT 尾部。
    err_post_offset = max(0, old_audit["old_final_err_size_bytes"])  # 以旧超时终态 ERR 大小切分有效恢复后的新增错误输出。
    require(0 <= out_post_offset <= len(output_payload) and 0 <= err_post_offset <= len(error_payload), "旧 operator OUT/ERR 快照大小超出最终原件")  # 阻断文件截断、替换或错误基线。
    post_action_text = output_payload[out_post_offset:].decode("latin-1", errors="strict") + "\n" + error_payload[err_post_offset:].decode("latin-1", errors="strict")  # 只在旧空 ABT 控制器超时后的原生新增尾部寻找有效动作确认。
    acknowledgement_matches = match_abort_acknowledgements(post_action_text)  # 识别实际 `terminated ... from the ABT file` 或 2026 R1 等价签名。
    require(bool(acknowledgement_matches), "旧超时终态后的 OUT/ERR 缺少 MAPDL 原生 ABT/STOP 终止确认")  # 进程退出和动作回执不能单独证明 causal acknowledgement。
    require(re.search(r"REASON\s+FOR\s+TERMINATION[.\s]*UNCONVERGED\s+SOLUTION", post_action_text, re.IGNORECASE) is None, "动作后原生日志把最终原因记录为未收敛而非 ABT")  # 区分受控停止与自然 NCNV 失败。
    require(not any(step == 2 and substep >= 3 for step, substep in completed_steps), "有效 ABT 后意外接受第三个或更后 LS2 子步")  # 关闭动作到消费窗口内状态漂移。
    require(abs(float(mntr_rows[-1]["total_time_printed"]) - 1.0) <= 5.0e-5, "MNTR 最后打印总时间已明显离开 beta=1 邻域")  # 原生只打印五位有效数字会把 1.000001 显示为 1.0000，因此由子步与增量精确累计并仅用打印值排除 1.001 端点。
    gate_path = context["solver_dir"] / "c10_gate_status.txt"  # 定位主控默认 fail-closed 静力门禁文本。
    gate_disposition: str | None = None  # 初始化门禁可能因 ABT 终止输入而不存在的状态。
    if gate_path.is_file():  # 主输入若在 SOLVE 返回后继续执行会保留或更新门禁原件。
        gate_text = gate_path.read_text(encoding="latin-1", errors="strict").upper()  # 读取并规范化人工可见状态文本。
        require("STATUS=PASSED" not in gate_text, "APDL 门禁在 beta=0 未完成时意外记录 PASSED")  # 任何成功哨兵都与恰好两步互斥。
        gate_disposition = "REJECTED_OR_RUNNING_NOT_PASSED"  # 将可接受的未通过门禁归一为机器摘要。
    require(not (context["solver_dir"] / "c10_static_energy_mass_reaction.txt").exists(), "受控停止运行意外产生完整静力能量/质量/反力摘要")  # beta=0 后处理不得执行。
    require(not (context["solver_dir"] / f"{EXPECTED_JOBNAME}_eq.db").exists(), "受控停止运行意外保存 beta=0 平衡端点数据库")  # 区分自动保存中断 DB 与专门的 eq.db 成功工件。
    success_status_paths = [context["run_dir"] / "C10_static_final_status.json", context["run_dir"] / "C10_modal_final_status.json", context["run_dir"] / "modal" / "C10_modal_final_status.json"]  # 汇总与失败关闭互斥的静力和模态成功根状态候选。
    require(all(not path.exists() for path in success_status_paths), "运行已存在静力或模态成功终态")  # 成功与诊断充分受控停止必须互斥。
    partial_suffixes = {".rst", ".db", ".rdb", ".ldhi", ".esav", ".osav"}  # 冻结受控停止可能自动保存但禁止作为本项目基态的文件类别。
    partial_files = [path.relative_to(context["run_dir"]).as_posix() for path in context["solver_dir"].iterdir() if path.is_file() and (path.suffix.casefold() in partial_suffixes or re.fullmatch(r"\.[rm]\d+", path.suffix.casefold()) is not None)]  # 枚举部分结果、数据库和重启动碎片供用途警告。
    return {"files": {"out": {"relative_path": output_path.relative_to(context["run_dir"]).as_posix(), "size_bytes": len(output_payload), "sha256": sha256_bytes(output_payload)}, "err": {"relative_path": error_path.relative_to(context["run_dir"]).as_posix(), "size_bytes": len(error_payload), "sha256": sha256_bytes(error_payload)}, "mntr": {"relative_path": mntr_path.relative_to(context["run_dir"]).as_posix(), "size_bytes": len(mntr_payload), "sha256": sha256_bytes(mntr_payload)}}, "equation_count": {"expected": EXPECTED_EQUATION_COUNT, "observed": equation_counts, "unique": [EXPECTED_EQUATION_COUNT], "stable": True}, "pivots": {"observed": pivots, "first_ls1": pivots[0], "minimum_positive": min(pivots), "all_finite_positive": True, "hard_pivot_event_observed": False}, "completed_steps": completed_steps, "forbidden_native_events": forbidden_matches, "native_abort_acknowledgements": acknowledgement_matches, "native_abort_acknowledgement_proven_after_old_timeout_prefix": True, "final_termination_reason": "VALID_NONLINEAR_ABT_CONTROLLED_STOP", "gate_path": gate_path.relative_to(context["run_dir"]).as_posix() if gate_path.is_file() else None, "gate_disposition": gate_disposition, "beta_zero_reached": False, "static_endpoint_reached": False, "partial_result_or_restart_files": sorted(partial_files), "partial_result_or_restart_files_allowed_as_project_restart_base": False, "partial_result_or_restart_files_allowed_as_modal_basis": False}  # 返回原生因果、数值健康、恰好两步和严格用途禁令摘要。


def validate_run(run_dir_value: Path, runs_root: Path = RUNS_ROOT, stability_wait_seconds: float = 0.0) -> dict[str, Any]:  # 接收唯一事故运行并返回所有准备、监控、事故、恢复和原生证据闭合的只读上下文。
    context = validate_preparation_and_launch(run_dir_value, runs_root)  # 首先固定运行边界、准备谱系、启动命令和进程已退出事实。
    final_targets = [context["run_dir"] / "qa" / SCRIPT_PATH.name, context["run_dir"] / "qa" / "diagnostic_sufficiency_stop_audit.json", context["run_dir"] / "diagnostic_sufficiency_stop_report.md", context["run_dir"] / "artifact_hashes_diagnostic_sufficiency_final.sha256", context["run_dir"] / "C10_diagnostic_sufficiency_final_status.json"]  # 汇总本终结器唯一允许新增的五个目标。
    require(all(not path.exists() for path in final_targets), "至少一个诊断充分性封存目标已存在，拒绝重复验证后发布")  # 保持一次运行只有一次首次发布语义。
    require_files_stable([context["output_path"], context["error_path"], context["mntr_path"]], stability_wait_seconds)  # 正式发布前可配置短稳定窗口，离线调用可用零秒。
    mntr_payload = context["mntr_path"].read_bytes()  # 冻结完整 MNTR 字节供三条证据链共同使用。
    mntr_rows = parse_mntr_bytes(mntr_payload)  # 解析 LS1 与恰好两个 LS2 接受行。
    sufficiency = evaluate_sufficiency(mntr_rows)  # 独立重算最小步、后一步迭代和严格七天投影。
    monitor_audit = validate_monitor_chain(context)  # 闭合持续监控 JSONL、终态、无硬事件和无强制动作。
    old_audit = validate_old_operator_chain(context, monitor_audit, mntr_rows)  # 闭合旧工具创建并消费零字节 ABT 后超时的事故事实。
    recovery_audit = validate_recovery_chain(context, monitor_audit, old_audit, mntr_rows)  # 闭合有效十字节 ABT 双回执和自然退出恢复链。
    native_audit = validate_native_files(context, old_audit, recovery_audit, mntr_rows)  # 用 OUT/ERR/MNTR 补上原生因果和数值健康证据。
    context.update({"final_targets": final_targets, "mntr_rows": mntr_rows, "sufficiency": sufficiency, "monitor_audit": monitor_audit, "old_operator_audit": old_audit, "recovery_audit": recovery_audit, "native_audit": native_audit})  # 合并发布审计与中文报告需要的全部闭合对象。
    return context  # 返回未写任何最终工件的严格只读验证结果。


def publish_final(context: dict[str, Any]) -> tuple[Path, dict[str, Any]]:  # 接收完整只读验证上下文并排他发布源码快照、机器审计、中文报告、追加账本和最终根状态。
    run_dir = context["run_dir"]  # 读取唯一事故运行根供固定发布目标定位。
    snapshot_path, audit_path, report_path, ledger_path, final_status_path = context["final_targets"]  # 按源码、审计、报告、账本、根状态顺序展开五个不可覆盖目标。
    script_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 读取实际执行终结器源码供运行内快照和摘要闭合。
    script_sha256 = sha256_bytes(script_text.encode("utf-8"))  # 按实际 UTF-8 写出字节计算终结器身份。
    sufficiency = context["sufficiency"]  # 读取由最终 MNTR 独立重算的恰好两步与七天投影摘要。
    monitor = context["monitor_audit"]  # 读取完整 JSONL 重算后的监控摘要。
    old_operator = context["old_operator_audit"]  # 读取旧空 ABT 事故链摘要。
    recovery = context["recovery_audit"]  # 读取有效十字节 ABT 恢复链摘要。
    native = context["native_audit"]  # 读取 OUT/ERR/MNTR 原生因果和数值健康摘要。
    audit = {"schema_version": 1, "status": FINAL_STATUS, "run_name": run_dir.name, "jobname": EXPECTED_JOBNAME, "diagnostic_subtype": EXPECTED_SUBTYPE, "single_variable_change": EXPECTED_SINGLE_CHANGE, "finalized_at_utc": utc_now(), "finalized_by_script": f"qa/{SCRIPT_PATH.name}", "finalizer_script_sha256": script_sha256, "preparation_chain": {"manifest_path": "manifest.json", "manifest_sha256": context["manifest_sha256"], "prepared_status_preserved": context["root_status"]["status"], "prepared_ledger_path": "artifact_hashes.sha256", "prepared_ledger_sha256": context["prepared_ledger_sha256"], "prepared_ledger_entry_count": len(context["prepared_entries"]), "all_prepared_entries_rehashed": True, "manifest_and_prepared_status_overwritten": False}, "launch_chain": {"runtime_launch_claim_sha256": sha256_file(context["launch_claim_path"]), "runtime_launch_sha256": sha256_file(context["launch_path"]), "runtime_process_identity_sha256": sha256_file(context["identity_path"]), "main_pid": int(context["launch"]["main_pid"]), "main_process_exact_identity_absent": True, "active_job_process_count": 0, "mapdl_executable_sha256": sha256_file(context["mapdl_path"]), "main_input_sha256": sha256_file(context["input_path"]), "smp_np": 1}, "runtime_monitor": {"claim_path": "qa/runtime_hard_stop_monitor_claim.json", "claim_sha256": monitor["claim_sha256"], "samples_path": "qa/runtime_hard_stop_monitor_samples.jsonl", "samples_sha256": monitor["samples_sha256"], "sample_count": monitor["sample_count"], "final_path": "qa/runtime_hard_stop_monitor_final.json", "final_sha256": monitor["final_sha256"], "status": monitor["final"]["status"], "hard_event_count": 0, "controller_abort_requested": False, "terminate_sent_pids": [], "kill_sent_pids": [], "minimum_physical_memory_available_bytes": monitor["minimum_physical_memory_available_bytes"], "minimum_disk_free_bytes": monitor["minimum_disk_free_bytes"], "maximum_related_rss_bytes": monitor["maximum_related_rss_bytes"], "files_stable_at_monitor_commit": True}, "old_empty_abort_incident": {"claim_path": "qa/runtime_operator_stop_claim.json", "claim_sha256": old_operator["claim_sha256"], "claim_status": old_operator["claim"]["status"], "final_path": "qa/runtime_operator_stop_final.json", "final_sha256": old_operator["final_sha256"], "final_status": old_operator["final"]["status"], "executed_old_tool_sha256": OLD_STOP_TOOL_SHA256, "current_old_tool_source_sha256": old_operator["current_old_tool_source_sha256"], "current_old_tool_source_matches_executed_version": old_operator["current_old_tool_source_matches_executed_version"], "executed_version_proven_by_claim_and_recovery_pre_action_hash_gate": True, "native_abort_created_exclusively": True, "native_abort_initial_size_bytes": 0, "native_abort_initial_sha256": EMPTY_SHA256, "native_abort_consumed_without_exit": True, "wait_seconds": float(old_operator["final"]["wait_seconds"]), "exact_process_tree_exit_confirmed": False, "operator_force_actions": False}, "valid_abort_recovery": {"claim_sha256": recovery["claim_sha256"], "plan_sha256": recovery["plan_sha256"], "executed_sha256": recovery["executed_sha256"], "final_sha256": recovery["final_sha256"], "claim_status": recovery["claim"]["status"], "plan_status": recovery["plan"]["status"], "executed_status": recovery["executed"]["status"], "final_status": recovery["final"]["status"], "recovery_tool_sha256": RECOVERY_TOOL_SHA256, "native_abort_created_at_utc": recovery["created_at_utc"], "payload": recovery["payload_contract"], "exact_process_tree_exit_confirmed": True, "monitor_event_classification": recovery["monitor_event_classification"], "operator_force_actions": False}, "diagnostic_sufficiency": sufficiency, "native_solver_evidence": native, "engineering_disposition": {"diagnostic_sufficiency_proven": True, "static_numeric_completion": False, "beta_zero_reached": False, "static_endpoint_reached": False, "valid_static_result_obtained": False, "partial_rst_or_database_is_valid_static_endpoint": False, "partial_rst_or_database_allowed_as_project_restart_base": False, "partial_rst_or_database_allowed_as_modal_basis": False, "modal_execution_attempted": False, "modal_execution_allowed": False, "modal_status": "BLOCKED_NOT_RUN", "production_claim_allowed": False, "valid_for_production": False, "design_or_code_check_allowed": False, "failure_closed_reason": "VALID_NONLINEAR_ABT_CONTROLLED_STOP_AFTER_EXACTLY_TWO_ACCEPTED_MINIMUM_LS2_STEPS_WITH_PROJECTED_REMAINING_RUNTIME_STRICTLY_OVER_SEVEN_DAYS_BEFORE_BETA_ZERO"}, "appended_ledger": "artifact_hashes_diagnostic_sufficiency_final.sha256"}  # 汇总准备谱系、监控、空 ABT 事故、源码替代披露、有效恢复、原生日志和工程用途禁令。
    audit_text = render_json(audit)  # 在任何发布前完成机器审计合法 JSON 渲染和 NaN 拒绝。
    final_status = {"schema_version": 1, "run_name": run_dir.name, "jobname": EXPECTED_JOBNAME, "status": FINAL_STATUS, "static_numeric_status": "STOPPED_BEFORE_BETA_ZERO_NOT_A_COMPLETED_STATIC_SOLUTION", "stop_classification": "VALID_NONLINEAR_ABT_CONTROLLED_STOP_AFTER_DIAGNOSTIC_SUFFICIENCY", "diagnostic_sufficiency_proven": True, "ls1_beta_one_old_load_position_equilibrium_accepted": True, "ls2_accepted_substep_count": EXPECTED_ACCEPTED_LS2_STEPS, "ls2_each_increment": MINIMUM_INCREMENT, "later_ls2_step_iterations": sufficiency["later_step_iterations"], "projected_remaining_seconds": sufficiency["projected_remaining_seconds"], "projection_strictly_exceeds_seven_days": True, "equation_count": EXPECTED_EQUATION_COUNT, "minimum_positive_pivot": native["pivots"]["minimum_positive"], "monitor_hard_event_count": 0, "controller_abort_requested": False, "operator_process_force_action_used": False, "valid_native_abort_payload_sha256": ABT_PAYLOAD_SHA256, "native_abort_acknowledgement_proven": True, "beta_zero_reached": False, "static_endpoint_reached": False, "valid_static_result_obtained": False, "partial_rst_or_database_allowed_as_project_restart_base": False, "partial_rst_or_database_allowed_as_modal_basis": False, "modal_status": "BLOCKED_NOT_RUN", "modal_execution_allowed": False, "production_claim_allowed": False, "valid_for_production": False, "design_or_code_check_allowed": False, "prepared_manifest_status_preserved": context["root_status"]["status"], "machine_audit": "qa/diagnostic_sufficiency_stop_audit.json", "human_report": "diagnostic_sufficiency_stop_report.md", "final_appended_ledger": "artifact_hashes_diagnostic_sufficiency_final.sha256"}  # 提供下游无需解释准备态 manifest 即可识别未完成静力和全用途禁令的根状态。
    final_status_text = render_json(final_status)  # 在任何发布前完成最终根状态 JSON 渲染。
    report_text = f"# C10 自适应迁移诊断充分性受控停止封存\n\n最终状态：`{FINAL_STATUS}`。这不是 beta=0 静力完成，也不是模态结果；它只证明继续计算的诊断价值已经不足，并由有效 MAPDL `nonlinear` ABT 干净停止。\n\n- 准备与执行身份：准备账本 {len(context['prepared_entries'])} 项全部复算通过；manifest、主控输入、MAPDL 2026 R1 二进制、启动 claim/launch/identity 和 SMP1 命令行一致，原 job 进程树已全部退出。\n- 旧事故：旧工具排他创建的是零字节 ABT，MAPDL 消费后没有退出；旧控制器等待 {float(old_operator['final']['wait_seconds']):.1f} 秒超时并明确未调用 terminate/kill。旧工件全部保留，未覆盖。\n- 有效恢复：恢复工具排他创建十字节 `nonlinear\\n`，SHA-256 为 `{ABT_PAYLOAD_SHA256}`；完整写入、flush/fsync、同句柄回读均通过，ABT 被 MAPDL 消费，OUT/ERR 在旧超时前缀之后出现原生终止确认，进程树和 lock 自然消失。\n- 持续监控：最终 JSONL 共 {monitor['sample_count']} 个连续样本；硬事件 0，监控器自身中止请求 0，terminate/kill PID 均为空，OUT/ERR/MNTR 与 monitor/recovery final 快照一致。\n- 数值健康：全部方程报告均为 {EXPECTED_EQUATION_COUNT:,}；{len(native['pivots']['observed'])} 个最小主元均有限且为正，最小值 {native['pivots']['minimum_positive']:.9g}；未见 FATAL、small/zero/negative pivot 或 CNVTOL 被忽略/重置。\n- 充分性：MNTR 只有 LS1 和恰好两个 LS2 接受步；两个 LS2 增量均为 `5E-7`，后一步 Newton 迭代 {sufficiency['later_step_iterations']} 次，实测每最小步 {sufficiency['measured_seconds_per_minimum_step']:.3f} 秒，剩余 {sufficiency['remaining_minimum_step_count']} 个最小步投影 {sufficiency['projected_remaining_seconds']:.3f} 秒（{sufficiency['projected_remaining_seconds'] / 86400.0:.3f} 天），严格超过七天。\n- 工程结论：beta=0 未达到，静力端点不存在，`valid_static_result_obtained=false`。任何部分 RST、DB、RDB、LDHI 或重启动碎片都不得作为本项目重启动基态、预应力模态基态、设计验算或生产结果。模态状态为 `BLOCKED_NOT_RUN`，`modal_execution_allowed=false`，`production_claim_allowed=false`。\n\n机器审计见 `qa/diagnostic_sufficiency_stop_audit.json`，非自引用全运行追加账本见 `artifact_hashes_diagnostic_sufficiency_final.sha256`。\n"  # 生成人工可直接判断事故、恢复、充分性、数值健康和禁用边界的中文报告。
    virtual_texts = {snapshot_path: script_text, audit_path: audit_text, report_path: report_text, final_status_path: final_status_text}  # 汇总除最终账本外的四个待发布文本及其精确字节。
    ledger_text, ledger_entry_count = build_appended_ledger(run_dir, context["prepared_entries"], virtual_texts, ledger_path)  # 对全部既有原件和待发布文本生成非自引用追加账本。
    publish_payloads = {snapshot_path: script_text, audit_path: audit_text, report_path: report_text, ledger_path: ledger_text, final_status_path: final_status_text}  # 按根状态最后的顺序构造不可覆盖批量发布内容。
    write_new_batch(publish_payloads)  # 统一预检、fsync 暂存、硬链接发布并在异常时安全回滚本批次全部对象。
    require(sha256_file(snapshot_path) == script_sha256 and sha256_file(audit_path) == sha256_bytes(audit_text.encode("utf-8")) and sha256_file(final_status_path) == sha256_bytes(final_status_text.encode("utf-8")), "发布后源码快照、机器审计或根状态摘要与内存渲染不一致")  # 立即复核三项关键发布字节。
    summary = {"run_dir": str(run_dir), "status": FINAL_STATUS, "final_status_path": str(final_status_path), "final_ledger_path": str(ledger_path), "final_ledger_entry_count": ledger_entry_count, "final_ledger_sha256": sha256_file(ledger_path), "accepted_ls2_substep_count": EXPECTED_ACCEPTED_LS2_STEPS, "projection_strictly_exceeds_seven_days": True, "native_abort_acknowledgement_proven": True, "beta_zero_reached": False, "static_endpoint_reached": False, "modal_execution_allowed": False, "production_claim_allowed": False}  # 构造调用者可直接解析的发布结果与用途禁令摘要。
    return final_status_path, summary  # 返回已排他发布并完成关键摘要复核的根状态路径和机器摘要。


def finalize(run_dir_value: Path, validate_only: bool = False, runs_root: Path = RUNS_ROOT, stability_wait_seconds: float = 2.0) -> dict[str, Any]:  # 接收运行、只验证开关、可测试根和稳定窗口并返回不写或已发布摘要。
    context = validate_run(run_dir_value, runs_root, stability_wait_seconds)  # 先以同一严格门完成全部只读证据验证。
    if validate_only:  # 调用者只要求审计可发布性时不得新增任何运行工件。
        return {"run_dir": str(context["run_dir"]), "status": "VALIDATION_PASSED_NO_FINAL_ARTIFACTS_WRITTEN", "would_publish_status": FINAL_STATUS, "accepted_ls2_substep_count": context["sufficiency"]["accepted_ls2_substep_count"], "later_step_iterations": context["sufficiency"]["later_step_iterations"], "projected_remaining_seconds": context["sufficiency"]["projected_remaining_seconds"], "native_abort_acknowledgement_count": len(context["native_audit"]["native_abort_acknowledgements"]), "beta_zero_reached": False, "static_endpoint_reached": False, "modal_execution_allowed": False, "production_claim_allowed": False, "final_artifacts_written": False}  # 返回明确无写入的验证摘要。
    _, summary = publish_final(context)  # 全部门通过后才进入五件工件不可覆盖发布。
    return summary  # 返回已发布根状态和追加账本摘要。


def expect_runtime_error(operation: Any, label: str) -> str:  # 接收无参测试操作和标签并要求其严格抛出 RuntimeError。
    try:  # 执行预期失败的纯函数或临时目录操作。
        operation()  # 调用测试闭包且不向其传递项目运行路径。
    except RuntimeError as error:  # 只有本工具统一失败关闭异常类型才算通过。
        return str(error)  # 返回原因文本供自测摘要或进一步断言使用。
    raise RuntimeError(f"离线自测未按预期拒绝：{label}")  # 未抛异常表示对应严格门已经退化。


def ast_call_name(call: ast.Call) -> str | None:  # 接收 AST 调用节点并返回简单函数名或属性名供禁止动作审计。
    if isinstance(call.func, ast.Name):  # 直接函数调用使用标识符节点。
        return call.func.id  # 返回直接调用名称。
    if isinstance(call.func, ast.Attribute):  # 对象方法调用使用属性节点。
        return call.func.attr  # 返回末级方法名以捕获 process.kill 等形式。
    return None  # 其他动态调用形式没有稳定简单名称且不属于当前禁用集合匹配方式。


def run_offline_self_tests() -> dict[str, Any]:  # 无运行目录输入并返回不访问当前运行主流程的数学、字节、分类、发布和注释自测摘要。
    require(len(ABT_PAYLOAD) == ABT_PAYLOAD_LENGTH, "离线自测失败：有效 ABT 长度不是十字节")  # 验证九个 ASCII 字母加单一 LF 的长度合同。
    require(ABT_PAYLOAD.hex() == ABT_PAYLOAD_HEX, "离线自测失败：有效 ABT 十六进制漂移")  # 验证精确字节序列而不依赖文本换行转换。
    require(sha256_bytes(ABT_PAYLOAD) == ABT_PAYLOAD_SHA256, "离线自测失败：有效 ABT SHA-256 漂移")  # 验证固定载荷摘要文本本身正确。
    require(OLD_STOP_TOOL_PATH.is_file() and re.fullmatch(r"[0-9a-f]{64}", OLD_STOP_TOOL_SHA256) is not None, "离线自测失败：旧 operator 工具路径或执行时固定摘要无效")  # 事故后源码可被新版替代，执行时字节由运行 claim 和恢复前固定哈希门证明。
    require(RECOVERY_TOOL_PATH.is_file() and sha256_file(RECOVERY_TOOL_PATH) == RECOVERY_TOOL_SHA256, "离线自测失败：有效恢复工具摘要漂移")  # 不访问运行目录地固定双回执恢复源码身份。
    synthetic_mntr = b"1 1 1 4 4 1.0 1.0 300.0\n2 1 4 29 48 5.0E-7 1.0000005 3700.0\n2 2 1 45 93 5.0E-7 1.0000010 6600.0\n"  # 构造 LS1 与恰好两个连续 5E-7 接受步，后一步四十五次迭代且投影超过七天。
    synthetic_rows = parse_mntr_bytes(synthetic_mntr)  # 验证 MNTR 八列词法能恢复全部三行。
    synthetic_result = evaluate_sufficiency(synthetic_rows)  # 独立计算两步耗时差、剩余步数和投影秒数。
    require(synthetic_result["accepted_ls2_substep_count"] == 2 and synthetic_result["later_step_iterations"] == 45 and float(synthetic_result["projected_remaining_seconds"]) > SUFFICIENCY_HORIZON_SECONDS, "离线自测失败：合成充分性样本未通过")  # 固定本工具核心成功路径。
    bad_increment_rows = [dict(row) for row in synthetic_rows]  # 深度到单层复制合成行供坏增量拒绝测试。
    bad_increment_rows[2]["increment"] = 1.0e-6  # 把后一步改为非冻结最小增量，应严格失败。
    bad_increment_reason = expect_runtime_error(lambda: evaluate_sufficiency(bad_increment_rows), "非 5E-7 LS2 增量")  # 验证步长门不会宽松接受其他速度基准。
    low_iteration_rows = [dict(row) for row in synthetic_rows]  # 复制合成行供后一步迭代数下界测试。
    low_iteration_rows[2]["iterations"] = 19  # 设置为阈值以下十九次，排除偶发快步。
    low_iteration_reason = expect_runtime_error(lambda: evaluate_sufficiency(low_iteration_rows), "后一步少于二十次迭代")  # 验证二十次门为包含下界。
    short_projection_rows = [dict(row) for row in synthetic_rows]  # 复制合成行供七天严格大于测试。
    short_projection_rows[2]["elapsed_seconds"] = float(short_projection_rows[1]["elapsed_seconds"]) + 1.0  # 把实测最小步耗时缩短到一秒，使总投影远低于七天。
    short_projection_reason = expect_runtime_error(lambda: evaluate_sufficiency(short_projection_rows), "剩余投影不足七天")  # 验证停止充分性不能由短样本触发。
    third_step_rows = [*synthetic_rows, {"load_step": 2, "substep": 3, "attempt": 1, "iterations": 25, "total_iterations": 118, "increment": MINIMUM_INCREMENT, "total_time_printed": 1.0000015, "elapsed_seconds": 9500.0}]  # 构造动作窗口又接受第三步的状态漂移。
    third_step_reason = expect_runtime_error(lambda: evaluate_sufficiency(third_step_rows), "第三个 LS2 接受步")  # 验证当前事故只接受恰好两步。
    action_time = parse_utc("2026-08-02T03:00:00+00:00", "自测动作时刻")  # 构造带时区有效 ABT 时刻供事件分类测试。
    good_event = {"kind": "OPERATOR_ABORT", "detected_at_utc": "2026-08-02T03:00:01+00:00"}  # 构造动作后一秒且类别显式批准的合成事件。
    good_classification = classify_monitor_events([good_event], action_time, frozenset({"OPERATOR_ABORT"}))  # 验证双条件满足时进入预期集合。
    require(good_classification["expected_operator_abort_events"] == [good_event] and good_classification["unexpected_hard_events"] == [], "离线自测失败：动作后批准事件分类错误")  # 固定正向事件分类合同。
    early_event = {"kind": "OPERATOR_ABORT", "detected_at_utc": "2026-08-02T02:59:59+00:00"}  # 构造同类别但早于动作的事件。
    fatal_event = {"kind": "MAPDL_FATAL", "detected_at_utc": "2026-08-02T03:00:02+00:00"}  # 构造动作后但类别未批准的独立硬错误。
    bad_classification = classify_monitor_events([early_event, fatal_event], action_time, frozenset({"OPERATOR_ABORT"}))  # 验证错时和错类均进入未预期集合。
    require(bad_classification["expected_operator_abort_events"] == [] and bad_classification["unexpected_hard_events"] == [early_event, fatal_event], "离线自测失败：动作前或 FATAL 事件未失败关闭")  # 固定事件不能被 ABT 背景掩盖。
    acknowledgement_matches = match_abort_acknowledgements("The nonlinear analysis was terminated cleanly from the ABT file at the next equilibrium iteration.")  # 构造当前实际原生 terminated-from-ABT 等价签名。
    require(any(item["signature"] == "TERMINATED_FROM_ABT_FILE" for item in acknowledgement_matches), "离线自测失败：原生 ABT 确认签名未命中")  # 防止正则漂移导致真实运行无法封存。
    with tempfile.TemporaryDirectory(prefix="c10_sufficiency_finalize_selftest_") as temporary_name:  # 仅在系统临时根建立可自动回收的排他发布沙箱。
        temporary_root = Path(temporary_name).resolve()  # 规范化临时根供账本相对路径计算。
        seed_path = temporary_root / "seed.txt"  # 定位模拟准备账本已保护的既有工件。
        seed_path.write_text("准备字节\n", encoding="utf-8", newline="\n")  # 在临时目录写入最小既有工件且不接触项目运行。
        prepared_entries = {"seed.txt": sha256_file(seed_path)}  # 构造一项模拟准备谱系供保留门测试。
        virtual_path = temporary_root / "virtual.json"  # 定位模拟待发布机器工件。
        ledger_path = temporary_root / "final.sha256"  # 定位模拟非自引用追加账本。
        virtual_text = render_json({"status": "SELF_TEST"})  # 渲染稳定模拟 JSON 文本供虚拟摘要测试。
        ledger_text, ledger_count = build_appended_ledger(temporary_root, prepared_entries, {virtual_path: virtual_text}, ledger_path)  # 验证准备条目保留和虚拟工件预哈希。
        require(ledger_count == 2 and prepared_entries["seed.txt"] in ledger_text, "离线自测失败：追加账本未保留准备条目")  # 固定非自引用账本应含 seed 与 virtual 两项。
        write_new_batch({virtual_path: virtual_text, ledger_path: ledger_text})  # 验证排他暂存、fsync 和硬链接发布成功路径。
        require(virtual_path.read_text(encoding="utf-8", errors="strict") == virtual_text and ledger_path.read_text(encoding="utf-8", errors="strict") == ledger_text, "离线自测失败：排他发布后字节不一致")  # 逐字节复核模拟发布内容。
        repeat_reason = expect_runtime_error(lambda: write_new_batch({virtual_path: virtual_text}), "覆盖既有最终工件")  # 验证第二次调用在任何写入前失败关闭。
        require(bool(repeat_reason), "离线自测失败：重复发布拒绝原因为空")  # 保留明确拒绝消息供操作员定位。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 严格读取本工具完整源码供 AST 和逐行注释自审计。
    syntax_tree = ast.parse(source_text, filename=str(SCRIPT_PATH))  # 解析完整源码以确认 Python 语法合法。
    forbidden_calls = sorted({name for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) for name in [ast_call_name(node)] if name in FORBIDDEN_PROCESS_CALL_NAMES})  # 收集全部被禁止的主动进程动作调用名。
    require(not forbidden_calls, f"离线自测失败：发现禁止的主动进程动作调用 {forbidden_calls}")  # 源码出现 kill、terminate 或 send_signal 即失败。
    uncommented_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if line.strip() and "#" not in line]  # 收集所有非空且缺少相邻注释标记的物理源码行。
    require(not uncommented_lines, f"离线自测失败：存在缺少逐行中文注释的源码行 {uncommented_lines[:20]}")  # 强制每一行有效代码都带注释。
    non_chinese_comment_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if "#" in line and re.search(r"[\u4e00-\u9fff]", line.split("#", 1)[1]) is None]  # 收集首个注释段不含中文字符的物理行。
    require(not non_chinese_comment_lines, f"离线自测失败：存在不含中文的注释行 {non_chinese_comment_lines[:20]}")  # 落实默认中文逐行注释合同。
    return {"status": "OFFLINE_SELF_TESTS_PASSED", "tool_sha256": sha256_file(SCRIPT_PATH), "native_abort_payload_length_bytes": ABT_PAYLOAD_LENGTH, "native_abort_payload_sha256": ABT_PAYLOAD_SHA256, "synthetic_projected_remaining_seconds": synthetic_result["projected_remaining_seconds"], "synthetic_later_step_iterations": synthetic_result["later_step_iterations"], "exactly_two_steps_enforced": bool(third_step_reason), "bad_increment_rejected": bool(bad_increment_reason), "low_iteration_rejected": bool(low_iteration_reason), "short_projection_rejected": bool(short_projection_reason), "event_classification_tests_passed": True, "native_abort_ack_signature_tests_passed": True, "exclusive_publish_and_repeat_rejection_tests_passed": True, "forbidden_process_calls": forbidden_calls, "uncommented_line_count": len(uncommented_lines), "non_chinese_comment_line_count": len(non_chinese_comment_lines), "current_run_main_invoked": False, "current_run_writes_performed": False}  # 返回可机器解析且明确未访问当前运行主流程的完整离线自测摘要。


def parse_arguments() -> argparse.Namespace:  # 无业务输入并返回运行目录、只验证和离线自测参数。
    parser = argparse.ArgumentParser(description="严格封存当前 C10 自适应迁移由有效 nonlinear ABT 受控停止、诊断充分但未到 beta=0 的失败关闭状态；本工具绝不操作求解进程。")  # 创建事故专用命令行解析器。
    parser.add_argument("--run-dir", type=Path, help=f"唯一批准运行目录，名称必须为 {EXPECTED_RUN_NAME}。")  # 接收显式运行目录且禁止 latest、通配符和跨项目路径。
    parser.add_argument("--validate-only", action="store_true", help="执行与发布相同的全链只读验证但不新增最终工件。")  # 提供操作员先验证后正式封存入口。
    parser.add_argument("--self-test", action="store_true", help="仅执行数学、字节、分类、临时发布、AST 和逐行中文注释离线自测。")  # 提供绝不进入当前运行主流程的验证入口。
    return parser.parse_args()  # 返回已完成基本类型转换的命名空间。


def main() -> None:  # 无返回值；执行完全离线自测、只读全链验证或不可覆盖最终封存。
    arguments = parse_arguments()  # 读取显式运行目录和两个模式开关。
    if arguments.self_test:  # 离线模式优先且不得进入运行验证或发布路径。
        require(arguments.run_dir is None, "--self-test 不接受 --run-dir，防止误触当前运行主流程")  # 用参数互斥明确隔离项目运行。
        print(json.dumps(run_offline_self_tests(), ensure_ascii=False, allow_nan=False))  # 输出可解析自测摘要并结束。
        return  # 明确阻断后续运行主流程。
    require(arguments.run_dir is not None, "验证或封存模式必须显式提供 --run-dir")  # 禁止 latest 或隐式选择运行。
    summary = finalize(arguments.run_dir, validate_only=bool(arguments.validate_only), stability_wait_seconds=2.0)  # 执行同一严格验证并按开关决定是否排他发布。
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))  # 输出最终状态、账本或无写入验证摘要。


if __name__ == "__main__":  # 仅直接命令行执行时进入参数解析，导入测试不会触发运行主流程。
    main()  # 调用唯一入口并让任何失败关闭异常产生非零退出码。
