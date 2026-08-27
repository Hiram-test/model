# -*- coding: utf-8 -*-
"""D10 from sealed C20 SPRING: replace 4 equivalent downpull LINKs with 32 physical stays."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
C20 = ROOT / "ultra_runs" / "C20_HINGES_SPRING_20260826T221141789051Z" / "solver"
DRAFT = ROOT / "ultra_runs" / "d10_draft" / "apply_d10_physical_downpull.inp"
INCLUDES = [
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_finite_gates_and_passages_v2.inp",
    "apply_c20_post_roty_springs.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_dynamic_mass21_spatialized_v2.inp",
    "apply_authoritative_mct_gravity_v1.inp",
]
C20_JOB = "cw_C20s_0826t221141"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"D10_DOWNPULL_{ts}"
    job = f"cw_D10_{ts[4:8]}t{ts[9:15]}"
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True)
    qa.mkdir()
    for name in INCLUDES:
        shutil.copy2(C20 / name, solver / name)
    down = DRAFT.read_text(encoding="utf-8")
    (solver / "apply_mct_downpull_equivalent_xlong.inp").write_text(down, encoding="utf-8")
    text = (C20 / "c20_gate_post_hinges_main.inp").read_text(encoding="utf-8")
    text = text.replace(C20_JOB, job)
    text = text.replace("C20 GATE HINGE SPRING FULL BRIDGE PRESTRESSED MODAL", "D10 DOWNPULL FROM C20 SPRING FULL BRIDGE PRESTRESSED MODAL")
    text = text.replace("C20_GATE_HINGE_SPRING", "D10_DOWNPULL_FROM_C20")
    text = text.replace("*IF,C20_NCOUNT,NE,109086,THEN", "*IF,D10_NCOUNT,NE,109082,THEN")
    text = text.replace("预期 109086", "预期 109082（去掉4个下压耦合点）")
    text = text.replace("*IF,C20_ECOUNT,NE,173562,THEN", "*IF,D10_ECOUNT,NE,173590,THEN")
    text = text.replace("预期 173562", "预期 173590（-4等效+32物理索，C20弹簧568保留）")
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
    # keep spring include filename
    if "apply_D10_post_roty_springs" in text:
        text = text.replace("apply_D10_post_roty_springs", "apply_c20_post_roty_springs")
    (solver / "d10_downpull_main.inp").write_text(text, encoding="utf-8")
    note = (
        "# D10 from C20 SPRING\n\n"
        "Parent: C20_HINGES_SPRING_20260826T221141789051Z (static pass, 80 modes).\n"
        "C20 TA1 remains 0.07381 Hz (S10 0.07380). Hinges did not activate soft-port stiffness.\n"
        "D10 removes 16-rope CP and attaches 8 LINK180 stays per tower group to alternate bottom ropes.\n"
        "Node 109082, element 173590 = C20 173562 -4 +32.\n"
    )
    (qa / "d10_decision.md").write_text(note, encoding="utf-8")
    status = {
        "run_id": "D10_DOWNPULL",
        "run_name": run_name,
        "jobname": job,
        "parent": "C20_HINGES_SPRING_20260826T221141789051Z",
        "status": "PREPARED_READY_TO_LAUNCH",
        "ncount": 109082,
        "ecount": 173590,
    }
    (run_dir / "D10_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(run_dir)
    print(job)


if __name__ == "__main__":
    main()
