# D10 downpull ear-plate result

- Parent: `C20_HINGES_SPRING_20260826T221141789051Z`
- Static: LS1/LS2 CNVG=1; mass error 4.47e-10 t; RF rel error 7.35e-11
- Modal: 80/80 exported
- Four near-zero modes: lower ear-plate ROTY spin (16 cables coplanar at each tower). Physical spectrum starts at mode 5 = 0.036822 Hz.
- Physical TA1 = mode 8 = **0.073809 Hz** (same as S10/C20)

As-run input did **not** constrain master ROTY. Adding `D,9000x,ROTY,0` would remove the four zeros without changing TA1; that rerun was not launched because TA1 is already known to be insensitive.
