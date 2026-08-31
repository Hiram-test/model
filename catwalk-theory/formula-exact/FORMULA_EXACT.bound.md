# Formula-exact path — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_formula_exact=true`. `not_fourteen_mode_table=true`.

The branch name and artifact `catwalk-formula-exact-results` are not a closed-form solution and not attach TA1. Do not write 复现 / 一致.

## Wave P1 — main-span parabola 32-cable toy (`86e9238`…`95ff14a`, run `33437560765`)

New branch from already-stamped `a01768a`. Unique files: `solve_formula_exact.py` (135 lines) and a 22-line workflow.

- Model is **main-span only**: L=2286.642 m, sag 227.300 m, 16+16 floor cables, 80 segments, no gantry ropes, no portals as frames, no MCT topology. Not the 44-rope dual-catwalk solver.
- Transverse/passage coupling is EA/L on lateral DOFs only. Vertical spectrum is nearly **32-fold degenerate** at 0.06901 Hz and again at 0.10109 Hz. `eigh` of a weakly coupled parabola is not “formula exact”.
- Classification `pick(family, parity, rank)` has no n=2/3/5 lock. Reported CLASS TA1 **0.06901 ≠ 0.0996**; TS1/TS2/VS1/VS2 all 0.10109 Hz (same cluster). VA1/VA2/TA1 share 0.06901 Hz. This is not a physical 14-mode table.
- Isolation: no attach Hz in the solver or YAML. Green zip is stdout, not DAT/FRD/ccx, not true3d C4.

## Wave P2 — 44-rope main-span `eigsh` (`c3f1e70`, `46e70b5`, run `33439905034`)

- `solve_formula_exact_v4.py` (313 lines): 32 floor + 12 gantry ropes, 71 condensed portals, 13 main-span passages, 10428 free DOF. Still **main-span only**. Still `eigsh`, not a closed-form exact solution.
- No attach Hz in the solver. `target_frequency_used=false`. Family pick is rank-by-frequency, not n=2/3/5 lock. Reported TS2 has `longitudinal_order=1` (not n=5).
- Selected vs attach 2-3 (comparison only): TA1 **0.07165 ≠ 0.0996 (−28.1%)**; TS1 0.10056 ≠ 0.1147 (−12.3%); TS2 0.15049 ≠ 0.1571. Not 复现.
- Artifact `catwalk-formula-exact-v4-results` is not formula-exact and not attach TA1.

Do not treat this path as the true3d reduced C4 deck.
