from __future__ import annotations  # Enable stable modern type annotations.
import json  # Write deterministic extracted passage data.
import urllib.request  # Download the immutable public C3 release asset inside the runner.
from collections import defaultdict  # Accumulate element blocks and equation connectivity.
from pathlib import Path  # Resolve deterministic local and output paths.
import numpy as np  # Evaluate coordinate windows and extents.

HERE = Path(__file__).resolve().parent  # Locate the inverse-form-finding calculation directory.
OUT = HERE / "c3_midspan_passage_extract"  # Define the isolated extraction directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the extraction directory idempotently.
URL = "https://github.com/Hiram-test/model/releases/download/c3-ft14-parser-safe-667c5047/C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"  # Freeze the audited release URL.
DECK = OUT / "C3.inp"  # Define the temporary downloaded deck path.
SEED_SET = "UG64_0084"  # Select the flat main-span-midpoint passage block identified by coordinate audit.
X_MARGIN_MM = 2000.0  # Retain the full 1.5-m passage longitudinal width and nearby connection nodes.
Y_LIMIT_MM = 26000.0  # Retain both catwalks and the complete 49.655-m passage width.
Z_BELOW_MM = 3500.0  # Retain the 1.7-m triangular passage depth and nearby lower connections.
Z_ABOVE_MM = 12000.0  # Retain the complete approximately 9-m high passage support frame.


def parse_options(line: str) -> dict[str, str]:  # Parse comma-separated CalculiX keyword options.
    output: dict[str, str] = {}  # Initialize the normalized option mapping.
    for token in line.strip().split(",")[1:]:  # Traverse all options after the keyword name.
        if "=" in token:  # Test whether the option has an explicit value.
            key, value = token.split("=", 1)  # Split the option once.
            output[key.strip().upper()] = value.strip()  # Store the normalized option.
        else:  # Handle a flag-style option.
            output[token.strip().upper()] = ""  # Store the normalized flag.
    return output  # Return the parsed keyword options.


def main() -> int:  # Download, parse, isolate, and export the midspan passage substructure.
    urllib.request.urlretrieve(URL, DECK)  # Download the immutable C3 release deck.
    lines = DECK.read_text(encoding="utf-8", errors="replace").splitlines()  # Read the complete deck tolerantly.
    nodes: dict[int, np.ndarray] = {}  # Initialize all node coordinates.
    elements: dict[int, dict] = {}  # Initialize all element connectivity records.
    element_blocks: dict[str, list[int]] = defaultdict(list)  # Initialize direct element-block membership.
    equations: list[list[tuple[int, int, float]]] = []  # Initialize all multipoint equation records.
    keyword = ""  # Initialize the active keyword name.
    options: dict[str, str] = {}  # Initialize active keyword options.
    current_type = ""  # Initialize active element type.
    current_set = ""  # Initialize active direct element-set name.
    equation_terms_expected = 0  # Initialize the number of terms expected in the active equation.
    equation_buffer: list[float] = []  # Initialize the active equation numeric buffer.
    for raw in lines:  # Traverse every deck line once.
        line = raw.strip()  # Remove leading and trailing whitespace.
        if not line or line.startswith("**"):  # Skip blank and comment lines.
            continue  # Continue to the next physical line.
        if line.startswith("*"):  # Detect a new CalculiX keyword.
            keyword = line.split(",", 1)[0].strip().upper()  # Normalize the keyword name.
            options = parse_options(line)  # Parse keyword options.
            current_type = options.get("TYPE", "") if keyword == "*ELEMENT" else ""  # Read the active element type.
            current_set = options.get("ELSET", "") if keyword == "*ELEMENT" else ""  # Read the active direct element set.
            equation_terms_expected = 0  # Reset any prior equation term count.
            equation_buffer = []  # Reset any prior equation buffer.
            continue  # Continue to the first data line under the keyword.
        fields = [field.strip() for field in line.split(")") if False]  # Keep the parser explicitly comma-based without hidden token rewriting.
        values = [field.strip() for field in line.split(",") if field.strip()]  # Parse all nonempty comma-separated fields.
        if keyword == "*NODE" and len(values) >= 4:  # Parse one node record.
            node_id = int(values[0])  # Read the node identifier.
            nodes[node_id] = np.array([float(values[1]), float(values[2]), float(values[3])], dtype=float)  # Store its coordinate vector.
        elif keyword == "*ELEMENT" and len(values) >= 2:  # Parse one element record.
            element_id = int(values[0])  # Read the element identifier.
            connectivity = [int(value) for value in values[1:]]  # Read all listed element nodes.
            elements[element_id] = {"type": current_type, "set": current_set, "nodes": connectivity}  # Store the element record.
            if current_set:  # Test whether this block declares an element set.
                element_blocks[current_set].append(element_id)  # Add the element to its direct block set.
        elif keyword == "*EQUATION":  # Parse one possibly multiline multipoint equation.
            if equation_terms_expected == 0:  # Test whether this is the equation-term-count line.
                equation_terms_expected = int(values[0])  # Read the number of node-DOF-coefficient terms.
                equation_buffer = []  # Initialize the equation numeric buffer.
            else:  # Handle one continuation line of equation terms.
                equation_buffer.extend(float(value) for value in values)  # Append all equation numeric values.
                if len(equation_buffer) >= 3 * equation_terms_expected:  # Test whether the full equation has been read.
                    terms = [(int(equation_buffer[3 * index]), int(equation_buffer[3 * index + 1]), float(equation_buffer[3 * index + 2])) for index in range(equation_terms_expected)]  # Convert the numeric buffer to node-DOF-coefficient terms.
                    equations.append(terms)  # Store the complete equation.
                    equation_terms_expected = 0  # Reset the equation-term count.
                    equation_buffer = []  # Reset the equation buffer.
    seed_elements = element_blocks.get(SEED_SET, [])  # Read the selected flat midspan passage seed block.
    if not seed_elements:  # Reject a missing seed set explicitly.
        raise RuntimeError(f"Seed set {SEED_SET} is absent")  # Report the missing direct block.
    seed_nodes = sorted({node_id for element_id in seed_elements for node_id in elements[element_id]["nodes"]})  # Collect all nodes in the seed block.
    seed_coordinates = np.array([nodes[node_id] for node_id in seed_nodes], dtype=float)  # Stack the seed coordinates.
    x_centre = 0.5 * (float(np.min(seed_coordinates[:, 0])) + float(np.max(seed_coordinates[:, 0])))  # Evaluate the seed passage longitudinal centre.
    z_floor = float(np.median(seed_coordinates[:, 2]))  # Estimate the passage top/floor elevation from the flat seed block.
    local_nodes = sorted([node_id for node_id, coordinate in nodes.items() if abs(float(coordinate[0]) - x_centre) <= X_MARGIN_MM and abs(float(coordinate[1])) <= Y_LIMIT_MM and z_floor - Z_BELOW_MM <= float(coordinate[2]) <= z_floor + Z_ABOVE_MM])  # Select every coordinate-bearing node in the complete local passage envelope.
    local_node_set = set(local_nodes)  # Build an efficient local-node membership set.
    local_elements = sorted([element_id for element_id, record in elements.items() if record["nodes"] and all(node_id in local_node_set for node_id in record["nodes"])])  # Retain elements wholly contained in the local passage envelope.
    local_equations = [terms for terms in equations if any(node_id in local_node_set for node_id, _dof, _coefficient in terms)]  # Retain all equations touching the local passage envelope.
    equation_nodes = sorted({node_id for terms in local_equations for node_id, _dof, _coefficient in terms if node_id in nodes})  # Collect every coordinate-bearing node reached through local equations.
    expanded_node_set = local_node_set | set(equation_nodes)  # Expand the local node set by all equation-linked coordinate nodes.
    expanded_elements = sorted([element_id for element_id, record in elements.items() if record["nodes"] and all(node_id in expanded_node_set for node_id in record["nodes"]) and any(node_id in local_node_set for node_id in record["nodes"])])  # Retain elements connected to local nodes and contained in the expanded set.
    block_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # Initialize local element counts by direct set and type.
    for element_id in expanded_elements:  # Traverse every extracted element.
        record = elements[element_id]  # Read the current element record.
        block_counts[record["set"] or "<NONE>"][record["type"]] += 1  # Count the current local element.
    coordinate_records = [{"node": int(node_id), "x": float(nodes[node_id][0]), "y": float(nodes[node_id][1]), "z": float(nodes[node_id][2]), "seed": bool(node_id in set(seed_nodes)), "local_window": bool(node_id in local_node_set), "equation_linked": bool(node_id in set(equation_nodes))} for node_id in sorted(expanded_node_set)]  # Export all extracted node coordinates and roles.
    element_records = [{"element": int(element_id), "type": elements[element_id]["type"], "set": elements[element_id]["set"], "nodes": [int(value) for value in elements[element_id]["nodes"]]} for element_id in expanded_elements]  # Export all extracted element records.
    equation_records = [[{"node": int(node_id), "dof": int(dof), "coefficient": float(coefficient)} for node_id, dof, coefficient in terms] for terms in local_equations]  # Export all local multipoint equations.
    coordinates = np.array([nodes[node_id] for node_id in expanded_node_set], dtype=float)  # Stack expanded local coordinates for extent audit.
    report = {"source_url": URL, "seed_set": SEED_SET, "seed_element_count": len(seed_elements), "seed_node_count": len(seed_nodes), "x_centre": x_centre, "z_floor_estimate": z_floor, "window": {"x_margin_mm": X_MARGIN_MM, "y_limit_mm": Y_LIMIT_MM, "z_below_mm": Z_BELOW_MM, "z_above_mm": Z_ABOVE_MM}, "local_window_node_count": len(local_nodes), "equation_linked_node_count": len(equation_nodes), "expanded_node_count": len(expanded_node_set), "expanded_element_count": len(expanded_elements), "local_equation_count": len(local_equations), "coordinate_minimum": np.min(coordinates, axis=0).tolist(), "coordinate_maximum": np.max(coordinates, axis=0).tolist(), "coordinate_extent": np.ptp(coordinates, axis=0).tolist(), "block_counts": {name: dict(counts) for name, counts in block_counts.items()}, "nodes": coordinate_records, "elements": element_records, "equations": equation_records}  # Assemble the complete extracted passage report.
    (OUT / "c3_midspan_passage_extract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the full machine-readable passage extraction.
    print(json.dumps({key: report[key] for key in ("seed_set", "seed_element_count", "seed_node_count", "x_centre", "z_floor_estimate", "local_window_node_count", "equation_linked_node_count", "expanded_node_count", "expanded_element_count", "local_equation_count", "coordinate_extent", "block_counts")}, ensure_ascii=False, indent=2, sort_keys=True))  # Print the concise extraction summary into the workflow log.
    return 0  # Report successful passage extraction.


if __name__ == "__main__":  # Execute only when invoked as the extraction program.
    raise SystemExit(main())  # Return the extraction status to the operating system.
