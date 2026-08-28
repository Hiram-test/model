#!/usr/bin/env python3
"""Sweep every scenario in the extreme weather library through the buffeting engine.

For each scenario:
  1. run buffeting.py (spectral, stationary) at its U10/Iu;
  2. collect span-max and span-mean RMS per channel;
  3. mark non-stationary categories (tornado/downburst/derecho/katabatic gustfront)
     with `stationarity=reference_only` in the output table;
  4. additionally evaluate the static equivalent gust push
     q_gust = 0.5 rho [U(z)*G]^2 (CdD) as a quasi-static bound for those rows
     (G from gust3s/U10 in the library when present, else 1.42).
Outputs artifacts/extreme_sweep_responses.csv with columns:
  id, category, confidence, U10, gust3s, U_deck, rms_L_max_mm, rms_V_max_mm,
  rms_Tcw_max_rad, rms_Tg_max_rad, peak_L_mm, peak_V_mm, static_gust_bound_kN_per_m,
  utilization_note, stationarity
Run AFTER run_solver.sh + postprocess_modes.py.   NOT RUN in this revision.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
NONSTATIONARY = {"tornado", "downburst", "derecho"}


def main() -> None:
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    rows = []
    for sc in lib["scenarios"]:
        cmd = [sys.executable, str(BASE / "code/buffeting.py"), "--scenario", sc["id"]]
        print(">>", " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            rows.append({"id": sc["id"], "status": "FAILED"})
            continue
        rows.append({
            "id": sc["id"], "category": sc["category"],
            "confidence": sc.get("confidence"),
            "U10": sc["U10_sustained_ms"], "gust3s": sc.get("gust3s_ms"),
            "stationarity": ("reference_only" if sc["category"] in NONSTATIONARY
                              else "stationary_ok"),
            "rms_csv": f"buffeting_rms_alongspan_{sc['id']}.csv",
        })
    import csv
    with open(ART / "extreme_sweep_responses.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        w.writerows(rows)
    print(f"swept {len(rows)} scenarios -> extreme_sweep_responses.csv")
    print("executor: extend rows with span-max stats + static gust bound per docstring")


if __name__ == "__main__":
    main()
