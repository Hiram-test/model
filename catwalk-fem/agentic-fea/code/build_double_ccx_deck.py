"""Build the double-MCT catwalk CalculiX deck (N, mm, tonne units).

Skill nodes S07-S12 executor: geometry from the reviewed MCT source, sections and
connections per drawing-consistent conventions of the audited migrate deck
(974211b2), 21 cross-passages from the authoritative station map, second-stage
mass as MASS elements, prestress as element/IP six-component global PK2.

Steps emitted: P1 *STATIC NLGEOM (gravity + prestress) then *STEP,PERTURBATION
*FREQUENCY (80 modes). No attachment 2-3 frequency is read anywhere here.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/workspace")
ROM_CODE = REPO / "catwalk-fem/double-mct-buffeting/code"
sys.path.insert(0, str(ROM_CODE))
from double_mct_equivalent_passage_model import parse_mct, sha256_file  # noqa: E402

MCT_PATH = REPO / "catwalk-fem/double-mct-buffeting/inputs/catwalk_gantry_rope_combined_2.mct"
STATION_MAP = REPO / "catwalk-fem/double-mct-buffeting/inputs/passage_station_authoritative_map.csv"
OUT_DIR = REPO / "catwalk-fem/agentic-fea/solver"
ART_DIR = REPO / "catwalk-fem/agentic-fea/artifacts"

HALF_SPACING_MM = 21450.0
W2_NODE_OFFSET = 5000
W2_ELEM_OFFSET = 5000
PASSAGE_EID0 = 30000
MASS_EID0 = 40000
GRAVITY_MM_S2 = 9806.0
MODES = 80

# Audited migrate-deck material cards (N, mm, tonne).
MAT_CARDS = """*MATERIAL, NAME=MAT1
*ELASTIC
120000, 0.3
*DENSITY
1.26484805e-08
*MATERIAL, NAME=MAT2
*ELASTIC
120000, 0.3
*DENSITY
8.59881705e-09
*MATERIAL, NAME=MAT3
*ELASTIC
206000, 0.31
*DENSITY
1.01978381e-17
*MATERIAL, NAME=MATPASS
*ELASTIC
206000, 0.31
*DENSITY
1.01978381e-17
"""
AREA_CARRY_MM2 = 22298.692
AREA_GANTRY_MM2 = 8402.9797
GATE_RECT_MM = 98.954535
# Cross-passage triangular truss (drawing MD5): 3 chords phi152x6.
PASS_BOX_W_MM = 1500.0
PASS_BOX_H_MM = 1700.0
PASS_CHORD_AREA_MM2 = 3.0 * math.pi / 4.0 * (152.0**2 - 140.0**2)
PASS_BOX_T_MM = PASS_CHORD_AREA_MM2 / (2.0 * (PASS_BOX_W_MM + PASS_BOX_H_MM))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    parsed = parse_mct(MCT_PATH)
    nodes: dict[int, np.ndarray] = parsed["nodes"]
    elements: dict[int, dict] = parsed["elements"]
    forces_kn: dict[int, float] = parsed["initial_force_kn"]
    constraints: dict[int, str] = parsed["constraints"]
    masses_kg: dict[int, float] = parsed["concentrated_mass_kg"]
    stations = pd.read_csv(STATION_MAP)

    lines: list[str] = []
    push = lines.append
    push("*HEADING")
    push("Double-MCT catwalk, CalculiX 2.21, units N/mm/tonne; two widths y=+-21450 mm")
    push(f"** geometry+prestress source: {MCT_PATH.name} sha256={sha256_file(MCT_PATH)[:16]}...")
    push("** passages: 21 stations from passage_station_authoritative_map.csv (bottom-node beams)")
    push("** conventions follow audited migrate deck 974211b2; no TARGET-FREQ import")

    # --- nodes ---
    push("*NODE, NSET=NALL")
    for width, (noff, ysign) in {"W1": (0, +1.0), "W2": (W2_NODE_OFFSET, -1.0)}.items():
        for nid in sorted(nodes):
            x_m, _, z_m = nodes[nid]
            push(f"{nid + noff}, {x_m * 1000.0:.6f}, {ysign * HALF_SPACING_MM:.1f}, {z_m * 1000.0:.6f}")

    # --- elements per group and width ---
    groups = {"CARRY": [], "GANTRY": [], "GATE": []}
    for eid in sorted(elements):
        el = elements[eid]
        key = {1: "CARRY", 2: "GANTRY", 3: "GATE"}[int(el["material"])]
        groups[key].append(eid)

    for width, (noff, eoff) in {"W1": (0, 0), "W2": (W2_NODE_OFFSET, W2_ELEM_OFFSET)}.items():
        push(f"*ELEMENT, TYPE=B31, ELSET=E_CARRY_{width}")
        for eid in groups["CARRY"]:
            el = elements[eid]
            push(f"{eid + eoff}, {int(el['n1']) + noff}, {int(el['n2']) + noff}")
        push(f"*ELEMENT, TYPE=B31, ELSET=E_GANTRY_{width}")
        for eid in groups["GANTRY"]:
            el = elements[eid]
            push(f"{eid + eoff}, {int(el['n1']) + noff}, {int(el['n2']) + noff}")
        push(f"*ELEMENT, TYPE=B31, ELSET=E_GATE_{width}")
        for eid in groups["GATE"]:
            el = elements[eid]
            push(f"{eid + eoff}, {int(el['n1']) + noff}, {int(el['n2']) + noff}")

    # --- 21 cross-passage bottom beams (W1 bottom node -> W2 bottom node, B31 RECT equivalent) ---
    passage_records = []
    push("*ELEMENT, TYPE=B31, ELSET=E_PASS")
    for k, row in stations.iterrows():
        nb = int(row["mct_bottom_node"])
        eid = PASSAGE_EID0 + k + 1
        push(f"{eid}, {nb}, {nb + W2_NODE_OFFSET}")
        passage_records.append({"passage_id": str(row["passage_id"]), "eid": eid, "bottom_node": nb})

    # --- second-stage mass folded into per-element cable density (bin-quantized) ---
    # Node mass splits half to each adjacent same-chain cable element; end nodes give all
    # to their single segment.  MASS elements are avoided: ccx 2.21 *FREQUENCY,PERTURBATION
    # fails with add_bo_st when TYPE=MASS elements are present (bisected t1/t2/t3).
    mass_nodes = sorted(masses_kg)
    adjacency: dict[int, list[int]] = {}
    for eid in groups["CARRY"] + groups["GANTRY"]:
        el = elements[eid]
        for nid in (int(el["n1"]), int(el["n2"])):
            adjacency.setdefault(nid, []).append(eid)
    elem_extra_t: dict[int, float] = {eid: 0.0 for eid in groups["CARRY"] + groups["GANTRY"]}
    for nid, m_kg in masses_kg.items():
        adj = adjacency.get(nid, [])
        if not adj:
            continue
        share = (m_kg / 1000.0) / len(adj)
        for eid in adj:
            elem_extra_t[eid] += share
    base_density = {1: 1.26484805e-08, 2: 8.59881705e-09}
    area_of = {1: AREA_CARRY_MM2, 2: AREA_GANTRY_MM2}
    elem_density: dict[int, float] = {}
    for eid in groups["CARRY"] + groups["GANTRY"]:
        el = elements[eid]
        mat = int(el["material"])
        p1 = nodes[int(el["n1"])] * 1000.0
        p2 = nodes[int(el["n2"])] * 1000.0
        length = float(np.linalg.norm(p2 - p1))
        elem_density[eid] = base_density[mat] + elem_extra_t[eid] / (area_of[mat] * length)
    # quantize densities into bins (0.05% relative) to bound material-card count
    bins: dict[tuple[int, int], list[int]] = {}
    for eid, rho in elem_density.items():
        mat = int(elements[eid]["material"])
        key = (mat, int(round(math.log(rho / base_density[mat]) / 0.0005)))
        bins.setdefault(key, []).append(eid)
    bin_defs: list[tuple[str, int, float, list[int]]] = []
    for bkey, eids in sorted(bins.items()):
        mat = bkey[0]
        rho = float(np.mean([elem_density[e] for e in eids]))
        name = f"MB{'C' if mat == 1 else 'G'}{len(bin_defs):04d}"
        bin_defs.append((name, mat, rho, eids))

    # --- sections & materials ---
    push(MAT_CARDS.rstrip())
    for name, mat, rho, _ in bin_defs:
        push(f"*MATERIAL, NAME={name}")
        push("*ELASTIC")
        push("120000, 0.3")
        push("*DENSITY")
        push(f"{rho:.9e}")
    for name, mat, rho, eids in bin_defs:
        for width, eoff in {"W1": 0, "W2": W2_ELEM_OFFSET}.items():
            push(f"*ELSET, ELSET=EB_{name}_{width}")
            for eid in eids:
                push(f"{eid + eoff}")
            side = math.sqrt(area_of[mat])
            push(f"*BEAM SECTION, ELSET=EB_{name}_{width}, MATERIAL={name}, SECTION=RECT")
            push(f"{side:.6f}, {side:.6f}")
            push("0, 1, 0")
    for width in ("W1", "W2"):
        push(f"*BEAM SECTION, ELSET=E_GATE_{width}, MATERIAL=MAT3, SECTION=RECT")
        push(f"{GATE_RECT_MM}, {GATE_RECT_MM}")
        push("1, 1, 1")
    # RECT equivalent: area = 3 chords phi152x6 (8256 mm2); depth = truss height 1700 mm.
    pass_rect_a = PASS_CHORD_AREA_MM2 / PASS_BOX_H_MM
    push("*BEAM SECTION, ELSET=E_PASS, MATERIAL=MATPASS, SECTION=RECT")
    push(f"{pass_rect_a:.6f}, {PASS_BOX_H_MM}")
    push("1, 0, 0")

    # --- prestress IC: sigma = F/A along element axis, six global PK2, 8 IPs ---
    push("*INITIAL CONDITIONS, TYPE=STRESS")
    push("** sigma=F_N/A_mm2 from MCT INIFORCE AXIAL; PK2 = sigma n(x)n; 8 integration points")
    ic_count = 0
    for width, (noff, eoff) in {"W1": (0, 0), "W2": (W2_NODE_OFFSET, W2_ELEM_OFFSET)}.items():
        for eid in groups["CARRY"] + groups["GANTRY"]:
            el = elements[eid]
            force_n = forces_kn.get(eid, 0.0) * 1000.0
            if force_n == 0.0:
                continue
            area = AREA_CARRY_MM2 if int(el["material"]) == 1 else AREA_GANTRY_MM2
            sigma = force_n / area
            p1 = nodes[int(el["n1"])] * 1000.0
            p2 = nodes[int(el["n2"])] * 1000.0
            d = p2 - p1
            n = d / np.linalg.norm(d)
            sxx = sigma * n[0] * n[0]
            syy = sigma * n[1] * n[1]
            szz = sigma * n[2] * n[2]
            sxy = sigma * n[0] * n[1]
            sxz = sigma * n[0] * n[2]
            syz = sigma * n[1] * n[2]
            for ip in range(1, 9):
                push(
                    f"{eid + eoff}, {ip}, {sxx:.6e}, {syy:.6e}, {szz:.6e}, {sxy:.6e}, {sxz:.6e}, {syz:.6e}"
                )
            ic_count += 1

    # --- boundaries: MCT constraint masks (translations) per width ---
    push("*BOUNDARY")
    support_nodes = []
    for width, noff in {"W1": 0, "W2": W2_NODE_OFFSET}.items():
        for nid in sorted(constraints):
            mask = str(constraints[nid]).strip()
            for dof in range(1, 4):
                if len(mask) >= dof and mask[dof - 1] == "1":
                    push(f"{nid + noff}, {dof}, {dof}")
            support_nodes.append(nid + noff)
    push("*NSET, NSET=NSUPP")
    for nid in support_nodes:
        push(f"{nid}")

    # --- steps ---
    push("*STEP, NLGEOM, INC=200")
    push("*STATIC")
    push("1.0, 1.0, 1e-6, 1.0")
    push("*DLOAD")
    for width in ("W1", "W2"):
        for elset in (f"E_CARRY_{width}", f"E_GANTRY_{width}", f"E_GATE_{width}"):
            push(f"{elset}, GRAV, {GRAVITY_MM_S2}, 0.0, 0.0, -1.0")
    push(f"E_PASS, GRAV, {GRAVITY_MM_S2}, 0.0, 0.0, -1.0")
    push("*NODE FILE")
    push("U")
    push("*NODE PRINT, NSET=NSUPP, TOTALS=ONLY")
    push("RF")
    push("*END STEP")
    push("*STEP, PERTURBATION")
    push("*FREQUENCY")
    push(f"{MODES}")
    push("*NODE FILE")
    push("U")
    push("*END STEP")

    deck = "\n".join(lines) + "\n"
    deck_path = OUT_DIR / "double_mct_ccx.inp"
    deck_path.write_text(deck, encoding="utf-8")

    # --- mass ledger self check (binned densities as actually emitted) ---
    binned_rho = {}
    for name, mat, rho, eids in bin_defs:
        for eid in eids:
            binned_rho[eid] = rho
    cable_mass_t = 0.0
    base_mass_t = 0.0
    for eid in groups["CARRY"] + groups["GANTRY"]:
        el = elements[eid]
        mat = int(el["material"])
        p1 = nodes[int(el["n1"])] * 1000.0
        p2 = nodes[int(el["n2"])] * 1000.0
        length = float(np.linalg.norm(p2 - p1))
        cable_mass_t += binned_rho[eid] * area_of[mat] * length
        base_mass_t += base_density[mat] * area_of[mat] * length
    cable_mass_t *= 2.0
    base_mass_t *= 2.0
    point_mass_t = cable_mass_t - base_mass_t  # ballast actually carried by densities
    pass_mass_t = 0.0  # gates/passage beams massless by audit convention
    manifest = {
        "deck": str(deck_path),
        "deck_sha256": hashlib.sha256(deck.encode()).hexdigest(),
        "mct_sha256": sha256_file(MCT_PATH),
        "station_map_sha256": sha256_file(STATION_MAP),
        "nodes_per_width": len(nodes),
        "nodes_total": 2 * len(nodes),
        "elements": {
            "carry_per_width": len(groups["CARRY"]),
            "gantry_per_width": len(groups["GANTRY"]),
            "gate_B31_per_width": len(groups["GATE"]),
            "passages": len(passage_records),
            "density_ballast_bins": len(bin_defs),
        },
        "ic_stress_elements_per_width": ic_count // 2,
        "supports_per_width": len(constraints),
        "mass_ledger_t": {
            "cable_self_mass_both_widths": base_mass_t,
            "second_stage_ballast_both_widths": point_mass_t,
            "gates_and_passage_beams": pass_mass_t,
            "total": cable_mass_t,
            "audited_reference_total": 4108.467045,
            "density_bins": len(bin_defs),
        },
        "passage_sections": {
            "box_w_mm": PASS_BOX_W_MM,
            "box_h_mm": PASS_BOX_H_MM,
            "box_t_mm": PASS_BOX_T_MM,
            "chord_area_target_mm2": PASS_CHORD_AREA_MM2,
        },
        "passages": passage_records,
        "steps": ["P1 STATIC NLGEOM gravity+prestress", f"PERTURBATION FREQUENCY {MODES}"],
    }
    (ART_DIR / "fem_model_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps({k: manifest[k] for k in ("nodes_total", "elements", "mass_ledger_t")}, indent=2))
    print("deck bytes:", len(deck))


if __name__ == "__main__":
    main()
