from __future__ import annotations  # 启用延迟类型注解，避免运行时提前解析复杂注解并保持工具兼容性。

import argparse  # 解析离线自检、只读验证、生成与既有运行复核四种互斥模式。
import ast  # 审查本准备器源码，证明没有 subprocess 或求解器启动调用路径。
import json  # 读写机器可解析的清单、预求解门禁、谱系与零启动证据。
import re  # 解析标准 SHA-256 账本并检查准备器源码中的禁止调用。
import shutil  # 把已验证的冻结输入和运行工具逐字节复制到唯一新运行目录。
from datetime import datetime, timezone  # 生成带微秒的 UTC 运行目录、作业名和证据时刻。
from pathlib import Path  # 安全处理包含中文的工程绝对路径与运行内相对路径。
from typing import Any  # 标注 JSON 字典与异构审计对象允许的值类型。

import ultra_c10_static_diagnostic_prepare as static_base  # 复用已验证的摘要、JSON、唯一替换与父运行微验证基础门禁。


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 以当前 ultra_tools 的父目录冻结本项目根，不接受外部路径注入。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 冻结所有不可覆盖运行包的唯一父目录。
TOOLS_ROOT = PROJECT_ROOT / "ultra_tools"  # 冻结本次准备器和受控运行工具的唯一源目录。
C10_RUN_NAME = "C10_MPC_ONLY_20260801T190630474559Z"  # 指定当前 5,078 个单层 TYPE72 直接消元连接父运行。
C10_MAIN_NAME = "c10_mpc_only_main.inp"  # 指定当前父运行中包含 S10 静力斜坡与后续模态的主控文件。
C10_MAIN_SHA256 = "e537c411581ec86a7df4cccc0f5fa93450182f06e41084256fd0a11299155e94"  # 冻结当前父主控字节身份，阻断任何未登记修改。
C10_GATE_NAME = "apply_finite_gates_and_passages_v2.inp"  # 指定含 5,078 个 TYPE72 的受控连接 include 文件名。
C10_GATE_SHA256 = "4f7da8425a25739c694880422c4d2188088b83c1d64170baf44accd922b5b01e"  # 冻结当前直接消元连接 include 字节身份。
C10_MICRO_RUN_NAME = "C10_MICRO_VALIDATION_20260801T190634755506Z"  # 指定 12/12 通过的当前单层 TYPE72 微验证运行。
S10_RUN_NAME = "S10_SECTION_SHEAR_20260716T050342389124Z"  # 指定最后一个真实完成 LS1、LS2 与 80 阶模态的 S10 运行。
S10_MAIN_NAME = "s10_section_shear_main.inp"  # 指定 S10 权威主控文件名用于静力控制对照。
S10_MAIN_SHA256 = "fbfc0501ea21278c0ea65d3733ce220912b89a5a2e3a5bb06679c5f8f77009e8"  # 冻结 S10 权威主控字节身份。
S10_GATE_SHA256 = "72012ebbd107cf377c2178561b9008606aeb894c4f7879110d13c30d2a417330"  # 冻结 S10 旧 CERIG 与截面剪切修正后的连接 include 身份。
INITIAL_STATE_SHA256 = "d5958628a0e5b3159114aab35811bd2cceaffdc5ae865a4a295e359674ed9b53"  # 冻结 MCT LINK180 初始状态 include 身份。
DEADLOAD_SHA256 = "3feb7eec692762d8324865611ae600a39e4b13cd777d8d5bb29896b2e1a1223e"  # 冻结原 MCT 等效节点恒载 include 身份。
MASS21_SHA256 = "4f9cf3cac4d1b032abccf0c3dcca208f3a9e5c7d064b25fb47ebcdd3e6bcbc9f"  # 冻结空间化 MASS21 include 身份。
GRAVITY_SHA256 = "33238c02d9f8a0c7bfb4cd2d777e866453f5d51e5084254e21c09353337edb5e"  # 冻结原 MCT 等效节点重力清理 include 身份。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 冻结未来受控启动使用的 MAPDL 2026 R1 二进制路径。
RUN_PREFIX = "C10_A0_DIRECT_SPATIAL_RAMP_"  # 固定本次最短因果门运行目录族，禁止与迁移诊断混用。
DIAGNOSTIC_SUBTYPE = "A0_CURRENT_TYPE72_S10_DIRECT_SPATIAL_GRAVITY_RAMP_STATIC_ONLY_NRRE"  # 冻结 A0 的唯一模型、荷载路径、范围与诊断身份。
A0_MAIN_NAME = "c10_a0_direct_spatial_ramp_main.inp"  # 指定唯一可执行的静力专用主输入文件名。
EXECUTE_TOOL_NAME = "ultra_c10_a0_execute.py"  # 指定未来显式启动所用的 A0 专用受控入口文件名。
MONITOR_TOOL_NAME = "ultra_c10_a0_monitor.py"  # 指定未来启动后所用的 A0 专用安全监控文件名。
STATIC_HELPER_NAME = "ultra_c10_static_execute.py"  # 指定 A0 启动器只复用只读摘要、账本、进程与参数帮助函数的冻结模块。
MONITOR_HELPER_NAME = "ultra_c10_adaptive_monitor.py"  # 指定 A0 监控器只复用成熟进程识别、日志扫描与原生 ABT 帮助函数的冻结模块。
NRRE_MAXFILE = 50  # 最多保留五十个 Newton-Raphson 残差文件，取官方允许范围 1 至 999 内的诊断上限。
EXPECTED_EQUATION_COUNT = 1_234_834  # 冻结当前单层 TYPE72 全桥已观测方程数，运行时任何漂移均为硬事件。
EXPECTED_DEPENDENCY_COUNT = 11  # 冻结父主控在装配阶段按顺序调用的十一份 include 数量。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")  # 只接受小写六十四位摘要、双空格和运行内相对路径的标准账本行。


def require(condition: bool, message: str) -> None:  # 接收布尔门和失败说明；失败时阻断准备或复核且无业务返回值。
    if not condition:  # 仅在谱系、控制、工具、哈希或零启动证据不满足时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常并保证不创建可误用的部分运行包。


def executable_commands(text: str) -> list[str]:  # 输入完整 APDL 文本并返回删除说明和空格后的大写可执行命令序列。
    commands: list[str] = []  # 初始化保持真实执行先后顺序的命令列表。
    for line in text.splitlines():  # 逐物理行扫描完整输入，避免局部抽样漏掉禁止命令。
        command = line.split("!", maxsplit=1)[0].strip()  # 去除 APDL 行内说明并保留真正可执行部分。
        if not command:  # 空行或整行说明不属于数值控制合同。
            continue  # 跳过非执行内容并继续扫描下一物理行。
        commands.append(command.upper().replace(" ", ""))  # 规范大小写与普通空格但保留参数、数值和顺序。
    return commands  # 返回供精确计数、禁项检查和审计摘要使用的完整命令序列。


def source_hash(path: Path, expected_hash: str, label: str) -> str:  # 输入源文件、冻结摘要和标签并返回通过门禁的当前摘要。
    require(path.is_file(), f"缺少{label}：{path}")  # 在摘要计算前拒绝缺失、目录或错误路径。
    observed_hash = static_base.sha256_file(path)  # 流式复算当前真实字节的 SHA-256 身份。
    require(observed_hash == expected_hash, f"{label} SHA-256 漂移：{observed_hash}")  # 只接受与冻结值完全一致的源文件。
    return observed_hash  # 返回已经闭合的摘要供清单和谱系报告引用。


def validate_s10_source() -> dict[str, Any]:  # 无业务输入；验证 S10 真成功源、静力控制和质量荷载闭合并返回证据摘要。
    s10_dir = RUNS_ROOT / S10_RUN_NAME  # 定位最后一个真实通过完整静力与模态验收的 S10 目录。
    s10_main = s10_dir / "solver" / S10_MAIN_NAME  # 定位 S10 权威主控原件。
    source_hash(s10_main, S10_MAIN_SHA256, "S10 权威主控")  # 关闭 S10 主控字节身份门。
    s10_manifest = static_base.load_json(s10_dir / "manifest.json")  # 读取 S10 最终清单而不是准备态副本。
    s10_gate = static_base.load_json(s10_dir / "qa" / "postrun_gate.json")  # 读取 S10 独立运行后验收门。
    require(s10_manifest.get("run_name") == S10_RUN_NAME and s10_manifest.get("status") == "PASS_WITH_LEGACY_LIMITATIONS", "S10 清单不是冻结的真实通过状态")  # 要求正确运行名和最终状态。
    require(s10_manifest.get("main_input_sha256") == S10_MAIN_SHA256, "S10 清单主控摘要与冻结值不一致")  # 防止清单和真实主控分叉。
    require(s10_gate.get("gate_status") == "PASSED" and s10_gate.get("final_status") == "PASS_WITH_LEGACY_LIMITATIONS", "S10 后验门未通过")  # 只把真实完成运行作为 A0 路径参考。
    checks = s10_gate.get("checks")  # 读取 S10 后验门逐项布尔结果。
    require(isinstance(checks, dict) and checks.get("ls1_and_ls2_converged") is True and checks.get("mass_and_reaction_closed") is True, "S10 静力收敛或质量反力闭合证据缺失")  # 固定最关键静力真实性门。
    static_result = s10_gate.get("static")  # 读取 S10 静力端点与全历程量化证据。
    require(isinstance(static_result, dict) and static_result.get("ls1_converged") is True and static_result.get("ls2_converged") is True, "S10 LS1/LS2 不是双收敛")  # 双重确认两载荷步均真实收敛。
    require(int(static_result.get("ls1_history_rows", 0)) == 20 and float(static_result.get("reaction_relative_error", 1.0)) <= 1.0e-4, "S10 二十子步或重力反力闭合不满足参考条件")  # 证明成功路径确实使用二十段斜坡且反力闭合。
    s10_commands = executable_commands(s10_main.read_text(encoding="utf-8", errors="strict"))  # 解析 S10 全主控的真实命令序列。
    require(s10_commands.count("KBC,0") == 2 and s10_commands.count("AUTOTS,ON") == 1 and s10_commands.count("NSUBST,20,200,20") == 1 and s10_commands.count("PRED,OFF") == 1, "S10 成功路径四项控制命令不满足冻结合同")  # 固定 A0 要恢复的核心控制。
    return {"run_name": S10_RUN_NAME, "manifest_status": s10_manifest["status"], "postrun_gate_status": s10_gate["gate_status"], "main_sha256": S10_MAIN_SHA256, "main_out_sha256": s10_gate["main_out"]["sha256"], "ls1_history_rows": static_result["ls1_history_rows"], "mass_tonne": static_result["mass_actual_tonne"], "reaction_relative_error": static_result["reaction_relative_error"]}  # 返回足以证明真实成功、控制来源和质量闭合的紧凑摘要。


def validate_c10_source() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:  # 无业务输入；验证当前 C10、微验证、依赖和单差异证据并返回清单、结果与依赖记录。
    c10_dir = RUNS_ROOT / C10_RUN_NAME  # 定位当前单层 TYPE72 准备父运行。
    micro_dir = RUNS_ROOT / C10_MICRO_RUN_NAME  # 定位当前单层拓扑十二案例微验证运行。
    parent_manifest, micro_results = static_base.validate_parent(c10_dir, micro_dir)  # 复用父输入逐项哈希与 12/12 微验证门。
    source_hash(c10_dir / "solver" / C10_MAIN_NAME, C10_MAIN_SHA256, "C10 当前父主控")  # 关闭当前主控字节身份门。
    source_hash(c10_dir / "solver" / C10_GATE_NAME, C10_GATE_SHA256, "C10 当前 TYPE72 include")  # 关闭 5,078 条连接定义身份门。
    single_difference = static_base.load_json(c10_dir / "qa" / "model_single_difference_audit.json")  # 读取从 S10 到 C10 的可逆单差异审计。
    require(single_difference.get("status") == "PASSED" and single_difference.get("physical_change_family_count") == 1, "C10 单差异审计未通过或物理变化族不唯一")  # 只允许 CERIG 到单 TYPE72 运动学替换。
    reversible = single_difference.get("include_reversible_audit")  # 读取连接 include 逐条可逆审计对象。
    require(isinstance(reversible, dict) and reversible.get("source_sha256") == S10_GATE_SHA256 and reversible.get("candidate_sha256") == C10_GATE_SHA256 and reversible.get("canonicalized_equals_source_bytes") is True, "S10/C10 连接可逆审计未闭合")  # 证明除连接公式外没有第二物理变化。
    require(reversible.get("source_cerig_count") == 5078 and reversible.get("mpc184_type72_count") == 5078 and reversible.get("mpc184_type73_count") == 0 and reversible.get("aux_node_count") == 0, "C10 连接拓扑不是 5078 个单层 TYPE72")  # 固定数量、无辅助节点和无 TYPE73。
    dependencies = parent_manifest.get("dependencies")  # 读取当前父运行十二项文件记录。
    require(isinstance(dependencies, list) and len(dependencies) == 12, "C10 父运行依赖记录不是十二项")  # 十一 include 加父主控必须全部存在。
    include_records = [record for record in dependencies if isinstance(record, dict) and record.get("name") != C10_MAIN_NAME]  # 排除待受控截断的父主控，仅保留十一份物理输入。
    require(len(include_records) == EXPECTED_DEPENDENCY_COUNT, "C10 物理 include 数量不是十一")  # 防止漏项或多复制未登记输入。
    expected_invariants = {"apply_mct_authoritative_initial_state_link180.inp": INITIAL_STATE_SHA256, "apply_authoritative_mct_deadload_v1.inp": DEADLOAD_SHA256, "apply_dynamic_mass21_spatialized_v2.inp": MASS21_SHA256, "apply_authoritative_mct_gravity_v1.inp": GRAVITY_SHA256, C10_GATE_NAME: C10_GATE_SHA256}  # 冻结本 A0 绝不能改变的初态、恒载、质量、重力与连接摘要。
    for dependency_name, expected_hash in expected_invariants.items():  # 逐项验证五个核心物理输入的父记录和真实字节。
        matching = [record for record in include_records if record.get("name") == dependency_name]  # 按文件名精确定位唯一依赖记录。
        require(len(matching) == 1 and matching[0].get("solver_sha256") == expected_hash, f"C10 核心依赖记录漂移：{dependency_name}")  # 清单摘要必须与冻结值一致。
        source_hash(c10_dir / "solver" / dependency_name, expected_hash, f"C10 核心依赖 {dependency_name}")  # 真实文件必须与清单和冻结值三方闭合。
    gate_commands = executable_commands((c10_dir / "solver" / C10_GATE_NAME).read_text(encoding="utf-8", errors="strict"))  # 解析当前连接 include 的执行命令。
    require(gate_commands.count("ET,72,MPC184") == 1 and gate_commands.count("KEYOPT,72,1,1") == 1 and gate_commands.count("KEYOPT,72,2,0") == 1 and gate_commands.count("KEYOPT,72,5,0") == 1, "TYPE72 定义或三项 KEYOPT 不是冻结值")  # 明确保留直接消元和 KEYOPT(5)=0。
    require(gate_commands.count("TYPE,72") == 5078 and not any(command.startswith("ET,73,") or command == "TYPE,73" for command in gate_commands), "TYPE72 连接选择数不是 5078 或仍含 TYPE73")  # 以独立命令计数关闭拓扑门。
    require(not any(command.startswith("CERIG,") for command in gate_commands), "当前 C10 include 仍含 CERIG")  # 禁止把旧连接方程与 TYPE72 重复施加。
    mass_commands = executable_commands((c10_dir / "solver" / "apply_dynamic_mass21_spatialized_v2.inp").read_text(encoding="utf-8", errors="strict"))  # 解析空间化质量 include 的执行命令。
    require(mass_commands.count("FDELE,ALL,FZ") == 1 and mass_commands[-5:] == ["ALLSEL,ALL", "NSEL,ALL", "FDELE,ALL,FZ", "ALLSEL,ALL", "FINISH"], "MASS21 include 封板尾序列没有唯一 FDELE,ALL,FZ")  # 证明直接空间重力端点先清除旧 FZ、再恢复选择并正常结束，不会叠加旧节点重力。
    return parent_manifest, micro_results, include_records  # 返回后续生成所需的当前清单、微验证结果和十一依赖记录。


def transform_main(source_bytes: bytes, old_jobname: str, new_jobname: str) -> tuple[bytes, dict[str, Any]]:  # 输入冻结父主控、新旧作业名并返回仅增 NRRE 且截断模态的 A0 主控与审计。
    source_text = source_bytes.decode("utf-8", errors="strict")  # 严格按 UTF-8 解码父主控，禁止替代字符掩盖锚点漂移。
    newline = "\r\n" if "\r\n" in source_text else "\n"  # 保留父主控原有换行风格，使无关静力字节尽量稳定。
    require(source_text.count(old_jobname) == 5, "C10 父主控作业名引用数不是冻结的五处")  # 验证主作业、静力结果、模态结果和数据库身份锚点。
    candidate = source_text.replace(old_jobname, new_jobname)  # 先统一替换全部作业身份，再从模态入口截断多余引用。
    candidate = static_base.replace_once(candidate, "/TITLE,C10 MPC184 CONNECTION PATCH FULL BRIDGE PRESTRESSED MODAL", "/TITLE,C10 A0 CURRENT TYPE72 S10 DIRECT SPATIAL GRAVITY RAMP STATIC ONLY NRRE", "A0 标题")  # 使 OUT 明确声明当前连接、S10 路径、静力范围和残差诊断。
    candidate = static_base.replace_once(candidate, "! 保留预应力效应供后续线性扰动模态使用。", "! 保留预应力效应供静力切线一致性和外部复核；本 A0 包不执行模态。", "PSTRES 说明")  # 消除截断后会误导为继续模态的说明。
    candidate = static_base.replace_once(candidate, "! 只保留每载荷步末重启动帧，确保 LS2 扰动点可追溯。", "! 只保留每载荷步末重启动帧，确保 LS2 静力保持点可追溯。", "RESCONTROL 说明")  # 把重启动用途限定为静力追溯。
    candidate = static_base.replace_once(candidate, "! 保存 LS2 末完整场作为唯一扰动基态。", "! 保存 LS2 末完整场作为唯一静力复核基态。", "LS2 OUTRES 说明")  # 避免把 A0 端点预先定义为模态基态。
    candidate = static_base.replace_once(candidate, "! 恢复全部节点和单元选择，避免支承选择影响后续保存和模态。", "! 恢复全部节点和单元选择，避免支承选择影响后续保存和静力封板。", "ALLSEL 说明")  # 使后处理说明与静力终点一致。
    nrre_anchor = "! 每个 LS1 子步最多允许 100 次平衡迭代。" + newline + "NEQIT,100" + newline  # 构造不改变 NEQIT 的唯一非线性控制插入锚点。
    nrre_block = f"! 保存最近 {NRRE_MAXFILE} 次 Newton-Raphson 节点残差，供 A0 失败时定位；不启用 EFLG 且不改变收敛判据。" + newline + f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}" + newline + nrre_anchor  # 只增加官方 NRRE 输出，不改迭代上限或任何物理量。
    candidate = static_base.replace_once(candidate, nrre_anchor, nrre_block, "A0 NRRE 控制")  # 在首个 SOLVE 前启用一次 NRRE，使 LS1 与 LS2 均受同一诊断合同覆盖。
    candidate = static_base.replace_once(candidate, "! 离开后处理器，静力门禁全部通过后才允许进入扰动。", "! 离开后处理器；A0 静力门禁全部通过后立即结束，不进入扰动分析。", "静力结束说明")  # 明确截断边界。
    candidate = static_base.replace_once(candidate, "! 把静力门禁通过但模态未完成的阶段写入唯一 gate 状态。", "! 把 A0 静力门禁通过且等待外部 QA 的阶段写入唯一 gate 状态。", "静力状态说明")  # 防止内部命令冒充最终通过。
    candidate = static_base.replace_once(candidate, "! 该阶段不是最终结果通过，仅允许开始线性扰动。", "! 该阶段只表示求解器内静力门通过，仍必须由外部 QA 复核收敛、方程数、主元、质量和反力。", "静力结论说明")  # 冻结外部验收义务。
    candidate = static_base.replace_once(candidate, "/COM,STATUS=STATIC_GATES_PASSED PHASE=PERTURB_MODAL", "/COM,STATUS=STATIC_GATES_PASSED PHASE=EXTERNAL_QA_REQUIRED", "静力状态值")  # 把阶段从模态入口改为外部 QA 待决。
    candidate = static_base.replace_once(candidate, "! 恢复主输出，准备扰动求解。", "! 恢复主输出，准备结束 A0 静力专用 MAPDL 会话。", "退出说明")  # 使最后一条输出恢复说明与真实控制流一致。
    modal_anchor = "! 进入求解处理器并从 LS2 最高收敛帧建立线性扰动。"  # 使用父主控唯一模态入口说明作为静力截断锚点。
    require(candidate.count(modal_anchor) == 1, "C10 父主控模态截断锚点不是唯一一次")  # 锚点漂移时禁止保留半段模态或误删静力 QA。
    candidate = candidate.split(modal_anchor, 1)[0]  # 保留装配、两步静力、全部静力门、DB 保存和 gate 状态，删除全部模态命令。
    candidate += "! A0 到此结束；当前运行不生成、读取或宣称任何模态结果。" + newline  # 为最后退出命令提供逐行中文用途说明。
    candidate += "/EXIT,NOSAVE" + newline  # 正常退出 MAPDL 并保留先前显式保存的静力数据库与结果文件。
    commands = executable_commands(candidate)  # 解析最终 A0 主控的全部可执行命令供硬门计数。
    require(commands.count("SOLVE") == 2 and commands.count("ANTYPE,STATIC") == 1, "A0 不是唯一静力类型加 LS1/LS2 两次 SOLVE")  # 固定分析范围和求解次数。
    require(commands.count("KBC,0") == 2 and "KBC,1" not in commands, "A0 未逐字保留 S10 两步 KBC=0")  # 禁止形成态阶跃或迁移端点混入。
    require(commands.count("AUTOTS,ON") == 1 and commands.count("AUTOTS,OFF") == 1, "A0 未逐字保留 S10 自动步长开关")  # 固定 LS1 开启、LS2 关闭。
    require(commands.count("NSUBST,20,200,20") == 1 and commands.count("NSUBST,1,1,1") == 1, "A0 未逐字保留 S10 两步 NSUBST")  # 固定 LS1 二十起步与 LS2 单保持步。
    require(commands.count("PRED,OFF") == 1 and not any(command.startswith("PRED,") and command != "PRED,OFF" for command in commands), "A0 PRED 合同发生漂移")  # 保持 S10 关闭预测器且不做性能变量试验。
    require(commands.count(f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}") == 1 and not any(command.startswith("NLDIAG,EFLG") for command in commands), "A0 NRRE 不是唯一五十文件或混入 EFLG")  # 固定只输出节点残差。
    require(not any(command.startswith("CNVTOL,") for command in commands), "A0 意外修改 CNVTOL")  # 保持父 C10 与 S10 没有显式 CNVTOL 的原合同。
    require(not any(command.startswith("KEYOPT,72,") for command in commands), "A0 主控意外覆盖 TYPE72 KEYOPT")  # KEYOPT 必须只来自冻结连接 include 且保持 1/1、2/0、5/0。
    require(not any(command.startswith("MODOPT,") or command.startswith("PERTURB,") or ",PERTURB" in command or command.startswith("MXPAND,") for command in commands), "A0 静力主控仍含模态命令")  # 主动阻断所有模态入口与展开命令。
    require(not any("MIGRATION" in command or "C10_BETA" in command for command in commands), "A0 意外包含荷载位置迁移命令")  # 确认最短直接空间重力路径没有 beta 或修正向量。
    require(commands.count("ACEL,0,0,9806") == 2 and commands.count("TIME,1") == 1 and commands.count("TIME,1.001") == 1, "A0 重力和伪时间端点漂移")  # 固定 S10 直接空间质量重力两步端点。
    require(candidate.count(new_jobname) == 3 and old_jobname not in candidate, "A0 截断后作业名引用数或旧身份残留异常")  # 只保留 FILNAME、静力 RST 和平衡 DB 三处新身份。
    audit = {"schema_version": 1, "status": "PASSED", "source_sha256": static_base.sha256_bytes(source_bytes), "candidate_sha256": static_base.sha256_bytes(candidate.encode("utf-8")), "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "identity_change_only": True, "physical_model_change": False, "load_or_initial_state_change": False, "numerical_control_change": {"only_added_command": f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}", "cnvtol_changed": False, "keyopt_changed": False, "pred_changed": False, "neqit_changed": False}, "ls1": {"kbc": 0, "autots": True, "nsubst": [20, 200, 20], "pred": "OFF", "time": 1.0}, "ls2": {"kbc": 0, "autots": False, "nsubst": [1, 1, 1], "time": 1.001, "physical_load_increment": 0.0}, "solve_count": 2, "modal_commands_present": False, "static_only_truncated": True, "external_qa_required": True}  # 汇总 A0 唯一变更、两步控制、禁改项与结论边界。
    return candidate.encode("utf-8"), audit  # 返回可执行 UTF-8 主控字节和机器变更审计。


def validate_tool_source(path: Path, label: str) -> dict[str, Any]:  # 输入运行工具源码和标签并返回语法、逐行中文注释与用途摘要。
    require(path.is_file(), f"缺少{label}源码：{path}")  # 冻结工具前拒绝缺失源文件。
    source_text = path.read_text(encoding="utf-8", errors="strict")  # 严格读取完整 Python 源码供静态审查。
    ast.parse(source_text, filename=str(path))  # 解析整个抽象语法树，任何语法错误都会阻断准备。
    comment_violations = static_base.re.findall(r"$^", source_text)  # 构造稳定空列表占位，实际逐行规则由下方显式循环检查。
    line_violations: list[int] = []  # 初始化非空代码行缺中文说明的行号列表。
    for line_number, line in enumerate(source_text.splitlines(), start=1):  # 按一基真实行号审查每个非空物理行。
        if not line.strip():  # 空白分隔行不承载代码、声明或结束结构。
            continue  # 跳过空白行并检查下一行。
        if "#" not in line or re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", line.split("#", 1)[1]) is None:  # 每个非空行必须具有至少一个中文字符的同行说明。
            line_violations.append(line_number)  # 保存不满足全局注释合同的精确行号。
    require(not comment_violations and not line_violations, f"{label}逐行中文注释违规：{line_violations[:20]}")  # 任一违规都阻断工具冻结。
    return {"path": str(path), "sha256": static_base.sha256_file(path), "syntax_valid": True, "nonblank_line_count": sum(1 for line in source_text.splitlines() if line.strip()), "comment_violation_count": 0}  # 返回源身份与注释门摘要。


def validate_sources_and_render(new_jobname: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], bytes, dict[str, Any], dict[str, Any]]:  # 输入预览作业名并返回全部源证据、候选字节和工具审计。
    s10_evidence = validate_s10_source()  # 先证明 A0 控制来自最后一个真实成功 S10。
    parent_manifest, micro_results, include_records = validate_c10_source()  # 再证明当前 TYPE72 模型与 12/12 微验证来源有效。
    parent_dir = RUNS_ROOT / C10_RUN_NAME  # 定位已通过门禁的当前父运行目录。
    parent_bytes = (parent_dir / "solver" / C10_MAIN_NAME).read_bytes()  # 读取已哈希父主控原始字节供确定性变换。
    candidate_bytes, transform_audit = transform_main(parent_bytes, str(parent_manifest["jobname"]), new_jobname)  # 只增加 NRRE、更新身份并截断模态。
    tool_paths = [TOOLS_ROOT / EXECUTE_TOOL_NAME, TOOLS_ROOT / MONITOR_TOOL_NAME, TOOLS_ROOT / STATIC_HELPER_NAME, TOOLS_ROOT / MONITOR_HELPER_NAME]  # 冻结专用入口与两个只复用帮助函数的源文件集合。
    tool_audits = {path.name: validate_tool_source(path, path.name) for path in tool_paths}  # 逐项执行语法、逐行中文注释和摘要门。
    tools_audit = {"schema_version": 1, "status": "PASSED", "tools": tool_audits}  # 汇总全部运行工具源身份与代码规则结果。
    return s10_evidence, parent_manifest, include_records, candidate_bytes, transform_audit, {"micro_results": micro_results, "tools_audit": tools_audit}  # 返回生成阶段所需的全部已验证对象。


def validate_ledger(run_dir: Path) -> dict[str, str]:  # 输入已准备运行并返回逐项复算通过的账本映射。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 定位准备阶段最后写出的完整工件账本。
    require(ledger_path.is_file(), "A0 运行缺少 artifact_hashes.sha256")  # 没有账本时禁止声明准备闭合。
    entries: dict[str, str] = {}  # 初始化运行内相对路径到摘要的唯一映射。
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1):  # 逐行解析标准摘要账本。
        match = LEDGER_PATTERN.fullmatch(line)  # 要求每行使用冻结格式并避免宽松解析。
        require(match is not None, f"A0 账本第 {line_number} 行格式错误")  # 缺失摘要、分隔符或路径均立即失败。
        relative_text = match.group(2)  # 读取运行内 POSIX 相对路径文本。
        require(relative_text not in entries, f"A0 账本重复路径：{relative_text}")  # 禁止后值覆盖前值造成身份歧义。
        relative_path = Path(relative_text)  # 转换为本机路径对象供越界检查。
        require(not relative_path.is_absolute() and ".." not in relative_path.parts, f"A0 账本路径越界：{relative_text}")  # 禁止绝对路径或父目录逃逸。
        artifact_path = run_dir / relative_path  # 构造当前运行内真实文件路径。
        require(artifact_path.is_file() and static_base.sha256_file(artifact_path) == match.group(1), f"A0 账本工件缺失或漂移：{relative_text}")  # 复算当前字节并与冻结摘要比较。
        entries[relative_text] = match.group(1)  # 保存已通过格式、边界、存在性和摘要门的条目。
    require(len(entries) >= 25, "A0 准备账本条目异常不足二十五项")  # 防止只冻结主控而遗漏依赖、QA 或运行工具。
    return entries  # 返回供既有运行复核与未来启动器使用的完整映射。


def validate_prepared_run(run_dir: Path) -> dict[str, Any]:  # 输入唯一 A0 运行目录并返回不写盘的全包复核结果。
    resolved_run = run_dir.resolve()  # 规范化目标目录以关闭相对段歧义。
    require(resolved_run.is_dir() and resolved_run.parent == RUNS_ROOT.resolve() and resolved_run.name.startswith(RUN_PREFIX), f"目标不是批准 A0 运行：{resolved_run}")  # 只复核本项目直接子运行。
    manifest = static_base.load_json(resolved_run / "manifest.json")  # 读取准备清单原件。
    status = static_base.load_json(resolved_run / "C10_static_status.json")  # 独立读取根状态和启动权限边界。
    require(manifest.get("run_name") == resolved_run.name == status.get("run_name") and manifest.get("jobname") == status.get("jobname"), "A0 目录、清单与根状态身份不一致")  # 关闭跨目录复制和 job 错配。
    require(manifest.get("diagnostic_subtype") == DIAGNOSTIC_SUBTYPE and manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "A0 清单子类型或准备状态错误")  # 固定唯一用途和生命周期。
    require(status.get("mapdl_execution_attempted") is False and status.get("mapdl_started") is False and status.get("full_bridge_modal_status") == "NOT_RUN", "A0 根状态不是零启动或错误声称模态")  # 证明准备包没有运行结果。
    entries = validate_ledger(resolved_run)  # 逐项复算全部准备工件摘要。
    main_relative = str(manifest.get("main_input"))  # 读取唯一可执行主控运行内路径。
    require(main_relative in entries, "A0 主控未纳入准备账本")  # 禁止未冻结主控进入未来启动。
    main_path = resolved_run / main_relative  # 构造实际主控绝对路径。
    require(static_base.sha256_file(main_path) == manifest.get("main_input_sha256"), "A0 主控清单摘要漂移")  # 关闭清单、账本和真实文件三方身份。
    commands = executable_commands(main_path.read_text(encoding="utf-8", errors="strict"))  # 再次解析准备后真实主控命令。
    require(commands.count("KBC,0") == 2 and commands.count("AUTOTS,ON") == 1 and commands.count("NSUBST,20,200,20") == 1 and commands.count("PRED,OFF") == 1, "A0 准备后 S10 控制命令漂移")  # 复核最关键四项成功路径控制。
    require(commands.count(f"NLDIAG,NRRE,ON,{NRRE_MAXFILE}") == 1 and commands.count("SOLVE") == 2, "A0 准备后 NRRE 或两步静力合同漂移")  # 固定诊断输出与求解次数。
    require(not any(command.startswith("CNVTOL,") or command.startswith("KEYOPT,72,") or command.startswith("MODOPT,") or command.startswith("PERTURB,") for command in commands), "A0 准备后混入 CNVTOL、KEYOPT 或模态命令")  # 复核三类禁止变化。
    forbidden_runtime_names = ["runtime_launch_claim.json", "runtime_launch.json", "runtime_process_identity.json", "runtime_process_identity_failure.json"]  # 冻结任何实际启动都会产生的根级证据文件名。
    require(not any((resolved_run / name).exists() for name in forbidden_runtime_names), "A0 目录已存在启动或进程身份工件")  # 任一存在都推翻零启动结论。
    jobname = str(manifest.get("jobname"))  # 读取冻结作业名前缀供求解输出族检查。
    runtime_suffixes = [".out", ".err", ".lock", ".abt", ".rst", ".rdb", ".db", ".mntr", ".ldhi", ".full", ".mode"]  # 冻结 MAPDL 启动或求解可能生成的主要文件后缀。
    require(not any((resolved_run / "solver" / f"{jobname}{suffix}").exists() for suffix in runtime_suffixes), "A0 solver 已存在本 job 运行输出")  # 证明该唯一作业名从未在当前目录启动。
    return {"schema_version": 1, "status": "PASSED", "run_name": resolved_run.name, "jobname": jobname, "ledger_entry_count": len(entries), "main_input_sha256": manifest["main_input_sha256"], "s10_controls_exact": True, "current_type72_unchanged": True, "cnvtol_unchanged_absent": True, "modal_commands_present": False, "runtime_artifacts_present": False, "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回完整准备和零启动复核摘要。


def offline_self_test() -> dict[str, Any]:  # 无业务输入；只在内存中测试禁止启动路径、命令解析和源变换锚点。
    source_text = Path(__file__).read_text(encoding="utf-8", errors="strict")  # 读取准备器自身完整源码供 AST 安全审查。
    syntax_tree = ast.parse(source_text, filename=str(Path(__file__).resolve()))  # 解析真实源码结构而不是依赖关键词搜索。
    forbidden_imports = [node.names[0].name for node in ast.walk(syntax_tree) if isinstance(node, ast.Import) and node.names and node.names[0].name == "subprocess"]  # 查找任何直接 subprocess 导入。
    forbidden_from_imports = [node.module for node in ast.walk(syntax_tree) if isinstance(node, ast.ImportFrom) and node.module == "subprocess"]  # 查找任何 from subprocess 导入。
    forbidden_calls = [node.func.attr for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"Popen", "run", "call", "system"}]  # 查找典型求解器或 shell 启动调用。
    require(not forbidden_imports and not forbidden_from_imports and not forbidden_calls, "A0 准备器出现子进程或系统启动调用")  # 证明准备器没有执行 MAPDL 的代码路径。
    preview_jobname = "cw_C10a0_0101t000000000001_d1"  # 构造不与任何真实运行重合且不超过 32 字符的纯内存预览作业名。
    s10_evidence, parent_manifest, include_records, candidate_bytes, transform_audit, extra = validate_sources_and_render(preview_jobname)  # 对真实冻结源执行完整只读门和内存变换。
    require(len(preview_jobname) <= 32 and transform_audit.get("status") == "PASSED", "A0 内存变换或作业名长度自检失败")  # 固定 MAPDL 文件前缀和变换审计有效性。
    return {"schema_version": 1, "status": "PASSED", "preparer_has_subprocess_import": False, "preparer_has_process_start_call": False, "s10_source": s10_evidence, "c10_parent_run": parent_manifest["run_name"], "dependency_count": len(include_records), "candidate_sha256": static_base.sha256_bytes(candidate_bytes), "micro_validation_status": extra["micro_results"]["status"], "runtime_tool_source_gate": extra["tools_audit"]["status"], "mapdl_execution_attempted": False, "mapdl_started": False}  # 返回只读源、内存 deck 与零启动自检结果。


def generate_run() -> Path:  # 无业务输入；生成一个唯一 A0 可执行准备包并返回其绝对目录。
    created_at = datetime.now(timezone.utc)  # 记录准备动作的精确 UTC 时刻供目录、job 和证据共同使用。
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")  # 生成含微秒的不可覆盖运行目录后缀。
    run_name = f"{RUN_PREFIX}{stamp}"  # 构造明确区分 A0 与迁移、K5 或 PRED 诊断的唯一运行名。
    jobname = f"cw_C10a0_{created_at.strftime('%m%dt%H%M%S%f')}_d1"  # 构造 ASCII、含微秒且小于 32 字符的唯一 MAPDL 作业名。
    require(len(jobname) <= 32, f"A0 jobname 超过 MAPDL 32 字符限制：{jobname}")  # 防止求解器静默截断造成文件族碰撞。
    s10_evidence, parent_manifest, include_records, candidate_bytes, transform_audit, extra = validate_sources_and_render(jobname)  # 在创建目录前完成全部源、工具和内存 deck 门。
    require(MAPDL_EXE.is_file(), f"缺少冻结 MAPDL 二进制：{MAPDL_EXE}")  # 只验证未来启动入口存在，本准备器不会调用它。
    run_dir = RUNS_ROOT / run_name  # 构造本次唯一运行根目录。
    require(not run_dir.exists(), f"A0 目标运行已存在，禁止覆盖：{run_dir}")  # 任何名称碰撞都必须停止而不能复用。
    solver_dir = run_dir / "solver"  # 构造独立 MAPDL 工作目录。
    qa_dir = run_dir / "qa"  # 构造预求解、变更、零启动与工具审计目录。
    input_snapshot_dir = run_dir / "input_snapshot"  # 构造父输入和运行代码的只读快照目录。
    lineage_dir = run_dir / "lineage"  # 构造 S10/C10/微验证与历史判断证据目录。
    orchestrator_dir = run_dir / "orchestrator_snapshot"  # 构造本准备器自身源码快照目录。
    for directory in [solver_dir, qa_dir, input_snapshot_dir, lineage_dir, orchestrator_dir]:  # 按明确集合创建全部运行子目录。
        directory.mkdir(parents=True, exist_ok=False)  # 使用不可覆盖语义建立目录并拒绝任何既有对象。
    parent_dir = RUNS_ROOT / C10_RUN_NAME  # 定位已验证当前 C10 父运行供逐项复制。
    dependency_audit: list[dict[str, Any]] = []  # 初始化十一份物理 include 的复制闭合记录。
    for record in sorted(include_records, key=lambda item: int(item["order"])):  # 按父清单冻结顺序复制全部物理输入。
        name = str(record["name"])  # 读取当前依赖文件名用于源、目标和审计定位。
        source_path = parent_dir / "solver" / name  # 构造已经逐项验证的父 solver 源路径。
        target_path = solver_dir / name  # 构造本 A0 独立 solver 目标路径。
        shutil.copy2(source_path, target_path)  # 保留原始字节与文件时刻复制，不修改任何源运行。
        observed_hash = static_base.sha256_file(target_path)  # 复算复制后目标字节摘要。
        require(observed_hash == record["solver_sha256"], f"A0 复制后依赖摘要漂移：{name}")  # 复制异常时在清单生成前阻断。
        dependency_audit.append({"order": int(record["order"]), "name": name, "source_run": C10_RUN_NAME, "source_sha256": record["solver_sha256"], "solver_sha256": observed_hash, "byte_invariant": True})  # 保存顺序、谱系和逐字节不变结论。
    main_path = solver_dir / A0_MAIN_NAME  # 构造本运行唯一可执行主控路径。
    main_path.write_bytes(candidate_bytes)  # 写入已经通过命令级硬门的静力专用 APDL 字节。
    shutil.copy2(parent_dir / "solver" / C10_MAIN_NAME, input_snapshot_dir / C10_MAIN_NAME)  # 保存未修改父全模态主控供差分追溯，solver 中不保留可误启动副本。
    runtime_source_names = [EXECUTE_TOOL_NAME, MONITOR_TOOL_NAME, STATIC_HELPER_NAME, MONITOR_HELPER_NAME]  # 冻结未来启动、监控及其只复用帮助模块集合。
    for source_name in runtime_source_names:  # 逐项复制已经通过语法和逐行中文注释门的运行代码。
        shutil.copy2(TOOLS_ROOT / source_name, input_snapshot_dir / source_name)  # 把运行代码冻结在本 run 内并由最终账本保护。
    shutil.copy2(Path(__file__).resolve(), orchestrator_dir / Path(__file__).name)  # 保存实际执行的准备器源码供零启动与变换复现。
    lineage_sources = [(parent_dir / "manifest.json", "C10_parent_manifest.json"), (parent_dir / "qa" / "model_single_difference_audit.json", "C10_model_single_difference_audit.json"), (RUNS_ROOT / C10_MICRO_RUN_NAME / "unit_test_results.json", "C10_micro_unit_test_results.json"), (RUNS_ROOT / S10_RUN_NAME / "manifest.json", "S10_manifest.json"), (RUNS_ROOT / S10_RUN_NAME / "qa" / "postrun_gate.json", "S10_postrun_gate.json")]  # 定义五份直接支撑 A0 决策的冻结谱系文件。
    for source_path, target_name in lineage_sources:  # 逐项复制不修改的清单和验收原件。
        shutil.copy2(source_path, lineage_dir / target_name)  # 在运行内保存可独立哈希的证据快照。
    history_path = RUNS_ROOT / "C10_RESTART_NRRE_DIAGNOSTIC_20260802T0233180311824Z" / "qa" / "history_bisect.md"  # 定位已封板的失败历史二分结论。
    require(history_path.is_file(), f"缺少 A0 决策历史审计：{history_path}")  # 决策证据缺失时禁止只靠口头结论生成。
    shutil.copy2(history_path, lineage_dir / "history_bisect.md")  # 保存 A0 先于分组件迁移的因果顺序证据。
    execute_hash = static_base.sha256_file(input_snapshot_dir / EXECUTE_TOOL_NAME)  # 计算运行内冻结启动器摘要。
    monitor_hash = static_base.sha256_file(input_snapshot_dir / MONITOR_TOOL_NAME)  # 计算运行内冻结监控器摘要。
    static_helper_hash = static_base.sha256_file(input_snapshot_dir / STATIC_HELPER_NAME)  # 计算启动帮助模块摘要。
    monitor_helper_hash = static_base.sha256_file(input_snapshot_dir / MONITOR_HELPER_NAME)  # 计算监控帮助模块摘要。
    launch_argv = [str(MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", jobname, "-dir", str(solver_dir), "-i", str(main_path), "-o", str(solver_dir / f"{jobname}.out")]  # 构造未来明确批准的批处理 SMP1 参数数组，不含 DMP/MPI 或模态。
    launch_command = "& " + " ".join("'" + value.replace("'", "''") + "'" for value in launch_argv) + "\n"  # 生成只供审计和显式授权后的 PowerShell 命令文本。
    (run_dir / "launch_command_smp1.txt").write_text(launch_command, encoding="utf-8", newline="\n")  # 写出未来命令但绝不执行它。
    status = {"schema_version": 1, "run_name": run_name, "jobname": jobname, "status": "STATIC_DIAGNOSTIC_PREPARED", "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "created_at_utc": created_at.isoformat(), "parent_run": C10_RUN_NAME, "successful_control_reference_run": S10_RUN_NAME, "convergence_acceptance_scope": "DEFAULT_CNVTOL_DIAGNOSTIC_ONLY", "mapdl_execution_attempted": False, "mapdl_started": False, "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "launch_allowed_for_diagnostic": True, "launch_allowed_for_production": False, "full_bridge_static_status": "A0_PREPARED_NOT_STARTED", "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "next_action": "EXPLICITLY_RUN_FROZEN_A0_EXECUTE_VALIDATE_ONLY_BEFORE_ANY_SEPARATE_LAUNCH_AUTHORIZATION"}  # 冻结准备态、默认 CNVTOL 历史二分用途、零启动、资源例外和下一动作边界。
    manifest = {"schema_version": 1, "run_name": run_name, "jobname": jobname, "status": status["status"], "diagnostic_subtype": DIAGNOSTIC_SUBTYPE, "created_at_utc": created_at.isoformat(), "parent_run": C10_RUN_NAME, "successful_control_reference_run": S10_RUN_NAME, "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "constraint_imposition": "DIRECT_ELIMINATION", "expected_topology": parent_manifest["expected_topology"], "expected_equation_count": EXPECTED_EQUATION_COUNT, "main_input": f"solver/{A0_MAIN_NAME}", "main_input_sha256": transform_audit["candidate_sha256"], "controlled_include": f"solver/{C10_GATE_NAME}", "controlled_include_sha256": C10_GATE_SHA256, "dependencies": dependency_audit, "load_path_mode": "S10_DIRECT_SPATIAL_MASS21_GRAVITY_RAMP_NO_MIGRATION", "ls1": transform_audit["ls1"], "ls2": transform_audit["ls2"], "nrre": {"enabled": True, "label": "NRRE", "maxfile": NRRE_MAXFILE, "eflg_enabled": False}, "convergence_acceptance_scope": "DEFAULT_CNVTOL_DIAGNOSTIC_ONLY", "default_cnvtol_log_auto_relaxation_allowed": False, "cnvtol_explicit_command_count": 0, "cnvtol_changed": False, "if_a0_passes_next_run": "A0B_SAME_PATH_WITH_CURRENT_FOUR_EXPLICIT_CNVTOL_STATIC_ACCEPTANCE", "a0_direct_production_promotion_allowed": False, "mpc184_keyopt5_static": 0, "keyopt_changed": False, "initial_state_changed": False, "mass_changed": False, "load_changed": False, "modal_requested": False, "production_claim_allowed": False, "static_result_expected": True, "runtime_equation_count_change_allowed": False, "runtime_small_zero_negative_pivot_allowed": False, "mapdl_executable": str(MAPDL_EXE), "mapdl_executable_sha256": static_base.sha256_file(MAPDL_EXE), "execution_mode": status["execution_mode"], "launch_argv": launch_argv, "runtime_execute_script": f"input_snapshot/{EXECUTE_TOOL_NAME}", "runtime_execute_script_sha256": execute_hash, "runtime_monitor_script": f"input_snapshot/{MONITOR_TOOL_NAME}", "runtime_monitor_script_sha256": monitor_hash, "runtime_static_helper_script": f"input_snapshot/{STATIC_HELPER_NAME}", "runtime_static_helper_script_sha256": static_helper_hash, "runtime_monitor_helper_script": f"input_snapshot/{MONITOR_HELPER_NAME}", "runtime_monitor_helper_script_sha256": monitor_helper_hash}  # 汇总唯一输入、默认 CNVTOL 诊断边界、A0b 后续验收义务、禁改项、运行工具、求解器与运行时硬门。
    static_base.write_json(run_dir / "C10_static_status.json", status)  # 写出根级生命周期和权限状态。
    static_base.write_json(run_dir / "manifest.json", manifest)  # 写出完整 A0 机器清单。
    static_base.write_json(qa_dir / "a0_control_transform_audit.json", transform_audit)  # 写出只增 NRRE、静力截断和 S10 控制保持审计。
    static_base.write_json(qa_dir / "s10_success_reference.json", s10_evidence)  # 写出真实成功 S10 的直接控制来源摘要。
    static_base.write_json(qa_dir / "runtime_tools_audit.json", extra["tools_audit"])  # 写出四份运行代码语法、注释与源摘要门。
    pre_solve = {"schema_version": 1, "status": "PASSED_PREPARE_ONLY_NOT_SOLVED", "run_name": run_name, "units": {"force": "N", "length": "mm", "mass": "tonne", "time": "s"}, "source_hashes_closed": True, "dependency_count": len(dependency_audit), "topology_expected": parent_manifest["expected_topology"], "current_type72_count": 5078, "type73_count": 0, "aux_node_count": 0, "s10_controls_exact": {"KBC_0_count": 2, "AUTOTS_ON_count": 1, "NSUBST_20_200_20_count": 1, "PRED_OFF_count": 1}, "ls2_hold_exact": True, "nldiag_nrre_on_50_count": 1, "eflg_count": 0, "convergence_acceptance_scope": "DEFAULT_CNVTOL_DIAGNOSTIC_ONLY", "cnvtol_explicit_count": 0, "default_cnvtol_auto_relaxation_log_message_allowed": False, "a0b_explicit_cnvtol_acceptance_required_if_a0_passes": True, "keyopt_override_count_in_main": 0, "initial_state_sha256": INITIAL_STATE_SHA256, "deadload_sha256": DEADLOAD_SHA256, "mass21_sha256": MASS21_SHA256, "gravity_sha256": GRAVITY_SHA256, "modal_commands_present": False, "solve_count": 2, "pre_solve_only": True, "static_convergence": "NOT_RUN", "solution_verification": "NOT_RUN"}  # 冻结单位、拓扑、控制、默认 CNVTOL 历史二分边界、A0b 验收义务、依赖和未求解状态。
    static_base.write_json(qa_dir / "pre_solve_verification.json", pre_solve)  # 写出可由未来启动器和人工审查复用的预求解证据。
    preparation_ledger = {"schema_version": 1, "status": "PASSED", "run_name": run_name, "created_at_utc": created_at.isoformat(), "sources": {"s10_main_sha256": S10_MAIN_SHA256, "s10_gate_sha256": S10_GATE_SHA256, "c10_main_sha256": C10_MAIN_SHA256, "c10_gate_sha256": C10_GATE_SHA256, "micro_run": C10_MICRO_RUN_NAME}, "controlled_changes": ["UNIQUE_RUN_AND_JOB_IDENTITY", f"ADD_NLDIAG_NRRE_ON_{NRRE_MAXFILE}", "STATIC_ONLY_TRUNCATION", "STATIC_GATE_PHASE_TO_EXTERNAL_QA_REQUIRED"], "forbidden_changes_confirmed_absent": ["CNVTOL", "KEYOPT", "INITIAL_STATE", "MASS", "LOAD", "PRED", "NEQIT", "MIGRATION", "MODAL_EXECUTION"], "convergence_acceptance_scope": "DEFAULT_CNVTOL_DIAGNOSTIC_ONLY", "a0b_same_path_explicit_cnvtol_acceptance_required_if_a0_passes": True, "runtime_tools_frozen": True, "mapdl_execution_attempted": False, "mapdl_started": False}  # 汇总准备动作允许和禁止变化、默认 CNVTOL 历史二分范围、A0b 后续验收义务及零启动事实。
    static_base.write_json(qa_dir / "preparation_ledger.json", preparation_ledger)  # 写出与最终哈希账本互补的语义账本。
    self_test_evidence = {"schema_version": 1, "status": "PASSED", "preparer_has_process_start_call": False, "source_validation_passed": True, "deck_transform_passed": True, "runtime_tool_source_gate_passed": True, "candidate_sha256": transform_audit["candidate_sha256"], "mapdl_execution_attempted": False, "mapdl_started": False}  # 记录生成过程中已执行的内存自检与零启动结论。
    static_base.write_json(qa_dir / "self_test_evidence.json", self_test_evidence)  # 写出自检证据供最终账本保护。
    zero_start = {"schema_version": 1, "status": "PASSED_ZERO_START", "run_name": run_name, "jobname": jobname, "observed_at_utc": datetime.now(timezone.utc).isoformat(), "preparer_script": str(Path(__file__).resolve()), "preparer_script_sha256": static_base.sha256_file(Path(__file__).resolve()), "preparer_subprocess_import": False, "preparer_process_start_call": False, "launch_tool_executed": False, "monitor_tool_executed": False, "runtime_launch_claim_exists": False, "runtime_launch_exists": False, "runtime_process_identity_exists": False, "job_output_files_present": False, "mapdl_execution_attempted": False, "mapdl_started": False, "static_result": "NOT_RUN", "modal_result": "NOT_RUN"}  # 冻结代码路径、运行工件和结果状态三类零启动证明。
    static_base.write_json(qa_dir / "zero_start_evidence.json", zero_start)  # 写出用户要求的明确零启动证据。
    field_dictionary = "# A0 机器字段说明\n\n`STATIC_DIAGNOSTIC_PREPARED` 只表示 S10/C10 源哈希、当前 5,078 个 TYPE72、十一份依赖、A0 deck 和运行工具已通过准备门，不表示 MAPDL 已启动。LS1 严格使用 `KBC,0 / AUTOTS,ON / NSUBST,20,200,20 / PRED,OFF`；LS2 使用 `KBC,0 / AUTOTS,OFF / NSUBST,1,1,1`。本包唯一数值新增是 `NLDIAG,NRRE,ON,50`，没有 `CNVTOL`、`KEYOPT`、初始状态、质量、荷载、预测器或迭代上限变化。`DEFAULT_CNVTOL_DIAGNOSTIC_ONLY` 表示 A0 只回答“当前 TYPE72 在 S10 原始成功路径上能否重现静力”，监控器把 CNVTOL 被忽略或内部自动放宽消息列为硬事件；A0 即使通过也不得直接升格生产，必须再运行同一路径且恢复当前四项显式 CNVTOL 的 A0b 静力验收。主控在静力外部门前截断，绝不执行模态。单位为 N、mm、tonne、s。\n"  # 解释 JSON 无注释字段、两步控制、默认 CNVTOL 历史二分、A0b 义务、唯一新增、禁改项和单位。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出人读字段语义说明。
    launch_contract = f"# A0 启动与监控合同\n\n当前状态：准备完成、ANSYS 未启动。\n\n只读复核：`python -B input_snapshot/{EXECUTE_TOOL_NAME} --run-dir <本运行绝对目录> --validate-only`。该命令不得生成任何 runtime 或 solver 输出。\n\n若后续另行明确授权实际启动，才使用同一冻结脚本的 `--launch`，并立即以 `python -B input_snapshot/{MONITOR_TOOL_NAME} --run-dir <本运行绝对目录>` 附着。启动器只允许 SMP1、唯一 job、无并发 MAPDL、足够内存和磁盘；监控器只允许官方十字节 `nonlinear\\n` ABT，不调用 terminate、kill 或信号接口。\n"  # 生成人读但不执行的启动、监控和安全边界说明。
    (qa_dir / "launch_contract.md").write_text(launch_contract, encoding="utf-8", newline="\n")  # 写出未来授权动作的唯一顺序与安全要求。
    result_packet = f"# C10 A0 直接空间重力斜坡短验证准备结果\n\n状态：`STATIC_DIAGNOSTIC_PREPARED`；ANSYS 未启动。\n\n- 运行：`{run_name}`；job：`{jobname}`。\n- 当前连接：5,078 个单层 TYPE72，`KEYOPT(1/2/5)=1/0/0`；辅助节点=0，TYPE73=0。\n- 荷载路径：恢复 S10 的直接空间 MASS21 重力斜坡；LS1 为 `KBC,0 / AUTOTS,ON / NSUBST,20,200,20 / PRED,OFF`，LS2 为零增量保持。\n- 唯一新增诊断：`NLDIAG,NRRE,ON,50`；未增加或修改 CNVTOL、KEYOPT、初始状态、质量、荷载、PRED 或 NEQIT。\n- 收敛用途：`DEFAULT_CNVTOL_DIAGNOSTIC_ONLY`；日志中 CNVTOL 被忽略或内部自动放宽属于硬事件。A0 即使通过也不得直接升格正式修复，必须再做同路径且恢复当前四项显式 CNVTOL 的 A0b 静力验收。\n- 分析范围：装配、两步静力和全部静力门；模态命令已完整截断。\n- 当前没有静力结果、模态结果或生产结论。A0 若通过，先做 A0b 而不做荷载位置迁移；A0 若失败，才进入分组件迁移定位。\n"  # 生成便于人工快速确认的准备结论、默认 CNVTOL 历史二分边界、A0b 义务和后续判定逻辑。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出本运行用户可读摘要。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用账本外的全部准备工件。
    artifact_lines = [f"{static_base.sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 按相对路径稳定排序生成标准摘要行。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 最后写出覆盖全部准备工件且排除自身的不可覆盖身份账本。
    validation = validate_prepared_run(run_dir)  # 在账本落盘后立即执行一次不写盘的全包复核和零启动复核。
    require(validation.get("status") == "PASSED", "A0 生成后全包复核未通过")  # 理论上不可达；保留明确失败关闭门。
    return run_dir  # 返回已经通过源、变换、账本与零启动四层门的唯一运行目录。


def parse_args() -> argparse.Namespace:  # 无业务输入；解析四种互斥工作模式并返回命名空间。
    parser = argparse.ArgumentParser(description="准备或只读验证 C10 A0 直接空间重力斜坡静力包；本工具不启动 ANSYS。")  # 建立明确声明零启动边界的命令行接口。
    mode = parser.add_mutually_exclusive_group()  # 建立互斥模式组，防止自检、预览、生成和既有复核混用。
    mode.add_argument("--self-test", action="store_true", help="只读验证源码安全、冻结源、工具和内存 deck，不创建运行目录。")  # 提供完全零写入项目运行目录的回归模式。
    mode.add_argument("--validate-only", action="store_true", help="只读验证真实 S10/C10 源并在内存生成候选 deck，不创建运行目录。")  # 提供准备前真实源门预览。
    mode.add_argument("--validate-run", type=Path, help="只读复核一个已准备 A0 运行的账本、deck 与零启动证据。")  # 提供准备后独立复核入口。
    return parser.parse_args()  # 返回由 argparse 拒绝未知或冲突参数后的命名空间。


def main() -> None:  # 解析模式并执行一次只读自检、只读预览、既有复核或唯一新运行生成，无业务返回值。
    arguments = parse_args()  # 读取已经互斥验证的命令行参数。
    if bool(arguments.self_test):  # 显式自检时不创建任何 ultra_runs 目录或文件。
        print(json.dumps(offline_self_test(), ensure_ascii=False, allow_nan=False))  # 输出单行机器结果供调用者记录。
        return  # 自检完成后立即结束，生成路径不可达。
    if bool(arguments.validate_only):  # 显式真实源预览时只在内存构造候选 deck。
        preview_jobname = "cw_C10a0_0101t000000000002_d1"  # 使用第二个固定虚拟 job 区分自检与只读预览身份。
        s10_evidence, parent_manifest, include_records, candidate_bytes, transform_audit, extra = validate_sources_and_render(preview_jobname)  # 执行全部真实源和工具门但不写运行目录。
        preview = {"schema_version": 1, "status": "PASSED_VALIDATE_ONLY", "s10_source": s10_evidence, "c10_parent_run": parent_manifest["run_name"], "dependency_count": len(include_records), "candidate_sha256": static_base.sha256_bytes(candidate_bytes), "transform_status": transform_audit["status"], "micro_validation_status": extra["micro_results"]["status"], "runtime_tool_source_gate": extra["tools_audit"]["status"], "mapdl_execution_attempted": False, "mapdl_started": False}  # 汇总真实源预览与零启动事实。
        print(json.dumps(preview, ensure_ascii=False, allow_nan=False))  # 输出单行机器预览结果供人工或编排器复核。
        return  # 只读预览完成后立即结束，生成路径不可达。
    if arguments.validate_run is not None:  # 显式既有运行复核时只读取并复算目标工件。
        print(json.dumps(validate_prepared_run(arguments.validate_run), ensure_ascii=False, allow_nan=False))  # 输出单行全包与零启动复核结果。
        return  # 复核完成后立即结束，不修改目标运行或账本。
    generated_run = generate_run()  # 默认模式在全部前置门通过后生成一个不可覆盖 A0 运行包。
    print(str(generated_run))  # 输出唯一绝对目录供后续只读复核和人工交接。


if __name__ == "__main__":  # 仅在直接执行本工具时进入模式解析，导入时不读取或写入任何运行目录。
    main()  # 执行一次零启动的 A0 自检、预览、复核或准备流程。
