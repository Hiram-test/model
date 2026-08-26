"""在自适应迁移已证明最小步可收敛但预计剩余运行超过七天时请求可审计的 MAPDL 原生停机。"""  # 本工具只创建 job.abt，不调用 terminate、kill 或任何进程强制结束接口。

from __future__ import annotations  # 延迟解析类型标注，保持复杂 JSON 与进程记录容器在运行时兼容。

import argparse  # 解析用户显式指定的唯一自适应运行目录或完全离线自检开关，禁止隐式 latest 选择。
import ast  # 解析当前工具源码抽象语法树，离线证明不存在 terminate、kill 或信号处置调用。
import hashlib  # 复算准备、启动、监控、MNTR、认领、说明、ABT 和终态工件摘要。
import json  # 读取机器工件并排他写出操作员停机认领和最终审计对象。
import math  # 检查 MNTR 增量、耗时和投影结果均为有限数并执行向上取整。
import os  # 对十字节有效 ABT 载荷执行缓冲刷新和磁盘同步，确保原生停机请求真实落盘。
import re  # 解析准备账本、MNTR 数值行和主控中的冻结自适应命令。
import tempfile  # 只在操作系统临时目录创建离线 ABT 回归样本，绝不接触任何实际运行目录。
import time  # 使用单调时钟等待求解器响应 ABT，并复核退出后文件连续稳定。
from datetime import datetime, timezone  # 检查最新监控样本足够新鲜并记录带时区 UTC 审计时刻。
from pathlib import Path  # 规范化包含中文的项目、运行、solver 和 QA 路径。
from typing import Any  # 标注异构 JSON、进程身份和 MNTR 行对象。

import psutil  # 只读核验 PID、创建时刻、二进制、命令行和本 job 进程树身份。

SCRIPT_PATH = Path(__file__).resolve()  # 固定实际执行工具源码绝对路径供认领摘要使用。
PROJECT_ROOT = SCRIPT_PATH.parents[1]  # 取 ultra_tools 的父目录作为唯一分析包根。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 限定所有目标必须是统一运行证据根的直接子目录。
EXPECTED_RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_"  # 只允许恒总荷载位置迁移诊断族使用充分性停机。
EXPECTED_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结唯一批准的 0.05% 自适应子类型。
EXPECTED_SINGLE_CHANGE = "LS2_NSBMX_200_TO_2000_ONLY"  # 冻结相对固定 0.5% 输入的唯一工程命令差异。
EXPECTED_EQUATION_COUNT = 1234834  # 冻结单层 TYPE72 全桥独立方程数供监控流水复核。
MINIMUM_INCREMENT = 5.0e-7  # 总迁移伪时间 0.001 在 NSBMX=2000 下的最小接受增量。
MIGRATION_DURATION = 1.0e-3  # LS2 从总时间 1.0 到 1.001 的完整无量纲迁移时长。
MINIMUM_LATEST_ITERATIONS = 20  # 后一个最小步至少二十次 Newton 迭代才表明该速度不是偶发快速步。
MINIMUM_IN_PROGRESS_ITERATIONS = 29  # 门 B 要求尚未接受的 LS2 子步 2 已完整完成至少二十九次连续平衡迭代。
SUFFICIENCY_HORIZON_SECONDS = 7.0 * 24.0 * 60.0 * 60.0  # 七天阈值换算为 604800 秒，超过才允许停止。
MNTR_INCREMENT_TOLERANCE = 1.0e-12  # 比较 5E-7 原生增量时允许的绝对浮点解析尾差。
LATEST_MONITOR_SAMPLE_MAX_AGE_SECONDS = 45.0  # 要求最后监控样本距当前不超过四十五秒以证明监控仍在附着。
POLL_INTERVAL_SECONDS = 5.0  # ABT 后每五秒只读检查一次精确进程树、lock 和三项运行文件。
EXIT_CONFIRMATION_TIMEOUT_SECONDS = 1800.0  # 最多等待三十分钟供 MAPDL 在当前迭代边界响应原生 ABT，超时也绝不强杀。
POST_EXIT_MONITOR_TIMEOUT_SECONDS = 120.0  # 进程稳定退出后最多等待两分钟供冻结监控器提交终态。
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"  # 覆盖 MAPDL 整数、小数和科学计数法的有限数词法。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})\s{2}(.+)$")  # 只接受六十四位小写 SHA-256、双空格和相对路径。
MNTR_PATTERN = re.compile(rf"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})(?:\s+|$)", re.IGNORECASE)  # 匹配 MNTR 五个整数、增量、总时间和 Elap(s) 八列。
OUT_COMPLETION_PATTERN = re.compile(r"^\s*\*\*\*\s+LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED\.", re.IGNORECASE | re.MULTILINE)  # 识别 OUT 中自然接受载荷步和子步的权威完成事件。
OUT_EQUIL_ITER_PATTERN = re.compile(r"^\s*EQUIL ITER\s+(\d+)\s+COMPLETED\.", re.IGNORECASE | re.MULTILINE)  # 识别当前尝试已经完整完成的 Newton 平衡迭代编号。
OUT_SOLUTION_CONVERGED_PATTERN = re.compile(r"^\s*>>>\s*SOLUTION CONVERGED AFTER EQUILIBRIUM ITERATION", re.IGNORECASE | re.MULTILINE)  # 识别尚未写入 MNTR 前也已进入接受流程的收敛事件。
OUT_REJECTION_PATTERN = re.compile(r"(?:BEGIN\s+BISECTION|SOLUTION\s+NOT\s+CONVERGED|DOES\s+NOT\s+CONVERGE|CONVERGENCE\s+FAILURE|\bNCNV\b|NOT\s+COMPLETED|\*\*\*\s+(?:ERROR|FATAL)\s+\*\*\*|\bABORT(?:ED|ING)?\b|\bTERMINAT(?:ED|ING|ION)\b)", re.IGNORECASE)  # 阻断二分、拒绝、错误、中止或终止已经改变当前连续子步 2 状态的 OUT 尾段。
SOLVER_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 与冻结监控器完全一致地限定可审计求解进程，明确排除 ansyslmd 等许可证服务。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 冻结 MAPDL 2026 R1 认可的首行 nonlinear 关键字及单一 LF，共十个 ASCII 字节。
NATIVE_ABORT_PAYLOAD_LENGTH = 10  # 冻结有效 ABT 载荷的精确字节数，阻断空文件、CRLF 或附加说明混入。
NATIVE_ABORT_PAYLOAD_HEX = "6e6f6e6c696e6561720a"  # 冻结十字节载荷的逐字节十六进制表示供机器审计和回读比较。
NATIVE_ABORT_PAYLOAD_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结有效载荷 SHA-256，避免仅凭可见文本遗漏换行差异。
FORBIDDEN_PROCESS_ACTION_CALL_NAMES = {"kill", "terminate", "send_signal", "taskkill", "TerminateProcess", "system", "popen", "Popen", "run", "call", "check_call", "check_output"}  # 离线 AST 审计同时拒绝直接进程动作和可绕行 taskkill 的 shell/子进程调用入口。


def require(condition: bool, message: str) -> None:  # 接收必须成立的条件和拒绝原因；失败时不创建 ABT。
    if not condition:  # 仅在谱系、运行活性、MNTR 充分性、投影或审计门不闭合时进入。
        raise RuntimeError(message)  # 抛出明确异常并保持求解器继续自然运行。


def utc_now() -> str:  # 无输入并返回带 UTC 偏移的微秒级 ISO-8601 当前时刻。
    return datetime.now(timezone.utc).isoformat()  # 使用时区感知 UTC，避免本地时区和夏令时歧义。


def sha256_file(path: Path) -> str:  # 接收普通文件路径并返回完整二进制内容的六十四位小写摘要。
    digest = hashlib.sha256()  # 为当前文件创建独立 SHA-256 累加器。
    with path.open("rb") as handle:  # 使用只读二进制模式避免编码和换行转换。
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):  # 每次读取八 MiB 兼顾大型运行工件吞吐和内存峰值。
            digest.update(block)  # 按原始字节顺序累加当前数据块。
    return digest.hexdigest()  # 返回固定六十四位小写十六进制内容身份。


def read_json(path: Path) -> dict[str, Any]:  # 接收 UTF-8 JSON 路径并返回已经验证为对象的顶层字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 解析前拒绝缺失、目录或错误路径。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 严格解析 UTF-8 完整文档。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充具名工件。
    return payload  # 返回通过存在性、编码、语法和类型门的对象。


def render_json(payload: dict[str, Any]) -> str:  # 接收机器对象并返回保留中文、两空格缩进且禁止 NaN 的稳定 JSON。
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 固定末尾单一 LF 供摘要复核。


def write_text_exclusive(path: Path, text_value: str) -> None:  # 接收目标和文本并执行不可覆盖 UTF-8/LF 写入及磁盘同步。
    require(path.parent.is_dir(), f"排他工件父目录不存在：{path.parent}")  # 禁止隐式创建错误目录层级。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用操作系统排他创建语义阻断重复操作者。
        handle.write(text_value)  # 一次写入内存中已完成渲染的完整文本。
        handle.flush()  # 刷新 Python 缓冲，确保后续 ABT 动作之前认领可见。
        os.fsync(handle.fileno())  # 请求操作系统把认领或说明真实同步到磁盘。


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:  # 接收目标和对象并排他写出稳定机器 JSON。
    write_text_exclusive(path, render_json(payload))  # 复用不可覆盖、UTF-8、LF 和 fsync 合同。


def native_abort_evidence_template() -> dict[str, Any]:  # 无输入并返回尚未写入 ABT 时的完整载荷合同与动作证据初值，供成功和失败终态共用。
    return {"native_abort_payload_text_ascii": NATIVE_ABORT_PAYLOAD.decode("ascii"), "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_payload_contract_verified_before_write": False, "native_abort_created_exclusively": False, "native_abort_created_at_utc": None, "native_abort_write_returned_bytes": 0, "native_abort_payload_written_fully": False, "native_abort_flush_completed": False, "native_abort_fsync_completed": False, "native_abort_flush_and_fsync_completed": False, "native_abort_readback_length_bytes": None, "native_abort_readback_hex": None, "native_abort_readback_sha256": None, "native_abort_readback_matches_contract": False}  # 明确记录计划字节、排他创建、完整写入、同步和同句柄回读各阶段，避免用文件存在性替代有效性证明。


def create_valid_native_abort_exclusive(abort_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:  # 接收唯一 ABT 目标和可变证据字典，排他写入十字节有效载荷并返回完成回读校验的同一证据对象。
    require(abort_path.parent.is_dir(), f"ABT 父目录不存在：{abort_path.parent}")  # 禁止为拼错路径隐式创建目录或把停机请求写出批准 solver 目录。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n", "ABT 载荷字面值偏离 nonlinear 加 LF 合同")  # 在打开目标前核对精确字节字面值，常量漂移时保持零动作。
    require(len(NATIVE_ABORT_PAYLOAD) == NATIVE_ABORT_PAYLOAD_LENGTH, "ABT 载荷长度常量与真实字节不一致")  # 在打开目标前阻断空文件、CRLF 和附加字符。
    require(NATIVE_ABORT_PAYLOAD.hex() == NATIVE_ABORT_PAYLOAD_HEX, "ABT 载荷十六进制常量与真实字节不一致")  # 在打开目标前逐字节关闭可见文本和编码歧义。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256, "ABT 载荷 SHA-256 常量与真实字节不一致")  # 在打开目标前以独立摘要关闭换行或编码漂移。
    evidence["native_abort_payload_contract_verified_before_write"] = True  # 只有四项精确合同全部通过才允许取得文件排他创建权。
    with abort_path.open("x+b") as abort_handle:  # 使用排他创建且可回读的二进制模式，禁止覆盖既有控制请求或发生文本换行转换。
        evidence["native_abort_created_exclusively"] = True  # 文件描述符取得排他创建权后立即记录真实动作，即使后续写盘失败也不伪称未创建。
        evidence["native_abort_created_at_utc"] = utc_now()  # 记录排他创建成功的 UTC 时刻供运行终态审计。
        written_bytes = abort_handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入冻结十字节载荷，并保留底层返回的真实字节数。
        evidence["native_abort_write_returned_bytes"] = written_bytes  # 保存写调用返回值以区分完整写入和罕见短写。
        require(written_bytes == NATIVE_ABORT_PAYLOAD_LENGTH, f"ABT 载荷短写：{written_bytes}/{NATIVE_ABORT_PAYLOAD_LENGTH} 字节")  # 任何短写均失败关闭，不进入退出等待。
        evidence["native_abort_payload_written_fully"] = True  # 仅在写调用确认十字节完整接收后标记完整写入。
        abort_handle.flush()  # 把 Python 用户态缓冲全部提交给操作系统文件句柄。
        evidence["native_abort_flush_completed"] = True  # 只有 flush 正常返回才记录用户态缓冲已清空。
        os.fsync(abort_handle.fileno())  # 请求操作系统把有效 ABT 内容同步到持久存储，再进行回读证明。
        evidence["native_abort_fsync_completed"] = True  # 只有 fsync 正常返回才记录磁盘同步已完成。
        evidence["native_abort_flush_and_fsync_completed"] = True  # 合并记录两层同步均完成，供终态单字段判定。
        abort_handle.seek(0)  # 把同一排他文件描述符移回首字节，避免另开句柄带来路径替换竞态。
        readback_payload = abort_handle.read()  # 从同一文件对象回读全部字节，核对真实落盘对象内容。
        evidence["native_abort_readback_length_bytes"] = len(readback_payload)  # 保存回读长度，明确应为十字节。
        evidence["native_abort_readback_hex"] = readback_payload.hex()  # 保存回读十六进制，允许逐字节审计换行与编码。
        evidence["native_abort_readback_sha256"] = hashlib.sha256(readback_payload).hexdigest()  # 保存回读摘要，供终态和离线测试独立核验。
        evidence["native_abort_readback_matches_contract"] = readback_payload == NATIVE_ABORT_PAYLOAD and len(readback_payload) == NATIVE_ABORT_PAYLOAD_LENGTH and evidence["native_abort_readback_hex"] == NATIVE_ABORT_PAYLOAD_HEX and evidence["native_abort_readback_sha256"] == NATIVE_ABORT_PAYLOAD_SHA256  # 同时比较字节、长度、十六进制和摘要，禁止任一弱证据单独放行。
        require(bool(evidence["native_abort_readback_matches_contract"]), "ABT 回读字节不满足 nonlinear 加 LF 精确合同")  # 回读不一致时失败关闭并保留已发生动作证据。
    return evidence  # 返回包含排他创建、完整写入、fsync 和回读四段证据的同一对象。


def verify_prepared_ledger(path: Path, run_dir: Path) -> dict[str, str]:  # 接收准备账本和运行根并返回全部逐项复算通过的相对路径摘要。
    require(path.is_file(), "缺少准备态 artifact_hashes.sha256")  # 无启动前字节谱系时禁止充分性停机。
    entries: dict[str, str] = {}  # 初始化唯一相对路径到摘要映射。
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()  # 严格读取全部 UTF-8 账本行。
    require(len(lines) >= 29, f"准备账本条目不足：{len(lines)}")  # 当前自适应包至少应有二十九项冻结工件。
    for line_number, line in enumerate(lines, start=1):  # 按真实行号逐项验证格式、边界、存在性和摘要。
        match = LEDGER_PATTERN.fullmatch(line)  # 对完整行应用严格账本词法。
        require(match is not None, f"准备账本第 {line_number} 行格式无效")  # 空行、非小写摘要和错误分隔均拒绝。
        relative_text = match.group(2).replace("\\", "/")  # 统一路径分隔符供唯一比较。
        require(relative_text not in entries, f"准备账本重复路径：{relative_text}")  # 禁止后行覆盖先前摘要。
        artifact_path = (run_dir / Path(relative_text)).resolve()  # 将相对路径投影到规范运行根。
        require(artifact_path.is_relative_to(run_dir.resolve()), f"准备账本路径越界：{relative_text}")  # 阻断绝对路径和父目录逃逸。
        require(artifact_path.is_file() and sha256_file(artifact_path) == match.group(1), f"准备工件缺失或哈希漂移：{relative_text}")  # 逐字节关闭准备谱系。
        entries[relative_text] = match.group(1)  # 保存当前通过全部门的唯一条目。
    return entries  # 返回可与启动和监控认领交叉核对的准备映射。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收完整启动参数和标志并返回唯一相邻值。
    indexes = [index for index, value in enumerate(arguments) if value.casefold() == flag.casefold()]  # 忽略大小写收集全部出现位置。
    require(len(indexes) == 1, f"启动参数 {flag} 出现 {len(indexes)} 次")  # 缺失或重复均造成执行身份歧义。
    index = indexes[0]  # 读取已确认唯一的下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止末尾孤立标志越界。
    return arguments[index + 1]  # 返回求解器实际采用的字符串值。


def parse_mntr_bytes(payload: bytes) -> list[dict[str, float | int]]:  # 接收冻结 MNTR 字节并返回全部已接受子步的八项字段。
    rows: list[dict[str, float | int]] = []  # 初始化保持原生文件顺序的接受行列表。
    for line in payload.decode("latin-1", errors="strict").splitlines():  # Latin-1 一一映射全部字节并逐行扫描。
        match = MNTR_PATTERN.match(line)  # 尝试识别八列真实数值行而非页眉或空白。
        if match is not None:  # 只有完整八列前缀进入接受子步集合。
            row = {"load_step": int(match.group(1)), "substep": int(match.group(2)), "attempt": int(match.group(3)), "iterations": int(match.group(4)), "total_iterations": int(match.group(5)), "increment": float(match.group(6)), "total_time_printed": float(match.group(7)), "elapsed_seconds": float(match.group(8))}  # 转换控制列、时间列和实测耗时。
            require(all(math.isfinite(float(value)) for value in row.values()), f"MNTR 行含非有限值：{line}")  # 禁止 NaN 或无穷进入停止决策。
            rows.append(row)  # 保存当前已接受子步并保持原生顺序。
    return rows  # 返回可用于连续性、迭代数和剩余时长投影的列表。


def parse_out_in_progress_second_step(payload: bytes) -> dict[str, Any]:  # 接收某一确定时刻可见的 OUT 前缀并证明尾部仍是 LS2 子步 2 的首次连续尝试。
    text_value = payload.decode("latin-1", errors="strict")  # 使用 Latin-1 保持字节到字符一一对应，使偏移和摘要证据不受解码替换影响。
    completion_matches = list(OUT_COMPLETION_PATTERN.finditer(text_value))  # 收集全部自然接受完成事件以定位最后确定状态。
    require(completion_matches, "OUT 尚无任何自然接受完成事件")  # 无已完成事件时不能把尾部归属到 LS2 子步 2。
    completion_pairs = [(int(match.group(1)), int(match.group(2))) for match in completion_matches]  # 转换全部完成事件为载荷步和子步整数对。
    require(completion_pairs.count((2, 1)) == 1 and completion_pairs[-1] == (2, 1), f"OUT 最后完成事件并非唯一 LS2 子步 1：{completion_pairs[-3:]}")  # 证明当前尾段紧随唯一接受的 LS2 子步 1。
    active_tail = text_value[completion_matches[-1].end():]  # 截取 LS2 子步 1 完成事件之后的当前未决尾段。
    require(OUT_COMPLETION_PATTERN.search(active_tail) is None, "OUT 尾段已经出现新的接受完成事件")  # 若子步 2 已完成则必须改走门 A 或重新认领。
    require(OUT_SOLUTION_CONVERGED_PATTERN.search(active_tail) is None, "OUT 尾段已报告解收敛，子步 2 不再是未接受状态")  # 阻断收敛已发生但 MNTR 尚未来得及刷新的竞态。
    rejection_match = OUT_REJECTION_PATTERN.search(active_tail)  # 搜索任何二分、拒绝、错误、中止或终止状态转换。
    require(rejection_match is None, f"OUT 尾段已经出现拒绝或终止事件：{None if rejection_match is None else rejection_match.group(0)}")  # 只允许从子步 1 接受后连续推进的首次子步 2 尝试。
    iteration_matches = list(OUT_EQUIL_ITER_PATTERN.finditer(active_tail))  # 收集子步 2 尾段全部完整平衡迭代事件。
    iteration_numbers = [int(match.group(1)) for match in iteration_matches]  # 提取原生迭代编号供连续性和最低数量检查。
    require(iteration_numbers == list(range(1, len(iteration_numbers) + 1)), f"OUT 子步 2 迭代并非从 1 连续递增：{iteration_numbers[-10:]}")  # 编号重置或跳号表示尝试已切换或证据不完整。
    require(iteration_numbers and iteration_numbers[-1] >= MINIMUM_IN_PROGRESS_ITERATIONS, f"OUT 子步 2 完整迭代不足 29：{iteration_numbers[-1] if iteration_numbers else 0}")  # 门 B 至少覆盖首个接受步的完整二十九次迭代周期。
    last_iteration = iteration_matches[-1]  # 读取最后一个完整平衡迭代事件供尾状态定位。
    trailing_text = active_tail[last_iteration.end():]  # 截取最后完整迭代之后尚未形成下一状态事件的诊断文本。
    require(OUT_COMPLETION_PATTERN.search(trailing_text) is None and OUT_SOLUTION_CONVERGED_PATTERN.search(trailing_text) is None and OUT_REJECTION_PATTERN.search(trailing_text) is None, "OUT 最后迭代之后出现状态转换事件")  # 明确最后可识别结构事件仍属于未决 LS2 子步 2。
    return {"state": "LS2_SUBSTEP_2_FIRST_ATTEMPT_IN_PROGRESS", "last_completed_load_step": 2, "last_completed_substep": 1, "current_load_step": 2, "current_substep": 2, "completed_equilibrium_iterations": iteration_numbers[-1], "iteration_sequence_starts_at_one_and_is_contiguous": True, "accepted_after_substep_1": False, "rejected_or_bisected_after_substep_1": False, "last_structural_event": f"EQUIL_ITER_{iteration_numbers[-1]}_COMPLETED", "out_prefix_size_bytes": len(payload), "out_prefix_sha256": hashlib.sha256(payload).hexdigest(), "tail_after_last_iteration_size_bytes": len(trailing_text.encode('latin-1'))}  # 返回可写入认领的状态机事实而不携带巨大 OUT 正文。


def evaluate_mntr_sufficiency(mntr_rows: list[dict[str, float | int]], sampled_out_payload: bytes | None = None, current_out_payload: bytes | None = None, current_elapsed_seconds: float | None = None) -> dict[str, Any]:  # 接收 MNTR 和可选同步 OUT 证据并按门 A 或门 B 返回严格超过七天的投影对象。
    require(len(mntr_rows) >= 2 and int(mntr_rows[0]["load_step"]) == 1 and int(mntr_rows[0]["substep"]) == 1, "MNTR 尚无 LS1 加至少一个 LS2 接受行")  # 两条路径共同要求 LS1 与自然接受的 LS2 子步 1。
    require(all(int(row["load_step"]) in {1, 2} for row in mntr_rows), "MNTR 出现 LS1/LS2 之外的接受载荷步")  # 阻断后续阶段或混入运行借用投影。
    ls2_rows = [row for row in mntr_rows if int(row["load_step"]) == 2]  # 提取全部自然接受的迁移子步。
    require(ls2_rows and [int(row["substep"]) for row in ls2_rows] == list(range(1, len(ls2_rows) + 1)), "LS2 接受子步缺失或编号不连续")  # 固定从子步 1 开始的自然连续接受路径。
    require(all(math.isclose(float(row["increment"]), MINIMUM_INCREMENT, rel_tol=0.0, abs_tol=MNTR_INCREMENT_TOLERANCE) for row in ls2_rows), "LS2 已接受增量存在非 5E-7 值")  # 两条路径都只允许冻结最小步增量外推。
    latest_two: list[dict[str, float | int]] | None = None  # 初始化门 B 不具有两个接受行的显式空值。
    in_progress_out_evidence: dict[str, Any] | None = None  # 初始化门 A 不依赖未决 OUT 尾状态的显式空值。
    if len(ls2_rows) >= 2:  # 门 A 使用最近两个自然接受的连续最小步实测完整周期。
        latest_two = ls2_rows[-2:]  # 取最近两个接受行作为完整最小步速度窗口。
        require(int(latest_two[1]["substep"]) == int(latest_two[0]["substep"]) + 1, "最近两个 LS2 接受子步不连续")  # 显式关闭投影窗口连续性。
        require(int(latest_two[1]["iterations"]) >= MINIMUM_LATEST_ITERATIONS, f"门 A 后一个最小步迭代数不足 20：{latest_two[1]['iterations']}")  # 排除偶发快速接受行。
        measured_seconds_per_minimum_step = float(latest_two[1]["elapsed_seconds"]) - float(latest_two[0]["elapsed_seconds"])  # 由 MNTR Elap(s) 直接计算第二个连续接受步完整耗时。
        sufficiency_branch = "A_TWO_ACCEPTED_MINIMUM_STEPS"  # 标记使用两个自然接受行的完整周期门 A。
        projection_is_conservative_lower_bound = False  # 门 A 使用完整接受步实测值而不是未决步骤时长下界。
        projection_basis = "MNTR_LATEST_TWO_ACCEPTED_ROWS_ELAPSED_DIFFERENCE"  # 固定门 A 的可复算投影依据。
    else:  # 恰一个 LS2 接受行时仅允许满足同步 OUT 状态机和二十九次迭代的门 B。
        require(len(ls2_rows) == 1, "门 B 必须恰有一个 LS2 接受行")  # 禁止零行或多行误入未决步骤分支。
        require(sampled_out_payload is not None and current_out_payload is not None and current_elapsed_seconds is not None, "门 B 缺少同步 OUT 或当前 elapsed 证据")  # 三项证据缺一不可。
        sampled_evidence = parse_out_in_progress_second_step(sampled_out_payload)  # 证明监控样本时刻已经完整完成至少二十九次连续迭代。
        current_evidence = parse_out_in_progress_second_step(current_out_payload)  # 证明决策读取时仍未接受、拒绝、二分或切换尝试。
        require(int(current_evidence["completed_equilibrium_iterations"]) >= int(sampled_evidence["completed_equilibrium_iterations"]), "当前 OUT 迭代证据倒退于监控样本前缀")  # 阻断文件替换、截断或错误前缀。
        measured_seconds_per_minimum_step = float(current_elapsed_seconds) - float(ls2_rows[0]["elapsed_seconds"])  # 用监控当前 elapsed 减首步接受 Elap(s) 得到未决子步 2 已耗时下界。
        in_progress_out_evidence = {"sampled_prefix": sampled_evidence, "current_snapshot": current_evidence, "first_accepted_step_elapsed_seconds": float(ls2_rows[0]["elapsed_seconds"]), "current_monitor_elapsed_seconds": float(current_elapsed_seconds)}  # 合并同步样本前缀与最新稳定 OUT 的双重状态证据。
        sufficiency_branch = "B_ONE_ACCEPTED_PLUS_IN_PROGRESS_SECOND_STEP_LOWER_BOUND"  # 标记使用恰一接受行和未决第二步时长下界的门 B。
        projection_is_conservative_lower_bound = True  # 明确当前步骤尚未完成，所用时长只是其最终耗时的保守下界。
        projection_basis = "FIRST_ACCEPTED_MNTR_ELAPSED_TO_CURRENT_MONITOR_ELAPSED_LOWER_BOUND"  # 固定门 B 的 elapsed 差值来源和下界语义。
    require(math.isfinite(measured_seconds_per_minimum_step) and measured_seconds_per_minimum_step > 0.0, "投影使用的最小步实测耗时不是有限正数")  # 禁止时钟回退、错配或零耗时投影。
    accepted_migration = sum(float(row["increment"]) for row in ls2_rows)  # 按原生接受增量独立累计已完成迁移时长。
    require(MINIMUM_INCREMENT * len(ls2_rows) - MNTR_INCREMENT_TOLERANCE <= accepted_migration <= MIGRATION_DURATION + MNTR_INCREMENT_TOLERANCE, "LS2 接受增量累计越出迁移合同")  # 防止负值、超终点或破损行。
    remaining_migration = max(0.0, MIGRATION_DURATION - accepted_migration)  # 计算到 beta=0 端点仍需完成的伪时间。
    remaining_minimum_steps = int(math.ceil(max(0.0, remaining_migration - MNTR_INCREMENT_TOLERANCE) / MINIMUM_INCREMENT))  # 按最小步向上取整剩余接受数，避免低估。
    projected_remaining_seconds = measured_seconds_per_minimum_step * float(remaining_minimum_steps)  # 用完整实测周期或未决周期下界线性投影全部剩余最小步。
    require(remaining_minimum_steps > 0 and math.isfinite(projected_remaining_seconds) and projected_remaining_seconds > SUFFICIENCY_HORIZON_SECONDS, f"投影剩余时间未严格超过七天：{projected_remaining_seconds:.3f} 秒")  # 两条路径共同且唯一的运行充分性停止授权门。
    return {"sufficiency_branch": sufficiency_branch, "projection_basis": projection_basis, "projection_is_conservative_lower_bound": projection_is_conservative_lower_bound, "ls2_rows": ls2_rows, "latest_two": latest_two, "in_progress_out_evidence": in_progress_out_evidence, "measured_seconds_per_minimum_step": measured_seconds_per_minimum_step, "accepted_migration": accepted_migration, "remaining_migration": remaining_migration, "remaining_minimum_steps": remaining_minimum_steps, "projected_remaining_seconds": projected_remaining_seconds}  # 返回认领、中文说明和动作前复核共同使用的统一双门证据。


def snapshot_file(path: Path) -> dict[str, Any]:  # 接收可能不存在的运行文件并返回存在、大小和纳秒修改时刻快照。
    if not path.is_file():  # 启动早期或退出清理后的临时文件允许不存在。
        return {"exists": False, "size_bytes": 0, "mtime_ns": None}  # 使用固定字段表达缺失状态。
    stat = path.stat()  # 一次读取大小和纳秒修改时刻以减少跨字段竞争。
    return {"exists": True, "size_bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}  # 返回可写入审计并比较稳定性的最小状态。


def read_stable_bytes(path: Path, label: str, attempts: int = 3) -> tuple[bytes, dict[str, Any]]:  # 接收运行文件、审计标签和尝试次数并返回一次大小/时刻不变的完整字节快照。
    require(attempts >= 1, "稳定读取尝试次数必须至少为一")  # 防止零次循环产生未初始化返回值。
    for _ in range(attempts):  # 在求解器两次追加之间最多快速尝试指定次数。
        before = snapshot_file(path)  # 读取正文前冻结存在性、大小和修改时刻。
        require(before["exists"] is True, f"{label} 文件不存在：{path}")  # 缺失权威运行原件时立即失败关闭。
        candidate = path.read_bytes()  # 一次读取当前完整字节，绝不以写模式打开运行原件。
        after = snapshot_file(path)  # 读取正文后再次取得状态以识别并发追加或替换。
        if before == after and int(after["size_bytes"]) == len(candidate):  # 前后状态和实际读取长度一致时接受单一瞬时快照。
            return candidate, after  # 返回稳定字节及其可复核文件状态。
        time.sleep(0.1)  # 短暂让出一百毫秒以跨过求解器当前日志刷写窗口。
    raise RuntimeError(f"{label} 在 {attempts} 次读取期间持续变化")  # 多次重叠写入时不基于混合状态创建 ABT。


def process_record(process: psutil.Process) -> dict[str, Any]:  # 接收可读进程对象并返回防 PID 回收的精确身份记录。
    return {"pid": int(process.pid), "ppid": int(process.ppid()), "name": str(process.name()), "create_time_epoch_seconds": float(process.create_time()), "executable": str(Path(process.exe()).resolve()), "command_line": [str(value) for value in process.cmdline()]}  # 冻结 PID、父 PID、名称、创建时刻、二进制和参数数组。


def record_identity_tuple(record: dict[str, Any]) -> tuple[int, float, str, tuple[str, ...]]:  # 接收进程记录并返回可排序比较的四重身份元组。
    return (int(record["pid"]), float(record["create_time_epoch_seconds"]), str(Path(str(record["executable"])).resolve()).casefold(), tuple(str(value) for value in record["command_line"]))  # 排除资源波动字段并保留防复用身份。


def exact_process_alive(record: dict[str, Any]) -> bool:  # 接收冻结身份并判断同一进程是否仍存活，权限异常失败关闭。
    try:  # 进程可能自然退出、成为僵尸或 PID 被复用。
        process = psutil.Process(int(record["pid"]))  # 按冻结 PID 取得当前对象但不单凭 PID 作结论。
        return record_identity_tuple(process_record(process)) == record_identity_tuple(record)  # 四重身份完全一致才确认仍存活。
    except (psutil.NoSuchProcess, psutil.ZombieProcess):  # 进程已经消失或不可执行僵尸可视为不再运行。
        return False  # 返回原身份已经退出语义。
    except (psutil.AccessDenied, KeyError, TypeError, ValueError, OSError, RuntimeError) as error:  # 权限或字段异常无法证明安全状态。
        raise RuntimeError(f"无法严格复核进程身份：{error}") from error  # 失败关闭且不创建 ABT。


def related_processes(jobname: str, solver_dir: Path, main_identity: dict[str, Any]) -> list[dict[str, Any]]:  # 接收 job、solver 和主身份并返回当前精确相关 ANSYS 进程记录。
    records: list[dict[str, Any]] = []  # 初始化当前本 job 进程集合。
    main_pid = int(main_identity["pid"])  # 读取冻结包装器 PID 供父子和主身份纳入。
    for process in psutil.process_iter(["pid", "name"]):  # 遍历系统进程并只对冻结监控器批准的求解映像读取完整身份。
        try:  # 候选可能在读取期间退出、拒绝访问或成为僵尸。
            process_name = str(process.info.get("name") or "").casefold()  # 归一化映像名供快速候选筛选。
            if process_name not in SOLVER_PROCESS_NAMES:  # 用精确白名单排除 ansyslmd 等许可证服务，同时纳入 MPI/Hydra worker。
                continue  # 跳过非批准求解候选以避免无关 AccessDenied 阻断本 job 审计。
            record = process_record(process)  # 对候选冻结 PID、时刻、二进制和命令行。
        except (psutil.NoSuchProcess, psutil.ZombieProcess):  # 枚举后消失的瞬时进程不进入当前集合。
            continue  # 继续检查其余候选。
        except (psutil.AccessDenied, OSError, RuntimeError) as error:  # 无法读取批准求解候选时不能证明它与本 job 无关。
            raise RuntimeError(f"无法审计批准求解候选进程 {process.info.get('pid')}：{error}") from error  # 对白名单候选失败关闭且不请求停机。
        command_line_text = " ".join(str(value) for value in record["command_line"]).casefold()  # 合并完整参数供 job 和 solver 双条件识别。
        belongs_by_command = jobname.casefold() in command_line_text and str(solver_dir).casefold() in command_line_text  # 两项同时命中才是本运行 worker。
        belongs_by_main = int(record["pid"]) == main_pid and record_identity_tuple(record) == record_identity_tuple(main_identity)  # 四重身份一致时纳入包装主进程。
        if belongs_by_command or belongs_by_main:  # 当前候选由命令行或冻结主身份明确归属本 job。
            records.append(record)  # 保存完整身份供认领和动作前再次复核。
    records.sort(key=lambda value: int(value["pid"]))  # 按 PID 稳定排序便于哈希工件与样本集合比较。
    return records  # 返回不含模糊名称匹配的精确相关集合。


def validate_decision(run_dir: Path) -> dict[str, Any]:  # 接收规范运行目录并返回全部充分性门通过后的停机决策上下文。
    manifest_path = run_dir / "manifest.json"  # 定位准备态运行身份和启动参数清单。
    status_path = run_dir / "C10_static_status.json"  # 定位仍为准备/执行中语义的根状态。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 定位启动前完整准备账本。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后不可覆盖最小启动记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位主包装器防 PID 回收身份。
    monitor_claim_path = run_dir / "qa" / "runtime_hard_stop_monitor_claim.json"  # 定位冻结监控器认领。
    monitor_samples_path = run_dir / "qa" / "runtime_hard_stop_monitor_samples.jsonl"  # 定位持续监控 JSONL 流水。
    monitor_final_path = run_dir / "qa" / "runtime_hard_stop_monitor_final.json"  # 定位只应在运行退出后出现的监控终态。
    manifest = read_json(manifest_path)  # 读取当前自适应运行清单。
    root_status = read_json(status_path)  # 读取准备态根状态并确认尚未最终化。
    launch_claim = read_json(launch_claim_path)  # 读取进程创建前的参数和资源认领。
    launch = read_json(launch_path)  # 读取真实主 PID、命令和三段哈希链。
    identity = read_json(identity_path)  # 读取操作系统真实主进程身份。
    monitor_claim = read_json(monitor_claim_path)  # 读取监控脚本、启动链和初始相关进程身份。
    require(not monitor_final_path.exists(), "冻结监控器已经提交终态，运行不再允许充分性停机")  # 已退出或硬停运行不得再创建 ABT。
    require(manifest.get("schema_version") == 8 and root_status.get("schema_version") == 3, "manifest 或根状态 schema 不是当前自适应版本")  # 阻断历史包借用此工具。
    require(manifest.get("run_name") == run_dir.name and root_status.get("run_name") == run_dir.name, "manifest 或根状态运行名错配")  # 关闭目录复制和改名。
    require(manifest.get("jobname") == root_status.get("jobname") == launch_claim.get("jobname") == launch.get("jobname") == identity.get("jobname") == monitor_claim.get("jobname"), "六段工件 jobname 不一致")  # 固定唯一结果文件族。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "准备清单或根状态已被最终化")  # 只处理尚在运行的原始准备包。
    require(manifest.get("diagnostic_subtype") == EXPECTED_SUBTYPE and root_status.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "运行不是批准的自适应迁移子类型")  # 阻断固定步或 K5 诊断。
    require(manifest.get("single_variable_change") == EXPECTED_SINGLE_CHANGE and root_status.get("single_variable_change") == EXPECTED_SINGLE_CHANGE, "唯一变量不是 LS2 NSBMX 200→2000")  # 保持因果路径不变。
    require(manifest.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73" and manifest.get("mpc184_keyopt5_static") == 0, "拓扑或 TYPE72 K5 不是批准值")  # 阻断旧串联约束和已证伪 K5。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False, "manifest 意外允许模态或生产声明")  # 本动作只结束诊断静力运行。
    prepared_entries = verify_prepared_ledger(ledger_path, run_dir)  # 逐项复算全部启动前工件字节。
    ledger_sha256 = sha256_file(ledger_path)  # 计算已通过逐项复算的准备账本自身摘要。
    manifest_sha256 = sha256_file(manifest_path)  # 计算受准备账本保护的 manifest 摘要。
    require(launch_claim.get("schema_version") == 1 and launch_claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED", "启动认领状态错误")  # 只接受新版 Popen 前排他认领。
    require(launch.get("schema_version") == 1 and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "最小启动记录状态错误")  # 只接受新版 Popen 后记录。
    require(identity.get("schema_version") == 1 and identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED", "增强主进程身份状态错误")  # 身份捕获失败不能触发停机。
    require(launch_claim.get("manifest_sha256") == manifest_sha256 and launch.get("manifest_sha256") == manifest_sha256, "启动链 manifest 摘要漂移")  # 关闭认领两侧清单变化。
    require(launch_claim.get("prepared_ledger_sha256") == ledger_sha256 and launch.get("prepared_ledger_sha256") == ledger_sha256, "启动链准备账本摘要漂移")  # 关闭认领两侧输入变化。
    require(int(launch_claim.get("prepared_ledger_entry_count", -1)) == len(prepared_entries) == int(launch.get("prepared_ledger_entry_count", -1)), "启动链准备条目数不一致")  # 阻断账本截断。
    require(launch.get("launch_claim_sha256") == sha256_file(launch_claim_path) and identity.get("runtime_launch_sha256") == sha256_file(launch_path), "三段启动哈希链断裂")  # 闭合 Popen 前后与增强身份。
    require(int(identity.get("pid", 0)) == int(launch.get("main_pid", -1)), "增强身份 PID 与最小启动记录不一致")  # 固定操作对象为 Popen 实际返回的包装进程。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 恢复已核对 manifest 的完整批准参数。
    require(launch_argv == [str(value) for value in launch_claim.get("launch_argv", [])] == [str(value) for value in launch.get("launch_argv", [])] == [str(value) for value in identity.get("command_line", [])], "清单、认领、启动和真实命令行不一致")  # 固定实际执行入口。
    mapdl_path = Path(launch_argv[0]).resolve()  # 以完整参数首项定位真实 MAPDL 包装二进制。
    require(mapdl_path == Path(str(manifest.get("mapdl_executable", ""))).resolve() and mapdl_path.is_file(), "MAPDL 二进制路径与 manifest 不一致或缺失")  # 固定批准求解器位置。
    require(sha256_file(mapdl_path) == str(manifest.get("mapdl_executable_sha256", "")), "MAPDL 二进制 SHA-256 与 manifest 不一致")  # 阻断版本或文件字节漂移。
    require(str(Path(str(identity.get("executable", ""))).resolve()).casefold() == str(mapdl_path).casefold(), "增强进程可执行文件与批准 MAPDL 二进制不一致")  # 关闭命令行首项与操作系统实际映像分叉。
    solver_dir = (run_dir / "solver").resolve()  # 定位本运行唯一 MAPDL 工作目录。
    require(solver_dir.is_dir() and Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir, "启动 -dir 未指向本 run solver")  # 阻断跨运行输出污染。
    require(argument_value(launch_argv, "-j") == str(manifest["jobname"]) and argument_value(launch_argv, "-np") == "1", "启动 jobname 或进程数不是批准值")  # 固定 SMP1 job 身份。
    main_input_path = Path(argument_value(launch_argv, "-i")).resolve()  # 定位实际传入 MAPDL 的主控输入。
    input_relative = main_input_path.relative_to(run_dir).as_posix()  # 形成准备账本内相对路径。
    require(input_relative in prepared_entries and prepared_entries[input_relative] == manifest.get("main_input_sha256") == sha256_file(main_input_path), "实际主控输入未被准备账本和 manifest 共同冻结")  # 三方关闭输入漂移。
    commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in main_input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 规范化真实 APDL 命令供自适应合同计数。
    require(commands.count("NSUBST,200,2000,200") == 1 and commands.count("NSUBST,200,200,200") == 0 and sum(1 for command in commands if command.startswith("CNVTOL,")) == 4, "主控 NSUBST 或 CNVTOL 合同漂移")  # 禁止以放宽门限或其他步长运行借用充分性结论。
    require(monitor_claim.get("schema_version") == 1 and monitor_claim.get("status") == "MONITOR_CLAIMED", "冻结监控认领状态错误")  # 要求硬停监控已在运行初期附着。
    require(monitor_claim.get("run_name") == run_dir.name and monitor_claim.get("runtime_launch_sha256") == sha256_file(launch_path) and monitor_claim.get("runtime_launch_claim_sha256") == sha256_file(launch_claim_path) and monitor_claim.get("runtime_process_identity_sha256") == sha256_file(identity_path), "监控认领与当前启动链错配")  # 关闭跨运行监控工件复制。
    monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 规范化冻结监控器快照路径。
    require(monitor_relative in prepared_entries and monitor_claim.get("monitor_script_sha256") == manifest.get("runtime_monitor_script_sha256") == prepared_entries[monitor_relative], "监控代码在认领、清单和账本间不一致")  # 固定持续监控实现字节。
    require(monitor_samples_path.is_file() and monitor_samples_path.stat().st_size > 0, "监控样本流水缺失或为空")  # 停机前必须存在持续样本。
    monitor_samples_before = snapshot_file(monitor_samples_path)  # 读取流水前冻结大小和修改时刻供并发追加检测。
    monitor_samples_bytes = monitor_samples_path.read_bytes()  # 一次读取当前完整流水字节作为决策快照。
    monitor_samples_after = snapshot_file(monitor_samples_path)  # 读取后再次取得状态以排除半行跨界。
    require(monitor_samples_before == monitor_samples_after and int(monitor_samples_after["size_bytes"]) == len(monitor_samples_bytes), "监控样本流水在决策读取期间变化")  # 只解析单一稳定瞬时快照。
    sample_lines = [line for line in monitor_samples_bytes.decode("utf-8", errors="strict").splitlines() if line.strip()]  # 从冻结字节解码全部完整 JSONL 行供硬事件和连续性复核。
    samples = [json.loads(line) for line in sample_lines]  # 逐行解析，任何破损记录失败关闭。
    require(all(isinstance(sample, dict) and sample.get("schema_version") == 1 for sample in samples), "监控流水含非对象或未知 schema")  # 只接受冻结第一版样本。
    require([int(sample.get("sample_index", -1)) for sample in samples] == list(range(1, len(samples) + 1)), "监控样本序号不连续")  # 防止流水删行或重排。
    require(all(sample.get("new_hard_events") == [] for sample in samples), "监控流水已经记录硬停事件，操作员充分性停机不得抢占")  # 资源、FATAL、秩或主元硬停优先。
    latest_sample = samples[-1]  # 读取最后一个完整监控样本供活性和精确进程交叉核对。
    sampled_at = datetime.fromisoformat(str(latest_sample["sampled_at_utc"]).replace("Z", "+00:00"))  # 解析带时区样本时刻。
    sample_age_seconds = (datetime.now(timezone.utc) - sampled_at.astimezone(timezone.utc)).total_seconds()  # 计算距当前的真实 UTC 年龄。
    require(0.0 <= sample_age_seconds <= LATEST_MONITOR_SAMPLE_MAX_AGE_SECONDS, f"最新监控样本不新鲜：{sample_age_seconds:.3f} 秒")  # 证明监控仍在持续工作而不是历史残留。
    current_elapsed_seconds = float(latest_sample.get("elapsed_seconds", float("nan")))  # 读取与该样本 OUT 偏移同一轮记录的运行 elapsed 供门 B 下界投影。
    require(math.isfinite(current_elapsed_seconds) and current_elapsed_seconds > 0.0, "最新监控样本 elapsed 不是有限正数")  # 阻断缺失、NaN、无穷或非正运行时钟。
    require(latest_sample.get("lock_file", {}).get("exists") is True, "最新监控样本未见运行中 MAPDL lock")  # 运行必须仍活跃才能请求 ABT。
    require(all(int(value) == EXPECTED_EQUATION_COUNT for value in latest_sample.get("new_equation_counts", [])), "最新样本出现方程数漂移")  # 当前增量可无新报告或含多个重复报告，但每项必须是冻结值。
    current_related = related_processes(str(manifest["jobname"]), solver_dir, identity)  # 获取当前本 job 完整进程身份集合。
    require(current_related and any(record_identity_tuple(record) == record_identity_tuple(identity) for record in current_related), "冻结主进程身份当前不存活")  # 精确确认包装根仍在运行。
    sample_related = latest_sample.get("related_processes")  # 读取监控最后样本绑定的相关进程列表。
    require(isinstance(sample_related, list) and sample_related, "最新监控样本缺少相关进程身份")  # 空进程样本可能位于退出交接窗口，不允许操作。
    require({record_identity_tuple(record) for record in current_related} == {record_identity_tuple(record) for record in sample_related}, "当前精确进程集合与最新监控样本不一致")  # 动作前闭合独立工具和冻结监控两套身份识别。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 从四方一致的冻结启动参数定位权威 OUT 原件。
    require(output_path == solver_dir / f"{manifest['jobname']}.out" and output_path.is_file(), "启动 OUT 未指向本 solver/job 原件或文件缺失")  # 关闭跨 job 日志借用门 B 尾状态的路径。
    out_offset_bytes = int(latest_sample.get("out_offset_bytes", -1))  # 读取监控样本当时已完整扫描的 OUT 前缀长度。
    sampled_out_state = latest_sample.get("out_file")  # 读取同一监控样本记录的 OUT 文件状态。
    require(isinstance(sampled_out_state, dict) and sampled_out_state.get("exists") is True and int(sampled_out_state.get("size_bytes", -1)) == out_offset_bytes and out_offset_bytes > 0, "最新监控样本 OUT 偏移与文件状态不一致")  # 保证 elapsed 与 OUT 前缀属于同一次样本。
    current_out_bytes, current_out_snapshot = read_stable_bytes(output_path, "OUT")  # 取得决策时未并发变化的完整 OUT 用于排除样本后拒绝或接受。
    require(len(current_out_bytes) >= out_offset_bytes, "当前 OUT 比最新监控样本前缀更短")  # 阻断文件截断、替换或错误运行复制。
    sampled_out_bytes = current_out_bytes[:out_offset_bytes]  # 精确恢复最新监控 elapsed 时刻已经可见的 OUT 前缀。
    mntr_path = solver_dir / f"{manifest['jobname']}.mntr"  # 定位原生已接受子步与 Elap(s) 历史。
    require(mntr_path.is_file() and mntr_path.stat().st_size > 0, "MNTR 缺失或为空")  # 无原生接受行不能推断速度。
    mntr_before = snapshot_file(mntr_path)  # 读取 MNTR 前状态供并发变化检测。
    mntr_bytes = mntr_path.read_bytes()  # 一次冻结当前完整 MNTR 字节用于解析和认领哈希。
    mntr_after = snapshot_file(mntr_path)  # 读取后状态确认解析期间未追加接受行。
    require(mntr_before == mntr_after and int(mntr_after["size_bytes"]) == len(mntr_bytes), "MNTR 在决策读取期间发生变化")  # 防止速度证据跨两个状态。
    mntr_rows = parse_mntr_bytes(mntr_bytes)  # 解析冻结字节中的全部接受子步。
    sufficiency = evaluate_mntr_sufficiency(mntr_rows, sampled_out_bytes, current_out_bytes, current_elapsed_seconds)  # 按接受行数量自动关闭门 A 或同步 OUT/elapsed 门 B 的全部数学与状态条件。
    return {"run_dir": run_dir, "manifest": manifest, "manifest_path": manifest_path, "prepared_ledger_path": ledger_path, "prepared_ledger_sha256": ledger_sha256, "prepared_entry_count": len(prepared_entries), "launch_claim_path": launch_claim_path, "launch_path": launch_path, "identity_path": identity_path, "monitor_claim_path": monitor_claim_path, "monitor_samples_path": monitor_samples_path, "monitor_samples_sha256_at_decision": hashlib.sha256(monitor_samples_bytes).hexdigest(), "monitor_samples_snapshot": monitor_samples_after, "monitor_final_path": monitor_final_path, "monitor_sample_count": len(samples), "latest_monitor_sample_index": int(latest_sample["sample_index"]), "latest_monitor_sample_age_seconds": sample_age_seconds, "latest_monitor_elapsed_seconds": current_elapsed_seconds, "solver_dir": solver_dir, "jobname": str(manifest["jobname"]), "identity": identity, "current_related": current_related, "output_path": output_path, "out_snapshot": current_out_snapshot, "out_sha256_at_decision": hashlib.sha256(current_out_bytes).hexdigest(), "sampled_out_prefix_sha256": hashlib.sha256(sampled_out_bytes).hexdigest(), "sampled_out_prefix_size_bytes": len(sampled_out_bytes), "mntr_path": mntr_path, "mntr_bytes": mntr_bytes, "mntr_sha256": hashlib.sha256(mntr_bytes).hexdigest(), "mntr_snapshot": mntr_after, **sufficiency}  # 合并写认领和动作前复核所需的完整只读上下文与双门投影证据。


def resolve_run(run_dir_value: Path) -> Path:  # 接收用户路径并返回通过项目边界和运行族门的规范绝对目录。
    run_dir = run_dir_value.resolve()  # 消除相对段、当前目录和符号路径歧义。
    require(run_dir.is_dir(), f"运行目录不存在：{run_dir}")  # 拒绝缺失或普通文件路径。
    require(run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs 根：{run_dir}")  # 只允许证据根直接子运行。
    require(run_dir.name.startswith(EXPECTED_RUN_PREFIX), f"运行不属于迁移诊断族：{run_dir.name}")  # 阻断其他模型线。
    return run_dir  # 返回已通过边界与族名检查的目标。


def file_triplet_state(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:  # 接收上下文并返回 OUT、ERR、MNTR 和 lock 四项当前快照。
    output_path = Path(argument_value([str(value) for value in context["manifest"]["launch_argv"]], "-o")).resolve()  # 从冻结参数定位权威 OUT。
    error_path = context["solver_dir"] / f"{context['jobname']}.err"  # 按唯一 jobname 定位 ERR。
    lock_path = context["solver_dir"] / f"{context['jobname']}.lock"  # 按唯一 jobname 定位运行 lock。
    return (snapshot_file(output_path), snapshot_file(error_path), snapshot_file(context["mntr_path"]), snapshot_file(lock_path))  # 一次返回退出稳定性所需四项状态。


def monitor_still_clean_before_abort(context: dict[str, Any]) -> tuple[bool, str | None]:  # 接收决策上下文并返回 ABT 前冻结监控是否仍无硬事件和终态。
    if context["monitor_final_path"].exists():  # 冻结监控器已结束表示运行或硬停状态在认领后变化。
        return (False, "MONITOR_FINAL_APPEARED_AFTER_OPERATOR_CLAIM")  # 阻断操作员 ABT 与已发生退出/硬停竞争。
    stable_bytes: bytes | None = None  # 初始化尚未取得的单一稳定 JSONL 字节快照。
    for _ in range(3):  # 最多连续尝试三次以跨过十秒采样器恰好追加的一次窗口。
        before = snapshot_file(context["monitor_samples_path"])  # 读取前冻结流水大小和时刻。
        candidate = context["monitor_samples_path"].read_bytes()  # 一次读取当前完整字节。
        after = snapshot_file(context["monitor_samples_path"])  # 读取后取得状态供半行检测。
        if before == after and int(after["size_bytes"]) == len(candidate):  # 大小、时刻和读取长度一致时取得稳定快照。
            stable_bytes = candidate  # 保存完整字节并结束重试。
            break  # 跳出最多三次快速读取循环。
    if stable_bytes is None:  # 三次均与采样器写入重叠时不冒险创建 ABT。
        return (False, "MONITOR_SAMPLES_CONTINUOUSLY_CHANGED_DURING_PRE_ABORT_RECHECK")  # 返回可写入无动作终态的明确原因。
    try:  # 任何新破损行或字段异常都必须失败关闭。
        samples = [json.loads(line) for line in stable_bytes.decode("utf-8", errors="strict").splitlines() if line.strip()]  # 解析当前全部完整 JSONL 行。
    except (UnicodeDecodeError, json.JSONDecodeError) as error:  # 捕获编码或语法破损而不吞掉原因。
        return (False, f"MONITOR_SAMPLES_PARSE_FAILED_BEFORE_ABORT:{error}")  # 返回无 ABT 的审计原因。
    if not samples or any(not isinstance(sample, dict) or sample.get("new_hard_events") != [] for sample in samples):  # 任一硬事件或非对象记录都使监控器动作优先。
        return (False, "MONITOR_HARD_EVENT_OR_INVALID_SAMPLE_APPEARED_BEFORE_ABORT")  # 阻断操作员抢占硬停控制权。
    return (True, None)  # 证明 ABT 前最新完整监控流水仍无硬事件且无终态。


def validate_monitor_final(context: dict[str, Any]) -> tuple[dict[str, Any], str | None]:  # 接收上下文并返回冻结监控终态完整审计摘要及可选不干净原因。
    final_path = context["monitor_final_path"]  # 读取固定监控终态路径。
    require(final_path.is_file(), "进程退出后冻结监控器未提交终态")  # 无持续监控闭环时不能声明安全退出。
    final: dict[str, Any] | None = None  # 初始化尚未取得的完整稳定监控终态对象。
    for _ in range(3):  # 最多等待三次以跨过排他文件名已出现但正文仍写入的极短窗口。
        before = snapshot_file(final_path)  # 读取前冻结大小和修改时刻。
        try:  # JSON 可能在本轮读取时仍未写完，需要重试而非立即归类为不干净终态。
            candidate = json.loads(final_path.read_text(encoding="utf-8", errors="strict"))  # 严格读取当前终态正文。
        except (UnicodeDecodeError, json.JSONDecodeError):  # 捕获半写编码或语法状态并等待下一次。
            candidate = None  # 标记本轮尚未取得完整对象。
        after = snapshot_file(final_path)  # 读取后再次取得状态供并发写检测。
        if before == after and isinstance(candidate, dict):  # 文件状态不变且顶层对象完整时接受本轮快照。
            final = candidate  # 保存稳定对象并结束重试。
            break  # 跳出最多三次终态读取循环。
        time.sleep(1.0)  # 等待一秒供冻结监控器完成 fsync 和关闭文件。
    require(isinstance(final, dict), "冻结监控终态在三次读取后仍不完整或持续变化")  # 禁止半写 JSON 被误判为退出结论。
    controller_abort = final.get("controller_abort")  # 保留监控器中止对象，包括可能发生的 terminate/kill disposition。
    hard_events = final.get("hard_events")  # 保留监控器记录的全部硬事件而不是仅输出数量。
    final_related = final.get("final_related_processes")  # 保留监控器终态看到的完整相关进程集合。
    final_lock = final.get("final_lock_file")  # 保留监控器终态 lock 快照供独立退出审计。
    sample_count_value = final.get("sample_count")  # 读取可能损坏或缺失的样本数而不让字段异常逃逸。
    try:  # 样本数字段可能被半结构化手工内容污染，需要转换为显式阻断而不是未封板异常。
        sample_count = int(sample_count_value)  # 把合法整数或整数字符串规范为机器整数。
    except (TypeError, ValueError):  # 缺失、对象或非整数字符串均不能形成干净终态。
        sample_count = None  # 用空值保留字段无效事实并交由原因列表判定。
    samples_bytes, _ = read_stable_bytes(context["monitor_samples_path"], "监控终态 JSONL 流水")  # 在监控器退出后取得大小和时刻稳定的完整样本流水原件。
    samples_lines = [line for line in samples_bytes.decode("utf-8", errors="strict").splitlines() if line.strip()]  # 严格解码并去除不承载记录的空行。
    samples_objects = [json.loads(line) for line in samples_lines]  # 完整解析每条 JSONL 记录，破损行由外层重试或超时封板。
    samples_sequence_valid = all(isinstance(sample, dict) for sample in samples_objects) and [int(sample.get("sample_index", -1)) for sample in samples_objects] == list(range(1, len(samples_objects) + 1))  # 复核顶层对象和从一开始连续的样本序号。
    samples_sha256_actual = hashlib.sha256(samples_bytes).hexdigest()  # 复算最终 JSONL 流水原件摘要供终态闭环。
    samples_path_claimed = final.get("samples_path")  # 读取冻结监控终态声明的样本流水绝对路径。
    samples_path_matches = isinstance(samples_path_claimed, str) and Path(samples_path_claimed).resolve() == context["monitor_samples_path"].resolve()  # 阻断跨运行流水被终态引用。
    audit = {"path": final_path.relative_to(context["run_dir"]).as_posix(), "sha256": sha256_file(final_path), "schema_version": final.get("schema_version"), "run_name": final.get("run_name"), "jobname": final.get("jobname"), "status": final.get("status"), "sample_count": sample_count, "actual_sample_line_count": len(samples_objects), "sample_sequence_valid": samples_sequence_valid, "samples_path_claimed": samples_path_claimed, "samples_path_matches": samples_path_matches, "samples_sha256_claimed": final.get("samples_sha256"), "samples_sha256_actual": samples_sha256_actual, "hard_events": hard_events, "controller_abort": controller_abort, "final_related_processes": final_related, "final_lock_file": final_lock, "monitor_block_reason": final.get("monitor_block_reason"), "monitor_claim_sha256": final.get("monitor_claim_sha256")}  # 即使不干净也保存终态、完整流水哈希/行数/序号、硬事件和控制器进程处置证据。
    reasons: list[str] = []  # 初始化全部监控终态不干净原因，避免首项异常掩盖后续证据。
    if final.get("schema_version") != 1 or final.get("run_name") != context["run_dir"].name or final.get("jobname") != context["jobname"]:  # 检查 schema 与运行/job 身份闭合。
        reasons.append("MONITOR_FINAL_SCHEMA_OR_RUN_JOB_IDENTITY_MISMATCH")  # 记录跨版本或跨运行复制风险。
    if final.get("status") != "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP":  # 只接受冻结监控器定义的无硬停稳定退出。
        reasons.append(f"MONITOR_FINAL_STATUS_NOT_CLEAN:{final.get('status')}")  # 保留真实状态供操作员终态披露。
    if hard_events != []:  # 空数组以外的缺失、错型或真实事件均不干净。
        reasons.append("MONITOR_FINAL_HARD_EVENTS_NOT_EMPTY_OR_INVALID")  # 阻断操作员 ABT 掩盖硬停事件。
    if not isinstance(controller_abort, dict) or controller_abort.get("requested") is not False:  # 要求监控器明确记录自己未请求中止。
        reasons.append("MONITOR_CONTROLLER_ABORT_REQUESTED_OR_INVALID")  # 保留 controller_abort 原对象以披露可能的强制处置。
    if final_related != [] or not isinstance(final_lock, dict) or final_lock.get("exists") is not False or final.get("monitor_block_reason") is not None:  # 检查进程、lock 和监控阻断三项退出门。
        reasons.append("MONITOR_FINAL_PROCESS_LOCK_OR_BLOCK_STATE_NOT_CLEAN")  # 任何一项不闭合都禁止成功声明。
    if final.get("monitor_claim_sha256") != sha256_file(context["monitor_claim_path"]):  # 核对终态引用的初始监控认领摘要。
        reasons.append("MONITOR_FINAL_CLAIM_SHA256_MISMATCH")  # 记录哈希链断裂。
    if sample_count is None or sample_count < 1:  # 要求至少一个有效监控样本并拒绝错型字段。
        reasons.append("MONITOR_FINAL_SAMPLE_COUNT_INVALID")  # 把字段异常归一为可审计不干净原因。
    if sample_count != len(samples_objects) or not samples_sequence_valid:  # 终态样本数必须等于实际非空 JSONL 行数且序号连续。
        reasons.append("MONITOR_FINAL_SAMPLE_COUNT_OR_SEQUENCE_MISMATCH")  # 阻断流水删行、插入、重排或终态计数漂移。
    if final.get("samples_sha256") != samples_sha256_actual or not samples_path_matches:  # 同时核对终态声明的流水摘要和唯一绝对路径。
        reasons.append("MONITOR_FINAL_SAMPLES_SHA256_OR_PATH_MISMATCH")  # 关闭监控终态与完整 JSONL 流水之间最后一段证据链。
    return audit, None if not reasons else ";".join(reasons)  # 成功返回空原因；不干净时仍返回完整 SHA、状态和 controller disposition。


def write_stop_final(context: dict[str, Any], claim_path: Path, explanation_path: Path, abort_path: Path, abort_created: bool, status: str, pre_abort_recheck_started_at_utc: str, exit_confirmed: bool, stable_state: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None, wait_seconds: float, poll_count: int, monitor_final_audit: dict[str, Any] | None, block_reason: str | None) -> Path:  # 接收动作证据并排他写出仅约束本工具行为的操作员停机终态。
    final_path = context["run_dir"] / "qa" / "runtime_operator_stop_final.json"  # 定位本运行唯一操作员停机终态。
    final = {"schema_version": 1, "status": status, "run_name": context["run_dir"].name, "jobname": context["jobname"], "pre_abort_recheck_started_at_utc": pre_abort_recheck_started_at_utc, "native_abort_created_at_utc": context.get("native_abort_created_at_utc"), "finalized_at_utc": utc_now(), "operator_stop_claim_path": claim_path.relative_to(context["run_dir"]).as_posix(), "operator_stop_claim_exists": claim_path.is_file(), "operator_stop_claim_sha256": sha256_file(claim_path) if claim_path.is_file() else None, "operator_stop_explanation_path": explanation_path.relative_to(context["run_dir"]).as_posix(), "operator_stop_explanation_exists": explanation_path.is_file(), "operator_stop_explanation_sha256": sha256_file(explanation_path) if explanation_path.is_file() else None, "native_abort_path": abort_path.relative_to(context["run_dir"]).as_posix(), "native_abort_payload_text_ascii": context["native_abort_payload_text_ascii"], "native_abort_payload_length_bytes": context["native_abort_payload_length_bytes"], "native_abort_payload_hex": context["native_abort_payload_hex"], "native_abort_payload_sha256": context["native_abort_payload_sha256"], "native_abort_payload_contract_verified_before_write": context["native_abort_payload_contract_verified_before_write"], "native_abort_created_exclusively": bool(context["native_abort_created_exclusively"]) and abort_created, "native_abort_write_returned_bytes": context["native_abort_write_returned_bytes"], "native_abort_payload_written_fully": context["native_abort_payload_written_fully"], "native_abort_flush_completed": context["native_abort_flush_completed"], "native_abort_fsync_completed": context["native_abort_fsync_completed"], "native_abort_flush_and_fsync_completed": context["native_abort_flush_and_fsync_completed"], "native_abort_readback_length_bytes": context["native_abort_readback_length_bytes"], "native_abort_readback_hex": context["native_abort_readback_hex"], "native_abort_readback_sha256": context["native_abort_readback_sha256"], "native_abort_readback_matches_contract": context["native_abort_readback_matches_contract"], "native_abort_exists_at_finalization": abort_path.is_file(), "wait_seconds": wait_seconds, "poll_interval_seconds": POLL_INTERVAL_SECONDS, "poll_count": poll_count, "exit_confirmation_timeout_seconds": EXIT_CONFIRMATION_TIMEOUT_SECONDS, "exact_process_tree_exit_confirmed": exit_confirmed, "final_out_file": None if stable_state is None else stable_state[0], "final_err_file": None if stable_state is None else stable_state[1], "final_mntr_file": None if stable_state is None else stable_state[2], "final_lock_file": None if stable_state is None else stable_state[3], "frozen_monitor_final": monitor_final_audit, "block_reason": block_reason, "operator_tool_process_terminate_api_called": False, "operator_tool_process_kill_api_called": False, "operator_tool_forced_process_action_allowed": False, "valid_static_result_obtained": False, "modal_execution_allowed": False, "production_claim_allowed": False}  # 保持既有第一版终态 schema，并以向后兼容字段汇总精确载荷合同、真实创建/写入/同步/回读证据和绝不强杀边界。
    write_json_exclusive(final_path, final)  # 排他提交唯一终态，禁止覆盖或重复操作者改写。
    return final_path  # 返回已写出并同步磁盘的最终审计路径。


def request_sufficiency_stop(run_dir_value: Path) -> Path:  # 接收唯一运行目录并在全部充分性门通过后请求原生 ABT、等待自然退出并返回终态路径。
    context = validate_decision(resolve_run(run_dir_value))  # 在任何运行目录写入前完成准备、启动、监控、进程、MNTR 和七天投影全门。
    context.update(native_abort_evidence_template())  # 在任何运行目录写入前初始化完整载荷与动作证据，使所有失败终态都能区分计划、创建、写入、同步和回读阶段。
    qa_dir = context["run_dir"] / "qa"  # 定位已存在的运行内 QA 目录。
    claim_path = qa_dir / "runtime_operator_stop_claim.json"  # 定位必须先于 ABT 排他创建的机器认领。
    explanation_path = qa_dir / "runtime_operator_stop_claim.md"  # 定位必须先于 ABT 排他创建的相邻中文说明。
    final_path = qa_dir / "runtime_operator_stop_final.json"  # 定位 ABT 后唯一终态，动作前必须不存在。
    abort_path = context["solver_dir"] / f"{context['jobname']}.abt"  # 定位 MAPDL 按 jobname 识别的原生中止请求文件。
    require(not claim_path.exists() and not explanation_path.exists() and not final_path.exists() and not abort_path.exists(), "操作员停机 claim、说明、final 或 ABT 已存在")  # 排他阻断重复停机与既有控制动作。
    latest_two = context["latest_two"]  # 门 A 为最近两条接受行，门 B 明确为空而由 OUT 状态证据替代。
    in_progress_evidence = context["in_progress_out_evidence"]  # 门 B 保存同步样本前缀和决策时最新 OUT 的子步 2 状态机证据。
    if context["sufficiency_branch"] == "A_TWO_ACCEPTED_MINIMUM_STEPS":  # 为两个自然接受行的完整周期门 A 生成人工说明。
        later_iterations = int(latest_two[1]["iterations"])  # 读取门 A 后一个已接受最小步的原生迭代数。
        evidence_paragraph = f"MNTR 已自然接受 {len(context['ls2_rows'])} 个连续 LS2 最小子步；最近两个编号为 {int(latest_two[0]['substep'])}/{int(latest_two[1]['substep'])}，增量均为 `5E-7`，后一步使用 {later_iterations} 次平衡迭代。两行 `Elap(s)` 差值为 {context['measured_seconds_per_minimum_step']:.3f} 秒。"  # 形成门 A 的完整实测周期证据段。
    else:  # 为恰一接受行和未决第二步时长下界门 B 生成人工说明。
        later_iterations = int(in_progress_evidence["sampled_prefix"]["completed_equilibrium_iterations"])  # 读取与监控 elapsed 同步的 OUT 前缀已完整迭代数。
        evidence_paragraph = f"MNTR 恰好自然接受 1 个 LS2 最小子步，增量为 `5E-7`；与监控 elapsed 同步的 OUT 前缀证明当前仍是 LS2 子步 2 的首次连续尝试，已完整完成 {later_iterations} 次平衡迭代，且尚无接受、拒绝、二分、中止或终止事件。从首步接受 `Elap(s)={in_progress_evidence['first_accepted_step_elapsed_seconds']:.3f}` 到当前监控 `elapsed={in_progress_evidence['current_monitor_elapsed_seconds']:.3f}` 的差值 {context['measured_seconds_per_minimum_step']:.3f} 秒，只是该未完成第二步最终耗时的保守下界。"  # 明确门 B 的状态、同步来源和下界性质。
    claim = {"schema_version": 2, "status": "OPERATOR_SUFFICIENCY_STOP_CLAIMED_BEFORE_NATIVE_ABORT", "run_name": context["run_dir"].name, "jobname": context["jobname"], "claimed_at_utc": utc_now(), "tool_path": str(SCRIPT_PATH), "tool_sha256": sha256_file(SCRIPT_PATH), "prepared_ledger_sha256": context["prepared_ledger_sha256"], "prepared_ledger_entry_count": context["prepared_entry_count"], "runtime_launch_claim_sha256": sha256_file(context["launch_claim_path"]), "runtime_launch_sha256": sha256_file(context["launch_path"]), "runtime_process_identity_sha256": sha256_file(context["identity_path"]), "runtime_monitor_claim_sha256": sha256_file(context["monitor_claim_path"]), "runtime_monitor_samples_sha256_at_decision": context["monitor_samples_sha256_at_decision"], "runtime_monitor_sample_count_at_decision": context["monitor_sample_count"], "latest_monitor_sample_index": context["latest_monitor_sample_index"], "latest_monitor_sample_age_seconds": context["latest_monitor_sample_age_seconds"], "latest_monitor_elapsed_seconds": context["latest_monitor_elapsed_seconds"], "exact_related_processes_before_claim": context["current_related"], "mntr_path": context["mntr_path"].relative_to(context["run_dir"]).as_posix(), "mntr_sha256_at_decision": context["mntr_sha256"], "out_path": context["output_path"].relative_to(context["run_dir"]).as_posix(), "out_sha256_at_decision": context["out_sha256_at_decision"], "sampled_out_prefix_sha256": context["sampled_out_prefix_sha256"], "sampled_out_prefix_size_bytes": context["sampled_out_prefix_size_bytes"], "sufficiency_branch": context["sufficiency_branch"], "accepted_pair_gate_satisfied": context["sufficiency_branch"] == "A_TWO_ACCEPTED_MINIMUM_STEPS", "in_progress_lower_bound_gate_satisfied": context["sufficiency_branch"] == "B_ONE_ACCEPTED_PLUS_IN_PROGRESS_SECOND_STEP_LOWER_BOUND", "accepted_ls2_substep_count": len(context["ls2_rows"]), "accepted_ls2_rows": context["ls2_rows"], "latest_two_ls2_rows": latest_two, "in_progress_second_step_out_evidence": in_progress_evidence, "later_step_completed_iterations": later_iterations, "projection_basis": context["projection_basis"], "projection_is_conservative_lower_bound": context["projection_is_conservative_lower_bound"], "measured_or_lower_bound_seconds_per_minimum_step": context["measured_seconds_per_minimum_step"], "accepted_migration_time": context["accepted_migration"], "remaining_migration_time": context["remaining_migration"], "remaining_minimum_step_count": context["remaining_minimum_steps"], "projected_remaining_seconds": context["projected_remaining_seconds"], "projection_threshold_seconds": SUFFICIENCY_HORIZON_SECONDS, "projection_strictly_exceeds_seven_days": True, "native_abort_path_planned": abort_path.relative_to(context["run_dir"]).as_posix(), "native_abort_payload_text_ascii_planned": NATIVE_ABORT_PAYLOAD.decode("ascii"), "native_abort_payload_length_bytes_planned": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex_planned": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256_planned": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_exclusive_create_required": True, "native_abort_flush_fsync_and_readback_required": True, "operator_explanation_path": explanation_path.relative_to(context["run_dir"]).as_posix(), "operator_tool_active_kill_or_terminate_forbidden": True, "modal_execution_allowed": False, "production_claim_allowed": False}  # 保持既有第二版认领 schema，并以向后兼容字段冻结双门投影和十字节 ABT 动作合同。
    claim_text = render_json(claim)  # 在任何写盘前完成合法 JSON 渲染和非有限数拒绝。
    explanation_text = f"# C10 自适应迁移运行充分性停机认领\n\n本认领仅针对 `{context['run_dir'].name}` / `{context['jobname']}`，采用 `{context['sufficiency_branch']}`。{evidence_paragraph}\n\n按剩余 {context['remaining_minimum_steps']} 个 `5E-7` 最小步线性投影为 {context['projected_remaining_seconds']:.3f} 秒，即 {context['projected_remaining_seconds'] / 86400.0:.3f} 天，严格超过七天。门 B 的数值明确是由尚未完成第二步已耗时形成的保守下界，不是第二步已收敛或全部未来步骤耗时恒定的证明。\n\n该判断只说明继续运行的时间代价已足以形成停止诊断的决定，不说明 beta=0 静力端点已经取得。机器认领和本中文说明均必须先于 `{abort_path.name}` 排他落盘；随后以二进制排他创建写入精确十字节 ASCII `nonlinear\\n`（hex `{NATIVE_ABORT_PAYLOAD_HEX}`，SHA-256 `{NATIVE_ABORT_PAYLOAD_SHA256}`），完成 flush、fsync 和同句柄回读一致性校验后，仅等待 MAPDL 自行退出。本工具没有主动结束、强制结束或发送进程信号的代码路径。退出后的部分 RST、数据库和重启动文件不得用于模态或生产。\n"  # 生成人工可核对的双门证据、公式、精确 ABT 字节合同、动作顺序和用途禁令说明。
    write_text_exclusive(claim_path, claim_text)  # 第一步排他写出机器认领并同步磁盘。
    try:  # claim 已提交后，中文说明写入失败也必须形成无 ABT 的唯一终态封板。
        write_text_exclusive(explanation_path, explanation_text)  # 第二步排他写出相邻中文说明并同步磁盘，仍未创建 ABT。
    except (OSError, RuntimeError, UnicodeError) as error:  # 捕获目录、权限、编码、排他竞态、写入和同步异常。
        pre_abort_recheck_started_at_utc = utc_now()  # 为无动作终态记录发现说明写入失败的真实时刻。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_EXPLANATION_WRITE_FAILED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, f"EXPLANATION_EXCLUSIVE_WRITE_OR_SYNC_EXCEPTION:{error}")  # 即使说明缺失也用存在性/空摘要字段封板。
        raise RuntimeError(f"中文说明写入失败，未创建 ABT；审计见 {stopped_final}") from error  # 保留原异常并保持求解器不受动作。
    pre_abort_recheck_started_at_utc = utc_now()  # 记录两份先行证据完成后、任何动作前复核真正开始的时刻。
    try:  # 监控流水读取或字段竞态异常必须形成无 ABT final。
        monitor_clean, monitor_block_reason = monitor_still_clean_before_abort(context)  # 复核监控器仍未发现硬事件或提交终态。
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:  # 收敛全部预期文件和字段异常。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_MONITOR_RECHECK_EXCEPTION_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, f"MONITOR_RECHECK_EXCEPTION:{error}")  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"监控复核异常，未创建 ABT；审计见 {stopped_final}") from error  # 失败关闭并保留异常链。
    if not monitor_clean:  # 监控状态在决策与 ABT 之间变化时把控制权留给冻结监控器。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_MONITOR_STATE_CHANGED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, monitor_block_reason)  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"监控状态在认领后变化，未创建 ABT；审计见 {stopped_final}")  # 失败关闭并保持求解器/监控器原控制流。
    try:  # MNTR 和门 B OUT 状态读取异常必须形成无 ABT final。
        mntr_changed = snapshot_file(context["mntr_path"]) != context["mntr_snapshot"] or sha256_file(context["mntr_path"]) != context["mntr_sha256"]  # 检查认领依据的接受行是否发生任何字节变化。
        if not mntr_changed and context["sufficiency_branch"] == "B_ONE_ACCEPTED_PLUS_IN_PROGRESS_SECOND_STEP_LOWER_BOUND":  # 门 B 还必须证明认领后 OUT 尾状态仍未接受、拒绝或二分。
            rechecked_out_bytes, _ = read_stable_bytes(context["output_path"], "认领后 OUT")  # 取得 ABT 前最后稳定 OUT 快照。
            rechecked_out_evidence = parse_out_in_progress_second_step(rechecked_out_bytes)  # 重新执行完整状态机门而不是只检查文件增长。
            require(int(rechecked_out_evidence["completed_equilibrium_iterations"]) >= int(context["in_progress_out_evidence"]["current_snapshot"]["completed_equilibrium_iterations"]), "认领后 OUT 迭代证据倒退")  # 阻断替换、截断或状态回退。
    except (OSError, RuntimeError, UnicodeError, KeyError, TypeError, ValueError) as error:  # 捕获稳定读取、解析、状态或字段异常。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_DYNAMIC_EVIDENCE_RECHECK_FAILED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, f"MNTR_OR_OUT_RECHECK_EXCEPTION:{error}")  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"动态证据复核异常，未创建 ABT；审计见 {stopped_final}") from error  # 失败关闭并允许求解器继续运行。
    if mntr_changed:  # 认领写入期间若 MNTR 接受状态改变则不再按旧证据动作。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_MNTR_CHANGED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, "MNTR_CHANGED_AFTER_CLAIM_BEFORE_ABORT")  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"MNTR 在认领后变化，未创建 ABT；审计见 {stopped_final}")  # 失败关闭并允许求解器继续运行。
    try:  # 认领后的进程身份读取异常必须形成无 ABT final，而不是留下歧义认领。
        current_related = related_processes(context["jobname"], context["solver_dir"], context["identity"])  # ABT 前再次独立取得精确进程集合。
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as error:  # 捕获权限、字段或瞬态读取异常并失败关闭。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_PROCESS_IDENTITY_RECHECK_FAILED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, f"PROCESS_IDENTITY_RECHECK_EXCEPTION:{error}")  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"进程身份复核异常，未创建 ABT；审计见 {stopped_final}") from error  # 保留异常链并保持运行不受动作。
    if {record_identity_tuple(record) for record in current_related} != {record_identity_tuple(record) for record in context["current_related"]}:  # 任一进程消失、新增或身份变化都使认领时动作对象失效。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, False, "OPERATOR_STOP_NOT_REQUESTED_PROCESS_IDENTITY_CHANGED_AFTER_CLAIM", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, "PROCESS_IDENTITY_CHANGED_AFTER_CLAIM_BEFORE_ABORT")  # 留下明确无 ABT、无强杀终态。
        raise RuntimeError(f"进程身份在认领后变化，未创建 ABT；审计见 {stopped_final}")  # 失败关闭并保持运行不受动作。
    abort_created_by_this_tool = False  # 初始化本工具尚未取得 ABT 排他创建权，异常路径会从证据对象恢复真实值。
    try:  # ABT 合同、排他创建、完整写入、同步或回读任一步失败都必须形成明确 final，不能进入退出等待。
        create_valid_native_abort_exclusive(abort_path, context)  # 第三步调用同一受测帮助函数写入十字节有效载荷并完成全证据校验。
        abort_created_by_this_tool = True  # 只有帮助函数完整返回才允许把本次原生请求视为可进入自然退出等待。
    except (OSError, RuntimeError) as error:  # 捕获目标竞态、权限、短写、磁盘同步、回读或载荷合同异常。
        abort_created_by_this_tool = bool(context["native_abort_created_exclusively"])  # 从已即时记录的排他创建事实恢复准确动作状态，避免后续失败伪称未创建。
        stopped_final = write_stop_final(context, claim_path, explanation_path, abort_path, abort_created_by_this_tool, "OPERATOR_STOP_NATIVE_ABORT_CREATE_WRITE_SYNC_OR_READBACK_FAILED_NO_FORCE", pre_abort_recheck_started_at_utc, False, None, 0.0, 0, None, f"NATIVE_ABORT_EXCLUSIVE_CREATE_WRITE_SYNC_OR_READBACK_EXCEPTION:{error}")  # 披露失败发生于创建、写入、同步或回读中的具体阶段并明确无强杀。
        raise RuntimeError(f"原生 ABT 创建或有效载荷校验失败；审计见 {stopped_final}") from error  # 保留异常链并禁止退出等待冒充成功。
    wait_started = time.monotonic()  # 记录不受系统时钟校正影响的自然退出等待起点。
    previous_terminal_state: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None = None  # 初始化连续两个稳定样本比较基准。
    stable_empty_samples = 0  # 初始化进程为空、无 lock 且三文件不变的连续样本计数。
    poll_count = 0  # 初始化 ABT 后只读轮询次数。
    stable_state: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None = None  # 初始化尚未确认的最终文件状态。
    while time.monotonic() - wait_started < EXIT_CONFIRMATION_TIMEOUT_SECONDS:  # 在固定三十分钟内等待 MAPDL 自行响应 ABT。
        poll_count += 1  # 为本轮只读检查分配连续计数。
        try:  # ABT 后的只读进程或文件审计异常必须形成 final，绝不转为强制动作。
            remaining_related = related_processes(context["jobname"], context["solver_dir"], context["identity"])  # 获取当前仍存活的本 job 精确进程集合。
            current_state = file_triplet_state(context)  # 获取 OUT、ERR、MNTR 和 lock 当前快照。
        except (RuntimeError, OSError) as error:  # 捕获身份读取或文件状态异常并停止轮询。
            wait_seconds = time.monotonic() - wait_started  # 计算异常发生前已经等待的真实时长。
            return write_stop_final(context, claim_path, explanation_path, abort_path, True, "OPERATOR_SUFFICIENCY_STOP_REQUESTED_EXIT_AUDIT_EXCEPTION_NO_FORCE", pre_abort_recheck_started_at_utc, False, previous_terminal_state, wait_seconds, poll_count, None, f"POST_ABORT_READ_ONLY_AUDIT_EXCEPTION:{error}")  # 写明 ABT 已请求但绝无强杀的阻断终态。
        no_lock = current_state[3]["exists"] is False  # 只有 MAPDL 已移除 lock 才可能确认数据库关闭。
        terminal_files_exist = all(bool(snapshot["exists"]) for snapshot in current_state[:3])  # OUT、ERR 和 MNTR 三项权威原件必须全部保留。
        files_unchanged = previous_terminal_state is not None and current_state[:3] == previous_terminal_state[:3]  # 连续两轮三项原件大小和时刻相同才算稳定。
        if not remaining_related and no_lock and terminal_files_exist:  # 当前轮进程树空、无 lock 且三项原件存在时进入退出候选。
            stable_empty_samples = stable_empty_samples + 1 if files_unchanged else 1  # 文件与上轮相同则延续计数，否则把当前轮作为第一个空样本。
        else:  # 任一进程、lock 或文件变化表示退出尚未闭合。
            stable_empty_samples = 0  # 重置连续稳定样本计数。
        previous_terminal_state = current_state  # 保存本轮状态供下一轮比较。
        if stable_empty_samples >= 2:  # 两个连续轮次均进程树空、无 lock 且三项原件不变时确认自然退出。
            stable_state = current_state  # 冻结最终 OUT、ERR、MNTR 和无 lock 快照。
            break  # 结束自然退出等待并进入冻结监控终态闭环。
        time.sleep(POLL_INTERVAL_SECONDS)  # 等待五秒再只读检查，不调用任何进程动作接口。
    wait_seconds = time.monotonic() - wait_started  # 计算实际 ABT 后等待时长。
    if stable_state is None:  # 三十分钟内未同时取得进程空、无 lock 和文件稳定证据。
        return write_stop_final(context, claim_path, explanation_path, abort_path, True, "OPERATOR_SUFFICIENCY_STOP_REQUESTED_EXIT_NOT_CONFIRMED_TIMEOUT_NO_FORCE", pre_abort_recheck_started_at_utc, False, previous_terminal_state, wait_seconds, poll_count, None, "PROCESS_TREE_OR_FILES_NOT_STABLE_WITHIN_1800_SECONDS_NO_FORCE_ACTION_TAKEN")  # 写终态并明确绝不强杀。
    monitor_wait_started = time.monotonic()  # 记录等待冻结监控器提交完整稳定终态的单调起点。
    monitor_final_audit: dict[str, Any] | None = None  # 初始化尚未取得的可审计监控终态摘要。
    monitor_dirty_reason: str | None = None  # 初始化尚未判定的监控终态干净性原因。
    monitor_read_error: str | None = None  # 保存等待期最后一次半写、字段或文件读取异常。
    while time.monotonic() - monitor_wait_started < POST_EXIT_MONITOR_TIMEOUT_SECONDS:  # 最多等待两分钟跨过排他文件名先出现、正文后写完的真实窗口。
        if context["monitor_final_path"].is_file():  # 文件存在后仍必须等待大小/时刻稳定并完整解析。
            try:  # 每轮都重新尝试稳定读取和完整字段审计。
                monitor_final_audit, monitor_dirty_reason = validate_monitor_final(context)  # 同时取得证据摘要和是否不干净的显式原因。
                break  # 一旦取得完整稳定对象，无论干净与否都结束等待并如实封板。
            except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as error:  # 收敛半写 JSON、错型字段、哈希和文件竞态。
                monitor_read_error = str(error)  # 保留最后一次异常供超时终态解释。
        time.sleep(POLL_INTERVAL_SECONDS)  # 每五秒重试，期间绝不调用任何进程动作接口。
    if monitor_final_audit is None:  # 两分钟内未取得完整稳定且可审计的监控终态。
        missing_reason = "MONITOR_FINAL_MISSING_OR_INCOMPLETE_AFTER_120_SECONDS" if monitor_read_error is None else f"MONITOR_FINAL_STILL_UNREADABLE_AFTER_120_SECONDS:{monitor_read_error}"  # 区分从未出现和持续半写/错型。
        return write_stop_final(context, claim_path, explanation_path, abort_path, True, "OPERATOR_SUFFICIENCY_STOP_EXITED_BUT_MONITOR_FINAL_MISSING_OR_INCOMPLETE_NO_FORCE", pre_abort_recheck_started_at_utc, True, stable_state, wait_seconds, poll_count, None, missing_reason)  # 如实记录进程退出但监控闭环缺失或不完整。
    if monitor_dirty_reason is not None:  # 硬事件、监控器强制处置、lock、进程或哈希任一不干净时禁止成功状态。
        return write_stop_final(context, claim_path, explanation_path, abort_path, True, "OPERATOR_SUFFICIENCY_STOP_EXITED_MONITOR_FINAL_NOT_CLEAN_NO_FORCE", pre_abort_recheck_started_at_utc, True, stable_state, wait_seconds, poll_count, monitor_final_audit, monitor_dirty_reason)  # 保留监控终态 SHA、状态、硬事件及 controller process_disposition。
    return write_stop_final(context, claim_path, explanation_path, abort_path, True, "OPERATOR_SUFFICIENCY_STOP_NATIVE_ABORT_ACKNOWLEDGED_PROCESS_TREE_EXITED_STABLE", pre_abort_recheck_started_at_utc, True, stable_state, wait_seconds, poll_count, monitor_final_audit, None)  # 只有独立监控对象完整且无不干净原因时发布成功终态。


def find_forbidden_process_action_calls(source_text: str) -> list[dict[str, int | str]]:  # 接收完整 Python 源码并返回所有主动结束、强杀或发信号调用的名称与行号。
    syntax_tree = ast.parse(source_text, filename=str(SCRIPT_PATH))  # 只解析抽象语法树而不执行源码，安全检查真实调用节点而不是注释关键词。
    findings: list[dict[str, int | str]] = []  # 初始化按源码顺序收集的禁止进程动作调用列表。
    for node in ast.walk(syntax_tree):  # 遍历导入、函数、分支和表达式中的全部语法节点，关闭隐藏调用路径。
        if not isinstance(node, ast.Call):  # 非调用节点不可能直接触发进程处置。
            continue  # 跳过当前非调用节点并继续完整遍历。
        call_name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")  # 同时提取对象方法和直接函数名称，复杂动态调用按空名保留为无匹配。
        if call_name in FORBIDDEN_PROCESS_ACTION_CALL_NAMES:  # 只要调用名命中冻结禁表，无论是否位于当前分支都视为源代码不合规。
            findings.append({"call_name": call_name, "line_number": int(node.lineno)})  # 保存可定位的函数名和一基行号供修复。
    return sorted(findings, key=lambda finding: int(finding["line_number"]))  # 按源码行号稳定返回，便于离线测试与人工审查复现。


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


def run_offline_self_test() -> dict[str, Any]:  # 无业务输入并仅在操作系统临时目录执行载荷、排他创建、回读、充分性门和源码安全回归，返回机器结果。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n", "离线测试发现 ABT 字面值不是 nonlinear 加 LF")  # 独立确认唯一允许载荷字节序列。
    require(len(NATIVE_ABORT_PAYLOAD) == NATIVE_ABORT_PAYLOAD_LENGTH == 10, "离线测试发现 ABT 长度不是十字节")  # 同时核对真实长度、冻结常量和批准值十。
    require(NATIVE_ABORT_PAYLOAD.hex() == NATIVE_ABORT_PAYLOAD_HEX == "6e6f6e6c696e6561720a", "离线测试发现 ABT 十六进制不匹配")  # 逐字节确认 ASCII 内容和单一 LF。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256, "离线测试发现 ABT SHA-256 不匹配")  # 用运行时摘要独立核对冻结身份。
    first_evidence = native_abort_evidence_template()  # 初始化第一次临时排他创建的完整动作证据。
    duplicate_evidence = native_abort_evidence_template()  # 初始化第二次同路径创建的失败关闭证据。
    duplicate_rejected = False  # 初始化尚未证明同路径第二次排他创建被拒绝。
    with tempfile.TemporaryDirectory(prefix="ultra_c10_stop_offline_selftest_") as temporary_directory_text:  # 创建由运行库自动清理的独立临时目录，绝不解析或写入 ultra_runs。
        temporary_directory = Path(temporary_directory_text).resolve()  # 规范化临时目录供路径边界和回读断言使用。
        temporary_abort_path = temporary_directory / "offline_contract.abt"  # 在临时根内构造不会被 MAPDL 观察的虚拟 ABT 文件名。
        create_valid_native_abort_exclusive(temporary_abort_path, first_evidence)  # 调用生产同一帮助函数验证排他写入、flush、fsync 和回读路径。
        require(temporary_abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "离线临时 ABT 关闭句柄后字节漂移")  # 关闭写句柄后再次独立读取精确十字节载荷。
        try:  # 第二次使用同一路径验证排他创建不会覆盖既有有效证据。
            create_valid_native_abort_exclusive(temporary_abort_path, duplicate_evidence)  # 故意请求同路径第二次创建，预期在任何写入前触发 FileExistsError。
        except FileExistsError:  # 仅接受操作系统排他创建针对既有文件的标准拒绝异常。
            duplicate_rejected = True  # 记录并发或重复操作者被安全阻断的证明。
        require(duplicate_rejected, "离线测试发现第二次 ABT 排他创建未被拒绝")  # 若没有标准拒绝则说明存在覆盖风险。
        require(temporary_abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "第二次排他创建尝试改变了既有 ABT 字节")  # 证明拒绝路径没有截断或改写首个文件。
        require(bool(first_evidence["native_abort_created_exclusively"]), "离线测试缺少 ABT 排他创建成功证据")  # 核对生产帮助函数提交排他创建事实。
        require(bool(first_evidence["native_abort_payload_written_fully"]), "离线测试缺少 ABT 完整写入证据")  # 核对写调用真实返回十字节。
        require(bool(first_evidence["native_abort_flush_and_fsync_completed"]), "离线测试缺少 ABT flush/fsync 完成证据")  # 核对两层同步步骤均正常返回。
        require(bool(first_evidence["native_abort_readback_matches_contract"]), "离线测试缺少 ABT 回读一致证据")  # 核对同句柄回读四项合同全部匹配。
        require(not bool(duplicate_evidence["native_abort_created_exclusively"]), "重复创建失败路径错误认领了 ABT 创建权")  # 证明既有文件拒绝发生于取得创建权之前。
    synthetic_rows = [{"load_step": 1, "substep": 1, "attempt": 1, "iterations": 1, "total_iterations": 1, "increment": 1.0, "total_time_printed": 1.0, "elapsed_seconds": 0.0}, {"load_step": 2, "substep": 1, "attempt": 1, "iterations": 20, "total_iterations": 21, "increment": MINIMUM_INCREMENT, "total_time_printed": 1.0000005, "elapsed_seconds": 100.0}, {"load_step": 2, "substep": 2, "attempt": 1, "iterations": 20, "total_iterations": 41, "increment": MINIMUM_INCREMENT, "total_time_printed": 1.0000010, "elapsed_seconds": 500.0}]  # 构造门 A 最小合法 MNTR：两个连续 5E-7 步、后步二十次迭代且四百秒周期投影超过七天。
    synthetic_projection = evaluate_mntr_sufficiency(synthetic_rows)  # 复用生产充分性判定验证 ABT 修复没有破坏原停止授权门。
    require(synthetic_projection["sufficiency_branch"] == "A_TWO_ACCEPTED_MINIMUM_STEPS", "离线测试未进入预期门 A")  # 确认两个接受步走完整周期分支而非未决下界分支。
    require(float(synthetic_projection["projected_remaining_seconds"]) > SUFFICIENCY_HORIZON_SECONDS, "离线测试投影未严格超过七天")  # 确认合成输入满足唯一停机时间门。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 只读获取当前项目源代码供语法、进程动作和注释规则检查。
    ast.parse(source_text, filename=str(SCRIPT_PATH))  # 完整解析当前源文件，证明所有分支和结束结构语法有效且不生成缓存文件。
    forbidden_calls = find_forbidden_process_action_calls(source_text)  # 扫描实际调用节点，注释中的术语不会形成误报。
    comment_violations = find_comment_policy_violations(source_text)  # 扫描每一非空物理行的中文注释合同。
    require(not forbidden_calls, f"离线测试发现禁止进程动作调用：{forbidden_calls}")  # 任何 terminate、kill 或信号调用均使自检失败。
    require(not comment_violations, f"离线测试发现逐行中文注释违规：{comment_violations[:20]}")  # 报告前二十项并阻断不合规源码交付。
    return {"status": "PASS", "test_mode": "OFFLINE_TEMPORARY_DIRECTORY_ONLY", "current_run_writes_performed": False, "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "exclusive_create_succeeded": bool(first_evidence["native_abort_created_exclusively"]), "full_write_succeeded": bool(first_evidence["native_abort_payload_written_fully"]), "flush_and_fsync_succeeded": bool(first_evidence["native_abort_flush_and_fsync_completed"]), "readback_matched": bool(first_evidence["native_abort_readback_matches_contract"]), "duplicate_exclusive_create_rejected": duplicate_rejected, "duplicate_attempt_preserved_original_bytes": True, "sufficiency_gate_a_regression_passed": True, "forbidden_process_action_calls": forbidden_calls, "comment_policy_violations": comment_violations}  # 返回可由调用者直接存档的离线回归摘要，明确没有触碰当前运行。


def parse_arguments() -> argparse.Namespace:  # 无业务输入并返回用户显式指定的唯一运行目录或离线自检开关。
    parser = argparse.ArgumentParser(description="仅在门A两个已接受最小步，或门B一个已接受步加未决第二步二十九次迭代保守下界，且投影严格超过七天时，用原生 ABT 请求 C10 自适应诊断安全退出；绝不主动结束或强制结束进程。")  # 创建严格双门充分性停机命令行解析器。
    parser.add_argument("--run-dir", required=False, type=Path, help="正常模式下必填的唯一仍在运行 C10_LOAD_MIGRATION_DIAGNOSTIC 目录；禁止 latest 和通配符。")  # 为离线自检允许省略路径，正常动作仍由 main 显式强制必填。
    parser.add_argument("--self-test", action="store_true", help="仅在操作系统临时目录验证十字节 ABT、排他创建、fsync、回读、充分性门和无强杀源码。")  # 提供不读取、不写入、不停止任何实际运行的离线回归入口。
    return parser.parse_args()  # 返回已完成必填和 Path 类型转换的命名空间。


def main() -> None:  # 无输入和返回值；解析目标、执行充分性门和原生停机并输出机器摘要。
    arguments = parse_arguments()  # 读取正常运行目录或离线自检开关。
    if bool(arguments.self_test):  # 显式离线模式必须在任何运行目录解析、验证或写入之前短路。
        require(arguments.run_dir is None, "离线自检禁止同时提供 --run-dir")  # 阻断自检参数携带真实运行路径造成误解或未来回归误触。
        print(json.dumps(run_offline_self_test(), ensure_ascii=False, allow_nan=False))  # 输出单行机器结果且不创建项目内报告或 Python 缓存。
        return  # 离线测试完成后立即退出，保证 request_sufficiency_stop 不可达。
    require(arguments.run_dir is not None, "正常停机模式必须显式提供 --run-dir")  # 非自检模式保持唯一目标路径为强制门。
    final_path = request_sufficiency_stop(arguments.run_dir)  # 执行全链验证、先行认领、原生 ABT 和自然退出等待。
    final = read_json(final_path)  # 读取刚刚排他写出的终态供标准输出精简摘要。
    print(json.dumps({"run_dir": str(arguments.run_dir.resolve()), "status": final["status"], "operator_stop_final": str(final_path), "exact_process_tree_exit_confirmed": final["exact_process_tree_exit_confirmed"], "operator_tool_process_terminate_api_called": False, "operator_tool_process_kill_api_called": False, "modal_execution_allowed": False, "production_claim_allowed": False}, ensure_ascii=False, allow_nan=False))  # 返回可解析状态且明确仅本工具无强杀、无模态和无生产边界。


if __name__ == "__main__":  # 仅直接执行本文件时进入一次充分性停机流程，导入审查不访问运行或写文件。
    main()  # 执行严格运行充分性停机工具。
