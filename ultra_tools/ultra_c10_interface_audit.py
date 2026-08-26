"""为 C10 成功静力结果准备并复核 142 座门架与 3124 个 UXYZ 索接口的只读局部平衡审计。"""  # 本模块只生成 POST1 输入或解析其输出，禁止进入求解器和修改来源运行。
from __future__ import annotations  # 启用延迟类型注解，避免运行期解析前向引用。

import argparse  # 解析 inventory、prepare 与 reconcile 三种显式命令。
import csv  # 读取和写出全部逗号分隔工程台账。
import hashlib  # 计算来源、快照和审计工件的 SHA-256。
import json  # 读取运行清单并写出机器可读审计报告。
import math  # 执行向量范数、有限值和 Rodrigues 转动计算。
import os  # 计算从独立审计目录到来源求解目录的相对路径。
import statistics  # 计算同类构件热点的中位数基线。
import sys  # 向标准输出发布只读 inventory 结果并返回明确退出码。
from collections import defaultdict  # 按门架、接口和构件类型稳定归组。
from datetime import datetime, timezone  # 生成带微秒的 UTC 唯一审计目录名。
from pathlib import Path  # 使用跨平台路径对象并避免字符串路径拼接错误。
from typing import Any, Iterable, Sequence  # 声明 JSON、表格和向量函数的数据合同。

SCRIPT_PATH = Path(__file__).resolve()  # 冻结当前脚本绝对路径，供自身摘要和相邻项目目录定位。
PROJECT_DIR = SCRIPT_PATH.parent.parent  # ultra_tools 的父目录就是 V2.0 项目根目录。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 所有独立审计包均创建为 ultra_runs 的新兄弟运行。
GENERATED_NODES_PATH = PROJECT_DIR / "builder" / "generated" / "generated_nodes.csv"  # 冻结有限门架节点工程语义来源。
GENERATED_ELEMENTS_PATH = PROJECT_DIR / "builder" / "generated" / "generated_elements.csv"  # 冻结有限门架单元、体积和构件角色来源。
MASS_AUDIT_PATH = PROJECT_DIR / "mass21_spatialization_audit_v2.json"  # 冻结空间 MASS21 的生成来源摘要。
EXPECTED_GATE_COUNT = 142  # 两幅猫道有限门架总数必须恰为 142 座。
EXPECTED_UXYZ_COUNT = 3_124  # 每座 22 个索接口合计必须恰为 3124 个 UXYZ 接口。
EXPECTED_INTERFACE_LINK_COUNT = 6_248  # 每个接口必须邻接两段 LINK180，且不同接口之间不得复用同一段。
EXPECTED_INCIDENT_ROPE_NODE_COUNT = 9_372  # 3124 个接口节点及其两侧相邻节点合计必须恰为 9372 个唯一节点。
EXPECTED_INTERFACE_ROPE_NODE_COUNT = 3_124  # POST1 只需导出 3124 个 slave 节点以复核 TYPE72 刚臂运动学。
EXPECTED_GATE_NODE_COUNT = 4_828  # 每座门架 34 个非定向物理节点合计必须恰为 4828 个。
EXPECTED_GATE_ELEMENT_COUNT = 4_260  # 每座门架 30 个有限梁单元合计必须恰为 4260 个。
EXPECTED_LINK180_COUNT = 73_692  # 当前完整模型 TYPE4 LINK180 总数必须恰为 73692。
EXPECTED_CONNECTION_COUNT = 5_078  # 当前单层 TYPE72 连接映射总数必须恰为 5078。
EXPECTED_GATE_MASS_NODE_COUNT = 4_828  # 每个门架物理节点必须恰有一条空间 MASS21 质量记录。
EXPECTED_LOAD_PATH_MODE = "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 当前审计只接受 beta=1 到 beta=0 的恒总载荷位置迁移终态。
EXPECTED_FINAL_LOAD_STEP = 2  # 当前自适应迁移的最终平衡结果必须属于载荷步二。
EXPECTED_FINAL_TIME = 1.001  # 当前迁移终点伪时间必须为 1.001，单位 s 仅作求解路径参数。
MINIMUM_FINAL_SUBSTEP = 200  # 自适应 LS2 最少接受 200 个子步，对应初始 0.5% 迁移增量。
MAXIMUM_FINAL_SUBSTEP = 2_000  # 自适应 LS2 最多接受 2000 个子步，对应最小 0.05% 迁移增量。
GRAVITY_MM_S2 = 9_806.0  # 项目冻结重力加速度为 9806 mm/s²，tonne·mm/s² 等于 N。
FORCE_WEIGHT_RATIO_LIMIT = 1.0e-3  # 每座门架局部自由体残差不得超过本门架重量的千分之一。
MOMENT_WEIGHT_SPAN_RATIO_LIMIT = 1.0e-3  # 每座门架力矩残差不得超过重量乘特征跨度的千分之一。
FORCE_GROSS_RATIO_LIMIT = 1.0e-6  # 每座门架残差相对全部接口力模和不得超过百万分之一。
MOMENT_GROSS_RATIO_LIMIT = 1.0e-6  # 每座门架力矩残差相对全部作用力矩模和不得超过百万分之一。
INTERFACE_WRENCH_RATIO_LIMIT = 1.0e-6  # 每个 UXYZ 接口的等效力矩与 r×F 偏差相对作用尺度不得超过百万分之一。
ARM_LENGTH_ABS_TOL_MM = 1.0e-6  # TYPE72 刚臂长度保持的绝对容差为一微米的千分之一，即 1E-6 mm。
ARM_LENGTH_REL_TOL = 1.0e-9  # TYPE72 刚臂长度保持的相对容差为十亿分之一。
NEGATIVE_ENERGY_TOL_N_MM = 1.0e-8  # 允许二进制舍入导致不超过 1E-8 N·mm 的微小负能量。
HOTSPOT_MEDIAN_FACTOR = 5.0  # 超过同构件正值中位数五倍的响应进入人工热点复核，不直接判模型失败。
TOP_HOTSPOT_COUNT = 30  # 每类热点最多发布三十条，限制报告体积并保留控制位置。
HASH_BLOCK_BYTES = 8 * 1024 * 1024  # 大型 DB/RST 每次按 8 MiB 只读分块计算摘要。


def require(condition: bool, message: str) -> None:  # 输入硬门禁布尔和失败说明，失败时立即中止。
    """参数：condition 为门禁，message 为原因；返回：None；约束：失败必须 fail-closed。"""  # 说明函数输入、输出和异常路径。
    if not condition:  # 仅在门禁不满足时进入拒绝路径。
        raise RuntimeError(message)  # 抛出包含工程上下文的明确异常。


def sha256_file(path: Path) -> str:  # 输入普通文件并流式返回小写 SHA-256。
    """参数：path 为现存普通文件；返回：64 位摘要；约束：只读且不得跟随缺失对象。"""  # 说明摘要函数合同。
    require(path.is_file(), f"待哈希文件不存在：{path}")  # 哈希前确认目标存在且是普通文件。
    digest = hashlib.sha256()  # 为当前文件创建独立摘要累加器。
    with path.open("rb") as stream:  # 以二进制只读模式打开，禁止编码转换。
        while True:  # 持续读取直到明确到达文件末尾。
            block = stream.read(HASH_BLOCK_BYTES)  # 读取固定 8 MiB 字节块以控制内存。
            if not block:  # 空字节串只表示正常 EOF。
                break  # 结束摘要读取循环。
            digest.update(block)  # 把当前原始字节块加入摘要状态。
    return digest.hexdigest()  # 返回小写十六进制 SHA-256。


def read_json(path: Path) -> dict[str, Any]:  # 输入 JSON 路径并返回对象根字典。
    """参数：path 为 UTF-8 JSON；返回：字典；约束：根对象必须是 object。"""  # 说明 JSON 读取合同。
    require(path.is_file(), f"JSON 文件不存在：{path}")  # 拒绝缺失输入。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 以 UTF-8-SIG 严格解析完整文本并兼容既有 BOM。
    require(isinstance(value, dict), f"JSON 根对象不是字典：{path}")  # 拒绝数组或标量根对象。
    return value  # 返回经类型门禁的字典。


def read_csv_dicts(path: Path) -> list[dict[str, str]]:  # 输入带标题 CSV 并返回字符串字典行。
    """参数：path 为 UTF-8-SIG CSV；返回：行字典列表；约束：标题必须存在。"""  # 说明表格读取合同。
    require(path.is_file(), f"CSV 文件不存在：{path}")  # 读取前确认普通文件存在。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 兼容 BOM 并禁止换行二次转换。
        reader = csv.DictReader(stream)  # 使用首行构造稳定列名字典。
        require(reader.fieldnames is not None, f"CSV 缺少标题：{path}")  # 无标题文件不得作为工程台账。
        return [dict(row) for row in reader]  # 物化全部行，便于后续数量和唯一性门禁。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # 输入目标路径和字典并原子式写入 UTF-8 JSON。
    """参数：path 与 payload；返回：None；约束：临时文件与目标必须位于同一目录。"""  # 说明 JSON 发布合同。
    temporary = path.with_suffix(path.suffix + ".tmp")  # 使用相邻临时文件保证替换操作同卷原子。
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"  # 生成稳定排序且保留中文的文本。
    temporary.write_text(text, encoding="utf-8", newline="\n")  # 先完整写入临时对象并统一 LF。
    temporary.replace(path)  # 完整写入后原子替换目标文件。


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:  # 输入列和行并写出带标题 CSV。
    """参数：目标、列名和行；返回：None；约束：列顺序由 fieldnames 唯一决定。"""  # 说明 CSV 发布合同。
    temporary = path.with_suffix(path.suffix + ".tmp")  # 创建与目标相邻的临时 CSV。
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:  # 使用 Excel 兼容 BOM 和 csv 原生换行。
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="raise")  # 拒绝未声明字段以防静默丢列。
        writer.writeheader()  # 写出唯一标题行。
        for row in rows:  # 按调用方冻结顺序遍历全部记录。
            writer.writerow(row)  # 写出一条完整工程记录。
    temporary.replace(path)  # 全部记录完成后原子替换目标。


def finite_float(value: Any, label: str) -> float:  # 输入数值文本和字段名并返回有限浮点数。
    """参数：value 与 label；返回：有限 float；约束：NaN 和无穷均拒绝。"""  # 说明数值解析合同。
    number = float(value)  # 显式转换字符串或数值对象。
    require(math.isfinite(number), f"字段 {label} 不是有限数：{value}")  # 拒绝 NaN 与正负无穷。
    return number  # 返回经过有限性门禁的浮点数。


def vector_add(*vectors: Sequence[float]) -> list[float]:  # 输入任意三维向量并返回逐分量和。
    """参数：零个或多个三维向量；返回：[x,y,z]；约束：每个向量长度必须为三。"""  # 说明向量求和合同。
    result = [0.0, 0.0, 0.0]  # 初始化三维零向量。
    for vector in vectors:  # 遍历全部待累加向量。
        require(len(vector) == 3, f"向量维数不是 3：{vector}")  # 拒绝错误维数。
        result = [result[index] + float(vector[index]) for index in range(3)]  # 逐分量累加并返回新列表。
    return result  # 返回三维总和。


def vector_sub(left: Sequence[float], right: Sequence[float]) -> list[float]:  # 输入两个三维向量并返回 left-right。
    """参数：两个三维向量；返回：差向量；约束：维数均为三。"""  # 说明向量差合同。
    require(len(left) == 3 and len(right) == 3, "向量差输入维数不是 3")  # 拒绝错误维数。
    return [float(left[index]) - float(right[index]) for index in range(3)]  # 逐分量计算差值。


def vector_scale(vector: Sequence[float], factor: float) -> list[float]:  # 输入三维向量和标量并返回乘积。
    """参数：三维向量与标量；返回：缩放向量；约束：向量长度为三。"""  # 说明向量缩放合同。
    require(len(vector) == 3, "缩放向量维数不是 3")  # 拒绝错误维数。
    return [float(component) * float(factor) for component in vector]  # 对三个分量应用同一标量。


def vector_norm(vector: Sequence[float]) -> float:  # 输入三维向量并返回欧氏范数。
    """参数：三维向量；返回：非负范数；约束：向量长度为三。"""  # 说明范数合同。
    require(len(vector) == 3, "范数向量维数不是 3")  # 拒绝错误维数。
    return math.sqrt(sum(float(component) ** 2 for component in vector))  # 计算平方和的非负平方根。


def cross(left: Sequence[float], right: Sequence[float]) -> list[float]:  # 输入两个三维向量并返回叉积。
    """参数：两个三维向量；返回：left×right；约束：右手全局坐标。"""  # 说明力矩方向合同。
    require(len(left) == 3 and len(right) == 3, "叉积输入维数不是 3")  # 拒绝错误维数。
    return [float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]), float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]), float(left[0]) * float(right[1]) - float(left[1]) * float(right[0])]  # 按右手规则计算三个分量。


def rodrigues_rotate(rotation: Sequence[float], vector: Sequence[float]) -> list[float]:  # 用转动向量指数映射旋转三维向量。
    """参数：rad 转动向量和三维向量；返回：旋转向量；约束：仅作诊断，不作为硬门禁。"""  # 说明该量受 MAPDL 转角参数化影响。
    angle = vector_norm(rotation)  # 计算总转角幅值，单位 rad。
    if angle <= 1.0e-15:  # 极小转角进入一阶数值保护。
        return vector_add(vector, cross(rotation, vector))  # 使用一阶展开避免单位轴除零。
    axis = vector_scale(rotation, 1.0 / angle)  # 构造单位转轴。
    cosine = math.cos(angle)  # 计算 Rodrigues 余弦系数。
    sine = math.sin(angle)  # 计算 Rodrigues 正弦系数。
    return vector_add(vector_scale(vector, cosine), vector_scale(cross(axis, vector), sine), vector_scale(axis, sum(axis[index] * float(vector[index]) for index in range(3)) * (1.0 - cosine)))  # 按指数映射组合平行与垂直分量。


def percentile(values: Sequence[float], probability: float) -> float:  # 输入数值序列和 [0,1] 概率并线性插值分位数。
    """参数：有限序列和概率；返回：分位数；约束：序列非空且概率闭区间。"""  # 说明热点阈值计算合同。
    require(values and 0.0 <= probability <= 1.0, "分位数输入为空或概率越界")  # 拒绝空序列和非法概率。
    ordered = sorted(float(value) for value in values)  # 创建升序副本，禁止修改调用方序列。
    position = probability * (len(ordered) - 1)  # 把概率映射到零起点连续索引。
    lower = int(math.floor(position))  # 取得左侧样本索引。
    upper = int(math.ceil(position))  # 取得右侧样本索引。
    fraction = position - lower  # 计算右侧权重。
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction  # 在线性插值下返回分位数。


def resolve_parent_mapping(source_run: Path, manifest: dict[str, Any]) -> Path:  # 输入来源运行和清单并定位 5078 条连接映射。
    """参数：来源运行与清单；返回：connection_mapping.csv；约束：只允许当前或直接父 C10 运行。"""  # 说明谱系解析合同。
    direct = source_run / "qa" / "connection_mapping.csv"  # 先检查来源运行自身是否携带映射。
    if direct.is_file():  # 来源本身是 C10_MPC_ONLY 时直接使用。
        return direct  # 返回来源运行内的冻结映射。
    parent_name = str(manifest.get("parent_run", ""))  # 读取迁移运行声明的直接父运行名。
    require(parent_name.startswith("C10_MPC_ONLY_"), "来源运行未声明可接受的 C10_MPC_ONLY 直接父运行")  # 禁止跨谱系猜测映射。
    parent = source_run.parent / parent_name  # 在同一 ultra_runs 根目录解析父运行。
    require(parent.parent.resolve() == source_run.parent.resolve(), "父运行路径逃逸 ultra_runs")  # 防止清单路径穿越。
    mapping = parent / "qa" / "connection_mapping.csv"  # 构造父运行映射路径。
    require(mapping.is_file(), f"父运行连接映射不存在：{mapping}")  # 父映射缺失即拒绝。
    return mapping  # 返回直接父运行内的冻结映射。


def resolve_mass_path(source_run: Path) -> Path:  # 输入来源运行并定位其冻结空间质量节点表。
    """参数：来源运行；返回：mass21_spatialized_v2_nodes.csv；约束：优先使用 input_snapshot。"""  # 说明质量来源解析合同。
    candidates = [source_run / "input_snapshot" / "mass21_spatialized_v2_nodes.csv", source_run / "solver" / "mass21_spatialized_v2_nodes.csv", PROJECT_DIR / "mass21_spatialized_v2_nodes.csv"]  # 按运行快照、求解目录和项目封板源排序。
    for candidate in candidates:  # 依次寻找第一个现存来源。
        if candidate.is_file():  # 仅接受普通文件。
            return candidate  # 返回优先级最高的现存质量表。
    raise RuntimeError("未找到空间 MASS21 节点表")  # 所有候选缺失时 fail-closed。


def parse_link_connectivity(mesh_path: Path) -> dict[int, tuple[int, int]]:  # 从冻结基础网格恢复前 73688 个主索 LINK 元素连接。
    """参数：基础网格 APDL；返回：元素号到两节点；约束：仅解析 TYPE1 区段连续 E 命令。"""  # 说明解析范围和编号假定。
    connectivity: dict[int, tuple[int, int]] = {}  # 初始化主索连接字典。
    active_type = None  # 初始化尚未读取任何 TYPE 命令的状态。
    next_element_id = 0  # E 命令自动编号从零计数并在记录前加一。
    with mesh_path.open("r", encoding="utf-8-sig", errors="strict") as stream:  # 以 UTF-8 只读遍历冻结输入。
        for raw_line in stream:  # 按原文件顺序逐行解析。
            line = raw_line.strip()  # 去除首尾空白但保留逗号字段内容。
            upper = line.upper()  # 构造大小写无关命令视图。
            if upper.startswith("TYPE,"):  # TYPE 命令更新后续 E 自动编号所属单元族。
                fields = [field.strip() for field in line.split(",")]  # 拆分 TYPE 字段。
                active_type = int(fields[1])  # 保存当前显式类型编号。
                if active_type == 2 and len(connectivity) == 73_688:  # 首次进入梁单元区且主索计数已闭合时结束。
                    break  # 后续 BEAM4 元素与本接口索邻接无关。
            elif upper.startswith("E,") and active_type == 1:  # 仅解析基础网格 TYPE1 LINK10 的 E 自动编号命令。
                fields = [field.strip() for field in line.split(",")]  # 拆分 E 命令字段。
                require(len(fields) >= 3, f"LINK E 命令字段不足：{line}")  # 每个二节点索至少含两个节点号。
                next_element_id += 1  # 按 MAPDL 自动编号规则推进元素号。
                connectivity[next_element_id] = (int(fields[1]), int(fields[2]))  # 记录当前主索元素的两个端点。
    require(len(connectivity) == 73_688 and set(connectivity) == set(range(1, 73_689)), "基础网格主索元素不是连续 1..73688")  # 冻结主索拓扑必须完整连续。
    return connectivity  # 返回主索连接字典；四个下拉索不与门架接口相邻。


def build_inventory(source_run: Path, require_static_success: bool) -> dict[str, Any]:  # 汇总门架接口审计所需全部冻结对象。
    """参数：来源运行和成功门禁开关；返回：内存 inventory；约束：只读且执行完整数量闭合。"""  # 说明 inventory 合同。
    source_run = source_run.resolve()  # 解析绝对来源目录并消除相对歧义。
    require(source_run.is_dir(), f"来源运行目录不存在：{source_run}")  # 拒绝缺失来源运行。
    require(source_run.parent.resolve() == ULTRA_RUNS_DIR.resolve(), "来源运行不是本项目 ultra_runs 的直接子目录")  # 禁止跨项目来源。
    manifest = read_json(source_run / "manifest.json")  # 读取来源运行清单。
    jobname = str(manifest.get("jobname", ""))  # 提取 ASCII MAPDL jobname。
    require(jobname and len(jobname) <= 32 and all(character.isalnum() or character == "_" for character in jobname), "来源 jobname 非法或超过 32 字符")  # 防止路径和 MAPDL 参数注入。
    mapping_path = resolve_parent_mapping(source_run, manifest)  # 定位冻结连接映射。
    mass_path = resolve_mass_path(source_run)  # 定位当前运行实际使用的空间质量表。
    mesh_path = source_run / "solver" / "full_line_beam4_crossbeam_mesh_xlong.inp"  # 使用来源运行自己的冻结基础网格。
    require(mesh_path.is_file(), f"来源基础网格不存在：{mesh_path}")  # 网格缺失即拒绝。
    generated_audit = read_json(MASS_AUDIT_PATH)  # 读取生成几何来源摘要。
    binding = generated_audit.get("input_binding", {})  # 提取质量审计的输入绑定对象。
    require(isinstance(binding, dict), "质量审计 input_binding 不是字典")  # 拒绝损坏的来源绑定。
    require(sha256_file(GENERATED_NODES_PATH) == str(binding.get("generated_nodes", {}).get("sha256", "")), "generated_nodes.csv 已偏离质量审计摘要")  # 验证门架节点来源未漂移。
    require(sha256_file(GENERATED_ELEMENTS_PATH) == str(binding.get("generated_elements", {}).get("sha256", "")), "generated_elements.csv 已偏离质量审计摘要")  # 验证门架单元来源未漂移。
    mapping_rows = read_csv_dicts(mapping_path)  # 读取完整 5078 条逻辑连接。
    require(len(mapping_rows) == EXPECTED_CONNECTION_COUNT, "连接映射总数不是 5078")  # 拒绝不完整连接映射。
    uxyz_rows = [row for row in mapping_rows if row.get("system") == "gate" and row.get("dof_label") == "UXYZ"]  # 只保留 142 座门架的 3124 个平移索接口。
    require(len(uxyz_rows) == EXPECTED_UXYZ_COUNT, "门架 UXYZ 接口数不是 3124")  # 拒绝漏接口或重复接口。
    require(len({row["conn_id"] for row in uxyz_rows}) == EXPECTED_UXYZ_COUNT, "UXYZ conn_id 不唯一")  # 每条接口必须有唯一审计 ID。
    require(len({int(row["slave_node"]) for row in uxyz_rows}) == EXPECTED_UXYZ_COUNT, "UXYZ slave 节点不唯一")  # 每个索节点只能属于一个门架接口。
    require(len({int(row["rigid_element"]) for row in uxyz_rows}) == EXPECTED_UXYZ_COUNT, "UXYZ TYPE72 元素不唯一")  # 每个逻辑接口必须一对一映射刚臂。
    gate_nodes_all = read_csv_dicts(GENERATED_NODES_PATH)  # 读取有限构件全部节点语义。
    gate_nodes = [row for row in gate_nodes_all if row.get("system") == "gate" and row.get("is_orientation") == "0"]  # 排除仅定义梁朝向的定向节点。
    require(len(gate_nodes) == EXPECTED_GATE_NODE_COUNT, "门架物理节点数不是 4828")  # 每座 34 个物理节点必须闭合。
    require(len({int(row["apdl_node_id"]) for row in gate_nodes}) == EXPECTED_GATE_NODE_COUNT, "门架物理节点号不唯一")  # 拒绝重复节点号。
    gate_elements_all = read_csv_dicts(GENERATED_ELEMENTS_PATH)  # 读取有限构件全部单元语义。
    gate_elements = [row for row in gate_elements_all if row.get("system") == "gate"]  # 只保留 142 座门架物理梁。
    require(len(gate_elements) == EXPECTED_GATE_ELEMENT_COUNT, "门架物理梁单元数不是 4260")  # 每座 30 个梁单元必须闭合。
    require(len({int(row["apdl_elem_id"]) for row in gate_elements}) == EXPECTED_GATE_ELEMENT_COUNT, "门架物理梁单元号不唯一")  # 拒绝重复单元号。
    mass_rows_all = read_csv_dicts(mass_path)  # 读取当前来源运行使用的空间 MASS21 节点表。
    gate_mass_rows = [row for row in mass_rows_all if row.get("system") == "gate"]  # 只保留门架自重对应的质量记录。
    require(len(gate_mass_rows) == EXPECTED_GATE_MASS_NODE_COUNT, "门架 MASS21 节点数不是 4828")  # 每个物理节点必须有一条质量记录。
    require({int(row["apdl_node_id"]) for row in gate_mass_rows} == {int(row["apdl_node_id"]) for row in gate_nodes}, "门架 MASS21 节点集合与物理节点集合不一致")  # 质量与有限梁节点必须一一覆盖。
    gate_assemblies = sorted({row["assembly_name"] for row in uxyz_rows})  # 提取门架装配 ID 集合。
    require(len(gate_assemblies) == EXPECTED_GATE_COUNT, "门架装配数不是 142")  # 两幅各 71 座必须闭合。
    for assembly in gate_assemblies:  # 逐座执行固定工程量门禁。
        require(sum(row["assembly_name"] == assembly for row in uxyz_rows) == 22, f"{assembly} 的 UXYZ 接口数不是 22")  # 每座必须 16 根底索加 6 根门架索。
        require(sum(row["assembly_name"] == assembly for row in gate_nodes) == 34, f"{assembly} 的物理节点数不是 34")  # 每座物理节点数必须固定。
        require(sum(row["assembly_name"] == assembly for row in gate_elements) == 30, f"{assembly} 的梁单元数不是 30")  # 每座梁单元数必须固定。
        require(sum(row["assembly_name"] == assembly for row in gate_mass_rows) == 34, f"{assembly} 的 MASS21 节点数不是 34")  # 每座质量节点数必须固定。
    connectivity = parse_link_connectivity(mesh_path)  # 从来源网格独立恢复主索连接。
    node_to_links: dict[int, list[int]] = defaultdict(list)  # 初始化节点到相邻主索单元的反向索引。
    for element_id, endpoints in connectivity.items():  # 遍历全部 73688 个基础主索单元。
        node_to_links[endpoints[0]].append(element_id)  # 把单元加入 I 端节点邻接表。
        node_to_links[endpoints[1]].append(element_id)  # 把单元加入 J 端节点邻接表。
    incident_rows: list[dict[str, Any]] = []  # 初始化 6248 条接口邻接索映射。
    for connection in sorted(uxyz_rows, key=lambda row: row["conn_id"]):  # 按稳定 conn_id 顺序遍历全部接口。
        slave = int(connection["slave_node"])  # 读取当前原索 slave 节点号。
        adjacent = sorted(node_to_links.get(slave, []))  # 查找并排序相邻主索段。
        require(len(adjacent) == 2, f"接口 {connection['conn_id']} 的相邻主索段数不是 2")  # 每个门架位置必须位于连续索内部。
        for element_id in adjacent:  # 为左右两侧索段各写一条可追溯映射。
            n1, n2 = connectivity[element_id]  # 读取当前索段两个端点。
            other = n2 if n1 == slave else n1  # 确定远离接口的另一节点。
            require(n1 == slave or n2 == slave, "邻接索反向索引内部不一致")  # 防止索引构造缺陷。
            incident_rows.append({"conn_id": connection["conn_id"], "assembly_name": connection["assembly_name"], "master_node": int(connection["master_node"]), "slave_node": slave, "rigid_element": int(connection["rigid_element"]), "link_element": element_id, "n1": n1, "n2": n2, "other_node": other})  # 保存接口、刚臂和索段一对一来源链。
    require(len(incident_rows) == EXPECTED_INTERFACE_LINK_COUNT, "接口邻接索映射行数不是 6248")  # 两段乘 3124 必须闭合。
    require(len({int(row["link_element"]) for row in incident_rows}) == EXPECTED_INTERFACE_LINK_COUNT, "不同门架接口复用了同一相邻索段")  # 防止相邻门架过近导致自由体边界重复。
    incident_rope_node_ids = sorted({int(row["n1"]) for row in incident_rows} | {int(row["n2"]) for row in incident_rows})  # 汇总接口节点和全部相邻端点供离线拓扑闭合。
    require(len(incident_rope_node_ids) == EXPECTED_INCIDENT_ROPE_NODE_COUNT, "接口相邻索节点唯一数不是 9372")  # 3124×3 节点集合必须闭合。
    rope_node_ids = sorted(int(row["slave_node"]) for row in uxyz_rows)  # POST1 仅导出 3124 个原索 slave 节点以检查刚臂长度。
    require(len(rope_node_ids) == EXPECTED_INTERFACE_ROPE_NODE_COUNT and len(set(rope_node_ids)) == EXPECTED_INTERFACE_ROPE_NODE_COUNT, "接口 slave 节点数不是 3124 或不唯一")  # 最小节点导出集合必须闭合。
    master_node_ids = sorted(int(row["master_node"]) for row in uxyz_rows)  # 冻结 3124 个门架梁轴 master 节点供 gate-side FSUM。
    require(len(master_node_ids) == EXPECTED_UXYZ_COUNT and len(set(master_node_ids)) == EXPECTED_UXYZ_COUNT, "接口 master 节点数不是 3124 或不唯一")  # 每个接口必须有唯一门架侧节点。
    gate_node_ids = sorted(int(row["apdl_node_id"]) for row in gate_nodes)  # 冻结 4828 个门架物理节点号。
    gate_element_ids = sorted(int(row["apdl_elem_id"]) for row in gate_elements)  # 冻结 4260 个门架梁单元号。
    solver_dir = source_run / "solver"  # 定位来源求解目录。
    rst_path = solver_dir / f"{jobname}.rst"  # 构造来源静力结果路径。
    equilibrium_db_path = solver_dir / f"{jobname}_eq.db"  # 构造全部静力门禁通过后保存的平衡数据库路径。
    if require_static_success:  # prepare 模式必须证明来源静力已正式最终化。
        require(manifest.get("load_path_mode") == EXPECTED_LOAD_PATH_MODE, "来源运行不是当前 beta=1 到 beta=0 恒总载荷位置迁移路径")  # 禁止其他 C10 静力路径借用本审计结论。
        status = read_json(source_run / "C10_static_status.json")  # 读取来源最终静力状态。
        require(status.get("static_numeric_gates") == "PASSED", "来源 C10_static_status 未通过静力数值门禁")  # 拒绝准备态或失败态。
        gate_text = (solver_dir / "c10_gate_status.txt").read_text(encoding="latin-1", errors="strict")  # 读取 MAPDL 原生终态标记。
        require("STATUS=STATIC_DIAGNOSTIC_GATES_PASSED PHASE=STATIC_ONLY_COMPLETE" in gate_text, "来源 MAPDL gate 状态不是静力完成")  # 原生终态必须与最终化状态一致。
        require(rst_path.is_file() and equilibrium_db_path.is_file(), "来源静力 RST 或平衡 DB 缺失")  # POST1 复用所需两份二进制必须存在。
        require(not any(solver_dir.glob("*.lock")), "来源求解目录仍存在 lock，不允许并发读取")  # 避免与仍在运行的求解器并发读取。
    return {"source_run": source_run, "manifest": manifest, "jobname": jobname, "mapping_path": mapping_path, "mass_path": mass_path, "mesh_path": mesh_path, "gate_assemblies": gate_assemblies, "uxyz_rows": uxyz_rows, "gate_nodes": gate_nodes, "gate_elements": gate_elements, "gate_mass_rows": gate_mass_rows, "incident_rows": incident_rows, "incident_rope_node_ids": incident_rope_node_ids, "rope_node_ids": rope_node_ids, "master_node_ids": master_node_ids, "gate_node_ids": gate_node_ids, "gate_element_ids": gate_element_ids, "rst_path": rst_path, "equilibrium_db_path": equilibrium_db_path}  # 返回准备或只读盘点所需完整内存对象。


def append_selection(lines: list[str], entity: str, ids: Sequence[int]) -> None:  # 向 APDL 列表追加显式节点或单元选择。
    """参数：APDL 行、NODE/ELEM 和 ID；返回：None；约束：ID 严格递增且唯一。"""  # 说明选择生成合同。
    require(entity in {"NODE", "ELEM"}, f"不支持的选择实体：{entity}")  # 只允许节点和单元。
    require(list(ids) == sorted(set(int(value) for value in ids)), f"{entity} ID 未严格递增唯一")  # 防止重复选择隐藏工程量错误。
    selector = "NSEL" if entity == "NODE" else "ESEL"  # 选择对应 MAPDL 命令。
    lines.append(f"{selector},NONE ! 清空当前 {entity} 选择，建立精确审计集合。")  # 从空选择开始避免继承污染。
    for object_id in ids:  # 逐个加入冻结对象 ID。
        lines.append(f"{selector},A,{entity},,{int(object_id)} ! 加入冻结 {entity} {int(object_id)}。")  # 显式记录每个对象，便于输入审阅和哈希追踪。


def append_node_export(lines: list[str], ids: Sequence[int], stem: str, rotations: bool, expected_count: int) -> None:  # 追加节点位移或转角 CSV 导出块。
    """参数：行、ID、文件干名、是否含转角和期望数；返回：None；约束：只读 POST1。"""  # 说明节点导出合同。
    append_selection(lines, "NODE", ids)  # 建立当前节点精确选择集。
    prefix = "IAG" if rotations else "IAR"  # 使用短参数前缀满足 MAPDL 名称长度限制。
    lines.append(f"*GET,{prefix}_COUNT,NODE,0,COUNT ! 读取 {stem} 选中节点数。")  # 从求解器实测选择数。
    lines.append(f"*GET,{prefix}_NODE,NODE,0,NUM,MIN ! 读取 {stem} 首个节点号。")  # 初始化稳定编号遍历。
    lines.append(f"*CFOPEN,{stem},csv ! 打开 {stem}.csv 原始数值文件。")  # 输出不含标题，避免本地代码页影响。
    lines.append(f"*DO,{prefix}_I,1,{prefix}_COUNT ! 遍历全部 {stem} 节点。")  # 循环次数由 MAPDL 实测数量控制。
    lines.append(f"*GET,{prefix}_X,NODE,{prefix}_NODE,LOC,X ! 读取原始全局 X 坐标，单位 mm。")  # 保存未变形坐标。
    lines.append(f"*GET,{prefix}_Y,NODE,{prefix}_NODE,LOC,Y ! 读取原始全局 Y 坐标，单位 mm。")  # 保存未变形坐标。
    lines.append(f"*GET,{prefix}_Z,NODE,{prefix}_NODE,LOC,Z ! 读取原始全局 Z 坐标，单位 mm。")  # 保存未变形坐标。
    lines.append(f"*GET,{prefix}_UX,NODE,{prefix}_NODE,U,X ! 读取全局 UX，单位 mm。")  # 保存顺桥位移。
    lines.append(f"*GET,{prefix}_UY,NODE,{prefix}_NODE,U,Y ! 读取全局 UY，单位 mm。")  # 保存横桥位移。
    lines.append(f"*GET,{prefix}_UZ,NODE,{prefix}_NODE,U,Z ! 读取全局 UZ，单位 mm。")  # 保存竖向位移。
    if rotations:  # 门架 BEAM188 节点额外导出三个转角分量。
        lines.append(f"*GET,{prefix}_RX,NODE,{prefix}_NODE,ROT,X ! 读取全局 RX，单位 rad。")  # 保存绕 X 转角。
        lines.append(f"*GET,{prefix}_RY,NODE,{prefix}_NODE,ROT,Y ! 读取全局 RY，单位 rad。")  # 保存绕 Y 转角。
        lines.append(f"*GET,{prefix}_RZ,NODE,{prefix}_NODE,ROT,Z ! 读取全局 RZ，单位 rad。")  # 保存绕 Z 转角。
        lines.append(f"*VWRITE,{prefix}_NODE,{prefix}_X,{prefix}_Y,{prefix}_Z,{prefix}_UX,{prefix}_UY,{prefix}_UZ,{prefix}_RX,{prefix}_RY,{prefix}_RZ ! 写出节点号、坐标、位移和转角。")  # 固定十列节点结果。
        lines.append("(F12.0,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16)")  # 定义十列纯数值格式并保持格式行无尾注释。
    else:  # 纯 LINK180 节点没有转动自由度，只导出坐标与平移。
        lines.append(f"*VWRITE,{prefix}_NODE,{prefix}_X,{prefix}_Y,{prefix}_Z,{prefix}_UX,{prefix}_UY,{prefix}_UZ ! 写出节点号、坐标和位移。")  # 固定七列索节点结果。
        lines.append("(F12.0,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16)")  # 定义七列纯数值格式并保持格式行无尾注释。
    lines.append(f"*GET,{prefix}_NODE,NODE,{prefix}_NODE,NXTH ! 推进到下一选中节点。")  # 使用选择集稳定遍历。
    lines.append("*ENDDO ! 结束节点导出循环。")  # 闭合循环。
    lines.append("*CFCLOS ! 关闭节点 CSV。")  # 保证缓冲区落盘。
    lines.append(f"*IF,{prefix}_COUNT,NE,{expected_count},THEN ! 检查 {stem} 节点数是否匹配冻结值。")  # 原生工程量门禁。
    lines.append(f"/COM,INTERFACE_AUDIT_REJECTED {stem.upper()}_COUNT_MISMATCH ! 记录节点数量拒绝原因。")  # 在 OUT 中留下明确原因。
    lines.append("/EXIT,NOSAVE ! 数量不符时只读退出且不保存数据库。")  # 禁止错误对象进入 Python 对账。
    lines.append("*ENDIF ! 结束节点数量门禁。")  # 闭合条件分支。


def append_interface_fsum(lines: list[str], master_ids: Sequence[int]) -> None:  # 追加 3124 个门架侧 master 的 gate-only 元素节点合力导出块。
    """参数：APDL 行和唯一 master ID；返回：None；约束：调用前 ESEL 必须只含 4260 个门架梁。"""  # 说明 FSUM 仅隔离门架物理梁侧的接口力学口径。
    require(len(master_ids) == EXPECTED_UXYZ_COUNT and list(master_ids) == sorted(set(int(value) for value in master_ids)), "FSUM master ID 不是 3124 个递增唯一节点")  # 拒绝漏接口或重复接口。
    lines.append(f"IA_IFCOUNT={EXPECTED_UXYZ_COUNT} ! 冻结需要导出的 UXYZ master 数量。")  # 为数组和循环提供同一工程量参数。
    lines.append(f"*DIM,IA_MAST,ARRAY,{EXPECTED_UXYZ_COUNT} ! 分配 3124 项 master 节点号数组。")  # 使用显式数组避免循环中破坏节点选择集。
    for index, master_id in enumerate(master_ids, start=1):  # 按递增 master 节点号填充数组。
        lines.append(f"IA_MAST({index})={int(master_id)} ! 保存第 {index} 个门架侧接口 master 节点 {int(master_id)}。")  # 每个数组项均可由输入文本审计。
    lines.append("*CFOPEN,c10_ia_interface_gate_fsum,csv ! 打开门架侧接口六分量 FSUM 原始表。")  # 输出节点号、三力和三力矩共七列。
    lines.append("/NOPR ! 暂停 3124 次 FSUM 的冗长打印，但保留 FSUM 缓存和 *CFOPEN 写出。")  # 控制 OUT 体积且不改变数值计算。
    lines.append("*DO,IA_IFI,1,IA_IFCOUNT ! 遍历全部 UXYZ master。")  # 循环次数固定为 3124。
    lines.append("IA_MASTER=IA_MAST(IA_IFI) ! 读取当前门架侧 master 节点号。")  # 从显式数组取得当前对象。
    lines.append("NSEL,S,NODE,,IA_MASTER ! 仅选择当前 master 节点。")  # FSUM 只汇总当前边界节点。
    lines.append("SPOINT,IA_MASTER ! 把力矩求和点设为当前 master，消除全局坐标力臂项。")  # 得到接口在 master 处的直接等效力矩。
    lines.append("FSUM ! 汇总当前已选门架梁单元在 master 节点的三力和三力矩。")  # ESEL 仍仅含 4260 个门架物理梁，排除 TYPE72、MASS21 和索系。
    lines.append("*GET,IA_IFX,FSUM,0,ITEM,FX ! 读取门架梁节点合力 FX，单位 N。")  # 保存全局 X 分量。
    lines.append("*GET,IA_IFY,FSUM,0,ITEM,FY ! 读取门架梁节点合力 FY，单位 N。")  # 保存全局 Y 分量。
    lines.append("*GET,IA_IFZ,FSUM,0,ITEM,FZ ! 读取门架梁节点合力 FZ，单位 N。")  # 保存全局 Z 分量。
    lines.append("*GET,IA_IMX,FSUM,0,ITEM,MX ! 读取关于 master 的直接节点力矩 MX，单位 N·mm。")  # 保存绕 X 分量。
    lines.append("*GET,IA_IMY,FSUM,0,ITEM,MY ! 读取关于 master 的直接节点力矩 MY，单位 N·mm。")  # 保存绕 Y 分量。
    lines.append("*GET,IA_IMZ,FSUM,0,ITEM,MZ ! 读取关于 master 的直接节点力矩 MZ，单位 N·mm。")  # 保存绕 Z 分量。
    lines.append("*VWRITE,IA_MASTER,IA_IFX,IA_IFY,IA_IFZ,IA_IMX,IA_IMY,IA_IMZ ! 写出 master 节点号和六分量 gate-side FSUM。")  # 固定七列接口结果。
    lines.append("(F12.0,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16,',',E24.16)")  # 定义七列纯数值格式并保持格式行无尾注释。
    lines.append("*ENDDO ! 结束 3124 个接口 FSUM 循环。")  # 闭合循环。
    lines.append("/GOPR ! 恢复正常 MAPDL 打印。")  # 确保后续摘要与退出诊断可见。
    lines.append("*CFCLOS ! 关闭接口 FSUM CSV。")  # 保证全部七列记录落盘。
    lines.append("ALLSEL,ALL ! 恢复全部节点和单元选择。")  # 清除最后一个 master 的局部选择。


def make_apdl(inventory: dict[str, Any], audit_solver_dir: Path) -> str:  # 输入 inventory 和未来工作目录并生成唯一 POST1 输入。
    """参数：冻结 inventory 与审计 solver 目录；返回：APDL 文本；约束：不得含任何求解或保存命令。"""  # 说明 APDL 生成合同。
    source_solver = Path(inventory["source_run"]) / "solver"  # 定位来源求解目录。
    relative_solver = Path(os.path.relpath(source_solver, audit_solver_dir)).as_posix().replace("/", "\\")  # 构造 ASCII 相对 Windows 路径。
    require("'" not in relative_solver and "," not in relative_solver, "来源相对路径含 MAPDL 非安全字符")  # 拒绝引号或逗号注入。
    jobname = str(inventory["jobname"])  # 读取来源 jobname。
    lines: list[str] = []  # 初始化 APDL 行列表。
    lines.append("/CLEAR,NOSTART ! 清空独立会话并禁止读取启动文件。")  # 保证后处理环境可复现。
    lines.append(f"RESUME,'{relative_solver}\\{jobname}_eq','db' ! 只读恢复来源成功静力平衡数据库。")  # 复用现有模型而不重新装配。
    lines.append("/POST1 ! 进入通用后处理器，禁止进入 SOLU。")  # 明确只读分析阶段。
    lines.append(f"FILE,'{relative_solver}\\{jobname}','rst' ! 绑定来源静力结果文件。")  # 直接读取成功运行 RST。
    lines.append("SET,LAST ! 读取来源运行最终静力结果集。")  # 审计最终 beta=0 平衡端点。
    lines.append("FORCE,TOTAL ! 显式选择静力、阻尼和惯性元素节点力总和，禁止继承来源数据库的 FORCE 状态。")  # gate-only FSUM 必须使用冻结的总节点力口径。
    lines.append("*GET,IA_LS,ACTIVE,0,SET,LSTP ! 读取实际载荷步编号。")  # 禁止在 Python 中硬编码结果身份。
    lines.append("*GET,IA_SB,ACTIVE,0,SET,SBST ! 读取实际子步编号。")  # 保存最终自适应子步号。
    lines.append("*GET,IA_TM,ACTIVE,0,SET,TIME ! 读取实际伪时间。")  # 保存最终迁移时间。
    lines.append("CSYS,0 ! 固定全局笛卡尔坐标 X 顺桥、Y 横桥、Z 竖向。")  # 统一位置坐标系。
    lines.append("RSYS,0 ! 固定结果输出为全局笛卡尔坐标。")  # 统一位移和转角分量。
    lines.append("ALLSEL,ALL ! 恢复全部节点和单元选择。")  # 清除 DB 恢复后的选择状态。
    lines.append("ESEL,S,TYPE,,4 ! 选择全部 TYPE4 LINK180。")  # 全局正拉门禁覆盖 73692 根索段。
    lines.append("*GET,IA_LCOUNT,ELEM,0,COUNT ! 读取完整 LINK180 实测数量。")  # 记录求解器工程量。
    lines.append("ETABLE,ERAS ! 清空继承的单元表列。")  # 避免旧列污染轴力。
    lines.append("ETABLE,IA_AXIAL,SMISC,1 ! 建立 LINK180 轴力列，正值表示受拉，单位 N。")  # 使用项目已验证的 LINK180 官方结果项。
    lines.append("*GET,IA_ELEM,ELEM,0,NUM,MIN ! 读取首个选中 LINK180 元素号。")  # 初始化稳定元素遍历。
    lines.append("*CFOPEN,c10_ia_link180_force,csv ! 打开全部 LINK180 轴力原始表。")  # 输出两列纯数值。
    lines.append("*DO,IA_I,1,IA_LCOUNT ! 遍历全部 LINK180。")  # 循环次数由实测数量控制。
    lines.append("*GET,IA_FORCE,ELEM,IA_ELEM,ETAB,IA_AXIAL ! 读取当前 LINK180 轴力，单位 N。")  # 获取受拉正号结果。
    lines.append("*VWRITE,IA_ELEM,IA_FORCE ! 写出元素号和轴力。")  # 固定两列输出。
    lines.append("(F12.0,',',E24.16)")  # 定义两列纯数值格式并保留 16 位有效小数。
    lines.append("*GET,IA_ELEM,ELEM,IA_ELEM,NXTH ! 推进到下一选中 LINK180。")  # 使用选择集遍历。
    lines.append("*ENDDO ! 结束全部 LINK180 遍历。")  # 闭合循环。
    lines.append("*CFCLOS ! 关闭轴力 CSV。")  # 保证完整落盘。
    lines.append(f"*IF,IA_LCOUNT,NE,{EXPECTED_LINK180_COUNT},THEN ! 检查 LINK180 总数是否为 {EXPECTED_LINK180_COUNT}。")  # 原生全局索工程量门禁。
    lines.append("/COM,INTERFACE_AUDIT_REJECTED LINK180_COUNT_MISMATCH ! 记录索数量拒绝原因。")  # 在 OUT 中保留原因。
    lines.append("/EXIT,NOSAVE ! 数量不符时立即只读退出。")  # 禁止不完整轴力进入对账。
    lines.append("*ENDIF ! 结束 LINK180 数量门禁。")  # 闭合条件分支。
    append_selection(lines, "ELEM", inventory["gate_element_ids"])  # 选择全部 4260 个门架物理梁。
    lines.append("*GET,IA_GECOUNT,ELEM,0,COUNT ! 读取门架物理梁实测数量。")  # 原生验证选择工程量。
    lines.append("ETABLE,ERAS ! 清空 LINK180 轴力列。")  # 为门架能量建立独立列。
    lines.append("ETABLE,IA_SENE,SENE ! 建立门架梁单元应变能列，单位 N·mm。")  # 复用静力 RST 中已保存的 VENG。
    lines.append("*GET,IA_GELEM,ELEM,0,NUM,MIN ! 读取首个门架梁单元号。")  # 初始化能量遍历。
    lines.append("*CFOPEN,c10_ia_gate_element_sene,csv ! 打开门架单元能量原始表。")  # 输出两列纯数值。
    lines.append("*DO,IA_GEI,1,IA_GECOUNT ! 遍历全部门架梁单元。")  # 循环次数由实测数量控制。
    lines.append("*GET,IA_ENERGY,ELEM,IA_GELEM,ETAB,IA_SENE ! 读取当前梁单元应变能，单位 N·mm。")  # 获取能量热点基础量。
    lines.append("*VWRITE,IA_GELEM,IA_ENERGY ! 写出单元号和应变能。")  # 固定两列输出。
    lines.append("(F12.0,',',E24.16)")  # 定义两列纯数值格式并保留双精度文本。
    lines.append("*GET,IA_GELEM,ELEM,IA_GELEM,NXTH ! 推进到下一门架梁单元。")  # 使用选择集遍历。
    lines.append("*ENDDO ! 结束门架能量遍历。")  # 闭合循环。
    lines.append("*CFCLOS ! 关闭门架能量 CSV。")  # 保证完整落盘。
    lines.append(f"*IF,IA_GECOUNT,NE,{EXPECTED_GATE_ELEMENT_COUNT},THEN ! 检查门架梁单元数是否为 {EXPECTED_GATE_ELEMENT_COUNT}。")  # 原生门架单元门禁。
    lines.append("/COM,INTERFACE_AUDIT_REJECTED GATE_ELEMENT_COUNT_MISMATCH ! 记录门架梁数量拒绝原因。")  # 在 OUT 中保留原因。
    lines.append("/EXIT,NOSAVE ! 数量不符时立即只读退出。")  # 禁止不完整能量进入对账。
    lines.append("*ENDIF ! 结束门架梁数量门禁。")  # 闭合条件分支。
    append_selection(lines, "ELEM", inventory["gate_element_ids"])  # 再次精确选择 4260 个门架物理梁供接口节点 FSUM。
    append_interface_fsum(lines, inventory["master_node_ids"])  # 导出 3124 个 gate-side master 的三力和三力矩。
    append_node_export(lines, inventory["gate_node_ids"], "c10_ia_gate_node_response", True, EXPECTED_GATE_NODE_COUNT)  # 导出门架物理节点坐标、位移和转角。
    append_node_export(lines, inventory["rope_node_ids"], "c10_ia_rope_node_response", False, EXPECTED_INTERFACE_ROPE_NODE_COUNT)  # 导出接口邻接索节点坐标和位移。
    lines.append("/OUTPUT,c10_ia_result_identity,txt ! 打开结果集和工程量机器摘要。")  # 创建独立身份文件。
    lines.append("*VWRITE,IA_LS,IA_SB,IA_TM,IA_LCOUNT,IA_GECOUNT,IA_IFCOUNT,IAG_COUNT,IAR_COUNT ! 写出结果身份及五类工程量。")  # 固定八项摘要。
    lines.append("('LSTP=',F8.0,',SBST=',F12.0,',TIME=',E24.16,',LINK180=',F12.0,',GATE_ELEM=',F12.0,',INTERFACE=',F12.0,',GATE_NODE=',F12.0,',ROPE_NODE=',F12.0)")  # 定义可解析摘要格式并保持格式行无尾注释。
    lines.append("/OUTPUT ! 恢复主 OUT。")  # 结束机器摘要输出。
    lines.append("ALLSEL,ALL ! 退出前恢复全部实体选择。")  # 不在数据库留下选择副作用。
    lines.append("FINISH ! 离开 POST1。")  # 结束后处理阶段。
    lines.append("/EXIT,NOSAVE ! 不保存数据库并正常退出独立会话。")  # 硬性保证来源 DB 不被改写。
    text = "\n".join(lines) + "\n"  # 使用 LF 组装完整 APDL 文本。
    forbidden = {"/SOLU", "SOLVE", "ANTYPE", "SAVE", "RESWRITE", "RSTCREATE", "/DELETE", "/RENAME"}  # 冻结所有禁止的求解、保存和破坏命令头，避免路径中的 solver 字样误报。
    active_lines = [line.split("!", 1)[0].strip().upper() for line in lines if line.split("!", 1)[0].strip()]  # 去除注释构造逐行活动命令审计视图。
    command_heads = [line.split(",", 1)[0].strip() for line in active_lines]  # 提取每条活动行首个命令字段，参数字符串不参与命令识别。
    require(not any(head in forbidden for head in command_heads), f"生成 APDL 含禁止命令头：{sorted(forbidden & set(command_heads))}")  # 任一禁止命令头出现即拒绝发布。
    active = "\n".join(active_lines)  # 拼接活动命令供只读退出和结果集次数门禁使用。
    require(active.count("/EXIT,NOSAVE") >= 5 and active.count("SET,LAST") == 1, "生成 APDL 的只读退出或结果集合同不闭合")  # 证明全部失败路径和正常路径均 NOSAVE。
    return text  # 返回经 allowlist 门禁的只读 POST1 输入。


def prepare_audit(source_run: Path, requested_dir: Path | None) -> Path:  # 从成功静力来源创建独立审计准备包。
    """参数：来源运行和可选新目录；返回：审计目录；约束：绝不写入来源运行。"""  # 说明准备动作边界。
    inventory = build_inventory(source_run, True)  # 先只读关闭全部来源成功和工程量门禁。
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")  # 生成微秒级 UTC 唯一标识。
    audit_dir = (requested_dir or (ULTRA_RUNS_DIR / f"C10_INTERFACE_AUDIT_{timestamp}")).resolve()  # 解析未来独立审计目录。
    require(audit_dir.parent == ULTRA_RUNS_DIR.resolve(), "审计目录必须是 ultra_runs 的新直接子目录")  # 禁止写入来源运行或任意外部位置。
    require(audit_dir != Path(inventory["source_run"]), "审计目录不得等于来源运行")  # 双重禁止改当前 run。
    require(not audit_dir.exists(), f"审计目录已存在，拒绝覆盖：{audit_dir}")  # 所有审计包必须唯一且不可覆盖。
    solver_dir = audit_dir / "solver"  # 构造未来 MAPDL 工作目录。
    qa_dir = audit_dir / "qa"  # 构造 Python 对账目录。
    snapshot_dir = audit_dir / "input_snapshot"  # 构造冻结输入快照目录。
    solver_dir.mkdir(parents=True, exist_ok=False)  # 一次创建审计根和 solver，禁止复用旧目录。
    qa_dir.mkdir(exist_ok=False)  # 创建独立 QA 目录。
    snapshot_dir.mkdir(exist_ok=False)  # 创建独立输入快照目录。
    write_csv(snapshot_dir / "uxyz_connection_mapping.csv", list(inventory["uxyz_rows"][0].keys()), inventory["uxyz_rows"])  # 快照 3124 条逻辑接口。
    write_csv(snapshot_dir / "gate_nodes.csv", list(inventory["gate_nodes"][0].keys()), inventory["gate_nodes"])  # 快照 4828 个门架物理节点。
    write_csv(snapshot_dir / "gate_elements.csv", list(inventory["gate_elements"][0].keys()), inventory["gate_elements"])  # 快照 4260 个门架梁单元。
    write_csv(snapshot_dir / "gate_mass21_nodes.csv", list(inventory["gate_mass_rows"][0].keys()), inventory["gate_mass_rows"])  # 快照 4828 条门架质量记录。
    incident_fields = ["conn_id", "assembly_name", "master_node", "slave_node", "rigid_element", "link_element", "n1", "n2", "other_node"]  # 冻结邻接索映射列顺序。
    write_csv(snapshot_dir / "incident_link_map.csv", incident_fields, inventory["incident_rows"])  # 快照 6248 条接口邻接索。
    apdl_path = solver_dir / "c10_interface_audit_post1.inp"  # 构造未来只读 MAPDL 输入路径。
    apdl_path.write_text(make_apdl(inventory, solver_dir), encoding="utf-8", newline="\n")  # 写出经禁止命令门禁的 POST1 输入。
    rst_path = Path(inventory["rst_path"])  # 读取来源 RST 路径。
    db_path = Path(inventory["equilibrium_db_path"])  # 读取来源平衡 DB 路径。
    source_identity = {"source_run": Path(inventory["source_run"]).name, "jobname": inventory["jobname"], "source_manifest_sha256": sha256_file(Path(inventory["source_run"]) / "manifest.json"), "source_final_ledger_sha256": sha256_file(Path(inventory["source_run"]) / "artifact_hashes.sha256"), "source_rst": str(rst_path), "source_rst_size_bytes": rst_path.stat().st_size, "source_rst_sha256": sha256_file(rst_path), "source_equilibrium_db": str(db_path), "source_equilibrium_db_size_bytes": db_path.stat().st_size, "source_equilibrium_db_sha256": sha256_file(db_path), "parent_connection_mapping_sha256": sha256_file(Path(inventory["mapping_path"])), "source_mesh_sha256": sha256_file(Path(inventory["mesh_path"])), "source_mass21_sha256": sha256_file(Path(inventory["mass_path"]))}  # 冻结两份二进制和全部关键输入身份。
    write_json(qa_dir / "source_identity.json", source_identity)  # 发布来源身份供执行前后复核。
    manifest = {"schema_version": 1, "status": "PREPARED_NOT_EXECUTED", "audit_name": audit_dir.name, "created_at_utc": datetime.now(timezone.utc).isoformat(), "source_run": Path(inventory["source_run"]).name, "source_jobname": inventory["jobname"], "analysis_scope": "142_GATE_3124_UXYZ_LOCAL_FREE_BODY_MOMENT_TENSION_ROTATION_ENERGY_ENDPOINT_AUDIT", "execution_scope": "POST1_ONLY_REUSE_EXISTING_DB_RST_NO_SOLVE_NO_SAVE", "expected_counts": {"gates": EXPECTED_GATE_COUNT, "uxyz_interfaces": EXPECTED_UXYZ_COUNT, "incident_link_elements": EXPECTED_INTERFACE_LINK_COUNT, "incident_rope_nodes_topology_only": EXPECTED_INCIDENT_ROPE_NODE_COUNT, "exported_interface_slave_nodes": EXPECTED_INTERFACE_ROPE_NODE_COUNT, "gate_nodes": EXPECTED_GATE_NODE_COUNT, "gate_elements": EXPECTED_GATE_ELEMENT_COUNT, "all_link180": EXPECTED_LINK180_COUNT}, "acceptance_limits": {"force_residual_over_gate_weight": FORCE_WEIGHT_RATIO_LIMIT, "moment_residual_over_weight_times_span": MOMENT_WEIGHT_SPAN_RATIO_LIMIT, "force_residual_over_gross_interface_force": FORCE_GROSS_RATIO_LIMIT, "moment_residual_over_gross_action_moment": MOMENT_GROSS_RATIO_LIMIT, "interface_wrench_ratio": INTERFACE_WRENCH_RATIO_LIMIT, "rigid_arm_length_absolute_mm": ARM_LENGTH_ABS_TOL_MM, "rigid_arm_length_relative": ARM_LENGTH_REL_TOL, "negative_element_energy_tolerance_n_mm": NEGATIVE_ENERGY_TOL_N_MM}, "hotspot_policy": "REVIEW_ONLY_NOT_AUTOMATIC_MODEL_FAILURE", "apdl_input": "solver/c10_interface_audit_post1.inp", "source_identity": "qa/source_identity.json", "reconcile_script": str(SCRIPT_PATH), "reconcile_script_sha256": sha256_file(SCRIPT_PATH)}  # 发布预先冻结的用途、工程量和验收阈值。
    write_json(audit_dir / "manifest.json", manifest)  # 发布审计运行清单。
    readme = "# C10 门架接口局部审计包\n\n本包只允许在独立目录中以 POST1 读取来源成功静力 DB/RST，不含 SOLU、SOLVE、ANTYPE、SAVE、RESWRITE 或文件删除命令。\n\n原始输出字段：`c10_ia_link180_force.csv` 为 `element_id, axial_force_n`；`c10_ia_gate_element_sene.csv` 为 `element_id, sene_n_mm`；`c10_ia_interface_gate_fsum.csv` 为 `master_node,fx_n,fy_n,fz_n,mx_n_mm,my_n_mm,mz_n_mm`；`c10_ia_gate_node_response.csv` 为 `node_id,x_mm,y_mm,z_mm,ux_mm,uy_mm,uz_mm,rx_rad,ry_rad,rz_rad`；`c10_ia_rope_node_response.csv` 为 `slave_node,x_mm,y_mm,z_mm,ux_mm,uy_mm,uz_mm`。\n\nPython 对账以仅选择 4260 个门架梁后的 master 单节点 FSUM 隔离 gate-side 元素节点合力，并按 `F接口=-FSUM梁-F质量`、`M接口=-M_FSUM梁` 恢复索系经 TYPE72 施加给门架的等效六分量，再与变形后刚臂 `M≈r×F` 及整座自由体对账。该口径不受 slave 节点同时连接底横梁、其他质量和相邻索段的污染。TYPE72 direct-elimination 刚臂本身不提供可独立读取的拉格朗日乘子反力，因此不伪造 MPC 元素力。\n\n热点排名属于 REVIEW，不可单独作为整体模型失败或构件设计验算。\n"  # 生成 JSON/CSV 相邻字段说明并声明 direct-elimination 输出边界。
    (audit_dir / "README.md").write_text(readme, encoding="utf-8", newline="\n")  # 发布人读说明。
    write_ledger(audit_dir)  # 为准备包全部普通文件生成完整摘要账本。
    return audit_dir  # 返回新建独立审计目录。


def parse_numeric_csv(path: Path, columns: int) -> list[list[float]]:  # 解析 MAPDL 无标题纯数值 CSV。
    """参数：文件和固定列数；返回：有限浮点行；约束：空行忽略，其余必须精确列数。"""  # 说明原始结果解析合同。
    require(path.is_file(), f"MAPDL 原始 CSV 不存在：{path}")  # 拒绝缺失结果。
    rows: list[list[float]] = []  # 初始化数值行列表。
    with path.open("r", encoding="latin-1", errors="strict", newline="") as stream:  # MAPDL ASCII 输出用 latin-1 无损读取。
        for line_number, raw_line in enumerate(stream, start=1):  # 保留一基行号供异常定位。
            text = raw_line.strip()  # 去除空白和换行。
            if not text:  # 空行不代表工程记录。
                continue  # 跳过空行。
            fields = [field.strip() for field in text.split(",")]  # 按逗号拆分纯数值字段。
            require(len(fields) == columns, f"{path.name}:{line_number} 列数 {len(fields)} != {columns}")  # 拒绝截断或续行。
            rows.append([finite_float(field.replace("D", "E").replace("d", "e"), f"{path.name}:{line_number}") for field in fields])  # 兼容 Fortran D 指数并验证有限性。
    return rows  # 返回全部严格数值行。


def parse_result_identity(path: Path) -> dict[str, float]:  # 解析 MAPDL 结果集身份单行摘要。
    """参数：身份 txt；返回：字段到数值；约束：八个命名字段各出现一次。"""  # 说明摘要解析合同。
    require(path.is_file(), f"结果身份文件不存在：{path}")  # 拒绝缺失身份。
    text = path.read_text(encoding="latin-1", errors="strict")  # 无损读取 MAPDL ASCII。
    names = ["LSTP", "SBST", "TIME", "LINK180", "GATE_ELEM", "INTERFACE", "GATE_NODE", "ROPE_NODE"]  # 冻结八个必需字段。
    values: dict[str, float] = {}  # 初始化身份字典。
    for token in text.replace("\n", ",").split(","):  # 将可能换行的摘要统一拆成逗号项。
        if "=" not in token:  # 非键值日志文本与摘要无关。
            continue  # 跳过无等号项。
        key, raw_value = token.strip().split("=", 1)  # 只在首个等号处分割。
        if key in names:  # 仅接收冻结字段。
            require(key not in values, f"结果身份字段重复：{key}")  # 拒绝重复字段。
            values[key] = finite_float(raw_value.replace("D", "E").replace("d", "e"), key)  # 解析并验证有限数。
    require(set(values) == set(names), f"结果身份字段不完整：{sorted(set(names) - set(values))}")  # 八项必须全部存在。
    return values  # 返回结果身份对象。


def load_node_results(path: Path, rotations: bool) -> dict[int, dict[str, Any]]:  # 解析门架或索节点响应表。
    """参数：原始 CSV 与转角开关；返回：节点结果字典；约束：节点号唯一。"""  # 说明节点结果合同。
    column_count = 10 if rotations else 7  # 门架节点十列，索节点七列。
    rows = parse_numeric_csv(path, column_count)  # 严格解析固定列数。
    result: dict[int, dict[str, Any]] = {}  # 初始化节点号索引。
    for row in rows:  # 遍历全部节点记录。
        node_id = int(round(row[0]))  # 从 F12.0 字段恢复整数节点号。
        require(abs(row[0] - node_id) <= 1.0e-9 and node_id not in result, f"节点号非整数或重复：{row[0]}")  # 拒绝损坏 ID。
        record: dict[str, Any] = {"original": row[1:4], "displacement": row[4:7], "current": vector_add(row[1:4], row[4:7])}  # 保存原始、位移和当前坐标。
        if rotations:  # 门架节点额外保存总转角分量。
            record["rotation"] = row[7:10]  # 保存全局 RX/RY/RZ，单位 rad。
        result[node_id] = record  # 按唯一节点号登记。
    return result  # 返回节点结果索引。


def reconcile_audit(audit_dir: Path) -> dict[str, Any]:  # 解析独立 POST1 输出并执行 142 座门架对账。
    """参数：已执行审计目录；返回：总报告；约束：来源 DB/RST 哈希必须前后不变。"""  # 说明最终化合同。
    audit_dir = audit_dir.resolve()  # 解析绝对审计目录。
    require(audit_dir.parent == ULTRA_RUNS_DIR.resolve() and audit_dir.name.startswith("C10_INTERFACE_AUDIT_"), "不是本项目 C10_INTERFACE_AUDIT 独立目录")  # 禁止误写来源运行。
    manifest = read_json(audit_dir / "manifest.json")  # 读取准备期清单。
    require(manifest.get("status") == "PREPARED_NOT_EXECUTED", "审计清单状态不是可最终化准备态")  # 禁止重复最终化或错误状态。
    require(sha256_file(SCRIPT_PATH) == str(manifest.get("reconcile_script_sha256", "")), "当前对账脚本已偏离准备期冻结摘要")  # 禁止代码漂移后解释既有原始结果。
    source_identity = read_json(audit_dir / "qa" / "source_identity.json")  # 读取来源二进制冻结身份。
    rst_path = Path(str(source_identity["source_rst"]))  # 恢复来源 RST 绝对路径。
    db_path = Path(str(source_identity["source_equilibrium_db"]))  # 恢复来源平衡 DB 绝对路径。
    require(sha256_file(rst_path) == source_identity["source_rst_sha256"], "来源 RST 在审计执行前后发生变化")  # 证明只读结果复用。
    require(sha256_file(db_path) == source_identity["source_equilibrium_db_sha256"], "来源平衡 DB 在审计执行前后发生变化")  # 证明 NOSAVE 未改来源数据库。
    solver_dir = audit_dir / "solver"  # 定位原始 POST1 输出目录。
    identity = parse_result_identity(solver_dir / "c10_ia_result_identity.txt")  # 解析实际结果集和工程量。
    require(math.isclose(identity["LSTP"], float(EXPECTED_FINAL_LOAD_STEP), rel_tol=0.0, abs_tol=1.0e-12), "POST1 结果不是载荷步二")  # 结果必须属于迁移终态载荷步。
    require(math.isclose(identity["TIME"], EXPECTED_FINAL_TIME, rel_tol=0.0, abs_tol=1.0e-12), "POST1 结果时间不是 1.001")  # 结果必须位于 beta=0 终点。
    require(math.isclose(identity["SBST"], round(identity["SBST"]), rel_tol=0.0, abs_tol=1.0e-12) and MINIMUM_FINAL_SUBSTEP <= int(round(identity["SBST"])) <= MAXIMUM_FINAL_SUBSTEP, "POST1 最终子步数不在 200..2000 自适应合同内")  # 结果必须来自批准的自适应步长范围。
    require(int(round(identity["LINK180"])) == EXPECTED_LINK180_COUNT and int(round(identity["GATE_ELEM"])) == EXPECTED_GATE_ELEMENT_COUNT and int(round(identity["INTERFACE"])) == EXPECTED_UXYZ_COUNT and int(round(identity["GATE_NODE"])) == EXPECTED_GATE_NODE_COUNT and int(round(identity["ROPE_NODE"])) == EXPECTED_INTERFACE_ROPE_NODE_COUNT, "MAPDL 结果身份工程量不闭合")  # 五类实测数量必须匹配准备期。
    link_rows = parse_numeric_csv(solver_dir / "c10_ia_link180_force.csv", 2)  # 读取全部 LINK180 轴力。
    require(len(link_rows) == EXPECTED_LINK180_COUNT, "LINK180 轴力行数不是 73692")  # 全局索必须全部覆盖。
    link_forces: dict[int, float] = {}  # 初始化元素号到轴力索引。
    for row in link_rows:  # 遍历全部索力记录。
        element_id = int(round(row[0]))  # 恢复整数元素号。
        require(abs(row[0] - element_id) <= 1.0e-9 and element_id not in link_forces, f"LINK180 元素号非整数或重复：{row[0]}")  # 拒绝重复或损坏 ID。
        link_forces[element_id] = row[1]  # 保存有符号轴力，正值表示拉力。
    nonpositive_links = sorted(element_id for element_id, force in link_forces.items() if force <= 0.0)  # 收集全部非正索力元素。
    gate_energy_rows = parse_numeric_csv(solver_dir / "c10_ia_gate_element_sene.csv", 2)  # 读取门架梁单元应变能。
    require(len(gate_energy_rows) == EXPECTED_GATE_ELEMENT_COUNT, "门架单元能量行数不是 4260")  # 全部门架梁必须覆盖。
    gate_energy: dict[int, float] = {}  # 初始化单元能量索引。
    for row in gate_energy_rows:  # 遍历全部门架能量记录。
        element_id = int(round(row[0]))  # 恢复整数门架单元号。
        require(abs(row[0] - element_id) <= 1.0e-9 and element_id not in gate_energy, f"门架单元号非整数或重复：{row[0]}")  # 拒绝损坏 ID。
        gate_energy[element_id] = row[1]  # 保存应变能，单位 N·mm。
    interface_fsum_rows = parse_numeric_csv(solver_dir / "c10_ia_interface_gate_fsum.csv", 7)  # 读取 3124 个 master 上仅由门架梁贡献的六分量节点合力。
    require(len(interface_fsum_rows) == EXPECTED_UXYZ_COUNT, "门架侧接口 FSUM 行数不是 3124")  # 每个 UXYZ 接口必须有且仅有一行原始六分量。
    interface_fsum: dict[int, dict[str, list[float]]] = {}  # 初始化 master 节点到原始力和力矩的索引。
    for row in interface_fsum_rows:  # 遍历全部门架侧单节点 FSUM 记录。
        master = int(round(row[0]))  # 从 F12.0 字段恢复整数 master 节点号。
        require(abs(row[0] - master) <= 1.0e-9 and master not in interface_fsum, f"接口 FSUM master 非整数或重复：{row[0]}")  # 拒绝损坏或重复的接口身份。
        interface_fsum[master] = {"force": row[1:4], "moment": row[4:7]}  # 保存选中门架梁对 master 的元素节点力与关于 master 的直接力矩。
    gate_nodes = load_node_results(solver_dir / "c10_ia_gate_node_response.csv", True)  # 读取门架节点坐标、位移和转角。
    rope_nodes = load_node_results(solver_dir / "c10_ia_rope_node_response.csv", False)  # 读取 3124 个接口 slave 节点坐标和位移。
    require(len(gate_nodes) == EXPECTED_GATE_NODE_COUNT and len(rope_nodes) == EXPECTED_INTERFACE_ROPE_NODE_COUNT, "节点结果唯一数不闭合")  # 防止重复 ID 掩盖行数。
    connection_rows = read_csv_dicts(audit_dir / "input_snapshot" / "uxyz_connection_mapping.csv")  # 读取 3124 条接口快照。
    incident_rows = read_csv_dicts(audit_dir / "input_snapshot" / "incident_link_map.csv")  # 读取 6248 条邻接索快照。
    gate_node_rows = read_csv_dicts(audit_dir / "input_snapshot" / "gate_nodes.csv")  # 读取门架节点语义快照。
    gate_element_rows = read_csv_dicts(audit_dir / "input_snapshot" / "gate_elements.csv")  # 读取门架单元语义与体积快照。
    gate_mass_rows = read_csv_dicts(audit_dir / "input_snapshot" / "gate_mass21_nodes.csv")  # 读取门架质量快照。
    gate_mass_by_node: dict[int, float] = {}  # 初始化门架物理节点到本门架空间 MASS21 质量的唯一索引。
    for row in gate_mass_rows:  # 遍历全部 4828 条门架质量记录并关闭节点唯一性门禁。
        node_id = int(row["apdl_node_id"])  # 读取门架质量所在物理节点号。
        mass = finite_float(row["mass_tonne"], f"gate_mass.{node_id}")  # 解析本门架分配质量，单位 tonne。
        require(node_id not in gate_mass_by_node and mass >= 0.0, f"门架质量节点 {node_id} 重复或质量为负")  # 拒绝重复质量和非物理负质量。
        gate_mass_by_node[node_id] = mass  # 保存该节点仅属于门架系统的空间质量。
    require(len(gate_mass_by_node) == EXPECTED_GATE_MASS_NODE_COUNT, "门架质量节点唯一数不是 4828")  # 防止重复节点掩盖质量行数。
    expected_master_ids = {int(row["master_node"]) for row in connection_rows}  # 从冻结连接映射恢复完整 master 节点集合。
    require(set(interface_fsum) == expected_master_ids and len(expected_master_ids) == EXPECTED_UXYZ_COUNT, "接口 FSUM master 集合与连接映射不一致")  # 原始接口力必须与逻辑接口一一覆盖。
    incidents_by_connection: dict[str, list[dict[str, str]]] = defaultdict(list)  # 初始化接口到两段索的归组。
    for row in incident_rows:  # 遍历 6248 条邻接索映射。
        incidents_by_connection[row["conn_id"]].append(row)  # 按 conn_id 登记左右索段。
    interface_records: list[dict[str, Any]] = []  # 初始化 3124 条接口力学记录。
    interface_forces_by_gate: dict[str, list[dict[str, Any]]] = defaultdict(list)  # 初始化门架到接口力归组。
    for connection in sorted(connection_rows, key=lambda row: row["conn_id"]):  # 按稳定 conn_id 逐接口计算。
        conn_id = connection["conn_id"]  # 读取接口唯一 ID。
        master = int(connection["master_node"])  # 读取门架梁轴 master 节点。
        slave = int(connection["slave_node"])  # 读取原索 slave 节点。
        require(master in gate_nodes and slave in rope_nodes, f"接口 {conn_id} 缺节点结果")  # 两侧节点结果必须存在。
        adjacent = incidents_by_connection.get(conn_id, [])  # 取得两段相邻索映射。
        require(len(adjacent) == 2, f"接口 {conn_id} 邻接索记录不是 2 条")  # 再次关闭 topology 门禁。
        adjacent = sorted(adjacent, key=lambda row: int(row["link_element"]))  # 按元素号稳定两段邻接索的输出顺序。
        adjacent_tensions: list[float] = []  # 初始化两段正轴力标量。
        for incident in adjacent:  # 逐段读取正拉门禁所需的 LINK180 有符号轴力。
            element_id = int(incident["link_element"])  # 读取相邻 LINK180 元素号。
            require(element_id in link_forces, f"接口 {conn_id} 的邻接索力缺失")  # 全局索力表必须覆盖两段邻接索。
            tension = link_forces[element_id]  # 读取当前轴力，正值为受拉。
            adjacent_tensions.append(tension)  # 保存接口正拉门禁数据。
        raw_fsum_force = interface_fsum[master]["force"]  # 读取选中门架梁作用于 master 的元素节点合力。
        raw_fsum_moment = interface_fsum[master]["moment"]  # 读取选中门架梁关于 master 的元素节点力矩。
        master_mass = gate_mass_by_node.get(master)  # 读取该 master 上仅属于门架系统的空间质量。
        require(master_mass is not None, f"接口 {conn_id} 的 master 缺门架 MASS21 质量")  # 每个 master 必须属于 4828 个门架质量节点。
        master_mass_force = [0.0, 0.0, -float(master_mass) * GRAVITY_MM_S2]  # 重建该 master 上门架质量的全局负 Z 重力，单位 N。
        interface_force = vector_sub(vector_scale(raw_fsum_force, -1.0), master_mass_force)  # 由节点平衡 F接口=−FSUM梁−F质量 隔离索系经 MPC 施加给门架的力。
        interface_moment = vector_scale(raw_fsum_moment, -1.0)  # master 上无门架质量偶矩，故接口偶矩等于门架梁 FSUM 直接力矩的反号。
        initial_arm = vector_sub(rope_nodes[slave]["original"], gate_nodes[master]["original"])  # 构造初始 TYPE72 刚臂向量。
        current_arm = vector_sub(rope_nodes[slave]["current"], gate_nodes[master]["current"])  # 构造变形后刚臂向量。
        initial_arm_length = vector_norm(initial_arm)  # 计算初始刚臂长度。
        current_arm_length = vector_norm(current_arm)  # 计算当前刚臂长度。
        arm_length_error = abs(current_arm_length - initial_arm_length)  # 计算与转动参数化无关的长度保持误差。
        arm_tolerance = max(ARM_LENGTH_ABS_TOL_MM, ARM_LENGTH_REL_TOL * max(initial_arm_length, 1.0))  # 组合绝对和相对容差。
        predicted_arm = rodrigues_rotate(gate_nodes[master]["rotation"], initial_arm)  # 以主节点转动向量诊断精确刚臂方向。
        rotation_vector_compatibility_error = vector_norm(vector_sub(current_arm, predicted_arm))  # 计算方向兼容误差但不作为硬门禁。
        predicted_interface_moment = cross(current_arm, interface_force)  # 把 slave 处接口力等效到 master 并计算理论刚臂偶矩 r×F。
        interface_wrench_residual = vector_sub(interface_moment, predicted_interface_moment)  # 计算 FSUM 接口偶矩与刚臂等效偶矩的三分量偏差。
        interface_wrench_scale = max(vector_norm(interface_moment), vector_norm(predicted_interface_moment), vector_norm(interface_force) * max(current_arm_length, 1.0), 1.0)  # 以直接偶矩、r×F 和 F·L 的最大值构造不小于 1 N·mm 的尺度。
        interface_wrench_ratio = vector_norm(interface_wrench_residual) / interface_wrench_scale  # 计算无量纲刚性接口力矩不闭合比例。
        record = {"conn_id": conn_id, "assembly_name": connection["assembly_name"], "master_node": master, "slave_node": slave, "rigid_element": int(connection["rigid_element"]), "raw_gate_beam_fsum_fx_n": raw_fsum_force[0], "raw_gate_beam_fsum_fy_n": raw_fsum_force[1], "raw_gate_beam_fsum_fz_n": raw_fsum_force[2], "raw_gate_beam_fsum_mx_n_mm": raw_fsum_moment[0], "raw_gate_beam_fsum_my_n_mm": raw_fsum_moment[1], "raw_gate_beam_fsum_mz_n_mm": raw_fsum_moment[2], "master_gate_mass_tonne": float(master_mass), "master_gate_mass_fx_n": master_mass_force[0], "master_gate_mass_fy_n": master_mass_force[1], "master_gate_mass_fz_n": master_mass_force[2], "interface_fx_n": interface_force[0], "interface_fy_n": interface_force[1], "interface_fz_n": interface_force[2], "interface_force_norm_n": vector_norm(interface_force), "interface_mx_n_mm": interface_moment[0], "interface_my_n_mm": interface_moment[1], "interface_mz_n_mm": interface_moment[2], "interface_moment_norm_n_mm": vector_norm(interface_moment), "predicted_r_cross_f_mx_n_mm": predicted_interface_moment[0], "predicted_r_cross_f_my_n_mm": predicted_interface_moment[1], "predicted_r_cross_f_mz_n_mm": predicted_interface_moment[2], "interface_wrench_residual_mx_n_mm": interface_wrench_residual[0], "interface_wrench_residual_my_n_mm": interface_wrench_residual[1], "interface_wrench_residual_mz_n_mm": interface_wrench_residual[2], "interface_wrench_residual_norm_n_mm": vector_norm(interface_wrench_residual), "interface_wrench_scale_n_mm": interface_wrench_scale, "interface_wrench_ratio": interface_wrench_ratio, "interface_wrench_gate_passed": interface_wrench_ratio <= INTERFACE_WRENCH_RATIO_LIMIT, "adjacent_link_1": int(adjacent[0]["link_element"]), "adjacent_link_2": int(adjacent[1]["link_element"]), "tension_1_n": adjacent_tensions[0], "tension_2_n": adjacent_tensions[1], "all_adjacent_tensions_positive": all(value > 0.0 for value in adjacent_tensions), "initial_arm_length_mm": initial_arm_length, "current_arm_length_mm": current_arm_length, "arm_length_error_mm": arm_length_error, "arm_length_tolerance_mm": arm_tolerance, "arm_length_gate_passed": arm_length_error <= arm_tolerance, "rotation_vector_compatibility_error_mm_review_only": rotation_vector_compatibility_error, "application_x_mm": gate_nodes[master]["current"][0], "application_y_mm": gate_nodes[master]["current"][1], "application_z_mm": gate_nodes[master]["current"][2]}  # 保存 gate-side 接口六分量、质量修正、索力、刚臂和 master 作用点完整记录。
        interface_records.append(record)  # 追加到全局接口表。
        interface_forces_by_gate[connection["assembly_name"]].append(record)  # 追加到所属门架自由体边界。
    require(len(interface_records) == EXPECTED_UXYZ_COUNT, "接口力学记录数不是 3124")  # 防止漏对账。
    mass_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)  # 初始化门架质量归组。
    for row in gate_mass_rows:  # 遍历全部 4828 条门架质量记录。
        mass_by_gate[row["assembly_name"]].append(row)  # 按门架装配归组。
    nodes_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)  # 初始化门架节点归组。
    for row in gate_node_rows:  # 遍历全部门架物理节点语义。
        nodes_by_gate[row["assembly_name"]].append(row)  # 按门架装配归组。
    elements_by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)  # 初始化门架梁单元归组。
    for row in gate_element_rows:  # 遍历全部 4260 个门架梁单元。
        elements_by_gate[row["assembly_name"]].append(row)  # 按门架装配归组。
    gate_records: list[dict[str, Any]] = []  # 初始化 142 条门架自由体结果。
    rotation_hotspots: list[dict[str, Any]] = []  # 初始化节点转角热点候选。
    curvature_hotspots: list[dict[str, Any]] = []  # 初始化单元端转角差热点候选。
    energy_hotspots: list[dict[str, Any]] = []  # 初始化单元能量密度热点候选。
    for assembly in sorted(interface_forces_by_gate):  # 按门架 ID 稳定遍历 142 座门架。
        masses = mass_by_gate[assembly]  # 取得当前门架 34 个 MASS21 质量节点。
        interfaces = interface_forces_by_gate[assembly]  # 取得当前门架 22 个索接口边界力。
        require(len(masses) == 34 and len(interfaces) == 22, f"{assembly} 的质量或接口工程量不闭合")  # 再次确认每座固定工程量。
        total_mass = sum(finite_float(row["mass_tonne"], f"{assembly}.mass") for row in masses)  # 计算门架质量，单位 tonne。
        require(total_mass > 0.0, f"{assembly} 总质量非正")  # 门架必须有正自重。
        weighted_position = [0.0, 0.0, 0.0]  # 初始化当前质量一阶矩。
        for mass_row in masses:  # 遍历当前门架质量节点。
            node_id = int(mass_row["apdl_node_id"])  # 读取质量节点号。
            mass = finite_float(mass_row["mass_tonne"], f"{assembly}.{node_id}.mass")  # 读取节点质量。
            require(node_id in gate_nodes and mass >= 0.0, f"{assembly} 质量节点缺结果或质量为负")  # 拒绝缺失节点或负质量。
            weighted_position = vector_add(weighted_position, vector_scale(gate_nodes[node_id]["current"], mass))  # 累加当前质量一阶矩。
        reference = vector_scale(weighted_position, 1.0 / total_mass)  # 以当前门架质量中心作为力矩参考点。
        force_vectors: list[list[float]] = []  # 初始化门架全部外力向量。
        moment_vectors: list[list[float]] = []  # 初始化全部外力及直接偶矩关于质量中心的力矩向量。
        interface_force_norm_sum = 0.0  # 初始化接口力模总和，作为 gross 归一化尺度。
        for interface in interfaces:  # 加入 22 个由 gate-side FSUM 隔离的接口六分量。
            force = [float(interface["interface_fx_n"]), float(interface["interface_fy_n"]), float(interface["interface_fz_n"])]  # 恢复三分量接口力。
            couple = [float(interface["interface_mx_n_mm"]), float(interface["interface_my_n_mm"]), float(interface["interface_mz_n_mm"])]  # 恢复接口在 master 处的直接偶矩。
            point = [float(interface["application_x_mm"]), float(interface["application_y_mm"]), float(interface["application_z_mm"])]  # 恢复 master 当前作用点。
            force_vectors.append(force)  # 加入自由体外力列表。
            moment_vectors.append(vector_add(cross(vector_sub(point, reference), force), couple))  # 加入力对质量中心的力矩及 master 直接偶矩。
            interface_force_norm_sum += vector_norm(force)  # 累加接口力模。
        for mass_row in masses:  # 加入 34 个空间 MASS21 重力体力。
            node_id = int(mass_row["apdl_node_id"])  # 读取质量节点号。
            mass = finite_float(mass_row["mass_tonne"], f"{assembly}.{node_id}.mass")  # 读取节点质量。
            mass_force = [0.0, 0.0, -mass * GRAVITY_MM_S2]  # 以全局负 Z 方向重建节点重力，单位 N。
            force_vectors.append(mass_force)  # 加入门架质量节点外力列表。
            moment_vectors.append(cross(vector_sub(gate_nodes[node_id]["current"], reference), mass_force))  # 加入重力关于当前质量中心的力矩。
        force_residual = vector_add(*force_vectors)  # 计算门架自由体总力残差。
        moment_residual = vector_add(*moment_vectors)  # 计算门架自由体总力矩残差。
        weight = total_mass * GRAVITY_MM_S2  # 计算门架总重量，单位 N。
        characteristic_points = [gate_nodes[int(row["apdl_node_id"])]["current"] for row in nodes_by_gate[assembly]] + [[float(item["application_x_mm"]), float(item["application_y_mm"]), float(item["application_z_mm"])] for item in interfaces]  # 汇总门架和接口当前位置。
        characteristic_length = max(1.0, max(vector_norm(vector_sub(point, reference)) for point in characteristic_points))  # 定义不小于 1 mm 的特征跨度。
        gross_moment = max(1.0, sum(vector_norm(moment) for moment in moment_vectors))  # 计算全部作用力矩模和，避免分母为零。
        force_weight_ratio = vector_norm(force_residual) / max(weight, 1.0)  # 计算残差相对门架重量比例。
        moment_weight_span_ratio = vector_norm(moment_residual) / max(weight * characteristic_length, 1.0)  # 计算力矩残差相对重量乘跨度比例。
        force_gross_ratio = vector_norm(force_residual) / max(interface_force_norm_sum, 1.0)  # 计算残差相对 gross 接口力比例。
        moment_gross_ratio = vector_norm(moment_residual) / gross_moment  # 计算力矩残差相对 gross 作用比例。
        local_elements = elements_by_gate[assembly]  # 取得当前门架 30 个梁单元。
        local_energy_values = [gate_energy[int(row["apdl_elem_id"])] for row in local_elements]  # 读取当前门架全部单元能量。
        negative_energy_count = sum(value < -NEGATIVE_ENERGY_TOL_N_MM for value in local_energy_values)  # 统计超出舍入容差的负能量。
        total_gate_energy = sum(local_energy_values)  # 汇总门架应变能，单位 N·mm。
        arm_pass = all(bool(item["arm_length_gate_passed"]) for item in interfaces)  # 汇总 22 条 TYPE72 长度保持门禁。
        wrench_pass = all(bool(item["interface_wrench_gate_passed"]) for item in interfaces)  # 汇总 22 条接口六分量与 r×F 一致性门禁。
        tension_pass = all(bool(item["all_adjacent_tensions_positive"]) for item in interfaces)  # 汇总接口相邻索正拉门禁。
        equilibrium_pass = force_weight_ratio <= FORCE_WEIGHT_RATIO_LIMIT and moment_weight_span_ratio <= MOMENT_WEIGHT_SPAN_RATIO_LIMIT and force_gross_ratio <= FORCE_GROSS_RATIO_LIMIT and moment_gross_ratio <= MOMENT_GROSS_RATIO_LIMIT  # 同时执行工程尺度和 gross 数值尺度门禁。
        gate_pass = equilibrium_pass and arm_pass and wrench_pass and tension_pass and negative_energy_count == 0 and total_gate_energy > 0.0  # 形成单座门架局部审计硬结论。
        gate_records.append({"assembly_name": assembly, "mass_tonne": total_mass, "weight_n": weight, "reference_x_mm": reference[0], "reference_y_mm": reference[1], "reference_z_mm": reference[2], "characteristic_length_mm": characteristic_length, "residual_fx_n": force_residual[0], "residual_fy_n": force_residual[1], "residual_fz_n": force_residual[2], "force_residual_norm_n": vector_norm(force_residual), "residual_mx_n_mm": moment_residual[0], "residual_my_n_mm": moment_residual[1], "residual_mz_n_mm": moment_residual[2], "moment_residual_norm_n_mm": vector_norm(moment_residual), "force_residual_over_weight": force_weight_ratio, "moment_residual_over_weight_times_span": moment_weight_span_ratio, "force_residual_over_gross_interface_force": force_gross_ratio, "moment_residual_over_gross_action_moment": moment_gross_ratio, "interface_arm_gate_passed": arm_pass, "interface_wrench_gate_passed": wrench_pass, "interface_tension_gate_passed": tension_pass, "gate_sene_n_mm": total_gate_energy, "negative_gate_element_energy_count": negative_energy_count, "local_equilibrium_gate_passed": equilibrium_pass, "status": "PASS" if gate_pass else "REJECTED"})  # 保存单座门架完整自由体结论。
        for node_row in nodes_by_gate[assembly]:  # 构造门架节点总转角热点候选。
            node_id = int(node_row["apdl_node_id"])  # 读取物理节点号。
            magnitude = vector_norm(gate_nodes[node_id]["rotation"])  # 计算总转角幅值，单位 rad。
            rotation_hotspots.append({"assembly_name": assembly, "node_id": node_id, "role": node_row["role"], "rotation_magnitude_rad": magnitude})  # 保存节点语义和转角幅值。
        for element_row in local_elements:  # 构造单元端转角差与能量密度热点候选。
            element_id = int(element_row["apdl_elem_id"])  # 读取门架梁单元号。
            n1 = int(element_row["n1"])  # 读取 I 端节点号。
            n2 = int(element_row["n2"])  # 读取 J 端节点号。
            length = finite_float(element_row["length_mm"], f"{element_id}.length")  # 读取初始单元长度，单位 mm。
            volume = finite_float(element_row["volume_mm3"], f"{element_id}.volume")  # 读取单元体积，单位 mm³。
            require(n1 in gate_nodes and n2 in gate_nodes and length > 0.0 and volume > 0.0, f"门架单元 {element_id} 几何或节点结果非法")  # 拒绝零长、零体积或缺节点。
            rotation_jump = vector_norm(vector_sub(gate_nodes[n2]["rotation"], gate_nodes[n1]["rotation"]))  # 计算端节点转角向量差。
            curvature_proxy = rotation_jump / length  # 计算 rad/mm 转角梯度代理量，不替代梁纤维应变。
            energy = gate_energy[element_id]  # 读取当前单元应变能。
            energy_density = energy / volume  # 计算 N/mm² 能量密度代理量。
            curvature_hotspots.append({"assembly_name": assembly, "element_id": element_id, "member": element_row["member"], "rotation_jump_rad": rotation_jump, "curvature_proxy_rad_per_mm": curvature_proxy})  # 保存转角差热点候选。
            energy_hotspots.append({"assembly_name": assembly, "element_id": element_id, "member": element_row["member"], "sene_n_mm": energy, "volume_mm3": volume, "energy_density_n_per_mm2": energy_density})  # 保存能量密度热点候选。
    require(len(gate_records) == EXPECTED_GATE_COUNT, "门架自由体记录数不是 142")  # 全部门架必须有结论。
    def annotate_hotspots(records: list[dict[str, Any]], value_key: str, group_key: str) -> list[dict[str, Any]]:  # 按同类中位数和全局 99% 分位标记 REVIEW 热点。
        """参数：候选记录、数值字段和归组字段；返回：排序后的前 30 条；约束：只标记不改变硬门禁。"""  # 说明热点函数合同。
        groups: dict[str, list[float]] = defaultdict(list)  # 初始化同构件正值基线。
        for record in records:  # 遍历全部候选记录。
            value = float(record[value_key])  # 读取目标响应值。
            if value > 0.0:  # 仅正值进入倍数基线。
                groups[str(record[group_key])].append(value)  # 按角色或构件类型归组。
        global_values = [float(record[value_key]) for record in records]  # 汇总全部响应供全局分位数。
        global_p99 = percentile(global_values, 0.99)  # 计算预定义 99% 排名阈值。
        annotated: list[dict[str, Any]] = []  # 初始化带标记记录。
        for record in records:  # 第二次遍历并附加基线字段。
            group_values = groups.get(str(record[group_key]), [])  # 读取同类正值集合。
            median = statistics.median(group_values) if group_values else 0.0  # 无正值时中位数设零并禁止倍数判定。
            value = float(record[value_key])  # 读取当前响应。
            copy = dict(record)  # 创建副本避免修改基础记录。
            copy["same_group_positive_median"] = median  # 保存同类中位数基线。
            copy["global_p99"] = global_p99  # 保存全局 99% 分位阈值。
            copy["review_hotspot"] = median > 0.0 and value >= global_p99 and value > HOTSPOT_MEDIAN_FACTOR * median  # 同时满足高分位和五倍中位数才标记 REVIEW。
            annotated.append(copy)  # 保存带标记记录。
        return sorted(annotated, key=lambda record: float(record[value_key]), reverse=True)[:TOP_HOTSPOT_COUNT]  # 返回响应最高的三十条。
    rotation_rank = annotate_hotspots(rotation_hotspots, "rotation_magnitude_rad", "role")  # 生成节点转角热点排名。
    curvature_rank = annotate_hotspots(curvature_hotspots, "curvature_proxy_rad_per_mm", "member")  # 生成端转角差热点排名。
    energy_rank = annotate_hotspots(energy_hotspots, "energy_density_n_per_mm2", "member")  # 生成能量密度热点排名。
    all_gate_pass = all(record["status"] == "PASS" for record in gate_records)  # 汇总 142 座门架硬门禁。
    all_interface_arm_pass = all(bool(record["arm_length_gate_passed"]) for record in interface_records)  # 汇总 3124 条刚臂长度门禁。
    all_interface_wrench_pass = all(bool(record["interface_wrench_gate_passed"]) for record in interface_records)  # 汇总 3124 条接口六分量与 r×F 一致性门禁。
    all_interface_tension_pass = all(bool(record["all_adjacent_tensions_positive"]) for record in interface_records)  # 汇总 6248 条接口相邻索正拉门禁。
    global_tension_pass = len(nonpositive_links) == 0  # 全部 73692 根 LINK180 必须严格正拉。
    final_pass = all_gate_pass and all_interface_arm_pass and all_interface_wrench_pass and all_interface_tension_pass and global_tension_pass  # 形成审计总硬结论。
    interface_fields = list(interface_records[0].keys())  # 以第一条稳定记录冻结接口 CSV 列顺序。
    gate_fields = list(gate_records[0].keys())  # 以第一条稳定记录冻结门架 CSV 列顺序。
    write_csv(audit_dir / "qa" / "interface_force_and_kinematics.csv", interface_fields, interface_records)  # 发布 3124 条接口力和刚臂结果。
    write_csv(audit_dir / "qa" / "gate_free_body_balance.csv", gate_fields, gate_records)  # 发布 142 座门架自由体结果。
    tension_report = {"schema_version": 1, "status": "PASS" if global_tension_pass else "REJECTED", "result_set": identity, "link180_count": len(link_forces), "positive_count": len(link_forces) - len(nonpositive_links), "nonpositive_count": len(nonpositive_links), "nonpositive_element_ids": nonpositive_links, "minimum_force_n": min(link_forces.values()), "minimum_force_element_id": min(link_forces, key=link_forces.get), "maximum_force_n": max(link_forces.values()), "maximum_force_element_id": max(link_forces, key=link_forces.get), "interface_incident_link_count": EXPECTED_INTERFACE_LINK_COUNT, "interface_incident_all_positive": all_interface_tension_pass}  # 构造全局和接口正拉报告。
    write_json(audit_dir / "qa" / "link180_positive_tension_report.json", tension_report)  # 发布正拉机器报告。
    hotspot_report = {"schema_version": 1, "status": "REVIEW_ONLY", "policy": "热点仅用于定位，不单独判整体模型失败或完成构件设计验算。", "rotation_top": rotation_rank, "curvature_proxy_top": curvature_rank, "energy_density_top": energy_rank, "threshold_policy": {"global_percentile": 0.99, "same_group_positive_median_factor": HOTSPOT_MEDIAN_FACTOR, "top_record_limit": TOP_HOTSPOT_COUNT}}  # 构造转角和能量热点报告。
    write_json(audit_dir / "qa" / "rotation_energy_hotspots.json", hotspot_report)  # 发布 REVIEW 热点清单。
    free_body_report = {"schema_version": 1, "status": "PASS" if all_gate_pass else "REJECTED", "gate_count": len(gate_records), "passed_gate_count": sum(record["status"] == "PASS" for record in gate_records), "rejected_gate_count": sum(record["status"] != "PASS" for record in gate_records), "reference_point": "CURRENT_GATE_MASS_CENTER", "interface_force_reconstruction": "NEGATIVE_GATE_BEAM_ONLY_MASTER_FSUM_MINUS_MASTER_GATE_MASS21_GRAVITY_WITH_DIRECT_MASTER_COUPLE", "body_force_reconstruction": "SPATIAL_GATE_MASS21_TIMES_9806_MM_PER_S2_IN_GLOBAL_NEGATIVE_Z", "acceptance_limits": manifest["acceptance_limits"], "maximum_interface_wrench_ratio": max(float(record["interface_wrench_ratio"]) for record in interface_records), "maximum_force_residual_over_weight": max(float(record["force_residual_over_weight"]) for record in gate_records), "maximum_moment_residual_over_weight_times_span": max(float(record["moment_residual_over_weight_times_span"]) for record in gate_records), "maximum_force_residual_over_gross_interface_force": max(float(record["force_residual_over_gross_interface_force"]) for record in gate_records), "maximum_moment_residual_over_gross_action_moment": max(float(record["moment_residual_over_gross_action_moment"]) for record in gate_records), "rejected_gate_ids": [record["assembly_name"] for record in gate_records if record["status"] != "PASS"]}  # 构造门架自由体总报告。
    write_json(audit_dir / "qa" / "substructure_free_body_report.json", free_body_report)  # 发布局部自由体机器报告。
    final_report = {"schema_version": 1, "status": "PASS" if final_pass else "REJECTED", "audit_name": audit_dir.name, "source_run": source_identity["source_run"], "result_set": identity, "counts": {"gates": len(gate_records), "uxyz_interfaces": len(interface_records), "gate_side_fsum_interfaces": len(interface_fsum), "interface_incident_links": len(incident_rows), "all_link180": len(link_forces), "gate_nodes": len(gate_nodes), "gate_elements": len(gate_energy)}, "gates_all_passed": all_gate_pass, "uxyz_rigid_arm_lengths_all_passed": all_interface_arm_pass, "uxyz_interface_wrenches_all_passed": all_interface_wrench_pass, "interface_incident_links_all_positive": all_interface_tension_pass, "all_link180_positive": global_tension_pass, "hotspots_require_review": any(bool(record["review_hotspot"]) for record in rotation_rank + curvature_rank + energy_rank), "source_db_rst_unchanged": True, "limitations": ["TYPE72 direct-elimination 刚臂没有可独立读取的拉格朗日乘子反力；接口六分量由仅选门架梁的 master 单节点 FSUM、元素节点力符号反转和本门架 master MASS21 重力修正隔离。", "接口相邻两段 LINK180 只用于拓扑覆盖与正拉门禁；slave 同时连接的其他横梁、质量和索段使两段索力矢量和不等于纯门架接口力。", "当前静力 RST 仅支持已保存端点结果；未保存的逐子步接口力、转角和梁内力历程不能由 POST1 恢复。", "FSUM 力在 NLGEOM 下仍可用，但其力矩存在官方的大转动警告；本审计用单一 master、以该 master 为 SPOINT 并同时要求整座自由体闭合，仍需一次批准版本的 POST1 烟雾测试确认命令与符号。", "门架采用 BEAM188 线构件和零密度有限梁加空间 MASS21，自由体审计不等价于焊缝、节点板、局部屈曲或接触验算。", "Rodrigues 转动向量兼容误差只作诊断，不作为硬门禁；硬门禁使用与转角参数化无关的刚臂长度保持。"]}  # 汇总覆盖、平衡、正拉、只读来源和适用边界。
    write_json(audit_dir / "qa" / "interface_audit_status.json", final_report)  # 发布总状态。
    manifest["status"] = "COMPLETED_PASS" if final_pass else "COMPLETED_REJECTED"  # 更新独立审计运行状态。
    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()  # 记录最终化 UTC 时间。
    manifest["result_status"] = final_report["status"]  # 在清单中复制唯一总状态。
    write_json(audit_dir / "manifest.json", manifest)  # 原子更新独立审计清单。
    write_ledger(audit_dir)  # 以最终工件集合重建完整摘要账本。
    return final_report  # 返回总报告供 CLI 输出。


def write_ledger(root: Path) -> None:  # 为独立审计目录生成除账本自身外的完整 SHA-256 清单。
    """参数：审计根目录；返回：None；约束：按 POSIX 相对路径排序且不跟随目录。"""  # 说明工件账本合同。
    ledger_path = root / "artifact_hashes.sha256"  # 固定账本路径。
    files = sorted(path for path in root.rglob("*") if path.is_file() and path != ledger_path)  # 收集全部普通文件并排除自引用账本。
    lines = [f"{sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in files]  # 为每个文件生成摘要和稳定相对路径。
    temporary = ledger_path.with_suffix(".sha256.tmp")  # 创建相邻临时账本。
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")  # 一次写出完整有序账本。
    temporary.replace(ledger_path)  # 原子替换最终账本。


def inventory_summary(inventory: dict[str, Any]) -> dict[str, Any]:  # 把完整内存 inventory 压缩为只读盘点摘要。
    """参数：完整 inventory；返回：可 JSON 序列化摘要；约束：不泄露大表。"""  # 说明只读输出合同。
    return {"status": "INVENTORY_PASSED", "source_run": Path(inventory["source_run"]).name, "jobname": inventory["jobname"], "gate_count": len(inventory["gate_assemblies"]), "uxyz_interface_count": len(inventory["uxyz_rows"]), "incident_link_count": len(inventory["incident_rows"]), "incident_rope_node_count_topology_only": len(inventory["incident_rope_node_ids"]), "exported_interface_slave_node_count": len(inventory["rope_node_ids"]), "interface_master_node_count": len(inventory["master_node_ids"]), "gate_node_count": len(inventory["gate_node_ids"]), "gate_element_count": len(inventory["gate_element_ids"]), "gate_mass_node_count": len(inventory["gate_mass_rows"]), "per_gate_contract": {"uxyz_interfaces": 22, "physical_nodes": 34, "beam_elements": 30, "mass21_nodes": 34}, "result_dependency": {"source_rst": str(inventory["rst_path"]), "source_equilibrium_db": str(inventory["equilibrium_db_path"]), "requires_final_static_status": True}}  # 返回工程量、固定每座合同和未来结果依赖。


def parse_args(argv: Sequence[str]) -> argparse.Namespace:  # 输入命令行参数并返回解析命名空间。
    """参数：argv；返回：Namespace；约束：命令必须为 inventory、prepare 或 reconcile。"""  # 说明 CLI 合同。
    parser = argparse.ArgumentParser(description="准备或复核 C10 门架接口只读局部平衡审计。")  # 创建顶层解析器。
    subparsers = parser.add_subparsers(dest="command", required=True)  # 要求显式选择子命令。
    inventory_parser = subparsers.add_parser("inventory", help="只读盘点来源工程量，不要求静力成功。")  # 定义盘点子命令。
    inventory_parser.add_argument("--source-run", type=Path, required=True, help="待盘点 C10 运行目录。")  # 接收来源运行路径。
    prepare_parser = subparsers.add_parser("prepare", help="从已最终化成功静力运行创建新审计包。")  # 定义准备子命令。
    prepare_parser.add_argument("--source-run", type=Path, required=True, help="已通过静力门禁的 C10 运行目录。")  # 接收成功来源运行。
    prepare_parser.add_argument("--audit-dir", type=Path, help="可选的新审计目录；必须尚不存在且位于 ultra_runs。")  # 允许调用方冻结唯一目录名。
    reconcile_parser = subparsers.add_parser("reconcile", help="解析已完成的 POST1 原始输出并发布对账报告。")  # 定义最终化子命令。
    reconcile_parser.add_argument("--audit-dir", type=Path, required=True, help="已执行 POST1 的独立审计目录。")  # 接收审计目录路径。
    return parser.parse_args(list(argv))  # 解析参数副本并返回结果。


def main(argv: Sequence[str] | None = None) -> int:  # 输入可选参数序列并执行唯一子命令。
    """参数：argv 或 None；返回：进程退出码；约束：异常由顶层打印并返回 1。"""  # 说明程序入口合同。
    arguments = parse_args(sys.argv[1:] if argv is None else argv)  # 使用显式参数或进程参数。
    if arguments.command == "inventory":  # 只读盘点不创建任何文件。
        summary = inventory_summary(build_inventory(arguments.source_run, False))  # 执行全部几何和连接工程量门禁。
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # 向标准输出发布盘点 JSON。
        return 0  # 盘点通过返回零。
    if arguments.command == "prepare":  # 成功静力后创建独立审计准备包。
        audit_dir = prepare_audit(arguments.source_run, arguments.audit_dir)  # 创建唯一新目录并冻结输入。
        print(str(audit_dir))  # 输出新审计目录供后续执行器使用。
        return 0  # 准备成功返回零。
    if arguments.command == "reconcile":  # POST1 完成后解析原始输出。
        result = reconcile_audit(arguments.audit_dir)  # 执行来源不变、覆盖、平衡、正拉和热点审计。
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))  # 向标准输出发布总状态。
        return 0 if result["status"] == "PASS" else 2  # 通过返回零，工程门禁拒绝返回二。
    raise RuntimeError(f"未知命令：{arguments.command}")  # 理论不可达分支仍显式 fail-closed。


if __name__ == "__main__":  # 仅直接执行脚本时进入 CLI。
    try:  # 捕获工程门禁异常并转换为稳定退出码。
        raise SystemExit(main())  # 执行主函数并使用其退出码结束进程。
    except Exception as error:  # 捕获所有未关闭异常，避免伪装成功。
        print(f"ERROR: {error}", file=sys.stderr)  # 向标准错误输出明确原因。
        raise SystemExit(1)  # 任何异常统一返回非零退出码一。
