# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
sys.path.insert(0, str(ROOT / "ultra_runs"))
from _pair_modes_table41 import run_one, load_properties, load_sene, load_groups, load_probes, classify  # type: ignore

E20 = ROOT / "ultra_runs" / "E20_PASSAGE_SPRINGS_20260827T150412217226Z"
E10 = ROOT / "ultra_runs" / "E10_PASSAGE_UXYZ_20260827T125824870359Z"
S10 = (
    ROOT
    / "ultra_runs"
    / "S10_SECTION_SHEAR_20260716T050342389124Z"
    / "solver"
    / "s10_modal_properties.csv"
)


def main() -> None:
    result = run_one(E20, "e20", sibling_prop=S10)
    e10 = json.loads((E10 / "qa" / "e10_table41_pairing.json").read_text(encoding="utf-8"))
    e20 = json.loads((E20 / "qa" / "e20_table41_pairing.json").read_text(encoding="utf-8"))
    em = {p["label"]: p for p in e10["pairs"]}
    lines = [
        "# E20 vs E10 表4-1",
        "",
        "| 表4-1 | E10阶 | E20阶 | E10 Hz | E20 Hz | ΔHz | 阶次 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    changed = []
    for p in e20["pairs"]:
        o = em[p["label"]]
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
    solver = E20 / "solver"
    props = load_properties(solver / "e20_modal_properties.csv")
    sene = load_sene(solver / "e20_section_modal_sene.csv")
    groups = load_groups(solver / "e20_modal_sene_groups.csv")
    probes = load_probes(solver / "e20_mode_probes.csv")
    lines += ["", "## 前 8 阶独立分类", "", "| 阶 | Hz | family | hint | shareL | shareT | gateSENE | cableSENE |", "|---:|---:|---|---|---:|---:|---:|---:|"]
    for prop in props[:8]:
        m = prop["mode"]
        info = classify(prop, sene.get(m), groups.get(m), probes.get(m))
        lines.append(
            f"| {m} | {prop['freq']:.6f} | {info['family']} | {info['order_hint']} | "
            f"{info['share_L']:.3f} | {info['share_T']:.3f} | {info['r_gate']:.3f} | {info['r_cable_t4']:.3f} |"
        )
    lines += ["", "## 结论", ""]
    if not changed:
        lines.append("E20 未改变表4-1 阶次。")
    else:
        lines.append("相对 E10 发生变化的标签: " + ", ".join(changed))
    text = "\n".join(lines) + "\n"
    (E20 / "qa" / "e20_vs_e10_table41.md").write_text(text, encoding="utf-8")
    print(json.dumps({"paired": result["n_paired"], "local": result["n_local_gate"], "changed": changed}, ensure_ascii=False))
    print(text)


if __name__ == "__main__":
    main()
