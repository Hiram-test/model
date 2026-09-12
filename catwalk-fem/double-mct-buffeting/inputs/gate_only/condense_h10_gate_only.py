#!/usr/bin/env python3  # 凝聚 H10/CW1_GATE_32 普通有限门架而不包含横向通道。
import csv  # 写出带自由度标签的刚度和接口明细。
import importlib.util  # 复用已验证的 BEAM188 与刚臂组装内核而不修改主代码。
import json  # 写出机器可读审计与替换判断。
from pathlib import Path  # 稳定定位共享输入与独立输出目录。
import numpy as np  # 执行静力凝聚、谱审计和局部坐标变换。
from scipy.linalg import null_space  # 构造两点平动端的刚体正交补。
from scipy.sparse import bmat, coo_matrix, csc_matrix  # 组装索点约束与能量回代鞍点矩阵。
from scipy.sparse.linalg import splu  # 回代单位轴向变形并分解构件能量。

ROOT = Path(__file__).resolve().parents[2]  # tmp/gate_only_condensation 的上两级是工作区根目录。
CORE_PATH = ROOT / "tmp" / "gate_passage_condensation" / "condense_h10.py"  # 已验证的 BEAM188/Timoshenko 凝聚内核。
OUTPUT = ROOT / "tmp" / "gate_only_condensation"  # 普通门架独立输出目录。
MCT_PATH = ROOT / "tmp" / "mct_pair_sources" / "catwalk_gantry_rope_combined_2.mct"  # 原双索合建 MCT，用于 property-3 对比。
GATE_ELEMENT_RANGE = (2000931, 2000960)  # H10 对应 CW1_GATE_32 的 30 根 BEAM188。
PORTS = ("B", "T")  # 承重索中心与门架索中心的稳定端口顺序。
PORT_INDEX = {name: index for index, name in enumerate(PORTS)}  # 端口名到六自由度块号的映射。
E_STEEL = 206000.0  # 正式有限门架与 MCT property-3 的钢材弹性模量，单位 N/mm2。
MCT_PROPERTY3_AREA_MM2 = 2.0 * 161.0 * 8.0 + 2.0 * (161.0 - 2.0 * 8.0) * 8.0  # MCT B161×161×8 等效箱形截面面积 4896 mm2。
ROTATION_SCALE_MM = 1000.0  # 12 自由度谱审计把 1 rad 转角缩放为 1 m 端部位移量级。

def load_core():  # 动态载入共享内核且不触发其 main。
    specification = importlib.util.spec_from_file_location("gate_passage_core", CORE_PATH)  # 用显式文件路径创建模块规范。
    if specification is None or specification.loader is None:  # 缺少内核时阻止不透明失败。
        raise RuntimeError(f"无法载入凝聚内核 {CORE_PATH}")  # 返回明确的依赖路径。
    module = importlib.util.module_from_spec(specification)  # 创建隔离模块对象。
    specification.loader.exec_module(module)  # 执行定义但因 __name__ 不等于 __main__ 而不运行四端口任务。
    return module  # 返回可复用的梁与刚臂函数。

def write_matrix_csv(path, matrix, labels):  # 写出带稳定行列标签的方阵 CSV。
    with path.open("w", encoding="utf-8", newline="") as stream:  # 覆盖本次可再生结果。
        writer = csv.writer(stream)  # 使用标准 CSV 转义规则。
        writer.writerow(("dof",) + tuple(labels))  # 第一行给出列自由度顺序。
        for label, row in zip(labels, matrix):  # 逐行写出科学计数数值。
            writer.writerow((label,) + tuple(f"{value:.12e}" for value in row))  # 保留足够数值精度。

def build_gate_constraints(core, nodes, root_index, external_rigid, couplings):  # 把 16/6 个实际索点映射到 B/T 两个刚性截面中心。
    rigid_by_slave = {record["slave"]: record for record in external_rigid}  # 从原索节点查找门架梁轴 master。
    centers = {}  # 保存 B/T 中心 APDL 坐标。
    for port in PORTS:  # 分别计算承重索和门架索中心。
        points = [record["point"] for record in couplings if record["port"] == port]  # 当前索族实际节点坐标。
        centers[port] = np.mean(np.vstack(points), axis=0)  # 对称索排均值即中心线接口。
    rows = []  # 稀疏 A 矩阵行号。
    columns = []  # 稀疏 A 矩阵列号。
    values = []  # 稀疏 A 矩阵系数。
    port_map = np.zeros((len(couplings) * 3, 12), dtype=float)  # B 将两个中心六自由度映射到 22 点平动。
    for record_index, record in enumerate(couplings):  # 每个索点建立三项平动虚功相容。
        rigid = rigid_by_slave[record["slave"]]  # 查找对应 UXYZ 主节点。
        master = rigid["master"]  # master 位于门架横梁轴线上。
        if master not in root_index:  # 当前普通门架外接口 master 必须是消元后的根节点。
            raise RuntimeError(f"门架索接口 master {master} 不是根节点")  # 防止未来 ALL 链未处理。
        gate_map = core.translation_rigid_map(record["point"] - nodes[master])  # 门架轴六自由度到实际索点三平动。
        center_map = core.translation_rigid_map(record["point"] - centers[record["port"]])  # 中心刚性截面到同一点三平动。
        row0 = record_index * 3  # 当前约束三行的起点。
        column0 = root_index[master] * 6  # 当前 master 六自由度起点。
        port0 = PORT_INDEX[record["port"]] * 6  # 当前端口六自由度起点。
        for local_row in range(3):  # 写入三项平动关系。
            for local_column in range(6):  # 写入 master 六自由度系数。
                value = float(gate_map[local_row, local_column])  # 读取刚性偏置系数。
                if value != 0.0:  # 跳过精确零项控制稀疏规模。
                    rows.append(row0 + local_row)  # 追加约束行号。
                    columns.append(column0 + local_column)  # 追加根自由度列号。
                    values.append(value)  # 追加 A 系数。
        port_map[row0:row0 + 3, port0:port0 + 6] = center_map  # 写入 B 端口映射块。
    constraint_matrix = coo_matrix((values, (rows, columns)), shape=(len(couplings) * 3, len(root_index) * 6)).tocsc()  # 形成 A y=B q。
    return constraint_matrix, port_map, centers  # 返回约束、端口映射和中心坐标。

def rigid_modes_12(core, centers):  # 构造 B/T 六自由度端口的六个整体刚体模态。
    origin = 0.5 * (centers["B"] + centers["T"])  # 用两端中点降低刚体转动数值尺度。
    matrix = np.zeros((12, 6), dtype=float)  # 两端各六自由度，共 12 行。
    for port_index, port in enumerate(PORTS):  # 为 B/T 写入刚体运动学。
        matrix[port_index * 6:port_index * 6 + 6, :] = core.rigid_map(centers[port] - origin)  # 端口平动和转角随整体运动。
    return matrix  # K12 乘该矩阵应为零。

def rigid_modes_6(core, centers):  # 构造 B/T 平动端可观察的五维刚体子空间。
    origin = 0.5 * (centers["B"] + centers["T"])  # 采用两端中点作为转动中心。
    matrix = np.zeros((6, 6), dtype=float)  # 六列参数含一个绕连线不可观察的冗余转动。
    for port_index, port in enumerate(PORTS):  # 写入 u=t+theta×r。
        matrix[port_index * 3:port_index * 3 + 3, :3] = np.eye(3)  # 整体平移部分。
        matrix[port_index * 3:port_index * 3 + 3, 3:] = -core.skew(centers[port] - origin)  # 整体转动产生的端点平动。
    return matrix  # 该矩阵秩应为五。

def condense_free_rotations(stiffness_12):  # 自由凝聚 B/T 全部中心转角，仅保留六项平动。
    translation = np.array((0, 1, 2, 6, 7, 8), dtype=int)  # B/T 三平动索引。
    rotation = np.array((3, 4, 5, 9, 10, 11), dtype=int)  # B/T 三转角索引。
    k_tt = stiffness_12[np.ix_(translation, translation)]  # 固定端转角时的平动块。
    k_tr = stiffness_12[np.ix_(translation, rotation)]  # 平动—转角耦合块。
    k_rr = stiffness_12[np.ix_(rotation, rotation)]  # 自由转角内部块。
    eigen_rr = np.linalg.eigvalsh(0.5 * (k_rr + k_rr.T))  # 识别两个共线索排钻转零模态。
    inverse_action = np.linalg.pinv(k_rr, rcond=1.0e-12) @ k_tr.T  # 用对称伪逆消去不可观察转角。
    condensed = k_tt - k_tr @ inverse_action  # 形成自由转角后的两平动端刚度。
    return 0.5 * (condensed + condensed.T), k_tt, eigen_rr  # 同时返回固定转角平动块作为 portal 上限。

def clean_axial_k6(stiffness_6, rigid_modes):  # 将数值噪声投影到两点间唯一客观轴向变形子空间。
    strain_basis = null_space(rigid_modes.T, rcond=1.0e-12)  # 两平动点六自由度扣除五个刚体运动后仅余一列。
    if strain_basis.shape != (6, 1):  # 硬检查球铰两点的客观应变维数。
        raise RuntimeError(f"两点平动应变基维数异常 {strain_basis.shape}")  # 阻止误把剪切机制当正刚度。
    scalar = float((strain_basis.T @ stiffness_6 @ strain_basis)[0, 0])  # 唯一非零谱值应为 2EA/L。
    if scalar <= 0.0:  # 有限门架轴向刚度必须为正。
        raise RuntimeError(f"门架两端轴向谱非正 {scalar:.6e} N/mm")  # 拒绝不稳定结果。
    cleaned = strain_basis * scalar @ strain_basis.T  # 重构严格秩一且半正定的 K6。
    correction = np.linalg.norm(cleaned - stiffness_6, ord="fro") / max(np.linalg.norm(stiffness_6, ord="fro"), 1.0)  # 数值清理相对幅度。
    return 0.5 * (cleaned + cleaned.T), scalar, correction, strain_basis[:, 0]  # 返回主矩阵和唯一应变向量。

def local_portal_basis(centers):  # 构造门架中心线的局部 X剪切、Y剪切、轴向正交基。
    axial = centers["T"] - centers["B"]  # 从承重索中心指向门架索中心。
    length = float(np.linalg.norm(axial))  # 两中心距离，单位 mm。
    axial /= length  # 归一化门架轴向。
    transverse_y = np.array((0.0, 1.0, 0.0), dtype=float)  # APDL 全局 Y 横桥且与门架轴正交。
    shear_x = np.cross(transverse_y, axial)  # 由 y×n 得近似顺桥 X 的另一剪切轴。
    shear_x /= float(np.linalg.norm(shear_x))  # 归一化顺桥剪切方向。
    basis = np.column_stack((shear_x, transverse_y, axial))  # 列顺序为 Sx、Sy、N。
    return basis, length  # 返回全局分量基矩阵和门架中心距。

def axial_energy_breakdown(core, nodes, elements, sections, stiffness_root, constraints, port_map, stiffness_12, root_index, node_map, axial_direction):  # 回代 1 mm 轴向相对位移并分解顶梁、底梁和立柱内能。
    translation = np.array((0, 1, 2, 6, 7, 8), dtype=int)  # K12 的 B/T 平动索引。
    rotation = np.array((3, 4, 5, 9, 10, 11), dtype=int)  # K12 的 B/T 转角索引。
    prescribed_translation = np.zeros(6, dtype=float)  # 令 B 固定、T 沿门架轴移动 1 mm。
    prescribed_translation[3:6] = axial_direction  # T 端轴向单位位移。
    k_tr = stiffness_12[np.ix_(translation, rotation)]  # 平动—转角耦合块。
    k_rr = stiffness_12[np.ix_(rotation, rotation)]  # 两端自由转角块。
    optimal_rotation = -np.linalg.pinv(k_rr, rcond=1.0e-12) @ k_tr.T @ prescribed_translation  # 自由转角使总势能最小。
    port_displacement = np.zeros(12, dtype=float)  # 组合完整端口位移。
    port_displacement[translation] = prescribed_translation  # 写入 B/T 平动。
    port_displacement[rotation] = optimal_rotation  # 写入自由凝聚转角。
    zero = csc_matrix((constraints.shape[0], constraints.shape[0]), dtype=float)  # 拉格朗日乘子零块。
    saddle = bmat(((stiffness_root, constraints.T), (constraints, zero)), format="csc")  # 构造内部平衡鞍点矩阵。
    right_hand = np.concatenate((np.zeros(stiffness_root.shape[0], dtype=float), port_map @ port_displacement))  # 施加端口运动学。
    root_displacement = splu(saddle).solve(right_hand)[:stiffness_root.shape[0]]  # 求得消元后根节点位移。
    energies = {"bottom_beam": 0.0, "top_beam": 0.0, "posts": 0.0}  # 三类物理构件能量台账。
    for element in elements:  # 逐根梁按 0.5 u^T K u 累计。
        element_matrix, length = core.global_beam_stiffness(element, nodes, sections)  # 重建当前梁全局刚度。
        end_vectors = []  # 保存 I/J 端六自由度。
        for node_id in (element["n1"], element["n2"]):  # 从根节点运动恢复 ALL 从节点运动。
            root_node, mapping = node_map[node_id]  # 读取当前端的刚体映射。
            root_start = root_index[root_node] * 6  # 根节点自由度起点。
            end_vectors.append(mapping @ root_displacement[root_start:root_start + 6])  # 恢复物理端位移。
        element_displacement = np.concatenate(tuple(end_vectors))  # 形成 12 项梁端位移。
        energy = 0.5 * float(element_displacement @ element_matrix @ element_displacement)  # 当前梁应变能，单位 N-mm。
        category = "bottom_beam" if element["id"] <= 2000949 else ("top_beam" if element["id"] <= 2000958 else "posts")  # 按正式稳定编号分类。
        energies[category] += energy  # 累计当前构件类。
    total = sum(energies.values())  # 三类能量总和。
    port_energy = 0.5 * float(port_displacement @ stiffness_12 @ port_displacement)  # 端口凝聚矩阵给出的总能量。
    fractions = {name: value / total for name, value in energies.items()}  # 形成无量纲能量占比。
    balance_error = abs(total - port_energy) / max(abs(port_energy), 1.0)  # 检查逐梁能量与凝聚能量闭合。
    return energies, fractions, total, port_energy, balance_error, optimal_rotation  # 返回解释轴向柔度的审计证据。

def main():  # 执行单品普通门架的提取、凝聚、审计与 property-3 对比。
    OUTPUT.mkdir(parents=True, exist_ok=True)  # 创建隔离目录且不触碰主 ROM 代码。
    core = load_core()  # 载入共享有限梁内核。
    nodes, all_elements, all_cerig, sections, densities = core.parse_apdl()  # 读取正式 APDL 数据。
    elements = [element for element in all_elements if GATE_ELEMENT_RANGE[0] <= element["id"] <= GATE_ELEMENT_RANGE[1]]  # 只保留 CW1_GATE_32。
    physical_nodes = {element["n1"] for element in elements} | {element["n2"] for element in elements}  # 梁端物理节点集合。
    internal_rigid = [record for record in all_cerig if record["master"] in physical_nodes and record["slave"] in physical_nodes and record["dof"] == "ALL"]  # 门架梁—立柱四条内部刚臂。
    external_rigid = [record for record in all_cerig if record["master"] in physical_nodes and record["slave"] not in physical_nodes and record["dof"] == "UXYZ"]  # 22 个索平动连接。
    all_couplings = core.parse_h10_couplings()  # 读取 H10 两幅 44 个索点。
    couplings = [{**record, "port": "B" if record["port"] == "B_L" else "T"} for record in all_couplings if record["port"] in ("B_L", "T_L")]  # 只取 CW1 并重命名两端口。
    if len(elements) != 30 or len(physical_nodes) != 34 or len(internal_rigid) != 4 or len(external_rigid) != 22 or len(couplings) != 22:  # 硬检查正式普通门架拓扑。
        raise RuntimeError(f"普通门架计数不闭合: beams={len(elements)}, nodes={len(physical_nodes)}, ALL={len(internal_rigid)}, UXYZ={len(external_rigid)}, couplings={len(couplings)}")  # 防止号段漂移。
    if set(record["slave"] for record in external_rigid) != set(record["slave"] for record in couplings):  # 验证 APDL 与 CSV 索节点一一对应。
        raise RuntimeError("普通门架 UXYZ 从节点与 H10/CW1 索接口 CSV 不一致")  # 输入版本不匹配时失败。
    group_counts = {port: sum(record["port"] == port for record in couplings) for port in PORTS}  # 统计 B/T 实际索点。
    if group_counts != {"B": 16, "T": 6}:  # 权威接口数量必须为 16/6。
        raise RuntimeError(f"普通门架索接口数量异常 {group_counts}")  # 防止漏索或重复索。
    stiffness_root, root_nodes, root_index, node_map, beam_lengths = core.assemble_root_stiffness(nodes, elements, internal_rigid, sections)  # 消去四条内部 ALL 刚臂并组装门架梁。
    constraints, port_map, centers = build_gate_constraints(core, nodes, root_index, external_rigid, couplings)  # 建立 22 点到 B/T 中心的刚性截面映射。
    constraint_rank = int(np.linalg.matrix_rank(constraints.toarray(), tol=1.0e-9))  # 66 条三平动约束应满秩。
    stiffness_12, saddle_size = core.constrained_port_stiffness(stiffness_root, constraints, port_map)  # 得到保留中心转角的 12×12 刚度。
    rigid_12 = rigid_modes_12(core, centers)  # 构造六个整体刚体模态。
    rigid_residual_12 = np.linalg.norm(stiffness_12 @ rigid_12, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro") * np.linalg.norm(rigid_12, ord="fro"), 1.0)  # 12 自由度刚体残差。
    scaling = np.diag([1.0 if dof % 6 < 3 else 1.0 / ROTATION_SCALE_MM for dof in range(12)])  # 将转角缩放为 1 m 位移量级。
    scaled_12 = 0.5 * (scaling.T @ stiffness_12 @ scaling + scaling.T @ stiffness_12.T @ scaling)  # 构造量纲一致的对称审计矩阵。
    eigen_12_scaled = np.linalg.eigvalsh(scaled_12)  # 预期八零四正。
    stiffness_6_raw, stiffness_6_fixed_rotation, eigen_rr = condense_free_rotations(stiffness_12)  # 得到自由转角和固定转角两种口径。
    rigid_6 = rigid_modes_6(core, centers)  # 两点平动端只有五维可观察刚体运动。
    rigid_rank_6 = int(np.linalg.matrix_rank(rigid_6, tol=1.0e-10))  # 预期秩五。
    raw_rigid_residual_6 = np.linalg.norm(stiffness_6_raw @ rigid_6, ord="fro") / max(np.linalg.norm(stiffness_6_raw, ord="fro") * np.linalg.norm(rigid_6, ord="fro"), 1.0)  # 清理前刚体残差。
    stiffness_6, axial_eigenvalue, cleanup_correction, axial_shape = clean_axial_k6(stiffness_6_raw, rigid_6)  # 投影为严格球铰轴向秩一矩阵。
    rigid_residual_6 = np.linalg.norm(stiffness_6 @ rigid_6, ord="fro") / max(np.linalg.norm(stiffness_6, ord="fro") * np.linalg.norm(rigid_6, ord="fro"), 1.0)  # 清理后刚体残差。
    eigen_6 = np.linalg.eigvalsh(stiffness_6)  # 预期五零一正。
    local_basis, center_length = local_portal_basis(centers)  # 构造局部门架轴和两剪切轴。
    axial_direction = local_basis[:, 2]  # 取 B→T 轴向单位向量。
    k_axial = float(axial_direction @ stiffness_6[3:6, 3:6] @ axial_direction)  # 两节点轴杆 EA/L。
    equivalent_ea = k_axial * center_length  # 换算门架自由转角等效 EA，单位 N。
    equivalent_area = equivalent_ea / E_STEEL  # 换算 E=206 GPa 下等效面积。
    portal_relative_global = 0.5 * (stiffness_6_fixed_rotation[3:6, 3:6] + stiffness_6_fixed_rotation[3:6, 3:6].T)  # 两中心转角均固定时 T 端相对刚度。
    portal_relative_local = local_basis.T @ portal_relative_global @ local_basis  # 转到 Sx、Sy、N 局部方向。
    mct_k_axial = E_STEEL * MCT_PROPERTY3_AREA_MM2 / center_length  # 原 property-3 B161×161×8 TRUSS 轴向刚度。
    mct_ratio = k_axial / mct_k_axial  # 有限门架自由轴向刚度相对原 TRUSS。
    axial_energies, axial_energy_fractions, axial_total_energy, axial_port_energy, axial_energy_balance_error, axial_optimal_rotations = axial_energy_breakdown(core, nodes, elements, sections, stiffness_root, constraints, port_map, stiffness_12, root_index, node_map, axial_direction)  # 回代证明等效轴向柔度来源。
    labels_12 = [f"{port}_{dof}" for port in PORTS for dof in ("UX", "UY", "UZ", "RX", "RY", "RZ")]  # 保留转角矩阵标签。
    labels_6 = [f"{port}_{dof}" for port in PORTS for dof in ("UX", "UY", "UZ")]  # 两平动端矩阵标签。
    write_matrix_csv(OUTPUT / "K12_gate_ports_6dof.csv", stiffness_12, labels_12)  # 保存 N-mm 混合量纲的保留转角矩阵。
    write_matrix_csv(OUTPUT / "K6_gate_translation_free_rotation_N_per_mm.csv", stiffness_6, labels_6)  # 保存自由转角球铰端 K6，单位 N/mm。
    write_matrix_csv(OUTPUT / "K6_gate_translation_free_rotation_N_per_m.csv", stiffness_6 * 1000.0, labels_6)  # 保存 SI 主 ROM 版本，单位 N/m。
    write_matrix_csv(OUTPUT / "K6_gate_translation_free_rotation_raw.csv", stiffness_6_raw, labels_6)  # 保存数值清理前 Schur 补。
    write_matrix_csv(OUTPUT / "K6_gate_translation_fixed_rotation_portal_N_per_mm.csv", stiffness_6_fixed_rotation, labels_6)  # 保存端转角固定的 portal 上限矩阵。
    write_matrix_csv(OUTPUT / "Krel3_fixed_rotation_local_N_per_mm.csv", portal_relative_local, ("Sx_long", "Sy_trans", "N_axis"))  # 保存局部相对平动三乘三刚度。
    np.savez_compressed(OUTPUT / "H10_gate_only_condensed.npz", K12_gate_ports_mixed_N_mm=stiffness_12, K6_free_rotation_N_per_mm=stiffness_6, K6_free_rotation_N_per_m=stiffness_6 * 1000.0, K6_fixed_rotation_portal_N_per_mm=stiffness_6_fixed_rotation, Krel3_fixed_rotation_local_N_per_mm=portal_relative_local, port_labels_12=np.asarray(labels_12), port_labels_6=np.asarray(labels_6), centers_mm=np.vstack((centers["B"], centers["T"])), centers_m=np.vstack((centers["B"], centers["T"])) / 1000.0, local_basis_columns_Sx_Sy_N=local_basis, axial_shape_K6=axial_shape)  # 保存 ROM 可直接加载的数据包且不含质量。
    with (OUTPUT / "port_coordinates.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存 B/T 中心坐标。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("port", "x_long_mm", "y_trans_mm", "z_vert_mm", "actual_rope_nodes"))  # 明确 APDL 坐标和索数。
        for port in PORTS:  # 按矩阵端口顺序输出。
            writer.writerow((port,) + tuple(f"{value:.12f}" for value in centers[port]) + (group_counts[port],))  # 写入一端中心数据。
    with (OUTPUT / "equivalent_parameters.csv").open("w", encoding="utf-8", newline="") as stream:  # 汇总轴向与 portal 近似参数。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("parameter", "value", "unit", "interpretation"))  # 给出参数语义而非仅给数值。
        writer.writerow(("center_length", f"{center_length:.12e}", "mm", "distance B to T"))  # 门架两索族中心距。
        writer.writerow(("gate_free_rotation_axial_k", f"{k_axial:.12e}", "N/mm", "objective rank-one spherical-port stiffness"))  # 正式可替换 TRUSS 的轴向刚度。
        writer.writerow(("gate_free_rotation_equivalent_EA", f"{equivalent_ea:.12e}", "N", "EA=kL"))  # 等效轴刚度。
        writer.writerow(("gate_free_rotation_equivalent_area_at_E206GPa", f"{equivalent_area:.12e}", "mm2", "A=EA/E"))  # 等效截面积。
        writer.writerow(("MCT_property3_area_B161x161x8", f"{MCT_PROPERTY3_AREA_MM2:.12e}", "mm2", "decoded from section 3"))  # 原 MCT 等效箱形面积。
        writer.writerow(("MCT_property3_axial_k", f"{mct_k_axial:.12e}", "N/mm", "E*A/L with E=206000"))  # 原 TRUSS 轴向刚度。
        writer.writerow(("finite_gate_to_MCT_property3_k_ratio", f"{mct_ratio:.12e}", "-", "ratio of axial stiffnesses"))  # 判断是否需要重新标定。
        writer.writerow(("portal_fixed_rotation_k_Sx", f"{portal_relative_local[0, 0]:.12e}", "N/mm", "upper-bound longitudinal portal shear"))  # 顺桥 portal 剪切上限。
        writer.writerow(("portal_fixed_rotation_k_Sy", f"{portal_relative_local[1, 1]:.12e}", "N/mm", "upper-bound transverse in-plane portal shear"))  # 横桥 portal 剪切上限。
        writer.writerow(("portal_fixed_rotation_k_N", f"{portal_relative_local[2, 2]:.12e}", "N/mm", "fixed-rotation axial term"))  # 固定转角轴向项。
    with (OUTPUT / "H10_gate_beam188_elements.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存 30 根普通门架物理梁清单。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("element_id", "n1", "n2", "orientation_node", "material", "section", "length_mm"))  # 明确方向节点不含物理自由度。
        for element, length in zip(elements, beam_lengths):  # 元素顺序与组装长度顺序一致。
            writer.writerow((element["id"], element["n1"], element["n2"], element["orient"], element["material"], element["section"], f"{length:.12f}"))  # 写出稳定编号和梁长。
    with (OUTPUT / "H10_gate_internal_all_rigid_links.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存四条梁—立柱刚臂。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("source_line", "master", "slave", "dof", "dx_mm", "dy_mm", "dz_mm"))  # 记录完整偏置刚体运动。
        for record in internal_rigid:  # 按正式 APDL 行序输出。
            offset = nodes[record["slave"]] - nodes[record["master"]]  # 计算主从偏置。
            writer.writerow((record["line"], record["master"], record["slave"], record["dof"]) + tuple(f"{value:.12f}" for value in offset))  # 写出连接几何。
    external_by_slave = {record["slave"]: record for record in external_rigid}  # 为索接口明细查找门架 master。
    with (OUTPUT / "H10_gate_rope_interface_mapping.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存 22 个实际索点的中心映射。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("port", "family", "rope_index", "rope_node", "gate_master", "rope_x_long_mm", "rope_y_trans_mm", "rope_z_vert_mm", "center_dx_mm", "center_dy_mm", "center_dz_mm"))  # 明确虚功映射几何。
        for record in couplings:  # 按权威 CSV 顺序输出。
            center_offset = record["point"] - centers[record["port"]]  # 实际索点相对 B/T 中心的偏置。
            master = external_by_slave[record["slave"]]["master"]  # 对应门架梁轴 master。
            writer.writerow((record["port"], record["family"], record["rope_index"], record["slave"], master) + tuple(f"{value:.12f}" for value in record["point"]) + tuple(f"{value:.12f}" for value in center_offset))  # 写出一一映射。
    with (OUTPUT / "unit_axial_energy_breakdown.csv").open("w", encoding="utf-8", newline="") as stream:  # 保存 1 mm 轴向相对位移的逐类能量证据。
        writer = csv.writer(stream)  # 创建 CSV 写入器。
        writer.writerow(("component", "strain_energy_N_mm", "fraction"))  # 明确能量单位和占比。
        for component in ("bottom_beam", "top_beam", "posts"):  # 按结构传力顺序输出。
            writer.writerow((component, f"{axial_energies[component]:.12e}", f"{axial_energy_fractions[component]:.12e}"))  # 写出分项能量。
        writer.writerow(("total", f"{axial_total_energy:.12e}", "1.000000000000e+00"))  # 写出能量总和。
    maximum_12 = max(float(np.max(np.abs(eigen_12_scaled))), 1.0)  # 12 自由度相对零模态阈值基准。
    zero_12 = int(np.sum(np.abs(eigen_12_scaled) <= maximum_12 * 1.0e-8))  # 预期六整体刚体加两钻转共八。
    positive_12 = int(np.sum(eigen_12_scaled > maximum_12 * 1.0e-8))  # 预期四个可观察变形模态。
    maximum_6 = max(float(np.max(np.abs(eigen_6))), 1.0)  # K6 相对零模态阈值基准。
    zero_6 = int(np.sum(np.abs(eigen_6) <= maximum_6 * 1.0e-8))  # 预期五个球铰刚体机制。
    positive_6 = int(np.sum(eigen_6 > maximum_6 * 1.0e-8))  # 预期唯一轴向正模态。
    replacement = {"ordinary_stations_per_catwalk": 50, "translation_only_verdict": "yes, but only as an axial rank-one replacement for property-3 TRUSS; do not retain both", "reason": "after free condensation of center rotations the two translation ports form spherical joints and have five zero modes; only centerline extension is objective", "implementation": "use EA_eq=1.994057190978e8 N at each ordinary station and construct K_i=(EA_eq/L_i)[nn^T,-nn^T;-nn^T,nn^T] from that station's B-to-T direction; do not copy the H10 global matrix to differently inclined stations", "cross_passage_rule": "apply gate-only replacement at the 50 ordinary stations per catwalk only; the 21 combined gate-passage K12 matrices already include both gates, so adding gate-only stiffness there would double count", "axial_comparison": {"finite_gate_k_N_per_mm": k_axial, "finite_gate_equivalent_EA_N": equivalent_ea, "mct_property3_k_N_per_mm": mct_k_axial, "ratio": mct_ratio, "warning": "the finite-gate equivalent is only 19.77% of original property-3 axial stiffness, so replacing all 50 stations materially changes modes and requires full-bridge modal revalidation"}, "portal_shear_verdict": "two translation-only ports cannot represent portal shear objectively; retained K12 captures transverse Sy behavior but longitudinal Sx remains a mechanism because B_RY/T_RY are unobservable", "portal_options": ["preferred when rotational states exist: retain K12_gate_ports_6dof.csv; omit the two zero RY drilling DOFs and retain the observable transverse portal rotations", "translation-only sensitivity closure: axial k_N=24925.7008 N/mm plus transverse fixed-section upper-bound k_Sy=80.7156 N/mm, with k_Sx=0; this shear spring is non-objective under isolated rigid rotation and is not a formal replacement", "strict objective translation-only ROM: use only the rank-one axial K6 and accept that ordinary gates add no portal shear"], "mass_rule": "the gate-only condensed matrices contain stiffness only; preserve the existing concentrated gate/guide mass once and do not add BEAM188 mass"}  # 形成明确的替换判断。
    audit = {"source": {"core_script": str(CORE_PATH.relative_to(ROOT)), "formal_apdl": str(core.APDL.relative_to(ROOT)), "formal_apdl_sha256": core.sha256(core.APDL), "mct": str(MCT_PATH.relative_to(ROOT)), "mct_property3_section": "B161x161x8 equivalent, name denotes two B160x4 posts", "representative_gate": "H10/CW1_GATE_32"}, "topology": {"beam188_elements": len(elements), "physical_nodes": len(physical_nodes), "orientation_nodes": len({element["orient"] for element in elements}), "internal_ALL_rigid_links": len(internal_rigid), "external_UXYZ_rope_links": len(external_rigid), "root_nodes": len(root_nodes), "root_dofs": stiffness_root.shape[0], "constraint_rows": constraints.shape[0], "constraint_rank": constraint_rank, "saddle_size": saddle_size, "rope_counts": group_counts, "beam_length_mm_min": float(beam_lengths.min()), "beam_length_mm_max": float(beam_lengths.max())}, "interfaces": {"port_order": list(PORTS), "center_coordinates_apdl_mm": {port: centers[port].tolist() for port in PORTS}, "center_length_mm": center_length, "mapping": "16/6 actual rope translations mapped by u_i=u_c+theta_c cross r_i; rope rotations absent"}, "mass_policy": {"source_material_densities_tonne_per_mm3": {str(section_id): float(densities[section_id]) for section_id in (61, 62)}, "mass_matrix_generated": False, "duplicate_mass_added": False}, "retained_rotation_K12_audit": {"symmetry_error": float(np.linalg.norm(stiffness_12 - stiffness_12.T, ord="fro") / max(np.linalg.norm(stiffness_12, ord="fro"), 1.0)), "rigid_body_residual": float(rigid_residual_12), "scaled_eigenvalues": eigen_12_scaled.tolist(), "zero_mode_count_rel_1e_8": zero_12, "positive_mode_count_rel_1e_8": positive_12, "zero_mode_interpretation": "6 global rigid-body modes + independent RY drilling rotations at the two collinear rope groups"}, "free_rotation_K6_audit": {"raw_rigid_body_residual": float(raw_rigid_residual_6), "psd_cleanup_relative_correction": float(cleanup_correction), "rigid_mode_matrix_rank": rigid_rank_6, "symmetry_error": float(np.linalg.norm(stiffness_6 - stiffness_6.T, ord="fro") / max(np.linalg.norm(stiffness_6, ord="fro"), 1.0)), "rigid_body_residual": float(rigid_residual_6), "eigenvalues_N_per_mm": eigen_6.tolist(), "zero_mode_count_rel_1e_8": zero_6, "positive_mode_count_rel_1e_8": positive_6, "axial_nonzero_eigenvalue_N_per_mm": axial_eigenvalue, "spherical_hinge_mechanism": True}, "unit_axial_energy_audit": {"prescribed_relative_displacement_mm": 1.0, "component_energy_N_mm": axial_energies, "component_energy_fraction": axial_energy_fractions, "sum_energy_N_mm": axial_total_energy, "condensed_port_energy_N_mm": axial_port_energy, "relative_balance_error": axial_energy_balance_error, "optimal_port_rotations_rad": axial_optimal_rotations.tolist()}, "fixed_rotation_portal_local_Krel_N_per_mm": portal_relative_local.tolist(), "replacement_assessment": replacement}  # 汇总机器审计。
    (OUTPUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 保存完整审计。
    (OUTPUT / "replacement_assessment.json").write_text(json.dumps(replacement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 单独保存主 ROM 决策摘要。
    readme = ["# H10 普通有限门架两索族端口凝聚", "", "对象为 `CW1_GATE_32` 的 30 根 BEAM188，不含 H10 横向通道。16 个承重索点和 6 个门架索点分别用刚性截面虚功映射到 B/T 中心；只约束实际索点平动，不给索施加转角。", "", "## 核心结论", "", "中心转角全部自由凝聚后，B/T 两个平动端是球铰端口：6×6 K 只有一个正轴向模态和五个零模态。它可以作为原 property-3 TRUSS 的秩一轴向替代，但不能产生客观的 portal shear；原 TRUSS 与该 K6 只能二选一，不能叠加。", "", "自由转角有限门架给出 `k_N=24,925.7008 N/mm`、`EA_eq=1.99405719e8 N`、`A_eq=967.989 mm2`。原 property-3 的 B161×161×8 等效面积为 4896 mm2，H10 处 `k=126,071.929 N/mm`；有限门架只有原刚度的 19.77%。因此可以替换，但不是无影响替换，50 个普通站全部更新后必须重新校核全桥模态。", "", "对各普通站应使用同一 `EA_eq` 和该站 B→T 的实际方向、长度重新形成轴杆 K；不可把 H10 的全局 6×6 数值原样复制到有不同倾角的站位。21 个横通道站已由四端口 gate-passage K12 包含两品门架，不能再叠加本门架 K6。", "", "保留转角的 `K12_gate_ports_6dof.csv` 可描述横桥 Sy 方向的 portal 行为，但 B/T 索点各自沿横桥 Y 共线，B_RY、T_RY 是不可观察钻转，所以顺桥 Sx 剪切仍是机制。K12 正常具有 6 个整体刚体模态和 2 个钻转零模态。", "", "`K6_gate_translation_fixed_rotation_portal_N_per_mm.csv` 是截面转角受限的灵敏度上限。局部参数约为 `k_Sx=0`、`k_Sy=80.7156 N/mm`、`k_N=24,925.7008 N/mm`；其中两节点 Sy 剪切弹簧会在孤立刚体转动下产生伪能量，只能作包络，不能冒充正式客观连接。", "", "## 文件", "", "- `K6_gate_translation_free_rotation_N_per_mm.csv` / `_N_per_m.csv`：正式两平动端秩一轴向矩阵。", "- `K12_gate_ports_6dof.csv`：保留可观察中心转角的门架矩阵。", "- `Krel3_fixed_rotation_local_N_per_mm.csv`：局部 Sx、Sy、N 的固定转角 portal 上限。", "- `equivalent_parameters.csv`：EA、等效面积、property-3 对比和 portal 参数。", "- `H10_gate_only_condensed.npz`：上述矩阵和接口坐标的数据包。", "- `H10_gate_beam188_elements.csv`、`H10_gate_internal_all_rigid_links.csv`、`H10_gate_rope_interface_mapping.csv`：正式提取明细。", "", "## 质量", "", "仅凝聚刚度；正式 APDL 的门架梁材料密度为 0。本结果不含质量，50 个普通站仍只保留既有门架/导轮集中质量一次。", ""]  # 形成人工复核说明。
    (OUTPUT / "README.md").write_text("\n".join(readme), encoding="utf-8")  # 保存说明文档。
    print(json.dumps({"output": str(OUTPUT), "K6_eigenvalues_N_per_mm": eigen_6.tolist(), "k_axial_N_per_mm": k_axial, "equivalent_area_mm2": equivalent_area, "MCT_property3_k_N_per_mm": mct_k_axial, "ratio": mct_ratio, "portal_local_diagonal_N_per_mm": np.diag(portal_relative_local).tolist(), "verdict": replacement["translation_only_verdict"]}, ensure_ascii=False, indent=2))  # 打印关键结果供父任务读取。

if __name__ == "__main__":  # 仅直接执行时开展普通门架凝聚。
    main()  # 开始计算。
