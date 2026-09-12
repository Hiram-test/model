#!/usr/bin/env python3
"""Build the extreme-weather response atlas (图谱) from the sweep outputs.

A1 heatmap          scenarios x channels, normalized to site_sutong_100yr_obs
A2 alongspan_family selected events, dashed = reference_only
A3 survival         span-max L/V vs U10; non-stationary hatched in legend
A4 comparison       design-anchor along-span vs 附件2-3 表5-1 three stations
                    (comparison node only; extract is not used by the solver)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
ATLAS = ART / "atlas"
SELECT_ALONGSPAN = [
    "site_sutong_100yr_obs", "infa_2021_zhoushan", "doksuri_2023_jinjiang",
    "meranti_2016_peak", "ss_cat5", "funing_2016_ef4", "barrow_olivia_1996",
]
TOWERS_M = (714.5, 2995.3)
MAIN_L = 2995.3 - 714.5
ANCHOR = "site_sutong_100yr_obs"
NONSTAT = {"tornado", "downburst", "derecho"}


def _hatch_nonstat(ax, sweep, y_positions):
    for i, row in sweep.iterrows():
        if row["category"] in NONSTAT:
            ax.add_patch(Rectangle((-0.5, y_positions[i] - 0.5), 20, 1,
                                   fill=False, hatch="////", edgecolor="0.4", lw=0))


def main() -> None:
    ATLAS.mkdir(exist_ok=True)
    sweep = pd.read_csv(ART / "extreme_sweep_responses.csv")
    sweep = sweep[sweep["status"] == "OK"].reset_index(drop=True)
    lib = {s["id"]: s for s in json.loads(
        (ART / "extreme_weather_library.json").read_text())["scenarios"]}
    man = json.loads((ART / "true3d_model_manifest.json").read_text())
    foot = f"deck {man['deck_sha256'][:12]}  COARSEN={man['coarsen']}  not a scientific claim"

    # ---- A1 heatmap --------------------------------------------------------
    cols = ["rms_L_max_mm", "rms_V_max_mm", "rms_Tcw_max_rad", "rms_Tg_max_rad",
            "peak_L_mm", "peak_V_mm"]
    labels = ["RMS L", "RMS V", "RMS Tcw", "RMS Tg", "peak L", "peak V"]
    anc = sweep.set_index("id").loc[ANCHOR, cols].astype(float)
    mat = sweep[cols].astype(float).to_numpy() / anc.to_numpy()
    order = sweep.sort_values(["category", "U10"]).index.to_numpy()
    mat = mat[order]
    names = sweep.loc[order, "id"].tolist()
    fig, ax = plt.subplots(figsize=(8.2, 11.5))
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, rotation=25, ha="right")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=6)
    for i, sid in enumerate(names):
        if lib[sid]["category"] in NONSTAT:
            ax.add_patch(Rectangle((-0.5, i - 0.5), len(labels), 1,
                                   fill=False, hatch="////", edgecolor="0.35", lw=0.3))
    fig.colorbar(im, ax=ax, shrink=0.5, label=f"value / {ANCHOR}")
    ax.set_title("A1  scenario heatmap  (//// = reference_only)")
    fig.text(0.01, 0.005, foot, fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(ATLAS / "heatmap_scenarios.png", dpi=160)
    plt.close()

    # ---- A2 along-span -----------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), sharex=True)
    chans = [("rms_L_mm", "lateral RMS [mm]"), ("rms_V_mm", "vertical RMS [mm]"),
             ("rms_Tcw_rad", "T per-catwalk RMS [rad]"), ("rms_Tg_rad", "T global RMS [rad]")]
    for sid in SELECT_ALONGSPAN:
        p = ART / f"buffeting_rms_alongspan_{sid}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        style = "--" if lib[sid]["category"] in NONSTAT else "-"
        for ax, (col, _) in zip(axes.ravel(), chans):
            ax.plot(df.x_m, df[col], style, lw=1.15, label=sid)
    for ax, (_, ttl) in zip(axes.ravel(), chans):
        for tx in TOWERS_M:
            ax.axvline(tx, color="k", lw=0.5, alpha=0.4)
        ax.set_ylabel(ttl, fontsize=8)
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=6, ncol=2)
    axes[1, 0].set_xlabel("x [m]")
    axes[1, 1].set_xlabel("x [m]")
    fig.suptitle("A2  buffeting RMS along span  (dashed = reference_only)")
    fig.text(0.01, 0.005, foot, fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(ATLAS / "alongspan_family.png", dpi=160)
    plt.close()

    # ---- A3 survival / U10 scatter ----------------------------------------
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for cat, g in sweep.groupby("category"):
        m = "x" if cat in NONSTAT else "o"
        ax.scatter(g.U10, g.rms_L_max_mm / 1e3, marker=m, s=28, label=cat, alpha=0.85)
    ax.set_xlabel("U10 [m/s]")
    ax.set_ylabel("span-max lateral RMS [m]")
    ax.axvline(38.9, color="C0", ls=":", lw=0.8, label="Sutong site anchor 38.9 m/s")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    ax.set_title("A3  L-RMS vs U10  (x = tornado/downburst/derecho reference_only)")
    fig.text(0.01, 0.005, foot + "  utilization channel omitted (no reconstructed cable force)",
             fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(ATLAS / "survival_frontier.png", dpi=160)
    plt.close()

    # ---- A4 attach23 three-station overlay (comparison only) ---------------
    ext = json.loads((ART / "attach23_extract.json").read_text())
    p = ART / f"buffeting_rms_alongspan_{ANCHOR}.csv"
    df = pd.read_csv(p)
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 8.0), sharex=True)
    axes[0].plot(df.x_m, df.rms_L_mm / 1e3, "C0-", lw=1.3, label=f"{ANCHOR} L RMS")
    axes[1].plot(df.x_m, df.rms_V_mm / 1e3, "C1-", lw=1.3, label=f"{ANCHOR} V RMS")
    axes[2].plot(df.x_m, np.degrees(df.rms_Tcw_rad), "C2-", lw=1.3, label=f"{ANCHOR} Tcw RMS")
    xs = [TOWERS_M[0] + f * MAIN_L for f in (0.25, 0.50, 0.75)]
    for st, x in zip(ext["table_5_1_V10_30p1_ms"]["stations"], xs):
        axes[0].plot(x, st["lat_rms_m"], "ks", ms=7)
        axes[1].plot(x, st["vert_rms_m"], "ks", ms=7)
        axes[2].plot(x, st["tors_rms_deg"], "ks", ms=7)
    axes[0].plot([], [], "ks", label="attach 5-1 V10=30.1 three stations")
    for ax, ttl in zip(axes, ("L RMS [m]",
                              "V RMS [m] (table 5-1 vertical includes static sag)",
                              "T RMS [deg]")):
        for tx in TOWERS_M:
            ax.axvline(tx, color="k", lw=0.5, alpha=0.4)
        ax.set_ylabel(ttl, fontsize=8)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    axes[-1].set_xlabel("x [m]")
    fig.suptitle("A4  design-anchor vs Attachment 2-3 table 5-1  (comparison only; U10 not matched)")
    fig.text(0.01, 0.005, foot, fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(ATLAS / "comparison_attach23.png", dpi=160)
    plt.close()
    print("wrote A1-A4 under", ATLAS)


if __name__ == "__main__":
    main()
