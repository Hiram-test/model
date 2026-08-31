#!/usr/bin/env python3
"""Early-warning state machine (outline §3.1).  Thresholds remain 〔待填〕.

Query the master surface at (U10, Iu).  If gust factor GF > G_thr or the
caller marks non-stationary, fall back to a static-gust envelope note.
Measured RMS outside the [P16,P84] band (here: grid value only, P16/P84
not yet a CdD ensemble) raises anomaly for review, not a wind-level upgrade.

LEVEL is not dispatched while any threshold is 〔待填〕.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
ATLAS = ART / "atlas"
CHANS = ["L_mm", "V_mm", "Tcw_rad", "Tg_rad"]
G_THR = None   # 〔待填:阵风因子阈值，方案写 2.0 为草稿〕


def load_surface():
    d = np.load(ATLAS / "master_surface.npz")
    interps = {}
    for k, name in enumerate(CHANS):
        interps[name] = RegularGridInterpolator(
            (d["U"], d["Iu"]), d["cube"][:, :, k],
            bounds_error=False, fill_value=None)
    return interps, d


def classify(U10: float, Iu: float, GF: float | None = None,
             sigma_meas_L_mm: float | None = None,
             forecast_level: str | None = None) -> dict:
    interps, _ = load_surface()
    pt = np.array([[U10, Iu]])
    band = {n: float(interps[n](pt)[0]) for n in CHANS}
    nonstat = (GF is not None and G_THR is not None and GF > G_THR)
    mode = "NONSTATIONARY" if nonstat else "STATIONARY"
    anomaly = None
    if sigma_meas_L_mm is not None and band["L_mm"] > 0:
        # without P16/P84 ensemble, flag if meas > 1.5 × P50 as 〔待填〕 draft
        anomaly = bool(sigma_meas_L_mm > 1.5 * band["L_mm"])
    out = {
        "U10": U10, "Iu": Iu, "GF": GF, "mode": mode,
        "band_P50": band,
        "band_P16_P84": "〔待填:CdD×Iu ensemble; v0 surface is P50 grid only〕",
        "L_wind": "〔待填:阈值未定版不可上线〕",
        "anomaly_review_only": anomaly,
        "L_fcst": forecast_level,
        "LEVEL": "NOT_ARMED",
        "reason": "blue/yellow/orange/red numeric thresholds are 〔待填〕 from code/drawings; system must not dispatch",
        "actions": {
            "blue": "〔待填:施工作业限值 · 规范出处〕",
            "yellow": "〔待填:50% 设计响应 · 附件出处〕",
            "orange": "〔待填:80% 设计响应或利用率〕",
            "red": "〔待填:生存边界〕",
        },
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--U10", type=float, default=38.9)
    ap.add_argument("--Iu", type=float, default=0.11)
    ap.add_argument("--GF", type=float, default=None)
    ap.add_argument("--meas_L_mm", type=float, default=None)
    args = ap.parse_args()
    rec = classify(args.U10, args.Iu, args.GF, args.meas_L_mm)
    dest = ART / "warning_demo_sutong.json"
    dest.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    print(json.dumps(rec, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
