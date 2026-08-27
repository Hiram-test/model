# -*- coding: utf-8 -*-
"""E21: same E20 COMBIN14 topology, k=1e4 -> 1e3 N/mm."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
E20 = ROOT / "ultra_runs" / "E20_PASSAGE_SPRINGS_20260827T150412217226Z" / "solver"
E20_JOB = "cw_E20_0827t150412"
K_NEW = 1.0e3
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


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"E21_PASSAGE_SPRINGS_K1E3_{ts}"
    job = f"cw_E21_{ts[4:8]}t{ts[9:15]}"
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True)
    qa.mkdir()
    for name in INCLUDES:
        shutil.copy2(E20 / name, solver / name)
    gates = (E20 / "apply_finite_gates_and_passages_v2.inp").read_text(encoding="utf-8")
    gates = gates.replace("k=1e4 N/mm", "k=1e3 N/mm")
    gates = gates.replace("1.000000e+04", f"{K_NEW:.6e}")
    gates = gates.replace("R,80,10000", f"R,80,{K_NEW:.6e}")
    (solver / "apply_finite_gates_and_passages_v2.inp").write_text(gates, encoding="utf-8")
    main_txt = (E20 / "e20_passage_springs_main.inp").read_text(encoding="utf-8")
    main_txt = main_txt.replace(E20_JOB, job)
    main_txt = main_txt.replace("E20 PASSAGE SPRINGS FROM E10", "E21 PASSAGE SPRINGS K1E3 FROM E20")
    main_txt = main_txt.replace("E20_PASSAGE_SPRINGS_FROM_E10", "E21_PASSAGE_SPRINGS_K1E3_FROM_E20")
    main_txt = main_txt.replace("E20_", "E21_")
    main_txt = main_txt.replace("e20_", "e21_")
    main_txt = main_txt.replace("/INPUT,e21_post1_continue,inp", "/INPUT,e21_post1_continue,inp")
    (solver / "e21_passage_springs_main.inp").write_text(main_txt, encoding="utf-8")
    post = (E20 / "e20_post1_continue.inp").read_text(encoding="utf-8")
    post = post.replace(E20_JOB, job)
    post = post.replace("E20_", "E21_")
    post = post.replace("e20_", "e21_")
    (solver / "e21_post1_continue.inp").write_text(post, encoding="utf-8")
    (qa / "e21_decision.md").write_text(
        "# E21 横通道 COMBIN14 k=1e3\n\n"
        "Parent: E20_PASSAGE_SPRINGS_20260827T150412217226Z (k=1e4, TA1=0.08445 Hz, −15.2%).\n"
        "Same 4158 COMBIN14; k 1e4 → 1e3 N/mm (still >> v5 λ1=3.25).\n"
        "Hypothesis: softer four-port translation further raises TA1 toward 0.0996 Hz.\n"
        "If TA1 falls, 1e4 is nearer the peak and next k is between 1e3 and 1e4.\n",
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
        "$inp = \"e21_passage_springs_main.inp\"\n"
        f"$out = \"cw_e21_{job[7:]}.out\"\n"
        "Write-Host \"cwd=$solver\"\n"
        "Write-Host \"start $(Get-Date -Format o) job=$job E21\"\n"
        "& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out\n"
        "exit $LASTEXITCODE\n"
    )
    (run_dir / "launch_ansys.ps1").write_text(launch, encoding="utf-8")
    status = {
        "run_id": "E21_PASSAGE_SPRINGS_K1E3",
        "run_name": run_name,
        "jobname": job,
        "parent": "E20_PASSAGE_SPRINGS_20260827T150412217226Z",
        "status": "PREPARED_READY_TO_LAUNCH",
        "k_n_per_mm": K_NEW,
        "ncount": 109082,
        "ecount": 177180,
    }
    (run_dir / "E21_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (ROOT / "ultra_runs" / "E21_LATEST.md").write_text(
        f"# E21 指针\n\n`{run_name}` job `{job}`\n\nk=1e3 N/mm COMBIN14. Parent E20 TA1=0.08445 Hz.\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "jobname": job}, ensure_ascii=False))


if __name__ == "__main__":
    main()
