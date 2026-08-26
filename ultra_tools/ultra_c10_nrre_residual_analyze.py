#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格审计 C10 重启诊断产生的 ANSYS NLDIAG/NRRE 节点残差文件。"""

# 导入命令行解析器，用于显式冻结运行目录、源文件和验收参数。
import argparse
# 导入哈希算法，用于给全部输入与发布物生成 SHA-256 审计指纹。
import hashlib
# 导入堆排序工具，用于在九万余节点中稳定提取每次迭代的前若干热点。
import heapq
# 导入 JSON 序列化器，用于发布机器可读的完整审计结论。
import json
# 导入数学函数，用于计算三向力与三向力矩的欧氏范数并检查有限数。
import math
# 导入操作系统接口，用于原子替换发布文件而不留下半写正式报告。
import os
# 导入正则表达式，用于严格识别 APDL、NRRE 头部和节点数据行。
import re
# 导入统计函数，用于计算跨迭代中位数和奇偶迭代模式。
import statistics
# 导入系统接口，用于返回明确的成功或失败退出码。
import sys
# 导入 UTC 时间工具，用于在报告中记录可比较的生成时刻。
from datetime import datetime, timezone
# 导入路径抽象，用于安全处理中文路径和平台分隔符。
from pathlib import Path
# 导入类型标注，用于约束审计数据结构的输入输出语义。
from typing import Any, Iterable

# 固定默认节点数为本诊断数据库声明的 91,407 个残差节点，禁止静默接受截断文件。
DEFAULT_EXPECTED_NODE_COUNT = 91_407
# 固定默认载荷步为迁移阶段第二载荷步，避免把其他阶段的 NRRE 混入本审计。
DEFAULT_EXPECTED_LOAD_STEP = 2
# 固定默认子步为重启后继续求解的第三子步，避免把既有已接受子步误当诊断迭代。
DEFAULT_EXPECTED_SUBSTEP = 3
# 固定默认时间为重启文件记录的 1.000002，无量纲伪时间只用于身份核验。
DEFAULT_EXPECTED_TIME = 1.000002
# 固定时间比较绝对容差为 1E-9，覆盖文本舍入但拒绝相邻分析时刻。
DEFAULT_TIME_TOLERANCE = 1.0e-9
# 固定每次迭代输出 50 个力热点和 50 个力矩热点，以满足定位要求且控制报告体积。
DEFAULT_TOP_N = 50
# 固定跨迭代候选热点上限为 200 个节点，用于呈现频次、峰值和中位数。
DEFAULT_CROSS_TOP_N = 200
# 固定文本编码为 UTF-8；APDL 中文注释和本工具发布物均按该编码解释。
TEXT_ENCODING = "utf-8"
# 固定 NRRE 文件名规则为三位迭代编号，防止误读结果库或临时文件。
NR_FILE_PATTERN = re.compile(r"^(?P<job>.+)\.nr(?P<index>\d{3})$", re.IGNORECASE)
# 固定 NRRE 第二行规则并捕获文件名、残差范数 CNVV 与收敛阈值 CNVC。
NR_STATUS_PATTERN = re.compile(
    r"^\s*File written with name\s*=\s*(?P<name>\S+)\s+CNVV\s*=\s*(?P<cnvv>[+\-0-9.Ee]+)\s+CNVC\s*=\s*(?P<cnvc>[+\-0-9.Ee]+)\s*$"
)
# 固定 APDL 节点定义规则并捕获节点号及全局 X/Y/Z 坐标，单位继承模型的 mm。
NODE_PATTERN = re.compile(
    r"^\s*N\s*,\s*(?P<node>\d+)\s*,\s*(?P<x>[+\-0-9.Ee]+)\s*,\s*(?P<y>[+\-0-9.Ee]+)\s*,\s*(?P<z>[+\-0-9.Ee]+)"
)
# 固定 APDL 单元类型选择规则，用于仅解析 TYPE72/MPC184 主从连接。
TYPE_PATTERN = re.compile(r"^\s*TYPE\s*,\s*(?P<type>\d+)\b", re.IGNORECASE)
# 固定 TYPE72 两节点 EN 规则，并保留行尾注释供连接模式和装配身份解析。
CONNECTION_PATTERN = re.compile(
    r"^\s*EN\s*,\s*(?P<element>\d+)\s*,\s*(?P<master>\d+)\s*,\s*(?P<slave>\d+)\s*!\s*(?P<comment>.+?)\s*$",
    re.IGNORECASE,
)
# 固定连接逻辑编号规则，用于建立 APDL 元素与 C10-CONN 证据编号的一对一映射。
CONNECTION_ID_PATTERN = re.compile(r"\b(C10-CONN-\d+)\b", re.IGNORECASE)
# 固定刚接自由度模式规则，ALL 表示六自由度，UXYZ 表示仅平移语义。
CONNECTION_MODE_PATTERN = re.compile(r"(?:^|[^A-Z])(ALL|UXYZ)(?:[^A-Z]|$)", re.IGNORECASE)
# 固定装配字段规则，用于提取 CW*_GATE_## 等工程装配标识。
ASSEMBLY_PATTERN = re.compile(r"装配\s*=\s*([A-Za-z0-9_\-]+)", re.IGNORECASE)
# 固定门架序号规则，用于从 CW1_GATE_03 等精确装配名提取门架序号 03。
GATE_NUMBER_PATTERN = re.compile(r"_GATE_(\d+)\b", re.IGNORECASE)
# 固定 Hxx 构件组规则；H03 是独立构件组身份，绝不能由 GATE_03 猜测或替代。
HXX_ASSEMBLY_PATTERN = re.compile(r"^H(?P<number>\d+)$", re.IGNORECASE)
# 固定迁移修正力规则，捕获节点号与 C10_BETA 乘数内的基准 FZ，单位为 N。
MIGRATION_FORCE_PATTERN = re.compile(
    r"^\s*F\s*,\s*(?P<node>\d+)\s*,\s*FZ\s*,\s*C10_BETA\s*\*\s*\(\s*(?P<value>[+\-0-9.Ee]+)\s*\)\s*(?:!.*)?$",
    re.IGNORECASE,
)


# 定义专用异常类型，使格式错误、文件竞态和证据冲突以一致方式终止发布。
class AuditError(RuntimeError):
    """表示输入不完整、不一致或不满足冻结诊断契约。"""


# 计算指定文件的 SHA-256，并按二进制块读取以支持数 GB 证据文件。
def sha256_file(path: Path) -> str:
    """输入 path 为现存普通文件；返回其 64 位小写 SHA-256 十六进制字符串。"""
    # 创建 SHA-256 累加器，算法名称固定以便跨平台复核。
    digest = hashlib.sha256()
    # 以只读二进制方式打开文件，避免换行或编码转换改变指纹。
    with path.open("rb") as handle:
        # 持续读取固定 1 MiB 数据块，在内存与吞吐之间保持稳健平衡。
        while True:
            # 读取 1,048,576 字节；该字面值等于 1 MiB，不代表工程单位。
            block = handle.read(1_048_576)
            # 当返回空字节串时表示已到文件末尾，应结束哈希循环。
            if not block:
                # 退出当前读取循环，保留已经累计的全部字节。
                break
            # 将本块原始字节加入哈希，确保任何一位变化都会改变指纹。
            digest.update(block)
    # 返回最终十六进制摘要，供 JSON、Markdown 和清单共同引用。
    return digest.hexdigest()


# 将有限浮点值转换为统一科学计数法文本，便于 Markdown 中跨量级比较。
def scientific(value: float) -> str:
    """输入 value 为有限浮点数；返回保留六位小数的科学计数法字符串。"""
    # 使用六位小数兼顾定位精度与表格可读性，单位由调用表头明确给出。
    return f"{value:.6e}"


# 把内容原子发布到目标路径，确保正式文件要么是旧版完整文件要么是新版完整文件。
def atomic_write_text(path: Path, content: str) -> None:
    """输入 path 为发布路径、content 为完整 UTF-8 文本；成功时无返回值。"""
    # 确保目标父目录存在；该目录属于本次专用诊断运行的 qa 区域。
    path.parent.mkdir(parents=True, exist_ok=True)
    # 构造同目录临时文件名，使最终替换在同一文件系统中具备原子语义。
    temporary_path = path.with_name(f".{path.name}.tmp")
    # 以 UTF-8 和 LF 换行写出完整内容，避免平台默认编码污染中文证据。
    temporary_path.write_text(content, encoding=TEXT_ENCODING, newline="\n")
    # 原子替换正式路径；仅覆盖本工具自己的派生报告，不修改任何求解器文件。
    os.replace(temporary_path, path)


# 读取 UTF-8 源文件，同时确认读取期间文件大小和修改时间没有变化。
def stable_read_text(path: Path, encoding: str) -> tuple[str, os.stat_result]:
    """输入 path 与编码；返回稳定文本和读取前状态，若文件在读取时变化则拒绝。"""
    # 在读取前获取精确文件状态，作为半写或并发变更检测基线。
    before = path.stat()
    # 按指定编码严格解码全部文本，编码错误不得替换或忽略。
    text = path.read_text(encoding=encoding, errors="strict")
    # 在读取后再次获取文件状态，以发现求解器正在追加或替换文件的情况。
    after = path.stat()
    # 同时比较大小和纳秒修改时间；任一变化都意味着当前快照不可审计。
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        # 抛出明确异常并拒绝发布，调用者稍后可在文件稳定后原样重跑。
        raise AuditError(f"文件读取期间发生变化，疑似仍在写入：{path}")
    # 返回完整文本与稳定状态，供上层记录大小和时间证据。
    return text, before


# 对装配标识进行无猜测分类，严格区分 CW*_GATE_## 门架和独立 Hxx 构件组。
def classify_assembly(assembly: str | None) -> dict[str, Any]:
    """输入可空装配名；返回类别、门架序号/标签和独立 Hxx 身份，禁止二者互推。"""
    # 无装配字段时返回明确 unknown 分类，禁止从节点号或坐标猜测。
    if assembly is None:
        # 返回全部可选身份为空的稳定结构。
        return {"assembly_kind": "unknown", "gate_index": None, "gate_label": None, "hxx": None}
    # 搜索 CW*_GATE_## 名称中的门架序号；精确装配原名仍在连接记录单独保存。
    gate_match = GATE_NUMBER_PATTERN.search(assembly)
    # 命中门架序号时仅生成 GATE_## 标签，不错误映射为 H##。
    if gate_match is not None:
        # 将门架编号解析为整数，便于数值排序和跨猫道同号对照。
        gate_index = int(gate_match.group(1))
        # 返回 gate 分类及至少两位的 GATE_## 可读标签。
        return {"assembly_kind": "gate", "gate_index": gate_index, "gate_label": f"GATE_{gate_index:02d}", "hxx": None}
    # 尝试把完整装配名识别为独立 Hxx 构件组。
    hxx_match = HXX_ASSEMBLY_PATTERN.fullmatch(assembly)
    # 命中 Hxx 时保留其规范大写身份，不与任何门架序号绑定。
    if hxx_match is not None:
        # 将 H 编号规范为至少两位，例如 H3 规范为 H03。
        hxx = f"H{int(hxx_match.group('number')):02d}"
        # 返回 hxx 分类，门架字段保持空值。
        return {"assembly_kind": "hxx", "gate_index": None, "gate_label": None, "hxx": hxx}
    # 其他装配保持 other 分类，其精确原名仍足以回投源文件。
    return {"assembly_kind": "other", "gate_index": None, "gate_label": None, "hxx": None}


# 解析门架/通道 APDL，建立节点坐标与 TYPE72 主从连接的可追溯索引。
def parse_gate_input(path: Path) -> dict[str, Any]:
    """输入门架 APDL 路径；返回坐标、连接、节点角色及源文件元数据。"""
    # 稳定读取 UTF-8-SIG 以兼容有无 BOM 的中文 APDL 源文件。
    text, state = stable_read_text(path, "utf-8-sig")
    # 初始化节点坐标表，键为节点号，值为模型全局坐标 mm。
    coordinates: dict[int, list[float]] = {}
    # 初始化 TYPE72 连接列表，每项保存元素、主从、模式与工程装配证据。
    connections: list[dict[str, Any]] = []
    # 初始化当前 APDL TYPE；只有明确 TYPE,72 后的 EN 才能被解释为 MPC184。
    current_type: int | None = None
    # 按物理行扫描源文件并保留一基行号，便于报告回投原始证据。
    for line_number, line in enumerate(text.splitlines(), start=1):
        # 尝试解析节点定义，源文件内每个新增节点必须保持唯一坐标。
        node_match = NODE_PATTERN.match(line)
        # 命中节点行时读取节点号和三向坐标。
        if node_match is not None:
            # 将节点标识转换为整数，作为后续残差映射的稳定主键。
            node_id = int(node_match.group("node"))
            # 将 X/Y/Z 转换为浮点数，单位为模型冻结的 mm。
            coordinate = [float(node_match.group(axis)) for axis in ("x", "y", "z")]
            # 若同一节点重复定义且坐标不同，则源证据本身冲突，必须拒绝。
            if node_id in coordinates and coordinates[node_id] != coordinate:
                # 抛出带节点和行号的异常，避免静默采用后定义覆盖前定义。
                raise AuditError(f"门架 APDL 节点 {node_id} 在第 {line_number} 行重复且坐标冲突")
            # 保存或确认该节点坐标，供热点报告给出空间定位。
            coordinates[node_id] = coordinate
        # 尝试解析单元类型选择，更新后续 EN 行的解释上下文。
        type_match = TYPE_PATTERN.match(line)
        # 命中 TYPE 行时以其整数编号替换当前类型。
        if type_match is not None:
            # TYPE 号 72 代表本模型的 MPC184；其他编号会阻止误收普通梁/索单元。
            current_type = int(type_match.group("type"))
            # TYPE 行不可能同时是 EN 行，直接进入下一物理行减少歧义。
            continue
        # 仅在当前类型明确为 72 时尝试解析两节点连接。
        if current_type != 72:
            # 跳过普通 BEAM188、LINK180 等 EN 行，它们不属于主从约束证据。
            continue
        # 解析 TYPE72 的两节点 EN 行及其工程注释。
        connection_match = CONNECTION_PATTERN.match(line)
        # 非 EN 或没有审计注释的行不进入连接清单。
        if connection_match is None:
            # 继续扫描下一行；文件中的 TYPE72 定义行等属于预期情况。
            continue
        # 保存完整注释文本，后续分别提取连接号、模式和装配。
        comment = connection_match.group("comment").strip()
        # 从注释中提取唯一 C10-CONN 逻辑编号。
        connection_id_match = CONNECTION_ID_PATTERN.search(comment)
        # 缺少逻辑编号会破坏一对一回投，因此严格拒绝该 TYPE72 连接。
        if connection_id_match is None:
            # 抛出带物理行号的异常，要求源文件补齐工程语义。
            raise AuditError(f"TYPE72 EN 第 {line_number} 行缺少 C10-CONN 编号")
        # 从注释中提取 ALL 或 UXYZ 自由度语义。
        mode_match = CONNECTION_MODE_PATTERN.search(comment)
        # 缺少模式时无法判断六自由度刚接与平移连接，必须拒绝。
        if mode_match is None:
            # 抛出明确异常而非凭节点自由度推断连接模式。
            raise AuditError(f"TYPE72 EN 第 {line_number} 行缺少 ALL/UXYZ 模式")
        # 从注释中提取装配身份；允许少数非门架连接暂时无装配字段。
        assembly_match = ASSEMBLY_PATTERN.search(comment)
        # 将存在的装配字段保存为原字符串，不存在则记录空值。
        assembly = assembly_match.group(1) if assembly_match is not None else None
        # 对装配进行无猜测分类，严格区分门架与独立 Hxx 构件组。
        assembly_identity = classify_assembly(assembly)
        # 组装一条完整连接记录，节点顺序遵循 MPC184 EN 的主节点在前、从节点在后。
        connection = {
            # 保存 APDL 元素号作为求解器实体身份。
            "element_id": int(connection_match.group("element")),
            # 保存逻辑连接号作为工程证据身份。
            "connection_id": connection_id_match.group(1).upper(),
            # 保存第一个节点为 master，符合本生成器和项目注释契约。
            "master_node": int(connection_match.group("master")),
            # 保存第二个节点为 slave，符合本生成器和项目注释契约。
            "slave_node": int(connection_match.group("slave")),
            # 规范化连接模式为大写 ALL 或 UXYZ。
            "mode": mode_match.group(1).upper(),
            # 保存精确装配名用于跨 CW1/CW2 等体系区分同号门架。
            "assembly": assembly,
            # 保存装配类别 gate、hxx、other 或 unknown。
            "assembly_kind": assembly_identity["assembly_kind"],
            # 保存可选门架整数序号，Hxx 连接不得填入该字段。
            "gate_index": assembly_identity["gate_index"],
            # 保存可选 GATE_## 标签，严格不使用 H 前缀。
            "gate_label": assembly_identity["gate_label"],
            # 保存可选独立 Hxx 构件组身份，门架连接不得填入该字段。
            "hxx": assembly_identity["hxx"],
            # 保存源 APDL 一基行号，便于直接回投检查。
            "source_line": line_number,
        }
        # 将本连接追加到保持源顺序的清单中。
        connections.append(connection)
    # 源文件必须至少包含一个节点和一个 TYPE72，否则很可能选错 include。
    if not coordinates or not connections:
        # 抛出包含实际计数的异常，阻止无映射报告发布。
        raise AuditError(f"门架 APDL 缺少必要内容：节点={len(coordinates)}，TYPE72={len(connections)}")
    # 初始化节点角色索引，单个节点可以同时出现在多条连接或不同角色中。
    roles: dict[int, list[dict[str, Any]]] = {}
    # 遍历每条连接，为 master 和 slave 两端分别建立对称角色记录。
    for connection in connections:
        # 为主节点建立指向从节点的角色证据。
        master_role = {
            # 标记本端在 TYPE72 中承担 master 角色。
            "role": "master",
            # 保存对端从节点号，便于残差对称配对。
            "partner_node": connection["slave_node"],
            # 保存求解器元素号。
            "element_id": connection["element_id"],
            # 保存工程连接编号。
            "connection_id": connection["connection_id"],
            # 保存自由度连接模式。
            "mode": connection["mode"],
            # 保存精确装配标识。
            "assembly": connection["assembly"],
            # 保存装配类别。
            "assembly_kind": connection["assembly_kind"],
            # 保存可选门架序号。
            "gate_index": connection["gate_index"],
            # 保存可选门架标签。
            "gate_label": connection["gate_label"],
            # 保存可选独立 Hxx 构件组身份。
            "hxx": connection["hxx"],
            # 保存 APDL 证据行号。
            "source_line": connection["source_line"],
        }
        # 为从节点建立指向主节点的镜像角色证据。
        slave_role = {
            # 标记本端在 TYPE72 中承担 slave 角色。
            "role": "slave",
            # 保存对端主节点号，便于残差对称配对。
            "partner_node": connection["master_node"],
            # 保存求解器元素号。
            "element_id": connection["element_id"],
            # 保存工程连接编号。
            "connection_id": connection["connection_id"],
            # 保存自由度连接模式。
            "mode": connection["mode"],
            # 保存精确装配标识。
            "assembly": connection["assembly"],
            # 保存装配类别。
            "assembly_kind": connection["assembly_kind"],
            # 保存可选门架序号。
            "gate_index": connection["gate_index"],
            # 保存可选门架标签。
            "gate_label": connection["gate_label"],
            # 保存可选独立 Hxx 构件组身份。
            "hxx": connection["hxx"],
            # 保存 APDL 证据行号。
            "source_line": connection["source_line"],
        }
        # 将主节点角色追加到该节点的角色列表。
        roles.setdefault(connection["master_node"], []).append(master_role)
        # 将从节点角色追加到该节点的角色列表。
        roles.setdefault(connection["slave_node"], []).append(slave_role)
    # 汇总 ALL 与 UXYZ 数量，用于核验连接语义规模。
    mode_counts = {mode: sum(1 for item in connections if item["mode"] == mode) for mode in ("ALL", "UXYZ")}
    # 返回解析结果及源文件稳定元数据。
    return {
        # 保存源文件绝对路径。
        "path": str(path.resolve()),
        # 保存源文件字节数。
        "size_bytes": state.st_size,
        # 保存源文件 SHA-256。
        "sha256": sha256_file(path),
        # 保存全部新增节点坐标。
        "coordinates": coordinates,
        # 保存全部 TYPE72 连接记录。
        "connections": connections,
        # 保存按节点索引的主从角色。
        "roles": roles,
        # 保存连接模式计数。
        "mode_counts": mode_counts,
    }


# 解析载荷位置迁移 APDL，建立 15,071 个节点基准 FZ 修正值索引。
def parse_migration_input(path: Path) -> dict[str, Any]:
    """输入迁移 APDL 路径；返回节点到基准 FZ 修正值及源文件元数据。"""
    # 稳定读取 UTF-8-SIG，以严格保留中文注释并检测并发改写。
    text, state = stable_read_text(path, "utf-8-sig")
    # 初始化节点修正表，单位固定为 N。
    corrections: dict[int, float] = {}
    # 扫描每一物理行并保留一基行号，用于发现重复修正。
    for line_number, line in enumerate(text.splitlines(), start=1):
        # 尝试匹配 C10_BETA 乘基准 FZ 的正式命令行。
        match = MIGRATION_FORCE_PATTERN.match(line)
        # 非迁移 FZ 命令直接跳过。
        if match is None:
            # 继续处理下一行，避免将注释或控制命令误计为修正节点。
            continue
        # 将节点号转换为整数主键。
        node_id = int(match.group("node"))
        # 将基准修正值转换为浮点数，单位为 N。
        value = float(match.group("value"))
        # 要求修正值有限，拒绝 NaN 或无穷大污染统计。
        if not math.isfinite(value):
            # 抛出含节点和行号的异常，便于定位生成器错误。
            raise AuditError(f"迁移 APDL 第 {line_number} 行节点 {node_id} 的 FZ 非有限")
        # 同一节点出现两条正式修正会造成 APDL 替换语义歧义，严格拒绝。
        if node_id in corrections:
            # 抛出重复节点异常，禁止后值静默覆盖前值。
            raise AuditError(f"迁移 APDL 节点 {node_id} 在第 {line_number} 行重复定义")
        # 保存该节点完整 beta=1 基准修正力。
        corrections[node_id] = value
    # 修正表不得为空，否则说明选错文件或正则与正式格式不一致。
    if not corrections:
        # 抛出明确异常，避免发布全部节点均“无修正”的伪结论。
        raise AuditError("迁移 APDL 未解析到任何 C10_BETA*FZ 修正命令")
    # 统计正、负、零修正节点数，帮助识别增载与卸载两类路径。
    sign_counts = {
        # 正值表示 beta=1 时在该节点施加向 +Z 的基准修正。
        "positive": sum(1 for value in corrections.values() if value > 0.0),
        # 负值表示 beta=1 时在该节点施加向 -Z 的基准修正。
        "negative": sum(1 for value in corrections.values() if value < 0.0),
        # 零值保留用于识别无实际贡献但被写入的异常节点。
        "zero": sum(1 for value in corrections.values() if value == 0.0),
    }
    # 返回修正索引和源文件证据。
    return {
        # 保存源文件绝对路径。
        "path": str(path.resolve()),
        # 保存源文件字节数。
        "size_bytes": state.st_size,
        # 保存源文件 SHA-256。
        "sha256": sha256_file(path),
        # 保存全部节点修正值。
        "corrections": corrections,
        # 保存修正符号计数。
        "sign_counts": sign_counts,
    }


# 解析 MAPDL 捕获输出并记录自然终止签名，不对运行中进程发送任何控制信号。
def parse_solver_output(path: Path, solver_dir: Path, require_terminated: bool) -> dict[str, Any]:
    """输入求解输出、solver 目录和终态要求；返回终止签名、锁状态及源文件证据。"""
    # 以单字节 Latin-1 稳定读取 MAPDL 输出；中文路径字节可无损保留且英文签名仍按 ASCII 等值匹配。
    text, state = stable_read_text(path, "latin-1")
    # 按物理行拆分，同时保留一基行号便于回投终止证据。
    numbered_lines = list(enumerate(text.splitlines(), start=1))
    # 固定终止相关关键词，覆盖原生迭代上限、未收敛、错误和正常退出摘要。
    signature_terms = (
        # 捕获 MAPDL 错误标题。
        "*** ERROR ***",
        # 捕获平衡迭代数上限说明。
        "NUMBER OF EQUILIBRIUM ITERATIONS",
        # 捕获所有明确终止措辞。
        "TERMINAT",
        # 捕获收敛失败措辞。
        "CONVERGENCE FAILURE",
        # 捕获未收敛解措辞。
        "NOT CONVERGED",
        # 捕获错误计数摘要。
        "NUMBER OF ERRORS ENCOUNTERED",
        # 捕获 ANSYS 运行完成摘要。
        "ANSYS RUN COMPLETED",
    )
    # 初始化终止签名行列表，每项保留行号和去除首尾空白的原文。
    signature_lines: list[dict[str, Any]] = []
    # 扫描全部输出行并按大写文本匹配冻结关键词。
    for line_number, line in numbered_lines:
        # 将当前行规范为大写，仅用于不区分大小写的关键词判断。
        upper_line = line.upper()
        # 命中任一关键词时保存原文和行号。
        if any(term in upper_line for term in signature_terms):
            # 追加终止相关证据；空白缩进不影响语义。
            signature_lines.append({"line_number": line_number, "text": line.strip()})
    # 枚举当前 solver 目录所有 .lock 文件；非空列表表示求解仍可能在运行。
    lock_files = sorted(path_item.name for path_item in solver_dir.glob("*.lock") if path_item.is_file())
    # 将全文规范为大写，便于组合判断原生迭代上限签名。
    upper_text = text.upper()
    # 捕获 NCNV 累计迭代上限的精确数值，例如“number of iterations exceeds 105”。
    cumulative_limit_match = re.search(r"NUMBER OF ITERATIONS EXCEEDS\s+(?P<limit>\d+)", upper_text)
    # 判断 NEQIT 类平衡迭代上限签名，要求同时出现限制语义和 MAPDL 错误标题。
    equilibrium_iteration_limit_detected = (
        # 要求出现平衡迭代数措辞。
        "NUMBER OF EQUILIBRIUM ITERATIONS" in upper_text
        # 要求出现 LIMIT 或 MAXIMUM 词根，区分普通迭代日志。
        and ("LIMIT" in upper_text or "MAXIMUM" in upper_text)
        # 要求出现标准错误标题，证明求解器而非外部监视器结束运行。
        and "*** ERROR ***" in upper_text
    )
    # 判断 NCNV 类累计迭代上限签名，要求超限句与运行终止句同时出现。
    cumulative_iteration_limit_detected = (
        # 要求成功捕获“迭代数超过数值”语义。
        cumulative_limit_match is not None
        # 要求同一输出明确写出运行被终止。
        and "THE RUN IS TERMINATED" in upper_text
        # 要求出现标准错误标题，排除人工注释或预期说明。
        and "*** ERROR ***" in upper_text
    )
    # 原生迭代上限只需满足 NEQIT 或 NCNV 两种正式求解器签名之一。
    native_iteration_limit_detected = (
        # 接受 NEQIT 当前子步平衡迭代上限。
        equilibrium_iteration_limit_detected
        # 或接受 NCNV 累计迭代数上限。
        or cumulative_iteration_limit_detected
    )
    # 最终自然终止要求无锁文件且已捕获原生迭代上限错误。
    final_native_termination = not lock_files and native_iteration_limit_detected
    # 当调用者要求终态时，任何锁文件或缺失签名都必须阻止正式报告更新。
    if require_terminated and not final_native_termination:
        # 抛出包含锁和签名判断的异常，提示稍后在自然退出后原样重跑。
        raise AuditError(f"尚未形成原生迭代上限终态：lock={lock_files}，native_limit={native_iteration_limit_detected}")
    # 提取最后 80 个非空输出行作为终态上下文，数量足以覆盖错误和运行摘要。
    nonempty_lines = [{"line_number": line_number, "text": line.strip()} for line_number, line in numbered_lines if line.strip()]
    # 截取末尾 80 行；若总行数不足则保留全部。
    tail_context = nonempty_lines[-80:]
    # 返回求解输出证据和终态判断。
    return {
        # 保存绝对输出路径。
        "path": str(path.resolve()),
        # 保存字节数。
        "size_bytes": state.st_size,
        # 保存 SHA-256。
        "sha256": sha256_file(path),
        # 保存读取时存在的锁文件名。
        "lock_files_at_audit": lock_files,
        # 保存是否检测到 MAPDL 原生迭代上限错误组合签名。
        "native_iteration_limit_detected": native_iteration_limit_detected,
        # 保存是否检测到 NEQIT 类平衡迭代上限签名。
        "equilibrium_iteration_limit_detected": equilibrium_iteration_limit_detected,
        # 保存是否检测到 NCNV 类累计迭代上限签名。
        "cumulative_iteration_limit_detected": cumulative_iteration_limit_detected,
        # 保存从 NCNV 终止句解析出的累计迭代上限；未命中时为空。
        "cumulative_iteration_limit": int(cumulative_limit_match.group("limit")) if cumulative_limit_match is not None else None,
        # 保存是否达到无锁且原生终止的最终状态。
        "final_native_termination": final_native_termination,
        # 保存所有终止相关原始行。
        "termination_signature_lines": signature_lines,
        # 保存末尾上下文以支持独立复核。
        "tail_context": tail_context,
    }


# 解析一个完整 NRRE 文件并严格核验头部、节点数、唯一性和读取稳定性。
def parse_nr_file(
    path: Path,
    expected_node_count: int,
    expected_load_step: int,
    expected_substep: int,
    expected_time: float,
    time_tolerance: float,
) -> dict[str, Any]:
    """输入 NRRE 文件及冻结期望值；返回头部、每节点范数和源文件证据。"""
    # 先核验文件名并提取三位迭代编号。
    filename_match = NR_FILE_PATTERN.match(path.name)
    # 非标准 nrNNN 文件不应进入本函数。
    if filename_match is None:
        # 抛出文件名错误，防止报告无法关联求解器迭代。
        raise AuditError(f"NRRE 文件名不符合 .nrNNN 规则：{path.name}")
    # 将文件名三位编号转换为整数迭代号。
    filename_iteration = int(filename_match.group("index"))
    # 以 ASCII 严格读取数值文件，并确认读取期间未发生增长或改写。
    text, state = stable_read_text(path, "ascii")
    # 按物理行拆分；ANSYS 正式格式固定为四行头部加每节点一行。
    lines = text.splitlines()
    # 计算严格期望总行数，四行头部加冻结节点数。
    expected_line_count = expected_node_count + 4
    # 行数不等通常意味着求解器仍在写入或文件截断，必须拒绝本次全报告发布。
    if len(lines) != expected_line_count:
        # 抛出同时含实际与期望行数的异常，调用者可等待稳定后重跑。
        raise AuditError(f"NRRE 文件疑似半写或截断：{path.name} 行数={len(lines)}，期望={expected_line_count}")
    # 第一行必须声明 ANSYS RELEASE，确认来源为求解器诊断文件。
    if not lines[0].startswith("/COM,ANSYS RELEASE "):
        # 拒绝没有标准发布头的文本，避免误读人工或其他格式文件。
        raise AuditError(f"NRRE 第一行缺少 ANSYS RELEASE：{path.name}")
    # 严格解析第二行的文件名、CNVV 和 CNVC。
    status_match = NR_STATUS_PATTERN.match(lines[1])
    # 第二行不符合格式时无法确认残差范数与收敛阈值。
    if status_match is None:
        # 抛出头部格式错误并停止发布。
        raise AuditError(f"NRRE 第二行格式错误：{path.name}")
    # 头部声明文件名必须与磁盘文件名逐字一致。
    if status_match.group("name").lower() != path.name.lower():
        # 拒绝复制错名或内容错配文件。
        raise AuditError(f"NRRE 头部文件名与磁盘名不一致：{path.name}")
    # 第三行必须恰有节点数、时间、载荷步、子步、平衡迭代五列。
    header_tokens = lines[2].split()
    # 列数不是五说明格式变体或写入不完整。
    if len(header_tokens) != 5:
        # 抛出第三行列数异常。
        raise AuditError(f"NRRE 第三行列数不是 5：{path.name}")
    # 将头部五列按冻结类型转换。
    declared_node_count = int(header_tokens[0])
    # 将求解时刻转换为浮点数。
    result_time = float(header_tokens[1])
    # 将载荷步号转换为整数。
    load_step = int(header_tokens[2])
    # 将子步号转换为整数。
    substep = int(header_tokens[3])
    # 将平衡迭代号转换为整数。
    equilibrium_iteration = int(header_tokens[4])
    # 头部节点数必须等于冻结的 91,407。
    if declared_node_count != expected_node_count:
        # 拒绝节点数据库规模不一致的文件。
        raise AuditError(f"NRRE 节点数错误：{path.name}={declared_node_count}，期望={expected_node_count}")
    # 载荷步和子步必须与本重启诊断契约一致。
    if load_step != expected_load_step or substep != expected_substep:
        # 拒绝混入其他分析阶段。
        raise AuditError(f"NRRE 阶段错误：{path.name} LS={load_step} SS={substep}")
    # 伪时间必须在冻结绝对容差内一致。
    if not math.isclose(result_time, expected_time, rel_tol=0.0, abs_tol=time_tolerance):
        # 拒绝相邻或其他时刻的诊断结果。
        raise AuditError(f"NRRE 时间错误：{path.name} time={result_time}，期望={expected_time}")
    # 文件名编号必须等于头部平衡迭代号，防止重命名后次序错乱。
    if equilibrium_iteration != filename_iteration:
        # 抛出迭代身份冲突。
        raise AuditError(f"NRRE 文件编号与头部迭代不一致：{path.name} header={equilibrium_iteration}")
    # 第四行必须严格声明六个残差分量列号 1 至 6。
    if lines[3].split() != ["1", "2", "3", "4", "5", "6"]:
        # 拒绝列顺序或列数变化，以免错误计算范数。
        raise AuditError(f"NRRE 分量列头不是 1..6：{path.name}")
    # 初始化节点范数表，键为节点号，值含力范数与力矩范数。
    values: dict[int, tuple[float, float]] = {}
    # 从第五物理行开始逐节点解析六个分量。
    for data_line_number, line in enumerate(lines[4:], start=5):
        # 按空白切分节点号及 Fx/Fy/Fz/Mx/My/Mz 七列。
        tokens = line.split()
        # 每节点必须恰有七列，拒绝截断或额外列。
        if len(tokens) != 7:
            # 抛出带文件和物理行号的格式错误。
            raise AuditError(f"NRRE 数据列数错误：{path.name}:{data_line_number}")
        # 第一列解析为唯一节点号。
        node_id = int(tokens[0])
        # 后六列解析为浮点残差分量，前三为 N、后三为 N·mm。
        components = [float(token) for token in tokens[1:]]
        # 六分量必须全部有限，拒绝 NaN 或无穷大。
        if not all(math.isfinite(value) for value in components):
            # 抛出节点级非有限值异常。
            raise AuditError(f"NRRE 存在非有限分量：{path.name}:{data_line_number} 节点={node_id}")
        # 同一 NRRE 文件节点号必须唯一。
        if node_id in values:
            # 抛出重复节点异常，禁止静默覆盖。
            raise AuditError(f"NRRE 节点重复：{path.name} 节点={node_id}")
        # 计算前三分量的欧氏力范数，单位 N。
        force_norm = math.sqrt(sum(value * value for value in components[:3]))
        # 计算后三分量的欧氏力矩范数，单位 N·mm。
        moment_norm = math.sqrt(sum(value * value for value in components[3:]))
        # 保存节点的两个范数，原始六分量不进入报告以控制体积。
        values[node_id] = (force_norm, moment_norm)
    # 再次核验唯一节点数，覆盖空行或重复等边界情况。
    if len(values) != expected_node_count:
        # 拒绝任何未达到冻结节点规模的数据集。
        raise AuditError(f"NRRE 唯一节点数错误：{path.name}={len(values)}")
    # 将 CNVV 转换为有限浮点数。
    cnvv = float(status_match.group("cnvv"))
    # 将 CNVC 转换为有限浮点数。
    cnvc = float(status_match.group("cnvc"))
    # 两个收敛量必须有限且阈值为正。
    if not math.isfinite(cnvv) or not math.isfinite(cnvc) or cnvc <= 0.0:
        # 拒绝无意义的收敛头部。
        raise AuditError(f"NRRE CNVV/CNVC 非法：{path.name}")
    # 返回严格解析结果和文件证据。
    return {
        # 保存绝对路径。
        "path": str(path.resolve()),
        # 保存文件名。
        "name": path.name,
        # 保存文件字节数。
        "size_bytes": state.st_size,
        # 保存文件 SHA-256。
        "sha256": sha256_file(path),
        # 保存标准 ANSYS 发布头。
        "release_line": lines[0],
        # 保存结果时间。
        "time": result_time,
        # 保存载荷步号。
        "load_step": load_step,
        # 保存子步号。
        "substep": substep,
        # 保存平衡迭代号。
        "equilibrium_iteration": equilibrium_iteration,
        # 保存节点数。
        "node_count": declared_node_count,
        # 保存求解器残差范数 CNVV。
        "cnvv": cnvv,
        # 保存求解器收敛阈值 CNVC。
        "cnvc": cnvc,
        # 保存节点到力/力矩范数的映射。
        "values": values,
    }


# 为一个残差节点合并几何、TYPE72 和载荷迁移分类证据。
def annotate_node(node_id: int, gate: dict[str, Any], migration: dict[str, Any]) -> dict[str, Any]:
    """输入节点号及两个源索引；返回可 JSON 序列化的工程分类与映射。"""
    # 从门架新增节点坐标表中读取可选坐标。
    coordinate = gate["coordinates"].get(node_id)
    # 从 TYPE72 角色索引读取该节点涉及的全部连接。
    roles = gate["roles"].get(node_id, [])
    # 从迁移修正表读取可选基准 FZ 值。
    correction = migration["corrections"].get(node_id)
    # 初始化分类标签列表，并按固定顺序追加以保证报告可复现。
    categories: list[str] = []
    # 门架 include 内显式定义的节点标为 gate_geometry_node。
    if coordinate is not None:
        # 追加几何节点标签。
        categories.append("gate_geometry_node")
    # 参与任一 TYPE72 的节点标为 type72_node。
    if roles:
        # 追加 MPC184 节点标签。
        categories.append("type72_node")
    # 若至少一条角色为 master，则追加主节点标签。
    if any(role["role"] == "master" for role in roles):
        # 追加 TYPE72 master 标签。
        categories.append("type72_master")
    # 若至少一条角色为 slave，则追加从节点标签。
    if any(role["role"] == "slave" for role in roles):
        # 追加 TYPE72 slave 标签。
        categories.append("type72_slave")
    # 若涉及 ALL 六自由度连接，则单独标记以区分 UXYZ。
    if any(role["mode"] == "ALL" for role in roles):
        # 追加 ALL 六自由度刚接标签。
        categories.append("type72_all")
    # 若涉及 UXYZ 平移连接，则单独标记。
    if any(role["mode"] == "UXYZ" for role in roles):
        # 追加 UXYZ 平移连接标签。
        categories.append("type72_uxyz")
    # 迁移修正表中的节点标记为 migration_correction_node。
    if correction is not None:
        # 追加载荷位置迁移修正标签。
        categories.append("migration_correction_node")
    # 汇总非空装配并排序，保持同一输入下输出顺序稳定。
    assemblies = sorted({role["assembly"] for role in roles if role["assembly"] is not None})
    # 汇总精确 gate 类装配名；CW1_GATE_09 与 CW2_GATE_09 保持可区分。
    gate_assemblies = sorted({role["assembly"] for role in roles if role["assembly_kind"] == "gate" and role["assembly"] is not None})
    # 汇总门架通用 GATE_## 标签，仅用于跨猫道同序号对照。
    gate_labels = sorted({role["gate_label"] for role in roles if role["gate_label"] is not None})
    # 汇总独立 Hxx 构件组身份；该字段只来自源注释的装配=Hxx。
    hxx_assemblies = sorted({role["hxx"] for role in roles if role["hxx"] is not None})
    # 根据修正值给出正、负或零语义；无修正则保留空值。
    correction_sign = None if correction is None else ("positive" if correction > 0.0 else "negative" if correction < 0.0 else "zero")
    # 返回完整节点注释对象。
    return {
        # 保存节点号。
        "node_id": node_id,
        # 保存可选全局坐标 mm。
        "coordinate_mm": coordinate,
        # 保存稳定分类标签。
        "categories": categories,
        # 保存全部 TYPE72 角色记录。
        "type72_roles": roles,
        # 保存精确装配集合。
        "assemblies": assemblies,
        # 保存精确 CW*_GATE_## 门架装配集合。
        "gate_assemblies": gate_assemblies,
        # 保存通用 GATE_## 门架标签集合。
        "gate_labels": gate_labels,
        # 保存独立 Hxx 构件组集合。
        "hxx_assemblies": hxx_assemblies,
        # 保存可选迁移基准 FZ，单位 N。
        "migration_base_fz_n": correction,
        # 保存修正符号语义。
        "migration_sign": correction_sign,
    }


# 将节点范数和工程注释合并为热点报告行。
def hotspot_record(
    node_id: int,
    force_norm: float,
    moment_norm: float,
    gate: dict[str, Any],
    migration: dict[str, Any],
) -> dict[str, Any]:
    """输入节点范数及源索引；返回含工程分类的单个热点记录。"""
    # 先生成节点工程注释，避免在调用处重复分类逻辑。
    record = annotate_node(node_id, gate, migration)
    # 追加力范数，单位 N。
    record["force_norm_n"] = force_norm
    # 追加力矩范数，单位 N·mm。
    record["moment_norm_n_mm"] = moment_norm
    # 返回合并后的热点记录。
    return record


# 对一组数值计算计数、最小、最大、中位数和均值，空组返回显式空统计。
def descriptive(values: Iterable[float]) -> dict[str, Any]:
    """输入任意有限浮点序列；返回基础描述统计，空序列各数值字段为 null。"""
    # 将迭代器物化为列表，确保中位数和均值可重复访问。
    data = list(values)
    # 空序列没有可定义的数值统计，返回计数零和空字段。
    if not data:
        # 返回结构稳定的空统计对象。
        return {"count": 0, "minimum": None, "maximum": None, "median": None, "mean": None}
    # 返回使用 Python 标准统计定义的描述量。
    return {
        # 保存样本数量。
        "count": len(data),
        # 保存最小值。
        "minimum": min(data),
        # 保存最大值。
        "maximum": max(data),
        # 保存中位数；偶数样本取中间两值平均。
        "median": statistics.median(data),
        # 保存算术平均值。
        "mean": statistics.fmean(data),
    }


# 分析全部完整 NRRE 文件，生成逐迭代热点、跨迭代频次及奇偶模式。
def analyze_nr_files(
    nr_results: list[dict[str, Any]],
    gate: dict[str, Any],
    migration: dict[str, Any],
    top_n: int,
    cross_top_n: int,
) -> dict[str, Any]:
    """输入已验证 NRRE 序列和映射索引；返回完整残差分析对象。"""
    # 不允许对空文件集发布“成功”报告。
    if not nr_results:
        # 抛出无输入异常。
        raise AuditError("运行目录中没有完整 NRRE 文件")
    # 按平衡迭代号排序，避免目录枚举顺序影响奇偶分析。
    ordered = sorted(nr_results, key=lambda item: item["equilibrium_iteration"])
    # 提取实际迭代序列。
    iterations = [item["equilibrium_iteration"] for item in ordered]
    # 要求从 1 开始无间断，缺号意味着证据集不完整或文件尚未同步。
    if iterations != list(range(1, len(ordered) + 1)):
        # 抛出实际序列，禁止用不连续样本推断奇偶模式。
        raise AuditError(f"NRRE 平衡迭代序列不连续：{iterations}")
    # 以第一次迭代节点集合为基准。
    reference_nodes = set(ordered[0]["values"])
    # 后续每个文件必须包含完全相同的节点集合。
    for item in ordered[1:]:
        # 比较节点集合而非仅比较计数，防止等量替换节点未被发现。
        if set(item["values"]) != reference_nodes:
            # 抛出节点集合不一致异常。
            raise AuditError(f"NRRE 节点集合与 nr001 不一致：{item['name']}")
    # 初始化每节点力范数序列，用于峰值与中位数统计。
    force_series: dict[int, list[float]] = {node_id: [] for node_id in reference_nodes}
    # 初始化每节点力矩范数序列。
    moment_series: dict[int, list[float]] = {node_id: [] for node_id in reference_nodes}
    # 初始化节点进入每迭代力 topN 的次数。
    force_top_frequency: dict[int, int] = {}
    # 初始化节点进入每迭代力矩 topN 的次数。
    moment_top_frequency: dict[int, int] = {}
    # 初始化逐迭代报告列表。
    iteration_reports: list[dict[str, Any]] = []
    # 遍历按序迭代并计算热点。
    for item in ordered:
        # 将本迭代每节点两个范数追加到跨迭代序列。
        for node_id, norms in item["values"].items():
            # 追加该节点本迭代力范数。
            force_series[node_id].append(norms[0])
            # 追加该节点本迭代力矩范数。
            moment_series[node_id].append(norms[1])
        # 用 nlargest 提取力范数前 top_n，次级键为负节点号使并列时小节点号优先。
        top_force_pairs = heapq.nlargest(top_n, item["values"].items(), key=lambda pair: (pair[1][0], -pair[0]))
        # 用 nlargest 提取力矩范数前 top_n。
        top_moment_pairs = heapq.nlargest(top_n, item["values"].items(), key=lambda pair: (pair[1][1], -pair[0]))
        # 记录每个力热点节点出现频次。
        for node_id, _ in top_force_pairs:
            # 将该节点力 topN 频次增加一次。
            force_top_frequency[node_id] = force_top_frequency.get(node_id, 0) + 1
        # 记录每个力矩热点节点出现频次。
        for node_id, _ in top_moment_pairs:
            # 将该节点力矩 topN 频次增加一次。
            moment_top_frequency[node_id] = moment_top_frequency.get(node_id, 0) + 1
        # 为力热点逐项添加工程分类。
        top_force = [hotspot_record(node_id, norms[0], norms[1], gate, migration) for node_id, norms in top_force_pairs]
        # 为力矩热点逐项添加工程分类。
        top_moment = [hotspot_record(node_id, norms[0], norms[1], gate, migration) for node_id, norms in top_moment_pairs]
        # 计算本迭代所有节点力范数中位数，用于识别热点是否为局部异常。
        all_force_median = statistics.median(norms[0] for norms in item["values"].values())
        # 计算本迭代所有节点力矩范数中位数。
        all_moment_median = statistics.median(norms[1] for norms in item["values"].values())
        # 统计本迭代力 topN 的主要工程标签覆盖数。
        classification_counts = {
            # 统计参与任一 TYPE72 的力热点数量。
            "force_top_type72_nodes": sum("type72_node" in row["categories"] for row in top_force),
            # 统计涉及 ALL 六自由度刚接的力热点数量。
            "force_top_all_nodes": sum("type72_all" in row["categories"] for row in top_force),
            # 统计涉及 UXYZ 平移连接的力热点数量。
            "force_top_uxyz_nodes": sum("type72_uxyz" in row["categories"] for row in top_force),
            # 统计门架新增几何节点的力热点数量。
            "force_top_gate_geometry_nodes": sum("gate_geometry_node" in row["categories"] for row in top_force),
            # 统计迁移修正节点的力热点数量。
            "force_top_migration_nodes": sum("migration_correction_node" in row["categories"] for row in top_force),
            # 统计参与任一 TYPE72 的力矩热点数量。
            "moment_top_type72_nodes": sum("type72_node" in row["categories"] for row in top_moment),
            # 统计涉及 ALL 六自由度刚接的力矩热点数量。
            "moment_top_all_nodes": sum("type72_all" in row["categories"] for row in top_moment),
            # 统计涉及 UXYZ 平移连接的力矩热点数量。
            "moment_top_uxyz_nodes": sum("type72_uxyz" in row["categories"] for row in top_moment),
            # 统计门架新增几何节点的力矩热点数量。
            "moment_top_gate_geometry_nodes": sum("gate_geometry_node" in row["categories"] for row in top_moment),
            # 统计迁移修正节点的力矩热点数量。
            "moment_top_migration_nodes": sum("migration_correction_node" in row["categories"] for row in top_moment),
        }
        # 追加本迭代完整摘要。
        iteration_reports.append({
            # 保存文件身份和哈希。
            "file": {key: item[key] for key in ("name", "path", "size_bytes", "sha256")},
            # 保存平衡迭代号。
            "equilibrium_iteration": item["equilibrium_iteration"],
            # 保存奇偶类别，便于直接筛选。
            "parity": "odd" if item["equilibrium_iteration"] % 2 == 1 else "even",
            # 保存阶段头部。
            "header": {key: item[key] for key in ("time", "load_step", "substep", "node_count", "release_line")},
            # 保存 ANSYS 全局残差范数。
            "cnvv": item["cnvv"],
            # 保存 ANSYS 收敛阈值。
            "cnvc": item["cnvc"],
            # 保存 CNVV/CNVC 比率，小于等于一代表该力准则满足。
            "cnvv_to_cnvc": item["cnvv"] / item["cnvc"],
            # 保存全节点力范数中位数。
            "all_node_force_norm_median_n": all_force_median,
            # 保存全节点力矩范数中位数。
            "all_node_moment_norm_median_n_mm": all_moment_median,
            # 保存热点分类覆盖统计。
            "top_classification_counts": classification_counts,
            # 保存 50 个力热点。
            "top_force": top_force,
            # 保存 50 个力矩热点。
            "top_moment": top_moment,
        })
    # 构造跨迭代候选集，取曾进入力或力矩 topN 的节点并避免输出全部 91,407 节点。
    candidate_nodes = set(force_top_frequency) | set(moment_top_frequency)
    # 初始化跨迭代热点记录。
    cross_records: list[dict[str, Any]] = []
    # 对每个候选节点计算全序列统计。
    for node_id in candidate_nodes:
        # 读取该节点按迭代顺序的力范数序列。
        node_forces = force_series[node_id]
        # 读取该节点按迭代顺序的力矩范数序列。
        node_moments = moment_series[node_id]
        # 提取奇数平衡迭代的力范数。
        odd_forces = [value for index, value in enumerate(node_forces, start=1) if index % 2 == 1]
        # 提取偶数平衡迭代的力范数。
        even_forces = [value for index, value in enumerate(node_forces, start=1) if index % 2 == 0]
        # 提取奇数平衡迭代的力矩范数。
        odd_moments = [value for index, value in enumerate(node_moments, start=1) if index % 2 == 1]
        # 提取偶数平衡迭代的力矩范数。
        even_moments = [value for index, value in enumerate(node_moments, start=1) if index % 2 == 0]
        # 生成基础节点工程注释。
        record = annotate_node(node_id, gate, migration)
        # 保存进入力 topN 的迭代次数。
        record["force_top_frequency"] = force_top_frequency.get(node_id, 0)
        # 保存进入力矩 topN 的迭代次数。
        record["moment_top_frequency"] = moment_top_frequency.get(node_id, 0)
        # 保存每次迭代力范数序列。
        record["force_norm_series_n"] = node_forces
        # 保存每次迭代力矩范数序列。
        record["moment_norm_series_n_mm"] = node_moments
        # 保存全迭代力峰值。
        record["force_peak_n"] = max(node_forces)
        # 保存全迭代力中位数。
        record["force_median_n"] = statistics.median(node_forces)
        # 保存全迭代力矩峰值。
        record["moment_peak_n_mm"] = max(node_moments)
        # 保存全迭代力矩中位数。
        record["moment_median_n_mm"] = statistics.median(node_moments)
        # 保存奇数迭代力中位数。
        record["odd_force_median_n"] = statistics.median(odd_forces)
        # 偶数样本存在时保存偶数迭代力中位数，否则为空。
        record["even_force_median_n"] = statistics.median(even_forces) if even_forces else None
        # 保存奇数迭代力矩中位数。
        record["odd_moment_median_n_mm"] = statistics.median(odd_moments)
        # 偶数样本存在时保存偶数迭代力矩中位数，否则为空。
        record["even_moment_median_n_mm"] = statistics.median(even_moments) if even_moments else None
        # 追加到跨迭代候选记录。
        cross_records.append(record)
    # 按力频次、力峰值、力矩频次、力矩峰值和节点号确定性排序。
    cross_records.sort(
        key=lambda row: (
            -row["force_top_frequency"],
            -row["force_peak_n"],
            -row["moment_top_frequency"],
            -row["moment_peak_n_mm"],
            row["node_id"],
        )
    )
    # 截取冻结的跨迭代热点上限。
    cross_records = cross_records[:cross_top_n]
    # 提取奇数迭代报告。
    odd_reports = [row for row in iteration_reports if row["parity"] == "odd"]
    # 提取偶数迭代报告。
    even_reports = [row for row in iteration_reports if row["parity"] == "even"]
    # 构造相邻奇数到偶数的 CNVV 放大比，零分母时返回空值而非无穷大。
    paired_cnvv_ratios: list[dict[str, Any]] = []
    # 每个偶数迭代与其紧邻前一个奇数迭代配对。
    for even_iteration in range(2, len(iteration_reports) + 1, 2):
        # 读取前一个奇数迭代报告。
        odd_row = iteration_reports[even_iteration - 2]
        # 读取当前偶数迭代报告。
        even_row = iteration_reports[even_iteration - 1]
        # 计算偶数 CNVV 除以前一奇数 CNVV，正值残差范数保证分母可用。
        ratio = even_row["cnvv"] / odd_row["cnvv"] if odd_row["cnvv"] != 0.0 else None
        # 追加配对证据。
        paired_cnvv_ratios.append({"odd_iteration": odd_row["equilibrium_iteration"], "even_iteration": even_row["equilibrium_iteration"], "even_to_odd_cnvv_ratio": ratio})
    # 初始化装配级热点聚合表。
    assembly_aggregate: dict[str, dict[str, Any]] = {}
    # 遍历每次迭代力 topN，用出现次数和峰值衡量持续门架热点。
    for iteration_row in iteration_reports:
        # 遍历本迭代每个力热点。
        for hotspot in iteration_row["top_force"]:
            # 初始化本节点按精确装配去重的角色身份，防止同装配多条连接重复计数。
            role_identity_by_assembly: dict[str, dict[str, Any]] = {}
            # 扫描该节点全部 TYPE72 角色并建立装配到自身身份的一对一映射。
            for role in hotspot["type72_roles"]:
                # 无装配角色不能形成可追溯装配聚合，应直接跳过。
                if role["assembly"] is None:
                    # 继续检查该节点的下一条 TYPE72 角色。
                    continue
                # 读取本角色精确装配名作为聚合主键。
                assembly = role["assembly"]
                # 首条同名角色冻结该装配身份；后续同名角色只贡献同一节点的一次出现。
                role_identity_by_assembly.setdefault(assembly, role)
            # 按每个唯一装配聚合该节点在本迭代的一次热点出现。
            for assembly, role in role_identity_by_assembly.items():
                # 首次出现时创建装配聚合对象，并冻结其自身类别身份。
                aggregate = assembly_aggregate.setdefault(
                    assembly,
                    {
                        # 保存精确装配名。
                        "assembly": assembly,
                        # 保存装配类别，后续同名记录必须一致。
                        "assembly_kind": role["assembly_kind"],
                        # 保存可选门架标签。
                        "gate_label": role["gate_label"],
                        # 保存可选独立 Hxx 身份。
                        "hxx": role["hxx"],
                        # 初始化力 topN 出现次数。
                        "force_top_occurrences": 0,
                        # 初始化装配力峰值 N。
                        "force_peak_n": 0.0,
                        # 初始化唯一热点节点集合。
                        "node_ids": set(),
                    },
                )
                # 累加进入力 topN 的出现次数。
                aggregate["force_top_occurrences"] += 1
                # 更新该装配观察到的最大力范数。
                aggregate["force_peak_n"] = max(aggregate["force_peak_n"], hotspot["force_norm_n"])
                # 记录涉及的唯一节点号。
                aggregate["node_ids"].add(hotspot["node_id"])
    # 将集合转换为排序列表，保证 JSON 可序列化且输出确定。
    assembly_hotspots = [
        {
            # 保存装配名。
            "assembly": value["assembly"],
            # 保存装配类别。
            "assembly_kind": value["assembly_kind"],
            # 保存可选门架标签。
            "gate_label": value["gate_label"],
            # 保存可选独立 Hxx 身份。
            "hxx": value["hxx"],
            # 保存力 topN 出现总次数。
            "force_top_occurrences": value["force_top_occurrences"],
            # 保存装配力峰值 N。
            "force_peak_n": value["force_peak_n"],
            # 保存唯一热点节点数。
            "unique_hotspot_node_count": len(value["node_ids"]),
            # 保存排序后的热点节点号。
            "node_ids": sorted(value["node_ids"]),
        }
        # 遍历全部装配聚合值。
        for value in assembly_aggregate.values()
    ]
    # 按出现次数、峰值和装配名排序装配热点。
    assembly_hotspots.sort(key=lambda row: (-row["force_top_occurrences"], -row["force_peak_n"], row["assembly"]))
    # 返回完整分析结果。
    return {
        # 保存实际完整迭代数。
        "iteration_count": len(iteration_reports),
        # 保存连续迭代序列。
        "equilibrium_iterations": iterations,
        # 保存逐迭代完整报告。
        "iterations": iteration_reports,
        # 保存跨迭代候选热点。
        "cross_iteration_hotspots": cross_records,
        # 保存装配/门架级热点聚合。
        "assembly_hotspots": assembly_hotspots,
        # 保存奇偶迭代全局模式。
        "odd_even_pattern": {
            # 保存奇数迭代 CNVV 描述统计。
            "odd_cnvv": descriptive(row["cnvv"] for row in odd_reports),
            # 保存偶数迭代 CNVV 描述统计。
            "even_cnvv": descriptive(row["cnvv"] for row in even_reports),
            # 保存奇数迭代最大节点力描述统计。
            "odd_peak_force_n": descriptive(row["top_force"][0]["force_norm_n"] for row in odd_reports),
            # 保存偶数迭代最大节点力描述统计。
            "even_peak_force_n": descriptive(row["top_force"][0]["force_norm_n"] for row in even_reports),
            # 保存奇数迭代最大节点力矩描述统计。
            "odd_peak_moment_n_mm": descriptive(row["top_moment"][0]["moment_norm_n_mm"] for row in odd_reports),
            # 保存偶数迭代最大节点力矩描述统计。
            "even_peak_moment_n_mm": descriptive(row["top_moment"][0]["moment_norm_n_mm"] for row in even_reports),
            # 保存相邻偶数与前一奇数 CNVV 的放大比。
            "paired_even_to_preceding_odd_cnvv": paired_cnvv_ratios,
        },
    }


# 生成面向人工复核的 Markdown 摘要，并把详细节点表留在配套 JSON。
def render_markdown(report: dict[str, Any]) -> str:
    """输入完整机器报告；返回包含阶段、奇偶模式和热点证据的 Markdown 文本。"""
    # 读取分析主体以缩短后续表达式。
    analysis = report["analysis"]
    # 初始化 Markdown 行列表，最终统一以 LF 拼接。
    lines: list[str] = []
    # 写入报告标题。
    lines.append("# C10 重启 NRRE 残差严格审计")
    # 写入空行满足 CommonMark 标题分隔要求。
    lines.append("")
    # 读取求解执行证据以区分自然终止终态和运行中快照。
    execution = report["execution_evidence"]
    # 写入发布状态，强调这是诊断证据而不是工程通过结论。
    lines.append(f"状态：**{report['status']}；不构成静力通过、模态通过或工程发布许可。**")
    # 写入空行。
    lines.append("")
    # 写入生成时刻、验证文件数量和仅终态可用的最终文件数量。
    lines.append(f"生成时刻（UTC）：`{report['generated_at_utc']}`；已验证 NRRE：{execution['verified_nr_file_count']} 个；最终 NRRE 数：{execution['final_nr_file_count'] if execution['final_nr_file_count'] is not None else '尚未自然终止'}；每文件节点：{report['contract']['expected_node_count']:,}。")
    # 写入求解输出哈希、锁状态和原生迭代上限终止判断。
    lines.append(f"求解输出 SHA-256：`{execution['solver_output']['sha256']}`；审计时 lock：{execution['solver_output']['lock_files_at_audit'] or '无'}；原生迭代上限终止：{execution['solver_output']['native_iteration_limit_detected']}。")
    # 写入空行。
    lines.append("")
    # 写入输入与契约标题。
    lines.append("## 严格输入契约")
    # 写入空行。
    lines.append("")
    # 写入阶段身份。
    lines.append(f"全部文件已验证为 time={report['contract']['expected_time']:.6f}、载荷步 {report['contract']['expected_load_step']}、子步 {report['contract']['expected_substep']}，平衡迭代号连续为 {analysis['equilibrium_iterations']}。")
    # 写入源连接规模。
    lines.append(f"TYPE72 主从连接：{report['sources']['gate_input']['connection_count']:,} 条，其中 ALL={report['sources']['gate_input']['mode_counts']['ALL']:,}、UXYZ={report['sources']['gate_input']['mode_counts']['UXYZ']:,}；迁移修正节点：{report['sources']['migration_input']['correction_node_count']:,} 个。")
    # 写入半写拒绝说明。
    lines.append("每个 NRRE 均通过精确行数、91,407 个唯一节点、头部文件名、六列顺序、有限数、读取前后大小与纳秒修改时间一致检查；若遇到半写文件，本工具会整体失败且不更新正式报告。")
    # 写入终止签名标题。
    lines.append("")
    # 写入终止签名标题。
    lines.append("## MAPDL 终止签名")
    # 写入空行。
    lines.append("")
    # 无终止相关行时明确标记仍是中间快照。
    if not execution["solver_output"]["termination_signature_lines"]:
        # 写入未捕获终止签名说明。
        lines.append("尚未捕获终止相关行；该报告只能视为运行中间快照。")
    # 有终止相关行时逐行原样列出行号和文本。
    else:
        # 遍历全部终止签名行并用代码格式避免 Markdown 解释星号。
        for signature in execution["solver_output"]["termination_signature_lines"]:
            # 写入一条带源行号的终止证据。
            lines.append(f"- 第 {signature['line_number']} 行：`{signature['text']}`")
    # 写入空行。
    lines.append("")
    # 写入逐迭代标题。
    lines.append("## 逐迭代峰值与连接覆盖")
    # 写入空行。
    lines.append("")
    # 写入表头。
    lines.append("| 迭代 | 奇偶 | CNVV / CNVC | 最大节点力 (N) | 节点 | 最大节点力矩 (N·mm) | 节点 | 力 Top50 中 TYPE72 / ALL / 迁移节点 |")
    # 写入表格分隔线。
    lines.append("|---:|:---:|---:|---:|---:|---:|---:|---:|")
    # 遍历每次迭代并写入一行摘要。
    for row in analysis["iterations"]:
        # 读取本迭代第一力热点。
        force_top = row["top_force"][0]
        # 读取本迭代第一力矩热点。
        moment_top = row["top_moment"][0]
        # 读取分类覆盖计数。
        counts = row["top_classification_counts"]
        # 写入本迭代表格行。
        lines.append(
            f"| {row['equilibrium_iteration']} | {row['parity']} | {scientific(row['cnvv_to_cnvc'])} | {scientific(force_top['force_norm_n'])} | {force_top['node_id']} | {scientific(moment_top['moment_norm_n_mm'])} | {moment_top['node_id']} | {counts['force_top_type72_nodes']} / {counts['force_top_all_nodes']} / {counts['force_top_migration_nodes']} |"
        )
    # 写入空行。
    lines.append("")
    # 写入奇偶模式标题。
    lines.append("## 奇偶迭代模式")
    # 写入空行。
    lines.append("")
    # 读取奇偶模式对象。
    parity = analysis["odd_even_pattern"]
    # 写入奇数与偶数 CNVV 中位数。
    lines.append(f"奇数迭代 CNVV 中位数：{scientific(parity['odd_cnvv']['median'])}；偶数迭代 CNVV 中位数：{scientific(parity['even_cnvv']['median']) if parity['even_cnvv']['median'] is not None else '尚无偶数样本'}。")
    # 写入奇数与偶数节点力峰值中位数。
    lines.append(f"奇数迭代最大节点力中位数：{scientific(parity['odd_peak_force_n']['median'])} N；偶数迭代最大节点力中位数：{scientific(parity['even_peak_force_n']['median']) if parity['even_peak_force_n']['median'] is not None else '尚无偶数样本'} N。")
    # 若存在奇偶配对则写入每对 CNVV 放大比。
    if parity["paired_even_to_preceding_odd_cnvv"]:
        # 生成紧凑的配对文本列表。
        pair_text = ", ".join(f"{item['odd_iteration']}→{item['even_iteration']}: {scientific(item['even_to_odd_cnvv_ratio'])}" for item in parity["paired_even_to_preceding_odd_cnvv"])
        # 写入配对放大比。
        lines.append(f"相邻偶数/前一奇数 CNVV 放大比：{pair_text}。")
    # 写入空行。
    lines.append("")
    # 写入跨迭代热点标题。
    lines.append("## 跨迭代持续热点（按力 Top50 频次优先）")
    # 写入空行。
    lines.append("")
    # 写入前二十热点表头，完整前二百见 JSON。
    lines.append("| 节点 | 力 Top50 频次 | 力峰值 (N) | 力中位数 (N) | 力矩峰值 (N·mm) | 角色/模式 | 装配 / Hxx | 迁移 FZ (N) |")
    # 写入表格分隔线。
    lines.append("|---:|---:|---:|---:|---:|:---|:---|---:|")
    # 仅在 Markdown 展示前二十个，机器报告保留冻结的跨迭代上限。
    for row in analysis["cross_iteration_hotspots"][:20]:
        # 将 TYPE72 角色与模式去重后合并。
        role_text = ", ".join(sorted({f"{role['role']}:{role['mode']}" for role in row["type72_roles"]})) or "非 TYPE72"
        # 将精确门架装配和独立 Hxx 分栏语义合并，避免把 GATE_03 误称为 H03。
        assembly_text = ", ".join(row["gate_assemblies"] + row["hxx_assemblies"]) or ", ".join(row["assemblies"]) or "—"
        # 格式化可选迁移修正值。
        migration_text = scientific(row["migration_base_fz_n"]) if row["migration_base_fz_n"] is not None else "—"
        # 写入热点表格行。
        lines.append(f"| {row['node_id']} | {row['force_top_frequency']} | {scientific(row['force_peak_n'])} | {scientific(row['force_median_n'])} | {scientific(row['moment_peak_n_mm'])} | {role_text} | {assembly_text} | {migration_text} |")
    # 写入空行。
    lines.append("")
    # 写入门架装配聚合标题。
    lines.append("## 门架/装配热点")
    # 写入空行。
    lines.append("")
    # 写入前二十装配表头，类别栏明确区分门架和 Hxx。
    lines.append("| 装配 | 类别 | 门架标签 / Hxx | 力 Top50 出现次数 | 力峰值 (N) | 唯一热点节点数 |")
    # 写入表格分隔线。
    lines.append("|:---|:---|:---|---:|---:|---:|")
    # 展示出现次数最高的二十个装配。
    for row in analysis["assembly_hotspots"][:20]:
        # 选择该装配自身的门架标签或独立 Hxx 身份，两者不会同时存在。
        identity_text = row["gate_label"] or row["hxx"] or "—"
        # 写入装配聚合行。
        lines.append(f"| {row['assembly']} | {row['assembly_kind']} | {identity_text} | {row['force_top_occurrences']} | {scientific(row['force_peak_n'])} | {row['unique_hotspot_node_count']} |")
    # 写入空行。
    lines.append("")
    # 写入审慎解释标题。
    lines.append("## 解释边界")
    # 写入空行。
    lines.append("")
    # 明确报告能证明的范围。
    lines.append("本报告只回答残差在何时、何节点、何种 TYPE72 角色及何装配集中；它不单独证明具体连接物理定义错误。连接改动必须结合图纸、自由度语义和独立小模型验证后实施。")
    # 写入 JSON 细节说明。
    lines.append("逐迭代 Top50、跨迭代前 200、完整 TYPE72 角色、坐标、迁移修正值、输入哈希均保存在 `nrre_residual_audit.json`。")
    # 说明两个报告及全部输入的不可递归 SHA-256 记录位置。
    lines.append("JSON、Markdown、工具、求解输出、源 include 与全部 NRRE 的 SHA-256 均写入 `nrre_residual_audit_hashes.sha256`；哈希清单不对自身做递归哈希。")
    # 在末尾添加换行，符合文本发布习惯。
    return "\n".join(lines) + "\n"


# 生成包含输入和派生物的 SHA-256 清单，不把清单自身纳入循环哈希。
def render_hash_manifest(paths: list[Path], base: Path) -> str:
    """输入待哈希路径和相对基准目录；返回按相对路径排序的 SHA-256 清单文本。"""
    # 初始化清单行。
    lines: list[str] = []
    # 按绝对路径字符串排序，确保跨次运行顺序稳定。
    for path in sorted(paths, key=lambda item: str(item.resolve()).lower()):
        # 尽可能使用相对于项目基准的路径，超出基准时保留绝对路径。
        try:
            # 计算相对路径并统一为正斜杠，便于跨平台审阅。
            display_path = path.resolve().relative_to(base.resolve()).as_posix()
        # 捕获路径不在基准目录下的情况。
        except ValueError:
            # 使用绝对 POSIX 风格路径，避免丢失证据位置。
            display_path = path.resolve().as_posix()
        # 写入 SHA-256、字节数和路径三列。
        lines.append(f"{sha256_file(path)}  {path.stat().st_size}  {display_path}")
    # 返回带末尾换行的完整清单。
    return "\n".join(lines) + "\n"


# 构建命令行参数解析器并解释每个冻结值的工程含义。
def build_parser() -> argparse.ArgumentParser:
    """无输入；返回配置完成的 ArgumentParser。"""
    # 创建解析器并给出工具用途说明。
    parser = argparse.ArgumentParser(description="严格分析 C10 重启 NLDIAG/NRRE 节点残差并映射 TYPE72 与载荷迁移节点。")
    # 要求显式传入专用诊断运行目录，避免误扫其他 run。
    parser.add_argument("--run-dir", type=Path, required=True, help="包含 solver 与 qa 的 C10_RESTART_NRRE_DIAGNOSTIC 专用运行目录。")
    # 要求显式传入实际门架/通道 include，支持 gate_assembly 或 apply_finite 版本。
    parser.add_argument("--gate-inp", type=Path, required=True, help="包含 TYPE72 EN 主从关系、ALL/UXYZ 注释和节点坐标的 APDL include。")
    # 要求显式传入本次源运行的迁移修正 include。
    parser.add_argument("--migration-inp", type=Path, required=True, help="包含 C10_BETA*FZ 节点修正的 APDL include。")
    # 要求显式传入本次重启捕获的 MAPDL 输出，以便记录终止签名和输出哈希。
    parser.add_argument("--solver-out", type=Path, required=True, help="本次重启 NRRE 捕获的 MAPDL 文本输出文件。")
    # 提供最终发布开关；启用时必须无 lock 且检测到 MAPDL 原生迭代上限错误签名。
    parser.add_argument("--require-terminated", action="store_true", help="要求求解已自然退出并捕获原生迭代上限终止签名，否则拒绝更新报告。")
    # 允许覆盖冻结节点数，仅供未来数据库变化时显式调整。
    parser.add_argument("--expected-node-count", type=int, default=DEFAULT_EXPECTED_NODE_COUNT, help="每个 NRRE 必须包含的唯一节点数，默认 91407。")
    # 允许显式冻结其他载荷步，默认仍为本诊断的第二步。
    parser.add_argument("--expected-load-step", type=int, default=DEFAULT_EXPECTED_LOAD_STEP, help="NRRE 头部必须声明的载荷步号，默认 2。")
    # 允许显式冻结其他子步，默认仍为重启后的第三子步。
    parser.add_argument("--expected-substep", type=int, default=DEFAULT_EXPECTED_SUBSTEP, help="NRRE 头部必须声明的子步号，默认 3。")
    # 允许显式冻结结果时间，默认 1.000002。
    parser.add_argument("--expected-time", type=float, default=DEFAULT_EXPECTED_TIME, help="NRRE 头部必须声明的结果时间，默认 1.000002。")
    # 允许显式调整绝对时间容差，默认 1E-9。
    parser.add_argument("--time-tolerance", type=float, default=DEFAULT_TIME_TOLERANCE, help="结果时间绝对比较容差，默认 1E-9。")
    # 允许调整逐迭代热点数，默认 50 且必须为正。
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="每迭代保存的力与力矩热点数量，默认 50。")
    # 允许调整跨迭代热点上限，默认 200 且必须不小于 top_n。
    parser.add_argument("--cross-top-n", type=int, default=DEFAULT_CROSS_TOP_N, help="跨迭代候选热点保存上限，默认 200。")
    # 返回完成配置的解析器。
    return parser


# 执行完整审计流程：验证输入、分析残差、发布 JSON/Markdown/哈希清单。
def run(args: argparse.Namespace) -> dict[str, Path]:
    """输入解析后的命令行参数；返回三个正式发布路径。"""
    # 将运行目录解析为绝对路径，后续所有派生路径基于该目录。
    run_dir = args.run_dir.resolve()
    # 冻结求解器目录，工具只读取其中 NRRE 文件。
    solver_dir = run_dir / "solver"
    # 冻结 QA 发布目录，工具只写入三个专属审计文件。
    qa_dir = run_dir / "qa"
    # 核验运行目录和求解器目录存在。
    if not run_dir.is_dir() or not solver_dir.is_dir():
        # 抛出目录缺失异常，避免意外创建错误 run。
        raise AuditError(f"运行目录或 solver 目录不存在：{run_dir}")
    # 核验两个源 APDL 和求解输出均为现存普通文件。
    if not args.gate_inp.is_file() or not args.migration_inp.is_file() or not args.solver_out.is_file():
        # 抛出源文件缺失异常。
        raise AuditError("gate-inp、migration-inp 或 solver-out 不存在")
    # 核验所有数值参数为合理正值。
    if args.expected_node_count <= 0 or args.top_n <= 0 or args.cross_top_n < args.top_n or args.time_tolerance < 0.0:
        # 抛出参数约束异常。
        raise AuditError("节点数/top-n 必须为正，cross-top-n 不得小于 top-n，时间容差不得为负")
    # 解析门架几何和 TYPE72 连接证据。
    gate = parse_gate_input(args.gate_inp.resolve())
    # 解析载荷位置迁移节点证据。
    migration = parse_migration_input(args.migration_inp.resolve())
    # 解析求解输出；最终模式会在无自然终止签名时先于报告写入失败。
    execution = parse_solver_output(args.solver_out.resolve(), solver_dir, args.require_terminated)
    # 枚举严格匹配 nrNNN 的文件，并按三位编号排序。
    nr_paths = sorted((path for path in solver_dir.iterdir() if path.is_file() and NR_FILE_PATTERN.match(path.name)), key=lambda path: int(NR_FILE_PATTERN.match(path.name).group("index")))
    # 未发现 NRRE 时拒绝发布。
    if not nr_paths:
        # 抛出空文件集异常。
        raise AuditError(f"solver 目录没有 .nrNNN 文件：{solver_dir}")
    # 严格解析全部已出现 NRRE；任何一个半写文件都会使本次执行失败。
    nr_results = [
        parse_nr_file(
            # 传入当前 NRRE 路径。
            path,
            # 传入冻结节点数。
            args.expected_node_count,
            # 传入冻结载荷步。
            args.expected_load_step,
            # 传入冻结子步。
            args.expected_substep,
            # 传入冻结结果时间。
            args.expected_time,
            # 传入绝对时间容差。
            args.time_tolerance,
        )
        # 对枚举到的每个文件执行严格解析。
        for path in nr_paths
    ]
    # 执行逐迭代、奇偶和跨迭代分析。
    analysis = analyze_nr_files(nr_results, gate, migration, args.top_n, args.cross_top_n)
    # 生成 UTC ISO-8601 时刻并使用 Z 表示零时区。
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # 根据自然终止证据区分最终审计与运行中间快照。
    report_status = "FINAL_NATIVE_TERMINATION_CAPTURE" if execution["final_native_termination"] else "INTERMEDIATE_RUNNING_DIAGNOSTIC"
    # 构造不含九万节点原始序列的可审计机器报告。
    report = {
        # 保存报告模式和版本，便于后续脚本拒绝不兼容结构。
        "schema": "c10_nrre_residual_audit_v1",
        # 保存生成时刻。
        "generated_at_utc": generated_at,
        # 明确本报告是最终自然终止诊断或运行中间快照，两者都不是工程通过。
        "status": report_status,
        # 显式冻结所有解析契约。
        "contract": {
            # 保存期望节点数。
            "expected_node_count": args.expected_node_count,
            # 保存期望载荷步。
            "expected_load_step": args.expected_load_step,
            # 保存期望子步。
            "expected_substep": args.expected_substep,
            # 保存期望结果时间。
            "expected_time": args.expected_time,
            # 保存时间绝对容差。
            "time_tolerance": args.time_tolerance,
            # 保存逐迭代热点数量。
            "top_n": args.top_n,
            # 保存跨迭代热点数量上限。
            "cross_top_n": args.cross_top_n,
            # 明确半写文件处理策略为整体拒绝。
            "partial_file_policy": "REJECT_ALL_AND_DO_NOT_PUBLISH",
            # 保存本次是否要求无锁自然终止状态。
            "require_terminated": args.require_terminated,
        },
        # 保存源 APDL 的路径、哈希和规模摘要。
        "sources": {
            # 保存门架连接输入摘要。
            "gate_input": {
                # 保存绝对路径。
                "path": gate["path"],
                # 保存文件大小。
                "size_bytes": gate["size_bytes"],
                # 保存 SHA-256。
                "sha256": gate["sha256"],
                # 保存坐标节点数。
                "coordinate_node_count": len(gate["coordinates"]),
                # 保存 TYPE72 连接数。
                "connection_count": len(gate["connections"]),
                # 保存 ALL/UXYZ 计数。
                "mode_counts": gate["mode_counts"],
            },
            # 保存迁移输入摘要。
            "migration_input": {
                # 保存绝对路径。
                "path": migration["path"],
                # 保存文件大小。
                "size_bytes": migration["size_bytes"],
                # 保存 SHA-256。
                "sha256": migration["sha256"],
                # 保存修正节点数。
                "correction_node_count": len(migration["corrections"]),
                # 保存正负零节点数。
                "sign_counts": migration["sign_counts"],
            },
        },
        # 保存求解输出哈希、锁状态、原生终止判断和逐行终止签名。
        "execution_evidence": {
            # 保存最终完整 NRRE 文件数量，避免把中间 7/9 文件报告误标为终态。
            "final_nr_file_count": analysis["iteration_count"] if execution["final_native_termination"] else None,
            # 保存当前已验证的 NRRE 文件数量，运行中快照同样可追踪。
            "verified_nr_file_count": analysis["iteration_count"],
            # 保存求解输出证据对象。
            "solver_output": execution,
        },
        # 保存完整分析主体。
        "analysis": analysis,
        # 明确禁止把诊断报告升级为静力/模态通过。
        "release_flags": {"static_pass": False, "modal_pass": False, "production_release": False},
    }
    # 冻结 JSON 正式路径。
    json_path = qa_dir / "nrre_residual_audit.json"
    # 冻结 Markdown 正式路径。
    markdown_path = qa_dir / "nrre_residual_audit.md"
    # 冻结哈希清单正式路径。
    hash_path = qa_dir / "nrre_residual_audit_hashes.sha256"
    # 以缩进两格和 UTF-8 中文发布 JSON，并追加末尾换行。
    atomic_write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    # 生成人工可读摘要并原子发布。
    atomic_write_text(markdown_path, render_markdown(report))
    # 将工具本身、源 APDL、求解输出、全部本次 NRRE 和两个报告纳入哈希清单。
    manifest_inputs = [Path(__file__).resolve(), args.gate_inp.resolve(), args.migration_inp.resolve(), args.solver_out.resolve(), *nr_paths, json_path, markdown_path]
    # 以项目目录即 ultra_tools 的父目录作为相对路径基准。
    project_base = Path(__file__).resolve().parent.parent
    # 生成并原子发布哈希清单；清单自身不纳入以避免递归。
    atomic_write_text(hash_path, render_hash_manifest(manifest_inputs, project_base))
    # 返回三个发布物路径供终端摘要使用。
    return {"json": json_path, "markdown": markdown_path, "hashes": hash_path}


# 命令行入口负责一致的退出码和简洁错误输出，不吞掉审计失败原因。
def main() -> int:
    """无输入；解析命令行并执行审计，成功返回 0，契约失败返回 2。"""
    # 构建并执行命令行解析。
    args = build_parser().parse_args()
    # 捕获预期审计异常并转为稳定退出码。
    try:
        # 执行完整审计并取得发布路径。
        outputs = run(args)
    # 仅处理本工具定义的证据错误；程序缺陷仍保留完整回溯。
    except AuditError as error:
        # 向标准错误输出单行失败原因，便于自动化监视器捕获。
        print(f"NRRE_AUDIT_FAILED: {error}", file=sys.stderr)
        # 返回退出码 2 表示输入或契约不满足。
        return 2
    # 输出成功状态和三个绝对发布路径，便于人工核验。
    print("NRRE_AUDIT_PUBLISHED")
    # 逐项输出发布路径，排序保证终端结果稳定。
    for label, path in sorted(outputs.items()):
        # 输出标签和绝对路径，不修改任何求解器状态。
        print(f"{label}={path.resolve()}")
    # 返回零表示全部严格验证和发布完成。
    return 0


# 仅在脚本被直接执行时调用入口；被测试导入时不产生文件写入。
if __name__ == "__main__":
    # 将 main 返回值交给操作系统作为进程退出码。
    raise SystemExit(main())
