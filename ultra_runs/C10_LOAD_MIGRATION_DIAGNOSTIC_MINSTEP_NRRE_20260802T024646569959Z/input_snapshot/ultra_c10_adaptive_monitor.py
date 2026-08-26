from __future__ import annotations  # 启用延迟类型注解，避免运行时求值前向类型并保持 Python 版本兼容。

import argparse  # 解析调用者显式给出的唯一自适应迁移运行目录或完全离线自检开关。
import ast  # 解析当前监控器源码抽象语法树，离线证明所有 terminate、kill 和信号动作调用均不存在。
import hashlib  # 复算启动认领原件摘要并与真实 PID 启动记录闭合。
import json  # 读取冻结 JSON 身份并持续写出机器可审计的样本与终态。
import os  # 对十字节有效 ABT 载荷执行 flush 和 fsync，确保原生请求字节真实落盘。
import re  # 在 MAPDL 增量日志中识别方程数和有限集合的硬停短语。
import tempfile  # 只在操作系统临时目录创建离线 ABT 回归样本，绝不触碰任何实际运行目录。
import time  # 使用单调时钟计算低内存持续时间和只读采样间隔，不承担进程处置宽限逻辑。
from datetime import datetime, timezone  # 生成不受本地时区或夏令时影响的 UTC 时间戳。
from pathlib import Path  # 安全处理含中文的运行、求解和日志绝对路径。
from typing import Any, TextIO  # 标注异构 JSON 对象与持续打开的 JSONL 文本句柄。

import psutil  # 只读采集物理内存、磁盘、精确进程树和工作集，不调用任何主动进程处置接口。


SCRIPT_PATH = Path(__file__).resolve()  # 固定实际执行监控器源码路径供自检、启动认领和摘要复核使用。
RUNS_ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs")  # 冻结唯一允许监控的全桥运行根，阻断任意目录读取或 ABT 写入。
ADAPTIVE_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结允许本监控器附着的自适应迁移子类型。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结已通过单层 TYPE72 微验证与 LS1 复现的全桥方程数。
SAMPLE_INTERVAL_SECONDS = 10.0  # 每十秒采集一次资源、进程和增量日志，兼顾及时性与超大 OUT 的 I/O 开销。
PROCESS_EXIT_EMPTY_SAMPLES = 2  # 连续两个采样周期找不到本 job 进程才判定进程树退出，避免包装器交接瞬间误判。
POST_EXIT_STABILITY_TIMEOUT_SECONDS = 60.0  # 进程树退出后最多等待六十秒让 OUT/ERR/MNTR 稳定且 lock 消失，超时写阻断终态而不冒充自然完成。
IMMEDIATE_RAM_STOP_BYTES = 512 * 1024**2  # 可用物理内存低于 512 MiB 时立即请求 MAPDL 安全中止。
SUSTAINED_RAM_STOP_BYTES = 1024**3  # 可用物理内存低于 1 GiB 时进入持续计时，而不是因单点抖动立即中止。
SUSTAINED_RAM_STOP_SECONDS = 60.0  # 低于 1 GiB 连续六十秒才触发硬停，和启动记录合同完全一致。
DISK_STOP_BYTES = 32 * 1024**3  # D 盘空余低于 32 GiB 时立即中止，保留数据库和系统写盘余量。
NATIVE_ABORT_WAIT_ONLY = True  # 冻结硬事件后只允许提交有效 MAPDL 原生 ABT 并继续只读等待自然退出。
ACTIVE_PROCESS_DISPOSITION_ALLOWED = False  # 工程安全政策明确禁止监控器主动 terminate、kill 或发送进程信号。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 冻结 MAPDL 2026 R1 认可的首行 nonlinear 关键字及单一 LF，共十个 ASCII 字节。
NATIVE_ABORT_PAYLOAD_LENGTH = 10  # 冻结有效 ABT 载荷的精确字节数，阻断空文件、CRLF 或附加说明混入。
NATIVE_ABORT_PAYLOAD_HEX = "6e6f6e6c696e6561720a"  # 冻结十字节载荷的逐字节十六进制表示供机器审计和回读比较。
NATIVE_ABORT_PAYLOAD_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结有效载荷 SHA-256，避免仅凭可见文本遗漏换行差异。
FORBIDDEN_PROCESS_ACTION_CALL_NAMES = {"kill", "terminate", "send_signal", "taskkill", "TerminateProcess"}  # 离线 AST 审计拒绝任何主动结束、强制结束或发信号调用。
FORBIDDEN_PROCESS_ACTION_FUNCTION_NAMES = {"terminate_exact_processes", "kill_exact_processes", "force_process_disposition"}  # 离线 AST 审计同时拒绝旧强杀帮助函数或同义处置入口重新出现。
LOG_CARRY_CHARACTERS = 8192  # 为跨增量读取边界的完整 MAPDL 消息块保留八千一百九十二字符尾部，避免标题与硬短语被切断漏检。
SOLVER_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 限定 MAPDL 与 MPI 进程名集合，排除普通 Python 和桌面进程。
EQUATION_PATTERN = re.compile(r"^\s*NUMBER\s+OF\s+EQUATIONS\s*=\s*(\d+)", re.IGNORECASE | re.MULTILINE)  # 只匹配 MAPDL 行首每次矩阵组装打印的十进制方程数，避免命中输入注释。
SIGNED_NUMBER_PATTERN = r"[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?"  # 定义 MAPDL 主元输出允许的整数、小数和科学计数词法。
MINIMUM_PIVOT_PATTERN = re.compile(rf"^\s*SPARSE\s+SOLVER\s+MINIMUM\s+PIVOT\s*=\s*({SIGNED_NUMBER_PATTERN})", re.IGNORECASE | re.MULTILINE)  # 只解析非 absolute-value 行首稀疏求解器最小主元，正值不设临时阈值。
MESSAGE_HEADER_PATTERN = re.compile(r"^\s*\*\*\*\s+(?:WARNING|ERROR|FATAL)\s+\*\*\*", re.IGNORECASE | re.MULTILINE)  # 识别真实 MAPDL 消息块标题供 OUT 输入回显隔离。
HARD_TEXT_PATTERNS = [("MAPDL_FATAL", re.compile(r"^\s*\*\*\*\s+FATAL\s+\*\*\*", re.IGNORECASE | re.MULTILINE)), ("SMALL_EQUATION_SOLVER_PIVOT", re.compile(r"(?:VERY\s+)?SMALL\s+(?:EQUATION\s+SOLVER\s+)?PIVOT", re.IGNORECASE)), ("ZERO_PIVOT", re.compile(r"(?:ZERO\s+PIVOT|PIVOT\s+TERM[^\r\n]{0,80}\sZERO)", re.IGNORECASE)), ("NEGATIVE_PIVOT", re.compile(r"NEGATIVE\s+PIVOT", re.IGNORECASE)), ("CNVTOL_IGNORED", re.compile(r"THE\s+CNVTOL\s+COMMAND\s+IS\s+IGNORED", re.IGNORECASE)), ("CNVTOL_INTERNALLY_RESET", re.compile(r"INTERNALLY\s+RESET\s+TO\s+CNVTOL\s+TOLERANCE", re.IGNORECASE))]  # 只批准行首 FATAL 和消息块内明确坏主元/CNVTOL失效短语；普通 ERROR、NCNV、高残差与 BEGIN BISECTION 均不在此集合。


def require(condition: bool, message: str) -> None:  # 接收布尔门与失败说明；失败时中止监控器且不触碰任何求解进程。
    if not condition:  # 仅在目录、身份或冻结合同不满足时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确异常，防止监控器附着到错误 job 或写出虚假样本。


def utc_now() -> str:  # 无输入并返回带时区的 ISO-8601 UTC 时间文本。
    return datetime.now(timezone.utc).isoformat()  # 每次调用独立取时，使样本和动作顺序可审计。


def read_json(path: Path) -> dict[str, Any]:  # 接收 JSON 路径并返回经过顶层对象检查的字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 读取前拒绝缺失、目录或错误路径。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 以严格 UTF-8 解析完整文本，禁止静默替换身份字符。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 阻断数组或标量冒充启动身份。
    return payload  # 返回已验证的异构键值对象。


def sha256_file(path: Path) -> str:  # 接收普通文件路径并返回完整字节的 SHA-256 小写摘要。
    digest = hashlib.sha256()  # 为当前文件创建独立摘要状态。
    with path.open("rb") as handle:  # 以二进制只读方式打开，避免换行和编码转换。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 每次读取一 MiB 直至文件末尾，限制峰值内存。
            digest.update(chunk)  # 把当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回六十四位小写十六进制摘要。


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:  # 接收目标和对象，并以不可覆盖方式创建稳定 JSON。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 保留中文、拒绝非有限数并固定两空格缩进和末尾换行。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用操作系统排他创建，禁止第二监控器覆盖终态或启动记录。
        handle.write(rendered)  # 一次写入已经完整序列化的有效 JSON 字节。


def append_json_line(handle: TextIO, payload: dict[str, Any]) -> None:  # 接收已排他打开的 JSONL 句柄和单个样本对象并立即持久化。
    handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")  # 以单行紧凑 JSON 保存一个完整样本，避免崩溃时破坏先前行。
    handle.flush()  # 每个样本后刷新 Python 缓冲，使资源硬停前的证据尽快落盘。


def file_snapshot(path: Path) -> dict[str, Any]:  # 接收可能尚不存在的运行文件并返回存在性、大小和纳秒修改时刻快照。
    if not path.is_file():  # 启动早期或正常退出清理后的临时文件允许不存在。
        return {"exists": False, "size_bytes": 0, "mtime_ns": None}  # 使用固定字段表达缺失而不访问不存在文件状态。
    stat = path.stat()  # 一次读取文件大小与纳秒修改时刻，减少跨字段竞争。
    return {"exists": True, "size_bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}  # 返回可直接写入 JSON 和比较稳定性的最小状态。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收冻结参数数组和标志并返回其唯一后继值。
    indices = [index for index, value in enumerate(arguments) if value.lower() == flag.lower()]  # 忽略大小写查找全部标志位置。
    require(len(indices) == 1, f"启动参数 {flag} 出现 {len(indices)} 次，预期 1")  # 缺失或重复均会造成路径或 job 身份歧义。
    index = indices[0]  # 读取已经确认唯一的标志下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止数组越界或空参数。
    return arguments[index + 1]  # 返回求解器真实采用的相邻参数值。


def command_has_flag_value(arguments: list[str], flag: str, expected: str, path_value: bool) -> bool:  # 接收真实命令行、标志、期望值和路径语义并返回唯一相邻值是否精确匹配。
    indices = [index for index, value in enumerate(arguments) if value.lower() == flag.lower()]  # 查找忽略大小写的全部标志位置。
    if len(indices) != 1 or indices[0] + 1 >= len(arguments):  # 缺失、重复或没有后继值均不能作为进程归属证据。
        return False  # 返回不匹配而不抛错，使无关系统进程只进入披露列表。
    observed = arguments[indices[0] + 1]  # 读取真实命令行中的唯一相邻参数值。
    if path_value:  # `-dir` 等路径参数需要先规范化再执行 Windows 不区分大小写比较。
        try:  # 无效路径文本不应使全局进程枚举失败。
            return str(Path(observed).resolve()).casefold() == str(Path(expected).resolve()).casefold()  # 仅规范绝对路径完全相同时返回真。
        except (OSError, RuntimeError):  # 捕获路径规范化失败或异常循环。
            return False  # 无法证明相等时保持 fail-closed 的非归属结果。
    return observed.casefold() == expected.casefold()  # 普通 jobname 参数要求完整文本相等而不是宽松子串命中。


def compact_process_record(process: psutil.Process, parent_pid: int, name: str, command_line: list[str], create_time: float, executable: str) -> dict[str, Any]:  # 接收已验证进程字段并返回可防 PID 回收的审计快照。
    try:  # 尝试一次读取内存和 CPU 指标，进程退出或权限变化时允许回退为零。
        memory_info = process.memory_info()  # 获取同一瞬间的 RSS 与 VMS，减少两次系统调用竞争。
        cpu_times = process.cpu_times()  # 获取用户态和内核态 CPU 秒数供运行活性诊断。
        resident_bytes = int(memory_info.rss)  # 记录物理驻留工作集字节数用于资源诊断而非总内存门计算。
        virtual_bytes = int(memory_info.vms)  # 记录虚拟地址空间字节数用于发现异常映射增长。
        cpu_seconds = float(cpu_times.user + cpu_times.system)  # 汇总用户态与内核态 CPU 秒数供样本趋势复核。
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # 捕获采样瞬间进程消失、拒绝访问或僵尸状态。
        resident_bytes = 0  # 无法读取时使用零并保留 PID、创建时刻和命令身份，避免监控器崩溃。
        virtual_bytes = 0  # 无法读取时把虚拟内存显式记零而不是省略字段。
        cpu_seconds = 0.0  # 无法读取时把 CPU 累计显式记零并在下一样本重试。
    return {"pid": int(process.pid), "ppid": parent_pid, "name": name, "create_time_epoch_seconds": create_time, "executable": executable, "rss_bytes": resident_bytes, "vms_bytes": virtual_bytes, "cpu_seconds": cpu_seconds, "command_line": command_line}  # 返回足以复核 job 归属、PID 再用和资源占用的字段集。


def solver_process_snapshot(jobname: str, solver_dir: Path, main_identity: dict[str, Any], bound_identities: dict[int, float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, float]]:  # 接收 job、工作目录、启动根身份和既有绑定并返回相关、无关进程及更新绑定。
    raw_records: dict[int, tuple[psutil.Process, int, str, list[str], float, str]] = {}  # 初始化 PID 到进程对象、父 PID、名称、参数、创建时刻和可执行路径的映射。
    for process in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time", "exe"]):  # 一次遍历系统进程并只请求身份与监控所需只读字段。
        try:  # 单个系统进程可能在迭代期间退出或拒绝命令行访问。
            name = str(process.info.get("name") or "").lower()  # 规范化进程名用于批准集合精确匹配。
            if name not in SOLVER_PROCESS_NAMES:  # 普通应用和监控器自身不进入后续归属或处置集合。
                continue  # 跳过非 MAPDL/MPI 进程，缩小安全边界。
            command_line = [str(value) for value in (process.info.get("cmdline") or [])]  # 保留真实参数数组用于 `-j/-dir` 成对核验。
            parent_pid = int(process.info.get("ppid") or 0)  # 读取父 PID，缺失时使用零表示未知根。
            create_time = float(process.info.get("create_time") or process.create_time())  # 冻结进程创建时刻以阻断 PID 回收误绑定。
            executable = str(Path(str(process.info.get("exe") or process.exe())).resolve())  # 规范化真实二进制路径供启动根和动作前复核。
            raw_records[int(process.pid)] = (process, parent_pid, name, command_line, create_time, executable)  # 保存当前可访问的批准进程记录。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, RuntimeError):  # 采样竞争或路径异常不应扩大归属范围。
            continue  # 忽略本次无法稳定证明身份的单个进程并在下一周期重试。
    related_pids: set[int] = set()  # 初始化明确属于本 job 的进程 PID 集合。
    main_pid = int(main_identity["pid"])  # 从启动记录读取可信包装器 PID。
    main_create_time = float(main_identity["create_time_epoch_seconds"])  # 从启动记录读取包装器创建时刻供 PID 再用核验。
    if main_pid in raw_records and abs(raw_records[main_pid][4] - main_create_time) <= 0.001:  # 只有 PID 和创建时刻都相同时才把包装器作为可信根。
        related_pids.add(main_pid)  # 纳入精确 Popen 返回身份而不是仅凭相同 PID。
    for pid, (_, _, _, command_line, create_time, _) in raw_records.items():  # 遍历全部批准进程寻找双参数精确归属或既有绑定身份。
        exact_command_identity = command_has_flag_value(command_line, "-j", jobname, False) and command_has_flag_value(command_line, "-dir", str(solver_dir), True)  # 同时精确匹配 jobname 与 solver目录才允许孤儿进程重新归属。
        preserved_bound_identity = pid in bound_identities and abs(bound_identities[pid] - create_time) <= 0.001  # 先前已由可信父子链绑定且创建时刻未变的进程保持归属。
        if exact_command_identity or preserved_bound_identity:  # 两种证据任一成立即可纳入，单独名称、job子串或目录子串均不够。
            related_pids.add(pid)  # 保存已经严格证明属于本运行的求解进程 PID。
    changed = True  # 初始化父子闭包迭代标志，保证多层 MPI/solver 子进程均被包含。
    while changed:  # 反复扩展直到没有新的批准求解进程以相关 PID 为父。
        changed = False  # 每轮先假定闭包已经稳定。
        for pid, (_, parent_pid, _, _, _, _) in raw_records.items():  # 检查每个批准进程的父 PID 是否属于当前本 job 集合。
            if pid not in related_pids and parent_pid in related_pids:  # 只纳入尚未记录且父进程已确定属于本 job 的子进程。
                related_pids.add(pid)  # 扩展本 job 精确进程树。
                changed = True  # 标记需要再迭代一轮捕获更深后代。
    updated_bound_identities = dict(bound_identities)  # 复制既有 PID/创建时刻绑定，保留包装器退出后的孤儿身份。
    for pid in related_pids:  # 把本轮新发现的可信后代加入跨样本绑定。
        updated_bound_identities[pid] = raw_records[pid][4]  # 保存创建时刻，未来相同 PID 不同创建时刻不会误绑定。
    related = [compact_process_record(raw_records[pid][0], raw_records[pid][1], raw_records[pid][2], raw_records[pid][3], raw_records[pid][4], raw_records[pid][5]) for pid in sorted(related_pids)]  # 按 PID 稳定排序并生成本 job 防再用进程快照。
    unrelated = [compact_process_record(record[0], record[1], record[2], record[3], record[4], record[5]) for pid, record in sorted(raw_records.items()) if pid not in related_pids]  # 记录启动后出现但不属于本 job 的求解进程，披露而不擅自中止。
    return related, unrelated, updated_bound_identities  # 返回安全处置范围、仅审计并发范围和跨样本可信身份绑定。


def read_log_increment(path: Path, offset: int, carry: str) -> tuple[int, str, str, int]:  # 接收日志、旧偏移和边界尾文并返回新偏移、尾文、可扫描文本及当前大小。
    if not path.is_file():  # 求解器启动早期 OUT 或 ERR 尚未创建属于正常状态。
        return offset, carry, "", 0  # 保持旧偏移和尾文并报告零大小，不伪造硬错误。
    current_size = int(path.stat().st_size)  # 读取当前原始字节长度用于截断检测和样本记录。
    require(current_size >= offset, f"运行日志在监控期间缩短或被替换：{path}")  # 日志逆向缩短会破坏增量证据，必须 fail-closed。
    with path.open("rb") as handle:  # 以二进制只读模式读取新增区间，避免未知本地编码异常。
        handle.seek(offset)  # 精确跳到上一样本已处理的字节边界。
        new_bytes = handle.read()  # 读取当前新增尾段；每十秒一次且 OUT 增量远小于全文件。
    decoded = new_bytes.decode("latin-1", errors="strict")  # MAPDL 关键消息为 ASCII，Latin-1 一一映射全部字节并避免替换字符破坏偏移语义。
    searchable = carry + decoded  # 拼接上轮尾部以捕获跨读取边界的硬停短语和方程行。
    new_carry = searchable[-LOG_CARRY_CHARACTERS:]  # 只保留有限尾文，避免长期监控内存增长。
    return current_size, new_carry, searchable, current_size  # 返回下一偏移、下一尾文、本轮扫描文本和当前文件大小。


def scan_new_text(source: str, text_value: str, seen_event_keys: set[str]) -> tuple[list[dict[str, Any]], list[int]]:  # 接收日志来源、新文本和去重集合并返回新硬事件及方程数。
    events: list[dict[str, Any]] = []  # 初始化本轮首次发现的硬停事件列表。
    equation_counts = [int(value) for value in EQUATION_PATTERN.findall(text_value)]  # 提取本轮含边界尾文的全部组装方程数。
    signed_pivots = [float(value) for value in MINIMUM_PIVOT_PATTERN.findall(text_value)]  # 解析行首非绝对值稀疏求解器最小主元，正值仅记录不触发。
    for equation_count in equation_counts:  # 逐个检查每次组装是否保持单层 TYPE72 冻结秩。
        if equation_count != EXPECTED_EQUATION_COUNT:  # 任何数量漂移都表示拓扑、约束或模型状态已偏离批准输入。
            event_key = f"EQUATION_COUNT_DRIFT:{source}:{equation_count}"  # 构造来源与异常数值共同确定的去重键。
            if event_key not in seen_event_keys:  # 边界尾文可能重复上一轮命中，只有首次写入动作证据。
                seen_event_keys.add(event_key)  # 在返回前登记以保证后续样本不重复触发中止。
                events.append({"kind": "EQUATION_COUNT_DRIFT", "source": source, "observed": equation_count, "expected": EXPECTED_EQUATION_COUNT, "detected_at_utc": utc_now()})  # 保存异常秩及冻结期望值。
    for pivot_value in signed_pivots:  # 逐个检查明确带符号的稀疏求解器最小主元数值。
        if pivot_value <= 0.0:  # 仅零或负数触发；任何正但偏小值必须由 MAPDL 明确 small-pivot 消息判定。
            event_key = f"NONPOSITIVE_SPARSE_SOLVER_PIVOT:{source}:{pivot_value:.17g}"  # 构造来源和精确浮点文本值共同确定的去重键。
            if event_key not in seen_event_keys:  # 边界尾文重复解析同一主元时只形成一次硬事件。
                seen_event_keys.add(event_key)  # 登记事件以阻止重复中止动作。
                events.append({"kind": "NONPOSITIVE_SPARSE_SOLVER_PIVOT", "source": source, "observed": pivot_value, "threshold": 0.0, "detected_at_utc": utc_now()})  # 保存非正主元和零阈值。
    for kind, pattern in HARD_TEXT_PATTERNS:  # 逐类扫描有限、显式且不包含普通高残差/二分的硬停短语。
        for match in pattern.finditer(text_value):  # 保留同一日志中不同类别或不同文本位置的首次证据。
            message_prefix = text_value[max(0, match.start() - LOG_CARRY_CHARACTERS):match.start()]  # 取得当前命中前有限窗口供 OUT 消息块标题验证。
            message_scoped_kind = kind != "MAPDL_FATAL"  # FATAL 自身已用行首标题锚定，其余短语必须位于真实消息块内。
            if source.upper() == "OUT" and message_scoped_kind and MESSAGE_HEADER_PATTERN.search(message_prefix) is None:  # OUT 会回显输入，缺少前置 WARNING/ERROR/FATAL 标题的短语不得作为硬事件。
                continue  # 忽略输入注释或命令回显中的相同文字，同时 ERR 仍可直接接受原生消息。
            excerpt = " ".join(text_value[max(0, match.start() - 80):match.end() + 160].split())[:320]  # 截取规范化上下文供人工确认且限制 JSON 体积。
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()  # 对摘录生成稳定摘要用于边界重读去重。
            event_key = f"{kind}:{source}:{excerpt_hash}"  # 构造类别、来源与文本共同确定的唯一事件键。
            if event_key not in seen_event_keys:  # 只有未记录的新硬事件进入动作列表。
                seen_event_keys.add(event_key)  # 立即登记，避免同一轮或下一轮重复请求中止。
                events.append({"kind": kind, "source": source, "excerpt": excerpt, "excerpt_sha256": excerpt_hash, "detected_at_utc": utc_now()})  # 保存类别、来源、有限摘录及摘要。
    return events, equation_counts  # 返回本轮新事件和全部观察方程数供样本与终态汇总。


def native_abort_evidence_template(abort_path: Path) -> dict[str, Any]:  # 接收唯一 ABT 路径并返回尚未请求时的完整载荷合同、文件动作和回读证据初值。
    return {"abort_file": str(abort_path), "abort_file_action": "NOT_REQUESTED", "request_contract_satisfied": False, "native_abort_payload_text_ascii": NATIVE_ABORT_PAYLOAD.decode("ascii"), "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_payload_contract_verified_before_write": False, "native_abort_created_exclusively": False, "native_abort_created_at_utc": None, "native_abort_existing_file_preserved": False, "native_abort_write_returned_bytes": 0, "native_abort_payload_written_fully": False, "native_abort_flush_completed": False, "native_abort_fsync_completed": False, "native_abort_flush_and_fsync_completed": False, "native_abort_readback_length_bytes": None, "native_abort_readback_hex": None, "native_abort_readback_sha256": None, "native_abort_readback_matches_contract": False, "native_abort_error": None}  # 明确区分新建有效请求、既有有效请求、既有无效请求和写盘异常，禁止只凭文件存在性认定停机已提交。


def record_native_abort_readback(evidence: dict[str, Any], readback_payload: bytes) -> None:  # 接收可变证据对象和实际回读字节，无返回值并填充长度、十六进制、摘要及四项一致性结论。
    evidence["native_abort_readback_length_bytes"] = len(readback_payload)  # 保存回读长度，批准值必须精确为十字节。
    evidence["native_abort_readback_hex"] = readback_payload.hex()  # 保存逐字节十六进制以显式区分 LF、CRLF 和空文件。
    evidence["native_abort_readback_sha256"] = hashlib.sha256(readback_payload).hexdigest()  # 保存回读内容摘要供终态和离线测试复算。
    evidence["native_abort_readback_matches_contract"] = readback_payload == NATIVE_ABORT_PAYLOAD and len(readback_payload) == NATIVE_ABORT_PAYLOAD_LENGTH and evidence["native_abort_readback_hex"] == NATIVE_ABORT_PAYLOAD_HEX and evidence["native_abort_readback_sha256"] == NATIVE_ABORT_PAYLOAD_SHA256  # 同时核对字节、长度、hex 和 SHA，任一不符均不得声称有效请求。


def request_native_abort(solver_dir: Path, jobname: str, evidence: dict[str, Any]) -> dict[str, Any]:  # 接收冻结工作目录、jobname 和动作证据，排他写入或只读核验 ABT 后返回同一证据对象。
    abort_path = solver_dir / f"{jobname}.abt"  # 按 MAPDL 批处理约定构造唯一 jobname.abt 路径。
    require(abort_path == Path(str(evidence["abort_file"])), "ABT 证据路径与冻结 solver/jobname 目标不一致")  # 阻断调用者把动作证据绑定到另一文件。
    require(solver_dir.is_dir(), f"ABT solver 目录不存在：{solver_dir}")  # 禁止隐式创建错误目录层级或写出批准运行边界。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n", "ABT 载荷字面值偏离 nonlinear 加 LF 合同")  # 在打开目标前核对精确字节字面值，常量漂移时保持零动作。
    require(len(NATIVE_ABORT_PAYLOAD) == NATIVE_ABORT_PAYLOAD_LENGTH, "ABT 载荷长度常量与真实字节不一致")  # 在打开目标前阻断空文件、CRLF 和附加字符。
    require(NATIVE_ABORT_PAYLOAD.hex() == NATIVE_ABORT_PAYLOAD_HEX, "ABT 载荷十六进制常量与真实字节不一致")  # 在打开目标前逐字节关闭可见文本和编码歧义。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256, "ABT 载荷 SHA-256 常量与真实字节不一致")  # 在打开目标前以独立摘要关闭换行或编码漂移。
    evidence["native_abort_payload_contract_verified_before_write"] = True  # 只有四项精确合同全部通过才允许尝试取得文件排他创建权。
    try:  # 首选操作系统排他创建，若并发控制器已抢先创建则转为只读核验且绝不覆盖。
        with abort_path.open("x+b") as abort_handle:  # 使用排他创建且可回读的二进制模式，阻断文本换行转换与既有文件截断。
            evidence["native_abort_created_exclusively"] = True  # 取得文件描述符排他创建权后立即记录真实动作，即使后续步骤失败也不伪称未创建。
            evidence["native_abort_created_at_utc"] = utc_now()  # 记录排他创建成功的 UTC 时刻供终态审计。
            written_bytes = abort_handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入冻结十字节载荷并保留底层返回值。
            evidence["native_abort_write_returned_bytes"] = written_bytes  # 保存实际写入调用报告的字节数。
            require(written_bytes == NATIVE_ABORT_PAYLOAD_LENGTH, f"ABT 载荷短写：{written_bytes}/{NATIVE_ABORT_PAYLOAD_LENGTH} 字节")  # 任何短写均失败关闭且不声称请求有效。
            evidence["native_abort_payload_written_fully"] = True  # 仅在写调用确认十字节完整接收后标记完整写入。
            abort_handle.flush()  # 把 Python 用户态缓冲全部提交到操作系统文件句柄。
            evidence["native_abort_flush_completed"] = True  # 只有 flush 正常返回才记录用户态缓冲已清空。
            os.fsync(abort_handle.fileno())  # 请求操作系统把有效 ABT 内容同步到持久存储，再进行回读证明。
            evidence["native_abort_fsync_completed"] = True  # 只有 fsync 正常返回才记录磁盘同步已完成。
            evidence["native_abort_flush_and_fsync_completed"] = True  # 合并记录两层同步均完成供终态直接判定。
            abort_handle.seek(0)  # 把同一排他文件描述符移回首字节，避免另开句柄产生路径替换竞态。
            record_native_abort_readback(evidence, abort_handle.read())  # 从同一文件对象回读全部字节并填充四项一致性证据。
            require(bool(evidence["native_abort_readback_matches_contract"]), "新建 ABT 回读字节不满足 nonlinear 加 LF 精确合同")  # 回读不一致时失败关闭并保留已发生动作事实。
        evidence["abort_file_action"] = "ABORT_FILE_CREATED_VALID_CONTRACT"  # 只有排他创建、完整写入、同步和回读全部成功才记录新建有效请求。
        evidence["request_contract_satisfied"] = True  # 标记 MAPDL 原生请求字节合同已由本监控器完整建立。
        return evidence  # 返回新建有效请求的全阶段证据。
    except FileExistsError:  # 并发或此前控制器已创建同名文件时禁止覆盖、截断或补写。
        require(abort_path.is_file(), "既有 ABT 路径不是普通文件")  # 目录或其他对象不能作为原生请求证据。
        existing_payload = abort_path.read_bytes()  # 只读获取既有文件全部字节以判定其是否已满足同一有效合同。
        evidence["native_abort_existing_file_preserved"] = True  # 明确记录监控器没有修改既有 ABT 的任何字节。
        record_native_abort_readback(evidence, existing_payload)  # 对既有内容执行与新建文件完全相同的长度、hex 和摘要核验。
        evidence["abort_file_action"] = "ABORT_FILE_ALREADY_EXISTED_VALID_CONTRACT" if bool(evidence["native_abort_readback_matches_contract"]) else "ABORT_FILE_ALREADY_EXISTED_INVALID_CONTRACT_PRESERVED"  # 区分可依赖的既有原生请求和不可覆盖的无效既有字节。
        evidence["request_contract_satisfied"] = bool(evidence["native_abort_readback_matches_contract"])  # 只有既有字节精确等于 nonlinear 加 LF 才承认请求合同成立。
        return evidence  # 返回只读核验结果，调用者继续等待且永不进入主动进程处置。


def find_forbidden_process_action_nodes(source_text: str) -> dict[str, list[dict[str, int | str]]]:  # 接收完整 Python 源码并返回所有禁止进程动作调用及禁止处置函数定义的位置。
    syntax_tree = ast.parse(source_text, filename=str(SCRIPT_PATH))  # 只解析抽象语法树而不执行源码，检查真实结构而不是注释中的关键词。
    calls: list[dict[str, int | str]] = []  # 初始化主动结束、强杀或发信号调用清单。
    definitions: list[dict[str, int | str]] = []  # 初始化旧强杀帮助函数或同义处置入口定义清单。
    for node in ast.walk(syntax_tree):  # 遍历导入、函数、分支和表达式中的全部语法节点，关闭隐藏路径。
        if isinstance(node, ast.Call):  # 只有调用节点可能直接触发主动进程动作。
            call_name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")  # 同时提取对象方法和直接函数名称，复杂动态调用按空名处理。
            if call_name in FORBIDDEN_PROCESS_ACTION_CALL_NAMES:  # 任一调用名命中冻结禁表即视为源码不合规，不接受所谓不可达分支。
                calls.append({"call_name": call_name, "line_number": int(node.lineno)})  # 保存可定位的调用名和一基行号供修复。
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FORBIDDEN_PROCESS_ACTION_FUNCTION_NAMES:  # 禁止旧处置帮助函数或同义入口仅被保留但暂未调用。
            definitions.append({"function_name": node.name, "line_number": int(node.lineno)})  # 保存禁止定义名称和一基行号供审查。
    return {"calls": sorted(calls, key=lambda finding: int(finding["line_number"])), "definitions": sorted(definitions, key=lambda finding: int(finding["line_number"]))}  # 按源码行号稳定返回两类结果，便于离线测试复现。


def find_comment_policy_violations(source_text: str) -> list[dict[str, int | str]]:  # 接收完整源码并返回缺少同行注释或注释不含中文的非空行清单。
    violations: list[dict[str, int | str]] = []  # 初始化全文件逐行注释规则违规列表。
    for line_number, line in enumerate(source_text.splitlines(), start=1):  # 按一基真实行号遍历源码中的每一物理行。
        if not line.strip():  # 空白分隔行不承载代码、声明或结束结构，无需注释。
            continue  # 跳过空白行并检查下一物理行。
        if "#" not in line:  # 任一非空行缺少井号时即不满足项目逐行注释合同。
            violations.append({"line_number": line_number, "reason": "NONBLANK_LINE_WITHOUT_COMMENT"})  # 记录缺注释行号和稳定原因代码。
            continue  # 当前行没有可继续审查的注释正文，转入下一行。
        comment_text = line.split("#", 1)[1]  # 读取第一个井号之后的全部文本，覆盖正常行尾中文注释和含井号字符串后的说明。
        if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", comment_text) is None:  # 注释正文至少应含一个中日韩统一表意汉字才视为中文说明。
            violations.append({"line_number": line_number, "reason": "COMMENT_WITHOUT_CHINESE"})  # 记录只有英文、符号或空注释的行。
    return violations  # 返回全部违规而不是首项失败，缩短后续修复轮次。


def run_offline_self_test() -> dict[str, Any]:  # 无业务输入并仅在操作系统临时目录执行 ABT 成功、重复、无效既有文件和源码安全回归，返回机器结果。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n", "离线测试发现 ABT 字面值不是 nonlinear 加 LF")  # 独立确认唯一允许载荷字节序列。
    require(len(NATIVE_ABORT_PAYLOAD) == NATIVE_ABORT_PAYLOAD_LENGTH == 10, "离线测试发现 ABT 长度不是十字节")  # 同时核对真实长度、冻结常量和批准值十。
    require(NATIVE_ABORT_PAYLOAD.hex() == NATIVE_ABORT_PAYLOAD_HEX == "6e6f6e6c696e6561720a", "离线测试发现 ABT 十六进制不匹配")  # 逐字节确认 ASCII 内容和单一 LF。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256, "离线测试发现 ABT SHA-256 不匹配")  # 用运行时摘要独立核对冻结身份。
    require(NATIVE_ABORT_WAIT_ONLY is True and ACTIVE_PROCESS_DISPOSITION_ALLOWED is False, "离线测试发现工程安全策略未冻结为只等待且禁止主动进程处置")  # 验证策略常量没有被配置漂移重新开放。
    with tempfile.TemporaryDirectory(prefix="ultra_c10_monitor_offline_selftest_") as temporary_directory_text:  # 创建由运行库自动清理的独立临时目录，绝不解析或写入 ultra_runs。
        temporary_directory = Path(temporary_directory_text).resolve()  # 规范化临时目录供所有虚拟 ABT 路径使用。
        valid_abort_path = temporary_directory / "valid_job.abt"  # 构造不会被 MAPDL 观察的首次排他创建测试文件。
        first_evidence = native_abort_evidence_template(valid_abort_path)  # 初始化首次创建的完整载荷与动作证据。
        request_native_abort(temporary_directory, "valid_job", first_evidence)  # 调用生产同一函数验证排他写入、flush、fsync 和回读路径。
        require(valid_abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "离线有效 ABT 关闭句柄后字节漂移")  # 关闭写句柄后再次独立读取精确十字节载荷。
        require(first_evidence["abort_file_action"] == "ABORT_FILE_CREATED_VALID_CONTRACT", "离线首次 ABT 动作状态不正确")  # 确认新建文件只有全合同通过后才获有效状态。
        require(bool(first_evidence["native_abort_created_exclusively"]), "离线测试缺少 ABT 排他创建成功证据")  # 核对生产函数提交排他创建事实。
        require(bool(first_evidence["native_abort_payload_written_fully"]), "离线测试缺少 ABT 完整写入证据")  # 核对写调用真实返回十字节。
        require(bool(first_evidence["native_abort_flush_and_fsync_completed"]), "离线测试缺少 ABT flush/fsync 完成证据")  # 核对两层同步步骤均正常返回。
        require(bool(first_evidence["native_abort_readback_matches_contract"]), "离线测试缺少 ABT 回读一致证据")  # 核对同句柄回读四项合同全部匹配。
        existing_valid_evidence = native_abort_evidence_template(valid_abort_path)  # 初始化同一路径第二次请求的只读核验证据。
        request_native_abort(temporary_directory, "valid_job", existing_valid_evidence)  # 故意请求同路径第二次创建，验证排他拒绝后只读识别既有有效文件。
        require(existing_valid_evidence["abort_file_action"] == "ABORT_FILE_ALREADY_EXISTED_VALID_CONTRACT", "离线测试未正确识别既有有效 ABT")  # 确认重复控制器不会重写但可承认精确有效载荷。
        require(bool(existing_valid_evidence["native_abort_existing_file_preserved"]) and not bool(existing_valid_evidence["native_abort_created_exclusively"]), "离线测试未证明既有有效 ABT 被只读保留")  # 同时核对无创建权和原字节保留事实。
        require(valid_abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "重复请求改变了既有有效 ABT 字节")  # 证明排他拒绝路径没有截断或补写原文件。
        invalid_abort_path = temporary_directory / "invalid_job.abt"  # 构造既有无效 ABT 只读保留测试路径。
        invalid_payload = b"invalid\n"  # 使用八字节非 MAPDL 合同文本证明监控器不会把任意非空文件误判为有效请求。
        with invalid_abort_path.open("x+b") as invalid_handle:  # 排他创建完全位于临时目录的无效夹具，避免覆盖任何用户文件。
            invalid_written_bytes = invalid_handle.write(invalid_payload)  # 写入冻结八字节无效夹具并保留底层返回值。
            require(invalid_written_bytes == len(invalid_payload), "离线无效 ABT 夹具发生短写")  # 夹具不完整时停止测试，避免得到伪阴性结论。
            invalid_handle.flush()  # 把夹具用户态缓冲提交给操作系统句柄。
            os.fsync(invalid_handle.fileno())  # 同步夹具字节以保证后续只读保留检查稳定。
        existing_invalid_evidence = native_abort_evidence_template(invalid_abort_path)  # 初始化既有无效文件的只读核验证据。
        request_native_abort(temporary_directory, "invalid_job", existing_invalid_evidence)  # 调用生产函数验证无效既有文件不会被覆盖或冒充有效请求。
        require(existing_invalid_evidence["abort_file_action"] == "ABORT_FILE_ALREADY_EXISTED_INVALID_CONTRACT_PRESERVED", "离线测试未正确标记既有无效 ABT")  # 确认无效内容得到显式失败状态。
        require(not bool(existing_invalid_evidence["request_contract_satisfied"]), "离线测试错误承认了无效既有 ABT")  # 无效字节绝不能声称 MAPDL 原生请求合同已成立。
        require(bool(existing_invalid_evidence["native_abort_existing_file_preserved"]) and invalid_abort_path.read_bytes() == invalid_payload, "离线测试改变了既有无效 ABT 字节")  # 证明失败关闭同时尊重不可覆盖证据政策。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 只读获取当前项目源代码供语法、进程动作和注释规则检查。
    ast.parse(source_text, filename=str(SCRIPT_PATH))  # 完整解析当前源文件，证明所有分支和结束结构语法有效且不生成缓存文件。
    forbidden_nodes = find_forbidden_process_action_nodes(source_text)  # 扫描实际调用与函数定义，注释中的术语不会形成误报。
    comment_violations = find_comment_policy_violations(source_text)  # 扫描每一非空物理行的中文注释合同。
    require(not forbidden_nodes["calls"], f"离线测试发现禁止进程动作调用：{forbidden_nodes['calls']}")  # 任何 terminate、kill 或信号调用均使自检失败。
    require(not forbidden_nodes["definitions"], f"离线测试发现禁止进程处置函数定义：{forbidden_nodes['definitions']}")  # 即使暂未调用也不允许强杀帮助函数残留。
    require(not comment_violations, f"离线测试发现逐行中文注释违规：{comment_violations[:20]}")  # 报告前二十项并阻断不合规源码交付。
    return {"status": "PASS", "test_mode": "OFFLINE_TEMPORARY_DIRECTORY_ONLY", "current_run_writes_performed": False, "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "exclusive_create_succeeded": bool(first_evidence["native_abort_created_exclusively"]), "full_write_succeeded": bool(first_evidence["native_abort_payload_written_fully"]), "flush_and_fsync_succeeded": bool(first_evidence["native_abort_flush_and_fsync_completed"]), "readback_matched": bool(first_evidence["native_abort_readback_matches_contract"]), "duplicate_existing_valid_file_preserved": bool(existing_valid_evidence["native_abort_existing_file_preserved"]), "invalid_existing_file_rejected_and_preserved": bool(existing_invalid_evidence["native_abort_existing_file_preserved"]) and not bool(existing_invalid_evidence["request_contract_satisfied"]), "native_abort_wait_only": NATIVE_ABORT_WAIT_ONLY, "active_process_disposition_allowed": ACTIVE_PROCESS_DISPOSITION_ALLOWED, "forbidden_process_action_calls": forbidden_nodes["calls"], "forbidden_process_action_function_definitions": forbidden_nodes["definitions"], "comment_policy_violations": comment_violations}  # 返回可由调用者直接存档的离线回归摘要，明确没有触碰当前运行。


def main() -> None:  # 解析唯一运行、验证启动链、持续监控并排他写出最终硬停状态。
    parser = argparse.ArgumentParser(description="监控 C10 自适应恒总荷载位置迁移；硬事件仅提交有效原生 ABT 并等待自然退出，绝不主动处置进程。")  # 创建不接受 jobname 或路径猜测的安全命令行接口。
    parser.add_argument("--run-dir", required=False, type=Path, help="正常模式下必填、由 ultra_c10_static_execute.py 启动的唯一自适应迁移目录。")  # 为离线自检允许省略路径，正常监控仍由下方显式强制必填。
    parser.add_argument("--self-test", action="store_true", help="仅在操作系统临时目录验证 ABT 字节、排他创建、fsync、回读和无 terminate/kill 源码。")  # 提供不读取、不写入、不停止任何实际运行的离线回归入口。
    arguments = parser.parse_args()  # 解析命令行并由 argparse 拒绝未知参数。
    if bool(arguments.self_test):  # 显式离线模式必须在任何 ultra_runs 路径解析、验证或写入之前短路。
        require(arguments.run_dir is None, "离线自检禁止同时提供 --run-dir")  # 阻断自检携带真实运行路径造成误解或未来回归误触。
        print(json.dumps(run_offline_self_test(), ensure_ascii=False, allow_nan=False))  # 输出单行机器结果且不创建项目内报告或 Python 缓存。
        return  # 离线测试完成后立即退出，保证持续监控和真实 ABT 路径不可达。
    require(arguments.run_dir is not None, "正常监控模式必须显式提供 --run-dir")  # 非自检模式保持唯一目标路径为强制门。
    run_dir = arguments.run_dir.resolve()  # 规范化用户路径以关闭相对段和大小写歧义。
    require(run_dir.is_dir() and run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs：{run_dir}")  # 只允许当前项目直接子运行。
    require(run_dir.name.startswith("C10_LOAD_MIGRATION_DIAGNOSTIC_"), f"运行目录不是迁移诊断族：{run_dir.name}")  # 阻断普通静力、模态或微验证使用本专用硬停合同。
    manifest_path = run_dir / "manifest.json"  # 定位准备阶段冻结清单原件。
    root_status_path = run_dir / "C10_static_status.json"  # 定位准备器根状态以阻断启动后被作废或权限撤销的运行。
    claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领原件。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后含真实 PID 的启动记录。
    manifest = read_json(manifest_path)  # 读取运行输入、作业名和批准子类型。
    root_status = read_json(root_status_path)  # 读取根状态的启动许可、尝试状态和 job 身份。
    claim = read_json(claim_path)  # 读取唯一启动权、资源快照和准备谱系。
    launch = read_json(launch_path)  # 读取真实主 PID 和运行时硬停阈值。
    require(manifest.get("run_name") == run_dir.name and root_status.get("run_name") == run_dir.name and claim.get("run_name") == run_dir.name and launch.get("run_name") == run_dir.name, "根状态、清单、认领或启动记录运行名不一致")  # 关闭跨目录复制错配。
    require(root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("launch_allowed_for_diagnostic") is True and root_status.get("mapdl_execution_attempted") is False and root_status.get("mapdl_started") is False, "根状态不是未尝试且明确允许诊断的准备态")  # 执行器不会改写准备根状态，监控器仍要求其未被事后作废。
    runtime_monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 读取清单冻结的监控器运行内相对路径并规范分隔符。
    require(runtime_monitor_relative == "input_snapshot/ultra_c10_adaptive_monitor.py", "清单监控器快照路径不符合冻结合同")  # 只允许准备账本内固定文件名的监控代码。
    require(SCRIPT_PATH == (run_dir / runtime_monitor_relative).resolve(), "实际调用的监控器不是本运行冻结快照")  # 禁止从可继续编辑的工具源附着已启动求解器。
    require(sha256_file(SCRIPT_PATH) == str(manifest.get("runtime_monitor_script_sha256")), "实际监控器 SHA-256 与清单不一致")  # 关闭准备后运行代码字节漂移。
    require(manifest.get("diagnostic_subtype") == ADAPTIVE_SUBTYPE and claim.get("diagnostic_subtype") == ADAPTIVE_SUBTYPE and launch.get("diagnostic_subtype") == ADAPTIVE_SUBTYPE, "启动链不是批准的 0.05% 自适应迁移")  # 只监控唯一批准子类型。
    require(manifest.get("single_variable_change") == "LS2_NSBMX_200_TO_2000_ONLY" and claim.get("single_variable_change") == manifest.get("single_variable_change") and launch.get("single_variable_change") == manifest.get("single_variable_change"), "启动链唯一变量不是 NSBMX 200→2000")  # 禁止多变量运行借用本监控结论。
    require(claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED" and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "启动认领或最小 PID 记录状态错误")  # 固定先认领、再立即记录 PID、最后独立捕获增强身份的状态顺序。
    require(claim.get("launch_argv") == manifest.get("launch_argv") == launch.get("launch_argv"), "清单、认领和启动参数不一致")  # 要求三方完整参数数组逐项相同。
    require(launch.get("launch_claim_sha256") == sha256_file(claim_path), "真实启动记录引用的认领摘要漂移")  # 证明当前 PID 记录对应当前不可覆盖认领字节。
    require(claim.get("manifest_sha256") == sha256_file(manifest_path) == launch.get("manifest_sha256"), "启动链清单 SHA-256 不一致")  # 关闭清单在认领、Popen 和监控之间的时间窗。
    require(claim.get("prepared_ledger_sha256") == sha256_file(run_dir / "artifact_hashes.sha256") == launch.get("prepared_ledger_sha256"), "启动链准备账本 SHA-256 不一致")  # 关闭全部准备工件谱系身份。
    require(claim.get("prepared_ledger_entry_count") == launch.get("prepared_ledger_entry_count") and int(claim.get("prepared_ledger_entry_count", 0)) >= 27, "启动链准备账本条目数不一致或不足二十七项")  # 固定完整自适应输入、基准、授权和 QA 谱系规模。
    require(claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "认领与真实启动资源快照不一致")  # 防止资源门记录被进程创建后改写。
    require(launch.get("monitor_hard_stops") == {"available_ram_below_bytes": IMMEDIATE_RAM_STOP_BYTES, "available_ram_below_1_gib_sustained_seconds": int(SUSTAINED_RAM_STOP_SECONDS), "disk_free_below_bytes": DISK_STOP_BYTES}, "启动记录硬停阈值与监控器冻结值不一致")  # 禁止脚本和运行记录分叉。
    main_pid = int(launch.get("main_pid", 0))  # 读取执行器 Popen 返回的包装器 PID。
    require(main_pid > 0, "启动记录 main_pid 不是正整数")  # 阻断缺失或伪造的根进程身份。
    process_identity_relative = str(launch.get("process_identity_path", ""))  # 读取最小 PID 记录声明的增强进程身份相对路径。
    require(process_identity_relative == "runtime_process_identity.json", "启动记录增强进程身份路径不符合冻结合同")  # 只允许本运行根下唯一固定文件名，阻断路径逃逸或匿名身份。
    process_identity_path = run_dir / process_identity_relative  # 构造当前运行内增强身份绝对路径。
    main_identity = read_json(process_identity_path)  # 读取执行器在最小启动记录后独立排他写出的防 PID 回收身份。
    require(main_identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED" and main_identity.get("run_name") == run_dir.name and main_identity.get("jobname") == manifest.get("jobname"), "增强主进程身份状态或运行/job身份错误")  # 固定成功捕获语义并关闭跨运行复制。
    require(int(main_identity.get("pid", 0)) == main_pid and main_identity.get("runtime_launch_sha256") == sha256_file(launch_path), "增强主进程身份 PID 或最小启动记录摘要不一致")  # 证明增强身份对应当前不可覆盖 PID 记录。
    jobname = str(manifest.get("jobname", ""))  # 读取冻结 MAPDL jobname 供进程与文件族绑定。
    require(bool(jobname) and jobname == str(claim.get("jobname")) == str(launch.get("jobname")), "启动链 jobname 缺失或不一致")  # 防止监控另一结果文件族。
    launch_argv = [str(value) for value in manifest["launch_argv"]]  # 恢复已经三方核对的参数数组。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and argument_value(launch_argv, "-np") == "1", "启动参数不是唯一批处理 SMP 单进程")  # 固定诊断执行模式且拒绝重复标志。
    require("-dis" not in launch_argv and "-mpi" not in launch_argv, "启动参数意外包含 DMP/MPI")  # 防止未批准并行进程树混入监控身份。
    require(argument_value(launch_argv, "-j") == jobname, "启动参数 -j 与冻结 jobname 不一致")  # 要求结果文件族身份精确相等。
    solver_dir = Path(argument_value(launch_argv, "-dir")).resolve()  # 从实际启动参数定位唯一求解工作目录。
    require(solver_dir == (run_dir / "solver").resolve() and solver_dir.is_dir(), "启动 solver 目录越出本运行或缺失")  # 限制日志读取、中止文件和进程归属目录。
    input_path = Path(argument_value(launch_argv, "-i")).resolve()  # 从实际启动参数定位唯一主输入文件。
    require(input_path == (run_dir / str(manifest["main_input"])).resolve() and input_path.parent == solver_dir and input_path.is_file(), "启动 -i 未指向本运行已哈希主输入")  # 阻断正确 job 却实际执行另一 APDL 文件。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 从实际启动参数定位权威 OUT。
    require(output_path.parent == solver_dir and output_path.name.lower() == f"{jobname}.out".lower(), "OUT 文件身份与 jobname/solver 目录不一致")  # 阻断跨运行日志借用。
    require(str(Path(str(main_identity.get("executable", ""))).resolve()).casefold() == str(Path(launch_argv[0]).resolve()).casefold(), "启动根进程二进制与批准 MAPDL 路径不一致")  # 关闭 Popen 后二进制替换或 PID 复用。
    require([str(value) for value in main_identity.get("command_line", [])] == launch_argv, "启动根进程真实命令行与冻结 launch_argv 不一致")  # 监控前要求操作系统实际参数数组逐项相同。
    launch_started_epoch = datetime.fromisoformat(str(launch["started_at_utc"])).timestamp()  # 把带时区 UTC 启动时间转换为 Unix 秒供创建时刻合理性检查。
    require(float(main_identity.get("create_time_epoch_seconds", 0.0)) >= launch_started_epoch - 10.0, "主进程创建时刻早于启动记录超过十秒，疑似 PID 回收或身份错配")  # 容许 Windows 时间戳分辨率但拒绝明显旧进程。
    error_path = solver_dir / f"{jobname}.err"  # 按同一 jobname 定位原生 ERR，启动早期允许尚不存在。
    native_monitor_path = solver_dir / f"{jobname}.mntr"  # 定位 MAPDL 原生 MNTR 供大小和修改时刻活性记录，不把其文本作为硬停来源。
    lock_path = solver_dir / f"{jobname}.lock"  # 定位 MAPDL job 锁，正常自然退出时应由求解器移除。
    monitor_claim_path = run_dir / "qa" / "runtime_hard_stop_monitor_claim.json"  # 定位监控器自身排他认领，关闭两个控制器并发附着。
    samples_path = run_dir / "qa" / "runtime_hard_stop_monitor_samples.jsonl"  # 定位排他创建且逐样本刷新的运行监控流水。
    final_path = run_dir / "qa" / "runtime_hard_stop_monitor_final.json"  # 定位进程树退出后唯一终态记录。
    require(not monitor_claim_path.exists() and not samples_path.exists() and not final_path.exists(), "该运行已存在监控认领、流水或终态，禁止第二监控器附着")  # 关闭重复监控和双控制器中止风险。
    bound_identities: dict[int, float] = {}  # 初始化跨样本 PID 到创建时刻绑定，包装器后代一旦可信即保持身份。
    initial_related, initial_unrelated, bound_identities = solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 在认领前验证至少一个真实进程可由根身份或双参数命令绑定。
    require(bool(initial_related), "监控附着时找不到与启动根或精确 -j/-dir 匹配的 MAPDL 进程")  # 防止已结束、PID复用或错误 job 被写入正常监控流水。
    monitor_claim = {"schema_version": 1, "status": "MONITOR_CLAIMED", "run_name": run_dir.name, "jobname": jobname, "claimed_at_utc": utc_now(), "monitor_script": str(SCRIPT_PATH), "monitor_script_sha256": sha256_file(SCRIPT_PATH), "runtime_launch_sha256": sha256_file(launch_path), "runtime_launch_claim_sha256": sha256_file(claim_path), "runtime_process_identity_sha256": sha256_file(process_identity_path), "manifest_sha256": sha256_file(manifest_path), "prepared_ledger_sha256": sha256_file(run_dir / "artifact_hashes.sha256"), "main_process_identity": main_identity, "initial_related_processes": initial_related, "initial_unrelated_solver_processes": initial_unrelated, "hard_stop_thresholds": launch["monitor_hard_stops"], "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_wait_only": NATIVE_ABORT_WAIT_ONLY, "active_process_disposition_allowed": ACTIVE_PROCESS_DISPOSITION_ALLOWED, "ordinary_ncnv_and_bisection_are_not_hard_stops": True}  # 保持既有终结器批准的第一版认领 schema，并以向后兼容新增字段冻结精确 ABT 载荷、只等待安全政策和不得抢停 AUTOTS 的合同。
    write_json_exclusive(monitor_claim_path, monitor_claim)  # 在任何样本或中止动作前排他写出唯一监控权声明。
    started_monotonic = time.monotonic()  # 记录不受系统时钟校正影响的持续时间起点。
    started_at_utc = utc_now()  # 记录人读 UTC 监控起点供启动延迟审计。
    low_ram_since: float | None = None  # 初始化低于 1 GiB 的连续区间起点；资源正常时保持 None。
    output_offset = 0  # 初始化 OUT 增量读取字节偏移，从文件开头捕获启动后全部硬事件。
    error_offset = 0  # 初始化 ERR 增量读取字节偏移，从文件开头捕获全部原生警告/错误。
    output_carry = ""  # 初始化 OUT 跨读取边界尾文。
    error_carry = ""  # 初始化 ERR 跨读取边界尾文。
    seen_event_keys: set[str] = set()  # 初始化硬事件去重集合，防止边界尾文重复触发中止。
    hard_events: list[dict[str, Any]] = []  # 累积全部首次发现的文本、方程和资源硬停事件。
    observed_equation_counts: list[int] = []  # 累积全部日志观察方程数，终态用于确认无秩漂移。
    minimum_available_ram = 2**63 - 1  # 以足够大整数初始化最小可用内存，首样本必然替换。
    minimum_disk_free = 2**63 - 1  # 以足够大整数初始化最小磁盘空余，首样本必然替换。
    maximum_related_rss = 0  # 初始化本 job 进程合计工作集峰值。
    sample_count = 0  # 初始化已经持久化的样本总数。
    empty_process_samples = 0  # 初始化连续空进程树样本数，避免包装器交接误判。
    previous_terminal_file_state: tuple[int, int, int] | None = None  # 初始化 OUT/ERR/MNTR 三文件上轮大小，用于进程退出后稳定性确认。
    post_exit_since: float | None = None  # 初始化首次发现进程树为空的单调时刻，超时仍不稳定则写阻断终态。
    monitor_block_reason: str | None = None  # 初始化无监控完整性阻断；仅在退出后 lock 或文件持续不稳时赋值。
    abort_requested = False  # 初始化控制器未请求 MAPDL 原生中止状态。
    abort_record: dict[str, Any] = {"requested": False, "reason_kinds": [], **native_abort_evidence_template(solver_dir / f"{jobname}.abt"), "native_abort_wait_only": NATIVE_ABORT_WAIT_ONLY, "active_process_disposition_allowed": ACTIVE_PROCESS_DISPOSITION_ALLOWED, "process_disposition": {"policy": "DISABLED_BY_ENGINEERING_SAFETY_POLICY", "targeted_pids": [], "terminate_sent_pids": [], "kill_sent_pids": [], "identity_rejected_before_terminate_pids": [], "identity_rejected_before_kill_pids": []}}  # 预置完整载荷和安全政策审计结构，正常完成时明确未请求且主动进程处置始终禁用。
    final_related: list[dict[str, Any]] = []  # 初始化循环退出时本 job 进程快照。
    final_unrelated: list[dict[str, Any]] = []  # 初始化循环退出时其他求解进程披露快照。
    with samples_path.open("x", encoding="utf-8", newline="\n") as samples_handle:  # 排他创建监控流水，本文件存在即充当唯一监控认领。
        while True:  # 持续采样直到本 job 进程树稳定退出或完成硬停处置。
            sample_started = time.monotonic()  # 记录本轮起点以扣除采样耗时并保持近似固定周期。
            elapsed_seconds = sample_started - started_monotonic  # 计算从监控附着起的单调持续时间。
            memory = psutil.virtual_memory()  # 读取当前系统可用物理内存与总量。
            disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 读取运行所在 D 盘当前空余和总容量。
            available_ram = int(memory.available)  # 转换为普通整数以稳定写入 JSON。
            disk_free = int(disk.free)  # 转换为普通整数以稳定写入 JSON。
            minimum_available_ram = min(minimum_available_ram, available_ram)  # 更新监控期可用内存最小值。
            minimum_disk_free = min(minimum_disk_free, disk_free)  # 更新监控期磁盘空余最小值。
            related_processes, unrelated_processes, bound_identities = solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 获取本 job 防 PID 回收进程树、其他求解进程和更新绑定。
            related_rss = sum(int(record["rss_bytes"]) for record in related_processes)  # 汇总本 job 当前驻留工作集用于峰值诊断。
            maximum_related_rss = max(maximum_related_rss, related_rss)  # 更新本 job 合计工作集峰值。
            output_offset, output_carry, output_text, output_size = read_log_increment(output_path, output_offset, output_carry)  # 读取本轮新增 OUT 并保持边界尾文。
            error_offset, error_carry, error_text, error_size = read_log_increment(error_path, error_offset, error_carry)  # 读取本轮新增 ERR 并保持边界尾文。
            output_file_state = file_snapshot(output_path)  # 记录 OUT 存在性、大小和修改时刻供稳定性与样本审计。
            error_file_state = file_snapshot(error_path)  # 记录 ERR 存在性、大小和修改时刻供稳定性与样本审计。
            native_monitor_file_state = file_snapshot(native_monitor_path)  # 记录 MNTR 原生收敛监控文件状态而不把其普通不收敛文本作为硬停。
            lock_file_state = file_snapshot(lock_path)  # 记录 job lock 是否仍存在，正常自然退出必须清除。
            output_events, output_equations = scan_new_text("OUT", output_text, seen_event_keys)  # 扫描 OUT 的明确硬事件和组装方程数。
            error_events, error_equations = scan_new_text("ERR", error_text, seen_event_keys)  # 扫描 ERR 的明确硬事件和组装方程数。
            new_events = output_events + error_events  # 合并两个原生日志本轮首次发现的硬事件。
            observed_equation_counts.extend(output_equations + error_equations)  # 累积日志中全部方程数；边界尾文重复值允许在终态保留但不影响唯一集合。
            if available_ram < IMMEDIATE_RAM_STOP_BYTES:  # 512 MiB 为无需持续确认的内存硬线。
                event_key = "RESOURCE_RAM_BELOW_512_MIB"  # 构造本运行唯一的立即内存事件键。
                if event_key not in seen_event_keys:  # 仅首次越线形成中止原因。
                    seen_event_keys.add(event_key)  # 登记事件防止下一样本重复。
                    new_events.append({"kind": event_key, "observed_bytes": available_ram, "threshold_bytes": IMMEDIATE_RAM_STOP_BYTES, "detected_at_utc": utc_now()})  # 保存实测值与冻结阈值。
            if available_ram < SUSTAINED_RAM_STOP_BYTES:  # 低于 1 GiB 时开始或延续持续计时。
                low_ram_since = sample_started if low_ram_since is None else low_ram_since  # 首次越线保存起点，后续保持原起点。
            else:  # 一旦恢复至至少 1 GiB，前一低内存区间不再连续。
                low_ram_since = None  # 重置持续计时，防止非连续抖动累计六十秒。
            low_ram_duration = 0.0 if low_ram_since is None else sample_started - low_ram_since  # 计算当前连续低于 1 GiB 的秒数。
            if low_ram_duration >= SUSTAINED_RAM_STOP_SECONDS:  # 只有连续达到六十秒才形成硬停事件。
                event_key = "RESOURCE_RAM_BELOW_1_GIB_SUSTAINED_60_SECONDS"  # 构造本运行唯一的持续内存事件键。
                if event_key not in seen_event_keys:  # 首次满足持续门时记录并触发，后续不重复。
                    seen_event_keys.add(event_key)  # 登记事件去重。
                    new_events.append({"kind": event_key, "observed_bytes": available_ram, "threshold_bytes": SUSTAINED_RAM_STOP_BYTES, "duration_seconds": low_ram_duration, "detected_at_utc": utc_now()})  # 保存实测内存、阈值和连续时间。
            if disk_free < DISK_STOP_BYTES:  # 32 GiB 为保护数据库和操作系统写入的即时磁盘硬线。
                event_key = "RESOURCE_DISK_BELOW_32_GIB"  # 构造本运行唯一磁盘事件键。
                if event_key not in seen_event_keys:  # 仅首次越线形成中止原因。
                    seen_event_keys.add(event_key)  # 登记事件去重。
                    new_events.append({"kind": event_key, "observed_bytes": disk_free, "threshold_bytes": DISK_STOP_BYTES, "detected_at_utc": utc_now()})  # 保存实测空余和冻结阈值。
            hard_events.extend(new_events)  # 在写样本和判断动作前累计本轮全部新硬事件。
            sample_count += 1  # 为当前即将持久化的样本分配从一开始的稳定序号。
            sample = {"schema_version": 1, "sample_index": sample_count, "sampled_at_utc": utc_now(), "elapsed_seconds": elapsed_seconds, "physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": available_ram, "low_ram_continuous_seconds": low_ram_duration, "disk_total_bytes": int(disk.total), "disk_free_bytes": disk_free, "related_processes": related_processes, "unrelated_solver_processes": unrelated_processes, "related_rss_bytes": related_rss, "out_offset_bytes": output_offset, "err_offset_bytes": error_offset, "out_file": output_file_state, "err_file": error_file_state, "mntr_file": native_monitor_file_state, "lock_file": lock_file_state, "new_equation_counts": output_equations + error_equations, "new_hard_events": new_events, "autots_high_residual_or_bisection_is_not_a_hard_stop": True}  # 保存资源、精确进程、日志偏移/状态和明确允许 AUTOTS 二分的完整样本。
            append_json_line(samples_handle, sample)  # 立即刷盘当前样本，保证任何后续动作都有先行证据。
            if new_events and not abort_requested:  # 首次发现任一冻结硬事件时进入单次原生 ABT 请求流程。
                abort_requested = True  # 在尝试写 .abt 前锁定控制器已处理该事件，防止每个样本重复创建或重复报错。
                abort_path = solver_dir / f"{jobname}.abt"  # 定位当前冻结 jobname 唯一原生中止请求文件。
                abort_evidence = native_abort_evidence_template(abort_path)  # 初始化可保留部分失败阶段的载荷与动作证据。
                request_attempted_at_utc = utc_now()  # 记录本轮硬事件证据已刷盘后、任何 ABT 文件动作前的 UTC 时刻。
                if related_processes:  # 只有本 job 精确进程仍存在时才有必要尝试提交原生 ABT 请求。
                    try:  # 载荷合同、排他创建、完整写入、同步或回读异常必须留证并继续只读监控。
                        request_native_abort(solver_dir, jobname, abort_evidence)  # 使用受测生产函数创建或只读核验十字节有效 ABT。
                    except (OSError, RuntimeError, UnicodeError) as error:  # 捕获权限、竞态、短写、同步、回读和路径合同异常，绝不升级为进程动作。
                        abort_evidence["abort_file_action"] = "ABORT_FILE_REQUEST_FAILED_NO_PROCESS_ACTION"  # 明确原生请求没有获得完整有效合同，禁止冒充成功。
                        abort_evidence["native_abort_error"] = f"{type(error).__name__}:{error}"  # 保留异常类型与说明供终态人工处置。
                else:  # 硬事件样本写出时进程树已为空，无需也不应创建新的控制文件。
                    abort_evidence["abort_file_action"] = "PROCESS_ALREADY_GONE_NO_ABORT_FILE_CREATED"  # 明确未发生文件动作且不会主动处置任何进程。
                abort_record = {"requested": bool(abort_evidence["request_contract_satisfied"]), "request_attempted_at_utc": request_attempted_at_utc, "reason_kinds": sorted({str(event["kind"]) for event in hard_events}), **abort_evidence, "native_abort_wait_only": NATIVE_ABORT_WAIT_ONLY, "active_process_disposition_allowed": ACTIVE_PROCESS_DISPOSITION_ALLOWED, "process_disposition": {"policy": "DISABLED_BY_ENGINEERING_SAFETY_POLICY", "targeted_pids": [], "terminate_sent_pids": [], "kill_sent_pids": [], "identity_rejected_before_terminate_pids": [], "identity_rejected_before_kill_pids": []}}  # 冻结触发原因、精确 ABT 各阶段证据和永久空的主动进程处置清单；后续只恢复十秒采样等待自然退出。
            if related_processes:  # 本轮仍检测到本 job 进程时不能判定求解完成。
                empty_process_samples = 0  # 重置连续空样本计数，覆盖包装器/solver 正常运行期。
                post_exit_since = None  # 进程重新出现表示此前空窗是包装器交接，重置退出等待时钟。
                previous_terminal_file_state = None  # 清除交接空窗留下的文件大小，使真正退出后重新取得两个稳定样本。
            else:  # 本轮未检测到任何 jobname、solver目录或可信父子闭包进程。
                post_exit_since = sample_started if post_exit_since is None else post_exit_since  # 首次进程树为空时启动最长六十秒稳定等待。
                current_terminal_file_state = (int(output_file_state["size_bytes"]), int(error_file_state["size_bytes"]), int(native_monitor_file_state["size_bytes"]))  # 构造三项权威运行文件当前大小元组。
                terminal_files_stable = previous_terminal_file_state == current_terminal_file_state  # 只有连续两个样本大小完全相同才视为写入稳定。
                normal_exit_evidence = terminal_files_stable and not bool(lock_file_state["exists"])  # 自然退出还要求 MAPDL 已移除 job lock。
                empty_process_samples = empty_process_samples + 1 if (abort_requested or normal_exit_evidence) else 0  # 硬停只需进程稳定消失；自然退出同时要求文件稳定且无锁。
                previous_terminal_file_state = current_terminal_file_state  # 保存当前三文件大小供下一空进程样本比较。
                if not abort_requested and sample_started - post_exit_since >= POST_EXIT_STABILITY_TIMEOUT_SECONDS and not normal_exit_evidence:  # 自然退出后六十秒仍有锁或文件变化时不得无限等待或冒充正常。
                    monitor_block_reason = "PROCESS_TREE_EXITED_BUT_LOCK_REMAINED_OR_OUTPUTS_NOT_STABLE_FOR_60_SECONDS"  # 冻结监控完整性阻断原因供终结器 fail-closed。
                    final_related, final_unrelated, bound_identities = solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 超时提交前取得最后防 PID 回收进程快照。
                    break  # 跳出采样循环并写阻断终态，不执行控制器中止。
            if empty_process_samples >= PROCESS_EXIT_EMPTY_SAMPLES:  # 两个连续采样周期均为空时确认本 job 进程树稳定退出。
                final_related, final_unrelated, bound_identities = solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 在退出前再做一次防 PID 回收精确快照供终态记录。
                if not final_related:  # 最终快照仍为空才结束监控，避免第二样本和提交之间新出现同 job 进程。
                    break  # 跳出采样循环并写排他终态。
                empty_process_samples = 0  # 若最终快照重新发现本 job，则恢复运行态继续监控。
            sleep_seconds = max(0.0, SAMPLE_INTERVAL_SECONDS - (time.monotonic() - sample_started))  # 扣除本轮读取与写盘耗时以维持十秒节拍。
            time.sleep(sleep_seconds)  # 等待到下一采样周期；十秒远低于用户可见更新上限。
    final_status = "HARD_STOP_TRIGGERED" if hard_events else ("PROCESS_TREE_EXITED_MONITOR_BLOCKED" if monitor_block_reason is not None else "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP")  # 区分控制器硬停、退出证据不闭合和自然稳定退出三种监控终态。
    final_record = {"schema_version": 1, "status": final_status, "run_name": run_dir.name, "jobname": jobname, "monitor_started_at_utc": started_at_utc, "monitor_finished_at_utc": utc_now(), "duration_seconds": time.monotonic() - started_monotonic, "sample_count": sample_count, "monitor_claim_path": str(monitor_claim_path), "monitor_claim_sha256": sha256_file(monitor_claim_path), "monitor_block_reason": monitor_block_reason, "hard_stop_contract": {"immediate_ram_below_bytes": IMMEDIATE_RAM_STOP_BYTES, "sustained_ram_below_bytes": SUSTAINED_RAM_STOP_BYTES, "sustained_ram_seconds": SUSTAINED_RAM_STOP_SECONDS, "disk_below_bytes": DISK_STOP_BYTES, "expected_equation_count": EXPECTED_EQUATION_COUNT, "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_wait_only": NATIVE_ABORT_WAIT_ONLY, "active_process_disposition_allowed": ACTIVE_PROCESS_DISPOSITION_ALLOWED, "fatal_and_pivot_and_cnvtol_patterns_only": True, "high_residual_not_hard_stop": True, "begin_bisection_not_hard_stop": True, "ordinary_ncnv_not_hard_stop": True}, "minimum_physical_memory_available_bytes": minimum_available_ram, "minimum_disk_free_bytes": minimum_disk_free, "maximum_related_rss_bytes": maximum_related_rss, "observed_equation_counts": observed_equation_counts, "unique_equation_counts": sorted(set(observed_equation_counts)), "hard_events": hard_events, "controller_abort": abort_record, "final_related_processes": final_related, "final_unrelated_solver_processes": final_unrelated, "final_out_file": file_snapshot(output_path), "final_err_file": file_snapshot(error_path), "final_mntr_file": file_snapshot(native_monitor_path), "final_lock_file": file_snapshot(lock_path), "samples_path": str(samples_path), "samples_sha256": sha256_file(samples_path), "out_path": str(output_path), "err_path": str(error_path)}  # 保持既有终结器批准的第一版终态 schema，并以向后兼容新增字段汇总精确 ABT 合同、只等待安全政策、资源极值和最终进程状态。
    write_json_exclusive(final_path, final_record)  # 以排他创建提交监控终态，禁止覆盖或第二监控器伪造正常完成。
    print(json.dumps({"run_dir": str(run_dir), "status": final_status, "sample_count": sample_count, "hard_event_count": len(hard_events), "controller_abort_requested": bool(abort_record["requested"])}, ensure_ascii=False))  # 向调用者输出精简机器摘要，详细证据保留在 QA 工件。


if __name__ == "__main__":  # 仅直接执行脚本时进入监控，导入审查不会访问文件或进程。
    main()  # 执行一次严格绑定唯一自适应迁移运行的持续硬停监控。
