# C3 Track A legacy command-path — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `source=agent_constructed_legacy_command_path`. `not_attach_ta1=true`.

Parent remains frozen C3-UB-FT14 `667c5047` plus common-observation deck `50250d6f` and custom-ccx `b498dad8`. Added operations are agent-written `*BOUNDARY` / `*EQUATION` blocks on existing gate or passage masters. They are not the undisclosed human APDL. No springs, no added mass, no true3d overwrite. Actions green with `continue-on-error: true` is not a solve.

## Wave D1 — geometric high-endpoint ROTX (`cd08831` / `8b310ae`)

- v1 run `33338129131`: all five jobs failed at `base64: invalid input` on the unwrapped single-file stream. No Job finished.
- v2 run `33338357070`: four `E4_GATE_TOP_RX*` jobs died in `cascade` (SPC+MPC on node 79492 ROTX, CCX_EXIT=201). Only `END_HIGH_UZ_PAIR_ONLY` reached Job finished: 174786 elements, 439120 equations, wall 3:00.09. First 14 Hz stay on the frozen C3 table (max |Δ| ~3.7e-6). Closest to 0.0996 is frozen M5 **0.1012149**.

Endpoint-column heights from C3: 7144–8940 mm (mean 8366 mm). Not Track A inverse 9.069 m.

## Wave D2 — independent-master ROTX (`f650d64`, run `33338804058`)

All five jobs Job finished (not the 0-element fake), 174786 elements. Independent-master lever arms: 7312–9108 mm, mean 8533.56 mm.

| Variant | eqs | wall | first-14 max\|Δ\| vs frozen C3 | M4 (Hz) | closest to 0.0996 |
|---|---:|---:|---:|---:|---:|
| E4_GATE_MASTER_RX | 438838 | 2:36.85 | 0.02329 | 0.09684961 | 0.1012165 |
| E4_GATE_MASTER_RX_END_HIGH_RX | 438834 | 2:36.35 | 0.02330 | 0.09685638 | 0.1012165 |
| E4_GATE_MASTER_RX_END_HIGH_RX_PAIR | 438836 | 2:52.27 | 0.02330 | 0.09685638 | 0.1012165 |
| E4_GATE_MASTER_RX_END_HIGH_UZ_PAIR | 438836 | 2:35.87 | 0.02329 | 0.09685056 | 0.1012165 |
| END_HIGH_UZ_PAIR_ONLY | 439120 | 2:41.59 | 3.7e-6 | 0.07356101 | 0.1012149 |

Fixing 284 independent high-master RX remaps frozen M3 `0.07267` and inserts a fourth root near **0.09685 Hz**. That root is not attach TA1 `0.0996` (Δ≈0.00275). Closest native root remains the frozen M5 cluster **0.1012165**.

## Wave E — thirteen main-span passages (`1aaf739`, run `33339804665`)

Generator `build_legacy_tracka_main13_v1` (decoded sha `a7029417` before this stamp) selects 52 or 26 independent high masters at 13 existing main-span passage abscissae and applies RX, plus optional endpoint UX/UY/UZ. The earlier single part `build_legacy_tracka_main13.py.gz.b64.part00` is an incomplete/invalid base64 stream and was not solved. All seven matrix jobs Job finished, 174786-class C3 daughters. Master heights 7994.5–9080.40 mm (mean 8547.97 mm) are C3 passage geometry, not Track A inverse 9.069 m.

| Variant | eqs | wall | M4 (Hz) | closest to 0.0996 |
|---|---:|---:|---:|---:|
| E1_MAIN13_ALL4_RX | 439070 | 2:18.33 | 0.09132949 | 0.1012155 |
| E1_MAIN13_INNER_RX | 439096 | 2:21.94 | 0.08103383 | 0.1012154 |
| E1_MAIN13_OUTER_RX | 439096 | 2:17.97 | 0.08094606 | 0.1012149 |
| E1_MAIN13_ALL4_RX_END_HIGH_RX | 439066 | 2:36.44 | 0.09133677 | 0.1012155 |
| E1_MAIN13_ALL4_RX_END_HIGH_UZ | 439066 | 2:36.75 | 0.09133058 | 0.1012194 |
| E1_MAIN13_ALL4_RX_END_HIGH_UY_UZ | 439062 | 2:53.93 | 0.09133172 | 0.1012194 |
| E1_MAIN13_ALL4_RX_END_HIGH_UXYZ | 439058 | 2:43.03 | 0.09133353 | 0.1012625 |

ALL4 RX remaps frozen M3 and inserts ~0.09133 Hz. INNER/OUTER insert ~0.081 Hz. None is attach TA1 `0.0996`. Closest native root remains the frozen M5 cluster **0.10121**. Do not write 复现, 一致, or 原始人工过程.

Do not treat Ultra-C4 / C3 forensic daughters as the true3d reduced C4 deck.
