# Agentic FEA of the Zhangjinggao Construction Catwalk

**From a published centerline STEP to a hashed, coordinate-gated CalculiX deck**

Run `catwalk-main-deck-gate-f23d`. Geometry: Release `catwalk-attachment23-v2.0-s10-20260716`  
`cw_S10_0716t050342_a4_centerline.step` SHA-256 `d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344`.  
Main deck SHA-256 `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da`.  
Gate ledger: 26/26 PASS. CalculiX (`ccx`) was **not** executed.

## Abstract

This paper records an end-to-end agentic finite-element modelling run for the Zhangjinggao construction catwalk. A 77 MB millimetre STEP of member centre-lines is parsed, mapped into the project convention \(x=\text{chainage}-K16+876.000\), classified against drawing topology, coarsened, and written as a complete CalculiX `.inp`. The run forbids reading the companion S10 `.db`, B00, MCT, or TARGET-FREQ. Floor-rope and portal-rope anchors are separate `*NSET` / `*BOUNDARY` families. Twenty-one cross-passages and 142 portal frames (71 per deck) are reconciled against the drawing station lists; both counts close with zero drawing insertions. The hashed deck is the deliverable. Frequency targets stay isolated. The environment has no `ccx` binary, so this paper issues a pre-solve certificate only.

## 1. Introduction

### Related work

Automated CAD-to-FEM pipelines exist for buildings and bridges, but they usually inherit an already-consistent coordinate system and a single support family. Construction catwalks break that assumption: two walkways, two rope families with different anchor stations, discrete portals, and discrete passages, all written in chainage.

### Method

The run follows `catwalk-fem/SKILL.md` and `PLAN.md`. Geometry is STEP-only. Materials, sag, and loads come from drawings and the check report. The coordinate gate is a hard stop: identity unless saddle-height evidence requires a shift, and never `X-xmin`.

### Experiment

The published centre-line STEP (139 991 trimmed curves, `SI_UNIT(.MILLI.,.METRE.)`) is converted to metres. After identity mapping, \(X\in[0,4270.609]\) m, \(Z_{\max}=350.312\) m. The written deck has 51 896 nodes and 30 317 elements.

### Outlook

A later run should execute CalculiX and only then open TARGET-FREQ. North physical anchors lie outside this STEP and remain proxies.

## 2. Related work and isolation protocol

Agentic FEA here means a scripted, auditable chain with frozen constants, not a chat that invents sections. Isolation rules:

1. STEP supplies coordinates.
2. Properties come from DRW-A/B, CALC-INPUT, STD, or named ASSUMP.
3. TARGET-FREQ lives in `catwalk-fem/isolated/` and is not imported by `write_inp` or the solver deck.
4. Formed sag is \(h=227.300\) m (\(340.600-113.300\)). The 255.56 m main-cable control sag is forbidden in the deck (verified absent).
5. Two decks keep independent DOF; no mirror constraint.

## 3. Charter, evidence grades, and frozen constants

The charter (`artifacts/analysis_charter.json`) freezes: project `zjg-catwalk`, run `catwalk-main-deck-gate-f23d`, SI internal units, and the four load cases LC-DEAD-PRESTRESS, LC-PERSONNEL-UNIFORM, LC-WIND-Y, LC-FREQ.

Evidence grades follow theory v1.2: DRW-A/B, CALC-INPUT, STD, TEST, ASSUMP. Portal and passage stations are DRW-B dimension chains. Saddle coordinates are CALC-INPUT (report tables 1-5 / 1-9).

\[
\begin{aligned}
x_{\text{floor,N}}&=-23.895~\text{m}\ (K16+852.105),&
x_{\text{floor,S}}&=4210.368~\text{m}\ (K21+086.368),\\
x_{\text{portal,N}}&=-44.909~\text{m}\ (K16+831.091),&
x_{\text{portal,S}}&=4225.700~\text{m}\ (K21+101.700).
\end{aligned}
\]

These four stations are never collapsed into one “anchor” set.

## 4. Ingestion and classification (N02–N07)

### Method

`parse_step` stream-parses `CARTESIAN_POINT` / `TRIMMED_CURVE`, checks SHA-256, and scales millimetres to metres. `classify_segments` labels floor ropes by the drawing \(y=\pm(21.45\pm(0.85+0.26k))\) lattice, long high members as portal/handrail ropes, short transverse members as `portal_or_beam`, and long inter-deck members as `cross_passage`.

### Experiment

Raw counts: floor_rope 43 200, portal_or_beam 4 719, portal_rope 356, cross_passage 0, short_other 91 618. No single segment has \(\Delta y\ge 15\) m, because each 49.655 m passage is tessellated into \(\approx 1.7\) m pieces. At every drawing passage \(X\), node \(Y\) already spans \([-24.3,24.3]\) m. Detection therefore uses Y-span, not a single long beam.

Unclassified `short_other` is dropped from the coarsened deck (abstraction: clamps / mesh / unlabelled shorts are not first-class members). Longitudinal chains keep drawing stations and a 12 m target spacing.

## 5. Coordinate and topology gates (N07/N09)

### Method

`infer_x_transform` scores identity, minus-\(x_{\min}\), and minus raw chainage. High-\(Z\) histogram modes sit near portal clusters (\(\approx 700\) m and \(\approx 3023\) m), not on the saddles. Alignment is therefore confirmed by local \(Z_{p90}\) within 12 m of \(x=666.679\) and \(x=2953.321\).

Passages: 21 drawing stations (3+13+3+2). Portals: 71 stations \(\times\) 2 decks \(= 142\).

### Experiment

| Check | Result | Evidence |
|---|---|---|
| Units | PASS | mm STEP → m nodes; \(x_{\max}=4270.609<20\,000\) |
| Transform | PASS | identity, shift \(=0\) |
| Saddle \(Z\) | PASS | north \(Z_{p90}=330.78\) m, south \(324.85\) m vs 340.6 m |
| Two decks | PASS | \(Y\) medians \(+20.6\) / \(-20.6\) m vs \(\pm 21.45\) |
| Formed sag | PASS | geometry 214.18 m vs 227.30 m, \(\lvert\Delta\rvert=13.12\) m |
| No \(x_{\min}\) shift in `.inp` | PASS | node \(x_{\min}=0\) equals geometry |
| Passages | PASS | 21/21, insertions 0 |
| Portals | PASS | 142/142, insertions 0 |

Nominal breaks \(\{0,660,2960,3677,4180\}\) and physical saddles \(\{666.679,2953.321\}\) are both registered.

## 6. Materials, disjoint anchors, and cable seed (N08–N10)

### Method

Rope \(E=1.20\times 10^{11}\) Pa, floor/portal \(A=1400.42\times 10^{-6}\) m\(^2\), \(\mu=12.038\) kg/m (CALC-INPUT / DRW-A). Steel \(E=2.06\times 10^{11}\) Pa, \(\rho=7850\) kg/m\(^3\). Horizontal seed

\[
H=\frac{wL^2}{8h},\quad h=227.300~\text{m},\quad L=2286.642~\text{m}.
\]

Per deck, \(w_{\text{floor}}=2.766\) kN/m and \(w_{\text{portal}}=0.709\) kN/m give \(H_{\text{floor}}=7.954\) MN and \(H_{\text{portal}}=2.039\) MN. L0 wave frequency \(f_1=\sqrt{g/32h}=0.036719\) Hz is a magnitude gate only.

Floor and portal anchors use different node sets and two `*BOUNDARY` cards. A third card holds saddles and nominal ends. Intersection of `N_FLOOR_ANCHOR` and `N_PORTAL_ANCHOR` is empty (312 vs 16 nodes).

### Experiment

| Family | Station | Target \(x\) | Selected \(x_{\text{mean}}\) | Mode |
|---|---|---|---|---|
| Floor N | K16+852.105 | −23.895 | 0.000 | STEP north-end proxy |
| Floor S | K21+086.368 | 4210.368 | 4209.985 | matched, \(\Delta=0.38\) m |
| Portal N | K16+831.091 | −44.909 | 46.358 | STEP north-end proxy |
| Portal S | K21+101.700 | 4225.700 | 4221.093 | matched, \(\Delta=4.61\) m |

North physical anchors are outside the STEP bbox \([0,4270.609]\). The deck does not invent nodes at negative \(x\). South families remain 11.1 m apart in \(x\) and share no node.

## 7. Load cases (N11)

Per-deck packages are split equally onto 16 explicit floor ropes so that \(\sum_i w_{\text{rope}}L_i=w_{\text{deck}}L_{\text{deck}}\).

| Case | Deck \(w\) | Per-rope \(w\) | Resultant | Closure |
|---|---|---|---|---|
| Extra dead | 877.16 N/m | 54.82 N/m | 9.019 MN | exact vs \(wL\) |
| Personnel | 8.400 kN/m | 525 N/m | 86.371 MN | exact |
| Wind \(+Y\) | 0.50 kN/m | 31.25 N/m | 5.141 MN | exact |

Floor truss length in the coarsened mesh is 164 516 m (32 lines including sag and residual over-classified floor segments; \(\approx 5141\) m/line vs \(\approx 4300\) m expected). Gravity `*DLOAD` plus `*CLOAD` are rewritten each step (CalculiX does not inherit loads). LC-FREQ requests 20 eigenvalues and does not contain 0.0296 Hz or any other isolated target.

## 8. Solver deck and pre-solve (N12–N14)

The deck `artifacts/zjg_catwalk_coarsened.inp` (7 702 117 bytes) contains `*HEADING`, `*NODE`, `T3D2`, `B31`, materials, `*SOLID SECTION`, `*BEAM SECTION`, three `*BOUNDARY` cards, `*INITIAL CONDITIONS, TYPE=STRESS`, and the four steps. SHA-256

```
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da
```

is stored in `zjg_catwalk_coarsened.inp.sha256` and `main_deck_manifest.json`. Re-hash of the file matches the sidecar.

`ccx` is not present. `pre_solve_verification.json` marks `PRE_SOLVE_ONLY`. This paper does not report displacements, reactions, or frequencies from a solver.

## 9. Zhangjinggao results

1. Coordinate convention holds without subtracting \(x_{\min}\).
2. Topology reconcile: 21 passages, 142 portals, both from STEP evidence.
3. Anchor families are lexically and set-wise separate.
4. Independent sag seed uses 227.300 m; 255.56 m is absent from the deck.
5. All 26 automated gates PASS (`artifacts/coord_gate.json`).
6. Unit tests `test_coord_gate`, `test_write_inp`, `test_reconcile` PASS without the STEP.

Role counts in the written deck: floor_rope 25 299, portal_or_beam 4 719, portal_rope 227, cross_passage 21, handrail_rope 34, longitudinal_other 17.

## 10. Discussion and conclusions

The previous PR (#18) shipped the pipeline and left `artifacts/` empty. An empty directory cannot be a passed coordinate gate. This run produces a readable hashed deck.

Limits that remain visible in the evidence:

- North anchors are STEP-end proxies, not K16+852 / K16+831.
- Portal-rope classification is incomplete (227 coarsened elements); south portal nodes come from `portal_or_beam` at \(x=4221.093\).
- Geometric sag 214.18 m versus 227.30 m (13.12 m) is inside the 15 m gate but is not a formed-line fit.
- Floor-line length is about 20 % above a four-span catenary estimate; some non-floor centre-lines were labelled `floor_rope`.
- No `ccx` solve, no TARGET-FREQ comparison, no claim of fourteen-mode reproduction.

The scientific claim that is supported: a CalculiX main deck can be generated from the published STEP under \(x=\text{chainage}-K16+876.000\), with disjoint floor/portal anchors and a closed 21 / 142 topology audit, without reading S10.db or TARGET-FREQ, and that deck has a recorded SHA-256.

## Reproduction

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
python3 catwalk-fem/tests/test_reconcile.py
python3 catwalk-fem/pipeline/run_pipeline.py \
  --step /tmp/catwalk-assets/cw_S10_0716t050342_a4_centerline.step \
  --artifacts catwalk-fem/artifacts
sha256sum -c catwalk-fem/artifacts/zjg_catwalk_coarsened.inp.sha256
```

Do not add the 77 MB STEP to git. Do not feed `isolated/TARGET-FREQ.json` to the writer or the solver.
