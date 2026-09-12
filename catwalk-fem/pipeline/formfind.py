"""Independent cable-force seed. Drawing/report only. No S10.db, no TARGET-FREQ."""

from __future__ import annotations

try:
    from .constants import (
        FLOOR_SYSTEM_KNPM,
        FREE_SPAN_SADDLE_TO_SADDLE,
        G,
        PORTAL_ROPE_GROUP_KNPM,
        ROPE_FLOOR,
        ROPE_PORTAL,
        SAG_FORMED_M,
        SPAN_LENGTHS,
    )
except ImportError:
    from constants import (
        FLOOR_SYSTEM_KNPM,
        FREE_SPAN_SADDLE_TO_SADDLE,
        G,
        PORTAL_ROPE_GROUP_KNPM,
        ROPE_FLOOR,
        ROPE_PORTAL,
        SAG_FORMED_M,
        SPAN_LENGTHS,
    )


def horizontal_force(w_npm: float, span_m: float, sag_m: float) -> float:
    if sag_m <= 0.0:
        raise ValueError("sag must be positive")
    return w_npm * span_m**2 / (8.0 * sag_m)


def l0_wave_frequency(sag_m: float, n: int = 1) -> float:
    """Parabolic equal-support skeleton f_n = n * sqrt(g / 32 h). Mass cancels."""
    return n * (G / (32.0 * sag_m)) ** 0.5


def initial_state() -> dict:
    w_floor = FLOOR_SYSTEM_KNPM * 1000.0  # N/m per deck
    w_portal = PORTAL_ROPE_GROUP_KNPM * 1000.0
    l_saddle = FREE_SPAN_SADDLE_TO_SADDLE
    l_nominal = SPAN_LENGTHS[1]
    h = SAG_FORMED_M
    H_floor_saddle = horizontal_force(w_floor, l_saddle, h)
    H_floor_nominal = horizontal_force(w_floor, l_nominal, h)
    H_portal_saddle = horizontal_force(w_portal, l_saddle, h)
    n_floor = ROPE_FLOOR["n_per_deck"]
    n_portal = ROPE_PORTAL["n_per_deck"]
    return {
        "control": "sag_and_distributed_load",
        "sag_m": h,
        "forbidden_sag_m": 255.56,
        "w_floor_npm": w_floor,
        "w_portal_npm": w_portal,
        "L_saddle_m": l_saddle,
        "L_nominal_m": l_nominal,
        "H_floor_deck_saddle_N": H_floor_saddle,
        "H_floor_deck_nominal_N": H_floor_nominal,
        "H_floor_rope_saddle_N": H_floor_saddle / n_floor,
        "H_portal_deck_saddle_N": H_portal_saddle,
        "H_portal_rope_saddle_N": H_portal_saddle / n_portal,
        "sigma_floor_Pa": (H_floor_saddle / n_floor) / ROPE_FLOOR["A_m2"],
        "sigma_portal_Pa": (H_portal_saddle / n_portal) / ROPE_PORTAL["A_m2"],
        "l0_f1_hz": l0_wave_frequency(h, 1),
        "l0_f2_hz": l0_wave_frequency(h, 2),
        "source": "CALC-INPUT w from report table 1-1/1-3; h=227.300 m; L from table 1-9 saddles",
        "independent_of": ["S10.db", "B00", "MCT", "TARGET-FREQ"],
    }
