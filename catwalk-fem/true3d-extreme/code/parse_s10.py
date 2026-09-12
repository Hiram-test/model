#!/usr/bin/env python3
"""Parse the S10 (attachment-2-3 aligned V2.0) MAPDL source into a normalized model.

Sources (export from origin/main ultra_runs/S10_SECTION_SHEAR_20260716T050342389124Z/solver
into /tmp/s10; see ../README for the exact git-show commands):
  mesh.inp                                    N + LINK10/BEAM4 E blocks (elem ids 1..122308)
  apply_mct_downpull_equivalent_xlong.inp     4 downpull LINK + CP rings + D
  apply_finite_gates_and_passages_v2.inp      BEAM188 gates/passages + CERIG
  apply_mct_constraints_xlong.inp             D anchor masks
  apply_mct_authoritative_initial_state_link180.inp  INISTATE per rope element
  apply_authoritative_mct_deadload_v1.inp     MP DENS overrides + F second-stage loads
  mass21_nodes.csv                            33k dynamic masses with roles

Output: artifacts/s10_model.npz + s10_parse_report.json
Units: N, mm, tonne, s. X longitudinal, Y transverse, Z vertical.

Verified facts (2026-08-28 run before pod loss):
  44 rope lines = 32 bearing (2155 el each, sigma~472.4 MPa, T~655 kN/rope)
               + 12 gantry (394 el each, z = bearing + ~8.5 m, T~533.8 kN/rope);
  crossbeam rows 1430 @ ~2.948 m alternating box100x100x4 / box50x50x4,
  17 segments per catwalk per row; 142 gate frames (4 components each);
  21 passages (639 el each, full width y +-24.86 m, depth 1.855 m);
  sum(F)/g = 963.811381 t = sum(MASS21) exactly; towers x = 714.5 / 2995.3 m.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

SRC = Path("/tmp/s10")
OUT = Path(__file__).resolve().parent.parent / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)

BEARING_A = 1393.668228093791   # sec30, per physical bearing rope (MCT sect1 /16)
GANTRY_A = 1400.496622996084    # sec32, per gantry rope (MCT sect2 /6)
DOWNPULL_A = 22298.691649500659 # sec33


def parse_mesh():
    nodes: dict[int, tuple[float, float, float]] = {}
    elems = []  # (eid, n1, n2, etype, mat)
    etype = mat = None
    eid = 0
    with open(SRC / "mesh.inp") as f:
        for raw in f:
            line = raw.split("!", 1)[0].strip()
            if not line:
                continue
            if line.startswith("N,"):
                p = line.split(",")
                nodes[int(p[1])] = (float(p[2]), float(p[3]), float(p[4]))
            elif line.startswith("TYPE,"):
                etype = int(line.split(",")[1])
            elif line.startswith("MAT,"):
                mat = int(line.split(",")[1])
            elif line.startswith("E,"):
                p = line.split(",")
                eid += 1
                elems.append((eid, int(p[1]), int(p[2]), etype, mat))
    return nodes, elems


def parse_downpull():
    nodes, elems, cps, ds = {}, [], [], []
    with open(SRC / "apply_mct_downpull_equivalent_xlong.inp") as f:
        for raw in f:
            line = raw.split("!", 1)[0].strip()
            if line.startswith("N,"):
                p = line.split(",")
                nodes[int(p[1])] = (float(p[2]), float(p[3]), float(p[4]))
            elif line.startswith("EN,"):
                p = line.split(",")
                elems.append((int(p[1]), int(p[2]), int(p[3])))
            elif line.startswith("CP,"):
                p = line.split(",")
                cps.append({"id": int(p[1]), "dof": p[2], "nodes": [int(x) for x in p[3:] if x]})
            elif line.startswith("D,"):
                p = line.split(",")
                ds.append((int(p[1]), p[2]))
    return nodes, elems, cps, ds


def parse_constraints():
    ds = []
    with open(SRC / "apply_mct_constraints_xlong.inp") as f:
        for raw in f:
            line = raw.split("!", 1)[0].strip()
            if line.startswith("D,"):
                p = line.split(",")
                ds.append((int(p[1]), p[2]))
    return ds


def parse_inistate():
    sig = {}
    with open(SRC / "apply_mct_authoritative_initial_state_link180.inp") as f:
        for raw in f:
            if raw.startswith("INISTATE,DEFINE"):
                p = raw.strip().split(",")
                sig[int(p[2])] = float(p[6])
    return sig


def parse_deadload():
    dens = {}
    floads = []
    with open(SRC / "apply_authoritative_mct_deadload_v1.inp") as f:
        for raw in f:
            line = raw.split("!", 1)[0].strip()
            if line.startswith("MP,DENS,"):
                p = line.split(",")
                dens[int(p[2])] = float(p[3])
            elif line.startswith("F,"):
                p = line.split(",")
                floads.append((int(p[1]), float(p[3])))
    return dens, floads


def parse_gates():
    nodes, elems, cerigs = {}, [], []
    sec = None
    with open(SRC / "apply_finite_gates_and_passages_v2.inp") as f:
        for raw in f:
            line = raw.split("!", 1)[0].strip()
            if not line:
                continue
            if line.startswith("SECNUM,"):
                sec = int(line.split(",")[1])
            elif line.startswith("N,"):
                p = line.split(",")
                nodes[int(p[1])] = (float(p[2]), float(p[3]), float(p[4]))
            elif line.startswith("EN,"):
                p = line.split(",")
                elems.append((int(p[1]), int(p[2]), int(p[3]), int(p[4]) if len(p) > 4 else 0, sec))
            elif line.startswith("CERIG,"):
                p = line.split(",")
                cerigs.append((int(p[1]), int(p[2]), p[3]))
    return nodes, elems, cerigs


def parse_mass_csv():
    rows = []
    with open(SRC / "mass21_nodes.csv") as f:
        f.readline()
        for raw in f:
            p = raw.rstrip("\n").split(",")
            rows.append((int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), p[8]))
    return rows  # (node, x, y, z, mass_t, role)


def trace_lines(elem_list, tag):
    """Decompose rope elements into polylines split at degree!=2 junctions."""
    adj = defaultdict(list)
    for eid, n1, n2 in elem_list:
        adj[n1].append((n2, eid))
        adj[n2].append((n1, eid))
    used = set()
    lines = []
    endpoints = [n for n, a in adj.items() if len(a) != 2]
    seeds = endpoints + [n for n, a in adj.items() if len(a) == 2]
    for s in seeds:
        for nxt, eid in adj[s]:
            if eid in used:
                continue
            chain_nodes = [s]
            chain_eids = []
            nxt_node, nxt_eid = nxt, eid
            while True:
                used.add(nxt_eid)
                chain_eids.append(nxt_eid)
                chain_nodes.append(nxt_node)
                cur = nxt_node
                cand = [(m, e) for (m, e) in adj[cur] if e not in used]
                if len(adj[cur]) != 2 or not cand:
                    break
                nxt_node, nxt_eid = cand[0]
            lines.append({"tag": tag, "nodes": chain_nodes, "eids": chain_eids})
    return lines


def main():
    nodes, elems = parse_mesh()
    dp_nodes, dp_elems, cps, dp_ds = parse_downpull()
    nodes.update(dp_nodes)
    g_nodes, g_elems, cerigs = parse_gates()
    ds = parse_constraints() + dp_ds
    sig = parse_inistate()
    dens, floads = parse_deadload()
    masses = parse_mass_csv()

    bearing = [(e, a, b) for (e, a, b, t, m) in elems if t == 1 and m == 1]
    gantry = [(e, a, b) for (e, a, b, t, m) in elems if t == 1 and m == 2]
    cross3 = [(e, a, b) for (e, a, b, t, m) in elems if t == 2 and m == 3]
    cross4 = [(e, a, b) for (e, a, b, t, m) in elems if t == 2 and m == 4]

    lines = trace_lines(bearing, "bearing") + trace_lines(gantry, "gantry")
    rep = {
        "counts": {
            "mesh_nodes": len(nodes) - len(dp_nodes),
            "bearing_el": len(bearing), "gantry_el": len(gantry),
            "cross_large_el": len(cross3), "cross_small_el": len(cross4),
            "gate_nodes": len(g_nodes), "gate_pass_el": len(g_elems), "cerig": len(cerigs),
            "D": len(ds), "CP": len(cps), "inistate": len(sig), "F": len(floads),
            "mass21": len(masses),
        },
        "dens": dens,
        "lines": [],
    }

    for i, ln in enumerate(sorted(lines, key=lambda l: -len(l["eids"]))):
        xyz = np.array([nodes[n] for n in ln["nodes"]])
        A = BEARING_A if ln["tag"] == "bearing" else GANTRY_A
        s_vals = [sig.get(e, 0.0) for e in ln["eids"]]
        rep["lines"].append({
            "i": i, "tag": ln["tag"], "n_el": len(ln["eids"]),
            "x_range_m": [round(xyz[:, 0].min() / 1e3, 2), round(xyz[:, 0].max() / 1e3, 2)],
            "y_mean_m": round(float(xyz[:, 1].mean()) / 1e3, 4),
            "z_range_m": [round(xyz[:, 2].min() / 1e3, 2), round(xyz[:, 2].max() / 1e3, 2)],
            "sigma_mean_MPa": round(float(np.mean(s_vals)), 3),
            "T_mid_kN": round(float(np.median(s_vals)) * A / 1e3, 1),
        })

    m21 = sum(r[4] for r in masses)
    rep["sums"] = {
        "mass21_total_t": round(m21, 6),
        "F_total_kN": round(sum(v for _, v in floads) / 1e3, 3),
        "F_over_g_t": round(-sum(v for _, v in floads) / 9806.0, 6),
    }

    with open(OUT / "s10_parse_report.json", "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)

    node_ids = np.array(sorted(nodes))
    node_xyz = np.array([nodes[i] for i in node_ids])
    gnode_ids = np.array(sorted(g_nodes))
    gnode_xyz = np.array([g_nodes[i] for i in gnode_ids])
    np.savez_compressed(
        OUT / "s10_model.npz",
        node_ids=node_ids, node_xyz=node_xyz,
        gnode_ids=gnode_ids, gnode_xyz=gnode_xyz,
        bearing=np.array(bearing), gantry=np.array(gantry),
        cross_large=np.array(cross3), cross_small=np.array(cross4),
        gate_elems=np.array([(e, i_, j_, s) for (e, i_, j_, k_, s) in g_elems]),
        cerigs=np.array([(m, s, {"UXYZ": 0, "ALL": 1}[md]) for (m, s, md) in cerigs]),
        ds=np.array([(n, {"UX": 0, "UY": 1, "UZ": 2, "ROTY": 4}[d]) for (n, d) in ds]),
        dp_elems=np.array(dp_elems),
        cp_sets=np.array([[c["id"]] + [{"UX": 0, "UY": 1, "UZ": 2}[c["dof"]]] + c["nodes"] for c in cps], dtype=object),
        inistate_eids=np.array(sorted(sig)),
        inistate_sig=np.array([sig[e] for e in sorted(sig)]),
        floads=np.array(floads),
        masses=np.array([(r[0], r[1], r[2], r[3], r[4]) for r in masses]),
        mass_roles=np.array([r[5] for r in masses]),
        dens_mat=np.array([[k, v] for k, v in sorted(dens.items())]),
    )
    print(json.dumps({k: rep[k] for k in ("counts", "sums", "dens")}, ensure_ascii=False, indent=1))
    print("lines:", len(rep["lines"]))


if __name__ == "__main__":
    main()
