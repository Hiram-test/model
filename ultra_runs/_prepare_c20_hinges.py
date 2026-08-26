# -*- coding: utf-8 -*-
"""Prepare C20_HINGES from sealed S10: pin post-beam CERIG about ANSYS X (ROTX free)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
S10_SOLVER = ROOT / "ultra_runs" / "S10_SECTION_SHEAR_20260716T050342389124Z" / "solver"
CONSTRAINTS = ROOT / "builder" / "generated" / "generated_constraints.csv"
NODES = ROOT / "builder" / "generated" / "generated_nodes.csv"

INCLUDE_FILES = [
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

S10_JOB = "cw_S10_0716t050342_a4"
PIN_LAB = "UXYZ,ROTY,ROTZ"  # keep UX/UY/UZ + ROTY + ROTZ; release ROTX (pin along 顺桥 X)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_post_pairs() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with CONSTRAINTS.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["system"] != "gate" or row["dof_label"] != "ALL":
                continue
            reason = row["reason"]
            if "post" not in reason or "焊接" not in reason:
                raise RuntimeError(f"unexpected gate ALL reason: {reason}")
            end = "bottom" if "下端" in reason else "top" if "上端" in reason else ""
            side = "left" if "left_post" in reason else "right" if "right_post" in reason else ""
            if not end or not side:
                raise RuntimeError(f"cannot parse post end/side: {reason}")
            rows.append(
                {
                    "master_node": row["master_node"],
                    "slave_node": row["slave_node"],
                    "assembly_name": row["assembly_name"],
                    "reason": reason,
                    "end": end,
                    "side": side,
                    "old_dof": "ALL",
                    "new_dof": PIN_LAB,
                    "released": "ROTX",
                    "pin_axis_ansys": "X",
                    "pin_axis_meaning": "顺桥向销轴，释放门架平面(YZ)内相对转动",
                    "drawing": "MD4-07 pin φ75x295 (bottom) / report 4.4-4.5 hinge (top+bottom)",
                    "keep_passage_all": "true",
                }
            )
    if len(rows) != 568:
        raise RuntimeError(f"expected 568 post ALL connections, got {len(rows)}")
    bottoms = sum(1 for r in rows if r["end"] == "bottom")
    tops = sum(1 for r in rows if r["end"] == "top")
    if bottoms != 284 or tops != 284:
        raise RuntimeError(f"bottom/top split {bottoms}/{tops}, expected 284/284")
    return rows


def load_node_xyz() -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    with NODES.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out[row["apdl_node_id"]] = (row["x_mm"], row["y_mm"], row["z_mm"])
    return out


def patch_gates_inp(src: Path, dst: Path, post_rows: list[dict[str, str]]) -> int:
    pairs = {(r["master_node"], r["slave_node"]) for r in post_rows}
    cerig_all = re.compile(r"^CERIG,(\d+),(\d+),ALL\s*$")
    text = src.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    n_post = 0
    n_other_all = 0
    out_lines: list[str] = []
    for line in lines:
        raw = line.split("\n")[0].split("\r")[0]
        m = cerig_all.match(raw)
        if not m:
            out_lines.append(line)
            continue
        master, slave = m.group(1), m.group(2)
        if (master, slave) in pairs:
            nl = "\n" if line.endswith("\n") else ""
            out_lines.append(f"CERIG,{master},{slave},{PIN_LAB}{nl}")
            n_post += 1
        else:
            n_other_all += 1
            out_lines.append(line)
    if n_post != 568:
        raise RuntimeError(f"patched {n_post} post CERIG, expected 568")
    if n_other_all != 1386:
        raise RuntimeError(f"left {n_other_all} non-post CERIG ALL, expected 1386 passage")
    header = (
        "! C20_HINGES: 568 gate post-beam CERIG ALL -> UXYZ,ROTY,ROTZ (release ROTX).\n"
        "! Pin axis = ANSYS X (顺桥). CAD MD4-07 φ75x295 pin is along CAD-Y = ANSYS-X.\n"
        "! Passage-interface 1386 CERIG ALL unchanged. Rope UXYZ unchanged. Keep CERIG, no MPC184.\n"
    )
    dst.write_text(header + "".join(out_lines), encoding="utf-8")
    return n_post


def write_ledger(path: Path, post_rows: list[dict[str, str]], xyz: dict[str, tuple[str, str, str]]) -> None:
    fields = [
        "master_node",
        "slave_node",
        "assembly_name",
        "side",
        "end",
        "old_dof",
        "new_dof",
        "released",
        "pin_axis_ansys",
        "pin_axis_meaning",
        "drawing",
        "master_x_mm",
        "master_y_mm",
        "master_z_mm",
        "slave_x_mm",
        "slave_y_mm",
        "slave_z_mm",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in post_rows:
            mx = xyz.get(r["master_node"], ("", "", ""))
            sx = xyz.get(r["slave_node"], ("", "", ""))
            w.writerow(
                {
                    **{k: r[k] for k in fields if k in r},
                    "master_x_mm": mx[0],
                    "master_y_mm": mx[1],
                    "master_z_mm": mx[2],
                    "slave_x_mm": sx[0],
                    "slave_y_mm": sx[1],
                    "slave_z_mm": sx[2],
                }
            )


def make_main(src: Path, dst: Path, job: str) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    text = text.replace(S10_JOB, job)
    text = text.replace("s10_", "c20_")
    text = text.replace("S10_", "C20_")
    text = text.replace("S10 LEGACY COMPLETE", "C20 HINGES PIN-X FROM S10")
    text = text.replace("S10 LEGACY", "C20 HINGES")
    needle = "NROPT,FULL\n"
    insert = (
        "NROPT,FULL\n"
        "! C20: save up to 50 Newton residual snapshots for divergence diagnosis.\n"
        "NLDIAG,NRRE,ON,50\n"
    )
    if needle not in text:
        raise RuntimeError("NROPT,FULL not found in S10 main")
    text = text.replace(needle, insert, 1)
    dst.write_text(text, encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"C20_HINGES_{ts}"
    job = f"cw_C20_{ts[4:8]}t{ts[9:15]}"  # e.g. cw_C20_0826t214056
    if len(job) > 32:
        raise RuntimeError(f"jobname too long: {job}")
    run_dir = ROOT / "ultra_runs" / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    solver.mkdir(parents=True, exist_ok=False)
    qa.mkdir(parents=True, exist_ok=False)

    post_rows = load_post_pairs()
    xyz = load_node_xyz()

    copied = []
    for name in INCLUDE_FILES:
        src = S10_SOLVER / name
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = solver / name
        if name == "apply_finite_gates_and_passages_v2.inp":
            n = patch_gates_inp(src, dst, post_rows)
            copied.append({"file": name, "action": "copy_and_patch_post_cerig", "patched_post_cerig": n})
        else:
            shutil.copy2(src, dst)
            copied.append({"file": name, "action": "copy_unmodified"})

    write_ledger(qa / "c20_hinge_6dof_ledger.csv", post_rows, xyz)
    make_main(S10_SOLVER / "s10_section_shear_main.inp", solver / "c20_hinges_main.inp", job)

    decision = """# C20 门架铰链连接裁决

## 相对 S10 的单变量

只改 568 条门架立柱—横梁 CERIG：`ALL` → `UXYZ,ROTY,ROTZ`（释放 ROTX）。

不改：CERIG 本身（不换成 MPC184）、1386 条横通道接口 ALL、3124 条索 UXYZ、截面、质量、下压等效、ROTY 稳定点、荷载。

## 销轴方向

CAD `build_full_catwalk_from_drawings.py` 中 MD4-07 下支撑销 φ75×295 为

`(post_x, y-L/2, z+1500)` → `(post_x, y+L/2, z+1500)`。

全线模型 CAD-Y 为顺桥站位，XLong 变换为 `ANSYS_X = CAD_Y`，故销轴 = ANSYS X。
释放 ROTX = 允许立柱相对横梁在门架平面（YZ，横桥—竖向）内转动。

复核报告 4.4 / 4.5：竖杆与上横梁、底梁均为铰链；下端另有抱箍。上销 φ50×110、下销 φ75×295 均在 MD4-07。

## 为何上下都铰、不加交叉撑

1. 图纸与复核报告明确上下铰，不是焊接。S10 的 ALL 是生成器按“焊接偏置”写的，与图不符。
2. 不加 X 撑：MD4-02 斜撑是立柱外侧 22.7° 膝撑，不是两立柱对角撑；用现有四角做 X 撑会人为抬高平面内刚度，偏离 λ1≈3.25 N/mm 的软端口尺度。
3. 静力由索网几何刚度与 NLGEOM 维持。若 LS1 出现负主元或刚体发散，再把上端 284 条改回 ALL（下销保留），而不是改回全部焊接。

## 明确不改的连接

- 横通道顶弦—门架下横梁 1386 条 ALL：C10 诊断已禁止因残差热点改成铰接，本 run 不碰。
- 16+6 索 UXYZ：U 形螺栓/抱箍只传平动，与现语义一致。
"""
    (qa / "c20_connection_decision.md").write_text(decision, encoding="utf-8")

    ansys = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")
    out_file = solver / f"{job}.out"
    main_inp = solver / "c20_hinges_main.inp"
    launch = (
        f"STATUS=PREPARED_NOT_STARTED\n"
        f"RUN_NAME={run_name}\n"
        f"JOBNAME={job}\n"
        f"COMMAND_BEGIN\n"
        f"& '{ansys}' '-b' '-smp' '-np' '4' '-j' '{job}' "
        f"'-dir' '{solver}' '-i' '{main_inp}' '-o' '{out_file}'\n"
        f"COMMAND_END\n"
    )
    (run_dir / "launch_command.txt").write_text(launch, encoding="utf-8")

    hashes = {str(p.relative_to(run_dir)).replace("\\", "/"): sha256_file(p) for p in sorted(run_dir.rglob("*")) if p.is_file()}
    status = {
        "schema_version": 1,
        "run_id": "C20_HINGES",
        "run_name": run_name,
        "jobname": job,
        "parent_run": "S10_SECTION_SHEAR_20260716T050342389124Z",
        "status": "PREPARED_READY_TO_LAUNCH",
        "physical_change_family": "GATE_POST_BEAM_CERIG_ALL_TO_PIN_ABOUT_X",
        "post_cerig_changed": 568,
        "passage_cerig_all_unchanged": 1386,
        "rope_cerig_uxyz_unchanged": 3124,
        "mpc184_used": False,
        "cerig_kept": True,
        "modes_requested": 80,
        "mapdl_started": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "copied_includes": copied,
        "input_hashes": hashes,
    }
    (run_dir / "C20_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_name": run_name, "jobname": job, "parent": "S10_SECTION_SHEAR_20260716T050342389124Z", "files": hashes}, indent=2),
        encoding="utf-8",
    )
    pointer = run_dir / "solver_path.txt"
    pointer.write_text(str(solver), encoding="utf-8")
    print(run_dir)
    print(job)
    print(solver)


if __name__ == "__main__":
    main()
