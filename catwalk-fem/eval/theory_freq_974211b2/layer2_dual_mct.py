"""Layer 2 — dual MCT: floor line + portal-cable line.

The 974211b2 deck is already this topology in one Y=0 plane, coupled by 71 B31.
"""

from __future__ import annotations

import math
from typing import Any

from common import (
    ATT_F1,
    HERE,
    irvine_inplane_freqs,
    load_locked_params,
    rel_err,
    sag_H_N,
    taut_freq,
    two_dof_freqs,
    wave_speed,
    write_json,
)


def _portal_stations_main(L: float, n_portal: int = 41) -> list[float]:
    # Drawing main-span chain 64+11×57+18×51+11×57+64 = 2300. Scale to locked 2302.
    raw = [64.0] + [57.0] * 11 + [51.0] * 18 + [57.0] * 11 + [64.0]
    scale = L / sum(raw)
    xs = []
    acc = 0.0
    for i, seg in enumerate(raw[:-1]):
        acc += seg * scale
        xs.append(acc)
    assert len(xs) == n_portal
    return xs


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
    EA_f = p["EA_floor_N"]
    EA_p = p["EA_portal_N"]
    # Portal posts: MCT TRUSS / CCX B31, A=9792 mm², E=206000 N/mm², h≈8 m from overlay Δz.
    h_portal = 8.0
    EA_frame = 206000.0 * 9792.0  # N
    k_one = EA_frame / h_portal  # N/m

    xs = _portal_stations_main(L)
    rows = []

    def add(name: str, f: float, formula: str) -> None:
        rows.append(
            {
                "name": name,
                "f_Hz": f,
                "formula": formula,
                "vs_att_0.0296": {"abs": f - ATT_F1, "rel": rel_err(f, ATT_F1)},
                "vs_ccx_0.1335403": {"abs": f - p["ccx_f1_Hz"], "rel": rel_err(f, p["ccx_f1_Hz"])},
            }
        )

    taut_f = [taut_freq(n, L, Tf, mf) for n in range(1, 6)]
    taut_p = [taut_freq(n, L, Tp, mp) for n in range(1, 6)]
    taut_ip = [taut_freq(n, L, Ts, ms) for n in range(1, 6)]
    add("floor_only_n1", taut_f[0], "(1/2L)√(T_f/μ_f)")
    add("portal_only_n1", taut_p[0], "(1/2L)√(T_p/μ_p)")
    add("inphase_rigid_n1", taut_ip[0], "(1/2L)√((T_f+T_p)/(μ_f+μ_p))")
    add("inphase_rigid_n3", taut_ip[2], "3 × in-phase taut")

    irv_ip = irvine_inplane_freqs(L, d, Ts, ms, EA_f + EA_p)
    add("inphase_irvine_antisym1", irv_ip["antisymmetric"][0]["f_Hz"], "2 f_inphase")
    add("inphase_irvine_sym1", irv_ip["symmetric"][0]["f_Hz"], "Irvine symmetric of the locked pair")
    add("inphase_irvine_first", irv_ip["first_inplane_Hz"], "min of the in-phase Irvine pair")

    # Discrete portals as vertical springs. k_eq,n = Σ k sin²(nπx/L)
    optical = []
    for n in range(1, 5):
        keq = sum(k_one * math.sin(n * math.pi * x / L) ** 2 for x in xs)
        pair = two_dof_freqs(Tf, mf, Tp, mp, keq, L, n)
        pair["n"] = n
        pair["n_portals"] = len(xs)
        optical.append(pair)
        add(f"optical_n{n}_low", pair["f_low_Hz"], "2-DOF in-phase-ish with 41 axial posts")
        add(f"optical_n{n}_high", pair["f_high_Hz"], "2-DOF floor-vs-portal (optical)")

    # Four-span floor taut catalog lives in layer 4; here only quote 南边跨 as the
    # short-span root the 2-D dual line can actually form.
    south = next(s for s in p["spans"] if s["floor"] == "南边跨")
    f_south = taut_freq(1, south["L_floor_m"], south["T_floor_N"], mf)
    f_south_ip = taut_freq(1, south["L_floor_m"], south["T_sum_N"], ms)
    add("south_span_floor_n1", f_south, "南边跨 taut, locked T_floor / μ_floor")
    add("south_span_inphase_n1", f_south_ip, "南边跨 taut, T_sum / μ_sum")

    north = next(s for s in p["spans"] if s["floor"] == "北边跨")
    f_north = taut_freq(1, north["L_floor_m"], north["T_floor_N"], mf)
    add("north_span_floor_n1", f_north, "北边跨 taut, locked T_floor / μ_floor")

    nearest_att = min(rows, key=lambda r: abs(r["vs_att_0.0296"]["rel"]))
    nearest_ccx = min(rows, key=lambda r: abs(r["vs_ccx_0.1335403"]["rel"]))

    return {
        "layer": 2,
        "title": "dual MCT: floor TENSTR + portal TENSTR + discrete portals",
        "assumptions": [
            "Two continuous lines in one vertical plane: MAT1 floor bundle + MAT2 6×φ50 portal ropes.",
            "T and μ from locked 主跨 INIFORCE means and main-deck ρA.",
            "71 / 41 portals are axial connectors, h=8.0 m (overlay floor z_min 113.3 vs portal 121.3).",
            "MAT3 density is ~0, so portal-frame mass is not in the CCX inertia.",
            "In-phase rigid connector recovers one equivalent cable with T_sum, μ_sum.",
            "Optical (floor vs portal) uses the 41 main-span stations and EA/h of the B31 posts.",
            "Y=0 plane: no two-deck torsion, no lateral passages as springs.",
        ],
        "inputs": {
            "L_m": L,
            "T_floor_kN": Tf / 1e3,
            "T_portal_kN": Tp / 1e3,
            "mu_floor_kg_m": mf,
            "mu_portal_kg_m": mp,
            "c_floor_m_s": wave_speed(Tf, mf),
            "c_portal_m_s": wave_speed(Tp, mp),
            "c_inphase_m_s": wave_speed(Ts, ms),
            "beta_Tp_over_Tf_wave": (Tp / mp) / (Tf / mf),
            "h_portal_m": h_portal,
            "k_one_portal_N_m": k_one,
            "n_main_portals": len(xs),
            "H_sag_floor_kN": sag_H_N(mf, L, d, p["g_m_s2"]) / 1e3,
            "H_sag_portal_kN": sag_H_N(mp, L, 229.01158565151704, p["g_m_s2"]) / 1e3,
        },
        "formulas": {
            "uncoupled": "each line f_n = n/(2L) √(T/μ)",
            "inphase": "f_n = n/(2L) √((T_f+T_p)/(μ_f+μ_p))",
            "optical": "K = diag(T k_n²)+k_eq[[1,-1],[-1,1]],  k_eq=Σ k sin²(nπx/L)",
            "k_portal": "k = (EA)_B31 / h,  h=8 m",
        },
        "inphase_irvine": irv_ip,
        "optical_harmonics": optical,
        "compare_rows": rows,
        "self_judge": {
            "nearest_att_0.0296": nearest_att["name"],
            "nearest_ccx_0.1335403": nearest_ccx["name"],
            "optical_is_out_of_band": optical[0]["f_high_Hz"] > 10.0,
            "approaches_attachment_pair": "in-phase n=1 remains ~0.043 Hz; still the 0.03-order band, not a hit",
            "approaches_ccx_f1": "南边跨 taut n=1 sits on 0.1335; main-span in-phase n=3 and Irvine sym1 are the other neighbours",
            "does_not_claim_符合": True,
        },
    }


def main() -> dict[str, Any]:
    data = build()
    write_json(HERE / "layer2.json", data)
    return data


if __name__ == "__main__":
    main()
    print("wrote", HERE / "layer2.json")
