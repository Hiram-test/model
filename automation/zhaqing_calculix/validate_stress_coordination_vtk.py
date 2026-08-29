#!/usr/bin/env python3  # Validate the canonical Zhaqing stress VTK independently from the calculation writer.
from __future__ import annotations  # Keep modern type annotations available on the pinned Python runner.

import argparse  # Parse explicit immutable evidence paths for command-line validation.
import hashlib  # Recompute every evidence digest instead of trusting producer receipts.
import json  # Read strict machine receipts and write the independent validation receipt.
import math  # Reject non-finite values and recompute stress invariants independently.
import re  # Parse the frozen CalculiX input, DAT tables, and legacy VTK declarations strictly.
import sys  # Emit a fail-closed process status and concise diagnostics for Actions.
from pathlib import Path  # Resolve every evidence file without directory guessing.
from typing import Any  # Describe strict JSON values without importing third-party packages.


FROZEN_BASELINE_SHA256 = "1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d"  # Bind production validation to the immutable verified LC01 deck.
BASELINE_POINT_COUNT = 791  # Require every frozen source node while independently deriving the primary-response subset.
BASELINE_CELL_COUNT = 1078  # Require every frozen non-MASS structural element before explicit wind exclusion.
EXPECTED_POINT_COUNT = 783  # Require every and only primary-response source node after wind-only nodes are excluded.
EXPECTED_CELL_COUNT = 1070  # Require every and only primary-response structural element after both wind groups are excluded.
EXPECTED_CONNECTIVITY_INTEGER_COUNT = 4194  # Require the exact legacy CELLS integer count for 492 quads and 578 primary lines.
EXPECTED_VTK_LINE_COUNT = 13359  # Require the deterministic primary-response ASCII serialization without wind cells or nodes.
EXPECTED_INTEGRATION_POINT_IDS = frozenset(range(1, 9))  # Require all eight CalculiX stress records for every structural element.
GROUP_ORDER = (  # Freeze the exact primary-response engineering component order used by write_legacy_vtk.
    "DECK_SHELLS",  # Map the S4 deck shell cells first.
    "CROSSBEAMS",  # Map the transverse B31 deck members second.
    "LONG_GIRDERS",  # Map the longitudinal B31 deck members third.
    "TOWER_COLUMNS",  # Map the four tower-column members fourth.
    "TOWER_TOP_BEAMS",  # Map the two tower-top beams fifth.
    "MAIN_CABLES",  # Map the main-cable elements sixth.
    "HANGERS",  # Map the hanger elements seventh.
)  # Finish the immutable seven-group primary VTK component-order contract.
EXCLUDED_WIND_GROUP_ORDER = ("WIND_ATTACH_LINKS", "WIND_CABLES")  # Freeze the two source groups blocked from primary response by unresolved G3/G5 evidence.
SOURCE_GROUP_ORDER = GROUP_ORDER + EXCLUDED_WIND_GROUP_ORDER  # Parse all nine source groups independently before primary-response exclusion.
EXPECTED_WIND_ONLY_NODE_IDS = set(range(784, 792))  # Require exclusion of the eight baseline nodes used only by the wind subsystem.
EXPECTED_WIND_BLOCKER_ISSUE_IDS = {"C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001", "U-WIND-001"}  # Bind exclusion to the exact unresolved source issues.
EXPECTED_GROUP_COUNTS = {  # Freeze the independently verified structural element counts by source ELSET.
    "DECK_SHELLS": 492,  # Preserve all verified S4 deck cells.
    "CROSSBEAMS": 162,  # Preserve all verified crossbeam elements.
    "LONG_GIRDERS": 164,  # Preserve all verified longitudinal-girder elements.
    "TOWER_COLUMNS": 4,  # Preserve all verified tower-column elements.
    "TOWER_TOP_BEAMS": 2,  # Preserve both verified tower-top beams.
    "MAIN_CABLES": 196,  # Preserve all verified main-cable elements.
    "HANGERS": 50,  # Preserve all verified hanger elements.
    "WIND_ATTACH_LINKS": 4,  # Derive all four excluded wind attachment links from the frozen source.
    "WIND_CABLES": 4,  # Derive all four excluded wind-cable elements from the frozen source.
}  # Finish the exact component-count contract.
EXPECTED_GROUP_TYPES = {  # Freeze the source element family required for every exported component.
    "DECK_SHELLS": "S4",  # Require four-node shell topology for the deck.
    "CROSSBEAMS": "B31",  # Require beam topology for crossbeams.
    "LONG_GIRDERS": "B31",  # Require beam topology for longitudinal girders.
    "TOWER_COLUMNS": "B31",  # Require beam topology for tower columns.
    "TOWER_TOP_BEAMS": "B31",  # Require beam topology for tower-top beams.
    "MAIN_CABLES": "B31",  # Preserve the frozen baseline main-cable source representation.
    "HANGERS": "T3D2",  # Require axial two-node hanger topology.
    "WIND_ATTACH_LINKS": "B31",  # Require the expected source topology before excluding wind attachment links.
    "WIND_CABLES": "T3D2",  # Require the expected source topology before excluding wind cables.
}  # Finish the source element-family contract.
SCALAR_FIELD_ORDER = (  # Freeze every required cell scalar in exact writer order.
    "von_mises_mpa",  # Require the independently recomputable J2 stress magnitude.
    "axial_stress_mpa",  # Require the independently projected line-element axial stress.
    "equilibrium_target_axial_stress_mpa",  # Require the P2 suspension target field.
    "stress_coordination_ratio",  # Require the final-to-target suspension stress ratio.
    "component_id",  # Require the stable engineering component code.
    "source_element_id",  # Require the original CalculiX element label.
)  # Finish the exact scalar-field order.
NUMBER_TOKEN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?\Z")  # Accept finite decimal/scientific tokens while excluding NaN and infinity.
NODE_RESULT_ROW = re.compile(r"^\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s*$")  # Recognize one strict CalculiX nodal vector record.


class ValidationError(RuntimeError):  # Represent every deterministic contract violation with one fail-closed exception type.
    pass  # Carry the precise validation message without adding recovery behavior.


def require(condition: bool, message: str) -> None:  # Convert every failed invariant into the same fail-closed exception.
    if not condition:  # Reject the current artifact immediately when an invariant is false.
        raise ValidationError(message)  # Preserve the exact rejected condition for the receipt and workflow log.


def sha256_path(path: Path) -> str:  # Hash one evidence file without text normalization.
    require(path.is_file(), f"required evidence file is missing: {path}")  # Reject missing directories, symlinks to directories, and absent files.
    digest = hashlib.sha256()  # Initialize the independent SHA-256 computation.
    with path.open("rb") as stream:  # Read exact bytes from the evidence path.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Bound memory while consuming the complete file.
            digest.update(chunk)  # Extend the digest with the next exact byte block.
    return digest.hexdigest()  # Return the canonical lowercase hexadecimal digest.


def reject_json_constant(token: str) -> Any:  # Reject non-standard JSON NaN and Infinity constants explicitly.
    raise ValidationError(f"non-finite JSON constant is forbidden: {token}")  # Fail before a non-finite receipt value can influence a Gate.


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:  # Reject ambiguous duplicate keys in every parsed JSON object.
    result: dict[str, Any] = {}  # Accumulate one unambiguous mapping from the ordered key pairs.
    for key, value in pairs:  # Inspect every serialized key exactly once.
        require(key not in result, f"duplicate JSON key is forbidden: {key}")  # Prevent last-key-wins receipt spoofing.
        result[key] = value  # Preserve the unique key and its parsed value.
    return result  # Return the strictly unique JSON object.


def load_strict_json(path: Path) -> dict[str, Any]:  # Load one UTF-8 JSON evidence file with duplicate and non-finite rejection.
    require(path.is_file(), f"required JSON evidence is missing: {path}")  # Stop before attempting to parse absent evidence.
    try:  # Convert decoding or syntax failures into the common validation error.
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys, parse_constant=reject_json_constant)  # Parse strict JSON in one standard-library pass.
    except ValidationError:  # Preserve deliberate contract failures without wrapping away their detail.
        raise  # Re-raise the original fail-closed validation error.
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:  # Catch invalid UTF-8 and malformed JSON syntax.
        raise ValidationError(f"invalid JSON evidence {path}: {exc}") from exc  # Report the precise evidence path and parser failure.
    require(isinstance(value, dict), f"top-level JSON evidence must be an object: {path}")  # Require a keyed machine receipt rather than a scalar or list.
    return value  # Return the strictly parsed object for semantic validation.


def finite_float(value: Any, label: str) -> float:  # Convert one JSON or text scalar to a finite floating-point value.
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be numeric")  # Reject strings and booleans masquerading as quantities.
    converted = float(value)  # Normalize accepted integer and floating-point quantities.
    require(math.isfinite(converted), f"{label} must be finite")  # Reject NaN and both infinities before arithmetic.
    return converted  # Return the validated finite number.


def parse_text_float(token: str, label: str) -> float:  # Parse one finite decimal token from DAT or VTK text.
    require(NUMBER_TOKEN.fullmatch(token) is not None, f"{label} contains an invalid numeric token: {token}")  # Reject malformed and non-finite spellings.
    value = float(token)  # Convert the validated decimal grammar to a Python float.
    require(math.isfinite(value), f"{label} contains a non-finite value")  # Reject overflow to infinity after conversion.
    return value  # Return the finite parsed value.


def parse_vtk_float_row(line: str, count: int, label: str) -> tuple[list[str], tuple[float, ...]]:  # Parse one exact-width legacy VTK numeric row.
    tokens = line.split()  # Split canonical space-separated ASCII values.
    require(len(tokens) == count, f"{label} must contain exactly {count} values")  # Reject truncation and surplus numeric payload.
    values = tuple(parse_text_float(token, label) for token in tokens)  # Parse and finite-check every declared value.
    return tokens, values  # Preserve both original spellings and numeric values for canonical comparison.


def canonical_number(value: float) -> str:  # Reproduce the exact twelve-significant-digit writer representation.
    require(math.isfinite(value), "cannot serialize a non-finite expected VTK value")  # Prevent expected-data defects from weakening validation.
    return f"{value:.12g}"  # Match write_legacy_vtk numeric formatting exactly.


def require_canonical_values(tokens: list[str], expected: tuple[float, ...] | list[float], label: str, exact: bool = False) -> None:  # Compare one parsed VTK row to independently reconstructed expected values.
    actual_values = [parse_text_float(token, label) for token in tokens]  # Recover finite numeric values from the already width-checked row.
    require(tokens == [canonical_number(value) for value in actual_values], f"{label} uses noncanonical numeric serialization")  # Require the writer's exact twelve-significant-digit spelling.
    if exact:  # Apply byte-level equality to discrete ids that cannot carry rounding uncertainty.
        expected_tokens = [canonical_number(float(value)) for value in expected]  # Serialize the independent discrete values through the frozen writer format.
        require(tokens == expected_tokens, f"{label} mismatch: expected {expected_tokens}, got {tokens}")  # Reject any altered component or source id.
        return  # Finish the exact discrete comparison without applying floating tolerance.
    require(len(actual_values) == len(expected), f"{label} expected-value width mismatch")  # Defend aligned component-wise comparison.
    for index, (actual, reference) in enumerate(zip(actual_values, expected)):  # Compare every physical scalar within serialization-level tolerance.
        require(math.isclose(actual, float(reference), rel_tol=1.0e-11, abs_tol=1.0e-8), f"{label} value {index} mismatch: expected {reference}, got {actual}")  # Allow only negligible chained .12g round-trip error.


def parse_keyword_parameter(line: str, name: str) -> str | None:  # Extract one comma-delimited Abaqus keyword parameter case-insensitively.
    match = re.search(rf"(?:^|,)\s*{re.escape(name)}\s*=\s*([^,\s]+)", line, re.IGNORECASE)  # Locate the requested key without accepting partial names.
    return match.group(1).upper() if match else None  # Normalize an observed value or report its absence explicitly.


def parse_baseline(path: Path, expected_sha256: str) -> tuple[dict[int, tuple[float, float, float]], dict[str, list[tuple[int, list[int]]]]]:  # Independently recover the frozen source topology from LC01.
    actual_sha256 = sha256_path(path)  # Bind all derived expectations to the exact baseline bytes.
    require(actual_sha256 == expected_sha256, f"baseline SHA256 mismatch: {actual_sha256}")  # Reject any floating or substituted mother deck.
    try:  # Require the verified portable ASCII input encoding.
        lines = path.read_text(encoding="ascii").splitlines()  # Read the complete baseline without replacement characters.
    except UnicodeDecodeError as exc:  # Convert a non-ASCII input into the common validation failure.
        raise ValidationError(f"baseline input is not ASCII: {path}") from exc  # Preserve the frozen input-format contract.
    nodes: dict[int, tuple[float, float, float]] = {}  # Accumulate every source node and coordinate.
    groups: dict[str, list[tuple[int, list[int]]]] = {name: [] for name in SOURCE_GROUP_ORDER}  # Accumulate all nine source groups before explicit primary-response exclusion.
    group_types: dict[str, str] = {}  # Preserve each source ELSET element family for topology validation.
    in_nodes = False  # Track whether the scanner is inside the model NODE block.
    active_group: str | None = None  # Track the current exported ELEMENT block.
    for raw in lines:  # Scan the frozen input exactly once in source order.
        line = raw.strip()  # Normalize surrounding whitespace only for keyword recognition.
        upper = line.upper()  # Cache uppercase text for deterministic case-insensitive matching.
        if re.match(r"^\*NODE(?:,|\s|$)", line, re.IGNORECASE) and not re.match(r"^\*NODE\s+(PRINT|FILE)", line, re.IGNORECASE):  # Detect the source node definition rather than an output request.
            in_nodes = True  # Enter node-record parsing mode.
            active_group = None  # Leave any preceding element block.
            continue  # Advance to the first node record.
        if upper.startswith("*ELEMENT"):  # Detect a source finite-element block.
            in_nodes = False  # Leave node-record parsing mode.
            group_name = parse_keyword_parameter(line, "ELSET")  # Recover the source engineering component name.
            element_type = parse_keyword_parameter(line, "TYPE")  # Recover the source element formulation.
            active_group = group_name if group_name in groups else None  # Parse only cells included by the VTK contract.
            if active_group is not None:  # Validate the exported block before accepting connectivity.
                require(active_group not in group_types, f"duplicate exported ELEMENT block: {active_group}")  # Reject split or ambiguous ownership in the fixed source contract.
                require(element_type is not None, f"missing TYPE for exported ELEMENT block: {active_group}")  # Require an explicit source element family.
                group_types[active_group] = element_type  # Preserve the unique exported element family.
            continue  # Advance to element connectivity rows.
        if line.startswith("*"):  # Detect any other keyword boundary.
            in_nodes = False  # Leave node-record parsing mode.
            active_group = None  # Leave exported element parsing mode.
            continue  # Advance under the unrelated keyword.
        if not line or line.startswith("**"):  # Ignore empty records and comments outside numeric blocks.
            continue  # Preserve parser state while skipping non-data content.
        fields = [field.strip() for field in line.split(",") if field.strip()]  # Tokenize one comma-delimited source record.
        if in_nodes:  # Parse one source node record.
            require(len(fields) >= 4 and fields[0].isdigit(), f"malformed source node record: {raw}")  # Require node id plus three coordinates.
            node_id = int(fields[0])  # Recover the exact source node label.
            require(node_id not in nodes, f"duplicate source node id: {node_id}")  # Reject last-record-wins coordinate ambiguity.
            coordinates = tuple(parse_text_float(fields[index], f"node {node_id} coordinate") for index in range(1, 4))  # Parse all three finite source coordinates.
            nodes[node_id] = (coordinates[0], coordinates[1], coordinates[2])  # Store the complete coordinate tuple.
            continue  # Finish processing the current source node.
        if active_group is not None:  # Parse one exported structural connectivity record.
            require(fields and all(field.isdigit() for field in fields), f"malformed {active_group} connectivity record: {raw}")  # Require only positive integer labels.
            element_id = int(fields[0])  # Recover the exact source element label.
            connectivity = [int(field) for field in fields[1:]]  # Preserve source connectivity order without normalization.
            groups[active_group].append((element_id, connectivity))  # Append this cell in its original group order.
    require(sorted(nodes) == list(range(1, BASELINE_POINT_COUNT + 1)), "baseline node ids must be exactly 1..791")  # Freeze the complete source point set before wind exclusion.
    require(set(group_types) == set(SOURCE_GROUP_ORDER), "baseline is missing one or more structural source ELEMENT blocks")  # Require all primary and excluded wind groups exactly once.
    element_ids: list[int] = []  # Collect exported source element labels for uniqueness and coverage checks.
    connectivity_integer_count = 0  # Recompute the legacy VTK CELLS integer count independently.
    for group_name in SOURCE_GROUP_ORDER:  # Validate each source component against its fixed count and topology.
        require(group_types[group_name] == EXPECTED_GROUP_TYPES[group_name], f"unexpected source TYPE for {group_name}")  # Reject silent element-family changes.
        require(len(groups[group_name]) == EXPECTED_GROUP_COUNTS[group_name], f"unexpected element count for {group_name}")  # Reject missing or surplus structural cells.
        expected_connectivity_length = 4 if group_name == "DECK_SHELLS" else 2  # Apply quad topology only to deck shells and line topology elsewhere.
        for element_id, connectivity in groups[group_name]:  # Validate every exported structural element.
            require(len(connectivity) == expected_connectivity_length, f"unexpected connectivity width for element {element_id}")  # Reject malformed cell topology.
            require(len(set(connectivity)) == len(connectivity), f"element {element_id} repeats a node")  # Reject locally degenerate connectivity.
            require(all(node_id in nodes for node_id in connectivity), f"element {element_id} references an unknown node")  # Reject dangling point indices.
            element_ids.append(element_id)  # Preserve this source id for global coverage validation.
            connectivity_integer_count += len(connectivity) + 1  # Include the per-cell connectivity width token.
    require(len(element_ids) == BASELINE_CELL_COUNT, "baseline structural cell count mismatch")  # Require all 1078 source structural elements before exclusion.
    require(sorted(element_ids) == list(range(1, BASELINE_CELL_COUNT + 1)), "baseline structural element ids must be exactly 1..1078")  # Freeze the complete source element-id set.
    require(connectivity_integer_count == 4218, "baseline connectivity integer count mismatch")  # Require the exact complete-source CELLS payload before exclusion.
    return nodes, groups  # Return the independently verified source geometry and component topology.


def parse_wind_exclusion(path: Path, groups: dict[str, list[tuple[int, list[int]]]], primary_node_ids: set[int]) -> tuple[set[int], set[int], str]:  # Validate the explicit G3/G5 wind exclusion against frozen source topology.
    receipt = load_strict_json(path)  # Parse the exclusion receipt without duplicate or non-finite JSON values.
    receipt_sha256 = sha256_path(path)  # Bind the primary VTK validation receipt to exact exclusion evidence bytes.
    require(receipt.get("schema") == "zhaqing-wind-exclusion-v1", "wind exclusion schema mismatch")  # Require the agreed machine contract version.
    require(receipt.get("status") == "BLOCKED_G3_G5", "wind exclusion status must be BLOCKED_G3_G5")  # Prevent unresolved wind evidence from entering primary response.
    raw_groups = receipt.get("excludedGroups")  # Recover source element ids grouped by excluded engineering component.
    require(isinstance(raw_groups, dict) and set(raw_groups) == set(EXCLUDED_WIND_GROUP_ORDER), "wind exclusion must contain exactly both wind groups")  # Reject missing, surplus, or renamed groups.
    expected_by_group = {group_name: [element_id for element_id, _connectivity in groups[group_name]] for group_name in EXCLUDED_WIND_GROUP_ORDER}  # Derive exact excluded source ids from baseline order.
    for group_name in EXCLUDED_WIND_GROUP_ORDER:  # Validate both blocked source components independently.
        raw_ids = raw_groups[group_name]  # Recover this component's declared excluded ids.
        require(isinstance(raw_ids, list) and all(isinstance(value, int) and not isinstance(value, bool) for value in raw_ids), f"wind exclusion ids for {group_name} must be integers")  # Reject strings, booleans, and malformed ids.
        require(raw_ids == expected_by_group[group_name], f"wind exclusion ids mismatch for {group_name}")  # Require exact source ordering and coverage.
    excluded_element_ids = {element_id for group_name in EXCLUDED_WIND_GROUP_ORDER for element_id, _connectivity in groups[group_name]}  # Derive the complete eight-element excluded set.
    raw_element_ids = receipt.get("excludedElementIds")  # Recover the receipt's flattened excluded source ids.
    require(isinstance(raw_element_ids, list) and len(raw_element_ids) == len(set(raw_element_ids)), "excludedElementIds must be a unique list")  # Reject duplicates that could hide an omitted element.
    require(raw_element_ids == sorted(excluded_element_ids), "excludedElementIds must exactly match the eight baseline wind elements")  # Require exact complete flattened coverage.
    excluded_group_nodes = {node_id for group_name in EXCLUDED_WIND_GROUP_ORDER for _element_id, connectivity in groups[group_name] for node_id in connectivity}  # Recover every source node touched by wind elements.
    wind_only_node_ids = excluded_group_nodes - primary_node_ids  # Derive nodes owned only by the excluded wind subsystem.
    require(wind_only_node_ids == EXPECTED_WIND_ONLY_NODE_IDS, "baseline-derived wind-only nodes must be exactly 784..791")  # Freeze the expected source partition.
    raw_node_ids = receipt.get("windOnlyNodeIds")  # Recover the receipt's excluded point labels.
    require(isinstance(raw_node_ids, list) and raw_node_ids == sorted(wind_only_node_ids), "windOnlyNodeIds must be exactly 784..791")  # Require exact ordered point exclusion.
    raw_blockers = receipt.get("blockerIssueIds")  # Recover the unresolved evidence issues justifying exclusion.
    require(isinstance(raw_blockers, list) and len(raw_blockers) == len(set(raw_blockers)), "blockerIssueIds must be a unique list")  # Reject duplicated or ambiguous issue references.
    require(set(raw_blockers) == EXPECTED_WIND_BLOCKER_ISSUE_IDS, "wind exclusion blockerIssueIds mismatch")  # Require all and only the three agreed G3/G5 blockers.
    return excluded_element_ids, wind_only_node_ids, receipt_sha256  # Return independently verified exclusion sets and evidence identity.


def parse_equilibrium(path: Path, baseline_sha256: str, nodes: dict[int, tuple[float, float, float]], suspension_ids: set[int]) -> tuple[dict[int, tuple[float, float, float]], dict[int, float], str]:  # Validate the P2 coordinate and target-stress state used by the writer.
    equilibrium = load_strict_json(path)  # Parse the state without duplicate or non-finite JSON values.
    equilibrium_sha256 = sha256_path(path)  # Bind every reconstructed VTK expectation to the exact state bytes.
    require(equilibrium.get("schema") == "zhaqing-equilibrium-state-v3", "equilibrium_state schema must be zhaqing-equilibrium-state-v3")  # Prevent a legacy main-span-only state from satisfying the complete-system output contract.
    require(equilibrium.get("status") == "PASS", "equilibrium_state status must be PASS")  # Reject a visualization based on a failed P1/P2 state.
    require(equilibrium.get("sourceBaselineSha256") == baseline_sha256, "equilibrium_state baseline digest mismatch")  # Prevent state transfer across mother models.
    raw_coordinates = equilibrium.get("nodeCoordinatesMm")  # Recover the published baseline-coordinate overrides.
    require(isinstance(raw_coordinates, dict), "equilibrium_state.nodeCoordinatesMm must be an object")  # Require an explicit keyed coordinate contract.
    analysis_nodes = dict(nodes)  # Start from the complete frozen source coordinates.
    for raw_node_id, raw_values in raw_coordinates.items():  # Apply every explicit P2 coordinate override exactly once.
        require(isinstance(raw_node_id, str) and raw_node_id.isdigit(), f"invalid equilibrium node id: {raw_node_id}")  # Require canonical decimal source labels.
        node_id = int(raw_node_id)  # Convert the validated source label.
        require(node_id in analysis_nodes, f"equilibrium coordinate references unknown node {node_id}")  # Reject topology drift in the state contract.
        require(isinstance(raw_values, list) and len(raw_values) == 3, f"equilibrium node {node_id} must have three coordinates")  # Require one complete Cartesian coordinate.
        coordinates = tuple(finite_float(raw_values[index], f"equilibrium node {node_id} coordinate {index}") for index in range(3))  # Validate all override components.
        analysis_nodes[node_id] = (coordinates[0], coordinates[1], coordinates[2])  # Replace the frozen coordinate with the authoritative P2 coordinate.
    raw_targets = equilibrium.get("targetAxialStressMPa")  # Recover the unique target stress for every suspension element.
    require(isinstance(raw_targets, dict), "equilibrium_state.targetAxialStressMPa must be an object")  # Require explicit element-keyed target data.
    targets: dict[int, float] = {}  # Normalize validated suspension target stresses by integer element id.
    for raw_element_id, raw_value in raw_targets.items():  # Validate every published target stress.
        require(isinstance(raw_element_id, str) and raw_element_id.isdigit(), f"invalid target-stress element id: {raw_element_id}")  # Require canonical decimal source labels.
        element_id = int(raw_element_id)  # Convert the validated element label.
        require(element_id not in targets, f"duplicate target-stress element id: {element_id}")  # Defend against semantic duplication after integer normalization.
        targets[element_id] = finite_float(raw_value, f"target stress for element {element_id}")  # Preserve the finite target stress in MPa.
    require(set(targets) == suspension_ids, "target stress ids must exactly equal MAIN_CABLES plus HANGERS")  # Reject missing, surplus, or reassigned suspension targets.
    return analysis_nodes, targets, equilibrium_sha256  # Return the authoritative analysis geometry, targets, and state digest.


def close_node_frame(active: dict[int, tuple[float, float, float]] | None, frames: list[dict[int, tuple[float, float, float]]], label: str) -> None:  # Finish one explicitly terminated DAT nodal frame.
    require(active is not None and active, f"{label} DAT frame contains no numeric rows")  # Reject empty output headers.
    frames.append(active)  # Preserve the complete chronological frame for final-state selection.


def parse_final_dat_displacements(path: Path, expected_node_ids: set[int]) -> dict[int, tuple[float, float, float]]:  # Parse only the final complete NALL displacement table.
    require(path.is_file(), f"required DAT result is missing: {path}")  # Reject absent solver response evidence.
    try:  # Require exact UTF-8/ASCII solver text without replacement characters.
        lines = path.read_text(encoding="utf-8").splitlines()  # Read the complete DAT result once.
    except UnicodeDecodeError as exc:  # Convert invalid text encoding into the common failure.
        raise ValidationError(f"DAT result is not valid UTF-8: {path}") from exc  # Prevent silent row loss through replacement decoding.
    frames: list[dict[int, tuple[float, float, float]]] = []  # Preserve all explicitly terminated NALL displacement frames.
    active: dict[int, tuple[float, float, float]] | None = None  # Track the current displacement frame.
    for raw in lines:  # Scan every DAT line exactly once.
        line = raw.strip()  # Normalize surrounding whitespace for header and boundary recognition.
        lower = line.lower()  # Cache lowercase text for deterministic header matching.
        if "displacements (vx,vy,vz)" in lower and "set nall" in lower:  # Detect one complete-model displacement table header.
            require(active is None, "a new NALL displacement header began before the prior frame terminated")  # Reject truncated or nested result tables.
            active = {}  # Start a fresh chronological displacement frame.
            continue  # Advance through the optional blank row after the header.
        if active is None:  # Ignore unrelated solver output outside a NALL displacement table.
            continue  # Advance to the next possible table header.
        if not line:  # Accept standard CalculiX blank rows before data and between the final data row and its terminator.
            continue  # Remain inside the current frame while still requiring a later explicit nonblank terminator.
        match = NODE_RESULT_ROW.fullmatch(raw)  # Attempt to parse one node id and three result components.
        if match is not None:  # Preserve a well-formed numeric displacement row.
            node_id = int(match.group(1))  # Recover the original source node label.
            require(node_id not in active, f"duplicate displacement row for node {node_id}")  # Reject ambiguous repeated results inside one frame.
            vector = tuple(parse_text_float(match.group(index), f"displacement node {node_id}") for index in range(2, 5))  # Parse all three finite translations.
            active[node_id] = (vector[0], vector[1], vector[2])  # Store the complete nodal displacement vector.
            continue  # Advance to the next table row.
        if line and active:  # Treat the first nonnumeric nonblank row after data as the required frame terminator.
            close_node_frame(active, frames, "NALL displacement")  # Preserve this explicitly closed displacement frame.
            active = None  # Leave displacement parsing mode.
            continue  # Revisit no data from the terminating header because only the final displacement frame is needed.
        raise ValidationError(f"unexpected content before NALL displacement data: {raw}")  # Reject a malformed empty result table.
    require(active is None, "NALL displacement frame is truncated at end of DAT")  # Refuse to infer completeness from end-of-file.
    require(frames, "no complete NALL displacement frame found in DAT")  # Require solver evidence for the VTK point field.
    final_frame = frames[-1]  # Select only the last explicitly complete chronological response frame.
    require(set(final_frame) == expected_node_ids, "final DAT displacement ids do not exactly cover all 783 primary source nodes")  # Reject missing, helper, surplus, or wind-only node rows.
    return final_frame  # Return the complete final displacement map.


def close_stress_frame(active: dict[int, dict[int, tuple[float, float, float, float, float, float]]] | None, frames: list[dict[int, dict[int, tuple[float, float, float, float, float, float]]]]) -> None:  # Finish one explicitly terminated E_STRUCTURAL stress frame.
    require(active is not None and active, "E_STRUCTURAL DAT frame contains no numeric rows")  # Reject empty stress output headers.
    frames.append(active)  # Preserve the complete chronological stress frame for final-state selection.


def parse_final_dat_stresses(path: Path, expected_element_ids: set[int]) -> dict[int, tuple[float, float, float, float, float, float]]:  # Parse and average only the final complete E_STRUCTURAL stress frame.
    try:  # Require exact UTF-8/ASCII solver text without replacement characters.
        lines = path.read_text(encoding="utf-8").splitlines()  # Read the same complete DAT result independently for stress evidence.
    except (FileNotFoundError, UnicodeDecodeError) as exc:  # Convert missing or invalid text into the common failure.
        raise ValidationError(f"cannot read strict DAT stress evidence: {path}") from exc  # Prevent missing stress output from becoming a zero field.
    frames: list[dict[int, dict[int, tuple[float, float, float, float, float, float]]]] = []  # Preserve all explicitly terminated structural stress frames.
    active: dict[int, dict[int, tuple[float, float, float, float, float, float]]] | None = None  # Track the current element-to-integration-point map.
    for raw in lines:  # Scan every DAT line exactly once.
        line = raw.strip()  # Normalize surrounding whitespace for header and row recognition.
        lower = line.lower()  # Cache lowercase text for deterministic matching.
        if "stresses (elem" in lower and "set e_structural" in lower:  # Detect the complete structural stress table header.
            require(active is None, "a new E_STRUCTURAL stress header began before the prior frame terminated")  # Reject mixed or truncated frames.
            active = {}  # Start a fresh chronological stress frame.
            continue  # Advance through the optional blank row after the header.
        if active is None:  # Ignore unrelated DAT content outside the structural stress table.
            continue  # Advance to the next possible stress header.
        if not line:  # Accept standard CalculiX blank rows before data and between the final data row and its terminator.
            continue  # Remain inside the current frame while still requiring a later explicit nonblank terminator.
        fields = line.split()  # Tokenize a possible CalculiX integration-point stress row.
        numeric_row = len(fields) >= 8 and fields[0].isdigit() and fields[1].isdigit()  # Require element id, integration point, and six stress components.
        if numeric_row:  # Preserve one well-formed integration-point tensor.
            element_id = int(fields[0])  # Recover the source structural element label.
            integration_point = int(fields[1])  # Recover the CalculiX integration-point label.
            samples = active.setdefault(element_id, {})  # Allocate this element's strict integration-point map.
            require(integration_point not in samples, f"duplicate stress record for element {element_id} integration point {integration_point}")  # Reject frame mixing and duplicate output.
            tensor = tuple(parse_text_float(fields[index], f"stress element {element_id} integration point {integration_point}") for index in range(2, 8))  # Parse all six finite Cartesian stress components.
            samples[integration_point] = (tensor[0], tensor[1], tensor[2], tensor[3], tensor[4], tensor[5])  # Preserve the complete symmetric-tensor tuple.
            continue  # Advance to the next stress row.
        if line and active:  # Treat the first nonnumeric nonblank row after data as the required frame terminator.
            close_stress_frame(active, frames)  # Preserve this explicitly closed structural stress frame.
            active = None  # Leave structural stress parsing mode.
            continue  # Ignore the terminating strain or later output header.
        raise ValidationError(f"unexpected content before E_STRUCTURAL stress data: {raw}")  # Reject an empty or malformed stress table.
    require(active is None, "E_STRUCTURAL stress frame is truncated at end of DAT")  # Refuse to infer completeness from end-of-file.
    require(frames, "no complete E_STRUCTURAL stress frame found in DAT")  # Require actual solver stress evidence.
    final_frame = frames[-1]  # Select only the final explicitly complete chronological stress frame.
    require(set(final_frame) == expected_element_ids, "final raw DAT stress ids do not exactly cover all 1070 primary structural elements")  # Prevent P2-only, wind, or zero-default stress completion.
    averaged: dict[int, tuple[float, float, float, float, float, float]] = {}  # Allocate one independently averaged tensor per element.
    for element_id in sorted(expected_element_ids):  # Validate and reduce every source structural element.
        samples = final_frame[element_id]  # Recover this element's strict integration-point records.
        require(set(samples) == EXPECTED_INTEGRATION_POINT_IDS, f"element {element_id} must contain integration points 1..8 exactly")  # Reject partial or mixed stress output.
        averaged[element_id] = tuple(sum(samples[point][component] for point in range(1, 9)) / 8.0 for component in range(6))  # Match the writer's arithmetic eight-point average independently.
    return averaged  # Return complete raw final-frame element stresses without fabricated defaults.


def axial_tensor(stress: float, point_a: tuple[float, float, float], point_b: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:  # Reconstruct one P2 axial stress tensor in global axes.
    chord = tuple(point_b[index] - point_a[index] for index in range(3))  # Build the source element chord vector.
    length = math.sqrt(sum(component * component for component in chord))  # Compute its Euclidean length.
    require(math.isfinite(length) and length > 0.0, "cannot construct an axial tensor on a zero-length element")  # Reject degenerate suspension topology.
    ux, uy, uz = (component / length for component in chord)  # Normalize the axial direction.
    return (stress * ux * ux, stress * uy * uy, stress * uz * uz, stress * ux * uy, stress * ux * uz, stress * uy * uz)  # Return SXX,SYY,SZZ,SXY,SXZ,SYZ.


def von_mises(tensor: tuple[float, float, float, float, float, float]) -> float:  # Recompute the writer's three-dimensional J2 equivalent stress.
    sxx, syy, szz, sxy, sxz, syz = tensor  # Unpack the symmetric Cartesian components.
    value = math.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * (sxy * sxy + sxz * sxz + syz * syz))  # Evaluate the exact writer formula.
    require(math.isfinite(value), "recomputed von Mises stress is non-finite")  # Reject overflow or invalid tensors.
    return value  # Return the finite equivalent stress in MPa.


def projected_axial_stress(tensor: tuple[float, float, float, float, float, float], point_a: tuple[float, float, float], point_b: tuple[float, float, float]) -> float:  # Recompute line stress along the undeformed analysis chord.
    chord = tuple(point_b[index] - point_a[index] for index in range(3))  # Build the analysis-coordinate line chord.
    length = math.sqrt(sum(component * component for component in chord))  # Compute its Euclidean length.
    require(math.isfinite(length) and length > 0.0, "cannot project axial stress on a zero-length element")  # Reject degenerate cells.
    ux, uy, uz = (component / length for component in chord)  # Normalize the line direction.
    sxx, syy, szz, sxy, sxz, syz = tensor  # Unpack the symmetric Cartesian stress components.
    value = sxx * ux * ux + syy * uy * uy + szz * uz * uz + 2.0 * sxy * ux * uy + 2.0 * sxz * ux * uz + 2.0 * syz * uy * uz  # Evaluate u-transpose S u.
    require(math.isfinite(value), "recomputed axial stress is non-finite")  # Reject invalid or overflowing tensor projection.
    return value  # Return the signed line-element axial stress in MPa.


def build_expected_fields(nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], displacements: dict[int, tuple[float, float, float]], raw_stresses: dict[int, tuple[float, float, float, float, float, float]], targets: dict[int, float]) -> tuple[list[int], list[tuple[int, list[int], str]], dict[int, tuple[float, float, float, float, float, float]], dict[str, list[float]]]:  # Reconstruct every VTK field independently from source and raw solver evidence.
    node_ids = sorted(nodes)  # Freeze the same deterministic source-node order as the writer.
    cells = [(element_id, connectivity, group_name) for group_name in GROUP_ORDER for element_id, connectivity in groups[group_name]]  # Freeze the exact component and source connectivity order.
    total_stresses = dict(raw_stresses)  # Start final tensors from complete raw P3 stress output.
    suspension_groups = ("MAIN_CABLES", "HANGERS")  # Restrict P2 reference-stress addition to the suspension subsystem.
    for group_name in suspension_groups:  # Add the P2 reference tensor only after raw P3 coverage has already passed.
        for element_id, connectivity in groups[group_name]:  # Visit every suspension element once.
            base_tensor = axial_tensor(targets[element_id], nodes[connectivity[0]], nodes[connectivity[1]])  # Reconstruct its unique P2 target tensor.
            perturbation = raw_stresses[element_id]  # Require the already validated real P3 stress increment.
            total_stresses[element_id] = tuple(base_tensor[index] + perturbation[index] for index in range(6))  # Compose the coordinated final tensor without zero fallback.
    scalar_fields: dict[str, list[float]] = {name: [] for name in SCALAR_FIELD_ORDER}  # Allocate all six scalar fields in fixed order.
    component_codes = {name: index + 1 for index, name in enumerate(GROUP_ORDER)}  # Reconstruct stable engineering component ids.
    for element_id, connectivity, group_name in cells:  # Derive every scalar from the coordinated final tensor.
        tensor = total_stresses[element_id]  # Recover the complete coordinated tensor for this source cell.
        scalar_fields["von_mises_mpa"].append(von_mises(tensor))  # Recompute the J2 equivalent stress.
        axial = projected_axial_stress(tensor, nodes[connectivity[0]], nodes[connectivity[1]]) if group_name != "DECK_SHELLS" else 0.0  # Project only line-element stress along its analysis chord.
        scalar_fields["axial_stress_mpa"].append(axial)  # Preserve the signed projected line stress.
        target = targets.get(element_id, 0.0)  # Recover a P2 target only for suspension elements.
        scalar_fields["equilibrium_target_axial_stress_mpa"].append(target)  # Preserve the exact target field.
        scalar_fields["stress_coordination_ratio"].append(axial / target if abs(target) > 1.0e-12 else 0.0)  # Recompute the writer's guarded coordination ratio.
        scalar_fields["component_id"].append(float(component_codes[group_name]))  # Preserve the stable numeric component code.
        scalar_fields["source_element_id"].append(float(element_id))  # Preserve the exact original source element label.
    require(set(displacements) == set(node_ids), "internal displacement coverage changed after DAT validation")  # Defend the writer contract at the field-composition boundary.
    require(set(total_stresses) == {element_id for element_id, _connectivity, _group in cells}, "internal total-stress coverage mismatch")  # Defend complete stress coverage at serialization time.
    return node_ids, cells, total_stresses, scalar_fields  # Return all independently reconstructed VTK expectations.


class LineCursor:  # Consume legacy VTK lines exactly once and reject every truncated read.
    def __init__(self, lines: list[str]) -> None:  # Initialize one strict forward-only parser cursor.
        self.lines = lines  # Preserve the complete decoded VTK line list.
        self.index = 0  # Start before the first unconsumed line.

    def take(self, label: str) -> str:  # Consume one required VTK line.
        require(self.index < len(self.lines), f"VTK is truncated before {label}")  # Reject end-of-file before the declared section completes.
        line = self.lines[self.index]  # Recover the next exact line.
        self.index += 1  # Advance the cursor exactly once.
        return line  # Return the consumed line for semantic validation.


def validate_vtk_bytes(vtk_path: Path, summary: dict[str, Any], nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], displacements: dict[int, tuple[float, float, float]], total_stresses: dict[int, tuple[float, float, float, float, float, float]], scalar_fields: dict[str, list[float]], node_ids: list[int], cells: list[tuple[int, list[int], str]]) -> tuple[str, float, float]:  # Parse and validate the complete legacy VTK artifact.
    require(vtk_path.is_file(), f"required VTK artifact is missing: {vtk_path}")  # Reject an absent visualization before digest comparison.
    vtk_bytes = vtk_path.read_bytes()  # Read exact bytes once for encoding, structure, and SHA validation.
    require(vtk_bytes.startswith(b"# vtk DataFile Version 3.0\n"), "VTK signature or line ending is invalid")  # Require the exact legacy signature and LF encoding.
    require(not vtk_bytes.startswith(b"\xef\xbb\xbf"), "VTK UTF-8 BOM is forbidden")  # Reject a hidden prefix before the fixed signature.
    require(b"\x00" not in vtk_bytes, "VTK NUL bytes are forbidden")  # Reject binary or truncated-text contamination.
    require(b"\r" not in vtk_bytes, "VTK CR line endings are forbidden")  # Freeze portable LF-only serialization.
    require(vtk_bytes.endswith(b"\n"), "VTK must end with one complete LF-terminated line")  # Reject a truncated final scalar record.
    try:  # Decode the required portable ASCII-compatible UTF-8 representation strictly.
        vtk_text = vtk_bytes.decode("utf-8")  # Preserve exact characters without replacement.
    except UnicodeDecodeError as exc:  # Convert encoding corruption into the common validation failure.
        raise ValidationError("VTK is not valid UTF-8 text") from exc  # Prevent silent data loss during parsing.
    lines = vtk_text.splitlines()  # Split LF-terminated text into exact logical records.
    require(len(lines) == EXPECTED_VTK_LINE_COUNT, f"VTK line count must be exactly {EXPECTED_VTK_LINE_COUNT}")  # Reject truncation, surplus fields, and inserted blank rows.
    require(all(line and line == line.strip() for line in lines), "VTK blank lines or surrounding whitespace are forbidden")  # Freeze the deterministic writer layout.
    vtk_sha256 = hashlib.sha256(vtk_bytes).hexdigest()  # Recompute the delivered visualization digest independently.
    vtk_summary = summary.get("vtk")  # Recover the nested producer visualization receipt.
    require(isinstance(vtk_summary, dict), "summary.vtk must be an object")  # Require the complete nested receipt.
    require(vtk_summary.get("sha256") == vtk_sha256, "summary.vtk.sha256 does not match delivered VTK bytes")  # Bind the nested receipt to actual bytes.
    require(summary.get("vtkSha256") == vtk_sha256, "summary.vtkSha256 does not match delivered VTK bytes")  # Bind the top-level receipt to the same actual bytes.
    cursor = LineCursor(lines)  # Initialize strict sequential VTK consumption.
    require(cursor.take("VTK version") == "# vtk DataFile Version 3.0", "unexpected VTK version header")  # Require the exact legacy format version.
    require(cursor.take("VTK title") == "Zhaqing suspension bridge stress-coordinated P4 result", "unexpected VTK dataset title")  # Require the exact canonical title.
    require(cursor.take("VTK encoding") == "ASCII", "VTK encoding must be ASCII")  # Reject binary or undeclared mixed encoding.
    require(cursor.take("VTK dataset") == "DATASET UNSTRUCTURED_GRID", "VTK dataset must be UNSTRUCTURED_GRID")  # Require the intended finite-element grid type.
    require(cursor.take("POINTS declaration") == f"POINTS {EXPECTED_POINT_COUNT} double", "VTK POINTS declaration mismatch")  # Require the exact point count and precision.
    for node_id in node_ids:  # Validate every deformed point in sorted source-node order.
        tokens, _values = parse_vtk_float_row(cursor.take(f"point {node_id}"), 3, f"point {node_id}")  # Consume exactly one Cartesian coordinate.
        expected_point = tuple(nodes[node_id][index] + displacements[node_id][index] for index in range(3))  # Reconstruct the writer's deformed coordinate.
        require_canonical_values(tokens, expected_point, f"point {node_id}")  # Require exact canonical coordinate serialization.
    require(cursor.take("CELLS declaration") == f"CELLS {EXPECTED_CELL_COUNT} {EXPECTED_CONNECTIVITY_INTEGER_COUNT}", "VTK CELLS declaration mismatch")  # Require exact cell and integer counts.
    point_index = {node_id: index for index, node_id in enumerate(node_ids)}  # Reconstruct the source-label to zero-based VTK index map.
    for cell_index, (element_id, connectivity, _group_name) in enumerate(cells):  # Validate every cell in fixed engineering-component order.
        line = cursor.take(f"cell {cell_index}")  # Consume one complete connectivity row.
        tokens = line.split()  # Split the integer payload without accepting commas or floats.
        require(tokens and all(token.isdigit() for token in tokens), f"cell {cell_index} must contain only non-negative integers")  # Reject negative, floating, or malformed indices.
        values = [int(token) for token in tokens]  # Convert the validated integer tokens.
        require(values[0] == len(connectivity) and len(values) == len(connectivity) + 1, f"cell {cell_index} connectivity width mismatch")  # Require a self-consistent row width.
        require(all(0 <= value < EXPECTED_POINT_COUNT for value in values[1:]), f"cell {cell_index} contains an out-of-range point index")  # Reject dangling connectivity.
        require(len(set(values[1:])) == len(values[1:]), f"cell {cell_index} repeats a point index")  # Reject degenerate cells.
        expected_values = [len(connectivity)] + [point_index[node_id] for node_id in connectivity]  # Reconstruct exact source connectivity in VTK indices.
        require(values == expected_values, f"cell {cell_index} / source element {element_id} connectivity mismatch")  # Reject reordering, substitution, or topology drift.
    require(cursor.take("CELL_TYPES declaration") == f"CELL_TYPES {EXPECTED_CELL_COUNT}", "VTK CELL_TYPES declaration mismatch")  # Require one type per structural cell.
    for cell_index, (_element_id, _connectivity, group_name) in enumerate(cells):  # Validate each cell family against its source component.
        raw_type = cursor.take(f"cell type {cell_index}")  # Consume one exact integer type code.
        require(raw_type.isdigit(), f"cell type {cell_index} must be an integer")  # Reject floating or malformed type values.
        expected_type = 9 if group_name == "DECK_SHELLS" else 3  # Map S4 shells to VTK_QUAD and all line cells to VTK_LINE.
        require(int(raw_type) == expected_type, f"cell type mismatch at cell {cell_index}")  # Reject a topology/type inconsistency.
    require(cursor.take("POINT_DATA declaration") == f"POINT_DATA {EXPECTED_POINT_COUNT}", "VTK POINT_DATA declaration mismatch")  # Require one response vector per source node.
    require(cursor.take("displacement field declaration") == "VECTORS displacement_mm double", "VTK displacement vector declaration mismatch")  # Require the exact physical field name and units.
    for node_id in node_ids:  # Validate every final nodal displacement in point order.
        tokens, _values = parse_vtk_float_row(cursor.take(f"displacement {node_id}"), 3, f"displacement {node_id}")  # Consume one complete U1,U2,U3 vector.
        require_canonical_values(tokens, displacements[node_id], f"displacement {node_id}")  # Require the exact raw final DAT displacement serialization.
    require(cursor.take("CELL_DATA declaration") == f"CELL_DATA {EXPECTED_CELL_COUNT}", "VTK CELL_DATA declaration mismatch")  # Require one engineering field record per structural cell.
    require(cursor.take("stress tensor declaration") == "TENSORS stress_tensor_mpa double", "VTK stress tensor declaration mismatch")  # Require the exact coordinated tensor field.
    for cell_index, (element_id, _connectivity, _group_name) in enumerate(cells):  # Validate one full symmetric tensor for every cell.
        sxx, syy, szz, sxy, sxz, syz = total_stresses[element_id]  # Recover the independently composed coordinated tensor.
        expected_rows = ((sxx, sxy, sxz), (sxy, syy, syz), (sxz, syz, szz))  # Expand six components to the exact symmetric 3x3 writer layout.
        for row_index, expected_row in enumerate(expected_rows):  # Consume and validate all three tensor rows.
            tokens, values = parse_vtk_float_row(cursor.take(f"tensor cell {cell_index} row {row_index}"), 3, f"tensor cell {cell_index} row {row_index}")  # Parse one finite tensor row.
            require_canonical_values(tokens, expected_row, f"tensor cell {cell_index} row {row_index}")  # Require exact independently reconstructed tensor values.
            require(all(math.isfinite(value) for value in values), f"tensor cell {cell_index} contains a non-finite value")  # Retain an explicit finite tensor invariant.
    for field_name in SCALAR_FIELD_ORDER:  # Consume exactly six required scalar fields in canonical order.
        require(cursor.take(f"{field_name} declaration") == f"SCALARS {field_name} double 1", f"VTK scalar declaration mismatch for {field_name}")  # Reject missing, duplicate, renamed, or reordered fields.
        require(cursor.take(f"{field_name} lookup table") == "LOOKUP_TABLE default", f"VTK lookup table mismatch for {field_name}")  # Require the standard scalar lookup declaration.
        expected_values = scalar_fields[field_name]  # Recover one independently reconstructed value per source cell.
        require(len(expected_values) == EXPECTED_CELL_COUNT, f"internal scalar count mismatch for {field_name}")  # Defend complete expected-field coverage.
        for cell_index, expected_value in enumerate(expected_values):  # Validate every scalar record in cell order.
            tokens, _values = parse_vtk_float_row(cursor.take(f"{field_name} cell {cell_index}"), 1, f"{field_name} cell {cell_index}")  # Consume one finite scalar value.
            require_canonical_values(tokens, (expected_value,), f"{field_name} cell {cell_index}", exact=field_name in ("component_id", "source_element_id"))  # Require exact discrete ids and tightly matched physical scalars.
    require(cursor.index == len(lines), "VTK contains trailing or unknown sections")  # Reject any extra payload after the sixth scalar field.
    maximum_von_mises = max(scalar_fields["von_mises_mpa"])  # Recompute the nested receipt's maximum J2 stress.
    maximum_abs_axial = max(abs(value) for value in scalar_fields["axial_stress_mpa"])  # Recompute the nested receipt's maximum axial magnitude.
    require(vtk_summary.get("pointCount") == EXPECTED_POINT_COUNT, "summary VTK point count mismatch")  # Bind summary count to parsed topology.
    require(vtk_summary.get("cellCount") == EXPECTED_CELL_COUNT, "summary VTK cell count mismatch")  # Bind summary count to parsed topology.
    summary_max_von = finite_float(vtk_summary.get("maxVonMisesMPa"), "summary.vtk.maxVonMisesMPa")  # Validate the producer maximum as a finite number.
    summary_max_axial = finite_float(vtk_summary.get("maxAbsAxialStressMPa"), "summary.vtk.maxAbsAxialStressMPa")  # Validate the producer axial maximum as a finite number.
    require(math.isclose(summary_max_von, maximum_von_mises, rel_tol=1.0e-12, abs_tol=1.0e-12), "summary maximum von Mises stress mismatch")  # Bind the receipt maximum to recomputed values.
    require(math.isclose(summary_max_axial, maximum_abs_axial, rel_tol=1.0e-12, abs_tol=1.0e-12), "summary maximum absolute axial stress mismatch")  # Bind the receipt maximum to recomputed values.
    return vtk_sha256, maximum_von_mises, maximum_abs_axial  # Return decisive independently verified visualization quantities.


def validate_artifacts(vtk_path: Path, summary_path: Path, baseline_path: Path, equilibrium_path: Path, dat_path: Path, wind_exclusion_path: Path, expected_baseline_sha256: str = FROZEN_BASELINE_SHA256) -> dict[str, Any]:  # Validate the complete canonical primary-response VTK evidence chain.
    baseline_sha256 = sha256_path(baseline_path)  # Recover the exact mother-deck identity before semantic parsing.
    require(baseline_sha256 == expected_baseline_sha256, "baseline digest does not match the validation contract")  # Enforce the caller-selected immutable baseline identity.
    baseline_nodes, groups = parse_baseline(baseline_path, expected_baseline_sha256)  # Independently parse and validate the fixed source topology.
    primary_node_ids = {node_id for group_name in GROUP_ORDER for _element_id, connectivity in groups[group_name] for node_id in connectivity}  # Derive every node referenced by primary response directly from baseline topology.
    require(primary_node_ids == set(range(1, EXPECTED_POINT_COUNT + 1)), "primary source nodes must be exactly 1..783")  # Reject any wind-only or missing primary point.
    excluded_element_ids, wind_only_node_ids, wind_exclusion_sha256 = parse_wind_exclusion(wind_exclusion_path, groups, primary_node_ids)  # Validate the mandatory G3/G5 exclusion receipt.
    require(not (primary_node_ids & wind_only_node_ids), "wind-only nodes must not enter primary response")  # Defend the source point partition explicitly.
    cells = [(element_id, connectivity, group_name) for group_name in GROUP_ORDER for element_id, connectivity in groups[group_name]]  # Build the exact seven-group primary cell order.
    require(not ({element_id for element_id, _connectivity, _group_name in cells} & excluded_element_ids), "excluded wind elements must not enter primary response")  # Defend the source cell partition explicitly.
    expected_element_ids = {element_id for element_id, _connectivity, _group_name in cells}  # Recover the complete 1070-element primary source set.
    suspension_ids = {element_id for group_name in ("MAIN_CABLES", "HANGERS") for element_id, _connectivity in groups[group_name]}  # Recover the exact P2 target-stress element set.
    analysis_nodes, targets, equilibrium_sha256 = parse_equilibrium(equilibrium_path, baseline_sha256, baseline_nodes, suspension_ids)  # Validate and reconstruct the P2 analysis geometry.
    analysis_nodes = {node_id: analysis_nodes[node_id] for node_id in sorted(primary_node_ids)}  # Restrict visualization geometry to the exact baseline-derived primary point set.
    expected_node_ids = set(analysis_nodes)  # Recover the complete 783-node primary VTK point set.
    displacements = parse_final_dat_displacements(dat_path, expected_node_ids)  # Require complete raw final nodal response evidence.
    raw_stresses = parse_final_dat_stresses(dat_path, expected_element_ids)  # Require complete raw final stress evidence before P2 composition.
    node_ids, expected_cells, total_stresses, scalar_fields = build_expected_fields(analysis_nodes, groups, displacements, raw_stresses, targets)  # Reconstruct every expected VTK value independently.
    require(expected_cells == cells, "internal cell-order reconstruction mismatch")  # Defend deterministic component and source order.
    summary = load_strict_json(summary_path)  # Parse the producer summary without ambiguous or non-finite JSON values.
    require(summary.get("sourceBaselineSha256") == baseline_sha256, "summary baseline digest mismatch")  # Bind the summary to the exact mother deck.
    require(summary.get("equilibriumStateSha256") == equilibrium_sha256, "summary equilibrium-state digest mismatch")  # Bind the summary to the exact P2 state bytes.
    vtk_sha256, maximum_von_mises, maximum_abs_axial = validate_vtk_bytes(vtk_path, summary, analysis_nodes, groups, displacements, total_stresses, scalar_fields, node_ids, cells)  # Parse and validate the delivered VTK from beginning to EOF.
    return {  # Publish one compact independent machine receipt for canonical workflow enforcement.
        "schema": "zhaqing-strict-vtk-validation-v1",  # Version the independent validation contract explicitly.
        "status": "PASS",  # Announce PASS only after every preceding fail-closed invariant succeeded.
        "inputs": {  # Bind the receipt to every exact evidence file used by validation.
            "baselineSha256": baseline_sha256,  # Record the frozen LC01 mother-deck digest.
            "equilibriumStateSha256": equilibrium_sha256,  # Record the exact P2 state digest.
            "datSha256": sha256_path(dat_path),  # Record the exact final raw solver result digest.
            "windExclusionSha256": wind_exclusion_sha256,  # Record the exact G3/G5 wind-exclusion receipt digest.
            "summarySha256": sha256_path(summary_path),  # Record the exact producer summary digest.
            "vtkSha256": vtk_sha256,  # Record the exact delivered VTK digest.
        },  # Finish the immutable input identity block.
        "contract": {  # Publish decisive fixed topology and field coverage quantities.
            "pointCount": EXPECTED_POINT_COUNT,  # Record complete node coverage.
            "cellCount": EXPECTED_CELL_COUNT,  # Record complete structural-cell coverage.
            "connectivityIntegerCount": EXPECTED_CONNECTIVITY_INTEGER_COUNT,  # Record the exact CELLS payload size.
            "integrationPointCountPerElement": len(EXPECTED_INTEGRATION_POINT_IDS),  # Record complete raw stress sampling.
            "vtkLineCount": EXPECTED_VTK_LINE_COUNT,  # Record the deterministic ASCII line count.
            "scalarFields": list(SCALAR_FIELD_ORDER),  # Record the exact required scalar field order.
            "excludedWindElementIds": sorted(excluded_element_ids),  # Record the eight baseline-derived wind elements excluded from primary response.
            "excludedWindOnlyNodeIds": sorted(wind_only_node_ids),  # Record the eight baseline-derived wind-only points excluded from primary response.
            "windExclusionStatus": "BLOCKED_G3_G5",  # Preserve the engineering evidence boundary in the strict VTK receipt.
            "stressSemantics": {"MAIN_CABLES": "raw DAT tensor is the analytic current-minus-F3 increment and VTK total adds the F3 equilibrium tensor", "HANGERS": "raw DAT tensor is the analytic current-minus-F3 increment and VTK total adds the F3 equilibrium tensor", "retainedStructure": "raw DAT tensor is the final total tensor and transfers to VTK without F3 addition"},  # Declare the canonical mixed tangent-or-nonlinear response semantics explicitly for downstream audit.
        },  # Finish the fixed validation contract block.
        "results": {  # Publish independently recomputed visualization extrema.
            "maxVonMisesMPa": maximum_von_mises,  # Record the complete cell-field J2 maximum.
            "maxAbsAxialStressMPa": maximum_abs_axial,  # Record the complete line-field axial maximum.
        },  # Finish independently recomputed result quantities.
    }  # Return the complete PASS receipt.


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:  # Persist one deterministic independent validation receipt.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the explicitly requested receipt directory.
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")  # Write strict finite JSON with a final newline.


def build_argument_parser() -> argparse.ArgumentParser:  # Define the standalone validator command-line contract.
    parser = argparse.ArgumentParser(description="Strictly validate the canonical Zhaqing stress-coordinated legacy VTK")  # Create the fail-closed CLI parser.
    parser.add_argument("--vtk", type=Path, required=True)  # Require the delivered legacy VTK artifact.
    parser.add_argument("--summary", type=Path, required=True)  # Require the producer P4 summary receipt.
    parser.add_argument("--baseline", type=Path, required=True)  # Require the immutable LC01 mother deck.
    parser.add_argument("--equilibrium", type=Path, required=True)  # Require the exact P2 equilibrium-state contract.
    parser.add_argument("--dat", type=Path, required=True)  # Require the final raw P3 CalculiX DAT result.
    parser.add_argument("--wind-exclusion", type=Path, required=True)  # Require the explicit baseline-derived G3/G5 wind exclusion receipt.
    parser.add_argument("--receipt", type=Path, required=True)  # Require an explicit output path for the independent receipt.
    return parser  # Return the complete deterministic CLI definition.


def main(argv: list[str] | None = None) -> int:  # Execute strict validation and publish a process-level Gate result.
    args = build_argument_parser().parse_args(argv)  # Parse every required evidence and receipt path before validation.
    try:  # Convert every validation defect into a deterministic FAIL receipt and exit code.
        input_paths = {args.vtk.resolve(), args.summary.resolve(), args.baseline.resolve(), args.equilibrium.resolve(), args.dat.resolve(), args.wind_exclusion.resolve()}  # Resolve protected input paths for overwrite prevention.
        require(args.receipt.resolve() not in input_paths, "receipt path must not overwrite validation input evidence")  # Prevent destructive replacement of source evidence.
        receipt = validate_artifacts(args.vtk, args.summary, args.baseline, args.equilibrium, args.dat, args.wind_exclusion, FROZEN_BASELINE_SHA256)  # Execute primary-response validation only against the immutable baseline and explicit wind exclusion.
    except (ValidationError, OSError, ValueError, KeyError, TypeError) as exc:  # Fail closed on contract, file, numeric, and schema defects.
        failure = {"schema": "zhaqing-strict-vtk-validation-v1", "status": "FAIL", "error": str(exc)}  # Publish one compact non-ambiguous failure receipt.
        write_receipt(args.receipt, failure)  # Preserve the rejection reason for immutable Actions evidence.
        print(json.dumps(failure, ensure_ascii=False, allow_nan=False), file=sys.stderr)  # Mirror the same failure into the workflow log.
        return 2  # Make native process failure follow the strict VTK Gate.
    write_receipt(args.receipt, receipt)  # Persist the complete PASS receipt only after every invariant succeeds.
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))  # Mirror decisive verified quantities into the workflow log.
    return 0  # Return success only for a fully validated canonical artifact.


if __name__ == "__main__":  # Execute the validator only when invoked explicitly.
    raise SystemExit(main())  # Propagate the strict validation result to the caller.
