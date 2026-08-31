from __future__ import annotations  # Enable stable modern annotations.
import csv  # Write auditable tabular results.
import hashlib  # Freeze results before external comparison.
import json  # Write machine-readable evidence files.
import math  # Evaluate geometric and section formulas.
import os  # Record the exact GitHub commit identity.
import sys  # Load the existing MCT parser module.
from collections import defaultdict  # Build chain adjacency maps.
from pathlib import Path  # Handle repository and result paths.
import matplotlib  # Configure non-interactive plotting.
matplotlib.use("Agg")  # Use the headless renderer on GitHub Actions.
import matplotlib.pyplot as plt  # Create spectrum and mode-shape plots.
import numpy as np  # Perform matrix and vector calculations.
from scipy.optimize import lsq_linear  # Solve bounded inverse equilibrium.
from scipy.sparse import coo_matrix, csr_matrix, diags, vstack  # Assemble sparse global matrices.
from scipy.sparse.linalg import eigsh  # Solve the symmetric generalized eigenproblem.
CATWALK_FEM = Path(__file__).resolve().parents[1]  # Resolve the catwalk-fem directory.
MCT_DIR = CATWALK_FEM / "mct-from-zero"  # Locate the verified MCT parser and source.
sys.path.insert(0, str(MCT_DIR))  # Add the parser directory to Python imports.
from parse_mct import load_mct  # type: ignore  # Parse only the original MCT body.
OUT = Path(__file__).resolve().parent / "results"  # Define the isolated result directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the result directory idempotently.
G = 9.80665  # Use one gravity value throughout statics and mass conversion.
E_ROPE = 120.0e9  # Use the documented rope design modulus in pascals.
E_STEEL = 206.0e9  # Use the documented structural-steel modulus in pascals.
A_NORMAL = 1400.42e-6  # Convert normal floor-rope metallic area to square metres.
A_SMART = 1292.45e-6  # Convert smart floor-rope metallic area to square metres.
MU_ROPE = 12.038  # Use the documented phi-50 rope line mass in kilograms per metre.
FLOOR_Y = np.array([-2.67, -2.41, -2.15, -1.89, -1.63, -1.37, -1.11, -0.85, 0.85, 1.11, 1.37, 1.63, 1.89, 2.15, 2.41, 2.67])  # Retain all sixteen floor-rope offsets.
FLOOR_WIDTH = 5.60  # Use the documented effective floor-beam width.
GANTRY_WIDTH = 7.46  # Use the documented portal top-beam width.
GANTRY_Y = np.array([-GANTRY_WIDTH / 2.0] * 3 + [GANTRY_WIDTH / 2.0] * 3)  # Retain six gantry ropes as left and right triplets.
CAT_CENTRES = (-21.45, 21.45)  # Place the two catwalk centrelines 42.90 metres apart.
Q_FLOOR = 2766.0  # Use the independent complete lower-catwalk dead load in newtons per metre.
M_PORTAL = 1123.0 + 306.98  # Combine the current portal and bottom-beam mass package.
M_PASSAGE = 10130.0  # Use the independent full-passage design mass package.
PASSAGE_LENGTH = 49.655  # Use the current transverse-passage overall length.
PASSAGE_HEIGHT = 1.75  # Use the documented inverted-triangle height.
PIPE_D = 0.152  # Use the main-chord outer diameter.
PIPE_T = 0.006  # Use the main-chord wall thickness.
PORTAL_B = 0.161  # Use the MCT portal-equivalent box outer size.
PORTAL_T = 0.008  # Use the MCT portal-equivalent box wall size.
BETA_H = np.array([0.0, 2.82, 5.63, 8.75, 12.44, 15.68, 18.89, -20.24, -16.99, -13.36, -10.78, -7.39])  # Retain H1-H12 local slopes.
LABEL_ORDER = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]  # Fix only the reporting order.
def dump(path: Path, value: object) -> None:  # Write deterministic UTF-8 JSON.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Serialize with stable key ordering.
def sha(path: Path) -> str:  # Compute a file SHA-256 digest.
    digest = hashlib.sha256()  # Initialize the hash accumulator.
    with path.open("rb") as handle:  # Read the file as bytes.
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # Stream one-megabyte chunks.
            digest.update(chunk)  # Add the current chunk to the digest.
    return digest.hexdigest()  # Return the hexadecimal digest.
def xyz(model: dict, node_id: int) -> np.ndarray:  # Read one MCT node in metres.
    node = model["nodes"][node_id]  # Retrieve the parsed node record.
    return 1.0e-3 * np.array([float(node["x"]), float(node["y"]), float(node["z"])])  # Convert millimetres to metres.
def chain(model: dict, element_ids: list[int]) -> tuple[list[int], list[int]]:  # Recover an ordered unbranched element chain.
    adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)  # Initialize node adjacency.
    for element_id in element_ids:  # Traverse every requested element.
        element = model["elems"][element_id]  # Retrieve its endpoints.
        node_i = int(element["n1"])  # Convert the first endpoint to an integer.
        node_j = int(element["n2"])  # Convert the second endpoint to an integer.
        adjacency[node_i].append((node_j, element_id))  # Add the forward adjacency entry.
        adjacency[node_j].append((node_i, element_id))  # Add the reverse adjacency entry.
    endpoints = [node_id for node_id, links in adjacency.items() if len(links) == 1]  # Identify the two physical chain ends.
    if len(endpoints) != 2:  # Reject a broken or branched topology.
        raise RuntimeError(f"Expected two chain ends, found {len(endpoints)}")  # Report the topological inconsistency.
    current = min(endpoints, key=lambda node_id: xyz(model, node_id)[0])  # Start at the smaller longitudinal coordinate.
    previous = -1  # Initialize the preceding-node sentinel.
    ordered_nodes = [current]  # Start the ordered node list.
    ordered_elements: list[int] = []  # Start the ordered element list.
    while True:  # Walk until the opposite physical end is reached.
        candidates = [(other, element_id) for other, element_id in adjacency[current] if other != previous]  # Exclude the preceding edge.
        if not candidates:  # Detect the terminal node.
            break  # Finish the chain walk.
        if len(candidates) != 1:  # Reject any interior branch.
            raise RuntimeError(f"Chain branch at node {current}")  # Report the exact branch node.
        other, element_id = candidates[0]  # Take the unique forward edge.
        ordered_elements.append(element_id)  # Append the current physical element.
        ordered_nodes.append(other)  # Append its next node.
        previous, current = current, other  # Advance the walk state.
    if len(ordered_elements) != len(element_ids):  # Ensure no disconnected element was omitted.
        raise RuntimeError("Disconnected elements in chain")  # Reject an incomplete chain.
    return ordered_nodes, ordered_elements  # Return ordered physical topology.
def tributary(x_values: np.ndarray) -> np.ndarray:  # Compute nodal longitudinal control lengths.
    weights = np.zeros_like(x_values)  # Initialize the control-length vector.
    weights[0] = 0.5 * abs(x_values[1] - x_values[0])  # Assign the first half interval.
    weights[-1] = 0.5 * abs(x_values[-1] - x_values[-2])  # Assign the last half interval.
    weights[1:-1] = 0.5 * np.abs(x_values[2:] - x_values[:-2])  # Assign interior half-neighbour sums.
    return weights  # Return longitudinal integration weights.
def reference_tensions(model: dict, chain_ids: list[int], group_names: list[str], load_npm: float) -> dict[int, float]:  # Build a geometry-only tension reference.
    output: dict[int, float] = {}  # Initialize element reference forces in kilonewtons.
    chain_set = set(chain_ids)  # Build an efficient membership set.
    for group_name in group_names:  # Process each physical span independently.
        group = model["groups"][group_name]  # Retrieve the span group.
        points = np.array([[xyz(model, int(node_id))[0], xyz(model, int(node_id))[2]] for node_id in group["nodes"]])  # Extract its formed x-z line.
        points = points[np.argsort(points[:, 0])]  # Sort the formed line longitudinally.
        centre = float(np.mean(points[:, 0]))  # Centre the fit for numerical conditioning.
        coefficients = np.polyfit(points[:, 0] - centre, points[:, 1], 2)  # Fit the span curvature without target data.
        curvature = max(abs(2.0 * float(coefficients[0])), 1.0e-7)  # Obtain a positive curvature magnitude.
        horizontal = load_npm / curvature  # Apply H*z''=q to form a reference horizontal component.
        for element_id in group["elems"]:  # Traverse the elements assigned to this span.
            element_id = int(element_id)  # Normalize the element identifier.
            if element_id not in chain_set:  # Ignore non-chain group members.
                continue  # Continue with the next group element.
            element = model["elems"][element_id]  # Retrieve the chain element.
            delta = xyz(model, int(element["n2"])) - xyz(model, int(element["n1"]))  # Evaluate its formed direction.
            output[element_id] = 1.0e-3 * horizontal * float(np.linalg.norm(delta) / max(abs(delta[0]), 1.0e-12))  # Convert its full reference tension to kilonewtons.
    return output  # Return independent reference forces.
def inverse_static(model: dict, floor_nodes: list[int], floor_elements: list[int], top_nodes: list[int], top_elements: list[int]) -> dict:  # Solve prestress on the prescribed formed geometry.
    downpull = [728, 729]  # Retain both documented downpull links.
    portals = [int(element_id) for element_id in model["groups"]["门架"]["elems"]]  # Retain all seventy-one portal links.
    bars = list(floor_elements) + downpull + list(top_elements) + portals  # Form the complete aggregate static network.
    node_ids = sorted({int(model["elems"][element_id]["n1"]) for element_id in bars} | {int(model["elems"][element_id]["n2"]) for element_id in bars})  # Collect every network node.
    node_row = {node_id: index for index, node_id in enumerate(node_ids)}  # Map each node to its equilibrium row block.
    loads = {node_id: np.zeros(2) for node_id in node_ids}  # Initialize longitudinal and vertical nodal loads in kilonewtons.
    for element_id in floor_elements:  # Apply the independent complete floor-system dead load.
        element = model["elems"][element_id]  # Retrieve the current floor segment.
        node_i = int(element["n1"])  # Read its first node.
        node_j = int(element["n2"])  # Read its second node.
        weight = Q_FLOOR * abs(xyz(model, node_j)[0] - xyz(model, node_i)[0]) * 1.0e-3  # Integrate load over horizontal projection.
        loads[node_i][1] -= 0.5 * weight  # Distribute half to the first node.
        loads[node_j][1] -= 0.5 * weight  # Distribute half to the second node.
    for element_id in top_elements:  # Apply the self-weight of all six gantry ropes.
        element = model["elems"][element_id]  # Retrieve the current top-rope segment.
        node_i = int(element["n1"])  # Read its first node.
        node_j = int(element["n2"])  # Read its second node.
        weight = 6.0 * MU_ROPE * G * np.linalg.norm(xyz(model, node_j) - xyz(model, node_i)) * 1.0e-3  # Integrate six-rope self-weight.
        loads[node_i][1] -= 0.5 * weight  # Distribute half to the first node.
        loads[node_j][1] -= 0.5 * weight  # Distribute half to the second node.
    for element_id in portals:  # Apply each portal-frame dead load at its two physical levels.
        element = model["elems"][element_id]  # Retrieve the portal link.
        node_i = int(element["n1"])  # Read its first end.
        node_j = int(element["n2"])  # Read its second end.
        weight = M_PORTAL * G * 1.0e-3  # Convert portal mass to kilonewtons.
        loads[node_i][1] -= 0.5 * weight  # Put half at the lower or first endpoint.
        loads[node_j][1] -= 0.5 * weight  # Put half at the upper or second endpoint.
    for node_id in model["groups"]["横向通道节点"]["nodes"]:  # Apply half of every passage to each catwalk.
        node_id = int(node_id)  # Normalize the passage node identifier.
        if node_id in loads:  # Confirm that the node belongs to the static network.
            loads[node_id][1] -= 0.5 * M_PASSAGE * G * 1.0e-3  # Apply the physical half-passage weight.
    constrained_x: set[int] = set()  # Collect nodes carrying longitudinal reactions.
    constrained_z: set[int] = set()  # Collect nodes carrying vertical reactions.
    for constraint in model["constraints"]:  # Read only the MCT support topology.
        code = str(constraint["dof"])  # Read the six-digit restraint code.
        for node_id in constraint["nodes"]:  # Traverse its constrained nodes.
            node_id = int(node_id)  # Normalize the node identifier.
            if code[0] == "1":  # Test longitudinal restraint.
                constrained_x.add(node_id)  # Add a longitudinal reaction unknown.
            if code[2] == "1":  # Test vertical restraint.
                constrained_z.add(node_id)  # Add a vertical reaction unknown.
    reactions = [(node_id, 0) for node_id in sorted(constrained_x & set(node_ids))] + [(node_id, 1) for node_id in sorted(constrained_z & set(node_ids))]  # Enumerate physical reaction unknowns.
    unknowns = len(bars) + len(reactions)  # Count bar forces and support reactions.
    rows: list[int] = []  # Initialize equilibrium row triplets.
    cols: list[int] = []  # Initialize equilibrium column triplets.
    vals: list[float] = []  # Initialize equilibrium coefficients.
    for column, element_id in enumerate(bars):  # Assemble every bar direction into nodal equilibrium.
        element = model["elems"][element_id]  # Retrieve the current bar.
        node_i = int(element["n1"])  # Read its first node.
        node_j = int(element["n2"])  # Read its second node.
        delta = xyz(model, node_j)[[0, 2]] - xyz(model, node_i)[[0, 2]]  # Evaluate its x-z direction.
        unit = delta / np.linalg.norm(delta)  # Normalize the direction vector.
        for component in range(2):  # Assemble longitudinal and vertical components.
            rows += [2 * node_row[node_i] + component, 2 * node_row[node_j] + component]  # Add both endpoint rows.
            cols += [column, column]  # Add the current force column twice.
            vals += [float(unit[component]), float(-unit[component])]  # Apply equal and opposite tensile forces.
    for offset, (node_id, component) in enumerate(reactions):  # Assemble all support reactions.
        rows.append(2 * node_row[node_id] + component)  # Add the physical equilibrium row.
        cols.append(len(bars) + offset)  # Add the reaction unknown column.
        vals.append(1.0)  # Apply a unit reaction coefficient.
    equilibrium = coo_matrix((vals, (rows, cols)), shape=(2 * len(node_ids), unknowns)).tocsr()  # Build the sparse equilibrium operator.
    right_hand = -np.concatenate([loads[node_id] for node_id in node_ids])  # Move external loads to the right-hand side.
    floor_ref = reference_tensions(model, floor_elements, ["北边跨", "主跨", "南边跨", "南辅跨"], Q_FLOOR)  # Build floor references from formed curvature.
    top_length = max(xyz(model, top_nodes[-1])[0] - xyz(model, top_nodes[0])[0], 1.0)  # Evaluate the top-rope longitudinal extent.
    top_load = 6.0 * MU_ROPE * G + 0.5 * M_PORTAL * G * len(portals) / top_length  # Include rope and upper portal weight in the top reference.
    top_ref = reference_tensions(model, top_elements, ["门架索北边跨", "门架索主跨", "门架索南边跨", "门架索南辅跨"], top_load)  # Build top references from formed curvature.
    prior = np.zeros(unknowns)  # Initialize the weak self-stress selector.
    for column, element_id in enumerate(bars):  # Assign independent reference levels.
        if element_id in floor_ref:  # Test floor-chain membership.
            prior[column] = floor_ref[element_id]  # Use its curvature-derived reference.
        elif element_id in top_ref:  # Test top-chain membership.
            prior[column] = top_ref[element_id]  # Use its curvature-derived reference.
        elif element_id in downpull:  # Test downpull membership.
            prior[column] = 1500.0  # Use a positive scale only to select the self-stress branch.
        else:  # Handle portal links.
            prior[column] = -0.5 * M_PORTAL * G * 1.0e-3  # Use the portal half-weight compression scale.
    index_by_element = {element_id: index for index, element_id in enumerate(bars)}  # Map element IDs to force columns.
    smooth_blocks: list[csr_matrix] = []  # Collect weak continuity regularizers.
    smooth_right: list[np.ndarray] = []  # Collect their zero right-hand sides.
    for ordered in (floor_elements, top_elements):  # Regularize only continuous rope chains.
        s_rows: list[int] = []  # Initialize regularizer row indices.
        s_cols: list[int] = []  # Initialize regularizer column indices.
        s_vals: list[float] = []  # Initialize regularizer coefficients.
        for row, (left, right) in enumerate(zip(ordered[:-1], ordered[1:])):  # Traverse adjacent physical rope segments.
            s_rows += [row, row]  # Add the current continuity row twice.
            s_cols += [index_by_element[left], index_by_element[right]]  # Address the adjacent force unknowns.
            s_vals += [2.0e-4, -2.0e-4]  # Penalize only nonphysical segment-to-segment jumps.
        smooth_blocks.append(coo_matrix((s_vals, (s_rows, s_cols)), shape=(len(ordered) - 1, unknowns)).tocsr())  # Build the chain continuity block.
        smooth_right.append(np.zeros(len(ordered) - 1))  # Set its target jump to zero.
    prior_weight = 1.0e-6  # Keep the geometry-derived prior much weaker than equilibrium.
    system = vstack([equilibrium] + smooth_blocks + [diags(np.full(unknowns, prior_weight))], format="csr")  # Form the augmented inverse system.
    system_right = np.concatenate([right_hand] + smooth_right + [prior_weight * prior])  # Form the augmented right-hand side.
    lower = np.full(unknowns, -np.inf)  # Initialize unbounded lower limits.
    upper = np.full(unknowns, np.inf)  # Initialize unbounded upper limits.
    for column, element_id in enumerate(bars):  # Apply tension-only conditions.
        if str(model["elems"][element_id]["type"]).upper() == "TENSTR":  # Identify rope and downpull elements.
            lower[column] = 1.0e-3  # Require strictly positive tension in kilonewtons.
    solution = lsq_linear(system, system_right, bounds=(lower, upper), tol=1.0e-11, lsmr_tol=1.0e-11, max_iter=4000)  # Solve the constrained inverse equilibrium.
    residual = equilibrium @ solution.x - right_hand  # Evaluate only the physical equilibrium residual.
    forces = {str(element_id): float(solution.x[column]) for column, element_id in enumerate(bars)}  # Store aggregate bar forces in kilonewtons.
    cable_values = [forces[str(element_id)] for element_id in bars if str(model["elems"][element_id]["type"]).upper() == "TENSTR"]  # Collect all rope forces.
    return {"success": bool(solution.success), "message": str(solution.message), "equilibrium_relative_residual": float(np.linalg.norm(residual) / max(np.linalg.norm(right_hand), 1.0e-30)), "min_cable_force_kN": float(min(cable_values)), "max_cable_force_kN": float(max(cable_values)), "active_tension_lower_bounds": int(sum(value <= 1.001e-3 for value in cable_values)), "equations": int(equilibrium.shape[0]), "unknowns": int(equilibrium.shape[1]), "force_kN": forces}  # Return the inverse-static state.
def point_map(y_offset: float, z_offset: float = 0.0) -> np.ndarray:  # Map section translation and roll to one rope point.
    return np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, -z_offset], [0.0, 0.0, 1.0, y_offset]])  # Preserve rigid cross-section kinematics.
def rope_matrices(point_i: np.ndarray, point_j: np.ndarray, area: float, force: float, line_mass: float) -> tuple[np.ndarray, np.ndarray, float]:  # Form one prestressed three-dimensional rope element.
    delta = point_j - point_i  # Evaluate the current element vector.
    length = float(np.linalg.norm(delta))  # Evaluate the current element length.
    direction = delta / length  # Normalize the element direction.
    axial = E_ROPE * area  # Evaluate EA in newtons.
    unstressed = length / (1.0 + force / axial)  # Recover the linear-elastic unstressed length.
    operator = axial / unstressed * np.outer(direction, direction) + force / length * (np.eye(3) - np.outer(direction, direction))  # Add material and geometric tangent stiffness.
    stiffness = np.block([[operator, -operator], [-operator, operator]])  # Form the six-translation tangent matrix.
    mass_total = line_mass * length  # Evaluate the rope-segment mass.
    mass = mass_total / 6.0 * np.block([[2.0 * np.eye(3), np.eye(3)], [np.eye(3), 2.0 * np.eye(3)]])  # Form its consistent mass matrix.
    return stiffness, mass, unstressed  # Return stiffness, mass, and recovered unstressed length.
def add(rows: list[int], cols: list[int], vals: list[float], dofs: np.ndarray, matrix: np.ndarray) -> None:  # Scatter one dense local matrix into sparse triplets.
    for local_i, global_i in enumerate(dofs):  # Traverse local rows.
        for local_j, global_j in enumerate(dofs):  # Traverse local columns.
            value = float(matrix[local_i, local_j])  # Read the local coefficient.
            if value != 0.0:  # Omit exact zeros.
                rows.append(int(global_i))  # Append the global row.
                cols.append(int(global_j))  # Append the global column.
                vals.append(value)  # Append the coefficient.
def line_mass_matrix(total_mass: float, mapping: np.ndarray) -> np.ndarray:  # Form an eccentric two-section consistent mass matrix.
    metric = mapping.T @ mapping  # Convert point translation kinetic energy to section coordinates.
    return total_mass / 6.0 * np.block([[2.0 * metric, metric], [metric, 2.0 * metric]])  # Return the eight-DOF consistent matrix.
def deck_mass_matrix(total_mass: float) -> np.ndarray:  # Form the residual floor-system mass matrix.
    metric = np.diag([1.0, 1.0, 1.0, FLOOR_WIDTH**2 / 12.0])  # Preserve translation and uniform-width roll inertia.
    return total_mass / 6.0 * np.block([[2.0 * metric, metric], [metric, 2.0 * metric]])  # Return the eight-DOF consistent matrix.
def portal_matrices(height: float) -> tuple[np.ndarray, np.ndarray]:  # Form one objective equivalent portal frame.
    height = max(abs(height), 3.0)  # Guard only against degenerate zero height.
    inner = PORTAL_B - 2.0 * PORTAL_T  # Evaluate the box inner size.
    area = PORTAL_B**2 - inner**2  # Evaluate one column area.
    inertia = (PORTAL_B**4 - inner**4) / 12.0  # Evaluate one column bending inertia.
    sway = 24.0 * E_STEEL * inertia / height**3  # Evaluate two-column fixed-end sway stiffness.
    vertical = 2.0 * E_STEEL * area / height  # Evaluate two-column vertical stiffness.
    roll = E_STEEL * area * GANTRY_WIDTH**2 / (2.0 * height) + 8.0 * E_STEEL * inertia / height  # Evaluate differential-column roll stiffness.
    transform = np.zeros((4, 8))  # Initialize relative-deformation mapping.
    transform[0, [0, 4]] = [-1.0, 1.0]  # Define longitudinal relative translation.
    transform[1, [1, 3, 5, 7]] = [-1.0, height / 2.0, 1.0, height / 2.0]  # Define objective lateral sway.
    transform[2, [2, 6]] = [-1.0, 1.0]  # Define vertical relative translation.
    transform[3, [3, 7]] = [-1.0, 1.0]  # Define relative roll.
    stiffness = transform.T @ np.diag([sway, sway, vertical, roll]) @ transform  # Derive the portal stiffness from strain energy.
    mass = np.zeros((8, 8))  # Initialize the portal mass matrix.
    for y_offset in (-FLOOR_WIDTH / 2.0, FLOOR_WIDTH / 2.0):  # Distribute lower mass to both bottom corners.
        mapping = point_map(y_offset)  # Build the bottom-corner kinematic map.
        mass[:4, :4] += 0.5 * 0.35 * M_PORTAL * (mapping.T @ mapping)  # Preserve lower mass and roll inertia.
    for y_offset in (-GANTRY_WIDTH / 2.0, GANTRY_WIDTH / 2.0):  # Distribute upper mass to both top corners.
        mapping = point_map(y_offset)  # Build the top-corner kinematic map.
        mass[4:, 4:] += 0.5 * 0.65 * M_PORTAL * (mapping.T @ mapping)  # Preserve upper mass and roll inertia.
    return stiffness, mass  # Return the equivalent portal matrices.
def passage_matrices(beta_deg: float) -> tuple[np.ndarray, np.ndarray, dict]:  # Form one inclined multi-port passage equivalent.
    beta = math.radians(beta_deg)  # Convert the local slope to radians.
    cosine = math.cos(beta)  # Evaluate the rotation cosine.
    sine = math.sin(beta)  # Evaluate the rotation sine.
    pipe_area = math.pi * (PIPE_D**2 - (PIPE_D - 2.0 * PIPE_T) ** 2) / 4.0  # Evaluate one main-chord area.
    area = 3.0 * pipe_area  # Retain three main chords in the axial equivalent.
    top_z = PASSAGE_HEIGHT / 3.0  # Place the two top chords about the section centroid.
    bottom_z = -2.0 * PASSAGE_HEIGHT / 3.0  # Place the bottom chord about the section centroid.
    inertia = pipe_area * (2.0 * top_z**2 + bottom_z**2)  # Evaluate vertical bending inertia by chord-area separation.
    local_k = np.zeros((8, 8))  # Initialize the two-port local stiffness.
    axial_y = E_STEEL * area / PASSAGE_LENGTH  # Evaluate transverse axial stiffness.
    axial_x = 0.03 * axial_y  # Represent diagonal-bracing longitudinal stiffness as an explicit assumption.
    for dof, stiffness_value in ((0, axial_x), (1, axial_y)):  # Assemble relative longitudinal and transverse springs.
        local_k[dof, dof] += stiffness_value  # Add the first-end diagonal term.
        local_k[dof, dof + 4] -= stiffness_value  # Add the first-to-second coupling.
        local_k[dof + 4, dof] -= stiffness_value  # Add the symmetric coupling.
        local_k[dof + 4, dof + 4] += stiffness_value  # Add the second-end diagonal term.
    length = PASSAGE_LENGTH  # Abbreviate the passage length.
    bending = E_STEEL * inertia / length**3 * np.array([[12.0, 6.0 * length, -12.0, 6.0 * length], [6.0 * length, 4.0 * length**2, -6.0 * length, 2.0 * length**2], [-12.0, -6.0 * length, 12.0, -6.0 * length], [6.0 * length, 2.0 * length**2, -6.0 * length, 4.0 * length**2]])  # Form Euler vertical-bending stiffness.
    bend_dofs = [2, 3, 6, 7]  # Address vertical translation and roll at both ends.
    local_k[np.ix_(bend_dofs, bend_dofs)] += bending  # Add passage bending stiffness.
    local_m = np.zeros((8, 8))  # Initialize the passage mass matrix.
    translation = M_PASSAGE / 6.0 * np.array([[2.0, 1.0], [1.0, 2.0]])  # Form two-end consistent translation mass.
    for dof in (0, 1):  # Apply it to local longitudinal and transverse directions.
        local_m[np.ix_([dof, dof + 4], [dof, dof + 4])] += translation  # Add the selected translation mass block.
    bending_mass = M_PASSAGE / 420.0 * np.array([[156.0, 22.0 * length, 54.0, -13.0 * length], [22.0 * length, 4.0 * length**2, 13.0 * length, -3.0 * length**2], [54.0, 13.0 * length, 156.0, -22.0 * length], [-13.0 * length, -3.0 * length**2, -22.0 * length, 4.0 * length**2]])  # Form Euler consistent bending mass.
    local_m[np.ix_(bend_dofs, bend_dofs)] += bending_mass  # Add the vertical bending mass block.
    port = np.array([[cosine, 0.0, sine, 0.0], [0.0, 1.0, 0.0, 0.0], [-sine, 0.0, cosine, 0.0], [0.0, 0.0, 0.0, cosine]])  # Rotate each four-DOF port into the inclined local frame.
    transform = np.block([[port, np.zeros((4, 4))], [np.zeros((4, 4)), port]])  # Form the two-port block rotation.
    return transform.T @ local_k @ transform, transform.T @ local_m @ transform, {"beta_deg": beta_deg, "area_m2": area, "inertia_m4": inertia, "longitudinal_factor": 0.03}  # Return global passage matrices and parameters.
def assemble(model: dict, static: dict, floor_nodes: list[int], floor_elements: list[int], top_nodes: list[int], top_elements: list[int]) -> dict:  # Assemble the complete two-catwalk tangent model.
    floor_dofs: dict[tuple[int, int], np.ndarray] = {}  # Map every floor section to four global DOFs.
    top_dofs: dict[tuple[int, int], np.ndarray] = {}  # Map every gantry-rope section to four global DOFs.
    cursor = 0  # Initialize the global DOF counter.
    for catwalk in range(2):  # Process the two catwalks independently.
        for node_id in floor_nodes:  # Allocate all floor-section DOFs.
            floor_dofs[(catwalk, node_id)] = np.arange(cursor, cursor + 4)  # Assign ux, uy, uz, and roll.
            cursor += 4  # Advance the DOF counter.
        for node_id in top_nodes:  # Allocate all gantry-section DOFs.
            top_dofs[(catwalk, node_id)] = np.arange(cursor, cursor + 4)  # Assign ux, uy, uz, and roll.
            cursor += 4  # Advance the DOF counter.
    k_rows: list[int] = []  # Initialize stiffness rows.
    k_cols: list[int] = []  # Initialize stiffness columns.
    k_vals: list[float] = []  # Initialize stiffness values.
    m_rows: list[int] = []  # Initialize mass rows.
    m_cols: list[int] = []  # Initialize mass columns.
    m_vals: list[float] = []  # Initialize mass values.
    force_map = {int(key): 1.0e3 * float(value) for key, value in static["force_kN"].items()}  # Convert aggregate static forces to newtons.
    smart_index = {0: 8, 1: 7}  # Put each smart rope at the inner local rope position.
    recovered: list[dict] = []  # Store every explicit rope's recovered unstressed length.
    for catwalk in range(2):  # Assemble sixteen explicit floor ropes per catwalk.
        areas = np.full(16, A_NORMAL)  # Initialize fifteen normal-rope areas.
        areas[smart_index[catwalk]] = A_SMART  # Insert one smart-rope area.
        total_area = float(np.sum(areas))  # Evaluate the bundle area for force splitting.
        centre_y = CAT_CENTRES[catwalk]  # Read the current catwalk centreline.
        for element_id in floor_elements:  # Traverse all floor-chain segments.
            element = model["elems"][element_id]  # Retrieve the aggregate segment.
            node_i = int(element["n1"])  # Read its first section node.
            node_j = int(element["n2"])  # Read its second section node.
            base_i = xyz(model, node_i)  # Read the formed start point.
            base_j = xyz(model, node_j)  # Read the formed end point.
            section_dofs = np.concatenate([floor_dofs[(catwalk, node_i)], floor_dofs[(catwalk, node_j)]])  # Address both floor sections.
            explicit_mass = 0.0  # Initialize explicit floor-rope mass on this segment.
            for rope_number, (y_offset, area) in enumerate(zip(FLOOR_Y, areas), start=1):  # Assemble all sixteen ropes individually.
                point_i = np.array([base_i[0], centre_y + y_offset, base_i[2]])  # Place the first physical rope point.
                point_j = np.array([base_j[0], centre_y + y_offset, base_j[2]])  # Place the second physical rope point.
                rope_force = force_map[element_id] * float(area / total_area)  # Split aggregate force by EA under equal strain.
                stiffness6, mass6, unstressed = rope_matrices(point_i, point_j, float(area), rope_force, MU_ROPE)  # Evaluate this rope's tangent matrices.
                mapping = point_map(float(y_offset))  # Map section motion to this rope point.
                transform = np.block([[mapping, np.zeros((3, 4))], [np.zeros((3, 4)), mapping]])  # Form the two-section kinematic transform.
                add(k_rows, k_cols, k_vals, section_dofs, transform.T @ stiffness6 @ transform)  # Assemble this rope's stiffness.
                add(m_rows, m_cols, m_vals, section_dofs, transform.T @ mass6 @ transform)  # Assemble this rope's mass.
                explicit_mass += MU_ROPE * np.linalg.norm(point_j - point_i)  # Accumulate the physical rope mass.
                recovered.append({"catwalk": catwalk, "family": "floor", "rope": rope_number, "aggregate_element": element_id, "force_N": rope_force, "unstressed_length_m": unstressed})  # Record its recovered state.
            formed_length = float(np.linalg.norm(base_j - base_i))  # Evaluate the formed segment length.
            handrails = [(-2.89, 1.20, 5.42), (2.89, 1.20, 5.42), (-2.89, 0.80, 1.67), (2.89, 0.80, 1.67), (-2.89, 0.40, 1.67), (2.89, 0.40, 1.67)]  # Define six equivalent handrail mass lines.
            handrail_mass = 0.0  # Initialize equivalent handrail mass.
            for y_offset, z_offset, line_mass in handrails:  # Assemble every eccentric handrail mass line.
                current_mass = line_mass * formed_length  # Evaluate the current line-segment mass.
                handrail_mass += current_mass  # Accumulate handrail mass.
                add(m_rows, m_cols, m_vals, section_dofs, line_mass_matrix(current_mass, point_map(y_offset, z_offset)))  # Preserve its offset kinetic energy.
            target_mass = Q_FLOOR / G * abs(base_j[0] - base_i[0])  # Convert the complete horizontal dead load to dynamic mass.
            residual_mass = max(target_mass - explicit_mass - handrail_mass, 0.0)  # Close the remaining deck, beam, mesh, and attachment mass.
            add(m_rows, m_cols, m_vals, section_dofs, deck_mass_matrix(residual_mass))  # Preserve residual total mass and roll inertia.
    top_area = 8402.979737976504e-6 / 6.0  # Split the aggregate gantry-rope area into six explicit ropes.
    for catwalk in range(2):  # Assemble six explicit gantry ropes per catwalk.
        centre_y = CAT_CENTRES[catwalk]  # Read the current catwalk centreline.
        for element_id in top_elements:  # Traverse all gantry-chain segments.
            element = model["elems"][element_id]  # Retrieve the aggregate segment.
            node_i = int(element["n1"])  # Read its first section node.
            node_j = int(element["n2"])  # Read its second section node.
            base_i = xyz(model, node_i)  # Read the formed start point.
            base_j = xyz(model, node_j)  # Read the formed end point.
            section_dofs = np.concatenate([top_dofs[(catwalk, node_i)], top_dofs[(catwalk, node_j)]])  # Address both gantry sections.
            for rope_number, y_offset in enumerate(GANTRY_Y, start=1):  # Assemble all six gantry ropes individually.
                point_i = np.array([base_i[0], centre_y + y_offset, base_i[2]])  # Place the first physical gantry-rope point.
                point_j = np.array([base_j[0], centre_y + y_offset, base_j[2]])  # Place the second physical gantry-rope point.
                rope_force = force_map[element_id] / 6.0  # Split the aggregate force equally among identical ropes.
                stiffness6, mass6, unstressed = rope_matrices(point_i, point_j, top_area, rope_force, MU_ROPE)  # Evaluate the current rope tangent matrices.
                mapping = point_map(float(y_offset))  # Map section motion to the current rope point.
                transform = np.block([[mapping, np.zeros((3, 4))], [np.zeros((3, 4)), mapping]])  # Form the two-section transform.
                add(k_rows, k_cols, k_vals, section_dofs, transform.T @ stiffness6 @ transform)  # Assemble the gantry-rope stiffness.
                add(m_rows, m_cols, m_vals, section_dofs, transform.T @ mass6 @ transform)  # Assemble the gantry-rope mass.
                recovered.append({"catwalk": catwalk, "family": "gantry", "rope": rope_number, "aggregate_element": element_id, "force_N": rope_force, "unstressed_length_m": unstressed})  # Record its recovered state.
    floor_set = set(floor_nodes)  # Build the floor-node membership set.
    top_set = set(top_nodes)  # Build the gantry-node membership set.
    portal_records: list[dict] = []  # Store portal geometry and mappings.
    for element_id in model["groups"]["门架"]["elems"]:  # Traverse all seventy-one portals.
        element_id = int(element_id)  # Normalize the element ID.
        element = model["elems"][element_id]  # Retrieve its two levels.
        endpoints = [int(element["n1"]), int(element["n2"])]  # Read both endpoint IDs.
        floor_candidates = [node_id for node_id in endpoints if node_id in floor_set]  # Identify the lower floor section.
        top_candidates = [node_id for node_id in endpoints if node_id in top_set]  # Identify the upper gantry section.
        if len(floor_candidates) != 1 or len(top_candidates) != 1:  # Verify the physical portal topology.
            raise RuntimeError(f"Cannot map portal {element_id}")  # Stop on an ambiguous portal.
        floor_node = floor_candidates[0]  # Select its floor section.
        top_node = top_candidates[0]  # Select its gantry section.
        height = xyz(model, top_node)[2] - xyz(model, floor_node)[2]  # Evaluate its actual formed height.
        stiffness8, mass8 = portal_matrices(height)  # Form its equivalent frame matrices.
        for catwalk in range(2):  # Assemble one independent portal in each catwalk.
            section_dofs = np.concatenate([floor_dofs[(catwalk, floor_node)], top_dofs[(catwalk, top_node)]])  # Address lower and upper ports.
            add(k_rows, k_cols, k_vals, section_dofs, stiffness8)  # Assemble portal stiffness.
            add(m_rows, m_cols, m_vals, section_dofs, mass8)  # Assemble portal mass.
        portal_records.append({"element": element_id, "floor_node": floor_node, "top_node": top_node, "height_m": height})  # Record the physical portal map.
    for element_id in (728, 729):  # Traverse both downpull links.
        element = model["elems"][element_id]  # Retrieve the current downpull link.
        endpoints = [int(element["n1"]), int(element["n2"])]  # Read its two endpoint IDs.
        floor_node = next(node_id for node_id in endpoints if node_id in floor_set)  # Identify the floor attachment.
        anchor_node = next(node_id for node_id in endpoints if node_id != floor_node)  # Identify the fixed downpull anchor.
        aggregate_area = 15.0 * A_NORMAL + A_SMART  # Preserve the complete sixteen-rope metallic area.
        for catwalk in range(2):  # Assemble a symmetric pair in each catwalk.
            for y_offset in (-FLOOR_WIDTH / 2.0, FLOOR_WIDTH / 2.0):  # Retain left and right downpull eccentricity.
                floor_point = np.array([xyz(model, floor_node)[0], CAT_CENTRES[catwalk] + y_offset, xyz(model, floor_node)[2]])  # Place the floor attachment point.
                anchor_point = np.array([xyz(model, anchor_node)[0], CAT_CENTRES[catwalk] + y_offset, xyz(model, anchor_node)[2]])  # Place the fixed anchor point.
                stiffness6, _, _ = rope_matrices(anchor_point, floor_point, 0.5 * aggregate_area, 0.5 * force_map[element_id], 0.0)  # Form one half-width downpull tangent.
                mapping = point_map(y_offset)  # Map floor-section motion to the attachment point.
                add(k_rows, k_cols, k_vals, floor_dofs[(catwalk, floor_node)], mapping.T @ stiffness6[3:, 3:] @ mapping)  # Assemble the fixed-anchor tangent block.
    floor_position = {node_id: index for index, node_id in enumerate(floor_nodes)}  # Map ordered floor nodes for slope evaluation.
    passage_nodes = sorted([int(node_id) for node_id in model["groups"]["横向通道节点"]["nodes"]], key=lambda node_id: xyz(model, node_id)[0])  # Sort all twenty-one passage stations.
    passage_records: list[dict] = []  # Store every passage equivalent.
    for station, node_id in enumerate(passage_nodes):  # Assemble every passage station.
        if station < 9:  # Handle P01-P09 without detailed local-angle drawings.
            index = floor_position[node_id]  # Locate the station on the formed floor chain.
            left = xyz(model, floor_nodes[max(index - 1, 0)])  # Read its left neighbour.
            right = xyz(model, floor_nodes[min(index + 1, len(floor_nodes) - 1)])  # Read its right neighbour.
            beta = math.degrees(math.atan2(right[2] - left[2], right[0] - left[0]))  # Derive the local slope from formed geometry.
            name = f"P{station + 1:02d}"  # Assign the audit station name.
        else:  # Handle H1-H12 with documented local angles.
            beta = float(BETA_H[station - 9])  # Read the documented slope.
            name = f"H{station - 8}"  # Assign the documented station name.
        stiffness8, mass8, parameters = passage_matrices(beta)  # Form the inclined multi-port matrices.
        section_dofs = np.concatenate([floor_dofs[(0, node_id)], floor_dofs[(1, node_id)]])  # Address both physical catwalk ports.
        add(k_rows, k_cols, k_vals, section_dofs, stiffness8)  # Assemble passage stiffness.
        add(m_rows, m_cols, m_vals, section_dofs, mass8)  # Assemble passage mass exactly once.
        passage_records.append({"name": name, "node": node_id, "x_m": float(xyz(model, node_id)[0]), **parameters})  # Record station identity and equivalent parameters.
    stiffness_full = coo_matrix((k_vals, (k_rows, k_cols)), shape=(cursor, cursor)).tocsr()  # Build the complete tangent stiffness.
    mass_full = coo_matrix((m_vals, (m_rows, m_cols)), shape=(cursor, cursor)).tocsr()  # Build the complete consistent mass matrix.
    fixed: set[int] = set()  # Collect physically restrained generalized DOFs.
    for constraint in model["constraints"]:  # Reuse only the MCT support topology.
        code = str(constraint["dof"])  # Read its restraint code.
        for node_id in constraint["nodes"]:  # Traverse its physical nodes.
            node_id = int(node_id)  # Normalize the node ID.
            for catwalk in range(2):  # Apply the same topology to both independent catwalks.
                for dof_map in (floor_dofs, top_dofs):  # Test floor and gantry section maps.
                    if (catwalk, node_id) not in dof_map:  # Skip nodes absent from the selected section family.
                        continue  # Continue with the next section family.
                    block = dof_map[(catwalk, node_id)]  # Retrieve ux, uy, uz, and roll.
                    if code[0] == "1":  # Test longitudinal restraint.
                        fixed.add(int(block[0]))  # Restrain section ux.
                    if code[1] == "1":  # Test transverse restraint.
                        fixed.add(int(block[1]))  # Restrain section uy.
                    if code[2] == "1":  # Test vertical restraint.
                        fixed.add(int(block[2]))  # Restrain section uz.
                    if code[1] == "1" and code[2] == "1":  # Test whether all eccentric rope points are position-fixed.
                        fixed.add(int(block[3]))  # Restrain the corresponding section roll.
    free = np.array([degree for degree in range(cursor) if degree not in fixed], dtype=int)  # Enumerate all retained free DOFs.
    return {"K_full": stiffness_full, "M_full": mass_full, "K": stiffness_full[free][:, free].tocsr(), "M": mass_full[free][:, free].tocsr(), "free": free, "fixed": np.array(sorted(fixed)), "floor_dofs": floor_dofs, "top_dofs": top_dofs, "dof_count": cursor, "recovered": recovered, "portals": portal_records, "passages": passage_records, "smart_index": smart_index}  # Return the assembled physical model.
def solve_eigen(system: dict) -> tuple[np.ndarray, np.ndarray, list[float], dict]:  # Solve and verify low global modes.
    stiffness = system["K"]  # Read the constrained tangent stiffness.
    mass = system["M"]  # Read the constrained consistent mass matrix.
    asym_k = float(np.linalg.norm((stiffness - stiffness.T).data) / max(np.linalg.norm(stiffness.data), 1.0e-30))  # Measure stiffness asymmetry.
    asym_m = float(np.linalg.norm((mass - mass.T).data) / max(np.linalg.norm(mass.data), 1.0e-30))  # Measure mass asymmetry.
    shift = (2.0 * math.pi * 1.0e-5) ** 2  # Define a nonphysical numerical shift far below the target band.
    count = min(140, stiffness.shape[0] - 2)  # Keep the requested eigenspace smaller than the system.
    values, vectors = eigsh(stiffness + shift * mass, k=count, M=mass, sigma=0.0, which="LM", tol=1.0e-9, maxiter=20000)  # Solve near zero with symmetric shift-invert.
    values = values - shift  # Remove the numerical shift exactly.
    order = np.argsort(values)  # Sort eigenvalues in ascending order.
    values = np.asarray(values[order])  # Reorder the eigenvalues.
    vectors = np.asarray(vectors[:, order])  # Reorder the eigenvectors consistently.
    physical = values > (2.0 * math.pi * 1.0e-4) ** 2  # Remove numerical mechanisms below 0.0001 Hz.
    values = values[physical]  # Retain positive physical eigenvalues.
    vectors = vectors[:, physical]  # Retain their eigenvectors.
    frequencies = np.sqrt(values) / (2.0 * math.pi)  # Convert circular frequencies to hertz.
    residuals: list[float] = []  # Initialize normalized eigen-residuals.
    for column, value in enumerate(values):  # Verify every retained eigenpair.
        vector = vectors[:, column]  # Read the current eigenvector.
        residual = stiffness @ vector - value * (mass @ vector)  # Evaluate the generalized eigen-equation residual.
        scale = np.linalg.norm(stiffness @ vector) + abs(value) * np.linalg.norm(mass @ vector)  # Form a symmetric residual scale.
        residuals.append(float(np.linalg.norm(residual) / max(scale, 1.0e-30)))  # Store the normalized residual.
    checks = {"free_dofs": int(stiffness.shape[0]), "nnz_K": int(stiffness.nnz), "nnz_M": int(mass.nnz), "relative_asymmetry_K": asym_k, "relative_asymmetry_M": asym_m, "max_eigen_residual": float(max(residuals)), "numerical_shift_hz": 1.0e-5}  # Summarize matrix and eigenpair verification.
    return frequencies, vectors, residuals, checks  # Return verified eigenpairs and checks.
def correlation(left: np.ndarray, right: np.ndarray, weights: np.ndarray) -> float:  # Compute a weighted modal correlation.
    numerator = float(np.sum(weights * left * right))  # Evaluate the weighted inner product.
    denominator = math.sqrt(max(float(np.sum(weights * left**2) * np.sum(weights * right**2)), 1.0e-30))  # Evaluate weighted norms.
    return numerator / denominator  # Return the signed correlation.
def classify(model: dict, system: dict, floor_nodes: list[int], top_nodes: list[int], frequencies: np.ndarray, vectors: np.ndarray, residuals: list[float]) -> tuple[list[dict], dict[str, dict], dict]:  # Classify modes without target frequencies.
    floor_x = np.array([xyz(model, node_id)[0] for node_id in floor_nodes])  # Read ordered floor-section coordinates.
    floor_w = tributary(floor_x)  # Form floor-section longitudinal weights.
    top_x = np.array([xyz(model, node_id)[0] for node_id in top_nodes])  # Read ordered gantry-section coordinates.
    top_w = tributary(top_x)  # Form gantry-section longitudinal weights.
    spans = {"north": "北边跨", "main": "主跨", "south717": "南边跨", "south503": "南辅跨"}  # Declare physical span names.
    masks = {key: np.array([node_id in {int(item) for item in model["groups"][group]["nodes"]} for node_id in floor_nodes]) for key, group in spans.items()}  # Build span masks from MCT groups.
    main_mask = masks["main"]  # Select the main-span mask.
    main_x = floor_x[main_mask]  # Select main-span coordinates.
    main_w = floor_w[main_mask]  # Select main-span weights.
    main_mid = 0.5 * (float(np.min(main_x)) + float(np.max(main_x)))  # Evaluate the formed main-span midpoint.
    roll_radius = math.sqrt(float(np.mean(FLOOR_Y**2)))  # Convert roll to an equivalent rope-point displacement.
    raw: list[dict] = []  # Initialize physical metrics for all modes.
    shape_data: dict[int, dict] = {}  # Initialize mode-shape data for selected-report plots.
    for mode_index, frequency in enumerate(frequencies):  # Process every retained global mode.
        full = np.zeros(system["dof_count"])  # Reconstruct the full constrained vector.
        full[system["free"]] = vectors[:, mode_index]  # Insert the free eigenvector components.
        floor_fields: dict[int, dict[str, np.ndarray]] = {}  # Store each catwalk's floor fields.
        top_fields: dict[int, dict[str, np.ndarray]] = {}  # Store each catwalk's gantry fields.
        for catwalk in range(2):  # Extract both independent catwalks.
            floor_values = np.array([full[system["floor_dofs"][(catwalk, node_id)]] for node_id in floor_nodes])  # Read floor section DOFs.
            top_values = np.array([full[system["top_dofs"][(catwalk, node_id)]] for node_id in top_nodes])  # Read gantry section DOFs.
            floor_fields[catwalk] = {"L": floor_values[:, 1], "V": floor_values[:, 2], "T": roll_radius * floor_values[:, 3]}  # Define physical L, V, and T floor fields.
            top_fields[catwalk] = {"L": top_values[:, 1], "V": top_values[:, 2], "T": math.sqrt(float(np.mean(GANTRY_Y**2))) * top_values[:, 3]}  # Define corresponding gantry fields.
        energies = {family: float(sum(np.sum(floor_w * floor_fields[catwalk][family] ** 2) for catwalk in range(2))) for family in ("L", "V", "T")}  # Evaluate floor physical amplitudes.
        energy_total = max(sum(energies.values()), 1.0e-30)  # Form their total scale.
        family = max(energies, key=energies.get)  # Select the dominant physical family.
        confidence = float(energies[family] / energy_total)  # Quantify family purity.
        top_energy = float(sum(np.sum(top_w * top_fields[catwalk][kind] ** 2) for catwalk in range(2) for kind in ("L", "V", "T")))  # Evaluate gantry-section amplitude.
        floor_part = float(energy_total / max(energy_total + top_energy, 1.0e-30))  # Quantify floor-system participation.
        fields = [floor_fields[0][family], floor_fields[1][family]]  # Read both catwalk fields in the dominant family.
        total_span = float(sum(np.sum(floor_w * field**2) for field in fields))  # Evaluate full-line amplitude.
        span_fraction = {key: float(sum(np.sum(floor_w[mask] * field[mask] ** 2) for field in fields) / max(total_span, 1.0e-30)) for key, mask in masks.items()}  # Evaluate four-span localization.
        numerator = 0.0  # Initialize longitudinal reflection correlation.
        norm_a = 0.0  # Initialize original main-span norm.
        norm_b = 0.0  # Initialize reflected main-span norm.
        projections = np.zeros(8)  # Initialize fixed-end sine-order projections.
        for catwalk in range(2):  # Accumulate metrics from both catwalks.
            values = floor_fields[catwalk][family][main_mask]  # Read the current main-span field.
            reflected = np.interp(2.0 * main_mid - main_x, main_x, values)  # Reflect it about the main-span midpoint.
            numerator += float(np.sum(main_w * values * reflected))  # Accumulate the reflection inner product.
            norm_a += float(np.sum(main_w * values**2))  # Accumulate the original norm.
            norm_b += float(np.sum(main_w * reflected**2))  # Accumulate the reflected norm.
            xi = (main_x - float(np.min(main_x))) / (float(np.max(main_x)) - float(np.min(main_x)))  # Normalize main-span position.
            for order_index in range(1, 9):  # Test the first eight longitudinal orders.
                basis = np.sin(order_index * math.pi * xi)  # Form the current fixed-end sine basis.
                value = float(np.sum(main_w * values * basis))  # Evaluate its projection numerator.
                scale = max(float(np.sum(main_w * values**2) * np.sum(main_w * basis**2)), 1.0e-30)  # Form the normalized projection scale.
                projections[order_index - 1] += value * value / scale  # Accumulate squared projection from both catwalks.
        parity = float(numerator / math.sqrt(max(norm_a * norm_b, 1.0e-30)))  # Evaluate signed main-span parity.
        order_value = int(np.argmax(projections) + 1)  # Select the strongest longitudinal order.
        order_score = float(projections[order_value - 1] / 2.0)  # Normalize two-catwalk projection strength.
        same_sign = correlation(fields[0], fields[1], floor_w)  # Evaluate same-global-sign versus opposite-global-sign motion.
        nodal = floor_w * (fields[0] ** 2 + fields[1] ** 2)  # Evaluate longitudinal nodal amplitude density.
        localization = float(np.max(nodal) / max(np.sum(nodal), 1.0e-30))  # Detect single-node local modes.
        record = {"mode": mode_index + 1, "frequency_hz": float(frequency), "residual": float(residuals[mode_index]), "family": family, "family_confidence": confidence, "floor_participation": floor_part, "parity": parity, "parity_label": "S" if parity >= 0.0 else "A", "longitudinal_order": order_value, "order_score": order_score, "same_global_sign_correlation": same_sign, "span_fraction": span_fraction, "localization": localization, "family_fraction": {key: float(value / energy_total) for key, value in energies.items()}}  # Store the complete physical classification metrics.
        raw.append(record)  # Append the current mode record.
        shape_data[mode_index + 1] = {"x_m": floor_x.tolist(), "U": {key: value.tolist() for key, value in floor_fields[0].items()}, "D": {key: value.tolist() for key, value in floor_fields[1].items()}}  # Preserve its two-catwalk fields.
    selected: dict[str, dict] = {}  # Initialize canonical fourteen-family selections.
    used: set[int] = set()  # Prevent one numerical vector from receiving two labels.
    for label, span_key in (("SIDE1", "south717"), ("SIDE2", "north"), ("SIDE3", "south503")):  # Select the three predeclared side-span fundamentals.
        candidates = [record for record in raw if record["mode"] not in used and record["floor_participation"] >= 0.35 and record["span_fraction"][span_key] >= 0.45 and record["frequency_hz"] <= 0.50 and record["localization"] <= 0.20]  # Apply only physical locality and global-mode filters.
        if candidates:  # Test whether a physical candidate exists.
            choice = min(candidates, key=lambda record: (record["frequency_hz"], -record["span_fraction"][span_key]))  # Take the lowest physical mode in that span.
            selected[label] = {**choice, "selection_rule": f"lowest global mode with {span_key} fraction >= 0.45"}  # Store its independent selection rule.
            used.add(int(choice["mode"]))  # Mark the numerical mode as consumed.
        else:  # Handle a missing physical side mode.
            selected[label] = {"status": "unidentified", "selection_rule": f"no global mode with {span_key} fraction >= 0.45"}  # Report no identification rather than frequency matching.
    specifications = {"LS1": ("L", 1), "LA1": ("L", 2), "LS2": ("L", 3), "LA2": ("L", 4), "VA1": ("V", 2), "VS1": ("V", 3), "VA2": ("V", 4), "VS2": ("V", 5), "TA1": ("T", 2), "TS1": ("T", 3), "TS2": ("T", 5)}  # Declare family labels by physics and longitudinal order.
    for label, (family, order_value) in specifications.items():  # Select every main-span family.
        parity_label = "S" if order_value % 2 == 1 else "A"  # Derive fixed-end midpoint parity from order.
        candidates = [record for record in raw if record["mode"] not in used and record["family"] == family and record["longitudinal_order"] == order_value and record["parity_label"] == parity_label and record["span_fraction"]["main"] >= 0.45 and record["floor_participation"] >= 0.30 and record["frequency_hz"] <= 0.60 and record["localization"] <= 0.20]  # Apply target-independent physical filters.
        if candidates:  # Test whether strict physical candidates exist.
            choice = max(candidates, key=lambda record: (0.40 * record["family_confidence"] + 0.35 * record["order_score"] + 0.20 * record["span_fraction"]["main"] + 0.05 * record["floor_participation"] - 0.05 * record["localization"], -record["frequency_hz"]))  # Rank candidates by physical purity only.
            selected[label] = {**choice, "selection_rule": f"highest physical score for {family}, n={order_value}, parity={parity_label}"}  # Store the strict classification result.
            used.add(int(choice["mode"]))  # Mark the selected numerical mode.
        else:  # Handle failure of the strict rule.
            relaxed = [record for record in raw if record["mode"] not in used and record["family"] == family and record["longitudinal_order"] == order_value and record["span_fraction"]["main"] >= 0.35 and record["floor_participation"] >= 0.20 and record["frequency_hz"] <= 0.60]  # Relax only diagnostic purity thresholds.
            if relaxed:  # Test whether a diagnostic candidate exists.
                choice = max(relaxed, key=lambda record: (record["family_confidence"] + record["order_score"] + record["span_fraction"]["main"], -record["frequency_hz"]))  # Rank the relaxed candidates physically.
                selected[label] = {**choice, "status": "relaxed", "selection_rule": f"relaxed physical score for {family}, n={order_value}"}  # Explicitly flag the relaxed assignment.
                used.add(int(choice["mode"]))  # Mark the selected numerical mode.
            else:  # Handle complete absence of a candidate.
                selected[label] = {"status": "unidentified", "selection_rule": f"no {family} main-span mode with n={order_value}"}  # Preserve an honest unclassified state.
    selected_shapes = {label: shape_data.get(int(record["mode"])) for label, record in selected.items() if "mode" in record}  # Retain only the fourteen selected shape records.
    meta = {"target_frequency_used": False, "family_rule": "dominant floor-section L/V/T displacement energy", "parity_rule": "main-span midpoint reflection correlation", "order_rule": "largest projection on fixed-end sine orders one through eight", "side_rule": {"SIDE1": "south717 fundamental", "SIDE2": "north660 fundamental", "SIDE3": "south503 fundamental"}, "selected_shapes": selected_shapes}  # Describe classification independently of targets.
    return raw, selected, meta  # Return raw metrics, canonical labels, and shape data.
def plots(raw: list[dict], selected: dict[str, dict], comparison: list[dict], meta: dict) -> None:  # Generate auditable spectrum and shape plots.
    first = raw[:40]  # Select the first forty positive global modes.
    plt.figure(figsize=(10.0, 5.5))  # Create one spectrum figure.
    plt.vlines([item["mode"] for item in first], 0.0, [item["frequency_hz"] for item in first])  # Draw discrete spectral lines.
    plt.scatter([item["mode"] for item in first], [item["frequency_hz"] for item in first], s=16.0)  # Mark each eigenfrequency.
    plt.xlabel("Numerical mode")  # Label the numerical order axis.
    plt.ylabel("Frequency / Hz")  # Label the frequency axis.
    plt.title("Clean 44-rope theoretical model: first 40 modes")  # State the model identity.
    plt.grid(True, alpha=0.25)  # Add a light reading grid.
    plt.tight_layout()  # Fit labels inside the canvas.
    plt.savefig(OUT / "spectrum_first_40.png", dpi=180)  # Save the spectrum figure.
    plt.close()  # Release the spectrum canvas.
    valid = [item for item in comparison if item["computed_hz"] is not None]  # Select identified physical labels.
    plt.figure(figsize=(11.0, 5.8))  # Create one post-freeze comparison figure.
    positions = np.arange(len(valid))  # Form categorical positions.
    plt.bar(positions - 0.19, [item["computed_hz"] for item in valid], width=0.38, label="Computed")  # Plot frozen computed values.
    plt.bar(positions + 0.19, [item["target_hz"] for item in valid], width=0.38, label="External target")  # Plot externally loaded targets.
    plt.xticks(positions, [item["label"] for item in valid], rotation=45.0, ha="right")  # Label physical families.
    plt.ylabel("Frequency / Hz")  # Label the frequency axis.
    plt.title("External comparison loaded after model freeze")  # State the post-freeze protocol.
    plt.legend()  # Show data-series identity.
    plt.grid(True, axis="y", alpha=0.25)  # Add a light horizontal grid.
    plt.tight_layout()  # Fit labels inside the canvas.
    plt.savefig(OUT / "comparison_after_freeze.png", dpi=180)  # Save the comparison figure.
    plt.close()  # Release the comparison canvas.
    for label in LABEL_ORDER:  # Draw one independent mode-shape figure per identified label.
        if label not in meta["selected_shapes"] or meta["selected_shapes"][label] is None:  # Skip unidentified families.
            continue  # Continue to the next label.
        record = selected[label]  # Read the selected classification record.
        family = record["family"]  # Read its dominant physical component.
        shape = meta["selected_shapes"][label]  # Read its two-catwalk shape data.
        x_values = np.asarray(shape["x_m"])  # Read the longitudinal coordinates.
        upstream = np.asarray(shape["U"][family])  # Read the upstream dominant component.
        downstream = np.asarray(shape["D"][family])  # Read the downstream dominant component.
        scale = max(float(np.max(np.abs(upstream))), float(np.max(np.abs(downstream))), 1.0e-30)  # Form a common normalization scale.
        plt.figure(figsize=(10.0, 4.0))  # Create one mode-shape figure.
        plt.plot(x_values, upstream / scale, label="Upstream")  # Plot the upstream normalized field.
        plt.plot(x_values, downstream / scale, linestyle="--", label="Downstream")  # Plot the downstream normalized field.
        plt.axhline(0.0, linewidth=0.7)  # Show the zero-amplitude reference.
        plt.xlabel("MCT longitudinal coordinate / m")  # Label the longitudinal axis.
        plt.ylabel(f"Normalized {family}")  # Label the physical component.
        plt.title(f"{label}: mode {record['mode']}, {record['frequency_hz']:.6f} Hz")  # State label, numerical order, and frequency.
        plt.legend()  # Show catwalk identity.
        plt.grid(True, alpha=0.25)  # Add a light grid.
        plt.tight_layout()  # Fit labels inside the canvas.
        plt.savefig(OUT / f"mode_shape_{label}.png", dpi=170)  # Save the current mode shape.
        plt.close()  # Release the current canvas.
def write_csv(raw: list[dict], selected: dict[str, dict], comparison: list[dict]) -> None:  # Write the primary calculation tables.
    with (OUT / "raw_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the raw spectrum table.
        writer = csv.writer(handle)  # Create its CSV writer.
        writer.writerow(["mode", "frequency_hz", "family", "family_confidence", "floor_participation", "parity", "parity_label", "longitudinal_order", "order_score", "same_global_sign_correlation", "north_fraction", "main_fraction", "south717_fraction", "south503_fraction", "localization", "residual"])  # Write the raw table header.
        for item in raw:  # Traverse every solved mode.
            writer.writerow([item["mode"], item["frequency_hz"], item["family"], item["family_confidence"], item["floor_participation"], item["parity"], item["parity_label"], item["longitudinal_order"], item["order_score"], item["same_global_sign_correlation"], item["span_fraction"]["north"], item["span_fraction"]["main"], item["span_fraction"]["south717"], item["span_fraction"]["south503"], item["localization"], item["residual"]])  # Write the current physical metrics.
    with (OUT / "classified_14_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the frozen classification table.
        writer = csv.writer(handle)  # Create its CSV writer.
        writer.writerow(["label", "status", "mode", "frequency_hz", "family", "parity", "longitudinal_order", "main_fraction", "same_global_sign_correlation", "selection_rule"])  # Write the classification header.
        for label in LABEL_ORDER:  # Preserve the requested reporting order.
            item = selected[label]  # Read the current frozen assignment.
            writer.writerow([label, item.get("status", "identified"), item.get("mode"), item.get("frequency_hz"), item.get("family"), item.get("parity_label"), item.get("longitudinal_order"), (item.get("span_fraction") or {}).get("main"), item.get("same_global_sign_correlation"), item.get("selection_rule")])  # Write the classification row.
    with (OUT / "comparison_after_freeze.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the post-freeze external comparison table.
        writer = csv.DictWriter(handle, fieldnames=["label", "mode", "computed_hz", "target_hz", "error_percent", "status"])  # Create a named-field writer.
        writer.writeheader()  # Write the comparison header.
        writer.writerows(comparison)  # Write all fourteen comparison rows.
def main() -> int:  # Execute the clean calculation protocol.
    model = load_mct()  # Parse and hash-check the original MCT source.
    floor_nodes, floor_elements = chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the formed floor chain.
    top_nodes, top_elements = chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the formed gantry-rope chain.
    static = inverse_static(model, floor_nodes, floor_elements, top_nodes, top_elements)  # Reconstruct prestress from geometry and independent loads.
    if static["equilibrium_relative_residual"] > 5.0e-3:  # Require physical equilibrium compatibility.
        raise RuntimeError(f"Inverse equilibrium residual is {static['equilibrium_relative_residual']:.6e}")  # Reject an incompatible static state.
    system = assemble(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Assemble all explicit ropes and equivalent frames.
    frequencies, vectors, residuals, checks = solve_eigen(system)  # Solve and verify the global spectrum.
    raw, selected, classification_meta = classify(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Classify physical families without targets.
    assumptions = [{"name": "MCT use", "value": "formed coordinates, topology, groups, and restraint topology only; no INIFORCE, INI-EFORCE, CONLOAD, or modal result"}, {"name": "floor ropes", "value": "16 explicit ropes per catwalk; one smart rope at each inner local position, mirror-symmetric globally"}, {"name": "gantry ropes", "value": "6 explicit ropes per catwalk, represented as left and right triplets across 7.46 m"}, {"name": "secondary floor system", "value": "q=2.766 kN/m total lower-system mass; explicit ropes and handrails removed before residual width-distributed mass"}, {"name": "portals", "value": "71 per catwalk; 1429.98 kg each; 161x161x8 equivalent two-column frame"}, {"name": "passages", "value": "21 full multi-port equivalents; 10130 kg each; three phi152x6 chords; longitudinal bracing stiffness factor 0.03"}, {"name": "supports", "value": "current MCT restraint topology interpreted as the fixed-contact linearization state"}, {"name": "classification", "value": "L/V/T energy, main-span sine order, parity, and span localization only; no target frequency"}]  # Record every decisive modelling assumption.
    frozen = {"kind": "clean_theory_44_rope_catwalk_frozen", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "source_mct_bytes": model["source"]["bytes"], "target_frequency_used": False, "topology": {"explicit_floor_ropes": 32, "explicit_gantry_ropes": 12, "explicit_ropes_total": 44, "portals": 142, "passages": 21, "floor_chain_nodes": len(floor_nodes), "floor_chain_elements": len(floor_elements), "top_chain_nodes": len(top_nodes), "top_chain_elements": len(top_elements)}, "assumptions": assumptions, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": checks, "smart_index_zero_based": system["smart_index"], "portal_map": system["portals"], "passage_parameters": system["passages"], "raw_modes": raw, "classified_14": selected, "classification_meta": {key: value for key, value in classification_meta.items() if key != "selected_shapes"}}  # Form the target-free frozen result object.
    frozen_path = OUT / "frozen_results.json"  # Define the target-free result path.
    dump(frozen_path, frozen)  # Write classification and frequencies before targets exist in memory.
    frozen_sha = sha(frozen_path)  # Freeze the result identity.
    targets = {"LS1": 0.0365, "VA1": 0.0700, "LA1": 0.0726, "TA1": 0.0996, "VS1": 0.1028, "LS2": 0.1087, "TS1": 0.1147, "SIDE1": 0.1149, "SIDE2": 0.1239, "VA2": 0.1438, "LA2": 0.1449, "SIDE3": 0.1557, "TS2": 0.1571, "VS2": 0.1744}  # Load external targets only after freeze and hashing.
    comparison: list[dict] = []  # Initialize external comparison rows.
    for label in LABEL_ORDER:  # Traverse the fourteen declared labels.
        item = selected[label]  # Read the frozen physical assignment.
        computed = float(item["frequency_hz"]) if "frequency_hz" in item else None  # Read the computed value if identified.
        error = None if computed is None else 100.0 * (computed - targets[label]) / targets[label]  # Evaluate post-freeze relative error.
        comparison.append({"label": label, "mode": item.get("mode"), "computed_hz": computed, "target_hz": targets[label], "error_percent": error, "status": item.get("status", "identified")})  # Append the auditable comparison row.
    write_csv(raw, selected, comparison)  # Write raw, classified, and comparison tables.
    plots(raw, selected, comparison, classification_meta)  # Write spectrum and selected mode-shape plots.
    identified_errors = [abs(float(item["error_percent"])) for item in comparison if item["error_percent"] is not None]  # Collect identified absolute errors.
    summary = {"kind": "clean_theory_44_rope_catwalk_summary", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha, "identified_count": len(identified_errors), "mae_percent": float(np.mean(identified_errors)) if identified_errors else None, "max_abs_error_percent": float(np.max(identified_errors)) if identified_errors else None, "inverse_static": frozen["inverse_static"], "matrix_checks": checks, "classified": comparison}  # Build the concise final calculation summary.
    dump(OUT / "summary.json", summary)  # Write the final summary.
    dump(OUT / "unstressed_lengths.json", system["recovered"])  # Write all explicit-rope recovered unstressed lengths.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every primary result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2))  # Print the concise summary into the workflow log.
    return 0  # Return successful completion.
if __name__ == "__main__":  # Execute only when invoked as a script.
    raise SystemExit(main())  # Run the complete clean calculation.
