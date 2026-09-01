# MCT geometry inverse form-finding — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_fourteen_mode_table=true`. `not_ccx_job_finished=true`. `not_recovered_iniforce=true`.

Input boundary (Grok): allowed before solve = MCT formed coordinates, 1194 element incidences, self-weight, stage-two nodal loads, restraint topology. Forbidden before solve = `INIFORCE` / `INI-EFORCE` / `EQUI-MFORCE`, C3/S10/B00 modal data, target frequencies, previous inverse-force results, frequency-based tuning.

Family label `TA1` is not attach TA1 `0.0996`. Do not write 复现 / 一致.

## Wave Q1 — input boundary only (`7773f0a`, `77c020f`)

- New directory `catwalk-fem/inverse-formfinding-mct/` on `feat/catwalk-clean-theory-14modes`: 3-line README + this bound. No solver, no workflow, no `results/`.
- Isolation of the bound text is OK (target frequencies forbidden). The bound itself is not a solve and not a recovered cable-force field.
- zhaqing-prestress Actions failures on this push are unrelated.

Do not treat this path as the true3d reduced C4 deck.
