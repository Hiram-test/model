# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
sys.path.insert(0, str(ROOT / "ultra_runs"))
from _pair_modes_table41 import run_one  # type: ignore

E10 = ROOT / "ultra_runs" / "E10_PASSAGE_UXYZ_20260827T125824870359Z"
D10 = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z"
S10 = (
    ROOT
    / "ultra_runs"
    / "S10_SECTION_SHEAR_20260716T050342389124Z"
    / "solver"
    / "s10_modal_properties.csv"
)


def main() -> None:
    result = run_one(E10, "e10", sibling_prop=S10)
    d10 = json.loads((D10 / "qa" / "d10_table41_pairing.json").read_text(encoding="utf-8"))
    e10 = json.loads((E10 / "qa" / "e10_table41_pairing.json").read_text(encoding="utf-8"))
    dm = {p["label"]: p for p in d10["pairs"]}
    lines = [
        "# E10 vs D10 表4-1",
        "",
        "| 表4-1 | D10阶 | E10阶 | D10 Hz | E10 Hz | ΔHz | 阶次 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    changed = []
    for p in e10["pairs"]:
        o = dm[p["label"]]
        df = None
        if p.get("f_fem") is not None and o.get("f_fem") is not None:
            df = p["f_fem"] - o["f_fem"]
        same = p.get("mode") == o.get("mode")

        def fmt(v, nd=6):
            if v is None:
                return "—"
            if isinstance(v, float):
                return f"{v:.{nd}f}"
            return str(v)

        lines.append(
            f"| {p['label']} | {fmt(o.get('mode'), 0)} | {fmt(p.get('mode'), 0)} | "
            f"{fmt(o.get('f_fem'))} | {fmt(p.get('f_fem'))} | {fmt(df, 8)} | "
            f"{'是' if same else '否'} |"
        )
        if not same or (df is not None and abs(df) > 5e-4):
            changed.append(p["label"])
    lines += ["", "## 结论", ""]
    if not changed:
        lines.append("E10 未改变任何表4-1 配对阶次。横通道 ALL→UXYZ 不是 TA1 开关。")
    else:
        lines.append("变化标签: " + ", ".join(changed))
    text = "\n".join(lines) + "\n"
    (E10 / "qa" / "e10_vs_d10_table41.md").write_text(text, encoding="utf-8")
    print(json.dumps({"paired": result["n_paired"], "local": result["n_local_gate"], "changed": changed}, ensure_ascii=False))
    print(text)


if __name__ == "__main__":
    main()
