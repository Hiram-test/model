#!/usr/bin/env python3
"""Sweep every scenario in the extreme weather library through the buffeting engine.

For each scenario:
  1. run buffeting.py (spectral, stationary) at its U10/Iu;
  2. collect span-max / mean RMS and peaks from the summary JSON;
  3. mark tornado/downburst/derecho with stationarity=reference_only.
Outputs artifacts/extreme_sweep_responses.csv.
Run AFTER run_solver.sh + postprocess_modes.py.
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
        print(">>", " ".join(cmd), flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            rows.append({"id": sc["id"], "status": "FAILED",
                         "category": sc.get("category"),
                         "U10": sc.get("U10_sustained_ms")})
            continue
        sm = json.loads((ART / f"buffeting_summary_{sc['id']}.json").read_text())
        rows.append({
            "id": sc["id"], "status": "OK",
            "category": sc["category"],
            "confidence": sc.get("confidence"),
            "U10": sc["U10_sustained_ms"],
            "gust3s": sc.get("gust3s_ms"),
            "U_deck": sm.get("U_deck_ms"),
            "Iu": sc.get("Iu"),
            "stationarity": ("reference_only" if sc["category"] in NONSTATIONARY
                             else "stationary_ok"),
            "rms_L_max_mm": sm["rms_max"]["L_mm"],
            "rms_V_max_mm": sm["rms_max"]["V_mm"],
            "rms_Tcw_max_rad": sm["rms_max"]["Tcw_rad"],
            "rms_Tg_max_rad": sm["rms_max"]["Tg_rad"],
            "peak_L_mm": sm["peak_max"]["L_mm"],
            "peak_V_mm": sm["peak_max"]["V_mm"],
            "peak_Tcw_rad": sm["peak_max"]["Tcw_rad"],
            "peak_Tg_rad": sm["peak_max"]["Tg_rad"],
            "rms_csv": f"buffeting_rms_alongspan_{sc['id']}.csv",
        })
    import csv
    keys = ["id", "status", "category", "confidence", "U10", "gust3s", "U_deck", "Iu",
            "stationarity", "rms_L_max_mm", "rms_V_max_mm", "rms_Tcw_max_rad",
            "rms_Tg_max_rad", "peak_L_mm", "peak_V_mm", "peak_Tcw_rad", "peak_Tg_rad",
            "rms_csv"]
    with open(ART / "extreme_sweep_responses.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    n_ok = sum(1 for r in rows if r.get("status") == "OK")
    print(f"swept {len(rows)} scenarios ({n_ok} OK) -> extreme_sweep_responses.csv")


if __name__ == "__main__":
    main()
