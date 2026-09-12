"""Locked-parameter helpers for the 974211b2 theory-frequency layers.

Read-only. Does not rewrite the main deck. Does not import isolated/TARGET-FREQ.json.
Does not treat 0.06438 as a CCX frequency.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parent

MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
LOCK = ROOT / "eval" / "formfind_974211b2" / "lock_force.json"
FREQ = ROOT / "eval" / "formfind_974211b2" / "FREQ.json"
STACK = ROOT / "eval" / "overlay_974211b2" / "STACK.json"
ALIGN = ROOT / "eval" / "plan_974211b2" / "alignment.json"
META = ROOT / "mct-from-zero" / "artifacts" / "mct_from_zero_inp_meta.json"
DYN_DAT = ROOT / "eval" / "ccx_DYN_freq_974211b2" / "migrate_DYN.dat"

MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
MAIN_BYTES = 930300

# User-stated post-hoc pair. Not a solver input. Not read from isolated/TARGET-FREQ.json.
ATT_F1 = 0.0296
ATT_F2 = 0.0301
CCX_F1_LOCK = 0.1335403
FORBIDDEN_HALF = 0.06438

# Overlay / user lock for the formed main span.
L_MAIN_M = 2302.0
H_SAG_MAIN_M = 227.300

# MCT STRUCTYPE gravity is 9806 mm/s^2. Density conversion in emit_ccx uses this g.
G_MCT = 9.806
G_STD = 9.80665

# Drawing topology used only where the 2-D MCT line has no second deck / no width.
B_DECK_M = 42.90
R_F2 = 55.24 / 16.0  # 3.4525 m^2, 16 floor ropes about deck axis
R_G2 = ((2.00**2 + 2.26**2 + 2.52**2) * 2 + 6 * 8.00**2) / 6.0  # 69.152667 m^2
J_FRAME_PER_M = 41.0 * 46133.4364 / 2300.0  # v3 M1 smear, kg·m ; CCX MAT3 density ~0

# Main-span passage stations, metres from MCT 主跨 left (x=1528 m). Drawing chain.
PASSAGE_XI_MAIN_M = (
    178.0,
    349.0,
    520.0,
    691.0,
    844.0,
    997.0,
    1150.0,
    1303.0,
    1456.0,
    1609.0,
    1780.0,
    1951.0,
    2122.0,
)
M_PASS_CORE_KG = 5769.2
M_PASS_REPORT_KG = 10130.0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_err(model: float, ref: float) -> float:
    if ref == 0.0:
        return float("inf")
    return (model - ref) / ref


def taut_freq(n: int, length_m: float, tension_N: float, mu_kg_m: float) -> float:
    if length_m <= 0.0 or mu_kg_m <= 0.0 or tension_N <= 0.0 or n <= 0:
        raise ValueError("taut_freq needs positive n, L, T, μ")
    return n / (2.0 * length_m) * math.sqrt(tension_N / mu_kg_m)


def sag_freq(n: int, sag_m: float, g: float = G_MCT) -> float:
    if sag_m <= 0.0 or n <= 0:
        raise ValueError("sag_freq needs positive n, d")
    return n * math.sqrt(g / (32.0 * sag_m))


def wave_speed(tension_N: float, mu_kg_m: float) -> float:
    return math.sqrt(tension_N / mu_kg_m)


def sag_H_N(mu_kg_m: float, length_m: float, sag_m: float, g: float = G_MCT) -> float:
    return mu_kg_m * g * length_m * length_m / (8.0 * sag_m)


def irvine_Le_over_L(sag_m: float, length_m: float) -> float:
    return 1.0 + 8.0 * (sag_m / length_m) ** 2


def irvine_lambda2(sag_m: float, length_m: float, H_N: float, EA_N: float) -> float:
    if H_N <= 0.0 or EA_N <= 0.0:
        raise ValueError("Irvine λ² needs positive H, EA")
    ratio = sag_m / length_m
    return (8.0 * ratio) ** 2 * (EA_N / H_N) / irvine_Le_over_L(sag_m, length_m)


def _irvine_sym_residual(beta: float, lam2: float) -> float:
    return math.tan(beta) - beta * (1.0 - 4.0 * beta * beta / lam2)


def irvine_symmetric_Omegas(lam2: float, nroots: int = 4) -> list[float]:
    """Ω = ωL/c for in-plane symmetric Irvine modes. β = Ω/2."""
    roots: list[float] = []
    # Intervals (kπ, kπ + π/2) sit between tan poles at π/2 + kπ.
    k = 0
    while len(roots) < nroots and k < 24:
        left = k * math.pi + 1e-8
        right = k * math.pi + 0.5 * math.pi - 1e-8
        k += 1
        try:
            fl = _irvine_sym_residual(left, lam2)
            fr = _irvine_sym_residual(right, lam2)
        except ValueError:
            continue
        if fl == 0.0 and 2.0 * left >= 0.5:
            roots.append(2.0 * left)
            continue
        if fr == 0.0 and 2.0 * right >= 0.5:
            roots.append(2.0 * right)
            continue
        if fl * fr > 0.0:
            continue
        lo, hi = left, right
        flo = fl
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            fm = _irvine_sym_residual(mid, lam2)
            if flo * fm <= 0.0:
                hi = mid
            else:
                lo = mid
                flo = fm
        Omega = 2.0 * 0.5 * (lo + hi)
        # β=0 is always a trivial root of tan β = β(1−4β²/λ²). Drop it.
        if Omega < 0.5:
            continue
        roots.append(Omega)
    return roots


def irvine_inplane_freqs(
    length_m: float,
    sag_m: float,
    H_N: float,
    mu_kg_m: float,
    EA_N: float,
    n_sym: int = 3,
    n_antisym: int = 3,
) -> dict[str, Any]:
    c = wave_speed(H_N, mu_kg_m)
    ft = taut_freq(1, length_m, H_N, mu_kg_m)
    lam2 = irvine_lambda2(sag_m, length_m, H_N, EA_N)
    Omegas = irvine_symmetric_Omegas(lam2, nroots=n_sym)
    sym = []
    for i, Om in enumerate(Omegas, start=1):
        f = Om * c / (2.0 * math.pi * length_m)
        sym.append({"index": i, "Omega": Om, "f_Hz": f, "f_over_ftaut": f / ft})
    antisym = []
    for n in range(1, n_antisym + 1):
        f = taut_freq(2 * n, length_m, H_N, mu_kg_m)
        antisym.append({"index": n, "Omega": 2.0 * n * math.pi, "f_Hz": f, "f_over_ftaut": 2.0 * n})
    first_inplane = min(
        [row["f_Hz"] for row in sym + antisym],
        default=float("nan"),
    )
    return {
        "c_m_s": c,
        "f_taut_Hz": ft,
        "lambda2": lam2,
        "Le_over_L": irvine_Le_over_L(sag_m, length_m),
        "crossover_4pi2": 4.0 * math.pi**2,
        "lambda2_above_crossover": lam2 > 4.0 * math.pi**2,
        "symmetric": sym,
        "antisymmetric": antisym,
        "first_inplane_Hz": first_inplane,
        "formula_sym": "tan(Ω/2) = Ω/2 − 4/λ² (Ω/2)³,  Ω = ωL/√(H/μ)",
        "formula_antisym": "f = n/L √(H/μ) = 2n f_taut,  n = 1,2,…",
    }


def two_dof_freqs(T1: float, mu1: float, T2: float, mu2: float, k_eq: float, length_m: float, n: int) -> dict[str, float]:
    """In-phase / out-of-phase pair for harmonic n with connector stiffness k_eq (N/m)."""
    kn = (n * math.pi / length_m) ** 2
    K = [
        [T1 * kn + k_eq, -k_eq],
        [-k_eq, T2 * kn + k_eq],
    ]
    # Generalized: K a = ω² M a, M = diag(μ1, μ2)
    # Reduce to standard eig of M^{-1}K.
    a = K[0][0] / mu1
    b = K[0][1] / mu1
    c = K[1][0] / mu2
    d = K[1][1] / mu2
    tr = a + d
    det = a * d - b * c
    disc = max(tr * tr - 4.0 * det, 0.0)
    w2p = 0.5 * (tr + math.sqrt(disc))
    w2m = 0.5 * (tr - math.sqrt(disc))
    return {
        "f_low_Hz": math.sqrt(max(w2m, 0.0)) / (2.0 * math.pi),
        "f_high_Hz": math.sqrt(max(w2p, 0.0)) / (2.0 * math.pi),
        "k_eq_N_m": k_eq,
    }


def parse_main_materials(text: str) -> dict[str, dict[str, float]]:
    mats: dict[str, dict[str, float]] = {}
    name = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("*MATERIAL"):
            m = re.search(r"NAME=(\S+)", line)
            name = m.group(1) if m else None
            mats.setdefault(name or "?", {})
        elif name and line.startswith("*ELASTIC"):
            i += 1
            parts = [p.strip() for p in lines[i].split(",")]
            mats[name]["E_N_mm2"] = float(parts[0])
            mats[name]["nu"] = float(parts[1])
        elif name and line.startswith("*DENSITY"):
            i += 1
            mats[name]["rho_tonne_mm3"] = float(lines[i].strip())
        i += 1
    return mats


def parse_main_solid_areas(text: str) -> dict[str, float]:
    areas: dict[str, float] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("*SOLID SECTION"):
            m = re.search(r"ELSET=(\S+),", line)
            elset = m.group(1) if m else f"sec{i}"
            areas[elset] = float(lines[i + 1].split(",")[0].strip())
    return areas


def parse_dyn_participation(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    modes: dict[int, dict[str, Any]] = {}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if "E I G E N V A L U E" in line:
            section = "eig"
            continue
        if "P A R T I C I P A T I O N" in line:
            section = "pf"
            continue
        if "E F F E C T I V E   M O D A L   M A S S" in line:
            section = "emm"
            continue
        if "T O T A L   E F F E C T I V E   M A S S" in line:
            section = None
            continue
        if section is None or not line.strip():
            continue
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        mid = int(parts[0])
        modes.setdefault(mid, {"mode": mid})
        if section == "eig" and len(parts) >= 4:
            modes[mid]["eigenvalue"] = float(parts[1])
            modes[mid]["omega_rad"] = float(parts[2])
            modes[mid]["f_Hz"] = float(parts[3])
        elif section == "pf" and len(parts) >= 7:
            modes[mid]["pf_X"] = float(parts[1])
            modes[mid]["pf_Y"] = float(parts[2])
            modes[mid]["pf_Z"] = float(parts[3])
            modes[mid]["pf_RX"] = float(parts[4])
            modes[mid]["pf_RY"] = float(parts[5])
            modes[mid]["pf_RZ"] = float(parts[6])
        elif section == "emm" and len(parts) >= 7:
            modes[mid]["emm_X"] = float(parts[1])
            modes[mid]["emm_Y"] = float(parts[2])
            modes[mid]["emm_Z"] = float(parts[3])
            modes[mid]["emm_RX"] = float(parts[4])
            modes[mid]["emm_RY"] = float(parts[5])
            modes[mid]["emm_RZ"] = float(parts[6])
    return [modes[k] for k in sorted(modes)]


def load_locked_params() -> dict[str, Any]:
    main_sha = sha256_file(MAIN)
    cleared_sha = sha256_file(CLEARED)
    if main_sha != MAIN_SHA:
        raise RuntimeError(f"main deck hash moved: {main_sha}")
    if MAIN.stat().st_size != MAIN_BYTES:
        raise RuntimeError("main deck byte count moved")
    if cleared_sha != CLEARED_SHA:
        raise RuntimeError("760c0ee4 must stay untouched")

    lock = json.loads(LOCK.read_text())
    freq = json.loads(FREQ.read_text())
    stack = json.loads(STACK.read_text())
    align = json.loads(ALIGN.read_text())
    meta = json.loads(META.read_text())
    main_text = MAIN.read_text(encoding="utf-8")
    mats = parse_main_materials(main_text)
    areas = parse_main_solid_areas(main_text)

    rho1 = mats["MAT1"]["rho_tonne_mm3"]
    rho2 = mats["MAT2"]["rho_tonne_mm3"]
    A1 = areas["E_SEC1"]
    A2 = areas["E_SEC2"]
    # tonne/mm * 1e6 → kg/m
    mu_floor = rho1 * A1 * 1.0e6
    mu_portal = rho2 * A2 * 1.0e6
    E1 = mats["MAT1"]["E_N_mm2"]
    E2 = mats["MAT2"]["E_N_mm2"]
    EA_floor = E1 * A1
    EA_portal = E2 * A2

    by = lock["by_block_kN"]
    floor_by_name = {row["group"]: row for row in align["floor_spans"]}
    portal_by_name = {row["group"]: row for row in align["portal_cable_spans"]}

    ccx = list(freq["freq_cycles"])
    if abs(ccx[0] - CCX_F1_LOCK) > 1e-7:
        raise RuntimeError(f"FREQ.json f1 is {ccx[0]}, lock is {CCX_F1_LOCK}")
    if abs(ccx[0] - FORBIDDEN_HALF) < 1e-6:
        raise RuntimeError("refusing the discarded 0.06438 substitute")

    spans = []
    floor_names = ("北边跨", "主跨", "南边跨", "南辅跨")
    portal_names = ("门架索北边跨", "门架索主跨", "门架索南边跨", "门架索南辅跨")
    for fn, pn in zip(floor_names, portal_names):
        fs = floor_by_name[fn]
        ps = portal_by_name[pn]
        T_f = by[fn]["mean"] * 1.0e3
        T_p = by[pn]["mean"] * 1.0e3
        spans.append(
            {
                "floor": fn,
                "portal": pn,
                "L_floor_m": fs["L_m"],
                "L_portal_m": ps["L_m"],
                "z_left_m": fs["z_left_m"],
                "z_right_m": fs["z_right_m"],
                "z_min_m": fs["z_min_m"],
                "sag_end_minus_zmin_m": fs["sag_end_minus_zmin_m"],
                "T_floor_N": T_f,
                "T_portal_N": T_p,
                "T_sum_N": T_f + T_p,
                "inclined": abs(fs["z_left_m"] - fs["z_right_m"]) > 5.0,
            }
        )

    main_span = next(s for s in spans if s["floor"] == "主跨")
    H_sag_floor = sag_H_N(mu_floor, L_MAIN_M, H_SAG_MAIN_M, G_MCT)
    H_sag_portal = sag_H_N(mu_portal, L_MAIN_M, 229.01158565151704, G_MCT)

    dyn_modes = parse_dyn_participation(DYN_DAT) if DYN_DAT.is_file() else []

    return {
        "kind": "theory_freq_locked_params_974211b2",
        "imported_TARGET_FREQ": False,
        "used_0.06438_as_ccx": False,
        "not_table_5_4": True,
        "forbidden_table_5_4_kN": [9309.3, 581.8],
        "main": {
            "path": str(MAIN.relative_to(REPO)),
            "sha256": main_sha,
            "bytes": MAIN.stat().st_size,
            "rewritten": False,
        },
        "cleared_760c0ee4": {
            "path": str(CLEARED.relative_to(REPO)),
            "sha256": cleared_sha,
            "untouched": True,
        },
        "g_m_s2": G_MCT,
        "g_std": G_STD,
        "g_source": "MCT *STRUCTYPE 9806 mm/s2",
        "L_main_m": L_MAIN_M,
        "h_main_m_locked": H_SAG_MAIN_M,
        "h_main_m_overlay": floor_by_name["主跨"]["sag_end_minus_zmin_m"],
        "mu_floor_kg_m": mu_floor,
        "mu_portal_kg_m": mu_portal,
        "mu_sum_kg_m": mu_floor + mu_portal,
        "mu_frame_kg_m": mats["MAT3"]["rho_tonne_mm3"] * 9792.0 * 1.0e6,
        "A_floor_mm2": A1,
        "A_portal_mm2": A2,
        "E_floor_N_mm2": E1,
        "EA_floor_N": EA_floor,
        "EA_portal_N": EA_portal,
        "T_floor_main_N": main_span["T_floor_N"],
        "T_portal_main_N": main_span["T_portal_N"],
        "T_sum_main_N": main_span["T_sum_N"],
        "T_lock_global_mean_N": lock["mean_kN"] * 1.0e3,
        "H_sag_floor_main_N": H_sag_floor,
        "H_sag_portal_main_N": H_sag_portal,
        "T_floor_over_H_sag": main_span["T_floor_N"] / H_sag_floor,
        "materials_reread": mats,
        "lock_by_block_kN": by,
        "spans": spans,
        "ccx_freq_Hz": ccx,
        "ccx_f1_Hz": ccx[0],
        "att_pair_Hz": [ATT_F1, ATT_F2],
        "att_pair_note": "user-stated 附件2-3 first pair; post-hoc compare only",
        "B_deck_m": B_DECK_M,
        "r_f2_m2": R_F2,
        "r_g2_m2": R_G2,
        "J_frame_per_m": J_FRAME_PER_M,
        "passage_xi_main_m": list(PASSAGE_XI_MAIN_M),
        "m_pass_core_kg": M_PASS_CORE_KG,
        "m_pass_report_kg": M_PASS_REPORT_KG,
        "dyn_modes": dyn_modes,
        "y_plane": "MCT Y≈0 single-line 2-D equivalent; UY=0 on all nodes",
        "meta_source_sha256": meta.get("source_sha256"),
    }


def dumps(obj: Any) -> str:
    def default(o: Any) -> Any:
        if hasattr(o, "item"):
            return o.item()
        raise TypeError(type(o))

    return json.dumps(obj, indent=2, ensure_ascii=False, default=default) + "\n"


def write_json(path: Path, obj: Any) -> None:
    path.write_text(dumps(obj), encoding="utf-8")
