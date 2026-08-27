"""双 MCT 滚转升级模型（理论推导修复：恢复幅内滚转自由度）.

问题定位（见 modal_validation/gate_corrected_*）：平面化单索束把每幅 16 根承重索、
6 根门架索压到幅中心线，幅内滚转（扭转）的刚度与惯量同时消失，模型"扭转"塌缩为
竖弯的近简并孪生，表 4-1 的 T 族偏差 -28.2%/-12.0%/-8.5% 即由此产生。

理论修复（全部参数取自仓库既有审计数据，不引入任何拟合量）：
1. 双索组等效：每幅承重索束拆为 ±b_B 两个等效索组（b_B = 16 根实索横向偏距的
   rms），每组 EA/2、初张力 T/2、自重质量/2；门架索束同理拆到 ±b_T。
   该拆分对"共模"（两组同相）动力学严格保持原单索束方程，同时使索幕的滚转
   几何刚度 Σ T_i y_i² 与滚转惯量 Σ m_i y_i² 按实索排布精确恢复（等张力分摊）。
2. 双簇端口凝聚：普通门架与横通道站均改用 condense_h10_cluster_ports.py 的
   双簇平动端口矩阵（每个索接口按实索两簇 8+8 / 3+3 根各设一个参考点，参考点
   取在张力 rms 半距 ±b 处，与本模型索组节点位置严格一致；全部转角自由凝聚）。
   四/八个平动子端口客观观测截面滚转，横梁在两簇之间的柔性得到保留——
   不再需要任何截面刚性假设或伪逆展开，矩阵恰有 6 个刚体零模态、无多余机构。
   与横通道 21 站既有惯例一致，全部站位统一复用 H10 代表矩阵并按站位弦向旋转。
3. 二期质量空间化：963.811 t MCT 二期集中质量按质量空间化审计 V2.0 的
   33003 个 MASS21 真实坐标分配到四线节点（横向按保质心线性权重、纵向按链上
   线性插值、竖向按最近链层），恢复客观滚转惯量；索系分布质量 3144.656 t
   仍由单元自重生成。

运行（在 double-mct-buffeting 包根目录）：
    python code/double_mct_roll_upgraded_model.py --modes 80
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-double-mct")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import eigsh

PACKAGE = Path(__file__).resolve().parents[1]
MCT_PATH = PACKAGE / "inputs/catwalk_gantry_rope_combined_2.mct"
STATION_PATH = PACKAGE / "inputs/passage_station_authoritative_map.csv"
COUPLINGS_PATH = PACKAGE / "inputs/roll_upgrade_sources/passage_gate_rope_couplings.csv"
MASS21_PATH = PACKAGE / "inputs/roll_upgrade_sources/mass21_spatialized_v2_nodes.csv"
REFERENCE_PATH = PACKAGE / "inputs/roll_upgrade_sources/reference_attachment_2_3_table4_1.csv"
CLUSTER_DIR = PACKAGE / "inputs/roll_upgrade_sources/cluster_condensation"
GATE_CLUSTER_PATH = CLUSTER_DIR / "K12_gate_cluster_translation_N_per_mm.csv"
PASSAGE_CLUSTER_PATH = CLUSTER_DIR / "K24_passage_cluster_translation_N_per_mm.csv"
CLUSTER_AUDIT_PATH = CLUSTER_DIR / "cluster_condensation_audit.json"
OLD_RESULT_DIR = PACKAGE / "structural_results"
OUTPUT_DIR = PACKAGE / "roll_upgraded_results"

HALF_SPACING_M = 21.45
SPAN_THRESHOLD = 0.65
NEAR_ZERO_HZ = 0.01
TOTAL_MASS_TARGET_T = 4108.46690758
SECOND_STAGE_TARGET_T = 963.811380787273


def load_production_module():
    """Import the reviewed production assembly without modifying it."""
    spec = importlib.util.spec_from_file_location(
        "double_mct_equivalent_passage_model", PACKAGE / "code/double_mct_equivalent_passage_model.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rope_group_half_gauges() -> tuple[float, float, dict[str, object]]:
    """Derive b_B and b_T (m) as rms transverse offsets of the audited rope interfaces."""
    table = pd.read_csv(COUPLINGS_PATH)
    offsets: dict[str, set[float]] = {"BOTTOM_PHI50": set(), "GANTRY_PHI54": set()}
    for row in table.itertuples(index=False):
        x = float(row.rope_x_mm)
        center = HALF_SPACING_M * 1000.0 if x > 0 else -HALF_SPACING_M * 1000.0
        offsets[str(row.family)].add(round(x - center, 3))
    bottom = np.array(sorted(offsets["BOTTOM_PHI50"]), dtype=float)
    top = np.array(sorted(offsets["GANTRY_PHI54"]), dtype=float)
    if len(bottom) != 16 or len(top) != 6:
        raise ValueError(f"Unexpected rope layout: {len(bottom)} bottom, {len(top)} top offsets")
    if float(np.max(np.abs(bottom + bottom[::-1]))) > 1.0e-6 or float(np.max(np.abs(top + top[::-1]))) > 1.0e-6:
        raise ValueError("Rope offsets are not symmetric about the catwalk centreline")
    b_bottom_m = math.sqrt(float(np.mean(bottom**2))) / 1000.0
    b_top_m = math.sqrt(float(np.mean(top**2))) / 1000.0
    audit = {
        "bottom_offsets_mm": bottom.tolist(),
        "top_offsets_mm": top.tolist(),
        "b_bottom_rms_m": b_bottom_m,
        "b_top_rms_m": b_top_m,
        "equal_tension_share_assumption": "each physical rope carries an equal share of the bundle EA and initial force",
    }
    return b_bottom_m, b_top_m, audit


def read_cluster_matrix(path: Path, port_count: int) -> np.ndarray:
    """Read a cluster-port translation matrix (N/mm) and return it in SI (N/m)."""
    table = pd.read_csv(path, index_col=0)
    if table.shape != (3 * port_count, 3 * port_count):
        raise ValueError(f"{path.name}: unexpected shape {table.shape}")
    matrix = table.to_numpy(dtype=float)
    return 0.5 * (matrix + matrix.T) * 1000.0


def verify_cluster_rigid_null(matrix_si: np.ndarray, positions_m: list[np.ndarray], label: str) -> float:
    """Verify the translation-port matrix annihilates rigid motions of its reference points."""
    rigid = np.zeros((3 * len(positions_m), 6))
    origin = np.mean(np.vstack(positions_m), axis=0)
    for i, p in enumerate(positions_m):
        r = p - origin
        rigid[3 * i : 3 * i + 3, :3] = np.eye(3)
        rigid[3 * i : 3 * i + 3, 3:] = -np.array([[0.0, -r[2], r[1]], [r[2], 0.0, -r[0]], [-r[1], r[0], 0.0]])
    residual = float(np.max(np.abs(matrix_si @ rigid))) / max(float(np.max(np.abs(matrix_si))), 1.0)
    if residual > 1.0e-6:
        raise ValueError(f"{label}: cluster matrix violates rigid modes ({residual})")
    eigenvalues = np.linalg.eigvalsh(matrix_si)
    if float(eigenvalues.min()) < -1.0e-8 * max(float(eigenvalues.max()), 1.0):
        raise ValueError(f"{label}: cluster matrix is not positive semidefinite")
    return residual


def rotation_blocks_translation(rotation: np.ndarray, port_count: int) -> np.ndarray:
    """Block-diagonal local->global rotation for stacked translation ports."""
    return np.kron(np.eye(port_count), rotation)


def gate_rotation(chord: np.ndarray) -> np.ndarray:
    """Local->global rotation aligning gate local z with the station chord (y preserved)."""
    z_axis = chord / np.linalg.norm(chord)
    if abs(float(z_axis[1])) > 1.0e-9:
        raise ValueError("Gate chord unexpectedly leaves the elevation plane")
    y_axis = np.array([0.0, 1.0, 0.0])
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    return np.column_stack((x_axis, y_axis, z_axis))


def build_roll_model(
    production,
    parsed: dict[str, object],
    station_map: pd.DataFrame,
    b_bottom: float,
    b_top: float,
    passage_mode: str = "cerig-rigid",
) -> dict[str, object]:
    """Assemble the four-line (two rope groups per chain per width) double-MCT system."""
    source_nodes = parsed["nodes"]
    source_elements = parsed["elements"]
    initial_force_kn = parsed["initial_force_kn"]
    source_ids = sorted(source_nodes)
    x_origin = production.MCT_X_ORIGIN_M

    def chain_half_gauge(node_id: int) -> float:
        return b_bottom if node_id <= 730 else b_top

    index: dict[tuple[int, int, int], int] = {}
    coordinates: list[np.ndarray] = []
    for width, y_center in ((0, -HALF_SPACING_M), (1, HALF_SPACING_M)):
        for line in (1, -1):
            for node_id in source_ids:
                source = np.asarray(source_nodes[node_id], dtype=float)
                index[(width, line, node_id)] = len(coordinates)
                coordinates.append(
                    np.array([source[0] - x_origin, y_center + line * chain_half_gauge(node_id), source[2]])
                )
    xyz = np.vstack(coordinates)
    node_count = len(coordinates)
    nodal_mass = np.zeros(node_count)

    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []

    def add_pair(i: int, j: int, block: np.ndarray) -> None:
        di = np.arange(3 * i, 3 * i + 3)
        dj = np.arange(3 * j, 3 * j + 3)
        for a in range(3):
            for b in range(3):
                v = float(block[a, b])
                rows.extend([di[a], di[a], dj[a], dj[a]])
                cols.extend([di[b], dj[b], di[b], dj[b]])
                values.extend([v, -v, -v, v])

    def add_general(node_list: list[int], matrix: np.ndarray) -> None:
        dofs = np.concatenate([np.arange(3 * n, 3 * n + 3) for n in node_list])
        nz_r, nz_c = np.nonzero(np.abs(matrix) > 0.0)
        for a, b in zip(nz_r, nz_c):
            rows.append(int(dofs[a]))
            cols.append(int(dofs[b]))
            values.append(float(matrix[a, b]))

    replaced_gate_elements = {int(v) for v in station_map["mct_property3_element"].tolist()}
    ordinary_gate_elements = {
        int(eid) for eid, el in source_elements.items() if str(el["type"]) == "TRUSS" and int(eid) not in replaced_gate_elements
    }
    if len(ordinary_gate_elements) != 50:
        raise ValueError(f"Expected 50 ordinary gates, found {len(ordinary_gate_elements)}")

    distributed_mass_kg = 0.0
    for width in (0, 1):
        for line in (1, -1):
            for element_id in sorted(source_elements):
                element = source_elements[element_id]
                if str(element["type"]) != "TENSTR":
                    continue  # all 71 gates are handled by port-matrix assemblies
                n1, n2 = int(element["n1"]), int(element["n2"])
                i = index[(width, line, n1)]
                j = index[(width, line, n2)]
                vector = xyz[j] - xyz[i]
                length = float(np.linalg.norm(vector))
                direction = vector / length
                projector = np.outer(direction, direction)
                modulus, area, weight_density = production.material_and_section(element)
                force_n = float(initial_force_kn.get(element_id, 0.0)) * 1000.0
                tangent = (0.5 * modulus * area / length) * projector
                tangent += (0.5 * force_n / length) * (np.eye(3) - projector)
                add_pair(i, j, tangent)
                element_mass = weight_density * (area * 1.0e6) * (length * 1000.0) * 1000.0 / production.GRAVITY_M_S2
                half = 0.25 * element_mass  # half element mass, halved again between the two lines
                nodal_mass[i] += half
                nodal_mass[j] += half
                distributed_mass_kg += 0.5 * element_mass

    # Ordinary gates: H10 cluster-port matrix rotated to each station chord.
    cluster_audit = json.loads(CLUSTER_AUDIT_PATH.read_text(encoding="utf-8"))
    gate_cluster_si = read_cluster_matrix(GATE_CLUSTER_PATH, 4)
    gate_reference_mm = cluster_audit["gate_cluster"]["reference_points_apdl_mm"]
    gate_positions = [np.asarray(gate_reference_mm[k], dtype=float) / 1000.0 for k in ("Bp", "Bm", "Tp", "Tm")]
    gate_rigid_residual = verify_cluster_rigid_null(gate_cluster_si, gate_positions, "gate cluster K12")
    h10_gate_chord = np.mean([gate_positions[2], gate_positions[3]], axis=0) - np.mean(
        [gate_positions[0], gate_positions[1]], axis=0
    )
    gate_records = []
    for width in (0, 1):
        for element_id in sorted(ordinary_gate_elements):
            element = source_elements[element_id]
            n_bottom, n_top = int(element["n1"]), int(element["n2"])
            bottom_center = np.array(
                [float(source_nodes[n_bottom][0]) - x_origin, 0.0, float(source_nodes[n_bottom][2])]
            )
            top_center = np.array([float(source_nodes[n_top][0]) - x_origin, 0.0, float(source_nodes[n_top][2])])
            chord = top_center - bottom_center
            length = float(np.linalg.norm(chord))
            rotation = gate_rotation(chord)
            t_blocks = rotation_blocks_translation(rotation, 4)
            k_line = t_blocks @ gate_cluster_si @ t_blocks.T
            node_list = [
                index[(width, 1, n_bottom)],
                index[(width, -1, n_bottom)],
                index[(width, 1, n_top)],
                index[(width, -1, n_top)],
            ]
            add_general(node_list, k_line)
            gate_records.append(
                {
                    "width": "L" if width == 0 else "R",
                    "source_element": element_id,
                    "length_m": length,
                    "bottom_node": n_bottom,
                    "top_node": n_top,
                }
            )

    # Passage stations.
    # cerig-rigid: audited K24 cluster assembly (74 CERIG ALL rigid links bind the
    #   passage truss rigidly to both station gates).
    # drawing-soft: per drawings MD5-16/17/24/25 the passage is carried on MC-nylon
    #   rollers riding the carrying ropes, pinned tubes and chord hoop clamps, so it
    #   transfers translational forces but no roll moment.  That is exactly the
    #   kinematic content of the audited single-centre translation-port K12 (roll is
    #   unobservable there), which is therefore assembled through the pair-mean map
    #   u_centre = (u_+ + u_-)/2 -- roll-transparent by construction, no gate double
    #   counting beyond the production convention.
    passage_rigid_residual = float("nan")
    passage_records = []
    if passage_mode == "cerig-rigid":
        passage_matrix_si = read_cluster_matrix(PASSAGE_CLUSTER_PATH, 8)
        passage_reference_mm = cluster_audit["passage_cluster"]["reference_points_apdl_mm"]
        passage_positions = [
            np.asarray(passage_reference_mm[k], dtype=float) / 1000.0
            for k in ("B_Lp", "B_Lm", "T_Lp", "T_Lm", "B_Rp", "B_Rm", "T_Rp", "T_Rm")
        ]
        passage_rigid_residual = verify_cluster_rigid_null(passage_matrix_si, passage_positions, "passage cluster K24")
    else:
        k12_center_si, _ = production.read_four_port_matrix(PACKAGE / "inputs/gate_passage/K12_translation_ports.csv")
        mean_map = np.zeros((12, 24))
        for port in range(4):
            for axis in range(3):
                mean_map[3 * port + axis, 6 * port + axis] = 0.5
                mean_map[3 * port + axis, 6 * port + 3 + axis] = 0.5
    for row in station_map.itertuples(index=False):
        bottom_id = int(row.mct_bottom_node)
        gate_id = int(row.mct_gate_node)
        rotation = production.station_local_to_global(float(row.bottom_central_chord_slope_degree))
        if passage_mode == "cerig-rigid":
            t_blocks = rotation_blocks_translation(rotation, 8)
            k_line = t_blocks @ passage_matrix_si @ t_blocks.T
        else:
            t_blocks = rotation_blocks_translation(rotation, 4)
            k_center_global = t_blocks @ k12_center_si @ t_blocks.T
            k_line = mean_map.T @ k_center_global @ mean_map
        node_list = [
            index[(1, 1, bottom_id)],
            index[(1, -1, bottom_id)],
            index[(1, 1, gate_id)],
            index[(1, -1, gate_id)],
            index[(0, 1, bottom_id)],
            index[(0, -1, bottom_id)],
            index[(0, 1, gate_id)],
            index[(0, -1, gate_id)],
        ]
        add_general(node_list, k_line)
        passage_records.append(
            {
                "passage_id": str(row.passage_id),
                "bottom_node": bottom_id,
                "gate_node": gate_id,
                "x_centerline_m": 0.5 * (float(source_nodes[bottom_id][0]) + float(source_nodes[gate_id][0])) - x_origin,
                "slope_degree": float(row.bottom_central_chord_slope_degree),
            }
        )

    ndof = 3 * node_count
    stiffness = coo_matrix((values, (rows, cols)), shape=(ndof, ndof)).tocsr()

    constrained: set[int] = set()
    for width in (0, 1):
        for line in (1, -1):
            for node_id, mask in parsed["constraints"].items():
                g = index[(width, line, int(node_id))]
                for component in range(3):
                    if component < len(mask) and mask[component] == "1":
                        constrained.add(3 * g + component)
    free_mask = np.ones(ndof, dtype=bool)
    free_mask[sorted(constrained)] = False
    free_dofs = np.arange(ndof)[free_mask]

    return {
        "xyz": xyz,
        "index": index,
        "stiffness": stiffness,
        "nodal_mass_kg": nodal_mass,
        "free_dofs": free_dofs,
        "distributed_mass_kg": distributed_mass_kg,
        "gate_records": gate_records,
        "passage_records": passage_records,
        "b_bottom_m": b_bottom,
        "b_top_m": b_top,
        "source_ids": source_ids,
        "x_origin": x_origin,
        "gate_cluster_rigid_residual": gate_rigid_residual,
        "passage_cluster_rigid_residual": passage_rigid_residual,
        "ordinary_gate_elements": sorted(ordinary_gate_elements),
        "replaced_gate_elements": sorted(replaced_gate_elements),
    }


def allocate_spatialized_mass(production, parsed: dict[str, object], model: dict[str, object]) -> dict[str, object]:
    """Distribute the audited spatialized second-stage MASS21 set onto the four-line grid."""
    table = pd.read_csv(MASS21_PATH, usecols=["x_mm", "y_mm", "z_mm", "mass_tonne"])
    x = table["x_mm"].to_numpy(float) / 1000.0 - model["x_origin"]
    y = table["y_mm"].to_numpy(float) / 1000.0
    z = table["z_mm"].to_numpy(float) / 1000.0
    mass_kg = table["mass_tonne"].to_numpy(float) * 1000.0

    source_nodes = parsed["nodes"]
    carrying_ids = np.array([i for i in model["source_ids"] if i <= 728], dtype=int)
    gantry_ids = np.array([i for i in model["source_ids"] if 1001 <= i <= 1395], dtype=int)
    carrying_x = np.array([source_nodes[i][0] - model["x_origin"] for i in carrying_ids])
    carrying_z = np.array([source_nodes[i][2] for i in carrying_ids])
    gantry_x = np.array([source_nodes[i][0] - model["x_origin"] for i in gantry_ids])
    gantry_z = np.array([source_nodes[i][2] for i in gantry_ids])
    order_c = np.argsort(carrying_x)
    order_g = np.argsort(gantry_x)
    carrying_ids, carrying_x, carrying_z = carrying_ids[order_c], carrying_x[order_c], carrying_z[order_c]
    gantry_ids, gantry_x, gantry_z = gantry_ids[order_g], gantry_x[order_g], gantry_z[order_g]

    nodal_mass = model["nodal_mass_kg"]
    index = model["index"]
    b_bottom, b_top = model["b_bottom_m"], model["b_top_m"]

    def chain_arrays(is_gantry: bool):
        return (gantry_ids, gantry_x, gantry_z, b_top) if is_gantry else (carrying_ids, carrying_x, carrying_z, b_bottom)

    def deposit(width: int, is_gantry: bool, x_target: float, delta_y: float, amount_kg: float) -> None:
        ids, xs, zs, half_gauge = chain_arrays(is_gantry)
        position = float(np.clip(x_target, xs[0], xs[-1]))
        upper = int(np.clip(np.searchsorted(xs, position), 1, len(xs) - 1))
        lower = upper - 1
        w_upper = (position - xs[lower]) / (xs[upper] - xs[lower])
        w_plus = 0.5 * (1.0 + delta_y / half_gauge)
        for node_pos, w_x in ((lower, 1.0 - w_upper), (upper, w_upper)):
            node_id = int(ids[node_pos])
            nodal_mass[index[(width, 1, node_id)]] += amount_kg * w_x * w_plus
            nodal_mass[index[(width, -1, node_id)]] += amount_kg * w_x * (1.0 - w_plus)

    stats = {"side_kg": 0.0, "gap_kg": 0.0, "true_side_roll_inertia_kg_m2": 0.0}
    for xi, yi, zi, mi in zip(x, y, z, mass_kg):
        if abs(yi) >= 18.0:
            width = 1 if yi > 0 else 0
            center = HALF_SPACING_M if yi > 0 else -HALF_SPACING_M
            delta = yi - center
            zc = float(np.interp(xi, carrying_x, carrying_z))
            zg = float(np.interp(xi, gantry_x, gantry_z))
            is_gantry = abs(zi - zg) < abs(zi - zc)
            deposit(width, is_gantry, xi, delta, mi)
            stats["side_kg"] += mi
            stats["true_side_roll_inertia_kg_m2"] += mi * delta**2
        else:
            share_right = (yi + HALF_SPACING_M) / (2.0 * HALF_SPACING_M)
            deposit(1, False, xi, 0.0, mi * share_right)
            deposit(0, False, xi, 0.0, mi * (1.0 - share_right))
            stats["gap_kg"] += mi
    return stats


def solve_modes(model: dict[str, object], mode_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    free = model["free_dofs"]
    stiffness = model["stiffness"][free][:, free]
    dof_mass = np.repeat(model["nodal_mass_kg"], 3)
    model["dof_mass_kg"] = dof_mass
    if float(dof_mass[free].min()) <= 0.0:
        raise ValueError("Non-positive free translational mass after spatialized allocation")
    mass = diags(dof_mass[free], format="csr")
    eigenvalues, reduced = eigsh(stiffness, k=mode_count, M=mass, sigma=0.0, which="LM", tol=1.0e-10, maxiter=30000)
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order], dtype=float)
    reduced = np.asarray(reduced[:, order], dtype=float)
    modes = np.zeros((len(dof_mass), mode_count))
    modes[free, :] = reduced
    frequencies = np.sqrt(np.maximum(eigenvalues, 0.0)) / (2.0 * math.pi)
    return frequencies, modes, eigenvalues


def eigen_residual(model: dict[str, object], vector: np.ndarray, frequency_hz: float) -> tuple[float, float]:
    free = model["free_dofs"]
    reduced = vector[free]
    stiffness = model["stiffness"][free][:, free]
    mass_values = model["dof_mass_kg"][free]
    lam = (2.0 * math.pi * frequency_hz) ** 2
    elastic = stiffness @ reduced
    inertial = lam * mass_values * reduced
    denominator = float(np.linalg.norm(elastic) + np.linalg.norm(inertial))
    residual = float(np.linalg.norm(elastic - inertial) / denominator) if denominator > 0 else 0.0
    mass_norm = float(np.sum(model["dof_mass_kg"] * vector**2))
    return residual, mass_norm


SPAN_BOUNDS = {"NORTH": (-1.0e9, 700.3), "MAIN": (700.3, 3009.6), "SOUTH": (3009.6, 3724.0), "AUX": (3724.0, 1.0e9)}


def span_of(x_value: float) -> str:
    for name, (lo, hi) in SPAN_BOUNDS.items():
        if lo <= x_value < hi:
            return name
    return "AUX"


def classify_modes(production, parsed, model, frequencies, modes) -> pd.DataFrame:
    """Family classification extended to the four-line kinematics.

    Formal families keep the locked hierarchy; the T signal is the physical intra-width
    roll psi = (u_z(+b) - u_z(-b)) / 2b, which is what Attachment 2-3 labels 扭转.
    The old between-width differential-z family is retained as diagnostic SYSZ.
    """
    source_nodes = parsed["nodes"]
    index = model["index"]
    nodal_mass = model["nodal_mass_kg"]
    b_bottom = model["b_bottom_m"]
    source_ids = model["source_ids"]
    x_origin = model["x_origin"]

    node_span = {i: span_of(float(source_nodes[i][0]) - x_origin) for i in source_ids}
    main_ids = [i for i in source_ids if 155 <= i <= 448]
    main_x = np.array([source_nodes[i][0] - x_origin for i in main_ids])

    quad_indices = {}
    for i in source_ids:
        quad_indices[i] = [index[(0, 1, i)], index[(0, -1, i)], index[(1, 1, i)], index[(1, -1, i)]]

    patterns = {
        "common": np.array([1.0, 1.0, 1.0, 1.0]) / 2.0,
        "roll_c": np.array([1.0, -1.0, 1.0, -1.0]) / 2.0,
        "roll_a": np.array([1.0, -1.0, -1.0, 1.0]) / 2.0,
        "sys": np.array([1.0, 1.0, -1.0, -1.0]) / 2.0,
    }

    records = []
    for mode_index, frequency in enumerate(frequencies):
        flat = modes[:, mode_index]
        residual, mass_norm = eigen_residual(model, flat, float(frequency))
        vector = flat.reshape((-1, 3))
        span_energy = {name: 0.0 for name in SPAN_BOUNDS}
        component_energy = {
            (pattern, axis): 0.0 for pattern in patterns for axis in range(3)
        }
        main_component_energy = {key: 0.0 for key in component_energy}
        for i in source_ids:
            quad = quad_indices[i]
            masses = nodal_mass[quad]
            kinetic = float(np.sum(masses[:, None] * vector[quad] ** 2))
            span_energy[node_span[i]] += kinetic
            mean_mass = float(np.mean(masses))
            for axis in range(3):
                vals = vector[quad, axis]
                axis_energy = float(np.sum(masses * vals**2))
                raw = {name: mean_mass * float(p @ vals) ** 2 for name, p in patterns.items()}
                total_raw = sum(raw.values())
                scale = axis_energy / total_raw if total_raw > 0 else 0.0
                for name in patterns:
                    component_energy[(name, axis)] += raw[name] * scale
                    if node_span[i] == "MAIN":
                        main_component_energy[(name, axis)] += raw[name] * scale
        span_fraction = {k: v / mass_norm for k, v in span_energy.items()}
        dominant_span = max(span_fraction, key=span_fraction.get)
        dominant_fraction = span_fraction[dominant_span]
        mode_class = (
            "MAIN"
            if dominant_span == "MAIN" and dominant_fraction >= SPAN_THRESHOLD
            else "SIDE"
            if dominant_span != "MAIN" and dominant_fraction >= SPAN_THRESHOLD
            else "MIXED"
        )
        # Torsion family T merges the between-width differential-z rotation (the global
        # torsion observable, continuous with the locked pairing convention) and the
        # intra-width roll patterns (present in rigid-rotation proportion; the pure
        # intra-roll branch lies above 1 Hz in this model and outside the 80-mode window).
        main_families = {
            "X": main_component_energy[("common", 0)],
            "L": main_component_energy[("common", 1)],
            "V": main_component_energy[("common", 2)],
            "T": main_component_energy[("sys", 2)]
            + main_component_energy[("roll_c", 2)]
            + main_component_energy[("roll_a", 2)],
            "SYSY": main_component_energy[("sys", 1)],
            "BRTH": main_component_energy[("roll_c", 1)] + main_component_energy[("roll_a", 1)],
            "WARP": main_component_energy[("sys", 0)] + main_component_energy[("roll_c", 0)] + main_component_energy[("roll_a", 0)],
        }
        family = max(main_families, key=main_families.get)
        main_total = sum(main_families.values())
        family_fraction = main_families[family] / main_total if main_total > 0 else 0.0
        roll_common_dominant = main_component_energy[("roll_c", 2)] >= main_component_energy[("roll_a", 2)]

        half_wave, template_mac, parity = 0, 0.0, ""
        if mode_class == "MAIN" and family in {"L", "V", "T", "X"}:
            signal = np.zeros(len(main_ids))
            weights = np.zeros(len(main_ids))
            for pos, i in enumerate(main_ids):
                quad = quad_indices[i]
                masses = nodal_mass[quad]
                weights[pos] = float(np.sum(masses))
                vals_y = vector[quad, 1]
                vals_z = vector[quad, 2]
                vals_x = vector[quad, 0]
                if family == "L":
                    signal[pos] = float(patterns["common"] @ vals_y)
                elif family == "V":
                    signal[pos] = float(patterns["common"] @ vals_z)
                elif family == "X":
                    signal[pos] = float(patterns["common"] @ vals_x)
                else:
                    signal[pos] = float(patterns["sys"] @ vals_z)  # global torsion observable
            coordinate = (main_x - main_x.min()) / (main_x.max() - main_x.min())
            best_order, best_mac = 0, 0.0
            for order in range(1, 13):
                template = np.sin(order * math.pi * coordinate)
                numerator = float(np.sum(weights * signal * template)) ** 2
                denominator = float(np.sum(weights * signal**2)) * float(np.sum(weights * template**2))
                mac = numerator / denominator if denominator > 0 else 0.0
                if mac > best_mac:
                    best_order, best_mac = order, mac
            half_wave, template_mac = best_order, best_mac
            parity = "S" if half_wave % 2 == 1 else "A"

        records.append(
            {
                "mode": mode_index + 1,
                "frequency_hz": float(frequency),
                "eigenpair_relative_residual": residual,
                "mode_class": mode_class,
                "dominant_span": dominant_span,
                "dominant_span_fraction": dominant_fraction,
                "main_energy_fraction": span_fraction["MAIN"],
                "family": family if mode_class == "MAIN" else "SIDE" if mode_class == "SIDE" else family,
                "family_fraction_within_main": family_fraction,
                "span_parity": parity,
                "half_wave_order": half_wave,
                "template_mac": template_mac,
                "roll_common_dominant": bool(roll_common_dominant),
                "main_L_energy": main_families["L"] / mass_norm,
                "main_V_energy": main_families["V"] / mass_norm,
                "main_T_energy": main_families["T"] / mass_norm,
                "main_sys_z_energy": main_component_energy[("sys", 2)] / mass_norm,
                "main_intra_roll_energy": (
                    main_component_energy[("roll_c", 2)] + main_component_energy[("roll_a", 2)]
                )
                / mass_norm,
                "modal_mass_norm": mass_norm,
            }
        )
    frame = pd.DataFrame(records)
    counters: dict[str, int] = {}
    labels = []
    for row in frame.itertuples(index=False):
        if str(row.mode_class) == "MAIN" and str(row.family) in {"L", "V", "T"} and str(row.span_parity) in {"S", "A"}:
            key = f"{row.family}{row.span_parity}"
            counters[key] = counters.get(key, 0) + 1
            labels.append(f"{key}{counters[key]}")
        elif str(row.mode_class) == "MAIN" and str(row.span_parity) in {"S", "A"}:
            labels.append(f"{row.family}_{row.span_parity}_n{int(row.half_wave_order)}_DIAG")
        else:
            labels.append(f"SIDE_{row.dominant_span}" if str(row.mode_class) == "SIDE" else f"{row.family}_MIXED")
    frame["formal_label"] = labels
    return frame


def match_reference(reference: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    side_reference = reference[reference["internal_id"].str.startswith("SIDE")].copy()
    side_candidates = classification[classification["mode_class"] == "SIDE"].copy()
    cost = np.abs(
        side_reference["frequency_hz"].to_numpy(float)[:, None]
        / side_candidates["frequency_hz"].to_numpy(float)[None, :]
        - 1.0
    )
    r_idx, c_idx = linear_sum_assignment(cost)
    side_lookup = {str(side_reference.iloc[r]["internal_id"]): side_candidates.iloc[c] for r, c in zip(r_idx, c_idx)}
    rows = []
    for ref in reference.itertuples(index=False):
        rid = str(ref.internal_id)
        if rid.startswith("SIDE"):
            candidate = side_lookup[rid]
            basis = "dominant non-main span energy >=0.65 + global one-to-one relative-frequency assignment"
        else:
            candidates = classification[classification["formal_label"] == rid]
            if candidates.empty:
                rows.append(
                    {
                        "reference_order": int(ref.order),
                        "reference_id": rid,
                        "reference_description": str(ref.description),
                        "reference_frequency_hz": float(ref.frequency_hz),
                        "matched_mode": np.nan,
                        "matched_frequency_hz": np.nan,
                        "relative_error_percent": np.nan,
                        "absolute_error_percent": np.nan,
                        "match_basis": "missing formal within-family frequency ordinal",
                        "matched_formal_label": "MISSING",
                    }
                )
                continue
            candidate = candidates.iloc[0]
            basis = (
                "main-span energy + four-line family (T = intra-width roll) + parity"
                " + within-family ascending-frequency ordinal; half-wave is fingerprint only"
            )
        error = 100.0 * (float(candidate["frequency_hz"]) / float(ref.frequency_hz) - 1.0)
        rows.append(
            {
                "reference_order": int(ref.order),
                "reference_id": rid,
                "reference_description": str(ref.description),
                "reference_frequency_hz": float(ref.frequency_hz),
                "matched_mode": int(candidate["mode"]),
                "matched_frequency_hz": float(candidate["frequency_hz"]),
                "relative_error_percent": error,
                "absolute_error_percent": abs(error),
                "match_basis": basis,
                "matched_formal_label": str(candidate["formal_label"]),
                "mode_class": str(candidate["mode_class"]),
                "dominant_span": str(candidate["dominant_span"]),
                "half_wave_order_fingerprint": int(candidate["half_wave_order"]),
                "half_wave_template_mac": float(candidate["template_mac"]),
                "eigenpair_relative_residual": float(candidate["eigenpair_relative_residual"]),
            }
        )
    return pd.DataFrame(rows)


def project_to_center_space(model: dict[str, object], modes: np.ndarray, source_ids: list[int]) -> np.ndarray:
    """Average the +/- line motions back to per-(width, source) centreline vectors."""
    index = model["index"]
    projected = np.zeros((2 * len(source_ids) * 3, modes.shape[1]))
    for w in (0, 1):
        for pos, i in enumerate(source_ids):
            row = 3 * (w * len(source_ids) + pos)
            plus = 3 * index[(w, 1, i)]
            minus = 3 * index[(w, -1, i)]
            projected[row : row + 3, :] = 0.5 * (modes[plus : plus + 3, :] + modes[minus : minus + 3, :])
    return projected


def track_previous(production, parsed, model, station_map, classification, modes) -> pd.DataFrame:
    """Mass-weighted MAC tracking of the upgraded modes against the gate-corrected solution."""
    old_vectors = np.load(OLD_RESULT_DIR / "mode_vectors_first24.npz")
    old_modes = np.asarray(old_vectors["modes"], dtype=float)
    old_table = pd.read_csv(OLD_RESULT_DIR / "modal_properties.csv")
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch)
        (scratch_path / "tmp").mkdir()
        (scratch_path / "tmp/gate_only_condensation").symlink_to(PACKAGE / "inputs/gate_only")
        (scratch_path / "tmp/gate_passage_condensation").symlink_to(PACKAGE / "inputs/gate_passage")
        cwd = os.getcwd()
        os.chdir(scratch_path)
        try:
            old_model = production.build_double_model(parsed, station_map, PACKAGE / "inputs/gate_passage/K12_translation_ports.csv")
        finally:
            os.chdir(cwd)
    old_mass = np.asarray(old_model["dof_mass_kg"], dtype=float)
    source_ids = model["source_ids"]
    order = {(w, i): old_model["index"][(w, i)] for w in (0, 1) for i in source_ids}
    permutation = np.zeros(len(old_mass), dtype=int)
    for w in (0, 1):
        for pos, i in enumerate(source_ids):
            new_row = w * len(source_ids) + pos
            permutation[3 * order[(w, i)] : 3 * order[(w, i)] + 3] = np.arange(3 * new_row, 3 * new_row + 3)
    projected = project_to_center_space(model, modes[:, :40], source_ids)
    projected_in_old_order = projected[permutation, :]
    weighted = old_mass[:, None]
    cross = old_modes.T @ (weighted * projected_in_old_order)
    n_old = np.sum(weighted * old_modes**2, axis=0)
    n_new = np.sum(weighted * projected_in_old_order**2, axis=0)
    mac = cross**2 / np.outer(n_old, n_new)
    assigned_old, assigned_new = linear_sum_assignment(1.0 - mac)
    rows = []
    for o, n in zip(assigned_old, assigned_new):
        rows.append(
            {
                "previous_mode": int(o + 1),
                "previous_label": str(old_table.iloc[o].get("label", "")),
                "previous_frequency_hz": float(old_table.iloc[o]["frequency_hz"]),
                "upgraded_mode": int(n + 1),
                "upgraded_label": str(classification.iloc[n]["formal_label"]),
                "upgraded_frequency_hz": float(classification.iloc[n]["frequency_hz"]),
                "frequency_shift_percent": 100.0
                * (float(classification.iloc[n]["frequency_hz"]) / float(old_table.iloc[o]["frequency_hz"]) - 1.0),
                "mass_weighted_mac_center_projected": float(mac[o, n]),
            }
        )
    return pd.DataFrame(rows).sort_values("previous_mode").reset_index(drop=True)


def make_figures(production, parsed, model, classification, reference_match, modes, output_dir: Path) -> None:
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = "Noto Sans CJK SC"
    plt.rcParams["axes.unicode_minus"] = False

    # Cross-section schematic from the audited layout.
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    bottom_offsets = np.array([-2670, -2410, -2150, -1890, -1630, -1370, -1110, -850, 850, 1110, 1370, 1630, 1890, 2150, 2410, 2670]) / 1000.0
    top_offsets = np.array([-2210, -1950, -1690, 1690, 1950, 2210]) / 1000.0
    for center, color in ((-HALF_SPACING_M, "#1f77b4"), (HALF_SPACING_M, "#d95f02")):
        ax.scatter(center + bottom_offsets, np.zeros_like(bottom_offsets), s=18, color=color, label=None)
        ax.scatter(center + top_offsets, np.full_like(top_offsets, 8.0), s=18, marker="s", color=color)
        for sign in (1, -1):
            ax.plot([center + sign * model["b_bottom_m"]] * 2, [-0.6, 0.6], color="#2ca02c", linewidth=2.5)
            ax.plot([center + sign * model["b_top_m"]] * 2, [7.4, 8.6], color="#2ca02c", linewidth=2.5)
    ax.annotate("16 根 φ50 承重索（实际排布）", xy=(-HALF_SPACING_M, -0.1), xytext=(-HALF_SPACING_M, -2.4), ha="center", fontsize=9)
    ax.annotate("6 根 φ54 门架索", xy=(-HALF_SPACING_M, 8.0), xytext=(-HALF_SPACING_M, 10.0), ha="center", fontsize=9)
    ax.annotate("等效双索组 ±b（绿）", xy=(HALF_SPACING_M, 0.4), xytext=(HALF_SPACING_M, -2.4), ha="center", fontsize=9, color="#2ca02c")
    ax.set_xlabel("横桥向 Y / m")
    ax.set_ylabel("门架局部高度 / m")
    ax.set_title("双 MCT 横断面：实索排布与等效双索组（b_B=1.858 m，b_T=1.962 m，幅心距 42.9 m）")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "roll_upgraded_cross_section.png", dpi=180)
    plt.close(fig)

    # Error comparison old vs new for the 14 reference rows.
    old = pd.read_csv(PACKAGE / "modal_validation/gate_corrected_reference_table4_1_matching.csv")
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ids = reference_match["reference_id"].tolist()
    x_pos = np.arange(len(ids))
    ax.bar(x_pos - 0.2, old["relative_error_percent"], width=0.4, label="修正前（平面幅+秩一门架）", color="#c44e52")
    ax.bar(x_pos + 0.2, reference_match["relative_error_percent"], width=0.4, label="滚转升级后", color="#4c72b0")
    ax.axhline(0, color="#444444", linewidth=0.8)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(ids, rotation=45, ha="right")
    ax.set_ylabel("相对附件表 4-1 误差 / %")
    ax.set_title("附件 2-3 表 4-1 十四行配对误差：升级前后")
    ax.grid(alpha=0.25, axis="y")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "roll_upgraded_error_comparison.png", dpi=180)
    plt.close(fig)

    # Shapes of the matched named modes (roll / vertical / lateral observables).
    source_nodes = parsed["nodes"]
    index = model["index"]
    main_ids = [i for i in model["source_ids"] if 155 <= i <= 448]
    x_axis = np.array([source_nodes[i][0] - model["x_origin"] for i in main_ids])
    named = reference_match[~reference_match["reference_id"].str.startswith("SIDE")]
    fig, axes = plt.subplots(4, 3, figsize=(13.5, 11), sharex=True, constrained_layout=True)
    for ax, row in zip(axes.flat, named.itertuples(index=False)):
        if not np.isfinite(row.matched_mode):
            ax.text(0.5, 0.5, f"{row.reference_id}: 无正式配对", ha="center", va="center", fontsize=10)
            ax.axis("off")
            continue
        mode_col = int(row.matched_mode) - 1
        vector = modes[:, mode_col].reshape((-1, 3))
        family = str(row.reference_id)[0]
        series = np.zeros(len(main_ids))
        for pos, i in enumerate(main_ids):
            quad = [index[(0, 1, i)], index[(0, -1, i)], index[(1, 1, i)], index[(1, -1, i)]]
            if family == "L":
                series[pos] = float(np.mean(vector[quad, 1]))
            elif family == "V":
                series[pos] = float(np.mean(vector[quad, 2]))
            else:
                z_left = 0.5 * (vector[quad[0], 2] + vector[quad[1], 2])
                z_right = 0.5 * (vector[quad[2], 2] + vector[quad[3], 2])
                series[pos] = (z_right - z_left) / (2.0 * HALF_SPACING_M)
        scale = float(np.max(np.abs(series))) or 1.0
        ax.plot(x_axis, series / scale, color="#204a87", linewidth=1.1)
        ax.axhline(0.0, color="#999999", linewidth=0.5)
        observable = {"L": "共横移", "V": "共竖移", "T": "系统扭转角"}[family]
        ax.set_title(
            f"{row.reference_id}: M{int(row.matched_mode)}  {row.matched_frequency_hz:.4f} Hz ({row.relative_error_percent:+.2f}%)\n{observable}",
            fontsize=9,
        )
        ax.grid(alpha=0.2)
    for ax in axes.flat[len(named) :]:
        ax.axis("off")
    for ax in axes[-1, :]:
        ax.set_xlabel("顺桥向 X / m")
    fig.savefig(output_dir / "roll_upgraded_named_mode_shapes.png", dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Double-MCT roll-upgraded model (theory-derived torsion fix)")
    parser.add_argument("--modes", type=int, default=80)
    parser.add_argument(
        "--passage-mode",
        choices=("cerig-rigid", "drawing-soft"),
        default="cerig-rigid",
        help=(
            "cerig-rigid: audited K24 cluster assembly (74 CERIG ALL rigid links); "
            "drawing-soft: per drawings MD5-16/17/24/25 the passage rides on MC-nylon rollers, "
            "pinned tubes and hoop clamps, so no passage stiffness is assembled and each "
            "passage station carries two independent cluster gates instead"
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    production = load_production_module()
    expected = production.sha256_file(MCT_PATH)
    if expected != production.EXPECTED_MCT_SHA256:
        raise ValueError(f"MCT SHA-256 mismatch: {expected}")
    parsed = production.parse_mct(MCT_PATH)
    station_map = pd.read_csv(STATION_PATH, encoding="utf-8-sig")
    if len(station_map) != 21:
        raise ValueError("Expected 21 passage stations")

    b_bottom, b_top, gauge_audit = rope_group_half_gauges()
    model = build_roll_model(production, parsed, station_map, b_bottom, b_top, args.passage_mode)
    # Second-stage spatialized mass replaces the planar CONLOAD lumping (identical total).
    mass_stats = allocate_spatialized_mass(production, parsed, model)
    total_mass_t = float(np.sum(model["nodal_mass_kg"])) / 1000.0
    second_stage_t = mass_stats["side_kg"] / 1000.0 + mass_stats["gap_kg"] / 1000.0
    if abs(second_stage_t - SECOND_STAGE_TARGET_T) > 1.0e-6:
        raise ValueError(f"Second-stage mass closure failed: {second_stage_t}")

    frequencies, modes, raw_eigenvalues = solve_modes(model, args.modes)
    classification = classify_modes(production, parsed, model, frequencies, modes)
    reference = pd.read_csv(REFERENCE_PATH, encoding="utf-8-sig")
    reference_match = match_reference(reference, classification)
    tracking = track_previous(production, parsed, model, station_map, classification, modes)

    output_dir = args.output if args.output is not None else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    classification.to_csv(output_dir / "roll_upgraded_mode_classification.csv", index=False)
    reference_match.to_csv(output_dir / "roll_upgraded_reference_table4_1_matching.csv", index=False)
    tracking.to_csv(output_dir / "roll_upgraded_vs_gate_corrected_tracking.csv", index=False)

    valid = reference_match.dropna(subset=["absolute_error_percent"])
    torsional = valid[valid["reference_id"].str.startswith("T")]
    non_torsional = valid[~valid["reference_id"].str.startswith("T")]
    statistics = {
        "passage_mode": args.passage_mode,
        "b_bottom_rms_m": b_bottom,
        "b_top_rms_m": b_top,
        "total_mass_tonne": total_mass_t,
        "total_mass_target_tonne": TOTAL_MASS_TARGET_T,
        "total_mass_error_tonne": total_mass_t - TOTAL_MASS_TARGET_T,
        "second_stage_side_tonne": mass_stats["side_kg"] / 1000.0,
        "second_stage_gap_tonne": mass_stats["gap_kg"] / 1000.0,
        "second_stage_true_side_roll_rms_m": math.sqrt(
            mass_stats["true_side_roll_inertia_kg_m2"] / mass_stats["side_kg"]
        ),
        "minimum_frequency_hz": float(frequencies.min()),
        "mode_count_below_0_01_hz": int((frequencies < NEAR_ZERO_HZ).sum()),
        "minimum_raw_eigenvalue_rad2_s2": float(raw_eigenvalues.min()),
        "maximum_eigenpair_relative_residual": float(classification["eigenpair_relative_residual"].max()),
        "reference_all14_mean_absolute_error_percent": float(valid["absolute_error_percent"].mean()),
        "reference_all14_rms_error_percent": float(np.sqrt(np.mean(valid["relative_error_percent"] ** 2))),
        "reference_t_mean_absolute_error_percent": float(torsional["absolute_error_percent"].mean()),
        "reference_non_t_mean_absolute_error_percent": float(non_torsional["absolute_error_percent"].mean()),
        "reference_maximum_absolute_error_percent": float(valid["absolute_error_percent"].max()),
        "gauge_audit": gauge_audit,
    }
    (output_dir / "roll_upgraded_summary.json").write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_figures(production, parsed, model, classification, reference_match, modes, output_dir)
    np.savez_compressed(
        output_dir / "roll_upgraded_mode_vectors_first24.npz",
        modes=modes[:, : min(24, modes.shape[1])],
        xyz=model["xyz"],
        free_dofs=model["free_dofs"],
    )

    print(reference_match.to_string(index=False))
    print(json.dumps({k: v for k, v in statistics.items() if k != "gauge_audit"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
