#!/usr/bin/env python3  # Execute the strict Track A merger with the active Python interpreter.
from __future__ import annotations  # Keep annotations deterministic on the supported Python runtime.
from collections import Counter  # Compare repeated constraint equations and element families exactly.
from pathlib import Path  # Resolve complete input and audit paths independently of caller cwd.
import argparse  # Read explicit parent, Track, static-mother, output, and root-count arguments.
import hashlib  # Bind every complete input and generated daughter byte stream.
import json  # Publish the complete machine-readable construction audit.
import math  # Evaluate finite geometric lever-arm consistency.
import re  # Parse CalculiX keyword attributes, sparse equations, and numerical fields.
from typing import Iterable  # Describe deterministic line and sparse-term collections.
class BuildError(RuntimeError):  # Represent one strict model-construction failure.
    pass  # Keep the semantic exception behavior-free.
def require(condition: bool, code: str, detail: str) -> None:  # Enforce one explicit construction invariant.
    if not condition:  # Reject every condition not positively established.
        raise BuildError(f"{code}: {detail}")  # Surface a stable code with bounded context.
def sha256_file(path: Path) -> str:  # Compute one exact file identity by streaming.
    digest = hashlib.sha256()  # Initialize a fresh SHA-256 state.
    with path.open("rb") as handle:  # Open the complete file without decoding.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Traverse fixed-size blocks to EOF.
            digest.update(block)  # Bind each exact byte once.
    return digest.hexdigest()  # Return the lowercase hexadecimal identity.
def keyword_attributes(line: str) -> dict[str, str]:  # Parse comma-separated CalculiX keyword attributes.
    attributes: dict[str, str] = {}  # Initialize the normalized attribute mapping.
    for field in line.split(",")[1:]:  # Traverse fields after the leading keyword.
        if "=" not in field:  # Ignore flag-only attributes.
            continue  # Continue to the next field.
        key, value = field.split("=", 1)  # Split one key-value attribute.
        attributes[key.strip().upper()] = value.strip()  # Preserve the normalized key and original value.
    return attributes  # Return the parsed attribute mapping.
def read_lines(path: Path) -> list[str]:  # Read one complete ASCII CalculiX deck with stable line endings.
    require(path.is_file(), "INPUT_MISSING", str(path))  # Require the selected input file.
    return path.read_text(encoding="ascii", errors="strict").splitlines()  # Decode the complete deck without retaining newline characters.
def first_step_index(lines: list[str]) -> int:  # Locate the first analysis-step keyword.
    for index, raw in enumerate(lines):  # Traverse every input line in order.
        if raw.strip().upper().startswith("*STEP"):  # Detect the first step header.
            return index  # Return its zero-based line index.
    raise BuildError("STEP_NOT_FOUND")  # Reject a deck without any analysis step.
def split_steps(lines: list[str]) -> list[list[str]]:  # Split the analysis tail into complete STEP to END STEP blocks.
    start = first_step_index(lines)  # Locate the first analysis-step line.
    steps: list[list[str]] = []  # Accumulate complete step blocks.
    current: list[str] | None = None  # Hold the active step block.
    for raw in lines[start:]:  # Traverse the analysis tail only.
        upper = raw.strip().upper()  # Normalize keyword matching.
        if upper.startswith("*STEP"):  # Start one new analysis step.
            require(current is None, "NESTED_STEP", raw)  # Reject an unterminated prior step.
            current = [raw]  # Initialize the current step with its exact header.
            continue  # Continue to the next line.
        require(current is not None, "ANALYSIS_TAIL_OUTSIDE_STEP", raw[:120])  # Require every analysis-tail line to belong to a step.
        current.append(raw)  # Preserve the exact analysis line.
        if upper.startswith("*END STEP"):  # Detect the current step terminator.
            steps.append(current)  # Preserve the complete step block.
            current = None  # Clear the active step state.
    require(current is None, "UNTERMINATED_STEP", str(len(lines)))  # Reject a truncated final step.
    require(bool(steps), "NO_COMPLETE_STEPS", str(len(lines)))  # Require at least one complete step.
    return steps  # Return the complete ordered step sequence.
def step_has_keyword(step: list[str], prefix: str) -> bool:  # Test whether one step contains a keyword prefix.
    normalized = prefix.upper()  # Normalize the requested keyword prefix.
    return any(raw.strip().upper().startswith(normalized) for raw in step)  # Return the keyword-presence result.
def parse_nodes(lines: list[str]) -> dict[int, tuple[float, float, float]]:  # Parse every model-level node coordinate preceding the first step.
    nodes: dict[int, tuple[float, float, float]] = {}  # Initialize the node-coordinate mapping.
    active = False  # Track one NODE block.
    for raw in lines[:first_step_index(lines)]:  # Traverse model definitions only.
        line = raw.strip()  # Normalize surrounding whitespace.
        upper = line.upper()  # Normalize keyword matching.
        if not line or line.startswith("**"):  # Ignore blank and comment rows.
            continue  # Continue traversal.
        if upper.startswith("*"):  # Handle one keyword record.
            active = upper == "*NODE" or upper.startswith("*NODE,")  # Select coordinate-definition blocks only.
            continue  # Complete keyword handling.
        if not active:  # Ignore non-node data rows.
            continue  # Continue traversal.
        fields = [field.strip() for field in line.split(",")]  # Split node label and coordinates.
        require(len(fields) >= 4, "NODE_ROW_INVALID", line[:120])  # Require three coordinate values.
        node = int(fields[0])  # Parse the node label.
        require(node not in nodes, "NODE_DUPLICATE", str(node))  # Reject coordinate collisions.
        nodes[node] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Preserve the exact coordinate.
    return nodes  # Return the complete model-level node mapping.
def parse_elements(lines: list[str]) -> dict[int, dict[str, object]]:  # Parse every model-level element preceding the first step.
    elements: dict[int, dict[str, object]] = {}  # Initialize the element mapping.
    active_type: str | None = None  # Track one ELEMENT block type.
    active_elset: str | None = None  # Track one ELEMENT block set.
    for raw in lines[:first_step_index(lines)]:  # Traverse model definitions only.
        line = raw.strip()  # Normalize surrounding whitespace.
        upper = line.upper()  # Normalize keyword matching.
        if not line or line.startswith("**"):  # Ignore blank and comment rows.
            continue  # Continue traversal.
        if upper.startswith("*"):  # Handle one keyword record.
            active_type = None  # Close any prior element block.
            active_elset = None  # Close the prior element set.
            if upper.startswith("*ELEMENT,"):  # Parse one element header.
                attributes = keyword_attributes(line)  # Recover the header attributes.
                active_type = attributes.get("TYPE", "").upper()  # Select the normalized element type.
                active_elset = attributes.get("ELSET")  # Select the optional element set.
                require(bool(active_type), "ELEMENT_TYPE_MISSING", line)  # Require an explicit element type.
            continue  # Complete keyword handling.
        if active_type is None:  # Ignore non-element data rows.
            continue  # Continue traversal.
        values = [int(field.strip()) for field in line.split(",") if field.strip()]  # Parse element and connectivity labels.
        require(bool(values), "ELEMENT_ROW_INVALID", line[:120])  # Require one element label.
        element = values[0]  # Select the element label.
        require(element not in elements, "ELEMENT_DUPLICATE", str(element))  # Reject element-label collisions.
        elements[element] = {"type": active_type, "elset": active_elset, "connectivity": tuple(values[1:])}  # Preserve type, set, and connectivity.
    return elements  # Return the complete model-level element mapping.
def parse_equations(lines: list[str]) -> list[tuple[tuple[int, int, float], ...]]:  # Parse every model-level sparse constraint equation.
    equations: list[tuple[tuple[int, int, float], ...]] = []  # Initialize the ordered equation list.
    prefix = lines[:first_step_index(lines)]  # Select model definitions only.
    index = 0  # Initialize zero-based line traversal.
    while index < len(prefix):  # Traverse every model-definition line.
        upper = prefix[index].strip().upper()  # Normalize the current line.
        if upper != "*EQUATION":  # Skip non-equation keywords and data.
            index += 1  # Advance to the next line.
            continue  # Continue traversal.
        require(index + 1 < len(prefix), "TRUNCATED_EQUATION_DECLARATION", str(index + 1))  # Require the declared-arity row.
        declared = int(prefix[index + 1].strip().split(",")[0])  # Parse the declared sparse term count.
        fields: list[str] = []  # Accumulate continuation fields.
        cursor = index + 2  # Start reading equation-body rows.
        while cursor < len(prefix) and len(fields) < 3 * declared:  # Consume the complete sparse equation body.
            body = prefix[cursor].strip()  # Normalize the continuation row.
            require(not body.startswith("*"), "TRUNCATED_EQUATION_BODY", str(index + 1))  # Reject an interrupted body.
            fields.extend(field.strip() for field in body.split(",") if field.strip())  # Append nonempty sparse fields.
            cursor += 1  # Advance to the next continuation row.
        require(len(fields) == 3 * declared, "EQUATION_ARITY_MISMATCH", f"line={index + 1} declared={declared} fields={len(fields)}")  # Require the exact declared arity.
        terms = tuple((int(fields[3 * position]), int(fields[3 * position + 1]), float(fields[3 * position + 2].replace("D", "E").replace("d", "e"))) for position in range(declared))  # Parse node, DOF, and coefficient triples.
        equations.append(terms)  # Preserve the complete ordered equation.
        index = cursor  # Advance beyond the equation body.
    return equations  # Return the complete ordered equation list.
def equation_key(terms: tuple[tuple[int, int, float], ...]) -> tuple[tuple[int, int, float], ...]:  # Normalize one equation for exact multiset comparison.
    return tuple(sorted(((node, dof, round(coefficient, 12)) for node, dof, coefficient in terms), key=lambda item: (item[0], item[1], item[2])))  # Sort sparse terms and round parser noise.
def added_equations(parent: list[tuple[tuple[int, int, float], ...]], daughter: list[tuple[tuple[int, int, float], ...]]) -> list[tuple[tuple[int, int, float], ...]]:  # Recover daughter-only equations as an ordered multiset difference.
    inventory = Counter(equation_key(terms) for terms in parent)  # Count inherited parent equation signatures.
    additions: list[tuple[tuple[int, int, float], ...]] = []  # Accumulate daughter-only equations.
    for terms in daughter:  # Traverse daughter equations in original order.
        key = equation_key(terms)  # Normalize the current equation signature.
        if inventory[key] > 0:  # Match one inherited parent occurrence.
            inventory[key] -= 1  # Consume the inherited equation occurrence.
        else:  # Preserve equations absent from the parent multiset.
            additions.append(terms)  # Append one daughter-only equation.
    return additions  # Return the ordered daughter-only equations.
def render_equation(terms: tuple[tuple[int, int, float], ...]) -> str:  # Render one sparse equation in old-ANSYS-style notation.
    labels = {1: "UX", 2: "UY", 3: "UZ", 4: "ROTX", 5: "ROTY", 6: "ROTZ"}  # Map CalculiX DOFs to engineering labels.
    return " ".join(f"{coefficient:+.12g}*{labels.get(dof, f'DOF{dof}')}({node})" for node, dof, coefficient in terms) + " = 0"  # Return the complete homogeneous equation.
def rigid_formula_check(terms: tuple[tuple[int, int, float], ...], added_nodes: set[int], nodes: dict[int, tuple[float, float, float]]) -> dict[str, object]:  # Compare one equation against u_low equals u_high plus theta cross r.
    translations = [(node, dof, coefficient) for node, dof, coefficient in terms if dof in {1, 2, 3} and abs(abs(coefficient) - 1.0) <= 1.0e-8]  # Select unit translation terms.
    rotations = [(node, dof, coefficient) for node, dof, coefficient in terms if dof in {4, 5, 6}]  # Select rotational terms.
    if len(translations) < 2 or not rotations:  # Require a translation pair and at least one rotation term.
        return {"recognized": False, "maximum_error": None}  # Return an explicit unrecognized state.
    high_candidates = [node for node, _, _ in translations if node in added_nodes]  # Select translation terms on added high-master nodes.
    if not high_candidates:  # Fall back to a rotational-term node when the high master lacks a translation term.
        high_candidates = [node for node, _, _ in rotations if node in added_nodes]  # Select added nodes carrying rotations.
    if not high_candidates:  # Require a recoverable high-master identity.
        return {"recognized": False, "maximum_error": None}  # Return an explicit unrecognized state.
    high_node = high_candidates[0]  # Select the inferred high master.
    low_candidates = [node for node, _, _ in translations if node != high_node and node in nodes]  # Select the opposite translation node.
    if not low_candidates or high_node not in nodes:  # Require both geometric points.
        return {"recognized": False, "maximum_error": None}  # Return an explicit unrecognized state.
    low_node = low_candidates[0]  # Select the inferred lower node.
    high_xyz = nodes[high_node]  # Select the high-master coordinate.
    low_xyz = nodes[low_node]  # Select the lower-node coordinate.
    rx, ry, rz = (low_xyz[index] - high_xyz[index] for index in range(3))  # Form the high-master-to-low-node offset vector.
    expected_by_translation = {1: {5: -rz, 6: ry}, 2: {4: rz, 6: -rx}, 3: {4: -ry, 5: rx}}  # Encode u_low minus u_high minus theta cross r equals zero up to equation orientation.
    low_terms = [(node, dof, coefficient) for node, dof, coefficient in translations if node == low_node]  # Select lower-node translation terms.
    high_terms = [(node, dof, coefficient) for node, dof, coefficient in translations if node == high_node]  # Select high-master translation terms.
    if not low_terms or not high_terms:  # Require one translation term on each point.
        return {"recognized": False, "maximum_error": None, "offset": (rx, ry, rz)}  # Return geometry without claiming formula recognition.
    translation_dof = low_terms[0][1]  # Select the constrained translation component.
    low_sign = low_terms[0][2]  # Select the lower-node translation coefficient.
    expected = expected_by_translation.get(translation_dof, {})  # Select the rigid-offset rotational coefficients for that component.
    errors = [abs(observed - low_sign * expected.get(rotation_dof, 0.0)) for _, rotation_dof, observed in rotations]  # Compare every observed rotational coefficient after matching equation orientation.
    return {"recognized": bool(errors), "maximum_error": max(errors) if errors else None, "offset": (rx, ry, rz), "low_node": low_node, "high_node": high_node, "translation_dof": translation_dof}  # Return the complete rigid-formula audit.
def parse_keyword_blocks(lines: list[str]) -> list[list[str]]:  # Split model definitions into keyword-led blocks while retaining comments and data.
    blocks: list[list[str]] = []  # Accumulate keyword blocks.
    current: list[str] = []  # Hold the active block.
    for raw in lines:  # Traverse every model-definition line.
        if raw.strip().startswith("*") and current:  # Start a new block at the next keyword.
            blocks.append(current)  # Preserve the complete prior block.
            current = [raw]  # Initialize the new keyword block.
        else:  # Preserve comments, data, and the first keyword in the current block.
            current.append(raw)  # Append the exact line.
    if current:  # Preserve the final block.
        blocks.append(current)  # Append the final keyword block.
    return blocks  # Return the ordered keyword blocks.
def copy_missing_amplitudes(static_prefix: list[str], explicit_prefix: list[str]) -> list[str]:  # Recover model-level amplitude definitions referenced by the static mother but absent from the modal parent.
    explicit_names: set[str] = set()  # Collect amplitude names already present in the explicit prefix.
    for block in parse_keyword_blocks(explicit_prefix):  # Traverse explicit model-definition blocks.
        header = block[0].strip() if block else ""  # Select the block header.
        if header.upper().startswith("*AMPLITUDE"):  # Parse one amplitude definition.
            name = keyword_attributes(header).get("NAME")  # Select its explicit name.
            if name:  # Require a nonempty name.
                explicit_names.add(name.upper())  # Preserve the normalized amplitude name.
    additions: list[str] = []  # Accumulate missing amplitude blocks.
    for block in parse_keyword_blocks(static_prefix):  # Traverse static-mother model-definition blocks.
        header = block[0].strip() if block else ""  # Select the block header.
        if not header.upper().startswith("*AMPLITUDE"):  # Ignore non-amplitude blocks.
            continue  # Continue to the next block.
        name = keyword_attributes(header).get("NAME")  # Select the amplitude name.
        if not name or name.upper() in explicit_names:  # Skip unnamed or already present amplitudes.
            continue  # Continue to the next block.
        additions.extend(block)  # Preserve the complete missing amplitude block unchanged.
        explicit_names.add(name.upper())  # Prevent duplicate recovery.
    return additions  # Return all missing model-level amplitude definitions.
def strip_output_blocks(step: list[str]) -> list[str]:  # Remove result-output requests from one static step without changing its physics.
    output_prefixes = ("*NODE FILE", "*EL FILE", "*NODE PRINT", "*EL PRINT", "*CONTACT FILE", "*CONTACT PRINT")  # Define nonphysical output keywords to suppress.
    result: list[str] = []  # Accumulate the cleaned static step.
    index = 0  # Initialize zero-based step traversal.
    while index < len(step):  # Traverse every step line.
        upper = step[index].strip().upper()  # Normalize the current line.
        if not any(upper.startswith(prefix) for prefix in output_prefixes):  # Preserve all non-output records.
            result.append(step[index])  # Append the exact line.
            index += 1  # Advance to the next line.
            continue  # Continue traversal.
        index += 1  # Skip the output keyword itself.
        while index < len(step) and not step[index].strip().startswith("*"):  # Skip output variable data until the next keyword.
            index += 1  # Advance through the output block.
    return result  # Return the physics-equivalent cleaned step.
def gravity_rows(step: list[str]) -> list[tuple[str, list[str]]]:  # Parse every GRAV row inside one static step.
    rows: list[tuple[str, list[str]]] = []  # Accumulate element-set names and complete data fields.
    active = False  # Track one DLOAD block.
    for raw in step:  # Traverse every step line.
        line = raw.strip()  # Normalize surrounding whitespace.
        upper = line.upper()  # Normalize keyword matching.
        if not line or line.startswith("**"):  # Ignore blank and comment rows.
            continue  # Continue traversal.
        if upper.startswith("*"):  # Handle one keyword record.
            active = upper.startswith("*DLOAD")  # Select DLOAD data blocks only.
            continue  # Complete keyword handling.
        if not active:  # Ignore data outside DLOAD blocks.
            continue  # Continue traversal.
        fields = [field.strip() for field in line.split(",")]  # Split one distributed-load row.
        if len(fields) >= 3 and fields[1].upper().startswith("GRAV"):  # Select gravity rows only.
            rows.append((fields[0].upper(), fields))  # Preserve the loaded set and exact data fields.
    return rows  # Return all parsed gravity rows.
def inject_gravity_rows(step: list[str], elsets: Iterable[str], template: list[str], already_loaded: set[str]) -> tuple[list[str], list[str]]:  # Apply the inherited gravity vector to added mass sets not already loaded.
    pending = [name for name in sorted({name.upper() for name in elsets if name}) if name not in already_loaded]  # Select new mass sets requiring gravity.
    if not pending:  # Preserve the original static step when all added masses already inherit gravity.
        return step, []  # Return the unchanged step and no injected rows.
    result: list[str] = []  # Accumulate the gravity-augmented static step.
    injected_rows = [", ".join([name] + template[1:]) for name in pending]  # Form one exact gravity row per pending mass set.
    injected = False  # Track completion of the single insertion.
    index = 0  # Initialize zero-based step traversal.
    while index < len(step):  # Traverse every step line.
        raw = step[index]  # Select the current exact line.
        upper = raw.strip().upper()  # Normalize keyword matching.
        result.append(raw)  # Preserve the current line.
        if not injected and upper.startswith("*DLOAD"):  # Select the first DLOAD block containing the inherited GRAV template.
            cursor = index + 1  # Start inspecting DLOAD data rows.
            contains_gravity = False  # Track whether this DLOAD block contains a GRAV row.
            while cursor < len(step) and not step[cursor].strip().startswith("*"):  # Traverse DLOAD data rows only.
                fields = [field.strip() for field in step[cursor].split(",")]  # Parse the current DLOAD row.
                if len(fields) >= 3 and fields[1].upper().startswith("GRAV"):  # Detect the inherited gravity family.
                    contains_gravity = True  # Mark the current DLOAD block for insertion.
                result.append(step[cursor])  # Preserve the current DLOAD data row.
                cursor += 1  # Advance to the next data row.
            if contains_gravity:  # Insert added-mass gravity rows after the inherited gravity data.
                result.extend(injected_rows)  # Append the exact inherited-vector rows.
                injected = True  # Mark completion of gravity injection.
            index = cursor  # Advance beyond the consumed DLOAD data block.
            continue  # Continue traversal at the next keyword.
        index += 1  # Advance to the next line.
    require(injected, "GRAVITY_TEMPLATE_BLOCK_NOT_FOUND", repr(template))  # Require a physical gravity insertion location.
    return result, injected_rows  # Return the augmented step and exact injected rows.
def update_frequency_roots(step: list[str], roots: int) -> list[str]:  # Change only the requested eigenvalue count in one modal step.
    result = list(step)  # Copy the exact modal step for bounded modification.
    frequency_index = next((index for index, raw in enumerate(result) if raw.strip().upper().startswith("*FREQUENCY")), None)  # Locate the frequency keyword.
    require(frequency_index is not None, "FREQUENCY_KEYWORD_MISSING", str(len(step)))  # Require a modal procedure.
    data_index = int(frequency_index) + 1  # Select the first data row after the frequency keyword.
    while data_index < len(result) and (not result[data_index].strip() or result[data_index].strip().startswith("**")):  # Skip blank and comment rows.
        data_index += 1  # Advance to the first numerical data row.
    require(data_index < len(result) and not result[data_index].strip().startswith("*"), "FREQUENCY_DATA_MISSING", str(data_index))  # Require a numerical frequency row.
    fields = [field.strip() for field in result[data_index].split(",")]  # Split the frequency-control row while preserving empty fields.
    if len(fields) >= 3:  # Use the standard lower, upper, eigenvalue-count syntax.
        fields[2] = str(roots)  # Replace only the requested number of eigenvalues.
    else:  # Handle a compact one-field eigenvalue-count syntax.
        fields[0] = str(roots)  # Replace the single root-count field.
    result[data_index] = ", ".join(fields)  # Reassemble the frequency-control row deterministically.
    return result  # Return the modal step with unchanged physics and updated output range.
def main() -> None:  # Execute hypothesized command-path Track A model construction.
    parser = argparse.ArgumentParser(description="Merge an explicit high-master Track A model with the exact C3 nonlinear static history. Agent-constructed path; not human APDL.")  # Define the command-line interface.
    parser.add_argument("--parent", required=True, type=Path)  # Select the exact released C3 parent.
    parser.add_argument("--explicit", required=True, type=Path)  # Select the recovered explicit high-master Track A deck.
    parser.add_argument("--static-mother", required=True, type=Path)  # Select the structurally identical nonlinear C3 static mother.
    parser.add_argument("--output", required=True, type=Path)  # Select the complete generated daughter path.
    parser.add_argument("--audit", required=True, type=Path)  # Select the machine-readable construction-audit path.
    parser.add_argument("--roots", type=int, default=80)  # Select the requested modal extraction range.
    arguments = parser.parse_args()  # Parse the explicit command-line arguments.
    require(arguments.roots >= 40, "ROOT_COUNT_TOO_SMALL", str(arguments.roots))  # Retain enough modes for global branch tracking.
    parent_lines = read_lines(arguments.parent)  # Read the exact released C3 parent.
    explicit_lines = read_lines(arguments.explicit)  # Read the recovered explicit Track A deck.
    static_lines = read_lines(arguments.static_mother)  # Read the recovered exact nonlinear static mother.
    parent_nodes = parse_nodes(parent_lines)  # Parse parent node coordinates.
    explicit_nodes = parse_nodes(explicit_lines)  # Parse explicit Track A node coordinates.
    parent_elements = parse_elements(parent_lines)  # Parse parent elements.
    explicit_elements = parse_elements(explicit_lines)  # Parse explicit Track A elements.
    parent_equations = parse_equations(parent_lines)  # Parse parent constraint equations.
    explicit_equations = parse_equations(explicit_lines)  # Parse explicit Track A constraint equations.
    new_nodes = set(explicit_nodes) - set(parent_nodes)  # Identify added high-master nodes.
    new_element_ids = set(explicit_elements) - set(parent_elements)  # Identify added entity elements.
    new_equations = added_equations(parent_equations, explicit_equations)  # Identify added rigid-kinematic equations.
    new_type_counts = Counter(str(explicit_elements[element]["type"]).upper() for element in new_element_ids)  # Count added element types.
    spring_count = sum(count for element_type, count in new_type_counts.items() if element_type.startswith("SPRING"))  # Count surrogate spring elements.
    link_count = sum(count for element_type, count in new_type_counts.items() if element_type in {"T3D2", "UCAB3", "LINK180"})  # Count explicit LINK-type members.
    mass_ids = [element for element in new_element_ids if str(explicit_elements[element]["type"]).upper().startswith("MASS")]  # Select added discrete mass elements.
    mass_elsets = {str(explicit_elements[element]["elset"]).upper() for element in mass_ids if explicit_elements[element]["elset"]}  # Select their owning element sets.
    rotation_equations = [terms for terms in new_equations if any(dof in {4, 5, 6} and abs(coefficient) > 0.0 for _, dof, coefficient in terms)]  # Select equations containing rotational DOFs.
    lever_equations = [terms for terms in rotation_equations if any(abs(abs(coefficient) - 1.0) > 1.0e-8 for _, _, coefficient in terms)]  # Select equations containing genuine geometric lever coefficients.
    checks = [rigid_formula_check(terms, new_nodes, explicit_nodes) for terms in rotation_equations]  # Compare every rotational equation against rigid-offset kinematics.
    recognized = [check for check in checks if check.get("recognized")]  # Select equations with sufficient geometry for direct comparison.
    maximum_formula_error = max((float(check["maximum_error"]) for check in recognized if check.get("maximum_error") is not None), default=None)  # Measure the worst absolute lever-coefficient mismatch.
    require(bool(new_nodes), "HIGH_MASTER_NODES_MISSING", "No explicit nodes were added to C3")  # Require explicit high-master geometry.
    require(link_count > 0, "LINK_MEMBERS_MISSING", repr(new_type_counts))  # Require old-ANSYS-style LINK connectivity.
    require(spring_count == 0, "SURROGATE_SPRING_FORBIDDEN", repr(new_type_counts))  # Reject differential-spring substitutes.
    require(bool(rotation_equations), "ROTATIONAL_EQUATIONS_MISSING", str(len(new_equations)))  # Require rotational kinematic coupling.
    require(bool(lever_equations), "LEVER_COEFFICIENTS_MISSING", str(len(rotation_equations)))  # Require explicit geometric offset coefficients.
    require(maximum_formula_error is not None and maximum_formula_error <= 1.0e-6, "RIGID_FORMULA_MISMATCH", str(maximum_formula_error))  # Require u_low equals u_high plus theta cross r within input precision.
    static_steps_all = split_steps(static_lines)  # Parse the exact static-mother step sequence.
    static_steps = [strip_output_blocks(step) for step in static_steps_all if step_has_keyword(step, "*STATIC")]  # Preserve every static equilibrium step while suppressing nonphysical output requests.
    require(bool(static_steps), "STATIC_HISTORY_MISSING", str(len(static_steps_all)))  # Require a nonlinear static history.
    require(any("NLGEOM" in step[0].upper() for step in static_steps), "NLGEOM_STATIC_HISTORY_MISSING", repr([step[0] for step in static_steps]))  # Require geometrically nonlinear equilibrium.
    gravity_candidates = [(step_index, row) for step_index, step in enumerate(static_steps) for row in gravity_rows(step)]  # Collect all inherited gravity rows and owning step indices.
    require(bool(gravity_candidates), "C3_GRAVITY_ROW_MISSING", str(len(static_steps)))  # Require an inherited gravity vector.
    preferred = next((candidate for candidate in gravity_candidates if candidate[1][0] == "E_MASS"), gravity_candidates[0])  # Prefer the authoritative C3 mass-gravity row.
    gravity_step_index, (_, gravity_template) = preferred  # Select the owning static step and exact gravity data fields.
    loaded_sets = {name for step in static_steps for name, _ in gravity_rows(step)}  # Collect all element sets already receiving gravity.
    static_steps[gravity_step_index], injected_gravity = inject_gravity_rows(static_steps[gravity_step_index], mass_elsets, gravity_template, loaded_sets)  # Apply the inherited gravity vector to added mass sets when required.
    explicit_steps = split_steps(explicit_lines)  # Parse the explicit Track A analysis steps.
    modal_candidates = [step for step in explicit_steps if step_has_keyword(step, "*FREQUENCY")]  # Select explicit modal extraction steps.
    require(bool(modal_candidates), "EXPLICIT_MODAL_STEP_MISSING", str(len(explicit_steps)))  # Require the common observation-output modal step.
    modal_step = update_frequency_roots(modal_candidates[-1], arguments.roots)  # Preserve the final explicit modal step and request the bounded eighty-mode range.
    explicit_prefix = explicit_lines[:first_step_index(explicit_lines)]  # Select the complete explicit Track A model-definition prefix.
    static_prefix = static_lines[:first_step_index(static_lines)]  # Select the complete static-mother model-definition prefix.
    missing_amplitudes = copy_missing_amplitudes(static_prefix, explicit_prefix)  # Recover static-mother amplitude definitions absent from the modal parent.
    output_lines = list(explicit_prefix)  # Start with the complete C3 plus explicit Track A model definitions.
    if missing_amplitudes:  # Append only missing model-level amplitudes required by the static history.
        output_lines.extend(["** TRACK_A_RECOVERED_STATIC_MOTHER_AMPLITUDES"])  # Mark the nonphysical provenance block.
        output_lines.extend(missing_amplitudes)  # Preserve the exact recovered amplitude definitions.
    output_lines.extend(["** TRACK_A_OLD_ANSYS_FORWARD_STATIC_HISTORY_BEGIN"])  # Mark the start of the inherited old-workflow static sequence.
    for step in static_steps:  # Append every ordered nonlinear static equilibrium step.
        output_lines.extend(step)  # Preserve the complete physics step.
    output_lines.extend(["** TRACK_A_OLD_ANSYS_FORWARD_MODAL_EXTRACTION_BEGIN"])  # Mark the start of modal extraction.
    output_lines.extend(modal_step)  # Append the common-observation perturbation modal step.
    arguments.output.parent.mkdir(parents=True, exist_ok=True)  # Create the complete daughter output directory.
    arguments.output.write_text("\n".join(output_lines) + "\n", encoding="ascii")  # Publish the deterministic complete daughter deck.
    audit = {"status": "BUILT", "parent": {"path": str(arguments.parent), "sha256": sha256_file(arguments.parent)}, "explicit_track": {"path": str(arguments.explicit), "sha256": sha256_file(arguments.explicit)}, "static_mother": {"path": str(arguments.static_mother), "sha256": sha256_file(arguments.static_mother)}, "output": {"path": str(arguments.output), "sha256": sha256_file(arguments.output), "bytes": arguments.output.stat().st_size}, "construction": {"method": "complete explicit C3 plus high-master model prefix, exact inherited C3 NLGEOM static history, common-observation perturbation modal step", "roots": arguments.roots, "new_node_count": len(new_nodes), "new_element_type_counts": dict(new_type_counts), "new_equation_count": len(new_equations), "rotation_equation_count": len(rotation_equations), "lever_equation_count": len(lever_equations), "maximum_rigid_formula_error": maximum_formula_error, "added_mass_element_count": len(mass_ids), "added_mass_elsets": sorted(mass_elsets), "injected_gravity_rows": injected_gravity, "inherited_gravity_template": gravity_template, "static_step_count": len(static_steps), "missing_amplitude_line_count": len(missing_amplitudes), "surrogate_spring_count": spring_count, "target_frequency_used": False, "human_apdl": False, "frequency_reproduced": False, "not_attach_ta1": True, "source": "agent_constructed_hypothesized_command_path"}, "equation_samples": [{"rendered": render_equation(terms), "check": rigid_formula_check(terms, new_nodes, explicit_nodes)} for terms in rotation_equations[:24]]}  # Build the complete machine-readable construction record.
    arguments.audit.parent.mkdir(parents=True, exist_ok=True)  # Create the audit output directory.
    arguments.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")  # Publish the complete construction audit.
if __name__ == "__main__":  # Execute only when invoked as a script.
    main()  # Run hypothesized command-path Track A construction.
