"""Post-freeze comparison only. Not a solver and not attach reproduction."""
from __future__ import annotations
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
# Attachment 2-3 family Hz live only in this comparison node.
TARGETS = {
    "LS1": 0.0365,
    "VA1": 0.0700,
    "LA1": 0.0726,
    "TA1": 0.0996,
    "VS1": 0.1028,
    "LS2": 0.1087,
    "TS1": 0.1147,
    "SIDE1": 0.1149,
    "SIDE2": 0.1239,
    "VA2": 0.1438,
    "LA2": 0.1449,
    "SIDE3": 0.1557,
    "TS2": 0.1571,
    "VS2": 0.1744,
}


def main() -> int:
    frozen_path = OUT / "frozen_results.json"
    if not frozen_path.is_file():
        print("no frozen_results.json; comparison skipped")
        return 0
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    selected = frozen.get("classified_14") or {}
    rows = []
    for label, target in TARGETS.items():
        item = selected.get(label) or {}
        computed = item.get("frequency_hz")
        error = None if computed is None else 100.0 * (float(computed) - target) / target
        rows.append(
            {
                "label": label,
                "mode": item.get("mode"),
                "computed_hz": computed,
                "target_hz": target,
                "error_percent": error,
                "status": item.get("status", "missing"),
                "frequency_reproduced": False,
                "not_attach_ta1": True,
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "comparison_after_freeze.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    receipt = (
        "human_apdl=false\n"
        "frequency_reproduced=false\n"
        "not_attach_ta1=true\n"
        "not_fourteen_mode_table=true\n"
        "kind=post_freeze_comparison_only\n"
    )
    (OUT / "case.txt").write_text(receipt, encoding="utf-8")
    print(json.dumps({"kind": "post_freeze_comparison_only", "frequency_reproduced": False, "rows": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
