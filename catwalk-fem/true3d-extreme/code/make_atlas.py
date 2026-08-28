#!/usr/bin/env python3
"""Build the extreme-weather response atlas (图谱) from the sweep outputs.

Figures (all -> artifacts/atlas/):
  A1 heatmap_scenarios.png   rows = scenarios sorted by U10 within category,
                             cols = channels (L/V/Tcw/Tg RMS span-max, peak),
                             cell = value normalized by the site design anchor row
                             (site_sutong_100yr_obs = 1.0); non-stationary rows hatched.
  A2 alongspan_family.png    RMS along-span curve families for the design anchor +
                             6 selected extremes (In-Fa, Doksuri, Meranti, SS Cat5,
                             Funing EF4 [reference-only], Barrow Olivia), one panel
                             per channel, tower positions marked (x=714.5/2995.3 m).
  A3 survival_frontier.png   span-max response and rope utilization vs U10 scatter
                             with the stationary-theory validity band and the
                             utilization=1.0 line (needs rope break force in config;
                             stays annotated-blank until filled).
  A4 comparison_attach23.png design-anchor RMS along span overlaid with attachment
                             2-3 buffeting figures digitized by the executor
                             (digitization CSV path: artifacts/attach23_rms_digitized.csv).
Run AFTER sweep_extreme.py.  NOT RUN in this revision (computation delegated).
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
ATLAS = ART / "atlas"

SELECT_ALONGSPAN = ["site_sutong_100yr_obs", "infa_2021_zhoushan", "doksuri_2023_jinjiang",
                    "meranti_2016_peak", "ss_cat5", "funing_2016_ef4", "barrow_olivia_1996"]
TOWERS_M = (714.5, 2995.3)


def main() -> None:
    ATLAS.mkdir(exist_ok=True)
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sweep = pd.read_csv(ART / "extreme_sweep_responses.csv")
    lib = {s["id"]: s for s in json.loads(
        (ART / "extreme_weather_library.json").read_text())["scenarios"]}

    # A2 along-span families (works with the minimal buffeting.py output)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for sid in SELECT_ALONGSPAN:
        p = ART / f"buffeting_rms_alongspan_{sid}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        style = "--" if lib[sid]["category"] in ("tornado", "downburst", "derecho") else "-"
        axes[0].plot(df.x_m, df.rms_L_mm, style, lw=1.2, label=sid)
        axes[1].plot(df.x_m, df.rms_V_mm, style, lw=1.2, label=sid)
    for ax, ttl in zip(axes, ("lateral RMS [mm]", "vertical RMS [mm]")):
        for tx in TOWERS_M:
            ax.axvline(tx * 1, color="k", lw=0.5, alpha=0.4)
        ax.set_ylabel(ttl)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7, ncol=2)
    axes[1].set_xlabel("x [m]")
    fig.suptitle("Buffeting RMS along span - scenario family (dashed = reference-only)")
    fig.tight_layout()
    fig.savefig(ATLAS / "alongspan_family.png", dpi=160)
    print("wrote", ATLAS / "alongspan_family.png")
    print("A1/A3/A4: executor completes once sweep table carries span-max stats "
          "and attach23 digitization exists (see module docstring)")


if __name__ == "__main__":
    main()
