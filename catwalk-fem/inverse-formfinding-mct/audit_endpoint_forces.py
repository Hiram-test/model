from __future__ import annotations  # Enable stable type annotations.
import json  # Write deterministic audit output.
from pathlib import Path  # Resolve the isolated result directory.
import numpy as np  # Assemble endpoint-force equilibrium vectors.
from scipy.linalg import lstsq  # Recover the portal forces without regularization.
from solve_inverse import equilibrium_operator  # Reuse the frozen equilibrium topology.
from solve_inverse import external_components  # Reuse the independently parsed MCT load construction.
from solve_inverse import load_mct  # Reuse the hash-checked MCT parser entry point.
from solve_inverse import right_hand  # Reuse the free-equilibrium load-vector mapping.
from solve_inverse import xyz_mm  # Reuse exact MCT formed coordinates.

HERE = Path(__file__).resolve().parent  # Locate the isolated calculation directory.
OUT = HERE / "results"  # Locate the shared result directory.
OUT.mkdir(parents=True, exist_ok=True)  # Ensure the result directory exists.


def main() -> int:  # Execute the endpoint-force consistency audit.
    model = load_mct()  # Parse the sole hash-checked MCT source.
    operator_coo, _lengths_m, element_ids, row_keys, element_column = equilibrium_operator(model)  # Rebuild the frozen free-equilibrium operator.
    operator = operator_coo.tocsr()  # Convert the operator to compressed sparse form.
    _selfweight, _stage_two, combined = external_components(model)  # Rebuild the complete MCT load vector without initial-force input.
    right_combined = right_hand(row_keys, combined)  # Form the free-equilibrium right-hand side.
    row_index = {key: row for row, key in enumerate(row_keys)}  # Map node-component keys to free-equilibrium rows.
    tenstr_ids = [element_id for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TENSTR"]  # Collect all cable-element identifiers.
    truss_ids = [element_id for element_id in element_ids if str(model["elems"][element_id]["type"]).upper() == "TRUSS"]  # Collect all portal-element identifiers.
    endpoint_internal = np.zeros(len(row_keys), dtype=float)  # Allocate free-node internal forces from MCT endpoint force records.
    for element_id in tenstr_ids:  # Traverse every cable element.
        element = model["elems"][element_id]  # Read the current cable incidence.
        node_i = int(element["n1"])  # Read the first endpoint.
        node_j = int(element["n2"])  # Read the second endpoint.
        delta = xyz_mm(model, node_j) - xyz_mm(model, node_i)  # Evaluate the exact formed element vector.
        direction = delta / np.linalg.norm(delta)  # Evaluate the exact element unit direction.
        force_i = float(model["ini_eforce"][element_id]["axial_i_kN"])  # Read the MCT first-end axial force only for post-solve consistency audit.
        force_j = float(model["ini_eforce"][element_id]["axial_j_kN"])  # Read the MCT second-end axial force only for post-solve consistency audit.
        for component in (0, 2):  # Traverse the longitudinal and vertical components.
            key_i = (node_i, component)  # Form the first-end free-equilibrium key.
            key_j = (node_j, component)  # Form the second-end free-equilibrium key.
            if key_i in row_index:  # Test whether the first-end component is reaction-free.
                endpoint_internal[row_index[key_i]] += force_i * float(direction[component])  # Add the first-end tensile force component.
            if key_j in row_index:  # Test whether the second-end component is reaction-free.
                endpoint_internal[row_index[key_j]] -= force_j * float(direction[component])  # Add the second-end tensile force component.
    truss_columns = np.array([element_column[element_id] for element_id in truss_ids], dtype=int)  # Address all portal-force columns.
    truss_matrix = operator[:, truss_columns].toarray()  # Extract the portal equilibrium operator.
    portal_demand = right_combined - endpoint_internal  # Form the free-node demand remaining after endpoint cable forces.
    portal_forces, _residuals, portal_rank, _singular = lstsq(truss_matrix, portal_demand, cond=None, lapack_driver="gelsy")  # Recover the best portal forces.
    endpoint_residual = endpoint_internal + truss_matrix @ portal_forces - right_combined  # Evaluate the endpoint-force equilibrium residual.
    endpoint_relative = float(np.linalg.norm(endpoint_residual) / max(np.linalg.norm(right_combined), 1.0e-30))  # Normalize the endpoint-force residual.
    mean_force = np.array([float(model["iniforce"][element_id]["axial_kN"]) for element_id in tenstr_ids], dtype=float)  # Read the stored mean cable forces for a parallel audit.
    mean_columns = np.array([element_column[element_id] for element_id in tenstr_ids], dtype=int)  # Address the cable equilibrium columns.
    mean_demand = right_combined - operator[:, mean_columns] @ mean_force  # Form the portal demand after stored mean cable forces.
    mean_portal, _mean_residuals, mean_portal_rank, _mean_singular = lstsq(truss_matrix, mean_demand, cond=None, lapack_driver="gelsy")  # Recover the best portal forces for the mean-force representation.
    mean_residual = operator[:, mean_columns] @ mean_force + truss_matrix @ mean_portal - right_combined  # Evaluate the stored mean-force equilibrium residual.
    mean_relative = float(np.linalg.norm(mean_residual) / max(np.linalg.norm(right_combined), 1.0e-30))  # Normalize the stored mean-force residual.
    largest = np.argsort(np.abs(endpoint_residual))[::-1][:30]  # Identify the thirty largest free-equilibrium residual components.
    largest_rows = [{"node_id": int(row_keys[index][0]), "component": "X" if row_keys[index][1] == 0 else "Z", "residual_kN": float(endpoint_residual[index]), "external_kN": float(-right_combined[index])} for index in largest]  # Record the largest residual locations.
    summary = {"source_sha256": model["source"]["sha256"], "endpoint_force_relative_residual": endpoint_relative, "mean_iniforce_relative_residual": mean_relative, "portal_rank_endpoint_case": int(portal_rank), "portal_rank_mean_case": int(mean_portal_rank), "portal_force_endpoint_min_kN": float(np.min(portal_forces)), "portal_force_endpoint_max_kN": float(np.max(portal_forces)), "largest_endpoint_residual_rows": largest_rows}  # Assemble the endpoint-force audit summary.
    (OUT / "endpoint_force_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the endpoint-force audit file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete audit into the workflow log.
    return 0  # Report successful audit execution.


if __name__ == "__main__":  # Execute only when invoked as a program.
    raise SystemExit(main())  # Return the program status to the operating system.
