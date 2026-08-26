from __future__ import annotations  # 启用延迟类型注解，保持运行时类型提示兼容且不增加求解依赖。

import argparse  # 解析只读启动前复核、显式实际启动与离线自检三种互斥模式。
import ast  # 离线审查本启动器源码结构和唯一 Popen 调用数量。
import hashlib  # 验证官方原生 ABT 十字节载荷与运行工件身份。
import json  # 输出只读复核、离线自检、启动认领和真实 PID 记录。
import os  # 在身份采集失败时把官方 ABT 十字节载荷 flush 并 fsync 到磁盘。
import re  # 审查每个非空源码行是否具有中文说明。
import subprocess  # 仅在调用者显式给出 --launch 且全部门通过后启动一次 MAPDL。
import sys  # 使用当前已批准 Python 解释器自动启动同运行内冻结的专用监控器。
import tempfile  # 只在系统临时目录离线测试 ABT 排他创建、回读和重复拒绝行为。
import time  # 以单调时钟等待监控器认领握手和 ABT 后本 job 进程树自然退出。
from datetime import datetime, timezone  # 生成启动认领、进程记录和故障证据的 UTC 时刻。
from pathlib import Path  # 安全处理包含中文的运行、求解器、输入与输出绝对路径。
from typing import Any  # 标注清单、状态、账本和启动记录中的异构 JSON 值。

import psutil  # 只读检查实时内存、磁盘和 Popen 后的真实进程身份。

import ultra_c10_adaptive_monitor as monitor_base  # 复用精确本 job 进程树识别和官方 ABT 安全帮助函数，不调用其自适应主流程。
import ultra_c10_static_execute as runtime_base  # 复用已验证的摘要、账本、参数和冲突进程只读帮助函数，不调用其主流程。


RUNS_ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs")  # 冻结唯一批准运行根，阻断任意目录借用启动合同。
RUN_PREFIX = "C10_A0_DIRECT_SPATIAL_RAMP_"  # 只批准 A0 当前 TYPE72 直接空间重力斜坡运行族。
DIAGNOSTIC_SUBTYPE = "A0_CURRENT_TYPE72_S10_DIRECT_SPATIAL_GRAVITY_RAMP_STATIC_ONLY_NRRE"  # 冻结唯一诊断身份并阻断迁移、K5、PRED 或模态包借用。
SCRIPT_RELATIVE = "input_snapshot/ultra_c10_a0_execute.py"  # 冻结实际可调用启动器在运行内的唯一相对路径。
MONITOR_RELATIVE = "input_snapshot/ultra_c10_a0_monitor.py"  # 冻结启动后必须立即附着的专用监控器路径。
STATIC_HELPER_RELATIVE = "input_snapshot/ultra_c10_static_execute.py"  # 冻结当前模块实际导入的只读帮助代码路径。
CONTROLLED_INCLUDE_RELATIVE = "solver/apply_finite_gates_and_passages_v2.inp"  # 冻结 5,078 个 TYPE72 连接 include 路径。
CONTROLLED_INCLUDE_SHA256 = "4f7da8425a25739c694880422c4d2188088b83c1d64170baf44accd922b5b01e"  # 冻结当前直接消元连接字节身份。
MINIMUM_RAM_BYTES = 4 * 1024**3  # 实际 A0 诊断启动要求至少四 GiB 可用物理内存，正式八 GiB 门仍未豁免。
FORMAL_RAM_BYTES = 8 * 1024**3  # 记录正式全桥既定八 GiB 可用物理内存门槛供启动证据披露。
HISTORICAL_LARGEST_C10_PACKAGE_GIB = 5.630  # 冻结既有 C10 失败与 NRRE 包的实测最大占用为 5.630 GiB，来源为项目运行目录体积复核。
DISK_GATE_MULTIPLIER = 4.26  # 冻结二十四 GiB 相对 5.630 GiB 历史最大包约四点二六倍的安全倍率，单位为无量纲。
MINIMUM_DISK_BYTES = 24 * 1024**3  # 实际启动要求运行盘至少二十四 GiB 空余；在复核时 38.653 GiB 空余下仍保留约 14.653 GiB 额外余量，单位 byte。
MONITOR_RAM_IMMEDIATE_BYTES = 512 * 1024**2  # 监控器在可用物理内存低于五百一十二 MiB 时提交原生 ABT 请求。
MONITOR_RAM_SUSTAINED_SECONDS = 60  # 监控器在低于一 GiB 连续六十秒时提交原生 ABT 请求。
MONITOR_DISK_BYTES = 24 * 1024**3  # 监控器在运行盘空余低于二十四 GiB 时提交原生 ABT，请求线与同一历史 5.630 GiB、约四点二六倍证据门统一，单位 byte。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 冻结 MAPDL 2026 R1 认可的 nonlinear 加单一 LF 共十个 ASCII 字节。
NATIVE_ABORT_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结官方 ABT 载荷摘要以关闭换行和编码歧义。
HOST_LEASE_PATH = RUNS_ROOT / ".c10_a0_exclusive_host_lease.json"  # 冻结跨 A0 运行共享的唯一主机排他租约路径，防止两个诊断同时占用 MAPDL 主机资源。
MONITOR_SPAWN_CLAIM_RELATIVE = "runtime_monitor_spawn_claim.json"  # 冻结自动创建监控器前的排他认领文件名。
MONITOR_LAUNCH_RELATIVE = "runtime_monitor_launch.json"  # 冻结自动监控器 Popen 后真实 PID 记录文件名。
MONITOR_ATTACHMENT_RELATIVE = "runtime_monitor_attachment.json"  # 冻结启动器确认监控器已认领并仍存活的握手证据文件名。
MONITOR_CLAIM_RELATIVE = "qa/runtime_a0_monitor_claim.json"  # 冻结监控器完成启动链验证和进程附着后的排他认领路径。
MONITOR_ATTACHMENT_TIMEOUT_SECONDS = 30.0  # 自动监控器必须在三十秒内提交有效 claim，单位 s；超时触发本 job 官方 ABT。
MONITOR_ATTACHMENT_POLL_SECONDS = 0.25  # 启动器每零点二五秒检查一次监控 claim 和监控进程状态，单位 s。
NATURAL_EXIT_POLL_SECONDS = 2.0  # ABT 后每两秒只读检查本 job 进程树是否自然退出，单位 s。
NATURAL_EXIT_EMPTY_SAMPLES = 2  # 连续两个空进程样本才确认本 job 自然退出，避免包装器交接瞬间误判。
NATURAL_EXIT_TIMEOUT_SECONDS = 600.0  # ABT 后最多用十分钟闭合本 job 空进程、无锁和输出稳定证据，超时保留租约供人工审计，单位 s。


def require(condition: bool, message: str) -> None:  # 接收布尔门与失败说明；失败时阻断只读复核或实际启动且无业务返回值。
    if not condition:  # 仅在身份、谱系、控制、资源、排他性或代码安全门失败时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常并保证失败发生在 Popen 前或留下已启动故障证据。


def commands_from_text(text: str) -> list[str]:  # 输入完整 APDL 文本并返回删除说明和普通空格后的大写可执行命令序列。
    commands: list[str] = []  # 初始化保持真实执行顺序的命令列表。
    for line in text.splitlines():  # 逐行扫描完整主控或 include，禁止抽样漏掉禁项。
        command = line.split("!", maxsplit=1)[0].strip()  # 删除 APDL 说明并保留真正执行部分。
        if not command:  # 空行和整行说明不属于数值合同。
            continue  # 跳过非执行内容并处理下一物理行。
        commands.append(command.upper().replace(" ", ""))  # 规范大小写和普通空格但保留参数、数值与顺序。
    return commands  # 返回供精确计数与禁止项检查的完整命令列表。


def write_native_abort(solver_dir: Path, jobname: str) -> dict[str, Any]:  # 输入求解目录和作业名并排他创建、同步、回读官方十字节 ABT，返回动作证据。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n" and len(NATIVE_ABORT_PAYLOAD) == 10, "官方 ABT 字节或长度常量漂移")  # 在打开任何目标前关闭载荷字面值和长度门。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_SHA256, "官方 ABT SHA-256 常量漂移")  # 独立计算摘要并拒绝 CRLF、空文件或附加说明。
    abort_path = solver_dir / f"{jobname}.abt"  # 按 MAPDL 约定构造本 job 唯一原生中止请求路径。
    if abort_path.exists():  # 监控器可能已先一步为同一硬事件提交 ABT，此时只读验证并绝不覆盖。
        existing_payload = abort_path.read_bytes()  # 读取既有文件全部字节以核对是否已满足同一官方合同。
        require(existing_payload == NATIVE_ABORT_PAYLOAD, f"既有 ABT 不是有效十字节官方载荷：{abort_path}")  # 无效既有文件保持原样并 fail-closed。
        return {"path": str(abort_path), "length_bytes": len(existing_payload), "hex": existing_payload.hex(), "sha256": hashlib.sha256(existing_payload).hexdigest(), "created_exclusively": False, "existing_valid_file_preserved": True, "flush_completed": None, "fsync_completed": None, "readback_matches_contract": True, "force_termination_called": False}  # 返回只读确认的有效既有请求并明确未覆盖。
    with abort_path.open("x+b") as handle:  # 使用二进制排他创建，禁止文本换行转换和覆盖竞态。
        written = handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入精确十字节官方载荷。
        require(written == 10, f"官方 ABT 发生短写：{written}/10")  # 短写时禁止声称有效中止请求。
        handle.flush()  # 把 Python 用户态缓冲提交到操作系统句柄。
        os.fsync(handle.fileno())  # 请求操作系统把十字节内容同步到持久存储。
        handle.seek(0)  # 把同一排他句柄移回首字节以避免路径替换竞态。
        readback = handle.read()  # 从同一文件描述符回读实际落盘载荷。
    require(readback == NATIVE_ABORT_PAYLOAD, "官方 ABT 回读字节不一致")  # 只有逐字节相等才承认请求有效。
    return {"path": str(abort_path), "length_bytes": len(readback), "hex": readback.hex(), "sha256": hashlib.sha256(readback).hexdigest(), "created_exclusively": True, "flush_completed": True, "fsync_completed": True, "readback_matches_contract": True, "force_termination_called": False}  # 返回完整字节、同步、回读和禁止强制处置证据。


def archive_and_release_host_lease(run_dir: Path, expected_lease_sha256: str, archive_name: str, reason: str, mapdl_started: bool) -> dict[str, Any]:  # 输入运行、租约摘要、封存名、原因和启动事实并在精确核验后封存及释放全局租约。
    resolved_run = run_dir.resolve()  # 规范化运行根供边界和封存路径检查。
    require(resolved_run.parent == RUNS_ROOT.resolve() and resolved_run.name.startswith(RUN_PREFIX), "租约释放目标不是批准 A0 运行")  # 禁止借用本函数处理其他目录。
    require(HOST_LEASE_PATH.parent.resolve() == RUNS_ROOT.resolve() and HOST_LEASE_PATH.name == ".c10_a0_exclusive_host_lease.json", "全局租约路径常量越界")  # 固定只能释放唯一专用文件。
    require(HOST_LEASE_PATH.is_file(), "待封存的 A0 主机租约不存在")  # 缺失租约可能表示另一控制器已释放，必须拒绝重复动作。
    lease_payload = runtime_base.load_json(HOST_LEASE_PATH)  # 读取当前全局租约的运行、job 和取得时刻。
    current_hash = runtime_base.sha256_file(HOST_LEASE_PATH)  # 计算动作紧前租约字节摘要。
    expected_jobname = runtime_base.load_json(resolved_run / "manifest.json").get("jobname")  # 从本运行已冻结清单读取唯一 jobname 供租约归属核验。
    require(current_hash == expected_lease_sha256 and lease_payload.get("run_name") == resolved_run.name and lease_payload.get("jobname") == expected_jobname, "A0 主机租约摘要、运行或 job 身份漂移")  # 阻断删除另一运行或另一 job 的新租约。
    archive_path = resolved_run / "qa" / archive_name  # 构造本运行内不可覆盖的租约封存证据路径。
    archive = {"schema_version": 1, "status": "HOST_LEASE_ARCHIVED_AND_RELEASED", "run_name": resolved_run.name, "jobname": lease_payload.get("jobname"), "released_at_utc": datetime.now(timezone.utc).isoformat(), "release_reason": reason, "mapdl_started": mapdl_started, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": current_hash, "host_lease_payload": lease_payload, "active_process_disposition_allowed": False, "terminate_called": False, "kill_called": False}  # 冻结原租约、释放原因、启动事实和禁止强制进程处置边界。
    runtime_base.write_json(archive_path, archive)  # 在删除全局租约前排他提交完整封存证据。
    require(runtime_base.sha256_file(HOST_LEASE_PATH) == expected_lease_sha256, "A0 主机租约在封存后、释放前发生漂移")  # 关闭封存到删除之间的竞态窗口。
    HOST_LEASE_PATH.unlink()  # 只删除已经两次摘要核验且属于本运行的精确全局租约文件，以允许后续独立 A0 运行。
    require(not HOST_LEASE_PATH.exists(), "A0 主机租约释放后仍存在")  # 确认专用租约路径已真正释放。
    return {"archive_path": str(archive_path), "archive_sha256": runtime_base.sha256_file(archive_path), "host_lease_removed": True, "release_reason": reason, "terminate_called": False, "kill_called": False}  # 返回封存摘要和已释放事实供故障或终态记录引用。


def terminal_sample_is_stable(related: list[dict[str, Any]], lock_exists: bool, current_file_state: tuple[int, int, int], previous_file_state: tuple[int, int, int] | None) -> bool:  # 输入本 job 进程、锁状态和两轮 OUT/ERR/MNTR 大小并返回当前样本是否满足完整稳定退出门。
    return not related and not lock_exists and previous_file_state == current_file_state  # 只有空进程、lock 不存在且三份权威文件连续两轮大小一致才接受当前稳定样本。


def wait_for_natural_job_exit(solver_dir: Path, jobname: str, identity: dict[str, Any]) -> dict[str, Any]:  # 输入本 job 工作目录、作业名和增强身份并在限时内只读等待空进程、无锁及输出连续稳定。
    bound_identities: dict[int, float] = {}  # 初始化跨样本 PID 到创建时刻绑定，防止 PID 回收误判。
    sample_count = 0  # 初始化 ABT 后自然退出等待样本数。
    stable_samples = 0  # 初始化同时满足空进程、无锁和输出稳定的连续样本数。
    observed_unrelated: list[dict[str, Any]] = []  # 初始化等待期间出现的非本 job 求解进程披露列表。
    output_path = solver_dir / f"{jobname}.out"  # 构造本 job 权威 OUT 路径供连续稳定性检查。
    error_path = solver_dir / f"{jobname}.err"  # 构造本 job 原生 ERR 路径供连续稳定性检查。
    monitor_path = solver_dir / f"{jobname}.mntr"  # 构造本 job 原生 MNTR 路径供连续稳定性检查。
    lock_path = solver_dir / f"{jobname}.lock"  # 构造本 job 锁文件路径，释放租约前必须不存在。
    previous_file_state: tuple[int, int, int] | None = None  # 初始化 OUT、ERR、MNTR 上一轮大小基线。
    started_monotonic = time.monotonic()  # 记录不受系统时钟调整影响的十分钟超时起点。
    final_related: list[dict[str, Any]] = []  # 初始化返回前最后一轮本 job 进程快照。
    final_lock_exists = True  # 初始化返回前锁存在状态为保守真值。
    final_file_state = (0, 0, 0)  # 初始化返回前 OUT、ERR、MNTR 文件大小状态。
    while stable_samples < NATURAL_EXIT_EMPTY_SAMPLES and time.monotonic() - started_monotonic < NATURAL_EXIT_TIMEOUT_SECONDS:  # 在十分钟内持续只读等待连续两个完整稳定终态样本。
        related, unrelated, bound_identities = monitor_base.solver_process_snapshot(jobname, solver_dir, identity, bound_identities)  # 精确识别本 job、后代和非本 job MAPDL/MPI。
        sample_count += 1  # 为当前自然退出检查分配顺序号。
        observed_unrelated.extend(unrelated)  # 累计披露等待期间全部非本 job 求解进程而不处置它们。
        current_file_state = (int(monitor_base.file_snapshot(output_path)["size_bytes"]), int(monitor_base.file_snapshot(error_path)["size_bytes"]), int(monitor_base.file_snapshot(monitor_path)["size_bytes"]))  # 读取三份权威输出当前大小供连续稳定判断。
        lock_exists = bool(monitor_base.file_snapshot(lock_path)["exists"])  # 读取当前 MAPDL job 锁是否仍存在。
        stable_now = terminal_sample_is_stable(related, lock_exists, current_file_state, previous_file_state)  # 同时判定本轮空进程、无锁和输出未再增长。
        stable_samples = stable_samples + 1 if stable_now else 0  # 只累计完整稳定样本，任一条件回退都清零。
        previous_file_state = current_file_state  # 保存本轮文件大小供下一轮连续稳定比较。
        final_related = related  # 保存当前本 job 进程快照供成功或超时终态证据。
        final_lock_exists = lock_exists  # 保存当前锁状态供成功或超时终态证据。
        final_file_state = current_file_state  # 保存当前文件大小元组供成功或超时终态证据。
        if stable_samples < NATURAL_EXIT_EMPTY_SAMPLES and time.monotonic() - started_monotonic < NATURAL_EXIT_TIMEOUT_SECONDS:  # 尚未闭合且仍在批准窗口内时才等待下一轮。
            time.sleep(NATURAL_EXIT_POLL_SECONDS)  # 每次只等待两秒，绝不调用 terminate、kill 或信号接口。
    stable_exit_confirmed = stable_samples >= NATURAL_EXIT_EMPTY_SAMPLES and not final_related and not final_lock_exists  # 只有完整稳定样本数、最终空进程和最终无锁同时成立才闭合自然退出。
    return {"status": "NATURAL_JOB_EXIT_LOCK_ABSENT_OUTPUTS_STABLE_CONFIRMED" if stable_exit_confirmed else "NATURAL_JOB_EXIT_NOT_CONFIRMED_MANUAL_AUDIT_REQUIRED", "sample_count": sample_count, "stable_samples": stable_samples, "timeout_seconds": NATURAL_EXIT_TIMEOUT_SECONDS, "timed_out": not stable_exit_confirmed, "stable_exit_confirmed": stable_exit_confirmed, "host_lease_release_allowed": stable_exit_confirmed, "manual_audit_required": not stable_exit_confirmed, "final_related_processes": final_related, "final_lock_exists": final_lock_exists, "final_out_err_mntr_size_bytes": list(final_file_state), "unrelated_solver_processes_observed": observed_unrelated, "terminate_called": False, "kill_called": False}  # 返回进程、锁、文件稳定、超时、租约权限和无强制处置完整证据。


def validate_run(run_dir: Path) -> dict[str, Any]:  # 输入 A0 运行目录并返回不写盘的启动前包、控制和当前资源复核摘要。
    resolved_run = run_dir.resolve()  # 规范化目标绝对路径以关闭相对段歧义。
    require(resolved_run.is_dir() and resolved_run.parent == RUNS_ROOT.resolve() and resolved_run.name.startswith(RUN_PREFIX), f"目标不是批准 A0 运行：{resolved_run}")  # 只允许本项目 ultra_runs 的直接子目录。
    manifest_path = resolved_run / "manifest.json"  # 定位准备阶段冻结清单原件。
    status_path = resolved_run / "C10_static_status.json"  # 定位独立根状态与启动权限原件。
    manifest = runtime_base.load_json(manifest_path)  # 读取唯一主控、求解器、运行代码和控制合同。
    status = runtime_base.load_json(status_path)  # 读取零启动、诊断权限和非生产边界。
    require(manifest.get("run_name") == resolved_run.name == status.get("run_name") and manifest.get("jobname") == status.get("jobname"), "A0 目录、清单和根状态身份不一致")  # 关闭跨目录复制或 job 错配。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "A0 不是可复核准备态")  # 阻断已终结、作废或其他生命周期包。
    require(manifest.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE and status.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE, "A0 启动链诊断子类型漂移")  # 禁止其他静力或迁移候选借用本入口。
    require(status.get("launch_allowed_for_diagnostic") is True and status.get("launch_allowed_for_production") is False, "A0 根状态未明确限于诊断启动")  # 固定可诊断但不可生产的权限边界。
    require(status.get("mapdl_execution_attempted") is False and status.get("mapdl_started") is False and status.get("full_bridge_modal_status") == "NOT_RUN", "A0 根状态不是零启动或错误声称模态")  # 防止目录复用和结果覆盖。
    entries = runtime_base.verify_prepared_ledger(resolved_run)  # 在临近任何启动时逐项复算完整准备账本。
    require("manifest.json" in entries and "C10_static_status.json" in entries and len(entries) >= 25, "A0 准备账本缺少身份工件或条目不足")  # 防止残缺包进入运行环境。
    script_path = Path(__file__).resolve()  # 读取实际调用的启动器路径供运行内快照身份核验。
    script_expected = (resolved_run / SCRIPT_RELATIVE).resolve()  # 构造清单批准的运行内冻结启动器绝对路径。
    require(script_path == script_expected and SCRIPT_RELATIVE in entries, "实际调用的 A0 启动器不是本运行冻结快照")  # 禁止从可继续编辑的 ultra_tools 源直接启动。
    require(runtime_base.sha256_file(script_path) == manifest.get("runtime_execute_script_sha256") == entries[SCRIPT_RELATIVE], "A0 启动器真实字节、清单和账本摘要不一致")  # 三方闭合运行代码身份。
    require(MONITOR_RELATIVE in entries and runtime_base.sha256_file(resolved_run / MONITOR_RELATIVE) == manifest.get("runtime_monitor_script_sha256") == entries[MONITOR_RELATIVE], "A0 专用监控器未冻结或摘要漂移")  # 确保启动后可立即附着正确监控器。
    require(STATIC_HELPER_RELATIVE in entries and runtime_base.sha256_file(resolved_run / STATIC_HELPER_RELATIVE) == manifest.get("runtime_static_helper_script_sha256") == entries[STATIC_HELPER_RELATIVE], "A0 启动帮助模块未冻结或摘要漂移")  # 关闭导入帮助代码字节漂移。
    solver_dir = (resolved_run / "solver").resolve()  # 定位本运行唯一 MAPDL 工作目录。
    main_path = (resolved_run / str(manifest.get("main_input"))).resolve()  # 按清单定位唯一 A0 主控。
    include_path = (resolved_run / CONTROLLED_INCLUDE_RELATIVE).resolve()  # 定位当前 5,078 个 TYPE72 连接 include。
    executable = Path(str(manifest.get("mapdl_executable"))).resolve()  # 定位未来唯一批准 MAPDL 二进制。
    require(main_path.is_file() and main_path.parent == solver_dir, "A0 主控缺失或越出本运行 solver 目录")  # 阻断跨运行输入污染。
    require(include_path.is_file() and runtime_base.sha256_file(include_path) == CONTROLLED_INCLUDE_SHA256 == manifest.get("controlled_include_sha256"), "A0 当前 TYPE72 include 缺失或摘要漂移")  # 固定连接模型字节身份。
    require(executable.is_file() and runtime_base.sha256_file(executable) == manifest.get("mapdl_executable_sha256"), "A0 MAPDL 二进制缺失或摘要漂移")  # 固定未来求解器版本。
    require(runtime_base.sha256_file(main_path) == manifest.get("main_input_sha256") == entries[str(manifest["main_input"]).replace("\\", "/")], "A0 主控真实字节、清单和账本摘要不一致")  # 三方闭合唯一可执行 deck。
    main_commands = commands_from_text(main_path.read_text(encoding="utf-8", errors="strict"))  # 解析准备后真实主控完整命令序列。
    require(main_commands.count("SOLVE") == 2 and main_commands.count("ANTYPE,STATIC") == 1, "A0 主控不是静力 LS1/LS2 两次求解")  # 固定分析类型和求解范围。
    require(main_commands.count("KBC,0") == 2 and "KBC,1" not in main_commands, "A0 KBC 未保持 S10 双斜坡合同")  # 禁止形成态阶跃或迁移路径。
    require(main_commands.count("AUTOTS,ON") == 1 and main_commands.count("AUTOTS,OFF") == 1, "A0 AUTOTS 未保持 S10 LS1/LS2 合同")  # 固定 LS1 自动细分、LS2 单步保持。
    require(main_commands.count("NSUBST,20,200,20") == 1 and main_commands.count("NSUBST,1,1,1") == 1, "A0 NSUBST 未保持 S10 两步合同")  # 固定二十起步和零增量保持。
    require(main_commands.count("PRED,OFF") == 1 and main_commands.count("NLDIAG,NRRE,ON,50") == 1, "A0 PRED 或 NRRE 合同漂移")  # 保持预测器不变且只启用五十文件 NRRE。
    require(not any(command.startswith("CNVTOL,") or command.startswith("KEYOPT,72,") or command.startswith("NLDIAG,EFLG") for command in main_commands), "A0 主控意外含 CNVTOL、KEYOPT 或 EFLG")  # 固定默认 CNVTOL 诊断、当前 K5 和只输出 NRRE。
    require(not any(command.startswith("MODOPT,") or command.startswith("PERTURB,") or ",PERTURB" in command or command.startswith("MXPAND,") for command in main_commands), "A0 主控仍含模态命令")  # 阻断低内存诊断进入模态。
    include_commands = commands_from_text(include_path.read_text(encoding="utf-8", errors="strict"))  # 解析连接 include 供 KEYOPT 与数量独立复核。
    require(include_commands.count("KEYOPT,72,1,1") == 1 and include_commands.count("KEYOPT,72,2,0") == 1 and include_commands.count("KEYOPT,72,5,0") == 1 and include_commands.count("TYPE,72") == 5078, "A0 当前 TYPE72 KEYOPT 或数量漂移")  # 明确保留直接消元、大转动和几何应力刚度。
    require(manifest.get("cnvtol_explicit_command_count") == 0 and manifest.get("cnvtol_changed") is False and manifest.get("mpc184_keyopt5_static") == 0 and manifest.get("keyopt_changed") is False, "A0 清单没有冻结默认 CNVTOL 或当前 K5")  # 防止 deck 与机器说明分叉。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and manifest.get("execution_mode") == "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "A0 清单范围不是 SMP1 静力非生产诊断")  # 固定资源和结论边界。
    runtime_identity_names = ["runtime_launch_claim.json", "runtime_launch.json", "runtime_process_identity.json", "runtime_process_identity_failure.json", MONITOR_SPAWN_CLAIM_RELATIVE, MONITOR_LAUNCH_RELATIVE, MONITOR_ATTACHMENT_RELATIVE, "runtime_monitor_attachment_failure.json", "runtime_prelaunch_failure.json", "runtime_popen_failure.json"]  # 定义实际启动前必须不存在的全部启动器、监控器握手与故障根级工件。
    require(not any((resolved_run / name).exists() for name in runtime_identity_names), "A0 已存在启动认领、PID 或身份故障工件，禁止复用")  # 关闭同目录双启动和结果覆盖。
    jobname = str(manifest.get("jobname"))  # 读取冻结作业名前缀供结果族和参数核验。
    require(not list(solver_dir.glob(f"{jobname}*")), "A0 solver 已存在本 job 文件族，禁止覆盖或续跑")  # 任何 OUT、RST、LOCK、NRRE 或 DB 都证明该 job 已使用。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 恢复准备器冻结的完整参数数组。
    require(bool(launch_argv) and launch_argv[0] == str(executable), "A0 启动参数首项不是冻结 MAPDL")  # 固定实际二进制入口。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and runtime_base.argument_value(launch_argv, "-np") == "1", "A0 启动参数不是唯一批处理 SMP1")  # 禁止 DMP、MPI 或多进程诊断。
    require("-dis" not in launch_argv and "-mpi" not in launch_argv, "A0 启动参数意外包含 DMP/MPI")  # 显式关闭与当前资源合同不符的并行模式。
    require(runtime_base.argument_value(launch_argv, "-j") == jobname and Path(runtime_base.argument_value(launch_argv, "-dir")).resolve() == solver_dir, "A0 启动 job 或工作目录漂移")  # 固定唯一结果文件族和工作边界。
    require(Path(runtime_base.argument_value(launch_argv, "-i")).resolve() == main_path and Path(runtime_base.argument_value(launch_argv, "-o")).resolve() == (solver_dir / f"{jobname}.out").resolve(), "A0 启动输入或 OUT 路径漂移")  # 固定已哈希 deck 和唯一权威日志。
    conflicts = runtime_base.active_solver_processes()  # 只读获取当前 MAPDL/MPI 冲突进程；validate-only 披露但不把包判为无效。
    memory = psutil.virtual_memory()  # 只读获取当前物理内存快照供是否可立即启动判断。
    disk = psutil.disk_usage(str(resolved_run.drive + "\\"))  # 只读获取运行盘空间快照供是否可立即启动判断。
    host_lease_exists = HOST_LEASE_PATH.exists()  # 只读检查跨运行唯一主机租约是否已经被另一 A0 控制链占用。
    launch_ready_now = not conflicts and not host_lease_exists and int(memory.available) >= MINIMUM_RAM_BYTES and int(disk.free) >= MINIMUM_DISK_BYTES  # 同时满足真实进程独占、租约独占、四 GiB 内存与二十四 GiB 证据化磁盘门才标记当前可启动。
    return {"schema_version": 1, "status": "PASSED_VALIDATE_ONLY", "run_name": resolved_run.name, "jobname": jobname, "manifest": manifest, "root_status": status, "ledger_entry_count": len(entries), "solver_dir": solver_dir, "main_path": main_path, "executable": executable, "launch_argv": launch_argv, "conflicting_solver_processes": conflicts, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_exists": host_lease_exists, "physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": int(memory.available), "formal_8_gib_gate_passed": int(memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_gate_passed": int(memory.available) >= MINIMUM_RAM_BYTES, "disk_free_bytes": int(disk.free), "disk_24_gib_gate_passed": int(disk.free) >= MINIMUM_DISK_BYTES, "disk_gate_historical_largest_package_gib": HISTORICAL_LARGEST_C10_PACKAGE_GIB, "disk_gate_multiplier": DISK_GATE_MULTIPLIER, "monitor_auto_start_required": True, "monitor_attachment_timeout_seconds": MONITOR_ATTACHMENT_TIMEOUT_SECONDS, "postlaunch_unrelated_solver_process_is_hard_event": True, "active_process_disposition_allowed": False, "launch_ready_now": launch_ready_now, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回包有效性、实时资源、二十四 GiB 门、租约与自动监控合同，且和启动动作明确分离。


def offline_self_test() -> dict[str, Any]:  # 无业务输入；只在内存和系统临时目录验证源码、ABT 和零项目写入边界。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n" and len(NATIVE_ABORT_PAYLOAD) == 10 and hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_SHA256, "A0 启动器官方 ABT 合同自检失败")  # 同时核对字节、长度和摘要。
    source_text = Path(__file__).read_text(encoding="utf-8", errors="strict")  # 读取启动器自身完整源码供 AST 与逐行注释审查。
    syntax_tree = ast.parse(source_text, filename=str(Path(__file__).resolve()))  # 解析真实结构而不是依赖关键词匹配。
    popen_calls = [node for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]  # 统计所有可能创建子进程的 Popen 调用节点。
    require(len(popen_calls) == 2, f"A0 启动器 Popen 调用数不是批准的 MAPDL 加监控器两次：{len(popen_calls)}")  # 只允许显式 --launch 分支依次创建一个 MAPDL 和一个冻结专用监控器。
    forbidden_process_calls = [node.func.attr for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"terminate", "kill", "send_signal", "system"}]  # 查找任何主动进程处置或 shell 绕行调用。
    require(not forbidden_process_calls, f"A0 启动器存在禁止进程动作：{forbidden_process_calls}")  # 身份失败只能提交官方 ABT，绝不强杀。
    comment_violations: list[int] = []  # 初始化逐行中文注释违规行号列表。
    for line_number, line in enumerate(source_text.splitlines(), start=1):  # 审查每个非空物理行的同行中文说明。
        if not line.strip():  # 空白分隔行不承载代码或声明。
            continue  # 跳过空白行并处理下一行。
        if "#" not in line or re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", line.split("#", 1)[1]) is None:  # 非空行必须具有至少一个中文字符的同行注释。
            comment_violations.append(line_number)  # 保存违规行号供一次性修复。
    require(not comment_violations, f"A0 启动器逐行中文注释违规：{comment_violations[:20]}")  # 任一代码行缺说明都使自检失败。
    with tempfile.TemporaryDirectory(prefix="ultra_c10_a0_execute_selftest_") as temporary_text:  # 创建自动清理的系统临时目录，绝不触碰 ultra_runs。
        temporary_dir = Path(temporary_text)  # 把临时目录文本转换为路径对象供 ABT 测试。
        evidence = write_native_abort(temporary_dir, "a0_selftest")  # 排他创建、同步并回读一份官方十字节样本。
        require(evidence["readback_matches_contract"] is True and evidence["length_bytes"] == 10, "A0 启动器临时 ABT 回读自检失败")  # 固定写入函数真实行为。
        duplicate_evidence = write_native_abort(temporary_dir, "a0_selftest")  # 第二次调用只读确认同一有效十字节文件并保持原字节不变。
        require(duplicate_evidence["existing_valid_file_preserved"] is True and duplicate_evidence["created_exclusively"] is False, "A0 启动器未只读保留既有有效 ABT")  # 保证并发控制器重复请求不会覆盖或截断有效载荷。
        invalid_path = temporary_dir / "a0_invalid.abt"  # 构造独立无效既有 ABT 路径供 fail-closed 回归。
        invalid_path.write_bytes(b"invalid\n")  # 写入八字节无效样本以证明启动器绝不覆盖非合同内容。
        invalid_rejected = False  # 初始化无效既有 ABT 是否被拒绝的标志。
        try:  # 尝试对无效既有 ABT 提交同名请求。
            write_native_abort(temporary_dir, "a0_invalid")  # 调用必须只读发现漂移并抛出异常。
        except RuntimeError:  # 捕获预期的无效既有文件异常。
            invalid_rejected = True  # 记录 fail-closed 分支已经执行。
        require(invalid_rejected and invalid_path.read_bytes() == b"invalid\n", "A0 启动器未拒绝并原样保留无效既有 ABT")  # 同时证明拒绝事实和零覆盖事实。
    require(HOST_LEASE_PATH == RUNS_ROOT / ".c10_a0_exclusive_host_lease.json", "A0 全局主机租约路径漂移")  # 固定跨运行唯一租约文件且不触碰真实路径。
    require(terminal_sample_is_stable([], False, (10, 20, 30), (10, 20, 30)) is True and terminal_sample_is_stable([], True, (10, 20, 30), (10, 20, 30)) is False and terminal_sample_is_stable([{"pid": 1}], False, (10, 20, 30), (10, 20, 30)) is False and terminal_sample_is_stable([], False, (10, 20, 31), (10, 20, 30)) is False, "A0 启动器完整稳定退出判定自检失败")  # 固定空进程、无锁、三文件连续稳定全部成立才允许释放租约。
    require(NATURAL_EXIT_TIMEOUT_SECONDS == 600.0, "A0 启动器自然退出证据超时常量漂移")  # 固定十分钟后保留租约并转人工审计的安全边界。
    return {"schema_version": 1, "status": "PASSED", "popen_call_count": 2, "popen_not_executed": True, "mapdl_popen_count": 1, "monitor_popen_count": 1, "forbidden_process_action_count": 0, "comment_violation_count": 0, "native_abort_payload_length_bytes": 10, "native_abort_payload_sha256": NATIVE_ABORT_SHA256, "duplicate_valid_abort_preserved": True, "invalid_abort_rejected_and_preserved": True, "exclusive_host_lease_required": True, "double_solver_scan_required": True, "monitor_auto_start_and_claim_handshake_required": True, "monitor_attachment_timeout_seconds": MONITOR_ATTACHMENT_TIMEOUT_SECONDS, "runtime_failure_exit_requires_empty_process_no_lock_and_stable_outputs": True, "runtime_failure_exit_timeout_seconds": NATURAL_EXIT_TIMEOUT_SECONDS, "runtime_failure_timeout_retains_host_lease_for_manual_audit": True, "postlaunch_unrelated_solver_process_is_hard_event": True, "project_run_paths_touched": False, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回源码、ABT、租约、双扫描、自动监控、完整退出门和零启动自检结果。


def launch(validated: dict[str, Any]) -> dict[str, Any]:  # 输入已通过包门的只读复核对象，取得独占租约后依次启动 MAPDL 与专用监控器并返回握手摘要。
    require(validated.get("status") == "PASSED_VALIDATE_ONLY", "A0 启动输入不是刚通过的只读复核对象")  # 防止绕过统一启动前门。
    require(validated.get("launch_ready_now") is True, f"A0 当前资源、进程或租约门不允许启动：{validated.get('conflicting_solver_processes')}")  # 独占、内存或磁盘不满足时在任何写入前拒绝。
    run_dir = Path(str(validated["solver_dir"])).parent.resolve()  # 从已验证 solver 目录回取唯一运行根。
    manifest = validated["manifest"]  # 读取已经由账本和真实字节闭合的清单对象。
    solver_dir = Path(str(validated["solver_dir"])).resolve()  # 读取已验证 MAPDL 工作目录。
    executable = Path(str(validated["executable"])).resolve()  # 读取已验证 MAPDL 二进制路径。
    launch_argv = [str(value) for value in validated["launch_argv"]]  # 复制冻结参数数组，后续不得重新拼接或修改。
    monitor_path = (run_dir / MONITOR_RELATIVE).resolve()  # 定位已经由准备账本保护的专用监控器快照。
    monitor_argv = [str(Path(sys.executable).resolve()), "-B", str(monitor_path), "--run-dir", str(run_dir)]  # 构造由当前批准 Python 自动启动冻结监控器的唯一参数数组。
    claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领文件。
    launch_path = run_dir / "runtime_launch.json"  # 定位 MAPDL Popen 后最小真实 PID 记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位 MAPDL Popen 后增强创建时刻、二进制和命令身份记录。
    identity_failure_path = run_dir / "runtime_process_identity_failure.json"  # 定位仅在增强身份失败时生成的故障证据。
    prelaunch_failure_path = run_dir / "runtime_prelaunch_failure.json"  # 定位取得租约后第二次进程或资源门失败的证据。
    popen_failure_path = run_dir / "runtime_popen_failure.json"  # 定位 MAPDL 创建调用未返回进程对象时的故障证据。
    monitor_spawn_claim_path = run_dir / MONITOR_SPAWN_CLAIM_RELATIVE  # 定位监控器自动创建前的认领文件。
    monitor_launch_path = run_dir / MONITOR_LAUNCH_RELATIVE  # 定位监控器 Popen 后真实 PID 记录。
    monitor_attachment_path = run_dir / MONITOR_ATTACHMENT_RELATIVE  # 定位监控器 claim 握手成功证据。
    monitor_attachment_failure_path = run_dir / "runtime_monitor_attachment_failure.json"  # 定位监控器创建、退出、超时或 claim 漂移故障证据。
    runtime_paths = [claim_path, launch_path, identity_path, identity_failure_path, prelaunch_failure_path, popen_failure_path, monitor_spawn_claim_path, monitor_launch_path, monitor_attachment_path, monitor_attachment_failure_path]  # 汇总本启动器可能创建的全部根级运行工件。
    require(not any(path.exists() for path in runtime_paths), "A0 启动或监控工件在复核后出现，禁止并发或重复启动")  # 关闭检查到使用时间窗中的目录竞争。
    first_conflicts = runtime_base.active_solver_processes()  # 在取得全局租约前执行第一次真实 MAPDL/MPI 进程扫描。
    first_memory = psutil.virtual_memory()  # 在取得租约前读取第一次可用物理内存快照。
    first_disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 在取得租约前读取第一次运行盘空余快照。
    require(not first_conflicts and int(first_memory.available) >= MINIMUM_RAM_BYTES and int(first_disk.free) >= MINIMUM_DISK_BYTES, f"A0 第一次临启动进程或资源门失败：{first_conflicts}")  # 第一次扫描、四 GiB 内存或二十四 GiB 磁盘任一失败都保持零启动和零租约。
    require(not HOST_LEASE_PATH.exists(), f"A0 全局主机租约已存在：{HOST_LEASE_PATH}")  # 在排他创建前给出明确占用原因但不读取或改写他人租约。
    lease_payload = {"schema_version": 1, "status": "A0_EXCLUSIVE_HOST_LEASE_HELD", "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "acquired_at_utc": datetime.now(timezone.utc).isoformat(), "launcher_pid": os.getpid(), "launcher_script": str(Path(__file__).resolve()), "launcher_script_sha256": runtime_base.sha256_file(Path(__file__).resolve()), "manifest_sha256": runtime_base.sha256_file(run_dir / "manifest.json"), "first_solver_scan": first_conflicts, "active_process_disposition_allowed": False}  # 冻结租约持有者、输入身份、第一次空扫描与禁止强制处置边界。
    runtime_base.write_json(HOST_LEASE_PATH, lease_payload)  # 在第一次空扫描后以操作系统排他创建取得跨运行唯一主机租约。
    lease_sha256 = runtime_base.sha256_file(HOST_LEASE_PATH)  # 计算刚取得租约的完整字节摘要供启动、监控与释放三方闭合。
    second_conflicts = runtime_base.active_solver_processes()  # 在租约持有期间、MAPDL Popen 紧前执行第二次真实求解进程扫描。
    second_memory = psutil.virtual_memory()  # 在 MAPDL Popen 紧前重新读取可用物理内存。
    second_disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 在 MAPDL Popen 紧前重新读取运行盘空余。
    if second_conflicts or int(second_memory.available) < MINIMUM_RAM_BYTES or int(second_disk.free) < MINIMUM_DISK_BYTES:  # 第二次进程、内存或磁盘门任一失败时进入零 MAPDL 启动故障路径。
        release = archive_and_release_host_lease(run_dir, lease_sha256, "runtime_a0_host_lease_prelaunch_release.json", "SECOND_SOLVER_OR_RESOURCE_SCAN_FAILED_BEFORE_MAPDL_POPEN", False)  # 在没有进程需要等待时封存并释放本运行租约。
        failure = {"schema_version": 1, "status": "PRELAUNCH_SECOND_SCAN_FAILED_HOST_LEASE_RELEASED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "first_solver_scan": first_conflicts, "second_solver_scan": second_conflicts, "physical_memory_available_bytes": int(second_memory.available), "disk_free_bytes": int(second_disk.free), "required_memory_bytes": MINIMUM_RAM_BYTES, "required_disk_bytes": MINIMUM_DISK_BYTES, "host_lease_release": release, "mapdl_execution_attempted": False, "mapdl_started": False}  # 保存第二门失败、实测资源、零启动和租约释放证据。
        runtime_base.write_json(prelaunch_failure_path, failure)  # 以排他创建提交不可复用的预启动故障终态。
        raise RuntimeError("A0 第二次求解器或资源扫描失败；MAPDL 未启动且主机租约已封存释放")  # 向调用者报告精确零启动结论。
    started_at = datetime.now(timezone.utc)  # 记录启动认领与 MAPDL Popen 共用的精确 UTC 时刻。
    manifest_sha256 = runtime_base.sha256_file(run_dir / "manifest.json")  # 计算账本保护的清单摘要供启动链闭合。
    ledger_sha256 = runtime_base.sha256_file(run_dir / "artifact_hashes.sha256")  # 计算准备账本自身摘要供认领、PID 与监控三方闭合。
    prelaunch_resources = {"physical_memory_total_bytes": int(second_memory.total), "physical_memory_available_bytes": int(second_memory.available), "formal_8_gib_gate_passed": int(second_memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_gate_passed": True, "disk_free_bytes": int(second_disk.free), "disk_24_gib_gate_passed": True, "disk_gate_historical_largest_package_gib": HISTORICAL_LARGEST_C10_PACKAGE_GIB, "disk_gate_multiplier": DISK_GATE_MULTIPLIER, "first_solver_scan": first_conflicts, "second_solver_scan": second_conflicts, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256}  # 冻结真实进程创建前的双扫描、资源、二十四 GiB 历史证据门和租约身份。
    claim = {"schema_version": 1, "status": "LAUNCH_CLAIMED_NOT_YET_STARTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "claimed_at_utc": started_at.isoformat(), "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": ledger_sha256, "prepared_ledger_entry_count": int(validated["ledger_entry_count"]), "prelaunch_resources": prelaunch_resources, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256, "double_solver_scan_completed": True, "monitor_auto_start_required": True, "monitor_attachment_timeout_seconds": MONITOR_ATTACHMENT_TIMEOUT_SECONDS, "postlaunch_unrelated_solver_process_is_hard_event": True, "production_claim_allowed": False}  # 在 MAPDL Popen 前冻结唯一启动权、双扫描、租约、自动监控与非生产边界。
    try:  # 启动认领写盘失败发生在 MAPDL Popen 前，必须封存释放已经取得的主机租约。
        runtime_base.write_json(claim_path, claim)  # 以排他创建提交启动认领；成功后任何失败均禁止同目录重试。
    except Exception as claim_error:  # 捕获排他竞争、磁盘或序列化异常并保持零 MAPDL 启动。
        release = archive_and_release_host_lease(run_dir, lease_sha256, "runtime_a0_host_lease_launch_claim_failure_release.json", "LAUNCH_CLAIM_WRITE_FAILED_BEFORE_MAPDL_POPEN", False)  # 在无进程需要等待时封存并释放租约。
        failure = {"schema_version": 1, "status": "LAUNCH_CLAIM_WRITE_FAILED_HOST_LEASE_RELEASED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "error_type": type(claim_error).__name__, "error_message": str(claim_error), "host_lease_release": release, "mapdl_execution_attempted": False, "mapdl_started": False}  # 保存认领写盘失败、零启动和租约释放证据。
        runtime_base.write_json(prelaunch_failure_path, failure)  # 以排他创建提交不可复用的认领前故障终态。
        raise RuntimeError("A0 启动认领写盘失败；MAPDL 未启动且主机租约已封存释放") from claim_error  # 向调用者保留原始写盘异常谱系。
    claim_sha256 = runtime_base.sha256_file(claim_path)  # 计算已经落盘的不可覆盖认领摘要。
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 使用无窗口批处理标志；回退零值只保持非 Windows 语法兼容。
    try:  # MAPDL 创建调用本身可能因许可、路径或操作系统错误失败且没有可等待进程对象。
        process = subprocess.Popen(launch_argv, cwd=solver_dir, creationflags=creation_flags)  # 在全部门通过后创建一次且仅一次 MAPDL 进程。
    except Exception as popen_error:  # 捕获尚未取得 MAPDL 进程对象的创建失败并释放本运行租约。
        release = archive_and_release_host_lease(run_dir, lease_sha256, "runtime_a0_host_lease_popen_failure_release.json", "MAPDL_POPEN_DID_NOT_RETURN_PROCESS", False)  # 在无已知 MAPDL 进程可等待时封存并释放租约。
        failure = {"schema_version": 1, "status": "MAPDL_POPEN_FAILED_HOST_LEASE_RELEASED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "error_type": type(popen_error).__name__, "error_message": str(popen_error), "host_lease_release": release, "mapdl_execution_attempted": True, "mapdl_started": False}  # 保存创建尝试、无进程对象、错误和租约释放证据。
        runtime_base.write_json(popen_failure_path, failure)  # 以排他创建提交 MAPDL 创建故障终态。
        raise RuntimeError("A0 MAPDL Popen 失败；未取得进程对象且主机租约已封存释放") from popen_error  # 向调用者保留原始异常谱系。
    launch_record = {"schema_version": 1, "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "started_at_utc": started_at.isoformat(), "main_pid": int(process.pid), "process_identity_path": identity_path.name, "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": ledger_sha256, "prepared_ledger_entry_count": int(validated["ledger_entry_count"]), "launch_claim_sha256": claim_sha256, "prelaunch_resources": prelaunch_resources, "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256, "monitor_hard_stops": {"available_ram_below_bytes": MONITOR_RAM_IMMEDIATE_BYTES, "available_ram_below_1_gib_sustained_seconds": MONITOR_RAM_SUSTAINED_SECONDS, "disk_free_below_bytes": MONITOR_DISK_BYTES}, "postlaunch_unrelated_solver_process_is_hard_event": True, "production_claim_allowed": False}  # MAPDL Popen 后立即冻结最小 PID、参数、租约、谱系和监控阈值记录。
    try:  # 最小 PID 记录或增强身份任一失败都必须提交官方 ABT 并等待自然退出。
        runtime_base.write_json(launch_path, launch_record)  # 在任何增强身份读取前排他提交最小真实 PID 记录。
        process_identity = psutil.Process(process.pid)  # 按 Popen 返回 PID 获取操作系统进程对象。
        create_time = float(process_identity.create_time())  # 冻结进程创建时刻以阻断 PID 回收误附着。
        actual_executable = str(Path(process_identity.exe()).resolve())  # 冻结操作系统报告的真实二进制规范路径。
        actual_command_line = [str(value) for value in process_identity.cmdline()]  # 冻结操作系统报告的真实参数数组。
        require(Path(actual_executable).resolve() == executable and actual_command_line == launch_argv, "A0 Popen 后真实二进制或命令行与冻结值不一致")  # 只有完全一致才允许监控器附着。
        identity = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURED", "run_name": run_dir.name, "jobname": manifest["jobname"], "captured_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_launch_sha256": runtime_base.sha256_file(launch_path), "pid": int(process.pid), "create_time_epoch_seconds": create_time, "executable": actual_executable, "command_line": actual_command_line}  # 汇总防 PID 回收的增强身份。
        runtime_base.write_json(identity_path, identity)  # 以排他创建提交增强身份供专用监控器三方核验。
    except Exception as identity_error:  # 捕获身份读取、比较或排他写入的全部异常并进入原生安全中止路径。
        fallback_identity = {"pid": int(process.pid), "create_time_epoch_seconds": started_at.timestamp()}  # 构造只供 job 参数归属回退的最小身份，绝不把它冒充增强身份成功。
        abort_evidence = write_native_abort(solver_dir, str(manifest["jobname"]))  # 只提交本 job 官方十字节 ABT，不调用 terminate、kill 或信号接口。
        natural_exit = wait_for_natural_job_exit(solver_dir, str(manifest["jobname"]), fallback_identity)  # 在租约处置前限时等待本 job 空进程、无锁和 OUT/ERR/MNTR 连续稳定。
        release_allowed = bool(natural_exit.get("host_lease_release_allowed"))  # 读取完整稳定退出门而不是只凭两次空进程样本判断。
        release = archive_and_release_host_lease(run_dir, lease_sha256, "runtime_a0_host_lease_identity_failure_release.json", "MAIN_PROCESS_IDENTITY_CAPTURE_FAILED_AFTER_NATIVE_ABORT_AND_STABLE_NATURAL_EXIT", True) if release_allowed else {"host_lease_removed": False, "retained_for_manual_audit": True, "reason": "NATURAL_EXIT_LOCK_AND_OUTPUT_STABILITY_NOT_CONFIRMED", "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256}  # 仅完整稳定退出后释放；超时或不确定时保留租约阻止后继运行。
        failure = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_OR_RUNTIME_LAUNCH_RECORD_FAILED_NATIVE_ABORT_TERMINAL_AUDIT_RECORDED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "runtime_launch_sha256": runtime_base.sha256_file(launch_path) if launch_path.is_file() else None, "error_type": type(identity_error).__name__, "error_message": str(identity_error), "native_abort": abort_evidence, "natural_exit": natural_exit, "host_lease_release_allowed": release_allowed, "manual_audit_required": not release_allowed, "host_lease_release": release, "terminate_called": False, "kill_called": False}  # 保存已启动事实、故障、官方 ABT、完整退出门和租约释放或保留证据。
        runtime_base.write_json(identity_failure_path, failure)  # 以排他创建提交身份故障终态，禁止目录被误当作未启动。
        raise RuntimeError("A0 MAPDL 已启动但增强身份失败；已提交官方十字节 ABT，租约仅在空进程、无锁且输出稳定后释放，否则保留供人工审计") from identity_error  # 向调用者明确报告部分启动和条件化租约处置事实。
    monitor_spawn_claim = {"schema_version": 1, "status": "MONITOR_AUTO_SPAWN_CLAIMED_NOT_YET_STARTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "claimed_at_utc": datetime.now(timezone.utc).isoformat(), "launcher_pid": os.getpid(), "monitor_argv": monitor_argv, "monitor_script_sha256": runtime_base.sha256_file(monitor_path), "runtime_launch_sha256": runtime_base.sha256_file(launch_path), "runtime_process_identity_sha256": runtime_base.sha256_file(identity_path), "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256, "attachment_timeout_seconds": MONITOR_ATTACHMENT_TIMEOUT_SECONDS, "postlaunch_unrelated_solver_process_is_hard_event": True, "active_process_disposition_allowed": False}  # 在监控器 Popen 前冻结自动启动权、参数、MAPDL 身份、租约与硬事件政策。
    monitor_process: subprocess.Popen[Any] | None = None  # 初始化监控器进程对象，以便故障路径区分尚未创建和已经创建。
    try:  # 自动监控器认领、创建、claim 提交或握手核验任一失败都必须中止本 A0 job。
        runtime_base.write_json(monitor_spawn_claim_path, monitor_spawn_claim)  # 以排他创建提交监控器自动创建前认领，供子进程证明不是人工补挂。
        monitor_spawn_claim_sha256 = runtime_base.sha256_file(monitor_spawn_claim_path)  # 计算不可覆盖自动创建认领摘要供双向握手。
        monitor_process = subprocess.Popen(monitor_argv, cwd=run_dir, creationflags=creation_flags)  # 使用当前批准 Python 自动创建一次且仅一次冻结专用监控器。
        monitor_launch = {"schema_version": 1, "status": "MONITOR_PROCESS_STARTED_CLAIM_PENDING", "run_name": run_dir.name, "jobname": manifest["jobname"], "started_at_utc": datetime.now(timezone.utc).isoformat(), "monitor_pid": int(monitor_process.pid), "monitor_argv": monitor_argv, "monitor_spawn_claim_sha256": monitor_spawn_claim_sha256, "host_lease_sha256": lease_sha256}  # 冻结监控器真实 PID、参数、认领和租约身份。
        runtime_base.write_json(monitor_launch_path, monitor_launch)  # 在等待 claim 前排他提交监控器真实 PID 记录。
        deadline = time.monotonic() + MONITOR_ATTACHMENT_TIMEOUT_SECONDS  # 计算三十秒 claim 握手单调时钟截止点。
        monitor_claim_path = run_dir / MONITOR_CLAIM_RELATIVE  # 定位监控器完成链验证和本 job 附着后提交的排他 claim。
        monitor_claim: dict[str, Any] | None = None  # 初始化尚未读到有效监控 claim 的状态。
        while time.monotonic() < deadline:  # 在批准窗口内轮询 claim 和监控器退出码。
            if monitor_claim_path.is_file():  # 监控器已经提交 claim 时立即读取并闭合双向身份。
                candidate_claim = runtime_base.load_json(monitor_claim_path)  # 读取监控器不可覆盖 claim 对象。
                require(candidate_claim.get("status") == "A0_MONITOR_CLAIMED" and candidate_claim.get("run_name") == run_dir.name and candidate_claim.get("jobname") == manifest["jobname"], "A0 监控 claim 状态、运行或 job 身份错误")  # 固定 claim 语义和目标。
                require(int(candidate_claim.get("monitor_pid", 0)) == int(monitor_process.pid) and candidate_claim.get("monitor_spawn_claim_sha256") == monitor_spawn_claim_sha256, "A0 监控 claim PID 或自动创建认领摘要不一致")  # 证明 claim 来自本启动器刚创建的专用监控器。
                require(candidate_claim.get("host_lease_sha256") == lease_sha256 and candidate_claim.get("monitor_script_sha256") == runtime_base.sha256_file(monitor_path), "A0 监控 claim 租约或脚本摘要不一致")  # 关闭跨租约或可编辑脚本冒领。
                require(monitor_process.poll() is None, "A0 监控器提交 claim 后已提前退出")  # 握手成功时要求专用监控器仍在持续附着。
                monitor_claim = candidate_claim  # 保存已经全部闭合的有效 claim 并结束轮询。
                break  # 退出握手等待循环并提交附件证据。
            monitor_return_code = monitor_process.poll()  # 在 claim 尚未出现时只读检查监控器是否已经退出。
            require(monitor_return_code is None, f"A0 监控器在 claim 前退出，返回码 {monitor_return_code}")  # 任何提前退出都进入官方 ABT 故障路径。
            time.sleep(MONITOR_ATTACHMENT_POLL_SECONDS)  # 每零点二五秒重试且不超过三十秒总窗口。
        require(monitor_claim is not None, f"A0 监控器未在 {MONITOR_ATTACHMENT_TIMEOUT_SECONDS:.0f} 秒内提交有效 claim")  # 超时必须 fail-closed 并触发本 job 官方 ABT。
        attachment = {"schema_version": 1, "status": "MONITOR_AUTO_STARTED_AND_ATTACHMENT_CLAIM_VERIFIED", "run_name": run_dir.name, "jobname": manifest["jobname"], "attached_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "monitor_pid": int(monitor_process.pid), "monitor_spawn_claim_sha256": monitor_spawn_claim_sha256, "monitor_launch_sha256": runtime_base.sha256_file(monitor_launch_path), "monitor_claim_sha256": runtime_base.sha256_file(monitor_claim_path), "host_lease_sha256": lease_sha256, "monitor_process_alive_at_attachment": True, "monitor_owns_terminal_host_lease_release": True}  # 冻结自动创建、claim 有效、进程存活与终态租约所有权事实。
        runtime_base.write_json(monitor_attachment_path, attachment)  # 以排他创建提交启动器等待成功的双向握手证据。
    except Exception as monitor_error:  # 捕获监控器 Popen、PID 记录、提前退出、claim 漂移或超时全部故障。
        abort_evidence = write_native_abort(solver_dir, str(manifest["jobname"]))  # 只向本 A0 job 写入精确十字节官方 ABT，绝不处理任何其他进程。
        natural_exit = wait_for_natural_job_exit(solver_dir, str(manifest["jobname"]), identity)  # 在租约处置前限时等待本 job 空进程、无锁和 OUT/ERR/MNTR 连续稳定。
        release_allowed = bool(natural_exit.get("host_lease_release_allowed"))  # 读取完整稳定退出证据决定启动器异常释放权限。
        release = archive_and_release_host_lease(run_dir, lease_sha256, "runtime_a0_host_lease_monitor_attachment_failure_release.json", "MONITOR_AUTO_START_OR_ATTACHMENT_FAILED_AFTER_NATIVE_ABORT_AND_STABLE_NATURAL_EXIT", True) if release_allowed and HOST_LEASE_PATH.is_file() else ({"host_lease_removed": True, "release_reason": "MONITOR_ALREADY_RELEASED_LEASE_BEFORE_LAUNCHER_EXCEPTION_PATH"} if release_allowed else {"host_lease_removed": False, "retained_for_manual_audit": True, "reason": "NATURAL_EXIT_LOCK_AND_OUTPUT_STABILITY_NOT_CONFIRMED", "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256})  # 完整稳定退出才释放或接受已释放；超时或不确定时保留现有租约供人工审计。
        failure = {"schema_version": 1, "status": "MONITOR_AUTO_START_OR_ATTACHMENT_FAILED_NATIVE_ABORT_TERMINAL_AUDIT_RECORDED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "monitor_pid": None if monitor_process is None else int(monitor_process.pid), "error_type": type(monitor_error).__name__, "error_message": str(monitor_error), "native_abort": abort_evidence, "natural_exit": natural_exit, "host_lease_release_allowed": release_allowed, "manual_audit_required": not release_allowed, "host_lease_release": release, "terminate_called": False, "kill_called": False, "send_signal_called": False}  # 保存自动监控故障、官方 ABT、完整退出门、租约释放或保留及无强制处置证据。
        runtime_base.write_json(monitor_attachment_failure_path, failure)  # 以排他创建提交监控握手故障终态，禁止同目录重试。
        raise RuntimeError("A0 MAPDL 已启动但自动监控器未完成有效握手；已提交官方 ABT，租约仅在空进程、无锁且输出稳定后释放，否则保留供人工审计") from monitor_error  # 向调用者保留原始监控故障谱系和条件化租约边界。
    return {"run_dir": str(run_dir), "mapdl_pid": int(process.pid), "monitor_pid": int(monitor_process.pid), "status": "RUNNING_DIAGNOSTIC_MONITOR_AUTO_STARTED_AND_ATTACHED", "monitor_attachment_path": str(monitor_attachment_path), "monitor_claim_path": str(run_dir / MONITOR_CLAIM_RELATIVE), "host_lease_path": str(HOST_LEASE_PATH), "host_lease_sha256": lease_sha256, "monitor_owns_terminal_host_lease_release": True, "mapdl_execution_attempted": True, "mapdl_started": True}  # 返回 MAPDL、自动监控器、握手和终态租约所有权的紧凑事实。


def parse_args() -> argparse.Namespace:  # 无业务输入；解析离线自检或目标运行加只读/启动互斥动作并返回命名空间。
    parser = argparse.ArgumentParser(description="只读复核或显式启动已准备的 C10 A0 静力诊断；默认不执行任何动作。")  # 建立不允许隐式启动的命令行接口。
    parser.add_argument("--run-dir", required=False, type=Path, help="正常模式下必填的唯一 A0 运行绝对目录。")  # 要求调用者显式指定目标，禁止自动选择 latest。
    parser.add_argument("--self-test", action="store_true", help="仅在内存和系统临时目录验证源码与官方 ABT，不读取或写入任何 A0 运行。")  # 提供完全离线回归入口。
    action = parser.add_mutually_exclusive_group()  # 建立只读复核与实际启动互斥动作组。
    action.add_argument("--validate-only", action="store_true", help="只读复核包、deck、当前并发和资源，不创建 runtime 文件、不启动 MAPDL。")  # 推荐先执行的零启动动作。
    action.add_argument("--launch", action="store_true", help="仅在另行明确授权后创建启动认领并启动一次 MAPDL。")  # 把有状态动作放在显式开关后。
    return parser.parse_args()  # 返回由 argparse 拒绝未知或冲突参数后的命名空间。


def main() -> None:  # 解析模式并执行一次离线自检、只读复核或明确启动，无业务返回值。
    arguments = parse_args()  # 读取已经完成语法和互斥检查的命令行参数。
    if bool(arguments.self_test):  # 离线自检必须在任何运行目录解析前短路。
        require(arguments.run_dir is None and not arguments.validate_only and not arguments.launch, "A0 启动器自检禁止同时提供运行目录或动作")  # 防止自检携带真实目标造成误解。
        print(json.dumps(offline_self_test(), ensure_ascii=False, allow_nan=False))  # 输出单行机器自检结果。
        return  # 自检完成后立即退出，Popen 分支不可达。
    require(arguments.run_dir is not None, "A0 正常模式必须显式提供 --run-dir")  # 非自检模式禁止猜测目标运行。
    require(bool(arguments.validate_only) or bool(arguments.launch), "A0 正常模式必须显式选择 --validate-only 或 --launch")  # 默认无动作，避免误双击启动。
    validated = validate_run(arguments.run_dir)  # 无论只读或启动都先执行同一完整包、控制和资源复核。
    if bool(arguments.validate_only):  # 只读模式不得创建认领、PID、ABT 或任何 solver 输出。
        printable = {key: value for key, value in validated.items() if key not in {"manifest", "root_status", "solver_dir", "main_path", "executable", "launch_argv"}}  # 删除仅供内部启动使用的对象和长参数以保持输出紧凑。
        print(json.dumps(printable, ensure_ascii=False, allow_nan=False))  # 输出包有效性、冲突和资源现状且明确零启动。
        return  # 只读复核结束后立即退出，实际启动分支不可达。
    print(json.dumps(launch(validated), ensure_ascii=False, allow_nan=False))  # 只有显式 --launch 才调用唯一 Popen 创建点并输出真实 PID。


if __name__ == "__main__":  # 仅在直接执行本冻结脚本时解析动作，导入帮助函数时不读取或启动任何运行。
    main()  # 执行一次离线自检、只读启动前复核或明确实际启动。
