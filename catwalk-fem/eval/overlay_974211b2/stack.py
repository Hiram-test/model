"""Stack MCT alignment onto locked main 974211b2. Does not rewrite the inp."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "eval" / "plan_974211b2"))
sys.path.insert(0, str(ROOT / "mct-from-zero"))

from emit_ccx import _axial_kN_for_elem, _dof_flags, uniaxial_pk2_global  # noqa: E402
from overlay import (  # noqa: E402
    CLEARED,
    CLEARED_SHA,
    KN_TO_N,
    MAIN,
    MAIN_SHA,
    MCT,
    PORTAL_CABLE_GROUPS,
    SPAN_GROUPS,
    parse_main_ic,
    parse_main_nodes,
    sha256_file,
)
from parse_mct import EXPECTED_SHA256, load_mct  # noqa: E402


def parse_main_elems(text: str) -> dict[int, dict[str, Any]]:
    elems: dict[int, dict[str, Any]] = {}
    typ = None
    for line in text.splitlines():
        if line.startswith("*ELEMENT"):
            typ = "T3D2" if "T3D2" in line else "B31" if "B31" in line else None
            continue
        if line.startswith("*"):
            typ = None
            continue
        if typ is None or not line.strip():
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 3:
            eid = int(parts[0])
            elems[eid] = {"eid": eid, "type": typ, "n1": int(parts[1]), "n2": int(parts[2])}
    return elems


def parse_main_boundary(text: str) -> set[tuple[int, int]]:
    rows: set[tuple[int, int]] = set()
    on = False
    for line in text.splitlines():
        if line.startswith("*BOUNDARY"):
            on = True
            continue
        if on and line.startswith("*") and not line.startswith("**"):
            break
        if not on or line.startswith("**") or not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            rows.add((int(parts[0]), int(parts[1])))
    return rows


def parse_main_cload(text: str) -> dict[tuple[int, int], float]:
    loads: dict[tuple[int, int], float] = {}
    on = False
    for line in text.splitlines():
        if line.startswith("*CLOAD"):
            on = True
            continue
        if on and line.startswith("*"):
            break
        if not on or not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            loads[(int(parts[0]), int(parts[1]))] = float(parts[2])
    return loads


def expected_boundary(model: dict[str, Any]) -> set[tuple[int, int]]:
    rows: set[tuple[int, int]] = set()
    already_uy: set[int] = set()
    for c in model["constraints"]:
        dofs = _dof_flags(c["dof"])
        if 2 in dofs:
            already_uy.update(c["nodes"])
        for nid in c["nodes"]:
            for d in dofs:
                rows.add((nid, d))
    for nid in model["nodes"]:
        if nid not in already_uy:
            rows.add((nid, 2))
    return rows


def expected_cload(model: dict[str, Any]) -> dict[tuple[int, int], float]:
    loads: dict[tuple[int, int], float] = {}
    for rec in model["conload_erqi"]:
        for dof, key in ((1, "fx_kN"), (2, "fy_kN"), (3, "fz_kN")):
            val = rec[key] * KN_TO_N
            if abs(val) >= 1e-12:
                loads[(rec["nid"], dof)] = val
    return loads


def _rel(a: float, b: float) -> float:
    return abs(a - b) / (abs(b) if b != 0.0 else 1.0)


def polyline(model: dict[str, Any], gname: str) -> dict[str, Any]:
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
        n = nodes[nid]
        pts.append((nid, n["x"], n["z"]))
    pts.sort(key=lambda p: (p[1], p[0]))
    forces = []
    for eid in eids:
        f, src = _axial_kN_for_elem(model, eid)
        if f is not None:
            forces.append(f)
    return {
        "group": gname,
        "n_pts": len(pts),
        "n_tenstr": len(eids),
        "x0_m": pts[0][1] / 1000.0 if pts else None,
        "x1_m": pts[-1][1] / 1000.0 if pts else None,
        "z_min_m": min(p[2] for p in pts) / 1000.0 if pts else None,
        "z_max_m": max(p[2] for p in pts) / 1000.0 if pts else None,
        "F_kN": {
            "n": len(forces),
            "min": min(forces) if forces else None,
            "max": max(forces) if forces else None,
        },
        "pts_m": [{"nid": n, "x": x / 1000.0, "z": z / 1000.0} for n, x, z in pts],
        "eids": eids,
    }


def write_svg(polylines: list[dict[str, Any]], path: Path) -> None:
    xs = [p["x"] for pl in polylines for p in pl["pts_m"]]
    zs = [p["z"] for pl in polylines for p in pl["pts_m"]]
    xmin, xmax = min(xs), max(xs)
    zmin, zmax = min(zs), max(zs)
    pad = 40
    w, h = 1100, 280
    dx = xmax - xmin or 1.0
    dz = zmax - zmin or 1.0

    def xy(x: float, z: float) -> tuple[float, float]:
        return (
            pad + (x - xmin) / dx * (w - 2 * pad),
            h - pad - (z - zmin) / dz * (h - 2 * pad),
        )

    colors = ("#1d4ed8", "#b45309", "#15803d", "#be123c")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="12" y="18" font-size="12" font-family="sans-serif">'
        "MCT alignment on 974211b2 (X–Z, m). Main not rewritten.</text>",
    ]
    for i, pl in enumerate(polylines):
        pts = pl["pts_m"]
        if len(pts) < 2:
            continue
        d = "M " + " L ".join(f"{xy(p['x'], p['z'])[0]:.2f},{xy(p['x'], p['z'])[1]:.2f}" for p in pts)
        c = colors[i % len(colors)]
        parts.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="1.4"/>')
        tx, ty = xy(pts[0]["x"], pts[0]["z"])
        parts.append(
            f'<text x="{tx:.1f}" y="{ty - 6:.1f}" font-size="10" fill="{c}" font-family="sans-serif">{pl["group"]}</text>'
        )
    parts.append("</svg>\n")
    path.write_text("".join(parts), encoding="utf-8")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    main_sha = sha256_file(MAIN)
    cleared_sha = sha256_file(CLEARED)
    if main_sha != MAIN_SHA:
        raise RuntimeError(f"main rewritten: {main_sha}")
    if cleared_sha != CLEARED_SHA:
        raise RuntimeError(f"760c0ee4 rewritten: {cleared_sha}")

    model = load_mct(MCT)
    text = MAIN.read_text(encoding="utf-8")
    main_nodes = parse_main_nodes(text)
    main_elems = parse_main_elems(text)
    main_ic = parse_main_ic(text)
    main_bc = parse_main_boundary(text)
    main_cload = parse_main_cload(text)

    node_miss = 0
    reprint_miss = 0
    for nid, n in model["nodes"].items():
        got = main_nodes.get(nid)
        if got is None:
            node_miss += 1
            continue
        printed = (float(f"{n['x']:.8g}"), float(f"{n['y']:.8g}"), float(f"{n['z']:.8g}"))
        if printed != got:
            reprint_miss += 1

    elem_miss = 0
    type_miss = 0
    for eid, el in model["elems"].items():
        want = "T3D2" if el["type"] == "TENSTR" else "B31" if el["type"] == "TRUSS" else None
        got = main_elems.get(eid)
        if got is None:
            elem_miss += 1
            continue
        if got["n1"] != el["n1"] or got["n2"] != el["n2"]:
            elem_miss += 1
        if got["type"] != want:
            type_miss += 1

    ic_miss = 0
    ic_rel = []
    for eid, el in model["elems"].items():
        if el["type"] != "TENSTR":
            continue
        rec_f, _src = _axial_kN_for_elem(model, eid)
        area = model["sections"][el["sec"]]["area_mm2"]
        if rec_f is None or area is None:
            ic_miss += 1
            continue
        n1, n2 = model["nodes"][el["n1"]], model["nodes"][el["n2"]]
        sigma = (rec_f * KN_TO_N) / area
        pk2 = uniaxial_pk2_global(n2["x"] - n1["x"], n2["y"] - n1["y"], n2["z"] - n1["z"], sigma)
        got = main_ic.get(eid)
        if got is None:
            ic_miss += 1
            continue
        ic_rel.append(max(_rel(got[i], pk2[i]) for i in range(6)))

    want_bc = expected_boundary(model)
    want_cl = expected_cload(model)
    bc_extra = main_bc - want_bc
    bc_missing = want_bc - main_bc
    cl_keys_extra = set(main_cload) - set(want_cl)
    cl_keys_missing = set(want_cl) - set(main_cload)
    cl_rel = []
    for k, v in want_cl.items():
        if k in main_cload:
            cl_rel.append(_rel(main_cload[k], v))

    floor = [polyline(model, name) for name in SPAN_GROUPS]
    portal = [polyline(model, name) for name in PORTAL_CABLE_GROUPS]

    stack = {
        "kind": "mct_alignment_stack_on_974211b2",
        "main_sha256": main_sha,
        "main_rewritten": False,
        "cleared_760c0ee4": cleared_sha,
        "cleared_untouched": True,
        "mct_sha256": EXPECTED_SHA256,
        "nodes": {
            "n_mct": len(model["nodes"]),
            "n_main": len(main_nodes),
            "missing": node_miss,
            "reprint_miss": reprint_miss,
        },
        "elems": {
            "n_mct": len(model["elems"]),
            "n_main": len(main_elems),
            "connectivity_miss": elem_miss,
            "type_miss": type_miss,
        },
        "prestress_ic": {
            "n": len(ic_rel),
            "missing": ic_miss,
            "max_abs_rel": max(ic_rel) if ic_rel else None,
        },
        "boundary": {
            "n_main": len(main_bc),
            "n_expected": len(want_bc),
            "missing": len(bc_missing),
            "extra": len(bc_extra),
        },
        "cload_erqi": {
            "n_main": len(main_cload),
            "n_expected": len(want_cl),
            "missing": len(cl_keys_missing),
            "extra": len(cl_keys_extra),
            "max_abs_rel": max(cl_rel) if cl_rel else None,
        },
        "floor_spans": [
            {k: pl[k] for k in pl if k not in {"pts_m", "eids"}} | {"n_pts": pl["n_pts"]}
            for pl in floor
        ],
        "portal_cable_spans": [
            {k: pl[k] for k in pl if k not in {"pts_m", "eids"}} | {"n_pts": pl["n_pts"]}
            for pl in portal
        ],
    }
    return {"stack": stack, "floor": floor, "portal": portal}


def main() -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    out = run()
    _dump(HERE / "STACK.json", out["stack"])
    polylines = {
        "mct_sha256": EXPECTED_SHA256,
        "main_sha256": MAIN_SHA,
        "floor": out["floor"],
        "portal_cables": out["portal"],
    }
    _dump(HERE / "polylines.json", polylines)
    rows = ["group,nid,x_m,z_m"]
    for pl in out["floor"]:
        for p in pl["pts_m"]:
            rows.append(f"{pl['group']},{p['nid']},{p['x']:.9g},{p['z']:.9g}")
    (HERE / "floor_alignment.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    write_svg(out["floor"], HERE / "floor_alignment.svg")
    print(json.dumps(out["stack"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
