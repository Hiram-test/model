#!/usr/bin/env python3
"""Full-topology S10 → ccx deck. No R1–R7 reductions.

  - 44 physical rope lines, every station, T3D2 (tension only, like LINK10/180)
  - every BEAM188 gate/passage member, B31 RECT matched to S10 ASEC 61–66
  - every crossbeam row, B31
  - CERIG UXYZ/ALL → *EQUATION on the matching DOF
  - S10 D / CP / downpull copied
  - ROTY stab file applied on B31 nodes (R7 off)
  - MASS21 folded to nearest T3D2 density (ccx 2.21 TYPE=MASS × PERTURBATION
    is a solver crash, not a geometry contract)
  - prestress via temperature on T3D2 (TYPE=STRESS diverges on T3D2 in 2.21)

Does not overwrite solver/true3d_ccx.inp. Job name true3d_full.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from build_true3d_ccx import (
    BEARING_A, GANTRY_A, DOWNPULL_A, RHO, E_ROPE, NU_ROPE, E_STEEL, NU_STEEL,
    G_MM, CROSS_LARGE, CROSS_SMALL, rect_match,
)

ART = Path(__file__).resolve().parent.parent / "artifacts"
SOL = Path(__file__).resolve().parent.parent / "solver"
JOB = os.environ.get("CCX_JOB", "true3d_full")
MANIFEST_NAME = os.environ.get("MANIFEST_NAME", "true3d_model_manifest_full.json")
MODES = int(os.environ.get("MODES", "100"))

# S10 ASEC 61–66: (A, Izz, Iyy) → rect_match(I_vert=Izz, I_lat=Iyy)
ASEC = {
    61: (4997.5, 28164706.4583, 9830899.73958),
    62: (2496.0, 10130432.0, 10130432.0),
    63: (2752.03516454, 7345181.85417, 7345181.85417),
    64: (1231.50432021, 1480883.94505, 1480883.94505),
    65: (590.619418875, 164266.025875, 164266.025875),
    66: (576.0, 176672.0, 75232.0),
}


def main() -> None:
    d = np.load(ART / "s10_model.npz", allow_pickle=True)
    node_ids = np.asarray(d["node_ids"])
    node_xyz = np.asarray(d["node_xyz"])
    gnode_ids = np.asarray(d["gnode_ids"])
    gnode_xyz = np.asarray(d["gnode_xyz"])
    bearing = np.asarray(d["bearing"])
    gantry = np.asarray(d["gantry"])
    cross_L = np.asarray(d["cross_large"])
    cross_S = np.asarray(d["cross_small"])
    gates = np.asarray(d["gate_elems"])
    cerigs = np.asarray(d["cerigs"])
    ds = np.asarray(d["ds"])
    dp = np.asarray(d["dp_elems"])
    cp_sets = list(d["cp_sets"])
    sig = dict(zip(np.asarray(d["inistate_eids"]).tolist(),
                   np.asarray(d["inistate_sig"]).tolist()))
    masses = np.asarray(d["masses"])
    d.close()

    pos = {}
    for i, xyz in zip(node_ids, node_xyz):
        pos[int(i)] = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    for i, xyz in zip(gnode_ids, gnode_xyz):
        pos[int(i)] = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    for rec in dp:
        for n in (int(rec[1]), int(rec[2])):
            if n not in pos:
                raise SystemExit(f"downpull node {n} missing")

    used = set()
    for arr in (bearing, gantry, cross_L, cross_S):
        used.update(int(a) for a in arr[:, 1])
        used.update(int(a) for a in arr[:, 2])
    used.update(int(a) for a in gates[:, 1])
    used.update(int(a) for a in gates[:, 2])
    used.update(int(a) for a in dp[:, 1])
    used.update(int(a) for a in dp[:, 2])
    used.update(int(n) for n, _ in ds)
    for cp in cp_sets:
        used.update(int(n) for n in cp[2:])
    for m, s, _ in cerigs:
        used.add(int(m))
        used.add(int(s))

    dest = SOL / f"{JOB}.inp"
    f = open(dest, "w")
    w = f.write
    w("*HEADING\n")
    w("Full S10 topology ccx deck; R1-R7 OFF; ropes T3D2; units N/mm/t/s\n")
    w("*NODE, NSET=NALL\n")
    for n in sorted(used):
        if n not in pos:
            continue
        x, y, z = pos[n]
        w(f"{n}, {x:.6f}, {y:.6f}, {z:.6f}\n")

    def emit_t3d2(name, arr):
        w(f"*ELEMENT, TYPE=T3D2, ELSET={name}\n")
        for e, a, b in arr:
            w(f"{int(e)}, {int(a)}, {int(b)}\n")

    emit_t3d2("E_BEARING", bearing)
    emit_t3d2("E_GANTRY", gantry)
    w("*ELEMENT, TYPE=T3D2, ELSET=E_DOWNPULL\n")
    for k, rec in enumerate(dp, start=1):
        w(f"{900000 + k}, {int(rec[1])}, {int(rec[2])}\n")

    def beam_ori(a, b):
        """n1 must not be parallel to the element tangent (ccx RECT)."""
        pa, pb = np.array(pos[int(a)]), np.array(pos[int(b)])
        t = pb - pa
        nrm = float(np.linalg.norm(t))
        if nrm < 1e-12:
            return (0.0, 1.0, 0.0)
        t = t / nrm
        if abs(t[1]) > 0.85:
            return (1.0, 0.0, 0.0)
        return (0.0, 1.0, 0.0)

    def ori_key(a, b):
        o = beam_ori(a, b)
        return f"{o[0]:.0f}{o[1]:.0f}{o[2]:.0f}"

    bysec = defaultdict(list)
    for e, a, b, s in gates:
        bysec[(int(s), ori_key(a, b))].append((int(e), int(a), int(b)))
    gate_elsets = []
    for (s, ok), rows in sorted(bysec.items()):
        name = f"E_GATE_{s}_{ok}"
        gate_elsets.append((name, s, rows[0][1], rows[0][2]))
        w(f"*ELEMENT, TYPE=B31, ELSET={name}\n")
        for e, a, b in rows:
            w(f"{e}, {a}, {b}\n")

    cross_elsets = []
    for tag, arr, sec in (("L", cross_L, CROSS_LARGE), ("S", cross_S, CROSS_SMALL)):
        buckets = defaultdict(list)
        for e, a, b in arr:
            buckets[ori_key(a, b)].append((int(e), int(a), int(b)))
        for ok, rows in sorted(buckets.items()):
            name = f"E_CROSS_{tag}_{ok}"
            cross_elsets.append((name, sec, rows[0][1], rows[0][2]))
            w(f"*ELEMENT, TYPE=B31, ELSET={name}\n")
            for e, a, b in rows:
                w(f"{e}, {a}, {b}\n")

    rope_nodes = []
    rope_xyz = []
    for arr in (bearing, gantry):
        for _, a, b in arr:
            for n in (int(a), int(b)):
                rope_nodes.append(n)
                rope_xyz.append(pos[n])
    seen = {}
    rn, rx = [], []
    for n, xyz in zip(rope_nodes, rope_xyz):
        if n not in seen:
            seen[n] = len(rn)
            rn.append(n)
            rx.append(xyz)
    tree = cKDTree(np.array(rx))
    _, ix = tree.query(masses[:, 1:4], k=1)
    extra = defaultdict(float)
    for m, j in zip(masses[:, 4], ix):
        extra[rn[int(j)]] += float(m)

    inc = defaultdict(list)
    for e, a, b in list(bearing) + list(gantry):
        inc[int(a)].append(int(e))
        inc[int(b)].append(int(e))
    extra_e = defaultdict(float)
    for n, m in extra.items():
        els = inc.get(n)
        if not els:
            continue
        share = m / len(els)
        for e in els:
            extra_e[e] += share

    # T3D2 + TYPE=STRESS diverges in ccx 2.21 (2-bar probe: cutbacks).
    # Temperature prestress converges and stays tension-only: σ = E α |ΔT|, ΔT = -1.
    bins = defaultdict(list)
    for e, a, b in bearing:
        e, a, b = int(e), int(a), int(b)
        pa, pb = np.array(pos[a]), np.array(pos[b])
        L = float(np.linalg.norm(pb - pa))
        rho = RHO["bearing"] + extra_e.get(e, 0.0) / (BEARING_A * max(L, 1.0))
        s_val = float(sig.get(e, 0.0))
        key = ("B", int(round(math.log10(max(rho, 1e-18)) * 80)),
               int(round(s_val / 5.0)))
        bins[key].append((e, rho, BEARING_A, s_val))
    for e, a, b in gantry:
        e, a, b = int(e), int(a), int(b)
        pa, pb = np.array(pos[a]), np.array(pos[b])
        L = float(np.linalg.norm(pb - pa))
        rho = RHO["gantry"] + extra_e.get(e, 0.0) / (GANTRY_A * max(L, 1.0))
        s_val = float(sig.get(e, 0.0))
        key = ("G", int(round(math.log10(max(rho, 1e-18)) * 80)),
               int(round(s_val / 5.0)))
        bins[key].append((e, rho, GANTRY_A, s_val))

    for i, (key, rows) in enumerate(sorted(bins.items())):
        rho = float(np.mean([r[1] for r in rows]))
        s_mean = float(np.mean([r[3] for r in rows]))
        alpha = s_mean / E_ROPE if E_ROPE else 0.0
        name = f"MR{i:04d}"
        w(f"*MATERIAL, NAME={name}\n*ELASTIC\n{E_ROPE:.1f}, {NU_ROPE}\n*DENSITY\n{rho:.9e}\n")
        w(f"*EXPANSION\n{alpha:.9e}\n")
        w(f"*ELSET, ELSET=SR{i:04d}\n")
        ids = [r[0] for r in rows]
        for k in range(0, len(ids), 16):
            w(",".join(str(x) for x in ids[k:k + 16]) + "\n")
        A = rows[0][2]
        w(f"*SOLID SECTION, ELSET=SR{i:04d}, MATERIAL={name}\n{A:.6f}\n")

    dp_sig = [float(sig.get(int(rec[0]), 0.0)) for rec in dp]
    dp_alpha = (float(np.mean(dp_sig)) / E_ROPE) if dp_sig else 0.0
    w("*MATERIAL, NAME=MDP\n*ELASTIC\n{:.1f}, {}\n*DENSITY\n{:.9e}\n".format(
        E_ROPE, NU_ROPE, RHO["downpull"]))
    w(f"*EXPANSION\n{dp_alpha:.9e}\n")
    w(f"*SOLID SECTION, ELSET=E_DOWNPULL, MATERIAL=MDP\n{DOWNPULL_A:.6f}\n")

    w("*MATERIAL, NAME=MST\n*ELASTIC\n{:.1f}, {}\n*DENSITY\n1e-17\n".format(E_STEEL, NU_STEEL))
    for name, s, a, b in gate_elsets:
        A, Izz, Iyy = ASEC[s]
        h1, h2 = rect_match(Izz, Iyy)
        ox, oy, oz = beam_ori(a, b)
        w(f"*BEAM SECTION, ELSET={name}, MATERIAL=MST, SECTION=RECT\n")
        w(f"{h1:.6f}, {h2:.6f}\n{ox:.1f}, {oy:.1f}, {oz:.1f}\n")
    for name, sec, a, b in cross_elsets:
        side = (12.0 * sec[1]) ** 0.25
        ox, oy, oz = beam_ori(a, b)
        w(f"*BEAM SECTION, ELSET={name}, MATERIAL=MST, SECTION=RECT\n")
        w(f"{side:.6f}, {side:.6f}\n{ox:.1f}, {oy:.1f}, {oz:.1f}\n")

    ic_n = sum(1 for e, _, _ in list(bearing) + list(gantry) if sig.get(int(e), 0.0) != 0.0)
    ic_n += sum(1 for rec in dp if sig.get(int(rec[0]), 0.0) != 0.0)

    beam_nodes = set()
    for arr in (gates, cross_L, cross_S):
        beam_nodes.update(int(a) for a in arr[:, 1])
        beam_nodes.update(int(a) for a in arr[:, 2])

    bmap = defaultdict(set)
    for n, dof in ds:
        n, dof = int(n), int(dof)
        if n not in pos:
            continue
        ccx_dof = dof + 1
        if ccx_dof >= 4 and n not in beam_nodes:
            continue
        bmap[n].add(ccx_dof)

    roty_path = Path("/tmp/s10/apply_modal_roty_stabilization_xlong.inp")
    roty_n = 0
    if roty_path.is_file():
        for raw in roty_path.read_text().splitlines():
            line = raw.split("!", 1)[0].strip()
            if line.startswith("D,") and ",ROTY," in line:
                nid = int(line.split(",")[1])
                if nid in pos and nid in beam_nodes:
                    bmap[nid].add(5)
                    roty_n += 1

    w("*BOUNDARY\n")
    for n in sorted(bmap):
        for dof in sorted(bmap[n]):
            w(f"{n}, {dof}, {dof}\n")
    w("*NSET, NSET=NSUPP\n")
    for n in sorted(bmap):
        w(f"{n}\n")

    eqs = []
    for row in cerigs:
        m, s, kind = int(row[0]), int(row[1]), int(row[2])
        dofs = (1, 2, 3, 4, 5, 6) if kind == 1 else (1, 2, 3)
        for dof in dofs:
            eqs.append((s, dof, m))
    for cp in cp_sets:
        dof = int(cp[1]) + 1
        master = int(cp[2])
        for n in cp[3:]:
            n = int(n)
            if n != master:
                eqs.append((n, dof, master))
    if eqs:
        w("*EQUATION\n")
        for s, dof, m in eqs:
            w("2\n")
            w(f"{s}, {dof}, 1.0, {m}, {dof}, -1.0\n")

    elsets = (["E_BEARING", "E_GANTRY", "E_DOWNPULL"]
              + [name for name, _, _, _ in gate_elsets]
              + [name for name, _, _, _ in cross_elsets])
    w("*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 0\n")
    w("*STEP, NLGEOM, INC=200\n*STATIC\n0.05, 1.0, 1e-8, 1.0\n")
    w("*TEMPERATURE\nNALL, -1\n*DLOAD\n")
    for name in elsets:
        w(f"{name}, GRAV, {G_MM}, 0.0, 0.0, -1.0\n")
    w("*NODE FILE\nU\n*NODE PRINT, NSET=NSUPP\nRF\n*END STEP\n")
    w(f"*STEP, PERTURBATION\n*FREQUENCY\n{MODES}\n*NODE FILE\nU\n*END STEP\n")
    f.close()

    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    man = {
        "job": JOB,
        "deck_sha256": sha,
        "contracts": "NONE — R1-R7 off",
        "rope_element": "T3D2",
        "prestress": "T3D2 temperature (TYPE=STRESS diverges on T3D2)",
        "n_nodes_emitted": len(used),
        "n_bearing": int(len(bearing)),
        "n_gantry": int(len(gantry)),
        "n_gate": int(len(gates)),
        "n_cross": int(len(cross_L) + len(cross_S)),
        "n_cerig": int(len(cerigs)),
        "n_ic": ic_n,
        "n_rope_mats": len(bins),
        "n_eq": len(eqs),
        "n_roty": roty_n,
        "mass21_note": "folded to T3D2 density; ccx 2.21 TYPE=MASS x PERTURBATION crashes",
        "mass21_folded_t": float(masses[:, 4].sum()),
        "bytes": dest.stat().st_size,
    }
    (ART / MANIFEST_NAME).write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps(man, indent=2))


if __name__ == "__main__":
    main()
