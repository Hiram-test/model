# C3 E4 topology high-master — evidence bound

`frequency_reproduced=false`. `human_apdl=false`. `source=agent_ultra_s10_section_shear`. `not_attach_ta1=true`.

Actions `33336135321` on `ccc1d45` used custom-ccx `b498dad8` on frozen C3 `667c5047`. The only matrix change is rewriting existing passage CERIG equations so selected UXYZ rope and/or ALL passage relations use portal-top masters derived from `apply_finite_gates_and_passages_v2.inp` (`72012ebb…`) in the **agent Ultra S10 section-shear** snapshot. That include is not the undisclosed human APDL. Heights are topology-derived (min 7994.5 mm, mean 8547.97 mm, max 9080.40 mm), not Track A inverse 9.069 m and not attach TA1. No springs, no added mass. Linearization stays the parent N0; no re-equilibration after rewire.

Native Job finished (not the 0-element fake), 172998 elements, 439122 equations, 40 roots:

| Variant | wall | first-14 max\|Δ\| vs frozen C3 | closest to 0.0996 |
|---|---:|---:|---:|
| CONTROL_BOTTOM_MAIN13 | 2:34.99 | 0 | 0.1012149 |
| E4_ROPE_MAIN13 | 2:34.02 | 1.46e-5 | 0.101215 |
| E4_PASSAGE_MAIN13 | 2:53.08 | 1.35e-4 | 0.1012152 |
| E4_ALL_MAIN13 | 2:35.27 | 1.35e-4 | 0.1012152 |
| E4_ALL_ALL21 | 2:35.69 | 1.35e-4 | 0.1012152 |

CONTROL first 14 Hz byte-match frozen C3-UB-FT14. High-master daughters stay on the frozen M5 cluster near 0.101215 Hz. None is attach TA1 `0.0996`. Do not write 复现, 一致, or 原始人工过程.
