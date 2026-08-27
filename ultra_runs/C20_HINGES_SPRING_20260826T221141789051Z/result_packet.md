# C20 hinge-spring result

- Run: `C20_HINGES_SPRING_20260826T221141789051Z`
- Parent: restored S10 solver includes (CERIG retained)
- Static: LS1/LS2 CNVG=1; mass error 4.43e-10 t; RF rel error 3.08e-11
- Modal: 80/80 exported
- TA1 candidate (mode 4): **0.073813 Hz** vs S10 0.073800 Hz vs v5 0.10003 Hz

## What was tried

| Variant | Change | Static |
|---|---|---|
| both-end free ROTY pin | 568 CERIG pin | Failed, UX 6.3e9 (XZ parallelogram) |
| top-only free ROTY pin | 284 CERIG pin | Diverged at min dt=0.005 |
| **both-end pin + COMBIN14 ROTY K=1e8 N·mm/rad** | 568 pin + 568 springs | **Passed** |

## Frequency vs S10 (first 10)

C20 frequencies match S10 to ~1e-5 Hz. Gate-post hinges are not the missing TA1 restoring stiffness.
