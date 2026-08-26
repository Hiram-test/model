#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成“有限刚度门架 + 21 道完整横向通道”的 MAPDL include。

本脚本只负责结构拓扑、截面刚度、几何偏置和接口约束，不负责把集中质量
从原有 MASS21 中移除或重新空间化。为避免在质量空间化完成前重复计入自重，
所有新建梁材料的密度默认均为 0 tonne/mm^3。

坐标约定非常重要：

* CAD/CSV 坐标：``(x, y, z) = (横桥向, 顺桥向, 竖向)``；
* 当前 XLongitudinal MAPDL 坐标：
  ``(X, Y, Z) = (CAD_y, -CAD_x, CAD_z)``；
* 单位制：N、mm、tonne、s。

与旧模型相比，本脚本明确禁止以下两种会锁死或漏掉截面运动的简化：

* 不把一品门架的全部索节点用 ``CP,UX/UY/UZ`` 强制为同一平动；
* 不把两幅猫道仅用一道 ``CP,UY`` 横向耦合。

门架和横通道均采用 BEAM188 有限刚度杆件。原 ``CERIG,ALL`` 采用六自由度
``MPC184 rigid beam``，原 ``CERIG,UXYZ`` 采用“偏置 rigid beam + 显式高罚刚度共点三平移 general joint”；
I 端固定写 master，J 端固定写 slave。两类来源运动学语义保留在审计台账中，不再生成只适用于小挠度的
``CERIG``。横通道端部仍通过有限刚度三角接口杆接入 dedicated gate，并仅在
梁轴—接口根节点的短偏置处使用刚性梁连接。
"""

from __future__ import annotations

# argparse 提供可重复的命令行接口，使后续标定可以显式替换站位表、编号起点
# 或输出目录，而无需直接修改源代码中的常量。
import argparse
# csv 用于读取项目已有的几何/荷载审计表，并输出节点、单元和约束台账。
import csv
# json 用于写出机器可复核的拓扑与截面自校验结果。
import json
# math 提供向量长度、三角函数以及圆管/矩形管截面公式所需的常数。
import math
# defaultdict 用于按门架、系统、截面和跨别累计节点/单元组件。
from collections import defaultdict
# dataclass 让几何点、截面、节点、单元、约束等记录具有明确字段，减少位置参数误用。
from dataclasses import asdict, dataclass, field
# pathlib 可靠处理 Windows 中文路径，并避免手工拼接反斜杠。
from pathlib import Path
# typing 中的 Iterable/Sequence 为辅助函数注明输入集合的语义。
from typing import Iterable, Sequence


# ------------------------------ 稳定编号约定 ------------------------------

# BEAM_TYPE_ID 与现有模型中的 TYPE=1~6 错开；所有新增有限刚度梁统一使用该类型。
BEAM_TYPE_ID = 70

# MPC_RIGID_BEAM_TYPE_ID 使用当前空闲的 TYPE=72，实现来源语义为 ALL 的六自由度刚接。
MPC_RIGID_BEAM_TYPE_ID = 72
# MPC_TRANSLATION_JOINT_TYPE_ID 使用当前空闲的 TYPE=73，实现来源语义为 UXYZ 的共点三平移约束。
MPC_TRANSLATION_JOINT_TYPE_ID = 73
# MPC_TRANSLATION_JOINT_SECTION_ID 使用 SECTION=73 保存 displacement-only general joint 定义。
MPC_TRANSLATION_JOINT_SECTION_ID = 73
# MPC_TRANSLATION_JOINT_I_COORDINATE_SYSTEM_ID 使用空闲的局部坐标系9011定义joint的I端初始基底。
MPC_TRANSLATION_JOINT_I_COORDINATE_SYSTEM_ID = 9011
# MPC_TRANSLATION_JOINT_J_COORDINATE_SYSTEM_ID 使用空闲的局部坐标系9012定义joint的J端初始基底。
MPC_TRANSLATION_JOINT_J_COORDINATE_SYSTEM_ID = 9012
# MPC_RIGID_BEAM_KEYOPT_VALUE=1 选择具备六自由度刚体运动学的 rigid beam 公式。
MPC_RIGID_BEAM_KEYOPT_VALUE = 1
# MPC_DIRECT_ELIMINATION_KEYOPT_VALUE=0 选择可用于线性摄动分析的直接消元公式。
MPC_DIRECT_ELIMINATION_KEYOPT_VALUE = 0
# MPC_KEEP_GEOMETRIC_STIFFNESS_KEYOPT_VALUE=0 保留预应力摄动所需的几何刚度贡献。
MPC_KEEP_GEOMETRIC_STIFFNESS_KEYOPT_VALUE = 0
# MPC_GENERAL_JOINT_KEYOPT_VALUE=16 选择可逐项指定受约束相对自由度的general joint。
MPC_GENERAL_JOINT_KEYOPT_VALUE = 16
# MPC_DISPLACEMENT_ONLY_KEYOPT_VALUE=1 使joint节点只激活UX/UY/UZ，不向LINK180索节点引入自由转角。
MPC_DISPLACEMENT_ONLY_KEYOPT_VALUE = 1
# MPC_PENALTY_METHOD_KEYOPT_VALUE=1 选择可与直接消元rigid beam共节点的罚函数joint公式。
MPC_PENALTY_METHOD_KEYOPT_VALUE = 1
# MPC_TRANSLATION_PENALTY_FACTOR=5.0E10 是位移约束绝对罚因子；N-mm体系下的基准最大滑移为9.1944E-6 mm。
MPC_TRANSLATION_PENALTY_FACTOR = 5.0e10
# MPC_CONNECTION_COMPONENT_NAME 是两类 MPC184 连接共同使用的稳定 MAPDL 单元组件名。
MPC_CONNECTION_COMPONENT_NAME = "V2_MPC184_E"

# MATERIAL_IDS 为每一类可独立标定的构件保留稳定材料号。即使当前弹性模量相同，
# 后续也可仅修改某一材料的 EX，而不必重建拓扑或重编号单元。
MATERIAL_IDS = {
    "gate_bottom": 61,
    "gate_top_post": 62,
    "passage_chord152": 63,
    "passage_frame102": 64,
    "passage_brace51": 65,
    "passage_rhs50x30": 66,
}

# SECTION_IDS 与材料组一一对应，保持截面号在多轮参数标定之间不变。
SECTION_IDS = {
    "gate_bottom": 61,
    "gate_top_post": 62,
    "passage_chord152": 63,
    "passage_frame102": 64,
    "passage_brace51": 65,
    "passage_rhs50x30": 66,
}

# SECTION_COMPONENT_NAMES 给每个标定组分配不超过 32 字符的 MAPDL 单元组件名。
SECTION_COMPONENT_NAMES = {
    "gate_bottom": "GATE_BOTTOM_E",
    "gate_top_post": "GATE_TOPPOST_E",
    "passage_chord152": "PASS_CHORD152_E",
    "passage_frame102": "PASS_FRAME102_E",
    "passage_brace51": "PASS_BRACE51_E",
    "passage_rhs50x30": "PASS_RHS5030_E",
}

# 完整横通道装配控制尺寸来自 MD5-02 和既有 FreeCAD 装配脚本。
PASSAGE_CONTROL_LENGTH_MM = 49_720.0
PASSAGE_WIDTH_MM = 1_500.0
PASSAGE_HEIGHT_MM = 1_700.0

# MODULE_PLACEMENTS 按左至右顺序定义六段模块。尾段实体长 6700 mm，而装配控制
# 长度为 6600 mm，因此左右接口各存在 100 mm 搭接；后续拆分/去重算法会显式
# 合并该搭接，不会生成重叠单元。
MODULE_PLACEMENTS = (
    ("LT", "tail", 0.0, False),
    ("M1", "middle", 6_600.0, False),
    ("M2", "middle", 16_140.0, False),
    ("AD", "adjustment", 25_680.0, False),
    ("M3", "middle", 33_580.0, False),
    ("RT", "tail", PASSAGE_CONTROL_LENGTH_MM, True),
)

# 几何容差单位为 mm。CSV 坐标本身精确到远高于该尺度；使用 1e-4 mm 足以合并
# 模块边界和杆件交点，同时不会错误合并相邻的实体节点。
GEOMETRY_TOL_MM = 1.0e-4

# H175_SHEAR_CORRECTION_XZ 取自 MAPDL 2026 R1 对同尺寸 BEAM-I 截面的 SCZZ；
# 该无量纲值控制腹板主承的 local-xz（竖向）有效剪切刚度，而不是材料倍率。
H175_SHEAR_CORRECTION_XZ = 0.2363842696133852
# H175_SHEAR_CORRECTION_XY 取自同一内置截面的 SCYY，控制翼缘主承的 local-xy 剪切刚度。
H175_SHEAR_CORRECTION_XY = 0.6712958043168660
# RHS160_SHEAR_CORRECTION 取自 MAPDL 2026 R1 对 RHS160×160×4 BEAM-HREC 截面的
# SCYY/SCZZ；方形截面对称，两个方向采用同一无量纲值。
RHS160_SHEAR_CORRECTION = 0.4260313674227942
# HOLLOW_CIRCLE_SHEAR_CORRECTION 采用 ANSYS BEAM188 官方给出的薄壁空心圆管基准 1/2；
# PHI152×6、PHI102×4 与 PHI51×4 的 local-xz/local-xy 两个方向均使用该值。
HOLLOW_CIRCLE_SHEAR_CORRECTION = 0.5
# RHS50X30_SHEAR_CORRECTION_XZ 取自 MAPDL 2026 R1 对 local-y=50 mm、local-z=30 mm、
# 壁厚 4 mm 的 BEAM-HREC 截面 SCZZ，控制沿 30 mm 高度方向的 xz 剪切刚度。
RHS50X30_SHEAR_CORRECTION_XZ = 0.2874280543410113
# RHS50X30_SHEAR_CORRECTION_XY 取自同一内置截面的 SCYY，控制沿 50 mm 宽度方向的 xy 剪切刚度。
RHS50X30_SHEAR_CORRECTION_XY = 0.6098841965465526


@dataclass(frozen=True)
class Vec3:
    """不可变三维向量。

    参数：
        x: 第一坐标分量，单位 mm。
        y: 第二坐标分量，单位 mm。
        z: 第三坐标分量，单位 mm。

    该类型既可表示 CAD 坐标，也可表示 MAPDL 坐标；调用处必须通过变量名或
    注释说明坐标系，禁止隐式混用。
    """

    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        """返回两个向量逐分量相加的结果。"""

        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        """返回当前向量减去 ``other`` 的结果。"""

        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        """返回向量乘以标量 ``scalar`` 的结果。"""

        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other: "Vec3") -> float:
        """返回当前向量与 ``other`` 的点积。"""

        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        """返回当前向量与 ``other`` 的右手叉积。"""

        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def norm(self) -> float:
        """返回欧氏长度，单位与分量一致。"""

        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        """返回单位向量；零长度向量会立即报错，避免产生无效梁方向。"""

        length = self.norm()
        if length <= 1.0e-12:
            raise ValueError("不能归一化零长度向量")
        return self * (1.0 / length)

    def distance_to(self, other: "Vec3") -> float:
        """返回当前点到 ``other`` 的欧氏距离，单位 mm。"""

        return (self - other).norm()


@dataclass(frozen=True)
class SectionDef:
    """BEAM188 ASEC 所需的截面参数及稳定标定信息。

    参数：
        key: 内部稳定组名。
        material_id: MAPDL 材料号。
        section_id: MAPDL 截面号。
        area_mm2: 面积 A，单位 mm^2。
        iyy_mm4: 关于梁局部 y 轴的惯性矩，单位 mm^4。
        izz_mm4: 关于梁局部 z 轴的惯性矩，单位 mm^4。
        torsion_j_mm4: Saint-Venant 扭转常数 J，单位 mm^4。
        warping_iw_mm6: 翘曲常数 Iw，单位 mm^6；圆/闭口管取 0。
        thickness_z_mm: 截面沿梁局部 z 轴的最大高度 TKz，单位 mm；ASEC 必须显式输入。
        thickness_y_mm: 截面沿梁局部 y 轴的最大宽度 TKy，单位 mm；ASEC 必须显式输入。
        shear_correction_xz: xz 剪切分量的无量纲修正 TSxz，使 Kxz=TSxz*G*A。
        shear_correction_xy: xy 剪切分量的无量纲修正 TSxy，使 Kxy=TSxy*G*A。
        description: 人可读截面说明。
    """

    key: str
    material_id: int
    section_id: int
    area_mm2: float
    iyy_mm4: float
    izz_mm4: float
    torsion_j_mm4: float
    warping_iw_mm6: float
    # thickness_z_mm 是 ASEC 的第 11 项 TKz，表示 local-z 方向的截面外包络高度。
    thickness_z_mm: float
    # thickness_y_mm 是 ASEC 的第 12 项 TKy，表示 local-y 方向的截面外包络宽度。
    thickness_y_mm: float
    # shear_correction_xz 是 ASEC 的第 13 项 TSxz，控制 local-xz 平面的有效剪切刚度。
    shear_correction_xz: float
    # shear_correction_xy 是 ASEC 的第 14 项 TSxy，控制 local-xy 平面的有效剪切刚度。
    shear_correction_xy: float
    description: str


@dataclass
class NodeRecord:
    """一个由本生成器新建的 MAPDL 节点台账记录。"""

    apdl_node_id: int
    apdl_point: Vec3
    cad_point: Vec3
    system: str
    assembly_name: str
    role: str
    source_local_coord: str
    is_orientation: bool = False


@dataclass
class ElementRecord:
    """一个新增 BEAM188 单元的完整台账记录。"""

    apdl_elem_id: int
    n1: int
    n2: int
    orientation_node: int
    system: str
    assembly_name: str
    member: str
    section_key: str
    source_member_id: str
    length_mm: float


@dataclass
class RigidConnectionRecord:
    """一个按来源自由度语义选择 MPC184 公式的大转动连接台账记录。

    参数：
        apdl_elem_id: ALL 的 rigid beam 或 UXYZ 的共点 general joint 单元号；登记阶段必须为 ``None``。
        offset_elem_id: UXYZ 专用偏置 rigid beam 单元号；ALL 连接保持 ``None``。
        offset_node_id: UXYZ 专用且与原 slave 共点的零质量辅助节点；ALL 连接保持 ``None``。
        master_node: 既有台账语义中的主节点，并固定写在 MAPDL ``EN`` 命令的 I 端。
        slave_node: 既有台账语义中的从节点，并固定写在 MAPDL ``EN`` 命令的 J 端。
        source_semantics: 原 CERIG 的 UXYZ 或 ALL 语义，仅用于迁移追溯和数量闭合。
        system: gate 或 passage，用于区分门架与横通道系统。
        assembly_name: 当前连接所属的门架或横通道装配名称。
        reason: 当前刚性连接对应的物理接口及建模目的。
    """

    # apdl_elem_id 在物理 BEAM188 全部生成后统一赋值，确保两类单元编号连续且不交叠。
    apdl_elem_id: int | None
    # offset_elem_id 只为 UXYZ 分配，负责把 master 转动转换为共点辅助节点的刚体平移。
    offset_elem_id: int | None
    # offset_node_id 只为 UXYZ 保存，且坐标严格等于原 slave，以便共点 general joint 仅耦合平移。
    offset_node_id: int | None
    # master_node 固定作为 MPC184 的 I 端，使同一星形连接的公共主节点顺序一致。
    master_node: int
    # slave_node 固定作为 MPC184 的 J 端；MAPDL 内部消元的独立节点仍由求解器决定。
    slave_node: int
    # source_semantics 只允许 UXYZ 或 ALL，用于证明迁移前后 3124/1954 条语义数量不变。
    source_semantics: str
    # system 标识 gate 或 passage，供机器审计按结构系统分组。
    system: str
    # assembly_name 标识当前连接所属的具体品号，供拓扑连通性检查使用。
    assembly_name: str
    # reason 保存连接构造和目的，避免把机械替换误称为已取得接口图纸源证。
    reason: str


@dataclass(frozen=True)
class RawPassageEdge:
    """模块装配后、交点拆分前的一根原始中心线杆件。"""

    start: Vec3
    end: Vec3
    section_key: str
    member: str
    source_member_id: str


@dataclass
class PassageTemplate:
    """完成交点拆分、搭接去重后的单品横通道局部模板。"""

    points: list[Vec3]
    point_roles: list[str]
    edges: list[tuple[int, int, str, str, str]]
    intersection_points_added: int
    duplicate_subedges_removed: int
    represented_components: int


@dataclass
class GateBuildInfo:
    """一品门架构建后供横通道接口调用的关键节点信息。"""

    gate_name: str
    gate_index: int
    catwalk: int
    physical_node_ids: list[int]
    element_ids: list[int]
    outer_bottom_axis_master: int
    outer_bottom_rope_point_cad: Vec3
    bottom_axis_master_by_rope_index: dict[int, int]
    bottom_rope_point_by_rope_index: dict[int, Vec3]


@dataclass
class BuildAudit:
    """累积构建过程中的校验计数和警告。"""

    gate_count: int = 0
    passage_count: int = 0
    generated_node_count: int = 0
    generated_physical_node_count: int = 0
    generated_orientation_node_count: int = 0
    # generated_element_count 记录 BEAM188 与 MPC184 的新增单元总数，单位为个。
    generated_element_count: int = 0
    # generated_physical_beam_count 只记录可参与体积质量分配的 BEAM188 数量，单位为个。
    generated_physical_beam_count: int = 0
    # generated_mpc184_count 只记录零质量刚性连接单元数量，单位为个。
    generated_mpc184_count: int = 0
    # duplicate_rigid_connection_pairs 记录重复的无向 MPC184 端点对，验收目标为 0。
    duplicate_rigid_connection_pairs: int = 0
    # rigid_connection_physical_edge_overlaps 记录与物理 BEAM188 重合的 MPC 边，验收目标为 0。
    rigid_connection_physical_edge_overlaps: int = 0
    # max_rigid_master_degree 记录同一 master 发出的最大星形连接数，当前设计上限应为 4。
    max_rigid_master_degree: int = 0
    # h175_axis_audit_count 记录逐件通过 local-z/Iyy/Izz/TKz/TKy 硬校验的 H175 数量。
    h175_axis_audit_count: int = 0
    # rhs50x30_axis_audit_count 记录逐件通过 50/30 朝向硬校验的 RHS 数量。
    rhs50x30_axis_audit_count: int = 0
    duplicate_element_pairs: int = 0
    zero_length_elements: int = 0
    unused_physical_nodes: int = 0
    disconnected_assemblies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def discover_project_root(explicit_root: Path | None) -> Path:
    """定位项目根目录 ``D:/张靖皋大桥``。

    参数：
        explicit_root: 命令行显式给出的项目根；为 ``None`` 时从脚本父目录和
            当前工作目录逐级向上查找。

    返回：
        同时包含 ``02_CAD几何模型``、``03_猫道动力分析`` 和 ``output`` 的目录。
    """

    # 显式路径优先，便于复制到其他机器后复用生成器。
    if explicit_root is not None:
        candidates = [explicit_root.resolve()]
    else:
        # 脚本目录和当前工作目录都加入候选，以兼容从项目根或 builder 目录启动。
        candidates = list(Path(__file__).resolve().parents) + list(Path.cwd().resolve().parents)
        candidates.insert(0, Path.cwd().resolve())

    # 逐个检查具有项目特征的三个目录；第一次命中即为最靠近脚本的项目根。
    for candidate in candidates:
        if (
            (candidate / "02_CAD几何模型").is_dir()
            and (candidate / "03_猫道动力分析").is_dir()
            and (candidate / "output").is_dir()
        ):
            return candidate
    raise FileNotFoundError("无法定位张靖皋大桥项目根目录；请使用 --project-root 显式指定")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """以 UTF-8/BOM 兼容方式读取 CSV，并返回字典行列表。"""

    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def cad_to_apdl(point: Vec3) -> Vec3:
    """把 CAD ``(横桥向, 顺桥向, 竖向)`` 转成当前 XLongitudinal MAPDL 坐标。"""

    return Vec3(point.y, -point.x, point.z)


def coordinate_key(point: Vec3, tolerance: float = GEOMETRY_TOL_MM) -> tuple[int, int, int]:
    """按给定容差把浮点坐标量化为可哈希键，用于节点去重。"""

    return (
        round(point.x / tolerance),
        round(point.y / tolerance),
        round(point.z / tolerance),
    )


def point_segment_parameter(point: Vec3, start: Vec3, end: Vec3) -> tuple[float, float]:
    """计算点在直线段上的投影参数及点到投影的距离。

    返回：
        ``(t, distance_mm)``，其中投影点为 ``start + t*(end-start)``。
        ``0<=t<=1`` 表示投影落在线段内部。
    """

    direction = end - start
    squared_length = direction.dot(direction)
    if squared_length <= 1.0e-20:
        raise ValueError("原始杆件存在零长度线段")
    t_value = (point - start).dot(direction) / squared_length
    projected = start + direction * t_value
    return t_value, point.distance_to(projected)


def closest_points_on_segments(
    p1: Vec3,
    q1: Vec3,
    p2: Vec3,
    q2: Vec3,
) -> tuple[float, float, Vec3, Vec3]:
    """求两条有限三维线段的最近点及相应参数。

    参数：
        p1, q1: 第一条线段端点。
        p2, q2: 第二条线段端点。

    返回：
        ``(s, t, c1, c2)``；``c1=p1+s*(q1-p1)``，
        ``c2=p2+t*(q2-p2)``，且 ``s,t`` 已截断到 ``[0,1]``。

    公式采用通用线段最近点算法；平行和退化分支均显式处理，防止除零。
    """

    d1 = q1 - p1
    d2 = q2 - p2
    relative = p1 - p2
    a_value = d1.dot(d1)
    e_value = d2.dot(d2)
    f_value = d2.dot(relative)
    epsilon = 1.0e-20

    # 两条线段同时退化为点时，最近点就是两个输入点。
    if a_value <= epsilon and e_value <= epsilon:
        return 0.0, 0.0, p1, p2

    # 第一条退化为点时，只需把该点投影到第二条线段。
    if a_value <= epsilon:
        s_value = 0.0
        t_value = max(0.0, min(1.0, f_value / e_value))
    else:
        c_value = d1.dot(relative)
        # 第二条退化为点时，反向投影到第一条线段。
        if e_value <= epsilon:
            t_value = 0.0
            s_value = max(0.0, min(1.0, -c_value / a_value))
        else:
            b_value = d1.dot(d2)
            denominator = a_value * e_value - b_value * b_value
            # 非平行时先求无限直线的最优 s；平行时任选 s=0 后再截断 t。
            if abs(denominator) > epsilon:
                s_value = max(
                    0.0,
                    min(1.0, (b_value * f_value - c_value * e_value) / denominator),
                )
            else:
                s_value = 0.0
            t_value = (b_value * s_value + f_value) / e_value
            # t 越界时固定在端点，再重新求对应的 s。
            if t_value < 0.0:
                t_value = 0.0
                s_value = max(0.0, min(1.0, -c_value / a_value))
            elif t_value > 1.0:
                t_value = 1.0
                s_value = max(0.0, min(1.0, (b_value - c_value) / a_value))

    closest_1 = p1 + d1 * s_value
    closest_2 = p2 + d2 * t_value
    return s_value, t_value, closest_1, closest_2


def i_section_properties(
    height_mm: float,
    flange_width_mm: float,
    web_thickness_mm: float,
    flange_thickness_mm: float,
) -> tuple[float, float, float, float, float]:
    """计算双轴对称焊接 H/I 截面的 A、弱轴 I、强轴 I、J 和 Iw。

    返回：
        ``(A, I_weak, I_strong, J, Iw)``，单位依次为
        mm^2、mm^4、mm^4、mm^4、mm^6。
    """

    web_height = height_mm - 2.0 * flange_thickness_mm
    if min(height_mm, flange_width_mm, web_thickness_mm, flange_thickness_mm, web_height) <= 0.0:
        raise ValueError("H 形截面尺寸必须全部为正，且腹板净高必须大于 0")
    area = 2.0 * flange_width_mm * flange_thickness_mm + web_height * web_thickness_mm
    i_strong = (
        2.0
        * (
            flange_width_mm * flange_thickness_mm**3 / 12.0
            + flange_width_mm
            * flange_thickness_mm
            * (height_mm / 2.0 - flange_thickness_mm / 2.0) ** 2
        )
        + web_thickness_mm * web_height**3 / 12.0
    )
    i_weak = (
        2.0 * flange_thickness_mm * flange_width_mm**3 / 12.0
        + web_height * web_thickness_mm**3 / 12.0
    )
    torsion_j = (
        2.0 * flange_width_mm * flange_thickness_mm**3
        + web_height * web_thickness_mm**3
    ) / 3.0
    # 对称 I 形截面的常用薄壁近似翘曲常数；用于保留开口截面翘曲量级。
    warping_iw = (
        flange_width_mm**3
        * flange_thickness_mm
        * (height_mm - flange_thickness_mm) ** 2
        / 24.0
    )
    return area, i_weak, i_strong, torsion_j, warping_iw


def square_hollow_properties(size_mm: float, thickness_mm: float) -> tuple[float, float, float]:
    """计算等壁厚方管的 A、单轴 I 和闭口薄壁 J。"""

    inner = size_mm - 2.0 * thickness_mm
    if inner <= 0.0:
        raise ValueError("方管内边长必须大于 0")
    area = size_mm**2 - inner**2
    inertia = (size_mm**4 - inner**4) / 12.0
    median_size = size_mm - thickness_mm
    median_area = median_size**2
    perimeter_over_t = 4.0 * median_size / thickness_mm
    torsion_j = 4.0 * median_area**2 / perimeter_over_t
    return area, inertia, torsion_j


def rectangular_hollow_properties(
    height_mm: float,
    width_mm: float,
    thickness_mm: float,
) -> tuple[float, float, float, float]:
    """计算等壁厚矩形管的 A、两个主惯性矩和闭口薄壁 J。"""

    inner_height = height_mm - 2.0 * thickness_mm
    inner_width = width_mm - 2.0 * thickness_mm
    if min(inner_height, inner_width) <= 0.0:
        raise ValueError("矩形管内尺寸必须大于 0")
    area = height_mm * width_mm - inner_height * inner_width
    # i_about_y 对应 z 尺寸（此处 width）平方分布；i_about_z 对应 height 平方分布。
    i_about_y = (height_mm * width_mm**3 - inner_height * inner_width**3) / 12.0
    i_about_z = (width_mm * height_mm**3 - inner_width * inner_height**3) / 12.0
    median_height = height_mm - thickness_mm
    median_width = width_mm - thickness_mm
    median_area = median_height * median_width
    perimeter_over_t = 2.0 * (median_height + median_width) / thickness_mm
    torsion_j = 4.0 * median_area**2 / perimeter_over_t
    return area, i_about_y, i_about_z, torsion_j


def circular_tube_properties(diameter_mm: float, thickness_mm: float) -> tuple[float, float, float]:
    """计算圆管的 A、任一弯曲主惯性矩 I 和极惯性/扭转常数 J。"""

    inner_diameter = diameter_mm - 2.0 * thickness_mm
    if inner_diameter <= 0.0:
        raise ValueError("圆管内径必须大于 0")
    area = math.pi * (diameter_mm**2 - inner_diameter**2) / 4.0
    inertia = math.pi * (diameter_mm**4 - inner_diameter**4) / 64.0
    torsion_j = 2.0 * inertia
    return area, inertia, torsion_j


def build_section_definitions() -> dict[str, SectionDef]:
    """建立六个稳定且可独立标定的材料/截面组。"""

    gate_area, gate_iweak, gate_istrong, gate_j, gate_iw = i_section_properties(
        height_mm=175.0,
        flange_width_mm=175.0,
        web_thickness_mm=7.5,
        flange_thickness_mm=11.0,
    )
    rhs160_area, rhs160_i, rhs160_j = square_hollow_properties(160.0, 4.0)
    pipe152_area, pipe152_i, pipe152_j = circular_tube_properties(152.0, 6.0)
    pipe102_area, pipe102_i, pipe102_j = circular_tube_properties(102.0, 4.0)
    pipe51_area, pipe51_i, pipe51_j = circular_tube_properties(51.0, 4.0)
    rhs50_area, rhs50_iyy, rhs50_izz, rhs50_j = rectangular_hollow_properties(50.0, 30.0, 4.0)

    sections = {
        "gate_bottom": SectionDef(
            "gate_bottom",
            MATERIAL_IDS["gate_bottom"],
            SECTION_IDS["gate_bottom"],
            gate_area,
            gate_istrong,  # Iyy 绕 local-y；local-z 为腹板高度，所以该项必须使用竖弯强轴。
            gate_iweak,  # Izz 绕 local-z；local-y 为翼缘宽度，所以该项必须使用侧弯弱轴。
            gate_j,
            gate_iw,
            # H175 腹板沿 local-z 竖向布置，因此 TKz 为 175 mm 总高。
            175.0,
            # H175 翼缘沿 local-y 横向布置，因此 TKy 为 175 mm 总宽。
            175.0,
            # local-xz 剪切主要由腹板承担，采用 MAPDL 内置同尺寸 I 截面的 SCZZ。
            H175_SHEAR_CORRECTION_XZ,
            # local-xy 剪切主要由翼缘承担，采用 MAPDL 内置同尺寸 I 截面的 SCYY。
            H175_SHEAR_CORRECTION_XY,
            "门架下横梁 H175x175，腹板7.5，翼缘11",
        ),
        "gate_top_post": SectionDef(
            "gate_top_post",
            MATERIAL_IDS["gate_top_post"],
            SECTION_IDS["gate_top_post"],
            rhs160_area,
            rhs160_i,
            rhs160_i,
            rhs160_j,
            0.0,
            # RHS160 方管的 local-z 外包络高度为 160 mm。
            160.0,
            # RHS160 方管的 local-y 外包络宽度为 160 mm。
            160.0,
            # 方形空心截面的 xz 剪切修正与 xy 方向相同。
            RHS160_SHEAR_CORRECTION,
            # 方形空心截面的 xy 剪切修正与 xz 方向相同。
            RHS160_SHEAR_CORRECTION,
            "门架上横梁及立柱 RHS160x160x4",
        ),
        "passage_chord152": SectionDef(
            "passage_chord152",
            MATERIAL_IDS["passage_chord152"],
            SECTION_IDS["passage_chord152"],
            pipe152_area,
            pipe152_i,
            pipe152_i,
            pipe152_j,
            0.0,
            # PHI152 圆管在 local-z 方向的外包络高度等于 152 mm 外径。
            152.0,
            # PHI152 圆管在 local-y 方向的外包络宽度等于 152 mm 外径。
            152.0,
            # 空心圆管轴对称，xz 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            # 空心圆管轴对称，xy 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            "横通道主弦杆 PHI152x6",
        ),
        "passage_frame102": SectionDef(
            "passage_frame102",
            MATERIAL_IDS["passage_frame102"],
            SECTION_IDS["passage_frame102"],
            pipe102_area,
            pipe102_i,
            pipe102_i,
            pipe102_j,
            0.0,
            # PHI102 圆管在 local-z 方向的外包络高度等于 102 mm 外径。
            102.0,
            # PHI102 圆管在 local-y 方向的外包络宽度等于 102 mm 外径。
            102.0,
            # 空心圆管轴对称，xz 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            # 空心圆管轴对称，xy 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            "横通道端架/横架/接口杆 PHI102x4",
        ),
        "passage_brace51": SectionDef(
            "passage_brace51",
            MATERIAL_IDS["passage_brace51"],
            SECTION_IDS["passage_brace51"],
            pipe51_area,
            pipe51_i,
            pipe51_i,
            pipe51_j,
            0.0,
            # PHI51 圆管在 local-z 方向的外包络高度等于 51 mm 外径。
            51.0,
            # PHI51 圆管在 local-y 方向的外包络宽度等于 51 mm 外径。
            51.0,
            # 空心圆管轴对称，xz 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            # 空心圆管轴对称，xy 方向采用 ANSYS 官方薄壁空心圆管修正 1/2。
            HOLLOW_CIRCLE_SHEAR_CORRECTION,
            "横通道腹杆 PHI51x4",
        ),
        "passage_rhs50x30": SectionDef(
            "passage_rhs50x30",
            MATERIAL_IDS["passage_rhs50x30"],
            SECTION_IDS["passage_rhs50x30"],
            rhs50_area,
            rhs50_iyy,
            rhs50_izz,
            rhs50_j,
            0.0,
            # CAD 实体把 30 mm 作为竖向高度，方向节点令该尺寸对应 local-z。
            30.0,
            # CAD 实体把 50 mm 作为水平宽度，方向节点令该尺寸对应 local-y。
            50.0,
            # local-xz 剪切采用 MAPDL 内置 RHS50×30×4 截面的 SCZZ。
            RHS50X30_SHEAR_CORRECTION_XZ,
            # local-xy 剪切采用 MAPDL 内置 RHS50×30×4 截面的 SCYY。
            RHS50X30_SHEAR_CORRECTION_XY,
            "横通道纵向方矩管 RHS50x30x4",
        ),
    }

    # 所有刚度参数必须严格为正；翘曲常数允许闭口截面取 0。
    for section in sections.values():
        if min(
            section.area_mm2,
            section.iyy_mm4,
            section.izz_mm4,
            section.torsion_j_mm4,
        ) <= 0.0:
            raise ValueError(f"截面 {section.key} 存在非正 A/I/J")
        if section.warping_iw_mm6 < 0.0:
            raise ValueError(f"截面 {section.key} 的 Iw 不得为负")
        # ASEC 的 TKz/TKy 必须为正，否则截面外包络和后续方向审计没有物理意义。
        if min(section.thickness_z_mm, section.thickness_y_mm) <= 0.0:
            # 非正外包络尺寸说明截面数据缺项，因此立即阻止生成正式 include。
            raise ValueError(f"截面 {section.key} 存在非正 TKz/TKy")
        # 剪切修正是有效剪切面积与总面积之比；本模型各均质截面必须落在 (0,1]。
        if not (
            # xz 分量必须严格大于 0 且不得超过未修正总面积对应的上限 1。
            0.0 < section.shear_correction_xz <= 1.0
            # 两个分量必须同时满足范围约束，任一越界都视为截面定义错误。
            and 0.0 < section.shear_correction_xy <= 1.0
        ):
            # 越界值会直接污染 Timoshenko 剪切刚度，因此不允许静默写入 APDL。
            raise ValueError(f"截面 {section.key} 的 TSxz/TSxy 不在 (0,1] 内")
    # 门架 H175 的 local-z 对应 175 mm 截面高度，因此竖向弯曲必须调用 local-y 强轴 Iyy。
    gate_bottom_section = sections["gate_bottom"]
    # Iyy 不大于 Izz 会重现已确认的强弱轴对调，必须在生成阶段硬失败。
    if gate_bottom_section.iyy_mm4 <= gate_bottom_section.izz_mm4:
        # 错误消息明确指出预期轴映射，便于定位未来的截面公式回归。
        raise ValueError("gate_bottom 必须满足 Iyy(竖弯强轴) > Izz(侧弯弱轴)")
    # RHS50×30 的 50 mm 尺寸沿 local-y、30 mm 尺寸沿 local-z，因此 Izz 应大于 Iyy。
    rhs50x30_section = sections["passage_rhs50x30"]
    # 该断言防止把 CAD 的 50/30 朝向与 ASEC 的 local-y/local-z 顺序再次互换。
    if rhs50x30_section.izz_mm4 <= rhs50x30_section.iyy_mm4:
        # 错误消息记录正确的尺寸—惯性映射，禁止依赖材料倍率掩盖方向错误。
        raise ValueError("passage_rhs50x30 必须满足 Izz(local-y=50) > Iyy(local-z=30)")
    return sections


def normalize_passage_section(raw_section: str) -> str:
    """把模块 CSV 的图纸截面字符串映射到稳定标定组名。"""

    normalized = raw_section.strip().replace(" ", "").replace("φ", "Φ")
    mapping = {
        "Φ152×6": "passage_chord152",
        "Φ102×4": "passage_frame102",
        "Φ51×4": "passage_brace51",
        "□50×30×4": "passage_rhs50x30",
    }
    if normalized not in mapping:
        raise ValueError(f"横通道出现未定义截面：{raw_section!r}")
    return mapping[normalized]


def transform_module_point(point: Vec3, offset_mm: float, mirrored: bool) -> Vec3:
    """把单模块局部节点变换到 49.72 m 完整横通道局部坐标。"""

    if not mirrored:
        return Vec3(point.x + offset_mm, point.y, point.z)
    # 右尾段绕局部 Z 轴旋转 180° 后平移，实现 x'=49720-x、y'=1500-y。
    return Vec3(offset_mm - point.x, PASSAGE_WIDTH_MM - point.y, point.z)


def build_passage_template(
    module_directory: Path,
    gate_bottom_rope_x_coordinates_mm: Sequence[float],
) -> PassageTemplate:
    """读取三类模块 CSV，装配、求交、拆分并去除 100 mm 搭接重复边。

    参数：
        module_directory: ``cross_passage_local_coordinates`` 目录。
        gate_bottom_rope_x_coordinates_mm: 两幅猫道共 32 根底索的 CAD 横桥向
            ``x`` 坐标。生成器会把两条横通道顶弦在这些坐标处显式拆分，以便
            dedicated gate 下横梁分段节点逐点连接，而不是只连接通道最外端。

    返回：
        只保留实际参与杆件的节点和唯一子杆件的 ``PassageTemplate``。
    """

    raw_edges: list[RawPassageEdge] = []
    source_points: dict[tuple[int, int, int], tuple[Vec3, set[str]]] = {}

    # 六个模块按装配顺序读取；同一 middle 模块会在三个偏移位置重复实例化。
    for instance_name, module_key, offset_mm, mirrored in MODULE_PLACEMENTS:
        node_rows = read_csv_rows(module_directory / f"{module_key}_nodes.csv")
        edge_rows = read_csv_rows(module_directory / f"{module_key}_edges.csv")
        node_lookup: dict[str, Vec3] = {}

        # O000 只是包围盒基准角，不是实体中心线节点，因此明确跳过。
        for row in node_rows:
            source_node_id = row["节点ID"].strip()
            if source_node_id == "O000":
                continue
            module_point = Vec3(float(row["X_mm"]), float(row["Y_mm"]), float(row["Z_mm"]))
            assembled_point = transform_module_point(module_point, offset_mm, mirrored)
            node_lookup[source_node_id] = assembled_point
            key = coordinate_key(assembled_point)
            if key not in source_points:
                source_points[key] = (assembled_point, set())
            source_points[key][1].add(f"{instance_name}:{source_node_id}")

        # 每根 CSV 杆件同时用节点 ID 与显式端点坐标校核，防止表格列错位。
        for row in edge_rows:
            start_id = row["起点ID"].strip()
            end_id = row["终点ID"].strip()
            if start_id not in node_lookup or end_id not in node_lookup:
                raise ValueError(f"{module_key} 杆件 {row['杆件ID']} 引用了不存在节点")
            start = node_lookup[start_id]
            end = node_lookup[end_id]
            csv_start = transform_module_point(
                Vec3(float(row["X1_mm"]), float(row["Y1_mm"]), float(row["Z1_mm"])),
                offset_mm,
                mirrored,
            )
            csv_end = transform_module_point(
                Vec3(float(row["X2_mm"]), float(row["Y2_mm"]), float(row["Z2_mm"])),
                offset_mm,
                mirrored,
            )
            if start.distance_to(csv_start) > GEOMETRY_TOL_MM or end.distance_to(csv_end) > GEOMETRY_TOL_MM:
                raise ValueError(f"{module_key} 杆件 {row['杆件ID']} 的节点坐标与端点列不一致")
            raw_edges.append(
                RawPassageEdge(
                    start=start,
                    end=end,
                    section_key=normalize_passage_section(row["截面"]),
                    member=row["类别"].strip(),
                    source_member_id=f"{instance_name}:{row['杆件ID'].strip()}",
                )
            )

    # 横通道局部 q 坐标从 CAD x=-24860 mm 起算，因此 q=CAD_x+24860。
    # 两条顶弦分别位于局部 r=0 和 r=1500、z=1700。将全部 32 根底索的横向
    # 交点注入节点池后，长主弦会在拆分阶段形成 64 个真实接口节点。
    unique_rope_x = sorted(set(float(value) for value in gate_bottom_rope_x_coordinates_mm))
    if len(unique_rope_x) != 32:
        raise ValueError(f"底索横向接口坐标为 {len(unique_rope_x)} 个，预期两幅共 32 个")
    for cad_x in unique_rope_x:
        local_q = cad_x + PASSAGE_CONTROL_LENGTH_MM / 2.0
        if not (-GEOMETRY_TOL_MM <= local_q <= PASSAGE_CONTROL_LENGTH_MM + GEOMETRY_TOL_MM):
            raise ValueError(f"底索 CAD x={cad_x:.3f} mm 超出横通道控制宽度")
        for local_r in (0.0, PASSAGE_WIDTH_MM):
            interface_point = Vec3(local_q, local_r, PASSAGE_HEIGHT_MM)
            key = coordinate_key(interface_point)
            if key not in source_points:
                source_points[key] = (interface_point, set())
            source_points[key][1].add(
                f"DEDICATED_GATE_TOP_CHORD_INTERFACE:CAD_X={cad_x:.3f}:R={local_r:.0f}"
            )

    # points 先纳入全部图纸节点；随后补充没有在源 CSV 中显式列出的真实杆件交点。
    points = [value[0] for value in source_points.values()]
    roles = ["|".join(sorted(value[1])) for value in source_points.values()]
    point_index_by_key = {coordinate_key(point): index for index, point in enumerate(points)}
    intersection_points_added = 0

    # 两两检查非相邻原始杆件。若三维最近距离小于容差且交点落在线段内部，
    # 将交点加入节点池；后续每根长杆都会在该点拆分。
    for first_index, first_edge in enumerate(raw_edges):
        for second_edge in raw_edges[first_index + 1 :]:
            # 平行/共线杆件不在两两求交阶段补点。模块 100 mm 搭接属于共线重叠，
            # 其全部端点已在 source_points 中，随后“所有点投影到每根杆”步骤足以
            # 完整拆分；若在此使用最近点算法，会在重叠区任意位置生成伪交点。
            first_direction = first_edge.end - first_edge.start
            second_direction = second_edge.end - second_edge.start
            parallel_measure = first_direction.cross(second_direction).norm()
            if parallel_measure <= (
                1.0e-10 * first_direction.norm() * second_direction.norm()
            ):
                continue
            s_value, t_value, closest_1, closest_2 = closest_points_on_segments(
                first_edge.start,
                first_edge.end,
                second_edge.start,
                second_edge.end,
            )
            if closest_1.distance_to(closest_2) > GEOMETRY_TOL_MM:
                continue
            # 端点交会已经由源节点池表示；只有至少一根杆件内部的新点才需补充。
            if not (
                GEOMETRY_TOL_MM < s_value < 1.0 - GEOMETRY_TOL_MM
                or GEOMETRY_TOL_MM < t_value < 1.0 - GEOMETRY_TOL_MM
            ):
                continue
            intersection = (closest_1 + closest_2) * 0.5
            key = coordinate_key(intersection)
            if key not in point_index_by_key:
                point_index_by_key[key] = len(points)
                points.append(intersection)
                roles.append(
                    f"AUTO_INTERSECTION:{first_edge.source_member_id}|{second_edge.source_member_id}"
                )
                intersection_points_added += 1

    # 每根长杆在所有共线节点处拆分。deduplicated_edges 以无向节点对为键，
    # 从而把左右尾段 100 mm 搭接区的重复线段只保留一份。
    deduplicated_edges: dict[
        tuple[int, int], tuple[int, int, str, str, str]
    ] = {}
    duplicate_subedges_removed = 0
    for raw_edge in raw_edges:
        points_on_edge: list[tuple[float, int]] = []
        for point_index, point in enumerate(points):
            parameter, distance = point_segment_parameter(point, raw_edge.start, raw_edge.end)
            if -GEOMETRY_TOL_MM <= parameter <= 1.0 + GEOMETRY_TOL_MM and distance <= GEOMETRY_TOL_MM:
                points_on_edge.append((max(0.0, min(1.0, parameter)), point_index))
        points_on_edge.sort(key=lambda pair: pair[0])

        # 参数去重避免量化后同一空间点在排序列表中重复出现。
        ordered_unique_indices: list[int] = []
        for _, point_index in points_on_edge:
            if not ordered_unique_indices or point_index != ordered_unique_indices[-1]:
                ordered_unique_indices.append(point_index)
        if len(ordered_unique_indices) < 2:
            raise ValueError(f"杆件 {raw_edge.source_member_id} 拆分后少于两个节点")

        for n1_index, n2_index in zip(ordered_unique_indices, ordered_unique_indices[1:]):
            if points[n1_index].distance_to(points[n2_index]) <= GEOMETRY_TOL_MM:
                continue
            undirected_key = tuple(sorted((n1_index, n2_index)))
            candidate = (
                n1_index,
                n2_index,
                raw_edge.section_key,
                raw_edge.member,
                raw_edge.source_member_id,
            )
            if undirected_key in deduplicated_edges:
                previous = deduplicated_edges[undirected_key]
                if previous[2] != raw_edge.section_key:
                    raise ValueError(
                        "同一搭接子边出现不同截面："
                        f"{previous[4]}={previous[2]}，{raw_edge.source_member_id}={raw_edge.section_key}"
                    )
                duplicate_subedges_removed += 1
                continue
            deduplicated_edges[undirected_key] = candidate

    # 删除只作为模块说明、未参与任何最终子杆件的源节点，保证最终模板无孤立点。
    used_old_indices = sorted(
        {index for edge in deduplicated_edges.values() for index in (edge[0], edge[1])}
    )
    old_to_new = {old_index: new_index for new_index, old_index in enumerate(used_old_indices)}
    final_points = [points[old_index] for old_index in used_old_indices]
    final_roles = [roles[old_index] for old_index in used_old_indices]
    final_edges = [
        (old_to_new[edge[0]], old_to_new[edge[1]], edge[2], edge[3], edge[4])
        for edge in deduplicated_edges.values()
    ]

    # 用无向图检查模板是否为单一连通体；完整横通道若不连通，将在装配后产生机构。
    adjacency: dict[int, set[int]] = defaultdict(set)
    for n1_index, n2_index, _, _, _ in final_edges:
        adjacency[n1_index].add(n2_index)
        adjacency[n2_index].add(n1_index)
    represented_components = count_graph_components(set(range(len(final_points))), adjacency)
    if represented_components != 1:
        raise ValueError(f"横通道模板拆分后存在 {represented_components} 个连通分量，预期 1")

    # 左右端必须各保留三个主弦端点，供 dedicated gate 三角接口连接。
    for end_x in (0.0, PASSAGE_CONTROL_LENGTH_MM):
        end_nodes = [point for point in final_points if abs(point.x - end_x) <= GEOMETRY_TOL_MM]
        if len(end_nodes) != 3:
            raise ValueError(f"横通道 x={end_x:.0f} mm 端面节点数为 {len(end_nodes)}，预期 3")

    return PassageTemplate(
        points=final_points,
        point_roles=final_roles,
        edges=final_edges,
        intersection_points_added=intersection_points_added,
        duplicate_subedges_removed=duplicate_subedges_removed,
        represented_components=represented_components,
    )


def count_graph_components(nodes: set[int], adjacency: dict[int, set[int]]) -> int:
    """返回给定无向图的连通分量数。"""

    remaining = set(nodes)
    component_count = 0
    while remaining:
        component_count += 1
        seed = next(iter(remaining))
        stack = [seed]
        remaining.remove(seed)
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return component_count


def interpolate_bottom_profile(
    profile: Sequence[tuple[float, float]],
    target_y_mm: float,
) -> tuple[float, float]:
    """在底索 Y-Z 折线上插值高程，并返回局部顺桥坡度角。"""

    for (y0, z0), (y1, z1) in zip(profile, profile[1:]):
        if y0 <= target_y_mm <= y1:
            if abs(y1 - y0) <= 1.0e-12:
                raise ValueError("底索剖面存在重复 Y 节点，无法定义局部坡度")
            ratio = (target_y_mm - y0) / (y1 - y0)
            z_value = z0 + ratio * (z1 - z0)
            slope_degree = math.degrees(math.atan2(z1 - z0, y1 - y0))
            return z_value, slope_degree
    raise ValueError(f"站位 Y={target_y_mm:.3f} mm 超出底索剖面范围")


def derive_dedicated_station_rows(geometry_directory: Path) -> list[dict[str, str]]:
    """从权威 MCT gate 荷载 ``-21.556 kN`` 自动识别 21 个 dedicated station。

    该数值等于每幅“门架导轮组 9.196 kN + 横通道三角门架 12.36 kN”，
    因而比旧的图纸链距比例映射更能直接指向 MCT 中真实建模站位。
    """

    load_rows = read_csv_rows(geometry_directory / "authoritative_mct_deadload_v1_conload_mapping.csv")
    node_rows = read_csv_rows(geometry_directory / "nodes.csv")
    gate_station_rows = read_csv_rows(geometry_directory / "variable_height_gate_stations.csv")
    nodes_by_id = {int(row["node_id"]): row for row in node_rows}
    cw1_gate_rows = [row for row in gate_station_rows if int(row["catwalk"]) == 1]

    # 每个 MCT 节点在 6 根门架索上重复出现；按 mct_node 去重后应恰为 21 处。
    unique_candidates: dict[int, dict[str, str]] = {}
    for row in load_rows:
        if row["subsystem"] != "gate" or int(row["catwalk"]) != 1:
            continue
        if abs(float(row["mct_total_fz_kn_per_catwalk"]) + 21.556) > 1.0e-6:
            continue
        unique_candidates.setdefault(int(row["mct_node"]), row)
    if len(unique_candidates) != 21:
        raise ValueError(f"权威荷载映射识别到 {len(unique_candidates)} 个横通道门架站位，预期 21")

    # CW1 第 1 根底索用于计算站位处坡度；全部底索在 Y-Z 立面共享同一线形。
    bottom_profile = sorted(
        (
            float(row["y_mm"]),
            float(row["z_mm"]),
        )
        for row in node_rows
        if row["rope_name"] == "CW1_BOTTOM_PHI50_01"
    )

    resolved: list[dict[str, str]] = []
    for mct_node, mapping_row in unique_candidates.items():
        source_node = nodes_by_id[int(mapping_row["ansys_node"])]
        load_station_y = float(source_node["y_mm"])
        nearest_gate = min(
            cw1_gate_rows,
            key=lambda row: abs(float(row["top_station_y_mm"]) - load_station_y),
        )
        gate_index = int(nearest_gate["gate_index"])
        gate_center_y = float(nearest_gate["station_y_mm"])
        _, slope_degree = interpolate_bottom_profile(bottom_profile, gate_center_y)
        resolved.append(
            {
                "name": "",  # 排序后再按北至南顺序写 H01~H21。
                "span": "",  # 跨别将在排序后按真实 Y 分区补充。
                "gate_index": str(gate_index),
                "cw1_gate_name": f"CW1_GATE_{gate_index:02d}",
                "cw2_gate_name": f"CW2_GATE_{gate_index:02d}",
                "station_y_mm": f"{gate_center_y:.12f}",
                "top_chord_reference_z_mm": f"{float(nearest_gate['bottom_rope_z_mm']):.12f}",
                "local_slope_degree": f"{slope_degree:.12f}",
                "source_mct_gate_node": str(mct_node),
                "source_gate_total_fz_kn": "-21.556",
                "source_load_station_y_mm": f"{load_station_y:.12f}",
                "gate_to_load_y_offset_mm": f"{gate_center_y - load_station_y:.12f}",
            }
        )

    resolved.sort(key=lambda row: float(row["station_y_mm"]))
    for index, row in enumerate(resolved, start=1):
        y_value = float(row["station_y_mm"])
        row["name"] = f"H{index:02d}"
        # 跨界采用当前 MCT 控制点；这里只用于组件分组，不参与几何定位。
        if y_value < 696_909.0:
            row["span"] = "north_side"
        elif y_value < 2_998_909.0:
            row["span"] = "main_span"
        elif y_value < 3_724_185.0:
            row["span"] = "south_side"
        else:
            row["span"] = "south_aux"
    return resolved


def write_station_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    """把 resolved dedicated station 以稳定列序写入外部输入 CSV。"""

    fieldnames = [
        "name",
        "span",
        "gate_index",
        "cw1_gate_name",
        "cw2_gate_name",
        "station_y_mm",
        "top_chord_reference_z_mm",
        "local_slope_degree",
        "source_mct_gate_node",
        "source_gate_total_fz_kn",
        "source_load_station_y_mm",
        "gate_to_load_y_offset_mm",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def normalize_external_station_rows(raw_rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """把两种允许的外部 dedicated station 表头统一为生成器内部格式。

    支持：

    1. builder 自身的精简/解析格式（含 ``name``、``cw1_gate_name`` 等列）；
    2. V2.0 audit 目录的权威质量站位总表（含 ``passage_id``、
       ``ansys_gate_centerline_y_mm``、``bottom_central_chord_slope_degree`` 等列）。

    第二种格式是当前首选来源，因为它同时保留 MCT 节点、旧比例站位误差和质量
    分项证据。横通道中心采用 gate centerline Y，顶弦参考高程采用 dedicated
    bottom-rope Z，纵向旋转采用左右底索段坡度的中心值。
    """

    if not raw_rows:
        raise ValueError("dedicated station CSV 为空")
    first_columns = set(raw_rows[0])
    if {
        "name",
        "gate_index",
        "cw1_gate_name",
        "cw2_gate_name",
        "station_y_mm",
        "top_chord_reference_z_mm",
        "local_slope_degree",
    }.issubset(first_columns):
        # 返回逐行复制，避免后续补充/校验意外修改调用者持有的原字典。
        return [dict(row) for row in raw_rows]

    authoritative_required = {
        "passage_id",
        "span",
        "gate_index",
        "gate_name_cw1",
        "gate_name_cw2",
        "mct_gate_node",
        "ansys_gate_centerline_y_mm",
        "ansys_passage_top_chord_reference_z_mm",
        "bottom_central_chord_slope_degree",
        "ansys_gate_top_station_y_mm",
        "gate_mct_combined_weight_kn_per_catwalk",
    }
    if not authoritative_required.issubset(first_columns):
        missing = sorted(authoritative_required - first_columns)
        raise ValueError(f"外部 dedicated station CSV 表头不受支持，缺少列：{missing}")

    normalized: list[dict[str, str]] = []
    for row in raw_rows:
        gate_center_y = row["ansys_gate_centerline_y_mm"]
        gate_top_y = row["ansys_gate_top_station_y_mm"]
        normalized.append(
            {
                "name": row["passage_id"],
                "span": row["span"],
                "gate_index": row["gate_index"],
                "cw1_gate_name": row["gate_name_cw1"],
                "cw2_gate_name": row["gate_name_cw2"],
                "station_y_mm": gate_center_y,
                "top_chord_reference_z_mm": row[
                    "ansys_passage_top_chord_reference_z_mm"
                ],
                "local_slope_degree": row["bottom_central_chord_slope_degree"],
                "source_mct_gate_node": row["mct_gate_node"],
                "source_gate_total_fz_kn": row[
                    "gate_mct_combined_weight_kn_per_catwalk"
                ],
                "source_load_station_y_mm": gate_top_y,
                "gate_to_load_y_offset_mm": (
                    f"{float(gate_center_y) - float(gate_top_y):.12f}"
                ),
            }
        )
    normalized.sort(key=lambda row: float(row["station_y_mm"]))
    return normalized


def read_gate_bottom_rope_x_coordinates(geometry_directory: Path) -> list[float]:
    """从第一品两幅门架提取 32 根底索的 CAD 横桥向坐标。

    所有 71 个站位共享相同横向布置，只读取 CW1/CW2_GATE_01 可避免重复值；
    数量和唯一性检查能及时发现门架 CSV 版本发生变化。
    """

    coupling_rows = read_csv_rows(geometry_directory / "gate_rope_couplings.csv")
    coordinates = [
        float(row["rope_x_mm"])
        for row in coupling_rows
        if row["gate_name"] in {"CW1_GATE_01", "CW2_GATE_01"}
        and row["family"] == "BOTTOM_PHI50"
    ]
    unique_coordinates = sorted(set(coordinates))
    if len(coordinates) != 32 or len(unique_coordinates) != 32:
        raise ValueError(
            f"代表门架底索横向坐标行数/唯一数为 {len(coordinates)}/{len(unique_coordinates)}，预期 32/32"
        )
    return unique_coordinates


def validate_station_rows(rows: Sequence[dict[str, str]]) -> None:
    """校验外部站位表数量、名称、门架映射和 Y 单调性。"""

    if len(rows) != 21:
        raise ValueError(f"dedicated station CSV 含 {len(rows)} 行，预期 21")
    names = [row["name"].strip() for row in rows]
    if names != [f"H{index:02d}" for index in range(1, 22)]:
        raise ValueError("dedicated station 名称必须按 Y 递增严格为 H01~H21")
    gate_indices = [int(row["gate_index"]) for row in rows]
    if len(set(gate_indices)) != 21:
        raise ValueError("dedicated station 的 gate_index 必须互不重复")
    y_values = [float(row["station_y_mm"]) for row in rows]
    if any(next_y <= current_y for current_y, next_y in zip(y_values, y_values[1:])):
        raise ValueError("dedicated station 的 station_y_mm 必须严格递增")
    for row in rows:
        expected_index = int(row["gate_index"])
        if row["cw1_gate_name"].strip() != f"CW1_GATE_{expected_index:02d}":
            raise ValueError(f"{row['name']} 的 CW1 门架名与 gate_index 不一致")
        if row["cw2_gate_name"].strip() != f"CW2_GATE_{expected_index:02d}":
            raise ValueError(f"{row['name']} 的 CW2 门架名与 gate_index 不一致")


class ModelBuilder:
    """集中管理新增节点、物理梁、MPC184 刚性连接和 MAPDL 组件。

    参数：
        sections: 六个稳定截面定义。
        node_start: 第一个可用新增节点号。
        element_start: 第一个可用新增单元号。

    所有新建梁在加入单元时自动建立显式方向节点，避免各向异性截面依赖 MAPDL
    默认方向。方向节点仅定义局部截面方向，不参与结构连通图。
    """

    def __init__(
        self,
        sections: dict[str, SectionDef],
        node_start: int,
        element_start: int,
    ) -> None:
        self.sections = sections
        self.next_node_id = node_start
        self.next_element_id = element_start
        self.nodes: list[NodeRecord] = []
        self.elements: list[ElementRecord] = []
        # rigid_connections 保存待编号或已编号的 MPC184 刚性梁，且不混入物理梁体积台账。
        self.rigid_connections: list[RigidConnectionRecord] = []
        self.node_by_id: dict[int, NodeRecord] = {}
        self.element_by_id: dict[int, ElementRecord] = {}
        self.node_groups: dict[str, set[int]] = defaultdict(set)
        self.element_groups: dict[str, set[int]] = defaultdict(set)

    def add_node(
        self,
        cad_point: Vec3,
        system: str,
        assembly_name: str,
        role: str,
        source_local_coord: str,
        *,
        is_orientation: bool = False,
    ) -> int:
        """新增一个节点，返回稳定递增的 MAPDL 节点号。"""

        node_id = self.next_node_id
        self.next_node_id += 1
        record = NodeRecord(
            apdl_node_id=node_id,
            apdl_point=cad_to_apdl(cad_point),
            cad_point=cad_point,
            system=system,
            assembly_name=assembly_name,
            role=role,
            source_local_coord=source_local_coord,
            is_orientation=is_orientation,
        )
        self.nodes.append(record)
        self.node_by_id[node_id] = record
        return node_id

    def add_orientation_node(
        self,
        n1: int,
        n2: int,
        system: str,
        assembly_name: str,
        member: str,
    ) -> int:
        """为一根 BEAM188 创建不共线的显式方向节点。

        ANSYS 官方定义 I-J-K 平面包含梁局部 x、z 轴，因此 K 节点控制的是局部 z
        而不是局部 y。梁非竖直时令 local-z 接近全局 MAPDL Z；梁接近竖直时改用
        全局 MAPDL X，防止方向向量与梁轴平行。最后把参考向量投影到梁轴法平面。
        """

        # start_apdl 是梁 I 节点的全局 MAPDL 坐标，作为方向节点向量的共同起点。
        start_apdl = self.node_by_id[n1].apdl_point
        # end_apdl 是梁 J 节点的全局 MAPDL 坐标，与 I 节点共同定义 local-x 正向。
        end_apdl = self.node_by_id[n2].apdl_point
        # axis 是从 I 指向 J 的单位 local-x；归一化同时拒绝零长度梁。
        axis = (end_apdl - start_apdl).normalized()
        # 默认参考 (0,0,1) 表示全局竖向，使横梁和横通道纵杆的 local-z 对应真实截面高度。
        local_z_reference = Vec3(0.0, 0.0, 1.0)
        # 0.95 是方向余弦阈值；超过该值表示梁轴距竖直方向小于约 18.2°，投影会病态。
        if abs(axis.dot(local_z_reference)) > 0.95:
            # 竖杆改用全局 X 的单位向量 (1,0,0)，其方形/圆形截面对绕轴滚转不敏感。
            local_z_reference = Vec3(1.0, 0.0, 0.0)
        # 从参考向量扣除沿 local-x 的分量，得到严格位于梁轴法平面的 local-z 单位向量。
        local_z_direction = (
            # 正交投影公式为 r_perp=r-x*(x·r)，其中 x 已归一化。
            local_z_reference - axis * axis.dot(local_z_reference)
        ).normalized()
        # 100 mm 仅是无物理自由度的 K 节点偏置长度；其正方向明确等于目标 local-z。
        orientation_apdl = start_apdl + local_z_direction * 100.0
        # add_node 接收 CAD 坐标，因此对 MAPDL 变换作逆变换：CAD=( -Y, X, Z )。
        orientation_cad = Vec3(-orientation_apdl.y, orientation_apdl.x, orientation_apdl.z)
        return self.add_node(
            orientation_cad,
            system,
            assembly_name,
            role=f"orientation_for_{member}",
            source_local_coord="BEAM188 orientation node; not a physical joint",
            is_orientation=True,
        )

    def add_element(
        self,
        n1: int,
        n2: int,
        section_key: str,
        system: str,
        assembly_name: str,
        member: str,
        source_member_id: str,
    ) -> int:
        """新增一根有限刚度 BEAM188，并自动创建方向节点。"""

        if section_key not in self.sections:
            raise KeyError(f"未定义截面组 {section_key}")
        if n1 == n2:
            raise ValueError(f"{assembly_name}/{member} 的两个端节点相同")
        start = self.node_by_id[n1].apdl_point
        end = self.node_by_id[n2].apdl_point
        length = start.distance_to(end)
        if length <= GEOMETRY_TOL_MM:
            raise ValueError(f"{assembly_name}/{member} 出现零长度梁")
        orientation_node = self.add_orientation_node(n1, n2, system, assembly_name, member)
        element_id = self.next_element_id
        self.next_element_id += 1
        record = ElementRecord(
            apdl_elem_id=element_id,
            n1=n1,
            n2=n2,
            orientation_node=orientation_node,
            system=system,
            assembly_name=assembly_name,
            member=member,
            section_key=section_key,
            source_member_id=source_member_id,
            length_mm=length,
        )
        self.elements.append(record)
        self.element_by_id[element_id] = record
        self.element_groups[SECTION_COMPONENT_NAMES[section_key]].add(element_id)
        return element_id

    def add_rigid_connection(
        self,
        master_node: int,
        slave_node: int,
        source_semantics: str,
        system: str,
        assembly_name: str,
        reason: str,
        *,
        slave_cad_point: Vec3 | None = None,
    ) -> None:
        """登记一个待编号且保留 UXYZ/ALL 运动学差异的 MPC184 连接。

        参数：
            master_node: 固定写入 ``EN`` 命令 I 端的主节点号。
            slave_node: 固定写入 ``EN`` 命令 J 端的从节点号。
            source_semantics: 迁移前 CERIG 的 UXYZ 或 ALL 语义标签。
            system: gate、passage_interface 等结构系统标签。
            assembly_name: 当前连接所属的门架或横通道品名。
            reason: 连接对应的物理接口和建模目的。
            slave_cad_point: UXYZ 从节点的 CAD 坐标；用于创建共点零质量辅助节点，ALL 必须省略。
        返回：无；单元号由 ``finalize_rigid_connection_ids`` 统一分配。
        """

        # 只接受现有审计已经闭合的两类来源语义，防止未验证的新运动学静默进入模型。
        if source_semantics not in {"UXYZ", "ALL"}:
            # 非法标签必须停止生成，不能退化为任意刚性连接。
            raise ValueError(f"不允许的刚性连接来源语义：{source_semantics}")
        # master 与 slave 相同会生成零长度 MPC184，既无物理意义也会污染元素计数。
        if master_node == slave_node:
            # 发现同节点连接时立即失败，避免把拓扑错误留给 MAPDL 求解阶段。
            raise ValueError("MPC184 连接的 master 与 slave 不得相同")
        # UXYZ 必须提供从节点坐标，才能把偏置刚臂末端放到与原索节点严格共点的位置。
        if source_semantics == "UXYZ" and slave_cad_point is None:
            # 缺少坐标时无法构造“刚臂偏置+共点三平移 general joint”，因此必须停止生成。
            raise ValueError("UXYZ 连接必须提供 slave_cad_point")
        # ALL 直接使用原 master/slave 两节点，不允许额外传入会被静默忽略的坐标。
        if source_semantics == "ALL" and slave_cad_point is not None:
            # 多余坐标通常表示调用者误把 ALL 接口当成 UXYZ，必须显式拒绝。
            raise ValueError("ALL 连接不得提供 slave_cad_point")
        # UXYZ 先创建与原 slave 共点的零质量辅助节点；ALL 不需要辅助节点。
        offset_node_id = (
            # add_node 使用 CAD 坐标并自动转换到 MAPDL 坐标；is_orientation=True 使质量脚本排除该节点。
            self.add_node(
                # slave_cad_point 已由上方 UXYZ 硬检查排除 None。
                slave_cad_point,
                # system 保持原连接系统标签，便于审计定位辅助节点来源。
                system,
                # assembly_name 保持原装配名，便于逐品追溯。
                assembly_name,
                # role 明确该节点只承担 UXYZ 偏置运动学，不代表实体或质量位置。
                role="uxyz_offset_auxiliary",
                # source_local_coord 记录共点原 slave 节点号，便于坐标闭合复核。
                source_local_coord=f"coincident_with_original_slave={slave_node}",
                # is_orientation=True 复用现有“零质量、非物理节点”过滤契约。
                is_orientation=True,
            )
            # 非 UXYZ 连接不创建辅助节点并保持 None 哨兵。
            if source_semantics == "UXYZ"
            # else 分支对应 ALL 六自由度刚接。
            else None
        )
        # 新记录先用 None 标记尚未分配单元号；全部 BEAM188 完成后再统一顺排编号。
        self.rigid_connections.append(
            RigidConnectionRecord(
                # None 表示该记录仍处于登记阶段，写文件前必须完成编号。
                apdl_elem_id=None,
                # offset_elem_id 在物理梁完成后与主 MPC184 单元一起稳定编号。
                offset_elem_id=None,
                # offset_node_id 保存 UXYZ 共点辅助节点号，ALL 则为 None。
                offset_node_id=offset_node_id,
                # master_node 作为固定 I 端保存，便于审计星形连接的公共主节点。
                master_node=master_node,
                # slave_node 作为固定 J 端保存，保持迁移前主从台账语义。
                slave_node=slave_node,
                # source_semantics 决定写出组合式 UXYZ 或单个 ALL rigid beam，禁止再统一刚接。
                source_semantics=source_semantics,
                # system 保存连接所在结构系统，供生成摘要和问题追溯使用。
                system=system,
                # assembly_name 保存具体品名，供每品连通图校验使用。
                assembly_name=assembly_name,
                # reason 保存物理接口说明，明确机械替换不等于获得了连接详图源证。
                reason=reason,
            )
        )

    def finalize_rigid_connection_ids(self) -> None:
        """在全部物理梁完成后连续分配 MPC184 单元号并建立组件。

        参数：无；使用 ``next_element_id`` 作为首个可用刚性单元号。
        返回：无；成功后每条记录均有唯一正整数单元号，且 ``next_element_id`` 指向下一空号。
        """

        # 重复执行会改变编号或重复登记组件，因此只允许所有记录都处于未编号状态时调用一次。
        if any(connection.apdl_elem_id is not None for connection in self.rigid_connections):
            # 已编号记录说明调用顺序错误，必须停止而不是覆盖原有稳定编号。
            raise RuntimeError("MPC184 刚性连接单元号已经分配，禁止重复编号")
        # 按登记顺序稳定编号，使同一输入数据在不同机器上生成完全一致的元素号。
        for connection in self.rigid_connections:
            # UXYZ 先分配 master→辅助节点的 rigid beam 单元号，ALL 不进入该分支。
            if connection.source_semantics == "UXYZ":
                # offset_node_id 应已在登记阶段创建；None 表示调用契约被破坏。
                if connection.offset_node_id is None:
                    # 缺失辅助节点不能写出保持偏置转动的 UXYZ 运动学。
                    raise RuntimeError("UXYZ 连接缺少共点辅助节点")
                # 当前 next_element_id 分配给 UXYZ 偏置 rigid beam。
                connection.offset_elem_id = self.next_element_id
                # 偏置 rigid beam 与主 general joint 一并加入 MPC184 组件。
                self.element_groups[MPC_CONNECTION_COMPONENT_NAME].add(self.next_element_id)
                # 单元号递增 1，为当前 UXYZ 的共点 general joint 保留下一编号。
                self.next_element_id += 1
            # 当前 next_element_id 是 ALL rigid beam 或 UXYZ general joint 的主单元号。
            connection.apdl_elem_id = self.next_element_id
            # 将当前刚性单元号登记到独立组件，便于 MAPDL 端计数和选择。
            self.element_groups[MPC_CONNECTION_COMPONENT_NAME].add(self.next_element_id)
            # 单元号递增 1，确保下一条连接不与当前连接或物理梁冲突。
            self.next_element_id += 1


def derive_beam_local_axes(
    builder: ModelBuilder,
    element: ElementRecord,
) -> tuple[Vec3, Vec3, Vec3]:
    """依据 ANSYS BEAM188 的 I/J/K 定义返回 ``(local_x, local_y, local_z)``。

    参数：
        builder: 持有 I、J、K 节点全局 MAPDL 坐标的模型构建器。
        element: 需要计算局部轴的 BEAM188 单元台账记录。

    返回：
        三个右手正交单位向量；local-x 从 I 指向 J，local-z 是 I→K 在 local-x
        法平面内的投影，local-y 由 ``local-z × local-x`` 得到。

    约束：
        K 节点只定义初始方向，不是物理节点；若 I/J/K 退化或正交性失效，本函数
        立即抛错，禁止把不确定的截面滚转写入正式模型。
    """

    # start_apdl 读取 I 节点的全局 MAPDL 坐标，作为梁轴和方向向量共同起点。
    start_apdl = builder.node_by_id[element.n1].apdl_point
    # end_apdl 读取 J 节点的全局 MAPDL 坐标，与 I 节点共同定义 local-x。
    end_apdl = builder.node_by_id[element.n2].apdl_point
    # orientation_apdl 读取 K 节点坐标；其自由度不进入结构，仅用于初始截面定向。
    orientation_apdl = builder.node_by_id[element.orientation_node].apdl_point
    # local_x 是 I→J 的单位向量；normalized 会拒绝任何意外零长度单元。
    local_x = (end_apdl - start_apdl).normalized()
    # i_to_k 是 I→K 原始向量；该向量允许含 local-x 分量，但不得与梁轴共线。
    i_to_k = orientation_apdl - start_apdl
    # local_z_raw 按官方定义取 I→K 在 local-x 法平面上的正交投影。
    local_z_raw = i_to_k - local_x * local_x.dot(i_to_k)
    # local_z 归一化后给出 I-J-K 平面内、垂直 local-x 的截面 z 正向。
    local_z = local_z_raw.normalized()
    # local_y=local-z×local-x 保证 local-x×local-y=local-z，形成右手正交基。
    local_y = local_z.cross(local_x).normalized()
    # 1e-10 是单位向量点积的数值容差；超限表示节点坐标或叉乘规则发生回归。
    orthogonality_tolerance = 1.0e-10
    # 三个点积都应为 0；任一超限都意味着局部轴不再正交。
    if max(
        # local-x 与 local-y 的点积检查第一组正交关系。
        abs(local_x.dot(local_y)),
        # local-x 与 local-z 的点积检查方向节点是否正确投影。
        abs(local_x.dot(local_z)),
        # local-y 与 local-z 的点积检查叉积生成轴是否保持正交。
        abs(local_y.dot(local_z)),
    ) > orthogonality_tolerance:
        # 报错包含单元号，便于从逐件台账直接定位退化来源。
        raise ValueError(f"BEAM188 单元 {element.apdl_elem_id} 的 I/J/K 局部轴不正交")
    # handedness 应为 +1；它用于排除 local-y 叉积顺序写反造成的左手坐标系。
    handedness = local_x.cross(local_y).dot(local_z)
    # 右手性与 +1 的偏差采用同一 1e-10 容差，避免容许可见的截面翻转错误。
    if abs(handedness - 1.0) > orthogonality_tolerance:
        # 左手或退化坐标系会交换内力符号，因此在生成阶段直接失败。
        raise ValueError(f"BEAM188 单元 {element.apdl_elem_id} 的局部轴不是右手系")
    # 返回的三个单位轴供全模型硬校验和逐单元 CSV 复用，避免两套方向算法漂移。
    return local_x, local_y, local_z


def validate_anisotropic_section_axes(builder: ModelBuilder) -> dict[str, int]:
    """逐件验证 H175 与 RHS50×30 的 I/J/K 方向和 ASEC 主惯性矩映射。

    参数：
        builder: 已完成全部门架和横通道构建、但尚未写正式 include 的模型构建器。

    返回：
        两类非旋转对称截面的实际覆盖数量，键为稳定 ``section_key``。

    通过规则：
        2698 根 H175 必须满足 local-z=全局竖向、TKz/TKy=175/175、Iyy>Izz；
        2898 根 RHS50×30 必须满足 local-z=全局竖向、TKz/TKy=30/50、Izz>Iyy。
    """

    # global_vertical 是 MAPDL 全局 Z 单位向量，用于检查截面高度轴是否真实竖直。
    global_vertical = Vec3(0.0, 0.0, 1.0)
    # vertical_alignment_min 允许 1e-10 浮点误差，同时拒绝任何可见的截面滚转。
    vertical_alignment_min = 1.0 - 1.0e-10
    # counts 只统计需要方向封板的两类非圆/非方截面，其他旋转对称截面仍校验正交基。
    counts: dict[str, int] = {"gate_bottom": 0, "passage_rhs50x30": 0}
    # 遍历全部 17679 根新增 BEAM188，保证每个 I/J/K 坐标都通过右手正交检查。
    for element in builder.elements:
        # derive_beam_local_axes 会先验证该单元的三轴正交性和右手性。
        _, _, local_z = derive_beam_local_axes(builder, element)
        # section 提供当前单元实际写入 ASEC 的 Iyy/Izz、TKz/TKy 和剪切参数。
        section = builder.sections[element.section_key]
        # H175 门架下横梁是第一类明确受强弱轴影响的非旋转对称构件。
        if element.section_key == "gate_bottom":
            # 每通过一根即累计，最终必须与权威拓扑数量 2698 完全一致。
            counts["gate_bottom"] += 1
            # K 节点定义 local-z；H175 腹板竖直要求 local-z 与全局 Z 平行或反平行。
            if abs(local_z.dot(global_vertical)) < vertical_alignment_min:
                # 任一 H175 滚转偏离竖向都会改变强轴方向，因此禁止继续生成。
                raise ValueError(f"H175 单元 {element.apdl_elem_id} 的 local-z 未对齐全局竖向")
            # Iyy 必须是 175 mm 截面高度产生的强轴惯性矩，Izz 必须是弱轴。
            if section.iyy_mm4 <= section.izz_mm4:
                # 该分支直接阻断已确认的 34.9% 竖弯惯量回归。
                raise ValueError(f"H175 单元 {element.apdl_elem_id} 的 Iyy/Izz 强弱轴写反")
            # 两个 175 mm 是 H175 的总高和总宽；ASEC TKz/TKy 必须与构造尺寸闭合。
            if not (
                # TKz=175 mm 说明 local-z 确实代表腹板高度方向。
                math.isclose(section.thickness_z_mm, 175.0, rel_tol=0.0, abs_tol=1.0e-12)
                # TKy=175 mm 说明 local-y 代表翼缘宽度方向。
                and math.isclose(section.thickness_y_mm, 175.0, rel_tol=0.0, abs_tol=1.0e-12)
            ):
                # 外包络尺寸不符意味着 ASEC 14 项顺序或截面映射发生回归。
                raise ValueError(f"H175 单元 {element.apdl_elem_id} 的 TKz/TKy 不是 175/175 mm")
        # RHS50×30 横通道纵杆是第二类需要逐件确认 50/30 滚转方向的构件。
        elif element.section_key == "passage_rhs50x30":
            # 每通过一根即累计，最终必须与 21 品×单品 138 根=2898 完全一致。
            counts["passage_rhs50x30"] += 1
            # CAD 把 30 mm 作为竖高，因此 K 定义的 local-z 必须与全局 Z 平行或反平行。
            if abs(local_z.dot(global_vertical)) < vertical_alignment_min:
                # 任一 RHS 发生滚转都会把 50 mm 与 30 mm 对调，因此立即失败。
                raise ValueError(f"RHS50×30 单元 {element.apdl_elem_id} 的 local-z 未对齐全局竖向")
            # local-y=50 mm、local-z=30 mm 时 Izz 应为强轴、Iyy 应为弱轴。
            if section.izz_mm4 <= section.iyy_mm4:
                # 该分支防止误把 H175 的交换规则机械套用到真实朝向不同的 RHS。
                raise ValueError(f"RHS50×30 单元 {element.apdl_elem_id} 的 Iyy/Izz 与 50/30 朝向不符")
            # TKz=30 mm、TKy=50 mm 是 FreeCAD 实体 width=50/height=30 的直接数值证据。
            if not (
                # 30 mm 是竖向截面高度，对应 ASEC 第 11 项 TKz。
                math.isclose(section.thickness_z_mm, 30.0, rel_tol=0.0, abs_tol=1.0e-12)
                # 50 mm 是水平截面宽度，对应 ASEC 第 12 项 TKy。
                and math.isclose(section.thickness_y_mm, 50.0, rel_tol=0.0, abs_tol=1.0e-12)
            ):
                # 外包络尺寸不符意味着 50/30 的 local-y/local-z 映射失效。
                raise ValueError(f"RHS50×30 单元 {element.apdl_elem_id} 的 TKz/TKy 不是 30/50 mm")
    # 2698 是当前 142 品门架拆分后 H175 下横梁的权威单元数，少一根或多一根都不闭合。
    if counts["gate_bottom"] != 2698:
        # 数量不闭合说明逐件方向审计没有覆盖正式拓扑的全部 H175。
        raise ValueError(f"H175 方向审计覆盖 {counts['gate_bottom']} 根，预期 2698 根")
    # 2898=21 品横通道×单品 138 根 RHS50×30，是当前模板的权威拓扑数量。
    if counts["passage_rhs50x30"] != 2898:
        # 数量不闭合说明模板或截面映射已变化，必须重新取得 50/30 朝向证据。
        raise ValueError(f"RHS50×30 方向审计覆盖 {counts['passage_rhs50x30']} 根，预期 2898 根")
    # 返回稳定计数，供 JSON/CSV 审计记录本次实际覆盖规模。
    return counts


def projection_onto_line(point: Vec3, line_start: Vec3, line_end: Vec3) -> Vec3:
    """返回 ``point`` 在无限直线 ``line_start-line_end`` 上的正交投影。"""

    direction = line_end - line_start
    denominator = direction.dot(direction)
    if denominator <= 1.0e-20:
        raise ValueError("不能向零长度直线投影")
    parameter = (point - line_start).dot(direction) / denominator
    return line_start + direction * parameter


def split_gate_beam(
    builder: ModelBuilder,
    gate_name: str,
    member_name: str,
    start: Vec3,
    end: Vec3,
    split_descriptors: Sequence[tuple[Vec3, str]],
    section_key: str,
) -> tuple[dict[tuple[int, int, int], int], list[int], list[int]]:
    """在索连接点和立柱投影处拆分一根门架横梁。

    返回：
        ``(coordinate_to_node, physical_node_ids, element_ids)``。
    """

    descriptors: dict[tuple[int, int, int], tuple[Vec3, set[str]]] = {}

    # 两个端点首先加入；随后同坐标的索点/立柱投影会合并角色标签。
    for point, role in [(start, f"{member_name}_endpoint_start"), (end, f"{member_name}_endpoint_end")]:
        descriptors[coordinate_key(point)] = (point, {role})
    for point, role in split_descriptors:
        parameter, distance = point_segment_parameter(point, start, end)
        if not (-GEOMETRY_TOL_MM <= parameter <= 1.0 + GEOMETRY_TOL_MM):
            raise ValueError(f"{gate_name}/{member_name} 的拆分点位于梁段外")
        if distance > GEOMETRY_TOL_MM:
            raise ValueError(f"{gate_name}/{member_name} 的拆分点不在梁轴线上")
        key = coordinate_key(point)
        if key not in descriptors:
            descriptors[key] = (point, set())
        descriptors[key][1].add(role)

    # 按沿梁轴投影参数排序，保证单元顺序从 CSV 起点连续到终点。
    ordered = sorted(
        descriptors.values(),
        key=lambda value: point_segment_parameter(value[0], start, end)[0],
    )
    coordinate_to_node: dict[tuple[int, int, int], int] = {}
    physical_node_ids: list[int] = []
    for point, roles in ordered:
        node_id = builder.add_node(
            point,
            "gate",
            gate_name,
            role="|".join(sorted(roles)),
            source_local_coord=f"CAD=({point.x:.6f},{point.y:.6f},{point.z:.6f})",
        )
        coordinate_to_node[coordinate_key(point)] = node_id
        physical_node_ids.append(node_id)

    element_ids: list[int] = []
    for segment_index, (n1, n2) in enumerate(zip(physical_node_ids, physical_node_ids[1:]), start=1):
        element_ids.append(
            builder.add_element(
                n1,
                n2,
                section_key,
                "gate",
                gate_name,
                member_name,
                source_member_id=f"{gate_name}:{member_name}:segment_{segment_index:02d}",
            )
        )
    return coordinate_to_node, physical_node_ids, element_ids


def build_all_gates(
    builder: ModelBuilder,
    geometry_directory: Path,
) -> dict[str, GateBuildInfo]:
    """构建 142 品有限刚度门架并连接到 44 根原索。"""

    gate_node_rows = read_csv_rows(geometry_directory / "gate_centerline_nodes.csv")
    gate_element_rows = read_csv_rows(geometry_directory / "gate_centerline_elements.csv")
    coupling_rows = read_csv_rows(geometry_directory / "gate_rope_couplings.csv")
    rope_node_rows = read_csv_rows(geometry_directory / "nodes.csv")

    nodes_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    elements_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    couplings_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in gate_node_rows:
        nodes_by_gate[row["gate_name"]].append(row)
    for row in gate_element_rows:
        elements_by_gate[row["gate_name"]].append(row)
    for row in coupling_rows:
        couplings_by_gate[row["gate_name"]].append(row)

    if len(nodes_by_gate) != 142:
        raise ValueError(f"门架中心线表含 {len(nodes_by_gate)} 品，预期 142")
    if set(nodes_by_gate) != set(elements_by_gate) or set(nodes_by_gate) != set(couplings_by_gate):
        raise ValueError("门架节点、单元和索耦合 CSV 的 gate_name 集合不一致")

    # 按 rope_name 建立候选节点列表；每次只在一根指定索上做最近点查找。
    rope_nodes_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rope_node_rows:
        rope_nodes_by_name[row["rope_name"]].append(row)

    gate_infos: dict[str, GateBuildInfo] = {}
    # 按猫道号和门架序号排序，使节点/单元编号稳定，不受 CSV 行顺序影响。
    def gate_sort_key(name: str) -> tuple[int, int]:
        prefix, _, index_text = name.partition("_GATE_")
        return int(prefix.replace("CW", "")), int(index_text)

    for gate_name in sorted(nodes_by_gate, key=gate_sort_key):
        source_nodes = nodes_by_gate[gate_name]
        source_elements = elements_by_gate[gate_name]
        source_couplings = couplings_by_gate[gate_name]
        if len(source_nodes) != 8 or len(source_elements) != 4 or len(source_couplings) != 22:
            raise ValueError(
                f"{gate_name} 数据数量错误：nodes={len(source_nodes)}, "
                f"elements={len(source_elements)}, couplings={len(source_couplings)}"
            )
        roles = {row["role"]: row for row in source_nodes}
        expected_roles = {
            "bottom_beam_left",
            "bottom_beam_right",
            "top_beam_left",
            "top_beam_right",
            "left_post_bottom",
            "left_post_top",
            "right_post_bottom",
            "right_post_top",
        }
        if set(roles) != expected_roles:
            raise ValueError(f"{gate_name} 中心线角色不完整")
        if {row["member"] for row in source_elements} != {
            "bottom_beam",
            "top_beam",
            "left_post",
            "right_post",
        }:
            raise ValueError(f"{gate_name} 单元表构件类型不完整")

        def row_point(row: dict[str, str]) -> Vec3:
            """把门架中心线 CSV 一行转换为 CAD Vec3。"""

            return Vec3(float(row["x_mm"]), float(row["y_mm"]), float(row["z_mm"]))

        bottom_start = row_point(roles["bottom_beam_left"])
        bottom_end = row_point(roles["bottom_beam_right"])
        top_start = row_point(roles["top_beam_left"])
        top_end = row_point(roles["top_beam_right"])

        bottom_couplings = [row for row in source_couplings if row["family"] == "BOTTOM_PHI50"]
        top_couplings = [row for row in source_couplings if row["family"] == "GANTRY_PHI54"]
        if len(bottom_couplings) != 16 or len(top_couplings) != 6:
            raise ValueError(f"{gate_name} 的 16+6 索连接数量不正确")

        # 立柱中心线端部与横梁轴线相切而不相交；正交投影点用于建立 ALL 刚性偏置。
        post_role_pairs = [
            ("left_post_bottom", "left_post_top", "left_post"),
            ("right_post_bottom", "right_post_top", "right_post"),
        ]
        bottom_split_descriptors: list[tuple[Vec3, str]] = []
        top_split_descriptors: list[tuple[Vec3, str]] = []
        for coupling in bottom_couplings:
            axis_point = Vec3(
                float(coupling["beam_axis_x_mm"]),
                float(coupling["beam_axis_y_mm"]),
                float(coupling["beam_axis_z_mm"]),
            )
            bottom_split_descriptors.append(
                (axis_point, f"bottom_rope_master_{int(coupling['rope_index']):02d}")
            )
        for coupling in top_couplings:
            axis_point = Vec3(
                float(coupling["beam_axis_x_mm"]),
                float(coupling["beam_axis_y_mm"]),
                float(coupling["beam_axis_z_mm"]),
            )
            top_split_descriptors.append(
                (axis_point, f"gantry_rope_master_{int(coupling['rope_index']):02d}")
            )
        for bottom_role, top_role, post_name in post_role_pairs:
            bottom_post_point = row_point(roles[bottom_role])
            top_post_point = row_point(roles[top_role])
            bottom_split_descriptors.append(
                (
                    projection_onto_line(bottom_post_point, bottom_start, bottom_end),
                    f"{post_name}_bottom_weld_projection",
                )
            )
            top_split_descriptors.append(
                (
                    projection_onto_line(top_post_point, top_start, top_end),
                    f"{post_name}_top_weld_projection",
                )
            )

        bottom_map, bottom_nodes, bottom_elements = split_gate_beam(
            builder,
            gate_name,
            "bottom_beam",
            bottom_start,
            bottom_end,
            bottom_split_descriptors,
            "gate_bottom",
        )
        top_map, top_nodes, top_elements = split_gate_beam(
            builder,
            gate_name,
            "top_beam",
            top_start,
            top_end,
            top_split_descriptors,
            "gate_top_post",
        )

        physical_node_ids = list(bottom_nodes) + list(top_nodes)
        element_ids = list(bottom_elements) + list(top_elements)
        # 两根立柱各自使用真实中心线端点；端点到横梁轴的偏置用 MPC184 rigid beam 连接。
        for bottom_role, top_role, post_name in post_role_pairs:
            bottom_post_point = row_point(roles[bottom_role])
            top_post_point = row_point(roles[top_role])
            post_bottom_node = builder.add_node(
                bottom_post_point,
                "gate",
                gate_name,
                f"{post_name}_physical_bottom",
                f"CSV role={bottom_role}",
            )
            post_top_node = builder.add_node(
                top_post_point,
                "gate",
                gate_name,
                f"{post_name}_physical_top",
                f"CSV role={top_role}",
            )
            physical_node_ids.extend([post_bottom_node, post_top_node])
            element_ids.append(
                builder.add_element(
                    post_bottom_node,
                    post_top_node,
                    "gate_top_post",
                    "gate",
                    gate_name,
                    post_name,
                    source_member_id=f"{gate_name}:{post_name}",
                )
            )
            bottom_projection = projection_onto_line(bottom_post_point, bottom_start, bottom_end)
            top_projection = projection_onto_line(top_post_point, top_start, top_end)
            builder.add_rigid_connection(
                bottom_map[coordinate_key(bottom_projection)],
                post_bottom_node,
                "ALL",
                "gate",
                gate_name,
                f"{post_name} 下端焊接中心线偏置：平动+转动",
            )
            builder.add_rigid_connection(
                top_map[coordinate_key(top_projection)],
                post_top_node,
                "ALL",
                "gate",
                gate_name,
                f"{post_name} 上端焊接中心线偏置：平动+转动",
            )

        # 原索节点 ID 与 current XLongitudinal 基础网格节点号一致。每个索节点仅作为
        # slave 约束平动，不把 22 个点压成共同平动截面。
        catwalk = int(gate_name[2])
        for coupling in source_couplings:
            family = coupling["family"]
            rope_index = int(coupling["rope_index"])
            rope_name = f"CW{catwalk}_{family}_{rope_index:02d}"
            candidates = rope_nodes_by_name.get(rope_name, [])
            if not candidates:
                raise ValueError(f"{gate_name} 找不到索 {rope_name}")
            rope_point = Vec3(
                float(coupling["rope_x_mm"]),
                float(coupling["rope_y_mm"]),
                float(coupling["rope_z_mm"]),
            )
            nearest = min(
                candidates,
                key=lambda row: rope_point.distance_to(
                    Vec3(float(row["x_mm"]), float(row["y_mm"]), float(row["z_mm"]))
                ),
            )
            nearest_distance = rope_point.distance_to(
                Vec3(float(nearest["x_mm"]), float(nearest["y_mm"]), float(nearest["z_mm"]))
            )
            if nearest_distance > GEOMETRY_TOL_MM:
                raise ValueError(
                    f"{gate_name}/{rope_name} 最近原索节点误差 {nearest_distance:.6g} mm"
                )
            axis_point = Vec3(
                float(coupling["beam_axis_x_mm"]),
                float(coupling["beam_axis_y_mm"]),
                float(coupling["beam_axis_z_mm"]),
            )
            master_map = bottom_map if family == "BOTTOM_PHI50" else top_map
            builder.add_rigid_connection(
                master_map[coordinate_key(axis_point)],
                int(nearest["node_id"]),
                "UXYZ",
                "gate",
                gate_name,
                f"梁轴 master -> {rope_name} 原索 slave；保留截面刚体转动",
                # rope_point 是原索 slave 的权威 CAD 坐标，用于创建严格共点的零质量辅助节点。
                slave_cad_point=rope_point,
            )

        # 横通道接入每幅猫道外侧底索。CW1 在 CAD x<0，取最小 x；CW2 取最大 x。
        outer_coupling = (
            min(bottom_couplings, key=lambda row: float(row["rope_x_mm"]))
            if catwalk == 1
            else max(bottom_couplings, key=lambda row: float(row["rope_x_mm"]))
        )
        outer_axis_point = Vec3(
            float(outer_coupling["beam_axis_x_mm"]),
            float(outer_coupling["beam_axis_y_mm"]),
            float(outer_coupling["beam_axis_z_mm"]),
        )
        outer_rope_point = Vec3(
            float(outer_coupling["rope_x_mm"]),
            float(outer_coupling["rope_y_mm"]),
            float(outer_coupling["rope_z_mm"]),
        )
        # 保存 16 个下横梁分段 master，供横通道两条顶弦在每根底索横向位置处
        # 逐点连接。该字典是避免“只连最外端”简化的关键接口。
        bottom_axis_master_by_rope_index: dict[int, int] = {}
        bottom_rope_point_by_rope_index: dict[int, Vec3] = {}
        for coupling in bottom_couplings:
            rope_index = int(coupling["rope_index"])
            axis_point = Vec3(
                float(coupling["beam_axis_x_mm"]),
                float(coupling["beam_axis_y_mm"]),
                float(coupling["beam_axis_z_mm"]),
            )
            bottom_axis_master_by_rope_index[rope_index] = bottom_map[
                coordinate_key(axis_point)
            ]
            bottom_rope_point_by_rope_index[rope_index] = Vec3(
                float(coupling["rope_x_mm"]),
                float(coupling["rope_y_mm"]),
                float(coupling["rope_z_mm"]),
            )
        gate_index = int(gate_name.rsplit("_", 1)[1])
        gate_infos[gate_name] = GateBuildInfo(
            gate_name=gate_name,
            gate_index=gate_index,
            catwalk=catwalk,
            physical_node_ids=physical_node_ids,
            element_ids=element_ids,
            outer_bottom_axis_master=bottom_map[coordinate_key(outer_axis_point)],
            outer_bottom_rope_point_cad=outer_rope_point,
            bottom_axis_master_by_rope_index=bottom_axis_master_by_rope_index,
            bottom_rope_point_by_rope_index=bottom_rope_point_by_rope_index,
        )

        # 每品门架分别建立物理节点和单元组件；方向节点另纳入系统总节点组件。
        gate_component_prefix = f"G_CW{catwalk}_{gate_index:03d}"
        builder.node_groups[f"{gate_component_prefix}_N"].update(physical_node_ids)
        builder.element_groups[f"{gate_component_prefix}_E"].update(element_ids)

    return gate_infos


def transform_passage_local_to_cad(
    local_point: Vec3,
    station_y_mm: float,
    top_chord_reference_z_mm: float,
    slope_degree: float,
) -> Vec3:
    """将横通道局部节点旋转/平移到指定 dedicated station 的 CAD 全局坐标。"""

    reference = Vec3(
        PASSAGE_CONTROL_LENGTH_MM / 2.0,
        PASSAGE_WIDTH_MM / 2.0,
        PASSAGE_HEIGHT_MM,
    )
    relative = local_point - reference
    angle = math.radians(slope_degree)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    # 绕 CAD 全局 X（横桥向）旋转，使局部 y 贴合承重索顺桥切线。
    rotated_y = cosine * relative.y - sine * relative.z
    rotated_z = sine * relative.y + cosine * relative.z
    return Vec3(
        relative.x,
        station_y_mm + rotated_y,
        top_chord_reference_z_mm + rotated_z,
    )


def build_all_passages(
    builder: ModelBuilder,
    template: PassageTemplate,
    station_rows: Sequence[dict[str, str]],
    gate_infos: dict[str, GateBuildInfo],
) -> None:
    """在 21 个真实站位复制完整横通道，并接入对应 dedicated gate。"""

    span_component_names = {
        "north_side": "PASS_NORTH_E",
        "main_span": "PASS_MAIN_E",
        "south_side": "PASS_SOUTH_E",
        "south_aux": "PASS_SAUX_E",
    }
    span_node_component_names = {
        "north_side": "PASS_NORTH_N",
        "main_span": "PASS_MAIN_N",
        "south_side": "PASS_SOUTH_N",
        "south_aux": "PASS_SAUX_N",
    }

    for station in station_rows:
        passage_name = station["name"].strip()
        station_y = float(station["station_y_mm"])
        top_reference_z = float(station["top_chord_reference_z_mm"])
        slope_degree = float(station["local_slope_degree"])
        cw1_gate_name = station["cw1_gate_name"].strip()
        cw2_gate_name = station["cw2_gate_name"].strip()
        if cw1_gate_name not in gate_infos or cw2_gate_name not in gate_infos:
            raise ValueError(f"{passage_name} 指向不存在门架 {cw1_gate_name}/{cw2_gate_name}")

        passage_node_ids: list[int] = []
        local_index_to_node: dict[int, int] = {}
        local_coordinate_to_index: dict[tuple[int, int, int], int] = {}
        for local_index, (local_point, source_role) in enumerate(
            zip(template.points, template.point_roles)
        ):
            cad_point = transform_passage_local_to_cad(
                local_point,
                station_y,
                top_reference_z,
                slope_degree,
            )
            node_id = builder.add_node(
                cad_point,
                "passage",
                passage_name,
                role=f"passage_joint_{local_index:03d}",
                source_local_coord=(
                    f"local=({local_point.x:.6f},{local_point.y:.6f},{local_point.z:.6f});"
                    f"source={source_role}"
                ),
            )
            local_index_to_node[local_index] = node_id
            local_coordinate_to_index[coordinate_key(local_point)] = local_index
            passage_node_ids.append(node_id)

        passage_element_ids: list[int] = []
        for edge_index, (local_n1, local_n2, section_key, member, source_id) in enumerate(
            template.edges,
            start=1,
        ):
            passage_element_ids.append(
                builder.add_element(
                    local_index_to_node[local_n1],
                    local_index_to_node[local_n2],
                    section_key,
                    "passage",
                    passage_name,
                    member,
                    source_member_id=f"{passage_name}:{source_id}:split_{edge_index:03d}",
                )
            )

        # 横通道并非只在最外端连接。两条 PHI152 顶弦穿过两幅猫道各 16 根底索
        # 的横向位置；模板已在这些 64 个交点拆分。这里以 dedicated gate 下横梁
        # 对应分段节点为 master、顶弦交点梁节点为 slave 建立 MPC184 rigid beam，使两条
        # 顶弦相对门架中心线的 ±750*cos(theta) 顺桥偏置包含完整刚体转动项。
        for gate_name in (cw1_gate_name, cw2_gate_name):
            gate_info = gate_infos[gate_name]
            for rope_index in range(1, 17):
                if rope_index not in gate_info.bottom_axis_master_by_rope_index:
                    raise ValueError(f"{passage_name}/{gate_name} 缺少底索 {rope_index} 的梁轴 master")
                rope_point = gate_info.bottom_rope_point_by_rope_index[rope_index]
                local_q = rope_point.x + PASSAGE_CONTROL_LENGTH_MM / 2.0
                for local_r in (0.0, PASSAGE_WIDTH_MM):
                    local_interface = Vec3(local_q, local_r, PASSAGE_HEIGHT_MM)
                    interface_key = coordinate_key(local_interface)
                    if interface_key not in local_coordinate_to_index:
                        raise ValueError(
                            f"{passage_name}/{gate_name}/rope{rope_index:02d} 顶弦接口未在模板拆分"
                        )
                    slave_node = local_index_to_node[
                        local_coordinate_to_index[interface_key]
                    ]
                    builder.add_rigid_connection(
                        gate_info.bottom_axis_master_by_rope_index[rope_index],
                        slave_node,
                        "ALL",
                        "passage_interface",
                        passage_name,
                        (
                            f"{gate_name} 下横梁 rope{rope_index:02d} 分段 master -> "
                            f"顶弦 r={local_r:.0f} slave；含刚体转动"
                        ),
                    )

        # 每端三个弦杆端点通过有限刚度 PHI102x4 三角接口杆汇入一个接口根节点。
        # 根节点与门架下横梁轴 master 之间只有 4.65/112.5 mm 量级中心线偏置，
        # 该短偏置使用 MPC184 rigid beam，保证大转动刚体运动学且不采用同平动 CP。
        for end_x, gate_name, end_label in [
            (0.0, cw1_gate_name, "CW1_END"),
            (PASSAGE_CONTROL_LENGTH_MM, cw2_gate_name, "CW2_END"),
        ]:
            gate_info = gate_infos[gate_name]
            root_node = builder.add_node(
                gate_info.outer_bottom_rope_point_cad,
                "passage",
                passage_name,
                role=f"{end_label}_finite_interface_root",
                source_local_coord=f"dedicated gate={gate_name}; outer bottom-rope center",
            )
            passage_node_ids.append(root_node)
            builder.add_rigid_connection(
                gate_info.outer_bottom_axis_master,
                root_node,
                "ALL",
                "passage_interface",
                passage_name,
                f"{gate_name} 下横梁轴 -> 横通道三角接口根节点刚性偏置",
            )
            end_local_indices = [
                local_index
                for local_index, local_point in enumerate(template.points)
                if abs(local_point.x - end_x) <= GEOMETRY_TOL_MM
            ]
            if len(end_local_indices) != 3:
                raise ValueError(f"{passage_name}/{end_label} 端面不是 3 个连接点")
            for fan_index, local_index in enumerate(end_local_indices, start=1):
                passage_element_ids.append(
                    builder.add_element(
                        root_node,
                        local_index_to_node[local_index],
                        "passage_frame102",
                        "passage",
                        passage_name,
                        member="finite_tri_gate_interface",
                        source_member_id=f"{passage_name}:{end_label}:fan_{fan_index}",
                    )
                )

        builder.node_groups[f"P_{passage_name}_N"].update(passage_node_ids)
        builder.element_groups[f"P_{passage_name}_E"].update(passage_element_ids)
        span_name = station["span"].strip()
        if span_name not in span_component_names:
            raise ValueError(f"{passage_name} 的 span={span_name!r} 未定义")
        builder.element_groups[span_component_names[span_name]].update(passage_element_ids)
        # 跨别节点组件只收物理节点；方向节点已单独归入 PASS_ORIENT_N，避免后续
        # 质量空间化把 BEAM188 方向节点误当成可布置质量的真实节点。
        builder.node_groups[span_node_component_names[span_name]].update(
            passage_node_ids
        )


def add_system_components(builder: ModelBuilder) -> None:
    """按 gate/passage 系统补充总节点和总单元组件。"""

    for node in builder.nodes:
        if node.system == "gate":
            builder.node_groups["ALL_GATES_N"].add(node.apdl_node_id)
            # 每品门架节点组件同时包含物理节点和 BEAM188 方向节点；物理节点总组件
            # GATE_PHYS_N 仍可用于质量空间化，二者用途明确分离。
            gate_index = int(node.assembly_name.rsplit("_", 1)[1])
            catwalk = int(node.assembly_name[2])
            builder.node_groups[f"G_CW{catwalk}_{gate_index:03d}_N"].add(
                node.apdl_node_id
            )
            if node.is_orientation:
                builder.node_groups["GATE_ORIENT_N"].add(node.apdl_node_id)
            else:
                builder.node_groups["GATE_PHYS_N"].add(node.apdl_node_id)
        elif node.system == "passage":
            builder.node_groups["ALL_PASSAGES_N"].add(node.apdl_node_id)
            builder.node_groups[f"P_{node.assembly_name}_N"].add(node.apdl_node_id)
            if node.is_orientation:
                builder.node_groups["PASS_ORIENT_N"].add(node.apdl_node_id)
            else:
                builder.node_groups["PASS_PHYS_N"].add(node.apdl_node_id)

    for element in builder.elements:
        if element.system == "gate":
            builder.element_groups["ALL_GATES"].add(element.apdl_elem_id)
        elif element.system == "passage":
            builder.element_groups["ALL_PASSAGES"].add(element.apdl_elem_id)


def compress_integer_ranges(values: Iterable[int]) -> list[tuple[int, int]]:
    """把整数集合压缩为连续闭区间，减少 APDL 组件选择命令数量。"""

    ordered = sorted(set(values))
    if not ordered:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append((start, previous))
        start = previous = value
    ranges.append((start, previous))
    return ranges


def emit_component_commands(name: str, entity: str, ids: Iterable[int]) -> list[str]:
    """生成一个节点或单元组件的选择与 CM 命令。"""

    values = sorted(set(ids))
    if not values:
        return []
    if len(name) > 32:
        raise ValueError(f"MAPDL 组件名超过 32 字符：{name}")
    if entity == "NODE":
        select_command = "NSEL"
        item = "NODE"
    elif entity == "ELEM":
        select_command = "ESEL"
        item = "ELEM"
    else:
        raise ValueError(f"不支持的组件实体 {entity}")
    lines = [f"! 组件 {name}: {entity} 数量={len(values)}", f"{select_command},NONE"]
    for start, end in compress_integer_ranges(values):
        if start == end:
            lines.append(f"{select_command},A,{item},,{start}")
        else:
            lines.append(f"{select_command},A,{item},,{start},{end}")
    lines.extend([f"CM,{name},{entity}", "ALLSEL,ALL"])
    return lines


def write_apdl_include(
    path: Path,
    builder: ModelBuilder,
    sections: dict[str, SectionDef],
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    density_tonne_per_mm3: float,
) -> None:
    """写出可被主模型 ``/INPUT`` 的 MAPDL include。"""

    lines: list[str] = [
        "! ============================================================================",
        "! V2.0 有限刚度门架 + 21 道完整横向通道；由 Python 生成，请勿手工重编号。",
        "! 单位：N, mm, tonne, s；坐标：X顺桥、Y横桥、Z竖向。",
        "! 禁止策略：无 CP,UX/UY/UZ 全截面锁死；无仅 CP,UY 的两幅猫道耦合。",
        "! 新梁密度当前为 0；横通道/门架集中质量将由独立质量空间化步骤处理。",
        "! ALL 使用 MPC184 rigid beam；UXYZ 使用偏置刚臂+显式高罚刚度共点三平移 general joint；不生成小挠度 CERIG。",
        "! ============================================================================",
        "/PREP7",
        f"ET,{BEAM_TYPE_ID},BEAM188",
        f"KEYOPT,{BEAM_TYPE_ID},3,3",
        # TYPE=72 明确定义为 MPC184 rigid beam，只实现来源语义为 ALL 的六自由度刚接。
        f"ET,{MPC_RIGID_BEAM_TYPE_ID},MPC184 ! ALL来源的零质量六自由度刚性连接",
        # KEYOPT(1)=1 选择 rigid beam，使偏置从节点平动包含主节点转角产生的刚体位移。
        f"KEYOPT,{MPC_RIGID_BEAM_TYPE_ID},1,{MPC_RIGID_BEAM_KEYOPT_VALUE} ! 六自由度 rigid beam 公式",
        # KEYOPT(2)=0 选择直接消元，满足后续线性摄动模态对约束保留方式的要求。
        f"KEYOPT,{MPC_RIGID_BEAM_TYPE_ID},2,{MPC_DIRECT_ELIMINATION_KEYOPT_VALUE} ! rigid beam直接消元公式",
        # KEYOPT(5)=0 保留几何刚度，避免预应力摄动时无意丢失刚性连接的应力刚化贡献。
        f"KEYOPT,{MPC_RIGID_BEAM_TYPE_ID},5,{MPC_KEEP_GEOMETRIC_STIFFNESS_KEYOPT_VALUE} ! rigid beam保留几何刚度",
        # TYPE=73 明确定义为 MPC184 general joint；共点时只约束 UX/UY/UZ 三项相对位移。
        f"ET,{MPC_TRANSLATION_JOINT_TYPE_ID},MPC184 ! UXYZ来源的共点三平移general joint",
        # KEYOPT(1)=16 选择 general joint，使受约束自由度可由 SECJOINT,RDOF 明确列出。
        f"KEYOPT,{MPC_TRANSLATION_JOINT_TYPE_ID},1,{MPC_GENERAL_JOINT_KEYOPT_VALUE} ! general joint公式",
        # KEYOPT(2)=1 对 general joint 选择罚函数，避免与相邻 direct-elimination rigid beam 形成消元依赖冲突。
        f"KEYOPT,{MPC_TRANSLATION_JOINT_TYPE_ID},2,{MPC_PENALTY_METHOD_KEYOPT_VALUE} ! general joint罚函数公式",
        # KEYOPT(4)=1 只激活平移自由度，避免向仅含 LINK180 的原索节点引入零刚度转角。
        f"KEYOPT,{MPC_TRANSLATION_JOINT_TYPE_ID},4,{MPC_DISPLACEMENT_ONLY_KEYOPT_VALUE} ! joint仅激活UX/UY/UZ",
        # SECTION=73 声明 general joint 截面；V2UXYZ 名称标识该截面只承接原 UXYZ 语义。
        f"SECTYPE,{MPC_TRANSLATION_JOINT_SECTION_ID},JOINT,GENE,V2UXYZ ! UXYZ共点三平移joint截面",
        # 9011 坐标系与全局轴平行并作为 joint 的 I 端初始基底；七个 0 表示原点与欧拉角均不偏置。
        f"LOCAL,{MPC_TRANSLATION_JOINT_I_COORDINATE_SYSTEM_ID},0,0,0,0,0,0,0 ! joint I端全局平行初始基底",
        # 9012 坐标系同样与全局轴平行并作为 joint 的 J 端初始基底；独立编号保持两端定义清晰。
        f"LOCAL,{MPC_TRANSLATION_JOINT_J_COORDINATE_SYSTEM_ID},0,0,0,0,0,0,0 ! joint J端全局平行初始基底",
        # LSYS 将 9011/9012 分别绑定到 joint 两端；共点节点不会产生额外初始偏置。
        f"SECJOINT,LSYS,{MPC_TRANSLATION_JOINT_I_COORDINATE_SYSTEM_ID},{MPC_TRANSLATION_JOINT_J_COORDINATE_SYSTEM_ID} ! joint两端初始基底",
        # RDOF 中的 1、2、3 依次表示相对 UX、UY、UZ，明确不约束三项相对转动。
        "SECJOINT,RDOF,1,2,3 ! 仅约束三项相对平移",
        # PNLT 的负号表示直接给定位移绝对罚因子；5.0E10 的量级已经由静力与线性摄动小算例验收。
        f"SECJOINT,PNLT,DISP,-{MPC_TRANSLATION_PENALTY_FACTOR:.12g} ! 位移绝对罚因子，N/mm量纲",
    ]

    # 六组材料分别定义，方便后续单独标定 E；当前密度统一为 0 防止重复质量。
    for section in sections.values():
        lines.extend(
            [
                f"! 材料 {section.material_id}: {section.key} / {section.description}",
                f"MP,EX,{section.material_id},{elastic_modulus_mpa:.12g}",
                f"MP,PRXY,{section.material_id},{poisson_ratio:.12g}",
                f"MP,DENS,{section.material_id},{density_tonne_per_mm3:.12g}",
            ]
        )

    # ASEC 按官方 14 项顺序完整写入 A/I/Iw/J、中心、外包络和双向剪切修正；
    # 其中 Kxz=TSxz*G*A、Kxy=TSxy*G*A，禁止继续使用缺省 1.0。
    for section in sections.values():
        lines.extend(
            [
                f"! 截面 {section.section_id}: {section.description}",
                f"SECTYPE,{section.section_id},BEAM,ASEC,{section.key[:8].upper()}",
                (
                    f"SECDATA,{section.area_mm2:.12g},{section.iyy_mm4:.12g},0,"
                    f"{section.izz_mm4:.12g},{section.warping_iw_mm6:.12g},"
                    # 四个 0 依次表示对称截面的 CGy、CGz、SHy、SHz 均位于梁轴原点。
                    f"{section.torsion_j_mm4:.12g},0,0,0,0,"
                    # 最后四项严格对应 TKz、TKy、TSxz、TSxy，不允许交换两个剪切平面。
                    f"{section.thickness_z_mm:.12g},{section.thickness_y_mm:.12g},"
                    f"{section.shear_correction_xz:.12g},{section.shear_correction_xy:.12g}"
                ),
            ]
        )

    lines.append("! ------------------------------ 新增节点 ------------------------------")
    for node in builder.nodes:
        point = node.apdl_point
        lines.append(
            f"N,{node.apdl_node_id},{point.x:.12f},{point.y:.12f},{point.z:.12f}"
        )

    lines.append("! ------------------------------ BEAM188 单元 ------------------------------")
    current_assignment: tuple[int, int] | None = None
    for element in builder.elements:
        section = sections[element.section_key]
        assignment = (section.material_id, section.section_id)
        if assignment != current_assignment:
            lines.extend(
                [
                    f"TYPE,{BEAM_TYPE_ID}",
                    f"MAT,{section.material_id}",
                    f"SECNUM,{section.section_id}",
                ]
            )
            current_assignment = assignment
        lines.append(
            f"EN,{element.apdl_elem_id},{element.n1},{element.n2},{element.orientation_node}"
        )

    # 写文件前确认所有刚性连接已经在物理梁之后取得稳定单元号，禁止输出半编号记录。
    unassigned_connections = [
        # None 是登记阶段哨兵；出现任何一条都说明遗漏了 finalize_rigid_connection_ids 调用。
        connection for connection in builder.rigid_connections if connection.apdl_elem_id is None
    ]
    # 未编号连接会导致重复或非法 EN 命令，因此必须在产生正式 include 前失败。
    if unassigned_connections:
        # 错误消息给出数量，便于定位构建流程是否在完成物理梁前提前写文件。
        raise RuntimeError(f"仍有 {len(unassigned_connections)} 条 MPC184 刚性连接未分配单元号")
    # 单独分区写出两类 MPC184，避免与可参与体积质量分配的 BEAM188 物理杆件混淆。
    lines.append("! ---------------------- MPC184 大转动连接 ----------------------")
    # current_mpc_type_id 记录当前激活类型，避免为连续同类连接重复写 TYPE 命令。
    current_mpc_type_id: int | None = None
    # 按稳定登记顺序输出全部连接，使星形连接的公共 master 始终位于 I 端。
    for connection in builder.rigid_connections:
        # apdl_elem_id 已由上方硬检查排除 None；显式断言帮助类型检查器和人工审查。
        assert connection.apdl_elem_id is not None
        # ALL 来源需要完整刚体运动学，因此选择六自由度 rigid beam 类型。
        if connection.source_semantics == "ALL":
            # ALL 不应创建 UXYZ 专用辅助节点或偏置单元；任一非 None 都表示登记逻辑错误。
            if connection.offset_node_id is not None or connection.offset_elem_id is not None:
                # 非法辅助记录会造成重复刚臂，必须在写出 APDL 前停止。
                raise RuntimeError("ALL 连接意外包含 UXYZ 辅助节点或偏置单元")
            # 当前类型不是 72 时激活 rigid beam，确保本条 EN 使用六自由度刚接。
            if current_mpc_type_id != MPC_RIGID_BEAM_TYPE_ID:
                # TYPE=72 对后续 ALL 主单元和 UXYZ 偏置单元共同生效。
                lines.append(f"TYPE,{MPC_RIGID_BEAM_TYPE_ID} ! 六自由度rigid beam")
                # 更新类型缓存，避免连续 ALL 记录重复写出 TYPE。
                current_mpc_type_id = MPC_RIGID_BEAM_TYPE_ID
            # ALL 直接连接原 master/slave，并同时约束相对平移和相对转动。
            lines.append(
                # 行尾保留来源语义和装配名，便于逐条追溯。
                f"EN,{connection.apdl_elem_id},{connection.master_node},{connection.slave_node} "
                f"! MPC184 rigid beam六自由度刚接；来源语义=ALL；装配={connection.assembly_name}"
            )
        # UXYZ 的主约束单元位于辅助节点与原 slave 的共点位置，仅约束相对平移。
        elif connection.source_semantics == "UXYZ":
            # UXYZ 必须同时具备辅助节点和偏置 rigid beam 单元号，缺一都不能保持原偏置转动项。
            if connection.offset_node_id is None or connection.offset_elem_id is None:
                # 缺少组合中的任一部分都会退化为错误的直接平移耦合。
                raise RuntimeError("UXYZ 连接缺少辅助节点或偏置 rigid beam 单元")
            # 先激活 TYPE=72，把原 master 到共点辅助节点构造成六自由度刚性偏置。
            if current_mpc_type_id != MPC_RIGID_BEAM_TYPE_ID:
                # TYPE=72 使 master 转动正确产生辅助节点的偏置平移。
                lines.append(f"TYPE,{MPC_RIGID_BEAM_TYPE_ID} ! UXYZ前置偏置rigid beam")
                # 更新当前类型缓存为 72。
                current_mpc_type_id = MPC_RIGID_BEAM_TYPE_ID
            # 偏置刚臂终点是与原 slave 共点的新增辅助节点，不直接锁定原 slave 转角。
            lines.append(
                # offset_elem_id 是本逻辑连接的第一枚 MPC184 单元号。
                f"EN,{connection.offset_elem_id},{connection.master_node},{connection.offset_node_id} "
                f"! UXYZ偏置rigid beam；装配={connection.assembly_name}"
            )
            # 再激活 TYPE=73，用共点高罚刚度 general joint 连接辅助节点与原 slave。
            if current_mpc_type_id != MPC_TRANSLATION_JOINT_TYPE_ID:
                # TYPE=73 只激活 UX/UY/UZ，并以已验收的显式绝对罚因子约束三项相对平移。
                lines.append(f"TYPE,{MPC_TRANSLATION_JOINT_TYPE_ID} ! UXYZ共点三平移general joint")
                # SECTION=73 封装两端局部基底、三项 RDOF 与 5.0E10 位移绝对罚因子。
                lines.append(f"SECNUM,{MPC_TRANSLATION_JOINT_SECTION_ID} ! UXYZ general joint截面")
                # 更新当前类型缓存为 73；后续连续 UXYZ 连接沿用同一 joint 截面定义。
                current_mpc_type_id = MPC_TRANSLATION_JOINT_TYPE_ID
            # 共点 general joint 只高精度传递辅助节点的三项平移，不约束原 slave 的任何转动。
            lines.append(
                # apdl_elem_id 是本逻辑连接的第二枚 MPC184 单元号。
                f"EN,{connection.apdl_elem_id},{connection.offset_node_id},{connection.slave_node} "
                f"! MPC184 general joint共点三平移高罚刚度约束；来源语义=UXYZ；装配={connection.assembly_name}"
            )
        # 理论上 add_rigid_connection 已拒绝其他标签；该分支防止内存记录被外部篡改。
        else:
            # 未知语义不能安全选择 MPC184 类型，必须在写出 APDL 前停止。
            raise RuntimeError(f"无法映射的 MPC184 来源语义：{connection.source_semantics}")

    lines.append("! ------------------------------ 节点/单元组件 ------------------------------")
    for name in sorted(builder.node_groups):
        lines.extend(emit_component_commands(name, "NODE", builder.node_groups[name]))
    for name in sorted(builder.element_groups):
        lines.extend(emit_component_commands(name, "ELEM", builder.element_groups[name]))
    lines.extend(["ALLSEL,ALL", "FINISH", ""])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

    # 生成后立即检查禁用的 CP 与 CERIG 命令；注释行不以这些命令前缀开头，因此不会误报。
    forbidden_prefixes = ("CP,", "CERIG,")
    # forbidden_lines 保存真正以禁用命令开头的代码行，任何非空结果都表示运动学回退。
    forbidden_lines = [
        # 同时检查两个前缀，防止后续维护重新引入全截面 CP 或小挠度 CERIG。
        line for line in lines if line.strip().upper().startswith(forbidden_prefixes)
    ]
    # 禁用命令必须为零；只在发现违规时抛错并阻止覆盖可用产物。
    if forbidden_lines:
        # 报告总违规数和首条文本，便于快速定位生成逻辑中的回归位置。
        raise RuntimeError(
            f"生成的 APDL 意外包含 {len(forbidden_lines)} 条 CP/CERIG 命令：{forbidden_lines[0]}"
        )


def write_generated_node_csv(path: Path, builder: ModelBuilder) -> None:
    """输出新增节点坐标、系统、品名、角色及来源局部坐标台账。"""

    fieldnames = [
        "apdl_node_id",
        "x_mm",
        "y_mm",
        "z_mm",
        "cad_x_mm",
        "cad_y_mm",
        "cad_z_mm",
        "system",
        "assembly_name",
        "role",
        "source_local_coord",
        "is_orientation",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for node in builder.nodes:
            writer.writerow(
                {
                    "apdl_node_id": node.apdl_node_id,
                    "x_mm": f"{node.apdl_point.x:.12f}",
                    "y_mm": f"{node.apdl_point.y:.12f}",
                    "z_mm": f"{node.apdl_point.z:.12f}",
                    "cad_x_mm": f"{node.cad_point.x:.12f}",
                    "cad_y_mm": f"{node.cad_point.y:.12f}",
                    "cad_z_mm": f"{node.cad_point.z:.12f}",
                    "system": node.system,
                    "assembly_name": node.assembly_name,
                    "role": node.role,
                    "source_local_coord": node.source_local_coord,
                    "is_orientation": int(node.is_orientation),
                }
            )


def write_generated_element_csv(
    path: Path,
    builder: ModelBuilder,
    sections: dict[str, SectionDef],
) -> None:
    """输出新增单元拓扑、分组、长度、面积和体积台账。"""

    fieldnames = [
        "apdl_elem_id",
        "n1",
        "n2",
        "orientation_node",
        "system",
        "assembly_name",
        "member",
        "section_key",
        "material_id",
        "section_id",
        "length_mm",
        "area_mm2",
        "volume_mm3",
        "iyy_mm4",  # 记录绕 local-y 的弯曲惯性矩，供逐单元强弱轴审计。
        "izz_mm4",  # 记录绕 local-z 的弯曲惯性矩，供逐单元强弱轴审计。
        "shear_correction_xz",  # 记录 ASEC 的 TSxz，供核对 local-xz 剪切刚度。
        "shear_correction_xy",  # 记录 ASEC 的 TSxy，供核对 local-xy 剪切刚度。
        "source_member_id",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for element in builder.elements:
            section = sections[element.section_key]
            writer.writerow(
                {
                    "apdl_elem_id": element.apdl_elem_id,
                    "n1": element.n1,
                    "n2": element.n2,
                    "orientation_node": element.orientation_node,
                    "system": element.system,
                    "assembly_name": element.assembly_name,
                    "member": element.member,
                    "section_key": element.section_key,
                    "material_id": section.material_id,
                    "section_id": section.section_id,
                    "length_mm": f"{element.length_mm:.12f}",
                    "area_mm2": f"{section.area_mm2:.12f}",
                    "volume_mm3": f"{element.length_mm * section.area_mm2:.12f}",
                    # iyy_mm4 明确记录该单元在当前截面映射下绕 local-y 的惯性矩。
                    "iyy_mm4": f"{section.iyy_mm4:.12f}",
                    # izz_mm4 明确记录该单元在当前截面映射下绕 local-z 的惯性矩。
                    "izz_mm4": f"{section.izz_mm4:.12f}",
                    # shear_correction_xz 是无量纲 TSxz，实际剪切刚度为 TSxz*G*A。
                    "shear_correction_xz": f"{section.shear_correction_xz:.15f}",
                    # shear_correction_xy 是无量纲 TSxy，实际剪切刚度为 TSxy*G*A。
                    "shear_correction_xy": f"{section.shear_correction_xy:.15f}",
                    "source_member_id": element.source_member_id,
                }
            )


def write_anisotropic_axis_audit_csv(path: Path, builder: ModelBuilder) -> None:
    """输出全部 H175 与 RHS50×30 的 BEAM188 局部轴和截面映射逐件台账。

    参数：
        path: UTF-8-SIG CSV 输出路径，供人工审阅和后续验收脚本读取。
        builder: 已通过 ``validate_anisotropic_section_axes`` 的完整模型构建器。

    返回：
        无；成功时写出 2698+2898=5596 行，每行对应一根非旋转对称梁。
    """

    # fieldnames 固定列序，避免后续审计依赖 Python 字典插入顺序。
    fieldnames = [
        "apdl_elem_id",  # BEAM188 单元号，用于回查正式 APDL 的 EN 命令。
        "n1",  # I 节点号，定义 local-x 起点。
        "n2",  # J 节点号，定义 local-x 终点。
        "orientation_node",  # K 节点号，定义包含 local-x/local-z 的 I-J-K 平面。
        "assembly_name",  # 门架或横通道装配名，用于逐品定位。
        "member",  # 构件角色，用于区分门架下横梁和横通道纵杆。
        "section_key",  # 稳定截面键，只允许 gate_bottom 或 passage_rhs50x30。
        "local_x_global_x",  # local-x 在 MAPDL 全局 X 上的方向余弦。
        "local_x_global_y",  # local-x 在 MAPDL 全局 Y 上的方向余弦。
        "local_x_global_z",  # local-x 在 MAPDL 全局 Z 上的方向余弦。
        "local_y_global_x",  # local-y 在 MAPDL 全局 X 上的方向余弦。
        "local_y_global_y",  # local-y 在 MAPDL 全局 Y 上的方向余弦。
        "local_y_global_z",  # local-y 在 MAPDL 全局 Z 上的方向余弦。
        "local_z_global_x",  # local-z 在 MAPDL 全局 X 上的方向余弦。
        "local_z_global_y",  # local-z 在 MAPDL 全局 Y 上的方向余弦。
        "local_z_global_z",  # local-z 在 MAPDL 全局 Z 上的方向余弦。
        "abs_local_z_dot_global_z",  # 截面高度轴与全局竖向的绝对对齐度，目标为 1。
        "iyy_mm4",  # ASEC 绕 local-y 的惯性矩；H175 为强轴、RHS50×30 为弱轴。
        "izz_mm4",  # ASEC 绕 local-z 的惯性矩；H175 为弱轴、RHS50×30 为强轴。
        "thickness_z_mm",  # ASEC TKz；H175 为 175 mm、RHS50×30 为 30 mm。
        "thickness_y_mm",  # ASEC TKy；H175 为 175 mm、RHS50×30 为 50 mm。
        "shear_correction_xz",  # ASEC TSxz，控制 Kxz=TSxz*G*A。
        "shear_correction_xy",  # ASEC TSxy，控制 Kxy=TSxy*G*A。
        "acceptance_rule",  # 该截面类型的人读强弱轴验收规则。
        "status",  # 单行状态；能写出即为 PASS，失败会在写文件前抛错。
    ]
    # global_vertical 为 MAPDL 全局 Z 单位向量，用于输出可直接筛选的竖向对齐度。
    global_vertical = Vec3(0.0, 0.0, 1.0)
    # 先复用硬校验；若数量、方向或惯性映射不闭合，不允许生成带 PASS 的台账。
    validate_anisotropic_section_axes(builder)
    # 使用 utf-8-sig 方便 Excel 直接识别中文规则；newline='' 防止 Windows 产生空行。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        # DictWriter 依据固定 fieldnames 输出，extrasaction 采用默认 raise 防止字段漂移。
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        # 表头描述每列物理含义，必须在任何数据行之前写出。
        writer.writeheader()
        # 遍历全部梁，但只输出强弱轴会受滚转影响且已有构造方向证据的两类截面。
        for element in builder.elements:
            # 对称方管和圆管绕轴滚转不改变 Iyy/Izz，因此不进入本逐件非对称轴台账。
            if element.section_key not in {"gate_bottom", "passage_rhs50x30"}:
                # continue 只跳过台账输出，不跳过前置全梁 I/J/K 正交性校验。
                continue
            # 读取已校验的右手单位轴，确保 CSV 与正式 EN,I,J,K 使用同一算法。
            local_x, local_y, local_z = derive_beam_local_axes(builder, element)
            # section 提供该单元实际使用的 ASEC 惯性矩、尺寸和双向剪切修正。
            section = builder.sections[element.section_key]
            # H175 规则明确“local-z 竖直、Iyy 强、Izz 弱”，用于防止 34.9% 回归。
            if element.section_key == "gate_bottom":
                # 规则字符串只用于审阅，不参与数值判定；数值判定已由前置函数完成。
                acceptance_rule = "local-z竖直；TKz/TKy=175/175；Iyy强轴>Izz弱轴"
            # 另一允许分支必然是 passage_rhs50x30，因为上方集合已经完成筛选。
            else:
                # RHS 规则保留 CAD width=50/height=30 的真实朝向，不能套用 H175 交换逻辑。
                acceptance_rule = "local-z竖直；TKz/TKy=30/50；Izz强轴>Iyy弱轴"
            # 写出一个单元的全部方向余弦和截面映射；十五位小数保留双精度审计能力。
            writer.writerow(
                {
                    "apdl_elem_id": element.apdl_elem_id,  # 输出当前单元稳定编号。
                    "n1": element.n1,  # 输出 I 节点编号。
                    "n2": element.n2,  # 输出 J 节点编号。
                    "orientation_node": element.orientation_node,  # 输出 K 方向节点编号。
                    "assembly_name": element.assembly_name,  # 输出逐品装配名。
                    "member": element.member,  # 输出构件角色。
                    "section_key": element.section_key,  # 输出稳定截面键。
                    "local_x_global_x": f"{local_x.x:.15f}",  # 输出 ex 的全局 X 分量。
                    "local_x_global_y": f"{local_x.y:.15f}",  # 输出 ex 的全局 Y 分量。
                    "local_x_global_z": f"{local_x.z:.15f}",  # 输出 ex 的全局 Z 分量。
                    "local_y_global_x": f"{local_y.x:.15f}",  # 输出 ey 的全局 X 分量。
                    "local_y_global_y": f"{local_y.y:.15f}",  # 输出 ey 的全局 Y 分量。
                    "local_y_global_z": f"{local_y.z:.15f}",  # 输出 ey 的全局 Z 分量。
                    "local_z_global_x": f"{local_z.x:.15f}",  # 输出 ez 的全局 X 分量。
                    "local_z_global_y": f"{local_z.y:.15f}",  # 输出 ez 的全局 Y 分量。
                    "local_z_global_z": f"{local_z.z:.15f}",  # 输出 ez 的全局 Z 分量。
                    # 绝对点积允许 local-z 正向因 I/J 次序反号，但截面高度轴必须仍与竖向共线。
                    "abs_local_z_dot_global_z": f"{abs(local_z.dot(global_vertical)):.15f}",
                    "iyy_mm4": f"{section.iyy_mm4:.12f}",  # 输出绕 local-y 的惯性矩，单位 mm^4。
                    "izz_mm4": f"{section.izz_mm4:.12f}",  # 输出绕 local-z 的惯性矩，单位 mm^4。
                    "thickness_z_mm": f"{section.thickness_z_mm:.12f}",  # 输出 TKz，单位 mm。
                    "thickness_y_mm": f"{section.thickness_y_mm:.12f}",  # 输出 TKy，单位 mm。
                    # 输出 TSxz 无量纲值，并保留十五位小数以区分显式修正与旧缺省 1.0。
                    "shear_correction_xz": f"{section.shear_correction_xz:.15f}",
                    # 输出 TSxy 无量纲值，并保留十五位小数以区分两个剪切平面。
                    "shear_correction_xy": f"{section.shear_correction_xy:.15f}",
                    "acceptance_rule": acceptance_rule,  # 输出当前截面对应的人读验收规则。
                    "status": "PASS",  # PASS 表示该行已通过前置方向、尺寸、惯性与数量硬校验。
                }
            )


def write_rigid_connection_csv(path: Path, builder: ModelBuilder) -> None:
    """输出 MPC184 单元号、I/J 节点、来源语义和物理原因台账。

    参数：
        path: ``generated_rigid_connections.csv`` 的目标路径。
        builder: 已完成刚性连接编号的模型构建器。
    返回：无；写出的 CSV 不参与物理梁体积或质量空间化计算。
    """

    fieldnames = [
        "apdl_elem_id",  # ALL 主 rigid beam 或 UXYZ 共点 general joint 的稳定单元号。
        "offset_elem_id",  # UXYZ 前置偏置 rigid beam 的稳定单元号；ALL 为空。
        "offset_node_id",  # UXYZ 与原 slave 共点的零质量辅助节点号；ALL 为空。
        "master_node",  # 固定写在 EN 命令 I 端的主节点号。
        "slave_node",  # 固定写在 EN 命令 J 端的从节点号。
        "source_semantics",  # 迁移前 UXYZ 或 ALL 语义，仅用于追溯与数量闭合。
        "system",  # gate 或 passage_interface 等结构系统名称。
        "assembly_name",  # 当前连接所属的门架或横通道品名。
        "reason",  # 当前刚性连接的物理接口与建模目的。
    ]
    # 使用 UTF-8-SIG 让 Excel 可直接识别中文 reason 字段，同时保持标准 CSV 有效性。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        # DictWriter 按 fieldnames 的稳定顺序输出，避免不同 Python 版本改变列序。
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        # 表头逐项说明在相邻 Python 注释中，CSV 本身保持无注释的有效语法。
        writer.writeheader()
        # 每条逻辑连接恰写一行；UXYZ 行对应两个 MPC184，ALL 行对应一个 MPC184。
        for connection in builder.rigid_connections:
            # 写文件前再次拒绝未编号记录，防止 CSV 与 APDL 的单元号台账不一致。
            if connection.apdl_elem_id is None:
                # 抛错而不写出非法空单元号，使正式审计不会把半成品误判为通过。
                raise RuntimeError("MPC184 刚性连接 CSV 遇到未编号记录")
            # asdict 只输出记录声明的七个字段，顺序由 DictWriter 的 fieldnames 统一控制。
            writer.writerow(asdict(connection))


def write_calibration_csv(path: Path, sections: dict[str, SectionDef]) -> None:
    """输出后续独立标定所需的稳定材料/截面号和解析截面参数。"""

    fieldnames = [
        "group_key",
        "material_id",
        "section_id",
        "component_name",
        "area_mm2",
        "iyy_mm4",
        "izz_mm4",
        "torsion_j_mm4",
        "warping_iw_mm6",
        "thickness_z_mm",  # 记录 ASEC 第 11 项 TKz，即 local-z 截面外包络高度。
        "thickness_y_mm",  # 记录 ASEC 第 12 项 TKy，即 local-y 截面外包络宽度。
        "shear_correction_xz",  # 记录 ASEC 第 13 项 TSxz，即 xz 剪切修正。
        "shear_correction_xy",  # 记录 ASEC 第 14 项 TSxy，即 xy 剪切修正。
        "description",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for key, section in sections.items():
            writer.writerow(
                {
                    "group_key": key,
                    "material_id": section.material_id,
                    "section_id": section.section_id,
                    "component_name": SECTION_COMPONENT_NAMES[key],
                    "area_mm2": f"{section.area_mm2:.12f}",
                    "iyy_mm4": f"{section.iyy_mm4:.12f}",
                    "izz_mm4": f"{section.izz_mm4:.12f}",
                    "torsion_j_mm4": f"{section.torsion_j_mm4:.12f}",
                    "warping_iw_mm6": f"{section.warping_iw_mm6:.12f}",
                    # thickness_z_mm 输出 TKz，单位 mm，用于复核截面高度方向。
                    "thickness_z_mm": f"{section.thickness_z_mm:.12f}",
                    # thickness_y_mm 输出 TKy，单位 mm，用于复核截面宽度方向。
                    "thickness_y_mm": f"{section.thickness_y_mm:.12f}",
                    # shear_correction_xz 输出无量纲 TSxz，并保留十五位小数避免审计丢精度。
                    "shear_correction_xz": f"{section.shear_correction_xz:.15f}",
                    # shear_correction_xy 输出无量纲 TSxy，并保留十五位小数避免审计丢精度。
                    "shear_correction_xy": f"{section.shear_correction_xy:.15f}",
                    "description": section.description,
                }
            )


def write_passage_template_csvs(output_directory: Path, template: PassageTemplate) -> None:
    """输出交点拆分后的单品横通道局部节点/杆件，供几何可视化和人工抽查。"""

    node_path = output_directory / "passage_template_nodes.csv"
    with node_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = ["local_node_index", "q_mm", "r_mm", "z_mm", "role"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for index, (point, role) in enumerate(zip(template.points, template.point_roles)):
            writer.writerow(
                {
                    "local_node_index": index,
                    "q_mm": f"{point.x:.12f}",
                    "r_mm": f"{point.y:.12f}",
                    "z_mm": f"{point.z:.12f}",
                    "role": role,
                }
            )

    edge_path = output_directory / "passage_template_elements.csv"
    with edge_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = [
            "local_element_index",
            "n1_local",
            "n2_local",
            "section_key",
            "member",
            "source_member_id",
            "length_mm",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for index, (n1, n2, section_key, member, source_id) in enumerate(
            template.edges,
            start=1,
        ):
            writer.writerow(
                {
                    "local_element_index": index,
                    "n1_local": n1,
                    "n2_local": n2,
                    "section_key": section_key,
                    "member": member,
                    "source_member_id": source_id,
                    "length_mm": f"{template.points[n1].distance_to(template.points[n2]):.12f}",
                }
            )


def validate_built_model(builder: ModelBuilder, audit: BuildAudit) -> None:
    """检查 ID、局部轴、重复边、零长度、孤立物理节点及每品局部连通性。"""

    # node_ids 收集本生成器新增的全部物理节点和方向节点号，用于唯一性硬校验。
    node_ids = [node.apdl_node_id for node in builder.nodes]
    # physical_element_ids 只收集 BEAM188 物理梁号，避免质量台账把 MPC184 当成有体积杆件。
    physical_element_ids = [element.apdl_elem_id for element in builder.elements]
    # 未编号刚性连接表示 finalize 调用遗漏；此时不能安全构造完整新增单元号集合。
    if any(connection.apdl_elem_id is None for connection in builder.rigid_connections):
        # 在任何文件写出前失败，确保正式产物中不可能出现空或重复 MPC184 单元号。
        raise ValueError("存在未编号的 MPC184 刚性连接")
    # 上方已经排除 None；int 转换让后续集合比较具有明确的整数类型。
    rigid_element_ids = []
    # 逐条逻辑连接收集 ALL 的一个或 UXYZ 的两个 MPC184 单元号。
    for connection in builder.rigid_connections:
        # 主单元号已由上方 None 检查排除空值，可安全转成整数。
        rigid_element_ids.append(int(connection.apdl_elem_id))
        # UXYZ 额外收集前置偏置 rigid beam 单元号，ALL 的 None 不进入列表。
        if connection.offset_elem_id is not None:
            # offset_elem_id 只可能来自 UXYZ finalize 分支。
            rigid_element_ids.append(int(connection.offset_elem_id))
    # all_element_ids 合并物理梁与刚性梁，用于检查跨类型编号冲突。
    all_element_ids = physical_element_ids + rigid_element_ids
    # 新增节点号必须全局唯一，否则任一后写节点会覆盖此前几何定义。
    if len(node_ids) != len(set(node_ids)):
        # 重复节点号属于不可恢复的生成错误，必须立即停止。
        raise ValueError("新增节点号重复")
    # 物理梁和 MPC184 的联合号段必须唯一，防止刚性单元覆盖结构单元。
    if len(all_element_ids) != len(set(all_element_ids)):
        # 报错覆盖两类元素的共同编号空间，而不只检查物理 BEAM188。
        raise ValueError("新增单元号重复")
    # 在任何正式文件落盘前逐件校验 17679 根梁的 I/J/K，并硬闭合 H175 与 RHS50×30 数量。
    axis_audit_counts = validate_anisotropic_section_axes(builder)
    # 记录 2698 根 H175 的实际通过数量，使 build_audit.json 可机器判定方向审计是否闭合。
    audit.h175_axis_audit_count = axis_audit_counts["gate_bottom"]
    # 记录 2898 根 RHS50×30 的实际通过数量，使 50/30 朝向不再只依赖文字说明。
    audit.rhs50x30_axis_audit_count = axis_audit_counts["passage_rhs50x30"]

    duplicate_pairs = 0
    seen_pairs: set[tuple[int, int]] = set()
    physical_incidence: dict[int, int] = defaultdict(int)
    adjacency_by_assembly: dict[str, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    physical_nodes_by_assembly: dict[str, set[int]] = defaultdict(set)
    for node in builder.nodes:
        if not node.is_orientation:
            physical_nodes_by_assembly[node.assembly_name].add(node.apdl_node_id)
    for element in builder.elements:
        pair = tuple(sorted((element.n1, element.n2)))
        if pair in seen_pairs:
            duplicate_pairs += 1
        seen_pairs.add(pair)
        if element.length_mm <= GEOMETRY_TOL_MM:
            audit.zero_length_elements += 1
        physical_incidence[element.n1] += 1
        physical_incidence[element.n2] += 1
        graph = adjacency_by_assembly[element.assembly_name]
        graph[element.n1].add(element.n2)
        graph[element.n2].add(element.n1)

    # rigid_seen_pairs 单独记录 MPC184 无向端点对，用于区分刚性连接内部重复与物理边重合。
    rigid_seen_pairs: set[tuple[int, int]] = set()
    # master_degree 统计每个固定 I 端发出的星形连接数，验收当前最大设计度数为 4。
    master_degree: dict[int, int] = defaultdict(int)
    # 同一 assembly 内的 MPC184 rigid beam 建立六自由度刚体连通；索 slave 位于外部基础
    # 模型时不加入本地节点集合，避免把所有门架错误地视为一个局部组件。
    for connection in builder.rigid_connections:
        # pair 使用无向排序，使 I/J 顺序不同但连接相同的重复边仍能被识别。
        pair = tuple(sorted((connection.master_node, connection.slave_node)))
        # 与物理 BEAM188 重合会把同一端点对同时定义为有限杆和无限刚臂，必须单独计数。
        if pair in seen_pairs:
            # 每发现一对重合边就累计一次，最终统一硬失败并把数量写入异常信息。
            audit.rigid_connection_physical_edge_overlaps += 1
        # 同一刚性端点对重复出现会造成冗余约束和潜在奇异性，必须计数并拒绝。
        if pair in rigid_seen_pairs:
            # 重复无向对数量用于区分输入重复与星形 master 的正常多臂连接。
            audit.duplicate_rigid_connection_pairs += 1
        # 当前端点对加入已见集合，供后续连接检查重复。
        rigid_seen_pairs.add(pair)
        # 固定 I 端 master 的出度加 1，验证所有 spider 都按统一顺序生成。
        master_degree[connection.master_node] += 1
        if (
            connection.master_node in builder.node_by_id
            and connection.slave_node in builder.node_by_id
            and builder.node_by_id[connection.master_node].assembly_name == connection.assembly_name
            and builder.node_by_id[connection.slave_node].assembly_name == connection.assembly_name
        ):
            graph = adjacency_by_assembly[connection.assembly_name]
            graph[connection.master_node].add(connection.slave_node)
            graph[connection.slave_node].add(connection.master_node)
            physical_incidence[connection.master_node] += 1
            physical_incidence[connection.slave_node] += 1

    # max 使用 default=0 兼容未来无刚性连接的受控测试模型；正式模型当前应得到 4。
    audit.max_rigid_master_degree = max(master_degree.values(), default=0)
    # 任一重复刚性对都会生成冗余 MPC184，因此在写文件前硬失败。
    if audit.duplicate_rigid_connection_pairs:
        # 异常中保留精确数量，便于定位上游接口登记重复。
        raise ValueError(
            f"新增模型存在 {audit.duplicate_rigid_connection_pairs} 对重复 MPC184 端点"
        )
    # 任一刚性边与物理梁重合都会旁路有限刚度，属于明确拓扑错误。
    if audit.rigid_connection_physical_edge_overlaps:
        # 异常中保留精确数量，便于核对是否错误地把有限接口再次刚化。
        raise ValueError(
            f"新增模型存在 {audit.rigid_connection_physical_edge_overlaps} 对 MPC184/BEAM188 重合边"
        )

    audit.duplicate_element_pairs = duplicate_pairs
    if duplicate_pairs:
        raise ValueError(f"新增模型存在 {duplicate_pairs} 对重复节点边单元")
    if audit.zero_length_elements:
        raise ValueError(f"新增模型存在 {audit.zero_length_elements} 个零长度单元")

    unused_physical_nodes = [
        node_id
        for node_ids_for_assembly in physical_nodes_by_assembly.values()
        for node_id in node_ids_for_assembly
        if physical_incidence[node_id] == 0
    ]
    audit.unused_physical_nodes = len(unused_physical_nodes)
    if unused_physical_nodes:
        raise ValueError(f"新增模型存在 {len(unused_physical_nodes)} 个未连接物理节点")

    for assembly_name, assembly_nodes in physical_nodes_by_assembly.items():
        components = count_graph_components(assembly_nodes, adjacency_by_assembly[assembly_name])
        if components != 1:
            audit.disconnected_assemblies.append(f"{assembly_name}:{components}")
    if audit.disconnected_assemblies:
        raise ValueError("局部装配不连通：" + ", ".join(audit.disconnected_assemblies))


def write_audit_json(
    path: Path,
    builder: ModelBuilder,
    sections: dict[str, SectionDef],
    template: PassageTemplate,
    stations: Sequence[dict[str, str]],
    audit: BuildAudit,
) -> None:
    """写出包含数量、拓扑、截面和站位证据的 JSON 审计文件。"""

    audit.gate_count = len({element.assembly_name for element in builder.elements if element.system == "gate"})
    audit.passage_count = len(
        {element.assembly_name for element in builder.elements if element.system == "passage"}
    )
    audit.generated_node_count = len(builder.nodes)
    audit.generated_physical_node_count = sum(not node.is_orientation for node in builder.nodes)
    audit.generated_orientation_node_count = sum(node.is_orientation for node in builder.nodes)
    # 物理梁数量只统计 generated_elements.csv 中可参与几何体积和质量分配的 BEAM188。
    audit.generated_physical_beam_count = len(builder.elements)
    # MPC184 实际单元数按 ALL 每条 1 个、UXYZ 每条 2 个计算，当前闭合目标为 8202 个。
    audit.generated_mpc184_count = sum(
        # 基础 1 个表示 ALL 主 rigid beam 或 UXYZ 共点 general joint。
        1
        # UXYZ 额外增加 1 个 master→辅助节点的偏置 rigid beam。
        + (1 if connection.source_semantics == "UXYZ" else 0)
        # 逐条逻辑连接累加实际 MAPDL 单元数量。
        for connection in builder.rigid_connections
    )
    # 新增单元总数是物理梁与零质量刚性梁之和，用于完整模型单元计数验收。
    audit.generated_element_count = (
        # 第一项是有刚度、有截面但当前密度为零的 BEAM188 数量。
        audit.generated_physical_beam_count
        # 第二项是支持大转动且不参与体积质量分配的 MPC184 数量。
        + audit.generated_mpc184_count
    )
    # rigid_element_ids 用于在 JSON 中记录实际连续号段，空受控模型则输出 null 边界。
    rigid_element_ids = []
    # 逐条收集实际写入 APDL 的一个或两个 MPC184 单元号。
    for connection in builder.rigid_connections:
        # 主单元号非空时加入号段统计；空值只可能出现在受控的未 finalize 测试模型。
        if connection.apdl_elem_id is not None:
            # int 转换保持 JSON 只含数值或 null。
            rigid_element_ids.append(int(connection.apdl_elem_id))
        # UXYZ 偏置单元号非空时一并加入实际号段统计。
        if connection.offset_elem_id is not None:
            # int 转换保持 JSON 只含整数。
            rigid_element_ids.append(int(connection.offset_elem_id))

    payload = {
        "status": "PASS",
        "coordinate_transform": "APDL_X=CAD_y; APDL_Y=-CAD_x; APDL_Z=CAD_z",
        "units": "N-mm-tonne-s",
        "beam_type_id": BEAM_TYPE_ID,
        # 两个 MPC184 类型均与 MASS21 的 TYPE=71 分离，避免后续 include 相互覆盖类型定义。
        "mpc_type_ids": {
            # rigid_beam_all=72 实现来源语义为 ALL 的六自由度刚接。
            "rigid_beam_all": MPC_RIGID_BEAM_TYPE_ID,
            # general_joint_uxyz=73 实现来源语义为 UXYZ 的显式高罚刚度共点三平移约束。
            "general_joint_uxyz": MPC_TRANSLATION_JOINT_TYPE_ID,
        },
        # 两类公式的 KEYOPT 值逐项记录，使审计不必只依赖 APDL 文本检索。
        "mpc184_keyopts": {
            # KEYOPT(1)=1 表示 rigid beam，确保偏置刚臂保留主节点转动引起的从节点平移。
            "keyopt_1_rigid_beam": MPC_RIGID_BEAM_KEYOPT_VALUE,
            # KEYOPT(2)=0 表示直接消元公式，可随线性摄动保留当前连接。
            "keyopt_2_direct_elimination": MPC_DIRECT_ELIMINATION_KEYOPT_VALUE,
            # KEYOPT(5)=0 表示保留预应力摄动需要的几何刚度贡献。
            "keyopt_5_keep_geometric_stiffness": MPC_KEEP_GEOMETRIC_STIFFNESS_KEYOPT_VALUE,
            # KEYOPT(1)=16 表示 general joint，使 RDOF 可逐项限定为三项相对平移。
            "keyopt_1_general_joint": MPC_GENERAL_JOINT_KEYOPT_VALUE,
            # KEYOPT(4)=1 表示 displacement-only，只激活 UX/UY/UZ 并避免引入索节点转角。
            "keyopt_4_displacement_only": MPC_DISPLACEMENT_ONLY_KEYOPT_VALUE,
            # KEYOPT(2)=1 表示 penalty 公式，用有限但已验收的高罚刚度避免串联直接消元冲突。
            "keyopt_2_penalty_method": MPC_PENALTY_METHOD_KEYOPT_VALUE,
        },
        # penalty_parameters 独立记录 APDL 符号约定、绝对罚因子和小算例滑移门槛，便于结果复核。
        "penalty_parameters": {
            # 正值 5.0E10 是生成器内部保存的位移绝对罚因子幅值，单位为 N/mm。
            "translation_absolute_factor_n_per_mm": MPC_TRANSLATION_PENALTY_FACTOR,
            # APDL 的 SECJOINT,PNLT 以负号区分“绝对值”与“内部默认值缩放倍数”。
            "apdl_secjoint_pnlt_disp_value": -MPC_TRANSLATION_PENALTY_FACTOR,
            # 1.0E-5 mm 是当前共点三平移相对滑移的独立小算例验收上限。
            "verification_relative_slip_limit_mm": 1.0e-5,
            # 9.1944E-6 mm 是含线性摄动步骤的小算例实测最大相对滑移，低于验收上限。
            "verification_max_relative_slip_mm": 9.1944e-6,
        },
        "beam_density_tonne_per_mm3": 0.0,
        "audit": asdict(audit),
        "template": {
            "node_count": len(template.points),
            "element_count": len(template.edges),
            "intersection_points_added": template.intersection_points_added,
            "duplicate_subedges_removed": template.duplicate_subedges_removed,
            "connected_components": template.represented_components,
        },
        "sections": {key: asdict(section) for key, section in sections.items()},
        "station_gate_indices": [int(row["gate_index"]) for row in stations],
        # 刚性连接单元号段与物理梁号段分开记录，便于检查连续性和交叠。
        "rigid_connection_element_id_range": {
            # 空测试模型没有首号；正式模型当前首号应为 2017680。
            "minimum": min(rigid_element_ids) if rigid_element_ids else None,
            # 空测试模型没有末号；正式组合式 UXYZ 模型当前末号应为 2025881。
            "maximum": max(rigid_element_ids) if rigid_element_ids else None,
        },
        # 原 UXYZ/ALL 同时决定实际 MPC184 公式，并在此闭合两类连接数量。
        "rigid_connection_source_semantics_counts": {
            # 对两个允许标签逐项计数，正式验收目标依次为 3124 和 1954。
            semantics: sum(
                # 比较每条记录的来源标签，绝不把它重新解释为 MAPDL 自由度选项。
                connection.source_semantics == semantics
                for connection in builder.rigid_connections
            )
            for semantics in ("UXYZ", "ALL")
        },
        "component_counts": {
            "node_components": {name: len(ids) for name, ids in builder.node_groups.items()},
            "element_components": {name: len(ids) for name, ids in builder.element_groups.items()},
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary_markdown(
    path: Path,
    builder: ModelBuilder,
    template: PassageTemplate,
    station_rows: Sequence[dict[str, str]],
) -> None:
    """写出简洁的人读构建摘要和仍需在主模型中处理的边界条件。"""

    gate_elements = [element for element in builder.elements if element.system == "gate"]
    passage_elements = [element for element in builder.elements if element.system == "passage"]
    # uxyz_count 记录由“偏置 rigid beam + 共点高罚刚度 general joint”实现的原 UXYZ 语义数量。
    uxyz_count = sum(
        # 每条来源语义为 UXYZ 的记录贡献 1，正式闭合目标为 3124。
        connection.source_semantics == "UXYZ" for connection in builder.rigid_connections
    )
    # all_count 记录由 rigid beam 实现的原 ALL 语义数量。
    all_count = sum(
        # 每条来源语义为 ALL 的记录贡献 1，正式闭合目标为 1954。
        connection.source_semantics == "ALL" for connection in builder.rigid_connections
    )
    # actual_mpc184_count 按每条 ALL 一个、每条 UXYZ 两个计算实际写入 MAPDL 的 MPC184 数量。
    actual_mpc184_count = all_count + 2 * uxyz_count
    lines = [
        "# 有限刚度门架与横向通道生成摘要",
        "",
        "## 已生成",
        "",
        f"- 门架：142 品，BEAM188 单元 {len(gate_elements)} 个。",
        f"- 横向通道：21 品；单品拆分模板 {len(template.points)} 节点、{len(template.edges)} 杆件。",
        f"- 横向通道（含两端有限三角接口）：BEAM188 单元 {len(passage_elements)} 个。",
        f"- 新增节点总数：{len(builder.nodes)}（其中方向节点 {sum(n.is_orientation for n in builder.nodes)}）。",
        f"- 逻辑连接：UXYZ高罚刚度组合连接={uxyz_count} 个，ALL rigid beam={all_count} 个，总计 {len(builder.rigid_connections)} 个。",
        # 摘要明确记录罚因子与实测滑移，避免把 penalty joint 误称为数学上的零滑移精确约束。
        f"- UXYZ general joint：位移绝对罚因子={MPC_TRANSLATION_PENALTY_FACTOR:.6e} N/mm；独立小算例最大相对滑移=9.1944e-6 mm（门槛 1.0e-5 mm）。",
        f"- 实际 MPC184 单元：{actual_mpc184_count} 个；新增单元总数：{len(builder.elements) + actual_mpc184_count}（BEAM188+MPC184）；CERIG=0、CP=0。",
        f"- 模块交点自动补点：{template.intersection_points_added}；搭接重复子边删除：{template.duplicate_subedges_removed}。",
        "",
        "## dedicated station",
        "",
        "实际站位来自权威 MCT gate 集中荷载 -21.556 kN（导轮组 9.196 + 横通道三角门架 12.36），",
        "而不是旧的图纸链距比例映射。外部 CSV 可在后续修订，不需要改生成器。",
        "",
        "| 通道 | gate_index | Y (mm) | CW1/CW2 门架 |",
        "|---|---:|---:|---|",
    ]
    for row in station_rows:
        lines.append(
            f"| {row['name']} | {row['gate_index']} | {float(row['station_y_mm']):.3f} | "
            f"{row['cw1_gate_name']} / {row['cw2_gate_name']} |"
        )
    lines.extend(
        [
            "",
            "## 主模型集成时必须继续处理",
            "",
            "1. 本 include 必须替代旧 `apply_gate_rigid_diaphragm_couplings_xlong.inp` 与",
            "   `apply_crosspassage_lateral_couplings_xlong.inp`，不可与二者同时输入。",
            "2. 新梁密度为 0；门架/横通道现有 MCT 集中质量尚未从原 MASS21 中移出。",
            "   后续应按 `generated_elements.csv` 的体积/长度重新空间化，并闭合总质量、重心和转动惯量。",
            "3. 横通道端部三角接口采用 PHI102x4 有限刚度扇形杆。该拓扑是对 dedicated triangular gate",
            "   的明确等效，尚缺原设计节点释放/连接详图；后续应以模态和原图进一步校准，而不能声称局部应力精确。",
            # 第 4 项把已修复的 14 项 ASEC 和逐件方向台账列为正式集成的硬验收输入。
            "4. ASEC 已完整写入 A/I/J/Iw/TKz/TKy/TSxz/TSxy；正式集成必须要求",
            # 第二行明确验收文件和状态，防止只看可视化而遗漏 5596 根非对称梁的数值审计。
            "   `anisotropic_section_axis_audit.csv` 全部为 PASS，并用 MAPDL 原生回读截面属性。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    """定义并解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="生成有限刚度门架和 21 道完整横向通道 MAPDL include"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="项目根目录；默认从脚本位置自动发现",
    )
    parser.add_argument(
        "--stations-csv",
        type=Path,
        default=None,
        help="外部 dedicated station CSV；默认使用 builder/dedicated_cross_passage_stations.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="生成结果目录；默认 builder/generated",
    )
    parser.add_argument(
        "--node-start",
        type=int,
        default=2_000_001,
        help="新增节点号起点，默认 2000001",
    )
    parser.add_argument(
        "--element-start",
        type=int,
        default=2_000_001,
        help="新增单元号起点，默认 2000001",
    )
    parser.add_argument(
        "--elastic-modulus-mpa",
        type=float,
        default=206_000.0,
        help="六组材料初始弹性模量，默认 206000 MPa",
    )
    parser.add_argument(
        "--poisson-ratio",
        type=float,
        default=0.31,
        help="六组材料初始泊松比，默认 0.31",
    )
    parser.add_argument(
        "--density-tonne-per-mm3",
        type=float,
        default=0.0,
        help="兼容旧命令行的新增梁密度参数；独立 MASS21 流程要求且只允许精确值 0",
    )
    return parser.parse_args()


def main() -> None:
    """组织输入发现、模板/模型构建、自校验和全部输出。"""

    args = parse_arguments()
    if args.node_start <= 0 or args.element_start <= 0:
        raise ValueError("节点号和单元号起点必须为正整数")
    if args.elastic_modulus_mpa <= 0.0:
        raise ValueError("弹性模量必须为正")
    if not (-1.0 < args.poisson_ratio < 0.5):
        raise ValueError("泊松比必须位于 (-1, 0.5)")
    # 独立 MASS21 已承担门架和横通道质量；任何非零或非有限梁密度都会造成重复计重。
    if not math.isfinite(args.density_tonne_per_mm3) or args.density_tonne_per_mm3 != 0.0:
        # 精确拒绝全部非零值，使 build_audit.json 固定记录 0.0 与实际 APDL 命令一致。
        raise ValueError("独立 MASS21 流程要求新增梁密度严格等于 0 tonne/mm^3")

    project_root = discover_project_root(args.project_root)
    script_directory = Path(__file__).resolve().parent
    geometry_directory = (
        project_root / "02_CAD几何模型" / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"
    )
    module_directory = project_root / "output" / "freecad" / "cross_passage_local_coordinates"
    output_directory = (args.output_dir or (script_directory / "generated")).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    # 外部 station CSV 是模型输入接口。默认优先读取 V2.0 audit 目录中同时闭合
    # 站位和质量的权威总表；若该文件不存在，才在 builder 中从荷载映射自动派生。
    authoritative_station_csv = (
        project_root
        / "03_猫道动力分析"
        / "附件2-3全模态精确对齐_V2.0"
        / "audit"
        / "passage_station_authoritative_map.csv"
    )
    station_csv = (
        args.stations_csv
        or (
            authoritative_station_csv
            if authoritative_station_csv.is_file()
            else script_directory / "dedicated_cross_passage_stations.csv"
        )
    ).resolve()
    if station_csv.is_file():
        station_rows = normalize_external_station_rows(read_csv_rows(station_csv))
    else:
        station_rows = derive_dedicated_station_rows(geometry_directory)
        write_station_csv(station_csv, station_rows)
    validate_station_rows(station_rows)

    sections = build_section_definitions()
    gate_bottom_rope_x_coordinates = read_gate_bottom_rope_x_coordinates(
        geometry_directory
    )
    template = build_passage_template(
        module_directory,
        gate_bottom_rope_x_coordinates,
    )
    builder = ModelBuilder(sections, args.node_start, args.element_start)
    gate_infos = build_all_gates(builder, geometry_directory)
    build_all_passages(builder, template, station_rows, gate_infos)
    add_system_components(builder)
    # 全部物理 BEAM188 与刚性连接均已登记，此时统一把 MPC184 排在物理梁号段之后。
    builder.finalize_rigid_connection_ids()

    audit = BuildAudit()
    validate_built_model(builder, audit)

    apdl_path = output_directory / "apply_finite_gates_and_passages_v2.inp"
    write_apdl_include(
        apdl_path,
        builder,
        sections,
        args.elastic_modulus_mpa,
        args.poisson_ratio,
        args.density_tonne_per_mm3,
    )
    write_generated_node_csv(output_directory / "generated_nodes.csv", builder)
    write_generated_element_csv(output_directory / "generated_elements.csv", builder, sections)
    # 逐件写出 2698 根 H175 与 2898 根 RHS50×30 的 I/J/K 局部轴和 ASEC 主轴映射证据。
    write_anisotropic_axis_audit_csv(
        # 文件名稳定标识“非旋转对称截面方向审计”，供正式预检和人工复核共同使用。
        output_directory / "anisotropic_section_axis_audit.csv",
        # builder 提供正式 EN 单元实际使用的 I/J/K 节点与截面定义。
        builder,
    )
    # 新台账只记录 MPC184，文件名明确避免与已删除的 CERIG/CE 约束概念混淆。
    write_rigid_connection_csv(output_directory / "generated_rigid_connections.csv", builder)
    # legacy_constraint_path 指向旧版 CERIG 台账；保留它会让审计误读为当前仍生成约束方程。
    legacy_constraint_path = output_directory / "generated_constraints.csv"
    # 只删除当前受控输出目录中的确切旧文件名，不递归、不匹配其他用户文件。
    if legacy_constraint_path.is_file():
        # unlink 清理已经被新 rigid-connection 台账取代的单个陈旧生成文件。
        legacy_constraint_path.unlink()
    write_calibration_csv(output_directory / "calibration_groups.csv", sections)
    write_passage_template_csvs(output_directory, template)
    write_station_csv(output_directory / "resolved_dedicated_stations.csv", station_rows)
    write_audit_json(
        output_directory / "build_audit.json",
        builder,
        sections,
        template,
        station_rows,
        audit,
    )
    write_summary_markdown(
        output_directory / "build_summary.md",
        builder,
        template,
        station_rows,
    )

    # 标准输出仅给出关键路径和数量，便于批处理日志快速确认成功。
    print(f"PASS: {apdl_path}")
    # 第二行同时报告物理梁、MPC184 和总新增单元，避免旧 elements 字段只统计 BEAM188。
    print(
        # nodes 同时统计物理/方向节点和 UXYZ 共点辅助节点，辅助节点不参与质量分配。
        f"nodes={len(builder.nodes)}, physical_beams={len(builder.elements)}, "
        # rigid_mpc 报告实际 MPC184 单元数，而不是 5078 条逻辑连接数。
        f"rigid_mpc={audit.generated_mpc184_count}, "
        # total_elements 明确包含两种单元；stations 保持 21 道横通道站位计数。
        f"total_elements={len(builder.elements) + audit.generated_mpc184_count}, "
        f"stations={len(station_rows)}"
    )


if __name__ == "__main__":
    main()
