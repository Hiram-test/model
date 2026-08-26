from __future__ import annotations  # 启用延迟类型注解，避免运行期解析容器注解增加额外依赖。

import argparse  # 解析唯一运行目录、两个已核验进程号和控制器终止时间。
import hashlib  # 对准备工件、运行原件和最终发布包计算 SHA-256 字节身份。
import json  # 读取并更新无注释的机器清单、根状态和终止审计对象。
import math  # 验证从 MAPDL 输出提取的残差、主元和增量全部为有限数。
import re  # 严格提取 MAPDL 方程数、最小主元及关键 Newton 迭代打印值。
import shutil  # 把本终止归档实现复制到运行 QA 目录，保留可复现代码身份。
from datetime import datetime  # 验证控制器提供的 UTC 终止时间为可解析 ISO-8601 时间。
from pathlib import Path  # 安全处理包含中文的运行目录、求解文件和相对账本路径。
from typing import Any  # 标注 JSON 对象可容纳字符串、数字、布尔值、列表和嵌套字典。

import psutil  # 在提交终止状态前确认包装进程和实际求解进程均已不存在。


EXPECTED_RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_"  # 只允许归档恒总荷载位置迁移诊断族，阻断其他模型线。
EXPECTED_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED"  # 只处理已批准的 TYPE72 KEYOPT(5)=1 单变量运行。
FINAL_STATUS = "ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_0_5_PERCENT_MIGRATION_DIVERGED_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED"  # 冻结本失败类型的根级终态名称。
EXPECTED_EQUATION_COUNT = 1234834  # 冻结单层 TYPE72 全桥模型的方程总数，单位为方程条数。
EXPECTED_MINIMUM_PIVOT = 25.3126539  # 冻结 LS1 首次分解报告的最小正主元，用于排除旧双层约束病态复发。
FLOAT_ABS_TOLERANCE = 1.0e-9  # 对输出中冻结小数使用十亿分之一绝对容差，只容许二进制解析尾差。
SCRIPT_PATH = Path(__file__).resolve()  # 记录当前归档实现的绝对路径，供 QA 快照和摘要使用。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")  # 只接受六十四位小写 SHA-256、双空格和 POSIX 相对路径格式。
EQUATION_PATTERN = re.compile(r"Number of equations\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 稀疏求解器报告的方程总数。
PIVOT_PATTERN = re.compile(r"Sparse solver minimum pivot=\s*([+\-0-9.Ee]+)", re.IGNORECASE)  # 提取每次新三角分解报告的最小主元。


def require(condition: bool, message: str) -> None:  # 输入布尔条件和失败原因；门禁失败时终止且不提交任何最终状态。
    if not condition:  # 仅在谱系、进程、日志、数值或账本证据不闭合时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常，禁止生成伪完整的终止发布包。


def sha256_file(path: Path) -> str:  # 输入普通文件路径并返回六十四位小写 SHA-256 字节摘要。
    digest = hashlib.sha256()  # 初始化独立摘要状态，禁止依赖文件名或时间戳代替内容身份。
    with path.open("rb") as handle:  # 以只读二进制模式打开文件，避免编码和换行转换改变摘要。
        while True:  # 持续分块读取直到明确到达文件结尾，支持数 GB 求解器原件。
            block = handle.read(8 * 1024 * 1024)  # 每次读取八 MiB，在吞吐与峰值内存之间取得稳定平衡。
            if not block:  # 空字节块只在文件读取完成时出现。
                break  # 结束摘要循环并保留此前累计的全部字节。
            digest.update(block)  # 把当前原始字节块按顺序加入摘要状态。
    return digest.hexdigest()  # 返回可写入标准账本的六十四位小写十六进制摘要。


def load_json(path: Path) -> dict[str, Any]:  # 输入 JSON 路径并返回顶层对象字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 在解析前拒绝缺失、目录或错误路径。
    value = json.loads(path.read_text(encoding="utf-8"))  # 按项目冻结 UTF-8 编码解析完整文本。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 下游字段更新只接受对象结构。
    return value  # 返回通过存在性、编码、语法和顶层类型门的对象。


def write_json(path: Path, value: dict[str, Any]) -> None:  # 输入目标路径和对象并写出稳定缩进、禁止 NaN 的 UTF-8 JSON。
    rendered = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 先在内存完成序列化，避免半写入状态。
    path.write_text(rendered, encoding="utf-8", newline="\n")  # 用唯一 LF 和末尾换行提交可复核机器工件。


def validate_prelaunch_ledger(run_dir: Path, ledger_path: Path) -> int:  # 输入运行根和准备账本并返回验证通过的条目数。
    require(ledger_path.is_file(), "缺少准备阶段 artifact_hashes.sha256")  # 没有准备字节身份时禁止归档运行结果。
    lines = ledger_path.read_text(encoding="utf-8").splitlines()  # 按冻结 UTF-8 格式读取全部准备条目。
    require(len(lines) >= 20, "准备阶段哈希账本条目异常不足")  # 阻断只覆盖少量文件的残缺准备包。
    for line_number, line in enumerate(lines, start=1):  # 按真实行号逐项核验格式、路径和当前字节摘要。
        match = LEDGER_PATTERN.fullmatch(line)  # 对当前整行执行严格标准账本格式匹配。
        require(match is not None, f"准备账本第 {line_number} 行格式错误")  # 拒绝空行、非小写摘要或不唯一分隔符。
        relative_path = Path(match.group(2))  # 把 POSIX 相对文本转换为当前平台路径对象。
        require(not relative_path.is_absolute() and ".." not in relative_path.parts, f"准备账本第 {line_number} 行路径越界")  # 禁止绝对路径或父目录逃逸。
        artifact_path = run_dir / relative_path  # 构造当前运行根内的真实工件路径。
        require(artifact_path.is_file(), f"准备账本工件缺失：{relative_path.as_posix()}")  # 拒绝运行期间丢失的准备输入或说明。
        require(sha256_file(artifact_path) == match.group(1), f"准备账本工件漂移：{relative_path.as_posix()}")  # 拒绝启动后被修改的准备工件。
    return len(lines)  # 返回完整通过格式、边界、存在性和摘要门的条目数量。


def require_close(actual: float, expected: float, label: str) -> None:  # 输入实际值、冻结值和字段名并执行有限性与绝对误差门。
    require(math.isfinite(actual), f"{label} 不是有限值")  # 禁止 NaN 或无穷进入终止审计。
    require(abs(actual - expected) <= FLOAT_ABS_TOLERANCE, f"{label} 与冻结输出不一致：{actual}")  # 只容许浮点解析尾差，不容许工程量变化。


def parse_args() -> argparse.Namespace:  # 无业务输入并返回四项显式命令行参数的命名空间。
    parser = argparse.ArgumentParser(description="封存 TYPE72 KEYOPT(5)=1 后仍在首个 0.5% 迁移子步发散的 C10 运行。")  # 创建只负责终止归档且不启动求解器的解析器。
    parser.add_argument("--run-dir", required=True, type=Path, help="唯一 C10_LOAD_MIGRATION_DIAGNOSTIC 运行目录。")  # 禁止自动选择 latest 或跨运行归档。
    parser.add_argument("--wrapper-pid", required=True, type=int, help="停止前核验的 ANSYS261 包装进程号。")  # 记录启动器层身份并在提交前确认其已退出。
    parser.add_argument("--actual-solver-pid", required=True, type=int, help="停止前核验的 ANSYS 实际求解进程号。")  # 记录计算层身份并在提交前确认其已退出。
    parser.add_argument("--stopped-at-utc", required=True, help="控制器精确停止时间，必须为含时区 ISO-8601。")  # 冻结人工控制动作发生时间而非归档脚本运行时间。
    return parser.parse_args()  # 返回已完成类型检查的参数；未知参数由 argparse 拒绝。


def main() -> None:  # 验证准备谱系、进程终止、MAPDL 发散证据并原子式发布失败状态和最终账本。
    args = parse_args()  # 解析唯一目标及控制器已核验的两个进程身份与终止时刻。
    run_dir = args.run_dir.resolve()  # 解析目标绝对路径，消除相对路径和当前目录歧义。
    require(run_dir.is_dir() and run_dir.name.startswith(EXPECTED_RUN_PREFIX), f"目标不是批准的迁移运行目录：{run_dir}")  # 阻断错误目录族或缺失路径。
    stopped_at = datetime.fromisoformat(str(args.stopped_at_utc).replace("Z", "+00:00"))  # 解析允许 Z 后缀的 ISO-8601 时间。
    require(stopped_at.tzinfo is not None, "控制器终止时间缺少 UTC 偏移")  # 禁止把本地无时区时间冒充审计时刻。
    require(int(args.wrapper_pid) > 0 and int(args.actual_solver_pid) > 0 and int(args.wrapper_pid) != int(args.actual_solver_pid), "包装与求解进程号无效或重复")  # 固定两个独立正整数进程身份。
    require(not psutil.pid_exists(int(args.wrapper_pid)) and not psutil.pid_exists(int(args.actual_solver_pid)), "包装或实际求解进程仍存在，禁止提交终止状态")  # 只有两个目标进程均消失后才允许归档。
    manifest_path = run_dir / "manifest.json"  # 定位准备阶段冻结的完整运行清单。
    status_path = run_dir / "C10_static_status.json"  # 定位准备阶段根级状态，最终将原地提交终止状态。
    runtime_launch_path = run_dir / "runtime_launch.json"  # 定位执行器在启动前写出的资源和进程证据。
    manifest = load_json(manifest_path)  # 读取求解器、输入、谱系和唯一变量清单。
    status = load_json(status_path)  # 读取尚未冒充已完成的准备根状态。
    runtime_launch = load_json(runtime_launch_path)  # 读取真实启动参数、包装 PID 和资源门证据。
    require(manifest.get("run_name") == run_dir.name and status.get("run_name") == run_dir.name, "清单或状态运行名与目录不一致")  # 阻断复制或改名后的错配包。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "运行不处于可归档的准备/执行态")  # 防止重复终结或覆盖其他结论。
    require(manifest.get("diagnostic_subtype") == EXPECTED_SUBTYPE and status.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "运行不是冻结的 KEYOPT(5)=1 迁移子类型")  # 限定本归档器的唯一数值路径。
    require(manifest.get("mpc184_keyopt5_static") == 1 and manifest.get("single_variable_change") == "TYPE72_KEYOPT5_0_TO_1_ONLY", "清单未冻结 TYPE72 KEYOPT(5) 单差异")  # 禁止多变量或默认 K5 运行进入本结论。
    require(manifest.get("prestressed_modal_requires_keyopt5_restore_to_zero") is True and manifest.get("modal_requested") is False, "模态边界未正确冻结")  # 确保失败运行没有启动模态且不能被误续算。
    require(runtime_launch.get("status") == "RUNNING_DIAGNOSTIC" and int(runtime_launch.get("main_pid", -1)) == int(args.wrapper_pid), "启动证据与包装进程号不一致")  # 闭合执行器记录和控制器停止对象。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位尚代表启动前状态的准备账本。
    prepared_entry_count = validate_prelaunch_ledger(run_dir, prepared_ledger_path)  # 在任何发布写入前复算全部准备字节身份。
    prelaunch_ledger_path = run_dir / "artifact_hashes_prelaunch.sha256"  # 构造不可与最终账本混淆的启动前账本副本路径。
    require(not prelaunch_ledger_path.exists(), "启动前账本副本已存在，禁止重复终结")  # 防止再次执行覆盖首次终止证据。
    prepared_ledger_bytes = prepared_ledger_path.read_bytes()  # 暂存已验证的准备账本字节，全部日志门通过后才提交副本。
    main_input_path = run_dir / str(manifest.get("main_input"))  # 按清单定位实际启动的唯一 APDL 主控。
    require(main_input_path.is_file() and sha256_file(main_input_path) == str(manifest.get("main_input_sha256")), "实际主控缺失或摘要漂移")  # 再次关闭启动入口身份门。
    main_text = main_input_path.read_text(encoding="utf-8")  # 读取主控供命令计数和模态范围复核。
    require(main_text.splitlines().count("KEYOPT,72,5,1") == 1, "主控未唯一设置 TYPE72 KEYOPT(5)=1")  # 证明本次静力切线开关确实进入求解输入。
    require(main_text.splitlines().count("NSUBST,200,200,200") == 1 and main_text.splitlines().count("KBC,0") == 1, "0.5% LS2 迁移合同漂移")  # 固定二百等分和线性插值路径。
    require(sum(1 for line in main_text.splitlines() if line.startswith("CNVTOL,")) == 4 and "PERTURB,MODAL" not in main_text and "MODOPT," not in main_text, "收敛门或静力专用范围漂移")  # 确认四项门禁未放宽且无模态命令。
    output_path = run_dir / "solver" / f"{manifest['jobname']}.out"  # 按清单作业名定位 MAPDL 主输出原件。
    require(output_path.is_file() and output_path.stat().st_size > 1_000_000, "MAPDL 主输出缺失或异常过小")  # 需要至少一 MB 以证明完整装配和 LS1/LS2 打印存在。
    output_text = output_path.read_text(encoding="utf-8", errors="replace")  # MAPDL 输出为 ASCII 兼容文本，替代偶发非 UTF-8 字节但保留数值行。
    equation_counts = [int(value) for value in EQUATION_PATTERN.findall(output_text)]  # 提取全部报告方程数供恒定性审计。
    pivots = [float(value) for value in PIVOT_PATTERN.findall(output_text)]  # 提取全部最小主元供正定性与病态复发审计。
    require(equation_counts and set(equation_counts) == {EXPECTED_EQUATION_COUNT}, "方程数缺失、变化或不是 1,234,834")  # 阻断约束拓扑运行时变化。
    require(pivots and all(math.isfinite(value) and value > 0.0 for value in pivots), "最小主元缺失、非有限或非正")  # 拒绝 small、zero 或 negative pivot 路径。
    require_close(min(pivots), EXPECTED_MINIMUM_PIVOT, "最小正主元")  # 固定与前序基准相同的健康首分解主元。
    output_upper = output_text.upper()  # 构造不区分大小写的错误与病态关键词检查视图。
    require("SMALL EQUATION SOLVER PIVOT" not in output_upper and "ZERO PIVOT" not in output_upper and "NEGATIVE PIVOT" not in output_upper, "运行出现 small/zero/negative pivot")  # 排除旧双层连接病态。
    required_fragments = ["FORCE CONVERGENCE VALUE  =  0.7009", "MOMENT CONVERGENCE VALUE =   10.78", ">>> SOLUTION CONVERGED AFTER EQUILIBRIUM ITERATION   4", "FORCE CONVERGENCE VALUE  =   522.4", "EQUIL ITER   1 COMPLETED.  NEW TRIANG MATRIX.  MAX DOF INC= -0.8899", "FORCE CONVERGENCE VALUE  =  0.8500E+08", "MOMENT CONVERGENCE VALUE =  0.1515E+10", "EQUIL ITER   2 COMPLETED.  NEW TRIANG MATRIX.  MAX DOF INC=  -12.17"]  # 冻结 LS1 最终闭合和 LS2 前两轮爆炸轨迹的求解器原生打印片段。
    require(all(fragment in output_text for fragment in required_fragments), "MAPDL 输出缺少冻结的 LS1 收敛或 LS2 发散片段")  # 只有全部关键片段同时存在才允许发布本失败类型。
    require(re.search(r"\*\*\* LOAD STEP\s+2\s+SUBSTEP", output_text) is None, "LS2 已存在完成子步，不能按首子步未收敛归档")  # 确认 beta=0.995 端点尚未形成可用结果帧。
    previous_reference = load_json(run_dir / "qa" / "previous_migration_reference.json")  # 读取本次单变量运行冻结的 0.5% 直接前序证据。
    previous_run_dir = run_dir.parent / str(previous_reference.get("run_name"))  # 按冻结运行名定位默认 KEYOPT(5)=0 基准目录。
    previous_abort_path = previous_run_dir / "qa" / "runtime_abort_audit.json"  # 定位前序原生发散数值审计。
    require(previous_abort_path.is_file() and sha256_file(previous_abort_path) == str(previous_reference.get("runtime_abort_audit_sha256")), "前序运行终止审计缺失或摘要漂移")  # 防止重写基准后伪称单变量比较。
    previous_abort = load_json(previous_abort_path)  # 读取默认 K5 基准的前两轮残差和位移增量。
    require(previous_abort.get("ls2_force_residual_n_by_observed_state") == [522.4, 85003000.0] and previous_abort.get("ls2_moment_residual_n_mm_by_observed_state") == [10.78, 1515300000.0] and previous_abort.get("ls2_maximum_dof_increment_mm_by_completed_iteration") == [-0.8899, -12.17], "前序 0.5% 发散轨迹不是冻结基准")  # 证明新旧 K5 运行在打印精度下完全同轨。
    prelaunch_ledger_path.write_bytes(prepared_ledger_bytes)  # 所有只读门通过后逐字节提交已验证的二十六项准备账本副本。
    finalizer_snapshot_path = run_dir / "qa" / SCRIPT_PATH.name  # 构造本归档实现的运行内只读证据路径。
    require(not finalizer_snapshot_path.exists(), "终止归档脚本快照已存在，禁止重复终结")  # 防止后执行覆盖首次发布代码身份。
    shutil.copy2(SCRIPT_PATH, finalizer_snapshot_path)  # 保留实际执行版本的逐字节快照和文件时间。
    abort_audit = {"schema_version": 2, "status": FINAL_STATUS, "run_name": run_dir.name, "jobname": manifest["jobname"], "wrapper_pid": int(args.wrapper_pid), "actual_solver_pid": int(args.actual_solver_pid), "exact_command_lines_verified_before_stop": True, "processes_confirmed_absent_after_stop": True, "stopped_at_utc": stopped_at.isoformat(), "equation_count": EXPECTED_EQUATION_COUNT, "equation_count_constant": True, "minimum_positive_pivot": min(pivots), "small_zero_negative_pivot_observed": False, "ls1_beta": 1.0, "ls1_converged": True, "ls1_equilibrium_iterations": 4, "ls1_final_force_residual_n": 0.7009, "ls1_final_force_criterion_n": 47870.0, "ls1_final_moment_residual_n_mm": 10.78, "ls1_final_moment_criterion_n_mm": 7806000.0, "ls1_final_displacement_increment_mm": 0.0001645, "ls1_final_rotation_increment": 1.081e-7, "ls2_target_beta_first_substep": 0.995, "ls2_migration_fraction_first_substep": 0.005, "ls2_completed_substeps": 0, "ls2_force_residual_n_by_observed_state": [522.4, 85000000.0], "ls2_moment_residual_n_mm_by_observed_state": [10.78, 1515000000.0], "ls2_maximum_dof_increment_mm_by_completed_iteration": [-0.8899, -12.17], "mpc184_keyopt5_static": 1, "single_difference_baseline_run": previous_run_dir.name, "single_difference_observed_effect": "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION", "static_result_obtained": False, "modal_execution_attempted": False, "production_claim_allowed": False, "next_diagnostic_single_difference": "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT"}  # 汇总进程、拓扑、主元、LS1 闭合、LS2 同轨发散、K5 无效和唯一后续授权。
    abort_audit_path = run_dir / "qa" / "runtime_abort_audit.json"  # 构造机器可读终止审计路径。
    write_json(abort_audit_path, abort_audit)  # 提交已通过全部门禁的第二版终止审计。
    audit_dictionary = "# KEYOPT(5)=1 后 0.5% 迁移终止审计字段说明\n\n`runtime_abort_audit.json` 为无注释 JSON，字段语义集中记录于此。力单位 N，力矩单位 N·mm，平移单位 mm，转角单位 rad。`ls1_converged=true` 仅证明 beta=1 旧荷载位置基态闭合。`ls2_completed_substeps=0` 表示 beta=0.995 首端点未收敛，中断时 ESAV、EMAT、R001 和 RST 均不得作为最终静力或模态状态。`single_difference_observed_effect` 表示相对默认 `KEYOPT(5)=0` 基准，前两轮 Newton 打印值没有变化，因此排除 rigid-beam 几何应力刚度未修复发散。下一轮只授权把 `NSUBST` 从 `200,200,200` 改为 `200,2000,200`，保留初始和最大增量 0.5%，允许求解器最小切回到 0.05%；不授权改变荷载、质量、连接、初始内力或四项收敛标准。\n"  # 为 JSON 提供单位、不可用结果边界、K5 结论和后续唯一变量说明。
    (run_dir / "qa" / "runtime_abort_audit.md").write_text(audit_dictionary, encoding="utf-8", newline="\n")  # 写出伴随人读字段字典。
    manifest.update({"status": FINAL_STATUS, "initial_state_equilibrium_audit": "LS1_BETA_1_PASSED_LS2_0_5_PERCENT_DIVERGED_IDENTICALLY_WITH_TYPE72_KEYOPT5_1", "static_result_expected": False, "static_result_obtained": False, "ls1_beta_1_converged": True, "ls2_beta_0_reached": False, "runtime_abort_audit": "qa/runtime_abort_audit.json", "runtime_abort_audit_dictionary": "qa/runtime_abort_audit.md", "abort_finalizer_snapshot": f"qa/{SCRIPT_PATH.name}", "next_action": "PREPARE_LS2_ADAPTIVE_200_2000_200_SINGLE_DIFFERENCE_DIAGNOSTIC"})  # 把清单从准备态更新为 K5 无效、无静力结果且只允许自适应步长后续的终态。
    write_json(manifest_path, manifest)  # 提交保留全部原字段和新增运行结论的清单。
    status.update({"status": FINAL_STATUS, "mapdl_execution_attempted": True, "mapdl_started": True, "stopped_at_utc": stopped_at.isoformat(), "controller_stop_verified_wrapper_pid": int(args.wrapper_pid), "controller_stop_verified_solver_pid": int(args.actual_solver_pid), "launch_allowed_for_diagnostic": False, "full_bridge_static_status": "LS1_BETA_1_CONVERGED_LS2_FIRST_0_5_PERCENT_MIGRATION_NOT_CONVERGED_K5_EXCLUSION_NO_EFFECT", "valid_static_result_obtained": False, "ls1_beta_1_converged": True, "ls1_equilibrium_iteration_count": 4, "ls1_final_force_residual_n": 0.7009, "ls1_final_moment_residual_n_mm": 10.78, "equation_count_constant": True, "small_zero_negative_pivot_observed": False, "minimum_positive_pivot": min(pivots), "ls2_attempted_migration_fraction": 0.005, "ls2_completed_substep_count": 0, "ls2_second_iteration_force_residual_n": 85000000.0, "ls2_second_iteration_moment_residual_n_mm": 1515000000.0, "single_difference_observed_effect": "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION", "next_action": "PREPARE_LS2_ADAPTIVE_200_2000_200_SINGLE_DIFFERENCE_DIAGNOSTIC"})  # 提交根级失败事实、停止身份、K5 无效结论和唯一下一步。
    write_json(status_path, status)  # 最后写出下游首先读取的根级终止状态。
    result_packet = f"# C10 TYPE72 KEYOPT(5)=1 迁移诊断终止结果\n\n状态：`{FINAL_STATUS}`。\n\n- LS1 在 4 次迭代收敛：力残差 0.7009 N，力矩残差 10.78 N·mm，最小正主元 {min(pivots):.7f}。\n- LS2 首个 0.5% 端点未收敛：第 1/2 轮力残差为 522.4 N / 85.00 MN，力矩残差为 10.78 N·mm / 1.515 GN·mm，位移修正为 -0.8899 mm / -12.17 mm。\n- 上述 LS2 打印轨迹与默认 KEYOPT(5)=0 基准相同，因此关闭 TYPE72 rigid-beam 几何应力刚度没有修复发散。\n- 控制器已核对并停止包装 PID {int(args.wrapper_pid)} 与实际求解 PID {int(args.actual_solver_pid)}；两者均已消失。\n- 没有取得有效静力端点，没有执行模态，也不允许生产使用。\n- 下一轮唯一获准变化为 `NSUBST,200,2000,200`，允许 0.5% 首步失败时切回至最小 0.05%。\n"  # 生成面向人工复核的关键残差、同轨结论、停止证据和后续边界。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 用最终事实替换准备阶段人读结果包。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用最终账本外的全部输入、日志、二进制和 QA 工件。
    artifact_lines = [f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 按 POSIX 相对路径稳定排序并计算当前真实字节摘要。
    prepared_ledger_path.write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 用覆盖全部运行工件的最终账本替换准备账本。
    print(json.dumps({"run_dir": str(run_dir), "status": FINAL_STATUS, "prepared_ledger_entry_count": prepared_entry_count, "final_ledger_entry_count": len(artifact_lines), "minimum_positive_pivot": min(pivots), "ls2_second_iteration_force_residual_n": 85000000.0, "processes_confirmed_absent_after_stop": True}, ensure_ascii=False))  # 返回可解析的终态、账本规模和关键发散证据。


if __name__ == "__main__":  # 仅在直接执行本文件时进入一次终止归档流程，导入时不写任何运行工件。
    main()  # 执行全部谱系、进程、日志、数值、比较和最终哈希门禁。
