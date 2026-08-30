# C3 forensic ROTX/LINK binary matrix — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `not_attach_ta1=true`. `not_undisclosed_human_apdl=true`.

New branch `agent/c3-forensic-binary-20260831` from `d372295`. The gzip builder at `deaa326` (`18c7ed76…` / source `651e1fd9…`) is a target-blind ROTX and LINK/high-pilot hypothesis set on frozen C3 `667c5047`. The 9.08 m uniform height is a template number, not attach TA1 and not the Track A inverse 9.069 m. Receipt already says the unavailable original APDL cannot be proved.

Actions `33336166862` on `deaa326` used custom-ccx `b498dad8`. All 14 cases reached native Job finished (not the 0-element fake), 172998 elements, 40 roots:

| Case | eqs | wall | closest to 0.0996 | first-14 max\|Δ\| vs frozen C3 |
|---|---:|---:|---:|---:|
| BASE40 | 439122 | 2:48.82 | 0.1012149 | 0 |
| ROT_MAIN13_CENTER | 439096 | 2:56.10 | 0.1012167 | 0.02951 |
| ROT_ALL21_CENTER | 439080 | 2:35.07 | 0.1012167 | 0.02951 |
| ROT_MAIN13_GATE_BOTTOM | 439074 | 2:52.38 | 0.1012161 | 0.02905 |
| ROT_ALL_GATE_BOTTOM | 439050 | 2:49.69 | 0.1012161 | 0.02905 |
| ROT_ALL_GATE_TOP | 439050 | 2:36.24 | 0.1012153 | 0.01777 |
| ROT_MAX_GATE_BOTTOM | 439118 | 2:23.82 | 0.101215 | 0.00394 |
| ROT_CENTER_PLUS_GATE_BOTTOM | 439008 | 2:50.06 | 0.101217 | 0.02951 |
| LINK_ZERO_ALL | 438906 | 2:35.79 | 0.1012183 | 0.02952 |
| LINK_HIGH_ALL_REAL | 438906 | 2:35.59 | 0.101218 | 0.02952 |
| LINK_HIGH_MAIN13_REAL | 438978 | 2:38.25 | 0.101218 | 0.02952 |
| LINK_HIGH_MAX_REAL | 439110 | 2:49.72 | 0.101215 | 0.00874 |
| LINK_HIGH_ALL_9080 | 438906 | 2:20.44 | 0.101218 | 0.02952 |
| LINK_TOP_ALL | 438906 | 2:58.32 | 0.10122 | 0.02952 |

BASE40 first 14 Hz byte-match frozen C3-UB-FT14. ROT/LINK daughters drop frozen M3 `0.07267` and land nearest 0.0996 on the 0.10122 cluster (same neighborhood as E1/E2/E3). None is attach TA1.

`06037ee` added `c3-forensic-top-end.yml` (END4 / LEFT2 / RIGHT2 tower-downpull ROTX on BASE40 or ROT_ALL_GATE_TOP). Actions `33336971997` failed before solve: the insertion `awk` used `index` as a loop variable, which is an awk builtin. No Job finished and no frequencies for those four cases.

Do not write 复现, 一致, or 原始人工过程.
