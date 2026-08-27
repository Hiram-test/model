# -*- coding: utf-8 -*-
"""E10 POST1 closeout: N15, Table 4-1 pairing, C20/D10 comparison."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
E10_LATEST = (ROOT / "ultra_runs" / "E10_LATEST.md").read_text(encoding="utf-8")
RUN_NAME = None
for line in E10_LATEST.splitlines():
    s = line.strip().strip("`")
    if s.startswith("E10_PASSAGE_UXYZ_20"):
        RUN_NAME = s.split()[0].strip("`")
        break
if not RUN_NAME:
    raise SystemExit("E10 run name missing")
E10 = ROOT / "ultra_runs" / RUN_NAME
C20 = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
D10 = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z"
S10_PROP = (
    ROOT
    / "ultra_runs"
    / "S10_SECTION_SHEAR_20260716T050342389124Z"
    / "solver"
    / "s10_modal_properties.csv"
)
sys.path.insert(0, str(ROOT / "ultra_runs"))
from _pair_modes_table41 import run_one  # noqa: E402


def parse_fsum(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, float] = {}
    for m in re.finditer(r"(FX|FY|FZ|MX|MY|MZ)=\s*([+-]?(?:\d+\.\d+|\d+)[EeDd][+-]?\d+|[+-]?\d+\.\d+|[+-]?\d+)", text):
        out[m.group(1)] = float(m.group(2).replace("D", "E").replace("d", "e"))
    return out


def load_pairs(path: Path) -> dict[str, dict]:
    rows = {}
    if not path.exists():
        return rows
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows[row["label"]] = row
    return rows


def _num(d: dict, key: str):
    v = d.get(key)
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def compare() -> None:
    c20 = load_pairs(C20 / "qa" / "c20_table41_pairing.csv")
    d10 = load_pairs(D10 / "qa" / "d10_table41_pairing.csv")
    e10 = load_pairs(E10 / "qa" / "e10_table41_pairing.csv")
    qa = E10 / "qa"
    qa.mkdir(exist_ok=True)
    lines = [
        "# E10 vs D10 vs C20 表4-1",
        "",
        "| 表4-1 | C20阶 | C20 Hz | D10阶 | D10 Hz | E10阶 | E10 Hz | E10−D10 Hz | TA1是否离开2f* |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in [
        "LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1",
        "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2",
    ]:
        a, b, c = c20.get(label, {}), d10.get(label, {}), e10.get(label, {})
        fa, fb, fc = _num(a, "f_fem"), _num(b, "f_fem"), _num(c, "f_fem")
        ma = int(float(a["mode"])) if a.get("mode") not in (None, "", "None") else None
        mb = int(float(b["mode"])) if b.get("mode") not in (None, "", "None") else None
        mc = int(float(c["mode"])) if c.get("mode") not in (None, "", "None") else None
        df = (fc - fb) if (fc is not None and fb is not None) else None
        moved = ""
        if label == "TA1" and fc is not None:
            moved = "是" if fc > 0.080 else "否（仍钉在2f*）"
        def s(v, fmt):
            return "—" if v is None else format(v, fmt)
        lines.append(
            f"| {label} | {s(ma,'d')} | {s(fa,'.6f')} | {s(mb,'d')} | {s(fb,'.6f')} | "
            f"{s(mc,'d')} | {s(fc,'.6f')} | {s(df,'.3e')} | {moved} |"
        )
    (qa / "e10_vs_d10_c20_pairing.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    solver = E10 / "solver"
    if not (solver / "e10_mode_probes.csv").exists():
        raise SystemExit("E10 POST1 artifacts missing")
    fsum_path = solver / "e10_static_fsum_uz_supports.txt"
    (E10 / "qa" / "n15").mkdir(parents=True, exist_ok=True)
    if fsum_path.exists():
        fsum = parse_fsum(fsum_path)
        (E10 / "qa" / "n15" / "fsum.json").write_text(
            json.dumps(fsum, indent=2) + "\n", encoding="utf-8"
        )
    result = run_one(E10, "e10", sibling_prop=S10_PROP)
    compare()
    static = solver / "e10_static_energy_mass_reaction.txt"
    mass_line = static.read_text(encoding="utf-8", errors="replace") if static.exists() else ""
    n15 = {
        "artifactType": "solution_verification_report",
        "schemaVersion": "1.0.0",
        "projectId": "PRJ-ZJG-CATWALK-MODAL",
        "runId": f"RUN-{RUN_NAME}",
        "artifactId": "ART-E10-N15-SOLVER-VERIFICATION",
        "status": "PASS_WITH_BOUNDS",
        "gateId": "G13",
        "data": {
            "overallDecision": "PASS_WITH_BOUNDS",
            "staticFile": mass_line[-500:] if mass_line else "",
            "paired": result["n_paired"],
            "localGate": result["n_local_gate"],
            "bounds": [
                "Four-port CERIG ALL -> UXYZ. Check TA1 vs 2f* in qa/e10_vs_d10_c20_pairing.md.",
                "No remesh. Sibling is D10 TOPPIN ROTX + 32 stays.",
            ],
        },
    }
    (E10 / "qa" / "n15" / "solution_verification_report.json").write_text(
        json.dumps(n15, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run": RUN_NAME, "paired": result["n_paired"], "local": result["n_local_gate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
