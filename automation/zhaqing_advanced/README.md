# Zhaqing L3 nonlinear prestressed screening model

This directory contains a compressed deterministic generator and pipeline for the upgraded whole-bridge model.

Model additions over the validated L2 S4 baseline:

- 0.5 m longitudinal S4 deck mesh;
- separate shell/beam nodes with 180 mm rigid eccentricity equations;
- two-step `NLGEOM=YES` static analysis;
- dead-load-derived cable and hanger prestrain targets;
- automated inverse calibration against completed-geometry dead-load midspan displacement;
- P075/P100/P125 prestress sensitivity for key service/extreme cases;
- fully expanded ASCII INP decks using the common CalculiX/Abaqus keyword subset.

Engineering release remains `BLOCKED`. The thermal prestrain is a transparent inverse-analysis proxy for missing accepted unstressed cable lengths and erection-stage data.
