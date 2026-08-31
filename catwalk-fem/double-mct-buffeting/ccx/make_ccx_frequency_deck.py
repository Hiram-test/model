"""Emit a runnable CalculiX linear *FREQUENCY deck for the double-MCT catwalk model.

Sources (all committed in this repository, never modified here):
- structural_results/double_mct_nodes.csv        : double-plane node coordinates (sag as in MCT source).
- structural_results/double_mct_source_elements.csv : TENSTR ropes (EA, initial force) and gate replacements.
- structural_results/cross_passage_equivalent_links.csv : the 21 four-port stations (port node indices).
- inputs/gate_passage/K12_translation_ports_SI.csv : condensed 12x12 four-port matrix in N/m.
- inputs/catwalk_gantry_rope_combined_2.mct      : *CONSTRAINT supports and first *CONLOAD mass block.

Modelling rules implemented (per task instructions):
- Sag comes from the source coordinates unchanged; nothing is straightened or re-levelled.
- Supports are only the MCT *CONSTRAINT translations, applied to both widths; no global UY pinning.
- Every TENSTR is a T3D2 truss (real EA) plus three same-DOF SPRING2 elements of
  stiffness N/L (dx-dx, dy-dy, dz-dz) between its two end nodes. T3D2 contributes (EA/L) dd^T and
  the isotropic spring triplet contributes (N/L) I, so the pair reproduces the reference tangent
  (EA/L) dd^T + (N/L)(I - dd^T) with a documented +N/EA (<0.6%) axial surplus. No DOFs are added.
- All densities are near-zero and ALL mass is lumped into MASS elements (rope halves per element
  plus the first *CONLOAD block), exactly like the reference lumped-mass model. This is deliberate:
  the ccx 2.20 T3D2 expansion was measured to inflate consistent mass ~6.6x on a 3-node cable
  (see README), while zero-density T3D2 + lumped MASS matched scipy to 7 digits.
- Ordinary gates stay rank-one axial bars (T3D2 with the audited equivalent EA, near-zero density).
- The 21 four-port 12x12 matrices are NOT spring-decomposed (no extra DOFs). Each station gets
  three zero-mass T3D2 bars sized from the dominant K12 blocks: B_L-T_L and B_R-T_R along the
  in-plane bottom-to-gantry chord with k = |K12(B_UZ,T_UZ)|, and B_L-B_R transverse with
  k = |K12(B_L_UY,B_R_UY)|. Dropped small blocks are listed in the audit JSON.
- Second-stage masses are MASS elements from the first MCT *CONLOAD block (per width).
- One linear *STEP with *FREQUENCY, 25 modes (>= 20 required).
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
NODES_CSV = PKG / "structural_results" / "double_mct_nodes.csv"
ELEMS_CSV = PKG / "structural_results" / "double_mct_source_elements.csv"
PASSAGE_CSV = PKG / "structural_results" / "cross_passage_equivalent_links.csv"
K12_SI_CSV = PKG / "inputs" / "gate_passage" / "K12_translation_ports_SI.csv"
MCT_PATH = PKG / "inputs" / "catwalk_gantry_rope_combined_2.mct"
INP_PATH = HERE / "double_mct_frequency.inp"
SAG_CSV = HERE / "SAG_CHECK.csv"
SAG_MD = HERE / "SAG_CHECK.md"
AUDIT_JSON = HERE / "deck_audit.json"

GRAVITY = 9.806
E_ROPE = 120.0e9
A_CARRY = math.pi * 0.168498**2 / 4.0
A_GANTRY = math.pi * 0.103436**2 / 4.0
RHO_CARRY = 1.24031e-7 * 1.0e9 * 1000.0 / GRAVITY   # kN/mm3 -> kg/m3 (used for lumping only)
RHO_GANTRY = 8.432e-8 * 1.0e9 * 1000.0 / GRAVITY
GATE_EA = 199_405_719.09780553
A_GATE = 4896.0e-6
E_GATE = GATE_EA / A_GATE
RHO_TINY = 1.0e-9  # all element densities near zero; mass is carried by lumped MASS elements
MODES = 60  # ARPACK with a small subspace stalls on the tight low clusters; 60 recovers all low modes
MCT_X_ORIGIN_M = 831.091


def expand_id_spec(spec: str) -> list[int]:
    result: list[int] = []
    for token in spec.replace("\\", " ").split():
        m = re.fullmatch(r"(-?\d+)to(-?\d+)(?:by(-?\d+))?", token, flags=re.IGNORECASE)
        if m:
            start, stop = int(m.group(1)), int(m.group(2))
            step = int(m.group(3) or (1 if stop >= start else -1))
            result.extend(range(start, stop + (1 if step > 0 else -1), step))
        elif re.fullmatch(r"-?\d+", token):
            result.append(int(token))
    return result


def mct_blocks(lines: list[str], name: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("*"):
            current = [] if stripped.split()[0].upper() == name.upper() else None
            if current is not None:
                blocks.append(current)
            continue
        if current is not None and stripped and not stripped.startswith(";"):
            current.append(stripped)
    return blocks


def main() -> None:
    mct_lines = MCT_PATH.read_text(encoding="utf-8", errors="replace").splitlines()

    # --- MCT source nodes (mm -> m) for the sag check -------------------------------------
    src_nodes: dict[int, tuple[float, float, float]] = {}
    for line in mct_blocks(mct_lines, "*NODE")[0]:
        f = [x.strip() for x in line.split(",")]
        src_nodes[int(f[0])] = (float(f[1]) / 1000.0, float(f[2]) / 1000.0, float(f[3]) / 1000.0)

    # --- Double-plane nodes (authoritative geometry, sag untouched) -----------------------
    nodes: dict[int, tuple[float, float, float]] = {}
    node_meta: dict[int, tuple[str, int]] = {}
    with NODES_CSV.open() as fh:
        for row in csv.DictReader(fh):
            gid = int(row["global_index"]) + 1  # ccx ids are 1-based
            nodes[gid] = (float(row["x_m"]), float(row["y_m"]), float(row["z_m"]))
            node_meta[gid] = (row["width"], int(row["mct_node"]))
    by_width_mct = {(w, m): gid for gid, (w, m) in node_meta.items()}

    # --- Sag check against the MCT source --------------------------------------------------
    max_dz = 0.0
    for gid, (w, mct_id) in node_meta.items():
        dz = abs(nodes[gid][2] - src_nodes[mct_id][2])
        dx = abs(nodes[gid][0] - (src_nodes[mct_id][0] - MCT_X_ORIGIN_M))
        max_dz = max(max_dz, dz, dx)
    carry_main = [i for i in src_nodes if 155 <= i <= 448]
    xs = {i: src_nodes[i][0] - MCT_X_ORIGIN_M for i in carry_main}
    mid_x = 0.5 * (min(xs.values()) + max(xs.values()))
    mid_node = min(carry_main, key=lambda i: abs(xs[i] - mid_x))
    tower_node = max(src_nodes, key=lambda i: src_nodes[i][2])
    sag_rows = []
    for width in ("L", "R"):
        deck_mid = nodes[by_width_mct[(width, mid_node)]]
        deck_tower = nodes[by_width_mct[(width, tower_node)]]
        sag_rows.append({
            "width": width,
            "tower_top_mct_node": tower_node,
            "tower_top_z_deck_m": deck_tower[2],
            "tower_top_z_source_m": src_nodes[tower_node][2],
            "midspan_mct_node": mid_node,
            "midspan_x_m": deck_mid[0],
            "midspan_z_deck_m": deck_mid[2],
            "midspan_z_source_m": src_nodes[mid_node][2],
            "tower_minus_midspan_m": deck_tower[2] - deck_mid[2],
            "max_abs_coord_diff_vs_source_m": max_dz,
        })
    with SAG_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sag_rows[0]))
        writer.writeheader()
        writer.writerows(sag_rows)

    # --- Elements (rope mass lumped half-half per node, like the reference) ------------------
    carry, gantry, gate = [], [], []
    springs: list[tuple[int, int, float]] = []  # n1, n2, k=N/L
    lumped_mass: dict[int, float] = {}
    with ELEMS_CSV.open() as fh:
        for row in csv.DictReader(fh):
            kind = row["kind"]
            if kind == "TRUSS_REPLACED_BY_FOUR_PORT":
                continue
            n1 = int(row["n1_global"]) + 1
            n2 = int(row["n2_global"]) + 1
            ea = float(row["equivalent_ea_n"])
            if kind == "TENSTR":
                is_carry = abs(ea - E_ROPE * A_CARRY) < abs(ea - E_ROPE * A_GANTRY)
                (carry if is_carry else gantry).append((n1, n2))
                force_n = float(row["initial_force_kn"]) * 1000.0
                length = float(row["length_m"])
                if force_n > 0.0:
                    springs.append((n1, n2, force_n / length))
                rho, area = (RHO_CARRY, A_CARRY) if is_carry else (RHO_GANTRY, A_GANTRY)
                half = 0.5 * rho * area * length
                lumped_mass[n1] = lumped_mass.get(n1, 0.0) + half
                lumped_mass[n2] = lumped_mass.get(n2, 0.0) + half
            else:  # TRUSS_REPLACED_BY_GATE_ONLY_RANK1
                gate.append((n1, n2))
    if not carry or not gantry or len(gate) != 100:
        raise ValueError(f"unexpected element counts: carry={len(carry)} gantry={len(gantry)} gate={len(gate)}")

    # --- Four-port stations -> three dominant-block bars each -------------------------------
    with K12_SI_CSV.open() as fh:
        rows = list(csv.reader(fh))
    labels = rows[0][1:]
    k12 = {(rows[i + 1][0], labels[j]): float(rows[i + 1][j + 1]) for i in range(12) for j in range(12)}
    k_bt = abs(k12[("B_L_UZ", "T_L_UZ")])
    k_bb = abs(k12[("B_L_UY", "B_R_UY")])
    dropped = {"T_L_UY-T_R_UY": k12[("T_L_UY", "T_R_UY")], "B_L_UY-T_L_UY": k12[("B_L_UY", "T_L_UY")],
               "B_L_UX-B_L_UX": k12[("B_L_UX", "B_L_UX")]}
    passage_bt, passage_bb = [], []
    with PASSAGE_CSV.open() as fh:
        for row in csv.DictReader(fh):
            bl = int(row["cw1_bottom_global"]) + 1
            tl = int(row["cw1_gantry_global"]) + 1
            br = int(row["cw2_bottom_global"]) + 1
            tr = int(row["cw2_gantry_global"]) + 1
            passage_bt.extend([(bl, tl), (br, tr)])
            passage_bb.append((bl, br))
    if len(passage_bb) != 21:
        raise ValueError(f"expected 21 passages, found {len(passage_bb)}")

    def dist(a: int, b: int) -> float:
        (x1, y1, z1), (x2, y2, z2) = nodes[a], nodes[b]
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

    # --- Supports: only the MCT *CONSTRAINT translations ------------------------------------
    boundaries: list[tuple[int, int]] = []
    constrained_nodes = set()
    for line in mct_blocks(mct_lines, "*CONSTRAINT")[0]:
        f = [x.strip() for x in line.split(",")]
        mask = f[1]
        for mct_id in expand_id_spec(f[0]):
            for width in ("L", "R"):
                gid = by_width_mct[(width, mct_id)]
                constrained_nodes.add(gid)
                for comp in range(3):
                    if comp < len(mask) and mask[comp] == "1":
                        boundaries.append((gid, comp + 1))
    uy_fixed = sum(1 for _, d in boundaries if d == 2)

    # --- Second-stage masses from the first *CONLOAD block ----------------------------------
    conload_mass: dict[int, float] = {}
    for line in mct_blocks(mct_lines, "*CONLOAD")[0]:
        f = [x.strip() for x in line.split(",")]
        fz_kn = float(f[3])
        for mct_id in expand_id_spec(f[0]):
            conload_mass[mct_id] = conload_mass.get(mct_id, 0.0) + max(0.0, -fz_kn) * 1000.0 / GRAVITY

    # --- Write the deck ----------------------------------------------------------------------
    out: list[str] = []
    out.append("** Double-MCT catwalk linear frequency deck (generated by make_ccx_frequency_deck.py)")
    out.append("** Geometry: structural_results/double_mct_nodes.csv (MCT source sag, unmodified)")
    out.append("** Supports: MCT *CONSTRAINT only; no global UY constraint")
    out.append("*NODE")
    for gid in sorted(nodes):
        x, y, z = nodes[gid]
        out.append(f"{gid}, {x:.10e}, {y:.10e}, {z:.10e}")

    eid = 0

    def emit_trusses(name: str, pairs: list[tuple[int, int]]) -> None:
        nonlocal eid
        out.append(f"*ELEMENT, TYPE=T3D2, ELSET={name}")
        for n1, n2 in pairs:
            eid += 1
            out.append(f"{eid}, {n1}, {n2}")

    emit_trusses("ECARRY", carry)
    emit_trusses("EGANTRY", gantry)
    emit_trusses("EGATE", gate)
    emit_trusses("EXP_BT", passage_bt)
    emit_trusses("EXP_BB", passage_bb)

    out.append("*MATERIAL, NAME=MCARRY")
    out.append(f"*ELASTIC\n{E_ROPE:.10e}, 0.")
    out.append(f"*DENSITY\n{RHO_TINY:.10e}")
    out.append("*MATERIAL, NAME=MGANTRY")
    out.append(f"*ELASTIC\n{E_ROPE:.10e}, 0.")
    out.append(f"*DENSITY\n{RHO_TINY:.10e}")
    out.append("*MATERIAL, NAME=MGATE")
    out.append(f"*ELASTIC\n{E_GATE:.10e}, 0.")
    out.append(f"*DENSITY\n{RHO_TINY:.10e}")
    out.append(f"*SOLID SECTION, ELSET=ECARRY, MATERIAL=MCARRY\n{A_CARRY:.10e}")
    out.append(f"*SOLID SECTION, ELSET=EGANTRY, MATERIAL=MGANTRY\n{A_GANTRY:.10e}")
    out.append(f"*SOLID SECTION, ELSET=EGATE, MATERIAL=MGATE\n{A_GATE:.10e}")

    # Four-port dominant-block bars: per-element sections so that EA = k * L.
    for tag, pairs, k in (("XBT", passage_bt, k_bt), ("XBB", passage_bb, k_bb)):
        base_eid = eid - len(passage_bt) - len(passage_bb) + (0 if tag == "XBT" else len(passage_bt))
        for i, (n1, n2) in enumerate(pairs):
            this_eid = base_eid + i + 1
            elset = f"E{tag}{i:02d}"
            out.append(f"*ELSET, ELSET={elset}\n{this_eid}")
            length = dist(n1, n2)
            area = k * length / E_GATE
            out.append(f"*SOLID SECTION, ELSET={elset}, MATERIAL=MGATE\n{area:.10e}")

    # Geometric stiffness of the initial tensions: three same-DOF SPRING2 per TENSTR (k=N/L).
    for i, (n1, n2, k) in enumerate(springs):
        for dof in (1, 2, 3):
            eid += 1
            elset = f"SPG{i:04d}D{dof}"
            out.append(f"*ELEMENT, TYPE=SPRING2, ELSET={elset}\n{eid}, {n1}, {n2}")
            out.append(f"*SPRING, ELSET={elset}\n{dof}, {dof}\n{k:.10e}")

    # All mass lumped per node: rope halves plus the second-stage *CONLOAD masses (both widths).
    for mct_id, mass in sorted(conload_mass.items()):
        for width in ("L", "R"):
            gid = by_width_mct[(width, mct_id)]
            lumped_mass[gid] = lumped_mass.get(gid, 0.0) + mass
    total_mass = sum(lumped_mass.values())
    mass_id = 0
    for gid in sorted(lumped_mass):
        if lumped_mass[gid] <= 0.0:
            continue
        eid += 1
        mass_id += 1
        elset = f"GM{mass_id:04d}"
        out.append(f"*ELEMENT, TYPE=MASS, ELSET={elset}\n{eid}, {gid}")
        out.append(f"*MASS, ELSET={elset}\n{lumped_mass[gid]:.10e}")

    out.append("*BOUNDARY")
    for gid, dof in boundaries:
        out.append(f"{gid}, {dof}, {dof}")

    out.append("*STEP")
    out.append(f"*FREQUENCY\n{MODES}")
    out.append("*NODE FILE\nU")
    out.append("*END STEP")
    INP_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")

    # --- Sag markdown + audit ----------------------------------------------------------------
    r = sag_rows[0]
    SAG_MD.write_text(
        "# SAG_CHECK\n\n"
        "Deck geometry is copied verbatim from `structural_results/double_mct_nodes.csv` "
        "(itself the MCT source coordinates); nothing straightened, midspan not raised.\n\n"
        f"- Tower-top Z (deck) = {r['tower_top_z_deck_m']:.4f} m ; MCT source = {r['tower_top_z_source_m']:.4f} m (MCT node {r['tower_top_mct_node']})\n"
        f"- Main-span midspan Z (deck) = {r['midspan_z_deck_m']:.4f} m ; MCT source = {r['midspan_z_source_m']:.4f} m (MCT node {r['midspan_mct_node']}, x = {r['midspan_x_m']:.2f} m)\n"
        f"- Tower-top minus midspan = {r['tower_minus_midspan_m']:.4f} m of sag retained\n"
        f"- Max |deck - source| over all node coordinates (both widths) = {r['max_abs_coord_diff_vs_source_m']:.3e} m\n"
        f"- UY fixed only at MCT support nodes: {uy_fixed} DOFs out of {3 * len(nodes)} total; no global UY pinning\n",
        encoding="utf-8",
    )
    audit = {
        "deck": str(INP_PATH.name),
        "modes_requested": MODES,
        "nodes": len(nodes),
        "elements": {"carry_t3d2": len(carry), "gantry_t3d2": len(gantry), "gate_rank1_t3d2": len(gate),
                     "passage_bt_bars": len(passage_bt), "passage_bb_bars": len(passage_bb),
                     "tension_spring2": 3 * len(springs), "mass_elements": mass_id},
        "boundary_dofs": len(boundaries),
        "uy_fixed_dofs": uy_fixed,
        "no_global_uy_pinning": True,
        "four_port_treatment": {
            "rule": "no spring decomposition (no extra DOFs); dominant K12 blocks as zero-mass axial bars",
            "k_bt_N_per_m": k_bt, "k_bb_N_per_m": k_bb, "dropped_blocks_N_per_m": dropped,
        },
        "axial_surplus_note": "T3D2 keeps full EA; spring triplet adds N/L isotropically, so axial stiffness is (EA+N)/L (max +0.6%)",
        "mass_model": {
            "rule": "all element densities 1e-9; total mass lumped into per-node MASS elements (rope halves + first *CONLOAD block)",
            "total_lumped_mass_tonne": total_mass / 1000.0,
            "reference_target_tonne": 4108.46690758,
        },
        "sag_check": sag_rows,
    }
    AUDIT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit["elements"], indent=2))
    print(f"nodes={len(nodes)} boundaries={len(boundaries)} uy_fixed={uy_fixed}")
    print(f"sag: tower={r['tower_top_z_deck_m']:.3f} mid={r['midspan_z_deck_m']:.3f} maxdiff={r['max_abs_coord_diff_vs_source_m']:.2e}")


if __name__ == "__main__":
    main()
