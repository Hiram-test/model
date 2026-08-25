"""Write a complete CalculiX deck. Geometry already in x = chainage − K16+876."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from .constants import (
        ANCHOR_SPECS,
        AUDIT_STATIONS,
        FLOOR_SYSTEM_KNPM,
        G,
        PERSONNEL_KPA,
        PERSONNEL_SOURCE,
        PERSONNEL_WIDTH_M,
        PRIMARY_SUPPORTS,
        ROPE_FLOOR,
        ROPE_HAND_L,
        ROPE_HAND_U,
        ROPE_PORTAL,
        STEEL,
        SUPPORT_MATCH_TOL_M,
        WIND_KNPM,
        WIND_SOURCE,
    )
    from .formfind import initial_state
    from .reconcile import family_anchor_sets, serialize_anchors, write_sha256_sidecar
except ImportError:
    from constants import (
        ANCHOR_SPECS,
        AUDIT_STATIONS,
        FLOOR_SYSTEM_KNPM,
        G,
        PERSONNEL_KPA,
        PERSONNEL_SOURCE,
        PERSONNEL_WIDTH_M,
        PRIMARY_SUPPORTS,
        ROPE_FLOOR,
        ROPE_HAND_L,
        ROPE_HAND_U,
        ROPE_PORTAL,
        STEEL,
        SUPPORT_MATCH_TOL_M,
        WIND_KNPM,
        WIND_SOURCE,
    )
    from formfind import initial_state
    from reconcile import family_anchor_sets, serialize_anchors, write_sha256_sidecar

TENSION_ROLES = ("floor_rope", "portal_rope", "handrail_rope", "longitudinal_other")
BEAM_ROLES = ("cross_passage", "portal_or_beam", "short_other")

ROLE_MATERIAL = {
    "floor_rope": ROPE_FLOOR,
    "portal_rope": ROPE_PORTAL,
    "handrail_rope": ROPE_HAND_U,
    "longitudinal_other": ROPE_HAND_L,
    "cross_passage": STEEL,
    "portal_or_beam": STEEL,
    "short_other": STEEL,
}


def _role_density(mat: dict) -> float:
    if "rho" in mat:
        return float(mat["rho"])
    return float(mat["mu_kgpm"] / mat["A_m2"])


def support_sets(coords: np.ndarray) -> dict:
    """Pick support nodes in the SAME x used by *NODE. No xmin shift."""
    result = {}
    for spec in list(PRIMARY_SUPPORTS) + list(AUDIT_STATIONS):
        dist = np.abs(coords[:, 0] - spec["x"])
        near = np.flatnonzero(dist < SUPPORT_MATCH_TOL_M)
        result[spec["id"]] = {
            **spec,
            "node_idx": near,
            "n": int(near.size),
            "x_mean": None if near.size == 0 else float(coords[near, 0].mean()),
            "dx_max": None if near.size == 0 else float(dist[near].max()),
        }
    return result


def _distribute_line_load(coords, n1, n2, pick, w_npm, dof) -> dict[int, float]:
    """Distribute a uniform line load (N/m) to nodes of selected elements."""
    acc: dict[int, float] = defaultdict(float)
    if not np.any(pick):
        return acc
    vec = coords[n2[pick]] - coords[n1[pick]]
    length = np.linalg.norm(vec, axis=1)
    for a, b, elen in zip(n1[pick], n2[pick], length):
        share = 0.5 * w_npm * float(elen)
        acc[int(a)] += share
        acc[int(b)] += share
    return acc


def _fmt_set(name: str, ids: list[int], kind: str) -> list[str]:
    key = "NSET" if kind == "N" else "ELSET"
    lines = [f"*{key}, {key}={name}"]
    row: list[str] = []
    for i, nid in enumerate(ids, 1):
        row.append(str(nid))
        if i % 10 == 0:
            lines.append(", ".join(row))
            row = []
    if row:
        lines.append(", ".join(row))
    return lines


def write_calculix_inp(mesh: dict, out_path: Path, *, include_frequency: bool = True) -> dict:
    coords = mesh["coords"]
    n1 = mesh["n1"]
    n2 = mesh["n2"]
    role = mesh["role"]
    side = mesh["side"]
    n_nodes = len(coords)
    n_elem = len(n1)
    node_id = np.arange(1, n_nodes + 1)
    elem_id = np.arange(1, n_elem + 1)
    state = initial_state()
    supports = support_sets(coords)
    anchors = family_anchor_sets(mesh)

    n_floor = ROPE_FLOOR["n_per_deck"]
    # report packages are per deck; distributing onto 16 explicit floor ropes
    extra_dead_deck_npm = FLOOR_SYSTEM_KNPM * 1000.0 - n_floor * ROPE_FLOOR["mu_kgpm"] * G
    extra_dead_npm = extra_dead_deck_npm / n_floor
    personnel_npm = PERSONNEL_KPA * 1000.0 * PERSONNEL_WIDTH_M / n_floor
    wind_npm = WIND_KNPM * 1000.0 / n_floor

    floor = role == "floor_rope"
    dead_z = _distribute_line_load(coords, n1, n2, floor, extra_dead_npm, 3)
    live_z = _distribute_line_load(coords, n1, n2, floor, personnel_npm, 3)
    wind_y = _distribute_line_load(coords, n1, n2, floor, wind_npm, 2)

    def resultant(acc: dict[int, float]) -> float:
        return float(sum(acc.values()))

    floor_len = float(np.linalg.norm(coords[n2[floor]] - coords[n1[floor]], axis=1).sum()) if np.any(floor) else 0.0

    lines: list[str] = []
    a = lines.append
    a("*HEADING")
    a("Zhangjinggao catwalk centerline FEM")
    a("** coordinate: x = chainage - K16+876.000, y upstream->downstream, z up")
    a("** units: m, N, kg, s")
    a("** geometry: STEP cw_S10_0716t050342_a4_centerline.step (Release catwalk-attachment23-v2.0-s10-20260716)")
    a("** properties: drawings / check report; NOT S10.db, NOT B00, NOT MCT, NOT TARGET-FREQ")
    a("** write_inp: complete deck (nodes, elsets, materials, BC, initial stress, load cases)")
    a("** anchors: floor-rope and portal-rope families are DISJOINT NSETs; do not mix")
    a("** topology audit: 21 cross-passages, 71 portals/deck = 142 both decks")
    a(f"** nodes={n_nodes} elements={n_elem}")
    a("")

    a("*NODE")
    for nid, xyz in zip(node_id, coords):
        a(f"{nid}, {xyz[0]:.6f}, {xyz[1]:.6f}, {xyz[2]:.6f}")

    # nsets
    for spec in PRIMARY_SUPPORTS:
        rec = supports[spec["id"]]
        ids = [int(node_id[i]) for i in rec["node_idx"]]
        if ids:
            lines.extend(_fmt_set(f"N_SUP_{spec['id']}", ids, "N"))
    all_sup = []
    for spec in PRIMARY_SUPPORTS:
        all_sup.extend(int(node_id[i]) for i in supports[spec["id"]]["node_idx"])
    all_sup = sorted(set(all_sup))
    if all_sup:
        lines.extend(_fmt_set("N_SUPPORT_SADDLE_ENDS", all_sup, "N"))
        # keep legacy alias for older gates; it still excludes family anchors
        lines.extend(_fmt_set("N_SUPPORT_ALL", all_sup, "N"))

    # floor vs portal anchors: four named sets, never one mixed set
    a("** FAMILY ANCHORS: floor and portal kept in separate NSETs")
    a("** DECLARED: N_FLOOR_N N_FLOOR_S N_PORTAL_N N_PORTAL_S N_FLOOR_ANCHOR N_PORTAL_ANCHOR")
    floor_ids: list[int] = []
    portal_ids: list[int] = []
    for spec in ANCHOR_SPECS:
        rec = anchors[spec["id"]]
        ids = [int(node_id[i]) for i in rec["node_idx"]]
        if ids:
            lines.extend(_fmt_set(f"N_{spec['id']}", ids, "N"))
        else:
            a(f"** empty N_{spec['id']} (family={spec['family']}, x={spec['x']}, mode={rec.get('mode')})")
        if spec["family"] == "floor":
            floor_ids.extend(ids)
        else:
            portal_ids.extend(ids)
    floor_ids = sorted(set(floor_ids))
    portal_ids = sorted(set(portal_ids))
    if floor_ids:
        lines.extend(_fmt_set("N_FLOOR_ANCHOR", floor_ids, "N"))
    if portal_ids:
        lines.extend(_fmt_set("N_PORTAL_ANCHOR", portal_ids, "N"))
    overlap = sorted(set(floor_ids) & set(portal_ids))
    a(f"** floor/portal NSET overlap count = {len(overlap)} (must be 0)")
    for sname in ("upstream", "downstream"):
        ids = sorted(
            {int(node_id[int(a)]) for a, sid in zip(n1, side) if sid == sname}
            | {int(node_id[int(b)]) for b, sid in zip(n2, side) if sid == sname}
        )
        if ids:
            lines.extend(_fmt_set(f"N_{sname.upper()}", ids, "N"))

    # elements
    truss_ids: dict[str, list[int]] = defaultdict(list)
    beam_ids: dict[str, list[int]] = defaultdict(list)
    a("*ELEMENT, TYPE=T3D2, ELSET=E_TRUSS")
    for eid, a1, b1, r in zip(elem_id, n1, n2, role):
        if r in TENSION_ROLES:
            a(f"{eid}, {int(node_id[a1])}, {int(node_id[b1])}")
            truss_ids[r].append(int(eid))
    a("*ELEMENT, TYPE=B31, ELSET=E_BEAM")
    for eid, a1, b1, r in zip(elem_id, n1, n2, role):
        if r in BEAM_ROLES:
            a(f"{eid}, {int(node_id[a1])}, {int(node_id[b1])}")
            beam_ids[r].append(int(eid))

    for r, ids in truss_ids.items():
        lines.extend(_fmt_set(f"E_{r.upper()}", ids, "EL"))
    for r, ids in beam_ids.items():
        lines.extend(_fmt_set(f"E_{r.upper()}", ids, "EL"))

    # materials / sections
    mats = [ROPE_FLOOR, ROPE_PORTAL, ROPE_HAND_U, ROPE_HAND_L, STEEL]
    seen = set()
    for mat in mats:
        if mat["name"] in seen:
            continue
        seen.add(mat["name"])
        a(f"*MATERIAL, NAME={mat['name']}")
        a("*ELASTIC")
        a(f"{mat['E_Pa']:.6e}, {mat['nu']}")
        a("*DENSITY")
        a(f"{_role_density(mat):.6f}")

    for r, ids in truss_ids.items():
        mat = ROLE_MATERIAL[r]
        a(f"*SOLID SECTION, ELSET=E_{r.upper()}, MATERIAL={mat['name']}")
        a(f"{mat['A_m2']:.8e}")
    if beam_ids:
        a("*BEAM SECTION, ELSET=E_BEAM, MATERIAL=MAT-STEEL, SECTION=RECT")
        a("0.160, 0.160")
        a("0.0, 0.0, 1.0")

    # boundaries — same x convention; floor and portal get separate cards
    a("** BOUNDARY: UX,UY,UZ. Floor-rope anchors and portal-rope anchors are separate cards.")
    a("** convention: x = chainage - K16+876.000")
    if floor_ids:
        a("*BOUNDARY")
        a("N_FLOOR_ANCHOR, 1, 3")
    if portal_ids:
        a("*BOUNDARY")
        a("N_PORTAL_ANCHOR, 1, 3")
    if all_sup:
        a("*BOUNDARY")
        a("N_SUPPORT_SADDLE_ENDS, 1, 3")

    # initial stress
    a("** INITIAL STRESS from independent sag formula H=wL^2/(8h), h=227.300 m")
    a(f"** H_floor_deck={state['H_floor_deck_saddle_N']:.6e} N  sigma_floor={state['sigma_floor_Pa']:.6e} Pa")
    a("*INITIAL CONDITIONS, TYPE=STRESS")
    if truss_ids.get("floor_rope"):
        a(f"E_FLOOR_ROPE, {state['sigma_floor_Pa']:.6e}")
    if truss_ids.get("portal_rope"):
        a(f"E_PORTAL_ROPE, {state['sigma_portal_Pa']:.6e}")

    def cload_block(acc: dict[int, float], dof: int) -> None:
        if not acc:
            return
        a("*CLOAD")
        for nid in sorted(acc):
            val = acc[nid]
            if abs(val) < 1.0e-9:
                continue
            # dof 3 negative is downward
            a(f"{node_id[nid]}, {dof}, {val:.6e}")

    def grav() -> None:
        a("*DLOAD")
        if truss_ids:
            a(f"E_TRUSS, GRAV, {G:.6f}, 0., 0., -1.")
        if beam_ids:
            a(f"E_BEAM, GRAV, {G:.6f}, 0., 0., -1.")

    # STEP 1 dead + prestress
    a("*STEP, NLGEOM")
    a("LC-DEAD-PRESTRESS")
    a("*STATIC")
    grav()
    a("** extra floor-system dead beyond rope self-weight, downward")
    cload_block({k: -v for k, v in dead_z.items()}, 3)
    a("*NODE FILE")
    a("U")
    a("*EL FILE")
    a("S")
    a("*END STEP")

    # STEP personnel (loads redefined; CalculiX does not inherit DLOAD/CLOAD)
    a("*STEP, NLGEOM")
    a("LC-PERSONNEL-UNIFORM")
    a("*STATIC")
    grav()
    merged_z = defaultdict(float)
    for k, v in dead_z.items():
        merged_z[k] -= v
    for k, v in live_z.items():
        merged_z[k] -= v
    a(f"** personnel {PERSONNEL_KPA} kPa x {PERSONNEL_WIDTH_M} m; {PERSONNEL_SOURCE}")
    cload_block(merged_z, 3)
    a("*NODE FILE")
    a("U")
    a("*EL FILE")
    a("S")
    a("*END STEP")

    a("*STEP, NLGEOM")
    a("LC-WIND-Y")
    a("*STATIC")
    grav()
    a(f"** {WIND_SOURCE}")
    cload_block({k: -v for k, v in dead_z.items()}, 3)
    cload_block(wind_y, 2)
    a("*NODE FILE")
    a("U")
    a("*EL FILE")
    a("S")
    a("*END STEP")

    if include_frequency:
        a("** LC-FREQ after last static: linearization uses the last NLGEOM state.")
        a("** Dedicated dead+freq deck is written separately when run_pipeline asks.")
        a("*STEP")
        a("LC-FREQ")
        a("*FREQUENCY")
        a("20")
        a("*NODE FILE")
        a("U")
        a("*END STEP")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")

    text = out_path.read_text()
    required = (
        "*HEADING", "*NODE", "*ELEMENT, TYPE=T3D2", "*ELEMENT, TYPE=B31",
        "*MATERIAL", "*ELASTIC", "*DENSITY", "*SOLID SECTION", "*BEAM SECTION",
        "*BOUNDARY", "*INITIAL CONDITIONS, TYPE=STRESS",
        "LC-DEAD-PRESTRESS", "LC-PERSONNEL-UNIFORM", "LC-WIND-Y",
        "*DLOAD", "*CLOAD", "*STEP", "*END STEP",
        "N_FLOOR_ANCHOR", "N_PORTAL_ANCHOR",
    )
    missing = [key for key in required if key not in text]
    if include_frequency and "LC-FREQ" not in text:
        missing.append("LC-FREQ")

    meta = {
        "path": str(out_path),
        "n_nodes": n_nodes,
        "n_elements": n_elem,
        "role_counts": {r: int(np.sum(role == r)) for r in sorted(set(role))},
        "x_min": float(coords[:, 0].min()),
        "x_max": float(coords[:, 0].max()),
        "supports": {
            k: {kk: vv for kk, vv in rec.items() if kk != "node_idx"}
            for k, rec in supports.items()
        },
        "initial_state": state,
        "loads": {
            "floor_truss_length_m": floor_len,
            "n_floor_ropes_per_deck": n_floor,
            "extra_dead_deck_npm": extra_dead_deck_npm,
            "extra_dead_npm": extra_dead_npm,
            "extra_dead_resultant_N": resultant(dead_z),
            "personnel_deck_npm": PERSONNEL_KPA * 1000.0 * PERSONNEL_WIDTH_M,
            "personnel_npm": personnel_npm,
            "personnel_resultant_N": resultant(live_z),
            "wind_deck_npm": WIND_KNPM * 1000.0,
            "wind_npm": wind_npm,
            "wind_resultant_N": resultant(wind_y),
            "personnel_source": PERSONNEL_SOURCE,
            "wind_source": WIND_SOURCE,
            "distribution": "per-deck package split equally onto 16 floor ropes",
        },
        "missing_keywords": missing,
        "complete": not missing,
        "target_freq_in_deck": any(f"{f:.4f}" in text for f in (0.0296, 0.0301, 0.1187)),
        "xmin_shift_used": False,
        "anchors": serialize_anchors(anchors),
        "anchor_nsets_disjoint": len(overlap) == 0,
        "n_floor_anchor_nodes": len(floor_ids),
        "n_portal_anchor_nodes": len(portal_ids),
    }
    meta["hash"] = write_sha256_sidecar(out_path)
    return meta
