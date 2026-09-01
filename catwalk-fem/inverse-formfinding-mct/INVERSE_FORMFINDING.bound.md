# Input boundary

Allowed before solve: verified MCT formed node coordinates; all 1194 element incidences and section/material definitions; MCT self-weight declaration; stage-two nodal load vectors; MCT restraint topology.

Forbidden before solve: `INIFORCE`, `INI-EFORCE`, `EQUI-MFORCE`, C3/S10/B00 modal data, target frequencies, previous inverse-force results, frequency-based tuning.

Validation after solve: compare recovered TENSTR forces elementwise with MCT `INIFORCE`, with separate reporting for the 727 floor-chain members, two down-pull members, and 394 gantry-rope members.
