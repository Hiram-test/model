# C20_HINGES

- Parent: `S10_SECTION_SHEAR_20260716T050342389124Z` (CERIG retained, S10 shear sections frozen)
- Change: 568 gate-post `CERIG,ALL` -> `CERIG,UX,UY,UZ,ROTX,ROTZ` (release ROTY)
- Unchanged: 1386 passage-interface ALL, 3124 cable UXYZ, mesh, mass, loads, downpull
- Pin axis: global Y (transverse, along top/bottom beams)
- Why not release ROTX: that would turn the YZ portal into a 4-bar and destroy the height couple needed by TA1
