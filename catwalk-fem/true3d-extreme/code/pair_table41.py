#!/usr/bin/env python3
"""Locked-rule Attachment 2-3 Table 4-1 pairing for the true-3D ccx model.

Rules (same hierarchy as double-MCT / gate-corrected):
  main rows: main_span_fraction >= 0.65, then family + parity + within-family
             ascending-frequency ordinal; half-waves are fingerprints only.
  side rows: dominant non-main-span, global one-to-one relative-frequency.
  No half-wave MAC promotion; TS2 stays TS2.
Reference CSV columns internal_id / frequency_hz are not modified.
T-family errors are reported; reproduction / 一致 is not claimed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
REPO = BASE.parent.parent
REF = REPO / ("catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/"
              "reference_attachment_2_3_table4_1.csv")
ROM_LOCKED = REPO / ("catwalk-fem/double-mct-buffeting/modal_validation/"
                     "gate_corrected_reference_table4_1_matching.csv")
ROM_UPG = REPO / ("catwalk-fem/double-mct-buffeting/roll_upgraded_results/"
                  "roll_upgraded_reference_table4_1_matching.csv")

MAIN_ROWS = {
    "LS1": ("L", "S", 1),
    "VA1": ("V", "A", 1),
    "LA1": ("L", "A", 1),
    "TA1": ("T", "A", 1),
    "VS1": ("V", "S", 1),
    "LS2": ("L", "S", 2),
    "TS1": ("T", "S", 1),
    "VA2": ("V", "A", 2),
    "LA2": ("L", "A", 2),
    "TS2": ("T", "S", 2),
    "VS2": ("V", "S", 2),
}


def main() -> None:
    cls = pd.read_csv(ART / "true3d_mode_table.csv")
    cls = cls[~cls["residual_zero"].astype(bool)].copy()
    ref = pd.read_csv(REF)
    ref_map = dict(zip(ref["internal_id"], ref["frequency_hz"]))

    main_pool = cls[cls["main_span_fraction"] >= 0.65].copy()
    side_pool = cls[cls["main_span_fraction"] < 0.65].copy()

    rows = []
    used = set()
    for rid, (fam, par, ordn) in MAIN_ROWS.items():
        cand = main_pool[(main_pool["family"] == fam) & (main_pool["parity"] == par)]
        cand = cand.sort_values("f_hz")
        if len(cand) >= ordn:
            r = cand.iloc[ordn - 1]
            used.add(int(r["mode"]))
            rows.append({
                "reference_id": rid,
                "reference_hz": ref_map[rid],
                "matched_mode": int(r["mode"]),
                "matched_hz": float(r["f_hz"]),
                "half_wave_fingerprint": int(r["half_waves"]),
                "family": fam, "parity": par,
                "main_span_fraction": float(r["main_span_fraction"]),
            })
        else:
            rows.append({
                "reference_id": rid, "reference_hz": ref_map[rid],
                "matched_mode": None, "matched_hz": float("nan"),
                "family": fam, "parity": par,
            })

    side_targets = [("SIDE1", ref_map["SIDE1"]),
                    ("SIDE2", ref_map["SIDE2"]),
                    ("SIDE3", ref_map["SIDE3"])]
    side_cand = side_pool.sort_values("f_hz")[["mode", "f_hz", "dominant_span"]].values.tolist()
    for rid, fr in side_targets:
        leftover = [c for c in side_cand if int(c[0]) not in used]
        if not leftover:
            rows.append({"reference_id": rid, "reference_hz": fr,
                         "matched_mode": None, "matched_hz": float("nan")})
            continue
        best = min(leftover, key=lambda c: abs(c[1] - fr) / fr)
        used.add(int(best[0]))
        rows.append({
            "reference_id": rid, "reference_hz": fr,
            "matched_mode": int(best[0]), "matched_hz": float(best[1]),
            "dominant_span": str(best[2]),
        })

    out = pd.DataFrame(rows)
    order = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1",
             "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]
    out["__o"] = out["reference_id"].map({k: i for i, k in enumerate(order)})
    out = out.sort_values("__o").drop(columns="__o")
    out["relative_error_percent"] = (out["matched_hz"] - out["reference_hz"]) / out["reference_hz"] * 100.0

    if ROM_LOCKED.exists():
        rom_l = pd.read_csv(ROM_LOCKED)[["reference_id", "relative_error_percent"]].rename(
            columns={"relative_error_percent": "rom_locked_err"})
        out = out.merge(rom_l, on="reference_id", how="left")
    if ROM_UPG.exists():
        rom_u = pd.read_csv(ROM_UPG)[["reference_id", "relative_error_percent"]].rename(
            columns={"relative_error_percent": "rom_upgraded_err"})
        out = out.merge(rom_u, on="reference_id", how="left")

    out.to_csv(ART / "true3d_table41_pairing.csv", index=False)
    t_rows = out["reference_id"].isin(["TA1", "TS1", "TS2"])
    valid = out["matched_hz"].notna()
    stats = {
        "n_paired": int(valid.sum()),
        "mae_14": float(out.loc[valid, "relative_error_percent"].abs().mean()),
        "rms_14": float((out.loc[valid, "relative_error_percent"] ** 2).mean() ** 0.5),
        "mae_T": float(out.loc[t_rows & valid, "relative_error_percent"].abs().mean()),
        "mae_nonT": float(out.loc[(~t_rows) & valid, "relative_error_percent"].abs().mean()),
        "claim": "comparison_only; T family cited only via three-stack bracket, not 复现/一致",
    }
    (ART / "true3d_table41_stats.json").write_text(json.dumps(stats, indent=2))
    print(out.to_string(index=False))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
