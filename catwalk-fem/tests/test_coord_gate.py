"""Unit tests for x = chainage − K16+876. No STEP required."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(HERE))

from coord import apply_transform, infer_x_transform  # noqa: E402
from constants import SADDLE_N, SADDLE_S  # noqa: E402
from write_inp import support_sets  # noqa: E402


def test_identity_when_saddles_already_aligned():
    xs = np.linspace(0.0, 4180.0, 400)
    ys = np.where(np.arange(400) % 2 == 0, 21.45, -21.45)
    zs = np.full(400, 120.0)
    zs[np.abs(xs - 666.679) < 20] = 340.6
    zs[np.abs(xs - 2953.321) < 20] = 340.6
    xyz = np.column_stack([xs, ys, zs])
    tr = infer_x_transform(xyz)
    assert tr["decision"] == "identity"
    assert abs(tr["x_shift_m"]) < 1e-9
    assert tr["pass_saddle_align"]


def test_does_not_prefer_xmin_shift_on_truncated_north():
    xs = np.linspace(21.0, 4255.0, 400)
    ys = np.full(400, 24.12)
    zs = np.full(400, 120.0)
    zs[np.abs(xs - 666.679) < 25] = 340.6
    zs[np.abs(xs - 2953.321) < 25] = 340.6
    tr = infer_x_transform(np.column_stack([xs, ys, zs]))
    assert tr["decision"] == "identity"
    moved = apply_transform(np.array([[21.0, 0.0, 0.0]]), tr["x_shift_m"])
    assert abs(moved[0, 0] - 21.0) < 1e-9


def test_support_sets_use_same_x():
    xs = np.array([0.0, 666.679, 1810.0, 2953.321, 3677.0, 4180.0])
    coords = np.column_stack([xs, np.zeros(6), np.array([60, 340, 113, 340, 200, 80], float)])
    sets = support_sets(coords)
    assert sets["NT_SADDLE"]["n"] == 1
    assert abs(sets["NT_SADDLE"]["x_mean"] - SADDLE_N["x"]) < 1e-6
    assert abs(sets["ST_SADDLE"]["x_mean"] - SADDLE_S["x"]) < 1e-6
    assert sets["X0"]["n"] == 1
    assert sets["X4180"]["n"] == 1


if __name__ == "__main__":
    test_identity_when_saddles_already_aligned()
    test_does_not_prefer_xmin_shift_on_truncated_north()
    test_support_sets_use_same_x()
    print("test_coord_gate ok")
