#!/usr/bin/env python3
"""C4: drop 4 equalizer UCOR6 actuators. C5: drop UG61-E pure ROT weld only."""
from __future__ import annotations
import hashlib, json, os, re, sys
from collections import defaultdict
from pathlib import Path
EXPECTED_SRC_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"
EQ_ELSET = "E_EQUALIZER_ROT_ACT"

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def first_pass(src):
    coords_y = {}
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
                coords_y[int(fields[0])] = float(fields[2])
            elif state == "element":
                fields = [part.strip() for part in line.split(",") if part.strip()]
                fam = elset.split("_", 1)[0]
                for token in fields[1:]:
                    node_fam[int(token)].add(fam)
                    if elset.startswith("E_"):
                        node_fam[int(token)].add(elset)
    return coords_y, node_fam

def classify_c5(terms, node_fam):
    fams = set()
    for node, _, _ in terms:
        fams |= node_fam.get(node, set())
    dofs = {term[1] for term in terms}
    has_trans = any(dof <= 3 for dof in dofs)
    has_rot = any(dof >= 4 for dof in dofs)
    has_e = "E" in fams or "E_BEARING" in fams
    has_ug61 = "UG61" in fams
    has_ug62 = "UG62" in fams
    if has_ug61 and has_ug62:
        return "KEEP"
    if has_e and has_ug61 and has_rot and not has_trans:
        return "DROP_SADDLE_PURE_ROT"
    return "KEEP"

def write_equation(handle, terms):
    handle.write("*EQUATION\n")
    handle.write(f"{len(terms)}\n")
    chunks = [f"{node}, {dof}, {coef}" for node, dof, coef in terms]
    for i in range(0, len(chunks), 3):
        handle.write(", ".join(chunks[i:i + 3]) + "\n")

def rewrite(src, dst, variant, node_fam):
    stats = {
        "variant": variant,
        "equations_in": 0,
        "keep": 0,
        "drop_saddle_pure_rot": 0,
        "elements_deleted": 0,
        "equalizer_ucor6_deleted": 0,
    }
    state = ""
    skip_element = False
    skip_section = False
    eq_needed = 0
    eq_values = []
    with src.open(encoding="utf-8") as handle, dst.open("w", encoding="utf-8", newline="\n") as out:
        for raw in handle:
            stripped = raw.strip()
            upper = stripped.upper()
            if stripped.startswith("*") and not stripped.startswith("**"):
                skip_element = False
                skip_section = False
                if variant == "C4" and upper.startswith("*ELEMENT") and f"ELSET={EQ_ELSET}" in upper:
                    skip_element = True
                    stats["equalizer_ucor6_deleted_header"] = stats.get("equalizer_ucor6_deleted_header", 0) + 1
                    continue
                if variant == "C4" and upper.startswith("*USER SECTION") and f"ELSET={EQ_ELSET}" in upper:
                    skip_section = True
                    continue
                if upper.startswith("*EQUATION"):
                    state = "eqc"
                    continue
                state = ""
                out.write(raw)
                continue
            if skip_element:
                stats["equalizer_ucor6_deleted"] += 1
                stats["elements_deleted"] += 1
                continue
            if skip_section:
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
                if variant == "C5":
                    action = classify_c5(terms, node_fam)
                if action == "DROP_SADDLE_PURE_ROT":
                    stats["drop_saddle_pure_rot"] += 1
                else:
                    write_equation(out, terms)
                    stats["keep"] += 1
                state = "eqc"
                continue
            out.write(raw)
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
    _coords_y, node_fam = first_pass(src)
    out_dir = Path(os.environ.get("C3_OUT", repo_root / "artifacts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{variant}-UB-FT14_m14.inp"
    stats = rewrite(src, dst, variant, node_fam)
    if variant == "C4" and stats["equalizer_ucor6_deleted"] != 4:
        raise SystemExit(f"C4 must delete exactly 4 equalizer UCOR6, got {stats['equalizer_ucor6_deleted']}")
    if variant == "C5" and stats["drop_saddle_pure_rot"] < 1:
        raise SystemExit("C5 dropped no saddle pure-ROT equations")
    dst_sha = sha256_file(dst)
    receipt = {
        "schema": "catwalk.c4-c5.v1",
        "variant": variant,
        "source": {"path": src.name, "sha256": src_sha},
        "output": {"path": dst.name, "sha256": dst_sha, "bytes": dst.stat().st_size},
        "rule": {
            "C4": "delete 4 E_EQUALIZER_ROT_ACT UCOR6 only; keep sticky saddles and passages",
            "C5": "drop UG61-E pure ROT weld only; keep hoops, equalizers, translation levers",
        }[variant],
        "friction": False,
        "contact": False,
        "back_tuned_to_0_0996": False,
        "stats": stats,
    }
    (out_dir / f"{variant}_PATCH.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"event": f"{variant}_PATCHED", "dst": str(dst), "dst_sha256": dst_sha, **stats}, sort_keys=True))

if __name__ == "__main__":
    main()
