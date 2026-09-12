"""Map STEP XYZ into x = chainage − K16+876. Never subtract xmin by default."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    from .constants import (
        DECK_HALF_SPACING,
        MIDSPAN,
        ORIGIN_STATION_M,
        SADDLE_N,
        SADDLE_S,
        SAG_FORMED_M,
        SPAN_BREAKS_NOMINAL,
    )
except ImportError:
    from constants import (
        DECK_HALF_SPACING,
        MIDSPAN,
        ORIGIN_STATION_M,
        SADDLE_N,
        SADDLE_S,
        SAG_FORMED_M,
        SPAN_BREAKS_NOMINAL,
    )


def _high_z_x_peaks(xyz: np.ndarray, z_band: float = 20.0) -> list[float]:
    z = xyz[:, 2]
    high = xyz[z >= z.max() - z_band]
    if high.size == 0:
        return []
    # two strongest X modes on a 20 m histogram
    lo, hi = float(high[:, 0].min()), float(high[:, 0].max())
    if hi - lo < 1.0:
        return [float(np.median(high[:, 0]))]
    edges = np.linspace(lo, hi, max(8, int((hi - lo) / 20.0) + 1))
    hist, edges = np.histogram(high[:, 0], bins=edges)
    order = np.argsort(hist)[::-1]
    peaks = []
    for idx in order:
        if hist[idx] <= 0:
            continue
        centre = 0.5 * (edges[idx] + edges[idx + 1])
        if all(abs(centre - old) > 200.0 for old in peaks):
            peaks.append(float(centre))
        if len(peaks) == 2:
            break
    return sorted(peaks)


def infer_x_transform(xyz_m: np.ndarray) -> dict:
    """Decide how raw metre coordinates become x = chainage − K16+876."""
    xs = xyz_m[:, 0]
    peaks = _high_z_x_peaks(xyz_m)
    expected = (SADDLE_N["x"], SADDLE_S["x"])

    candidates = {
        "identity": 0.0,
        "minus_xmin": float(xs.min()),
        "minus_raw_chainage": ORIGIN_STATION_M,
    }

    def score(shift: float) -> float:
        if len(peaks) < 2:
            return 1.0e9
        moved = sorted(p - shift for p in peaks)
        return abs(moved[0] - expected[0]) + abs(moved[1] - expected[1])

    ranked = sorted(candidates.items(), key=lambda kv: score(kv[1]))
    name, shift = ranked[0]
    residual = score(shift)
    # identity wins unless another candidate is materially better
    if name != "identity" and score(0.0) <= residual + 15.0:
        name, shift, residual = "identity", 0.0, score(0.0)

    moved_peaks = sorted(p - shift for p in peaks) if peaks else []

    def saddle_z_ok(x_shift: float) -> dict:
        xx = xyz_m[:, 0] - x_shift
        zz = xyz_m[:, 2]
        rec = {}
        ok = True
        for key, spec in (("north", SADDLE_N), ("south", SADDLE_S)):
            near = np.abs(xx - spec["x"]) < 12.0
            z90 = float(np.quantile(zz[near], 0.90)) if np.any(near) else None
            rec[f"{key}_n"] = int(np.count_nonzero(near))
            rec[f"{key}_z_p90"] = z90
            rec[f"{key}_expected_z"] = spec["z"]
            if z90 is None or z90 < spec["z"] - 40.0:
                ok = False
        rec["ok"] = ok
        return rec

    z_ev = saddle_z_ok(shift)
    # Histogram modes of high-Z points sit on portal clusters (~700/3023), not
    # the saddles themselves. Identity is confirmed when expected saddle X
    # already carries the tower-top height in this metre frame.
    xspan_ok = float(xs.min() - shift) > -50.0 and float(xs.max() - shift) < 5000.0
    return {
        "decision": name,
        "x_shift_m": shift,
        "tower_x_raw_m": peaks,
        "tower_x_after_m": moved_peaks,
        "expected_saddle_x_m": list(expected),
        "saddle_residual_m": residual,
        "saddle_z_evidence": z_ev,
        "pass_saddle_align": bool(z_ev["ok"] and xspan_ok),
        "histogram_residual_note": "high-Z histogram modes may sit on portal clusters, not saddles",
        "rule": "do_not_subtract_xmin_unless_saddle_evidence_requires_it",
    }


def apply_transform(xyz_m: np.ndarray, shift: float) -> np.ndarray:
    out = np.array(xyz_m, dtype=np.float64, copy=True)
    out[:, 0] -= shift
    return out


def geometry_audit(xyz: np.ndarray, transform: dict) -> dict:
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    mid = (x > 1750.0) & (x < 1870.0)
    north_saddle = np.abs(x - SADDLE_N["x"]) < 12.0
    south_saddle = np.abs(x - SADDLE_S["x"]) < 12.0
    mid_z = float(np.median(z[mid])) if np.any(mid) else None
    z_nt = float(np.quantile(z[north_saddle], 0.90)) if np.any(north_saddle) else None
    z_st = float(np.quantile(z[south_saddle], 0.90)) if np.any(south_saddle) else None
    sag = None
    if z_nt is not None and mid_z is not None:
        sag = 0.5 * (z_nt + (z_st or z_nt)) - mid_z
    y_pos = y[y > 0]
    y_neg = y[y < 0]
    return {
        "n_points": int(len(xyz)),
        "x_min": float(x.min()),
        "x_max": float(x.max()),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        "z_min": float(z.min()),
        "z_max": float(z.max()),
        "covers_nominal_0_4180": bool(x.min() <= 5.0 and x.max() >= 4175.0),
        "deck_half_spacing_expected": DECK_HALF_SPACING,
        "y_pos_median": float(np.median(y_pos)) if y_pos.size else None,
        "y_neg_median": float(np.median(y_neg)) if y_neg.size else None,
        "two_decks": bool(y_pos.size and y_neg.size),
        "z_north_saddle_p90": z_nt,
        "z_south_saddle_p90": z_st,
        "z_midspan_median": mid_z,
        "sag_from_geometry_m": sag,
        "sag_report_m": SAG_FORMED_M,
        "sag_abs_err_m": None if sag is None else abs(sag - SAG_FORMED_M),
        "nominal_breaks": list(SPAN_BREAKS_NOMINAL),
        "midspan_expected_z": MIDSPAN["z"],
        "transform": transform,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
