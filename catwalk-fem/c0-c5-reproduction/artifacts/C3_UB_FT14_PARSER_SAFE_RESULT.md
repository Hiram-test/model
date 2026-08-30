# C3 parser-safe fourteen-mode result

## Scope

This receipt freezes the completed CalculiX C3 upper-bound frozen-tangent modal run. The model keeps the C3 topology, sticky saddles, locked downpull equalizers, explicit transverse four-port framing, and the previously frozen geometry, tension, and mass state. No target-frequency fitting was applied.

## Parser correction

CalculiX 2.23 reads each `*USER SECTION` constant through an `f20.0` field. The former 21-character `.15e` UCAB3 line-mass token lost the final exponent digit during parsing, turning values on the order of `e-05` or `e-04` into `e-00`.

The corrected deck rewrites all 73,692 UCAB3 line-mass tokens with `.12e`. Geometry, constraints, tangent stiffness, prestress, and intended physical mass remain unchanged. The maximum relative serialization change is `3.429598065690985e-13`.

## Solver result

- Nodes: 91,415
- Elements: 172,998
- Active equations: 439,122
- Lower-triangle nonzeros: 4,024,459
- Requested and normalized modes: 14
- Symmetric spectral shift: `-0.001`
- Solver binary SHA-256: `b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e`
- Eigen-shift patch SHA-256: `7b1004adac070f1308bc6956377b37b0b5517aca3bf88aa0e98db98689d7ff88`

| Mode | Frequency (Hz) |
|---:|---:|
| 1 | 0.03677346 |
| 2 | 0.07144416 |
| 3 | 0.07267216 |
| 4 | 0.07356089 |
| 5 | 0.1012149 |
| 6 | 0.1028555 |
| 7 | 0.1101283 |
| 8 | 0.1161726 |
| 9 | 0.1248024 |
| 10 | 0.1456783 |
| 11 | 0.1464436 |
| 12 | 0.1465091 |
| 13 | 0.1465538 |
| 14 | 0.1491063 |

## Physical interpretation

The C3 stiffness upper bound does not reproduce the two required fingerprints:

- Computed M3, not M4, is the differential vertical branch: dominant `UZ`, left-right `UZ` mirror correlation `-0.9999999984`, and common-vertical fraction `5.29e-08`.
- Computed M4 remains lateral-dominant: `UY` energy fraction `0.93675` at `0.07356089 Hz`; it is not the required `0.0996 Hz` TA1 branch.
- Computed M14 is also differential vertical: left-right `UZ` mirror correlation `-0.9999999985` and common-vertical fraction `5.00e-08`; it is not the required common-vertical VS2 branch near `0.1744 Hz`.

This is therefore a valid C3 modal calculation and a negative reproduction result, not an independent match to the attachment spectrum.

## Immutable identities

- Parser-safe input SHA-256: `667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86`
- Solver DAT SHA-256: `329a017f0356504ea5a360488ae0f87adfa39dae507119bdb9e622fb139c1208`
- Mode CSV SHA-256: `ff1d792e8af0d31fd20d46fed8468c1ac0dde066e7a8406ff4af72275ab76d1d`
- Mode JSON SHA-256: `db03c70e466d9a821f1bce2575df04d105e3fe27d383cb9707f48e78e6b03514`

The 112 MB FRD and other transient solver files are intentionally excluded from version control. The committed input deck, DAT table, classification records, generators, and UCAB3 patch evidence are the review package.
