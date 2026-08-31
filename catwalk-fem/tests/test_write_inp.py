"""write_inp must emit a complete self-consistent deck."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(HERE))

from formfind import initial_state, l0_wave_frequency  # noqa: E402
from write_inp import write_calculix_inp  # noqa: E402


def _toy_mesh():
    xs = np.unique(
        np.concatenate(
            [
                np.linspace(0.0, 4180.0, 80),
                [0.0, 666.679, 1810.0, 2953.321, 3677.0, 4180.0, 4210.368],
            ]
        )
    )
    xs_portal = np.unique(np.concatenate([xs, [-44.909, 4225.700]]))
    coords = []
    n1 = []
    n2 = []
    role = []
    side = []
    for s, y0 in (("upstream", -21.45), ("downstream", 21.45)):
        base = len(coords)
        for x in xs:
            coords.append((x, y0 + 2.67, 340.6 - 227.3 * (1 - ((x - 1810) / 1150) ** 2) if 660 < x < 2960 else 200.0))
        for i in range(len(xs) - 1):
            n1.append(base + i)
            n2.append(base + i + 1)
            role.append("floor_rope")
            side.append(s)
        pbase = len(coords)
        for x in xs_portal:
            coords.append((x, y0 + 3.20, 340.6 - 227.3 * (1 - ((x - 1810) / 1150) ** 2) if 660 < x < 2960 else 208.0))
        for i in range(len(xs_portal) - 1):
            n1.append(pbase + i)
            n2.append(pbase + i + 1)
            role.append("portal_rope")
            side.append(s)
        # a few portal beams at saddles
        a = base + int(np.argmin(np.abs(xs - 666.679)))
        coords.append((xs[a - base], y0, coords[a][2] + 3.0))
        n1.append(a)
        n2.append(len(coords) - 1)
        role.append("portal_or_beam")
        side.append(s)
    return {
        "coords": np.asarray(coords, float),
        "n1": np.asarray(n1, np.int64),
        "n2": np.asarray(n2, np.int64),
        "role": np.asarray(role, object),
        "side": np.asarray(side, object),
    }


def test_complete_keywords(tmp_path: Path | None = None):
    out = (tmp_path or Path("/tmp")) / "toy_catwalk.inp"
    meta = write_calculix_inp(_toy_mesh(), out, include_frequency=True)
    text = out.read_text()
    assert meta["complete"]
    assert meta["xmin_shift_used"] is False
    assert meta["target_freq_in_deck"] is False
    for key in (
        "*HEADING",
        "K16+876",
        "*NODE",
        "*ELEMENT, TYPE=T3D2",
        "*ELEMENT, TYPE=B31",
        "*MATERIAL",
        "*SOLID SECTION",
        "*BEAM SECTION",
        "*BOUNDARY",
        "*INITIAL CONDITIONS, TYPE=STRESS",
        "LC-DEAD-PRESTRESS",
        "LC-PERSONNEL-UNIFORM",
        "LC-WIND-Y",
        "LC-FREQ",
        "*CLOAD",
        "*DLOAD",
    ):
        assert key in text, key
    assert "255.56" not in text
    assert meta["supports"]["NT_SADDLE"]["n"] > 0
    assert meta["supports"]["ST_SADDLE"]["n"] > 0
    assert "N_FLOOR_ANCHOR" in text
    assert "N_PORTAL_ANCHOR" in text
    assert meta["anchor_nsets_disjoint"] is True
    assert meta["anchors"]["FLOOR_S"]["n"] > 0
    assert meta["anchors"]["PORTAL_S"]["n"] > 0
    assert abs(meta["anchors"]["FLOOR_S"]["x_mean"] - meta["anchors"]["PORTAL_S"]["x_mean"]) > 5.0
    assert meta["hash"]["sha256"]
    assert Path(meta["hash"]["sidecar"]).is_file()
    assert meta["ic_elset_uniaxial"] is False
    assert meta["ic_ccx_2_21_legal"] is True
    assert meta["ic_n_intpt"] == 8
    assert meta["ic_n_rows"] == meta["ic_n_floor_rows"] + meta["ic_n_portal_rows"]
    assert meta["ic_n_rows"] > 0
    ic_body = text.split("*INITIAL CONDITIONS, TYPE=STRESS", 1)[1].split("*STEP", 1)[0]
    ic_data = [ln.strip() for ln in ic_body.splitlines() if ln.strip() and not ln.startswith("*") and not ln.startswith("**")]
    assert ic_data
    assert all(ln.split(",")[0].strip().isdigit() for ln in ic_data)
    assert all(len([p for p in ln.split(",") if p.strip()]) == 8 for ln in ic_data)
    assert not any(ln.startswith("E_FLOOR_ROPE") or ln.startswith("E_PORTAL_ROPE") for ln in ic_data)
    from write_inp import uniaxial_pk2_global  # noqa: E402

    sxx, syy, szz, sxy, sxz, syz = uniaxial_pk2_global((1.0, 0.0, 0.0), 1.0e8)
    assert abs(sxx - 1.0e8) < 1e-6
    assert abs(syy) < 1e-12 and abs(szz) < 1e-12
    sxx, syy, szz, sxy, sxz, syz = uniaxial_pk2_global((0.0, 0.0, 2.0), 1.0e8)
    assert abs(szz - 1.0e8) < 1e-6
    assert abs(sxx) < 1e-12


def test_l0_frequency_matches_theory():
    f1 = l0_wave_frequency(227.300, 1)
    assert abs(f1 - 0.036718559) < 1e-6
    state = initial_state()
    assert state["sag_m"] == 227.300
    assert state["H_floor_deck_saddle_N"] > 1e6


if __name__ == "__main__":
    test_complete_keywords()
    test_l0_frequency_matches_theory()
    print("test_write_inp ok")
