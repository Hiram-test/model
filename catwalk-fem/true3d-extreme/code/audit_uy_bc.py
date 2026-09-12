#!/usr/bin/env python3
"""Independent reread of true3d_ccx.inp BOUNDARY cards.

Hard lock: catwalk UY must not be nailed on the whole mesh (the 2-D MCT
migrate pattern). This script does not import the builder.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INP = BASE / "solver" / f"{os.environ.get('CCX_JOB', 'true3d_ccx')}.inp"
ART = BASE / "artifacts"
UY_FRAC_MAX = 0.05


def main() -> None:
    text = INP.read_text()
    if "NALL" in text and any(
        line.strip().upper().startswith("NALL") and ",2" in line.replace(" ", "")
        for line in text.splitlines()
    ):
        raise SystemExit("UY GATE FAIL: NALL appears as a BOUNDARY target")
    if "*BOUNDARY, NSET=NALL" in text.upper().replace(" ", ""):
        raise SystemExit("UY GATE FAIL: *BOUNDARY,NSET=NALL present")

    nodes = set()
    bmap: dict[int, set[int]] = defaultdict(set)
    in_node = in_bc = False
    for raw in text.splitlines():
        line = raw.split("**", 1)[0].strip()
        if not line:
            continue
        u = line.upper()
        if u.startswith("*NODE"):
            in_node, in_bc = True, False
            continue
        if u.startswith("*BOUNDARY"):
            in_bc, in_node = True, False
            if "NSET" in u and "NALL" in u:
                raise SystemExit("UY GATE FAIL: *BOUNDARY with NSET=NALL")
            continue
        if u.startswith("*"):
            in_node = in_bc = False
            continue
        if in_node:
            try:
                nodes.add(int(line.split(",")[0]))
            except ValueError:
                continue
        elif in_bc:
            p = [x.strip() for x in line.split(",")]
            if len(p) < 3:
                continue
            try:
                n = int(p[0])
                d1 = int(p[1])
                d2 = int(p[2])
            except ValueError:
                continue
            for d in range(d1, d2 + 1):
                bmap[n].add(d)

    n_uy = sum(1 for ds in bmap.values() if 2 in ds)
    n_all = len(nodes)
    frac = n_uy / max(n_all, 1)
    all_mesh = n_uy >= 0.90 * n_all
    report = {
        "inp": str(INP),
        "nodes_total": n_all,
        "bc_nodes": len(bmap),
        "uy_nodes": n_uy,
        "ux_nodes": sum(1 for ds in bmap.values() if 1 in ds),
        "uz_nodes": sum(1 for ds in bmap.values() if 3 in ds),
        "uy_frac": frac,
        "all_mesh_uy": all_mesh,
        "uy_frac_max": UY_FRAC_MAX,
        "pass": (not all_mesh) and (0 < frac < UY_FRAC_MAX) and n_uy > 0,
        "nall_uy_card": False,
    }
    tag = os.environ.get("CCX_JOB", "true3d_ccx")
    dest = ART / ("uy_bc_reread.json" if tag == "true3d_ccx" else f"uy_bc_reread_{tag}.json")
    dest.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    if not report["pass"]:
        raise SystemExit("UY GATE FAIL on independent reread")
    print("UY GATE PASS")


if __name__ == "__main__":
    main()
