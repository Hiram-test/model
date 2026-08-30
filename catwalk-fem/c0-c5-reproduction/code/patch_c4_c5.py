#!/usr/bin/env python3
"""C4: downpull modal Kt~0. C5: tower saddle groove stays, cable-direction k_saddle spring."""
from __future__ import annotations
import hashlib, json, os, re, sys
from collections import defaultdict
from pathlib import Path
EXPECTED_SRC_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"
DOWNPULL_ELSETS = {"CAB122309", "CAB122310", "CAB122311", "CAB122312"}
TOWER_WINDOWS_MM = (
    (650000.0, 670000.0),
    (2930000.0, 2960000.0),
    (3650000.0, 3680000.0),
)
EXPECTED_C5_PAIRS = 96
# Bearing EA from C3 CAB1.. and main-span length from drawings (2960-660 m).
BEARING_EA_N = 1.672401873713e8
L_MAIN_MM = 2.300000e6
K_SADDLE_N_PER_MM = BEARING_EA_N / L_MAIN_MM
SPRING_EID0 = 200000

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

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
                fam = elset.split("_", 1)[0]
                for token in fields[1:]:
                    node_fam[int(token)].add(fam)
    return coords, node_fam

def near_tower(x):
    return any(lo <= x <= hi for lo, hi in TOWER_WINDOWS_MM)

def classify_c5(terms, coords, node_fam):
    nodes = [term[0] for term in terms]
    fams = set()
    for node in nodes:
        fams |= node_fam.get(node, set())
    dofs = {term[1] for term in terms}
    has_ug61 = "UG61" in fams
    has_e = "E" in fams
    has_ug62 = "UG62" in fams
    has_ux = 1 in dofs
    mean_x = sum(coords[node][0] for node in nodes) / len(nodes)
    if has_ug61 and has_ug62:
        return "KEEP", None
    if has_ug61 and has_e and has_ux and near_tower(mean_x):
        e_node = None
        s_node = None
        for node, dof, _coef in terms:
            fam = node_fam.get(node, set())
            if dof == 1 and "E" in fam and "UG61" not in fam:
                e_node = node
            if "UG61" in fam:
                s_node = node
        if e_node is None or s_node is None:
            raise SystemExit(f"C5 pair missing E/UG61 in {terms}")
        return "SPRING_TOWER_UX", (e_node, s_node)
    return "KEEP", None

def write_equation(handle, terms):
    handle.write("*EQUATION\n")
    handle.write(f"{len(terms)}\n")
    chunks = [f"{node}, {dof}, {coef}" for node, dof, coef in terms]
    for i in range(0, len(chunks), 3):
        handle.write(", ".join(chunks[i:i + 3]) + "\n")

def write_springs(handle, pairs):
    handle.write("** C5: groove UY/UZ kept; cable-direction stick-slip spring\n")
    handle.write("*ELEMENT, TYPE=SPRING2, ELSET=E_SADDLE_KS\n")
    for i, (e_node, s_node) in enumerate(pairs, 1):
        handle.write(f"{SPRING_EID0 + i}, {e_node}, {s_node}\n")
    handle.write("*SPRING, ELSET=E_SADDLE_KS\n")
    handle.write("1, 1\n")
    handle.write(f"{K_SADDLE_N_PER_MM:.12e}\n")

def rewrite(src, dst, variant, coords, node_fam):
    stats = {
        "variant": variant,
        "equations_in": 0,
        "keep": 0,
        "drop_tower_saddle_ux": 0,
        "saddle_springs": 0,
        "downpull_ea_n0_zeroed": 0,
        "elements_deleted": 0,
        "k_saddle_N_per_mm": K_SADDLE_N_PER_MM if variant == "C5" else None,
    }
    state = ""
    pending_downpull = False
    eq_needed = 0
    eq_values = []
    pairs = []
    springs_written = False
    with src.open(encoding="utf-8") as handle, dst.open("w", encoding="utf-8", newline="\n") as out:
        for raw in handle:
            stripped = raw.strip()
            upper = stripped.upper()
            if variant == "C5" and upper.startswith("*STEP") and not springs_written:
                write_springs(out, pairs)
                springs_written = True
            if stripped.startswith("*") and not stripped.startswith("**"):
                pending_downpull = False
                if variant == "C4" and upper.startswith("*USER SECTION"):
                    elset_match = re.search(r"ELSET=([^,\s]+)", upper)
                    pending_downpull = bool(elset_match and elset_match.group(1) in DOWNPULL_ELSETS)
                    out.write(raw)
                    continue
                if upper.startswith("*EQUATION"):
                    state = "eqc"
                    continue
                state = ""
                out.write(raw)
                continue
            if pending_downpull:
                fields = [part.strip() for part in stripped.split(",")]
                if len(fields) != 3:
                    raise SystemExit(f"unexpected downpull constants: {stripped}")
                ea, n0, mu = (float(fields[0]), float(fields[1]), float(fields[2]))
                if ea < 1.0e8 or n0 <= 0.0:
                    raise SystemExit(f"downpull constants not the locked C3 values: {stripped}")
                out.write(f"1.000000000000e+00, 0.000000000000e+00, {fields[2]}\n")
                stats["downpull_ea_n0_zeroed"] += 1
                pending_downpull = False
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
                action = "KEEP"
                pair = None
                if variant == "C5":
                    action, pair = classify_c5(terms, coords, node_fam)
                if action == "SPRING_TOWER_UX":
                    stats["drop_tower_saddle_ux"] += 1
                    pairs.append(pair)
                else:
                    write_equation(out, terms)
                    stats["keep"] += 1
                state = "eqc"
                continue
            out.write(raw)
        if variant == "C5" and not springs_written:
            write_springs(out, pairs)
    stats["saddle_springs"] = len(pairs)
    return stats

def main():
    variant = os.environ.get("C45_VARIANT", sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if variant not in {"C4", "C5"}:
        raise SystemExit("C45_VARIANT must be C4 or C5")
    here = Path(__file__).resolve().parent
    repo_root = here.parent if here.name == "code" else here
    src = Path(os.environ.get("C3_SRC", repo_root / "solver" / "c3_ub_frozen_tangent_diag" / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"))
    if not src.is_file():
        raise SystemExit(f"missing source deck: {src}")
    src_sha = sha256_file(src)
    if src_sha != EXPECTED_SRC_SHA256:
        raise SystemExit(f"source SHA mismatch: {src_sha}")
    coords, node_fam = first_pass(src)
    out_dir = Path(os.environ.get("C3_OUT", repo_root / "artifacts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{variant}-UB-FT14_m14.inp"
    stats = rewrite(src, dst, variant, coords, node_fam)
    if variant == "C4" and stats["downpull_ea_n0_zeroed"] != 4:
        raise SystemExit(f"C4 must zero exactly 4 downpull sections, got {stats['downpull_ea_n0_zeroed']}")
    if variant == "C5" and stats["saddle_springs"] != EXPECTED_C5_PAIRS:
        raise SystemExit(f"C5 must write exactly {EXPECTED_C5_PAIRS} k_saddle springs, got {stats['saddle_springs']}")
    dst_sha = sha256_file(dst)
    receipt = {
        "schema": "catwalk.c4-c5.official-scheme.v4",
        "variant": variant,
        "source": {"path": src.name, "sha256": src_sha},
        "output": {"path": dst.name, "sha256": dst_sha, "bytes": dst.stat().st_size},
        "rule": {
            "C4": "C3 plus downpull modal tangent ~0: EA->1 N, N0->0 on 4 E_DOWNPULL UCAB3; mu unchanged",
            "C5": "C3 plus tower-saddle slip WITH finite k_saddle=EA/L_main on UX springs; groove UY/UZ kept; anchors sticky; no friction contact",
        }[variant],
        "k_saddle": {
            "formula": "EA_bearing / L_main",
            "EA_N": BEARING_EA_N,
            "L_main_mm": L_MAIN_MM,
            "k_N_per_mm": K_SADDLE_N_PER_MM,
        } if variant == "C5" else None,
        "friction": False,
        "contact": False,
        "bare_slip": False,
        "back_tuned_to_0_0996": False,
        "stats": stats,
    }
    (out_dir / f"{variant}_PATCH.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"event": f"{variant}_PATCHED", "dst": str(dst), "dst_sha256": dst_sha, **{k: v for k, v in stats.items() if k != "k_saddle_N_per_mm"}, "k_saddle_N_per_mm": stats["k_saddle_N_per_mm"]}, sort_keys=True))

if __name__ == "__main__":
    main()
