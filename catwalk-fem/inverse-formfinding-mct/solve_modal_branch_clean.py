from __future__ import annotations  # Enable stable type annotations throughout the recalculation.
import csv  # Write the complete raw and selected modal tables.
import json  # Write deterministic machine-readable calculation receipts.
import math  # Evaluate normalization and harmonic projection formulas.
import os  # Record the exact GitHub commit used by the numerical run.
import sys  # Add the existing isolated solver directories to the import path.
from pathlib import Path  # Resolve repository and result paths safely.
import numpy as np  # Assemble modal fields and evaluate weighted physical metrics.

HERE = Path(__file__).resolve().parent  # Locate the verified inverse-form-finding directory.
CATWALK_FEM = HERE.parent  # Locate the common catwalk finite-element directory.
CLEAN_DIR = CATWALK_FEM / "clean-theory-14modes"  # Locate the existing matrix and eigensolver implementation.
sys.path.insert(0, str(HERE))  # Make the verified inverse solver importable.
sys.path.insert(0, str(CLEAN_DIR))  # Make the existing matrix implementation importable.
import solve_modal_from_inverse as previous  # type: ignore  # Reuse only the verified inverse-force reconstruction function.
import solve as base  # type: ignore  # Reuse the formed geometry, assembly primitives, and generalized eigensolver.
import solve_v2 as v2  # type: ignore  # Reuse the audited mass-consistent full assembly.
import solve_v4_drawing_corrected as v4  # type: ignore  # Reuse the drawing-corrected portal and passage dimensions.

OUT = HERE / "modal_results_branch_clean"  # Isolate the branch-clean recalculation from all previous modal outputs.
OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated output directory idempotently.
base.OUT = OUT  # Redirect any reused base output into the isolated result directory.
v2.OUT = OUT  # Redirect any reused v2 output into the isolated result directory.
v4.OUT = OUT  # Redirect any reused drawing-corrected output into the isolated result directory.
LABEL_ORDER = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]  # Preserve the required fourteen-label reporting order.
ACOUSTIC_COHERENCE_MIN = 0.25  # Require floor and gantry systems to move as the same global branch rather than an optical relative mode.
MAIN_FRACTION_MIN = 0.45  # Require a main-span physical branch to carry at least forty-five percent of its selected field measure in the main span.
SIDE_FRACTION_MIN = 0.45  # Require a side-span candidate to localize at least forty-five percent of its selected field measure in the declared span.
LOCALIZATION_MAX = 0.20  # Exclude single-station and strongly local numerical or component modes.
FLOOR_PARTICIPATION_MIN = 0.20  # Exclude modes whose selected motion is almost entirely confined to the gantry-rope system.


def weighted_inner(left: np.ndarray, right: np.ndarray, weights: np.ndarray) -> float:  # Evaluate one weighted real inner product.
    return float(np.sum(weights * left * right))  # Return the weighted scalar product.


def weighted_norm(values: np.ndarray, weights: np.ndarray) -> float:  # Evaluate one weighted Euclidean norm.
    return math.sqrt(max(weighted_inner(values, values, weights), 0.0))  # Return the nonnegative weighted norm.


def weighted_correlation(left: np.ndarray, right: np.ndarray, weights: np.ndarray) -> float:  # Evaluate signed weighted shape correlation.
    denominator = weighted_norm(left, weights) * weighted_norm(right, weights)  # Form the product of the two weighted norms.
    return weighted_inner(left, right, weights) / max(denominator, 1.0e-30)  # Return the normalized signed correlation.


def weighted_coherence(left: np.ndarray, right: np.ndarray, weights: np.ndarray) -> float:  # Measure same-shape and same-amplitude acoustic motion between floor and gantry systems.
    numerator = 2.0 * weighted_inner(left, right, weights)  # Form twice the signed cross work.
    denominator = weighted_inner(left, left, weights) + weighted_inner(right, right, weights)  # Form the combined weighted amplitude.
    return numerator / max(denominator, 1.0e-30)  # Return a bounded coherence in the interval minus one to one.


def tributary(values: np.ndarray) -> np.ndarray:  # Build one-dimensional nodal integration weights from ordered coordinates.
    weights = np.zeros_like(values, dtype=float)  # Allocate the integration-weight vector.
    if len(values) == 1:  # Handle a single retained station explicitly.
        weights[0] = 1.0  # Assign a unit weight to the isolated station.
        return weights  # Return the single-station weight vector.
    weights[0] = 0.5 * abs(float(values[1] - values[0]))  # Assign the first half interval.
    weights[-1] = 0.5 * abs(float(values[-1] - values[-2]))  # Assign the final half interval.
    weights[1:-1] = 0.5 * np.abs(values[2:] - values[:-2])  # Assign the sum of neighboring half intervals to interior stations.
    return weights  # Return the complete integration weights.


def harmonic_descriptor(field: np.ndarray, coordinates: np.ndarray, weights: np.ndarray) -> tuple[int, float]:  # Describe but do not select a branch by its strongest sine projection.
    left = float(np.min(coordinates))  # Read the physical left endpoint of the retained span.
    length = float(np.max(coordinates) - left)  # Evaluate the retained span length.
    norm = weighted_norm(field, weights)  # Evaluate the selected field norm.
    scores: list[float] = []  # Initialize the first eight harmonic projection scores.
    for order in range(1, 9):  # Traverse the first eight fixed-end sine descriptors.
        basis = np.sin(order * math.pi * (coordinates - left) / length)  # Form the current fixed-end sine field.
        score = abs(weighted_inner(field, basis, weights)) / max(norm * weighted_norm(basis, weights), 1.0e-30)  # Evaluate its normalized absolute projection.
        scores.append(float(score))  # Store the descriptive projection score.
    return int(np.argmax(scores) + 1), float(max(scores))  # Return the strongest descriptive order and its score.


def zero_crossing_count(field: np.ndarray) -> int:  # Count robust interior sign changes as a second descriptive shape measure.
    scale = max(float(np.max(np.abs(field))), 1.0e-30)  # Form the maximum modal amplitude scale.
    filtered = np.where(np.abs(field) >= 0.03 * scale, field, 0.0)  # Suppress numerical sign chatter below three percent of peak amplitude.
    signs: list[int] = []  # Initialize the sequence of nonzero modal signs.
    for value in filtered:  # Traverse the filtered modal field in longitudinal order.
        sign = int(np.sign(value))  # Convert the current amplitude to minus one, zero, or one.
        if sign == 0:  # Ignore amplitudes inside the numerical dead band.
            continue  # Continue to the next station.
        if not signs or signs[-1] != sign:  # Retain only genuine sign-domain transitions.
            signs.append(sign)  # Append the new sign domain.
    return max(len(signs) - 1, 0)  # Return the number of robust interior sign changes.


def modal_records(model: dict, system: dict, floor_nodes: list[int], top_nodes: list[int], frequencies: np.ndarray, vectors: np.ndarray, residuals: list[float]) -> tuple[list[dict], dict[int, dict]]:  # Build target-free physical branch records for every solved mode.
    floor_x = np.array([base.xyz(model, int(node_id))[0] for node_id in floor_nodes], dtype=float)  # Read the ordered floor-chain longitudinal coordinates in metres.
    floor_weights = tributary(floor_x)  # Build floor-chain longitudinal integration weights.
    floor_index = {int(node_id): index for index, node_id in enumerate(floor_nodes)}  # Map every floor-chain node to its ordered field index.
    top_index = {int(node_id): index for index, node_id in enumerate(top_nodes)}  # Map every gantry-chain node to its ordered field index.
    span_groups = {"north": "北边跨", "main": "主跨", "south717": "南边跨", "south503": "南辅跨"}  # Declare the four physical MCT span groups.
    span_masks = {key: np.array([int(node_id) in {int(value) for value in model["groups"][group_name]["nodes"]} for node_id in floor_nodes], dtype=bool) for key, group_name in span_groups.items()}  # Build one ordered floor-node mask per physical span.
    main_mask = span_masks["main"]  # Select the main-span floor mask.
    main_x = floor_x[main_mask]  # Extract the main-span longitudinal coordinates.
    main_weights = floor_weights[main_mask]  # Extract the main-span integration weights.
    main_midpoint = 0.5 * (float(np.min(main_x)) + float(np.max(main_x)))  # Evaluate the physical main-span midpoint.
    main_floor_nodes = {int(node_id) for node_id in model["groups"]["主跨"]["nodes"]}  # Build the main-span floor-node membership set.
    portal_pairs = sorted([(int(record["floor_node"]), int(record["top_node"])) for record in system["portals"] if int(record["floor_node"]) in main_floor_nodes], key=lambda pair: base.xyz(model, pair[0])[0])  # Retain and order all main-span floor-to-gantry portal pairs.
    portal_x = np.array([base.xyz(model, floor_node)[0] for floor_node, _top_node in portal_pairs], dtype=float)  # Read the main-span portal coordinates.
    portal_weights = tributary(portal_x)  # Build the main-span portal integration weights.
    raw: list[dict] = []  # Initialize the complete raw modal record list.
    shapes: dict[int, dict] = {}  # Initialize the selected-field storage for later plotting and audit.
    for mode_index, frequency in enumerate(frequencies):  # Traverse every computed physical eigenmode.
        full = np.zeros(system["dof_count"], dtype=float)  # Allocate the complete constrained generalized vector.
        full[system["free"]] = vectors[:, mode_index]  # Restore the free eigenvector components into physical generalized coordinates.
        floor_values: dict[int, np.ndarray] = {}  # Initialize both catwalk floor-section fields.
        top_values: dict[int, np.ndarray] = {}  # Initialize both catwalk gantry-section fields.
        for catwalk in range(2):  # Traverse the upstream and downstream catwalks.
            floor_values[catwalk] = np.array([full[system["floor_dofs"][(catwalk, int(node_id))]] for node_id in floor_nodes], dtype=float)  # Read all four floor-section generalized coordinates.
            top_values[catwalk] = np.array([full[system["top_dofs"][(catwalk, int(node_id))]] for node_id in top_nodes], dtype=float)  # Read all four gantry-section generalized coordinates.
        lateral_upstream = floor_values[0][:, 1]  # Read the upstream floor lateral displacement field.
        lateral_downstream = floor_values[1][:, 1]  # Read the downstream floor lateral displacement field.
        vertical_upstream = floor_values[0][:, 2]  # Read the upstream floor vertical displacement field.
        vertical_downstream = floor_values[1][:, 2]  # Read the downstream floor vertical displacement field.
        lateral_common = (lateral_upstream + lateral_downstream) / math.sqrt(2.0)  # Form the energy-preserving common lateral coordinate.
        lateral_difference = (lateral_downstream - lateral_upstream) / math.sqrt(2.0)  # Form the energy-preserving differential lateral coordinate.
        vertical_common = (vertical_upstream + vertical_downstream) / math.sqrt(2.0)  # Form the energy-preserving common vertical coordinate.
        vertical_difference = (vertical_downstream - vertical_upstream) / math.sqrt(2.0)  # Form the energy-preserving double-catwalk roll coordinate before division by spacing.
        energy_lateral_common = weighted_inner(lateral_common, lateral_common, floor_weights)  # Evaluate common lateral modal measure.
        energy_lateral_difference = weighted_inner(lateral_difference, lateral_difference, floor_weights)  # Evaluate differential lateral modal measure.
        energy_vertical_common = weighted_inner(vertical_common, vertical_common, floor_weights)  # Evaluate common vertical modal measure.
        energy_vertical_difference = weighted_inner(vertical_difference, vertical_difference, floor_weights)  # Evaluate differential vertical or system-roll modal measure.
        family_measures = {"L": energy_lateral_common + energy_lateral_difference, "V": energy_vertical_common, "T": energy_vertical_difference}  # Form the three mutually interpretable global family measures.
        family = max(family_measures, key=family_measures.get)  # Select the physically dominant global family without target frequencies.
        if family == "L":  # Handle global lateral motion.
            if energy_lateral_common >= energy_lateral_difference:  # Test whether both catwalks move predominantly together laterally.
                relation = "common"  # Record the common lateral relation.
                selected_field = lateral_common  # Use the common lateral field for shape classification.
            else:  # Handle predominant differential lateral motion.
                relation = "differential"  # Record the differential lateral relation.
                selected_field = lateral_difference  # Use the differential lateral field for shape classification.
        elif family == "V":  # Handle common vertical bending.
            relation = "common"  # Record the defining common vertical relation.
            selected_field = vertical_common  # Use the common vertical field for shape classification.
        else:  # Handle double-catwalk global torsion.
            relation = "differential"  # Record the defining differential vertical relation.
            selected_field = vertical_difference  # Use the differential vertical field for shape classification.
        total_selected_measure = weighted_inner(selected_field, selected_field, floor_weights)  # Evaluate the selected full-line modal measure.
        span_fraction = {key: weighted_inner(selected_field[mask], selected_field[mask], floor_weights[mask]) / max(total_selected_measure, 1.0e-30) for key, mask in span_masks.items()}  # Evaluate the selected-field fraction in every physical span.
        main_field = selected_field[main_mask]  # Extract the selected main-span shape.
        reflected_field = np.interp(2.0 * main_midpoint - main_x, main_x, main_field)  # Reflect the main-span shape about its physical midpoint.
        parity = weighted_correlation(main_field, reflected_field, main_weights)  # Evaluate the signed midpoint-reflection parity.
        parity_label = "S" if parity >= 0.0 else "A"  # Assign symmetric or antisymmetric parity from the actual shape.
        harmonic_order, harmonic_score = harmonic_descriptor(main_field, main_x, main_weights)  # Describe the shape by its strongest fixed-end sine projection without using it for branch selection.
        crossings = zero_crossing_count(main_field)  # Count robust interior sign changes as an independent descriptor.
        catwalk_correlation = weighted_correlation(lateral_upstream if family == "L" else vertical_upstream, lateral_downstream if family == "L" else vertical_downstream, floor_weights)  # Evaluate the signed upstream-downstream relation in the underlying displacement component.
        floor_portal_upstream: list[float] = []  # Initialize the upstream floor motion at main-span portal pairs.
        floor_portal_downstream: list[float] = []  # Initialize the downstream floor motion at main-span portal pairs.
        top_portal_upstream: list[float] = []  # Initialize the upstream gantry motion at main-span portal pairs.
        top_portal_downstream: list[float] = []  # Initialize the downstream gantry motion at main-span portal pairs.
        component = 1 if family == "L" else 2  # Select lateral displacement for L and vertical displacement for V or T.
        for floor_node, top_node in portal_pairs:  # Traverse every main-span physical portal pair.
            floor_portal_upstream.append(float(floor_values[0][floor_index[floor_node], component]))  # Store the upstream floor-port motion.
            floor_portal_downstream.append(float(floor_values[1][floor_index[floor_node], component]))  # Store the downstream floor-port motion.
            top_portal_upstream.append(float(top_values[0][top_index[top_node], component]))  # Store the upstream gantry-port motion.
            top_portal_downstream.append(float(top_values[1][top_index[top_node], component]))  # Store the downstream gantry-port motion.
        floor_portal_upstream_array = np.asarray(floor_portal_upstream, dtype=float)  # Convert the upstream floor portal field to an array.
        floor_portal_downstream_array = np.asarray(floor_portal_downstream, dtype=float)  # Convert the downstream floor portal field to an array.
        top_portal_upstream_array = np.asarray(top_portal_upstream, dtype=float)  # Convert the upstream gantry portal field to an array.
        top_portal_downstream_array = np.asarray(top_portal_downstream, dtype=float)  # Convert the downstream gantry portal field to an array.
        if relation == "common":  # Form the acoustic comparison for a common two-catwalk branch.
            floor_portal_field = (floor_portal_upstream_array + floor_portal_downstream_array) / math.sqrt(2.0)  # Form the common floor portal field.
            top_portal_field = (top_portal_upstream_array + top_portal_downstream_array) / math.sqrt(2.0)  # Form the common gantry portal field.
        else:  # Form the acoustic comparison for a differential two-catwalk branch.
            floor_portal_field = (floor_portal_downstream_array - floor_portal_upstream_array) / math.sqrt(2.0)  # Form the differential floor portal field.
            top_portal_field = (top_portal_downstream_array - top_portal_upstream_array) / math.sqrt(2.0)  # Form the differential gantry portal field.
        acoustic_coherence = weighted_coherence(floor_portal_field, top_portal_field, portal_weights)  # Measure same-shape and same-amplitude floor-gantry motion.
        floor_top_correlation = weighted_correlation(floor_portal_field, top_portal_field, portal_weights)  # Record the pure signed shape correlation separately.
        floor_portal_measure = weighted_inner(floor_portal_field, floor_portal_field, portal_weights)  # Evaluate floor selected motion at the portal stations.
        top_portal_measure = weighted_inner(top_portal_field, top_portal_field, portal_weights)  # Evaluate gantry selected motion at the portal stations.
        floor_participation = floor_portal_measure / max(floor_portal_measure + top_portal_measure, 1.0e-30)  # Quantify whether the global branch is visible in the floor system.
        nodal_measure = floor_weights * selected_field**2  # Form the longitudinal selected-field density.
        localization = float(np.max(nodal_measure) / max(np.sum(nodal_measure), 1.0e-30))  # Detect concentration at one longitudinal station.
        total_family_measure = max(sum(family_measures.values()), 1.0e-30)  # Form the total family-classification measure.
        record = {"mode": int(mode_index + 1), "frequency_hz": float(frequency), "eigen_residual": float(residuals[mode_index]), "family": family, "catwalk_relation": relation, "family_fraction_L": float(family_measures["L"] / total_family_measure), "family_fraction_V": float(family_measures["V"] / total_family_measure), "family_fraction_T": float(family_measures["T"] / total_family_measure), "parity": float(parity), "parity_label": parity_label, "harmonic_order_descriptor": int(harmonic_order), "harmonic_score": float(harmonic_score), "interior_zero_crossings": int(crossings), "upstream_downstream_correlation": float(catwalk_correlation), "floor_gantry_acoustic_coherence": float(acoustic_coherence), "floor_gantry_shape_correlation": float(floor_top_correlation), "floor_participation": float(floor_participation), "localization": float(localization), "north_fraction": float(span_fraction["north"]), "main_fraction": float(span_fraction["main"]), "south717_fraction": float(span_fraction["south717"]), "south503_fraction": float(span_fraction["south503"])}  # Store the complete target-free branch record.
        raw.append(record)  # Append the current modal record.
        shapes[int(mode_index + 1)] = {"x_m": floor_x.tolist(), "selected_field": selected_field.tolist(), "main_field": main_field.tolist(), "family": family, "catwalk_relation": relation, "floor_portal_x_m": portal_x.tolist(), "floor_portal_field": floor_portal_field.tolist(), "top_portal_field": top_portal_field.tolist()}  # Preserve the physical fields required for audit plots.
    return raw, shapes  # Return every target-free branch record and its selected fields.


def select_branches(raw: list[dict]) -> dict[str, dict]:  # Select the fourteen physical labels by branch rank rather than fixed harmonic order.
    selected: dict[str, dict] = {}  # Initialize the selected fourteen-family table.
    used: set[int] = set()  # Prevent any numerical eigenvector from receiving two physical labels.
    side_definitions = [("SIDE1", "south717_fraction"), ("SIDE2", "north_fraction"), ("SIDE3", "south503_fraction")]  # Declare the three side-span localization labels.
    for label, fraction_key in side_definitions:  # Traverse every predeclared side-span family.
        candidates = [record for record in raw if record["mode"] not in used and record[fraction_key] >= SIDE_FRACTION_MIN and record["floor_participation"] >= FLOOR_PARTICIPATION_MIN and record["localization"] <= LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Apply only physical span, participation, localization, and frequency-band filters.
        if candidates:  # Test whether a physical side-span candidate exists.
            choice = min(candidates, key=lambda record: (record["frequency_hz"], -record[fraction_key]))  # Select the lowest global mode localized in the declared physical span.
            selected[label] = {**choice, "selection_rule": f"lowest global branch with {fraction_key}>={SIDE_FRACTION_MIN:.2f}"}  # Store the side-span selection and its rule.
            used.add(int(choice["mode"]))  # Mark the selected numerical mode as consumed.
        else:  # Handle a missing side-span branch honestly.
            selected[label] = {"status": "unidentified", "selection_rule": f"no global branch with {fraction_key}>={SIDE_FRACTION_MIN:.2f}"}  # Preserve an explicit unidentified state.
    main_candidates = [record for record in raw if record["mode"] not in used and record["main_fraction"] >= MAIN_FRACTION_MIN and record["floor_gantry_acoustic_coherence"] >= ACOUSTIC_COHERENCE_MIN and record["floor_participation"] >= FLOOR_PARTICIPATION_MIN and record["localization"] <= LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Build the global acoustic main-span branch set without a harmonic-order condition.
    label_specs = {"LS1": ("L", "common", "S", 1), "LS2": ("L", "common", "S", 2), "LA1": ("L", "common", "A", 1), "LA2": ("L", "common", "A", 2), "VS1": ("V", "common", "S", 1), "VS2": ("V", "common", "S", 2), "VA1": ("V", "common", "A", 1), "VA2": ("V", "common", "A", 2), "TS1": ("T", "differential", "S", 1), "TS2": ("T", "differential", "S", 2), "TA1": ("T", "differential", "A", 1)}  # Define every main-span label by family, two-catwalk relation, parity, and ascending branch rank only.
    for label, (family, relation, parity_label, rank) in label_specs.items():  # Traverse every requested main-span physical label.
        candidates = sorted([record for record in main_candidates if record["mode"] not in used and record["family"] == family and record["catwalk_relation"] == relation and record["parity_label"] == parity_label], key=lambda record: record["frequency_hz"])  # Filter and frequency-order only physically admissible acoustic branches.
        if len(candidates) >= rank:  # Test whether the requested parity-family rank exists.
            choice = candidates[rank - 1]  # Select the requested ascending physical branch rank.
            selected[label] = {**choice, "selection_rule": f"rank {rank} by frequency among acoustic main-span {family}-{relation}-{parity_label} branches; harmonic order is descriptive only"}  # Store the selected physical branch and its target-free rule.
            used.add(int(choice["mode"]))  # Mark the numerical mode as consumed.
        else:  # Handle a missing physical branch rank honestly.
            selected[label] = {"status": "unidentified", "selection_rule": f"fewer than {rank} acoustic main-span {family}-{relation}-{parity_label} branches"}  # Preserve an explicit unidentified state.
    return selected  # Return the complete target-free fourteen-family selection.


def write_outputs(raw: list[dict], selected: dict[str, dict], shapes: dict[int, dict], summary: dict) -> None:  # Write the complete recalculation evidence package.
    with (OUT / "raw_branch_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the complete raw branch table.
        writer = csv.DictWriter(handle, fieldnames=list(raw[0].keys()))  # Create a named-column CSV writer.
        writer.writeheader()  # Write the raw branch table header.
        writer.writerows(raw)  # Write every solved target-free modal record.
    selected_fields = ["label", "status", "mode", "frequency_hz", "family", "catwalk_relation", "parity_label", "branch_rank_rule", "harmonic_order_descriptor", "harmonic_score", "interior_zero_crossings", "floor_gantry_acoustic_coherence", "floor_gantry_shape_correlation", "main_fraction", "north_fraction", "south717_fraction", "south503_fraction", "eigen_residual", "selection_rule"]  # Define the selected fourteen-family table columns.
    with (OUT / "classified_14_modes_branch_clean.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the selected fourteen-family table.
        writer = csv.DictWriter(handle, fieldnames=selected_fields)  # Create its named-column CSV writer.
        writer.writeheader()  # Write the selected table header.
        for label in LABEL_ORDER:  # Preserve the requested physical label order.
            record = selected.get(label, {"status": "unidentified"})  # Read the selected record or an explicit missing state.
            writer.writerow({"label": label, "status": record.get("status", "identified"), "mode": record.get("mode"), "frequency_hz": record.get("frequency_hz"), "family": record.get("family"), "catwalk_relation": record.get("catwalk_relation"), "parity_label": record.get("parity_label"), "branch_rank_rule": record.get("selection_rule"), "harmonic_order_descriptor": record.get("harmonic_order_descriptor"), "harmonic_score": record.get("harmonic_score"), "interior_zero_crossings": record.get("interior_zero_crossings"), "floor_gantry_acoustic_coherence": record.get("floor_gantry_acoustic_coherence"), "floor_gantry_shape_correlation": record.get("floor_gantry_shape_correlation"), "main_fraction": record.get("main_fraction"), "north_fraction": record.get("north_fraction"), "south717_fraction": record.get("south717_fraction"), "south503_fraction": record.get("south503_fraction"), "eigen_residual": record.get("eigen_residual"), "selection_rule": record.get("selection_rule")})  # Write the current selected physical branch.
    (OUT / "selected_mode_shapes.json").write_text(json.dumps({label: shapes.get(int(record["mode"])) for label, record in selected.items() if "mode" in record}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Preserve the selected physical fields for independent inspection.
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the concise recalculation summary.


def main() -> int:  # Execute the complete branch-clean inverse-static and modal recalculation.
    v4.apply_drawing_corrections()  # Apply only the independently documented drawing corrections before assembly.
    model = base.load_mct()  # Parse and hash-check the sole MCT geometry, topology, support, and load source.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-chain topology.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope topology.
    static = previous.recover_static_state(model)  # Recompute the unique MCT-geometry inverse axial-force state from scratch.
    if not bool(static["success"]):  # Reject any inverse-solver failure before modal assembly.
        raise RuntimeError(str(static["message"]))  # Report the exact inverse-solver failure.
    if int(static["nullity"]) != 0:  # Require a unique aggregate force field.
        raise RuntimeError(f"Inverse equilibrium nullity is {static['nullity']}")  # Reject an unresolved self-stress branch.
    if float(static["min_cable_force_kN"]) <= 0.0:  # Require every cable to remain in tension.
        raise RuntimeError(f"Minimum recovered cable force is {static['min_cable_force_kN']:.6f} kN")  # Reject cable compression before forming geometric stiffness.
    if float(static["max_abs_force_error_percent"]) > 0.5:  # Require the independently recovered force field to remain within the declared elementwise MCT agreement band.
        raise RuntimeError(f"Maximum MCT initial-force mismatch is {static['max_abs_force_error_percent']:.6f}%")  # Reject a prestress state that no longer matches the verified MCT equilibrium state.
    system = v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Reassemble the complete drawing-corrected 44-rope, portal, passage, and mass matrices.
    frequencies, vectors, residuals, matrix_checks = base.solve_eigen(system)  # Recompute and verify the low generalized eigenpairs from the newly assembled matrices.
    raw, shapes = modal_records(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Reclassify every mode by global physical fields and floor-gantry branch coherence.
    selected = select_branches(raw)  # Select the fourteen labels by physical branch rank without hard-coded harmonic orders.
    identified = {label: float(record["frequency_hz"]) for label, record in selected.items() if "frequency_hz" in record}  # Build the compact identified-frequency map.
    frozen = {"kind": "mct_inverse_prestress_modal_branch_clean_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False, "mct_initial_force_used_in_inverse": False, "mct_initial_force_loaded_after_inverse_for_verification": True, "classification_uses_fixed_harmonic_order": False, "classification_rule": "physical L/V/T field, common or differential catwalk relation, midpoint parity, floor-gantry acoustic coherence, span localization, then ascending branch rank; sine order is descriptive only", "thresholds": {"acoustic_coherence_min": ACOUSTIC_COHERENCE_MIN, "main_fraction_min": MAIN_FRACTION_MIN, "side_fraction_min": SIDE_FRACTION_MIN, "localization_max": LOCALIZATION_MAX, "floor_participation_min": FLOOR_PARTICIPATION_MIN}, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": matrix_checks, "mass_audit": system["mass_audit_v2"], "first_40_frequencies_hz": [float(value) for value in frequencies[:40]], "raw_modes": raw, "classified_14": selected}  # Assemble the target-free frozen recalculation result.
    frozen_path = OUT / "frozen_results_branch_clean.json"  # Define the immutable target-free result path.
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Freeze the complete target-free branch calculation before any comparison.
    frozen_sha256 = base.sha(frozen_path)  # Compute the immutable target-free result digest.
    summary = {"kind": "mct_inverse_prestress_modal_branch_clean_summary_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha256, "inverse_static": frozen["inverse_static"], "matrix_checks": matrix_checks, "identified_count": int(len(identified)), "identified_frequencies_hz": identified, "classification_uses_fixed_harmonic_order": False, "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False}  # Build the concise target-free calculation receipt.
    write_outputs(raw, selected, shapes, summary)  # Write every primary target-free result file.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve every explicit rope force and recovered unstressed length.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every generated result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete recalculation summary into the workflow log.
    return 0  # Report successful recalculation completion.


if __name__ == "__main__":  # Execute only when invoked as the main calculation program.
    raise SystemExit(main())  # Return the numerical status to the operating system.
