from __future__ import annotations  # Enable modern type annotations.

import argparse  # Parse command-line inputs.
import csv  # Write transparent tabular outputs.
import hashlib  # Bind results to the authoritative MCT source.
import json  # Write the calculation audit record.
import math  # Supply geometric constants.
import os  # Configure a writable plotting cache.
import re  # Expand MIDAS node and element ranges.
from pathlib import Path  # Handle paths safely.

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-double-mct")  # Avoid a read-only home cache.

import matplotlib  # Configure non-interactive plots.

matplotlib.use("Agg")  # Render figures without a display.

import matplotlib.pyplot as plt  # Create topology and mode-shape figures.
from matplotlib import font_manager  # Register the bundled Chinese plotting font.
import numpy as np  # Assemble vectors and matrices.
import pandas as pd  # Read the authoritative station mapping.
from scipy.sparse import coo_matrix, diags  # Build sparse FE matrices.
from scipy.sparse.linalg import eigsh  # Solve the generalized eigenproblem.

EXPECTED_MCT_SHA256 = "0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1"  # Freeze the reviewed source.
GRAVITY_M_S2 = 9.806  # Match the MCT gravity value of 9806 mm/s2.
HALF_CATWALK_SPACING_M = 21.45  # Place the two MCT planes 42.9 m apart.
MCT_X_ORIGIN_M = 831.091  # Shift the gate-rope north endpoint to global X=0.
GATE_ONLY_EQUIVALENT_EA_N = 199_405_719.09780553  # Use the H10 finite-gate free-rotation condensation for each ordinary gate.
GATE_ONLY_AUDIT_PATH = Path("tmp/gate_only_condensation/audit.json")  # Bind the ordinary-gate replacement to its reviewed condensation record.
DEFAULT_FOUR_PORT_MATRIX = Path("tmp/gate_passage_condensation/K12_translation_ports.csv")  # Use the six-rigid-mode finite-gate plus 633-member passage condensation.
CHINESE_FONT_PATH = Path("tmp/pdfs/fonts/NotoSansCJKsc-Regular.otf")  # Reuse the verified report font.

if CHINESE_FONT_PATH.exists():  # Register Chinese glyphs when the bundled font is present.
    font_manager.fontManager.addfont(str(CHINESE_FONT_PATH))  # Add the font to Matplotlib's runtime registry.
    plt.rcParams["font.family"] = "Noto Sans CJK SC"  # Select the registered family globally.
plt.rcParams["axes.unicode_minus"] = False  # Keep minus signs readable with CJK fonts.


def sha256_file(path: Path) -> str:  # Hash an input file without changing it.
    digest = hashlib.sha256()  # Initialize the digest.
    with path.open("rb") as stream:  # Read the file in bounded chunks.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Stream one MiB at a time.
            digest.update(chunk)  # Accumulate the file bytes.
    return digest.hexdigest()  # Return the lowercase hexadecimal hash.


def block_occurrences(lines: list[str], name: str) -> list[list[str]]:  # Return every repeated MCT block.
    occurrences: list[list[str]] = []  # Store matching block bodies.
    current: list[str] | None = None  # Track the active matching block.
    for raw in lines:  # Scan the source once.
        stripped = raw.strip()  # Normalize surrounding whitespace.
        if stripped.startswith("*"):  # Detect a new MCT command block.
            command = stripped.split()[0].upper()  # Ignore comments after the command name.
            current = [] if command == name.upper() else None  # Start only a requested block.
            if current is not None:  # Register the new occurrence.
                occurrences.append(current)  # Preserve repeated blocks such as CONLOAD.
            continue  # Do not include the command line itself.
        if current is not None:  # Capture lines within a matching block.
            current.append(raw)  # Preserve commas and range syntax.
    return occurrences  # Return all matching bodies.


def data_lines(block: list[str]) -> list[str]:  # Remove MCT comments and empty lines.
    return [line.strip() for line in block if line.strip() and not line.lstrip().startswith(";")]  # Keep data only.


def expand_id_spec(spec: str) -> list[int]:  # Expand MIDAS forms such as 1to9by2.
    cleaned = spec.replace("\\", " ").strip()  # Remove continuation markers.
    result: list[int] = []  # Collect expanded identifiers.
    for token in cleaned.split():  # Process space-separated atoms.
        match = re.fullmatch(r"(-?\d+)to(-?\d+)(?:by(-?\d+))?", token, flags=re.IGNORECASE)  # Match ranges.
        if match:  # Expand a range token.
            start = int(match.group(1))  # Read the inclusive start.
            stop = int(match.group(2))  # Read the inclusive stop.
            step = int(match.group(3) or (1 if stop >= start else -1))  # Infer the direction if omitted.
            result.extend(range(start, stop + (1 if step > 0 else -1), step))  # Include the terminal ID.
        elif re.fullmatch(r"-?\d+", token):  # Accept a single integer ID.
            result.append(int(token))  # Append the scalar ID.
    return result  # Return a flat integer list.


def parse_mct(path: Path) -> dict[str, object]:  # Parse the reviewed subset of the MCT format.
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()  # Preserve mojibake-safe numeric data.
    nodes: dict[int, np.ndarray] = {}  # Map node IDs to SI coordinates.
    for line in data_lines(block_occurrences(lines, "*NODE")[0]):  # Read the unique node block.
        fields = [field.strip() for field in line.split(",")]  # Split comma-delimited values.
        nodes[int(fields[0])] = np.array([float(fields[1]), float(fields[2]), float(fields[3])], dtype=float) / 1000.0  # Convert mm to m.
    elements: dict[int, dict[str, int | str]] = {}  # Store two-node element connectivity and properties.
    for line in data_lines(block_occurrences(lines, "*ELEMENT")[0]):  # Read the unique element block.
        fields = [field.strip() for field in line.split(",")]  # Split the record.
        element_id = int(fields[0])  # Read the sparse element ID.
        elements[element_id] = {  # Preserve the required fields.
            "type": fields[1].upper(),  # Record TENSTR or TRUSS.
            "material": int(fields[2]),  # Record the material ID.
            "section": int(fields[3]),  # Record the section ID.
            "n1": int(fields[4]),  # Record the first node.
            "n2": int(fields[5]),  # Record the second node.
        }  # Finish the element record.
    initial_force_kn: dict[int, float] = {}  # Store one geometric-stiffness force per cable element.
    for line in data_lines(block_occurrences(lines, "*INIFORCE")[0]):  # Read the authoritative initial-force block.
        fields = [field.strip() for field in line.split(",")]  # Split list, direction, and force.
        if len(fields) < 3 or fields[1].upper() != "AXIAL":  # Reject unrelated records.
            continue  # Skip non-axial data.
        for element_id in expand_id_spec(fields[0]):  # Expand grouped element IDs.
            initial_force_kn[element_id] = float(fields[2])  # Assign the shared force value.
    constraints: dict[int, str] = {}  # Store translational support masks.
    for line in data_lines(block_occurrences(lines, "*CONSTRAINT")[0]):  # Read supports.
        fields = [field.strip() for field in line.split(",")]  # Split node list and mask.
        for node_id in expand_id_spec(fields[0]):  # Expand support node ranges.
            constraints[node_id] = fields[1]  # Preserve the six-character MIDAS mask.
    conload_blocks = block_occurrences(lines, "*CONLOAD")  # Collect all repeated nodal-load cases.
    concentrated_mass_kg: dict[int, float] = {}  # Convert the first CONLOAD block to nodal mass.
    for line in data_lines(conload_blocks[0]):  # The first block is the reviewed second-stage gravity load.
        fields = [field.strip() for field in line.split(",")]  # Split the nodal force record.
        node_ids = expand_id_spec(fields[0])  # Expand the node list.
        fz_kn = float(fields[3])  # Read vertical force in kN.
        for node_id in node_ids:  # Assign mass to each listed node.
            concentrated_mass_kg[node_id] = concentrated_mass_kg.get(node_id, 0.0) + max(0.0, -fz_kn) * 1000.0 / GRAVITY_M_S2  # Convert N/g to kg.
    return {  # Return the parsed model.
        "nodes": nodes,  # Expose node coordinates.
        "elements": elements,  # Expose connectivity.
        "initial_force_kn": initial_force_kn,  # Expose cable forces.
        "constraints": constraints,  # Expose supports.
        "concentrated_mass_kg": concentrated_mass_kg,  # Expose nodal masses.
    }  # Finish the parser output.


def material_and_section(element: dict[str, int | str]) -> tuple[float, float, float]:  # Return E, area, and weight density.
    material_id = int(element["material"])  # Normalize the material key.
    section_id = int(element["section"])  # Normalize the section key.
    if material_id == 1 and section_id == 1:  # Match the carrying-rope equivalent bundle.
        area_m2 = math.pi * (0.168498**2) / 4.0  # Convert the reviewed solid-round diameter to area.
        return 120.0e9, area_m2, 1.24031e-7  # Return modulus, SI area, and kN/mm3 weight density.
    if material_id == 2 and section_id == 2:  # Match the gantry-rope equivalent bundle.
        area_m2 = math.pi * (0.103436**2) / 4.0  # Convert its reviewed equivalent diameter.
        return 120.0e9, area_m2, 8.432e-8  # Return reviewed properties.
    if material_id == 3 and section_id == 3:  # Match the two-post gate axial surrogate.
        return 206.0e9, 4896.0e-6, 0.0  # Preserve the source B161x161x8 equivalent area while adding no duplicated mass.
    raise ValueError(f"Unsupported material/section pair: {material_id}/{section_id}")  # Stop on silent model drift.


def add_pair_matrix(rows: list[int], cols: list[int], values: list[float], i: int, j: int, matrix: np.ndarray) -> None:  # Assemble a 3D two-node spring.
    dof_i = np.arange(3 * i, 3 * i + 3)  # Locate node-i translation DOFs.
    dof_j = np.arange(3 * j, 3 * j + 3)  # Locate node-j translation DOFs.
    for a in range(3):  # Traverse local row components.
        for b in range(3):  # Traverse local column components.
            value = float(matrix[a, b])  # Read one 3x3 coefficient.
            rows.extend([int(dof_i[a]), int(dof_i[a]), int(dof_j[a]), int(dof_j[a])])  # Add four block positions.
            cols.extend([int(dof_i[b]), int(dof_j[b]), int(dof_i[b]), int(dof_j[b])])  # Add matching columns.
            values.extend([value, -value, -value, value])  # Assemble [[K,-K],[-K,K]].


def read_four_port_matrix(path: Path) -> tuple[np.ndarray, str]:  # Read and validate the condensed finite-gate/passage matrix.
    table = pd.read_csv(path, index_col=0)  # Preserve the labelled 12-port order from the condensation audit.
    expected = [f"{port}_{axis}" for port in ("B_L", "T_L", "B_R", "T_R") for axis in ("UX", "UY", "UZ")]  # Freeze the APDL global-axis port order.
    if list(table.index) != expected or list(table.columns) != expected:  # Reject a silently reordered matrix.
        raise ValueError("The four-port passage matrix labels or order do not match the reviewed interface.")  # Stop before a wrong-axis assembly.
    matrix_n_per_mm = table.to_numpy(dtype=float)  # Convert the labelled table to a dense numeric matrix.
    symmetry_error = float(np.max(np.abs(matrix_n_per_mm - matrix_n_per_mm.T)))  # Audit Maxwell reciprocity.
    if symmetry_error > 1.0e-5:  # Allow only CSV roundoff.
        raise ValueError(f"The four-port passage matrix is not symmetric: {symmetry_error}")  # Reject corrupt input.
    matrix_n_per_mm = 0.5 * (matrix_n_per_mm + matrix_n_per_mm.T)  # Remove harmless printed roundoff asymmetry.
    eigenvalues = np.linalg.eigvalsh(matrix_n_per_mm)  # Check the expected semidefinite spectrum.
    scale = max(float(np.max(np.abs(eigenvalues))), 1.0)  # Define a relative eigenvalue scale.
    if int(np.sum(eigenvalues < -scale * 1.0e-8)) != 0:  # Require no material negative modes.
        raise ValueError("The four-port passage matrix contains a negative stiffness mode.")  # Stop on an invalid condensation.
    return matrix_n_per_mm * 1000.0, sha256_file(path)  # Convert N/mm to N/m for metre-based displacements and bind the file hash.


def add_general_matrix(rows: list[int], cols: list[int], values: list[float], node_indices: list[int], matrix: np.ndarray) -> None:  # Assemble an arbitrary translation-port stiffness matrix.
    dofs = np.concatenate([np.arange(3 * node, 3 * node + 3, dtype=int) for node in node_indices])  # Expand four node ports to twelve global DOFs.
    if matrix.shape != (len(dofs), len(dofs)):  # Guard the port-matrix dimension.
        raise ValueError(f"Port matrix shape {matrix.shape} does not match {len(dofs)} DOFs.")  # Stop on topology drift.
    nonzero_rows, nonzero_cols = np.nonzero(np.abs(matrix) > 0.0)  # Avoid inserting numerical zeros into the sparse matrix.
    for local_row, local_col in zip(nonzero_rows, nonzero_cols):  # Traverse all retained coupling terms.
        rows.append(int(dofs[local_row]))  # Map the local row to a global DOF.
        cols.append(int(dofs[local_col]))  # Map the local column to a global DOF.
        values.append(float(matrix[local_row, local_col]))  # Preserve the complete non-diagonal coefficient.


def station_local_to_global(slope_degree: float) -> np.ndarray:  # Rotate the near-horizontal H10 X-Y-Z condensation to any rope slope.
    theta = math.radians(float(slope_degree))  # Convert the central carrying-rope slope to radians.
    x_axis = np.array([math.cos(theta), 0.0, math.sin(theta)], dtype=float)  # Align local X with the carrying-rope tangent.
    y_axis = np.array([0.0, 1.0, 0.0], dtype=float)  # Preserve the APDL transverse Y direction from B_R to B_L.
    z_axis = np.cross(x_axis, y_axis)  # Complete the APDL right-handed X-Y-Z station frame.
    rotation = np.column_stack((x_axis, y_axis, z_axis))  # Map station-local X-Y-Z components to global X-Y-Z.
    if float(np.max(np.abs(rotation.T @ rotation - np.eye(3)))) > 1.0e-12:  # Verify orthonormality.
        raise ValueError("The passage station frame is not orthonormal.")  # Stop on an axis-construction error.
    return rotation  # Return local-to-global direction cosines.


def build_double_model(parsed: dict[str, object], station_map: pd.DataFrame, passage_matrix_path: Path = DEFAULT_FOUR_PORT_MATRIX) -> dict[str, object]:  # Assemble the double-MCT sparse system.
    gate_only_audit = json.loads(GATE_ONLY_AUDIT_PATH.read_text(encoding="utf-8"))  # Read the reviewed finite-gate-only condensation record.
    audited_gate_ea_n = float(gate_only_audit["replacement_assessment"]["axial_comparison"]["finite_gate_equivalent_EA_N"])  # Extract its authoritative equivalent axial rigidity.
    if not math.isclose(audited_gate_ea_n, GATE_ONLY_EQUIVALENT_EA_N, rel_tol=1.0e-12, abs_tol=1.0e-6):  # Prevent a hard-coded parameter from drifting away from the source audit.
        raise ValueError(f"Ordinary-gate EA mismatch: code={GATE_ONLY_EQUIVALENT_EA_N}, audit={audited_gate_ea_n}")  # Stop before inconsistent assembly.
    source_nodes = parsed["nodes"]  # Read source coordinates.
    source_elements = parsed["elements"]  # Read source elements.
    initial_force_kn = parsed["initial_force_kn"]  # Read reviewed initial forces.
    concentrated_mass_kg = parsed["concentrated_mass_kg"]  # Read reviewed nodal masses.
    source_ids = sorted(source_nodes)  # Preserve sparse MCT IDs in deterministic order.
    index: dict[tuple[int, int], int] = {}  # Map width and MCT ID to global node index.
    coordinates: list[np.ndarray] = []  # Collect SI coordinates.
    node_records: list[dict[str, object]] = []  # Prepare an auditable node table.
    for width, transverse_m in ((0, -HALF_CATWALK_SPACING_M), (1, HALF_CATWALK_SPACING_M)):  # Create left and right copies.
        for node_id in source_ids:  # Copy every original MCT node.
            source = np.asarray(source_nodes[node_id], dtype=float)  # Read X,Y,Z in SI.
            global_index = len(coordinates)  # Assign a compact global index.
            coordinate = np.array([source[0] - MCT_X_ORIGIN_M, transverse_m, source[2]], dtype=float)  # Shift X and replace planar Y.
            index[(width, node_id)] = global_index  # Save the lookup.
            coordinates.append(coordinate)  # Append coordinates.
            node_records.append({"global_index": global_index, "width": "L" if width == 0 else "R", "mct_node": node_id, "x_m": coordinate[0], "y_m": coordinate[1], "z_m": coordinate[2]})  # Record provenance.
    xyz = np.vstack(coordinates)  # Form the global coordinate array.
    nodal_mass_kg = np.zeros(len(coordinates), dtype=float)  # Initialize scalar translational node masses.
    rows: list[int] = []  # Accumulate stiffness row indices.
    cols: list[int] = []  # Accumulate stiffness column indices.
    values: list[float] = []  # Accumulate stiffness coefficients.
    element_records: list[dict[str, object]] = []  # Prepare an auditable element table.
    distributed_mass_kg = 0.0  # Track the source cable mass closure.
    replaced_gate_elements = set(int(value) for value in station_map["mct_property3_element"].tolist())  # Identify the 21 planar gate surrogates replaced by finite-gate condensation.
    ordinary_gate_elements = {int(element_id) for element_id, element in source_elements.items() if str(element["type"]) == "TRUSS" and int(element_id) not in replaced_gate_elements}  # Identify the remaining 50 planar gate surrogates replaced by finite-gate axial condensation.
    if len(ordinary_gate_elements) != 50:  # Guard the reviewed 71 equals 21 plus 50 gate schedule.
        raise ValueError(f"Expected 50 ordinary gate TRUSS elements, found {len(ordinary_gate_elements)}")  # Stop on topology drift.
    for width in (0, 1):  # Assemble each MCT plane independently.
        for element_id in sorted(source_elements):  # Preserve element order.
            element = source_elements[element_id]  # Read source properties.
            if element_id in replaced_gate_elements:  # Replace each passage-station planar TRUSS with the four-port finite gate matrix.
                element_records.append({"width": "L" if width == 0 else "R", "source_element": element_id, "kind": "TRUSS_REPLACED_BY_FOUR_PORT", "n1_global": index[(width, int(element["n1"]))], "n2_global": index[(width, int(element["n2"]))], "length_m": float(np.linalg.norm(xyz[index[(width, int(element["n2"]))]] - xyz[index[(width, int(element["n1"]))]])), "initial_force_kn": 0.0})  # Record the non-duplicated replacement.
                continue  # Do not double-count its axial or supplemental gate shear stiffness.
            n1_id = int(element["n1"])  # Normalize node one.
            n2_id = int(element["n2"])  # Normalize node two.
            i = index[(width, n1_id)]  # Resolve global node one.
            j = index[(width, n2_id)]  # Resolve global node two.
            vector = xyz[j] - xyz[i]  # Form the element chord.
            length_m = float(np.linalg.norm(vector))  # Compute length.
            direction = vector / length_m  # Form the unit chord.
            projector = np.outer(direction, direction)  # Form the axial projector.
            initial_force_n = float(initial_force_kn.get(element_id, 0.0)) * 1000.0  # Convert kN to N.
            if str(element["type"]) == "TENSTR":  # Add cable geometric stiffness.
                elastic_modulus_pa, area_m2, weight_density_kn_mm3 = material_and_section(element)  # Resolve the reviewed cable properties.
                axial_stiffness = elastic_modulus_pa * area_m2 / length_m  # Compute EA/L in N/m.
                tangent = axial_stiffness * projector  # Start with material axial stiffness.
                tangent += (initial_force_n / length_m) * (np.eye(3) - projector)  # Linearize about the reviewed tension state.
                element_kind = str(element["type"])  # Preserve the cable source type.
            else:  # Replace an ordinary planar gate surrogate by the audited free-rotation finite-gate condensation.
                area_m2 = 0.0  # Add no distributed mass because all gate and guide weight is already carried by the MCT lumped masses.
                weight_density_kn_mm3 = 0.0  # Keep the stiffness-only gate condensation massless.
                axial_stiffness = GATE_ONLY_EQUIVALENT_EA_N / length_m  # Reorient the constant condensed EA along this station's actual bottom-to-top chord.
                tangent = axial_stiffness * projector  # Retain the sole objective translational deformation mode of the freely rotating gate ports.
                element_kind = "TRUSS_REPLACED_BY_GATE_ONLY_RANK1"  # Distinguish the finite-gate replacement from the original property-3 surrogate.
            add_pair_matrix(rows, cols, values, i, j, tangent)  # Assemble element tangent stiffness.
            length_mm = length_m * 1000.0  # Convert length for MCT weight density.
            area_mm2 = area_m2 * 1.0e6  # Convert area for MCT weight density.
            element_weight_kn = weight_density_kn_mm3 * area_mm2 * length_mm  # Compute source selfweight.
            element_mass_kg = element_weight_kn * 1000.0 / GRAVITY_M_S2  # Convert kN/g to kg.
            nodal_mass_kg[i] += 0.5 * element_mass_kg  # Lump half at node one.
            nodal_mass_kg[j] += 0.5 * element_mass_kg  # Lump half at node two.
            distributed_mass_kg += element_mass_kg  # Accumulate mass closure.
            element_records.append({"width": "L" if width == 0 else "R", "source_element": element_id, "kind": element_kind, "n1_global": i, "n2_global": j, "length_m": length_m, "initial_force_kn": initial_force_n / 1000.0, "equivalent_ea_n": GATE_ONLY_EQUIVALENT_EA_N if element_kind == "TRUSS_REPLACED_BY_GATE_ONLY_RANK1" else elastic_modulus_pa * area_m2})  # Record the retained cable or condensed ordinary gate.
        for node_id, mass_kg in concentrated_mass_kg.items():  # Add the reviewed second-stage nodal mass.
            nodal_mass_kg[index[(width, int(node_id))]] += float(mass_kg)  # Preserve the original node assignment.
    passage_local_n_per_m, passage_matrix_sha256 = read_four_port_matrix(passage_matrix_path)  # Load the audited H10 four-rope-port matrix.
    passage_records: list[dict[str, object]] = []  # Record all 21 finite-gate and passage assemblies.
    for row in station_map.itertuples(index=False):  # Use only the authoritative MCT station map.
        bottom_id = int(row.mct_bottom_node)  # Read the dedicated lower-rope node.
        gate_id = int(row.mct_gate_node)  # Read the matched gantry-rope node.
        port_nodes = [index[(1, bottom_id)], index[(1, gate_id)], index[(0, bottom_id)], index[(0, gate_id)]]  # Map matrix CW1 to +Y and CW2 to -Y for q=-Y.
        rotation = station_local_to_global(float(row.bottom_central_chord_slope_degree))  # Rotate the near-horizontal H10 matrix to this station tangent.
        local_from_global = rotation.T  # Convert each global displacement to station-local X-Y-Z components.
        transform = np.kron(np.eye(4), local_from_global)  # Apply the same station frame to all four rope ports.
        passage_global = transform.T @ passage_local_n_per_m @ transform  # Transform the complete 12x12 matrix by virtual-work consistency.
        add_general_matrix(rows, cols, values, port_nodes, passage_global)  # Couple bottom and gantry ropes of both complete MCT planes.
        passage_records.append({"passage_id": str(row.passage_id), "bottom_node": bottom_id, "gate_node": gate_id, "replaced_gate_element": int(row.mct_property3_element), "cw1_bottom_global": port_nodes[0], "cw1_gantry_global": port_nodes[1], "cw2_bottom_global": port_nodes[2], "cw2_gantry_global": port_nodes[3], "x_bottom_m": float(source_nodes[bottom_id][0] - MCT_X_ORIGIN_M), "x_gate_m": float(source_nodes[gate_id][0] - MCT_X_ORIGIN_M), "x_centerline_m": 0.5 * float(source_nodes[bottom_id][0] + source_nodes[gate_id][0]) - MCT_X_ORIGIN_M, "slope_degree": float(row.bottom_central_chord_slope_degree), "matrix_sha256": passage_matrix_sha256, "added_mass_kg": 0.0})  # Bind all four interfaces and the zero-density rule.
    ndof = 3 * len(coordinates)  # Count translational DOFs.
    stiffness = coo_matrix((values, (rows, cols)), shape=(ndof, ndof)).tocsr()  # Sum duplicate sparse entries.
    constrained: set[int] = set()  # Collect constrained global DOFs.
    for width in (0, 1):  # Apply source supports to each plane.
        for node_id, mask in parsed["constraints"].items():  # Read each MIDAS support mask.
            global_node = index[(width, int(node_id))]  # Resolve the duplicate node.
            for component in range(3):  # Use only translation characters Dx,Dy,Dz.
                if component < len(mask) and mask[component] == "1":  # Detect a fixed translation.
                    constrained.add(3 * global_node + component)  # Add the global DOF.
    all_dofs = np.arange(ndof, dtype=int)  # Enumerate every translation DOF.
    free_mask = np.ones(ndof, dtype=bool)  # Start with all DOFs free.
    free_mask[np.array(sorted(constrained), dtype=int)] = False  # Remove supports.
    free_dofs = all_dofs[free_mask]  # Form the free-DOF index.
    dof_mass_kg = np.repeat(nodal_mass_kg, 3)  # Assign isotropic translational inertia.
    if np.min(dof_mass_kg[free_dofs]) <= 0.0:  # Reject massless free DOFs.
        raise ValueError("The assembled model contains a non-positive free translational mass.")  # Stop before eigensolution.
    return {  # Return the assembled system and audit tables.
        "xyz": xyz,  # Expose node coordinates.
        "index": index,  # Expose source-to-global mapping.
        "stiffness": stiffness,  # Expose the full tangent stiffness.
        "nodal_mass_kg": nodal_mass_kg,  # Expose scalar node masses.
        "dof_mass_kg": dof_mass_kg,  # Expose diagonal DOF masses.
        "free_dofs": free_dofs,  # Expose the reduced system mapping.
        "node_records": node_records,  # Expose the node audit table.
        "element_records": element_records,  # Expose source element audit data.
        "passage_records": passage_records,  # Expose passage interfaces.
        "distributed_mass_kg": distributed_mass_kg,  # Expose the duplicated source cable mass.
        "concentrated_mass_kg": float(sum(concentrated_mass_kg.values()) * 2.0),  # Expose duplicated nodal mass.
        "passage_matrix_path": str(passage_matrix_path),  # Expose the four-port condensation source.
        "passage_matrix_sha256": passage_matrix_sha256,  # Bind the assembled stiffness to its reviewed file.
        "gate_only_audit_path": str(GATE_ONLY_AUDIT_PATH),  # Expose the ordinary-gate condensation source.
        "gate_only_audit_sha256": sha256_file(GATE_ONLY_AUDIT_PATH),  # Bind its exact reviewed record.
        "gate_only_equivalent_ea_n": audited_gate_ea_n,  # Expose the asserted equivalent axial rigidity.
        "replaced_gate_elements": sorted(replaced_gate_elements),  # Expose the 21 non-duplicated planar gate surrogates.
        "ordinary_gate_elements": sorted(ordinary_gate_elements),  # Expose the 50 source surrogates replaced in each width.
    }  # Finish the model object.


def solve_modes(model: dict[str, object], mode_count: int) -> tuple[np.ndarray, np.ndarray]:  # Solve and mass-normalize low modes.
    free_dofs = np.asarray(model["free_dofs"], dtype=int)  # Read the reduction map.
    stiffness = model["stiffness"][free_dofs][:, free_dofs]  # Reduce tangent stiffness.
    mass_values = np.asarray(model["dof_mass_kg"], dtype=float)[free_dofs]  # Reduce the diagonal mass.
    mass = diags(mass_values, format="csr")  # Form the sparse mass matrix.
    eigenvalues, reduced_modes = eigsh(stiffness, k=mode_count, M=mass, sigma=0.0, which="LM", tol=1.0e-9, maxiter=20000)  # Use shift-invert near zero.
    order = np.argsort(eigenvalues)  # Sort ascending.
    eigenvalues = np.maximum(eigenvalues[order], 0.0)  # Remove tiny negative roundoff.
    reduced_modes = reduced_modes[:, order]  # Reorder eigenvectors.
    full_modes = np.zeros((len(model["dof_mass_kg"]), mode_count), dtype=float)  # Allocate supported full vectors.
    full_modes[free_dofs, :] = reduced_modes  # Restore constrained zeros.
    frequencies_hz = np.sqrt(eigenvalues) / (2.0 * math.pi)  # Convert rad2/s2 to Hz.
    return frequencies_hz, full_modes  # Return frequencies and full vectors.


def symmetry_correlation(x: np.ndarray, values: np.ndarray) -> float:  # Measure main-span midpoint symmetry.
    midpoint = 0.5 * (float(np.min(x)) + float(np.max(x)))  # Define the sampled span midpoint.
    mirrored: list[float] = []  # Collect nearest mirrored ordinates.
    original: list[float] = []  # Collect original ordinates.
    for coordinate, value in zip(x, values):  # Visit each sample.
        target = 2.0 * midpoint - coordinate  # Find its mirror coordinate.
        nearest = int(np.argmin(np.abs(x - target)))  # Resolve the nearest discrete partner.
        original.append(float(value))  # Store the original value.
        mirrored.append(float(values[nearest]))  # Store its mirrored partner.
    a = np.asarray(original, dtype=float)  # Form the first vector.
    b = np.asarray(mirrored, dtype=float)  # Form the mirrored vector.
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))  # Compute the cosine denominator.
    return float(np.dot(a, b) / denominator) if denominator > 0.0 else 0.0  # Return signed correlation.


def half_wave_match(x: np.ndarray, values: np.ndarray, maximum_order: int = 12) -> tuple[int, float]:  # Match a main-span shape to sine half-wave templates.
    coordinate = (np.asarray(x, dtype=float) - float(np.min(x))) / max(float(np.max(x) - np.min(x)), np.finfo(float).eps)  # Normalize the sampled main span to zero through one.
    shape = np.asarray(values, dtype=float)  # Read the selected family ordinate.
    shape_norm = float(np.dot(shape, shape))  # Compute its squared norm once.
    best_order = 0  # Reserve the winning half-wave count.
    best_mac = 0.0  # Reserve the winning modal assurance criterion.
    for order in range(1, maximum_order + 1):  # Test physically relevant low half-wave counts.
        template = np.sin(order * math.pi * coordinate)  # Form a fixed-end sine template.
        denominator = shape_norm * float(np.dot(template, template))  # Form the MAC denominator.
        mac = float(np.dot(shape, template) ** 2 / denominator) if denominator > 0.0 else 0.0  # Evaluate sign-invariant MAC.
        if mac > best_mac:  # Retain the closest template.
            best_order = order  # Store its half-wave count.
            best_mac = mac  # Store the match quality.
    return best_order, best_mac  # Return the physical count and audit metric.


def validation_label(family: str, half_wave_order: int, fallback: str) -> str:  # Convert half-wave count to the Attachment 2-3 family convention.
    if family == "EDGE" or half_wave_order <= 0:  # Keep side-span/local modes separate.
        return fallback  # Return the existing edge label.
    parity = "S" if half_wave_order % 2 == 1 else "A"  # Map odd/even half waves to midpoint symmetry.
    if family == "L":  # Lateral numbering starts with the one-half-wave symmetric mode.
        sequence = (half_wave_order + 1) // 2 if parity == "S" else half_wave_order // 2  # Number LS1/LA1, LS2/LA2, and so on.
        return f"L{parity}{sequence}"  # Return the lateral label.
    if half_wave_order == 1:  # Attachment Table 4-1 omits the one-half-wave V/T branch.
        return f"{family}S0_UNLISTED"  # Prevent it from being mislabelled as VS2 or TS2.
    sequence = (half_wave_order - 1) // 2 if parity == "S" else half_wave_order // 2  # Start V/T listed symmetric numbering at three half waves.
    return f"{family}{parity}{sequence}"  # Return the vertical or torsional label.


def classify_modes(parsed: dict[str, object], model: dict[str, object], frequencies_hz: np.ndarray, modes: np.ndarray) -> pd.DataFrame:  # Classify family and span symmetry.
    nodal_mass = np.asarray(model["nodal_mass_kg"], dtype=float)  # Read scalar node masses.
    index = model["index"]  # Read the duplicate-node lookup.
    source_nodes = parsed["nodes"]  # Read source geometry.
    main_ids = [node_id for node_id in sorted(source_nodes) if 155 <= node_id <= 448]  # Use the reviewed main carrying chain.
    carrying_ids = [node_id for node_id in sorted(source_nodes) if 1 <= node_id <= 728]  # Use the full reviewed carrying main chain.
    main_x = np.array([source_nodes[node_id][0] - MCT_X_ORIGIN_M for node_id in main_ids], dtype=float)  # Form shifted main-span X coordinates.
    records: list[dict[str, object]] = []  # Collect modal metrics.
    for mode_index, frequency_hz in enumerate(frequencies_hz):  # Analyze each eigenvector.
        vector = modes[:, mode_index].reshape((-1, 3))  # Reshape into node translations.
        kinetic = np.sum(nodal_mass[:, None] * vector**2, axis=0)  # Measure axis-wise mass participation.
        common_lateral = []  # Collect left-right common lateral motion.
        common_vertical = []  # Collect common vertical motion.
        roll_vertical = []  # Collect differential vertical motion.
        longitudinal = []  # Collect common longitudinal motion.
        for node_id in main_ids:  # Sample matching left and right carrying nodes.
            left = vector[index[(0, node_id)]]  # Read left displacement.
            right = vector[index[(1, node_id)]]  # Read right displacement.
            longitudinal.append(0.5 * (left[0] + right[0]))  # Form common longitudinal motion.
            common_lateral.append(0.5 * (left[1] + right[1]))  # Form common lateral motion.
            common_vertical.append(0.5 * (left[2] + right[2]))  # Form common vertical motion.
            roll_vertical.append(0.5 * (right[2] - left[2]))  # Form system-roll numerator.
        all_common_lateral = []  # Collect full-line common lateral motion.
        all_common_vertical = []  # Collect full-line common vertical motion.
        all_roll_vertical = []  # Collect full-line differential vertical motion.
        all_longitudinal = []  # Collect full-line common longitudinal motion.
        for node_id in carrying_ids:  # Sample the complete carrying chain for edge-mode screening.
            left = vector[index[(0, node_id)]]  # Read the left-width displacement.
            right = vector[index[(1, node_id)]]  # Read the right-width displacement.
            all_longitudinal.append(0.5 * (left[0] + right[0]))  # Form full-line common longitudinal motion.
            all_common_lateral.append(0.5 * (left[1] + right[1]))  # Form full-line common lateral motion.
            all_common_vertical.append(0.5 * (left[2] + right[2]))  # Form full-line common vertical motion.
            all_roll_vertical.append(0.5 * (right[2] - left[2]))  # Form full-line system-roll numerator.
        family_signals = {  # Define physically interpretable family amplitudes.
            "L": float(np.linalg.norm(common_lateral)),  # Lateral family.
            "V": float(np.linalg.norm(common_vertical)),  # Vertical family.
            "T": float(np.linalg.norm(roll_vertical)),  # Two-width roll/torsion family.
            "X": float(np.linalg.norm(longitudinal)),  # Longitudinal diagnostic family.
        }  # Finish family metrics.
        full_signals = {  # Define matching full-line family amplitudes.
            "L": float(np.linalg.norm(all_common_lateral)),  # Full-line common lateral amplitude.
            "V": float(np.linalg.norm(all_common_vertical)),  # Full-line common vertical amplitude.
            "T": float(np.linalg.norm(all_roll_vertical)),  # Full-line differential vertical amplitude.
            "X": float(np.linalg.norm(all_longitudinal)),  # Full-line common longitudinal amplitude.
        }  # Finish full-line metrics.
        preliminary_family = "L" if kinetic[1] / np.sum(kinetic) >= 0.5 else ("T" if family_signals["T"] > family_signals["V"] else "V")  # Separate lateral from vertical/system-roll motion.
        main_fraction = family_signals[preliminary_family] / max(full_signals[preliminary_family], np.finfo(float).eps)  # Measure main-span participation.
        family = "EDGE" if main_fraction < 0.20 else preliminary_family  # Isolate local side-span modes before numbering.
        selected = {"L": common_lateral, "V": common_vertical, "T": roll_vertical, "EDGE": common_lateral if kinetic[1] / np.sum(kinetic) >= 0.5 else common_vertical}[family]  # Select its shape ordinate.
        correlation = symmetry_correlation(main_x, np.asarray(selected, dtype=float))  # Measure midpoint parity.
        parity = "S" if correlation >= 0.0 else "A"  # Map positive/negative correlation to symmetric/antisymmetric.
        half_wave_order, template_mac = half_wave_match(main_x, np.asarray(selected, dtype=float)) if family != "EDGE" else (0, 0.0)  # Identify the physical main-span branch.
        records.append({  # Record mode metrics.
            "mode": mode_index + 1,  # Use one-based numbering.
            "frequency_hz": float(frequency_hz),  # Store the eigenfrequency.
            "family": family,  # Store L, V, T, or X.
            "span_parity": parity,  # Store S or A.
            "provisional_label": f"{family}{parity}",  # Provide a family label before sequence numbering.
            "symmetry_correlation": correlation,  # Store the signed shape correlation.
            "mass_energy_x_fraction": float(kinetic[0] / np.sum(kinetic)),  # Store axial kinetic fraction.
            "mass_energy_y_fraction": float(kinetic[1] / np.sum(kinetic)),  # Store lateral kinetic fraction.
            "mass_energy_z_fraction": float(kinetic[2] / np.sum(kinetic)),  # Store vertical kinetic fraction.
            "signal_L": family_signals["L"],  # Store the main-span lateral metric.
            "signal_V": family_signals["V"],  # Store the main-span vertical metric.
            "signal_T": family_signals["T"],  # Store the main-span roll metric.
            "signal_X": family_signals["X"],  # Store the main-span axial metric.
            "main_span_signal_fraction": main_fraction,  # Store the edge-mode screening metric.
            "half_wave_order": half_wave_order,  # Store the matched number of main-span half waves.
            "template_mac": template_mac,  # Store the sign-invariant sine-template MAC.
        })  # Finish one record.
    frame = pd.DataFrame(records)  # Form the modal table.
    counters: dict[str, int] = {}  # Number repeated family/parity labels.
    labels: list[str] = []  # Collect final labels.
    for key in frame["provisional_label"]:  # Traverse modes in frequency order.
        counters[key] = counters.get(key, 0) + 1  # Increment family sequence.
        labels.append(f"{key}{counters[key]}")  # Form labels such as LS1 or EDGES1.
    frame["sequence_label"] = labels  # Preserve family-and-parity frequency-order numbering used by Attachment 2-3.
    frame["half_wave_fingerprint"] = [validation_label(str(row.family), int(row.half_wave_order), str(row.sequence_label)) for row in frame.itertuples(index=False)]  # Keep the sine-template branch as a diagnostic, not an attachment renumbering.
    frame["label"] = frame["sequence_label"]  # Report the conventional within-family frequency sequence unless attachment vectors permit a MAC-based reassignment.
    return frame  # Return the classification table.


def plot_topology(parsed: dict[str, object], model: dict[str, object], output_path: Path) -> None:  # Plot the exact double-MCT topology.
    source_nodes = parsed["nodes"]  # Read source geometry.
    station_records = model["passage_records"]  # Read finite-link stations.
    carrying_ids = list(range(1, 729))  # Follow the reviewed carrying main chain.
    gantry_ids = list(range(1001, 1396))  # Follow the reviewed gantry-rope chain.
    fig, axes = plt.subplots(2, 1, figsize=(14, 8.5), constrained_layout=True)  # Create elevation and plan views.
    for ids, color, label in ((carrying_ids, "#1f77b4", "承重索 MCT"), (gantry_ids, "#d95f02", "门架索 MCT")):  # Draw both longitudinal chains.
        x = np.array([source_nodes[node_id][0] - MCT_X_ORIGIN_M for node_id in ids if node_id in source_nodes])  # Read shifted longitudinal coordinates.
        z = np.array([source_nodes[node_id][2] for node_id in ids if node_id in source_nodes])  # Read elevations.
        axes[0].plot(x, z, color=color, linewidth=1.1, label=label)  # Plot the common side elevation.
    for element_id in range(1395, 1466):  # Draw all 71 source gate connections.
        element = parsed["elements"][element_id]  # Read the gate endpoints.
        n1 = source_nodes[int(element["n1"])]  # Read the lower point.
        n2 = source_nodes[int(element["n2"])]  # Read the upper point.
        axes[0].plot([n1[0] - MCT_X_ORIGIN_M, n2[0] - MCT_X_ORIGIN_M], [n1[2], n2[2]], color="#777777", linewidth=0.5, alpha=0.8)  # Draw a shifted gate stem.
    axes[0].scatter([record["x_centerline_m"] for record in station_records], [source_nodes[int(record["bottom_node"])][2] for record in station_records], s=22, color="#2ca02c", zorder=4, label="21 道四端口凝聚接口")  # Mark exact passage centers.
    axes[0].set_xlabel("顺桥向 X / m")  # Label the abscissa.
    axes[0].set_ylabel("高程 Z / m")  # Label the ordinate.
    axes[0].set_title("单幅 MCT 侧视：承重索—71 门架—门架索")  # State the retained topology.
    axes[0].grid(alpha=0.22)  # Add a light grid.
    axes[0].legend(ncol=3, fontsize=9)  # Show component labels.
    x_all = np.array([source_nodes[node_id][0] - MCT_X_ORIGIN_M for node_id in carrying_ids if node_id in source_nodes])  # Read shifted plan-view coordinates.
    for y, name, color in ((-HALF_CATWALK_SPACING_M, "左幅完整 MCT", "#1f77b4"), (HALF_CATWALK_SPACING_M, "右幅完整 MCT", "#d95f02")):  # Draw two MCT planes.
        axes[1].plot(x_all, np.full_like(x_all, y), color=color, linewidth=2.0, label=name)  # Draw one plane centerline.
    for record in station_records:  # Draw every finite passage link.
        axes[1].plot([record["x_centerline_m"], record["x_centerline_m"]], [-HALF_CATWALK_SPACING_M, HALF_CATWALK_SPACING_M], color="#2ca02c", linewidth=1.2, alpha=0.85)  # Connect the two planes.
    axes[1].set_xlabel("顺桥向 X / m")  # Label the plan abscissa.
    axes[1].set_ylabel("横桥向 Y / m")  # Label transverse position.
    axes[1].set_title("双 MCT 平面 + 21 道门架—横通道四端口等效杆组")  # State the corrected topology.
    axes[1].grid(alpha=0.22)  # Add a light grid.
    axes[1].legend(ncol=2, fontsize=9)  # Show plane labels.
    fig.savefig(output_path, dpi=180)  # Save a readable audit figure.
    plt.close(fig)  # Release memory.


def plot_mode_shapes(parsed: dict[str, object], model: dict[str, object], modal_table: pd.DataFrame, modes: np.ndarray, output_path: Path, count: int = 12) -> None:  # Plot main-span observables.
    source_nodes = parsed["nodes"]  # Read source geometry.
    index = model["index"]  # Read duplicate node mapping.
    main_ids = [node_id for node_id in sorted(source_nodes) if 155 <= node_id <= 448]  # Select the main carrying chain.
    x = np.array([source_nodes[node_id][0] - MCT_X_ORIGIN_M for node_id in main_ids], dtype=float)  # Form the shifted X axis.
    fig, axes = plt.subplots(4, 3, figsize=(14, 11), sharex=True, constrained_layout=True)  # Create a compact twelve-mode panel.
    for mode_index, axis in enumerate(axes.flat[:count]):  # Draw one observable per mode.
        vector = modes[:, mode_index].reshape((-1, 3))  # Reshape translations.
        left = np.vstack([vector[index[(0, node_id)]] for node_id in main_ids])  # Read left-width motion.
        right = np.vstack([vector[index[(1, node_id)]] for node_id in main_ids])  # Read right-width motion.
        label = str(modal_table.iloc[mode_index]["label"])  # Read the classified family.
        family = str(modal_table.iloc[mode_index]["family"])  # Read the dominant family.
        if family == "L":  # Plot common lateral motion.
            ordinate = 0.5 * (left[:, 1] + right[:, 1])  # Form the common lateral shape.
            ylabel = "共横移"  # State the observable.
        elif family == "T":  # Plot system roll.
            ordinate = (right[:, 2] - left[:, 2]) / (2.0 * HALF_CATWALK_SPACING_M)  # Convert differential vertical motion to roll.
            ylabel = "系统转角"  # State the observable.
        elif family == "V":  # Plot common vertical motion.
            ordinate = 0.5 * (left[:, 2] + right[:, 2])  # Form the common vertical shape.
            ylabel = "共竖移"  # State the observable.
        else:  # Plot common longitudinal motion.
            ordinate = 0.5 * (left[:, 0] + right[:, 0])  # Form the common longitudinal shape.
            ylabel = "共纵移"  # State the observable.
        scale = float(np.max(np.abs(ordinate))) or 1.0  # Normalize without division by zero.
        axis.plot(x, ordinate / scale, color="#204a87", linewidth=1.2)  # Draw the normalized shape.
        axis.axhline(0.0, color="#888888", linewidth=0.5)  # Mark zero displacement.
        axis.set_title(f"M{mode_index + 1} {label}  {modal_table.iloc[mode_index]['frequency_hz']:.4f} Hz\n{ylabel}", fontsize=9)  # Label mode and frequency.
        axis.grid(alpha=0.18)  # Add a light grid.
    for axis in axes[-1, :]:  # Label the bottom row.
        axis.set_xlabel("X / m")  # State the longitudinal coordinate.
    fig.savefig(output_path, dpi=180)  # Save the mode-shape audit figure.
    plt.close(fig)  # Release memory.


def write_outputs(parsed: dict[str, object], model: dict[str, object], modal_table: pd.DataFrame, modes: np.ndarray, mct_path: Path, station_path: Path, output_dir: Path) -> None:  # Write all reproducibility artifacts.
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the dedicated result directory.
    pd.DataFrame(model["node_records"]).to_csv(output_dir / "double_mct_nodes.csv", index=False)  # Write node provenance.
    pd.DataFrame(model["element_records"]).to_csv(output_dir / "double_mct_source_elements.csv", index=False)  # Write retained MCT elements.
    pd.DataFrame(model["passage_records"]).to_csv(output_dir / "cross_passage_equivalent_links.csv", index=False)  # Write the 21 link definitions.
    modal_table.to_csv(output_dir / "modal_properties.csv", index=False)  # Write classified modal properties.
    mode_limit = min(24, modes.shape[1])  # Limit the vector file to useful low modes.
    np.savez_compressed(output_dir / "mode_vectors_first24.npz", modes=modes[:, :mode_limit], xyz=model["xyz"], free_dofs=model["free_dofs"])  # Save exact vectors for response reduction.
    plot_topology(parsed, model, output_dir / "double_mct_topology.png")  # Render the corrected topology.
    plot_mode_shapes(parsed, model, modal_table, modes, output_dir / "mode_shapes_first12.png")  # Render low-mode shapes.
    total_mass_kg = float(np.sum(model["nodal_mass_kg"]))  # Compute total physical mass once.
    audit = {  # Build the machine-readable calculation record.
        "status": "DOUBLE_MCT_FOUR_PORT_MODAL_MODEL",  # State the completed structural-reduction stage.
        "model_description": "two complete MCT planes with explicit carrying and gantry ropes, 50 finite-gate rank-one replacements per width, and 21 four-rope-port condensed finite-gate/cross-passage assemblies",  # Describe topology precisely.
        "authoritative_inputs": {  # Bind source files.
            "mct_path": str(mct_path),  # Record the local MCT path.
            "mct_sha256": sha256_file(mct_path),  # Record its exact content hash.
            "station_map_path": str(station_path),  # Record the station map path.
            "station_map_sha256": sha256_file(station_path),  # Record its content hash.
            "four_port_matrix_path": str(model["passage_matrix_path"]),  # Record the condensed finite-gate/passage source.
            "four_port_matrix_sha256": str(model["passage_matrix_sha256"]),  # Bind the complete non-diagonal matrix.
            "ordinary_gate_condensation_audit_path": str(model["gate_only_audit_path"]),  # Record the finite-gate-only condensation source.
            "ordinary_gate_condensation_audit_sha256": str(model["gate_only_audit_sha256"]),  # Bind the ordinary-gate replacement parameters.
        },  # Finish input binding.
        "counts": {  # Record topology counts.
            "source_mct_nodes_per_width": len(parsed["nodes"]),  # Count one MCT plane.
            "source_mct_elements_per_width": len(parsed["elements"]),  # Count one MCT element set.
            "double_mct_nodes": len(model["xyz"]),  # Count duplicated nodes.
            "double_mct_elements": len(model["element_records"]),  # Count duplicated source elements.
            "finite_passage_links": len(model["passage_records"]),  # Count passage links.
            "ordinary_gate_rank_one_replacements": 2 * len(model["ordinary_gate_elements"]),  # Count 50 replacements in each complete MCT plane.
            "total_translational_dofs": len(model["dof_mass_kg"]),  # Count all translation DOFs.
            "free_translational_dofs": len(model["free_dofs"]),  # Count reduced DOFs.
        },  # Finish counts.
        "mass_closure": {  # Record mass components.
            "distributed_rope_mass_tonne": float(model["distributed_mass_kg"]) / 1000.0,  # Report duplicated cable mass.
            "second_stage_lumped_mass_tonne": float(model["concentrated_mass_kg"]) / 1000.0,  # Report duplicated nodal mass.
            "equivalent_passage_added_mass_tonne": 0.0,  # Confirm no duplicate passage mass.
            "total_mass_tonne": total_mass_kg / 1000.0,  # Report full double-width mass.
            "target_total_mass_tonne": 4108.46690758,  # State the independent audit target.
            "target_error_tonne": total_mass_kg / 1000.0 - 4108.46690758,  # Quantify closure error.
        },  # Finish mass closure.
        "passage_four_port_condensation": {  # Record the adopted complete interface model.
            "topology": "representative H10: two 30-BEAM188 finite gates plus one 639-BEAM188 passage assembly, 699 BEAM188 total, 74 internal ALL rigid links and 44 external rope-interface groups",  # State the condensed topology.
            "port_order": ["B_L_UX", "B_L_UY", "B_L_UZ", "T_L_UX", "T_L_UY", "T_L_UZ", "B_R_UX", "B_R_UY", "B_R_UZ", "T_R_UX", "T_R_UY", "T_R_UZ"],  # Freeze connection order.
            "assembly_rule": "rotate the full 12x12 matrix to each local carrying-rope slope and retain every off-diagonal term",  # State the virtual-work transformation.
            "replaced_mct_gate_elements": model["replaced_gate_elements"],  # Identify deleted planar TRUSS surrogates.
            "matrix_rigid_modes": 6,  # Record the independently verified three translations and three rotations.
            "matrix_positive_deformation_modes": 6,  # Record the retained generalized deformation springs.
            "added_density": 0.0,  # Prevent passage mass duplication.
        },  # Finish passage model.
        "ordinary_gate_condensation": {  # Record the non-passage gate replacement.
            "representative_gate": "H10 finite gate, 30 BEAM188 and 22 rope translation interfaces",  # State the condensed source topology.
            "source_property3_elements_per_width": model["ordinary_gate_elements"],  # Identify all 50 source surrogates.
            "equivalent_ea_n": float(model["gate_only_equivalent_ea_n"]),  # Report the asserted constant condensed axial rigidity.
            "representative_axial_stiffness_n_per_mm": 24925.700817808793,  # Report the H10 8.000 m value for independent checking.
            "original_property3_stiffness_ratio": 0.1977101567931475,  # Quantify the correction relative to the MCT planar surrogate.
            "translation_port_rank": 1,  # State the one objective deformation mode.
            "zero_mechanism_count": 5,  # State the five freely rotating two-port mechanisms.
            "assembly_rule": "delete each ordinary property-3 TRUSS and re-form (EAeq/L) nn^T along the station-specific bottom-to-gantry chord",  # State the exact replacement rule.
            "added_density": 0.0,  # Prevent gate or guide mass duplication.
        },  # Finish ordinary-gate model.
        "limitations": [  # State current boundaries.
            "This phase validates topology and low modes only; prior one-cable V/T buffeting results are withdrawn.",  # Withdraw superseded results.
            "One representative H10 condensed matrix is rotated and reused at all 21 stations; station-specific gate/passage condensation remains a refinement.",  # State the representative-station approximation.
            "The translation-only ordinary-gate replacement retains its objective axial mode but no portal shear; a rotational-port model is required to retain finite transverse portal action without artificial rigid-rotation energy.",  # State the ordinary-gate reduction boundary.
            "The main model labels global -Y as L and +Y as R, whereas the APDL condensation names +Y as CW1/L; matrix assembly follows coordinates exactly, so only the textual side labels differ.",  # Prevent a false left-right interface interpretation.
            "Each width's local gate roll is recoverable from carrying-rope versus gantry-rope relative lateral translation; within-deck warping and individual physical-rope torsion are not retained.",  # State the retained torsional meaning.
        ],  # Finish limitations.
    }  # Finish the audit object.
    (output_dir / "model_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")  # Write the audit file.


def parse_args() -> argparse.Namespace:  # Define the command-line interface.
    parser = argparse.ArgumentParser(description="Build a two-MCT catwalk model with finite equivalent cross-passage links.")  # Create the parser.
    parser.add_argument("--mct", type=Path, default=Path("tmp/mct_pair_sources/catwalk_gantry_rope_combined_2.mct"))  # Accept the reviewed MCT path.
    parser.add_argument("--stations", type=Path, default=Path("tmp/mct_pair_sources/passage_station_authoritative_map.csv"))  # Accept the authoritative station map.
    parser.add_argument("--output", type=Path, default=Path("output/double_mct_results"))  # Accept a result directory.
    parser.add_argument("--modes", type=int, default=40)  # Request enough low modes for family screening.
    parser.add_argument("--passage-matrix", type=Path, default=DEFAULT_FOUR_PORT_MATRIX)  # Accept a labelled four-rope-port 12x12 matrix in N/mm.
    return parser.parse_args()  # Return parsed values.


def main() -> None:  # Run source checks, assembly, eigenanalysis, and audit output.
    args = parse_args()  # Read command-line values.
    actual_hash = sha256_file(args.mct)  # Hash the source before parsing.
    if actual_hash != EXPECTED_MCT_SHA256:  # Prevent an unreviewed MCT substitution.
        raise ValueError(f"MCT SHA-256 mismatch: {actual_hash}")  # Stop with the observed hash.
    parsed = parse_mct(args.mct)  # Parse the reviewed model.
    station_map = pd.read_csv(args.stations, encoding="utf-8-sig")  # Read exact 21-station MCT mapping.
    if len(station_map) != 21:  # Enforce the report schedule.
        raise ValueError(f"Expected 21 cross passages, found {len(station_map)}")  # Stop on station drift.
    model = build_double_model(parsed, station_map, args.passage_matrix)  # Assemble the corrected topology.
    frequencies_hz, modes = solve_modes(model, args.modes)  # Solve the low modes.
    modal_table = classify_modes(parsed, model, frequencies_hz, modes)  # Classify physical families.
    write_outputs(parsed, model, modal_table, modes, args.mct, args.stations, args.output)  # Write auditable results.
    print(modal_table.head(20).to_string(index=False))  # Show the first twenty modes in the run log.
    print(f"total_mass_tonne={np.sum(model['nodal_mass_kg']) / 1000.0:.9f}")  # Show mass closure.


if __name__ == "__main__":  # Run only as a script.
    main()  # Execute the calculation.
