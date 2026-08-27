# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from pathlib import Path

SOLVER = Path(
    r"D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs"
    r"\C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z\solver"
)


def main() -> None:
    rows: dict[int, dict[int, dict[str, float]]] = {}
    for line in (SOLVER / "c20_mode_probes.csv").read_text(encoding="utf-8").splitlines():
        t = [float(x.replace("D", "E")) for x in line.split(",") if x.strip() != ""]
        if len(t) < 10:
            continue
        m = int(round(t[0]))
        k = int(round(t[2]))
        rows.setdefault(m, {})[k] = {"f": t[1], "uy": t[5], "uz": t[6], "rx": t[7]}
    grp: dict[int, list[float]] = {}
    for line in (SOLVER / "c20_modal_sene_groups.csv").read_text(encoding="utf-8").splitlines():
        t = [float(x.replace("D", "E")) for x in line.split(",") if x.strip() != ""]
        if len(t) < 14:
            continue
        grp[int(round(t[0]))] = t
    print("m   fHz      L     V     T   mainAmp midUY   middUZ  q1dUZ   q1UY    q3UY   rT4   rTop")
    for m in range(1, 31):
        r = rows[m]

        def u(k: int, c: str) -> float:
            return r.get(k, {}).get(c, 0.0)

        l_e = v_e = t_e = 0.0
        for a, b in ((2, 7), (3, 8), (4, 9)):
            uyp, uyn = u(a, "uy"), u(b, "uy")
            uzp, uzn = u(a, "uz"), u(b, "uz")
            l_e += (uyp + uyn) ** 2
            v_e += (uzp + uzn) ** 2
            t_e += (uzp - uzn) ** 2
        tot = l_e + v_e + t_e + 1e-30
        main = math.sqrt(sum(u(k, "uy") ** 2 + u(k, "uz") ** 2 for k in (2, 3, 4, 7, 8, 9)) / 6.0)
        g = grp.get(m, [0.0] * 14)
        mid_duz = u(3, "uz") - u(8, "uz")
        q1_duz = u(2, "uz") - u(7, "uz")
        print(
            f"{m:2d} {r[3]['f']:.5f} {l_e/tot:.3f} {v_e/tot:.3f} {t_e/tot:.3f} "
            f"{main:7.1e} {u(3,'uy'):8.1e} {mid_duz:8.1e} {q1_duz:8.1e} "
            f"{u(2,'uy'):8.1e} {u(4,'uy'):8.1e} {g[8]:6.3f} {g[12]:6.3f}"
        )


if __name__ == "__main__":
    main()
