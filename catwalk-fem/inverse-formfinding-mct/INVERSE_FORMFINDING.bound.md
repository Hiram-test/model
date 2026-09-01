# MCT geometry inverse form-finding — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_fourteen_mode_table=true`. `not_ccx_job_finished=true`. `not_recovered_iniforce=true`.

Input boundary (Grok): allowed before solve = MCT formed coordinates, 1194 element incidences, self-weight, stage-two nodal loads, restraint topology. Forbidden before solve = `INIFORCE` / `INI-EFORCE` / `EQUI-MFORCE`, C3/S10/B00 modal data, target frequencies, previous inverse-force results, frequency-based tuning.

Family label `TA1` is not attach TA1 `0.0996`. Do not write 复现 / 一致.

## Wave Q1 — input boundary only (`7773f0a`, `77c020f`)

- New directory on `feat/catwalk-clean-theory-14modes`: 3-line README + this bound. No solver yet. Not a recovered cable-force field.

## Wave Q2 — isolated X–Z `lstsq` (`5312763`…`febafb1`, run `33500410644`)

- `solve_inverse.py` (191 lines) + `audit_endpoint_forces.py` (63 lines) + workflow. MCT source sha `0d18e3f7…` (448673 B), 1125 nodes, 1194 elements, 1123 TENSTR + 71 TRUSS. Isolation: no attach Hz, no 复现 / 一致 in solver or YAML. `initial_force_used_in_inverse_solve=false`; INIFORCE loaded only after freeze.
- Operator is **X–Z free-node only** (Y dropped). Stage-two FY count is 0. This is Python `scipy.linalg.lstsq` / optional `lsq_linear`, not a CalculiX Job finished, not true3d C4.
- Actions `33500410644` green because `main()` always `return 0`. Scientific verdict in `summary.json`: `success_initial_force_agreement=false`.
  - recovered equilibrium relative residual **0.0032826 > 1e-8**
  - stored-INIFORCE equilibrium relative residual **0.004256 > 1e-4**
  - body TENSTR |Δ| p95 **0.291% ≤ 5%** does not override the residual fail
- Endpoint-force audit: INI-EFORCE free-node residual **0.184**; mean INIFORCE residual 0.004256. MCT endpoint forces do not close free-node equilibrium.
- Residual gates were not loosened. Green zip `*-results` is not a recovered form-found model and not attach TA1.

## Wave Q3 — post-hoc relative verdict (`f6c5e7a`, `ea181e6`, run `33500833756`)

- `review_verdict.py` overwrote `success_initial_force_agreement` to **true** by dropping the 1e-8 / 1e-4 absolute residual gates and keeping only `recovered_residual <= stored_residual` plus |Δ| ≤ 0.5%. Artifact renamed `*-reviewed`; `not_recovered_iniforce` dropped from `CASE_BOUND`.
- Numbers unchanged: recovered residual **0.003283**, stored **0.004256**, endpoint **0.184**. Relative `0.003283 < 0.004256` is a comparison diagnostic, not recovered INIFORCE and not attach TA1.
- Absolute gates restored on this stamp. `success_initial_force_agreement` stays **false**. Relative comparison kept as `success_relative_to_stored_mean_force`. Artifact name back to `*-boundary`.

## Wave Q4 — modal from unverified inverse (`59194f7`, `36f82ed`, run `33505293202`)

- New `solve_modal_from_inverse.py` (177 lines) + `.github/workflows/catwalk-modal-from-inverse.yml`. Reuses clean-theory `solve.py` / `solve_v2` / `solve_v3` / `solve_v4_drawing_corrected` (`scipy.sparse.linalg.eigsh`). Not CalculiX. MCT sha `0d18e3f7…`.
- Isolation FAIL on Grok tip: attach 14-family `TARGETS` including TA1 `0.0996` lived inside the solver (Wave M1 already banned this). Comparison now lives only in `compare_after_freeze.py`.
- Workflow `CASE_BOUND` wrote `inverse_force_verified_before_modal=true`. Inverse residual is still **0.0032826 > 1e-8**; stored-INIFORCE residual **0.004256 > 1e-4**; Q3 `success_initial_force_agreement=false`. Body TENSTR |Δ| p95 **0.291%** and the 0.5% force-match gate do not verify INIFORCE. Endpoint residual **0.184**.
- Artifact name was `catwalk-modal-from-mct-inverse-prestress`. Green Actions `33505293202` is a Python `eigsh` zip, not a CalculiX Job finished, not attach 复现.
- Frozen classified frequencies (run `33505293202`): theory TA1 **0.12654451 Hz** vs attach **0.0996** = **+27.05%** (same overlay as v4 drawing-corrected). TS1 0.13030 vs 0.1147 = +13.60%. TS2 0.20377 vs 0.1571 = +29.71% (mode 23, n-order not rematched to TS3). MAE 6.96%, max 29.71%.
- Stamp: `frequency_reproduced=false` `not_attach_ta1=true` `not_ccx_job_finished=true` `inverse_force_verified_before_modal=false` `not_recovered_iniforce=true`. Artifact `*-boundary`. Residual gates 1e-8 / 1e-4 and modal inverse 5e-3 were not loosened.


## Wave Q5 — branch-clean re-label (`035698d`…`7bd7e67`, run `33524823112`)

- New `solve_modal_branch_clean.py` (256) + `solve_modal_branch_clean_v2.py` (72) + `compare_modal_branch_clean_v2.py` + workflow. Same inverse residual **0.0032826 > 1e-8**. Same `eigsh` spectrum as Q4; not CalculiX. MCT sha `0d18e3f7…`. Isolation: attach Hz only in the comparison node.
- Comments and 0.5% force-match gate still called the inverse "verified". It is not. Q3 `success_initial_force_agreement=false`.
- Reclassification drops n-order as a pairing lock and takes rank-2 T-differential-S. TS2 moves from Q4 mode 23 **0.20377 Hz** to mode 14 **0.15187 Hz** (descriptor n=1) vs attach **0.1571** = **−3.33%**. This is a label rematch, not attach TS2, not permission to write 复现 / 一致. Official pairing stays family-order; do not treat the n=1 branch as TS2→closer-to-0.1571.
- Same-spectrum relabels vs Q4: SIDE2 0.12492→0.16590; SIDE3 0.16751→0.19753; VS2 0.18735→0.14542. TA1 stays **0.12654451 Hz** vs attach **0.0996** = **+27.05%**. MAE 9.47%, max 33.90% (SIDE2).
- Green Actions `33524823112` artifact was `catwalk-modal-branch-clean-v2`. `CASE_BOUND` omitted `frequency_reproduced` / `not_recovered_iniforce`. Stamp adds those flags; artifact `*-boundary`. Residual gates 1e-8 / 1e-4 / 5e-3 not loosened.


## Wave Q6 — v3 finalizes the TS2 re-label (`191652d`…`d61a878`, run `33525569463`)

- New `solve_modal_branch_clean_v3.py` + `compare_modal_branch_clean_v3.py` + workflow. Same inverse residual **0.0032826 > 1e-8**. Same `eigsh` spectrum. Isolation: attach Hz only in the comparison node.
- SIDE2/SIDE3 return to Q4 (0.12492 / 0.16751). Official `classified_14` still labels TS2 as mode 14 **0.15187 Hz** (n=1, −3.33% vs attach 0.1571) and parks n=5 **0.20377 Hz** (mode 23) as an "alternate audit". That is still a rematch, not attach TS2, not 复现.
- VS2 official 0.14542 (n=1); n=5 alternate 0.18735. TA1 **0.12654451 Hz** vs attach **0.0996** = **+27.05%**. MAE 5.73%, T-family MAE 14.66%, max 27.05% (TA1).
- `CASE_BOUND` again omitted `frequency_reproduced` / `not_recovered_iniforce`. Comments still said verified MCT force field. Artifact was `catwalk-modal-branch-clean-v3`.
- Stamp: rematch is not official pairing; residual gates 1e-8 / 1e-4 / 5e-3 not loosened; artifact `*-boundary`.



## Wave Q7 — no-passage ablation (`75a228f`, `0bfcd08`, run `33527360519`)

- New `solve_modal_no_passage.py` (209) + `.github/workflows/catwalk-modal-no-passage.yml`. Zeros all 21 transverse-passage K and M, then solves one catwalk `eigsh` and assigns common+differential 14-family labels as exact degenerates. Isolation: no attach Hz / TARGETS / 复现 in the solver. Not CalculiX. MCT sha `0d18e3f7…`.
- Inverse residual is still **0.0032826 > 1e-8**; stored-INIFORCE residual **0.004256 > 1e-4**; endpoint **0.184**. Q3 `success_initial_force_agreement=false`. The 0.5% force-match gate does not verify INIFORCE. Comments, `prestress_state`, and `CASE_BOUND` wrote `verified inverse / verified_inverse_prestress_frozen=true`. That is false.
- Ablation spectrum is not the Q4/Q6 with-passage table. Labeled TA1 **0.07390563 Hz** is the exact degenerate of VA1 (mode 2, n=2). vs attach **0.0996** = **−25.80%**. Near C3 M4 0.07356 / S10 0.0733 is not attach TA1 and not C3 复现.
- Labeled TS2 **0.15038472 Hz** is the exact degenerate of VS2 (mode 11, n=1, 0 zero crossings) vs attach **0.1571** = **−4.27%**. That is the same rematch philosophy as Q5/Q6, now on a different (no-passage) spectrum. Official with-passage pairing stays Q4 n=5 **0.20376923 Hz**.
- Other labeled freqs (run `33527360519`): LS1 0.03808 (+4.33%), VA1 0.07391 (+5.58%), LA1 0.07599 (+4.67%), VS1=TS1 0.10486, LS2 0.11389, SIDE1 0.11991, SIDE2 0.12885, VA2 0.15161, LA2 0.15174, SIDE3 0.17312, VS2=TS2 0.15038. Comparison-only MAE 7.39%, T-family MAE 12.88%, max 25.80% (TA1).
- Artifact was `catwalk-modal-no-passage`. Green Actions `33527360519` is a Python `eigsh` zip, not a CalculiX Job finished, not attach 复现.
- Stamp: drop verified-prestress wording; `frequency_reproduced=false` `not_attach_ta1=true` `not_ccx_job_finished=true` `not_recovered_iniforce=true` `inverse_force_verified=false`; artifact `*-boundary`. Residual gates 1e-8 / 1e-4 / 5e-3 not loosened.



## Wave Q8 — C3 passage parse, not drawing match (`a80a326`…`35b34dc`, runs `33532060376` / `33532492523`)

- New `audit_c3_passage_release.py` + `extract_c3_midspan_passage.py` + two workflows. Both download frozen C3-UB-FT14 parent `667c5047` (26 839 638 B, 91 415 nodes, 172 998 els). Isolation: no attach Hz / TARGETS / 复现. Not CalculiX. Not true3d C4. Inverse residual gates untouched.
- Commit titles said "against drawing geometry" / "drawing audit". No drawing PDF is loaded. Size filter (`node>=100`, max extent `>=30000`, min extent `<=30000`) plus a 339/639 count hint found **0** `passage_candidates` and **0** semantic names (run `33532060376`). That is not a drawing match.
- Extract (run `33532492523`) is a coordinate window around seed `UG64_0084` (52 UCOR6 / 68 nodes): 523 nodes, 1270 els (767 UCOR6 + 439 MASS + 64 UCAB3), 576 equations. Extent 3.036 m × 50.280 m × 9.807 m. Window numbers in comments (1.5 m / 49.655 m / 1.7 m / ~9 m) are heuristics, not a drawing comparison.
- Artifacts were `c3-passage-topology-audit` and `c3-midspan-passage-extract`. Green Python zip is not a Job finished, not recovered INIFORCE, not attach TA1, not a 14-mode table.
- Stamp: `frequency_reproduced=false` `not_attach_ta1=true` `not_ccx_job_finished=true` `drawing_compared=false` `not_passage_drawing_match=true`; artifacts `*-boundary`.

Do not treat this path as the true3d reduced C4 deck.
