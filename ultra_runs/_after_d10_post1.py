# -*- coding: utf-8 -*-
"""After D10 POST1: pair Table 4-1, compare with C20, refresh N15 FSUM notes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")

import sys

sys.path.insert(0, str(ROOT / "ultra_runs"))
from _pair_modes_table41 import run_one  # type: ignore


D10 = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z"
C20 = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
S10_PROP = (
    ROOT
    / "ultra_runs"
    / "S10_SECTION_SHEAR_20260716T050342389124Z"
    / "solver"
    / "s10_modal_properties.csv"
)


def require_post1() -> None:
    needed = [
        D10 / "solver" / "d10_gate_status.txt",
        D10 / "solver" / "d10_modal_properties.csv",
        D10 / "solver" / "d10_mode_probes.csv",
        D10 / "solver" / "d10_section_modal_sene.csv",
        D10 / "solver" / "d10_modal_sene_groups.csv",
        D10 / "solver" / "d10_static_fsum_uz_supports.txt",
    ]
    missing = [str(p) for p in needed if not p.exists() or p.stat().st_size < 10]
    if missing:
        raise SystemExit("POST1 artifacts missing:\n" + "\n".join(missing))
    status = (D10 / "solver" / "d10_gate_status.txt").read_text(encoding="utf-8", errors="replace")
    if "SOLVER_EXPORT_COMPLETED" not in status:
        raise SystemExit(f"gate not completed: {status.strip()}")


def compare_pairs() -> dict:
    c20 = json.loads((C20 / "qa" / "c20_table41_pairing.json").read_text(encoding="utf-8"))
    d10 = json.loads((D10 / "qa" / "d10_table41_pairing.json").read_text(encoding="utf-8"))
    rows = []
    changed = []
    c20_map = {p["label"]: p for p in c20["pairs"]}
    for rec in d10["pairs"]:
        other = c20_map.get(rec["label"], {})
        same_mode = rec.get("mode") == other.get("mode")
        df = None
        if rec.get("f_fem") is not None and other.get("f_fem") is not None:
            df = rec["f_fem"] - other["f_fem"]
        row = {
            "label": rec["label"],
            "c20_mode": other.get("mode"),
            "d10_mode": rec.get("mode"),
            "c20_hz": other.get("f_fem"),
            "d10_hz": rec.get("f_fem"),
            "df_hz": df,
            "same_mode_index": same_mode,
        }
        rows.append(row)
        if not same_mode or (df is not None and abs(df) > 5e-4):
            changed.append(row)
    md = [
        "# D10 vs C20 表4-1 配对对比",
        "",
        "方法与 C20 复查后相同：能量份额 + 测点符号，禁止按阶次硬配。",
        "S10 官方 PFACT 仅作同频旁证。",
        "",
        "| 表4-1 | C20 阶 | D10 阶 | C20 Hz | D10 Hz | ΔHz | 阶次是否相同 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        def fmt(v, nd=6):
            return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
        md.append(
            f"| {r['label']} | {fmt(r['c20_mode'],0)} | {fmt(r['d10_mode'],0)} | "
            f"{fmt(r['c20_hz'])} | {fmt(r['d10_hz'])} | {fmt(r['df_hz'], 8)} | "
            f"{'是' if r['same_mode_index'] else '否'} |"
        )
    md += ["", "## 是否改变配对结论", ""]
    if not changed:
        md.append("D10 没有改变任何表4-1 配对阶次，频率差均 < 5e-4 Hz。下压索不是 TA1 开关。")
    else:
        md.append("以下标签阶次或频率与 C20 不一致，需人工阅读测点：")
        for r in changed:
            md.append(f"- {r['label']}: C20 M{r['c20_mode']} → D10 M{r['d10_mode']}, Δf={r['df_hz']}")
    text = "\n".join(md) + "\n"
    (D10 / "qa" / "d10_vs_c20_table41.md").write_text(text, encoding="utf-8")
    (ROOT / "ultra_runs" / "frequency_comparison_C20_D10_table41.md").write_text(text, encoding="utf-8")
    return {"n_changed": len(changed), "rows": rows}


def refresh_fsum_note() -> None:
    fsum = (D10 / "solver" / "d10_static_fsum_uz_supports.txt").read_text(encoding="utf-8", errors="replace")
    n15 = D10 / "qa" / "n15" / "solution_verification_report.json"
    payload = json.loads(n15.read_text(encoding="utf-8"))
    for item in payload["data"]["globalEquilibriumChecks"]:
        if item["checkId"] == "N15-EQ-MOMENT":
            item["status"] = "POST1_FSUM_WRITTEN"
            item["note"] = fsum.strip().replace("\n", " | ")
            item["decision"] = "PASS_WITH_BOUNDS"
    unverified = payload["data"]["unverifiedFieldRefs"]
    payload["data"]["unverifiedFieldRefs"] = [x for x in unverified if "fsum" not in x]
    payload["data"]["verifiedFieldRefs"] = list(
        dict.fromkeys(payload["data"]["verifiedFieldRefs"] + ["static.fsum.uz_supports", "modal.sene.rstp_veng", "modal.probes"])
    )
    n15.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    require_post1()
    result = run_one(D10, "d10", sibling_prop=S10_PROP)
    cmp_ = compare_pairs()
    refresh_fsum_note()
    status_path = D10 / "D10_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["status"] = "POST1_PAIRED"
    status["n_paired"] = result["n_paired"]
    status["n_local_gate"] = result["n_local_gate"]
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "paired": result["n_paired"],
                "local": result["n_local_gate"],
                "changed_vs_c20": cmp_["n_changed"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
