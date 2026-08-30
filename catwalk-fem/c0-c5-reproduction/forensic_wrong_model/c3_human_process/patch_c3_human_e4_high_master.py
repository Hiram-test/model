#!/usr/bin/env python3  # Target-blind E4 high-master rewire on frozen C3. Portal masters come from the agent Ultra S10 include, not undisclosed human APDL. frequency_reproduced=false. human_apdl=false.
from __future__ import annotations  # Preserve modern type annotations on supported Python versions.
import argparse  # Parse immutable source paths, the preregistered variant, and modal-root controls.
import csv  # Write an auditable passage-master and high-master geometry ledger.
import hashlib  # Verify immutable input identities and bind emitted daughter identities.
import json  # Write the machine-readable construction receipt.
import math  # Check finite coordinates and coefficient differences without external dependencies.
import re  # Parse explicit numeric APDL and CalculiX records.
from collections import Counter, defaultdict  # Count legacy master profiles and build deterministic reverse indices.
from pathlib import Path  # Handle repository and runner paths without shell-dependent string operations.
from typing import Iterable  # Annotate deterministic formatting helpers.
C3_PARENT_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"  # Lock the exact released C3 parent input.
LEGACY_APDL_SHA256 = "72012ebbd107cf377c2178561b9008606aeb894c4f7879110d13c30d2a417330"  # Lock apply_finite_gates_and_passages_v2.inp from the agent Ultra S10 section-shear snapshot.
EXPECTED_PARENT_NODES = 91415  # Preserve the validated C3 node count.
EXPECTED_PARENT_ELEMENTS = 172998  # Preserve the validated C3 element count.
EXPECTED_LEGACY_MASTERS = 3692  # Preserve the recovered unique CERIG-master count.
EXPECTED_PASSAGE_MASTERS = 42  # Preserve twenty-one passage stations times two catwalk sides.
EXPECTED_MAIN13_MASTERS = 26  # Preserve thirteen main-span passage stations times two catwalk sides.
MAIN_SPAN_X_MIN_MM = 660000.0  # Use the north-tower main-span coordinate as the strict lower selection bound.
MAIN_SPAN_X_MAX_MM = 2960000.0  # Use the south-tower main-span coordinate as the strict upper selection bound.
OBSERVATION_NODES = [79599, 79701, 79803, 79905, 80007, 80109, 80211, 80313, 80415, 80517, 80619, 80721, 80823, 80925, 81027, 81129, 81231, 81333, 81435, 81537, 81639, 82028, 82130, 82232, 82334, 82436, 82538, 82640, 82742, 82844, 82946, 83048, 83150, 83252, 83354, 83456, 83558, 83660, 83762, 83864, 83966, 84068, 79453, 79454, 79455, 79456, 79457, 79458, 79459, 79460]  # Use the frozen fifty-node branch-tracking field.
VARIANTS = {"CONTROL_BOTTOM_MAIN13": ("main13", "bottom", "bottom"), "E4_ROPE_MAIN13": ("main13", "high", "bottom"), "E4_PASSAGE_MAIN13": ("main13", "bottom", "high"), "E4_ALL_MAIN13": ("main13", "high", "high"), "E4_ALL_ALL21": ("all21", "high", "high")}  # Freeze the target-blind control and E4 decomposition matrix.
def digest_bytes(data: bytes) -> str:  # Return one lowercase SHA-256 digest.
    return hashlib.sha256(data).hexdigest()  # Bind and return the exact byte stream.
def coordinate_key(x_value: float, y_value: float, z_value: float) -> tuple[float, float, float]:  # Normalize one global coordinate for cross-format matching.
    return round(x_value, 6), round(y_value, 6), round(z_value, 6)  # Use the audited one-micrometre decimal representation.
def parse_arguments() -> argparse.Namespace:  # Parse all explicit construction controls.
    parser = argparse.ArgumentParser(description="Rewire exact C3 passage CERIG relations from bottom masters to S10-topology high portal masters. Not human APDL. frequency_reproduced=false.")  # Create a self-documenting command interface.
    parser.add_argument("--source", required=True, type=Path)  # Require the exact frozen C3 parent deck.
    parser.add_argument("--legacy-apdl", required=True, type=Path)  # Require the agent Ultra S10 finite-gate-and-passage include (not undisclosed human APDL).
    parser.add_argument("--output", required=True, type=Path)  # Require the complete daughter input path.
    parser.add_argument("--variant", required=True, choices=sorted(VARIANTS))  # Restrict execution to preregistered target-blind variants.
    parser.add_argument("--roots", type=int, default=40)  # Request forty modes by default for crossing-aware branch tracking.
    parser.add_argument("--expected-source-sha256", default=C3_PARENT_SHA256)  # Permit an explicit local-test identity while Actions retains the frozen parent digest.
    parser.add_argument("--expected-parent-nodes", type=int, default=EXPECTED_PARENT_NODES)  # Permit an explicit local-test node count.
    parser.add_argument("--expected-parent-elements", type=int, default=EXPECTED_PARENT_ELEMENTS)  # Permit an explicit local-test element count.
    return parser.parse_args()  # Return the validated command namespace.
def parse_c3_nodes_and_elements(lines: list[str]) -> tuple[dict[int, tuple[float, float, float]], set[int]]:  # Parse complete C3 geometry and element identity.
    node_coordinates: dict[int, tuple[float, float, float]] = {}  # Accumulate every explicit numeric node coordinate.
    element_ids: set[int] = set()  # Accumulate every explicit numeric element identifier.
    active_keyword = ""  # Track the current CalculiX data block.
    for raw_line in lines:  # Scan the source once in order.
        stripped = raw_line.strip()  # Normalize whitespace for parsing only.
        if not stripped or stripped.startswith("**"):  # Ignore blank and comment records.
            continue  # Advance to the next source line.
        if stripped.startswith("*"):  # Update the active keyword at each CalculiX card.
            active_keyword = stripped.split(",", 1)[0].upper()  # Retain only the normalized keyword token.
            continue  # Skip keyword lines for entity parsing.
        if active_keyword == "*NODE":  # Parse one explicit node data row.
            fields = [field.strip() for field in stripped.split(",")]  # Split the node identifier and global coordinates.
            if len(fields) >= 4 and re.fullmatch(r"[+-]?\d+", fields[0]):  # Accept only complete numeric node records.
                node_coordinates[int(fields[0])] = coordinate_key(float(fields[1]), float(fields[2]), float(fields[3]))  # Store one exact matching coordinate.
        elif active_keyword == "*ELEMENT":  # Parse one explicit element data row.
            token = stripped.split(",", 1)[0].strip()  # Read the leading element identifier.
            if re.fullmatch(r"[+-]?\d+", token):  # Accept only numeric element records.
                element_ids.add(int(token))  # Preserve the unique element identity.
    return node_coordinates, element_ids  # Return the complete parent topology identity.
def parse_c3_equations(lines: list[str]) -> list[dict[str, object]]:  # Parse every CalculiX equation with its exact source range.
    equations: list[dict[str, object]] = []  # Accumulate deterministic equation records.
    index = 0  # Initialize the source-line cursor.
    while index < len(lines):  # Traverse the complete source deck.
        if not lines[index].strip().upper().startswith("*EQUATION"):  # Skip records outside equation blocks.
            index += 1  # Advance the source-line cursor.
            continue  # Continue scanning for the next equation card.
        start_index = index  # Record the inclusive equation-block start.
        index += 1  # Advance to the term-count record.
        while index < len(lines) and (not lines[index].strip() or lines[index].strip().startswith("**")):  # Tolerate blank or comment records after the keyword.
            index += 1  # Advance to the numeric term-count record.
        if index >= len(lines):  # Require a complete equation block.
            raise ValueError("Truncated *EQUATION block without a term count.")  # Reject a malformed parent deck.
        term_count = int(lines[index].strip().split(",", 1)[0])  # Parse the required number of node-DOF-coefficient terms.
        index += 1  # Advance to the equation data records.
        fields: list[str] = []  # Accumulate flattened equation tokens.
        while index < len(lines) and len(fields) < 3 * term_count:  # Read enough tokens for every declared term.
            stripped = lines[index].strip()  # Normalize one equation data record.
            if stripped.startswith("*"):  # Prevent accidental consumption of the next keyword.
                raise ValueError(f"Equation beginning at line {start_index + 1} ended before all terms were read.")  # Reject a malformed equation block.
            if stripped and not stripped.startswith("**"):  # Parse nonblank noncomment equation data.
                fields.extend(field.strip() for field in stripped.split(",") if field.strip())  # Append every explicit token.
            index += 1  # Advance to the next source line.
        if len(fields) != 3 * term_count:  # Require exact token closure.
            raise ValueError(f"Equation beginning at line {start_index + 1} declared {term_count} terms but supplied {len(fields) / 3.0}.")  # Reject an incomplete or overrun record.
        terms: list[tuple[int, int, float]] = []  # Accumulate normalized numeric equation terms.
        for term_index in range(term_count):  # Parse every node-DOF-coefficient triple.
            node_token = fields[3 * term_index]  # Read the node identifier token.
            if not re.fullmatch(r"[+-]?\d+", node_token):  # Require numeric nodes for the selected legacy relation audit.
                raise ValueError(f"Non-numeric node token {node_token!r} appears in an equation at line {start_index + 1}.")  # Reject an unsupported equation representation.
            terms.append((int(node_token), int(fields[3 * term_index + 1]), float(fields[3 * term_index + 2].replace("D", "E").replace("d", "e"))))  # Store one normalized term.
        equations.append({"start": start_index, "end": index, "terms": terms})  # Preserve the half-open source range and normalized terms.
    return equations  # Return every parsed parent equation.
def parse_legacy_apdl(apdl_text: str) -> tuple[dict[int, tuple[float, float, float]], dict[int, dict[str, object]], list[tuple[int, int, str]], dict[int, Counter[str]]]:  # Parse legacy geometry, finite beams, CERIG relations, and master profiles.
    node_coordinates: dict[int, tuple[float, float, float]] = {}  # Accumulate explicit APDL node coordinates.
    elements: dict[int, dict[str, object]] = {}  # Accumulate finite BEAM188 connectivity with section identity.
    cerig_relations: list[tuple[int, int, str]] = []  # Preserve every explicit master-slave-degree relation.
    master_profiles: dict[int, Counter[str]] = defaultdict(Counter)  # Count each CERIG degree profile by master.
    current_section: int | None = None  # Track the active APDL beam section.
    for raw_line in apdl_text.splitlines():  # Scan the S10 include once in source order.
        command_text = raw_line.split("!", 1)[0].strip()  # Remove only APDL end-of-line comments before parsing.
        if not command_text:  # Ignore blank and comment-only records.
            continue  # Advance to the next APDL record.
        fields = [field.strip() for field in command_text.split(",")]  # Split one APDL command into normalized fields.
        command = fields[0].upper()  # Normalize the command token.
        if command == "N" and len(fields) >= 5 and re.fullmatch(r"[+-]?\d+", fields[1]):  # Parse explicit N,node,x,y,z records.
            node_coordinates[int(fields[1])] = coordinate_key(float(fields[2]), float(fields[3]), float(fields[4]))  # Store one exact global coordinate.
        elif command == "SECNUM" and len(fields) >= 2:  # Track the active finite-beam section.
            current_section = int(fields[1])  # Store the current section number.
        elif command == "EN" and len(fields) >= 4 and re.fullmatch(r"[+-]?\d+", fields[1]):  # Parse explicit EN,eid,node_i,node_j,orientation records.
            elements[int(fields[1])] = {"node_i": int(fields[2]), "node_j": int(fields[3]), "section": current_section}  # Preserve physical endpoints and section identity.
        elif command == "CERIG" and len(fields) >= 3 and re.fullmatch(r"[+-]?\d+", fields[1]) and re.fullmatch(r"[+-]?\d+", fields[2]):  # Parse explicit CERIG records.
            degree_label = fields[3].upper() if len(fields) >= 4 and fields[3] else "ALL"  # Apply the APDL ALL default when the degree field is omitted.
            master_id = int(fields[1])  # Parse the legacy master node.
            slave_id = int(fields[2])  # Parse the legacy slave node.
            cerig_relations.append((master_id, slave_id, degree_label))  # Preserve the exact relation.
            master_profiles[master_id][degree_label] += 1  # Count the master profile.
    return node_coordinates, elements, cerig_relations, master_profiles  # Return all data required for topology-derived high-master reconstruction.
def build_legacy_graph(elements: dict[int, dict[str, object]], cerig_relations: list[tuple[int, int, str]]) -> tuple[dict[int, list[tuple[int, int]]], dict[int, list[tuple[int, str]]], dict[int, list[tuple[int, str]]]]:  # Build finite-beam and CERIG adjacency indices.
    beam_adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)  # Map each physical beam node to neighboring node and section.
    for element in elements.values():  # Traverse every finite BEAM188 element.
        node_i = int(element["node_i"])  # Read the first physical endpoint.
        node_j = int(element["node_j"])  # Read the second physical endpoint.
        section = int(element["section"])  # Read the active section identity.
        beam_adjacency[node_i].append((node_j, section))  # Add the forward undirected adjacency.
        beam_adjacency[node_j].append((node_i, section))  # Add the reverse undirected adjacency.
    cerig_by_master: dict[int, list[tuple[int, str]]] = defaultdict(list)  # Map each legacy master to its slave relations.
    cerig_by_slave: dict[int, list[tuple[int, str]]] = defaultdict(list)  # Map each legacy slave to its master relations.
    for master_id, slave_id, degree_label in cerig_relations:  # Traverse every explicit CERIG relation.
        cerig_by_master[master_id].append((slave_id, degree_label))  # Index the relation by master.
        cerig_by_slave[slave_id].append((master_id, degree_label))  # Index the relation by slave.
    return beam_adjacency, cerig_by_master, cerig_by_slave  # Return deterministic legacy topology indices.
def derive_high_master_rows(node_coordinates: dict[int, tuple[float, float, float]], elements: dict[int, dict[str, object]], cerig_relations: list[tuple[int, int, str]], master_profiles: dict[int, Counter[str]]) -> list[dict[str, object]]:  # Derive the actual outer portal-top master above every passage master from legacy topology.
    beam_adjacency, cerig_by_master, cerig_by_slave = build_legacy_graph(elements, cerig_relations)  # Build finite-beam and rigid-relation adjacency.
    passage_masters = sorted((master_id for master_id, profile in master_profiles.items() if profile == Counter({"ALL": 3, "UXYZ": 1})), key=lambda master_id: (node_coordinates[master_id][0], -node_coordinates[master_id][1]))  # Identify and order the forty-two passage masters by their unique profile.
    if len(master_profiles) != EXPECTED_LEGACY_MASTERS:  # Preserve the complete recovered legacy master scope.
        raise ValueError(f"Expected {EXPECTED_LEGACY_MASTERS} legacy masters, found {len(master_profiles)}.")  # Reject a different APDL model line.
    if len(passage_masters) != EXPECTED_PASSAGE_MASTERS:  # Preserve the twenty-one two-sided passage scope.
        raise ValueError(f"Expected {EXPECTED_PASSAGE_MASTERS} passage masters, found {len(passage_masters)}.")  # Reject a changed passage template.
    rows: list[dict[str, object]] = []  # Accumulate one topology-derived high-master record per passage side.
    for bottom_master in passage_masters:  # Traverse every passage master in station and side order.
        x_value, y_value, z_value = node_coordinates[bottom_master]  # Read the exact bottom passage-master coordinate.
        side_sign = 1 if y_value > 0.0 else -1  # Identify the positive- or negative-Y catwalk side.
        outer_column_y = side_sign * 24360.0  # Use the actual outer portal-column line adjacent to the rope-side passage master.
        bottom_column_candidates = [neighbor for neighbor, section in beam_adjacency[bottom_master] if section == 61 and neighbor in node_coordinates and abs(node_coordinates[neighbor][0] - x_value) <= 1.0e-6 and abs(node_coordinates[neighbor][1] - outer_column_y) <= 1.0e-6 and abs(node_coordinates[neighbor][2] - z_value) <= 1.0e-6]  # Find the unique bottom-beam node at the outer portal column.
        if len(bottom_column_candidates) != 1:  # Require one exact adjacent outer-column bottom node.
            raise ValueError(f"Passage master {bottom_master} has {len(bottom_column_candidates)} outer-column bottom candidates: {bottom_column_candidates}.")  # Reject ambiguous portal topology.
        bottom_column_master = bottom_column_candidates[0]  # Select the unique outer-column bottom-beam master.
        post_bottom_candidates = [slave_id for slave_id, degree_label in cerig_by_master[bottom_column_master] if degree_label == "ALL" and slave_id in node_coordinates and abs(node_coordinates[slave_id][0] - x_value) <= 1.0e-6 and abs(node_coordinates[slave_id][1] - outer_column_y) <= 1.0e-6 and 0.0 < node_coordinates[slave_id][2] - z_value < 200.0]  # Find the rigidly tied physical post-bottom node.
        if len(post_bottom_candidates) != 1:  # Require one exact outer post-bottom node.
            raise ValueError(f"Passage master {bottom_master} has {len(post_bottom_candidates)} post-bottom candidates: {post_bottom_candidates}.")  # Reject ambiguous rigid-region topology.
        post_bottom = post_bottom_candidates[0]  # Select the unique post-bottom node.
        post_top_candidates = [neighbor for neighbor, section in beam_adjacency[post_bottom] if section == 62 and neighbor in node_coordinates and abs(node_coordinates[neighbor][0] - x_value) <= 1.0e-6 and abs(node_coordinates[neighbor][1] - outer_column_y) <= 1.0e-6 and node_coordinates[neighbor][2] - z_value > 1000.0]  # Follow the actual RHS160 portal post to its top node.
        if len(post_top_candidates) != 1:  # Require one exact physical post-top node.
            raise ValueError(f"Passage master {bottom_master} has {len(post_top_candidates)} post-top candidates: {post_top_candidates}.")  # Reject ambiguous finite-beam topology.
        post_top = post_top_candidates[0]  # Select the unique post-top node.
        high_master_candidates = [master_id for master_id, degree_label in cerig_by_slave[post_top] if degree_label == "ALL" and master_id in node_coordinates and abs(node_coordinates[master_id][0] - x_value) <= 1.0e-6 and abs(node_coordinates[master_id][1] - outer_column_y) <= 1.0e-6 and abs(node_coordinates[master_id][2] - node_coordinates[post_top][2]) < 200.0]  # Recover the actual portal-top master rigidly tied to the post top.
        if len(high_master_candidates) != 1:  # Require one exact high portal master.
            raise ValueError(f"Passage master {bottom_master} has {len(high_master_candidates)} high-master candidates: {high_master_candidates}.")  # Reject ambiguous high-pilot geometry.
        high_master = high_master_candidates[0]  # Select the topology-derived high portal master.
        high_x, high_y, high_z = node_coordinates[high_master]  # Read the exact high-master coordinate.
        height = high_z - z_value  # Compute the actual vertical pilot height without target fitting.
        if not (7000.0 < height < 10000.0):  # Require a physically plausible portal height from the recovered geometry.
            raise ValueError(f"Passage master {bottom_master} produced an implausible high-master height {height} mm.")  # Reject a wrong topology path.
        rows.append({"bottom_apdl": bottom_master, "high_apdl": high_master, "bottom_column_apdl": bottom_column_master, "post_bottom_apdl": post_bottom, "post_top_apdl": post_top, "x_mm": x_value, "side": side_sign, "bottom_x_mm": x_value, "bottom_y_mm": y_value, "bottom_z_mm": z_value, "high_x_mm": high_x, "high_y_mm": high_y, "high_z_mm": high_z, "height_mm": height, "lateral_offset_mm": high_y - y_value})  # Record the complete actual portal geometry chain.
    return rows  # Return all forty-two topology-derived high-master records.
def map_unique_c3_node(c3_by_coordinate: dict[tuple[float, float, float], list[int]], coordinate: tuple[float, float, float], label: str) -> int:  # Map one APDL physical coordinate to one exact C3 node.
    candidates = c3_by_coordinate.get(coordinate, [])  # Read all C3 nodes at the exact rounded coordinate.
    if len(candidates) != 1:  # Require one unambiguous C3 identity for each master coordinate.
        raise ValueError(f"{label} at {coordinate} maps to {len(candidates)} C3 nodes: {candidates[:20]}.")  # Reject missing or duplicate-coordinate master mappings.
    return candidates[0]  # Return the unique exact C3 node identity.
def equation_relation_groups(equations: list[dict[str, object]], bottom_master: int) -> dict[int, list[int]]:  # Recover the four existing C3 CERIG relation groups controlled by one passage master.
    groups: dict[int, list[int]] = defaultdict(list)  # Map each dependent slave node to equation indices.
    for equation_index, equation in enumerate(equations):  # Traverse every parent equation once for this selected master.
        terms = list(equation["terms"])  # Read the normalized equation terms.
        dependent_node = int(terms[0][0])  # Read the first-term dependent node.
        if dependent_node == bottom_master:  # Exclude equations where the bottom master itself is dependent.
            continue  # Advance to the next equation.
        if any(int(node_id) == bottom_master for node_id, _, _ in terms[1:]):  # Identify equations using the selected bottom master as an independent rigid-reference node.
            groups[dependent_node].append(equation_index)  # Add the equation to its dependent slave relation group.
    group_sizes = sorted(len(indices) for indices in groups.values())  # Summarize the recovered relation profile.
    if group_sizes != [3, 6, 6, 6]:  # Require one UXYZ rope relation and three ALL passage relations.
        raise ValueError(f"C3 bottom master {bottom_master} has relation-group sizes {group_sizes}, not [3, 6, 6, 6].")  # Reject a changed or ambiguous C3 equation topology.
    for dependent_node, indices in groups.items():  # Audit every recovered slave relation.
        dependent_dofs = sorted(int(equations[index]["terms"][0][1]) for index in indices)  # Read its dependent degree sequence.
        if dependent_dofs not in ([1, 2, 3], [1, 2, 3, 4, 5, 6]):  # Require an exact UXYZ or ALL rigid relation.
            raise ValueError(f"C3 relation {bottom_master}->{dependent_node} has dependent DOFs {dependent_dofs}.")  # Reject an unrecognized equation group.
    return groups  # Return the four exact existing relation groups.
def rigid_equation_terms(master_node: int, slave_node: int, degree: int, coordinates: dict[int, tuple[float, float, float]]) -> list[tuple[int, int, float]]:  # Generate one exact small-rotation rigid-body equation from actual geometry.
    master_x, master_y, master_z = coordinates[master_node]  # Read the selected master coordinate.
    slave_x, slave_y, slave_z = coordinates[slave_node]  # Read the unchanged slave coordinate.
    delta_x = slave_x - master_x  # Compute the slave longitudinal offset from the master.
    delta_y = slave_y - master_y  # Compute the slave transverse offset from the master.
    delta_z = slave_z - master_z  # Compute the slave vertical offset from the master.
    if degree == 1:  # Generate the UX rigid-body relation.
        raw_terms = [(slave_node, 1, 1.0), (master_node, 1, -1.0), (master_node, 5, -delta_z), (master_node, 6, delta_y)]  # Apply u_sx-u_mx-delta_z*theta_y+delta_y*theta_z=0.
    elif degree == 2:  # Generate the UY rigid-body relation.
        raw_terms = [(slave_node, 2, 1.0), (master_node, 2, -1.0), (master_node, 4, delta_z), (master_node, 6, -delta_x)]  # Apply u_sy-u_my+delta_z*theta_x-delta_x*theta_z=0.
    elif degree == 3:  # Generate the UZ rigid-body relation.
        raw_terms = [(slave_node, 3, 1.0), (master_node, 3, -1.0), (master_node, 4, -delta_y), (master_node, 5, delta_x)]  # Apply u_sz-u_mz-delta_y*theta_x+delta_x*theta_y=0.
    elif degree in (4, 5, 6):  # Generate a slave-to-master rotational equality for an ALL relation.
        raw_terms = [(slave_node, degree, 1.0), (master_node, degree, -1.0)]  # Apply theta_slave-theta_master=0.
    else:  # Reject unsupported rigid-region degrees.
        raise ValueError(f"Unsupported rigid-equation degree {degree}.")  # Prevent an unintended constraint operator.
    return [(node_id, dof, coefficient) for node_id, dof, coefficient in raw_terms if abs(coefficient) > 1.0e-12]  # Omit exactly zero geometric coefficients as CalculiX does.
def compare_equation_terms(reference_terms: list[tuple[int, int, float]], generated_terms: list[tuple[int, int, float]]) -> float:  # Compare two equations after indexing by node and degree.
    reference_map = {(node_id, dof): coefficient for node_id, dof, coefficient in reference_terms}  # Index the parent equation coefficients.
    generated_map = {(node_id, dof): coefficient for node_id, dof, coefficient in generated_terms}  # Index the regenerated equation coefficients.
    all_keys = set(reference_map) | set(generated_map)  # Collect every node-degree identity present in either equation.
    return max((abs(reference_map.get(key, 0.0) - generated_map.get(key, 0.0)) for key in all_keys), default=0.0)  # Return the maximum absolute coefficient difference.
def format_coefficient(value: float) -> str:  # Serialize one CalculiX equation coefficient within safe parser width.
    if abs(value - round(value)) <= 1.0e-12 and abs(value) < 10.0:  # Preserve simple unit coefficients compactly.
        return f"{value:.1f}"  # Emit 1.0 or -1.0 exactly.
    return f"{value:.12g}"  # Preserve twelve significant digits for geometric offsets.
def format_equation(terms: list[tuple[int, int, float]]) -> list[str]:  # Format one complete CalculiX equation block.
    data_tokens: list[str] = []  # Accumulate flattened node-DOF-coefficient tokens.
    for node_id, dof, coefficient in terms:  # Traverse terms in rigid-body equation order.
        data_tokens.extend([str(node_id), str(dof), format_coefficient(coefficient)])  # Append one complete numeric triple.
    return ["*EQUATION\n", f"{len(terms)}\n", ", ".join(data_tokens) + "\n"]  # Return the complete keyword, term count, and data record.
def find_final_perturbation_step(lines: list[str]) -> tuple[int, int]:  # Locate the sole final modal perturbation step.
    starts = [index for index, line in enumerate(lines) if line.strip().upper().startswith("*STEP") and "PERTURBATION" in line.upper()]  # Find every perturbation-step opening line.
    if len(starts) != 1:  # Require one unambiguous final modal step.
        raise ValueError(f"Expected exactly one perturbation step, found {len(starts)}.")  # Reject an unexpected parent layout.
    start_index = starts[0]  # Select the sole modal-step opening line.
    end_candidates = [index for index in range(start_index + 1, len(lines)) if lines[index].strip().upper().startswith("*END STEP")]  # Find closing step keywords after the opening line.
    if not end_candidates:  # Require a complete final modal step.
        raise ValueError("The perturbation step has no END STEP keyword.")  # Reject a truncated parent deck.
    end_index = end_candidates[0]  # Select the first closing keyword belonging to the modal step.
    if any(line.strip() for line in lines[end_index + 1:]):  # Require the modal step to be the final nonblank source section.
        raise ValueError("Unexpected nonblank records follow the final perturbation step.")  # Reject silent source truncation.
    return start_index, end_index  # Return the inclusive original modal-step range.
def format_nset(node_ids: Iterable[int], width: int = 16) -> list[str]:  # Format a deterministic numeric node set.
    ordered = list(node_ids)  # Materialize the validated node sequence.
    return [", ".join(str(node_id) for node_id in ordered[index:index + width]) + "\n" for index in range(0, len(ordered), width)]  # Emit bounded comma-separated records.
def build_modal_step(roots: int) -> list[str]:  # Build the common crossing-aware observation-only modal step.
    block = ["*NSET, NSET=N_HUMAN_OBS\n"]  # Declare the frozen observation set.
    block.extend(format_nset(OBSERVATION_NODES))  # Emit all fifty common observation nodes.
    block.extend(["*STEP, PERTURBATION\n", "*FREQUENCY\n", f"{roots}\n", "*NODE FILE, NSET=N_HUMAN_OBS, OUTPUT=2D\n", "U\n", "*END STEP\n"])  # Request forty modal roots and all translational observation displacements.
    return block  # Return the complete replacement modal section.
def write_mapping_csv(path: Path, rows: list[dict[str, object]]) -> None:  # Write the topology-derived bottom-to-high master ledger.
    fieldnames = ["station_index", "scope_selected", "x_mm", "side", "bottom_apdl", "bottom_c3", "high_apdl", "high_c3", "height_mm", "lateral_offset_mm", "rope_master_choice", "passage_master_choice", "relation_slave_count", "rewritten_equation_count"]  # Define the explicit auditable schema.
    with path.open("w", encoding="utf-8", newline="") as stream:  # Open the deterministic UTF-8 CSV destination.
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")  # Create a stable CSV writer.
        writer.writeheader()  # Publish the schema first.
        for row in rows:  # Preserve station and side order.
            writer.writerow({field: row[field] for field in fieldnames})  # Emit one complete topology and operation record.
def main() -> None:  # Execute validation, topology-derived high-master reconstruction, direct C3 rewiring, and receipt generation.
    args = parse_arguments()  # Read all explicit construction controls.
    if not 20 <= args.roots <= 100:  # Keep branch tracking resolved and computationally bounded.
        raise ValueError("The modal root count must be between 20 and 100.")  # Reject an under-resolved or excessive extraction request.
    source_bytes = args.source.read_bytes()  # Read the parent byte stream once.
    source_sha256 = digest_bytes(source_bytes)  # Compute the actual parent identity.
    if source_sha256 != args.expected_source_sha256.lower():  # Require the caller-provided immutable source identity.
        raise ValueError(f"Source SHA-256 mismatch: expected {args.expected_source_sha256}, got {source_sha256}.")  # Reject source drift before modeling.
    legacy_bytes = args.legacy_apdl.read_bytes()  # Read the agent Ultra S10 include byte stream once.
    legacy_sha256 = digest_bytes(legacy_bytes)  # Compute the actual APDL identity.
    if legacy_sha256 != LEGACY_APDL_SHA256:  # Require the recovered immutable APDL source.
        raise ValueError(f"Legacy APDL SHA-256 mismatch: expected {LEGACY_APDL_SHA256}, got {legacy_sha256}.")  # Reject a different geometry source.
    source_lines = source_bytes.decode("utf-8").splitlines(keepends=True)  # Preserve every original source line and terminator.
    c3_coordinates, element_ids = parse_c3_nodes_and_elements(source_lines)  # Parse complete parent topology identity.
    if len(c3_coordinates) != args.expected_parent_nodes or len(element_ids) != args.expected_parent_elements:  # Require the stated exact C3 topology.
        raise ValueError(f"Parent topology mismatch: nodes={len(c3_coordinates)}, elements={len(element_ids)}.")  # Reject a different C3 deck.
    equations = parse_c3_equations(source_lines)  # Parse every parent equation and source range.
    legacy_coordinates, legacy_elements, cerig_relations, master_profiles = parse_legacy_apdl(legacy_bytes.decode("utf-8"))  # Parse the S10 finite gate and passage topology.
    geometry_rows = derive_high_master_rows(legacy_coordinates, legacy_elements, cerig_relations, master_profiles)  # Derive every actual outer portal-top master without target data.
    c3_by_coordinate: dict[tuple[float, float, float], list[int]] = defaultdict(list)  # Build an ambiguity-preserving reverse C3 coordinate index.
    for node_id, coordinate in c3_coordinates.items():  # Index every exact C3 node coordinate.
        c3_by_coordinate[coordinate].append(node_id)  # Retain all node identities at each coordinate.
    for row in geometry_rows:  # Map every legacy bottom and high master to the exact C3 topology.
        row["bottom_c3"] = map_unique_c3_node(c3_by_coordinate, coordinate_key(float(row["bottom_x_mm"]), float(row["bottom_y_mm"]), float(row["bottom_z_mm"])), f"bottom APDL master {row['bottom_apdl']}")  # Map the passage-bottom master.
        row["high_c3"] = map_unique_c3_node(c3_by_coordinate, coordinate_key(float(row["high_x_mm"]), float(row["high_y_mm"]), float(row["high_z_mm"])), f"high APDL master {row['high_apdl']}")  # Map the actual portal-top master.
    scope_name, rope_choice, passage_choice = VARIANTS[args.variant]  # Read the fixed scope and master choices for the selected variant.
    selected_rows = [row for row in geometry_rows if scope_name == "all21" or MAIN_SPAN_X_MIN_MM < float(row["x_mm"]) < MAIN_SPAN_X_MAX_MM]  # Select all twenty-one or only thirteen main-span stations.
    expected_selected = EXPECTED_PASSAGE_MASTERS if scope_name == "all21" else EXPECTED_MAIN13_MASTERS  # Determine the exact expected two-sided master count.
    if len(selected_rows) != expected_selected:  # Require the preregistered physical scope.
        raise ValueError(f"Variant {args.variant} expected {expected_selected} selected passage masters, found {len(selected_rows)}.")  # Reject a changed station selection.
    dependent_dofs = {(int(equation["terms"][0][0]), int(equation["terms"][0][1])) for equation in equations}  # Index every parent dependent equation degree.
    high_dependency_conflicts = [(int(row["high_c3"]), dof) for row in selected_rows for dof in range(1, 7) if (int(row["high_c3"]), dof) in dependent_dofs]  # Detect high masters already used as dependent equation coordinates.
    if high_dependency_conflicts:  # Require every high-master degree to remain an independent physical coordinate.
        raise ValueError(f"Selected high-master dependent-DOF conflicts: {high_dependency_conflicts[:20]}.")  # Reject an overconstrained reparameterization.
    remove_equation_indices: set[int] = set()  # Accumulate the exact parent equation blocks replaced by the variant.
    generated_equations: list[list[tuple[int, int, float]]] = []  # Accumulate every replacement rigid-body equation.
    mapping_rows: list[dict[str, object]] = []  # Accumulate one complete operation ledger row per passage side.
    control_max_coefficient_difference = 0.0  # Track algebraic regeneration fidelity for the bottom-master control.
    for station_index, row in enumerate(selected_rows, start=1):  # Traverse selected passage masters in station and side order.
        bottom_master = int(row["bottom_c3"])  # Read the exact current C3 passage-bottom master.
        high_master = int(row["high_c3"])  # Read the exact topology-derived portal-top master.
        groups = equation_relation_groups(equations, bottom_master)  # Recover the one UXYZ and three ALL C3 relations.
        rewritten_count = 0  # Count the exact equation blocks regenerated for this passage side.
        for slave_node, equation_indices in sorted(groups.items()):  # Traverse every dependent slave relation in numeric order.
            relation_dofs = sorted(int(equations[equation_index]["terms"][0][1]) for equation_index in equation_indices)  # Read the exact UXYZ or ALL dependent degree set.
            is_rope_relation = relation_dofs == [1, 2, 3]  # Identify the sole translation-only rope relation.
            selected_master = high_master if (rope_choice == "high" if is_rope_relation else passage_choice == "high") else bottom_master  # Apply the preregistered high- or bottom-master choice by relation type.
            for equation_index in sorted(equation_indices, key=lambda item: int(equations[item]["terms"][0][1])):  # Preserve the dependent degree order within each relation.
                degree = int(equations[equation_index]["terms"][0][1])  # Read the dependent equation degree.
                replacement_terms = rigid_equation_terms(selected_master, slave_node, degree, c3_coordinates)  # Generate the exact rigid relation from actual C3 geometry.
                if selected_master == bottom_master:  # Audit algebraic fidelity whenever the original bottom master is retained.
                    difference = compare_equation_terms(list(equations[equation_index]["terms"]), replacement_terms)  # Compare the parent and regenerated coefficients.
                    control_max_coefficient_difference = max(control_max_coefficient_difference, difference)  # Preserve the worst coefficient difference across retained relations.
                    if difference > 1.0e-6:  # Require numerical equivalence at the audited C3 coordinate precision.
                        raise ValueError(f"Bottom-master regeneration differs by {difference} for master {bottom_master}, slave {slave_node}, DOF {degree}.")  # Reject an incorrect rigid-equation formula.
                remove_equation_indices.add(equation_index)  # Mark the exact parent equation block for removal.
                generated_equations.append(replacement_terms)  # Append the replacement relation in deterministic order.
                rewritten_count += 1  # Count the regenerated equation.
        row["station_index"] = station_index  # Record deterministic selected-row order.
        row["scope_selected"] = 1  # Mark this passage side as physically modified or regenerated.
        row["rope_master_choice"] = rope_choice  # Record the UXYZ rope relation master choice.
        row["passage_master_choice"] = passage_choice  # Record the three ALL passage relation master choices.
        row["relation_slave_count"] = len(groups)  # Record the four recovered slave relations.
        row["rewritten_equation_count"] = rewritten_count  # Record the expected twenty-one regenerated equations.
        mapping_rows.append(row)  # Append the complete operation ledger row.
    if len(remove_equation_indices) != len(selected_rows) * 21 or len(generated_equations) != len(selected_rows) * 21:  # Require exactly twenty-one replaced equations per passage side.
        raise ValueError(f"Expected {len(selected_rows) * 21} rewritten equations, found removed={len(remove_equation_indices)}, generated={len(generated_equations)}.")  # Reject incomplete or expanded equation surgery.
    removal_ranges = {(int(equations[index]["start"]), int(equations[index]["end"])) for index in remove_equation_indices}  # Collect the exact half-open source ranges to remove.
    removal_start_to_end = {start: end for start, end in removal_ranges}  # Index each removed equation block by its opening line.
    modal_start, modal_end = find_final_perturbation_step(source_lines)  # Locate the sole final modal step for replacement.
    output_lines: list[str] = []  # Accumulate the complete daughter input while preserving untouched parent records.
    line_index = 0  # Initialize the source-line cursor.
    while line_index < modal_start:  # Copy all model data before the final modal step.
        if line_index in removal_start_to_end:  # Skip one exact selected parent equation block.
            line_index = removal_start_to_end[line_index]  # Advance directly to the first source line after the removed block.
            continue  # Continue copying untouched parent model data.
        output_lines.append(source_lines[line_index])  # Preserve one untouched parent line exactly.
        line_index += 1  # Advance to the next source line.
    output_lines.extend(["** -----------------------------------------------------------------------------\n", f"** TARGET-BLIND E4 HIGH-MASTER VARIANT {args.variant}. NOT human APDL. frequency_reproduced=false.\n", "** Portal-top masters and heights are derived only from the agent Ultra S10 BEAM188 and CERIG topology.\n", "** No target frequency, fitted spring, added mass, material change, section change, prestress change, or coordinate change is used.\n", "** Track equation: Delta U_T=0.5*sum_j(k_theta_j*theta_j^2); this daughter tests the finite topology-generated k_theta operator.\n", "** -----------------------------------------------------------------------------\n"])  # State the exact evidence boundary inside the emitted daughter deck.
    for equation_terms in generated_equations:  # Emit every regenerated rigid relation after all untouched model data.
        output_lines.extend(format_equation(equation_terms))  # Serialize one complete CalculiX equation block.
    output_lines.extend(build_modal_step(args.roots))  # Append the common forty-root observation-only modal step.
    output_text = "".join(output_lines)  # Assemble the complete daughter input text.
    args.output.parent.mkdir(parents=True, exist_ok=True)  # Create the requested output directory when needed.
    args.output.write_text(output_text, encoding="utf-8", newline="")  # Write the complete daughter without platform newline translation.
    output_sha256 = digest_bytes(args.output.read_bytes())  # Bind the exact emitted daughter bytes.
    output_coordinates, output_elements = parse_c3_nodes_and_elements(output_text.splitlines(keepends=True))  # Reparse emitted topology for invariant closure.
    if output_coordinates != c3_coordinates or output_elements != element_ids:  # Require exact coordinate and element identity preservation.
        raise ValueError("The emitted E4 daughter changed parent node coordinates or element identities.")  # Reject unintended topology mutation.
    output_equations = parse_c3_equations(output_text.splitlines(keepends=True))  # Reparse the complete emitted equation system.
    if len(output_equations) != len(equations):  # Require one-for-one equation replacement without changing the global count.
        raise ValueError(f"Equation count changed from {len(equations)} to {len(output_equations)}.")  # Reject missing or duplicated equation blocks.
    output_dependent_dofs = [(int(equation["terms"][0][0]), int(equation["terms"][0][1])) for equation in output_equations]  # Enumerate every emitted dependent node-degree identity.
    duplicate_dependents = [identity for identity, count in Counter(output_dependent_dofs).items() if count > 1]  # Identify duplicate dependent degrees that CalculiX would reject or eliminate unpredictably.
    if duplicate_dependents:  # Require a one-to-one dependent equation system.
        raise ValueError(f"Emitted duplicate dependent DOFs: {duplicate_dependents[:20]}.")  # Reject an invalid MPC system before solution.
    mapping_path = args.output.with_suffix(args.output.suffix + ".mapping.csv")  # Derive the adjacent geometry and operation ledger path.
    write_mapping_csv(mapping_path, mapping_rows)  # Publish the complete topology-derived high-master ledger.
    unique_station_x = sorted({float(row["x_mm"]) for row in selected_rows})  # Recover the selected physical passage station coordinates.
    height_values = [float(row["height_mm"]) for row in selected_rows]  # Collect actual topology-derived portal heights.
    receipt = {"schema_version": 3, "variant": args.variant, "model": "exact frozen C3 entity model", "target_blind": True, "attachment_target_frequencies_loaded": False, "frequency_reproduced": False, "back_tuned": False, "low_dimensional": False, "human_apdl": False, "not_attach_ta1": True, "source": "agent_ultra_s10_section_shear", "human_process_hypothesis": "Hypothesis only: reuse the visible portal-top master for rope UXYZ and/or passage ALL. Not recovered human APDL and not attach TA1.", "track_equation": "Delta U_T = 0.5*sum_j(k_theta_j*theta_j^2); omega_wrong^2 = omega_0^2 + sum_j(k_theta_j*phi_j^2)/I_T", "operator_source": "agent Ultra S10 BEAM188 portal geometry plus existing C3 rigid equations", "source_sha256": source_sha256, "legacy_apdl_sha256": legacy_sha256, "output_sha256": output_sha256, "mapping_csv_sha256": digest_bytes(mapping_path.read_bytes()), "parent_nodes": len(c3_coordinates), "parent_elements": len(element_ids), "parent_equations": len(equations), "output_equations": len(output_equations), "scope": scope_name, "physical_station_count": len(unique_station_x), "selected_passage_side_count": len(selected_rows), "rewritten_equation_count": len(generated_equations), "rope_master_choice": rope_choice, "passage_master_choice": passage_choice, "height_mm_min": min(height_values), "height_mm_max": max(height_values), "height_mm_mean": sum(height_values) / len(height_values), "height_values_mm": height_values, "station_x_mm": unique_station_x, "control_max_coefficient_difference": control_max_coefficient_difference, "modal_roots": args.roots, "observation_node_count": len(OBSERVATION_NODES), "observation_nodes": OBSERVATION_NODES, "forbidden_changes_confirmed_absent": ["target-conditioned parameter", "spring element", "added mass", "material change", "section change", "prestress change", "node-coordinate change", "element-connectivity change", "hard rotational boundary"], "status": "CONSTRUCTED_TARGET_BLIND_NOT_YET_INTERPRETED"}  # Record complete identity, actual geometry, scope, and evidence boundaries.
    receipt_path = args.output.with_suffix(args.output.suffix + ".receipt.json")  # Derive the adjacent machine-readable receipt path.
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Publish the deterministic construction receipt.
    print(json.dumps({"variant": args.variant, "output_sha256": output_sha256, "selected_passage_sides": len(selected_rows), "physical_stations": len(unique_station_x), "rewritten_equations": len(generated_equations), "height_mm_min": min(height_values), "height_mm_max": max(height_values), "height_mm_mean": sum(height_values) / len(height_values), "control_max_coefficient_difference": control_max_coefficient_difference, "target_blind": True, "frequency_reproduced": False}, ensure_ascii=False, sort_keys=True))  # Emit a compact machine-readable construction summary.
if __name__ == "__main__":  # Execute the constructor only when invoked as a script.
    main()  # Run the validated target-blind high-master reconstruction.
