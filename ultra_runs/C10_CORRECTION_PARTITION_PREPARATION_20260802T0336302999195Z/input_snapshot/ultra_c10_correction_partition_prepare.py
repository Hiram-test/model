# -*- coding: utf-8 -*-  # 声明源码采用 UTF-8，保证中文审计说明与 Windows 路径可稳定解析。
"""从冻结质量分项台账与冻结荷载迁移 include 构造可审计的分组件修正分区准备包。

本工具只做离线数据重建与守恒核验，不生成可执行 APDL、不启动 ANSYS，也不修改任何冻结源文件。
主分区 ``GATE_ONLY`` 与 ``CROSS_PASSAGE_HALF_ONLY`` 互斥且完备；``H03_COMPLETE_PAIRED`` 是一个
与前两者重叠的局部诊断视图，不能再次叠加到主分区，否则会重复计入。所有候选分区必须在严格
``1e-6 N`` 门限内保持零合力，同时完整保留由旧、新真实节点坐标决定的迁移合矩。
"""

from __future__ import annotations  # 延迟解析类型注解，避免运行期为前向类型引用增加额外依赖。

import argparse  # 解析显式输入、输出路径与自测开关，避免隐式依赖当前工作目录。
import csv  # 读取冻结 CSV 台账并写出逐分项修正长表。
import hashlib  # 为全部输入快照和输出工件计算 SHA256 身份摘要。
import json  # 读取质量审计并写出机器可读的分区审计结果。
import shutil  # 只读复制源文件到新准备包的输入快照目录，保留可复算证据。
import sys  # 根据主流程结果返回成功或失败关闭的进程状态码。
from collections import defaultdict  # 按节点、站位和分区聚合贡献，同时保留每条来源记录。
from decimal import Decimal, getcontext  # 以十进制定点精度复现 APDL 文本数值，避免二进制浮点漂移。
from pathlib import Path  # 安全处理含中文和空格的 Windows 文件路径。
from typing import Iterable, Mapping, Sequence  # 明确函数输入集合、映射与顺序约束。


getcontext().prec = 60  # 使用 60 位十进制精度，使节点力与 N·mm 合矩累加远离舍入上限。

SCHEMA_VERSION = 1  # 固定本准备包机器审计 schema 的首版编号，供后续工具拒绝不兼容格式。
GRAVITY_MM_S2 = Decimal("9806")  # 采用项目冻结 N-mm-tonne-s 单位制重力加速度，单位 mm/s²。
FORCE_ZERO_TOLERANCE_N = Decimal("1e-6")  # 每个候选分区允许的最大合力绝对值，单位 N。
NODE_MATCH_TOLERANCE_N = Decimal("1e-6")  # 分项源重建值与冻结 include 单节点值的最大允许差，单位 N。
COORDINATE_MATCH_TOLERANCE_MM = Decimal("1e-6")  # H03 显式站位关系允许的坐标闭合误差，单位 mm。
MOMENT_REFERENCE_TOLERANCE_NMM = Decimal("1e-6")  # 对父级已独立核验合矩的最大允许复核差，单位 N·mm。
SOURCE_TO_RUNTIME_COORDINATE_TOLERANCE_MM = Decimal("1e-3")  # 源 CSV 坐标与冻结求解 deck 文本坐标允许的最大渲染差，单位 mm。
EXPECTED_CORRECTION_NODE_COUNT = 15_071  # 冻结 include 中非数值尘埃修正节点的权威数量。
EXPECTED_POSITIVE_NODE_COUNT = 11_947  # 冻结 include 中迁移到新生成节点的正修正节点数量。
EXPECTED_NEGATIVE_NODE_COUNT = 3_124  # 冻结 include 中从旧绳索节点移除荷载的负修正节点数量。
EXPECTED_TOTAL_MX_NMM = Decimal("-5224390.90299234")  # 父级独立坐标核验得到的总 X 轴合矩，单位 N·mm。
EXPECTED_TOTAL_MY_NMM = Decimal("-2973859.39218768")  # 父级独立坐标核验得到的总 Y 轴合矩，单位 N·mm。
EXPECTED_CORRECTION_SHA256 = "7a8c359c3f332f7b214b6f51e5e26ebf80899b15418388250033cfdc4e76d9d0"  # 锁定原迁移 include 的冻结身份。
EXPECTED_ALLOCATION_SHA256 = "ad923f5bef3e6ef91b045f1f37d69c93c8970a6caca75a51bd377f1267c81213"  # 锁定当前求解链采用的质量分项台账身份。
EXPECTED_MAPPING_SHA256 = "99e3a14e3f368d4bc2262347387b64daafc46dedbe5a9fc30261eba1795fe475"  # 锁定权威 MCT 到 APDL 荷载映射身份。
EXPECTED_NODES_SHA256 = "b8c7f44823f5648f59af7791dcc5468656725fcc5e0f67b034ed7f3804727e5a"  # 锁定旧绳索节点坐标表身份。
EXPECTED_STATIONS_SHA256 = "820a74e0e3d6f8b3334f0b153ce7da80b9452c874c7a0b64fdcc3a0da515c054"  # 锁定 H01～H21 专用站位解析表身份。
EXPECTED_MASS_AUDIT_SHA256 = "3df93394c22454c18ef9e5f9ce1305d2d798d40f55e2eadc6e53c22a2a2e7e50"  # 锁定质量空间化总审计身份。
EXPECTED_BASE_MESH_SHA256 = "be556489f10b90389c786c70e0455d29bc186c16ebbad61cd29c5b90a4c79957"  # 锁定冻结求解 deck 的旧节点基础网格坐标身份。
EXPECTED_FINITE_GEOMETRY_SHA256 = "4f7da8425a25739c694880422c4d2188088b83c1d64170baf44accd922b5b01e"  # 锁定冻结求解 deck 的有限门架与横通道节点坐标身份。

RELOCATED_COMPONENTS = frozenset(  # 定义从旧索节点迁移到有限门架或横通道节点的唯一五类分项。
    {  # 使用不可变集合，避免运行中意外改变质量所有权边界。
        "gate_bottom_beam",  # 门架下横梁分项属于门架候选分区。
        "ordinary_gate",  # 普通门架上部框架分项属于门架候选分区。
        "cross_passage_tri_gate",  # 横通道专用三角门架上部框架分项属于门架候选分区。
        "guide_roller",  # 门架导轮组分项属于门架候选分区。
        "cross_passage_half",  # 两幅半横通道合并后属于横通道候选分区。
    }  # 结束五类迁移分项的不可变集合定义。
)  # 完成迁移分项集合构造。
GATE_COMPONENTS = frozenset(  # 定义 gate-only 候选包含的四类门架分项。
    {  # 使用不可变集合保证候选筛选在整次准备中保持一致。
        "gate_bottom_beam",  # 纳入所有门架下横梁修正。
        "ordinary_gate",  # 纳入所有普通门架上部修正。
        "cross_passage_tri_gate",  # 纳入所有横通道专用三角门架修正。
        "guide_roller",  # 纳入所有导轮组修正。
    }  # 结束门架分项集合定义。
)  # 完成门架分项集合构造。
PASSAGE_COMPONENT = "cross_passage_half"  # 定义 cross-passage-only 候选的唯一物理分项标识。

COMPONENT_UNIT_WEIGHT_KN = {  # 冻结质量生成器采用的物理分项单件重量，单位 kN。
    "large_crossbeam": Decimal("1.32"),  # 大横梁单件重量，仅用于组合唯一分解校验。
    "gate_bottom_beam": Decimal("3.18"),  # 门架下横梁单件重量。
    "pws_roller": Decimal("1.21"),  # PWS 滚筒单件重量，仅用于组合唯一分解校验。
    "cross_passage_half": Decimal("49.69"),  # 单幅半横通道单件重量。
    "main_cable_restrainer": Decimal("14.72"),  # 主缆抑位器单件重量，仅用于组合唯一分解校验。
    "main_tower_frame": Decimal("67.9833"),  # 主塔架单件重量，仅用于组合唯一分解校验。
    "aux_tower_frame": Decimal("59.6937"),  # 辅助塔架单件重量，仅用于组合唯一分解校验。
    "anchorage_frame": Decimal("62.7153"),  # 锚碇架单件重量，仅用于组合唯一分解校验。
    "ordinary_gate": Decimal("8.927"),  # 普通门架上部单件重量。
    "guide_roller": Decimal("9.196"),  # 导轮组单件重量。
    "cross_passage_tri_gate": Decimal("12.36"),  # 横通道专用三角门架上部单件重量。
}  # 完成分项单件重量字典定义。

BOTTOM_COMBINATIONS = {  # 定义底索 MCT 组合重量到物理分项数量的唯一冻结映射。
    Decimal("1.21"): {"pws_roller": 1},  # 仅含一套 PWS 滚筒。
    Decimal("1.32"): {"large_crossbeam": 1},  # 仅含一件大横梁。
    Decimal("2.53"): {"pws_roller": 1, "large_crossbeam": 1},  # 同站含 PWS 与大横梁。
    Decimal("3.18"): {"gate_bottom_beam": 1},  # 仅含一件门架下横梁。
    Decimal("4.50"): {"gate_bottom_beam": 1, "large_crossbeam": 1},  # 同站含门架下横梁与大横梁。
    Decimal("62.1137"): {"aux_tower_frame": 1, "pws_roller": 2},  # 同站含辅助塔架与两套 PWS。
    Decimal("62.2237"): {"aux_tower_frame": 1, "pws_roller": 1, "large_crossbeam": 1},  # 同站含辅助塔架、PWS 与大横梁。
    Decimal("62.7153"): {"anchorage_frame": 1},  # 仅含一件锚碇架。
    Decimal("67.59"): {"cross_passage_half": 1, "main_cable_restrainer": 1, "gate_bottom_beam": 1},  # 横通道站基本组合。
    Decimal("68.80"): {"cross_passage_half": 1, "main_cable_restrainer": 1, "gate_bottom_beam": 1, "pws_roller": 1},  # 横通道站叠加 PWS。
    Decimal("70.12"): {"cross_passage_half": 1, "main_cable_restrainer": 1, "gate_bottom_beam": 1, "pws_roller": 1, "large_crossbeam": 1},  # 横通道站叠加 PWS 与大横梁。
    Decimal("67.9833"): {"main_tower_frame": 1},  # 仅含一件主塔架。
}  # 完成底索组合分解表定义。
GATE_COMBINATIONS = {  # 定义门架索 MCT 组合重量到物理分项数量的唯一冻结映射。
    Decimal("18.123"): {"ordinary_gate": 1, "guide_roller": 1},  # 普通门架与导轮组合。
    Decimal("21.556"): {"cross_passage_tri_gate": 1, "guide_roller": 1},  # 横通道三角门架与导轮组合。
}  # 完成门架索组合分解表定义。

LEDGER_FIELDNAMES = [  # 固定逐分项 CSV 列序，便于下游稳定读取和人工审计。
    "row_id",  # 逐行稳定编号，按节点与来源排序生成。
    "apdl_node_id",  # 修正作用的 MAPDL 节点号。
    "x_mm",  # MAPDL 顺桥向 X 坐标，单位 mm。
    "y_mm",  # MAPDL 横桥向 Y 坐标，单位 mm。
    "z_mm",  # MAPDL 竖向 Z 坐标，单位 mm。
    "source_side",  # OLD_SOURCE_REMOVAL 或 NEW_DESTINATION_ADDITION。
    "component_id",  # 唯一物理质量分项标识。
    "source_subsystem",  # 旧端 bottom/gate；新端留空。
    "source_catwalk",  # 旧端幅号 1/2；新端留空。
    "source_mct_node",  # 旧端 MCT 站位节点号；新端留空。
    "destination_system",  # 新端 gate/passage；旧端留空。
    "destination_assembly",  # 新端门架名或 H01～H21；旧端留空。
    "destination_role",  # 新端有限节点角色；旧端留空。
    "source_identity",  # 可追溯到旧站位或新装配的稳定来源键。
    "raw_correction_fz_n",  # 由冻结分项质量直接换算的原始竖向修正，单位 N。
    "render_adjustment_n",  # 为逐节点精确复现冻结 include 文本值而记录的舍入闭合量，单位 N。
    "correction_fz_n",  # 原始修正与文本舍入闭合量之和，单位 N。
    "moment_x_nmm",  # 该行关于全局原点的 Mx=y*Fz，单位 N·mm。
    "moment_y_nmm",  # 该行关于全局原点的 My=-x*Fz，单位 N·mm。
    "primary_partition_id",  # 互斥完备主分区 GATE_ONLY 或 CROSS_PASSAGE_HALF_ONLY。
    "in_candidate_gate_only",  # 该行是否属于 gate-only 候选，1 表示属于。
    "in_candidate_cross_passage_half_only",  # 该行是否属于横通道分项候选，1 表示属于。
    "in_candidate_h03_complete_paired",  # 该行是否属于 H03 完整配对局部候选，1 表示属于。
    "pairing_status",  # 记录普通分项重建或 H03 显式唯一配对状态。
    "pairing_evidence",  # 记录支持配对的站位坐标、MCT 节点或装配名称证据。
]  # 完成 CSV 固定列序定义。


class PartitionPreparationError(RuntimeError):  # 定义所有失败关闭路径的专用异常类型。
    """表示源身份、唯一配对、守恒或逐节点重组任一硬门失败。"""  # 说明异常只用于拒绝生成可执行候选。


def decimal_text(value: Decimal) -> str:  # 定义稳定输出十进制数值的文本格式函数。
    """返回不丢精度且不受地区设置影响的十进制文本。"""  # 说明返回值直接用于 CSV 与 JSON 审计。

    return format(value, "f") if value == value.to_integral() else format(value.normalize(), "f")  # 整数保留普通十进制，其余去除无意义尾零。


def decimal_scientific(value: Decimal) -> str:  # 定义适合极小闭合误差的科学计数输出函数。
    """以统一科学计数法返回十进制值，保留全部有效数字。"""  # 说明该格式用于力和合矩误差字段。

    return format(value, "E")  # 使用 Decimal 原生科学计数，避免先转 float 丢失文本精度。


def sha256_file(path: Path) -> str:  # 定义大文件增量 SHA256 计算函数。
    """计算指定现有文件的 64 字符小写 SHA256 摘要。"""  # 说明缺失文件由调用前硬门处理。

    digest = hashlib.sha256()  # 创建独立摘要对象，防止不同文件状态串联。
    with path.open("rb") as stream:  # 使用二进制读取，避免换行和编码转换改变摘要。
        while True:  # 按固定块循环读取直到文件末尾。
            block = stream.read(1024 * 1024)  # 每次读取 1 MiB，在速度与内存占用之间取稳定平衡。
            if not block:  # 空块表示已经到达文件末尾。
                break  # 结束当前文件摘要循环。
            digest.update(block)  # 把原始字节块追加到 SHA256 状态。
    return digest.hexdigest()  # 返回适合 JSON、Markdown 与哈希清单记录的小写摘要。


def require_file(path: Path, label: str) -> None:  # 定义输入文件存在性硬门函数。
    """要求路径是普通文件，否则立即失败关闭。"""  # 说明 label 用于生成可理解的错误信息。

    if not path.is_file():  # 缺失或目录路径都不能作为冻结输入。
        raise PartitionPreparationError(f"缺少冻结输入 {label}：{path}")  # 报出精确缺失项并停止准备。


def require_sha256(path: Path, expected: str, label: str) -> str:  # 定义冻结输入身份硬门函数。
    """校验文件 SHA256 等于冻结期望值并返回实际摘要。"""  # 说明失败时不得继续解释不同版本数据。

    require_file(path, label)  # 先检查文件存在，避免摘要函数抛出不具工程语义的异常。
    actual = sha256_file(path)  # 计算当前磁盘字节的实际摘要。
    if actual != expected:  # 任一字节变化都表示输入谱系不再是本工具审查版本。
        raise PartitionPreparationError(f"{label} SHA256 不匹配：actual={actual}, expected={expected}")  # 报出实际与期望摘要后失败关闭。
    return actual  # 返回已验证摘要，供机器审计直接绑定。


def read_csv_rows(path: Path) -> list[dict[str, str]]:  # 定义 UTF-8-SIG CSV 全表读取函数。
    """读取 CSV 为保留原字段文本的字典列表。"""  # 说明数值解析由物理语义函数显式完成。

    require_file(path, path.name)  # 在解码前确认文件存在且为普通文件。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 兼容带 BOM 与无 BOM 的项目 CSV。
        reader = csv.DictReader(stream)  # 以首行字段名建立逐行字典，避免依赖列位置。
        if reader.fieldnames is None:  # 空文件没有 schema，不能作为权威台账。
            raise PartitionPreparationError(f"CSV 缺少表头：{path}")  # 明确拒绝无 schema 输入。
        return list(reader)  # 一次读入以支持多轮唯一性与守恒交叉检查。


def load_json(path: Path) -> dict[str, object]:  # 定义 UTF-8-SIG JSON 读取函数。
    """读取 JSON 对象并要求根节点是字典。"""  # 说明数组或标量根节点不符合审计 schema。

    require_file(path, path.name)  # 在解码前确认文件存在。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 兼容项目既有带 BOM JSON。
    if not isinstance(value, dict):  # 机器审计根节点必须支持按字段访问。
        raise PartitionPreparationError(f"JSON 根节点不是对象：{path}")  # 拒绝 schema 类型错误。
    return value  # 返回已验证的对象字典。


def parse_decimal(raw: str, label: str) -> Decimal:  # 定义带字段上下文的十进制解析函数。
    """把非空数值文本解析为有限 Decimal。"""  # 说明异常会带出精确字段标签。

    try:  # 捕获空文本、非数字与无穷值等解析问题。
        value = Decimal(raw.strip())  # 去除表格空白后按十进制文本精确解析。
    except Exception as exc:  # Decimal 的多种格式异常统一转换为工程失败关闭错误。
        raise PartitionPreparationError(f"无法解析 {label}={raw!r}") from exc  # 保留原异常链方便开发复核。
    if not value.is_finite():  # NaN 与正负无穷都不能参与质量或合矩审计。
        raise PartitionPreparationError(f"{label} 不是有限数：{raw!r}")  # 明确拒绝非有限值。
    return value  # 返回有限十进制数值。


def parse_correction_include(path: Path) -> dict[int, Decimal]:  # 定义冻结迁移 include 的 FZ 向量解析函数。
    """解析 ``F,node,FZ,C10_BETA*(value)`` 并执行节点数、符号与总和硬门。"""  # 说明只接受项目冻结渲染格式。

    corrections: dict[int, Decimal] = {}  # 以节点号保存唯一基准修正，beta 缩放不在本工具内展开。
    fcum_repl_count = 0  # 统计显式替换模式命令，必须且只能有一次。
    for raw_line in path.read_text(encoding="utf-8").splitlines():  # 按冻结 include 的普通 UTF-8 编码逐行读取。
        line = raw_line.strip()  # 去除首尾空白，使解析不受缩进影响。
        if line.upper() == "FCUM,REPL":  # 识别固定节点集的替换载荷语义。
            fcum_repl_count += 1  # 累加替换命令数量，后续要求唯一。
            continue  # 当前行不是节点力记录，继续解析下一行。
        if not line.upper().startswith("F,"):  # 注释和选择命令不参与修正向量。
            continue  # 跳过非 F 命令行。
        parts = line.split(",", 3)  # 仅拆分前三个逗号，保留表达式内部文本完整。
        if len(parts) != 4 or parts[2].upper() != "FZ":  # 本工具只允许四字段竖向节点力命令。
            raise PartitionPreparationError(f"迁移 include 出现未审查 F 命令：{line}")  # 拒绝其他自由度或语法变体。
        node_id = int(parts[1])  # 解析 APDL 节点号，非整数会直接失败关闭。
        expression = parts[3].strip()  # 提取 C10_BETA 缩放表达式。
        prefix = "C10_BETA*("  # 固定冻结表达式前缀，确保 beta 端点语义未改变。
        if not expression.upper().startswith(prefix) or not expression.endswith(")"):  # 要求完整括号和固定变量名。
            raise PartitionPreparationError(f"迁移 include 出现未审查表达式：{line}")  # 拒绝常量、累加或其他缩放方式。
        value = parse_decimal(expression[len(prefix) : -1], f"节点 {node_id} 修正 FZ")  # 精确解析括号内基准修正值。
        if node_id in corrections:  # 同节点重复 F 命令会使替换顺序影响最终向量。
            raise PartitionPreparationError(f"迁移 include 节点 {node_id} 重复定义")  # 拒绝顺序相关的非唯一节点向量。
        corrections[node_id] = value  # 保存唯一节点修正值。
    if fcum_repl_count != 1:  # 固定 include 必须显式且唯一声明替换模式。
        raise PartitionPreparationError(f"FCUM,REPL 数量为 {fcum_repl_count}，预期 1")  # 拒绝累加语义不明的输入。
    if len(corrections) != EXPECTED_CORRECTION_NODE_COUNT:  # 节点集变化表示冻结向量身份失效。
        raise PartitionPreparationError(f"修正节点数为 {len(corrections)}，预期 {EXPECTED_CORRECTION_NODE_COUNT}")  # 报出节点数差异。
    positive_count = sum(1 for value in corrections.values() if value > 0)  # 统计新生成节点的正修正数量。
    negative_count = sum(1 for value in corrections.values() if value < 0)  # 统计旧索节点的负修正数量。
    if positive_count != EXPECTED_POSITIVE_NODE_COUNT or negative_count != EXPECTED_NEGATIVE_NODE_COUNT:  # 符号拓扑必须与冻结审计一致。
        raise PartitionPreparationError(f"修正符号数量异常：positive={positive_count}, negative={negative_count}")  # 拒绝正负节点集变化。
    total_force = sum(corrections.values(), Decimal("0"))  # 精确累加 include 文本渲染后的总修正力。
    if abs(total_force) > FORCE_ZERO_TOLERANCE_N:  # 全向量必须在严格工程门限内保持恒总竖向荷载。
        raise PartitionPreparationError(f"冻结修正向量总力不闭合：{total_force} N")  # 拒绝总荷载变化超门限的输入。
    return corrections  # 返回已通过身份、数量、符号和总力硬门的节点向量。


def load_original_coordinates(path: Path) -> dict[int, tuple[Decimal, Decimal, Decimal]]:  # 定义旧节点坐标读取与坐标系转换函数。
    """把 CAD 坐标转换为 MAPDL=(CAD_Y,-CAD_X,CAD_Z) 坐标。"""  # 说明返回单位均为 mm。

    coordinates: dict[int, tuple[Decimal, Decimal, Decimal]] = {}  # 保存所有旧绳索节点的唯一 MAPDL 坐标。
    for row in read_csv_rows(path):  # 逐行读取权威旧节点表。
        node_id = int(row["node_id"])  # 解析旧 APDL 节点号。
        if node_id in coordinates:  # 节点号重复会让坐标来源不唯一。
            raise PartitionPreparationError(f"旧节点坐标表节点 {node_id} 重复")  # 拒绝重复节点定义。
        cad_x = parse_decimal(row["x_mm"], f"旧节点 {node_id} CAD_X")  # 解析 CAD 横桥坐标。
        cad_y = parse_decimal(row["y_mm"], f"旧节点 {node_id} CAD_Y")  # 解析 CAD 顺桥坐标。
        cad_z = parse_decimal(row["z_mm"], f"旧节点 {node_id} CAD_Z")  # 解析 CAD 竖向坐标。
        coordinates[node_id] = (cad_y, -cad_x, cad_z)  # 应用冻结 XLongitudinal 坐标变换。
    return coordinates  # 返回节点号到三维 MAPDL 坐标的完整映射。


def load_runtime_coordinates(paths: Sequence[Path], required_nodes: set[int]) -> dict[int, tuple[Decimal, Decimal, Decimal]]:  # 定义冻结求解 deck 节点坐标解析函数。
    """从基础网格和有限构件 include 中读取实际进入 MAPDL 的数值 ``N`` 命令。"""  # 说明符号表达式节点只在不是目标节点时允许跳过。

    coordinates: dict[int, tuple[Decimal, Decimal, Decimal]] = {}  # 保存冻结运行时节点号到真实 deck 文本坐标的唯一映射。
    for path in paths:  # 按基础网格在前、有限构件在后的固定顺序读取两份冻结几何输入。
        require_file(path, f"冻结求解节点坐标 {path.name}")  # 在逐行解析前确认当前 deck 文件存在。
        with path.open("r", encoding="utf-8", errors="strict") as stream:  # 按 APDL include 的普通 UTF-8 编码读取原始文本。
            for line_number, raw_line in enumerate(stream, start=1):  # 保留行号以便报出具体坐标解析问题。
                line = raw_line.strip()  # 去除换行与无意义首尾空白。
                if not line.upper().startswith("N,"):  # 只有显式节点定义命令参与运行时坐标索引。
                    continue  # 跳过材料、单元、注释与控制命令。
                parts = line.split(",")  # APDL N 命令的节点号和三坐标均以逗号分隔。
                if len(parts) < 5:  # 数值 N 命令至少需要命令名、节点号和 X/Y/Z 三坐标。
                    continue  # 非完整模板行若不引用目标节点，由缺失节点硬门统一处理。
                try:  # 节点模板可能包含 APDL 参数表达式，因此先尝试解析整数节点号。
                    node_id = int(parts[1].strip())  # 解析显式 APDL 节点号。
                except ValueError:  # 参数化节点号不是本冻结修正向量的数值目标节点。
                    continue  # 跳过无法建立数值节点键的模板命令。
                if node_id not in required_nodes:  # 只解析 15,071 个修正节点，避免无关符号坐标触发误报。
                    continue  # 跳过非目标节点以降低内存与解析开销。
                try:  # 目标节点的运行时三坐标必须全部是确定数值。
                    coordinate = (Decimal(parts[2].strip()), Decimal(parts[3].strip()), Decimal(parts[4].strip()))  # 精确解析 deck 文本 X/Y/Z 坐标。
                except Exception as exc:  # 任一目标坐标为参数表达式都意味着当前源不足以独立计算合矩。
                    raise PartitionPreparationError(f"冻结 deck 目标节点 {node_id} 坐标不是确定数值：{path}:{line_number}") from exc  # 按要求失败关闭且不猜参数值。
                if not all(value.is_finite() for value in coordinate):  # NaN 或无穷坐标不能定义物理力臂。
                    raise PartitionPreparationError(f"冻结 deck 目标节点 {node_id} 含非有限坐标：{coordinate}")  # 拒绝非法几何。
                if node_id in coordinates and coordinates[node_id] != coordinate:  # 同一目标节点若被两份 include 以不同坐标重复定义，运行时值取决于顺序。
                    raise PartitionPreparationError(f"冻结 deck 目标节点 {node_id} 重复且坐标冲突：{coordinates[node_id]} vs {coordinate}")  # 拒绝顺序相关的非唯一几何。
                coordinates[node_id] = coordinate  # 保存或确认当前目标节点的运行时坐标。
    missing_nodes = sorted(required_nodes - set(coordinates))  # 找出冻结修正向量中没有数值 deck 坐标的节点。
    if missing_nodes:  # 任一缺失节点都会使总合矩无法完整复现。
        raise PartitionPreparationError(f"冻结 deck 缺少 {len(missing_nodes)} 个修正节点坐标：{missing_nodes[:20]}")  # 报出前 20 个缺失节点并失败关闭。
    return coordinates  # 返回覆盖全部冻结修正节点的实际运行时坐标。


def apply_runtime_coordinates(contributions: Sequence[dict[str, object]], runtime_coordinates: Mapping[int, tuple[Decimal, Decimal, Decimal]]) -> dict[str, object]:  # 定义源坐标与冻结运行时坐标核对及替换函数。
    """核对 CSV 来源坐标仅有文本渲染差，并统一改用实际求解 deck 坐标计算合矩。"""  # 说明质量与站位归属仍来自冻结台账和权威 mapping。

    maximum_dx = Decimal("0")  # 记录源台账坐标与运行时 deck 的最大 X 差绝对值。
    maximum_dy = Decimal("0")  # 记录源台账坐标与运行时 deck 的最大 Y 差绝对值。
    maximum_dz = Decimal("0")  # 记录源台账坐标与运行时 deck 的最大 Z 差绝对值。
    changed_record_count = 0  # 统计至少一个坐标分量文本不完全相同的分项记录数量。
    for record in contributions:  # 遍历全部旧端和新端物理分项记录。
        node_id = int(record["node_id"])  # 读取当前修正作用节点号。
        if node_id not in runtime_coordinates:  # 理论上已由 load_runtime_coordinates 全覆盖硬门保证。
            raise PartitionPreparationError(f"分项记录节点 {node_id} 缺少冻结运行时坐标")  # 防御性拒绝索引不一致。
        runtime_x, runtime_y, runtime_z = runtime_coordinates[node_id]  # 读取实际进入求解器的三维坐标。
        dx = runtime_x - record["x_mm"]  # 计算运行时 X 与源 CSV X 的有符号差。
        dy = runtime_y - record["y_mm"]  # 计算运行时 Y 与源 CSV Y 的有符号差。
        dz = runtime_z - record["z_mm"]  # 计算运行时 Z 与源 CSV Z 的有符号差。
        maximum_dx = max(maximum_dx, abs(dx))  # 更新最大 X 坐标文本差。
        maximum_dy = max(maximum_dy, abs(dy))  # 更新最大 Y 坐标文本差。
        maximum_dz = max(maximum_dz, abs(dz))  # 更新最大 Z 坐标文本差。
        if dx != 0 or dy != 0 or dz != 0:  # 统计任何一个分量存在末位差的记录。
            changed_record_count += 1  # 累加源到运行时坐标替换记录数。
        if max(abs(dx), abs(dy), abs(dz)) > SOURCE_TO_RUNTIME_COORDINATE_TOLERANCE_MM:  # 大于 0.001 mm 就不再视作文本渲染差。
            raise PartitionPreparationError(f"节点 {node_id} 源坐标与冻结 deck 坐标差超限：dx={dx}, dy={dy}, dz={dz} mm")  # 拒绝跨版本几何拼接。
        record["x_mm"] = runtime_x  # 用冻结求解 deck 的真实 X 坐标替换来源表坐标。
        record["y_mm"] = runtime_y  # 用冻结求解 deck 的真实 Y 坐标替换来源表坐标。
        record["z_mm"] = runtime_z  # 用冻结求解 deck 的真实 Z 坐标替换来源表坐标。
    return {"coordinate_authority": "FROZEN_SOLVER_DECK_N_COMMANDS", "required_node_count": len(runtime_coordinates), "changed_record_count": changed_record_count, "maximum_abs_dx_mm": decimal_scientific(maximum_dx), "maximum_abs_dy_mm": decimal_scientific(maximum_dy), "maximum_abs_dz_mm": decimal_scientific(maximum_dz), "source_to_runtime_tolerance_mm": decimal_scientific(SOURCE_TO_RUNTIME_COORDINATE_TOLERANCE_MM), "status": "PASS"}  # 返回源与运行时坐标一致性审计。


def match_combination(subsystem: str, combined_weight_kn: Decimal) -> dict[str, int]:  # 定义 MCT 组合重量唯一分解函数。
    """按子系统返回唯一冻结物理分项数量映射。"""  # 说明未审查或多义组合必须失败关闭。

    patterns = BOTTOM_COMBINATIONS if subsystem == "bottom" else GATE_COMBINATIONS if subsystem == "gate" else None  # 根据子系统选择唯一权威组合表。
    if patterns is None:  # bottom/gate 之外的值表示输入 schema 已改变。
        raise PartitionPreparationError(f"未知权威荷载子系统：{subsystem}")  # 拒绝未审查子系统。
    candidates = [components for weight, components in patterns.items() if abs(weight - combined_weight_kn) <= Decimal("1e-6")]  # 在冻结 1e-6 kN 容差内收集匹配模式。
    if len(candidates) != 1:  # 零匹配或多匹配都不能唯一解释旧负节点。
        raise PartitionPreparationError(f"{subsystem} 组合 {combined_weight_kn} kN 匹配数为 {len(candidates)}")  # 报出组合歧义并停止。
    return dict(candidates[0])  # 返回副本，避免调用者修改全局冻结表。


def build_old_contributions(mapping_rows: Sequence[dict[str, str]], coordinates: Mapping[int, tuple[Decimal, Decimal, Decimal]]) -> tuple[list[dict[str, object]], dict[tuple[str, str, str], list[dict[str, str]]]]:  # 定义旧端迁移分项重建函数。
    """按权威组合与物理索数拆出旧节点上的五类负修正贡献。"""  # 说明同时返回用于 H03 唯一站位检查的分组行。

    contributions: list[dict[str, object]] = []  # 保存每个旧节点、每个迁移分项的一条负修正记录。
    station_rows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)  # 按子系统、幅号、MCT 节点收集完整物理索行。
    station_patterns: dict[tuple[str, str, str], dict[str, int]] = {}  # 保存每个站位的唯一组合分解，防止行间不一致。
    for row in mapping_rows:  # 遍历权威 mapping 的全部 23,028 个物理索记录。
        subsystem = row["subsystem"].strip()  # 读取 bottom 或 gate 子系统标识。
        catwalk = row["catwalk"].strip()  # 读取猫道幅号 1 或 2。
        mct_node = row["mct_node"].strip()  # 读取原 MCT 物理站位节点号。
        node_id = int(row["ansys_node"])  # 读取对应 APDL 物理索节点号。
        if node_id not in coordinates:  # 权威 mapping 引用缺失坐标时无法计算迁移合矩。
            raise PartitionPreparationError(f"旧负节点 {node_id} 缺少权威坐标")  # 报出精确缺失节点并失败关闭。
        combined_weight_kn = abs(parse_decimal(row["mct_total_fz_kn_per_catwalk"], f"站位 {subsystem}/{catwalk}/{mct_node} 组合重量"))  # 读取单幅组合重量绝对值。
        pattern = match_combination(subsystem, combined_weight_kn)  # 唯一分解当前组合为物理分项数量。
        station_key = (subsystem, catwalk, mct_node)  # 构造跨行稳定的物理站位键。
        if station_key in station_patterns and station_patterns[station_key] != pattern:  # 同一站位不同索行必须采用完全相同组合。
            raise PartitionPreparationError(f"站位 {station_key} 的组合分解在索行之间不一致")  # 拒绝站位内部源冲突。
        station_patterns[station_key] = pattern  # 记录或确认站位组合。
        station_rows[station_key].append(row)  # 保存原始行供物理索数和 H03 坐标唯一性检查。
        distribution_count = 16 if subsystem == "bottom" else 6  # 底索组合等分到 16 根，门架索组合等分到 6 根。
        for component_id, quantity in pattern.items():  # 逐个物理分项拆出当前索节点贡献。
            if component_id not in RELOCATED_COMPONENTS:  # 未迁移分项继续由原节点 MASS21 承担，不属于修正向量。
                continue  # 跳过保留分项，避免重复计入重力。
            force_n = -(COMPONENT_UNIT_WEIGHT_KN[component_id] * Decimal(quantity) * Decimal("1000") / Decimal(distribution_count))  # 计算从旧节点移除的精确负修正，单位 N。
            x_mm, y_mm, z_mm = coordinates[node_id]  # 读取旧节点真实 MAPDL 坐标。
            contributions.append(  # 追加一条可追溯旧端物理分项记录。
                {  # 使用统一内部字段 schema 供后续重组和 CSV 输出。
                    "node_id": node_id,  # 保存修正作用节点号。
                    "x_mm": x_mm,  # 保存顺桥向坐标。
                    "y_mm": y_mm,  # 保存横桥向坐标。
                    "z_mm": z_mm,  # 保存竖向坐标。
                    "source_side": "OLD_SOURCE_REMOVAL",  # 标识该行从旧荷载位置移除重量。
                    "component_id": component_id,  # 保存唯一物理分项标识。
                    "source_subsystem": subsystem,  # 保存旧端 bottom/gate 子系统。
                    "source_catwalk": catwalk,  # 保存旧端猫道幅号。
                    "source_mct_node": mct_node,  # 保存旧端 MCT 站位。
                    "destination_system": "",  # 旧端行不占用新端系统字段。
                    "destination_assembly": "",  # 旧端行不占用新端装配字段。
                    "destination_role": "",  # 旧端行不占用新端节点角色字段。
                    "source_identity": f"OLD|{subsystem}|CW{catwalk}|MCT{mct_node}|N{node_id}|{component_id}",  # 构造稳定且可人工解释的旧来源键。
                    "raw_fz_n": force_n,  # 保存权威分项直接计算的负修正值。
                    "render_adjustment_n": Decimal("0"),  # 初始舍入闭合量为零，节点重组时再显式分配。
                    "correction_fz_n": force_n,  # 初始最终修正等于原始物理修正。
                    "pairing_status": "COMPONENT_DECOMPOSED_FROM_AUTHORITATIVE_COMBINATION",  # 记录旧端组合分解依据。
                    "pairing_evidence": f"subsystem={subsystem};catwalk={catwalk};mct_node={mct_node};distribution={distribution_count}",  # 记录唯一组合与物理索数证据。
                }  # 结束旧端贡献字段定义。
            )  # 完成当前旧端贡献追加。
    for station_key, rows in station_rows.items():  # 对所有旧物理站位复核索行完整性。
        expected_count = 16 if station_key[0] == "bottom" else 6  # 根据子系统确定应有物理索数。
        if len(rows) != expected_count:  # 缺索或重复索都会破坏单件重量等分关系。
            raise PartitionPreparationError(f"旧站位 {station_key} 有 {len(rows)} 行，预期 {expected_count}")  # 报出不完整站位并失败关闭。
    return contributions, station_rows  # 返回旧端贡献长表和站位原始行索引。


def load_new_contributions(allocation_rows: Sequence[dict[str, str]]) -> list[dict[str, object]]:  # 定义新端质量分项台账读取函数。
    """读取生成节点上的五类正修正贡献，并拒绝迁移分项残留在旧节点。"""  # 说明正修正按质量乘冻结重力重建。

    contributions: list[dict[str, object]] = []  # 保存每个新节点、每个迁移分项的一条正修正记录。
    for row in allocation_rows:  # 遍历冻结质量分项长表的全部记录。
        component_id = row["component_id"].strip()  # 读取物理质量分项标识。
        if component_id not in RELOCATED_COMPONENTS:  # 保留原节点的其他分项不属于迁移修正。
            continue  # 跳过非迁移分项，保持唯一质量所有权。
        system = row["system"].strip()  # 读取新端 gate 或 passage 系统标识。
        if system not in {"gate", "passage"}:  # 迁移分项若仍标记 original，说明质量所有权没有完成转移。
            raise PartitionPreparationError(f"迁移分项 {component_id} 出现在非生成系统 {system}")  # 拒绝新旧重复或遗漏质量。
        if component_id == PASSAGE_COMPONENT and system != "passage":  # 横通道质量只能由 passage 有限杆系节点承担。
            raise PartitionPreparationError(f"横通道分项误分配到系统 {system}")  # 拒绝系统归属错误。
        if component_id in GATE_COMPONENTS and system != "gate":  # 四类门架质量只能由 gate 有限杆系节点承担。
            raise PartitionPreparationError(f"门架分项 {component_id} 误分配到系统 {system}")  # 拒绝系统归属错误。
        node_id = int(row["apdl_node_id"])  # 解析新生成物理节点号。
        x_mm = parse_decimal(row["x_mm"], f"新节点 {node_id} X")  # 解析新节点顺桥向坐标。
        y_mm = parse_decimal(row["y_mm"], f"新节点 {node_id} Y")  # 解析新节点横桥向坐标。
        z_mm = parse_decimal(row["z_mm"], f"新节点 {node_id} Z")  # 解析新节点竖向坐标。
        mass_tonne = parse_decimal(row["mass_tonne"], f"新节点 {node_id} {component_id} 质量")  # 解析分项质量，单位 tonne。
        if mass_tonne <= 0:  # 新端 MASS21 分项必须为严格正质量。
            raise PartitionPreparationError(f"新节点 {node_id} 的 {component_id} 质量非正：{mass_tonne}")  # 拒绝零或负质量。
        force_n = mass_tonne * GRAVITY_MM_S2  # 按冻结重力把 tonne·mm/s² 直接换为 N。
        assembly = row["assembly_name"].strip()  # 读取新端门架名或 H01～H21 装配名。
        role = row["role"].strip()  # 读取新端有限节点物理角色。
        contributions.append(  # 追加一条可追溯新端物理分项记录。
            {  # 使用与旧端一致的统一内部字段 schema。
                "node_id": node_id,  # 保存修正作用节点号。
                "x_mm": x_mm,  # 保存顺桥向坐标。
                "y_mm": y_mm,  # 保存横桥向坐标。
                "z_mm": z_mm,  # 保存竖向坐标。
                "source_side": "NEW_DESTINATION_ADDITION",  # 标识该行把重量加到真实空间化节点。
                "component_id": component_id,  # 保存唯一物理分项标识。
                "source_subsystem": "",  # 新端行不占用旧端子系统字段。
                "source_catwalk": "",  # 新端行不占用旧端幅号字段。
                "source_mct_node": "",  # 新端行不占用旧端 MCT 节点字段。
                "destination_system": system,  # 保存新端 gate/passage 系统。
                "destination_assembly": assembly,  # 保存新端装配名。
                "destination_role": role,  # 保存新端节点角色。
                "source_identity": f"NEW|{system}|{assembly}|N{node_id}|{component_id}|{role}",  # 构造稳定且可人工解释的新来源键。
                "raw_fz_n": force_n,  # 保存质量台账直接换算的正修正值。
                "render_adjustment_n": Decimal("0"),  # 初始舍入闭合量为零，节点重组时再显式分配。
                "correction_fz_n": force_n,  # 初始最终修正等于原始物理修正。
                "pairing_status": "COMPONENT_READ_FROM_FROZEN_MASS_LEDGER",  # 记录新端质量来源状态。
                "pairing_evidence": f"system={system};assembly={assembly};role={role}",  # 记录新装配与角色证据。
            }  # 结束新端贡献字段定义。
        )  # 完成当前新端贡献追加。
    if not contributions:  # 空的新端贡献表示读错台账或 schema 已改变。
        raise PartitionPreparationError("冻结质量分项台账未找到任何迁移分项")  # 拒绝生成空候选。
    return contributions  # 返回新端正修正贡献长表。


def derive_h03_binding(resolved_rows: Sequence[dict[str, str]], mapping_rows: Sequence[dict[str, str]], station_rows: Mapping[tuple[str, str, str], Sequence[dict[str, str]]], coordinates: Mapping[int, tuple[Decimal, Decimal, Decimal]]) -> dict[str, object]:  # 定义 H03 旧、新装配唯一配对函数。
    """用显式门架 MCT 节点和解析站位偏移唯一锁定 H03 的两幅旧底索站。"""  # 说明禁止按模糊最近距离猜配。

    h03_rows = [row for row in resolved_rows if row["name"].strip() == "H03"]  # 从 H01～H21 解析表精确选择 H03。
    if len(h03_rows) != 1:  # H03 缺失或重复都无法唯一界定局部装配。
        raise PartitionPreparationError(f"resolved_dedicated_stations 中 H03 行数为 {len(h03_rows)}")  # 报出局部装配标识问题。
    h03 = h03_rows[0]  # 获取唯一 H03 解析记录。
    gate_mct_node = h03["source_mct_gate_node"].strip()  # 读取显式绑定的旧门架索 MCT 节点，本项目为 1048。
    gate_assemblies = {h03["cw1_gate_name"].strip(), h03["cw2_gate_name"].strip()}  # 读取两幅新三角门架装配名。
    if len(gate_assemblies) != 2:  # 两幅门架名称必须不同且完整。
        raise PartitionPreparationError(f"H03 新门架装配名不唯一：{sorted(gate_assemblies)}")  # 拒绝装配命名冲突。
    station_y = parse_decimal(h03["station_y_mm"], "H03 station_y_mm")  # 读取新有限门架站位顺桥坐标。
    gate_to_load_offset = parse_decimal(h03["gate_to_load_y_offset_mm"], "H03 gate_to_load_y_offset_mm")  # 读取解析表给出的门架到旧底索荷载站偏移。
    expected_bottom_x = station_y + gate_to_load_offset  # 由显式解析关系计算旧底索 MAPDL X 坐标，本项目精确为 545909 mm。
    old_bottom_keys: set[tuple[str, str, str]] = set()  # 保存两幅唯一旧底索站位键。
    old_gate_keys: set[tuple[str, str, str]] = set()  # 保存两幅显式旧门架索站位键。
    bottom_evidence: list[dict[str, object]] = []  # 保存 H03 底索配对坐标与 MCT 节点证据。
    gate_evidence: list[dict[str, object]] = []  # 保存 H03 门架索配对行数与 MCT 节点证据。
    for catwalk in ("1", "2"):  # 分别对两幅猫道执行独立唯一性硬门。
        gate_key = ("gate", catwalk, gate_mct_node)  # 按显式 MCT 节点构造旧门架索站位键。
        gate_rows = list(station_rows.get(gate_key, []))  # 获取该幅门架索的六根物理索记录。
        if len(gate_rows) != 6:  # 横通道三角门架必须在每幅恰有六根门架索记录。
            raise PartitionPreparationError(f"H03 旧门架索站 {gate_key} 行数为 {len(gate_rows)}，预期 6")  # 报出缺失或重复索行。
        gate_pattern = match_combination("gate", abs(parse_decimal(gate_rows[0]["mct_total_fz_kn_per_catwalk"], f"H03 门架站 {gate_key} 重量")))  # 唯一分解门架组合。
        if gate_pattern != {"cross_passage_tri_gate": 1, "guide_roller": 1}:  # H03 必须对应三角门架而非普通门架。
            raise PartitionPreparationError(f"H03 旧门架索站 {gate_key} 组合不是三角门架+导轮：{gate_pattern}")  # 拒绝错误门架类型。
        old_gate_keys.add(gate_key)  # 记录已通过显式节点和组合硬门的旧门架站。
        gate_evidence.append({"catwalk": catwalk, "mct_node": gate_mct_node, "row_count": len(gate_rows), "pattern": gate_pattern})  # 保存机器可读门架配对证据。
        bottom_candidates: list[tuple[tuple[str, str, str], Decimal, list[dict[str, str]]]] = []  # 收集坐标精确闭合且含横通道分项的底索站候选。
        for station_key, rows in station_rows.items():  # 遍历全部旧站位寻找当前幅的显式坐标匹配。
            if station_key[0] != "bottom" or station_key[1] != catwalk:  # 只检查当前幅的底索站。
                continue  # 跳过其他子系统或另一幅站位。
            first_row = rows[0]  # 同站 16 根物理索具有共同顺桥坐标，可用首行建立坐标门禁。
            pattern = match_combination("bottom", abs(parse_decimal(first_row["mct_total_fz_kn_per_catwalk"], f"底索站 {station_key} 重量")))  # 唯一分解当前底索组合。
            if PASSAGE_COMPONENT not in pattern or "gate_bottom_beam" not in pattern:  # H03 完整配对要求同站同时含半横通道和门架下横梁。
                continue  # 跳过普通门架或非横通道底索站。
            x_values = {coordinates[int(row["ansys_node"])][0] for row in rows}  # 收集该站全部 16 根索的 MAPDL X 坐标。
            if len(x_values) != 1:  # 同一物理站位若顺桥坐标不一致则不能按站整体配对。
                raise PartitionPreparationError(f"底索站 {station_key} 的 X 坐标不唯一：{sorted(x_values)}")  # 报出源几何冲突。
            station_x = next(iter(x_values))  # 取得唯一底索站顺桥坐标。
            if abs(station_x - expected_bottom_x) <= COORDINATE_MATCH_TOLERANCE_MM:  # 只接受显式偏移关系在微米级门限内闭合的站位。
                bottom_candidates.append((station_key, station_x, list(rows)))  # 保存通过坐标、分项和幅号三重门禁的候选。
        if len(bottom_candidates) != 1:  # 零候选表示源信息不足，多候选表示配对不唯一。
            raise PartitionPreparationError(f"H03 第 {catwalk} 幅旧底索唯一候选数为 {len(bottom_candidates)}；expected_x={expected_bottom_x}")  # 按用户要求失败关闭且不得猜。
        bottom_key, station_x, matched_rows = bottom_candidates[0]  # 解包唯一通过硬门的旧底索站。
        if len(matched_rows) != 16:  # 完整半横通道旧荷载必须覆盖一幅 16 根底索。
            raise PartitionPreparationError(f"H03 旧底索站 {bottom_key} 行数为 {len(matched_rows)}，预期 16")  # 拒绝不完整物理索组。
        old_bottom_keys.add(bottom_key)  # 记录已通过唯一性硬门的旧底索站。
        bottom_evidence.append({"catwalk": catwalk, "mct_node": bottom_key[2], "expected_x_mm": decimal_scientific(expected_bottom_x), "actual_x_mm": decimal_scientific(station_x), "coordinate_error_mm": decimal_scientific(station_x - expected_bottom_x), "row_count": len(matched_rows)})  # 保存坐标精确配对证据。
    return {"passage_assembly": "H03", "gate_assemblies": gate_assemblies, "old_bottom_keys": old_bottom_keys, "old_gate_keys": old_gate_keys, "expected_bottom_x_mm": expected_bottom_x, "gate_mct_node": gate_mct_node, "bottom_evidence": bottom_evidence, "gate_evidence": gate_evidence}  # 返回完整 H03 旧、新绑定与证据。


def assign_partition_membership(contributions: Sequence[dict[str, object]], h03_binding: Mapping[str, object]) -> None:  # 定义主分区与三个候选视图成员标记函数。
    """为每条物理分项贡献赋予互斥主分区和重叠 H03 局部候选标记。"""  # 说明函数原位写入内部记录。

    gate_assemblies = set(h03_binding["gate_assemblies"])  # 读取 H03 两幅新门架装配名集合。
    old_bottom_keys = set(h03_binding["old_bottom_keys"])  # 读取 H03 两幅唯一旧底索站位键。
    old_gate_keys = set(h03_binding["old_gate_keys"])  # 读取 H03 两幅显式旧门架索站位键。
    for record in contributions:  # 遍历每条旧端或新端物理分项记录。
        component_id = str(record["component_id"])  # 读取物理分项标识。
        is_gate = component_id in GATE_COMPONENTS  # 判断记录是否属于 gate-only 主分区。
        is_passage = component_id == PASSAGE_COMPONENT  # 判断记录是否属于横通道主分区。
        if is_gate == is_passage:  # 五类迁移分项必须且只能落入一个主分区。
            raise PartitionPreparationError(f"分项 {component_id} 的主分区归属不唯一")  # 拒绝遗漏或重叠主分区。
        record["primary_partition_id"] = "GATE_ONLY" if is_gate else "CROSS_PASSAGE_HALF_ONLY"  # 写入互斥完备主分区标识。
        record["in_candidate_gate_only"] = is_gate  # 标记 gate-only 候选成员。
        record["in_candidate_cross_passage_half_only"] = is_passage  # 标记横通道分项候选成员。
        is_h03 = False  # 默认记录不属于 H03 局部完整配对视图。
        if record["source_side"] == "OLD_SOURCE_REMOVAL":  # 旧端成员按显式站位键判断。
            old_key = (str(record["source_subsystem"]), str(record["source_catwalk"]), str(record["source_mct_node"]))  # 重建旧物理站位键。
            is_h03 = (old_key in old_bottom_keys and component_id in {"gate_bottom_beam", PASSAGE_COMPONENT}) or (old_key in old_gate_keys and component_id in {"cross_passage_tri_gate", "guide_roller"})  # 纳入 H03 旧底索两分项和旧门架索两分项。
        else:  # 新端成员按有限装配名称与分项判断。
            assembly = str(record["destination_assembly"])  # 读取新端装配名。
            is_h03 = (assembly == h03_binding["passage_assembly"] and component_id == PASSAGE_COMPONENT) or (assembly in gate_assemblies and component_id in {"gate_bottom_beam", "cross_passage_tri_gate", "guide_roller"})  # 纳入 H03 横通道和两幅配套三角门架。
        record["in_candidate_h03_complete_paired"] = is_h03  # 写入 H03 完整配对候选成员标记。
        if is_h03:  # 对 H03 成员提升配对状态和证据可见性。
            record["pairing_status"] = "H03_EXPLICIT_UNIQUE_PAIRING_CONFIRMED"  # 标记已经通过显式 MCT/坐标/装配唯一性硬门。
            record["pairing_evidence"] = f"{record['pairing_evidence']};H03_binding=explicit_unique"  # 在原来源证据后追加 H03 唯一配对结论。


def reconcile_to_frozen_vector(contributions: Sequence[dict[str, object]], corrections: Mapping[int, Decimal]) -> dict[str, object]:  # 定义分项贡献到冻结节点向量的逐节点精确重组函数。
    """校验源分项和与 include 一致，并把纯文本舍入差显式记录到确定性锚行。"""  # 说明不允许凭空新增物理修正。

    by_node: dict[int, list[dict[str, object]]] = defaultdict(list)  # 按 APDL 节点聚合全部物理分项贡献。
    for record in contributions:  # 遍历旧端和新端全部贡献记录。
        by_node[int(record["node_id"])].append(record)  # 把记录追加到对应节点组。
    raw_nodes = set(by_node)  # 获取分项源重建涉及的唯一节点集合。
    correction_nodes = set(corrections)  # 获取冻结 include 的唯一节点集合。
    missing_nodes = sorted(correction_nodes - raw_nodes)  # 找出 include 有值但没有物理分项来源的节点。
    extra_nodes = sorted(raw_nodes - correction_nodes)  # 找出物理分项有值但被冻结 include 遗漏的节点。
    if missing_nodes or extra_nodes:  # 节点集必须完全相同才能声明逐节点精确重组。
        raise PartitionPreparationError(f"分项源与冻结向量节点集不一致：missing={missing_nodes[:20]}, extra={extra_nodes[:20]}")  # 报出前 20 个差异节点并失败关闭。
    maximum_raw_error = Decimal("0")  # 记录舍入闭合前单节点最大源差，用于审计来源质量。
    adjusted_node_count = 0  # 统计需要显式文本舍入闭合的节点数量。
    for node_id in sorted(corrections):  # 按节点号稳定处理全部 15,071 个冻结修正节点。
        records = by_node[node_id]  # 获取当前节点的一个或多个分项记录。
        coordinate_set = {(record["x_mm"], record["y_mm"], record["z_mm"]) for record in records}  # 收集节点在所有分项行上的坐标。
        if len(coordinate_set) != 1:  # 同一 APDL 节点不得出现不同空间坐标。
            raise PartitionPreparationError(f"节点 {node_id} 的分项记录坐标不一致")  # 拒绝无法定义唯一合矩臂的节点。
        raw_sum = sum((record["raw_fz_n"] for record in records), Decimal("0"))  # 精确累加质量与组合直接重建的节点修正。
        target = corrections[node_id]  # 读取冻结 include 文本中的权威节点修正。
        raw_error = target - raw_sum  # 计算仅由跨表渲染精度产生的节点闭合差。
        maximum_raw_error = max(maximum_raw_error, abs(raw_error))  # 更新单节点最大源差绝对值。
        if abs(raw_error) > NODE_MATCH_TOLERANCE_N:  # 超过 1e-6 N 说明不是文本舍入而是源分项或配对错误。
            raise PartitionPreparationError(f"节点 {node_id} 分项和不匹配冻结向量：raw={raw_sum}, target={target}, error={raw_error} N")  # 报出完整节点差异并失败关闭。
        if raw_error != 0:  # 仅对确有跨表末位差的节点记录显式闭合量。
            anchor = sorted(records, key=lambda record: (abs(record["raw_fz_n"]), str(record["component_id"]), str(record["source_identity"])))[-1]  # 选择绝对贡献最大且排序稳定的锚行，最小化相对扰动并消除任意性。
            anchor["render_adjustment_n"] = raw_error  # 把冻结文本与物理分项和的末位差单独记录。
            anchor["correction_fz_n"] = anchor["raw_fz_n"] + raw_error  # 使当前节点分项和精确等于 include 文本值。
            adjusted_node_count += 1  # 累加发生显式文本闭合的节点数量。
        recomposed = sum((record["correction_fz_n"] for record in records), Decimal("0"))  # 重新累加闭合后的节点分项值。
        if recomposed != target:  # Decimal 精确重组必须逐节点文本数值相等，不使用容差掩盖错误。
            raise PartitionPreparationError(f"节点 {node_id} 闭合后仍不精确：{recomposed} != {target}")  # 拒绝任何非零逐节点重组误差。
    return {"node_count": len(by_node), "missing_node_count": len(missing_nodes), "extra_node_count": len(extra_nodes), "exact_node_recomposition": True, "maximum_raw_source_error_n": decimal_scientific(maximum_raw_error), "render_adjusted_node_count": adjusted_node_count}  # 返回逐节点精确重组审计摘要。


def summarize_records(records: Iterable[dict[str, object]]) -> dict[str, object]:  # 定义任意记录子集的合力、合矩与节点数汇总函数。
    """按全局原点计算 Fz、Mx=yFz、My=-xFz 与正负记录统计。"""  # 说明只存在竖向力，因此 Mz 恒为零。

    selected = list(records)  # 固化迭代器，支持多轮统计且保持稳定顺序。
    force = sum((record["correction_fz_n"] for record in selected), Decimal("0"))  # 精确累加竖向修正合力。
    moment_x = sum((record["y_mm"] * record["correction_fz_n"] for record in selected), Decimal("0"))  # 精确累加关于 X 轴的合矩。
    moment_y = sum((-record["x_mm"] * record["correction_fz_n"] for record in selected), Decimal("0"))  # 精确累加关于 Y 轴的合矩。
    nodes = {int(record["node_id"]) for record in selected}  # 统计子集涉及的唯一 APDL 节点。
    return {"row_count": len(selected), "node_count": len(nodes), "positive_row_count": sum(1 for record in selected if record["correction_fz_n"] > 0), "negative_row_count": sum(1 for record in selected if record["correction_fz_n"] < 0), "sum_fz_n": decimal_scientific(force), "sum_mx_nmm": decimal_scientific(moment_x), "sum_my_nmm": decimal_scientific(moment_y), "sum_mz_nmm": "0E+0", "zero_force_tolerance_n": decimal_scientific(FORCE_ZERO_TOLERANCE_N), "zero_force_status": "PASS" if abs(force) <= FORCE_ZERO_TOLERANCE_N else "FAIL"}  # 返回机器可读汇总与零合力判定。


def validate_h03_component_pairs(contributions: Sequence[dict[str, object]]) -> dict[str, object]:  # 定义 H03 完整配对逐分项质量闭合函数。
    """要求 H03 四类分项在旧端移除量与新端增加量分别闭合。"""  # 说明该检查避免总量偶然抵消掩盖错配。

    h03_records = [record for record in contributions if bool(record["in_candidate_h03_complete_paired"])]  # 选择 H03 完整配对局部候选全部记录。
    expected_components = {"gate_bottom_beam", "cross_passage_tri_gate", "guide_roller", PASSAGE_COMPONENT}  # 定义 H03 应有的四类物理分项。
    actual_components = {str(record["component_id"]) for record in h03_records}  # 收集实际 H03 分项集合。
    if actual_components != expected_components:  # 缺少或混入分项都表示局部装配不完整。
        raise PartitionPreparationError(f"H03 分项集合不完整：actual={sorted(actual_components)}, expected={sorted(expected_components)}")  # 报出集合差异并失败关闭。
    result: dict[str, object] = {}  # 保存四类分项逐项旧、新闭合结果。
    for component_id in sorted(expected_components):  # 按稳定分项名顺序逐项核验。
        component_rows = [record for record in h03_records if record["component_id"] == component_id]  # 选择当前分项的 H03 记录。
        old_force = sum((record["correction_fz_n"] for record in component_rows if record["source_side"] == "OLD_SOURCE_REMOVAL"), Decimal("0"))  # 累加旧端负修正。
        new_force = sum((record["correction_fz_n"] for record in component_rows if record["source_side"] == "NEW_DESTINATION_ADDITION"), Decimal("0"))  # 累加新端正修正。
        closure = old_force + new_force  # 计算当前物理分项的迁移合力闭合值。
        if abs(closure) > FORCE_ZERO_TOLERANCE_N:  # 每个分项本身也必须在严格门限内质量守恒。
            raise PartitionPreparationError(f"H03 分项 {component_id} 不闭合：old={old_force}, new={new_force}, closure={closure} N")  # 拒绝总量偶然抵消。
        result[component_id] = {"old_removal_fz_n": decimal_scientific(old_force), "new_addition_fz_n": decimal_scientific(new_force), "closure_fz_n": decimal_scientific(closure), "status": "PASS"}  # 保存逐分项配对结果。
    return result  # 返回 H03 四类分项的独立闭合证据。


def validate_and_build_audit(contributions: Sequence[dict[str, object]], corrections: Mapping[int, Decimal], source_binding: Mapping[str, object], h03_binding: Mapping[str, object], recomposition: Mapping[str, object]) -> dict[str, object]:  # 定义总体验证与机器审计构造函数。
    """执行主分区完备性、候选零合力、总合矩和 H03 逐分项硬门。"""  # 说明成功结果仍只允许作为求解前准备工件。

    gate_rows = [record for record in contributions if bool(record["in_candidate_gate_only"])]  # 选择 gate-only 候选全部记录。
    passage_rows = [record for record in contributions if bool(record["in_candidate_cross_passage_half_only"])]  # 选择横通道分项候选全部记录。
    h03_rows = [record for record in contributions if bool(record["in_candidate_h03_complete_paired"])]  # 选择 H03 完整配对局部候选全部记录。
    if len(gate_rows) + len(passage_rows) != len(contributions):  # 两个主分区必须互斥且覆盖所有物理分项行。
        raise PartitionPreparationError("gate 与 passage 主分区未形成互斥完备覆盖")  # 拒绝主分区遗漏或重复。
    gate_summary = summarize_records(gate_rows)  # 计算门架候选合力与真实迁移合矩。
    passage_summary = summarize_records(passage_rows)  # 计算横通道候选合力与真实迁移合矩。
    h03_summary = summarize_records(h03_rows)  # 计算 H03 局部完整配对合力与真实迁移合矩。
    for candidate_name, summary in (("gate-only", gate_summary), ("cross_passage_half-only", passage_summary), ("H03完整配对", h03_summary)):  # 逐个候选执行严格零合力硬门。
        if summary["zero_force_status"] != "PASS":  # 任一候选超出 1e-6 N 都不得发布准备包。
            raise PartitionPreparationError(f"候选 {candidate_name} 合力不闭合：{summary['sum_fz_n']} N")  # 报出失败候选和值。
    full_summary = summarize_records(contributions)  # 计算全部主分区重组后的总合力与总合矩。
    reference_rows: list[dict[str, object]] = []  # 构造每节点一条的冻结向量参考记录，独立复核分项合矩。
    coordinates_by_node: dict[int, tuple[Decimal, Decimal, Decimal]] = {}  # 保存每个冻结修正节点的唯一坐标。
    for record in contributions:  # 遍历分项行建立节点坐标索引。
        node_id = int(record["node_id"])  # 读取 APDL 节点号。
        coordinate = (record["x_mm"], record["y_mm"], record["z_mm"])  # 读取当前分项行坐标。
        if node_id in coordinates_by_node and coordinates_by_node[node_id] != coordinate:  # 同节点坐标必须严格一致。
            raise PartitionPreparationError(f"节点 {node_id} 在总合矩复核中出现坐标冲突")  # 拒绝非唯一力臂。
        coordinates_by_node[node_id] = coordinate  # 保存或确认节点坐标。
    for node_id in sorted(corrections):  # 按节点号构造不依赖分项拆分的冻结参考向量。
        x_mm, y_mm, z_mm = coordinates_by_node[node_id]  # 读取冻结修正节点真实坐标。
        reference_rows.append({"node_id": node_id, "x_mm": x_mm, "y_mm": y_mm, "z_mm": z_mm, "correction_fz_n": corrections[node_id]})  # 保存一节点一力的参考记录。
    reference_summary = summarize_records(reference_rows)  # 独立计算冻结 include 的总合力与总合矩。
    full_force = parse_decimal(str(full_summary["sum_fz_n"]), "完整分区总力")  # 解析完整分区总力供精确比较。
    reference_force = parse_decimal(str(reference_summary["sum_fz_n"]), "冻结向量总力")  # 解析冻结参考总力供精确比较。
    full_mx = parse_decimal(str(full_summary["sum_mx_nmm"]), "完整分区 Mx")  # 解析完整分区总 Mx。
    reference_mx = parse_decimal(str(reference_summary["sum_mx_nmm"]), "冻结向量 Mx")  # 解析冻结参考总 Mx。
    full_my = parse_decimal(str(full_summary["sum_my_nmm"]), "完整分区 My")  # 解析完整分区总 My。
    reference_my = parse_decimal(str(reference_summary["sum_my_nmm"]), "冻结向量 My")  # 解析冻结参考总 My。
    if full_force != reference_force or full_mx != reference_mx or full_my != reference_my:  # 线性分项重组必须精确复现冻结参考的合力与合矩。
        raise PartitionPreparationError(f"完整分区合量未精确复现冻结向量：F={full_force-reference_force}, Mx={full_mx-reference_mx}, My={full_my-reference_my}")  # 报出非零合量差并失败关闭。
    if abs(reference_mx - EXPECTED_TOTAL_MX_NMM) > MOMENT_REFERENCE_TOLERANCE_NMM or abs(reference_my - EXPECTED_TOTAL_MY_NMM) > MOMENT_REFERENCE_TOLERANCE_NMM:  # 与父级独立复核合矩交叉比较。
        raise PartitionPreparationError(f"冻结向量合矩与独立参考不一致：Mx={reference_mx}, My={reference_my}")  # 拒绝坐标系或符号约定漂移。
    h03_component_pairs = validate_h03_component_pairs(contributions)  # 执行 H03 四类分项逐项旧、新质量闭合硬门。
    component_summaries = {component_id: summarize_records(record for record in contributions if record["component_id"] == component_id) for component_id in sorted(RELOCATED_COMPONENTS)}  # 生成五类迁移分项独立守恒与合矩摘要。
    for component_id, summary in component_summaries.items():  # 逐项确认全桥迁移质量守恒。
        if summary["zero_force_status"] != "PASS":  # 任一分项超门限会破坏候选的物理可解释性。
            raise PartitionPreparationError(f"全桥分项 {component_id} 不闭合：{summary['sum_fz_n']} N")  # 拒绝只靠分项间抵消的总量闭合。
    return {"schema_version": SCHEMA_VERSION, "status": "PASS_PREPARATION_ONLY_NO_SOLVER_RUN", "purpose": "为 gate-only、cross_passage_half-only 与 H03 完整配对静力 A/B 修复试验准备可审计修正分区；本工件自身不是可执行 APDL", "solver_launched": False, "frozen_sources_modified": False, "units": {"length": "mm", "force": "N", "moment": "N*mm", "coordinate_system": "MAPDL X longitudinal, Y transverse, Z vertical"}, "hard_gates": {"force_zero_tolerance_n": decimal_scientific(FORCE_ZERO_TOLERANCE_N), "node_source_match_tolerance_n": decimal_scientific(NODE_MATCH_TOLERANCE_N), "h03_coordinate_match_tolerance_mm": decimal_scientific(COORDINATE_MATCH_TOLERANCE_MM), "source_to_runtime_coordinate_tolerance_mm": decimal_scientific(SOURCE_TO_RUNTIME_COORDINATE_TOLERANCE_MM), "moment_reference_tolerance_nmm": decimal_scientific(MOMENT_REFERENCE_TOLERANCE_NMM)}, "source_binding": dict(source_binding), "source_vector": {"correction_node_count": len(corrections), "positive_node_count": sum(1 for value in corrections.values() if value > 0), "negative_node_count": sum(1 for value in corrections.values() if value < 0), "rendered_sum_fz_n": reference_summary["sum_fz_n"], "rendered_sum_mx_nmm": reference_summary["sum_mx_nmm"], "rendered_sum_my_nmm": reference_summary["sum_my_nmm"], "independent_expected_mx_nmm": decimal_scientific(EXPECTED_TOTAL_MX_NMM), "independent_expected_my_nmm": decimal_scientific(EXPECTED_TOTAL_MY_NMM)}, "exact_recomposition": {**dict(recomposition), "primary_partition_ids": ["GATE_ONLY", "CROSS_PASSAGE_HALF_ONLY"], "primary_partitions_mutually_exclusive": True, "primary_partitions_complete": True, "per_node_sum_exactly_equals_frozen_include": True, "full_sum_exactly_equals_frozen_include_force_and_moments": True, "full_recomposition": full_summary, "frozen_reference": reference_summary}, "candidate_views": {"gate_only": gate_summary, "cross_passage_half_only": passage_summary, "h03_complete_paired": h03_summary}, "h03_unique_pairing": {"status": "PASS", "passage_assembly": h03_binding["passage_assembly"], "gate_assemblies": sorted(h03_binding["gate_assemblies"]), "old_gate_mct_node": h03_binding["gate_mct_node"], "expected_old_bottom_x_mm": decimal_scientific(h03_binding["expected_bottom_x_mm"]), "old_bottom_station_evidence": h03_binding["bottom_evidence"], "old_gate_station_evidence": h03_binding["gate_evidence"], "component_pair_closure": h03_component_pairs}, "component_closure": component_summaries, "overlap_rule": "H03_COMPLETE_PAIRED 是从两个主分区中筛出的重叠局部诊断视图；不得与 GATE_ONLY、CROSS_PASSAGE_HALF_ONLY 再次相加。只有两个主分区用于完整 15071 节点重组。", "authorization_boundary": {"ansys_execution_allowed_by_this_artifact": False, "executable_candidate_include_generated": False, "production_claim_allowed": False, "next_step_requires_separate_review_and_new_run": True}}  # 返回完整机器审计对象并明确用途边界。


def ledger_output_row(record: Mapping[str, object], row_id: int) -> dict[str, object]:  # 定义内部记录到固定 CSV schema 的转换函数。
    """格式化一条逐分项记录，保留全部十进制有效数字和候选成员标记。"""  # 说明 JSON 不参与该行格式。

    force = record["correction_fz_n"]  # 读取最终已与冻结 include 闭合的竖向修正。
    return {"row_id": row_id, "apdl_node_id": record["node_id"], "x_mm": decimal_scientific(record["x_mm"]), "y_mm": decimal_scientific(record["y_mm"]), "z_mm": decimal_scientific(record["z_mm"]), "source_side": record["source_side"], "component_id": record["component_id"], "source_subsystem": record["source_subsystem"], "source_catwalk": record["source_catwalk"], "source_mct_node": record["source_mct_node"], "destination_system": record["destination_system"], "destination_assembly": record["destination_assembly"], "destination_role": record["destination_role"], "source_identity": record["source_identity"], "raw_correction_fz_n": decimal_scientific(record["raw_fz_n"]), "render_adjustment_n": decimal_scientific(record["render_adjustment_n"]), "correction_fz_n": decimal_scientific(force), "moment_x_nmm": decimal_scientific(record["y_mm"] * force), "moment_y_nmm": decimal_scientific(-record["x_mm"] * force), "primary_partition_id": record["primary_partition_id"], "in_candidate_gate_only": int(bool(record["in_candidate_gate_only"])), "in_candidate_cross_passage_half_only": int(bool(record["in_candidate_cross_passage_half_only"])), "in_candidate_h03_complete_paired": int(bool(record["in_candidate_h03_complete_paired"])), "pairing_status": record["pairing_status"], "pairing_evidence": record["pairing_evidence"]}  # 返回与 LEDGER_FIELDNAMES 完全对应的输出字典。


def build_field_dictionary() -> str:  # 定义 CSV、JSON 与使用边界的中文字段说明生成函数。
    """生成配套 Markdown，逐项解释不支持注释的 CSV/JSON 字段。"""  # 说明该文件满足审计可读性要求。

    lines = ["# 修正分区准备工件字段说明", "", "本目录只包含离线准备与审计结果，未启动 ANSYS，也没有生成可执行候选 include。CSV/JSON 语法不支持注释，因此全部字段在此集中说明。", "", "## CSV：correction_partition_ledger.csv", ""]  # 初始化标题、用途边界与 CSV 小节。
    for field_name, meaning in zip(LEDGER_FIELDNAMES, ["稳定行号。", "MAPDL 节点号。", "MAPDL X 坐标，单位 mm。", "MAPDL Y 坐标，单位 mm。", "MAPDL Z 坐标，单位 mm。", "旧位置移除或新位置增加。", "物理质量分项。", "旧端 bottom/gate 子系统。", "旧端猫道幅号。", "旧端 MCT 节点。", "新端 gate/passage 系统。", "新端门架名或横通道名。", "新端节点物理角色。", "可回溯旧站位或新装配的稳定来源键。", "由权威单重或冻结质量直接得到的 FZ，单位 N。", "只用于复现冻结 include 文本末位的显式舍入闭合量，单位 N。", "最终用于分区重组的 FZ，单位 N。", "关于全局原点的 Mx=yFz，单位 N·mm。", "关于全局原点的 My=-xFz，单位 N·mm。", "互斥完备主分区，只能是 GATE_ONLY 或 CROSS_PASSAGE_HALF_ONLY。", "是否属于 gate-only 候选。", "是否属于 cross_passage_half-only 候选。", "是否属于 H03 完整配对局部候选。", "分项来源或 H03 唯一配对状态。", "MCT 节点、站位坐标或新装配名称等配对证据。"]):  # 同步遍历固定字段与逐项中文释义。
        lines.append(f"- `{field_name}`：{meaning}")  # 为当前字段追加一条 Markdown 说明。
    lines.extend(["", "## audit.json 关键字段", "", "- `status`：只能在全部源身份、唯一配对、零合力、逐节点重组和合矩门禁通过后为 `PASS_PREPARATION_ONLY_NO_SOLVER_RUN`。", "- `exact_recomposition`：证明两个互斥主分区逐节点精确重组冻结 15,071 节点向量。", "- `candidate_views`：分别给出 gate-only、cross_passage_half-only、H03 完整配对的合力与真实迁移合矩。", "- `h03_unique_pairing`：记录显式门架 MCT 节点 1048，以及由 `station_y_mm + gate_to_load_y_offset_mm` 精确得到的两幅旧底索站。", "- `runtime_coordinate_binding`：说明合矩最终采用实际冻结求解 deck 的 `N` 命令坐标，并记录其与来源 CSV 的最大末位差。", "- `overlap_rule`：H03 是重叠局部视图，不能与两个主分区重复相加。", "- `authorization_boundary`：明确该准备包不授权启动 ANSYS、发布生产结果或直接用于设计验算。", "", "## 主分区与候选视图关系", "", "`GATE_ONLY + CROSS_PASSAGE_HALF_ONLY` 是唯一用于全向量重组的互斥完备分解。`H03_COMPLETE_PAIRED` 从这两个主分区中筛出 H03 横通道及两幅配套三角门架，是局部 A/B 诊断视图。", "", "## 舍入闭合说明", "", "`render_adjustment_n` 只吸收质量台账与 APDL include 各自文本渲染造成的末位差；每节点原始分项和与 include 的差必须不超过 1e-6 N。闭合量分配给该节点绝对贡献最大且排序稳定的一行，并单独留痕，不改变任何节点总修正。", ""])  # 追加 JSON、运行时坐标权威、分区关系、重叠规则与舍入闭合说明。
    return "\n".join(lines)  # 返回 UTF-8 Markdown 完整文本。


def write_csv(path: Path, records: Sequence[dict[str, object]]) -> None:  # 定义逐分项 CSV 原子前置写出函数。
    """按稳定排序写出 BOM UTF-8 CSV。"""  # 说明排序键不依赖哈希遍历顺序。

    ordered = sorted(records, key=lambda record: (int(record["node_id"]), str(record["source_side"]), str(record["component_id"]), str(record["source_identity"])))  # 按节点、端别、分项和来源键稳定排序。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:  # 使用 BOM 方便表格软件识别中文字段。
        writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDNAMES)  # 绑定固定列序并拒绝额外字段泄漏。
        writer.writeheader()  # 写出机器可读表头。
        for row_id, record in enumerate(ordered, start=1):  # 从 1 开始生成稳定人类行号。
            writer.writerow(ledger_output_row(record, row_id))  # 格式化并写出当前物理分项记录。


def snapshot_inputs(snapshot_dir: Path, source_paths: Mapping[str, Path], tool_path: Path) -> dict[str, object]:  # 定义冻结输入快照复制函数。
    """把本次已校验源和工具自身复制到新目录，不触碰原文件。"""  # 说明返回每个快照的相对路径与摘要。

    snapshot_dir.mkdir(parents=True, exist_ok=False)  # 新建专用快照目录，拒绝覆盖既有证据。
    result: dict[str, object] = {}  # 保存原路径、快照路径与一致摘要。
    for label, source_path in source_paths.items():  # 逐个复制已通过 SHA 硬门的输入文件。
        destination = snapshot_dir / f"{label}__{source_path.name}"  # 以语义标签前缀避免同名输入冲突。
        shutil.copy2(source_path, destination)  # 保留文件内容与时间元数据，原源文件保持只读未改。
        source_sha = sha256_file(source_path)  # 复核源文件摘要，防止准备期间被外部改变。
        snapshot_sha = sha256_file(destination)  # 计算复制后快照摘要。
        if source_sha != snapshot_sha:  # 快照字节必须与源完全一致。
            raise PartitionPreparationError(f"输入快照复制后摘要不一致：{label}")  # 拒绝不可靠快照。
        result[label] = {"source_path": str(source_path), "snapshot_path": str(destination.relative_to(snapshot_dir.parent)).replace("\\", "/"), "sha256": snapshot_sha, "size_bytes": destination.stat().st_size}  # 记录可追溯源与快照身份。
    tool_destination = snapshot_dir / tool_path.name  # 为本准备工具建立同名源码快照路径。
    shutil.copy2(tool_path, tool_destination)  # 复制实际执行工具源码以支持未来复算。
    result["preparation_tool"] = {"source_path": str(tool_path), "snapshot_path": str(tool_destination.relative_to(snapshot_dir.parent)).replace("\\", "/"), "sha256": sha256_file(tool_destination), "size_bytes": tool_destination.stat().st_size}  # 记录工具快照身份。
    return result  # 返回全部输入与工具快照绑定。


def write_hash_ledger(output_dir: Path, relative_paths: Sequence[Path]) -> Path:  # 定义输出工件 SHA256 清单写出函数。
    """按相对路径排序写出 sha256sum 兼容清单。"""  # 说明清单本身不自包含，避免递归摘要。

    ledger_path = output_dir / "artifact_hashes.sha256"  # 固定准备包哈希清单文件名。
    lines = [f"{sha256_file(output_dir / relative_path)}  {str(relative_path).replace(chr(92), '/')}" for relative_path in sorted(relative_paths, key=lambda value: str(value))]  # 为每个既有工件生成摘要与正斜杠相对路径。
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")  # 使用普通 UTF-8 和 LF 写出可复核清单。
    return ledger_path  # 返回清单路径供终端摘要与父流程引用。


def run_self_test() -> None:  # 定义不依赖项目文件的确定性微型自测。
    """验证混合节点舍入闭合、主分区完备性和逐节点精确重组。"""  # 说明自测不写文件、不调用求解器。

    corrections = {1: Decimal("-12.0000000000001"), 2: Decimal("10"), 3: Decimal("2.0000000000001")}  # 构造总力严格闭合且节点 1 含末位渲染差的三节点向量。
    template = {"z_mm": Decimal("0"), "source_subsystem": "", "source_catwalk": "", "source_mct_node": "", "destination_system": "", "destination_assembly": "", "destination_role": "", "render_adjustment_n": Decimal("0"), "pairing_status": "SELF_TEST", "pairing_evidence": "synthetic"}  # 定义微型记录公共字段。
    records = [  # 构造门架与横通道在同一旧节点叠加、随后分别迁移到新节点的四条记录。
        {**template, "node_id": 1, "x_mm": Decimal("0"), "y_mm": Decimal("1"), "source_side": "OLD_SOURCE_REMOVAL", "component_id": "gate_bottom_beam", "source_identity": "A", "raw_fz_n": Decimal("-10"), "correction_fz_n": Decimal("-10")},  # 旧节点门架分项。
        {**template, "node_id": 1, "x_mm": Decimal("0"), "y_mm": Decimal("1"), "source_side": "OLD_SOURCE_REMOVAL", "component_id": PASSAGE_COMPONENT, "source_identity": "B", "raw_fz_n": Decimal("-2"), "correction_fz_n": Decimal("-2")},  # 旧节点横通道分项。
        {**template, "node_id": 2, "x_mm": Decimal("1"), "y_mm": Decimal("2"), "source_side": "NEW_DESTINATION_ADDITION", "component_id": "gate_bottom_beam", "source_identity": "C", "raw_fz_n": Decimal("10"), "correction_fz_n": Decimal("10")},  # 新节点门架分项。
        {**template, "node_id": 3, "x_mm": Decimal("2"), "y_mm": Decimal("3"), "source_side": "NEW_DESTINATION_ADDITION", "component_id": PASSAGE_COMPONENT, "source_identity": "D", "raw_fz_n": Decimal("2.0000000000001"), "correction_fz_n": Decimal("2.0000000000001")},  # 新节点横通道分项。
    ]  # 完成微型贡献记录构造。
    fake_binding = {"gate_assemblies": set(), "old_bottom_keys": set(), "old_gate_keys": set(), "passage_assembly": "H03"}  # 构造不选择 H03 的最小成员绑定。
    assign_partition_membership(records, fake_binding)  # 为微型记录赋予互斥 gate/passage 主分区。
    result = reconcile_to_frozen_vector(records, corrections)  # 执行节点 1 的确定性末位差闭合。
    if not result["exact_node_recomposition"]:  # 自测必须得到逐节点精确重组真值。
        raise PartitionPreparationError("自测逐节点重组未通过")  # 以专用异常报告内部逻辑失败。
    gate_summary = summarize_records(record for record in records if record["in_candidate_gate_only"])  # 汇总微型门架分区。
    passage_summary = summarize_records(record for record in records if record["in_candidate_cross_passage_half_only"])  # 汇总微型横通道分区。
    if gate_summary["zero_force_status"] != "PASS" or passage_summary["zero_force_status"] != "PASS":  # 两个微型主分区都必须在严格门限内零合力。
        raise PartitionPreparationError("自测主分区零合力未通过")  # 报出内部守恒逻辑失败。
    print("SELF_TEST_PASS; exact_node_recomposition=true; no_solver_run=true")  # 输出固定成功摘要供父流程留证。


def prepare(args: argparse.Namespace) -> Path:  # 定义真实项目分区准备主函数。
    """校验冻结输入、重建分项、发布新准备包并返回输出目录。"""  # 说明所有硬门在写出正式审计前完成。

    output_dir = args.output_directory.resolve()  # 解析新准备包绝对路径，避免工作目录歧义。
    if output_dir.exists():  # 既有目录可能含历史证据，禁止覆盖或混写。
        raise PartitionPreparationError(f"输出目录已存在，拒绝覆盖：{output_dir}")  # 要求调用者使用新的唯一目录。
    source_paths = {"component_allocation_ledger": args.component_allocation_ledger.resolve(), "correction_include": args.correction_include.resolve(), "authoritative_mapping": args.authoritative_mapping.resolve(), "original_nodes": args.original_nodes.resolve(), "resolved_stations": args.resolved_stations.resolve(), "mass_audit": args.mass_audit.resolve(), "base_mesh": args.base_mesh.resolve(), "finite_geometry": args.finite_geometry.resolve()}  # 汇总六项物理来源与两份冻结运行时几何文件的绝对路径。
    source_binding = {"component_allocation_ledger": {"path": str(source_paths["component_allocation_ledger"]), "sha256": require_sha256(source_paths["component_allocation_ledger"], EXPECTED_ALLOCATION_SHA256, "冻结质量分项台账")}, "correction_include": {"path": str(source_paths["correction_include"]), "sha256": require_sha256(source_paths["correction_include"], EXPECTED_CORRECTION_SHA256, "冻结迁移 include")}, "authoritative_mapping": {"path": str(source_paths["authoritative_mapping"]), "sha256": require_sha256(source_paths["authoritative_mapping"], EXPECTED_MAPPING_SHA256, "权威 MCT 映射")}, "original_nodes": {"path": str(source_paths["original_nodes"]), "sha256": require_sha256(source_paths["original_nodes"], EXPECTED_NODES_SHA256, "旧绳索节点坐标")}, "resolved_stations": {"path": str(source_paths["resolved_stations"]), "sha256": require_sha256(source_paths["resolved_stations"], EXPECTED_STATIONS_SHA256, "专用站位解析表")}, "mass_audit": {"path": str(source_paths["mass_audit"]), "sha256": require_sha256(source_paths["mass_audit"], EXPECTED_MASS_AUDIT_SHA256, "质量空间化审计")}, "base_mesh": {"path": str(source_paths["base_mesh"]), "sha256": require_sha256(source_paths["base_mesh"], EXPECTED_BASE_MESH_SHA256, "冻结基础网格")}, "finite_geometry": {"path": str(source_paths["finite_geometry"]), "sha256": require_sha256(source_paths["finite_geometry"], EXPECTED_FINITE_GEOMETRY_SHA256, "冻结有限门架横通道几何")}}  # 对八项冻结源逐一执行固定 SHA256 硬门并建立初始绑定。
    mass_audit = load_json(source_paths["mass_audit"])  # 读取质量空间化机器审计用于交叉绑定输入摘要。
    audit_input_binding = mass_audit.get("input_binding")  # 获取质量审计记录的上游源身份对象。
    if not isinstance(audit_input_binding, dict):  # 缺失输入绑定表示质量审计 schema 不完整。
        raise PartitionPreparationError("质量空间化审计缺少 input_binding")  # 拒绝无法追溯的质量台账。
    for audit_key, expected_sha in (("authoritative_conload_mapping", EXPECTED_MAPPING_SHA256), ("original_rope_nodes", EXPECTED_NODES_SHA256), ("resolved_dedicated_stations", EXPECTED_STATIONS_SHA256)):  # 逐项交叉检查质量审计中的关键上游摘要。
        entry = audit_input_binding.get(audit_key)  # 读取当前上游绑定记录。
        if not isinstance(entry, dict) or entry.get("sha256") != expected_sha:  # 审计记录必须与本工具固定摘要一致。
            raise PartitionPreparationError(f"质量审计中的 {audit_key} 绑定不一致")  # 拒绝跨版本拼接质量与荷载源。
    corrections = parse_correction_include(source_paths["correction_include"])  # 解析并验证冻结 15,071 节点修正向量。
    coordinates = load_original_coordinates(source_paths["original_nodes"])  # 读取并转换全部旧绳索节点坐标。
    mapping_rows = read_csv_rows(source_paths["authoritative_mapping"])  # 读取权威旧荷载逐索映射。
    old_contributions, station_rows = build_old_contributions(mapping_rows, coordinates)  # 唯一拆出旧端五类负修正及站位索引。
    allocation_rows = read_csv_rows(source_paths["component_allocation_ledger"])  # 读取冻结空间化质量逐分项台账。
    new_contributions = load_new_contributions(allocation_rows)  # 构造新端五类正修正贡献。
    contributions = old_contributions + new_contributions  # 合并旧端移除与新端增加，形成完整物理迁移记录。
    resolved_rows = read_csv_rows(source_paths["resolved_stations"])  # 读取 H01～H21 显式站位解析结果。
    h03_binding = derive_h03_binding(resolved_rows, mapping_rows, station_rows, coordinates)  # 建立 H03 旧、新装配唯一配对关系。
    assign_partition_membership(contributions, h03_binding)  # 赋予两个主分区和三个候选视图成员标记。
    runtime_coordinates = load_runtime_coordinates([source_paths["base_mesh"], source_paths["finite_geometry"]], set(corrections))  # 从实际冻结求解 deck 读取全部修正节点坐标。
    runtime_coordinate_audit = apply_runtime_coordinates(contributions, runtime_coordinates)  # 核对来源表坐标差并统一采用运行时真实坐标计算合矩。
    recomposition = reconcile_to_frozen_vector(contributions, corrections)  # 逐节点精确重组冻结 include 并记录末位闭合量。
    audit = validate_and_build_audit(contributions, corrections, source_binding, h03_binding, recomposition)  # 执行零合力、合矩、H03 分项和主分区完备硬门。
    audit["runtime_coordinate_binding"] = runtime_coordinate_audit  # 在机器审计中记录 deck 坐标权威与源表末位差统计。
    output_dir.mkdir(parents=True, exist_ok=False)  # 所有计算硬门通过后才创建全新准备包目录。
    snapshot_binding = snapshot_inputs(output_dir / "input_snapshot", source_paths, Path(__file__).resolve())  # 复制已验证源和实际工具源码到只读证据快照。
    source_binding_with_snapshot = dict(source_binding)  # 复制初始源绑定，避免修改调用前对象。
    for label, snapshot_entry in snapshot_binding.items():  # 把快照相对路径和摘要补充到源绑定。
        if label in source_binding_with_snapshot:  # 六项输入同时具有原路径和快照路径。
            source_binding_with_snapshot[label] = {**source_binding_with_snapshot[label], "snapshot_path": snapshot_entry["snapshot_path"], "size_bytes": snapshot_entry["size_bytes"]}  # 合并快照身份信息。
    source_binding_with_snapshot["preparation_tool"] = snapshot_binding["preparation_tool"]  # 单独记录实际执行工具源码快照。
    audit["source_binding"] = source_binding_with_snapshot  # 用包含快照的最终绑定替换初始源绑定。
    ledger_path = output_dir / "correction_partition_ledger.csv"  # 固定逐分项修正台账输出路径。
    dictionary_path = output_dir / "字段说明.md"  # 固定中文字段说明输出路径。
    audit_path = output_dir / "audit.json"  # 固定机器审计输出路径。
    write_csv(ledger_path, contributions)  # 写出完整逐分项修正长表。
    dictionary_path.write_text(build_field_dictionary(), encoding="utf-8-sig", newline="\n")  # 写出 CSV/JSON 配套字段与使用边界说明。
    audit["output_binding"] = {"correction_partition_ledger.csv": {"sha256": sha256_file(ledger_path), "size_bytes": ledger_path.stat().st_size}, "字段说明.md": {"sha256": sha256_file(dictionary_path), "size_bytes": dictionary_path.stat().st_size}}  # 在审计中绑定先写出的两个工件身份。
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig", newline="\n")  # 写出最终机器审计，JSON 保持有效且不插入非法注释。
    hash_targets = [path.relative_to(output_dir) for path in output_dir.rglob("*") if path.is_file()]  # 收集审计、台账、说明与全部输入快照相对路径。
    hash_ledger = write_hash_ledger(output_dir, hash_targets)  # 写出不自包含的完整 SHA256 工件清单。
    print(f"PARTITION_PREPARATION_PASS; output={output_dir}; ledger_sha256={sha256_file(ledger_path)}; audit_sha256={sha256_file(audit_path)}; hash_ledger_sha256={sha256_file(hash_ledger)}; no_solver_run=true")  # 输出固定成功摘要供父流程记录。
    return output_dir  # 返回准备包目录供调用方进一步检查。


def parse_arguments() -> argparse.Namespace:  # 定义命令行参数解析函数。
    """解析自测开关、八项冻结输入与唯一输出目录。"""  # 说明默认值锁定当前 C10 迁移诊断源链。

    script_path = Path(__file__).resolve()  # 获取当前工具绝对路径。
    model_root = script_path.parent.parent  # 从 ultra_tools 上一级定位 V2.0 模型根目录。
    project_root = model_root.parents[1]  # 从 V2.0 根目录向上两级定位 D:/张靖皋大桥。
    geometry_root = project_root / "02_CAD几何模型" / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"  # 定位权威几何与 MCT 映射目录。
    frozen_run = model_root / "ultra_runs" / "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T234415577134Z"  # 定位已冻结的原荷载迁移诊断 run。
    parser = argparse.ArgumentParser(description=__doc__)  # 创建带模块说明的命令行解析器。
    parser.add_argument("--self-test", action="store_true", help="只运行内置微型自测，不读项目文件、不写输出。")  # 提供无副作用的逻辑自测入口。
    parser.add_argument("--output-directory", type=Path, help="新准备包目录；正式准备时必填且必须不存在。")  # 要求调用者显式命名新证据目录。
    parser.add_argument("--component-allocation-ledger", type=Path, default=model_root / "mass21_spatialized_v2_component_allocations.csv", help="冻结质量逐分项台账。")  # 默认绑定当前空间化质量分项台账。
    parser.add_argument("--correction-include", type=Path, default=frozen_run / "solver" / "apply_constant_total_load_position_migration_v1.inp", help="冻结 15071 节点荷载迁移 include。")  # 默认绑定失败诊断实际采用的迁移向量。
    parser.add_argument("--authoritative-mapping", type=Path, default=geometry_root / "authoritative_mct_deadload_v1_conload_mapping.csv", help="权威 MCT 到 APDL 逐索荷载映射。")  # 默认绑定旧负节点分项唯一分解来源。
    parser.add_argument("--original-nodes", type=Path, default=geometry_root / "nodes.csv", help="旧绳索节点 CAD 坐标表。")  # 默认绑定旧端真实坐标来源。
    parser.add_argument("--resolved-stations", type=Path, default=model_root / "builder" / "generated" / "resolved_dedicated_stations.csv", help="H01～H21 解析站位表。")  # 默认绑定 H03 新旧站位关系来源。
    parser.add_argument("--mass-audit", type=Path, default=model_root / "mass21_spatialization_audit_v2.json", help="空间化质量机器审计。")  # 默认绑定质量源输入摘要与守恒基线。
    parser.add_argument("--base-mesh", type=Path, default=frozen_run / "solver" / "full_line_beam4_crossbeam_mesh_xlong.inp", help="冻结求解 deck 的基础网格节点坐标。")  # 默认绑定实际进入失败诊断的旧节点坐标文本。
    parser.add_argument("--finite-geometry", type=Path, default=frozen_run / "solver" / "apply_finite_gates_and_passages_v2.inp", help="冻结求解 deck 的有限门架与横通道节点坐标。")  # 默认绑定实际进入失败诊断的新生成节点坐标文本。
    return parser.parse_args()  # 返回完整命名空间供主入口使用。


def main() -> int:  # 定义进程主入口并返回明确状态码。
    """运行自测或正式准备；所有错误都以失败关闭信息和非零状态返回。"""  # 说明不会捕获后继续生成半成品。

    args = parse_arguments()  # 解析用户显式参数与冻结默认源路径。
    try:  # 把专用失败关闭异常转换为稳定终端状态。
        if args.self_test:  # 自测模式不得读取真实项目输入或写出准备包。
            run_self_test()  # 运行混合节点舍入闭合和主分区微型测试。
            return 0  # 自测通过时返回成功状态。
        if args.output_directory is None:  # 正式准备必须显式指定新输出目录。
            raise PartitionPreparationError("正式准备必须提供 --output-directory")  # 拒绝默认写入或覆盖任意目录。
        prepare(args)  # 执行全部源身份、分项重建、唯一配对和输出发布步骤。
        return 0  # 全部硬门通过且工件写出成功时返回成功状态。
    except PartitionPreparationError as exc:  # 捕获可预期的工程失败关闭路径。
        print(f"PARTITION_PREPARATION_BLOCKED: {exc}", file=sys.stderr)  # 向标准错误输出单行可检索阻断原因。
        return 2  # 使用固定非零状态 2 表示源、配对或守恒硬门失败。


if __name__ == "__main__":  # 仅在直接执行工具时进入命令行主流程。
    raise SystemExit(main())  # 把主入口返回值传给操作系统，不在导入时产生副作用。
