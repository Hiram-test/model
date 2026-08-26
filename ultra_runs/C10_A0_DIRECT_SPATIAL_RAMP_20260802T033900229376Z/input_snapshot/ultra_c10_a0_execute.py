from __future__ import annotations  # 启用延迟类型注解，保持运行时类型提示兼容且不增加求解依赖。

import argparse  # 解析只读启动前复核、显式实际启动与离线自检三种互斥模式。
import ast  # 离线审查本启动器源码结构和唯一 Popen 调用数量。
import hashlib  # 验证官方原生 ABT 十字节载荷与运行工件身份。
import json  # 输出只读复核、离线自检、启动认领和真实 PID 记录。
import os  # 在身份采集失败时把官方 ABT 十字节载荷 flush 并 fsync 到磁盘。
import re  # 审查每个非空源码行是否具有中文说明。
import subprocess  # 仅在调用者显式给出 --launch 且全部门通过后启动一次 MAPDL。
import tempfile  # 只在系统临时目录离线测试 ABT 排他创建、回读和重复拒绝行为。
from datetime import datetime, timezone  # 生成启动认领、进程记录和故障证据的 UTC 时刻。
from pathlib import Path  # 安全处理包含中文的运行、求解器、输入与输出绝对路径。
from typing import Any  # 标注清单、状态、账本和启动记录中的异构 JSON 值。

import psutil  # 只读检查实时内存、磁盘和 Popen 后的真实进程身份。

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
MINIMUM_DISK_BYTES = 50 * 1024**3  # 实际启动要求运行盘至少五十 GiB 空余，给 DB、RST 和 NRRE 留安全余量。
MONITOR_RAM_IMMEDIATE_BYTES = 512 * 1024**2  # 监控器在可用物理内存低于五百一十二 MiB 时提交原生 ABT 请求。
MONITOR_RAM_SUSTAINED_SECONDS = 60  # 监控器在低于一 GiB 连续六十秒时提交原生 ABT 请求。
MONITOR_DISK_BYTES = 32 * 1024**3  # 监控器在运行盘空余低于三十二 GiB 时提交原生 ABT 请求。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 冻结 MAPDL 2026 R1 认可的 nonlinear 加单一 LF 共十个 ASCII 字节。
NATIVE_ABORT_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 冻结官方 ABT 载荷摘要以关闭换行和编码歧义。


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
    require(not abort_path.exists(), f"身份故障时 ABT 已存在，禁止覆盖：{abort_path}")  # 保留任何并发控制动作的原始字节和时间证据。
    with abort_path.open("x+b") as handle:  # 使用二进制排他创建，禁止文本换行转换和覆盖竞态。
        written = handle.write(NATIVE_ABORT_PAYLOAD)  # 一次写入精确十字节官方载荷。
        require(written == 10, f"官方 ABT 发生短写：{written}/10")  # 短写时禁止声称有效中止请求。
        handle.flush()  # 把 Python 用户态缓冲提交到操作系统句柄。
        os.fsync(handle.fileno())  # 请求操作系统把十字节内容同步到持久存储。
        handle.seek(0)  # 把同一排他句柄移回首字节以避免路径替换竞态。
        readback = handle.read()  # 从同一文件描述符回读实际落盘载荷。
    require(readback == NATIVE_ABORT_PAYLOAD, "官方 ABT 回读字节不一致")  # 只有逐字节相等才承认请求有效。
    return {"path": str(abort_path), "length_bytes": len(readback), "hex": readback.hex(), "sha256": hashlib.sha256(readback).hexdigest(), "created_exclusively": True, "flush_completed": True, "fsync_completed": True, "readback_matches_contract": True, "force_termination_called": False}  # 返回完整字节、同步、回读和禁止强制处置证据。


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
    runtime_identity_names = ["runtime_launch_claim.json", "runtime_launch.json", "runtime_process_identity.json", "runtime_process_identity_failure.json"]  # 定义实际启动前必须不存在的根级运行工件。
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
    launch_ready_now = not conflicts and int(memory.available) >= MINIMUM_RAM_BYTES and int(disk.free) >= MINIMUM_DISK_BYTES  # 同时满足独占、四 GiB 与五十 GiB 才标记当前可启动。
    return {"schema_version": 1, "status": "PASSED_VALIDATE_ONLY", "run_name": resolved_run.name, "jobname": jobname, "manifest": manifest, "root_status": status, "ledger_entry_count": len(entries), "solver_dir": solver_dir, "main_path": main_path, "executable": executable, "launch_argv": launch_argv, "conflicting_solver_processes": conflicts, "physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": int(memory.available), "formal_8_gib_gate_passed": int(memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_gate_passed": int(memory.available) >= MINIMUM_RAM_BYTES, "disk_free_bytes": int(disk.free), "disk_50_gib_gate_passed": int(disk.free) >= MINIMUM_DISK_BYTES, "launch_ready_now": launch_ready_now, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回包有效性与实时资源/并发状态，二者明确分离。


def offline_self_test() -> dict[str, Any]:  # 无业务输入；只在内存和系统临时目录验证源码、ABT 和零项目写入边界。
    require(NATIVE_ABORT_PAYLOAD == b"nonlinear\n" and len(NATIVE_ABORT_PAYLOAD) == 10 and hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_SHA256, "A0 启动器官方 ABT 合同自检失败")  # 同时核对字节、长度和摘要。
    source_text = Path(__file__).read_text(encoding="utf-8", errors="strict")  # 读取启动器自身完整源码供 AST 与逐行注释审查。
    syntax_tree = ast.parse(source_text, filename=str(Path(__file__).resolve()))  # 解析真实结构而不是依赖关键词匹配。
    popen_calls = [node for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]  # 统计所有可能创建子进程的 Popen 调用节点。
    require(len(popen_calls) == 1, f"A0 启动器 Popen 调用数不是唯一一次：{len(popen_calls)}")  # 只允许显式 --launch 分支内一个创建点。
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
        duplicate_rejected = False  # 初始化重复文件是否按禁止覆盖合同被拒绝的标志。
        try:  # 尝试再次写同一 job 以验证排他保护。
            write_native_abort(temporary_dir, "a0_selftest")  # 第二次调用必须在打开写句柄前失败。
        except RuntimeError:  # 捕获预期的既有文件拒绝异常。
            duplicate_rejected = True  # 记录重复 ABT 没有被覆盖或截断。
        require(duplicate_rejected, "A0 启动器未拒绝重复 ABT")  # 保证排他创建回归有效。
    return {"schema_version": 1, "status": "PASSED", "popen_call_count": 1, "popen_not_executed": True, "forbidden_process_action_count": 0, "comment_violation_count": 0, "native_abort_payload_length_bytes": 10, "native_abort_payload_sha256": NATIVE_ABORT_SHA256, "duplicate_abort_rejected": True, "project_run_paths_touched": False, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回源码、ABT、排他性和零启动自检结果。


def launch(validated: dict[str, Any]) -> dict[str, Any]:  # 输入已通过包门的只读复核对象并启动一次 MAPDL，返回真实 PID 与身份摘要。
    require(validated.get("status") == "PASSED_VALIDATE_ONLY", "A0 启动输入不是刚通过的只读复核对象")  # 防止绕过统一启动前门。
    require(validated.get("launch_ready_now") is True, f"A0 当前资源或并发门不允许启动：{validated.get('conflicting_solver_processes')}")  # 独占、内存或磁盘不满足时在任何写入前拒绝。
    run_dir = Path(str(validated["solver_dir"])).parent.resolve()  # 从已验证 solver 目录回取唯一运行根。
    manifest = validated["manifest"]  # 读取已经由账本和真实字节闭合的清单对象。
    solver_dir = Path(str(validated["solver_dir"])).resolve()  # 读取已验证 MAPDL 工作目录。
    executable = Path(str(validated["executable"])).resolve()  # 读取已验证 MAPDL 二进制路径。
    launch_argv = [str(value) for value in validated["launch_argv"]]  # 复制冻结参数数组，后续不得重新拼接或修改。
    claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他启动认领文件。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后最小真实 PID 记录。
    identity_path = run_dir / "runtime_process_identity.json"  # 定位 Popen 后增强创建时刻、二进制和命令身份记录。
    failure_path = run_dir / "runtime_process_identity_failure.json"  # 定位仅在增强身份失败时生成的故障证据。
    require(not any(path.exists() for path in [claim_path, launch_path, identity_path, failure_path]), "A0 启动工件在复核后出现，禁止并发或重复启动")  # 关闭检查到使用时间窗中的目录竞争。
    conflicts = runtime_base.active_solver_processes()  # 在 Popen 紧前再次读取真实 MAPDL/MPI 冲突进程。
    memory = psutil.virtual_memory()  # 在 Popen 紧前再次读取可用物理内存。
    disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 在 Popen 紧前再次读取运行盘空余。
    require(not conflicts and int(memory.available) >= MINIMUM_RAM_BYTES and int(disk.free) >= MINIMUM_DISK_BYTES, f"A0 临启动资源或独占门失败：{conflicts}")  # 任一瞬时门失败都保持零启动。
    started_at = datetime.now(timezone.utc)  # 记录认领与 Popen 共用的精确 UTC 启动时刻。
    manifest_sha256 = runtime_base.sha256_file(run_dir / "manifest.json")  # 计算账本保护的清单摘要供启动链闭合。
    ledger_sha256 = runtime_base.sha256_file(run_dir / "artifact_hashes.sha256")  # 计算准备账本自身摘要供认领、PID 与监控三方闭合。
    prelaunch_resources = {"physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": int(memory.available), "formal_8_gib_gate_passed": int(memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_gate_passed": True, "disk_free_bytes": int(disk.free), "disk_50_gib_gate_passed": True, "conflicting_solver_process_count": 0}  # 冻结真实进程创建前的资源和独占性证据。
    claim = {"schema_version": 1, "status": "LAUNCH_CLAIMED_NOT_YET_STARTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "claimed_at_utc": started_at.isoformat(), "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": ledger_sha256, "prepared_ledger_entry_count": int(validated["ledger_entry_count"]), "prelaunch_resources": prelaunch_resources, "production_claim_allowed": False}  # 在 Popen 前冻结唯一启动权、输入身份、资源与非生产边界。
    runtime_base.write_json(claim_path, claim)  # 以排他创建提交启动认领；后续任何失败均禁止同目录重试。
    claim_sha256 = runtime_base.sha256_file(claim_path)  # 计算已经落盘的不可覆盖认领摘要。
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 使用无窗口批处理标志；本项目固定 Windows，回退值仅保持语法兼容。
    process = subprocess.Popen(launch_argv, cwd=solver_dir, creationflags=creation_flags)  # 只在显式 --launch 且全部门通过后创建唯一 MAPDL 进程。
    launch_record = {"schema_version": 1, "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "started_at_utc": started_at.isoformat(), "main_pid": int(process.pid), "process_identity_path": identity_path.name, "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": ledger_sha256, "prepared_ledger_entry_count": int(validated["ledger_entry_count"]), "launch_claim_sha256": claim_sha256, "prelaunch_resources": prelaunch_resources, "monitor_hard_stops": {"available_ram_below_bytes": MONITOR_RAM_IMMEDIATE_BYTES, "available_ram_below_1_gib_sustained_seconds": MONITOR_RAM_SUSTAINED_SECONDS, "disk_free_below_bytes": MONITOR_DISK_BYTES}, "production_claim_allowed": False}  # Popen 后立即冻结最小 PID、参数、谱系和监控阈值记录。
    runtime_base.write_json(launch_path, launch_record)  # 在任何增强身份读取前排他提交最小真实 PID 记录。
    try:  # 增强身份可能因包装器快速交接或系统访问策略失败，失败必须提交官方 ABT 而非强杀。
        process_identity = psutil.Process(process.pid)  # 按 Popen 返回 PID 获取操作系统进程对象。
        create_time = float(process_identity.create_time())  # 冻结进程创建时刻以阻断 PID 回收误附着。
        actual_executable = str(Path(process_identity.exe()).resolve())  # 冻结操作系统报告的真实二进制规范路径。
        actual_command_line = [str(value) for value in process_identity.cmdline()]  # 冻结操作系统报告的真实参数数组。
        require(Path(actual_executable).resolve() == executable and actual_command_line == launch_argv, "A0 Popen 后真实二进制或命令行与冻结值不一致")  # 只有完全一致才允许监控器附着。
        identity = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURED", "run_name": run_dir.name, "jobname": manifest["jobname"], "captured_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_launch_sha256": runtime_base.sha256_file(launch_path), "pid": int(process.pid), "create_time_epoch_seconds": create_time, "executable": actual_executable, "command_line": actual_command_line}  # 汇总防 PID 回收的增强身份。
        runtime_base.write_json(identity_path, identity)  # 以排他创建提交增强身份供专用监控器三方核验。
    except Exception as identity_error:  # 捕获身份读取、比较或排他写入的全部异常并进入原生安全中止路径。
        abort_evidence = write_native_abort(solver_dir, str(manifest["jobname"]))  # 只提交官方十字节 ABT，不调用 terminate、kill 或信号接口。
        failure = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURE_FAILED_NATIVE_ABORT_REQUESTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "runtime_launch_sha256": runtime_base.sha256_file(launch_path), "error_type": type(identity_error).__name__, "error_message": str(identity_error), "native_abort": abort_evidence, "terminate_called": False, "kill_called": False}  # 保存已启动事实、故障和官方 ABT 完整证据。
        runtime_base.write_json(failure_path, failure)  # 以排他创建提交身份故障终态，禁止目录被误当作未启动。
        raise RuntimeError("A0 MAPDL 已启动但增强身份失败；已提交官方十字节 ABT，禁止重复启动") from identity_error  # 向调用者明确报告部分启动和后续只等待边界。
    return {"run_dir": str(run_dir), "pid": int(process.pid), "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURED", "monitor_command": ["python", "-B", str(run_dir / MONITOR_RELATIVE), "--run-dir", str(run_dir)], "mapdl_execution_attempted": True, "mapdl_started": True}  # 返回真实 PID、监控入口和已启动事实供编排器立即接管。


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
