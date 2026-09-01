from __future__ import annotations  # Enable stable modern type annotations.
import csv  # Write auditable no-passage modal tables.
import json  # Write deterministic calculation receipts.
import math  # Evaluate weighted modal metrics and normalization formulas.
import os  # Record the exact GitHub source revision.
import sys  # Add the existing isolated solver directories to the import path.
from pathlib import Path  # Resolve repository and result paths safely.
import numpy as np  # Assemble modal fields and evaluate physical branch measures.

HERE = Path(__file__).resolve().parent  # Locate the verified inverse-form-finding directory.
CATWALK_FEM = HERE.parent  # Locate the common catwalk finite-element directory.
CLEAN_DIR = CATWALK_FEM / "clean-theory-14modes"  # Locate the accepted matrix and eigensolver implementation.
sys.path.insert(0, str(HERE))  # Make the verified inverse solver modules importable.
sys.path.insert(0, str(CLEAN_DIR))  # Make the existing dynamic solver modules importable.
import solve_modal_from_inverse as previous  # type: ignore  # Reuse the verified inverse axial-force reconstruction.
import solve_modal_branch_clean as metrics  # type: ignore  # Reuse weighted modal metric helpers only.
import solve as base  # type: ignore  # Reuse formed geometry, matrix assembly, and generalized eigensolution.
import solve_v2 as v2  # type: ignore  # Reuse the mass-consistent complete dynamic assembly.
import solve_v4_drawing_corrected as v4  # type: ignore  # Reuse independently documented geometry corrections.

OUT = HERE / "modal_results_no_passage"  # Isolate this ablation from every previous result directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated result directory idempotently.
base.OUT = OUT  # Redirect any reused base output into the isolated result directory.
v2.OUT = OUT  # Redirect any reused mass-audit output into the isolated result directory.
v4.OUT = OUT  # Redirect any reused drawing-corrected output into the isolated result directory.
LABEL_ORDER = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]  # Preserve the required fourteen-label reporting order.
MAIN_FRACTION_MIN = 0.45  # Require a main-span branch to carry at least forty-five percent of its selected modal measure in the main span.
SIDE_FRACTION_MIN = 0.45  # Require a side-span branch to localize at least forty-five percent of its selected modal measure in the declared side span.
ACOUSTIC_COHERENCE_MIN = 0.25  # Require floor and gantry systems to move as one acoustic global branch.
FLOOR_PARTICIPATION_MIN = 0.20  # Exclude branches whose selected displacement is almost entirely confined to the gantry-rope system.
LOCALIZATION_MAX = 0.20  # Exclude modes concentrated at one longitudinal station.


def zero_passage_matrices(beta_deg: float) -> tuple[np.ndarray, np.ndarray, dict]:  # Replace each transverse passage by an exact zero stiffness and zero mass contribution.
    return np.zeros((8, 8), dtype=float), np.zeros((8, 8), dtype=float), {"beta_deg": float(beta_deg), "removed": True, "stiffness_zero": True, "mass_zero": True}  # Return zero matrices while preserving station metadata.


def collect_catwalk_dofs(system: dict, catwalk: int, floor_nodes: list[int], top_nodes: list[int]) -> np.ndarray:  # Collect every generalized degree belonging to one physical catwalk.
    values: list[int] = []  # Initialize the catwalk degree list.
    for node_id in floor_nodes:  # Traverse all floor-chain section nodes.
        values.extend(int(value) for value in system["floor_dofs"][(catwalk, int(node_id))])  # Add the floor section degrees.
    for node_id in top_nodes:  # Traverse all gantry-chain section nodes.
        values.extend(int(value) for value in system["top_dofs"][(catwalk, int(node_id))])  # Add the gantry section degrees.
    return np.array(sorted(set(values)), dtype=int)  # Return the unique ordered generalized degree set.


def cross_block_relative_norm(matrix, left: np.ndarray, right: np.ndarray) -> float:  # Measure residual coupling between the two catwalk blocks.
    cross = matrix[left][:, right]  # Extract the off-diagonal catwalk coupling block.
    numerator = float(np.linalg.norm(cross.data))  # Evaluate its sparse coefficient norm.
    denominator = max(float(np.linalg.norm(matrix.data)), 1.0e-30)  # Evaluate a stable full-matrix norm scale.
    return numerator / denominator  # Return the normalized inter-catwalk coupling measure.


def classify_single_catwalk(model: dict, system: dict, floor_nodes: list[int], top_nodes: list[int], free_positions: np.ndarray, frequencies: np.ndarray, vectors: np.ndarray, residuals: list[float]) -> tuple[list[dict], dict[int, dict]]:  # Classify the independent one-catwalk eigenbranches.
    floor_x = np.array([base.xyz(model, int(node_id))[0] for node_id in floor_nodes], dtype=float)  # Read ordered floor-chain longitudinal coordinates.
    floor_weights = metrics.tributary(floor_x)  # Build longitudinal integration weights.
    floor_index = {int(node_id): index for index, node_id in enumerate(floor_nodes)}  # Map floor nodes to ordered field indices.
    top_index = {int(node_id): index for index, node_id in enumerate(top_nodes)}  # Map gantry nodes to ordered field indices.
    span_groups = {"north": "北边跨", "main": "主跨", "south717": "南边跨", "south503": "南辅跨"}  # Declare the four physical MCT span groups.
    span_masks = {key: np.array([int(node_id) in {int(value) for value in model["groups"][group_name]["nodes"]} for node_id in floor_nodes], dtype=bool) for key, group_name in span_groups.items()}  # Build one ordered floor-node mask per physical span.
    main_mask = span_masks["main"]  # Select the main-span mask.
    main_x = floor_x[main_mask]  # Extract main-span longitudinal coordinates.
    main_weights = floor_weights[main_mask]  # Extract main-span integration weights.
    main_midpoint = 0.5 * (float(np.min(main_x)) + float(np.max(main_x)))  # Evaluate the physical main-span midpoint.
    main_floor_nodes = {int(node_id) for node_id in model["groups"]["主跨"]["nodes"]}  # Build main-span floor-node membership.
    portal_pairs = sorted([(int(record["floor_node"]), int(record["top_node"])) for record in system["portals"] if int(record["floor_node"]) in main_floor_nodes], key=lambda pair: base.xyz(model, pair[0])[0])  # Retain and order all main-span portal pairs.
    portal_x = np.array([base.xyz(model, floor_node)[0] for floor_node, _top_node in portal_pairs], dtype=float)  # Read portal longitudinal coordinates.
    portal_weights = metrics.tributary(portal_x)  # Build portal integration weights.
    floor_roll_radius = math.sqrt(float(np.mean(np.asarray(base.FLOOR_Y, dtype=float) ** 2)))  # Convert floor roll to an equivalent rope-point displacement.
    top_roll_radius = math.sqrt(float(np.mean(np.asarray(base.GANTRY_Y, dtype=float) ** 2)))  # Convert gantry roll to an equivalent rope-point displacement.
    free_global = np.asarray(system["free"], dtype=int)[free_positions]  # Map one-catwalk constrained coordinates back to full generalized degree numbers.
    raw: list[dict] = []  # Initialize the complete one-catwalk modal record list.
    shapes: dict[int, dict] = {}  # Initialize stored modal fields for audit.
    for mode_index, frequency in enumerate(frequencies):  # Traverse every solved one-catwalk eigenmode.
        full = np.zeros(system["dof_count"], dtype=float)  # Allocate the complete generalized vector.
        full[free_global] = vectors[:, mode_index]  # Restore the one-catwalk eigenvector to its physical generalized degrees.
        floor_values = np.array([full[system["floor_dofs"][(0, int(node_id))]] for node_id in floor_nodes], dtype=float)  # Read all floor-section degrees for the retained catwalk.
        top_values = np.array([full[system["top_dofs"][(0, int(node_id))]] for node_id in top_nodes], dtype=float)  # Read all gantry-section degrees for the retained catwalk.
        fields = {"L": floor_values[:, 1], "V": floor_values[:, 2], "R": floor_roll_radius * floor_values[:, 3]}  # Form lateral, vertical, and local-roll displacement fields.
        measures = {family: metrics.weighted_inner(field, field, floor_weights) for family, field in fields.items()}  # Evaluate the three floor-system modal measures.
        family = max(measures, key=measures.get)  # Select the physically dominant single-catwalk family.
        selected_field = fields[family]  # Read the dominant physical field.
        total_measure = max(metrics.weighted_inner(selected_field, selected_field, floor_weights), 1.0e-30)  # Form a stable selected-field measure.
        span_fraction = {key: metrics.weighted_inner(selected_field[mask], selected_field[mask], floor_weights[mask]) / total_measure for key, mask in span_masks.items()}  # Evaluate selected-field localization in every physical span.
        main_field = selected_field[main_mask]  # Extract the selected main-span shape.
        reflected = np.interp(2.0 * main_midpoint - main_x, main_x, main_field)  # Reflect the main-span shape about its physical midpoint.
        parity = metrics.weighted_correlation(main_field, reflected, main_weights)  # Evaluate signed midpoint-reflection parity.
        parity_label = "S" if parity >= 0.0 else "A"  # Assign symmetric or antisymmetric parity from the computed shape.
        harmonic_order, harmonic_score = metrics.harmonic_descriptor(main_field, main_x, main_weights)  # Describe the strongest sine projection without using it for selection.
        zero_crossings = metrics.zero_crossing_count(main_field)  # Count robust interior sign changes.
        floor_portal_field: list[float] = []  # Initialize floor displacement at main-span portal stations.
        top_portal_field: list[float] = []  # Initialize gantry displacement at main-span portal stations.
        component = 1 if family == "L" else 2 if family == "V" else 3  # Select the matching generalized component.
        floor_scale = 1.0 if family in {"L", "V"} else floor_roll_radius  # Define the floor conversion scale.
        top_scale = 1.0 if family in {"L", "V"} else top_roll_radius  # Define the gantry conversion scale.
        for floor_node, top_node in portal_pairs:  # Traverse every main-span portal pair.
            floor_portal_field.append(float(floor_scale * floor_values[floor_index[floor_node], component]))  # Store the floor selected displacement.
            top_portal_field.append(float(top_scale * top_values[top_index[top_node], component]))  # Store the gantry selected displacement.
        floor_portal_array = np.asarray(floor_portal_field, dtype=float)  # Convert the floor portal field to an array.
        top_portal_array = np.asarray(top_portal_field, dtype=float)  # Convert the gantry portal field to an array.
        acoustic_coherence = metrics.weighted_coherence(floor_portal_array, top_portal_array, portal_weights)  # Measure same-shape and same-amplitude floor-gantry motion.
        floor_top_correlation = metrics.weighted_correlation(floor_portal_array, top_portal_array, portal_weights)  # Measure signed floor-gantry shape correlation.
        floor_measure = metrics.weighted_inner(floor_portal_array, floor_portal_array, portal_weights)  # Evaluate floor modal measure at portal stations.
        top_measure = metrics.weighted_inner(top_portal_array, top_portal_array, portal_weights)  # Evaluate gantry modal measure at portal stations.
        floor_participation = floor_measure / max(floor_measure + top_measure, 1.0e-30)  # Quantify floor participation in the acoustic branch.
        nodal_measure = floor_weights * selected_field**2  # Form the longitudinal selected-field density.
        localization = float(np.max(nodal_measure) / max(np.sum(nodal_measure), 1.0e-30))  # Detect concentration at one longitudinal station.
        family_total = max(sum(measures.values()), 1.0e-30)  # Form the total single-catwalk family measure.
        record = {"single_catwalk_mode": int(mode_index + 1), "frequency_hz": float(frequency), "eigen_residual": float(residuals[mode_index]), "family": family, "family_fraction_L": float(measures["L"] / family_total), "family_fraction_V": float(measures["V"] / family_total), "family_fraction_R": float(measures["R"] / family_total), "parity": float(parity), "parity_label": parity_label, "harmonic_order_descriptor": int(harmonic_order), "harmonic_score": float(harmonic_score), "interior_zero_crossings": int(zero_crossings), "floor_gantry_acoustic_coherence": float(acoustic_coherence), "floor_gantry_shape_correlation": float(floor_top_correlation), "floor_participation": float(floor_participation), "localization": float(localization), "north_fraction": float(span_fraction["north"]), "main_fraction": float(span_fraction["main"]), "south717_fraction": float(span_fraction["south717"]), "south503_fraction": float(span_fraction["south503"])}  # Store the complete target-free single-catwalk branch record.
        raw.append(record)  # Append the current modal record.
        shapes[int(mode_index + 1)] = {"x_m": floor_x.tolist(), "selected_field": selected_field.tolist(), "main_field": main_field.tolist(), "family": family}  # Preserve the selected physical field for audit.
    return raw, shapes  # Return every one-catwalk branch record and its modal field.


def select_single_catwalk_branches(raw: list[dict]) -> dict[str, dict]:  # Select global branch families before forming the exact two-catwalk degenerate combinations.
    selected: dict[str, dict] = {}  # Initialize the selected branch table.
    used_side: set[int] = set()  # Prevent one single-catwalk mode from receiving two side-span labels.
    side_definitions = [("SIDE1", "south717_fraction"), ("SIDE2", "north_fraction"), ("SIDE3", "south503_fraction")]  # Map each SIDE label to its declared physical span.
    for label, fraction_key in side_definitions:  # Traverse all three side-span families.
        candidates = [record for record in raw if record["single_catwalk_mode"] not in used_side and record["family"] in {"L", "V"} and record[fraction_key] >= SIDE_FRACTION_MIN and record["localization"] <= LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Apply only global translational family, span, localization, and frequency-band conditions.
        if candidates:  # Test whether a global side-span branch exists.
            choice = min(candidates, key=lambda record: (record["frequency_hz"], -record[fraction_key]))  # Select the lowest global branch localized in the declared side span.
            selected[label] = {**choice, "selection_rule": f"lowest one-catwalk translational branch with {fraction_key}>={SIDE_FRACTION_MIN:.2f}; full two-catwalk system contains an exact degenerate pair"}  # Store the selected side branch.
            used_side.add(int(choice["single_catwalk_mode"]))  # Mark the selected side branch as consumed.
        else:  # Handle an absent side branch honestly.
            selected[label] = {"status": "unidentified", "selection_rule": f"no translational branch with {fraction_key}>={SIDE_FRACTION_MIN:.2f}"}  # Preserve an explicit unidentified state.
    main_candidates = [record for record in raw if record["family"] in {"L", "V"} and record["main_fraction"] >= MAIN_FRACTION_MIN and record["floor_gantry_acoustic_coherence"] >= ACOUSTIC_COHERENCE_MIN and record["floor_participation"] >= FLOOR_PARTICIPATION_MIN and record["localization"] <= LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Freeze the acoustic main-span translational branch set.
    groups = {("L", "S"): [("LS1", 1), ("LS2", 2)], ("L", "A"): [("LA1", 1), ("LA2", 2)], ("V", "S"): [("VS1", 1), ("VS2", 2)], ("V", "A"): [("VA1", 1), ("VA2", 2)]}  # Define each single-catwalk family by displacement family, midpoint parity, and ascending rank.
    for (family, parity_label), labels in groups.items():  # Traverse every disjoint physical family-parity group.
        candidates = sorted([record for record in main_candidates if record["family"] == family and record["parity_label"] == parity_label], key=lambda record: record["frequency_hz"])  # Sort the immutable physical candidate set by computed frequency.
        for label, rank in labels:  # Assign every requested branch rank.
            if len(candidates) >= rank:  # Test whether the requested physical rank exists.
                choice = candidates[rank - 1]  # Select the requested branch.
                selected[label] = {**choice, "selection_rule": f"rank {rank} among acoustic one-catwalk main-span {family}-{parity_label} branches; full system has common and differential degenerate combinations"}  # Store the selected single-catwalk branch.
            else:  # Handle a missing physical rank honestly.
                selected[label] = {"status": "unidentified", "selection_rule": f"fewer than {rank} acoustic one-catwalk main-span {family}-{parity_label} branches"}  # Preserve an explicit unidentified state.
    for torsion_label, vertical_label in (("TA1", "VA1"), ("TS1", "VS1"), ("TS2", "VS2")):  # Form the exact differential-vertical counterparts of the vertical common branches.
        vertical = selected.get(vertical_label, {})  # Read the corresponding one-catwalk vertical branch.
        if "frequency_hz" in vertical:  # Test whether the source vertical branch was identified.
            selected[torsion_label] = {**vertical, "family": "T", "degenerate_with": vertical_label, "selection_rule": f"exact differential-vertical combination of the same no-passage single-catwalk branch as {vertical_label}; frequency degeneracy follows from block-diagonal identical catwalk matrices"}  # Store the no-passage torsional counterpart.
        else:  # Handle an unidentified source vertical branch.
            selected[torsion_label] = {"status": "unidentified", "selection_rule": f"source branch {vertical_label} unidentified"}  # Preserve an explicit unidentified state.
    return selected  # Return the complete fourteen-family no-passage assignment.


def write_outputs(raw: list[dict], selected: dict[str, dict], shapes: dict[int, dict], summary: dict) -> None:  # Write the complete no-passage calculation evidence.
    with (OUT / "raw_single_catwalk_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the complete one-catwalk modal table.
        writer = csv.DictWriter(handle, fieldnames=list(raw[0].keys()))  # Create a named-column CSV writer.
        writer.writeheader()  # Write the raw table header.
        writer.writerows(raw)  # Write every computed one-catwalk branch record.
    with (OUT / "classified_14_modes_no_passage.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the no-passage fourteen-family table.
        fields = ["label", "status", "single_catwalk_mode", "frequency_hz", "family", "degenerate_with", "parity_label", "harmonic_order_descriptor", "interior_zero_crossings", "main_fraction", "north_fraction", "south717_fraction", "south503_fraction", "floor_gantry_acoustic_coherence", "eigen_residual", "selection_rule"]  # Define the selected table columns.
        writer = csv.DictWriter(handle, fieldnames=fields)  # Create the selected-table writer.
        writer.writeheader()  # Write the selected-table header.
        for label in LABEL_ORDER:  # Preserve the required fourteen-label reporting order.
            record = selected.get(label, {"status": "unidentified"})  # Read the current assignment or an explicit missing state.
            writer.writerow({"label": label, "status": record.get("status", "identified"), "single_catwalk_mode": record.get("single_catwalk_mode"), "frequency_hz": record.get("frequency_hz"), "family": record.get("family"), "degenerate_with": record.get("degenerate_with"), "parity_label": record.get("parity_label"), "harmonic_order_descriptor": record.get("harmonic_order_descriptor"), "interior_zero_crossings": record.get("interior_zero_crossings"), "main_fraction": record.get("main_fraction"), "north_fraction": record.get("north_fraction"), "south717_fraction": record.get("south717_fraction"), "south503_fraction": record.get("south503_fraction"), "floor_gantry_acoustic_coherence": record.get("floor_gantry_acoustic_coherence"), "eigen_residual": record.get("eigen_residual"), "selection_rule": record.get("selection_rule")})  # Write the current no-passage branch record.
    (OUT / "selected_mode_shapes_no_passage.json").write_text(json.dumps({label: shapes.get(int(record["single_catwalk_mode"])) for label, record in selected.items() if "single_catwalk_mode" in record}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Preserve selected one-catwalk modal fields.
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the concise no-passage receipt.


def main() -> int:  # Execute the complete no-transverse-passage dynamic ablation.
    v4.apply_drawing_corrections()  # Apply only independently documented geometry corrections before assembly.
    base.passage_matrices = zero_passage_matrices  # Remove all twenty-one transverse-passage stiffness and mass matrices exactly.
    model = base.load_mct()  # Parse and hash-check the sole MCT geometry, topology, support, and load source.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-chain topology.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope topology.
    static = previous.recover_static_state(model)  # Recompute the verified full-system MCT-geometry prestress state before dynamic ablation.
    if not bool(static["success"]):  # Reject inverse-solver failure before dynamic assembly.
        raise RuntimeError(str(static["message"]))  # Report the exact inverse-solver failure.
    if int(static["nullity"]) != 0:  # Require a unique aggregate force state.
        raise RuntimeError(f"Inverse equilibrium nullity is {static['nullity']}")  # Reject an unresolved self-stress branch.
    if float(static["min_cable_force_kN"]) <= 0.0:  # Require every cable member to remain in tension.
        raise RuntimeError(f"Minimum recovered cable force is {static['min_cable_force_kN']:.6f} kN")  # Reject cable compression before geometric-stiffness assembly.
    if float(static["max_abs_force_error_percent"]) > 0.5:  # Preserve the declared elementwise initial-force agreement threshold.
        raise RuntimeError(f"Maximum MCT initial-force mismatch is {static['max_abs_force_error_percent']:.6f}%")  # Reject a prestress state that no longer matches the verified MCT force field.
    system = v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble all ropes, portals, supports, and masses with every transverse-passage matrix removed.
    catwalk_zero_dofs = collect_catwalk_dofs(system, 0, floor_nodes, top_nodes)  # Collect the upstream catwalk generalized degrees.
    catwalk_one_dofs = collect_catwalk_dofs(system, 1, floor_nodes, top_nodes)  # Collect the downstream catwalk generalized degrees.
    free = np.asarray(system["free"], dtype=int)  # Read the constrained full-system free-degree map.
    positions_zero = np.array([index for index, degree in enumerate(free) if int(degree) in set(catwalk_zero_dofs.tolist())], dtype=int)  # Locate upstream catwalk coordinates in the constrained matrices.
    positions_one = np.array([index for index, degree in enumerate(free) if int(degree) in set(catwalk_one_dofs.tolist())], dtype=int)  # Locate downstream catwalk coordinates in the constrained matrices.
    if len(positions_zero) != len(positions_one):  # Verify identical free-degree counts in both nominally identical catwalks.
        raise RuntimeError(f"Catwalk free-DOF mismatch: {len(positions_zero)} versus {len(positions_one)}")  # Reject a non-identical block decomposition.
    if len(positions_zero) + len(positions_one) != len(free):  # Verify that every dynamic free degree belongs to exactly one catwalk.
        raise RuntimeError("Free degrees are not exhausted by the two catwalk blocks")  # Reject an unclassified shared degree.
    cross_k = cross_block_relative_norm(system["K"], positions_zero, positions_one)  # Measure residual inter-catwalk stiffness coupling.
    cross_m = cross_block_relative_norm(system["M"], positions_zero, positions_one)  # Measure residual inter-catwalk mass coupling.
    if cross_k > 1.0e-14 or cross_m > 1.0e-14:  # Require numerical block diagonality after passage removal.
        raise RuntimeError(f"Residual inter-catwalk coupling K={cross_k:.3e}, M={cross_m:.3e}")  # Reject incomplete passage removal.
    single_system = {"K": system["K"][positions_zero][:, positions_zero].tocsr(), "M": system["M"][positions_zero][:, positions_zero].tocsr()}  # Extract one exact physical catwalk block.
    frequencies, vectors, residuals, matrix_checks = base.solve_eigen(single_system)  # Solve and verify the independent one-catwalk spectrum.
    raw, shapes = classify_single_catwalk(model, system, floor_nodes, top_nodes, positions_zero, frequencies, vectors, residuals)  # Classify single-catwalk physical branches without target frequencies.
    selected = select_single_catwalk_branches(raw)  # Form the exact common and differential two-catwalk branch assignments from the block-diagonal spectrum.
    identified = {label: float(record["frequency_hz"]) for label, record in selected.items() if "frequency_hz" in record}  # Build the compact identified-frequency map.
    frozen = {"kind": "mct_inverse_prestress_no_transverse_passage_modal_ablation_v1", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "transverse_passage_stiffness_included": False, "transverse_passage_mass_included": False, "prestress_state": "verified full-system MCT inverse prestress frozen before dynamic passage ablation", "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False, "inter_catwalk_relative_coupling": {"K": cross_k, "M": cross_m}, "degeneracy_statement": "With no transverse-passage matrices the two nominal catwalk blocks are identical and uncoupled; every one-catwalk branch generates exact common and differential two-catwalk combinations at the same frequency.", "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "single_catwalk_matrix_checks": matrix_checks, "mass_audit": system["mass_audit_v2"], "first_40_single_catwalk_frequencies_hz": [float(value) for value in frequencies[:40]], "raw_single_catwalk_modes": raw, "classified_14": selected}  # Assemble the immutable target-free no-passage result.
    frozen_path = OUT / "frozen_results_no_passage.json"  # Define the immutable target-free result path.
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Freeze the complete no-passage result before any comparison.
    frozen_sha256 = base.sha(frozen_path)  # Compute the immutable result digest.
    summary = {"kind": "mct_inverse_prestress_no_transverse_passage_modal_summary_v1", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha256, "transverse_passage_stiffness_included": False, "transverse_passage_mass_included": False, "inter_catwalk_relative_coupling_K": cross_k, "inter_catwalk_relative_coupling_M": cross_m, "single_catwalk_free_dofs": int(len(positions_zero)), "identified_count": int(len(identified)), "identified_frequencies_hz": identified, "inverse_static": frozen["inverse_static"], "single_catwalk_matrix_checks": matrix_checks, "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False}  # Build the concise no-passage calculation receipt.
    write_outputs(raw, selected, shapes, summary)  # Write every primary target-free no-passage result file.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve every explicit rope force and recovered unstressed length.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every generated result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete no-passage summary into the workflow log.
    return 0  # Report successful no-passage ablation completion.


if __name__ == "__main__":  # Execute only when invoked as the main calculation program.
    raise SystemExit(main())  # Return the numerical status to the operating system.
