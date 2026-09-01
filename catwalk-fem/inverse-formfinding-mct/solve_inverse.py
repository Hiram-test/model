from __future__ import annotations  # Enable stable type annotations.
import csv  # Write elementwise force comparisons.
import json  # Write deterministic machine-readable summaries.
import math  # Evaluate finite scalar checks.
import sys  # Add the verified parser directory to imports.
from pathlib import Path  # Resolve repository and output paths.
import numpy as np  # Assemble equilibrium vectors and calculate statistics.
from scipy.linalg import lstsq  # Solve the unregularized full-rank equilibrium system.
from scipy.optimize import lsq_linear  # Enforce tension-only bounds when required.
from scipy.sparse import coo_matrix  # Assemble the sparse equilibrium operator.

HERE = Path(__file__).resolve().parent  # Locate this isolated calculation directory.
CATWALK_FEM = HERE.parent  # Locate the catwalk-fem directory.
MCT_DIR = CATWALK_FEM / "mct-from-zero"  # Locate the verified parser and MCT source.
sys.path.insert(0, str(MCT_DIR))  # Make the verified parser importable.
from parse_mct import load_mct  # type: ignore  # Read only the hash-checked MCT file.

OUT = HERE / "results"  # Define the isolated output directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the output directory if needed.
BODY_MIN_LENGTH_M = 5.0  # Separate short anchor and reaction-dominated members in reporting.


def xyz_mm(model: dict, node_id: int) -> np.ndarray:  # Return one MCT node coordinate in millimetres.
    node = model["nodes"][node_id]  # Read the parsed node record.
    return np.array([float(node["x"]), float(node["y"]), float(node["z"])], dtype=float)  # Form the coordinate vector.


def fixed_sets(model: dict) -> tuple[set[int], set[int], set[int]]:  # Recover the three translational support sets.
    fixed_x: set[int] = set()  # Initialize the longitudinal restraint set.
    fixed_y: set[int] = set()  # Initialize the transverse restraint set.
    fixed_z: set[int] = set()  # Initialize the vertical restraint set.
    for constraint in model["constraints"]:  # Traverse every MCT restraint record.
        code = str(constraint["dof"])  # Read the six-character restraint code.
        for node_id in constraint["nodes"]:  # Traverse every node in the record.
            node_id = int(node_id)  # Normalize the node identifier.
            if len(code) >= 1 and code[0] == "1":  # Test the global-X restraint flag.
                fixed_x.add(node_id)  # Add the node to the longitudinal restraint set.
            if len(code) >= 2 and code[1] == "1":  # Test the global-Y restraint flag.
                fixed_y.add(node_id)  # Add the node to the transverse restraint set.
            if len(code) >= 3 and code[2] == "1":  # Test the global-Z restraint flag.
                fixed_z.add(node_id)  # Add the node to the vertical restraint set.
    return fixed_x, fixed_y, fixed_z  # Return all translational restraint sets.


def external_components(model: dict) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray], dict[int, np.ndarray]]:  # Build self-weight, stage-two, and combined nodal loads.
    node_ids = sorted(int(node_id) for node_id in model["nodes"])  # Collect all model node identifiers.
    selfweight = {node_id: np.zeros(3, dtype=float) for node_id in node_ids}  # Initialize exact MCT self-weight nodal loads in kilonewtons.
    stage_two = {node_id: np.zeros(3, dtype=float) for node_id in node_ids}  # Initialize exact MCT stage-two nodal loads in kilonewtons.
    sw = model.get("selfweight") or {"gx": 0.0, "gy": 0.0, "gz": 0.0}  # Read the MCT self-weight direction factors.
    direction = np.array([float(sw["gx"]), float(sw["gy"]), float(sw["gz"])], dtype=float)  # Form the self-weight direction vector.
    for element_id, element in model["elems"].items():  # Traverse every physical MCT element.
        node_i = int(element["n1"])  # Read the first element endpoint.
        node_j = int(element["n2"])  # Read the second element endpoint.
        delta = xyz_mm(model, node_j) - xyz_mm(model, node_i)  # Evaluate the exact formed element vector.
        length_mm = float(np.linalg.norm(delta))  # Evaluate the exact formed element length in millimetres.
        material = model["materials"][int(element["mat"])]  # Read the assigned material record.
        section = model["sections"][int(element["sec"])]  # Read the assigned section record.
        density = float(material["den_raw"])  # Read the MCT weight-density value in its native consistent units.
        area_mm2 = float(section["area_mm2"])  # Read the section area in square millimetres.
        element_weight_kN = density * area_mm2 * length_mm  # Convert density times area times formed length to element weight in kilonewtons.
        equivalent = 0.5 * element_weight_kN * direction  # Form the equal two-node consistent resultant for constant self-weight.
        selfweight[node_i] += equivalent  # Add half the element weight to the first endpoint.
        selfweight[node_j] += equivalent  # Add half the element weight to the second endpoint.
    for record in model["conload_erqi"]:  # Traverse every parsed stage-two nodal load record.
        node_id = int(record["nid"])  # Read the loaded node identifier.
        stage_two[node_id] += np.array([float(record["fx_kN"]), float(record["fy_kN"]), float(record["fz_kN"])], dtype=float)  # Add the exact MCT nodal load components.
    combined = {node_id: selfweight[node_id] + stage_two[node_id] for node_id in node_ids}  # Sum the two independently parsed load components.
    return selfweight, stage_two, combined  # Return the separate and combined nodal loads.


def equilibrium_operator(model: dict) -> tuple[coo_matrix, np.ndarray, list[int], list[tuple[int, int]], dict[int, int]]:  # Assemble the planar free-node equilibrium operator.
    fixed_x, _fixed_y, fixed_z = fixed_sets(model)  # Read the physical support topology.
    element_ids = sorted(int(element_id) for element_id in model["elems"])  # Preserve deterministic element-column order.
    element_column = {element_id: column for column, element_id in enumerate(element_ids)}  # Map each element to its equilibrium column.
    row_keys: list[tuple[int, int]] = []  # Initialize free equilibrium rows as node-component pairs.
    for node_id in sorted(int(node_id) for node_id in model["nodes"]):  # Traverse all physical nodes.
        if node_id not in fixed_x:  # Test whether longitudinal equilibrium is reaction-free.
            row_keys.append((node_id, 0))  # Retain the global-X equilibrium equation.
        if node_id not in fixed_z:  # Test whether vertical equilibrium is reaction-free.
            row_keys.append((node_id, 2))  # Retain the global-Z equilibrium equation.
    row_index = {key: row for row, key in enumerate(row_keys)}  # Map every free node-component pair to a matrix row.
    rows: list[int] = []  # Initialize sparse row indices.
    cols: list[int] = []  # Initialize sparse column indices.
    values: list[float] = []  # Initialize sparse coefficients.
    lengths_m = np.zeros(len(element_ids), dtype=float)  # Allocate exact formed element lengths for reporting.
    for element_id in element_ids:  # Traverse every axial element.
        element = model["elems"][element_id]  # Read the current element record.
        node_i = int(element["n1"])  # Read the first endpoint.
        node_j = int(element["n2"])  # Read the second endpoint.
        delta_mm = xyz_mm(model, node_j) - xyz_mm(model, node_i)  # Evaluate the exact formed element vector.
        length_mm = float(np.linalg.norm(delta_mm))  # Evaluate the exact formed element length.
        direction = delta_mm / length_mm  # Evaluate the exact unit direction vector.
        column = element_column[element_id]  # Resolve the current element-force column.
        lengths_m[column] = 1.0e-3 * length_mm  # Store the formed element length in metres.
        for node_id, sign in ((node_i, 1.0), (node_j, -1.0)):  # Apply equal and opposite tensile nodal forces.
            for component in (0, 2):  # Assemble only the physical X-Z form-finding plane.
                key = (node_id, component)  # Form the candidate free-equilibrium key.
                if key in row_index:  # Test whether this component has no support reaction.
                    rows.append(row_index[key])  # Append the global equilibrium row.
                    cols.append(column)  # Append the current force column.
                    values.append(sign * float(direction[component]))  # Append the directional equilibrium coefficient.
    operator = coo_matrix((values, (rows, cols)), shape=(len(row_keys), len(element_ids)))  # Build the sparse free-equilibrium operator.
    return operator, lengths_m, element_ids, row_keys, element_column  # Return the operator and deterministic metadata.


def right_hand(row_keys: list[tuple[int, int]], loads: dict[int, np.ndarray]) -> np.ndarray:  # Form the free-node equilibrium right-hand side.
    return -np.array([float(loads[node_id][component]) for node_id, component in row_keys], dtype=float)  # Move external nodal loads to the right-hand side.


def force_family(model: dict, element_id: int) -> str:  # Assign each TENSTR element to its reporting family.
    floor = set(int(value) for value in model["groups"]["ZJG04_bcs"]["elems"])  # Read the 727-member floor chain.
    gantry = set(int(value) for value in model["groups"]["门架索"]["elems"])  # Read the 394-member gantry-rope chain.
    if element_id in floor:  # Test floor-chain membership.
        return "floor_chain"  # Return the floor-chain family.
    if element_id in {728, 729}:  # Test the two down-pull members.
        return "downpull"  # Return the down-pull family.
    if element_id in gantry:  # Test gantry-rope membership.
        return "gantry_rope"  # Return the gantry-rope family.
    return "other"  # Preserve any unexpected TENSTR member explicitly.


def statistics(relative_errors: np.ndarray) -> dict[str, float | int | None]:  # Compute deterministic absolute-relative-error statistics.
    if relative_errors.size == 0:  # Handle an empty selection.
        return {"count": 0, "mean_abs_percent": None, "median_abs_percent": None, "p95_abs_percent": None, "max_abs_percent": None, "signed_mean_percent": None}  # Return an explicit empty record.
    absolute = np.abs(relative_errors) * 100.0  # Convert absolute relative errors to percent.
    return {"count": int(relative_errors.size), "mean_abs_percent": float(np.mean(absolute)), "median_abs_percent": float(np.median(absolute)), "p95_abs_percent": float(np.percentile(absolute, 95.0)), "max_abs_percent": float(np.max(absolute)), "signed_mean_percent": float(100.0 * np.mean(relative_errors))}  # Return all requested statistics.


def main() -> int:  # Execute the isolated MCT-geometry inverse form-finding calculation.
    model = load_mct()  # Parse and hash-check the sole MCT geometry and load source.
    operator_coo, lengths_m, element_ids, row_keys, element_column = equilibrium_operator(model)  # Assemble the exact free-equilibrium operator.
    operator = operator_coo.tocsr()  # Convert the operator to compressed sparse form.
    selfweight, stage_two, combined = external_components(model)  # Build the exact MCT load components without reading initial forces.
    right_selfweight = right_hand(row_keys, selfweight)  # Form the self-weight-only equilibrium right-hand side.
    right_stage_two = right_hand(row_keys, stage_two)  # Form the stage-two-only equilibrium right-hand side.
    right_combined = right_hand(row_keys, combined)  # Form the complete self-weight-plus-stage-two equilibrium right-hand side.
    dense_operator = operator.toarray()  # Convert the moderate equilibrium operator to dense form for rank-revealing QR.
    unconstrained, _residual_array, rank, _singular = lstsq(dense_operator, right_combined, cond=None, lapack_driver="gelsy")  # Solve the unregularized rank-revealing least-squares problem.
    tenstr_columns = np.array([element_column[element_id] for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TENSTR"], dtype=int)  # Address all tension-only element columns.
    lower = np.full(len(element_ids), -np.inf, dtype=float)  # Initialize unrestricted lower force bounds.
    upper = np.full(len(element_ids), np.inf, dtype=float)  # Initialize unrestricted upper force bounds.
    lower[tenstr_columns] = 0.0  # Enforce nonnegative axial force in every TENSTR member.
    if float(np.min(unconstrained[tenstr_columns])) >= -1.0e-8:  # Test whether the unique unregularized solution already satisfies tension-only physics.
        recovered = unconstrained  # Adopt the unregularized equilibrium solution without adding a selector.
        bounded_status = "unbounded_solution_is_tension_admissible"  # Record why no bounded iteration was needed.
        bounded_success = True  # Record successful admissibility.
    else:  # Handle a solution containing compression in tension-only members.
        bounded = lsq_linear(operator, right_combined, bounds=(lower, upper), tol=1.0e-12, lsmr_tol=1.0e-12, max_iter=5000, verbose=0)  # Solve the bounded equilibrium problem without target-force regularization.
        recovered = bounded.x  # Adopt the bounded equilibrium solution.
        bounded_status = str(bounded.message)  # Record the bounded solver status.
        bounded_success = bool(bounded.success)  # Record bounded solver success.
    equilibrium_residual = operator @ recovered - right_combined  # Evaluate the complete physical free-node equilibrium residual.
    equilibrium_relative = float(np.linalg.norm(equilibrium_residual) / max(np.linalg.norm(right_combined), 1.0e-30))  # Normalize the equilibrium residual.
    tenstr_ids = [element_id for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TENSTR"]  # Collect all TENSTR element identifiers.
    truss_ids = [element_id for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TRUSS"]  # Collect all portal TRUSS element identifiers.
    tenstr_target = np.array([float(model["iniforce"][element_id]["axial_kN"]) for element_id in tenstr_ids], dtype=float)  # Load MCT initial forces only after the inverse solution is frozen.
    tenstr_recovered = np.array([float(recovered[element_column[element_id]]) for element_id in tenstr_ids], dtype=float)  # Extract the recovered TENSTR force vector.
    relative_error = (tenstr_recovered - tenstr_target) / tenstr_target  # Compute the elementwise signed relative error.
    truss_matrix = operator[:, [element_column[element_id] for element_id in truss_ids]].toarray()  # Extract the portal-force equilibrium columns.
    target_without_truss = right_combined - operator[:, [element_column[element_id] for element_id in tenstr_ids]] @ tenstr_target  # Form the residual equilibrium demand after inserting stored TENSTR forces.
    target_truss, _target_residuals, _target_rank, _target_singular = lstsq(truss_matrix, target_without_truss, cond=None, lapack_driver="gelsy")  # Recover the portal forces that best equilibrate the stored initial cable forces.
    target_equilibrium_residual = truss_matrix @ target_truss - target_without_truss  # Evaluate the stored-force free-node equilibrium residual.
    target_equilibrium_relative = float(np.linalg.norm(target_equilibrium_residual) / max(np.linalg.norm(right_combined), 1.0e-30))  # Normalize the stored-force equilibrium residual.
    comparison_rows: list[dict] = []  # Initialize the elementwise comparison table.
    for index, element_id in enumerate(tenstr_ids):  # Traverse every physical TENSTR member.
        column = element_column[element_id]  # Resolve the current equilibrium column.
        comparison_rows.append({"element_id": int(element_id), "family": force_family(model, element_id), "length_m": float(lengths_m[column]), "recovered_kN": float(tenstr_recovered[index]), "mct_iniforce_kN": float(tenstr_target[index]), "signed_error_kN": float(tenstr_recovered[index] - tenstr_target[index]), "relative_error_percent": float(100.0 * relative_error[index]), "body_member": bool(lengths_m[column] >= BODY_MIN_LENGTH_M)})  # Store the current elementwise result.
    with (OUT / "inverse_force_comparison.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the elementwise force comparison file.
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0].keys()))  # Create a named-column CSV writer.
        writer.writeheader()  # Write the comparison header.
        writer.writerows(comparison_rows)  # Write every TENSTR comparison row.
    family_summary: dict[str, dict] = {}  # Initialize grouped force-match statistics.
    for family in ("floor_chain", "downpull", "gantry_rope", "other"):  # Traverse every reporting family.
        indices = np.array([index for index, element_id in enumerate(tenstr_ids) if force_family(model, element_id) == family], dtype=int)  # Address all family members.
        if indices.size == 0:  # Skip empty families while keeping deterministic output.
            family_summary[family] = {"all": statistics(np.array([], dtype=float)), "body": statistics(np.array([], dtype=float)), "recovered_mean_kN": None, "target_mean_kN": None}  # Store an explicit empty family record.
            continue  # Continue with the next family.
        body_indices = np.array([index for index in indices if lengths_m[element_column[tenstr_ids[index]]] >= BODY_MIN_LENGTH_M], dtype=int)  # Remove only short anchor and reaction-dominated members from the secondary body metric.
        family_summary[family] = {"all": statistics(relative_error[indices]), "body": statistics(relative_error[body_indices]), "recovered_mean_kN": float(np.mean(tenstr_recovered[indices])), "target_mean_kN": float(np.mean(tenstr_target[indices])), "force_correlation": float(np.corrcoef(tenstr_recovered[indices], tenstr_target[indices])[0, 1]) if indices.size > 1 else None}  # Store grouped force statistics.
    body_mask = np.array([lengths_m[element_column[element_id]] >= BODY_MIN_LENGTH_M for element_id in tenstr_ids], dtype=bool)  # Build the complete physical-body mask.
    load_stats = {"selfweight_total_kN": np.sum(np.array(list(selfweight.values())), axis=0).astype(float).tolist(), "stage_two_total_kN": np.sum(np.array(list(stage_two.values())), axis=0).astype(float).tolist(), "combined_total_kN": np.sum(np.array(list(combined.values())), axis=0).astype(float).tolist(), "stage_two_record_count": int(len(model["conload_erqi"])), "stage_two_nonzero_fx": int(sum(abs(float(record["fx_kN"])) > 1.0e-12 for record in model["conload_erqi"])), "stage_two_nonzero_fy": int(sum(abs(float(record["fy_kN"])) > 1.0e-12 for record in model["conload_erqi"])), "stage_two_nonzero_fz": int(sum(abs(float(record["fz_kN"])) > 1.0e-12 for record in model["conload_erqi"]))}  # Record independently parsed load totals and component counts.
    component_audit = {"right_selfweight_norm_kN": float(np.linalg.norm(right_selfweight)), "right_stage_two_norm_kN": float(np.linalg.norm(right_stage_two)), "right_combined_norm_kN": float(np.linalg.norm(right_combined)), "stored_force_equilibrium_relative_residual": target_equilibrium_relative}  # Record load-component and target-equilibrium diagnostics.
    verdict = bool(bounded_success and equilibrium_relative <= 1.0e-8 and target_equilibrium_relative <= 1.0e-4 and statistics(relative_error[body_mask])["p95_abs_percent"] is not None and float(statistics(relative_error[body_mask])["p95_abs_percent"]) <= 5.0)  # Apply the declared initial-force agreement criterion without tuning model inputs.
    summary = {"model": "mct_geometry_inverse_formfinding_v1", "source_sha256": model["source"]["sha256"], "source_bytes": model["source"]["bytes"], "node_count": int(model["counts"]["n_nodes"]), "element_count": int(model["counts"]["n_elems"]), "equilibrium_shape": [int(operator.shape[0]), int(operator.shape[1])], "equilibrium_rank": int(rank), "equilibrium_nullity": int(operator.shape[1] - rank), "bounded_status": bounded_status, "equilibrium_relative_residual": equilibrium_relative, "minimum_recovered_tenstr_kN": float(np.min(tenstr_recovered)), "maximum_recovered_tenstr_kN": float(np.max(tenstr_recovered)), "stored_force_equilibrium_relative_residual": target_equilibrium_relative, "all_tenstr_match": statistics(relative_error), "body_tenstr_match": statistics(relative_error[body_mask]), "family_match": family_summary, "load_stats": load_stats, "component_audit": component_audit, "success_initial_force_agreement": verdict, "initial_force_used_in_inverse_solve": False, "initial_force_loaded_after_solution_freeze": True}  # Assemble the full inverse form-finding summary.
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the complete machine-readable summary.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete result into the workflow log.
    return 0  # Report successful program execution regardless of scientific verdict.


if __name__ == "__main__":  # Execute only when invoked as a program.
    raise SystemExit(main())  # Return the program status to the operating system.
