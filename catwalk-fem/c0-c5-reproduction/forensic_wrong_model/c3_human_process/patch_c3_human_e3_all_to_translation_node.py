#!/usr/bin/env python3  # Target-blind ROTX/ROTY/ROTZ=0 E3 hypothesis on frozen C3. Masters from agent Ultra S10 include, not undisclosed human APDL. frequency_reproduced=false. human_apdl=false.
from __future__ import annotations  # Preserve modern type annotations on the GitHub Actions Python runtime.
import argparse  # Parse the explicit source, legacy APDL, output, variant, and modal-root controls.
import csv  # Write the coordinate-matched APDL-to-C3 master ledger used by each daughter model.
import hashlib  # Verify immutable input identities and record output identities.
import json  # Write the machine-readable construction receipt.
from collections import Counter  # Count each legacy CERIG degree-of-freedom profile without external packages.
from pathlib import Path  # Handle repository and Actions paths without shell-dependent string operations.
from typing import Iterable  # Annotate helpers that consume deterministic integer sequences.
C3_PARENT_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"  # Lock the released C3 parent deck used by the E3 rotation variant.
LEGACY_APDL_SHA256 = "72012ebbd107cf377c2178561b9008606aeb894c4f7879110d13c30d2a417330"  # Lock apply_finite_gates_and_passages_v2.inp from the agent Ultra S10 section-shear snapshot.
EXPECTED_PARENT_NODES = 91415  # Preserve the validated C3 node count before any variant operation.
EXPECTED_PARENT_ELEMENTS = 172998  # Preserve the validated C3 element count before any variant operation.
EXPECTED_LEGACY_MASTERS = 3692  # Preserve the recovered count of unique CERIG master nodes.
EXPECTED_PASSAGE_MASTERS = 42  # Preserve the recovered count of twenty-one passage stations times two catwalk sides.
EXPECTED_MAIN13_MASTERS = 26  # Preserve the recovered count of thirteen main-span passage stations times two catwalk sides.
MAIN_SPAN_X_MIN_MM = 660000.0  # Use the physical north-tower main-span coordinate as the selection lower bound.
MAIN_SPAN_X_MAX_MM = 2960000.0  # Use the physical south-tower main-span coordinate as the selection upper bound.
OBSERVATION_NODES = [79599, 79701, 79803, 79905, 80007, 80109, 80211, 80313, 80415, 80517, 80619, 80721, 80823, 80925, 81027, 81129, 81231, 81333, 81435, 81537, 81639, 82028, 82130, 82232, 82334, 82436, 82538, 82640, 82742, 82844, 82946, 83048, 83150, 83252, 83354, 83456, 83558, 83660, 83762, 83864, 83966, 84068, 79453, 79454, 79455, 79456, 79457, 79458, 79459, 79460]  # Use the same fifty translational observation nodes as the frozen C3 baseline solve.
VARIANT_EXPECTED_COUNTS = {"E3_ALL21_TRANSLATION_SLAVE_ALL": EXPECTED_PASSAGE_MASTERS}  # Lock the physical scope of the preregistered E3 all-DOF-to-translation-node hypothesis.
def sha256_bytes(data: bytes) -> str:  # Return the lowercase SHA-256 digest of one immutable byte stream.
    return hashlib.sha256(data).hexdigest()  # Compute and return the content digest without modifying the stream.
def coordinate_key(x_value: float, y_value: float, z_value: float) -> tuple[float, float, float]:  # Normalize one three-dimensional coordinate for exact cross-format matching.
    return round(x_value, 6), round(y_value, 6), round(z_value, 6)  # Match the previously audited one-micrometre decimal representation.
def parse_arguments() -> argparse.Namespace:  # Parse all explicit construction controls from the command line.
    parser = argparse.ArgumentParser(description="Patch exact C3 with the target-blind E3 all-rotation-remove hypothesis mapped from the agent Ultra S10 include. Not human APDL.")  # Create a self-documenting command-line interface.
    parser.add_argument("--source", required=True, type=Path)  # Require the exact frozen C3 parent input path.
    parser.add_argument("--legacy-apdl", required=True, type=Path)  # Require the agent Ultra S10 finite-gate-and-passage include (not undisclosed human APDL).
    parser.add_argument("--output", required=True, type=Path)  # Require the complete daughter input path.
    parser.add_argument("--variant", required=True, choices=sorted(VARIANT_EXPECTED_COUNTS))  # Restrict construction to the single preregistered E3 variant.
    parser.add_argument("--roots", type=int, default=40)  # Request forty modes by default for branch tracking through crossings.
    parser.add_argument("--expected-source-sha256", default=C3_PARENT_SHA256)  # Allow explicit identity injection only for local parser tests while the workflow retains the frozen digest.
    parser.add_argument("--expected-parent-nodes", type=int, default=EXPECTED_PARENT_NODES)  # Allow local parser tests to state their known node count explicitly.
    parser.add_argument("--expected-parent-elements", type=int, default=EXPECTED_PARENT_ELEMENTS)  # Allow local parser tests to state their known element count explicitly.
    return parser.parse_args()  # Return the validated command-line namespace.
def parse_c3_entities(lines: list[str]) -> tuple[dict[int, tuple[float, float, float]], set[int]]:  # Read unique C3 node coordinates and element identities from the complete parent deck.
    node_coordinates: dict[int, tuple[float, float, float]] = {}  # Accumulate every numeric node and its exact model coordinate.
    element_ids: set[int] = set()  # Accumulate every numeric element identifier exactly once.
    active_keyword = ""  # Track whether the current data block is a NODE or ELEMENT block.
    for raw_line in lines:  # Scan the parent deck once in source order.
        stripped = raw_line.strip()  # Remove surrounding whitespace without changing stored source content.
        if not stripped or stripped.startswith("**"):  # Ignore blank lines and CalculiX comment lines for entity parsing.
            continue  # Advance to the next source record.
        if stripped.startswith("*"):  # Update the current keyword whenever a CalculiX keyword line is reached.
            active_keyword = stripped.split(",", 1)[0].upper()  # Normalize only the keyword token and preserve all later source text untouched.
            continue  # Keyword lines do not themselves contain entity identifiers.
        if active_keyword == "*NODE":  # Parse one node data record inside a NODE block.
            fields = [field.strip() for field in stripped.split(",")]  # Split the node identifier and three global coordinates.
            if len(fields) >= 4 and fields[0].lstrip("+-").isdigit():  # Accept only complete explicit numeric node records.
                node_id = int(fields[0])  # Parse the unique C3 node identifier.
                node_coordinates[node_id] = coordinate_key(float(fields[1]), float(fields[2]), float(fields[3]))  # Record its rounded exact matching coordinate.
        elif active_keyword == "*ELEMENT":  # Parse one element data record inside an ELEMENT block.
            token = stripped.split(",", 1)[0].strip()  # Read the leading element identifier token.
            if token.lstrip("+-").isdigit():  # Accept only explicit numeric element identifiers.
                element_ids.add(int(token))  # Record the unique element identity.
    return node_coordinates, element_ids  # Return the complete parent entity identity data.
def parse_legacy_apdl(apdl_text: str) -> tuple[dict[int, tuple[float, float, float]], list[int], dict[int, Counter[str]]]:  # Recover legacy APDL node coordinates and ordered CERIG master profiles.
    apdl_coordinates: dict[int, tuple[float, float, float]] = {}  # Accumulate every APDL N-command coordinate needed for master mapping.
    master_order: list[int] = []  # Preserve the first CERIG occurrence order used by the legacy include.
    master_profiles: dict[int, Counter[str]] = {}  # Count ALL and UXYZ CERIG calls for every master node.
    for raw_line in apdl_text.splitlines():  # Scan the S10 include once in source order.
        command_text = raw_line.split("!", 1)[0].strip()  # Remove only APDL end-of-line comments before command parsing.
        if not command_text:  # Ignore blank and comment-only records.
            continue  # Advance to the next APDL record.
        fields = [field.strip() for field in command_text.split(",")]  # Split one APDL command into normalized fields.
        command = fields[0].upper()  # Normalize the APDL command token.
        if command == "N" and len(fields) >= 5 and fields[1].lstrip("+-").isdigit():  # Parse explicit N,node,x,y,z records.
            node_id = int(fields[1])  # Parse the legacy APDL node identifier.
            apdl_coordinates[node_id] = coordinate_key(float(fields[2]), float(fields[3]), float(fields[4]))  # Record the exact global coordinate.
        elif command == "CERIG" and len(fields) >= 4 and fields[1].lstrip("+-").isdigit():  # Parse explicit CERIG,master,slave,DOF records.
            master_id = int(fields[1])  # Parse the legacy CERIG master identifier.
            dof_label = fields[3].upper() if fields[3] else "ALL"  # Treat an omitted CERIG degree-of-freedom label as the APDL ALL default.
            if master_id not in master_profiles:  # Initialize a profile at the first occurrence of each master.
                master_profiles[master_id] = Counter()  # Create an empty deterministic CERIG profile counter.
                master_order.append(master_id)  # Preserve the first-occurrence legacy source order.
            master_profiles[master_id][dof_label] += 1  # Count the exact CERIG operation applied to this master.
    missing_coordinates = [master_id for master_id in master_order if master_id not in apdl_coordinates]  # Identify CERIG masters without an explicit N-command coordinate.
    if missing_coordinates:  # Require complete legacy master geometry.
        raise ValueError(f"Legacy APDL masters lack coordinates: {missing_coordinates[:20]}.")  # Reject an incomplete or wrong APDL include.
    return apdl_coordinates, master_order, master_profiles  # Return the complete legacy master geometry and profiles.
def map_legacy_masters_to_c3(c3_coordinates: dict[int, tuple[float, float, float]], apdl_coordinates: dict[int, tuple[float, float, float]], master_order: list[int], master_profiles: dict[int, Counter[str]]) -> list[dict[str, object]]:  # Coordinate-match every legacy CERIG master to one exact C3 node.
    c3_by_coordinate: dict[tuple[float, float, float], list[int]] = {}  # Build a reverse C3 coordinate index that retains duplicate-coordinate detection.
    for node_id, key in c3_coordinates.items():  # Index every C3 node by its rounded global coordinate.
        c3_by_coordinate.setdefault(key, []).append(node_id)  # Retain all identities at each coordinate for ambiguity checks.
    rows: list[dict[str, object]] = []  # Accumulate one auditable mapping row per legacy CERIG master.
    for master_id in master_order:  # Preserve the legacy first-CERIG source order.
        key = apdl_coordinates[master_id]  # Read the S10 include master coordinate.
        candidates = c3_by_coordinate.get(key, [])  # Find all exact C3 nodes at the same rounded coordinate.
        if len(candidates) != 1:  # Require one and only one C3 identity for every legacy master.
            raise ValueError(f"Legacy master {master_id} at {key} maps to {len(candidates)} C3 nodes: {candidates[:20]}.")  # Reject missing or ambiguous coordinate mappings.
        profile = master_profiles[master_id]  # Read the exact CERIG operation profile for this master.
        rows.append({"apdl_master": master_id, "c3_node": candidates[0], "x_mm": key[0], "y_mm": key[1], "z_mm": key[2], "all_count": int(profile.get("ALL", 0)), "uxyz_count": int(profile.get("UXYZ", 0)), "profile": tuple(sorted((label, int(count)) for label, count in profile.items()))})  # Record geometry, C3 identity, and CERIG profile.
    return rows  # Return the complete exact APDL-to-C3 master ledger.
def select_variant_rows(variant: str, mapping_rows: list[dict[str, object]]) -> list[dict[str, object]]:  # Select the exact S10-mapped master scope for the preregistered E3 hypothesis.
    passage_rows = [row for row in mapping_rows if row["all_count"] == 3 and row["uxyz_count"] == 1]  # Identify the twenty-one two-sided passage masters by their unique three-ALL-plus-one-UXYZ signature.
    passage_rows.sort(key=lambda row: (float(row["x_mm"]), -float(row["y_mm"])))  # Order passage masters by station and positive-Y side first.
    main13_rows = [row for row in passage_rows if MAIN_SPAN_X_MIN_MM < float(row["x_mm"]) < MAIN_SPAN_X_MAX_MM]  # Select passage masters physically between the two main towers.
    if len(mapping_rows) != EXPECTED_LEGACY_MASTERS:  # Preserve the full recovered CERIG-master scope.
        raise ValueError(f"Expected {EXPECTED_LEGACY_MASTERS} mapped legacy masters, found {len(mapping_rows)}.")  # Reject an incomplete or different APDL model line.
    if len(passage_rows) != EXPECTED_PASSAGE_MASTERS:  # Preserve the twenty-one two-sided passage scope.
        raise ValueError(f"Expected {EXPECTED_PASSAGE_MASTERS} passage masters, found {len(passage_rows)}.")  # Reject a changed passage template.
    if len(main13_rows) != EXPECTED_MAIN13_MASTERS:  # Preserve the thirteen two-sided main-span passage scope.
        raise ValueError(f"Expected {EXPECTED_MAIN13_MASTERS} main-span passage masters, found {len(main13_rows)}.")  # Reject a changed main-span station selection.
    if variant == "E3_ALL21_TRANSLATION_SLAVE_ALL":  # Implement the mistaken CERIG ALL relation from each passage master to its translation-only rope slave.
        return passage_rows  # Return all forty-two physical passage masters whose rotations are indirectly removed by the wrong ALL option.
    raise ValueError(f"Unsupported variant {variant}.")  # Reject any unregistered E3 operation.
def parse_existing_numeric_boundaries(lines: list[str]) -> set[tuple[int, int]]:  # Identify explicit numeric node-DOF constraints already present in the parent.
    constrained: set[tuple[int, int]] = set()  # Accumulate every existing numeric node and constrained degree of freedom.
    inside_boundary = False  # Track whether the current data records belong to a BOUNDARY block.
    for raw_line in lines:  # Scan the complete source deck in order.
        stripped = raw_line.strip()  # Normalize whitespace for keyword and field parsing.
        if not stripped or stripped.startswith("**"):  # Ignore blank and comment lines without leaving an active boundary block.
            continue  # Advance to the next record.
        if stripped.startswith("*"):  # Update the active block on every keyword line.
            inside_boundary = stripped.split(",", 1)[0].upper() == "*BOUNDARY"  # Enter only literal BOUNDARY data blocks.
            continue  # Keyword lines contain no constrained numeric node record.
        if not inside_boundary:  # Skip all non-boundary data records.
            continue  # Advance to the next record.
        fields = [field.strip() for field in stripped.split(",")]  # Split one boundary data line into normalized fields.
        if len(fields) < 2 or not fields[0].lstrip("+-").isdigit():  # Ignore named node sets and malformed numeric records.
            continue  # Advance to the next boundary record.
        node_id = int(fields[0])  # Parse the explicit numeric node identifier.
        first_dof = int(fields[1])  # Parse the first constrained degree of freedom.
        last_dof = int(fields[2]) if len(fields) >= 3 and fields[2] else first_dof  # Parse the last constrained degree of freedom or reuse the first.
        for dof in range(first_dof, last_dof + 1):  # Expand a boundary interval into individual node-DOF identities.
            constrained.add((node_id, dof))  # Record the existing explicit constraint.
    return constrained  # Return the complete explicit numeric boundary identity set.
def find_final_perturbation_step(lines: list[str]) -> tuple[int, int]:  # Locate the final modal perturbation step that will be replaced without touching model data.
    step_indices = [index for index, line in enumerate(lines) if line.strip().upper().startswith("*STEP") and "PERTURBATION" in line.upper()]  # Find every perturbation-step opening line.
    if len(step_indices) != 1:  # Require one unambiguous frozen-tangent modal step in the released C3 deck.
        raise ValueError(f"Expected exactly one perturbation step, found {len(step_indices)}.")  # Reject an ambiguous or structurally changed parent.
    start_index = step_indices[0]  # Select the sole modal-step opening line.
    end_candidates = [index for index in range(start_index + 1, len(lines)) if lines[index].strip().upper().startswith("*END STEP")]  # Find closing step keywords after the opening line.
    if not end_candidates:  # Require a complete modal step.
        raise ValueError("The perturbation step has no END STEP keyword.")  # Reject a truncated or malformed parent deck.
    end_index = end_candidates[0]  # Select the first closing keyword belonging to the modal step.
    if any(line.strip() for line in lines[end_index + 1:]):  # Require the modal step to be the final nonblank model section.
        raise ValueError("Unexpected nonblank records follow the final perturbation step.")  # Reject an unrecognized source layout instead of silently discarding content.
    return start_index, end_index  # Return the inclusive source range occupied by the original modal step.
def format_nset(node_ids: Iterable[int], width: int = 16) -> list[str]:  # Format deterministic node-set records with a bounded number of identifiers per line.
    ordered = list(node_ids)  # Materialize the already validated deterministic node sequence.
    return [", ".join(str(node_id) for node_id in ordered[index:index + width]) + "\n" for index in range(0, len(ordered), width)]  # Emit comma-separated CalculiX node-set lines.
def build_patch_block(variant: str, selected_nodes: list[int], new_nodes: list[int], roots: int) -> list[str]:  # Build the complete target-blind model-data and modal-output replacement block.
    set_name = f"N_HUMAN_{variant}_ROT"  # Create a unique descriptive CalculiX node-set name for the selected legacy passage masters.
    block: list[str] = []  # Accumulate generated lines in deterministic order.
    block.append("** -----------------------------------------------------------------------------\n")  # Open the reconstruction annotation block.
    block.append(f"** TARGET-BLIND AGENT-ULTRA-S10 E3 VARIANT {variant}. NOT human APDL. frequency_reproduced=false.\n")  # Identify the exact preregistered E3 hypothesis without claiming an undisclosed human process.
    block.append("** The only physical change emulates CERIG,master,translation-only-rope-node,ALL instead of UXYZ.\n")  # State the sole legacy command error being reconstructed.
    block.append("** No spring, no added mass, no material change, no prestress change, and no target frequency was used.\n")  # Bound the interpretation of the daughter model.
    block.append("** Inactive rope-node rotations are represented as zero, so master ROTX, ROTY, and ROTZ are removed without fitted springs.\n")  # State the CalculiX equivalent of the old ALL-to-translation-node operation.
    block.append("** Track energy statement: Delta U_T = 0.5*sum(k_theta_j*theta_j^2); E3 tests the rigid-limit operator generated by the wrong ALL option.\n")  # Tie the discrete operation to the Track torsional-energy equation without fitting a finite stiffness.
    block.append("** -----------------------------------------------------------------------------\n")  # Close the annotation header.
    block.append(f"*NSET, NSET={set_name}\n")  # Declare the exact selected legacy-master node set.
    block.extend(format_nset(selected_nodes))  # Emit every selected node identity in deterministic mapping order.
    if new_nodes:  # Add a boundary block only when at least one selected ROTX was not already fixed in the parent.
        new_set_name = f"N_HUMAN_{variant}_ROT_NEW"  # Create a second set containing only newly constrained passage-master identities.
        block.append(f"*NSET, NSET={new_set_name}\n")  # Declare the newly constrained subset.
        block.extend(format_nset(new_nodes))  # Emit every newly constrained node identity.
        block.append("*BOUNDARY\n")  # Open the CalculiX boundary-condition block.
        block.append(f"{new_set_name}, 4, 6, 0.0\n")  # Remove all three master rotations, matching the inactive rotational DOFs of the translation-only rope slave under CERIG ALL.
    block.append("*NSET, NSET=N_HUMAN_OBS\n")  # Declare the frozen fifty-node observation set used by every comparison.
    block.extend(format_nset(OBSERVATION_NODES))  # Emit all common observation node identities.
    block.append("*STEP, PERTURBATION\n")  # Start the frozen-tangent eigenvalue extraction step.
    block.append("*FREQUENCY\n")  # Request a standard CalculiX frequency extraction.
    block.append(f"{roots}\n")  # Extract enough roots to follow branch crossings and spectral reordering.
    block.append("*NODE FILE, NSET=N_HUMAN_OBS, OUTPUT=2D\n")  # Restrict the FRD field to the common observation nodes while retaining all three translations.
    block.append("U\n")  # Request translational modal displacement output.
    block.append("*END STEP\n")  # Close the perturbation step.
    return block  # Return the complete deterministic generated block.
def write_mapping_csv(path: Path, mapping_rows: list[dict[str, object]], selected_nodes: set[int]) -> None:  # Write the complete APDL-to-C3 coordinate mapping and variant membership ledger.
    with path.open("w", encoding="utf-8", newline="") as stream:  # Open the mapping ledger with deterministic UTF-8 CSV handling.
        writer = csv.writer(stream)  # Create a standard-library CSV writer.
        writer.writerow(["apdl_master", "c3_node", "x_mm", "y_mm", "z_mm", "all_count", "uxyz_count", "profile", "selected_for_variant"])  # Write the explicit mapping schema.
        for row in mapping_rows:  # Preserve the legacy source order for every master mapping row.
            writer.writerow([row["apdl_master"], row["c3_node"], f"{float(row['x_mm']):.6f}", f"{float(row['y_mm']):.6f}", f"{float(row['z_mm']):.6f}", row["all_count"], row["uxyz_count"], repr(row["profile"]), int(int(row["c3_node"]) in selected_nodes)])  # Record geometry, CERIG profile, and variant selection.
def main() -> None:  # Execute validation, exact coordinate mapping, direct C3 patching, and receipt generation.
    args = parse_arguments()  # Read all explicit construction controls.
    if args.roots < 20 or args.roots > 100:  # Keep the branch-tracking spectrum large enough and computationally bounded.
        raise ValueError("The modal root count must be between 20 and 100.")  # Reject an under-resolved or excessive extraction request.
    source_bytes = args.source.read_bytes()  # Read the exact parent byte stream once for identity verification.
    source_sha256 = sha256_bytes(source_bytes)  # Compute the actual parent digest.
    if source_sha256 != args.expected_source_sha256.lower():  # Require the caller-provided immutable parent identity.
        raise ValueError(f"Source SHA-256 mismatch: expected {args.expected_source_sha256}, got {source_sha256}.")  # Reject source drift before any modeling operation.
    legacy_bytes = args.legacy_apdl.read_bytes()  # Read the locked S10 include once for identity verification.
    legacy_sha256 = sha256_bytes(legacy_bytes)  # Compute the actual legacy APDL digest.
    if legacy_sha256 != LEGACY_APDL_SHA256:  # Require the recovered immutable APDL source identity.
        raise ValueError(f"Legacy APDL SHA-256 mismatch: expected {LEGACY_APDL_SHA256}, got {legacy_sha256}.")  # Reject a different or edited S10 include.
    source_text = source_bytes.decode("utf-8")  # Decode the validated ASCII-compatible C3 deck.
    source_lines = source_text.splitlines(keepends=True)  # Preserve every original line ending in the unchanged source prefix.
    c3_coordinates, element_ids = parse_c3_entities(source_lines)  # Read complete parent geometry and element identities.
    if len(c3_coordinates) != args.expected_parent_nodes:  # Preserve the explicitly stated parent node topology.
        raise ValueError(f"Parent node count mismatch: expected {args.expected_parent_nodes}, got {len(c3_coordinates)}.")  # Reject topology drift.
    if len(element_ids) != args.expected_parent_elements:  # Preserve the explicitly stated parent element topology.
        raise ValueError(f"Parent element count mismatch: expected {args.expected_parent_elements}, got {len(element_ids)}.")  # Reject topology drift.
    apdl_coordinates, master_order, master_profiles = parse_legacy_apdl(legacy_bytes.decode("utf-8"))  # Recover exact legacy master geometry and CERIG profiles.
    mapping_rows = map_legacy_masters_to_c3(c3_coordinates, apdl_coordinates, master_order, master_profiles)  # Coordinate-match every legacy master to the exact C3 topology.
    selected_rows = select_variant_rows(args.variant, mapping_rows)  # Select the preregistered E3 physical scope.
    selected_nodes = [int(row["c3_node"]) for row in selected_rows]  # Preserve deterministic selected C3 master order.
    if len(selected_nodes) != VARIANT_EXPECTED_COUNTS[args.variant]:  # Require the exact preregistered constraint count.
        raise ValueError(f"Variant {args.variant} expected {VARIANT_EXPECTED_COUNTS[args.variant]} nodes, got {len(selected_nodes)}.")  # Reject incomplete or expanded scope.
    if len(selected_nodes) != len(set(selected_nodes)):  # Require every selected C3 master identity to be unique.
        raise ValueError(f"Variant {args.variant} contains duplicate C3 node identifiers.")  # Reject an ambiguous boundary definition.
    missing_observation = sorted(set(OBSERVATION_NODES) - set(c3_coordinates))  # Identify common observation nodes absent from the exact C3 topology.
    if missing_observation:  # Require the common branch-tracking field to exist in every daughter.
        raise ValueError(f"Observation nodes missing from C3: {missing_observation}.")  # Reject an invalid comparison field.
    existing_boundaries = parse_existing_numeric_boundaries(source_lines)  # Read every existing explicit numeric parent constraint.
    preexisting_rotx_nodes = [node_id for node_id in selected_nodes if all((node_id, dof) in existing_boundaries for dof in (4, 5, 6))]  # Identify passage masters whose three rotations are already fixed in C3.
    new_rotx_nodes = [node_id for node_id in selected_nodes if not all((node_id, dof) in existing_boundaries for dof in (4, 5, 6))]  # Identify passage masters receiving at least one new rotational constraint.
    modal_start, modal_end = find_final_perturbation_step(source_lines)  # Locate the sole final modal step for controlled replacement.
    generated_block = build_patch_block(args.variant, selected_nodes, new_rotx_nodes, args.roots)  # Generate the exact E3 daughter block.
    output_lines = source_lines[:modal_start] + generated_block  # Preserve every parent byte before the modal step and append only the preregistered operation.
    output_text = "".join(output_lines)  # Assemble the complete daughter input deck.
    args.output.parent.mkdir(parents=True, exist_ok=True)  # Create the requested output directory when needed.
    args.output.write_text(output_text, encoding="utf-8", newline="")  # Write the complete UTF-8 daughter deck without platform newline translation.
    output_bytes = args.output.read_bytes()  # Read the emitted bytes for final identity recording.
    output_sha256 = sha256_bytes(output_bytes)  # Compute the exact daughter digest.
    output_coordinates, output_element_ids = parse_c3_entities(output_text.splitlines(keepends=True))  # Verify that the direct constraint operation did not change topology.
    if output_coordinates != c3_coordinates or output_element_ids != element_ids:  # Require exact node coordinates and element identity preservation.
        raise ValueError("The emitted daughter changed parent coordinates or element identities.")  # Reject any unintended topology mutation.
    mapping_path = args.output.with_suffix(args.output.suffix + ".mapping.csv")  # Derive an auditable coordinate-mapping ledger path adjacent to the daughter deck.
    write_mapping_csv(mapping_path, mapping_rows, set(selected_nodes))  # Write the complete exact legacy-master mapping and variant membership.
    profile_counts = Counter(repr(row["profile"]) for row in mapping_rows)  # Count the recovered legacy CERIG master profiles for audit closure.
    receipt = {"schema_version": 2, "variant": args.variant, "model": "exact frozen C3 entity model", "target_blind": True, "attachment_target_frequencies_loaded": False, "frequency_reproduced": False, "back_tuned": False, "low_dimensional": False, "human_apdl": False, "source_kind": "agent_ultra_s10_section_shear", "not_attach_ta1": True, "not_undisclosed_human_apdl": True, "track_equation": "Delta U_T = 0.5*sum_j(k_theta_j*theta_j^2); E3 rigid-limit CERIG-ALL-to-translation-node hypothesis", "human_operation": "remove passage-master ROTX/ROTY/ROTZ as a rigid-limit stand-in for CERIG ALL to a translation-only slave (agent Ultra S10 map, not human APDL)", "physical_changes": ["passage-master ROTX ROTY ROTZ removed as the rigid-limit equivalent of inactive slave rotations"], "forbidden_changes_confirmed_absent": ["added spring", "added mass", "material change", "section change", "prestress change", "coordinate change", "connectivity change"], "source": str(args.source), "source_sha256": source_sha256, "expected_source_sha256": args.expected_source_sha256.lower(), "legacy_apdl": str(args.legacy_apdl), "legacy_apdl_sha256": legacy_sha256, "legacy_mapping_method": "unique exact global-coordinate match rounded to 1e-6 mm", "output": str(args.output), "output_sha256": output_sha256, "mapping_csv": str(mapping_path), "mapping_csv_sha256": sha256_bytes(mapping_path.read_bytes()), "parent_nodes": len(c3_coordinates), "parent_elements": len(element_ids), "legacy_cerig_master_count": len(mapping_rows), "legacy_cerig_profile_counts": dict(sorted(profile_counts.items())), "selected_rotation_nodes": selected_nodes, "selected_rotation_node_count": len(selected_nodes), "preexisting_all_rotation_nodes": preexisting_rotx_nodes, "preexisting_all_rotation_node_count": len(preexisting_rotx_nodes), "new_all_rotation_nodes": new_rotx_nodes, "new_all_rotation_node_count": len(new_rotx_nodes), "observation_nodes": OBSERVATION_NODES, "observation_node_count": len(OBSERVATION_NODES), "modal_roots": args.roots, "source_modal_step_start_line_1based": modal_start + 1, "source_modal_step_end_line_1based": modal_end + 1}  # Record the complete construction identity and evidence boundary.
    receipt_path = args.output.with_suffix(args.output.suffix + ".receipt.json")  # Derive a receipt path adjacent to the emitted daughter input.
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write the deterministic machine-readable construction receipt.
    print(json.dumps({"variant": args.variant, "output": str(args.output), "output_sha256": output_sha256, "legacy_cerig_master_count": len(mapping_rows), "selected_rotation_node_count": len(selected_nodes), "preexisting_all_rotation_node_count": len(preexisting_rotx_nodes), "new_all_rotation_node_count": len(new_rotx_nodes), "roots": args.roots, "target_blind": True, "frequency_reproduced": False, "human_apdl": False, "source_kind": "agent_ultra_s10_section_shear", "not_attach_ta1": True}, ensure_ascii=False, sort_keys=True))  # Emit a compact machine-readable execution summary.
if __name__ == "__main__":  # Run the construction only when invoked as a script.
    main()  # Execute the validated direct-C3 E3 rotation variant generator.
