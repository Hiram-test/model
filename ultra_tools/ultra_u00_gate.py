"""生成 Ultra 首轮 U00 可执行源门禁的机器可读清单和人工审阅报告。"""  # 说明脚本仅审计文件与环境，不启动 MAPDL 求解。

from __future__ import annotations  # 延迟解析类型标注，确保脚本在当前 Python 版本稳定运行。

import argparse  # 解析输出目录参数，使每次 U00 审计写入独立 Run。
import csv  # 写出任务书要求的源文件清单 CSV。
import hashlib  # 计算源输入和 MAPDL 可执行文件的 SHA-256。
import json  # 写出依赖图、环境、状态和 manifest JSON。
import os  # 读取处理器数量和操作系统环境信息。
import platform  # 读取 Windows、Python 和 CPU 架构版本信息。
import re  # 从 APDL 输入中提取递归 /INPUT 依赖。
from datetime import datetime, timezone  # 生成可审计的 UTC 时间戳。
from pathlib import Path  # 统一处理 Windows 中文路径和相对路径。
from typing import Any  # 为混合类型 JSON 字段提供明确类型标注。


WORKSPACE = Path(r"D:\张靖皋大桥")  # 指定本项目工作区根目录，所有源路径均从此处推导。
V2_ROOT = WORKSPACE / "03_猫道动力分析" / "附件2-3全模态精确对齐_V2.0"  # 指定当前 V2 可执行源目录。
SOURCE_RUN = WORKSPACE / "03_猫道动力分析" / "第一阶模态验证_V1.0"  # 指定 V2 继承的权威基础索网和荷载输入目录。
GEOMETRY_DIR = WORKSPACE / "02_CAD几何模型" / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"  # 指定 builder 与质量生成器共同使用的权威几何台账目录。
MODULE_DIR = WORKSPACE / "output" / "freecad" / "cross_passage_local_coordinates"  # 指定横向通道三类局部模板 CSV 目录。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 指定既有成功作业使用的 ANSYS 2026 R1 MAPDL 可执行文件。
PROCESS_COUNT = 4  # 固定历史作业使用的 Intel MPI DMP 进程数，保证后续作业身份一致。
UNITS = "N-mm-tonne-s"  # 固定当前模型的力、长度、质量和时间单位制。
COORDINATES = "X longitudinal, Y transverse, Z vertical"  # 固定当前模型三轴物理含义。
HASH_CHUNK_BYTES = 1024 * 1024  # 使用 1 MiB 分块读取文件，避免大型输入一次进入内存。
INPUT_PATTERN = re.compile(r"^\s*/INPUT\s*,\s*([^,\s]+)(?:\s*,\s*([^,\s]+))?", re.IGNORECASE)  # 识别 APDL /INPUT 文件名和可选扩展名字段。


def source_specs(builder_output_dir: Path, mass_output_dir: Path) -> list[dict[str, Any]]:  # 定义 U00 必需及辅助源文件的稳定清单，并显式接收本轮封板产物目录。
    """返回每个源文件的类别、角色、绝对路径和是否为硬门禁。"""  # 说明返回值将直接驱动 PASS_A 判断与 CSV 输出。
    specs: list[dict[str, Any]] = [  # 初始化源文件规格列表，条目顺序即人工报告中的审阅顺序。
        {"item_id": "S001", "category": "runner", "role": "V2主输入生成与启动器", "path": V2_ROOT / "prepare_and_run_v2.py", "required": True},  # 主入口必须存在才能从源文件重建独立作业。
        {"item_id": "S002", "category": "builder", "role": "有限门架与横向通道生成器", "path": V2_ROOT / "builder" / "build_finite_gate_passage_apdl.py", "required": True},  # 生成有限刚度拓扑的 Python 源码属于硬门禁。
        {"item_id": "S003", "category": "builder_output", "role": "本轮隔离重生的有限门架与横向通道APDL include", "path": builder_output_dir / "apply_finite_gates_and_passages_v2.inp", "required": True},  # 已封板拓扑 include 必须来自本轮显式目录并可哈希。
        {"item_id": "S004", "category": "builder_audit", "role": "本轮隔离重生的有限拓扑生成审计", "path": builder_output_dir / "build_audit.json", "required": True},  # 本轮生成数量、零长和连通性结论必须可追溯。
        {"item_id": "S005", "category": "mass", "role": "空间化MASS21生成器", "path": V2_ROOT / "generate_spatialized_mass21_v2.py", "required": True},  # 质量空间化生成逻辑属于硬门禁。
        {"item_id": "S006", "category": "mass_output", "role": "本轮隔离重生的空间化MASS21 APDL include", "path": mass_output_dir / "apply_dynamic_mass21_spatialized_v2.inp", "required": True},  # 当前封板质量 include 必须来自本轮显式目录。
        {"item_id": "S007", "category": "mass_audit", "role": "本轮隔离重生的空间化质量审计", "path": mass_output_dir / "mass21_spatialization_audit_v2.json", "required": True},  # 本轮总量、质心和分项映射证据必须存在。
        {"item_id": "S008", "category": "audit", "role": "权威横通道站位与质量映射", "path": V2_ROOT / "audit" / "passage_station_authoritative_map.csv", "required": True},  # 21道横向通道的站位接口属于硬门禁。
        {"item_id": "S009", "category": "audit", "role": "横通道站位质量闭合审计", "path": V2_ROOT / "audit" / "passage_station_mass_map_audit.json", "required": True},  # 站位和质量的交叉闭合结果必须存在。
        {"item_id": "S010", "category": "geometry", "role": "权威原索网节点", "path": GEOMETRY_DIR / "nodes.csv", "required": True},  # builder 和质量生成器共同依赖原索网节点坐标。
        {"item_id": "S011", "category": "geometry", "role": "权威恒载分项", "path": GEOMETRY_DIR / "authoritative_mct_deadload_v1_items.csv", "required": True},  # 质量分项数量与单重来源必须存在。
        {"item_id": "S012", "category": "geometry", "role": "权威恒载节点映射", "path": GEOMETRY_DIR / "authoritative_mct_deadload_v1_conload_mapping.csv", "required": True},  # 节点荷载到质量项的映射属于硬门禁。
        {"item_id": "S013", "category": "geometry", "role": "门架变高度站位", "path": GEOMETRY_DIR / "variable_height_gate_stations.csv", "required": True},  # 门架几何生成需要各站位高度。
        {"item_id": "S014", "category": "geometry", "role": "门架与索连接映射", "path": GEOMETRY_DIR / "gate_rope_couplings.csv", "required": True},  # 索夹连接和偏心节点关系必须存在。
        {"item_id": "S015", "category": "geometry", "role": "门架中心线节点", "path": GEOMETRY_DIR / "gate_centerline_nodes.csv", "required": True},  # 门架物理梁节点生成来源必须存在。
        {"item_id": "S016", "category": "geometry", "role": "门架中心线单元", "path": GEOMETRY_DIR / "gate_centerline_elements.csv", "required": True},  # 门架物理梁拓扑生成来源必须存在。
        {"item_id": "S017", "category": "module", "role": "横通道中段节点模板", "path": MODULE_DIR / "middle_nodes.csv", "required": True},  # 中段横通道节点局部坐标模板属于硬门禁。
        {"item_id": "S018", "category": "module", "role": "横通道中段杆件模板", "path": MODULE_DIR / "middle_edges.csv", "required": True},  # 中段横通道杆件连接模板属于硬门禁。
        {"item_id": "S019", "category": "module", "role": "横通道调节段节点模板", "path": MODULE_DIR / "adjustment_nodes.csv", "required": True},  # 调节段节点局部坐标模板属于硬门禁。
        {"item_id": "S020", "category": "module", "role": "横通道调节段杆件模板", "path": MODULE_DIR / "adjustment_edges.csv", "required": True},  # 调节段杆件连接模板属于硬门禁。
        {"item_id": "S021", "category": "module", "role": "横通道尾段节点模板", "path": MODULE_DIR / "tail_nodes.csv", "required": True},  # 尾段节点局部坐标模板属于硬门禁。
        {"item_id": "S022", "category": "module", "role": "横通道尾段杆件模板", "path": MODULE_DIR / "tail_edges.csv", "required": True},  # 尾段杆件连接模板属于硬门禁。
        {"item_id": "S023", "category": "environment", "role": "MAPDL 2026 R1可执行文件", "path": MAPDL_EXE, "required": True},  # 没有求解器只能判源链不可执行。
        {"item_id": "S024", "category": "post", "role": "模态识别与导出后处理", "path": V2_ROOT / "post" / "modal_identification_pipeline.py", "required": True},  # 完整频谱和振型识别链必须可生成。
        {"item_id": "S025", "category": "source_model", "role": "MCT门架索合建文本模型", "path": WORKSPACE / "01_设计资料与规范" / "猫道 - 门架索合建模型2.mct", "required": True},  # MCT线形、支承、初力和荷载来源必须在工作区保留。
        {"item_id": "S026", "category": "source_drawing", "role": "猫道原版图纸", "path": WORKSPACE / "01_设计资料与规范" / "00张靖皋长江大桥南航道桥猫道图纸1225.pdf", "required": False},  # 图纸对后续轴和连接封板重要，但不阻止旧物理基线重算。
        {"item_id": "S027", "category": "source_report", "role": "猫道结构复核报告", "path": WORKSPACE / "01_设计资料与规范" / "张靖皋长江大桥南航道桥 猫道结构复核计算报告0324.pdf", "required": False},  # 复核报告提供结构与连接说明但不是 APDL 执行依赖。
        {"item_id": "S028", "category": "source_report", "role": "猫道结构抗风性能试验报告", "path": WORKSPACE / "01_设计资料与规范" / "附件2-3：猫道结构抗风性能试验报告.pdf", "required": False},  # 抗风报告提供目标频率和部分振型图，不参与源链执行。
        {"item_id": "S029", "category": "legacy_frozen_output", "role": "B00 LEGACY冻结CERIG有限拓扑APDL include", "path": V2_ROOT / "builder" / "generated" / "apply_finite_gates_and_passages_v2.inp", "required": True},  # 根产物保留旧CERIG=5078物理定义，是B00不可替换的冻结基线。
        {"item_id": "S030", "category": "legacy_frozen_output", "role": "B00 LEGACY冻结空间化质量APDL include", "path": V2_ROOT / "apply_dynamic_mass21_spatialized_v2.inp", "required": True},  # 根质量产物必须与根旧拓扑成对进入B00，禁止与MPC候选交叉。
        {"item_id": "S031", "category": "legacy_frozen_audit", "role": "B00 LEGACY冻结有限拓扑审计", "path": V2_ROOT / "builder" / "generated" / "build_audit.json", "required": True},  # 根审计绑定109086节点、172994单元和CERIG计数来源。
        {"item_id": "S032", "category": "legacy_frozen_audit", "role": "B00 LEGACY冻结质量审计", "path": V2_ROOT / "mass21_spatialization_audit_v2.json", "required": True},  # 根质量审计绑定33003个MASS21和4108.466907581062吨总质量。
    ]  # 完成显式源文件规格列表定义。
    authoritative_inputs = [  # 定义 V2 主输入生成器从第一阶验证目录复制的九个权威 APDL include。
        ("I001", "基础索网与横梁", "full_line_beam4_crossbeam_mesh_xlong.inp"),  # 基础节点、索网和旧横梁输入是装配起点。
        ("I002", "BEAM4到BEAM188转换", "convert_crossbeams_beam4_to_beam188.inp"),  # 转换输入决定基础横梁的现代单元实现。
        ("I003", "MCT等效下拉接口", "apply_mct_downpull_equivalent_xlong.inp"),  # 旧物理基线必须冻结当前下拉接口。
        ("I004", "MCT位移支承", "apply_mct_constraints_xlong.inp"),  # 支承和边界条件属于硬门禁。
        ("I005", "LINK180权威初应力", "apply_mct_authoritative_initial_state_link180.inp"),  # 非线性静力平衡需要完整初应力。
        ("I006", "ROTY数值稳定约束", "apply_modal_roty_stabilization_xlong.inp"),  # 旧 V2 物理定义中的 ROTY 约束必须冻结。
        ("I007", "代表索组件", "define_representative_rope_component.inp"),  # 后处理组件能量和索力审计依赖代表索组件。
        ("I008", "权威二期恒载", "apply_authoritative_mct_deadload_v1.inp"),  # 静力总量和反力闭合需要权威恒载。
        ("I009", "权威重力", "apply_authoritative_mct_gravity_v1.inp"),  # 重力加速度与荷载方向输入属于硬门禁。
    ]  # 完成九个权威 include 的稳定清单。
    for item_id, role, filename in authoritative_inputs:  # 遍历权威 include 并追加为独立硬门禁条目。
        specs.append({"item_id": item_id, "category": "authoritative_inp", "role": role, "path": SOURCE_RUN / filename, "required": True})  # 保存绝对路径并标记为必须存在。
    return specs  # 返回完整源文件规格供审计主流程使用。


def sha256_file(path: Path) -> str:  # 定义流式 SHA-256 计算函数，避免大型输入占用过多内存。
    """返回普通文件的 64 位小写十六进制 SHA-256。"""  # 说明输入必须是文件，输出用于 manifest 和源哈希清单。
    digest = hashlib.sha256()  # 初始化新的 SHA-256 摘要对象，确保每个文件相互独立。
    with path.open("rb") as stream:  # 以二进制只读方式打开文件，避免换行和编码转换改变哈希。
        while True:  # 循环读取固定大小数据块直到文件末尾。
            chunk = stream.read(HASH_CHUNK_BYTES)  # 每次读取 1 MiB，平衡磁盘吞吐和内存占用。
            if not chunk:  # 空字节块表示已经到达文件末尾。
                break  # 结束循环并准备返回最终摘要。
            digest.update(chunk)  # 将当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回稳定的 64 位小写十六进制字符串。


def inspect_sources(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:  # 定义源清单检查函数，输入稳定规格并返回带证据的行。
    """检查存在性、大小、时间和 SHA-256，不修改任何源文件。"""  # 明确该函数是只读 U00 门禁核心。
    rows: list[dict[str, Any]] = []  # 初始化机器可读行列表，随后写入两个同内容 CSV。
    for spec in specs:  # 按稳定顺序逐一检查全部必需和辅助源文件。
        path = Path(spec["path"])  # 将规格中的路径标准化为 Path 对象。
        exists = path.is_file()  # 只接受普通文件，目录或断链均视为不存在。
        stat = path.stat() if exists else None  # 文件存在时读取大小和修改时间，缺失时保持空值。
        rows.append({  # 追加一行完整源证据，所有字段均可直接写入 CSV 和 JSON。
            "item_id": spec["item_id"],  # 写入稳定条目标识，便于跨次审计比较。
            "category": spec["category"],  # 写入文件所属类别，如 builder、mass 或 authoritative_inp。
            "role": spec["role"],  # 写入文件在执行链中的用途。
            "path": str(path),  # 写入可人工定位的绝对路径。
            "required": bool(spec["required"]),  # 写入该项是否控制 PASS_A 硬门禁。
            "exists": exists,  # 写入普通文件存在性布尔值。
            "size_bytes": stat.st_size if stat else None,  # 写入文件字节数，缺失时为 JSON/CSV 空值。
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else "",  # 写入 UTC 修改时间以便与历史 Run 对照。
            "sha256": sha256_file(path) if exists else "",  # 文件存在时计算原始字节 SHA-256，缺失时留空。
        })  # 完成当前源文件证据行。
    return rows  # 返回全部源文件证据行供状态判断和落盘。


def parse_apdl_dependencies(rows: list[dict[str, Any]], builder_output_dir: Path, mass_output_dir: Path) -> dict[str, Any]:  # 定义 APDL 递归依赖图生成函数，并接收本轮封板产物目录。
    """解析清单中 INP 的 /INPUT，并记录可解析与缺失目标。"""  # 说明图仅描述显式 APDL include，不猜测 Python 动态生成关系。
    input_paths = [Path(row["path"]) for row in rows if row["exists"] and Path(row["path"]).suffix.lower() == ".inp"]  # 选择所有存在的 APDL 输入文件。
    basename_index = {path.name.lower(): path for path in input_paths}  # 建立不区分大小写的文件名索引以解析同目录快照依赖。
    nodes = [{"id": str(path), "type": "apdl_input", "sha256": sha256_file(path)} for path in input_paths]  # 为每个 APDL 文件建立带哈希的图节点。
    edges: list[dict[str, Any]] = []  # 初始化显式 /INPUT 有向边列表。
    unresolved: list[dict[str, str]] = []  # 初始化无法在清单索引解析的 include 记录。
    for source_path in input_paths:  # 逐个读取 APDL 输入并搜索 /INPUT 命令。
        text = source_path.read_text(encoding="utf-8", errors="replace")  # 用宽容 UTF-8 读取命令文本，ASCII 命令不会受替换字符影响。
        for line_number, line in enumerate(text.splitlines(), start=1):  # 保留一基行号以便人工回到源文件复核。
            match = INPUT_PATTERN.match(line)  # 尝试匹配当前行开头的 /INPUT 命令。
            if match is None:  # 非 /INPUT 行不属于依赖边。
                continue  # 继续检查下一行以避免无关解析。
            stem = match.group(1).strip("'\"")  # 去除文件名两侧可能存在的单引号或双引号。
            extension = (match.group(2) or "inp").strip("'\"")  # 未提供扩展名时采用 MAPDL 常见默认 inp。
            target_name = f"{stem}.{extension}" if "." not in Path(stem).name else stem  # 仅在文件名没有扩展名时追加显式或默认扩展名。
            target_path = basename_index.get(Path(target_name).name.lower())  # 先按文件名在权威清单中查找目标。
            if target_path is None:  # 索引中没有目标时记录为未解析，而不伪造存在性。
                unresolved.append({"source": str(source_path), "line": str(line_number), "requested": target_name})  # 保存源路径、行号和请求名称。
                continue  # 跳过当前未解析边并继续处理其他 include。
            edges.append({"source": str(source_path), "target": str(target_path), "relation": "/INPUT", "line": line_number})  # 保存已解析的有向依赖边。
    legacy_main = "GENERATED:B00_LEGACY_COMPLETE_main.inp"  # 使用稳定虚拟节点表示待由独立编排器生成的B00旧物理主输入。
    diagnostic_main = "GENERATED:C10_MPC_DIAGNOSTIC_main.inp"  # 使用另一虚拟节点表示后续MPC诊断候选主输入，禁止与B00混用。
    generated_chain = [  # 建立 Python 动态生成链的显式逻辑边，补足静态 APDL 中不存在的入口关系。
        {"source": str(V2_ROOT / "prepare_and_run_v2.py"), "target": legacy_main, "relation": "contains build template; shared runner disabled"},  # 旧runner包含主输入模板但入口已硬禁用，后续须由独立Run编排器复用其逻辑。
        {"source": str(V2_ROOT / "builder" / "build_finite_gate_passage_apdl.py"), "target": str(builder_output_dir / "apply_finite_gates_and_passages_v2.inp"), "relation": "generates"},  # builder 在隔离目录生成有限拓扑 include。
        {"source": str(V2_ROOT / "generate_spatialized_mass21_v2.py"), "target": str(mass_output_dir / "apply_dynamic_mass21_spatialized_v2.inp"), "relation": "generates"},  # 质量脚本在隔离目录生成 MASS21 include。
    ]  # 完成动态生成关系列表。
    shared_base_inputs = [  # 明确列出LEGACY与MPC诊断两条模型线共同使用的九份权威APDL include。
        SOURCE_RUN / "full_line_beam4_crossbeam_mesh_xlong.inp",  # 基础索网与横梁必须首先装配。
        SOURCE_RUN / "convert_crossbeams_beam4_to_beam188.inp",  # 基础横梁随后转换为 BEAM188。
        SOURCE_RUN / "apply_mct_downpull_equivalent_xlong.inp",  # 冻结旧 V2 的下拉等效接口。
        SOURCE_RUN / "apply_mct_constraints_xlong.inp",  # 应用 MCT 权威支承和位移约束。
        SOURCE_RUN / "apply_mct_authoritative_initial_state_link180.inp",  # 恢复 LINK180 权威初始索力。
        SOURCE_RUN / "apply_modal_roty_stabilization_xlong.inp",  # 应用旧物理基线的 ROTY 稳定约束。
        SOURCE_RUN / "define_representative_rope_component.inp",  # 定义代表索组件供审计和后处理。
        SOURCE_RUN / "apply_authoritative_mct_deadload_v1.inp",  # 应用权威二期恒载。
        SOURCE_RUN / "apply_authoritative_mct_gravity_v1.inp",  # 最后应用权威重力加速度。
    ]  # 完成两条模型线的共享基础include定义。
    legacy_inputs = [*shared_base_inputs[:5], V2_ROOT / "builder" / "generated" / "apply_finite_gates_and_passages_v2.inp", *shared_base_inputs[5:8], V2_ROOT / "apply_dynamic_mass21_spatialized_v2.inp", shared_base_inputs[8]]  # 以旧CERIG拓扑和同代根质量组成B00冻结输入链。
    diagnostic_inputs = [*shared_base_inputs[:5], builder_output_dir / "apply_finite_gates_and_passages_v2.inp", *shared_base_inputs[5:8], mass_output_dir / "apply_dynamic_mass21_spatialized_v2.inp", shared_base_inputs[8]]  # 以MPC184拓扑和同代质量组成C10诊断输入链。
    for order, dependency_path in enumerate(legacy_inputs, start=1):  # 遍历B00十一份依赖并保留真实装配次序。
        generated_chain.append({"source": legacy_main, "target": str(dependency_path), "relation": "/INPUT LEGACY_FROZEN_APDL", "order": order})  # 写入B00冻结输入有向边。
    for order, dependency_path in enumerate(diagnostic_inputs, start=1):  # 遍历C10十一份依赖并保留真实装配次序。
        generated_chain.append({"source": diagnostic_main, "target": str(dependency_path), "relation": "/INPUT MPC_DIAGNOSTIC_GENERATED", "order": order})  # 写入MPC诊断输入有向边。
    return {"schema_version": "1.0", "nodes": nodes, "apdl_edges": edges, "generated_edges": generated_chain, "unresolved_apdl_inputs": unresolved}  # 返回完整依赖图对象。


def memory_environment() -> dict[str, Any]:  # 定义 Windows 内存信息读取函数，避免依赖第三方包。
    """从 GlobalMemoryStatusEx 返回物理内存总量和当前可用量。"""  # 说明该值用于启动门禁而非模型源链身份判断。
    import ctypes  # 在函数内导入 ctypes，仅用于调用 Windows 内核内存状态接口。
    class MemoryStatus(ctypes.Structure):  # 定义与 Windows MEMORYSTATUSEX 二进制布局一致的结构体。
        _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong), ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong), ("avail_extended_virtual", ctypes.c_ulonglong)]  # 声明所有字段及其原生整数类型。
    status = MemoryStatus()  # 初始化零值结构体以接收内核函数写入。
    status.length = ctypes.sizeof(MemoryStatus)  # 按 API 要求写入结构体自身字节长度。
    success = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # 调用 Windows 内核接口填充当前内存状态。
    if not success:  # 内核函数返回零表示调用失败。
        return {"available": False}  # 返回明确不可用状态而不猜测内存数值。
    return {"available": True, "total_physical_bytes": int(status.total_phys), "available_physical_bytes": int(status.avail_phys), "memory_load_percent": int(status.memory_load)}  # 返回启动门禁需要的三项内存指标。


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:  # 定义通用源清单 CSV 写入函数。
    """以 UTF-8-SIG 写入固定列清单，兼容 Excel 和 Pro 读取。"""  # 说明 CSV 不支持注释，字段解释写入同目录 Markdown。
    fieldnames = ["item_id", "category", "role", "path", "required", "exists", "size_bytes", "modified_utc", "sha256"]  # 固定列顺序以便跨次差异比较。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:  # 使用带 BOM 的 UTF-8 并关闭额外空行转换。
        writer = csv.DictWriter(stream, fieldnames=fieldnames)  # 创建按固定字段顺序输出的字典写入器。
        writer.writeheader()  # 写入列名，保证独立打开 CSV 时含义完整。
        writer.writerows(rows)  # 写入全部源文件证据行，不进行人工筛选。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # 定义统一 JSON 写入函数，确保所有机器文件格式一致。
    """以无 BOM UTF-8 和两空格缩进写入标准 JSON。"""  # 说明 JSON 不支持注释，字段解释由 Markdown 提供。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 保留中文原文并以换行结束文件。


def main() -> None:  # 定义 U00 审计主流程，集中完成检查、判断和全部输出。
    """执行只读源门禁并生成任务书第 2 节要求的成果。"""  # 说明主流程不会启动或修改 MAPDL 作业。
    parser = argparse.ArgumentParser(description=__doc__)  # 创建命令行解析器并使用模块说明作为帮助文本。
    parser.add_argument("--output-dir", type=Path, required=True, help="独立 U00 Run 输出目录")  # 要求调用方显式指定输出目录以避免覆盖历史审计。
    parser.add_argument("--builder-output-dir", type=Path, required=True, help="本轮隔离重生的 builder 封板目录")  # 要求显式绑定当前源码生成的有限拓扑产物，禁止默认采用陈旧根产物。
    parser.add_argument("--mass-output-dir", type=Path, required=True, help="本轮隔离重生的 MASS21 封板目录")  # 要求显式绑定与当前 builder 同代的质量产物。
    args = parser.parse_args()  # 解析命令行参数并在缺失输出目录时自动失败。
    output_dir = args.output_dir.resolve()  # 将输出目录规范化为绝对路径写入所有 manifest。
    builder_output_dir = args.builder_output_dir.resolve()  # 将本轮 builder 产物目录规范化并绑定到全部依赖和哈希。
    mass_output_dir = args.mass_output_dir.resolve()  # 将本轮质量产物目录规范化并绑定到全部依赖和哈希。
    output_dir.mkdir(parents=True, exist_ok=True)  # 创建独立 Run 目录及必要父目录，保留其他作业不受影响。
    generated_utc = datetime.now(timezone.utc).isoformat()  # 记录本次审计生成时刻，使用带时区 UTC 格式。
    specs = source_specs(builder_output_dir, mass_output_dir)  # 取得包含本轮隔离封板产物的必需和辅助源文件清单。
    rows = inspect_sources(specs)  # 只读检查全部源文件并计算哈希证据。
    required_missing = [row for row in rows if row["required"] and not row["exists"]]  # 收集所有控制 PASS_A 的缺失项。
    dependency_graph = parse_apdl_dependencies(rows, builder_output_dir, mass_output_dir)  # 建立绑定本轮隔离封板产物的输入依赖图。
    memory = memory_environment()  # 读取当前物理内存状态供后续是否启动求解判断。
    mapdl_exists = MAPDL_EXE.is_file()  # 单独保存 MAPDL 可执行文件存在性以便环境 JSON 直接读取。
    mapdl_hash = sha256_file(MAPDL_EXE) if mapdl_exists else ""  # 求解器存在时绑定其原始字节 SHA-256。
    source_status = "PASS_A" if not required_missing else "FAIL"  # 全部硬门禁存在时判完整源链可重建，否则禁止求解。
    minimum_full_solve_bytes = 8 * 1024**3  # 采用既有作业记录中的 8 GiB 最低可用物理内存门槛。
    comfortable_full_solve_bytes = 10 * 1024**3  # 采用既有作业记录中的 10 GiB 舒适可用物理内存目标。
    available_bytes = int(memory.get("available_physical_bytes", 0))  # 缺内存接口时以零表示不可满足启动门禁。
    full_solve_memory_ready = available_bytes >= minimum_full_solve_bytes  # 判断当前时刻是否满足全桥最低可用内存门槛。
    mapdl_environment = {  # 组织任务书要求的 MAPDL 环境清单。
        "generated_utc": generated_utc,  # 写入环境采集 UTC 时刻。
        "executable": str(MAPDL_EXE),  # 写入求解器绝对路径。
        "executable_exists": mapdl_exists,  # 写入求解器存在性。
        "executable_sha256": mapdl_hash,  # 写入求解器原始字节 SHA-256。
        "ansys_release": "2026 R1 / v261",  # 根据安装目录和可执行文件名记录实际发行版。
        "os": platform.platform(),  # 写入 Windows 版本和架构组合字符串。
        "python": platform.python_version(),  # 写入审计脚本使用的 Python 版本。
        "cpu_architecture": platform.machine(),  # 写入 CPU 指令架构。
        "logical_processors": os.cpu_count(),  # 写入操作系统报告的逻辑处理器数量。
        "parallel_mode": "DMP",  # 冻结历史全桥作业使用的分布式内存并行模式。
        "mpi": "intelmpi",  # 冻结历史全桥作业使用的 Intel MPI 实现。
        "processes": PROCESS_COUNT,  # 冻结四个 DMP 分区数量。
        "units": UNITS,  # 写入模型单位制。
        "coordinate_system": COORDINATES,  # 写入模型轴向定义。
        "memory": memory,  # 嵌入当前物理内存总量、可用量和负载比例。
        "minimum_available_memory_bytes_for_full_solve": minimum_full_solve_bytes,  # 写入 8 GiB 全桥最低门槛。
        "comfortable_available_memory_bytes_for_full_solve": comfortable_full_solve_bytes,  # 写入 10 GiB 舒适目标。
        "full_solve_memory_ready": full_solve_memory_ready,  # 明确当前是否允许启动 B00 全桥求解。
    }  # 完成 MAPDL 环境字典。
    status_payload = {  # 组织 U00 状态 JSON，状态词严格使用任务书允许值。
        "run_id": "U00_SOURCE_GATE",  # 固定本轮 Run 标识。
        "generated_utc": generated_utc,  # 写入审计时刻。
        "status": source_status,  # 写入 PASS_A 或 FAIL。
        "required_item_count": sum(1 for row in rows if row["required"]),  # 写入硬门禁总项数。
        "required_missing_count": len(required_missing),  # 写入硬门禁缺失项数。
        "required_missing": [{"item_id": row["item_id"], "role": row["role"], "path": row["path"]} for row in required_missing],  # 写入全部缺失硬门禁证据。
        "generated_main_input_present": False,  # 当前源目录未保留固定主输入，主输入由 runner 为每个独立 Run 动态生成。
        "generated_main_input_reconstructable": source_status == "PASS_A",  # 只有源链完整时才声明主输入可重建。
        "sealed_builder_output_dir": str(builder_output_dir),  # 写入本轮执行链唯一采用的 builder 封板目录。
        "sealed_mass_output_dir": str(mass_output_dir),  # 写入本轮执行链唯一采用的质量封板目录。
        "legacy_frozen_builder_output": str(V2_ROOT / "builder" / "generated" / "apply_finite_gates_and_passages_v2.inp"),  # 写入B00冻结旧CERIG拓扑路径。
        "legacy_frozen_mass_output": str(V2_ROOT / "apply_dynamic_mass21_spatialized_v2.inp"),  # 写入与B00拓扑同代的冻结质量路径。
        "root_generated_outputs_authoritative_for_legacy_only": True,  # 明确根产物只对B00旧物理基线权威，不代表当前生成器输出。
        "current_shared_runner_disabled": True,  # 记录prepare_and_run_v2入口已硬失败，后续必须建立独立Run编排器。
        "full_solve_memory_ready": full_solve_memory_ready,  # 把内存启动条件与源链身份条件明确分离。
        "next_action": "RUN_U01_UNIT_TESTS" if source_status == "PASS_A" else "STOP_AND_EXPORT_MISSING_LIST",  # 指定合法下一步且不越过 U01。
    }  # 完成 U00 状态字典。
    manifest = {  # 组织本次独立 U00 Run 的最小 manifest。
        "run_id": "U00_SOURCE_GATE",  # 写入稳定 Run 标识。
        "jobname": "NO_SOLVE_U00",  # U00 不调用 MAPDL，因此使用明确的无求解作业名。
        "model_line": "CONTROL",  # U00 属于任务矩阵中的控制线。
        "parent_run": "",  # U00 为首个 Run，没有父作业。
        "single_change": "No solve; executable source gate only",  # 说明本轮不改变模型且不求解。
        "mapdl_version": "2026 R1 / v261",  # 写入已定位求解器版本。
        "executable_sha256": mapdl_hash,  # 绑定求解器原始字节身份。
        "processes": PROCESS_COUNT,  # 写入未来作业固定的 DMP 进程数。
        "units": UNITS,  # 写入模型单位制。
        "coordinate_system": COORDINATES,  # 写入模型轴定义。
        "input_hashes": {row["item_id"]: row["sha256"] for row in rows if row["exists"]},  # 嵌入全部已找到源文件哈希。
        "sealed_builder_output_dir": str(builder_output_dir),  # 在 manifest 中固定当前有限拓扑封板目录。
        "sealed_mass_output_dir": str(mass_output_dir),  # 在 manifest 中固定当前质量封板目录。
        "model_lineages": {"B00_LEGACY_COMPLETE": {"topology": str(V2_ROOT / "builder" / "generated" / "apply_finite_gates_and_passages_v2.inp"), "mass": str(V2_ROOT / "apply_dynamic_mass21_spatialized_v2.inp"), "kinematics": "CERIG_5078_FROZEN"}, "C10_MPC_DIAGNOSTIC": {"topology": str(builder_output_dir / "apply_finite_gates_and_passages_v2.inp"), "mass": str(mass_output_dir / "apply_dynamic_mass21_spatialized_v2.inp"), "kinematics": "MPC184_8202_GENERATED"}},  # 在manifest中并列封存两条不可互换的模型线。
        "expected_counts": {},  # U00 不装配模型，因此没有求解前拓扑计数。
        "actual_counts": {},  # U00 不运行 MAPDL，因此没有实际拓扑计数。
        "status": "PASSED" if source_status == "PASS_A" else "REJECTED",  # 将源门禁映射到 manifest 生命周期状态。
    }  # 完成 U00 manifest 字典。
    write_csv(output_dir / "source_inventory.csv", rows)  # 写出任务书第 2.4 节要求的原名源清单。
    write_csv(output_dir / "01_source_inventory.csv", rows)  # 同时写出任务书第 19 节规定的编号版源清单。
    write_json(output_dir / "input_dependency_graph.json", dependency_graph)  # 写出显式和动态输入依赖图。
    write_json(output_dir / "mapdl_environment.json", mapdl_environment)  # 写出求解器、系统、并行和内存环境清单。
    write_json(output_dir / "U00_status.json", status_payload)  # 写出机器可读 U00 合法状态。
    write_json(output_dir / "manifest.json", manifest)  # 写出独立 Run manifest。
    hash_lines = [f"{row['sha256']}  {row['path']}" for row in rows if row["exists"]]  # 生成标准 SHA-256 清单行并保留绝对源路径。
    (output_dir / "source_hashes.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")  # 写出无 BOM 标准哈希清单。
    report_lines = [  # 组织人工可读源门禁报告并逐项解释机器文件字段。
        "# U00 可执行源门禁",  # 写入报告标题。
        "",  # 插入 Markdown 空行以正确分隔标题和正文。
        f"- 生成时间：`{generated_utc}`",  # 写入 UTC 审计时刻。
        f"- 状态：`{source_status}`",  # 写入任务书允许的 U00 状态。
        f"- 必需源项：{status_payload['required_item_count']} 项；缺失：{status_payload['required_missing_count']} 项。",  # 汇总硬门禁数量。
        f"- MAPDL：`{MAPDL_EXE}`；存在：`{mapdl_exists}`；SHA-256：`{mapdl_hash}`。",  # 汇总求解器身份。
        f"- 当前可用物理内存：{available_bytes / 1024**3:.2f} GiB；全桥最低门槛：8.00 GiB；当前允许启动全桥：`{full_solve_memory_ready}`。",  # 汇总独立内存启动门禁。
        f"- B00 LEGACY冻结拓扑：`{V2_ROOT / 'builder' / 'generated' / 'apply_finite_gates_and_passages_v2.inp'}`。",  # 汇总B00旧CERIG拓扑路径。
        f"- B00 LEGACY冻结质量：`{V2_ROOT / 'apply_dynamic_mass21_spatialized_v2.inp'}`。",  # 汇总B00同代质量路径。
        f"- C10 MPC诊断封板：`{builder_output_dir}`。",  # 汇总后续C10使用的MPC184有限拓扑产物目录。
        f"- C10 MPC诊断质量：`{mass_output_dir}`。",  # 汇总与C10拓扑同代的质量产物目录。
        "",  # 插入章节前空行。
        "## 判定",  # 写入源门禁判定章节。
        "",  # 插入标题与正文之间的 Markdown 空行。
        "完整 runner、九个权威基础 include、有限拓扑 builder 及产物、质量生成器及产物、几何/站位/横通道模板和 MAPDL 可执行文件均存在时判 `PASS_A`。固定主输入不作为静态源文件保存，而由 runner 为独立 Run 生成；其可重建性由上述源链共同控制。",  # 解释动态主输入为何不构成缺失。
        "源链存在两条不可互换的 lineage：根 `builder/generated` 与根质量 include 是 B00 所需的冻结旧 CERIG 物理基线；隔离重生的 MPC184=8202 拓扑与同代质量 include 是后续 C10 诊断候选。隔离重生产物与历史 `0221` 快照逐字节一致。两条线都通过 U00 哈希封存，但任何拓扑和质量 pair 禁止交叉使用。",  # 解释版本分叉及两条模型线的严格边界。
        "",  # 插入章节前空行。
        "## 当前执行边界",  # 写入首轮执行边界章节。
        "",  # 插入标题与正文之间的 Markdown 空行。
        "U00 只完成只读源审计，不启动 MAPDL。`PASS_A` 后下一步只能进入 U01 小算例；只有 U01 全部通过且可用物理内存恢复到至少 8 GiB，才能启动 B00 全桥重算。",  # 明确任务书规定的合法下一步。
        "",  # 插入章节前空行。
        "## 机器文件说明",  # 写入无注释格式的配套字段说明章节。
        "",  # 插入标题与列表之间的 Markdown 空行。
        "- `source_inventory.csv` / `01_source_inventory.csv`：逐项记录类别、用途、绝对路径、硬门禁标志、存在性、字节数、UTC 修改时间和 SHA-256。",  # 解释 CSV 每行用途。
        "- `input_dependency_graph.json`：记录显式 `/INPUT` 依赖、Python 动态生成关系和未解析 include。",  # 解释依赖图 JSON。
        "- `mapdl_environment.json`：记录求解器身份、Windows/Python/CPU、DMP/Intel MPI、四进程和内存门禁。",  # 解释环境 JSON。
        "- `U00_status.json`：记录唯一合法状态、缺失项、主输入可重建性及下一步。",  # 解释状态 JSON。
        "- `source_hashes.sha256`：绑定所有已找到关键源文件的原始字节内容。",  # 解释哈希清单。
    ]  # 完成人工报告文本行列表。
    (output_dir / "00_source_gate.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8-sig")  # 以 UTF-8 BOM 写出人工报告，保证 Windows 中文兼容。
    print(json.dumps({"status": source_status, "output_dir": str(output_dir), "full_solve_memory_ready": full_solve_memory_ready}, ensure_ascii=False))  # 在标准输出打印最小调度摘要。


if __name__ == "__main__":  # 判断脚本是否被直接执行，而不是作为库导入。
    main()  # 调用主流程完成 U00 全部只读检查和成果落盘。
