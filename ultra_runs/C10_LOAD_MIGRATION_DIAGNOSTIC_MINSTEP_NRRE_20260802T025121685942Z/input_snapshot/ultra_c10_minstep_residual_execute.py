from __future__ import annotations  # 启用延迟类型注解，避免运行时解析复杂注解产生额外依赖。

import argparse  # 解析调用者明确给出的唯一运行目录，禁止自动选择 latest 或猜测路径。
import hashlib  # 计算官方原生中止载荷与运行工件的 SHA-256 身份。
import json  # 输出机器可读的启动摘要，详细字段由运行包字段字典解释。
import os  # 在极少见的启动后身份捕获失败路径中强制把原生中止请求刷入磁盘。
import subprocess  # 以独立无窗口进程启动唯一 MAPDL 最小增量残差诊断。
from datetime import datetime, timezone  # 生成带时区 UTC 启动、认领和故障时间。
from pathlib import Path  # 安全处理包含中文的绝对工程路径和运行内相对路径。
from typing import Any  # 标注 JSON 字典允许容纳的异构审计值。

import psutil  # 读取物理内存、磁盘和 Popen 后的真实进程身份。

import ultra_c10_static_execute as runtime_base  # 复用已验证的准备账本、资源冲突和参数解析基础函数，不调用其主流程。


RUNS_ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs")  # 冻结唯一允许启动的不可覆盖运行根目录，避免源目录与 input_snapshot 层级不同造成误解析。
RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_MINSTEP_NRRE_"  # 只批准最小 0.05% 迁移残差运行目录族。
DIAGNOSTIC_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_FIRST_0_05_PERCENT_NRRE_ENDPOINT"  # 冻结专用启动器唯一接受的诊断子类型。
DIAGNOSTIC_CHANGE_SET = "FULL_LS1_THEN_FIXED_SINGLE_0_05_PERCENT_LS2_WITH_NRRE_MAXFILE_50"  # 冻结多命令但单一物理增量的受控诊断变更集。
MINIMUM_RAM_BYTES = 4 * 1024**3  # 诊断例外启动要求至少四 GiB 可用物理内存，不能替代正式八 GiB 门。
FORMAL_RAM_BYTES = 8 * 1024**3  # 记录正式全桥既定八 GiB 可用物理内存门，单位 byte。
MINIMUM_DISK_BYTES = 50 * 1024**3  # 启动时要求运行盘至少五十 GiB 空余，单位 byte。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 按 MAPDL 官方 ABT 合同固定第一列以 nonlinear 开头并带唯一 LF 的十字节载荷。
NATIVE_ABORT_PAYLOAD_SHA256 = hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest()  # 冻结十字节官方原生中止载荷的可审计摘要。


def require(condition: bool, message: str) -> None:  # 输入布尔门和失败说明；门失败时阻断启动且无业务返回值。
    if not condition:  # 仅在身份、谱系、命令、资源或排他性不满足时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常并保证 Popen 之前的失败不创建求解进程。


def executable_apdl_lines(text: str) -> list[str]:  # 输入完整 APDL 文本并返回去除说明、空行和标题后的规范大写命令序列。
    commands: list[str] = []  # 初始化保持原先后关系的可执行命令列表。
    for line in text.splitlines():  # 按真实行顺序扫描整个主控，禁止局部抽样漏掉隐藏命令。
        executable = line.split("!", maxsplit=1)[0].strip()  # 删除 APDL 行内说明并去除显示空白。
        if not executable or executable.upper().startswith("/TITLE,"):  # 空行、整行说明和运行身份标题不属于数值合同。
            continue  # 跳过非执行内容并继续扫描下一行。
        commands.append(executable.upper().replace(" ", ""))  # 规范大小写与普通空格但保留字段、数值和顺序。
    return commands  # 返回供精确计数和禁止项核验的完整执行序列。


def request_native_abort(solver_dir: Path, jobname: str) -> tuple[Path, str]:  # 输入工作目录和作业名并排他写出经过回读验证的官方 ABT 载荷。
    abort_path = solver_dir / f"{jobname}.abt"  # 按 MAPDL 约定构造只属于当前作业的原生中止文件。
    if abort_path.exists():  # 既有文件可能来自并发控制动作，禁止覆盖其时间和字节证据。
        require(abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "既有 ABT 不是官方 nonlinear 十字节载荷")  # 只接受完全相同的幂等原生请求。
        return abort_path, "VALID_NATIVE_ABORT_ALREADY_EXISTED"  # 返回已存在且通过字节门的动作说明。
    with abort_path.open("xb") as handle:  # 使用二进制排他创建，避免文本换行转换或两个控制器覆盖。
        written = handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入精确十字节载荷，第一列第一词为 nonlinear。
        require(written == len(NATIVE_ABORT_PAYLOAD), "ABT 原生中止载荷未完整写入")  # 阻断短写造成的无效请求。
        handle.flush()  # 把 Python 缓冲区内容提交给操作系统。
        os.fsync(handle.fileno())  # 强制持久化文件内容，使故障证据先于异常返回落盘。
    require(abort_path.read_bytes() == NATIVE_ABORT_PAYLOAD, "ABT 原生中止载荷回读不一致")  # 用独立回读关闭写入后的字节身份。
    return abort_path, "VALID_NATIVE_ABORT_CREATED_AND_FSYNCED"  # 返回新建且已刷盘的官方请求动作说明。


def main() -> None:  # 解析唯一运行、复算准备账本和专用命令门并异步启动一次 MAPDL，无业务返回值。
    parser = argparse.ArgumentParser(description="启动已准备的 C10 最小增量 NRRE 残差诊断")  # 建立只接受运行目录的专用命令行接口。
    parser.add_argument("--run-dir", required=True, type=Path, help="唯一 C10 最小增量 NRRE 准备运行绝对目录")  # 要求显式目标，禁止默认选择或目录复用。
    arguments = parser.parse_args()  # 解析参数并由 argparse 拒绝缺失和未知选项。
    run_dir = arguments.run_dir.resolve()  # 规范化目标绝对路径，消除相对段歧义。
    require(run_dir.is_dir() and run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs：{run_dir}")  # 只允许项目运行根的直接子目录。
    require(run_dir.name.startswith(RUN_PREFIX), f"运行目录不属于最小增量 NRRE 族：{run_dir.name}")  # 阻断其他静力、模态或历史运行借用本合同。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领文件。
    runtime_launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后立即写出的真实 PID 记录。
    process_identity_path = run_dir / "runtime_process_identity.json"  # 定位 Popen 后增强进程身份记录。
    require(not launch_claim_path.exists() and not runtime_launch_path.exists() and not process_identity_path.exists(), "运行已存在启动认领、PID 或进程身份，禁止重复启动")  # 关闭同目录双启动和结果覆盖路径。
    manifest_path = run_dir / "manifest.json"  # 定位准备器冻结的完整运行清单。
    status_path = run_dir / "C10_static_status.json"  # 定位根级准备状态与诊断启动权限。
    manifest = runtime_base.load_json(manifest_path)  # 读取机器清单并验证顶层对象结构。
    root_status = runtime_base.load_json(status_path)  # 独立读取根状态，避免只修改一份权限工件。
    require(manifest.get("run_name") == run_dir.name and root_status.get("run_name") == run_dir.name, "清单或根状态运行名与目录不一致")  # 关闭跨目录复制错配。
    require(manifest.get("jobname") == root_status.get("jobname"), "清单与根状态 jobname 不一致")  # 固定唯一结果文件族身份。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "运行不是可启动的准备态")  # 只接受未运行准备包。
    require(root_status.get("launch_allowed_for_diagnostic") is True and root_status.get("mapdl_execution_attempted") is False and root_status.get("mapdl_started") is False, "根状态未明确允许首次诊断启动")  # 作废、已尝试或已启动状态一律拒绝。
    require(manifest.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE and root_status.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE, "启动链诊断子类型不是最小 0.05% NRRE")  # 阻断其他荷载路径借用本启动器。
    require(manifest.get("diagnostic_change_set") == DIAGNOSTIC_CHANGE_SET, "清单受控诊断变更集漂移")  # 固定完整 LS1 加唯一最小 LS2 增量范围。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and manifest.get("static_result_expected") is False, "清单未关闭模态、生产或完整静力结论")  # 确认只允许定位用途。
    prepared_entries = runtime_base.verify_prepared_ledger(run_dir)  # 在临近 Popen 时逐项复算准备阶段完整哈希账本。
    require(len(prepared_entries) >= 30, "最小增量准备账本条目异常不足三十项")  # 要求父输入、修正向量、QA 和三段运行代码均受保护。
    launcher_relative = str(manifest.get("runtime_execute_script", "")).replace("\\", "/")  # 读取清单冻结的专用启动器运行内路径。
    monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 读取清单冻结的专用监控器运行内路径。
    require(launcher_relative == "input_snapshot/ultra_c10_minstep_residual_execute.py", "清单专用启动器快照路径错误")  # 固定本文件在运行内的唯一位置。
    require(monitor_relative == "input_snapshot/ultra_c10_minstep_residual_monitor.py", "清单专用监控器快照路径错误")  # 固定后续监控入口位置。
    require(Path(__file__).resolve() == (run_dir / launcher_relative).resolve(), "实际调用的启动器不是本运行冻结快照")  # 禁止从可继续编辑的工具源启动已准备包。
    require(launcher_relative in prepared_entries and monitor_relative in prepared_entries, "准备账本未冻结专用启动器或监控器")  # 关闭运行代码脱离准备谱系的路径。
    require(runtime_base.sha256_file(Path(__file__).resolve()) == str(manifest.get("runtime_execute_script_sha256")) == prepared_entries[launcher_relative], "专用启动器当前字节、清单和账本摘要不一致")  # 三方闭合启动代码身份。
    require(runtime_base.sha256_file(run_dir / monitor_relative) == str(manifest.get("runtime_monitor_script_sha256")) == prepared_entries[monitor_relative], "专用监控器当前字节、清单和账本摘要不一致")  # 三方闭合监控代码身份。
    required_qa = ["qa/load_position_migration_audit.json", "qa/minstep_residual_control_audit.json", "qa/upstream_authorization_reference.json", "qa/micro_validation_reference.json"]  # 冻结启动前必须存在的四项物理、数值与谱系 QA 工件。
    require(all(relative in prepared_entries for relative in required_qa), "准备账本缺少迁移守恒、最小步控制、授权或微验证证据")  # 阻断证据不完整的输入。
    solver_dir = run_dir / "solver"  # 定位本运行独立 MAPDL 工作目录。
    main_input = run_dir / str(manifest.get("main_input"))  # 按清单定位唯一主输入文件。
    executable = Path(str(manifest.get("mapdl_executable")))  # 按清单定位冻结 MAPDL 2026 R1 可执行文件。
    require(main_input.is_file() and main_input.parent.resolve() == solver_dir.resolve(), "主输入缺失或越出本运行 solver 目录")  # 防止跨运行入口污染。
    require(executable.is_file(), f"冻结 MAPDL 可执行文件缺失：{executable}")  # 在启动前关闭求解器存在性门。
    require(runtime_base.sha256_file(main_input) == str(manifest.get("main_input_sha256")), "主输入 SHA-256 与清单不一致")  # 拒绝准备后人工修改 deck。
    require(runtime_base.sha256_file(executable) == str(manifest.get("mapdl_executable_sha256")), "MAPDL 可执行文件 SHA-256 漂移")  # 拒绝未登记求解器替换。
    main_text = main_input.read_text(encoding="utf-8")  # 读取短主控供最后一次命令级专项门禁。
    commands = executable_apdl_lines(main_text)  # 生成排除说明和标题的完整规范命令序列。
    require(commands.count("SOLVE") == 2 and commands.count("KBC,1") == 1 and commands.count("KBC,0") == 1, "主控不是完整 LS1 加单个 LS2 的两步合同")  # 固定两次求解和端点插值边界。
    require(commands.count("C10_BETA=1") == 1 and commands.count("C10_BETA=0.9995") == 1 and "C10_BETA=0" not in commands, "beta 端点不是 1→0.9995")  # 确认只迁移完整路径的万分之五。
    require(commands.count("TIME,1") == 1 and commands.count("TIME,1.0000005") == 1 and "TIME,1.001" not in commands, "伪时间端点不是 1→1.0000005")  # 固定最小增量与原 0.001 路径尺度的对应关系。
    require(commands.count("AUTOTS,OFF") == 2 and "AUTOTS,ON" not in commands and commands.count("NSUBST,1,1,1") == 2, "LS1/LS2 未同时固定为单子步且关闭自动切分")  # 禁止隐藏 cutback 改变诊断端点。
    require(commands.count("NLDIAG,NRRE,ON,50") == 1 and not any(command.startswith("NLDIAG,EFLG") for command in commands), "NRRE MAXFILE=50 不唯一或混入 EFLG")  # 固定唯一残差输出族并控制磁盘文件数。
    require(sum(1 for command in commands if command.startswith("CNVTOL,")) == 4 and "STABILIZE,ON" not in commands, "四项收敛标准或无稳定化合同漂移")  # 禁止以放宽准则或稳定化获得表面端点。
    require("PERTURB,MODAL" not in main_text and "MODOPT," not in main_text, "最小增量主输入仍含模态命令")  # 双重阻断模态与低内存生产外推。
    require(commands.count(f"SAVE,{manifest['jobname']}_L1,DB".upper()) == 1 and commands.count(f"SAVE,{manifest['jobname']}_MS,DB".upper()) == 1, "LS1 或最小步端点 DB 保存命令缺失")  # 确保完整基线和成功端点各有独立数据库。
    conflicting = runtime_base.active_solver_processes()  # 获取当前精确 MAPDL/MPI 冲突进程清单。
    require(not conflicting, f"已有 MAPDL/MPI 进程，拒绝并发启动：{conflicting}")  # 保证本诊断独占求解环境且不干扰其他运行。
    memory = psutil.virtual_memory()  # 读取启动瞬间物理内存快照。
    disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 读取运行所在卷的实时磁盘快照。
    require(int(memory.available) >= MINIMUM_RAM_BYTES, f"可用物理内存低于诊断下限四 GiB：{memory.available}")  # 资源不足时在 Popen 前拒绝。
    require(int(disk.free) >= MINIMUM_DISK_BYTES, f"运行盘空余低于诊断启动线五十 GiB：{disk.free}")  # 防止 RST、DB 或 NR 文件写满磁盘。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 从冻结清单恢复完整参数数组，禁止重新拼接猜测。
    require(bool(launch_argv) and launch_argv[0] == str(executable), "启动参数首项不是冻结 MAPDL")  # 固定实际二进制入口。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and runtime_base.argument_value(launch_argv, "-np") == "1", "启动参数不是唯一批处理 SMP1")  # 禁止 DMP、MPI 或多进程占用。
    require("-dis" not in launch_argv and "-mpi" not in launch_argv, "启动参数意外包含 DMP/MPI")  # 显式关闭低内存范围之外的并行模式。
    require(runtime_base.argument_value(launch_argv, "-j") == str(manifest.get("jobname")), "启动参数 jobname 与清单不一致")  # 固定结果文件族。
    require(Path(runtime_base.argument_value(launch_argv, "-dir")).resolve() == solver_dir.resolve(), "启动参数工作目录越出本运行")  # 固定所有原始输出位置。
    require(Path(runtime_base.argument_value(launch_argv, "-i")).resolve() == main_input.resolve(), "启动参数未指向已哈希主输入")  # 关闭 deck 替换路径。
    expected_output = (solver_dir / f"{manifest['jobname']}.out").resolve()  # 构造本作业唯一权威 OUT 路径。
    require(Path(runtime_base.argument_value(launch_argv, "-o")).resolve() == expected_output, "启动参数 OUT 路径错误")  # 阻断跨运行日志覆盖。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位已逐项复算的准备账本原件。
    prepared_ledger_sha256 = runtime_base.sha256_file(prepared_ledger_path)  # 计算准备账本自身摘要供启动链三方核对。
    manifest_sha256 = runtime_base.sha256_file(manifest_path)  # 计算清单摘要供认领、PID 记录和监控器闭合。
    started_at = datetime.now(timezone.utc)  # 在排他认领和创建进程前记录统一 UTC 起点。
    resources = {"physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": int(memory.available), "formal_8_gib_gate_passed": int(memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_exception_gate_passed": True, "disk_free_bytes": int(disk.free), "disk_50_gib_gate_passed": True, "conflicting_solver_process_count": len(conflicting)}  # 冻结启动前资源与独占性证据。
    claim = {"schema_version": 1, "run_name": run_dir.name, "jobname": manifest["jobname"], "status": "LAUNCH_CLAIMED_NOT_YET_STARTED", "claimed_at_utc": started_at.isoformat(), "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "diagnostic_change_set": DIAGNOSTIC_CHANGE_SET, "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": prepared_ledger_sha256, "prepared_ledger_entry_count": len(prepared_entries), "prelaunch_resources": resources, "production_claim_allowed": False}  # 在 Popen 前冻结唯一启动权和全部输入身份。
    runtime_base.write_json(launch_claim_path, claim)  # 以排他创建写出认领；后续任何失败都会使目录不可复用。
    claim_sha256 = runtime_base.sha256_file(launch_claim_path)  # 计算已落盘认领摘要供真实 PID 记录引用。
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 使用无窗口标志；项目固定 Windows，其他平台回退零。
    process = subprocess.Popen(launch_argv, cwd=solver_dir, creationflags=creation_flags)  # 仅在全部门禁通过后异步启动唯一 MAPDL 进程。
    record = {"schema_version": 1, "run_name": run_dir.name, "jobname": manifest["jobname"], "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "started_at_utc": started_at.isoformat(), "main_pid": int(process.pid), "process_identity_path": process_identity_path.name, "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "diagnostic_change_set": DIAGNOSTIC_CHANGE_SET, "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": prepared_ledger_sha256, "prepared_ledger_entry_count": len(prepared_entries), "launch_claim_sha256": claim_sha256, "prelaunch_resources": resources, "production_claim_allowed": False, "monitor_hard_stops": {"available_ram_below_bytes": 512 * 1024**2, "available_ram_below_1_gib_sustained_seconds": 60, "disk_free_below_bytes": 32 * 1024**3}, "native_abort_only": True, "force_termination_allowed": False}  # 取得 PID 后第一时间冻结最小启动记录和只允许原生中止的监控合同。
    runtime_base.write_json(runtime_launch_path, record)  # 以排他创建提交 PID 和运行时硬门，再尝试增强身份采集。
    try:  # 增强身份采集可能因包装器极速交接或系统策略失败，必须安全留下原生中止证据。
        process_identity = psutil.Process(process.pid)  # 按刚取得的 PID 获取真实包装器对象。
        create_time = float(process_identity.create_time())  # 冻结操作系统进程创建时刻以阻断 PID 回收误附着。
        executable_path = str(Path(process_identity.exe()).resolve())  # 冻结真实二进制规范路径。
        command_line = [str(value) for value in process_identity.cmdline()]  # 冻结操作系统实际命令行数组。
        require(str(Path(executable_path).resolve()).casefold() == str(executable.resolve()).casefold(), "Popen 后二进制不是批准 MAPDL")  # 不区分 Windows 路径大小写核对真实程序。
        require(command_line == launch_argv, "Popen 后真实命令行与冻结参数不一致")  # 要求全部参数逐项相同。
        identity = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURED", "run_name": run_dir.name, "jobname": manifest["jobname"], "captured_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_launch_sha256": runtime_base.sha256_file(runtime_launch_path), "pid": int(process.pid), "create_time_epoch_seconds": create_time, "executable": executable_path, "command_line": command_line}  # 建立与 PID 记录绑定的防回收身份。
        runtime_base.write_json(process_identity_path, identity)  # 以排他创建提交增强身份供专用监控器附着。
    except Exception as identity_error:  # 捕获已启动后任何身份采集、核对或写盘失败。
        failure_path = run_dir / "runtime_process_identity_failure.json"  # 定位不可覆盖的启动后身份故障记录。
        failure = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURE_FAILED_NATIVE_ABORT_REQUESTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "runtime_launch_sha256": runtime_base.sha256_file(runtime_launch_path), "error_type": type(identity_error).__name__, "error_message": str(identity_error), "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "force_termination_allowed": False}  # 记录故障、PID、启动身份和只允许原生中止边界。
        runtime_base.write_json(failure_path, failure)  # 先持久化故障记录，防止目录被误认为未启动。
        abort_path, abort_action = request_native_abort(solver_dir, str(manifest["jobname"]))  # 仅写官方 nonlinear 原生请求，不调用 terminate 或 kill。
        raise RuntimeError(f"MAPDL 已启动但进程身份捕获失败；已执行 {abort_action}：{abort_path}") from identity_error  # 向调用者报告部分启动和自然退出等待义务。
    print(json.dumps({"run_dir": str(run_dir), "pid": int(process.pid), "status": "RUNNING_MINSTEP_NRRE_IDENTITY_CAPTURED", "process_identity_path": str(process_identity_path), "native_abort_only": True}, ensure_ascii=False))  # 返回供立即启动专用监控器使用的机器摘要。


if __name__ == "__main__":  # 仅直接执行本文件时进入一次排他启动流程，导入审查不访问运行状态。
    main()  # 执行准备账本、专用命令、资源和进程身份全门后启动 MAPDL。
