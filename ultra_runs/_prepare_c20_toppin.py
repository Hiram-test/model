# -*- coding: utf-8 -*-
"""C20 toppin: only upper gate-post CERIG ALL -> pin ROTY-free; bottom stays ALL."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
S10_SOLVER = ROOT / "ultra_runs" / "S10_SECTION_SHEAR_20260716T050342389124Z" / "solver"
CONSTRAINTS = ROOT / "builder" / "generated" / "generated_constraints.csv"
RUNS = ROOT / "ultra_runs"
PIN_LDOF = "UX,UY,UZ,ROTX,ROTZ"
INCLUDE_NAMES = [
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_downpull_equivalent_xlong.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_finite_gates_and_passages_v2.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_dynamic_mass21_spatialized_v2.inp",
    "apply_authoritative_mct_gravity_v1.inp",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_top_pairs(path: Path) -> dict[tuple[int, int], dict[str, str]]:
    pairs: dict[tuple[int, int], dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["system"] != "gate" or row["dof_label"] != "ALL":
                continue
            if "上端" not in row["reason"]:
                continue
            key = (int(row["master_node"]), int(row["slave_node"]))
            pairs[key] = row
    if len(pairs) != 284:
        raise RuntimeError(f"expected 284 top pairs, got {len(pairs)}")
    return pairs


def patch(src: Path, dst: Path, pairs: dict[tuple[int, int], dict[str, str]]) -> dict[str, int]:
    lines = src.read_text(encoding="utf-8").splitlines()
    patched = 0
    leftover_all = 0
    out: list[str] = []
    for line in lines:
        raw = line.split("!", 1)[0].strip()
        if raw.upper().startswith("CERIG,"):
            parts = raw.split(",")
            if len(parts) >= 4 and parts[3].strip().upper() == "ALL":
                key = (int(parts[1]), int(parts[2]))
                if key in pairs:
                    row = pairs[key]
                    line = (
                        f"CERIG,{key[0]},{key[1]},{PIN_LDOF}  "
                        f"! C20 toppin ROTY-free: {row['assembly_name']} {row['reason']}"
                    )
                    patched += 1
                else:
                    leftover_all += 1
        out.append(line)
    if patched != 284:
        raise RuntimeError(f"patched {patched}")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"patched_top_pin": patched, "remaining_all_cerig": leftover_all}


def build_main(src: Path, dst: Path, jobname: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace("cw_S10_0716t050342_a4", jobname)
    text = text.replace("S10_LEGACY_COMPLETE", "C20_GATE_TOP_HINGES")
    text = text.replace("S10 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL", "C20 GATE TOP HINGES FULL BRIDGE PRESTRESSED MODAL")
    text = text.replace("S10_", "C20_")
    text = text.replace("s10_", "c20_")
    if "NLDIAG,NRRE,ON,50" not in text:
        text = text.replace("NROPT,FULL", "NROPT,FULL\nNLDIAG,NRRE,ON,50", 1)
    header = (
        "! C20 toppin: only 284 upper post CERIG ALL -> UX,UY,UZ,ROTX,ROTZ (release ROTY).\n"
        "! Bottom 284 post CERIG stay ALL (hoop). Passage ALL and cable UXYZ unchanged.\n"
        "! Both-end pins were a linear XZ parallelogram mechanism (see failed C20_HINGES_20260826T213527693892Z).\n"
    )
    dst.write_text(header + text, encoding="utf-8")


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"C20_HINGES_TOPPIN_{stamp}"
    jobname = f"cw_C20t_{stamp[4:8]}t{stamp[9:15]}"
    run_dir = RUNS / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    lineage = run_dir / "lineage"
    for folder in (solver, qa, lineage):
        folder.mkdir(parents=True, exist_ok=True)
    pairs = load_top_pairs(CONSTRAINTS)
    copied = {}
    stats = None
    for name in INCLUDE_NAMES:
        src = S10_SOLVER / name
        dst = solver / name
        if name == "apply_finite_gates_and_passages_v2.inp":
            stats = patch(src, dst, pairs)
        else:
            shutil.copy2(src, dst)
        copied[name] = sha256_file(dst)
    build_main(S10_SOLVER / "s10_section_shear_main.inp", solver / "c20_gate_post_hinges_main.inp", jobname)
    with (run_dir / "c20_toppin_ledger.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["master_node", "slave_node", "assembly_name", "reason", "c20_dof"])
        for (m, s), row in sorted(pairs.items()):
            w.writerow([m, s, row["assembly_name"], row["reason"], PIN_LDOF])
    manifest = {
        "schema_version": 1,
        "run_id": "C20_HINGES_TOPPIN",
        "run_name": run_name,
        "jobname": jobname,
        "parent": "S10_SECTION_SHEAR_20260716T050342389124Z",
        "failed_both_end_parent": "C20_HINGES_20260826T213527693892Z",
        "patch_stats": stats,
        "include_sha256": copied,
        "main_sha256": sha256_file(solver / "c20_gate_post_hinges_main.inp"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": jobname, "stats": stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
