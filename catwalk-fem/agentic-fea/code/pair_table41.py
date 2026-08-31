"""Formal Attachment 2-3 Table 4-1 pairing for the ccx double-MCT model.

Locked rules (identical hierarchy to the gate-corrected reference pairing):
main rows need main-span energy >= 0.65, then family + parity + within-family
ascending-frequency ordinal; half-wave counts are fingerprints only.  Side rows
use dominant non-main-span energy with a global one-to-one relative-frequency
assignment.  No re-pairing on shape hunches (TS2 stays TS2).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160

REPO = Path("/workspace")
ART = REPO / "catwalk-fem/agentic-fea/artifacts"
REF = REPO / "catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/reference_attachment_2_3_table4_1.csv"
ROM_LOCKED = REPO / "catwalk-fem/double-mct-buffeting/modal_validation/gate_corrected_reference_table4_1_matching.csv"
ROM_UPG = REPO / "catwalk-fem/double-mct-buffeting/roll_upgraded_results/roll_upgraded_reference_table4_1_matching.csv"

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
    cls = pd.read_csv(ART / "ccx_mode_classification.csv")
    ref = pd.read_csv(REF)
    ref_map = dict(zip(ref["internal_id"], ref["frequency_hz"]))

    main_pool = cls[(cls["main_span_fraction"] >= 0.65)].copy()
    side_pool = cls[(cls["main_span_fraction"] < 0.65)].copy()

    rows = []
    used = set()
    for rid, (fam, par, ordn) in MAIN_ROWS.items():
        cand = main_pool[(main_pool["family"] == fam) & (main_pool["parity"] == par)]
        cand = cand.sort_values("frequency_hz")
        if len(cand) >= ordn:
            r = cand.iloc[ordn - 1]
            used.add(int(r["mode"]))
            rows.append(
                {
                    "reference_id": rid,
                    "reference_hz": ref_map[rid],
                    "matched_mode": int(r["mode"]),
                    "matched_hz": float(r["frequency_hz"]),
                    "half_wave_fingerprint": int(r["half_wave"]),
                    "family_fraction": float(r["family_fraction"]),
                }
            )
        else:
            rows.append({"reference_id": rid, "reference_hz": ref_map[rid], "matched_mode": None})

    side_targets = [("SIDE1", ref_map["SIDE1"]), ("SIDE2", ref_map["SIDE2"]), ("SIDE3", ref_map["SIDE3"])]
    side_cand = side_pool.sort_values("frequency_hz")[["mode", "frequency_hz", "dominant_span"]].values.tolist()
    for rid, fr in side_targets:
        best = min(
            (c for c in side_cand if int(c[0]) not in used),
            key=lambda c: abs(c[1] - fr) / fr,
        )
        used.add(int(best[0]))
        rows.append(
            {
                "reference_id": rid,
                "reference_hz": fr,
                "matched_mode": int(best[0]),
                "matched_hz": float(best[1]),
                "dominant_span": str(best[2]),
            }
        )

    out = pd.DataFrame(rows)
    order = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]
    out["__o"] = out["reference_id"].map({k: i for i, k in enumerate(order)})
    out = out.sort_values("__o").drop(columns="__o")
    out["relative_error_percent"] = (out["matched_hz"] - out["reference_hz"]) / out["reference_hz"] * 100.0

    rom_l = pd.read_csv(ROM_LOCKED)[["reference_id", "relative_error_percent"]].rename(
        columns={"relative_error_percent": "rom_locked_err"}
    )
    rom_u = pd.read_csv(ROM_UPG)[["reference_id", "relative_error_percent"]].rename(
        columns={"relative_error_percent": "rom_upgraded_err"}
    )
    out = out.merge(rom_l, on="reference_id", how="left").merge(rom_u, on="reference_id", how="left")
    out.to_csv(ART / "ccx_table41_pairing.csv", index=False)

    t_rows = out["reference_id"].isin(["TA1", "TS1", "TS2"])
    stats = {
        "mae_14": float(out["relative_error_percent"].abs().mean()),
        "rms_14": float((out["relative_error_percent"] ** 2).mean() ** 0.5),
        "mae_T": float(out.loc[t_rows, "relative_error_percent"].abs().mean()),
        "mae_nonT": float(out.loc[~t_rows, "relative_error_percent"].abs().mean()),
    }
    (ART / "ccx_table41_stats.json").write_text(json.dumps(stats, indent=2))
    print(out.to_string(index=False))
    print(json.dumps(stats, indent=2))

    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    x = range(len(out))
    w = 0.27
    ax.bar([i - w for i in x], out["rom_locked_err"], w, label="ROM 锁定版(2026-08-05)", color="#7f8c8d")
    ax.bar(list(x), out["rom_upgraded_err"], w, label="ROM 滚转升级(08-27)", color="#1f618d")
    ax.bar([i + w for i in x], out["relative_error_percent"], w, label="ccx 全三维(本次, 焊接端理想化)", color="#b03a2e")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(list(x))
    ax.set_xticklabels(out["reference_id"], fontsize=9)
    ax.set_ylabel("相对附件表4-1 / %")
    ax.set_title("十四行相对误差：ROM 两代 vs CalculiX 全三维物理框架模型")
    ax.legend(fontsize=9)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(ART / "ccx_vs_rom_table41_errors.png", bbox_inches="tight")
    print("figure written")


if __name__ == "__main__":
    main()
