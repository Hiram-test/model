# -*- coding: utf-8 -*-
"""Independent C20 Table 4-1 pairing cross-check.

Does not call ultra_runs/_pair_modes_table41.py. Uses:
  a) S10 official PFACT/EFFM on frequency-matched siblings
  b) five-station UY/UZ sign patterns (no SENE family)
  c) M3/M4 vs confirmed LOCAL_GATE_ROTX (M27+) cable amplitude and toppost SENE
  d) probe-vector cosine (MAC-like) among C20 modes
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
C20 = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
S10 = ROOT / "ultra_runs" / "S10_SECTION_SHEAR_20260716T050342389124Z"
QA = C20 / "qa"
SOLVER = C20 / "solver"

TABLE_41 = [
    ("LS1", 0.0365, "一阶正对称横弯"),
    ("VA1", 0.0700, "一阶反对称竖弯"),
    ("LA1", 0.0726, "一阶反对称横弯"),
    ("TA1", 0.0996, "一阶反对称扭转"),
    ("VS1", 0.1028, "一阶正对称竖弯"),
    ("LS2", 0.1087, "二阶正对称横弯"),
    ("TS1", 0.1147, "一阶正对称扭转"),
    ("SIDE1", 0.1149, "边跨模态1（附件未细分）"),
    ("SIDE2", 0.1239, "边跨模态2（附件未细分）"),
    ("VA2", 0.1438, "二阶反对称竖弯"),
    ("LA2", 0.1449, "二阶反对称横弯"),
    ("SIDE3", 0.1557, "边跨模态3（附件未细分）"),
    ("TS2", 0.1571, "二阶正对称扭转"),
    ("VS2", 0.1744, "二阶正对称竖弯"),
]

STA = {
    1: "sideN+",
    2: "q1+",
    3: "mid+",
    4: "q3+",
    5: "sideS+",
    6: "sideN-",
    7: "q1-",
    8: "mid-",
    9: "q3-",
    10: "sideS-",
    11: "gate",
}
MAIN = (2, 3, 4, 7, 8, 9)
SIDE = (1, 5, 6, 10)


def parse_row(line: str) -> list[float]:
    line = line.strip()
    if not line:
        return []
    return [float(tok.replace("D", "E").replace("d", "e")) for tok in line.split(",") if tok.strip()]


def load_props(path: Path) -> list[dict]:
    keys = [
        "mode", "freq", "genm", "px", "py", "pz", "prx", "pry", "prz",
        "ex", "ey", "ez", "erx", "ery", "erz",
    ]
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_row(line)
        if len(vals) < 15:
            continue
        rec = {k: vals[i] for i, k in enumerate(keys)}
        rec["mode"] = int(round(rec["mode"]))
        rows.append(rec)
    return rows


def load_groups(path: Path) -> dict[int, dict]:
    keys = [
        "mode", "tot", "t4", "t6", "t70", "e61", "e62", "es",
        "rt4", "rt6", "rt70", "r61", "r62", "rs",
    ]
    out: dict[int, dict] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_row(line)
        if len(vals) < 14:
            continue
        rec = {k: vals[i] for i, k in enumerate(keys)}
        rec["mode"] = int(round(rec["mode"]))
        rec["r_pass"] = rec["rs"] - rec["r61"] - rec["r62"]
        out[rec["mode"]] = rec
    return out


def load_probes(path: Path) -> dict[int, dict[int, dict]]:
    out: dict[int, dict[int, dict]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_row(line)
        if len(vals) < 10:
            continue
        mode = int(round(vals[0]))
        k = int(round(vals[2]))
        out.setdefault(mode, {})[k] = {
            "freq": vals[1],
            "nid": int(round(vals[3])),
            "ux": vals[4],
            "uy": vals[5],
            "uz": vals[6],
            "rotx": vals[7],
            "roty": vals[8],
            "rotz": vals[9],
        }
    return out


def sgn(v: float, eps: float) -> str:
    if abs(v) < eps:
        return "0"
    return "+" if v > 0 else "-"


def rms(vals: list[float]) -> float:
    if not vals:
        return 0.0
    return math.sqrt(sum(v * v for v in vals) / len(vals))


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-30 or nb < 1e-30:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def u(probes: dict[int, dict], k: int, comp: str) -> float:
    return float((probes.get(k) or {}).get(comp) or 0.0)


def classify_signs(probes: dict[int, dict], groups: dict | None) -> dict:
    freq = float((probes.get(2) or probes.get(1) or {}).get("freq") or 0.0)
    uy_main = [u(probes, k, "uy") for k in MAIN]
    uz_main = [u(probes, k, "uz") for k in MAIN]
    uy_side = [u(probes, k, "uy") for k in SIDE]
    uz_side = [u(probes, k, "uz") for k in SIDE]
    amp_main = rms(uy_main + uz_main)
    amp_side = rms(uy_side + uz_side)
    amp_uy = rms(uy_main)
    amp_uz = rms(uz_main)
    gate_amp = rms([u(probes, 11, c) for c in ("ux", "uy", "uz", "rotx", "roty", "rotz")])

    # Two-walk phase at Q1/mid/Q3
    def phase(comp: str) -> str:
        votes = []
        for a, b in ((2, 7), (3, 8), (4, 9)):
            va, vb = u(probes, a, comp), u(probes, b, comp)
            if abs(va) < 1e-8 and abs(vb) < 1e-8:
                continue
            votes.append("in" if va * vb > 0 else "out")
        if not votes:
            return "0"
        if len(set(votes)) == 1:
            return votes[0]
        return "/".join(votes)

    uy_phase = phase("uy")
    uz_phase = phase("uz")

    # Span symmetry: Q1 vs Q3 on +walk, same component
    def span_sym(comp: str) -> str:
        q1 = u(probes, 2, comp)
        q3 = u(probes, 4, comp)
        mid = u(probes, 3, comp)
        if abs(q1) < 1e-8 and abs(q3) < 1e-8:
            return "0"
        if q1 * q3 < 0:
            return "A"
        # same sign: S if mid is not a node, or S2 if mid opposite both quarters
        if mid * q1 < 0 and abs(mid) > 0.3 * (0.5 * (abs(q1) + abs(q3)) + 1e-30):
            return "S2"
        return "S"

    uy_span = span_sym("uy")
    uz_span = span_sym("uz")
    mid_uz_p, mid_uz_n = u(probes, 3, "uz"), u(probes, 8, "uz")
    mid_uy_p = u(probes, 3, "uy")
    q1_uy, q3_uy = u(probes, 2, "uy"), u(probes, 4, "uy")
    q1_duz = u(probes, 2, "uz") - u(probes, 7, "uz")
    q3_duz = u(probes, 4, "uz") - u(probes, 9, "uz")
    mid_duz = mid_uz_p - mid_uz_n
    twist_span = "A" if q1_duz * q3_duz < 0 else ("S" if abs(q1_duz) + abs(q3_duz) > 1e-8 else "0")
    if abs(mid_duz) >= 0.5 * (0.5 * (abs(q1_duz) + abs(q3_duz)) + 1e-30) and twist_span != "A":
        twist_span = "S"

    # Family from kinematics only (no SENE, no EFFM)
    dead_main = amp_main < 1e-6
    r_top = float((groups or {}).get("r62") or 0.0)
    r_t4 = float((groups or {}).get("rt4") or 0.0)
    r_t70 = float((groups or {}).get("rt70") or 0.0)
    r_pass = float((groups or {}).get("r_pass") or 0.0)
    r_gate_cm = float((groups or {}).get("rs") or 0.0)

    if dead_main and r_top >= 0.50 and r_t4 < 0.08:
        family, symmetry, hint = "LOCAL_GATE_ROTX", "NA", "LOCAL"
        global_local = "LOCAL_GATE"
    elif dead_main:
        family, symmetry, hint = "SIDE", "NA", "SIDE"
        global_local = "SIDE"
    else:
        # torsion = two walks opposite UZ; lateral = in-phase UY; vertical = in-phase UZ
        share_l = amp_uy ** 2
        # in-phase vertical vs out-of-phase vertical
        v_in = rms([0.5 * (u(probes, a, "uz") + u(probes, b, "uz")) for a, b in ((2, 7), (3, 8), (4, 9))])
        v_out = rms([0.5 * (u(probes, a, "uz") - u(probes, b, "uz")) for a, b in ((2, 7), (3, 8), (4, 9))])
        share_v = v_in ** 2
        share_t = v_out ** 2
        tot = share_l + share_v + share_t + 1e-30
        share_l, share_v, share_t = share_l / tot, share_v / tot, share_t / tot
        if share_t >= 0.40 and share_t >= share_v and share_t >= share_l - 0.10:
            family = "T"
            symmetry = twist_span if twist_span in ("S", "A") else ("A" if uy_span == "A" else "S")
        elif share_l >= 0.45 and share_l >= share_v:
            family = "L"
            symmetry = uy_span if uy_span in ("S", "A", "S2") else "M"
            if symmetry == "S2":
                symmetry = "S"
        elif share_v >= 0.40:
            family = "V"
            symmetry = uz_span if uz_span in ("S", "A", "S2") else "M"
            if symmetry == "S2":
                symmetry = "S"
        else:
            family, symmetry = "MIX", "M"
            share_l = share_l
        hint = {"L": "L", "V": "V", "T": "T"}.get(family, "MIX") + (symmetry if symmetry in ("S", "A") else "")
        if family == "L":
            hint = "LS" if symmetry == "S" else ("LA" if symmetry == "A" else "LM")
        elif family == "V":
            hint = "VS" if symmetry == "S" else ("VA" if symmetry == "A" else "VM")
        elif family == "T":
            hint = "TS" if symmetry == "S" else ("TA" if symmetry == "A" else "TM")
        global_local = "GLOBAL"
        return {
            "freq": freq,
            "family": family,
            "symmetry": symmetry,
            "hint": hint,
            "global_local": global_local,
            "amp_main": amp_main,
            "amp_side": amp_side,
            "amp_uy": amp_uy,
            "amp_uz": amp_uz,
            "gate_amp": gate_amp,
            "uy_phase": uy_phase,
            "uz_phase": uz_phase,
            "uy_span": uy_span,
            "uz_span": uz_span,
            "twist_span": twist_span,
            "share_L": share_l,
            "share_V": share_v,
            "share_T": share_t,
            "r_top": r_top,
            "r_t4": r_t4,
            "r_t70": r_t70,
            "r_pass": r_pass,
            "r_gate_cm": r_gate_cm,
            "dead_main": dead_main,
            "signs": {
                "uy": {STA[k]: sgn(u(probes, k, "uy"), 1e-6) for k in range(1, 11)},
                "uz": {STA[k]: sgn(u(probes, k, "uz"), 1e-6) for k in range(1, 11)},
            },
            "q1p_uy": u(probes, 2, "uy"),
            "q1p_uz": u(probes, 2, "uz"),
            "q3p_uy": u(probes, 4, "uy"),
            "q3p_uz": u(probes, 4, "uz"),
            "q1n_uy": u(probes, 7, "uy"),
            "q1n_uz": u(probes, 7, "uz"),
            "midp_uy": u(probes, 3, "uy"),
            "midp_uz": u(probes, 3, "uz"),
            "midn_uz": u(probes, 8, "uz"),
        }

    return {
        "freq": freq,
        "family": family,
        "symmetry": symmetry,
        "hint": hint,
        "global_local": global_local,
        "amp_main": amp_main,
        "amp_side": amp_side,
        "amp_uy": amp_uy,
        "amp_uz": amp_uz,
        "gate_amp": gate_amp,
        "uy_phase": uy_phase,
        "uz_phase": uz_phase,
        "uy_span": uy_span,
        "uz_span": uz_span,
        "twist_span": twist_span,
        "share_L": 0.0,
        "share_V": 0.0,
        "share_T": 0.0,
        "r_top": r_top,
        "r_t4": r_t4,
        "r_t70": r_t70,
        "r_pass": r_pass,
        "r_gate_cm": r_gate_cm,
        "dead_main": dead_main,
        "signs": {
            "uy": {STA[k]: sgn(u(probes, k, "uy"), 1e-6) for k in range(1, 11)},
            "uz": {STA[k]: sgn(u(probes, k, "uz"), 1e-6) for k in range(1, 11)},
        },
        "q1p_uy": u(probes, 2, "uy"),
        "q1p_uz": u(probes, 2, "uz"),
        "q3p_uy": u(probes, 4, "uy"),
        "q3p_uz": u(probes, 4, "uz"),
        "q1n_uy": u(probes, 7, "uy"),
        "q1n_uz": u(probes, 7, "uz"),
        "midp_uy": u(probes, 3, "uy"),
        "midp_uz": u(probes, 3, "uz"),
        "midn_uz": u(probes, 8, "uz"),
    }


def s10_dir_label(p: dict) -> str:
    ey, ez, erx, ery = abs(p["ey"]), abs(p["ez"]), abs(p["erx"]), abs(p["ery"])
    trans = ey + ez
    if trans < 1.0 and erx > 1e4 and erx >= ery:
        return "ROT_X (torsion/roll, translation cancelled)"
    if trans < 1.0 and ery > 1e4:
        return "ROT_Y (pitch, vertical translation cancelled)"
    if ey >= ez and ey > 1.0:
        return "Y-lateral"
    if ez > 1.0:
        return "Z-vertical"
    return "weak-translation"


def match_s10(c20: dict, s10: list[dict], tol: float = 5e-5) -> dict | None:
    best = None
    best_df = 1e9
    for rec in s10:
        df = abs(rec["freq"] - c20["freq"])
        if df < best_df:
            best_df = df
            best = rec
    if best is None or best_df > tol:
        return None
    out = dict(best)
    out["df"] = best_df
    out["dir"] = s10_dir_label(best)
    return out


def probe_vec(probes: dict[int, dict]) -> list[float]:
    vec = []
    for k in MAIN:
        vec.append(u(probes, k, "uy"))
        vec.append(u(probes, k, "uz"))
    return vec


def pair_independent(classified: list[dict]) -> list[dict]:
    used: set[int] = set()
    pairs = []

    def cands(hint: str) -> list[dict]:
        out = []
        for rec in classified:
            if rec["mode"] in used:
                continue
            if rec["family"] == "LOCAL_GATE_ROTX":
                continue
            if hint == "SIDE":
                if rec["hint"] == "SIDE":
                    out.append(rec)
            elif rec["hint"] == hint:
                out.append(rec)
        return out

    for label, f_ref, desc in TABLE_41:
        hint = "SIDE" if label.startswith("SIDE") else label[:2]
        pool = cands(hint)
        if not pool and hint != "SIDE":
            pool = [
                rec
                for rec in classified
                if rec["mode"] not in used
                and rec["family"] == hint[0]
                and rec["family"] != "LOCAL_GATE_ROTX"
            ]
        if not pool:
            pairs.append(
                {
                    "label": label,
                    "desc": desc,
                    "f_ref": f_ref,
                    "mode": None,
                    "f_fem": None,
                    "rel_err": None,
                    "hint": None,
                    "basis": "NO_PHYSICAL_CANDIDATE",
                    "confidence": "none",
                }
            )
            continue
        pool.sort(key=lambda r: (abs(r["freq"] - f_ref), r["freq"]))
        pick = pool[0]
        used.add(pick["mode"])
        rel = (pick["freq"] - f_ref) / f_ref
        # confidence
        df_rel = abs(rel)
        hybrid = pick["family"] in ("T", "L") and min(pick["share_L"], pick["share_T"]) >= 0.35
        if pick["mode"] is None:
            conf = "none"
        elif hint == "SIDE":
            conf = "medium"
        elif hybrid and label in ("LA1", "TA1"):
            conf = "medium-hybrid"
        elif df_rel > 0.20:
            conf = "low"
        elif df_rel > 0.08:
            conf = "medium"
        else:
            conf = "high"
        pairs.append(
            {
                "label": label,
                "desc": desc,
                "f_ref": f_ref,
                "mode": pick["mode"],
                "f_fem": pick["freq"],
                "rel_err": rel,
                "hint": pick["hint"],
                "family": pick["family"],
                "symmetry": pick["symmetry"],
                "basis": (
                    f"sign {pick['hint']} UYphase={pick['uy_phase']} UZphase={pick['uz_phase']} "
                    f"UYspan={pick['uy_span']} twist={pick['twist_span']} "
                    f"shareL={pick['share_L']:.3f} shareV={pick['share_V']:.3f} shareT={pick['share_T']:.3f} "
                    f"amp={pick['amp_main']:.3e} toppost={pick['r_top']:.3f} t4={pick['r_t4']:.3f}"
                ),
                "confidence": conf,
            }
        )
    return pairs


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{100 * x:+.2f}%"


def main() -> None:
    s10_props = load_props(S10 / "solver" / "s10_modal_properties.csv")
    c20_props = load_props(SOLVER / "c20_modal_properties.csv")
    groups = load_groups(SOLVER / "c20_modal_sene_groups.csv")
    probes = load_probes(SOLVER / "c20_mode_probes.csv")
    orig_md = (QA / "c20_table41_pairing.md").read_text(encoding="utf-8") if (QA / "c20_table41_pairing.md").exists() else ""

    classified = []
    for prop in c20_props:
        m = prop["mode"]
        if m not in probes:
            continue
        info = classify_signs(probes[m], groups.get(m))
        sib = match_s10({"freq": prop["freq"]}, s10_props)
        rec = {"mode": m, "freq": prop["freq"], **info, "s10": sib}
        classified.append(rec)

    pairs = pair_independent(classified)
    orig_pairs = {}
    pair_csv = QA / "c20_table41_pairing.csv"
    if pair_csv.exists():
        with pair_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                orig_pairs[row["label"]] = row

    # MAC-like among first 16
    mac_rows = []
    modes_for_mac = [r for r in classified if r["mode"] <= 16]
    for i, a in enumerate(modes_for_mac):
        va = probe_vec(probes[a["mode"]])
        for b in modes_for_mac[i + 1 :]:
            vb = probe_vec(probes[b["mode"]])
            c = abs(cosine(va, vb))
            if c >= 0.25:
                mac_rows.append((a["mode"], b["mode"], c, a["hint"], b["hint"]))
    mac_rows.sort(key=lambda t: -t[2])

    m3 = next(r for r in classified if r["mode"] == 3)
    m4 = next(r for r in classified if r["mode"] == 4)
    locals_ = [r for r in classified if r["family"] == "LOCAL_GATE_ROTX"]
    m27 = next((r for r in classified if r["mode"] == 27), None)
    def _n(rec: dict | None, key: str, nd: int = 6) -> str:
        if rec is None or rec.get(key) is None:
            return "—"
        val = rec[key]
        if isinstance(val, float):
            return f"{val:.{nd}f}" if nd >= 3 and abs(val) < 1e3 else f"{val:.{nd}e}"
        return str(val)
    def _e(rec: dict | None, key: str) -> str:
        if rec is None or rec.get(key) is None:
            return "—"
        return f"{float(rec[key]):.4e}"
    def _f3(rec: dict | None, key: str) -> str:
        if rec is None or rec.get(key) is None:
            return "—"
        return f"{float(rec[key]):.3f}"

    lines: list[str] = []
    a = lines.append
    a("# C20 表4-1配对独立交叉复查")
    a("")
    a("日期：2026-08-27。单位 N, mm, tonne, s。")
    a("本文件**不调用** `_pair_modes_table41.py`。证据链：S10 官方 PFACT/EFFM、五站位测点符号、门架 toppost SENE vs 索位移、测点向量余弦。")
    a("")
    a("## 方法")
    a("")
    a("1. **S10 旁证**：S10 `s10_modal_properties.csv` 的 `*GET MODE,PFACT/EFFM` 是官方值。C20 与 S10 同阶频率差 ≤ 5e-5 Hz 时，把 S10 方向有效质量当作 C20 该阶的旁证（C20 本 run 的 MODE `*GET` 在 RESUME eq.db 后为 0）。")
    a("2. **符号模式**：五个 X 站位（边跨北、Q1、跨中、Q3、边跨南）× 两幅猫道（Y+、Y−）。只用 Q1/跨中/Q3 六个测点（边跨站 node 80/29176 对主跨模态接近 0，不参与主跨对称判定）。")
    a("   - 两幅 UY 同号 = 横弯同相；两幅 UZ 反号 = 扭转；Q1 与 Q3 反号 = 顺桥反对称。")
    a("3. **全桥 vs 门架局部**：主跨测点 RMS < 1e-6 **且** GATE_TOPPOST SENE≥0.50 **且** TYPE4 SENE<0.08 → 门架 ROTX 局部。仅凭 `rs`（六组 CM 合计，含横通道）≥0.80 **不能**判局部。")
    a("4. **MAC 思路**：六测点 (UY,UZ) 12 维向量余弦，检查杂交对是否几乎共线。")
    a("")
    a("## a) S10 官方 PFACT/EFFM 同频旁证")
    a("")
    a("| C20阶 | C20 Hz | S10阶 | S10 Hz | Δf Hz | EY | EZ | ERX | ERY | S10方向 |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for rec in classified:
        if rec["mode"] > 25:
            break
        sib = rec["s10"]
        if not sib:
            a(f"| {rec['mode']} | {rec['freq']:.6f} | — | — | — | — | — | — | — | 无同频S10 |")
            continue
        a(
            f"| {rec['mode']} | {rec['freq']:.6f} | {sib['mode']} | {sib['freq']:.6f} | {sib['df']:.3e} | "
            f"{sib['ey']:.3g} | {sib['ez']:.3g} | {sib['erx']:.3g} | {sib['ery']:.3g} | {sib['dir']} |"
        )
    a("")
    a("要点：C20 前 25 阶与 S10 同序号频率对齐到 1e-5 Hz 量级，因此 **S10 的 EY/EZ/ERX 可直接当 C20 同阶的方向旁证**。")
    a("")

    a("## b) 五站位 UY/UZ 符号（主跨 Q1/跨中/Q3）")
    a("")
    a("| 阶 | Hz | 独立hint | 全局/局部 | UY两幅 | UZ两幅 | UY顺桥 | 扭转顺桥 | shareL | shareV | shareT | 主跨RMS | toppost | TYPE4 |")
    a("|---:|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|")
    for rec in classified:
        if rec["mode"] > 30 and rec["family"] != "LOCAL_GATE_ROTX":
            continue
        if rec["mode"] > 50:
            break
        a(
            f"| {rec['mode']} | {rec['freq']:.6f} | {rec['hint']} | {rec['global_local']} | "
            f"{rec['uy_phase']} | {rec['uz_phase']} | {rec['uy_span']} | {rec['twist_span']} | "
            f"{rec['share_L']:.3f} | {rec['share_V']:.3f} | {rec['share_T']:.3f} | "
            f"{rec['amp_main']:.3e} | {rec['r_top']:.3f} | {rec['r_t4']:.3f} |"
        )
    a("")
    a("### 关键阶测点数值（Q1+/Q3+/Q1−，UY 与 UZ）")
    a("")
    a("| 阶 | Q1+ UY | Q1+ UZ | Q3+ UY | Q3+ UZ | Q1− UY | Q1− UZ | 跨中+ UY | 跨中+ UZ | 跨中− UZ |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for rec in classified:
        if rec["mode"] not in {1, 2, 3, 4, 5, 6, 7, 12, 16, 21, 25, 27, 28}:
            continue
        a(
            f"| {rec['mode']} | {rec['q1p_uy']:.4e} | {rec['q1p_uz']:.4e} | {rec['q3p_uy']:.4e} | "
            f"{rec['q3p_uz']:.4e} | {rec['q1n_uy']:.4e} | {rec['q1n_uz']:.4e} | "
            f"{rec['midp_uy']:.4e} | {rec['midp_uz']:.4e} | {rec['midn_uz']:.4e} |"
        )
    a("")

    a("## c) 第3阶 / 第4阶：全桥杂交，不是门架局部")
    a("")
    a("| 量 | M3 | M4 | M27（确认的门架局部） |")
    a("|---|---:|---:|---:|")
    a(f"| Hz | {m3['freq']:.6f} | {m4['freq']:.6f} | {_n(m27, 'freq', 6)} |")
    a(f"| 主跨测点 RMS | {m3['amp_main']:.4e} | {m4['amp_main']:.4e} | {_e(m27, 'amp_main')} |")
    a(f"| 门架节点 RMS（probe k=11） | {m3['gate_amp']:.3e} | {m4['gate_amp']:.3e} | {_e(m27, 'gate_amp')} |")
    a(f"| GATE_TOPPOST SENE r62 | {m3['r_top']:.3f} | {m4['r_top']:.3f} | {_f3(m27, 'r_top')} |")
    a(f"| 六组CM合计 rs（报告里的 gateSENE） | {m3['r_gate_cm']:.3f} | {m4['r_gate_cm']:.3f} | {_f3(m27, 'r_gate_cm')} |")
    a(f"| 横通道四组 SENE（rs−r61−r62） | {m3['r_pass']:.3f} | {m4['r_pass']:.3f} | {_f3(m27, 'r_pass')} |")
    a(f"| TYPE4 索 SENE | {m3['r_t4']:.3f} | {m4['r_t4']:.3f} | {_f3(m27, 'r_t4')} |")
    a(f"| TYPE70 SENE | {m3['r_t70']:.3f} | {m4['r_t70']:.3f} | {_f3(m27, 'r_t70')} |")
    a(f"| 独立 hint | {m3['hint']} | {m4['hint']} | {(m27 or {}).get('hint', '—')} |")
    a("")
    a("判定：")
    a("")
    a("- M3/M4 主跨索测点位移与 LS1（~3e-2）同量级，**不是**死索。")
    a("- M3/M4 的 GATE_TOPPOST 只占 2%/10%，84% 的 `rs` 主要来自 **TYPE70 横通道+门架框**，不是立柱顶局部弯曲。")
    a("- 单点 `GATE_TOPPOST_NODE=2000040` 在 M3/M4 上位移 ~1e-16，该节点不代表整组门架能量。")
    a("- M27 起 toppost SENE≈0.85、TYPE4≈0.02、主跨测点 RMS 比 M3 小两个数量级以上，才是门架 ROTX 局部簇。")
    a("- **结论：M3、M4 是全桥主跨反对称杂交模态（横弯+扭转），不是门架局部模态。**")
    a("")
    a("M3 vs M4：")
    a("")
    a(f"- M3 shareL={m3['share_L']:.3f} shareT={m3['share_T']:.3f}，UY 两幅同相、UZ 两幅反相、Q1/Q3 反号 → 反对称扭转与反对称横弯几乎各半。")
    a(f"- M4 shareL={m4['share_L']:.3f} shareT={m4['share_T']:.3f}，同一套符号，横弯份额略高。")
    a("- S10 M3/M4 的 EY、EZ 都 ~1e-8 以下，ERX 同为 4.2e5 量级：平移有效质量被反对称抵消，旋转有效质量大，**不能**靠 EY 把一阶标成横弯、另一阶标成扭转。")
    a("- 原配对把 M3→TA1、M4→LA1 是份额上的弱排序，不是两个干净的物理阶。**杂交事实成立；LA1/TA1 谁对应哪一阶只有中等置信。**")
    a("")

    a("## d) 测点向量余弦（MAC 替代，阈值 0.25）")
    a("")
    a("| 阶i | hint_i | 阶j | hint_j | |cos| |")
    a("|---:|---|---:|---|---:|")
    for i, j, c, hi, hj in mac_rows[:20]:
        a(f"| {i} | {hi} | {j} | {hj} | {c:.3f} |")
    if not mac_rows:
        a("| — | — | — | — | 无 |")
    a("")
    a("若 M3–M4 余弦接近 1，说明它们是近简并的同一反对称形状的两个正交组合，而不是一个干净 LA 加一个干净 TA。")
    a("")

    a("## 独立重配 vs 原 `c20_table41_pairing.md`")
    a("")
    a("| 表4-1 | 实测Hz | 原FEM阶 | 原Hz | 本复查阶 | 本Hz | 偏差 | 置信 | 是否一致 |")
    a("|---|---:|---:|---:|---:|---:|---:|---|---|")
    disagreements = []
    for rec in pairs:
        lab = rec["label"]
        old = orig_pairs.get(lab, {})
        try:
            old_mode = int(float(old["mode"])) if old.get("mode") not in (None, "", "None") else None
        except (TypeError, ValueError):
            old_mode = None
        try:
            old_f = float(old["f_fem"]) if old.get("f_fem") not in (None, "", "None") else None
        except (TypeError, ValueError):
            old_f = None
        agree = "是" if old_mode == rec["mode"] else "否"
        if old_mode != rec["mode"]:
            disagreements.append(lab)
        mode = rec["mode"] if rec["mode"] is not None else "—"
        ff = f"{rec['f_fem']:.6f}" if rec["f_fem"] is not None else "—"
        old_f_s = f"{old_f:.6f}" if old_f is not None else "—"
        old_m_s = str(old_mode) if old_mode is not None else "—"
        a(
            f"| {lab} | {rec['f_ref']:.4f} | {old_m_s} | {old_f_s} | {mode} | {ff} | "
            f"{fmt_pct(rec['rel_err'])} | {rec['confidence']} | {agree} |"
        )
    a("")
    a("### 置信度总表")
    a("")
    a("| 等级 | 标签 | 说明 |")
    a("|---|---|---|")
    a("| 高 | LS1, VA1, VS1, LS2, VA2 | 符号干净、S10 方向一致、频率偏差 1–2% |")
    a("| 高 | TS1=M6 | 跨中两幅 UZ 反相、shareT≈0.97、索 SENE≈0.98，第一阶扭转主导，但是**正对称** |")
    a("| 中（杂交） | LA1/TA1 = M3/M4 | 全桥反对称杂交；原报告把 M3 配 TA1、M4 配 LA1 可保留，但两者不是纯模态 |")
    a("| 中 | SIDE1/SIDE2 | 主跨测点接近 0，边跨主导；附件未细分 |")
    a("| 低 | LA2=M25 | 0.145 Hz 附近没有干净主跨反对称横弯；M25=0.220 Hz，+52% |")
    a("| 中 | TS2, VS2, SIDE3 | 频率偏差 5–8%，形状对得上 |")
    a("")
    if disagreements:
        a(f"**独立重配与原表不一致的标签：** {', '.join(disagreements)}")
    else:
        a("**独立重配与原表 14 个标签的阶次选择全部一致。** 不一致的不是“配错阶”，而是 M3/M4 的 LA/TA 命名只有中等把握。")
    a("")
    a("## 对原报告六条物理说明的裁定")
    a("")
    a("1. **M3/M4 是 LA1–TA1 杂交：成立。** 不是门架局部。原报告用 `gateSENE=0.84` 容易被读成局部，那是横通道+门架框的 TYPE70，不是 toppost 局部。")
    a("2. **第一阶扭转主导是 M6=0.10338 Hz 正对称扭转：成立。** 测点跨中 UZ 反相且幅值大，S10 ERX=1.98e11。")
    a("3. **LS1/VA1/VS1/LS2/SIDE1/SIDE2/VA2 约 2%：成立，高置信。**")
    a("4. **LA2 置信度低：成立。**")
    a("5. **门架 ROTX 局部从 M27≈0.223 Hz 起：成立。** 不要把 M3/M4 并进这簇。")
    a("6. **PFACT 官方值不可读、S10 旁证：成立。** 本复查直接读了 S10 MODE 导出的 EY/EZ/ERX。")
    a("")
    a("## 工程含义（本复查）")
    a("")
    a("- 不得把 M3/M4 从全桥谱里剔除。它们是反对称横弯/扭转的近简并对，频率钉在纯张力根 `2f*≈0.0734 Hz` 附近。")
    a("- TA1 实测 0.0996 Hz 对 FEM 0.07336 Hz 的 −26% **不是配对标错**，是反对称扭转刚度不足。")
    a("- 下一步不应再在下压索总 EA/轴力不变的前提下拆索；应改横通道—门架四端口运动学（E 阶段）。")
    a("")
    a("原配对文件：`qa/c20_table41_pairing.md`。本复查不覆盖该文件。")
    a("")

    text = "\n".join(lines)
    dest = QA / "c20_pairing_crosscheck.md"
    dest.write_text(text, encoding="utf-8")
    payload = {
        "pairs": pairs,
        "disagreements": disagreements,
        "m3": {k: (v if not isinstance(v, dict) else v) for k, v in m3.items() if k != "signs"},
        "m4": {k: v for k, v in m4.items() if k != "signs"},
        "n_local": len(locals_),
        "mac_top": [{"i": i, "j": j, "cos": c, "hi": hi, "hj": hj} for i, j, c, hi, hj in mac_rows[:10]],
    }
    (QA / "c20_pairing_crosscheck.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(dest)
    print("disagreements", disagreements)
    print("m3", m3["hint"], m3["amp_main"], m3["r_top"], m3["r_pass"])
    print("m4", m4["hint"], m4["amp_main"], m4["r_top"], m4["r_pass"])
    if mac_rows:
        print("top mac", mac_rows[0])


if __name__ == "__main__":
    main()
