"""封板 A20 RHS50×30 的逐件方向源证，并且在零物理差异时禁止重复启动 MAPDL。"""  # 模块职责是只读核查 CAD、B00、U00 与 U01，再生成可追溯审计包。

from __future__ import annotations  # 启用延迟类型注解，避免运行时解析复合类型带来兼容性差异。

import argparse  # 解析可选的确定性运行目录名，除此之外不接受改变物理口径的参数。
import csv  # 读取 U00 逐件轴台账并写出 A20 正式 RHS 方向台账。
import hashlib  # 计算全部源文件与生成产物的 SHA-256 身份。
import json  # 读取 U01 状态并写出机器可读门禁、状态和清单。
import math  # 计算向量模长并拒绝 NaN、无穷或退化方向。
import re  # 严格解析 B00 APDL 的 N、TYPE、MAT、SECNUM 与 EN 命令。
from datetime import datetime, timezone  # 生成采用 UTC 的唯一运行时间戳。
from pathlib import Path  # 以显式绝对路径管理输入和输出，避免当前目录影响结果。
from typing import Any  # 描述 JSON/CSV 行中允许的异构标量值。


SCRIPT_PATH = Path(__file__).resolve()  # 固定本脚本绝对路径，供清单与自哈希使用。
PROJECT_DIR = SCRIPT_PATH.parents[1]  # 指向“附件2-3全模态精确对齐_V2.0”项目根目录。
WORKSPACE_DIR = SCRIPT_PATH.parents[3]  # 指向“D:\张靖皋大桥”工作区根目录。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 所有 Ultra 正式运行包只能写入该目录。
B00_RUN_NAME = "B00_LEGACY_COMPLETE_20260715T111105670409Z"  # 冻结的旧物理完整基线身份。
U00_RUN_NAME = "U00_SOURCE_GATE_20260715T024455Z"  # 已通过的可执行源链门禁身份。
U01_RUN_NAME = "U01_UNIT_TESTS_20260715T101428628522Z"  # 已通过的单元与接口小算例身份。
B00_INCLUDE_PATH = ULTRA_RUNS_DIR / B00_RUN_NAME / "input_snapshot" / "apply_finite_gates_and_passages_v2.inp"  # B00 冻结门架/横通道 APDL 输入。
U00_AXIS_LEDGER_PATH = ULTRA_RUNS_DIR / U00_RUN_NAME / "regenerated_source_chain" / "builder_generated" / "anisotropic_section_axis_audit.csv"  # U00 重建源链逐件轴证据。
U01_STATUS_PATH = ULTRA_RUNS_DIR / U01_RUN_NAME / "U01_status.json"  # U01 八项门禁机器状态。
CAD_SOURCE_PATH = WORKSPACE_DIR / "02_CAD几何模型" / "猫道全线STEP模型" / "build_full_catwalk_from_drawings.py"  # 图纸驱动 FreeCAD 实体生成逻辑。
RUN_PREFIX = "A20_RHS5030_AXIS"  # 运行目录前缀与试算矩阵的 A20 标识保持一致。
TARGET_TYPE_ID = 70  # B00 中横通道有限梁统一采用 BEAM188 的 TYPE 70。
TARGET_MATERIAL_ID = 66  # RHS50×30×4 的冻结材料编号为 66。
TARGET_SECTION_ID = 66  # RHS50×30×4 的冻结 ASEC 截面编号为 66。
TARGET_ELEMENT_COUNT = 2898  # 21 品横通道各 138 根，共应覆盖 2,898 根 RHS 梁。
EXPECTED_WIDTH_MM = 50.0  # 图纸 MD5-03/05 给出的截面水平/纵向宽度为 50 mm。
EXPECTED_HEIGHT_MM = 30.0  # 图纸 MD5-03/05 给出的截面竖向高度为 30 mm。
EXPECTED_IYY_MM4 = 75232.0  # 50×30×4 截面绕 local-y 的冻结弱轴惯性矩，单位 mm^4。
EXPECTED_IZZ_MM4 = 176672.0  # 50×30×4 截面绕 local-z 的冻结强轴惯性矩，单位 mm^4。
ORIENTATION_ALIGNMENT_MIN = 1.0 - 1.0e-10  # local-z 与全局竖向的最小绝对点积，允许双精度舍入误差。
VECTOR_TOLERANCE = 1.0e-10  # 单位向量、正交性与参考台账比对的无量纲容差。
REFERENCE_FLOAT_TOLERANCE = 1.0e-9  # B00 与 U00 文本小数比对容差，覆盖 15 位输出舍入。
RUN_NAME_PATTERN = re.compile(r"A20_RHS5030_AXIS_\d{8}T\d{12}Z\Z", re.ASCII)  # 只允许 UTC 微秒格式的安全运行目录名。
NUMBER_TOKEN = r"[-+0-9.Ee]+"  # APDL 科学计数法数字字段的严格字符集合。
NODE_PATTERN = re.compile(rf"N,(\d+),({NUMBER_TOKEN}),({NUMBER_TOKEN}),({NUMBER_TOKEN})\s*(?:!.*)?", re.IGNORECASE)  # 解析节点号与 XYZ，允许行尾注释。
TYPE_PATTERN = re.compile(r"TYPE,(\d+)\s*(?:!.*)?", re.IGNORECASE)  # 解析后续 EN 使用的元素类型状态。
MATERIAL_PATTERN = re.compile(r"MAT,(\d+)\s*(?:!.*)?", re.IGNORECASE)  # 解析后续 EN 使用的材料状态。
SECTION_PATTERN = re.compile(r"SECNUM,(\d+)\s*(?:!.*)?", re.IGNORECASE)  # 解析后续 EN 使用的截面状态。
ELEMENT_PATTERN = re.compile(r"EN,(\d+),(\d+),(\d+),(\d+)\s*(?:!.*)?", re.IGNORECASE)  # 解析 BEAM188 的元素号和 I/J/K 节点。


def require(condition: bool, message: str) -> None:  # 输入布尔门禁和失败说明；通过时无输出，失败时立即抛错。
    """所有证据门禁均采用 fail-closed；任何不确定性都不得生成 A20 完成状态。"""  # 函数说明明确异常路径和安全语义。
    if not condition:  # 只有门禁为假时进入拒绝路径。
        raise RuntimeError(message)  # 抛出带上下文的异常并阻止生成误导性正式包。


def sha256_file(path: Path) -> str:  # 输入现有文件路径并返回小写十六进制 SHA-256。
    """采用 1 MiB 分块读取，既避免大文件占满内存，也保持字节级身份不变。"""  # 函数说明给出输入、输出和内存约束。
    digest = hashlib.sha256()  # 创建新的 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读方式打开文件，禁止换行或编码转换。
        while True:  # 循环读取直到明确遇到 EOF。
            block = stream.read(1024 * 1024)  # 每次读取 1 MiB，数值来源是通用流式哈希块大小。
            if not block:  # 空字节串表示已经到达文件末尾。
                break  # 结束读取循环并保留已累计的摘要。
            digest.update(block)  # 将当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回稳定的 64 字符小写十六进制摘要。


def vector_subtract(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入两个三维向量并返回 left-right。
    """逐分量相减；坐标输入时输出单位仍为 mm。"""  # 函数说明给出数学关系和单位保持规则。
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])  # 返回三个分量的差。


def vector_dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:  # 输入两个三维向量并返回点积。
    """单位向量输入时输出为无量纲方向余弦。"""  # 函数说明给出输出物理意义。
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]  # 累加三个对应分量乘积。


def vector_cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入两个三维向量并返回右手叉积。
    """按标准行列式计算 left×right，用于恢复 BEAM188 的 local-y。"""  # 函数说明给出用途和手性约束。
    return (left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0])  # 返回右手叉积三分量。


def vector_norm(vector: tuple[float, float, float]) -> float:  # 输入三维向量并返回非负欧氏模长。
    """坐标差输入时输出单位为 mm，单位向量输入时输出无量纲。"""  # 函数说明给出单位传播规则。
    return math.sqrt(vector_dot(vector, vector))  # 对自点积开平方得到模长。


def vector_normalize(vector: tuple[float, float, float], label: str) -> tuple[float, float, float]:  # 输入非退化向量和审计标签并返回单位向量。
    """模长不大于 1E-12 或含非有限数时拒绝，禁止静默采用默认轴。"""  # 函数说明给出退化阈值和异常路径。
    require(all(math.isfinite(value) for value in vector), f"方向向量含非有限数：{label}")  # 在任何算术前拒绝 NaN 与无穷。
    length = vector_norm(vector)  # 计算待归一化向量的模长。
    require(length > 1.0e-12, f"方向向量退化：{label}")  # 1E-12 是任务书对 1E-8 投影门禁更严格的数值底线。
    return (vector[0] / length, vector[1] / length, vector[2] / length)  # 逐分量除以模长得到单位向量。


def parse_b00_rhs(path: Path) -> tuple[list[dict[str, Any]], dict[int, tuple[float, float, float]]]:  # 输入 B00 include 并返回 2,898 个目标 EN 与全部节点坐标。
    """只选择 TYPE/MAT/SECNUM=70/66/66 的 EN；不修改任何 B00 字节。"""  # 函数说明给出选择条件、输出和只读约束。
    source_text = path.read_text(encoding="utf-8")  # 以 UTF-8 读取含中文注释的冻结 APDL 文本。
    nodes: dict[int, tuple[float, float, float]] = {}  # 保存节点号到 XYZ(mm) 的唯一映射。
    target_elements: list[dict[str, Any]] = []  # 按 B00 原顺序保存 RHS 目标元素身份。
    all_physical_nodes: set[int] = set()  # 保存所有 EN 的 I/J 节点，验证 K 节点不承担物理拓扑。
    current_type: int | None = None  # 跟踪当前 TYPE 状态，初始未定义。
    current_material: int | None = None  # 跟踪当前 MAT 状态，初始未定义。
    current_section: int | None = None  # 跟踪当前 SECNUM 状态，初始未定义。
    for line_number, raw_line in enumerate(source_text.splitlines(), start=1):  # 逐行扫描并保留一基 APDL 行号供追溯。
        text = raw_line.strip()  # 只移除行首尾空白，不改变冻结文件本身。
        node_match = NODE_PATTERN.fullmatch(text)  # 尝试把当前行解析为 N 命令。
        if node_match is not None:  # 节点命令进入坐标注册路径。
            node_id = int(node_match.group(1))  # 读取节点编号。
            require(node_id not in nodes, f"B00 节点重复定义：{node_id}")  # 每个节点只允许一个 N 定义。
            coordinate = (float(node_match.group(2)), float(node_match.group(3)), float(node_match.group(4)))  # 读取 XYZ 坐标，单位 mm。
            require(all(math.isfinite(value) for value in coordinate), f"B00 节点坐标非有限：{node_id}")  # 拒绝不可计算坐标。
            nodes[node_id] = coordinate  # 注册当前节点供 I/J/K 方向计算。
            continue  # 节点行不再参与属性状态或元素解析。
        type_match = TYPE_PATTERN.fullmatch(text)  # 尝试解析 TYPE 状态。
        if type_match is not None:  # TYPE 命令只更新后续元素状态。
            current_type = int(type_match.group(1))  # 保存元素类型编号。
            continue  # 当前行处理完成。
        material_match = MATERIAL_PATTERN.fullmatch(text)  # 尝试解析 MAT 状态。
        if material_match is not None:  # MAT 命令只更新后续元素状态。
            current_material = int(material_match.group(1))  # 保存材料编号。
            continue  # 当前行处理完成。
        section_match = SECTION_PATTERN.fullmatch(text)  # 尝试解析 SECNUM 状态。
        if section_match is not None:  # SECNUM 命令只更新后续元素状态。
            current_section = int(section_match.group(1))  # 保存截面编号。
            continue  # 当前行处理完成。
        element_match = ELEMENT_PATTERN.fullmatch(text)  # 尝试解析四节点字段的 EN 命令。
        if element_match is None:  # 非 EN 行不参与本函数后续逻辑。
            continue  # 跳到下一条 APDL 行。
        element_id = int(element_match.group(1))  # 读取元素编号。
        i_node = int(element_match.group(2))  # 读取物理 I 端节点。
        j_node = int(element_match.group(3))  # 读取物理 J 端节点。
        k_node = int(element_match.group(4))  # 读取仅用于定向的 K 节点。
        all_physical_nodes.update((i_node, j_node))  # 所有 EN 的 I/J 均属于物理拓扑集合。
        if current_material == TARGET_MATERIAL_ID and current_section == TARGET_SECTION_ID:  # 只选择 RHS50×30 的 MAT/SECNUM 66/66。
            require(current_type == TARGET_TYPE_ID, f"RHS 元素不是 TYPE {TARGET_TYPE_ID}：{element_id}")  # 拒绝混入其他元素类型。
            target_elements.append({"element_id": element_id, "i_node": i_node, "j_node": j_node, "k_node": k_node, "element_line_number": line_number})  # 保存目标身份和源行号。
    require(len(target_elements) == TARGET_ELEMENT_COUNT, f"B00 RHS 元素数不是 {TARGET_ELEMENT_COUNT}：{len(target_elements)}")  # 硬闭合任务书数量。
    target_k_nodes = [int(row["k_node"]) for row in target_elements]  # 按元素顺序提取 K 节点号。
    require(len(set(target_k_nodes)) == TARGET_ELEMENT_COUNT, "B00 RHS K 节点不是逐根独占")  # 每根梁必须有唯一方向节点。
    require(not (set(target_k_nodes) & all_physical_nodes), "B00 RHS K 节点同时被用作 I/J 物理节点")  # 防止定向证据与真实网格混淆。
    for row in target_elements:  # 逐根确认三节点坐标均可用。
        require(int(row["i_node"]) in nodes and int(row["j_node"]) in nodes and int(row["k_node"]) in nodes, f"RHS 节点定义不完整：{row['element_id']}")  # 缺任一节点即拒绝。
    return target_elements, nodes  # 返回只读解析结果供逐件轴计算。


def read_reference_rows(path: Path) -> dict[int, dict[str, str]]:  # 输入 U00 轴台账并返回以元素号索引的 RHS 行。
    """仅接收 section_key=passage_rhs50x30 且 status=PASS 的 2,898 行。"""  # 函数说明给出过滤条件和数量门禁。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 兼容有无 BOM 的 UTF-8 CSV 并保持字段边界。
        rows = [row for row in csv.DictReader(stream) if row.get("section_key") == "passage_rhs50x30"]  # 只保留 RHS50×30 记录。
    require(len(rows) == TARGET_ELEMENT_COUNT, f"U00 RHS 参考台账不是 {TARGET_ELEMENT_COUNT} 行：{len(rows)}")  # 硬闭合参考覆盖率。
    require(all(row.get("status") == "PASS" for row in rows), "U00 RHS 参考台账含非 PASS 行")  # 参考源自身必须全部通过。
    indexed = {int(row["apdl_elem_id"]): row for row in rows}  # 以 APDL 元素号建立稳定索引。
    require(len(indexed) == TARGET_ELEMENT_COUNT, "U00 RHS 参考台账存在重复元素号")  # 拒绝重复覆盖导致的假完整。
    return indexed  # 返回元素号到原始 CSV 行的映射。


def validate_cad_contract(path: Path) -> dict[str, Any]:  # 输入图纸驱动 CAD 生成器并返回源证定位摘要。
    """验证 50×30 常量及 make_oriented_box 的纵向宽度、竖向高度参数顺序。"""  # 函数说明给出语义门禁和输出。
    source_text = path.read_text(encoding="utf-8")  # 以 UTF-8 只读加载 CAD 生成逻辑。
    lines = source_text.splitlines()  # 分行为一基定位生成证据，不改源文件。
    constant_line = next((index for index, line in enumerate(lines, start=1) if "CROSS_PASSAGE_RAIL_BOX = (50.0, 30.0)" in line), None)  # 定位 50×30 图纸常量。
    require(constant_line is not None, "CAD 生成器缺少 CROSS_PASSAGE_RAIL_BOX=(50,30) 源证")  # 缺失尺寸常量时 A20 必须源阻断。
    block_pattern = re.compile(r"make_oriented_box\(\s*f\"\{name\}_\{side_label\}_\{rail_label\}_handrail_box50x30_MD5_03_05\",\s*point\(0\.0, width_offset, rail_z\),\s*transverse,\s*longitudinal,\s*vertical,\s*CROSS_PASSAGE_TOTAL_LENGTH,\s*CROSS_PASSAGE_RAIL_BOX\[0\],\s*CROSS_PASSAGE_RAIL_BOX\[1\],\s*\)", re.DOTALL)  # 要求长度轴=transverse、50 mm=longitudinal、30 mm=vertical 的完整调用顺序。
    block_match = block_pattern.search(source_text)  # 在整个源文件中查找明确的有向盒体生成调用。
    require(block_match is not None, "CAD 生成器缺少 RHS50×30 的纵向/竖向面向源证")  # 禁止仅凭梁轴猜测滚转角。
    block_start_line = source_text.count("\n", 0, block_match.start()) + 1  # 把匹配起点转换为一基源行号。
    block_end_line = source_text.count("\n", 0, block_match.end()) + 1  # 把匹配终点转换为一基源行号。
    return {"path": str(path), "sha256": sha256_file(path), "dimension_constant_line": constant_line, "orientation_block_start_line": block_start_line, "orientation_block_end_line": block_end_line, "length_axis": "transverse", "width_50mm_axis": "longitudinal", "height_30mm_axis": "vertical"}  # 返回可机器复核的源证摘要。


def build_formal_ledger(elements: list[dict[str, Any]], nodes: dict[int, tuple[float, float, float]], references: dict[int, dict[str, str]], cad_contract: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:  # 输入 B00、U00 和 CAD 证据并返回正式逐件台账与汇总。
    """逐根恢复 BEAM188 local-x/y/z，要求 B00 与图纸方向及 U00 重建源链完全一致。"""  # 函数说明给出输入、输出和三方闭合条件。
    global_z = (0.0, 0.0, 1.0)  # MAPDL 全局竖向固定为 +Z。
    output_rows: list[dict[str, Any]] = []  # 保存即将写入正式 CSV 的 2,898 行。
    max_reference_axis_difference = 0.0  # 累计 B00 与 U00 对应局部轴分量的最大绝对差。
    min_vertical_alignment = 1.0  # 累计全部 RHS 的 local-z 竖向绝对点积最小值。
    max_orthogonality_error = 0.0  # 累计三轴两两正交误差最大值。
    max_handedness_error = 0.0  # 累计右手系三重积相对 +1 的最大误差。
    for element in elements:  # 按 B00 原始 EN 顺序逐根计算并核对。
        element_id = int(element["element_id"])  # 读取当前 APDL 元素号。
        i_node = int(element["i_node"])  # 读取当前 I 节点号。
        j_node = int(element["j_node"])  # 读取当前 J 节点号。
        k_node = int(element["k_node"])  # 读取当前方向 K 节点号。
        i_coord = nodes[i_node]  # 取得 I 节点 XYZ(mm)。
        j_coord = nodes[j_node]  # 取得 J 节点 XYZ(mm)。
        k_coord = nodes[k_node]  # 取得 K 节点 XYZ(mm)。
        local_x = vector_normalize(vector_subtract(j_coord, i_coord), f"element={element_id}:local_x")  # BEAM188 local-x=normalize(J-I)。
        i_to_k = vector_subtract(k_coord, i_coord)  # 计算 I→K 原始方向向量，单位 mm。
        projected = vector_dot(i_to_k, local_x)  # 计算 I→K 沿梁轴的投影标量，单位 mm。
        local_z_raw = (i_to_k[0] - projected * local_x[0], i_to_k[1] - projected * local_x[1], i_to_k[2] - projected * local_x[2])  # 去掉轴向分量得到 local-z 投影。
        local_z = vector_normalize(local_z_raw, f"element={element_id}:local_z")  # I-J-K 平面按 BEAM188 定义给出 local-z。
        local_y = vector_normalize(vector_cross(local_z, local_x), f"element={element_id}:local_y")  # local-y=local-z×local-x 保持右手系。
        orthogonality_error = max(abs(vector_dot(local_x, local_y)), abs(vector_dot(local_x, local_z)), abs(vector_dot(local_y, local_z)))  # 汇总两两点积残差。
        handedness = vector_dot(vector_cross(local_x, local_y), local_z)  # 计算 local-x×local-y 与 local-z 的一致性。
        vertical_alignment = abs(vector_dot(local_z, global_z))  # 符号不影响截面惯性轴，绝对点积必须接近 1。
        require(orthogonality_error <= VECTOR_TOLERANCE, f"B00 RHS 局部轴不正交：{element_id}")  # 拒绝定向节点退化或数值错误。
        require(abs(handedness - 1.0) <= VECTOR_TOLERANCE, f"B00 RHS 局部轴不是右手系：{element_id}")  # 拒绝错误手性。
        require(vertical_alignment >= ORIENTATION_ALIGNMENT_MIN, f"B00 RHS 的 30 mm 高度轴未竖直：{element_id}")  # 落实 CAD 的 30 mm=vertical 源证。
        reference = references.get(element_id)  # 读取同元素的 U00 重建源链轴证据。
        require(reference is not None, f"U00 RHS 参考台账缺元素：{element_id}")  # 每个 B00 元素必须一对一匹配参考行。
        u00_i_node = int(reference["n1"])  # 读取 U00 重建版本的 I 节点号；生成器版本变化可能使节点编号整体平移。
        u00_j_node = int(reference["n2"])  # 读取 U00 重建版本的 J 节点号，用于显式记录而不冒充 B00 节点身份。
        u00_k_node = int(reference["orientation_node"])  # 读取 U00 重建版本的方向节点号，用于版本差异审计。
        require(u00_i_node > 0 and u00_j_node > 0 and u00_k_node > 0, f"U00 RHS I-J-K 节点号非法：{element_id}")  # 节点号必须是正整数但无需跨生成器版本相等。
        reference_axis = (float(reference["local_z_global_x"]), float(reference["local_z_global_y"]), float(reference["local_z_global_z"]))  # 读取 U00 local-z 三分量。
        axis_difference = max(abs(local_z[index] - reference_axis[index]) for index in range(3))  # 计算 B00 与 U00 逐分量最大差。
        require(axis_difference <= REFERENCE_FLOAT_TOLERANCE, f"B00/U00 RHS local-z 不一致：{element_id}, diff={axis_difference}")  # 拒绝重建源链与冻结基线分叉。
        require(abs(float(reference["thickness_y_mm"]) - EXPECTED_WIDTH_MM) <= VECTOR_TOLERANCE, f"U00 RHS 50 mm 宽度不符：{element_id}")  # 核对 local-y 截面宽度。
        require(abs(float(reference["thickness_z_mm"]) - EXPECTED_HEIGHT_MM) <= VECTOR_TOLERANCE, f"U00 RHS 30 mm 高度不符：{element_id}")  # 核对 local-z 截面高度。
        require(abs(float(reference["iyy_mm4"]) - EXPECTED_IYY_MM4) <= VECTOR_TOLERANCE, f"U00 RHS Iyy 不符：{element_id}")  # 核对冻结弱轴惯性矩。
        require(abs(float(reference["izz_mm4"]) - EXPECTED_IZZ_MM4) <= VECTOR_TOLERANCE, f"U00 RHS Izz 不符：{element_id}")  # 核对冻结强轴惯性矩。
        require(EXPECTED_IZZ_MM4 > EXPECTED_IYY_MM4, "RHS50×30 冻结惯性矩强弱轴关系错误")  # 50 mm 宽、30 mm 高时 Izz 必须大于 Iyy。
        max_reference_axis_difference = max(max_reference_axis_difference, axis_difference)  # 更新三方闭合最大差。
        min_vertical_alignment = min(min_vertical_alignment, vertical_alignment)  # 更新最差竖向对齐度。
        max_orthogonality_error = max(max_orthogonality_error, orthogonality_error)  # 更新全体正交误差。
        max_handedness_error = max(max_handedness_error, abs(handedness - 1.0))  # 更新全体右手误差。
        output_rows.append({"apdl_elem_id": element_id, "b00_n1": i_node, "b00_n2": j_node, "b00_orientation_node": k_node, "u00_n1": u00_i_node, "u00_n2": u00_j_node, "u00_orientation_node": u00_k_node, "cross_version_node_ids_equal": str((i_node, j_node, k_node) == (u00_i_node, u00_j_node, u00_k_node)).upper(), "element_line_number": int(element["element_line_number"]), "assembly_name": reference["assembly_name"], "member": reference["member"], "cad_source_key": "MD5_03_05_RHS50X30", "cad_length_axis": cad_contract["length_axis"], "cad_width_50mm_axis": cad_contract["width_50mm_axis"], "cad_height_30mm_axis": cad_contract["height_30mm_axis"], "local_x_global_x": f"{local_x[0]:.15f}", "local_x_global_y": f"{local_x[1]:.15f}", "local_x_global_z": f"{local_x[2]:.15f}", "local_y_global_x": f"{local_y[0]:.15f}", "local_y_global_y": f"{local_y[1]:.15f}", "local_y_global_z": f"{local_y[2]:.15f}", "local_z_global_x": f"{local_z[0]:.15f}", "local_z_global_y": f"{local_z[1]:.15f}", "local_z_global_z": f"{local_z[2]:.15f}", "abs_local_z_dot_global_z": f"{vertical_alignment:.15f}", "width_local_y_mm": f"{EXPECTED_WIDTH_MM:.1f}", "height_local_z_mm": f"{EXPECTED_HEIGHT_MM:.1f}", "iyy_mm4": f"{EXPECTED_IYY_MM4:.1f}", "izz_mm4": f"{EXPECTED_IZZ_MM4:.1f}", "b00_matches_u00_source_axis": "TRUE", "physical_axis_change_required": "FALSE", "status": "PASS_ALREADY_CORRECT"})  # 写出版本化节点身份、逐件源证、实际轴、截面映射与零差异结论。
    require(len(output_rows) == TARGET_ELEMENT_COUNT, "A20 正式台账输出行数不闭合")  # 防止循环内意外跳行。
    summary = {"schema_version": 1, "status": "PASSED_ALREADY_CORRECT_NO_SOLVE", "target_element_count": TARGET_ELEMENT_COUNT, "passed_element_count": len(output_rows), "source_backed_orientation": {"width_50mm_axis": "longitudinal/local-y", "height_30mm_axis": "vertical/local-z"}, "physical_change_required_count": 0, "changed_n_command_count": 0, "minimum_abs_local_z_dot_global_z": min_vertical_alignment, "maximum_b00_u00_local_z_component_difference": max_reference_axis_difference, "maximum_orthogonality_error": max_orthogonality_error, "maximum_handedness_error": max_handedness_error, "decision": "B00 的 2,898 根 RHS50×30 已满足图纸/生成逻辑方向；A20 不得人为制造错误轴，也无需重复全桥求解。"}  # 汇总逐件门禁结果与工程决策。
    return output_rows, summary  # 返回正式 CSV 行和机器摘要。


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:  # 输入目标路径和非空同构行并写 UTF-8 CSV。
    """CSV 语法不支持注释，字段用途由同目录 field_dictionary.md 逐项说明。"""  # 函数说明遵守无效格式不可插入注释的约束。
    require(bool(rows), f"拒绝写空 CSV：{path.name}")  # 空台账不能满足源证门禁。
    path.parent.mkdir(parents=True, exist_ok=True)  # 仅创建本次新运行包内的必要父目录。
    with path.open("w", encoding="utf-8-sig", newline="") as stream:  # 使用 Excel 兼容 UTF-8 BOM 和标准 CSV 换行。
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), lineterminator="\n")  # 固定首行字段顺序和 LF 行尾。
        writer.writeheader()  # 写出唯一表头。
        writer.writerows(rows)  # 按 B00 元素原顺序写出 2,898 行。


def write_json(path: Path, payload: Any) -> None:  # 输入目标路径和 JSON 可序列化对象并写格式化 UTF-8 文本。
    """JSON 不允许注释，字段与字面值含义由配套 Markdown 说明。"""  # 函数说明遵守 JSON 有效性约束。
    path.parent.mkdir(parents=True, exist_ok=True)  # 仅创建本次新运行包内的必要父目录。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 使用两空格缩进和末尾换行生成稳定文本。


def validate_run_name(value: str) -> str:  # 输入命令行运行名并返回已验证原值。
    """只接受 A20_RHS5030_AXIS_YYYYMMDDTHHMMSSffffffZ，拒绝路径字符。"""  # 函数说明给出格式约束和安全目的。
    if RUN_NAME_PATTERN.fullmatch(value) is None:  # 不符合唯一格式时进入 argparse 错误路径。
        raise argparse.ArgumentTypeError("run name must match A20_RHS5030_AXIS_YYYYMMDDTHHMMSSffffffZ")  # 返回清晰的合法格式。
    return value  # 合法名称原样返回供目录创建。


def main() -> int:  # 不接收物理变更参数；成功生成正式 A20 源证包时返回 0。
    """执行只读门禁、写新审计目录，并明确记录未启动 MAPDL。"""  # 函数说明给出总体输入、输出和副作用边界。
    parser = argparse.ArgumentParser(description="Seal the source-backed A20 RHS50x30 orientation ledger; never starts MAPDL.")  # 创建仅含运行名的命令行接口。
    parser.add_argument("--run-name", type=validate_run_name, default=None, help="Optional exact A20_RHS5030_AXIS_<UTC-microseconds>Z directory name.")  # 允许测试时指定确定性目录名。
    arguments = parser.parse_args()  # 解析命令行并拒绝未知参数。
    for required_path in (B00_INCLUDE_PATH, U00_AXIS_LEDGER_PATH, U01_STATUS_PATH, CAD_SOURCE_PATH):  # 枚举本次门禁全部权威输入。
        require(required_path.is_file(), f"A20 必需源文件不存在：{required_path}")  # 任一源缺失时禁止生成完成包。
    u01_status = json.loads(U01_STATUS_PATH.read_text(encoding="utf-8"))  # 读取 U01 八项小算例状态。
    require(u01_status.get("status") == "PASSED", f"U01 未通过：{u01_status.get('status')}")  # A20 必须继承已通过的轴/截面单元门禁。
    require(int(u01_status.get("passed_count", -1)) == int(u01_status.get("required_count", -2)) == 8, "U01 不是 8/8 通过")  # 明确要求全部八项通过。
    cad_contract = validate_cad_contract(CAD_SOURCE_PATH)  # 封板 50/30 方向的图纸驱动生成逻辑。
    elements, nodes = parse_b00_rhs(B00_INCLUDE_PATH)  # 只读解析 B00 的 2,898 根 RHS I/J/K。
    references = read_reference_rows(U00_AXIS_LEDGER_PATH)  # 读取 U00 重建源链对应逐件证据。
    ledger_rows, gate_summary = build_formal_ledger(elements, nodes, references, cad_contract)  # 执行 CAD-B00-U00 三方逐件闭合。
    created_at = datetime.now(timezone.utc)  # 记录当前 UTC 时间供唯一目录和清单使用。
    run_name = arguments.run_name or f"{RUN_PREFIX}_{created_at.strftime('%Y%m%dT%H%M%S%f')}Z"  # 默认生成含微秒的唯一运行名。
    run_dir = ULTRA_RUNS_DIR / run_name  # 构造仅位于 ultra_runs 下的新输出目录。
    require(not run_dir.exists(), f"A20 运行目录已存在：{run_dir}")  # 禁止覆盖任何既有审计或求解结果。
    qa_dir = run_dir / "qa"  # 所有机器门禁和字段说明写入 qa 子目录。
    qa_dir.mkdir(parents=True, exist_ok=False)  # 原子创建全新目录树，存在即失败。
    formal_ledger_path = run_dir / "rhs50_direction_ledger.csv"  # 任务书点名要求的正式方向台账路径。
    write_csv(formal_ledger_path, ledger_rows)  # 写出 2,898 行逐件源证和实际方向。
    source_hashes = {"script": {"path": str(SCRIPT_PATH), "sha256": sha256_file(SCRIPT_PATH)}, "cad_generator": {"path": str(CAD_SOURCE_PATH), "sha256": sha256_file(CAD_SOURCE_PATH)}, "b00_frozen_include": {"path": str(B00_INCLUDE_PATH), "sha256": sha256_file(B00_INCLUDE_PATH)}, "u00_axis_ledger": {"path": str(U00_AXIS_LEDGER_PATH), "sha256": sha256_file(U00_AXIS_LEDGER_PATH)}, "u01_status": {"path": str(U01_STATUS_PATH), "sha256": sha256_file(U01_STATUS_PATH)}}  # 记录全部输入字节身份。
    zero_difference_audit = {"schema_version": 1, "status": "PASSED", "parent_run": B00_RUN_NAME, "candidate_run": run_name, "physical_change_family_count": 0, "physical_change_required_count": 0, "changed_n_command_count": 0, "b00_input_sha256": source_hashes["b00_frozen_include"]["sha256"], "a20_candidate_input_sha256": source_hashes["b00_frozen_include"]["sha256"], "byte_identical_to_b00": True, "solver_run_required": False, "solver_run_performed": False, "reason": "2,898 根 RHS50×30 在 B00 中已与 CAD 源证及 U00 重建源链逐件一致；轴单变量不存在。"}  # 证明 A20 是零物理差异而非漏改。
    status_payload = {"schema_version": 1, "run_id": "A20_RHS5030_AXIS_ONLY", "run_name": run_name, "status": "COMPLETED_NO_SOLVE_ALREADY_CORRECT", "created_at_utc": created_at.isoformat(), "parent_run": B00_RUN_NAME, "precondition_rhs_orientation_source_ledger_complete": True, "target_element_count": TARGET_ELEMENT_COUNT, "passed_element_count": TARGET_ELEMENT_COUNT, "physical_change_required_count": 0, "mapdl_started": False, "next_step": "A30_ALL_AXES_EQUIVALENCE_TO_A10", "decision": gate_summary["decision"]}  # 写出不夸大为求解完成的 A20 正式状态。
    manifest_payload = {"schema_version": 1, "run_id": "A20_RHS5030_AXIS_ONLY", "run_name": run_name, "model_line": "DIAGNOSTIC_ZERO_DIFFERENCE_SOURCE_GATE", "parent_run": B00_RUN_NAME, "created_at_utc": created_at.isoformat(), "status": status_payload["status"], "source_contract": cad_contract, "source_hashes": source_hashes, "gate_summary": gate_summary, "physical_change_contract": zero_difference_audit, "outputs": ["rhs50_direction_ledger.csv", "A20_status.json", "manifest.json", "result_packet.md", "qa/a20_source_gate.json", "qa/model_zero_difference_audit.json", "qa/field_dictionary.md", "source_hashes.sha256", "artifact_hashes.sha256"]}  # 汇总来源、门禁、零差异合同和产物清单。
    write_json(qa_dir / "a20_source_gate.json", gate_summary)  # 写机器可读逐件门禁汇总。
    write_json(qa_dir / "model_zero_difference_audit.json", zero_difference_audit)  # 写 B00 与 A20 候选输入的零差异证明。
    write_json(run_dir / "A20_status.json", status_payload)  # 写本轮正式状态。
    write_json(run_dir / "manifest.json", manifest_payload)  # 写完整运行清单。
    field_dictionary = """# A20 RHS50×30 方向台账字段说明

`rhs50_direction_ledger.csv` 是任务书要求的 2,898 根逐件正式源证台账。CSV/JSON 语法本身不支持注释，因此在此集中说明字段和固定值。

- `apdl_elem_id`：B00 冻结输入中的 BEAM188 元素号；必须唯一且共 2,898 个。
- `b00_n1`、`b00_n2`、`b00_orientation_node`：B00 冻结输入的 BEAM188 I、J、K 节点；K 只定义截面方向，不是物理连接节点。
- `u00_n1`、`u00_n2`、`u00_orientation_node`：U00 重建源链版本的对应 I、J、K 节点；生成器版本变化允许编号不同。
- `cross_version_node_ids_equal`：仅记录 B00/U00 节点号是否相同；`FALSE` 不代表几何或方向不一致，方向按元素号和单位轴另行硬核对。
- `element_line_number`：该 EN 命令在 B00 include 中的一基行号。
- `assembly_name`、`member`：U00 可执行源链重建时的构件身份。
- `cad_source_key=MD5_03_05_RHS50X30`：方向依据为 MD5-03/05 图纸驱动 CAD 生成逻辑。
- `cad_length_axis=transverse`：盒体长度沿横通道横向轴。
- `cad_width_50mm_axis=longitudinal`：50 mm 截面宽度沿桥纵向，对应 BEAM188 local-y。
- `cad_height_30mm_axis=vertical`：30 mm 截面高度沿全局竖向，对应 BEAM188 local-z。
- `local_*_global_*`：由 B00 I/J/K 恢复的右手单位轴方向余弦；无量纲。
- `abs_local_z_dot_global_z`：30 mm 高度轴与全局竖向的绝对点积；本门禁要求不小于 0.9999999999。
- `width_local_y_mm=50.0`、`height_local_z_mm=30.0`：截面外包络尺寸及其局部轴映射，单位 mm。
- `iyy_mm4=75232.0`、`izz_mm4=176672.0`：冻结 ASEC 主惯性矩，单位 mm⁴；Izz>Iyy 与 50 mm 宽、30 mm 高一致。
- `b00_matches_u00_source_axis=TRUE`：同一元素号的 B00 与 U00 重建源链 local-z 逐分量一致；不要求不同生成器版本的节点编号相同。
- `physical_axis_change_required=FALSE`：该元素在 A20 不需要修改 K 节点。
- `status=PASS_ALREADY_CORRECT`：图纸方向、生成逻辑、B00 实际轴和 U00 重建源链四者闭合。

`COMPLETED_NO_SOLVE_ALREADY_CORRECT` 只表示 A20 的轴源证门禁已完成且不存在轴单变量，不表示新做了一次 MAPDL 求解。因为候选输入与 B00 字节相同，重复求解不会产生新的物理证据。
"""  # 为不支持注释的 CSV/JSON 逐项解释字段、单位、阈值与状态语义。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8")  # 写人类可读字段说明。
    result_packet = f"""# A20 RHS50×30 方向源证结果

- 状态：`COMPLETED_NO_SOLVE_ALREADY_CORRECT`
- 权威方向：50 mm 沿桥纵向，30 mm 沿竖向。
- B00 逐件核查：{TARGET_ELEMENT_COUNT}/{TARGET_ELEMENT_COUNT} 通过。
- U00 重建源链逐件一致：{TARGET_ELEMENT_COUNT}/{TARGET_ELEMENT_COUNT}。
- 需要修改的 K 节点：0。
- MAPDL 启动：否。
- 工程判定：B00 的 RHS50×30 已物理正确；A20 不得人为制造错误轴。A30 的合并轴基线因此与已完成的 A10 物理输入等价，下一步应封板该等价关系后进入 S10。
"""  # 简洁说明 A20 完成的是源证/零差异门禁而非新求解。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8")  # 写人类可读结果包。
    source_hash_lines = [f"{entry['sha256']}  {entry['path']}" for entry in source_hashes.values()]  # 把输入身份转换为 sha256sum 风格行。
    (run_dir / "source_hashes.sha256").write_text("\n".join(source_hash_lines) + "\n", encoding="utf-8")  # 写源文件哈希清单。
    artifact_candidates = sorted(path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256")  # 枚举除自引用清单外的全部生成文件。
    artifact_hash_lines = [f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in artifact_candidates]  # 计算相对路径产物哈希。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_hash_lines) + "\n", encoding="utf-8")  # 写非自引用产物清单。
    print(json.dumps({"run_dir": str(run_dir), "status": status_payload["status"], "passed": TARGET_ELEMENT_COUNT, "changed": 0, "mapdl_started": False}, ensure_ascii=False))  # 向调用者输出唯一机器摘要。
    return 0  # 以成功退出码表示全部源证门禁和写入均完成。


if __name__ == "__main__":  # 只有直接执行脚本时才运行正式入口，导入时保持无副作用。
    raise SystemExit(main())  # 把 main 返回值传递为进程退出码。
