"""Independent verification of double_mct_frequency.inp: rebuild the same K and lumped M
from the source CSVs with scipy and compare eigenfrequencies against the ccx .dat output.

Writes mode_comparison.csv with:
- ccx vs scipy (same model, translation check; should agree to ~1e-4 relative), and
- nearest-frequency pairing of the reference 80-mode table (full 12x12 four-port model)
  against the ccx spectrum, for the first 20 reference modes.
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import eigsh

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MODES = 60


def blocks(lines: list[str], name: str) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] | None = None
    for raw in lines:
        s = raw.strip()
        if s.startswith("*"):
            cur = [] if s.split()[0].upper() == name else None
            if cur is not None:
                out.append(cur)
            continue
        if cur is not None and s and not s.startswith(";"):
            cur.append(s)
    return out


def expand(spec: str) -> list[int]:
    res: list[int] = []
    for t in spec.replace("\\", " ").split():
        m = re.fullmatch(r"(-?\d+)to(-?\d+)(?:by(-?\d+))?", t, re.I)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            st = int(m.group(3) or (1 if b >= a else -1))
            res.extend(range(a, b + (1 if st > 0 else -1), st))
        elif re.fullmatch(r"-?\d+", t):
            res.append(int(t))
    return res


def main() -> None:
    nodes: dict[int, tuple[float, float, float, str, int]] = {}
    with (PKG / "structural_results" / "double_mct_nodes.csv").open() as fh:
        for r in csv.DictReader(fh):
            nodes[int(r["global_index"])] = (float(r["x_m"]), float(r["y_m"]), float(r["z_m"]), r["width"], int(r["mct_node"]))
    n = len(nodes)
    xyz = np.array([[nodes[i][0], nodes[i][1], nodes[i][2]] for i in range(n)])
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []

    def add_pair(i: int, j: int, m3: np.ndarray) -> None:
        di = np.arange(3 * i, 3 * i + 3)
        dj = np.arange(3 * j, 3 * j + 3)
        for a in range(3):
            for b in range(3):
                v = float(m3[a, b])
                rows.extend([di[a], di[a], dj[a], dj[a]])
                cols.extend([di[b], dj[b], di[b], dj[b]])
                vals.extend([v, -v, -v, v])

    gr = 9.806
    a1 = math.pi * 0.168498**2 / 4
    a2 = math.pi * 0.103436**2 / 4
    rho1 = 1.24031e-7 * 1e9 * 1000 / gr
    rho2 = 8.432e-8 * 1e9 * 1000 / gr
    mass = np.zeros(n)
    with (PKG / "structural_results" / "double_mct_source_elements.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "TRUSS_REPLACED_BY_FOUR_PORT":
                continue
            i, j = int(r["n1_global"]), int(r["n2_global"])
            length = float(r["length_m"])
            ea = float(r["equivalent_ea_n"])
            d = (xyz[j] - xyz[i]) / length
            proj = np.outer(d, d)
            if r["kind"] == "TENSTR":
                nf = float(r["initial_force_kn"]) * 1000
                add_pair(i, j, ea / length * proj + nf / length * np.eye(3))
                area, rho = (a1, rho1) if abs(ea - 120e9 * a1) < abs(ea - 120e9 * a2) else (a2, rho2)
                half = 0.5 * rho * area * length
                mass[i] += half
                mass[j] += half
            else:
                add_pair(i, j, ea / length * proj)
    k12: dict[tuple[str, str], float] = {}
    with (PKG / "inputs" / "gate_passage" / "K12_translation_ports_SI.csv").open() as fh:
        rr = list(csv.reader(fh))
        lab = rr[0][1:]
        for a in range(12):
            for b in range(12):
                k12[(rr[a + 1][0], lab[b])] = float(rr[a + 1][b + 1])
    kbt = abs(k12[("B_L_UZ", "T_L_UZ")])
    kbb = abs(k12[("B_L_UY", "B_R_UY")])
    with (PKG / "structural_results" / "cross_passage_equivalent_links.csv").open() as fh:
        for r in csv.DictReader(fh):
            bl, tl, br, tr = (int(r[c]) for c in ("cw1_bottom_global", "cw1_gantry_global", "cw2_bottom_global", "cw2_gantry_global"))
            for (i, j, kk) in ((bl, tl, kbt), (br, tr, kbt), (bl, br, kbb)):
                d = xyz[j] - xyz[i]
                length = float(np.linalg.norm(d))
                d = d / length
                add_pair(i, j, kk * np.outer(d, d))
    ml = (PKG / "inputs" / "catwalk_gantry_rope_combined_2.mct").read_text(encoding="utf-8", errors="replace").splitlines()
    bymw = {(nodes[i][3], nodes[i][4]): i for i in range(n)}
    for line in blocks(ml, "*CONLOAD")[0]:
        f = [x.strip() for x in line.split(",")]
        fz = float(f[3])
        for mid in expand(f[0]):
            for w in "LR":
                mass[bymw[(w, mid)]] += max(0.0, -fz) * 1000 / gr
    fixed: set[int] = set()
    for line in blocks(ml, "*CONSTRAINT")[0]:
        f = [x.strip() for x in line.split(",")]
        for mid in expand(f[0]):
            for w in "LR":
                g = bymw[(w, mid)]
                for c in range(3):
                    if c < len(f[1]) and f[1][c] == "1":
                        fixed.add(3 * g + c)
    stiff = coo_matrix((vals, (rows, cols)), shape=(3 * n, 3 * n)).tocsr()
    free = np.array([d for d in range(3 * n) if d not in fixed])
    dof_mass = np.repeat(mass, 3)
    ev, _ = eigsh(stiff[free][:, free], k=MODES, M=diags(dof_mass[free]), sigma=0.0, which="LM", tol=1e-10, maxiter=20000)
    scipy_hz = np.sqrt(np.maximum(np.sort(ev), 0)) / (2 * math.pi)

    ccx_hz: list[float] = []
    for l in (HERE / "double_mct_frequency.dat").open():
        m = re.match(r"\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", l)
        if m and len(ccx_hz) < MODES:
            try:
                ccx_hz.append(float(m.group(4)))
            except ValueError:
                pass
    ref = list(csv.DictReader((PKG / "structural_results" / "modal_properties.csv").open()))

    with (HERE / "mode_comparison.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["section", "mode", "ccx_hz", "scipy_same_model_hz", "translation_diff_pct", "note"])
        worst = 0.0
        for i in range(min(MODES, len(ccx_hz))):
            d = 100 * (ccx_hz[i] - scipy_hz[i]) / scipy_hz[i]
            worst = max(worst, abs(d))
            w.writerow(["ccx_vs_scipy", i + 1, f"{ccx_hz[i]:.6f}", f"{scipy_hz[i]:.6f}", f"{d:.4f}", ""])
        w.writerow([])
        w.writerow(["section", "ref_mode", "ref_label", "ref_hz", "nearest_ccx_hz", "diff_pct"])
        for i in range(20):
            fr = float(ref[i]["frequency_hz"])
            nearest = min(ccx_hz, key=lambda v: abs(v - fr))
            w.writerow(["ref_nearest_match", i + 1, ref[i]["label"], f"{fr:.6f}", f"{nearest:.6f}", f"{100 * (nearest - fr) / fr:.2f}"])
        print(f"worst ccx-vs-scipy translation diff over {min(MODES, len(ccx_hz))} modes: {worst:.4f}%")


if __name__ == "__main__":
    main()
