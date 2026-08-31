# Clean 44-rope theory solver — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_fourteen_mode_table=true`.

Family label `TA1` in classification is not attach TA1 `0.0996`. T-family only via three-stack brackets. Do not write 复现 / 一致.

## Wave M1 — solver source, no Job (`bfebbb9`, `f28294d`)

- `README.md` plus `solve.py` (648 lines) under `catwalk-fem/clean-theory-14modes/`. Inverse static + 44-rope assembly + `eigsh`. Classification is energy / parity / sine-order only.
- The same `main()` hardcoded the attach 14-item Hz table (`0.0996`, `0.1147`, `0.1571`, …) after freeze. Isolation forbids attach numbers in a solver script. Targets moved to `compare_after_freeze.py`.
- Workflow still looks for `catwalk-theory/clean-44cable-modal/solve_clean_model.py`, which does not exist. These commits did not run the new solver. No `results/`, no DAT/FRD, no PR. zhaqing-prestress failures are unrelated.
- Source on disk is not a 14-mode table and not attach TA1.

## Wave M2 — CI wired; v1 inverse residual rejected (`7a7bca8`, `50cb382`)

- `7a7bca8` rewrote the workflow to run `solve.py` then `compare_after_freeze.py`. Isolation of the YAML is OK. Same commit reused `cache: pip` without `requirements.txt`. Actions `33429421996` failed at `setup-python`.
- `50cb382` dropped the pip cache. Actions `33429500742` invoked `solve.py`. Inverse residual **1.775168e-01 ≫ 5.0e-3**. No freeze, no comparison, no upload.
- A rejected inverse static is honest. The 5e-3 gate was not loosened.

## Wave M3 — v2 inverse closed; T labels unidentified (`34eab41`, `8e28926`, run `33430157422`)

- `solve_v2.py` adds explicit MCT `CONLOAD` / formed-length mass. Residual **0.003385 < 5.0e-3**. `eigsh` ran (8848 free DOF). No attach Hz in `solve_v2.py`.
- Artifact `dual-catwalk-clean-theory-14modes-v2`. Local-roll T labels unidentified (11/14). Comparison rows stay `frequency_reproduced=false`. This is a Python 2D 44-rope `eigsh`, not a ccx Job and not attach TA1.

## Wave M4 — v3 labels differential-V as T (`472a0a8`, `9572e19`, run `33430620066`)

- `solve_v3.py` overwrites TA1/TS1/TS2 from vertical-dominant modes with U/D correlation ≤ −0.50 (`Theta=(w_D-w_U)/42.90`). Order lock stays n=2/3/5. No TS2→TS3 rematch. No attach Hz in the solver.
- Frozen theory labels vs attach 2-3 (comparison node only): TA1 **0.12608 ≠ 0.0996 (+26.6%)**; TS1 0.12921 ≠ 0.1147 (+12.7%); TS2 0.20437 ≠ 0.1571 (+30.1%). L/V rows are not 复现.
- Green zip `dual-catwalk-clean-theory-14modes-v3` is a theory 14-label table, not attach reproduction and not true3d C4. Family label `TA1` is still not attach TA1.

## Wave N1 — archived drawing extract only (`03e2839`, `87f3516`, run `33432125425`)

New branch `feat/catwalk-clean-theory-v4-flexible-section` from `9a8b969`. Workflow downloads `zhangjinggao-full-20260729` shard `archive-0001.tar.zst` and extracts `01_设计资料与规范/00张靖皋长江大桥南航道桥猫道图纸1225.pdf` (20 566 268 B, sha `8df26c6b…`). `03e2839` failed because three copies of the same basename exist. No solver, no section properties, no 14-mode table. Green PDF is not a flexible-section model and not attach TA1.

Do not treat this path as the true3d reduced C4 deck.
