from __future__ import annotations  # Enable modern annotations.

import hashlib  # Bind the independent check to exact input bytes.
import importlib.util  # Load reviewed modules without changing the package layout.
import json  # Write a machine-readable independent audit.
import math  # Represent unavailable Attachment entries without string sentinels.
from pathlib import Path  # Resolve shared model and result paths.

import numpy as np  # Recompute reaction means and covariance propagation.
import pandas as pd  # Join support identities with Attachment 2-3 references.

HERE = Path(__file__).resolve().parent  # Anchor all independent outputs here.
ROOT = HERE.parents[1]  # Resolve the shared workspace root.
STRUCTURE_PATH = ROOT / "output" / "double_mct_equivalent_passage_model.py"  # Bind the current gate-corrected builder.
RECOVERY_PATH = ROOT / "tmp" / "reaction_recovery" / "reaction_recovery.py"  # Bind the independently derived partitioned-equilibrium module.
MCT_PATH = ROOT / "tmp" / "mct_pair_sources" / "catwalk_gantry_rope_combined_2.mct"  # Bind the authoritative MCT.
STATIONS_PATH = ROOT / "tmp" / "mct_pair_sources" / "passage_station_authoritative_map.csv"  # Bind the 21 exact stations.
PASSAGE_PATH = ROOT / "tmp" / "gate_passage_condensation" / "K12_translation_ports.csv"  # Bind the corrected four-port matrix.
STATE_PATH = ROOT / "output" / "double_mct_buffeting_results_gate_corrected_final" / "reduced_response_state.npz"  # Read only the final 150-mode reduced response state.
MAIN_REACTION_PATH = ROOT / "output" / "double_mct_buffeting_results_gate_corrected_final" / "support_reaction_recovery.csv"  # Use the final main output only after independent recomputation.
MAIN_AUDIT_PATH = ROOT / "output" / "double_mct_buffeting_results_gate_corrected_final" / "calculation_audit.json"  # Read final nominal wind metadata.
MAPPING_PATH = ROOT / "tmp" / "reaction_recovery" / "attachment_table5_support_mapping.csv"  # Bind the reviewed position map.
REFERENCE_PATH = ROOT / "tmp" / "reaction_recovery" / "attachment_table5_2_5_3_reference.csv"  # Bind the transcribed tables 5-2 and 5-3.
ATTACHMENT_SPEED_MPS = 30.1  # Read the comparison wind speed from the table captions.


def sha256_file(path: Path) -> str:  # Hash a file without changing it.
    digest = hashlib.sha256()  # Initialize SHA-256.
    with path.open("rb") as stream:  # Read binary bytes.
        for block in iter(lambda: stream.read(1024 * 1024), b""):  # Stream bounded blocks.
            digest.update(block)  # Accumulate the digest.
    return digest.hexdigest()  # Return lowercase hexadecimal text.


def load_module(path: Path, name: str) -> object:  # Import a Python module by exact path.
    specification = importlib.util.spec_from_file_location(name, path)  # Build an isolated module specification.
    if specification is None or specification.loader is None:  # Guard against a missing loader.
        raise RuntimeError(f"Cannot load module {path}.")  # Stop on an incomplete source tree.
    module = importlib.util.module_from_spec(specification)  # Allocate the module.
    specification.loader.exec_module(module)  # Execute the exact file.
    return module  # Return its functions and constants.


def build_yz_comparison(reactions: pd.DataFrame, mapping: pd.DataFrame, reference: pd.DataFrame, nominal_speed_mps: float) -> pd.DataFrame:  # Compare only constrained transverse and vertical reactions.
    rows: list[dict[str, object]] = []  # Collect one row for each width, location, and recoverable Y/Z axis.
    static_speed_factor = (ATTACHMENT_SPEED_MPS / nominal_speed_mps) ** 2  # Mean quasi-steady force is exactly proportional to U squared in this linear model.
    for mapped in mapping.itertuples(index=False):  # Traverse all eight Attachment locations.
        for width in ("L", "R"):  # Keep the two physical catwalk widths separate.
            for axis in ("Y_transverse", "Z_vertical"):  # Enforce the requested Y/Z-only comparison.
                selected = reactions[(reactions["width"] == width) & (reactions["mct_node"] == int(mapped.mct_node)) & (reactions["global_axis"] == axis)]  # Select one constrained DOF.
                if len(selected) != 1:  # Require a unique supported Y or Z coordinate.
                    raise ValueError(f"Expected one {width} N{mapped.mct_node} {axis} reaction, found {len(selected)}.")  # Stop on mapping drift.
                model_row = selected.iloc[0]  # Read the independent recovered result.
                attachment = reference[(reference["attachment_row"] == mapped.attachment_row) & (reference["global_axis"] == axis)]  # Match the reordered Attachment component.
                if len(attachment) != 1:  # Require one transcribed reference row.
                    raise ValueError(f"Missing Attachment reference for {mapped.attachment_row} {axis}.")  # Stop on a table transcription gap.
                reference_row = attachment.iloc[0]  # Read table 5-2/5-3 values.
                static_model_nominal = float(model_row["static_wind_reaction_increment_kN"])  # Read nominal-speed static increment.
                static_model_attachment_speed = static_model_nominal * static_speed_factor  # Rescale the mean exactly for the same coefficient kernel.
                static_reference = float(reference_row["static_wind_increment_kN"]) if pd.notna(reference_row["static_wind_increment_kN"]) else math.nan  # Read the Attachment static increment when present.
                sigma_reference = float(reference_row["buffeting_RMS_kN"]) if pd.notna(reference_row["buffeting_RMS_kN"]) else math.nan  # Read the Attachment fluctuating RMS when present.
                static_error = static_model_attachment_speed - static_reference if np.isfinite(static_reference) else math.nan  # Form the raw-axis difference while preserving the unresolved source sign convention.
                sigma_model = float(model_row["buffeting_reaction_sigma_kN"])  # Read the nominal-speed reaction RMS.
                rows.append({"attachment_row": mapped.attachment_row, "width": width, "mct_node": int(mapped.mct_node), "global_axis": axis, "constraint_status": "constrained", "model_nominal_speed_mps": nominal_speed_mps, "attachment_speed_mps": ATTACHMENT_SPEED_MPS, "model_static_increment_U44p9_kN": static_model_nominal, "model_static_increment_rescaled_U30p1_kN": static_model_attachment_speed, "attachment_static_increment_U30p1_kN": static_reference, "static_raw_axis_difference_kN": static_error, "static_sign_convention_aligned": False, "model_buffeting_sigma_U44p9_kN": sigma_model, "attachment_buffeting_RMS_U30p1_kN": sigma_reference, "buffeting_like_for_like_speed": False, "comparison_note": "Static mean is U^2-rescaled within the adopted kernel, but the Attachment signed-reaction convention is not proven identical; RMS is shown without a ratio because spectrum, coherence, and modal filtering are speed-dependent."})  # Record an honest comparison row.
    return pd.DataFrame(rows)  # Return the 32-row Y/Z table.


def main() -> None:  # Independently rebuild Kcf and recover all support reactions from the saved reduced state.
    HERE.mkdir(parents=True, exist_ok=True)  # Ensure the requested independent output directory exists.
    structure = load_module(STRUCTURE_PATH, "gate_corrected_structure_independent")  # Load the current structural builder.
    recovery = load_module(RECOVERY_PATH, "gate_corrected_reaction_recovery_independent")  # Load the independently derived equilibrium functions.
    parsed = structure.parse_mct(MCT_PATH)  # Parse the authoritative source model.
    stations = pd.read_csv(STATIONS_PATH, encoding="utf-8-sig")  # Read exact passage positions.
    model = structure.build_double_model(parsed, stations, PASSAGE_PATH)  # Rebuild the gate-corrected global tangent stiffness.
    with np.load(STATE_PATH) as state:  # Read the final response state without using the main reaction CSV.
        modes = np.asarray(state["modes"], dtype=float)  # Read the exact retained mode matrix.
        q_static = np.asarray(state["q_static"], dtype=float)  # Read nominal static modal coordinates.
        modal_covariance = np.asarray(state["modal_covariance"], dtype=float)  # Read full correlated modal covariance.
        saved_free_dofs = np.asarray(state["free_dofs"], dtype=int)  # Read the saved reduction mapping.
        frequencies_hz = np.asarray(state["frequencies_hz"], dtype=float)  # Read the exact retained frequencies.
    if not np.array_equal(saved_free_dofs, np.asarray(model["free_dofs"], dtype=int)):  # Prevent a stale-state/model mismatch.
        raise ValueError("Saved free DOFs do not match the rebuilt gate-corrected model.")  # Stop rather than mix model revisions.
    fixed_static, static_n = recovery.static_reaction(model, modes=modes, q_static=q_static)  # Independently recover nominal mean reaction increments.
    fixed_dynamic, reaction_covariance_n2, sigma_n = recovery.reaction_covariance_from_q(model, modes, modal_covariance)  # Independently propagate complete modal covariance.
    if not np.array_equal(fixed_static, fixed_dynamic):  # Require identical constrained-DOF ordering.
        raise ValueError("Static and dynamic constrained-DOF order differs.")  # Stop on an invalid join.
    static_table = recovery.reactions_to_table(model, fixed_static, static_n, "static_wind_reaction_increment")  # Add MCT provenance and convert N to kN.
    sigma_table = recovery.reactions_to_table(model, fixed_dynamic, sigma_n, "buffeting_reaction_sigma")  # Add MCT provenance and convert RMS to kN.
    reactions = static_table.merge(sigma_table[["global_dof", "buffeting_reaction_sigma_N", "buffeting_reaction_sigma_kN"]], on="global_dof", how="inner", validate="one_to_one")  # Form one row per constrained DOF.
    reactions["reaction_sign"] = "support action on structure"  # Freeze the sign convention.
    reactions["direct_support_wind_load_N"] = 0.0  # Record fc=0 for the main-span wind mapping.
    reactions.to_csv(HERE / "independent_all_108_support_reactions.csv", index=False)  # Save all independently recovered constrained directions.
    main_audit = json.loads(MAIN_AUDIT_PATH.read_text(encoding="utf-8"))  # Read nominal speed only after the independent recovery.
    nominal_speed_mps = float(main_audit["wind"]["mean_speed_mps"])  # Read the final-case speed.
    mapping = pd.read_csv(MAPPING_PATH)  # Read the eight-location mapping.
    reference = pd.read_csv(REFERENCE_PATH)  # Read tables 5-2 and 5-3.
    mapped_status = pd.concat([mapping.assign(width=width) for width in ("L", "R")], ignore_index=True)  # Expand each Attachment position to both physical catwalk widths.
    mapped_status["YZ_comparison_included"] = True  # Confirm that every mapped Y and Z DOF is constrained and recoverable.
    mapped_status["X_comparison_included"] = False  # Enforce the requested Y/Z-only scope even at the two fully fixed edge-side tower nodes.
    mapped_status["X_scope_note"] = np.where(mapped_status["global_X_status"].eq("free"), "UX sliding/free: no nodal support reaction exists", "UX constrained but omitted by requested Y/Z-only comparison")  # Distinguish six sliding locations from two fixed-X locations.
    mapped_status.to_csv(HERE / "mapped_attachment_support_dof_status.csv", index=False)  # Save the explicit constraint and comparison audit.
    yz_comparison = build_yz_comparison(reactions, mapping, reference, nominal_speed_mps)  # Build only the requested recoverable axes.
    yz_comparison.to_csv(HERE / "attachment_table5_2_5_3_YZ_comparison.csv", index=False)  # Save the honest cross-speed comparison.
    main_reactions = pd.read_csv(MAIN_REACTION_PATH)  # Read the main recovery only for a posteriori verification.
    validation = reactions.merge(main_reactions, on=["width", "mct_node", "global_node_index", "global_dof", "global_axis"], suffixes=("_independent", "_main"), validate="one_to_one")  # Align the two calculations.
    static_difference = validation["static_wind_reaction_increment_kN_independent"] - validation["static_wind_reaction_increment_kN_main"]  # Compute main-versus-independent mean differences.
    sigma_difference = validation["buffeting_reaction_sigma_kN_independent"] - validation["buffeting_reaction_sigma_kN_main"]  # Compute main-versus-independent RMS differences.
    validation["static_difference_kN"] = static_difference  # Preserve rowwise mean differences.
    validation["sigma_difference_kN"] = sigma_difference  # Preserve rowwise RMS differences.
    validation.to_csv(HERE / "main_vs_independent_108_dof_validation.csv", index=False)  # Save the exact numerical cross-check.
    yz_numeric = yz_comparison[pd.notna(yz_comparison["attachment_buffeting_RMS_U30p1_kN"])]  # Isolate rows with reported RMS values.
    tower_main = yz_numeric[yz_numeric["attachment_row"].isin(["北塔转索鞍中跨侧", "南塔转索鞍中跨侧"])]  # Isolate the load-path-active tower main-span supports.
    near_zero_threshold_kn = 1.0e-3  # Treat sub-newton reaction RMS as numerical zero at the kN reporting scale.
    near_zero = yz_comparison[np.abs(yz_comparison["model_buffeting_sigma_U44p9_kN"]) < near_zero_threshold_kn]  # Count disconnected or inactive mapped directions.
    audit = {  # Build an independent provenance and interpretation record.
        "status": "INDEPENDENT_GATE_CORRECTED_REACTION_RECOVERY_COMPLETE",  # State completion.
        "formula": "R_c=K_cf*Phi*q-f_c; Sigma_R=A*Sigma_q*A^T with A=K_cf*Phi",  # Record the exact specialization.
        "reaction_sign": "support action on structure",  # Record force direction.
        "dynamic_cross_terms": {"M_cf": "zero because mass is diagonal lumped", "C_cf": "not included because modal damping does not define a unique physical support-row damping block", "f_c": "zero because the current wind mapping applies no direct constrained-node load"},  # State why no extra terms appear.
        "input_hashes": {"structure_py": sha256_file(STRUCTURE_PATH), "reaction_recovery_py": sha256_file(RECOVERY_PATH), "mct": sha256_file(MCT_PATH), "stations": sha256_file(STATIONS_PATH), "passage_matrix": sha256_file(PASSAGE_PATH), "reduced_state": sha256_file(STATE_PATH)},  # Bind every independent input.
        "dimensions": {"total_dofs": int(len(model["dof_mass_kg"])), "free_dofs": int(len(model["free_dofs"])), "constrained_dofs": int(len(fixed_static)), "retained_modes": int(modes.shape[1]), "reaction_covariance_shape": list(reaction_covariance_n2.shape)},  # Record array sizes.
        "frequency_range_hz": [float(frequencies_hz[0]), float(frequencies_hz[-1])],  # Record modal truncation.
        "main_output_validation": {"matched_rows": int(len(validation)), "maximum_absolute_static_difference_kN": float(np.max(np.abs(static_difference))), "maximum_absolute_sigma_difference_kN": float(np.max(np.abs(sigma_difference)))},  # Quantify exact reproduction of the main recovery.
        "attachment_comparison": {"axes_included": ["Y_transverse", "Z_vertical"], "X_excluded": "UX is free at six mapped sliding nodes; UX is constrained at N154/N450 but omitted to keep the requested Y/Z-only scope", "model_speed_mps": nominal_speed_mps, "attachment_speed_mps": ATTACHMENT_SPEED_MPS, "same_speed": False, "static_speed_rescaling": float((ATTACHMENT_SPEED_MPS / nominal_speed_mps) ** 2), "static_sign_convention_aligned": False, "buffeting_ratio_reported": False, "reason_no_buffeting_speed_scaling": "wind PSD, coherence, and modal filtering vary with U; a U=30.1 stochastic rerun is required for like-for-like RMS"},  # Prevent false ratio claims.
        "load_path_findings": {"mapped_YZ_rows": int(len(yz_comparison)), "near_zero_definition": f"absolute RMS below {near_zero_threshold_kn} kN", "near_zero_model_sigma_rows": int(len(near_zero)), "tower_main_span_reported_RMS_rows": int(len(tower_main)), "tower_main_span_model_sigma_range_kN_at_nominal_speed": [float(tower_main["model_buffeting_sigma_U44p9_kN"].min()), float(tower_main["model_buffeting_sigma_U44p9_kN"].max())], "tower_main_span_attachment_RMS_range_kN_at_30p1": [float(tower_main["attachment_buffeting_RMS_U30p1_kN"].min()), float(tower_main["attachment_buffeting_RMS_U30p1_kN"].max())]},  # Summarize the only load-path-active mapped locations.
        "interpretation_limits": ["The static U=30.1 values are exact U-squared rescalings only within the adopted linear quasi-steady zero-angle coefficient kernel.", "The Attachment signed reaction convention has not been proven identical to the model's support-on-structure convention; static differences are raw axis differences, not validated signed errors.", "Buffeting U=44.9 and Attachment U=30.1 values are not a like-for-like validation; no RMS ratio is asserted.", "Near-zero anchor and tower-edge reactions are a consequence of the present main-span loading and support segmentation, not a numerical recovery failure.", "The tangent model does not contain the dead-load reaction baseline, so Table 5-3 total deadload-plus-wind reactions cannot be reconstructed from q_static.", "A formal Attachment RMS reproduction requires rerunning the stochastic wind field at U=30.1 with the same declared spectral assumptions."],  # State the comparison boundary.
    }  # Finish the independent audit.
    (HERE / "independent_reaction_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")  # Save the machine-readable audit.


if __name__ == "__main__":  # Execute only as a script.
    main()  # Run the independent recovery and comparison.
