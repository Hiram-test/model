#!/usr/bin/env python3  # 以工作区 Python 运行可复核的 H10 子结构凝聚。
import csv  # 读取门架—索接口权威 CSV。
import hashlib  # 记录输入文件 SHA-256 以固定数据版本。
import json  # 写出机器可读审计和刚度矩阵。
from pathlib import Path  # 稳定处理工作区路径。
import numpy as np  # 组装与凝聚刚度矩阵。
from scipy.linalg import null_space  # 构造刚体模态的正交补空间。
from scipy.optimize import nnls  # 拟合非负轴向等效杆刚度。
from scipy.sparse import bmat, coo_matrix, csc_matrix  # 组装稀疏梁刚度和约束鞍点矩阵。
from scipy.sparse.linalg import splu  # 对多右端项复用稀疏 LU 分解。

ROOT = Path(__file__).resolve().parents[2]  # tmp/gate_passage_condensation 的上两级是工作区根目录。
SOURCE = ROOT / "tmp" / "mct_pair_sources"  # 权威有限门架与横通道源文件目录。
OUTPUT = ROOT / "tmp" / "gate_passage_condensation"  # 本次静力凝聚输出目录。
APDL = SOURCE / "apply_finite_gates_and_passages_v2.inp"  # 含 142 品门架与 21 道完整横通道的 APDL。
COUPLINGS = SOURCE / "passage_gate_rope_couplings.csv"  # 6/16 根索到门架轴线的权威映射。
E_MODULUS = 206000.0  # 钢材弹性模量，单位 N/mm2。
POISSON = 0.31  # 钢材泊松比。
G_MODULUS = E_MODULUS / (2.0 * (1.0 + POISSON))  # 钢材剪切模量，单位 N/mm2。
LENGTH_SCALE = 1000.0  # 旋转自由度正定审计采用 1 m 位移尺度。
PORTS = ("B_L", "T_L", "B_R", "T_R")  # 四个中心线接口的稳定顺序。
PORT_INDEX = {name: index for index, name in enumerate(PORTS)}  # 接口名到矩阵块号的映射。
GATE_NODE_RANGES = ((2001985, 2002048), (2006529, 2006592))  # H10 对应 CW1/CW2 第 32 品门架节点。
PASSAGE_NODE_RANGE = (2017891, 2018868)  # H10 完整横通道节点范围。
GATE_ELEMENT_RANGES = ((2000931, 2000960), (2003061, 2003090))  # 两品有限门架 BEAM188 单元范围。
PASSAGE_ELEMENT_RANGE = (2010012, 2010650)  # H10 完整横通道 BEAM188 单元范围。

def in_ranges(value, ranges):  # 判断稳定编号是否位于目标连续号段。
    return any(start <= value <= end for start, end in ranges)  # 任一号段命中即属于 H10 子结构。

def skew(vector):  # 返回满足 skew(a)b=a×b 的反对称矩阵。
    x_value, y_value, z_value = vector  # 展开三维向量分量。
    return np.array(((0.0, -z_value, y_value), (z_value, 0.0, -x_value), (-y_value, x_value, 0.0)), dtype=float)  # 构造叉乘矩阵。

def rigid_map(offset):  # 从刚性截面中心六自由度映射到偏置点六自由度。
    mapping = np.zeros((6, 6), dtype=float)  # 初始化六自由度刚体映射。
    mapping[:3, :3] = np.eye(3)  # 偏置点平动包含中心平动。
    mapping[:3, 3:] = -skew(offset)  # theta×r 等于 -skew(r)theta。
    mapping[3:, 3:] = np.eye(3)  # ALL 语义下偏置点转角等于中心转角。
    return mapping  # 返回完整刚体映射。

def translation_rigid_map(offset):  # 从中心六自由度映射到偏置点三项平动。
    mapping = np.zeros((3, 6), dtype=float)  # 初始化三平动映射。
    mapping[:, :3] = np.eye(3)  # 保留中心平动。
    mapping[:, 3:] = -skew(offset)  # 保留中心转角产生的偏置平动。
    return mapping  # 不生成或约束索节点转角。

def parse_apdl():  # 读取 H10 两品门架和一品横通道的节点、梁与 CERIG 关系。
    lines = APDL.read_text(encoding="utf-8").splitlines()  # 一次读取便于保持材料和截面状态。
    node_ranges = GATE_NODE_RANGES + (PASSAGE_NODE_RANGE,)  # 合并 H10 节点号段。
    element_ranges = GATE_ELEMENT_RANGES + (PASSAGE_ELEMENT_RANGE,)  # 合并 H10 单元号段。
    nodes = {}  # 保存 APDL 全部新增节点坐标，包含方向节点。
    elements = []  # 保存目标 H10 BEAM188 单元。
    cerig = []  # 保存至少一端属于 H10 的 CERIG 关系。
    sections = {}  # 保存 ASEC 的 A、Iyy、Izz、J。
    densities = {}  # 保存材料密度以证明刚度凝聚未携带重复质量。
    current_material = None  # 跟踪 EN 命令前最近的 MAT。
    current_section = None  # 跟踪 EN 命令前最近的 SECNUM。
    pending_section = None  # 跟踪 SECTYPE 后等待 SECDATA 的截面号。
    for line_number, raw_line in enumerate(lines, start=1):  # 顺序扫描 APDL 命令。
        command = raw_line.split("!", 1)[0].strip()  # 删除行尾注释并保留命令主体。
        if not command:  # 跳过空行与纯注释。
            continue  # 当前行不影响解析状态。
        fields = [field.strip() for field in command.split(",")]  # 按 APDL 逗号字段拆分。
        keyword = fields[0].upper()  # 命令关键字统一为大写。
        if keyword == "N" and len(fields) >= 5:  # 读取节点编号和三维坐标。
            node_id = int(fields[1])  # APDL 稳定节点号。
            nodes[node_id] = np.array(tuple(float(value) for value in fields[2:5]), dtype=float)  # 单位为 mm。
        elif keyword == "SECTYPE" and len(fields) >= 2:  # 记录下一条 SECDATA 所属截面。
            pending_section = int(fields[1])  # 截面号与材料号在本模型中一一对应。
        elif keyword == "SECDATA" and pending_section is not None:  # 读取 ASEC 六个主参数。
            values = [float(value) for value in fields[1:] if value != ""]  # ASEC 最多按 A、Iyy、Iyz、Izz、Iw、J、CG、SH、TK、TS 的 14 项读取。
            shear_xz = values[12] if len(values) >= 14 else 1.0  # 源 APDL 仅写六项时按 ASEC 缺省 TSxz=1.0 复现。
            shear_xy = values[13] if len(values) >= 14 else 1.0  # 源 APDL 仅写六项时按 ASEC 缺省 TSxy=1.0 复现。
            sections[pending_section] = {"A": values[0], "Iyy": values[1], "Izz": values[3], "J": values[5], "TSxz": shear_xz, "TSxy": shear_xy, "SECDATA_count": len(values)}  # 保留线性 Timoshenko 梁所需项与字段计数。
            pending_section = None  # 防止后续无关 SECDATA 覆盖当前截面。
        elif keyword == "MAT" and len(fields) >= 2:  # 更新当前材料号。
            current_material = int(fields[1])  # 六组材料当前均取相同 E 和 nu。
        elif keyword == "MP" and len(fields) >= 4 and fields[1].upper() == "DENS":  # 读取材料密度定义。
            densities[int(fields[2])] = float(fields[3])  # N-mm-tonne-s 下密度应为零。
        elif keyword == "SECNUM" and len(fields) >= 2:  # 更新当前截面号。
            current_section = int(fields[1])  # 后续 EN 继承该截面。
        elif keyword == "EN" and len(fields) >= 5:  # 读取三节点 BEAM188，其中第三节点只定方向。
            element_id = int(fields[1])  # 稳定单元号。
            if in_ranges(element_id, element_ranges):  # 仅保留 H10 两门架和一横通道。
                elements.append({"id": element_id, "n1": int(fields[2]), "n2": int(fields[3]), "orient": int(fields[4]), "material": current_material, "section": current_section})  # 保存梁定义。
        elif keyword == "CERIG" and len(fields) >= 4:  # 读取旧 include 的刚体连接语义。
            master = int(fields[1])  # 刚体主节点位于门架梁轴或通道接口。
            slave = int(fields[2])  # 从节点可能位于梁、通道或原索。
            if in_ranges(master, node_ranges) or in_ranges(slave, node_ranges):  # 保留与 H10 有关的连接。
                cerig.append({"line": line_number, "master": master, "slave": slave, "dof": fields[3].upper()})  # 保存 ALL 或 UXYZ 语义。
    return nodes, elements, cerig, sections, densities  # 返回完整解析结果和质量口径。

def parse_h10_couplings():  # 读取 H10 的 44 个实际索连接点并分类到四个中心接口。
    records = []  # 保存经过坐标变换和接口分类的权威行。
    with COUPLINGS.open("r", encoding="utf-8-sig", newline="") as stream:  # utf-8-sig 消除 CSV BOM。
        for row in csv.DictReader(stream):  # 按列名读取避免依赖列序号。
            if row["passage_id"] != "H10":  # 只抽取代表性的主跨 H10。
                continue  # 其他 20 道通道不进入本地子结构。
            side = "L" if int(row["catwalk"]) == 1 else "R"  # CW1 定义为左幅，CW2 定义为右幅。
            level = "B" if row["subsystem"] == "bottom" else "T"  # bottom 为承重索，gate 为门架索。
            port = f"{level}_{side}"  # 形成 B_L、T_L、B_R、T_R 稳定标签。
            cad_point = np.array((float(row["rope_x_mm"]), float(row["rope_y_mm"]), float(row["rope_z_mm"])), dtype=float)  # CSV 坐标为横、顺、竖。
            apdl_point = np.array((cad_point[1], -cad_point[0], cad_point[2]), dtype=float)  # 变换为 APDL 的顺、横、竖坐标。
            records.append({"port": port, "slave": int(row["ansys_rope_node"]), "point": apdl_point, "family": row["family"], "rope_index": int(row["rope_index"])})  # 保存索节点平动接口。
    return records  # 预期四组数量依次为 16、6、16、6。

def local_beam_stiffness(length, section, section_id):  # 构造含剪切变形的 3D Timoshenko 梁局部刚度。
    area = section["A"]  # 截面面积，单位 mm2。
    inertia_y = section["Iyy"]  # 绕 local-y 的惯性矩，单位 mm4。
    inertia_z = section["Izz"]  # 绕 local-z 的惯性矩，单位 mm4。
    torsion = section["J"]  # Saint-Venant 扭转常数，单位 mm4。
    kappa_xz, kappa_xy = section["TSxz"], section["TSxy"]  # 直接遵循当前 APDL ASEC 的显式值或缺省 1.0。
    matrix = np.zeros((12, 12), dtype=float)  # 初始化两节点各六自由度梁刚度。
    axial = E_MODULUS * area / length  # 轴向刚度 EA/L。
    twist = G_MODULUS * torsion / length  # 扭转刚度 GJ/L。
    matrix[0, 0] += axial  # I 端轴向对角项。
    matrix[0, 6] -= axial  # I-J 轴向耦合项。
    matrix[6, 0] -= axial  # 保持对称。
    matrix[6, 6] += axial  # J 端轴向对角项。
    matrix[3, 3] += twist  # I 端扭转对角项。
    matrix[3, 9] -= twist  # I-J 扭转耦合项。
    matrix[9, 3] -= twist  # 保持对称。
    matrix[9, 9] += twist  # J 端扭转对角项。
    phi_xy = 12.0 * E_MODULUS * inertia_z / (kappa_xy * G_MODULUS * area * length * length)  # local-xy 剪切柔度参数。
    factor_xy = E_MODULUS * inertia_z / (length ** 3 * (1.0 + phi_xy))  # v-rz 弯曲公共系数。
    block_xy = factor_xy * np.array(((12.0, 6.0 * length, -12.0, 6.0 * length), (6.0 * length, (4.0 + phi_xy) * length * length, -6.0 * length, (2.0 - phi_xy) * length * length), (-12.0, -6.0 * length, 12.0, -6.0 * length), (6.0 * length, (2.0 - phi_xy) * length * length, -6.0 * length, (4.0 + phi_xy) * length * length)), dtype=float)  # 标准 Timoshenko 平面弯曲块。
    indices_xy = (1, 5, 7, 11)  # local-y 平动与 local-z 转角自由度。
    matrix[np.ix_(indices_xy, indices_xy)] += block_xy  # 装入 local-xy 弯曲块。
    phi_xz = 12.0 * E_MODULUS * inertia_y / (kappa_xz * G_MODULUS * area * length * length)  # local-xz 剪切柔度参数。
    factor_xz = E_MODULUS * inertia_y / (length ** 3 * (1.0 + phi_xz))  # w-ry 弯曲公共系数。
    block_xz = factor_xz * np.array(((12.0, -6.0 * length, -12.0, -6.0 * length), (-6.0 * length, (4.0 + phi_xz) * length * length, 6.0 * length, (2.0 - phi_xz) * length * length), (-12.0, 6.0 * length, 12.0, 6.0 * length), (-6.0 * length, (2.0 - phi_xz) * length * length, 6.0 * length, (4.0 + phi_xz) * length * length)), dtype=float)  # 符合右手坐标的 w-ry 弯曲块。
    indices_xz = (2, 4, 8, 10)  # local-z 平动与 local-y 转角自由度。
    matrix[np.ix_(indices_xz, indices_xz)] += block_xz  # 装入 local-xz 弯曲块。
    return matrix  # 返回 N/mm 与 N-mm/rad 混合量纲的局部刚度。

def global_beam_stiffness(element, nodes, sections):  # 用显式方向节点把局部梁刚度变换到 APDL 全局轴。
    point_i = nodes[element["n1"]]  # 梁 I 端坐标。
    point_j = nodes[element["n2"]]  # 梁 J 端坐标。
    point_k = nodes[element["orient"]]  # BEAM188 K 方向节点坐标。
    axis_x = point_j - point_i  # 未归一化 local-x。
    length = float(np.linalg.norm(axis_x))  # 梁长，单位 mm。
    axis_x /= length  # 归一化 local-x。
    trial_z = point_k - point_i  # K 节点定义 I-J-K 平面中的 local-z 方向。
    axis_z = trial_z - axis_x * float(axis_x @ trial_z)  # 删除沿梁轴分量。
    axis_z /= float(np.linalg.norm(axis_z))  # 归一化 local-z。
    axis_y = np.cross(axis_z, axis_x)  # 由 x×y=z 得 y=z×x。
    axis_y /= float(np.linalg.norm(axis_y))  # 消除舍入误差。
    rotation = np.vstack((axis_x, axis_y, axis_z))  # 全局分量到局部分量的正交变换。
    transform = np.zeros((12, 12), dtype=float)  # 初始化两端平动与转角变换。
    for start in (0, 3, 6, 9):  # 四个三自由度向量块使用同一旋转矩阵。
        transform[start:start + 3, start:start + 3] = rotation  # 写入块对角变换。
    local = local_beam_stiffness(length, sections[element["section"]], element["section"])  # 计算局部 Timoshenko 刚度。
    global_matrix = transform.T @ local @ transform  # 按虚功一致性变换回全局坐标。
    return 0.5 * (global_matrix + global_matrix.T), length  # 对称化并返回梁长。

def assemble_root_stiffness(nodes, elements, internal_rigid, sections):  # 消去 ALL 刚臂从节点后组装根节点刚度。
    physical_nodes = sorted({element["n1"] for element in elements} | {element["n2"] for element in elements})  # 方向节点无物理自由度。
    slave_to_master = {record["slave"]: record["master"] for record in internal_rigid}  # 本子结构 ALL 连接无链、无重复从节点。
    root_nodes = sorted(set(physical_nodes) - set(slave_to_master))  # 仅根节点保留独立六自由度。
    root_index = {node_id: index for index, node_id in enumerate(root_nodes)}  # 根节点到六自由度块号的映射。
    node_map = {}  # 每个物理节点到其根节点及六乘六刚体映射。
    for node_id in physical_nodes:  # 为梁端点建立运动学映射。
        if node_id in slave_to_master:  # ALL 从节点由主节点刚体运动决定。
            master = slave_to_master[node_id]  # 当前数据中主节点必为根节点。
            node_map[node_id] = (master, rigid_map(nodes[node_id] - nodes[master]))  # 保留偏置转动项。
        else:  # 非从节点直接作为根节点。
            node_map[node_id] = (node_id, np.eye(6))  # 单位映射。
    rows = []  # COO 稀疏矩阵行索引。
    columns = []  # COO 稀疏矩阵列索引。
    values = []  # COO 稀疏矩阵数值。
    lengths = []  # 梁长审计列表。
    for element in elements:  # 逐根梁执行 T^T K T 组装。
        element_matrix, length = global_beam_stiffness(element, nodes, sections)  # 得到全局梁刚度。
        lengths.append(length)  # 记录最短和最长梁以检查单位。
        root_i, map_i = node_map[element["n1"]]  # I 端刚体映射。
        root_j, map_j = node_map[element["n2"]]  # J 端刚体映射。
        maps = (map_i, map_j)  # 两端映射块。
        roots = (root_i, root_j)  # 两端根节点。
        for end_a in range(2):  # 遍历梁刚度四个六乘六分块的行端。
            for end_b in range(2):  # 遍历列端。
                source_block = element_matrix[end_a * 6:(end_a + 1) * 6, end_b * 6:(end_b + 1) * 6]  # 取梁端分块。
                block = maps[end_a].T @ source_block @ maps[end_b]  # 刚体消元后的根节点分块。
                row0 = root_index[roots[end_a]] * 6  # 目标行起点。
                col0 = root_index[roots[end_b]] * 6  # 目标列起点。
                for local_row in range(6):  # 写出六乘六分块所有非零项。
                    for local_col in range(6):  # 写出列分量。
                        value = float(block[local_row, local_col])  # 转为 Python 浮点便于 COO 构造。
                        if value != 0.0:  # 跳过精确零项以控制稀疏规模。
                            rows.append(row0 + local_row)  # 添加全局行号。
                            columns.append(col0 + local_col)  # 添加全局列号。
                            values.append(value)  # 添加刚度值。
    size = len(root_nodes) * 6  # 根节点总自由度数。
    stiffness = coo_matrix((values, (rows, columns)), shape=(size, size)).tocsc()  # 汇总重复项并转 CSC。
    stiffness = 0.5 * (stiffness + stiffness.T)  # 消除稀疏累加舍入导致的微小不对称。
    return stiffness, root_nodes, root_index, node_map, np.asarray(lengths)  # 返回凝聚前根系统。

def build_interface_constraints(nodes, root_index, external_rigid, coupling_records):  # 建立 44 个索平动与四个刚性截面六自由度的虚功一致映射。
    rigid_by_slave = {record["slave"]: record for record in external_rigid}  # 从原索节点快速查找门架轴 master。
    centers = {}  # 保存四个接口中心的 APDL 坐标。
    for port in PORTS:  # 每组中心取 6 或 16 个实际索点的算术中心。
        points = [record["point"] for record in coupling_records if record["port"] == port]  # 当前接口实际索点。
        centers[port] = np.mean(np.vstack(points), axis=0)  # 对称索排的均值即猫道中心线交点。
    constraint_rows = []  # 稀疏 A 矩阵行索引。
    constraint_columns = []  # 稀疏 A 矩阵列索引。
    constraint_values = []  # 稀疏 A 矩阵数值。
    port_map = np.zeros((len(coupling_records) * 3, len(PORTS) * 6), dtype=float)  # B 把四个中心六自由度映射到 44 点平动。
    for record_index, record in enumerate(coupling_records):  # 每个实际索点提供三项平动相容条件。
        rigid = rigid_by_slave[record["slave"]]  # 找到对应门架梁轴 master。
        master = rigid["master"]  # UXYZ 主节点必须是独立根节点。
        if master not in root_index:  # 若未来拓扑出现 ALL 链则拒绝静默误映射。
            raise RuntimeError(f"外部索连接 master {master} 不是根节点")  # 明确指出需增加递归映射。
        gate_map = translation_rigid_map(record["point"] - nodes[master])  # 门架轴六自由度到实际索点平动。
        center_map = translation_rigid_map(record["point"] - centers[record["port"]])  # 中心六自由度到同一索点平动。
        row0 = record_index * 3  # 当前三项约束起始行。
        col0 = root_index[master] * 6  # 当前门架 master 六自由度起始列。
        port0 = PORT_INDEX[record["port"]] * 6  # 当前接口中心六自由度起始列。
        for local_row in range(3):  # 写入 A 的三行。
            for local_col in range(6):  # 写入 master 六自由度系数。
                value = float(gate_map[local_row, local_col])  # 当前运动学系数。
                if value != 0.0:  # 省略精确零项。
                    constraint_rows.append(row0 + local_row)  # 约束行号。
                    constraint_columns.append(col0 + local_col)  # 根自由度列号。
                    constraint_values.append(value)  # A 矩阵系数。
        port_map[row0:row0 + 3, port0:port0 + 6] = center_map  # B 的当前接口块。
    constraint_matrix = coo_matrix((constraint_values, (constraint_rows, constraint_columns)), shape=(len(coupling_records) * 3, len(root_index) * 6)).tocsc()  # 形成 A y=B q。
    return constraint_matrix, port_map, centers  # 返回稀疏约束、端口映射和中心坐标。

def constrained_port_stiffness(stiffness, constraint_matrix, port_map):  # 用约束鞍点方程得到四端口 24×24 刚度。
    zero = csc_matrix((constraint_matrix.shape[0], constraint_matrix.shape[0]), dtype=float)  # 拉格朗日乘子块为零。
    saddle = bmat(((stiffness, constraint_matrix.T), (constraint_matrix, zero)), format="csc")  # 构造 [K A^T;A 0]。
    right_hand = np.vstack((np.zeros((stiffness.shape[0], port_map.shape[1]), dtype=float), port_map))  # 依次施加 24 个单位中心自由度。
    factor = splu(saddle)  # 只分解一次以减少多右端求解误差。
    solution = factor.solve(right_hand)  # 同时求得内部位移与拉格朗日乘子。
    multipliers = solution[stiffness.shape[0]:, :]  # 提取约束反力乘子。
    port_stiffness = -port_map.T @ multipliers  # 广义外力为 -B^T lambda。
    return 0.5 * (port_stiffness + port_stiffness.T), saddle.shape[0]  # 对称化并返回鞍点规模。

def rigid_body_matrix_24(centers):  # 构造四个六自由度中心端口的六个全局刚体模态。
    origin = np.mean(np.vstack([centers[port] for port in PORTS]), axis=0)  # 以四端口几何中心降低数值尺度。
    matrix = np.zeros((24, 6), dtype=float)  # 三平移加三转动共六列。
    for port_index, port in enumerate(PORTS):  # 对每个端口写入刚体运动学。
        offset = centers[port] - origin  # 端口相对审计原点的位置。
        matrix[port_index * 6:port_index * 6 + 6, :] = rigid_map(offset)  # 中心平动和转角均随整体刚体运动。
    return matrix  # K24 乘该矩阵应接近零。

def condense_port_rotations(stiffness_24):  # 将四个中心的 12 个自由转角静力凝聚，仅保留四端三平动。
    translation = np.array([port * 6 + dof for port in range(4) for dof in range(3)], dtype=int)  # 12 个保留平动索引。
    rotation = np.array([port * 6 + dof for port in range(4) for dof in range(3, 6)], dtype=int)  # 12 个内部转角索引。
    k_tt = stiffness_24[np.ix_(translation, translation)]  # 平动—平动块。
    k_tr = stiffness_24[np.ix_(translation, rotation)]  # 平动—转角块。
    k_rr = stiffness_24[np.ix_(rotation, rotation)]  # 转角—转角块。
    eigen_rr = np.linalg.eigvalsh(0.5 * (k_rr + k_rr.T))  # 审计内部转角块可逆性。
    if eigen_rr[0] <= max(eigen_rr[-1], 1.0) * 1.0e-12:  # 只允许浮点量级以下的近零值。
        inverse_action = np.linalg.pinv(k_rr, rcond=1.0e-12) @ k_tr.T  # 对未来可能的自由机构采用明确伪逆。
        method = "symmetric_pseudoinverse"  # 记录凝聚分支。
    else:  # 当前 H10 预期转角块正定。
        inverse_action = np.linalg.solve(k_rr, k_tr.T)  # 精确解 Krr X=Krt。
        method = "direct_solve"  # 记录标准 Schur 补分支。
    condensed = k_tt - k_tr @ inverse_action  # 形成仅含中心平动的 12×12 Schur 补。
    return 0.5 * (condensed + condensed.T), eigen_rr, method  # 返回对称刚度及转角块审计。

def rigid_body_matrix_12(centers):  # 构造四个平动端口可表达的六个刚体模态。
    origin = np.mean(np.vstack([centers[port] for port in PORTS]), axis=0)  # 与 24 自由度审计使用同一原点。
    matrix = np.zeros((12, 6), dtype=float)  # 每端三平动，共 12 行。
    for port_index, port in enumerate(PORTS):  # 写入 u=t+theta×r。
        matrix[port_index * 3:port_index * 3 + 3, :3] = np.eye(3)  # 整体平移部分。
        matrix[port_index * 3:port_index * 3 + 3, 3:] = -skew(centers[port] - origin)  # 整体转动产生的端点平动。
    return matrix  # K12 乘该矩阵应接近零。

def clean_translation_stiffness(stiffness_12, rigid_modes):  # 在六刚体模态正交补上清除凝聚舍入噪声并强制半正定。
    strain_basis = null_space(rigid_modes.T, rcond=1.0e-12)  # 四个空间点的纯变形子空间维数为六。
    reduced = 0.5 * (strain_basis.T @ stiffness_12 @ strain_basis + strain_basis.T @ stiffness_12.T @ strain_basis)  # 投影为对称六乘六刚度。
    eigenvalues, eigenvectors = np.linalg.eigh(reduced)  # 检查纯变形子空间是否正定。
    tolerance = max(float(np.max(np.abs(eigenvalues))), 1.0) * 1.0e-10  # 定义仅用于舍入噪声的截断阈值。
    if float(eigenvalues.min()) < -tolerance:  # 明显负特征值代表梁组装或约束符号错误。
        raise RuntimeError(f"K12 纯变形子空间出现显著负刚度 {eigenvalues.min():.6e} N/mm")  # 禁止用投影掩盖真实不稳定。
    clipped = np.maximum(eigenvalues, 0.0)  # 仅把阈值内的微小负数截为零。
    cleaned = strain_basis @ eigenvectors @ np.diag(clipped) @ eigenvectors.T @ strain_basis.T  # 重构严格半正定 K12。
    cleaned = 0.5 * (cleaned + cleaned.T)  # 消除重构舍入不对称。
    correction = np.linalg.norm(cleaned - stiffness_12, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro"), 1.0)  # 记录数值清理相对幅值。
    return cleaned, eigenvalues, correction  # 返回主 ROM 矩阵、清理前纯变形谱和修正量。

def sha256(path):  # 计算输入文件内容哈希以支持复算追溯。
    digest = hashlib.sha256()  # 初始化 SHA-256 状态。
    with path.open("rb") as stream:  # 二进制读取避免换行转换。
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # 逐 MiB 读取控制内存。
            digest.update(chunk)  # 累计哈希。
    return digest.hexdigest()  # 返回小写十六进制摘要。

def generalized_springs(stiffness_12, rigid_modes):  # 把 K12 精确分解为刚体正交补上的六个广义弹簧。
    strain_basis = null_space(rigid_modes.T, rcond=1.0e-12)  # 12×6 正交基排除六个刚体模态。
    strain_stiffness = strain_basis.T @ stiffness_12 @ strain_basis  # 在纯变形坐标中形成 6×6 刚度。
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (strain_stiffness + strain_stiffness.T))  # 对称特征分解。
    order = np.argsort(eigenvalues)  # 按由柔到刚排序便于 ROM 截断。
    eigenvalues = eigenvalues[order]  # 排序广义刚度。
    eigenvectors = eigenvectors[:, order]  # 同步排序局部特征向量。
    shapes = strain_basis @ eigenvectors  # 映射为四端 12 平动的广义变形向量。
    reconstructed = shapes @ np.diag(eigenvalues) @ shapes.T  # 六个广义弹簧的刚度重构。
    error = np.linalg.norm(reconstructed - stiffness_12, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro"), 1.0)  # 相对 Frobenius 误差。
    return eigenvalues, shapes, error  # 每列 shape 定义 delta=g^T q。

def fit_axial_rods(stiffness_12, centers):  # 用四中心节点间六根非负轴向杆拟合并量化其固有局限。
    pairs = ((0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2))  # 左右竖杆、上下横杆和两根对角杆。
    basis = []  # 每根单位轴向刚度杆对应一个 12×12 矩阵。
    lengths = []  # 保存杆长用于换算 EA 和等效面积。
    for first, second in pairs:  # 构造标准 truss 的 n n^T 分块。
        point_i = centers[PORTS[first]]  # 杆 I 端中心坐标。
        point_j = centers[PORTS[second]]  # 杆 J 端中心坐标。
        delta = point_j - point_i  # 杆轴向向量。
        length = float(np.linalg.norm(delta))  # 杆长，单位 mm。
        direction = delta / length  # 轴向单位向量。
        projector = np.outer(direction, direction)  # 单位轴刚度三乘三投影。
        matrix = np.zeros((12, 12), dtype=float)  # 初始化单位 k=EA/L 的杆刚度。
        slices = (slice(first * 3, first * 3 + 3), slice(second * 3, second * 3 + 3))  # 两端自由度切片。
        matrix[slices[0], slices[0]] += projector  # I-I 块。
        matrix[slices[0], slices[1]] -= projector  # I-J 块。
        matrix[slices[1], slices[0]] -= projector  # J-I 块。
        matrix[slices[1], slices[1]] += projector  # J-J 块。
        basis.append(matrix)  # 保存单位轴刚度基矩阵。
        lengths.append(length)  # 保存杆长。
    upper = np.triu_indices(12)  # 只拟合对称矩阵上三角避免重复加权。
    design = np.column_stack([matrix[upper] for matrix in basis])  # 六个候选杆构成线性设计矩阵。
    target = stiffness_12[upper]  # 目标 K12 上三角。
    stiffnesses, _ = nnls(design, target)  # 强制 EA/L 非负以保持杆网能量非负。
    fitted = sum(value * matrix for value, matrix in zip(stiffnesses, basis))  # 重构六杆刚度。
    relative_error = np.linalg.norm(fitted - stiffness_12, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro"), 1.0)  # 量化四点平面杆网的拟合误差。
    return pairs, np.asarray(lengths), stiffnesses, fitted, relative_error  # 返回杆网参数与误差。

def write_matrix_csv(path, matrix, labels):  # 写出带稳定自由度标签的方阵 CSV。
    with path.open("w", encoding="utf-8", newline="") as stream:  # 覆盖本次可再生输出。
        writer = csv.writer(stream)  # 使用标准 CSV 转义。
        writer.writerow(("dof",) + tuple(labels))  # 第一行记录列自由度顺序。
        for label, row in zip(labels, matrix):  # 每行写出行标签和科学计数数值。
            writer.writerow((label,) + tuple(f"{value:.12e}" for value in row))  # 保留 12 位有效尾数。

def main():  # 执行解析、梁组装、刚性截面映射、静力凝聚与等效拟合。
    OUTPUT.mkdir(parents=True, exist_ok=True)  # 创建隔离输出目录且不删除其他工作。
    nodes, elements, cerig, sections, densities = parse_apdl()  # 读取源 APDL。
    couplings = parse_h10_couplings()  # 读取 H10 权威索接口。
    physical_nodes = {element["n1"] for element in elements} | {element["n2"] for element in elements}  # 梁端物理节点集合。
    internal_rigid = [record for record in cerig if record["master"] in physical_nodes and record["slave"] in physical_nodes and record["dof"] == "ALL"]  # 梁内和门架—通道 ALL 刚臂。
    external_rigid = [record for record in cerig if record["master"] in physical_nodes and record["slave"] not in physical_nodes and record["dof"] == "UXYZ"]  # 门架轴到原索的三平动连接。
    if len(elements) != 699 or len(physical_nodes) != 407 or len(internal_rigid) != 74 or len(external_rigid) != 44 or len(couplings) != 44:  # 硬检查权威 H10 拓扑计数。
        raise RuntimeError(f"H10 拓扑计数不闭合: beams={len(elements)}, physical_nodes={len(physical_nodes)}, internal_ALL={len(internal_rigid)}, external_UXYZ={len(external_rigid)}, couplings={len(couplings)}")  # 阻止错误号段静默凝聚。
    if set(record["slave"] for record in external_rigid) != set(record["slave"] for record in couplings):  # 验证 CSV 与 APDL 原索节点一一闭合。
        raise RuntimeError("H10 外部 UXYZ 从节点与 passage_gate_rope_couplings.csv 不一致")  # 连接版本不一致时立即失败。
    if any(densities.get(section_id) != 0.0 for section_id in range(61, 67)):  # 六组新增梁材料必须显式零密度。
        raise RuntimeError(f"源 APDL 新增梁密度并非全零: {densities}")  # 防止凝聚刚度时误带入重复质量口径。
    group_counts = {port: sum(record["port"] == port for record in couplings) for port in PORTS}  # 统计四组实际索点。
    if group_counts != {"B_L": 16, "T_L": 6, "B_R": 16, "T_R": 6}:  # 严格执行 16/6/16/6 接口定义。
        raise RuntimeError(f"索接口数量不闭合: {group_counts}")  # 防止漏索或重复索。
    stiffness_root, root_nodes, root_index, node_map, beam_lengths = assemble_root_stiffness(nodes, elements, internal_rigid, sections)  # 组装已消去 ALL 从节点的梁系统。
    constraints, port_map, centers = build_interface_constraints(nodes, root_index, external_rigid, couplings)  # 建立刚性截面虚功映射。
    rank_constraints = int(np.linalg.matrix_rank(constraints.toarray(), tol=1.0e-9))  # 132 行约束应线性独立。
    stiffness_24, saddle_size = constrained_port_stiffness(stiffness_root, constraints, port_map)  # 得到四中心六自由度刚度。
    rigid_24 = rigid_body_matrix_24(centers)  # 构造 24 自由度刚体运动。
    scale_24 = np.diag([1.0 if dof % 6 < 3 else 1.0 / LENGTH_SCALE for dof in range(24)])  # 将旋转列换算到 1 m 位移尺度。
    eigen_24_scaled = np.linalg.eigvalsh(0.5 * (scale_24.T @ stiffness_24 @ scale_24 + scale_24.T @ stiffness_24.T @ scale_24))  # 量纲一致的正定审计谱。
    rigid_residual_24 = np.linalg.norm(stiffness_24 @ rigid_24, ord="fro") / max(np.linalg.norm(stiffness_24, ord="fro") * np.linalg.norm(rigid_24, ord="fro"), 1.0)  # 六刚体模态相对残差。
    stiffness_12_raw, eigen_rotation_block, rotation_method = condense_port_rotations(stiffness_24)  # 自由凝聚中心转角并保留清理前矩阵。
    rigid_12 = rigid_body_matrix_12(centers)  # 构造四平动端的六刚体模态。
    raw_eigen_12 = np.linalg.eigvalsh(stiffness_12_raw)  # 记录鞍点求解与伪逆带来的原始浮点谱。
    raw_rigid_residual_12 = np.linalg.norm(stiffness_12_raw @ rigid_12, ord="fro") / max(np.linalg.norm(stiffness_12_raw, ord="fro") * np.linalg.norm(rigid_12, ord="fro"), 1.0)  # 原始刚体残差。
    stiffness_12, strain_eigen_raw, cleanup_correction = clean_translation_stiffness(stiffness_12_raw, rigid_12)  # 强制六刚体零模态和纯变形半正定。
    eigen_12 = np.linalg.eigvalsh(stiffness_12)  # K12 全谱用于零模态和正定审计。
    rigid_residual_12 = np.linalg.norm(stiffness_12 @ rigid_12, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro") * np.linalg.norm(rigid_12, ord="fro"), 1.0)  # 六刚体模态相对残差。
    spring_values, spring_shapes, reconstruction_error = generalized_springs(stiffness_12, rigid_12)  # 精确六广义弹簧分解。
    rod_pairs, rod_lengths, rod_stiffnesses, rod_matrix, rod_error = fit_axial_rods(stiffness_12, centers)  # 非负六杆低阶拟合。
    labels_24 = [f"{port}_{dof}" for port in PORTS for dof in ("UX", "UY", "UZ", "RX", "RY", "RZ")]  # K24 稳定自由度顺序。
    labels_12 = [f"{port}_{dof}" for port in PORTS for dof in ("UX", "UY", "UZ")]  # K12 稳定自由度顺序。
    write_matrix_csv(OUTPUT / "K24_ports_6dof.csv", stiffness_24, labels_24)  # 保存旋转凝聚前矩阵。
    write_matrix_csv(OUTPUT / "K12_translation_ports.csv", stiffness_12, labels_12)  # 保存主 ROM 推荐矩阵。
    write_matrix_csv(OUTPUT / "K12_translation_ports_SI.csv", stiffness_12 * 1000.0, labels_12)  # 位移采用 m 时把 N/mm 转为 N/m。
    write_matrix_csv(OUTPUT / "K12_translation_ports_raw.csv", stiffness_12_raw, labels_12)  # 保存数值清理前 Schur 补便于逐项追溯。
    write_matrix_csv(OUTPUT / "K12_six_axial_rods_fit.csv", rod_matrix, labels_12)  # 保存低保真杆网拟合矩阵。
    np.savez_compressed(OUTPUT / "H10_gate_passage_condensed.npz", K24_mixed_N_mm=stiffness_24, K12_N_per_mm=stiffness_12, K12_N_per_m=stiffness_12 * 1000.0, port_labels_24=np.asarray(labels_24), port_labels_12=np.asarray(labels_12), centers_mm=np.vstack([centers[port] for port in PORTS]), centers_m=np.vstack([centers[port] for port in PORTS]) / 1000.0, generalized_stiffness_N_per_mm=spring_values, generalized_stiffness_N_per_m=spring_values * 1000.0, generalized_shapes=spring_shapes, rod_fit_K12_N_per_mm=rod_matrix, rod_fit_K12_N_per_m=rod_matrix * 1000.0)  # 保存 N-mm 和 SI 两套主 ROM 数据且不含质量。
    with (OUTPUT / "port_coordinates.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存四中心坐标和索点数量。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("port", "x_long_mm", "y_trans_mm", "z_vert_mm", "actual_rope_nodes"))  # 明确 APDL 坐标轴。
        for port in PORTS:  # 按刚度矩阵块顺序输出。
            writer.writerow((port,) + tuple(f"{value:.9f}" for value in centers[port]) + (group_counts[port],))  # 写入中心与组内索数。
    with (OUTPUT / "generalized_springs.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存六个精确广义弹簧。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("spring", "k_N_per_mm") + tuple(labels_12))  # 每行给出 k 与 delta=g^T q 的 g。
        for index, value in enumerate(spring_values, start=1):  # 由柔到刚输出。
            writer.writerow((f"GS{index}", f"{value:.12e}") + tuple(f"{entry:.12e}" for entry in spring_shapes[:, index - 1]))  # 保存正交广义变形向量。
    with (OUTPUT / "six_axial_rods_fit.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存六根轴向杆参数。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("rod", "node_i", "node_j", "length_mm", "k_EA_over_L_N_per_mm", "EA_N", "area_at_E206GPa_mm2"))  # 给出主 ROM 常用杆参数。
        for index, ((first, second), length, value) in enumerate(zip(rod_pairs, rod_lengths, rod_stiffnesses), start=1):  # 按固定六杆顺序输出。
            writer.writerow((f"R{index}", PORTS[first], PORTS[second], f"{length:.9f}", f"{value:.12e}", f"{value * length:.12e}", f"{value * length / E_MODULUS:.12e}"))  # 由 k 换算 EA 和面积。
    with (OUTPUT / "H10_beam188_elements.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存实际参与凝聚的 699 根物理梁清单。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("element_id", "n1", "n2", "orientation_node", "material", "section", "length_mm"))  # 明确方向节点不含物理自由度。
        for element, length in zip(elements, beam_lengths):  # 元素顺序与组装长度顺序一致。
            writer.writerow((element["id"], element["n1"], element["n2"], element["orient"], element["material"], element["section"], f"{length:.12f}"))  # 写出稳定编号与梁长。
    with (OUTPUT / "H10_internal_all_rigid_links.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存门架内部及门架—通道刚臂清单。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("source_line", "master", "slave", "dof", "dx_mm", "dy_mm", "dz_mm"))  # ALL 连接保留完整偏置刚体运动。
        for record in internal_rigid:  # 按原 APDL 行序输出便于回查。
            offset = nodes[record["slave"]] - nodes[record["master"]]  # 计算从主到从的偏置向量。
            writer.writerow((record["line"], record["master"], record["slave"], record["dof"]) + tuple(f"{value:.12f}" for value in offset))  # 写出刚臂几何。
    external_by_slave = {record["slave"]: record for record in external_rigid}  # 为接口明细快速查找门架 master。
    with (OUTPUT / "H10_rope_interface_mapping.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存 44 个索点到四中心端的映射。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("port", "family", "rope_index", "rope_node", "gate_master", "rope_x_long_mm", "rope_y_trans_mm", "rope_z_vert_mm", "center_dx_mm", "center_dy_mm", "center_dz_mm"))  # 记录虚功映射几何。
        for record in couplings:  # 按权威 CSV 顺序输出。
            center_offset = record["point"] - centers[record["port"]]  # 实际索点相对四中心端的偏置。
            master = external_by_slave[record["slave"]]["master"]  # 对应门架梁轴节点。
            writer.writerow((record["port"], record["family"], record["rope_index"], record["slave"], master) + tuple(f"{value:.12f}" for value in record["point"]) + tuple(f"{value:.12f}" for value in center_offset))  # 写出一一映射。
    (OUTPUT / "K12_translation_ports.json").write_text(json.dumps({"units_native": "N/mm for all translation-translation entries", "si_conversion": "K_N_per_m = 1000 * K_N_per_mm", "coordinate_system": {"X": "longitudinal", "Y": "transverse", "Z": "vertical"}, "port_order": list(PORTS), "dof_order_each": ["UX", "UY", "UZ"], "labels": labels_12, "matrix_N_per_mm": stiffness_12.tolist(), "matrix_N_per_m": (stiffness_12 * 1000.0).tolist()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 保存语言无关的四节点刚度接口及 SI 版本。
    maximum_24 = float(max(np.max(np.abs(eigen_24_scaled)), 1.0))  # K24 缩放谱的相对计数基准。
    zero_count_24 = int(np.sum(np.abs(eigen_24_scaled) <= maximum_24 * 1.0e-8))  # 预期六刚体加四组索线钻转共十个零模态。
    positive_count_24 = int(np.sum(eigen_24_scaled > maximum_24 * 1.0e-8))  # 预期十四个可观测变形模态。
    maximum_12 = float(max(abs(eigen_12[0]), abs(eigen_12[-1]), 1.0))  # 定义相对零模态阈值基准。
    zero_count_12 = int(np.sum(np.abs(eigen_12) <= maximum_12 * 1.0e-8))  # 预期恰为六个刚体零模态。
    positive_count_12 = int(np.sum(eigen_12 > maximum_12 * 1.0e-8))  # 预期恰为六个变形模态。
    audit = {"source": {"apdl": str(APDL.relative_to(ROOT)), "apdl_sha256": sha256(APDL), "couplings": str(COUPLINGS.relative_to(ROOT)), "couplings_sha256": sha256(COUPLINGS), "representative_station": "H10", "gate_indices": [32, 32], "asec_shear_policy": "use explicit TSxz/TSxy when present; source has six SECDATA values so reproduce ASEC defaults TSxz=TSxy=1.0", "section_shear_data": {str(section_id): {"SECDATA_count": int(section["SECDATA_count"]), "TSxz": float(section["TSxz"]), "TSxy": float(section["TSxy"])} for section_id, section in sections.items()}}, "topology": {"beam188_elements": len(elements), "physical_beam_nodes": len(physical_nodes), "orientation_nodes": len({element["orient"] for element in elements}), "internal_cerig_all": len(internal_rigid), "external_cerig_uxyz": len(external_rigid), "root_nodes_after_all_elimination": len(root_nodes), "root_dofs": stiffness_root.shape[0], "constraint_rows": constraints.shape[0], "constraint_rank": rank_constraints, "saddle_size": saddle_size, "beam_length_mm_min": float(beam_lengths.min()), "beam_length_mm_max": float(beam_lengths.max())}, "interfaces": {"order": list(PORTS), "dof_order_each_24": ["UX", "UY", "UZ", "RX", "RY", "RZ"], "dof_order_each_12": ["UX", "UY", "UZ"], "rope_counts": group_counts, "coordinates_apdl_mm": {port: centers[port].tolist() for port in PORTS}, "mapping": "actual rope translations = center translation + center rotation cross offset; rope rotations absent; four center rotations then statically condensed", "unobservable_rotations": "each rope group is collinear along transverse Y, so its center RY drilling rotation does not enter any rope-point translation"}, "mass_policy": {"beam_material_densities_tonne_per_mm3": {str(section_id): float(densities[section_id]) for section_id in range(61, 67)}, "mass_matrix_generated": False, "duplicate_mass_added": False}, "stiffness_audit": {"symmetry_error_K24": float(np.linalg.norm(stiffness_24 - stiffness_24.T, ord="fro") / max(np.linalg.norm(stiffness_24, ord="fro"), 1.0)), "rigid_body_residual_K24": float(rigid_residual_24), "scaled_K24_eigenvalues": eigen_24_scaled.tolist(), "K24_zero_eigenvalue_count_rel_1e_8": zero_count_24, "K24_positive_eigenvalue_count_rel_1e_8": positive_count_24, "K24_zero_mode_interpretation": "6 global rigid-body modes + 4 unobservable RY drilling rotations of collinear rope groups", "rotation_condensation_method": rotation_method, "Krr_eigenvalues_mixed_units": eigen_rotation_block.tolist(), "raw_K12_rigid_body_residual": float(raw_rigid_residual_12), "raw_K12_eigenvalues_N_per_mm": raw_eigen_12.tolist(), "K12_psd_cleanup_relative_correction": float(cleanup_correction), "K12_strain_subspace_eigenvalues_before_clipping_N_per_mm": strain_eigen_raw.tolist(), "symmetry_error_K12": float(np.linalg.norm(stiffness_12 - stiffness_12.T, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro"), 1.0)), "rigid_body_residual_K12": float(rigid_residual_12), "K12_eigenvalues_N_per_mm": eigen_12.tolist(), "K12_zero_eigenvalue_count_rel_1e_8": zero_count_12, "K12_positive_eigenvalue_count_rel_1e_8": positive_count_12, "minimum_generalized_spring_N_per_mm": float(spring_values.min()), "maximum_generalized_spring_N_per_mm": float(spring_values.max()), "generalized_spring_reconstruction_relative_error": float(reconstruction_error)}, "equivalent_models": {"recommended": "K12_translation_ports.csv or H10_gate_passage_condensed.npz exact four-node generalized spring", "generalized_springs": "six orthogonal strain springs delta_j=g_j^T q with k_j; exact up to numerical roundoff", "six_axial_rods_fit_relative_error": float(rod_error), "six_axial_rods_warning": "four coplanar center nodes cannot reproduce out-of-plane frame stiffness while preserving all six rigid-body modes; use only for sensitivity checks"}}  # 汇总机器审计。
    (OUTPUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 保存 JSON 审计。
    readme_lines = ["# H10 两品有限门架 + 一品完整横通道静力凝聚", "", "本目录从 `apply_finite_gates_and_passages_v2.inp` 的 H10/CW1_GATE_32/CW2_GATE_32 提取 699 根 BEAM188，并保留门架—横通道的 74 条 `CERIG,ALL` 刚臂运动学。", "", "四个索接口依次为 `B_L, T_L, B_R, T_R`。每组 16/6 个实际索节点只参与三平动相容：先按刚性截面 `u_i=u_c+theta_c×r_i` 做虚功一致映射，不给索节点增加转角；随后把四个中心转角作为内部自由度静力凝聚，得到 12×12 平动端刚度。", "", "四组索点各自沿横桥向共线，因此每个中心绕横桥 Y 轴的钻转不会产生任何索点平动。K24 具有 6 个整体刚体模态和 4 个这种不可观测钻转，共 10 个零模态；用对称伪逆凝聚这些自由转角是预期运动学，不是局部机构。最终 K12 恰有 6 个刚体零模态和 6 个正变形模态。", "", "源 APDL 的每条 ASEC `SECDATA` 只写 A/I/J 六项；本脚本按该文件的缺省 `TSxz=TSxy=1.0` 复现 BEAM188 Timoshenko 剪切刚度，不混入相邻生成脚本后来补充的 14 项截面修正。", "", "## 推荐文件", "", "- `K12_translation_ports.csv`：N-mm 制主 ROM 推荐矩阵，节点内顺序为 UX、UY、UZ；已投影清除数值噪声并保持六刚体模态。", "- `K12_translation_ports_SI.csv`：完全相同的矩阵按 N/m 输出，SI 主 ROM 可直接读取。", "- `H10_gate_passage_condensed.npz`：同时含 K12_N_per_mm、K12_N_per_m、凝聚前 K24、两套接口坐标及六广义弹簧。", "- `generalized_springs.csv`：六个正交广义变形弹簧，`delta_j=g_j^T q`、`F_j=k_j delta_j`，可精确重构 K12。", "- `six_axial_rods_fit.csv`：六根非负轴向杆的低保真拟合；误差见 `audit.json`，不应替代精确 K12。", "- `H10_beam188_elements.csv`、`H10_internal_all_rigid_links.csv`、`H10_rope_interface_mapping.csv`：提取和连接审计清单。", "", "## 质量口径", "", "本次只凝聚刚度。源 APDL 的新梁密度为 0，未生成质量矩阵、未把横通道或门架集中质量再次计入，因此不会与既有 MASS21 重复。", "", "## 单位与坐标", "", "采用 N-mm 制；APDL 坐标为 X 顺桥、Y 横桥、Z 竖向。K12 的平动刚度统一为 N/mm；换成位移 m 时使用 `K_N_per_m=1000 K_N_per_mm`。K24 含转角时相应行列具有 N、N-mm 的混合量纲。", ""]  # 形成人工复核说明。
    (OUTPUT / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")  # 保存说明文件。
    print(json.dumps({"output": str(OUTPUT), "K12_eigenvalues": eigen_12.tolist(), "rigid_residual_K12": rigid_residual_12, "generalized_spring_reconstruction_error": reconstruction_error, "six_axial_rods_fit_error": rod_error}, ensure_ascii=False, indent=2))  # 向调用者打印关键结果。

if __name__ == "__main__":  # 仅直接执行脚本时运行凝聚。
    main()  # 开始 H10 子结构静力凝聚。
