# Zhaqing L3 nonlinear prestressed screening model

This directory contains the deterministic generator bundle for the upgraded
whole-bridge comparison model.

## Additions over the validated L2 S4 baseline

- 0.5 m longitudinal S4 deck mesh (984 deck shells);
- B31 longitudinal/crossbeam grid with 180 mm physical section offsets;
- one permanent-load equilibrium step followed by a variable-load step;
- `NLGEOM=YES` in every step so cable initial-stress and load-stiffness effects enter the tangent stiffness;
- source-traceable thermal-prestrain proxies for main cables, hangers and wind cables;
- automated inverse calibration against completed-geometry dead-load midspan displacement;
- P075/P100/P125 prestress sensitivity for the service-crowd and extreme-combination cases;
- fully expanded ASCII INP decks using the common CalculiX/Abaqus keyword subset.

LC01 ends after the converged permanent-load equilibrium state. Other cases
inherit that temperature/prestrain and gravity state and update only their total
nodal load vector; unchanged permanent actions are not reset with `OP=NEW`.

Engineering release remains `BLOCKED`. The thermal prestrain is a transparent
inverse-analysis proxy for missing accepted unstressed cable lengths, measured
elastic moduli, saddle pre-offsets and erection-stage data. The continuous S4
deck also assumes full composite action with the beam grid; real panel joints,
slip and local connection hardware require separate calibrated local models.
