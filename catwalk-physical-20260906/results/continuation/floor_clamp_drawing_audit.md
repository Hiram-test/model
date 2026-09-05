# Original floor crossbeam connection audit

Read-only examination of `results/original_drawing_1225.pdf`, 124 pages, in [run 33984938968, artifact 9975072535](https://github.com/Hiram-test/model/actions/runs/33984938968/artifacts/9975072535). The failed full input was executed at commit `acccac4a08bb0080ad48fc135cc66967e1be0946`; findings about its then-current offsets and mass ownership refer to that input. This audit used the original drawing images; no previous modal results were read.

## Large ordinary floor crossbeam

PDF pages 11 and 12 are drawing sheets MD1-01 and MD1-02, 面网大横梁构造图（一）/（二）.

- The native section shown is □100×100×4.
- MD1-02 note 4 explicitly states: “连接板件④在大横梁件①两侧交叉设置。” The connection plates alternate on the two sides of the beam.
- The material table lists 16 connection plates, 16 stiffeners, and 16 M14×302 U bolts per large crossbeam; note 8 explicitly identifies these U bolts as connections for the φ50 catwalk carrying ropes.
- MD1-01 view A–A shows each carrying rope running across the 100 mm beam width, with its U bolt attached to a plate projecting from one longitudinal side of the beam. Consequently the 16 real clamp positions are not all on the same global-X plane. Alternating signed X offsets are directly supported by the drawing.
- The label in A–A gives plate ④ as 120×50×10, while the MD1-02 material table gives 120×45×10. A nominal clamp-center offset of 75 mm from the beam center follows from the 50 mm projection view, but this dimension discrepancy must be resolved or explicitly retained as an interpretation. This audit does not silently select a dimension.
- The B–B detail with a 300 mm plate and four clamps is for the φ20 connection rope near the end of the crossbeam. It must not be mistaken for four clamps around each φ50 carrying rope.

## Small ordinary floor crossbeam

PDF page 13 is drawing MD1-03, 面网小横梁构造图.

- The small beam is □50×50×4. Its plan explicitly dimensions the longitudinal width as 50 mm. Its elevation shows the beam above the φ50 carrying ropes, resting across them.
- The material table lists the small square tube, wood treads, and end closure plates. No U bolts, clamps, or longitudinal pair of fasteners are drawn or listed for this small beam. Its notes do not specify bonding, friction, preload, or rotational restraint.
- The drawing supports a finite 50 mm beam footprint crossing each rope. It does not by itself support replacing that footprint with two fully bonded, bilateral, all-translation ties. A unilateral contact or equivalent bearing model requires a stated mechanical idealization and validation; a specific clamp or tie model requires additional source evidence.
- The small-beam sheet contains no handrail posts. MD1-01/02 place those posts on the large-beam assemblies. The input executed in run 33984938968 distributed rail inertia to every floor row; that was a separate mass idealization and is not a depicted small-beam attachment.

## Elevation sign requiring correction review

Both original large- and small-beam elevations show the physical beam above the carrying ropes. The input executed in run 33984938968 used ordinary floor BeamLine centers at `zf - 0.075` or `zf - 0.05`, placing them below the source carrying-rope center. The sign is opposite to the drawing. Mesh thickness and plate placement can affect the exact large-beam offset, so the magnitude should be read from the detailed geometry rather than inferred only from tube half-depth plus rope radius.

## Failure localization context

The first failed native equilibrium iteration is localized independently in `native_failure_mapping.json`: B32R elements 17221–17224, ordinary small crossbeam `F0_3238.000000`. Internal nodes 1108953, 1109025, 1109061, and 1109079 are native ROT nodes for original nodes 152870, 152874, 152876, and 152877. Their DOF 2 is global ROTY, with correction values in radians. This localization agrees with an admissible local pitch mechanism in the assembled input but does not establish it as the sole error in the complete model.

## Original visual evidence

Use `results/original_drawing_1225.pdf` in [the original run artifact](https://github.com/Hiram-test/model/actions/runs/33984938968/artifacts/9975072535):

- PDF page 11, MD1-01: C elevation, A-A carrying-rope side plate, and the separate B-B connection-rope hardware.
- PDF page 12, MD1-02: material table; note 4 on alternating sides; note 8 on φ50 carrying-rope U bolts.
- PDF page 13, MD1-03: small-beam elevation, 50 mm longitudinal footprint, 5520 mm tube length, and the material table without handrail posts or clamp hardware.

## Subsequent source-supported code corrections

After this failure audit, `spatial_native.py` was changed to 5520/5772 mm native tube lengths, above-rope center offsets of +0.050/+0.075 m explicitly neglecting mesh and plate thickness, alternating large-beam clamp X offsets of ±0.075 m, and source-arc redistribution of unchanged railing mass to large/HW/frame stations only. All floor ropes now share the complete source/attachment station grid; observation output reads only existing assembled nodes. The original 45/50 mm plate discrepancy and unresolved small-beam bearing contact are recorded in the generated physical assumptions.

These code corrections have only been checked by assembly and mass/connectivity accounting, recorded in `drawing_corrections_assembly_only.json`. They have not produced a new full-bridge equilibrium or eigenvalue solution. The actual full run at `acccac4a...` remains failed with no accepted dead-load increment or native eigenvalues.
