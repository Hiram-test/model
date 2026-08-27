"""H10 双簇端口凝聚：把门架/横通道凝聚到每接口两个索簇平动子端口.

背景：单中心端口凝聚把每接口 16/6 个索点刚性绑到一个中心。转角自由凝聚后
（正式 ROM）截面滚转不可观，幅内扭转刚度丢失；若保留中心转角再刚性展开，
又把整个 5.34 m 幅宽当成刚性平板，幅内扭转被过约束（Rayleigh 检验显示该
分支被推到 1.0–3.8 Hz，比附件 TA1=0.0996 Hz 高一个量级）。

本脚本按实际索排布（每接口两簇：承重索 8+8 根、门架索 3+3 根）把每簇刚性
映射到该簇的参考点（取在张力 rms 半距 ±b 处——刚性映射对参考点选取不敏感，
选 rms 点使子端口与双索组模型的节点位置严格一致），保留簇参考点 6 自由度后
再把全部转角自由凝聚。所得平动子端口矩阵：

- 门架（单品，30 根 BEAM188）：K12，端口序 (B+, B-, T+, T-)×(UX,UY,UZ)；
- 门架×2 + 横通道（699 根 BEAM188）：K24，端口序
  (B_L+, B_L-, T_L+, T_L-, B_R+, B_R-, T_R+, T_R-)×(UX,UY,UZ)。

"+" 表示簇位于该幅中心 +Y 一侧（APDL 横桥向）。四/八个子端口即可客观观测
截面滚转，横梁在两簇之间的柔性被保留，不再需要任何截面刚性假设或伪逆展开。

来源等价性：包内 `apply_finite_gates_and_passages_v2.inp`（legacy 版）重跑
单中心凝聚与已审计 `H10_gate_passage_condensed.npz` 的 K24 相对最大差为 0，
证明其 H10 子结构与审计版本完全一致（文件级哈希差异来自与凝聚无关的段落）。

运行（在 double-mct-buffeting 包根目录）：
    python code/condense_h10_cluster_ports.py
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import null_space

PACKAGE = Path(__file__).resolve().parents[1]
CORE_PATH = PACKAGE / "inputs/gate_passage/condense_h10.py"
APDL_PATH = PACKAGE / "inputs/roll_upgrade_sources/apply_finite_gates_and_passages_v2.inp"
COUPLINGS_PATH = PACKAGE / "inputs/roll_upgrade_sources/passage_gate_rope_couplings.csv"
REFERENCE_NPZ = PACKAGE / "inputs/gate_passage/H10_gate_passage_condensed.npz"
OUTPUT_DIR = PACKAGE / "inputs/roll_upgrade_sources/cluster_condensation"

PASSAGE_PORTS = ("B_L", "T_L", "B_R", "T_R")
GATE_PORTS = ("B", "T")


def load_core():
    spec = importlib.util.spec_from_file_location("condense_core", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.APDL = APDL_PATH
    module.COUPLINGS = COUPLINGS_PATH
    return module


def cluster_reference_points(couplings: list[dict], ports: tuple[str, ...]) -> tuple[dict, dict]:
    """Assign each rope record to a (port, sign) cluster; reference point at the rms half-gauge."""
    references: dict[tuple[str, int], np.ndarray] = {}
    rms_by_port: dict[str, float] = {}
    for port in ports:
        points = np.vstack([r["point"] for r in couplings if r["port"] == port])
        center = points.mean(axis=0)
        offsets = points[:, 1] - center[1]  # APDL y is the transverse axis
        rms = math.sqrt(float(np.mean(offsets**2)))
        rms_by_port[port] = rms
        for sign in (1, -1):
            reference = center.copy()
            reference[1] = center[1] + sign * rms
            references[(port, sign)] = reference
    for record in couplings:
        center_y = float(np.mean([r["point"][1] for r in couplings if r["port"] == record["port"]]))
        record["cluster_sign"] = 1 if record["point"][1] > center_y else -1
    return references, rms_by_port


def build_cluster_constraints(core, nodes, root_index, external_rigid, couplings, ports):
    """Constraint rows tie each physical rope translation to its gate master (UXYZ);
    the port map expresses the same translations from the cluster reference DOFs."""
    from scipy.sparse import coo_matrix

    rigid_by_slave = {record["slave"]: record for record in external_rigid}
    references, rms_by_port = cluster_reference_points(couplings, ports)
    port_keys = [(port, sign) for port in ports for sign in (1, -1)]
    key_index = {key: i for i, key in enumerate(port_keys)}
    rows, cols, vals = [], [], []
    port_map = np.zeros((len(couplings) * 3, len(port_keys) * 6))
    for record_index, record in enumerate(couplings):
        rigid = rigid_by_slave[record["slave"]]
        master = rigid["master"]
        if master not in root_index:
            raise RuntimeError(f"external master {master} is not a root node")
        gate_map = core.translation_rigid_map(record["point"] - nodes[master])
        key = (record["port"], record["cluster_sign"])
        center_map = core.translation_rigid_map(record["point"] - references[key])
        row0 = record_index * 3
        col0 = root_index[master] * 6
        for lr in range(3):
            for lc in range(6):
                value = float(gate_map[lr, lc])
                if value != 0.0:
                    rows.append(row0 + lr)
                    cols.append(col0 + lc)
                    vals.append(value)
        port0 = key_index[key] * 6
        port_map[row0 : row0 + 3, port0 : port0 + 6] = center_map
    constraint = coo_matrix((vals, (rows, cols)), shape=(len(couplings) * 3, len(root_index) * 6)).tocsc()
    return constraint, port_map, references, rms_by_port, port_keys


def condense_rotations(stiffness_full: np.ndarray, port_count: int) -> tuple[np.ndarray, np.ndarray, str]:
    translation = np.array([p * 6 + d for p in range(port_count) for d in range(3)])
    rotation = np.array([p * 6 + d for p in range(port_count) for d in range(3, 6)])
    k_tt = stiffness_full[np.ix_(translation, translation)]
    k_tr = stiffness_full[np.ix_(translation, rotation)]
    k_rr = 0.5 * (
        stiffness_full[np.ix_(rotation, rotation)] + stiffness_full[np.ix_(rotation, rotation)].T
    )
    eigen_rr = np.linalg.eigvalsh(k_rr)
    if eigen_rr[0] <= max(eigen_rr[-1], 1.0) * 1.0e-12:
        inverse_action = np.linalg.pinv(k_rr, rcond=1.0e-12) @ k_tr.T
        method = "symmetric_pseudoinverse"
    else:
        inverse_action = np.linalg.solve(k_rr, k_tr.T)
        method = "direct_solve"
    condensed = k_tt - k_tr @ inverse_action
    return 0.5 * (condensed + condensed.T), eigen_rr, method


def rigid_modes_translations(positions: list[np.ndarray]) -> np.ndarray:
    origin = np.mean(np.vstack(positions), axis=0)
    matrix = np.zeros((3 * len(positions), 6))
    for i, p in enumerate(positions):
        r = p - origin
        matrix[3 * i : 3 * i + 3, :3] = np.eye(3)
        matrix[3 * i : 3 * i + 3, 3:] = -np.array(
            [[0.0, -r[2], r[1]], [r[2], 0.0, -r[0]], [-r[1], r[0], 0.0]]
        )
    return matrix


def clean_translation_stiffness(stiffness: np.ndarray, rigid: np.ndarray):
    strain_basis = null_space(rigid.T, rcond=1.0e-12)
    reduced = 0.5 * (strain_basis.T @ (stiffness + stiffness.T) @ strain_basis)
    eigenvalues, eigenvectors = np.linalg.eigh(reduced)
    tolerance = max(float(np.max(np.abs(eigenvalues))), 1.0) * 1.0e-10
    if float(eigenvalues.min()) < -tolerance:
        raise RuntimeError(f"significant negative stiffness {eigenvalues.min():.6e} N/mm in strain subspace")
    clipped = np.maximum(eigenvalues, 0.0)
    cleaned = strain_basis @ eigenvectors @ np.diag(clipped) @ eigenvectors.T @ strain_basis.T
    cleaned = 0.5 * (cleaned + cleaned.T)
    correction = np.linalg.norm(cleaned - stiffness, "fro") / max(np.linalg.norm(stiffness, "fro"), 1.0)
    return cleaned, eigenvalues, correction


def write_matrix(path: Path, matrix: np.ndarray, labels: list[str]) -> None:
    import csv

    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dof"] + labels)
        for label, row in zip(labels, matrix):
            writer.writerow([label] + [f"{value:.12e}" for value in row])


def spectrum_summary(matrix: np.ndarray, rigid: np.ndarray) -> dict:
    eigenvalues = np.linalg.eigvalsh(matrix)
    scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
    zero_count = int(np.sum(np.abs(eigenvalues) < scale * 1.0e-8))
    negative_count = int(np.sum(eigenvalues < -scale * 1.0e-8))
    rigid_residual = float(np.max(np.abs(matrix @ rigid))) / scale
    return {
        "eigenvalues_N_per_mm": eigenvalues.tolist(),
        "zero_mode_count_rel_1e_8": zero_count,
        "negative_mode_count_rel_1e_8": negative_count,
        "rigid_body_residual": rigid_residual,
    }


def main() -> None:
    core = load_core()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nodes, elements, cerig, sections, densities = core.parse_apdl()
    couplings = core.parse_h10_couplings()
    internal = [r for r in cerig if r["dof"] == "ALL"]
    external = [r for r in cerig if r["dof"] != "ALL"]
    audit: dict[str, object] = {
        "apdl_path": str(APDL_PATH.relative_to(PACKAGE)),
        "apdl_sha256": core.sha256(APDL_PATH),
        "couplings_sha256": core.sha256(COUPLINGS_PATH),
        "beam188_elements": len(elements),
        "internal_all_links": len(internal),
        "external_uxyz_links": len(external),
        "material_densities": densities,
    }

    # --- Source-equivalence check: reproduce the audited single-centre K24 exactly.
    stiffness_root, root_nodes, root_index, node_map, lengths = core.assemble_root_stiffness(
        nodes, elements, internal, sections
    )
    constraint_c, port_map_c, centers_c = core.build_interface_constraints(nodes, root_index, external, couplings)
    k24_center, _ = core.constrained_port_stiffness(stiffness_root, constraint_c, port_map_c)
    reference = np.load(REFERENCE_NPZ)
    k24_audited = np.asarray(reference["K24_mixed_N_mm"], dtype=float)
    reproduction = float(np.max(np.abs(k24_center - k24_audited))) / float(np.max(np.abs(k24_audited)))
    audit["audited_K24_reproduction_relative_max_diff"] = reproduction
    if reproduction > 1.0e-9:
        raise RuntimeError(f"APDL source does not reproduce the audited K24 (diff {reproduction})")

    # --- Passage + both gates: eight cluster translation ports.
    constraint, port_map, references, rms_by_port, port_keys = build_cluster_constraints(
        core, nodes, root_index, external, couplings, PASSAGE_PORTS
    )
    k48, saddle_size = core.constrained_port_stiffness(stiffness_root, constraint, port_map)
    k24_cluster_raw, eigen_rr, method = condense_rotations(k48, 8)
    positions = [references[key] for key in port_keys]
    rigid24 = rigid_modes_translations(positions)
    k24_cluster, strain_eigen_24, correction_24 = clean_translation_stiffness(k24_cluster_raw, rigid24)
    labels24 = [f"{port}{'p' if sign > 0 else 'm'}_{axis}" for port, sign in port_keys for axis in ("UX", "UY", "UZ")]
    write_matrix(OUTPUT_DIR / "K24_passage_cluster_translation_N_per_mm.csv", k24_cluster, labels24)
    audit["passage_cluster"] = {
        "port_order": [f"{port}{'p' if sign > 0 else 'm'}" for port, sign in port_keys],
        "reference_points_apdl_mm": {f"{p}{'p' if s > 0 else 'm'}": references[(p, s)].tolist() for p, s in port_keys},
        "rms_half_gauge_mm": rms_by_port,
        "saddle_size": saddle_size,
        "rotation_condensation_method": method,
        "rotation_block_eigenvalues": eigen_rr.tolist(),
        "strain_subspace_eigenvalues_before_clip": strain_eigen_24.tolist(),
        "psd_cleanup_relative_correction": correction_24,
        "spectrum": spectrum_summary(k24_cluster, rigid24),
    }

    # --- Single CW1 gate: four cluster translation ports.
    gate_nodes_range = (2001985, 2002048)
    gate_elements = [e for e in elements if core.in_ranges(e["id"], (core.GATE_ELEMENT_RANGES[0],))]
    gate_node_ids = {e["n1"] for e in gate_elements} | {e["n2"] for e in gate_elements}
    gate_internal = [r for r in internal if r["master"] in gate_node_ids or r["slave"] in gate_node_ids]
    gate_couplings = [
        {**r, "port": "B" if r["port"] == "B_L" else "T"} for r in couplings if r["port"] in ("B_L", "T_L")
    ]
    gate_slaves = {r["slave"] for r in gate_couplings}
    gate_external = [r for r in external if r["slave"] in gate_slaves]
    k_gate_root, gate_roots, gate_root_index, _, gate_lengths = core.assemble_root_stiffness(
        nodes, gate_elements, gate_internal, sections
    )
    g_constraint, g_port_map, g_references, g_rms, g_port_keys = build_cluster_constraints(
        core, nodes, gate_root_index, gate_external, gate_couplings, GATE_PORTS
    )
    k24_gate, g_saddle = core.constrained_port_stiffness(k_gate_root, g_constraint, g_port_map)
    k12_gate_raw, g_eigen_rr, g_method = condense_rotations(k24_gate, 4)
    g_positions = [g_references[key] for key in g_port_keys]
    rigid12 = rigid_modes_translations(g_positions)
    k12_gate, strain_eigen_12, correction_12 = clean_translation_stiffness(k12_gate_raw, rigid12)
    labels12 = [f"{port}{'p' if sign > 0 else 'm'}_{axis}" for port, sign in g_port_keys for axis in ("UX", "UY", "UZ")]
    write_matrix(OUTPUT_DIR / "K12_gate_cluster_translation_N_per_mm.csv", k12_gate, labels12)

    # Axial extraction along the H10 chord for the per-station EA/L rescale.
    b_center = np.mean([g_references[("B", 1)], g_references[("B", -1)]], axis=0)
    t_center = np.mean([g_references[("T", 1)], g_references[("T", -1)]], axis=0)
    chord = t_center - b_center
    chord_unit = chord / np.linalg.norm(chord)
    g_axial = np.zeros(12)
    for i, (port, sign) in enumerate(g_port_keys):
        g_axial[3 * i : 3 * i + 3] = (0.5 * chord_unit) * (1.0 if port == "T" else -1.0)
    axial_k = float(g_axial @ k12_gate @ g_axial)  # |g| = 1, so k = g^T K g
    audit["gate_cluster"] = {
        "port_order": [f"{port}{'p' if sign > 0 else 'm'}" for port, sign in g_port_keys],
        "reference_points_apdl_mm": {f"{p}{'p' if s > 0 else 'm'}": g_references[(p, s)].tolist() for p, s in g_port_keys},
        "rms_half_gauge_mm": g_rms,
        "beam188_elements": len(gate_elements),
        "saddle_size": g_saddle,
        "rotation_condensation_method": g_method,
        "rotation_block_eigenvalues": g_eigen_rr.tolist(),
        "strain_subspace_eigenvalues_before_clip": strain_eigen_12.tolist(),
        "psd_cleanup_relative_correction": correction_12,
        "spectrum": spectrum_summary(k12_gate, rigid12),
        "h10_chord_apdl_mm": chord.tolist(),
        "axial_k_N_per_mm": axial_k,
        "single_center_axial_k_N_per_mm": 24925.700817808793,
        "axial_k_ratio_cluster_over_center": axial_k / 24925.700817808793,
    }

    (OUTPUT_DIR / "cluster_condensation_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in audit.items() if not isinstance(v, dict)}, ensure_ascii=False, indent=2))
    print("passage cluster zero modes:", audit["passage_cluster"]["spectrum"]["zero_mode_count_rel_1e_8"])
    print("passage strain eigen (N/mm):", np.round(np.array(strain_eigen_24), 6).tolist())
    print("gate cluster zero modes:", audit["gate_cluster"]["spectrum"]["zero_mode_count_rel_1e_8"])
    print("gate strain eigen (N/mm):", np.round(np.array(strain_eigen_12), 6).tolist())
    print(f"gate axial k = {axial_k:.4f} N/mm (single-centre 24925.7008)")


if __name__ == "__main__":
    main()
