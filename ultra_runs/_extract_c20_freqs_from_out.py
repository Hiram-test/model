# -*- coding: utf-8 -*-
"""Extract Block Lanczos 80 frequencies from C20 OUT into csv."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
RUN = ROOT / "ultra_runs" / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
OUT = RUN / "solver" / "cw_c20x_0827t053427.out"
DEST = RUN / "qa" / "c20_frequencies_from_out.csv"

MARKER = "*** FREQUENCIES FROM BLOCK LANCZOS ITERATION ***"
ROW = re.compile(r"^\s*(\d+)\s+([0-9.+-Ee]+)\s*$")


def main() -> None:
    text = OUT.read_text(encoding="utf-8", errors="replace")
    idx = text.rfind(MARKER)
    if idx < 0:
        raise SystemExit("frequency table not found")
    rows: list[tuple[int, float]] = []
    for raw in text[idx:].splitlines():
        m = ROW.match(raw)
        if not m:
            if rows and raw.strip().startswith("***"):
                break
            continue
        mode = int(m.group(1))
        freq = float(m.group(2))
        if 1 <= mode <= 80:
            rows.append((mode, freq))
        if mode == 80:
            break
    if len(rows) != 80:
        raise SystemExit(f"expected 80 rows, got {len(rows)}")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(
        "mode,freq_hz\n" + "\n".join(f"{m},{f:.16e}" for m, f in rows) + "\n",
        encoding="utf-8",
    )
    print(DEST)
    print(f"f1={rows[0][1]:.8f} f80={rows[-1][1]:.8f}")


if __name__ == "__main__":
    main()
