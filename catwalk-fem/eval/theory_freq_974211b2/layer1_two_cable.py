"""Layer 1 — single-span taut cable / two parallel cables.

Uses locked L, T, μ from 974211b2. No FEM. No TARGET-FREQ import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    ATT_F1,
    ATT_F2,
    G_STD,
    HERE,
    irvine_inplane_freqs,
    load_locked_params,
    rel_err,
    sag_H_N,
    sag_freq,
    taut_freq,
    wave_speed,
    write_json,
)


def build(p: dict[str, Any] | None = None) -> dict[str, Any]:
    p = p or load_locked_params()
    L = p["L_main_m"]
    d = p["h_main_m_locked"]
    Tf = p["T_floor_main_N"]
    Tp = p["T_portal_main_N"]
    mf = p["mu_floor_kg_m"]
    mp = p["mu_portal_kg_m"]
    EA = p["EA_floor_N"]
    g = p["g_m_s2"]

    # 1a  Single equivalent floor line (what the 2-D deck already is).
    c_lock = wave_speed(Tf, mf)
    taut = [taut_freq(n, L, Tf, mf) for n in range(1, 6)]
    sag = [sag_freq(n, d, g) for n in range(1, 6)]
    sag_std = [sag_freq(n, d, G_STD) for n in range(1, 6)]
    H_sag = sag_H_N(mf, L, d, g)
    taut_from_sagH = [taut_freq(n, L, H_sag, mf) for n in range(1, 6)]

    # 1b  Two identical parallel floor lines, no coupling (two decks, passages off).
    # Degenerate pair: same spectrum twice.
    pair = {
        "assumption": "two identical copies of the locked floor line, B apart, k_c=0",
        "B_m": p["B_deck_m"],
        "f_common_Hz": taut[0],
        "f_diff_Hz": taut[0],
        "split": 0.0,
        "note": "uncoupled pair cannot split 0.0296 / 0.0301; it only duplicates the taut root",
    }

    # 1c  Irvine in-plane on the locked floor line (Y is pinned in CCX, so only this polarisation exists).
    irv_lock = irvine_inplane_freqs(L, d, Tf, mf, EA)
    irv_sag = irvine_inplane_freqs(L, d, H_sag, mf, EA)

    rows = []

    def add(name: str, f: float, formula: str) -> None:
        rows.append(
            {
                "name": name,
                "f_Hz": f,
                "formula": formula,
                "vs_att_0.0296": {"abs": f - ATT_F1, "rel": rel_err(f, ATT_F1)},
                "vs_att_0.0301": {"abs": f - ATT_F2, "rel": rel_err(f, ATT_F2)},
                "vs_ccx_0.1335403": {"abs": f - p["ccx_f1_Hz"], "rel": rel_err(f, p["ccx_f1_Hz"])},
            }
        )

    add("sag_n1_gMCT", sag[0], "n √(g/32d), d=227.300 m, g=9.806")
    add("sag_n1_gSTD", sag_std[0], "n √(g/32d), g=9.80665")
    add("taut_lockT_n1", taut[0], "(1/2L) √(T_lock/μ_floor), T=主跨 mean INIFORCE")
    add("taut_sagH_n1", taut_from_sagH[0], "(1/2L) √(H_sag/μ); H=μgL²/8d. Same number as sag_n1")
    add("two_parallel_uncoupled_n1", taut[0], "two copies of taut_lockT_n1")
    add("irvine_lockT_antisym1", irv_lock["antisymmetric"][0]["f_Hz"], "2 f_taut (in-plane odd)")
    add("irvine_lockT_sym1", irv_lock["symmetric"][0]["f_Hz"], "first Irvine symmetric, λ² from lock T")
    add("irvine_lockT_first_inplane", irv_lock["first_inplane_Hz"], "min(antisym1, sym1)")
    add("irvine_sagH_antisym1", irv_sag["antisymmetric"][0]["f_Hz"], "2 √(g/32d)")
    add("taut_lockT_n3", taut[2], "3 f_taut ; catalog only")
    add("taut_lockT_n4", taut[3], "4 f_taut ; catalog only")

    nearest_att = min(rows, key=lambda r: abs(r["vs_att_0.0296"]["rel"]))
    nearest_ccx = min(rows, key=lambda r: abs(r["vs_ccx_0.1335403"]["rel"]))

    return {
        "layer": 1,
        "title": "single-span taut / two parallel cables",
        "assumptions": [
            "Main span only. L=2302 m, d=227.300 m from the locked overlay / user lock.",
            "T = MCT *INIFORCE mean on 主跨 TENSTR (10431.68 kN). Not table 5-4.",
            "μ = ρ_MAT1 × A_SEC1 reread from the main deck (N-mm-s → kg/m).",
            "Single line = the 2-D equivalent already in 974211b2 (16 φ50 bundled).",
            "Two parallel cables = two copies of that line, uncoupled, spacing B=42.90 m from drawings.",
            "No portals, no passages, no second polarisation beyond the taut/Irvine pair.",
            "Ends pinned. No 4-span leakage.",
        ],
        "inputs": {
            "L_m": L,
            "d_m": d,
            "d_overlay_m": p["h_main_m_overlay"],
            "T_floor_kN": Tf / 1e3,
            "mu_floor_kg_m": mf,
            "EA_floor_N": EA,
            "H_sag_kN": H_sag / 1e3,
            "T_over_H_sag": Tf / H_sag,
            "c_lock_m_s": c_lock,
            "c_sag_m_s": wave_speed(H_sag, mf),
            "g": g,
        },
        "formulas": {
            "taut": "f_n = n/(2L) √(T/μ)",
            "sag": "f_n = n √(g/32d)  (T=μgL²/8d eliminates μ)",
            "two_parallel": "k_c=0 ⇒ {f,f} degenerate",
            "Irvine": irv_lock["formula_sym"],
        },
        "spectrum": {
            "taut_lockT_Hz": taut,
            "sag_gMCT_Hz": sag,
            "taut_sagH_Hz": taut_from_sagH,
        },
        "irvine_lockT": irv_lock,
        "irvine_sagH": irv_sag,
        "two_parallel": pair,
        "compare_rows": rows,
        "self_judge": {
            "nearest_att_0.0296": nearest_att["name"],
            "nearest_ccx_0.1335403": nearest_ccx["name"],
            "approaches_attachment_pair": "sag / taut n=1 sit in the 0.037–0.042 Hz band, same order as 0.0296/0.0301, still 24–41% high",
            "approaches_ccx_f1": "only n=3 taut (0.125) and Irvine sym1 (~0.12) are in the 0.13 neighbourhood; they are not this layer's fundamental",
            "does_not_claim_符合": True,
        },
        "unused": {
            "T_portal_kN": Tp / 1e3,
            "mu_portal_kg_m": mp,
            "reason": "portal line is layer 2",
        },
    }


def main() -> dict[str, Any]:
    data = build()
    write_json(HERE / "layer1.json", data)
    return data


if __name__ == "__main__":
    main()
    print("wrote", HERE / "layer1.json")
