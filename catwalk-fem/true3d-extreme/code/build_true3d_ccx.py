#!/usr/bin/env python3
"""Build the simplified TRUE-3D catwalk CalculiX deck from the parsed S10 model.

Simplification contract (recorded in manifest):
  R1  Per catwalk two walkway bands; each band's 8 bearing ropes merge into ONE
      equivalent line (A,T x8) at the band's mean Y; each band's 3 gantry ropes
      merge into ONE line (A,T x3) at their mean Y, keeping their real elevated
      profile (~+8.5 m).  8 rope lines total + 4 downpull links.
  R2  Longitudinal coarsening: keep every 4th bearing node (~7.9 m) plus forced
      stations (gates, passages, D-constraint x, CP rings, saddles, ends).
  R3  142 gate frames -> parametric portal per catwalk station: bottom H175 beam
      (innerB-outerB), 2 posts RHS160 (B->G), top RHS160 (innerG-outerG).
      Real CERIG UXYZ pin replaced by shared node (rope I is negligible).
  R4  Crossbeam ladder (1430 rows, alternating box100/box50 @2.95 m) -> one
      smeared beam innerB-outerB per kept station, section scaled by
      (tributary dx / 2.948 m); mass stays in MASS21 (density zero, as in S10).
  R5  21 passages -> one 2-chord-equivalent beam each across the full width,
      welded at the 4 bearing-line crossings (real: pin), chord-only Iz.
  R6  33,003 MASS21 folded into per-element densities (binned); the 23,028
      static F loads are dropped because sum(F)/g == sum(MASS21) (963.811 t).
  R7  ROTY stabilization file skipped (B31 expansion provides rotary DOFs).
Units N/mm/tonne/s.  X longitudinal, Y transverse, Z vertical.
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

ART = Path(__file__).resolve().parent.parent / "artifacts"
SOL = Path(__file__).resolve().parent.parent / "solver"
SOL.mkdir(parents=True, exist_ok=True)
UY_FRAC_MAX = 0.05          # hard lock: catwalk UY must NOT be all-mesh pinned
BUILDER_SCHEME_MIN = 100000  # nid = 100000*(g+1)+k ; S10 raw ids collide above this
IMPORT_SHIFT = 2_000_000
PASSAGE_CLUSTER_GAP_MM = 5000.0


def deck_id_from_s10(n: int) -> int:
    """Keep 100000*(g+1)+k reserved. S10 ids in that range are shifted."""
    n = int(n)
    if n < BUILDER_SCHEME_MIN:
        return n
    return IMPORT_SHIFT + n


def cluster_x_stations(xs, gap: float = PASSAGE_CLUSTER_GAP_MM) -> list[float]:
    """R5: one equivalent beam per passage, not one per sec-63 depth sample."""
    xs = sorted(float(x) for x in xs)
    if not xs:
        return []
    clusters = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] < gap:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [float(sum(c) / len(c)) for c in clusters]

BEARING_A = 1393.668228093791
GANTRY_A = 1400.496622996084
DOWNPULL_A = 22298.691649500659
RHO = {"bearing": 1.264848052212931e-08, "gantry": 8.598817050785234e-09,
       "downpull": 1.264848052212931e-08}
RHO_STEEL_NIL = 1.0e-17
E_ROPE, NU_ROPE = 120000.0, 0.3
E_STEEL, NU_STEEL = 206000.0, 0.31
G_MM = 9806.0
MODES = int(os.environ.get("MODES", "100"))
COARSEN = int(os.environ.get("COARSEN", "4"))          # keep every Nth bearing node (~7.9 m at 4)
CCX_JOB = os.environ.get("CCX_JOB", "true3d_ccx")
MANIFEST_NAME = os.environ.get("MANIFEST_NAME", "true3d_model_manifest.json")

# ASEC (A, I_vert, I_lat, J) from S10 include
SEC_H175 = (4997.5, 28164706.4583, 9830899.73958, 176798.958333)
SEC_RHS160 = (2496.0, 10130432.0, 10130432.0, 15185664.0)
CROSS_LARGE = (1536.0, 2363392.0, 2363392.0, 3538944.0)
CROSS_SMALL = (736.0, 261525.333333, 261525.333333, 389344.0)
CROSS_SPACING = 2948.0
PASS_CHORD_A = 2752.03516454
PASS_CHORD_I = 7345181.85417


def rect_match(I_vert: float, I_lat: float) -> tuple[float, float]:
    """RECT h1 (1-dir thickness), h2 with I_lat=h2*h1^3/12, I_vert=h1*h2^3/12."""
    prod = math.sqrt(144.0 * I_vert * I_lat)      # (h1*h2)^2
    h1h2 = math.sqrt(prod)
    ratio = math.sqrt(I_vert / I_lat)             # h2/h1
    h1 = math.sqrt(h1h2 / ratio)
    h2 = h1 * ratio
    return h1, h2


def trace_lines(elem_arr):
    adj = defaultdict(list)
    for eid, n1, n2 in elem_arr:
        adj[int(n1)].append((int(n2), int(eid)))
        adj[int(n2)].append((int(n1), int(eid)))
    used, lines = set(), []
    seeds = [n for n, a in adj.items() if len(a) != 2] + [n for n, a in adj.items() if len(a) == 2]
    for s in seeds:
        for nxt, eid in adj[s]:
            if eid in used:
                continue
            chain_n, chain_e = [s], []
            nn, ee = nxt, eid
            while True:
                used.add(ee)
                chain_e.append(ee)
                chain_n.append(nn)
                cand = [(m, e2) for (m, e2) in adj[nn] if e2 not in used]
                if len(adj[nn]) != 2 or not cand:
                    break
                nn, ee = cand[0]
            lines.append((chain_n, chain_e))
    return lines


def _rss_mb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        return -1.0
    return -1.0


def main() -> None:
    # Bind each npz array once. NpzFile.__getitem__ decompresses a fresh copy
    # per access; looping d["node_xyz"][k] over 79k ids OOMs a 15 GB VM.
    d = np.load(ART / "s10_model.npz", allow_pickle=True)
    node_ids = np.asarray(d["node_ids"])
    node_xyz_arr = np.asarray(d["node_xyz"])
    gnode_ids = np.asarray(d["gnode_ids"])
    gnode_xyz_arr = np.asarray(d["gnode_xyz"])
    inistate_eids = np.asarray(d["inistate_eids"])
    inistate_sig = np.asarray(d["inistate_sig"])
    bearing_arr = np.asarray(d["bearing"])
    gantry_arr = np.asarray(d["gantry"])
    gate_elems = np.asarray(d["gate_elems"])
    ds_arr = np.asarray(d["ds"])
    cp_sets = list(d["cp_sets"])
    dp_elems = np.asarray(d["dp_elems"])
    masses = np.asarray(d["masses"])
    floads = np.asarray(d["floads"])
    d.close()
    print(f"npz loaded rss_mb={_rss_mb():.0f}")

    pos = {int(i): node_xyz_arr[k] for k, i in enumerate(node_ids)}
    gpos = {int(i): gnode_xyz_arr[k] for k, i in enumerate(gnode_ids)}
    sig = dict(zip(inistate_eids.tolist(), inistate_sig.tolist()))

    # ---- rope line groups -------------------------------------------------
    groups: dict[str, dict] = {}
    for tag, arr, a_single in (("bearing", bearing_arr, BEARING_A),
                               ("gantry", gantry_arr, GANTRY_A)):
        for chain_n, chain_e in trace_lines(arr):
            y = float(np.mean([pos[n][1] for n in chain_n]))
            cw = "P" if y > 0 else "M"
            band = "O" if abs(y) > 21450.0 else "I"
            key = f"{cw}{band}{'B' if tag == 'bearing' else 'G'}"
            g = groups.setdefault(key, {"tag": tag, "a_single": a_single, "lines": []})
            g["lines"].append({"nodes": chain_n, "eids": chain_e, "y": y})
    assert len(groups) == 8, sorted(groups)
    for key, g in groups.items():
        g["n"] = len(g["lines"])
        g["y_eq"] = float(np.mean([ln["y"] for ln in g["lines"]]))
        g["A_eq"] = g["a_single"] * g["n"]
        rep = sorted(g["lines"], key=lambda ln: ln["y"])[g["n"] // 2]
        xs = np.array([pos[n][0] for n in rep["nodes"]])
        zs = np.array([pos[n][2] for n in rep["nodes"]])
        order = np.argsort(xs)
        g["rep_x"], g["rep_z"] = xs[order], zs[order]
        rn = rep["nodes"]
        mid, s_ = [], []
        for k, e in enumerate(rep["eids"]):
            x1, x2 = pos[rn[k]][0], pos[rn[k + 1]][0]
            mid.append(0.5 * (x1 + x2))
            s_.append(sig.get(e, 0.0))
        mo = np.argsort(mid)
        g["sig_x"] = np.array(mid)[mo]
        g["sig_v"] = np.array(s_)[mo]
        g["node_set"] = set()
        for ln in g["lines"]:
            g["node_set"].update(ln["nodes"])

    node_owner = {}
    for key, g in groups.items():
        for n in g["node_set"]:
            node_owner[n] = key

    # ---- gate / passage stations from generated components -----------------
    ge = gate_elems
    gate_x = sorted({round(gpos[int(i)][0], 1) for e, i, j, s in ge if s == 61})
    pass_x_raw = sorted({round(gpos[int(i)][0], 1) for e, i, j, s in ge if s == 63})
    pass_x = cluster_x_stations(pass_x_raw)
    print(f"gate stations: {len(gate_x)}  passage stations: {len(pass_x)} (raw {len(pass_x_raw)})")

    # ---- constraint / CP node stations -------------------------------------
    ds = ds_arr
    d_rope = [(int(n), int(dof)) for n, dof in ds if int(n) in node_owner]
    d_other = [(int(n), int(dof)) for n, dof in ds if int(n) not in node_owner]

    forced_x = set()
    for n, _ in d_rope:
        forced_x.add(round(pos[n][0], 1))
    for cp in cp_sets:
        for n in cp[2:]:
            if int(n) in node_owner:
                forced_x.add(round(pos[int(n)][0], 1))
    forced_x.update(gate_x)
    forced_x.update(pass_x)
    for key, g in groups.items():
        zpk = g["rep_x"][np.argmax(g["rep_z"])]
        forced_x.add(round(float(zpk), 1))

    # ---- global kept-X grid -------------------------------------------------
    gb = groups["PIB"]
    base_x = list(gb["rep_x"][::COARSEN])
    if gb["rep_x"][-1] not in base_x:
        base_x.append(gb["rep_x"][-1])
    kept = sorted(set(round(float(x), 1) for x in base_x) | forced_x)
    grid = []
    for x in kept:
        if grid and x - grid[-1] < 500.0 and x not in forced_x:
            continue
        if grid and x - grid[-1] < 100.0:
            continue
        grid.append(x)
    grid = np.array(grid)
    print(f"kept X stations: {len(grid)}  range {grid[0]/1e3:.1f}..{grid[-1]/1e3:.1f} m  rss_mb={_rss_mb():.0f}")

    # ---- emit nodes ---------------------------------------------------------
    lines_out: list[str] = []
    push = lines_out.append
    push("*HEADING")
    push("True-3D simplified catwalk from S10 V2.0 APDL; units N / mm / tonne / s")
    push("** X=longitudinal (chainage-K16+876, mm), Y=transverse, Z=up")
    push("** R1-R7 contract; 8 merged rope lines (2 catwalks x 2 bands x bearing/gantry)")
    push("** BOUNDARY: UX/UY/UZ only at S10-mapped support nodes (anchors / downpull).")
    push("** HARD LOCK: do NOT restrain UY on NALL. All-mesh UY=0 is the 2-D MCT migrate")
    push("** pattern and is forbidden on this deck. Lateral (L) modes must remain free.")
    push(f"** COARSEN={COARSEN}  MODES={MODES}  TYPE=B31 SECTION=RECT  IC=8-IP global PK2")
    push("*NODE, NSET=NALL")

    GK = sorted(groups)  # MIB MIG MOB MOG PIB PIG POB POG
    gidx = {k: i for i, k in enumerate(GK)}
    node_id = {}
    node_xyz = {}

    def nid(gkey: str, k: int) -> int:
        return 100000 * (gidx[gkey] + 1) + k

    for key in GK:
        g = groups[key]
        x0, x1 = g["rep_x"][0], g["rep_x"][-1]
        ks = np.where((grid >= x0 - 50.0) & (grid <= x1 + 50.0))[0]
        g["grid_idx"] = ks
        for k in ks:
            x = float(np.clip(grid[k], x0, x1))
            z = float(np.interp(x, g["rep_x"], g["rep_z"]))
            i = nid(key, int(k))
            node_id[(key, int(k))] = i
            node_xyz[i] = (x, g["y_eq"], z)
            push(f"{i}, {x:.3f}, {g['y_eq']:.3f}, {z:.3f}")

    dp = dp_elems
    dp_nodes = sorted({int(n) for e in dp for n in e[1:]})
    rope_ids = set(node_xyz)
    for n in dp_nodes:
        i = deck_id_from_s10(n)
        if i in rope_ids:
            raise SystemExit(f"node id collision: S10 {n} -> {i} overlaps builder scheme")
        x, y, z = pos[n]
        node_xyz[i] = (float(x), float(y), float(z))
        push(f"{i}, {x:.3f}, {y:.3f}, {z:.3f}")

    # passage nodes: per passage, at 4 bearing crossings + 2 tips (y +-24860)
    # TRUE3D_SKIP_PASSAGES=1: wave-5 Lemma-A diagnostic — drop the 21 welded
    # 2-chord passage beams (base rho ~0, folded mass re-bins to neighbours)
    # to test whether they are the non-provenance path lifting antisym torsion.
    skip_passages = os.environ.get("TRUE3D_SKIP_PASSAGES") == "1"
    # TRUE3D_PASSAGE_HINGE=1: wave-5 diagnostic — keep the 21 passage beams but
    # sever moment continuity at the 4 bearing crossings (duplicate node +
    # *EQUATION on UX/UY/UZ only), i.e. the S10 CERIG-UXYZ semantics.
    passage_hinge = os.environ.get("TRUE3D_PASSAGE_HINGE") == "1"
    passage_i_scale = float(os.environ.get("TRUE3D_PASSAGE_I_SCALE", "1"))
    pass_elems = []
    PBASE = 900000
    pn = 0
    pass_records = []
    pass_hinge_pairs = []
    pass_spin_ties = []
    for ip, px in enumerate(pass_x if not skip_passages else []):
        k = int(np.argmin(np.abs(grid - px)))
        ys = [(groups[key]["y_eq"], key) for key in ("MOB", "MIB", "PIB", "POB")]
        zc = float(np.interp(grid[k], groups["PIB"]["rep_x"], groups["PIB"]["rep_z"]))
        chain = []
        pts = [(-24860.0, None)] + sorted(ys) + [(24860.0, None)]
        for y, key in pts:
            if key is None:
                pn += 1
                i = PBASE + pn
                node_xyz[i] = (float(grid[k]), y, zc)
                push(f"{i}, {grid[k]:.3f}, {y:.3f}, {zc:.3f}")
                chain.append(i)
            elif passage_hinge:
                orig = node_id[(key, k)]
                pn += 1
                i = PBASE + pn
                ox, oy, oz = node_xyz[orig]
                node_xyz[i] = (ox, oy, oz)
                push(f"{i}, {ox:.3f}, {oy:.3f}, {oz:.3f}")
                chain.append(i)
                if not any(p == ip for p, _, _ in pass_spin_ties):
                    # one ROTY tie per passage kills the spin-about-own-axis
                    # mechanism; RX/RZ stay released everywhere.
                    pass_spin_ties.append((ip, i, orig))
                else:
                    pass_hinge_pairs.append((i, orig))
            else:
                chain.append(node_id[(key, k)])
        pass_records.append({"x_m": round(px / 1e3, 2), "grid_k": k})
        for a, b in zip(chain[:-1], chain[1:]):
            pass_elems.append((a, b))

    # ---- elements -----------------------------------------------------------
    eid = 0
    elsets: dict[str, list[int]] = defaultdict(list)
    elem_def = {}
    elem_meta = {}

    def emit_elems(pairs, kind, gkey=None):
        nonlocal eid
        out = []
        for a, b in pairs:
            eid += 1
            elem_def[eid] = (a, b)
            pa, pb = np.array(node_xyz[a]), np.array(node_xyz[b])
            L = float(np.linalg.norm(pb - pa))
            elem_meta[eid] = {"kind": kind, "group": gkey, "L": L}
            out.append(eid)
        return out

    for key in GK:
        g = groups[key]
        ks = g["grid_idx"]
        pairs = [(node_id[(key, int(ks[i]))], node_id[(key, int(ks[i + 1]))])
                 for i in range(len(ks) - 1)]
        elsets[f"E_ROPE_{key}"] = emit_elems(pairs, "rope", key)

    elsets["E_DOWNPULL"] = emit_elems(
        [(deck_id_from_s10(int(a)), deck_id_from_s10(int(b))) for _, a, b in dp],
        "downpull",
    )

    portal_count = 0
    for gx in gate_x:
        k = int(np.argmin(np.abs(grid - gx)))
        for cw in ("P", "M"):
            need = [(f"{cw}IB", k), (f"{cw}OB", k), (f"{cw}IG", k), (f"{cw}OG", k)]
            if not all(kk in node_id for kk in need):
                continue
            ib, ob = node_id[(f"{cw}IB", k)], node_id[(f"{cw}OB", k)]
            ig, og = node_id[(f"{cw}IG", k)], node_id[(f"{cw}OG", k)]
            elsets["E_GATE_BOT"] += emit_elems([(ib, ob)], "gate_bot")
            elsets["E_GATE_POST"] += emit_elems([(ib, ig), (ob, og)], "gate_post")
            elsets["E_GATE_TOP"] += emit_elems([(ig, og)], "gate_top")
            portal_count += 1

    row_x0, row_x1 = 43870.0, 4221090.0
    tributary = np.gradient(grid)
    for k, x in enumerate(grid):
        if x < row_x0 or x > row_x1:
            continue
        s = float(tributary[k]) / CROSS_SPACING
        for cw in ("P", "M"):
            kib, kob = (f"{cw}IB", k), (f"{cw}OB", k)
            if kib in node_id and kob in node_id:
                ids = emit_elems([(node_id[kib], node_id[kob])], "crossrow")
                elsets["E_CROSS"] += ids
                elem_meta[ids[0]]["scale"] = s

    elsets["E_PASS"] = emit_elems(pass_elems, "passage")

    for name, ids in elsets.items():
        if not ids:
            continue
        push(f"*ELEMENT, TYPE=B31, ELSET={name}")
        for e in ids:
            a, b = elem_def[e]
            push(f"{e}, {a}, {b}")

    # ---- masses -> nearest kept node -> element density bins ----------------
    # masses already bound from npz
    kept_ids = np.array(sorted(node_xyz))
    kept_arr = np.array([node_xyz[i] for i in kept_ids])
    tree = cKDTree(kept_arr)
    dist, idx = tree.query(masses[:, 1:4], k=1)
    node_extra = defaultdict(float)
    for (row, j) in zip(masses, idx):
        node_extra[int(kept_ids[j])] += float(row[4])
    print(f"mass mapping: max snap dist {dist.max()/1e3:.2f} m, mean {dist.mean()/1e3:.3f} m")

    node_adj = defaultdict(list)
    for e, (a, b) in elem_def.items():
        node_adj[a].append(e)
        node_adj[b].append(e)
    elem_extra = defaultdict(float)
    for n, m in node_extra.items():
        adj = node_adj[n]
        for e in adj:
            elem_extra[e] += m / len(adj)

    def base_props(e):
        meta = elem_meta[e]
        kind = meta["kind"]
        if kind == "rope":
            g = groups[meta["group"]]
            return g["A_eq"], RHO[g["tag"]]
        if kind == "downpull":
            return DOWNPULL_A, RHO["downpull"]
        if kind == "gate_bot":
            h1, h2 = rect_match(SEC_H175[1], SEC_H175[2])
            return h1 * h2, RHO_STEEL_NIL
        if kind in ("gate_post", "gate_top"):
            h1, h2 = rect_match(SEC_RHS160[1], SEC_RHS160[2])
            return h1 * h2, RHO_STEEL_NIL
        if kind == "crossrow":
            s = elem_meta[e].get("scale", 1.0)
            I_avg = 0.5 * (CROSS_LARGE[1] + CROSS_SMALL[1]) * s
            side = (12.0 * I_avg) ** 0.25
            return side * side, RHO_STEEL_NIL
        if kind == "passage":
            h1, h2 = rect_match(2.0 * PASS_CHORD_A * (1855.0 / 2.0) ** 2 * passage_i_scale,
                                2.0 * PASS_CHORD_I * passage_i_scale)
            return h1 * h2, RHO_STEEL_NIL
        raise KeyError(kind)

    rho_el = {}
    for e in elem_def:
        A, rho0 = base_props(e)
        L = elem_meta[e]["L"]
        rho_el[e] = rho0 + elem_extra.get(e, 0.0) / (A * max(L, 1.0))

    bins = defaultdict(list)
    for e, rho in rho_el.items():
        key = (elem_meta[e]["kind"], elem_meta[e].get("group") or "-",
               int(round(math.log10(max(rho, 1e-18)) * 150)))
        bins[key].append(e)
    print(f"density bins: {len(bins)}")

    bmats = []
    for i, (bkey, eids) in enumerate(sorted(bins.items())):
        kind = bkey[0]
        rho = float(np.mean([rho_el[e] for e in eids]))
        name = f"MB{i:04d}"
        if kind in ("rope", "downpull"):
            E, nu = E_ROPE, NU_ROPE
        else:
            E, nu = E_STEEL, NU_STEEL
        bmats.append((name, E, nu, rho, eids, kind))
    for name, E, nu, rho, _, _ in bmats:
        push(f"*MATERIAL, NAME={name}")
        push("*ELASTIC")
        push(f"{E:.1f}, {nu}")
        push("*DENSITY")
        push(f"{rho:.9e}")

    ori_of_kind = {
        "rope": "0, 1, 0", "downpull": "0, 1, 0",
        "gate_bot": "1, 0, 0", "gate_top": "1, 0, 0", "gate_post": "1, 0, 0",
        "crossrow": "1, 0, 0", "passage": "1, 0, 0",
    }

    def sec_dims(e):
        meta = elem_meta[e]
        kind = meta["kind"]
        if kind == "rope":
            side = math.sqrt(groups[meta["group"]]["A_eq"])
            return side, side
        if kind == "downpull":
            side = math.sqrt(DOWNPULL_A)
            return side, side
        if kind == "gate_bot":
            return rect_match(SEC_H175[1], SEC_H175[2])
        if kind in ("gate_post", "gate_top"):
            return rect_match(SEC_RHS160[1], SEC_RHS160[2])
        if kind == "crossrow":
            s = meta.get("scale", 1.0)
            I_avg = 0.5 * (CROSS_LARGE[1] + CROSS_SMALL[1]) * s
            side = (12.0 * I_avg) ** 0.25
            return side, side
        if kind == "passage":
            return rect_match(2.0 * PASS_CHORD_A * (1855.0 / 2.0) ** 2 * passage_i_scale,
                              2.0 * PASS_CHORD_I * passage_i_scale)
        raise KeyError(kind)

    for i, (name, E, nu, rho, eids, kind) in enumerate(bmats):
        bysec = defaultdict(list)
        for e in eids:
            h1, h2 = sec_dims(e)
            bysec[(round(h1, 3), round(h2, 3))].append(e)
        for j, ((h1, h2), es) in enumerate(sorted(bysec.items())):
            sname = f"S{i:04d}_{j}"
            push(f"*ELSET, ELSET={sname}")
            for e in es:
                push(f"{e}")
            push(f"*BEAM SECTION, ELSET={sname}, MATERIAL={name}, SECTION=RECT")
            push(f"{h1:.6f}, {h2:.6f}")
            push(ori_of_kind[kind])

    # ---- initial stress ------------------------------------------------------
    push("*INITIAL CONDITIONS, TYPE=STRESS")
    ic_n = 0
    for key in GK:
        g = groups[key]
        for e in elsets[f"E_ROPE_{key}"]:
            a, b = elem_def[e]
            pa, pb = np.array(node_xyz[a]), np.array(node_xyz[b])
            xm = 0.5 * (pa[0] + pb[0])
            s_val = float(np.interp(xm, g["sig_x"], g["sig_v"]))
            n = (pb - pa) / np.linalg.norm(pb - pa)
            comp = (s_val * n[0] * n[0], s_val * n[1] * n[1], s_val * n[2] * n[2],
                    s_val * n[0] * n[1], s_val * n[0] * n[2], s_val * n[1] * n[2])
            for ip in range(1, 9):
                push(f"{e}, {ip}, " + ", ".join(f"{c:.6e}" for c in comp))
            ic_n += 1
    dp_list = [(int(x[0]), int(x[1]), int(x[2])) for x in dp]
    for (edp, a, b), e_local in zip(dp_list, elsets["E_DOWNPULL"]):
        s_val = sig.get(edp, 0.0)
        a, b = deck_id_from_s10(a), deck_id_from_s10(b)
        pa, pb = np.array(node_xyz[a]), np.array(node_xyz[b])
        n = (pb - pa) / np.linalg.norm(pb - pa)
        comp = (s_val * n[0] * n[0], s_val * n[1] * n[1], s_val * n[2] * n[2],
                s_val * n[0] * n[1], s_val * n[0] * n[2], s_val * n[1] * n[2])
        for ip in range(1, 9):
            push(f"{e_local}, {ip}, " + ", ".join(f"{c:.6e}" for c in comp))
        ic_n += 1
    print(f"IC elements: {ic_n}")

    # ---- boundaries (anchor-level only; UY is NOT all-mesh) -------------------
    bmap = defaultdict(set)
    for n, dof in d_rope:
        key = node_owner[n]
        x = pos[n][0]
        k = int(np.argmin(np.abs(grid - x)))
        if (key, k) in node_id:
            bmap[node_id[(key, k)]].add(int(dof) + 1)
    for n, dof in d_other:
        if int(dof) == 4:
            continue
        deck_n = deck_id_from_s10(n)
        if deck_n in node_xyz:
            bmap[deck_n].add(int(dof) + 1)
    n_uy = sum(1 for n, ds in bmap.items() if 2 in ds)
    uy_frac = n_uy / max(len(node_xyz), 1)
    print(f"BC nodes {len(bmap)}  UY nodes {n_uy}  uy_frac {uy_frac:.4f}")
    if n_uy >= len(node_xyz) * 0.90:
        raise SystemExit("UY GATE FAIL: all-mesh UY pin detected (forbidden)")
    if uy_frac >= UY_FRAC_MAX:
        raise SystemExit(f"UY GATE FAIL: uy_frac={uy_frac:.4f} >= {UY_FRAC_MAX}")
    if n_uy == 0:
        raise SystemExit("UY GATE FAIL: zero UY supports (rigid-body Y unconstrained)")

    push("** BOUNDARY cards written node-by-node from S10 D,UX/UY/UZ mapped to kept")
    push("** stations plus downpull anchors. No NALL,UY card exists on this deck.")
    push("*BOUNDARY")
    for n in sorted(bmap):
        for dof in sorted(bmap[n]):
            push(f"{n}, {dof}, {dof}")
    push("*NSET, NSET=NSUPP")
    for n in sorted(bmap):
        push(f"{n}")
    push("*NSET, NSET=N_UY")
    uy_nodes = [n for n in sorted(bmap) if 2 in bmap[n]]
    for n in uy_nodes:
        push(f"{n}")
    push("*NSET, NSET=N_UX")
    for n in (n for n in sorted(bmap) if 1 in bmap[n]):
        push(f"{n}")
    push("*NSET, NSET=N_UZ")
    for n in (n for n in sorted(bmap) if 3 in bmap[n]):
        push(f"{n}")

    # ---- CP rings -> equations (masters remapped like slaves) -----------------
    def mapped_node(n: int):
        n = int(n)
        deck_n = deck_id_from_s10(n)
        if deck_n in node_xyz:
            return deck_n
        key = node_owner.get(n)
        if key is None:
            return None
        x = pos[n][0]
        k = int(np.argmin(np.abs(grid - x)))
        return node_id.get((key, k))

    eq_lines = []
    missing_master = []
    for cp in cp_sets:
        dof = int(cp[1]) + 1
        master = mapped_node(int(cp[2]))
        if master is None:
            missing_master.append(int(cp[2]))
            continue
        slaves = set()
        for n in cp[3:]:
            s_node = mapped_node(int(n))
            if s_node is not None:
                slaves.add(s_node)
        for s_node in sorted(slaves):
            if s_node == master:
                continue
            eq_lines.append((s_node, dof, master))
    if missing_master:
        raise SystemExit(f"CP master nodes missing from deck: {sorted(set(missing_master))}")
    for dup, orig in pass_hinge_pairs:
        for dof in (1, 2, 3):
            eq_lines.append((dup, dof, orig))
    for _, dup, orig in pass_spin_ties:
        for dof in (1, 2, 3, 5):
            eq_lines.append((dup, dof, orig))
    if eq_lines:
        push("*EQUATION")
        for s_node, dof, master in eq_lines:
            push("2")
            push(f"{s_node}, {dof}, 1.0, {master}, {dof}, -1.0")
    print(f"equations: {len(eq_lines)}")

    # ---- steps (gravity + prestress only; no personnel / wind in this chain) -
    push("** STEP 1: NLGEOM static, single increment. Load = GRAV only.")
    push("** Prestress is *INITIAL CONDITIONS,TYPE=STRESS (8 IP, global PK2).")
    push("** No CLOAD live load, no wind pressure on this step.")
    push("*STEP, NLGEOM, INC=200")
    push("*STATIC")
    push("1.0, 1.0, 1e-6, 1.0")
    push("*DLOAD")
    for name, ids in elsets.items():
        if ids:
            push(f"{name}, GRAV, {G_MM}, 0.0, 0.0, -1.0")
    push("*NODE FILE")
    push("U")
    push("*NODE PRINT, NSET=NSUPP")
    push("RF")
    push("** RF via NSUPP print without TOTALS (ccx 2.21 *NODE PRINT,TOTALS segfaults)")
    push("*END STEP")
    push("** STEP 2: perturbation frequency on the prestressed tangent stiffness.")
    push("** Does not read attachment 2-3 target frequencies.")
    push("*STEP, PERTURBATION")
    push("*FREQUENCY")
    push(f"{MODES}")
    push("*NODE FILE")
    push("U")
    push("*END STEP")

    dest = SOL / f"{CCX_JOB}.inp"
    h = hashlib.sha256()
    nbytes = 0
    with dest.open("w", encoding="utf-8") as fh:
        for line in lines_out:
            rec = line + "\n"
            fh.write(rec)
            raw = rec.encode()
            h.update(raw)
            nbytes += len(raw)
    del lines_out
    deck_sha = h.hexdigest()
    print(f"deck written rss_mb={_rss_mb():.0f} bytes={nbytes}")

    rope_base_t = 0.0
    for key in GK:
        g = groups[key]
        for e in elsets[f"E_ROPE_{key}"]:
            rope_base_t += RHO[g["tag"]] * g["A_eq"] * elem_meta[e]["L"]
    dp_base_t = sum(RHO["downpull"] * DOWNPULL_A * elem_meta[e]["L"] for e in elsets["E_DOWNPULL"])
    extra_t = sum(elem_extra.values())
    manifest = {
        "deck_sha256": deck_sha,
        "grid_stations": int(len(grid)),
        "coarsen": COARSEN,
        "groups": {k: {"n_ropes": groups[k]["n"], "y_eq_m": round(groups[k]["y_eq"] / 1e3, 4),
                       "A_eq_mm2": round(groups[k]["A_eq"], 2)} for k in GK},
        "elements": {name: len(ids) for name, ids in elsets.items() if ids},
        "elements_total": len(elem_def),
        "nodes_total": len(node_xyz),
        "portals": portal_count,
        "passages": 0 if skip_passages else len(pass_x),
        "diagnostic_skip_passages": skip_passages,
        "diagnostic_passage_hinge": passage_hinge,
        "diagnostic_passage_i_scale": passage_i_scale,
        "passages_raw_x_stations": len(pass_x_raw),
        "passages_cluster_gap_mm": PASSAGE_CLUSTER_GAP_MM,
        "passages_note": (
            f"R5: {len(pass_x)} equivalent beams from {len(pass_x_raw)} sec-63 "
            f"x-stations clustered at {PASSAGE_CLUSTER_GAP_MM:.0f} mm"
        ),
        "ic_elements": ic_n,
        "boundary_nodes": len(bmap),
        "boundary_uy_nodes": n_uy,
        "boundary_uy_frac": uy_frac,
        "uy_gate": {
            "rule": "UY only at S10-mapped supports; forbid all-mesh UY=0",
            "uy_frac_max": UY_FRAC_MAX,
            "uy_frac": uy_frac,
            "pass": bool(uy_frac < UY_FRAC_MAX and n_uy < 0.9 * len(node_xyz) and n_uy > 0),
        },
        "equations": len(eq_lines),
        "density_bins": len(bins),
        "mass_ledger_t": {
            "rope_base": rope_base_t, "downpull_base": dp_base_t,
            "mass21_folded": extra_t,
            "total": rope_base_t + dp_base_t + extra_t,
            "s10_reference": 4108.466907580,
        },
        "dropped_F_loads": {"n": int(len(floads)),
                            "sum_kN": float(floads[:, 1].sum() / 1e3),
                            "reason": "sum(F)/g == sum(MASS21) exactly; folded densities carry weight"},
        "simplifications": ["R1 band-merge 8/3 ropes", "R2 coarsen x4 (~7.9 m)",
                            "R3 parametric portals shared-node", "R4 smeared crossrows",
                            "R5 passage 2-chord equivalent beam", "R6 MASS21->density bins",
                            "R7 ROTY file skipped"],
    }
    (ART / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps(manifest["mass_ledger_t"], indent=1))
    print(json.dumps(manifest["elements"], indent=1))
    print("nodes:", manifest["nodes_total"], " deck bytes:", nbytes)


if __name__ == "__main__":
    main()
