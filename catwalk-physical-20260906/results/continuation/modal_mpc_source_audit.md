# Local modal MPC source audit — 2026-09-06

The two local spectra in `results/connection_research_modes` cannot currently establish physical stability or instability. The observed modes violate the intended beam-to-clip connection, and official CCX 2.23 source identifies a specific unresolved-MPC-chain path that affects matrix assembly as well as displacement recovery. This audit does not change the production model, solver, or restraints and includes no new native run.

## The analysis keywords are appropriate

Both local inputs contain a converged `*STEP,NLGEOM` / `*STATIC`, followed by `*STEP,PERTURBATION` / `*FREQUENCY`. The [official CCX 2.23 manual](https://dhondt.de/ccx_2.23.pdf), sections 6.9 and 7.125, defines the preceding static stress and deformation as the reference state for this perturbation procedure. `NLGEOM` is not added directly to the frequency step. No general prohibition on using a rigid body in frequency analysis was found. The parser retains `iperturb(1)=1` for the explicit perturbation step (`steps.f` and `frequencys.f`).

The issue is the handling of this model's chained constraints between analysis procedures, rather than the spelling of the frequency keywords.

## Official source identifies a missing chain-expansion path

Source below was checked directly in the [official CCX 2.23 source archive](https://www.dhondt.de/ccx_2.23.src.tar.bz2), the same upstream URL used by `build_joint_solver.py`. The project patch changes only `gen3dnor.f`; the routines below are upstream routines. Line references refer to the archive's original files.

| Routine | Evidence | Consequence for these inputs |
| --- | --- | --- |
| `cascade.c`, 104–179 | A nonlinear MPC that depends on another MPC sets `icascade=2`; a call from main then leaves that dependency for the nonlinear procedure to handle. | The RIGID → proxy EQUATION → beam KNOT chain requires repeated expansion during nonlinear iterations. The native static log explicitly reports a common MPC node. |
| `nonlingeo.c`, 782–790 and 4126–4135 | When `icascade==2`, the routine saves the incoming unexpanded `nodempc` and `coefmpc` arrays, and restores them before returning. | Successful static convergence does not mean the returned MPC arrays contain the expanded constraints used in the final static solve. |
| `ccx_2.23.c`, 701 | Main resets `icascade=0` for frequency analysis. | The nonlinear dependency flag no longer triggers restructuring by itself. |
| `ccx_2.23.c`, 1161–1174 | Main calls `cascade` only on the first step, for transforms, an MPC-change flag, or changed node/MPC counts. | The unchanged second step does not automatically expand the restored MPC chain. |
| `arpack.c`, 208–359 | Its `remastructar` call is inside the contact branch. There is no call to `nonlinmpc` in `arpack.c`. | These inputs have no contact and get no later chain-expansion pass through this branch. |
| `mafillsm.f`, 411–439 and 469–550 | Element assembly substitutes one MPC level. Terms contribute to the ordinary stiffness/mass matrices only when their resulting `nactdof` is positive; a nested dependent MPC DOF is a negative odd index and receives no recursive substitution. | If the restored chain reaches assembly, contributions linking the clip-side spring elements to the beam coordinates are omitted. This affects the eigenproblem itself. |
| `resultsini.c`, 230–309 | Dependent modal displacements are recovered by one pass through MPC declaration order, using current values of the independent-side coordinates. | A RIGID clip processed before its proxy EQUATION can remain zero even when that proxy is subsequently recovered as nonzero. This additionally affects output recovery. |

The local input declares the rigid bodies before the proxy equations. For example, the first rigid body uses reference node 38; the static log reports node 38, direction 1, as the shared linear/nonlinear MPC coordinate. After static convergence, the log prints a new matrix structure with 376 equations but no intervening `Decascading the MPC's` message. This is consistent with the exact source path above.

The separate vector review finds all 16 spring-clip translations exactly zero in all 20 modes while the physical beam coordinates move. Together, the runtime observation and the source path establish a concrete constraint-consistency defect to resolve before accepting these spectra. An instrumented or corrected comparison has not yet been run; the amount by which each eigenvalue changes remains unknown.

## What the evidence supports

The current BOX50 negative roots, including approximately −0.20168 and −0.20161, and BOX100 near-zero roots remain actual native outputs, but are not validated eigenvalues of the intended connected system. They should not be relabelled as proof of the real catwalk's instability, nor should they be dismissed as ordinary roundoff merely because their magnitudes are small. The anomaly has a source-backed assembly explanation in addition to a recovery explanation.

A later solver correction must retain or recompute the MPC linearization at the converged reference configuration and expand its dependency chains before matrix assembly. Reconstructing the printed clip motion alone would not validate the existing eigenvalues. Acceptance would require checking the connection tangent residual `C φ` for the recovered modes and confirming the same constraints enter the stiffness and mass transformations. No such correction or validation is claimed here.

The separate three-case MASS-only pendulum experiment is invalid for this question: native exit code 0 accompanies the warning that the model has no degrees of freedom and an equation count of zero. Its zero displacements and reactions provide no evidence about nonlinear MPC gravity tangent behavior. This source audit therefore draws no conclusion from that experiment.
