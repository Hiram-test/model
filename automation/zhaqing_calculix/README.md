# Zhaqing CalculiX / Abaqus screening analysis

This directory contains the compressed deterministic generator used by `.github/workflows/zhaqing-calculix.yml`.

The active global model uses the common CalculiX/Abaqus keyword subset:

- `S4` equivalent deck shell, 50 mm nominal thickness and approximately 1 m longitudinal mesh;
- `B31` longitudinal girders, crossbeams, towers and the regularized main-cable surrogate;
- `T3D2` hangers and wind cables;
- `MASS` elements for distributed accessories and non-structural deck mass.

The shell is connected to the longitudinal and transverse beam grid through shared nodes. The earlier diagonal `DECK_BRACING` surrogate has been removed so deck in-plane stiffness is not counted twice. Shell density is calibrated so the 78 drawing-controlled deck-panel masses close exactly in the generated model; a separate distributed mass represents the documented screening allowance for accessories and railings.

The generated `.inp` files are completely expanded, ASCII, do not use `*INCLUDE`, and stay within the common keyword set used by both CalculiX and Abaqus/Standard.

This remains a global screening model. Panel joints, composite connection stiffness, fabrication-state cable prestress, unstressed cable lengths, construction stages, anchor-foundation flexibility and several local interfaces are not closed by the source drawings. Engineering release therefore remains `BLOCKED`.
