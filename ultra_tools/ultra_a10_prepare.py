"""从指定 B00 冻结 run 派生 A10 H175 局部轴试算输入，并且永不启动 MAPDL。"""  # 模块职责仅包含只读校验、独立复制、受控改写和静态审计，禁止求解与删除。

from __future__ import annotations  # 启用延迟类型注解，使容器注解不引入运行期求值副作用。

import argparse  # 仅用于提供可选的确定性 run 目录名参数和无副作用帮助页。
import csv  # 仅用于把 2698 根 H175 的逐根轴审计写成合法 CSV。
import difflib  # 仅用于记录 frozen B00 旧控制流到当前单作业控制流的非物理文本差异。
import hashlib  # 仅用于计算源、复制件、规范化文本和产物账本的 SHA-256。
import io  # 仅用于在内存中构造 CSV，避免半写入文件成为审计证据。
import json  # 仅用于读取 frozen B00 机器证据并写出 A10 JSON 证据。
import math  # 仅用于三维向量模长、归一化和正交性计算。
import re  # 仅用于严格解析 APDL 节点、单元、属性状态和安全目录名。
import secrets  # 仅用于生成两位十六进制 jobname 后缀，避免同秒名称碰撞。
import shutil  # 仅用于不可覆盖复制和只读磁盘容量快照；本脚本不调用删除接口。
from datetime import datetime, timezone  # 仅用于生成带微秒的 UTC run 身份和审计时间。
from pathlib import Path  # 统一处理 Windows 路径、run 内相对路径和不可覆盖目标。
from typing import Any  # 为 JSON 动态字段和审计行提供明确但不过度收窄的类型标注。

import ultra_b00_prepare as b00  # 只复用当前已修复 B00 的纯文本主输入生成器和只读资源快照函数。


SCRIPT_PATH = Path(__file__).resolve()  # 当前 A10 编排器绝对路径用于源码哈希和 run 内快照。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是 A10 编排器与当前 B00 模板的共同目录。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录承载 ultra_runs 和全部冻结证据。
ULTRA_RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # A10 新 run 只能创建在既有 ultra_runs 父目录内。
B00_RUN_NAME = "B00_LEGACY_COMPLETE_20260715T111105670409Z"  # 唯一授权父 run，禁止自动选择最新 B00。
B00_RUN = ULTRA_RUNS_ROOT / B00_RUN_NAME  # 指定 frozen B00 的绝对派生根路径。
B00_MAIN_NAME = "b00_legacy_complete_main.inp"  # frozen B00 旧主输入仅用于控制流差异证据，不作为 A10 模板。
AXIS_INCLUDE_NAME = "apply_finite_gates_and_passages_v2.inp"  # 唯一允许发生物理字节变化的十一项依赖文件。
A10_MAIN_NAME = "a10_h175_axis_main.inp"  # A10 单作业从头静力—扰动模态主输入的固定文件名。
RUN_ID = "A10_H175_AXIS"  # 本入口唯一允许生成的试算标识，表示只修 H175 局部轴。
MODEL_LINE = "LEGACY_A10_H175_AXIS_ONLY"  # manifest 模型线强调 CERIG/CP 等 legacy 运动学完全不变。
STATUS_WAITING = "PREPARED_WAITING_RESOURCES"  # 当前资源不足时的固定状态，明确不是 READY 或 RUNNING。
STATUS_OVERRIDE = "PREPARED_NOT_STARTED_USER_OVERRIDE"  # 用户显式忽略内存门槛时的准备状态，仍明确尚未启动。
NEXT_ACTION = "WAIT_FOR_MEMORY_AND_DISK_THEN_SEPARATE_EXPLICIT_LAUNCH"  # 准备完成后的外部人工动作，本脚本没有启动路径。
OVERRIDE_NEXT_ACTION = "USER_OVERRIDE_RECORDED_SEPARATE_EXPLICIT_LAUNCH_REQUIRED"  # 记录用户覆盖后仍需外部显式启动的下一动作。
DEPENDENCY_COUNT = 11  # frozen B00 的装配依赖必须恰好为 order 1 至 11。
TARGET_ELEMENT_COUNT = 2698  # 诊断方案封板的 MAT/SECNUM 61 H175 门架下横梁数量。
TARGET_MATERIAL_ID = 61  # H175 门架下横梁唯一材料编号，E 和密度必须保持原值。
TARGET_SECTION_ID = 61  # H175 门架下横梁唯一截面编号，Iyy/Izz 必须保持原值。
TARGET_TYPE_ID = 70  # frozen builder 中有限刚度新增 BEAM188 的元素类型编号。
ORIENTATION_LENGTH_MM = 100.0  # 新方向节点到 I 节点的固定距离，单位 mm。
REQUESTED_MODES = 80  # A10 单作业从最低频率起严格提取 80 阶且不设置频带上限。
EXPECTED_CERIG_COUNT = 5078  # legacy 连接必须保留的 CERIG 命令数量。
EXPECTED_CP_COUNT = 12  # frozen 下拉接口必须保留的 CP 命令数量。
B00_AXIS_SHA256 = "51dc4dabba9d4ad1464d033fa69aba80cbaea79bcbed163fadb81e3b63211b98"  # frozen H175 include 的固定源身份。
B00_OLD_MAIN_SHA256 = "9474b445eb63746b731547191664fc50ec623890ecec744fac808e21ccbe4d56"  # frozen 旧主输入身份，仅用于 lineage。
CURRENT_B00_PREPARER_SHA256 = "6e51cffdfdc67773bd1b66e6dcb456e01565b9dfb80b5fa3e236d7884d71360f"  # 当前真实 LS2、无频带上限模板的固定源码身份。
RUN_NAME_PATTERN = re.compile(r"A10_H175_AXIS_\d{8}T\d{12}Z\Z", re.ASCII)  # 可选 run 名必须含 UTC 微秒且不允许路径字符。
JOBNAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z", re.ASCII)  # MAPDL jobname 必须为最多 32 位 ASCII 安全标识。
NODE_PATTERN = re.compile(r"N,(\d+),([^,]+),([^,]+),([^,]+)\Z", re.ASCII)  # 严格解析四字段 APDL N 命令及三维坐标。
ELEMENT_PATTERN = re.compile(r"EN,(\d+),(\d+),(\d+),(\d+)\Z", re.ASCII)  # 严格解析 BEAM188 的元素号、I、J、K 三节点。
TYPE_PATTERN = re.compile(r"TYPE,(\d+)\Z", re.ASCII)  # 解析当前 APDL TYPE 状态以确认目标均为 TYPE 70。
MATERIAL_PATTERN = re.compile(r"MAT,(\d+)\Z", re.ASCII)  # 解析当前 APDL MAT 状态以筛选材料 61。
SECTION_PATTERN = re.compile(r"SECNUM,(\d+)\Z", re.ASCII)  # 解析当前 APDL SECNUM 状态以筛选截面 61。
INTEGER_TOKEN_PATTERN = re.compile(r"\d+\Z", re.ASCII)  # 识别节点引用字段中的纯整数，避免把坐标或标签误作节点号。
AXIS_INLINE_COMMENT = " ! A10：H175方向点K=I+100*ez（100 mm）"  # 每条改写 N 命令的统一中文短注释，满足逐行注释且控制行长。
VECTOR_TOLERANCE = 1.0e-9  # 单位向量、正交性和 100 mm 重构的双精度绝对容差。
REPRESENTATIVE_TOLERANCE_MM = 1.0e-8  # 代表横梁 K-I 与 -100 global X 的绝对分量容差，单位 mm。
APDL_MAX_LINE_LENGTH = 640  # MAPDL 安全静态行长上限，单位 Unicode 字符，远大于本次短注释行。
ENERGY_BEGIN = "! A10_ENERGY_EXPORT_BEGIN"  # 能量证据注入块的机器可识别起始标记。
ENERGY_END = "! A10_ENERGY_EXPORT_END"  # 能量证据注入块的机器可识别结束标记。
ENERGY_FILE_STEM = "a10_gate_bottom_modal_sene"  # 未来每阶总 SENE、组件 SENE 和比例 CSV 的固定文件干名。


def require(condition: bool, message: str) -> None:  # 定义 fail-closed 断言，输入布尔条件与失败说明，成功时无返回值。
    """条件为假时抛出 RuntimeError；本函数不写文件、不改变源 run。"""  # 函数约束说明失败即中断且不做恢复性删除。
    if not condition:  # 仅当硬门禁未满足时进入异常路径。
        raise RuntimeError(message)  # 立即中止准备，禁止不完整证据被标为通过。


def sha256_bytes(payload: bytes) -> str:  # 输入任意字节串并返回 64 位小写 SHA-256，用于内存文本审计。
    """计算内存字节的 SHA-256；输入不被修改，输出为规范小写十六进制。"""  # 函数说明明确输入、输出和无副作用。
    return hashlib.sha256(payload).hexdigest()  # 一次性计算当前内存证据摘要并返回。


def sha256_text(text: str) -> str:  # 输入 Unicode 文本并按无 BOM UTF-8 返回 SHA-256。
    """把文本严格编码为 UTF-8 后计算摘要，供生成前和落盘后双向闭合。"""  # 函数说明固定编码约束。
    return sha256_bytes(text.encode("utf-8"))  # 使用 UTF-8 原始字节计算确定性摘要。


def sha256_file(path: Path) -> str:  # 输入现存普通文件路径并返回流式 SHA-256。
    """以 1 MiB 块读取文件；缺失或目录输入均 fail-closed。"""  # 函数说明给出输入约束、输出和内存策略。
    require(path.is_file(), f"待哈希文件不存在：{path}")  # 哈希前确认目标是普通文件。
    digest = hashlib.sha256()  # 为当前单一文件初始化独立摘要状态。
    with path.open("rb") as stream:  # 以二进制只读方式打开，禁止换行或编码转换。
        while True:  # 持续读取固定块直至 EOF。
            chunk = stream.read(1024 * 1024)  # 每次最多读取 1 MiB，兼顾吞吐和内存。
            if not chunk:  # 空字节串只表示正常文件尾。
                break  # 结束读取循环并保留累计摘要。
            digest.update(chunk)  # 把当前原始字节块加入摘要状态。
    return digest.hexdigest()  # 返回 64 位小写十六进制摘要。


def read_json(path: Path) -> dict[str, Any]:  # 输入 JSON 文件路径并返回顶层对象字典。
    """按 UTF-8-sig 读取合法 JSON 对象；数组或标量顶层均拒绝。"""  # 函数说明给出编码兼容和结构约束。
    require(path.is_file(), f"缺少 JSON 证据：{path}")  # 读取前确认文件存在。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 兼容可选 BOM 并严格解析 JSON。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 顶层必须具名字段便于审计。
    return value  # 返回已验证为字典的 JSON 对象。


def write_new_text(path: Path, text: str) -> None:  # 输入新文件路径和完整文本，仅允许首次创建。
    """以无 BOM UTF-8 和调用方给定换行写入；绝不覆盖既有文件。"""  # 函数说明固定不可覆盖和编码约束。
    require(not path.exists(), f"拒绝覆盖既有文件：{path}")  # 写入前执行显式同名门禁。
    path.parent.mkdir(parents=True, exist_ok=True)  # 只创建新 run 内必要父目录，不删除任何路径。
    with path.open("x", encoding="utf-8", newline="") as stream:  # x 模式提供操作系统级不可覆盖保证并禁用换行转换。
        stream.write(text)  # 一次写出完整内存文本，避免人为拼接中途状态。


def write_new_json(path: Path, value: dict[str, Any]) -> None:  # 输入目标路径和 JSON 对象并写出稳定机器证据。
    """以两空格缩进、中文直写和末尾换行创建 JSON；JSON 本身不加入非法注释。"""  # 函数说明遵守 JSON 语法与配套 Markdown 规则。
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"  # 生成确定性可读 JSON 并保留末尾换行。
    write_new_text(path, rendered)  # 复用不可覆盖文本写入门禁。


def copy_new_verified(source: Path, destination: Path) -> str:  # 输入源和新目标路径，返回两端一致的 SHA-256。
    """逐字节复制普通文件并复算双端摘要；任何差异立即失败。"""  # 函数说明明确输入、输出和闭合条件。
    require(source.is_file(), f"复制源不存在：{source}")  # 复制前确认源是普通文件。
    require(not destination.exists(), f"拒绝覆盖复制目标：{destination}")  # 目标必须尚未存在。
    destination.parent.mkdir(parents=True, exist_ok=True)  # 只在新 run 内创建所需父目录。
    source_hash = sha256_file(source)  # 复制前取得源字节身份。
    shutil.copy2(source, destination)  # 保留文件元数据并逐字节复制，不改源文件。
    destination_hash = sha256_file(destination)  # 复制后从磁盘复算目标身份。
    require(destination_hash == source_hash, f"复制哈希不闭合：{source} -> {destination}")  # 任一字节变化均拒绝。
    return source_hash  # 返回同时代表源和复制件的摘要。


def vector_subtract(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入两个三维点并返回 left-right。
    """逐分量相减两个三维向量；输入和输出单位由调用方保持一致。"""  # 函数说明给出输入、输出和单位约束。
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])  # 按 X、Y、Z 顺序计算差向量。


def vector_dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:  # 输入两个三维向量并返回无量纲点积。
    """计算三维欧氏点积，用于投影和正交性审计。"""  # 函数说明明确用途和标量输出。
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]  # 累加三个对应分量乘积。


def vector_cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:  # 输入两个三维向量并返回 left×right。
    """按右手规则计算三维叉积，供 ez=cross(ex,ey) 使用。"""  # 函数说明固定方向约定。
    return (left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0])  # 展开标准右手叉积公式。


def vector_norm(vector: tuple[float, float, float]) -> float:  # 输入三维向量并返回其欧氏模长。
    """返回 sqrt(v·v)；输出单位与输入分量单位一致。"""  # 函数说明给出数学定义和单位。
    return math.sqrt(vector_dot(vector, vector))  # 通过点积和平方根计算非负模长。


def vector_normalize(vector: tuple[float, float, float], label: str) -> tuple[float, float, float]:  # 输入非零向量和审计标签并返回单位向量。
    """向量模长小于 1E-12 时 fail-closed；否则逐分量除以模长。"""  # 函数说明给出退化约束和输出。
    length = vector_norm(vector)  # 计算待归一化向量模长。
    require(length > 1.0e-12, f"方向向量退化：{label}")  # 拒绝 I=J 或梁轴近似竖直造成的不可定义局部轴。
    return (vector[0] / length, vector[1] / length, vector[2] / length)  # 返回无量纲单位向量。


def vector_add_scaled(origin: tuple[float, float, float], direction: tuple[float, float, float], scale: float) -> tuple[float, float, float]:  # 输入原点、方向和尺度并返回 origin+scale*direction。
    """按三个分量执行仿射组合；scale 在本任务中固定为 100 mm。"""  # 函数说明给出输入、输出和本轮约束。
    return (origin[0] + scale * direction[0], origin[1] + scale * direction[1], origin[2] + scale * direction[2])  # 生成新的 K 节点坐标。


def command_text(line: str) -> str:  # 输入带或不带行尾的 APDL 行并返回不含 CR/LF 的命令文本。
    """只移除行尾换行，不去除其他空格或注释，保证差异定位精确。"""  # 函数说明固定最小规范化范围。
    return line.rstrip("\r\n")  # 删除 Windows 或 LF 行尾并保留其余全部字符。


def parse_and_transform_axis(source_text: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:  # 输入 frozen include 文本并返回改写文本、逐根行和汇总。
    """只改 MAT=61 且 SECNUM=61 的 EN 第三节点 N 坐标；任何共享或额外引用均拒绝。"""  # 函数说明明确允许差异、输出和 fail-closed 约束。
    require("\r\n" in source_text, "frozen H175 include 不是预期 CRLF 文本。")  # 要求源换行身份与封板文件一致。
    require("\n" not in source_text.replace("\r\n", ""), "frozen H175 include 混有裸 LF。")  # 拒绝混合换行隐藏文本差异。
    lines = source_text.splitlines(keepends=True)  # 保留每条 CRLF 以便只替换目标 N 行。
    require("".join(lines) == source_text, "include 分行后无法逐字节重组。")  # 验证分行操作无信息损失。
    nodes: dict[int, tuple[float, float, float]] = {}  # 保存全部 N 命令的节点号到 XYZ 坐标映射。
    node_line_indices: dict[int, int] = {}  # 保存每个节点唯一 N 命令的零基行索引。
    target_elements: list[dict[str, int]] = []  # 按 APDL 原顺序保存目标元素及 I/J/K 节点号。
    all_i_j_nodes: set[int] = set()  # 保存全部 EN 的 I/J 节点，防止方向节点同时承担物理拓扑。
    node_reference_counts: dict[int, int] = {}  # 只统计 N、EN、CERIG、CP、D、F 等节点语义字段，避免元素号同号误报。
    current_type: int | None = None  # 跟踪当前 TYPE 状态，初始未定义。
    current_material: int | None = None  # 跟踪当前 MAT 状态，初始未定义。
    current_section: int | None = None  # 跟踪当前 SECNUM 状态，初始未定义。
    for line_index, raw_line in enumerate(lines):  # 按 frozen 原顺序扫描全部 APDL 行并保留零基索引。
        text = command_text(raw_line)  # 仅去掉当前行 CR/LF 以供严格正则匹配。
        fields = [field.strip() for field in text.split(",")]  # 拆出当前命令字段供节点语义引用审计。
        command = fields[0].upper() if fields else ""  # 取得大写 APDL 命令名；空行使用空字符串。
        node_match = NODE_PATTERN.fullmatch(text)  # 尝试把当前行解析为严格四字段 N 命令。
        if node_match is not None:  # 节点命令进入坐标注册路径。
            node_id = int(node_match.group(1))  # 读取节点编号。
            require(node_id not in nodes, f"节点 N 命令重复：{node_id}")  # 每个节点在该 include 中只允许定义一次。
            coordinate = (float(node_match.group(2)), float(node_match.group(3)), float(node_match.group(4)))  # 读取 X、Y、Z，单位 mm。
            require(all(math.isfinite(value) for value in coordinate), f"节点坐标不是有限数：{node_id}")  # 拒绝 NaN 或无穷坐标。
            nodes[node_id] = coordinate  # 注册当前节点坐标供后续 I/J/K 查找。
            node_line_indices[node_id] = line_index  # 注册当前节点定义行索引。
            node_reference_counts[node_id] = node_reference_counts.get(node_id, 0) + 1  # N 定义本身计为该节点唯一合法身份引用。
            continue  # 节点行不再参与属性状态或元素解析。
        type_match = TYPE_PATTERN.fullmatch(text)  # 尝试解析 TYPE 状态命令。
        if type_match is not None:  # TYPE 命令只更新当前元素类型状态。
            current_type = int(type_match.group(1))  # 保存后续 EN 使用的类型编号。
            continue  # TYPE 行处理完成后进入下一行。
        material_match = MATERIAL_PATTERN.fullmatch(text)  # 尝试解析 MAT 状态命令。
        if material_match is not None:  # MAT 命令只更新当前材料状态。
            current_material = int(material_match.group(1))  # 保存后续 EN 使用的材料编号。
            continue  # MAT 行处理完成后进入下一行。
        section_match = SECTION_PATTERN.fullmatch(text)  # 尝试解析 SECNUM 状态命令。
        if section_match is not None:  # SECNUM 命令只更新当前截面状态。
            current_section = int(section_match.group(1))  # 保存后续 EN 使用的截面编号。
            continue  # SECNUM 行处理完成后进入下一行。
        element_match = ELEMENT_PATTERN.fullmatch(text)  # 尝试解析四字段 EN 命令。
        if element_match is not None:  # 所有解析成功的 EN 都进入拓扑引用审计。
            element_id = int(element_match.group(1))  # 读取元素编号。
            i_node = int(element_match.group(2))  # 读取梁 I 端节点号。
            j_node = int(element_match.group(3))  # 读取梁 J 端节点号。
            k_node = int(element_match.group(4))  # 读取梁方向节点号。
            all_i_j_nodes.update((i_node, j_node))  # 把两个物理端节点加入全 EN 物理节点集合。
            for referenced_node in (i_node, j_node, k_node):  # EN 的第二至第四字段均具有明确节点语义。
                node_reference_counts[referenced_node] = node_reference_counts.get(referenced_node, 0) + 1  # 累加当前梁对 I/J/K 节点的引用。
            if current_material == TARGET_MATERIAL_ID and current_section == TARGET_SECTION_ID:  # 仅 MAT/SECNUM 同为 61 的元素属于 A10 目标。
                require(current_type == TARGET_TYPE_ID, f"目标 H175 不是 TYPE 70：元素 {element_id}")  # 防止错误类型被同属性状态误选。
                target_elements.append({"element_id": element_id, "i_node": i_node, "j_node": j_node, "k_node": k_node, "line_number": line_index + 1})  # 保存目标身份和一基行号。
            continue  # EN 行处理完成后不再进入其他节点命令解析。
        node_field_positions: list[int] = []  # 默认当前命令没有需要统计的显式节点字段。
        if command == "CERIG":  # CERIG 的主节点和从节点位于第一、第二参数。
            node_field_positions = [1, 2]  # 只统计两个节点字段，不把自由度标签计入。
        elif command == "CP":  # CP 的前三字段依次为集合号、自由度和首节点前缀。
            node_field_positions = list(range(3, len(fields)))  # 第四字段起的全部整数均是被耦合节点号。
        elif command in {"D", "F", "NMODIF", "NDELE"}:  # 这些命令的第一参数具有明确节点语义。
            node_field_positions = [1]  # 只统计首个节点号，忽略自由度、数值和范围参数。
        elif command == "NSEL":  # NSEL 只改变组件或审计选择集，不建立拓扑、约束或载荷引用。
            node_field_positions = []  # 方向节点可合法进入 NSEL 范围，因此不把选择动作计为额外物理引用。
        for position in node_field_positions:  # 遍历当前命令已知具有节点语义的字段位置。
            if position < len(fields) and INTEGER_TOKEN_PATTERN.fullmatch(fields[position]):  # 只接收存在且为纯整数的节点字段。
                referenced_node = int(fields[position])  # 把字段转换为节点号键。
                node_reference_counts[referenced_node] = node_reference_counts.get(referenced_node, 0) + 1  # 累加额外节点语义引用。
    require(len(target_elements) == TARGET_ELEMENT_COUNT, f"H175 目标元素数不是 {TARGET_ELEMENT_COUNT}：{len(target_elements)}")  # 目标总数必须与诊断封板一致。
    target_k_nodes = [item["k_node"] for item in target_elements]  # 按元素顺序提取方向节点号列表。
    require(len(set(target_k_nodes)) == TARGET_ELEMENT_COUNT, "H175 K 节点不是 2698 个一对一独占节点。")  # 每根梁必须拥有唯一方向节点。
    require(not (set(target_k_nodes) & all_i_j_nodes), "H175 K 节点同时被任一 EN 当作 I/J 物理节点。")  # 禁止改坐标触及真实网格拓扑。
    for k_node in target_k_nodes:  # 对每个目标 K 节点执行定义和全文引用独占门禁。
        require(k_node in nodes, f"H175 K 节点缺少 N 定义：{k_node}")  # 每个方向节点必须在 include 中有唯一坐标。
        require(node_reference_counts.get(k_node) == 2, f"H175 K 节点存在额外节点语义引用：{k_node}")  # 只允许在自身 N 与所属 EN 中各出现一次。
    modified_lines = list(lines)  # 创建内存行副本，源文本和 frozen 文件均保持不变。
    audit_rows: list[dict[str, Any]] = []  # 保存逐元素轴公式、旧新坐标和正交性证据。
    global_z = (0.0, 0.0, 1.0)  # 全局竖直单位向量固定为 +Z。
    representative_vector: tuple[float, float, float] | None = None  # 稍后记录最小元素号的 K-I 代表向量。
    representative_element_id: int | None = None  # 与代表向量同步记录实际最小目标元素号。
    max_orthogonality_error = 0.0  # 累计 ex/ey/ez 两两点积绝对值最大值。
    max_handedness_error = 0.0  # 累计 cross(ex,ey) 与 ez 一致性的最大误差。
    max_reconstruction_error_mm = 0.0  # 累计落盘坐标重构与解析公式的最大误差，单位 mm。
    for target in target_elements:  # 按目标 EN 原始顺序逐根计算新的局部轴方向。
        element_id = target["element_id"]  # 读取当前目标元素编号。
        i_node = target["i_node"]  # 读取当前 I 节点编号。
        j_node = target["j_node"]  # 读取当前 J 节点编号。
        k_node = target["k_node"]  # 读取当前独占 K 节点编号。
        require(i_node in nodes and j_node in nodes, f"目标元素端节点缺少 N 定义：{element_id}")  # 公式计算前要求 I/J 坐标完整。
        i_coord = nodes[i_node]  # 取得 I 节点 XYZ，单位 mm。
        j_coord = nodes[j_node]  # 取得 J 节点 XYZ，单位 mm。
        old_k_coord = nodes[k_node]  # 取得 frozen B00 的旧 K 节点 XYZ，单位 mm。
        ex = vector_normalize(vector_subtract(j_coord, i_coord), f"element={element_id}:ex")  # 严格计算 ex=normalize(J-I)。
        vertical_projection = vector_dot(global_z, ex)  # 计算 globalZ 在 ex 上的标量投影。
        ey_raw = (global_z[0] - vertical_projection * ex[0], global_z[1] - vertical_projection * ex[1], global_z[2] - vertical_projection * ex[2])  # 计算 ey 的未归一化竖直投影残量。
        ey = vector_normalize(ey_raw, f"element={element_id}:ey")  # 严格计算 ey=normalize(globalZ-dot(globalZ,ex)*ex)。
        ez = vector_normalize(vector_cross(ex, ey), f"element={element_id}:ez")  # 严格计算右手 ez=cross(ex,ey)。
        new_k_coord = vector_add_scaled(i_coord, ez, ORIENTATION_LENGTH_MM)  # 严格计算 K=I+100*ez，单位 mm。
        new_axis = vector_subtract(new_k_coord, i_coord)  # 计算新 K-I 向量供长度和方向审计。
        old_axis = vector_subtract(old_k_coord, i_coord)  # 计算 frozen B00 旧 K-I 向量供差异说明。
        dot_ex_ey = vector_dot(ex, ey)  # 计算 ex 与 ey 的正交残差。
        dot_ex_ez = vector_dot(ex, ez)  # 计算 ex 与 ez 的正交残差。
        dot_ey_ez = vector_dot(ey, ez)  # 计算 ey 与 ez 的正交残差。
        handedness = vector_dot(vector_cross(ex, ey), ez)  # 计算右手三轴标量三重积，预期 +1。
        orthogonality_error = max(abs(dot_ex_ey), abs(dot_ex_ez), abs(dot_ey_ez))  # 汇总当前三对正交误差。
        reconstruction_error_mm = vector_norm(vector_subtract(new_axis, (ORIENTATION_LENGTH_MM * ez[0], ORIENTATION_LENGTH_MM * ez[1], ORIENTATION_LENGTH_MM * ez[2])))  # 计算公式重构误差，单位 mm。
        require(abs(vector_norm(ex) - 1.0) <= VECTOR_TOLERANCE, f"ex 非单位向量：{element_id}")  # 硬验证 ex 单位长度。
        require(abs(vector_norm(ey) - 1.0) <= VECTOR_TOLERANCE, f"ey 非单位向量：{element_id}")  # 硬验证 ey 单位长度。
        require(abs(vector_norm(ez) - 1.0) <= VECTOR_TOLERANCE, f"ez 非单位向量：{element_id}")  # 硬验证 ez 单位长度。
        require(orthogonality_error <= VECTOR_TOLERANCE, f"局部轴不正交：{element_id}")  # 硬验证三轴两两正交。
        require(abs(handedness - 1.0) <= VECTOR_TOLERANCE, f"局部轴不是右手系：{element_id}")  # 硬验证右手方向。
        require(abs(vector_norm(new_axis) - ORIENTATION_LENGTH_MM) <= VECTOR_TOLERANCE, f"K-I 长度不是 100 mm：{element_id}")  # 硬验证方向点距离。
        require(vector_dot(ey, global_z) > 0.0, f"ey 未保持朝向 +globalZ：{element_id}")  # 防止竖直投影符号翻转。
        node_line_index = node_line_indices[k_node]  # 取得当前 K 节点 N 命令的零基行索引。
        old_line = command_text(lines[node_line_index])  # 保存原始 N 命令文本供单差异审计。
        new_line = f"N,{k_node},{new_k_coord[0]:.15f},{new_k_coord[1]:.15f},{new_k_coord[2]:.15f}{AXIS_INLINE_COMMENT}"  # 以 15 位小数和统一中文注释生成唯一允许的新 N 命令。
        require(len(new_line) <= APDL_MAX_LINE_LENGTH, f"改写 N 命令超过 APDL 行长上限：{k_node}")  # 确认短注释不造成输入截断。
        modified_lines[node_line_index] = new_line + "\r\n"  # 只替换当前 K 节点行并保持 frozen CRLF。
        if representative_element_id is None or element_id < representative_element_id:  # 最小元素号作为诊断方案的代表横梁。
            representative_vector = new_axis  # 保存代表构件的新 K-I 向量。
            representative_element_id = element_id  # 保存与当前代表向量一致的元素号。
        max_orthogonality_error = max(max_orthogonality_error, orthogonality_error)  # 更新全体正交误差最大值。
        max_handedness_error = max(max_handedness_error, abs(handedness - 1.0))  # 更新全体右手误差最大值。
        max_reconstruction_error_mm = max(max_reconstruction_error_mm, reconstruction_error_mm)  # 更新全体公式重构误差最大值。
        audit_rows.append({"element_id": element_id, "material_id": TARGET_MATERIAL_ID, "section_id": TARGET_SECTION_ID, "type_id": TARGET_TYPE_ID, "element_line_number": target["line_number"], "k_node_line_number": node_line_index + 1, "i_node": i_node, "j_node": j_node, "k_node": k_node, "i_x_mm": i_coord[0], "i_y_mm": i_coord[1], "i_z_mm": i_coord[2], "j_x_mm": j_coord[0], "j_y_mm": j_coord[1], "j_z_mm": j_coord[2], "old_k_x_mm": old_k_coord[0], "old_k_y_mm": old_k_coord[1], "old_k_z_mm": old_k_coord[2], "new_k_x_mm": new_k_coord[0], "new_k_y_mm": new_k_coord[1], "new_k_z_mm": new_k_coord[2], "ex_x": ex[0], "ex_y": ex[1], "ex_z": ex[2], "ey_x": ey[0], "ey_y": ey[1], "ey_z": ey[2], "ez_x": ez[0], "ez_y": ez[1], "ez_z": ez[2], "old_ki_x_mm": old_axis[0], "old_ki_y_mm": old_axis[1], "old_ki_z_mm": old_axis[2], "new_ki_x_mm": new_axis[0], "new_ki_y_mm": new_axis[1], "new_ki_z_mm": new_axis[2], "old_ki_length_mm": vector_norm(old_axis), "new_ki_length_mm": vector_norm(new_axis), "dot_ex_ey": dot_ex_ey, "dot_ex_ez": dot_ex_ez, "dot_ey_ez": dot_ey_ez, "right_handed_triple_product": handedness, "old_n_command": old_line, "new_n_command": new_line})  # 保存逐根完整审计行；CSV 字段由配套 Markdown 解释。
    require(representative_vector is not None, "未形成代表 H175 新方向向量。")  # 目标非空时必须有代表向量。
    require(representative_element_id is not None, "未形成代表 H175 元素号。")  # 代表向量与元素身份必须同步存在。
    representative_error_mm = vector_norm(vector_subtract(representative_vector, (-ORIENTATION_LENGTH_MM, 0.0, 0.0)))  # 计算代表 K-I 与 -globalX 100 mm 的偏差。
    require(representative_error_mm <= REPRESENTATIVE_TOLERANCE_MM, f"代表 H175 的 K-I 不是 -globalX：误差 {representative_error_mm} mm")  # 落实诊断方案代表方向门禁。
    modified_text = "".join(modified_lines)  # 重组只含 2698 条目标 N 行变化的完整 CRLF 文本。
    changed_line_numbers = [index + 1 for index, (before, after) in enumerate(zip(lines, modified_lines)) if before != after]  # 精确枚举发生文本变化的一基行号。
    require(len(changed_line_numbers) == TARGET_ELEMENT_COUNT, f"include 改变行数不是 {TARGET_ELEMENT_COUNT}：{len(changed_line_numbers)}")  # 物理文本差异必须恰为 2698 行。
    require(changed_line_numbers == [int(row["k_node_line_number"]) for row in audit_rows], "改变行集合与目标 K 节点行集合不一致。")  # 禁止任何非 K 行变化。
    require(modified_text.count(AXIS_INLINE_COMMENT) == TARGET_ELEMENT_COUNT, "A10 K 节点中文行尾注释数量不闭合。")  # 每条改写代码行都必须有统一中文注释。
    summary = {"schema_version": 1, "status": "PASSED", "formula": {"ex": "normalize(J-I)", "ey": "normalize(globalZ-dot(globalZ,ex)*ex)", "ez": "cross(ex,ey)", "K": "I+100*ez", "orientation_length_mm": ORIENTATION_LENGTH_MM}, "target": {"material_id": TARGET_MATERIAL_ID, "section_id": TARGET_SECTION_ID, "type_id": TARGET_TYPE_ID, "element_count": len(target_elements), "unique_k_node_count": len(set(target_k_nodes)), "changed_n_command_count": len(changed_line_numbers), "inline_comment_count": modified_text.count(AXIS_INLINE_COMMENT)}, "exclusive_k_nodes": True, "representative_element_id": representative_element_id, "representative_new_k_minus_i_mm": {"x": representative_vector[0], "y": representative_vector[1], "z": representative_vector[2]}, "representative_minus_global_x_error_mm": representative_error_mm, "max_orthogonality_error": max_orthogonality_error, "max_handedness_error": max_handedness_error, "max_reconstruction_error_mm": max_reconstruction_error_mm, "source_line_count": len(lines), "changed_line_numbers_sha256": sha256_text(",".join(str(value) for value in changed_line_numbers)), "maximum_output_line_length": max(len(command_text(line)) for line in modified_lines), "apdl_line_length_limit": APDL_MAX_LINE_LENGTH}  # 汇总机器可读公式、数量、方向、误差和行长门禁。
    require(int(summary["maximum_output_line_length"]) <= APDL_MAX_LINE_LENGTH, "A10 include 存在超过 640 字符的行。")  # 对全文件而非仅改写行执行行长门禁。
    return modified_text, audit_rows, summary  # 返回内存改写结果和两级审计证据，不写源文件。


def append_a10_reject_gate(lines: list[str], parameter: str, operator: str, threshold: str, reason: str, explanation: str, close_energy_file: bool) -> None:  # 输入 APDL 行列表与比较条件并追加能量导出拒绝门禁。
    """条件成立时写 A10 gate、可选关闭 CSV 并立即退出；用于组件和每阶能量 fail-closed。"""  # 函数说明给出参数用途、输出和异常路径。
    b00.add_apdl(lines, f"*IF,{parameter},{operator},{threshold},THEN", explanation)  # 追加明确 APDL 比较条件。
    b00.add_apdl(lines, "/OUTPUT,a10_gate_status,txt", "把能量导出拒绝原因写入 A10 唯一 gate 状态文件。")  # 打开 A10 状态文件。
    b00.add_apdl(lines, f"/COM,STATUS=REJECTED REASON={reason}", f"写出固定拒绝原因 {reason} 供外部解析。")  # 写机器可读拒绝状态。
    b00.add_apdl(lines, "/OUTPUT", "恢复主输出，确保退出摘要保留在唯一主 OUT。")  # 关闭状态重定向。
    if close_energy_file:  # 只有 CSV 已打开的每阶门禁需要先关闭 *CFOPEN 文件。
        b00.add_apdl(lines, "*CFCLOS", "拒绝退出前关闭模态应变能 CSV，避免文件句柄保持。")  # 安全关闭能量 CSV。
    b00.add_apdl(lines, "/EXIT,NOSAVE", "能量证据门禁失败时立即退出且不保存数据库。")  # 阻止不完整能量证据被标为完成。
    b00.add_apdl(lines, "*ENDIF", "结束当前能量 fail-closed 条件分支。")  # 闭合 APDL 条件结构。


def energy_setup_block() -> list[str]:  # 无输入并返回模态向量循环前的组件计数与 CSV 打开 APDL 行。
    """验证 GATE_BOTTOM_E 恰含 2698 元素后打开纯数值 CSV；不改变求解设置。"""  # 函数说明给出输出和非物理性质。
    lines: list[str] = [f"{ENERGY_BEGIN} SETUP"]  # 以机器标记开始可剥离的 setup 注入块。
    b00.add_apdl(lines, "ALLSEL,ALL", "模态能量导出前恢复全部节点和单元选择。")  # 保证组件计数不受前序选择影响。
    b00.add_apdl(lines, "CMSEL,S,GATE_BOTTOM_E", "只选择 frozen include 定义的 H175 门架下横梁元素组件。")  # 建立目标组件选择。
    b00.add_apdl(lines, "*GET,A10_GATE_COUNT,ELEM,0,COUNT", "读取 GATE_BOTTOM_E 元素数，预期恰为 2698。")  # 获取组件规模。
    b00.add_apdl(lines, "ALLSEL,ALL", "组件计数后恢复全部实体，避免影响后续模态向量输出。")  # 恢复全选。
    append_a10_reject_gate(lines, "A10_GATE_COUNT", "NE", str(TARGET_ELEMENT_COUNT), "GATE_BOTTOM_COMPONENT_COUNT_MISMATCH", "GATE_BOTTOM_E 数量不等于 2698 时拒绝能量导出。", False)  # 在 CSV 打开前执行组件身份硬门禁。
    b00.add_apdl(lines, f"*CFOPEN,{ENERGY_FILE_STEM},csv", "打开无标题纯数值 CSV；仅 *VWRITE 写入，SSUM 仍留在主 OUT。")  # 打开未来应变能证据文件。
    lines.append(f"{ENERGY_END} SETUP")  # 结束 setup 注入块，供静态剥离审计。
    return lines  # 返回完整 setup APDL 行列表。


def energy_output_request_block() -> list[str]:  # 无输入并返回模态 SOLVE 前恢复元素能量结果记录的 APDL 行。
    """在 OUTRES,ALL,NONE 后显式执行 OUTRES,VENG,ALL；这是后续 ETABLE,SENE 的必要结果链。"""  # 函数说明给出插入位置、输出对象和必要性。
    lines: list[str] = [f"{ENERGY_BEGIN} VENG_REQUEST"]  # 以机器标记开始可剥离的 VENG 输出契约块。
    b00.add_apdl(lines, "OUTRES,VENG,ALL", "为全部 80 阶显式恢复元素能量结果，使 RSTP 可供 ETABLE,A10SENE,SENE 读取。")  # 在 ALL,NONE 后重新请求每阶 VENG。
    lines.append(f"{ENERGY_END} VENG_REQUEST")  # 结束 VENG 输出契约块供规范化审计。
    return lines  # 返回只含中文说明和 OUTRES,VENG,ALL 的完整 APDL 行列表。


def energy_mode_block(mode_index: int) -> list[str]:  # 输入一基模态阶次并返回该阶 GATE_BOTTOM_E 应变能 APDL 行。
    """输出 mode,total_sene,gate_sene,ratio 四列；总能量非正或组件能量负值时 fail-closed。"""  # 函数说明给出输入范围、CSV 输出和拒绝条件。
    require(1 <= mode_index <= REQUESTED_MODES, f"能量导出阶次越界：{mode_index}")  # 阶次必须位于固定 1..80 范围。
    suffix = f"{mode_index:04d}"  # 使用四位后缀保证 APDL 参数名唯一且可排序。
    total_name = f"A10_ST{suffix}"  # 当前阶全模型 SENE 参数名。
    gate_name = f"A10_SG{suffix}"  # 当前阶 GATE_BOTTOM_E SENE 参数名。
    ratio_name = f"A10_RG{suffix}"  # 当前阶组件与总 SENE 比参数名。
    lines: list[str] = [f"{ENERGY_BEGIN} MODE_{suffix}"]  # 以机器标记开始当前阶可剥离注入块。
    b00.add_apdl(lines, "ETABLE,ERAS", f"清空第 {mode_index} 阶之前的单元表定义。")  # 避免跨结果集沿用旧 SENE 列。
    b00.add_apdl(lines, "ETABLE,A10SENE,SENE", f"建立第 {mode_index} 阶单元应变能列；MXPAND 的 Elcalc=YES 保证可用。")  # 建立模态 SENE 列。
    b00.add_apdl(lines, "SSUM", f"对第 {mode_index} 阶当前全部元素的 A10SENE 求和。")  # 计算全模型模态应变能。
    b00.add_apdl(lines, f"*GET,{total_name},SSUM,0,ITEM,A10SENE", f"读取第 {mode_index} 阶全模型总应变能，单位 N·mm。")  # 获取总 SENE。
    append_a10_reject_gate(lines, total_name, "LE", "0", f"MODE_{suffix}_TOTAL_SENE_NONPOSITIVE", f"第 {mode_index} 阶总 SENE 非正时拒绝，禁止无效比例进入 CSV。", True)  # 总能量必须严格为正。
    b00.add_apdl(lines, "CMSEL,S,GATE_BOTTOM_E", f"只选择第 {mode_index} 阶 H175 门架下横梁组件。")  # 建立组件元素选择。
    b00.add_apdl(lines, "SSUM", f"对第 {mode_index} 阶 GATE_BOTTOM_E 的 A10SENE 求和。")  # 计算目标组件模态应变能。
    b00.add_apdl(lines, f"*GET,{gate_name},SSUM,0,ITEM,A10SENE", f"读取第 {mode_index} 阶 H175 组件应变能，单位 N·mm。")  # 获取组件 SENE。
    append_a10_reject_gate(lines, gate_name, "LT", "0", f"MODE_{suffix}_GATE_SENE_NEGATIVE", f"第 {mode_index} 阶 H175 组件 SENE 为负时拒绝。", True)  # 组件能量不允许出现负值。
    b00.add_apdl(lines, f"{ratio_name}={gate_name}/{total_name}", f"计算第 {mode_index} 阶 H175 组件 SENE 占全模型比例。")  # 计算无量纲能量比例。
    b00.add_apdl(lines, "ALLSEL,ALL", f"第 {mode_index} 阶组件求和后恢复全部实体。")  # 避免选择状态影响节点位移和转角输出。
    b00.add_vwrite(lines, f"*VWRITE,{mode_index},{total_name},{gate_name},{ratio_name}", "(F8.0,3(',',E24.16))", f"向能量 CSV 写第 {mode_index} 阶四列纯数值记录。")  # 输出阶次、总 SENE、组件 SENE 和比例。
    lines.append(f"{ENERGY_END} MODE_{suffix}")  # 结束当前阶注入块供静态剥离审计。
    return lines  # 返回当前阶完整 APDL 行列表。


def energy_close_block() -> list[str]:  # 无输入并返回向量循环结束后的 CSV 关闭 APDL 行。
    """关闭 a10_gate_bottom_modal_sene.csv；该块不改变任何模型或求解设置。"""  # 函数说明明确输出与非物理性质。
    lines: list[str] = [f"{ENERGY_BEGIN} CLOSE"]  # 开始可剥离的关闭块。
    b00.add_apdl(lines, "*CFCLOS", "关闭 80 阶 H175 模态应变能纯数值 CSV。")  # 正常关闭未来文件句柄并刷新记录。
    lines.append(f"{ENERGY_END} CLOSE")  # 结束关闭块。
    return lines  # 返回完整关闭 APDL 行列表。


def augment_main_with_energy(base_text: str) -> tuple[str, dict[str, Any]]:  # 输入 A10 身份化主 APDL 并返回能量增强文本和静态审计。
    """在模态 SOLVE 前恢复 VENG，并在每个 SET,1,n 后注入组件 SENE；剥离标记块后逐字等于基线。"""  # 函数说明给出插入位置、输出和非物理证据增量边界。
    lines = base_text.splitlines()  # 当前 B00 纯文本生成器固定返回 LF，按命令行拆分且不保留行尾。
    require(base_text.endswith("\n"), "当前 B00 主输入生成器未返回末尾 LF。")  # 保留生成器文本契约。
    all_none_indices = [index for index, line in enumerate(lines) if line == "OUTRES,ALL,NONE"]  # 查找模态求解前唯一关闭全部结果记录的命令。
    require(len(all_none_indices) == 1, "A10 基线主输入中的 OUTRES,ALL,NONE 数量不是 1。")  # VENG 恢复锚点必须唯一。
    all_none_index = all_none_indices[0]  # 取得唯一 ALL,NONE 的零基行索引。
    require(lines[all_none_index + 2] == "OUTRES,NSOL,ALL", "OUTRES,ALL,NONE 后未发现预期注释/NSOL 恢复结构。")  # 确认 B00 模板仍只恢复节点结果。
    veng_insertion_index = all_none_index + 3  # 把 VENG 块插在 NSOL,ALL 之后且模态 SOLVE 之前。
    lines[veng_insertion_index:veng_insertion_index] = energy_output_request_block()  # 显式恢复所有模态的元素能量结果记录。
    gopr_indices = [index for index, line in enumerate(lines) if line == "/GOPR"]  # 查找属性 CSV 结束后唯一 /GOPR 命令。
    require(len(gopr_indices) == 1, "A10 基线主输入中的 /GOPR 数量不是 1。")  # setup 插入锚点必须唯一。
    setup_index = gopr_indices[0] + 1  # setup 块插在 /GOPR 后、向量循环前。
    lines[setup_index:setup_index] = energy_setup_block()  # 插入组件计数门禁和 CSV 打开块。
    inserted_modes: list[int] = []  # 记录成功插入应变能的模态阶次。
    search_start = setup_index  # 后续查找从 setup 后开始以避开属性循环。
    for mode_index in range(1, REQUESTED_MODES + 1):  # 严格为固定 80 阶逐一寻找 SET 锚点。
        set_command = f"SET,1,{mode_index}"  # 当前阶向量循环的唯一结果集激活命令。
        matching_indices = [index for index in range(search_start, len(lines)) if lines[index] == set_command]  # 在剩余文本中查找当前阶 SET。
        require(len(matching_indices) == 1, f"第 {mode_index} 阶 SET 锚点数量不是 1。")  # 防止插错属性循环或重复注入。
        set_index = matching_indices[0]  # 取得当前阶 SET 的唯一行索引。
        require(lines[set_index + 2] == "ALLSEL,ALL", f"第 {mode_index} 阶 SET 后未发现预期注释/ALLSEL 结构。")  # B00 生成器每个命令前有一行中文注释，因此 ALLSEL 位于 +2。
        insertion_index = set_index + 3  # 能量块插在当前阶 ALLSEL 命令之后。
        block = energy_mode_block(mode_index)  # 生成当前阶可执行且 fail-closed 的 SENE APDL。
        lines[insertion_index:insertion_index] = block  # 插入当前阶能量块而不改变 SET 或 PRNSOL 原顺序。
        inserted_modes.append(mode_index)  # 记录当前阶注入成功。
        search_start = insertion_index + len(block)  # 下阶查找从当前注入块后继续。
    save_indices = [index for index, line in enumerate(lines) if line.startswith("SAVE,") and line.endswith("_modal,db")]  # 查找唯一模态数据库保存命令。
    require(len(save_indices) == 1, "A10 主输入中的 modal SAVE 数量不是 1。")  # 关闭 CSV 必须锚定唯一最终保存前。
    final_allsel_candidates = [index for index in range(search_start, save_indices[0]) if lines[index] == "ALLSEL,ALL"]  # 查找最后一阶循环后的最终全选命令。
    require(len(final_allsel_candidates) == 1, "第 80 阶后到 modal SAVE 前的最终 ALLSEL 数量不是 1。")  # 关闭块插入位置必须唯一。
    close_index = final_allsel_candidates[0] - 1  # 把关闭块放在最终 ALLSEL 的中文说明之前，保持注释紧邻命令。
    lines[close_index:close_index] = energy_close_block()  # 插入正常 *CFCLOS 块。
    augmented_text = "\n".join(lines) + "\n"  # 以当前生成器相同 LF 约定重组完整主输入。
    stripped_lines: list[str] = []  # 累积剥离所有标记注入块后的基线行。
    inside_energy_block = False  # 标记当前是否位于能量注入块内部。
    energy_block_count = 0  # 统计 VENG、setup、80 mode 和 close 共 83 个块。
    for line in augmented_text.splitlines():  # 按最终 APDL 原顺序逐行执行标记剥离审计。
        if line.startswith(ENERGY_BEGIN):  # 起始标记进入跳过状态。
            require(not inside_energy_block, "能量注入块发生嵌套。")  # 禁止标记结构重叠。
            inside_energy_block = True  # 开始跳过当前注入块。
            energy_block_count += 1  # 累加一个完整块的起始计数。
            continue  # 起始标记本身不进入规范化基线。
        if line.startswith(ENERGY_END):  # 结束标记退出跳过状态。
            require(inside_energy_block, "能量注入块结束标记没有起始标记。")  # 禁止孤立结束标记。
            inside_energy_block = False  # 结束当前注入块。
            continue  # 结束标记本身不进入规范化基线。
        if not inside_energy_block:  # 只保留注入块之外的原始 A10 基线行。
            stripped_lines.append(line)  # 按原顺序追加未改变的基线行。
    require(not inside_energy_block, "能量注入块在文件末尾未闭合。")  # 文件结束时所有标记必须闭合。
    stripped_text = "\n".join(stripped_lines) + "\n"  # 重建剥离注入后的规范化主输入。
    require(stripped_text == base_text, "剥离能量证据后 A10 主输入不等于当前 B00 控制模板。")  # 证明能量输出是唯一主输入增量。
    require(inserted_modes == list(range(1, REQUESTED_MODES + 1)), "能量导出阶次不是连续 1..80。")  # 80 阶必须无遗漏无重复。
    require(energy_block_count == REQUESTED_MODES + 3, "能量注入块数量不是 83。")  # VENG、setup、80阶、close 数量闭合。
    require("MXPAND,80,,,YES" in augmented_text, "A10 主输入未保留 MXPAND Elcalc=YES。")  # 模态单元能量可用性的硬前提。
    require("MODOPT,LANB,80\n" in augmented_text and "MODOPT,LANB,80," not in augmented_text, "A10 主输入未使用无频带上限 80 阶 LANB。")  # 禁止继承 B00 旧 0.35 Hz 截断。
    final_all_none_index = augmented_text.rfind("OUTRES,ALL,NONE")  # 定位最终主输入中最后一次关闭全部结果的命令。
    final_nsol_index = augmented_text.find("OUTRES,NSOL,ALL", final_all_none_index)  # 定位 ALL,NONE 后恢复节点结果的命令。
    final_veng_index = augmented_text.find("OUTRES,VENG,ALL", final_all_none_index)  # 定位 ALL,NONE 后恢复元素能量的命令。
    final_modal_solve_index = augmented_text.find("SOLVE", final_veng_index)  # 定位 VENG 恢复后的下一次模态求解命令。
    require(final_all_none_index < final_nsol_index < final_veng_index < final_modal_solve_index, "A10 模态 OUTRES 的 ALL,NONE→NSOL→VENG→SOLVE 顺序不闭合。")  # 硬验证节点与能量结果均在求解前恢复。
    audit = {"status": "PASSED", "requested_modes": REQUESTED_MODES, "energy_exported_modes": inserted_modes, "energy_block_count": energy_block_count, "component_name": "GATE_BOTTOM_E", "component_expected_element_count": TARGET_ELEMENT_COUNT, "etable_item": "SENE", "mxpand_elcalc_yes": True, "outres_all_none_then_nsol_all": True, "outres_all_none_then_veng_all": True, "modal_output_order": ["OUTRES,ALL,NONE", "OUTRES,NSOL,ALL", "OUTRES,VENG,ALL", "SOLVE"], "csv_columns": ["mode_index", "total_sene_n_mm", "gate_bottom_sene_n_mm", "gate_bottom_sene_ratio"], "future_output": f"solver/{ENERGY_FILE_STEM}.csv", "stripped_main_sha256": sha256_text(stripped_text), "base_main_sha256": sha256_text(base_text), "stripped_equals_base": stripped_text == base_text, "fail_closed_checks": ["GATE_BOTTOM_E count equals 2698", "each mode total SENE is positive", "each mode GATE_BOTTOM_E SENE is nonnegative"]}  # 汇总 VENG 结果链、能量输出结构和 fail-closed 门禁。
    return augmented_text, audit  # 返回增强主输入和静态审计，不启动求解器。


def relabel_b00_main_as_a10(b00_text: str) -> str:  # 输入当前 B00 生成器文本并返回只改证据身份的 A10 文本。
    """机械替换大写 B00 和小写 b00；jobname 已由调用方传入 A10，不改求解命令。"""  # 函数说明明确输入、输出和机械替换边界。
    return b00_text.replace("B00", "A10").replace("b00", "a10")  # 同时改参数、标题和证据文件前缀，不改数值契约。


def audit_rows_to_csv(rows: list[dict[str, Any]]) -> str:  # 输入逐根轴审计对象并返回合法无注释 CSV 文本。
    """保持首行字段顺序并以 LF 输出 2698 行；字段语义由 qa/field_dictionary.md 逐项说明。"""  # 函数说明遵守 CSV 语法例外和配套文档要求。
    require(len(rows) == TARGET_ELEMENT_COUNT, "待写轴审计行数不是 2698。")  # 写 CSV 前再次闭合目标数量。
    fieldnames = list(rows[0].keys())  # 以第一行插入顺序固定全部 CSV 列顺序。
    buffer = io.StringIO(newline="")  # 创建内存文本缓冲并禁用平台换行替换。
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")  # 创建合法 CSV 写入器并固定 LF。
    writer.writeheader()  # 写出唯一字段标题行，CSV 不加入非法注释。
    writer.writerows(rows)  # 按 APDL 元素原顺序写出全部 2698 行。
    return buffer.getvalue()  # 返回完整 CSV 文本供不可覆盖落盘。


def make_hash_ledger(entries: list[tuple[str, str]]) -> str:  # 输入摘要与标签二元组并返回标准双空格账本文本。
    """保持调用方顺序写出 SHA-256 账本；标签不能为空且摘要必须规范。"""  # 函数说明给出输入、输出和格式约束。
    rendered_lines: list[str] = []  # 保存逐项账本行。
    for digest, label in entries:  # 按确定性输入顺序遍历全部摘要标签。
        require(bool(re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII)), f"账本摘要格式错误：{label}")  # 每个摘要必须为小写 SHA-256。
        require(bool(label), "账本标签不得为空。")  # 空标签无法绑定文件身份。
        rendered_lines.append(f"{digest}  {label}")  # 使用标准两个空格分隔摘要和标签。
    return "\n".join(rendered_lines) + "\n"  # 返回末尾含 LF 的完整账本。


def make_field_dictionary() -> str:  # 无输入并返回 JSON、CSV、PATCH 和 TXT 配套 Markdown 说明。
    """逐项解释不支持注释的机器文件及关键字段，满足 AGENTS.md 配套说明要求。"""  # 函数说明给出输出用途。
    lines = [  # 按用户阅读顺序构造字段说明 Markdown。
        "# A10 准备与轴审计字段说明",  # 文档标题说明覆盖本 run 全部机器证据。
        "",  # 空行分隔标题与正文。
        "本目录内 JSON 和 CSV 保持严格机器语法，因此不在文件内部添加注释；本说明承担逐项解释。",  # 解释机器格式不加注释的原因。
        "",  # 空行分隔段落。
        "## h175_axis_audit.csv",  # 逐根轴审计表章节。
        "",  # 空行分隔标题与内容。
        "每行对应一个 MAT=61、SECNUM=61、TYPE=70 的 BEAM188 元素，共 2698 行。element_id 与 line_number 字段定位 EN/N 命令；i/j/k_node 是节点号；i、j、old_k、new_k 和 old/new_ki 字段单位均为 mm；ex/ey/ez 是单位向量；三个 dot 字段和 right_handed_triple_product 审计正交右手系；old_n_command/new_n_command 是唯一允许变化的 APDL 行。",  # 解释所有列族、单位和约束。
        "",  # 空行分隔章节。
        "## h175_axis_summary.json",  # 轴汇总 JSON 章节。
        "",  # 空行分隔标题与内容。
        "formula 固定四步局部轴公式；target 记录属性编号与 2698 数量闭合；exclusive_k_nodes 表示 K 节点未被任何 EN 当作 I/J；representative 字段验证 K-I 约为 -global X；max_* 字段给出正交、右手和重构误差；maximum_output_line_length 必须不超过 640。",  # 解释轴汇总字段。
        "",  # 空行分隔章节。
        "## input_hash_audit.csv",  # 输入哈希审计表章节。
        "",  # 空行分隔标题与内容。
        "每行是一项依赖。role=invariant 的 10 项必须在 B00 snapshot、B00 solver、A10 snapshot、A10 solver 四处同哈希；role=controlled_axis_change 的 include 要求两个 B00 副本同哈希、两个 A10 副本同哈希且新旧不同。expected_b00_sha256 来自 frozen B00 manifest。",  # 解释哈希表角色和通过条件。
        "",  # 空行分隔章节。
        "## model_single_difference_audit.json",  # 单物理差异 JSON 章节。
        "",  # 空行分隔标题与内容。
        "physical_change_family_count 必须为 1；唯一家族是 2698 个 H175 K 方向节点。canonicalized_modified_sha256 等于 frozen_source_sha256 表示把这些目标行还原后全文逐字闭合。forbidden_changes 全为 false，说明 Iyy/Izz、E、密度、质量、索力、CERIG/CP、网格和剪切参数未变。",  # 解释单差异的规范化证据。
        "",  # 空行分隔章节。
        "## main_control_flow_audit.json 与 b00_old_to_current_control_flow.patch",  # 主控制流证据章节。
        "",  # 空行分隔标题与内容。
        "PATCH 仅记录 frozen B00 旧主输入到当前 B00 单作业模板的非物理控制修正；JSON 记录修正版模板哈希、A10 机械身份化、80 阶无频带上限、真实 LS2、严格结果数闭合、ALL,NONE 后显式恢复 NSOL/VENG 及 GATE_BOTTOM_E 每阶 SENE 注入。此差异不计入模型物理单差异。",  # 区分控制修复、结果输出闭合与模型物理变化。
        "",  # 空行分隔章节。
        "## manifest.json、A10_status.json 与 preflight.json",  # 根机器清单和状态章节。
        "",  # 空行分隔标题与内容。
        "manifest 固定父 B00、jobname、依赖、求解契约、能量输出和未来 argv；A10_status 可报告 PREPARED_WAITING_RESOURCES、PREPARED_NOT_STARTED 或 PREPARED_NOT_STARTED_USER_OVERRIDE，mapdl_started/process_started/execution_attempted 永远为 false；preflight 分别记录实测资源和 USER_OVERRIDE。任何 READY/RUNNING 状态均不由本脚本产生。",  # 解释状态、用户覆盖语义和禁止执行事实。
        "",  # 空行分隔章节。
        "## source_hashes.sha256 与 artifact_hashes.sha256",  # 两类账本章节。
        "",  # 空行分隔标题与内容。
        "source_hashes 绑定 frozen B00 输入、当前 B00 模板源码、A10 编排器和生成输入；artifact_hashes 枚举除自身外的 run 内全部文件。每行格式为 SHA-256、两个空格、标签。",  # 解释账本边界和格式。
        "",  # 空行分隔章节。
        "## 未来 a10_gate_bottom_modal_sene.csv",  # 求解后能量 CSV 章节。
        "",  # 空行分隔标题与内容。
        "该文件仅在未来显式启动 MAPDL 后由主 APDL 生成，无标题四列依次为 mode_index、total_sene_n_mm、gate_bottom_sene_n_mm、gate_bottom_sene_ratio；准备阶段不会创建空结果文件。",  # 解释未来四列输出和 prepare-only 行为。
    ]  # 结束 Markdown 行列表。
    return "\n".join(lines) + "\n"  # 返回末尾含 LF 的完整字段说明。


def make_result_packet(run_name: str, jobname: str, status: str, memory: dict[str, int | bool], disk: dict[str, int | bool | str], axis_hash: str, user_override_memory_gate: bool) -> str:  # 输入 run 身份、资源、轴摘要和内存覆盖标志并返回用户可读准备包。
    """汇总唯一物理变化、资源等待、未来证据和绝不执行事实；不包含求解结果。"""  # 函数说明给出输入、输出和状态边界。
    lines = [  # 按结论优先顺序构造结果包 Markdown。
        "# A10 H175 局部轴第二轮准备结果",  # 文档标题标识 A10 轴试算。
        "",  # 空行分隔标题与正文。
        f"- run：{run_name}",  # 记录唯一 run 目录名。
        f"- jobname：{jobname}",  # 记录未来 MAPDL 唯一 ASCII jobname。
        f"- 状态：{status}",  # 明确当前仅等待资源或外部启动。
        "- MAPDL：未启动；本脚本没有任何进程创建或删除路径。",  # 明确 prepare-only 事实。
        f"- 唯一物理变化：MAT/SECNUM 61 的 {TARGET_ELEMENT_COUNT} 根 H175，仅按 K=I+100*ez 改独占方向节点。",  # 概括单物理差异。
        f"- A10 轴 include SHA-256：{axis_hash}",  # 记录新物理输入身份。
        f"- 可用物理内存：{int(memory.get('available_physical_bytes', 0))} byte；8 GiB 门禁={bool(memory.get('memory_ready', False))}。",  # 记录准备瞬间内存门禁。
        f"- 内存门槛策略：{'USER_OVERRIDE' if user_override_memory_gate else 'ENFORCED'}；覆盖只改变调度授权记录，不代表资源充足。",  # 明确用户覆盖与实测资源是两个独立事实。
        f"- 可用磁盘：{int(disk.get('free_bytes', 0))} byte；32 GiB 门禁={bool(disk.get('disk_ready', False))}。",  # 记录准备瞬间磁盘门禁。
        "- 主流程：当前修正版 B00 单作业控制模板，真实 LS2、80 阶无频带上限、MXPAND Elcalc=YES、严格 80/80 闭合。",  # 概括非物理控制修复。
        "- 新增未来证据：在 ALL,NONE 后显式恢复 NSOL,ALL 与 VENG,ALL，再导出每阶 GATE_BOTTOM_E 总 SENE、组件 SENE 与比例；组件数和能量有效性 fail-closed。",  # 概括闭合后的能量结果链。
        "",  # 空行分隔结论与下一步。
        "下一步只能由独立显式启动流程在内存与磁盘门禁通过后执行 launch_command.txt；该文件在本次准备中仅作为文本证据。",  # 给出安全下一动作。
    ]  # 结束结果包 Markdown 行列表。
    return "\n".join(lines) + "\n"  # 返回末尾含 LF 的完整结果包。


def write_artifact_ledger(run_dir: Path) -> None:  # 输入已封板 run 根目录并写出除账本自身外的全部产物摘要。
    """递归枚举普通文件并写 artifact_hashes.sha256；调用后禁止再修改 run。"""  # 函数说明给出输入、输出和调用时序约束。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 定义最终产物账本路径。
    require(not ledger_path.exists(), f"artifact 账本已存在：{ledger_path}")  # 拒绝覆盖或重复封板。
    files = sorted(path for path in run_dir.rglob("*") if path.is_file() and path != ledger_path)  # 按相对路径稳定枚举全部既有普通文件。
    require(bool(files), "A10 run 内没有可封板产物。")  # 空 run 不能形成有效证据。
    entries = [(sha256_file(path), path.relative_to(run_dir).as_posix()) for path in files]  # 逐文件计算摘要并生成 run 相对标签。
    write_new_text(ledger_path, make_hash_ledger(entries))  # 以不可覆盖方式写出最终完整账本。


def prepare_run(optional_run_name: str | None, user_override_memory_gate: bool) -> Path:  # 输入可选安全 run 名和显式内存覆盖标志并返回新 A10 run 绝对路径。
    """完成全部只读源验证、内存改写、双副本和审计封板；无论资源状态都不启动 MAPDL。"""  # 函数说明给出输入、输出和绝对执行禁令。
    require(B00_RUN.is_dir(), f"指定 frozen B00 run 不存在：{B00_RUN}")  # 父 run 必须按固定名称存在。
    current_b00_hash = sha256_file(Path(b00.__file__).resolve())  # 复算当前 B00 模板源码身份。
    require(current_b00_hash == CURRENT_B00_PREPARER_SHA256, f"当前 B00 模板源码哈希漂移：{current_b00_hash}")  # 防止未审计控制流被静默使用。
    b00_manifest_path = B00_RUN / "manifest.json"  # 定义 frozen B00 根 manifest 路径。
    b00_manifest = read_json(b00_manifest_path)  # 读取 frozen 依赖、jobname 和未来执行元数据。
    require(b00_manifest.get("run_id") == "B00_LEGACY_COMPLETE", "frozen B00 manifest 的 run_id 不匹配。")  # 固定父模型身份。
    dependencies_value = b00_manifest.get("dependencies")  # 读取 manifest 依赖字段供类型检查。
    require(isinstance(dependencies_value, list), "frozen B00 dependencies 不是数组。")  # 依赖必须为有序数组。
    dependencies: list[dict[str, Any]] = dependencies_value  # 在类型门禁后收窄为依赖对象列表。
    require(len(dependencies) == DEPENDENCY_COUNT, "frozen B00 依赖数不是 11。")  # 依赖数量闭合。
    require([item.get("order") for item in dependencies] == list(range(1, DEPENDENCY_COUNT + 1)), "frozen B00 依赖 order 不是 1..11。")  # 装配顺序闭合。
    basenames = [str(item.get("basename")) for item in dependencies]  # 提取十一项文件名供唯一性和模板使用。
    require(len(set(basenames)) == DEPENDENCY_COUNT, "frozen B00 依赖 basename 不唯一。")  # 禁止复制时同名覆盖。
    require(basenames.count(AXIS_INCLUDE_NAME) == 1, "frozen B00 依赖中 H175 include 数量不是 1。")  # 唯一允许改写文件必须恰好出现一次。
    delivery_status_path = B00_RUN / "delivery_59mode_20260715" / "交付ZIP状态.json"  # 指定 completed B00 交付状态证据。
    delivery_summary_path = B00_RUN / "delivery_59mode_20260715" / "关键结果摘要.json"  # 指定 completed B00 59 阶结果摘要。
    delivery_status = read_json(delivery_status_path)  # 读取冻结交付完成状态。
    delivery_summary = read_json(delivery_summary_path)  # 读取冻结结果规模和旧主错误事实。
    require(delivery_status.get("status") == "COMPLETED", "指定 B00 交付状态不是 COMPLETED。")  # 父 run 必须已有完成交付证据。
    require(delivery_summary.get("mode_count") == 59, "指定 B00 交付摘要不是 0-0.35 Hz 的 59 阶。")  # 固定本轮诊断来源规模。
    old_main_path = B00_RUN / "solver" / B00_MAIN_NAME  # 定义 frozen 旧主输入路径。
    require(sha256_file(old_main_path) == B00_OLD_MAIN_SHA256, "frozen B00 旧主输入哈希不匹配。")  # 固定 lineage 旧控制流身份。
    source_axis_path = B00_RUN / "input_snapshot" / AXIS_INCLUDE_NAME  # 唯一物理派生源固定使用 frozen input_snapshot。
    require(sha256_file(source_axis_path) == B00_AXIS_SHA256, "frozen H175 include 哈希不匹配。")  # 固定源物理输入身份。
    source_axis_text = source_axis_path.read_bytes().decode("utf-8")  # 以原始字节解码无 BOM UTF-8，保留 frozen CRLF 身份。
    modified_axis_text, axis_rows, axis_summary = parse_and_transform_axis(source_axis_text)  # 在内存中完成 2698 个 K 节点受控改写和轴审计。
    modified_axis_hash = sha256_text(modified_axis_text)  # 计算尚未落盘的新 include 摘要。
    require(modified_axis_hash != B00_AXIS_SHA256, "A10 H175 include 与 B00 源哈希意外相同。")  # 物理试算必须确有受控差异。
    created = datetime.now(timezone.utc)  # 取得唯一 UTC 微秒时间供目录、jobname 和 manifest 共用。
    generated_run_name = f"{RUN_ID}_{created.strftime('%Y%m%dT%H%M%S%f')}Z"  # 生成标准 A10_H175_AXIS_UTC微秒目录名。
    run_name = optional_run_name if optional_run_name is not None else generated_run_name  # 优先采用用户显式但已受约束的确定性名称。
    require(bool(RUN_NAME_PATTERN.fullmatch(run_name)), f"A10 run 名格式非法：{run_name}")  # 禁止路径逃逸、空格和非标准名称。
    run_dir = ULTRA_RUNS_ROOT / run_name  # 计算新 A10 run 目标路径。
    require(not run_dir.exists(), f"拒绝覆盖既有 A10 run：{run_dir}")  # 新 run 目录必须尚未存在。
    jobname = f"cw_A10_{created.strftime('%m%d')}t{created.strftime('%H%M%S')}_{secrets.token_hex(1)}"  # 生成同秒碰撞概率低的 ASCII 作业名。
    require(bool(JOBNAME_PATTERN.fullmatch(jobname)), f"A10 jobname 非法：{jobname}")  # 验证首字符、字符集和最大 32 位约束。
    require(len(jobname) <= 32, f"A10 jobname 超过 32 位：{jobname}")  # 显式记录 MAPDL 长度硬门禁。
    current_b00_template = b00.build_main_input(jobname, REQUESTED_MODES, dependencies)  # 用当前修正版纯文本生成器构造单作业 B00 控制模板。
    a10_base_main = relabel_b00_main_as_a10(current_b00_template)  # 机械改参数和证据身份为 A10，不改求解数值与装配顺序。
    a10_main_text, energy_audit = augment_main_with_energy(a10_base_main)  # 增加每阶 H175 模态应变能证据并验证可剥离闭合。
    a10_main_hash = sha256_text(a10_main_text)  # 计算最终 A10 主输入内存摘要。
    old_jobname = str(b00_manifest.get("jobname"))  # 取得 frozen 旧 jobname 供控制流同身份比较。
    current_b00_for_diff = b00.build_main_input(old_jobname, REQUESTED_MODES, dependencies)  # 以旧 jobname 生成当前控制模板，排除名称噪声。
    old_main_text = old_main_path.read_text(encoding="utf-8")  # 只读 frozen 旧主输入供非物理差异补丁。
    diff_lines = list(difflib.unified_diff(old_main_text.splitlines(), current_b00_for_diff.splitlines(), fromfile=f"{B00_RUN_NAME}/solver/{B00_MAIN_NAME}", tofile=f"current/{B00_MAIN_NAME}", lineterm=""))  # 生成稳定 unified diff 行列表。
    control_patch_text = "\n".join(diff_lines) + "\n"  # 重组带末尾 LF 的控制流补丁证据。
    removed_diff_lines = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))  # 统计旧控制文本删除行数。
    added_diff_lines = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))  # 统计当前控制文本新增行数。
    memory = b00.memory_snapshot()  # 只读获取当前物理内存快照，不触发任何执行。
    disk = b00.disk_snapshot()  # 只读获取当前项目卷磁盘快照，不触发任何执行。
    measured_resources_ready = bool(memory.get("memory_ready")) and bool(disk.get("disk_ready"))  # 计算未覆盖的实测资源联合布尔值，仅用于事实记录。
    launch_policy_satisfied = bool(disk.get("disk_ready")) and (bool(memory.get("memory_ready")) or user_override_memory_gate)  # 用户覆盖只替代内存门槛，不替代磁盘门槛。
    status_value = STATUS_OVERRIDE if user_override_memory_gate and bool(disk.get("disk_ready")) else ("PREPARED_NOT_STARTED" if measured_resources_ready else STATUS_WAITING)  # 覆盖时明确记录 USER_OVERRIDE，仍不声称 READY/RUNNING。
    next_action_value = OVERRIDE_NEXT_ACTION if user_override_memory_gate else NEXT_ACTION  # 根据是否覆盖选择对应外部显式启动说明。
    input_snapshot_dir = run_dir / "input_snapshot"  # 定义 A10 第一套输入快照目录。
    solver_dir = run_dir / "solver"  # 定义未来唯一工作目录和第二套输入复制目录。
    qa_dir = run_dir / "qa"  # 定义差异、轴、哈希和 preflight 证据目录。
    lineage_dir = run_dir / "lineage"  # 定义 frozen B00 与当前模板源码快照目录。
    orchestrator_dir = run_dir / "orchestrator_snapshot"  # 定义 A10 实际执行源码快照目录。
    run_dir.mkdir(parents=True, exist_ok=False)  # 在全部内存门禁通过后首次创建唯一新 run；不触碰任何旧 run。
    input_hash_rows: list[dict[str, Any]] = []  # 保存十一项 B00/A10 双副本哈希闭合记录。
    source_ledger_entries: list[tuple[str, str]] = []  # 保存 frozen 源、模板源码和生成输入身份账本。
    for dependency in dependencies:  # 按 order 1..11 复制并审计全部 frozen 依赖。
        order = int(dependency["order"])  # 读取依赖装配顺序。
        basename = str(dependency["basename"])  # 读取依赖文件名。
        expected_hash = str(dependency["sha256"])  # 读取 frozen manifest 封存摘要。
        b00_snapshot_source = B00_RUN / "input_snapshot" / basename  # 第一源固定为 frozen B00 input_snapshot。
        b00_solver_source = B00_RUN / "solver" / basename  # 第二源用于证明 completed solver 使用同一依赖字节。
        b00_snapshot_hash = sha256_file(b00_snapshot_source)  # 复算 frozen 快照摘要。
        b00_solver_hash = sha256_file(b00_solver_source)  # 复算 frozen solver 副本摘要。
        require(b00_snapshot_hash == expected_hash, f"B00 snapshot 哈希不等于 manifest：{basename}")  # 固定第一父副本身份。
        require(b00_solver_hash == expected_hash, f"B00 solver 哈希不等于 manifest：{basename}")  # 固定第二父副本身份。
        snapshot_destination = input_snapshot_dir / basename  # 定义 A10 第一套目标路径。
        solver_destination = solver_dir / basename  # 定义 A10 第二套目标路径。
        if basename == AXIS_INCLUDE_NAME:  # 唯一物理变化文件进入受控文本写入路径。
            write_new_text(snapshot_destination, modified_axis_text)  # 写 A10 修改后的 input_snapshot 副本。
            write_new_text(solver_destination, modified_axis_text)  # 写逐字相同的 solver 副本。
            snapshot_hash = sha256_file(snapshot_destination)  # 从磁盘复算第一新副本摘要。
            solver_hash = sha256_file(solver_destination)  # 从磁盘复算第二新副本摘要。
            require(snapshot_hash == modified_axis_hash and solver_hash == modified_axis_hash, "A10 H175 include 双副本哈希不闭合。")  # 两份新输入必须逐字相同。
            role = "controlled_axis_change"  # 标记唯一允许变化的物理依赖角色。
            passed = snapshot_hash != expected_hash and solver_hash != expected_hash  # 新旧必须不同且新副本已同哈希。
        else:  # 其余十项进入不可变逐字复制路径。
            snapshot_hash = copy_new_verified(b00_snapshot_source, snapshot_destination)  # 复制并闭合 A10 第一副本。
            solver_hash = copy_new_verified(b00_snapshot_source, solver_destination)  # 从同一 frozen 快照复制并闭合 A10 solver 副本。
            role = "invariant"  # 标记材料、质量、索力、连接、网格等不可变依赖。
            passed = snapshot_hash == expected_hash and solver_hash == expected_hash  # 不可变项必须四端同哈希。
        require(passed, f"A10 输入哈希审计失败：{basename}")  # 任一依赖闭合失败立即中断。
        input_hash_rows.append({"order": order, "basename": basename, "role": role, "expected_b00_sha256": expected_hash, "b00_input_snapshot_sha256": b00_snapshot_hash, "b00_solver_sha256": b00_solver_hash, "a10_input_snapshot_sha256": snapshot_hash, "a10_solver_sha256": solver_hash, "passed": passed})  # 保存当前依赖完整哈希链。
        source_ledger_entries.append((b00_snapshot_hash, f"B00_FROZEN::input_snapshot/{basename}"))  # 把 frozen 源身份加入 source 账本。
        source_ledger_entries.append((snapshot_hash, f"A10_GENERATED::input_snapshot/{basename}"))  # 把 A10 第一副本身份加入 source 账本。
        source_ledger_entries.append((solver_hash, f"A10_GENERATED::solver/{basename}"))  # 把 A10 solver 副本身份加入 source 账本。
    snapshot_main_path = input_snapshot_dir / A10_MAIN_NAME  # 定义 A10 主输入第一快照路径。
    solver_main_path = solver_dir / A10_MAIN_NAME  # 定义 A10 未来唯一主输入路径。
    write_new_text(snapshot_main_path, a10_main_text)  # 写入主输入第一快照。
    write_new_text(solver_main_path, a10_main_text)  # 写入逐字相同的 solver 主输入。
    require(sha256_file(snapshot_main_path) == a10_main_hash and sha256_file(solver_main_path) == a10_main_hash, "A10 主输入双副本哈希不闭合。")  # 双副本必须等于内存模板摘要。
    copied_b00_manifest_hash = copy_new_verified(b00_manifest_path, lineage_dir / "b00_frozen_manifest.json")  # 快照父 manifest 供离线 lineage。
    copied_delivery_status_hash = copy_new_verified(delivery_status_path, lineage_dir / "b00_delivery_status.json")  # 快照 completed 交付状态。
    copied_delivery_summary_hash = copy_new_verified(delivery_summary_path, lineage_dir / "b00_delivery_summary.json")  # 快照 59 阶结果摘要。
    copied_old_main_hash = copy_new_verified(old_main_path, lineage_dir / B00_MAIN_NAME)  # 快照 frozen 旧主输入供补丁复核。
    copied_b00_preparer_hash = copy_new_verified(Path(b00.__file__).resolve(), lineage_dir / "current_ultra_b00_prepare.py")  # 快照当前修正版控制模板源码。
    copied_a10_preparer_hash = copy_new_verified(SCRIPT_PATH, orchestrator_dir / SCRIPT_PATH.name)  # 快照实际运行的 A10 编排器源码。
    source_ledger_entries.extend([(copied_b00_manifest_hash, "B00_FROZEN::manifest.json"), (copied_delivery_status_hash, "B00_FROZEN::delivery_status.json"), (copied_delivery_summary_hash, "B00_FROZEN::delivery_summary.json"), (copied_old_main_hash, f"B00_FROZEN::solver/{B00_MAIN_NAME}"), (copied_b00_preparer_hash, "TEMPLATE_SOURCE::ultra_b00_prepare.py"), (copied_a10_preparer_hash, "ORCHESTRATOR_SOURCE::ultra_a10_prepare.py"), (a10_main_hash, f"A10_GENERATED::input_snapshot/{A10_MAIN_NAME}"), (a10_main_hash, f"A10_GENERATED::solver/{A10_MAIN_NAME}")])  # 把 lineage、源码和生成主输入身份加入账本。
    write_new_text(qa_dir / "h175_axis_audit.csv", audit_rows_to_csv(axis_rows))  # 写 2698 根逐轴 CSV 证据。
    write_new_json(qa_dir / "h175_axis_summary.json", axis_summary)  # 写轴公式、误差和行长汇总 JSON。
    hash_buffer = io.StringIO(newline="")  # 为十一项输入哈希表创建独立内存缓冲。
    hash_writer = csv.DictWriter(hash_buffer, fieldnames=list(input_hash_rows[0].keys()), lineterminator="\n")  # 固定哈希 CSV 列顺序和 LF。
    hash_writer.writeheader()  # 写合法无注释标题行。
    hash_writer.writerows(input_hash_rows)  # 按 order 1..11 写全部依赖哈希链。
    write_new_text(qa_dir / "input_hash_audit.csv", hash_buffer.getvalue())  # 写十一项哈希审计 CSV。
    original_lines = source_axis_text.splitlines(keepends=True)  # 重新取得 frozen 源行供规范化恢复。
    modified_lines = modified_axis_text.splitlines(keepends=True)  # 取得 A10 改写行供规范化恢复。
    restored_lines = list(modified_lines)  # 创建只用于审计的 A10 文本副本。
    for row in axis_rows:  # 用逐根 CSV 中的原始 N 命令恢复全部目标行。
        line_index = int(row["k_node_line_number"]) - 1  # 把一基 N 行号转换为零基索引。
        restored_lines[line_index] = original_lines[line_index]  # 恢复对应 frozen 原行及其 CRLF。
    restored_text = "".join(restored_lines)  # 重组规范化恢复后的完整 include。
    require(restored_text == source_axis_text, "还原 2698 个 K 节点后 include 未逐字等于 frozen 源。")  # 证明没有任何其他文本变化。
    model_single_difference = {"schema_version": 1, "status": "PASSED", "physical_change_family_count": 1, "physical_change_family": "H175_BEAM188_ORIENTATION_NODE_K_ONLY", "parent_run": B00_RUN_NAME, "source_file": f"input_snapshot/{AXIS_INCLUDE_NAME}", "frozen_source_sha256": B00_AXIS_SHA256, "modified_sha256": modified_axis_hash, "canonicalized_modified_sha256": sha256_text(restored_text), "canonicalized_equals_frozen": restored_text == source_axis_text, "changed_line_count": TARGET_ELEMENT_COUNT, "changed_command": "N,K,X,Y,Z with inline Chinese comment", "target_element_count": TARGET_ELEMENT_COUNT, "invariant_dependency_count": sum(1 for row in input_hash_rows if row["role"] == "invariant"), "controlled_dependency_count": sum(1 for row in input_hash_rows if row["role"] == "controlled_axis_change"), "forbidden_changes": {"iyy_izz": False, "elastic_modulus": False, "density": False, "mass": False, "cable_force_or_initial_state": False, "cerig_or_cp": False, "mesh_topology": False, "section_shear_parameters": False}, "source_command_counts": {"CERIG": source_axis_text.count("CERIG,"), "CP": sum(source_axis_text.count(f"CP,{index},") for index in range(1, EXPECTED_CP_COUNT + 1))}, "modified_command_counts": {"CERIG": modified_axis_text.count("CERIG,"), "CP": sum(modified_axis_text.count(f"CP,{index},") for index in range(1, EXPECTED_CP_COUNT + 1))}, "main_control_corrections_are_nonphysical_and_separately_audited": True}  # 构造唯一物理差异的机器证明。
    require(model_single_difference["source_command_counts"] == model_single_difference["modified_command_counts"], "A10 include 的 CERIG/CP 计数发生变化。")  # 连接命令计数必须不变。
    require(int(model_single_difference["source_command_counts"]["CERIG"]) == EXPECTED_CERIG_COUNT, "frozen/A10 include 的 CERIG 数不是 5078。")  # 明确保留 legacy 5078 CERIG。
    write_new_json(qa_dir / "model_single_difference_audit.json", model_single_difference)  # 写唯一物理差异 JSON。
    current_template_hash = sha256_text(current_b00_for_diff)  # 计算同旧 jobname 的当前 B00 控制模板摘要。
    main_control_audit = {"schema_version": 1, "status": "PASSED", "physical_change": False, "frozen_old_main": {"path": f"{B00_RUN_NAME}/solver/{B00_MAIN_NAME}", "sha256": B00_OLD_MAIN_SHA256, "known_original_main_out_error_count": delivery_summary.get("original_static_main_out_errors"), "known_modal_resume_error_count": delivery_summary.get("modal_resume_errors")}, "current_template": {"source": str(Path(b00.__file__).resolve()), "source_sha256": current_b00_hash, "generated_same_old_jobname_sha256": current_template_hash, "true_ls2_same_solu": "LS1 收敛门禁通过后保持在同一 /SOLU" in current_b00_for_diff, "unbounded_lanb_80": "MODOPT,LANB,80\n" in current_b00_for_diff and "MODOPT,LANB,80," not in current_b00_for_diff, "strict_result_count_80": "*IF,B00_AVAILABLE,NE,80,THEN" in current_b00_for_diff, "mxpand_elcalc_yes": "MXPAND,80,,,YES" in current_b00_for_diff}, "diff_patch": "qa/b00_old_to_current_control_flow.patch", "diff_added_lines": added_diff_lines, "diff_removed_lines": removed_diff_lines, "a10_identity_relabel_only_before_energy": True, "a10_base_main_sha256": sha256_text(a10_base_main), "a10_final_main_sha256": a10_main_hash, "energy_export": energy_audit, "solver_contract": {"from_scratch_static": True, "ls1_time": 1.0, "ls2_time": 1.001, "ls2_nsubst": [1, 1, 1], "ls2_stabilization": "OFF", "modal_restart": "ANTYPE,,RESTART,2,,PERTURB", "modal_solver": "LANB", "modes": REQUESTED_MODES, "frequency_bounds_hz": None, "lumped_mass": False, "mxpand_element_calculation": True}}  # 构造非物理主控制修复、A10 身份化和能量输出审计。
    require(all(bool(value) for value in (main_control_audit["current_template"]["true_ls2_same_solu"], main_control_audit["current_template"]["unbounded_lanb_80"], main_control_audit["current_template"]["strict_result_count_80"], main_control_audit["current_template"]["mxpand_elcalc_yes"])), "当前 B00 控制模板关键修复未全部通过静态审计。")  # 四项单作业控制门禁必须全部为真。
    write_new_json(qa_dir / "main_control_flow_audit.json", main_control_audit)  # 写非物理控制流审计 JSON。
    write_new_text(qa_dir / "b00_old_to_current_control_flow.patch", control_patch_text)  # 写 frozen 旧主到当前模板 unified diff。
    write_new_text(qa_dir / "field_dictionary.md", make_field_dictionary())  # 写所有无注释机器格式的配套字段说明。
    mapdl_executable = str(b00_manifest.get("mapdl_executable"))  # 从 frozen manifest 读取未来可执行文件路径，仅作为文本参数。
    mapdl_sha256 = str(b00_manifest.get("mapdl_executable_sha256"))  # 从 frozen manifest 读取未来可执行程序身份。
    output_path = solver_dir / f"{jobname}.out"  # 定义未来唯一主 OUT 路径，不在准备阶段创建。
    launch_argv = [mapdl_executable, "-b", "-dis", "-mpi", "intelmpi", "-np", "4", "-j", jobname, "-dir", str(solver_dir.resolve()), "-i", str(solver_main_path.resolve()), "-o", str(output_path.resolve())]  # 构造未来 DMP4 参数数组，当前函数不调用任何进程 API。
    rendered_command = "& " + " ".join(b00.powershell_quote(argument) for argument in launch_argv)  # 只把未来参数渲染为人工可读 PowerShell 文本。
    launch_text = "\n".join(["STATUS=NOT_EXECUTED_PREPARED_COMMAND_ONLY", "EXECUTION_ATTEMPTED=false", f"CURRENT_PREPARE_STATUS={status_value}", f"MEMORY_GATE_POLICY={'USER_OVERRIDE' if user_override_memory_gate else 'ENFORCED'}", f"MEASURED_MEMORY_READY={str(bool(memory.get('memory_ready'))).lower()}", f"DISK_GATE_POLICY=ENFORCED_AND_READY_{str(bool(disk.get('disk_ready'))).lower()}", "QUEUE_POLICY=NO_QUEUE_OR_AUTOSTART_IMPLEMENTED", "FUTURE_DMP4_COMMAND_BEGIN", rendered_command, "FUTURE_DMP4_COMMAND_END", "THIS_FILE_IS_EVIDENCE_ONLY_AND_WAS_NOT_EXECUTED_BY_ULTRA_A10_PREPARE", ""])  # 生成醒目标记未执行、内存覆盖事实和无队列的未来命令证据。
    write_new_text(run_dir / "launch_command.txt", launch_text)  # 写未来命令文本但绝不执行。
    checks = [{"check_id": "PARENT_B00_DELIVERY_COMPLETED", "passed": True, "actual": delivery_status.get("status"), "expected": "COMPLETED"}, {"check_id": "FROZEN_DEPENDENCIES_11", "passed": len(input_hash_rows) == DEPENDENCY_COUNT, "actual": len(input_hash_rows), "expected": DEPENDENCY_COUNT}, {"check_id": "INVARIANT_DEPENDENCIES_10", "passed": sum(1 for row in input_hash_rows if row["role"] == "invariant") == 10, "actual": sum(1 for row in input_hash_rows if row["role"] == "invariant"), "expected": 10}, {"check_id": "CONTROLLED_PHYSICAL_CHANGE_FAMILY_1", "passed": True, "actual": 1, "expected": 1}, {"check_id": "H175_TARGET_ELEMENTS_2698", "passed": len(axis_rows) == TARGET_ELEMENT_COUNT, "actual": len(axis_rows), "expected": TARGET_ELEMENT_COUNT}, {"check_id": "CERIG_COUNT_UNCHANGED_5078", "passed": int(model_single_difference["modified_command_counts"]["CERIG"]) == EXPECTED_CERIG_COUNT, "actual": int(model_single_difference["modified_command_counts"]["CERIG"]), "expected": EXPECTED_CERIG_COUNT}, {"check_id": "CURRENT_B00_TEMPLATE_HASH", "passed": current_b00_hash == CURRENT_B00_PREPARER_SHA256, "actual": current_b00_hash, "expected": CURRENT_B00_PREPARER_SHA256}, {"check_id": "MAIN_SINGLE_JOB_TRUE_LS2", "passed": bool(main_control_audit["current_template"]["true_ls2_same_solu"]), "actual": bool(main_control_audit["current_template"]["true_ls2_same_solu"]), "expected": True}, {"check_id": "MODAL_UNBOUNDED_80_STRICT", "passed": bool(main_control_audit["current_template"]["unbounded_lanb_80"] and main_control_audit["current_template"]["strict_result_count_80"]), "actual": True, "expected": True}, {"check_id": "MODAL_OUTRES_NSOL_AND_VENG_RESTORED", "passed": bool(energy_audit["outres_all_none_then_nsol_all"] and energy_audit["outres_all_none_then_veng_all"]), "actual": energy_audit["modal_output_order"], "expected": ["OUTRES,ALL,NONE", "OUTRES,NSOL,ALL", "OUTRES,VENG,ALL", "SOLVE"]}, {"check_id": "GATE_BOTTOM_MODAL_SENE_80", "passed": len(energy_audit["energy_exported_modes"]) == REQUESTED_MODES, "actual": len(energy_audit["energy_exported_modes"]), "expected": REQUESTED_MODES}, {"check_id": "MEMORY_GATE_POLICY_RECORDED", "passed": True, "actual": "USER_OVERRIDE" if user_override_memory_gate else "ENFORCED", "expected": "RECORDED_WITH_MEASURED_SNAPSHOT"}, {"check_id": "DISK_GATE_SNAPSHOT_RECORDED", "passed": True, "actual": bool(disk.get("disk_ready")), "expected": "RECORDED_WITHOUT_AUTOSTART"}, {"check_id": "PREPARE_ONLY_NO_EXECUTION", "passed": True, "actual": False, "expected": False}]  # 构造准备期全部硬门禁，包含 VENG 结果链和用户内存覆盖事实但不让资源快照触发执行。
    require(all(bool(check["passed"]) for check in checks), "A10 preflight 存在未通过硬门禁。")  # 写状态前要求所有静态门禁通过。
    preflight = {"schema_version": 1, "run_id": RUN_ID, "generated_utc": created.isoformat(), "status": status_value, "prepare_gate_passed": True, "checks": checks, "memory_snapshot": memory, "disk_snapshot": disk, "measured_resources_ready": measured_resources_ready, "memory_gate_policy": "USER_OVERRIDE" if user_override_memory_gate else "ENFORCED", "memory_gate_overridden_by_user": user_override_memory_gate, "launch_policy_satisfied_after_override": launch_policy_satisfied, "resource_gate_is_nonexecuting": True, "mapdl_execution_attempted": False, "process_started": False, "next_action": next_action_value}  # 汇总静态门禁、实测资源和用户覆盖事实，且不触发执行。
    manifest = {"schema_version": 1, "run_id": RUN_ID, "model_line": MODEL_LINE, "status": status_value, "next_action": next_action_value, "created_utc": created.isoformat(), "run_dir_name": run_name, "run_dir": str(run_dir.resolve()), "jobname": jobname, "jobname_length": len(jobname), "parent_run": B00_RUN_NAME, "parent_delivery_status": delivery_status.get("status"), "units": "N-mm-tonne-s", "coordinate_system": "X longitudinal, Y transverse, Z vertical", "prepare_only": True, "mapdl_execution_attempted": False, "process_started": False, "mapdl_started": False, "execution_policy": "NEVER_EXECUTE_MAPDL_FROM_ULTRA_A10_PREPARE_REGARDLESS_OF_RESOURCE_STATE", "queue_or_autostart_available": False, "memory_gate_policy": "USER_OVERRIDE" if user_override_memory_gate else "ENFORCED", "memory_gate_overridden_by_user": user_override_memory_gate, "measured_resources_ready": measured_resources_ready, "launch_policy_satisfied_after_override": launch_policy_satisfied, "mapdl_executable_from_parent_manifest": mapdl_executable, "mapdl_executable_sha256_from_parent_manifest": mapdl_sha256, "parallel_mode_for_future_launch": "DMP", "processes_for_future_launch": 4, "mpi_for_future_launch": "intelmpi", "memory_snapshot": memory, "disk_snapshot": disk, "dependencies": input_hash_rows, "input_snapshot_inp_count": len(list(input_snapshot_dir.glob("*.inp"))), "solver_prepared_inp_count": len(list(solver_dir.glob("*.inp"))), "main_input": solver_main_path.relative_to(run_dir).as_posix(), "main_input_sha256": a10_main_hash, "axis_include_sha256": modified_axis_hash, "orchestrator_source": str(SCRIPT_PATH), "orchestrator_sha256": copied_a10_preparer_hash, "orchestrator_snapshot": (orchestrator_dir / SCRIPT_PATH.name).relative_to(run_dir).as_posix(), "current_b00_template_source_sha256": current_b00_hash, "physical_change_contract": model_single_difference, "axis_audit_summary": axis_summary, "main_control_flow_audit": main_control_audit, "static_solution_contract": b00_manifest.get("static_solution_contract"), "modal_solution_contract": {"restart": "ANTYPE,,RESTART,2,,PERTURB", "perturb": "PERTURB,MODAL,AUTO,CURRENT,PARKEEP", "eigensolver": "LANB", "modes_requested": REQUESTED_MODES, "frequency_bounds_hz": None, "result_count_must_equal_requested": True, "lumped_mass": False, "mxpand_element_calculation": True, "node_solution_output": "NSOL,ALL", "element_energy_output": "VENG,ALL", "modal_output_order": energy_audit["modal_output_order"], "gate_bottom_modal_sene_output": f"solver/{ENERGY_FILE_STEM}.csv"}, "future_launch": {"status": "NOT_EXECUTED_PREPARED_COMMAND_ONLY", "execution_attempted": False, "memory_gate_policy": "USER_OVERRIDE" if user_override_memory_gate else "ENFORCED", "argv": launch_argv, "launch_command_file": "launch_command.txt"}}  # 构造 A10 根 manifest，完整记录唯一物理变化、VENG 结果链、用户覆盖和未来单作业契约。
    status_payload = {"run_id": RUN_ID, "run_dir_name": run_name, "jobname": jobname, "model_line": MODEL_LINE, "generated_utc": created.isoformat(), "status": status_value, "prepare_gate_passed": True, "mapdl_started": False, "process_started": False, "execution_attempted": False, "memory_ready": bool(memory.get("memory_ready")), "disk_ready": bool(disk.get("disk_ready")), "measured_resources_ready": measured_resources_ready, "memory_gate_policy": "USER_OVERRIDE" if user_override_memory_gate else "ENFORCED", "memory_gate_overridden_by_user": user_override_memory_gate, "launch_policy_satisfied_after_override": launch_policy_satisfied, "next_action": next_action_value}  # 构造根状态对象，区分实测资源与用户覆盖且禁止 READY/RUNNING 值。
    require(status_value not in {"READY", "RUNNING"}, "prepare-only 状态不得声称 READY 或 RUNNING。")  # 双重保护用户要求的资源等待语义。
    write_new_json(run_dir / "manifest.json", manifest)  # 写根机器清单。
    write_new_json(run_dir / "A10_status.json", status_payload)  # 写根准备状态。
    write_new_json(qa_dir / "preflight.json", preflight)  # 写准备硬门禁和资源证据。
    write_new_text(run_dir / "source_hashes.sha256", make_hash_ledger(source_ledger_entries))  # 写 frozen 源与生成输入身份账本。
    write_new_text(run_dir / "result_packet.md", make_result_packet(run_name, jobname, status_value, memory, disk, modified_axis_hash, user_override_memory_gate))  # 写包含 VENG 链和用户覆盖事实的可读准备结果包。
    write_artifact_ledger(run_dir)  # 最后封板 run 内除账本自身外全部文件；此后不得再写。
    return run_dir.resolve()  # 返回已完整封板的新 A10 run 绝对路径。


def validate_optional_run_name(value: str) -> str:  # 输入命令行 run 名并返回已验证原字符串。
    """只接受 A10_H175_AXIS_YYYYMMDDTHHMMSSffffffZ；非法输入交由 argparse 报错。"""  # 函数说明给出输入、输出和格式约束。
    if RUN_NAME_PATTERN.fullmatch(value) is None:  # 格式不匹配时进入 argparse 类型错误路径。
        raise argparse.ArgumentTypeError("run name must match A10_H175_AXIS_YYYYMMDDTHHMMSSffffffZ")  # 给出不含歧义的安全格式说明。
    return value  # 返回保持字节不变的安全目录名。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回受约束命令行参数对象。
    """仅提供可选 run 名与显式内存覆盖记录；不存在 --execute、--queue 或删除参数。"""  # 函数说明强调 CLI 能力边界。
    parser = argparse.ArgumentParser(description="Prepare and audit A10 H175-axis run only; never starts MAPDL and never deletes files.")  # 创建只描述准备职责的解析器。
    parser.add_argument("--run-name", type=validate_optional_run_name, default=None, help="Optional exact A10_H175_AXIS_<UTC-microseconds>Z directory name; default is generated.")  # 提供可复现实验所需的唯一可选参数。
    parser.add_argument("--user-override-memory-gate", action="store_true", help="Record the user's explicit decision to ignore the 8 GiB memory gate; still never starts MAPDL.")  # 只记录用户覆盖事实，不增加任何进程创建能力。
    return parser.parse_args()  # 让 argparse 处理帮助页和非法参数且不创建 run。


def main() -> int:  # 无输入并返回进程退出码，零表示准备证据封板完成。
    """成功只表示 PREPARED；异常返回 2，任何路径都不会调用 MAPDL。"""  # 函数说明区分准备成功与求解成功。
    arguments = parse_arguments()  # 先解析唯一可选 run 名；帮助页在此无副作用退出。
    try:  # 捕获全部源哈希、几何、复制和封板异常并输出单行原因。
        run_dir = prepare_run(arguments.run_name, arguments.user_override_memory_gate)  # 执行只读验证、受控改写和覆盖证据创建，不启动任何进程。
    except Exception as exc:  # 任一 fail-closed 门禁或文件系统异常进入统一失败路径。
        print(f"A10 prepare-only FAILED: {exc}")  # 向标准输出报告具体失败原因，不伪造完成状态。
        return 2  # 非零退出表示没有形成可接受的完整 A10 准备包。
    print(f"A10 prepare-only completed without MAPDL execution: {run_dir}")  # 成功仅报告新 run 路径和未执行事实。
    return 0  # 零退出表示准备与静态审计完成，不表示工程求解通过。


if __name__ == "__main__":  # 只有直接运行脚本时才进入命令行主流程，导入模块不会创建 run。
    raise SystemExit(main())  # 把明确退出码交给操作系统；不存在任何自动重试或后台启动。
