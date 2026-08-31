# Clean theoretical catwalk 14-mode calculation

This branch keeps the calculation independent from C3/S10 modal matrices and target frequencies. MCT supplies formed geometry and topology only. The solver reconstructs prestress from equilibrium, assembles 16 floor ropes and 6 gantry ropes per catwalk, equivalent portal frames, and 21 transverse passages, then classifies physical mode families before loading external target frequencies.
