# Clean 44-rope theory solver — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_fourteen_mode_table=true`.

Family label `TA1` in classification is not attach TA1 `0.0996`. T-family only via three-stack brackets. Do not write 复现 / 一致.

## Wave M1 — solver source, no Job (`bfebbb9`, `f28294d`)

- `README.md` plus `solve.py` (648 lines) under `catwalk-fem/clean-theory-14modes/`. Inverse static + 44-rope assembly + `eigsh`. Classification is energy / parity / sine-order only.
- The same `main()` hardcoded the attach 14-item Hz table (`0.0996`, `0.1147`, `0.1571`, …) after freeze. Isolation forbids attach numbers in a solver script. Targets moved to `compare_after_freeze.py`.
- Workflow still looks for `catwalk-theory/clean-44cable-modal/solve_clean_model.py`, which does not exist. These commits did not run the new solver. No `results/`, no DAT/FRD, no PR. zhaqing-prestress failures are unrelated.
- Source on disk is not a 14-mode table and not attach TA1.

Do not treat this path as the true3d reduced C4 deck.
