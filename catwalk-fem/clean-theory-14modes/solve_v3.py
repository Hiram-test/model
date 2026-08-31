from __future__ import annotations  # Enable stable modern annotations for the revised physical classifier.
import json  # Serialize the final target-free calculation receipts.
import os  # Record the exact GitHub source commit in frozen results.
from pathlib import Path  # Resolve the isolated calculation output directory.
import numpy as np  # Evaluate modal fields and global torsional coordinates.
import solve as base  # Reuse the audited eigen, raw-physics, CSV, and standard plot implementation.
import solve_v2 as v2  # Reuse the corrected inverse statics and mass-consistent dynamic assembly.
OUT = Path(__file__).resolve().parent / "results"  # Use the isolated clean-theory result directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the output directory before writing results.
T_SPEC = {"TA1": 2, "TS1": 3, "TS2": 5}  # Define global torsional families only by main-span longitudinal order.
def extract_floor_vertical(system: dict, floor_nodes: list[int], vectors: np.ndarray, mode_number: int) -> tuple[np.ndarray, np.ndarray]:  # Recover both catwalk vertical centreline fields for one numerical eigenvector.
    full = np.zeros(system["dof_count"])  # Initialize the full constrained generalized vector.
    full[system["free"]] = vectors[:, mode_number - 1]  # Insert the selected free-DOF eigenvector into physical coordinates.
    upstream = np.array([full[system["floor_dofs"][(0, node_id)]][2] for node_id in floor_nodes])  # Read upstream floor-centre vertical displacement at every section.
    downstream = np.array([full[system["floor_dofs"][(1, node_id)]][2] for node_id in floor_nodes])  # Read downstream floor-centre vertical displacement at every section.
    return upstream, downstream  # Return the two physical vertical fields.
def classify_v3(model: dict, system: dict, floor_nodes: list[int], top_nodes: list[int], frequencies: np.ndarray, vectors: np.ndarray, residuals: list[float]) -> tuple[list[dict], dict[str, dict], dict]:  # Classify local bending and twin-catwalk global torsion without target frequencies.
    raw, selected, meta = base.classify(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Compute the audited raw L/V/local-roll metrics and non-torsional labels first.
    used = {int(record["mode"]) for label, record in selected.items() if label not in T_SPEC and "mode" in record}  # Protect every already assigned non-torsional physical mode from double labelling.
    for label, order_value in T_SPEC.items():  # Select the three global torsional modes from differential twin-catwalk vertical motion.
        parity_label = "S" if order_value % 2 == 1 else "A"  # Derive main-span midpoint parity from the fixed-end longitudinal order.
        candidates = [record for record in raw if record["mode"] not in used and record["family"] == "V" and record["longitudinal_order"] == order_value and record["parity_label"] == parity_label and record["span_fraction"]["main"] >= 0.45 and record["floor_participation"] >= 0.30 and record["same_global_sign_correlation"] <= -0.50 and record["frequency_hz"] <= 0.60 and record["localization"] <= 0.20]  # Apply only target-free system-roll kinematics, span, parity, and global-mode filters.
        if candidates:  # Test whether a physically admissible global torsional mode exists.
            choice = max(candidates, key=lambda record: (0.35 * record["family_confidence"] + 0.30 * record["order_score"] + 0.20 * record["span_fraction"]["main"] + 0.10 * (-record["same_global_sign_correlation"]) + 0.05 * record["floor_participation"] - 0.05 * record["localization"], -record["frequency_hz"]))  # Rank candidates by differential-vertical torsional purity only.
            selected[label] = {**choice, "family": "T", "underlying_component": "differential_vertical", "global_torsion_definition": "Theta=(w_D-w_U)/42.90", "selection_rule": f"highest target-free twin-catwalk torsion score for differential V, n={order_value}, parity={parity_label}, corr<=-0.50"}  # Store the global torsion classification without frequency matching.
            used.add(int(choice["mode"]))  # Prevent the same numerical eigenvector from receiving another physical label.
        else:  # Handle a physically absent global torsion candidate honestly.
            selected[label] = {"status": "unidentified", "family": "T", "global_torsion_definition": "Theta=(w_D-w_U)/42.90", "selection_rule": f"no differential-vertical main-span mode with n={order_value}, parity={parity_label}, corr<=-0.50"}  # Preserve an explicit missing-label state.
    meta["global_torsion_rule"] = "Theta=(w_D-w_U)/42.90; require vertical-dominant main-span mode with signed U/D correlation <= -0.50"  # Record the corrected twin-catwalk torsion definition in classification metadata.
    return raw, selected, meta  # Return raw modes, corrected fourteen labels, and target-free metadata.
def plot_global_torsion_shapes(model: dict, system: dict, floor_nodes: list[int], vectors: np.ndarray, selected: dict[str, dict]) -> None:  # Draw the three corrected system-roll mode shapes for audit.
    x_values = np.array([base.xyz(model, node_id)[0] for node_id in floor_nodes])  # Read the ordered MCT longitudinal section coordinates.
    for label in ("TA1", "TS1", "TS2"):  # Traverse the three global torsional labels.
        record = selected[label]  # Read the corrected target-free classification record.
        if "mode" not in record:  # Skip a label with no physically identified eigenvector.
            continue  # Continue to the next torsional label.
        upstream, downstream = extract_floor_vertical(system, floor_nodes, vectors, int(record["mode"]))  # Recover the two vertical centreline fields.
        theta = (downstream - upstream) / (2.0 * abs(base.CAT_CENTRES[1]))  # Convert differential vertical motion to the small global roll coordinate using 42.90 m spacing.
        scale = max(float(np.max(np.abs(theta))), 1.0e-30)  # Form a stable normalization factor for plotting only.
        base.plt.figure(figsize=(10.0, 4.0))  # Create one independent global-torsion shape figure.
        base.plt.plot(x_values, theta / scale, label="Global torsion Theta")  # Plot the normalized double-catwalk roll field.
        base.plt.axhline(0.0, linewidth=0.7)  # Show the zero-roll reference line.
        base.plt.xlabel("MCT longitudinal coordinate / m")  # Label the longitudinal coordinate.
        base.plt.ylabel("Normalized Theta")  # Label the dimensionless normalized global torsion coordinate.
        base.plt.title(f"{label}: mode {record['mode']}, {record['frequency_hz']:.6f} Hz")  # State the physical label, numerical order, and frozen frequency.
        base.plt.legend()  # Display the global-torsion curve identity.
        base.plt.grid(True, alpha=0.25)  # Add a light reading grid.
        base.plt.tight_layout()  # Fit labels inside the canvas.
        base.plt.savefig(OUT / f"mode_shape_{label}.png", dpi=170)  # Save the corrected global-torsion shape figure.
        base.plt.close()  # Release the current plot canvas.
def main() -> int:  # Execute the final clean calculation with corrected twin-catwalk torsion classification.
    model = base.load_mct()  # Parse and SHA-check the original MCT source body.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-catwalk aggregate chain.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope aggregate chain.
    static = v2.inverse_static_v2(model, floor_nodes, floor_elements, top_nodes, top_elements)  # Reconstruct prestress from formed geometry and explicit dead-load inputs without MCT internal forces.
    if static["equilibrium_relative_residual"] > v2.STATIC_TOLERANCE:  # Enforce the unchanged inverse-equilibrium compatibility threshold.
        raise RuntimeError(f"Inverse equilibrium residual is {static['equilibrium_relative_residual']:.6e}")  # Reject an incompatible static state rather than relaxing the criterion.
    system = v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble the mass-consistent explicit 44-rope, portal, and passage model.
    frequencies, vectors, residuals, checks = base.solve_eigen(system)  # Solve and verify the symmetric generalized eigenproblem.
    raw, selected, classification_meta = classify_v3(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Apply the corrected target-free fourteen-family physical classification.
    assumptions = [{"name": "MCT use", "value": "formed coordinates, topology, groups, restraint topology, SELFWEIGHT definition, and explicit second-stage CONLOAD input only; INIFORCE, INI-EFORCE, and modal results excluded"}, {"name": "inverse statics", "value": "prestress reconstructed by bounded nodal equilibrium on prescribed formed geometry; acceptance residual <= 0.005"}, {"name": "floor ropes", "value": "16 explicit ropes per catwalk; one smart rope at each inner local position, mirror-symmetric globally"}, {"name": "gantry ropes", "value": "6 explicit ropes per catwalk, represented as left and right triplets across 7.46 m"}, {"name": "secondary floor system", "value": "2.766 kN/m lower-system self-weight on formed length, decomposed into explicit floor ropes, handrail masses, and residual width-distributed mass"}, {"name": "second-stage mass", "value": "prescribed second-stage vertical loads converted to mass after subtracting explicitly represented portal and half-passage mass at the corresponding single-catwalk stations"}, {"name": "portals", "value": "71 per catwalk; 1429.98 kg each; 161x161x8 equivalent two-column frame"}, {"name": "passages", "value": "21 full multi-port equivalents; 10130 kg each; three phi152x6 chords; longitudinal bracing stiffness factor 0.03"}, {"name": "global torsion", "value": "twin-catwalk system roll Theta=(w_D-w_U)/42.90; T modes are vertical-dominant main-span modes with negative signed U/D correlation"}, {"name": "supports", "value": "current MCT restraint topology interpreted as the fixed-contact linearization state"}, {"name": "classification", "value": "L/V/T-system energy and kinematics, main-span sine order, parity, signed U/D correlation, and span localization only; no target frequency"}]  # Record every decisive model and classification assumption.
    frozen = {"kind": "clean_theory_44_rope_catwalk_frozen_v3", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "source_mct_bytes": model["source"]["bytes"], "target_frequency_used": False, "mct_internal_force_used": False, "frequency_reproduced": False, "not_attach_ta1": True, "not_attach_fourteen_mode_table": True, "topology": {"explicit_floor_ropes": 32, "explicit_gantry_ropes": 12, "explicit_ropes_total": 44, "portals": 142, "passages": 21, "floor_chain_nodes": len(floor_nodes), "floor_chain_elements": len(floor_elements), "top_chain_nodes": len(top_nodes), "top_chain_elements": len(top_elements)}, "assumptions": assumptions, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": checks, "mass_audit_v2": system["mass_audit_v2"], "smart_index_zero_based": system["smart_index"], "portal_map": system["portals"], "passage_parameters": system["passages"], "raw_modes": raw, "classified_14": selected, "classification_meta": {key: value for key, value in classification_meta.items() if key != "selected_shapes"}}  # Form the target-free frozen result object with corrected global torsion labels.
    frozen_path = OUT / "frozen_results.json"  # Define the target-free frozen result path.
    base.dump(frozen_path, frozen)  # Write frequencies and classifications before external target frequencies are loaded.
    frozen_sha = base.sha(frozen_path)  # Freeze the target-free calculation identity with SHA-256.
    base.write_csv(raw, selected, [])  # Write the raw spectrum and corrected fourteen-family classification without external targets.
    base.plots(raw, selected, [], classification_meta)  # Write the spectrum and all non-system-torsion selected shape plots.
    plot_global_torsion_shapes(model, system, floor_nodes, vectors, selected)  # Write the corrected TA1, TS1, and TS2 global-torsion shape plots.
    summary = {"kind": "clean_theory_44_rope_catwalk_summary_v3", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha, "identified_count": sum(1 for item in selected.values() if "frequency_hz" in item), "inverse_static": frozen["inverse_static"], "matrix_checks": checks, "mass_audit_v2": system["mass_audit_v2"], "target_frequency_used": False, "mct_internal_force_used": False, "frequency_reproduced": False, "not_attach_ta1": True, "not_attach_fourteen_mode_table": True}  # Build the concise target-free final summary.
    base.dump(OUT / "summary.json", summary)  # Write the concise solver summary.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Write every explicit rope's recovered unstressed length and force.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every primary target-free result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2))  # Print the final target-free calculation receipt into the workflow log.
    return 0  # Return successful completion.
if __name__ == "__main__":  # Execute only when the final revised solver is invoked directly.
    raise SystemExit(main())  # Run the complete final clean calculation.
