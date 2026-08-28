# true3d-extreme run status 2026-08-28 (not a scientific claim)

Deck `f089dee33377`  COARSEN=4  ccx 2.21  7477 B31  5422 nodes  100 eigenvalues.

| Gate | Result |
|---|---|
| G-P1 | PASS  44 rope lines, F/g ≡ MASS21 = 963.811381 t |
| G-P2 | PASS  mass ledger 4108.466 t vs S10 4108.467 t (rel 2.4e-7) |
| UY | PASS  84/5422 nodes, frac 0.0155, not all-mesh |
| G-P3 | PASS  static 3 Newton iters, Job finished, 151.8 s |
| G-P4 | **FAIL**  4 residual-RB modes (~2e-4 Hz) still in the first 100 (dropped from modal_basis); last residual 57 N / W = 1.42e-6 > 1e-6. `conclusion_allowed=false`. RF print omitted: ccx 2.21 TOTALS segfault. |

First structural: LS1-like 0.03982 Hz. Locked Table 4-1 pairing in `true3d_table41_pairing.csv` (comparison only). T-family cited only via the three-stack bracket, not 复现/一致.

43/43 extreme scenarios swept. Atlas A1–A4 in `artifacts/atlas/`. Tornado/downburst/derecho rows are `reference_only` and hatched.

Known deviations kept this run: solved COARSEN=4 deck still has 63 passage x-stations. `cluster_x_stations` is **not** in the builder (ce82b54 named it; source does not have it). LS2 locked-rule pair is the next main-span L+S at 0.209 Hz (ratio 1.92 to attach 0.1087, half-waves=5); no re-pair. LS1 is +9.1%. COARSEN=2 T-shift ledger is in `coarsen2_shift.json` (TA1 −1.43%, TS1 −1.10%, LS1 −0.90%).

Follow-on this same day:
- Master surface CV PASS (stationary max rel 3.37% < 5%). A5 written.
- 陡振 Den Hartog H=0.733>0 on the catwalk section; single-rope Cl' 〔待填〕.
- Knowledge graph 181 nodes / 323 edges.
- Warning state machine `LEVEL=NOT_ARMED` (thresholds 〔待填〕).
- Three workshops filled under `workshops/`. Formal 2-page PDF: `report/true3d_three_workshops_cn.pdf`.
- C-level count in the library is 15 (A16/B12/C15). All stay unverified_C. Thresholds cited but armed=false.

`.frd` is local-only (185 MB). Rebuild: `bash code/run_solver.sh`.
Patrol is off on this agent.
