# Track A scalar equivalent — CalculiX 2.21 verification

Status: `OPERATOR_SELF_CONSISTENT`

Evidence boundary:

- `frequency_reproduced=false`
- `back_tuned=true`
- `attach_reproduction=false`
- This verifies only that the retained Track A scalar `K/M` operator is represented correctly in a runnable CalculiX input.
- It does not prove that the undisclosed APDL used the same causal mechanism.

## Executed input

- File: `TrackA_five_frequency_CCX_noMPC_robust.inp`
- Input SHA-256: `689037cfa52b556bc3debe7175fc4ae06fd71eac5b5ad5162d963c5197d7f380`
- Deck formulation: native `SPRING1` plus `MASS`; no `T3D2`, no `*EQUATION`, no `*CLOAD`, no nonlinear prestress step.

## Solver

- CalculiX version: `2.21`
- Workflow run: `33330827371`
- Workflow result: `success`
- Native solver termination: `Job finished`

## Native frequencies

These five roots match the inverse-fit W2 `K/M` algebra (max `|Δ| = 3.13e-8 Hz`)
because each `SPRING1` stiffness was chosen from that table. This is operator
self-consistency, not attach TA1 / TS1 / VS2 reproduction.

| Mode | Algebra / Hz | CCX 2.21 / Hz |
|---:|---:|---:|
| 1 | 0.0996000000 | 0.0996000 |
| 2 | 0.1150435687 | 0.1150436 |
| 3 | 0.1556126225 | 0.1556126 |
| 4 | 0.1566294277 | 0.1566294 |
| 5 | 0.1751835898 | 0.1751836 |

The two earlier decks are invalid for delivery:

1. Long-field `*CLOAD` deck: input parsing failure.
2. Parser-safe NLGEOM/MPC deck: `*ERROR in add_bo_st: coefficient should be 0` during modal assembly.
