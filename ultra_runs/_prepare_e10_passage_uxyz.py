# -*- coding: utf-8 -*-
"""E10: release 1386 passage CERIG ALL -> UXYZ, keep D10 parent physics.

Parent: D10_DOWNPULL_20260827T075458947752Z
Keep: 284 toppin ROTX, 284 bottom hoop ALL, 32 physical downpull stays, 3124 cable UXYZ.
Change: remaining 1386 CERIG ALL (cross-passage / four-port) -> UXYZ
        so relative rotation can enter the antisymmetric roll.
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
D10 = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z" / "solver"
ELEMENTS = ROOT / "builder" / "generated" / "generated_elements.csv"
D10_JOB = "cw_D10x_0827t075458"
INCLUDES = [
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_downpull_equivalent_xlong.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_dynamic_mass21_spatialized_v2.inp",
    "apply_authoritative_mct_gravity_v1.inp",
]


def parse_node_xyz(src: Path) -> dict[int, tuple[float, float, float]]:
    coords: dict[int, tuple[float, float, float]] = {}
    with src.open(encoding="utf-8") as handle:
        for line in handle:
            raw = line.split("!", 1)[0].strip()
            if not raw.upper().startswith("N,"):
                continue
            parts = raw.split(",")
            if len(parts) < 5:
                continue
            try:
                nid = int(parts[1])
                xyz = (float(parts[2]), float(parts[3]), float(parts[4]))
            except ValueError:
                continue
            coords[nid] = xyz
    return coords


def bottom_post_slaves(coords: dict[int, tuple[float, float, float]]) -> set[int]:
    posts: list[tuple[int, int]] = []
    with ELEMENTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["member"] in ("left_post", "right_post"):
                posts.append((int(row["n1"]), int(row["n2"])))
    if len(posts) != 284:
        raise RuntimeError(f"expected 284 posts, got {len(posts)}")
    bots: set[int] = set()
    for n1, n2 in posts:
        if n1 not in coords or n2 not in coords:
            raise RuntimeError(f"missing post node {n1}/{n2}")
        bot = n1 if coords[n1][2] <= coords[n2][2] else n2
        bots.add(bot)
    if len(bots) != 284:
        raise RuntimeError(f"bottom slaves {len(bots)}")
    return bots


def patch_passage_cerig(src: Path, dst: Path, bot_slaves: set[int]) -> dict[str, int]:
    lines = src.read_text(encoding="utf-8").splitlines()
    n_all = n_keep_bot = n_pass = n_toppin = n_uxyz = 0
    out = []
    for line in lines:
        raw = line.split("!", 1)[0].strip()
        if not raw.upper().startswith("CERIG,"):
            out.append(line)
            continue
        parts = [p.strip() for p in raw.split(",")]
        dof = ",".join(p.upper() for p in parts[3:])
        if dof == "UX,UY,UZ,ROTY,ROTZ":
            n_toppin += 1
            out.append(line)
            continue
        if dof == "UXYZ":
            n_uxyz += 1
            out.append(line)
            continue
        if dof != "ALL":
            out.append(line)
            continue
        n_all += 1
        slave = int(parts[2])
        if slave in bot_slaves:
            n_keep_bot += 1
            out.append(line)
            continue
        n_pass += 1
        out.append(
            f"CERIG,{parts[1]},{parts[2]},UXYZ  "
            "! E10 four-port: passage ALL -> UXYZ; bottom hoop stays ALL"
        )
    if n_keep_bot != 284:
        raise RuntimeError(f"kept bottom ALL {n_keep_bot}, expected 284")
    if n_toppin != 284:
        raise RuntimeError(f"toppin {n_toppin}, expected 284")
    if n_pass != 1386:
        raise RuntimeError(f"passage patched {n_pass}, expected 1386")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {
        "all_before": n_all,
        "bottom_all_kept": n_keep_bot,
        "passage_to_uxyz": n_pass,
        "toppin": n_toppin,
        "cable_uxyz": n_uxyz,
    }


def build_main(src: Path, dst: Path, job: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace(D10_JOB, job)
    text = text.replace(
        "D10 DOWNPULL FROM C20 TOPPIN ROTX FULL BRIDGE PRESTRESSED MODAL",
        "E10 PASSAGE UXYZ FROM D10 FULL BRIDGE PRESTRESSED MODAL",
    )
    text = text.replace("D10_DOWNPULL_FROM_C20_TOPPIN_ROTX", "E10_PASSAGE_UXYZ_FROM_D10")
    text = text.replace("D10_", "E10_")
    text = text.replace("d10_gate_status", "e10_gate_status")
    text = text.replace("d10_topology_counts", "e10_topology_counts")
    text = text.replace("d10_constraint_equations", "e10_constraint_equations")
    text = text.replace("d10_coupled_dof", "e10_coupled_dof")
    text = text.replace("d10_displacement_constraints", "e10_displacement_constraints")
    text = text.replace("d10_static_energy_mass_reaction", "e10_static_energy_mass_reaction")
    text = text.replace("d10_ls1_energy_history", "e10_ls1_energy_history")
    text = text.replace("d10_modal_export_manifest", "e10_modal_export_manifest")
    text = text.replace("d10_modal_set_list", "e10_modal_set_list")
    text = text.replace("d10_modal_properties", "e10_modal_properties")
    text = text.replace("d10_section_modal_sene", "e10_section_modal_sene")
    text = text.replace("/INPUT,d10_post1_continue,inp", "/INPUT,e10_post1_continue,inp")
    header = (
        "! E10 from D10: 1386 passage CERIG ALL -> UXYZ. Keep toppin ROTX, bottom hoop ALL,\n"
        "! 32 physical downpull stays. Four-port relative rotation may enter TA roll.\n"
    )
    if not text.startswith("! E10 from D10"):
        text = header + text
    dst.write_text(text, encoding="utf-8")


def write_post1(src: Path, dst: Path, job: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace("cw_D10x_0827t075458", job)
    text = text.replace("D10_", "E10_")
    text = text.replace("d10_", "e10_")
    dst.write_text(text, encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"E10_PASSAGE_UXYZ_{ts}"
    job = f"cw_E10_{ts[4:8]}t{ts[9:15]}"
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True)
    qa.mkdir()
    for name in INCLUDES:
        shutil.copy2(D10 / name, solver / name)
    coords = parse_node_xyz(D10 / "apply_finite_gates_and_passages_v2.inp")
    bots = bottom_post_slaves(coords)
    counts = patch_passage_cerig(
        D10 / "apply_finite_gates_and_passages_v2.inp",
        solver / "apply_finite_gates_and_passages_v2.inp",
        bots,
    )
    build_main(D10 / "d10_downpull_main.inp", solver / "e10_passage_uxyz_main.inp", job)
    write_post1(D10 / "d10_post1_continue.inp", solver / "e10_post1_continue.inp", job)
    mxp = (D10 / "d10_mxpand_then_post1.inp").read_text(encoding="utf-8")
    mxp = mxp.replace("cw_D10x_0827t075458", job)
    mxp = mxp.replace("d10_", "e10_")
    mxp = mxp.replace("D10 ", "E10 ")
    (solver / "e10_mxpand_then_post1.inp").write_text(mxp, encoding="utf-8")
    (qa / "e10_decision.md").write_text(
        "# E10 横通道四端口 UXYZ\n\n"
        "Parent: D10_DOWNPULL_20260827T075458947752Z\n"
        "Keep 284 toppin ROTX, 284 bottom hoop ALL, 32 LINK180 downpull stays.\n"
        f"Patch {counts['passage_to_uxyz']} passage CERIG ALL -> UXYZ.\n"
        "Hypothesis: ALL rigid arms at 21-station four-ports block antisymmetric roll "
        "from seeing kappa_soft; UXYZ lets relative rotation enter TA1.\n"
        "Node/element counts unchanged vs D10: 109082 / 173022.\n",
        encoding="utf-8",
    )
    launch = (
        "$ErrorActionPreference = \"Stop\"\n"
        "$solver = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) \"solver\"\n"
        "Set-Location $solver\n"
        f"$exe = \"D:\\ANSYS2026\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe\"\n"
        f"$job = \"{job}\"\n"
        "$inp = \"e10_passage_uxyz_main.inp\"\n"
        f"$out = \"cw_e10_{job[7:]}.out\"\n"
        "Write-Host \"cwd=$solver\"\n"
        "Write-Host \"start $(Get-Date -Format o) job=$job E10\"\n"
        "& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out\n"
        "$code = $LASTEXITCODE\n"
        "Write-Host \"exit=$code end $(Get-Date -Format o)\"\n"
        "exit $code\n"
    )
    (run_dir / "launch_ansys.ps1").write_text(launch, encoding="utf-8")
    status = {
        "run_id": "E10_PASSAGE_UXYZ",
        "run_name": run_name,
        "jobname": job,
        "parent": "D10_DOWNPULL_20260827T075458947752Z",
        "status": "PREPARED_WAIT_D10_POST1",
        "ncount": 109082,
        "ecount": 173022,
        "cerig": counts,
    }
    (run_dir / "E10_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (ROOT / "ultra_runs" / "E10_LATEST.md").write_text(
        f"# E10 指针\n\n已准备、**尚未启动**（D10 MXPAND+POST1 占用 ANSYS）：\n\n"
        f"`{run_name}` job `{job}`\n\n"
        f"- 父线 D10 TOPPIN ROTX + 32 索\n"
        f"- 1386 条横通道 CERIG ALL → UXYZ\n"
        f"- 284 底抱箍 ALL、284 上销 ROTX 不改\n"
        f"- 启动：该 run 目录 `launch_ansys.ps1`\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "jobname": job, "cerig": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
