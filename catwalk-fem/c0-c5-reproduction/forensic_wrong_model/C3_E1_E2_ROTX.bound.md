# C3 E1/E2 ROTX — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `source=agent_ultra_s10_section_shear`. `not_attach_ta1=true`.

Actions `33334009151` on `28741ea` used custom-ccx `b498dad8` on frozen C3 `667c5047`. The only matrix change is `*BOUNDARY` ROTX=0 on nodes coordinate-matched (1e-6 mm) to CERIG masters in `apply_finite_gates_and_passages_v2.inp` (`72012ebb…`) taken from the **agent Ultra S10 section-shear** snapshot. That include is not the undisclosed human APDL. No springs, no added mass.

Native Job finished (not the 0-element fake):

| Variant | ROTX nodes | equations | wall | closest to 0.0996 |
|---|---:|---:|---:|---|
| E1_MAIN13 | 26 | 439096 | 3:00.51 | 0.1012167 |
| E1_ALL21 | 42 | 439080 | 2:52.36 | 0.1012167 |
| E2_ALL_MASTERS | 3692 | 435430 | 2:34.81 | 0.1012205 |

First ten native roots / Hz versus frozen C3-UB-FT14:

| Mode | E1_MAIN13 | E1_ALL21 | E2_ALL_MASTERS | frozen C3 |
|---:|---:|---:|---:|---:|
| 1 | 0.03677354 | 0.03677354 | 0.03677491 | 0.03677346 |
| 2 | 0.07144467 | 0.07144467 | 0.07144646 | 0.07144416 |
| 3 | 0.07350459 | 0.07350459 | 0.07350782 | 0.07267216 |
| 4 | 0.1012167 | 0.1012167 | 0.1012205 | 0.07356089 |
| 5 | 0.1101196 | 0.1101196 | 0.1101255 | 0.1012149 |
| 6 | 0.1161726 | 0.1161772 | 0.1161915 | 0.1028555 |
| 7 | 0.1248024 | 0.1248096 | 0.1248306 | 0.1101283 |
| 8 | 0.1456835 | 0.1456835 | 0.1456908 | 0.1161726 |
| 9 | 0.1464486 | 0.1464486 | 0.1464574 | 0.1248024 |
| 10 | 0.1465824 | 0.1465824 | 0.1465918 | 0.1456783 |

None of these is attach TA1 `0.0996`. Do not write 复现, 一致, or 原始人工过程.
