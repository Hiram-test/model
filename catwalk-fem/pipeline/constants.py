"""Frozen drawing / report constants. No TARGET-FREQ. No S10.db."""

from __future__ import annotations

# --- coordinate convention -------------------------------------------------
ORIGIN_STATION = "K16+876.000"
ORIGIN_STATION_M = 16_000.0 + 876.0  # 16876 m; only for detecting raw-chainage X
X_POSITIVE = "north_to_south"
Y_POSITIVE = "upstream_to_downstream"
Z_POSITIVE = "upward"
UNITS_INTERNAL = {"length": "m", "force": "N", "mass": "kg", "time": "s"}

# nominal four-span breaks (DRW-B from overall layout)
SPAN_BREAKS_NOMINAL = (0.0, 660.0, 2960.0, 3677.0, 4180.0)
SPAN_LENGTHS = (660.0, 2300.0, 717.0, 503.0)

# physical anchors (DRW-B / theory v1.2 §4)
FLOOR_ANCHOR_N = {"station": "K16+852.105", "x": -23.895}
FLOOR_ANCHOR_S = {"station": "K21+086.368", "x": 4210.368}
PORTAL_ANCHOR_N = {"station": "K16+831.091", "x": -44.909}
PORTAL_ANCHOR_S = {"station": "K21+101.700", "x": 4225.700}

# physical anchors stay in SEPARATE families. Do not union floor and portal.
ANCHOR_SPECS = (
    {**FLOOR_ANCHOR_N, "id": "FLOOR_N", "family": "floor", "role": "floor_rope", "end": "north",
     "source": "DRW-B / theory v1.2 §4; not the portal-rope north anchor"},
    {**FLOOR_ANCHOR_S, "id": "FLOOR_S", "family": "floor", "role": "floor_rope", "end": "south",
     "source": "DRW-B / theory v1.2 §4; not the portal-rope south anchor"},
    {**PORTAL_ANCHOR_N, "id": "PORTAL_N", "family": "portal", "role": "portal_rope", "end": "north",
     "source": "DRW-B / theory v1.2 §4; not the floor-rope north anchor"},
    {**PORTAL_ANCHOR_S, "id": "PORTAL_S", "family": "portal", "role": "portal_rope", "end": "south",
     "source": "DRW-B / theory v1.2 §4; not the floor-rope south anchor"},
)
N_PORTALS_PER_DECK = 71
N_PORTALS_BOTH_DECKS = 142
N_CROSS_PASSAGES = 21
PASSAGE_MATCH_TOL_M = 12.0
PORTAL_MATCH_TOL_M = 12.0
ANCHOR_MATCH_TOL_M = 8.0  # < 15.332 m south floor/portal separation
ANCHOR_END_BAND_M = 10.0
PASSAGE_LABELS = (
    "P01", "P02", "P03",
    "P04", "P05", "P06", "P07", "P08", "P09",
    "H1", "H2", "H3", "H4", "H5", "H6", "H7",
    "H8", "H9", "H10",
    "H11", "H12",
)

# saddles and formed catwalk line (CALC-INPUT, 复核报告表1-5/1-9)
SADDLE_N = {"station": "K17+542.679", "x": 666.679, "z": 340.600, "source": "CALC-INPUT"}
SADDLE_S = {"station": "K19+829.321", "x": 2953.321, "z": 340.600, "source": "CALC-INPUT"}
MIDSPAN = {"station": "K18+686.000", "x": 1810.000, "z": 113.300, "source": "CALC-INPUT"}
SAG_FORMED_M = 227.300  # 340.600 - 113.300; NOT the 255.56 m main-cable control line
FREE_SPAN_SADDLE_TO_SADDLE = 2286.642  # 2953.321 - 666.679

# drop points (boundary sensitivity, not default supports)
DROP_N = {"station": "K17+553.300", "x": 677.300, "z": 334.645}
DROP_S = {"station": "K19+818.700", "x": 2942.700, "z": 334.537}

DECK_HALF_SPACING = 21.45  # two deck centre-lines, 42.90 m apart
FLOOR_Y_LOCAL = tuple(s * (0.85 + 0.26 * k) for s in (-1.0, 1.0) for k in range(8))

# 71 portals per deck (DRW-B, 1225 MD0-01/MD0-02 dimension chains)
PORTAL_X = (
    45, 102, 159, 216, 273, 330, 387, 444, 501, 558, 615,
    724, 781, 838, 895, 952, 1009, 1066, 1123, 1180, 1237, 1294, 1351,
    1402, 1453, 1504, 1555, 1606, 1657, 1708, 1759, 1810, 1861, 1912, 1963,
    2014, 2065, 2116, 2167, 2218, 2269, 2326, 2383, 2440, 2497, 2554, 2611,
    2668, 2725, 2782, 2839, 2896,
    3018.5, 3078.5, 3138.5, 3198.5, 3258.5, 3318.5, 3378.5, 3438.5, 3498.5,
    3558.5, 3618.5,
    3729, 3786, 3843, 3900, 3957, 4014, 4071, 4128,
)

# 21 cross-passages, 2025 drawing / 2026 report branch
PASSAGE_X = (
    159, 330, 501,
    838, 1009, 1180, 1351, 1504, 1657,
    1810, 1963, 2116, 2269, 2440, 2611, 2782,
    3138.5, 3318.5, 3498.5,
    3843, 4014,
)

G = 9.80665

# ropes (DRW-A / 复核报告)
ROPE_FLOOR = {
    "name": "MAT-ROPE-FLOOR",
    "n_per_deck": 16,
    "diameter_m": 0.050,
    "mu_kgpm": 12.038,
    "E_Pa": 1.20e11,
    "A_m2": 1400.42e-6,
    "nu": 0.30,
    "source": "CALC-INPUT E,A; DRW-A mu phi50",
}
ROPE_PORTAL = {
    "name": "MAT-ROPE-PORTAL",
    "n_per_deck": 6,
    "diameter_m": 0.050,
    "mu_kgpm": 12.038,
    "E_Pa": 1.20e11,
    "A_m2": 1400.42e-6,
    "nu": 0.30,
    "source": "2026 report / later drawing phi50",
}
ROPE_HAND_U = {
    "name": "MAT-ROPE-HAND-U",
    "n_per_deck": 2,
    "diameter_m": 0.036,
    "mu_kgpm": 5.42,
    "E_Pa": 1.20e11,
    "A_m2": 0.25 * 3.141592653589793 * 0.036**2,
    "nu": 0.30,
    "source": "DRW-A phi36; A from diameter, ASSUMP circular",
}
ROPE_HAND_L = {
    "name": "MAT-ROPE-HAND-L",
    "n_per_deck": 4,
    "diameter_m": 0.020,
    "mu_kgpm": 1.67,
    "E_Pa": 1.20e11,
    "A_m2": 0.25 * 3.141592653589793 * 0.020**2,
    "nu": 0.30,
    "source": "DRW-A phi20; A from diameter, ASSUMP circular",
}
STEEL = {
    "name": "MAT-STEEL",
    "E_Pa": 2.06e11,
    "nu": 0.30,
    "rho": 7850.0,
    "source": "STD structural steel",
}

# report load packages (CALC-INPUT). Do not add drawing rope mu on top of these
# without subtracting the overlapping rope self-weight.
FLOOR_SYSTEM_KNPM = 2.766  # per deck, includes mesh/wood/small beams/cables
PORTAL_ROPE_GROUP_KNPM = 0.709  # six portal ropes per deck

# live / wind: registered assumptions, not code-invented coefficients
PERSONNEL_KPA = 1.5
PERSONNEL_WIDTH_M = 5.60
PERSONNEL_SOURCE = "ASSUMP construction walkway 1.5 kPa on 5.60 m effective width"
WIND_KNPM = 0.50
WIND_SOURCE = "ASSUMP construction wind 0.50 kN/m per deck, +Y"

SUPPORT_MATCH_TOL_M = 8.0
NODE_MERGE_TOL_M = 0.005

# STEP release (geometry only)
STEP_RELEASE = "catwalk-attachment23-v2.0-s10-20260716"
STEP_NAME = "cw_S10_0716t050342_a4_centerline.step"
STEP_SHA256 = "d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344"

# TARGET-FREQ lives in catwalk-fem/isolated/ and must not be imported here.

# primary supports in the SAME x convention (physical first)
PRIMARY_SUPPORTS = (
    {"id": "X0", "x": 0.0, "kind": "north_nominal_end", "source": "DRW-B"},
    {"id": "NT_SADDLE", "x": 666.679, "kind": "north_tower_saddle", "source": "CALC-INPUT"},
    {"id": "ST_SADDLE", "x": 2953.321, "kind": "south_tower_saddle", "source": "CALC-INPUT"},
    {"id": "AUX", "x": 3677.0, "kind": "south_aux_break", "source": "DRW-B"},
    {"id": "X4180", "x": 4180.0, "kind": "south_nominal_end", "source": "DRW-B"},
)
AUDIT_STATIONS = (
    {"id": "NT_NOMINAL", "x": 660.0, "kind": "north_tower_nominal"},
    {"id": "ST_NOMINAL", "x": 2960.0, "kind": "south_tower_nominal"},
)
