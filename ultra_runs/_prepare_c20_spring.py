# -*- coding: utf-8 -*-
"""C20 regularized hinges: 568 post CERIG pin + COMBIN14 ROTY springs."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
S10_SOLVER = ROOT / "ultra_runs" / "S10_SECTION_SHEAR_20260716T050342389124Z" / "solver"
ELEMENTS = ROOT / "builder" / "generated" / "generated_elements.csv"
RUNS = ROOT / "ultra_runs"
PIN_LDOF = "UX,UY,UZ,ROTX,ROTZ"
K_ROTY = 1.0e8  # N*mm/rad; ~0.4 of RHS160 post EI/L, regularizes XZ parallelogram
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


def load_pairs() -> list[dict[str, str]]:
    post_nodes: set[int] = set()
    with ELEMENTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["member"] in ("left_post", "right_post"):
                post_nodes.add(int(row["n1"]))
                post_nodes.add(int(row["n2"]))
    if len(post_nodes) != 568:
        raise RuntimeError(f"expected 568 post end nodes, got {len(post_nodes)}")
    src = S10_SOLVER / "apply_finite_gates_and_passages_v2.inp"
    rows: list[dict[str, str]] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        raw = line.split("!", 1)[0].strip()
        if not raw.upper().startswith("CERIG,"):
            continue
        parts = raw.split(",")
        if len(parts) < 4 or parts[3].strip().upper() != "ALL":
            continue
        master = int(parts[1])
        slave = int(parts[2])
        if slave in post_nodes:
            rows.append({"master_node": str(master), "slave_node": str(slave), "reason": "post_end"})
    if len(rows) != 568:
        raise RuntimeError(f"expected 568 post ALL CERIG, got {len(rows)}")
    return rows


def patch_cerig(src: Path, dst: Path, rows: list[dict[str, str]]) -> int:
    keys = {(int(r["master_node"]), int(r["slave_node"])) for r in rows}
    lines = src.read_text(encoding="utf-8").splitlines()
    patched = 0
    out = []
    for line in lines:
        raw = line.split("!", 1)[0].strip()
        if raw.upper().startswith("CERIG,"):
            parts = raw.split(",")
            if len(parts) >= 4 and parts[3].strip().upper() == "ALL":
                key = (int(parts[1]), int(parts[2]))
                if key in keys:
                    line = f"CERIG,{key[0]},{key[1]},{PIN_LDOF}  ! C20 pin + ROTY spring"
                    patched += 1
        out.append(line)
    if patched != 568:
        raise RuntimeError(f"patched {patched}")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return patched


def write_springs(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "! C20: COMBIN14 ROTY springs at 568 gate-post pins.",
        f"! K={K_ROTY:.6e} N*mm/rad about global Y. CERIG already released ROTY.",
        "/PREP7",
        "ET,75,COMBIN14",
        "KEYOPT,75,2,5",
        f"R,75001,{K_ROTY:.6e}",
        "TYPE,75",
        "REAL,75001",
    ]
    eid = 401000
    for row in rows:
        m = int(row["master_node"])
        s = int(row["slave_node"])
        lines.append(f"EN,{eid},{m},{s}")
        eid += 1
    if eid - 401000 != 568:
        raise RuntimeError("spring count")
    lines.extend(["ALLSEL,ALL", "FINISH", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_main(src: Path, dst: Path, jobname: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace("cw_S10_0716t050342_a4", jobname)
    text = text.replace("S10_LEGACY_COMPLETE", "C20_GATE_HINGE_SPRING")
    text = text.replace("S10 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL", "C20 GATE HINGE SPRING FULL BRIDGE PRESTRESSED MODAL")
    text = text.replace("S10_", "C20_")
    text = text.replace("s10_", "c20_")
    insert_after = "/INPUT,apply_finite_gates_and_passages_v2,inp\n"
    extra = insert_after + "/INPUT,apply_c20_post_roty_springs,inp\n"
    if insert_after not in text:
        raise RuntimeError("missing finite gates include")
    if "/INPUT,apply_c20_post_roty_springs,inp" not in text:
        text = text.replace(insert_after, extra, 1)
    text = text.replace("*IF,C20_ECOUNT,NE,172994,THEN", "*IF,C20_ECOUNT,NE,173562,THEN")
    text = text.replace("预期 172994", "预期 173562")
    t71 = (
        "ESEL,S,TYPE,,71\n"
        "! 读取 TYPE 71 单元数，预期 33003。\n"
        "*GET,C20_T71,ELEM,0,COUNT\n"
    )
    if t71 in text:
        text = text.replace(
            t71,
            t71
            + "ESEL,S,TYPE,,75\n"
            "! 读取 TYPE 75 COMBIN14 销轴弹簧，预期 568。\n"
            "*GET,C20_T75,ELEM,0,COUNT\n",
            1,
        )
    text = text.replace(
        "*VWRITE,C20_T70,C20_T71\n('TYPE70=',F12.0,', TYPE71=',F12.0)",
        "*VWRITE,C20_T70,C20_T71,C20_T75\n('TYPE70=',F12.0,', TYPE71=',F12.0,', TYPE75=',F12.0)",
        1,
    )
    if "NLDIAG,NRRE,ON,50" not in text:
        text = text.replace("NROPT,FULL", "NROPT,FULL\nNLDIAG,NRRE,ON,50", 1)
    header = (
        "! C20 hinge springs: 568 post CERIG pin (release ROTY) + COMBIN14 K=1e8 N*mm/rad.\n"
        "! Free both-end pins and free toppins diverged (XZ parallelogram). Springs regularize.\n"
    )
    dst.write_text(header + text, encoding="utf-8")


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"C20_HINGES_SPRING_{stamp}"
    jobname = f"cw_C20s_{stamp[4:8]}t{stamp[9:15]}"
    run_dir = RUNS / run_name
    solver = run_dir / "solver"
    for folder in (solver, run_dir / "qa", run_dir / "lineage"):
        folder.mkdir(parents=True, exist_ok=True)
    rows = load_pairs()
    copied = {}
    for name in INCLUDE_NAMES:
        src = S10_SOLVER / name
        dst = solver / name
        if name == "apply_finite_gates_and_passages_v2.inp":
            patch_cerig(src, dst, rows)
        else:
            shutil.copy2(src, dst)
        copied[name] = sha256_file(dst)
    write_springs(solver / "apply_c20_post_roty_springs.inp", rows)
    copied["apply_c20_post_roty_springs.inp"] = sha256_file(solver / "apply_c20_post_roty_springs.inp")
    build_main(S10_SOLVER / "s10_section_shear_main.inp", solver / "c20_gate_post_hinges_main.inp", jobname)
    manifest = {
        "schema_version": 1,
        "run_id": "C20_HINGES_SPRING",
        "run_name": run_name,
        "jobname": jobname,
        "k_roty_Nmm_per_rad": K_ROTY,
        "n_springs": 568,
        "n_pin_cerig": 568,
        "element_count": 173562,
        "include_sha256": copied,
        "main_sha256": sha256_file(solver / "c20_gate_post_hinges_main.inp"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": jobname}, ensure_ascii=False))


if __name__ == "__main__":
    main()
