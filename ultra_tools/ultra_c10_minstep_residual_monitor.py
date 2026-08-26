from __future__ import annotations  # 启用延迟类型注解，保持运行期依赖最小且便于静态审计。

import argparse  # 解析调用者显式给出的唯一已启动运行目录。
import hashlib  # 计算官方 ABT 十字节载荷和有限文本摘录的 SHA-256 摘要。
import json  # 输出专用监控器最终机器摘要，详细流水写入 JSONL。
import os  # 对官方原生中止文件执行 flush 后 fsync，确保请求真实落盘。
import time  # 使用单调时钟维持十秒采样、低资源持续窗口和退出稳定检查。
from datetime import datetime, timezone  # 解析启动时刻并生成带时区 UTC 采样时间。
from pathlib import Path  # 安全处理包含中文的运行、日志和原生中止文件路径。
from typing import Any  # 标注监控记录、启动链和嵌套 JSON 字段。

import psutil  # 读取实时物理内存、磁盘和已绑定 MAPDL 进程树资源。

import ultra_c10_adaptive_monitor as monitor_base  # 复用只读日志扫描、文件快照和防 PID 回收进程绑定函数，不调用其终止函数或主流程。


RUNS_ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs")  # 冻结唯一允许附着的全桥运行根目录。
RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_MINSTEP_NRRE_"  # 只批准最小 0.05% 迁移残差运行目录族。
DIAGNOSTIC_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_FIRST_0_05_PERCENT_NRRE_ENDPOINT"  # 冻结专用监控器唯一接受的诊断子类型。
DIAGNOSTIC_CHANGE_SET = "FULL_LS1_THEN_FIXED_SINGLE_0_05_PERCENT_LS2_WITH_NRRE_MAXFILE_50"  # 冻结完整 LS1 加单一最小增量的受控诊断变更集。
SAMPLE_INTERVAL_SECONDS = 10.0  # 每十秒采集一次资源、进程和新增日志，单位 s。
PROCESS_EXIT_EMPTY_SAMPLES = 2  # 连续两个样本找不到本 job 才确认进程树退出，避免包装器交接误判。
POST_EXIT_STABILITY_TIMEOUT_SECONDS = 60.0  # 自然退出后最多等待六十秒使 OUT/ERR/MNTR 稳定且 lock 消失。
IMMEDIATE_RAM_STOP_BYTES = 512 * 1024**2  # 可用物理内存低于五百一十二 MiB 时请求 MAPDL 原生中止。
SUSTAINED_RAM_STOP_BYTES = 1024**3  # 可用物理内存低于一 GiB 时进入持续计时，单位 byte。
SUSTAINED_RAM_STOP_SECONDS = 60.0  # 低于一 GiB 连续六十秒才触发原生中止，单位 s。
DISK_STOP_BYTES = 32 * 1024**3  # 运行盘空余低于三十二 GiB 时请求原生中止，单位 byte。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结单层 TYPE72 全桥已观测方程总数，单位 equation。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 按官方 ABT 合同固定第一列第一词与唯一 LF 的十字节载荷。
NATIVE_ABORT_PAYLOAD_SHA256 = hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest()  # 冻结官方原生中止载荷摘要供终态核验。


def require(condition: bool, message: str) -> None:  # 输入布尔门和失败说明；不满足时退出监控且不触碰求解进程。
    if not condition:  # 仅在身份、谱系、文件或运行合同不满足时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常，禁止误附着其他作业或执行任何处置。


def utc_now() -> str:  # 无输入并返回带时区的 ISO-8601 UTC 文本。
    return datetime.now(timezone.utc).isoformat()  # 使用真实 UTC 当前时刻供样本和动作排序。


def request_native_abort(solver_dir: Path, jobname: str) -> tuple[Path, str, str]:  # 输入工作目录和作业名并返回经过排他写入、刷盘与回读的 ABT 证据。
    abort_path = solver_dir / f"{jobname}.abt"  # 按 MAPDL 批处理约定构造当前 job 唯一原生中止路径。
    if abort_path.exists():  # 既有文件可能来自并发安全控制动作，禁止覆盖其时间证据。
        existing_payload = abort_path.read_bytes()  # 二进制读取既有载荷，避免文本换行转换。
        require(existing_payload == NATIVE_ABORT_PAYLOAD, "既有 ABT 不是官方 nonlinear 十字节载荷")  # 只允许完全相同的幂等请求继续监控。
        return abort_path, "VALID_NATIVE_ABORT_ALREADY_EXISTED", hashlib.sha256(existing_payload).hexdigest()  # 返回既有路径、动作和真实摘要。
    with abort_path.open("xb") as handle:  # 使用二进制排他创建关闭双监控器覆盖窗口。
        written = handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入精确十字节官方载荷。
        require(written == len(NATIVE_ABORT_PAYLOAD), "ABT 原生中止载荷发生短写")  # 阻断不完整请求被误记为成功。
        handle.flush()  # 把 Python 缓冲区提交给操作系统。
        os.fsync(handle.fileno())  # 强制持久化中止请求后才允许记录动作完成。
    readback = abort_path.read_bytes()  # 独立回读真实磁盘字节供关闭写后身份窗口。
    require(readback == NATIVE_ABORT_PAYLOAD, "ABT 原生中止载荷回读不一致")  # 要求第一列第一词和换行逐字节正确。
    return abort_path, "VALID_NATIVE_ABORT_CREATED_AND_FSYNCED", hashlib.sha256(readback).hexdigest()  # 返回新建路径、动作和回读摘要。


def main() -> None:  # 解析唯一运行、验证启动链、持续采样并只用官方 ABT 请求硬停，无业务返回值。
    parser = argparse.ArgumentParser(description="监控 C10 固定 0.05% 最小增量 NRRE 残差诊断")  # 建立不接受 jobname 或路径猜测的命令行接口。
    parser.add_argument("--run-dir", required=True, type=Path, help="已由专用 minstep 启动器启动的唯一运行绝对目录")  # 要求调用者显式给出运行根。
    arguments = parser.parse_args()  # 解析参数并由 argparse 拒绝缺失或未知选项。
    run_dir = arguments.run_dir.resolve()  # 规范化运行绝对路径以关闭相对段歧义。
    require(run_dir.is_dir() and run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs：{run_dir}")  # 只允许项目运行根直接子目录。
    require(run_dir.name.startswith(RUN_PREFIX), f"运行目录不是最小增量 NRRE 族：{run_dir.name}")  # 阻断普通静力、模态或自适应全路径运行。
    manifest_path = run_dir / "manifest.json"  # 定位准备清单原件。
    status_path = run_dir / "C10_static_status.json"  # 定位根级准备状态原件。
    claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后真实 PID 记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位增强进程身份记录。
    manifest = monitor_base.read_json(manifest_path)  # 读取准备输入和专用运行代码身份。
    root_status = monitor_base.read_json(status_path)  # 读取诊断权限和未作废状态。
    claim = monitor_base.read_json(claim_path)  # 读取唯一启动权和准备账本摘要。
    launch = monitor_base.read_json(launch_path)  # 读取真实 PID、参数和运行时硬门。
    main_identity = monitor_base.read_json(identity_path)  # 读取防 PID 回收的主进程身份。
    require(manifest.get("run_name") == root_status.get("run_name") == claim.get("run_name") == launch.get("run_name") == main_identity.get("run_name") == run_dir.name, "五段启动链运行名不一致")  # 关闭跨目录复制错配。
    require(manifest.get("jobname") == root_status.get("jobname") == claim.get("jobname") == launch.get("jobname") == main_identity.get("jobname"), "五段启动链 jobname 不一致")  # 固定唯一进程和文件族。
    require(manifest.get("diagnostic_subtype") == claim.get("diagnostic_subtype") == launch.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE, "启动链不是最小 0.05% NRRE 子类型")  # 阻断其他分析借用本监控结论。
    require(manifest.get("diagnostic_change_set") == claim.get("diagnostic_change_set") == launch.get("diagnostic_change_set") == DIAGNOSTIC_CHANGE_SET, "启动链受控诊断变更集不一致")  # 固定本次只有完整 LS1 与一个最小 LS2 增量。
    require(root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("launch_allowed_for_diagnostic") is True, "根状态不是仍有效的诊断准备态")  # 执行器保持原准备状态，事后作废则拒绝附着。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and manifest.get("static_result_expected") is False, "清单未关闭模态、生产或完整静力结论")  # 保持结果只供定位。
    monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 读取清单冻结的专用监控器相对路径。
    execute_relative = str(manifest.get("runtime_execute_script", "")).replace("\\", "/")  # 读取清单冻结的专用启动器相对路径。
    require(monitor_relative == "input_snapshot/ultra_c10_minstep_residual_monitor.py" and execute_relative == "input_snapshot/ultra_c10_minstep_residual_execute.py", "专用运行代码快照路径错误")  # 固定两段入口文件名。
    require(Path(__file__).resolve() == (run_dir / monitor_relative).resolve(), "实际调用的监控器不是本运行冻结快照")  # 禁止工具源直接附着已启动作业。
    require(monitor_base.sha256_file(Path(__file__).resolve()) == str(manifest.get("runtime_monitor_script_sha256")), "专用监控器 SHA-256 与清单不一致")  # 关闭准备后监控代码变化。
    require(monitor_base.sha256_file(run_dir / execute_relative) == str(manifest.get("runtime_execute_script_sha256")), "专用启动器 SHA-256 与清单不一致")  # 证明启动代码仍与准备包相同。
    require(claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED" and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING" and main_identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED", "认领、PID 或进程身份状态错误")  # 固定启动链先后顺序。
    require(claim.get("launch_argv") == manifest.get("launch_argv") == launch.get("launch_argv") == main_identity.get("command_line"), "清单、认领、PID 和系统命令行不一致")  # 要求真实参数数组逐项相同。
    require(launch.get("launch_claim_sha256") == monitor_base.sha256_file(claim_path), "PID 记录引用的启动认领摘要漂移")  # 证明当前进程属于当前唯一认领。
    require(claim.get("manifest_sha256") == launch.get("manifest_sha256") == monitor_base.sha256_file(manifest_path), "启动链清单摘要不一致")  # 关闭准备与 Popen 之间的修改窗口。
    require(claim.get("prepared_ledger_sha256") == launch.get("prepared_ledger_sha256") == monitor_base.sha256_file(run_dir / "artifact_hashes.sha256"), "启动链准备账本摘要不一致")  # 固定全部输入与运行代码身份。
    require(claim.get("prepared_ledger_entry_count") == launch.get("prepared_ledger_entry_count") and int(claim.get("prepared_ledger_entry_count", 0)) >= 30, "启动链准备账本条目数不一致或不足")  # 要求完整谱系覆盖。
    require(launch.get("native_abort_only") is True and launch.get("force_termination_allowed") is False, "启动记录未关闭强制进程处置")  # 专用监控只能使用官方 ABT 请求。
    require(launch.get("monitor_hard_stops") == {"available_ram_below_bytes": IMMEDIATE_RAM_STOP_BYTES, "available_ram_below_1_gib_sustained_seconds": int(SUSTAINED_RAM_STOP_SECONDS), "disk_free_below_bytes": DISK_STOP_BYTES}, "启动记录硬停阈值与监控器冻结值不一致")  # 防止阈值在启动后改变。
    main_pid = int(launch.get("main_pid", 0))  # 读取执行器 Popen 返回的包装器 PID。
    require(main_pid > 0 and int(main_identity.get("pid", 0)) == main_pid, "主 PID 缺失或增强身份不一致")  # 阻断伪造或回收 PID。
    require(main_identity.get("runtime_launch_sha256") == monitor_base.sha256_file(launch_path), "增强身份引用的 PID 记录摘要漂移")  # 闭合增强身份与最小启动记录。
    jobname = str(manifest.get("jobname", ""))  # 取得已经五方核对的作业名供文件与进程绑定。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 恢复完整冻结启动参数数组。
    solver_dir = Path(monitor_base.argument_value(launch_argv, "-dir")).resolve()  # 从真实参数定位唯一工作目录。
    require(solver_dir == (run_dir / "solver").resolve() and solver_dir.is_dir(), "solver 目录越出本运行或缺失")  # 限制日志、ABT 和结果文件作用域。
    input_path = Path(monitor_base.argument_value(launch_argv, "-i")).resolve()  # 从参数定位已哈希主控。
    output_path = Path(monitor_base.argument_value(launch_argv, "-o")).resolve()  # 从参数定位权威 OUT。
    require(input_path == (run_dir / str(manifest.get("main_input"))).resolve() and input_path.is_file(), "启动主输入与清单不一致")  # 阻断正确 job 执行另一 deck。
    require(output_path.parent == solver_dir and output_path.name.casefold() == f"{jobname}.out".casefold(), "OUT 路径与 jobname 不一致")  # 固定日志文件族。
    require(str(Path(str(main_identity.get("executable", ""))).resolve()).casefold() == str(Path(launch_argv[0]).resolve()).casefold(), "增强身份二进制与批准 MAPDL 不一致")  # 关闭 PID 回收和程序替换。
    launch_started_epoch = datetime.fromisoformat(str(launch.get("started_at_utc"))).timestamp()  # 把 UTC 启动时间转换为 Unix 秒。
    require(float(main_identity.get("create_time_epoch_seconds", 0.0)) >= launch_started_epoch - 10.0, "进程创建时刻早于启动记录超过十秒")  # 容许 Windows 时间戳分辨率但拒绝明显旧进程。
    error_path = solver_dir / f"{jobname}.err"  # 定位 MAPDL 原生 ERR，启动早期允许暂不存在。
    native_monitor_path = solver_dir / f"{jobname}.mntr"  # 定位 MAPDL 原生 MNTR 供活性和退出稳定审计。
    lock_path = solver_dir / f"{jobname}.lock"  # 定位 MAPDL job 锁，正常退出应自行删除。
    monitor_claim_path = run_dir / "qa" / "runtime_minstep_monitor_claim.json"  # 定位专用监控排他认领文件。
    samples_path = run_dir / "qa" / "runtime_minstep_monitor_samples.jsonl"  # 定位逐样本立即刷盘的监控流水。
    final_path = run_dir / "qa" / "runtime_minstep_monitor_final.json"  # 定位进程树退出后的唯一监控终态。
    require(not monitor_claim_path.exists() and not samples_path.exists() and not final_path.exists(), "运行已存在专用监控认领、流水或终态")  # 关闭双监控器并发请求 ABT 的路径。
    bound_identities: dict[int, float] = {}  # 初始化跨样本 PID 到创建时刻绑定表。
    initial_related, initial_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 在认领前取得可信本 job 进程树和无关求解进程。
    require(bool(initial_related), "监控附着时找不到与启动身份或精确 -j/-dir 匹配的 MAPDL 进程")  # 防止附着已结束或错误作业。
    monitor_claim = {"schema_version": 1, "status": "MINSTEP_MONITOR_CLAIMED", "run_name": run_dir.name, "jobname": jobname, "claimed_at_utc": utc_now(), "monitor_script": str(Path(__file__).resolve()), "monitor_script_sha256": monitor_base.sha256_file(Path(__file__).resolve()), "runtime_launch_sha256": monitor_base.sha256_file(launch_path), "runtime_launch_claim_sha256": monitor_base.sha256_file(claim_path), "runtime_process_identity_sha256": monitor_base.sha256_file(identity_path), "manifest_sha256": monitor_base.sha256_file(manifest_path), "prepared_ledger_sha256": monitor_base.sha256_file(run_dir / "artifact_hashes.sha256"), "main_process_identity": main_identity, "initial_related_processes": initial_related, "initial_unrelated_solver_processes": initial_unrelated, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_only": True, "force_termination_allowed": False}  # 冻结监控器、启动链、初始进程和只允许官方 ABT 的行为合同。
    monitor_base.write_json_exclusive(monitor_claim_path, monitor_claim)  # 在任何采样或动作前排他提交监控权。
    started_monotonic = time.monotonic()  # 记录不受系统时钟校正影响的持续时间起点。
    started_at_utc = utc_now()  # 记录人读 UTC 监控起点。
    low_ram_since: float | None = None  # 初始化低于一 GiB 的连续区间起点。
    output_offset = 0  # 初始化 OUT 增量读取字节偏移。
    output_carry = ""  # 初始化 OUT 跨块消息边界尾文。
    error_offset = 0  # 初始化 ERR 增量读取字节偏移。
    error_carry = ""  # 初始化 ERR 跨块消息边界尾文。
    seen_event_keys: set[str] = set()  # 初始化硬事件去重集合。
    hard_events: list[dict[str, Any]] = []  # 初始化全程明确 FATAL、坏主元、方程漂移、CNVTOL 或资源硬事件清单。
    observed_equation_counts: list[int] = []  # 初始化全部组装阶段方程数记录。
    minimum_available_ram: int | None = None  # 初始化最小可用物理内存极值。
    minimum_disk_free: int | None = None  # 初始化最小磁盘空余极值。
    maximum_related_rss = 0  # 初始化本 job 进程树最大 RSS，单位 byte。
    sample_count = 0  # 初始化从一开始的样本序号。
    empty_process_samples = 0  # 初始化连续空进程树样本数。
    previous_terminal_state: tuple[int, int, int] | None = None  # 初始化 OUT/ERR/MNTR 三文件上轮大小。
    post_exit_since: float | None = None  # 初始化首次发现进程树为空的单调时刻。
    monitor_block_reason: str | None = None  # 初始化无退出证据阻断原因。
    abort_requested = False  # 初始化尚未请求官方原生中止。
    abort_record: dict[str, Any] = {"requested": False, "native_abort_only": True, "force_termination_allowed": False, "terminate_called": False, "kill_called": False}  # 预置正常完成时也明确无强制处置的动作记录。
    final_related: list[dict[str, Any]] = []  # 初始化循环结束时本 job 进程快照。
    final_unrelated: list[dict[str, Any]] = []  # 初始化循环结束时无关求解进程快照。
    with samples_path.open("x", encoding="utf-8", newline="\n") as samples_handle:  # 排他创建 JSONL 流水并保持句柄供逐样本刷盘。
        while True:  # 持续采样直至自然/ABT 后进程稳定退出或退出证据阻断。
            sample_started = time.monotonic()  # 记录当前采样起点供节拍和持续资源计算。
            elapsed_seconds = sample_started - started_monotonic  # 计算总监控时长，单位 s。
            memory = psutil.virtual_memory()  # 读取当前物理内存快照。
            disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 读取运行卷磁盘快照。
            available_ram = int(memory.available)  # 提取可用物理内存，单位 byte。
            disk_free = int(disk.free)  # 提取磁盘空余，单位 byte。
            minimum_available_ram = available_ram if minimum_available_ram is None else min(minimum_available_ram, available_ram)  # 更新全程最小可用内存。
            minimum_disk_free = disk_free if minimum_disk_free is None else min(minimum_disk_free, disk_free)  # 更新全程最小磁盘空余。
            low_ram_since = sample_started if available_ram < SUSTAINED_RAM_STOP_BYTES and low_ram_since is None else low_ram_since  # 首次低于一 GiB 时开始持续计时。
            low_ram_since = None if available_ram >= SUSTAINED_RAM_STOP_BYTES else low_ram_since  # 内存恢复时清除连续低内存区间。
            low_ram_duration = 0.0 if low_ram_since is None else sample_started - low_ram_since  # 计算当前连续低内存秒数。
            related_processes, unrelated_processes, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 获取防 PID 回收的本 job 和无关进程快照。
            related_rss = sum(int(record.get("rss_bytes", 0)) for record in related_processes)  # 累计当前本 job 进程树 RSS，单位 byte。
            maximum_related_rss = max(maximum_related_rss, related_rss)  # 更新全程最大本 job RSS。
            output_offset, output_carry, output_text, output_size = monitor_base.read_log_increment(output_path, output_offset, output_carry)  # 增量读取 OUT 并保留跨块尾文。
            error_offset, error_carry, error_text, error_size = monitor_base.read_log_increment(error_path, error_offset, error_carry)  # 增量读取 ERR 并保留跨块尾文。
            output_events, output_equations = monitor_base.scan_new_text("OUT", output_text, seen_event_keys)  # 扫描 OUT 明确硬事件和方程数。
            error_events, error_equations = monitor_base.scan_new_text("ERR", error_text, seen_event_keys)  # 扫描 ERR 明确硬事件和方程数。
            new_events = output_events + error_events  # 合并两类原生文本硬事件且保持检出顺序。
            observed_equation_counts.extend(output_equations + error_equations)  # 累计全部新增方程数供终态审计。
            if available_ram < IMMEDIATE_RAM_STOP_BYTES:  # 可用物理内存低于五百一十二 MiB 时触发即时资源硬门。
                event_key = "RESOURCE_RAM_BELOW_512_MIB"  # 定义稳定硬事件类别用于去重。
                if event_key not in seen_event_keys:  # 仅首次越过即时门时登记动作。
                    seen_event_keys.add(event_key)  # 立即登记防止下一样本重复请求。
                    new_events.append({"kind": event_key, "observed_bytes": available_ram, "threshold_bytes": IMMEDIATE_RAM_STOP_BYTES, "detected_at_utc": utc_now()})  # 保存实测值、阈值和时刻。
            if low_ram_duration >= SUSTAINED_RAM_STOP_SECONDS:  # 连续低于一 GiB 达六十秒时触发持续资源硬门。
                event_key = "RESOURCE_RAM_BELOW_1_GIB_FOR_60_SECONDS"  # 定义稳定持续内存事件类别。
                if event_key not in seen_event_keys:  # 只在首次达到持续门时登记。
                    seen_event_keys.add(event_key)  # 立即登记去重键。
                    new_events.append({"kind": event_key, "observed_bytes": available_ram, "threshold_bytes": SUSTAINED_RAM_STOP_BYTES, "continuous_seconds": low_ram_duration, "detected_at_utc": utc_now()})  # 保存内存、阈值和持续时长。
            if disk_free < DISK_STOP_BYTES:  # 磁盘空余低于三十二 GiB 时触发写盘安全硬门。
                event_key = "RESOURCE_DISK_BELOW_32_GIB"  # 定义稳定磁盘事件类别。
                if event_key not in seen_event_keys:  # 仅首次越过磁盘门时登记。
                    seen_event_keys.add(event_key)  # 立即登记去重键。
                    new_events.append({"kind": event_key, "observed_bytes": disk_free, "threshold_bytes": DISK_STOP_BYTES, "detected_at_utc": utc_now()})  # 保存实测磁盘、阈值和时刻。
            hard_events.extend(new_events)  # 在写样本和请求 ABT 前累计本轮全部新硬事件。
            sample_count += 1  # 为当前样本分配从一开始的稳定序号。
            sample = {"schema_version": 1, "sample_index": sample_count, "sampled_at_utc": utc_now(), "elapsed_seconds": elapsed_seconds, "physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": available_ram, "low_ram_continuous_seconds": low_ram_duration, "disk_total_bytes": int(disk.total), "disk_free_bytes": disk_free, "related_processes": related_processes, "unrelated_solver_processes": unrelated_processes, "related_rss_bytes": related_rss, "out_offset_bytes": output_offset, "out_size_bytes": output_size, "err_offset_bytes": error_offset, "err_size_bytes": error_size, "mntr_file": monitor_base.file_snapshot(native_monitor_path), "lock_file": monitor_base.file_snapshot(lock_path), "new_equation_counts": output_equations + error_equations, "new_hard_events": new_events, "ordinary_ncnv_and_high_residual_are_not_hard_stops": True, "native_abort_only": True}  # 保存资源、精确进程、日志、方程和硬事件完整样本。
            monitor_base.append_json_line(samples_handle, sample)  # 立即写入、刷新和 fsync 当前 JSONL 样本。
            if new_events and not abort_requested:  # 首次检测到冻结硬事件时只进入一次官方原生中止路径。
                abort_requested = True  # 在文件动作前锁定已请求状态，防止重复进入。
                if related_processes:  # 只有当前 job 仍有可信进程时才创建 ABT。
                    abort_path, abort_action, abort_sha256 = request_native_abort(solver_dir, jobname)  # 排他写入并回读官方 nonlinear 十字节载荷。
                    abort_record = {"requested": True, "requested_at_utc": utc_now(), "reason_kinds": sorted({str(event.get("kind")) for event in hard_events}), "abort_file": str(abort_path), "abort_file_action": abort_action, "abort_payload_length_bytes": len(NATIVE_ABORT_PAYLOAD), "abort_payload_sha256": abort_sha256, "native_abort_only": True, "force_termination_allowed": False, "terminate_called": False, "kill_called": False, "wait_for_natural_process_exit": True}  # 冻结动作、原因、精确载荷和绝不强制处置边界。
                else:  # 硬事件与进程自然退出同时发生时无需创建可能永不被消费的 ABT。
                    abort_record = {"requested": False, "requested_at_utc": utc_now(), "reason_kinds": sorted({str(event.get("kind")) for event in hard_events}), "abort_file": str(solver_dir / f"{jobname}.abt"), "abort_file_action": "PROCESS_ALREADY_GONE_NO_ABORT_CREATED", "abort_payload_length_bytes": len(NATIVE_ABORT_PAYLOAD), "abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_only": True, "force_termination_allowed": False, "terminate_called": False, "kill_called": False, "wait_for_natural_process_exit": True}  # 明确进程已消失且没有执行文件动作。
            if related_processes:  # 本 job 仍运行时继续自然等待，不因高残差、NCNV 或 ABT 宽限期强制结束。
                empty_process_samples = 0  # 清除包装器交接或短暂不可见造成的空样本计数。
                post_exit_since = None  # 清除先前空窗的退出稳定计时。
                previous_terminal_state = None  # 清除先前空窗的文件大小基线。
            else:  # 本轮找不到任何可信本 job 进程。
                post_exit_since = sample_started if post_exit_since is None else post_exit_since  # 首次空树时启动最长六十秒退出证据计时。
                current_terminal_state = (int(monitor_base.file_snapshot(output_path)["size_bytes"]), int(monitor_base.file_snapshot(error_path)["size_bytes"]), int(monitor_base.file_snapshot(native_monitor_path)["size_bytes"]))  # 构造 OUT/ERR/MNTR 当前大小元组。
                terminal_files_stable = previous_terminal_state == current_terminal_state  # 只有连续两个样本大小相同才认为写入稳定。
                normal_exit_evidence = terminal_files_stable and not bool(monitor_base.file_snapshot(lock_path)["exists"])  # 自然或 ABT 后退出均要求 lock 消失。
                empty_process_samples = empty_process_samples + 1 if normal_exit_evidence else 0  # 只对同时满足文件稳定和无锁的空树样本计数。
                previous_terminal_state = current_terminal_state  # 保存当前大小供下一空样本比较。
                if sample_started - post_exit_since >= POST_EXIT_STABILITY_TIMEOUT_SECONDS and not normal_exit_evidence:  # 进程退出六十秒仍有锁或文件变化时 fail-closed。
                    monitor_block_reason = "PROCESS_TREE_EXITED_BUT_LOCK_REMAINED_OR_OUTPUTS_NOT_STABLE_FOR_60_SECONDS"  # 冻结监控完整性阻断原因。
                    final_related, final_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 提交前取得最后进程快照。
                    break  # 结束采样并写阻断终态，不执行任何强制处置。
            if empty_process_samples >= PROCESS_EXIT_EMPTY_SAMPLES:  # 连续两个稳定空树样本确认作业自然或响应 ABT 后退出。
                final_related, final_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, main_identity, bound_identities)  # 再次取得防 PID 回收最终快照。
                if not final_related:  # 最终快照仍为空时提交终态。
                    break  # 跳出采样循环进入最终工件写入。
                empty_process_samples = 0  # 若最终快照重新发现本 job，则恢复运行态继续采样。
            sleep_seconds = max(0.0, SAMPLE_INTERVAL_SECONDS - (time.monotonic() - sample_started))  # 扣除本轮工作时间维持十秒节拍。
            time.sleep(sleep_seconds)  # 等待下一样本；单次等待不超过十秒。
    if monitor_block_reason is not None:  # 退出证据未闭合时选择阻断终态。
        final_status = "PROCESS_TREE_EXITED_MINSTEP_MONITOR_BLOCKED"  # 不把未知锁或仍变化输出冒充自然完成。
    elif hard_events:  # 存在冻结硬事件且进程最终自行退出时选择原生中止终态。
        final_status = "HARD_STOP_NATIVE_ABORT_ONLY_PROCESS_TREE_EXITED_STABLE"  # 明确只请求 ABT 且未强制结束进程。
    else:  # 无硬事件且进程、文件和锁均稳定退出时选择自然完成终态。
        final_status = "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP"  # 只描述执行终止，不宣称残差或工程通过。
    final_record = {"schema_version": 1, "status": final_status, "run_name": run_dir.name, "jobname": jobname, "monitor_started_at_utc": started_at_utc, "monitor_finished_at_utc": utc_now(), "duration_seconds": time.monotonic() - started_monotonic, "sample_count": sample_count, "monitor_claim_path": str(monitor_claim_path), "monitor_claim_sha256": monitor_base.sha256_file(monitor_claim_path), "monitor_block_reason": monitor_block_reason, "hard_stop_contract": {"immediate_ram_below_bytes": IMMEDIATE_RAM_STOP_BYTES, "sustained_ram_below_bytes": SUSTAINED_RAM_STOP_BYTES, "sustained_ram_seconds": SUSTAINED_RAM_STOP_SECONDS, "disk_below_bytes": DISK_STOP_BYTES, "expected_equation_count": EXPECTED_EQUATION_COUNT, "fatal_bad_pivot_equation_drift_cnvtol_or_resource_only": True, "high_residual_not_hard_stop": True, "ordinary_ncnv_not_hard_stop": True, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_only": True, "force_termination_allowed": False}, "minimum_physical_memory_available_bytes": minimum_available_ram, "minimum_disk_free_bytes": minimum_disk_free, "maximum_related_rss_bytes": maximum_related_rss, "observed_equation_counts": observed_equation_counts, "unique_equation_counts": sorted(set(observed_equation_counts)), "hard_events": hard_events, "controller_abort": abort_record, "terminate_called": False, "kill_called": False, "final_related_processes": final_related, "final_unrelated_solver_processes": final_unrelated, "final_out_file": monitor_base.file_snapshot(output_path), "final_err_file": monitor_base.file_snapshot(error_path), "final_mntr_file": monitor_base.file_snapshot(native_monitor_path), "final_lock_file": monitor_base.file_snapshot(lock_path), "samples_path": str(samples_path), "samples_sha256": monitor_base.sha256_file(samples_path), "out_path": str(output_path), "err_path": str(error_path), "result_use": "RESIDUAL_LOCALIZATION_ONLY_NOT_STATIC_MODAL_OR_PRODUCTION"}  # 汇总监控身份、资源极值、方程数、硬事件、原生动作和严格用途边界。
    monitor_base.write_json_exclusive(final_path, final_record)  # 以排他创建提交唯一监控终态。
    print(json.dumps({"run_dir": str(run_dir), "status": final_status, "sample_count": sample_count, "hard_event_count": len(hard_events), "native_abort_requested": bool(abort_record.get("requested")), "terminate_called": False, "kill_called": False}, ensure_ascii=False))  # 返回精简机器摘要供终结器接管。


if __name__ == "__main__":  # 仅直接执行本冻结快照时进入持续监控，导入审查不访问进程。
    main()  # 执行启动链核验、十秒采样、官方 ABT 请求和自然退出确认。
