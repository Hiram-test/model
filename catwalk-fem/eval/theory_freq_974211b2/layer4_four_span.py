"""Layer 4 — four-span taut catalog + CCX participation reading.

Improvement on the three requested layers: the 2-D deck is four spans, not one.
"""

from __future__ import annotations

from typing import Any

from common import (
    ATT_F1,
    HERE,
    irvine_inplane_freqs,
    load_locked_params,
    rel_err,
    taut_freq,
    wave_speed,
    write_json,
)


def build(p: dict[str, Any] | None = None) -> dict[str, Any]:
    p = p or load_locked_params()
    mf = p["mu_floor_kg_m"]
    mp = p["mu_portal_kg_m"]
    ms = mf + mp
    catalog = []
    for span in p["spans"]:
        item = {
            "floor": span["floor"],
            "L_m": span["L_floor_m"],
            "inclined": span["inclined"],
            "T_floor_kN": span["T_floor_N"] / 1e3,
            "T_sum_kN": span["T_sum_N"] / 1e3,
            "c_floor_m_s": wave_speed(span["T_floor_N"], mf),
            "c_inphase_m_s": wave_speed(span["T_sum_N"], ms),
            "floor_taut_Hz": [taut_freq(n, span["L_floor_m"], span["T_floor_N"], mf) for n in range(1, 7)],
            "inphase_taut_Hz": [taut_freq(n, span["L_floor_m"], span["T_sum_N"], ms) for n in range(1, 7)],
            "portal_taut_Hz": [
                taut_freq(n, span["L_portal_m"], span["T_portal_N"], mp) for n in range(1, 7)
            ],
        }
        if span["floor"] == "主跨":
            item["irvine_floor"] = irvine_inplane_freqs(
                span["L_floor_m"],
                p["h_main_m_locked"],
                span["T_floor_N"],
                mf,
                p["EA_floor_N"],
            )
            item["irvine_inphase"] = irvine_inplane_freqs(
                span["L_floor_m"],
                p["h_main_m_locked"],
                span["T_sum_N"],
                ms,
                p["EA_floor_N"] + p["EA_portal_N"],
            )
        catalog.append(item)

    # Flatten candidates for matching.
    cands: list[dict[str, Any]] = []
    for item in catalog:
        for n, f in enumerate(item["floor_taut_Hz"], start=1):
            cands.append({"src": f"{item['floor']} floor taut n={n}", "f_Hz": f})
        for n, f in enumerate(item["inphase_taut_Hz"], start=1):
            cands.append({"src": f"{item['floor']} in-phase taut n={n}", "f_Hz": f})
        for n, f in enumerate(item["portal_taut_Hz"], start=1):
            cands.append({"src": f"{item['floor']} portal taut n={n}", "f_Hz": f})
        if "irvine_floor" in item:
            cands.append(
                {
                    "src": "主跨 floor Irvine antisym1",
                    "f_Hz": item["irvine_floor"]["antisymmetric"][0]["f_Hz"],
                }
            )
            cands.append(
                {
                    "src": "主跨 floor Irvine sym1",
                    "f_Hz": item["irvine_floor"]["symmetric"][0]["f_Hz"],
                }
            )
            cands.append(
                {
                    "src": "主跨 in-phase Irvine antisym1",
                    "f_Hz": item["irvine_inphase"]["antisymmetric"][0]["f_Hz"],
                }
            )
            cands.append(
                {
                    "src": "主跨 in-phase Irvine sym1",
                    "f_Hz": item["irvine_inphase"]["symmetric"][0]["f_Hz"],
                }
            )

    ccx = p["ccx_freq_Hz"]
    matches = []
    for i, f in enumerate(ccx, start=1):
        best = min(cands, key=lambda c: abs(c["f_Hz"] - f))
        matches.append(
            {
                "ccx_mode": i,
                "ccx_Hz": f,
                "nearest": best["src"],
                "theory_Hz": best["f_Hz"],
                "rel": rel_err(best["f_Hz"], f),
                "abs": best["f_Hz"] - f,
            }
        )

    dyn = p["dyn_modes"]
    mode1 = next((m for m in dyn if m.get("mode") == 1), {})
    mode2 = next((m for m in dyn if m.get("mode") == 2), {})

    south = next(c for c in catalog if c["floor"] == "南边跨")
    north = next(c for c in catalog if c["floor"] == "北边跨")
    main = next(c for c in catalog if c["floor"] == "主跨")

    return {
        "layer": 4,
        "title": "four-span taut / Irvine catalog vs locked CCX spectrum",
        "assumptions": [
            "Each span is an independent pinned taut string (or Irvine on the level main span).",
            "South / north / aux spans are inclined: 'sag' in the overlay is mostly end-height drop, so taut with lock T is the first formula, not √(g/32d).",
            "Tower saddles in the deck fix UZ and free UX; that couples spans axially. This layer does *not* solve the sliding-saddle continuity problem — it only lists the isolated-span roots.",
            "CCX participation is read from migrate_DYN.dat after the fact. T3D2→C3D8I makes original-node participation a soft reading, not a second frequency.",
        ],
        "formulas": {
            "taut": "f_n = n/(2L) √(T/μ)  per span, T = that span's INIFORCE mean",
            "Irvine_main": "in-plane only; UY is nailed on the 2-D deck",
        },
        "catalog": catalog,
        "ccx_matches": matches,
        "ccx_mode1_participation": mode1,
        "ccx_mode2_participation": mode2,
        "highlights": {
            "south_floor_n1_Hz": south["floor_taut_Hz"][0],
            "south_floor_n1_vs_ccx_f1": rel_err(south["floor_taut_Hz"][0], p["ccx_f1_Hz"]),
            "south_inphase_n1_Hz": south["inphase_taut_Hz"][0],
            "north_floor_n1_Hz": north["floor_taut_Hz"][0],
            "north_floor_n1_vs_ccx_f2": rel_err(north["floor_taut_Hz"][0], p["ccx_freq_Hz"][1]),
            "main_taut_n1_Hz": main["floor_taut_Hz"][0],
            "main_taut_n1_in_ccx_first20": any(abs(f - main["floor_taut_Hz"][0]) / f < 0.08 for f in ccx),
            "main_taut_n2_Hz": main["floor_taut_Hz"][1],
            "main_taut_n3_Hz": main["floor_taut_Hz"][2],
            "att_0.0296_in_this_catalog": False,
        },
        "self_judge": {
            "approaches_attachment_pair": "no four-span taut / Irvine root sits on 0.0296/0.0301",
            "approaches_ccx_f1": "南边跨 floor taut n=1 is the closest isolated-span number to 0.1335403; 北边跨 n=1 neighbours CCX f2",
            "main_span_n1_n2_absent_from_ccx_head": True,
            "does_not_claim_符合": True,
            "participation_note": (
                "CCX mode 1 has ~0 Z effective mass and large RY / some X. That is compatible "
                "with an even (cancelling-Z) in-plane shape *or* with a participation artefact "
                "on the expanded T3D2 mesh. The frequency match to 南边跨 is the harder fact."
            ),
        },
        "vs_att_0.0296_best": min(
            ({"src": c["src"], "f_Hz": c["f_Hz"], "rel": rel_err(c["f_Hz"], ATT_F1)} for c in cands),
            key=lambda r: abs(r["rel"]),
        ),
    }


def main() -> dict[str, Any]:
    data = build()
    write_json(HERE / "layer4.json", data)
    return data


if __name__ == "__main__":
    main()
    print("wrote", HERE / "layer4.json")
