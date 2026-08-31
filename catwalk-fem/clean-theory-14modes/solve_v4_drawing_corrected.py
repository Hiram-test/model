from __future__ import annotations  # Enable modern annotations for the drawing-corrected solver.
import json  # Serialize target-free calculation receipts.
import os  # Record the exact GitHub commit identity.
from pathlib import Path  # Resolve the isolated result directory.
import numpy as np  # Define drawing-based coordinate arrays and inspect modal fields.
import solve as base  # Reuse the audited element, matrix, eigen, and plotting implementation.
import solve_v2 as v2  # Reuse the accepted inverse statics and mass-consistent assembly wrapper.
import solve_v3 as v3  # Reuse the accepted twin-catwalk system-roll classifier.
OUT = Path(__file__).resolve().parent / "results"  # Keep the standard result location for the existing comparison node.
OUT.mkdir(parents=True, exist_ok=True)  # Create the result directory before writing any output.
DRAWING_GANTRY_WIDTH = 7.380  # Use MD4-02 top-beam overall width 7380 mm.
DRAWING_GANTRY_Y = np.array([-2.520, -2.260, -2.000, 2.000, 2.260, 2.520])  # Use the two three-rope groups from the 260-260-850-2300-850-260-260 dimension chain.
DRAWING_PORTAL_B = 0.160  # Use the MD4-02 square-tube outer dimension 160 mm.
DRAWING_PORTAL_T = 0.004  # Use the MD4-02 square-tube wall thickness 4 mm.
DRAWING_PORTAL_BODY_MASS = 829.30  # Use the MD4-01 single portal-frame mass excluding the bottom beam.
DRAWING_BOTTOM_BEAM_MASS = 313.46  # Use the MD1-05 single portal bottom-beam mass.
DRAWING_PORTAL_TOTAL_MASS = DRAWING_PORTAL_BODY_MASS + DRAWING_BOTTOM_BEAM_MASS  # Form one complete portal package without mixing versions.
DRAWING_PASSAGE_PORT_SPAN = 42.900  # Use the MD5-02 centre-to-centre spacing between the two catwalk ports.
DRAWING_PASSAGE_HEIGHT = 1.700  # Use the MD5-02 triangular passage depth 1700 mm.
def apply_drawing_corrections() -> None:  # Apply only independently documented geometry and mass corrections before assembly.
    base.GANTRY_WIDTH = DRAWING_GANTRY_WIDTH  # Replace the previous 7.46 m inferred width with the directly dimensioned 7.38 m top beam.
    base.GANTRY_Y = DRAWING_GANTRY_Y.copy()  # Replace the previous ±3.73 m triplets with the six directly dimensioned rope offsets.
    base.PORTAL_B = DRAWING_PORTAL_B  # Replace the previous 161 mm portal box idealization with the drawing value.
    base.PORTAL_T = DRAWING_PORTAL_T  # Correct the previous 8 mm wall to the drawing 4 mm wall.
    base.M_PORTAL = DRAWING_PORTAL_TOTAL_MASS  # Use the same verified 2025 frame-plus-bottom-beam mass package throughout dynamics and mass subtraction.
    base.PASSAGE_LENGTH = DRAWING_PASSAGE_PORT_SPAN  # Use the actual two-port separation in the passage beam kinematics so rigid system-roll is objective.
    base.PASSAGE_HEIGHT = DRAWING_PASSAGE_HEIGHT  # Use the directly dimensioned triangular passage depth.
def main() -> int:  # Execute the complete drawing-corrected fourteen-family calculation.
    apply_drawing_corrections()  # Freeze every drawing-based correction before reading or assembling the model.
    model = base.load_mct()  # Parse and SHA-check the original MCT body used only for formed geometry, topology, supports, and explicit load input.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed floor-chain topology.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope chain.
    static = v2.inverse_static_v2(model, floor_nodes, floor_elements, top_nodes, top_elements)  # Reconstruct prestress without reading MCT internal-force output.
    if static["equilibrium_relative_residual"] > v2.STATIC_TOLERANCE:  # Enforce the unchanged inverse-equilibrium acceptance criterion.
        raise RuntimeError(f"Inverse equilibrium residual is {static['equilibrium_relative_residual']:.6e}")  # Reject the model if the formed geometry and prescribed loads are incompatible.
    system = v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble the corrected portal, gantry-rope, passage, rope, and mass matrices.
    frequencies, vectors, residuals, checks = base.solve_eigen(system)  # Solve and verify the symmetric generalized eigenproblem.
    raw, selected, classification_meta = v3.classify_v3(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Classify all fourteen physical families without target frequencies.
    assumptions = [  # Record every decisive model assumption and drawing correction explicitly.
        {"name": "MCT use", "value": "formed coordinates, topology, restraint topology, SELFWEIGHT definition, and explicit second-stage CONLOAD only; internal-force and modal outputs excluded"},  # Preserve input isolation.
        {"name": "inverse statics", "value": "bounded nodal equilibrium on the prescribed formed geometry with acceptance residual <= 0.005"},  # Record the unchanged static criterion.
        {"name": "floor ropes", "value": "16 explicit ropes per catwalk with one smart rope at the inner local position"},  # Preserve all sixteen floor ropes.
        {"name": "gantry ropes", "value": "6 explicit ropes per catwalk at y = ±2.00, ±2.26, ±2.52 m from MD4-02"},  # Record the corrected gantry-rope offsets.
        {"name": "portal section", "value": "160x160x4 Q235 square tubes from MD4-02, not 160x160x8"},  # Record the corrected portal wall thickness.
        {"name": "portal mass", "value": "829.30 kg portal frame + 313.46 kg bottom beam = 1142.76 kg per portal from MD4-01 and MD1-05"},  # Record the consistent old-drawing mass package.
        {"name": "passage port span", "value": "42.90 m catwalk-centre port separation from MD5-02 used in two-port bending kinematics; passage overall structural length is not used as the port span"},  # Record the objectivity correction.
        {"name": "passage depth", "value": "1.70 m from MD5-02"},  # Record the corrected triangular depth.
        {"name": "global torsion", "value": "Theta=(w_D-w_U)/42.90; T modes require vertical-dominant main-span differential motion with negative signed U/D correlation"},  # Preserve the accepted system-roll definition.
        {"name": "classification", "value": "mode kinematics, main-span order, parity, signed U/D correlation, and span localization only; no target frequency"},  # Preserve target-free classification.
    ]  # Close the assumption registry.
    frozen = {  # Form the target-free frozen result before any external frequency table is loaded.
        "kind": "clean_theory_44_rope_catwalk_frozen_v4_drawing_corrected",  # Identify this corrected calculation version.
        "git_sha": os.environ.get("GITHUB_SHA", "local"),  # Record the exact source revision.
        "source_mct_sha256": model["source"]["sha256"],  # Record the source geometry identity.
        "source_mct_bytes": model["source"]["bytes"],  # Record the source geometry size.
        "target_frequency_used": False,  # Certify that target frequencies were excluded from the solve.
        "mct_internal_force_used": False,  # Certify that MCT internal-force results were excluded.
        "frequency_reproduced": False,  # Certify that this is a forward calculation rather than target-conditioned reproduction.
        "not_attach_ta1": True,  # Family label TA1 is not attach TA1.
        "not_attach_fourteen_mode_table": True,  # This table is not the attach 2-3 fourteen-mode result.
        "topology": {"explicit_floor_ropes": 32, "explicit_gantry_ropes": 12, "explicit_ropes_total": 44, "portals": 142, "passages": 21},  # Record the retained physical skeleton.
        "drawing_corrections": {"gantry_width_m": DRAWING_GANTRY_WIDTH, "gantry_y_m": DRAWING_GANTRY_Y.tolist(), "portal_outer_m": DRAWING_PORTAL_B, "portal_wall_m": DRAWING_PORTAL_T, "portal_mass_kg": DRAWING_PORTAL_TOTAL_MASS, "passage_port_span_m": DRAWING_PASSAGE_PORT_SPAN, "passage_depth_m": DRAWING_PASSAGE_HEIGHT},  # Store every corrected input numerically.
        "assumptions": assumptions,  # Store the complete assumption registry.
        "inverse_static": {key: value for key, value in static.items() if key != "force_kN"},  # Store the accepted static diagnostics without the large force vector.
        "matrix_checks": checks,  # Store matrix symmetry and eigen-residual diagnostics.
        "mass_audit_v2": system["mass_audit_v2"],  # Preserve the existing mass accounting audit.
        "raw_modes": raw,  # Store every solved mode's target-free physical metrics.
        "classified_14": selected,  # Store the target-free fourteen-family classification.
        "classification_meta": {key: value for key, value in classification_meta.items() if key != "selected_shapes"},  # Store classification rules without duplicating full shape arrays.
    }  # Close the target-free frozen result object.
    frozen_path = OUT / "frozen_results.json"  # Define the standard frozen-result path consumed by the comparison script.
    base.dump(frozen_path, frozen)  # Write the target-free result before loading any external frequency table.
    frozen_sha = base.sha(frozen_path)  # Freeze the exact target-free result identity.
    base.write_csv(raw, selected, [])  # Write the raw spectrum and fourteen-family target-free classification.
    base.plots(raw, selected, [], classification_meta)  # Plot the spectrum and all non-system-roll selected shapes.
    v3.plot_global_torsion_shapes(model, system, floor_nodes, vectors, selected)  # Plot TA1, TS1, and TS2 with the accepted system-roll coordinate.
    summary = {"kind": "clean_theory_44_rope_catwalk_summary_v4_drawing_corrected", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha, "identified_count": sum(1 for item in selected.values() if "frequency_hz" in item), "inverse_static": frozen["inverse_static"], "matrix_checks": checks, "drawing_corrections": frozen["drawing_corrections"], "target_frequency_used": False, "mct_internal_force_used": False, "frequency_reproduced": False, "not_attach_ta1": True, "not_attach_fourteen_mode_table": True}  # Build a concise audit summary.
    base.dump(OUT / "summary.json", summary)  # Write the concise target-free summary.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve all recovered explicit-rope unstressed lengths and forces.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every primary result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2))  # Print the target-free calculation receipt into the workflow log.
    return 0  # Return successful completion.
if __name__ == "__main__":  # Execute only when the drawing-corrected solver is invoked directly.
    raise SystemExit(main())  # Run the complete forward calculation.
