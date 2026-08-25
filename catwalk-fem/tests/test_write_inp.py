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
                [0.0, 666.679, 1810.0, 2953.321, 3677.0, 4180.0],
            ]
        )
    )
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
