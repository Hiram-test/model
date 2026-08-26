"""生成并可选执行附件 2-3 V2.0 有限刚度模态模型。

本脚本只承担“装配求解输入、执行 MAPDL、检查求解器退出状态”三项职责。
门架/横向通道的几何拓扑由 ``builder`` 子目录中的独立生成器负责，集中质量
空间化由本目录中的质量生成器负责。把三项职责拆开，可以在后续标定截面或质量时
复用同一套权威索网、支承与初始索力，避免手工编辑大型 APDL 文件。

坐标与单位：X 顺桥、Y 横桥、Z 竖向；N、mm、tonne、s。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path


# SCRIPT_DIR 是 V2.0 工作目录；所有相对路径都以脚本所在位置为基准，
# 从而允许用户从任意当前工作目录调用本脚本。
SCRIPT_DIR = Path(__file__).resolve().parent
# WORKSPACE_ROOT 是项目根目录。``SCRIPT_DIR.parents[0]`` 是
# ``03_猫道动力分析``，因而 ``parents[1]`` 稳定指向项目根目录。
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
# SOURCE_RUN_DIR 保存已经核验过的 X 顺桥索网、支承、初始索力和重力输入。
SOURCE_RUN_DIR = (
    WORKSPACE_ROOT / "03_猫道动力分析" / "第一阶模态验证_V1.0"
)
# BUILDER_DIR 保存有限刚度门架/横向通道生成器及其机器可读产物。
BUILDER_DIR = SCRIPT_DIR / "builder"
# BUILDER_OUTPUT_DIR 是生成器默认的封板产物目录；源码与大体量台账分目录存放，
# 可以避免质量脚本把 Python 源文件误当作模型输入复制。
BUILDER_OUTPUT_DIR = BUILDER_DIR / "generated"
# RUN_DIR 是 MAPDL 的唯一工作目录，防止大型临时文件散落到源码目录。
RUN_DIR = SCRIPT_DIR / "run"
# FINITE_INCLUDE_NAME 是有限刚度拓扑的统一 APDL 接口文件名。
FINITE_INCLUDE_NAME = "apply_finite_gates_and_passages_v2.inp"
# MASS_INCLUDE_NAME 是空间化集中质量的统一 APDL 接口文件名。
MASS_INCLUDE_NAME = "apply_dynamic_mass21_spatialized_v2.inp"
# MAIN_INPUT_NAME 是本脚本生成的完整静力—线性扰动模态输入文件名。
MAIN_INPUT_NAME = "run_attachment23_v2.inp"
# JOBNAME 同时决定 MAPDL 的数据库、结果、线性扰动结果和临时文件名前缀。
JOBNAME = "attachment23_v2"
# MAPDL_EXE 指向本机已经用于 V1.0 成功求解的 ANSYS 2026 R1 可执行程序。
MAPDL_EXE = Path(
    r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
)


# AUTHORITATIVE_INPUTS 明确列出不得被 V2.0 生成器重写的权威基础输入。
# 旧的门架 CP 和横通道 CP 故意不在此列表中，因为它们正是本轮需要替换的对象。
AUTHORITATIVE_INPUTS = (
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_downpull_equivalent_xlong.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_authoritative_mct_gravity_v1.inp",
)


def copy_required_inputs() -> None:
    """把权威基础输入和两个 V2.0 生成 include 复制到求解目录。

    参数：
        无。

    返回：
        无。函数在 ``RUN_DIR`` 中建立或覆盖同名求解输入。

    异常：
        任一源文件缺失时抛出 ``FileNotFoundError``，防止 MAPDL 在缺件模型上继续。
    """

    # 求解目录可以重复创建；exist_ok=True 只保证目录存在，不会删除既有求解证据。
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    # 逐项复制权威输入。显式循环便于在缺失时指出具体文件，而不是复制半套模型后失败。
    for input_name in AUTHORITATIVE_INPUTS:
        # source_path 是经 V1.0 静力与模态链核验过的原始文件。
        source_path = SOURCE_RUN_DIR / input_name
        # 文件不存在说明工作区被移动、清理或版本不完整；此时严禁静默跳过。
        if not source_path.is_file():
            raise FileNotFoundError(f"缺少权威基础输入：{source_path}")
        # copy2 同时保留修改时间，便于后续审计判断输入是否发生变化。
        shutil.copy2(source_path, RUN_DIR / input_name)

    # finite_source 是 builder 输出的有限刚度门架与横向通道统一 include。
    finite_source = BUILDER_OUTPUT_DIR / FINITE_INCLUDE_NAME
    # 只有实际生成过有限拓扑后才允许进入求解，绝不退回旧 CP 简化。
    if not finite_source.is_file():
        raise FileNotFoundError(
            f"缺少有限刚度拓扑：{finite_source}；请先运行 builder 生成器。"
        )
    # 复制而不是跨目录 /INPUT，使最终 run 目录本身就是一份可复算快照。
    shutil.copy2(finite_source, RUN_DIR / FINITE_INCLUDE_NAME)

    # mass_source 是质量空间化生成器输出；它必须与当前有限拓扑节点号一致。
    mass_source = SCRIPT_DIR / MASS_INCLUDE_NAME
    # 缺失质量文件时继续使用旧集中质量会破坏转动惯量，因此直接停止。
    if not mass_source.is_file():
        raise FileNotFoundError(
            f"缺少空间化质量输入：{mass_source}；请先生成质量映射。"
        )
    # 复制质量 include，保证求解快照不会随上级文件的后续修改而变化。
    shutil.copy2(mass_source, RUN_DIR / MASS_INCLUDE_NAME)


def build_main_input(mode_count: int, upper_frequency_hz: float) -> Path:
    """生成完整的非线性静力—线性扰动模态 APDL 输入。

    参数：
        mode_count：Block Lanczos 最多提取的特征阶数，同时也是导出的振型数。
        upper_frequency_hz：特征值搜索的频率上限，单位 Hz。

    返回：
        生成的 APDL 主输入文件绝对路径。

    说明：
        输入文件显式排除旧门架三向 CP 和旧横通道 ``CP,UY``。静力拓扑变化后
        必须重新求非线性平衡；不能直接复用 V1.0 的线性扰动结果。
    """

    # 非正阶数没有物理意义，也会使 MXPAND/MODOPT 生成无效命令。
    if mode_count <= 0:
        raise ValueError("mode_count 必须为正整数。")
    # 频率上限必须覆盖附件最高目标 0.1744 Hz，并留出候选分支诊断余量。
    if upper_frequency_hz <= 0.1744:
        raise ValueError("upper_frequency_hz 必须大于附件最高目标 0.1744 Hz。")

    # lines 按 MAPDL 实际执行顺序保存命令；最后一次性写盘，避免生成半截输入。
    lines: list[str] = [
        "! ============================================================================",
        "! 附件2-3 V2.0：有限刚度门架、完整21品横向通道及空间化质量模态核算。",
        "! 坐标：X顺桥、Y横桥、Z竖向；单位：N、mm、tonne、s。",
        "! 本模型严禁调用旧门架CP文件和旧横通道CP,UY文件。",
        "! ============================================================================",
        "/CLEAR,START",
        f"/FILNAME,{JOBNAME}",
        "/TITLE,Attachment 2-3 Finite Gate and Passage Modal Model V2.0",
        "",
        "! 1. 读取权威索网与横梁，并把归档BEAM4转换为线性扰动支持的BEAM188。",
        "/INPUT,full_line_beam4_crossbeam_mesh_xlong,inp",
        "/INPUT,convert_crossbeams_beam4_to_beam188,inp",
        "! 下拉索和MCT位移支承仍采用已经完成静力等价核验的正式V1.1输入。",
        "/INPUT,apply_mct_downpull_equivalent_xlong,inp",
        "/INPUT,apply_mct_constraints_xlong,inp",
        "",
        "! 2. 恢复权威LINK180初始索力；随后建立真正有限刚度的门架和横向通道。",
        "/INPUT,apply_mct_authoritative_initial_state_link180,inp",
        f"/INPUT,{Path(FINITE_INCLUDE_NAME).stem},inp",
        "! 旧模型每根独立横梁的ROTY锚仅消除BEAM188数值钻转，不冻结门架/通道转动。",
        "/INPUT,apply_modal_roty_stabilization_xlong,inp",
        "/INPUT,define_representative_rope_component,inp",
        "",
        "! 3. 先读取MCT权威二期重量，再由V2.0质量文件删除FZ并在真实空间位置重建MASS21。",
        "/INPUT,apply_authoritative_mct_deadload_v1,inp",
        f"/INPUT,{Path(MASS_INCLUDE_NAME).stem},inp",
        "/INPUT,apply_authoritative_mct_gravity_v1,inp",
        "",
        "! 4. 求解前输出拓扑数量；该文件用于确认CP简化没有重新混入。",
        "/PREP7",
        "ALLSEL,ALL",
        "*GET,V2_NCOUNT,NODE,0,COUNT",
        "*GET,V2_ECOUNT,ELEM,0,COUNT",
        "/OUTPUT,v2_topology_counts,txt",
        "*VWRITE,V2_NCOUNT,V2_ECOUNT",
        "('NODE_COUNT=',F12.0,', ELEMENT_COUNT=',F12.0)",
        "/OUTPUT",
        "! MAPDL 2026 R1 不支持 *GET,CE,0,COUNT；用原生 CELIST 保存全部方程作独立审计。",
        "/OUTPUT,v2_constraint_equations,txt",
        "CELIST,ALL",
        "/OUTPUT",
        "FINISH",
        "",
        "! 5. 新增有限刚度构件和质量改变了平衡方程，必须重新求横向自由的非线性静力基态。",
        "/SOLU",
        "ANTYPE,STATIC",
        "NLGEOM,ON",
        "PSTRES,ON",
        "NROPT,FULL",
        "KBC,0",
        "AUTOTS,ON",
        "! 有限构件使每次结果写盘显著增大；以4个初始子步加载，并允许AUTOTS最多细分到50步。",
        "NSUBST,4,50,1",
        "NEQIT,100",
        "LNSRCH,ON",
        "! 线性扰动只需要最终收敛状态；中间子步不写全量梁结果，避免无谓的百秒级I/O。",
        "OUTRES,ALL,LAST",
        "RESCONTROL,DEFINE,ALL,LAST",
        "SOLVE",
        "FINISH",
        "",
        "! 6. 在已收敛结果上核对完整平动质量和竖向反力闭合。",
        "/POST1",
        "SET,LAST",
        "ALLSEL,ALL",
        "*GET,V2_MTOTX,ELEM,0,MTOT,X",
        "NSEL,S,D,UZ",
        "*GET,V2_QN,NODE,0,COUNT",
        "*GET,V2_NODE,NODE,0,NUM,MIN",
        "V2_RFZ=0",
        "*DO,V2_I,1,V2_QN",
        "  *GET,V2_RF,NODE,V2_NODE,RF,FZ",
        "  V2_RFZ=V2_RFZ+V2_RF",
        "  *GET,V2_NODE,NODE,V2_NODE,NXTH",
        "*ENDDO",
        "V2_RFERR=V2_RFZ-AUTH_TOT2*1000",
        "/OUTPUT,v2_static_mass_closure,txt",
        "*VWRITE,V2_MTOTX,V2_QN,V2_RFZ,V2_RFERR",
        "('MASS_TONNE=',E24.16,', UZ_SUPPORTS=',F12.0,', RFZ_N=',E24.16,', ERROR_N=',E24.16)",
        "/OUTPUT",
        "ALLSEL,ALL",
        "SAVE,attachment23_v2_equilibrium,db",
        "FINISH",
        "",
        "! 7. 从当前大变形/预应力切线状态执行线性扰动模态，不能改用传统PSTRES模态。",
        "/SOLU",
        "ANTYPE,STATIC,RESTART,,,PERTURB",
        "PERTURB,MODAL,AUTO,CURRENT,PARKEEP",
        "SOLVE,ELFORM",
        "LUMPM,OFF",
        f"MODOPT,LANB,{mode_count},0,{upper_frequency_hz:.9f}",
        f"MXPAND,{mode_count},,,NO",
        "OUTRES,ALL,NONE",
        "OUTRES,NSOL,ALL",
        "SOLVE",
        "FINISH",
        "",
        "! 8. 频率和全节点特征向量来自RSTP；每阶单独成文件供自动形态识别。",
        "/POST1",
        f"FILE,{JOBNAME},rstp",
        "! 先激活最后一个真实结果集，再从结果文件读取实际可用结果集总数。",
        "! 频率上限可能使实际阶数小于MODOPT请求值，后续全部导出均以该实际数为上限。",
        "SET,LAST",
        "*GET,V2_AVAILABLE_MODES,ACTIVE,0,SET,NSET",
        f"V2_REQUESTED_MODES={mode_count}",
        "V2_EXPORTED_MODES=V2_REQUESTED_MODES",
        "*IF,V2_AVAILABLE_MODES,LT,V2_EXPORTED_MODES,THEN",
        "  V2_EXPORTED_MODES=V2_AVAILABLE_MODES",
        "*ENDIF",
        "! 独立清单同时记录请求数、实际数和导出数，供Python端做闭环校验。",
        "/OUTPUT,v2_modal_export_manifest,txt",
        "*VWRITE,V2_REQUESTED_MODES,V2_AVAILABLE_MODES,V2_EXPORTED_MODES",
        "('REQUESTED=',F12.0,', AVAILABLE=',F12.0,', EXPORTED=',F12.0)",
        "/OUTPUT",
        "/OUTPUT,v2_modal_set_list,txt",
        "SET,LIST",
        "/OUTPUT",
        "/OUTPUT,v2_modal_frequencies,txt",
    ]

    # 逐阶生成 *GET/*VWRITE，而不是依赖表格文本列宽，保证频率 CSV 可稳定解析。
    for mode_index in range(1, mode_count + 1):
        # parameter_name 采用四位序号，避免阶数超过99时与其他参数重名。
        parameter_name = f"V2_F{mode_index:04d}"
        # 只有真实结果集覆盖本阶时才读取频率；这一步防止频率上限截断后写出伪零值。
        lines.append(f"*IF,V2_EXPORTED_MODES,GE,{mode_index},THEN")
        # 每一阶从 MODE 实体直接读取频率，避免解析易受列宽影响的 SET,LIST 文本。
        lines.append(f"*GET,{parameter_name},MODE,{mode_index},FREQ")
        # 第一列写整数阶次，第二列写双精度科学计数频率。
        lines.append(f"*VWRITE,{mode_index},{parameter_name}")
        lines.append("(F8.0,',',E24.16)")
        # 每一个条件块显式闭合，保证请求阶数大于实际阶数时不会进入无效 *GET。
        lines.append("*ENDIF")
    # 频率写完后恢复标准输出，防止后续 PRNSOL 混入频率文件。
    lines.extend(["/OUTPUT", ""])

    # mode_index 循环为每一阶建立独立全节点位移文件；节点坐标由后处理读取基础/生成CSV。
    for mode_index in range(1, mode_count + 1):
        # mode_file_stem 使用两位起步、自动扩展的格式，兼容现有 V1.0 文件命名。
        # 文件名严格遵循自动识别流水线公开协议 ``mode_XX_all_nodes.txt``；
        # 模型版本由所在 V2.0/run 目录表达，不在文件名中再追加后缀。
        mode_file_stem = f"mode_{mode_index:02d}_all_nodes"
        # 只有本阶确实存在时才执行 SET；这是修复“请求50阶、实际仅41阶、SET 42报错”的核心保护。
        lines.append(f"*IF,V2_EXPORTED_MODES,GE,{mode_index},THEN")
        # SET,1,n 显式选择线性扰动第 n 阶结果，避免依赖当前活动结果集。
        lines.append(f"SET,1,{mode_index}")
        # ALLSEL 确保门架、通道和索网节点全部进入形态诊断，而非只看代表底索。
        lines.append("ALLSEL,ALL")
        lines.append(f"/OUTPUT,{mode_file_stem},txt")
        lines.append("PRNSOL,U,COMP")
        lines.append("/OUTPUT")
        # 条件块在文件输出恢复后闭合，确保不存在的阶次既不 SET，也不创建空文本文件。
        lines.append("*ENDIF")

    # 保存后处理数据库并正常退出，使批处理日志出现明确的 RUN COMPLETED。
    lines.extend(
        [
            "ALLSEL,ALL",
            "SAVE,attachment23_v2_modal,db",
            "FINISH",
            "/EXIT,NOSAVE",
        ]
    )

    # main_input_path 是唯一主输入；newline='\n' 让 MAPDL 在 Windows 上也获得稳定行结束。
    main_input_path = RUN_DIR / MAIN_INPUT_NAME
    # UTF-8 与现有中文 APDL 注释一致；命令和文件名本身均为 ASCII。
    main_input_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return main_input_path


def clear_previous_text_evidence() -> None:
    """在新一轮 MAPDL 批处理前清理会造成“新旧结果混读”的小型文本证据。

    参数：
        无。清理范围固定在 ``RUN_DIR`` 内，不接受外部路径输入。

    返回：
        无。函数仅删除可由本脚本重新生成的模态文本、清单和闭合校核文本；
        不删除数据库、结果文件或任何变体求解文件。

    安全说明：
        每个待删文件都先解析为绝对路径并核对父目录严格等于 ``RUN_DIR``，避免
        通配符或符号链接把删除范围扩展到工作区其他位置。
    """

    # resolved_run_dir 是允许删除的唯一父目录；后续逐文件执行严格父目录比较。
    resolved_run_dir = RUN_DIR.resolve()
    # exact_names 仅包含本脚本每次都会重建的小型证据文件，不触碰任何求解二进制。
    exact_names = (
        "v2_modal_export_manifest.txt",
        "v2_modal_set_list.txt",
        "v2_modal_frequencies.txt",
        "v2_static_mass_closure.txt",
        "v2_topology_counts.txt",
        "v2_constraint_equations.txt",
    )
    # candidates 先收集固定文件，再加入按公开协议命名的旧模态向量文本。
    candidates = [RUN_DIR / file_name for file_name in exact_names]
    candidates.extend(RUN_DIR.glob("mode_*_all_nodes.txt"))
    # 逐个文件核验路径并删除；目录、其他扩展名和变体文件均不会进入本循环。
    for candidate in candidates:
        # resolved_candidate 消解相对段，防止表面位于 RUN_DIR、实际指向外部的路径通过。
        resolved_candidate = candidate.resolve()
        # 父目录不一致属于程序配置错误，宁可停止也不执行越界删除。
        if resolved_candidate.parent != resolved_run_dir:
            raise RuntimeError(f"拒绝删除求解目录之外的文件：{resolved_candidate}")
        # 只删除普通文件；不存在表示首次运行，目录则保留并由后续一致性检查报错。
        if resolved_candidate.is_file():
            resolved_candidate.unlink()


def parse_modal_export_manifest(manifest_path: Path) -> tuple[int, int, int]:
    """解析 MAPDL 写出的模态导出数量闭环清单。

    参数：
        manifest_path：``v2_modal_export_manifest.txt`` 的绝对或相对路径。

    返回：
        ``(requested, available, exported)`` 三个整数，依次表示请求阶数、结果文件
        实际阶数和最终导出阶数。

    异常：
        文件缺失、格式不匹配、数量非正或 ``exported`` 不等于两者最小值时抛出异常。
    """

    # 清单只包含 ASCII 关键字和数字；errors='replace' 不会掩盖这些必需字段。
    if not manifest_path.is_file():
        raise FileNotFoundError(f"缺少模态导出清单：{manifest_path}")
    manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
    # 正则允许 MAPDL 的 F 格式在等号后插入任意空白，并接受尾随小数点。
    match = re.search(
        r"REQUESTED=\s*([0-9]+(?:\.[0-9]*)?)\s*,\s*"
        r"AVAILABLE=\s*([0-9]+(?:\.[0-9]*)?)\s*,\s*"
        r"EXPORTED=\s*([0-9]+(?:\.[0-9]*)?)",
        manifest_text,
    )
    # 没有完整三字段说明 APDL 后处理没有执行到清单写出位置，不能继续接受结果。
    if match is None:
        raise RuntimeError(f"无法解析模态导出清单：{manifest_path}")
    # MAPDL 使用 F12.0 写整数，先转 float 再转 int 可兼容“41.”格式。
    requested, available, exported = (
        int(float(match.group(field_index))) for field_index in range(1, 4)
    )
    # 至少需要一个模态；零值意味着特征值提取或结果文件读取失败。
    if min(requested, available, exported) <= 0:
        raise RuntimeError(
            "模态导出数量必须全部为正："
            f"requested={requested}, available={available}, exported={exported}"
        )
    # APDL 条件保护的契约是导出两者最小值；任何偏差都表明输入未按预期执行。
    if exported != min(requested, available):
        raise RuntimeError(
            "模态导出数量闭环失败："
            f"requested={requested}, available={available}, exported={exported}"
        )
    return requested, available, exported


def run_mapdl(input_path: Path, processor_count: int) -> Path:
    """以批处理方式运行 MAPDL 并验证进程与日志状态。

    参数：
        input_path：由 ``build_main_input`` 生成的 APDL 输入文件。
        processor_count：MAPDL 使用的本地并行进程数。

    返回：
        MAPDL 主输出文件绝对路径。

    异常：
        可执行程序缺失、进程返回码非零或日志没有 ``RUN COMPLETED`` 时抛出异常。
    """

    # 非正处理器数会被 MAPDL 拒绝，提前报错比等待许可证初始化后失败更清楚。
    if processor_count <= 0:
        raise ValueError("processor_count 必须为正整数。")
    # 本机安装路径是既有 V1.0 成功求解链的一部分；缺失时不得换用未知版本。
    if not MAPDL_EXE.is_file():
        raise FileNotFoundError(f"找不到 MAPDL 可执行程序：{MAPDL_EXE}")
    # 新一轮执行前删除旧的小型文本证据，防止求解中途失败后被旧文件伪装成新结果。
    clear_previous_text_evidence()
    # output_path 收集完整求解器输出，是判断收敛、警告和特征值数量的原始证据。
    output_path = RUN_DIR / "attachment23_v2.out"
    # command 使用参数列表而非拼接命令行，避免中文路径或空格被错误拆分。
    command = [
        str(MAPDL_EXE),
        "-b",
        "-np",
        str(processor_count),
        "-dir",
        str(RUN_DIR),
        "-j",
        JOBNAME,
        "-i",
        str(input_path),
        "-o",
        str(output_path),
    ]
    # check=False 允许先读取日志再给出包含返回码的自定义异常信息。
    completed = subprocess.run(command, cwd=RUN_DIR, check=False)
    # 非零返回码表示许可证、输入或求解器级错误，不能仅凭部分输出继续后处理。
    if completed.returncode != 0:
        raise RuntimeError(
            f"MAPDL 返回码为 {completed.returncode}；请检查 {output_path}。"
        )
    # errors='replace' 只影响罕见的本地编码字符，不会隐藏 ASCII 状态关键字。
    output_text = output_path.read_text(encoding="utf-8", errors="replace")
    # MAPDL 即使在后处理出现“Load set not found”也可能写 RUN COMPLETED 并返回0；
    # 因此必须先拒绝任何原生错误块或“因错误终止”标志，再检查正常结束标志。
    error_count_matches = re.findall(
        r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*([0-9]+)",
        output_text,
    )
    # 取所有阶段错误计数的最大值；不存在汇总行时仍由显式错误标志兜底。
    maximum_error_count = max(
        (int(value) for value in error_count_matches),
        default=0,
    )
    # explicit_error_marker 覆盖标准“*** ERROR ***”以及求解器的错误终止横幅。
    explicit_error_marker = (
        "*** ERROR ***" in output_text
        or "PROBLEM TERMINATED BY INDICATED ERROR" in output_text
    )
    # 任何错误都使本轮失败；警告保留在日志中但不在这里一刀切拒绝。
    if maximum_error_count > 0 or explicit_error_marker:
        raise RuntimeError(
            "MAPDL 日志包含错误："
            f"error_count={maximum_error_count}；请检查 {output_path}。"
        )
    # RUN COMPLETED 是 ANSYS 正常批处理结束的原生标志；缺失时视作未完成。
    if "RUN COMPLETED" not in output_text:
        raise RuntimeError(f"MAPDL 日志没有 RUN COMPLETED：{output_path}")
    # 读取 APDL 写出的数量清单，并核对全节点向量文件与实际导出数完全一致。
    _requested, _available, exported = parse_modal_export_manifest(
        RUN_DIR / "v2_modal_export_manifest.txt"
    )
    # 正式附件比对至少需要14个独立结果集；不足时即使求解器无错误也不构成交付。
    if exported < 14:
        raise RuntimeError(f"实际仅导出 {exported} 阶，少于附件要求的14个目标分支。")
    # expected_mode_files 是从1开始连续编号的完整清单，不允许缺阶或用旧高阶文件补位。
    expected_mode_files = [
        RUN_DIR / f"mode_{mode_index:02d}_all_nodes.txt"
        for mode_index in range(1, exported + 1)
    ]
    # missing_mode_files 只记录不存在或空文件；空 PRNSOL 文件同样不能进入后处理。
    missing_mode_files = [
        path for path in expected_mode_files if not path.is_file() or path.stat().st_size == 0
    ]
    # 缺少任一连续向量都会破坏全局一对一分配，直接给出前几个缺件路径。
    if missing_mode_files:
        preview = ", ".join(str(path) for path in missing_mode_files[:5])
        raise RuntimeError(f"模态向量导出不连续或为空：{preview}")
    return output_path


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。

    参数：
        无；参数来自当前进程命令行。

    返回：
        包含 ``run``、``np``、``modes`` 和 ``upper_frequency`` 的命名空间。
    """

    # parser 的说明文字直接展示给命令行用户，明确默认操作只生成、不盲目开跑。
    parser = argparse.ArgumentParser(description=__doc__)
    # --run 是显式执行开关；省略时只准备可审阅的输入快照。
    parser.add_argument("--run", action="store_true", help="生成输入后立即运行 MAPDL。")
    # 四进程与 V1.0 已验证运行配置一致，兼顾许可证与内存占用。
    parser.add_argument("--np", type=int, default=4, help="MAPDL 并行进程数，默认4。")
    # 当前0.30 Hz窗口实测有41个结果集；默认请求40阶可覆盖目标分支并避免无谓的边界截断。
    # 即使用户显式请求更多阶，APDL中的实际阶数保护仍会安全截断导出，不再执行无效SET。
    parser.add_argument(
        "--modes",
        type=int,
        default=40,
        help="最多提取并导出的模态阶数，默认40；实际导出数取请求数与结果集数的较小值。",
    )
    # 0.30 Hz 为附件最高目标的约1.72倍，可容纳错序和局部分支诊断。
    parser.add_argument(
        "--upper-frequency",
        type=float,
        default=0.30,
        help="Block Lanczos 频率上限/Hz，默认0.30。",
    )
    return parser.parse_args()


def main() -> None:
    """准备 V2.0 输入，并在用户显式指定 ``--run`` 时执行 MAPDL。

    参数：
        无。

    返回：
        无。执行结果通过生成文件和标准输出路径体现。
    """

    # args 保存本次运行的全部可调求解参数，后续函数不再直接读取命令行。
    args = parse_arguments()
    # 现有runner固定写共享run目录并复用attachment23_v2作业名，已经造成不同模态作业
    # 覆盖同名二进制。按照当前“不得启动新求解、必须单作业强绑定”的决定，在新的
    # run_id目录、唯一jobname和完整manifest机制完成前，入口必须硬失败；不能仅靠说明
    # 文字或调用者自觉避免再次污染。
    raise RuntimeError(
        "当前V2动力runner已禁用：不得运行或生成共享目录输入。"
        "重新启用前必须实现独立run_id目录、唯一jobname和逐文件SHA-256 manifest。"
    )
    # 先复制并验证全部 include，避免生成引用缺失文件的主输入。
    copy_required_inputs()
    # main_input 是已经闭合的静力—模态 APDL 输入路径。
    main_input = build_main_input(args.modes, args.upper_frequency)
    # 未指定 --run 时只打印输入路径，供人工审阅或调度系统后续启动。
    if not args.run:
        print(main_input)
        return
    # 指定 --run 后执行 MAPDL，并打印原生主日志路径作为最小可追溯输出。
    output_path = run_mapdl(main_input, args.np)
    print(output_path)


# 只有脚本作为主程序运行时才执行；被质量或后处理脚本导入时不会意外启动求解。
if __name__ == "__main__":
    main()
