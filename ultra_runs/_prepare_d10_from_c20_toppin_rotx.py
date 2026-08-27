# -*- coding: utf-8 -*-
"""D10 physical 32-stay downpull from sealed C20 TOPPIN ROTX."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
C20 = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z" / "solver"
DRAFT = ROOT / "ultra_runs" / "d10_draft" / "apply_d10_physical_downpull.inp"
C20_JOB = "cw_C20x_0827t053427"
INCLUDES = [
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_finite_gates_and_passages_v2.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_dynamic_mass21_spatialized_v2.inp",
    "apply_authoritative_mct_gravity_v1.inp",
]


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"D10_DOWNPULL_{ts}"
    job = f"cw_D10x_{ts[4:8]}t{ts[9:15]}"
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True)
    qa.mkdir()
    for name in INCLUDES:
        shutil.copy2(C20 / name, solver / name)
    (solver / "apply_mct_downpull_equivalent_xlong.inp").write_text(
        DRAFT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    text = (C20 / "c20_gate_post_hinges_main.inp").read_text(encoding="utf-8")
    text = text.replace(C20_JOB, job)
    text = text.replace(
        "C20 GATE TOP PIN ROTX FULL BRIDGE PRESTRESSED MODAL",
        "D10 DOWNPULL FROM C20 TOPPIN ROTX FULL BRIDGE PRESTRESSED MODAL",
    )
    text = text.replace("C20_GATE_TOPPIN_ROTX", "D10_DOWNPULL_FROM_C20_TOPPIN_ROTX")
    text = text.replace("*IF,C20_NCOUNT,NE,109086,THEN", "*IF,D10_NCOUNT,NE,109082,THEN")
    text = text.replace("预期 109086", "预期 109082（去掉4个下压耦合点）")
    text = text.replace("*IF,C20_ECOUNT,NE,172994,THEN", "*IF,D10_ECOUNT,NE,173022,THEN")
    text = text.replace("预期 172994", "预期 173022（-4等效+32物理索）")
    text = text.replace("*IF,C20_T4,NE,73692,THEN", "*IF,D10_T4,NE,73720,THEN")
    text = text.replace("预期 73692", "预期 73720")
    text = text.replace("C20_MEXP=4108.46690758000", "D10_MEXP=4108.63982477003")
    text = text.replace("C20_", "D10_")
    text = text.replace("c20_gate_status", "d10_gate_status")
    text = text.replace("c20_topology_counts", "d10_topology_counts")
    text = text.replace("c20_constraint_equations", "d10_constraint_equations")
    text = text.replace("c20_coupled_dof", "d10_coupled_dof")
    text = text.replace("c20_displacement_constraints", "d10_displacement_constraints")
    text = text.replace("c20_static_energy_mass_reaction", "d10_static_energy_mass_reaction")
    text = text.replace("c20_ls1_energy_history", "d10_ls1_energy_history")
    text = text.replace("c20_modal_export_manifest", "d10_modal_export_manifest")
    text = text.replace("c20_modal_set_list", "d10_modal_set_list")
    text = text.replace("c20_modal_properties", "d10_modal_properties")
    text = text.replace("c20_section_modal_sene", "d10_section_modal_sene")
    header = (
        "! D10 from C20 TOPPIN ROTX: 32 LINK180 stays, remove 12 CP, keep ROTX toppins.\n"
        "! Parent C20 job cw_C20x_0827t053427. Node 109082, element 173022.\n"
    )
    if not text.startswith("! D10 from C20"):
        text = header + text
    (solver / "d10_downpull_main.inp").write_text(text, encoding="utf-8")
    (qa / "d10_decision.md").write_text(
        "# D10 from C20 TOPPIN ROTX\n\n"
        "Parent: C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z\n"
        "32 LINK180 stays SEC/REAL as d10_draft, 12 tower CPs removed.\n"
        "Gate toppins (ROTX) and bottom hoop ALL retained.\n"
        "Node 109082, element 173022 = C20 172994 -4 +32.\n",
        encoding="utf-8",
    )
    status = {
        "run_id": "D10_DOWNPULL",
        "run_name": run_name,
        "jobname": job,
        "parent": "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z",
        "status": "PREPARED_READY_TO_LAUNCH",
        "ncount": 109082,
        "ecount": 173022,
    }
    (run_dir / "D10_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": job}, ensure_ascii=False))


if __name__ == "__main__":
    main()
