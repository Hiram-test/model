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

Do not treat this path as the true3d reduced C4 deck.
