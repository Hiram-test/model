"""Parse ccx .frd modes, classify families, and pair Attachment 2-3 Table 4-1.

Classification observables follow the locked double-MCT convention:
common lateral (L), common vertical (V), between-width differential vertical
(system torsion observable T), per span; half-wave counts are fingerprints only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/workspace")
SOLVER = REPO / "catwalk-fem/agentic-fea/solver"
ART = REPO / "catwalk-fem/agentic-fea/artifacts"
W2 = 5000

sys.path.insert(0, str(REPO / "catwalk-fem/double-mct-buffeting/code"))
from double_mct_equivalent_passage_model import parse_mct  # noqa: E402

MCT = REPO / "catwalk-fem/double-mct-buffeting/inputs/catwalk_gantry_rope_combined_2.mct"

# Span windows in MCT x (metres), from the audited four-span line shape.
SPAN_WINDOWS = {
    "NORTH": (831.0, 1553.4),
    "MAIN": (1553.4, 3818.6),
    "SOUTH_AUX": (3818.6, 4380.0),
    "SOUTH": (4380.0, 5102.0),
}


def read_frd_coords(path: Path) -> dict[int, np.ndarray]:
    """Parse the expanded-mesh nodal coordinate block (2C)."""
    coords: dict[int, np.ndarray] = {}
    in2c = False
    with path.open() as fh:
        for line in fh:
            if line.startswith("    2C"):
                in2c = True
                continue
            if in2c:
                if line.startswith(" -1") and len(line) >= 48:
                    try:
                        nid = int(line[3:13])
                        coords[nid] = np.array(
                            [float(line[13:25]), float(line[25:37]), float(line[37:49])]
                        )
                    except ValueError:
                        continue
                elif line.startswith(" -3"):
                    break
    return coords


def read_frd_modes(path: Path) -> tuple[list[float], list[dict[int, np.ndarray]]]:
    """Return (frequencies_hz_per_block, list of {node: (ux,uy,uz)})."""
    freqs: list[float] = []
    blocks: list[dict[int, np.ndarray]] = []
    current: dict[int, np.ndarray] | None = None
    with path.open() as fh:
        for line in fh:
            if line.startswith("  100CL"):
                # header of a result block; frequency value in column 13-25
                current = {}
                blocks.append(current)
                try:
                    freqs.append(float(line[12:25]))
                except ValueError:
                    freqs.append(float("nan"))
            elif line.startswith(" -1") and current is not None and len(line) >= 48:
                try:
                    nid = int(line[3:13])
                    ux = float(line[13:25])
                    uy = float(line[25:37])
                    uz = float(line[37:49])
                except ValueError:
                    continue
                current[nid] = np.array([ux, uy, uz])
            elif line.startswith(" -3"):
                current = None
    return freqs, blocks


def main() -> None:
    parsed = parse_mct(MCT)
    nodes = parsed["nodes"]
    elements = parsed["elements"]
    masses_kg = parsed["concentrated_mass_kg"]

    carry_nodes = sorted(
        {int(e["n1"]) for e in elements.values() if int(e["material"]) == 1}
        | {int(e["n2"]) for e in elements.values() if int(e["material"]) == 1}
    )
    gantry_nodes = sorted(
        {int(e["n1"]) for e in elements.values() if int(e["material"]) == 2}
        | {int(e["n2"]) for e in elements.values() if int(e["material"]) == 2}
    )
    # nodal translational mass (tonne): cable tributary + ballast share (approximate, for weighting)
    node_mass = {n: masses_kg.get(n, 0.0) / 1000.0 for n in set(carry_nodes) | set(gantry_nodes)}
    for eid, el in elements.items():
        mat = int(el["material"])
        if mat == 3:
            continue
        p1 = nodes[int(el["n1"])]
        p2 = nodes[int(el["n2"])]
        length_mm = float(np.linalg.norm(p2 - p1)) * 1000.0
        rho_a = {1: 1.26484805e-08 * 22298.692, 2: 8.59881705e-09 * 8402.9797}[mat]
        half = rho_a * length_mm / 2.0
        for n in (int(el["n1"]), int(el["n2"])):
            node_mass[n] = node_mass.get(n, 0.0) + half

    freqs, blocks = read_frd_modes(SOLVER / "double_mct_ccx.frd")
    eig = json.loads((SOLVER / "eigenfrequencies_hz.json").read_text())
    # first block is the static step; modal blocks follow
    modal_blocks = blocks[-len(eig):]

    # Map expanded-mesh nodes back to original nodes: bucket every frd node to the
    # nearest original node (both widths, both chains) within the section radius,
    # then average each bucket's modal displacement.  ccx zeroes retained nodes at
    # expanded knots, so eigenvectors live on the expanded section nodes only.
    from scipy.spatial import cKDTree

    orig_ids: list[int] = []
    orig_xyz: list[np.ndarray] = []
    for n in carry_nodes + gantry_nodes:
        base = nodes[n] * 1000.0
        orig_ids.append(n)
        orig_xyz.append(np.array([base[0], +21450.0, base[2]]))
        orig_ids.append(n + W2)
        orig_xyz.append(np.array([base[0], -21450.0, base[2]]))
    tree = cKDTree(np.vstack(orig_xyz))
    coords = read_frd_coords(SOLVER / "double_mct_ccx.frd")
    frd_ids = np.array(sorted(coords))
    frd_xyz = np.vstack([coords[i] for i in frd_ids])
    dist, idx = tree.query(frd_xyz, k=1)
    keep = dist <= 400.0
    bucket_of = {int(f): int(i) for f, i, k in zip(frd_ids, idx, keep) if k}

    def collapse(blk: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
        sums: dict[int, np.ndarray] = {}
        counts: dict[int, int] = {}
        for f, b in bucket_of.items():
            v = blk.get(f)
            if v is None:
                continue
            oid = orig_ids[b]
            if oid in sums:
                sums[oid] += v
                counts[oid] += 1
            else:
                sums[oid] = v.copy()
                counts[oid] = 1
        return {k: sums[k] / counts[k] for k in sums}

    modal_blocks = [collapse(b) for b in modal_blocks]

    x_carry = np.array([nodes[n][0] for n in carry_nodes])
    records = []
    shapes_obs = []
    for k, (f_hz, blk) in enumerate(zip(eig, modal_blocks), start=1):
        span_energy = {s: 0.0 for s in SPAN_WINDOWS}
        fam_energy = {"L": 0.0, "V": 0.0, "T": 0.0}
        obs_L, obs_V, obs_T = [], [], []
        for n in carry_nodes + gantry_nodes:
            u1 = blk.get(n)
            u2 = blk.get(n + W2)
            if u1 is None or u2 is None:
                continue
            m = node_mass.get(n, 0.0)
            x = nodes[n][0]
            common = 0.5 * (u1 + u2)
            diff = 0.5 * (u1 - u2)
            eL = m * common[1] ** 2
            eV = m * common[2] ** 2
            eT = m * diff[2] ** 2
            eRest = m * (diff[0] ** 2 + diff[1] ** 2 + common[0] ** 2)
            tot = eL + eV + eT + eRest
            for s, (x0, x1) in SPAN_WINDOWS.items():
                if x0 <= x < x1:
                    span_energy[s] += tot
                    break
            fam_energy["L"] += eL
            fam_energy["V"] += eV
            fam_energy["T"] += eT
            if n in carry_nodes:
                obs_L.append((x, common[1], m))
                obs_V.append((x, common[2], m))
                obs_T.append((x, diff[2], m))
        tot_span = sum(span_energy.values()) or 1.0
        dom_span = max(span_energy, key=span_energy.get)
        fam_tot = sum(fam_energy.values()) or 1.0
        fam = max(fam_energy, key=fam_energy.get)
        # half-wave + parity on main-span carry common observable of the dominant family
        obs = {"L": obs_L, "V": obs_V, "T": obs_T}[fam]
        xs = np.array([o[0] for o in obs])
        vs = np.array([o[1] for o in obs])
        ws = np.array([o[2] for o in obs])
        sel = (xs >= SPAN_WINDOWS["MAIN"][0]) & (xs < SPAN_WINDOWS["MAIN"][1])
        xm, vm, wm = xs[sel], vs[sel], ws[sel]
        order = np.argsort(xm)
        xm, vm, wm = xm[order], vm[order], wm[order]
        half_wave, parity, mac = 0, "?", 0.0
        if len(xm) > 8 and np.max(np.abs(vm)) > 0:
            L0, L1 = xm[0], xm[-1]
            xi = (xm - L0) / (L1 - L0)
            best = (0.0, 0, "?")
            for nhw in range(1, 9):
                tpl = np.sin(np.pi * nhw * xi)
                num = float(np.sum(wm * vm * tpl)) ** 2
                den = float(np.sum(wm * vm * vm)) * float(np.sum(wm * tpl * tpl))
                m2 = num / den if den > 0 else 0.0
                if m2 > best[0]:
                    best = (m2, nhw, "S" if nhw % 2 == 1 else "A")
            mac, half_wave, parity = best
        records.append(
            {
                "mode": k,
                "frequency_hz": f_hz,
                "dominant_span": dom_span,
                "main_span_fraction": span_energy["MAIN"] / tot_span,
                "family": fam,
                "family_fraction": fam_energy[fam] / fam_tot,
                "L_frac": fam_energy["L"] / fam_tot,
                "V_frac": fam_energy["V"] / fam_tot,
                "T_frac": fam_energy["T"] / fam_tot,
                "half_wave": half_wave,
                "parity": parity,
                "template_mac2": mac,
            }
        )
        if k <= 24:
            shapes_obs.append({"mode": k, "obs": {"L": obs_L, "V": obs_V, "T": obs_T}})

    df = pd.DataFrame(records)
    df.to_csv(ART / "ccx_mode_classification.csv", index=False)
    with pd.option_context("display.width", 200):
        print(df.head(24).to_string(index=False))
    np.save(ART / "ccx_mode_observables_first24.npy", np.array(shapes_obs, dtype=object), allow_pickle=True)


if __name__ == "__main__":
    main()
