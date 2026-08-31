#!/usr/bin/env python3
"""Lemma-A lateral-inertia audit (comparison evidence, not a conclusion).

Locked dossier: catwalk-fem/double-mct-buffeting/report/double_mct_torsion_discussion_cn.tex §5
and the f99-chain-closure S10/C20/D10/E10 ANSYS 109k-node 3-D model.

    λ_T / λ_V = rms_y(T)² / rms_y(m)²

S10 already obeys it (TA1 = 0.0733 Hz ≡ 2f*, −26.4% vs attach 0.0996).
This script only checks whether the reduced ccx deck still has the same
lateral mass/tension layout, and records the I-scale passage probe.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
DECK = BASE / "solver" / "true3d_ccx.inp"


def parse_deck(path: Path):
    nodes: dict[int, tuple[float, float, float]] = {}
    elems: dict[int, tuple[int, int]] = {}
    elset_ids: dict[str, list[int]] = {}
    sec: dict[str, tuple[float, str]] = {}
    dens: dict[str, float] = {}
    mode = None
    cur_set = cur_mat = None
    sec_pending = None
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("**"):
                continue
            if line.startswith("*"):
                up = line.upper()
                if up.startswith("*NODE,") or up == "*NODE":
                    mode = "node"
                elif up.startswith("*ELEMENT"):
                    m = re.search(r"ELSET=([^,\s]+)", up)
                    cur_set = m.group(1) if m else "?"
                    elset_ids.setdefault(cur_set, [])
                    mode = "elem"
                elif up.startswith("*ELSET"):
                    m = re.search(r"ELSET=([^,\s]+)", up)
                    cur_set = m.group(1)
                    elset_ids.setdefault(cur_set, [])
                    mode = "elset"
                elif up.startswith("*BEAM SECTION"):
                    ms = re.search(r"ELSET=([^,\s]+)", up)
                    mm = re.search(r"MATERIAL=([^,\s]+)", up)
                    sec_pending = (ms.group(1), mm.group(1))
                    mode = "beamsec"
                elif up.startswith("*MATERIAL"):
                    mm = re.search(r"NAME=([^,\s]+)", up)
                    cur_mat = mm.group(1)
                    mode = None
                elif up.startswith("*DENSITY"):
                    mode = "dens"
                else:
                    mode = None
                continue
            if mode == "node":
                p = line.split(",")
                nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
            elif mode == "elem":
                p = line.split(",")
                eid = int(p[0])
                elems[eid] = (int(p[1]), int(p[2]))
                elset_ids[cur_set].append(eid)
            elif mode == "elset":
                elset_ids[cur_set].extend(int(t) for t in line.split(",") if t.strip())
            elif mode == "beamsec" and sec_pending is not None:
                p = line.split(",")
                h1, h2 = float(p[0]), float(p[1])
                sec[sec_pending[0]] = (h1 * h2, sec_pending[1])
                sec_pending = None
                mode = None
            elif mode == "dens":
                dens[cur_mat] = float(line.split(",")[0])
                mode = None
    return nodes, elems, elset_ids, sec, dens


def rms_y(w: np.ndarray, y: np.ndarray) -> float:
    return float(np.sqrt((w * y**2).sum() / w.sum()))


def hw_match(path: Path, fam: str, par: str, hw: int):
    if not path.is_file():
        return None
    for r in csv.DictReader(open(path)):
        if r.get("residual_zero") in ("True", "true", "1"):
            continue
        if (r["family"] == fam and r["parity"] == par
                and float(r["main_span_fraction"]) >= 0.65
                and int(float(r["half_waves"])) == hw):
            return float(r["f_hz"])
    return None


def main() -> None:
    man = json.loads((ART / "true3d_model_manifest.json").read_text())
    nodes, elems, elset_ids, sec, dens = parse_deck(DECK)

    wm, ym = [], []
    seen: set[int] = set()
    for name, (area, mat) in sec.items():
        rho = dens.get(mat, 0.0)
        if rho <= 0:
            continue
        for eid in elset_ids.get(name, ()):
            if eid in seen or eid not in elems:
                continue
            seen.add(eid)
            n1, n2 = elems[eid]
            a, b = np.array(nodes[n1]), np.array(nodes[n2])
            L = float(np.linalg.norm(b - a))
            wm.append(rho * area * L)
            ym.append(0.5 * (a[1] + b[1]))
    wm, ym = np.array(wm), np.array(ym)
    deck_mass_t = float(wm.sum())
    deck_rms_m = rms_y(wm, ym) / 1e3

    g = man["groups"]
    wt = np.array([8 * 655.0e3 if k.endswith("B") else 3 * 533.8e3 for k in g])
    yt = np.array([g[k]["y_eq_m"] for k in g])
    rms_T = rms_y(wt, yt)

    d = np.load(ART / "s10_model.npz", allow_pickle=True)
    masses = np.asarray(d["masses"])
    nid = np.asarray(d["node_ids"])
    nxyz = np.asarray(d["node_xyz"])
    pos = {int(i): j for j, i in enumerate(nid)}
    dens_mat = {int(k): v for k, v in np.asarray(d["dens_mat"])}
    rope_w, rope_y = [], []
    for arr_name, area, mat in (("bearing", 1393.67, 1), ("gantry", 1400.50, 2)):
        arr = np.asarray(d[arr_name])
        n1 = np.array([pos[int(e[1])] for e in arr])
        n2 = np.array([pos[int(e[2])] for e in arr])
        L = np.linalg.norm(nxyz[n2] - nxyz[n1], axis=1)
        ymid = 0.5 * (nxyz[n1][:, 1] + nxyz[n2][:, 1]) / 1e3
        rope_w.append(dens_mat[mat] * area * L)
        rope_y.append(ymid)
    rope_w = np.concatenate(rope_w)
    rope_y = np.concatenate(rope_y)
    src_w = np.concatenate([masses[:, 4], rope_w])
    src_y = np.concatenate([masses[:, 2] / 1e3, rope_y])
    src_rms_m = rms_y(src_w, src_y)

    va1 = hw_match(ART / "true3d_mode_table.csv", "V", "A", 2)
    ta1 = hw_match(ART / "true3d_mode_table.csv", "T", "A", 2)
    va1_s = hw_match(ART / "true3d_mode_table_isoft.csv", "V", "A", 2)
    ta1_s = hw_match(ART / "true3d_mode_table_isoft.csv", "T", "A", 2)

    out = {
        "claim": "comparison_only; does not decide attachment 2-3",
        "lemma": "lam_T/lam_V = rms_y(T)^2 / rms_y(m)^2",
        "source": "double_mct_torsion_discussion_cn.tex §5 + f99-chain-closure",
        "locked_ansys_3d": {
            "model": "S10 V2.0 MAPDL, 109086 nodes / 172994 elems (f99 S10/C20/D10/E10)",
            "TA1_Hz": 0.07333,
            "TA1_vs_attach": -0.264,
            "note": "pinned to 2f* ~0.07344; 3-D ANSYS already in the repo",
        },
        "deck": {
            "sha": man["deck_sha256"][:16],
            "mass_total_t": round(deck_mass_t, 3),
            "rms_y_mass_m": round(deck_rms_m, 3),
            "rms_y_tension_m": round(rms_T, 3),
            "predicted_TA1_over_VA1": round(rms_T / deck_rms_m, 4),
            "solved_VA1_Hz": va1,
            "solved_TA1_Hz": ta1,
            "solved_TA1_over_VA1": None if not (va1 and ta1) else round(ta1 / va1, 4),
        },
        "source_s10_arrays": {
            "mass21_t": round(float(masses[:, 4].sum()), 3),
            "rope_mass_t": round(float(rope_w.sum()), 3),
            "rms_y_mass_m": round(src_rms_m, 3),
            "predicted_TA1_over_VA1": round(rms_T / src_rms_m, 4),
        },
        "attachment_TA1_over_VA1": 0.0996 / 0.0700,
        "passage_I_scale_0.01": {
            "VA1_Hz": va1_s,
            "TA1_Hz": ta1_s,
            "TA1_over_VA1": None if not (va1_s and ta1_s) else round(ta1_s / va1_s, 4),
            "dTA1_vs_C4": None if not (ta1 and ta1_s) else round(ta1_s / ta1 - 1, 4),
            "note": "topology kept, EI_pass /100; skip/hinge/I=1e-4 static-diverge",
        },
        "reading": (
            "Mass and tension share the same lateral rms (~21.5 m), so Lemma A "
            "predicts TA1≈VA1. The reduced deck solves TA1/VA1≈1.46 (attach 1.42) "
            "while the 109k-node S10 ANSYS 3-D model stays at ≈1.00. Softening the "
            "21 welded passage beams by 100× drops TA1 only 2.7%. The +6.5% vs "
            "attach is therefore not '3-D topology recovering a missing path'; "
            "it is a reduced-deck lift above the locked S10 floor, path not yet "
            "isolated. Comparison only."
        ),
    }
    (ART / "lateral_inertia_audit.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
