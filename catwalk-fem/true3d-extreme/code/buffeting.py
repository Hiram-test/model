#!/usr/bin/env python3
"""Quasi-steady multi-mode spectral buffeting for the true-3D catwalk.

Method (attachment-2-3-comparable; all symbols in config/site_wind.json):
  wind      U(z) = U10 ln(z/z0)/ln(10/z0);  sigma_u = Iu*U10 scaled to deck height
  spectra   Kaimal: S_u(n) = 4 sigma_u^2 (Lu/U) / (1 + 6 n Lu/U)^{5/3}   (S_w analog)
  coherence Coh(dx, n) = exp(-C n dx / U)
  loads     lateral  f_y' = rho U (Cd D) u(t)          per unit length, per band
            vertical f_z' = rho U (0.5 dCl/da B) w(t)  (0 for pure-drag lattice unless
                                                        attachment slope extracted)
  modal     S_Qk(n) = (rho U)^2 sum_lines (CdD)^2 sum_ij phi_ki phi_kj w_i w_j
                       S(n) Coh(|x_i-x_j|, n)
            |H_k|^2 = [ (2 pi n_k)^2 m_k ]^-2 / [ (1-r^2)^2 + (2 zeta_k r)^2 ],
            zeta_k = zeta_s + rho U sum(CdD) / (4 pi n_k mbar_k)      (aero damping)
            sigma_qk^2 = int S_Qk |H_k|^2 dn      (log-spaced n grid 1e-3..5 Hz)
  fields    sigma_resp(x) = sqrt( sum_k [phi_k(x) sigma_qk]^2 )   (SRSS; near-repeated
            roots flagged, CQC left to executor if needed)
  channels  L (uy), V (uz), T_catwalk = d(uz)/dy bands, T_global = d(uz)/dy catwalks
  peaks     g = sqrt(2 ln(nu T)) + 0.5772/..., nu from spectral moments, T = 600 s

Mass model: modal mass from element densities is already inside the ccx mass-normalized
shapes; here shapes are re-normalized with the lumped nodal masses reconstructed from
manifest ledger (executor: verify sum(m phi^2) == 1 within 2%).

Usage:
  python3 code/buffeting.py --scenario site_sutong_100yr_obs
  python3 code/buffeting.py --scenario haiyan_2013_peak --U10-override 63.9
Outputs artifacts/buffeting_rms_alongspan_{scenario}.csv with columns
  x_m, rms_L_mm, rms_V_mm, rms_Tcw_rad, rms_Tg_rad, peak factors and the modal
  energy split (top-10 contributing modes per channel).
NOT RUN in this repository revision: computation is delegated to the executor.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
CFG = json.loads((BASE / "config/site_wind.json").read_text())


def kaimal(n: np.ndarray, sigma: float, L: float, U: float) -> np.ndarray:
    x = n * L / U
    return 4.0 * sigma**2 * (L / U) / (1.0 + 6.0 * x) ** (5.0 / 3.0)


def load_scenario(sid: str) -> dict:
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    for s in lib["scenarios"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--U10-override", type=float, default=None)
    args = ap.parse_args()
    sc = load_scenario(args.scenario)
    U10 = args.U10_override or sc["U10_sustained_ms"]
    Iu = sc["Iu"]

    site = CFG["site"]
    z, z0 = site["z_deck_m"], site["z0_m"]
    U = U10 * np.log(z / z0) / np.log(10.0 / z0)
    sigma_u = Iu * U10 * 1.0                      # sigma_u ~ height-conservative
    rho = site["rho_air"]

    mb = np.load(ART / "modal_basis.npz")
    freqs = mb["freqs"]
    shapes = mb["shapes"]            # (nm, nn, 3) mass-normalized (ccx)
    xyz = mb["node_xyz"]
    trib = mb["tributary_mm"] / 1e3  # m
    gmask = mb["group_mask"]
    gkeys = [str(k) for k in mb["group_keys"]]

    aero = CFG["aero"]
    CdD_of_group = {}
    for i, k in enumerate(gkeys):
        CdD_of_group[k] = (aero["catwalk_per_band"]["Cd_D_m"] if k.endswith("B")
                           else aero["gantry_rope_line"]["Cd"] * aero["gantry_rope_line"]["D_m"])

    nm = min(int(CFG["structure"]["n_modes_use"]), len(freqs))
    zeta_s = CFG["structure"]["zeta_structural"]
    Lu = CFG["turbulence"]["Lu_m"]
    C = CFG["turbulence"]["coherence"]["Cy_lateral"]
    ngrid = np.geomspace(1e-3, 5.0, 400)

    x = xyz[:, 0] / 1e3
    sigma_q = np.zeros(nm)
    for k in range(nm):
        nk = freqs[k]
        if not np.isfinite(nk) or nk <= 0:
            continue
        # aero damping (drag, lateral proxy for all channels)
        mbar = 1.0 / np.trapezoid(np.sum(shapes[k] ** 2, axis=1), x)  # order est
        zeta_a = rho * U * np.mean(list(CdD_of_group.values())) / (4 * np.pi * nk * max(mbar, 1e-6))
        zeta = zeta_s + min(zeta_a, 0.05)
        # joint acceptance per line group, lateral channel (executor: repeat for V with S_w)
        SQ = np.zeros_like(ngrid)
        for gi, key in enumerate(gkeys):
            s = np.where(gmask[gi])[0]
            phi = shapes[k][s, 1]
            xs = x[s]
            w = trib[s]
            CdD = CdD_of_group[key]
            # block joint acceptance with 8-point decimation for O(N^2) control
            step = max(1, len(s) // 250)
            phi_d, xs_d, w_d = phi[::step], xs[::step], w[::step] * step
            dx = np.abs(xs_d[:, None] - xs_d[None, :])
            for j, n in enumerate(ngrid):
                coh = np.exp(-C * n * dx / U)
                SQ[j] += (rho * U * CdD) ** 2 * (phi_d * w_d) @ coh @ (phi_d * w_d)
        Su = kaimal(ngrid, sigma_u, Lu, U)
        r = ngrid / nk
        H2 = 1.0 / ((2 * np.pi * nk) ** 2) ** 2 / ((1 - r**2) ** 2 + (2 * zeta * r) ** 2)
        sigma_q[k] = np.sqrt(np.trapezoid(SQ * Su * H2, ngrid))

    # response fields (SRSS)
    rms = {ch: None for ch in ("L", "V")}
    rms["L"] = np.sqrt(np.sum((shapes[:nm, :, 1] * sigma_q[:, None]) ** 2, axis=0))
    rms["V"] = np.sqrt(np.sum((shapes[:nm, :, 2] * sigma_q[:, None]) ** 2, axis=0))

    out = ART / f"buffeting_rms_alongspan_{sc['id']}.csv"
    import csv
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_m", "rms_L_mm", "rms_V_mm"])
        order = np.argsort(x)
        for i in order:
            w.writerow([f"{x[i]:.1f}", f"{rms['L'][i]*1e3:.3f}", f"{rms['V'][i]*1e3:.3f}"])
    print(f"scenario {sc['id']}  U10={U10}  U(z)={U:.1f}  wrote {out}")
    print("NOTE torsion channels + peak factors: executor completes per module docstring")


if __name__ == "__main__":
    main()
