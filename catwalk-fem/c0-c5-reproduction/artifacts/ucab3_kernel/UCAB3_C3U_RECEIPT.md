# UCAB3 C3-U release receipt

## Release decision

**PASS for C3-U deck generation and execution.** The immutable binary is:

`/tmp/ucab3-contingency-dmcXjg/work/CalculiX/ccx_2.23/src/ccx_2.23`

SHA-256: `2a7b985edd66e7db401f7ecceebff13fa8551fa312e8187fe4366a0f564e2061`

The minimal patch on the merged C0-SM source is:

`/tmp/ucab3-contingency-dmcXjg/evidence/ucab3_on_c0sm_final.minimal.patch`

SHA-256: `70852b902934494288a770e618db58328ee251188577dfdecac213e7e91c9171`

It replays with `patch -p1 --fuzz=0`, and all ten patched source files then match the build tree. The patch has 298 nonblank added code lines and zero inline-comment violations.

## Frozen input contract

```text
*USER ELEMENT, TYPE=UCAB3, NODES=2, INTEGRATION POINTS=1, MAXDOF=3
...
*USER SECTION, ELSET=<one or more UCAB3 elements>, MATERIAL=<existing material>, CONSTANTS=3
EA_N, N0_N, mu_t_per_mm
```

`EA_N > 0`, `N0_N >= 0`, and `mu_t_per_mm >= 0`. Tension is positive. `N0=0` is the exact C2 axial-member state. The named material must exist because CalculiX requires it on `*USER SECTION`, but UCAB3 ignores its elastic constants and density.

No fourth gravity flag exists. Standard `*DLOAD ... GRAV` membership supplies the acceleration. The element contributes the exact consistent nodal gravity load `mu L g/2` at each endpoint. Native `MASS` elements remain separate; the builder must not duplicate UCAB3 line mass or gravity.

## Exact element semantics

For reference chord length `L` and unit vector `n`:

```text
Q = EA/L n n^T + N0/L (I - n n^T)
K = [[ Q, -Q],[-Q, Q]]
M = mu L/6 [[2I, I],[I, 2I]]
r0 = [-N0 n, +N0 n]
```

The static internal force is `r0 + K d`. Therefore frozen end tractions balance at exactly zero correction in a linear static reference step.

For the static tension gate, request:

```text
*EL PRINT, ELSET=E_ROPES
S
```

For UCAB3, the DAT `Sxx` channel is a generalized axial force in N, not continuum stress:

`Sxx = N0 + EA/L * n dot (uJ-uI)`.

All other reported S channels are zero. Parse the final linear-static reference frame, not modal frames.

## Coupon evidence

| Coupon | Exact expectation | CalculiX result | Verdict |
|---|---:|---:|---|
| Axial stiffness | reaction `100 N` | `100 N` | PASS |
| Positive-N geometric stiffness | transverse reaction `1 N` | `1 N` | PASS |
| Frozen residual | end reactions `[-1000,+1000] N` | `[-1000,+1000] N` | PASS |
| Consistent gravity | free-end `uy=-0.004905 mm` | `-0.004905 mm` | PASS |
| Consistent axial mass | `f1=40.55064083` | `40.55064` | PASS |
| Static-reference perturbation | `lambda1=lambda2=3000` | `3000,3000` | PASS |
| Rotated 3-4-5 full tangent | J force `[295.6,390.8,3] N` | same | PASS |
| `N0=0` transverse null | reaction `0` | `0` | PASS |
| Stock T3D2 A/B | `2N/(Lm)=200` | stock `200`, UCAB3 `200` | PASS |
| UCOR6 + MASS + EQUATION | six positive finite modes | six positive finite modes | PASS |

The decisive A/B uses only `*STATIC, DIRECT` followed by `*STEP, PERTURBATION`; no `NLGEOM` is present. Stock T3D2 and UCAB3 both produce `N=1000 N`, end reactions `[-1000,+1000] N`, and eigenvalue `200.000000`.

## C3-U scope

Replace 73,692 frozen stressed T3D2 members, including the four downpull members, plus 11,529 C2 zero-force axial members: 85,221 UCAB3 elements total. Do not add four again. This is one physical element per source member, with no ROM and no element lumping.

This receipt certifies the binary and coupon boundary. It does not claim that a C3-U full deck has assembled or produced catwalk frequencies.
