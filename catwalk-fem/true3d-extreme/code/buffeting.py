#!/usr/bin/env python3
"""Quasi-steady multi-mode spectral buffeting engine (complete, four channels).

Physics (units t / mm / s / N throughout; rho_air = 1.225e-12 t/mm^3):
  profile    U(z) = U10 ln(z/z0)/ln(10/z0)
  spectra    Kaimal  S_a(n) = 4 sigma_a^2 (L_a/U) / (1+6 n L_a/U)^{5/3},  a in {u,w}
  coherence  Davenport  Coh(s,n) = exp(-C n s / U),  s = sqrt(dx^2+dy^2+dz^2)
  loads/len  lateral (u):  f_y' = rho U (CdD)_u u(t)
             vertical (w): f_z' = rho U * 0.5 (Cl' B + CdD)_w w(t)
  modal      S_Qk(n) = (rho U)^2 [ Su(n) * v_y^T E(n) v_y * cu^2  +
                                   Sw(n) * v_z^T E(n) v_z * cw^2 ]   (u-w cross neglected)
             with v_y,i = phi_y,i w_i (CdD_u,i/CdD_ref), E_ij(n)=Coh(s_ij,n)
  transfer   |H_k(n)|^2 = [(2 pi n_k)^2 m_k]^-2 / [(1-r^2)^2+(2 zeta_k r)^2],  m_k = 1 t
  damping    zeta_k = zeta_s + c_k/(4 pi n_k),  c_k = rho U sum_i [Cu_i phi_y_i^2
                                                     + Cw_i phi_z_i^2] w_i
  response   sigma_ch(x) = sqrt( sum_k (phi_ch,k(x) sigma_qk)^2 )   (SRSS)
  channels   L = uy, V = uz, Tcw = [uz(OB)-uz(IB)]/dy_band per catwalk (worst),
             Tg = [uz(P)-uz(M)]/dy_global
  peaks      g_ch = sqrt(2 ln(nu T)) + 0.5772/sqrt(2 ln(nu T)),
             nu = energy-weighted modal frequency of the channel

Inputs : artifacts/modal_basis.npz (or --basis override), config/site_wind.json,
         artifacts/extreme_weather_library.json
Outputs: artifacts/buffeting_rms_alongspan_{id}{tag}.csv
         artifacts/buffeting_summary_{id}{tag}.json
API    : run_scenario(scenario_dict, basis_dict, cfg, tag="") -> summary dict
CLI    : python3 code/buffeting.py --scenario site_sutong_100yr_obs [--basis F] [--tag T]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
RHO = 1.225e-12          # t/mm^3
MM = 1e3                 # m -> mm

N_GRID = np.geomspace(5e-4, 5.0, 140)


def kaimal(n, sigma, L_mm, U_mm):
    x = n * L_mm / U_mm
    return 4.0 * sigma**2 * (L_mm / U_mm) / (1.0 + 6.0 * x) ** (5.0 / 3.0)


def load_basis(path: Path) -> dict:
    d = np.load(path, allow_pickle=True)
    gk = [str(k) for k in d["group_keys"]]
    ids = d["node_ids"]
    mb = {
        "freqs": d["freqs"], "shapes": d["shapes"], "ids": ids,
        "xyz": d["node_xyz"], "trib": d["tributary_mm"], "gk": gk,
        "gmask": d["group_mask"], "y_eq": d["y_eq"],
    }
    # station index k inside each group: node id = 100000*(g+1)+k (builder contract)
    mb["k_of_node"] = ids % 100000
    return mb


def channel_operators(mb: dict):
    """Aligned station sets for torsion channels; returns dict of index arrays."""
    gk = mb["gk"]
    gi = {k: i for i, k in enumerate(gk)}
    kmap = {}
    for key in gk:
        sel = np.where(mb["gmask"][gi[key]])[0]
        kmap[key] = {int(k): j for k, j in zip(mb["k_of_node"][sel], sel)}
    ops = {"cw": {}, "gl": None}
    for cw in ("P", "M"):
        ib, ob = kmap.get(f"{cw}IB", {}), kmap.get(f"{cw}OB", {})
        ks = sorted(set(ib) & set(ob))
        dy = abs(mb["y_eq"][gi[f"{cw}OB"]] - mb["y_eq"][gi[f"{cw}IB"]])
        ops["cw"][cw] = {"k": ks, "i_in": np.array([ib[k] for k in ks]),
                         "i_out": np.array([ob[k] for k in ks]), "dy": dy}
    pi, po = kmap.get("PIB", {}), kmap.get("POB", {})
    mi, mo = kmap.get("MIB", {}), kmap.get("MOB", {})
    ks = sorted(set(pi) & set(po) & set(mi) & set(mo))
    dyg = abs(0.5 * (mb["y_eq"][gi["PIB"]] + mb["y_eq"][gi["POB"]])
              - 0.5 * (mb["y_eq"][gi["MIB"]] + mb["y_eq"][gi["MOB"]]))
    ops["gl"] = {"k": ks,
                 "iP": (np.array([pi[k] for k in ks]), np.array([po[k] for k in ks])),
                 "iM": (np.array([mi[k] for k in ks]), np.array([mo[k] for k in ks])),
                 "dy": dyg}
    return ops


def run_scenario(sc: dict, mb: dict, cfg: dict, tag: str = "") -> dict:
    U10 = sc["U10_sustained_ms"] * MM
    Iu = sc["Iu"]
    site, turb, aero = cfg["site"], cfg["turbulence"], cfg["aero"]
    z, z0 = site["z_deck_m"], site["z0_m"]
    U = U10 * np.log(z / z0) / np.log(10.0 / z0)
    sigma_u = Iu * U10
    sigma_w = turb["sigma_w_over_sigma_u"] * sigma_u
    Lu, Lw = turb["Lu_m"] * MM, turb["Lw_m"] * MM
    C = turb["coherence"]["Cy_lateral"]
    zeta_s = cfg["structure"]["zeta_structural"]
    nm = min(int(cfg["structure"]["n_modes_use"]), len(mb["freqs"]))

    gk, gmask = mb["gk"], mb["gmask"]
    xyz, trib, shapes = mb["xyz"], mb["trib"], mb["shapes"]

    # per-node aerodynamic reference lengths [mm]
    CdD_u = np.zeros(len(xyz))
    CdD_w = np.zeros(len(xyz))
    cw_b = aero["catwalk_per_band"]
    g_l = aero["gantry_rope_line"]
    for i, key in enumerate(gk):
        s = gmask[i]
        if key.endswith("B"):
            CdD_u[s] = cw_b["Cd_D_m"] * MM
            CdD_w[s] = 0.5 * (cw_b["dCl_dalpha_B_m"] + cw_b["Cd_D_m"]) * MM
        else:
            CdD_u[s] = g_l["Cd"] * g_l["D_m"] * MM
            CdD_w[s] = 0.5 * g_l["Cd"] * g_l["D_m"] * MM

    # decimated global point set for the O(N^2) joint acceptance
    act = np.where(trib > 0)[0]
    step = max(1, len(act) // 360)
    P = act[::step]
    w_p = trib[P] * step
    sep = np.sqrt(((xyz[P, None, :] - xyz[None, P, :]) ** 2).sum(-1))
    a_coef = C * sep / U                       # Coh = exp(-a n)

    Su = kaimal(N_GRID, sigma_u, Lu, U)
    Sw = kaimal(N_GRID, sigma_w, Lw, U)

    freqs = mb["freqs"]
    sigma_q = np.zeros(nm)
    zeta_tab = np.zeros(nm)
    for k in range(nm):
        nk = freqs[k]
        if not np.isfinite(nk) or nk <= 1e-4:
            continue
        vy = shapes[k][P, 1] * w_p * (RHO * U * CdD_u[P])
        vz = shapes[k][P, 2] * w_p * (RHO * U * CdD_w[P])
        c_aero = RHO * U * float(np.sum((CdD_u[P] * shapes[k][P, 1] ** 2
                                         + CdD_w[P] * shapes[k][P, 2] ** 2) * w_p))
        zeta = zeta_s + min(c_aero / (4.0 * np.pi * nk), 0.08)
        zeta_tab[k] = zeta
        SQ = np.empty_like(N_GRID)
        for j, n in enumerate(N_GRID):
            E = np.exp(-a_coef * n)
            SQ[j] = Su[j] * (vy @ E @ vy) + Sw[j] * (vz @ E @ vz)
        r = N_GRID / nk
        H2 = ((2 * np.pi * nk) ** 2) ** -2 / ((1 - r**2) ** 2 + (2 * zeta * r) ** 2)
        sigma_q[k] = np.sqrt(max(np.trapezoid(SQ * H2, N_GRID), 0.0))

    # ---- channel fields -------------------------------------------------------
    contrib_L = shapes[:nm, :, 1] * sigma_q[:, None]          # (nm, nn) mm
    contrib_V = shapes[:nm, :, 2] * sigma_q[:, None]
    rms_L = np.sqrt((contrib_L**2).sum(0))
    rms_V = np.sqrt((contrib_V**2).sum(0))

    ops = channel_operators(mb)
    tcw = {}
    for cw, op in ops["cw"].items():
        d = (shapes[:nm, op["i_out"], 2] - shapes[:nm, op["i_in"], 2]) / op["dy"]
        tcw[cw] = {"x": xyz[op["i_in"], 0], "rms": np.sqrt(((d * sigma_q[:, None])**2).sum(0)),
                   "modal": d}
    og = ops["gl"]
    zP = 0.5 * (shapes[:nm, og["iP"][0], 2] + shapes[:nm, og["iP"][1], 2])
    zM = 0.5 * (shapes[:nm, og["iM"][0], 2] + shapes[:nm, og["iM"][1], 2])
    dg = (zP - zM) / og["dy"]
    rms_Tg = np.sqrt(((dg * sigma_q[:, None])**2).sum(0))
    x_Tg = xyz[og["iP"][0], 0]

    # ---- peak factors (energy-weighted nu per channel at span-max station) ----
    T = cfg["peak_factor"]["T_s"]

    def peak_g(modal_amp_at_xmax):
        a2 = modal_amp_at_xmax**2
        if a2.sum() <= 0:
            return 3.5
        nu = float(np.sqrt((freqs[:nm][: len(a2)] ** 2 * a2).sum() / a2.sum()))
        lg = np.sqrt(2 * np.log(max(nu, 1e-3) * T))
        return float(lg + 0.5772 / lg)

    iL = int(np.argmax(rms_L))
    iV = int(np.argmax(rms_V))
    g_L = peak_g(np.abs(contrib_L[:, iL]))
    g_V = peak_g(np.abs(contrib_V[:, iV]))
    cw_max = max(tcw, key=lambda c: tcw[c]["rms"].max())
    iT = int(np.argmax(tcw[cw_max]["rms"]))
    g_T = peak_g(np.abs(tcw[cw_max]["modal"][:, iT] * sigma_q))
    iG = int(np.argmax(rms_Tg))
    g_G = peak_g(np.abs(dg[:, iG] * sigma_q))

    # ---- write along-span CSV (bearing-line stations, PIB as x carrier) --------
    gi = {k: i for i, k in enumerate(gk)}
    sP = np.where(gmask[gi["PIB"]])[0]
    order = sP[np.argsort(xyz[sP, 0])]
    x_out = xyz[order, 0] / MM
    csv = ART / f"buffeting_rms_alongspan_{sc['id']}{tag}.csv"
    import csv as _csv
    with open(csv, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["x_m", "rms_L_mm", "rms_V_mm", "rms_Tcw_rad", "rms_Tg_rad"])
        tc = tcw["P"]
        for xi, i in zip(x_out, order):
            j = int(np.argmin(np.abs(tc["x"] - xyz[i, 0])))
            jg = int(np.argmin(np.abs(x_Tg - xyz[i, 0])))
            w.writerow([f"{xi:.1f}", f"{rms_L[i]:.4f}", f"{rms_V[i]:.4f}",
                        f"{tc['rms'][j]:.3e}", f"{rms_Tg[jg]:.3e}"])

    top = np.argsort(sigma_q)[::-1][:10]
    summary = {
        "id": sc["id"], "tag": tag, "U10_ms": sc["U10_sustained_ms"],
        "U_deck_ms": U / MM, "Iu": Iu,
        "rms_max": {"L_mm": float(rms_L.max()), "V_mm": float(rms_V.max()),
                    "Tcw_rad": float(max(t["rms"].max() for t in tcw.values())),
                    "Tg_rad": float(rms_Tg.max())},
        "rms_mean": {"L_mm": float(rms_L[trib > 0].mean()),
                     "V_mm": float(rms_V[trib > 0].mean())},
        "peak_factor": {"L": g_L, "V": g_V, "Tcw": g_T, "Tg": g_G},
        "peak_max": {"L_mm": float(g_L * rms_L.max()), "V_mm": float(g_V * rms_V.max()),
                     "Tcw_rad": float(g_T * max(t["rms"].max() for t in tcw.values())),
                     "Tg_rad": float(g_G * rms_Tg.max())},
        "zeta_range": [float(zeta_tab[zeta_tab > 0].min() if (zeta_tab > 0).any() else 0),
                       float(zeta_tab.max())],
        "top_modes": [{"mode": int(m + 1), "f_hz": float(freqs[m]),
                       "sigma_q": float(sigma_q[m])} for m in top],
        "alongspan_csv": csv.name,
    }
    (ART / f"buffeting_summary_{sc['id']}{tag}.json").write_text(
        json.dumps(summary, indent=1))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--basis", default=str(ART / "modal_basis.npz"))
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    cfg = json.loads((BASE / "config/site_wind.json").read_text())
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    sc = next(s for s in lib["scenarios"] if s["id"] == args.scenario)
    mb = load_basis(Path(args.basis))
    s = run_scenario(sc, mb, cfg, tag=args.tag)
    print(json.dumps({k: s[k] for k in ("id", "U_deck_ms", "rms_max", "peak_max")},
                     indent=1))


if __name__ == "__main__":
    main()
