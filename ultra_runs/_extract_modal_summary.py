# -*- coding: utf-8 -*-
"""Extract first 20 frequencies and a TA1 candidate from a solver modal CSV."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

# Columns: mode, freq, genm, PX, PY, PZ, PRX, PRY, PRZ, EX, EY, EZ, ERX, ERY, ERZ
TARGETS = {
    "LS1": 0.0365,
    "LA1": 0.0700,
    "VA1": 0.0726,
    "TA1": 0.0996,
    "VS1": 0.1028,
    "TA1_v5": 0.10003,
    "TS1": 0.1147,
    "TS2": 0.1571,
}


def parse_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 15:
            continue
        vals = [float(p) for p in parts[:15]]
        rows.append(
            {
                "mode": vals[0],
                "freq": vals[1],
                "genm": vals[2],
                "PX": vals[3],
                "PY": vals[4],
                "PZ": vals[5],
                "PRX": vals[6],
                "PRY": vals[7],
                "PRZ": vals[8],
                "EX": vals[9],
                "EY": vals[10],
                "EZ": vals[11],
                "ERX": vals[12],
                "ERY": vals[13],
                "ERZ": vals[14],
            }
        )
    return rows


def ta1_score(row: dict[str, float]) -> float:
    # Prefer ~0.07-0.12 Hz with large ROTX effective mass relative to translation.
    freq = row["freq"]
    if freq < 0.05 or freq > 0.16:
        return -1.0
    erx = abs(row["ERX"])
    trans = abs(row["EX"]) + abs(row["EY"]) + abs(row["EZ"]) + 1.0
    return erx / trans - abs(freq - 0.0996) * 1e6


def summarize(path: Path) -> dict:
    rows = parse_csv(path)
    ranked = sorted(rows, key=ta1_score, reverse=True)
    ta1 = ranked[0] if ranked else None
    first10 = rows[:10]
    return {
        "path": str(path),
        "n_modes": len(rows),
        "first10": [{"mode": int(r["mode"]), "freq": r["freq"], "ERX": r["ERX"], "EY": r["EY"], "EZ": r["EZ"]} for r in first10],
        "ta1_candidate": None
        if ta1 is None
        else {
            "mode": int(ta1["mode"]),
            "freq": ta1["freq"],
            "ERX": ta1["ERX"],
            "target_0p0996_rel_error": (ta1["freq"] - 0.0996) / 0.0996,
            "v5_0p10003_rel_error": (ta1["freq"] - 0.10003) / 0.10003,
        },
    }


if __name__ == "__main__":
    target = Path(sys.argv[1])
    print(json.dumps(summarize(target), indent=2))
