# -*- coding: utf-8 -*-
"""Pair ANSYS modes to 附件2-3 Table 4-1 by physics, not frequency rank."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")

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

PROP_COLS = [
    "mode", "freq", "genm", "px", "py", "pz", "prx", "pry", "prz",
    "ex", "ey", "ez", "erx", "ery", "erz",
]
SENE_COLS = [
    "mode", "tot", "e61", "e62", "e63", "e64", "e65", "e66",
    "r61", "r62", "r63", "r64", "r65", "r66", "es", "rs",
]
# probes: k=1..5 Y+, 6..10 Y- = stations sideN,Q1,mid,Q3,sideS; k=11 gate toppost
STA_POS = {1: "sideN+", 2: "q1+", 3: "mid+", 4: "q3+", 5: "sideS+"}
STA_NEG = {6: "sideN-", 7: "q1-", 8: "mid-", 9: "q3-", 10: "sideS-"}


def parse_fortran_row(line: str) -> list[float]:
    line = line.strip()
    if not line:
        return []
    return [float(tok.replace("D", "E").replace("d", "e")) for tok in line.split(",") if tok.strip()]


def load_properties(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_fortran_row(line)
        if len(vals) < 15:
            continue
        rec = {k: vals[i] for i, k in enumerate(PROP_COLS)}
        rec["mode"] = int(round(rec["mode"]))
        rows.append(rec)
    return rows


def load_sene(path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_fortran_row(line)
        if len(vals) < 16:
            continue
        rec = {k: vals[i] for i, k in enumerate(SENE_COLS)}
        out[int(round(rec["mode"]))] = rec
    return out


def load_groups(path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not path.exists():
        return out
    keys = [
        "mode", "tot", "t4", "t6", "t70", "e61", "e62", "es",
        "rt4", "rt6", "rt70", "r61", "r62", "rs",
    ]
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_fortran_row(line)
        if len(vals) < 14:
            continue
        rec = {k: vals[i] for i, k in enumerate(keys)}
        out[int(round(rec["mode"]))] = rec
    return out


def load_probes(path: Path) -> dict[int, dict[int, dict]]:
    out: dict[int, dict[int, dict]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        vals = parse_fortran_row(line)
        if len(vals) < 10:
            continue
        mode = int(round(vals[0]))
        k = int(round(vals[2]))
        rec = {
            "freq": vals[1],
            "nid": int(round(vals[3])),
            "ux": vals[4],
            "uy": vals[5],
            "uz": vals[6],
            "rotx": vals[7],
            "roty": vals[8],
            "rotz": vals[9],
        }
        out.setdefault(mode, {})[k] = rec
    return out


def rms(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def _u(probes: dict[int, dict] | None, k: int, comp: str) -> float:
    if not probes:
        return 0.0
    rec = probes.get(k) or {}
    return float(rec.get(comp) or 0.0)


def classify(prop: dict, sene: dict | None, groups: dict | None, probes: dict[int, dict] | None) -> dict:
    ex, ey, ez = abs(prop["ex"]), abs(prop["ey"]), abs(prop["ez"])
    erx, ery, erz = abs(prop["erx"]), abs(prop["ery"]), abs(prop["erz"])
    r_gate = 0.0
    r_t4 = 0.0
    r_top = 0.0
    if sene:
        r_gate = float(sene.get("rs") or 0.0)
        r_top = float(sene.get("r62") or 0.0)
    if groups:
        r_t4 = float(groups.get("rt4") or 0.0)
        r_gate = max(r_gate, float(groups.get("rs") or 0.0))
        r_top = max(r_top, float(groups.get("r62") or 0.0))

    l_energy = v_energy = t_energy = 0.0
    for a, b in ((2, 7), (3, 8), (4, 9)):
        uyp, uyn = _u(probes, a, "uy"), _u(probes, b, "uy")
        uzp, uzn = _u(probes, a, "uz"), _u(probes, b, "uz")
        l_energy += (uyp + uyn) ** 2
        v_energy += (uzp + uzn) ** 2
        t_energy += (uzp - uzn) ** 2
    shape_tot = l_energy + v_energy + t_energy + 1e-30
    share_l = l_energy / shape_tot
    share_v = v_energy / shape_tot
    share_t = t_energy / shape_tot

    mid_uy = _u(probes, 3, "uy")
    mid_uz_p, mid_uz_n = _u(probes, 3, "uz"), _u(probes, 8, "uz")
    q1_uy, q3_uy = _u(probes, 2, "uy"), _u(probes, 4, "uy")
    mid_duz = mid_uz_p - mid_uz_n
    q1_duz = _u(probes, 2, "uz") - _u(probes, 7, "uz")
    q3_duz = _u(probes, 4, "uz") - _u(probes, 9, "uz")
    mid_cuz = 0.5 * (mid_uz_p + mid_uz_n)
    q1_cuz = 0.5 * (_u(probes, 2, "uz") + _u(probes, 7, "uz"))
    main_amp = rms(
        [_u(probes, k, "uy") for k in (2, 3, 4, 7, 8, 9)]
        + [_u(probes, k, "uz") for k in (2, 3, 4, 7, 8, 9)]
    )
    dead_main = main_amp < 1.0e-6

    local_gate = bool(dead_main and r_top >= 0.50 and r_t4 < 0.08)
    if r_top >= 0.80 and r_t4 < 0.05 and share_t >= 0.90:
        local_gate = True

    if dead_main and not local_gate:
        family = "SIDE"
    elif share_t >= 0.40 and share_t >= share_v and share_t >= share_l - 0.08:
        family = "T"
    elif share_l >= 0.50 and share_l >= share_v:
        family = "L"
    elif share_v >= 0.40:
        family = "V"
    elif ey >= ez and ey > 1.0:
        family = "L"
    elif ez > 1.0:
        family = "V"
    else:
        family = "MIX"

    if family == "L":
        if abs(mid_uy) >= 0.6 * (0.5 * (abs(q1_uy) + abs(q3_uy)) + 1e-30) and q1_uy * q3_uy >= 0:
            symmetry = "S"
        elif abs(mid_uy) <= 0.35 * (0.5 * (abs(q1_uy) + abs(q3_uy)) + 1e-30) or q1_uy * q3_uy < 0:
            symmetry = "A"
        else:
            symmetry = "M"
        # second symmetric lateral: mid opposite to both quarters
        if q1_uy * q3_uy > 0 and mid_uy * q1_uy < 0:
            symmetry = "S"
    elif family == "V":
        if abs(mid_cuz) >= 0.5 * (abs(q1_cuz) + 1e-30):
            symmetry = "S"
        else:
            symmetry = "A"
    elif family == "T":
        if abs(mid_duz) >= 0.5 * (0.5 * (abs(q1_duz) + abs(q3_duz)) + 1e-30):
            symmetry = "S"
        else:
            symmetry = "A"
    else:
        symmetry = "NA"

    order_hint = None
    if local_gate:
        order_hint = "LOCAL"
        family = "LOCAL_GATE_ROTX"
        symmetry = "NA"
    elif family == "SIDE":
        order_hint = "SIDE"
    elif family == "L" and symmetry == "S":
        order_hint = "LS"
    elif family == "L" and symmetry == "A":
        order_hint = "LA"
    elif family == "V" and symmetry == "S":
        order_hint = "VS"
    elif family == "V" and symmetry == "A":
        order_hint = "VA"
    elif family == "T" and symmetry == "S":
        order_hint = "TS"
    elif family == "T" and symmetry == "A":
        order_hint = "TA"

    return {
        "family": family,
        "symmetry": symmetry,
        "order_hint": order_hint,
        "share_L": share_l,
        "share_V": share_v,
        "share_T": share_t,
        "side_ratio": 1.0 if dead_main else 0.0,
        "r_gate": r_gate,
        "r_toppost": r_top,
        "r_cable_t4": r_t4,
        "effm_x": ex,
        "effm_y": ey,
        "effm_z": ez,
        "effm_rx": erx,
        "effm_ry": ery,
        "effm_rz": erz,
        "pfact_x": prop["px"],
        "pfact_y": prop["py"],
        "pfact_z": prop["pz"],
        "local_gate": local_gate,
        "main_amp": main_amp,
        "mid_duz": mid_duz,
        "q1_duz": q1_duz,
        "pfact_source": prop.get("pfact_source", "official"),
    }


def pair_table41(classified: list[dict]) -> list[dict]:
    used: set[int] = set()
    pairs = []
    family_counts = {"LS": 0, "LA": 0, "VS": 0, "VA": 0, "TS": 0, "TA": 0, "SIDE": 0}

    def candidates(hint: str, allow_m: bool = True) -> list[dict]:
        out = []
        for rec in classified:
            if rec["mode"] in used:
                continue
            if rec["local_gate"]:
                continue
            h = rec["order_hint"]
            if hint == "SIDE":
                if h == "SIDE":
                    out.append(rec)
            elif h == hint:
                out.append(rec)
            elif allow_m and rec["family"] == hint[0] and rec["symmetry"] == "M":
                out.append(rec)
        return out

    for label, f_ref, desc in TABLE_41:
        hint = "SIDE" if label.startswith("SIDE") else label[:2]
        cands = candidates(hint, allow_m=True)
        if not cands and hint != "SIDE":
            fam = hint[0]
            cands = [
                rec
                for rec in classified
                if rec["mode"] not in used
                and not rec["local_gate"]
                and rec["family"] == fam
            ]
        if not cands:
            pairs.append(
                {
                    "label": label,
                    "desc": desc,
                    "f_ref": f_ref,
                    "mode": None,
                    "f_fem": None,
                    "rel_err": None,
                    "basis": "NO_PHYSICAL_CANDIDATE",
                }
            )
            continue
        # Nearest unused same-hint mode. Never expand TA->TS by measured-frequency
        # proximity: C20 cross-check forbids giving TA1 to the 0.103 Hz TS.
        family_counts[hint] = family_counts.get(hint, 0) + 1
        cands_sorted = sorted(cands, key=lambda r: (abs(r["freq"] - f_ref), r["freq"]))
        pick = cands_sorted[0]
        used.add(pick["mode"])
        rel = (pick["freq"] - f_ref) / f_ref
        basis = (
            f"family={pick['family']} symmetry={pick['symmetry']} "
            f"shareL={pick['share_L']:.3f} shareV={pick['share_V']:.3f} shareT={pick['share_T']:.3f} "
            f"EY={pick['effm_y']:.3g} EZ={pick['effm_z']:.3g} ERX={pick['effm_rx']:.3g} ERY={pick['effm_ry']:.3g} "
            f"gateSENE={pick['r_gate']:.3f} cableSENE={pick['r_cable_t4']:.3f} sideRatio={pick['side_ratio']:.2f}"
        )
        pairs.append(
            {
                "label": label,
                "desc": desc,
                "f_ref": f_ref,
                "mode": pick["mode"],
                "f_fem": pick["freq"],
                "rel_err": rel,
                "basis": basis,
                "order_hint": pick["order_hint"],
            }
        )
    return pairs


def attach_sibling_pfact(props: list[dict], sibling_csv: Path, tol_hz: float = 5.0e-5) -> None:
    """Copy S10/C20-SPRING PFACT/EFFM onto frequency-matched rows when MODE *GET is empty."""
    if not sibling_csv.exists() or not props:
        return
    sibling = load_properties(sibling_csv)
    for rec in props:
        official = abs(rec.get("ey") or 0.0) + abs(rec.get("ez") or 0.0) + abs(rec.get("ex") or 0.0)
        if official > 1e-12:
            rec["pfact_source"] = "official"
            continue
        best = None
        best_df = 1e9
        for other in sibling:
            df = abs(other["freq"] - rec["freq"])
            if df < best_df:
                best_df = df
                best = other
        if best is None or best_df > tol_hz:
            rec["pfact_source"] = "none"
            continue
        for key in ("genm", "px", "py", "pz", "prx", "pry", "prz", "ex", "ey", "ez", "erx", "ery", "erz"):
            rec[key] = best[key]
        rec["pfact_source"] = f"sibling:{sibling_csv.parent.parent.name}:df={best_df:.3e}Hz"


def run_one(run_dir: Path, prefix: str, sibling_prop: Path | None = None) -> dict:
    solver = run_dir / "solver"
    qa = run_dir / "qa"
    qa.mkdir(exist_ok=True)
    props = load_properties(solver / f"{prefix}_modal_properties.csv")
    if sibling_prop:
        attach_sibling_pfact(props, sibling_prop)
    sene = load_sene(solver / f"{prefix}_section_modal_sene.csv")
    groups = load_groups(solver / f"{prefix}_modal_sene_groups.csv")
    probes = load_probes(solver / f"{prefix}_mode_probes.csv")
    classified = []
    for prop in props:
        m = prop["mode"]
        info = classify(prop, sene.get(m), groups.get(m), probes.get(m))
        rec = {"mode": m, "freq": prop["freq"], "genm": prop["genm"], **info}
        classified.append(rec)
    pairs = pair_table41(classified)
    cls_csv = qa / f"{prefix}_mode_classification.csv"
    with cls_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "mode", "freq", "family", "symmetry", "order_hint", "local_gate",
                "share_L", "share_V", "share_T", "side_ratio", "r_gate", "r_toppost",
                "r_cable_t4", "effm_x", "effm_y", "effm_z", "effm_rx", "effm_ry", "effm_rz",
            ],
        )
        w.writeheader()
        for rec in classified:
            w.writerow({k: rec.get(k) for k in w.fieldnames})
    pair_csv = qa / f"{prefix}_table41_pairing.csv"
    with pair_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["label", "desc", "mode", "f_fem", "f_ref", "rel_err", "order_hint", "basis"],
        )
        w.writeheader()
        for rec in pairs:
            w.writerow(rec)
    md = qa / f"{prefix}_table41_pairing.md"
    lines = [
        f"# {prefix.upper()} 与附件2-3表4-1物理模态配对",
        "",
        "配对依据振型物理特征（有效质量方向、两幅猫道同/反相、主跨正/反对称、SENE 组件占比），",
        "禁止仅按频率阶次硬配。门架上端释放 ROTX 产生的平面内局部模态单独列出，不进入表4-1。",
        "",
        "| 表4-1 | 说明 | 实测 Hz | FEM 阶 | FEM Hz | 偏差 | 配对依据 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for rec in pairs:
        mode = rec["mode"] if rec["mode"] is not None else "—"
        ff = f"{rec['f_fem']:.6f}" if rec["f_fem"] is not None else "—"
        re = f"{100*rec['rel_err']:+.2f}%" if rec["rel_err"] is not None else "—"
        lines.append(
            f"| {rec['label']} | {rec['desc']} | {rec['f_ref']:.4f} | {mode} | {ff} | {re} | {rec['basis']} |"
        )
    locals_ = [r for r in classified if r["local_gate"]]
    lines += ["", "## 排除的门架 ROTX 局部模态", ""]
    if not locals_:
        lines.append("未检出门架平面内局部主导模态（GATE_TOPPOST SENE 占比均低于阈值）。")
    else:
        lines.append("| 阶 | Hz | toppost SENE | cable SENE | 说明 |")
        lines.append("|---:|---:|---:|---:|---|")
        for r in locals_:
            lines.append(
                f"| {r['mode']} | {r['freq']:.6f} | {r['r_toppost']:.3f} | {r['r_cable_t4']:.3f} | LOCAL_GATE_ROTX |"
            )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "run_dir": str(run_dir),
        "n_classified": len(classified),
        "n_paired": sum(1 for p in pairs if p["mode"] is not None),
        "n_local_gate": len(locals_),
        "pairs": pairs,
    }
    (qa / f"{prefix}_table41_pairing.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def main() -> None:
    sibling = (
        ROOT
        / "ultra_runs"
        / "S10_SECTION_SHEAR_20260716T050342389124Z"
        / "solver"
        / "s10_modal_properties.csv"
    )
    jobs = [
        (
            ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z",
            "c20",
        ),
        (
            ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z",
            "d10",
        ),
    ]
    summary = []
    for run, prefix in jobs:
        prop = run / "solver" / f"{prefix}_modal_properties.csv"
        probes = run / "solver" / f"{prefix}_mode_probes.csv"
        if not prop.exists() or not probes.exists():
            summary.append({"prefix": prefix, "skipped": True, "reason": "POST1 artifacts missing"})
            continue
        result = run_one(run, prefix, sibling_prop=sibling)
        summary.append(
            {
                "prefix": prefix,
                "paired": result["n_paired"],
                "local": result["n_local_gate"],
            }
        )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
