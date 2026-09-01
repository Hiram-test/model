from __future__ import annotations  # Enable stable modern type annotations.
import json  # Write machine-readable calculation receipts.
import os  # Record the exact GitHub commit identity.
import sys  # Add the two isolated solver directories to the import path.
from pathlib import Path  # Resolve repository and output paths safely.
import numpy as np  # Assemble force vectors and calculate numerical statistics.
from scipy.linalg import lstsq  # Solve the rank-revealing unregularized inverse equilibrium system.
from scipy.optimize import lsq_linear  # Enforce cable tension bounds only when the unconstrained solution violates them.

HERE = Path(__file__).resolve().parent  # Locate the inverse-form-finding calculation directory.
CATWALK_FEM = HERE.parent  # Locate the common catwalk-fem directory.
CLEAN_DIR = CATWALK_FEM / "clean-theory-14modes"  # Locate the accepted explicit 44-rope dynamic implementation.
sys.path.insert(0, str(HERE))  # Make the inverse-equilibrium helpers importable.
sys.path.insert(0, str(CLEAN_DIR))  # Make the explicit dynamic solver modules importable.
import solve_inverse as inverse  # type: ignore  # MCT geometry/load/equilibrium operators. Residual 0.00328 is not verified INIFORCE.
import solve as base  # type: ignore  # Reuse the audited rope, frame, mass, eigen, plotting, and CSV implementation.
import solve_v2 as v2  # type: ignore  # Reuse the mass-consistent assembly correction.
import solve_v3 as v3  # type: ignore  # Reuse the accepted twin-catwalk global-torsion classifier.
import solve_v4_drawing_corrected as v4  # type: ignore  # Reuse the drawing-corrected portal, gantry-rope, and passage geometry.

OUT = HERE / "modal_results"  # Define an output directory isolated from every earlier calculation.
OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated modal output directory.
base.OUT = OUT  # Redirect the base solver tables and plots into the isolated modal directory.
v2.OUT = OUT  # Redirect any v2 outputs into the isolated modal directory.
v3.OUT = OUT  # Redirect the global-torsion plots into the isolated modal directory.
v4.OUT = OUT  # Redirect any v4 outputs into the isolated modal directory.
# Attach 2-3 family Hz are not stored here. comparison_after_freeze.py is the only comparison node.


def recover_static_state(model: dict) -> dict:  # Recover the complete aggregate axial-force state without using stored MCT initial forces.
    operator_coo, _lengths_m, element_ids, row_keys, element_column = inverse.equilibrium_operator(model)  # Assemble the exact MCT free-node equilibrium operator.
    operator = operator_coo.tocsr()  # Convert the equilibrium operator to compressed sparse format.
    _selfweight, _stage_two, combined = inverse.external_components(model)  # Build MCT self-weight and second-stage external loads independently of initial force.
    right_combined = inverse.right_hand(row_keys, combined)  # Form the complete free-node equilibrium right-hand side.
    dense_operator = operator.toarray()  # Convert the moderate equilibrium system to dense form for rank-revealing QR.
    unconstrained, _residuals, rank, _singular = lstsq(dense_operator, right_combined, cond=None, lapack_driver="gelsy")  # Solve the unique unregularized equilibrium system.
    tenstr_columns = np.array([element_column[element_id] for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TENSTR"], dtype=int)  # Address every tension-only cable column.
    lower = np.full(len(element_ids), -np.inf, dtype=float)  # Initialize unrestricted lower bounds for all member forces.
    upper = np.full(len(element_ids), np.inf, dtype=float)  # Initialize unrestricted upper bounds for all member forces.
    lower[tenstr_columns] = 0.0  # Enforce nonnegative force in every MCT TENSTR member.
    if float(np.min(unconstrained[tenstr_columns])) >= -1.0e-8:  # Test whether the unique unregularized solution already satisfies cable tension physics.
        recovered = unconstrained  # Adopt the unregularized equilibrium solution directly.
        solver_status = "unregularized_full_rank_solution"  # Record the exact inverse-solution path.
        solver_success = True  # Record successful inverse solution.
    else:  # Handle a mathematically unique solution containing cable compression.
        bounded = lsq_linear(operator, right_combined, bounds=(lower, upper), tol=1.0e-12, lsmr_tol=1.0e-12, max_iter=5000, verbose=0)  # Solve the bounded equilibrium system without any target-force selector.
        recovered = bounded.x  # Adopt the bounded cable-admissible force solution.
        solver_status = str(bounded.message)  # Record the bounded solver status.
        solver_success = bool(bounded.success)  # Record bounded solver success.
    equilibrium_residual = operator @ recovered - right_combined  # Evaluate the complete recovered free-node equilibrium residual.
    equilibrium_relative = float(np.linalg.norm(equilibrium_residual) / max(np.linalg.norm(right_combined), 1.0e-30))  # Normalize the recovered equilibrium residual.
    force_kN = {str(element_id): float(recovered[element_column[element_id]]) for element_id in element_ids}  # Store every aggregate element force in kilonewtons for tangent assembly.
    tenstr_ids = [element_id for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TENSTR"]  # Preserve deterministic cable order for post-solve verification.
    target_force = np.array([float(model["iniforce"][element_id]["axial_kN"]) for element_id in tenstr_ids], dtype=float)  # Load stored MCT initial force only after the inverse result is frozen.
    recovered_force = np.array([float(force_kN[str(element_id)]) for element_id in tenstr_ids], dtype=float)  # Extract the recovered cable-force vector.
    relative_error = (recovered_force - target_force) / target_force  # Calculate the elementwise post-solve force mismatch.
    return {  # Return the complete inverse-static state required by the dynamic assembly.
        "success": solver_success,  # Store inverse-solver success.
        "message": solver_status,  # Store the exact inverse-solver path or status.
        "equilibrium_relative_residual": equilibrium_relative,  # Store the recovered free-node equilibrium residual.
        "equations": int(operator.shape[0]),  # Store the number of free equilibrium equations.
        "unknowns": int(operator.shape[1]),  # Store the number of aggregate member-force unknowns.
        "rank": int(rank),  # Store the rank of the equilibrium operator.
        "nullity": int(operator.shape[1] - rank),  # Store the equilibrium-force nullity.
        "min_cable_force_kN": float(np.min(recovered_force)),  # Store the minimum recovered cable tension.
        "max_cable_force_kN": float(np.max(recovered_force)),  # Store the maximum recovered cable tension.
        "mean_abs_force_error_percent": float(100.0 * np.mean(np.abs(relative_error))),  # Store the mean absolute elementwise force mismatch.
        "p95_abs_force_error_percent": float(100.0 * np.percentile(np.abs(relative_error), 95.0)),  # Store the ninety-fifth-percentile force mismatch.
        "max_abs_force_error_percent": float(100.0 * np.max(np.abs(relative_error))),  # Store the maximum elementwise force mismatch.
        "force_correlation": float(np.corrcoef(recovered_force, target_force)[0, 1]),  # Store the recovered-versus-MCT force correlation.
        "force_kN": force_kN,  # Store every aggregate force for explicit-rope tangent assembly.
    }  # Close the inverse-static state record.


def main() -> int:  # Execute the MCT-geometry inverse-prestress modal calculation. Attach Hz are not read here.
    v4.apply_drawing_corrections()  # Apply only the independently documented drawing corrections before dynamic assembly.
    model = base.load_mct()  # Parse and hash-check the sole MCT geometry, topology, support, and load source.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-chain topology.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope topology.
    static = recover_static_state(model)  # Recover the aggregate prestress from the exact formed geometry and applied loads.
    if not bool(static["success"]):  # Reject a failed inverse solution before constructing any modal matrix.
        raise RuntimeError(str(static["message"]))  # Report the inverse-solver failure exactly.
    if int(static["nullity"]) != 0:  # Require a unique aggregate force state in the declared equilibrium space.
        raise RuntimeError(f"Inverse equilibrium nullity is {static['nullity']}")  # Reject an unresolved self-stress branch.
    if float(static["min_cable_force_kN"]) <= 0.0:  # Require every cable member to remain in tension.
        raise RuntimeError(f"Minimum recovered cable force is {static['min_cable_force_kN']:.6f} kN")  # Reject cable compression before tangent assembly.
    if float(static["max_abs_force_error_percent"]) > 0.5:  # Elementwise |Δ| is a comparison diagnostic, not the 1e-8 residual gate.
        raise RuntimeError(f"Maximum MCT initial-force mismatch is {static['max_abs_force_error_percent']:.6f}%")  # Reject a prestress state that no longer reproduces the MCT force field.
    # Residual 0.00328 > 1e-8 remains not_recovered_iniforce. Do not treat |Δ| p95 as verified prestress.
    system = v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble the drawing-corrected explicit 44-rope tangent stiffness and consistent mass matrices.
    frequencies, vectors, residuals, checks = base.solve_eigen(system)  # Solve and verify the low global generalized eigenpairs.
    raw, selected, classification_meta = v3.classify_v3(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Classify fourteen physical families without target frequencies.
    frozen = {  # Assemble the target-free frozen modal result before any external frequency is read.
        "kind": "mct_inverse_prestress_44_rope_modal_frozen_v1",  # Identify the exact model and solve stage.
        "git_sha": os.environ.get("GITHUB_SHA", "local"),  # Record the exact source revision.
        "source_mct_sha256": model["source"]["sha256"],  # Record the verified MCT source identity.
        "source_mct_bytes": model["source"]["bytes"],  # Record the verified MCT source size.
        "target_frequency_used": False,  # Certify that target frequencies were absent from assembly and eigensolution.
        "mct_initial_force_used_in_inverse": False,  # Certify that stored MCT initial forces were absent from the inverse solve.
        "mct_initial_force_used_after_inverse_for_verification": True,  # Post-solve |Δ| vs stored INIFORCE is a comparison diagnostic.
        "inverse_force_verified": False,  # Residual 0.00328 > 1e-8 is not recovered INIFORCE.
        "not_recovered_iniforce": True,  # Absolute residual gates stay 1e-8 / 1e-4.
        "frequency_reproduced": False,  # Python eigsh zip is not attach 复现.
        "not_attach_ta1": True,  # Theory family TA1 is not attach TA1.
        "not_ccx_job_finished": True,  # This path is scipy eigsh, not CalculiX.
        "inverse_static": {key: value for key, value in static.items() if key != "force_kN"},  # Store inverse diagnostics without duplicating the large force vector.
        "drawing_corrections": {"gantry_width_m": v4.DRAWING_GANTRY_WIDTH, "gantry_y_m": v4.DRAWING_GANTRY_Y.tolist(), "portal_outer_m": v4.DRAWING_PORTAL_B, "portal_wall_m": v4.DRAWING_PORTAL_T, "portal_mass_kg": v4.DRAWING_PORTAL_TOTAL_MASS, "passage_port_span_m": v4.DRAWING_PASSAGE_PORT_SPAN, "passage_depth_m": v4.DRAWING_PASSAGE_HEIGHT},  # Store every drawing correction numerically.
        "topology": {"explicit_floor_ropes": 32, "explicit_gantry_ropes": 12, "explicit_ropes_total": 44, "portals": 142, "passages": 21},  # Store the complete explicit dynamic topology.
        "matrix_checks": checks,  # Store matrix symmetry and eigenpair residual diagnostics.
        "mass_audit": system["mass_audit_v2"],  # Store the complete non-duplicated dynamic-mass audit.
        "first_40_frequencies_hz": [float(value) for value in frequencies[:40]],  # Store the first forty physical frequencies before classification.
        "raw_modes": raw,  # Store all target-free physical mode metrics.
        "classified_14": selected,  # Store the target-free fourteen-family classification.
        "classification_meta": {key: value for key, value in classification_meta.items() if key != "selected_shapes"},  # Store classification rules without duplicating shape arrays.
    }  # Close the target-free frozen modal result.
    frozen_path = OUT / "frozen_results.json"  # Define the target-free frozen-result path.
    base.dump(frozen_path, frozen)  # Write and freeze the complete modal result before comparison.
    frozen_sha = base.sha(frozen_path)  # Calculate the immutable frozen-result digest.
    base.write_csv(raw, selected, [])  # Write the raw spectrum and fourteen-family table without external target values.
    base.plots(raw, selected, [], classification_meta)  # Generate the spectrum and non-system-torsion mode-shape plots.
    v3.plot_global_torsion_shapes(model, system, floor_nodes, vectors, selected)  # Generate the three twin-catwalk global-torsion mode-shape plots.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve every explicit rope force and recovered unstressed length.
    summary = {  # Build the concise calculation receipt. Comparison metrics live in compare_after_freeze.py only.
        "kind": "mct_inverse_prestress_44_rope_modal_summary_v1",  # Identify the completed calculation.
        "git_sha": os.environ.get("GITHUB_SHA", "local"),  # Record the exact calculation commit.
        "source_mct_sha256": model["source"]["sha256"],  # Record the verified MCT source identity.
        "frozen_sha256": frozen_sha,  # Record the frozen target-free result digest.
        "inverse_static": frozen["inverse_static"],  # Store the initial-force agreement and equilibrium diagnostics.
        "matrix_checks": checks,  # Store the eigenproblem verification diagnostics.
        "identified_frequencies_hz": {label: record.get("frequency_hz") for label, record in selected.items()},  # Store the fourteen classified frequencies compactly.
        "target_frequency_used_in_solve": False,  # Certify target isolation in the eigensolution.
        "inverse_force_verified": False,  # Residual 0.00328 > 1e-8 is not verified prestress.
        "not_recovered_iniforce": True,  # Absolute residual gates stay 1e-8 / 1e-4.
        "frequency_reproduced": False,  # Green eigsh zip is not attach 复现.
        "not_attach_ta1": True,  # Theory family TA1 is not attach TA1.
        "not_ccx_job_finished": True,  # This path is scipy eigsh, not CalculiX.
        "absolute_recovered_residual_limit": 1.0e-8,  # Inverse form-finding residual gate. Do not loosen.
        "absolute_stored_residual_limit": 1.0e-4,  # Stored-INIFORCE residual gate. Do not loosen.
    }  # Close the concise calculation receipt.
    base.dump(OUT / "summary.json", summary)  # Write the concise modal summary.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every primary result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete modal summary into the workflow log.
    return 0  # Report successful completion.


if __name__ == "__main__":  # Execute only when invoked as a program.
    raise SystemExit(main())  # Return the calculation status to the operating system.
