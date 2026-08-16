from __future__ import annotations  # 启用延迟类型注解，保证前向类型引用稳定。
import argparse  # 解析命令行参数。
import csv  # 写出区域、粒子群和方案指标表。
import json  # 读写VLM观察、意图和最终摘要。
import math  # 提供标量数学函数。
import time  # 统计各阶段墙钟时间。
from dataclasses import asdict  # 将数据类转换为可序列化字典。
from dataclasses import dataclass  # 定义结构化配置和结果对象。
from pathlib import Path  # 跨平台管理输出路径。
from typing import Any  # 标注异质JSON对象。
import matplotlib  # 导入Matplotlib主包。
matplotlib.use("Agg")  # 使用无界面后端，保证服务器本地运行。
import matplotlib.pyplot as plt  # 生成网格、应力和PSO图。
import numpy as np  # 执行有限元、恢复估计和粒子群数值计算。
from matplotlib import cm  # 将应力标量映射到表面颜色。
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # 绘制三维外表面三角形。
from scipy.sparse import coo_matrix  # 以坐标格式装配稀疏刚度矩阵。
from scipy.sparse import csr_matrix  # 标注压缩行稀疏矩阵类型。
from scipy.sparse.linalg import spsolve  # 求解施加边界条件后的线性系统。

@dataclass(frozen=True)  # 将几何配置定义为不可变对象。
class Geometry:  # 描述沿x轴延伸的三维实体T梁。
    length: float = 6.0  # 梁长，单位为米。
    flange_width: float = 1.2  # 翼缘总宽度，单位为米。
    total_height: float = 1.0  # 截面总高度，单位为米。
    web_thickness: float = 0.24  # 腹板厚度，单位为米。
    flange_thickness: float = 0.20  # 翼缘厚度，单位为米。
    root_fraction: float = 0.22  # 固定端高关注区长度比例。
    tip_fraction: float = 0.22  # 自由端载荷区长度比例。

@dataclass(frozen=True)  # 将材料配置定义为不可变对象。
class Material:  # 描述各向同性三维线弹性材料。
    young_modulus: float = 210.0e9  # 杨氏模量，单位为帕。
    poisson_ratio: float = 0.30  # 泊松比，无量纲。

@dataclass(frozen=True)  # 将荷载配置定义为不可变对象。
class Load:  # 描述自由端面总力。
    force_x: float = 0.0  # x方向总力，单位为牛。
    force_y: float = 0.0  # y方向总力，单位为牛。
    force_z: float = -1.0e6  # z方向总力，负号表示向下，单位为牛。

@dataclass(frozen=True)  # 将连续网格控制量定义为不可变对象。
class Action:  # 表示PSO解码的五维网格动作。
    hx_root: float  # 固定端区纵向目标尺寸。
    hx_mid: float  # 中部区纵向目标尺寸。
    hx_tip: float  # 自由端区纵向目标尺寸。
    h_web: float  # 腹板横截面目标尺寸。
    h_flange: float  # 翼缘横截面目标尺寸。

@dataclass  # 将三维网格组织为一个对象。
class Mesh:  # 保存节点、四面体、区域和动作信息。
    requested_action: Action  # 可重新编译相同整数网格的请求动作。
    realized_action: Action  # 由整数分段得到的实际特征尺寸。
    nodes: np.ndarray  # N乘3节点坐标。
    tets: np.ndarray  # M乘4四面体连接。
    regions: np.ndarray  # 六区域编号。
    signature: tuple[int, int, int, int, int, int, int]  # 七个一维分段数。

@dataclass  # 将求解结果组织为一个对象。
class Solution:  # 保存位移、应力、能量和平衡信息。
    displacement: np.ndarray  # N乘3节点位移。
    stress: np.ndarray  # M乘6单元常应力。
    strain: np.ndarray  # M乘6单元常应变。
    volume: np.ndarray  # M个单元体积。
    energy: np.ndarray  # M个单元应变能。
    force: np.ndarray  # 全局结点力向量。
    stiffness: csr_matrix  # 全局稀疏刚度矩阵。
    fixed_dofs: np.ndarray  # 固定端自由度。
    tip_displacement_z: float  # 自由端面积平均竖向位移。
    compliance: float  # 外力功。
    reaction_z: float  # 固定端z向总反力。
    seconds: float  # 完整装配与求解时间。

@dataclass  # 将ZZ恢复结果组织为一个对象。
class ZZ:  # 保存误差估计和恢复应力场。
    relative_error: float  # 全局相对ZZ能量指标。
    element_error_squared: np.ndarray  # 各单元误差能平方贡献。
    recovered_element_stress: np.ndarray  # 单元恢复应力。
    recovered_nodal_stress: np.ndarray  # 节点恢复应力。

@dataclass  # 将一个方案的核心指标组织为对象。
class Metrics:  # 保存比较和导出所需指标。
    name: str  # 方案名称。
    action: Action  # 请求动作。
    nodes: int  # 节点数。
    elements: int  # 四面体数。
    dof: int  # 总自由度。
    zz: float  # 相对ZZ指标。
    tip_z: float  # 自由端竖向位移。
    compliance: float  # 柔度。
    root_p95_vm: float  # 固定端区95分位von Mises应力。
    max_vm: float  # 全模型最大von Mises应力。
    min_quality: float  # 最小四面体质量。
    mean_quality: float  # 平均四面体质量。
    solve_seconds: float  # 完整求解耗时。

def action_array(action: Action) -> np.ndarray:  # 将动作转换为固定顺序数组。
    return np.array([action.hx_root, action.hx_mid, action.hx_tip, action.h_web, action.h_flange], dtype=float)  # 返回五维数组。

def action_object(values: np.ndarray) -> Action:  # 将五维数组转换为动作对象。
    return Action(float(values[0]), float(values[1]), float(values[2]), float(values[3]), float(values[4]))  # 返回类型化动作。

def coarse_action() -> Action:  # 返回默认一次粗解动作。
    return Action(0.45, 0.65, 0.45, 0.24, 0.22)  # 使用经过实跑验证的粗网格尺寸。

def action_bounds(coarse: Action, geometry: Geometry) -> tuple[np.ndarray, np.ndarray]:  # 建立安全连续动作域。
    lower = np.array([0.12, 0.20, 0.12, 0.08, 0.07], dtype=float)  # 控制最细网格和计算规模。
    caps = np.array([geometry.length * geometry.root_fraction, geometry.length * (1.0 - geometry.root_fraction - geometry.tip_fraction), geometry.length * geometry.tip_fraction, min(geometry.web_thickness, geometry.total_height - geometry.flange_thickness), min(0.5 * (geometry.flange_width - geometry.web_thickness), geometry.flange_thickness)], dtype=float)  # 建立几何上限。
    upper = np.minimum(action_array(coarse), caps)  # 禁止终局动作在任一维度比粗网格更粗。
    return lower, upper  # 返回下界与上界。

def segment_count(start: float, end: float, target: float) -> int:  # 将连续目标尺寸转换为整数分段数。
    return max(1, int(math.ceil((end - start) / max(target, 1.0e-12))))  # 向上取整保证实际尺寸不超过目标。

def segment_coordinates(start: float, end: float, count: int) -> np.ndarray:  # 生成含端点的一维均匀坐标。
    return np.linspace(start, end, count + 1, dtype=float)  # 返回坐标数组。

def join_segments(parts: list[np.ndarray]) -> np.ndarray:  # 无重复地拼接相邻坐标段。
    result = parts[0]  # 以第一段为起始。
    for part in parts[1:]:  # 遍历其余坐标段。
        result = np.concatenate([result, part[1:]])  # 删除重复接口端点后拼接。
    return result  # 返回完整坐标轴。

def mesh_signature(geometry: Geometry, action: Action) -> tuple[int, int, int, int, int, int, int]:  # 计算动作对应的七个整数分段数。
    root_end = geometry.length * geometry.root_fraction  # 计算固定端区终点。
    tip_start = geometry.length * (1.0 - geometry.tip_fraction)  # 计算自由端区起点。
    web_top = geometry.total_height - geometry.flange_thickness  # 计算腹板顶部。
    half_width = 0.5 * geometry.flange_width  # 计算翼缘半宽。
    half_web = 0.5 * geometry.web_thickness  # 计算腹板半厚。
    nx_root = segment_count(0.0, root_end, action.hx_root)  # 固定端区纵向分段数。
    nx_mid = segment_count(root_end, tip_start, action.hx_mid)  # 中部区纵向分段数。
    nx_tip = segment_count(tip_start, geometry.length, action.hx_tip)  # 自由端区纵向分段数。
    ny_overhang = segment_count(-half_width, -half_web, action.h_flange)  # 单侧翼缘悬臂分段数。
    ny_web = segment_count(-half_web, half_web, min(action.h_web, action.h_flange))  # 腹板厚度区分段数。
    nz_web = segment_count(0.0, web_top, action.h_web)  # 腹板高度分段数。
    nz_flange = segment_count(web_top, geometry.total_height, action.h_flange)  # 翼缘厚度分段数。
    return nx_root, nx_mid, nx_tip, ny_overhang, ny_web, nz_web, nz_flange  # 返回稳定签名。

def compile_mesh(geometry: Geometry, action: Action) -> Mesh:  # 将五维动作确定性编译为相容四面体T梁网格。
    nx_root, nx_mid, nx_tip, ny_overhang, ny_web, nz_web, nz_flange = mesh_signature(geometry, action)  # 取得整数分段数。
    root_end = geometry.length * geometry.root_fraction  # 计算固定端区终点。
    tip_start = geometry.length * (1.0 - geometry.tip_fraction)  # 计算自由端区起点。
    web_top = geometry.total_height - geometry.flange_thickness  # 计算腹板顶部。
    half_width = 0.5 * geometry.flange_width  # 计算翼缘半宽。
    half_web = 0.5 * geometry.web_thickness  # 计算腹板半厚。
    x = join_segments([segment_coordinates(0.0, root_end, nx_root), segment_coordinates(root_end, tip_start, nx_mid), segment_coordinates(tip_start, geometry.length, nx_tip)])  # 生成三段纵向坐标。
    y = join_segments([segment_coordinates(-half_width, -half_web, ny_overhang), segment_coordinates(-half_web, half_web, ny_web), segment_coordinates(half_web, half_width, ny_overhang)])  # 生成T截面宽度坐标。
    z = join_segments([segment_coordinates(0.0, web_top, nz_web), segment_coordinates(web_top, geometry.total_height, nz_flange)])  # 生成T截面高度坐标。
    nx, ny, nz = len(x), len(y), len(z)  # 取得三个方向节点数。
    def raw_index(i: int, j: int, k: int) -> int:  # 将三维结构化索引映射到一维。
        return (i * ny + j) * nz + k  # 返回一维节点索引。
    raw_nodes = np.array([(xx, yy, zz) for xx in x for yy in y for zz in z], dtype=float)  # 生成完整张量积候选节点。
    hexes: list[list[int]] = []  # 创建实体六面体列表。
    hex_regions: list[int] = []  # 创建六面体区域标签列表。
    for i in range(nx - 1):  # 遍历纵向单元层。
        xc = 0.5 * (x[i] + x[i + 1])  # 计算当前六面体纵向中心。
        x_zone = 0 if xc < root_end else (1 if xc < tip_start else 2)  # 确定根部、中部或端部区。
        for j in range(ny - 1):  # 遍历宽度单元层。
            yc = 0.5 * (y[j] + y[j + 1])  # 计算宽度中心。
            for k in range(nz - 1):  # 遍历高度单元层。
                zc = 0.5 * (z[k] + z[k + 1])  # 计算高度中心。
                in_flange = zc >= web_top - 1.0e-12  # 判断是否位于翼缘实体。
                in_web = abs(yc) <= half_web + 1.0e-12  # 判断是否位于腹板实体。
                if not (in_flange or in_web):  # 排除T截面两侧空腔。
                    continue  # 跳过空腔六面体。
                vertices = [raw_index(i, j, k), raw_index(i + 1, j, k), raw_index(i + 1, j + 1, k), raw_index(i, j + 1, k), raw_index(i, j, k + 1), raw_index(i + 1, j, k + 1), raw_index(i + 1, j + 1, k + 1), raw_index(i, j + 1, k + 1)]  # 收集八节点。
                hexes.append(vertices)  # 保存实体六面体。
                hex_regions.append(2 * x_zone + (1 if in_flange else 0))  # 组合六区域编号。
    if not hexes:  # 检查是否产生实体单元。
        raise ValueError("mesh action produced no solid cells")  # 显式报告非法动作。
    pattern = np.array([[0, 1, 2, 6], [0, 2, 3, 6], [0, 3, 7, 6], [0, 7, 4, 6], [0, 4, 5, 6], [0, 5, 1, 6]], dtype=int)  # 定义一致的六四面体分解。
    raw_tets = np.vstack([np.asarray(cell, dtype=int)[pattern] for cell in hexes])  # 将每个六面体分解为六个四面体。
    regions = np.repeat(np.asarray(hex_regions, dtype=int), 6)  # 将区域标签复制给子四面体。
    used = np.unique(raw_tets)  # 查找真正被实体使用的节点。
    remap = -np.ones(len(raw_nodes), dtype=int)  # 创建紧凑节点映射。
    remap[used] = np.arange(len(used), dtype=int)  # 为已使用节点分配连续编号。
    nodes = raw_nodes[used]  # 删除空腔中的悬空节点。
    tets = remap[raw_tets]  # 将连接转换为紧凑节点编号。
    coords = nodes[tets]  # 收集每个四面体坐标。
    dets = np.linalg.det(np.stack([coords[:, 1] - coords[:, 0], coords[:, 2] - coords[:, 0], coords[:, 3] - coords[:, 0]], axis=2))  # 计算有向六倍体积。
    negative = dets < 0.0  # 标记负方向四面体。
    temporary = tets[negative, 2].copy()  # 临时保存第三节点。
    tets[negative, 2] = tets[negative, 3]  # 交换第三与第四节点。
    tets[negative, 3] = temporary  # 完成正方向修正。
    realized = Action(root_end / nx_root, (tip_start - root_end) / nx_mid, (geometry.length - tip_start) / nx_tip, math.sqrt((geometry.web_thickness / ny_web) * (web_top / nz_web)), math.sqrt(((half_width - half_web) / ny_overhang) * (geometry.flange_thickness / nz_flange)))  # 记录实际分段特征尺寸。
    return Mesh(action, realized, nodes, tets, regions, (nx_root, nx_mid, nx_tip, ny_overhang, ny_web, nz_web, nz_flange))  # 返回完整网格。

def elasticity_matrix(material: Material) -> np.ndarray:  # 构造三维各向同性本构矩阵。
    young = material.young_modulus  # 读取杨氏模量。
    poisson = material.poisson_ratio  # 读取泊松比。
    lame_lambda = young * poisson / ((1.0 + poisson) * (1.0 - 2.0 * poisson))  # 计算第一拉梅常数。
    shear = young / (2.0 * (1.0 + poisson))  # 计算剪切模量。
    return np.array([[lame_lambda + 2.0 * shear, lame_lambda, lame_lambda, 0.0, 0.0, 0.0], [lame_lambda, lame_lambda + 2.0 * shear, lame_lambda, 0.0, 0.0, 0.0], [lame_lambda, lame_lambda, lame_lambda + 2.0 * shear, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, shear, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, shear, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, shear]], dtype=float)  # 返回六乘六本构矩阵。

def b_matrix_volume(coordinates: np.ndarray) -> tuple[np.ndarray, float]:  # 计算C3D4单元B矩阵和体积。
    interpolation = np.column_stack([np.ones(4, dtype=float), coordinates])  # 构造线性形函数插值矩阵。
    coefficients = np.linalg.inv(interpolation)  # 反演得到形函数系数。
    gradients = coefficients[1:, :].T  # 取得四个形函数的空间梯度。
    b = np.zeros((6, 12), dtype=float)  # 初始化应变位移矩阵。
    for local_node, (dx, dy, dz) in enumerate(gradients):  # 遍历四个节点。
        column = 3 * local_node  # 计算当前节点自由度起始列。
        b[0, column] = dx  # 写入epsilon_xx项。
        b[1, column + 1] = dy  # 写入epsilon_yy项。
        b[2, column + 2] = dz  # 写入epsilon_zz项。
        b[3, column] = dy  # 写入gamma_xy对u_x项。
        b[3, column + 1] = dx  # 写入gamma_xy对u_y项。
        b[4, column + 1] = dz  # 写入gamma_yz对u_y项。
        b[4, column + 2] = dy  # 写入gamma_yz对u_z项。
        b[5, column] = dz  # 写入gamma_xz对u_x项。
        b[5, column + 2] = dx  # 写入gamma_xz对u_z项。
    edge_matrix = np.stack([coordinates[1] - coordinates[0], coordinates[2] - coordinates[0], coordinates[3] - coordinates[0]], axis=1)  # 构造三条边向量矩阵。
    volume = abs(float(np.linalg.det(edge_matrix))) / 6.0  # 计算四面体体积。
    return b, volume  # 返回B矩阵和体积。

def boundary_faces(tets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:  # 提取外表面及所属四面体。
    templates = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=int)  # 定义四个局部面。
    faces = np.vstack([tets[:, template] for template in templates])  # 展开全部四面体面。
    owners = np.tile(np.arange(len(tets), dtype=int), 4)  # 记录每个展开面的所属单元。
    sorted_faces = np.sort(faces, axis=1)  # 忽略面方向进行拓扑排序。
    _, inverse, counts = np.unique(sorted_faces, axis=0, return_inverse=True, return_counts=True)  # 统计每个面的出现次数。
    exterior = counts[inverse] == 1  # 外表面只出现一次。
    return faces[exterior], owners[exterior]  # 返回外表面与所属单元。

def triangle_areas(nodes: np.ndarray, faces: np.ndarray) -> np.ndarray:  # 批量计算三角形面积。
    coords = nodes[faces]  # 收集三角面坐标。
    return 0.5 * np.linalg.norm(np.cross(coords[:, 1] - coords[:, 0], coords[:, 2] - coords[:, 0]), axis=1)  # 返回叉积模长一半。

def solve(mesh: Mesh, geometry: Geometry, material: Material, load: Load) -> Solution:  # 装配并求解三维静态线弹性问题。
    start = time.perf_counter()  # 记录求解起始时间。
    constitutive = elasticity_matrix(material)  # 构造本构矩阵。
    element_count = len(mesh.tets)  # 取得四面体数。
    node_count = len(mesh.nodes)  # 取得节点数。
    rows = np.empty(element_count * 144, dtype=int)  # 预分配稀疏矩阵行索引。
    columns = np.empty(element_count * 144, dtype=int)  # 预分配稀疏矩阵列索引。
    values = np.empty(element_count * 144, dtype=float)  # 预分配刚度数值。
    b_matrices = np.empty((element_count, 6, 12), dtype=float)  # 保存单元B矩阵。
    volumes = np.empty(element_count, dtype=float)  # 保存单元体积。
    cursor = 0  # 初始化稀疏条目游标。
    for element_index, connectivity in enumerate(mesh.tets):  # 遍历所有四面体。
        b, volume = b_matrix_volume(mesh.nodes[connectivity])  # 计算单元B矩阵和体积。
        if volume <= 1.0e-15:  # 检查退化单元。
            raise ValueError(f"degenerate tetrahedron at {element_index}")  # 显式报告非法网格。
        b_matrices[element_index] = b  # 保存B矩阵。
        volumes[element_index] = volume  # 保存体积。
        stiffness_element = b.T @ constitutive @ b * volume  # 计算十二乘十二单元刚度。
        dofs = np.ravel(np.column_stack([3 * connectivity, 3 * connectivity + 1, 3 * connectivity + 2]))  # 构造十二自由度索引。
        block = slice(cursor, cursor + 144)  # 定义当前单元条目块。
        rows[block] = np.repeat(dofs, 12)  # 写入行索引。
        columns[block] = np.tile(dofs, 12)  # 写入列索引。
        values[block] = stiffness_element.ravel()  # 写入刚度数值。
        cursor += 144  # 推进条目游标。
    stiffness = coo_matrix((values, (rows, columns)), shape=(3 * node_count, 3 * node_count)).tocsr()  # 汇总全局刚度矩阵。
    force = np.zeros(3 * node_count, dtype=float)  # 初始化全局结点力。
    faces, _ = boundary_faces(mesh.tets)  # 提取完整外表面。
    tip_mask = np.all(np.isclose(mesh.nodes[faces, 0], geometry.length, atol=1.0e-10), axis=1)  # 识别自由端面。
    tip_faces = faces[tip_mask]  # 取得自由端三角面。
    if len(tip_faces) == 0:  # 检查自由端面是否存在。
        raise ValueError("free-end surface not found")  # 显式报告边界提取失败。
    areas = triangle_areas(mesh.nodes, tip_faces)  # 计算端面三角形面积。
    total_area = float(np.sum(areas))  # 汇总端面面积。
    traction = np.array([load.force_x, load.force_y, load.force_z], dtype=float) / total_area  # 将总力转换为均匀面牵引。
    for face, area in zip(tip_faces, areas):  # 遍历自由端面。
        nodal_force = traction * area / 3.0  # 计算线性三角形一致结点力。
        for node in face:  # 遍历三角面三个节点。
            force[3 * node:3 * node + 3] += nodal_force  # 累加三向结点力。
    fixed_nodes = np.flatnonzero(np.isclose(mesh.nodes[:, 0], 0.0, atol=1.0e-10))  # 识别固定端节点。
    fixed_dofs = np.ravel(np.column_stack([3 * fixed_nodes, 3 * fixed_nodes + 1, 3 * fixed_nodes + 2]))  # 约束固定端三向位移。
    all_dofs = np.arange(3 * node_count, dtype=int)  # 构造全部自由度索引。
    free_dofs = np.setdiff1d(all_dofs, fixed_dofs, assume_unique=False)  # 取得自由自由度。
    displacement_vector = np.zeros(3 * node_count, dtype=float)  # 初始化位移向量。
    displacement_vector[free_dofs] = spsolve(stiffness[free_dofs][:, free_dofs], force[free_dofs])  # 求解自由自由度线性系统。
    if not np.all(np.isfinite(displacement_vector)):  # 检查数值结果。
        raise FloatingPointError("non-finite displacement")  # 对求解失败立即报告。
    stress = np.empty((element_count, 6), dtype=float)  # 预分配单元应力。
    strain = np.empty((element_count, 6), dtype=float)  # 预分配单元应变。
    energy = np.empty(element_count, dtype=float)  # 预分配单元应变能。
    for element_index, connectivity in enumerate(mesh.tets):  # 遍历单元进行后处理。
        dofs = np.ravel(np.column_stack([3 * connectivity, 3 * connectivity + 1, 3 * connectivity + 2]))  # 构造当前单元自由度索引。
        element_strain = b_matrices[element_index] @ displacement_vector[dofs]  # 计算常应变。
        element_stress = constitutive @ element_strain  # 计算常应力。
        strain[element_index] = element_strain  # 保存应变。
        stress[element_index] = element_stress  # 保存应力。
        energy[element_index] = 0.5 * float(element_strain @ element_stress) * volumes[element_index]  # 计算单元应变能。
    displacement = displacement_vector.reshape((-1, 3))  # 将位移重排为节点三分量矩阵。
    tip_z = 0.0  # 初始化面积平均端部竖向位移。
    for face, area in zip(tip_faces, areas):  # 对端面进行面积积分。
        tip_z += float(np.mean(displacement[face, 2])) * area / total_area  # 累加面积加权位移。
    compliance = float(force @ displacement_vector)  # 计算外力功。
    reactions = stiffness @ displacement_vector - force  # 恢复全局反力。
    reaction_z = float(np.sum(reactions[fixed_dofs[fixed_dofs % 3 == 2]]))  # 汇总固定端z向反力。
    return Solution(displacement, stress, strain, volumes, energy, force, stiffness, fixed_dofs, tip_z, compliance, reaction_z, time.perf_counter() - start)  # 返回完整求解结果。

def von_mises(stress: np.ndarray) -> np.ndarray:  # 计算三维von Mises等效应力。
    sx, sy, sz, txy, tyz, txz = stress.T  # 解包六应力分量。
    normal = 0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)  # 计算法向偏应力项。
    shear = 3.0 * (txy ** 2 + tyz ** 2 + txz ** 2)  # 计算剪应力项。
    return np.sqrt(np.maximum(normal + shear, 0.0))  # 返回非负等效应力。

def recover_zz(mesh: Mesh, solution: Solution, material: Material) -> ZZ:  # 执行体积加权节点应力恢复和ZZ估计。
    nodal = np.zeros((len(mesh.nodes), 6), dtype=float)  # 初始化节点恢复应力累计量。
    weights = np.zeros(len(mesh.nodes), dtype=float)  # 初始化节点体积权重。
    for local_node in range(4):  # 遍历四个局部节点。
        np.add.at(nodal, mesh.tets[:, local_node], solution.stress * solution.volume[:, None])  # 累加体积加权单元应力。
        np.add.at(weights, mesh.tets[:, local_node], solution.volume)  # 累加体积权重。
    nodal /= np.maximum(weights[:, None], 1.0e-30)  # 归一化得到节点恢复应力。
    recovered_element = np.mean(nodal[mesh.tets], axis=1)  # 将节点恢复应力平均到单元中心。
    compliance_matrix = np.linalg.inv(elasticity_matrix(material))  # 构造应力能范数柔度矩阵。
    difference = recovered_element - solution.stress  # 计算恢复应力差。
    error_squared = solution.volume * np.einsum("ei,ij,ej->e", difference, compliance_matrix, difference)  # 计算单元误差能平方。
    recovered_energy = solution.volume * np.einsum("ei,ij,ej->e", recovered_element, compliance_matrix, recovered_element)  # 计算恢复场能量范数。
    relative = math.sqrt(max(float(np.sum(error_squared)) / max(float(np.sum(recovered_energy)), 1.0e-30), 0.0))  # 计算全局相对ZZ指标。
    return ZZ(relative, error_squared, recovered_element, nodal)  # 返回恢复结果。

def tetra_quality(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:  # 计算零到一范围的平均比质量。
    coords = nodes[tets]  # 收集四面体节点坐标。
    dets = np.linalg.det(np.stack([coords[:, 1] - coords[:, 0], coords[:, 2] - coords[:, 0], coords[:, 3] - coords[:, 0]], axis=2))  # 计算六倍体积。
    volumes = np.abs(dets) / 6.0  # 转换为体积。
    edge_pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]  # 定义六条边。
    edge_sum = np.zeros(len(tets), dtype=float)  # 初始化边长平方和。
    for first, second in edge_pairs:  # 遍历六条边。
        edge_sum += np.sum((coords[:, first] - coords[:, second]) ** 2, axis=1)  # 累加边长平方。
    return 12.0 * np.power(np.maximum(3.0 * volumes, 1.0e-30), 2.0 / 3.0) / np.maximum(edge_sum, 1.0e-30)  # 返回正四面体归一化质量。

def metrics(name: str, mesh: Mesh, solution: Solution, zz: ZZ, geometry: Geometry) -> Metrics:  # 汇总一个方案的核心指标。
    quality = tetra_quality(mesh.nodes, mesh.tets)  # 计算全部四面体质量。
    vm = von_mises(solution.stress)  # 计算单元等效应力。
    centroids = np.mean(mesh.nodes[mesh.tets], axis=1)  # 计算单元重心。
    root_mask = centroids[:, 0] < geometry.length * geometry.root_fraction + 1.0e-12  # 识别固定端区。
    return Metrics(name, mesh.requested_action, len(mesh.nodes), len(mesh.tets), 3 * len(mesh.nodes), zz.relative_error, solution.tip_displacement_z, solution.compliance, float(np.quantile(vm[root_mask], 0.95)), float(np.max(vm)), float(np.min(quality)), float(np.mean(quality)), solution.seconds)  # 返回统一指标。

def solve_case(name: str, action: Action, geometry: Geometry, material: Material, load: Load) -> tuple[Mesh, Solution, ZZ, Metrics]:  # 编译、求解、恢复并汇总一个方案。
    mesh = compile_mesh(geometry, action)  # 编译真实四面体网格。
    solution = solve(mesh, geometry, material, load)  # 执行完整三维有限元求解。
    zz = recover_zz(mesh, solution, material)  # 执行ZZ恢复与误差估计。
    return mesh, solution, zz, metrics(name, mesh, solution, zz, geometry)  # 返回完整方案结果。

def sampled_surface(mesh: Mesh, maximum_faces: int = 12000) -> tuple[np.ndarray, np.ndarray]:  # 提取并按需抽样外表面。
    faces, owners = boundary_faces(mesh.tets)  # 提取完整外表面。
    if len(faces) <= maximum_faces:  # 检查是否无需抽样。
        return faces, owners  # 返回完整表面。
    indices = np.linspace(0, len(faces) - 1, maximum_faces, dtype=int)  # 均匀抽样表面三角形。
    return faces[indices], owners[indices]  # 返回抽样表面。

def plot_surface(path: Path, mesh: Mesh, geometry: Geometry, title: str, solution: Solution | None = None) -> None:  # 绘制外表面网格或应力云图。
    faces, owners = sampled_surface(mesh)  # 提取外表面。
    figure = plt.figure(figsize=(12, 5))  # 创建宽幅三维画布。
    axis = figure.add_subplot(111, projection="3d")  # 创建三维坐标轴。
    if solution is None:  # 检查是否绘制纯网格。
        collection = Poly3DCollection(mesh.nodes[faces], facecolors=(0.94, 0.94, 0.94, 1.0), edgecolors=(0.05, 0.05, 0.05, 0.35), linewidths=0.08)  # 创建网格表面集合。
    else:  # 绘制应力云图。
        values = von_mises(solution.stress)[owners] / 1.0e6  # 取得表面单元应力并转换为兆帕。
        normalization = plt.Normalize(vmin=float(np.min(values)), vmax=float(np.max(values)))  # 创建颜色归一化。
        collection = Poly3DCollection(mesh.nodes[faces], linewidths=0.03)  # 创建表面集合。
        collection.set_facecolor(cm.inferno(normalization(values)))  # 按应力设置表面颜色。
        collection.set_edgecolor((0.05, 0.05, 0.05, 0.08))  # 弱化网格边线。
        scalar = cm.ScalarMappable(norm=normalization, cmap=cm.inferno)  # 创建颜色条映射器。
        scalar.set_array(values)  # 绑定颜色条数据。
        figure.colorbar(scalar, ax=axis, shrink=0.68, pad=0.10, label="von Mises [MPa]")  # 添加应力颜色条。
    axis.add_collection3d(collection)  # 将表面加入坐标轴。
    axis.set_xlim(0.0, geometry.length)  # 设置x轴范围。
    axis.set_ylim(-0.5 * geometry.flange_width, 0.5 * geometry.flange_width)  # 设置y轴范围。
    axis.set_zlim(0.0, geometry.total_height)  # 设置z轴范围。
    axis.set_box_aspect((geometry.length, geometry.flange_width, geometry.total_height))  # 使用真实几何比例。
    axis.set_proj_type("ortho")  # 使用正交投影。
    axis.view_init(elev=22, azim=-58)  # 设置等轴视角。
    axis.set_xticks([0.0, 0.5 * geometry.length, geometry.length])  # 仅保留三个x刻度。
    axis.set_yticks([-0.5 * geometry.flange_width, 0.0, 0.5 * geometry.flange_width])  # 仅保留三个y刻度。
    axis.set_zticks([0.0, 0.5 * geometry.total_height, geometry.total_height])  # 仅保留三个z刻度。
    axis.set_xlabel("x [m]")  # 标注x轴。
    axis.set_ylabel("y [m]")  # 标注y轴。
    axis.set_zlabel("z [m]")  # 标注z轴。
    axis.set_title(title)  # 写入标题。
    figure.savefig(path, dpi=180, bbox_inches="tight")  # 保存PNG图。
    plt.close(figure)  # 关闭画布释放内存。
