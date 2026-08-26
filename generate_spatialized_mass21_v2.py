# -*- coding: utf-8 -*-
"""生成 V2.0 门架与横向通道空间化 MASS21，并完成质量、重心和惯量闭合审计。

本脚本只重建 MCT 二期集中恒载对应的动力质量，不改变承重索、门架索和下拉索
已经通过材料密度表示的分布质量。原模型把一个 MCT 组合节点的重量等分到 16 根
承重索或 6 根门架索，因此总质量正确，但门架与横向通道的空间质量分布和转动惯量
不正确。本脚本先按权威表 1-2、表 1-3 的已知组合逐项拆分，再执行以下迁移：

* 门架下横梁 3.18 kN/幅/品：按新建下横梁 BEAM188 的体积作节点集中化；
* 普通门架 8.927 kN 或横通道三角门架 12.36 kN：按顶梁和两根立柱体积集中化；
* 导轮组 9.196 kN：等分到顶梁的 6 个门架索连接点；
* 横通道两幅半重 2×49.69 kN：合并为每品 99.38 kN，并按完整杆系体积集中化；
* 大横梁、PWS 滚筒、主缆抑位器、塔架和锚碇架等其余分项保留在原索节点。

坐标和单位统一采用当前 XLongitudinal MAPDL 模型：X 顺桥、Y 横桥、Z 竖向，
长度 mm、质量 tonne、时间 s。重力加速度采用 9806 mm/s²。
"""

from __future__ import annotations

# argparse 用于提供可复算的命令行入口，而不是在源码中隐式依赖当前工作目录。
import argparse
# csv 用于读取权威映射、有限拓扑台账，并写出逐节点与逐分项质量台账。
import csv
# hashlib 用于记录输入文件 SHA256，使审计可以绑定到确切数据版本。
import hashlib
# json 用于输出机器可读的质量、重心和惯量审计结果。
import json
# math 用于有限数检查和少量数值运算。
import math
# defaultdict 用于按节点和分项累加质量，避免重复节点被覆盖。
from collections import defaultdict
# dataclass 用于明确表示三维点和集中质量节点，减少裸字典字段误用。
from dataclasses import dataclass, field
# Path 用于可靠处理含中文与空格的 Windows 路径。
from pathlib import Path
# Mapping、Sequence 等类型用于把函数参数和返回值约束写清楚。
from typing import Iterable, Mapping, Sequence


# G_MM_S2 是本项目 N-mm-tonne-s 单位制中的重力加速度；1 tonne 在该加速度下重 9806 N。
G_MM_S2 = 9806.0
# TARGET_CONCENTRATED_MASS_TONNE 是权威 MCT 二期 CONLOAD 全部转为 MASS21 后的总质量。
TARGET_CONCENTRATED_MASS_TONNE = 963.811380787273
# TARGET_FULL_MODEL_MASS_TONNE 是承重/门架/下拉索分布质量与本次集中质量之和。
TARGET_FULL_MODEL_MASS_TONNE = 4108.46690758
# MASS_TOLERANCE_TONNE 是用户要求的严格总质量误差限值。
MASS_TOLERANCE_TONNE = 1.0e-9
# COMBINATION_TOLERANCE_KN 用于匹配 MCT 中保留到四位小数的组合重量。
COMBINATION_TOLERANCE_KN = 1.0e-6
# MASS21_TYPE_ID 与有限模型的 BEAM188 类型 70 分离，避免覆盖现有类型定义。
MASS21_TYPE_ID = 71
# MASS21_ELEMENT_START 紧接有限拓扑最大单元号约 2,017,679；既避免编号冲突，也避免
# 从 3,000,001 起号造成 MAPDL 为中间空号段扩展稀疏实体表。
MASS21_ELEMENT_START = 2_100_001
# MASS21_REAL_START 从 1000 连续编号；基础绳索实常数只占用低位小编号，而旧动态质量的
# 200000 号段在本流程中不再读取。连续且最高约 34002 的编号可避免巨大稀疏实常数表。
MASS21_REAL_START = 1_000


# COMPONENT_UNIT_WEIGHT_KN 保存每个权威分项的单件重量；键名同时用于所有输出台账。
COMPONENT_UNIT_WEIGHT_KN: dict[str, float] = {
    "large_crossbeam": 1.32,
    "gate_bottom_beam": 3.18,
    "pws_roller": 1.21,
    "cross_passage_half": 49.69,
    "main_cable_restrainer": 14.72,
    "main_tower_frame": 67.9833,
    "aux_tower_frame": 59.6937,
    "anchorage_frame": 62.7153,
    "ordinary_gate": 8.927,
    "guide_roller": 9.196,
    "cross_passage_tri_gate": 12.36,
}


# EXPECTED_QUANTITY_TWO_CATWALKS 是 items.csv 中“每幅数量”的两倍；用于反向校验组合拆分。
EXPECTED_QUANTITY_TWO_CATWALKS: dict[str, int] = {
    "large_crossbeam": 1_098,
    "gate_bottom_beam": 142,
    "pws_roller": 904,
    "cross_passage_half": 42,
    "main_cable_restrainer": 42,
    "main_tower_frame": 8,
    "aux_tower_frame": 4,
    "anchorage_frame": 4,
    "ordinary_gate": 100,
    "guide_roller": 142,
    "cross_passage_tri_gate": 42,
}


# BOTTOM_COMBINATIONS 把表 1-2 的 MCT 组合重量唯一分解为物理分项及数量。
# 例如 62.1137 = 59.6937 + 2×1.21，表示辅助塔架与两套 PWS 滚筒共节点。
BOTTOM_COMBINATIONS: dict[float, dict[str, int]] = {
    1.21: {"pws_roller": 1},
    1.32: {"large_crossbeam": 1},
    2.53: {"pws_roller": 1, "large_crossbeam": 1},
    3.18: {"gate_bottom_beam": 1},
    4.50: {"gate_bottom_beam": 1, "large_crossbeam": 1},
    62.1137: {"aux_tower_frame": 1, "pws_roller": 2},
    62.2237: {"aux_tower_frame": 1, "pws_roller": 1, "large_crossbeam": 1},
    62.7153: {"anchorage_frame": 1},
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
    67.9833: {"main_tower_frame": 1},
}


# GATE_COMBINATIONS 把表 1-3 的门架索节点组合重量拆分为门架实体与导轮组。
GATE_COMBINATIONS: dict[float, dict[str, int]] = {
    18.123: {"ordinary_gate": 1, "guide_roller": 1},
    21.556: {"cross_passage_tri_gate": 1, "guide_roller": 1},
}


# RELOCATED_COMPONENTS 是必须从原索节点迁移到有限杆系的分项集合。
RELOCATED_COMPONENTS = {
    "gate_bottom_beam",
    "ordinary_gate",
    "cross_passage_tri_gate",
    "guide_roller",
    "cross_passage_half",
}


@dataclass(frozen=True)
class Point3D:
    """表示 MAPDL XLongitudinal 坐标系中的三维点。

    参数：
        x_mm: 顺桥向 X 坐标，单位 mm。
        y_mm: 横桥向 Y 坐标，单位 mm。
        z_mm: 竖向 Z 坐标，单位 mm。
    """

    # x_mm 是顺桥向坐标，用于纵向质量重心和横桥/竖向转动惯量。
    x_mm: float
    # y_mm 是横桥向坐标，空间化横通道质量后该方向惯量变化最显著。
    y_mm: float
    # z_mm 是竖向坐标，门架顶梁质量上移会改变对应转动惯量。
    z_mm: float


@dataclass
class MassPoint:
    """保存一个最终 MASS21 节点的坐标、来源和分项质量。

    参数：
        node_id: 原模型或有限拓扑中的 MAPDL 节点号。
        point: 节点在 XLongitudinal 坐标系中的坐标。
        is_generated: True 表示节点来自 V2.0 有限门架/横通道生成器。
        system: original、gate 或 passage，用于审计分组。
        assembly_name: 原节点写 ORIGINAL，新增节点写门架名或 H01~H21。
        role: 有限拓扑节点角色；原节点写 authoritative_conload_node。
        component_masses: 各权威物理分项在该节点上的质量，单位 tonne。
    """

    # node_id 同时是输出 MASS21 单元连接的唯一节点号。
    node_id: int
    # point 用于计算重心、惯量并写入逐节点质量台账。
    point: Point3D
    # is_generated 区分保留在原索节点的质量和迁移后的实体质量。
    is_generated: bool
    # system 用于汇总 original/gate/passage 三类空间分布。
    system: str
    # assembly_name 记录质量所对应的具体门架或横通道品号。
    assembly_name: str
    # role 记录有限杆系中的物理位置或原节点角色。
    role: str
    # component_masses 允许多个分项在同一个有限节点叠加，同时保留可追溯性。
    component_masses: dict[str, float] = field(default_factory=dict)

    @property
    def total_mass_tonne(self) -> float:
        """返回该节点所有分项质量之和，单位 tonne。"""

        # 使用 math.fsum 降低大量很小体积分配份额相加时的舍入误差。
        return math.fsum(self.component_masses.values())


class MassLedger:
    """按节点累加分项质量，并保证同一节点的坐标与元数据一致。"""

    def __init__(self) -> None:
        """创建空的节点质量账本。

        参数：无。
        返回：无；新对象的 ``points`` 字典为空。
        """

        # points 以 MAPDL 节点号为键，防止同一节点因多个构件相交而生成多个 MASS21。
        self.points: dict[int, MassPoint] = {}

    def add_mass(
        self,
        node_id: int,
        point: Point3D,
        component_id: str,
        mass_tonne: float,
        *,
        is_generated: bool,
        system: str,
        assembly_name: str,
        role: str,
    ) -> None:
        """向指定节点增加一个权威物理分项质量。

        参数：
            node_id: MAPDL 节点号。
            point: MAPDL XLongitudinal 三维坐标。
            component_id: items.csv 中稳定的分项标识。
            mass_tonne: 本次增加的质量，单位 tonne；只允许非负有限数。
            is_generated: 是否为 V2.0 新建节点。
            system: original、gate 或 passage。
            assembly_name: ORIGINAL、CW*_GATE_* 或 H**。
            role: 质量所在节点的物理角色。
        返回：无；质量原位累加到 ``points``。
        """

        # 负质量会导致静力重量与模态质量同时失真，因此在最早入口直接拒绝。
        if not math.isfinite(mass_tonne) or mass_tonne < -1.0e-15:
            raise ValueError(f"节点 {node_id} 的 {component_id} 质量非法：{mass_tonne}")
        # 数值闭合修正可能产生 1e-16 量级负零；该量低于物理和输出精度，安全归零。
        if abs(mass_tonne) <= 1.0e-15:
            return
        # 第一次遇到节点时创建完整元数据；后续只累加分项质量。
        if node_id not in self.points:
            self.points[node_id] = MassPoint(
                node_id=node_id,
                point=point,
                is_generated=is_generated,
                system=system,
                assembly_name=assembly_name,
                role=role,
            )
        else:
            # 同一节点不能同时被解释为原节点和新增节点，否则说明 ID 号段冲突。
            existing = self.points[node_id]
            if existing.is_generated != is_generated:
                raise ValueError(f"节点 {node_id} 的 original/generated 属性冲突")
            # 坐标差超过纳米量级说明输入表版本不一致，不应静默合并。
            coordinate_error = max(
                abs(existing.point.x_mm - point.x_mm),
                abs(existing.point.y_mm - point.y_mm),
                abs(existing.point.z_mm - point.z_mm),
            )
            if coordinate_error > 1.0e-6:
                raise ValueError(f"节点 {node_id} 出现不一致坐标，最大差 {coordinate_error} mm")
        # setdefault 保证分项第一次出现时从零开始，随后可由多根相邻梁端共同贡献。
        current_mass = self.points[node_id].component_masses.get(component_id, 0.0)
        self.points[node_id].component_masses[component_id] = current_mass + mass_tonne

    def total_mass_tonne(self) -> float:
        """返回账本中全部节点质量总和，单位 tonne。"""

        # 对所有节点总质量使用 fsum，保证总质量审计不受节点遍历顺序影响。
        return math.fsum(point.total_mass_tonne for point in self.points.values())

    def component_totals(self) -> dict[str, float]:
        """返回按 component_id 汇总的总质量，单位 tonne。"""

        # contributions 先收集每个分项的所有节点份额，再分别使用 fsum 精确求和。
        contributions: dict[str, list[float]] = defaultdict(list)
        # 每个节点可能同时承载门架实体与导轮组，因此必须遍历全部分项而非只取主标签。
        for point in self.points.values():
            for component_id, mass_tonne in point.component_masses.items():
                contributions[component_id].append(mass_tonne)
        # 对键排序使 JSON、CSV 和审计差异具有稳定顺序。
        return {
            component_id: math.fsum(contributions[component_id])
            for component_id in sorted(contributions)
        }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """读取 UTF-8-SIG CSV 并返回行字典列表。

    参数：
        path: 待读取 CSV 的绝对或相对路径。
    返回：
        保留原列名和文本值的字典列表。
    """

    # 缺失输入必须在生成 APDL 前停止，防止使用旧版本或空列表继续运行。
    if not path.is_file():
        raise FileNotFoundError(f"缺少输入 CSV：{path}")
    # utf-8-sig 同时兼容带 BOM 和不带 BOM 的项目 CSV。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        # DictReader 用表头绑定字段，避免列顺序变化造成错读。
        return list(csv.DictReader(stream))


def sha256_file(path: Path) -> str:
    """计算文件 SHA256 十六进制摘要。

    参数：
        path: 需要绑定版本的输入文件路径。
    返回：
        64 字符小写 SHA256 字符串。
    """

    # digest 是增量哈希对象，可避免一次性把数 MB CSV 全部读入额外内存。
    digest = hashlib.sha256()
    # 二进制读取保证摘要不受换行转换或编码解码影响。
    with path.open("rb") as stream:
        # 按 1 MiB 分块，在速度与内存占用之间取得稳定平衡。
        while True:
            block = stream.read(1024 * 1024)
            # 空块表示到达文件末尾，循环在此唯一出口结束。
            if not block:
                break
            digest.update(block)
    # hexdigest 便于直接写入 JSON/Markdown 并人工核对。
    return digest.hexdigest()


def kn_to_tonne(weight_kn: float, gravity_mm_s2: float) -> float:
    """把重量 kN 转换为 N-mm-tonne-s 单位制中的质量 tonne。

    参数：
        weight_kn: 非负重量，单位 kN。
        gravity_mm_s2: 重力加速度，单位 mm/s²。
    返回：
        等效质量，单位 tonne。
    """

    # 1 kN = 1000 N；1 tonne 在 mm/s² 加速度下产生 ``m*g`` N。
    return weight_kn * 1000.0 / gravity_mm_s2


def match_combination(
    subsystem: str,
    combined_weight_kn: float,
) -> dict[str, int]:
    """按子系统与组合重量返回唯一物理分项数量。

    参数：
        subsystem: authoritative mapping 中的 bottom 或 gate。
        combined_weight_kn: 单幅单个 MCT 节点的组合重量绝对值，单位 kN。
    返回：
        ``component_id -> quantity`` 的新字典。
    """

    # bottom 与 gate 使用不同权威表；其他值说明输入 schema 已改变。
    if subsystem == "bottom":
        patterns = BOTTOM_COMBINATIONS
    elif subsystem == "gate":
        patterns = GATE_COMBINATIONS
    else:
        raise ValueError(f"未知集中恒载子系统：{subsystem}")
    # candidates 保存落在严格容差内的模式，最终必须且只能有一个。
    candidates: list[tuple[float, dict[str, int]]] = []
    # 遍历模式数量很少，显式容差匹配比浮点字典直接索引更可靠。
    for pattern_weight_kn, components in patterns.items():
        error_kn = abs(pattern_weight_kn - combined_weight_kn)
        if error_kn <= COMBINATION_TOLERANCE_KN:
            candidates.append((error_kn, components))
    # 零匹配表示遇到未审查组合，多匹配表示容差或模式定义不再唯一；两者都必须停止。
    if len(candidates) != 1:
        raise ValueError(
            f"{subsystem} 组合 {combined_weight_kn:.9f} kN 的匹配数为 {len(candidates)}"
        )
    # 返回副本，防止调用者意外修改全局权威模式常量。
    return dict(candidates[0][1])


def load_original_apdl_coordinates(nodes_csv: Path) -> dict[int, Point3D]:
    """读取原绳索节点，并转换为 XLongitudinal MAPDL 坐标。

    参数：
        nodes_csv: V1.0 ``nodes.csv``，其坐标仍是 CAD 的 X 横桥、Y 顺桥、Z 竖向。
    返回：
        ``node_id -> Point3D``；变换关系为 MAPDL=(CAD_Y, -CAD_X, CAD_Z)。
    """

    # coordinates 保存所有绳索节点；后续只访问权威 mapping 实际使用的节点。
    coordinates: dict[int, Point3D] = {}
    # 逐行转换可直接发现节点号重复，而不是让后写行静默覆盖前写行。
    for row in read_csv_rows(nodes_csv):
        node_id = int(row["node_id"])
        if node_id in coordinates:
            raise ValueError(f"原节点表中节点号 {node_id} 重复")
        cad_x_mm = float(row["x_mm"])
        cad_y_mm = float(row["y_mm"])
        cad_z_mm = float(row["z_mm"])
        coordinates[node_id] = Point3D(cad_y_mm, -cad_x_mm, cad_z_mm)
    return coordinates


def build_original_component_ledger(
    mapping_rows: Sequence[dict[str, str]],
    original_coordinates: Mapping[int, Point3D],
    gravity_mm_s2: float,
) -> tuple[MassLedger, dict[str, int], dict[tuple[str, str, str], dict[str, int]]]:
    """把原组合 MASS21 拆成逐节点物理分项账本。

    参数：
        mapping_rows: authoritative_mct_deadload_v1_conload_mapping.csv 全部行。
        original_coordinates: 原节点号到 XLongitudinal 坐标的映射。
        gravity_mm_s2: 质量换算采用的重力加速度。
    返回：
        三元组：原始分项账本、两幅合计分项数量、按 MCT 站位记录的组合分解。
    """

    # ledger 保存“迁移前”全部集中质量，可直接用于前置重心和惯量计算。
    ledger = MassLedger()
    # station_patterns 以子系统/幅号/MCT节点唯一标识物理站位，避免 16 或 6 根索重复计数。
    station_patterns: dict[tuple[str, str, str], dict[str, int]] = {}
    # row_count_by_station 校验每个 bottom 站位恰有16行、gate站位恰有6行。
    row_count_by_station: dict[tuple[str, str, str], int] = defaultdict(int)
    # 逐行把组合重量按物理索数等分到分项质量，保持与原 MASS21 完全相同的总节点质量。
    for row in mapping_rows:
        subsystem = row["subsystem"].strip()
        catwalk = row["catwalk"].strip()
        mct_node = row["mct_node"].strip()
        node_id = int(row["ansys_node"])
        if node_id not in original_coordinates:
            raise KeyError(f"权威映射节点 {node_id} 不在原 nodes.csv 中")
        combined_weight_kn = abs(float(row["mct_total_fz_kn_per_catwalk"]))
        pattern = match_combination(subsystem, combined_weight_kn)
        station_key = (subsystem, catwalk, mct_node)
        if station_key in station_patterns and station_patterns[station_key] != pattern:
            raise ValueError(f"MCT 站位 {station_key} 在不同索行出现不一致组合")
        station_patterns[station_key] = pattern
        row_count_by_station[station_key] += 1
        # 每幅底索有16根、门架索有6根；MCT 单幅组合重量应在这些物理索间等分。
        distribution_count = 16 if subsystem == "bottom" else 6
        # 对组合内每个物理分项分别建账，后续才能只迁移门架/横通道而保留其他分项。
        for component_id, quantity in pattern.items():
            component_weight_at_node_kn = (
                COMPONENT_UNIT_WEIGHT_KN[component_id] * quantity / distribution_count
            )
            component_mass_at_node_tonne = kn_to_tonne(
                component_weight_at_node_kn,
                gravity_mm_s2,
            )
            ledger.add_mass(
                node_id,
                original_coordinates[node_id],
                component_id,
                component_mass_at_node_tonne,
                is_generated=False,
                system="original",
                assembly_name="ORIGINAL",
                role="authoritative_conload_node",
            )
        # 用权威 applied_fz_n 反校验拆分后的单节点质量，避免组合表遗漏一个分项。
        expected_node_mass_tonne = abs(float(row["applied_fz_n_per_physical_rope"])) / gravity_mm_s2
        actual_node_mass_tonne = math.fsum(
            kn_to_tonne(
                COMPONENT_UNIT_WEIGHT_KN[component_id] * quantity / distribution_count,
                gravity_mm_s2,
            )
            for component_id, quantity in pattern.items()
        )
        if abs(actual_node_mass_tonne - expected_node_mass_tonne) > 1.0e-12:
            raise ValueError(
                f"节点 {node_id} 组合拆分质量与 applied_fz 不闭合："
                f"{actual_node_mass_tonne} vs {expected_node_mass_tonne} tonne"
            )
    # 每个站位的物理索行数必须严格符合模型复制数，防止 mapping 缺行时仍保持局部质量正确假象。
    for station_key, row_count in row_count_by_station.items():
        expected_row_count = 16 if station_key[0] == "bottom" else 6
        if row_count != expected_row_count:
            raise ValueError(f"MCT 站位 {station_key} 有 {row_count} 行，预期 {expected_row_count}")
    # 分项数量只按站位计一次；quantity 可能为2，例如辅助塔站的两套 PWS 滚筒。
    component_quantities: dict[str, int] = defaultdict(int)
    for pattern in station_patterns.values():
        for component_id, quantity in pattern.items():
            component_quantities[component_id] += quantity
    # 与 items.csv 权威数量逐项比较，确保组合分解不是仅在总重量上偶然闭合。
    if dict(sorted(component_quantities.items())) != dict(sorted(EXPECTED_QUANTITY_TWO_CATWALKS.items())):
        raise ValueError(
            "组合拆分后的分项数量不等于 items.csv 两幅合计："
            f"actual={dict(component_quantities)}, expected={EXPECTED_QUANTITY_TWO_CATWALKS}"
        )
    return ledger, dict(component_quantities), station_patterns


def load_generated_topology(
    generated_nodes_csv: Path,
    generated_elements_csv: Path,
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    """读取有限模型生成节点与单元，并转换数值字段。

    参数：
        generated_nodes_csv: builder/generated/generated_nodes.csv。
        generated_elements_csv: builder/generated/generated_elements.csv。
    返回：
        节点号索引和单元字典列表；方向节点保留在索引中但不会被分配质量。
    """

    # nodes 既保存坐标也保存 assembly_name/role，供导轮连接点和输出台账使用。
    nodes: dict[int, dict[str, object]] = {}
    # 对所有生成节点逐行转为强类型字段，后续不再重复解析文本。
    for row in read_csv_rows(generated_nodes_csv):
        node_id = int(row["apdl_node_id"])
        if node_id in nodes:
            raise ValueError(f"generated_nodes.csv 节点号 {node_id} 重复")
        nodes[node_id] = {
            "point": Point3D(float(row["x_mm"]), float(row["y_mm"]), float(row["z_mm"])),
            "system": row["system"].strip(),
            "assembly_name": row["assembly_name"].strip(),
            "role": row["role"].strip(),
            "is_orientation": bool(int(row["is_orientation"])),
        }
    # elements 只保留空间质量分配所需的拓扑、分组和体积字段。
    elements: list[dict[str, object]] = []
    # 每根梁的体积由 builder 按解析截面面积和实际分段长度给出，避免本脚本重复几何计算。
    for row in read_csv_rows(generated_elements_csv):
        n1 = int(row["n1"])
        n2 = int(row["n2"])
        if n1 not in nodes or n2 not in nodes:
            raise KeyError(f"生成单元 {row['apdl_elem_id']} 引用不存在节点 {n1}/{n2}")
        if bool(nodes[n1]["is_orientation"]) or bool(nodes[n2]["is_orientation"]):
            raise ValueError(f"生成单元 {row['apdl_elem_id']} 的物理端点误用方向节点")
        volume_mm3 = float(row["volume_mm3"])
        if not math.isfinite(volume_mm3) or volume_mm3 <= 0.0:
            raise ValueError(f"生成单元 {row['apdl_elem_id']} 的体积非法：{volume_mm3}")
        elements.append(
            {
                "element_id": int(row["apdl_elem_id"]),
                "n1": n1,
                "n2": n2,
                "system": row["system"].strip(),
                "assembly_name": row["assembly_name"].strip(),
                "member": row["member"].strip(),
                "section_key": row["section_key"].strip(),
                "volume_mm3": volume_mm3,
            }
        )
    return nodes, elements


def select_elements(
    elements: Sequence[dict[str, object]],
    *,
    system: str,
    assembly_name: str,
    allowed_members: set[str] | None,
) -> list[dict[str, object]]:
    """按系统、品名和可选构件集合筛选物理梁单元。

    参数：
        elements: 已数值化的生成单元列表。
        system: gate 或 passage。
        assembly_name: CW*_GATE_* 或 H**。
        allowed_members: 允许的 member 集合；None 表示该品全部构件。
    返回：
        满足全部条件的单元列表。
    """

    # selected 仅保存当前实体的梁，后续体积归一化绝不能跨品分配质量。
    selected: list[dict[str, object]] = []
    # 对每根梁显式检查三个条件，便于未来 schema 增加其他系统时仍保持隔离。
    for element in elements:
        if element["system"] != system:
            continue
        if element["assembly_name"] != assembly_name:
            continue
        if allowed_members is not None and str(element["member"]) not in allowed_members:
            continue
        selected.append(element)
    # 空选择表示门架/横通道生成不完整，不能退化为把质量放在任意一个节点。
    if not selected:
        raise ValueError(
            f"未找到 system={system}, assembly={assembly_name}, members={allowed_members} 的单元"
        )
    return selected


def lump_mass_by_element_volume(
    elements: Sequence[dict[str, object]],
    target_mass_tonne: float,
) -> dict[int, float]:
    """按单元体积等效密度分配，并把每根梁质量各半集中到两个端节点。

    参数：
        elements: 同一物理分项允许参与分配的梁单元。
        target_mass_tonne: 该分项必须严格保持的目标总质量。
    返回：
        ``node_id -> lumped_mass_tonne``，其总和经末节点闭合修正后等于目标值。
    """

    # total_volume_mm3 是等效密度归一化分母；各截面实际面积差异已包含在 volume_mm3 中。
    total_volume_mm3 = math.fsum(float(element["volume_mm3"]) for element in elements)
    if not math.isfinite(total_volume_mm3) or total_volume_mm3 <= 0.0:
        raise ValueError(f"体积分配的总实体积非法：{total_volume_mm3}")
    # nodal_masses 汇总相邻梁端的多个半质量份额。
    nodal_masses: dict[int, float] = defaultdict(float)
    # 每根梁质量 = 目标质量×本梁体积/总体积；两端各取一半是标准集中质量近似。
    for element in elements:
        element_mass_tonne = target_mass_tonne * float(element["volume_mm3"]) / total_volume_mm3
        half_mass_tonne = 0.5 * element_mass_tonne
        nodal_masses[int(element["n1"])] += half_mass_tonne
        nodal_masses[int(element["n2"])] += half_mass_tonne
    # 浮点除法可能留下约 1e-15 tonne 的闭合差；将其加到最大节点质量，避免产生相对异常小份额。
    actual_mass_tonne = math.fsum(nodal_masses.values())
    closure_tonne = target_mass_tonne - actual_mass_tonne
    anchor_node = max(nodal_masses, key=nodal_masses.get)
    nodal_masses[anchor_node] += closure_tonne
    # 修正后仍不闭合说明出现 NaN 或逻辑错误，而不是正常舍入。
    if abs(math.fsum(nodal_masses.values()) - target_mass_tonne) > 1.0e-12:
        raise ArithmeticError("单元体积节点集中化未能闭合目标质量")
    return dict(nodal_masses)


def equal_mass_distribution(node_ids: Sequence[int], target_mass_tonne: float) -> dict[int, float]:
    """把目标质量等分到一组物理连接节点，并在末节点吸收浮点闭合差。

    参数：
        node_ids: 不得为空且不得重复的目标节点号序列。
        target_mass_tonne: 需要严格保持的总质量。
    返回：
        节点号到等分质量的映射。
    """

    # 重复节点会让“6个连接点”等物理规则失真，因此显式拒绝。
    if not node_ids or len(set(node_ids)) != len(node_ids):
        raise ValueError(f"等分节点集合为空或含重复：{node_ids}")
    # base_mass_tonne 是除末节点外所有节点的公共份额。
    base_mass_tonne = target_mass_tonne / len(node_ids)
    distribution = {node_id: base_mass_tonne for node_id in node_ids}
    # 最后一个稳定排序节点吸收机器舍入差，保证总质量严格等于目标。
    anchor_node = sorted(node_ids)[-1]
    distribution[anchor_node] += target_mass_tonne - math.fsum(distribution.values())
    return distribution


def add_generated_distribution(
    ledger: MassLedger,
    generated_nodes: Mapping[int, dict[str, object]],
    component_id: str,
    distribution: Mapping[int, float],
) -> None:
    """把已计算的新增节点分布写入最终质量账本。

    参数：
        ledger: 最终空间化质量账本。
        generated_nodes: builder 生成节点索引。
        component_id: 当前物理分项标识。
        distribution: ``node_id -> mass_tonne`` 分布。
    返回：无。
    """

    # 每个分配节点必须是有限生成器的物理节点，方向节点不能承受实体质量。
    for node_id, mass_tonne in distribution.items():
        if node_id not in generated_nodes:
            raise KeyError(f"质量分配引用不存在的生成节点 {node_id}")
        metadata = generated_nodes[node_id]
        if bool(metadata["is_orientation"]):
            raise ValueError(f"分项 {component_id} 误分配到方向节点 {node_id}")
        ledger.add_mass(
            node_id,
            metadata["point"],  # type: ignore[arg-type]
            component_id,
            mass_tonne,
            is_generated=True,
            system=str(metadata["system"]),
            assembly_name=str(metadata["assembly_name"]),
            role=str(metadata["role"]),
        )


def build_spatialized_ledger(
    original_ledger: MassLedger,
    generated_nodes: Mapping[int, dict[str, object]],
    generated_elements: Sequence[dict[str, object]],
    dedicated_station_rows: Sequence[dict[str, str]],
    gravity_mm_s2: float,
) -> MassLedger:
    """保留非迁移分项，并在有限杆系节点上重建门架和横通道质量。

    参数：
        original_ledger: 已逐项拆分的迁移前质量账本。
        generated_nodes: 有限模型生成节点索引。
        generated_elements: 有限模型生成梁单元列表。
        dedicated_station_rows: 21 品横通道与两幅门架的权威映射。
        gravity_mm_s2: kN 到 tonne 的换算加速度。
    返回：
        迁移后的完整 MASS21 账本。
    """

    # final_ledger 最终同时包含原绳索节点的保留分项和新增实体节点的迁移分项。
    final_ledger = MassLedger()
    # 首先逐节点复制所有不需要空间迁移的分项；迁移集合暂不写入，防止重复质量。
    for original_point in original_ledger.points.values():
        for component_id, mass_tonne in original_point.component_masses.items():
            if component_id in RELOCATED_COMPONENTS:
                continue
            final_ledger.add_mass(
                original_point.node_id,
                original_point.point,
                component_id,
                mass_tonne,
                is_generated=False,
                system="original",
                assembly_name="ORIGINAL",
                role="retained_authoritative_conload_component",
            )
    # dedicated_gate_names 含 21 品×2 幅三角门架，用它区分12.36 kN与8.927 kN门架上部质量。
    dedicated_gate_names: set[str] = set()
    # passage_names 保存 H01~H21，并验证没有重复或遗漏。
    passage_names: list[str] = []
    for row in dedicated_station_rows:
        passage_names.append(row["name"].strip())
        dedicated_gate_names.add(row["cw1_gate_name"].strip())
        dedicated_gate_names.add(row["cw2_gate_name"].strip())
    if passage_names != [f"H{index:02d}" for index in range(1, 22)]:
        raise ValueError("resolved_dedicated_stations.csv 必须严格按 H01~H21 排列")
    if len(dedicated_gate_names) != 42:
        raise ValueError(f"三角门架名称数为 {len(dedicated_gate_names)}，预期42")
    # all_gate_names 来自实际生成单元而不是假定，确保质量与当前 builder 产物同版本。
    all_gate_names = sorted(
        {
            str(element["assembly_name"])
            for element in generated_elements
            if element["system"] == "gate"
        }
    )
    if len(all_gate_names) != 142:
        raise ValueError(f"生成有限门架数为 {len(all_gate_names)}，预期142")
    # 每一幅每一品门架分别迁移下横梁、上部框架和导轮组三类质量。
    for gate_name in all_gate_names:
        # 下横梁只允许 bottom_beam 单元参与3.18 kN体积分配。
        bottom_elements = select_elements(
            generated_elements,
            system="gate",
            assembly_name=gate_name,
            allowed_members={"bottom_beam"},
        )
        bottom_mass_tonne = kn_to_tonne(COMPONENT_UNIT_WEIGHT_KN["gate_bottom_beam"], gravity_mm_s2)
        add_generated_distribution(
            final_ledger,
            generated_nodes,
            "gate_bottom_beam",
            lump_mass_by_element_volume(bottom_elements, bottom_mass_tonne),
        )
        # 顶梁和两根立柱使用同一 RHS160 截面，按真实梁体积表示普通/三角门架实体质量。
        upper_elements = select_elements(
            generated_elements,
            system="gate",
            assembly_name=gate_name,
            allowed_members={"top_beam", "left_post", "right_post"},
        )
        upper_component_id = (
            "cross_passage_tri_gate" if gate_name in dedicated_gate_names else "ordinary_gate"
        )
        upper_mass_tonne = kn_to_tonne(
            COMPONENT_UNIT_WEIGHT_KN[upper_component_id],
            gravity_mm_s2,
        )
        add_generated_distribution(
            final_ledger,
            generated_nodes,
            upper_component_id,
            lump_mass_by_element_volume(upper_elements, upper_mass_tonne),
        )
        # 导轮组与6根门架索相连；角色前缀由有限 builder 稳定生成，因此按这6点等分。
        guide_nodes = sorted(
            node_id
            for node_id, metadata in generated_nodes.items()
            if metadata["system"] == "gate"
            and metadata["assembly_name"] == gate_name
            and str(metadata["role"]).startswith("gantry_rope_master_")
            and not bool(metadata["is_orientation"])
        )
        if len(guide_nodes) != 6:
            raise ValueError(f"{gate_name} 顶梁导轮连接点数为 {len(guide_nodes)}，预期6")
        guide_mass_tonne = kn_to_tonne(COMPONENT_UNIT_WEIGHT_KN["guide_roller"], gravity_mm_s2)
        add_generated_distribution(
            final_ledger,
            generated_nodes,
            "guide_roller",
            equal_mass_distribution(guide_nodes, guide_mass_tonne),
        )
    # 每品横通道把两幅各49.69 kN合为一个99.38 kN完整结构，按所有截面杆件体积分配。
    for passage_name in passage_names:
        passage_elements = select_elements(
            generated_elements,
            system="passage",
            assembly_name=passage_name,
            allowed_members=None,
        )
        full_passage_mass_tonne = kn_to_tonne(
            2.0 * COMPONENT_UNIT_WEIGHT_KN["cross_passage_half"],
            gravity_mm_s2,
        )
        add_generated_distribution(
            final_ledger,
            generated_nodes,
            "cross_passage_half",
            lump_mass_by_element_volume(passage_elements, full_passage_mass_tonne),
        )
    return final_ledger


def calculate_mass_properties(ledger: MassLedger) -> dict[str, object]:
    """计算集中质量总量、重心及关于原点/重心的惯量张量分量。

    参数：
        ledger: 迁移前或迁移后的节点质量账本。
    返回：
        可直接 JSON 序列化的质量特性字典；惯量单位 tonne·mm²。
    """

    # points 过滤理论上不应存在的零质量节点，避免除零和无意义输出。
    points = [point for point in ledger.points.values() if point.total_mass_tonne > 0.0]
    total_mass_tonne = math.fsum(point.total_mass_tonne for point in points)
    if total_mass_tonne <= 0.0:
        raise ValueError("质量账本为空，不能计算重心和惯量")
    # 一阶矩除以总质量得到 X/Y/Z 三向重心。
    cg_x_mm = math.fsum(point.total_mass_tonne * point.point.x_mm for point in points) / total_mass_tonne
    cg_y_mm = math.fsum(point.total_mass_tonne * point.point.y_mm for point in points) / total_mass_tonne
    cg_z_mm = math.fsum(point.total_mass_tonne * point.point.z_mm for point in points) / total_mass_tonne

    def inertia_about(reference: Point3D) -> dict[str, float]:
        """计算关于给定参考点的笛卡尔惯量张量六个独立分量。

        参数：
            reference: 惯量参考点。
        返回：
            Ixx/Iyy/Izz 与张量惯用负积惯量 Ixy/Ixz/Iyz。
        """

        # xx、yy、zz 和积惯量分别收集后用 fsum 汇总，减少正负项抵消误差。
        ixx_terms: list[float] = []
        iyy_terms: list[float] = []
        izz_terms: list[float] = []
        ixy_terms: list[float] = []
        ixz_terms: list[float] = []
        iyz_terms: list[float] = []
        # 点质量自身转动惯量忽略；这里只计算其相对参考点的平行轴贡献。
        for point in points:
            mass_tonne = point.total_mass_tonne
            dx_mm = point.point.x_mm - reference.x_mm
            dy_mm = point.point.y_mm - reference.y_mm
            dz_mm = point.point.z_mm - reference.z_mm
            ixx_terms.append(mass_tonne * (dy_mm * dy_mm + dz_mm * dz_mm))
            iyy_terms.append(mass_tonne * (dx_mm * dx_mm + dz_mm * dz_mm))
            izz_terms.append(mass_tonne * (dx_mm * dx_mm + dy_mm * dy_mm))
            # 工程惯量张量的非对角项采用负积惯量定义。
            ixy_terms.append(-mass_tonne * dx_mm * dy_mm)
            ixz_terms.append(-mass_tonne * dx_mm * dz_mm)
            iyz_terms.append(-mass_tonne * dy_mm * dz_mm)
        return {
            "Ixx_tonne_mm2": math.fsum(ixx_terms),
            "Iyy_tonne_mm2": math.fsum(iyy_terms),
            "Izz_tonne_mm2": math.fsum(izz_terms),
            "Ixy_tonne_mm2": math.fsum(ixy_terms),
            "Ixz_tonne_mm2": math.fsum(ixz_terms),
            "Iyz_tonne_mm2": math.fsum(iyz_terms),
        }

    # 原点惯量便于与全局模型核对，重心惯量更直接反映空间化对动力转动惯量的影响。
    origin = Point3D(0.0, 0.0, 0.0)
    centroid = Point3D(cg_x_mm, cg_y_mm, cg_z_mm)
    return {
        "node_count": len(points),
        "mass_tonne": total_mass_tonne,
        "center_of_mass_mm": {"x": cg_x_mm, "y": cg_y_mm, "z": cg_z_mm},
        "inertia_about_origin": inertia_about(origin),
        "inertia_about_center_of_mass": inertia_about(centroid),
    }


def difference_mapping(after: Mapping[str, float], before: Mapping[str, float]) -> dict[str, float]:
    """返回两个同字段数值字典的 after-before 差值。

    参数：
        after: 空间化后数值字典。
        before: 空间化前数值字典。
    返回：
        按 after 键顺序生成的差值字典。
    """

    # 字段不一致表示调用者比较了不同物理量，应立即停止而非只比较交集。
    if set(after) != set(before):
        raise ValueError("前后数值字典字段不一致")
    return {key: float(after[key]) - float(before[key]) for key in after}


def write_node_mass_csv(path: Path, ledger: MassLedger) -> None:
    """写出最终逐节点聚合质量 CSV。

    参数：
        path: 输出 CSV 路径。
        ledger: 最终空间化质量账本。
    返回：无。
    """

    # 固定列序便于 MAPDL 节点号、坐标、总质量和分项来源人工复核。
    fieldnames = [
        "apdl_node_id",
        "x_mm",
        "y_mm",
        "z_mm",
        "mass_tonne",
        "is_generated_node",
        "system",
        "assembly_name",
        "role",
        "component_ids",
        "component_masses_tonne",
    ]
    # 父目录在脚本入口统一创建，这里仍显式保证可单独调用。
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        # 按节点号排序使 APDL、CSV 和审计中的节点顺序完全一致。
        for node_id in sorted(ledger.points):
            point = ledger.points[node_id]
            component_ids = sorted(point.component_masses)
            writer.writerow(
                {
                    "apdl_node_id": node_id,
                    "x_mm": f"{point.point.x_mm:.12f}",
                    "y_mm": f"{point.point.y_mm:.12f}",
                    "z_mm": f"{point.point.z_mm:.12f}",
                    "mass_tonne": f"{point.total_mass_tonne:.17e}",
                    "is_generated_node": int(point.is_generated),
                    "system": point.system,
                    "assembly_name": point.assembly_name,
                    "role": point.role,
                    "component_ids": ";".join(component_ids),
                    "component_masses_tonne": ";".join(
                        f"{component_id}={point.component_masses[component_id]:.17e}"
                        for component_id in component_ids
                    ),
                }
            )


def write_component_allocation_csv(path: Path, ledger: MassLedger) -> None:
    """写出逐节点逐物理分项的长表 CSV，支持按 component_id 独立求和。

    参数：
        path: 输出长表路径。
        ledger: 最终空间化质量账本。
    返回：无。
    """

    # 长表比聚合表更适合检查同一节点上叠加的门架实体和导轮组质量。
    fieldnames = [
        "apdl_node_id",
        "x_mm",
        "y_mm",
        "z_mm",
        "component_id",
        "mass_tonne",
        "weight_kn",
        "destination_rule",
        "system",
        "assembly_name",
        "role",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        # 每个节点的分项也排序，保证输出可重复且易于版本比较。
        for node_id in sorted(ledger.points):
            point = ledger.points[node_id]
            for component_id in sorted(point.component_masses):
                mass_tonne = point.component_masses[component_id]
                # 根据分项与节点类别给出明确空间化规则，避免只凭坐标猜测来源。
                if not point.is_generated:
                    destination_rule = "retained_at_original_rope_node"
                elif component_id == "gate_bottom_beam":
                    destination_rule = "gate_bottom_beam_volume_lumped_to_ends"
                elif component_id in {"ordinary_gate", "cross_passage_tri_gate"}:
                    destination_rule = "gate_top_and_posts_volume_lumped_to_ends"
                elif component_id == "guide_roller":
                    destination_rule = "equally_distributed_to_six_top_rope_connections"
                elif component_id == "cross_passage_half":
                    destination_rule = "full_passage_all_member_volume_lumped_to_ends"
                else:
                    raise ValueError(f"新增节点出现未定义空间化规则的分项 {component_id}")
                writer.writerow(
                    {
                        "apdl_node_id": node_id,
                        "x_mm": f"{point.point.x_mm:.12f}",
                        "y_mm": f"{point.point.y_mm:.12f}",
                        "z_mm": f"{point.point.z_mm:.12f}",
                        "component_id": component_id,
                        "mass_tonne": f"{mass_tonne:.17e}",
                        "weight_kn": f"{mass_tonne * G_MM_S2 / 1000.0:.17e}",
                        "destination_rule": destination_rule,
                        "system": point.system,
                        "assembly_name": point.assembly_name,
                        "role": point.role,
                    }
                )


def write_apdl_mass_include(path: Path, ledger: MassLedger) -> None:
    """写出删除旧集中质量并建立空间化 MASS21 的 APDL include。

    参数：
        path: ``apply_dynamic_mass21_spatialized_v2.inp`` 输出路径。
        ledger: 最终空间化质量账本。
    返回：无。
    """

    # 只输出正质量节点；零质量原节点不需要占用单元和实常数号。
    mass_points = [
        ledger.points[node_id]
        for node_id in sorted(ledger.points)
        if ledger.points[node_id].total_mass_tonne > 0.0
    ]
    # lines 先在内存中构建，最后一次写入可避免生成中断留下半个可执行 include。
    lines: list[str] = [
        "! ============================================================================",
        "! V2.0 权威二期集中恒载空间化动力质量；由 Python 生成，禁止手工改质量值。",
        "! 单位：N, mm, tonne, s；坐标：X顺桥、Y横桥、Z竖向。",
        "! 门架与横通道质量已从原索节点迁移；其他分项保留在原索节点。",
        "! ============================================================================",
        "/PREP7",
        "! 必须先定义 TYPE=71，随后才能用 ESEL,TYPE 安全选择重复运行留下的质量单元。",
        f"ET,{MASS21_TYPE_ID},MASS21",
        f"KEYOPT,{MASS21_TYPE_ID},3,2",
        "ALLSEL,ALL",
        "! 权威 deadload include 已负责清除旧 TYPE=3 MASS21；本文件不得再选择/删除 TYPE=3。",
        "! 只清除本文件上一次建立的 TYPE=71 MASS21，使重复 include 保持幂等。",
        f"ESEL,S,TYPE,,{MASS21_TYPE_ID}",
        "*GET,V2_OLD_MASS21_COUNT,ELEM,0,COUNT",
        "*IF,V2_OLD_MASS21_COUNT,GT,0,THEN",
        "  EDELE,ALL",
        "*ENDIF",
        "ALLSEL,ALL",
        f"TYPE,{MASS21_TYPE_ID}",
    ]
    # 每个节点使用独立实常数，避免浮点近似分组改变空间化质量闭合。
    for index, point in enumerate(mass_points):
        real_id = MASS21_REAL_START + index
        element_id = MASS21_ELEMENT_START + index
        mass_tonne = point.total_mass_tonne
        lines.extend(
            [
                f"R,{real_id},{mass_tonne:.17E}",
                f"REAL,{real_id}",
                f"EN,{element_id},{point.node_id}",
            ]
        )
    # 删除原 FZ，后续 ACEL 重力通过 MASS21 产生同总量但空间位置正确的静力重量。
    lines.extend(
        [
            "ALLSEL,ALL",
            "NSEL,ALL",
            "FDELE,ALL,FZ",
            "ALLSEL,ALL",
            "FINISH",
            "",
        ]
    )
    # APDL 把 UTF-8 BOM 当成首行命令字符并产生“not a recognized BEGIN command”警告，
    # 因此求解 include 必须写普通 UTF-8；CSV/Markdown 仍可保留 BOM 方便表格软件识别。
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_audit(
    *,
    before_ledger: MassLedger,
    after_ledger: MassLedger,
    component_quantities: Mapping[str, int],
    input_paths: Mapping[str, Path],
) -> dict[str, object]:
    """组装机器可读的前后质量、重心、惯量和分项闭合审计。

    参数：
        before_ledger: 原组合质量逐项拆分后的迁移前账本。
        after_ledger: 空间化后的最终账本。
        component_quantities: 从权威组合反解的两幅分项数量。
        input_paths: 审计所绑定的关键输入文件。
    返回：
        可写入 JSON 的完整审计字典。
    """

    # before_properties/after_properties 是本次空间化直接改变的 CONLOAD 集中质量特性。
    before_properties = calculate_mass_properties(before_ledger)
    after_properties = calculate_mass_properties(after_ledger)
    # 分项前后总量必须逐项守恒，而不只检查963.811 t总和。
    before_components = before_ledger.component_totals()
    after_components = after_ledger.component_totals()
    component_balance: dict[str, dict[str, float | int]] = {}
    for component_id in sorted(before_components):
        component_balance[component_id] = {
            "quantity_two_catwalks": int(component_quantities[component_id]),
            "before_mass_tonne": before_components[component_id],
            "after_mass_tonne": after_components.get(component_id, 0.0),
            "error_tonne": after_components.get(component_id, 0.0) - before_components[component_id],
        }
    # 总质量误差分别针对迁移前、迁移后和完整模型目标计算。
    before_mass_error = float(before_properties["mass_tonne"]) - TARGET_CONCENTRATED_MASS_TONNE
    after_mass_error = float(after_properties["mass_tonne"]) - TARGET_CONCENTRATED_MASS_TONNE
    invariant_distributed_mass_tonne = TARGET_FULL_MODEL_MASS_TONNE - TARGET_CONCENTRATED_MASS_TONNE
    predicted_full_mass_tonne = invariant_distributed_mass_tonne + float(after_properties["mass_tonne"])
    full_mass_error = predicted_full_mass_tonne - TARGET_FULL_MODEL_MASS_TONNE
    # 前后重心差直接显示门架质量上移和横通道质量横向铺开的效果。
    cg_before = before_properties["center_of_mass_mm"]
    cg_after = after_properties["center_of_mass_mm"]
    inertia_before_origin = before_properties["inertia_about_origin"]
    inertia_after_origin = after_properties["inertia_about_origin"]
    inertia_before_cg = before_properties["inertia_about_center_of_mass"]
    inertia_after_cg = after_properties["inertia_about_center_of_mass"]
    # 每个关键输入记录绝对路径、文件大小和 SHA256，保证以后可以重现同一结果。
    input_binding = {
        name: {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for name, path in input_paths.items()
    }
    # component_pass 要求每个物理分项误差也小于总质量容差。
    component_pass = all(
        abs(float(balance["error_tonne"])) < MASS_TOLERANCE_TONNE
        for balance in component_balance.values()
    )
    # mass_closure_status 只评价可由现有权威重量唯一验收的总质量和分项质量守恒。
    mass_closure_status = (
        "PASS"
        if abs(before_mass_error) < MASS_TOLERANCE_TONNE
        and abs(after_mass_error) < MASS_TOLERANCE_TONNE
        and abs(full_mass_error) < MASS_TOLERANCE_TONNE
        and component_pass
        else "FAIL"
    )
    # rotary_inertia_coverage_status 明确标记内禀惯量和表1-1附件空间分布尚无完整源证。
    rotary_inertia_coverage_status = "INCOMPLETE"
    # status 是完整动力质量模型的总状态；质量守恒通过也不能把缺失惯量升级为 PASS。
    status = (
        # 质量闭合失败时完整状态必须为 FAIL，不能被惯量未完成状态掩盖。
        "FAIL"
        if mass_closure_status == "FAIL"
        # 质量闭合通过但惯量源证不完整时返回 INCOMPLETE，阻止把本报告误称为全面通过。
        else "INCOMPLETE"
    )
    return {
        "schema": "dynamic_mass21_spatialization_v2",
        "status": status,
        # mass_closure_status 是生成 APDL 的数值守恒门槛；当前有效结果应为 PASS。
        "mass_closure_status": mass_closure_status,
        # rotary_inertia_coverage_status 是动力质量矩阵门槛；源证补齐前固定为 INCOMPLETE。
        "rotary_inertia_coverage_status": rotary_inertia_coverage_status,
        # dynamic_readiness=BLOCKED 表示不得凭本质量守恒结果恢复正式动力模态作业。
        "dynamic_readiness": "BLOCKED",
        "units": {
            "length": "mm",
            "mass": "tonne",
            "force": "N",
            "inertia": "tonne*mm^2",
            "coordinate_system": "MAPDL X longitudinal, Y transverse, Z vertical",
        },
        "constants": {
            "gravity_mm_s2": G_MM_S2,
            "target_concentrated_mass_tonne": TARGET_CONCENTRATED_MASS_TONNE,
            "invariant_distributed_link_mass_tonne": invariant_distributed_mass_tonne,
            "target_full_model_mass_tonne": TARGET_FULL_MODEL_MASS_TONNE,
            "mass_tolerance_tonne": MASS_TOLERANCE_TONNE,
            "mass21_type_id": MASS21_TYPE_ID,
            "mass21_element_start": MASS21_ELEMENT_START,
            "mass21_real_start": MASS21_REAL_START,
        },
        "input_binding": input_binding,
        "topology_counts": {
            "before_mass_node_count": int(before_properties["node_count"]),
            "after_mass_node_count": int(after_properties["node_count"]),
            "after_original_node_count": sum(
                1 for point in after_ledger.points.values() if not point.is_generated
            ),
            "after_generated_gate_node_count": sum(
                1 for point in after_ledger.points.values() if point.system == "gate"
            ),
            "after_generated_passage_node_count": sum(
                1 for point in after_ledger.points.values() if point.system == "passage"
            ),
        },
        "mass_closure": {
            "before_mass_tonne": float(before_properties["mass_tonne"]),
            "before_error_tonne": before_mass_error,
            "after_mass_tonne": float(after_properties["mass_tonne"]),
            "after_error_tonne": after_mass_error,
            "predicted_full_model_mass_tonne": predicted_full_mass_tonne,
            "full_model_error_tonne": full_mass_error,
        },
        "component_balance": component_balance,
        # rotary_inertia_coverage 逐项说明已计算量、缺失量和禁止的错误修法。
        "rotary_inertia_coverage": {
            # 三向平动质量已经通过节点空间位置产生平行轴或“轨道”惯量。
            "orbital_inertia_from_mass_point_coordinates": "CALCULATED",
            # TYPE=71 仍采用 KEYOPT(3)=2，因此单点所代表构件的自身惯量没有进入质量矩阵。
            "mass21_intrinsic_rotary_inertia": "NOT_MODELLED_SOURCE_DATA_MISSING",
            # 权威重量表没有提供各集中构件的真实三轴质心和质心惯量张量。
            "component_cg_and_inertia_source": "INCOMPLETE",
            # 表1-1附件仍混在材料1底索等效密度中，尚未完成真实横竖向空间化。
            "table_1_1_accessory_mass_spatialization": "INCOMPLETE",
            # 当前 CG 和惯量只作为可复算诊断量，不能在没有独立目标时构成通过判据。
            "independent_cg_and_inertia_acceptance_target": "MISSING",
            # 禁止把已有 mr² 再填入 IXX/IYY/IZZ，否则会重复计算平行轴贡献。
            "prohibition": "不得猜测内禀惯量，也不得把节点坐标产生的 m*r^2 重复写入 MASS21",
        },
        "before_original_combined_mass21": before_properties,
        "after_spatialized_mass21": after_properties,
        "after_minus_before": {
            "center_of_mass_mm": difference_mapping(cg_after, cg_before),  # type: ignore[arg-type]
            "inertia_about_origin": difference_mapping(
                inertia_after_origin, inertia_before_origin  # type: ignore[arg-type]
            ),
            "inertia_about_center_of_mass": difference_mapping(
                inertia_after_cg, inertia_before_cg  # type: ignore[arg-type]
            ),
        },
        "interpretation": {
            "scope": (
                "CG和惯量前后值针对963.811380787273 tonne的MCT二期集中质量；"
                "3144.655526792727 tonne索系分布质量在本次迁移中保持不变。"
            ),
            "gate_bottom_rule": "3.18 kN按门架下横梁单元体积分配并半集中到梁端节点",
            "gate_upper_rule": "8.927/12.36 kN按顶梁及两立柱单元体积分配并半集中到梁端节点",
            "guide_rule": "9.196 kN等分到每幅门架顶梁6个门架索连接点",
            "passage_rule": "两幅49.69 kN合并为99.38 kN并按整品横通道全部杆件体积分配",
            "retained_rule": "大横梁、PWS、抑位器、塔架、锚碇架保留原索节点",
        },
    }


def write_audit_markdown(path: Path, audit: Mapping[str, object]) -> None:
    """把 JSON 审计中的关键结果写成中文 Markdown 摘要。

    参数：
        path: Markdown 输出路径。
        audit: ``build_audit`` 返回的完整审计字典。
    返回：无。
    """

    # 以下局部变量只抽取 Markdown 表格所需字段，避免在格式字符串中反复深层索引。
    mass_closure = audit["mass_closure"]  # type: ignore[assignment]
    before = audit["before_original_combined_mass21"]  # type: ignore[assignment]
    after = audit["after_spatialized_mass21"]  # type: ignore[assignment]
    delta = audit["after_minus_before"]  # type: ignore[assignment]
    component_balance = audit["component_balance"]  # type: ignore[assignment]
    topology_counts = audit["topology_counts"]  # type: ignore[assignment]
    lines: list[str] = [
        "# V2.0 动力质量空间化审计",
        "",
        f"- 完整动力质量状态：**{audit['status']}**",
        f"- 总质量与分项守恒：**{audit['mass_closure_status']}**",
        f"- 内禀转动惯量覆盖：**{audit['rotary_inertia_coverage_status']}**",
        f"- 动力作业就绪状态：**{audit['dynamic_readiness']}**",
        f"- 重力加速度：{G_MM_S2:.1f} mm/s²",
        "- 坐标：MAPDL X 顺桥、Y 横桥、Z 竖向",
        "- 惯量单位：tonne·mm²",
        "",
        "## 1. 总质量闭合",
        "",
        "| 项目 | 质量 / tonne | 误差 / tonne |",
        "|---|---:|---:|",
        (
            f"| 空间化前 MCT 二期集中质量 | {mass_closure['before_mass_tonne']:.15f} | "
            f"{mass_closure['before_error_tonne']:.3e} |"
        ),
        (
            f"| 空间化后 MASS21 | {mass_closure['after_mass_tonne']:.15f} | "
            f"{mass_closure['after_error_tonne']:.3e} |"
        ),
        (
            f"| 完整模型预测总质量 | {mass_closure['predicted_full_model_mass_tonne']:.15f} | "
            f"{mass_closure['full_model_error_tonne']:.3e} |"
        ),
        "",
        "## 2. 节点数量",
        "",
        f"- 空间化前质量节点：{topology_counts['before_mass_node_count']}",
        f"- 空间化后质量节点：{topology_counts['after_mass_node_count']}",
        f"- 保留原节点：{topology_counts['after_original_node_count']}",
        f"- 新增门架质量节点：{topology_counts['after_generated_gate_node_count']}",
        f"- 新增横通道质量节点：{topology_counts['after_generated_passage_node_count']}",
        "",
        "## 3. 分项守恒",
        "",
        "| 分项 | 两幅数量 | 前质量 / tonne | 后质量 / tonne | 误差 / tonne |",
        "|---|---:|---:|---:|---:|",
    ]
    # 逐项表保留 component_id 稳定键名，便于与 items.csv 和长表 CSV 直接连接。
    for component_id in sorted(component_balance):
        balance = component_balance[component_id]
        lines.append(
            f"| {component_id} | {balance['quantity_two_catwalks']} | "
            f"{balance['before_mass_tonne']:.12f} | {balance['after_mass_tonne']:.12f} | "
            f"{balance['error_tonne']:.3e} |"
        )
    before_cg = before["center_of_mass_mm"]
    after_cg = after["center_of_mass_mm"]
    delta_cg = delta["center_of_mass_mm"]
    lines.extend(
        [
            "",
            "## 4. 集中质量重心变化",
            "",
            "| 方向 | 前 / mm | 后 / mm | 后-前 / mm |",
            "|---|---:|---:|---:|",
        ]
    )
    # X/Y/Z 三行用统一格式输出；Y 理论上因两幅对称应接近零。
    for axis in ("x", "y", "z"):
        lines.append(
            f"| {axis.upper()} | {before_cg[axis]:.6f} | {after_cg[axis]:.6f} | "
            f"{delta_cg[axis]:.6f} |"
        )
    before_inertia = before["inertia_about_center_of_mass"]
    after_inertia = after["inertia_about_center_of_mass"]
    delta_inertia = delta["inertia_about_center_of_mass"]
    lines.extend(
        [
            "",
            "## 5. 关于集中质量重心的惯量变化",
            "",
            "| 分量 | 前 / tonne·mm² | 后 / tonne·mm² | 后-前 / tonne·mm² |",
            "|---|---:|---:|---:|",
        ]
    )
    # 六个张量独立分量全部输出，不能只看 Ixx/Iyy/Izz 而忽略非对角耦合。
    for key in (
        "Ixx_tonne_mm2",
        "Iyy_tonne_mm2",
        "Izz_tonne_mm2",
        "Ixy_tonne_mm2",
        "Ixz_tonne_mm2",
        "Iyz_tonne_mm2",
    ):
        lines.append(
            f"| {key.replace('_tonne_mm2', '')} | {before_inertia[key]:.9e} | "
            f"{after_inertia[key]:.9e} | {delta_inertia[key]:.9e} |"
        )
    lines.extend(
        [
            "",
            "## 6. 空间化规则",
            "",
            "1. 门架下横梁 3.18 kN 按下横梁单元体积归一化，并把每根梁质量各半集中到两端。",
            "2. 普通门架 8.927 kN 或横通道三角门架 12.36 kN 按顶梁与两根立柱体积归一化。",
            "3. 导轮组 9.196 kN 等分到顶梁 6 个门架索连接点。",
            "4. 每品横通道两幅半重合并为 99.38 kN，按全部杆件截面体积分配。",
            "5. 大横梁、PWS 滚筒、主缆抑位器、塔架与锚碇架质量保留在原索节点。",
            "",
            "> 注：本页重心和惯量前后值针对 963.811380787273 tonne 的 MCT 二期集中质量；",
            "> 3144.655526792727 tonne 索系分布质量在本次空间化中保持不变。",
            "",
            "## 7. 尚未通过的动力质量项目",
            "",
            "1. TYPE 71 仍采用 `KEYOPT(3)=2`；节点坐标产生的轨道惯量已计算，但构件自身惯量无源证。",
            "2. 权威重量表未给集中构件真实三轴质心与质心惯量，当前体积/六点分配属于可复算假设。",
            "3. 表 1-1 的扶手绳、网片、踏步、小横梁、电缆等仍混在材料 1 等效底索密度中。",
            "4. 因此本文件只允许声明质量守恒 PASS，不允许声明完整质心或扭转质量矩阵 PASS。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def parse_arguments() -> argparse.Namespace:
    """解析生成器命令行参数。

    参数：无；参数来自命令行。
    返回：
        含 project_root、generated_directory 和 output_directory 的命名空间。
    """

    # script_directory 是 V2.0 根目录，默认输出与求解准备脚本约定一致。
    script_directory = Path(__file__).resolve().parent
    # project_root 默认取 V2.0 根目录向上两级，即 D:/张靖皋大桥。
    project_root = script_directory.parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=project_root,
        help="项目根目录；默认由脚本位置自动定位。",
    )
    parser.add_argument(
        "--generated-directory",
        type=Path,
        default=script_directory / "builder" / "generated",
        help="有限门架/横通道 builder 的 generated 输出目录。",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=script_directory,
        help="MASS21 include、CSV 和审计输出目录。",
    )
    return parser.parse_args()


def main() -> None:
    """执行输入绑定、组合拆分、空间化分配、严格自校验和全部文件输出。

    参数：无；读取 ``parse_arguments`` 的命令行配置。
    返回：无；成功时打印一行 PASS 摘要，失败时抛出异常并不覆盖有效结果。
    """

    # args 保存显式路径参数；resolve 让审计记录不依赖调用时工作目录。
    args = parse_arguments()
    project_root = args.project_root.resolve()
    generated_directory = args.generated_directory.resolve()
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    # geometry_directory 是权威 mapping/items 与原绳索坐标所在的唯一来源目录。
    geometry_directory = (
        project_root
        / "02_CAD几何模型"
        / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"
    )
    # input_paths 集中定义并在审计中逐个绑定哈希，避免某个输入遗漏版本记录。
    input_paths = {
        "authoritative_items": geometry_directory / "authoritative_mct_deadload_v1_items.csv",
        "authoritative_conload_mapping": (
            geometry_directory / "authoritative_mct_deadload_v1_conload_mapping.csv"
        ),
        "original_rope_nodes": geometry_directory / "nodes.csv",
        "generated_nodes": generated_directory / "generated_nodes.csv",
        "generated_elements": generated_directory / "generated_elements.csv",
        "resolved_dedicated_stations": generated_directory / "resolved_dedicated_stations.csv",
    }
    # 所有输入先做存在性检查，避免运行到中途才发现缺文件并留下部分新输出。
    for input_name, input_path in input_paths.items():
        if not input_path.is_file():
            raise FileNotFoundError(f"缺少 {input_name}：{input_path}")
    # items.csv 虽主要用于哈希和数量权威，仍检查所有要求分项都存在且单值一致。
    item_rows = read_csv_rows(input_paths["authoritative_items"])
    item_weights = {
        row["component_id"].strip(): float(row["unit_value"])
        for row in item_rows
        if row["component_id"].strip() in COMPONENT_UNIT_WEIGHT_KN
    }
    for component_id, expected_weight_kn in COMPONENT_UNIT_WEIGHT_KN.items():
        if component_id not in item_weights:
            raise KeyError(f"items.csv 缺少权威分项 {component_id}")
        if abs(item_weights[component_id] - expected_weight_kn) > COMBINATION_TOLERANCE_KN:
            raise ValueError(
                f"items.csv 中 {component_id} 单重 {item_weights[component_id]} 已变化，"
                f"脚本审查值为 {expected_weight_kn}"
            )
    # 原节点坐标转换后与 mapping 的节点号直接对接。
    original_coordinates = load_original_apdl_coordinates(input_paths["original_rope_nodes"])
    mapping_rows = read_csv_rows(input_paths["authoritative_conload_mapping"])
    before_ledger, component_quantities, _station_patterns = build_original_component_ledger(
        mapping_rows,
        original_coordinates,
        G_MM_S2,
    )
    # generated_nodes/elements 必须由同一次有限 builder 运行产生，哈希将在 JSON 中记录。
    generated_nodes, generated_elements = load_generated_topology(
        input_paths["generated_nodes"],
        input_paths["generated_elements"],
    )
    dedicated_station_rows = read_csv_rows(input_paths["resolved_dedicated_stations"])
    after_ledger = build_spatialized_ledger(
        before_ledger,
        generated_nodes,
        generated_elements,
        dedicated_station_rows,
        G_MM_S2,
    )
    # audit 在任何输出写入前完成；若质量、分项、重心或惯量计算失败，不产生半成品 APDL。
    audit = build_audit(
        before_ledger=before_ledger,
        after_ledger=after_ledger,
        component_quantities=component_quantities,
        input_paths=input_paths,
    )
    # 生成 APDL 的硬门槛是权威总质量和分项质量守恒；完整动力状态仍保持 INCOMPLETE。
    if audit["mass_closure_status"] != "PASS":
        # 质量不守恒时不得写出任何 APDL 或台账半成品。
        raise ArithmeticError(f"空间化质量审计失败：{audit['mass_closure']}")
    # 四类输出分别服务于 MAPDL、逐节点检查、逐分项追溯和人/机审计。
    apdl_path = output_directory / "apply_dynamic_mass21_spatialized_v2.inp"
    node_csv_path = output_directory / "mass21_spatialized_v2_nodes.csv"
    allocation_csv_path = output_directory / "mass21_spatialized_v2_component_allocations.csv"
    audit_json_path = output_directory / "mass21_spatialization_audit_v2.json"
    audit_markdown_path = output_directory / "质量空间化审计_V2.0.md"
    write_apdl_mass_include(apdl_path, after_ledger)
    write_node_mass_csv(node_csv_path, after_ledger)
    write_component_allocation_csv(allocation_csv_path, after_ledger)
    audit_json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    write_audit_markdown(audit_markdown_path, audit)
    # 终端摘要使用固定精度，供父流程和 CI 快速确认结果，而详细值保留在 JSON。
    mass_closure = audit["mass_closure"]
    print(
        "MASS_CLOSURE_PASS; ROTARY_INERTIA_INCOMPLETE: "
        f"MASS21={mass_closure['after_mass_tonne']:.15f} tonne, "
        f"full={mass_closure['predicted_full_model_mass_tonne']:.15f} tonne, "
        f"nodes={audit['topology_counts']['after_mass_node_count']}"
    )


# 仅在直接执行脚本时运行 main；作为模块导入时可复用审计函数而不产生文件。
if __name__ == "__main__":
    main()
