# -*- coding: utf-8 -*-
"""C20 toppin ROTX: bottom hoop stays ALL, top pin releases ROTX.

Pin axis from CAD MD4-07: cylinder along CAD Y (bridge axis) = ANSYS X.
Previous ROTY toppin / both-end ROTY / both-end free ROTX all failed or
did not activate the in-plane (YZ) portal hinge.
"""
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
PIN_LDOF = "UX,UY,UZ,ROTY,ROTZ"  # release ROTX = pin about ANSYS X
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


def load_top_pairs(coords: dict[int, tuple[float, float, float]]) -> list[dict[str, str]]:
    posts: list[tuple[int, int]] = []
    with ELEMENTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["member"] in ("left_post", "right_post"):
                posts.append((int(row["n1"]), int(row["n2"])))
    if len(posts) != 284:
        raise RuntimeError(f"expected 284 posts, got {len(posts)}")
    src = S10_SOLVER / "apply_finite_gates_and_passages_v2.inp"
    top_slaves: set[int] = set()
    bot_slaves: set[int] = set()
    for n1, n2 in posts:
        if n1 not in coords or n2 not in coords:
            raise RuntimeError(f"missing post node coords {n1}/{n2}")
        if coords[n2][2] >= coords[n1][2]:
            top, bot = n2, n1
        else:
            top, bot = n1, n2
        top_slaves.add(top)
        bot_slaves.add(bot)
    if len(top_slaves) != 284 or len(bot_slaves) != 284:
        raise RuntimeError(f"top={len(top_slaves)} bot={len(bot_slaves)}")
    if top_slaves & bot_slaves:
        raise RuntimeError("top/bottom post node overlap")
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
        if slave in top_slaves:
            rows.append(
                {
                    "master_node": str(master),
                    "slave_node": str(slave),
                    "reason": "top_pin_rotx",
                    "mz": f"{coords[master][2]:.6f}",
                    "sz": f"{coords[slave][2]:.6f}",
                }
            )
    if len(rows) != 284:
        raise RuntimeError(f"expected 284 top ALL CERIG, got {len(rows)}")
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
                    line = (
                        f"CERIG,{key[0]},{key[1]},{PIN_LDOF}  "
                        "! C20 toppin ROTX (pin axis = ANSYS X); bottom hoop stays ALL"
                    )
                    patched += 1
        out.append(line)
    if patched != 284:
        raise RuntimeError(f"patched {patched}")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return patched


def build_main(src: Path, dst: Path, jobname: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace("cw_S10_0716t050342_a4", jobname)
    text = text.replace("S10_LEGACY_COMPLETE", "C20_GATE_TOPPIN_ROTX")
    text = text.replace(
        "S10 LEGACY COMPLETE FULL BRIDGE PRESTRESSED MODAL",
        "C20 GATE TOP PIN ROTX FULL BRIDGE PRESTRESSED MODAL",
    )
    text = text.replace("S10_", "C20_")
    text = text.replace("s10_", "c20_")
    if "NLDIAG,NRRE,ON,50" not in text:
        text = text.replace("NROPT,FULL", "NROPT,FULL\nNLDIAG,NRRE,ON,50", 1)
    header = (
        "! C20 toppin ROTX: 284 upper post CERIG ALL -> UX,UY,UZ,ROTY,ROTZ.\n"
        "! Bottom 284 hoop CERIG stay ALL. Pin axis from MD4-07 CAD = ANSYS X.\n"
        "! ROTY toppin and free ROTX both-ends failed; this is the drawing hinge.\n"
    )
    dst.write_text(header + text, encoding="utf-8")


def write_qa(qa: Path, run_name: str, jobname: str, rows: list[dict[str, str]]) -> None:
    decision = f"""# C20 门架铰链连接裁决（TOPPIN ROTX）

日期：2026-08-27
Run：`{run_name}`  job `{jobname}`

## 销轴方向（已用 CAD 闭合，不再按 ROTX 口头假设）

CAD `build_full_catwalk_from_drawings.py` 坐标：X 横桥、Y 顺桥、Z 竖向。
ANSYS 坐标：X 顺桥、Y 横桥、Z 竖向。

MD4-07 下销 φ75×295：

```
make_cylinder_between(
    ..._lower_support_pin_phi75x295_MD4_07,
    (post_x, y - 147.5, z + 1500),
    (post_x, y + 147.5, z + 1500),
    37.5)
```

圆柱轴线沿 CAD Y = 顺桥 = **ANSYS X**。释放自由度是 **ROTX**，不是 ROTY。
门架平面是 ANSYS YZ，因此该销允许立柱在门架平面内转动。

MD4-03 上端 A 详图销板同样沿 CAD Y 布置，上销轴线同向。

## 本 run 做的连接

- 下端抱箍：284 条立柱底 CERIG 保持 `ALL`（复核：下端另有抱箍，不得做成自由平行四边形）。
- 上端销：284 条立柱顶 CERIG `ALL` → `UX,UY,UZ,ROTY,ROTZ`（只释放 ROTX）。
- 横通道 1386 条 ALL、索 UXYZ 不改。
- 不加 COMBIN14。若静力负主元/不收敛，下一试才在上端加 ROTX 弹簧。

## 已关闭的负证据

| 变体 | 释放 | 结果 |
|---|---|---|
| 两端自由 ROTY | 568 销 | 节点 2027671 UX=6.3e9，XZ 平行四边形机构 |
| 两端自由 ROTX | 568 销 | 节点 2004350 ROTZ 小主元，负主元 |
| 仅上端自由 ROTY | 284 销 | 重力斜坡不收敛，ABT |
| 两端 ROTY + COMBIN14 K=1e8 | 568 | 静力/80 阶通过，TA1 仍 0.07381（错轴） |

## 为何还要再跑 C20

已完成的 C20 SPRING 释放的是 ROTY（错轴），不能激活门架平面内的四端口软模态。
本 run 按图纸销轴做上端 ROTX 铰、下端刚接，才是 C20 的物理闭合。
"""
    (qa / "c20_connection_decision.md").write_text(decision, encoding="utf-8")
    pairs_path = qa / "c20_toppin_rotx_pairs.csv"
    with pairs_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["master_node", "slave_node", "reason", "mz", "sz"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_name = f"C20_HINGES_TOPPIN_ROTX_{stamp}"
    jobname = f"cw_C20x_{stamp[4:8]}t{stamp[9:15]}"
    run_dir = RUNS / run_name
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    lineage = run_dir / "lineage"
    for folder in (solver, qa, lineage):
        folder.mkdir(parents=True, exist_ok=True)
    coords = parse_node_xyz(S10_SOLVER / "apply_finite_gates_and_passages_v2.inp")
    rows = load_top_pairs(coords)
    copied: dict[str, str] = {}
    for name in INCLUDE_NAMES:
        src = S10_SOLVER / name
        dst = solver / name
        if name == "apply_finite_gates_and_passages_v2.inp":
            patch_cerig(src, dst, rows)
        else:
            shutil.copy2(src, dst)
        copied[name] = sha256_file(dst)
    build_main(S10_SOLVER / "s10_section_shear_main.inp", solver / "c20_gate_post_hinges_main.inp", jobname)
    write_qa(qa, run_name, jobname, rows)
    (lineage / "parent.txt").write_text(
        "S10_SECTION_SHEAR_20260716T050342389124Z\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "run_id": "C20_HINGES_TOPPIN_ROTX",
        "run_name": run_name,
        "jobname": jobname,
        "parent": "S10_SECTION_SHEAR_20260716T050342389124Z",
        "pin_axis": "ANSYS X (CAD Y, MD4-07 phi75x295)",
        "released_dof": "ROTX",
        "n_top_pins": 284,
        "n_bottom_all": 284,
        "element_count": 172994,
        "node_count": 109086,
        "include_sha256": copied,
        "main_sha256": sha256_file(solver / "c20_gate_post_hinges_main.inp"),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pointer = (
        f"# C20 当前有效作业\n\n"
        f"请监控：`{run_name}`\n\n"
        f"- Jobname: `{jobname}`\n"
        f"- 284 条立柱顶 CERIG `ALL` → `UX,UY,UZ,ROTY,ROTZ`（释放 ROTX）\n"
        f"- 284 条立柱底 CERIG 保持 `ALL`（下端抱箍）\n"
        f"- 销轴 = ANSYS X（CAD MD4-07 沿顺桥向）\n"
        f"- 横通道 ALL 与索 UXYZ 未改\n"
        f"- 不要再开第二套全桥 ANSYS\n"
    )
    (RUNS / "C20_LATEST.md").write_text(pointer, encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "jobname": jobname}, ensure_ascii=False))


if __name__ == "__main__":
    main()
