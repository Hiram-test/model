#!/usr/bin/env python3  # Target-blind C3 ROTX/LINK forward probes. Not undisclosed human APDL. frequency_reproduced=false. human_apdl=false.
from __future__ import annotations  # Preserve modern type annotations on the GitHub Actions Python runtime.
import argparse  # Parse explicit source, case, output, and root-count arguments.
import hashlib  # Bind the exact parent and every generated daughter to immutable SHA-256 identities.
import json  # Publish a machine-readable construction receipt beside every generated input deck.
import math  # Validate finite geometry and calculate physical gate-post lengths.
from collections import Counter, defaultdict  # Audit dependent equation coordinates and group LINK equations.
from pathlib import Path  # Handle all paths without depending on the working directory.

EXPECTED_PARENT_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"  # Freeze the validated C3 parent byte identity.
EXPECTED_PARENT_NODES = 91415  # Freeze the validated C3 physical node count.
EXPECTED_PARENT_ELEMENTS = 172998  # Freeze the validated C3 physical element count.
EXPECTED_PARENT_EQUATIONS = 21312  # Freeze the validated C3 original equation count.
CENTER_POSITIVE = (79599, 79701, 79803, 79905, 80007, 80109, 80211, 80313, 80415, 80517, 80619, 80721, 80823, 80925, 81027, 81129, 81231, 81333, 81435, 81537, 81639)  # List the positive-Y passage-center masters in longitudinal order.
CENTER_NEGATIVE = (82028, 82130, 82232, 82334, 82436, 82538, 82640, 82742, 82844, 82946, 83048, 83150, 83252, 83354, 83456, 83558, 83660, 83762, 83864, 83966, 84068)  # List the negative-Y passage-center masters in longitudinal order.
SUPPORT_OBSERVATIONS = tuple(range(79453, 79461))  # Preserve the eight tower/downpull observation nodes used by prior C3 tracking.
MAIN13_STATIONS = tuple(range(4, 17))  # Identify the thirteen main-span passage stations in the twenty-one-station order.
UNIFORM_MCT_HEIGHT_MM = 9080.0  # Preserve the independently noticed 9.08 m MCT gate-height clue without using target frequencies.
VALID_CASES = (  # Enumerate every preregistered target-blind ROTX/LINK forward probe.
    "BASE40",  # Recompute the unmodified parent with forty roots and compact observations.
    "ROT_MAIN13_CENTER",  # Clear global ROTX at the twenty-six main-span passage-center masters.
    "ROT_ALL21_CENTER",  # Clear global ROTX at all forty-two passage-center masters.
    "ROT_MAIN13_GATE_BOTTOM",  # Clear global ROTX at all main-span repeated gate-bottom masters.
    "ROT_ALL_GATE_BOTTOM",  # Clear global ROTX at all seventy-two repeated gate-bottom masters.
    "ROT_ALL_GATE_TOP",  # Clear global ROTX at all seventy-two repeated gate-top masters.
    "ROT_MAX_GATE_BOTTOM",  # Clear global ROTX only at the four posts of the tallest C3 gate station.
    "ROT_CENTER_PLUS_GATE_BOTTOM",  # Reproduce an overly broad ALL-selection spanning centers and gate-bottom masters.
    "LINK_ZERO_ALL",  # Tie every gate-bottom reference to the existing translation-only LINK node with zero eccentricity.
    "LINK_HIGH_ALL_REAL",  # Tie every real high-reference point to the existing translation-only LINK node using actual C3 height.
    "LINK_HIGH_MAIN13_REAL",  # Apply the same high-reference operation only in the main-span thirteen stations.
    "LINK_HIGH_MAX_REAL",  # Apply the real-height high-reference operation only at the tallest C3 gate station.
    "LINK_HIGH_ALL_9080",  # Reproduce a novice template that applies a uniform 9.08 m high reference to every repeated gate post.
    "LINK_TOP_ALL",  # Tie every actual gate-top node translation directly to the existing translation-only LINK node.
)  # Close the immutable case registry.


class BuildError(RuntimeError):  # Represent one fail-closed topology, equation, or source-identity violation.
    pass  # Keep the semantic exception intentionally behavior-free.


def require(condition: bool, code: str, detail: str) -> None:  # Enforce one explicit construction invariant.
    if not condition:  # Reject every condition that was not positively established.
        raise BuildError(f"{code}: {detail}")  # Surface a stable machine-readable error code and bounded context.


def sha256_file(path: Path) -> str:  # Compute an exact SHA-256 identity for a potentially large input deck.
    digest = hashlib.sha256()  # Initialize one fresh cryptographic digest state.
    with path.open("rb") as handle:  # Stream the selected file without holding a second 26 MB byte copy.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Traverse deterministic one-megabyte blocks to end of file.
            digest.update(block)  # Bind every source or daughter byte exactly once.
    return digest.hexdigest()  # Return the lowercase hexadecimal digest.


def parse_equation(lines: list[str], index: int) -> tuple[list[tuple[int, int, float]], int]:  # Decode one CalculiX equation block starting at the keyword line.
    require(index + 2 < len(lines), "TRUNCATED_EQUATION_HEADER", str(index + 1))  # Require a term-count row and at least one body row.
    term_count = int(lines[index + 1].strip())  # Read the declared number of sparse node-degree-coefficient triplets.
    fields: list[str] = []  # Accumulate continuation-row fields in their original order.
    cursor = index + 2  # Start at the first sparse equation body row.
    while len(fields) < 3 * term_count:  # Continue until the declared number of triplets has been recovered.
        require(cursor < len(lines), "TRUNCATED_EQUATION_BODY", str(index + 1))  # Reject an unexpected end of file.
        require(not lines[cursor].lstrip().startswith("*"), "EQUATION_BODY_KEYWORD_COLLISION", str(index + 1))  # Reject a premature next keyword.
        fields.extend(field.strip() for field in lines[cursor].split(",") if field.strip())  # Preserve every nonempty comma-separated field.
        cursor += 1  # Advance to a possible continuation row.
    require(len(fields) == 3 * term_count, "EQUATION_ARITY_MISMATCH", str(index + 1))  # Reject missing or extra sparse fields.
    terms = [(int(fields[offset]), int(fields[offset + 1]), float(fields[offset + 2])) for offset in range(0, len(fields), 3)]  # Convert every triplet to typed values.
    return terms, cursor  # Return the complete equation and the first line after its body.


def parse_parent(lines: list[str]) -> tuple[dict[int, tuple[float, float, float]], list[list[tuple[int, int, float]]], int]:  # Recover nodes, equations, and element count from the exact parent deck.
    nodes: dict[int, tuple[float, float, float]] = {}  # Index every physical node coordinate by solver label.
    equations: list[list[tuple[int, int, float]]] = []  # Preserve every original equation exactly for dependency and LINK audits.
    element_count = 0  # Count every physical element connectivity row.
    current_node = False  # Track whether data rows belong to a NODE block.
    current_element = False  # Track whether data rows belong to an ELEMENT block.
    index = 0  # Traverse the complete line array exactly once.
    while index < len(lines):  # Continue until every parent line has been classified.
        stripped = lines[index].strip()  # Normalize surrounding whitespace for keyword recognition only.
        upper = stripped.upper()  # Parse all CalculiX keywords case-insensitively.
        if upper == "*EQUATION":  # Decode one complete original equation block.
            terms, next_index = parse_equation(lines, index)  # Recover the declared sparse row without altering coefficients.
            equations.append(terms)  # Preserve the equation in source order.
            current_node = False  # Close any prior NODE context.
            current_element = False  # Close any prior ELEMENT context.
            index = next_index  # Resume after the consumed equation body.
            continue  # Avoid reprocessing consumed lines.
        if stripped.startswith("*"):  # Enter one new non-equation keyword context.
            current_node = upper == "*NODE" or upper.startswith("*NODE,")  # Admit coordinate NODE cards but not NODE FILE cards.
            current_element = upper.startswith("*ELEMENT,")  # Admit every physical element block.
            index += 1  # Advance to the first data row below the keyword.
            continue  # Complete keyword handling before data parsing.
        if not stripped or stripped.startswith("**"):  # Ignore blank and comment records without changing the active context.
            index += 1  # Advance past the non-data row.
            continue  # Preserve no topology data from comments.
        if current_node:  # Decode one physical node coordinate row.
            fields = [field.strip() for field in stripped.split(",")]  # Split the solver label and XYZ coordinates.
            require(len(fields) == 4, "NODE_ROW_INVALID", stripped[:120])  # Require exactly one node label and three coordinates.
            node = int(fields[0])  # Parse the physical node label.
            require(node not in nodes, "NODE_DUPLICATE", str(node))  # Reject coordinate-label collisions.
            coordinate = (float(fields[1]), float(fields[2]), float(fields[3]))  # Parse the frozen C3 coordinate triplet.
            require(all(math.isfinite(value) for value in coordinate), "NODE_COORDINATE_NONFINITE", str(node))  # Reject NaN or infinite source geometry.
            nodes[node] = coordinate  # Preserve the exact coordinate.
        elif current_element:  # Count one physical element connectivity row.
            element_count += 1  # Increment exactly once per non-comment data row below an ELEMENT keyword.
        index += 1  # Advance to the next unconsumed source row.
    return nodes, equations, element_count  # Return the complete immutable topology inventory.


def dependent_dofs(equations: list[list[tuple[int, int, float]]]) -> Counter[tuple[int, int]]:  # Count all first-term dependent coordinates in original equations.
    counter: Counter[tuple[int, int]] = Counter()  # Initialize the dependent-coordinate multiset.
    for terms in equations:  # Traverse every validated original equation.
        require(bool(terms), "EMPTY_EQUATION", "original")  # Reject an impossible empty sparse row.
        counter[(terms[0][0], terms[0][1])] += 1  # Record the first node-degree coordinate as the CalculiX dependent coordinate.
    require(max(counter.values(), default=0) == 1, "ORIGINAL_DEPENDENT_DOF_DUPLICATE", str(max(counter.values(), default=0)))  # Require each original dependent coordinate at most once.
    return counter  # Return the original dependency inventory.


def group_link_equations(equations: list[list[tuple[int, int, float]]]) -> dict[int, dict[int, list[tuple[int, int, float]]]]:  # Locate passage-center equations tied to translation-only LINK nodes.
    centers = set(CENTER_POSITIVE + CENTER_NEGATIVE)  # Form the complete expected passage-center master set.
    grouped: dict[int, dict[int, list[tuple[int, int, float]]]] = defaultdict(dict)  # Group one exact original equation by center and translation component.
    for terms in equations:  # Traverse every original equation.
        if len(terms) != 2:  # Retain only canonical two-term translation relations.
            continue  # Skip rigid-offset and multi-node rows.
        first, second = terms  # Select the dependent and independent sparse terms.
        if first[1] not in (1, 2, 3) or second[1] != first[1]:  # Require a matching translational component.
            continue  # Reject rotations and mixed-component relations.
        if abs(first[2] - 1.0) > 1.0e-12 or abs(second[2] + 1.0) > 1.0e-12:  # Require the canonical dependent minus independent form.
            continue  # Reject scaled or sign-reversed equations.
        if second[0] not in centers:  # Require the independent coordinate to be one expected passage center.
            continue  # Skip unrelated translation ties.
        grouped[second[0]][first[1]] = terms  # Preserve the exact source equation for later substitution.
    return grouped  # Return all discovered center-to-LINK translation relations.


def nearest_nodes(nodes: dict[int, tuple[float, float, float]], target: tuple[float, float, float], excluded: set[int], tolerance: float) -> list[int]:  # Locate all source nodes coincident with one derived geometric target.
    tx, ty, tz = target  # Expand the target coordinate once.
    matches: list[int] = []  # Collect every node within the strict Euclidean tolerance.
    for node, (x, y, z) in nodes.items():  # Traverse every source coordinate.
        if node in excluded:  # Skip labels already consumed by a prior chain role.
            continue  # Preserve uniqueness across derived master chains.
        if abs(x - tx) <= tolerance and abs(y - ty) <= tolerance and abs(z - tz) <= tolerance:  # Apply the strict coordinate-box prefilter.
            if math.dist((x, y, z), target) <= tolerance:  # Confirm full Euclidean coincidence.
                matches.append(node)  # Preserve the coincident solver label.
    return sorted(matches)  # Return deterministic ascending labels.


def derive_chains(nodes: dict[int, tuple[float, float, float]], equations: list[list[tuple[int, int, float]]]) -> tuple[list[dict[str, object]], dict[int, dict[int, list[tuple[int, int, float]]]]]:  # Recover repeated gate-bottom, gate-top, and translation-only LINK chains from exact C3 topology.
    link_equations = group_link_equations(equations)  # Recover the original passage-center translation relations.
    complete_centers = [center for center, components in link_equations.items() if set(components) == {1, 2, 3}]  # Select centers with complete XYZ translation ties.
    require(len(complete_centers) == 36, "COMPLETE_LINK_CENTER_COUNT_MISMATCH", str(len(complete_centers)))  # Require the known thirty-six framed passage sides.
    all_centers = list(zip(CENTER_POSITIVE, CENTER_NEGATIVE, strict=True))  # Preserve the twenty-one longitudinal station pairs.
    framed_stations = [station for station, pair in enumerate(all_centers, start=1) if all(center in link_equations and set(link_equations[center]) == {1, 2, 3} for center in pair)]  # Select stations with both translation-only LINK centers.
    require(len(framed_stations) == 18, "FRAMED_STATION_COUNT_MISMATCH", str(len(framed_stations)))  # Require the known eighteen station planes carrying repeated high gates.
    chains: list[dict[str, object]] = []  # Accumulate four post chains per framed station.
    used_bottoms: set[int] = set()  # Prevent a lower master from being assigned twice.
    used_tops: set[int] = set()  # Prevent a high endpoint from being assigned twice.
    for station in framed_stations:  # Traverse each framed passage plane in longitudinal order.
        for side, center in (("P", CENTER_POSITIVE[station - 1]), ("N", CENTER_NEGATIVE[station - 1])):  # Traverse the positive and negative catwalk sides.
            cx, cy, cz = nodes[center]  # Select the passage-side master coordinate.
            candidate_bottoms = [node for node, (x, y, z) in nodes.items() if node not in used_bottoms and abs(x - cx) < 1.0e-6 and abs(z - cz) < 1.0e-6 and 4000.0 <= abs(y - cy) <= 6500.0]  # Find the two outer lower six-DOF gate masters on the same station line and elevation.
            require(len(candidate_bottoms) == 2, "BOTTOM_MASTER_COUNT_MISMATCH", f"station={station} side={side} count={len(candidate_bottoms)}")  # Require exactly two repeated posts per catwalk side.
            for bottom in sorted(candidate_bottoms, key=lambda node: nodes[node][1]):  # Traverse the lower masters in deterministic transverse order.
                bx, by, bz = nodes[bottom]  # Select the lower master coordinate.
                candidate_tops = [node for node, (x, y, z) in nodes.items() if node not in used_tops and abs(x - bx) < 1.0e-6 and abs(y - by) < 1.0e-6 and z > bz + 5000.0 and z < bz + 10000.0]  # Find the high gate endpoint directly above the lower master.
                require(len(candidate_tops) == 1, "TOP_MASTER_COUNT_MISMATCH", f"station={station} bottom={bottom} count={len(candidate_tops)}")  # Require one unique physical high endpoint.
                top = candidate_tops[0]  # Select the unique high endpoint.
                used_bottoms.add(bottom)  # Reserve the lower master.
                used_tops.add(top)  # Reserve the high endpoint.
                link_nodes = {link_equations[center][component][0][0] for component in (1, 2, 3)}  # Recover the dependent translation-only LINK node used by all three source equations.
                require(len(link_nodes) == 1, "LINK_NODE_COMPONENT_MISMATCH", str(center))  # Require one LINK node for all translations.
                link_node = next(iter(link_nodes))  # Select the unique translation-only LINK node.
                offset = (nodes[top][0] - bx, nodes[top][1] - by, nodes[top][2] - bz)  # Compute the exact high-reference eccentricity from frozen C3 geometry.
                vertical_height = offset[2]  # Preserve the global vertical lever arm highlighted by the 9.08 m clue.
                member_length = math.dist(nodes[bottom], nodes[top])  # Preserve the full physical endpoint distance.
                require(5000.0 < vertical_height < 10000.0, "GATE_HEIGHT_OUT_OF_RANGE", f"bottom={bottom} h={vertical_height}")  # Reject an unrelated coincident node.
                require(all(link_equations[center][component][0][0] == link_node for component in (1, 2, 3)), "LINK_NODE_COMPONENT_MISMATCH", str(center))  # Require one LINK node for all translations.
                chains.append({"station": station, "side": side, "center": center, "bottom": bottom, "top": top, "link": link_node, "offset_mm": offset, "vertical_height_mm": vertical_height, "member_length_mm": member_length})  # Record the target-blind physical topology.
    require(len(chains) == 72, "HIGH_MASTER_CHAIN_COUNT_MISMATCH", str(len(chains)))  # Require the known seventy-two repeated post chains.
    require(len({int(chain["bottom"]) for chain in chains}) == 72, "BOTTOM_NODE_DUPLICATE", "bottom")  # Require one unique lower master per chain.
    require(len({int(chain["top"]) for chain in chains}) == 72, "TOP_NODE_DUPLICATE", "top")  # Require one unique upper endpoint per chain.
    require(len({int(chain["link"]) for chain in chains}) == 36, "LINK_NODE_COUNT_MISMATCH", str(len({int(chain["link"]) for chain in chains})))  # Require two translation-only LINK nodes at each of eighteen framed stations.
    return chains, link_equations  # Return the complete physical chain inventory and exact original LINK relations.


def combine_terms(terms: list[tuple[int, int, float]]) -> list[tuple[int, int, float]]:  # Merge repeated sparse coordinates and remove exact cancellations.
    order: list[tuple[int, int]] = []  # Preserve the first occurrence order for deterministic output.
    values: dict[tuple[int, int], float] = {}  # Accumulate one coefficient per sparse node-degree coordinate.
    for node, dof, coefficient in terms:  # Traverse every proposed term in physical derivation order.
        key = (node, dof)  # Form the sparse coordinate identity.
        if key not in values:  # Register a coordinate on its first occurrence.
            order.append(key)  # Preserve deterministic serialization order.
            values[key] = 0.0  # Initialize its accumulated coefficient.
        values[key] += coefficient  # Add the current contribution.
    return [(node, dof, values[(node, dof)]) for node, dof in order if abs(values[(node, dof)]) > 1.0e-12]  # Return only nonzero combined terms.


def cross_terms(master: int, offset: tuple[float, float, float], component: int) -> list[tuple[int, int, float]]:  # Express one component of theta_master cross offset.
    dx, dy, dz = offset  # Select the exact reference-point eccentricity.
    if component == 1:  # Form theta_y times dz minus theta_z times dy for longitudinal displacement.
        return [(master, 5, dz), (master, 6, -dy)]  # Return the longitudinal rigid-offset terms.
    if component == 2:  # Form theta_z times dx minus theta_x times dz for transverse displacement.
        return [(master, 6, dx), (master, 4, -dz)]  # Return the transverse rigid-offset terms carrying the critical ROTX lever arm.
    require(component == 3, "CROSS_COMPONENT_INVALID", str(component))  # Admit only the three translational components.
    return [(master, 4, dy), (master, 5, -dx)]  # Return the vertical rigid-offset terms.


def equation_lines(terms: list[tuple[int, int, float]]) -> list[str]:  # Serialize one compact sparse equation in CalculiX syntax.
    require(2 <= len(terms) <= 10, "NEW_EQUATION_TERM_COUNT_INVALID", str(len(terms)))  # Keep every generated row within the expected compact range.
    body: list[str] = []  # Accumulate node-degree-coefficient fields before serialization.
    for node, dof, coefficient in terms:  # Traverse each sparse term in deterministic order.
        body.extend((str(node), str(dof), f"{coefficient:.12g}"))  # Emit a parser-safe compact numeric representation.
    return ["*EQUATION", str(len(terms)), ", ".join(body)]  # Return the complete three-line equation card.


def replace_frequency_roots(lines: list[str], roots: int) -> list[str]:  # Replace only the requested modal root count.
    output = list(lines)  # Copy the source line array for controlled mutation.
    indices = [index for index, line in enumerate(output) if line.strip().upper().startswith("*FREQUENCY")]  # Locate the unique modal keyword.
    require(len(indices) == 1, "FREQUENCY_CARD_COUNT_MISMATCH", str(len(indices)))  # Require the validated single modal step.
    data_index = indices[0] + 1  # Start below the frequency keyword.
    while data_index < len(output) and (not output[data_index].strip() or output[data_index].lstrip().startswith("**")):  # Skip blank and comment rows only.
        data_index += 1  # Advance to the root-count data row.
    require(data_index < len(output), "FREQUENCY_DATA_MISSING", str(indices[0] + 1))  # Reject a truncated modal step.
    int(output[data_index].split(",", 1)[0].strip())  # Require the original first field to be an integer.
    output[data_index] = str(roots)  # Replace only the number of requested eigenpairs.
    return output  # Return the root-adjusted line array.


def replace_node_file(lines: list[str]) -> list[str]:  # Route modal displacement output to the compact forensic observation set.
    output = list(lines)  # Copy the source line array for controlled output-card mutation.
    indices = [index for index, line in enumerate(output) if line.strip().upper().startswith("*NODE FILE")]  # Locate the unique nodal file-output card.
    require(len(indices) == 1, "NODE_FILE_CARD_COUNT_MISMATCH", str(len(indices)))  # Require one validated output card.
    output[indices[0]] = "*NODE FILE, NSET=N_FORENSIC_OBS, OUTPUT=2D"  # Preserve six-component modal vectors on the common physical observation set.
    return output  # Return the output-routed line array.


def insert_before_first(lines: list[str], keyword: str, inserted: list[str]) -> list[str]:  # Insert a generated block before the first selected keyword.
    index = next((index for index, line in enumerate(lines) if line.strip().upper().startswith(keyword)), None)  # Locate the first matching keyword.
    require(index is not None, "INSERTION_KEYWORD_MISSING", keyword)  # Reject an unexpected parent layout.
    return lines[:index] + inserted + lines[index:]  # Preserve every source line around the insertion point.


def select_chains(case: str, chains: list[dict[str, object]]) -> list[dict[str, object]]:  # Select the gate-post chains implied by one human workflow action.
    if case in ("LINK_HIGH_MAIN13_REAL",):  # Restrict one high-link operation to the thirteen main-span passage planes.
        return [chain for chain in chains if int(chain["station"]) in MAIN13_STATIONS]  # Return every repeated post in those thirteen stations.
    if case in ("LINK_HIGH_MAX_REAL",):  # Restrict one high-link operation to the tallest C3 gate station.
        maximum = max(float(chain["vertical_height_mm"]) for chain in chains)  # Recover the maximum real C3 vertical lever arm.
        return [chain for chain in chains if abs(float(chain["vertical_height_mm"]) - maximum) < 1.0e-6]  # Return the four posts at that station.
    return list(chains)  # Use all seventy-two repeated post chains for every other LINK case.


def select_rotation_nodes(case: str, chains: list[dict[str, object]]) -> list[int]:  # Select the explicit ROTX cleanup scope for one old-ANSYS-style action.
    if case == "ROT_MAIN13_CENTER":  # Model a loop restricted to the thirteen main-span passage masters.
        return sorted([CENTER_POSITIVE[index - 1] for index in MAIN13_STATIONS] + [CENTER_NEGATIVE[index - 1] for index in MAIN13_STATIONS])  # Return twenty-six side-center masters.
    if case == "ROT_ALL21_CENTER":  # Model an unfiltered selection of all passage-center masters.
        return sorted(CENTER_POSITIVE + CENTER_NEGATIVE)  # Return all forty-two center masters.
    if case == "ROT_MAIN13_GATE_BOTTOM":  # Model a repeated gate macro restricted to main-span lower masters.
        return sorted({int(chain["bottom"]) for chain in chains if int(chain["station"]) in MAIN13_STATIONS})  # Return all available main-span lower gate masters.
    if case == "ROT_ALL_GATE_BOTTOM":  # Model cleanup on every lower master in the repeated gate macro.
        return sorted({int(chain["bottom"]) for chain in chains})  # Return all seventy-two lower gate masters.
    if case == "ROT_ALL_GATE_TOP":  # Model cleanup on every physical high endpoint used as a pilot/master.
        return sorted({int(chain["top"]) for chain in chains})  # Return all seventy-two high gate endpoints.
    if case == "ROT_MAX_GATE_BOTTOM":  # Model cleanup only at the tallest C3 gate station.
        maximum = max(float(chain["vertical_height_mm"]) for chain in chains)  # Recover the maximum real vertical gate height.
        return sorted({int(chain["bottom"]) for chain in chains if abs(float(chain["vertical_height_mm"]) - maximum) < 1.0e-6})  # Return the four lower masters at that station.
    if case == "ROT_CENTER_PLUS_GATE_BOTTOM":  # Model an overly broad component selection spanning passage and gate masters.
        return sorted(set(CENTER_POSITIVE + CENTER_NEGATIVE) | {int(chain["bottom"]) for chain in chains})  # Return the complete combined master scope.
    return []  # Return no explicit rotation constraints for baseline and LINK-reparameterization cases.


def build(source: Path, output: Path, case: str, roots: int) -> dict[str, object]:  # Generate one complete target-blind full-C3 daughter deck.
    require(case in VALID_CASES, "CASE_INVALID", case)  # Reject every unregistered variant name.
    require(roots >= 40, "ROOT_COUNT_TOO_SMALL", str(roots))  # Require enough roots for dense-cluster branch tracking.
    source_sha = sha256_file(source)  # Compute the exact parent byte identity.
    require(source_sha == EXPECTED_PARENT_SHA256, "PARENT_SHA256_MISMATCH", source_sha)  # Bind all daughters to the validated C3 parent.
    source_lines = source.read_text(encoding="ascii").splitlines()  # Decode the frozen parent without newline ambiguity.
    nodes, equations, element_count = parse_parent(source_lines)  # Recover the complete topology and original equation inventory.
    require(len(nodes) == EXPECTED_PARENT_NODES, "PARENT_NODE_COUNT_MISMATCH", str(len(nodes)))  # Require the validated C3 node count.
    require(element_count == EXPECTED_PARENT_ELEMENTS, "PARENT_ELEMENT_COUNT_MISMATCH", str(element_count))  # Require the validated C3 element count.
    require(len(equations) == EXPECTED_PARENT_EQUATIONS, "PARENT_EQUATION_COUNT_MISMATCH", str(len(equations)))  # Require the validated C3 equation count.
    chains, link_equations = derive_chains(nodes, equations)  # Recover the seventy-two real high-reference chains and their LINK relations.
    dependencies = dependent_dofs(equations)  # Audit every original dependent degree of freedom.
    rotation_nodes = select_rotation_nodes(case, chains)  # Select any explicit ROTX cleanup scope.
    selected_chains = select_chains(case, chains) if case.startswith("LINK_") else []  # Select the chain scope for a high-link operation.
    generated_equations: list[list[tuple[int, int, float]]] = []  # Accumulate new target-blind kinematic rows.
    if case.startswith("LINK_"):  # Build one translation-only LINK/pilot workflow variant.
        for chain in selected_chains:  # Traverse every selected physical gate-post chain.
            center = int(chain["center"])  # Select the original passage-side master associated with the LINK relation.
            bottom = int(chain["bottom"])  # Select the lower six-DOF gate master.
            top = int(chain["top"])  # Select the actual high gate endpoint.
            real_offset = tuple(float(value) for value in chain["offset_mm"])  # Select the actual C3 high-reference eccentricity.
            if case == "LINK_ZERO_ALL":  # Suppress the high-reference lever arm while preserving the same selected topology.
                working_offset = (0.0, 0.0, 0.0)  # Define a zero-height control reference.
            elif case == "LINK_HIGH_ALL_9080":  # Reproduce a uniform-height copied gate template.
                working_offset = (0.0, 0.0, UNIFORM_MCT_HEIGHT_MM)  # Apply the independently observed 9.08 m vertical reference at every repeated post.
            else:  # Preserve the actual C3 post geometry for real-height cases.
                working_offset = real_offset  # Use the exact upper-minus-lower coordinate difference.
            for component in (1, 2, 3):  # Generate all three translational relations for each selected chain.
                source_equation = link_equations[center][component]  # Select the exact original dependent-LINK equation for this component.
                require(source_equation[0][1] == component and abs(source_equation[0][2] - 1.0) < 1.0e-12, "LINK_EQUATION_DEPENDENT_TERM_INVALID", f"center={center} dof={component}")  # Require the canonical original LINK term.
                if case == "LINK_TOP_ALL":  # Tie the actual high beam endpoint directly to the translation-only LINK node.
                    dependent_node = top  # Select the physical high endpoint as the new dependent coordinate.
                    require(dependencies[(dependent_node, component)] == 0, "TOP_TRANSLATION_ALREADY_DEPENDENT", f"node={dependent_node} dof={component}")  # Prevent duplicate dependent coordinates.
                    terms = [(dependent_node, component, 1.0)] + source_equation[1:]  # Express top minus LINK equals zero after substituting the original LINK relation.
                else:  # Tie the rigid high-reference point carried by the lower six-DOF master to the translation-only LINK node.
                    dependent_node = bottom  # Select the lower six-DOF master translation as the new dependent coordinate.
                    require(dependencies[(dependent_node, component)] == 0, "BOTTOM_TRANSLATION_ALREADY_DEPENDENT", f"node={dependent_node} dof={component}")  # Prevent duplicate dependent coordinates.
                    terms = [(dependent_node, component, 1.0)] + source_equation[1:] + cross_terms(bottom, working_offset, component)  # Express bottom plus theta cross offset minus LINK equals zero.
                generated_equations.append(combine_terms(terms))  # Merge repeated sparse terms before serialization.
    observation_nodes = sorted(set(CENTER_POSITIVE + CENTER_NEGATIVE + SUPPORT_OBSERVATIONS + tuple(int(chain["bottom"]) for chain in chains) + tuple(int(chain["top"]) for chain in chains) + tuple(int(chain["link"]) for chain in chains)))  # Assemble the common physical tracking set.
    require(len(observation_nodes) == 230, "OBSERVATION_NODE_COUNT_MISMATCH", str(len(observation_nodes)))  # Freeze the compact observation cardinality.
    inserted: list[str] = ["** TARGET-BLIND C3 ROTX/LINK FORWARD PROBE. NOT human APDL. frequency_reproduced=false.", f"** CASE={case}", "*NSET, NSET=N_FORENSIC_OBS"]  # Begin the deterministic pre-step insertion block.
    for start in range(0, len(observation_nodes), 16):  # Wrap observation labels into bounded CalculiX rows.
        inserted.append(", ".join(str(node) for node in observation_nodes[start:start + 16]))  # Emit at most sixteen node labels per row.
    if rotation_nodes:  # Add an explicit old-ANSYS-style rotational cleanup boundary block when selected.
        inserted.extend(["** ANALOG OF D,MASTER,ROTX,0. Hypothesis only; not recovered human APDL.", "*BOUNDARY"])  # Document the discrete ROTX boundary being tested.
        inserted.extend(f"{node}, 4, 4, 0." for node in rotation_nodes)  # Fix only global longitudinal rotation at each selected master.
    if generated_equations:  # Add translation-only LINK/high-reference constraints for the selected kinematic variant.
        inserted.append("** ANALOG OF A HIGH PILOT/MASTER TO A TRANSLATION-ONLY LINK NODE. Hypothesis only; not human APDL.")  # Document the discrete LINK hypothesis being tested.
        for equation in generated_equations:  # Serialize every generated sparse row.
            inserted.extend(equation_lines(equation))  # Append one complete CalculiX equation block.
    if not rotation_nodes and not generated_equations:  # Preserve an explicit no-op marker for the BASE40 control.
        inserted.append("** BASE40 ADDS NO BOUNDARY, EQUATION, ELEMENT, MASS, MATERIAL, OR PRESTRESS CHANGE")  # Document the untouched physical baseline.
    daughter_lines = replace_frequency_roots(source_lines, roots)  # Increase only the requested modal range.
    daughter_lines = replace_node_file(daughter_lines)  # Route modal output to the common forensic observation set.
    daughter_lines = insert_before_first(daughter_lines, "*STEP", inserted)  # Insert observations and selected kinematics immediately before the modal step.
    heading_index = next((index for index, line in enumerate(daughter_lines) if line.strip().upper() == "*HEADING"), None)  # Locate the parent heading keyword.
    require(heading_index is not None, "HEADING_MISSING", str(source))  # Require the validated heading structure.
    daughter_lines.insert(heading_index + 1, f"FORENSIC FORWARD PROBE {case}; full C3; target-blind; not human APDL; frequency_reproduced=false")  # Stamp the exact case into native solver outputs.
    output.parent.mkdir(parents=True, exist_ok=True)  # Create the selected output directory.
    output.write_text("\n".join(daughter_lines) + "\n", encoding="ascii")  # Publish the complete full-entity daughter input deck.
    output_sha = sha256_file(output)  # Bind the generated daughter byte identity.
    vertical_heights = [float(chain["vertical_height_mm"]) for chain in chains]  # Collect real C3 global vertical post heights.
    member_lengths = [float(chain["member_length_mm"]) for chain in chains]  # Collect real physical endpoint distances.
    receipt = {  # Build the machine-readable construction and evidence-boundary record.
        "status": "TARGET_BLIND_FULL_C3_FORWARD_PROBE",  # Mark the result as a causal forward probe rather than an inverse fit.
        "case": case,  # Preserve the exact preregistered variant name.
        "source": str(source),  # Preserve the selected parent path.
        "source_sha256": source_sha,  # Preserve the validated parent digest.
        "output": str(output),  # Preserve the generated daughter path.
        "output_sha256": output_sha,  # Preserve the exact daughter digest.
        "target_frequencies_read": False,  # Confirm that attachment frequencies never entered variant generation.
        "frequency_reproduced": False,  # Prohibit reading any later root as attach TA1.
        "human_apdl": False,  # This is a forward hypothesis, not recovered undisclosed human APDL.
        "not_attach_ta1": True,  # 9.08 m and ROTX/LINK scopes are not attach reproduction.
        "not_undisclosed_human_apdl": True,  # No original APDL command text is available.
        "nodes_changed": 0,  # Confirm that no physical node or coordinate was edited.
        "elements_changed": 0,  # Confirm that no physical element was added, deleted, or retyped.
        "mass_changed": False,  # Confirm that no MASS value was altered in the human-kinematic route.
        "material_changed": False,  # Confirm that all material properties remain frozen.
        "prestress_changed": False,  # Confirm that all UCAB3 initial-force rows remain frozen.
        "rotation_cleanup_nodes": rotation_nodes,  # Preserve the exact explicit ROTX boundary scope.
        "rotation_cleanup_node_count": len(rotation_nodes),  # Preserve its cardinality.
        "new_equation_count": len(generated_equations),  # Preserve the exact number of high-reference translation constraints.
        "selected_chain_count": len(selected_chains),  # Preserve the number of affected physical gate posts.
        "selected_chains": selected_chains,  # Preserve bottom, top, center, LINK, and real-height context for every affected post.
        "all_chain_count": len(chains),  # Preserve the complete seventy-two-chain inventory.
        "gate_vertical_height_mm_min": min(vertical_heights),  # Preserve the minimum global vertical lever arm.
        "gate_vertical_height_mm_max": max(vertical_heights),  # Preserve the maximum global vertical lever arm.
        "gate_member_length_mm_max": max(member_lengths),  # Preserve the maximum physical post endpoint distance.
        "uniform_mct_height_mm": UNIFORM_MCT_HEIGHT_MM if case == "LINK_HIGH_ALL_9080" else None,  # Preserve the independent uniform-template height only where used.
        "roots": roots,  # Preserve the requested spectral range.
        "observation_nodes": observation_nodes,  # Preserve the common branch-tracking set.
        "theory": {  # State the exact Track mechanism implemented by this discrete model.
            "energy": "Delta_U_T = 0.5 * sum_j(k_theta_j * theta(x_j)^2)",  # Preserve the discrete artificial roll-foundation energy form.
            "frequency": "omega_wrong_n^2 = omega_0_n^2 + sum_j(k_theta_j * phi_n(x_j)^2) / I_T_n",  # Preserve the modal frequency-square perturbation form.
            "human_process": "Hypothesis only: batch-clear ROTX or attach a high pilot to a translation-only LINK node. Not recovered human APDL and not attach TA1.",  # Preserve the historical behavior hypothesis without claiming the unavailable command text.
            "discrete_realization": "No fitted k_theta is supplied. The existing full-C3 UCOR6/UCAB3 tangent generates the reaction stiffness produced by the selected boundary/equation scope.",  # Explain why the forward model is not a low-dimensional spring fit.
        },  # Close the Track-theory receipt block.
        "evidence_boundary": "The variant can support or falsify an equivalent error mechanism, but cannot prove the unavailable original APDL command text.",  # Preserve the forensic inference boundary.
    }  # Close the receipt mapping.
    output.with_suffix(output.suffix + ".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Publish the readable machine audit beside the input deck.
    return receipt  # Return the completed record to the command-line entry point.


def main() -> int:  # Execute one deterministic command-line build.
    parser = argparse.ArgumentParser(description="Build target-blind C3 ROTX/LINK forward probes. Not human APDL. frequency_reproduced=false.")  # Define the bounded tool interface.
    parser.add_argument("--source", required=True, type=Path)  # Require the exact validated C3 parent input.
    parser.add_argument("--output", required=True, type=Path)  # Require one explicit full daughter output path.
    parser.add_argument("--case", required=True, choices=VALID_CASES)  # Require one preregistered human-workflow case.
    parser.add_argument("--roots", type=int, default=40)  # Extract forty modes by default for dense-cluster tracking.
    arguments = parser.parse_args()  # Parse and validate all command-line fields.
    receipt = build(arguments.source, arguments.output, arguments.case, arguments.roots)  # Generate the selected full-C3 daughter.
    print(json.dumps({key: receipt[key] for key in ("status", "case", "output_sha256", "rotation_cleanup_node_count", "new_equation_count", "selected_chain_count", "roots")}, ensure_ascii=False, sort_keys=True))  # Emit one compact build receipt.
    return 0  # Signal successful deterministic generation.


if __name__ == "__main__":  # Execute the command-line path only when invoked directly.
    raise SystemExit(main())  # Return the stable process status to the caller.
