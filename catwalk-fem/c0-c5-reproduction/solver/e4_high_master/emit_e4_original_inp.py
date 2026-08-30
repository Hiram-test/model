#!/usr/bin/env python3
"""Stdlib writer for a target-conditioned high-master toy CalculiX deck."""
from __future__ import annotations
import json
import math
from pathlib import Path

# Heights and dM are copied from Track A forensic_fit.json, not drawing geometry.
STATUS = "TARGET_CONDITIONED_INVERSE_HEIGHTS"
FREQUENCY_REPRODUCED = False
BACK_TUNED = True
TRACK_B_BLIND_E4 = False
NOTE = (
    "H_SHARED=5.607 m, H_TA1_TOTAL=9.069 m and dM=13*10.1346 t come from the "
    "invalidated Track A inverse fit. This is not Track B blind E4, not C3-UB-FT14, "
    "not true3d, and not attach TA1 reproduction."
)

G = 9.80665
SUPPORTS = [0.0, 660.0, 2960.0, 3677.0, 4180.0]
MAIN_L = 2300.0
SAG = 227.3
B = 42.9
TOTAL_MASS = 4108.46690758 * 1000.0
MU = 0.5 * TOTAL_MASS / SUPPORTS[-1]
H_TENSION = MU * G * MAIN_L**2 / (8.0 * SAG)
PASSAGE_T = 10.134611462369978
H_SHARED = 5.607480846148725
H_TA1_TOTAL = H_SHARED + 3.4610524428520746
XI = (
    0.07739130434782608, 0.1517391304347826, 0.22608695652173913,
    0.30043478260869565, 0.36609099999999994, 0.4343515217391304,
    0.5, 0.5656558695652174, 0.6339170869565218, 0.6995652173913044,
    0.7739130434782608, 0.8482608695652174, 0.9226086956521739,
)
TOWER_X = [666.679, 2953.321]


def sag(x: float) -> float:
    if SUPPORTS[1] <= x <= SUPPORTS[2]:
        xi = (x - SUPPORTS[1]) / MAIN_L
        return 4.0 * SAG * xi * (1.0 - xi)
    for i in range(4):
        if SUPPORTS[i] <= x <= SUPPORTS[i + 1] + 1e-12:
            li = SUPPORTS[i + 1] - SUPPORTS[i]
            hi = MU * G * li * li / (8.0 * H_TENSION)
            xi = (x - SUPPORTS[i]) / li if li else 0.0
            return 4.0 * hi * xi * (1.0 - xi)
    return 0.0


def linspace(a, b, n):
    if n == 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def unique_merge(vals, tol=0.05):
    vals = sorted(vals)
    out = [vals[0]]
    for x in vals[1:]:
        if abs(x - out[-1]) >= tol:
            out.append(x)
    return out


def nearest(xs, xp):
    return min(range(len(xs)), key=lambda i: abs(xs[i] - xp))


def axis():
    nseg = (20, 80, 24, 16)
    xs = []
    for i, ns in enumerate(nseg):
        grid = linspace(SUPPORTS[i], SUPPORTS[i + 1], ns + 1)
        xs.extend(grid if i == 0 else grid[1:])
    pass_x = [SUPPORTS[1] + MAIN_L * xi for xi in XI]
    xs = unique_merge(xs + pass_x + TOWER_X + SUPPORTS)
    return xs, pass_x


def write_inp(path: Path) -> None:
    xs, pass_x = axis()
    n = len(xs)
    lines = [
        "*HEADING",
        "TARGET-CONDITIONED inverse-fit high-master toy deck; frequency_reproduced=false",
        "13 main-span pilots h=5.607 m and tower pilots h=9.069 m from Track A, not drawings",
        "Not Track B blind E4; not C3-UB-FT14; not true3d; not attach TA1 reproduction",
        "NLGEOM gravity then FREQUENCY; dM=13*10.1346 t inverse-fit bookkeeping",
        "*NODE",
    ]
    for i, x in enumerate(xs, start=1):
        z = -1000.0 * sag(x)
        lines.append(f"{i}, {1000*x:.6f}, {-500.0*B:.6f}, {z:.6f}")
        lines.append(f"{100000+i}, {1000*x:.6f}, {500.0*B:.6f}, {z:.6f}")
    mid = 300000
    stations = [(x, H_SHARED) for x in pass_x] + [(x, H_TA1_TOTAL) for x in TOWER_X]
    master_ids = []
    for kst, (xp, h) in enumerate(stations):
        i = nearest(xs, xp) + 1
        z = -1000.0 * sag(xs[i - 1])
        ml, mr = mid + 2 * kst + 1, mid + 2 * kst + 2
        lines.append(f"{ml}, {1000*xs[i-1]:.6f}, {-500.0*B:.6f}, {z + 1000*h:.6f}")
        lines.append(f"{mr}, {1000*xs[i-1]:.6f}, {500.0*B:.6f}, {z + 1000*h:.6f}")
        master_ids.append((ml, mr, i, h))
    lines.append("*ELEMENT, TYPE=T3D2, ELSET=E_LEFT")
    lines.extend(f"{i}, {i}, {i+1}" for i in range(1, n))
    lines.append("*ELEMENT, TYPE=T3D2, ELSET=E_RIGHT")
    lines.extend(f"{200000+i}, {100000+i}, {100000+i+1}" for i in range(1, n))
    lines.append("*ELEMENT, TYPE=T3D2, ELSET=E_HIGHPASS")
    eid = 500000
    for ml, mr, i, h in master_ids:
        eid += 1
        lines.append(f"{eid}, {ml}, {mr}")
    lines.append("** translation-only CERIG equivalent: UX,UY,UZ slave, ROTX free/absent")
    for ml, mr, i, h in master_ids:
        for dof in (1, 2, 3):
            lines += ["*EQUATION", "2", f"{i}, {dof}, 1.0, {ml}, {dof}, -1.0"]
            lines += ["*EQUATION", "2", f"{100000+i}, {dof}, 1.0, {mr}, {dof}, -1.0"]
    lines.append("*ELEMENT, TYPE=MASS, ELSET=E_MASS21DUP")
    eid = 600000
    for xp in pass_x:
        i = nearest(xs, xp) + 1
        eid += 1
        lines.append(f"{eid}, {i}")
        eid += 1
        lines.append(f"{eid}, {100000+i}")
    area = 20000.0
    dens = MU / (area * 1e-6) / 1000.0
    pret = H_TENSION / area
    half = PASSAGE_T * 1000.0 / 2.0
    lines += [
        "*MATERIAL, NAME=MROPE", "*ELASTIC", "200000.0, 0.3", "*DENSITY", f"{dens:.12e}",
        "*MATERIAL, NAME=MHIGH", "*ELASTIC", "200000.0, 0.3", "*DENSITY", "0.0",
        "*SOLID SECTION, ELSET=E_LEFT, MATERIAL=MROPE", f"{area:.6f}",
        "*SOLID SECTION, ELSET=E_RIGHT, MATERIAL=MROPE", f"{area:.6f}",
        "*SOLID SECTION, ELSET=E_HIGHPASS, MATERIAL=MHIGH", "20000.0",
        "*MASS, ELSET=E_MASS21DUP", f"{half:.9f}",
        "*NSET, NSET=NSUP",
    ]
    sup = []
    for xs_s in SUPPORTS:
        i = nearest(xs, xs_s) + 1
        sup.extend([str(i), str(100000 + i)])
    lines.append(",".join(sup))
    lines += [
        "*BOUNDARY", "NSUP, 1, 3",
        "*INITIAL CONDITIONS, TYPE=STRESS",
        f"E_LEFT, {pret:.8f}",
        f"E_RIGHT, {pret:.8f}",
        "*STEP, NLGEOM",
        "*STATIC",
        "*DLOAD",
        "E_LEFT, GRAV, 9810.0, 0.0, 0.0, -1.0",
        "E_RIGHT, GRAV, 9810.0, 0.0, 0.0, -1.0",
        "*END STEP",
        "*STEP, PERTURBATION",
        "*FREQUENCY",
        "40",
        "*NODE FILE",
        "U",
        "*END STEP",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    receipt = {
        "status": STATUS,
        "frequency_reproduced": FREQUENCY_REPRODUCED,
        "back_tuned": BACK_TUNED,
        "track_b_blind_e4": TRACK_B_BLIND_E4,
        "note": NOTE,
        "h_shared_m": H_SHARED,
        "h_ta1_total_m": H_TA1_TOTAL,
        "passage_t": PASSAGE_T,
        "total_mass_t": TOTAL_MASS / 1000.0,
        "deck": str(path),
    }
    receipt_path = path.with_name(path.stem + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    out = Path("E4_original_high_master.ccx.inp")
    write_inp(out)
    print(out.resolve(), out.stat().st_size, "frequency_reproduced=false")
