"""Layer 3 — dual MCT + lateral passages (two decks).

974211b2 cannot form this layer: Y≈0, one line, 21 passage *nodes* only.
The layer is the theoretical two-deck reconstruction using locked T, μ.
"""

from __future__ import annotations

import math
from typing import Any

from common import (
    ATT_F1,
    ATT_F2,
    HERE,
    J_FRAME_PER_M,
    M_PASS_CORE_KG,
    M_PASS_REPORT_KG,
    PASSAGE_XI_MAIN_M,
    R_F2,
    R_G2,
    load_locked_params,
    rel_err,
    sag_H_N,
    taut_freq,
    wave_speed,
    write_json,
)


def _two_deck_harmonics(
    L: float,
    T: float,
    mu: float,
    xs: tuple[float, ...],
    m_pass: float,
    k_pass: float,
    n_max: int = 4,
) -> list[dict[str, Any]]:
    """Galerkin on two identical decks, passages as point mass + vertical spring."""
    out = []
    for n in range(1, n_max + 1):
        kn = (n * math.pi / L) ** 2
        # Modal mass of one deck: ∫ μ sin² = μ L/2
        Mdeck = mu * L / 2.0
        Kdeck = T * kn * L / 2.0
        s2 = [math.sin(n * math.pi * x / L) ** 2 for x in xs]
        Mpass = m_pass * sum(s2)  # half of each passage mass on each deck if split; here full on relative?
        # Common: passages ride along, add mass, spring does not stretch.
        # Differential: spring sees 2u, mass is the passage if it stays on the mid-plane (no roll inertia).
        # Use: common M = 2 Mdeck + m_pass Σ sin², K = 2 Kdeck
        #      diff    M = 2 Mdeck,                 K = 2 Kdeck + 2 k_pass Σ sin²
        # Passage mass on the centreline does not enter the differential (system-roll) inertia.
        Mc = 2.0 * Mdeck + m_pass * sum(s2)
        Md = 2.0 * Mdeck
        Kc = 2.0 * Kdeck
        Kd = 2.0 * Kdeck + 2.0 * k_pass * sum(s2)
        fc = math.sqrt(Kc / Mc) / (2.0 * math.pi)
        fd = math.sqrt(Kd / Md) / (2.0 * math.pi)
        out.append(
            {
                "n": n,
                "f_common_Hz": fc,
                "f_diff_Hz": fd,
                "split_rel": (fd - fc) / fc if fc else None,
                "M_common": Mc,
                "M_diff": Md,
                "k_pass_N_m": k_pass,
                "m_pass_kg": m_pass,
            }
        )
    return out


def _torsion_branch(T_f: float, T_p: float, mu_f: float, mu_p: float, L: float, j_frame: float) -> dict[str, Any]:
    C = T_f * R_F2 + T_p * R_G2
    J = mu_f * R_F2 + mu_p * R_G2 + j_frame
    cT = math.sqrt(C / J)
    f1 = cT / (2.0 * L)
    return {
        "C_theta_N_m2": C,
        "J_theta_kg_m": J,
        "c_T_m_s": cT,
        "f1_Hz": f1,
        "f_n_Hz": [n * f1 for n in range(1, 5)],
        "formula": "C_θ = T_f r_f² + T_p r_g²,  J_θ = μ_f r_f² + μ_p r_g² + J_frame,  f_n = n c_T / 2L",
        "r_f2": R_F2,
        "r_g2": R_G2,
        "J_frame_per_m": j_frame,
    }


def _k_for_target_split(L: float, T: float, mu: float, xs: tuple[float, ...], m_pass: float, target_rel: float) -> float:
    """Stiffness that produces a given (f_d−f_c)/f_c on n=1, mass-on-common only."""
    # fd = (1/2π) √(Kd/Md), fc = (1/2π) √(Kc/Mc)
    # fd/fc = 1+target
    n = 1
    kn = (n * math.pi / L) ** 2
    Mdeck = mu * L / 2.0
    Kdeck = T * kn * L / 2.0
    ssum = sum(math.sin(n * math.pi * x / L) ** 2 for x in xs)
    Mc = 2.0 * Mdeck + m_pass * ssum
    Md = 2.0 * Mdeck
    Kc = 2.0 * Kdeck
    fc = math.sqrt(Kc / Mc)
    fd = fc * (1.0 + target_rel)
    Kd = (fd**2) * Md
    # Kd = 2 Kdeck + 2 k Σsin²
    k = (Kd - 2.0 * Kdeck) / (2.0 * ssum)
    return k


def build(p: dict[str, Any] | None = None) -> dict[str, Any]:
    p = p or load_locked_params()
    L = p["L_main_m"]
    d = p["h_main_m_locked"]
    Tf = p["T_floor_main_N"]
    Tp = p["T_portal_main_N"]
    mf = p["mu_floor_kg_m"]
    mp = p["mu_portal_kg_m"]
    Ts = Tf + Tp
    ms = mf + mp
    g = p["g_m_s2"]
    xs = PASSAGE_XI_MAIN_M
    att_split = (ATT_F2 - ATT_F1) / (0.5 * (ATT_F1 + ATT_F2))

    # Passage stiffness bounds: free → a single φ152×6 chord axial / B.
    A_tube = math.pi * (76.0**2 - 70.0**2)  # mm²
    k_hard = 206000.0 * A_tube / p["B_deck_m"]  # E[N/mm²]·A[mm²]/B[m] = N/m

    cases = {
        "mass_core_k0": _two_deck_harmonics(L, Ts, ms, xs, M_PASS_CORE_KG, 0.0),
        "mass_report_k0": _two_deck_harmonics(L, Ts, ms, xs, M_PASS_REPORT_KG, 0.0),
        "mass_report_khard": _two_deck_harmonics(L, Ts, ms, xs, M_PASS_REPORT_KG, k_hard),
    }
    k_att = _k_for_target_split(L, Ts, ms, xs, M_PASS_REPORT_KG, att_split)
    # Mass-only split is already wider than 0.0296/0.0301. A positive spring widens it more.
    # Negative k is not a physical passage. Record the sign; do not run it as a case.

    # Single-deck slow torsion with locked T vs sag H (the older theory path).
    tor_lock = _torsion_branch(Tf, Tp, mf, mp, L, J_FRAME_PER_M)
    Hs_f = sag_H_N(mf, L, d, g)
    Hs_p = sag_H_N(mp, L, 229.01158565151704, g)
    tor_sag = _torsion_branch(Hs_f, Hs_p, mf, mp, L, J_FRAME_PER_M)

    # β-style reduction of portal C only (v3), locked μ and lock-T floor.
    beta_grid = []
    for beta in (0.6, 0.7, 0.8, 1.0, (Tp / mp) / (Tf / mf)):
        C = Tf * R_F2 + beta * (Tf / mf) * mp * R_G2
        J = mf * R_F2 + mp * R_G2 + J_FRAME_PER_M
        cT = math.sqrt(C / J)
        f1 = cT / (2.0 * L)
        beta_grid.append({"beta": beta, "C_theta": C, "c_T": cT, "f1_Hz": f1})

    # Extra untensioned J needed to put locked-T torsion on 0.0296.
    c_need = 2.0 * L * ATT_F1
    J_need = tor_lock["C_theta_N_m2"] / (c_need**2)

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

    add("two_deck_common_n1_report_k0", cases["mass_report_k0"][0]["f_common_Hz"], "in-phase + 13×10130 kg")
    add("two_deck_diff_n1_report_k0", cases["mass_report_k0"][0]["f_diff_Hz"], "out-of-phase, k=0 (degenerate w.r.t spring)")
    add("two_deck_common_n1_khard", cases["mass_report_khard"][0]["f_common_Hz"], "in-phase, hard tube")
    add("two_deck_diff_n1_khard", cases["mass_report_khard"][0]["f_diff_Hz"], "out-of-phase, hard tube")
    add("torsion_lockT_n1", tor_lock["f1_Hz"], "M5 C_θ,J_θ with locked T")
    add("torsion_sagH_n1", tor_sag["f1_Hz"], "same J, sag-consistent H (not the lock)")
    add("torsion_lockT_n4", tor_lock["f_n_Hz"][3], "4th harmonic of locked-T torsion")
    add(
        "report_massonly_split_n1",
        cases["mass_report_k0"][0]["f_common_Hz"],
        "13×10130 kg already splits ~4%, wider than 1.67%; k_att would be negative",
    )

    nearest_att = min(rows, key=lambda r: abs(r["vs_att_0.0296"]["rel"]))
    nearest_ccx = min(rows, key=lambda r: abs(r["vs_ccx_0.1335403"]["rel"]))

    return {
        "layer": 3,
        "title": "dual MCT + lateral passages / single-deck slow torsion",
        "ccx_can_realise": False,
        "why_ccx_cannot": "974211b2 is a Y=0 single line; UY=0 on every node; 21 横向通道节点 are markers, not two-deck springs",
        "assumptions": [
            "Two identical dual-MCT decks, spacing B=42.90 m (drawing; absent from the 2-D MCT).",
            "T, μ locked from 974211b2. Passages: 13 main-span stations from the drawing chain.",
            "Two mass books: 5769.2 kg core modules / 10130 kg report whole-passage. Not stacked.",
            "Common motion: passages add mass. Differential: passages add stiffness; centreline mass drops out of J_roll.",
            "Single-deck torsion uses v3 radii (r_f²=3.4525, r_g²=69.15, z=8 m) plus locked T, μ.",
            "J_frame smear is a drawing / v3 number. CCX MAT3 density ~0, so CCX does not carry it.",
            "k that reproduces the 0.0296/0.0301 *split* is a diagnostic, not a back-fit of the absolute frequency.",
        ],
        "inputs": {
            "L_m": L,
            "B_m": p["B_deck_m"],
            "T_sum_kN": Ts / 1e3,
            "mu_sum_kg_m": ms,
            "n_pass_main": len(xs),
            "xi_m": list(xs),
            "k_hard_one_tube_N_m": k_hard,
            "att_pair_split_rel": att_split,
            "k_for_att_split_N_m": k_att,
            "k_for_att_split_physical": k_att > 0.0,
        },
        "formulas": {
            "common": "ω² = (T (nπ/L)²) / (μ + m_pass Σsin² / L)",
            "diff": "ω² = (T (nπ/L)² + 2 k_pass Σsin² / L) / μ   (centreline mass omitted)",
            "torsion": tor_lock["formula"],
        },
        "two_deck": cases,
        "torsion_lockT": tor_lock,
        "torsion_sagH": tor_sag,
        "beta_grid_locked_floor_c": beta_grid,
        "J_needed_for_0.0296_with_lockT": {
            "c_need_m_s": c_need,
            "J_need_kg_m": J_need,
            "J_have_kg_m": tor_lock["J_theta_kg_m"],
            "ratio": J_need / tor_lock["J_theta_kg_m"],
            "note": "locked portal T/μ is higher than floor (β>1); extra high mass alone is not enough unless J grows a lot or portal C is cut",
        },
        "compare_rows": rows,
        "self_judge": {
            "nearest_att_0.0296": nearest_att["name"],
            "nearest_ccx_0.1335403": nearest_ccx["name"],
            "approaches_attachment_pair": (
                "the *topology* of this layer is the one that can form a 0.0296/0.0301 near-doublet "
                "(two decks + weak passages, or slow torsion). With *locked* 974211b2 T the absolute "
                "root stays ~0.04 Hz. The older sag-H + β<1 construction is what sat on 0.0296; "
                "that H is not the lock."
            ),
            "approaches_ccx_f1": "nothing in this layer sits on 0.1335 except a 4th torsion harmonic of the locked-T branch, which is the wrong mechanism",
            "does_not_claim_符合": True,
        },
    }


def main() -> dict[str, Any]:
    data = build()
    write_json(HERE / "layer3.json", data)
    return data


if __name__ == "__main__":
    main()
    print("wrote", HERE / "layer3.json")
