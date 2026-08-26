from __future__ import annotations  # 启用延迟类型注解，保持监控器在不同 Python 小版本中的兼容性。

import argparse  # 解析离线自检或唯一 A0 运行目录，禁止自动选择 latest。
import ast  # 离线审查本监控器源码不存在 terminate、kill、信号或子进程调用。
import json  # 读取启动链并排他写出监控认领、逐样本流水和最终状态。
import os  # 读取本监控器与父启动器 PID，并在终态精确移除已经双重摘要核验的唯一主机租约。
import re  # 审查逐行中文说明并辅助源码安全自检。
import sys  # 核验启动器自动创建监控器时采用的 Python 解释器与当前真实解释器完全一致。
import time  # 使用单调时钟计算采样节奏、低内存持续时间和退出稳定窗口。
from datetime import datetime  # 把带时区启动记录转换为 Unix 秒以检查 PID 创建时刻合理性。
from pathlib import Path  # 安全处理包含中文的运行、日志、锁和原生 ABT 绝对路径。
from typing import Any  # 标注异构 JSON 记录和运行时事件列表的值类型。

import psutil  # 只读采集物理内存、磁盘和精确进程树，不调用任何主动进程处置接口。

import ultra_c10_adaptive_monitor as monitor_base  # 复用已回归的进程身份、增量日志、硬事件和官方十字节 ABT 帮助函数，不调用其主流程。
import ultra_c10_static_execute as ledger_base  # 复用准备账本逐项摘要复算函数，不调用其启动主流程。


RUNS_ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs")  # 冻结唯一批准运行根，阻断监控任意目录或向外写 ABT。
RUN_PREFIX = "C10_A0_DIRECT_SPATIAL_RAMP_"  # 只批准当前 TYPE72 直接空间重力 A0 运行族。
DIAGNOSTIC_SUBTYPE = "A0_CURRENT_TYPE72_S10_DIRECT_SPATIAL_GRAVITY_RAMP_STATIC_ONLY_NRRE"  # 冻结监控器允许附着的唯一诊断身份。
SCRIPT_RELATIVE = "input_snapshot/ultra_c10_a0_monitor.py"  # 冻结本监控器在运行内的唯一相对路径。
HELPER_RELATIVE = "input_snapshot/ultra_c10_adaptive_monitor.py"  # 冻结进程、日志和 ABT 帮助代码在运行内的唯一相对路径。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结当前单层 TYPE72 全桥方程数，任何组装漂移都是硬事件。
SAMPLE_INTERVAL_SECONDS = 10.0  # 每十秒采集一次进程、资源与增量日志，兼顾及时性和大 OUT 的读取开销。
PROCESS_EXIT_EMPTY_SAMPLES = 2  # 连续两个稳定空进程样本才确认退出，避免包装器交接瞬间误判。
POST_EXIT_TIMEOUT_SECONDS = 60.0  # 进程树退出后最多等待六十秒让 OUT/ERR/MNTR 稳定且 lock 消失。
IMMEDIATE_RAM_STOP_BYTES = 512 * 1024**2  # 可用物理内存低于五百一十二 MiB 时提交官方 ABT。
SUSTAINED_RAM_STOP_BYTES = 1024**3  # 可用物理内存低于一 GiB 时开始持续计时。
SUSTAINED_RAM_STOP_SECONDS = 60.0  # 低于一 GiB 连续六十秒才提交官方 ABT，避免单点抖动误停。
HISTORICAL_LARGEST_C10_PACKAGE_GIB = 5.630  # 冻结既有 C10 失败与 NRRE 包的实测最大占用为 5.630 GiB，来源为项目运行目录体积复核。
DISK_GATE_MULTIPLIER = 4.26  # 冻结二十四 GiB 相对 5.630 GiB 历史最大包约四点二六倍的安全倍率，单位为无量纲。
DISK_STOP_BYTES = 24 * 1024**3  # 运行盘空余低于二十四 GiB 时提交官方 ABT；在复核时 38.653 GiB 空余下仍有约 14.653 GiB 额外余量，单位 byte。
HOST_LEASE_PATH = RUNS_ROOT / ".c10_a0_exclusive_host_lease.json"  # 冻结跨 A0 运行共享的唯一主机排他租约路径。
MONITOR_SPAWN_CLAIM_RELATIVE = "runtime_monitor_spawn_claim.json"  # 冻结启动器自动创建监控器前必须提交的认领文件名。
HOST_LEASE_RELEASE_RELATIVE = "qa/runtime_a0_host_lease_monitor_release.json"  # 冻结监控终态封存并释放主机租约的唯一运行内证据路径。


def require(condition: bool, message: str) -> None:  # 接收布尔门和失败说明；失败时阻断附着或监控且无业务返回值。
    if not condition:  # 仅在身份、谱系、资源合同或源码安全门失败时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常且不扩大任何进程动作范围。


def utc_now() -> str:  # 无输入并返回带时区的 ISO-8601 UTC 文本。
    return monitor_base.utc_now()  # 复用冻结帮助函数以保持启动、监控和 ABT 证据时间格式一致。


def unrelated_solver_events(records: list[dict[str, Any]], seen_event_keys: set[str]) -> list[dict[str, Any]]:  # 输入当前非本 job MAPDL/MPI 记录和去重集合并返回每个新进程身份对应的硬事件。
    events: list[dict[str, Any]] = []  # 初始化本样本首次出现的非本 job 求解进程硬事件列表。
    for record in records:  # 逐一处理进程扫描已经判定为无关的 MAPDL 或 MPI 身份。
        pid = int(record.get("pid", 0))  # 读取进程 PID 作为身份键第一部分。
        create_time = float(record.get("create_time_epoch_seconds", 0.0))  # 读取创建时刻作为阻断 PID 回收误去重的第二部分。
        event_key = f"UNRELATED_SOLVER_PROCESS_AFTER_A0_LAUNCH:{pid}:{create_time:.6f}"  # 构造同一进程身份跨样本稳定、PID 再用后重新触发的去重键。
        if event_key in seen_event_keys:  # 同一 PID 与创建时刻已经报告过时不重复生成事件或 ABT。
            continue  # 跳过当前已知身份并继续检查其余无关求解进程。
        seen_event_keys.add(event_key)  # 在返回事件前登记身份，保证下一样本不会重复触发。
        events.append({"kind": "UNRELATED_SOLVER_PROCESS_AFTER_A0_LAUNCH", "event_key": event_key, "detected_at_utc": utc_now(), "unrelated_process": record, "hard_event": True, "required_action": "WRITE_NATIVE_ABORT_FOR_THIS_A0_JOB_ONLY_AND_WAIT_NATURAL_EXIT", "other_process_disposition_allowed": False})  # 保存完整无关进程身份和只中止本 A0 job 的明确处置边界。
    return events  # 返回本轮全部新无关求解进程硬事件，空列表表示没有新身份。


def host_lease_release_allowed(monitor_block_reason: str | None, stable_exit_confirmed: bool, final_related: list[dict[str, Any]]) -> bool:  # 输入阻断原因、稳定退出确认和最终本 job 进程快照并返回是否允许释放租约。
    return monitor_block_reason is None and stable_exit_confirmed and not final_related  # 仅在无阻断、锁与文件稳定且最终进程树为空三项同时成立时批准释放。


def archive_and_release_host_lease(validated: dict[str, Any], final_status: str) -> dict[str, Any]:  # 输入已闭合启动链与监控终态并在精确核验后封存、删除本运行唯一全局租约。
    run_dir = Path(str(validated["run_dir"])).resolve()  # 读取已经限制在批准运行根内的当前运行目录。
    jobname = str(validated["jobname"])  # 读取已经由启动链闭合的唯一作业名。
    expected_sha256 = str(validated["host_lease_sha256"])  # 读取监控附着前冻结的全局租约字节摘要。
    require(HOST_LEASE_PATH.parent.resolve() == RUNS_ROOT.resolve() and HOST_LEASE_PATH.name == ".c10_a0_exclusive_host_lease.json", "A0 监控器主机租约路径越界")  # 固定只允许处理运行根下唯一专用租约文件。
    require(HOST_LEASE_PATH.is_file(), "A0 监控终态缺少仍应持有的主机租约")  # 租约提前消失表示控制链被外部修改，禁止伪称正常释放。
    lease_payload = monitor_base.read_json(HOST_LEASE_PATH)  # 读取当前全局租约的运行、job 和启动器身份。
    current_sha256 = monitor_base.sha256_file(HOST_LEASE_PATH)  # 在封存前计算当前租约完整字节摘要。
    require(current_sha256 == expected_sha256 and lease_payload.get("run_name") == run_dir.name and lease_payload.get("jobname") == jobname, "A0 监控终态主机租约摘要、运行或 job 身份漂移")  # 阻断删除另一运行或后继控制器的租约。
    archive_path = run_dir / HOST_LEASE_RELEASE_RELATIVE  # 构造本运行 QA 内唯一排他租约终态证据路径。
    archive = {"schema_version": 1, "status": "HOST_LEASE_ARCHIVED_AND_RELEASED_BY_A0_MONITOR", "run_name": run_dir.name, "jobname": jobname, "released_at_utc": utc_now(), "monitor_final_status": final_status, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": current_sha256, "host_lease_payload": lease_payload, "active_process_disposition_allowed": False, "terminate_called": False, "kill_called": False, "send_signal_called": False}  # 冻结原租约、终态、释放时刻和无强制进程处置边界。
    monitor_base.write_json_exclusive(archive_path, archive)  # 在删除全局租约前排他提交完整运行内封存证据。
    require(monitor_base.sha256_file(HOST_LEASE_PATH) == expected_sha256, "A0 主机租约在封存后、释放前发生漂移")  # 关闭封存与删除之间的外部替换竞态。
    HOST_LEASE_PATH.unlink()  # 只删除已两次摘要核验且明确属于本运行和本 job 的唯一全局租约。
    require(not HOST_LEASE_PATH.exists(), "A0 监控终态主机租约释放后仍存在")  # 确认专用租约路径已经真正释放供后续独立运行使用。
    return {"archive_path": str(archive_path), "archive_sha256": monitor_base.sha256_file(archive_path), "host_lease_removed": True, "released_by_monitor": True, "terminate_called": False, "kill_called": False, "send_signal_called": False}  # 返回封存摘要、释放事实和无强制处置证据。


def validate_launch_chain(run_dir: Path) -> dict[str, Any]:  # 输入 A0 运行目录并返回已闭合的启动链、路径与进程身份对象。
    resolved_run = run_dir.resolve()  # 规范化目标绝对路径以关闭相对段歧义。
    require(resolved_run.is_dir() and resolved_run.parent == RUNS_ROOT.resolve() and resolved_run.name.startswith(RUN_PREFIX), f"目标不是批准 A0 运行：{resolved_run}")  # 只允许本项目直接子运行。
    manifest_path = resolved_run / "manifest.json"  # 定位准备清单原件。
    status_path = resolved_run / "C10_static_status.json"  # 定位准备根状态和诊断权限原件。
    claim_path = resolved_run / "runtime_launch_claim.json"  # 定位 Popen 前排他认领原件。
    launch_path = resolved_run / "runtime_launch.json"  # 定位 Popen 后最小真实 PID 记录。
    spawn_claim_path = resolved_run / MONITOR_SPAWN_CLAIM_RELATIVE  # 定位启动器自动创建本监控器前提交的排他认领原件。
    manifest = monitor_base.read_json(manifest_path)  # 读取输入、job、工具和硬门清单。
    status = monitor_base.read_json(status_path)  # 读取准备态、零生产权限和原始零启动声明。
    claim = monitor_base.read_json(claim_path)  # 读取唯一启动权、输入摘要和资源快照。
    launch = monitor_base.read_json(launch_path)  # 读取真实 PID、参数、谱系和监控阈值。
    spawn_claim = monitor_base.read_json(spawn_claim_path)  # 读取证明本监控器由批准启动器自动创建的参数与谱系认领。
    require(HOST_LEASE_PATH.is_file(), "A0 自动监控附着时全局主机租约不存在")  # 启动器必须从双扫描前持续持有租约直到监控终态。
    host_lease = monitor_base.read_json(HOST_LEASE_PATH)  # 读取当前跨运行唯一租约的持有者身份。
    host_lease_sha256 = monitor_base.sha256_file(HOST_LEASE_PATH)  # 计算当前租约摘要供启动链和自动监控认领闭合。
    require(manifest.get("run_name") == resolved_run.name == status.get("run_name") == claim.get("run_name") == launch.get("run_name") == spawn_claim.get("run_name") == host_lease.get("run_name"), "A0 清单、状态、认领、启动、监控认领或租约运行名不一致")  # 关闭跨目录复制错配。
    require(manifest.get("jobname") == status.get("jobname") == claim.get("jobname") == launch.get("jobname") == spawn_claim.get("jobname") == host_lease.get("jobname"), "A0 启动链或主机租约 jobname 不一致")  # 固定唯一结果文件族。
    require(manifest.get("diagnostic_subtype") == status.get("diagnostic_subtype") == claim.get("diagnostic_subtype") == launch.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE, "A0 启动链诊断子类型漂移")  # 阻断其他路径借用监控结论。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "A0 准备清单或根状态已被作废")  # 只附着未被事后撤销的准备输入。
    require(status.get("launch_allowed_for_diagnostic") is True and status.get("launch_allowed_for_production") is False, "A0 根状态未限定为诊断用途")  # 禁止把监控完成外推为生产批准。
    require(claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED" and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "A0 启动认领或 PID 记录状态错误")  # 固定先认领再记录 PID 的顺序。
    require(claim.get("launch_argv") == manifest.get("launch_argv") == launch.get("launch_argv"), "A0 清单、认领与真实启动参数不一致")  # 要求三方参数逐项相等。
    require(launch.get("launch_claim_sha256") == monitor_base.sha256_file(claim_path), "A0 启动记录引用的认领摘要漂移")  # 证明 PID 记录对应当前不可覆盖认领。
    require(claim.get("manifest_sha256") == monitor_base.sha256_file(manifest_path) == launch.get("manifest_sha256"), "A0 启动链清单摘要不一致")  # 关闭清单在准备、认领和监控间的时间窗。
    require(claim.get("prepared_ledger_sha256") == monitor_base.sha256_file(resolved_run / "artifact_hashes.sha256") == launch.get("prepared_ledger_sha256"), "A0 启动链准备账本摘要不一致")  # 关闭全部输入谱系字节身份。
    require(claim.get("prepared_ledger_entry_count") == launch.get("prepared_ledger_entry_count") and int(claim.get("prepared_ledger_entry_count", 0)) >= 25, "A0 启动链账本条目数不一致或不足")  # 固定完整输入、QA 和工具覆盖范围。
    require(claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "A0 认领与 PID 记录资源快照不一致")  # 防止进程创建后改写资源门证据。
    prelaunch_resources = claim.get("prelaunch_resources", {})  # 读取双扫描、资源和租约共同快照供专门硬门核验。
    require(claim.get("double_solver_scan_completed") is True and prelaunch_resources.get("first_solver_scan") == [] and prelaunch_resources.get("second_solver_scan") == [], "A0 启动前没有完成租约前后两次空求解器扫描")  # 固定取得租约前一次、MAPDL Popen 前一次均无冲突进程。
    require(prelaunch_resources.get("disk_24_gib_gate_passed") is True and int(prelaunch_resources.get("disk_free_bytes", 0)) >= DISK_STOP_BYTES, "A0 启动记录没有通过统一二十四 GiB 磁盘门")  # 阻断旧五十 GiB 或低于批准门的运行链。
    require(claim.get("host_lease_path") == launch.get("host_lease_path") == str(HOST_LEASE_PATH) and claim.get("host_lease_sha256") == launch.get("host_lease_sha256") == host_lease_sha256, "A0 启动认领、PID 记录或真实主机租约不一致")  # 三方闭合唯一租约路径与字节身份。
    require(host_lease.get("status") == "A0_EXCLUSIVE_HOST_LEASE_HELD" and int(host_lease.get("launcher_pid", 0)) == int(spawn_claim.get("launcher_pid", -1)), "A0 主机租约状态或启动器 PID 与监控认领不一致")  # 证明自动监控器认领来自当前租约持有启动器。
    require(spawn_claim.get("status") == "MONITOR_AUTO_SPAWN_CLAIMED_NOT_YET_STARTED" and spawn_claim.get("host_lease_sha256") == host_lease_sha256, "A0 监控器自动创建认领状态或租约摘要错误")  # 禁止人工补挂或跨租约监控器。
    require(spawn_claim.get("runtime_launch_sha256") == monitor_base.sha256_file(launch_path), "A0 监控器自动创建认领引用的 MAPDL 启动记录漂移")  # 证明监控器是在当前真实 MAPDL PID 已记录后创建。
    require(claim.get("monitor_auto_start_required") is True and claim.get("postlaunch_unrelated_solver_process_is_hard_event") is True and launch.get("postlaunch_unrelated_solver_process_is_hard_event") is True, "A0 启动链未冻结自动监控或无关求解进程硬事件政策")  # 固定 P1 自动监控和独占运行边界。
    expected_stops = {"available_ram_below_bytes": IMMEDIATE_RAM_STOP_BYTES, "available_ram_below_1_gib_sustained_seconds": int(SUSTAINED_RAM_STOP_SECONDS), "disk_free_below_bytes": DISK_STOP_BYTES}  # 构造当前监控器批准的三项资源硬停阈值。
    require(launch.get("monitor_hard_stops") == expected_stops, "A0 启动记录硬停阈值与专用监控器不一致")  # 禁止启动器和监控器资源合同分叉。
    entries = ledger_base.verify_prepared_ledger(resolved_run)  # 监控附着前逐项复算全部准备工件摘要。
    script_path = Path(__file__).resolve()  # 读取实际调用的监控器源码路径。
    require(script_path == (resolved_run / SCRIPT_RELATIVE).resolve() and SCRIPT_RELATIVE in entries, "实际调用的 A0 监控器不是本运行冻结快照")  # 禁止从可编辑工具源附着真实 PID。
    require(monitor_base.sha256_file(script_path) == manifest.get("runtime_monitor_script_sha256") == entries[SCRIPT_RELATIVE], "A0 监控器真实字节、清单与账本摘要不一致")  # 三方闭合监控代码身份。
    monitor_argv = [str(value) for value in spawn_claim.get("monitor_argv", [])]  # 读取启动器冻结的专用监控器实际参数数组。
    expected_monitor_argv = [str(Path(sys.executable).resolve()), "-B", str(script_path), "--run-dir", str(resolved_run)]  # 构造当前子进程真实解释器和运行目标对应的唯一批准参数数组。
    require(monitor_argv == expected_monitor_argv and spawn_claim.get("monitor_script_sha256") == monitor_base.sha256_file(script_path), "A0 监控器不是由启动器以冻结脚本和参数自动创建")  # 阻断人工补挂、脚本替换或运行目标漂移。
    require(int(spawn_claim.get("launcher_pid", 0)) == os.getppid(), "A0 监控器真实父 PID 不是自动创建认领中的启动器 PID")  # 证明本进程仍由等待握手的批准启动器直接创建。
    require(HELPER_RELATIVE in entries and monitor_base.sha256_file(resolved_run / HELPER_RELATIVE) == manifest.get("runtime_monitor_helper_script_sha256") == entries[HELPER_RELATIVE], "A0 监控帮助模块未冻结或摘要漂移")  # 关闭导入帮助代码字节漂移。
    require(monitor_base.EXPECTED_EQUATION_COUNT == EXPECTED_EQUATION_COUNT, "监控帮助模块方程数常量与 A0 合同不一致")  # 防止日志扫描采用另一个模型秩。
    identity_relative = str(launch.get("process_identity_path", ""))  # 读取最小 PID 记录声明的增强身份相对路径。
    require(identity_relative == "runtime_process_identity.json", "A0 增强进程身份路径不符合冻结合同")  # 阻断路径逃逸或匿名身份。
    identity_path = resolved_run / identity_relative  # 构造当前运行内增强进程身份绝对路径。
    identity = monitor_base.read_json(identity_path)  # 读取 Popen 后真实创建时刻、二进制和命令数组。
    require(identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED" and identity.get("run_name") == resolved_run.name and identity.get("jobname") == manifest.get("jobname"), "A0 增强进程身份状态或 job 错误")  # 固定成功捕获语义。
    require(int(identity.get("pid", 0)) == int(launch.get("main_pid", 0)) and identity.get("runtime_launch_sha256") == monitor_base.sha256_file(launch_path), "A0 增强身份 PID 或启动记录摘要不一致")  # 证明增强身份对应当前最小 PID 记录。
    require(spawn_claim.get("runtime_process_identity_sha256") == monitor_base.sha256_file(identity_path), "A0 监控器自动创建认领引用的增强进程身份漂移")  # 证明监控器只在 MAPDL 增强身份成功后自动创建。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 恢复已经三方闭合的实际启动参数数组。
    jobname = str(manifest.get("jobname"))  # 读取唯一作业名前缀供文件和进程归属绑定。
    solver_dir = Path(monitor_base.argument_value(launch_argv, "-dir")).resolve()  # 从真实参数定位唯一求解工作目录。
    input_path = Path(monitor_base.argument_value(launch_argv, "-i")).resolve()  # 从真实参数定位唯一主输入。
    output_path = Path(monitor_base.argument_value(launch_argv, "-o")).resolve()  # 从真实参数定位权威 OUT。
    require(solver_dir == (resolved_run / "solver").resolve() and solver_dir.is_dir(), "A0 solver 目录越出本运行或缺失")  # 限制日志、锁、进程和 ABT 作用域。
    require(input_path == (resolved_run / str(manifest.get("main_input"))).resolve() and input_path.is_file(), "A0 实际启动输入不是清单主控")  # 阻断正确 job 却执行另一 deck。
    require(output_path == (solver_dir / f"{jobname}.out").resolve(), "A0 OUT 路径不是本 job 唯一权威日志")  # 阻断跨运行日志借用。
    require([str(value) for value in identity.get("command_line", [])] == launch_argv and Path(str(identity.get("executable", ""))).resolve() == Path(launch_argv[0]).resolve(), "A0 操作系统真实命令行或二进制与冻结值不一致")  # 关闭 Popen 后替换和 PID 回收。
    launch_epoch = datetime.fromisoformat(str(launch.get("started_at_utc"))).timestamp()  # 把带时区启动时刻转换为 Unix 秒。
    require(float(identity.get("create_time_epoch_seconds", 0.0)) >= launch_epoch - 10.0, "A0 主进程创建时刻明显早于启动记录")  # 容许 Windows 时间分辨率但拒绝旧 PID。
    return {"run_dir": resolved_run, "manifest": manifest, "claim_path": claim_path, "launch_path": launch_path, "launch": launch, "identity_path": identity_path, "identity": identity, "spawn_claim_path": spawn_claim_path, "spawn_claim": spawn_claim, "host_lease_sha256": host_lease_sha256, "host_lease": host_lease, "solver_dir": solver_dir, "jobname": jobname, "output_path": output_path}  # 返回持续监控所需且已闭合的启动、自动创建、租约、进程和路径对象集合。


def offline_self_test() -> dict[str, Any]:  # 无业务输入；只在内存和系统临时目录验证帮助模块、安全源码和硬门常量。
    base_result = monitor_base.run_offline_self_test()  # 复用成熟帮助模块的十字节 ABT、排他创建、fsync、回读与禁止强杀回归。
    require(base_result.get("status") == "PASS", "A0 监控帮助模块离线自检未通过")  # 只有底层安全函数完整通过才接受包装器；帮助模块冻结状态值为 PASS。
    require(monitor_base.EXPECTED_EQUATION_COUNT == EXPECTED_EQUATION_COUNT, "A0 监控帮助模块方程数常量漂移")  # 固定日志硬门针对当前全桥秩。
    source_text = Path(__file__).read_text(encoding="utf-8", errors="strict")  # 读取本监控器自身源码供 AST 和逐行说明审查。
    syntax_tree = ast.parse(source_text, filename=str(Path(__file__).resolve()))  # 解析真实源码结构而不是依赖关键词搜索。
    forbidden_calls = [node.func.attr for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"terminate", "kill", "send_signal", "Popen", "run", "system"}]  # 查找主动结束、发信号或启动其他进程的调用。
    require(not forbidden_calls, f"A0 监控器存在禁止进程动作：{forbidden_calls}")  # 监控器只能提交官方 ABT并只读等待。
    comment_violations: list[int] = []  # 初始化逐行中文说明违规行号列表。
    for line_number, line in enumerate(source_text.splitlines(), start=1):  # 审查每个非空物理行的同行说明。
        if not line.strip():  # 空白分隔行不承载代码或声明。
            continue  # 跳过空白行并继续检查下一行。
        if "#" not in line or re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", line.split("#", 1)[1]) is None:  # 非空行必须具有至少一个中文字符的同行注释。
            comment_violations.append(line_number)  # 保存违规行号供一次性修复。
    require(not comment_violations, f"A0 监控器逐行中文注释违规：{comment_violations[:20]}")  # 任一缺注释行都使自检失败。
    seen_event_keys: set[str] = set()  # 初始化纯内存无关求解进程硬事件去重集合。
    synthetic_record = {"pid": 43210, "create_time_epoch_seconds": 1234.5, "name": "ansys.exe", "command_line": ["ansys.exe", "-j", "other_job"]}  # 构造不指向真实进程的测试身份以验证硬事件政策。
    first_events = unrelated_solver_events([synthetic_record], seen_event_keys)  # 首次出现同一无关求解进程必须生成一个硬事件。
    duplicate_events = unrelated_solver_events([synthetic_record], seen_event_keys)  # 同一 PID 和创建时刻重复采样不得重复生成事件。
    reused_record = dict(synthetic_record, create_time_epoch_seconds=1235.5)  # 构造 PID 相同但创建时刻不同的再用身份。
    reused_events = unrelated_solver_events([reused_record], seen_event_keys)  # PID 再用后的新身份必须重新生成硬事件。
    require(len(first_events) == 1 and not duplicate_events and len(reused_events) == 1 and first_events[0].get("kind") == "UNRELATED_SOLVER_PROCESS_AFTER_A0_LAUNCH", "A0 无关 MAPDL/MPI 硬事件或 PID 再用去重自检失败")  # 同时固定首次触发、同身份去重和再用重触发语义。
    require(host_lease_release_allowed(None, True, []) is True and host_lease_release_allowed("LOCK_OR_OUTPUT_UNSTABLE", False, []) is False and host_lease_release_allowed(None, True, [synthetic_record]) is False, "A0 主机租约仅在稳定空进程终态释放的判定自检失败")  # 固定正常稳定退出允许、阻断终态禁止和最终仍有本 job 进程禁止三类分支。
    require(HOST_LEASE_PATH == RUNS_ROOT / ".c10_a0_exclusive_host_lease.json", "A0 监控器全局主机租约路径漂移")  # 固定终态只能释放运行根下唯一专用租约且自检不触碰它。
    return {"schema_version": 1, "status": "PASSED", "base_monitor_self_test": base_result, "expected_equation_count": EXPECTED_EQUATION_COUNT, "forbidden_process_action_count": 0, "comment_violation_count": 0, "native_abort_only": True, "force_termination_allowed": False, "exclusive_host_lease_required": True, "monitor_releases_host_lease_only_after_stable_empty_exit": True, "blocked_terminal_retains_host_lease_for_manual_audit": True, "auto_spawn_claim_required": True, "postlaunch_unrelated_solver_process_is_hard_event": True, "unrelated_process_self_test_event_count": len(first_events) + len(reused_events), "project_run_paths_touched": False, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回安全帮助函数、方程门、租约、自动创建、阻断保留、无关进程硬门和零启动自检摘要。


def monitor(validated: dict[str, Any]) -> dict[str, Any]:  # 输入已闭合启动链并持续监控至稳定退出，返回最终状态摘要。
    run_dir = Path(str(validated["run_dir"])).resolve()  # 读取已经验证的唯一运行根。
    solver_dir = Path(str(validated["solver_dir"])).resolve()  # 读取已经限制在本运行内的求解目录。
    jobname = str(validated["jobname"])  # 读取已经四方闭合的唯一作业名。
    output_path = Path(str(validated["output_path"])).resolve()  # 读取唯一权威 OUT 路径。
    error_path = solver_dir / f"{jobname}.err"  # 构造本 job 原生 ERR 路径，启动早期允许不存在。
    native_monitor_path = solver_dir / f"{jobname}.mntr"  # 构造 MAPDL 原生 MNTR 路径供活性和稳定性记录。
    lock_path = solver_dir / f"{jobname}.lock"  # 构造本 job 锁文件，稳定退出时必须消失。
    monitor_claim_path = run_dir / "qa" / "runtime_a0_monitor_claim.json"  # 定位本监控器排他认领文件。
    samples_path = run_dir / "qa" / "runtime_a0_monitor_samples.jsonl"  # 定位逐样本立即刷新的机器流水。
    final_path = run_dir / "qa" / "runtime_a0_monitor_final.json"  # 定位进程树稳定退出后的唯一终态。
    require(not any(path.exists() for path in [monitor_claim_path, samples_path, final_path]), "A0 已存在监控认领、流水或终态，禁止第二监控器附着")  # 关闭双控制器并发与重复 ABT 风险。
    identity = validated["identity"]  # 读取防 PID 回收的增强主进程身份。
    bound_identities: dict[int, float] = {}  # 初始化跨样本 PID 到创建时刻绑定。
    seen_event_keys: set[str] = set()  # 在首次进程快照前初始化硬事件去重集合，使附着瞬间的无关求解进程也进入同一政策。
    initial_related, initial_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, identity, bound_identities)  # 在认领前获取精确本 job 与无关求解进程快照。
    require(bool(initial_related), "A0 监控附着时找不到可信本 job 进程")  # 防止附着已结束、PID 回收或错误 job。
    pending_unrelated_events = unrelated_solver_events(initial_unrelated, seen_event_keys)  # 把附着瞬间出现的每个非本 job MAPDL/MPI 身份立即分类为待提交硬事件。
    claim = {"schema_version": 1, "status": "A0_MONITOR_CLAIMED", "run_name": run_dir.name, "jobname": jobname, "claimed_at_utc": utc_now(), "monitor_pid": os.getpid(), "launcher_pid": os.getppid(), "monitor_script": str(Path(__file__).resolve()), "monitor_script_sha256": monitor_base.sha256_file(Path(__file__).resolve()), "runtime_launch_sha256": monitor_base.sha256_file(validated["launch_path"]), "runtime_launch_claim_sha256": monitor_base.sha256_file(validated["claim_path"]), "runtime_process_identity_sha256": monitor_base.sha256_file(validated["identity_path"]), "monitor_spawn_claim_sha256": monitor_base.sha256_file(validated["spawn_claim_path"]), "host_lease_sha256": validated["host_lease_sha256"], "manifest_sha256": monitor_base.sha256_file(run_dir / "manifest.json"), "prepared_ledger_sha256": monitor_base.sha256_file(run_dir / "artifact_hashes.sha256"), "initial_related_processes": initial_related, "initial_unrelated_solver_processes": initial_unrelated, "initial_unrelated_solver_hard_events": pending_unrelated_events, "expected_equation_count": EXPECTED_EQUATION_COUNT, "hard_stops": validated["launch"]["monitor_hard_stops"], "native_abort_payload_sha256": monitor_base.NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_only": True, "force_termination_allowed": False, "postlaunch_unrelated_solver_process_is_hard_event": True, "other_process_disposition_allowed": False, "default_cnvtol_relaxation_messages_are_hard_events": True}  # 冻结监控 PID、父启动器、自动创建认领、租约、进程、方程、资源和全部硬门。
    monitor_base.write_json_exclusive(monitor_claim_path, claim)  # 在任何样本或 ABT 动作前排他提交唯一监控权。
    started_monotonic = time.monotonic()  # 记录不受系统时钟校正影响的持续时间起点。
    started_at_utc = utc_now()  # 记录人读 UTC 监控起点。
    low_ram_since: float | None = None  # 初始化低于一 GiB 的连续区间起点。
    output_offset = 0  # 初始化 OUT 增量读取字节偏移。
    output_carry = ""  # 初始化 OUT 跨块消息尾文。
    error_offset = 0  # 初始化 ERR 增量读取字节偏移。
    error_carry = ""  # 初始化 ERR 跨块消息尾文。
    hard_events: list[dict[str, Any]] = []  # 初始化全程 FATAL、坏主元、方程漂移、CNVTOL 自动放宽或资源事件列表。
    observed_equations: list[int] = []  # 初始化全部组装方程数记录。
    sample_count = 0  # 初始化从一开始的样本序号。
    empty_samples = 0  # 初始化连续稳定空进程样本数。
    post_exit_since: float | None = None  # 初始化首次发现空进程树的单调时刻。
    previous_terminal_state: tuple[int, int, int] | None = None  # 初始化 OUT、ERR 与 MNTR 上一轮大小元组。
    low_ram_minimum: int | None = None  # 初始化全程最小可用物理内存。
    disk_minimum: int | None = None  # 初始化全程最小磁盘空余。
    maximum_related_rss = 0  # 初始化本 job 进程树最大 RSS，单位 byte。
    abort_evidence = monitor_base.native_abort_evidence_template(solver_dir / f"{jobname}.abt")  # 初始化尚未请求的官方十字节 ABT 完整证据对象。
    monitor_block_reason: str | None = None  # 初始化无退出稳定性阻断原因。
    final_related: list[dict[str, Any]] = []  # 初始化循环结束时本 job 进程快照。
    final_unrelated: list[dict[str, Any]] = []  # 初始化循环结束时无关求解进程快照。
    stable_exit_confirmed = False  # 初始化本 job 空进程、lock 消失和 OUT/ERR/MNTR 连续稳定的组合终态确认。
    with samples_path.open("x", encoding="utf-8", newline="\n") as samples_handle:  # 排他创建逐样本 JSONL，禁止第二监控器覆盖。
        while True:  # 持续采样直至自然或 ABT 后进程树稳定退出，或退出证据超时阻断。
            sample_started = time.monotonic()  # 记录当前样本起点供持续资源计算和十秒节奏。
            memory = psutil.virtual_memory()  # 读取当前全机物理内存快照。
            disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 读取当前运行盘空间快照。
            available_ram = int(memory.available)  # 提取可用物理内存字节数。
            disk_free = int(disk.free)  # 提取运行盘空余字节数。
            low_ram_minimum = available_ram if low_ram_minimum is None else min(low_ram_minimum, available_ram)  # 更新全程最小可用内存。
            disk_minimum = disk_free if disk_minimum is None else min(disk_minimum, disk_free)  # 更新全程最小磁盘空余。
            low_ram_since = sample_started if available_ram < SUSTAINED_RAM_STOP_BYTES and low_ram_since is None else low_ram_since  # 首次低于一 GiB 时开始持续计时。
            low_ram_since = None if available_ram >= SUSTAINED_RAM_STOP_BYTES else low_ram_since  # 内存恢复时清除持续低内存区间。
            low_ram_duration = 0.0 if low_ram_since is None else sample_started - low_ram_since  # 计算当前连续低内存秒数。
            related, unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, identity, bound_identities)  # 获取防 PID 回收的本 job 与无关求解进程快照。
            related_rss = sum(int(record.get("rss_bytes", 0)) for record in related)  # 累计当前本 job 进程树 RSS。
            maximum_related_rss = max(maximum_related_rss, related_rss)  # 更新全程最大本 job RSS。
            output_offset, output_carry, output_text, _ = monitor_base.read_log_increment(output_path, output_offset, output_carry)  # 增量读取 OUT 并保留跨块尾文。
            error_offset, error_carry, error_text, _ = monitor_base.read_log_increment(error_path, error_offset, error_carry)  # 增量读取 ERR 并保留跨块尾文。
            output_events, output_equations = monitor_base.scan_new_text("OUT", output_text, seen_event_keys)  # 扫描 OUT 中 FATAL、坏主元、方程漂移和 CNVTOL 自动放宽消息。
            error_events, error_equations = monitor_base.scan_new_text("ERR", error_text, seen_event_keys)  # 扫描 ERR 中同一有限硬事件集合。
            current_unrelated_events = unrelated_solver_events(unrelated, seen_event_keys)  # 把本样本每个新出现的非本 job MAPDL/MPI 身份分类为硬事件且绝不处置它们。
            new_events = pending_unrelated_events + current_unrelated_events + output_events + error_events  # 合并附着瞬间、当前无关进程和日志硬事件并保持安全优先顺序。
            pending_unrelated_events = []  # 首个样本接收附着瞬间硬事件后清空待提交列表，后续由稳定身份去重集合管理。
            observed_equations.extend(output_equations + error_equations)  # 累计全部组装方程数供终态审计。
            if available_ram < IMMEDIATE_RAM_STOP_BYTES and "RESOURCE_RAM_BELOW_512_MIB" not in seen_event_keys:  # 首次低于五百一十二 MiB 时触发即时资源硬门。
                seen_event_keys.add("RESOURCE_RAM_BELOW_512_MIB")  # 登记稳定去重键避免重复 ABT。
                new_events.append({"kind": "RESOURCE_RAM_BELOW_512_MIB", "observed_bytes": available_ram, "threshold_bytes": IMMEDIATE_RAM_STOP_BYTES, "detected_at_utc": utc_now()})  # 保存实测、阈值与时刻。
            if low_ram_duration >= SUSTAINED_RAM_STOP_SECONDS and "RESOURCE_RAM_BELOW_1_GIB_FOR_60_SECONDS" not in seen_event_keys:  # 首次持续低于一 GiB 六十秒时触发资源硬门。
                seen_event_keys.add("RESOURCE_RAM_BELOW_1_GIB_FOR_60_SECONDS")  # 登记去重键。
                new_events.append({"kind": "RESOURCE_RAM_BELOW_1_GIB_FOR_60_SECONDS", "observed_bytes": available_ram, "continuous_seconds": low_ram_duration, "detected_at_utc": utc_now()})  # 保存实测、持续时长与时刻。
            if disk_free < DISK_STOP_BYTES and "RESOURCE_DISK_BELOW_24_GIB" not in seen_event_keys:  # 首次磁盘低于二十四 GiB 证据门时触发写盘安全硬门。
                seen_event_keys.add("RESOURCE_DISK_BELOW_24_GIB")  # 登记包含批准阈值的稳定去重键。
                new_events.append({"kind": "RESOURCE_DISK_BELOW_24_GIB", "observed_bytes": disk_free, "threshold_bytes": DISK_STOP_BYTES, "historical_largest_package_gib": HISTORICAL_LARGEST_C10_PACKAGE_GIB, "gate_multiplier": DISK_GATE_MULTIPLIER, "detected_at_utc": utc_now()})  # 保存实测、阈值、历史最大包、倍率与时刻。
            hard_events.extend(new_events)  # 在写样本和请求 ABT 前累计本轮全部新硬事件。
            sample_count += 1  # 为当前样本分配从一开始的稳定序号。
            sample = {"schema_version": 1, "sample_index": sample_count, "sampled_at_utc": utc_now(), "elapsed_seconds": sample_started - started_monotonic, "physical_memory_available_bytes": available_ram, "low_ram_continuous_seconds": low_ram_duration, "disk_free_bytes": disk_free, "related_processes": related, "unrelated_solver_processes": unrelated, "related_rss_bytes": related_rss, "out_offset_bytes": output_offset, "err_offset_bytes": error_offset, "out_file": monitor_base.file_snapshot(output_path), "err_file": monitor_base.file_snapshot(error_path), "mntr_file": monitor_base.file_snapshot(native_monitor_path), "lock_file": monitor_base.file_snapshot(lock_path), "new_equation_counts": output_equations + error_equations, "new_hard_events": new_events, "default_cnvtol_relaxation_messages_are_hard_events": True, "ordinary_ncnv_high_residual_and_bisection_are_not_hard_events": True, "native_abort_only": True}  # 保存资源、进程、日志、秩、硬事件与安全政策完整样本。
            monitor_base.append_json_line(samples_handle, sample)  # 立即写入、刷新并保留已完成样本证据。
            if new_events and not bool(abort_evidence.get("request_contract_satisfied")):  # 首次硬事件且尚无有效官方请求时进入唯一 ABT 路径。
                if related:  # 只有可信本 job 进程仍存在时才创建会被消费的 ABT。
                    abort_evidence = monitor_base.request_native_abort(solver_dir, jobname, abort_evidence)  # 排他写入、fsync 并回读官方十字节载荷。
                else:  # 硬事件与进程自然退出同时发生时不留下可能永不消费的 ABT。
                    abort_evidence["abort_file_action"] = "PROCESS_ALREADY_GONE_NO_ABORT_CREATED"  # 记录无文件动作的明确原因。
            if related:  # 本 job 进程树仍存在时继续只读等待而不主动处置。
                empty_samples = 0  # 清除任何包装器交接造成的临时空样本计数。
                post_exit_since = None  # 清除退出稳定计时。
                previous_terminal_state = None  # 清除终端文件大小基线。
            else:  # 当前样本找不到可信本 job 进程树。
                post_exit_since = sample_started if post_exit_since is None else post_exit_since  # 首次空树时开始最多六十秒稳定窗口。
                current_terminal_state = (int(monitor_base.file_snapshot(output_path)["size_bytes"]), int(monitor_base.file_snapshot(error_path)["size_bytes"]), int(monitor_base.file_snapshot(native_monitor_path)["size_bytes"]))  # 构造 OUT、ERR、MNTR 当前大小元组。
                stable_files = previous_terminal_state == current_terminal_state  # 只有连续两轮大小相同才认为权威文件不再写入。
                stable_exit = stable_files and not bool(monitor_base.file_snapshot(lock_path)["exists"])  # 同时要求 MAPDL job 锁已经消失。
                empty_samples = empty_samples + 1 if stable_exit else 0  # 只累计真正稳定且无锁的空进程样本。
                previous_terminal_state = current_terminal_state  # 保存当前大小供下一样本比较。
                if sample_started - post_exit_since >= POST_EXIT_TIMEOUT_SECONDS and not stable_exit:  # 空进程树六十秒后文件或锁仍不稳定时 fail-closed。
                    monitor_block_reason = "PROCESS_TREE_EXITED_BUT_LOCK_REMAINED_OR_OUTPUTS_NOT_STABLE_FOR_60_SECONDS"  # 冻结退出证据阻断原因。
                    final_related, final_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, identity, bound_identities)  # 提交前取得最终进程快照。
                    break  # 结束循环并写阻断终态，绝不强制清理未知锁或进程。
            if empty_samples >= PROCESS_EXIT_EMPTY_SAMPLES:  # 连续两个稳定空树样本满足自然或 ABT 后退出确认。
                final_related, final_unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, identity, bound_identities)  # 再次取得防 PID 回收最终快照。
                if not final_related:  # 最终快照仍为空时才允许提交终态。
                    stable_exit_confirmed = True  # 记录两轮稳定空树、无锁和文件稳定已经闭合且最终复查仍无本 job 进程。
                    break  # 跳出采样循环进入终态汇总。
                empty_samples = 0  # 若重新发现本 job，则恢复运行态继续监控。
            sleep_seconds = max(0.0, SAMPLE_INTERVAL_SECONDS - (time.monotonic() - sample_started))  # 扣除本轮工作时间维持十秒采样节奏。
            time.sleep(sleep_seconds)  # 等待下一轮；单次等待不超过十秒且不阻塞用户超过六十秒。
    if monitor_block_reason is not None:  # 退出证据未闭合时选择阻断终态。
        final_status = "PROCESS_TREE_EXITED_A0_MONITOR_BLOCKED"  # 不把未知锁或持续写入冒充自然完成。
    elif hard_events:  # 存在硬事件且进程最终稳定退出时选择原生中止终态。
        final_status = "HARD_STOP_NATIVE_ABORT_ONLY_PROCESS_TREE_EXITED_STABLE"  # 明确没有调用任何主动进程处置接口。
    else:  # 无硬事件且进程、文件和锁都稳定退出时选择自然完成终态。
        final_status = "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP"  # 只描述执行终止，不宣称静力验收通过。
    lease_release_allowed = host_lease_release_allowed(monitor_block_reason, stable_exit_confirmed, final_related)  # 以纯判定函数关闭阻断终态误释放租约的路径。
    host_lease_release = archive_and_release_host_lease(validated, final_status) if lease_release_allowed else {"host_lease_removed": False, "released_by_monitor": False, "retained_for_manual_audit": True, "reason": monitor_block_reason or "STABLE_EMPTY_EXIT_NOT_CONFIRMED", "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": validated["host_lease_sha256"]}  # 稳定空进程终态才释放；阻断或不确定终态保留租约阻止后继运行。
    final_record = {"schema_version": 1, "status": final_status, "run_name": run_dir.name, "jobname": jobname, "monitor_started_at_utc": started_at_utc, "monitor_finished_at_utc": utc_now(), "duration_seconds": time.monotonic() - started_monotonic, "sample_count": sample_count, "monitor_claim_sha256": monitor_base.sha256_file(monitor_claim_path), "monitor_block_reason": monitor_block_reason, "stable_exit_confirmed": stable_exit_confirmed, "host_lease_release_allowed": lease_release_allowed, "retained_for_manual_audit": not lease_release_allowed, "minimum_physical_memory_available_bytes": low_ram_minimum, "minimum_disk_free_bytes": disk_minimum, "maximum_related_rss_bytes": maximum_related_rss, "observed_equation_counts": observed_equations, "unique_equation_counts": sorted(set(observed_equations)), "expected_equation_count": EXPECTED_EQUATION_COUNT, "hard_events": hard_events, "native_abort": abort_evidence, "host_lease_release": host_lease_release, "terminate_called": False, "kill_called": False, "send_signal_called": False, "final_related_processes": final_related, "final_unrelated_solver_processes": final_unrelated, "final_out_file": monitor_base.file_snapshot(output_path), "final_err_file": monitor_base.file_snapshot(error_path), "final_mntr_file": monitor_base.file_snapshot(native_monitor_path), "final_lock_file": monitor_base.file_snapshot(lock_path), "samples_path": str(samples_path), "samples_sha256": monitor_base.sha256_file(samples_path), "result_use": "A0_EXECUTION_MONITOR_ONLY_EXTERNAL_STATIC_QA_REQUIRED_NO_MODAL_OR_PRODUCTION_CLAIM"}  # 汇总身份、资源、稳定退出、硬事件、官方 ABT、租约释放或保留、退出证据和严格用途边界。
    monitor_base.write_json_exclusive(final_path, final_record)  # 以排他创建提交唯一监控终态。
    return {"run_dir": str(run_dir), "status": final_status, "sample_count": sample_count, "hard_event_count": len(hard_events), "native_abort_requested": bool(abort_evidence.get("request_contract_satisfied")), "stable_exit_confirmed": stable_exit_confirmed, "host_lease_release_allowed": lease_release_allowed, "retained_for_manual_audit": not lease_release_allowed, "host_lease_release": host_lease_release, "terminate_called": False, "kill_called": False, "external_static_qa_required": True}  # 返回稳定退出、硬事件、官方 ABT、租约释放或保留和无强制处置的紧凑机器摘要。


def parse_args() -> argparse.Namespace:  # 无业务输入；解析离线自检或唯一运行监控模式并返回命名空间。
    parser = argparse.ArgumentParser(description="监控 C10 A0 静力运行；硬事件只提交官方十字节 ABT 并等待自然退出。")  # 建立明确无强制处置的命令行接口。
    parser.add_argument("--run-dir", required=False, type=Path, help="正常模式下必填、已经由 A0 专用启动器启动的唯一运行绝对目录。")  # 要求显式目标并禁止猜测 latest。
    parser.add_argument("--self-test", action="store_true", help="仅在内存和系统临时目录验证源码、帮助模块与 ABT，不读取或写入实际运行。")  # 提供零启动离线回归入口。
    return parser.parse_args()  # 返回由 argparse 拒绝未知参数后的命名空间。


def main() -> None:  # 解析模式并执行一次离线自检或持续 A0 监控，无业务返回值。
    arguments = parse_args()  # 读取已完成语法检查的命令行参数。
    if bool(arguments.self_test):  # 离线自检必须在任何运行目录解析前短路。
        require(arguments.run_dir is None, "A0 监控器自检禁止同时提供 --run-dir")  # 防止自检携带真实目标造成误解。
        print(json.dumps(offline_self_test(), ensure_ascii=False, allow_nan=False))  # 输出单行机器自检结果。
        return  # 自检完成后立即退出，真实监控和 ABT 路径不可达。
    require(arguments.run_dir is not None, "A0 正常监控模式必须显式提供 --run-dir")  # 禁止默认选择或遍历其他运行。
    validated = validate_launch_chain(arguments.run_dir)  # 在创建监控认领前闭合准备、启动和进程身份链。
    print(json.dumps(monitor(validated), ensure_ascii=False, allow_nan=False))  # 持续监控至稳定退出并输出紧凑终态摘要。


if __name__ == "__main__":  # 仅在直接执行本冻结脚本时进入自检或监控，导入时不读取任何运行。
    main()  # 执行一次离线回归或唯一 A0 运行持续监控。
