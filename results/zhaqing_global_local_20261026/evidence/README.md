# Recovered Zhaqing geometry and native solver evidence

The original whole-bridge baseline was recovered from the retained `verified-zhaqing-s4-static-shell.zip`. Its archive SHA-256, `fadcd8ec455c90a429f69001f2ba98b04c7840c64d5d37f5f3cd90c766745a20`, exactly matches the immutable baseline digest in `.github/workflows/zhaqing-stress-coordination.yml`. The recovered `LC01_G_DEAD.inp` hash is `1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d`, also an exact match. The original Actions artifacts are no longer available; this is a byte-verified recovery, not a regenerated baseline.

`baseline/` preserves all nine original load-case inputs, the source contract, the original assumptions manifest, and the later fixed-L0 cable equilibrium state. These are historical solver inputs and evidence, not newly validated nonlinear wind results. The baseline uses equivalent beam sections and deck properties. Its main-girder rectangle preserves area and strong-axis inertia but does not preserve the actual HW400 section's transverse or torsional stiffness. The later F3 state assumes frictionless continuous saddles and excludes formal wind-cable design. These limitations must not disappear when reusing the baseline.

The current raw DWGs were independently converted using LibreDWG 0.13.3. `drawings/drawing_source_audit.json` binds seven drawings to source hashes and entity inventories. The original cable note at `03-缆索布置.dwg`, handle `16B5`, states **283 wires, diameter 5 mm, nominal breaking-stress basis 1670 MPa**. The stated strength is not a fatigue law or an elastic/plastic stress-strain calibration.

The saddle drawing is a curved bearing plate with two side rails and welded stiffeners. Its material table gives a 400 × 30 × 1600 mm base plate, two 110 × 20 × 1600 mm plates, and ten 100 × 20 × 100 mm stiffener pieces. The source profile is represented by CAD arcs, not a rectangular block. Exact individual wire packing, coating, residual stress, friction, fatigue constants, weld detail, and installation conditions remain separate inputs.

**Source identity conflict:** `桥跨横断面图.dwg` titleblock handle `C2A` reads `杂多县尕沙河电站至昂塞乡政府支线`, whereas the saddle, cable, general, deck, crossbeam, and girder drawings identify the Zhaqing project. Matching width values alone do not establish that this separate section drawing is the Zhaqing aerodynamic section. It is retained as reference evidence; authenticated project drawings must control any reconstructed wind section.

`previews/` contains direct native CAD linework previews. They were created with LibreDWG and librsvg, with no Python plotting. Only zero-width stroke visibility, the shifted SVG viewport, background, and fonts were adjusted; entity coordinates were not changed. Converter warnings and empty/ignored MTEXT mean these previews are not a complete dimension transcription. Original DWGs and extracted entity handles remain authoritative.

Reproduction uses `automation/zhaqing_global_local/evidence/audit_drawings.py` (entity extraction only) and `render_source_previews.sh` (native rendering). Their scope is evidence recovery and source inspection, not numerical or engineering acceptance.

## Detailed steel-deck correction

`detailed_deck_source_contract.json` is a new correction contract; it does not overwrite the historical frozen model. `audit_detailed_deck.py` independently checks the original CAD handles and dimension scaling.

The old 50 mm deck-thickness source was misread: `3D10` is a **horizontal fixing/cleat dimension**, not panel thickness. The material row `762F` specifies a **10 × 1560 × 2690 mm steel plate**. Each panel has six 2666 mm channels, nominal 160 × 65 × 8.5/10 mm geometry, plus actual end and cross stiffeners. The 26 bays and three-panel width produce 78 panels and 468 channels. The source girder spacing is 5100 mm, giving centers at ±2550 mm, while the plate field is 4680 mm wide.

The SGT12 source labels 3000 mm crossbeam-center spacing, 2700 mm clear distance, and a 2696 mm longitudinal girder. A 2690 mm panel fits that clear distance with 5 mm at each end. Its placement is therefore 155 mm from a crossbeam center; channel ends are 167 mm from that center. General-arrangement end-face coordinates and the 300 mm box width support the 2–80 m crossbeam station sequence, documented as a source-based geometric interpretation.

The crossbeam's source section is a **closed two-web box**, 420 × 300 mm with 10 mm plates, not a single-web I section. Its two N5 support angles project 100 mm outwards from the box faces at ±150 mm, reaching ±250 mm. The ledge lies 170 mm below the top surface, matching the 10 mm plate plus 160 mm channels. This is an actual physical support path for the panel; it does not require fictitious 150 mm rigid arms. Angle thickness is 10 mm and its unequal legs are 100 and 63 mm. Connection friction, bolt pretension, bearing, and weld behavior remain separate constitutive choices.

Two source contradictions remain visible: the drawn box web clear height is 400 mm whereas the cut-piece table says 416 mm, and the panel plan indicates N3 endplates across 1560 mm whereas its material row gives 2690 mm. The contract names a drawn-geometry branch and preserves these contradictions. Neither a silent mass correction nor invented thin closure plates is used to make them disappear.
