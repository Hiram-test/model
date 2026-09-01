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

Do not treat this path as the true3d reduced C4 deck.
