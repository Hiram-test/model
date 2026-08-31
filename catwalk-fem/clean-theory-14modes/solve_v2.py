from __future__ import annotations  # Enable stable modern annotations for the clean solver wrapper.
import json  # Serialize the revised calculation receipts and summaries.
import math  # Evaluate gravity-based mass and geometry relations.
import os  # Record the exact GitHub commit identity in frozen results.
from pathlib import Path  # Resolve the isolated solver and result directories.
import numpy as np  # Perform vector, matrix, and norm operations.
from scipy.optimize import lsq_linear  # Solve the bounded inverse-equilibrium system.
from scipy.sparse import coo_matrix, csr_matrix, diags, vstack  # Assemble sparse equilibrium and mass-correction matrices.
import solve as base  # Reuse the already-audited topology, tangent, eigen, classification, and plotting implementation.
OUT = Path(__file__).resolve().parent / "results"  # Use the same isolated result directory as the base solver.
OUT.mkdir(parents=True, exist_ok=True)  # Create the result directory before any output is written.
TOP_ROPE_WEIGHT_NPM = 6.0 * base.MU_ROPE * base.G  # Compute the six explicit gantry-rope self-weight per formed metre.
STATIC_TOLERANCE = 5.0e-3  # Preserve the original inverse-equilibrium acceptance threshold without relaxation.
def inverse_static_v2(model: dict, floor_nodes: list[int], floor_elements: list[int], top_nodes: list[int], top_elements: list[int]) -> dict:  # Reconstruct prestress from formed geometry and the actual applied dead-load inputs.
    downpull = [728, 729]  # Retain both documented downpull links as explicit tension members.
    portals = [int(element_id) for element_id in model["groups"]["门架"]["elems"]]  # Retain all seventy-one aggregate portal links.
    bars = list(floor_elements) + downpull + list(top_elements) + portals  # Form the complete two-dimensional aggregate static network.
    node_ids = sorted({int(model["elems"][element_id]["n1"]) for element_id in bars} | {int(model["elems"][element_id]["n2"]) for element_id in bars})  # Collect every node participating in equilibrium.
    node_row = {node_id: index for index, node_id in enumerate(node_ids)}  # Map each physical node to its two equilibrium rows.
    loads = {node_id: np.zeros(2) for node_id in node_ids}  # Initialize longitudinal and vertical external loads in kilonewtons.
    floor_selfweight_kN = 0.0  # Accumulate the aggregate lower-system self-weight for audit.
    for element_id in floor_elements:  # Traverse every aggregate lower-catwalk segment.
        element = model["elems"][element_id]  # Retrieve the current segment endpoints.
        node_i = int(element["n1"])  # Read the first physical node identifier.
        node_j = int(element["n2"])  # Read the second physical node identifier.
        formed_length = float(np.linalg.norm(base.xyz(model, node_j) - base.xyz(model, node_i)))  # Measure the actual formed segment length used by element self-weight.
        weight = base.Q_FLOOR * formed_length * 1.0e-3  # Convert the independent 2.766 kN/m lower-system weight to kilonewtons on formed length.
        loads[node_i][1] -= 0.5 * weight  # Apply half of the segment self-weight to the first node.
        loads[node_j][1] -= 0.5 * weight  # Apply half of the segment self-weight to the second node.
        floor_selfweight_kN += weight  # Add the current segment contribution to the audit total.
    top_selfweight_kN = 0.0  # Accumulate six-gantry-rope self-weight for audit.
    for element_id in top_elements:  # Traverse every aggregate gantry-rope segment.
        element = model["elems"][element_id]  # Retrieve the current segment endpoints.
        node_i = int(element["n1"])  # Read the first physical node identifier.
        node_j = int(element["n2"])  # Read the second physical node identifier.
        formed_length = float(np.linalg.norm(base.xyz(model, node_j) - base.xyz(model, node_i)))  # Measure the actual formed segment length.
        weight = TOP_ROPE_WEIGHT_NPM * formed_length * 1.0e-3  # Convert the six physical rope self-weight to kilonewtons.
        loads[node_i][1] -= 0.5 * weight  # Apply half of the segment self-weight to the first node.
        loads[node_j][1] -= 0.5 * weight  # Apply half of the segment self-weight to the second node.
        top_selfweight_kN += weight  # Add the current segment contribution to the audit total.
    secondary_fx_kN = 0.0  # Accumulate the explicit second-stage longitudinal load input for audit.
    secondary_fz_kN = 0.0  # Accumulate the explicit second-stage vertical load input for audit.
    secondary_rows_used = 0  # Count second-stage load records that lie on the complete static network.
    for record in model["conload_erqi"]:  # Traverse the MCT second-stage nodal-load input block without reading any internal force result.
        node_id = int(record["nid"])  # Normalize the loaded node identifier.
        if node_id not in loads:  # Ignore records outside the selected complete rope-frame static network.
            continue  # Continue to the next explicit load record.
        fx_kN = float(record["fx_kN"])  # Read the prescribed longitudinal external load component.
        fz_kN = float(record["fz_kN"])  # Read the prescribed vertical external load component.
        loads[node_id][0] += fx_kN  # Add the prescribed longitudinal load to nodal equilibrium.
        loads[node_id][1] += fz_kN  # Add the prescribed vertical load to nodal equilibrium.
        secondary_fx_kN += fx_kN  # Accumulate the longitudinal input-load audit total.
        secondary_fz_kN += fz_kN  # Accumulate the vertical input-load audit total.
        secondary_rows_used += 1  # Count the applied second-stage load row.
    constrained_x: set[int] = set()  # Collect nodes that may supply longitudinal reactions.
    constrained_z: set[int] = set()  # Collect nodes that may supply vertical reactions.
    for constraint in model["constraints"]:  # Traverse only the explicit MCT restraint topology.
        code = str(constraint["dof"])  # Read the six-character restraint code.
        for node_id in constraint["nodes"]:  # Traverse every node named by the restraint record.
            node_id = int(node_id)  # Normalize the restrained node identifier.
            if code[0] == "1":  # Test whether longitudinal translation is restrained.
                constrained_x.add(node_id)  # Permit a longitudinal reaction unknown at this node.
            if code[2] == "1":  # Test whether vertical translation is restrained.
                constrained_z.add(node_id)  # Permit a vertical reaction unknown at this node.
    reactions = [(node_id, 0) for node_id in sorted(constrained_x & set(node_ids))] + [(node_id, 1) for node_id in sorted(constrained_z & set(node_ids))]  # Enumerate all admissible support reactions.
    unknowns = len(bars) + len(reactions)  # Count member-force and reaction unknowns in the inverse problem.
    rows: list[int] = []  # Initialize sparse equilibrium row indices.
    cols: list[int] = []  # Initialize sparse equilibrium column indices.
    vals: list[float] = []  # Initialize sparse equilibrium coefficients.
    for column, element_id in enumerate(bars):  # Assemble the direction cosines of every aggregate member.
        element = model["elems"][element_id]  # Retrieve the current member endpoints.
        node_i = int(element["n1"])  # Read the first endpoint identifier.
        node_j = int(element["n2"])  # Read the second endpoint identifier.
        delta = base.xyz(model, node_j)[[0, 2]] - base.xyz(model, node_i)[[0, 2]]  # Evaluate the member direction in the MCT x-z plane.
        unit = delta / np.linalg.norm(delta)  # Normalize the physical member direction.
        for component in range(2):  # Assemble longitudinal and vertical force equilibrium.
            rows += [2 * node_row[node_i] + component, 2 * node_row[node_j] + component]  # Address both endpoint equilibrium rows.
            cols += [column, column]  # Address the current member-force unknown at both endpoints.
            vals += [float(unit[component]), float(-unit[component])]  # Apply equal and opposite tensile-force directions.
    for offset, (node_id, component) in enumerate(reactions):  # Assemble every admissible support-reaction unknown.
        rows.append(2 * node_row[node_id] + component)  # Address the corresponding physical equilibrium row.
        cols.append(len(bars) + offset)  # Address the current reaction unknown column.
        vals.append(1.0)  # Apply a unit reaction coefficient.
    equilibrium = coo_matrix((vals, (rows, cols)), shape=(2 * len(node_ids), unknowns)).tocsr()  # Build the exact sparse physical equilibrium operator.
    right_hand = -np.concatenate([loads[node_id] for node_id in node_ids])  # Move all prescribed external loads to the equilibrium right-hand side.
    floor_ref = base.reference_tensions(model, floor_elements, ["北边跨", "主跨", "南边跨", "南辅跨"], base.Q_FLOOR)  # Build only a weak geometry-derived floor self-stress selector.
    top_ref = base.reference_tensions(model, top_elements, ["门架索北边跨", "门架索主跨", "门架索南边跨", "门架索南辅跨"], TOP_ROPE_WEIGHT_NPM)  # Build only a weak geometry-derived gantry-rope self-stress selector.
    prior = np.zeros(unknowns)  # Initialize the weak branch-selection vector.
    for column, element_id in enumerate(bars):  # Assign a non-target prior scale to each member force.
        if element_id in floor_ref:  # Test floor-chain membership.
            prior[column] = floor_ref[element_id]  # Use the curvature-derived floor reference tension.
        elif element_id in top_ref:  # Test gantry-chain membership.
            prior[column] = top_ref[element_id]  # Use the curvature-derived gantry-rope reference tension.
        elif element_id in downpull:  # Test downpull membership.
            prior[column] = 1500.0  # Use a positive non-target scale only to select a tensile self-stress branch.
        else:  # Handle aggregate portal links.
            prior[column] = 0.0  # Avoid injecting an assumed portal compression into physical equilibrium.
    index_by_element = {element_id: index for index, element_id in enumerate(bars)}  # Map each member identifier to its force column.
    smooth_blocks: list[csr_matrix] = []  # Collect weak continuity regularizers for the two continuous rope chains.
    smooth_right: list[np.ndarray] = []  # Collect the corresponding zero target jumps.
    for ordered in (floor_elements, top_elements):  # Regularize only physically continuous rope segments.
        s_rows: list[int] = []  # Initialize regularizer row indices.
        s_cols: list[int] = []  # Initialize regularizer column indices.
        s_vals: list[float] = []  # Initialize regularizer coefficients.
        for row, (left, right) in enumerate(zip(ordered[:-1], ordered[1:])):  # Traverse adjacent rope segments.
            s_rows += [row, row]  # Address the current continuity row twice.
            s_cols += [index_by_element[left], index_by_element[right]]  # Address adjacent force unknowns.
            s_vals += [2.0e-4, -2.0e-4]  # Penalize only abrupt segment-to-segment force jumps.
        smooth_blocks.append(coo_matrix((s_vals, (s_rows, s_cols)), shape=(len(ordered) - 1, unknowns)).tocsr())  # Build the sparse continuity block.
        smooth_right.append(np.zeros(len(ordered) - 1))  # Set the desired artificial jump to zero.
    prior_weight = 1.0e-6  # Keep the branch-selection prior much weaker than physical equilibrium.
    system = vstack([equilibrium] + smooth_blocks + [diags(np.full(unknowns, prior_weight))], format="csr")  # Form the bounded inverse system without changing equilibrium weights.
    system_right = np.concatenate([right_hand] + smooth_right + [prior_weight * prior])  # Form the augmented right-hand side.
    lower = np.full(unknowns, -np.inf)  # Initialize unbounded lower limits for reactions and portal forces.
    upper = np.full(unknowns, np.inf)  # Initialize unbounded upper limits for every inverse unknown.
    for column, element_id in enumerate(bars):  # Apply the physical tension-only condition to every TENSTR element.
        if str(model["elems"][element_id]["type"]).upper() == "TENSTR":  # Identify rope and downpull tension members.
            lower[column] = 1.0e-3  # Require strictly positive tension in kilonewtons.
    solution = lsq_linear(system, system_right, bounds=(lower, upper), tol=1.0e-11, lsmr_tol=1.0e-11, max_iter=8000)  # Solve the constrained inverse equilibrium to tight numerical tolerance.
    residual = equilibrium @ solution.x - right_hand  # Evaluate only the unregularized physical equilibrium residual.
    forces = {str(element_id): float(solution.x[column]) for column, element_id in enumerate(bars)}  # Store all aggregate member forces in kilonewtons.
    cable_values = [forces[str(element_id)] for element_id in bars if str(model["elems"][element_id]["type"]).upper() == "TENSTR"]  # Collect all tension-member forces for physical checks.
    residual_norm = float(np.linalg.norm(residual) / max(np.linalg.norm(right_hand), 1.0e-30))  # Normalize the physical equilibrium residual by the prescribed load norm.
    return {"success": bool(solution.success), "message": str(solution.message), "equilibrium_relative_residual": residual_norm, "min_cable_force_kN": float(min(cable_values)), "max_cable_force_kN": float(max(cable_values)), "active_tension_lower_bounds": int(sum(value <= 1.001e-3 for value in cable_values)), "equations": int(equilibrium.shape[0]), "unknowns": int(equilibrium.shape[1]), "floor_selfweight_kN": float(floor_selfweight_kN), "top_selfweight_kN": float(top_selfweight_kN), "secondary_fx_kN": float(secondary_fx_kN), "secondary_fz_kN": float(secondary_fz_kN), "secondary_rows_used": int(secondary_rows_used), "force_kN": forces}  # Return the fully auditable inverse-static state.
def add_nodal_mass(rows: list[int], cols: list[int], vals: list[float], dofs: np.ndarray, mass_value: float, width: float) -> None:  # Add one four-DOF section mass while preserving translational mass and roll inertia.
    if mass_value <= 0.0:  # Reject non-positive residual masses before sparse assembly.
        return  # Leave the global mass matrix unchanged for this node.
    metric = np.diag([1.0, 1.0, 1.0, width**2 / 12.0])  # Preserve three translations and a uniform-width roll radius of gyration.
    base.add(rows, cols, vals, dofs, mass_value * metric)  # Scatter the nodal generalized mass into sparse triplets.
def assemble_v2(model: dict, static: dict, floor_nodes: list[int], floor_elements: list[int], top_nodes: list[int], top_elements: list[int]) -> dict:  # Add missing applied-load mass while preserving the base explicit 44-rope, portal, and passage dynamics.
    system = base.assemble(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Build the already-audited explicit rope-frame-passage tangent model first.
    correction_rows: list[int] = []  # Initialize sparse mass-correction row indices.
    correction_cols: list[int] = []  # Initialize sparse mass-correction column indices.
    correction_vals: list[float] = []  # Initialize sparse mass-correction coefficients.
    floor_set = set(floor_nodes)  # Build the floor-node membership set for secondary-mass placement.
    top_set = set(top_nodes)  # Build the gantry-node membership set for secondary-mass placement.
    floor_length_mass_added = 0.0  # Accumulate the formed-length correction to the lower-system base mass.
    for catwalk in range(2):  # Apply the same verified lower-system mass correction to both physical catwalks.
        for element_id in floor_elements:  # Traverse every lower-system segment.
            element = model["elems"][element_id]  # Retrieve the current aggregate floor segment.
            node_i = int(element["n1"])  # Read its first section node.
            node_j = int(element["n2"])  # Read its second section node.
            point_i = base.xyz(model, node_i)  # Read the formed first section position.
            point_j = base.xyz(model, node_j)  # Read the formed second section position.
            formed_length = float(np.linalg.norm(point_j - point_i))  # Measure the actual formed segment length.
            projected_length = abs(float(point_j[0] - point_i[0]))  # Measure the horizontal projection used by the base residual-mass expression.
            explicit_floor_mass = 16.0 * base.MU_ROPE * formed_length  # Reconstruct the sixteen explicit floor-rope mass on this segment.
            handrail_mass = (2.0 * 5.42 + 4.0 * 1.67) * formed_length  # Reconstruct the six equivalent handrail line masses on this segment.
            old_target = base.Q_FLOOR / base.G * projected_length  # Reconstruct the base solver's horizontal-projection target mass.
            old_total = max(old_target, explicit_floor_mass + handrail_mass)  # Reconstruct the actual total mass already present after the base max operation.
            new_target = base.Q_FLOOR / base.G * formed_length  # Define the physically consistent formed-length lower-system mass.
            correction_mass = max(new_target - old_total, 0.0)  # Add only the missing mass needed to reach the formed-length target.
            section_dofs = np.concatenate([system["floor_dofs"][(catwalk, node_i)], system["floor_dofs"][(catwalk, node_j)]])  # Address both section nodes on the current physical catwalk.
            base.add(correction_rows, correction_cols, correction_vals, section_dofs, base.deck_mass_matrix(correction_mass))  # Add the consistent formed-length residual mass correction.
            floor_length_mass_added += correction_mass  # Accumulate the correction mass for audit.
    explicit_secondary_by_node: dict[int, float] = {}  # Track secondary masses already represented explicitly in each single-catwalk MCT load path.
    for portal in system["portals"]:  # Traverse all mapped portal stations.
        floor_node = int(portal["floor_node"])  # Read the portal lower section node.
        top_node = int(portal["top_node"])  # Read the portal upper section node.
        explicit_secondary_by_node[floor_node] = explicit_secondary_by_node.get(floor_node, 0.0) + 0.35 * base.M_PORTAL  # Account for the explicit lower portal mass already in each catwalk.
        explicit_secondary_by_node[top_node] = explicit_secondary_by_node.get(top_node, 0.0) + 0.65 * base.M_PORTAL  # Account for the explicit upper portal mass already in each catwalk.
    for passage in system["passages"]:  # Traverse all twenty-one explicit full-passage equivalents.
        node_id = int(passage["node"])  # Read the associated single-line MCT floor station.
        explicit_secondary_by_node[node_id] = explicit_secondary_by_node.get(node_id, 0.0) + 0.5 * base.M_PASSAGE  # Account for one catwalk's half share of the already explicit full passage mass.
    residual_secondary_single_catwalk = 0.0  # Accumulate secondary nodal mass still missing from one physical catwalk after explicit portal and passage subtraction.
    secondary_mass_input_single_catwalk = 0.0  # Accumulate the total prescribed second-stage downward-load mass for one catwalk.
    explicit_mass_excess_nodes: list[dict] = []  # Record nodes where the chosen explicit equivalent exceeds the local MCT second-stage load mass.
    for record in model["conload_erqi"]:  # Traverse the prescribed second-stage nodal-load input block.
        node_id = int(record["nid"])  # Normalize the loaded node identifier.
        downward_kN = max(-float(record["fz_kN"]), 0.0)  # Retain only downward dead-load magnitude for dynamic mass conversion.
        if downward_kN < 1.0e-4:  # Ignore numerical sentinel loads that carry no physical mass significance.
            continue  # Continue to the next prescribed load record.
        prescribed_mass = downward_kN * 1.0e3 / base.G  # Convert the vertical dead-load input to equivalent physical mass in kilograms.
        secondary_mass_input_single_catwalk += prescribed_mass  # Accumulate the total prescribed secondary mass.
        explicit_mass = explicit_secondary_by_node.get(node_id, 0.0)  # Read portal or passage mass already represented explicitly at this station.
        residual_mass = prescribed_mass - explicit_mass  # Compute the secondary mass not yet represented by explicit dynamic substructures.
        if residual_mass < -1.0e-6:  # Detect a local explicit-mass excess instead of silently creating negative mass.
            explicit_mass_excess_nodes.append({"node": node_id, "prescribed_mass_kg": prescribed_mass, "explicit_mass_kg": explicit_mass, "excess_kg": -residual_mass})  # Preserve the mismatch as an auditable modelling warning.
        residual_mass = max(residual_mass, 0.0)  # Prevent nonphysical negative residual mass in the global mass matrix.
        residual_secondary_single_catwalk += residual_mass  # Accumulate the remaining secondary mass for audit.
        for catwalk in range(2):  # Duplicate the single-catwalk prescribed load model onto both physical catwalks.
            if node_id in floor_set:  # Place lower-system residual secondary mass on the floor section.
                add_nodal_mass(correction_rows, correction_cols, correction_vals, system["floor_dofs"][(catwalk, node_id)], residual_mass, base.FLOOR_WIDTH)  # Preserve floor translation and width-based roll inertia.
            elif node_id in top_set:  # Place upper-system residual secondary mass on the gantry section.
                add_nodal_mass(correction_rows, correction_cols, correction_vals, system["top_dofs"][(catwalk, node_id)], residual_mass, base.GANTRY_WIDTH)  # Preserve top translation and gantry-width roll inertia.
    correction = coo_matrix((correction_vals, (correction_rows, correction_cols)), shape=(system["dof_count"], system["dof_count"])).tocsr()  # Build the complete positive-semidefinite dynamic mass correction.
    mass_full = (system["M_full"] + correction).tocsr()  # Add formed-length and second-stage residual mass to the explicit model exactly once.
    system["M_full"] = mass_full  # Replace the full mass matrix with the corrected physical matrix.
    system["M"] = mass_full[system["free"]][:, system["free"]].tocsr()  # Rebuild the constrained generalized mass matrix on the unchanged free-DOF set.
    system["mass_audit_v2"] = {"floor_formed_length_correction_two_catwalks_kg": float(floor_length_mass_added), "secondary_input_single_catwalk_kg": float(secondary_mass_input_single_catwalk), "secondary_residual_single_catwalk_kg": float(residual_secondary_single_catwalk), "secondary_residual_two_catwalks_kg": float(2.0 * residual_secondary_single_catwalk), "explicit_mass_excess_nodes": explicit_mass_excess_nodes}  # Record every dynamic-mass correction and local mismatch.
    return system  # Return the corrected tangent model for eigenanalysis.
def main() -> int:  # Execute the revised clean calculation without using MCT internal forces or target frequencies.
    model = base.load_mct()  # Parse and SHA-check the original MCT source body.
    floor_nodes, floor_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-catwalk aggregate chain.
    top_nodes, top_elements = base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope aggregate chain.
    static = inverse_static_v2(model, floor_nodes, floor_elements, top_nodes, top_elements)  # Reconstruct prestress from geometry, supports, self-weight, and explicit second-stage load input.
    if static["equilibrium_relative_residual"] > STATIC_TOLERANCE:  # Enforce the unchanged physical equilibrium compatibility threshold.
        raise RuntimeError(f"Inverse equilibrium residual is {static['equilibrium_relative_residual']:.6e}")  # Reject a still-incompatible static state without relaxing acceptance.
    system = assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble explicit ropes, frames, passages, constraints, and non-duplicated prescribed masses.
    frequencies, vectors, residuals, checks = base.solve_eigen(system)  # Solve and verify the symmetric generalized eigenproblem.
    raw, selected, classification_meta = base.classify(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Classify physical families before loading any external target frequency.
    assumptions = [{"name": "MCT use", "value": "formed coordinates, topology, groups, restraint topology, SELFWEIGHT definition, and explicit second-stage CONLOAD input only; INIFORCE, INI-EFORCE, and modal results excluded"}, {"name": "inverse statics", "value": "prestress reconstructed by bounded nodal equilibrium on the prescribed formed geometry; acceptance residual <= 0.005"}, {"name": "floor ropes", "value": "16 explicit ropes per catwalk; one smart rope at each inner local position, mirror-symmetric globally"}, {"name": "gantry ropes", "value": "6 explicit ropes per catwalk, represented as left and right triplets across 7.46 m"}, {"name": "secondary floor system", "value": "2.766 kN/m lower-system self-weight on formed length, decomposed into explicit floor ropes, handrail masses, and residual width-distributed mass"}, {"name": "second-stage mass", "value": "MCT prescribed second-stage vertical loads converted to mass only after subtracting explicit portal and half-passage masses at the same single-catwalk nodes"}, {"name": "portals", "value": "71 per catwalk; 1429.98 kg each; 161x161x8 equivalent two-column frame"}, {"name": "passages", "value": "21 full multi-port equivalents; 10130 kg each; three phi152x6 chords; longitudinal bracing stiffness factor 0.03"}, {"name": "supports", "value": "current MCT restraint topology interpreted as the fixed-contact linearization state"}, {"name": "classification", "value": "L/V/T energy, main-span sine order, parity, and span localization only; no target frequency"}]  # Record every decisive modelling assumption explicitly.
    frozen = {"kind": "clean_theory_44_rope_catwalk_frozen_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "source_mct_bytes": model["source"]["bytes"], "target_frequency_used": False, "mct_internal_force_used": False, "frequency_reproduced": False, "not_attach_ta1": True, "topology": {"explicit_floor_ropes": 32, "explicit_gantry_ropes": 12, "explicit_ropes_total": 44, "portals": 142, "passages": 21, "floor_chain_nodes": len(floor_nodes), "floor_chain_elements": len(floor_elements), "top_chain_nodes": len(top_nodes), "top_chain_elements": len(top_elements)}, "assumptions": assumptions, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": checks, "mass_audit_v2": system["mass_audit_v2"], "smart_index_zero_based": system["smart_index"], "portal_map": system["portals"], "passage_parameters": system["passages"], "raw_modes": raw, "classified_14": selected, "classification_meta": {key: value for key, value in classification_meta.items() if key != "selected_shapes"}}  # Form the target-free frozen result object.
    frozen_path = OUT / "frozen_results.json"  # Define the target-free frozen result path.
    base.dump(frozen_path, frozen)  # Write frequencies and classifications before any benchmark frequency is loaded.
    frozen_sha = base.sha(frozen_path)  # Freeze the target-free calculation identity with SHA-256.
    base.write_csv(raw, selected, [])  # Write the raw spectrum and fourteen-family classification without external targets.
    base.plots(raw, selected, [], classification_meta)  # Write spectrum and selected physical mode-shape plots without target values.
    summary = {"kind": "clean_theory_44_rope_catwalk_summary_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha, "identified_count": sum(1 for item in selected.values() if "frequency_hz" in item), "inverse_static": frozen["inverse_static"], "matrix_checks": checks, "mass_audit_v2": system["mass_audit_v2"], "target_frequency_used": False, "mct_internal_force_used": False, "frequency_reproduced": False}  # Build the concise target-free solver summary.
    base.dump(OUT / "summary.json", summary)  # Write the concise solver summary.
    base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Write every explicit rope's recovered unstressed length and force.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every primary target-free result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2))  # Print the concise calculation receipt into the workflow log.
    return 0  # Return successful completion.
if __name__ == "__main__":  # Execute only when the revised solver is invoked directly.
    raise SystemExit(main())  # Run the complete revised clean calculation.
