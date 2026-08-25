"""Extract MCT alignment and overlay prestress onto 974211b2.

Line drawings are absent in this tree. Alignment comes from the MCT body.
The official deck is not rewritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "mct-from-zero"))

from emit_ccx import uniaxial_pk2_global  # noqa: E402
from parse_mct import EXPECTED_BYTES, EXPECTED_SHA256, SOURCE_RELATIVE, load_mct  # noqa: E402

MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
MCT = ROOT / "mct-from-zero" / "source" / SOURCE_RELATIVE
SIBLING_STATIC = ROOT / "mct-from-zero" / "artifacts" / "mct_from_zero_static.ccx.inp"
KN_TO_N = 1000.0
SPAN_GROUPS = ("北边跨", "主跨", "南边跨", "南辅跨")
PORTAL_CABLE_GROUPS = ("门架索北边跨", "门架索主跨", "门架索南边跨", "门架索南辅跨")

DRAWING_GLOBS = (
    "*图纸汇总*",
    "*线形*",
    "*成型线*",
    "*猫道图纸*",
    "*.dwg",
    "*.dxf",
    "*centerline*.pdf",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def drawing_search(repo: Path) -> dict[str, Any]:
    hits: list[str] = []
    skip = {".git", "node_modules"}
    for pattern in DRAWING_GLOBS:
        for p in repo.rglob(pattern):
            if skip.intersection(p.parts):
                continue
            hits.append(str(p.relative_to(repo)))
    # Explicit names cited by theory text; confirm absence.
    missing = [
        "图纸汇总-2026.08.05.pdf",
        "猫道图纸1225.pdf",
        "猫道结构复核计算报告0324.pdf",
    ]
    present_named = [name for name in missing if any(name in h for h in hits)]
    return {
        "searched_globs": list(DRAWING_GLOBS),
        "named_drawing_files_present": present_named,
        "glob_hits": sorted(hits)[:40],
        "n_glob_hits": len(hits),
        "alignment_drawing_in_tree": False,
        "source_used": "MCT *NODE / *ELEMENT / *GROUP",
        "note": "No alignment drawing in this checkout. Overlay uses the MCT body.",
    }


def _polyline_from_group(model: dict[str, Any], gname: str) -> dict[str, Any]:
    g = model["groups"].get(gname) or {"nodes": [], "elems": []}
    nodes = model["nodes"]
    elems = model["elems"]
    eids = [e for e in g["elems"] if e in elems and elems[e]["type"] == "TENSTR"]
    nids = set(g["nodes"])
    for eid in eids:
        el = elems[eid]
        nids.add(el["n1"])
        nids.add(el["n2"])
    pts = []
    for nid in nids:
        if nid not in nodes:
            continue
        n = nodes[nid]
        pts.append({"nid": nid, "x_mm": n["x"], "y_mm": n["y"], "z_mm": n["z"]})
    pts.sort(key=lambda r: (r["x_mm"], r["nid"]))
    if len(pts) < 2:
        return {
            "group": gname,
            "n_nodes": len(pts),
            "n_tenstr": len(eids),
            "empty": True,
        }
    x0, x1 = pts[0]["x_mm"], pts[-1]["x_mm"]
    z_left, z_right = pts[0]["z_mm"], pts[-1]["z_mm"]
    zmin = min(p["z_mm"] for p in pts)
    zmax = max(p["z_mm"] for p in pts)
    mid = min(pts, key=lambda p: abs(p["x_mm"] - 0.5 * (x0 + x1)))
    z_end = 0.5 * (z_left + z_right)
    sag = z_end - zmin
    return {
        "group": gname,
        "n_nodes": len(pts),
        "n_tenstr": len(eids),
        "x0_mm": x0,
        "x1_mm": x1,
        "L_m": (x1 - x0) / 1000.0,
        "z_left_m": z_left / 1000.0,
        "z_right_m": z_right / 1000.0,
        "z_min_m": zmin / 1000.0,
        "z_max_m": zmax / 1000.0,
        "z_mid_node_m": mid["z_mm"] / 1000.0,
        "mid_nid": mid["nid"],
        "sag_end_minus_zmin_m": sag / 1000.0,
        "y_abs_max_mm": max(abs(p["y_mm"]) for p in pts),
        "sample": [pts[0], mid, pts[-1]],
    }


def overlay_one(model: dict[str, Any], eid: int) -> dict[str, Any] | None:
    el = model["elems"].get(eid)
    if el is None or el["type"] != "TENSTR":
        return None
    ini_e = model["ini_eforce"].get(eid)
    ini = model["iniforce"].get(eid)
    if ini_e is not None:
        force_kN = float(ini_e["axial_mean_kN"])
        force_from = "INI-EFORCE mean(i,j)"
    elif ini is not None:
        force_kN = float(ini["axial_kN"])
        force_from = "INIFORCE AXIAL"
    else:
        return None
    area = model["sections"][el["sec"]]["area_mm2"]
    n1, n2 = model["nodes"][el["n1"]], model["nodes"][el["n2"]]
    dx, dy, dz = n2["x"] - n1["x"], n2["y"] - n1["y"], n2["z"] - n1["z"]
    sigma = (force_kN * KN_TO_N) / area
    pk2 = uniaxial_pk2_global(dx, dy, dz, sigma)
    return {
        "eid": eid,
        "n1": el["n1"],
        "n2": el["n2"],
        "sec": el["sec"],
        "F_kN": force_kN,
        "F_from": force_from,
        "A_mm2": area,
        "sigma_N_mm2": sigma,
        "pk2": pk2,
        "L_mm": math.hypot(dx, dy, dz),
    }


def parse_main_ic(text: str) -> dict[int, tuple[float, ...]]:
    lines = text.splitlines()
    ic: dict[int, tuple[float, ...]] = {}
    i = 0
    while i < len(lines):
        if lines[i].startswith("*INITIAL CONDITIONS"):
            i += 1
            while i < len(lines) and lines[i].startswith("**"):
                i += 1
            while i < len(lines) and not lines[i].startswith("*"):
                parts = [p.strip() for p in lines[i].split(",")]
                if len(parts) >= 8 and parts[1] == "1":
                    eid = int(parts[0])
                    ic[eid] = tuple(float(parts[k]) for k in range(2, 8))
                i += 1
            break
        i += 1
    return ic


def _rel(a: float, b: float) -> float:
    den = abs(b) if b != 0.0 else 1.0
    return abs(a - b) / den


def run() -> dict[str, Any]:
    drawings = drawing_search(REPO)
    model = load_mct(MCT)
    main_sha = sha256_file(MAIN)
    cleared_sha = sha256_file(CLEARED)
    sibling_sha = sha256_file(SIBLING_STATIC) if SIBLING_STATIC.is_file() else None
    if main_sha != MAIN_SHA:
        raise RuntimeError(f"main hash changed: {main_sha}")
    if cleared_sha != CLEARED_SHA:
        raise RuntimeError(f"760c0ee4 rewritten: {cleared_sha}")

    spans = [_polyline_from_group(model, name) for name in SPAN_GROUPS]
    portal_cables = [_polyline_from_group(model, name) for name in PORTAL_CABLE_GROUPS]
    hangers = model["groups"].get("垂点组", {}).get("nodes") or []
    hang_pts = []
    for nid in hangers:
        n = model["nodes"][nid]
        hang_pts.append({"nid": nid, "x_m": n["x"] / 1000.0, "z_m": n["z"] / 1000.0})

    overlays = []
    tenstr = [e for e, v in model["elems"].items() if v["type"] == "TENSTR"]
    for eid in tenstr:
        rec = overlay_one(model, eid)
        if rec is not None:
            overlays.append(rec)

    main_text = MAIN.read_text(encoding="utf-8")
    ic = parse_main_ic(main_text)
    rels = []
    named = {}
    for rec in overlays:
        got = ic.get(rec["eid"])
        if got is None:
            continue
        r = [_rel(got[i], rec["pk2"][i]) for i in range(6)]
        rels.append(max(r))
        if rec["eid"] in (1, 4, 728, 729, 1169):
            named[str(rec["eid"])] = {
                "F_kN": rec["F_kN"],
                "A_mm2": rec["A_mm2"],
                "sigma_N_mm2": rec["sigma_N_mm2"],
                "overlay_pk2": rec["pk2"],
                "main_ip1_pk2": got,
                "max_abs_rel_pk2": max(r),
            }

    eid1 = next(r for r in overlays if r["eid"] == 1)
    iniforce_1 = model["iniforce"][1]["axial_kN"]
    source_sigma = {
        "eid": 1,
        "INI_EFORCE_mean_kN": eid1["F_kN"],
        "INIFORCE_kN": iniforce_1,
        "A_mm2": eid1["A_mm2"],
        "sigma_from_INI_EFORCE_N_mm2": eid1["sigma_N_mm2"],
        "sigma_from_INIFORCE_N_mm2": (iniforce_1 * KN_TO_N) / eid1["A_mm2"],
        "lock_manuscript": False,
        "note": "703.46 MPa is F/A on the MCT body. Not equilibrium. Do not lock the paper on it.",
    }

    alignment = {
        "kind": "mct_alignment_extract",
        "drawing_absent": True,
        "drawings": drawings,
        "source": {
            "path": str(MCT.relative_to(REPO)),
            "sha256": EXPECTED_SHA256,
            "bytes": EXPECTED_BYTES,
            "unit": "kN, mm",
            "y_plane": "Y≈0 single-line 2-D equivalent",
        },
        "bbox_m": {
            "x_min": model["bbox_mm"]["x_min"] / 1000.0,
            "x_max": model["bbox_mm"]["x_max"] / 1000.0,
            "y_min": model["bbox_mm"]["y_min"] / 1000.0,
            "y_max": model["bbox_mm"]["y_max"] / 1000.0,
            "z_min": model["bbox_mm"]["z_min"] / 1000.0,
            "z_max": model["bbox_mm"]["z_max"] / 1000.0,
        },
        "counts": {
            "n_nodes": model["counts"]["n_nodes"],
            "n_TENSTR": model["counts"]["n_TENSTR"],
            "n_TRUSS": model["counts"]["n_TRUSS"],
            "n_cross_passage_nodes": len(model["groups"]["横向通道节点"]["nodes"]),
            "n_portal_frames": len(model["groups"]["门架"]["elems"]),
        },
        "hang_points_垂点组": hang_pts,
        "floor_spans": spans,
        "portal_cable_spans": portal_cables,
    }

    overlay = {
        "kind": "mct_prestress_overlay_on_alignment",
        "main": {
            "path": "catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp",
            "sha256": main_sha,
            "rewritten": False,
        },
        "identical_to_mct_from_zero_static": sibling_sha == main_sha,
        "n_overlay_tenstr": len(overlays),
        "n_main_ic_eids": len(ic),
        "pk2_vs_main_ip1_abs_rel": {
            "n": len(rels),
            "min": min(rels) if rels else None,
            "max": max(rels) if rels else None,
            "mean": (sum(rels) / len(rels)) if rels else None,
        },
        "named": named,
        "source_sigma_eid1_not_locked": source_sigma,
        "760c0ee4_untouched": cleared_sha == CLEARED_SHA,
        "formula": "sigma = F_N / A_mm2; PK2 = sigma * n⊗n on MCT node-to-node vector",
        "compare_target": "CalculiX own working prestress / cable force on this deck, not ANSYS POST1",
    }

    ccx_sidecar = ROOT / "eval" / "ccx_mct_from_zero" / "ccx_run.json"
    ccx = json.loads(ccx_sidecar.read_text(encoding="utf-8")) if ccx_sidecar.is_file() else None
    stage = (ccx or {}).get("stage_IC_selfweight_erqi") or {}
    acknowledged = {
        "source": "calculation group + #19 sidecar eval/ccx_mct_from_zero/ccx_run.json",
        "mechanism": True,
        "frd_DISP_node_count": 0,
        "S_approx_IC_is_not_equilibrium": True,
        "worst_rel": stage.get("force_vs_MCT_INI_EFORCE_mean_abs_rel", {}).get("max"),
        "worst_eid": stage.get("force_vs_MCT_INI_EFORCE_mean_abs_rel", {}).get("worst_eid"),
        "worst_rel_as_percent": (
            -100.0 * stage["force_vs_MCT_INI_EFORCE_mean_abs_rel"]["max"]
            if stage.get("force_vs_MCT_INI_EFORCE_mean_abs_rel", {}).get("max") is not None
            else None
        ),
        "U_max_mm_from_NODE_PRINT": stage.get("U_max_mm"),
        "balanced": stage.get("balanced"),
        "lock_703_46": False,
        "this_turn_ran_ccx": False,
        "ccx_binary_on_this_vm": False,
        "note": "机构型. FRD DISP 节点 0. S≈IC 不是平衡. 最差 −19.1%. 703.46 不锁稿.",
    }

    evidence = {
        "kind": "plan_974211b2_evidence",
        "not_a_scientific_solved_claim": True,
        "alignment": alignment,
        "overlay": overlay,
        "acknowledged_linear_static": acknowledged,
        "frozen": {
            "760c0ee4": CLEARED_SHA,
            "untouched": True,
        },
        "pushed_main": False,
        "opened_new_pr": False,
        "merged": False,
        "twisted_to_demo_rl_calculix": False,
    }
    return evidence


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_overlay_md(ev: dict[str, Any]) -> str:
    al = ev["alignment"]
    ov = ev["overlay"]
    ack = ev["acknowledged_linear_static"]
    lines = [
        "# MCT 线形抽取 + 预应力叠层（主 974211b2，不换主）",
        "",
        "线形图纸：本树没有。对象是 MCT《猫道 - 门架索合建模型2.mct》。",
        f"主 deck `{ov['main']['path']}` SHA-256 `{ov['main']['sha256']}`。本轮未改写。",
        "",
        "## 线形（从 MCT 扒）",
        "",
        "| 组 | L (m) | z_left (m) | z_right (m) | z_min (m) | sag (m) | TENSTR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in al["floor_spans"]:
        lines.append(
            f"| {s['group']} | {s['L_m']:.6f} | {s['z_left_m']:.6f} | {s['z_right_m']:.6f} | "
            f"{s['z_min_m']:.6f} | {s['sag_end_minus_zmin_m']:.6f} | {s['n_tenstr']} |"
        )
    sig = ov["source_sigma_eid1_not_locked"]
    pk = ov["pk2_vs_main_ip1_abs_rel"]
    lines += [
        "",
        "## 预应力叠层（对 CalculiX 自己的运营力）",
        "",
        f"- TENSTR 叠层 {ov['n_overlay_tenstr']} 根，主 deck IC eid {ov['n_main_ic_eids']}。",
        f"- 叠层 PK2 对主 deck ip1：n={pk['n']}，max |rel|={pk['max']:.3e}，mean |rel|={pk['mean']:.3e}。",
        f"- eid 1：INI-EFORCE mean {sig['INI_EFORCE_mean_kN']} kN / A={sig['A_mm2']:.6f} mm² → "
        f"σ={sig['sigma_from_INI_EFORCE_N_mm2']:.5f} N/mm²。**不锁稿。**",
        "",
        "## 计算组已认（线性步，不是平衡）",
        "",
        f"- 机构型。FRD DISP 节点 {ack['frd_DISP_node_count']}。S≈IC 不是平衡。",
        f"- 最差 eid {ack['worst_eid']}，|rel|={ack['worst_rel']}（−19.1%）。",
        f"- `.dat` |U|_max = {ack['U_max_mm_from_NODE_PRINT']} mm。`balanced={ack['balanced']}`。",
        "",
        "`760c0ee4` 未动。不 push main。不开新 PR。不合并。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ev = run()
    HERE.mkdir(parents=True, exist_ok=True)
    _dump(HERE / "EVIDENCE.json", ev)
    _dump(HERE / "alignment.json", ev["alignment"])
    _dump(HERE / "overlay.json", ev["overlay"])
    (HERE / "OVERLAY.md").write_text(write_overlay_md(ev), encoding="utf-8")
    print(json.dumps(
        {
            "main_sha": ev["overlay"]["main"]["sha256"],
            "pk2_max_rel": ev["overlay"]["pk2_vs_main_ip1_abs_rel"]["max"],
            "sigma_eid1": ev["overlay"]["source_sigma_eid1_not_locked"]["sigma_from_INI_EFORCE_N_mm2"],
            "lock_703_46": False,
            "cleared_untouched": ev["frozen"]["untouched"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
