# Clean 44-cable theory path — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_fourteen_mode_table=true`. `kind=mct_topology_diagnostic_only`.

This branch inspects the hash-checked MCT aggregate (`0d18e3f7…`). It is not a 14-mode eigen table, not attach TA1 `0.0996`, and not 复现 / 一致. Do not invent a 14-row attach comparison without DAT/FRD.

## Wave L1 — inspect + green topology JSON (`412f2b5`…`fd31a76`, run `33421724296`)

New branch `feat/catwalk-clean-theory-14modes` from already-reviewed `d372295`.

- `inspect_clean_input.py` walks `ZJG04_bcs` (727 elems, 1 chain), `门架索` (394 elems, 1 chain), 71 portals, 21 floor passages. No attach frequencies in the script or JSON.
- Workflow first failed (`1ae6843` pip-cache / tuple JSON keys; `922e5dd` still tuple keys). `4bad9bc` made keys JSON-safe. Actions `33421724296` success uploaded `clean-catwalk-44cable-modal-results`.
- Bot commit `fd31a76` is 3732-line `input_topology_diagnostic.json` only. `solve_clean_model.py` and `compare_after_freeze.py` are absent.
- Green JSON / artifact name `*-modal-results` is not a Job finished solve and not a 14-mode table.

## Wave L2 — attach MCT source + parser to the inspect zip (`a3d6264`…`6cd1231`, run `33422810017`)

- `a3d6264` put the MCT path on `upload-artifact` next to YAML `#` comments. Actions treated the comments as path text (`33422263751` "No files were found"). Not a model failure.
- `ba978d9` copies the same MCT to transient `artifacts/source_geometry.mct` after the bot commit (no in-tree duplicate). Run `33422810017` success.
- `6cd1231` also copies `parse_mct.py` into the zip. Copied MCT `0d18e3f7…` (448673 B); parser `91963266…`. Existing `mct-from-zero` files, not a new model.
- Still no `solve_clean_model.py`. Green zip with MCT + parser + topology JSON is not a 14-mode table and not attach TA1.

Comparison, if later added, must stay in `compare_after_freeze.py` after freeze. T-family only via three-stack brackets. Relabel any `TA1` on a C3/MCT root to a model-local id.

Do not treat this path as the true3d reduced C4 deck.

## Wave M1 — solver source under catwalk-fem/clean-theory-14modes (`f28294d`)

See `catwalk-fem/clean-theory-14modes/CLEAN_THEORY_14MODES.bound.md`. Attach Hz were stripped out of `solve.py`. No Job finished.

## Wave M2–M4 — solver CI (`50cb382` residual reject → `9572e19` v3 zip)

v1 inverse residual 0.177 rejected. v2 residual 0.003385, T unidentified. v3 theory TA1 0.12608 Hz is not attach TA1 0.0996. Green zip is not 复现.
