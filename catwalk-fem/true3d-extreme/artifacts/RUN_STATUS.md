# true3d-extreme run status 2026-08-28 (not a scientific claim)

Deck `f089dee33377`  COARSEN=4  ccx 2.21  7477 B31  5422 nodes  100 eigenvalues.

| Gate | Result |
|---|---|
| G-P1 | PASS  44 rope lines, F/g ≡ MASS21 = 963.811381 t |
| G-P2 | PASS  mass ledger 4108.466 t vs S10 4108.467 t (rel 2.4e-7) |
| UY | PASS  84/5422 nodes, frac 0.0155, not all-mesh |
| G-P3 | PASS  static 3 Newton iters, Job finished, 151.8 s |
| G-P4 | STRUCTURAL_OK_NUMERICAL_ZEROS_DROPPED  4 residual-RB modes (~2e-4 Hz) dropped from modal_basis; last residual 57 N / W = 1.4e-6 (RF print omitted: ccx 2.21 TOTALS segfault) |

First structural: LS1-like 0.03982 Hz. Locked Table 4-1 pairing in `true3d_table41_pairing.csv` (comparison only). T-family cited only via the three-stack bracket, not 复现/一致.

43/43 extreme scenarios swept. Atlas A1–A4 in `artifacts/atlas/`. Tornado/downburst/derecho rows are `reference_only` and hatched.

Known deviations kept this run: R5 asked 21 passages; builder emitted 63 x-stations = 21 clusters of 3 (passage depth ~1.4 m). LS2 locked-rule pair is the next main-span L+S at 0.209 Hz (+92 %); no re-pair.

`.frd` is local-only (185 MB). Rebuild: `bash code/run_solver.sh`.
