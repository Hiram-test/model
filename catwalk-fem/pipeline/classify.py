"""Classify metre segments against drawing topology, not S10 properties."""

from __future__ import annotations

import numpy as np

try:
    from .constants import DECK_HALF_SPACING, FLOOR_Y_LOCAL
except ImportError:
    from constants import DECK_HALF_SPACING, FLOOR_Y_LOCAL

ROLES = (
    "floor_rope",
    "portal_rope",
    "handrail_rope",
    "longitudinal_other",
    "cross_passage",
    "portal_or_beam",
    "short_other",
)


def _nearest_center(y: np.ndarray) -> np.ndarray:
    return np.where(y >= 0.0, DECK_HALF_SPACING, -DECK_HALF_SPACING)


def _floor_y_absolute() -> np.ndarray:
    return np.asarray(
        [center + loc for center in (DECK_HALF_SPACING, -DECK_HALF_SPACING) for loc in FLOOR_Y_LOCAL],
        dtype=np.float64,
    )


def classify_segments(p1: np.ndarray, p2: np.ndarray) -> dict:
    mid = 0.5 * (p1 + p2)
    delta = p2 - p1
    length = np.linalg.norm(delta, axis=1)
    dx = np.abs(delta[:, 0])
    dy = np.abs(delta[:, 1])
    y = mid[:, 1]
    z = mid[:, 2]
    side = np.where(y >= 0.0, "downstream", "upstream")
    local_y = y - _nearest_center(y)
    floor_abs = _floor_y_absolute()
    y_to_floor = np.min(np.abs(y[:, None] - floor_abs[None, :]), axis=1)

    roles = np.full(len(p1), "short_other", dtype=object)
    long_like = (dx >= dy) & (length > 2.0)
    cross = (dy >= 15.0) & (length > 20.0)
    transverse = (dx < 4.0) & (dy >= 1.5) & (length < 20.0) & ~cross

    roles[cross] = "cross_passage"
    roles[transverse] = "portal_or_beam"

    floor = long_like & (y_to_floor < 0.10)
    roles[floor] = "floor_rope"

    # remaining long members: split by height relative to nearby floor
    remain = long_like & (roles == "short_other")
    if np.any(remain) and np.any(floor):
        floor_z_ref = np.median(z[floor])
        high = remain & (z > floor_z_ref + 1.20)
        midh = remain & ~high
        # portal ropes sit farther from deck centre than handrails
        roles[high & (np.abs(local_y) >= 2.0)] = "portal_rope"
        roles[high & (np.abs(local_y) < 2.0)] = "handrail_rope"
        roles[midh & (y_to_floor < 0.35)] = "floor_rope"
        roles[remain & (roles == "short_other")] = "longitudinal_other"
    elif np.any(remain):
        roles[remain] = "longitudinal_other"

    return {
        "p1": p1,
        "p2": p2,
        "mid": mid,
        "length": length,
        "role": roles,
        "side": side,
        "local_y": local_y,
        "counts": {role: int(np.sum(roles == role)) for role in ROLES},
    }
