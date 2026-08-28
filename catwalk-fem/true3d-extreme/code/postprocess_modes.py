#!/usr/bin/env python3
"""Modal post-processing for the true-3D catwalk ccx run.

Inputs : solver/true3d_ccx.frd (+ .dat), artifacts/true3d_model_manifest.json,
         artifacts/s10_model.npz (for reference table pairing sources see below)
Outputs: artifacts/modal_basis.npz        (freqs, mass-normalized shapes on rope nodes,
                                           tributary lengths, line tags, y_eq, per-catwalk
                                           torsion operators)
         artifacts/true3d_mode_table.csv  (mode #, f, family L/V/T, span, half-waves,
                                           per-catwalk vs global torsion split)
         artifacts/true3d_table41_pairing.csv (locked-rule pairing vs attachment 2-3)

ccx 2.21 quirks handled (bisected in the agentic-fea run of 2026-08-28):
  Q1 expanded-mesh node renumbering -> KDTree bucket back to deck nodes (<=400 mm)
  Q2 displacement lines in FRD -1 blocks may be shorter than 60 chars -> len>=48
  Q3 SPC reactions migrate to expanded knots -> use global force balance, not RF
Classification observables (per kept station x on each line group):
  L = mean lateral (uy), V = mean vertical (uz)
  T_catwalk(cw) = [uz(outer band) - uz(inner band)] / dy_bands   (per catwalk twist)
  T_global      = [uz(catwalk P) - uz(catwalk M)] / dy_catwalks  (anti-phase)
Family = argmax of span-integrated |observable|; half-waves = sign changes + 1.
Table 4-1 pairing follows the LOCKED rules of
  catwalk-fem/double-mct-buffeting/modal_validation (frequency-order within family,
  no half-wave MAC promotion, no TS2->TS3 re-pairing); reference CSV:
  catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/
  reference_attachment_2_3_table4_1.csv  (columns internal_id, frequency_hz)
Run:  python3 code/postprocess_modes.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

BASE = Path(__file__).resolve().parent.parent
SOL, ART = BASE / "solver", BASE / "artifacts"
REPO = BASE.parent.parent
REF_CSV = REPO / ("catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/"
                  "reference_attachment_2_3_table4_1.csv")
SNAP_MM = 400.0
# S10 towers (mm); used only for span-energy split, not imported from attachment
TOWER_X = (714.5e3, 2995.3e3)
F_ZERO = 5e-3          # numerical residual-RB cutoff (Hz)


def read_frd_coords(path: Path) -> tuple[np.ndarray, np.ndarray]:
    ids, xyz = [], []
    with open(path) as f:
        in_blk = False
        for line in f:
            if line.startswith("    2C"):
                in_blk = True
                continue
            if in_blk:
                if line.startswith(" -1"):
                    ids.append(int(line[3:13]))
                    xyz.append([float(line[13:25]), float(line[25:37]), float(line[37:49])])
                elif line.startswith(" -3"):
                    break
    return np.array(ids), np.array(xyz)


def read_frd_modes(path: Path):
    freqs, blocks = [], []
    with open(path) as f:
        cur = None
        for line in f:
            if line.startswith("    1PSTEP"):
                continue
            if " 100CL" in line[:8]:
                cur = {}
                blocks.append(cur)
                try:
                    freqs.append(float(line.split()[2]))
                except (IndexError, ValueError):
                    freqs.append(np.nan)
            elif cur is not None and line.startswith(" -1") and len(line) >= 48:
                nid = int(line[3:13])
                cur[nid] = np.array([float(line[13:25]), float(line[25:37]), float(line[37:49])])
            elif line.startswith(" -3"):
                pass
    return freqs, blocks


def read_dat_freqs(path: Path) -> list[float]:
    """Authoritative cycles/time column from ccx .dat EIGENVALUE OUTPUT."""
    freqs: list[float] = []
    in_ev = False
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if "E I G E N V A L U E" in raw:
                in_ev = True
                continue
            if not in_ev:
                continue
            if not line:
                if freqs:
                    break
                continue
            p = line.split()
            if len(p) >= 4 and p[0].isdigit():
                freqs.append(float(p[3]))
    if not freqs:
        raise SystemExit(f"no eigenvalues in {path}")
    return freqs


def main() -> None:
    manifest = json.loads((ART / "true3d_model_manifest.json").read_text())
    groups = manifest["groups"]

    # deck nodes from the inp (NODE block) -----------------------------------
    deck_nodes = {}
    with open(SOL / "true3d_ccx.inp") as f:
        in_nodes = False
        for line in f:
            if line.startswith("*NODE"):
                in_nodes = True
                continue
            if in_nodes:
                if line.startswith("*"):
                    break
                p = line.split(",")
                deck_nodes[int(p[0])] = [float(p[1]), float(p[2]), float(p[3])]
    ids = np.array(sorted(deck_nodes))
    xyz = np.array([deck_nodes[i] for i in ids])

    # bucket expanded FRD mesh back to deck nodes (Q1) ------------------------
    fids, fxyz = read_frd_coords(SOL / "true3d_ccx.frd")
    tree = cKDTree(xyz)
    dist, idx = tree.query(fxyz, k=1)
    keep = dist <= SNAP_MM
    bucket = {int(fi): int(j) for fi, j, k in zip(fids, idx, keep) if k}

    dat_freqs = read_dat_freqs(SOL / "true3d_ccx.dat")
    frd_freqs, blocks = read_frd_modes(SOL / "true3d_ccx.frd")
    # Static *NODE FILE writes one DISP block (100CL freq often 1.0 = step time).
    # Modal blocks are the last N, N = eigenvalue count from .dat.
    if len(blocks) < len(dat_freqs):
        raise SystemExit(f"FRD DISP blocks {len(blocks)} < .dat modes {len(dat_freqs)}")
    modal = blocks[-len(dat_freqs):]
    freqs = dat_freqs

    def collapse(block):
        acc = np.zeros((len(ids), 3))
        cnt = np.zeros(len(ids))
        for nid, u in block.items():
            j = bucket.get(nid)
            if j is not None:
                acc[j] += u
                cnt[j] += 1
        cnt[cnt == 0] = 1
        return acc / cnt[:, None]

    shapes = np.stack([collapse(b) for b in modal])  # (nm, nn, 3)

    # line-group masks on deck ids (100000*(g+1)+k numbering from builder) ----
    gk = sorted(groups)
    gsel = {key: (ids // 100000) == (i + 1) for i, key in enumerate(gk)}
    y_eq = {key: groups[key]["y_eq_m"] * 1e3 for key in gk}

    # observables per mode -----------------------------------------------------
    rows = []
    for m, (f, sh) in enumerate(zip(freqs, shapes), start=1):
        obs = {}
        for key in gk:
            s = gsel[key]
            obs[key] = {"x": xyz[s][:, 0], "uy": sh[s][:, 1], "uz": sh[s][:, 2]}
        def span_int(key, comp):
            o = obs[key]
            order = np.argsort(o["x"])
            return np.trapezoid(np.abs(o[comp][order]), o["x"][order])
        L = sum(span_int(k, "uy") for k in gk if k.endswith("B"))
        V = sum(span_int(k, "uz") for k in gk if k.endswith("B"))
        # per-catwalk twist from band differential (bearing lines)
        tw = []
        for cw in ("P", "M"):
            i_, o_ = obs[f"{cw}IB"], obs[f"{cw}OB"]
            n = min(len(i_["x"]), len(o_["x"]))
            dy = abs(y_eq[f"{cw}OB"] - y_eq[f"{cw}IB"])
            tw.append(np.trapezoid(np.abs(o_["uz"][:n] - i_["uz"][:n]), o_["x"][:n]) / dy)
        Tcw = sum(tw)
        zP = 0.5 * (obs["PIB"]["uz"] + obs["POB"]["uz"][: len(obs["PIB"]["uz"])])
        zM = 0.5 * (obs["MIB"]["uz"] + obs["MOB"]["uz"][: len(obs["MIB"]["uz"])])
        n = min(len(zP), len(zM))
        dyg = abs(0.5 * (y_eq["PIB"] + y_eq["POB"]) - 0.5 * (y_eq["MIB"] + y_eq["MOB"]))
        Tg = np.trapezoid(np.abs(zP[:n] - zM[:n]), obs["PIB"]["x"][:n]) / dyg
        fam = max((("L", L), ("V", V), ("T", (Tcw + Tg) * dyg)), key=lambda kv: kv[1])[0]
        # half waves on dominant bearing line; odd -> S (symmetric), even -> A
        o = obs["PIB"]
        xord = np.argsort(o["x"])
        comp = (o["uy"] if fam == "L" else o["uz"])[xord]
        xo = o["x"][xord]
        amp = np.abs(comp)
        thr = 0.05 * (amp.max() if amp.max() > 0 else 1.0)
        sgn = np.sign(comp[amp > thr])
        hw = int(np.sum(np.abs(np.diff(sgn)) > 0) + 1) if len(sgn) else 0
        parity = "S" if (hw % 2 == 1) else "A"
        # main-span energy fraction on PIB (towers from S10 parse, not attachment)
        main = (xo >= TOWER_X[0]) & (xo <= TOWER_X[1])
        e_all = float(np.trapezoid(amp, xo)) if len(xo) > 1 else 0.0
        e_main = float(np.trapezoid(amp[main], xo[main])) if main.sum() > 1 else 0.0
        main_frac = e_main / e_all if e_all > 0 else 0.0
        if main_frac >= 0.65:
            span = "main"
        elif float(np.trapezoid(amp[xo < TOWER_X[0]], xo[xo < TOWER_X[0]])) >= \
                float(np.trapezoid(amp[xo > TOWER_X[1]], xo[xo > TOWER_X[1]])):
            span = "side_NW"
        else:
            span = "side_SE"
        residual_zero = bool(f < F_ZERO)
        rows.append({"mode": m, "f_hz": f, "family": fam, "parity": parity,
                     "half_waves": hw, "main_span_fraction": main_frac,
                     "dominant_span": span, "residual_zero": residual_zero,
                     "L": L, "V": V, "T_catwalk": Tcw, "T_global": Tg})

    import csv
    with open(ART / "true3d_mode_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # modal basis for buffeting: drop numerical residual-RB (f < F_ZERO)
    keep = np.array([not r["residual_zero"] for r in rows])
    trib = np.zeros(len(ids))
    for key in gk:
        s = np.where(gsel[key])[0]
        xs = xyz[s][:, 0]
        o = np.argsort(xs)
        t = np.gradient(xs[o])
        trib[s[o]] = t
    np.savez_compressed(ART / "modal_basis.npz",
                        freqs=np.array(freqs)[keep], shapes=shapes[keep], node_ids=ids,
                        node_xyz=xyz, tributary_mm=trib,
                        group_keys=np.array(gk),
                        group_mask=np.stack([gsel[k] for k in gk]),
                        y_eq=np.array([y_eq[k] for k in gk]),
                        dropped_residual_zeros=int((~keep).sum()),
                        f_zero_hz=F_ZERO)
    n_zero = int((~keep).sum())
    print(f"modes: {len(freqs)} (structural {int(keep.sum())}, residual-zero {n_zero}); families:",
          {f: sum(1 for r in rows if r['family'] == f and not r['residual_zero']) for f in 'LVT'})
    print("wrote modal_basis.npz + true3d_mode_table.csv")


if __name__ == "__main__":
    main()
