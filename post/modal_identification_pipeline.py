# -*- coding: utf-8 -*-
"""附件 2-3 前 14 个物理分支的可重复模态识别、全局分配与对比流水线。

本脚本面向两个阶段：

1. 立即对当前 V1 的 1～30 阶全节点 ``PRNSOL,U,COMP`` 结果做回归自测；
2. 当 V2 有 40～60 阶结果后，仅替换 ``--raw-dir`` 和可选构件节点注册表即可复用。

与旧脚本最重要的区别是：本脚本**不写死任何目标对应的 ANSYS 阶次**。它先从
每一阶全节点向量提取 L/V/T 参与、两幅猫道相位、主跨 S/A、符号波腹、跨域能量
和门架/横通道局部参与，再用 Hungarian 算法一次性完成 14×N 的全局一对一分配。

附件报告没有提供 R19.2 的质量归一化源模态向量，因此本脚本不能计算真正的 MAC。
这里输出的 ``feature_cost``、``shape_confidence`` 和 ``assignment_confidence`` 都是
透明可复核的形态特征指标，不得改称 MAC，也不得作为“源向量一致”的证据。

坐标约定：V1 主节点 CSV 采用旧坐标，读取时执行
``Xnew=Yold, Ynew=-Xold, Znew=Zold``；V2 补充节点表必须直接提供
``X_mm,Y_mm,Z_mm``，从而明确表示 X 顺桥、Y 横桥、Z 竖向。
"""

from __future__ import annotations

# argparse 负责把同一脚本用于当前 30 阶回归和未来 40～60 阶 V2 结果。
import argparse
# csv 负责读取附件表 4-1，并写出 Excel 可直接打开的 UTF-8 BOM 审计表。
import csv
# hashlib 为每个关键输入形成 SHA-256 指纹，保证结果可追溯到具体文件版本。
import hashlib
# json 用于输出机器可读的参数、哈希、退化子空间和分配摘要。
import json
# math 提供有限数校验、平方根、对数频差和置信度计算。
import math
# re 用于解析 MAPDL 数值行、频率表以及模态文件名中的阶次。
import re
# dataclass 为几何、模态、候选和目标提供字段明确的数据结构。
from dataclasses import dataclass
# datetime 记录本次流水线实际生成时刻。
from datetime import datetime
# Path 统一处理 Windows 中文路径，避免手工拼接反斜杠。
from pathlib import Path
# Iterable、Sequence 和 Any 用于明确函数参数与返回值中的集合/标量类型。
from typing import Any, Iterable, Sequence

# numpy 负责模态数组、弧长积分、近重根子空间旋转和数值统计。
import numpy as np
# pandas 负责合并主节点表与 V2 门架/横通道补充节点注册表。
import pandas as pd
# 明确使用无窗口后端，使批处理环境不会等待图形界面。
import matplotlib

matplotlib.use("Agg")

# pyplot 负责生成谱对比、代价矩阵、目标振型和局部参与图。
import matplotlib.pyplot as plt
# scipy.linalg.eigh 用广义特征分解在近重根子空间内寻找 V/T 主方向。
from scipy.linalg import eigh
# Hungarian 算法在全部目标和候选之间执行真正的全局一对一最小代价分配。
from scipy.optimize import linear_sum_assignment
# find_peaks 与 savgol_filter 分别计算显著波腹并抑制节点尺度数值噪声。
from scipy.signal import find_peaks, savgol_filter


# SCRIPT_DIR 是本脚本以及全部 CSV、图件、JSON、Markdown 输出所在目录。
SCRIPT_DIR = Path(__file__).resolve().parent
# OUTPUT_DIR 是本次运行的实际输出目录。默认仍为脚本目录；命令行 ``--output-dir``
# 可把 V1/V2 回归写入彼此独立的目录，避免一次回归静默覆盖另一次证据。
OUTPUT_DIR = SCRIPT_DIR
# V2_ROOT 是 ``附件2-3全模态精确对齐_V2.0``；未来原始结果通常放在此目录内。
V2_ROOT = SCRIPT_DIR.parent
# DYNAMIC_DIR 是共享 ``03_猫道动力分析`` 目录。
DYNAMIC_DIR = V2_ROOT.parent
# PROJECT_ROOT 是整个张靖皋大桥工作区根目录。
PROJECT_ROOT = DYNAMIC_DIR.parent
# CURRENT_V1_RAW_DIR 是尚未完成 V2 求解时用于回归自测的当前 1～30 阶结果目录。
CURRENT_V1_RAW_DIR = DYNAMIC_DIR / "第一阶模态验证_V1.0"
# PRIMARY_NODE_CSV 是 32 根底索及当前全部节点编号的权威 V1 主注册表。
PRIMARY_NODE_CSV = (
    PROJECT_ROOT
    / "02_CAD几何模型"
    / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"
    / "full_line_beam4_nodes.csv"
)
# REFERENCE_CSV 是从附件 2-3 表 4-1 逐项转录的 14 行权威频率表。
REFERENCE_CSV = SCRIPT_DIR / "reference_attachment_2_3_table4_1.csv"
# ATTACHMENT_PDF 是参考表及图 4-3～4-8 的原始文档，用于审计哈希而非自动 OCR。
ATTACHMENT_PDF = PROJECT_ROOT / "01_设计资料与规范" / "附件2-3：猫道结构抗风性能试验报告.pdf"

# 四个顺桥边界沿用经过审计的全线几何，单位均为 mm。
NORTH_SIDE_START_MM = 48_797.0
MAIN_SPAN_START_MM = 696_909.0
MAIN_SPAN_END_MM = 2_998_909.0
SOUTH_SIDE_END_MM = 3_724_185.0
SOUTH_AUX_END_MM = 4_221_093.0
# MAIN_SPAN_CENTER_MM 用于将主跨左半边镜像到右半边并判定 S/A。
MAIN_SPAN_CENTER_MM = (MAIN_SPAN_START_MM + MAIN_SPAN_END_MM) / 2.0

# 只有相邻频率相对间隙小于该值时，才把原始向量视为求解器任意基并尝试子空间旋转。
DEFAULT_DEGENERATE_RELATIVE_GAP = 1.0e-5
# 该阈值只用于发现“频率很近且方向强混合”的识别簇；它明显大于严格重根阈值，
# 因而这些簇内的线性组合绝不能被冒充为新的特征向量。当前阈值 1% 可覆盖
# V2 的 M3/M4（相对间隙约 0.60%），同时不会把一般相邻根随意合并。
DEFAULT_IDENTIFICATION_CLUSTER_RELATIVE_GAP = 1.0e-2
# 近重根子空间只有在每个原始基的 V+T 份额均达到该值时才按 V/T 旋转。
NORMAL_SUBSPACE_MIN_SHARE = 0.65
# 识别簇中的每个原始根在两个候选方向上的合计份额必须达到该值；否则频率接近
# 可能只是偶然，不足以认定为同一 L/T、L/V 或 V/T 混合子空间。
IDENTIFICATION_CLUSTER_AXES_MIN_SHARE = 0.80
# 若某一原始根已经有超过该阈值的单一方向份额，就把它视为可独立分类的纯根，
# 不再仅因邻根频率接近而降低其身份置信度。
IDENTIFICATION_CLUSTER_PURE_SHARE_LIMIT = 0.80
# 构造同方向/同 S-A 分支阶次时，候选在该方向至少应有该份额。0.30 允许
# M3/M4 这种约 50%-50% 的 L/T 混合根同时进入两个方向的簇级排序，纯根则自然通过。
FAMILY_RANK_MIN_DIRECTION_SHARE = 0.30
# 分支阶次只对主跨占比充分且 S/A 镜像余弦明确的候选定义；边跨或混合跨候选
# 不应因一次离散标签而得到看似精确的家族序号。
FAMILY_RANK_MIN_MAIN_SHARE = 0.70
FAMILY_RANK_MIN_SYMMETRY_COSINE = 0.80
# 主跨份额不足该值时，S/A 结果不可靠，代价函数会给予缺证据惩罚。
SYMMETRY_MIN_MAIN_SHARE = 0.40
# 局部参与比超过该尺度后，门架或横通道局部模态惩罚开始明显增加。
LOCAL_RELATIVE_RMS_SCALE = 0.25

# HUMAN_TEXT_ENCODING 给 Markdown 等面向 Windows 人工审阅的文本增加 UTF-8 BOM。
# BOM 不改变正文字符，却能避免旧版记事本、Excel 外壳和未显式指定编码的 PowerShell
# 把中文 UTF-8 误判为系统 ANSI；这是本交付的人类可读文本统一编码契约。
HUMAN_TEXT_ENCODING = "utf-8-sig"
# MACHINE_JSON_ENCODING 保持 JSON 为无 BOM 的标准 UTF-8，便于严格 JSON 解析器直接读取。
# JSON 中通过 ensure_ascii=False 保留中文，读取方应显式使用 UTF-8。
MACHINE_JSON_ENCODING = "utf-8"

# FLOAT_TOKEN 同时接受普通小数以及 MAPDL/Fortran 常见 E、D 科学计数法。
FLOAT_TOKEN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
# NODE_LINE_PATTERN 允许相邻负数没有空格，并忽略可选的第四列 USUM。
NODE_LINE_PATTERN = re.compile(
    rf"^\s*(\d+)\s+({FLOAT_TOKEN})\s*({FLOAT_TOKEN})\s*({FLOAT_TOKEN})"
    rf"(?:\s*({FLOAT_TOKEN}))?\s*$"
)
# MODE_FILE_PATTERN 自动从 ``mode_01_all_nodes.txt`` 等文件名提取任意位数阶次。
MODE_FILE_PATTERN = re.compile(r"^mode_(\d+)_all_nodes\.txt$", re.IGNORECASE)
# COMMA_FREQUENCY_PATTERN 解析 MAPDL ``*VWRITE`` 常见的“阶次,频率”两列格式。
# MAPDL 的 ``F8.0`` 会把整数阶次写成 ``1.``；可选小数点只用于兼容这种原生格式，
# 不放宽为任意浮点阶次，避免把其他两列表误认成模态频率。
COMMA_FREQUENCY_PATTERN = re.compile(rf"^\s*(\d+)(?:\.)?\s*,\s*({FLOAT_TOKEN})\s*$")
# STRICT_FREQUENCY_PATTERN 解析日志中连续打印的“阶次 频率”高精度两列格式。
STRICT_FREQUENCY_PATTERN = re.compile(rf"^\s*(\d+)\s+({FLOAT_TOKEN})\s*$")
# SET_LIST_PATTERN 解析 ``SET,LIST`` 中阶次、频率、荷载步、子步和累计步格式。
SET_LIST_PATTERN = re.compile(
    rf"^\s*(\d+)\s+({FLOAT_TOKEN})\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
)


@dataclass(frozen=True)
class ReferenceTarget:
    """保存附件表 4-1 的一个物理目标以及由标签推导的形态规则。

    属性：
        order：附件表中的顺序 1～14。
        label：稳定内部标签，例如 ``LS1`` 或 ``SIDE2``。
        display_label：图表中展示的标签；边跨项显示“边跨1/2/3”。
        description：附件原始中文说明，不擅自补写边跨方向。
        frequency_hz：附件表频率，单位 Hz。
        source_location：表号、PDF 物理页和印刷页定位。
        expected_type：主跨分支的 L/V/T；边跨项为 ``None``。
        expected_symmetry：主跨分支的 S/A；边跨项为 ``None``。
        expected_branch_rank：附件标签末尾数字给出的同方向、同 S/A 家族分支序号；
            边跨项为 ``None``。该序号是附件明示语义，不等同于波腹数。
        expected_lobes：仅在图 4-3～4-8 直接可见时登记的主跨符号波腹数；
            没有源振型图的目标为 ``None``，不得用理论序列填成伪观测。
        target_region：``main`` 或 ``side``，用于跨域代价。
        rule_basis：逐项说明哪些规则来自标签、哪些来自附件图以及哪些证据缺失。
    """

    order: int
    label: str
    display_label: str
    description: str
    frequency_hz: float
    source_location: str
    expected_type: str | None
    expected_symmetry: str | None
    expected_branch_rank: int | None
    expected_lobes: int | None
    target_region: str
    rule_basis: str


@dataclass(frozen=True)
class NodeRegistry:
    """保存全模型节点注册表及可供局部参与分析的构件分类。

    属性：
        frame：每行至少含 node_id、X_mm、Y_mm、Z_mm、family、component_class。
        node_ids：与 frame 行顺序一致的整数节点号数组。
        id_to_index：节点号到数组行号的映射，供 PRNSOL 流式解析使用。
        class_masks：bottom/gate/passage/crossbeam/other 五类布尔掩码。
    """

    frame: pd.DataFrame
    node_ids: np.ndarray
    id_to_index: dict[int, int]
    class_masks: dict[str, np.ndarray]


@dataclass(frozen=True)
class BottomGeometry:
    """保存 32 根底索共同网格、索面局部基和跨域积分信息。

    属性：
        registry_indices：形状 ``(32,n_station)``，直接索引 NodeRegistry 位移数组。
        node_ids：与 registry_indices 同形状的 MAPDL 节点号。
        family_names：按横桥 Y 从负到正排序的 32 个底索族名。
        y_mm：每根底索的平均横桥坐标。
        x_node_mm、z_node_mm：共同节点网格与竖向线形。
        x_mid_mm、ds_mm：索段中点顺桥坐标及弧长积分权重。
        tangent_x/tangent_z：索面切向单位向量的全局 X/Z 分量。
        normal_x/normal_z：索面法向单位向量的全局 X/Z 分量。
        negative_mask/positive_mask：两幅猫道各 16 根索的布尔掩码。
    """

    registry_indices: np.ndarray
    node_ids: np.ndarray
    family_names: tuple[str, ...]
    y_mm: np.ndarray
    x_node_mm: np.ndarray
    z_node_mm: np.ndarray
    x_mid_mm: np.ndarray
    ds_mm: np.ndarray
    tangent_x: np.ndarray
    tangent_z: np.ndarray
    normal_x: np.ndarray
    normal_z: np.ndarray
    negative_mask: np.ndarray
    positive_mask: np.ndarray


@dataclass(frozen=True)
class ModeData:
    """保存一个原始或线性组合模态的节点位移场。

    属性：
        source_modes：构成本向量的原始阶次元组。
        coefficients：与 source_modes 一一对应的线性组合系数。
        frequency_hz：原始频率或近重根组平均频率。
        field_id：稳定且唯一的候选标识。
        source_kind：``raw`` 或 ``degenerate_subspace``。
        registry_u：形状 ``(n_registry,3)`` 的 UX/UY/UZ 数组。
        bottom_u：形状 ``(32,n_station,3)`` 的底索位移数组。
        subspace_group：近重根组名；非近重根为空字符串。
    """

    source_modes: tuple[int, ...]
    coefficients: tuple[float, ...]
    frequency_hz: float
    field_id: str
    source_kind: str
    registry_u: np.ndarray
    bottom_u: np.ndarray
    subspace_group: str


@dataclass(frozen=True)
class Candidate:
    """保存可参与全局分配的一个物理候选及其形态特征。

    属性：
        candidate_id：分配矩阵列名，不与任何目标阶次绑定。
        source_modes：原始 ANSYS 阶次，可为近重根中的多个阶次。
        coefficients：形成候选向量的子空间系数。
        frequency_hz：候选频率，单位 Hz。
        source_kind：独立原始根或近重根规范方向。
        subspace_group：近重根组名，便于提示“同频但不同子空间方向”。
        features：方向、跨域、S/A、波腹和局部参与等标量特征。
        plot_data：两幅猫道有符号曲线以及用于判别的主曲线。
    """

    candidate_id: str
    source_modes: tuple[int, ...]
    coefficients: tuple[float, ...]
    frequency_hz: float
    source_kind: str
    subspace_group: str
    features: dict[str, Any]
    plot_data: dict[str, np.ndarray]


def to_float(token: str) -> float:
    """把 MAPDL 的 E/D 科学计数法字符串转换为有限浮点数。

    参数：
        token：来自 PRNSOL、频率表或 SET 列表的单个数值字符串。

    返回：
        可用于 numpy 计算的有限 ``float``。
    """

    # Python 不直接接受 Fortran 的 D 指数，因此先统一替换为 E。
    value = float(token.replace("D", "E").replace("d", "e"))
    # NaN/Inf 会让积分、特征分解和 Hungarian 代价失去意义，必须在入口拒绝。
    if not math.isfinite(value):
        raise ValueError(f"发现非有限数值：{token!r}")
    return value


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256，避免一次性读入大型 MAPDL 文本。

    参数：
        path：需要形成审计指纹的文件。

    返回：
        64 位小写十六进制哈希字符串。
    """

    # digest 保存增量哈希状态；1 MiB 分块兼顾机械盘读取效率和内存占用。
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        # 循环直到 read 返回空字节串；每个块只在内存中停留一次。
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv_rows(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """把同构字典行写为 UTF-8 BOM CSV。

    参数：
        path：目标 CSV 路径。
        rows：至少一行，且字段集合必须一致的字典序列。

    返回：
        无；成功时目标文件被完整覆盖。
    """

    # 空结果通常代表上游解析或筛选错误，拒绝生成没有表头的“成功”文件。
    if not rows:
        raise ValueError(f"拒绝写出空 CSV：{path}")
    # 第一行插入顺序定义稳定列序，便于版本差分和人工审查。
    fieldnames = list(rows[0].keys())
    # newline="" 避免 Windows csv 模块在行间再插入空行。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        # 每一行都经 DictWriter 按同一列序输出，额外字段会立刻报错。
        for row in rows:
            writer.writerow(row)


def finite_or_blank(value: Any) -> Any:
    """把非有限浮点数转换为空字符串，避免 CSV 中出现易误读的 ``nan``。

    参数：
        value：任意待输出标量。

    返回：
        有限数或原对象保持不变；NaN/Inf 返回空字符串。
    """

    # 只有 Python/numpy 浮点数需要有限性检查，字符串和整数直接保留。
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return ""
    return value


def derive_target_rule(
    label: str,
) -> tuple[str | None, str | None, int | None, int | None, str, str]:
    """从附件标签和已发表振型图提取方向、S/A、分支序号与波腹证据。

    参数：
        label：附件内部标签，例如 ``LA2``、``VS1`` 或 ``SIDE3``。

    返回：
        ``(expected_type, expected_symmetry, expected_branch_rank, expected_lobes,
        target_region, rule_basis)``。

    说明：
        附件表下注释明确把标签末尾数字定义成“第几阶同方向、同对称族振型”；
        它不是波腹数。图 4-3～4-8 只给出了表中前 7 个目标的源振型图，因此只有
        LS1/VA1/LA1/TA1/VS1/LS2/TS1 可以登记直接观察到的波腹数。VA2、LA2、
        TS2、VS2 没有源图，必须保留 ``expected_lobes=None``，改用附件明示的
        ``expected_branch_rank=2`` 识别，不再把“5 波腹”等理论序列伪装成证据。
    """

    # 边跨三项在附件中没有方向、对称性和具体跨位，只能约束“边跨占主导”。
    if label.upper().startswith("SIDE"):
        return (
            None,
            None,
            None,
            None,
            "side",
            "附件仅标注边跨模态，未提供方向、对称性、家族序号或振型图",
        )

    # 标准分支必须满足“L/V/T + S/A + 正整数阶次”的标签格式。
    match = re.fullmatch(r"([LVT])([SA])(\d+)", label.upper())
    if match is None:
        raise ValueError(f"无法从附件标签推导形态规则：{label!r}")
    # expected_type 是横弯、竖弯或扭转的首字母。
    expected_type = match.group(1)
    # expected_symmetry 是关于主跨中点的正对称 S 或反对称 A。
    expected_symmetry = match.group(2)
    # ordinal 是同一方向和同一对称族内部的阶次编号；该定义直接来自表 4-1 注释。
    ordinal = int(match.group(3))

    # direct_lobes 只转录图 4-3～4-8 能直接辨认的主跨符号波腹；这里故意不用
    # 2n、2n±1 公式外推未刊出的第二阶目标，以保持观测与理论假设的边界。
    direct_lobes = {
        "LS1": 1,
        "VA1": 2,
        "LA1": 2,
        "TA1": 2,
        "VS1": 3,
        "LS2": 3,
        "TS1": 3,
    }
    normalized_label = label.upper()
    expected_lobes = direct_lobes.get(normalized_label)
    if expected_lobes is None:
        # 表中第二阶目标虽无图，但末尾数字 2 仍是直接证据；报告必须明确只按分支序号。
        rule_basis = (
            "附件表4-1标签明示同方向/同S-A家族第"
            f"{ordinal}阶；附件未给该目标振型图，波腹数不设先验"
        )
    else:
        # 前七项同时拥有标签分支序号和图中可见波腹，因此两类证据可独立交叉检查。
        rule_basis = (
            "附件表4-1标签明示家族第"
            f"{ordinal}阶；图4-3～4-8直接可见{expected_lobes}个主跨符号波腹"
        )
    return (
        expected_type,
        expected_symmetry,
        ordinal,
        expected_lobes,
        "main",
        rule_basis,
    )


def load_reference_targets(path: Path) -> list[ReferenceTarget]:
    """读取附件表 4-1 转录 CSV，并为每一行附加形态规则。

    参数：
        path：本目录中的 ``reference_attachment_2_3_table4_1.csv``。

    返回：
        按附件顺序排列的 14 个 ``ReferenceTarget``。
    """

    # CSV 必须存在且非空；否则分配没有权威频率基准。
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    # targets 保存逐行构造的不可变目标对象。
    targets: list[ReferenceTarget] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        # 每一行先解析稳定内部标签，再由标签推导独立于候选阶次的形态规则。
        for row in reader:
            label = str(row["internal_id"]).strip()
            (
                expected_type,
                expected_symmetry,
                expected_branch_rank,
                expected_lobes,
                target_region,
                rule_basis,
            ) = derive_target_rule(label)
            targets.append(
                ReferenceTarget(
                    order=int(row["order"]),
                    label=label,
                    display_label=str(row["derived_display_label"]).strip(),
                    description=str(row["description"]).strip(),
                    frequency_hz=to_float(str(row["frequency_hz"])),
                    source_location=str(row["source_location"]).strip(),
                    expected_type=expected_type,
                    expected_symmetry=expected_symmetry,
                    expected_branch_rank=expected_branch_rank,
                    expected_lobes=expected_lobes,
                    target_region=target_region,
                    rule_basis=rule_basis,
                )
            )

    # 表 4-1 必须恰有 14 行且阶次连续，避免静默接受截断或重复转录。
    if [target.order for target in targets] != list(range(1, 15)):
        raise RuntimeError(
            f"附件目标阶次异常：实际={[target.order for target in targets]}，期望=1～14"
        )
    # 频率必须严格递增，这是附件表本身的谱顺序审计。
    frequencies = [target.frequency_hz for target in targets]
    if any(second <= first for first, second in zip(frequencies, frequencies[1:])):
        raise RuntimeError("附件表 4-1 频率不是严格递增。")
    return targets


def infer_component_class(family: str, explicit_class: str = "") -> str:
    """把节点族名或 V2 显式标签归入局部参与分析的五类。

    参数：
        family：节点注册表中的族名/构件名。
        explicit_class：补充注册表可直接给出的 ``component_class``。

    返回：
        ``bottom``、``gate``、``passage``、``crossbeam`` 或 ``other``。
    """

    # 显式分类优先级最高；它避免“cross_passage_tri_gate”等复合名称被误判。
    normalized_explicit = explicit_class.strip().lower()
    if normalized_explicit in {"bottom", "gate", "passage", "crossbeam", "other"}:
        return normalized_explicit

    # family_upper 统一大小写和常见分隔符，减少不同生成器命名风格的影响。
    family_upper = family.upper().replace("-", "_").replace(" ", "_")
    # 32 根用于全局物理识别的底索名称均含稳定的 ``_BOTTOM_`` 片段。
    if "_BOTTOM_" in family_upper:
        return "bottom"
    # 横通道必须在普通猫道横梁之前判断，避免 CROSS_PASSAGE 被 CROSS 片段误归类。
    if "CROSS_PASSAGE" in family_upper or "CROSSPASSAGE" in family_upper or "PASSAGE" in family_upper:
        return "passage"
    # 门架既可能写 GATE，也可能沿用 GANTRY。
    if "GATE" in family_upper or "GANTRY" in family_upper:
        return "gate"
    # CROSSBEAM 是单幅猫道自身横梁，仅作为局部畸变补充指标，不等同于横通道。
    if "CROSSBEAM" in family_upper or "CROSS_BEAM" in family_upper:
        return "crossbeam"
    return "other"


def normalize_primary_node_frame(path: Path) -> pd.DataFrame:
    """读取 V1 主节点表并转换为 X 顺桥坐标。

    参数：
        path：V1 ``full_line_beam4_nodes.csv`` 路径。

    返回：
        列名统一为 node_id/X_mm/Y_mm/Z_mm/family/component_class 的 DataFrame。
    """

    # raw_frame 保留原 CSV 全部附加列；下方只创建流水线需要的标准列。
    raw_frame = pd.read_csv(path)
    # required_columns 硬检查旧坐标主表的节点号、三坐标和节点族。
    required_columns = {"node_id", "x_mm", "y_mm", "z_mm", "family"}
    missing_columns = sorted(required_columns - set(raw_frame.columns))
    if missing_columns:
        raise RuntimeError(f"主节点表缺少列：{missing_columns}")

    # normalized 使用独立 DataFrame，避免原列与转换后列名并存造成坐标误用。
    normalized = pd.DataFrame()
    normalized["node_id"] = pd.to_numeric(raw_frame["node_id"], errors="raise").astype(np.int64)
    # 当前 X-long 模型由旧坐标执行 Xnew=Yold。
    normalized["X_mm"] = pd.to_numeric(raw_frame["y_mm"], errors="raise").astype(float)
    # 当前 Ynew=-Xold，正负号决定两幅猫道相位，不能省略。
    normalized["Y_mm"] = -pd.to_numeric(raw_frame["x_mm"], errors="raise").astype(float)
    # 竖向坐标在正交变换中保持不变。
    normalized["Z_mm"] = pd.to_numeric(raw_frame["z_mm"], errors="raise").astype(float)
    normalized["family"] = raw_frame["family"].astype(str)
    # 主表没有显式 component_class，逐族名执行稳定规则推断。
    normalized["component_class"] = [
        infer_component_class(family_name) for family_name in normalized["family"]
    ]
    # registry_source 记录节点标签来自哪个文件，便于补充表覆盖分类时审计。
    normalized["registry_source"] = str(path)
    return normalized


def normalize_supplemental_node_frame(path: Path) -> pd.DataFrame:
    """读取 V2 门架/横通道补充节点注册表。

    参数：
        path：必须提供 node_id、X_mm、Y_mm、Z_mm，并提供 family 或 component 字段的 CSV。

    返回：
        与主节点表相同标准列的 DataFrame。

    说明：
        补充表不接受无坐标系声明的旧小写坐标列，以防把 X/Y 再旋转一次。V2 生成器
        应直接写大写 ``X_mm,Y_mm,Z_mm``；``component_class`` 最好显式写 gate/passage。
    """

    # raw_frame 读取补充表全部列；标准化只依赖下列必要字段。
    raw_frame = pd.read_csv(path)
    # 大写坐标列是“已经处于 X 顺桥系”的机器可读声明。
    required_coordinates = {"node_id", "X_mm", "Y_mm", "Z_mm"}
    missing_coordinates = sorted(required_coordinates - set(raw_frame.columns))
    if missing_coordinates:
        raise RuntimeError(
            f"V2 补充节点表 {path} 缺少明确 X-long 坐标列：{missing_coordinates}"
        )

    # family 可由 family/component/name 三个常见字段之一提供。
    family_column = next(
        (column for column in ("family", "component", "name") if column in raw_frame.columns),
        None,
    )
    if family_column is None:
        raise RuntimeError(f"V2 补充节点表 {path} 缺少 family/component/name 字段。")

    # normalized 逐列执行强制数值转换，任何空值或文本坐标都会立即暴露。
    normalized = pd.DataFrame()
    normalized["node_id"] = pd.to_numeric(raw_frame["node_id"], errors="raise").astype(np.int64)
    normalized["X_mm"] = pd.to_numeric(raw_frame["X_mm"], errors="raise").astype(float)
    normalized["Y_mm"] = pd.to_numeric(raw_frame["Y_mm"], errors="raise").astype(float)
    normalized["Z_mm"] = pd.to_numeric(raw_frame["Z_mm"], errors="raise").astype(float)
    normalized["family"] = raw_frame[family_column].astype(str)
    # explicit_values 在表未提供 component_class 时使用空字符串，让推断函数接管。
    if "component_class" in raw_frame.columns:
        explicit_values = raw_frame["component_class"].fillna("").astype(str)
    else:
        explicit_values = pd.Series([""] * len(raw_frame), index=raw_frame.index, dtype=str)
    normalized["component_class"] = [
        infer_component_class(family_name, explicit_class)
        for family_name, explicit_class in zip(normalized["family"], explicit_values)
    ]
    normalized["registry_source"] = str(path)
    return normalized


def build_node_registry(primary_path: Path, supplemental_paths: Sequence[Path]) -> NodeRegistry:
    """合并主节点表和任意数量的 V2 构件补充表。

    参数：
        primary_path：包含 32 根底索的 V1 权威主节点 CSV。
        supplemental_paths：未来 V2 新门架/横通道节点注册表列表，可为空。

    返回：
        去重、坐标一致且带构件分类的 ``NodeRegistry``。
    """

    # 主表必须存在且非空，它提供底索身份和共同网格。
    if not primary_path.is_file() or primary_path.stat().st_size == 0:
        raise FileNotFoundError(primary_path)
    # combined_by_id 以节点号为键，使补充表可为已有节点补充更精确的构件分类。
    combined_by_id: dict[int, dict[str, Any]] = {}
    # frames 第一项固定为主表，后续补充表按命令行顺序覆盖 family/class 标签。
    frames = [normalize_primary_node_frame(primary_path)]
    # 每个补充表都必须存在；缺失时不能静默丢掉门架/横通道局部参与分析。
    for supplemental_path in supplemental_paths:
        if not supplemental_path.is_file() or supplemental_path.stat().st_size == 0:
            raise FileNotFoundError(supplemental_path)
        frames.append(normalize_supplemental_node_frame(supplemental_path))

    # 逐表、逐行合并，显式检查同一节点号的物理坐标是否一致。
    for frame in frames:
        for row in frame.to_dict(orient="records"):
            node_id = int(row["node_id"])
            if node_id in combined_by_id:
                previous = combined_by_id[node_id]
                # coordinates 保存当前表坐标；previous_coordinates 保存已登记坐标。
                coordinates = np.asarray([row["X_mm"], row["Y_mm"], row["Z_mm"]], dtype=float)
                previous_coordinates = np.asarray(
                    [previous["X_mm"], previous["Y_mm"], previous["Z_mm"]], dtype=float
                )
                # 1e-6 mm 只容许 CSV 舍入误差，不容许同号节点对应不同几何点。
                if not np.allclose(coordinates, previous_coordinates, rtol=0.0, atol=1.0e-6):
                    raise RuntimeError(
                        f"节点 {node_id} 在注册表中坐标冲突：{previous_coordinates} vs {coordinates}"
                    )
                # 补充表的显式 family/class 用于替换主表的推断标签，坐标保持不变。
                previous["family"] = row["family"]
                previous["component_class"] = row["component_class"]
                previous["registry_source"] = row["registry_source"]
            else:
                combined_by_id[node_id] = row

    # 按节点号排序提供跨运行稳定的数组行序，便于审计 CSV 和哈希复核。
    combined_frame = pd.DataFrame(
        [combined_by_id[node_id] for node_id in sorted(combined_by_id)]
    ).reset_index(drop=True)
    # node_ids 与 DataFrame 行一一对应，后续位移数组直接使用该顺序。
    node_ids = combined_frame["node_id"].to_numpy(dtype=np.int64)
    # id_to_index 让流式 PRNSOL 解析无需保留包含无关节点的巨大 Python 字典。
    id_to_index = {int(node_id): index for index, node_id in enumerate(node_ids)}
    # class_masks 为每类节点建立布尔索引；即使某类当前不存在也保留全 False 掩码。
    component_classes = combined_frame["component_class"].astype(str).str.lower().to_numpy()
    class_masks = {
        class_name: component_classes == class_name
        for class_name in ("bottom", "gate", "passage", "crossbeam", "other")
    }
    return NodeRegistry(combined_frame, node_ids, id_to_index, class_masks)


def build_bottom_geometry(registry: NodeRegistry) -> BottomGeometry:
    """从合并节点注册表恢复 32 根底索共同网格及索面局部基。

    参数：
        registry：已经转换到 X 顺桥坐标系的节点注册表。

    返回：
        可供弧长积分和两幅猫道相位分析的 ``BottomGeometry``。
    """

    # bottom_rows 只选 component_class=bottom，排除门架索和普通横梁节点。
    bottom_rows = registry.frame.loc[registry.class_masks["bottom"]].copy()
    # family_summary 统计每个索族的平均 Y 和节点数，并按 Y 从负到正排列。
    family_summary = (
        bottom_rows.groupby("family", sort=False)
        .agg(y_mm=("Y_mm", "mean"), count=("node_id", "size"))
        .sort_values("y_mm")
    )
    # 当前物理模型应有两幅各 16 根、合计 32 根底索。
    if len(family_summary) != 32:
        raise RuntimeError(f"底索族数为 {len(family_summary)}，期望 32。")
    # 所有索族必须共享同一站点数，才能用矩阵形式做逐站断面分解。
    if family_summary["count"].nunique() != 1:
        raise RuntimeError("各底索节点数不一致，无法构造共同顺桥网格。")

    # family_names 保存稳定顺序；后续数组第一维均与其一一对应。
    family_names = tuple(str(name) for name in family_summary.index)
    # node_id_rows 和 registry_index_rows 分别保存 MAPDL 节点号及注册表行号。
    node_id_rows: list[np.ndarray] = []
    registry_index_rows: list[np.ndarray] = []
    # x_reference/z_reference 在第一根索上初始化，其余 31 根必须逐点一致。
    x_reference: np.ndarray | None = None
    z_reference: np.ndarray | None = None
    # 逐索族按 X 排序，确保共同站点从北端到南端排列。
    for family_name in family_names:
        family_frame = bottom_rows[bottom_rows["family"] == family_name].sort_values("X_mm")
        current_x = family_frame["X_mm"].to_numpy(dtype=float)
        current_z = family_frame["Z_mm"].to_numpy(dtype=float)
        # 第一根索建立参考网格；后续分支只负责一致性校验。
        if x_reference is None:
            x_reference = current_x
            z_reference = current_z
        else:
            if not np.allclose(current_x, x_reference, rtol=0.0, atol=1.0e-9):
                raise RuntimeError(f"{family_name} 的 X 网格与其他底索不一致。")
            if not np.allclose(current_z, z_reference, rtol=0.0, atol=1.0e-9):
                raise RuntimeError(f"{family_name} 的 Z 线形与其他底索不一致。")
        current_node_ids = family_frame["node_id"].to_numpy(dtype=np.int64)
        node_id_rows.append(current_node_ids)
        registry_index_rows.append(
            np.asarray([registry.id_to_index[int(node_id)] for node_id in current_node_ids], dtype=np.int64)
        )

    # 32 族校验保证参考网格一定已初始化；assert 仅帮助类型检查器收窄类型。
    assert x_reference is not None and z_reference is not None
    # dx/dz 是相邻节点在索面内的坐标差；ds 是非均匀网格的物理弧长权重。
    dx = np.diff(x_reference)
    dz = np.diff(z_reference)
    ds = np.sqrt(dx * dx + dz * dz)
    # 零长或反向重复节点会破坏局部基和积分，必须立即报错。
    if np.any(ds <= 0.0):
        raise RuntimeError("底索共同网格存在零长索段。")
    # y_mm 决定两幅猫道掩码和断面线性插值顺序。
    y_mm = family_summary["y_mm"].to_numpy(dtype=float)
    negative_mask = y_mm < 0.0
    positive_mask = y_mm > 0.0
    if int(np.sum(negative_mask)) != 16 or int(np.sum(positive_mask)) != 16:
        raise RuntimeError("两幅猫道底索必须各为 16 根。")

    return BottomGeometry(
        registry_indices=np.vstack(registry_index_rows),
        node_ids=np.vstack(node_id_rows),
        family_names=family_names,
        y_mm=y_mm,
        x_node_mm=x_reference,
        z_node_mm=z_reference,
        x_mid_mm=(x_reference[:-1] + x_reference[1:]) / 2.0,
        ds_mm=ds,
        tangent_x=dx / ds,
        tangent_z=dz / ds,
        normal_x=-dz / ds,
        normal_z=dx / ds,
        negative_mask=negative_mask,
        positive_mask=positive_mask,
    )


def discover_mode_files(raw_dir: Path, maximum_modes: int | None) -> dict[int, Path]:
    """发现原始目录中的全节点模态文本并校验阶次连续性。

    参数：
        raw_dir：MAPDL 输出目录。
        maximum_modes：用户要求读取的最高阶；``None`` 表示使用全部已发现阶次。

    返回：
        以阶次为键、文件路径为值的连续字典。
    """

    # discovered 保存唯一阶次到文件的映射；重复阶次文件会立即暴露命名冲突。
    discovered: dict[int, Path] = {}
    # 只遍历 raw_dir 顶层，避免误把历史子目录的旧结果混入当前作业。
    for path in raw_dir.iterdir():
        # 目录或其他文件名不参与模态结果发现。
        if not path.is_file():
            continue
        match = MODE_FILE_PATTERN.match(path.name)
        if match is None:
            continue
        # mode_number 从任意位数字段解析，因此同时兼容 mode_01 和 mode_001。
        mode_number = int(match.group(1))
        if mode_number in discovered:
            raise RuntimeError(
                f"同一阶次出现多个全节点文件：{discovered[mode_number]} 与 {path}"
            )
        # 空文件代表 MAPDL 后处理未完成，不能当作可用阶次。
        if path.stat().st_size == 0:
            raise RuntimeError(f"全节点模态文件为空：{path}")
        discovered[mode_number] = path

    # 至少需要 14 个物理候选，且通常读取 30～60 阶以防高阶分支被漏检。
    if not discovered:
        raise FileNotFoundError(f"{raw_dir} 中未发现 mode_*_all_nodes.txt")
    # requested_max 在用户未指定时取已发现最大阶次；否则不得超过现有文件上界。
    requested_max = max(discovered) if maximum_modes is None else int(maximum_modes)
    if requested_max <= 0:
        raise ValueError("--max-modes 必须为正整数。")
    # expected_modes 强制从 M1 连续到 requested_max，防止频率与向量错位。
    expected_modes = set(range(1, requested_max + 1))
    missing_modes = sorted(expected_modes - set(discovered))
    if missing_modes:
        raise RuntimeError(f"全节点结果缺少连续阶次：{missing_modes}")
    # 返回时丢弃高于 requested_max 的文件，便于用同一 60 阶目录做 30 阶快速回归。
    return {mode_number: discovered[mode_number] for mode_number in range(1, requested_max + 1)}


def discover_frequency_sources(raw_dir: Path, explicit_paths: Sequence[Path]) -> list[Path]:
    """只接收一份显式频率来源，并拒绝目录中的任何第二来源。

    参数：
        raw_dir：模态原始输出目录。
        explicit_paths：命令行重复传入的 ``--frequency-source`` 路径。

    返回：
        只含一项的频率来源列表。

    说明：
        旧实现会扫描同一目录中的全部频率表、SET表和模态日志，再逐阶选择看似
        精度最高的记录。这会让不同作业进入同一个候选池。当前实现把“单作业”
        作为硬约束：调用者必须且只能显式提供一份来源，目录中发现第二来源就
        立即失败，不能再通过排序或精度评分择优。
    """

    # 零份来源会退回旧式自动发现，多份来源会重新形成跨作业选择；两者都禁止。
    if len(explicit_paths) != 1:
        raise RuntimeError(
            "必须且只能提供一次 --frequency-source；已永久禁用自动发现和多来源合并。"
        )

    # 相对路径严格相对于 raw_dir 解释；来源必须存在、非空且位于本作业目录内。
    explicit_path = explicit_paths[0]
    selected = explicit_path if explicit_path.is_absolute() else raw_dir / explicit_path
    if not selected.is_file() or selected.stat().st_size == 0:
        raise FileNotFoundError(selected)
    selected_resolved = selected.resolve()
    try:
        selected_resolved.relative_to(raw_dir.resolve())
    except ValueError as exc:
        raise RuntimeError("频率来源必须位于本次 raw-dir 内，禁止跨目录引用其他作业。") from exc

    # 扫描只用于发现冲突，任何冲突都会报错；扫描结果绝不再参与数值选择。
    discovered: set[Path] = set()
    for pattern in ("*frequenc*.txt", "*frequency*.txt", "*set_list*.txt"):
        discovered.update(path.resolve() for path in raw_dir.glob(pattern) if path.is_file())
    for path in raw_dir.glob("*.out"):
        lower_name = path.name.lower()
        if path.is_file() and ("mode" in lower_name or "modal" in lower_name):
            discovered.add(path.resolve())
    conflicting = sorted(path for path in discovered if path != selected_resolved)
    if conflicting:
        preview = ", ".join(path.name for path in conflicting[:8])
        raise RuntimeError(
            f"raw-dir 中发现 {len(conflicting)} 份未授权频率/SET/模态日志来源：{preview}。"
            "每个作业必须使用独立空目录。"
        )
    return [selected]


def validate_single_job_manifest(
    manifest_path: Path,
    raw_dir: Path,
    frequency_source: Path,
    mode_files: dict[int, Path],
) -> dict[str, Any]:
    """验证频率表和全部振型向量确实由同一份作业清单绑定。

    参数：
        manifest_path：本次作业唯一的JSON清单路径。
        raw_dir：只包含本次作业原始输出的独立目录。
        frequency_source：命令行显式指定的唯一频率来源。
        mode_files：已经发现的连续阶次到全节点向量文件的映射。

    返回：
        通过结构、路径和SHA-256核验后的清单字典。

    说明：
        清单必须提供 ``schema_version=1``、非空 ``run_id`` 和 ``job_name``、
        ``raw_dir``、``frequency_source``、``frequency_source_sha256``，以及逐阶
        ``mode_files`` 列表。任何缺项、额外阶次、路径不符或哈希不符都会立即失败。
    """

    # 清单本身必须位于当前raw_dir内，防止拿另一作业的清单为当前目录背书。
    manifest_resolved = manifest_path.resolve()
    raw_resolved = raw_dir.resolve()
    try:
        manifest_resolved.relative_to(raw_resolved)
    except ValueError as exc:
        raise RuntimeError("job manifest必须位于本次raw-dir内。") from exc
    if not manifest_resolved.is_file() or manifest_resolved.stat().st_size == 0:
        raise FileNotFoundError(manifest_resolved)

    # JSON结构必须是对象；列表或标量无法表达稳定的作业身份字段。
    manifest = json.loads(manifest_resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise RuntimeError("job manifest顶层必须是JSON对象。")
    if manifest.get("schema_version") != 1:
        raise RuntimeError("job manifest的schema_version必须为1。")
    for identity_key in ("run_id", "job_name"):
        if not isinstance(manifest.get(identity_key), str) or not manifest[identity_key].strip():
            raise RuntimeError(f"job manifest缺少非空字段：{identity_key}。")

    # raw_dir字段相对于清单目录解释，并必须精确指向命令行raw-dir。
    declared_raw = Path(str(manifest.get("raw_dir", "")))
    declared_raw = declared_raw if declared_raw.is_absolute() else manifest_resolved.parent / declared_raw
    if declared_raw.resolve() != raw_resolved:
        raise RuntimeError("job manifest中的raw_dir与命令行raw-dir不一致。")

    # 频率文件的路径和哈希必须同时一致，不能只凭相同文件名认定身份。
    declared_frequency = Path(str(manifest.get("frequency_source", "")))
    declared_frequency = (
        declared_frequency
        if declared_frequency.is_absolute()
        else raw_resolved / declared_frequency
    )
    if declared_frequency.resolve() != frequency_source.resolve():
        raise RuntimeError("job manifest中的frequency_source与命令行来源不一致。")
    expected_frequency_hash = str(manifest.get("frequency_source_sha256", "")).lower()
    if len(expected_frequency_hash) != 64 or sha256_file(frequency_source).lower() != expected_frequency_hash:
        raise RuntimeError("frequency_source的SHA-256与job manifest不一致。")

    # 每阶向量使用显式mode_number、path和sha256；阶次集合必须与实际发现结果完全相同。
    declared_modes = manifest.get("mode_files")
    if not isinstance(declared_modes, list):
        raise RuntimeError("job manifest的mode_files必须是逐阶对象列表。")
    declared_by_mode: dict[int, dict[str, Any]] = {}
    for row in declared_modes:
        if not isinstance(row, dict):
            raise RuntimeError("mode_files中的每一项都必须是JSON对象。")
        mode_number = int(row.get("mode_number", 0))
        if mode_number <= 0 or mode_number in declared_by_mode:
            raise RuntimeError(f"mode_files包含非法或重复阶次：{mode_number}。")
        declared_by_mode[mode_number] = row
    if set(declared_by_mode) != set(mode_files):
        raise RuntimeError("job manifest登记的模态阶次与raw-dir实际向量集合不一致。")

    # 对每个向量逐一核对真实路径和哈希；禁止未登记改名、复制或跨作业替换。
    for mode_number, actual_path in sorted(mode_files.items()):
        row = declared_by_mode[mode_number]
        declared_path = Path(str(row.get("path", "")))
        declared_path = declared_path if declared_path.is_absolute() else raw_resolved / declared_path
        if declared_path.resolve() != actual_path.resolve():
            raise RuntimeError(f"M{mode_number}向量路径与job manifest不一致。")
        expected_hash = str(row.get("sha256", "")).lower()
        if len(expected_hash) != 64 or sha256_file(actual_path).lower() != expected_hash:
            raise RuntimeError(f"M{mode_number}向量SHA-256与job manifest不一致。")
    return manifest


def parse_frequency_source(
    path: Path,
    available_modes: set[int],
) -> list[dict[str, Any]]:
    """从一个来源提取带格式可靠度的频率候选记录。

    参数：
        path：频率文本、SET 列表或 MAPDL 日志。
        available_modes：确有全节点向量的阶次集合，用于过滤无关表格。

    返回：
        字典列表，每项含 mode_number、frequency_hz、format_rank、precision_digits 和 source。
    """

    # lines 允许本地代码页标题乱码；所有需要的数值行均是 ASCII。
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # records 可同时保存同一来源中的逗号表、高精度两列表和 SET 列表，后续按分数选优。
    records: list[dict[str, Any]] = []

    # 逗号格式通常来自用户专门写出的 *VWRITE 文件，可靠度最高。
    for line_number, line in enumerate(lines, start=1):
        match = COMMA_FREQUENCY_PATTERN.match(line)
        if match is None:
            continue
        mode_number = int(match.group(1))
        if mode_number not in available_modes:
            continue
        token = match.group(2)
        frequency_hz = to_float(token)
        if frequency_hz <= 0.0:
            continue
        # precision_digits 用非数字符号剔除后的字符串长度近似数值有效位数。
        precision_digits = len(re.sub(r"[^0-9]", "", token))
        records.append(
            {
                "mode_number": mode_number,
                "frequency_hz": frequency_hz,
                "format_rank": 100,
                "precision_digits": precision_digits,
                "source": str(path),
                "line_number": line_number,
                "format": "comma_two_column",
            }
        )

    # strict_matches 保存所有严格两列行；只有连续递增至少三阶的行组才认作模态频率表。
    strict_matches: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        match = STRICT_FREQUENCY_PATTERN.match(line)
        if match is not None:
            strict_matches.append((line_number, int(match.group(1)), match.group(2)))
    # current_run 临时保存相邻文本行且阶次递增 1 的候选组。
    current_run: list[tuple[int, int, str]] = []
    # runs 收集长度至少三阶的连续表，从而排除日志中的任意两列计数。
    runs: list[list[tuple[int, int, str]]] = []
    for current in strict_matches:
        # 新记录只有同时满足“文本下一行”和“阶次+1”才延续当前频率表。
        if current_run and not (
            current[0] == current_run[-1][0] + 1 and current[1] == current_run[-1][1] + 1
        ):
            if len(current_run) >= 3:
                runs.append(current_run)
            current_run = []
        current_run.append(current)
    # 循环结束后必须处理最后一个未触发断点的连续组。
    if len(current_run) >= 3:
        runs.append(current_run)
    # 每个连续组逐行写入高可靠度记录；高精度日志优于 SET 的截断显示。
    for run in runs:
        for line_number, mode_number, token in run:
            if mode_number not in available_modes:
                continue
            frequency_hz = to_float(token)
            if frequency_hz <= 0.0:
                continue
            records.append(
                {
                    "mode_number": mode_number,
                    "frequency_hz": frequency_hz,
                    "format_rank": 90,
                    "precision_digits": len(re.sub(r"[^0-9]", "", token)),
                    "source": str(path),
                    "line_number": line_number,
                    "format": "strict_contiguous_two_column",
                }
            )

    # SET,LIST 格式可靠但通常只打印 8 位左右，作为缺少高精度表时的后备来源。
    for line_number, line in enumerate(lines, start=1):
        match = SET_LIST_PATTERN.match(line)
        if match is None:
            continue
        mode_number = int(match.group(1))
        if mode_number not in available_modes:
            continue
        token = match.group(2)
        frequency_hz = to_float(token)
        if frequency_hz <= 0.0:
            continue
        records.append(
            {
                "mode_number": mode_number,
                "frequency_hz": frequency_hz,
                "format_rank": 40,
                "precision_digits": len(re.sub(r"[^0-9]", "", token)),
                "source": str(path),
                "line_number": line_number,
                "format": "set_list",
            }
        )
    return records


def select_frequencies(
    sources: Sequence[Path],
    available_modes: set[int],
) -> tuple[dict[int, float], list[dict[str, Any]]]:
    """汇总多个来源，并为每个阶次选择最高可靠度/精度频率。

    参数：
        sources：由显式参数和自动发现得到的频率来源。
        available_modes：全节点结果的连续阶次集合。

    返回：
        ``(frequencies, audit_rows)``；前者用于计算，后者写入来源审计 CSV。
    """

    # 第二道防线：即使其他调用者绕过命令行入口，也不允许把多份来源送入选择器。
    if len(sources) != 1:
        raise RuntimeError("频率选择器只允许单一作业的一份来源。")

    # candidates_by_mode 按阶次归组；当前每阶记录只能来自同一份授权文件。
    candidates_by_mode: dict[int, list[dict[str, Any]]] = {
        mode_number: [] for mode_number in sorted(available_modes)
    }
    for source_order, source in enumerate(sources):
        # source_order 只在格式和精度完全相同时用于稳定打破平局。
        parsed_records = parse_frequency_source(source, available_modes)
        for record in parsed_records:
            record["source_order"] = source_order
            candidates_by_mode[int(record["mode_number"])].append(record)

    # frequencies 保存最终选值；audit_rows 记录为何选中某一来源。
    frequencies: dict[int, float] = {}
    audit_rows: list[dict[str, Any]] = []
    for mode_number in sorted(available_modes):
        mode_candidates = candidates_by_mode[mode_number]
        if not mode_candidates:
            raise RuntimeError(f"没有找到 M{mode_number} 的频率来源。")
        # 格式可靠度优先，其次有效位数，最后优先显式/较早来源。
        selected = max(
            mode_candidates,
            key=lambda row: (
                int(row["format_rank"]),
                int(row["precision_digits"]),
                -int(row["source_order"]),
            ),
        )
        selected_frequency = float(selected["frequency_hz"])
        frequencies[mode_number] = selected_frequency
        # 同阶全部高可靠度值应在各自打印精度可解释范围内一致；这里记录最大偏差供审计。
        differences = [abs(float(row["frequency_hz"]) - selected_frequency) for row in mode_candidates]
        maximum_difference = max(differences) if differences else 0.0
        audit_rows.append(
            {
                "mode_number": mode_number,
                "selected_frequency_hz": selected_frequency,
                "selected_source": selected["source"],
                "selected_line_number": selected["line_number"],
                "selected_format": selected["format"],
                "format_rank": selected["format_rank"],
                "precision_digits": selected["precision_digits"],
                "candidate_record_count": len(mode_candidates),
                "max_difference_across_sources_hz": maximum_difference,
            }
        )

    # 物理频率必须随阶次非降；严格重根容许完全相等。
    ordered_frequencies = [frequencies[mode_number] for mode_number in sorted(frequencies)]
    if any(second + 1.0e-12 < first for first, second in zip(ordered_frequencies, ordered_frequencies[1:])):
        raise RuntimeError("选定频率不随模态阶次非降，可能混入了错误日志表。")
    return frequencies, audit_rows


def parse_mode_file(
    path: Path,
    mode_number: int,
    frequency_hz: float,
    registry: NodeRegistry,
    geometry: BottomGeometry,
) -> ModeData:
    """流式解析一阶 PRNSOL，并仅保留注册表节点位移。

    参数：
        path：``mode_XX_all_nodes.txt``。
        mode_number：原始 ANSYS 阶次。
        frequency_hz：与该向量对应的选定频率。
        registry：需要保留的主模型和 V2 构件节点注册表。
        geometry：底索注册表索引，用于构造 ``bottom_u``。

    返回：
        ``source_kind=raw`` 的 ``ModeData``。
    """

    # registry_u 预分配为 NaN，便于解析结束后准确发现缺节点而非把缺失误当零位移。
    registry_u = np.full((len(registry.node_ids), 3), np.nan, dtype=float)
    # found 标记每个注册节点是否至少出现一次。
    found = np.zeros(len(registry.node_ids), dtype=bool)
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        # 逐行匹配能把内存限制在一个 6～10 MB 文本行以内，并跳过页眉/分页统计。
        for raw_line in stream:
            match = NODE_LINE_PATTERN.match(raw_line)
            if match is None:
                continue
            node_id = int(match.group(1))
            registry_index = registry.id_to_index.get(node_id)
            # 全节点文本可能含未纳入注册表的辅助节点，它们不影响当前识别，直接跳过。
            if registry_index is None:
                continue
            displacement = np.asarray(
                [to_float(match.group(2)), to_float(match.group(3)), to_float(match.group(4))],
                dtype=float,
            )
            # 分页重复打印同一节点时必须数值完全一致到合理打印精度。
            if found[registry_index] and not np.allclose(
                registry_u[registry_index], displacement, rtol=0.0, atol=1.0e-14
            ):
                raise RuntimeError(f"{path.name} 节点 {node_id} 出现矛盾重复位移。")
            registry_u[registry_index] = displacement
            found[registry_index] = True

    # 缺节点会让底索或局部参与指标产生系统偏差，因此不允许用零值补齐。
    if not np.all(found):
        missing_node_ids = registry.node_ids[~found]
        preview = ",".join(str(int(node_id)) for node_id in missing_node_ids[:10])
        raise RuntimeError(
            f"{path.name} 缺少 {len(missing_node_ids)} 个注册节点；前10个={preview}"
        )
    # bottom_u 通过预先计算的二维注册表索引直接重排，无需 Python 双层节点循环。
    bottom_u = registry_u[geometry.registry_indices]
    return ModeData(
        source_modes=(mode_number,),
        coefficients=(1.0,),
        frequency_hz=frequency_hz,
        field_id=f"M{mode_number}",
        source_kind="raw",
        registry_u=registry_u,
        bottom_u=bottom_u,
        subspace_group="",
    )


def weighted_sum(values: np.ndarray, weights: np.ndarray) -> float:
    """计算一维密度与弧长权重的离散积分。

    参数：
        values：定义在索段中点的一维密度数组。
        weights：与 values 同形状的索段长度数组。

    返回：
        ``sum(values*weights)`` 的 Python 浮点数。
    """

    # 形状不一致通常代表节点值和索段值混用，必须显式报错。
    if values.shape != weights.shape:
        raise ValueError(f"加权数组形状不一致：{values.shape} vs {weights.shape}")
    return float(np.sum(values * weights))


def weighted_cosine(first: np.ndarray, second: np.ndarray, weights: np.ndarray) -> float:
    """计算不减均值的弧长加权余弦，保留振型相位和 S/A 信息。

    参数：
        first：第一条有符号顺桥曲线。
        second：第二条有符号顺桥曲线。
        weights：与曲线同形状的弧长权重。

    返回：
        [-1,1] 内的余弦；任一曲线近零时返回 NaN。
    """

    # numerator 是弧长内积；两个 norm 是相同权重下的 L2 范数。
    numerator = weighted_sum(first * second, weights)
    first_norm = math.sqrt(max(weighted_sum(first * first, weights), 0.0))
    second_norm = math.sqrt(max(weighted_sum(second * second, weights), 0.0))
    # 近零范数没有稳定相位含义，不强行返回 0。
    if first_norm <= np.finfo(float).eps or second_norm <= np.finfo(float).eps:
        return float("nan")
    return float(np.clip(numerator / (first_norm * second_norm), -1.0, 1.0))


def project_bottom(mode: ModeData, geometry: BottomGeometry) -> dict[str, np.ndarray]:
    """把底索节点位移投影到索段法向、切向和横桥方向。

    参数：
        mode：待分类的原始或组合模态。
        geometry：共同网格及局部索面单位向量。

    返回：
        normal/tangent/lateral 三个形状 ``(32,n_segment)`` 的数组。
    """

    # midpoint_u 用相邻节点平均近似索段中点位移，与 ds_mm 一一对应。
    midpoint_u = (mode.bottom_u[:, :-1, :] + mode.bottom_u[:, 1:, :]) / 2.0
    # ux/uy/uz 分别是 X 顺桥、Y 横桥、Z 竖向分量。
    ux = midpoint_u[:, :, 0]
    uy = midpoint_u[:, :, 1]
    uz = midpoint_u[:, :, 2]
    # normal 在垂直索线的 X-Z 方向上投影，避免把有垂度索的切向滑移误判为竖弯。
    normal = ux * geometry.normal_x[None, :] + uz * geometry.normal_z[None, :]
    # tangent 用于识别纵向/索面切向局部模态。
    tangent = ux * geometry.tangent_x[None, :] + uz * geometry.tangent_z[None, :]
    # lateral 就是全局 Y 位移，因为坐标系已经转换为 X 顺桥。
    lateral = uy
    return {"normal": normal, "tangent": tangent, "lateral": lateral}


def classify_main_symmetry(
    profile: np.ndarray,
    geometry: BottomGeometry,
) -> tuple[str, float, float, float]:
    """判别有符号主跨曲线关于跨中的 S/A 镜像性。

    参数：
        profile：定义在底索索段中点的主导物理曲线。
        geometry：提供主跨 X 网格和弧长权重。

    返回：
        ``(class, cosine, normalized_residual, amplitude_ratio)``。
    """

    # main_mask 限制在主跨，left_mask 取含跨中的左半跨。
    main_mask = (
        (geometry.x_mid_mm >= MAIN_SPAN_START_MM)
        & (geometry.x_mid_mm <= MAIN_SPAN_END_MM)
    )
    left_mask = main_mask & (geometry.x_mid_mm <= MAIN_SPAN_CENTER_MM)
    if int(np.sum(left_mask)) < 10:
        return "NA", float("nan"), float("nan"), float("nan")
    # left_x/left_profile/weights 是左半跨的实际非均匀网格数据。
    left_x = geometry.x_mid_mm[left_mask]
    left_profile = profile[left_mask]
    weights = geometry.ds_mm[left_mask]
    # mirror_x 把左半跨坐标镜像到右半跨；np.interp 统一两边网格位置。
    mirror_x = 2.0 * MAIN_SPAN_CENTER_MM - left_x
    right_mirrored = np.interp(
        mirror_x,
        geometry.x_mid_mm[main_mask],
        profile[main_mask],
    )
    # cosine 接近 +1 表示正对称，接近 -1 表示反对称。
    cosine = weighted_cosine(left_profile, right_mirrored, weights)
    # 两侧 RMS 用于防止“相位正确但一侧振幅近零”被误判为高置信 S/A。
    left_rms = math.sqrt(weighted_sum(left_profile * left_profile, weights) / float(np.sum(weights)))
    right_rms = math.sqrt(weighted_sum(right_mirrored * right_mirrored, weights) / float(np.sum(weights)))
    amplitude_ratio = right_rms / left_rms if left_rms > np.finfo(float).eps else float("nan")
    # sign 按余弦选择最接近的 S 或 A 符号，再计算归一化镜像残差。
    sign = 1.0 if cosine >= 0.0 else -1.0
    residual_rms = math.sqrt(
        weighted_sum((left_profile - sign * right_mirrored) ** 2, weights) / float(np.sum(weights))
    )
    normalization = math.sqrt(max(left_rms * left_rms + right_rms * right_rms, np.finfo(float).eps))
    normalized_residual = residual_rms / normalization

    # 高置信 S/A 同时要求相位、左右幅值比例和残差通过。
    if cosine >= 0.95 and 0.80 <= amplitude_ratio <= 1.25 and normalized_residual <= 0.25:
        symmetry_class = "S"
    elif cosine <= -0.95 and 0.80 <= amplitude_ratio <= 1.25 and normalized_residual <= 0.25:
        symmetry_class = "A"
    # 余弦达到 0.85 但幅值/残差未完全通过时只标“倾向”，不等同于确定分类。
    elif abs(cosine) >= 0.85:
        symmetry_class = "S倾向" if cosine > 0.0 else "A倾向"
    else:
        symmetry_class = "混合"
    return symmetry_class, cosine, normalized_residual, amplitude_ratio


def count_signed_lobes(
    profile: np.ndarray,
    geometry: BottomGeometry,
    lower_x_mm: float,
    upper_x_mm: float,
) -> tuple[int, int, int]:
    """计算指定跨域内的符号波腹、过零次数和绝对峰数。

    参数：
        profile：有符号顺桥主导曲线。
        geometry：提供索段中点 X 网格。
        lower_x_mm：分析区间左边界。
        upper_x_mm：分析区间右边界。

    返回：
        ``(signed_lobes, zero_crossings, absolute_peaks)``。
    """

    # region_mask 限制当前跨域；少于 10 点时无法可靠平滑和计峰。
    region_mask = (
        (geometry.x_mid_mm >= lower_x_mm)
        & (geometry.x_mid_mm <= upper_x_mm)
    )
    if int(np.sum(region_mask)) < 10:
        return 0, 0, 0
    # 统一到 801 点可使非均匀网格下的阈值、峰距口径保持稳定。
    uniform_x = np.linspace(lower_x_mm, upper_x_mm, 801)
    uniform_profile = np.interp(
        uniform_x,
        geometry.x_mid_mm[region_mask],
        profile[region_mask],
    )
    # 31 点三阶 Savitzky-Golay 只抑制节点尺度噪声，不改变 1～7 波腹拓扑。
    smooth_profile = savgol_filter(uniform_profile, window_length=31, polyorder=3)
    amplitude = float(np.max(np.abs(smooth_profile)))
    if amplitude <= np.finfo(float).eps:
        return 0, 0, 0
    # 2.5% 峰值以下视为零区，避免数值噪声反复翻转符号。
    threshold = 0.025 * amplitude
    signs = np.where(
        smooth_profile > threshold,
        1,
        np.where(smooth_profile < -threshold, -1, 0),
    )
    # sign_runs 只保留跨过零区后的真正非零符号变化。
    sign_runs: list[int] = []
    for sign_value in signs:
        # 零值既不新建波腹也不清除前一个有效符号。
        if sign_value == 0:
            continue
        if not sign_runs or int(sign_value) != sign_runs[-1]:
            sign_runs.append(int(sign_value))
    # 显著峰用 8% prominence 和 60 点最小间距，检测“同号双峰”等异常形态。
    peak_indices, _properties = find_peaks(
        np.abs(smooth_profile),
        prominence=0.08 * amplitude,
        distance=60,
    )
    signed_lobes = len(sign_runs)
    zero_crossings = max(signed_lobes - 1, 0)
    return signed_lobes, zero_crossings, int(len(peak_indices))


def interpolate_bottom_reference(
    mode: ModeData,
    geometry: BottomGeometry,
    node_x_mm: np.ndarray,
    node_y_mm: np.ndarray,
) -> np.ndarray:
    """在任意构件节点处插值底索断面的随动参考位移。

    参数：
        mode：待分析模态。
        geometry：32 根底索 X/Y 网格。
        node_x_mm：构件节点顺桥坐标数组。
        node_y_mm：构件节点横桥坐标数组。

    返回：
        形状 ``(n_node,3)`` 的断面线性随动参考位移。

    说明：
        先在共同 X 网格上逐索线性插值，再在 32 根索的 Y 坐标之间线性插值。
        因而整体平移和断面一阶转动不会被误计为门架/横通道局部变形；剩余 RMS 才是
        局部参与指标。该指标仍是位移形态比，不是构件应变能。
    """

    # 空构件类直接返回零行数组，调用方会输出 NaN 而不是误报 0 局部参与。
    if len(node_x_mm) == 0:
        return np.empty((0, 3), dtype=float)
    # x_index 定位每个构件节点左侧底索站点，并裁剪到有效插值区间。
    x_index = np.searchsorted(geometry.x_node_mm, node_x_mm, side="right") - 1
    x_index = np.clip(x_index, 0, len(geometry.x_node_mm) - 2)
    # x_left/x_right 和 x_fraction 构造顺桥线性插值权重。
    x_left = geometry.x_node_mm[x_index]
    x_right = geometry.x_node_mm[x_index + 1]
    x_fraction = (node_x_mm - x_left) / (x_right - x_left)
    x_fraction = np.clip(x_fraction, 0.0, 1.0)
    # values_at_x 形状为 (32,n_component_node,3)，一次性完成全部索的 X 插值。
    values_at_x = (
        mode.bottom_u[:, x_index, :] * (1.0 - x_fraction)[None, :, None]
        + mode.bottom_u[:, x_index + 1, :] * x_fraction[None, :, None]
    )
    # 转置后每个构件节点对应 32 根底索的三向位移。
    values_at_x = np.transpose(values_at_x, (1, 0, 2))
    # y_index 定位节点横桥坐标左侧索；跨出底索范围的门架端点使用边界外推截断。
    y_index = np.searchsorted(geometry.y_mm, node_y_mm, side="right") - 1
    y_index = np.clip(y_index, 0, len(geometry.y_mm) - 2)
    y_left = geometry.y_mm[y_index]
    y_right = geometry.y_mm[y_index + 1]
    y_fraction = (node_y_mm - y_left) / (y_right - y_left)
    y_fraction = np.clip(y_fraction, 0.0, 1.0)
    # row_indices 让 numpy 按每个节点自己的 y_index 取相邻两根索。
    row_indices = np.arange(len(node_y_mm), dtype=np.int64)
    left_values = values_at_x[row_indices, y_index, :]
    right_values = values_at_x[row_indices, y_index + 1, :]
    return left_values * (1.0 - y_fraction)[:, None] + right_values * y_fraction[:, None]


def component_local_metrics(
    mode: ModeData,
    registry: NodeRegistry,
    geometry: BottomGeometry,
) -> dict[str, Any]:
    """计算门架、横通道和猫道横梁的绝对/相对位移参与。

    参数：
        mode：待分析模态。
        registry：含构件分类和坐标的全节点表。
        geometry：底索断面参考插值所需网格。

    返回：
        每类节点数量、RMS/底索 RMS、相对 RMS/底索 RMS 和全局峰值信息。
    """

    # bottom_amplitudes 与 bottom_rms 提供无量纲归一化尺度。
    bottom_amplitudes = np.linalg.norm(mode.bottom_u.reshape(-1, 3), axis=1)
    bottom_rms = math.sqrt(float(np.mean(bottom_amplitudes * bottom_amplitudes)))
    bottom_peak = float(np.max(bottom_amplitudes))
    # registry_amplitudes 用于定位全注册表最大位移族和整体/底索比。
    registry_amplitudes = np.linalg.norm(mode.registry_u, axis=1)
    registry_rms = math.sqrt(float(np.mean(registry_amplitudes * registry_amplitudes)))
    global_peak_index = int(np.argmax(registry_amplitudes))
    global_peak_row = registry.frame.iloc[global_peak_index]

    # output 先登记所有模态共有的尺度与全局峰值信息。
    output: dict[str, Any] = {
        "bottom_rms": bottom_rms,
        "registry_rms_over_bottom_rms": registry_rms / bottom_rms,
        "global_peak_over_bottom_peak": float(registry_amplitudes[global_peak_index]) / bottom_peak,
        "global_peak_family": str(global_peak_row["family"]),
        "global_peak_component_class": str(global_peak_row["component_class"]),
        "global_peak_x_mm": float(global_peak_row["X_mm"]),
    }
    # 三类有限刚度构件分别计算；crossbeam 仅用于辅助识别截面局部畸变。
    for class_name in ("gate", "passage", "crossbeam"):
        class_mask = registry.class_masks[class_name]
        node_count = int(np.sum(class_mask))
        output[f"{class_name}_node_count"] = node_count
        # 当前 V1 没有实体横通道节点时输出 NaN，明确区分“未建模”和“相对运动为零”。
        if node_count == 0:
            output[f"{class_name}_rms_over_bottom"] = float("nan")
            output[f"{class_name}_relative_rms_over_bottom"] = float("nan")
            continue
        # class_u 是当前构件类全部节点的三向位移。
        class_u = mode.registry_u[class_mask, :]
        class_amplitude = np.linalg.norm(class_u, axis=1)
        class_rms = math.sqrt(float(np.mean(class_amplitude * class_amplitude)))
        # class_frame 提供每个构件节点的 X/Y 坐标，用于剔除底索断面随动分量。
        class_frame = registry.frame.loc[class_mask]
        reference_u = interpolate_bottom_reference(
            mode,
            geometry,
            class_frame["X_mm"].to_numpy(dtype=float),
            class_frame["Y_mm"].to_numpy(dtype=float),
        )
        relative_u = class_u - reference_u
        relative_amplitude = np.linalg.norm(relative_u, axis=1)
        relative_rms = math.sqrt(float(np.mean(relative_amplitude * relative_amplitude)))
        output[f"{class_name}_rms_over_bottom"] = class_rms / bottom_rms
        output[f"{class_name}_relative_rms_over_bottom"] = relative_rms / bottom_rms
    return output


def compute_mode_features(
    mode: ModeData,
    registry: NodeRegistry,
    geometry: BottomGeometry,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """提取一阶模态的 L/V/T、相位、跨域、S/A、波腹和局部参与特征。

    参数：
        mode：原始特征向量或近重根子空间线性组合。
        registry：节点族及门架/横通道分类。
        geometry：底索共同网格、局部索面基和弧长权重。

    返回：
        ``(features, plot_data)``；前者只含标量，后者保存有符号顺桥曲线。

    说明：
        这里的“能量”是弧长加权位移平方，仅用于形态份额，并不是结构应变能、
        有效模态质量或质量矩阵内积。因附件源向量缺失，它也不是 MAC。
    """

    # projected 保存 32 根底索在索面法向、切向和横桥方向的索段中点位移。
    projected = project_bottom(mode, geometry)
    normal = projected["normal"]
    tangent = projected["tangent"]
    lateral = projected["lateral"]
    negative = geometry.negative_mask
    positive = geometry.positive_mask

    # 两幅猫道各自先对 16 根底索平均，避免 42.9 m 间距被单一截面回归混淆。
    normal_negative = np.mean(normal[negative, :], axis=0)
    normal_positive = np.mean(normal[positive, :], axis=0)
    lateral_negative = np.mean(lateral[negative, :], axis=0)
    lateral_positive = np.mean(lateral[positive, :], axis=0)
    tangent_negative = np.mean(tangent[negative, :], axis=0)
    tangent_positive = np.mean(tangent[positive, :], axis=0)

    # vertical_common 是两幅猫道同相法向运动；torsion_differential 是反相法向运动。
    vertical_common = (normal_positive + normal_negative) / 2.0
    torsion_differential = (normal_positive - normal_negative) / 2.0
    # lateral_common 是整体横弯；两幅横向反相/断面内部差异归入 distortion。
    lateral_common = (lateral_positive + lateral_negative) / 2.0
    # tangent_common 用于画纵向主导模态的一维曲线。
    tangent_common = (tangent_positive + tangent_negative) / 2.0

    # predicted_normal 按猫道侧别重构两幅平均法向运动，剩余量是单幅内部畸变。
    predicted_normal = np.where(
        positive[:, None],
        normal_positive[None, :],
        normal_negative[None, :],
    )
    # predicted_lateral 对全部 32 根索使用整体横弯常数项，反相横摆进入内部项。
    predicted_lateral = np.broadcast_to(lateral_common[None, :], lateral.shape)
    # 五个方向密度都定义在索段中点，系数 32 保持 V/T 与 32 根索总量同阶。
    component_density = {
        "L": 32.0 * lateral_common * lateral_common,
        "V": 32.0 * vertical_common * vertical_common,
        "T": 32.0 * torsion_differential * torsion_differential,
        "LONG": np.sum(tangent * tangent, axis=0),
        "DISTORTION": (
            np.sum((normal - predicted_normal) ** 2, axis=0)
            + np.sum((lateral - predicted_lateral) ** 2, axis=0)
        ),
    }
    # physical_mask 排除锚固尾段，仅积分报告所对应四个实体跨域。
    physical_mask = (
        (geometry.x_mid_mm >= NORTH_SIDE_START_MM)
        & (geometry.x_mid_mm <= SOUTH_AUX_END_MM)
    )
    # component_integrals 逐项做弧长积分；where 让掩码外密度严格为零。
    component_integrals = {
        component_name: weighted_sum(
            np.where(physical_mask, density, 0.0),
            geometry.ds_mm,
        )
        for component_name, density in component_density.items()
    }
    total_component_integral = float(sum(component_integrals.values()))
    if total_component_integral <= np.finfo(float).tiny:
        raise RuntimeError(f"{mode.field_id} 的底索位移形态积分近零。")
    # component_shares 是透明的无量纲方向份额，五项严格和为 1（舍入误差除外）。
    component_shares = {
        component_name: integral / total_component_integral
        for component_name, integral in component_integrals.items()
    }
    # dominant_key 仅按最大份额命名，不覆盖其余份额；混合模态仍能从 CSV 看出。
    dominant_key = max(component_shares, key=component_shares.get)
    dominant_label = {
        "L": "横弯L",
        "V": "竖弯V",
        "T": "扭转T",
        "LONG": "纵向/索面切向",
        "DISTORTION": "截面内部畸变",
    }[dominant_key]
    # sorted_shares 用最大份额与次大份额之差衡量方向判别余量。
    sorted_shares = sorted(component_shares.values(), reverse=True)
    type_margin = sorted_shares[0] - sorted_shares[1]

    # 每幅猫道总位移积分用于识别求解器是否给出“一幅动、一幅静”的退化任意基。
    negative_density = np.sum(
        normal[negative, :] ** 2 + tangent[negative, :] ** 2 + lateral[negative, :] ** 2,
        axis=0,
    )
    positive_density = np.sum(
        normal[positive, :] ** 2 + tangent[positive, :] ** 2 + lateral[positive, :] ** 2,
        axis=0,
    )
    negative_integral = weighted_sum(np.where(physical_mask, negative_density, 0.0), geometry.ds_mm)
    positive_integral = weighted_sum(np.where(physical_mask, positive_density, 0.0), geometry.ds_mm)
    catwalk_total = negative_integral + positive_integral
    catwalk_localization = max(negative_integral, positive_integral) / catwalk_total
    inactive_to_active_rms = math.sqrt(
        min(negative_integral, positive_integral) / max(negative_integral, positive_integral)
    )

    # profile 必须与 dominant_key 对应，才能让 S/A 和波腹具有明确物理含义。
    if dominant_key == "L":
        profile = lateral_common
        negative_profile = lateral_negative
        positive_profile = lateral_positive
        catwalk_phase_cosine = weighted_cosine(
            lateral_negative[physical_mask],
            lateral_positive[physical_mask],
            geometry.ds_mm[physical_mask],
        )
    elif dominant_key == "V":
        profile = vertical_common
        negative_profile = normal_negative
        positive_profile = normal_positive
        catwalk_phase_cosine = weighted_cosine(
            normal_negative[physical_mask],
            normal_positive[physical_mask],
            geometry.ds_mm[physical_mask],
        )
    elif dominant_key == "T":
        profile = torsion_differential
        negative_profile = normal_negative
        positive_profile = normal_positive
        catwalk_phase_cosine = weighted_cosine(
            normal_negative[physical_mask],
            normal_positive[physical_mask],
            geometry.ds_mm[physical_mask],
        )
    elif dominant_key == "LONG":
        profile = tangent_common
        negative_profile = tangent_negative
        positive_profile = tangent_positive
        catwalk_phase_cosine = weighted_cosine(
            tangent_negative[physical_mask],
            tangent_positive[physical_mask],
            geometry.ds_mm[physical_mask],
        )
    else:
        # 内部畸变没有唯一有符号平均量，使用法向标准差作为非负诊断包络。
        profile = np.std(normal, axis=0)
        negative_profile = np.std(normal[negative, :], axis=0)
        positive_profile = np.std(normal[positive, :], axis=0)
        catwalk_phase_cosine = float("nan")

    # phase_class 用连续余弦的 ±0.95 阈值给出可读相位，不把混合相位硬分到 V/T。
    if not math.isfinite(catwalk_phase_cosine):
        phase_class = "NA"
    elif catwalk_phase_cosine >= 0.95:
        phase_class = "两幅同相"
    elif catwalk_phase_cosine <= -0.95:
        phase_class = "两幅反相"
    else:
        phase_class = "两幅混合相位"

    # total_bottom_density 不依赖预先分类，用于跨域份额和主/边跨位置判别。
    total_bottom_density = np.sum(normal * normal + tangent * tangent + lateral * lateral, axis=0)
    region_bounds = {
        "north_side": (NORTH_SIDE_START_MM, MAIN_SPAN_START_MM),
        "main_span": (MAIN_SPAN_START_MM, MAIN_SPAN_END_MM),
        "south_side": (MAIN_SPAN_END_MM, SOUTH_SIDE_END_MM),
        "south_aux": (SOUTH_SIDE_END_MM, SOUTH_AUX_END_MM),
    }
    # region_integrals 保存四跨弧长积分，边界共用单个中点对最终份额影响远低于打印精度。
    region_integrals: dict[str, float] = {}
    for region_name, (lower_bound, upper_bound) in region_bounds.items():
        region_mask = (
            (geometry.x_mid_mm >= lower_bound)
            & (geometry.x_mid_mm <= upper_bound)
        )
        region_integrals[region_name] = weighted_sum(
            np.where(region_mask, total_bottom_density, 0.0),
            geometry.ds_mm,
        )
    region_total = float(sum(region_integrals.values()))
    region_shares = {
        region_name: integral / region_total
        for region_name, integral in region_integrals.items()
    }
    dominant_region = max(region_shares, key=region_shares.get)
    # location_class 使用 70%/30% 双阈值保留“全线混合”，避免强行二分。
    if region_shares["main_span"] >= 0.70:
        location_class = "主跨"
    elif region_shares["main_span"] <= 0.30:
        location_class = "边跨"
    else:
        location_class = "全线混合"

    # S/A 始终在主跨计算；主跨份额过低时仍保留余弦供审计，但类别标为 NA。
    symmetry_class_raw, symmetry_cosine, symmetry_residual, symmetry_amplitude_ratio = (
        classify_main_symmetry(profile, geometry)
    )
    symmetry_class = (
        symmetry_class_raw
        if region_shares["main_span"] >= SYMMETRY_MIN_MAIN_SHARE
        else "NA"
    )
    # main_lobes 是主跨目标分配使用的拓扑指标，与候选当前是否边跨主导无关。
    main_lobes, main_zero_crossings, main_absolute_peaks = count_signed_lobes(
        profile,
        geometry,
        MAIN_SPAN_START_MM,
        MAIN_SPAN_END_MM,
    )
    # dominant_lobes 用于边跨候选审计，区间取其实际主导区域。
    dominant_lower, dominant_upper = region_bounds[dominant_region]
    dominant_lobes, dominant_zero_crossings, dominant_absolute_peaks = count_signed_lobes(
        profile,
        geometry,
        dominant_lower,
        dominant_upper,
    )
    # lobe_quality_penalty 在同号多峰时为正，提醒“绝对峰数≠符号波腹数”。
    lobe_quality_penalty = abs(main_absolute_peaks - main_lobes)

    # features 先写入来源和全局形态，再追加构件局部参与指标。
    features: dict[str, Any] = {
        "field_id": mode.field_id,
        "source_kind": mode.source_kind,
        "source_modes": "/".join(str(number) for number in mode.source_modes),
        "coefficients": "/".join(f"{coefficient:.10g}" for coefficient in mode.coefficients),
        "subspace_group": mode.subspace_group,
        "frequency_hz": mode.frequency_hz,
        "share_L": component_shares["L"],
        "share_V": component_shares["V"],
        "share_T": component_shares["T"],
        "share_LONG": component_shares["LONG"],
        "share_DISTORTION": component_shares["DISTORTION"],
        "dominant_type": dominant_key,
        "dominant_type_label": dominant_label,
        "type_margin": type_margin,
        "catwalk_localization": catwalk_localization,
        "inactive_to_active_rms": inactive_to_active_rms,
        "catwalk_phase_cosine": catwalk_phase_cosine,
        "catwalk_phase_class": phase_class,
        "north_side_share": region_shares["north_side"],
        "main_span_share": region_shares["main_span"],
        "south_side_share": region_shares["south_side"],
        "south_aux_share": region_shares["south_aux"],
        "side_total_share": 1.0 - region_shares["main_span"],
        "dominant_region": dominant_region,
        "location_class": location_class,
        "symmetry_class": symmetry_class,
        "symmetry_cosine": symmetry_cosine,
        "symmetry_residual": symmetry_residual,
        "symmetry_amplitude_ratio": symmetry_amplitude_ratio,
        "main_signed_lobes": main_lobes,
        "main_zero_crossings": main_zero_crossings,
        "main_absolute_peaks": main_absolute_peaks,
        "main_lobe_quality_penalty": lobe_quality_penalty,
        "dominant_signed_lobes": dominant_lobes,
        "dominant_zero_crossings": dominant_zero_crossings,
        "dominant_absolute_peaks": dominant_absolute_peaks,
        "comparison_method": "形态特征分配（非MAC；附件源向量缺失）",
    }
    features.update(component_local_metrics(mode, registry, geometry))
    # plot_data 只保存每阶 4×n_segment 浮点曲线，远小于重复保留全节点数组。
    plot_data = {
        "x_mm": geometry.x_mid_mm.copy(),
        "profile": profile.copy(),
        "negative_catwalk_profile": negative_profile.copy(),
        "positive_catwalk_profile": positive_profile.copy(),
    }
    return features, plot_data


def find_degenerate_groups(
    frequencies: dict[int, float],
    relative_gap_limit: float,
) -> list[tuple[int, ...]]:
    """按相邻相对频差自动发现连续近重根组。

    参数：
        frequencies：连续阶次到频率的字典。
        relative_gap_limit：判定同一子空间的最大相对频差。

    返回：
        每项长度至少为 2 的连续阶次元组；不硬编码任何阶次。
    """

    # ordered_modes 明确按阶次排序；频率字典的插入顺序不作为算法前提。
    ordered_modes = sorted(frequencies)
    # groups 保存已经闭合的连续近重根组；current_group 保存正在扩展的组。
    groups: list[tuple[int, ...]] = []
    current_group: list[int] = []
    for first_mode, second_mode in zip(ordered_modes, ordered_modes[1:]):
        # 非连续阶次不允许跨空缺组成近重根组。
        if second_mode != first_mode + 1:
            if len(current_group) >= 2:
                groups.append(tuple(current_group))
            current_group = []
            continue
        # relative_gap 用两频平均归一化，避免同一绝对差在高低频采用不同口径。
        mean_frequency = (frequencies[first_mode] + frequencies[second_mode]) / 2.0
        relative_gap = abs(frequencies[second_mode] - frequencies[first_mode]) / mean_frequency
        if relative_gap <= relative_gap_limit:
            # 新组首先登记前一阶；已有组只追加后一阶，避免重复。
            if not current_group:
                current_group = [first_mode]
            current_group.append(second_mode)
        else:
            # 间隙超阈值时闭合当前组，并从下一对重新开始。
            if len(current_group) >= 2:
                groups.append(tuple(current_group))
            current_group = []
    # 最后一组不会再遇到“超阈值”分支，循环后单独闭合。
    if len(current_group) >= 2:
        groups.append(tuple(current_group))
    return groups


def combine_modes(
    modes: Sequence[ModeData],
    coefficients: np.ndarray,
    field_id: str,
    subspace_group: str,
) -> ModeData:
    """用给定系数线性组合多个近重根原始向量。

    参数：
        modes：属于同一连续近重根组的原始 ``ModeData``。
        coefficients：与 modes 等长的实系数数组。
        field_id：组合候选的唯一标识。
        subspace_group：例如 ``M2/M3`` 的组名。

    返回：
        系数按欧氏范数归一化后的 ``source_kind=degenerate_subspace`` 模态。
    """

    # 系数长度必须与原始基数量一致；否则 tensordot 会产生难以定位的维度错误。
    if len(modes) != len(coefficients):
        raise ValueError("近重根组合系数数量与原始基数量不一致。")
    # coefficient_norm 为零意味着广义特征分解失败，不能构造物理向量。
    coefficient_norm = float(np.linalg.norm(coefficients))
    if coefficient_norm <= np.finfo(float).eps:
        raise RuntimeError(f"{subspace_group} 得到零组合系数。")
    normalized_coefficients = np.asarray(coefficients, dtype=float) / coefficient_norm
    # registry_stack 第一维是子空间基，后两维是节点和三向位移。
    registry_stack = np.stack([mode.registry_u for mode in modes], axis=0)
    # bottom_stack 第一维同样是子空间基，便于一次 tensordot 得到组合底索场。
    bottom_stack = np.stack([mode.bottom_u for mode in modes], axis=0)
    registry_u = np.tensordot(normalized_coefficients, registry_stack, axes=(0, 0))
    bottom_u = np.tensordot(normalized_coefficients, bottom_stack, axes=(0, 0))
    # 严格/近重根共用组平均频率；报告会保留原始阶次和“同频子空间”状态。
    frequency_hz = float(np.mean([mode.frequency_hz for mode in modes]))
    return ModeData(
        source_modes=tuple(mode.source_modes[0] for mode in modes),
        coefficients=tuple(float(value) for value in normalized_coefficients),
        frequency_hz=frequency_hz,
        field_id=field_id,
        source_kind="degenerate_subspace",
        registry_u=registry_u,
        bottom_u=bottom_u,
        subspace_group=subspace_group,
    )


def canonicalize_normal_subspace(
    modes: Sequence[ModeData],
    geometry: BottomGeometry,
    group_name: str,
) -> list[ModeData]:
    """在近重根组内按 V/T 位移平方商旋转出规范物理方向。

    参数：
        modes：同一近重根组的原始向量，数量至少为 2。
        geometry：底索法向投影和弧长积分网格。
        group_name：稳定子空间名称。

    返回：
        与原始基数量相同、线性独立的规范组合列表。

    说明：
        对任意系数 c，构造 ``R_V=c^T A_V c / c^T(A_V+A_T)c``。广义特征值
        从大到小给出最 V-like 到最 T-like 的方向。它只消除求解器在严格重根中的
        任意基选择，不会把有明确频率分裂的独立模态强行旋转。
    """

    if len(modes) < 2:
        raise ValueError("近重根子空间至少需要两个原始向量。")
    # common_profiles/differential_profiles 的第一维是原始基，第二维是索段中点。
    common_profiles: list[np.ndarray] = []
    differential_profiles: list[np.ndarray] = []
    for mode in modes:
        normal = project_bottom(mode, geometry)["normal"]
        normal_negative = np.mean(normal[geometry.negative_mask, :], axis=0)
        normal_positive = np.mean(normal[geometry.positive_mask, :], axis=0)
        common_profiles.append((normal_positive + normal_negative) / 2.0)
        differential_profiles.append((normal_positive - normal_negative) / 2.0)
    common_matrix = np.vstack(common_profiles)
    differential_matrix = np.vstack(differential_profiles)
    # physical_mask 与主分类一致，排除锚固尾段。
    physical_mask = (
        (geometry.x_mid_mm >= NORTH_SIDE_START_MM)
        & (geometry.x_mid_mm <= SOUTH_AUX_END_MM)
    )
    weights = geometry.ds_mm[physical_mask]
    common_physical = common_matrix[:, physical_mask]
    differential_physical = differential_matrix[:, physical_mask]
    # gram_v/gram_t 是子空间内 V/T 弧长内积矩阵。
    gram_v = (common_physical * weights[None, :]) @ common_physical.T
    gram_t = (differential_physical * weights[None, :]) @ differential_physical.T
    gram_total = gram_v + gram_t
    # regularization 仅用于处理打印舍入导致的极小数值奇异，不改变可解析主方向。
    trace_scale = float(np.trace(gram_total)) / len(modes)
    if trace_scale <= np.finfo(float).tiny:
        raise RuntimeError(f"{group_name} 的法向子空间积分近零。")
    regularized_total = gram_total + np.eye(len(modes)) * trace_scale * 1.0e-12
    # eigh 返回升序特征值/向量；最大值最 V-like，因此随后倒序。
    eigenvalues, eigenvectors = eigh(gram_v, regularized_total)
    order = np.argsort(eigenvalues)[::-1]
    canonical_modes: list[ModeData] = []
    for rank, eigen_index in enumerate(order, start=1):
        coefficients = eigenvectors[:, eigen_index]
        # phase_name 仅描述子空间主方向，不把它预先绑定到附件 VA/VS/TA/TS 目标。
        phase_name = f"phase_principal_{rank}"
        field_id = f"{group_name}_{phase_name}"
        canonical_modes.append(combine_modes(modes, coefficients, field_id, group_name))
    return canonical_modes


def build_candidates(
    raw_modes: dict[int, ModeData],
    raw_features: dict[int, dict[str, Any]],
    degenerate_groups: Sequence[tuple[int, ...]],
    registry: NodeRegistry,
    geometry: BottomGeometry,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    """自动决定哪些近重根需要 V/T 规范化，并构造分配候选集。

    参数：
        raw_modes：全部已解析原始阶次向量。
        raw_features：每个原始阶次的方向份额等标量特征。
        degenerate_groups：按频率自动发现的连续近重根组。
        registry：计算组合向量局部参与所需节点表。
        geometry：计算组合向量全局形态所需底索网格。

    返回：
        ``(candidates, subspace_audit_rows)``。
    """

    # group_by_mode 让主循环 O(1) 判断当前阶次是否属于某一近重根组。
    group_by_mode: dict[int, tuple[int, ...]] = {}
    for group in degenerate_groups:
        for mode_number in group:
            if mode_number in group_by_mode:
                raise RuntimeError(f"M{mode_number} 同时属于两个近重根组。")
            group_by_mode[mode_number] = group

    # candidates 保存真正进入 Hungarian 的独立物理方向；processed_modes 防止组内重复处理。
    candidates: list[Candidate] = []
    processed_modes: set[int] = set()
    subspace_audit_rows: list[dict[str, Any]] = []
    for mode_number in sorted(raw_modes):
        if mode_number in processed_modes:
            continue
        group = group_by_mode.get(mode_number)
        # 非近重根直接把原始向量作为唯一候选，不做任何阶次映射假设。
        if group is None:
            mode = raw_modes[mode_number]
            features, plot_data = compute_mode_features(mode, registry, geometry)
            candidates.append(
                Candidate(
                    candidate_id=mode.field_id,
                    source_modes=mode.source_modes,
                    coefficients=mode.coefficients,
                    frequency_hz=mode.frequency_hz,
                    source_kind=mode.source_kind,
                    subspace_group="",
                    features=features,
                    plot_data=plot_data,
                )
            )
            processed_modes.add(mode_number)
            continue

        # group_modes/raw_normal_shares 用于判断该近重根是否真的是 V/T 法向退化子空间。
        group_modes = [raw_modes[number] for number in group]
        raw_normal_shares = [
            float(raw_features[number]["share_V"]) + float(raw_features[number]["share_T"])
            for number in group
        ]
        group_name = "/".join(f"M{number}" for number in group)
        # 只有每个原始基都以法向 V/T 为主时才旋转；L/局部构件偶然近频保持原始向量。
        should_canonicalize = all(share >= NORMAL_SUBSPACE_MIN_SHARE for share in raw_normal_shares)
        if should_canonicalize:
            canonical_modes = canonicalize_normal_subspace(group_modes, geometry, group_name)
            # 每个规范方向都是子空间内线性独立候选，数量与原始基相同，保证一对一资源不丢失。
            for canonical_mode in canonical_modes:
                features, plot_data = compute_mode_features(canonical_mode, registry, geometry)
                candidates.append(
                    Candidate(
                        candidate_id=canonical_mode.field_id,
                        source_modes=canonical_mode.source_modes,
                        coefficients=canonical_mode.coefficients,
                        frequency_hz=canonical_mode.frequency_hz,
                        source_kind=canonical_mode.source_kind,
                        subspace_group=canonical_mode.subspace_group,
                        features=features,
                        plot_data=plot_data,
                    )
                )
            action = "按V/T广义位移平方商旋转"
        else:
            # 非法向近频组逐个保留原始基，避免凭频率接近制造不存在的物理组合。
            for raw_mode in group_modes:
                features, plot_data = compute_mode_features(raw_mode, registry, geometry)
                candidates.append(
                    Candidate(
                        candidate_id=raw_mode.field_id,
                        source_modes=raw_mode.source_modes,
                        coefficients=raw_mode.coefficients,
                        frequency_hz=raw_mode.frequency_hz,
                        source_kind=raw_mode.source_kind,
                        subspace_group=group_name,
                        features=features,
                        plot_data=plot_data,
                    )
                )
            action = "保留原始基（并非V/T主导子空间）"
        # mean_frequency 和 maximum_relative_gap 用于审计判据是否真正满足阈值。
        group_frequencies = [raw_modes[number].frequency_hz for number in group]
        mean_frequency = float(np.mean(group_frequencies))
        maximum_relative_gap = max(group_frequencies) - min(group_frequencies)
        maximum_relative_gap /= mean_frequency
        subspace_audit_rows.append(
            {
                "subspace_group": group_name,
                "source_modes": "/".join(str(number) for number in group),
                "mean_frequency_hz": mean_frequency,
                "maximum_relative_gap": maximum_relative_gap,
                "raw_normal_share_min": min(raw_normal_shares),
                "raw_normal_share_max": max(raw_normal_shares),
                "action": action,
                "candidate_count": len(group),
            }
        )
        processed_modes.update(group)

    # 候选标识必须全局唯一，否则代价矩阵列和输出图会发生歧义。
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RuntimeError("生成了重复 candidate_id。")
    return candidates, subspace_audit_rows


def find_mixed_identification_clusters(
    raw_features: dict[int, dict[str, Any]],
    frequencies: dict[int, float],
    strict_degenerate_groups: Sequence[tuple[int, ...]],
    relative_gap_limit: float,
) -> tuple[dict[int, str], list[dict[str, Any]]]:
    """发现不能稳定逐根命名、但可稳定识别为二维方向簇的近频混合根。

    参数：
        raw_features：每个原始特征向量的方向份额、主跨份额和 S/A 指标。
        frequencies：原始阶次到频率的权威映射。
        strict_degenerate_groups：已经按严格重根逻辑处理的阶次组；这些组由
            ``canonicalize_normal_subspace`` 负责，不再重复标为“有限频差混合簇”。
        relative_gap_limit：相邻根可进入识别簇的最大相对频差。

    返回：
        ``(mode_to_cluster, audit_rows)``。前者把每个簇内原始阶次映射到如
        ``M3/M4`` 的稳定标识；后者完整记录判据和“只可簇级识别”的限制。

    说明：
        本函数**不旋转**有限频差的特征向量。不同特征值对应的线性组合不是新的
        特征向量；这里只认定“两个原始根共同张成 L/T 等二维识别空间”，并在最终
        结果中把簇内单根标签标为不可唯一。这与严格重根的合法基变换有本质区别。
    """

    if relative_gap_limit <= 0.0:
        raise ValueError("识别簇相对频差阈值必须为正数。")

    # strict_modes 汇总已被严格重根算法接管的原始阶次，防止同一证据被两套逻辑重复解释。
    strict_modes = {
        mode_number
        for group in strict_degenerate_groups
        for mode_number in group
    }
    # adjacency 形成一个只含“相邻且满足混合判据”边的无向图；连通分量即最终识别簇。
    adjacency: dict[int, set[int]] = {mode_number: set() for mode_number in raw_features}
    ordered_modes = sorted(raw_features)
    for first_mode, second_mode in zip(ordered_modes, ordered_modes[1:]):
        # 只有连续阶次才可能组成一个未漏根的局部识别簇。
        if second_mode != first_mode + 1:
            continue
        # 严格重根已能在等特征值子空间内合法选基，不应再降低为有限频差歧义簇。
        if first_mode in strict_modes or second_mode in strict_modes:
            continue
        # relative_gap 用两频平均归一化，与严格重根发现函数保持同一量纲口径。
        mean_frequency = (frequencies[first_mode] + frequencies[second_mode]) / 2.0
        relative_gap = abs(frequencies[second_mode] - frequencies[first_mode]) / mean_frequency
        if relative_gap > relative_gap_limit:
            continue

        first_features = raw_features[first_mode]
        second_features = raw_features[second_mode]
        # 两根都必须由主跨主导，否则边跨偶然近频不能被解释为主跨方向混合。
        if (
            float(first_features["main_span_share"]) < FAMILY_RANK_MIN_MAIN_SHARE
            or float(second_features["main_span_share"]) < FAMILY_RANK_MIN_MAIN_SHARE
        ):
            continue
        # S/A 类别必须相同且明确；不同对称族即使频率相近也属于独立物理分支。
        first_symmetry = str(first_features["symmetry_class"])
        second_symmetry = str(second_features["symmetry_class"])
        if first_symmetry not in {"S", "A"} or second_symmetry != first_symmetry:
            continue

        # direction_totals 从两根合计份额中选出最重要的两个 L/V/T 方向作为候选轴。
        direction_totals = {
            direction: (
                float(first_features[f"share_{direction}"])
                + float(second_features[f"share_{direction}"])
            )
            for direction in ("L", "V", "T")
        }
        selected_axes = tuple(
            direction
            for direction, _value in sorted(
                direction_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:2]
        )
        # 每根在这两个轴上的合计份额都必须很高，确保“方向混合”而不是内部畸变/纵向污染。
        axes_shares = []
        pure_shares = []
        for features in (first_features, second_features):
            direction_shares = [float(features[f"share_{axis}"]) for axis in selected_axes]
            axes_shares.append(sum(direction_shares))
            pure_shares.append(max(direction_shares))
        if min(axes_shares) < IDENTIFICATION_CLUSTER_AXES_MIN_SHARE:
            continue
        # 至少一根、且在当前二根场景下通常两根，都必须没有稳定的单一方向优势。
        # 若两根均已接近纯方向，则它们可直接分类，不应仅因近频而宣布身份不可唯一。
        if max(pure_shares) > IDENTIFICATION_CLUSTER_PURE_SHARE_LIMIT:
            continue

        # 当前边通过全部物理与数值判据，登记无向连接供后续连通分量合并。
        adjacency[first_mode].add(second_mode)
        adjacency[second_mode].add(first_mode)

    # 深度优先遍历只处理至少含一条边的节点；孤立原始根保持单根可分状态。
    mode_to_cluster: dict[int, str] = {}
    audit_rows: list[dict[str, Any]] = []
    visited: set[int] = set()
    for seed_mode in ordered_modes:
        if seed_mode in visited or not adjacency[seed_mode]:
            continue
        stack = [seed_mode]
        component: list[int] = []
        while stack:
            current_mode = stack.pop()
            if current_mode in visited:
                continue
            visited.add(current_mode)
            component.append(current_mode)
            # sorted(..., reverse=True) 只为得到可重复遍历顺序，物理结果不依赖栈顺序。
            stack.extend(sorted(adjacency[current_mode] - visited, reverse=True))
        component.sort()
        if len(component) < 2:
            continue

        # cluster_axes 以整个连通分量的合计份额重新计算，避免三根以上时沿用某一条边的轴。
        component_direction_totals = {
            direction: sum(
                float(raw_features[mode_number][f"share_{direction}"])
                for mode_number in component
            )
            for direction in ("L", "V", "T")
        }
        cluster_axes = tuple(
            direction
            for direction, _value in sorted(
                component_direction_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:2]
        )
        cluster_id = "/".join(f"M{mode_number}" for mode_number in component)
        for mode_number in component:
            mode_to_cluster[mode_number] = cluster_id

        component_frequencies = [frequencies[mode_number] for mode_number in component]
        mean_frequency = float(np.mean(component_frequencies))
        maximum_relative_span = (
            max(component_frequencies) - min(component_frequencies)
        ) / mean_frequency
        audit_rows.append(
            {
                "identification_cluster": cluster_id,
                "source_modes": "/".join(str(mode_number) for mode_number in component),
                "mean_frequency_hz": mean_frequency,
                "maximum_relative_span": maximum_relative_span,
                "axes": "/".join(cluster_axes),
                "symmetry": str(raw_features[component[0]]["symmetry_class"]),
                "action": (
                    "仅作簇级方向识别；保留原始特征向量，不旋转有限频差根，"
                    "簇内单根物理标签不可唯一"
                ),
            }
        )
    return mode_to_cluster, audit_rows


def enrich_identification_clusters_with_direction_subspace_audit(
    raw_modes: dict[int, ModeData],
    cluster_rows: Sequence[dict[str, Any]],
    geometry: BottomGeometry,
) -> None:
    """计算有限频差混合簇是否确实同时张成两个近纯方向的诊断商。

    参数：
        raw_modes：原始 MAPDL 特征向量；必须包含审计行 ``source_modes`` 中全部阶次。
        cluster_rows：有限频差混合簇审计行；函数原位追加方向商、系数和可分离度。
        geometry：底索局部法向/切向、猫道侧别和弧长权重。

    返回：
        无；每个审计行新增 ``axis_1_max_fraction``、``axis_2_max_fraction``、
        ``subspace_separability``、两组诊断组合系数及 ``combination_warning``。

    说明：
        对簇基系数 c，方向 1 商定义为
        ``c^T G1 c / c^T(G1+G2)c``。最大值接近 1 且最小值接近 0，说明该二维
        空间可分别取出近纯方向 1/2。由于簇内频率并不严格相等，这些组合仅用于
        证明“子空间方向可分”，**不是**新特征向量，也不参与频率映射或 Hungarian
        候选集。这样既能稳健认定 M3/M4 共同覆盖 L/T，又不会伪造纯 LA1/TA1 根。
    """

    # physical_mask 与正式 L/V/T 特征积分完全相同，排除不属于报告实体跨域的锚固尾段。
    physical_mask = (
        (geometry.x_mid_mm >= NORTH_SIDE_START_MM)
        & (geometry.x_mid_mm <= SOUTH_AUX_END_MM)
    )
    physical_weights = geometry.ds_mm[physical_mask]

    for row in cluster_rows:
        # axes 必须恰含两个 L/V/T 方向；发现阶段已按两个主方向生成该字段，仍做硬检查。
        axes = tuple(str(row["axes"]).split("/"))
        if len(axes) != 2 or any(axis not in {"L", "V", "T"} for axis in axes):
            raise RuntimeError(
                f"识别簇 {row['identification_cluster']} 的方向轴异常：{axes}"
            )
        source_modes = tuple(
            int(token)
            for token in str(row["source_modes"]).split("/")
            if token
        )
        if len(source_modes) < 2:
            raise RuntimeError(
                f"识别簇 {row['identification_cluster']} 少于两个原始根。"
            )

        # axis_profiles 按方向保存“子空间基 × 索段”的有符号曲线矩阵；所有方向采用
        # 与 compute_mode_features 相同的猫道平均/差分定义，保证诊断商可复核。
        axis_profiles: dict[str, list[np.ndarray]] = {axis: [] for axis in axes}
        for mode_number in source_modes:
            if mode_number not in raw_modes:
                raise KeyError(
                    f"识别簇 {row['identification_cluster']} 缺原始模态 M{mode_number}。"
                )
            projected = project_bottom(raw_modes[mode_number], geometry)
            normal = projected["normal"]
            lateral = projected["lateral"]
            normal_negative = np.mean(normal[geometry.negative_mask, :], axis=0)
            normal_positive = np.mean(normal[geometry.positive_mask, :], axis=0)
            lateral_negative = np.mean(lateral[geometry.negative_mask, :], axis=0)
            lateral_positive = np.mean(lateral[geometry.positive_mask, :], axis=0)
            directional_profiles = {
                "L": (lateral_positive + lateral_negative) / 2.0,
                "V": (normal_positive + normal_negative) / 2.0,
                "T": (normal_positive - normal_negative) / 2.0,
            }
            for axis in axes:
                axis_profiles[axis].append(directional_profiles[axis][physical_mask])

        # gram_matrices 是两个方向在原始簇基中的弧长位移平方 Gram 矩阵；共同系数 32
        # 与正式份额定义一致，虽会在商中约掉，但保留有助于量纲审计。
        gram_matrices: dict[str, np.ndarray] = {}
        for axis in axes:
            profile_matrix = np.vstack(axis_profiles[axis])
            gram_matrices[axis] = (
                32.0
                * (profile_matrix * physical_weights[None, :])
                @ profile_matrix.T
            )
        gram_total = gram_matrices[axes[0]] + gram_matrices[axes[1]]
        trace_scale = float(np.trace(gram_total)) / len(source_modes)
        if trace_scale <= np.finfo(float).tiny:
            raise RuntimeError(
                f"识别簇 {row['identification_cluster']} 的双方向积分近零。"
            )
        # 极小正则项只抵消 PRNSOL 打印舍入造成的奇异，不改变可解析的近 0/1 方向商。
        regularized_total = (
            gram_total
            + np.eye(len(source_modes)) * trace_scale * 1.0e-12
        )
        eigenvalues, eigenvectors = eigh(
            gram_matrices[axes[0]],
            regularized_total,
        )
        maximum_index = int(np.argmax(eigenvalues))
        minimum_index = int(np.argmin(eigenvalues))
        axis_1_fraction = float(np.clip(eigenvalues[maximum_index], 0.0, 1.0))
        axis_2_fraction = float(np.clip(1.0 - eigenvalues[minimum_index], 0.0, 1.0))

        # normalize_coefficients 仅把本次打印基下的诊断组合系数归一化，便于人工复算；
        # 系数会随原始向量幅值标定改变，因此报告不会把它解释成质量归一化结果。
        def normalize_coefficients(vector: np.ndarray) -> tuple[float, ...]:
            """把一个诊断广义特征向量归一化为欧氏范数 1 的可打印元组。

            参数：
                vector：定义在当前簇原始 PRNSOL 基上的实系数向量。

            返回：
                与 ``source_modes`` 等长的浮点元组；零范数会被拒绝。
            """

            norm = float(np.linalg.norm(vector))
            if norm <= np.finfo(float).eps:
                raise RuntimeError(
                    f"识别簇 {row['identification_cluster']} 得到零诊断系数。"
                )
            return tuple(float(value) for value in vector / norm)

        axis_1_coefficients = normalize_coefficients(eigenvectors[:, maximum_index])
        axis_2_coefficients = normalize_coefficients(eigenvectors[:, minimum_index])
        row["axis_1_max_fraction"] = axis_1_fraction
        row["axis_2_max_fraction"] = axis_2_fraction
        row["subspace_separability"] = min(axis_1_fraction, axis_2_fraction)
        row["axis_1_diagnostic_coefficients"] = "/".join(
            f"{value:.10g}" for value in axis_1_coefficients
        )
        row["axis_2_diagnostic_coefficients"] = "/".join(
            f"{value:.10g}" for value in axis_2_coefficients
        )
        row["combination_warning"] = (
            "诊断组合只证明子空间含近纯方向；有限频差下不是特征向量，"
            "系数也不是质量归一化系数"
        )


def annotate_candidates_with_identification_clusters(
    candidates: Sequence[Candidate],
    mode_to_cluster: dict[int, str],
    cluster_rows: Sequence[dict[str, Any]],
) -> None:
    """把有限频差混合簇元数据附到候选特征字典，供分配、CSV 和报告共同使用。

    参数：
        candidates：已经由原始根或严格重根规范方向构造的候选序列。
        mode_to_cluster：原始阶次到识别簇 ID 的映射。
        cluster_rows：``find_mixed_identification_clusters`` 的审计行。

    返回：
        无；函数原位补充每个 ``Candidate.features`` 中的审计字段。Candidate 本身
        虽为冻结数据类，但其 ``features`` 字典是有意保留的可扩展审计容器。
    """

    # cluster_metadata 使每个候选可 O(1) 取得方向轴与对称性说明。
    cluster_metadata = {
        str(row["identification_cluster"]): row
        for row in cluster_rows
    }
    for candidate in candidates:
        # source_cluster_ids 汇总候选所有原始来源所属的有限频差簇；严格重根规范方向
        # 通常没有该标记，因为严格组已在发现阶段排除。
        source_cluster_ids = {
            mode_to_cluster[mode_number]
            for mode_number in candidate.source_modes
            if mode_number in mode_to_cluster
        }
        if len(source_cluster_ids) > 1:
            raise RuntimeError(
                f"候选 {candidate.candidate_id} 跨越多个有限频差识别簇：{source_cluster_ids}"
            )
        if source_cluster_ids:
            cluster_id = next(iter(source_cluster_ids))
            metadata = cluster_metadata[cluster_id]
            candidate.features["identification_cluster"] = cluster_id
            candidate.features["identification_cluster_axes"] = str(metadata["axes"])
            candidate.features["individual_identity_status"] = "簇内单根标签不可唯一"
        else:
            candidate.features["identification_cluster"] = ""
            candidate.features["identification_cluster_axes"] = ""
            candidate.features["individual_identity_status"] = "单根可按当前形态特征分类"


def assign_candidate_family_branch_ranks(candidates: Sequence[Candidate]) -> None:
    """按频率为每个主跨 L/V/T-S/A 家族建立显式分支序号。

    参数：
        candidates：全部物理候选；函数读取方向份额、主跨份额、S/A 余弦和有限
            频差识别簇标识，并补充 ``family_rank_LS`` 等六个字段。

    返回：
        无；所有候选特征字典都会得到六个字段，未满足家族资格的值为 ``None``。

    说明：
        标签 ``TS2`` 的“2”来自附件明示的家族序号。对 M3/M4 这类 L/T 混合簇，
        两根共享同一个簇 token，因此该簇在 L-A 和 T-A 家族中都只计为第一分支，
        不会错误地把 M4 当成“第二阶 L-A”。这正是簇级稳健分类的关键。
    """

    family_names = [
        f"{direction}{symmetry}"
        for direction in ("L", "V", "T")
        for symmetry in ("S", "A")
    ]
    # 先为所有候选写入 None，保证 CSV 列稳定且代价函数不会读到遗留值。
    for candidate in candidates:
        for family_name in family_names:
            candidate.features[f"family_rank_{family_name}"] = None

    for direction in ("L", "V", "T"):
        for symmetry in ("S", "A"):
            family_name = f"{direction}{symmetry}"
            target_sign = 1.0 if symmetry == "S" else -1.0
            # eligible_entries 保存候选、计数 token 和频率；同一混合簇的多个原始根
            # 使用共同 token，从而在这个物理家族中只占一个分支序号。
            eligible_entries: list[tuple[Candidate, str, float]] = []
            for candidate in candidates:
                features = candidate.features
                direction_share = float(features[f"share_{direction}"])
                main_share = float(features["main_span_share"])
                symmetry_cosine = float(features["symmetry_cosine"])
                if direction_share < FAMILY_RANK_MIN_DIRECTION_SHARE:
                    continue
                if main_share < FAMILY_RANK_MIN_MAIN_SHARE:
                    continue
                if (
                    not math.isfinite(symmetry_cosine)
                    or target_sign * symmetry_cosine < FAMILY_RANK_MIN_SYMMETRY_COSINE
                ):
                    continue
                cluster_id = str(features.get("identification_cluster", ""))
                rank_token = cluster_id if cluster_id else candidate.candidate_id
                eligible_entries.append((candidate, rank_token, candidate.frequency_hz))

            # token_frequency 使用同一 token 内候选平均频率；混合簇内的微小分裂不应
            # 改变其相对于后续家族分支的顺序。
            token_frequency_lists: dict[str, list[float]] = {}
            for _candidate, rank_token, frequency_hz in eligible_entries:
                token_frequency_lists.setdefault(rank_token, []).append(frequency_hz)
            ordered_tokens = sorted(
                token_frequency_lists,
                key=lambda token: float(np.mean(token_frequency_lists[token])),
            )
            token_to_rank = {
                rank_token: rank
                for rank, rank_token in enumerate(ordered_tokens, start=1)
            }
            for candidate, rank_token, _frequency_hz in eligible_entries:
                candidate.features[f"family_rank_{family_name}"] = token_to_rank[rank_token]


def safe_local_ratio(features: dict[str, Any], key: str) -> float:
    """读取可选构件局部参与比；节点类缺失时返回 0 而不是制造惩罚。

    参数：
        features：候选形态特征字典。
        key：例如 ``gate_relative_rms_over_bottom``。

    返回：
        有限非负比值；缺类/NaN 返回 0。

    说明：
        返回 0 只用于“代价不因缺数据而增加”；输出 CSV/报告仍保留 NaN 和节点数，
        因而不会把“未建模横通道”误写成“横通道局部变形为零”。
    """

    value = features.get(key, float("nan"))
    # bool 也是 int 子类，但这里不会作为局部比值；统一转换 float 后检查有限性。
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric_value) or numeric_value < 0.0:
        return 0.0
    return numeric_value


def compute_target_candidate_cost(
    target: ReferenceTarget,
    candidate: Candidate,
) -> dict[str, float]:
    """计算一个目标—候选边的透明分项代价。

    参数：
        target：附件表 4-1 的一个物理目标。
        candidate：从原始或近重根规范向量得到的候选。

    返回：
        frequency/type/symmetry/branch_rank/lobe/region/local/quality 各项及 total_cost。

    权重原则：
        形态拓扑和附件明示的家族序号优先于单纯“就近配频”。10% 对数频差约贡献
        1.5；错一个有直接图证的波腹贡献 0.9；错一个家族分支序号贡献 2.0；
        完全错方向最多约 4；S/A 完全反号贡献 2。无源图目标不使用波腹代价，
        从而不会把 TS2/VS2 强行解释成未经附件证明的 5 波腹分支。
    """

    features = candidate.features
    # 对数频差对正负相对误差近似对称，避免高估/低估采用不同尺度。
    log_frequency_error = abs(math.log(candidate.frequency_hz / target.frequency_hz))
    frequency_cost = 1.5 * log_frequency_error / 0.10

    # 主跨 L/V/T 目标要求对应方向份额；边跨附件未细分方向，因此该项严格为零。
    if target.expected_type is None:
        type_cost = 0.0
    else:
        expected_share = float(features[f"share_{target.expected_type}"])
        # clip 防止极小数值舍入略超 [0,1]。
        type_cost = 4.0 * (1.0 - float(np.clip(expected_share, 0.0, 1.0)))

    # S/A 用连续镜像余弦而非离散标签；缺证据按中性最差一半处理。
    if target.expected_symmetry is None:
        symmetry_cost = 0.0
    else:
        symmetry_cosine = float(features["symmetry_cosine"])
        if math.isfinite(symmetry_cosine) and float(features["main_span_share"]) >= SYMMETRY_MIN_MAIN_SHARE:
            target_sign = 1.0 if target.expected_symmetry == "S" else -1.0
            symmetry_cost = 2.0 * (1.0 - target_sign * symmetry_cosine) / 2.0
        else:
            # 缺主跨能量或余弦不可算时，不能奖励也不能假定完全反号，取 1.5 的缺证据惩罚。
            symmetry_cost = 1.5

    # branch_rank_cost 直接落实附件标签末尾数字的语义。候选家族序号由频率排序、
    # 方向份额和 S/A 镜像证据共同建立；有限频差混合簇在每个家族中只计一次。
    if (
        target.expected_type is None
        or target.expected_symmetry is None
        or target.expected_branch_rank is None
    ):
        branch_rank_cost = 0.0
        candidate_branch_rank: int | None = None
    else:
        family_name = f"{target.expected_type}{target.expected_symmetry}"
        raw_candidate_rank = features.get(f"family_rank_{family_name}")
        if raw_candidate_rank is None or raw_candidate_rank == "":
            # 没有足够方向/主跨/S-A 证据进入该家族时，给予明确缺证据惩罚。
            branch_rank_cost = 3.0
            candidate_branch_rank = None
        else:
            candidate_branch_rank = int(raw_candidate_rank)
            rank_difference = abs(candidate_branch_rank - target.expected_branch_rank)
            # 单级差 2.0 足以阻止 VS2 因频率更近而从第二分支跳到第三分支；
            # 上限 6.0 防止高阶候选的序号项无限压倒其他全部形态证据。
            branch_rank_cost = 2.0 * min(rank_difference, 3)

    # 波腹代价只用于有明确主跨方向的标签；边跨三项没有附件振型图。
    if target.expected_lobes is None:
        lobe_cost = 0.0
        quality_cost = 0.0
    else:
        lobe_difference = abs(int(features["main_signed_lobes"]) - target.expected_lobes)
        # 差异上限 6 防止极端局部噪声让某一项无限压倒全部证据。
        lobe_cost = 0.9 * min(lobe_difference, 6)
        # 同号多峰说明波腹识别可能不稳，按峰/符号差额追加小惩罚。
        quality_cost = 0.35 * min(int(features["main_lobe_quality_penalty"]), 4)

    # 主跨目标奖励主跨占比；边跨目标只约束“非主跨”，不擅自指定南/北/辅助跨。
    main_share = float(features["main_span_share"])
    if target.target_region == "main":
        region_cost = 3.0 * (1.0 - main_share)
    else:
        region_cost = 4.0 * main_share

    # 门架、横通道和普通横梁的相对变形取最大值，防止局部构件模态混入前 14 分支。
    local_ratios = [
        safe_local_ratio(features, "gate_relative_rms_over_bottom"),
        safe_local_ratio(features, "passage_relative_rms_over_bottom"),
        safe_local_ratio(features, "crossbeam_relative_rms_over_bottom"),
    ]
    maximum_local_ratio = max(local_ratios)
    # log1p 让小于尺度的正常随动仅受轻微惩罚，而高局部参与单调增加。
    local_cost = 0.8 * math.log1p(maximum_local_ratio / LOCAL_RELATIVE_RMS_SCALE)
    # 全局峰远高于底索峰也是局部模态信号，超过 2 倍后补充惩罚。
    peak_ratio = float(features["global_peak_over_bottom_peak"])
    if peak_ratio > 2.0:
        local_cost += 0.4 * math.log1p(peak_ratio - 2.0)

    # 原始 V/T 向量若几乎只在一幅猫道上运动，说明未完成物理相位分裂；规范组合不会触发。
    localization = float(features["catwalk_localization"])
    degeneracy_basis_cost = 0.0
    if target.expected_type in {"V", "T"} and localization > 0.90:
        degeneracy_basis_cost = 2.0 * (localization - 0.90) / 0.10

    total_cost = (
        frequency_cost
        + type_cost
        + symmetry_cost
        + branch_rank_cost
        + lobe_cost
        + region_cost
        + local_cost
        + quality_cost
        + degeneracy_basis_cost
    )
    return {
        "frequency_cost": frequency_cost,
        "type_cost": type_cost,
        "symmetry_cost": symmetry_cost,
        "branch_rank_cost": branch_rank_cost,
        # candidate_branch_rank 用 float/NaN 统一返回类型，边表写出时会由 finite_or_blank 清理。
        "candidate_branch_rank": (
            float(candidate_branch_rank)
            if candidate_branch_rank is not None
            else float("nan")
        ),
        "lobe_cost": lobe_cost,
        "region_cost": region_cost,
        "local_cost": local_cost,
        "quality_cost": quality_cost,
        "degeneracy_basis_cost": degeneracy_basis_cost,
        "total_cost": total_cost,
    }


def solve_assignment_matrix(cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """对任意矩形代价矩阵执行 Hungarian 全局一对一分配。

    参数：
        cost_matrix：行是目标、列是候选，元素必须为有限实数。

    返回：
        ``(row_indices, column_indices, total_cost)``。
    """

    # 目标数不能超过候选数，否则无法一对一覆盖全部附件目标。
    if cost_matrix.shape[0] > cost_matrix.shape[1]:
        raise RuntimeError(
            f"候选数 {cost_matrix.shape[1]} 少于目标数 {cost_matrix.shape[0]}。"
        )
    # NaN/Inf 会让优化器产生不可解释结果，入口统一拒绝。
    if not np.all(np.isfinite(cost_matrix)):
        raise RuntimeError("目标—候选代价矩阵含 NaN/Inf。")
    row_indices, column_indices = linear_sum_assignment(cost_matrix)
    total_cost = float(np.sum(cost_matrix[row_indices, column_indices]))
    return row_indices, column_indices, total_cost


def confidence_from_cost_and_margins(
    target: ReferenceTarget,
    assigned_cost: float,
    local_margin: float,
    global_margin: float,
) -> str:
    """把绝对代价、局部次优差和全局禁边差转换为可读置信度。

    参数：
        target：当前附件目标；边跨因形态未细分最多只能给“中”。
        assigned_cost：被选边的总特征代价。
        local_margin：同一目标次低边与被选边的代价差。
        global_margin：禁止被选边后全局最优总成本的增加量。

    返回：
        ``高``、``中`` 或 ``低``。
    """

    # 高置信要求形态/频率总成本较低，且局部与全局替代方案都有清晰间隔。
    if assigned_cost <= 3.0 and local_margin >= 0.6 and global_margin >= 0.35:
        confidence = "高"
    # 中置信容许一定频差或其中一个替代间隔较小。
    elif assigned_cost <= 5.5 and local_margin >= 0.20 and global_margin >= 0.10:
        confidence = "中"
    else:
        confidence = "低"
    # 附件没有给边跨方向/具体跨位/振型图，因此任何算法都不能把边跨置信度升为“高”。
    if target.target_region == "side" and confidence == "高":
        confidence = "中"
    return confidence


def assign_targets_globally(
    targets: Sequence[ReferenceTarget],
    candidates: Sequence[Candidate],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], np.ndarray, float]:
    """构造完整代价矩阵并执行全局一对一目标分配。

    参数：
        targets：附件表 4-1 的 14 个目标。
        candidates：从全部已解析模态生成的物理候选。

    返回：
        ``(assignment_rows, edge_rows, cost_matrix, optimal_total_cost)``。
    """

    # cost_matrix 是 Hungarian 的数值输入；edge_details 保存每条边的透明分项。
    cost_matrix = np.empty((len(targets), len(candidates)), dtype=float)
    edge_details: dict[tuple[int, int], dict[str, float]] = {}
    edge_rows: list[dict[str, Any]] = []
    for target_index, target in enumerate(targets):
        for candidate_index, candidate in enumerate(candidates):
            components = compute_target_candidate_cost(target, candidate)
            edge_details[(target_index, candidate_index)] = components
            cost_matrix[target_index, candidate_index] = components["total_cost"]
            edge_rows.append(
                {
                    "reference_order": target.order,
                    "reference_label": target.label,
                    "reference_frequency_hz": target.frequency_hz,
                    "expected_branch_rank": (
                        target.expected_branch_rank
                        if target.expected_branch_rank is not None
                        else ""
                    ),
                    "candidate_id": candidate.candidate_id,
                    "candidate_frequency_hz": candidate.frequency_hz,
                    "source_modes": "/".join(str(number) for number in candidate.source_modes),
                    "candidate_type": candidate.features["dominant_type"],
                    "candidate_symmetry": candidate.features["symmetry_class"],
                    "candidate_main_lobes": candidate.features["main_signed_lobes"],
                    "identification_cluster": candidate.features.get(
                        "identification_cluster", ""
                    ),
                    **{
                        key: finite_or_blank(value)
                        for key, value in components.items()
                    },
                }
            )

    row_indices, column_indices, optimal_total_cost = solve_assignment_matrix(cost_matrix)
    # assigned_column_by_row 将优化器返回的稀疏索引对转换为目标行到候选列的映射。
    assigned_column_by_row = {
        int(row_index): int(column_index)
        for row_index, column_index in zip(row_indices, column_indices)
    }
    if set(assigned_column_by_row) != set(range(len(targets))):
        raise RuntimeError("Hungarian 结果未覆盖全部附件目标。")

    # assignment_rows 按附件顺序输出，而非按候选阶次或优化器内部顺序输出。
    assignment_rows: list[dict[str, Any]] = []
    for target_index, target in enumerate(targets):
        candidate_index = assigned_column_by_row[target_index]
        candidate = candidates[candidate_index]
        components = edge_details[(target_index, candidate_index)]
        # local_alternatives 是同一目标除被选候选外的全部边，用于局部歧义余量。
        local_alternatives = np.delete(cost_matrix[target_index, :], candidate_index)
        local_margin = float(np.min(local_alternatives) - components["total_cost"])
        # forbidden_matrix 只禁止当前已选边，再重解全局问题；成本增加量是真正全局替代余量。
        forbidden_matrix = cost_matrix.copy()
        forbidden_matrix[target_index, candidate_index] = 1.0e9
        _alt_rows, _alt_columns, alternative_total_cost = solve_assignment_matrix(forbidden_matrix)
        global_margin = alternative_total_cost - optimal_total_cost
        confidence = confidence_from_cost_and_margins(
            target,
            float(components["total_cost"]),
            local_margin,
            global_margin,
        )
        # relative_error_percent 保留符号，便于判断模型偏硬（正）或偏软（负）。
        frequency_difference = candidate.frequency_hz - target.frequency_hz
        relative_error_percent = frequency_difference / target.frequency_hz * 100.0
        # frequency_status 与“形态映射置信度”分开，避免高置信地找到错误频率分支后被误读为对齐通过。
        if abs(relative_error_percent) <= 5.0:
            frequency_status = "阶段通过(|误差|≤5%)"
        else:
            frequency_status = "未通过(|误差|>5%)"
        # overall_match_status 同时要求频率阶段阈值和形态映射不是低置信。
        overall_match_status = (
            "阶段通过"
            if abs(relative_error_percent) <= 5.0 and confidence != "低"
            else "未通过"
        )
        features = candidate.features
        assignment_rows.append(
            {
                "reference_order": target.order,
                "reference_label": target.label,
                "display_label": target.display_label,
                "reference_description": target.description,
                "reference_frequency_hz": target.frequency_hz,
                "expected_type": target.expected_type or "未细分",
                "expected_symmetry": target.expected_symmetry or "未细分",
                "expected_branch_rank": (
                    target.expected_branch_rank
                    if target.expected_branch_rank is not None
                    else ""
                ),
                "expected_lobes": target.expected_lobes if target.expected_lobes is not None else "",
                "shape_rule_basis": target.rule_basis,
                "assigned_candidate": candidate.candidate_id,
                "source_modes": "/".join(str(number) for number in candidate.source_modes),
                "source_coefficients": "/".join(f"{value:.10g}" for value in candidate.coefficients),
                "source_kind": candidate.source_kind,
                "subspace_group": candidate.subspace_group,
                "identification_cluster": features.get("identification_cluster", ""),
                "identification_cluster_axes": features.get(
                    "identification_cluster_axes", ""
                ),
                "ansys_frequency_hz": candidate.frequency_hz,
                "signed_difference_hz": frequency_difference,
                "relative_error_percent": relative_error_percent,
                "candidate_type": features["dominant_type"],
                "share_L": features["share_L"],
                "share_V": features["share_V"],
                "share_T": features["share_T"],
                "candidate_symmetry": features["symmetry_class"],
                "symmetry_cosine": features["symmetry_cosine"],
                # candidate_branch_rank 在内部代价字典中以 float/NaN 统一承载；
                # 正式分配表恢复为整数或空白，避免图表出现“第2.0阶”的伪精度。
                "candidate_branch_rank": (
                    int(components["candidate_branch_rank"])
                    if math.isfinite(components["candidate_branch_rank"])
                    else ""
                ),
                "main_signed_lobes": features["main_signed_lobes"],
                "main_absolute_peaks": features["main_absolute_peaks"],
                "dominant_signed_lobes": features["dominant_signed_lobes"],
                "dominant_absolute_peaks": features["dominant_absolute_peaks"],
                "main_span_share": features["main_span_share"],
                "dominant_region": features["dominant_region"],
                "gate_relative_rms_over_bottom": finite_or_blank(
                    features["gate_relative_rms_over_bottom"]
                ),
                "passage_relative_rms_over_bottom": finite_or_blank(
                    features["passage_relative_rms_over_bottom"]
                ),
                "feature_total_cost": components["total_cost"],
                "frequency_cost": components["frequency_cost"],
                "type_cost": components["type_cost"],
                "symmetry_cost": components["symmetry_cost"],
                "branch_rank_cost": components["branch_rank_cost"],
                "lobe_cost": components["lobe_cost"],
                "region_cost": components["region_cost"],
                "local_cost": components["local_cost"],
                "local_alternative_margin": local_margin,
                "global_forbidden_edge_margin": global_margin,
                "assignment_confidence": confidence,
                "mapping_scope": "单根或严格重根规范方向",
                "individual_identity_status": str(
                    features.get(
                        "individual_identity_status",
                        "单根可按当前形态特征分类",
                    )
                ),
                "frequency_status": frequency_status,
                "overall_match_status": overall_match_status,
                "mac_status": "不可计算：附件未提供源模态向量",
            }
        )

    # 同一有限频差混合簇可能被两个目标分别占用，但稳健结论只能是“目标集合对应
    # 这个二维子空间”。簇内 M3/M4 等单根的 LA1/TA1 排列会随微小扰动旋转或交换，
    # 因而必须把个体置信度降为低，同时保留簇级映射文字供工程判断。
    cluster_to_assignment_rows: dict[str, list[dict[str, Any]]] = {}
    for row in assignment_rows:
        cluster_id = str(row["identification_cluster"])
        if cluster_id:
            cluster_to_assignment_rows.setdefault(cluster_id, []).append(row)
    for cluster_id, cluster_assignment_rows in cluster_to_assignment_rows.items():
        target_labels = sorted(
            (str(row["reference_label"]) for row in cluster_assignment_rows),
            key=lambda label: next(
                target.order for target in targets if target.label == label
            ),
        )
        target_set_text = "{" + ",".join(target_labels) + "}"
        stable_statement = (
            f"仅可稳健认定 {target_set_text} ↔ span({cluster_id})；"
            "簇内单根标签不可唯一，当前逐根排列仅供审计"
        )
        for row in cluster_assignment_rows:
            row["mapping_scope"] = "有限频差近简并混合簇"
            row["individual_identity_status"] = stable_statement
            row["assignment_confidence"] = "低"
            # overall_match_status 是逐根结论；既然单根身份不可唯一，就不能标阶段通过。
            row["overall_match_status"] = "未通过（仅簇级可识别）"

    # selected_candidate_ids 必须严格唯一，构成全局一对一分配的最终硬检查。
    selected_candidate_ids = [str(row["assigned_candidate"]) for row in assignment_rows]
    if len(set(selected_candidate_ids)) != len(selected_candidate_ids):
        raise RuntimeError("目标分配结果重复使用了同一候选。")
    return assignment_rows, edge_rows, cost_matrix, optimal_total_cost


def configure_plot_style() -> None:
    """设置适合中文工程报告和批处理导出的 Matplotlib 样式。

    参数：
        无。

    返回：
        无；函数更新全局 ``plt.rcParams``。
    """

    # 字体列表按 Windows 常见中文字体优先，DejaVu Sans 作为数字/英文后备。
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9.0,
            "figure.dpi": 120,
            "savefig.dpi": 240,
        }
    )


def compact_candidate_label(candidate: Candidate) -> str:
    """为图件生成不遮挡数据区的简短候选标签。

    参数：
        candidate：需要显示来源阶次和物理方向的候选。

    返回：
        原始独立根如 ``M7``；近重根规范方向如 ``M21/22-T``。
    """

    # mode_text 首项保留 M 前缀，后续只写数字，从而显著缩短近重根标签。
    mode_text = "M" + "/".join(str(number) for number in candidate.source_modes)
    # 独立原始根不需要重复写已可从标题读取的 dominant_type。
    if candidate.source_kind == "raw":
        return mode_text
    # 规范方向附加由数据识别的 L/V/T/其他主导类型，而不是附件目标标签。
    return f"{mode_text}-{candidate.features['dominant_type']}"


def save_figure(figure: plt.Figure, base_name: str) -> list[Path]:
    """把一张正式图同时保存为 PNG 和 PDF。

    参数：
        figure：已经完成布局的 Matplotlib Figure。
        base_name：不含扩展名的输出基名。

    返回：
        两个实际写出路径的列表。
    """

    # output_paths 保存可在 Markdown 中引用的确定文件名。
    output_paths = [OUTPUT_DIR / f"{base_name}.png", OUTPUT_DIR / f"{base_name}.pdf"]
    # PNG 便于快速预览，PDF 保留矢量文字和曲线供正式归档。
    for output_path in output_paths:
        figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)
    return output_paths


def create_frequency_assignment_figure(
    targets: Sequence[ReferenceTarget],
    assignment_rows: Sequence[dict[str, Any]],
) -> list[Path]:
    """绘制附件目标与全局分配频率的逐项对比图。

    参数：
        targets：附件顺序的 14 个目标。
        assignment_rows：与 targets 同顺序的分配结果。

    返回：
        PNG/PDF 两个路径。
    """

    # orders 用附件编号作为横坐标；reference/calculated 分别是两组频率。
    orders = np.arange(1, len(targets) + 1)
    reference = np.asarray([target.frequency_hz for target in targets], dtype=float)
    calculated = np.asarray([float(row["ansys_frequency_hz"]) for row in assignment_rows], dtype=float)
    errors = (calculated - reference) / reference * 100.0
    # figure 上半部比较频率，下半部显示带符号相对误差。
    figure, (axis_frequency, axis_error) = plt.subplots(
        2,
        1,
        figsize=(13.0, 8.0),
        gridspec_kw={"height_ratios": [2.0, 1.0]},
        sharex=True,
    )
    axis_frequency.plot(orders, reference, "o-", color="#202020", lw=1.8, label="附件2-3表4-1")
    axis_frequency.plot(orders, calculated, "s--", color="#2F6B9A", lw=1.7, label="全局特征分配结果")
    # 每个计算点标注实际候选 ID，而不是仅标 ANSYS 顺序。
    # 当前函数没有接收候选列表，因此从 source_modes/source_kind/candidate_type 构造同口径短标。
    for order, value, row in zip(orders, calculated, assignment_rows):
        source_numbers = str(row["source_modes"]).split("/")
        source_label = "M" + "/".join(source_numbers)
        if str(row["source_kind"]) != "raw":
            source_label += f"-{row['candidate_type']}"
        axis_frequency.annotate(
            source_label,
            (order, value),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=7.2,
            rotation=28,
        )
    axis_frequency.set_ylabel("频率 / Hz")
    axis_frequency.set_title("附件2-3前14个物理分支：全局一对一识别频率对比", fontweight="bold")
    axis_frequency.grid(True, alpha=0.28)
    axis_frequency.legend(frameon=False, loc="upper left")

    # 误差绝对值小于 5% 用蓝色，否则用红色，直观暴露仍需调参的物理分支。
    colors = np.where(np.abs(errors) <= 5.0, "#4C78A8", "#C44E52")
    axis_error.bar(orders, errors, color=colors, width=0.68)
    axis_error.axhline(0.0, color="#333333", lw=0.8)
    axis_error.axhline(5.0, color="#999999", lw=0.8, ls="--")
    axis_error.axhline(-5.0, color="#999999", lw=0.8, ls="--")
    # 逐柱标注一位小数误差，正号表示当前模型频率偏高。
    for order, error in zip(orders, errors):
        vertical_alignment = "bottom" if error >= 0.0 else "top"
        vertical_offset = 2 if error >= 0.0 else -2
        axis_error.annotate(
            f"{error:+.1f}%",
            (order, error),
            xytext=(0, vertical_offset),
            textcoords="offset points",
            ha="center",
            va=vertical_alignment,
            fontsize=7.5,
        )
    axis_error.set_ylabel("相对误差 / %")
    axis_error.set_xlabel("附件表4-1模态编号")
    axis_error.set_xticks(orders)
    axis_error.set_xticklabels([target.display_label for target in targets])
    axis_error.grid(True, axis="y", alpha=0.25)
    figure.tight_layout()
    return save_figure(figure, "figure_01_global_assignment_frequency")


def create_cost_matrix_figure(
    targets: Sequence[ReferenceTarget],
    candidates: Sequence[Candidate],
    assignment_rows: Sequence[dict[str, Any]],
    cost_matrix: np.ndarray,
) -> list[Path]:
    """绘制完整目标—候选特征代价矩阵并标出 Hungarian 选边。

    参数：
        targets：矩阵行目标。
        candidates：矩阵列候选。
        assignment_rows：用于查找被选 candidate_id。
        cost_matrix：未裁剪的实际优化代价矩阵。

    返回：
        PNG/PDF 两个路径。
    """

    # 显示色阶在 95 分位截断，避免少数极大错误边把有效差异压成同一颜色。
    color_limit = float(np.percentile(cost_matrix, 95.0))
    figure_width = max(14.0, 0.42 * len(candidates))
    figure, axis = plt.subplots(figsize=(figure_width, 8.2))
    image = axis.imshow(
        np.clip(cost_matrix, 0.0, color_limit),
        aspect="auto",
        cmap="viridis_r",
        vmin=0.0,
        vmax=color_limit,
    )
    axis.set_yticks(np.arange(len(targets)))
    axis.set_yticklabels([target.display_label for target in targets])
    axis.set_xticks(np.arange(len(candidates)))
    axis.set_xticklabels(
        [compact_candidate_label(candidate) for candidate in candidates],
        rotation=70,
        ha="right",
        fontsize=7.0,
    )
    axis.set_xlabel("自动生成的候选（无硬编码目标阶次）")
    axis.set_ylabel("附件表4-1物理目标")
    axis.set_title("全局一对一分配的完整特征代价矩阵（圆圈为 Hungarian 选边）", fontweight="bold")
    # candidate_index_by_id 用稳定标识查找每一行的选定列。
    candidate_index_by_id = {
        candidate.candidate_id: index for index, candidate in enumerate(candidates)
    }
    for target_index, row in enumerate(assignment_rows):
        selected_column = candidate_index_by_id[str(row["assigned_candidate"])]
        axis.scatter(
            [selected_column],
            [target_index],
            s=105,
            facecolors="none",
            edgecolors="#FF2B2B",
            linewidths=1.6,
        )
    colorbar = figure.colorbar(image, ax=axis, pad=0.015)
    colorbar.set_label(f"总特征代价（显示截断至95分位={color_limit:.2f}）")
    figure.tight_layout()
    return save_figure(figure, "figure_02_target_candidate_cost_matrix")


def create_assigned_profile_figure(
    targets: Sequence[ReferenceTarget],
    candidates: Sequence[Candidate],
    assignment_rows: Sequence[dict[str, Any]],
) -> list[Path]:
    """绘制 14 个已分配候选的两幅猫道有符号顺桥曲线。

    参数：
        targets：附件目标，用于标题中的期望类型/S/A/波腹。
        candidates：提供实际两幅猫道曲线。
        assignment_rows：提供目标到 candidate_id 的一对一映射。

    返回：
        PNG/PDF 两个路径。
    """

    # candidate_by_id 让绘图只依赖稳定 ID，不假定候选列表顺序与目标一致。
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    figure, axes = plt.subplots(7, 2, figsize=(16.0, 20.5), sharex=True)
    for target, row, axis in zip(targets, assignment_rows, axes.ravel()):
        candidate = candidate_by_id[str(row["assigned_candidate"])]
        x_km = candidate.plot_data["x_mm"] / 1.0e6
        negative_profile = candidate.plot_data["negative_catwalk_profile"]
        positive_profile = candidate.plot_data["positive_catwalk_profile"]
        # 两幅曲线共用同一归一化尺度，因而相对相位和幅值差不会被隐藏。
        scale = max(
            float(np.max(np.abs(negative_profile))),
            float(np.max(np.abs(positive_profile))),
        )
        if scale <= np.finfo(float).eps:
            scale = 1.0
        axis.plot(x_km, negative_profile / scale, color="#3274A1", lw=1.25, label="Y<0猫道")
        axis.plot(x_km, positive_profile / scale, color="#E1812C", lw=1.15, ls="--", label="Y>0猫道")
        axis.axhline(0.0, color="#777777", lw=0.55)
        axis.axvspan(
            MAIN_SPAN_START_MM / 1.0e6,
            MAIN_SPAN_END_MM / 1.0e6,
            color="#E7EDF3",
            alpha=0.60,
        )
        axis.set_ylim(-1.12, 1.12)
        axis.grid(True, alpha=0.24, lw=0.45)
        # expected_shape 对边跨显示“未细分”；无源图的主跨目标只显示家族序号，
        # 绝不把 None 或理论外推波腹数画成附件观测。
        if target.expected_type is None:
            expected_shape = "边跨（方向/对称性未细分）"
            identified_shape = (
                f"识别 {row['candidate_type']}/{row['dominant_region']}/"
                f"{row['dominant_signed_lobes']}波腹"
            )
        elif target.expected_lobes is None:
            expected_shape = (
                f"期望 {target.expected_type}-{target.expected_symmetry}"
                f"家族第{target.expected_branch_rank}阶（附件无源图）"
            )
            identified_shape = (
                f"识别 {row['candidate_type']}-{row['candidate_symmetry']}/"
                f"家族第{row['candidate_branch_rank']}阶/"
                f"实测{row['main_signed_lobes']}波腹"
            )
        else:
            expected_shape = (
                f"期望 {target.expected_type}-{target.expected_symmetry}/"
                f"家族第{target.expected_branch_rank}阶/{target.expected_lobes}波腹"
            )
            identified_shape = (
                f"识别 {row['candidate_type']}-{row['candidate_symmetry']}/"
                f"家族第{row['candidate_branch_rank']}阶/{row['main_signed_lobes']}波腹"
            )
        axis.set_title(
            f"{target.display_label} {target.frequency_hz:.4f} Hz → {compact_candidate_label(candidate)} "
            f"{candidate.frequency_hz:.6f} Hz ({float(row['relative_error_percent']):+.2f}%)\n"
            f"{expected_shape}；{identified_shape}；映射置信度 {row['assignment_confidence']}",
            loc="left",
            fontsize=8.2,
        )
    # 图例全图共用，避免 14 个子图重复遮挡曲线。
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.998))
    figure.suptitle(
        "附件2-3目标分支的两幅猫道有符号振型特征（形态特征，非MAC）",
        fontsize=15,
        fontweight="bold",
        y=1.012,
    )
    figure.supxlabel("顺桥 X / km")
    figure.supylabel("按本候选两幅最大值归一化")
    figure.tight_layout(rect=(0.025, 0.025, 0.995, 0.985))
    return save_figure(figure, "figure_03_assigned_mode_profiles")


def create_local_participation_figure(
    candidates: Sequence[Candidate],
    assignment_rows: Sequence[dict[str, Any]],
) -> list[Path]:
    """绘制全部候选的门架/横通道相对参与与底索谱位置。

    参数：
        candidates：全部自动候选。
        assignment_rows：用于突出最终 14 个选中候选。

    返回：
        PNG/PDF 两个路径。
    """

    # selected_ids 用于区分被选物理分支与未选局部/高阶候选。
    selected_ids = {str(row["assigned_candidate"]) for row in assignment_rows}
    frequencies = np.asarray([candidate.frequency_hz for candidate in candidates], dtype=float)
    gate_values = np.asarray(
        [safe_local_ratio(candidate.features, "gate_relative_rms_over_bottom") for candidate in candidates],
        dtype=float,
    )
    passage_values = np.asarray(
        [safe_local_ratio(candidate.features, "passage_relative_rms_over_bottom") for candidate in candidates],
        dtype=float,
    )
    selected_mask = np.asarray([candidate.candidate_id in selected_ids for candidate in candidates], dtype=bool)
    figure, axis = plt.subplots(figsize=(13.0, 6.8))
    # 未选候选用淡色小点；选中候选用深色描边，便于检查局部模态是否被错误吸收。
    axis.scatter(frequencies[~selected_mask], gate_values[~selected_mask], s=28, color="#8BB6D6", alpha=0.65, label="门架相对参与（未选）")
    axis.scatter(frequencies[selected_mask], gate_values[selected_mask], s=70, color="#1F77B4", edgecolor="black", lw=0.5, label="门架相对参与（已选）")
    # 当前 V1 没有 passage 节点时 safe_local_ratio 为 0；图注会明确该类缺数据。
    axis.scatter(frequencies[~selected_mask], passage_values[~selected_mask], s=28, marker="^", color="#F5A45D", alpha=0.65, label="横通道相对参与（未选）")
    axis.scatter(frequencies[selected_mask], passage_values[selected_mask], s=70, marker="^", color="#E1812C", edgecolor="black", lw=0.5, label="横通道相对参与（已选）")
    axis.axhline(LOCAL_RELATIVE_RMS_SCALE, color="#777777", lw=0.9, ls="--", label="局部惩罚尺度")
    # 标注被选候选 ID，便于回到 target_assignment.csv 查对应目标。
    for candidate, is_selected, gate_value, passage_value in zip(candidates, selected_mask, gate_values, passage_values):
        if not is_selected:
            continue
        axis.annotate(
            compact_candidate_label(candidate),
            (candidate.frequency_hz, max(gate_value, passage_value)),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=7.0,
        )
    axis.set_xlabel("候选频率 / Hz")
    axis.set_ylabel("构件相对位移 RMS / 底索 RMS")
    axis.set_title("门架与横通道局部参与筛查（剔除断面随动参考后）", fontweight="bold")
    axis.grid(True, alpha=0.25)
    axis.legend(frameon=False, ncol=2)
    figure.tight_layout()
    return save_figure(figure, "figure_04_gate_passage_local_participation")


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """把简单二维数据转换为 GitHub 风格 Markdown 表格。

    参数：
        headers：列标题。
        rows：逐行可迭代单元格。

    返回：
        含表头、分隔行和数据行的 Markdown 字符串。
    """

    # escape_cell 防止单元格中的竖线破坏 Markdown 列结构，并把换行压成空格。
    def escape_cell(value: Any) -> str:
        """转义一个 Markdown 表格单元格。

        参数：
            value：任意可字符串化对象。

        返回：
            不含原始换行且竖线已转义的字符串。
        """

        return str(value).replace("|", "\\|").replace("\n", " ")

    # lines 第一行为标题，第二行为 Markdown 必需的列分隔符。
    lines = [
        "| " + " | ".join(escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _header in headers) + " |",
    ]
    # 数据行按输入顺序追加；生成器也会在此被一次性消费。
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(value) for value in row) + " |")
    return "\n".join(lines)


def write_markdown_report(
    raw_dir: Path,
    primary_node_csv: Path,
    supplemental_paths: Sequence[Path],
    targets: Sequence[ReferenceTarget],
    candidates: Sequence[Candidate],
    assignment_rows: Sequence[dict[str, Any]],
    subspace_rows: Sequence[dict[str, Any]],
    identification_cluster_rows: Sequence[dict[str, Any]],
    optimal_total_cost: float,
    mode_count: int,
    passage_node_count: int,
    gate_node_count: int,
) -> Path:
    """生成用户可读的识别方法、结果、限制与复算路径报告。

    参数：
        raw_dir：本次读取的 MAPDL 原始目录。
        primary_node_csv：32 根底索主节点表。
        supplemental_paths：V2 门架/横通道补充节点表。
        targets/candidates/assignment_rows：参考、候选和最终分配。
        subspace_rows：自动近重根处理审计。
        identification_cluster_rows：有限频差方向混合簇审计；这些簇只可做
            子空间级识别，不能把簇内线性组合称为新的特征向量。
        optimal_total_cost：Hungarian 最优总特征代价。
        mode_count：实际读取的连续原始阶次数。
        passage_node_count/gate_node_count：构件局部参与的数据覆盖计数。

    返回：
        写出的 Markdown 路径。
    """

    # relative_errors 用于汇总频率误差，不影响目标分配本身。
    relative_errors = np.asarray(
        [float(row["relative_error_percent"]) for row in assignment_rows],
        dtype=float,
    )
    within_one = int(np.sum(np.abs(relative_errors) <= 1.0))
    within_three = int(np.sum(np.abs(relative_errors) <= 3.0))
    within_five = int(np.sum(np.abs(relative_errors) <= 5.0))
    maximum_error = float(np.max(np.abs(relative_errors)))
    mean_absolute_error = float(np.mean(np.abs(relative_errors)))
    # assignment_table_rows 只选报告最关键列；完整分项留在 CSV。
    assignment_table_rows = []
    for row in assignment_rows:
        # report_candidate_label 用来源阶次和识别方向缩写长的 phase_principal 审计 ID。
        report_candidate_label = "M" + "/".join(str(row["source_modes"]).split("/"))
        if str(row["source_kind"]) != "raw":
            report_candidate_label += f"-{row['candidate_type']}"
        # 主跨目标显示 S/A 与主跨波腹；附件未细分的边跨项显示实际主导跨域和该跨波腹。
        if str(row["expected_type"]) == "未细分":
            identified_shape = (
                f"{row['candidate_type']}/{row['dominant_region']}/"
                f"{row['dominant_signed_lobes']}波腹"
            )
        else:
            identified_shape = (
                f"{row['candidate_type']}-{row['candidate_symmetry']}/"
                f"家族第{row['candidate_branch_rank']}阶/"
                f"{row['main_signed_lobes']}波腹"
            )
        assignment_table_rows.append(
            (
                row["reference_order"],
                row["display_label"],
                f"{float(row['reference_frequency_hz']):.4f}",
                report_candidate_label,
                f"{float(row['ansys_frequency_hz']):.6f}",
                f"{float(row['relative_error_percent']):+.2f}%",
                identified_shape,
                row["mapping_scope"],
                row["assignment_confidence"],
                row["overall_match_status"],
            )
        )
    assignment_table = markdown_table(
        [
            "序",
            "附件目标",
            "参考Hz",
            "自动候选",
            "计算Hz",
            "误差",
            "识别形态",
            "识别范围",
            "映射置信度",
            "阶段状态",
        ],
        assignment_table_rows,
    )

    # near_root_text 在没有近重根时仍给出明确结论，避免空章节。
    if subspace_rows:
        near_root_table = markdown_table(
            ["子空间", "平均Hz", "最大相对间隙", "处理"],
            [
                (
                    row["subspace_group"],
                    f"{float(row['mean_frequency_hz']):.9f}",
                    f"{float(row['maximum_relative_gap']):.3e}",
                    row["action"],
                )
                for row in subspace_rows
            ],
        )
    else:
        near_root_table = "未发现达到近重根阈值的连续频率组。"

    # identification_cluster_table 单独列出有限频差混合簇，明确它不同于可合法旋转
    # 的严格重根子空间；空结果时同样给出可审计结论而不是省略章节。
    if identification_cluster_rows:
        identification_cluster_table = markdown_table(
            ["识别簇", "平均Hz", "相对频宽", "方向轴", "可分离度", "S/A", "处理"],
            [
                (
                    row["identification_cluster"],
                    f"{float(row['mean_frequency_hz']):.9f}",
                    f"{float(row['maximum_relative_span']):.3e}",
                    row["axes"],
                    f"{float(row['subspace_separability']):.6f}",
                    row["symmetry"],
                    row["action"],
                )
                for row in identification_cluster_rows
            ],
        )
    else:
        identification_cluster_table = "未发现达到判据的有限频差方向混合簇。"

    # component_coverage_text 明确当前是否真正含有限门架/横通道节点。
    if passage_node_count == 0:
        passage_coverage = "横通道节点注册数为 0；当前只能输出“缺数据”，不能宣称横通道局部变形为零。"
    else:
        passage_coverage = f"已注册 {passage_node_count} 个横通道节点，并计算剔除断面随动后的相对 RMS。"
    if gate_node_count == 0:
        gate_coverage = "门架节点注册数为 0；门架局部参与不可评价。"
    else:
        gate_coverage = f"已注册 {gate_node_count} 个门架/门架索节点。"

    # supplemental_listing 逐行列出补充注册表；空列表明确写“无”。
    supplemental_listing = (
        "\n".join(f"  - `{path}`" for path in supplemental_paths)
        if supplemental_paths
        else "  - 无（本次为当前 V1 回归自测）"
    )
    # assignment_by_label 供判定边界动态引用本次实际结果；报告函数同时服务 V1/V2，
    # 因而绝不能硬编码“TS2=M15”等只对某一批结果成立的阶次。
    assignment_by_label = {
        str(row["reference_label"]): row
        for row in assignment_rows
    }

    def format_assigned_source(label: str) -> str:
        """把指定附件目标的实际来源阶次格式化为紧凑 M 前缀字符串。

        参数：
            label：附件内部目标标签，例如 ``TS2`` 或 ``VS2``。

        返回：
            单根返回 ``M15``，多根/严格重根方向返回 ``M2/3``；若目标缺失则
            返回“未分配”。本函数只格式化实际审计结果，不推断任何物理身份。
        """

        row = assignment_by_label.get(label)
        if row is None:
            return "未分配"
        return "M" + "/".join(str(row["source_modes"]).split("/"))

    # cluster_conclusions 汇总本次真正被目标占用的有限频差簇，避免 V1 没有 M3/M4
    # 混合簇时仍输出一条不适用的固定结论。
    cluster_conclusions = sorted(
        {
            str(row["individual_identity_status"])
            for row in assignment_rows
            if str(row["identification_cluster"])
        }
    )
    cluster_boundary_text = (
        "；".join(cluster_conclusions)
        if cluster_conclusions
        else "本次没有被目标采用的有限频差方向混合簇。"
    )
    # generated_at 使用本机时区的 ISO 格式，便于与求解日志时间对照。
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    report = f"""# 附件2-3全模态自动识别与全局分配报告

生成时间：{generated_at}

## 1. 输入与范围

- MAPDL 原始结果：`{raw_dir}`
- 连续读取：M1～M{mode_count}，共 {mode_count} 个全节点向量。
- 底索主节点表：`{primary_node_csv}`
- V2 构件补充节点表：
{supplemental_listing}
- 权威频率：附件2-3表4-1，PDF第16物理页/印刷第14页。
- 自动生成物理候选：{len(candidates)} 个；Hungarian 最优总特征代价：{optimal_total_cost:.4f}。

## 2. 识别和分配方法

1. 把 UX/UZ 投影到有垂度底索的局部法向/切向，并对非均匀索段做弧长加权。
2. 分解整体横弯 L、两幅同相法向 V、两幅反相法向 T、纵向和断面内部畸变。
3. 从主导有符号曲线计算主跨 S/A 镜像余弦、符号波腹/过零及绝对峰数；只有图 4-3～4-8 直接给图的目标才使用波腹先验。
4. 按方向、S/A 和频率为每个候选建立家族分支序号；标签末尾数字按附件表下注释解释为家族序号，不解释为波腹数。
5. 对频率自动发现的严格 V/T 重根子空间做广义位移平方商旋转；没有严格退化时保留原始独立根。
6. 对有限频差且方向强混合的相邻根只登记“识别簇”，不旋转、不制造新特征向量，簇内逐根身份标为不可唯一。
7. 门架/横通道局部参与使用“构件节点位移减去同 X/Y 底索断面线性随动”的相对 RMS。
8. 构造包含频率、方向、S/A、家族序号、直接有图的波腹、跨域和局部参与的完整 14×N 代价矩阵，一次性执行全局一对一 Hungarian 分配。

**重要限制：附件未提供 R19.2 的质量归一化源模态向量，因此无法计算真正 MAC。本文的代价和置信度仅是形态特征，不是 MAC，也不证明源向量一致。**

## 3. 全局一对一结果

{assignment_table}

频率误差汇总：|误差|≤1% 为 {within_one}/14，≤3% 为 {within_three}/14，≤5% 为 {within_five}/14；平均绝对误差 {mean_absolute_error:.2f}%，最大绝对误差 {maximum_error:.2f}%。

## 4. 自动近重根审计

{near_root_table}

近重根规范方向是同一特征值子空间内的独立线性组合；它们不代表模型已经产生 V/T 频率分裂。V2 有限刚度门架和横通道正确建模后，应优先看到 V/T 成为不同频率的原始独立根。

## 5. 有限频差方向混合簇审计

{identification_cluster_table}

有限频差簇中的线性组合一般不是特征向量。因此本流水线只给出集合/子空间级结论，例如 `{{LA1,TA1}} ↔ span(M3,M4)`；M3 与 M4 的逐根标签仅是当前 Hungarian 排列，不得当成稳定物理身份。

## 6. 门架与横通道覆盖

- {gate_coverage}
- {passage_coverage}

## 7. 产物

- `raw_mode_features.csv`：每个原始 ANSYS 向量的全部形态/局部指标。
- `assignment_candidates.csv`：实际进入全局分配的独立根或近重根规范方向。
- `target_candidate_costs.csv`：完整 14×N 分项代价，不隐藏未选候选。
- `target_assignment.csv`：最终全局一对一结果、误差、余量和置信度。
- `frequency_sources.csv`：每阶频率实际取值来源与跨来源偏差。
- `subspace_audit.csv`：近重根发现及是否旋转的依据（若存在）。
- `identification_cluster_audit.csv`：有限频差方向混合簇及逐根不可唯一限制。
- `figure_01_global_assignment_frequency.*`：目标/计算谱与误差。
- `figure_02_target_candidate_cost_matrix.*`：完整代价矩阵和选边。
- `figure_03_assigned_mode_profiles.*`：14 个已选候选的两幅猫道曲线。
- `figure_04_gate_passage_local_participation.*`：构件局部参与筛查。
- `modal_pipeline_audit.json`：输入哈希、参数和机器可读摘要。

## 8. 判定边界

- 三个“边跨模态”在附件中没有方向、具体边跨和振型图，置信度最高只标“中”。
- VA2/LA2/TS2/VS2 没有附件振型图，故不设置波腹先验；只按附件明示的第二家族分支、方向、S/A、跨域和频率识别。
- 本次 TS2 按第二个 T-S 家族分支映射到 {format_assigned_source('TS2')}，VS2 按第二个 V-S 家族分支映射到 {format_assigned_source('VS2')}；这是“家族序号+计算向量特征”识别，仍不是真 MAC。
- 有限频差混合簇结论：{cluster_boundary_text}
- 只有 `target_assignment.csv` 中频率、方向、S/A、家族序号、跨域、局部参与，以及有源图目标的波腹证据同时通过，才可称该物理分支对上；不得仅按频率顺序宣称“前14阶已对齐”。
"""
    output_path = OUTPUT_DIR / "模态自动识别与全局分配报告.md"
    # Markdown 面向 Windows 人工审阅，使用 UTF-8 BOM 防止系统默认 ANSI 造成中文乱码。
    output_path.write_text(report, encoding=HUMAN_TEXT_ENCODING)
    return output_path


def build_argument_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器，使当前回归和未来 V2 共用一套入口。

    参数：
        无。

    返回：
        配置好默认路径、重复参数和帮助文本的 ``ArgumentParser``。
    """

    parser = argparse.ArgumentParser(
        description="附件2-3前14分支：全节点形态识别、近重根规范化和全局一对一分配。"
    )
    # raw-dir 默认当前 V1，未来 V2 求解完成后显式指向新原始结果目录。
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=CURRENT_V1_RAW_DIR,
        help="包含 mode_XX_all_nodes.txt 的 MAPDL 输出目录。",
    )
    # primary-node-csv 固定提供 32 根底索身份；V2 新增节点另用 supplemental 参数。
    parser.add_argument(
        "--primary-node-csv",
        type=Path,
        default=PRIMARY_NODE_CSV,
        help="V1 权威主节点表；脚本会执行旧坐标到 X-long 的正交变换。",
    )
    # action=append 允许门架和横通道由多个生成器分别写注册表。
    parser.add_argument(
        "--supplemental-node-csv",
        type=Path,
        action="append",
        default=[],
        help="V2 新构件节点表，可重复；须含 node_id,X_mm,Y_mm,Z_mm,component_class。",
    )
    # 单作业规则要求显式且唯一的频率来源；未给或重复给出都会在入口失败。
    parser.add_argument(
        "--frequency-source",
        type=Path,
        action="append",
        default=[],
        help="唯一频率文本或SET列表；必须且只能提供一次，路径相对于raw-dir。",
    )
    # manifest把频率文件和全部向量的路径、阶次与SHA-256绑定到同一run_id/jobname。
    parser.add_argument(
        "--job-manifest",
        type=Path,
        required=True,
        help="位于raw-dir内的单作业JSON清单；缺失、路径不符或哈希不符即失败。",
    )
    # max-modes 未给时读取全部已发现向量；快速回归可指定 30，正式 V2 推荐 40～60。
    parser.add_argument(
        "--max-modes",
        type=int,
        default=None,
        help="读取最高阶次；省略时使用 raw-dir 中全部连续结果。",
    )
    # 退化阈值暴露为参数但默认与当前严格二重根审计口径一致。
    parser.add_argument(
        "--degenerate-relative-gap",
        type=float,
        default=DEFAULT_DEGENERATE_RELATIVE_GAP,
        help="自动近重根相邻相对频差阈值，默认 1e-5。",
    )
    # identification-cluster-relative-gap 只控制有限频差方向混合簇审计；它不会
    # 触发特征向量旋转，因此可独立于严格重根阈值设置。
    parser.add_argument(
        "--identification-cluster-relative-gap",
        type=float,
        default=DEFAULT_IDENTIFICATION_CLUSTER_RELATIVE_GAP,
        help="有限频差方向混合簇阈值，默认 1e-2；簇内不会旋转特征向量。",
    )
    # 输出目录不再允许默认写共享post；调用者必须提供本run_id下的新空目录。
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="本次作业独占的新空输出目录，必须位于raw-dir内。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行完整解析、识别、分配、绘图、报告和审计输出。

    参数：
        argv：供测试传入的参数序列；``None`` 时读取真实命令行。

    返回：
        ``0`` 表示所有 CSV/图/MD/JSON 均生成并通过硬检查。
    """

    # OUTPUT_DIR 是绘图和报告辅助函数共享的本次输出位置；在解析参数后统一设置，
    # 避免为十余个纯输出函数重复传递同一目录参数。
    global OUTPUT_DIR
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    # raw_dir/primary_path 解析为绝对路径，审计输出不依赖调用时工作目录。
    raw_dir = args.raw_dir.resolve()
    primary_path = args.primary_node_csv.resolve()
    supplemental_paths = [path.resolve() for path in args.supplemental_node_csv]
    OUTPUT_DIR = args.output_dir.resolve()
    if not raw_dir.is_dir():
        raise NotADirectoryError(raw_dir)
    # 输出必须留在本次作业目录内，并且只能写入不存在的新目录，防止残留旧图或旧JSON。
    try:
        OUTPUT_DIR.relative_to(raw_dir)
    except ValueError as exc:
        raise RuntimeError("output-dir必须位于本次raw-dir内。") from exc
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"output-dir必须是尚不存在的新目录：{OUTPUT_DIR}")
    if args.degenerate_relative_gap <= 0.0:
        raise ValueError("--degenerate-relative-gap 必须为正数。")
    if args.identification_cluster_relative_gap <= 0.0:
        raise ValueError("--identification-cluster-relative-gap 必须为正数。")
    if args.identification_cluster_relative_gap <= args.degenerate_relative_gap:
        raise ValueError(
            "有限频差识别簇阈值必须大于严格重根阈值，才能保持两类处理语义分离。"
        )

    # references/registry/geometry 是全部后续步骤共享的权威目标和几何基础。
    references = load_reference_targets(REFERENCE_CSV)
    registry = build_node_registry(primary_path, supplemental_paths)
    geometry = build_bottom_geometry(registry)
    # mode_files 决定本次连续阶次窗口，不从频率表猜测是否已有节点向量。
    mode_files = discover_mode_files(raw_dir, args.max_modes)
    available_modes = set(mode_files)
    # frequency_sources 允许 V1 的 M1～20 频率表与 M21～30 日志自动拼接。
    frequency_sources = discover_frequency_sources(raw_dir, args.frequency_source)
    if not frequency_sources:
        raise RuntimeError(f"{raw_dir} 中没有可解析频率来源。")
    # 在解析任何数值前先验证唯一作业清单及每个关键文件的SHA-256。
    validate_single_job_manifest(
        args.job_manifest.resolve(),
        raw_dir,
        frequency_sources[0],
        mode_files,
    )
    # 身份验证通过后才创建输出目录，避免无效作业留下看似正式的空目录。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    frequencies, frequency_audit_rows = select_frequencies(frequency_sources, available_modes)

    # raw_modes 保留后续子空间旋转所需全节点数组；raw_feature_rows 是输出表。
    raw_modes: dict[int, ModeData] = {}
    raw_features: dict[int, dict[str, Any]] = {}
    raw_feature_rows: list[dict[str, Any]] = []
    for mode_number in sorted(mode_files):
        mode = parse_mode_file(
            mode_files[mode_number],
            mode_number,
            frequencies[mode_number],
            registry,
            geometry,
        )
        raw_modes[mode_number] = mode
        features, _plot_data = compute_mode_features(mode, registry, geometry)
        raw_features[mode_number] = features
        # finite_or_blank 逐字段清理 NaN，保留“缺构件节点”的空白语义。
        raw_feature_rows.append({key: finite_or_blank(value) for key, value in features.items()})

    # degenerate_groups 完全由频率间隙发现，不使用旧报告中的已知阶次列表。
    degenerate_groups = find_degenerate_groups(frequencies, args.degenerate_relative_gap)
    candidates, subspace_rows = build_candidates(
        raw_modes,
        raw_features,
        degenerate_groups,
        registry,
        geometry,
    )
    # mixed_mode_to_cluster 只发现有限频差且方向强混合的原始根；随后给候选附注簇 ID，
    # 再按簇 token 建立六个 L/V/T-S/A 家族分支序号。
    mixed_mode_to_cluster, identification_cluster_rows = find_mixed_identification_clusters(
        raw_features,
        frequencies,
        degenerate_groups,
        args.identification_cluster_relative_gap,
    )
    # 方向商只做簇级诊断，不把有限频差线性组合加入 candidates；这一步量化
    # M3/M4 空间能否分别提取近纯 L/T 方向，同时保持原始根身份不被覆盖。
    enrich_identification_clusters_with_direction_subspace_audit(
        raw_modes,
        identification_cluster_rows,
        geometry,
    )
    annotate_candidates_with_identification_clusters(
        candidates,
        mixed_mode_to_cluster,
        identification_cluster_rows,
    )
    assign_candidate_family_branch_ranks(candidates)
    assignment_rows, edge_rows, cost_matrix, optimal_total_cost = assign_targets_globally(
        references,
        candidates,
    )

    # candidate_rows 把 Candidate 元数据和 features 展平，数组曲线不写入 CSV。
    candidate_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        row = {
            "candidate_id": candidate.candidate_id,
            "source_modes": "/".join(str(number) for number in candidate.source_modes),
            "coefficients": "/".join(f"{value:.10g}" for value in candidate.coefficients),
            "source_kind": candidate.source_kind,
            "subspace_group": candidate.subspace_group,
            "frequency_hz": candidate.frequency_hz,
        }
        # features 中已有部分同名来源字段，跳过它们避免覆盖明确的候选元数据。
        for key, value in candidate.features.items():
            if key in row:
                continue
            row[key] = finite_or_blank(value)
        candidate_rows.append(row)

    # 六个核心 CSV 的写出顺序固定，便于自动回归检查文件集合。
    write_csv_rows(OUTPUT_DIR / "frequency_sources.csv", frequency_audit_rows)
    write_csv_rows(OUTPUT_DIR / "raw_mode_features.csv", raw_feature_rows)
    write_csv_rows(OUTPUT_DIR / "assignment_candidates.csv", candidate_rows)
    write_csv_rows(OUTPUT_DIR / "target_candidate_costs.csv", edge_rows)
    write_csv_rows(OUTPUT_DIR / "target_assignment.csv", assignment_rows)
    # 没有近重根时写一行明确状态，避免空 CSV；正式模型可能正是这种情况。
    if subspace_rows:
        write_csv_rows(OUTPUT_DIR / "subspace_audit.csv", subspace_rows)
    else:
        write_csv_rows(
            OUTPUT_DIR / "subspace_audit.csv",
            [
                {
                    "subspace_group": "",
                    "source_modes": "",
                    "mean_frequency_hz": "",
                    "maximum_relative_gap": "",
                    "raw_normal_share_min": "",
                    "raw_normal_share_max": "",
                    "action": "未发现达到阈值的连续近重根",
                    "candidate_count": 0,
                }
            ],
        )
    # 有限频差混合簇独立于严格重根审计；空结果仍写一行明确状态，便于回归脚本
    # 区分“未发现”与“流水线漏写文件”。
    if identification_cluster_rows:
        write_csv_rows(
            OUTPUT_DIR / "identification_cluster_audit.csv",
            identification_cluster_rows,
        )
    else:
        write_csv_rows(
            OUTPUT_DIR / "identification_cluster_audit.csv",
            [
                {
                    "identification_cluster": "",
                    "source_modes": "",
                    "mean_frequency_hz": "",
                    "maximum_relative_span": "",
                    "axes": "",
                    "symmetry": "",
                    "action": "未发现达到判据的有限频差方向混合簇",
                    "axis_1_max_fraction": "",
                    "axis_2_max_fraction": "",
                    "subspace_separability": "",
                    "axis_1_diagnostic_coefficients": "",
                    "axis_2_diagnostic_coefficients": "",
                    "combination_warning": "",
                }
            ],
        )

    # 图件统一样式后依次生成；任何一图失败都会让脚本非零退出，防止半套交付。
    configure_plot_style()
    create_frequency_assignment_figure(references, assignment_rows)
    create_cost_matrix_figure(references, candidates, assignment_rows, cost_matrix)
    create_assigned_profile_figure(references, candidates, assignment_rows)
    create_local_participation_figure(candidates, assignment_rows)

    # 构件节点覆盖数从注册表掩码直接读取，与每阶结果无关。
    gate_node_count = int(np.sum(registry.class_masks["gate"]))
    passage_node_count = int(np.sum(registry.class_masks["passage"]))
    report_path = write_markdown_report(
        raw_dir,
        primary_path,
        supplemental_paths,
        references,
        candidates,
        assignment_rows,
        subspace_rows,
        identification_cluster_rows,
        optimal_total_cost,
        len(mode_files),
        passage_node_count,
        gate_node_count,
    )

    # audit_inputs 只哈希关键小文件和每阶向量；大型文件逐个流式读取，不叠加内存。
    audit_input_paths = [REFERENCE_CSV, ATTACHMENT_PDF, primary_path, *supplemental_paths, *frequency_sources]
    # 模态向量数量较多但每个文件都属于结果证据，因此全部纳入哈希。
    audit_input_paths.extend(mode_files[mode_number] for mode_number in sorted(mode_files))
    # 绝对路径去重防止同一频率文件被自动发现和显式参数同时登记。
    unique_audit_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path in audit_input_paths:
        resolved = path.resolve()
        if resolved not in seen_paths:
            unique_audit_paths.append(path)
            seen_paths.add(resolved)
    input_hashes = {
        str(path): sha256_file(path)
        for path in unique_audit_paths
        if path.is_file()
    }
    # audit_summary 聚合机器复核所需参数、计数和硬限制，不复制大型逐边矩阵。
    audit_summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "raw_dir": str(raw_dir),
        "mode_count": len(mode_files),
        "mode_range": [min(mode_files), max(mode_files)],
        "candidate_count": len(candidates),
        "reference_count": len(references),
        "degenerate_relative_gap": args.degenerate_relative_gap,
        "degenerate_groups": [list(group) for group in degenerate_groups],
        "identification_cluster_relative_gap": args.identification_cluster_relative_gap,
        "identification_clusters": identification_cluster_rows,
        "optimal_total_feature_cost": optimal_total_cost,
        "one_to_one_unique_candidate_count": len(
            {str(row["assigned_candidate"]) for row in assignment_rows}
        ),
        "gate_node_count": gate_node_count,
        "passage_node_count": passage_node_count,
        "mac_available": False,
        "mac_unavailable_reason": "附件未提供质量归一化源模态向量",
        # encoding_contract 明确区分人工文本、Excel审计表和机器JSON的编码，
        # 后续复核不再依赖操作系统或编辑器的隐式编码猜测。
        "encoding_contract": {
            "markdown": "UTF-8 with BOM (utf-8-sig)",
            "csv": "UTF-8 with BOM (utf-8-sig)",
            "json": "UTF-8 without BOM",
        },
        "input_sha256": input_hashes,
    }
    audit_path = OUTPUT_DIR / "modal_pipeline_audit.json"
    audit_path.write_text(
        json.dumps(audit_summary, ensure_ascii=False, indent=2),
        encoding=MACHINE_JSON_ENCODING,
    )

    # 标准输出只给关键路径和计数，供 PowerShell/CI 捕获，不打印数百行中间数据。
    print(f"MODE_COUNT={len(mode_files)}")
    print(f"CANDIDATE_COUNT={len(candidates)}")
    print(f"ASSIGNMENT_CSV={OUTPUT_DIR / 'target_assignment.csv'}")
    print(f"REPORT={report_path}")
    print(f"AUDIT={audit_path}")
    return 0


if __name__ == "__main__":
    # 只有直接执行脚本时才生成/覆盖产物；被单元测试导入时不会修改文件系统。
    raise SystemExit(main())
