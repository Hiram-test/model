#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建立附件2-3前14阶模态精细模型所需的21处横向通道权威站位与质量映射。

本脚本刻意把“站位权威”和“旧比例映射”分开处理：

1. 站位权威来自原始MCT“二期”集中荷载。门架索体系中21个21.556 kN站
   唯一对应“横通道三角门架12.360 kN + 门架导轮组9.196 kN”；
2. 同一位置在底索体系中有21个含49.69 kN“横向通道半幅”质量的组合站，
   它们必须与21个三角门架站一一配对；
3. ``cross_passage_21_stations.csv`` 的比例映射只用于继承H01～H21编号、分跨
   名称并量化旧误差，绝不再作为新模型坐标来源；
4. 当前模态模型把MCT集中恒载转换成了MASS21。本脚本同时解析该APDL include，
   输出每个原MASS21单元、节点、实常数和可拆分组件质量，便于后续把质量迁移到
   有限刚度门架/横向通道杆系而不改变总质量。

统一单位：

- 几何坐标：mm；
- 重量：kN；
- 质量：tonne；
- MCT坐标：X为顺桥、Y为横桥、Z为竖向；
- 当前ANSYS模型坐标：X为横桥、Y为顺桥、Z为竖向。

脚本只读取已有权威源文件，并只向当前 ``audit`` 目录写新文件；不会修改任何
既有MCT、CSV、APDL或求解结果。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Iterable, Sequence


# SCRIPT_DIR 是本脚本及全部新审计输出所在目录。
SCRIPT_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT 由固定目录层级反推：audit -> V2.0 -> 03_猫道动力分析 -> 工程根目录。
# 使用相对层级可避免把盘符或用户名写死在计算逻辑中。
PROJECT_ROOT = SCRIPT_DIR.parents[2]

# MODEL_DIR 保存权威MCT恒载分解、完整索/横梁节点以及门架中心线几何。
MODEL_DIR = (
    PROJECT_ROOT
    / "02_CAD几何模型"
    / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"
)

# MODAL_DIR 保存当前14阶/30阶模态模型实际使用的集中质量APDL include。
MODAL_DIR = PROJECT_ROOT / "03_猫道动力分析" / "第一阶模态验证_V1.0"

# SOURCE_DIR 保存未经派生的MCT原始权威文件。
SOURCE_DIR = PROJECT_ROOT / "01_设计资料与规范"

# 以下路径均为只读输入。逐一列名而不是使用模糊glob，可阻止临时副本被误用。
MCT_PATH = SOURCE_DIR / "猫道 - 门架索合建模型2.mct"
ITEMS_PATH = MODEL_DIR / "authoritative_mct_deadload_v1_items.csv"
FORCE_MAPPING_PATH = MODEL_DIR / "authoritative_mct_deadload_v1_conload_mapping.csv"
FULL_NODES_PATH = MODEL_DIR / "full_line_beam4_nodes.csv"
FULL_ELEMENTS_PATH = MODEL_DIR / "full_line_beam4_elements.csv"
GATE_FIT_PATH = MODEL_DIR / "gate_fit_audit.csv"
GATE_CENTERLINE_NODES_PATH = MODEL_DIR / "gate_centerline_nodes.csv"
GATE_CENTERLINE_ELEMENTS_PATH = MODEL_DIR / "gate_centerline_elements.csv"
GATE_COUPLINGS_PATH = MODEL_DIR / "gate_rope_couplings.csv"
OLD_PROPORTIONAL_STATIONS_PATH = MODEL_DIR / "cross_passage_21_stations.csv"
DYNAMIC_MASS21_PATH = MODAL_DIR / "apply_dynamic_mass21_from_conloads.inp"

# 以下路径是本脚本唯一允许写入的结果文件。
STATION_OUTPUT_PATH = SCRIPT_DIR / "passage_station_authoritative_map.csv"
COMPONENT_OUTPUT_PATH = SCRIPT_DIR / "passage_component_authoritative_inventory.csv"
MASS_NODE_OUTPUT_PATH = SCRIPT_DIR / "passage_mass21_node_map.csv"
COMPONENT_ALLOCATION_OUTPUT_PATH = (
    SCRIPT_DIR / "passage_component_mass21_allocation.csv"
)
GATE_NODE_OUTPUT_PATH = SCRIPT_DIR / "passage_gate_centerline_nodes.csv"
GATE_ELEMENT_OUTPUT_PATH = SCRIPT_DIR / "passage_gate_centerline_elements.csv"
GATE_COUPLING_OUTPUT_PATH = SCRIPT_DIR / "passage_gate_rope_couplings.csv"
AUDIT_OUTPUT_PATH = SCRIPT_DIR / "passage_station_mass_map_audit.json"
README_OUTPUT_PATH = SCRIPT_DIR / "README_权威站位与质量映射.md"

# 当前正式动力模型采用9.806 m/s²，即1 tonne质量对应9.806 kN重量。
GRAVITY_KN_PER_TONNE = 9.806

# MCT与现有三维模型的顺桥坐标存在固定平移。脚本不会依赖该常数生成节点，
# 但会由全部21处站位反算并验证，以发现坐标系或文件版本错配。
EXPECTED_MCT_X_TO_ANSYS_Y_OFFSET_MM = 831_091.0

# 门架体系的21.556 kN是专用横通道站的唯一识别值。
DEDICATED_GATE_COMBINATION_KN = 21.556

# 底索体系三种组合值均含49.69 kN“横向通道半幅”。显式列举可避免把
# 67.9833 kN主塔刚架等数值相近但物理含义不同的站误选进来。
PASSAGE_BOTTOM_COMBINATION_KN = (67.59, 68.80, 70.12)

# 21品横向通道在附件布置中按北向南顺序跨越四个分跨。H编号与分跨标签
# 只用于可读性；具体Y坐标严格来自MCT专用荷载节点。
EXPECTED_SPAN_COUNTS = {
    "north_side": 3,
    "main_span": 13,
    "south_side": 3,
    "south_aux": 2,
}

# 专用站可能包含的全部表1-2/表1-3组件。字段顺序固定，便于生成稳定CSV。
ALL_PASSAGE_COMPONENT_IDS = (
    "cross_passage_half",
    "main_cable_restrainer",
    "gate_bottom_beam",
    "pws_roller",
    "large_crossbeam",
    "cross_passage_tri_gate",
    "guide_roller",
)


def sha256_file(path: Path) -> str:
    """计算一个输入文件的SHA256。

    参数：
        path：需要绑定版本的文件路径。

    返回：
        64位小写十六进制SHA256字符串。

    采用分块读取是为了避免一次把大型节点/单元CSV全部载入散列缓冲区。
    """

    # digest 保存滚动散列状态；每次只读取1 MiB。
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            # block 是本轮读取的原始字节块。
            block = stream.read(1024 * 1024)
            if not block:
                # 空字节串表示到达文件末尾，必须退出循环。
                break
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """读取带表头CSV并返回字符串字典列表。

    参数：
        path：CSV输入路径。

    返回：
        每行一个字典，键来自CSV表头；数值转换由调用方按语义完成。
    """

    # utf-8-sig同时兼容带BOM和不带BOM的项目CSV。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, object]],
) -> None:
    """以固定字段顺序写UTF-8 BOM CSV。

    参数：
        path：输出文件路径；
        fieldnames：稳定的字段顺序；
        rows：待写字典行，可为列表或生成器。

    返回：
        无；结果直接写入 ``path``。
    """

    # extrasaction='raise'确保新增但未声明的字段不会被静默丢弃。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            # 每次写一行便于在异常时定位具体生成阶段。
            writer.writerow(row)


def is_close(value: float, target: float, tolerance: float = 1.0e-7) -> bool:
    """执行不带相对误差的确定性浮点近似比较。

    参数：
        value：待检查值；
        target：权威目标值；
        tolerance：允许的绝对误差。

    返回：
        两值绝对差不超过容差时返回True，否则返回False。
    """

    return math.isclose(value, target, rel_tol=0.0, abs_tol=tolerance)


def read_mct_text(path: Path) -> str:
    """以原MCT实际使用的GB系编码严格读取文本。

    参数：
        path：原始MCT路径。

    返回：
        完整MCT文本。

    ``errors='strict'`` 禁止把无法解码的中文静默替换成问号，以免“二期”工况
    关键字匹配失败后仍继续生成貌似完整的空结果。
    """

    return path.read_text(encoding="gb18030", errors="strict")


def extract_mct_first_section(text: str, keyword: str) -> list[str]:
    """提取MCT中第一次出现的指定星号段。

    参数：
        text：完整MCT文本；
        keyword：不带星号的段名，例如 ``NODE``。

    返回：
        已剔除空行与分号注释的原始数据行列表。
    """

    # marker 是MCT段起始标记。
    marker = f"*{keyword}"
    start = text.find(marker)
    if start < 0:
        # 节点段缺失说明输入不是目标MCT，不能继续推断站位。
        raise RuntimeError(f"MCT中未找到{marker}段。")

    # data_lines 保存当前段的有效数据行。
    data_lines: list[str] = []
    for line in text[start:].splitlines()[1:]:
        # stripped 仅用于判断控制符，原始逗号列仍从line解析。
        stripped = line.strip()
        if stripped.startswith("*"):
            # 下一个星号段表示本段结束。
            break
        if not stripped or stripped.startswith(";"):
            # 空行和注释不属于数据记录。
            continue
        data_lines.append(line)
    return data_lines


def parse_mct_nodes(text: str) -> dict[int, tuple[float, float, float]]:
    """解析MCT节点号及其原始X/Y/Z坐标。

    参数：
        text：完整MCT文本。

    返回：
        键为MCT节点号、值为 ``(X,Y,Z)`` 毫米坐标的字典。
    """

    # nodes 汇总全部节点，便于后续同时查底索节点与门架索节点。
    nodes: dict[int, tuple[float, float, float]] = {}
    for line in extract_mct_first_section(text, "NODE"):
        # fields 的前四列固定为节点号、X、Y、Z。
        fields = [field.strip() for field in line.split(",")]
        node_id = int(fields[0])
        nodes[node_id] = (
            float(fields[1]),
            float(fields[2]),
            float(fields[3]),
        )
    return nodes


def parse_mct_secondary_conloads(text: str) -> dict[int, float]:
    """只解析MCT“二期”工况CONLOAD中的节点FZ。

    参数：
        text：完整MCT文本。

    返回：
        键为MCT节点号、值为向下为负的FZ（kN）字典。
    """

    # secondary_marker 明确绑定“二期”而非后续施工风或阵风工况。
    secondary_marker = "*USE-STLD, 二期"
    secondary_start = text.find(secondary_marker)
    if secondary_start < 0:
        raise RuntimeError("MCT中未找到‘二期’工况。")

    # secondary_text 从二期工况起截断，后续只寻找该工况的首个CONLOAD。
    secondary_text = text[secondary_start:]
    conload_start = secondary_text.find("*CONLOAD")
    if conload_start < 0:
        raise RuntimeError("MCT二期工况中未找到CONLOAD段。")

    # loads 保存二期每个节点的原始FZ；包括小哨兵值，筛选在后续显式完成。
    loads: dict[int, float] = {}
    for line in secondary_text[conload_start:].splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("*"):
            break
        if not stripped or stripped.startswith(";"):
            continue
        # MCT CONLOAD固定列：NODE,FX,FY,FZ,MX,MY,MZ,...。
        fields = [field.strip() for field in line.split(",")]
        loads[int(fields[0])] = float(fields[3])
    return loads


def decompose_bottom_load(magnitude_kn: float) -> dict[str, int]:
    """把含横向通道的底索组合荷载唯一分解为表1-2组件。

    参数：
        magnitude_kn：向下组合荷载的正幅值，单位kN。

    返回：
        组件ID到数量的字典；每个专用站的组件数量均为0或1。
    """

    # combinations 直接采用权威恒载脚本已审计的三种精确组合。
    combinations: dict[float, dict[str, int]] = {
        67.59: {
            "cross_passage_half": 1,
            "main_cable_restrainer": 1,
            "gate_bottom_beam": 1,
        },
        68.80: {
            "cross_passage_half": 1,
            "main_cable_restrainer": 1,
            "gate_bottom_beam": 1,
            "pws_roller": 1,
        },
        70.12: {
            "cross_passage_half": 1,
            "main_cable_restrainer": 1,
            "gate_bottom_beam": 1,
            "pws_roller": 1,
            "large_crossbeam": 1,
        },
    }
    for known_value, decomposition in combinations.items():
        if is_close(magnitude_kn, known_value):
            # 返回新字典，防止调用方意外修改共享常量。
            return dict(decomposition)
    raise ValueError(f"底索荷载{magnitude_kn} kN不属于三种横向通道组合。")


def decompose_gate_load(magnitude_kn: float) -> dict[str, int]:
    """把21.556 kN专用门架组合分解为表1-3组件。

    参数：
        magnitude_kn：向下组合荷载的正幅值，单位kN。

    返回：
        ``cross_passage_tri_gate`` 与 ``guide_roller`` 各1件。
    """

    if not is_close(magnitude_kn, DEDICATED_GATE_COMBINATION_KN):
        raise ValueError(f"门架荷载{magnitude_kn} kN不是专用横通道组合。")
    return {"cross_passage_tri_gate": 1, "guide_roller": 1}


def load_component_items() -> dict[str, dict[str, object]]:
    """读取表1-2/表1-3逐项权威重量。

    返回：
        键为组件ID；值包含中文名、单处重量、来源类别和原始说明。
    """

    # items_by_id 只保留本任务所需的7种组件。
    items_by_id: dict[str, dict[str, object]] = {}
    for row in read_csv_rows(ITEMS_PATH):
        component_id = row["component_id"]
        if component_id not in ALL_PASSAGE_COMPONENT_IDS:
            # 均布附件、普通门架等与专用21站无关，跳过以避免误搬质量。
            continue
        if row["unit"] != "kN/处":
            raise AssertionError(
                f"组件{component_id}单位为{row['unit']}，期望kN/处。"
            )
        items_by_id[component_id] = {
            "component_name": row["component_name"],
            "unit_weight_kn": float(row["unit_value"]),
            "category": row["category"],
            "authority": row["authority"],
            "note": row["note"],
        }

    # missing 用于阻止缺少任一分项时仍以零值生成质量表。
    missing = set(ALL_PASSAGE_COMPONENT_IDS) - set(items_by_id)
    if missing:
        raise AssertionError(f"权威items.csv缺少组件：{sorted(missing)}")
    return items_by_id


def load_full_nodes() -> dict[int, dict[str, object]]:
    """读取当前三维模型全部节点及坐标/索族信息。

    返回：
        键为ANSYS节点号；值为已转换数值的节点记录。
    """

    # nodes_by_id 既用于输出原MASS21坐标，也用于校验门架耦合坐标。
    nodes_by_id: dict[int, dict[str, object]] = {}
    for row in read_csv_rows(FULL_NODES_PATH):
        node_id = int(row["node_id"])
        nodes_by_id[node_id] = {
            "node_id": node_id,
            "x_mm": float(row["x_mm"]),
            "y_mm": float(row["y_mm"]),
            "z_mm": float(row["z_mm"]),
            "family": row["family"],
            "source": row["source"],
        }
    return nodes_by_id


def parse_dynamic_mass21() -> dict[int, dict[str, object]]:
    """解析当前模态模型MASS21 include并建立节点到单元的映射。

    返回：
        键为ANSYS节点号；值包含MASS21单元号、实常数号和质量tonne。

    APDL文件先定义 ``R``，随后反复使用 ``REAL`` 与 ``EN``。解析时保存当前
    实常数状态，严格模拟APDL的状态式命令语义。
    """

    # real_mass_by_id 保存每个MASS21实常数对应的唯一平动质量。
    real_mass_by_id: dict[int, float] = {}
    # mass_by_node 保存最终单节点MASS21记录。
    mass_by_node: dict[int, dict[str, object]] = {}
    # current_real_id 是最近一次REAL命令选中的实常数号。
    current_real_id: int | None = None

    for raw_line in DYNAMIC_MASS21_PATH.read_text(encoding="utf-8").splitlines():
        # line 去除首尾空白；空行和感叹号注释无需解析。
        line = raw_line.strip()
        if not line or line.startswith("!"):
            continue
        # fields 统一转大写判断命令，数值字段仍保留原字符串。
        fields = [field.strip() for field in line.split(",")]
        command = fields[0].upper()
        if command == "R":
            # KEYOPT(3)=2时R的首个数值就是XYZ三个平动方向共同质量。
            real_mass_by_id[int(fields[1])] = float(fields[2])
        elif command == "REAL":
            # REAL命令只改变后续单元的活动实常数集。
            current_real_id = int(fields[1])
        elif command == "EN":
            if current_real_id is None:
                raise AssertionError("MASS21 EN命令之前没有活动REAL实常数。")
            element_id = int(fields[1])
            node_id = int(fields[2])
            if node_id in mass_by_node:
                raise AssertionError(f"节点{node_id}存在重复MASS21单元。")
            if current_real_id not in real_mass_by_id:
                raise AssertionError(
                    f"MASS21单元{element_id}引用未定义实常数{current_real_id}。"
                )
            mass_by_node[node_id] = {
                "mass21_element_id": element_id,
                "mass21_real_id": current_real_id,
                "mass21_mass_tonne": real_mass_by_id[current_real_id],
            }
    return mass_by_node


def load_force_mapping() -> dict[tuple[str, int, int], list[dict[str, object]]]:
    """读取权威FZ到实体索节点的映射并按站位/幅号分组。

    返回：
        键为 ``(subsystem, mct_node, catwalk)``；值为按物理索序号排序的节点记录。
    """

    # grouped 暂存每个MCT等效节点分配到同一幅物理索的所有记录。
    grouped: dict[tuple[str, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in read_csv_rows(FORCE_MAPPING_PATH):
        subsystem = row["subsystem"]
        mct_node = int(row["mct_node"])
        catwalk = int(row["catwalk"])
        grouped[(subsystem, mct_node, catwalk)].append(
            {
                "subsystem": subsystem,
                "catwalk": catwalk,
                "mct_node": mct_node,
                "rope_index": int(row["rope_index"]),
                "ansys_node": int(row["ansys_node"]),
                "mct_total_fz_kn_per_catwalk": float(
                    row["mct_total_fz_kn_per_catwalk"]
                ),
                "applied_fz_n_per_physical_rope": float(
                    row["applied_fz_n_per_physical_rope"]
                ),
            }
        )

    # 每组内部按索号排序，使后续分号列表和逐节点CSV具有稳定顺序。
    for records in grouped.values():
        records.sort(key=lambda record: int(record["rope_index"]))
    return dict(grouped)


def build_incident_element_counts(
    selected_node_ids: set[int],
) -> dict[int, Counter[str]]:
    """统计选定MASS21节点相邻的基础网格单元类型。

    参数：
        selected_node_ids：只需审计的ANSYS节点号集合。

    返回：
        每个节点到 ``LINK10``/``BEAM4`` 等单元类型计数的Counter。

    该检查证明MASS21确实放在索网格节点，而不是悬空节点；同时为后续拆分质量时
    判断节点拓扑提供机器可用信息。
    """

    # counts 只为选定节点分配Counter，避免存储全部12万单元的邻接表。
    counts: dict[int, Counter[str]] = {
        node_id: Counter() for node_id in selected_node_ids
    }
    for row in read_csv_rows(FULL_ELEMENTS_PATH):
        element_type = row["ansys_element"].upper()
        node_i = int(row["n1"])
        node_j = int(row["n2"])
        if node_i in counts:
            counts[node_i][element_type] += 1
        if node_j in counts:
            counts[node_j][element_type] += 1
    return counts


def semicolon_join(values: Iterable[object]) -> str:
    """把稳定有序值序列写成分号分隔字符串。

    参数：
        values：任意可转字符串的值序列。

    返回：
        不带首尾分号的字符串，适合在宽表中保存节点/单元列表。
    """

    return ";".join(str(value) for value in values)


def component_weight_sum(
    decomposition: dict[str, int],
    component_items: dict[str, dict[str, object]],
) -> float:
    """计算一个唯一分解字典对应的权威总重量。

    参数：
        decomposition：组件ID到数量的字典；
        component_items：组件ID到单处权威重量的字典。

    返回：
        分解后的重量总和，单位kN。
    """

    return math.fsum(
        float(component_items[component_id]["unit_weight_kn"]) * quantity
        for component_id, quantity in decomposition.items()
    )


def validate_group(
    records: list[dict[str, object]],
    expected_rope_count: int,
    expected_fz_kn: float,
) -> None:
    """校验一个MCT站位在单幅物理索中的等分映射。

    参数：
        records：同一子系统、MCT节点、猫道幅号的映射记录；
        expected_rope_count：底索应为16，门架索应为6；
        expected_fz_kn：单幅MCT组合FZ，向下为负。

    返回：
        无；任何数量、索号或荷载闭合错误都会抛出异常。
    """

    if len(records) != expected_rope_count:
        raise AssertionError(
            f"MCT节点{records[0]['mct_node'] if records else 'EMPTY'}映射"
            f"{len(records)}根索，期望{expected_rope_count}根。"
        )

    # expected_indices 用于检查没有漏索、重索或从0开始编号。
    expected_indices = list(range(1, expected_rope_count + 1))
    actual_indices = [int(record["rope_index"]) for record in records]
    if actual_indices != expected_indices:
        raise AssertionError(
            f"MCT节点{records[0]['mct_node']}物理索序号{actual_indices}不连续。"
        )

    for record in records:
        # 每条记录重复保存单幅组合值，必须与MCT直接解析结果一致。
        if not is_close(
            float(record["mct_total_fz_kn_per_catwalk"]), expected_fz_kn
        ):
            raise AssertionError(
                f"MCT节点{record['mct_node']}映射FZ与原MCT不一致。"
            )

    # mapped_total_kn 把各物理索节点N换回kN后求和，应闭合单幅MCT组合值。
    mapped_total_kn = math.fsum(
        float(record["applied_fz_n_per_physical_rope"]) for record in records
    ) / 1000.0
    if not is_close(mapped_total_kn, expected_fz_kn, tolerance=1.0e-9):
        raise AssertionError(
            f"MCT节点{records[0]['mct_node']}物理索等分合计{mapped_total_kn} kN，"
            f"不等于{expected_fz_kn} kN。"
        )


def validate_coordinate_match(
    coupling_row: dict[str, str],
    node_row: dict[str, object],
) -> None:
    """校验门架耦合表中的绳点坐标与权威ANSYS节点一致。

    参数：
        coupling_row：``gate_rope_couplings.csv``的一行；
        node_row：对应 ``full_line_beam4_nodes.csv`` 节点记录。

    返回：
        无；任一坐标差超过1e-6 mm即报错。
    """

    # coordinate_pairs 逐轴绑定耦合表字段和节点表字段。
    coordinate_pairs = (
        ("rope_x_mm", "x_mm"),
        ("rope_y_mm", "y_mm"),
        ("rope_z_mm", "z_mm"),
    )
    for coupling_field, node_field in coordinate_pairs:
        coupling_value = float(coupling_row[coupling_field])
        node_value = float(node_row[node_field])
        if not is_close(coupling_value, node_value, tolerance=1.0e-6):
            raise AssertionError(
                f"门架{coupling_row['gate_name']}索{coupling_row['family']} "
                f"#{coupling_row['rope_index']}的{coupling_field}={coupling_value}，"
                f"与节点{node_row['node_id']}的{node_field}={node_value}不一致。"
            )


def main() -> None:
    """执行21处专用站识别、几何配对、质量拆分和审计文件生成。"""

    # required_inputs 明确列出版本绑定所需全部输入；缺一项立即终止。
    required_inputs = (
        MCT_PATH,
        ITEMS_PATH,
        FORCE_MAPPING_PATH,
        FULL_NODES_PATH,
        FULL_ELEMENTS_PATH,
        GATE_FIT_PATH,
        GATE_CENTERLINE_NODES_PATH,
        GATE_CENTERLINE_ELEMENTS_PATH,
        GATE_COUPLINGS_PATH,
        OLD_PROPORTIONAL_STATIONS_PATH,
        DYNAMIC_MASS21_PATH,
    )
    missing_inputs = [str(path) for path in required_inputs if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"缺少输入文件：{missing_inputs}")

    # 第一阶段：载入权威MCT、恒载分项、实体节点和当前MASS21。
    mct_text = read_mct_text(MCT_PATH)
    mct_nodes = parse_mct_nodes(mct_text)
    mct_conloads = parse_mct_secondary_conloads(mct_text)
    component_items = load_component_items()
    full_nodes = load_full_nodes()
    mass21_by_node = parse_dynamic_mass21()
    force_groups = load_force_mapping()

    # dedicated_gate_mct_nodes 是MCT门架索节点1001～1395中21.556 kN的21站。
    dedicated_gate_mct_nodes = sorted(
        node_id
        for node_id in range(1001, 1396)
        if node_id in mct_conloads
        and is_close(abs(mct_conloads[node_id]), DEDICATED_GATE_COMBINATION_KN)
    )

    # passage_bottom_mct_nodes 只允许三种显式横通道组合，避免近似范围筛选误纳塔架荷载。
    passage_bottom_mct_nodes = sorted(
        node_id
        for node_id in range(1, 729)
        if node_id in mct_conloads
        and any(
            is_close(abs(mct_conloads[node_id]), known_value)
            for known_value in PASSAGE_BOTTOM_COMBINATION_KN
        )
    )

    if len(dedicated_gate_mct_nodes) != 21:
        raise AssertionError(
            f"MCT专用三角门架站为{len(dedicated_gate_mct_nodes)}，期望21。"
        )
    if len(passage_bottom_mct_nodes) != 21:
        raise AssertionError(
            f"MCT横通道半幅底索站为{len(passage_bottom_mct_nodes)}，期望21。"
        )

    # 第二阶段：使用gate_fit_audit中原MCT property-3门架拓扑，把门架索站与底索站配对。
    gate_fit_rows = read_csv_rows(GATE_FIT_PATH)
    gate_fit_by_index: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in gate_fit_rows:
        top_node = int(row["mct_top_node"])
        if top_node in dedicated_gate_mct_nodes:
            gate_fit_by_index[int(row["gate_index"])].append(row)

    if len(gate_fit_by_index) != 21:
        raise AssertionError(
            f"gate_fit中匹配到{len(gate_fit_by_index)}个专用门架索引，期望21。"
        )

    # station_pairs 每项保存一处专用门架的稳定索引、上下MCT节点及两幅门架记录。
    station_pairs: list[dict[str, object]] = []
    for gate_index, rows in sorted(gate_fit_by_index.items()):
        if len(rows) != 2:
            raise AssertionError(
                f"门架索引{gate_index}有{len(rows)}幅记录，期望CW1/CW2共2幅。"
            )
        top_nodes = {int(row["mct_top_node"]) for row in rows}
        bottom_nodes = {int(row["mct_bottom_node"]) for row in rows}
        if len(top_nodes) != 1 or len(bottom_nodes) != 1:
            raise AssertionError(f"门架索引{gate_index}两幅MCT节点不一致。")
        top_mct_node = next(iter(top_nodes))
        bottom_mct_node = next(iter(bottom_nodes))
        if bottom_mct_node not in passage_bottom_mct_nodes:
            raise AssertionError(
                f"专用门架MCT节点{top_mct_node}配对底索节点{bottom_mct_node}"
                "不含横通道半幅荷载。"
            )
        station_pairs.append(
            {
                "gate_index": gate_index,
                "top_mct_node": top_mct_node,
                "bottom_mct_node": bottom_mct_node,
                "gate_fit_rows": sorted(rows, key=lambda row: row["gate_name"]),
            }
        )

    # pair_top_nodes/pair_bottom_nodes验证21个配对既无遗漏也无重复。
    pair_top_nodes = [int(pair["top_mct_node"]) for pair in station_pairs]
    pair_bottom_nodes = [int(pair["bottom_mct_node"]) for pair in station_pairs]
    if sorted(pair_top_nodes) != dedicated_gate_mct_nodes:
        raise AssertionError("gate_fit专用门架节点集合与MCT 21.556 kN集合不一致。")
    if sorted(pair_bottom_nodes) != passage_bottom_mct_nodes:
        raise AssertionError("gate_fit底索节点集合与MCT横通道半幅荷载集合不一致。")

    # old_station_rows 仅提供H编号/分跨标签和误差对照，不参与新坐标计算。
    old_station_rows = sorted(
        read_csv_rows(OLD_PROPORTIONAL_STATIONS_PATH),
        key=lambda row: int(row["index"]),
    )
    if len(old_station_rows) != 21:
        raise AssertionError("旧比例映射CSV不是21行，无法稳定继承H编号。")
    actual_span_counts = Counter(row["span"] for row in old_station_rows)
    if dict(actual_span_counts) != EXPECTED_SPAN_COUNTS:
        raise AssertionError(
            f"旧H编号分跨计数{dict(actual_span_counts)}与预期{EXPECTED_SPAN_COUNTS}不一致。"
        )

    # 第三阶段：读门架中心线/单元/耦合几何，并按gate_name建立索引。
    gate_centerline_nodes = read_csv_rows(GATE_CENTERLINE_NODES_PATH)
    gate_centerline_elements = read_csv_rows(GATE_CENTERLINE_ELEMENTS_PATH)
    gate_couplings = read_csv_rows(GATE_COUPLINGS_PATH)

    centerline_nodes_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in gate_centerline_nodes:
        centerline_nodes_by_gate[row["gate_name"]].append(row)
    centerline_elements_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in gate_centerline_elements:
        centerline_elements_by_gate[row["gate_name"]].append(row)
    couplings_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in gate_couplings:
        couplings_by_gate[row["gate_name"]].append(row)

    # 第四阶段：先收集全部选定物理节点，随后一次统计基础网格邻接单元。
    selected_ansys_node_ids: set[int] = set()
    for pair in station_pairs:
        bottom_node = int(pair["bottom_mct_node"])
        top_node = int(pair["top_mct_node"])
        for catwalk in (1, 2):
            bottom_records = force_groups[("bottom", bottom_node, catwalk)]
            gate_records = force_groups[("gate", top_node, catwalk)]
            selected_ansys_node_ids.update(
                int(record["ansys_node"]) for record in bottom_records
            )
            selected_ansys_node_ids.update(
                int(record["ansys_node"]) for record in gate_records
            )
    incident_counts = build_incident_element_counts(selected_ansys_node_ids)

    # 以下列表分别保存七类输出表；全部通过验证后才一次写盘。
    station_output_rows: list[dict[str, object]] = []
    component_output_rows: list[dict[str, object]] = []
    mass_node_output_rows: list[dict[str, object]] = []
    allocation_output_rows: list[dict[str, object]] = []
    gate_node_output_rows: list[dict[str, object]] = []
    gate_element_output_rows: list[dict[str, object]] = []
    gate_coupling_output_rows: list[dict[str, object]] = []

    # coordinate_offsets 和 old_errors 用于最终统计坐标系闭合与旧映射误差。
    coordinate_offsets: list[float] = []
    old_bottom_errors_mm: list[float] = []
    old_gate_center_errors_mm: list[float] = []

    # total_existing_mass21_tonne 累计当前MASS21中与21个专用站相关的组合质量。
    total_existing_mass21_tonne = 0.0

    # 逐站循环严格按北到南gate_index顺序，因此与H01～H21一一对应。
    for passage_zero_index, pair in enumerate(station_pairs):
        passage_index = passage_zero_index + 1
        passage_id = f"H{passage_index:02d}"
        old_row = old_station_rows[passage_zero_index]
        if old_row["name"] != passage_id:
            raise AssertionError(
                f"旧站位第{passage_index}行名称为{old_row['name']}，期望{passage_id}。"
            )

        gate_index = int(pair["gate_index"])
        bottom_mct_node = int(pair["bottom_mct_node"])
        gate_mct_node = int(pair["top_mct_node"])
        bottom_fz_kn = mct_conloads[bottom_mct_node]
        gate_fz_kn = mct_conloads[gate_mct_node]
        bottom_decomposition = decompose_bottom_load(abs(bottom_fz_kn))
        gate_decomposition = decompose_gate_load(abs(gate_fz_kn))

        # 分解后的分项重量必须严格闭合MCT组合值。
        if not is_close(
            component_weight_sum(bottom_decomposition, component_items),
            abs(bottom_fz_kn),
            tolerance=1.0e-9,
        ):
            raise AssertionError(f"{passage_id}底索组件分解不闭合。")
        if not is_close(
            component_weight_sum(gate_decomposition, component_items),
            abs(gate_fz_kn),
            tolerance=1.0e-9,
        ):
            raise AssertionError(f"{passage_id}门架组件分解不闭合。")

        # 两幅gate_fit记录只在名称前缀不同，其站位和高度应一致。
        fit_rows = list(pair["gate_fit_rows"])
        fit_by_catwalk = {
            1 if row["gate_name"].startswith("CW1_") else 2: row
            for row in fit_rows
        }
        if set(fit_by_catwalk) != {1, 2}:
            raise AssertionError(f"{passage_id}无法区分CW1/CW2门架记录。")

        # MCT坐标分别保留底索和门架索；二者顺桥位置相差0～9.3 mm是实物偏置而非误差。
        bottom_mct_x, bottom_mct_y, bottom_mct_z = mct_nodes[bottom_mct_node]
        gate_mct_x, gate_mct_y, gate_mct_z = mct_nodes[gate_mct_node]

        # 横向通道局部1500 mm顺桥宽度需要随底索局部坡度旋转。由于站位恰好落在
        # MCT折线节点上，左段与右段坡度一般略有差异；同时输出左右坡度和跨相邻两点
        # 的中心弦坡度，避免后续生成器默默选取某一侧。中心弦坡度可作为对称放置的
        # 推荐值，但三者都保留以便与施工图连接细节复核。
        if (bottom_mct_node - 1) not in mct_nodes or (
            bottom_mct_node + 1
        ) not in mct_nodes:
            raise AssertionError(
                f"{passage_id}底索MCT节点{bottom_mct_node}缺少相邻节点，无法计算坡度。"
            )
        previous_mct_x, _previous_mct_y, previous_mct_z = mct_nodes[
            bottom_mct_node - 1
        ]
        next_mct_x, _next_mct_y, next_mct_z = mct_nodes[bottom_mct_node + 1]
        bottom_left_slope_degree = math.degrees(
            math.atan2(
                bottom_mct_z - previous_mct_z,
                bottom_mct_x - previous_mct_x,
            )
        )
        bottom_right_slope_degree = math.degrees(
            math.atan2(
                next_mct_z - bottom_mct_z,
                next_mct_x - bottom_mct_x,
            )
        )
        bottom_central_chord_slope_degree = math.degrees(
            math.atan2(
                next_mct_z - previous_mct_z,
                next_mct_x - previous_mct_x,
            )
        )

        # 使用CW1第一根底索/门架索节点取得当前ANSYS坐标变换后的站位。
        bottom_group_cw1 = force_groups[("bottom", bottom_mct_node, 1)]
        gate_group_cw1 = force_groups[("gate", gate_mct_node, 1)]
        validate_group(bottom_group_cw1, 16, bottom_fz_kn)
        validate_group(gate_group_cw1, 6, gate_fz_kn)
        bottom_reference_node = full_nodes[int(bottom_group_cw1[0]["ansys_node"])]
        gate_reference_node = full_nodes[int(gate_group_cw1[0]["ansys_node"])]
        bottom_station_y_mm = float(bottom_reference_node["y_mm"])
        gate_top_station_y_mm = float(gate_reference_node["y_mm"])
        bottom_reference_z_mm = float(bottom_reference_node["z_mm"])
        gate_top_reference_z_mm = float(gate_reference_node["z_mm"])

        # gate_centerline_y_mm 直接读取已经通过两幅一致性检查的门架中心线站位。
        gate_centerline_y_values = {
            float(row["station_y_mm"]) for row in fit_rows
        }
        if len(gate_centerline_y_values) != 1:
            raise AssertionError(f"{passage_id}两幅门架中心线Y不一致。")
        gate_centerline_y_mm = next(iter(gate_centerline_y_values))

        # 坐标变换应满足ANSYS Y=MCT X-831091 mm。
        coordinate_offsets.append(bottom_mct_x - bottom_station_y_mm)
        coordinate_offsets.append(gate_mct_x - gate_top_station_y_mm)

        old_y_mm = float(old_row["global_y_mm"])
        old_bottom_error_mm = bottom_station_y_mm - old_y_mm
        old_gate_center_error_mm = gate_centerline_y_mm - old_y_mm
        old_bottom_errors_mm.append(old_bottom_error_mm)
        old_gate_center_errors_mm.append(old_gate_center_error_mm)

        # 以下字典缓存每一幅、每个子系统的映射节点/质量单元列表，供宽表复用。
        groups_by_catwalk_and_subsystem: dict[
            tuple[int, str], list[dict[str, object]]
        ] = {}
        for catwalk in (1, 2):
            for subsystem, mct_node, expected_count, expected_fz in (
                ("bottom", bottom_mct_node, 16, bottom_fz_kn),
                ("gate", gate_mct_node, 6, gate_fz_kn),
            ):
                records = force_groups[(subsystem, mct_node, catwalk)]
                validate_group(records, expected_count, expected_fz)
                groups_by_catwalk_and_subsystem[(catwalk, subsystem)] = records

                # decomposition 决定当前组合MASS21中各物理组件的可拆分份额。
                decomposition = (
                    bottom_decomposition if subsystem == "bottom" else gate_decomposition
                )
                component_count = expected_count

                for record in records:
                    ansys_node = int(record["ansys_node"])
                    if ansys_node not in full_nodes:
                        raise AssertionError(f"ANSYS节点{ansys_node}在节点CSV中不存在。")
                    if ansys_node not in mass21_by_node:
                        raise AssertionError(f"ANSYS节点{ansys_node}没有当前MASS21单元。")

                    node = full_nodes[ansys_node]
                    mass_record = mass21_by_node[ansys_node]
                    nodal_weight_kn = abs(
                        float(record["applied_fz_n_per_physical_rope"])
                    ) / 1000.0
                    expected_nodal_mass_tonne = (
                        nodal_weight_kn / GRAVITY_KN_PER_TONNE
                    )
                    actual_nodal_mass_tonne = float(
                        mass_record["mass21_mass_tonne"]
                    )
                    if not is_close(
                        actual_nodal_mass_tonne,
                        expected_nodal_mass_tonne,
                        tolerance=1.0e-12,
                    ):
                        raise AssertionError(
                            f"节点{ansys_node}的MASS21质量{actual_nodal_mass_tonne} tonne"
                            f"与FZ换算{expected_nodal_mass_tonne} tonne不一致。"
                        )

                    # 每个组合MASS21只累计一次；分项分配行不能重复进入总量。
                    total_existing_mass21_tonne += actual_nodal_mass_tonne

                    counts = incident_counts[ansys_node]
                    mass_node_output_rows.append(
                        {
                            "passage_index": passage_index,
                            "passage_id": passage_id,
                            "span": old_row["span"],
                            "gate_index": gate_index,
                            "catwalk": catwalk,
                            "subsystem": subsystem,
                            "mct_node": mct_node,
                            "rope_index": int(record["rope_index"]),
                            "ansys_node": ansys_node,
                            "ansys_x_mm": float(node["x_mm"]),
                            "ansys_y_mm": float(node["y_mm"]),
                            "ansys_z_mm": float(node["z_mm"]),
                            "node_family": node["family"],
                            "node_source": node["source"],
                            "mct_combined_fz_kn_per_catwalk": expected_fz,
                            "applied_fz_n_at_node": float(
                                record["applied_fz_n_per_physical_rope"]
                            ),
                            "combined_weight_kn_at_node": nodal_weight_kn,
                            "combined_mass_tonne_at_node": actual_nodal_mass_tonne,
                            "mass21_element_id": int(
                                mass_record["mass21_element_id"]
                            ),
                            "mass21_real_id": int(mass_record["mass21_real_id"]),
                            "incident_link10_count": counts["LINK10"],
                            "incident_beam4_count": counts["BEAM4"],
                            "incident_total_element_count": sum(counts.values()),
                            "component_ids_in_combined_mass": semicolon_join(
                                decomposition.keys()
                            ),
                        }
                    )

                    # allocation_output_rows把组合MASS21按权威分项拆成可迁移质量。
                    for component_id, quantity in decomposition.items():
                        item = component_items[component_id]
                        component_weight_kn_per_catwalk = (
                            float(item["unit_weight_kn"]) * quantity
                        )
                        component_weight_kn_at_node = (
                            component_weight_kn_per_catwalk / component_count
                        )
                        component_mass_tonne_at_node = (
                            component_weight_kn_at_node / GRAVITY_KN_PER_TONNE
                        )
                        allocation_output_rows.append(
                            {
                                "passage_index": passage_index,
                                "passage_id": passage_id,
                                "span": old_row["span"],
                                "gate_index": gate_index,
                                "catwalk": catwalk,
                                "subsystem": subsystem,
                                "mct_node": mct_node,
                                "rope_index": int(record["rope_index"]),
                                "ansys_node": ansys_node,
                                "mass21_element_id": int(
                                    mass_record["mass21_element_id"]
                                ),
                                "component_id": component_id,
                                "component_name": item["component_name"],
                                "component_quantity_at_station": quantity,
                                "component_weight_kn_per_catwalk_station": (
                                    component_weight_kn_per_catwalk
                                ),
                                "distribution_node_count": component_count,
                                "component_weight_kn_at_node": (
                                    component_weight_kn_at_node
                                ),
                                "component_mass_tonne_at_node": (
                                    component_mass_tonne_at_node
                                ),
                                "allocation_note": (
                                    "当前MASS21只保存组合质量；本行是按权威分项/物理索数"
                                    "等分得到的可迁移份额，不是现有独立MASS21单元。"
                                ),
                            }
                        )

        # 每站×每幅×每组件输出聚合清单，便于直接按实物类别迁移质量。
        for catwalk in (1, 2):
            for subsystem, mct_node, decomposition in (
                ("bottom", bottom_mct_node, bottom_decomposition),
                ("gate", gate_mct_node, gate_decomposition),
            ):
                records = groups_by_catwalk_and_subsystem[(catwalk, subsystem)]
                for component_id, quantity in decomposition.items():
                    item = component_items[component_id]
                    unit_weight_kn = float(item["unit_weight_kn"])
                    station_weight_kn = unit_weight_kn * quantity
                    station_mass_tonne = station_weight_kn / GRAVITY_KN_PER_TONNE
                    component_output_rows.append(
                        {
                            "passage_index": passage_index,
                            "passage_id": passage_id,
                            "span": old_row["span"],
                            "gate_index": gate_index,
                            "catwalk": catwalk,
                            "subsystem": subsystem,
                            "mct_node": mct_node,
                            "component_id": component_id,
                            "component_name": item["component_name"],
                            "authority_category": item["category"],
                            "authority": item["authority"],
                            "quantity_at_station_per_catwalk": quantity,
                            "unit_weight_kn": unit_weight_kn,
                            "weight_kn_per_catwalk_station": station_weight_kn,
                            "mass_tonne_per_catwalk_station": station_mass_tonne,
                            "original_distribution_node_count": len(records),
                            "original_weight_kn_per_node": station_weight_kn
                            / len(records),
                            "original_mass_tonne_per_node": station_mass_tonne
                            / len(records),
                            "original_ansys_nodes": semicolon_join(
                                int(record["ansys_node"]) for record in records
                            ),
                            "original_mass21_elements": semicolon_join(
                                int(
                                    mass21_by_node[int(record["ansys_node"])][
                                        "mass21_element_id"
                                    ]
                                )
                                for record in records
                            ),
                            "relocation_note": (
                                "迁移到精细杆系时只移除此组件份额；同一原MASS21还含本组合"
                                "其他组件，不能整单元删除后遗漏。"
                            ),
                        }
                    )

        # 生成两幅专用门架的中心线节点、单元和绳点耦合长表。
        for catwalk in (1, 2):
            gate_name = f"CW{catwalk}_GATE_{gate_index:02d}"
            center_nodes = sorted(
                centerline_nodes_by_gate[gate_name],
                key=lambda row: int(row["node_id"]),
            )
            center_elements = sorted(
                centerline_elements_by_gate[gate_name],
                key=lambda row: int(row["element_id"]),
            )
            coupling_rows = sorted(
                couplings_by_gate[gate_name],
                key=lambda row: (
                    0 if row["family"] == "BOTTOM_PHI50" else 1,
                    int(row["rope_index"]),
                ),
            )
            if len(center_nodes) != 8 or len(center_elements) != 4:
                raise AssertionError(
                    f"{gate_name}中心线为{len(center_nodes)}节点/{len(center_elements)}单元，"
                    "期望8节点/4单元。"
                )
            if len(coupling_rows) != 22:
                raise AssertionError(
                    f"{gate_name}绳点耦合为{len(coupling_rows)}，期望16+6=22。"
                )

            for row in center_nodes:
                gate_node_output_rows.append(
                    {
                        "passage_index": passage_index,
                        "passage_id": passage_id,
                        "span": old_row["span"],
                        "gate_index": gate_index,
                        "catwalk": catwalk,
                        "gate_name": gate_name,
                        "centerline_node_id": int(row["node_id"]),
                        "role": row["role"],
                        "x_mm": float(row["x_mm"]),
                        "y_mm": float(row["y_mm"]),
                        "z_mm": float(row["z_mm"]),
                    }
                )
            for row in center_elements:
                gate_element_output_rows.append(
                    {
                        "passage_index": passage_index,
                        "passage_id": passage_id,
                        "span": old_row["span"],
                        "gate_index": gate_index,
                        "catwalk": catwalk,
                        "gate_name": gate_name,
                        "centerline_element_id": int(row["element_id"]),
                        "n1": int(row["n1"]),
                        "n2": int(row["n2"]),
                        "member": row["member"],
                    }
                )

            for row in coupling_rows:
                subsystem = "bottom" if row["family"] == "BOTTOM_PHI50" else "gate"
                mct_node = bottom_mct_node if subsystem == "bottom" else gate_mct_node
                records = groups_by_catwalk_and_subsystem[(catwalk, subsystem)]
                record_by_rope = {
                    int(record["rope_index"]): record for record in records
                }
                rope_index = int(row["rope_index"])
                if rope_index not in record_by_rope:
                    raise AssertionError(
                        f"{gate_name}耦合索{row['family']} #{rope_index}无权威节点映射。"
                    )
                record = record_by_rope[rope_index]
                ansys_node = int(record["ansys_node"])
                node = full_nodes[ansys_node]
                validate_coordinate_match(row, node)
                mass_record = mass21_by_node[ansys_node]
                gate_coupling_output_rows.append(
                    {
                        "passage_index": passage_index,
                        "passage_id": passage_id,
                        "span": old_row["span"],
                        "gate_index": gate_index,
                        "catwalk": catwalk,
                        "gate_name": gate_name,
                        "subsystem": subsystem,
                        "mct_node": mct_node,
                        "family": row["family"],
                        "rope_index": rope_index,
                        "ansys_rope_node": ansys_node,
                        "rope_x_mm": float(row["rope_x_mm"]),
                        "rope_y_mm": float(row["rope_y_mm"]),
                        "rope_z_mm": float(row["rope_z_mm"]),
                        "beam_axis_x_mm": float(row["beam_axis_x_mm"]),
                        "beam_axis_y_mm": float(row["beam_axis_y_mm"]),
                        "beam_axis_z_mm": float(row["beam_axis_z_mm"]),
                        "rigid_offset_z_mm": float(row["rigid_offset_z_mm"]),
                        "surface_gap_mm": float(row["surface_gap_mm"]),
                        "original_mass21_element_id": int(
                            mass_record["mass21_element_id"]
                        ),
                        "original_mass21_real_id": int(
                            mass_record["mass21_real_id"]
                        ),
                        "original_combined_mass_tonne": float(
                            mass_record["mass21_mass_tonne"]
                        ),
                    }
                )

        # 宽表中的节点/质量列表按CW1、CW2分别生成，便于APDL生成器直接读取。
        bottom_nodes_cw1 = groups_by_catwalk_and_subsystem[(1, "bottom")]
        bottom_nodes_cw2 = groups_by_catwalk_and_subsystem[(2, "bottom")]
        gate_nodes_cw1 = groups_by_catwalk_and_subsystem[(1, "gate")]
        gate_nodes_cw2 = groups_by_catwalk_and_subsystem[(2, "gate")]

        # component_value返回本站某组件的单幅重量；组合未含该件时返回0。
        def component_value(component_id: str) -> float:
            """返回当前站某组件的单幅权威重量，未出现时返回0 kN。"""

            quantity = bottom_decomposition.get(
                component_id, gate_decomposition.get(component_id, 0)
            )
            return float(component_items[component_id]["unit_weight_kn"]) * quantity

        # dedicated_weight_kn_per_catwalk包含该站底索组合与门架组合的所有实物。
        dedicated_weight_kn_per_catwalk = abs(bottom_fz_kn) + abs(gate_fz_kn)
        station_output_rows.append(
            {
                "passage_index": passage_index,
                "passage_id": passage_id,
                "span": old_row["span"],
                "gate_index": gate_index,
                "gate_name_cw1": f"CW1_GATE_{gate_index:02d}",
                "gate_name_cw2": f"CW2_GATE_{gate_index:02d}",
                "mct_property3_element": int(
                    fit_by_catwalk[1]["mct_property3_element"]
                ),
                "mct_bottom_node": bottom_mct_node,
                "mct_gate_node": gate_mct_node,
                "mct_bottom_x_mm": bottom_mct_x,
                "mct_bottom_y_mm": bottom_mct_y,
                "mct_bottom_z_mm": bottom_mct_z,
                "mct_gate_x_mm": gate_mct_x,
                "mct_gate_y_mm": gate_mct_y,
                "mct_gate_z_mm": gate_mct_z,
                "ansys_passage_center_x_mm": 0.0,
                "ansys_bottom_station_y_mm": bottom_station_y_mm,
                "ansys_gate_top_station_y_mm": gate_top_station_y_mm,
                "ansys_gate_centerline_y_mm": gate_centerline_y_mm,
                "ansys_passage_top_chord_reference_z_mm": bottom_reference_z_mm,
                "ansys_gate_top_rope_z_mm": gate_top_reference_z_mm,
                "bottom_left_segment_slope_degree": bottom_left_slope_degree,
                "bottom_right_segment_slope_degree": bottom_right_slope_degree,
                "bottom_central_chord_slope_degree": (
                    bottom_central_chord_slope_degree
                ),
                "gate_top_bottom_station_mismatch_mm": gate_top_station_y_mm
                - bottom_station_y_mm,
                "old_proportional_global_y_mm": old_y_mm,
                "authority_bottom_minus_old_y_mm": old_bottom_error_mm,
                "authority_gate_center_minus_old_y_mm": old_gate_center_error_mm,
                "bottom_mct_combined_weight_kn_per_catwalk": abs(bottom_fz_kn),
                "gate_mct_combined_weight_kn_per_catwalk": abs(gate_fz_kn),
                "dedicated_total_weight_kn_per_catwalk": dedicated_weight_kn_per_catwalk,
                "dedicated_total_mass_tonne_per_catwalk": (
                    dedicated_weight_kn_per_catwalk / GRAVITY_KN_PER_TONNE
                ),
                "dedicated_total_weight_kn_two_catwalks": (
                    2.0 * dedicated_weight_kn_per_catwalk
                ),
                "dedicated_total_mass_tonne_two_catwalks": (
                    2.0
                    * dedicated_weight_kn_per_catwalk
                    / GRAVITY_KN_PER_TONNE
                ),
                "cross_passage_half_weight_kn_per_catwalk": component_value(
                    "cross_passage_half"
                ),
                "cross_passage_full_weight_kn_two_catwalks": 2.0
                * component_value("cross_passage_half"),
                "cross_passage_full_mass_tonne_two_catwalks": 2.0
                * component_value("cross_passage_half")
                / GRAVITY_KN_PER_TONNE,
                "cross_passage_tri_gate_weight_kn_per_catwalk": component_value(
                    "cross_passage_tri_gate"
                ),
                "gate_bottom_beam_weight_kn_per_catwalk": component_value(
                    "gate_bottom_beam"
                ),
                "guide_roller_weight_kn_per_catwalk": component_value(
                    "guide_roller"
                ),
                "main_cable_restrainer_weight_kn_per_catwalk": component_value(
                    "main_cable_restrainer"
                ),
                "pws_roller_weight_kn_per_catwalk": component_value("pws_roller"),
                "large_crossbeam_weight_kn_per_catwalk": component_value(
                    "large_crossbeam"
                ),
                "bottom_component_ids": semicolon_join(bottom_decomposition.keys()),
                "gate_component_ids": semicolon_join(gate_decomposition.keys()),
                "bottom_ansys_nodes_cw1": semicolon_join(
                    int(record["ansys_node"]) for record in bottom_nodes_cw1
                ),
                "bottom_ansys_nodes_cw2": semicolon_join(
                    int(record["ansys_node"]) for record in bottom_nodes_cw2
                ),
                "gate_ansys_nodes_cw1": semicolon_join(
                    int(record["ansys_node"]) for record in gate_nodes_cw1
                ),
                "gate_ansys_nodes_cw2": semicolon_join(
                    int(record["ansys_node"]) for record in gate_nodes_cw2
                ),
                "bottom_mass21_elements_cw1": semicolon_join(
                    int(mass21_by_node[int(record["ansys_node"])]["mass21_element_id"])
                    for record in bottom_nodes_cw1
                ),
                "bottom_mass21_elements_cw2": semicolon_join(
                    int(mass21_by_node[int(record["ansys_node"])]["mass21_element_id"])
                    for record in bottom_nodes_cw2
                ),
                "gate_mass21_elements_cw1": semicolon_join(
                    int(mass21_by_node[int(record["ansys_node"])]["mass21_element_id"])
                    for record in gate_nodes_cw1
                ),
                "gate_mass21_elements_cw2": semicolon_join(
                    int(mass21_by_node[int(record["ansys_node"])]["mass21_element_id"])
                    for record in gate_nodes_cw2
                ),
                "recommended_finite_model_station_rule": (
                    "门架中心线保留gate_centerline_y；底梁/顶梁分别用刚臂连接bottom/gate"
                    "原索节点；横通道顶弦参考点连接bottom站，不再使用old比例Y。"
                ),
            }
        )

    # 第五阶段：执行全局数量、质量和坐标闭合检查。
    if len(station_output_rows) != 21:
        raise AssertionError("权威站位宽表不是21行。")
    if len(mass_node_output_rows) != 21 * 2 * (16 + 6):
        raise AssertionError(
            f"专用站MASS21节点表为{len(mass_node_output_rows)}行，期望924行。"
        )
    if len(gate_node_output_rows) != 21 * 2 * 8:
        raise AssertionError("专用门架中心线节点表数量不等于21×2×8。")
    if len(gate_element_output_rows) != 21 * 2 * 4:
        raise AssertionError("专用门架中心线单元表数量不等于21×2×4。")
    if len(gate_coupling_output_rows) != 21 * 2 * 22:
        raise AssertionError("专用门架耦合表数量不等于21×2×22。")

    # coordinate_offset_spread_mm应接近机器舍入误差；均值应为831091 mm。
    coordinate_offset_spread_mm = max(coordinate_offsets) - min(coordinate_offsets)
    coordinate_offset_mean_mm = fmean(coordinate_offsets)
    if coordinate_offset_spread_mm > 1.0e-6 or not is_close(
        coordinate_offset_mean_mm,
        EXPECTED_MCT_X_TO_ANSYS_Y_OFFSET_MM,
        tolerance=1.0e-6,
    ):
        raise AssertionError(
            f"MCT X到ANSYS Y平移均值/极差为{coordinate_offset_mean_mm}/"
            f"{coordinate_offset_spread_mm} mm，与预期不符。"
        )

    # allocation_mass_tonne按组件分配行累计，应与924个组合MASS21总量完全一致。
    allocation_mass_tonne = math.fsum(
        float(row["component_mass_tonne_at_node"])
        for row in allocation_output_rows
    )
    if not is_close(
        allocation_mass_tonne,
        total_existing_mass21_tonne,
        tolerance=1.0e-9,
    ):
        raise AssertionError(
            f"组件分配质量{allocation_mass_tonne} tonne与原组合MASS21"
            f"{total_existing_mass21_tonne} tonne不闭合。"
        )

    # 第六阶段：以固定字段顺序写出全部机器可用CSV。
    station_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "gate_name_cw1",
        "gate_name_cw2",
        "mct_property3_element",
        "mct_bottom_node",
        "mct_gate_node",
        "mct_bottom_x_mm",
        "mct_bottom_y_mm",
        "mct_bottom_z_mm",
        "mct_gate_x_mm",
        "mct_gate_y_mm",
        "mct_gate_z_mm",
        "ansys_passage_center_x_mm",
        "ansys_bottom_station_y_mm",
        "ansys_gate_top_station_y_mm",
        "ansys_gate_centerline_y_mm",
        "ansys_passage_top_chord_reference_z_mm",
        "ansys_gate_top_rope_z_mm",
        "bottom_left_segment_slope_degree",
        "bottom_right_segment_slope_degree",
        "bottom_central_chord_slope_degree",
        "gate_top_bottom_station_mismatch_mm",
        "old_proportional_global_y_mm",
        "authority_bottom_minus_old_y_mm",
        "authority_gate_center_minus_old_y_mm",
        "bottom_mct_combined_weight_kn_per_catwalk",
        "gate_mct_combined_weight_kn_per_catwalk",
        "dedicated_total_weight_kn_per_catwalk",
        "dedicated_total_mass_tonne_per_catwalk",
        "dedicated_total_weight_kn_two_catwalks",
        "dedicated_total_mass_tonne_two_catwalks",
        "cross_passage_half_weight_kn_per_catwalk",
        "cross_passage_full_weight_kn_two_catwalks",
        "cross_passage_full_mass_tonne_two_catwalks",
        "cross_passage_tri_gate_weight_kn_per_catwalk",
        "gate_bottom_beam_weight_kn_per_catwalk",
        "guide_roller_weight_kn_per_catwalk",
        "main_cable_restrainer_weight_kn_per_catwalk",
        "pws_roller_weight_kn_per_catwalk",
        "large_crossbeam_weight_kn_per_catwalk",
        "bottom_component_ids",
        "gate_component_ids",
        "bottom_ansys_nodes_cw1",
        "bottom_ansys_nodes_cw2",
        "gate_ansys_nodes_cw1",
        "gate_ansys_nodes_cw2",
        "bottom_mass21_elements_cw1",
        "bottom_mass21_elements_cw2",
        "gate_mass21_elements_cw1",
        "gate_mass21_elements_cw2",
        "recommended_finite_model_station_rule",
    ]
    component_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "subsystem",
        "mct_node",
        "component_id",
        "component_name",
        "authority_category",
        "authority",
        "quantity_at_station_per_catwalk",
        "unit_weight_kn",
        "weight_kn_per_catwalk_station",
        "mass_tonne_per_catwalk_station",
        "original_distribution_node_count",
        "original_weight_kn_per_node",
        "original_mass_tonne_per_node",
        "original_ansys_nodes",
        "original_mass21_elements",
        "relocation_note",
    ]
    mass_node_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "subsystem",
        "mct_node",
        "rope_index",
        "ansys_node",
        "ansys_x_mm",
        "ansys_y_mm",
        "ansys_z_mm",
        "node_family",
        "node_source",
        "mct_combined_fz_kn_per_catwalk",
        "applied_fz_n_at_node",
        "combined_weight_kn_at_node",
        "combined_mass_tonne_at_node",
        "mass21_element_id",
        "mass21_real_id",
        "incident_link10_count",
        "incident_beam4_count",
        "incident_total_element_count",
        "component_ids_in_combined_mass",
    ]
    allocation_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "subsystem",
        "mct_node",
        "rope_index",
        "ansys_node",
        "mass21_element_id",
        "component_id",
        "component_name",
        "component_quantity_at_station",
        "component_weight_kn_per_catwalk_station",
        "distribution_node_count",
        "component_weight_kn_at_node",
        "component_mass_tonne_at_node",
        "allocation_note",
    ]
    gate_node_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "gate_name",
        "centerline_node_id",
        "role",
        "x_mm",
        "y_mm",
        "z_mm",
    ]
    gate_element_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "gate_name",
        "centerline_element_id",
        "n1",
        "n2",
        "member",
    ]
    gate_coupling_fields = [
        "passage_index",
        "passage_id",
        "span",
        "gate_index",
        "catwalk",
        "gate_name",
        "subsystem",
        "mct_node",
        "family",
        "rope_index",
        "ansys_rope_node",
        "rope_x_mm",
        "rope_y_mm",
        "rope_z_mm",
        "beam_axis_x_mm",
        "beam_axis_y_mm",
        "beam_axis_z_mm",
        "rigid_offset_z_mm",
        "surface_gap_mm",
        "original_mass21_element_id",
        "original_mass21_real_id",
        "original_combined_mass_tonne",
    ]

    write_csv(STATION_OUTPUT_PATH, station_fields, station_output_rows)
    write_csv(COMPONENT_OUTPUT_PATH, component_fields, component_output_rows)
    write_csv(MASS_NODE_OUTPUT_PATH, mass_node_fields, mass_node_output_rows)
    write_csv(
        COMPONENT_ALLOCATION_OUTPUT_PATH,
        allocation_fields,
        allocation_output_rows,
    )
    write_csv(GATE_NODE_OUTPUT_PATH, gate_node_fields, gate_node_output_rows)
    write_csv(GATE_ELEMENT_OUTPUT_PATH, gate_element_fields, gate_element_output_rows)
    write_csv(
        GATE_COUPLING_OUTPUT_PATH,
        gate_coupling_fields,
        gate_coupling_output_rows,
    )

    # 第七阶段：形成JSON总审计，集中给出权威节点列表、误差和质量闭合。
    component_totals_two_catwalks: dict[str, dict[str, float]] = {}
    for component_id in ALL_PASSAGE_COMPONENT_IDS:
        matching_rows = [
            row
            for row in component_output_rows
            if row["component_id"] == component_id
        ]
        total_weight_kn = math.fsum(
            float(row["weight_kn_per_catwalk_station"]) for row in matching_rows
        )
        component_totals_two_catwalks[component_id] = {
            "weight_kn": total_weight_kn,
            "mass_tonne": total_weight_kn / GRAVITY_KN_PER_TONNE,
            "inventory_row_count": len(matching_rows),
        }

    audit = {
        "schema": "attachment23_authoritative_passage_station_mass_map_v2",
        "status": "PASS",
        "authority_rule": (
            "21个MCT门架索21.556 kN站（cross_passage_tri_gate+guide_roller）"
            "通过gate_fit中的原MCT property-3门架，与21个含cross_passage_half的"
            "底索组合站严格一一配对；旧比例映射不参与坐标。"
        ),
        "source_binding_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
            for path in required_inputs
        },
        "counts": {
            "passage_station_count": len(station_output_rows),
            "dedicated_gate_mct_node_count": len(dedicated_gate_mct_nodes),
            "passage_bottom_mct_node_count": len(passage_bottom_mct_nodes),
            "selected_mass21_node_count": len(mass_node_output_rows),
            "component_inventory_row_count": len(component_output_rows),
            "component_allocation_row_count": len(allocation_output_rows),
            "gate_centerline_node_row_count": len(gate_node_output_rows),
            "gate_centerline_element_row_count": len(gate_element_output_rows),
            "gate_rope_coupling_row_count": len(gate_coupling_output_rows),
        },
        "authoritative_mct_nodes": {
            "gate_21_556_kn": dedicated_gate_mct_nodes,
            "bottom_contains_cross_passage_half": passage_bottom_mct_nodes,
            "gate_indices": [int(pair["gate_index"]) for pair in station_pairs],
        },
        "coordinate_check": {
            "mct_x_minus_ansys_y_mean_mm": coordinate_offset_mean_mm,
            "mct_x_minus_ansys_y_spread_mm": coordinate_offset_spread_mm,
            "expected_offset_mm": EXPECTED_MCT_X_TO_ANSYS_Y_OFFSET_MM,
            "status": "PASS",
        },
        "old_proportional_mapping_error": {
            "bottom_station_signed_min_mm": min(old_bottom_errors_mm),
            "bottom_station_signed_max_mm": max(old_bottom_errors_mm),
            "bottom_station_max_absolute_mm": max(
                abs(value) for value in old_bottom_errors_mm
            ),
            "bottom_station_mean_absolute_mm": fmean(
                abs(value) for value in old_bottom_errors_mm
            ),
            "gate_center_max_absolute_mm": max(
                abs(value) for value in old_gate_center_errors_mm
            ),
            "conclusion": (
                "旧比例站位只保留为误差对照；精细FE必须使用本审计MCT专用站。"
            ),
        },
        "mass_closure": {
            "selected_existing_combined_mass21_tonne": total_existing_mass21_tonne,
            "component_allocation_sum_tonne": allocation_mass_tonne,
            "absolute_difference_tonne": abs(
                total_existing_mass21_tonne - allocation_mass_tonne
            ),
            "status": "PASS",
        },
        "component_totals_two_catwalks_all_21_stations": (
            component_totals_two_catwalks
        ),
        "important_interpretation": {
            "cross_passage_half": (
                "49.69 kN是每幅计1/2；每品完整横向通道为99.38 kN，"
                "21品合计2086.98 kN。"
            ),
            "dedicated_gate": (
                "专用站使用cross_passage_tri_gate=12.360 kN/幅，不得再叠加"
                "ordinary_gate=8.927 kN/幅；门架下横梁3.18 kN/幅在底索组合中另计。"
            ),
            "mass21": (
                "现有MASS21是组合质量。component allocation CSV给出可迁移份额；"
                "不能把一个组合MASS21整单元删除后只恢复横向通道质量。"
            ),
        },
        "uncertainties": [
            (
                "H01～H21名称和分跨标签由附件旧表按北到南顺序继承；原MCT只保存"
                "节点/荷载类型，不保存H编号。21对21单调配对唯一，但名称本身不是MCT字段。"
            ),
            (
                "MCT/报告提供组件总重量，不提供横向通道、导轮和抑位器的质量质心与"
                "转动惯量；精细动力模型应利用CAD杆系空间分布，并逐组件保持本表总质量。"
            ),
            (
                "底索站、门架索站和门架中心线Y相差0～9.3 mm；这是上下索实际站位偏置。"
                "有限元中应保留三套坐标并用刚臂连接，不能再次用单个CP节点抹平。"
            ),
        ],
        "outputs": [
            path.name
            for path in (
                STATION_OUTPUT_PATH,
                COMPONENT_OUTPUT_PATH,
                MASS_NODE_OUTPUT_PATH,
                COMPONENT_ALLOCATION_OUTPUT_PATH,
                GATE_NODE_OUTPUT_PATH,
                GATE_ELEMENT_OUTPUT_PATH,
                GATE_COUPLING_OUTPUT_PATH,
                AUDIT_OUTPUT_PATH,
                README_OUTPUT_PATH,
            )
        ],
    }
    AUDIT_OUTPUT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # README面向人工复核，CSV/JSON仍是后续APDL生成器的唯一机器输入。
    passage_total_weight_kn = component_totals_two_catwalks[
        "cross_passage_half"
    ]["weight_kn"]
    passage_total_mass_tonne = component_totals_two_catwalks[
        "cross_passage_half"
    ]["mass_tonne"]
    readme = f"""# 21处横向通道/专用三角门架权威站位与质量映射

## 结论

- 已从原始MCT“二期”工况识别 **21个21.556 kN专用门架索节点**，并通过
  `gate_fit_audit.csv` 的原MCT property-3门架拓扑，与 **21个含49.69 kN
  横向通道半幅重量的底索节点**逐处一一配对。
- 权威门架MCT节点：`{semicolon_join(dedicated_gate_mct_nodes)}`。
- 权威底索MCT节点：`{semicolon_join(passage_bottom_mct_nodes)}`。
- 对应门架索引：`{semicolon_join(int(pair['gate_index']) for pair in station_pairs)}`。
- 旧比例映射相对权威底索站的最大偏差为
  **{max(abs(value) for value in old_bottom_errors_mm):.3f} mm**，平均绝对偏差为
  **{fmean(abs(value) for value in old_bottom_errors_mm):.3f} mm**；旧Y坐标不得再进入
  精细FE。

## 权威质量口径

- 每品完整横向通道：`49.69×2 = 99.38 kN`，质量
  `{99.38 / GRAVITY_KN_PER_TONNE:.12f} tonne`。
- 21品完整横向通道合计：`{passage_total_weight_kn:.6f} kN`，质量
  `{passage_total_mass_tonne:.12f} tonne`。
- 每个专用站、每幅猫道另含：三角门架12.360 kN、门架下横梁3.18 kN、
  门架导轮组9.196 kN、主缆抑位器14.72 kN；部分站还叠加PWS滚筒1.21 kN
  和/或大横梁1.32 kN，逐站详见CSV。
- 专用站不得再叠加普通门架8.927 kN；现有MASS21是组合质量，迁移时必须按
  `passage_component_mass21_allocation.csv` 分项扣除/恢复。

## 坐标使用规则

1. 门架中心线使用 `ansys_gate_centerline_y_mm`；
2. 底梁与16根底索连接使用 `ansys_bottom_station_y_mm`；
3. 顶梁与6根门架索连接使用 `ansys_gate_top_station_y_mm`；
4. 横向通道顶弦参考高程使用
   `ansys_passage_top_chord_reference_z_mm`，并连接到底索站；
5. 上述Y最多相差9.3 mm，应用刚臂/刚性偏置保留，不应以三向CP合并。

## 机器文件

- `passage_station_authoritative_map.csv`：21行主站位宽表；
- `passage_component_authoritative_inventory.csv`：逐站、逐幅、逐组件重量/质量；
- `passage_mass21_node_map.csv`：924个原MASS21节点/单元映射；
- `passage_component_mass21_allocation.csv`：组合MASS21的逐组件可迁移份额；
- `passage_gate_centerline_nodes.csv` / `...elements.csv`：42榀专用门架中心线；
- `passage_gate_rope_couplings.csv`：42×22个绳点及刚性偏置；
- `passage_station_mass_map_audit.json`：版本散列、闭合检查和不确定项。

## 仍需在精细动力模型中处理的不确定项

- MCT/报告只给组件总重量，不给组件质心和转动惯量；横向通道杆系应依据CAD
  空间分布布置质量，并保持本表总量、质心和惯性尽可能一致。
- H编号来自附件布置的北到南顺序；MCT本身没有H字段。21处数量、顺序和专用
  载荷类型一致，因此配对唯一，但这一名称来源需保留在审计说明中。
"""
    README_OUTPUT_PATH.write_text(readme, encoding="utf-8")

    # 控制台输出只给关键数量和结果路径，便于批处理日志快速判定成功。
    print(f"PASS: authoritative passage stations = {len(station_output_rows)}")
    print(f"PASS: selected MASS21 nodes = {len(mass_node_output_rows)}")
    print(
        "PASS: selected MASS21/component allocation mass tonne = "
        f"{total_existing_mass21_tonne:.12f}/{allocation_mass_tonne:.12f}"
    )
    print(STATION_OUTPUT_PATH)
    print(AUDIT_OUTPUT_PATH)


# 只有直接执行脚本时才生成结果；作为后续APDL生成器模块导入时不会改写文件。
if __name__ == "__main__":
    main()
