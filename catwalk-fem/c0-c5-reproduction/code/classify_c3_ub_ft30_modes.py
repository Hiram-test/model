from __future__ import annotations  # Keep annotations deterministic on the supported Python runtime.

import csv  # Publish a compact mode-by-mode engineering table.
import hashlib  # Bind the exact deck and solver result inputs.
import heapq  # Retain only the highest-amplitude nodes while streaming the large FRD.
import json  # Publish detailed machine-readable classification evidence.
import math  # Compute displacement norms and component fractions.
import re  # Parse fixed-format FRD exponent fields robustly when adjacent signs occur.
from collections import Counter, defaultdict  # Aggregate incident topology labels without dense matrices.
from pathlib import Path  # Resolve project artifacts independently of the invoking shell.

BASE = Path(__file__).resolve().parent.parent  # Anchor the C0-C5 reproduction project.
DECK = BASE / "solver" / "c3_ub_frozen_tangent_diag" / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"  # Bind the parser-safe physical-property fourteen-root C3 deck.
RUN_DIR = BASE / "solver" / "runs" / "C3UBFT14_PARSER_SAFE_667c5047"  # Select the completed parser-safe C3 run.
FRD = RUN_DIR / "job.frd"  # Select the exact full nodal mode-shape result.
DAT = RUN_DIR / "job.dat"  # Select the exact eigenvalue table.
ARTIFACTS = BASE / "artifacts"  # Store immutable classification outputs beside prior evidence.
EXPECTED_DECK_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"  # Freeze the generated deck bytes.
TOP_COUNT = 12  # Retain enough extrema to distinguish a local mechanism from a global branch.
FLOAT_PATTERN = re.compile(r"[-+]?\d*\.\d+E[-+]\d+")  # Capture adjacent CalculiX scientific fields without relying on whitespace.


class ClassificationError(RuntimeError):  # Represent one stable fail-closed analysis violation.
    pass  # Keep the semantic exception behavior-free.


def require(condition: bool, code: str, detail: str) -> None:  # Enforce one exact analysis contract.
    if not condition:  # Reject every condition not positively established.
        raise ClassificationError(f"{code}: {detail}")  # Surface a stable bounded diagnostic.


def sha256_file(path: Path) -> str:  # Hash a potentially large input without duplicate memory.
    digest = hashlib.sha256()  # Allocate a fresh exact-byte digest.
    with path.open("rb") as handle:  # Stream the selected file to EOF.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Bound transient hashing memory to one MiB.
            digest.update(block)  # Fold every byte into the identity.
    return digest.hexdigest()  # Return the complete lowercase identity.


def audit_comments(path: Path) -> dict[str, object]:  # Enforce a comment on every nonempty analysis-source line.
    lines = path.read_text(encoding="utf-8").splitlines()  # Read the source exactly once.
    violations = [index for index, line in enumerate(lines, 1) if line.strip() and "#" not in line]  # Locate every uncommented nonempty line.
    require(not violations, "SOURCE_COMMENT_AUDIT_FAILED", repr(violations[:20]))  # Reject publication on any user-style violation.
    return {"path": str(path.relative_to(BASE)), "nonempty_lines": sum(bool(line.strip()) for line in lines), "violations": violations, "status": "PASS"}  # Return complete source-audit evidence.


def topology_label(element_type: str, elset: str) -> str:  # Collapse exact property sets into meaningful physical families.
    if element_type == "UCAB3":  # Preserve each physical prestressed axial family.
        return elset  # Return E_BEARING, E_GANTRY, or E_DOWNPULL directly.
    if element_type == "MASS":  # Identify nodes carrying native attached mass.
        return "NATIVE_MASS"  # Use one stable family label.
    if elset.startswith("UG61_"):  # Identify the original SEC61 upper-bound member family.
        return "UCOR6_SEC61"  # Collapse property-level fragmentation.
    if elset.startswith("UG62_"):  # Identify the original SEC62 upper-bound member family.
        return "UCOR6_SEC62"  # Collapse property-level fragmentation.
    if elset.startswith("UG63_"):  # Identify the restored passage SEC63 family.
        return "UCOR6_SEC63"  # Collapse property-level fragmentation.
    if elset.startswith("UG64_"):  # Identify the retained passage SEC64 family.
        return "UCOR6_SEC64"  # Collapse property-level fragmentation.
    if elset.startswith("UG65_"):  # Identify the restored passage SEC65 family.
        return "UCOR6_SEC65"  # Collapse property-level fragmentation.
    if elset.startswith("UG66_"):  # Identify the restored passage SEC66 family.
        return "UCOR6_SEC66"  # Collapse property-level fragmentation.
    if elset == "UXL":  # Identify the large converted transverse member family.
        return "UCOR6_CROSS_LARGE"  # Return its compact engineering name.
    if elset == "UXS":  # Identify the small converted transverse member family.
        return "UCOR6_CROSS_SMALL"  # Return its compact engineering name.
    if elset == "E_EQUALIZER_ROT_ACT":  # Identify the four numerical rotational activators explicitly.
        return "EQUALIZER_ROT_ACT"  # Keep numerical activators visible in extrema audits.
    return f"{element_type}:{elset}"  # Preserve every unexpected family rather than silently dropping it.


def parse_deck() -> tuple[dict[int, tuple[float, float, float]], dict[int, Counter[str]], set[int], set[int], set[int]]:  # Recover node coordinates, incident families, and constraint roles.
    coordinates: dict[int, tuple[float, float, float]] = {}  # Store exact model coordinates by solver node.
    incidence: dict[int, Counter[str]] = defaultdict(Counter)  # Count incident physical families by node.
    dependent_nodes: set[int] = set()  # Track the first node of every multiple-point equation.
    master_nodes: set[int] = set()  # Track every nondependent node appearing in a multiple-point equation.
    boundary_nodes: set[int] = set()  # Track nodes carrying at least one single-point boundary condition.
    state = ""  # Track the active keyword data grammar.
    element_type = ""  # Preserve the current element type.
    element_elset = ""  # Preserve the current element set.
    equation_terms_needed = 0  # Count remaining numeric MPC term fields after the row count.
    equation_values: list[str] = []  # Buffer a possibly wrapped equation record.
    with DECK.open("r", encoding="utf-8") as handle:  # Stream the large deck once.
        for raw in handle:  # Visit every input line in exact order.
            line = raw.strip()  # Normalize only surrounding whitespace for card parsing.
            if not line or line.startswith("**"):  # Ignore blank records and comments.
                continue  # Advance without changing active data state.
            if line.startswith("*"):  # Enter a new keyword grammar.
                upper = line.upper()  # Normalize keyword matching without altering data.
                state = ""  # Close the preceding data grammar by default.
                equation_values = []  # Clear any completed equation buffer.
                equation_terms_needed = 0  # Clear the completed equation field count.
                if upper.startswith("*NODE") and not upper.startswith("*NODE FILE"):  # Select model coordinate records only.
                    state = "node"  # Mark coordinate data.
                elif upper.startswith("*ELEMENT"):  # Select element connectivity records.
                    state = "element"  # Mark connectivity data.
                    type_match = re.search(r"TYPE=([^,\s]+)", upper)  # Extract the exact element type.
                    set_match = re.search(r"ELSET=([^,\s]+)", upper)  # Extract the exact element set.
                    require(type_match is not None and set_match is not None, "ELEMENT_HEADER_INVALID", line)  # Reject an unclassified element block.
                    element_type = type_match.group(1)  # Preserve normalized type.
                    element_elset = set_match.group(1)  # Preserve normalized set.
                elif upper.startswith("*EQUATION"):  # Select multiple-point equation records.
                    state = "equation_count"  # Expect the number of terms next.
                elif upper.startswith("*BOUNDARY"):  # Select single-point constraints.
                    state = "boundary"  # Mark boundary rows.
                continue  # Do not interpret a keyword as data.
            if state == "node":  # Parse one coordinate record.
                fields = [field.strip() for field in line.split(",")]  # Split the comma-separated node fields.
                require(len(fields) >= 4, "NODE_ROW_INVALID", line)  # Require label plus three coordinates.
                coordinates[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Store the exact coordinate triple.
            elif state == "element":  # Parse one two-node user element or one-node mass connectivity record.
                fields = [field.strip() for field in line.split(")" if False else ",")]  # Split connectivity while keeping every source line explicitly commented.
                node_ids = [int(field) for field in fields[1:] if field]  # Exclude the element label and parse attached nodes.
                label = topology_label(element_type, element_elset)  # Map the exact set to a physical family.
                for node_id in node_ids:  # Attach the family to every incident node.
                    incidence[node_id][label] += 1  # Count connectivity multiplicity for extrema interpretation.
            elif state == "equation_count":  # Parse the number of MPC terms.
                equation_terms_needed = int(line.split(",", 1)[0]) * 3  # Convert terms to the expected node-DOF-coefficient field count.
                equation_values = []  # Start a fresh possibly wrapped equation record.
                state = "equation_terms"  # Consume numeric term fields next.
            elif state == "equation_terms":  # Collect one possibly wrapped MPC record.
                equation_values.extend(field.strip() for field in line.split(",") if field.strip())  # Append every nonempty numeric field.
                if len(equation_values) >= equation_terms_needed:  # Finalize once all declared terms are present.
                    require(len(equation_values) == equation_terms_needed, "EQUATION_FIELD_COUNT_INVALID", repr((len(equation_values), equation_terms_needed)))  # Reject wrapped-row overrun.
                    term_nodes = [int(equation_values[index]) for index in range(0, equation_terms_needed, 3)]  # Extract node labels from each triplet.
                    dependent_nodes.add(term_nodes[0])  # CalculiX eliminates the first equation term.
                    master_nodes.update(term_nodes[1:])  # Preserve every remaining coupling node as a master-role participant.
                    state = "equation_count_or_keyword"  # Require the next record to be a new keyword in this generated deck.
            elif state == "equation_count_or_keyword":  # Reject unexpected data between generated equation cards.
                raise ClassificationError(f"EQUATION_CARD_SEQUENCE_INVALID: {line}")  # Fail closed rather than misclassifying topology.
            elif state == "boundary":  # Parse one single-point boundary row.
                boundary_nodes.add(int(line.split(",", 1)[0]))  # Record the constrained node label.
    require(len(coordinates) == 91415, "NODE_COUNT_MISMATCH", str(len(coordinates)))  # Bind the known dense C3 model cardinality.
    return coordinates, incidence, dependent_nodes, master_nodes, boundary_nodes  # Return all topology context required for mode classification.


def build_mirror_map(coordinates: dict[int, tuple[float, float, float]]) -> dict[int, int]:  # Pair transverse reflections while preserving coincident split-node multiplicity.
    groups: dict[tuple[float, float, float], dict[str, list[int]]] = defaultdict(lambda: {"negative": [], "positive": []})  # Group nodes by x, absolute y, and z at deck precision.
    for node_id, xyz in coordinates.items():  # Visit every solver node once.
        if xyz[1] == 0.0:  # Exclude centerline nodes without a distinct reflected partner.
            continue  # Advance to the next physical node.
        key = (round(xyz[0], 6), round(abs(xyz[1]), 6), round(xyz[2], 6))  # Collapse only the sign of the transverse coordinate.
        side = "negative" if xyz[1] < 0.0 else "positive"  # Preserve the physical side.
        groups[key][side].append(node_id)  # Retain coincident-node multiplicity explicitly.
    mirror_partner: dict[int, int] = {}  # Build a reciprocal one-to-one node mapping.
    unequal_groups = 0  # Count unmatched coordinate groups for bounded evidence.
    for sides in groups.values():  # Resolve each geometric reflection group independently.
        negative = sorted(sides["negative"])  # Make coincident-node pairing deterministic by solver label.
        positive = sorted(sides["positive"])  # Make the reflected side pairing deterministic by solver label.
        if len(negative) != len(positive):  # Exclude ambiguous asymmetric multiplicity rather than guessing.
            unequal_groups += 1  # Record the excluded coordinate group.
            continue  # Do not form a partial pair.
        for negative_node, positive_node in zip(negative, positive):  # Pair equal-multiplicity reflections one-to-one.
            mirror_partner[negative_node] = positive_node  # Map negative to positive.
            mirror_partner[positive_node] = negative_node  # Map positive back to negative.
    require(len(mirror_partner) > 40000 and unequal_groups < 2000, "MIRROR_GROUP_CLOSURE_FAILED", repr((len(mirror_partner), unequal_groups)))  # Require broad symmetric coverage and bounded exceptions.
    require(all(mirror_partner.get(partner) == node_id for node_id, partner in mirror_partner.items()), "MIRROR_RECIPROCITY_FAILED", str(len(mirror_partner)))  # Require exact reciprocal closure.
    return mirror_partner  # Return the deterministic geometric-pair map.


def parse_frequencies() -> dict[int, float]:  # Recover solver-order frequencies from the exact DAT table.
    frequencies: dict[int, float] = {}  # Map each requested mode to cycles per model time.
    in_table = False  # Track the eigenvalue table body.
    for raw in DAT.read_text(encoding="utf-8").splitlines():  # Read the compact DAT file exactly once.
        if len(frequencies) == 14:  # Close immediately after the declared fourteen roots.
            break  # Do not admit later effective-mass numeric records.
        if "MODE NO" in raw and "EIGENVALUE" in raw:  # Detect the eigenvalue table header.
            in_table = True  # Admit subsequent numeric rows.
            continue  # Skip the header itself.
        if in_table and raw.strip() and raw.lstrip()[0].isdigit():  # Parse one numeric eigenvalue row.
            fields = raw.split()  # Split the whitespace-delimited result columns.
            require(len(fields) >= 5, "DAT_EIGEN_ROW_INVALID", raw)  # Require mode, eigenvalue, omega, frequency, and imaginary omega.
            frequencies[int(fields[0])] = float(fields[3])  # Preserve cycles per time exactly as reported.
        elif in_table and frequencies and "PARTICIPATION" in raw:  # Close at the following result section.
            break  # Stop once all eigenvalue rows have been consumed.
    require(sorted(frequencies) == list(range(1, 15)), "DAT_MODE_COUNT_MISMATCH", repr(sorted(frequencies)))  # Require all fourteen solver-order roots.
    return frequencies  # Return the immutable mode-frequency map.


def parse_modes(coordinates: dict[int, tuple[float, float, float]], mirror_partner: dict[int, int]) -> dict[int, dict[str, object]]:  # Stream displacement fields and compute topology-neutral shape metrics.
    modes: dict[int, dict[str, object]] = {}  # Store finalized metrics by solver mode number.
    current_mode = 0  # Track the active FRD mode block.
    in_displacement = False  # Track the displacement result body.
    heap: list[tuple[float, int, tuple[float, float, float, float, float, float]]] = []  # Retain current top-amplitude nodes.
    component_squares = [0.0] * 6  # Accumulate unweighted nodal component squares.
    translation_square = 0.0  # Accumulate total translational amplitude square.
    weighted_coordinate = [0.0, 0.0, 0.0]  # Accumulate amplitude-square coordinate centroid numerators.
    side_square = {"left_y_negative": 0.0, "right_y_positive": 0.0}  # Split translation content by the two catwalk planes.
    seen_vectors: dict[int, tuple[float, float, float, float, float, float]] = {}  # Retain paired-node vectors only until their mirror is visited.
    mirror_cross = [0.0, 0.0, 0.0]  # Accumulate component-wise left-right signed products.
    mirror_square_a = [0.0, 0.0, 0.0]  # Accumulate the first side component squares.
    mirror_square_b = [0.0, 0.0, 0.0]  # Accumulate the mirrored side component squares.
    mirror_common_square = [0.0, 0.0, 0.0]  # Accumulate squared common-motion coordinates.
    mirror_differential_square = [0.0, 0.0, 0.0]  # Accumulate squared differential-motion coordinates.
    mirror_pairs_seen = 0  # Count unique geometric mirror pairs contributing to correlations.

    def reset_mode() -> None:  # Reset all streaming accumulators for a new mode.
        nonlocal heap, component_squares, translation_square, weighted_coordinate, side_square, seen_vectors, mirror_cross, mirror_square_a, mirror_square_b, mirror_common_square, mirror_differential_square, mirror_pairs_seen  # Rebind the enclosing mode accumulators.
        heap = []  # Clear extrema.
        component_squares = [0.0] * 6  # Clear component energy proxies.
        translation_square = 0.0  # Clear the translation norm proxy.
        weighted_coordinate = [0.0, 0.0, 0.0]  # Clear centroid numerators.
        side_square = {"left_y_negative": 0.0, "right_y_positive": 0.0}  # Clear side totals.
        seen_vectors = {}  # Clear unpaired displacement vectors.
        mirror_cross = [0.0, 0.0, 0.0]  # Clear signed pair products.
        mirror_square_a = [0.0, 0.0, 0.0]  # Clear first-side component squares.
        mirror_square_b = [0.0, 0.0, 0.0]  # Clear second-side component squares.
        mirror_common_square = [0.0, 0.0, 0.0]  # Clear common-motion squares.
        mirror_differential_square = [0.0, 0.0, 0.0]  # Clear differential-motion squares.
        mirror_pairs_seen = 0  # Clear the unique mirror-pair count.

    def finalize_mode() -> None:  # Freeze one completed displacement block.
        if current_mode == 0:  # Ignore the preamble before the first mode.
            return  # Nothing is available to finalize.
        require(translation_square > 0.0 and len(heap) == TOP_COUNT, "MODE_FIELD_EMPTY", str(current_mode))  # Require a populated physical displacement field.
        centroid = [value / translation_square for value in weighted_coordinate]  # Compute amplitude-square spatial centroid.
        total_six = sum(component_squares)  # Normalize all six displacement components consistently.
        top_nodes = [{"node": node_id, "translation_norm": amplitude, "u": list(vector[:3]), "r": list(vector[3:]), "xyz_mm": list(coordinates[node_id])} for amplitude, node_id, vector in sorted(heap, reverse=True)]  # Preserve ordered extrema with exact vectors and coordinates.
        mirror_correlation = [mirror_cross[index] / math.sqrt(mirror_square_a[index] * mirror_square_b[index]) if mirror_square_a[index] > 0.0 and mirror_square_b[index] > 0.0 else 0.0 for index in range(3)]  # Normalize signed left-right correlation for UX, UY, and UZ.
        mirror_common_fraction = [mirror_common_square[index] / (mirror_common_square[index] + mirror_differential_square[index]) if mirror_common_square[index] + mirror_differential_square[index] > 0.0 else 0.0 for index in range(3)]  # Report common versus differential pair motion per component.
        modes[current_mode] = {"translation_l2": math.sqrt(translation_square), "component_square_fractions": [value / total_six for value in component_squares], "translation_component_fractions": [component_squares[index] / translation_square for index in range(3)], "translation_weighted_centroid_mm": centroid, "side_translation_square_fractions": {key: value / translation_square for key, value in side_square.items()}, "mirror_pairs": mirror_pairs_seen, "mirror_component_correlation": mirror_correlation, "mirror_common_fraction": mirror_common_fraction, "top_nodes": top_nodes}  # Store compact topology-neutral metrics.

    with FRD.open("r", encoding="utf-8", errors="strict") as handle:  # Stream the 250 MiB-class result without loading it into memory.
        for raw in handle:  # Visit every FRD record in exact order.
            stripped = raw.strip()  # Normalize surrounding whitespace for record tags.
            if stripped.startswith("1PMODE"):  # Enter a new modal result frame.
                if in_displacement:  # Close any preceding displacement frame before advancing.
                    finalize_mode()  # Freeze its accumulated metrics.
                current_mode = int(stripped.split()[-1])  # Parse the solver mode number.
                reset_mode()  # Start fresh accumulators.
                in_displacement = False  # Wait for the DISP result tag.
            elif stripped.startswith("-4") and "DISP" in stripped:  # Enter the six-component nodal displacement records.
                in_displacement = True  # Admit subsequent -1 rows.
            elif in_displacement and stripped.startswith("-1"):  # Parse one nodal displacement row.
                head = re.match(r"\s*-1\s+(\d+)(.*)$", raw)  # Separate the node label from adjacent exponent fields.
                require(head is not None, "FRD_NODE_ROW_INVALID", raw[:80])  # Reject a malformed displacement row.
                node_id = int(head.group(1))  # Parse the solver node label.
                values = tuple(float(value) for value in FLOAT_PATTERN.findall(head.group(2)))  # Parse all six fixed-format displacement components.
                require(len(values) == 6, "FRD_COMPONENT_COUNT_INVALID", repr((current_mode, node_id, values)))  # Require the complete six-component field.
                amplitude_square = values[0] * values[0] + values[1] * values[1] + values[2] * values[2]  # Compute translational amplitude square.
                amplitude = math.sqrt(amplitude_square)  # Compute the ranking norm.
                for index, value in enumerate(values):  # Accumulate every component consistently.
                    component_squares[index] += value * value  # Add this nodal component square.
                translation_square += amplitude_square  # Accumulate the global translation norm proxy.
                xyz = coordinates[node_id]  # Resolve the exact model coordinate.
                for index in range(3):  # Accumulate spatial centroid components.
                    weighted_coordinate[index] += amplitude_square * xyz[index]  # Weight position by translational amplitude square.
                side_key = "left_y_negative" if xyz[1] < 0.0 else "right_y_positive"  # Assign the node to its physical catwalk side by transverse coordinate.
                side_square[side_key] += amplitude_square  # Accumulate this side's displacement content.
                partner = mirror_partner.get(node_id)  # Resolve an exact geometric mirror node when present.
                if partner is not None and partner in seen_vectors:  # Complete one unique mirror pair when its counterpart was already visited.
                    partner_values = seen_vectors.pop(partner)  # Remove the stored counterpart so the pair contributes exactly once.
                    mirror_pairs_seen += 1  # Count this completed geometric pair.
                    for index in range(3):  # Accumulate UX, UY, and UZ pair metrics independently.
                        mirror_cross[index] += values[index] * partner_values[index]  # Preserve signed common or differential phase.
                        mirror_square_a[index] += values[index] * values[index]  # Accumulate this side's component square.
                        mirror_square_b[index] += partner_values[index] * partner_values[index]  # Accumulate its counterpart square.
                        mirror_common_square[index] += (values[index] + partner_values[index]) ** 2  # Accumulate common-motion content.
                        mirror_differential_square[index] += (values[index] - partner_values[index]) ** 2  # Accumulate differential-motion content.
                elif partner is not None:  # Retain this vector until its mirror is encountered.
                    seen_vectors[node_id] = values  # Store only nodes participating in an exact geometric pair.
                record = (amplitude, node_id, values)  # Package the node for bounded extrema retention.
                if len(heap) < TOP_COUNT:  # Fill the initial extrema heap.
                    heapq.heappush(heap, record)  # Retain the candidate.
                elif record[0] > heap[0][0]:  # Replace only when this node exceeds the smallest retained amplitude.
                    heapq.heapreplace(heap, record)  # Keep the heap bounded at TOP_COUNT.
            elif in_displacement and stripped.startswith("-3"):  # Close the current DISP result body.
                finalize_mode()  # Freeze the completed mode immediately.
                in_displacement = False  # Reject subsequent non-DISP result rows.
    require(sorted(modes) == list(range(1, 15)), "FRD_MODE_COUNT_MISMATCH", repr(sorted(modes)))  # Require all fourteen completed mode fields.
    return modes  # Return the topology-neutral modal metrics.


def main() -> None:  # Classify the true lowest fourteen roots before the strict target comparison.
    require(DECK.is_file() and DAT.is_file() and FRD.is_file(), "INPUT_RESULT_MISSING", repr((DECK, DAT, FRD)))  # Require every exact source artifact.
    require(sha256_file(DECK) == EXPECTED_DECK_SHA256, "DECK_SHA256_MISMATCH", sha256_file(DECK))  # Reject model drift.
    coordinates, incidence, dependent_nodes, master_nodes, boundary_nodes = parse_deck()  # Recover physical topology context.
    mirror_partner = build_mirror_map(coordinates)  # Pair exact transverse reflections without nearest-neighbor inference.
    frequencies = parse_frequencies()  # Recover solver-order root frequencies.
    modes = parse_modes(coordinates, mirror_partner)  # Compute shape metrics from exact nodal results.
    rows: list[dict[str, object]] = []  # Build the compact engineering table.
    for mode_number in range(1, 15):  # Preserve native solver order without rematching.
        mode = modes[mode_number]  # Select this exact root.
        top = mode["top_nodes"][0]  # Select its maximum translational node.
        node_id = int(top["node"])  # Resolve the maximum node label.
        labels = dict(sorted(incidence.get(node_id, Counter()).items()))  # Preserve every incident physical family.
        topology_role = "dependent_mpc" if node_id in dependent_nodes else "master_mpc" if node_id in master_nodes else "free_independent"  # Classify its equation role.
        if node_id in boundary_nodes:  # Preserve any boundary overlap explicitly.
            topology_role += "+boundary"  # Append the single-point-constraint role.
        fractions = mode["translation_component_fractions"]  # Select normalized UX, UY, and UZ content.
        dominant = ("UX", "UY", "UZ")[max(range(3), key=lambda index: fractions[index])]  # Identify the dominant translational component.
        row = {"mode": mode_number, "frequency_hz": frequencies[mode_number], "dominant_translation": dominant, "ux_fraction": fractions[0], "uy_fraction": fractions[1], "uz_fraction": fractions[2], "ux_mirror_correlation": mode["mirror_component_correlation"][0], "uy_mirror_correlation": mode["mirror_component_correlation"][1], "uz_mirror_correlation": mode["mirror_component_correlation"][2], "uz_common_fraction": mode["mirror_common_fraction"][2], "left_fraction": mode["side_translation_square_fractions"]["left_y_negative"], "right_fraction": mode["side_translation_square_fractions"]["right_y_positive"], "max_node": node_id, "max_node_x_mm": top["xyz_mm"][0], "max_node_y_mm": top["xyz_mm"][1], "max_node_z_mm": top["xyz_mm"][2], "max_node_role": topology_role, "max_node_incidence": ";".join(f"{key}:{value}" for key, value in labels.items())}  # Record one fixed-order classification row.
        rows.append(row)  # Preserve native mode order.
        mode["maximum_node_context"] = {"role": topology_role, "incidence": labels}  # Enrich the detailed report.
        for top_node in mode["top_nodes"]:  # Add topology context to every retained extremum.
            top_id = int(top_node["node"])  # Resolve this extremum label.
            top_node["mpc_role"] = "dependent_mpc" if top_id in dependent_nodes else "master_mpc" if top_id in master_nodes else "free_independent"  # Classify its equation role.
            top_node["incidence"] = dict(sorted(incidence.get(top_id, Counter()).items()))  # Attach incident physical families.
    csv_buffer_lines: list[str] = []  # Build CSV text through the standard writer without a temporary file.
    import io  # Import the in-memory text stream locally to keep the module surface minimal.
    csv_buffer = io.StringIO()  # Allocate a deterministic newline-controlled text buffer.
    writer = csv.DictWriter(csv_buffer, fieldnames=list(rows[0]))  # Freeze column order from the explicit row schema.
    writer.writeheader()  # Emit the engineering table header.
    writer.writerows(rows)  # Emit all fourteen roots in native order.
    csv_bytes = csv_buffer.getvalue().encode("utf-8")  # Freeze exact CSV bytes.
    csv_sha256 = hashlib.sha256(csv_bytes).hexdigest()  # Bind the compact table identity.
    csv_path = ARTIFACTS / f"C3-UB-FT14-PARSER-SAFE_mode_classification_{csv_sha256[:16]}.csv"  # Address the table by content.
    require(not csv_path.exists(), "CSV_OUTPUT_COLLISION", str(csv_path))  # Preserve immutable earlier evidence.
    csv_path.write_bytes(csv_bytes)  # Publish the compact table after all fourteen modes pass.
    source_audit = audit_comments(Path(__file__).resolve())  # Bind the user-required source-comment audit.
    report = {"schema": "catwalk.c3-ub-ft14-parser-safe.mode-classification.v1", "status": "TRUE_LOWEST_FOURTEEN_CLASSIFIED", "target_access": "STRICT_FIXED_ORDER_AFTER_SOLVE", "claims": {"production": False, "frequency_reproduced": False, "equilibrium_validated": False}, "inputs": {"deck": {"path": str(DECK.relative_to(BASE)), "sha256": sha256_file(DECK)}, "dat": {"path": str(DAT.relative_to(BASE)), "sha256": sha256_file(DAT)}, "frd": {"path": str(FRD.relative_to(BASE)), "sha256": sha256_file(FRD)}}, "topology": {"nodes": len(coordinates), "dependent_mpc_nodes": len(dependent_nodes), "master_mpc_nodes": len(master_nodes), "boundary_nodes": len(boundary_nodes), "exact_mirror_node_entries": len(mirror_partner)}, "modes": {str(key): value for key, value in modes.items()}, "table": {"path": str(csv_path.relative_to(BASE)), "sha256": csv_sha256}, "source": source_audit}  # Publish detailed mode evidence for the solved physical C3 state.
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")  # Serialize deterministic readable evidence.
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()  # Bind every exact report byte.
    report_path = ARTIFACTS / f"C3-UB-FT14-PARSER-SAFE_mode_classification_{report_sha256[:16]}.json"  # Address detailed evidence by content.
    require(not report_path.exists(), "JSON_OUTPUT_COLLISION", str(report_path))  # Preserve immutable earlier evidence.
    report_path.write_bytes(report_bytes)  # Publish only after all classification checks pass.
    print(json.dumps({"event": "C3UB_FT14_PARSER_SAFE_MODES_CLASSIFIED", "csv": str(csv_path.relative_to(BASE)), "csv_sha256": csv_sha256, "report": str(report_path.relative_to(BASE)), "report_sha256": report_sha256, "frequency_min_hz": frequencies[1], "frequency_max_hz": frequencies[14], "target_access": "STRICT_FIXED_ORDER_AFTER_SOLVE"}, sort_keys=True), flush=True)  # Emit concise handoff facts.


if __name__ == "__main__":  # Execute only when invoked as the fourteen-mode classifier.
    main()  # Classify exact solver results and publish immutable evidence.
