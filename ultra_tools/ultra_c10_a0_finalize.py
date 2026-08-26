from __future__ import annotations  # 启用延迟类型注解，避免复杂容器注解在运行时提前求值。

import argparse  # 解析调用者必须显式给出的唯一 run-dir 参数。
import ast  # 解析本终结器抽象语法树，离线证明不存在求解器启停调用。
import csv  # 严格解析 LS1 六列能量历程 CSV，避免手工分隔字段歧义。
import hashlib  # 对准备、启动、监控、求解和最终工件逐字节复算 SHA-256。
import json  # 严格读取现有机器工件并稳定渲染新的最终 JSON。
import math  # 检查主元、时间、能量和 NRRE 数值的有限性与容差。
import os  # 使用同卷硬链接实现不可覆盖的整批最终工件发布。
import re  # 识别 MAPDL 消息块、方程数、主元、迭代、切步、阶段与 NRRE 头部。
import tempfile  # 仅为离线自测创建由运行库自动回收的系统临时目录。
import time  # 仅用两秒只读稳定窗口，不承担任何进程等待或处置。
from datetime import datetime, timezone  # 生成不受本地时区影响的 ISO-8601 UTC 终结时刻。
from pathlib import Path  # 安全处理含中文的项目、运行、求解与 QA 路径。
from typing import Any  # 标注异构 JSON 对象、日志证据和发布数据结构。

import psutil  # 仅只读检查冻结 PID 身份和本 job 进程是否已消失，不调用主动处置接口。


SCRIPT_PATH = Path(__file__).resolve()  # 冻结实际执行终结器路径，用于项目定位、源码快照与摘要。
PROJECT_ROOT = SCRIPT_PATH.parents[1]  # 以 ultra_tools 的父目录作为本分析包唯一项目根。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 限定终结目标必须是统一运行证据根的直接子目录。
HOST_LEASE_PATH = RUNS_ROOT / ".c10_a0_exclusive_host_lease.json"  # 冻结启动器取得、监控稳定终态释放的唯一跨运行主机租约路径。
EXPECTED_RUN_PREFIX = "C10_A0_DIRECT_SPATIAL_RAMP_"  # 只允许本工具处理 A0 直接空间重力斜坡运行族。
EXPECTED_SUBTYPE = "A0_CURRENT_TYPE72_S10_DIRECT_SPATIAL_GRAVITY_RAMP_STATIC_ONLY_NRRE"  # 冻结 A0 唯一允许的诊断子类型。
EXPECTED_LOAD_PATH = "S10_DIRECT_SPATIAL_MASS21_GRAVITY_RAMP_NO_MIGRATION"  # 冻结 S10 直接空间质量重力斜坡且无位置迁移的路径。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结单层 TYPE72、无辅助节点与无 TYPE73 全桥独立方程数。
EXPECTED_NODE_COUNT = 109_086  # 冻结 A0 清单中的总节点数，仅用于输入身份与 NRRE 上界检查。
EXPECTED_ELEMENT_COUNT = 178_072  # 冻结 A0 清单中的总单元数，用于阻断运行族错配。
EXPECTED_TYPE72_COUNT = 5_078  # 冻结当前单层 TYPE72 运动学连接数量。
EXPECTED_NRRE_MAXFILE = 50  # 冻结 NLDIAG/NRRE 最多保留五十个平衡迭代文件的合同。
EXPECTED_MASS_TONNE = 4_108.466_907_58  # 冻结父 S10 质量台账的全桥总质量，单位 tonne。
GRAVITY_MM_PER_S2 = 9_806.0  # 冻结主控 ACEL 使用的重力加速度绝对值，单位 mm/s²。
MASS_ABSOLUTE_TOLERANCE_TONNE = 1.0e-6  # 允许质量摘要相对冻结台账的绝对误差上限，单位 tonne。
REACTION_RELATIVE_TOLERANCE = 1.0e-4  # 允许 UZ 支承竖向重力反力闭合的相对误差上限。
LS1_ENERGY_RATIO_LIMIT = 1.0e-2  # 允许 LS1 端点与全历程稳定化能绝对比值上限。
LS2_ENERGY_RATIO_LIMIT = 1.0e-8  # 允许零物理增量 LS2 稳定化能绝对比值上限。
LS1_MIN_ACCEPTED_SUBSTEPS = 20  # 冻结 NSUBST,20,200,20 合同中 LS1 最少已接受子步数。
LS1_MAX_ACCEPTED_SUBSTEPS = 200  # 冻结 NSUBST,20,200,20 合同中 LS1 最多已接受子步数。
TIME_ABSOLUTE_TOLERANCE = 5.0e-6  # 考虑 MNTR 打印精度后比较 1.0 与 1.001 终点的伪时间绝对容差。
STABILITY_WAIT_SECONDS = 2.0  # 在监控 final 后再比较两秒文件大小与修改时刻，排除延迟刷新。
SELF_TEST_SENTINEL = "__SELF_TEST__"  # 使用唯一 run-dir 参数的保留值进入完全离线自测。
NATURAL_MONITOR_STATUS = "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP"  # 冻结无硬事件的监控稳定退出状态。
HARD_MONITOR_STATUS = "HARD_STOP_NATIVE_ABORT_ONLY_PROCESS_TREE_EXITED_STABLE"  # 冻结硬事件后仅原生 ABT 且稳定退出状态。
BLOCKED_MONITOR_STATUS = "PROCESS_TREE_EXITED_A0_MONITOR_BLOCKED"  # 冻结文件或锁未稳定时必须拒绝发布的监控状态。
PASS_STATUS = "PASS_DIAGNOSTIC_ONLY_NEEDS_A0B"  # 冻结 A0 全门通过后唯一允许的诊断结论，必须继续 A0B。
CNVTOL_FAILURE_STATUS = "FAIL_DEFAULT_CNVTOL_POLICY_VIOLATION"  # 冻结 CNVTOL 被忽略或内部放宽时的专项失败类别。
HARD_ABORT_FAILURE_STATUS = "FAIL_HARD_EVENT_NATIVE_ABORT"  # 冻结硬事件且有效十字节原生 ABT 证据的失败类别。
HARD_NO_ABORT_FAILURE_STATUS = "FAIL_HARD_EVENT_WITHOUT_VALID_NATIVE_ABORT"  # 冻结硬事件但无有效 ABT 合同证据的失败类别。
ABT_FAILURE_STATUS = "FAIL_NATIVE_ABT_TERMINATION"  # 冻结无已证硬事件但日志显示 ABT 终止的失败类别。
NATURAL_FAILURE_STATUS = "FAIL_NATURAL_NONCONVERGENCE"  # 冻结 MAPDL 自然 NCNV 或 LS1/LS2 未收敛的失败类别。
GATE_FAILURE_STATUS = "FAIL_STATIC_GATE_OR_SOLVER_ERROR"  # 冻结非 NCNV 静力门拒绝或求解器错误的失败类别。
INCOMPLETE_FAILURE_STATUS = "FAIL_INCOMPLETE_OR_UNPROVEN_STATIC_SEQUENCE"  # 冻结证据不足以证明两步完整路径的失败类别。
NATIVE_ABORT_LENGTH = 10  # 冻结 MAPDL 2026 R1 批准 ABT 载荷的精确字节数。
NATIVE_ABORT_HEX = "6e6f6e6c696e6561720a"  # 冻结 ASCII nonlinear 加单一 LF 的逐字节十六进制表示。
NATIVE_ABORT_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结十字节原生 ABT 载荷的 SHA-256。
SOLVER_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 限定只读进程检查考虑的 MAPDL 与 MPI 映像名集合。
FORBIDDEN_CALL_NAMES = {"terminate", "kill", "send_signal", "taskkill", "TerminateProcess", "system", "popen", "Popen", "run", "call", "check_call", "check_output"}  # 离线 AST 审计拒绝主动进程处置与 shell/子进程绕行入口。
FINAL_RELATIVE_PATHS = ("qa/ultra_c10_a0_finalize_snapshot.py", "qa/a0_final_audit.json", "qa/a0_final_report.md", "C10_a0_final_status.json", "artifact_hashes_a0_final.sha256")  # 冻结五项不可覆盖最终工件的运行内相对路径。
MONITOR_SPAWN_CLAIM_RELATIVE = "runtime_monitor_spawn_claim.json"  # 冻结启动器自动创建监控器前的排他认领文件名。
MONITOR_LAUNCH_RELATIVE = "runtime_monitor_launch.json"  # 冻结自动监控器 Popen 后的真实 PID 记录文件名。
MONITOR_ATTACHMENT_RELATIVE = "runtime_monitor_attachment.json"  # 冻结启动器验证监控 claim 且存活的双向握手工件名。
HOST_LEASE_RELEASE_RELATIVE = "qa/runtime_a0_host_lease_monitor_release.json"  # 冻结监控稳定终态封存并释放主机租约的运行内证据路径。
NUMBER_PATTERN = r"[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?"  # 定义 MAPDL 整数、小数与科学计数法允许的有限数词法。
LEDGER_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})\s{2}(.+)$")  # 只接受六十四位小写摘要、双空格和相对路径的账本行。
EQUATION_PATTERN = re.compile(r"^\s*NUMBER\s+OF\s+EQUATIONS\s*=\s*(\d+)", re.IGNORECASE | re.MULTILINE)  # 只提取行首 MAPDL 直接求解器组装方程数。
PIVOT_PATTERN = re.compile(rf"^\s*SPARSE\s+SOLVER\s+MINIMUM\s+PIVOT\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE | re.MULTILINE)  # 只提取行首有符号稀疏求解器最小主元。
MESSAGE_HEADER_PATTERN = re.compile(r"^\s*\*\*\*\s+(WARNING|ERROR|FATAL)\s+\*\*\*", re.IGNORECASE | re.MULTILINE)  # 识别真实 MAPDL 警告、错误与致命消息块标题。
COMPLETED_PATTERN = re.compile(r"\*\*\*\s+LOAD\s+STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED", re.IGNORECASE)  # 提取 MAPDL 明确接受并形成结果集的载荷步与子步。
REJECTED_PATTERN = re.compile(r"\*\*\*\s+LOAD\s+STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+NOT\s+COMPLETED(?:\.\s+CUM\s+ITER\s*=\s*(\d+))?", re.IGNORECASE)  # 提取未接受尝试及可选累计迭代数。
BISECTION_PATTERN = re.compile(rf"BEGIN\s+BISECTION\s+NUMBER\s+(\d+)\s+NEW\s+TIME\s+INCREMENT\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 提取 AUTOTS 实际切步编号与新伪时间增量。
ITERATION_PATTERN = re.compile(r"EQUIL\s+ITER\s+(\d+)\s+COMPLETED", re.IGNORECASE)  # 提取每个已完成 Newton 平衡迭代编号。
MNTR_ROW_PATTERN = re.compile(rf"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})(?:\s+|$)", re.IGNORECASE)  # 匹配 MNTR 五个整数控制列与两个时间列。
ERROR_COUNT_PATTERN = re.compile(r"NUMBER\s+OF\s+ERROR\s+MESSAGES\s+ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 页尾累计错误消息数。
WARNING_COUNT_PATTERN = re.compile(r"NUMBER\s+OF\s+WARNING\s+MESSAGES\s+ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 页尾累计警告消息数。
NRRE_NAME_PATTERN_TEMPLATE = r"^{job}\.nr(?P<index>\d{{3}})$"  # 定义本 job 三位平衡迭代 NRRE 文件名模板。
NRRE_SECOND_LINE_PATTERN = re.compile(r"^\s*File written with name\s*=\s*(?P<name>\S+)\s+CNVV\s*=\s*(?P<cnvv>[+\-0-9.Ee]+)\s+CNVC\s*=\s*(?P<cnvc>[+\-0-9.Ee]+)\s*$", re.IGNORECASE)  # 严格解析 NRRE 文件名、残差范数 CNVV 和收敛阈值 CNVC。
CNVTOL_PATTERNS = (re.compile(r"THE\s+CNVTOL\s+COMMAND\s+IS\s+IGNORED", re.IGNORECASE), re.compile(r"CNVTOL\s+COMMAND\s+IS\s+IGNORED", re.IGNORECASE), re.compile(r"INTERNALLY\s+RESET\s+TO\s+CNVTOL\s+TOLERANCE", re.IGNORECASE), re.compile(r"CNVTOL[^\r\n]{0,160}(?:AUTOMATICALLY|INTERNALLY)[^\r\n]{0,80}(?:RELAXED|INCREASED|RESET)", re.IGNORECASE), re.compile(r"(?:AUTOMATICALLY|INTERNALLY)[^\r\n]{0,80}(?:RELAXED|INCREASED|RESET)[^\r\n]{0,160}(?:CNVTOL|CONVERGENCE\s+TOLERANCE)", re.IGNORECASE))  # 冻结默认 CNVTOL 被忽略或自动放宽的真实消息块模式。
BAD_PIVOT_PATTERNS = (("SMALL_EQUATION_SOLVER_PIVOT", re.compile(r"(?:VERY\s+)?SMALL\s+(?:EQUATION\s+SOLVER\s+)?PIVOT", re.IGNORECASE)), ("ZERO_PIVOT", re.compile(r"(?:ZERO\s+PIVOT|PIVOT\s+TERM[^\r\n]{0,80}\sZERO)", re.IGNORECASE)), ("NEGATIVE_PIVOT", re.compile(r"NEGATIVE\s+PIVOT", re.IGNORECASE)))  # 冻结小、零、负主元的原生消息块分类。
NATURAL_NONCONVERGENCE_PATTERNS = (re.compile(r"SOLUTION\s+(?:IS\s+)?NOT\s+CONVERGED", re.IGNORECASE), re.compile(r"FAILED\s+TO\s+CONVERGE", re.IGNORECASE), re.compile(r"CONVERGENCE\s+FAILURE", re.IGNORECASE), re.compile(r"NUMBER\s+OF\s+(?:EQUILIBRIUM\s+)?ITERATIONS\s+EXCEEDS", re.IGNORECASE), re.compile(r"UNCONVERGED\s+SOLUTION", re.IGNORECASE), re.compile(r"LS[12]_(?:SOLVE_NOT_CONVERGED|HOLD_NOT_CONVERGED)", re.IGNORECASE))  # 冻结 MAPDL 自然 NCNV 与 A0 内部门的非收敛签名。
ABT_PATTERNS = (re.compile(r"RUN\s+IS\s+TERMINATED\s+AT\s+THE\s+USER'?S\s+REQUEST\s+FROM\s+THE\s+ABT\s+FILE", re.IGNORECASE), re.compile(r"REASON\s+FOR\s+TERMINATION[^\r\n]*NONLINEAR\s+KEYWORD\s+ON\s+THE\s+ABT\s+FILE", re.IGNORECASE), re.compile(r"NONLINEAR\s+KEYWORD\s+ON\s+THE\s+ABT\s+FILE", re.IGNORECASE))  # 冻结 MAPDL 明确承认原生 ABT 终止的文本签名。


def require(condition: bool, message: str) -> None:  # 接收必须成立的布尔条件和拒绝原因；失败时在发布前中止。
    if not condition:  # 仅当身份、稳定性或数据契约不满足时进入拒绝路径。
        raise RuntimeError(message)  # 抛出带完整上下文的异常，禁止不完整运行被冒充最终结论。


def utc_now() -> str:  # 无业务输入，返回带时区的 ISO-8601 UTC 文本。
    return datetime.now(timezone.utc).isoformat()  # 每次调用独立取时，使终结时刻可审计。


def sha256_bytes(payload: bytes) -> str:  # 接收任意字节并返回六十四位小写 SHA-256。
    return hashlib.sha256(payload).hexdigest()  # 一次计算内存工件摘要，供发布前虚拟入账。


def sha256_file(path: Path, require_stable: bool = False) -> str:  # 接收普通文件和稳定开关，返回完整原始字节摘要。
    require(path.is_file(), f"缺少待摘要普通文件：{path}")  # 计算前拒绝缺失、目录或错路径。
    first_stat = path.stat()  # 读取摘要前的大小与纳秒修改时刻，用于可选稳定检查。
    digest = hashlib.sha256()  # 为当前文件创建独立摘要状态。
    with path.open("rb") as handle:  # 以二进制只读方式打开，禁止编码或换行转换。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 每次读取一 MiB 直至文件末尾，限制峰值内存。
            digest.update(chunk)  # 把当前原始字节块加入摘要状态。
    second_stat = path.stat()  # 读取摘要后的大小与修改时刻，检查是否边读边写。
    if require_stable:  # 只对最终账本和权威原件启用严格单次读取稳定门。
        require(first_stat.st_size == second_stat.st_size and first_stat.st_mtime_ns == second_stat.st_mtime_ns, f"文件在 SHA-256 读取期间变化：{path}")  # 任一属性漂移都阻断终结。
    return digest.hexdigest()  # 返回六十四位小写十六进制摘要。


def read_json(path: Path) -> dict[str, Any]:  # 接收 JSON 路径并返回已验证为对象的顶层字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 读取前拒绝缺失或非普通文件。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 以严格 UTF-8 解析全部文本，禁止静默替换身份字符。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 阻断数组或标量冒充契约对象。
    return payload  # 返回已通过顶层类型检查的异构键值对象。


def render_json(payload: dict[str, Any]) -> str:  # 接收机器对象并返回稳定、保留中文且拒绝 NaN 的 JSON 文本。
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 固定两空格缩进和单一末尾 LF。


def file_snapshot(path: Path) -> dict[str, Any]:  # 接收可能不存在的运行文件并返回存在性、字节数和纳秒时刻。
    if not path.is_file():  # 求解早期或失败路径允许某些原生文件完全未创建。
        return {"exists": False, "size_bytes": 0, "mtime_ns": None}  # 用固定三字段表示缺失，避免访问不存在的状态。
    stat = path.stat()  # 一次读取大小与纳秒修改时刻，减少跨字段竞态。
    return {"exists": True, "size_bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}  # 返回可直接写入 JSON 和精确比较的快照。


def parse_ledger_text(text_value: str) -> dict[str, str]:  # 接收账本全文并返回唯一相对路径到摘要的映射。
    entries: dict[str, str] = {}  # 初始化保持账本顺序的路径摘要映射。
    for line_number, raw_line in enumerate(text_value.splitlines(), start=1):  # 按一基真实行号遍历每个非空账本记录。
        require(bool(raw_line), f"账本含空行：{line_number}")  # 禁止空行或尾部多余分隔被忽略。
        match = LEDGER_LINE_PATTERN.fullmatch(raw_line)  # 尝试按冻结的小写摘要加双空格格式完整匹配。
        require(match is not None, f"账本行格式错误：{line_number}")  # 任何宽松或残缺行都阻断备算。
        digest = str(match.group(1))  # 读取已确认为六十四位小写十六进制的摘要。
        relative_text = str(match.group(2))  # 读取账本中的 POSIX 运行内相对路径文本。
        relative_path = Path(relative_text)  # 将路径文本转为可执行绝对与父段检查的 Path。
        require(relative_text == relative_text.replace("\\", "/") and not relative_path.is_absolute() and ".." not in relative_path.parts, f"账本路径不是安全 POSIX 相对路径：{relative_text}")  # 阻断反斜杠、绝对路径与父目录逃逸。
        require(relative_text not in entries, f"账本路径重复：{relative_text}")  # 禁止同一工件以不同摘要重复声明。
        entries[relative_text] = digest  # 保存已通过语法与路径安全检查的条目。
    return entries  # 返回完整映射，空账本由调用者按运行合同拒绝。


def verify_hash_ledger(path: Path, root: Path) -> dict[str, str]:  # 接收准备账本和运行根，返回已逐项复算通过的映射。
    entries = parse_ledger_text(path.read_text(encoding="utf-8", errors="strict"))  # 严格 UTF-8 读取并使用与离线自测相同的纯解析器。
    require(len(entries) >= 25, f"A0 准备账本条目不足二十五项：{len(entries)}")  # 阻断裁剪包或丢失运行工具的准备运行。
    resolved_root = root.resolve()  # 规范化运行根，供每个账本路径的边界比较。
    for relative_text, expected_digest in entries.items():  # 按账本顺序逐项复算全部准备字节。
        artifact_path = (resolved_root / Path(relative_text)).resolve()  # 合并相对路径并消除点段与链接歧义。
        require(artifact_path == resolved_root or resolved_root in artifact_path.parents, f"账本工件越出运行根：{relative_text}")  # 二次阻断符号链接或路径绕过。
        observed_digest = sha256_file(artifact_path, require_stable=True)  # 对当前原件做完整且单次读取稳定的 SHA-256。
        require(observed_digest == expected_digest, f"准备账本摘要不一致：{relative_text}")  # 任一上游字节漂移都拒绝终结。
    return entries  # 返回已以当前原件逐项重算的准备映射。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收启动参数数组和标志，返回该唯一标志的相邻后继值。
    indices = [index for index, value in enumerate(arguments) if value.casefold() == flag.casefold()]  # 忽略 Windows 大小写差异定位全部标志位置。
    require(len(indices) == 1, f"启动参数 {flag} 出现 {len(indices)} 次，预期 1 次")  # 缺失或重复都会造成 job 或路径身份歧义。
    index = indices[0]  # 读取已确认唯一的标志下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止数组越界或空参数。
    return str(arguments[index + 1])  # 返回求解器真实采用的相邻文本值。


def executable_commands(text_value: str) -> list[str]:  # 接收完整 APDL 文本并返回去说明、去空格和大写化的可执行命令。
    commands: list[str] = []  # 初始化保持原始执行顺序的命令列表。
    for raw_line in text_value.splitlines():  # 按主控实际物理行遍历全部 APDL。
        command = raw_line.split("!", 1)[0].strip().upper().replace(" ", "")  # 去除感叹号后说明、首尾与内部空格并归一大小写。
        if command:  # 只有去除说明后仍有内容的行才影响求解器。
            commands.append(command)  # 保存当前可执行命令供计数和禁止项审计。
    return commands  # 返回不含纯说明的稳定命令序列。


def resolve_run(run_dir_value: Path) -> Path:  # 接收调用者给出的唯一路径并返回通过边界和运行族门的绝对目录。
    run_dir = run_dir_value.resolve()  # 消除相对段、当前目录与链接歧义。
    require(run_dir.is_dir(), f"A0 运行目录不存在：{run_dir}")  # 拒绝缺失路径或普通文件。
    require(run_dir.parent == RUNS_ROOT.resolve(), f"A0 运行不是 ultra_runs 的直接子目录：{run_dir}")  # 阻断跨项目或嵌套目录误发布。
    require(run_dir.name.startswith(EXPECTED_RUN_PREFIX), f"运行名不属于 A0 直接空间斜坡族：{run_dir.name}")  # 禁止其他诊断借用 A0 判据。
    require(not (run_dir / "SUPERSEDED_NOT_LAUNCHED.json").exists(), "A0 运行已标记 SUPERSEDED_NOT_LAUNCHED，禁止写入最终工件")  # 明确保护旧的未启动替代运行。
    targets = [run_dir / relative_text for relative_text in FINAL_RELATIVE_PATHS]  # 构造本终结器五项唯一最终目标。
    require(all(not path.exists() for path in targets), "A0 已存在本终结器的最终工件，拒绝重复或覆盖发布")  # 一个 run 只允许首次不可覆盖终结。
    require(not (run_dir / "C10_static_final_status.json").exists() and not (run_dir / "C10_modal_final_status.json").exists(), "A0 运行已有静力或模态最终状态，禁止分叉封板")  # 阻断与旧成功或模态终态并存。
    return run_dir  # 返回已通过边界、运行族、替代与唯一发布门的目录。


def validate_prepared_package(run_dir: Path) -> dict[str, Any]:  # 接收已解析 A0 运行并返回逐项复算通过的准备身份与路径。
    manifest_path = run_dir / "manifest.json"  # 定位冻结运行用途、输入、控制与启动参数的主清单。
    root_status_path = run_dir / "C10_static_status.json"  # 定位准备期生命周期和诊断/生产权限原件。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位启动前已冻结且不得修改的准备账本。
    manifest = read_json(manifest_path)  # 独立读取主清单，不借用启动或监控摘要。
    root_status = read_json(root_status_path)  # 独立读取根状态，不对其准备态字节做事后更写。
    require(manifest.get("schema_version") == 1 and root_status.get("schema_version") == 1, "A0 manifest 或根状态 schema 版本不是 1")  # 只接受本终结器已审查的第一版契约。
    require(manifest.get("run_name") == run_dir.name == root_status.get("run_name"), "A0 目录、manifest 与根状态运行名不一致")  # 关闭跨运行复制和目录复用风险。
    jobname = str(manifest.get("jobname", ""))  # 读取将用于全部原生文件族和进程身份的唯一 jobname。
    require(bool(jobname) and jobname == str(root_status.get("jobname", "")) and len(jobname) <= 32, "A0 jobname 缺失、分叉或超过 MAPDL 三十二字符限制")  # 固定文件前缀与启动身份。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "A0 准备 manifest 或根状态已作废或漂移")  # 最终工件采用追加发布，不允许覆写上游准备态。
    require(manifest.get("diagnostic_subtype") == EXPECTED_SUBTYPE == root_status.get("diagnostic_subtype"), "A0 诊断子类型不是直接空间重力斜坡 NRRE 路径")  # 禁止其他试验借用本判据。
    require(manifest.get("load_path_mode") == EXPECTED_LOAD_PATH, "A0 载荷路径不是 S10 直接空间 MASS21 重力斜坡")  # 阻断位置迁移或其他物理变量混入。
    require(root_status.get("launch_allowed_for_diagnostic") is True and root_status.get("launch_allowed_for_production") is False and root_status.get("valid_for_production") is False, "A0 根状态未固定为仅诊断且非生产")  # 从上游权限层关闭生产外推。
    orchestration = manifest.get("runtime_orchestration")  # 读取新 A0 准备器冻结的主机租约、双扫描与自动监控握手合同。
    require(isinstance(orchestration, dict), "A0 manifest 缺少新的 runtime_orchestration 租约/自动监控契约")  # 本终结器只接受已修复 P1 编排闭环的新 run。
    require(orchestration.get("host_lease_path") == str(HOST_LEASE_PATH) and orchestration.get("host_lease_acquired_after_first_solver_scan") is True and orchestration.get("double_solver_scan_required") is True, "A0 manifest 主机租约路径或租约前后双求解器扫描合同不完整")  # 固定租约前一次、MAPDL Popen 前一次空扫描。
    require(orchestration.get("monitor_auto_start_required") is True and float(orchestration.get("monitor_claim_timeout_seconds", -1.0)) == 30.0 and orchestration.get("monitor_releases_host_lease_only_after_stable_empty_exit") is True, "A0 manifest 自动监控、三十秒 claim 握手或稳定退出释放租约合同不完整")  # 禁止人工补挂监控或提前释放租约。
    require(orchestration.get("blocked_or_unconfirmed_exit_retains_host_lease") is True and orchestration.get("postlaunch_unrelated_solver_process_is_hard_event") is True and orchestration.get("native_abort_target_scope") == "THIS_A0_JOB_ONLY" and orchestration.get("active_process_disposition_allowed") is False, "A0 manifest 阻断保留租约、无关求解器硬事件或 ABT 安全边界不完整")  # 确保终结器不接受弱化的旧运行链。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and manifest.get("a0_direct_production_promotion_allowed") is False, "A0 manifest 未关闭模态或直接生产升格")  # 确保通过也只能去 A0B。
    require(manifest.get("convergence_acceptance_scope") == "DEFAULT_CNVTOL_DIAGNOSTIC_ONLY" and manifest.get("default_cnvtol_log_auto_relaxation_allowed") is False, "A0 默认 CNVTOL 诊断边界或日志放宽禁令漂移")  # 固定被忽略/自动放宽必须失败的语义。
    require(manifest.get("cnvtol_explicit_command_count") == 0 and manifest.get("cnvtol_changed") is False, "A0 manifest 不再声明零条显式 CNVTOL 且未改收敛准则")  # 保持与 S10 原成功路径的历史二分合同。
    require(manifest.get("if_a0_passes_next_run") == "A0B_SAME_PATH_WITH_CURRENT_FOUR_EXPLICIT_CNVTOL_STATIC_ACCEPTANCE", "A0 通过后的 A0B 显式四项 CNVTOL 义务不一致")  # 防止诊断成功被直接升格。
    require(int(manifest.get("expected_equation_count", 0)) == EXPECTED_EQUATION_COUNT and manifest.get("runtime_equation_count_change_allowed") is False, "A0 方程数基线或漂移禁令错误")  # 冻结组装秩门。
    require(manifest.get("runtime_small_zero_negative_pivot_allowed") is False, "A0 manifest 意外允许小、零或负主元")  # 坏主元不得被非收敛或门结果掩盖。
    topology = manifest.get("expected_topology")  # 读取准备阶段冻结的节点、单元、连接与边界统计。
    require(isinstance(topology, dict), "A0 expected_topology 不是对象")  # 阻断缺失或非结构化拓扑契约。
    expected_topology = {"nodes": EXPECTED_NODE_COUNT, "elements": EXPECTED_ELEMENT_COUNT, "TYPE4": 73_692, "TYPE6": 48_620, "TYPE70": 17_679, "TYPE71": 33_003, "TYPE72": EXPECTED_TYPE72_COUNT, "TYPE73": 0, "CERIG_commands": 0, "CP_commands": 12, "D_commands": 3_968}  # 构造本 A0 运行族已批准的完整拓扑统计。
    require(all(int(topology.get(key, -1)) == value for key, value in expected_topology.items()), f"A0 expected_topology 与冻结单层 TYPE72 统计不一致：{topology}")  # 任一节点、单元或约束统计漂移都拒绝。
    ls1 = manifest.get("ls1")  # 读取第一载荷步的斜坡加载数值控制。
    ls2 = manifest.get("ls2")  # 读取第二载荷步的零物理增量保持控制。
    nrre = manifest.get("nrre")  # 读取节点残差诊断输出契约。
    require(ls1 == {"kbc": 0, "autots": True, "nsubst": [20, 200, 20], "pred": "OFF", "time": 1.0}, f"A0 LS1 控制不等于 S10 斜坡路径：{ls1}")  # 精确冻结 KBC、AUTOTS、NSUBST、PRED 和终点。
    require(ls2 == {"kbc": 0, "autots": False, "nsubst": [1, 1, 1], "time": 1.001, "physical_load_increment": 0.0}, f"A0 LS2 零增量保持控制错误：{ls2}")  # 精确冻结单子步无 cutback 和 time=1.001。
    require(nrre == {"enabled": True, "label": "NRRE", "maxfile": EXPECTED_NRRE_MAXFILE, "eflg_enabled": False}, f"A0 NRRE 合同不是 ON/50 且 EFLG 关闭：{nrre}")  # 禁止另一数值诊断变量混入。
    prepared_entries = verify_hash_ledger(prepared_ledger_path, run_dir)  # 在读取任何求解结论前逐项复算全部准备字节。
    require("manifest.json" in prepared_entries and "C10_static_status.json" in prepared_entries and str(manifest.get("main_input", "")) in prepared_entries, "A0 准备账本缺少 manifest、根状态或主控")  # 关闭核心工件脱离账本的失效开放路径。
    main_relative = str(manifest.get("main_input", ""))  # 读取清单声明的唯一主 APDL 运行内相对路径。
    main_path = (run_dir / main_relative).resolve()  # 构造主控绝对路径供命令和摘要复核。
    solver_dir = (run_dir / "solver").resolve()  # 定位与启动 -dir 必须一致的唯一求解目录。
    require(main_path.parent == solver_dir and main_path.is_file(), f"A0 主控不在本运行 solver 目录：{main_path}")  # 阻断外部输入或路径逃逸。
    main_sha256 = sha256_file(main_path, require_stable=True)  # 复算实际执行 deck 字节摘要。
    require(main_sha256 == manifest.get("main_input_sha256") == prepared_entries[main_relative], "A0 主控、manifest 和准备账本 SHA-256 不一致")  # 闭合执行输入的三方身份。
    main_text = main_path.read_text(encoding="utf-8", errors="strict")  # 以严格 UTF-8 读取准备已冻结的 A0 deck。
    commands = executable_commands(main_text)  # 提取不受中文说明影响的真实 APDL 命令序列。
    require(commands.count("SOLVE") == 2 and commands.count("ANTYPE,STATIC") == 1, "A0 deck 不是唯一静力分析与两次 SOLVE")  # 固定 LS1 和 LS2 唯一两步路径。
    require(commands.count("NLDIAG,NRRE,ON,50") == 1 and not any(command.startswith("NLDIAG,EFLG") for command in commands), "A0 deck 的 NRRE ON/50 或 EFLG 禁令漂移")  # 固定唯一数值新增。
    require(not any(command.startswith("CNVTOL,") for command in commands), "A0 deck 含显式 CNVTOL，不再是默认 CNVTOL 历史二分")  # 阻断输入与清单分叉。
    require(not any(command.startswith(prefix) for command in commands for prefix in ("ANTYPE,MODAL", "MODOPT,", "MXPAND,", "PERTURB,")), "A0 deck 含模态或扰动求解命令")  # 确保静力外部门后已完整截断。
    require(commands.count("KBC,0") == 2 and commands.count("AUTOTS,ON") == 1 and commands.count("AUTOTS,OFF") >= 1 and commands.count("NSUBST,20,200,20") == 1 and commands.count("NSUBST,1,1,1") == 1 and commands.count("PRED,OFF") == 1, "A0 deck 的 LS1/LS2 数值控制计数漂移")  # 以命令实体交叉复核 manifest。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 把冻结启动参数规范为字符串数组。
    require(len(launch_argv) >= 13 and launch_argv[0] == str(manifest.get("mapdl_executable", "")), "A0 manifest 启动参数缺失或首项不是冻结 MAPDL 可执行文件")  # 固定真实进程入口。
    require("-b" in [value.casefold() for value in launch_argv] and "-smp" in [value.casefold() for value in launch_argv], "A0 启动参数未固定批处理 SMP")  # 阻断交互式或分布式模式混入。
    require(argument_value(launch_argv, "-np") == "1" and argument_value(launch_argv, "-j") == jobname, "A0 启动参数未固定 SMP1 或唯一 jobname")  # 固定单进程诊断模式。
    require(Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir and Path(argument_value(launch_argv, "-i")).resolve() == main_path, "A0 启动 -dir 或 -i 不指向本运行原件")  # 关闭跨目录执行风险。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 从冻结启动数组解析唯一权威 OUT 路径。
    require(output_path.parent == solver_dir and output_path.name.casefold() == f"{jobname}.out".casefold(), "A0 启动 -o 不是本 solver/jobname 权威 OUT")  # 阻断将其他运行日志归入本结论。
    return {"manifest": manifest, "root_status": root_status, "manifest_path": manifest_path, "root_status_path": root_status_path, "prepared_ledger_path": prepared_ledger_path, "prepared_entries": prepared_entries, "prepared_ledger_sha256": sha256_file(prepared_ledger_path, require_stable=True), "main_path": main_path, "main_sha256": main_sha256, "main_commands": commands, "solver_dir": solver_dir, "jobname": jobname, "launch_argv": launch_argv, "output_path": output_path}  # 返回准备链摘要、已验证输入和后续权威路径。


def process_identity_is_alive(identity: dict[str, Any]) -> bool:  # 接收冻结 PID、创建时刻、二进制和参数并返回同一进程是否仍存活。
    try:  # 尝试以只读系统调用复原当前 PID 身份。
        process = psutil.Process(int(identity["pid"]))  # 按冻结 PID 获取当前进程对象，但不单凭 PID 下结论。
        if abs(float(process.create_time()) - float(identity["create_time_epoch_seconds"])) > 0.001:  # 创建时刻差超过一毫秒表示 PID 已复用。
            return False  # 将复用 PID 视为原 MAPDL 身份已消失。
        if str(Path(process.exe()).resolve()).casefold() != str(Path(str(identity["executable"])).resolve()).casefold():  # 实际映像路径变化表示不是同一执行身份。
            return False  # 二进制不一致时不把无关进程冒充为未退出求解器。
        return [str(value) for value in process.cmdline()] == [str(value) for value in identity["command_line"]]  # 只有完整参数数组也一致才返回同一身份存活。
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError, TypeError, ValueError, OSError):  # 进程消失、僵尸、权限或身份字段不可读时进入保守结果。
        return False  # 无法复原精确同一身份时返回原进程不存活，后续仍扫描本 job 其他 worker。


def command_flag_matches(arguments: list[str], flag: str, expected: str, path_value: bool) -> bool:  # 接收真实参数、标志、期望值和路径语义，返回唯一相邻值是否精确匹配。
    indices = [index for index, value in enumerate(arguments) if str(value).casefold() == flag.casefold()]  # 查找忽略大小写的全部标志位置。
    if len(indices) != 1 or indices[0] + 1 >= len(arguments):  # 缺失、重复或无后继值均不能作为进程归属证据。
        return False  # 返回不匹配而不打断全局只读进程枚举。
    observed = str(arguments[indices[0] + 1])  # 读取真实参数中的唯一相邻值。
    if path_value:  # -dir 等路径参数需先规范化再做 Windows 不区分大小写比较。
        try:  # 无效路径文本不应使全局进程枚举失败。
            return str(Path(observed).resolve()).casefold() == str(Path(expected).resolve()).casefold()  # 仅规范绝对路径完全相同时返回真。
        except (OSError, RuntimeError):  # 捕获路径规范化错误或异常链接循环。
            return False  # 无法证明相等时保持 fail-closed 的非归属结果。
    return observed.casefold() == expected.casefold()  # 普通 jobname 要求完整文本相等，不允许子串命中。


def active_job_processes(jobname: str, solver_dir: Path) -> list[dict[str, Any]]:  # 接收唯一 job 与求解目录，返回仍携带双重身份的求解进程只读记录。
    records: list[dict[str, Any]] = []  # 初始化仍活动本 job 进程的紧凑证据列表。
    for process in psutil.process_iter(["pid", "name", "cmdline", "create_time", "exe"]):  # 一次枚举并只请求归属判断所需身份字段。
        try:  # 进程可在枚举中途自然退出或改变可读权限。
            name = str(process.info.get("name") or "").casefold()  # 规范化映像名供批准集合精确匹配。
            arguments = [str(value) for value in (process.info.get("cmdline") or [])]  # 保留完整参数数组供 -j/-dir 双门归属。
            if name in SOLVER_PROCESS_NAMES and command_flag_matches(arguments, "-j", jobname, False) and command_flag_matches(arguments, "-dir", str(solver_dir), True):  # 只纳入映像、job 和工作目录三方同时一致的进程。
                records.append({"pid": int(process.info["pid"]), "name": name, "create_time_epoch_seconds": float(process.info.get("create_time") or process.create_time()), "executable": str(process.info.get("exe") or ""), "command_line": arguments})  # 保存足以人工核对且不含动作的身份记录。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, TypeError, ValueError):  # 忽略在只读采样间消失、僵尸或不可读的无法证明归属进程。
            continue  # 继续检查下一系统进程，不对任何 PID 发出动作。
    return sorted(records, key=lambda record: int(record["pid"]))  # 按 PID 稳定排序返回当前精确本 job 进程。


def exact_command_line_processes(expected_arguments: list[str]) -> list[dict[str, Any]]:  # 接收冻结参数数组并返回当前仍以完全相同命令行运行的只读进程记录。
    records: list[dict[str, Any]] = []  # 初始化精确命令行匹配进程列表。
    for process in psutil.process_iter(["pid", "name", "cmdline", "create_time", "exe"]):  # 一次枚举系统进程且只请求身份字段。
        try:  # 进程可在只读枚举期间自然退出或变为不可读。
            arguments = [str(value) for value in (process.info.get("cmdline") or [])]  # 读取不修改的完整真实参数数组。
            if arguments == expected_arguments:  # 只有项数、顺序和每个文本都相同才确认为目标进程。
                records.append({"pid": int(process.info["pid"]), "name": str(process.info.get("name") or ""), "create_time_epoch_seconds": float(process.info.get("create_time") or process.create_time()), "executable": str(process.info.get("exe") or ""), "command_line": arguments})  # 保存完整身份供拒绝说明。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, TypeError, ValueError):  # 忽略在查询中自然消失或无法证明身份的进程。
            continue  # 继续检查下一进程，不发出任何进程动作。
    return sorted(records, key=lambda record: int(record["pid"]))  # 按 PID 稳定返回当前仍存活的精确命令行身份。


def validate_runtime_chain(prepared: dict[str, Any]) -> dict[str, Any]:  # 接收已通过准备门的上下文并返回闭合的三段启动身份链。
    run_dir = Path(str(prepared["manifest_path"])).parent.resolve()  # 从已验证 manifest 反推唯一运行根。
    claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前已排他写出的启动认领原件。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后立即写出的最小 PID 启动记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位带创建时刻、映像和完整参数的增强身份。
    identity_failure_path = run_dir / "runtime_process_identity_failure.json"  # 定位增强身份捕获失败且请求 ABT 的互斥工件。
    monitor_spawn_claim_path = run_dir / MONITOR_SPAWN_CLAIM_RELATIVE  # 定位启动器创建监控器前提交的自动创建认领。
    monitor_launch_path = run_dir / MONITOR_LAUNCH_RELATIVE  # 定位自动监控器 Popen 后的真实 PID 记录。
    monitor_attachment_path = run_dir / MONITOR_ATTACHMENT_RELATIVE  # 定位启动器验证监控 claim 且仍存活的双向握手工件。
    failure_paths = [identity_failure_path, run_dir / "runtime_prelaunch_failure.json", run_dir / "runtime_popen_failure.json", run_dir / "runtime_monitor_attachment_failure.json"]  # 汇总与完整启动及自动监控链互斥的四类失败工件。
    require(claim_path.is_file() and launch_path.is_file() and identity_path.is_file(), "A0 缺少 runtime launch claim、launch 或 process identity，不是可终结的真实运行")  # 阻断旧未启动准备包。
    require(not any(path.exists() for path in failure_paths), f"A0 存在与完整启动/自动监控链互斥的失败工件：{[str(path) for path in failure_paths if path.exists()]}")  # 分叉启动故障不得冒充可常规封板运行。
    require(monitor_spawn_claim_path.is_file() and monitor_launch_path.is_file() and monitor_attachment_path.is_file(), "A0 缺少自动监控 spawn claim、launch 或 attachment 握手工件")  # 只接受新 run 的自动监控闭环，禁止人工补挂。
    claim = read_json(claim_path)  # 独立读取启动前认领原件。
    launch = read_json(launch_path)  # 独立读取最小真实 PID 记录。
    identity = read_json(identity_path)  # 独立读取防 PID 复用的增强身份原件。
    monitor_spawn_claim = read_json(monitor_spawn_claim_path)  # 独立读取监控器 Popen 前的自动创建认领。
    monitor_launch = read_json(monitor_launch_path)  # 独立读取监控器真实 PID 与参数记录。
    monitor_attachment = read_json(monitor_attachment_path)  # 独立读取启动器等待监控 claim 成功的握手证据。
    manifest = prepared["manifest"]  # 引用已通过准备字节门的主清单对象。
    run_name = run_dir.name  # 冻结当前目录名供四方运行身份比较。
    jobname = str(prepared["jobname"])  # 引用已通过准备门的唯一 jobname。
    require(claim.get("schema_version") == 1 and launch.get("schema_version") == 1 and identity.get("schema_version") == 1, "A0 runtime 三段链 schema 版本不是 1")  # 只允许已审查契约。
    require(claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED" and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING" and identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED", "A0 runtime 认领、PID 或增强身份状态错误")  # 固定先认领、后启动、再捕获身份的顺序。
    require(claim.get("run_name") == launch.get("run_name") == identity.get("run_name") == run_name and claim.get("jobname") == launch.get("jobname") == identity.get("jobname") == jobname, "A0 runtime 三段链运行名或 jobname 分叉")  # 关闭跨运行工件复制。
    require(claim.get("diagnostic_subtype") == launch.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "A0 runtime 诊断子类型漂移")  # 防止其他路径借用运行身份。
    manifest_sha256 = sha256_file(Path(str(prepared["manifest_path"])), require_stable=True)  # 复算已入准备账本的 manifest 原件摘要。
    prepared_ledger_sha256 = str(prepared["prepared_ledger_sha256"])  # 读取刚刚对准备账本本身复算得到的摘要。
    prepared_entry_count = len(prepared["prepared_entries"])  # 计算已复算通过的准备条目数。
    require(claim.get("manifest_sha256") == launch.get("manifest_sha256") == manifest_sha256, "A0 runtime 认领或启动记录引用的 manifest 摘要不一致")  # 闭合准备输入身份。
    require(claim.get("prepared_ledger_sha256") == launch.get("prepared_ledger_sha256") == prepared_ledger_sha256, "A0 runtime 认领或启动记录引用的准备账本摘要不一致")  # 防止启动前后输入包漂移。
    require(int(claim.get("prepared_ledger_entry_count", -1)) == int(launch.get("prepared_ledger_entry_count", -1)) == prepared_entry_count, "A0 runtime 准备账本条目数不一致")  # 防止只对账本文件摘要而忽略裁剪条目。
    require(launch.get("launch_claim_sha256") == sha256_file(claim_path, require_stable=True), "A0 runtime launch 未正确引用 Popen 前认领摘要")  # 闭合第一段到第二段链。
    require(identity.get("runtime_launch_sha256") == sha256_file(launch_path, require_stable=True), "A0 runtime identity 未正确引用最小 PID 启动记录")  # 闭合第二段到第三段链。
    launch_argv = [str(value) for value in prepared["launch_argv"]]  # 引用已通过 -j/-dir/-i/-o 检查的 manifest 启动数组。
    require(launch_argv == [str(value) for value in claim.get("launch_argv", [])] == [str(value) for value in launch.get("launch_argv", [])] == [str(value) for value in identity.get("command_line", [])], "A0 manifest、认领、启动与操作系统真实参数数组不一致")  # 固定实际执行入口。
    require(int(identity.get("pid", 0)) == int(launch.get("main_pid", -1)) > 0 and launch.get("process_identity_path") == "runtime_process_identity.json", "A0 增强身份 PID 或路径与启动记录不一致")  # 关闭 PID 和身份文件的歧义。
    require(str(Path(str(identity.get("executable", ""))).resolve()).casefold() == str(Path(launch_argv[0]).resolve()).casefold(), "A0 操作系统真实映像不是 manifest MAPDL 可执行文件")  # 固定真实二进制身份。
    require(claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "A0 启动认领与 PID 记录的启动前资源快照分叉")  # 防止启动后事后改写资源门。
    prelaunch_resources = claim.get("prelaunch_resources")  # 读取启动前第二次资源快照和租约前后求解器扫描记录。
    require(isinstance(prelaunch_resources, dict) and claim.get("double_solver_scan_completed") is True and prelaunch_resources.get("first_solver_scan") == [] and prelaunch_resources.get("second_solver_scan") == [], "A0 启动链未证明租约前后两次求解器空扫描")  # 阻断与其他 MAPDL/MPI 并发运行。
    host_lease_sha256 = str(claim.get("host_lease_sha256", ""))  # 读取启动认领冻结的跨运行主机租约字节身份。
    require(claim.get("host_lease_path") == launch.get("host_lease_path") == prelaunch_resources.get("host_lease_path") == str(HOST_LEASE_PATH) and launch.get("host_lease_sha256") == prelaunch_resources.get("host_lease_sha256") == host_lease_sha256 and len(host_lease_sha256) == 64, "A0 启动认领、PID 记录与资源快照的主机租约路径或摘要分叉")  # 闭合租约在 MAPDL Popen 前后的同一性。
    require(claim.get("monitor_auto_start_required") is True and float(claim.get("monitor_attachment_timeout_seconds", -1.0)) == 30.0 and claim.get("postlaunch_unrelated_solver_process_is_hard_event") is True and launch.get("postlaunch_unrelated_solver_process_is_hard_event") is True, "A0 启动链未冻结自动监控、三十秒握手或无关求解器硬事件政策")  # 确保新编排合同实际进入运行链。
    require(claim.get("production_claim_allowed") is False and launch.get("production_claim_allowed") is False, "A0 runtime 链意外允许生产结论")  # 从真实执行链再次关闭生产外推。
    require(isinstance(launch.get("monitor_hard_stops"), dict) and bool(launch.get("monitor_hard_stops")), "A0 runtime launch 缺少资源监控硬门")  # 不允许无安全监控合同的执行进入最终审计。
    require(monitor_spawn_claim.get("schema_version") == 1 and monitor_spawn_claim.get("status") == "MONITOR_AUTO_SPAWN_CLAIMED_NOT_YET_STARTED" and monitor_spawn_claim.get("run_name") == run_name and monitor_spawn_claim.get("jobname") == jobname, "A0 监控器自动创建认领 schema、状态或身份错误")  # 固定监控 Popen 前的排他语义。
    require(monitor_spawn_claim.get("runtime_launch_sha256") == sha256_file(launch_path, require_stable=True) and monitor_spawn_claim.get("runtime_process_identity_sha256") == sha256_file(identity_path, require_stable=True), "A0 监控器自动创建认领引用的 MAPDL launch 或 identity 摘要不一致")  # 证明监控在 MAPDL 身份捕获成功后创建。
    require(monitor_spawn_claim.get("host_lease_path") == str(HOST_LEASE_PATH) and monitor_spawn_claim.get("host_lease_sha256") == host_lease_sha256 and float(monitor_spawn_claim.get("attachment_timeout_seconds", -1.0)) == 30.0 and monitor_spawn_claim.get("postlaunch_unrelated_solver_process_is_hard_event") is True and monitor_spawn_claim.get("active_process_disposition_allowed") is False, "A0 监控器自动创建认领的租约、握手或安全政策错误")  # 闭合自动监控与同一租约。
    monitor_argv = [str(value) for value in monitor_spawn_claim.get("monitor_argv", [])]  # 读取启动器用于创建专用监控器的完整参数数组。
    expected_monitor_script = (run_dir / str(manifest["runtime_monitor_script"])).resolve()  # 定位准备账本保护的运行内监控器快照。
    require(len(monitor_argv) == 5 and monitor_argv[1:] == ["-B", str(expected_monitor_script), "--run-dir", str(run_dir)] and monitor_spawn_claim.get("monitor_script_sha256") == sha256_file(expected_monitor_script, require_stable=True), "A0 监控器不是以冻结脚本、无 pyc 和唯一 run-dir 自动创建")  # 阻断人工补挂或参数漂移。
    require(monitor_launch.get("schema_version") == 1 and monitor_launch.get("status") == "MONITOR_PROCESS_STARTED_CLAIM_PENDING" and monitor_launch.get("run_name") == run_name and monitor_launch.get("jobname") == jobname and [str(value) for value in monitor_launch.get("monitor_argv", [])] == monitor_argv, "A0 监控器 PID 记录 schema、状态、身份或参数错误")  # 固定真实监控进程启动身份。
    monitor_spawn_claim_sha256 = sha256_file(monitor_spawn_claim_path, require_stable=True)  # 复算监控 Popen 前排他认领摘要。
    require(monitor_launch.get("monitor_spawn_claim_sha256") == monitor_spawn_claim_sha256 and monitor_launch.get("host_lease_sha256") == host_lease_sha256 and int(monitor_launch.get("monitor_pid", 0)) > 0, "A0 监控器 PID 记录引用的 spawn claim、租约或 PID 错误")  # 闭合监控认领到真实 PID 的链。
    require(monitor_attachment.get("schema_version") == 1 and monitor_attachment.get("status") == "MONITOR_AUTO_STARTED_AND_ATTACHMENT_CLAIM_VERIFIED" and monitor_attachment.get("run_name") == run_name and monitor_attachment.get("jobname") == jobname, "A0 监控 attachment 握手 schema、状态或身份错误")  # 只接受启动器在三十秒内确认的有效附着。
    monitor_launch_sha256 = sha256_file(monitor_launch_path, require_stable=True)  # 复算自动监控器真实 PID 记录摘要。
    require(int(monitor_attachment.get("main_pid", 0)) == int(launch["main_pid"]) and int(monitor_attachment.get("monitor_pid", 0)) == int(monitor_launch["monitor_pid"]) and monitor_attachment.get("monitor_spawn_claim_sha256") == monitor_spawn_claim_sha256 and monitor_attachment.get("monitor_launch_sha256") == monitor_launch_sha256, "A0 监控 attachment 握手的 MAPDL PID、监控 PID 或两段摘要链不一致")  # 闭合自动创建、PID 与握手三段链。
    require(monitor_attachment.get("host_lease_sha256") == host_lease_sha256 and monitor_attachment.get("monitor_process_alive_at_attachment") is True and monitor_attachment.get("monitor_owns_terminal_host_lease_release") is True, "A0 监控 attachment 未闭合租约或终态释放所有权")  # 固定监控而非启动器负责稳定终态释放。
    require(not process_identity_is_alive(identity), f"A0 冻结 MAPDL 主进程身份仍存活：{identity.get('pid')}")  # 求解中禁止启动终结器。
    remaining_processes = active_job_processes(jobname, Path(str(prepared["solver_dir"])))  # 独立扫描仍携带本 job 与 solver 双标志的 worker 或包装进程。
    require(not remaining_processes, f"A0 仍有本 job 求解器进程活动：{remaining_processes}")  # 只有 PID 和本 job 进程树均消失才可继续。
    remaining_monitors = exact_command_line_processes(monitor_argv)  # 独立检查自动监控器精确参数身份是否仍存活。
    require(not remaining_monitors, f"A0 自动监控器精确进程仍存活：{remaining_monitors}")  # 只在监控已完成终态释放并返回后运行终结器。
    require(not HOST_LEASE_PATH.exists(), f"A0 跨运行主机租约仍存在：{HOST_LEASE_PATH}")  # 稳定空进程终态必须已由监控器封存并释放租约。
    return {"claim": claim, "launch": launch, "identity": identity, "claim_path": claim_path, "launch_path": launch_path, "identity_path": identity_path, "claim_sha256": sha256_file(claim_path, require_stable=True), "launch_sha256": sha256_file(launch_path, require_stable=True), "identity_sha256": sha256_file(identity_path, require_stable=True), "main_pid": int(launch["main_pid"]), "create_time_epoch_seconds": float(identity["create_time_epoch_seconds"]), "active_job_processes": remaining_processes, "monitor_spawn_claim": monitor_spawn_claim, "monitor_launch": monitor_launch, "monitor_attachment": monitor_attachment, "monitor_spawn_claim_path": monitor_spawn_claim_path, "monitor_launch_path": monitor_launch_path, "monitor_attachment_path": monitor_attachment_path, "monitor_spawn_claim_sha256": monitor_spawn_claim_sha256, "monitor_launch_sha256": monitor_launch_sha256, "monitor_attachment_sha256": sha256_file(monitor_attachment_path, require_stable=True), "monitor_argv": monitor_argv, "active_monitor_processes": remaining_monitors, "host_lease_path": HOST_LEASE_PATH, "host_lease_sha256": host_lease_sha256, "host_lease_absent_after_stable_exit": True}  # 返回 MAPDL 启动、自动监控、租约与双向握手的完整闭合证据。


def read_jsonl(path: Path) -> list[dict[str, Any]]:  # 接收监控 JSONL 路径并返回按原文顺序严格解析的样本对象列表。
    require(path.is_file() and path.stat().st_size > 0, f"缺少或为空的监控 JSONL：{path}")  # 空流水无法独立复算退出稳定性。
    samples: list[dict[str, Any]] = []  # 初始化保持只读流水物理顺序的样本列表。
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1):  # 以严格 UTF-8 按一基行号遍历每个已刷新样本。
        require(bool(raw_line), f"监控 JSONL 含空行：{line_number}")  # 禁止中间空行或部分写入被静默跳过。
        payload = json.loads(raw_line)  # 将当前单行解析为一个完整 JSON 值。
        require(isinstance(payload, dict), f"监控 JSONL 第 {line_number} 行顶层不是对象")  # 数组或标量不得冒充样本。
        samples.append(payload)  # 保存已通过单行完整性与顶层类型检查的样本。
    return samples  # 返回可复算索引、资源极值、方程数和硬事件的有序列表。


def native_abort_contract_valid(native_abort: dict[str, Any]) -> bool:  # 接收监控原生 ABT 证据并返回十字节合同是否完整成立。
    return native_abort.get("request_contract_satisfied") is True and int(native_abort.get("native_abort_readback_length_bytes", -1)) == NATIVE_ABORT_LENGTH and str(native_abort.get("native_abort_readback_hex", "")) == NATIVE_ABORT_HEX and str(native_abort.get("native_abort_readback_sha256", "")) == NATIVE_ABORT_SHA256 and native_abort.get("native_abort_readback_matches_contract") is True and native_abort.get("native_abort_payload_written_fully") is True and native_abort.get("native_abort_flush_and_fsync_completed") is True  # 同时要求请求、长度、hex、摘要、完整写、磁盘同步和回读全部成立。


def snapshots_stable(paths: list[Path]) -> dict[str, dict[str, Any]]:  # 接收权威运行文件列表并返回经两秒窗口确认不变的快照。
    first = {str(path): file_snapshot(path) for path in paths}  # 在窗口起点同步采集所有目标的存在性、大小和修改时刻。
    time.sleep(STABILITY_WAIT_SECONDS)  # 等待两秒以排除 MAPDL 退出后页尾或文件系统延迟刷新。
    second = {str(path): file_snapshot(path) for path in paths}  # 在窗口终点对同一路径集合再次采集快照。
    require(first == second, f"A0 权威文件在两秒终结窗口内仍变化：{[(key, first[key], second[key]) for key in first if first[key] != second[key]]}")  # 任一存在性、大小或时刻变化都拒绝发布。
    return second  # 返回稳定窗口终点快照供与监控 final 逐项比对。


def validate_monitor_chain(prepared: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:  # 接收准备与 runtime 链并返回由 JSONL 独立复算的稳定退出证据。
    run_dir = Path(str(prepared["manifest_path"])).parent.resolve()  # 从已验证准备上下文恢复唯一运行根。
    qa_dir = run_dir / "qa"  # 定位准备已建立的 QA 证据目录。
    claim_path = qa_dir / "runtime_a0_monitor_claim.json"  # 定位监控器在采样前排他写出的认领原件。
    samples_path = qa_dir / "runtime_a0_monitor_samples.jsonl"  # 定位每个十秒样本立即刷新的只追加流水。
    final_path = qa_dir / "runtime_a0_monitor_final.json"  # 定位进程树退出后的唯一监控终态。
    lease_release_path = run_dir / HOST_LEASE_RELEASE_RELATIVE  # 定位监控对原租约字节封存并成功释放的唯一证据。
    claim = read_json(claim_path)  # 独立读取监控认领原件。
    final = read_json(final_path)  # 独立读取监控终态原件。
    samples = read_jsonl(samples_path)  # 逐行解析全部监控样本供独立复算。
    run_name = run_dir.name  # 冻结当前运行名供监控两段身份比较。
    jobname = str(prepared["jobname"])  # 引用已闭合的唯一 jobname。
    require(claim.get("schema_version") == 1 and final.get("schema_version") == 1, "A0 监控 claim 或 final schema 版本不是 1")  # 只允许已审查的第一版契约。
    require(claim.get("status") == "A0_MONITOR_CLAIMED" and claim.get("run_name") == final.get("run_name") == run_name and claim.get("jobname") == final.get("jobname") == jobname, "A0 监控认领或终态身份错误")  # 关闭跨运行监控工件复制。
    require(claim.get("runtime_launch_sha256") == runtime["launch_sha256"] and claim.get("runtime_launch_claim_sha256") == runtime["claim_sha256"] and claim.get("runtime_process_identity_sha256") == runtime["identity_sha256"], "A0 监控认领引用的 runtime 三段摘要链断裂")  # 证明监控精确附着本次启动。
    require(claim.get("monitor_spawn_claim_sha256") == runtime["monitor_spawn_claim_sha256"] and claim.get("host_lease_sha256") == runtime["host_lease_sha256"], "A0 监控 claim 引用的自动创建认领或主机租约摘要不一致")  # 证明 claim 来自同一启动器创建链与同一租约。
    require(int(claim.get("monitor_pid", 0)) == int(runtime["monitor_launch"].get("monitor_pid", -1)) and int(claim.get("launcher_pid", 0)) == int(runtime["monitor_spawn_claim"].get("launcher_pid", -1)), "A0 监控 claim 的 monitor PID 或父 launcher PID 与自动创建链不一致")  # 关闭人工补挂或跨启动器冒领。
    require(claim.get("manifest_sha256") == sha256_file(Path(str(prepared["manifest_path"])), require_stable=True) and claim.get("prepared_ledger_sha256") == prepared["prepared_ledger_sha256"], "A0 监控认领引用的 manifest 或准备账本摘要不一致")  # 将监控与已执行输入字节闭合。
    require(int(claim.get("expected_equation_count", 0)) == EXPECTED_EQUATION_COUNT and claim.get("hard_stops") == runtime["launch"].get("monitor_hard_stops"), "A0 监控方程数或资源硬门与启动合同分叉")  # 禁止监控后事后更改阈值。
    require(claim.get("native_abort_payload_sha256") == NATIVE_ABORT_SHA256 and claim.get("native_abort_only") is True and claim.get("force_termination_allowed") is False, "A0 监控认领未固定十字节原生 ABT 且禁止强制处置")  # 固定硬事件后唯一安全路径。
    require(claim.get("postlaunch_unrelated_solver_process_is_hard_event") is True and claim.get("other_process_disposition_allowed") is False and isinstance(claim.get("initial_unrelated_solver_hard_events"), list), "A0 监控 claim 未将启动后无关求解器固定为硬事件且禁止处置其他进程")  # 闭合新 P1 独占运行政策。
    require(claim.get("default_cnvtol_relaxation_messages_are_hard_events") is True, "A0 监控认领未将 CNVTOL 忽略/放宽消息固定为硬事件")  # 从监控策略层关闭失效开放路径。
    monitor_script = Path(str(claim.get("monitor_script", ""))).resolve()  # 读取监控认领声明的实际执行脚本绝对路径。
    require(monitor_script.is_file() and monitor_script == (run_dir / str(prepared["manifest"]["runtime_monitor_script"])).resolve(), "A0 监控认领不指向本运行冻结监控器")  # 阻断外部或错版脚本冒充。
    require(claim.get("monitor_script_sha256") == sha256_file(monitor_script, require_stable=True) == prepared["manifest"].get("runtime_monitor_script_sha256"), "A0 监控脚本、claim 与 manifest 摘要不一致")  # 闭合实际监控代码字节身份。
    require(isinstance(claim.get("initial_related_processes"), list) and bool(claim.get("initial_related_processes")), "A0 监控认领时没有可信本 job 进程")  # 拒绝事后空附着冒充持续监控。
    require(final.get("status") in {NATURAL_MONITOR_STATUS, HARD_MONITOR_STATUS, BLOCKED_MONITOR_STATUS}, f"A0 监控 final 状态未知：{final.get('status')}")  # 只接受冻结的三种退出结果。
    require(final.get("status") != BLOCKED_MONITOR_STATUS and final.get("monitor_block_reason") is None, f"A0 监控 final 未稳定：{final.get('monitor_block_reason')}")  # 用户要求只在监控 final 稳定后运行，阻断状态不发布。
    require(final.get("stable_exit_confirmed") is True and final.get("host_lease_release_allowed") is True and final.get("retained_for_manual_audit") is False, "A0 监控 final 未显式证明稳定空进程退出、允许释放租约且无需人工保留")  # 只在新 schema 完整终态闭合后继续。
    require(final.get("monitor_claim_sha256") == sha256_file(claim_path, require_stable=True), "A0 监控 final 引用的 claim 摘要不一致")  # 闭合监控认领到终态的不可覆盖链。
    require(runtime["monitor_attachment"].get("monitor_claim_sha256") == sha256_file(claim_path, require_stable=True), "A0 启动器 attachment 握手引用的监控 claim 摘要不一致")  # 闭合启动器等待成功与监控实际认领原件。
    require(Path(str(final.get("samples_path", ""))).resolve() == samples_path.resolve() and final.get("samples_sha256") == sha256_file(samples_path, require_stable=True), "A0 监控 final 引用的 JSONL 路径或摘要不一致")  # 关闭样本流替换或截断风险。
    require(int(final.get("sample_count", 0)) == len(samples) and len(samples) >= 2, "A0 监控 final 样本数不能由 JSONL 复算或少于两个")  # 至少两样本才可证明连续稳定退出。
    require([int(sample.get("sample_index", -1)) for sample in samples] == list(range(1, len(samples) + 1)), "A0 监控 JSONL 样本索引不从 1 连续递增")  # 阻断丢样、重复或重排。
    require(all(sample.get("schema_version") == 1 for sample in samples), "A0 监控 JSONL 存在非 schema 1 样本")  # 样本契约不得在同一流水中混用。
    sample_equations = [int(value) for sample in samples for value in sample.get("new_equation_counts", [])]  # 按样本与日志发现顺序独立重建全部方程数观测。
    sample_hard_events = [event for sample in samples for event in sample.get("new_hard_events", [])]  # 按样本顺序独立重建全部硬事件对象。
    require(sample_equations == final.get("observed_equation_counts") and sorted(set(sample_equations)) == final.get("unique_equation_counts"), "A0 监控 final 方程数序列不能由 JSONL 逐项复算")  # 阻断摘要删改或重排秩证据。
    require(sample_hard_events == final.get("hard_events"), "A0 监控 final 硬事件列表不能由 JSONL 逐项复算")  # 阻断终态遗漏或事后添加硬事件。
    available_ram = [int(sample["physical_memory_available_bytes"]) for sample in samples]  # 提取全部样本的可用物理内存字节数。
    disk_free = [int(sample["disk_free_bytes"]) for sample in samples]  # 提取全部样本的运行盘空余字节数。
    related_rss = [int(sample["related_rss_bytes"]) for sample in samples]  # 提取全部本 job 进程树驻留工作集字节数。
    require(min(available_ram) == int(final.get("minimum_physical_memory_available_bytes", -1)) and min(disk_free) == int(final.get("minimum_disk_free_bytes", -1)) and max(related_rss) == int(final.get("maximum_related_rss_bytes", -1)), "A0 监控 final 资源极值不能由 JSONL 复算")  # 关闭资源事件与摘要分叉。
    require(final.get("terminate_called") is False and final.get("kill_called") is False and final.get("send_signal_called") is False, "A0 监控 final 显示调用了禁止的主动进程处置")  # 任一强制动作都使运行不符合安全合同。
    require(final.get("final_related_processes") == [], "A0 监控 final 仍记录本 job 进程")  # 只有进程树终态为空才可进入文件解析。
    require(all(sample.get("related_processes") == [] for sample in samples[-2:]), "A0 监控 JSONL 最后两个样本不是连续空进程树")  # 独立覆盖单点包装器交接误判。
    output_path = Path(str(prepared["output_path"])).resolve()  # 引用已从 manifest -o 验证的权威 OUT 路径。
    solver_dir = Path(str(prepared["solver_dir"])).resolve()  # 引用已验证的求解工作目录。
    error_path = solver_dir / f"{jobname}.err"  # 按唯一 jobname 构造原生 ERR 路径。
    mntr_path = solver_dir / f"{jobname}.mntr"  # 按唯一 jobname 构造原生已接受步 MNTR 路径。
    lock_path = solver_dir / f"{jobname}.lock"  # 按唯一 jobname 构造求解运行 lock 路径。
    stable = snapshots_stable([output_path, error_path, mntr_path, lock_path])  # 在进程树已空后再对 OUT/ERR/MNTR/lock 执行独立两秒稳定门。
    require(stable[str(output_path)] == final.get("final_out_file") and stable[str(error_path)] == final.get("final_err_file") and stable[str(mntr_path)] == final.get("final_mntr_file") and stable[str(lock_path)] == final.get("final_lock_file"), "A0 当前 OUT/ERR/MNTR/lock 不再等于监控 final 提交快照")  # 任一事后变化都使冻结候选失效。
    require(final.get("final_lock_file") == {"exists": False, "size_bytes": 0, "mtime_ns": None} and not lock_path.exists(), "A0 job lock 在监控 final 或当前文件系统中仍存在")  # 用户要求 PID 和锁均消失才允许终结。
    require(all(sample.get("lock_file") == {"exists": False, "size_bytes": 0, "mtime_ns": None} for sample in samples[-2:]), "A0 监控 JSONL 最后两个样本未连续证明 lock 消失")  # 独立覆盖单次锁观测竞态。
    last_sizes = [(int(sample["out_file"]["size_bytes"]), int(sample["err_file"]["size_bytes"]), int(sample["mntr_file"]["size_bytes"])) for sample in samples[-2:]]  # 重建最后两个样本的三文件大小元组。
    require(last_sizes[0] == last_sizes[1], f"A0 监控 JSONL 最后两个样本的 OUT/ERR/MNTR 大小不稳定：{last_sizes}")  # 不单依赖 final 快照声明稳定。
    hard_events = list(final.get("hard_events", []))  # 引用已由 JSONL 逐项重建的有序硬事件列表。
    require((final.get("status") == HARD_MONITOR_STATUS) == bool(hard_events), "A0 监控 final 硬停状态与硬事件列表不一致")  # 阻断无事件硬停或有事件自然退出的摘要矛盾。
    native_abort = final.get("native_abort")  # 读取监控器完整原生 ABT 动作和回读证据对象。
    require(isinstance(native_abort, dict), "A0 监控 final 缺少 native_abort 对象")  # 无论是否请求都必须显式披露动作合同。
    abort_valid = native_abort_contract_valid(native_abort)  # 按十字节、hex、摘要、写盘和回读全门独立计算有效性。
    if final.get("status") == NATURAL_MONITOR_STATUS:  # 无硬事件自然退出时不应存在被请求的 ABT。
        require(not abort_valid and native_abort.get("request_contract_satisfied") is False, "A0 自然监控终态却记录有效原生 ABT 请求")  # 阻断控制器中止被冒充为自然完成。
    require(final.get("result_use") == "A0_EXECUTION_MONITOR_ONLY_EXTERNAL_STATIC_QA_REQUIRED_NO_MODAL_OR_PRODUCTION_CLAIM", "A0 监控 final 用途边界漂移")  # 确保监控退出本身没有声称静力通过。
    host_lease_release = final.get("host_lease_release")  # 读取监控 final 中对租约封存与释放动作的摘要。
    require(isinstance(host_lease_release, dict) and host_lease_release.get("host_lease_removed") is True and host_lease_release.get("released_by_monitor") is True, "A0 监控 final 未证明租约已由监控器释放")  # 禁止租约仍保留或由未知主体删除的运行封板。
    require(Path(str(host_lease_release.get("archive_path", ""))).resolve() == lease_release_path.resolve() and host_lease_release.get("archive_sha256") == sha256_file(lease_release_path, require_stable=True), "A0 监控 final 引用的租约释放封存路径或摘要不一致")  # 闭合 final 到租约原文封存工件。
    lease_release = read_json(lease_release_path)  # 独立读取监控在删除全局租约前写出的完整封存。
    require(lease_release.get("schema_version") == 1 and lease_release.get("status") == "HOST_LEASE_ARCHIVED_AND_RELEASED_BY_A0_MONITOR" and lease_release.get("run_name") == run_name and lease_release.get("jobname") == jobname, "A0 租约释放封存 schema、状态或身份错误")  # 固定封存属于当前运行与 job。
    require(lease_release.get("monitor_final_status") == final.get("status") and lease_release.get("host_lease_path") == str(HOST_LEASE_PATH) and lease_release.get("host_lease_sha256") == runtime["host_lease_sha256"], "A0 租约释放封存的监控终态、路径或原租约摘要不一致")  # 证明删除前两次核验的是本运行原租约。
    lease_payload = lease_release.get("host_lease_payload")  # 读取封存中完整保留的原全局租约对象。
    require(isinstance(lease_payload, dict) and lease_payload.get("status") == "A0_EXCLUSIVE_HOST_LEASE_HELD" and lease_payload.get("run_name") == run_name and lease_payload.get("jobname") == jobname and int(lease_payload.get("launcher_pid", 0)) == int(runtime["monitor_spawn_claim"].get("launcher_pid", -1)), "A0 租约释放封存中的原租约持有者身份错误")  # 闭合原租约、启动器与监控自动创建链。
    require(lease_release.get("active_process_disposition_allowed") is False and lease_release.get("terminate_called") is False and lease_release.get("kill_called") is False and lease_release.get("send_signal_called") is False and not HOST_LEASE_PATH.exists(), "A0 租约释放封存的无强制处置证据或当前租约消失事实不完整")  # 确保释放仅修改专用租约路径且没有处置进程。
    return {"status": str(final["status"]), "claim_sha256": sha256_file(claim_path, require_stable=True), "samples_sha256": sha256_file(samples_path, require_stable=True), "final_sha256": sha256_file(final_path, require_stable=True), "sample_count": len(samples), "minimum_physical_memory_available_bytes": min(available_ram), "minimum_disk_free_bytes": min(disk_free), "maximum_related_rss_bytes": max(related_rss), "observed_equation_counts": sample_equations, "unique_equation_counts": sorted(set(sample_equations)), "hard_events": hard_events, "hard_event_count": len(hard_events), "native_abort": native_abort, "native_abort_contract_valid": abort_valid, "stable_exit_confirmed": True, "host_lease_release_allowed": True, "retained_for_manual_audit": False, "host_lease_release": host_lease_release, "host_lease_release_sha256": sha256_file(lease_release_path, require_stable=True), "terminate_called": False, "kill_called": False, "send_signal_called": False, "final_related_processes": [], "files_stable_at_monitor_commit_and_finalizer": True, "output_path": output_path, "error_path": error_path, "mntr_path": mntr_path, "lock_path": lock_path, "stable_snapshots": stable}  # 返回可直接纳入最终审计的自动监控、租约释放、资源、秩、硬事件、ABT 和稳定退出证据。


def read_latin1_optional(path: Path) -> tuple[bool, str]:  # 接收可能缺失的 MAPDL 文本路径并返回存在性与一一字节解码文本。
    if not path.is_file():  # 硬事件或早期启动失败可能在某个原生日志创建前结束。
        return False, ""  # 返回显式缺失而不伪造空文件。
    return True, path.read_bytes().decode("latin-1", errors="strict")  # Latin-1 一一映射所有原始字节，保持 ASCII 求解器签名。


def extract_message_blocks(text_value: str, source: str) -> list[dict[str, str]]:  # 接收完整日志和来源标签，返回真实 MAPDL 消息块的级别、摘要和有限摘录。
    matches = list(MESSAGE_HEADER_PATTERN.finditer(text_value))  # 一次定位全部 WARNING/ERROR/FATAL 标题及其原文位置。
    blocks: list[dict[str, str]] = []  # 初始化保持日志顺序的消息块审计列表。
    for index, match in enumerate(matches):  # 按原文顺序为每个标题确定到下一标题前的消息范围。
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text_value)  # 末块延伸到文件末尾，其余延伸到下一标题起点。
        raw_block = text_value[match.start():min(block_end, match.start() + 4_096)]  # 每块最多保留四千零九十六字符，足以覆盖原生消息且避免后续输入回显污染。
        normalized = " ".join(raw_block.split())  # 把求解器自动换行与多空格压缩为单空格供稳定分类。
        blocks.append({"source": source, "severity": str(match.group(1)).upper(), "sha256": sha256_bytes(raw_block.encode("latin-1")), "excerpt": normalized[:640]})  # 保存来源、级别、完整块摘要和最多六百四十字摘录。
    return blocks  # 返回可用于 CNVTOL、主元、致命和普通错误分类的有序列表。


def parse_solver_logs(output_exists: bool, output_text: str, error_exists: bool, error_text: str) -> dict[str, Any]:  # 接收 OUT/ERR 存在性与文本并返回方程、主元、迭代、切步、阶段和消息证据。
    combined_text = output_text + "\n" + error_text  # 以单一换行合并两份原生日志，仅用于跨来源签名统计。
    output_blocks = extract_message_blocks(output_text, "OUT")  # 独立切分 OUT 消息块，避免输入回显短语被当成真实事件。
    error_blocks = extract_message_blocks(error_text, "ERR")  # 独立切分 ERR 消息块供与 OUT 交叉审计。
    message_blocks = output_blocks + error_blocks  # 合并两来源已限定范围的真实消息块。
    equations_out = [int(value) for value in EQUATION_PATTERN.findall(output_text)]  # 按 OUT 原文顺序提取全部组装方程数。
    equations_err = [int(value) for value in EQUATION_PATTERN.findall(error_text)]  # 按 ERR 原文顺序提取可能复制或独立记录的方程数。
    pivots_out = [float(value) for value in PIVOT_PATTERN.findall(output_text)]  # 按 OUT 原文顺序提取全部有符号最小主元。
    pivots_err = [float(value) for value in PIVOT_PATTERN.findall(error_text)]  # 按 ERR 原文顺序提取可能独立记录的有符号主元。
    require(all(math.isfinite(value) for value in pivots_out + pivots_err), "A0 OUT/ERR 含非有限最小主元数词")  # 禁止 NaN 或无穷值进入最小值与符号门。
    cnvtol_messages: list[dict[str, str]] = []  # 初始化 CNVTOL 被忽略或内部放宽的真实消息块列表。
    bad_pivot_messages: list[dict[str, str]] = []  # 初始化明确小、零、负主元消息块列表。
    fatal_messages: list[dict[str, str]] = []  # 初始化原生 FATAL 消息块列表。
    for block in message_blocks:  # 对每个已隔离输入回显的真实消息块执行硬事件分类。
        excerpt = str(block["excerpt"])  # 读取已规范空白的有限消息摘录。
        if str(block["severity"]) == "FATAL":  # 标题级别直接为 FATAL 时无需依赖后续短语。
            fatal_messages.append(block)  # 保存致命块供硬事件和人工定位。
        for pattern in CNVTOL_PATTERNS:  # 逐个检查忽略、内部重置和显式自动放宽模式。
            if pattern.search(excerpt) is not None:  # 只有真实消息块摘录命中才视为 CNVTOL 政策失效。
                cnvtol_messages.append({**block, "pattern": pattern.pattern})  # 保存来源、摘要和命中模式，且不依赖输入说明。
                break  # 同一消息块只归入一条 CNVTOL 失效记录。
        for kind, pattern in BAD_PIVOT_PATTERNS:  # 逐类检查小、零和负主元原生短语。
            if pattern.search(excerpt) is not None:  # 只有真实消息块内命中才记录显式坏主元。
                bad_pivot_messages.append({**block, "kind": kind})  # 保存稳定类别和原块证据。
                break  # 同一块只记录第一个最具体的坏主元类别。
    completed_steps = [{"load_step": int(load_step), "substep": int(substep)} for load_step, substep in COMPLETED_PATTERN.findall(output_text)]  # 按 OUT 原文顺序记录全部已接受子步。
    rejected_steps = [{"load_step": int(match.group(1)), "substep": int(match.group(2)), "cumulative_iterations": int(match.group(3)) if match.group(3) is not None else None, "text_offset": int(match.start())} for match in REJECTED_PATTERN.finditer(output_text)]  # 记录全部未完成尝试与原文位置。
    bisections = [{"number": int(match.group(1)), "new_time_increment": float(match.group(2)), "text_offset": int(match.start())} for match in BISECTION_PATTERN.finditer(output_text)]  # 记录全部 AUTOTS 切步编号、新增量和原文位置。
    require(all(math.isfinite(float(item["new_time_increment"])) and float(item["new_time_increment"]) > 0.0 for item in bisections), "A0 OUT 含非有限或非正切步增量")  # 阻断破损数词进入切步路径结论。
    iteration_numbers = [int(value) for value in ITERATION_PATTERN.findall(output_text)]  # 按 OUT 原文顺序提取全部已完成平衡迭代编号。
    natural_matches: list[dict[str, str]] = []  # 初始化自然 NCNV 或超迭代上限签名列表。
    for pattern in NATURAL_NONCONVERGENCE_PATTERNS:  # 按冻结签名集逐项搜索合并原生日志。
        match = pattern.search(combined_text)  # 查找当前签名的首个真实命中位置。
        if match is not None:  # 只对实际命中的签名形成分类证据。
            natural_matches.append({"pattern": pattern.pattern, "excerpt": " ".join(combined_text[max(0, match.start() - 120):match.end() + 240].split())[:480]})  # 保存稳定模式和有限上下文。
    abt_matches: list[dict[str, str]] = []  # 初始化 MAPDL 承认 ABT 终止的签名列表。
    for pattern in ABT_PATTERNS:  # 按冻结的用户 ABT 请求与终止原因签名逐项搜索。
        match = pattern.search(combined_text)  # 查找当前 ABT 签名的首个命中位置。
        if match is not None:  # 只有 MAPDL 原文显式承认才记录 ABT 终止。
            abt_matches.append({"pattern": pattern.pattern, "excerpt": " ".join(combined_text[max(0, match.start() - 120):match.end() + 240].split())[:480]})  # 保存签名与有限原文上下文。
    equation_counts = equations_out + equations_err  # 合并 OUT 与 ERR 方程数观测供完整性与漂移检查。
    pivots = pivots_out + pivots_err  # 合并 OUT 与 ERR 有符号主元供有限性与正值检查。
    hard_events: list[dict[str, Any]] = []  # 初始化由终结器对完整日志重建的硬事件列表。
    for equation_count in equation_counts:  # 逐个检查直接求解器每次组装的独立方程数。
        if equation_count != EXPECTED_EQUATION_COUNT:  # 任一数量漂移都表示拓扑、约束或激活状态偏离批准输入。
            hard_events.append({"kind": "EQUATION_COUNT_DRIFT", "observed": equation_count, "expected": EXPECTED_EQUATION_COUNT})  # 记录异常秩和冻结期望值。
    for pivot in pivots:  # 逐个检查有符号稀疏求解器最小主元。
        if pivot <= 0.0:  # 只有数值零或负数直接触发，正但很小的值由 MAPDL 明确消息判定。
            hard_events.append({"kind": "NONPOSITIVE_SPARSE_SOLVER_PIVOT", "observed": pivot, "threshold": 0.0})  # 记录非正主元与零门限。
    hard_events.extend({"kind": "MAPDL_FATAL", **message} for message in fatal_messages)  # 把每个原生 FATAL 消息块纳入重建硬事件。
    hard_events.extend({"kind": str(message["kind"]), **message} for message in bad_pivot_messages)  # 把每个明确小、零或负主元块纳入硬事件。
    hard_events.extend({"kind": "CNVTOL_POLICY_VIOLATION", **message} for message in cnvtol_messages)  # 把 CNVTOL 忽略或放宽块纳入专项硬事件。
    error_blocks_count = sum(1 for block in message_blocks if str(block["severity"]) == "ERROR")  # 统计 OUT 与 ERR 中全部原生 ERROR 消息块数。
    warning_blocks_count = sum(1 for block in message_blocks if str(block["severity"]) == "WARNING")  # 统计 OUT 与 ERR 中全部原生 WARNING 消息块数。
    return {"output_exists": output_exists, "error_exists": error_exists, "output_size_bytes": len(output_text.encode("latin-1")), "error_size_bytes": len(error_text.encode("latin-1")), "output_sha256": sha256_bytes(output_text.encode("latin-1")) if output_exists else None, "error_sha256": sha256_bytes(error_text.encode("latin-1")) if error_exists else None, "equation_counts_out": equations_out, "equation_counts_err": equations_err, "equation_counts": equation_counts, "unique_equation_counts": sorted(set(equation_counts)), "pivots_out": pivots_out, "pivots_err": pivots_err, "minimum_pivots": pivots, "minimum_reported_pivot": min(pivots) if pivots else None, "iteration_numbers": iteration_numbers, "completed_equilibrium_iteration_line_count": len(iteration_numbers), "maximum_equilibrium_iteration_number": max(iteration_numbers) if iteration_numbers else None, "completed_steps": completed_steps, "rejected_steps": rejected_steps, "bisections": bisections, "bisection_count": len(bisections), "message_blocks": message_blocks, "warning_block_count": warning_blocks_count, "error_block_count": error_blocks_count, "fatal_messages": fatal_messages, "bad_pivot_messages": bad_pivot_messages, "cnvtol_policy_messages": cnvtol_messages, "natural_nonconvergence_matches": natural_matches, "abt_termination_matches": abt_matches, "hard_events": hard_events, "run_completed_marker": "RUN COMPLETED" in combined_text.upper(), "normal_nosave_exit_marker": "EXIT MAPDL WITHOUT SAVING DATABASE" in combined_text.upper(), "error_summaries": [int(value) for value in ERROR_COUNT_PATTERN.findall(combined_text)], "warning_summaries": [int(value) for value in WARNING_COUNT_PATTERN.findall(combined_text)]}  # 返回可独立复查的完整求解日志证据包。


def parse_mntr_text(text_value: str) -> list[dict[str, float | int]]:  # 接收 MAPDL MNTR 全文并返回每个已接受子步的七项控制与时间字段。
    rows: list[dict[str, float | int]] = []  # 初始化保持原生已接受子步顺序的行列表。
    for line in text_value.splitlines():  # 按原生 MNTR 物理行遍历标题、空行和数值行。
        match = MNTR_ROW_PATTERN.match(line)  # 尝试把当前行识别为五整数加两时间列的数据行。
        if match is not None:  # 只有完整七字段前缀的真实已接受步进入结果。
            row = {"load_step": int(match.group(1)), "substep": int(match.group(2)), "attempt": int(match.group(3)), "iterations": int(match.group(4)), "total_iterations": int(match.group(5)), "increment": float(match.group(6)), "total_time": float(match.group(7))}  # 把五个控制列转为整数、增量与累计时间转为浮点数。
            require(all(math.isfinite(float(value)) for value in row.values()), f"A0 MNTR 数据行含非有限数：{line}")  # 禁止 NaN、无穷或破损数词进入阶段门。
            rows.append(row)  # 保存当前已接受子步及其尝试、迭代和时间路径。
    return rows  # 返回可与 OUT completed 标志和准备 NSUBST 交叉复核的有序记录。


def analyze_static_sequence(mntr_exists: bool, mntr_text: str, logs: dict[str, Any]) -> dict[str, Any]:  # 接收 MNTR 存在性、文本和日志证据并返回 LS1/LS2 已接受路径审计。
    rows = parse_mntr_text(mntr_text) if mntr_exists else []  # 仅当原生 MNTR 存在时解析已接受步，失败路径缺失时保留空列表。
    ls1_rows = [row for row in rows if int(row["load_step"]) == 1]  # 提取第一载荷步的全部已接受斜坡子步。
    ls2_rows = [row for row in rows if int(row["load_step"]) == 2]  # 提取第二载荷步的已接受零增量保持子步。
    other_rows = [row for row in rows if int(row["load_step"]) not in {1, 2}]  # 提取任何超出 A0 两步静力合同的异常行。
    completed_ls1 = [int(item["substep"]) for item in logs["completed_steps"] if int(item["load_step"]) == 1]  # 从 OUT 提取 LS1 已接受子步编号序列。
    completed_ls2 = [int(item["substep"]) for item in logs["completed_steps"] if int(item["load_step"]) == 2]  # 从 OUT 提取 LS2 已接受子步编号序列。
    ls1_increments = [float(row["increment"]) for row in ls1_rows]  # 提取 LS1 每个真实已接受伪时间增量。
    ls1_times = [float(row["total_time"]) for row in ls1_rows]  # 提取 LS1 每个已接受累计时间。
    ls1_checks = {"mntr_present": mntr_exists, "accepted_count_within_20_to_200": LS1_MIN_ACCEPTED_SUBSTEPS <= len(ls1_rows) <= LS1_MAX_ACCEPTED_SUBSTEPS, "substeps_sequential_from_one": [int(row["substep"]) for row in ls1_rows] == list(range(1, len(ls1_rows) + 1)), "attempts_and_iterations_positive": all(int(row["attempt"]) >= 1 and int(row["iterations"]) >= 1 and int(row["total_iterations"]) >= 1 for row in ls1_rows), "increments_positive": bool(ls1_increments) and all(value > 0.0 for value in ls1_increments), "times_strictly_increasing": bool(ls1_times) and all(ls1_times[index] > (0.0 if index == 0 else ls1_times[index - 1]) for index in range(len(ls1_times))), "final_time_one": bool(ls1_times) and math.isclose(ls1_times[-1], 1.0, rel_tol=0.0, abs_tol=TIME_ABSOLUTE_TOLERANCE), "increment_sum_one": bool(ls1_increments) and math.isclose(sum(ls1_increments), 1.0, rel_tol=0.0, abs_tol=1.0e-4), "out_completed_matches_mntr": completed_ls1 == [int(row["substep"]) for row in ls1_rows]}  # 以 MNTR 和 OUT 交叉证明 LS1 在批准子步边界内到达 time=1。
    ls1_checks["passed"] = all(ls1_checks.values())  # 只有 LS1 全部子门同时成立才承认斜坡终点已接受。
    ls2_row = ls2_rows[0] if len(ls2_rows) == 1 else None  # 只有 LS2 恰好一行时取得唯一零增量保持记录。
    ls2_checks = {"mntr_present": mntr_exists, "exactly_one_accepted_row": len(ls2_rows) == 1, "substep_one": ls2_row is not None and int(ls2_row["substep"]) == 1, "attempt_one_without_cutback": ls2_row is not None and int(ls2_row["attempt"]) == 1, "iterations_positive": ls2_row is not None and int(ls2_row["iterations"]) >= 1 and int(ls2_row["total_iterations"]) >= 1, "increment_0_001": ls2_row is not None and math.isclose(float(ls2_row["increment"]), 0.001, rel_tol=0.0, abs_tol=1.0e-8), "final_time_1_001": ls2_row is not None and math.isclose(float(ls2_row["total_time"]), 1.001, rel_tol=0.0, abs_tol=TIME_ABSOLUTE_TOLERANCE), "out_completed_exactly_ls2_substep_one": completed_ls2 == [1], "no_load_steps_beyond_two": not other_rows}  # 证明 LS2 在 AUTOTS OFF 下以唯一子步保持到 time=1.001。
    ls2_checks["passed"] = all(ls2_checks.values())  # 只有 LS2 全部子门同时成立才承认零增量保持点已接受。
    return {"mntr_exists": mntr_exists, "row_count": len(rows), "rows": rows, "ls1": {"accepted_row_count": len(ls1_rows), "rows": ls1_rows, "final_time": ls1_times[-1] if ls1_times else None, "total_equilibrium_iterations_on_accepted_rows": sum(int(row["iterations"]) for row in ls1_rows), "checks": ls1_checks}, "ls2": {"accepted_row_count": len(ls2_rows), "rows": ls2_rows, "final_time": float(ls2_row["total_time"]) if ls2_row is not None else None, "equilibrium_iterations": int(ls2_row["iterations"]) if ls2_row is not None else None, "checks": ls2_checks}, "other_load_step_rows": other_rows, "out_completed_ls1_substeps": completed_ls1, "out_completed_ls2_substeps": completed_ls2, "all_checks_passed": bool(ls1_checks["passed"]) and bool(ls2_checks["passed"])}  # 返回完整接受路径、迭代统计和两步通过布尔门。


def parse_scalar_fields(text_value: str, labels: tuple[str, ...]) -> tuple[dict[str, float], list[str]]:  # 接收 MAPDL 摘要文本与必需标签并返回唯一有限数值和全部解析错误。
    values: dict[str, float] = {}  # 初始化已成功解析的标签到浮点值映射。
    errors: list[str] = []  # 初始化缺失、重复、非数词或非有限错误列表。
    for label in labels:  # 按冻结字段顺序逐个解析并保留完整错误集。
        pattern = re.compile(rf"(?<![A-Z0-9_]){re.escape(label)}\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 用左边界避免 LS2 误命中 LS2_CNVG 等更长标签。
        matches = pattern.findall(text_value)  # 收集当前标签全部数值文本，禁止静默选择最后一个。
        if len(matches) != 1:  # 缺失或重复均破坏一字段一真值合同。
            errors.append(f"{label}_MATCH_COUNT_{len(matches)}")  # 保存可机器分类的标签和实际匹配数。
            continue  # 转入下一字段，一次披露所有破损标签。
        try:  # 尝试将已匹配的 MAPDL 数词转为双精度浮点数。
            value = float(matches[0])  # 转换整数、小数或科学计数法文本。
        except ValueError:  # 尽管正则已限定数词，仍对运行库转换异常 fail-closed。
            errors.append(f"{label}_FLOAT_PARSE_ERROR")  # 保存字段级转换失败原因。
            continue  # 继续检查其他标签而不发布通过。
        if not math.isfinite(value):  # NaN 与无穷值不得进入能量、质量或反力比较。
            errors.append(f"{label}_NONFINITE")  # 保存非有限字段原因。
            continue  # 继续收集其他错误以缩短审查轮次。
        values[label] = value  # 保存已唯一匹配且有限的数值。
    return values, errors  # 返回可用值与不会因单项错误丢失其他线索的完整错误集。


def parse_history_file(path: Path) -> tuple[list[list[float]], list[str]]:  # 接收 LS1 六列能量历程路径并返回有限数值行与解析错误。
    if not path.is_file():  # 未到达外部 QA 阶段的失败运行允许历程完全缺失。
        return [], ["HISTORY_FILE_MISSING"]  # 以明确错误而非异常表示缺失，使自然失败仍能封存。
    rows: list[list[float]] = []  # 初始化保持 MAPDL 结果集顺序的六列数值行。
    errors: list[str] = []  # 初始化列数、数词与有限性错误列表。
    with path.open("r", encoding="utf-8", errors="strict", newline="") as handle:  # 以严格 UTF-8 和标准 CSV 换行语义只读打开。
        for row_number, raw_row in enumerate(csv.reader(handle), start=1):  # 按一基行号遍历每个 *VWRITE 结果集记录。
            if len(raw_row) != 6:  # 合同要求 LSTP、SBST、TIME、SENE、STEN、RATIO 恰好六列。
                errors.append(f"ROW_{row_number}_COLUMN_COUNT_{len(raw_row)}")  # 保存破损行号和实际列数。
                continue  # 不把破损行混入数值路径，继续收集后续错误。
            try:  # 尝试将六个去空白单元格转为浮点数。
                values = [float(cell.strip()) for cell in raw_row]  # 按固定列顺序转换完整当前行。
            except ValueError:  # 任一单元格不是有效浮点文本时记录行级错误。
                errors.append(f"ROW_{row_number}_FLOAT_PARSE_ERROR")  # 保存可定位的数词错误。
                continue  # 继续审查其他行而不冒充完整历程。
            if not all(math.isfinite(value) for value in values):  # 任一 NaN 或无穷值都使当前结果集不可用。
                errors.append(f"ROW_{row_number}_NONFINITE")  # 保存非有限行号。
                continue  # 继续检查后续行并保留完整问题图。
            rows.append(values)  # 保存已通过列数、数词与有限性检查的历程行。
    return rows, errors  # 返回所有可解析行和完整错误列表。


def analyze_static_outputs(run_dir: Path, jobname: str) -> dict[str, Any]:  # 接收已退出 A0 运行与 jobname，返回内部门、能量、质量、反力和结果文件审计。
    solver_dir = run_dir / "solver"  # 定位已由准备与启动参数闭合的求解工作目录。
    gate_path = solver_dir / "c10_gate_status.txt"  # 定位 APDL 内部静力门状态原件。
    static_path = solver_dir / "c10_static_energy_mass_reaction.txt"  # 定位 LS1/LS2、能量、质量和竖向反力机器摘要。
    history_path = solver_dir / "c10_ls1_energy_history.csv"  # 定位 LS1 全部已接受子步能量历程。
    result_path = solver_dir / f"{jobname}.rst"  # 定位求解器结果文件，成功路径必须存在且不作生产输入。
    equilibrium_db_path = solver_dir / f"{jobname}_eq.db"  # 定位全部内部静力门通过后唯一保存的平衡数据库。
    stable = snapshots_stable([gate_path, static_path, history_path, result_path, equilibrium_db_path])  # 对所有静力判据与成功结果文件执行两秒独立稳定门。
    gate_exists, gate_raw = read_latin1_optional(gate_path)  # 读取可能因早期失败而缺失的内部门文本。
    gate_text = gate_raw.strip()  # 去除 MAPDL 对齐空格和末尾换行，保留实际状态字段。
    if gate_text.upper().startswith("/COM,"):  # 兼容原生 /COM 前缀被保留的文本输出形式。
        gate_text = gate_text[5:].strip()  # 只去除固定五字符命令前缀，不改写后续状态。
    gate_passed = gate_text == "STATUS=STATIC_GATES_PASSED PHASE=EXTERNAL_QA_REQUIRED"  # 只承认静力内部门已通过且等待外部 QA 的精确终态。
    gate_rejected = "STATUS=REJECTED" in gate_text.upper()  # 识别任一拓扑、收敛、能量、质量或反力内部门拒绝。
    gate_reason_match = re.search(r"REASON=([A-Z0-9_]+)", gate_text.upper())  # 提取稳定机器拒绝原因键。
    gate_reason = str(gate_reason_match.group(1)) if gate_reason_match is not None else None  # 在存在时保存拒绝原因，其他状态保持空值。
    static_exists, static_text = read_latin1_optional(static_path)  # 读取可能因未到达后处理而缺失的机器摘要。
    labels = ("LS1_CNVG", "LS2_CNVG", "LS2", "TIME2", "SENE1", "STEN1", "RATIO1", "STATIC_NSET", "LS1_HISTORY_COUNT", "PEAK_SUBSTEP", "PEAK_TIME", "LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE", "SENE2", "STEN2", "RATIO2", "MASS", "EXPECTED", "ABS_ERROR", "UZ", "RF_EXPECTED", "RF_ACTUAL", "RF_ERROR", "RF_RELATIVE_ERROR")  # 冻结 A0 静力摘要必须唯一提供的二十三个数值字段。
    values, scalar_errors = parse_scalar_fields(static_text, labels) if static_exists else ({}, ["STATIC_SUMMARY_MISSING"])  # 存在时逐字段解析，缺失时以可封存错误表示。
    history_rows, history_errors = parse_history_file(history_path)  # 使用同一生产解析器读取 LS1 六列能量历程。
    static_checks: dict[str, bool] = {"summary_present": static_exists, "all_required_scalars_unique_finite": not scalar_errors and len(values) == len(labels)}  # 初始化静力摘要完整性与数值合法性门。
    if not scalar_errors and len(values) == len(labels):  # 只有全部必需字段唯一且有限时才执行工程数值比较。
        ratio1 = abs(values["STEN1"]) / abs(values["SENE1"]) if values["SENE1"] != 0.0 else math.inf  # 独立复算 LS1 端点稳定化能绝对比，零应变能按无穷失败。
        ratio2 = abs(values["STEN2"]) / abs(values["SENE2"]) if values["SENE2"] != 0.0 else math.inf  # 独立复算 LS2 零增量保持点稳定化能比。
        mass_error = abs(values["MASS"] - EXPECTED_MASS_TONNE)  # 相对冻结 S10 台账独立复算总质量绝对误差，单位 tonne。
        expected_reaction = EXPECTED_MASS_TONNE * GRAVITY_MM_PER_S2 * 1_000.0  # tonne·mm/s² 乘一千转换为 N，得到竖向重力反力期望值。
        reaction_error = abs(abs(values["RF_ACTUAL"]) - abs(expected_reaction))  # 按大小独立复算实际竖向反力与期望重力的绝对差，单位 N。
        reaction_relative_error = reaction_error / abs(expected_reaction)  # 以非零期望重力归一化竖向反力误差。
        static_checks.update({"ls1_converged_exact": math.isclose(values["LS1_CNVG"], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "ls2_converged_exact": math.isclose(values["LS2_CNVG"], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "last_load_step_two_exact": math.isclose(values["LS2"], 2.0, rel_tol=0.0, abs_tol=1.0e-12), "time2_1_001_exact": math.isclose(values["TIME2"], 1.001, rel_tol=0.0, abs_tol=1.0e-12), "ls1_positive_strain_energy": values["SENE1"] > 0.0, "ls1_ratio_recomputed_matches": math.isclose(abs(values["RATIO1"]), ratio1, rel_tol=1.0e-10, abs_tol=1.0e-30), "ls1_ratio_within_1e_minus_2": ratio1 <= LS1_ENERGY_RATIO_LIMIT, "ls2_positive_strain_energy": values["SENE2"] > 0.0, "ls2_ratio_recomputed_matches": math.isclose(abs(values["RATIO2"]), ratio2, rel_tol=1.0e-10, abs_tol=1.0e-30), "ls2_ratio_within_1e_minus_8": ratio2 <= LS2_ENERGY_RATIO_LIMIT, "mass_matches_frozen_ledger": mass_error <= MASS_ABSOLUTE_TOLERANCE_TONNE, "reported_mass_expected_matches": math.isclose(values["EXPECTED"], EXPECTED_MASS_TONNE, rel_tol=0.0, abs_tol=1.0e-9), "reported_mass_error_recomputed": values["ABS_ERROR"] >= 0.0 and math.isclose(values["ABS_ERROR"], mass_error, rel_tol=1.0e-9, abs_tol=1.0e-12), "uz_support_count_464_exact": math.isclose(values["UZ"], 464.0, rel_tol=0.0, abs_tol=1.0e-12), "reported_expected_reaction_recomputed": math.isclose(abs(values["RF_EXPECTED"]), abs(expected_reaction), rel_tol=1.0e-12, abs_tol=1.0e-6), "reported_reaction_error_recomputed": math.isclose(values["RF_ERROR"], reaction_error, rel_tol=1.0e-9, abs_tol=1.0e-6), "reported_reaction_relative_error_recomputed": math.isclose(values["RF_RELATIVE_ERROR"], reaction_relative_error, rel_tol=1.0e-9, abs_tol=1.0e-15), "vertical_gravity_reaction_closure": values["RF_RELATIVE_ERROR"] <= REACTION_RELATIVE_TOLERANCE})  # 对 LS1/LS2、能量、质量、UZ 支承数和竖向重力反力执行独立复算门。
    history_checks: dict[str, bool] = {"history_present_and_parseable": not history_errors and bool(history_rows)}  # 初始化 LS1 历程文件存在且全行可解析门。
    if not history_errors and history_rows:  # 只有六列历程全部可解析时执行顺序、终点和能量复算。
        history_ratios = [abs(row[4]) / abs(row[3]) if row[3] != 0.0 else math.inf for row in history_rows]  # 独立复算每个已接受 LS1 结果集的 |STEN/SENE|。
        history_checks.update({"accepted_count_within_20_to_200": LS1_MIN_ACCEPTED_SUBSTEPS <= len(history_rows) <= LS1_MAX_ACCEPTED_SUBSTEPS, "all_load_step_one": all(math.isclose(row[0], 1.0, rel_tol=0.0, abs_tol=1.0e-12) for row in history_rows), "substeps_sequential": [int(round(row[1])) for row in history_rows] == list(range(1, len(history_rows) + 1)) and all(math.isclose(row[1], float(index), rel_tol=0.0, abs_tol=1.0e-12) for index, row in enumerate(history_rows, start=1)), "times_strictly_increasing": all(history_rows[index][2] > (0.0 if index == 0 else history_rows[index - 1][2]) for index in range(len(history_rows))), "final_time_one": math.isclose(history_rows[-1][2], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "positive_strain_energy": all(row[3] > 0.0 for row in history_rows), "reported_row_ratios_match_recomputed": all(math.isclose(abs(row[5]), ratio, rel_tol=1.0e-10, abs_tol=1.0e-30) for row, ratio in zip(history_rows, history_ratios, strict=True)), "peak_ratio_within_1e_minus_2": max(history_ratios) <= LS1_ENERGY_RATIO_LIMIT})  # 对子步编号、时间、正应变能和全历程稳定化能峰值执行独立门。
        if not scalar_errors and len(values) == len(labels):  # 机器摘要也完整时交叉比较历程行数、结果集数与峰值。
            peak_index = max(range(len(history_ratios)), key=lambda index: history_ratios[index])  # 按未舍入独立比值定位全历程控制子步。
            history_checks.update({"reported_history_count_matches": math.isclose(values["LS1_HISTORY_COUNT"], float(len(history_rows)), rel_tol=0.0, abs_tol=1.0e-12), "reported_static_nset_is_history_plus_one_ls2": math.isclose(values["STATIC_NSET"], float(len(history_rows) + 1), rel_tol=0.0, abs_tol=1.0e-12), "history_endpoint_matches_ls1_summary": math.isclose(history_rows[-1][3], values["SENE1"], rel_tol=1.0e-10, abs_tol=1.0e-12) and math.isclose(history_rows[-1][4], values["STEN1"], rel_tol=1.0e-10, abs_tol=1.0e-12), "reported_peak_substep_and_time_match": math.isclose(values["PEAK_SUBSTEP"], history_rows[peak_index][1], rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(values["PEAK_TIME"], history_rows[peak_index][2], rel_tol=0.0, abs_tol=1.0e-12), "reported_peak_ratio_matches": math.isclose(values["LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE"], history_ratios[peak_index], rel_tol=1.0e-10, abs_tol=1.0e-30)})  # 闭合独立历程和 APDL 摘要的端点、数量与峰值。
    static_checks["passed"] = all(static_checks.values())  # 只有完整性与所有数值门同时通过才承认静力摘要有效。
    history_checks["passed"] = all(history_checks.values())  # 只有历程文件全部独立门同时通过才承认 LS1 能量路径。
    result_checks = {"result_file_present_nonempty": result_path.is_file() and result_path.stat().st_size > 0, "equilibrium_database_present_nonempty": equilibrium_db_path.is_file() and equilibrium_db_path.stat().st_size > 0}  # 成功路径必须实际生成结果文件和内部门后平衡数据库。
    result_checks["passed"] = all(result_checks.values())  # 两份成功原件均存在且非空时才通过。
    return {"gate": {"path": gate_path.relative_to(run_dir).as_posix(), "exists": gate_exists, "text": gate_text, "passed": gate_passed, "rejected": gate_rejected, "reason": gate_reason, "sha256": sha256_file(gate_path, require_stable=True) if gate_exists else None}, "static_summary": {"path": static_path.relative_to(run_dir).as_posix(), "exists": static_exists, "sha256": sha256_file(static_path, require_stable=True) if static_exists else None, "values": values, "parse_errors": scalar_errors, "checks": static_checks}, "ls1_history": {"path": history_path.relative_to(run_dir).as_posix(), "exists": history_path.is_file(), "sha256": sha256_file(history_path, require_stable=True) if history_path.is_file() else None, "row_count": len(history_rows), "parse_errors": history_errors, "checks": history_checks}, "result_files": {"result_path": result_path.relative_to(run_dir).as_posix(), "result_sha256": sha256_file(result_path, require_stable=True) if result_path.is_file() else None, "equilibrium_database_path": equilibrium_db_path.relative_to(run_dir).as_posix(), "equilibrium_database_sha256": sha256_file(equilibrium_db_path, require_stable=True) if equilibrium_db_path.is_file() else None, "checks": result_checks}, "stable_snapshots": stable, "all_pass_checks": gate_passed and bool(static_checks["passed"]) and bool(history_checks["passed"]) and bool(result_checks["passed"])}  # 返回可在成功或失败封板中共用的内部门、独立数值复算和结果原件证据。


def parse_nrre_file(path: Path, jobname: str) -> tuple[dict[str, Any] | None, list[str]]:  # 接收单个 NRRE 路径与 jobname，返回头部/节点序列证据或完整解析错误。
    errors: list[str] = []  # 初始化文件名、头部、行数、节点唯一性和数值错误列表。
    name_pattern = re.compile(NRRE_NAME_PATTERN_TEMPLATE.format(job=re.escape(jobname)), re.IGNORECASE)  # 用转义 jobname 实例化三位文件名模式。
    name_match = name_pattern.fullmatch(path.name)  # 对磁盘文件名执行完整不区分大小写匹配。
    if name_match is None:  # 任何非 job.nrNNN 的文件不得进入节点残差序列。
        return None, ["FILENAME_NOT_JOB_NR_THREE_DIGITS"]  # 返回稳定错误且不尝试读取未知文件。
    filename_iteration = int(name_match.group("index"))  # 从三位后缀读取平衡迭代编号。
    line_count = 0  # 初始化包含四行头部与所有节点数据的物理行数。
    node_count = 0  # 初始化实际成功解析的节点数据行数。
    node_ids: set[int] = set()  # 初始化当前文件节点号唯一性集合。
    node_sequence_digest = hashlib.sha256()  # 对节点号原顺序生成不受残差值影响的集合/顺序身份。
    release_line = ""  # 初始化 ANSYS release 头部文本。
    second_line = ""  # 初始化文件名、CNVV 与 CNVC 头部文本。
    third_line = ""  # 初始化节点数、时间、载荷步、子步和迭代头部文本。
    fourth_line = ""  # 初始化六个残差分量列号头部文本。
    with path.open("rb") as handle:  # 以二进制只读流式打开，避免超大 NRRE 全文进入内存。
        for line_number, raw_line in enumerate(handle, start=1):  # 按一基物理行号遍历头部与全部节点残差。
            line_count = line_number  # 实时更新文件物理行总数。
            line = raw_line.decode("latin-1", errors="strict").rstrip("\r\n")  # Latin-1 一一解码并仅去除行末 CR/LF。
            if line_number == 1:  # 第一行必须声明 ANSYS release 身份。
                release_line = line  # 保存完整 release 原文供工具链追溯。
                continue  # 第一行不按节点数据解析。
            if line_number == 2:  # 第二行必须提供文件名、CNVV 与 CNVC。
                second_line = line  # 保存完整第二行供后续严格正则解析。
                continue  # 第二行不按节点数据解析。
            if line_number == 3:  # 第三行必须提供五个阶段与迭代字段。
                third_line = line  # 保存完整第三行供后续严格分列。
                continue  # 第三行不按节点数据解析。
            if line_number == 4:  # 第四行必须是六个残差分量列号。
                fourth_line = line  # 保存列头原文供顺序检查。
                continue  # 第四行不按节点数据解析。
            tokens = line.split()  # 按任意连续空白分割节点号和六个残差分量。
            if len(tokens) != 7:  # 每个节点数据行必须恰好一个整数节点号和六个数值。
                errors.append(f"DATA_LINE_{line_number}_COLUMN_COUNT_{len(tokens)}")  # 保存破损行号与实际列数。
                continue  # 继续检查后续行以披露完整破损范围。
            try:  # 尝试将第一列转为节点整数、其余六列转为浮点数。
                node_id = int(tokens[0])  # 解析节点号，不允许浮点或科学计数法冒充 ID。
                components = [float(value) for value in tokens[1:]]  # 解析力与力矩六个残差分量。
            except ValueError:  # 节点或任一残差分量无法转换时记录行级错误。
                errors.append(f"DATA_LINE_{line_number}_NUMERIC_PARSE_ERROR")  # 保存可定位的数词错误。
                continue  # 继续扫描后续行而不冒充完整文件。
            if node_id <= 0 or not all(math.isfinite(value) for value in components):  # 节点号必须为正整数且六分量必须全部有限。
                errors.append(f"DATA_LINE_{line_number}_INVALID_NODE_OR_NONFINITE_COMPONENT")  # 保存无效节点或非有限分量行号。
                continue  # 不将无效行纳入节点数与序列摘要。
            if node_id in node_ids:  # 同一 NRRE 中每个节点必须恰好出现一次。
                errors.append(f"DATA_LINE_{line_number}_DUPLICATE_NODE_{node_id}")  # 保存重复节点号和第二次出现位置。
                continue  # 不将重复行再次纳入数量与序列摘要。
            node_ids.add(node_id)  # 登记当前唯一节点号供后续重复检查。
            node_sequence_digest.update(f"{node_id}\n".encode("ascii"))  # 将十进制节点号加 LF 纳入跨文件序列身份。
            node_count += 1  # 累加已通过所有行级门的唯一节点记录数。
    if "ANSYS RELEASE" not in release_line.upper():  # 第一行必须明确由 ANSYS 原生 NLDIAG 写出。
        errors.append("HEADER_RELEASE_LINE_MISSING")  # 保存求解器 release 身份缺失错误。
    second_match = NRRE_SECOND_LINE_PATTERN.fullmatch(second_line)  # 严格匹配第二行的文件名、CNVV 与 CNVC。
    if second_match is None:  # 第二行任一字段缺失或破损时无法完成头部数值审计。
        errors.append("HEADER_SECOND_LINE_INVALID")  # 保存第二行格式错误。
    third_tokens = third_line.split()  # 分割第三行的节点数、时间、载荷步、子步与迭代。
    if len(third_tokens) != 5:  # 第三行必须恰好五列。
        errors.append(f"HEADER_THIRD_LINE_COLUMN_COUNT_{len(third_tokens)}")  # 保存头部实际列数。
    if fourth_line.split() != ["1", "2", "3", "4", "5", "6"]:  # 第四行必须精确声明六个残差分量顺序。
        errors.append("HEADER_COMPONENT_COLUMNS_NOT_1_TO_6")  # 保存列头顺序错误。
    if errors:  # 任一行级或头部错误都使当前 NRRE 不能作为完整迭代证据。
        return None, errors  # 返回完整错误集，使终结器可失败封存而不伪造解析结果。
    try:  # 尝试转换已通过列数检查的三行头部数值。
        declared_node_count = int(third_tokens[0])  # 读取 NRRE 声明的节点记录数。
        result_time = float(third_tokens[1])  # 读取当前迭代所属的结果伪时间。
        load_step = int(third_tokens[2])  # 读取当前迭代所属载荷步号。
        substep = int(third_tokens[3])  # 读取当前迭代所属子步号。
        header_iteration = int(third_tokens[4])  # 读取头部平衡迭代号。
        cnvv = float(second_match.group("cnvv"))  # 读取求解器节点力残差范数 CNVV。
        cnvc = float(second_match.group("cnvc"))  # 读取对应力收敛阈值 CNVC。
    except (ValueError, AttributeError):  # 捕获整数、浮点或已匹配对象转换异常。
        return None, ["HEADER_NUMERIC_PARSE_ERROR"]  # 返回头部数词错误而不中止失败封存。
    header_errors: list[str] = []  # 初始化数值转换后的跨字段一致性错误列表。
    if str(second_match.group("name")).casefold() != path.name.casefold():  # 第二行声明文件名必须与磁盘名完全一致。
        header_errors.append("HEADER_FILENAME_MISMATCH")  # 保存头部与磁盘名错配。
    if declared_node_count != node_count or declared_node_count <= 0 or declared_node_count > EXPECTED_NODE_COUNT:  # 声明数必须等于实际唯一节点数且不超过全模节点数。
        header_errors.append(f"DECLARED_NODE_COUNT_{declared_node_count}_ACTUAL_{node_count}")  # 保存声明、实际和上界差异。
    if line_count != declared_node_count + 4:  # 完整 NRRE 物理行数必须恰好是节点数加四行头部。
        header_errors.append(f"LINE_COUNT_{line_count}_EXPECTED_{declared_node_count + 4}")  # 保存半写、截断或多余行证据。
    if header_iteration != filename_iteration:  # 头部迭代号必须与 .nrNNN 三位后缀一致。
        header_errors.append(f"HEADER_ITERATION_{header_iteration}_FILENAME_{filename_iteration}")  # 保存迭代身份错配。
    if not all(math.isfinite(value) for value in (result_time, cnvv, cnvc)) or cnvv < 0.0 or cnvc <= 0.0:  # 时间与 CNV 必须有限，残差不得为负且阈值必须为正。
        header_errors.append("NONFINITE_OR_INVALID_TIME_CNVV_CNVC")  # 保存不可用头部数值错误。
    if header_errors:  # 任一跨字段错误都使当前文件不能进入有效迭代组。
        return None, header_errors  # 返回完整头部错误集。
    record = {"name": path.name, "relative_path": path.parent.name + "/" + path.name, "sha256": sha256_file(path, require_stable=True), "size_bytes": int(path.stat().st_size), "line_count": line_count, "release_line": release_line, "filename_iteration": filename_iteration, "equilibrium_iteration": header_iteration, "node_count": declared_node_count, "node_sequence_sha256": node_sequence_digest.hexdigest(), "time": result_time, "load_step": load_step, "substep": substep, "cnvv": cnvv, "cnvc": cnvc, "cnvv_to_cnvc": cnvv / cnvc}  # 汇总文件身份、完整性、阶段、迭代和力残差收敛比。
    return record, []  # 返回已通过全文流式验证的 NRRE 记录与空错误列表。


def analyze_nrre_files(solver_dir: Path, jobname: str) -> dict[str, Any]:  # 接收求解目录与 jobname，返回全部 NRRE 完整性、阶段分组与 LS2 终点证据。
    name_pattern = re.compile(NRRE_NAME_PATTERN_TEMPLATE.format(job=re.escape(jobname)), re.IGNORECASE)  # 实例化本 job 三位 NRRE 文件名模式。
    paths = sorted([path for path in solver_dir.iterdir() if path.is_file() and name_pattern.fullmatch(path.name) is not None], key=lambda path: int(name_pattern.fullmatch(path.name).group("index")))  # 按三位迭代号升序枚举本 job 全部 NRRE。
    snapshots_stable(paths) if paths else {}  # 若存在 NRRE，在解析前对全文件集执行两秒大小/时刻稳定门。
    records: list[dict[str, Any]] = []  # 初始化已通过单文件全文门的记录列表。
    parse_errors: list[dict[str, Any]] = []  # 初始化按文件分组的完整解析错误列表。
    for path in paths:  # 按文件名迭代顺序逐个流式验证头部与所有节点行。
        record, errors = parse_nrre_file(path, jobname)  # 调用同一严格单文件解析器。
        if record is not None:  # 只有无任何错误的完整 NRRE 进入阶段分组。
            records.append(record)  # 保存已验证记录。
        if errors:  # 任一文件可同时披露多个行级或头部错误。
            parse_errors.append({"name": path.name, "errors": errors, "sha256": sha256_file(path, require_stable=True), "size_bytes": int(path.stat().st_size)})  # 保存破损文件身份、摘要、大小和完整错误。
    node_sequence_hashes = sorted({str(record["node_sequence_sha256"]) for record in records})  # 去重全部有效文件的节点号顺序身份。
    node_counts = sorted({int(record["node_count"]) for record in records})  # 去重全部有效文件声明与验证通过的节点数。
    groups: dict[str, list[dict[str, Any]]] = {}  # 初始化按载荷步、子步和结果时间分组的迭代映射。
    for record in records:  # 逐个将完整 NRRE 归入其头部声明的阶段上下文。
        group_key = f"LS{int(record['load_step'])}_SS{int(record['substep'])}_TIME{float(record['time']):.12g}"  # 构造不舍入实际双精度语义的稳定人读分组键。
        groups.setdefault(group_key, []).append(record)  # 保持文件名迭代顺序追加当前记录。
    group_summaries = [{"key": key, "load_step": int(group[0]["load_step"]), "substep": int(group[0]["substep"]), "time": float(group[0]["time"]), "iterations": [int(item["equilibrium_iteration"]) for item in group], "file_count": len(group), "final_cnvv_to_cnvc": float(group[-1]["cnvv_to_cnvc"]), "files": [str(item["name"]) for item in group]} for key, group in groups.items()]  # 汇总每个阶段组的迭代号、文件数和最终力残差比。
    terminal_ls2 = [record for record in records if int(record["load_step"]) == 2 and int(record["substep"]) == 1 and math.isclose(float(record["time"]), 1.001, rel_tol=0.0, abs_tol=TIME_ABSOLUTE_TOLERANCE)]  # 提取与已批准 LS2 零增量保持终点一致的 NRRE 组。
    terminal_iterations = [int(record["equilibrium_iteration"]) for record in terminal_ls2]  # 提取 LS2 终点组的平衡迭代号序列。
    terminal_max_iteration = max(terminal_iterations) if terminal_iterations else 0  # 读取 LS2 终点最后一个平衡迭代号，缺失时为零。
    conflicting_low_indices = [record["name"] for record in records if record not in terminal_ls2 and int(record["equilibrium_iteration"]) <= terminal_max_iteration]  # 检查本应被 LS2 重写的低编号是否仍声明其他阶段。
    checks = {"at_least_one_nrre_file": bool(paths), "all_nrre_files_parseable": not parse_errors and len(records) == len(paths), "file_count_at_most_50": len(paths) <= EXPECTED_NRRE_MAXFILE, "node_count_constant": len(node_counts) == 1 and bool(node_counts), "node_sequence_constant": len(node_sequence_hashes) == 1 and bool(node_sequence_hashes), "terminal_ls2_group_present": bool(terminal_ls2), "terminal_ls2_iterations_continuous_from_one": terminal_iterations == list(range(1, len(terminal_iterations) + 1)), "no_conflicting_prior_context_at_terminal_indices": not conflicting_low_indices, "terminal_force_residual_converged": bool(terminal_ls2) and float(terminal_ls2[-1]["cnvv_to_cnvc"]) <= 1.0}  # 允许高编号文件保留前一子步诊断，但要求 LS2 终点自 nr001 连续且最终力残差收敛。
    checks["passed"] = all(checks.values())  # 只有全部文件完整、节点一致且 LS2 终点迭代组成立才通过。
    return {"file_count": len(paths), "files": records, "parse_errors": parse_errors, "node_counts": node_counts, "node_sequence_sha256_values": node_sequence_hashes, "groups": group_summaries, "terminal_ls2": {"file_count": len(terminal_ls2), "iterations": terminal_iterations, "final_cnvv": float(terminal_ls2[-1]["cnvv"]) if terminal_ls2 else None, "final_cnvc": float(terminal_ls2[-1]["cnvc"]) if terminal_ls2 else None, "final_cnvv_to_cnvc": float(terminal_ls2[-1]["cnvv_to_cnvc"]) if terminal_ls2 else None, "conflicting_prior_context_files_at_terminal_indices": conflicting_low_indices}, "checks": checks}  # 返回全部 NRRE 原件身份、破损证据、阶段分组和成功路径 LS2 残差门。


def choose_status(pass_ready: bool, cnvtol_violation: bool, hard_event: bool, abort_valid: bool, abt_termination: bool, natural_nonconvergence: bool, gate_or_solver_error: bool) -> str:  # 接收七项互有优先级的结论条件并返回唯一冻结 A0 最终状态字符串。
    if pass_ready:  # 只有调用者已经证明全部通过门同时为真时，才允许最高优先级的诊断通过结论。
        return PASS_STATUS  # 返回“仅诊断通过且必须继续 A0B”，绝不直接批准模态或生产用途。
    if cnvtol_violation:  # 默认 CNVTOL 被忽略、重置或自动放宽时必须优先于一般硬事件单独归类。
        return CNVTOL_FAILURE_STATUS  # 返回默认收敛准则历史二分失效的专项失败状态。
    if hard_event and abort_valid:  # 存在方程数、主元、致命、资源或并发等硬事件且监控 ABT 合同完整时进入受控中止类。
        return HARD_ABORT_FAILURE_STATUS  # 返回硬事件触发且仅原生十字节 ABT 的失败状态。
    if hard_event:  # 硬事件存在但没有完整 ABT 写盘、同步和回读证据时必须更严格失败关闭。
        return HARD_NO_ABORT_FAILURE_STATUS  # 返回硬事件没有有效原生 ABT 的失败状态。
    if abt_termination:  # 没有已重建硬事件但 MAPDL 原文明确承认 ABT 终止时按原生中止归类。
        return ABT_FAILURE_STATUS  # 返回独立 ABT 终止失败状态，不把它误认成自然非收敛。
    if natural_nonconvergence:  # MAPDL 或内部 LS1/LS2 门明确给出自然未收敛时进入数值非收敛类。
        return NATURAL_FAILURE_STATUS  # 返回自然非收敛失败状态供后续工程复盘。
    if gate_or_solver_error:  # 内部静力门拒绝或求解器 ERROR/FATAL/非零错误摘要存在时进入门或求解器错误类。
        return GATE_FAILURE_STATUS  # 返回静力门或求解器错误失败状态。
    return INCOMPLETE_FAILURE_STATUS  # 其余缺日志、缺阶段、缺结果或证据不闭合情况统一失败关闭为未证明完整序列。


def json_safe(value: Any) -> Any:  # 接收可能含 Path、集合或嵌套容器的审计值并返回可由严格 JSON 稳定编码的等价对象。
    if isinstance(value, Path):  # Path 不是 JSON 原生类型，必须保留其规范字符串身份。
        return str(value)  # 返回绝对或既有相对路径文本而不访问文件系统。
    if isinstance(value, dict):  # 对任意异构字典递归转换键和值。
        return {str(key): json_safe(item) for key, item in value.items()}  # 把键规范为字符串并保持原插入顺序递归转换值。
    if isinstance(value, (list, tuple)):  # 列表和元组均以 JSON 数组语义保存顺序。
        return [json_safe(item) for item in value]  # 逐项递归转换并返回新列表，避免修改上游证据对象。
    if isinstance(value, (set, frozenset)):  # 集合没有稳定顺序，必须在进入审计前规范化。
        return [json_safe(item) for item in sorted(value, key=lambda item: str(item))]  # 按字符串表示稳定排序后递归转换。
    return value  # 字符串、布尔、空值和有限数字等 JSON 原生标量保持不变。


def detect_unexpected_modal_artifacts(run_dir: Path, jobname: str) -> list[dict[str, Any]]:  # 接收已退出运行和 jobname，返回不应在纯静力 A0 中出现的模态结果工件清单。
    candidates = [run_dir / "C10_modal_final_status.json", run_dir / "qa" / "c10_modal_final_audit.json", run_dir / "qa" / "c10_modal_final_report.md", run_dir / "solver" / "c10_modal_frequencies.txt", run_dir / "solver" / f"{jobname}_modal_frequencies.txt", run_dir / "solver" / f"{jobname}_modal_results.txt"]  # 冻结会声明已执行模态或形成模态结果的精确目标路径，避免把含 modal 字样的准备说明误报。
    findings: list[dict[str, Any]] = []  # 初始化意外模态工件身份列表。
    for path in candidates:  # 逐个检查明确的模态状态、审计、报告和频率结果路径。
        if path.is_file():  # 仅普通文件构成运行已越过静力截断线的证据。
            findings.append({"path": path.relative_to(run_dir).as_posix(), "size_bytes": int(path.stat().st_size), "sha256": sha256_file(path, require_stable=True)})  # 保存相对路径、字节数和稳定摘要供失败封板。
    return findings  # 返回空列表表示没有发现 A0 禁止的模态结果工件。


def write_new_batch(payloads: dict[Path, str]) -> None:  # 接收全部最终路径与渲染文本并通过同卷暂存、排他硬链接和身份安全回滚一次发布。
    require(bool(payloads), "A0 最终批量发布列表为空")  # 禁止空调用被误认为已完成封板。
    staging_paths = {path: path.with_name(f"{path.name}.codex_staging") for path in payloads}  # 为每个目标构造同目录同卷暂存名以保证链接发布不跨卷。
    published_identities: dict[Path, tuple[int, int, int]] = {}  # 保存本调用创建目标的卷号、文件 ID 和大小，供异常时只回滚本批对象。
    for target_path, staging_path in staging_paths.items():  # 在写出任何字节前统一预检全部目标与暂存路径。
        require(target_path.parent.is_dir(), f"A0 最终工件父目录不存在：{target_path.parent}")  # 禁止终结器隐式创建错误目录层级。
        require(not target_path.exists(), f"拒绝覆盖既有 A0 最终工件：{target_path}")  # 一个 run 的同名最终工件只允许首次创建。
        require(not staging_path.exists(), f"发现遗留 A0 暂存工件：{staging_path}")  # 防止上次异常字节被本次发布复用。
    try:  # 任一暂存、同步、链接或删名异常都进入本批次安全回滚分支。
        for target_path, rendered_text in payloads.items():  # 先把全部已完成渲染的文本写入对应暂存文件。
            staging_path = staging_paths[target_path]  # 取得当前目标唯一同目录暂存路径。
            with staging_path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用排他创建、UTF-8 和固定 LF 写入，拒绝覆盖残留文件。
                handle.write(rendered_text)  # 一次写出内存中已验证且不含 NaN 的完整文本。
                handle.flush()  # 把 Python 用户态文本缓冲全部交给操作系统。
                os.fsync(handle.fileno())  # 请求把暂存字节同步到磁盘后才允许发布最终名称。
        for target_path, staging_path in staging_paths.items():  # 全部暂存成功后按插入顺序逐项发布最终名称。
            os.link(staging_path, target_path)  # 通过不可覆盖硬链接发布；目标若迟到存在则由操作系统原子拒绝。
            published_stat = target_path.stat()  # 读取本调用刚创建目标的数据对象身份。
            published_identities[target_path] = (int(published_stat.st_dev), int(published_stat.st_ino), int(published_stat.st_size))  # 冻结卷、文件 ID 与字节数三元组。
            staging_path.unlink()  # 删除暂存名称，仅保留指向同一已同步数据对象的最终名称。
    except Exception:  # 捕获任意文件系统异常并恢复到没有本批次部分最终工件的状态。
        for staging_path in staging_paths.values():  # 遍历只属于本次固定命名规则的暂存路径。
            if staging_path.exists():  # 已正常删名的暂存路径不进入删除分支。
                staging_path.unlink()  # 删除本次未发布或部分发布的暂存名称，不触碰其他文件。
        for target_path, expected_identity in reversed(list(published_identities.items())):  # 逆序检查本调用已经创建的部分最终目标。
            if target_path.is_file():  # 只有目标仍为普通文件时才读取并比较数据对象身份。
                current_stat = target_path.stat()  # 取得异常时目标当前卷号、文件 ID 和大小。
                current_identity = (int(current_stat.st_dev), int(current_stat.st_ino), int(current_stat.st_size))  # 构造与发布时同格式的当前身份三元组。
                if current_identity == expected_identity:  # 仅当目标仍指向本调用创建的同一数据对象时允许回滚删除。
                    target_path.unlink()  # 删除本次部分发布目标，防止半套封板被下游误读。
        raise  # 原样重新抛出异常，让调用者明确看到发布没有完成。


def build_appended_ledger(run_dir: Path, prepared_entries: dict[str, str], virtual_texts: dict[Path, str], ledger_path: Path) -> tuple[str, int]:  # 接收运行、准备谱系、四项虚拟最终文本和账本路径，返回覆盖全部非自引用工件的最终账本。
    target_paths = {path.resolve() for path in virtual_texts} | {ledger_path.resolve()}  # 构造尚未发布的虚拟目标和不得自引用的最终账本目标集合。
    existing_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.resolve() not in target_paths and not path.name.endswith(".codex_staging")]  # 枚举运行内全部既有普通文件并排除本批目标、账本自身和暂存名。
    ledger_entries: dict[str, str] = {}  # 初始化相对路径到稳定 SHA-256 的完整映射。
    for path in existing_paths:  # 对准备、启动、监控、租约、求解与诊断原件逐项完整散列。
        relative_text = path.relative_to(run_dir).as_posix()  # 转换为跨平台稳定的 POSIX 运行内相对路径。
        require(relative_text not in ledger_entries, f"A0 最终账本既有路径重复：{relative_text}")  # 阻断枚举或大小写歧义导致的覆盖。
        ledger_entries[relative_text] = sha256_file(path, require_stable=True)  # 对原件执行读前读后稳定检查并保存完整摘要。
    for relative_text, prepared_sha256 in prepared_entries.items():  # 逐项证明启动前准备账本路径与字节在最终时仍原样存在。
        require(ledger_entries.get(relative_text) == prepared_sha256, f"A0 最终账本未保持准备条目：{relative_text}")  # 任一准备字节漂移、缺失或被目标遮蔽都拒绝发布。
    for path, rendered_text in virtual_texts.items():  # 对尚未落盘的源码快照、审计、报告和根最终状态预计算摘要。
        relative_text = path.resolve().relative_to(run_dir).as_posix()  # 将每个虚拟目标限制并转换为运行内 POSIX 路径。
        require(relative_text not in ledger_entries, f"A0 最终账本虚拟路径与既有工件冲突：{relative_text}")  # 发布前关闭重名和覆盖路径。
        ledger_entries[relative_text] = sha256_bytes(rendered_text.encode("utf-8"))  # 按实际 UTF-8 写出字节计算虚拟摘要。
    ordered_lines = [f"{ledger_entries[relative_text]}  {relative_text}" for relative_text in sorted(ledger_entries)]  # 按相对路径稳定排序生成标准双空格账本行。
    require(len(ordered_lines) > len(prepared_entries), "A0 最终追加账本没有覆盖准备账本之外的运行与终态工件")  # 必须真实新增启动、监控、求解和最终审计证据。
    return "\n".join(ordered_lines) + "\n", len(ordered_lines)  # 返回末尾单一 LF 的非自引用账本文本和条目数。


def render_final_report(run_name: str, jobname: str, status: str, pass_gate_checks: dict[str, bool], monitor: dict[str, Any], logs: dict[str, Any], static_outputs: dict[str, Any], nrre: dict[str, Any], finalized_at_utc: str) -> str:  # 接收最终证据摘要并返回面向工程复核的简明中文 Markdown 报告。
    failed_gates = [name for name, passed in pass_gate_checks.items() if not passed]  # 提取所有没有通过的外部 QA 门名称供一眼定位。
    failed_gate_text = "、".join(failed_gates) if failed_gates else "无"  # 将空失败集明确渲染为“无”，其余按中文顿号连接。
    next_action = "A0 仅诊断通过；下一步必须新建同一路径 A0B，并启用当前四项显式 CNVTOL 后重新执行静力验收。" if status == PASS_STATUS else "A0 未通过；禁止续跑本 run、禁止进入模态或生产，须先按失败证据复核并新建运行。"  # 根据唯一状态确定允许的后续动作边界。
    lines = ["# C10 A0 外部终结报告", "", f"- 运行：`{run_name}`", f"- Job：`{jobname}`", f"- 最终状态：`{status}`", f"- 封板时刻（UTC）：`{finalized_at_utc}`", f"- 监控终态：`{monitor['status']}`", f"- 监控硬事件数：`{monitor['hard_event_count']}`", f"- 日志重建硬事件数：`{len(logs['hard_events'])}`", f"- 静力内部门：`{static_outputs['gate']['text'] or '缺失'}`", f"- NRRE 文件数：`{nrre['file_count']}`", "", "## 外部 QA 判定", "", f"未通过的门：{failed_gate_text}", "", "## 使用边界", "", next_action, "", "本报告不构成设计签认；A0 在任何状态下都不允许直接形成模态或生产结论。", ""]  # 组装固定字段、失败门和用途边界，避免报告引入机器审计之外的新结论。
    return "\n".join(lines)  # 返回带末尾 LF 的可读 Markdown 文本。


def finalize_run(run_dir_value: Path) -> dict[str, Any]:  # 接收唯一 A0 运行目录，在稳定自然终态后完成只读复核并排他发布五项最终工件。
    run_dir = resolve_run(run_dir_value)  # 先关闭目录边界、替代运行和重复发布门。
    prepared = validate_prepared_package(run_dir)  # 独立复算准备账本、清单、拓扑、deck 和启动参数身份。
    runtime = validate_runtime_chain(prepared)  # 独立闭合启动认领、真实进程身份、自动监控握手与主机租约链。
    monitor = validate_monitor_chain(prepared, runtime)  # 只接受稳定空进程、无锁且租约由监控封存释放的自然或受控硬终态。
    output_exists, output_text = read_latin1_optional(Path(str(monitor["output_path"])))  # 读取监控已冻结稳定的权威 OUT 原文。
    error_exists, error_text = read_latin1_optional(Path(str(monitor["error_path"])))  # 读取监控已冻结稳定的权威 ERR 原文。
    mntr_exists, mntr_text = read_latin1_optional(Path(str(monitor["mntr_path"])))  # 读取监控已冻结稳定的权威 MNTR 原文。
    logs = parse_solver_logs(output_exists, output_text, error_exists, error_text)  # 从完整 OUT/ERR 重建方程数、主元、消息、终止和完成证据。
    sequence = analyze_static_sequence(mntr_exists, mntr_text, logs)  # 以 MNTR 与 OUT 交叉验证 LS1 斜坡和 LS2 零增量保持路径。
    static_outputs = analyze_static_outputs(run_dir, str(prepared["jobname"]))  # 独立复算内部门、能量、质量、反力和成功结果原件。
    nrre = analyze_nrre_files(Path(str(prepared["solver_dir"])), str(prepared["jobname"]))  # 流式验证全部 NRRE 文件及 LS2 终点力残差收敛组。
    modal_artifacts = detect_unexpected_modal_artifacts(run_dir, str(prepared["jobname"]))  # 检查纯静力 A0 是否意外越过模态截断线。
    monitor_cnvtol_events = [event for event in monitor["hard_events"] if "CNVTOL" in str(event.get("kind", "")).upper()]  # 从监控硬事件中提取所有 CNVTOL 忽略、重置或放宽类别。
    cnvtol_violation = bool(logs["cnvtol_policy_messages"] or monitor_cnvtol_events)  # 任一完整日志或在线监控命中都使默认 CNVTOL 历史二分失败。
    combined_hard_events = [{"source": "MONITOR", "event": event} for event in monitor["hard_events"]] + [{"source": "FULL_LOG_RECONSTRUCTION", "event": event} for event in logs["hard_events"]]  # 合并在线即时硬事件和退出后完整日志重建证据，保留来源而不去重。
    hard_event = bool(combined_hard_events)  # 任一硬事件都禁止诊断通过，并决定 ABT 合同分支。
    abort_valid = bool(monitor["native_abort_contract_valid"])  # 引用已经按十字节、hex、SHA、同步和回读逐项复核的 ABT 有效性。
    abt_termination = bool(logs["abt_termination_matches"])  # 只有 MAPDL 原文明确承认 ABT 终止才设置原生中止签名。
    gate_reason_upper = str(static_outputs["gate"].get("reason") or "").upper()  # 规范内部静力门拒绝原因供自然非收敛分类。
    natural_nonconvergence = bool(logs["natural_nonconvergence_matches"]) or any(token in gate_reason_upper for token in ("NOT_CONVERGED", "NONCONVERGENCE", "NCNV"))  # 合并 MAPDL 自然未收敛签名和 LS1/LS2 内部门原因。
    gate_or_solver_error = bool(static_outputs["gate"]["rejected"]) or int(logs["error_block_count"]) > 0 or bool(logs["fatal_messages"]) or any(int(value) > 0 for value in logs["error_summaries"])  # 识别非零错误摘要、ERROR/FATAL 块或任一内部门拒绝。
    pass_gate_checks: dict[str, bool] = {"monitor_natural_stable_exit": monitor["status"] == NATURAL_MONITOR_STATUS, "monitor_has_no_hard_events": int(monitor["hard_event_count"]) == 0, "monitor_has_no_native_abort": not abort_valid, "output_file_present": output_exists, "error_file_present": error_exists, "mntr_file_present": mntr_exists, "run_completed_marker_present": bool(logs["run_completed_marker"]), "normal_nosave_exit_marker_present": bool(logs["normal_nosave_exit_marker"]), "error_summary_exactly_single_zero": logs["error_summaries"] == [0], "no_error_message_blocks": int(logs["error_block_count"]) == 0, "no_fatal_message_blocks": not logs["fatal_messages"], "equation_count_reported": bool(logs["equation_counts"]), "all_equation_counts_match_1234834": bool(logs["equation_counts"]) and all(int(value) == EXPECTED_EQUATION_COUNT for value in logs["equation_counts"]), "minimum_pivot_reported": bool(logs["minimum_pivots"]), "all_minimum_pivots_finite_positive": bool(logs["minimum_pivots"]) and all(math.isfinite(float(value)) and float(value) > 0.0 for value in logs["minimum_pivots"]), "no_explicit_bad_pivot_messages": not logs["bad_pivot_messages"], "no_default_cnvtol_policy_violation": not cnvtol_violation, "no_natural_nonconvergence_signature": not natural_nonconvergence, "no_abt_termination_signature": not abt_termination, "ls1_ls2_sequence_passed": bool(sequence["all_checks_passed"]), "static_outputs_all_passed": bool(static_outputs["all_pass_checks"]), "nrre_all_passed": bool(nrre["checks"]["passed"]), "no_modal_result_artifacts": not modal_artifacts}  # 冻结 A0 诊断通过必须同时满足的二十三项外部 QA 门。
    pass_ready = all(pass_gate_checks.values())  # 只有全部外部门同时成立才允许进入 A0 诊断通过分类。
    status = choose_status(pass_ready, cnvtol_violation, hard_event, abort_valid, abt_termination, natural_nonconvergence, gate_or_solver_error)  # 按 CNVTOL、硬事件、ABT、NCNV、门错误和证据不足的冻结优先级选唯一状态。
    require((status == PASS_STATUS) == pass_ready, "A0 状态分类与全部通过门布尔值分叉")  # 防止未来修改让失败证据被错误升格或全门通过被降为其他类别。
    finalized_at_utc = utc_now()  # 在全部只读数值与文件验证完成后冻结唯一封板时刻。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 严格读取本终结器当前源码作为运行内不可覆盖执行逻辑快照。
    snapshot_path = run_dir / "qa" / "ultra_c10_a0_finalize_snapshot.py"  # 定位最终器源码快照目标。
    audit_path = run_dir / "qa" / "a0_final_audit.json"  # 定位完整机器审计目标。
    report_path = run_dir / "qa" / "a0_final_report.md"  # 定位简明中文报告目标。
    status_path = run_dir / "C10_a0_final_status.json"  # 定位运行根唯一 A0 最终状态目标。
    ledger_path = run_dir / "artifact_hashes_a0_final.sha256"  # 定位覆盖全部非自引用工件的追加账本目标。
    preparation_summary = {"manifest_path": "manifest.json", "manifest_sha256": sha256_file(Path(str(prepared["manifest_path"])), require_stable=True), "root_status_path": "C10_static_status.json", "root_status_sha256": sha256_file(Path(str(prepared["root_status_path"])), require_stable=True), "prepared_ledger_path": "artifact_hashes.sha256", "prepared_ledger_sha256": str(prepared["prepared_ledger_sha256"]), "prepared_ledger_entry_count": len(prepared["prepared_entries"]), "main_input_path": Path(str(prepared["main_path"])).relative_to(run_dir).as_posix(), "main_input_sha256": str(prepared["main_sha256"]), "run_name": run_dir.name, "jobname": str(prepared["jobname"]), "diagnostic_subtype": EXPECTED_SUBTYPE, "load_path_mode": EXPECTED_LOAD_PATH, "expected_equation_count": EXPECTED_EQUATION_COUNT}  # 汇总已逐字节闭合的准备谱系、执行 deck 和冻结分析身份。
    runtime_summary = {"launch_claim_path": Path(str(runtime["claim_path"])).relative_to(run_dir).as_posix(), "launch_claim_sha256": str(runtime["claim_sha256"]), "runtime_launch_path": Path(str(runtime["launch_path"])).relative_to(run_dir).as_posix(), "runtime_launch_sha256": str(runtime["launch_sha256"]), "process_identity_path": Path(str(runtime["identity_path"])).relative_to(run_dir).as_posix(), "process_identity_sha256": str(runtime["identity_sha256"]), "main_pid": int(runtime["main_pid"]), "main_create_time_epoch_seconds": float(runtime["create_time_epoch_seconds"]), "launch_argv": list(prepared["launch_argv"]), "host_lease_path": str(runtime["host_lease_path"]), "host_lease_sha256": str(runtime["host_lease_sha256"]), "host_lease_absent_after_stable_exit": bool(runtime["host_lease_absent_after_stable_exit"]), "monitor_spawn_claim_path": Path(str(runtime["monitor_spawn_claim_path"])).relative_to(run_dir).as_posix(), "monitor_spawn_claim_sha256": str(runtime["monitor_spawn_claim_sha256"]), "monitor_launch_path": Path(str(runtime["monitor_launch_path"])).relative_to(run_dir).as_posix(), "monitor_launch_sha256": str(runtime["monitor_launch_sha256"]), "monitor_attachment_path": Path(str(runtime["monitor_attachment_path"])).relative_to(run_dir).as_posix(), "monitor_attachment_sha256": str(runtime["monitor_attachment_sha256"]), "monitor_argv": list(runtime["monitor_argv"]), "active_job_processes_at_finalizer": list(runtime["active_job_processes"]), "active_monitor_processes_at_finalizer": list(runtime["active_monitor_processes"])}  # 汇总 MAPDL、自动监控握手、租约和最终无活动进程的闭合执行链。
    classification = {"status": status, "pass_ready": pass_ready, "cnvtol_violation": cnvtol_violation, "hard_event": hard_event, "native_abort_contract_valid": abort_valid, "abt_termination": abt_termination, "natural_nonconvergence": natural_nonconvergence, "gate_or_solver_error": gate_or_solver_error, "pass_gate_checks": pass_gate_checks, "combined_hard_events": combined_hard_events, "unexpected_modal_artifacts": modal_artifacts}  # 保存唯一分类输入、全部通过门和硬事件来源供独立复算。
    use_boundaries = {"a0_diagnostic_passed": status == PASS_STATUS, "next_required_run": "A0B_SAME_PATH_WITH_CURRENT_FOUR_EXPLICIT_CNVTOL_STATIC_ACCEPTANCE" if status == PASS_STATUS else "ENGINEERING_REVIEW_AND_NEW_RUN_REQUIRED", "modal_status": "BLOCKED_NOT_RUN", "modal_execution_allowed": False, "production_claim_allowed": False, "valid_for_production": False, "a0_direct_production_promotion_allowed": False, "design_signoff_provided": False}  # 在通过与失败两条路径都明确关闭模态、生产和设计签认权限。
    audit = {"schema_version": 1, "status": status, "finalized_at_utc": finalized_at_utc, "preparation_chain": preparation_summary, "runtime_execution_chain": runtime_summary, "monitor_and_host_lease_verification": json_safe(monitor), "solver_log_evidence": logs, "static_sequence_verification": sequence, "static_output_verification": static_outputs, "nrre_verification": nrre, "classification": classification, "use_boundaries": use_boundaries, "finalizer_contract": {"tool_path": str(SCRIPT_PATH), "tool_sha256": sha256_bytes(source_text.encode("utf-8")), "source_snapshot_path": snapshot_path.relative_to(run_dir).as_posix(), "final_status_path": status_path.relative_to(run_dir).as_posix(), "final_report_path": report_path.relative_to(run_dir).as_posix(), "final_ledger_path": ledger_path.relative_to(run_dir).as_posix(), "final_ledger_is_non_self_referential": True, "terminate_called": False, "kill_called": False, "send_signal_called": False, "solver_execution_attempted": False}}  # 组装准备、运行、监控、日志、阶段、数值、NRRE、分类和用途边界的完整机器审计。
    audit_text = render_json(json_safe(audit))  # 以稳定 UTF-8 JSON 渲染完整审计并拒绝任何 NaN。
    report_text = render_final_report(run_dir.name, str(prepared["jobname"]), status, pass_gate_checks, monitor, logs, static_outputs, nrre, finalized_at_utc)  # 渲染只复述机器结论的中文报告。
    final_status = {"schema_version": 1, "status": status, "run_name": run_dir.name, "jobname": str(prepared["jobname"]), "diagnostic_subtype": EXPECTED_SUBTYPE, "finalized_at_utc": finalized_at_utc, "static_execution_terminal_stable": True, "static_result_valid_for_a0_diagnostic": status == PASS_STATUS, "a0_diagnostic_passed": status == PASS_STATUS, "pass_gate_checks": pass_gate_checks, "monitor_status": str(monitor["status"]), "monitor_hard_event_count": int(monitor["hard_event_count"]), "native_abort_contract_valid": abort_valid, "modal_status": "BLOCKED_NOT_RUN", "modal_execution_allowed": False, "production_claim_allowed": False, "valid_for_production": False, "next_required_run": use_boundaries["next_required_run"], "final_audit_path": audit_path.relative_to(run_dir).as_posix(), "final_audit_sha256": sha256_bytes(audit_text.encode("utf-8")), "final_report_path": report_path.relative_to(run_dir).as_posix(), "final_report_sha256": sha256_bytes(report_text.encode("utf-8")), "finalizer_snapshot_path": snapshot_path.relative_to(run_dir).as_posix(), "finalizer_snapshot_sha256": sha256_bytes(source_text.encode("utf-8")), "prepared_ledger_path": "artifact_hashes.sha256", "prepared_ledger_sha256": str(prepared["prepared_ledger_sha256"]), "final_ledger_path": ledger_path.relative_to(run_dir).as_posix(), "final_ledger_non_self_referential": True, "terminate_called": False, "kill_called": False, "send_signal_called": False, "solver_execution_attempted_by_finalizer": False}  # 组装根级唯一最终状态并始终保持模态与生产关闭。
    final_status_text = render_json(final_status)  # 稳定渲染根最终状态供虚拟摘要和排他发布。
    virtual_texts = {snapshot_path: source_text, audit_path: audit_text, report_path: report_text, status_path: final_status_text}  # 构造四项非账本最终工件及其精确待写文本。
    ledger_text, ledger_entry_count = build_appended_ledger(run_dir, prepared["prepared_entries"], virtual_texts, ledger_path)  # 对全部既有原件和四项虚拟工件生成追加非自引用账本。
    write_new_batch({snapshot_path: source_text, audit_path: audit_text, report_path: report_text, status_path: final_status_text, ledger_path: ledger_text})  # 以单批同卷排他方式发布五项最终工件。
    published_entries = parse_ledger_text(ledger_path.read_text(encoding="utf-8", errors="strict"))  # 解析刚发布的非自引用最终账本供目标字节回读验证。
    for target_path, rendered_text in virtual_texts.items():  # 逐项验证四项虚拟工件的账本摘要与实际落盘字节三方一致。
        relative_text = target_path.relative_to(run_dir).as_posix()  # 取得当前最终目标在账本中的稳定相对键。
        expected_sha256 = sha256_bytes(rendered_text.encode("utf-8"))  # 按发布前内存文本复算期望 UTF-8 摘要。
        require(published_entries.get(relative_text) == expected_sha256 == sha256_file(target_path, require_stable=True), f"A0 发布后最终工件摘要不闭合：{relative_text}")  # 任一账本、内存或落盘字节分叉都显式失败。
    require(len(published_entries) == ledger_entry_count and ledger_path.relative_to(run_dir).as_posix() not in published_entries, "A0 最终账本条目数或非自引用合同错误")  # 确认账本没有将自身错误纳入哈希闭环。
    return {"schema_version": 1, "status": status, "run_name": run_dir.name, "jobname": str(prepared["jobname"]), "final_status_path": str(status_path), "final_status_sha256": sha256_file(status_path, require_stable=True), "final_audit_path": str(audit_path), "final_audit_sha256": sha256_file(audit_path, require_stable=True), "final_report_path": str(report_path), "final_report_sha256": sha256_file(report_path, require_stable=True), "final_ledger_path": str(ledger_path), "final_ledger_sha256": sha256_file(ledger_path, require_stable=True), "final_ledger_entry_count": ledger_entry_count, "modal_execution_allowed": False, "production_claim_allowed": False, "solver_execution_attempted_by_finalizer": False}  # 返回可供调用者定位和核验的最终发布摘要。


def ast_call_name(node: ast.Call) -> str | None:  # 接收一个 AST 调用节点并返回简单函数名或属性名，无法稳定识别时返回空值。
    if isinstance(node.func, ast.Name):  # 直接名称调用可从 Name 节点取得标识符。
        return str(node.func.id)  # 返回例如 print 或 finalize_run 的简单名称。
    if isinstance(node.func, ast.Attribute):  # 对象方法或模块属性调用可从 Attribute 节点取得末级名称。
        return str(node.func.attr)  # 返回例如 link、unlink 或 process_iter 的末级属性名。
    return None  # 下标或其他动态可调用表达式没有稳定简单名称。


def expect_runtime_error(action: Any, label: str) -> str:  # 接收预期抛出 RuntimeError 的零参数动作和测试标签，返回实际拒绝原因文本。
    try:  # 执行坏输入动作以验证其失败关闭行为。
        action()  # 调用只作用于内存或系统临时目录的自测动作。
    except RuntimeError as exc:  # 只把本工具契约拒绝异常视为预期结果。
        return str(exc)  # 返回明确拒绝原因供自测摘要证明。
    raise RuntimeError(f"离线自测失败：{label} 没有被拒绝")  # 动作意外成功时立即使整体自测失败。


def run_offline_self_tests() -> dict[str, Any]:  # 无运行输入并返回不访问 ultra_runs、不扫描进程且不启动 MAPDL 的离线解析、分类、发布和注释自测摘要。
    ledger_rejection = expect_runtime_error(lambda: parse_ledger_text("不是合法账本\n"), "畸形账本")  # 验证准备与最终账本解析器拒绝非 SHA-256 标准行。
    synthetic_mntr = "\n".join([f"1 {index} 1 3 {index * 3} 0.05 {index * 0.05}" for index in range(1, 21)] + ["2 1 1 2 62 0.001 1.001"]) + "\n"  # 构造二十个 LS1 已接受子步和唯一无 cutback 的 LS2 保持子步。
    synthetic_completed = "\n".join([f"*** LOAD STEP 1 SUBSTEP {index} COMPLETED" for index in range(1, 21)] + ["*** LOAD STEP 2 SUBSTEP 1 COMPLETED"])  # 构造与 MNTR 完全一致的 OUT 已接受结果集标记。
    synthetic_pass_out = "\n".join([f"NUMBER OF EQUATIONS = {EXPECTED_EQUATION_COUNT}", "SPARSE SOLVER MINIMUM PIVOT = 1.000000E-06", synthetic_completed, "NUMBER OF ERROR MESSAGES ENCOUNTERED = 0", "RUN COMPLETED", "EXIT MAPDL WITHOUT SAVING DATABASE", ""])  # 构造方程数、正主元、零错误和正常 NOSAVE 退出均成立的合成 OUT。
    synthetic_pass_logs = parse_solver_logs(True, synthetic_pass_out, True, "")  # 使用生产日志解析器验证成功特征提取。
    synthetic_sequence = analyze_static_sequence(True, synthetic_mntr, synthetic_pass_logs)  # 使用生产阶段解析器验证 LS1/LS2 合成成功路径。
    require(synthetic_sequence["all_checks_passed"] and synthetic_pass_logs["error_summaries"] == [0] and synthetic_pass_logs["minimum_pivots"] == [1.0e-6], "离线自测失败：合成成功 OUT/MNTR 未通过")  # 固定方程、主元、阶段和退出词法的正向行为。
    synthetic_cnvtol_out = synthetic_pass_out + "*** WARNING ***\nTHE CNVTOL COMMAND IS IGNORED\n"  # 在真实 WARNING 消息块中加入默认 CNVTOL 被忽略签名。
    synthetic_cnvtol_logs = parse_solver_logs(True, synthetic_cnvtol_out, True, "")  # 使用生产消息块隔离器解析 CNVTOL 合成失败路径。
    require(bool(synthetic_cnvtol_logs["cnvtol_policy_messages"]), "离线自测失败：CNVTOL 被忽略消息未命中")  # 固定输入回显之外的真实消息块必须触发专项失败。
    synthetic_natural_logs = parse_solver_logs(True, synthetic_pass_out + "SOLUTION IS NOT CONVERGED\n", True, "")  # 构造 MAPDL 自然未收敛原文签名。
    require(bool(synthetic_natural_logs["natural_nonconvergence_matches"]), "离线自测失败：自然未收敛签名未命中")  # 固定 NCNV 与证据不足或 ABT 的分类边界。
    synthetic_abt_logs = parse_solver_logs(True, synthetic_pass_out + "RUN IS TERMINATED AT THE USER'S REQUEST FROM THE ABT FILE\n", True, "")  # 构造 MAPDL 明确承认用户 ABT 的终止签名。
    require(bool(synthetic_abt_logs["abt_termination_matches"]), "离线自测失败：原生 ABT 终止签名未命中")  # 固定 ABT 原文确认识别行为。
    status_cases = [(True, False, False, False, False, False, False, PASS_STATUS), (False, True, True, True, False, False, False, CNVTOL_FAILURE_STATUS), (False, False, True, True, False, False, False, HARD_ABORT_FAILURE_STATUS), (False, False, True, False, False, False, False, HARD_NO_ABORT_FAILURE_STATUS), (False, False, False, False, True, False, False, ABT_FAILURE_STATUS), (False, False, False, False, False, True, True, NATURAL_FAILURE_STATUS), (False, False, False, False, False, False, True, GATE_FAILURE_STATUS), (False, False, False, False, False, False, False, INCOMPLETE_FAILURE_STATUS)]  # 构造覆盖八种唯一状态和优先级冲突的分类真值表。
    observed_statuses = [choose_status(*case[:7]) for case in status_cases]  # 对每个真值组合调用生产分类器。
    expected_statuses = [str(case[7]) for case in status_cases]  # 提取真值表中冻结的期望状态顺序。
    require(observed_statuses == expected_statuses, f"离线自测失败：状态分类优先级漂移 {observed_statuses}")  # 确认 CNVTOL、硬事件、ABT、NCNV、门错误和不完整的顺序。
    with tempfile.TemporaryDirectory(prefix="c10_a0_finalize_selftest_") as temporary_name:  # 仅在系统临时根创建自动回收沙箱，不访问项目 ultra_runs。
        temporary_root = Path(temporary_name).resolve()  # 规范化临时根供 NRRE、账本和发布测试使用。
        synthetic_nrre_path = temporary_root / "selfjob.nr001"  # 定位两节点 LS2 终点的合成 NRRE 文件。
        synthetic_nrre_text = "\n".join(["***** ANSYS RELEASE 2026 R1 *****", "File written with name = selfjob.nr001 CNVV = 1.000000E-04 CNVC = 2.000000E-04", "2 1.001 2 1 1", "1 2 3 4 5 6", "1 0.0 0.0 0.0 0.0 0.0 0.0", "2 1.0E-09 -1.0E-09 2.0E-09 -2.0E-09 3.0E-09 -3.0E-09", ""])  # 构造头部、连续迭代、有限六分量和 CNVV/CNVC 小于一的完整文本。
        synthetic_nrre_path.write_text(synthetic_nrre_text, encoding="latin-1", newline="\n")  # 仅向自动回收临时目录写入合成 NRRE 原件。
        synthetic_nrre_record, synthetic_nrre_errors = parse_nrre_file(synthetic_nrre_path, "selfjob")  # 使用生产流式解析器读取合成 NRRE。
        require(not synthetic_nrre_errors and synthetic_nrre_record is not None and int(synthetic_nrre_record["node_count"]) == 2 and float(synthetic_nrre_record["cnvv_to_cnvc"]) == 0.5, f"离线自测失败：合成 NRRE 解析错误 {synthetic_nrre_errors}")  # 固定文件名、头部、节点数、六分量和残差比行为。
        seed_path = temporary_root / "seed.txt"  # 定位模拟准备账本已保护的既有工件。
        seed_path.write_text("准备字节\n", encoding="utf-8", newline="\n")  # 仅在临时目录创建最小准备原件。
        prepared_entries = {"seed.txt": sha256_file(seed_path)}  # 构造一项模拟启动前准备谱系。
        virtual_path = temporary_root / "virtual.json"  # 定位模拟待发布最终机器工件。
        ledger_path = temporary_root / "final.sha256"  # 定位模拟非自引用追加账本。
        virtual_text = render_json({"status": "SELF_TEST"})  # 渲染稳定模拟 JSON 供虚拟摘要测试。
        ledger_text, ledger_count = build_appended_ledger(temporary_root, prepared_entries, {virtual_path: virtual_text}, ledger_path)  # 验证准备条目保留、既有 NRRE 纳入和虚拟工件预哈希。
        require(ledger_count == 3 and prepared_entries["seed.txt"] in ledger_text, "离线自测失败：追加账本没有同时覆盖准备、NRRE 和虚拟工件")  # 固定最终账本全量且非自引用的最小行为。
        write_new_batch({virtual_path: virtual_text, ledger_path: ledger_text})  # 验证同卷排他暂存、fsync、硬链接和删暂存成功路径。
        require(virtual_path.read_text(encoding="utf-8", errors="strict") == virtual_text and ledger_path.read_text(encoding="utf-8", errors="strict") == ledger_text, "离线自测失败：排他发布后字节不一致")  # 逐字节复核模拟发布内容。
        repeat_rejection = expect_runtime_error(lambda: write_new_batch({virtual_path: virtual_text}), "重复覆盖最终工件")  # 验证第二次发布在写出任何暂存字节前失败关闭。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 严格读取本工具完整源码供语法、禁止动作和逐行中文注释自审计。
    syntax_tree = ast.parse(source_text, filename=str(SCRIPT_PATH))  # 解析完整抽象语法树，兼作不生成 pyc 的语法检查。
    forbidden_calls = sorted({name for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) for name in [ast_call_name(node)] if name in FORBIDDEN_CALL_NAMES})  # 收集主动进程处置、shell 和子进程绕行调用名。
    require(not forbidden_calls, f"离线自测失败：发现禁止的主动进程或子进程调用 {forbidden_calls}")  # 任一 kill、terminate、signal 或启动入口出现都失败。
    uncommented_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if line.strip() and "#" not in line]  # 收集全部非空且缺少注释标记的物理源码行。
    require(not uncommented_lines, f"离线自测失败：存在缺少逐行中文注释的源码行 {uncommented_lines[:20]}")  # 强制每一行有效代码都有对应说明。
    non_chinese_comment_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if "#" in line and re.search(r"[\u4e00-\u9fff]", line.split("#", 1)[1]) is None]  # 收集首个注释段不含中文字符的物理行。
    require(not non_chinese_comment_lines, f"离线自测失败：存在不含中文的注释行 {non_chinese_comment_lines[:20]}")  # 落实默认中文逐行注释合同。
    return {"status": "OFFLINE_SELF_TESTS_PASSED", "tool_sha256": sha256_file(SCRIPT_PATH), "ledger_malformed_rejected": bool(ledger_rejection), "synthetic_static_sequence_passed": bool(synthetic_sequence["all_checks_passed"]), "synthetic_cnvtol_detected": True, "synthetic_natural_nonconvergence_detected": True, "synthetic_native_abt_detected": True, "all_eight_classifications_passed": observed_statuses == expected_statuses, "synthetic_nrre_parsed": True, "exclusive_publish_and_repeat_rejection_passed": bool(repeat_rejection), "forbidden_process_calls": forbidden_calls, "uncommented_line_count": len(uncommented_lines), "non_chinese_comment_line_count": len(non_chinese_comment_lines), "current_run_reads_performed": False, "current_run_writes_performed": False, "solver_process_scan_performed": False, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回机器可读且明确证明未访问当前运行、未扫描进程、未尝试 MAPDL 的完整离线自测摘要。


def parse_arguments() -> argparse.Namespace:  # 无业务输入并返回调用者必须显式提供的唯一 run-dir 参数对象。
    parser = argparse.ArgumentParser(description="只读验证并不可覆盖封存 C10 A0 直接空间重力斜坡静力诊断；本工具绝不启动、终止或控制 MAPDL 进程。")  # 创建仅含一个业务参数的命令行解析器。
    parser.add_argument("--run-dir", required=True, type=str, help="A0 运行目录；保留值 __SELF_TEST__ 仅执行系统临时目录离线自测。")  # 要求调用者显式给出真实运行或唯一离线哨兵，避免隐式选最新 run。
    return parser.parse_args()  # 返回 argparse 已验证参数对象，除标准帮助外没有其他业务开关。


def main() -> int:  # 无显式参数并返回进程退出码；离线哨兵短路自测，其他值才进入真实运行终结。
    arguments = parse_arguments()  # 解析唯一 run-dir 字符串而不访问任何运行目录。
    if str(arguments.run_dir) == SELF_TEST_SENTINEL:  # 唯一哨兵必须在路径解析、进程扫描和 ultra_runs 访问之前短路。
        print(render_json(run_offline_self_tests()), end="")  # 将完整离线自测摘要写到标准输出供人工和自动化核验。
        return 0  # 自测全部通过时返回零且没有当前运行读写或 MAPDL 行为。
    result = finalize_run(Path(str(arguments.run_dir)))  # 只有真实路径才执行稳定终态验证、外部 QA 和不可覆盖封板。
    print(render_json(result), end="")  # 输出最终状态、工件路径和摘要，便于调用者定位审计包。
    return 0  # 五项最终工件已发布且回读闭合后返回零。


if __name__ == "__main__":  # 仅当本文件作为脚本直接执行时进入命令行主流程。
    raise SystemExit(main())  # 将主函数整数返回值转换为标准进程退出码。
