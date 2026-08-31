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

## Wave O1 — drawing-constant overlay (`f228aac`, `903272b`, run `33433820161`)

- `solve_v4_drawing_corrected.py` mutates gantry 7.38 m / y=±2.00/2.26/2.52, portal 160×4, portal mass 1142.76 kg, passage span 42.90 m / depth 1.70 m (cited MD4-01/02, MD1-05, MD5-02). Residual gate stays 5e-3. No attach Hz in the solver.
- Actions `33433820161` residual **0.003332**. Theory TA1 **0.12654 ≠ 0.0996 (+27.1%)**; TS1 0.13030 ≠ 0.1147 (+13.6%); TS2 0.20377 ≠ 0.1571 (+29.7%). vs v3, TA1 moved 0.12608→0.12654. Not a knob to attach TA1.
- Artifact name `*-v4-drawing-corrected` is not attach reproduction and not 复现. This patrol does not treat the MD* citations as independently re-measured from the PDF.

Do not treat this path as the true3d reduced C4 deck.
