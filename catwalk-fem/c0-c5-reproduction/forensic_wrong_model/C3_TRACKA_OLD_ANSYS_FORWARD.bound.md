# C3 Track A hypothesized command-path forward — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `source=agent_constructed_hypothesized_command_path`.

This wave is not undisclosed human APDL and not attach TA1. Do not write 复现 or 一致.

## Wave G1 — publish (`eb71622`, run `33341567141`)

Workflow `c3-tracka-publish-explicit-result.yml` polls for `C3-TrackA-explicit-height-recovery` and `C3-TrackA-explicit-model-tracking`. Recovery artifact `9740725121` is 283 B case.txt from the failed HTTP 401 recovery. Tracking artifact is absent. No entity INP, DAT, or FRD. INCOMPLETE is not a solve.

## Wave G2 — release (`b8d4a89`, run `33341658780`)

Workflow `c3-tracka-release-explicit-result.yml` requires both prerequisite artifacts. Tag `c3-tracka-explicit-forward-20260831` does not exist. Do not treat a later package as attach TA1 复现.

## Wave G3 — static mother (`8ab7c1e`, run `33341900303`)

Workflow `c3-exact-static-mother-recovery.yml` Actions conclusion is success, but `C3_STATIC_MOTHER_RECOVERY.json` is `status=NOT_FOUND`. `artifact_count_considered=301`, `download_errors=301` all `HTTP 401`. `candidate_deck_count=0`. `selection_found=false`. No `C3_EXACT_NLGEOM_STATIC_MOTHER.inp`. A green job that wrote NOT_FOUND is not a recovered mother.

## Wave G4 — merger + tracker (`ead39b9`, `7411f30`)

`build_tracka_old_ansys_forward.py` is target-blind (`target_frequency_used=false`) and forbids surrogate springs. That is construction hygiene, not APDL provenance.

`track_tracka_old_ansys_modes.py` used global one-to-one MAC (good) but labeled frozen C3 mode 3 as `TA1`. Frozen C3 M3 is `0.07267216 Hz`, which is not attach TA1 `0.0996`. Labels are withdrawn to `C3_M*`.

## Wave G5 — forward chain (`2674e9f`, run `33342111283`)

Workflow `c3-tracka-old-ansys-forward.yml` failed at `gh release download c3-tracka-explicit-forward-20260831` with `release not found`. Solver, merger, and tracker were skipped. No Job finished. Do not invent an eighty-mode spectrum.

## Wave I1 — rebuild kit (`3359589`, run `33358611771`)

Workflow `c3-tracka-export-rebuild-kit.yml` failed decoding incomplete `build_legacy_tracka_main13.py.gz.b64.part*` (`base64: invalid input`). No kit uploaded. Incomplete part00 is not a generator.

## Wave I2 — rebuild kit (`923f2b0`, run `33358783510`)

Same workflow dropped the broken main13 fragments and uploaded `C3-TrackA-reconstruction-kit`. Contents are source only: C3 parent sha `667c5047`, custom ccx sha `b498dad8`, already-stamped hypothesized builders, and copies of Track A yml files. Green export is not a Job finished solve and not a recovered entity. `human_apdl=false`. `frequency_reproduced=false`. `not_attach_ta1=true`.

Do not treat this path as the true3d reduced C4 deck.
