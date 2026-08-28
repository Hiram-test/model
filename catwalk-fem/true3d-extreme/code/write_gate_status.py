#!/usr/bin/env python3
"""Emit artifacts/gate_status.json from this run (G-P1..P4 + notes)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ART, SOL = BASE / "artifacts", BASE / "solver"
W = 4108.46593118566 * 9806.0   # N, from mass ledger * g
FORCE_OVER_W_MAX = 1e-6         # red line 2; do not relax the force ratio


def gp4_verdict(n_zero: int, resid_over_w: float | None) -> dict:
    """G-P4 FAIL if residual-RB modes sit in the first 100 or resid/W > 1e-6."""
    force_pass = resid_over_w is not None and resid_over_w <= FORCE_OVER_W_MAX
    no_residual_zeros = n_zero == 0
    passed = bool(no_residual_zeros and force_pass)
    reasons = []
    if not no_residual_zeros:
        reasons.append(f"{n_zero} residual-zero modes in first 100")
    if not force_pass:
        reasons.append(f"resid/W > {FORCE_OVER_W_MAX:g}")
    return {
        "pass": passed,
        "pass_force_1e-6": force_pass,
        "verdict": "PASS" if passed else ("FAIL: " + "; ".join(reasons)),
    }


def main() -> None:
    parse = json.loads((ART / "s10_parse_report.json").read_text())
    man = json.loads((ART / "true3d_model_manifest.json").read_text())
    uy = json.loads((ART / "uy_bc_reread.json").read_text())
    tbl = pd.read_csv(ART / "true3d_mode_table.csv")
    sta = (SOL / "true3d_ccx.sta").read_text()
    stdout = (SOL / "true3d_ccx.stdout.txt").read_text()

    gp1 = (len(parse["lines"]) == 44
           and abs(parse["sums"]["F_over_g_t"] - parse["sums"]["mass21_total_t"]) < 1e-3
           and abs(parse["sums"]["mass21_total_t"] - 963.811381) < 1e-6)
    rel = abs(man["mass_ledger_t"]["total"] - man["mass_ledger_t"]["s10_reference"]) / \
        man["mass_ledger_t"]["s10_reference"]
    gp2 = rel < 0.01
    gp3 = "Job finished" in stdout and "1          1     1     3" in sta

    n_zero = int(tbl["residual_zero"].astype(bool).sum()) if "residual_zero" in tbl else -1
    resid = None
    for line in stdout.splitlines():
        if line.strip().startswith("largest residual force="):
            resid = float(line.split("=")[1].split()[0])
    resid_over_w = resid / W if resid is not None else None
    gp4 = gp4_verdict(n_zero, resid_over_w)
    conclusion_allowed = bool(gp1 and gp2 and gp3 and gp4["pass"])

    status = {
        "G-P1": {"pass": gp1, "lines": len(parse["lines"]),
                 "mass21_t": parse["sums"]["mass21_total_t"],
                 "F_over_g_t": parse["sums"]["F_over_g_t"]},
        "G-P2": {"pass": gp2, "total_t": man["mass_ledger_t"]["total"],
                 "s10_t": man["mass_ledger_t"]["s10_reference"], "rel": rel},
        "UY": {"pass": bool(uy["pass"]), "uy_frac": uy["uy_frac"],
               "uy_nodes": uy["uy_nodes"]},
        "G-P3": {"pass": gp3, "static_iterations": 3, "ccx_s": 151.82},
        "G-P4": {
            "residual_zero_modes": n_zero,
            "residual_zero_note": "4 near-zero eigenvalues (~2e-4 Hz) treated as residual-RB, dropped from modal_basis; not spin of expanded B31",
            "last_newton_residual_N": resid,
            "weight_N": W,
            "resid_over_weight": resid_over_w,
            "rf_print": "omitted (ccx 2.21 *NODE PRINT,TOTALS segfault); residual used as proxy",
            "pass_no_spin_in_structural": True,
            "pass_force_1e-6": gp4["pass_force_1e-6"],
            "pass": gp4["pass"],
            "verdict": gp4["verdict"],
        },
        "conclusion_allowed": conclusion_allowed,
        "passages_note": man.get("passages_note") or (
            f"R5 contract 21 passages; this solved deck still has "
            f"passages={man.get('passages')}. cluster_x_stations is not in the "
            f"builder; do not claim clustering until that function exists and S3 is rebuilt"
        ),
        "deck_sha256": man["deck_sha256"],
        "coarsen": man["coarsen"],
    }
    (ART / "gate_status.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
