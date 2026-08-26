from __future__ import annotations  # 启用延迟类型注解，避免运行时解析复杂容器注解增加依赖。

import argparse  # 解析互斥的离线自检或只准备运行模式，禁止本脚本启动 MAPDL。
import ast  # 静态检查专用启动器和监控器不存在 terminate、kill 或 send_signal 调用。
import json  # 生成机器可读状态、清单、控制审计和离线自检结果。
import re  # 严格验证冻结 SHA-256 常量和生成主控中的 NR 文件模式说明。
import shutil  # 将父求解依赖、权威质量源和运行代码逐字节复制进唯一运行包。
import sys  # 冻结生成准备包时使用的 Python 可执行文件路径供后续启动命令引用。
from datetime import datetime, timezone  # 生成包含微秒的 UTC 运行和作业身份，防止覆盖历史结果。
from pathlib import Path  # 安全处理包含中文的绝对工程路径和运行内相对路径。
from typing import Any  # 标注 JSON 审计对象允许容纳字符串、数字、布尔值和嵌套结构。

import ultra_c10_load_migration_prepare as migration  # 复用已验证的恒总荷载修正向量、授权谱系和两步迁移变换。
import ultra_c10_static_diagnostic_prepare as static_base  # 复用父谱系、微验证、确定性替换和 SHA-256 基础函数。


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 取 ultra_tools 父目录作为猫道分析包根目录。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 冻结全部不可覆盖 C10 运行包所在目录。
STATIC_BASE_SHA256 = "c7c14705c7635b7513bde90369aa25f59962c36411975dd72704eb14f5d2c2ba"  # 冻结静力基础准备模块当前六十四位小写摘要。
MIGRATION_BASE_SHA256 = "4993385f646957f661ee4198df8d32ed4cf93e2bfd41e0f069acf3df7a20076c"  # 冻结恒总荷载迁移准备模块当前六十四位小写摘要。
RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_MINSTEP_NRRE_"  # 指定唯一新运行目录族，保持现有执行体系允许的迁移前缀。
DIAGNOSTIC_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_FIRST_0_05_PERCENT_NRRE_ENDPOINT"  # 冻结最小增量残差定位子类型。
DIAGNOSTIC_CHANGE_SET = "FULL_LS1_THEN_FIXED_SINGLE_0_05_PERCENT_LS2_WITH_NRRE_MAXFILE_50"  # 冻结多命令但单一物理增量的诊断变更集。
MINSTEP_MAIN_NAME = "c10_minstep_nrre_static_main.inp"  # 指定新运行唯一允许启动的 APDL 静力主控文件名。
CORRECTION_INCLUDE_NAME = migration.CORRECTION_INCLUDE_NAME  # 复用已验证的 15,071 节点恒总荷载位置修正 include 名称。
EXECUTE_SCRIPT_NAME = "ultra_c10_minstep_residual_execute.py"  # 指定运行内专用启动器快照文件名。
MONITOR_SCRIPT_NAME = "ultra_c10_minstep_residual_monitor.py"  # 指定运行内专用原生 ABT 监控器快照文件名。
STATIC_RUNTIME_UTILITY_NAME = "ultra_c10_static_execute.py"  # 指定专用启动器只读复用的准备账本与资源门工具模块。
MONITOR_RUNTIME_UTILITY_NAME = "ultra_c10_adaptive_monitor.py"  # 指定专用监控器只读复用的日志扫描与进程绑定工具模块。
MINSTEP_BETA_TEXT = "0.9995"  # 冻结 LS2 终点 beta，使完整迁移路径只前进 0.05%。
MINSTEP_TIME_TEXT = "1.0000005"  # 冻结 LS2 伪时间终点，相对 LS1 的增量为 5E-7。
MINSTEP_MIGRATION_FRACTION = 0.0005  # 以无量纲小数记录完整 beta 路径的万分之五迁移比例。
MINSTEP_TIME_INCREMENT = 0.0000005  # 以伪时间单位记录 LS2 相对 TIME=1 的二百万分之一增量。
NRRE_MAXFILE = 50  # 规定 NLDIAG 最多保留五十个 Jobname.nrxxx 节点残差文本文件。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结单层 TYPE72 全桥在既有 LS1 与最小步运行中观察到的方程数。
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")  # 只接受六十四位小写十六进制 SHA-256 文本。
FORBIDDEN_PROCESS_METHODS = {"terminate", "kill", "send_signal"}  # 冻结专用启动与监控控制流禁止调用的强制进程方法集合。


def require(condition: bool, message: str) -> None:  # 输入布尔门和失败说明；不满足时停止自检或准备且无业务返回值。
    if not condition:  # 仅在代码、谱系、数量、命令、守恒或路径门失败时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常并禁止留下可被误启动的半成品运行。


def parse_args() -> argparse.Namespace:  # 无业务输入并返回互斥的离线自检或只准备模式。
    parser = argparse.ArgumentParser(description="离线验证或只准备 C10 最小 0.05% 迁移 NRRE 残差诊断")  # 创建明确禁止默认启动的命令行接口。
    mode_group = parser.add_mutually_exclusive_group(required=True)  # 强制调用者在两种无求解模式中显式选择一个。
    mode_group.add_argument("--self-test", action="store_true", help="只在内存中重建候选并静态核验三段工具，不创建 run")  # 提供零写入、零求解的离线测试入口。
    mode_group.add_argument("--prepare-only", action="store_true", help="创建唯一已哈希运行包和启动命令，但绝不启动 ANSYS")  # 提供唯一允许创建准备工件的入口。
    return parser.parse_args()  # 返回已由 argparse 拒绝缺失、重复或未知选项的命名空间。


def powershell_quote(value: str) -> str:  # 输入单个命令行参数并返回 PowerShell 单引号安全文本。
    return "'" + value.replace("'", "''") + "'"  # 通过双写内部单引号保持中文路径和空格逐字传递。


def executable_apdl_lines(text: str) -> list[str]:  # 输入完整 APDL 文本并返回排除空行、说明和标题的规范大写执行序列。
    commands: list[str] = []  # 初始化保持原顺序的真实命令列表。
    for line in text.splitlines():  # 按完整主控真实行顺序扫描，禁止只抽查局部片段。
        executable = line.split("!", maxsplit=1)[0].strip()  # 删除行内说明并去除首尾显示空白。
        if not executable or executable.upper().startswith("/TITLE,"):  # 空行、说明和运行身份标题不属于数值合同。
            continue  # 跳过非执行内容并继续下一行。
        commands.append(executable.upper().replace(" ", ""))  # 规范大小写和普通空格但保留字段、数值与顺序。
    return commands  # 返回供精确计数和禁止项核验的完整序列。


def forbidden_process_calls(path: Path) -> list[str]:  # 输入 Python 源路径并返回所有禁止的进程方法调用名称及行号。
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))  # 解析完整 UTF-8 源码且不执行其中任何逻辑。
    findings: list[str] = []  # 初始化禁止调用发现列表。
    for node in ast.walk(tree):  # 遍历完整抽象语法树，覆盖嵌套函数、异常和条件路径。
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_PROCESS_METHODS:  # 只匹配真实方法调用而非说明文字或字段名。
            findings.append(f"{node.func.attr}@{getattr(node, 'lineno', 0)}")  # 保存方法名和一基行号供修复定位。
    return findings  # 空列表表示专用代码没有 terminate、kill 或 send_signal 调用路径。


def validate_upstream_evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:  # 无业务输入并返回通过父模型、微验证和 0.05% 授权门的三份证据摘要。
    require(SHA256_PATTERN.fullmatch(STATIC_BASE_SHA256) is not None, "静力基础模块冻结摘要格式错误")  # 防止少位摘要让代码身份门失效。
    require(SHA256_PATTERN.fullmatch(MIGRATION_BASE_SHA256) is not None, "迁移基础模块冻结摘要格式错误")  # 防止少位摘要让物理变换身份门失效。
    require(static_base.sha256_file(Path(static_base.__file__).resolve()) == STATIC_BASE_SHA256, "静力基础准备模块 SHA-256 漂移")  # 固定父谱系和静力截断实现。
    require(static_base.sha256_file(Path(migration.__file__).resolve()) == MIGRATION_BASE_SHA256, "恒总荷载迁移准备模块 SHA-256 漂移")  # 固定修正向量和授权门实现。
    parent_dir = RUNS_ROOT / static_base.PARENT_RUN_NAME  # 定位已删除串联链的单层 TYPE72 权威父运行。
    micro_dir = RUNS_ROOT / static_base.MICRO_RUN_NAME  # 定位十二案例全部通过的连接微验证运行。
    parent_manifest, micro_results = static_base.validate_parent(parent_dir, micro_dir)  # 逐项复算父十二项输入和微验证身份。
    baseline_dir = RUNS_ROOT / migration.K5_REFERENCE_MIGRATION_RUN_NAME  # 定位默认 K5=0 的固定 0.5% 发散输入基准。
    baseline_entry_count = migration.validate_final_artifact_ledger(baseline_dir, migration.ADAPTIVE_INPUT_BASELINE_LEDGER_SHA256)  # 复算基准五十九项最终归档。
    require(baseline_entry_count == 59, "默认 0.5% 输入基准最终账本条目不是五十九项")  # 固定输入基准发布覆盖规模。
    require(static_base.sha256_file(baseline_dir / "C10_static_status.json") == migration.ADAPTIVE_INPUT_BASELINE_STATUS_SHA256, "默认 0.5% 基准状态摘要漂移")  # 固定基准失败类型。
    require(static_base.sha256_file(baseline_dir / "manifest.json") == migration.ADAPTIVE_INPUT_BASELINE_MANIFEST_SHA256, "默认 0.5% 基准清单摘要漂移")  # 固定基准谱系。
    require(static_base.sha256_file(baseline_dir / "qa" / "runtime_abort_audit.json") == migration.ADAPTIVE_INPUT_BASELINE_ABORT_SHA256, "默认 0.5% 基准终止审计漂移")  # 固定首步发散数值证据。
    require(static_base.sha256_file(baseline_dir / "solver" / migration.MIGRATION_MAIN_NAME) == migration.ADAPTIVE_INPUT_BASELINE_MAIN_SHA256, "默认 0.5% 基准主控摘要漂移")  # 固定真实可执行输入身份。
    authorization_dir = RUNS_ROOT / migration.ADAPTIVE_REFERENCE_MIGRATION_RUN_NAME  # 定位 K5=1 同轨仍发散且明确批准 0.05% 下一步的授权运行。
    authorization_entry_count = migration.validate_final_artifact_ledger(authorization_dir, migration.ADAPTIVE_REFERENCE_LEDGER_SHA256)  # 复算授权运行五十九项最终归档。
    require(authorization_entry_count == 59, "K5 授权运行最终账本条目不是五十九项")  # 固定授权证据覆盖规模。
    require(static_base.sha256_file(authorization_dir / "C10_static_status.json") == migration.ADAPTIVE_REFERENCE_STATUS_SHA256, "K5 授权运行状态摘要漂移")  # 固定 K5 无效终态。
    require(static_base.sha256_file(authorization_dir / "manifest.json") == migration.ADAPTIVE_REFERENCE_MANIFEST_SHA256, "K5 授权运行清单摘要漂移")  # 固定授权谱系。
    require(static_base.sha256_file(authorization_dir / "qa" / "runtime_abort_audit.json") == migration.ADAPTIVE_REFERENCE_ABORT_SHA256, "K5 授权运行终止审计漂移")  # 固定同轨残差证据。
    require(static_base.sha256_file(authorization_dir / "solver" / migration.MIGRATION_MAIN_NAME) == migration.ADAPTIVE_REFERENCE_MAIN_SHA256, "K5 授权运行主控摘要漂移")  # 固定 K5=1 可执行输入身份。
    authorization_status = static_base.load_json(authorization_dir / "C10_static_status.json")  # 读取授权根状态供语义门禁。
    authorization_abort = static_base.load_json(authorization_dir / "qa" / "runtime_abort_audit.json")  # 读取 K5 无效和后续许可字段。
    require(authorization_status.get("status") == "ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_0_5_PERCENT_MIGRATION_DIVERGED_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED", "K5 授权运行终态不符合冻结失败类型")  # 只接受已正式封板运行。
    require(authorization_abort.get("single_difference_observed_effect") == "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION", "K5 授权运行未证明同轨发散")  # 固定 K5 证伪核心事实。
    require(authorization_abort.get("ls1_converged") is True and int(authorization_abort.get("ls2_completed_substeps", -1)) == 0, "K5 授权运行未证明 LS1 闭合和 LS2 零完成子步")  # 确保最小步仍从同一完整 LS1 基线重跑。
    require(authorization_abort.get("next_diagnostic_single_difference") == "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT", "K5 授权运行未批准 0.05% 最小增量")  # 固定本诊断步长来源。
    authorization_reference = {"schema_version": 1, "status": "PASSED", "input_baseline_run": baseline_dir.name, "input_baseline_final_ledger_sha256": migration.ADAPTIVE_INPUT_BASELINE_LEDGER_SHA256, "input_baseline_final_ledger_entry_count": baseline_entry_count, "authorization_run": authorization_dir.name, "authorization_final_ledger_sha256": migration.ADAPTIVE_REFERENCE_LEDGER_SHA256, "authorization_final_ledger_entry_count": authorization_entry_count, "authorization_observation": authorization_abort["single_difference_observed_effect"], "authorized_minimum_migration_fraction": MINSTEP_MIGRATION_FRACTION, "authorized_next_diagnostic": authorization_abort["next_diagnostic_single_difference"], "ls1_converged": True, "ls2_completed_substeps": 0, "result_use": "AUTHORIZATION_EVIDENCE_ONLY_NOT_RESULT_BASELINE"}  # 汇总输入基准和 0.05% 许可且不冒充当前结果。
    return parent_manifest, micro_results, authorization_reference  # 返回完整通过父、连接和数值授权门的三份对象。


def build_migration_inputs(parent_manifest: dict[str, Any]) -> tuple[bytes, bytes, dict[str, Any]]:  # 输入父清单并返回父主控、修正 include 和完整守恒审计。
    parent_dir = RUNS_ROOT / static_base.PARENT_RUN_NAME  # 定位已经通过 validate_parent 的父运行目录。
    source_solver_dir = parent_dir / "solver"  # 定位父十二项求解输入目录。
    deadload_path = source_solver_dir / migration.DEADLOAD_INCLUDE_NAME  # 定位原 MCT 平衡荷载位置权威 include。
    mass_include_path = source_solver_dir / migration.MASS_INCLUDE_NAME  # 定位建立空间 MASS21 并删除旧 FZ 的实际 include。
    mass_csv_path = PROJECT_ROOT / migration.MASS_CSV_NAME  # 定位 33,003 个空间质量节点权威 CSV。
    require(static_base.sha256_file(mass_include_path) == migration.MASS_INCLUDE_SHA256, "空间化 MASS21 include SHA-256 漂移")  # 固定真实求解质量输入。
    require(mass_include_path.read_text(encoding="utf-8").count("FDELE,ALL,FZ") == 1, "空间化 MASS21 include 未唯一删除旧 FZ")  # 保证修正向量施加前不存在旧节点力残留。
    old_forces = migration.load_old_fz(deadload_path)  # 读取并验证 23,028 个旧平衡荷载节点。
    masses, mass_source_counts = migration.load_spatial_mass(mass_csv_path)  # 读取并验证 33,003 个空间质量节点和来源分类。
    corrections, correction_audit = migration.build_corrections(old_forces, masses)  # 生成 15,071 节点零合力位置修正向量。
    correction_bytes, correction_audit = migration.render_correction_include(corrections, correction_audit)  # 渲染 APDL 并复算文本级微牛守恒。
    correction_audit["mass_source_counts"] = mass_source_counts  # 把原始/生成节点记录数并入最终物理审计。
    correction_audit["old_deadload_include_sha256"] = migration.DEADLOAD_INCLUDE_SHA256  # 冻结旧荷载位置源身份。
    correction_audit["mass_csv_sha256"] = migration.MASS_CSV_SHA256  # 冻结空间质量节点与数值源身份。
    correction_audit["mass_include_sha256"] = migration.MASS_INCLUDE_SHA256  # 冻结求解器实际 MASS21 输入身份。
    parent_main_path = source_solver_dir / static_base.PARENT_MAIN_NAME  # 定位父静力加模态完整主控原件。
    parent_main_bytes = parent_main_path.read_bytes()  # 二进制读取父主控，保持原始换行和编码字节。
    require(static_base.sha256_bytes(parent_main_bytes) == str(parent_manifest.get("main_input_sha256")), "父主控摘要与清单不一致")  # 再次闭合可执行入口身份。
    return parent_main_bytes, correction_bytes, correction_audit  # 返回已通过身份、数量和守恒门的三项输入。


def transform_minstep_main(parent_main_bytes: bytes, old_jobname: str, new_jobname: str, correction_audit: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:  # 输入父主控、作业身份和修正审计并返回完整 LS1 加单个最小 LS2 的残差 deck。
    adaptive_bytes, audit = migration.transform_main(parent_main_bytes, old_jobname, new_jobname, correction_audit, False, True)  # 先复用已验证的 beta 路径、四项 CNVTOL、静力截断和 K5=0 变换。
    candidate = adaptive_bytes.decode("utf-8")  # 严格按 UTF-8 解码已通过基础迁移门的主控。
    newline = "\r\n" if "\r\n" in candidate else "\n"  # 保持父主控继承的 CRLF 或 LF 换行风格。
    candidate = static_base.replace_once(candidate, "/TITLE,C10 DIRECT MPC CONSTANT-LOAD MIGRATION ADAPTIVE-CUTBACK STATIC DIAGNOSTIC", "/TITLE,C10 DIRECT MPC FIRST 0.05 PERCENT MIGRATION NRRE ENDPOINT DIAGNOSTIC", "最小增量 NRRE 标题")  # 明确本运行只到第一个最小增量端点。
    ls1_end_anchor = "! 结束当前 fail-closed 条件分支；通过时继续下一门禁。" + newline + "*ENDIF" + newline + "! LS1 收敛门禁通过后保持在同一 /SOLU 分析中，使下一次 SOLVE 自动形成真实载荷步 2。" + newline  # 构造只位于 LS1 收敛门之后的唯一插入锚点。
    ls1_end_replacement = "! 结束当前 fail-closed 条件分支；通过时继续下一门禁。" + newline + "*ENDIF" + newline + "! 保存完整 LS1 beta=1 平衡数据库；即使后续最小步不收敛也保留可审计起点。" + newline + f"SAVE,{new_jobname}_l1,db" + newline + f"! 只为下一次 LS2 求解启用节点不平衡残差文本，并把最多文件数固定为 {NRRE_MAXFILE}。" + newline + f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}" + newline + "! LS1 收敛门禁通过后保持在同一 /SOLU 分析中，使下一次 SOLVE 自动形成真实载荷步 2。" + newline  # 在同一求解会话内保存 LS1 并启用 LS2 专用 NRRE。
    candidate = static_base.replace_once(candidate, ls1_end_anchor, ls1_end_replacement, "LS1 数据库与 LS2 NRRE 启用")  # 保证 NLDIAG 不污染 LS1 迭代且基线 DB 独立留存。
    old_time_block = "! 把 LS2 终点设为单调递增伪时间 1.001。" + newline + "TIME,1.001" + newline  # 冻结完整迁移主控的 LS2 时间终点片段。
    new_time_block = f"! 把 LS2 终点设为 {MINSTEP_TIME_TEXT}；相对 TIME=1 只前进 5E-7，对应完整迁移路径的 0.05%。" + newline + f"TIME,{MINSTEP_TIME_TEXT}" + newline  # 定义单个最小增量伪时间终点。
    candidate = static_base.replace_once(candidate, old_time_block, new_time_block, "LS2 最小增量时间")  # 只改变 LS2 终点，不重标度 LS1 或物理荷载总量。
    old_beta_block = "! 把二值迁移参数设为 0，使修正 include 在同一 15,071 节点集显式写入零值并定义最终荷载端点。" + newline + "C10_BETA=0" + newline  # 冻结完整迁移的 beta=0 终点片段。
    new_beta_block = f"! 把迁移参数设为 {MINSTEP_BETA_TEXT}，使修正向量只从 beta=1 减少 0.05%，而不是到达 beta=0 最终空间质量端点。" + newline + f"C10_BETA={MINSTEP_BETA_TEXT}" + newline  # 定义固定最小 beta 端点。
    candidate = static_base.replace_once(candidate, old_beta_block, new_beta_block, "LS2 beta 最小增量终点")  # 保持同一 15,071 节点 replacement 更新集合。
    candidate = static_base.replace_once(candidate, "! 用 replacement 重发 LS1 修正节点的零端点；随后 KBC,0 连续插值，ACEL 和总重力保持不变。", "! 用 replacement 重发 LS1 修正节点的 beta=0.9995 端点；KBC,0 在单子步内插值，ACEL 和总重力保持不变。", "LS2 include 最小端点说明")  # 使逐行说明与实际 beta 数值一致。
    candidate = static_base.replace_once(candidate, "! 使用斜坡定义把 beta=1 修正向量连续插值到 beta=0；修正向量总和为零，所以每个子步总荷载恒定。", "! 使用斜坡定义把 beta=1 修正向量插值到 beta=0.9995；修正向量总和为零，所以该最小增量总荷载恒定。", "LS2 KBC 最小增量语义")  # 明确本运行不抵达最终 beta=0。
    old_autots_block = "! 启用 LS2 自动时间步；初始和最少子步数保持二百，禁止增量大于 0.5%，失败时最多细分到二千子步即 0.05%。" + newline + "AUTOTS,ON" + newline  # 冻结自适应全路径的 LS2 自动步长片段。
    new_autots_block = "! 关闭 LS2 自动时间步；本运行只计算预先批准的一个 0.05% 固定增量，禁止再切分、放大或继续迁移。" + newline + "AUTOTS,OFF" + newline  # 定义固定单子步且无 cutback 的诊断合同。
    candidate = static_base.replace_once(candidate, old_autots_block, new_autots_block, "LS2 固定最小步自动控制")  # 防止求解器改变残差定位端点。
    old_nsubst_block = "! LS2 初始 200、最多 2000、最少 200 个子步；初始与最大迁移增量为 0.5%，失败时允许切回至最小 0.05%。" + newline + "NSUBST,200,2000,200" + newline  # 冻结自适应全路径子步片段。
    new_nsubst_block = "! LS2 终点本身已经是完整路径的 0.05%；三个参数均为 1，只允许一个受控子步到达该局部端点。" + newline + "NSUBST,1,1,1" + newline  # 定义单个固定子步且不继续向 beta=0 推进。
    candidate = static_base.replace_once(candidate, old_nsubst_block, new_nsubst_block, "LS2 固定最小步子步合同")  # 将全路径二千子步能力收缩为一个局部端点。
    candidate = static_base.replace_once(candidate, "! 执行 LS2 无稳定化恒总荷载位置迁移，并在 beta=0 空间化 MASS21 端点取得最终平衡。", "! 执行 LS2 无稳定化单个 0.05% 位置迁移；结果与 NRxxx 只供定位首个最小增量残差。", "LS2 最小增量 SOLVE 语义")  # 禁止把局部端点描述成最终空间质量状态。
    candidate = static_base.replace_once(candidate, "! LS2 最终端点 CNVG 不等于 1 时立即拒绝；允许的 cutback 只能增加路径分辨率，不能放宽收敛准则。", "! LS2 局部 beta=0.9995 端点 CNVG 不等于 1 时立即拒绝；本固定单子步不允许 cutback 或继续全路径。", "LS2 最小增量收敛门语义")  # 准确声明固定步失败边界。
    candidate = static_base.replace_once(candidate, "/COM,STATUS=REJECTED REASON=LS2_LOAD_POSITION_MIGRATION_NOT_CONVERGED", "/COM,STATUS=REJECTED REASON=LS2_FIRST_0_05_PERCENT_MINSTEP_NOT_CONVERGED", "LS2 最小增量失败代码")  # 输出可机器解析的真实局部失败类型。
    candidate = static_base.replace_once(candidate, "! 固定拒绝原因 LS2_LOAD_POSITION_MIGRATION_NOT_CONVERGED 供外部审计按字段解析。", "! 固定拒绝原因 LS2_FIRST_0_05_PERCENT_MINSTEP_NOT_CONVERGED 供外部审计按字段解析。", "LS2 最小增量失败说明")  # 使注释与实际 /COM 代码完全一致。
    candidate = static_base.replace_once(candidate, "! 读取 LS2 无稳定化位置迁移的 beta=0 最后收敛结果。", "! 读取 LS2 无稳定化位置迁移的 beta=0.9995 局部端点结果。", "LS2 最小端点后处理说明")  # 防止后处理误称最终状态。
    candidate = static_base.replace_once(candidate, "! 读取当前结果集伪时间，预期为 1.001。", f"! 读取当前结果集伪时间，预期为 {MINSTEP_TIME_TEXT}。", "LS2 最小端点时间读取说明")  # 对齐局部结果集时间说明。
    candidate = static_base.replace_once(candidate, "! 计算 LS2 当前时间与 1.001 的绝对误差。" + newline + "C10_TERR2=ABS(C10_TIME2-1.001)" + newline, f"! 计算 LS2 当前时间与 {MINSTEP_TIME_TEXT} 的绝对误差。" + newline + f"C10_TERR2=ABS(C10_TIME2-{MINSTEP_TIME_TEXT})" + newline, "LS2 最小端点时间误差")  # 使数值门核验真实局部时间。
    candidate = static_base.replace_once(candidate, "! LS2 时间与 1.001 的绝对误差超过 1E-10 时拒绝。", f"! LS2 时间与 {MINSTEP_TIME_TEXT} 的绝对误差超过 1E-10 时拒绝。", "LS2 最小端点时间门说明")  # 更新门禁说明而不放宽阈值。
    candidate = static_base.replace_once(candidate, f"SAVE,{new_jobname}_eq,db", f"SAVE,{new_jobname}_ms,db", "最小增量端点数据库名称")  # 把通过全部局部数值门的数据库与全路径 eq 名称区分。
    candidate = static_base.replace_once(candidate, "! 离开后处理器；静力门禁已全部通过，本诊断按限定范围不进入扰动分析。", "! 离开后处理器；局部最小步数值门已通过，但完整迁移静力仍未完成且不得进入扰动分析。", "最小增量结论边界说明")  # 禁止局部端点外推为完整静力。
    candidate = static_base.replace_once(candidate, "! 把静力诊断全部门禁通过的终态写入唯一 gate 状态。", "! 把最小增量残差端点已捕获的诊断终态写入唯一 gate 状态。", "最小增量 gate 状态说明")  # 区分局部捕获与工程通过。
    candidate = static_base.replace_once(candidate, "! 该状态只表示静力诊断通过，仍不包含任何模态或生产结论。", "! 该状态只表示 beta=0.9995 局部端点已通过当前数值门并留下 NRRE，不代表完整静力、模态或生产通过。", "最小增量状态用途说明")  # 明确允许用途边界。
    candidate = static_base.replace_once(candidate, "/COM,STATUS=STATIC_DIAGNOSTIC_GATES_PASSED PHASE=STATIC_ONLY_COMPLETE", "/COM,STATUS=MINSTEP_NRRE_ENDPOINT_CAPTURED PHASE=RESIDUAL_LOCALIZATION_ONLY", "最小增量最终状态")  # 输出唯一可机器识别的局部诊断终态。
    candidate = static_base.replace_once(candidate, "! 恢复主输出，准备结束静力专用 MAPDL 会话。", "! 恢复主输出，准备结束最小增量残差专用 MAPDL 会话。", "最小增量退出说明")  # 对齐会话用途。
    candidate = static_base.replace_once(candidate, "! 静力诊断在全部门禁通过后结束；本运行不生成或宣称任何模态结果。", "! 最小增量残差诊断在局部端点门通过后结束；本运行不继续 beta=0 全路径，也不生成任何模态结论。", "最小增量末端说明")  # 冻结求解边界。
    commands = executable_apdl_lines(candidate)  # 生成最终 deck 完整执行序列供独立静态回读。
    require(commands.count("SOLVE") == 2 and commands.count("KBC,1") == 1 and commands.count("KBC,0") == 1, "最终 deck 不是完整 LS1 加单个 LS2 两步合同")  # 固定两次求解和插值边界。
    require(commands.count("C10_BETA=1") == 1 and commands.count(f"C10_BETA={MINSTEP_BETA_TEXT}") == 1 and "C10_BETA=0" not in commands, "最终 beta 端点不是 1→0.9995")  # 排除误达完整 beta=0。
    require(commands.count("TIME,1") == 1 and commands.count(f"TIME,{MINSTEP_TIME_TEXT}") == 1 and "TIME,1.001" not in commands, "最终时间端点不是 1→1.0000005")  # 固定局部伪时间。
    require(commands.count("AUTOTS,OFF") == 2 and "AUTOTS,ON" not in commands and commands.count("NSUBST,1,1,1") == 2, "最终 LS1/LS2 未同时固定单子步")  # 禁止隐含自适应继续路径。
    require(commands.count(f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}") == 1 and not any(command.startswith("NLDIAG,EFLG") for command in commands), "最终 NRRE 命令不唯一或混入 EFLG")  # 固定残差文本输出范围。
    require(sum(1 for command in commands if command.startswith("CNVTOL,")) == 4 and "STABILIZE,ON" not in commands, "最终 deck 四项 CNVTOL 或无稳定化合同漂移")  # 保留力、力矩、平移和转角准则。
    require(commands.count(f"SAVE,{new_jobname}_L1,DB".upper()) == 1 and commands.count(f"SAVE,{new_jobname}_MS,DB".upper()) == 1, "最终 deck 未分别保存 LS1 和最小步数据库")  # 确保基线与成功端点可独立审计。
    require("PERTURB,MODAL" not in candidate and "MODOPT," not in candidate, "最终 deck 仍含模态命令")  # 主动阻断模态分析。
    require("MINSTEP_NRRE_ENDPOINT_CAPTURED" in candidate and "STATIC_DIAGNOSTIC_GATES_PASSED" not in candidate, "最终状态仍可能冒充完整静力通过")  # 固定局部结果语义。
    audit["schema_version"] = 9  # 提升控制审计结构版本以容纳局部端点和残差输出字段。
    audit["candidate_sha256"] = static_base.sha256_bytes(candidate.encode("utf-8"))  # 用最终真实入口覆盖自适应全路径候选摘要。
    audit["change_families"] = [family for family in audit.get("change_families", []) if family != "LS2_ADAPTIVE_CUTBACK_0_5_TO_0_05_PERCENT"] + ["FIRST_MINIMUM_INCREMENT_ENDPOINT_ISOLATION", "NLDIAG_NRRE_MAXFILE_50_LOCALIZATION", "LS1_AND_MINSTEP_DB_RETENTION"]  # 移除不再执行的全路径自适应声明并登记真实局部变更。
    audit["diagnostic_change_set"] = DIAGNOSTIC_CHANGE_SET  # 冻结多命令共同服务于一个物理增量的审计身份。
    audit["load_path_physical_basis"] = "MCT_INITIAL_FORCE_STATE_BALANCED_AT_BETA_1_THEN_ONLY_FIRST_0_05_PERCENT_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION"  # 记录完整 LS1 与局部迁移的工程依据。
    audit["load_path_physical_approval"] = "RESIDUAL_LOCALIZATION_ONLY_REQUIRES_INTERFACE_AND_INITIAL_STATE_REPAIR_BEFORE_FULL_PATH"  # 明确局部残差不能签认完整路径。
    audit["ls2"] = {"kbc": 0, "autots": False, "nsubst": [1, 1, 1], "time_start": 1.0, "time_end": float(MINSTEP_TIME_TEXT), "time_increment": MINSTEP_TIME_INCREMENT, "beta_start": 1.0, "beta_end": float(MINSTEP_BETA_TEXT), "migration_fraction": MINSTEP_MIGRATION_FRACTION, "single_controlled_substep": True, "cutback_allowed": False, "full_path_endpoint_reached": False, "total_vertical_load_change_n": correction_audit["rendered_correction_sum_n"], "physical_role": "FIRST_MINIMUM_INCREMENT_RESIDUAL_ENDPOINT_ONLY"}  # 覆盖原全路径字段并记录局部端点真实数值。
    audit["nldiag"] = {"label": "NRRE", "status": "ON", "maxfile": NRRE_MAXFILE, "expected_filename_glob": f"{new_jobname}.nr[0-9][0-9][0-9]", "enabled_after_ls1_convergence": True, "residual_use": "NODE_RESIDUAL_LOCALIZATION_ONLY"}  # 冻结 NLDIAG 命令、文件族和用途。
    audit["database_retention"] = {"ls1_database": f"{new_jobname}_l1.db", "minstep_endpoint_database_if_converged": f"{new_jobname}_ms.db", "result_file": f"{new_jobname}.rst", "restart_control": "RESCONTROL_DEFINE_ALL_LAST"}  # 记录预期 DB、RST 和重启动留存。
    audit["modal_commands_present"] = False  # 明确最终 deck 没有模态控制流。
    audit["production_claim_allowed"] = False  # 明确局部残差结果不得进入生产验算。
    audit["full_static_claim_allowed"] = False  # 明确 beta 未到零且不能宣称完整静力端点。
    rendered = candidate.encode("utf-8")  # 将完成全部静态门的主控编码为确定性 UTF-8 字节。
    return rendered, audit  # 返回完整 LS1 加单个最小 LS2 的可审计 deck 与控制审计。


def run_offline_self_tests() -> dict[str, Any]:  # 无业务输入并返回不创建 run、不启动求解器的完整离线测试摘要。
    parent_manifest, micro_results, authorization_reference = validate_upstream_evidence()  # 复算父输入、十二案例连接微验证和 0.05% 授权链。
    parent_main_bytes, correction_bytes, correction_audit = build_migration_inputs(parent_manifest)  # 在内存重建恒总荷载修正向量并关闭守恒门。
    test_jobname = "cw_C10mnr_selftest_d1"  # 使用短 ASCII 测试作业名，只存在内存中且不生成文件。
    require(len(test_jobname) <= 32, "离线测试作业名超过 MAPDL 三十二字符限制")  # 确保测试覆盖与正式作业名相同的长度约束。
    candidate_bytes, control_audit = transform_minstep_main(parent_main_bytes, str(parent_manifest.get("jobname")), test_jobname, correction_audit)  # 在内存执行完整确定性变换。
    require(control_audit.get("candidate_sha256") == static_base.sha256_bytes(candidate_bytes), "离线候选摘要与真实字节不一致")  # 关闭审计对象和 deck 分叉。
    require(correction_audit.get("correction_node_count") == migration.EXPECTED_CORRECTION_NODE_COUNT and correction_audit.get("rendered_correction_sum_n") == "2.08526E-10", "离线修正向量数量或守恒量漂移")  # 固定 15,071 节点和微牛级零合力。
    tool_dir = Path(__file__).resolve().parent  # 定位三段新工具和两段只读运行工具源目录。
    execute_path = tool_dir / EXECUTE_SCRIPT_NAME  # 定位专用启动器源文件。
    monitor_path = tool_dir / MONITOR_SCRIPT_NAME  # 定位专用监控器源文件。
    require(execute_path.is_file() and monitor_path.is_file(), "缺少专用最小步启动器或监控器")  # 自检前拒绝不完整工具链。
    compile(execute_path.read_text(encoding="utf-8"), str(execute_path), "exec")  # 编译专用启动器源码但不执行其 Popen 主流程。
    compile(monitor_path.read_text(encoding="utf-8"), str(monitor_path), "exec")  # 编译专用监控器源码但不附着进程。
    compile(Path(__file__).read_text(encoding="utf-8"), str(Path(__file__)), "exec")  # 编译当前准备器源码但不递归进入 main。
    require(not forbidden_process_calls(execute_path), f"专用启动器含强制进程调用：{forbidden_process_calls(execute_path)}")  # 只允许官方 ABT 原生请求。
    require(not forbidden_process_calls(monitor_path), f"专用监控器含强制进程调用：{forbidden_process_calls(monitor_path)}")  # 禁止 terminate、kill 和 send_signal 的任何 AST 调用路径。
    execute_source = execute_path.read_text(encoding="utf-8")  # 读取启动器文本供官方载荷字面量计数。
    monitor_source = monitor_path.read_text(encoding="utf-8")  # 读取监控器文本供官方载荷字面量计数。
    require(execute_source.count('NATIVE_ABORT_PAYLOAD = b"nonlinear\\n"') == 1, "专用启动器未唯一冻结官方 nonlinear ABT 载荷")  # 防止失败路径生成空文件或说明文本。
    require(monitor_source.count('NATIVE_ABORT_PAYLOAD = b"nonlinear\\n"') == 1, "专用监控器未唯一冻结官方 nonlinear ABT 载荷")  # 防止硬事件监控重现无效 ABT。
    require("terminate_exact_processes" not in execute_source and "terminate_exact_processes" not in monitor_source, "专用代码引用了共享强制终止函数")  # 即使共享工具暴露旧函数也保持调用不可达。
    return {"schema_version": 1, "status": "PASSED", "writes_performed": False, "mapdl_execution_attempted": False, "parent_run": static_base.PARENT_RUN_NAME, "parent_main_sha256": static_base.sha256_bytes(parent_main_bytes), "micro_validation_run": static_base.MICRO_RUN_NAME, "micro_validation_status": micro_results.get("status"), "authorization_run": authorization_reference["authorization_run"], "authorized_minimum_migration_fraction": authorization_reference["authorized_minimum_migration_fraction"], "candidate_sha256": control_audit["candidate_sha256"], "candidate_size_bytes": len(candidate_bytes), "correction_include_sha256": correction_audit["include_sha256"], "correction_include_size_bytes": len(correction_bytes), "correction_node_count": correction_audit["correction_node_count"], "rendered_correction_sum_n": correction_audit["rendered_correction_sum_n"], "ls1_nsubst": control_audit["ls1"]["nsubst"], "ls2_nsubst": control_audit["ls2"]["nsubst"], "ls2_beta_end": control_audit["ls2"]["beta_end"], "ls2_time_end": control_audit["ls2"]["time_end"], "nldiag": control_audit["nldiag"], "execute_script_sha256": static_base.sha256_file(execute_path), "monitor_script_sha256": static_base.sha256_file(monitor_path), "forbidden_process_calls": [], "modal_commands_present": False, "production_claim_allowed": False}  # 汇总零写入、自检 deck、守恒、步长、运行代码和用途门。


def prepare_unique_run(self_test: dict[str, Any]) -> dict[str, Any]:  # 输入已通过的离线自检摘要并创建一个唯一未启动运行包，返回机器摘要。
    require(self_test.get("status") == "PASSED" and self_test.get("writes_performed") is False, "准备前离线自检未通过或声称发生写入")  # 只允许经过零写入测试的代码创建运行包。
    parent_manifest, micro_results, authorization_reference = validate_upstream_evidence()  # 在真正创建目录前再次关闭父谱系和 0.05% 授权门。
    parent_main_bytes, correction_bytes, correction_audit = build_migration_inputs(parent_manifest)  # 重建即将真实写入的恒总荷载修正向量。
    created_at = datetime.now(timezone.utc)  # 记录本次准备动作精确 UTC 时间。
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")  # 生成含微秒的目录身份，防止并发和历史覆盖。
    run_name = f"{RUN_PREFIX}{stamp}"  # 派生只属于最小增量 NRRE 的唯一运行名。
    run_dir = RUNS_ROOT / run_name  # 构造新运行根目录。
    solver_dir = run_dir / "solver"  # 构造独立 MAPDL 工作目录。
    qa_dir = run_dir / "qa"  # 构造守恒、控制、授权和字段说明目录。
    input_snapshot_dir = run_dir / "input_snapshot"  # 构造父主控、权威 CSV 和三段运行代码快照目录。
    require(not run_dir.exists(), f"目标运行目录已存在，禁止覆盖：{run_dir}")  # 强制每次尝试拥有唯一干净目录。
    jobname = f"cw_C10mnr_{created_at.strftime('%m%dt%H%M%S%f')}_d1"  # 派生包含微秒且只含 ASCII 的 MAPDL 作业名。
    require(len(jobname) <= 32, "最小增量 MAPDL 作业名超过三十二字符")  # 遵守求解器作业名前缀长度限制。
    main_bytes, control_audit = transform_minstep_main(parent_main_bytes, str(parent_manifest.get("jobname")), jobname, correction_audit)  # 在任何目录写入前生成并验证最终 deck。
    require(control_audit.get("candidate_sha256") == static_base.sha256_bytes(main_bytes), "正式候选摘要与真实字节不一致")  # 关闭写入前最后身份门。
    solver_dir.mkdir(parents=True)  # 一次建立唯一运行根和 solver 子目录。
    qa_dir.mkdir()  # 建立 QA 工件目录。
    input_snapshot_dir.mkdir()  # 建立运行代码与输入快照目录。
    parent_dir = RUNS_ROOT / static_base.PARENT_RUN_NAME  # 定位已通过身份门的父运行。
    source_solver_dir = parent_dir / "solver"  # 定位父十二项求解依赖目录。
    for source_path in sorted(source_solver_dir.iterdir(), key=lambda item: item.name):  # 按文件名稳定顺序复制全部父求解依赖。
        require(source_path.is_file(), f"父 solver 含非文件对象：{source_path.name}")  # 禁止目录或链接混入求解依赖。
        shutil.copy2(source_path, solver_dir / source_path.name)  # 保留原始字节和时间复制到独立工作目录。
    correction_path = solver_dir / CORRECTION_INCLUDE_NAME  # 构造本运行唯一位置修正 include 路径。
    correction_path.write_bytes(correction_bytes)  # 写入已通过源端和文本端守恒门的确定性 UTF-8 字节。
    copied_parent_main = solver_dir / static_base.PARENT_MAIN_NAME  # 定位刚复制到新目录的父全模态入口。
    require(copied_parent_main.is_file(), "复制后的父主控缺失")  # 删除前确认目标确是父入口文件。
    main_path = solver_dir / MINSTEP_MAIN_NAME  # 构造本运行唯一允许启动的最小步主控路径。
    main_path.write_bytes(main_bytes)  # 写入已通过命令级回读的最终 APDL 字节。
    copied_parent_main.unlink()  # 删除 solver 内未授权启动的父全模态入口，避免误选错误主控。
    shutil.copy2(parent_dir / "solver" / static_base.PARENT_MAIN_NAME, input_snapshot_dir / static_base.PARENT_MAIN_NAME)  # 在快照目录保留未修改父主控供差分复核。
    shutil.copy2(PROJECT_ROOT / migration.MASS_CSV_NAME, input_snapshot_dir / migration.MASS_CSV_NAME)  # 保留生成修正向量所用权威质量 CSV 原件。
    tool_dir = Path(__file__).resolve().parent  # 定位三段新工具和两段只读运行工具源目录。
    source_names = [Path(__file__).name, EXECUTE_SCRIPT_NAME, MONITOR_SCRIPT_NAME, Path(static_base.__file__).name, Path(migration.__file__).name, STATIC_RUNTIME_UTILITY_NAME, MONITOR_RUNTIME_UTILITY_NAME]  # 冻结准备器、启动器、监控器及四个复用模块快照清单。
    require(len(source_names) == len(set(source_names)), "运行代码快照文件名发生重复")  # 防止后复制文件覆盖先前证据。
    for source_name in source_names:  # 按声明顺序复制全部代码原件。
        source_path = tool_dir / source_name  # 构造当前工具源绝对路径。
        require(source_path.is_file(), f"缺少运行代码源：{source_name}")  # 在复制前拒绝缺失依赖。
        shutil.copy2(source_path, input_snapshot_dir / source_name)  # 保留真实字节和时间到准备账本保护范围。
    launch_argv = [str(static_base.MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", jobname, "-dir", str(solver_dir), "-i", str(main_path), "-o", str(solver_dir / f"{jobname}.out")]  # 构造批处理 SMP 单进程且不含模态的冻结 MAPDL 参数数组。
    direct_command = "& " + " ".join(powershell_quote(value) for value in launch_argv) + "\n"  # 生成只供审计的底层 MAPDL PowerShell 命令文本。
    (run_dir / "launch_command_smp1.txt").write_text(direct_command, encoding="utf-8", newline="\n")  # 写出底层合同但准备器绝不执行该命令。
    execute_snapshot = input_snapshot_dir / EXECUTE_SCRIPT_NAME  # 定位运行内冻结专用启动器。
    monitor_snapshot = input_snapshot_dir / MONITOR_SCRIPT_NAME  # 定位运行内冻结专用监控器。
    execute_argv = [str(Path(sys.executable).resolve()), str(execute_snapshot), "--run-dir", str(run_dir)]  # 构造必须先执行的准备账本与资源门启动命令数组。
    monitor_argv = [str(Path(sys.executable).resolve()), str(monitor_snapshot), "--run-dir", str(run_dir)]  # 构造启动后立即附着的专用监控命令数组。
    (run_dir / "execute_via_frozen_launcher.txt").write_text("& " + " ".join(powershell_quote(value) for value in execute_argv) + "\n", encoding="utf-8", newline="\n")  # 写出唯一批准启动入口且不执行。
    (run_dir / "monitor_via_frozen_monitor.txt").write_text("& " + " ".join(powershell_quote(value) for value in monitor_argv) + "\n", encoding="utf-8", newline="\n")  # 写出启动后立即使用的唯一批准监控入口且不执行。
    static_base.write_json(qa_dir / "load_position_migration_audit.json", correction_audit)  # 保存节点数量、质量、力总和、极值和 include 身份审计。
    static_base.write_json(qa_dir / "minstep_residual_control_audit.json", control_audit)  # 保存 LS1、局部 LS2、NLDIAG、DB/RST 和用途边界审计。
    static_base.write_json(qa_dir / "upstream_authorization_reference.json", authorization_reference)  # 保存默认 0.5% 基准与 K5 证伪授权链。
    micro_dir = RUNS_ROOT / static_base.MICRO_RUN_NAME  # 定位权威十二案例连接微验证目录。
    micro_reference = {"schema_version": 2, "status": micro_results["status"], "run_name": static_base.MICRO_RUN_NAME, "unit_test_results_sha256": static_base.sha256_file(micro_dir / "unit_test_results.json"), "constraint_topology": micro_results["constraint_topology"], "planned_case_count": micro_results["planned_case_count"], "passed_case_count": micro_results["passed_case_count"], "failed_case_count": micro_results["failed_case_count"]}  # 冻结单层 TYPE72 连接微验证证据。
    static_base.write_json(qa_dir / "micro_validation_reference.json", micro_reference)  # 写出连接边界验证引用。
    prepared_self_test = dict(self_test)  # 复制调用前零写入自检摘要，避免原对象被补充字段污染。
    prepared_self_test["prepared_candidate_sha256"] = control_audit["candidate_sha256"]  # 记录正式微秒 jobname 对应的真实候选摘要。
    prepared_self_test["prepared_at_utc"] = created_at.isoformat()  # 记录正式准备时间以区分先前内存测试身份。
    static_base.write_json(qa_dir / "offline_self_test.json", prepared_self_test)  # 写出准备前代码、谱系、守恒和 deck 测试证据。
    execute_sha256 = static_base.sha256_file(execute_snapshot)  # 计算运行内专用启动器真实摘要。
    monitor_sha256 = static_base.sha256_file(monitor_snapshot)  # 计算运行内专用监控器真实摘要。
    status = {"schema_version": 1, "run_name": run_name, "jobname": jobname, "status": "STATIC_DIAGNOSTIC_PREPARED", "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "diagnostic_change_set": DIAGNOSTIC_CHANGE_SET, "created_at_utc": created_at.isoformat(), "parent_run": static_base.PARENT_RUN_NAME, "micro_validation_run": static_base.MICRO_RUN_NAME, "authorization_run": authorization_reference["authorization_run"], "mapdl_execution_attempted": False, "mapdl_started": False, "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "launch_allowed_for_diagnostic": True, "launch_allowed_for_production": False, "full_bridge_static_status": "FIRST_MINIMUM_INCREMENT_NRRE_PREPARED_NOT_STARTED_NOT_FULL_PATH", "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "next_action": "ONLY_WHEN_CURRENT_SOLVER_IS_CLEAR_EXECUTE_FROZEN_MINSTEP_LAUNCHER_THEN_IMMEDIATELY_FROZEN_MONITOR"}  # 冻结未启动、局部端点、非模态和非生产根状态。
    manifest = {"schema_version": 1, "run_name": run_name, "jobname": jobname, "status": status["status"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "diagnostic_change_set": DIAGNOSTIC_CHANGE_SET, "created_at_utc": created_at.isoformat(), "parent_run": static_base.PARENT_RUN_NAME, "parent_main_sha256": static_base.sha256_bytes(parent_main_bytes), "input_baseline_run": authorization_reference["input_baseline_run"], "authorization_run": authorization_reference["authorization_run"], "upstream_authorization_reference": "qa/upstream_authorization_reference.json", "preparer_script": f"input_snapshot/{Path(__file__).name}", "preparer_script_sha256": static_base.sha256_file(input_snapshot_dir / Path(__file__).name), "runtime_execute_script": f"input_snapshot/{EXECUTE_SCRIPT_NAME}", "runtime_execute_script_sha256": execute_sha256, "runtime_monitor_script": f"input_snapshot/{MONITOR_SCRIPT_NAME}", "runtime_monitor_script_sha256": monitor_sha256, "runtime_execute_utility_script": f"input_snapshot/{STATIC_RUNTIME_UTILITY_NAME}", "runtime_execute_utility_script_sha256": static_base.sha256_file(input_snapshot_dir / STATIC_RUNTIME_UTILITY_NAME), "runtime_monitor_utility_script": f"input_snapshot/{MONITOR_RUNTIME_UTILITY_NAME}", "runtime_monitor_utility_script_sha256": static_base.sha256_file(input_snapshot_dir / MONITOR_RUNTIME_UTILITY_NAME), "static_base_preparer_sha256": STATIC_BASE_SHA256, "migration_base_preparer_sha256": MIGRATION_BASE_SHA256, "micro_validation_run": static_base.MICRO_RUN_NAME, "micro_validation_status": micro_results["status"], "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "expected_topology": parent_manifest["expected_topology"], "expected_equation_count": EXPECTED_EQUATION_COUNT, "main_input": f"solver/{MINSTEP_MAIN_NAME}", "main_input_sha256": control_audit["candidate_sha256"], "load_position_correction_include": f"solver/{CORRECTION_INCLUDE_NAME}", "load_position_correction_include_sha256": correction_audit["include_sha256"], "load_position_migration_audit": "qa/load_position_migration_audit.json", "minstep_residual_control_audit": "qa/minstep_residual_control_audit.json", "mapdl_executable": str(static_base.MAPDL_EXE), "mapdl_executable_sha256": static_base.sha256_file(static_base.MAPDL_EXE), "python_executable_used_for_preparation": str(Path(sys.executable).resolve()), "execution_mode": status["execution_mode"], "analysis_scope": "FULL_BRIDGE_COMPLETE_LS1_THEN_ONLY_FIRST_FIXED_0_05_PERCENT_LS2_INCREMENT", "load_path_mode": "BETA_1_TO_BETA_0_9995_AT_CONSTANT_TOTAL_VERTICAL_LOAD", "initial_state_load_path": "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_FIRST_MINIMUM_POSITION_MIGRATION", "initial_state_equilibrium_audit": "PENDING_INTERFACE_AND_INITIAL_STATE_REPAIR_FULL_PATH_NOT_ATTEMPTED", "ls1": control_audit["ls1"], "ls2": control_audit["ls2"], "nldiag": control_audit["nldiag"], "database_retention": control_audit["database_retention"], "expected_raw_outputs": {"ls1_database": f"solver/{jobname}_l1.db", "minstep_database_if_converged": f"solver/{jobname}_ms.db", "result_file": f"solver/{jobname}.rst", "restart_file_glob": f"solver/{jobname}.r*", "node_residual_file_glob": f"solver/{jobname}.nr[0-9][0-9][0-9]", "output_file": f"solver/{jobname}.out", "error_file": f"solver/{jobname}.err", "native_monitor_file": f"solver/{jobname}.mntr"}, "constraint_imposition": "DIRECT_ELIMINATION", "mpc184_keyopt5_static": 0, "penalty_n_per_mm": None, "modal_requested": False, "production_claim_allowed": False, "static_result_expected": False, "full_static_claim_allowed": False, "runtime_equation_count_change_allowed": False, "runtime_small_zero_negative_pivot_allowed": False, "runtime_ignored_or_reset_cnvtol_allowed": False, "runtime_native_abort_payload": "nonlinear\\n", "runtime_native_abort_only": True, "runtime_force_termination_allowed": False, "launch_argv": launch_argv, "execute_argv": execute_argv, "monitor_argv": monitor_argv}  # 汇总输入谱系、局部荷载路径、输出文件族、运行代码、求解器、硬门和用途边界。
    static_base.write_json(run_dir / "C10_static_status.json", status)  # 保存根级准备状态供专用启动器唯一识别。
    static_base.write_json(run_dir / "manifest.json", manifest)  # 保存完整最小步残差运行清单。
    field_dictionary = f"# 最小增量 NRRE 机器字段说明\n\nJSON 不允许注释，因此字段语义集中记录于此。`beta=1` 是完整 LS1 旧 MCT 平衡荷载位置；`beta={MINSTEP_BETA_TEXT}` 只迁移完整位置路径的 0.05%，不是最终 `beta=0` 空间 MASS21 端点。LS1 使用 `KBC=1`、`AUTOTS=OFF`、`NSUBST=1/1/1`；LS2 使用 `KBC=0`、`AUTOTS=OFF`、`NSUBST=1/1/1`，时间从 1 到 {MINSTEP_TIME_TEXT}。`NLDIAG,NRRE,ON,{NRRE_MAXFILE}` 只在 LS1 收敛并保存 `{jobname}_l1.db` 后启用，因此 `Jobname.nrxxx` 只对应局部 LS2 Newton 迭代；最多保留 {NRRE_MAXFILE} 个文本文件。若 LS2 收敛并通过局部数值门，另存 `{jobname}_ms.db`；RST 和重启动文件按本 job 独立生成。专用监控器硬事件只允许写精确十字节 `nonlinear\\n` 原生 ABT，并等待进程自然退出；`terminate/kill/send_signal` 无调用路径。`STATIC_DIAGNOSTIC_PREPARED` 只表示输入、代码和证据已哈希，不表示 ANSYS 已启动。所有 NR、DB、RST 只供接口/初始状态残差定位，禁止作为完整静力、模态、规范或生产结果。力单位 N，长度 mm，质量 tonne，加速度 mm/s²，伪时间无物理时间含义。\n"  # 解释无注释格式中全部关键数值、输出和结论边界。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出伴随字段字典供人工复核。
    sequence = f"# 最小增量残差运行顺序\n\n当前包只完成准备，ANSYS 未启动。确认没有任何 MAPDL/MPI 运行后，先执行 `execute_via_frozen_launcher.txt` 中的唯一命令；启动器返回 PID 和 `RUNNING_MINSTEP_NRRE_IDENTITY_CAPTURED` 后，立即在另一进程执行 `monitor_via_frozen_monitor.txt`。不得直接执行底层 `launch_command_smp1.txt` 绕过准备账本、资源门和进程身份。监控器无强制结束路径；无硬事件时等待自然完成，有冻结硬事件时只写官方 `nonlinear\\n` ABT 并继续等待自然退出。完成后必须独立终结并哈希 DB、RST、NRxxx、OUT、ERR、MNTR 和重启动文件；在此之前不得发布任何静力或模态结论。\n"  # 生成人读且不自动执行的严格操作顺序。
    (run_dir / "OPERATING_SEQUENCE.md").write_text(sequence, encoding="utf-8", newline="\n")  # 写出启动和监控先后关系及禁止绕过边界。
    result_packet = f"# C10 首个 0.05% 迁移 NRRE 诊断准备结果\n\n状态：`STATIC_DIAGNOSTIC_PREPARED`；ANSYS 未启动。\n\n- 完整 LS1：beta=1、TIME=1、单子步、自动步长关闭，并独立保存 `{jobname}_l1.db`。\n- 局部 LS2：beta=1→{MINSTEP_BETA_TEXT}、TIME=1→{MINSTEP_TIME_TEXT}、单个固定子步、自动步长关闭。\n- 残差输出：`NLDIAG,NRRE,ON,{NRRE_MAXFILE}`，预期 `{jobname}.nrxxx`；不启用 EFLG。\n- 恒总荷载：15,071 个修正节点，渲染后修正力合计 {correction_audit['rendered_correction_sum_n']} N。\n- 连接基线：5,078 个单层 TYPE72，辅助节点=0、TYPE73=0；微验证 12/12 通过。\n- 运行代码：专用启动器与专用监控器已冻结并纳入准备账本；硬事件只允许官方 ABT，禁止强制结束进程。\n- 禁止范围：不继续 beta=0 全路径，不运行模态，不形成完整静力或生产结论。\n"  # 生成人工快速复核的准备摘要。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出当前未启动结论和关键数值。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用账本外的全部准备工件。
    artifact_lines = [f"{static_base.sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 生成稳定排序的小写摘要与 POSIX 相对路径行。
    require(len(artifact_lines) >= 30, "最小步准备工件少于三十项")  # 阻断运行代码、QA 或输入快照遗漏。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 构造启动前完整工件账本路径。
    ledger_path.write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 写出非自引用且可逐项复算的准备账本。
    return {"run_dir": str(run_dir), "run_name": run_name, "jobname": jobname, "status": status["status"], "mapdl_execution_attempted": False, "main_input_sha256": control_audit["candidate_sha256"], "prepared_ledger_sha256": static_base.sha256_file(ledger_path), "prepared_ledger_entry_count": len(artifact_lines), "execute_script_sha256": execute_sha256, "monitor_script_sha256": monitor_sha256, "ls2_beta_end": float(MINSTEP_BETA_TEXT), "ls2_time_end": float(MINSTEP_TIME_TEXT), "ls2_migration_fraction": MINSTEP_MIGRATION_FRACTION, "nrre_maxfile": NRRE_MAXFILE, "modal_requested": False, "production_claim_allowed": False}  # 返回唯一目录、字节身份、局部端点和严格用途边界。


def main() -> None:  # 解析显式模式并执行零写入自检或唯一准备流程，无业务返回值。
    arguments = parse_args()  # 获取互斥的 --self-test 或 --prepare-only 选择。
    self_test = run_offline_self_tests()  # 两种模式都先执行完整代码、谱系、守恒和内存 deck 测试。
    if arguments.self_test:  # 只在显式离线自检模式下直接返回零写入摘要。
        print(json.dumps(self_test, ensure_ascii=False))  # 输出机器可解析测试结果且不创建任何 run。
        return  # 结束当前脚本，确保不进入准备目录写入流程。
    require(arguments.prepare_only is True, "内部模式不是明确的 prepare-only")  # 防止未来参数扩展意外落入创建分支。
    prepared = prepare_unique_run(self_test)  # 创建唯一已哈希运行包，但不调用启动器、监控器或 MAPDL。
    print(json.dumps(prepared, ensure_ascii=False))  # 返回新目录、job、账本和关键数值供调用者审阅。


if __name__ == "__main__":  # 仅直接执行本文件时进入自检或准备流程，导入时不创建文件或启动进程。
    main()  # 执行显式选择的零写入自检或只准备运行。
