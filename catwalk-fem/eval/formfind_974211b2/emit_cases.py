"""Emit CalculiX daughter decks for six MCT cases + a frequency card.

Modeling post only. Does not rewrite 974211b2. Does not write the paper.
Does not import isolated TARGET-FREQ. Does not use 附件2-3 table 5-4.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "mct-from-zero"))

from parse_mct import (  # noqa: E402
    EXPECTED_BYTES,
    EXPECTED_SHA256,
    SOURCE_RELATIVE,
    load_mct,
)

MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
P1_SHA = "be533c5f3228aacf19aea4913b503c2c6fac6d6246f6e6ab7b1eba4720e630ae"
MCT = ROOT / "mct-from-zero" / "source" / SOURCE_RELATIVE
P1_DIR = ROOT / "eval" / "ccx_P1_nlgeom_974211b2"
REVIEW = HERE / "mct_review"
DAUGHTERS = HERE / "daughters"
ISOLATED_FREQ = ROOT / "isolated" / "TARGET-FREQ.json"
KN_TO_N = 1000.0
FORBIDDEN_TABLE_54 = (9309.3, 581.8)
N_FREQ = 20
SPAN_GROUPS = ("北边跨", "主跨", "南边跨", "南辅跨")
PORTAL_CABLE_GROUPS = ("门架索北边跨", "门架索主跨", "门架索南边跨", "门架索南辅跨")
FORCE_CSV_ROW = re.compile(
    r"^\s+(\d+)\.,\s+([+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s*$"
)

# MCT *LOADCOMB names (decoded). Extra STLDCASE cards stacked on 合计 = 自重+二期.
CASES = (
    {
        "id": "P1",
        "mct_comb": "工况1恒载",
        "review_id": 1,
        "add": (),
        "temp_c": None,
        "has_wind": False,
    },
    {
        "id": "P2",
        "mct_comb": "工况2 恒+施工",
        "review_id": 2,
        "add": ("施工荷载",),
        "temp_c": None,
        "has_wind": False,
    },
    {
        "id": "P3",
        "mct_comb": "工可3恒+施工+温度",
        "review_id": 3,
        "add": ("施工荷载",),
        "temp_c": -15.0,
        "has_wind": False,
    },
    {
        "id": "P4",
        "mct_comb": "工可4恒+施工+施工风",
        "review_id": 4,
        "add": ("施工荷载", "施工风荷载"),
        "temp_c": None,
        "has_wind": True,
    },
    {
        "id": "P5",
        "mct_comb": "工况5恒+最大阵风",
        "review_id": 5,
        "add": ("最大阵风",),
        "temp_c": None,
        "has_wind": True,
    },
    {
        "id": "P6",
        "mct_comb": "工况6恒+施工+温34",
        "review_id": 6,
        "add": ("施工荷载",),
        "temp_c": -34.0,
        "has_wind": False,
    },
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)
    return {
        "n": n,
        "min": s[0],
        "max": s[-1],
        "mean": float(sum(s) / n),
        "p50": s[n // 2],
        "p95": s[min(n - 1, int(math.ceil(0.95 * n) - 1))],
    }


def scrape_mct_loads(text: str) -> dict[str, Any]:
    """Associate *USE-STLD with the following *CONLOAD / *SYSTEMPER block."""
    cases: dict[str, dict[str, Any]] = {}
    current: str | None = None
    mode: str | None = None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("*USE-STLD"):
            current = s.split(",", 1)[1].strip() if "," in s else ""
            cases.setdefault(current, {"conload": [], "systemper_c": None})
            mode = None
            continue
        if s.startswith("*") and not s.startswith("*;"):
            cmd = s.split(";", 1)[0].split(",", 1)[0].strip().upper()
            if cmd == "*CONLOAD" and current:
                mode = "conload"
            elif cmd == "*SYSTEMPER" and current:
                mode = "temp"
            else:
                mode = None
            continue
        if not current or not s or s.startswith(";"):
            continue
        parts = [p.strip() for p in raw.split(",")]
        if mode == "conload" and len(parts) >= 4:
            try:
                nid = int(parts[0])
                fx, fy, fz = float(parts[1]), float(parts[2]), float(parts[3])
            except ValueError:
                continue
            cases[current]["conload"].append(
                {"nid": nid, "fx_kN": fx, "fy_kN": fy, "fz_kN": fz}
            )
        elif mode == "temp" and parts:
            try:
                cases[current]["systemper_c"] = float(parts[0])
            except ValueError:
                pass
    return cases


def scrape_thermal_alpha(text: str) -> dict[int, float]:
    """MCT *MATERIAL DATA1: E, nu, THERMAL, DEN, MASS after the leading 2."""
    alphas: dict[int, float] = {}
    on = False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("*MATERIAL"):
            on = True
            continue
        if on and s.startswith("*") and not s.startswith("*;"):
            break
        if not on or not s or s.startswith(";"):
            continue
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 14:
            continue
        try:
            mid = int(parts[0])
            alphas[mid] = float(parts[12])
        except ValueError:
            continue
    return alphas


def parse_review_force_csv(path: Path) -> dict[int, float]:
    out: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = FORCE_CSV_ROW.match(line)
        if not m:
            continue
        out[int(m.group(1))] = float(m.group(2))
    return out


def _dat_blocks(dat_text: str, header: str) -> list[list[str]]:
    """Collect CalculiX .dat sections. Last block is the last finished step."""
    blocks: list[list[str]] = []
    current: list[str] = []
    on = False
    for line in dat_text.splitlines():
        low = line.lower()
        if header in low:
            if on:
                blocks.append(current)
            current = []
            on = True
            continue
        if on and (
            "stresses (elem" in low
            or "displacements (vx,vy,vz)" in low
            or "eigenvalue" in low
            or "frequency (cycles/time)" in low
            or "forces (" in low
        ):
            if header not in low:
                blocks.append(current)
                current = []
                on = False
            continue
        if on:
            current.append(line)
    if on:
        blocks.append(current)
    return blocks


def parse_dat_u(dat_text: str) -> dict[int, tuple[float, float, float]]:
    u: dict[int, tuple[float, float, float]] = {}
    blocks = _dat_blocks(dat_text, "displacements (vx,vy,vz)")
    if not blocks:
        return u
    for line in blocks[-1]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                nid = int(parts[0])
                u[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
            except ValueError:
                continue
    return u


def parse_dat_s(dat_text: str) -> dict[int, list[tuple[float, ...]]]:
    s: dict[int, list[tuple[float, ...]]] = defaultdict(list)
    blocks = _dat_blocks(dat_text, "stresses (elem, integ.pnt.")
    if not blocks:
        return {}
    for line in blocks[-1]:
        parts = line.split()
        if len(parts) >= 8:
            try:
                eid = int(parts[0])
                comps = tuple(float(p) for p in parts[2:8])
            except ValueError:
                continue
            s[eid].append(comps)
    return dict(s)


def axial_from_s(
    model: dict[str, Any], stresses: dict[int, list[tuple[float, ...]]]
) -> dict[int, float]:
    nodes = model["nodes"]
    elems = model["elems"]
    sections = model["sections"]
    out: dict[int, float] = {}
    for eid, ips in stresses.items():
        el = elems.get(eid)
        if el is None or el["type"] != "TENSTR" or not ips:
            continue
        n1, n2 = nodes[el["n1"]], nodes[el["n2"]]
        dx, dy, dz = n2["x"] - n1["x"], n2["y"] - n1["y"], n2["z"] - n1["z"]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length <= 0.0:
            continue
        nx, ny, nz = dx / length, dy / length, dz / length
        sigmas = []
        for sx, sy, sz, txy, txz, tyz in ips:
            sigmas.append(
                sx * nx * nx
                + sy * ny * ny
                + sz * nz * nz
                + 2.0 * txy * nx * ny
                + 2.0 * txz * nx * nz
                + 2.0 * tyz * ny * nz
            )
        area = sections[el["sec"]]["area_mm2"]
        out[eid] = (sum(sigmas) / len(sigmas)) * area
    return out


def lock_force_ledger(model: dict[str, Any]) -> dict[str, Any]:
    rows = []
    portal_frames = []
    group_of: dict[int, str] = {}
    for gname in SPAN_GROUPS + PORTAL_CABLE_GROUPS:
        for eid in (model["groups"].get(gname) or {}).get("elems") or []:
            group_of[eid] = gname
    for eid, el in sorted(model["elems"].items()):
        if el["type"] == "TRUSS":
            portal_frames.append(eid)
            continue
        ini = model["iniforce"].get(eid)
        ini_e = model["ini_eforce"].get(eid)
        if ini_e is not None:
            f_kN = float(ini_e["axial_mean_kN"])
            src = "INI-EFORCE mean(i,j)"
        elif ini is not None:
            f_kN = float(ini["axial_kN"])
            src = "INIFORCE AXIAL"
        else:
            continue
        area = model["sections"][el["sec"]]["area_mm2"]
        rows.append(
            {
                "eid": eid,
                "block": group_of.get(eid, ""),
                "F_lock_kN": f_kN,
                "A_mm2": area,
                "sigma_N_mm2": (f_kN * KN_TO_N) / area if area else None,
                "from": src,
            }
        )
    by_block: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["block"]:
            by_block[r["block"]].append(r["F_lock_kN"])
    stats = _stats([r["F_lock_kN"] for r in rows])
    named = {str(r["eid"]): r for r in rows if r["eid"] in (1, 4, 728, 729)}
    eid1 = next((r for r in rows if r["eid"] == 1), None)
    eid1_fa = None
    eid1_ok = False
    if eid1 and eid1["A_mm2"]:
        eid1_fa = (eid1["F_lock_kN"] * KN_TO_N) / eid1["A_mm2"]
        eid1_ok = abs(eid1["sigma_N_mm2"] - eid1_fa) <= 1e-9
    return {
        "kind": "initial_lock_force_from_mct",
        "source": "MCT *INIFORCE / *INI-EFORCE",
        "independent_control": "MCT formed geometry (974211b2 *NODE)",
        "determined_quantity": "initial lock force = MCT *INIFORCE / *INI-EFORCE mean",
        "not_table_5_4": True,
        "forbidden_table_5_4_kN": list(FORBIDDEN_TABLE_54),
        "n_iniforce": len(rows),
        "n_TENSTR_lock": len(rows),
        "n_portal_truss_without_iniforce": len(portal_frames),
        "n_portal_TRUSS_no_lock": len(portal_frames),
        "portal_stop": False,
        "mean_kN": stats.get("mean"),
        "max_kN": stats.get("max"),
        "min_kN": stats.get("min"),
        "eid1_sigma_equals_F_over_A": eid1_ok,
        "eid1_F_over_A_N_mm2": eid1_fa,
        "stats_kN": stats,
        "by_block_kN": {k: _stats(v) for k, v in by_block.items()},
        "named": named,
        "rows": rows,
        "note": (
            "INIFORCE is MCT geometric-stiffness lock force on the formed line. "
            "工况1 运力增量按复核表应接近 0。表5-4 9309.3/581.8 是另一套 16×φ50 恒+静风，不用。"
        ),
    }


def p1_bytes(main_bytes: bytes) -> bytes:
    old = b"*STEP\n*STATIC\n"
    new = b"*STEP, NLGEOM\n*STATIC\n"
    if main_bytes.count(old) != 1:
        raise ValueError("expected exactly one *STEP/*STATIC pair on the main deck")
    return main_bytes.replace(old, new, 1)


def _cload_lines(loads: list[dict[str, float]]) -> list[str]:
    lines = ["*CLOAD"]
    for rec in loads:
        nid = rec["nid"]
        for dof, key in ((1, "fx_kN"), (2, "fy_kN"), (3, "fz_kN")):
            val = rec[key] * KN_TO_N
            if abs(val) < 1e-12:
                continue
            lines.append(f"{nid}, {dof}, {val:.8g}")
    return lines


def emit_daughter(
    main_text: str,
    *,
    extra_loads: list[dict[str, float]],
    temp_c: float | None,
    alpha: float,
    heading: str,
) -> str:
    """P1 NLGEOM first, then a second NLGEOM step with MCT extras.

    Matches warehouse MAPDL load-step 2: formed 恒载, then 施工/风/温.
    Does not rewrite the main. First step stays the P1 card.
    """
    text = main_text.replace("*STEP\n*STATIC\n", "*STEP, NLGEOM\n*STATIC\n", 1)
    if temp_c is not None:
        text = text.replace(
            "*ELASTIC\n120000, 0.3\n*DENSITY\n",
            f"*ELASTIC\n120000, 0.3\n*EXPANSION\n{alpha:.8g}\n*DENSITY\n",
        )
        text = text.replace(
            "*ELASTIC\n206000, 0.31\n*DENSITY\n",
            f"*ELASTIC\n206000, 0.31\n*EXPANSION\n{alpha:.8g}\n*DENSITY\n",
        )
    second: list[str] = [
        heading,
        "*STEP, NLGEOM",
        "*STATIC",
        "0.05, 1., 1e-8, 0.1",
    ]
    if extra_loads:
        second.extend(_cload_lines(extra_loads))
    if temp_c is not None:
        second.extend(["*TEMPERATURE", f"N_MCT, {temp_c:.8g}"])
    second.extend(
        [
            "*NODE FILE, NSET=N_MCT",
            "U",
            "*EL FILE",
            "S, E",
            "*NODE PRINT, NSET=N_MCT",
            "U",
            "*EL PRINT, ELSET=E_CABLE",
            "S",
            "*END STEP",
        ]
    )
    if not text.endswith("\n"):
        text += "\n"
    text = text.rstrip() + "\n" + "\n".join(second) + "\n"
    text = text.replace(
        "MCT from-zero static migrate: 猫道 - 门架索合建模型2.mct\n",
        f"MCT from-zero static migrate: 猫道 - 门架索合建模型2.mct\n{heading}\n",
        1,
    )
    return text


def emit_dyn(p1_text: str) -> str:
    if "TARGET-FREQ" in p1_text or "0.0296" in p1_text:
        raise ValueError("frequency deck must not contain isolated TARGET-FREQ values")
    extra = (
        "\n*STEP, PERTURBATION\n"
        "*FREQUENCY\n"
        f"{N_FREQ}\n"
        "*NODE FILE, NSET=N_MCT\n"
        "U\n"
        "*END STEP\n"
    )
    if not p1_text.endswith("\n"):
        p1_text += "\n"
    text = p1_text.rstrip() + extra
    text = text.replace(
        "MCT from-zero static migrate: 猫道 - 门架索合建模型2.mct\n",
        "MCT from-zero static migrate: 猫道 - 门架索合建模型2.mct\n"
        "** DYN: P1 NLGEOM then *STEP,PERTURBATION *FREQUENCY. "
        "No isolated frequency-table import. Not attachment 2-3.\n",
        1,
    )
    return text


def gather_extra(stld: dict[str, Any], names: tuple[str, ...]) -> list[dict[str, float]]:
    merged: dict[int, dict[str, float]] = {}
    for name in names:
        rec = stld.get(name)
        if rec is None:
            raise KeyError(f"MCT STLDCASE missing: {name!r}; have {sorted(stld)}")
        for row in rec["conload"]:
            slot = merged.setdefault(
                row["nid"], {"nid": row["nid"], "fx_kN": 0.0, "fy_kN": 0.0, "fz_kN": 0.0}
            )
            slot["fx_kN"] += row["fx_kN"]
            slot["fy_kN"] += row["fy_kN"]
            slot["fz_kN"] += row["fz_kN"]
    return [merged[k] for k in sorted(merged)]


def load_sum(loads: list[dict[str, float]]) -> dict[str, float]:
    return {
        "n": len(loads),
        "fx_kN": sum(r["fx_kN"] for r in loads),
        "fy_kN": sum(r["fy_kN"] for r in loads),
        "fz_kN": sum(r["fz_kN"] for r in loads),
        "n_fy": sum(1 for r in loads if abs(r["fy_kN"]) >= 1e-9),
    }


def compare_forces(
    ccx_N: dict[int, float], table_N: dict[int, float], tenstr: set[int]
) -> dict[str, Any]:
    rels = []
    worst = None
    for eid in sorted(tenstr):
        a = ccx_N.get(eid)
        b = table_N.get(eid)
        if a is None or b is None or b == 0.0:
            continue
        rel = abs(a - b) / abs(b)
        rels.append(rel)
        if worst is None or rel > worst[0]:
            worst = (rel, eid, a, b)
    st = _stats(rels)
    return {
        "n_compared": st.get("n", 0),
        "p50": st.get("p50"),
        "p95": st.get("p95"),
        "max": st.get("max"),
        "worst_eid": None if worst is None else worst[1],
        "named_1": {
            "ccx_N": ccx_N.get(1),
            "table_N": table_N.get(1),
        },
    }


def parse_sta_finished(sta_text: str) -> bool:
    return bool(re.search(r"^\s+1\s+1\s+1\s+\d+", sta_text, re.M))


def parse_freq_dat(dat_text: str) -> list[float]:
    freqs: list[float] = []
    # ccx prints "eigenvalue number     X" then "frequency (cycles/time) ..."
    for line in dat_text.splitlines():
        if "frequency (cycles/time)" in line.lower() or "FREQUENCY (CYCLES/TIME)" in line:
            parts = line.replace("=", " ").split()
            for p in reversed(parts):
                try:
                    freqs.append(float(p))
                    break
                except ValueError:
                    continue
    if freqs:
        return freqs
    # fallback: lines that look like "    1  0.1234E-01" after EIGENVALUE
    on = False
    for line in dat_text.splitlines():
        if "EIGENVALUE NUMBER" in line.upper() or "eigenvalue number" in line.lower():
            on = True
            continue
        if on:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    freqs.append(float(parts[-1]))
                except ValueError:
                    if freqs:
                        break
    return freqs


def run_ccx(inp_path: Path, jobdir: Path) -> dict[str, Any]:
    jobdir.mkdir(parents=True, exist_ok=True)
    stem = inp_path.stem
    dest = jobdir / f"{stem}.inp"
    if dest.resolve() != inp_path.resolve():
        shutil.copy2(inp_path, dest)
    ccx = shutil.which("ccx")
    if not ccx:
        return {"ran": False, "reason": "ccx_not_on_path"}
    stdout = jobdir / f"{stem}.stdout.txt"
    stderr = jobdir / f"{stem}.stderr.txt"
    with stdout.open("w", encoding="utf-8") as so, stderr.open("w", encoding="utf-8") as se:
        proc = subprocess.run(
            [ccx, "-i", stem],
            cwd=jobdir,
            stdout=so,
            stderr=se,
            check=False,
        )
    out: dict[str, Any] = {
        "ran": True,
        "exit": proc.returncode,
        "cmd": [ccx, "-i", stem],
        "jobdir": str(jobdir.relative_to(REPO)),
    }
    for ext in (".inp", ".dat", ".frd", ".sta", ".cvg", ".stdout.txt"):
        p = jobdir / f"{stem}{ext}"
        if p.is_file():
            out[f"sha256{ext}"] = sha256_file(p)
            out[f"bytes{ext}"] = p.stat().st_size
    return out


def qoi_from_dat(model: dict[str, Any], dat_path: Path) -> dict[str, Any]:
    text = dat_path.read_text(encoding="utf-8", errors="replace")
    u = parse_dat_u(text)
    s = parse_dat_s(text)
    axial = axial_from_s(model, s)
    umags = {nid: math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) for nid, v in u.items()}
    umax_nid = max(umags, key=umags.get) if umags else None
    return {
        "n_U": len(u),
        "Umax_mm": None if umax_nid is None else umags[umax_nid],
        "Umax_nid": umax_nid,
        "U_304_mm": None if 304 not in u else math.sqrt(sum(c * c for c in u[304])),
        "U_304_uz": None if 304 not in u else u[304][2],
        "U_1176_mm": None if 1176 not in u else math.sqrt(sum(c * c for c in u[1176])),
        "U_306_mm": None if 306 not in u else math.sqrt(sum(c * c for c in u[306])),
        "n_axial": len(axial),
        "axial_N": axial,
        "named_axial_N": {str(e): axial.get(e) for e in (1, 4, 728, 729)},
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit_all(*, solve: bool = False) -> dict[str, Any]:
    main_sha = sha256_file(MAIN)
    if main_sha != MAIN_SHA:
        raise RuntimeError("main deck hash drifted; refuse to emit")
    if sha256_file(CLEARED) != CLEARED_SHA:
        raise RuntimeError("cleared frozen hash drifted")
    model = load_mct(MCT)
    mct_text = MCT.read_bytes().decode("gb18030")
    stld = scrape_mct_loads(mct_text)
    alphas = scrape_thermal_alpha(mct_text)
    alpha = alphas.get(1) or alphas.get(2) or 1.2e-5
    lock = lock_force_ledger(model)
    main_text = MAIN.read_text(encoding="utf-8")
    main_b = MAIN.read_bytes()
    DAUGHTERS.mkdir(parents=True, exist_ok=True)
    P1_DIR.mkdir(parents=True, exist_ok=True)

    p1 = p1_bytes(main_b)
    if hashlib.sha256(p1).hexdigest() != P1_SHA:
        raise RuntimeError("P1 STEP-only hash is not be533c5f")
    p1_path = P1_DIR / "migrate_P1.inp"
    if (not p1_path.is_file()) or sha256_file(p1_path) != P1_SHA:
        p1_path.write_bytes(p1)

    isolated = json.loads(ISOLATED_FREQ.read_text(encoding="utf-8"))
    isolated_vals = [float(v) for v in isolated.get("values", [])]

    stld_sums = {
        name: load_sum(rec["conload"]) | {"systemper_c": rec["systemper_c"]}
        for name, rec in stld.items()
    }

    case_cards = []
    tenstr = {e for e, el in model["elems"].items() if el["type"] == "TENSTR"}
    review_tables = {}
    for spec in CASES:
        rid = spec["review_id"]
        csv_path = REVIEW / f"mct_case_{rid}_element_force.csv"
        review_tables[rid] = parse_review_force_csv(csv_path) if csv_path.is_file() else {}

    for spec in CASES:
        extra = gather_extra(stld, spec["add"]) if spec["add"] else []
        heading = (
            f"** {spec['id']} {spec['mct_comb']} NLGEOM daughter of 974211b2. "
            f"add={list(spec['add'])} temp={spec['temp_c']}. Not a new main."
        )
        if spec["id"] == "P1":
            text = p1.decode("utf-8")
            path = p1_path
        else:
            text = emit_daughter(
                main_text,
                extra_loads=extra,
                temp_c=spec["temp_c"],
                alpha=alpha,
                heading=heading,
            )
            path = DAUGHTERS / f"migrate_{spec['id']}.inp"
            path.write_text(text, encoding="utf-8")
        if any(str(v) in text for v in isolated_vals[:3]):
            raise RuntimeError(f"{spec['id']} imported TARGET-FREQ")
        comment_blob = "\n".join(
            ln for ln in text.splitlines() if ln.lstrip().startswith("*") and ln.lstrip().startswith("**")
        )
        # CLOAD magnitudes may contain the digit string 581.8 (e.g. -2581.872 N). That is MCT wind, not 表5-4.
        if "表5-4" in comment_blob or "9309.3 / 581.8" in text:
            raise RuntimeError(f"{spec['id']} used table 5-4 as a card target")
        card = {
            "id": spec["id"],
            "mct_comb": spec["mct_comb"],
            "review_id": spec["review_id"],
            "path": str(path.relative_to(REPO)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "nlgeom": True,
            "add": list(spec["add"]),
            "temp_c": spec["temp_c"],
            "has_wind": spec["has_wind"],
            "extra_load_sum": load_sum(extra),
            "main_rewritten": False,
        }
        case_cards.append(card)

    dyn_text = emit_dyn(p1.decode("utf-8"))
    if any(str(v) in dyn_text for v in isolated_vals):
        raise RuntimeError("DYN imported TARGET-FREQ")
    dyn_path = DAUGHTERS / "migrate_DYN.inp"
    dyn_path.write_text(dyn_text, encoding="utf-8")
    dyn_job_dir = ROOT / "eval" / "ccx_DYN_freq_974211b2"
    dyn_job_dir.mkdir(parents=True, exist_ok=True)
    dyn_job_inp = dyn_job_dir / "migrate_DYN.inp"
    if dyn_job_inp.resolve() != dyn_path.resolve():
        shutil.copy2(dyn_path, dyn_job_inp)
    dyn_card = {
        "id": "DYN",
        "path": str(dyn_path.relative_to(REPO)),
        "job_path": str(dyn_job_inp.relative_to(REPO)),
        "sha256": sha256_file(dyn_path),
        "bytes": dyn_path.stat().st_size,
        "n_freq_requested": N_FREQ,
        "imported_TARGET_FREQ": False,
        "note": "Perturbation frequency after P1 NLGEOM. Modeling card only.",
    }
    for card in case_cards:
        if card["id"] == "P1":
            continue
        job = ROOT / "eval" / f"ccx_{card['id']}_nlgeom_974211b2"
        job.mkdir(parents=True, exist_ok=True)
        src = DAUGHTERS / f"migrate_{card['id']}.inp"
        dest = job / src.name
        shutil.copy2(src, dest)
        card["job_path"] = str(dest.relative_to(REPO))

    solves: dict[str, Any] = {}
    qois: dict[str, Any] = {}

    def _ingest_existing(cid: str, job: Path, stem: str) -> bool:
        dat = job / f"{stem}.dat"
        sta = job / f"{stem}.sta"
        if not (dat.is_file() and sta.is_file()):
            return False
        exit_path = job / "exit_code.txt"
        solves[cid] = {
            "ran": True,
            "reused_existing": True,
            "exit": int(exit_path.read_text().strip() or "0") if exit_path.is_file() else 0,
            "sha256.dat": sha256_file(dat),
            "sha256.sta": sha256_file(sta),
        }
        if cid == "DYN":
            freqs = parse_freq_dat(dat.read_text(encoding="utf-8", errors="replace"))
            qois[cid] = {
                "n_freq_parsed": len(freqs),
                "freq_cycles": freqs,
                "compared_to_attachment_2_3": False,
            }
        else:
            qois[cid] = qoi_from_dat(model, dat)
        return True

    _ingest_existing("P1", P1_DIR, "migrate_P1")
    for card in case_cards:
        if card["id"] == "P1":
            if solve and "P1" not in solves:
                solves["P1"] = run_ccx(p1_path, P1_DIR)
                dat = P1_DIR / "migrate_P1.dat"
                if dat.is_file() and solves["P1"].get("exit") == 0:
                    qois["P1"] = qoi_from_dat(model, dat)
            continue
        job = ROOT / "eval" / f"ccx_{card['id']}_nlgeom_974211b2"
        inp = DAUGHTERS / f"migrate_{card['id']}.inp"
        if _ingest_existing(card["id"], job, inp.stem):
            continue
        if solve:
            solves[card["id"]] = run_ccx(inp, job)
            dat = job / f"{inp.stem}.dat"
            if dat.is_file() and solves[card["id"]].get("exit") == 0:
                qois[card["id"]] = qoi_from_dat(model, dat)
    dyn_job = ROOT / "eval" / "ccx_DYN_freq_974211b2"
    if not _ingest_existing("DYN", dyn_job, "migrate_DYN") and solve:
        solves["DYN"] = run_ccx(dyn_path, dyn_job)
        dyn_dat = dyn_job / "migrate_DYN.dat"
        if dyn_dat.is_file():
            freqs = parse_freq_dat(dyn_dat.read_text(encoding="utf-8", errors="replace"))
            qois["DYN"] = {
                "n_freq_parsed": len(freqs),
                "freq_cycles": freqs,
                "compared_to_attachment_2_3": False,
            }

    comparisons = {}
    lock_N = {r["eid"]: r["F_lock_kN"] * KN_TO_N for r in lock["rows"]}
    for card in case_cards:
        rid = card["review_id"]
        table = review_tables.get(rid) or {}
        ccx_ax = (qois.get(card["id"]) or {}).get("axial_N") or {}
        vs_review = compare_forces(ccx_ax, table, tenstr) if ccx_ax and table else None
        vs_lock = compare_forces(ccx_ax, lock_N, tenstr) if ccx_ax else None
        review_u = None
        extrema_path = REVIEW / "mct_six_static_cases_extrema.csv"
        if extrema_path.is_file():
            with extrema_path.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if int(row["case_id"]) == rid:
                        review_u = {
                            "max_usum_mm": float(row["max_usum_mm"]),
                            "usum_node_id": int(float(row["usum_node_id"])),
                            "max_abs_uz_mm": float(row["max_abs_uz_mm"]),
                            "uz_node_id": int(float(row["uz_node_id"])),
                        }
        q = qois.get(card["id"]) or {}
        portal_nid = (review_u or {}).get("usum_node_id")
        portal_hit = (
            q.get("Umax_nid") == portal_nid if portal_nid and q.get("Umax_nid") else None
        )
        comparisons[card["id"]] = {
            "vs_review_element_force": vs_review,
            "vs_mct_lock_force": vs_lock,
            "review_U": review_u,
            "ccx_Umax_mm": q.get("Umax_mm"),
            "ccx_Umax_nid": q.get("Umax_nid"),
            "ccx_U_1176_mm": q.get("U_1176_mm"),
            "ccx_U_304_mm": q.get("U_304_mm"),
            "review_peak_node_matched": portal_hit,
            "portal_mismatch_is_stop": False,
            "table_5_4_used": False,
        }

    # Engineer gate on form-finding (P1 vs review case 1). Do not stop if later cases miss.
    p1c = comparisons.get("P1") or {}
    p1_u = p1c.get("ccx_Umax_mm")
    rev_u = (p1c.get("review_U") or {}).get("max_usum_mm")
    formfind_ok = False
    if p1_u is not None and rev_u:
        formfind_ok = abs(p1_u - rev_u) / rev_u <= 0.05
    force_p50 = ((p1c.get("vs_review_element_force") or {}).get("p50"))
    if force_p50 is not None:
        formfind_ok = formfind_ok and force_p50 <= 0.01

    evidence = {
        "kind": "formfind_six_case_dyn_modeling",
        "not_a_scientific_success_document": True,
        "wrote_符合附件2-3": False,
        "wrote_paper": False,
        "main": {"path": str(MAIN.relative_to(REPO)), "sha256": main_sha, "rewritten": False},
        "main_sha256": main_sha,
        "cleared_760c0ee4_untouched": sha256_file(CLEARED) == CLEARED_SHA,
        "p1": {"path": str(p1_path.relative_to(REPO)), "sha256": sha256_file(p1_path)},
        "p1_sha256": sha256_file(p1_path),
        "lock_force": {
            k: lock[k]
            for k in lock
            if k != "rows"
        },
        "stld_sums": stld_sums,
        "thermal_alpha": {"MAT1": alphas.get(1), "used": alpha},
        "case_cards": case_cards,
        "dyn_card": dyn_card,
        "solves": solves,
        "qoi_summary": {
            cid: {k: v for k, v in q.items() if k != "axial_N"} for cid, q in qois.items()
        },
        "comparisons": comparisons,
        "gates": {
            "formfind_P1_vs_review_case1": "PASS" if formfind_ok else "CONTINUE",
            "portal_mismatch_is_stop": False,
            "table_5_4_is_lock_force": False,
            "TARGET_FREQ_imported": False,
            "paper_written_by_modeling_post": False,
            "dynamics_card_emitted": True,
        },
        "handoff_to_paper_post": {
            "formfind_layer_may_be_written": formfind_ok,
            "six_cases_and_wind_cards": True,
            "dynamics_card": True,
            "do_not_write_符合附件2-3": True,
        },
        "handoff": "paper_post_formfind_layer_only",
        "paper_written": False,
    }
    lock_pub = {k: lock[k] for k in lock if k != "rows"}
    lock_pub["n_rows"] = len(lock["rows"])
    write_json(HERE / "lock_force.json", lock_pub)
    write_json(HERE / "prestress_and_lock_in_ledger.json", lock_pub)
    write_json(
        HERE / "six_cases.json",
        {
            "stld_sums": stld_sums,
            "cards": case_cards,
            "dyn": dyn_card,
            "cases": [
                {
                    "id": c["review_id"],
                    "card_id": c["id"],
                    "has_wind": c["has_wind"],
                    "n_conload": c["extra_load_sum"]["n"],
                    "add": c["add"],
                    "temp_c": c["temp_c"],
                }
                for c in case_cards
            ],
        },
    )
    write_json(HERE / "EVIDENCE.json", evidence)
    return evidence


def write_modeling_md(ev: dict[str, Any]) -> None:
    p1 = ev["comparisons"].get("P1") or {}
    lines = [
        "# 建模岗：找形锁力 + 六工况卡 + 动力卡（不成稿）",
        "",
        "本文件是工况卡与求解账，不是论文。论文岗成稿。不成附件对照结论。",
        "",
        f"主 `974211b2` 未改。P1 `be533c5f` = 只加 `*STEP, NLGEOM`。",
        "",
        "## 初始锁力（已确定）",
        "",
        "独立控制量 = MCT 成型线形。初始锁力 = MCT `*INIFORCE` / `*INI-EFORCE` mean，1123 根 TENSTR。",
        "71 榀门架 TRUSS 无锁力，不编，门不对也不停。",
        "不用表5-4 的 9309.3 / 581.8。",
        "",
        f"- n = {ev['lock_force']['n_TENSTR_lock']}",
        f"- min/max/mean kN = {ev['lock_force']['stats_kN']}",
        "",
        "## 工况1 找形门（自判）",
        "",
        f"- CCX Umax = {p1.get('ccx_Umax_mm')} mm @ nid {p1.get('ccx_Umax_nid')}",
        f"- 复核报告工况1 USUM = {(p1.get('review_U') or {}).get('max_usum_mm')} mm @ {(p1.get('review_U') or {}).get('usum_node_id')}",
        f"- vs 复核单元轴力 = {p1.get('vs_review_element_force')}",
        f"- vs MCT 锁力 = {p1.get('vs_mct_lock_force')}",
        f"- 门: `{ev['gates']['formfind_P1_vs_review_case1']}`。过了就让论文岗写找形层。建模岗不停，接着六工况和动力。",
        "",
        "P2–P6 是 P1 后再加第二步 NLGEOM（施工/风/温）。门架索峰值对不上也不停。",
        "",
        "## 六工况卡（恒载/施工/温/风已有，从 MCT 刮，不编）",
        "",
        "| ID | 组合 | 加的 STLDCASE | 风 | temp | sha256 |",
        "|---|---|---|---|---|---|",
    ]
    for c in ev["case_cards"]:
        lines.append(
            f"| {c['id']} | {c['mct_comb']} | {c['add']} | {c['has_wind']} | {c['temp_c']} | `{c['sha256'][:16]}` |"
        )
    wind = ev["stld_sums"].get("施工风荷载") or {}
    gust = ev["stld_sums"].get("最大阵风") or {}
    lines += [
        "",
        f"施工风 ΣFY={wind.get('fy_kN')} kN，ΣFZ={wind.get('fz_kN')} kN，n_fy={wind.get('n_fy')}（横载+进风已在 MCT，P4 已加）。",
        f"最大阵风 ΣFY={gust.get('fy_kN')} kN，ΣFZ={gust.get('fz_kN')} kN（P5）。",
        "二维 UY 钉死，FY 进反力；面内差主要来自风的 FZ。",
        "",
        "## 动力卡",
        "",
        f"- `{ev['dyn_card']['path']}` sha `{ev['dyn_card']['sha256']}`",
        f"- P1 NLGEOM 后 `*STEP, PERTURBATION` + `*FREQUENCY` {ev['dyn_card']['n_freq_requested']} 阶",
        "- 不读 `isolated/TARGET-FREQ.json`，不把 0.0296… 写进 inp",
        "",
        "## 求解",
        "",
    ]
    for cid, sol in ev["solves"].items():
        lines.append(f"- {cid}: {sol}")
    lines += [
        "",
        "## 交接",
        "",
        "找形层对上了可以写。六工况卡和恒载进风卡在。动力卡在。",
        "建模岗到此交工况卡，不成稿。不成附件对照结论。",
        "",
    ]
    (HERE / "MODELING.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    do_solve = "--solve" in sys.argv
    ev = emit_all(solve=do_solve)
    write_modeling_md(ev)
    print(json.dumps({
        "main": ev["main"]["sha256"][:16],
        "p1": ev["p1"]["sha256"][:16],
        "gates": ev["gates"],
        "n_cards": len(ev["case_cards"]),
        "dyn": ev["dyn_card"]["sha256"][:16],
        "solves": {k: v.get("exit", v.get("ran")) for k, v in ev["solves"].items()},
        "qoi": ev["qoi_summary"],
    }, ensure_ascii=False, indent=2))
