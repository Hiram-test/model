#!/usr/bin/env python3
"""Build the 974211b2 theory-frequency stack. Does not touch the main deck."""

from __future__ import annotations

from common import (
    ATT_F1,
    ATT_F2,
    CCX_F1_LOCK,
    FORBIDDEN_HALF,
    HERE,
    MAIN,
    MAIN_SHA,
    dumps,
    load_locked_params,
    sha256_file,
    write_json,
)
from layer1_two_cable import build as build1
from layer2_dual_mct import build as build2
from layer3_passages import build as build3
from layer4_four_span import build as build4


def _svg(compare: dict) -> str:
    width, height = 920, 420
    pad_l, pad_r, pad_t, pad_b = 70, 24, 36, 48
    fmax = 0.18
    marks = compare["spectrum_marks_Hz"]

    def x(f: float) -> float:
        return pad_l + (f / fmax) * (width - pad_l - pad_r)

    def y(row: int) -> float:
        return pad_t + 55 + row * 70

    colours = {
        "att": "#1f4e79",
        "L1": "#2e7d32",
        "L2": "#e65100",
        "L3": "#6a1b9a",
        "ccx": "#b71c1c",
    }
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffef8"/>',
        '<text x="16" y="24" font-size="14" font-family="ui-sans-serif,sans-serif">'
        "974211b2 theory layers vs 附件2-3 first pair and locked CCX f1 (Hz)</text>",
    ]
    for f in (0.00, 0.03, 0.06, 0.09, 0.12, 0.15, 0.18):
        xx = x(f)
        out.append(f'<line x1="{xx:.1f}" y1="{pad_t+20}" x2="{xx:.1f}" y2="{height-pad_b}" stroke="#eee"/>')
        out.append(
            f'<text x="{xx:.1f}" y="{height-18}" text-anchor="middle" font-size="11">{f:.2f}</text>'
        )
    rows = [
        (0, "附件2-3 首对", [marks["att1"], marks["att2"]], colours["att"]),
        (1, "L1 主跨张弦/垂度", [marks["l1_sag"], marks["l1_taut"]], colours["L1"]),
        (2, "L2 南边跨 / 主跨合相 n=3", [marks["l2_south"], marks["l2_inphase_n3"]], colours["L2"]),
        (3, "L3 扭转 lockT / sagH", [marks["l3_tor_lock"], marks["l3_tor_sag"]], colours["L3"]),
        (4, "CCX f1 锁", [marks["ccx_f1"]], colours["ccx"]),
    ]
    for i, title, freqs, col in rows:
        yy = y(i)
        out.append(
            f'<text x="12" y="{yy+4}" font-size="11" font-family="ui-sans-serif,sans-serif">{title}</text>'
        )
        out.append(
            f'<line x1="{x(0):.1f}" y1="{yy}" x2="{x(fmax):.1f}" y2="{yy}" stroke="#ccc"/>'
        )
        for f in freqs:
            if 0 <= f <= fmax:
                out.append(f'<circle cx="{x(f):.1f}" cy="{yy}" r="6" fill="{col}"/>')
                out.append(
                    f'<text x="{x(f):.1f}" y="{yy-12}" text-anchor="middle" font-size="10" fill="{col}">{f:.4f}</text>'
                )
            else:
                out.append(
                    f'<text x="{width-8}" y="{yy+4}" text-anchor="end" font-size="10" fill="{col}">off {f:.3f}</text>'
                )
    out.append(
        '<text x="16" y="408" font-size="10" fill="#555">'
        "Not a fit claim. VM output is not a scientific statement.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> dict:
    params = load_locked_params()
    if sha256_file(MAIN) != MAIN_SHA:
        raise SystemExit("main deck moved; refuse to write theory on a different hash")
    l1 = build1(params)
    l2 = build2(params)
    l3 = build3(params)
    l4 = build4(params)
    write_json(HERE / "params.json", {k: v for k, v in params.items() if k != "dyn_modes"})
    write_json(HERE / "layer1.json", l1)
    write_json(HERE / "layer2.json", l2)
    write_json(HERE / "layer3.json", l3)
    write_json(HERE / "layer4.json", l4)

    def row(layer: str, name: str, f: float) -> dict:
        return {
            "layer": layer,
            "name": name,
            "f_Hz": f,
            "vs_0.0296_rel": (f - ATT_F1) / ATT_F1,
            "vs_0.1335403_rel": (f - CCX_F1_LOCK) / CCX_F1_LOCK,
        }

    pick = [
        row("L1", "sag_n1", l1["spectrum"]["sag_gMCT_Hz"][0]),
        row("L1", "taut_lockT_n1", l1["spectrum"]["taut_lockT_Hz"][0]),
        row("L1", "irvine_lockT_antisym1", l1["irvine_lockT"]["antisymmetric"][0]["f_Hz"]),
        row("L1", "irvine_lockT_sym1", l1["irvine_lockT"]["symmetric"][0]["f_Hz"]),
        row("L1", "irvine_lockT_first_inplane", l1["irvine_lockT"]["first_inplane_Hz"]),
        row("L2", "inphase_n1", next(r["f_Hz"] for r in l2["compare_rows"] if r["name"] == "inphase_rigid_n1")),
        row("L2", "south_span_floor_n1", next(r["f_Hz"] for r in l2["compare_rows"] if r["name"] == "south_span_floor_n1")),
        row("L2", "inphase_n3", next(r["f_Hz"] for r in l2["compare_rows"] if r["name"] == "inphase_rigid_n3")),
        row("L3", "torsion_lockT_n1", l3["torsion_lockT"]["f1_Hz"]),
        row("L3", "torsion_sagH_n1", l3["torsion_sagH"]["f1_Hz"]),
        row("L3", "two_deck_common_n1", l3["two_deck"]["mass_report_k0"][0]["f_common_Hz"]),
        row("L4", "south_floor_n1", l4["highlights"]["south_floor_n1_Hz"]),
        row("L4", "north_floor_n1", l4["highlights"]["north_floor_n1_Hz"]),
        row("L4", "main_taut_n1", l4["highlights"]["main_taut_n1_Hz"]),
        row("CCX", "f1_lock", CCX_F1_LOCK),
        row("ATT", "pair_0.0296", ATT_F1),
        row("ATT", "pair_0.0301", ATT_F2),
    ]

    nearest_att = min((r for r in pick if r["layer"] not in {"CCX", "ATT"}), key=lambda r: abs(r["vs_0.0296_rel"]))
    nearest_ccx = min((r for r in pick if r["layer"] not in {"CCX", "ATT"}), key=lambda r: abs(r["vs_0.1335403_rel"]))

    compare = {
        "kind": "theory_freq_974211b2_compare",
        "imported_TARGET_FREQ": False,
        "used_0.06438": False,
        "wrote_符合": False,
        "scientific_success": False,
        "main_sha256": MAIN_SHA,
        "main_rewritten": False,
        "ccx_f1_Hz": CCX_F1_LOCK,
        "forbidden_half_Hz": FORBIDDEN_HALF,
        "att_pair_Hz": [ATT_F1, ATT_F2],
        "rows": pick,
        "nearest_to_0.0296": nearest_att,
        "nearest_to_ccx_f1": nearest_ccx,
        "judgment": {
            "layer_closest_to_attachment_pair": "L1 sag n=1 and L3 sag-H torsion (same 0.03-order band). Locked-T roots stay ~0.04 Hz.",
            "layer_closest_to_ccx_f1": "L2/L4 南边跨 taut n=1.",
            "mechanism": (
                "CCX is a Y-pinned 2-D dual line. It cannot form the two-deck near-doublet. "
                "Its locked f1 sits on a short-span in-plane taut root (~0.133), not on the "
                "main-span taut n=1 (~0.042) and not on 0.0296. The spoken '约高一倍' is not "
                "used as a number; ratios vs 0.0296 and vs main-span n=1 are reported instead. "
                "0.06438 is not a CCX frequency."
            ),
            "still_open": (
                "Main-span taut n=1 and n=2 do not appear at the head of the CCX 20. "
                "Isolated-span theory does not close that absence. Sliding-saddle 4-span "
                "continuity and T3D2 expansion remain open. Not a stop."
            ),
            "does_not_claim_符合": True,
            "handoff": "paper_post",
        },
        "spectrum_marks_Hz": {
            "att1": ATT_F1,
            "att2": ATT_F2,
            "l1_sag": l1["spectrum"]["sag_gMCT_Hz"][0],
            "l1_taut": l1["spectrum"]["taut_lockT_Hz"][0],
            "l2_south": next(r["f_Hz"] for r in l2["compare_rows"] if r["name"] == "south_span_floor_n1"),
            "l2_inphase_n3": next(r["f_Hz"] for r in l2["compare_rows"] if r["name"] == "inphase_rigid_n3"),
            "l3_tor_lock": l3["torsion_lockT"]["f1_Hz"],
            "l3_tor_sag": l3["torsion_sagH"]["f1_Hz"],
            "ccx_f1": CCX_F1_LOCK,
        },
    }
    write_json(HERE / "COMPARE.json", compare)
    (HERE / "spectrum.svg").write_text(_svg(compare), encoding="utf-8")

    digest_lines = []
    for name in (
        "params.json",
        "layer1.json",
        "layer2.json",
        "layer3.json",
        "layer4.json",
        "COMPARE.json",
        "spectrum.svg",
        "MODELING.md",
    ):
        path = HERE / name
        if path.is_file():
            digest_lines.append(f"{sha256_file(path)}  {name}")
    (HERE / "HASHES.sha256").write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    return compare


if __name__ == "__main__":
    c = main()
    print("main", c["main_sha256"][:8], "untouched")
    print("nearest 0.0296", c["nearest_to_0.0296"])
    print("nearest CCX", c["nearest_to_ccx_f1"])
    print("wrote", HERE)
