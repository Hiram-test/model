#!/usr/bin/env python3
"""C3 drawing topology: passage UXYZ + saddle GAPUNI contact."""
from __future__ import annotations
import hashlib, json, os, re
from collections import defaultdict
from pathlib import Path
CROSS_Y_MM = 15000.0
EXPECTED_SRC_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"
PASSAGE_FAM = ("UG63", "UG64", "UG65", "UG66", "UXL", "UXS")
KN_N_PER_MM = 1.0e6
KT_N_PER_MM = 1.0e4
GAP_CLEARANCE = 0.0
FIRST_GAP_EID = 300001
FIRST_FRIC_EID = 400001

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def family(elset):
    return elset.split("_", 1)[0]

def first_pass(src):
    coords = {}
    node_fam = defaultdict(set)
    state = ""
    elset = ""
    with src.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("**"):
                continue
            if line.startswith("*"):
                upper = line.upper()
                state = ""
                if upper.startswith("*NODE") and "FILE" not in upper:
                    state = "node"
                elif upper.startswith("*ELEMENT"):
                    state = "element"
                    elset = re.search(r"ELSET=([^,\s]+)", upper).group(1)
                continue
            if state == "node":
                fields = [part.strip() for part in line.split(",")]
                coords[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))
            elif state == "element":
                fields = [part.strip() for part in line.split(",") if part.strip()]
                fam = family(elset)
                for token in fields[1:]:
                    node_fam[int(token)].add(fam)
    return coords, node_fam

def classify_equation(terms, coords, node_fam):
    nodes = [term[0] for term in terms]
    ys = [coords[node][1] for node in nodes]
    dy = abs(max(ys) - min(ys))
    fams = set()
    for node in nodes:
        fams |= node_fam.get(node, set())
    dofs = {term[1] for term in terms}
    has_passage = any(fam in fams for fam in PASSAGE_FAM)
    has_rot = any(dof >= 4 for dof in dofs)
    has_ux = 1 in dofs
    has_uy = 2 in dofs
    has_uz = 3 in dofs
    has_cable = "E" in fams
    has_ug61 = "UG61" in fams
    has_ug62 = "UG62" in fams
    is_bottom_hoop = has_ug61 and has_ug62
    is_saddle = has_cable and (has_ug61 or has_ug62) and not is_bottom_hoop
    if dy >= CROSS_Y_MM:
        return "DROP_CROSS_Y"
    if is_bottom_hoop:
        return "KEEP"
    if has_passage and has_rot:
        return "HINGE_UXYZ"
    if is_saddle and has_uy and not has_ux and not has_uz:
        return "HINGE_UXYZ"
    if is_saddle and (has_ux or has_uz or (has_rot and not has_uy)):
        return "SADDLE_TO_CONTACT"
    return "KEEP"

def hinge_terms(terms):
    by_dof = defaultdict(list)
    for node, dof, coef in terms:
        by_dof[dof].append((node, dof, coef))
    kept = []
    for dof in (1, 2, 3):
        group = by_dof.get(dof, [])
        if len(group) >= 2:
            kept.extend(group[:2])
        elif len(group) == 1 and abs(group[0][2]) > 0:
            nodes = []
            for node, _, _ in terms:
                if node not in nodes:
                    nodes.append(node)
            if len(nodes) >= 2:
                kept.append((nodes[0], dof, 1.0))
                kept.append((nodes[1], dof, -1.0))
    seen = set()
    unique = []
    for item in kept:
        key = (item[0], item[1])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique if len(unique) >= 2 else []

def write_equation(handle, terms):
    handle.write("*EQUATION\n")
    handle.write(f"{len(terms)}\n")
    chunks = [f"{node}, {dof}, {coef}" for node, dof, coef in terms]
    for i in range(0, len(chunks), 3):
        handle.write(", ".join(chunks[i:i + 3]) + "\n")

def collect_saddle_pairs(src, coords, node_fam):
    pairs = {}
    state = ""
    eq_needed = 0
    eq_values = []
    with src.open(encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            upper = stripped.upper()
            if stripped.startswith("*") and not stripped.startswith("**"):
                if upper.startswith("*EQUATION"):
                    state = "eqc"
                    continue
                state = ""
                continue
            if state == "eqc":
                if stripped.startswith("**") or stripped.startswith("*"):
                    state = ""
                    continue
                nterms = int(stripped.split(",", 1)[0])
                eq_needed = nterms * 3
                eq_values = []
                state = "eqt"
                continue
            if state == "eqt":
                eq_values.extend(part.strip() for part in stripped.split(",") if part.strip())
                if len(eq_values) < eq_needed:
                    continue
                terms = [(int(eq_values[i]), int(eq_values[i + 1]), float(eq_values[i + 2])) for i in range(0, eq_needed, 3)]
                if classify_equation(terms, coords, node_fam) == "SADDLE_TO_CONTACT":
                    nodes = tuple(sorted(set(term[0] for term in terms)))
                    if len(nodes) == 2:
                        pairs[nodes] = True
                state = "eqc"
    return list(pairs)

def write_contact(handle, pairs, coords):
    handle.write("** drawing saddle contact: GAPUNI normal + frictional tangent penalty\n")
    handle.write("*ELEMENT, TYPE=GAPUNI, ELSET=E_SADDLE_GAP\n")
    for i, (a, b) in enumerate(pairs):
        za = coords[a][2]
        zb = coords[b][2]
        upper, lower = (a, b) if za >= zb else (b, a)
        handle.write(f"{FIRST_GAP_EID + i}, {upper}, {lower}\n")
    handle.write("*GAP, ELSET=E_SADDLE_GAP\n")
    handle.write(f"{GAP_CLEARANCE:.6f}, 0., 0., -1., , {KN_N_PER_MM:.6e}, 1.\n")
    handle.write("*ELEMENT, TYPE=SPRING2, ELSET=E_SADDLE_FRIC\n")
    for i, (a, b) in enumerate(pairs):
        handle.write(f"{FIRST_FRIC_EID + i}, {a}, {b}\n")
    handle.write("*SPRING, ELSET=E_SADDLE_FRIC\n")
    handle.write("1, 1\n")
    handle.write(f"{KT_N_PER_MM:.6e}\n")

def rewrite(src, dst, coords, node_fam):
    stats = {
        "equations_in": 0,
        "keep": 0,
        "drop_cross_y": 0,
        "hinge_rewritten": 0,
        "hinge_dropped_pure_rot": 0,
        "saddle_to_contact": 0,
        "saddle_pairs": 0,
        "elements_deleted": 0,
    }
    pairs = collect_saddle_pairs(src, coords, node_fam)
    stats["saddle_pairs"] = len(pairs)
    state = ""
    eq_needed = 0
    eq_values = []
    with src.open(encoding="utf-8") as handle, dst.open("w", encoding="utf-8", newline="\n") as out:
        for raw in handle:
            stripped = raw.strip()
            upper = stripped.upper()
            if stripped.startswith("*") and not stripped.startswith("**"):
                if upper.startswith("*STEP"):
                    write_contact(out, pairs, coords)
                    out.write(raw)
                    state = ""
                    continue
                if upper.startswith("*EQUATION"):
                    state = "eqc"
                    continue
                state = ""
                out.write(raw)
                continue
            if state == "eqc":
                if stripped.startswith("**") or stripped.startswith("*"):
                    state = ""
                    out.write(raw)
                    continue
                stats["equations_in"] += 1
                nterms = int(stripped.split(",", 1)[0])
                eq_needed = nterms * 3
                eq_values = []
                state = "eqt"
                continue
            if state == "eqt":
                eq_values.extend(part.strip() for part in stripped.split(",") if part.strip())
                if len(eq_values) < eq_needed:
                    continue
                terms = [(int(eq_values[i]), int(eq_values[i + 1]), float(eq_values[i + 2])) for i in range(0, eq_needed, 3)]
                action = classify_equation(terms, coords, node_fam)
                if action == "DROP_CROSS_Y":
                    stats["drop_cross_y"] += 1
                elif action == "SADDLE_TO_CONTACT":
                    stats["saddle_to_contact"] += 1
                elif action == "HINGE_UXYZ":
                    hinged = hinge_terms(terms)
                    if hinged:
                        write_equation(out, hinged)
                        stats["hinge_rewritten"] += 1
                    else:
                        stats["hinge_dropped_pure_rot"] += 1
                else:
                    write_equation(out, terms)
                    stats["keep"] += 1
                state = "eqc"
                continue
            out.write(raw)
    return stats

def main():
    here = Path(__file__).resolve().parent
    repo_root = here.parent if here.name == "code" else here
    src = Path(os.environ.get("C3_SRC", repo_root / "solver" / "c3_ub_frozen_tangent_diag" / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"))
    if not src.is_file():
        fallback = here / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"
        src = fallback if fallback.is_file() else src
    if not src.is_file():
        raise SystemExit(f"missing source deck: {src}")
    src_sha = sha256_file(src)
    if src_sha != EXPECTED_SRC_SHA256:
        raise SystemExit(f"source SHA mismatch: {src_sha}")
    coords, node_fam = first_pass(src)
    default_out = repo_root / "artifacts" if (repo_root / "artifacts").is_dir() else here
    out_dir = Path(os.environ.get("C3_OUT", default_out))
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "C3-UB-FT14-DRAW-TOPO_m14.inp"
    stats = rewrite(src, dst, coords, node_fam)
    if stats["elements_deleted"] != 0:
        raise SystemExit("refusing member deletion")
    if stats["saddle_pairs"] < 1:
        raise SystemExit("no saddle contact pairs")
    dst_sha = sha256_file(dst)
    receipt = {
        "schema": "catwalk.c3-ub-ft14.draw-topology.v5-contact",
        "source": {"path": src.name, "sha256": src_sha, "bytes": src.stat().st_size},
        "output": {"path": dst.name, "sha256": dst_sha, "bytes": dst.stat().st_size},
        "rule": {
            "passage": "UXYZ hinge",
            "saddle_normal": "GAPUNI closed contact kn=1e6 N/mm",
            "saddle_tangent": "SPRING2 UX friction penalty kt=1e4 N/mm",
            "saddle_groove": "keep UY",
            "keep": "284 bottom-hoop ALL, all members",
            "e20_e21_springs": False,
            "back_tuned_to_0_0996": False,
            "members_deleted": 0,
        },
        "stats": stats,
        "frequency_claim": False,
    }
    (out_dir / "C3_DRAW_TOPO_PATCH.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"event": "C3_DRAW_TOPO_PATCHED", "dst": str(dst), "dst_sha256": dst_sha, **stats}, sort_keys=True))

if __name__ == "__main__":
    main()
