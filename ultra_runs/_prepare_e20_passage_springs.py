# -*- coding: utf-8 -*-
"""E20: replace 1386 passage CERIG UXYZ with COMBIN14 UX/UY/UZ springs.

Parent E10. Keep toppin ROTX, bottom hoop ALL, 32 stays, cable UXYZ.
k=1e4 N/mm per DOF: finite so passage-gate ports can have relative translation
instead of being slaved to one gate master. Not a calibration of v5 lambda1.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
E10 = ROOT / "ultra_runs" / "E10_PASSAGE_UXYZ_20260827T125824870359Z" / "solver"
E10_JOB = "cw_E10_0827t125824"
K_N_PER_MM = 1.0e3
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


def convert_passage_uxyz_to_springs(src: Path, dst: Path) -> dict[str, int]:
    lines = src.read_text(encoding="utf-8").splitlines()
    pairs: list[tuple[int, int]] = []
    out: list[str] = []
    n_keep = 0
    for line in lines:
        raw = line.split("!", 1)[0].strip()
        if raw.upper().startswith("CERIG,") and "E10 four-port" in line:
            parts = [p.strip() for p in raw.split(",")]
            pairs.append((int(parts[1]), int(parts[2])))
            continue
        out.append(line)
        if raw.upper().startswith("CERIG,"):
            n_keep += 1
    if len(pairs) != 1386:
        raise RuntimeError(f"passage UXYZ pairs {len(pairs)}, expected 1386")
    block = [
        "",
        "! E20: 1386 passage UXYZ CERIG -> COMBIN14 UX/UY/UZ, k=1e4 N/mm",
        "ET,80,COMBIN14",
        "KEYOPT,80,2,1",
        "ET,81,COMBIN14",
        "KEYOPT,81,2,2",
        "ET,82,COMBIN14",
        "KEYOPT,82,2,3",
        f"R,80,{K_N_PER_MM:.6e}",
        f"R,81,{K_N_PER_MM:.6e}",
        f"R,82,{K_N_PER_MM:.6e}",
        "EID=500000",
    ]
    for master, slave in pairs:
        block += [
            "TYPE,80",
            "REAL,80",
            f"EN,EID,{master},{slave}",
            "EID=EID+1",
            "TYPE,81",
            "REAL,81",
            f"EN,EID,{master},{slave}",
            "EID=EID+1",
            "TYPE,82",
            "REAL,82",
            f"EN,EID,{master},{slave}",
            "EID=EID+1",
        ]
    block.append("ALLSEL,ALL")
    # insert before FINISH if present else append
    text = "\n".join(out)
    if text.rstrip().endswith("FINISH"):
        text = text.rstrip()[: -len("FINISH")].rstrip() + "\n" + "\n".join(block) + "\nFINISH\n"
    else:
        text = text.rstrip() + "\n" + "\n".join(block) + "\n"
    dst.write_text(text, encoding="utf-8")
    return {"passage_springs": len(pairs), "cerig_kept": n_keep, "combin14": len(pairs) * 3}


def build_main(src: Path, dst: Path, job: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace(E10_JOB, job)
    text = text.replace(
        "E10 PASSAGE UXYZ FROM D10 FULL BRIDGE PRESTRESSED MODAL",
        "E20 PASSAGE SPRINGS FROM E10 FULL BRIDGE PRESTRESSED MODAL",
    )
    text = text.replace("E10_PASSAGE_UXYZ_FROM_D10", "E20_PASSAGE_SPRINGS_FROM_E10")
    text = text.replace("*IF,E10_ECOUNT,NE,173022,THEN", "*IF,E20_ECOUNT,NE,177180,THEN")
    text = text.replace("预期 173022", "预期 177180（+4158 COMBIN14）")
    text = text.replace("E10_", "E20_")
    text = text.replace("e10_gate_status", "e20_gate_status")
    text = text.replace("e10_topology_counts", "e20_topology_counts")
    text = text.replace("e10_constraint_equations", "e20_constraint_equations")
    text = text.replace("e10_coupled_dof", "e20_coupled_dof")
    text = text.replace("e10_displacement_constraints", "e20_displacement_constraints")
    text = text.replace("e10_static_energy_mass_reaction", "e20_static_energy_mass_reaction")
    text = text.replace("e10_ls1_energy_history", "e20_ls1_energy_history")
    text = text.replace("e10_modal_export_manifest", "e20_modal_export_manifest")
    text = text.replace("e10_modal_set_list", "e20_modal_set_list")
    text = text.replace("e10_modal_properties", "e20_modal_properties")
    text = text.replace("e10_section_modal_sene", "e20_section_modal_sene")
    text = text.replace("/INPUT,e10_post1_continue,inp", "/INPUT,e20_post1_continue,inp")
    header = (
        "! E20 from E10: 1386 passage UXYZ CERIG -> COMBIN14 UX/UY/UZ k=1e4 N/mm.\n"
        "! Keep toppin ROTX, bottom hoop ALL, 32 stays, cable UXYZ.\n"
    )
    dst.write_text(header + text, encoding="utf-8")


def write_post1(src: Path, dst: Path, job: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace("cw_E10_0827t125824", job)
    text = text.replace("E10_", "E20_")
    text = text.replace("e10_", "e20_")
    dst.write_text(text, encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tag = "E21" if abs(K_N_PER_MM - 1.0e3) < 1e-6 else "E20"
    run_name = f"{tag}_PASSAGE_SPRINGS_{ts}"
    job = f"cw_{tag}_{ts[4:8]}t{ts[9:15]}"
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True)
    qa.mkdir()
    for name in INCLUDES:
        shutil.copy2(E10 / name, solver / name)
    counts = convert_passage_uxyz_to_springs(
        E10 / "apply_finite_gates_and_passages_v2.inp",
        solver / "apply_finite_gates_and_passages_v2.inp",
    )
    build_main(E10 / "e10_passage_uxyz_main.inp", solver / "e20_passage_springs_main.inp", job)
    write_post1(E10 / "e10_post1_continue.inp", solver / "e20_post1_continue.inp", job)
    (qa / "e20_decision.md").write_text(
        "# E20 横通道四端口 COMBIN14\n\n"
        "Parent: E10_PASSAGE_UXYZ_20260827T125824870359Z\n"
        f"Replace {counts['passage_springs']} passage UXYZ CERIG with "
        f"{counts['combin14']} COMBIN14 (UX/UY/UZ), k={K_N_PER_MM:.0e} N/mm.\n"
        "Hypothesis: UXYZ still slaves all ports to one gate master, so ALL→UXYZ "
        "could not admit four-port relative translation. Finite springs let the "
        "passage beams deform instead of being short-circuited.\n"
        "Expected elements 177180 = 173022 + 4158. Nodes 109082 unchanged.\n",
        encoding="utf-8",
    )
    status = {
        "run_id": "E20_PASSAGE_SPRINGS",
        "run_name": run_name,
        "jobname": job,
        "parent": "E10_PASSAGE_UXYZ_20260827T125824870359Z",
        "status": "PREPARED_READY_TO_LAUNCH",
        "ncount": 109082,
        "ecount": 177180,
        "k_n_per_mm": K_N_PER_MM,
        "cerig": counts,
    }
    (run_dir / "E20_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (ROOT / "ultra_runs" / "E20_LATEST.md").write_text(
        f"# E20 指针\n\n`{run_name}` job `{job}`\n\n"
        f"- 1386×3 COMBIN14 k=1e4 N/mm 替换横通道 UXYZ\n"
        f"- 父线 E10；节点 109082，单元 177180\n"
        f"- 启动：该 run 目录 launch_ansys.ps1\n",
        encoding="utf-8",
    )
    launch = (
        "$ErrorActionPreference = \"Stop\"\n"
        "$root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$solver = Join-Path $root \"solver\"\n"
        "Set-Location $solver\n"
        "$tmp = \"D:\\ANSYS_TMP\"\n"
        "if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }\n"
        "$env:TEMP = $tmp\n"
        "$env:TMP = $tmp\n"
        f"$lock = Join-Path $solver \"{job}.lock\"\n"
        "if (Test-Path $lock) { Remove-Item $lock -Force }\n"
        "$exe = \"D:\\ANSYS2026\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe\"\n"
        f"$job = \"{job}\"\n"
        "$inp = \"e20_passage_springs_main.inp\"\n"
        f"$out = \"cw_e20_{job[7:]}.out\"\n"
        "Write-Host \"cwd=$solver\"\n"
        "Write-Host \"start $(Get-Date -Format o) job=$job E20\"\n"
        "& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out\n"
        "$code = $LASTEXITCODE\n"
        "Write-Host \"exit=$code end $(Get-Date -Format o)\"\n"
        "exit $code\n"
    )
    (run_dir / "launch_ansys.ps1").write_text(launch, encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": job, "cerig": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
