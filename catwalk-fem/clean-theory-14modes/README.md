# Clean theoretical catwalk 14-mode calculation

This branch keeps the calculation independent from C3/S10 modal matrices.
MCT supplies formed geometry and topology only. `solve.py` reconstructs
prestress from equilibrium and classifies physical families. It does not
load attachment frequencies.

Compare only with `compare_after_freeze.py` after `results/frozen_results.json`
exists. Family label TA1 is not attach TA1. `frequency_reproduced=false`.
A source file without `results/` is not a 14-mode table.
