#!/usr/bin/env python3
"""Master-curve continuous atlas (outline §2.2).

Build a regular (U10, Iu) response surface by direct buffeting on a grid,
then query by bilinear interpolation. Cross-validate at the 43 named events
against their already-computed direct values. Gate: max |rel err| of
span-max L/V/Tcw/Tg < 5% on stationary events; non-stationary events are
reported but do not fail the gate (they are reference_only).

Outputs
  artifacts/atlas/master_surface.npz
  artifacts/atlas/master_surface_cv.json
  artifacts/atlas/master_curve_cv_hist.png
  artifacts/atlas/A5_master_surface.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from buffeting import load_basis, run_scenario

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
ATLAS = ART / "atlas"
ATLAS.mkdir(exist_ok=True)

U_GRID = np.array([18.0, 26.0, 32.0, 39.0, 48.0, 58.0, 70.0, 85.0, 100.0])
IU_GRID = np.array([0.10, 0.12, 0.15, 0.20, 0.25])
CHANS = ["L_mm", "V_mm", "Tcw_rad", "Tg_rad"]
CV_MAX = 0.05
NONSTAT = {"tornado", "downburst", "derecho"}


def _one(U10, Iu, mb, cfg):
    sc = {"id": f"grid_U{U10:g}_Iu{Iu:g}", "U10_sustained_ms": float(U10), "Iu": float(Iu)}
    s = run_scenario(sc, mb, cfg, tag="_grid")
    return [s["rms_max"]["L_mm"], s["rms_max"]["V_mm"],
            s["rms_max"]["Tcw_rad"], s["rms_max"]["Tg_rad"]]


def build_surface(mb, cfg):
    cube = np.zeros((len(U_GRID), len(IU_GRID), 4))
    for i, U in enumerate(U_GRID):
        for j, Iu in enumerate(IU_GRID):
            print(f"grid {i+1}/{len(U_GRID)} U={U} Iu={Iu}", flush=True)
            cube[i, j] = _one(U, Iu, mb, cfg)
    return cube


def interpolators(cube):
    out = {}
    for k, name in enumerate(CHANS):
        out[name] = RegularGridInterpolator(
            (U_GRID, IU_GRID), cube[:, :, k],
            bounds_error=False, fill_value=None)
    return out


def query(interps, U10, Iu):
    pt = np.array([[U10, Iu]])
    return {n: float(interps[n](pt)[0]) for n in CHANS}


def main() -> None:
    cfg = json.loads((BASE / "config/site_wind.json").read_text())
    mb = load_basis(ART / "modal_basis.npz")
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    sweep = pd.read_csv(ART / "extreme_sweep_responses.csv")
    sweep = sweep[sweep["status"] == "OK"]

    dest = ATLAS / "master_surface.npz"
    if dest.exists():
        d = np.load(dest)
        cube = d["cube"]
        print("loaded existing master_surface.npz")
    else:
        cube = build_surface(mb, cfg)
        np.savez_compressed(dest, U=U_GRID, Iu=IU_GRID, cube=cube,
                            channels=np.array(CHANS),
                            version="v1_attach23_aero",
                            deck_sha=json.loads((ART / "true3d_model_manifest.json").read_text())["deck_sha256"])
        print("wrote", dest)

    interps = interpolators(cube)
    rows = []
    for _, r in sweep.iterrows():
        pred = query(interps, float(r.U10), float(r.Iu))
        truth = {"L_mm": r.rms_L_max_mm, "V_mm": r.rms_V_max_mm,
                 "Tcw_rad": r.rms_Tcw_max_rad, "Tg_rad": r.rms_Tg_max_rad}
        rec = {"id": r.id, "category": r.category, "stationarity": r.stationarity,
               "U10": float(r.U10), "Iu": float(r.Iu)}
        rels = []
        for n in CHANS:
            t, p = float(truth[n]), pred[n]
            rel = (p - t) / t if t else 0.0
            rec[f"truth_{n}"] = t
            rec[f"pred_{n}"] = p
            rec[f"rel_{n}"] = rel
            rels.append(abs(rel))
        rec["rel_max_abs"] = max(rels)
        rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(ATLAS / "master_surface_cv.csv", index=False)
    stat = df[df.stationarity == "stationary_ok"]
    errs = stat["rel_max_abs"].to_numpy()
    gate = {
        "n_stationary": int(len(stat)),
        "n_reference_only": int((df.stationarity != "stationary_ok").sum()),
        "mae_rel_max": float(errs.mean()),
        "p95_rel_max": float(np.quantile(errs, 0.95)),
        "max_rel": float(errs.max()),
        "worst_id": str(stat.loc[stat.rel_max_abs.idxmax(), "id"]),
        "threshold": CV_MAX,
        "pass": bool(errs.max() < CV_MAX),
        "method": "RegularGridInterpolator on direct-buffeting (U,Iu) grid; not a silent relaxation",
        "grid_U": U_GRID.tolist(),
        "grid_Iu": IU_GRID.tolist(),
    }
    (ATLAS / "master_surface_cv.json").write_text(json.dumps(gate, indent=2))
    print(json.dumps(gate, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.hist(100 * errs, bins=12, color="#1f618d", edgecolor="w")
    ax.axvline(100 * CV_MAX, color="#b03a2e", ls="--", label="5% gate")
    ax.set_xlabel("max |rel err| of 4 channels [%]")
    ax.set_ylabel("stationary events")
    ax.set_title("Master-surface CV vs 43-event direct (stationary only)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ATLAS / "master_curve_cv_hist.png", dpi=150)
    plt.close()

    # A5 four-panel P50 surface + event scatter
    UU, II = np.meshgrid(U_GRID, IU_GRID, indexing="ij")
    fig, axes = plt.subplots(2, 2, figsize=(10.8, 8.2))
    titles = ["L RMS [m]", "V RMS [m]", "Tcw RMS [rad]", "Tg RMS [rad]"]
    scales = [1e-3, 1e-3, 1.0, 1.0]
    for ax, k, ttl, sc in zip(axes.ravel(), range(4), titles, scales):
        cs = ax.contourf(UU, II, cube[:, :, k] * sc, levels=12, cmap="YlOrRd")
        fig.colorbar(cs, ax=ax, shrink=0.8)
        for _, r in sweep.iterrows():
            m = "x" if r.category in NONSTAT else "o"
            ax.plot(r.U10, r.Iu, m, ms=4, color="k", alpha=0.7)
        ax.set_title(ttl, fontsize=9)
        ax.set_xlabel("U10 [m/s]")
        ax.set_ylabel("Iu")
    fig.suptitle("A5  master surface (grid P50) + 43 events  (x = reference_only)")
    man = json.loads((ART / "true3d_model_manifest.json").read_text())
    fig.text(0.01, 0.005,
             f"deck {man['deck_sha256'][:12]}  atlas v1_attach23_aero  not a scientific claim",
             fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(ATLAS / "A5_master_surface.png", dpi=160)
    plt.close()
    print("wrote A5 and CV histogram")


if __name__ == "__main__":
    main()
