# C3 Track A explicit-height recovery — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `source=agent_constructed_legacy_command_path`.

## Wave F1 — recover (`267a6ab`, run `33341282748`)

Workflow `c3-tracka-recover-explicit-height.yml` searches prior Actions artifacts with fingerprint frequencies `0.09956064`, `0.1111595`, `0.1636203`. Those numbers are a prior-run search key, not attach TA1. `0.09956064` is not attach `0.0996` (Δ=3.936e-5). The job failed at GitHub artifact download `HTTP 401`. No model was selected. `work/results/` was empty. No Job finished. Do not invent a recovered spectrum.

## Wave F2 — track (`4bb3138`, run `33341372762`)

Workflow `c3-tracka-explicit-recovery-track.yml` waits for the recovery artifact, then MAC-tracks against unchanged C3 baseline artifact `9737911706`. The committed tracker labeled frozen C3 mode 3 as `TA1`. Frozen C3 M3 is `0.07267216 Hz`, which is not attach TA1 `0.0996`. That label is withdrawn. Until a recovered daughter has a real Job finished DAT/FRD, do not publish a tracking table.

## Wave H1 — artifact rescue (`d8ea232` / `865bb13`, runs `33358186961` / `33358444871`)

Workflow `c3-tracka-artifact-rescue.yml` listed 1109 artifacts, filtered 360, downloaded 120, ranked 93. `exact_found=false`. `selected=null`. No candidate had `numerical_fingerprint` or `structural_exact`. All 93 parsed INPs had `added_node_count=0`. Parsed DAT frequency count is 0. 77 logs say Job finished; those are already-reviewed C3 parent/patch jobs, not the hypothesized explicit-height daughter. Green JSON is not a recovered model. `0.09956064` is not attach `0.0996` (Δ=3.936e-5). Do not invent an 80-mode table. Do not label frozen C3 M3 `0.07267216 Hz` as TA1.

Do not write 复现, 一致, or 原始人工过程. Do not treat this path as the true3d reduced C4 deck.
