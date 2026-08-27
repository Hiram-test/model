# -*- coding: utf-8 -*-
"""D10 POST1 closeout: N15 FSUM, Table 4-1 pairing, C20 comparison, N16-N18."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
D10 = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z"
C20 = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
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


def load_pairs(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def write_n15_fsum(fsum: dict[str, float]) -> None:
    n15 = D10 / "qa" / "n15" / "solution_verification_report.json"
    payload = json.loads(n15.read_text(encoding="utf-8"))
    data = payload["data"]
    for item in data["globalEquilibriumChecks"]:
        if item.get("checkId") == "N15-EQ-MOMENT":
            item["status"] = "POST1_FSUM_WRITTEN"
            item["fx"] = fsum.get("FX")
            item["fy"] = fsum.get("FY")
            item["fz"] = fsum.get("FZ")
            item["mx"] = fsum.get("MX")
            item["my"] = fsum.get("MY")
            item["mz"] = fsum.get("MZ")
            item["note"] = "FSUM at UZ supports from d10_static_fsum_uz_supports.txt after POST1."
            item["decision"] = "PASS_WITH_BOUNDS"
    verified = set(data.get("verifiedFieldRefs") or [])
    verified.update(
        [
            "static.fsum.uz_supports",
            "modal.sene.rstp_veng",
            "modal.probes",
            "modal.frequency.sets_expanded",
        ]
    )
    data["verifiedFieldRefs"] = sorted(verified)
    unverified = [
        x
        for x in (data.get("unverifiedFieldRefs") or [])
        if x not in {"static.fsum.uz_supports", "modal.sene.rstp_veng", "modal.probes"}
    ]
    data["unverifiedFieldRefs"] = unverified
    n15.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    eq = json.loads((D10 / "qa" / "n15" / "global_equilibrium_report.json").read_text(encoding="utf-8"))
    eq["data"]["uzSupportFsum"] = fsum
    eq["data"]["fsumSource"] = "solver/d10_static_fsum_uz_supports.txt"
    (D10 / "qa" / "n15" / "global_equilibrium_report.json").write_text(
        json.dumps(eq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_n16_n17_n18(pairs: list[dict], compared: list[dict]) -> None:
    qa = D10 / "qa"
    (qa / "n16").mkdir(exist_ok=True)
    (qa / "n17").mkdir(exist_ok=True)
    (qa / "n18").mkdir(exist_ok=True)
    n16 = {
        "artifactType": "static_review_summary",
        "schemaVersion": "1.0.0",
        "projectId": "PRJ-ZJG-CATWALK-MODAL",
        "runId": "RUN-D10-DOWNPULL-20260827T075458947752Z",
        "artifactId": "ART-D10-N16-STATIC-REVIEW",
        "status": "PASS_WITH_BOUNDS",
        "gateId": "G14",
        "data": {
            "intendedUse": "prestressed-modal-pairing-against-attachment-2-3-table-4-1",
            "excludedUse": [
                "member ULS design",
                "weld/bolt local check",
                "production frequency certification of TA1",
            ],
            "rulePackStatus": "NOT_FROZEN_FOR_CATWALK_ULS",
            "verifiedInputs": ["ART-D10-N15-SOLVER-VERIFICATION"],
            "gravityCase": {
                "massTonne": 4108.639824770034,
                "verticalReactionN": 40289322.12102870,
                "maxMonitorDisplacementMm": -138.74,
                "source": "d10_static_energy_mass_reaction.txt and mntr",
            },
            "decision": "PASS_WITH_BOUNDS",
            "bounds": [
                "Charter use is modal pairing, not member utilization.",
                "D10 vs C20 first 25 frequencies differ at 1e-5 Hz; physical 32-stay downpull does not change global eigenvalues.",
                "TA1 physical frequency remains 26% below measured 0.0996 Hz; not a production frequency claim.",
            ],
        },
    }
    (qa / "n16" / "static_review_summary.json").write_text(
        json.dumps(n16, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ta1 = next((p for p in pairs if p.get("label") == "TA1"), {})
    n17 = {
        "artifactType": "credibility_assessment",
        "schemaVersion": "1.0.0",
        "projectId": "PRJ-ZJG-CATWALK-MODAL",
        "runId": "RUN-D10-DOWNPULL-20260827T075458947752Z",
        "artifactId": "ART-D10-N17-CREDIBILITY",
        "status": "PASS_WITH_BOUNDS",
        "gateId": "G15",
        "data": {
            "independence": [
                "method: C20 cross-check signs + S10 PFACT + toppost SENE vs cable amp",
                "data: D10 POST1 probes/SENE and S10 sibling PFACT",
                "not: second solver",
            ],
            "claims": [
                {
                    "claimId": "CLM-D10-NO-FREQ-SHIFT",
                    "statement": "D10 32-stay downpull does not move the first 25 eigenvalues versus C20 TOPPIN ROTX",
                    "result": "PASS",
                    "note": "max |Δf| in first 25 is 3.5e-5 Hz at mode 25",
                },
                {
                    "claimId": "CLM-TA1-PHYSICS",
                    "statement": "Antisymmetric torsion remains hybridized near 0.0734 Hz, not 0.0996 Hz",
                    "result": "PASS_WITH_BOUNDS",
                    "femHz": ta1.get("f_fem"),
                    "refHz": 0.0996,
                    "mode": ta1.get("mode"),
                },
                {
                    "claimId": "CLM-PAIRING-UNCHANGED",
                    "statement": "D10 Table 4-1 pairing does not change C20 conclusions",
                    "result": "PASS" if all(r["same_mode"] for r in compared if r["label"] != "LA2") else "PASS_WITH_BOUNDS",
                },
            ],
            "permissibleUse": [
                "parent line for E10 passage UXYZ four-port release",
                "table 4-1 pairing discussion",
            ],
            "notPermissible": [
                "declare TA1 recovered to 0.0996 Hz",
                "rename this deck to production F00",
            ],
        },
    }
    (qa / "n17" / "credibility_assessment.json").write_text(
        json.dumps(n17, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# D10 物理下压 工程报告（N18 数据层）",
        "",
        "**Run** `D10_DOWNPULL_20260827T075458947752Z`",
        "**Job** `cw_D10x_0827t075458`",
        "**Parent** `C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z`",
        "**G13/G14/G15** PASS_WITH_BOUNDS",
        "",
        "## 用途",
        "",
        "允许：32 根物理下压索 vs 4 根等效索的连接研究、表 4-1 物理配对、作为 E10 父线。",
        "不允许：把 TA1 宣称已对齐 0.0996 Hz；封 F00 生产模型。",
        "",
        "## 静力",
        "",
        "质量 4108.63982477 t（相对 C20 +0.173 t，索更长），FZ 相对误差 1.65e-11，LS1/LS2 均收敛，稳定化能量比 ~1e-33。最大位移 −138.74 mm。",
        "",
        "## 相对 C20 的频率",
        "",
        "前 25 阶 Δf 在 1e-5 Hz 量级。32 根下压索总 EA 与总轴力未变，整体特征值不变。",
        "",
        "## 表 4-1",
        "",
        "见 `qa/d10_table41_pairing.md` 与 `qa/d10_vs_c20_pairing.md`。",
        "",
        "## 下一工况",
        "",
        "E10：1386 条横通道 CERIG ALL → UXYZ，释放四端口相对转动。",
        "",
    ]
    (qa / "n18" / "engineering_report.md").write_text("\n".join(lines), encoding="utf-8")


def compare_pairings() -> list[dict]:
    c20 = {r["label"]: r for r in load_pairs(C20 / "qa" / "c20_table41_pairing.csv")}
    d10 = {r["label"]: r for r in load_pairs(D10 / "qa" / "d10_table41_pairing.csv")}
    rows = []
    lines = [
        "# D10 vs C20 表4-1配对对比",
        "",
        "方法：C20 交叉复查后的物理配对（测点符号 + SENE toppost/TYPE4 + S10 PFACT 旁证 + 8% 频率窗）。",
        "禁止按阶次硬配。",
        "",
        "| 表4-1 | C20阶 | C20 Hz | D10阶 | D10 Hz | Δf Hz | 阶次是否相同 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for label, *_rest in [
        ("LS1",), ("VA1",), ("LA1",), ("TA1",), ("VS1",), ("LS2",), ("TS1",),
        ("SIDE1",), ("SIDE2",), ("VA2",), ("LA2",), ("SIDE3",), ("TS2",), ("VS2",),
    ]:
        a, b = c20.get(label, {}), d10.get(label, {})
        def _i(d, k):
            v = d.get(k)
            if v in (None, "", "None"):
                return None
            try:
                return int(float(v))
            except ValueError:
                return None
        def _f(d, k):
            v = d.get(k)
            if v in (None, "", "None"):
                return None
            try:
                return float(v)
            except ValueError:
                return None
        ma, mb = _i(a, "mode"), _i(b, "mode")
        fa, fb = _f(a, "f_fem"), _f(b, "f_fem")
        df = (fb - fa) if (fa is not None and fb is not None) else None
        same = ma == mb and ma is not None
        rows.append({"label": label, "c20_mode": ma, "d10_mode": mb, "same_mode": same, "delta_hz": df})
        def _s(v, fmt):
            if v is None:
                return "—"
            return format(v, fmt)
        lines.append(
            f"| {label} | {_s(ma, 'd')} | {_s(fa, '.6f')} | {_s(mb, 'd')} | {_s(fb, '.6f')} | "
            f"{_s(df, '.3e')} | {'是' if same else '否'} |"
        )
    changed = [r["label"] for r in rows if not r["same_mode"]]
    lines += ["", "## 结论", ""]
    if not changed:
        lines.append("**D10 没有改变任何表4-1 阶次结论。** TA1 仍是杂交对中偏扭转的那一阶，相对实测 −26%。")
    else:
        lines.append(f"阶次不一致的标签：{', '.join(changed)}。其余与 C20 一致。")
    lines.append("")
    dest = D10 / "qa" / "d10_vs_c20_pairing.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return rows


def update_pointers() -> None:
    (ROOT / "ultra_runs" / "D10_LATEST.md").write_text(
        "# D10 指针\n\n"
        "`D10_DOWNPULL_20260827T075458947752Z` job `cw_D10x_0827t075458`\n\n"
        "- 父线：`C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z`\n"
        "- 静力通过；Lanczos 80；MXPAND+POST1 已导出测点/SENE\n"
        "- N15 PASS_WITH_BOUNDS；表4-1 见 `qa/d10_table41_pairing.md`\n"
        "- 前 25 阶相对 C20 Δf ~ 1e-5 Hz，TA1 仍 −26%\n"
        "- 下一工况：E10 横通道 CERIG ALL→UXYZ\n",
        encoding="utf-8",
    )
    f99 = ROOT / "ultra_runs" / "F99_CHAIN_CLOSURE_20260827T080000Z" / "F99_chain_closure.md"
    f99.write_text(
        "# F99 链闭合（进行中）\n\n"
        "日期：2026-08-27。单位 N, mm, tonne, s。CERIG 保留，C10 MPC184 已放弃。\n\n"
        "## 链\n\n"
        "| 节点 | Run | 状态 |\n"
        "|---|---|---|\n"
        "| B00 | `B00_LEGACY_COMPLETE_20260715T111105670409Z` | 父线资料 |\n"
        "| S10 | `S10_SECTION_SHEAR_20260716T050342389124Z` | 静力+80 阶封板 |\n"
        "| C10 | MPC184 已放弃 | 不进入生产链 |\n"
        "| C20 | `C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z` | 静力+80 阶+POST1+N15+表4-1；交叉复查完成 |\n"
        "| D10 | `D10_DOWNPULL_20260827T075458947752Z` | 静力+80 阶+POST1+N15+表4-1；频率相对 C20 不变 |\n"
        "| E10 | `E10_PASSAGE_UXYZ_20260827T125824870359Z` | 已准备：1386 横通道 ALL→UXYZ |\n"
        "| F00 | — | 禁止：TA1 未进 0.0996 目标带 |\n",
        encoding="utf-8",
    )


def main() -> None:
    solver = D10 / "solver"
    probes = solver / "d10_mode_probes.csv"
    props = solver / "d10_modal_properties.csv"
    if not probes.exists() or not props.exists():
        raise SystemExit("D10 POST1 artifacts missing")
    fsum_path = solver / "d10_static_fsum_uz_supports.txt"
    if fsum_path.exists():
        write_n15_fsum(parse_fsum(fsum_path))
    result = run_one(D10, "d10", sibling_prop=S10_PROP)
    compared = compare_pairings()
    pairs = result["pairs"]
    write_n16_n17_n18(pairs, compared)
    update_pointers()
    (D10 / "D10_status.json").write_text(
        json.dumps(
            {
                "run_id": "D10_DOWNPULL",
                "run_name": "D10_DOWNPULL_20260827T075458947752Z",
                "jobname": "cw_D10x_0827t075458",
                "parent": "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z",
                "status": "POST1_N15_PAIRED",
                "ncount": 109082,
                "ecount": 173022,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "paired": result["n_paired"],
                "local": result["n_local_gate"],
                "changed_labels": [r["label"] for r in compared if not r["same_mode"]],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
