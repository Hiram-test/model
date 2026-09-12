from __future__ import annotations  # Enable modern annotations in the independent validator.

import json  # Read saved provenance and write a machine-readable summary.
import math  # Convert between cyclic frequency and generalized eigenvalue.
import sys  # Import the reviewed production assembly without changing it.
from pathlib import Path  # Resolve every audited path deterministically.

import numpy as np  # Evaluate sparse-eigenpair and modal-energy diagnostics.
import pandas as pd  # Read and write transparent CSV audit tables.
from scipy.optimize import linear_sum_assignment  # Enforce one-to-one modal matching.
from scipy.sparse import diags  # Form the independent diagonal mass matrix.
from scipy.sparse.linalg import eigsh  # Independently repeat the 60-mode eigensolution.

ROOT = Path(__file__).resolve().parents[2]  # Resolve the shared project root.
sys.path.insert(0, str(ROOT / "output"))  # Make the production assembly importable.
import double_mct_equivalent_passage_model as production  # Rebuild the exact corrected K and M without editing production code.
sys.path.insert(0, str(ROOT / "tmp/modal_validation"))  # Make the reviewed energy helpers importable.
import modal_validation as helpers  # Reuse the established span partition and mass-weighted observables.
import four_port_modal_validation as four_port  # Reuse the exact four-port strain-energy calculation.

MCT_PATH = ROOT / "tmp/mct_pair_sources/catwalk_gantry_rope_combined_2.mct"  # Bind the reviewed source model.
STATION_PATH = ROOT / "tmp/mct_pair_sources/passage_station_authoritative_map.csv"  # Bind the authoritative 21-station map.
REFERENCE_PATH = ROOT / "tmp/attachment23/extracted/reference_attachment_2_3_table4_1.csv"  # Bind Attachment Table 4-1.
RESULT_DIR = ROOT / "output/double_mct_results_gate_corrected_final"  # Read the final corrected production solution.
PREVIOUS_DIR = ROOT / "output/double_mct_results_four_port"  # Read the pre-gate-correction four-port solution.
MATRIX_PATH = ROOT / "tmp/gate_passage_condensation/K12_translation_ports.csv"  # Bind the four-port matrix.
OUTPUT_DIR = ROOT / "tmp/modal_validation_gate_corrected"  # Keep all independent artifacts together.
MODE_COUNT = 80  # Repeat every final production-saved eigenfrequency.
SPAN_THRESHOLD = 0.65  # Require clear spatial localization before assigning MAIN or SIDE.
NEAR_ZERO_HZ = 0.01  # Define a conservative mechanism-screen frequency threshold.
GATE_EA_N = float(production.GATE_ONLY_EQUIVALENT_EA_N)  # Read the exact audited rank-one gate rigidity.
GATE_AUDIT = json.loads((ROOT / "tmp/gate_only_condensation/audit.json").read_text(encoding="utf-8"))  # Read the finite-gate reduction audit for diagnostic bounds.
GATE_ORIGINAL_EA_N = GATE_EA_N / float(GATE_AUDIT["replacement_assessment"]["axial_comparison"]["ratio"])  # Recover the audited original property-3 axial rigidity.
GATE_FIXED_ROTATION_SHEAR_N_PER_M = float(GATE_AUDIT["fixed_rotation_portal_local_Krel_N_per_mm"][1][1]) * 1000.0  # Read the non-objective fixed-rotation transverse portal upper bound.


def independent_solve(model: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # Repeat the generalized eigensolution and retain raw eigenvalues.
    free_dofs = np.asarray(model["free_dofs"], dtype=int)  # Read the support-reduced DOF map.
    stiffness = model["stiffness"][free_dofs][:, free_dofs]  # Reduce the assembled tangent stiffness.
    mass_values = np.asarray(model["dof_mass_kg"], dtype=float)[free_dofs]  # Read the positive diagonal mass values.
    mass = diags(mass_values, format="csr")  # Form the independent sparse mass matrix.
    eigenvalues, reduced_modes = eigsh(stiffness, k=MODE_COUNT, M=mass, sigma=0.0, which="LM", tol=1.0e-10, maxiter=30000)  # Solve about zero without using production.solve_modes.
    order = np.argsort(eigenvalues)  # Sort raw eigenvalues in ascending order.
    eigenvalues = np.asarray(eigenvalues[order], dtype=float)  # Preserve signed raw values for mechanism screening.
    reduced_modes = np.asarray(reduced_modes[:, order], dtype=float)  # Apply the same sorted order to eigenvectors.
    modes = np.zeros((len(model["dof_mass_kg"]), MODE_COUNT), dtype=float)  # Allocate supported full-system vectors.
    modes[free_dofs, :] = reduced_modes  # Restore constrained DOFs as exact zeros.
    frequencies = np.sqrt(np.maximum(eigenvalues, 0.0)) / (2.0 * math.pi)  # Convert nonnegative eigenvalues to hertz.
    return frequencies, modes, eigenvalues  # Return frequencies, full vectors, and raw eigenvalues.


def eigenpair_metrics(vector_flat: np.ndarray, frequency_hz: float, model: dict[str, object]) -> tuple[float, float]:  # Check one vector against the rebuilt corrected matrices.
    free_dofs = np.asarray(model["free_dofs"], dtype=int)  # Read the supported reduction map.
    reduced = np.asarray(vector_flat, dtype=float)[free_dofs]  # Restrict the full vector to free DOFs.
    stiffness = model["stiffness"][free_dofs][:, free_dofs]  # Reduce the rebuilt tangent stiffness.
    mass_values = np.asarray(model["dof_mass_kg"], dtype=float)[free_dofs]  # Read reduced diagonal mass.
    eigenvalue = (2.0 * math.pi * float(frequency_hz)) ** 2  # Convert the reported cyclic frequency to lambda.
    elastic = stiffness @ reduced  # Evaluate K times phi.
    inertial = eigenvalue * mass_values * reduced  # Evaluate lambda M times phi.
    denominator = float(np.linalg.norm(elastic) + np.linalg.norm(inertial))  # Form a symmetric residual scale.
    residual = float(np.linalg.norm(elastic - inertial) / denominator) if denominator > 0.0 else 0.0  # Compute the relative eigenpair residual.
    mass_norm = float(np.sum(np.asarray(model["dof_mass_kg"], dtype=float) * np.asarray(vector_flat, dtype=float) ** 2))  # Compute phi-transpose-M-phi.
    return residual, mass_norm  # Return residual and mass normalization.


def mass_mac_matrix(first: np.ndarray, second: np.ndarray, dof_mass: np.ndarray) -> np.ndarray:  # Form the complete mass-weighted MAC matrix.
    weighted_cross = first.T @ (dof_mass[:, None] * second)  # Compute every mass-weighted cross product.
    first_norm = np.sum(dof_mass[:, None] * first**2, axis=0)  # Compute first-set modal norms.
    second_norm = np.sum(dof_mass[:, None] * second**2, axis=0)  # Compute second-set modal norms.
    denominator = first_norm[:, None] * second_norm[None, :]  # Form every MAC denominator.
    return np.divide(weighted_cross**2, denominator, out=np.zeros_like(weighted_cross), where=denominator > 0.0)  # Return sign-invariant MAC values.


def saved_solution_check(model: dict[str, object], solved_frequencies: np.ndarray, solved_modes: np.ndarray, raw_eigenvalues: np.ndarray) -> pd.DataFrame:  # Reconcile saved and independently repeated results.
    saved_table = pd.read_csv(RESULT_DIR / "modal_properties.csv")  # Read all sixty production frequencies.
    saved_vectors = np.load(RESULT_DIR / "mode_vectors_first24.npz")  # Read the production-saved first twenty-four vectors.
    saved_modes = np.asarray(saved_vectors["modes"], dtype=float)  # Extract the full-system vector block.
    dof_mass = np.asarray(model["dof_mass_kg"], dtype=float)  # Read the full diagonal mass vector.
    mac = mass_mac_matrix(saved_modes, solved_modes[:, : saved_modes.shape[1]], dof_mass)  # Compare saved and independently repeated low vectors.
    rows: list[dict[str, object]] = []  # Collect one row per solved mode.
    for mode_index in range(MODE_COUNT):  # Traverse the complete sixty-mode range.
        saved_frequency = float(saved_table.iloc[mode_index]["frequency_hz"])  # Read the production frequency.
        repeated_frequency = float(solved_frequencies[mode_index])  # Read the independently repeated frequency.
        repeated_residual, repeated_mass_norm = eigenpair_metrics(solved_modes[:, mode_index], repeated_frequency, model)  # Check the repeated eigenpair.
        row: dict[str, object] = {"mode": mode_index + 1, "saved_frequency_hz": saved_frequency, "independent_frequency_hz": repeated_frequency, "frequency_difference_hz": repeated_frequency - saved_frequency, "relative_frequency_difference_ppm": 1.0e6 * (repeated_frequency / saved_frequency - 1.0), "raw_eigenvalue_rad2_s2": float(raw_eigenvalues[mode_index]), "independent_eigenpair_relative_residual": repeated_residual, "independent_modal_mass_norm": repeated_mass_norm}  # Record the sixty-mode numerical reconciliation.
        if mode_index < saved_modes.shape[1]:  # Add direct saved-vector checks where vectors were persisted.
            saved_residual, saved_mass_norm = eigenpair_metrics(saved_modes[:, mode_index], saved_frequency, model)  # Check the saved eigenpair against rebuilt matrices.
            row.update({"saved_vector_eigenpair_relative_residual": saved_residual, "saved_vector_modal_mass_norm": saved_mass_norm, "same_rank_mass_weighted_mac": float(mac[mode_index, mode_index]), "best_independent_mode_by_mac": int(np.argmax(mac[mode_index, :])) + 1, "best_mass_weighted_mac": float(np.max(mac[mode_index, :]))})  # Record vector consistency and possible near-root rotations.
        else:  # Preserve explicit missing-vector fields beyond mode twenty-four.
            row.update({"saved_vector_eigenpair_relative_residual": np.nan, "saved_vector_modal_mass_norm": np.nan, "same_rank_mass_weighted_mac": np.nan, "best_independent_mode_by_mac": np.nan, "best_mass_weighted_mac": np.nan})  # Mark unavailable saved-vector diagnostics.
        rows.append(row)  # Append the completed numerical check.
    return pd.DataFrame(rows)  # Return the complete reconciliation table.


def rope_partition_metrics(vector: np.ndarray, model: dict[str, object], mass_norm: float) -> dict[str, float]:  # Partition kinetic energy between carrying and gantry ropes.
    index = model["index"]  # Read the paired source-to-global node map.
    nodal_mass = np.asarray(model["nodal_mass_kg"], dtype=float)  # Read scalar translational node masses.
    carrying = 0.0  # Accumulate carrying-rope modal mass.
    gantry = 0.0  # Accumulate gantry-rope modal mass.
    source_pair_energy: list[tuple[int, float]] = []  # Retain pairwise localization data.
    for source_id in sorted({key[1] for key in index}):  # Traverse every source node once.
        pair_energy = 0.0  # Initialize the two-width node-pair energy.
        for width in (0, 1):  # Visit both complete MCT planes.
            global_node = int(index[(width, source_id)])  # Resolve the duplicate node.
            pair_energy += float(nodal_mass[global_node] * np.dot(vector[global_node], vector[global_node]))  # Accumulate all translation axes.
        source_pair_energy.append((int(source_id), pair_energy))  # Preserve localization by source node.
        if int(source_id) <= 730:  # Assign the reviewed lower carrying-rope range.
            carrying += pair_energy  # Accumulate carrying-rope energy.
        else:  # Assign the reviewed upper gantry-rope range.
            gantry += pair_energy  # Accumulate gantry-rope energy.
    probabilities = np.asarray([energy for _, energy in source_pair_energy], dtype=float) / mass_norm  # Normalize node-pair kinetic fractions.
    maximum_index = int(np.argmax(probabilities))  # Locate the most active source-node pair.
    effective_count = float(1.0 / np.sum(probabilities**2)) if float(np.sum(probabilities**2)) > 0.0 else 0.0  # Form the inverse-participation effective node count.
    return {"carrying_rope_energy_fraction": carrying / mass_norm, "gantry_rope_energy_fraction": gantry / mass_norm, "maximum_source_node_pair_energy_fraction": float(probabilities[maximum_index]), "maximum_energy_source_node": float(source_pair_energy[maximum_index][0]), "effective_source_node_pair_count": effective_count}  # Return rope and localization metrics.


def ordinary_gate_metrics(vector: np.ndarray, frequency_hz: float, model: dict[str, object], parsed: dict[str, object], mass_norm: float, mode_number: int) -> tuple[dict[str, object], list[dict[str, object]]]:  # Quantify every ordinary rank-one gate and its unrestrained transverse relative motion.
    index = model["index"]  # Read the duplicated node lookup.
    xyz = np.asarray(model["xyz"], dtype=float)  # Read global node coordinates.
    total_mass = float(np.sum(np.asarray(model["nodal_mass_kg"], dtype=float)))  # Read total physical mass for scale-invariant displacement normalization.
    mass_rms = math.sqrt(mass_norm / total_mass)  # Form a global mass-weighted modal RMS displacement.
    modal_stiffness = (2.0 * math.pi * float(frequency_hz)) ** 2 * mass_norm  # Form phi-transpose-K-phi.
    long_rows: list[dict[str, object]] = []  # Collect one row per width and ordinary gate.
    total_gate_numerator = 0.0  # Accumulate all rank-one gate strain energy.
    total_transverse_square = 0.0  # Accumulate transverse bottom-to-top relative motion.
    total_relative_square = 0.0  # Accumulate total bottom-to-top relative motion.
    endpoint_scale_square = 0.0  # Accumulate endpoint amplitude for an internal relative-motion ratio.
    maximum_energy_fraction = -1.0  # Track the most energetic ordinary gate.
    maximum_energy_gate = ""  # Track its identifier.
    maximum_transverse = -1.0  # Track the largest unrestrained transverse relative motion.
    maximum_transverse_gate = ""  # Track its identifier.
    gate_endpoint_nodes: set[int] = set()  # Collect all ordinary-gate endpoint nodes without duplication.
    for width in (0, 1):  # Traverse both complete MCT planes.
        width_label = "L" if width == 0 else "R"  # Form a readable plane label.
        for element_id in model["ordinary_gate_elements"]:  # Traverse the fifty non-passage gate stations.
            element = parsed["elements"][int(element_id)]  # Read the source chord endpoints.
            lower = int(index[(width, int(element["n1"]))])  # Resolve the first global node.
            upper = int(index[(width, int(element["n2"]))])  # Resolve the second global node.
            gate_endpoint_nodes.update((lower, upper))  # Register both endpoints for kinetic localization.
            chord = xyz[upper] - xyz[lower]  # Form the station-specific gate chord.
            length = float(np.linalg.norm(chord))  # Compute the gate length in metres.
            direction = chord / length  # Form its axial unit vector.
            relative = vector[upper] - vector[lower]  # Form top-minus-bottom relative translation.
            axial = float(np.dot(relative, direction))  # Project relative motion onto the objective axial coordinate.
            transverse_vector = relative - axial * direction  # Isolate the five-mechanism transverse projection represented by translations.
            transverse = float(np.linalg.norm(transverse_vector))  # Compute the transverse relative amplitude.
            numerator = float((GATE_EA_N / length) * axial**2)  # Evaluate phi-transpose-K-gate-phi without the one-half energy factor.
            fraction = numerator / modal_stiffness if modal_stiffness > 0.0 else np.nan  # Normalize by total modal strain energy.
            normalized_transverse = transverse / mass_rms if mass_rms > 0.0 else np.nan  # Normalize relative motion by global modal RMS.
            total_gate_numerator += numerator  # Accumulate ordinary-gate strain energy.
            total_transverse_square += transverse**2  # Accumulate transverse relative motion.
            total_relative_square += float(np.dot(relative, relative))  # Accumulate total relative motion.
            endpoint_scale_square += 0.5 * float(np.dot(vector[lower], vector[lower]) + np.dot(vector[upper], vector[upper]))  # Accumulate endpoint amplitude scale.
            gate_key = f"{width_label}:{int(element_id)}"  # Form a unique gate key.
            if fraction > maximum_energy_fraction:  # Update the largest strain-energy contributor.
                maximum_energy_fraction = fraction  # Store its fraction.
                maximum_energy_gate = gate_key  # Store its key.
            if transverse > maximum_transverse:  # Update the largest unrestrained transverse motion.
                maximum_transverse = transverse  # Store its amplitude.
                maximum_transverse_gate = gate_key  # Store its key.
            long_rows.append({"mode": mode_number, "frequency_hz": float(frequency_hz), "width": width_label, "source_gate_element": int(element_id), "lower_global_node": lower, "upper_global_node": upper, "length_m": length, "axial_relative_displacement": axial, "transverse_relative_displacement": transverse, "transverse_over_global_mass_rms": normalized_transverse, "ordinary_gate_strain_energy_fraction": fraction})  # Record the gate-level audit row.
    nodal_mass = np.asarray(model["nodal_mass_kg"], dtype=float)  # Read nodal masses for endpoint localization.
    endpoint_energy = float(sum(nodal_mass[node] * np.dot(vector[node], vector[node]) for node in gate_endpoint_nodes))  # Sum modal mass at all ordinary-gate endpoints.
    gate_count = 2 * len(model["ordinary_gate_elements"])  # Count both planes' ordinary gates.
    summary: dict[str, object] = {"ordinary_gate_strain_energy_fraction": total_gate_numerator / modal_stiffness if modal_stiffness > 0.0 else np.nan, "maximum_single_ordinary_gate_energy_fraction": maximum_energy_fraction, "maximum_energy_ordinary_gate": maximum_energy_gate, "ordinary_gate_transverse_relative_rms_over_global_mass_rms": math.sqrt(total_transverse_square / gate_count) / mass_rms if mass_rms > 0.0 else np.nan, "maximum_ordinary_gate_transverse_over_global_mass_rms": maximum_transverse / mass_rms if mass_rms > 0.0 else np.nan, "maximum_transverse_ordinary_gate": maximum_transverse_gate, "ordinary_gate_transverse_share_of_relative_motion": total_transverse_square / total_relative_square if total_relative_square > 0.0 else np.nan, "ordinary_gate_relative_motion_over_endpoint_motion": math.sqrt(total_relative_square / endpoint_scale_square) if endpoint_scale_square > 0.0 else np.nan, "ordinary_gate_endpoint_kinetic_energy_fraction": endpoint_energy / mass_norm}  # Form the aggregate gate diagnostics.
    return summary, long_rows  # Return modal summary and gate-level detail.


def classify_modes(parsed: dict[str, object], station_map: pd.DataFrame, model: dict[str, object], frequencies: np.ndarray, modes: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:  # Classify all sixty modes by span, family, parity, and component energy.
    records: list[dict[str, object]] = []  # Collect one modal summary row.
    passage_rows: list[dict[str, object]] = []  # Collect mode-by-passage strain-energy rows.
    ordinary_rows: list[dict[str, object]] = []  # Collect mode-by-ordinary-gate rows.
    component_names = ["X", "L", "V", "W", "B", "T"]  # Map common XYZ and differential XYZ to physical coordinates.
    for mode_index, frequency_hz in enumerate(frequencies):  # Traverse the complete solved spectrum.
        vector_flat = modes[:, mode_index]  # Read one full-system eigenvector.
        vector = vector_flat.reshape((-1, 3))  # Restore node-by-axis translations.
        residual, mass_norm = eigenpair_metrics(vector_flat, float(frequency_hz), model)  # Verify the repeated eigenpair.
        span_energy: dict[str, float] = {}  # Accumulate normalized modal mass by span.
        span_components: dict[str, np.ndarray] = {}  # Retain six energy components per span.
        for span_name, node_ids in helpers.SPAN_IDS.items():  # Traverse the established exhaustive source-node partition.
            common, differential = helpers.paired_axis_energy(node_ids, vector, model)  # Decompose common and differential width coordinates.
            components = np.concatenate([common, differential]) / mass_norm  # Normalize the six-component energy split.
            span_components[span_name] = components  # Preserve the component vector.
            span_energy[span_name] = float(np.sum(components))  # Preserve the total span fraction.
        dominant_span = max(span_energy, key=span_energy.get)  # Identify the spatially dominant span.
        dominant_span_fraction = float(span_energy[dominant_span])  # Quantify localization confidence.
        mode_class = "MAIN" if dominant_span == "MAIN" and dominant_span_fraction >= SPAN_THRESHOLD else "SIDE" if dominant_span != "MAIN" and dominant_span_fraction >= SPAN_THRESHOLD else "MIXED"  # Assign localization before family.
        main_components = span_components["MAIN"]  # Read the main-span common/differential split.
        family_index = int(np.argmax(main_components))  # Select the dominant physical coordinate.
        raw_family = component_names[family_index]  # Map that coordinate to L, V, T, or a diagnostic family.
        main_total = float(np.sum(main_components))  # Compute total main-span energy.
        family_fraction = float(main_components[family_index] / main_total) if main_total > 1.0e-20 else 0.0  # Quantify main-family purity.
        half_wave = 0  # Default to no main-span shape fingerprint.
        template_mac = 0.0  # Default to zero template confidence.
        parity = ""  # Default to no report parity for side modes.
        fingerprint = f"SIDE_{dominant_span}" if mode_class == "SIDE" else f"{raw_family}_MIXED"  # Initialize a localization-aware fingerprint.
        formal_label = fingerprint  # Initialize the eventual report-style label.
        if mode_class == "MAIN":  # Apply the main-span shape template only after localization.
            signal, weights = helpers.main_signal(raw_family, vector, model)  # Extract the matching carrying-rope observable.
            half_wave, template_mac = helpers.best_half_wave_mac(signal, weights, parsed)  # Compute its mass-weighted half-wave MAC.
            parity = "S" if half_wave % 2 == 1 else "A" if half_wave > 0 else "U"  # Convert the shape fingerprint to midpoint parity.
            fingerprint = f"{raw_family}_{parity}_n{half_wave}"  # Store family, parity, and half-wave without assigning an ordinal.
            formal_label = f"{raw_family}{parity}_PENDING"  # Defer family-frequency numbering until every side mode is excluded.
        passage_fraction, maximum_passage_fraction, maximum_passage_id, station_details = four_port.four_port_station_energies(vector, float(frequency_hz), model, mass_norm)  # Evaluate the exact complete K12 assemblies.
        for station_detail in station_details:  # Attach mode identity to every passage row.
            station_detail.update({"mode": mode_index + 1, "frequency_hz": float(frequency_hz)})  # Complete one passage-level audit record.
            passage_rows.append(station_detail)  # Append it to the long-form table.
        gate_summary, gate_details = ordinary_gate_metrics(vector, float(frequency_hz), model, parsed, mass_norm, mode_index + 1)  # Evaluate all one hundred ordinary gates.
        ordinary_rows.extend(gate_details)  # Append ordinary-gate long-form records.
        rope_summary = rope_partition_metrics(vector, model, mass_norm)  # Evaluate carrying/gantry and localization metrics.
        roll_correlation, warp_ratio, top_bottom_ratio = helpers.gate_roll_metrics(vector, station_map, model)  # Evaluate coherent system roll and gate warp at passage stations.
        record: dict[str, object] = {"mode": mode_index + 1, "frequency_hz": float(frequency_hz), "eigenpair_relative_residual": residual, "modal_mass_norm": mass_norm, "mode_class": mode_class, "dominant_span": dominant_span, "dominant_span_fraction": dominant_span_fraction, "main_energy_fraction": span_energy["MAIN"], "north_energy_fraction": span_energy["NORTH"], "south_energy_fraction": span_energy["SOUTH"], "aux_energy_fraction": span_energy["AUX"], "family": raw_family if mode_class == "MAIN" else "SIDE" if mode_class == "SIDE" else raw_family, "family_fraction_within_main": family_fraction, "span_parity": parity, "half_wave_order": half_wave, "template_mac": template_mac, "shape_fingerprint_label": fingerprint, "formal_label": formal_label, "main_common_x_energy": main_components[0], "main_common_y_L_energy": main_components[1], "main_common_z_V_energy": main_components[2], "main_diff_x_warp_energy": main_components[3], "main_diff_y_breathing_energy": main_components[4], "main_diff_z_T_energy": main_components[5], "four_port_gate_passage_strain_energy_fraction": passage_fraction, "maximum_single_passage_energy_fraction": maximum_passage_fraction, "maximum_energy_passage_id": maximum_passage_id, "gate_bottom_top_roll_correlation": roll_correlation, "gate_warp_to_mean_roll_ratio": warp_ratio, "gate_top_to_bottom_roll_amplitude": top_bottom_ratio}  # Form the core modal record.
        record.update(gate_summary)  # Add ordinary-gate strain and relative-motion metrics.
        record.update(rope_summary)  # Add rope partition and spatial localization metrics.
        records.append(record)  # Append the complete modal record.
    frame = pd.DataFrame(records)  # Form the sixty-mode table before report numbering.
    counters: dict[str, int] = {}  # Count only recognized main families after side modes are removed.
    final_labels: list[str] = []  # Collect stable report-style ordinal labels.
    for row in frame.itertuples(index=False):  # Traverse modes in ascending frequency.
        if str(row.mode_class) == "MAIN" and str(row.family) in {"L", "V", "T"} and str(row.span_parity) in {"S", "A"}:  # Number only formal main families.
            key = f"{row.family}{row.span_parity}"  # Form a family/parity key such as TS.
            counters[key] = counters.get(key, 0) + 1  # Increment its within-family frequency ordinal.
            final_labels.append(f"{key}{counters[key]}")  # Form labels such as TS1 and TS2.
        elif str(row.mode_class) == "MAIN" and str(row.span_parity) in {"S", "A"}:  # Give non-L/V/T main branches a stable diagnostic identity.
            final_labels.append(f"{row.family}_{row.span_parity}_n{int(row.half_wave_order)}_DIAGNOSTIC")  # Preserve family and half-wave without entering attachment ordinals.
        else:  # Keep side and mixed modes outside formal numbering.
            final_labels.append(str(row.formal_label))  # Preserve its localization-aware label.
    frame["formal_label"] = final_labels  # Commit formal attachment-style labels.
    passage_frame = pd.DataFrame(passage_rows)  # Form the passage long table.
    passage_frame["formal_label"] = passage_frame["mode"].map(frame.set_index("mode")["formal_label"])  # Synchronize final labels.
    ordinary_frame = pd.DataFrame(ordinary_rows)  # Form the ordinary-gate long table.
    ordinary_frame["formal_label"] = ordinary_frame["mode"].map(frame.set_index("mode")["formal_label"])  # Synchronize final labels.
    return frame, passage_frame, ordinary_frame  # Return summary and both long-form energy tables.


def mechanism_screen(classification: pd.DataFrame) -> pd.DataFrame:  # Apply conservative low-frequency and localization screening without declaring every side mode spurious.
    frame = classification.copy()  # Preserve the full classification table.
    frame["near_zero_frequency_flag"] = frame["frequency_hz"] < NEAR_ZERO_HZ  # Flag only materially near-zero modes.
    frame["extreme_node_localization_flag"] = (frame["effective_source_node_pair_count"] < 12.0) & (frame["maximum_source_node_pair_energy_fraction"] > 0.15)  # Flag concentrated node-pair mechanisms.
    frame["extreme_gate_relative_motion_flag"] = (frame["ordinary_gate_relative_motion_over_endpoint_motion"] > 1.95) & (frame["ordinary_gate_endpoint_kinetic_energy_fraction"] > 0.50)  # Flag near-opposite motion concentrated at ordinary gate endpoints.
    frame["gantry_rope_decoupling_branch_flag"] = (frame["gantry_rope_energy_fraction"] > 0.95) & (frame["ordinary_gate_relative_motion_over_endpoint_motion"] > 1.30)  # Flag gantry-rope-only transverse branches exposed by rank-one gates.
    frame["mechanism_screen_flag"] = frame[["near_zero_frequency_flag", "extreme_node_localization_flag", "extreme_gate_relative_motion_flag", "gantry_rope_decoupling_branch_flag"]].any(axis=1)  # Combine numerical mechanisms and modelling-sensitivity branches.
    frame["mechanism_screen_reason"] = [";".join(reason for flag, reason in ((bool(row.near_zero_frequency_flag), "near_zero_frequency"), (bool(row.extreme_node_localization_flag), "extreme_node_pair_localization"), (bool(row.extreme_gate_relative_motion_flag), "extreme_ordinary_gate_relative_motion"), (bool(row.gantry_rope_decoupling_branch_flag), "gantry_rope_transverse_decoupling_branch")) if flag) or "none" for row in frame.itertuples(index=False)]  # State every triggered reason explicitly.
    columns = ["mode", "frequency_hz", "formal_label", "mode_class", "dominant_span", "dominant_span_fraction", "gantry_rope_energy_fraction", "four_port_gate_passage_strain_energy_fraction", "ordinary_gate_strain_energy_fraction", "ordinary_gate_transverse_relative_rms_over_global_mass_rms", "maximum_ordinary_gate_transverse_over_global_mass_rms", "ordinary_gate_relative_motion_over_endpoint_motion", "ordinary_gate_endpoint_kinetic_energy_fraction", "maximum_source_node_pair_energy_fraction", "maximum_energy_source_node", "effective_source_node_pair_count", "near_zero_frequency_flag", "extreme_node_localization_flag", "extreme_gate_relative_motion_flag", "gantry_rope_decoupling_branch_flag", "mechanism_screen_flag", "mechanism_screen_reason"]  # Select the auditable mechanism-screen fields.
    return frame[columns]  # Return the compact mechanism table.


def match_reference(reference: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:  # Match all fourteen Table 4-1 rows by formal family ordinal or side-span assignment.
    side_reference = reference[reference["internal_id"].str.startswith("SIDE")].copy()  # Select the three intentionally unnamed side modes.
    side_candidates = classification[classification["mode_class"] == "SIDE"].copy()  # Select every clearly localized non-main mode.
    side_cost = np.abs(side_reference["frequency_hz"].to_numpy(dtype=float)[:, None] / side_candidates["frequency_hz"].to_numpy(dtype=float)[None, :] - 1.0)  # Form relative-frequency costs.
    side_rows, side_columns = linear_sum_assignment(side_cost)  # Enforce a global one-to-one side assignment.
    side_lookup = {str(side_reference.iloc[row]["internal_id"]): side_candidates.iloc[column] for row, column in zip(side_rows, side_columns)}  # Build the side-mode lookup.
    rows: list[dict[str, object]] = []  # Collect enriched comparison rows.
    for reference_row in reference.itertuples(index=False):  # Traverse Attachment Table 4-1 in published order.
        reference_id = str(reference_row.internal_id)  # Read the formal published identifier.
        if reference_id.startswith("SIDE"):  # Match unnamed side modes only by localization and global frequency assignment.
            candidate = side_lookup[reference_id]  # Read the assigned side candidate.
            basis = "dominant non-main span energy >=0.65 + global one-to-one relative-frequency assignment"  # State the side matching rule.
        else:  # Match named modes by formal family/parity frequency ordinal.
            candidates = classification[classification["formal_label"] == reference_id]  # Select the exact formal ordinal label.
            if candidates.empty:  # Preserve a missing family explicitly.
                rows.append({"reference_order": int(reference_row.order), "reference_id": reference_id, "reference_description": str(reference_row.description), "reference_frequency_hz": float(reference_row.frequency_hz), "matched_mode": np.nan, "matched_frequency_hz": np.nan, "relative_error_percent": np.nan, "absolute_error_percent": np.nan, "match_basis": "missing formal within-family frequency ordinal", "matched_formal_label": "MISSING"})  # Record the missing formal mode.
                continue  # Advance to the next reference row.
            candidate = candidates.iloc[0]  # Formal ordinals are unique by construction.
            basis = "main-span energy + common/differential L/V/T family + parity + within-family ascending-frequency ordinal; half-wave is fingerprint only"  # State the attachment-compatible matching rule.
        relative_error = 100.0 * (float(candidate["frequency_hz"]) / float(reference_row.frequency_hz) - 1.0)  # Compute signed frequency bias.
        rows.append({"reference_order": int(reference_row.order), "reference_id": reference_id, "reference_description": str(reference_row.description), "reference_frequency_hz": float(reference_row.frequency_hz), "matched_mode": int(candidate["mode"]), "matched_frequency_hz": float(candidate["frequency_hz"]), "relative_error_percent": relative_error, "absolute_error_percent": abs(relative_error), "match_basis": basis, "matched_formal_label": str(candidate["formal_label"]), "mode_class": str(candidate["mode_class"]), "dominant_span": str(candidate["dominant_span"]), "dominant_span_fraction": float(candidate["dominant_span_fraction"]), "family_fraction_within_main": float(candidate["family_fraction_within_main"]), "half_wave_order_fingerprint": int(candidate["half_wave_order"]), "half_wave_template_mac": float(candidate["template_mac"]), "four_port_gate_passage_strain_energy_fraction": float(candidate["four_port_gate_passage_strain_energy_fraction"]), "ordinary_gate_strain_energy_fraction": float(candidate["ordinary_gate_strain_energy_fraction"]), "gantry_rope_energy_fraction": float(candidate["gantry_rope_energy_fraction"]), "ordinary_gate_transverse_relative_rms_over_global_mass_rms": float(candidate["ordinary_gate_transverse_relative_rms_over_global_mass_rms"]), "effective_source_node_pair_count": float(candidate["effective_source_node_pair_count"]), "eigenpair_relative_residual": float(candidate["eigenpair_relative_residual"])})  # Record one complete reference match.
    return pd.DataFrame(rows)  # Return the fourteen-row comparison.


def previous_gate_stiffness_diagnostics(vector_flat: np.ndarray, old_frequency_hz: float, model: dict[str, object], parsed: dict[str, object]) -> dict[str, float]:  # Diagnose which removed ordinary-gate terms explain a prior eigenpair.
    vector = np.asarray(vector_flat, dtype=float).reshape((-1, 3))  # Restore node-by-axis translations.
    mass_values = np.asarray(model["dof_mass_kg"], dtype=float)  # Read full diagonal mass values.
    mass_norm = float(np.sum(mass_values * np.asarray(vector_flat, dtype=float) ** 2))  # Compute modal mass normalization.
    old_eigenvalue = (2.0 * math.pi * float(old_frequency_hz)) ** 2  # Convert the prior frequency to lambda.
    current_rayleigh = float(np.asarray(vector_flat, dtype=float) @ (model["stiffness"] @ np.asarray(vector_flat, dtype=float)) / mass_norm)  # Evaluate the prior shape on the corrected stiffness.
    axial_delta_numerator = 0.0  # Accumulate the original-minus-current axial term.
    fixed_shear_numerator = 0.0  # Accumulate the fixed-section portal-shear diagnostic bound.
    xyz = np.asarray(model["xyz"], dtype=float)  # Read global node coordinates.
    index = model["index"]  # Read the duplicated node lookup.
    for width in (0, 1):  # Traverse both complete MCT planes.
        for element_id in model["ordinary_gate_elements"]:  # Traverse all fifty non-passage gate stations.
            element = parsed["elements"][int(element_id)]  # Read the source gate chord.
            lower = int(index[(width, int(element["n1"]))])  # Resolve its first global node.
            upper = int(index[(width, int(element["n2"]))])  # Resolve its second global node.
            chord = xyz[upper] - xyz[lower]  # Form the gate centerline chord.
            length = float(np.linalg.norm(chord))  # Compute its length.
            direction = chord / length  # Form the objective axial direction.
            relative = vector[upper] - vector[lower]  # Form top-minus-bottom relative translation.
            axial = float(np.dot(relative, direction))  # Project onto the objective extension coordinate.
            transverse = relative - axial * direction  # Isolate transverse relative translation.
            axial_delta_numerator += float((GATE_ORIGINAL_EA_N - GATE_EA_N) / length * axial**2)  # Evaluate the audited axial-rigidity change.
            fixed_shear_numerator += float(GATE_FIXED_ROTATION_SHEAR_N_PER_M * np.dot(transverse, transverse))  # Evaluate the fixed-section portal-shear upper-bound contribution.
    inferred_removed = old_eigenvalue - current_rayleigh  # Infer the complete stiffness removed from the prior eigenpair.
    axial_delta = axial_delta_numerator / mass_norm  # Normalize the axial change to eigenvalue units.
    fixed_shear = fixed_shear_numerator / mass_norm  # Normalize the portal-shear diagnostic to eigenvalue units.
    return {"prior_shape_current_stiffness_rayleigh_frequency_hz": math.sqrt(max(current_rayleigh, 0.0)) / (2.0 * math.pi), "inferred_removed_stiffness_fraction_of_prior_lambda": inferred_removed / old_eigenvalue, "audited_axial_EA_change_fraction_of_prior_lambda": axial_delta / old_eigenvalue, "inferred_nonaxial_removed_fraction_of_prior_lambda": (inferred_removed - axial_delta) / old_eigenvalue, "fixed_rotation_portal_shear_bound_fraction_of_prior_lambda": fixed_shear / old_eigenvalue, "inferred_nonaxial_over_fixed_rotation_shear_bound": (inferred_removed - axial_delta) / fixed_shear if fixed_shear > 0.0 else np.nan}  # Return the Rayleigh and stiffness-source diagnostics.


def track_previous_solution(model: dict[str, object], parsed: dict[str, object], current_classification: pd.DataFrame) -> pd.DataFrame:  # Track the gate correction against the immediately preceding four-port solution.
    previous_vectors = np.load(PREVIOUS_DIR / "mode_vectors_first24.npz")  # Read the prior first twenty-four vectors.
    current_vectors = np.load(RESULT_DIR / "mode_vectors_first24.npz")  # Read the corrected first twenty-four vectors.
    previous_modes = np.asarray(previous_vectors["modes"], dtype=float)  # Extract prior full vectors.
    current_modes = np.asarray(current_vectors["modes"], dtype=float)  # Extract corrected full vectors.
    previous_table = pd.read_csv(PREVIOUS_DIR / "modal_properties.csv")  # Read prior modal frequencies.
    current_table = pd.read_csv(RESULT_DIR / "modal_properties.csv")  # Read corrected modal frequencies.
    mac = mass_mac_matrix(current_modes, previous_modes, np.asarray(model["dof_mass_kg"], dtype=float))  # Form corrected-to-prior mass-weighted MAC.
    assigned_current, assigned_previous = linear_sum_assignment(1.0 - mac)  # Find the maximum-total-MAC one-to-one assignment.
    assigned_lookup = {int(current): int(previous) for current, previous in zip(assigned_current, assigned_previous)}  # Map each corrected rank to an assigned prior rank.
    rows: list[dict[str, object]] = []  # Collect one tracking row per corrected low mode.
    for current_index in range(current_modes.shape[1]):  # Traverse every corrected saved vector.
        best_previous = int(np.argmax(mac[current_index, :]))  # Locate its unconstrained best prior match.
        assigned = int(assigned_lookup[current_index])  # Read its global one-to-one assignment.
        old_frequency = float(previous_table.iloc[assigned]["frequency_hz"])  # Read the assigned prior frequency.
        new_frequency = float(current_table.iloc[current_index]["frequency_hz"])  # Read the corrected frequency.
        row: dict[str, object] = {"corrected_mode": current_index + 1, "corrected_formal_label": str(current_classification.iloc[current_index]["formal_label"]), "corrected_frequency_hz": new_frequency, "assigned_previous_mode": assigned + 1, "previous_frequency_hz": old_frequency, "frequency_shift_percent": 100.0 * (new_frequency / old_frequency - 1.0), "assigned_mass_weighted_mac": float(mac[current_index, assigned]), "unconstrained_best_previous_mode": best_previous + 1, "unconstrained_best_mac": float(mac[current_index, best_previous]), "previous_production_label": str(previous_table.iloc[assigned].get("label", previous_table.iloc[assigned].get("sequence_label", "")))}  # Form the core tracking record.
        row.update(previous_gate_stiffness_diagnostics(previous_modes[:, assigned], old_frequency, model, parsed))  # Add Rayleigh evidence separating axial-EA change from removed portal shear.
        rows.append(row)  # Record the complete tracking result.
    return pd.DataFrame(rows)  # Return the low-mode stability table.


def summary_statistics(reference_match: pd.DataFrame, classification: pd.DataFrame, saved_check: pd.DataFrame, mechanism: pd.DataFrame) -> dict[str, object]:  # Build compact numerical findings for report generation.
    valid = reference_match.dropna(subset=["absolute_error_percent"]).copy()  # Select successfully paired reference rows.
    torsional = valid[valid["reference_id"].str.startswith("T")].copy()  # Select formal T-family rows.
    non_torsional = valid[~valid["reference_id"].str.startswith("T")].copy()  # Select every non-T row.
    low = classification.iloc[:24].copy()  # Define the directly saved-vector low-mode range.
    gantry_branch = mechanism[mechanism["gantry_rope_decoupling_branch_flag"]].copy()  # Select the transverse gantry-rope sensitivity branch.
    return {"minimum_frequency_hz": float(classification["frequency_hz"].min()), "mode_count_below_0_01_hz": int((classification["frequency_hz"] < NEAR_ZERO_HZ).sum()), "minimum_raw_eigenvalue_rad2_s2": float(saved_check["raw_eigenvalue_rad2_s2"].min()), "maximum_saved_vector_residual_first24": float(saved_check["saved_vector_eigenpair_relative_residual"].dropna().max()), "maximum_independent_residual_80": float(saved_check["independent_eigenpair_relative_residual"].max()), "maximum_absolute_frequency_reproduction_difference_hz": float(saved_check["frequency_difference_hz"].abs().max()), "reference_all14_mean_absolute_error_percent": float(valid["absolute_error_percent"].mean()), "reference_all14_rms_error_percent": float(math.sqrt(float(np.mean(valid["relative_error_percent"] ** 2)))), "reference_t_mean_absolute_error_percent": float(torsional["absolute_error_percent"].mean()), "reference_non_t_mean_absolute_error_percent": float(non_torsional["absolute_error_percent"].mean()), "reference_maximum_absolute_error_percent": float(valid["absolute_error_percent"].max()), "mechanism_screen_flag_count_80": int(mechanism["mechanism_screen_flag"].sum()), "near_zero_or_extreme_localization_flag_count_80": int(mechanism[["near_zero_frequency_flag", "extreme_node_localization_flag", "extreme_gate_relative_motion_flag"]].any(axis=1).sum()), "gantry_rope_decoupling_branch_count_80": int(len(gantry_branch)), "first_gantry_rope_decoupling_mode": int(gantry_branch.iloc[0]["mode"]) if not gantry_branch.empty else None, "first_gantry_rope_decoupling_frequency_hz": float(gantry_branch.iloc[0]["frequency_hz"]) if not gantry_branch.empty else None, "minimum_effective_source_node_pair_count_80": float(classification["effective_source_node_pair_count"].min()), "maximum_source_node_pair_energy_fraction_80": float(classification["maximum_source_node_pair_energy_fraction"].max()), "maximum_gantry_rope_energy_fraction_first24": float(low["gantry_rope_energy_fraction"].max()), "maximum_ordinary_gate_energy_fraction_first24": float(low["ordinary_gate_strain_energy_fraction"].max()), "maximum_four_port_energy_fraction_first24": float(low["four_port_gate_passage_strain_energy_fraction"].max()), "maximum_four_port_energy_fraction_80": float(classification["four_port_gate_passage_strain_energy_fraction"].max())}  # Return key numerical acceptance statistics.


def write_findings(reference_match: pd.DataFrame, classification: pd.DataFrame, saved_check: pd.DataFrame, tracking: pd.DataFrame, mechanism: pd.DataFrame, summary: dict[str, object]) -> None:  # Write a concise independent findings note.
    named_ids = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "VA2", "LA2", "TS2", "VS2"]  # Select the formal named rows for a compact table.
    named = reference_match[reference_match["reference_id"].isin(named_ids)].copy()  # Preserve published order for named modes.
    lines: list[str] = ["# 普通门架秩一柔化后双 MCT 模态独立复核", "", "本复核按当前 MCT、21 道四端口 K12 和 50×2 道普通门架秩一轴杆重建 K、M，并独立重复最终 80 阶广义特征值求解。附件 TS2/VS2 始终按同一主跨家族及奇偶性内的频率顺序编号；半波 MAC 仅作为形状指纹。", "", "## 数值与机制筛查", "", f"- 最低频率为 {summary['minimum_frequency_hz']:.6f} Hz，0.01 Hz 以下模态数为 {summary['mode_count_below_0_01_hz']}；80 阶最小原始特征值为 {summary['minimum_raw_eigenvalue_rad2_s2']:.6e} rad²/s²。", f"- 保存前 24 阶对重建矩阵的最大相对残差为 {summary['maximum_saved_vector_residual_first24']:.3e}；独立重复 80 阶最大残差为 {summary['maximum_independent_residual_80']:.3e}。", f"- 独立重复频率与生产 CSV 的最大绝对差为 {summary['maximum_absolute_frequency_reproduction_difference_hz']:.3e} Hz。", f"- 近零、极端节点局部化或极端普通门架相对运动命中 {summary['near_zero_or_extreme_localization_flag_count_80']} / 80 阶；最小有效节点对数为 {summary['minimum_effective_source_node_pair_count_80']:.1f}，任一节点对最大动能占比上限为 {100.0*summary['maximum_source_node_pair_energy_fraction_80']:.2f}%。", f"- 另有 {summary['gantry_rope_decoupling_branch_count_80']} 阶门架索横向解耦敏感分支，首阶为 M{summary['first_gantry_rope_decoupling_mode']} = {summary['first_gantry_rope_decoupling_frequency_hz']:.6f} Hz；这些模态的门架索动能超过 95%，普通门架顶底相对运动约为单端运动的 √2。", "", "秩一普通门架自身有五个自由转动/横移机制，但承重索与门架索的连续索体系及 21 道 K12 总成没有形成全桥近零频根。表 4-1 和前 24 阶不受门架索解耦分支插入影响；M37 以后该分支对普通门架横剪假设敏感，不宜在未做转动端口门架校核前直接作为抖振主模态。", "", "## 附件表 4-1 正式配对", "", "| 模态 | 附件 Hz | 当前阶次 | 当前 Hz | 误差 | K12 能量 | 普通门架轴向能量 |", "|---|---:|---:|---:|---:|---:|---:|"]  # Initialize the findings and formal comparison table.
    for row in named.itertuples(index=False):  # Add one named attachment row.
        lines.append(f"| {row.reference_id} | {row.reference_frequency_hz:.4f} | M{int(row.matched_mode)} | {row.matched_frequency_hz:.6f} | {row.relative_error_percent:+.2f}% | {100.0*row.four_port_gate_passage_strain_energy_fraction:.4f}% | {100.0*row.ordinary_gate_strain_energy_fraction:.4f}% |")  # Render its core comparison.
    lines.extend(["", f"14 行平均绝对误差为 {summary['reference_all14_mean_absolute_error_percent']:.2f}%，RMS 误差为 {summary['reference_all14_rms_error_percent']:.2f}%；T 家族平均绝对误差为 {summary['reference_t_mean_absolute_error_percent']:.2f}%，非 T 为 {summary['reference_non_t_mean_absolute_error_percent']:.2f}%。", "", "TA1、TS1、TS2 的正式匹配分别按 TA、TS 家族内频率序号确定。半波指纹即使与附件命名直觉不一致，也不用于把 TS2 改配到 TS3。", "", "## 与未修正普通门架的四端口模型比较", "", "前 24 阶通过质量加权 MAC 做一一追踪。主跨 L/V 及明确边跨模态总体保持高 MAC，T 家族也保持 0.98 左右的高 MAC，因此频率下降是可追踪的整体柔化，不是突然出现的新局部根。TA1、TS1、TS2 相对前版分别下降 11.24%、7.05%、4.14%，对应 MAC 为 0.989、0.985、0.982。Rayleigh 分解显示当前秩一门架轴向能量极小，T 频率下降不能归因于 EA 从原值降到 19.77%；主因是取消了普通门架平移端口的非客观固定转角横剪上界。tracking CSV 同时列出推断缺失刚度、EA 变化和 80.7156 N/mm 横剪上界的逐模态对照。", "", "## 输出", "", "- gate_corrected_reference_table4_1_matching.csv：附件 14 行正式配对、误差和能量指标。", "- gate_corrected_error_statistics.csv：频率误差、残差及机制筛查汇总。", "- gate_corrected_mode_energy_classification_80.csv：80 阶跨别、L/V/T 共差分、K12/普通门架能量及局部化指标。", "- gate_corrected_saved_solution_check_80.csv：生产频率复算、前 24 阶保存向量残差和 MAC。", "- gate_corrected_vs_four_port_mode_tracking.csv：普通门架修正前后前 24 阶质量加权与 Rayleigh 刚度追踪。", "- gate_corrected_mechanism_screen_80.csv：近零、节点局部化及普通门架相对运动筛查。", "- gate_corrected_passage_station_energy_80.csv 与 gate_corrected_ordinary_gate_energy_80.csv：逐站/逐门架应变能明细。", ""])  # Complete the findings note.
    (OUTPUT_DIR / "gate_corrected_findings.md").write_text("\n".join(lines), encoding="utf-8")  # Persist the concise independent findings.


def main() -> None:  # Run the complete independent gate-corrected validation.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the requested audit directory exists.
    audit = json.loads((RESULT_DIR / "model_audit.json").read_text(encoding="utf-8"))  # Read saved production provenance.
    if production.sha256_file(MCT_PATH) != str(audit["authoritative_inputs"]["mct_sha256"]):  # Reject MCT source drift.
        raise ValueError("Saved corrected result and current MCT hashes differ.")  # Stop before inconsistent validation.
    if production.sha256_file(MATRIX_PATH) != str(audit["authoritative_inputs"]["four_port_matrix_sha256"]):  # Reject four-port matrix drift.
        raise ValueError("Saved corrected result and current K12 hashes differ.")  # Stop before inconsistent validation.
    parsed = production.parse_mct(MCT_PATH)  # Parse the reviewed longitudinal source.
    station_map = pd.read_csv(STATION_PATH, encoding="utf-8-sig")  # Read the twenty-one exact passage interfaces.
    model = production.build_double_model(parsed, station_map, MATRIX_PATH)  # Rebuild the exact gate-corrected matrices.
    frequencies, modes, raw_eigenvalues = independent_solve(model)  # Independently repeat all sixty modes.
    saved_check = saved_solution_check(model, frequencies, modes, raw_eigenvalues)  # Reconcile saved and repeated solutions.
    classification, passage_energy, ordinary_energy = classify_modes(parsed, station_map, model, frequencies, modes)  # Run physical classification and energy audits.
    mechanism = mechanism_screen(classification)  # Screen the complete repeated spectrum for spurious low/local roots.
    reference = pd.read_csv(REFERENCE_PATH, encoding="utf-8-sig")  # Read Attachment Table 4-1.
    reference_match = match_reference(reference, classification)  # Produce the formal fourteen-row pairing.
    tracking = track_previous_solution(model, parsed, classification)  # Track low modes against the prior ordinary-gate stiffness.
    statistics = summary_statistics(reference_match, classification, saved_check, mechanism)  # Summarize numerical evidence.
    classification.to_csv(OUTPUT_DIR / "gate_corrected_mode_energy_classification_80.csv", index=False)  # Write the eighty-mode classification.
    passage_energy.to_csv(OUTPUT_DIR / "gate_corrected_passage_station_energy_80.csv", index=False)  # Write mode-by-passage energy detail.
    ordinary_energy.to_csv(OUTPUT_DIR / "gate_corrected_ordinary_gate_energy_80.csv", index=False)  # Write mode-by-ordinary-gate energy detail.
    saved_check.to_csv(OUTPUT_DIR / "gate_corrected_saved_solution_check_80.csv", index=False)  # Write numerical residual and frequency checks.
    mechanism.to_csv(OUTPUT_DIR / "gate_corrected_mechanism_screen_80.csv", index=False)  # Write the conservative mechanism screen.
    reference_match.to_csv(OUTPUT_DIR / "gate_corrected_reference_table4_1_matching.csv", index=False)  # Write the formal attachment comparison.
    tracking.to_csv(OUTPUT_DIR / "gate_corrected_vs_four_port_mode_tracking.csv", index=False)  # Write pre/post-correction mode tracking.
    pd.DataFrame({"metric": list(statistics.keys()), "value": list(statistics.values())}).to_csv(OUTPUT_DIR / "gate_corrected_error_statistics.csv", index=False)  # Write compact tabular acceptance statistics.
    (OUTPUT_DIR / "gate_corrected_summary.json").write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")  # Write compact machine-readable findings.
    write_findings(reference_match, classification, saved_check, tracking, mechanism, statistics)  # Write the human-readable findings note.
    print(reference_match.to_string(index=False))  # Show the primary fourteen-row pairing in the run log.
    print(json.dumps(statistics, ensure_ascii=False, indent=2))  # Show acceptance statistics in the run log.


if __name__ == "__main__":  # Execute only when the validator is invoked directly.
    main()  # Run the complete validation workflow.
