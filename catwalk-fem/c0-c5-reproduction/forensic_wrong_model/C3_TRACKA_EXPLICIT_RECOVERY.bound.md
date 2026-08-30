# C3 Track A explicit-height recovery — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `source=agent_constructed_legacy_command_path`.

## Wave F1 — recover (`267a6ab`, run `33341282748`)

Workflow `c3-tracka-recover-explicit-height.yml` searches prior Actions artifacts with fingerprint frequencies `0.09956064`, `0.1111595`, `0.1636203`. Those numbers are a prior-run search key, not attach TA1. `0.09956064` is not attach `0.0996` (Δ=3.936e-5). The job failed at GitHub artifact download `HTTP 401`. No model was selected. `work/results/` was empty. No Job finished. Do not invent a recovered spectrum.

## Wave F2 — track (`4bb3138`, run `33341372762`)

Workflow `c3-tracka-explicit-recovery-track.yml` waits for the recovery artifact, then MAC-tracks against unchanged C3 baseline artifact `9737911706`. The committed tracker labeled frozen C3 mode 3 as `TA1`. Frozen C3 M3 is `0.07267216 Hz`, which is not attach TA1 `0.0996`. That label is withdrawn. Until a recovered daughter has a real Job finished DAT/FRD, do not publish a tracking table.

Do not write 复现, 一致, or 原始人工过程. Do not treat this path as the true3d reduced C4 deck.
