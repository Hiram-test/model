# -*- coding: utf-8 -*-
"""Prepare D10_DOWNPULL from a completed C20 (fallback S10) parent."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
RUNS = ROOT / "ultra_runs"
STAGING = RUNS / "_d10_staging"
D10_INCLUDE = STAGING / "apply_d10_downpull_earplate.inp"
S10 = RUNS / "S10_SECTION_SHEAR_20260716T050342389124Z"

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


def latest_c20() -> Path | None:
    cands = sorted(RUNS.glob("C20_HINGES_*"), key=lambda p: p.name)
    return cands[-1] if cands else None


def find_parent() -> Path:
    c20 = latest_c20()
    if c20 is not None:
        status_path = c20 / "solver" / "c20_gate_status.txt"
        if status_path.is_file():
            text = status_path.read_text(encoding="utf-8", errors="replace")
            if "SOLVER_EXPORT_COMPLETED" in text or "STATIC_GATES_PASSED" in text:
                return c20
        # Prefer C20 patched gates even if still running only when explicitly frozen includes exist.
        if (c20 / "solver" / "apply_finite_gates_and_passages_v2.inp").is_file():
            return c20
    return S10


def build_main(parent_main: Path, dst: Path, jobname: str, parent_is_c20: bool) -> None:
    text = parent_main.read_text(encoding="utf-8")
    if parent_is_c20:
        text = text.replace("cw_C20_0826t213527", jobname)
        text = text.replace("C20_GATE_POST_HINGES", "D10_DOWNPULL_EARPLATE")
        text = text.replace("C20 GATE POST HINGES FULL BRIDGE PRESTRESSED MODAL", "D10 DOWNPULL EARPLATE FULL BRIDGE PRESTRESSED MODAL")
        text = text.replace("C20_", "D10_")
        text = text.replace("c20_", "d10_")
    else:
        text = text.replace("cw_S10_0716t050342_a4", jobname)
        text = text.replace("S10_LEGACY_COMPLETE", "D10_DOWNPULL_EARPLATE")
        text = text.replace("S10 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL", "D10 DOWNPULL EARPLATE FULL BRIDGE PRESTRESSED MODAL")
        text = text.replace("S10_", "D10_")
        text = text.replace("s10_", "d10_")
    needle = "/INPUT,apply_mct_downpull_equivalent_xlong,inp\n"
    insert = (
        needle
        + "! D10：删除非共点下拉 CP，改为下耳板 CERIG,UXYZ。\n"
        + "/INPUT,apply_d10_downpull_earplate,inp\n"
    )
    if needle not in text:
        needle = "/INPUT,apply_mct_downpull_equivalent_xlong,inp\r\n"
        insert = needle + "! D10：删除非共点下拉 CP，改为下耳板 CERIG,UXYZ。\r\n/INPUT,apply_d10_downpull_earplate,inp\r\n"
    if needle not in text:
        raise RuntimeError("cannot find downpull include insertion point")
    if "/INPUT,apply_d10_downpull_earplate,inp" not in text:
        text = text.replace(needle, insert, 1)
    # Topology: +4 MASS21 TYPE74 elements.
    text = text.replace("D10_ECOUNT,NE,172994", "D10_ECOUNT,NE,172998")
    text = text.replace("预期 172994", "预期 172998")
    if "NLDIAG,NRRE,ON,50" not in text:
        text = text.replace("NROPT,FULL", "NROPT,FULL\nNLDIAG,NRRE,ON,50", 1)
    # Insert TYPE74 count after TYPE71 block.
    if "D10_T74" not in text:
        t71_block = (
            "ESEL,S,TYPE,,71\n"
            "! 读取 TYPE 71 单元数，预期 33003。\n"
            "*GET,D10_T71,ELEM,0,COUNT\n"
        )
        extra = (
            t71_block
            + "ESEL,S,TYPE,,74\n"
            "! 读取 TYPE 74 下耳板六自由度微量质量，预期 4。\n"
            "*GET,D10_T74,ELEM,0,COUNT\n"
        )
        if t71_block not in text:
            raise RuntimeError("cannot find TYPE71 count block")
        text = text.replace(t71_block, extra, 1)
        text = text.replace(
            "*VWRITE,D10_T70,D10_T71\n('TYPE70=',F12.0,', TYPE71=',F12.0)",
            "*VWRITE,D10_T70,D10_T71,D10_T74\n('TYPE70=',F12.0,', TYPE71=',F12.0,', TYPE74=',F12.0)",
            1,
        )
        reject = (
            "*IF,D10_T71,NE,33003,THEN\n"
            "! 把本次唯一拒绝原因写入 d10_gate_status.txt，覆盖先前 RUNNING 阶段状态。\n"
            "/OUTPUT,d10_gate_status,txt\n"
            "! 固定拒绝原因 TYPE_71_COUNT_MISMATCH 供外部审计按字段解析。\n"
            "/COM,STATUS=REJECTED REASON=TYPE_71_COUNT_MISMATCH\n"
        )
        t74_reject = (
            reject
            + "*ENDIF\n"
            "! TYPE 74 单元数不等于 4 时拒绝。\n"
            "*IF,D10_T74,NE,4,THEN\n"
            "/OUTPUT,d10_gate_status,txt\n"
            "/COM,STATUS=REJECTED REASON=TYPE_74_COUNT_MISMATCH\n"
            "/OUTPUT\n"
            "/EXIT,NOSAVE\n"
        )
        if reject not in text:
            raise RuntimeError("cannot find TYPE71 reject block")
        text = text.replace(reject, t74_reject, 1)
    header = (
        "! ============================================================================ \n"
        "! D10_DOWNPULL：在 C20 门架销轴边界上，用下耳板 CERIG,UXYZ 替换 12 组下拉 CP。\n"
        "! 4 组等效 LINK180 面积/初应力保持 MCT 728/729；不使用 MPC184。\n"
        "! 单元总数 172998 = S10/C20 的 172994 + 4 个 TYPE74 MASS21。\n"
        "! ============================================================================ \n"
    )
    if not text.startswith("! D10_DOWNPULL") and "D10_DOWNPULL：在 C20" not in text[:800]:
        text = header + text
    dst.write_text(text, encoding="utf-8")


def main() -> None:
    parent = find_parent()
    parent_is_c20 = parent.name.startswith("C20_")
    parent_solver = parent / "solver"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"D10_DOWNPULL_{stamp}"
    jobname = f"cw_D10_{stamp[4:8]}t{stamp[9:15]}"
    run_dir = RUNS / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    lineage = run_dir / "lineage"
    for folder in (solver, qa, lineage):
        folder.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in INCLUDE_NAMES:
        src = parent_solver / name
        if not src.is_file():
            src = S10 / "solver" / name
        shutil.copy2(src, solver / name)
        copied[name] = sha256_file(solver / name)
    shutil.copy2(D10_INCLUDE, solver / "apply_d10_downpull_earplate.inp")
    copied["apply_d10_downpull_earplate.inp"] = sha256_file(solver / "apply_d10_downpull_earplate.inp")
    parent_main = parent_solver / ("c20_gate_post_hinges_main.inp" if parent_is_c20 else "s10_section_shear_main.inp")
    build_main(parent_main, solver / "d10_downpull_main.inp", jobname, parent_is_c20)
    manifest = {
        "schema_version": 1,
        "run_id": "D10_DOWNPULL",
        "run_name": run_name,
        "jobname": jobname,
        "parent_run": parent.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "physical_change": {
            "description": "Replace 12 non-coincident downpull CPs with CERIG UXYZ lower ear plates",
            "cp_deleted": "60000-60011",
            "cerig_uxyz_added": 64,
            "type74_mass21_added": 4,
            "link180_400000_400003_unchanged": True,
            "inistate_unchanged": True,
        },
        "topology_expected": {
            "nodes": 109086,
            "elements": 172998,
            "type4": 73692,
            "type6": 48620,
            "type70": 17679,
            "type71": 33003,
            "type74": 4,
        },
        "include_sha256": copied,
        "main_sha256": sha256_file(solver / "d10_downpull_main.inp"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": jobname, "parent": parent.name}, ensure_ascii=False))


if __name__ == "__main__":
    main()
