# -*- coding: utf-8 -*-
"""Extract Block Lanczos 80 frequencies from D10 OUT into csv."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0")
RUN = ROOT / "ultra_runs" / "D10_DOWNPULL_20260827T075458947752Z"
OUT = RUN / "solver" / "cw_d10x_0827t075458.out"
DEST = RUN / "qa" / "d10_frequencies_from_out.csv"
C20 = (
    ROOT
    / "ultra_runs"
    / "C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z"
    / "qa"
    / "c20_frequencies_from_out.csv"
)

MARKER = "*** FREQUENCIES FROM BLOCK LANCZOS ITERATION ***"
ROW = re.compile(r"^\s*(\d+)\s+([0-9.+-Ee]+)\s*$")


def load_out(path: Path) -> list[tuple[int, float]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    idx = text.rfind(MARKER)
    if idx < 0:
        raise SystemExit(f"frequency table not found in {path}")
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
    return rows


def main() -> None:
    rows = load_out(OUT)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(
        "mode,freq_hz\n" + "\n".join(f"{m},{f:.16e}" for m, f in rows) + "\n",
        encoding="utf-8",
    )
    c20 = {}
    if C20.exists():
        for line in C20.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            m, f = line.split(",", 1)
            c20[int(m)] = float(f)
    cmp_path = RUN / "qa" / "d10_vs_c20_frequencies.csv"
    cmp_lines = ["mode,d10_hz,c20_hz,delta_hz"]
    max_abs = 0.0
    max_mode = 1
    for m, f in rows:
        cf = c20.get(m)
        df = (f - cf) if cf is not None else float("nan")
        cmp_lines.append(f"{m},{f:.16e},{'' if cf is None else format(cf, '.16e')},{df:.16e}")
        if cf is not None and abs(df) > max_abs:
            max_abs = abs(df)
            max_mode = m
    cmp_path.write_text("\n".join(cmp_lines) + "\n", encoding="utf-8")
    print(DEST)
    print(cmp_path)
    print(f"f1={rows[0][1]:.8f} f80={rows[-1][1]:.8f} max|d10-c20|={max_abs:.3e} at mode {max_mode}")


if __name__ == "__main__":
    main()
