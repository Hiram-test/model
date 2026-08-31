# true3d-extreme run status 2026-08-28 (not a scientific claim)

Deck `5ebc64fae00a`  COARSEN=4  ccx 2.21  6867 B31  5018 nodes  100 eigenvalues.
R5 landed this run: 63 passage x-stations clustered to 21 equivalent beams (5 m gap); S10 ids ≥ 100000 remapped via `deck_id_from_s10` so they cannot clobber the `100000*(g+1)+k` scheme.

| Gate | Result |
|---|---|
| G-P1 | PASS  44 rope lines, F/g ≡ MASS21 = 963.811381 t |
| G-P2 | PASS  mass ledger 4108.466 t vs S10 4108.467 t (rel 2.4e-7) |
| UY | PASS  84/5018 nodes, frac 0.0167, not all-mesh |
| G-P3 | PASS  static 3 Newton iters, Job finished, 151.8 s |
| G-P4 | **FAIL**  4 residual-RB modes (~2e-4 Hz) still in the first 100 (dropped from modal_basis); last residual 195.3 N / W = 4.85e-6 > 1e-6. `conclusion_allowed=false`. RF print omitted: ccx 2.21 TOTALS segfault. |

First structural: LS1-like 0.03904 Hz. Locked Table 4-1 pairing in `true3d_table41_pairing.csv` (comparison only): 14 rows, MAE 7.1% (63-station deck gave 15.3%). LS2 now pairs at 0.1222 Hz (+12.5%, half-waves 3); on the old 63-station deck the same locked rule landed on 0.2085 Hz (ratio 1.92, half-waves 5). T-family cited only via the three-stack bracket, not 复现/一致. The bracket's lower edge is the 109k-node S10 ANSYS 3-D model itself (f99 S10/C20/D10/E10 TA1 = 0.0733 Hz, −26.4%, pinned to 2f*), not a planar-only bound. This deck's TA1 +6.5% sits *above* that locked 3-D floor. Lemma-A audit (`lateral_inertia_audit.json`): mass/tension rms_y both ~21.5 m → predict TA1/VA1 ≈ 1.00; solved 1.46. Passage EI/100 drops TA1 only 2.65% (skip/hinge/I=1e-4 diverge). Lift path not isolated; comparison only.

43/43 extreme scenarios swept; Amphan row carries U10 = 63.5 (66.7/1.05) in the sweep CSV. Atlas A1–A5 in `artifacts/atlas/`. Tornado/downburst/derecho rows are `reference_only` and hatched.

COARSEN=2 extra file (separate job `true3d_ccx_c2`, does not overwrite C4): vs C4 TA1 −7.49%, TS1 −1.61%, LS1 −1.02%, VA1 −0.36% (`coarsen2_shift.json`). TA1 is the most R2-sensitive row of the four.

Follow-on same day, all on the new modal basis:
- Master surface rebuilt; CV PASS (35 stationary events, max rel 3.43% < 5%, worst `cape_denison_katabatic`; 8 reference_only). A5 written.
- 陡振 Den Hartog H=0.733>0 on the catwalk section; single-rope Cl' 〔待填〕.
- Knowledge graph 181 nodes / 323 edges.
- Warning state machine `LEVEL=NOT_ARMED` (thresholds 〔待填〕).
- Three workshops updated under `workshops/`. Formal PDF: `report/true3d_three_workshops_cn.pdf`.
- C-level count in the library is 15 (A16/B12/C15). All stay unverified_C. Thresholds cited but armed=false.

`.frd` is local-only (179 MB). Rebuild: `bash code/run_solver.sh`.

This session (continue from `5e60b1e` / `38728e7`, do not rewind the tree):
- Did not re-run S10→ccx, Table 4-1 pairing, 43-sweep, or COARSEN=2.
- G-P4 remains FAIL: error ledger `artifacts/gp4_error_ledger.json` (`stop=true`, `conclusion_allowed=false`).
- External RMS input is a three-station placeholder (`attach23_rms_digitized.csv`); C-level stays unverified_C.
- A1–A4 and the locked 14-row pairing table backfilled into `report/true3d_three_workshops_cn.tex` as comparison records only.
- Wave-4 SHA `3a4250e9` is still a git ancestor (`merge-base --is-ancestor` exit 0). Do not claim a 1-commit squash; do not rebase onto an older tree.
