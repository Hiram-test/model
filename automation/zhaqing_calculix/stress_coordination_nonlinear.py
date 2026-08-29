#!/usr/bin/env python3  # Provide fixed-L0 co-rotational suspension re-equilibration while the retained bridge remains a linear CalculiX substructure.
import hashlib  # Bind nonlinear iteration receipts and generated solver decks to their exact byte streams.
import json  # Publish deterministic machine-readable topology, iteration, convergence, and removed-member evidence.
import math  # Evaluate three-dimensional truss geometry, force, tangent, residual, and convergence quantities.
import re  # Validate generated native-solver basenames before they reach the shared calculation directory.
from pathlib import Path  # Keep every nonlinear evidence path explicit and caller-controlled.


NONLINEAR_SCHEMA = "zhaqing-fixed-l0-corotational-v1"  # Freeze the reusable nonlinear suspension implementation contract consumed by the case runner.
ITERATION_SCHEMA = "zhaqing-fixed-l0-coupled-iteration-v1"  # Freeze the per-iteration retained/suspension Newton receipt schema.
REMOVED_GHOST_SCHEMA = "zhaqing-removed-suspension-ghost-v1"  # Freeze the no-response metadata contract for source hanger e1033 after LC08 deletion.
SUSPENSION_GROUPS = ("MAIN_CABLES", "HANGERS")  # Restrict this solver to the evidenced vertical axial suspension subsystem.
DEFAULT_RETAINED_GROUPS = ("DECK_SHELLS", "CROSSBEAMS", "LONG_GIRDERS", "TOWER_COLUMNS", "TOWER_TOP_BEAMS", "DECK_ACCESSORY_MASS")  # Preserve the canonical retained deck-and-tower partition when the adapter does not publish its tuple.
STABLE_MODE_SLOTS_PER_PLANE = 81  # Reserve the nominal eighty-one interface degrees on each signed suspension plane.
NOMINAL_MODE_COUNT = 162  # Require the reviewed intact two-plane condensation population.
LC08_MODE_COUNT = 159  # Require the reviewed e1033-loss population with three positive-plane slots intentionally unused.
MINIMUM_CHORD_MM = 1.0e-6  # Reject collapsed axial members before direction, strain, or geometric stiffness becomes undefined.
DEFAULT_INTERNAL_RESIDUAL_TOL_N = 1.0e-4  # Require tight free-suspension nodal equilibrium at every inner Newton solution.
DEFAULT_COUPLING_RESIDUAL_TOL_N = 1.0e-2  # Require the actual nonlinear interface action to match the retained Newton action within one hundredth newton.
DEFAULT_INTERFACE_CORRECTION_TOL_MM = 1.0e-6  # Require the retained-interface Newton correction to close at sub-micrometre scale.
DEFAULT_MAXIMUM_INTERNAL_ITERATIONS = 60  # Bound every fixed-interface suspension Newton solve explicitly.
DEFAULT_MAXIMUM_OUTER_ITERATIONS = 30  # Bound every retained/suspension coupled Newton solve explicitly.
DEFAULT_LINE_SEARCH_STEPS = 18  # Bound tension-preserving inner Newton backtracking without accepting a stalled step.
DEFAULT_MAXIMUM_DISPLACEMENT_MM = 5000.0  # Fail closed before an obviously divergent trial geometry reaches a tangent or response artifact.


def _sha256_path(path: Path) -> str:  # Compute one exact file identity without relying on an adapter utility that may be unavailable during isolated tests.
    digest = hashlib.sha256()  # Allocate a fresh SHA-256 state for this evidence file.
    with path.open("rb") as stream:  # Read bytes directly so line endings and numeric spelling remain part of provenance.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Bound memory while preserving exact byte order.
            digest.update(chunk)  # Extend the immutable identity with the next exact block.
    return digest.hexdigest()  # Return the lowercase deterministic digest.


def _write_json(path: Path, payload: dict) -> str:  # Persist one deterministic UTF-8 receipt and return its exact byte identity.
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Use stable indentation and one final newline for reproducible evidence.
    return _sha256_path(path)  # Bind the caller to the exact published receipt bytes.


def _zero(adapter, rows: int, columns: int) -> list[list[float]]:  # Allocate a dense matrix through the audited adapter algebra when available.
    return adapter.zero_matrix(rows, columns) if hasattr(adapter, "zero_matrix") else [[0.0] * columns for _row in range(rows)]  # Preserve independent rows and standard-library-only execution.


def _norm(vector) -> float:  # Evaluate one Euclidean force, displacement, or action-remainder magnitude.
    return math.sqrt(math.fsum(float(value) * float(value) for value in vector))  # Use compensated accumulation for deterministic small residuals.


def _matrix_vector(matrix: list[list[float]], vector: list[float]) -> list[float]:  # Multiply one dense physical operator by one ordered degree vector.
    return [math.fsum(coefficient * value for coefficient, value in zip(row, vector)) for row in matrix]  # Evaluate every row without external numerical packages.


def _add_action(actions: dict[int, list[float]], node: int, vector) -> None:  # Accumulate one three-dimensional nodal action under the suspension-on-node sign convention.
    target = actions.setdefault(node, [0.0, 0.0, 0.0])  # Initialize the exact physical source node on first contribution.
    for axis in range(3):  # Resolve every global bridge direction independently.
        target[axis] += float(vector[axis])  # Add the signed force component without rounding or aggregation loss.


def _axial_tensor(stress_mpa: float, unit: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:  # Convert one total axial stress and current direction to the canonical global tensor order.
    ux, uy, uz = unit  # Unpack the current co-rotated direction cosines once.
    return (stress_mpa * ux * ux, stress_mpa * uy * uy, stress_mpa * uz * uz, stress_mpa * ux * uy, stress_mpa * ux * uz, stress_mpa * uy * uz)  # Return SXX,SYY,SZZ,SXY,SXZ,SYZ.


def _coordinate_plus(point: tuple[float, float, float], displacement) -> tuple[float, float, float]:  # Apply one physical translation to one nominal-F3 coordinate.
    return tuple(float(point[axis]) + float(displacement[axis]) for axis in range(3))  # Preserve the global right-handed coordinate convention.


def _validate_finite_vector(vector, label: str) -> tuple[float, float, float]:  # Normalize one caller displacement while rejecting missing, nonfinite, or malformed data.
    if not isinstance(vector, (tuple, list)) or len(vector) != 3:  # Require exactly three Cartesian translation components.
        raise RuntimeError(f"{label} must contain exactly three displacement components")  # Stop before silently filling or truncating a physical degree.
    converted = tuple(float(value) for value in vector)  # Convert each supplied scalar exactly once.
    if any(not math.isfinite(value) for value in converted):  # Refuse NaN or infinity before geometry construction.
        raise RuntimeError(f"{label} contains a nonfinite displacement")  # Identify the invalid physical vector directly.
    return converted  # Return the accepted immutable Cartesian tuple.


def build_fixed_l0_context(adapter, base_text: str, coordinated_nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], element_states: dict[int, dict], removed_element_ids: set[int] | None = None, damage_contract: dict | None = None) -> dict:  # Derive one immutable active suspension topology and fixed-fabrication constitutive context from LC01/F3 evidence.
    source_index = {int(element_id): (group_name, [int(value) for value in connectivity[:2]]) for group_name in SUSPENSION_GROUPS for element_id, connectivity in groups.get(group_name, [])}  # Index every nominal suspension member by stable source id, group, and ordered endpoints.
    if len(source_index) != NOMINAL_MODE_COUNT + 84:  # Require the reviewed 246-member nominal suspension inventory before nonlinear case reuse.
        raise RuntimeError(f"fixed-L0 context expected 246 suspension members, found {len(source_index)}")  # Reject a topology revision hidden behind compatible group names.
    removed = set(removed_element_ids or set())  # Freeze the optional topology deletion without mutating the caller's set.
    if any(not isinstance(element_id, int) or isinstance(element_id, bool) for element_id in removed):  # Require exact integer source identities.
        raise RuntimeError("removed suspension selection contains a noninteger source id")  # Stop before set coercion can rename a physical member.
    if not removed.issubset(source_index):  # Require every deletion to reference the immutable nominal suspension population.
        raise RuntimeError(f"removed suspension ids are absent from LC01: {sorted(removed - set(source_index))}")  # Expose the invalid source identities.
    if removed and removed != {1033}:  # Keep the reviewed nonlinear deletion exception narrowly bound to LC08 hanger e1033.
        raise RuntimeError(f"only reviewed LC08 source hanger e1033 may be removed, received {sorted(removed)}")  # Refuse an unaudited damage scenario.
    if removed:  # Validate the exact reviewed LC08 stable member identity and explicit damage declaration.
        expected_damage = source_index.get(1033) == ("HANGERS", [294, 638])  # Cross-check immutable group and ordered connectivity.
        contract_ok = isinstance(damage_contract, dict) and damage_contract.get("schema") == "zhaqing-static-alternate-path-damage-v1" and damage_contract.get("caseId") == "LC08"  # Require the reviewed alternate-path schema and case binding.
        if not expected_damage or not contract_ok:  # Refuse deletion without both source topology and event evidence.
            raise RuntimeError("LC08 nonlinear deletion requires HANGERS e1033=(294,638) and the reviewed damage contract")  # Stop before bypassing intact response semantics.
    elif damage_contract is not None:  # Refuse damage metadata on the intact topology.
        raise RuntimeError("damage contract supplied without a removed suspension member")  # Keep nominal and damaged evidence paths distinct.
    normalized_nodes = {int(node): tuple(float(value) for value in point) for node, point in coordinated_nodes.items()}  # Freeze nominal-F3 coordinates without defaults.
    if any(len(point) != 3 or any(not math.isfinite(value) for value in point) for point in normalized_nodes.values()):  # Require finite complete Cartesian geometry.
        raise RuntimeError("coordinated F3 node coordinates are malformed or nonfinite")  # Stop before deriving lengths or plane membership.
    normalized_states = {int(element_id): dict(record) for element_id, record in element_states.items()}  # Normalize persisted JSON source keys while preserving every record.
    if set(normalized_states) != set(source_index):  # Require fixed-L0 evidence for every nominal source member including the later removed ghost.
        raise RuntimeError("fixed-L0 element-state coverage differs from the nominal suspension topology")  # Stop before backfilling constitutive data.
    retained_group_names = tuple(getattr(adapter, "PRIMARY_RETAINED_GROUPS", DEFAULT_RETAINED_GROUPS))  # Reuse the canonical retained partition published by the loaded adapter.
    retained_nodes = {int(node) for group_name in retained_group_names for _element_id, connectivity in groups.get(group_name, []) for node in connectivity}  # Derive the complete linear CalculiX node population from source topology.
    active_ids = set(source_index) - removed  # Preserve every survivor source id without renumbering, reconnection, or length retargeting.
    active_nodes = {node for element_id in active_ids for node in source_index[element_id][1]}  # Derive active suspension nodes after deletion so removed-only interfaces produce no false modes.
    nsets = adapter.parse_nsets(base_text)  # Recover physical cable anchors through the same audited source parser as canonical P3.
    anchor_nodes = set(int(node) for node in nsets.get("MAIN_CABLE_ANCHORS", set())) & active_nodes  # Restrict prescribed anchor coordinates to active cable endpoints.
    interface_nodes = (retained_nodes & active_nodes) - anchor_nodes  # Define shared deck-hanger and saddle nodes as retained nonlinear interfaces.
    internal_nodes = active_nodes - anchor_nodes - interface_nodes  # Define cable-only free coordinates eliminated by nonlinear inner equilibrium.
    if not anchor_nodes or not interface_nodes or not internal_nodes:  # Require all physical substructure partitions explicitly.
        raise RuntimeError("fixed-L0 suspension context requires nonempty anchor, interface, and internal partitions")  # Stop before an unanchored or fully retained condensation.
    if any(abs(normalized_nodes[node][1]) <= 1.0e-12 for node in active_nodes):  # Require unique signed-plane membership from F3 coordinates.
        raise RuntimeError("active suspension node lies on the y=0 plane-selection boundary")  # Refuse arbitrary plane duplication or omission.
    element_data: dict[int, dict] = {}  # Store immutable fixed-fabrication data required by every nonlinear trial.
    for element_id in sorted(source_index):  # Validate all nominal members so a removed ghost retains trustworthy pre-loss metadata.
        group_name, connectivity = source_index[element_id]  # Recover stable source ownership and ordered endpoints.
        record = normalized_states[element_id]  # Recover the unique persisted F3 constitutive record.
        if record.get("group") != group_name or [int(value) for value in record.get("nodeIds", [])] != connectivity:  # Require topology identity across source and equilibrium-state evidence.
            raise RuntimeError(f"fixed-L0 topology mismatch for suspension element {element_id}")  # Stop before using state from another member.
        node_a, node_b = connectivity  # Unpack ordered physical endpoints.
        base_chord = tuple(normalized_nodes[node_b][axis] - normalized_nodes[node_a][axis] for axis in range(3))  # Recompute the nominal-F3 chord independently.
        base_length = _norm(base_chord)  # Recover the geometric equilibrium length in millimetres.
        l0 = float(record.get("unstressedLengthMm", float("nan")))  # Recover the immutable fabricated material length.
        published_length = float(record.get("equilibriumLengthMm", float("nan")))  # Recover the redundant nominal-F3 chord publication.
        axial_rigidity = float(record.get("materialTangentNPerMm", float("nan"))) * published_length  # Recover EA from the audited nominal EA/L publication without introducing a second modulus.
        area = float(adapter.MAIN_CABLE_AREA_MM2 if group_name == "MAIN_CABLES" else adapter.HANGER_AREA_MM2)  # Select the frozen physical axial area from the bound adapter.
        if not all(math.isfinite(value) and value > 0.0 for value in (base_length, l0, published_length, axial_rigidity, area)):  # Reject absent, nonpositive, or nonfinite constitutive scalars.
            raise RuntimeError(f"invalid fixed-L0 constitutive data for suspension element {element_id}")  # Stop before nonlinear force recovery.
        if abs(base_length - published_length) > 1.0e-8 * max(base_length, 1.0):  # Bind the material state to the exact coordinated geometry.
            raise RuntimeError(f"nominal-F3 length mismatch for suspension element {element_id}")  # Stop before combining different model revisions.
        base_unit = tuple(value / base_length for value in base_chord)  # Normalize the accepted nominal direction.
        base_force = float(record.get("axialForceN", float("nan")))  # Recover the pre-loss nominal tensile force for increment evidence.
        base_stress = float(record.get("axialStressMPa", float("nan")))  # Recover the pre-loss nominal axial stress for tensor composition.
        constitutive_force = axial_rigidity / l0 * (base_length - l0)  # Recompute the F3 force from the immutable L0 law used by every later case.
        if not math.isfinite(base_force) or base_force <= 0.0 or not math.isfinite(base_stress) or base_stress <= 0.0:  # Require a positive accepted nominal tension state.
            raise RuntimeError(f"invalid nominal suspension force or stress for element {element_id}")  # Stop before defining a relative increment.
        if abs(constitutive_force - base_force) > 1.0e-8 * max(abs(base_force), 1.0):  # Prove the published state is compatible with N=EA/L0*(L-L0).
            raise RuntimeError(f"fixed-L0 constitutive closure failed for suspension element {element_id}")  # Reject silent prestress retargeting.
        weight = area * float(adapter.STEEL_DENSITY_T_MM3) * float(adapter.GRAVITY_MM_S2) * published_length  # Freeze the complete nominal element self-weight as a constant case load.
        element_data[element_id] = {"elementId": element_id, "group": group_name, "nodeIds": connectivity, "areaMm2": area, "unstressedLengthMm": l0, "axialRigidityN": axial_rigidity, "baseLengthMm": published_length, "baseForceN": base_force, "baseStressMPa": base_stress, "baseUnit": base_unit, "baseTensorMPa": _axial_tensor(base_stress, base_unit), "constantSelfWeightN": weight}  # Preserve fixed fabrication, nominal reference, and constant gravity without mutable solver state.
    planes: list[dict] = []  # Build two noncrossing signed active suspension graphs.
    for sign in (1, -1):  # Preserve canonical positive-plane then negative-plane ordering.
        plane_nodes = {node for node in active_nodes if (normalized_nodes[node][1] > 0.0) == (sign > 0)}  # Select active nodes by immutable nominal transverse sign.
        plane_elements = [element_id for element_id in sorted(active_ids) if all(node in plane_nodes for node in source_index[element_id][1])]  # Select every within-plane survivor once.
        planes.append({"sign": sign, "nodes": plane_nodes, "elements": plane_elements, "interfaceNodes": interface_nodes & plane_nodes, "internalNodes": internal_nodes & plane_nodes, "anchorNodes": anchor_nodes & plane_nodes})  # Publish the exact per-plane active partition.
    if set().union(*(plane["nodes"] for plane in planes)) != active_nodes or sum(len(plane["elements"]) for plane in planes) != len(active_ids):  # Require complete nonoverlapping active coverage.
        raise RuntimeError("signed nonlinear suspension planes do not cover the active topology exactly once")  # Stop before dropping a member or cross-plane coupling.
    expected_modes = LC08_MODE_COUNT if removed else NOMINAL_MODE_COUNT  # Select the reviewed interface-degree count for intact or e1033-loss topology.
    actual_modes = sum(3 * len(plane["interfaceNodes"]) for plane in planes)  # Count the exact Cartesian retained interface population.
    if actual_modes != expected_modes:  # Refuse a superficially similar but unreviewed active topology.
        raise RuntimeError(f"nonlinear suspension topology expected {expected_modes} interface modes, found {actual_modes}")  # Expose the decisive mode-count drift.
    removed_ghosts = {element_id: {"schema": REMOVED_GHOST_SCHEMA, "elementId": element_id, "group": source_index[element_id][0], "nodeIds": source_index[element_id][1], "status": "REMOVED_ACTIVE_MECHANICS_EXCLUDED_STABLE_GHOST_PUBLISHED", "nominalF3BaseForceN": element_data[element_id]["baseForceN"], "nominalF3BaseStressMPa": element_data[element_id]["baseStressMPa"], "fixedUnstressedLengthMm": element_data[element_id]["unstressedLengthMm"], "stiffnessIncluded": False, "selfWeightIncluded": False, "zeroTotalResponseTensorPublished": True, "sourceIdReserved": True} for element_id in sorted(removed)}  # Preserve auditable nominal-F3 identity while the separate damage event records the actual pre-loss case state and this stable ghost remains outside active mechanics.
    normalized_damage = dict(damage_contract) if damage_contract is not None else None  # Preserve the caller's already reviewed event receipt without inventing fields.
    return {"schema": NONLINEAR_SCHEMA, "adapter": adapter, "baseText": base_text, "baseCoordinatesMm": normalized_nodes, "elementData": element_data, "sourceElementIndex": source_index, "activeElementIds": active_ids, "removedElementIds": removed, "removedGhosts": removed_ghosts, "retainedNodes": retained_nodes, "suspensionNodes": active_nodes, "interfaceNodes": interface_nodes, "internalNodes": internal_nodes, "anchorNodes": anchor_nodes, "planes": planes, "damageContract": normalized_damage, "receipt": {"schema": NONLINEAR_SCHEMA, "kinematics": "fixed-L0 co-rotational three-dimensional axial suspension", "retainedStructure": "linear CalculiX deck-and-tower model re-used at every outer Newton iteration", "suspensionMaterialLaw": "N=EA/L0*(L-L0)", "tangentLaw": "EA/L0*n*nT + N/L*(I-n*nT)", "selfWeightLaw": "constant nominal-F3 half-element nodal loads on active members", "nominalElementCount": len(source_index), "activeElementCount": len(active_ids), "removedElementIds": sorted(removed), "activeSuspensionNodeCount": len(active_nodes), "interfaceNodeCount": len(interface_nodes), "internalNodeCount": len(internal_nodes), "anchorNodeCount": len(anchor_nodes), "activeInterfaceDofCount": actual_modes, "expectedInterfaceDofCount": expected_modes, "survivorSourceIdsPreserved": True, "survivorConnectivityRetargeted": False, "survivorUnstressedLengthsRetargeted": False}}  # Return complete immutable mechanics and topology evidence for reusable solves.


def _element_response(adapter, element: dict, coordinates: dict[int, tuple[float, float, float]]) -> dict:  # Evaluate one fixed-L0 co-rotational member force, stress, direction, and exact tangent at current geometry.
    node_a, node_b = element["nodeIds"]  # Recover ordered source endpoints.
    chord = tuple(coordinates[node_b][axis] - coordinates[node_a][axis] for axis in range(3))  # Form the current physical chord from accepted coordinates.
    length = _norm(chord)  # Evaluate current length in millimetres.
    if not math.isfinite(length) or length <= MINIMUM_CHORD_MM:  # Reject collapse before normalization or strain evaluation.
        raise RuntimeError(f"suspension element {element['elementId']} has invalid current length {length}")  # Identify the failed stable source member.
    unit = tuple(value / length for value in chord)  # Normalize the co-rotated current direction.
    force = float(element["axialRigidityN"]) / float(element["unstressedLengthMm"]) * (length - float(element["unstressedLengthMm"]))  # Apply the immutable linear-elastic material-length law.
    stress = force / float(element["areaMm2"])  # Convert axial force to signed engineering stress in MPa.
    material = float(element["axialRigidityN"]) / float(element["unstressedLengthMm"])  # Evaluate dN/dL for the fixed-L0 constitutive law.
    geometric = force / length  # Evaluate current initial-force stiffness per current chord length.
    tangent = _zero(adapter, 3, 3)  # Allocate the exact three-dimensional material-plus-geometric block.
    for row in range(3):  # Assemble each global tangent row.
        for column in range(3):  # Assemble each global tangent column.
            axial = unit[row] * unit[column]  # Form one axial projector component.
            transverse = (1.0 if row == column else 0.0) - axial  # Form the orthogonal geometric-stiffness projector.
            tangent[row][column] = material * axial + geometric * transverse  # Combine fixed-L0 material and current-force geometric stiffness.
    return {"elementId": element["elementId"], "group": element["group"], "nodeIds": list(element["nodeIds"]), "lengthMm": length, "unit": unit, "axialForceN": force, "axialStressMPa": stress, "tangentNPerMm": tangent, "totalTensorMPa": _axial_tensor(stress, unit), "constantSelfWeightN": element["constantSelfWeightN"]}  # Return complete current member mechanics without mutating fixed data.


def _assemble_plane_response(context: dict, plane: dict, coordinates: dict[int, tuple[float, float, float]], assemble_internal_tangent: bool = True) -> dict:  # Assemble actual suspension actions and the positive internal Newton tangent for one signed plane.
    adapter = context["adapter"]  # Recover the caller-loaded audited adapter algebra.
    internal_dofs = [(node, axis) for node in sorted(plane["internalNodes"]) for axis in range(3)]  # Freeze deterministic inner Newton degree ordering.
    internal_index = {degree: index for index, degree in enumerate(internal_dofs)}  # Map each free coordinate to one dense tangent row and column.
    stiffness = _zero(adapter, len(internal_dofs), len(internal_dofs)) if assemble_internal_tangent else []  # Allocate only when a Newton factor is required.
    actions = {node: [0.0, 0.0, 0.0] for node in plane["nodes"]}  # Initialize actual element-plus-weight action at every active plane node.
    self_weight_actions = {node: [0.0, 0.0, 0.0] for node in plane["nodes"]}  # Preserve constant gravity contributions independently.
    element_responses: dict[int, dict] = {}  # Store every survivor's current force, stress, direction, and tangent.
    minimum_stress = float("inf")  # Track the least active tension for fail-closed line search and final Gates.
    for element_id in plane["elements"]:  # Visit every active signed-plane member exactly once.
        element = context["elementData"][element_id]  # Recover immutable fixed-L0 and nominal evidence.
        response = _element_response(adapter, element, coordinates)  # Evaluate current co-rotational mechanics.
        element_responses[element_id] = response  # Preserve the response under its stable source id.
        minimum_stress = min(minimum_stress, float(response["axialStressMPa"]))  # Update the active tension floor.
        node_a, node_b = element["nodeIds"]  # Recover ordered endpoints for action and tangent assembly.
        force_a = tuple(float(response["axialForceN"]) * component for component in response["unit"])  # Form the tensile action pulling endpoint A toward B.
        _add_action(actions, node_a, force_a)  # Assemble current axial action at endpoint A.
        _add_action(actions, node_b, tuple(-value for value in force_a))  # Assemble equal-and-opposite axial action at endpoint B.
        half_weight = (0.0, 0.0, -0.5 * float(response["constantSelfWeightN"]))  # Apply the frozen nominal half-element gravity convention.
        _add_action(actions, node_a, half_weight)  # Apply constant element gravity at endpoint A.
        _add_action(actions, node_b, half_weight)  # Apply constant element gravity at endpoint B.
        _add_action(self_weight_actions, node_a, half_weight)  # Preserve endpoint-A gravity for interface and mass receipts.
        _add_action(self_weight_actions, node_b, half_weight)  # Preserve endpoint-B gravity for interface and mass receipts.
        if assemble_internal_tangent:  # Assemble the standard positive tangent only for free internal rows and columns.
            tangent = response["tangentNPerMm"]  # Recover the exact current three-by-three element block.
            for row_node, row_sign in ((node_a, 1.0), (node_b, -1.0)):  # Visit both standard truss row blocks.
                for column_node, column_sign in ((node_a, 1.0), (node_b, -1.0)):  # Visit both standard truss column blocks.
                    for row_axis in range(3):  # Resolve each global row component.
                        row_index = internal_index.get((row_node, row_axis))  # Skip fixed interface and anchor rows.
                        if row_index is None:  # Preserve their actions outside the inner solve.
                            continue  # Advance to the next physical row component.
                        for column_axis in range(3):  # Resolve each global column component.
                            column_index = internal_index.get((column_node, column_axis))  # Skip fixed interface and anchor columns.
                            if column_index is not None:  # Assemble only active internal-to-internal stiffness.
                                stiffness[row_index][column_index] += row_sign * column_sign * tangent[row_axis][column_axis]  # Form the positive Newton matrix equal to minus the derivative of actual nodal action.
    internal_residual = max((_norm(actions[node]) for node in plane["internalNodes"]), default=float("inf"))  # Measure the worst physical free-node action imbalance.
    return {"actionsN": actions, "selfWeightActionsN": self_weight_actions, "elementResponses": element_responses, "internalDofs": internal_dofs, "internalTangentNPerMm": stiffness, "maximumInternalResidualN": internal_residual, "minimumAxialStressMPa": minimum_stress}  # Return current physical actions and optional Newton operator.


def _solve_plane_internal(context: dict, plane: dict, interface_displacements: dict[int, tuple[float, float, float]], initial_displacements: dict[int, tuple[float, float, float]] | None, residual_tolerance_n: float, maximum_iterations: int, maximum_line_search_steps: int, maximum_displacement_mm: float) -> dict:  # Re-equilibrate all cable-only coordinates at fixed retained interface coordinates and fixed anchors.
    adapter = context["adapter"]  # Recover audited dense Cholesky algebra and bound tension limit.
    base = context["baseCoordinatesMm"]  # Recover immutable nominal-F3 physical coordinates.
    coordinates = {node: tuple(base[node]) for node in plane["nodes"]}  # Initialize every active plane node at nominal F3.
    for node in plane["interfaceNodes"]:  # Apply the caller's retained translations exactly at shared physical nodes.
        coordinates[node] = _coordinate_plus(base[node], interface_displacements[node])  # Preserve all three retained displacement components.
    for node in plane["internalNodes"]:  # Apply an optional prior accepted nonlinear state as the Newton seed.
        seed = (initial_displacements or {}).get(node, (0.0, 0.0, 0.0))  # Default only a missing seed to nominal F3, never a missing final response.
        coordinates[node] = _coordinate_plus(base[node], _validate_finite_vector(seed, f"internal seed node {node}"))  # Initialize the current free coordinate deterministically.
    for node in plane["anchorNodes"]:  # Enforce the physical fixed-anchor boundary at nominal F3.
        coordinates[node] = tuple(base[node])  # Retain exact zero anchor displacement throughout every trial.
    tension_floor = float(getattr(adapter, "MIN_TENSION_MPA", 0.0))  # Reuse the canonical positive-tension Gate when bound by the caller.
    iterations: list[dict] = []  # Accumulate accepted inner Newton and line-search receipts.
    for iteration in range(maximum_iterations + 1):  # Include the initial residual evaluation before any correction.
        assembled = _assemble_plane_response(context, plane, coordinates, assemble_internal_tangent=True)  # Evaluate actual residual, active tension, and exact current tangent.
        residual = float(assembled["maximumInternalResidualN"])  # Recover the decisive free-node equilibrium norm.
        minimum_stress = float(assembled["minimumAxialStressMPa"])  # Recover the decisive active tension floor.
        if residual <= residual_tolerance_n:  # Accept only a tightly equilibrated fixed-interface suspension state.
            if minimum_stress < tension_floor:  # Fail closed when the converged physical state loses the precommitted minimum tension.
                raise RuntimeError(f"signed plane {plane['sign']} converged with lost tension at inner iteration {iteration}: {minimum_stress} MPa")  # Distinguish a physical final failure from a nonequilibrated Newton seed.
            iterations.append({"iteration": iteration, "maximumInternalResidualN": residual, "minimumAxialStressMPa": minimum_stress, "acceptedStepScale": 0.0, "lineSearchTrials": 0, "status": "CONVERGED"})  # Publish the terminal equilibrium observation.
            displacements = {node: tuple(coordinates[node][axis] - base[node][axis] for axis in range(3)) for node in plane["nodes"]}  # Recover physical translations from nominal F3 without incremental retargeting.
            return {"sign": plane["sign"], "nodes": set(plane["nodes"]), "elements": list(plane["elements"]), "interfaceNodes": set(plane["interfaceNodes"]), "internalNodes": set(plane["internalNodes"]), "anchorNodes": set(plane["anchorNodes"]), "coordinatesMm": coordinates, "displacementsMm": displacements, "actionsN": assembled["actionsN"], "selfWeightActionsN": assembled["selfWeightActionsN"], "elementResponses": assembled["elementResponses"], "maximumInternalResidualN": residual, "minimumAxialStressMPa": minimum_stress, "iterations": iterations}  # Return the accepted physical state and complete inner receipts.
        if iteration >= maximum_iterations:  # Refuse an unconverged state after the explicit iteration budget.
            raise RuntimeError(f"signed plane {plane['sign']} internal Newton did not converge after {maximum_iterations} iterations; residual={residual} N")  # Expose the terminal physical residual.
        factor, factor_receipt = adapter.cholesky(assembled["internalTangentNPerMm"], f"nonlinear signed plane {plane['sign']} K_JJ iteration {iteration}")  # Prove the active tension tangent remains positive definite without regularization.
        residual_vector = [assembled["actionsN"][node][axis] for node, axis in assembled["internalDofs"]]  # Form the actual free-node action residual in the exact tangent ordering.
        correction = adapter.solve_cholesky(factor, residual_vector)  # Solve K*du=r because the derivative of actual action is minus the standard positive tangent.
        accepted = None  # Hold the first tension-safe residual-reducing trial.
        for line_search in range(maximum_line_search_steps + 1):  # Backtrack a bounded number of times from the full Newton correction.
            scale = 0.5 ** line_search  # Preserve deterministic powers-of-two step scales.
            candidate = dict(coordinates)  # Copy the current accepted coordinates before changing only internal nodes.
            for index, (node, axis) in enumerate(assembled["internalDofs"]):  # Apply every ordered Newton component once.
                current = list(candidate[node])  # Recover the mutable current coordinate tuple.
                current[axis] += scale * correction[index]  # Advance along the physical equilibrium Newton direction.
                candidate[node] = (current[0], current[1], current[2])  # Store the complete updated Cartesian coordinate.
            maximum_trial_displacement = max((_norm(tuple(candidate[node][axis] - base[node][axis] for axis in range(3))) for node in plane["nodes"]), default=float("inf"))  # Screen global trial translation magnitude.
            if maximum_trial_displacement > maximum_displacement_mm:  # Reject a divergent trial before mechanics evaluation.
                continue  # Backtrack to a smaller physical correction.
            trial = _assemble_plane_response(context, plane, candidate, assemble_internal_tangent=False)  # Evaluate actual nonlinear action after this co-rotated trial.
            trial_residual = float(trial["maximumInternalResidualN"])  # Recover the trial free-node equilibrium norm.
            trial_minimum_stress = float(trial["minimumAxialStressMPa"])  # Recover the trial active tension floor.
            sufficient_reduction = trial_residual <= residual * (1.0 - 1.0e-4 * scale) or trial_residual <= residual_tolerance_n  # Require real residual descent rather than accepting a merely finite step.
            if trial_minimum_stress >= tension_floor and sufficient_reduction:  # Accept only a tension-safe residual-reducing geometry.
                accepted = (candidate, scale, line_search + 1, trial_residual, trial_minimum_stress)  # Preserve complete line-search evidence.
                break  # Stop at the largest acceptable deterministic step.
        if accepted is None:  # Refuse hidden damping or a non-descent correction.
            raise RuntimeError(f"signed plane {plane['sign']} inner Newton line search failed at iteration {iteration}; residual={residual} N")  # Expose the physical state that could not advance safely.
        coordinates, accepted_scale, trial_count, accepted_residual, accepted_minimum_stress = accepted  # Promote only the accepted tension-safe trial.
        iterations.append({"iteration": iteration, "maximumInternalResidualN": residual, "minimumAxialStressMPa": minimum_stress, "correctionNormMm": _norm(correction), "acceptedStepScale": accepted_scale, "lineSearchTrials": trial_count, "acceptedResidualN": accepted_residual, "acceptedMinimumAxialStressMPa": accepted_minimum_stress, "minimumCholeskyPivot": factor_receipt.get("minimumPivot"), "status": "ACCEPTED"})  # Publish the accepted Newton and no-regularization factor evidence.
    raise RuntimeError("unreachable inner nonlinear suspension state")  # Preserve fail-closed control flow for static analysis.


def solve_suspension_state(context: dict, retained_displacements: dict[int, tuple[float, float, float]], initial_suspension_displacements: dict[int, tuple[float, float, float]] | None = None, residual_tolerance_n: float = DEFAULT_INTERNAL_RESIDUAL_TOL_N, maximum_iterations: int = DEFAULT_MAXIMUM_INTERNAL_ITERATIONS, maximum_line_search_steps: int = DEFAULT_LINE_SEARCH_STEPS, maximum_displacement_mm: float = DEFAULT_MAXIMUM_DISPLACEMENT_MM) -> dict:  # Solve both signed fixed-L0 suspension planes for one retained-interface displacement field.
    if context.get("schema") != NONLINEAR_SCHEMA:  # Require a validated immutable context from this implementation.
        raise RuntimeError("solve_suspension_state requires a fixed-L0 nonlinear context")  # Stop before accepting an arbitrary dictionary as mechanics.
    if residual_tolerance_n <= 0.0 or maximum_iterations <= 0 or maximum_line_search_steps <= 0 or maximum_displacement_mm <= 0.0:  # Require positive explicit solver controls.
        raise RuntimeError("nonlinear suspension solver controls must be positive")  # Reject disabled convergence or unbounded geometry semantics.
    normalized_retained = {int(node): _validate_finite_vector(vector, f"retained displacement node {node}") for node, vector in retained_displacements.items()}  # Normalize supplied physical retained responses once.
    if not context["interfaceNodes"].issubset(normalized_retained):  # Require every active shared node translation without filling missing values.
        raise RuntimeError(f"retained displacement field misses suspension interfaces: {sorted(context['interfaceNodes'] - set(normalized_retained))[:8]}")  # Identify missing physical nodes directly.
    normalized_seed = {int(node): _validate_finite_vector(vector, f"suspension seed node {node}") for node, vector in (initial_suspension_displacements or {}).items()}  # Normalize optional prior nonlinear coordinates.
    plane_states = [_solve_plane_internal(context, plane, normalized_retained, normalized_seed, residual_tolerance_n, maximum_iterations, maximum_line_search_steps, maximum_displacement_mm) for plane in context["planes"]]  # Re-equilibrate both independent physical planes under identical controls.
    displacements: dict[int, tuple[float, float, float]] = {}  # Compose complete active suspension translations without copying one plane to the other.
    coordinates: dict[int, tuple[float, float, float]] = {}  # Compose complete active suspension current coordinates.
    element_responses: dict[int, dict] = {}  # Compose all survivor co-rotational member responses.
    for plane_state in plane_states:  # Merge the two disjoint accepted plane states.
        displacements.update(plane_state["displacementsMm"])  # Preserve actual retained, internal, and anchor translations.
        coordinates.update(plane_state["coordinatesMm"])  # Preserve actual current geometry under stable source node ids.
        element_responses.update(plane_state["elementResponses"])  # Preserve every active member exactly once.
    if set(displacements) != context["suspensionNodes"] or set(element_responses) != context["activeElementIds"]:  # Require complete active topology response coverage.
        raise RuntimeError("nonlinear suspension state coverage differs from active topology")  # Stop before any canonical response composition.
    maximum_residual = max(float(plane["maximumInternalResidualN"]) for plane in plane_states)  # Recover the decisive two-plane physical residual.
    minimum_stress = min(float(plane["minimumAxialStressMPa"]) for plane in plane_states)  # Recover the decisive two-plane active tension floor.
    return {"schema": NONLINEAR_SCHEMA, "planes": plane_states, "displacementsMm": displacements, "coordinatesMm": coordinates, "elementResponses": element_responses, "maximumInternalResidualN": maximum_residual, "minimumAxialStressMPa": minimum_stress, "removedGhosts": context["removedGhosts"], "receipt": {"schema": NONLINEAR_SCHEMA, "status": "PASS", "maximumInternalResidualN": maximum_residual, "internalResidualToleranceN": residual_tolerance_n, "minimumAxialStressMPa": minimum_stress, "activeElementCount": len(element_responses), "removedElementIds": sorted(context["removedElementIds"]), "planeIterations": [{"sign": plane["sign"], "iterationCount": len(plane["iterations"]), "iterations": plane["iterations"]} for plane in plane_states]}}  # Return the accepted physical state and full inner iteration evidence.


def _condense_plane(context: dict, plane_state: dict, reference_retained_displacements: dict[int, tuple[float, float, float]]) -> dict:  # Build one exact current-tangent Schur complement and effective nonlinear Newton load for the retained solver.
    adapter = context["adapter"]  # Recover audited dense factorization utilities.
    interface_dofs = [(node, axis) for node in sorted(plane_state["interfaceNodes"]) for axis in range(3)]  # Freeze retained shared-degree ordering.
    internal_dofs = [(node, axis) for node in sorted(plane_state["internalNodes"]) for axis in range(3)]  # Freeze eliminated current-tangent ordering.
    free_dofs = interface_dofs + internal_dofs  # Combine non-anchor suspension degrees while retaining anchor stiffness on free diagonals.
    free_index = {degree: index for index, degree in enumerate(free_dofs)}  # Map each physical degree to one dense tangent coordinate.
    stiffness = _zero(adapter, len(free_dofs), len(free_dofs))  # Allocate the complete current positive tangent before partitioning.
    element_tangents: dict[int, list[list[float]]] = {}  # Preserve each current co-rotational element block for independent recovery.
    for element_id in plane_state["elements"]:  # Assemble every active survivor once.
        response = plane_state["elementResponses"][element_id]  # Recover current force-dependent tangent and stable endpoints.
        node_a, node_b = response["nodeIds"]  # Unpack ordered physical endpoints.
        tangent = response["tangentNPerMm"]  # Recover the exact current three-by-three block.
        element_tangents[element_id] = tangent  # Preserve the block under the stable source identity.
        for row_node, row_sign in ((node_a, 1.0), (node_b, -1.0)):  # Visit standard positive truss row blocks.
            for column_node, column_sign in ((node_a, 1.0), (node_b, -1.0)):  # Visit standard positive truss column blocks.
                for row_axis in range(3):  # Resolve every global row direction.
                    row_index = free_index.get((row_node, row_axis))  # Skip only fixed anchor rows.
                    if row_index is None:  # Preserve anchor stiffness through free diagonal contributions.
                        continue  # Advance without inventing a solved anchor degree.
                    for column_axis in range(3):  # Resolve every global column direction.
                        column_index = free_index.get((column_node, column_axis))  # Skip only fixed anchor columns.
                        if column_index is not None:  # Assemble active free-to-free terms.
                            stiffness[row_index][column_index] += row_sign * column_sign * tangent[row_axis][column_axis]  # Form the symmetric standard current tangent.
    ni = len(interface_dofs)  # Freeze current retained interface order.
    nj = len(internal_dofs)  # Freeze current eliminated order.
    matrix_ii = [row[:ni] for row in stiffness[:ni]]  # Extract KII without aliasing the full matrix.
    matrix_ij = [row[ni:] for row in stiffness[:ni]]  # Extract KIJ.
    matrix_ji = [row[:ni] for row in stiffness[ni:]]  # Extract KJI.
    matrix_jj = [row[ni:] for row in stiffness[ni:]]  # Extract KJJ.
    factor_jj, internal_factor_receipt = adapter.cholesky(matrix_jj, f"nonlinear signed plane {plane_state['sign']} K_JJ")  # Prove current internal stability without regularization.
    solved = _zero(adapter, nj, ni)  # Allocate KJJ-inverse times KJI for Schur and tangent recovery.
    for column in range(ni):  # Solve every retained coupling column independently.
        solution = adapter.solve_cholesky(factor_jj, [matrix_ji[row][column] for row in range(nj)])  # Apply the accepted current internal factor.
        for row in range(nj):  # Store the solved column in deterministic row-major form.
            solved[row][column] = solution[row]  # Preserve the exact physical reduction operator.
    condensed = _zero(adapter, ni, ni)  # Allocate Kc=KII-KIJ*KJJ-inverse*KJI.
    for row in range(ni):  # Assemble every retained Schur row.
        for column in range(ni):  # Assemble every retained Schur column.
            condensed[row][column] = matrix_ii[row][column] - math.fsum(matrix_ij[row][index] * solved[index][column] for index in range(nj))  # Eliminate current free cable-only coordinates exactly.
    symmetry_numerator = _norm([condensed[row][column] - condensed[column][row] for row in range(ni) for column in range(ni)])  # Measure only roundoff antisymmetry.
    symmetry_denominator = max(_norm([value for row in condensed for value in row]), 1.0)  # Normalize by the physical tangent magnitude.
    symmetry_relative = symmetry_numerator / symmetry_denominator  # Form a dimensionless Schur consistency receipt.
    if symmetry_relative > float(getattr(adapter, "MATRIX_REL_TOL", 1.0e-10)):  # Enforce the canonical no-drift matrix tolerance.
        raise RuntimeError(f"nonlinear signed plane {plane_state['sign']} Schur symmetry error is {symmetry_relative}")  # Stop before modal serialization.
    for row in range(ni):  # Remove only floating-point antisymmetry before Cholesky mode construction.
        for column in range(row):  # Visit each strict lower-upper pair once.
            average = 0.5 * (condensed[row][column] + condensed[column][row])  # Form the energy-consistent symmetric value.
            condensed[row][column] = average  # Store the accepted lower entry.
            condensed[column][row] = average  # Store the identical upper entry.
    factor_condensed, condensed_factor_receipt = adapter.cholesky(condensed, f"nonlinear signed plane {plane_state['sign']} K_condensed")  # Prove anchored current interface stability without diagonal penalty.
    slot_start = 1 if plane_state["sign"] > 0 else STABLE_MODE_SLOTS_PER_PLANE + 1  # Reserve stable positive slots 1..81 and negative slots 82..162 even after e1033 deletion.
    modes: list[dict] = []  # Build one exact normalized rank-one mode per active current interface degree.
    for mode_index in range(ni):  # Visit every accepted Cholesky column once.
        column = [factor_condensed[row][mode_index] for row in range(ni)]  # Recover one lower-factor vector satisfying Kc=L*L-transpose.
        scale = max(abs(value) for value in column)  # Normalize MPC coefficients without changing modal energy.
        if not math.isfinite(scale) or scale <= 0.0:  # Reject an impossible zero or nonfinite SPD factor column.
            raise RuntimeError(f"invalid nonlinear condensed mode {mode_index} on signed plane {plane_state['sign']}")  # Stop before a zero-stiffness auxiliary degree.
        stable_slot = slot_start + mode_index  # Preserve the plane-local nominal auxiliary-id range despite missing damaged modes.
        modes.append({"vector": [value / scale for value in column], "stiffnessNPerMm": scale * scale, "stableSlot": stable_slot, "auxiliaryNodeId": 100000 + stable_slot, "auxiliaryElementId": 200000 + stable_slot})  # Publish data consumable by a stable-slot-aware adapter renderer while retaining legacy vector/stiffness keys.
    recovery = [[-solved[row][column] for column in range(ni)] for row in range(nj)]  # Preserve the current homogeneous tangent recovery operator for diagnostics only.
    interface_vector = [reference_retained_displacements[node][axis] for node, axis in interface_dofs]  # Read the absolute nominal-F3-referenced interface translation at this outer Newton point.
    condensed_reference = _matrix_vector(condensed, interface_vector)  # Form Kc*u_ref required by a homogeneous modal deck.
    physical_interface_actions = {node: list(plane_state["actionsN"][node]) for node in sorted(plane_state["interfaceNodes"])}  # Preserve the actual nonlinear suspension-on-retained action including active self-weight.
    effective_interface_actions = {node: list(physical_interface_actions[node]) for node in sorted(plane_state["interfaceNodes"])}  # Initialize the Newton-equivalent retained RHS at the actual action.
    for index, (node, axis) in enumerate(interface_dofs):  # Add Kc*u_ref in the exact Schur ordering.
        effective_interface_actions[node][axis] += condensed_reference[index]  # Make adapter.build_fine_deck solve (Kr+Kc)u=P+f_s(u_ref)+Kc*u_ref.
    unused_slots = list(range(slot_start + ni, slot_start + STABLE_MODE_SLOTS_PER_PLANE))  # Preserve explicit gaps only when a damaged plane has fewer than eighty-one modes.
    receipt = {"sign": plane_state["sign"], "interfaceNodeCount": len(plane_state["interfaceNodes"]), "interfaceDofCount": ni, "internalNodeCount": len(plane_state["internalNodes"]), "internalDofCount": nj, "anchorNodeCount": len(plane_state["anchorNodes"]), "internalFactor": internal_factor_receipt, "condensedFactor": condensed_factor_receipt, "schurSymmetryRelative": symmetry_relative, "regularizationAddedNPerMm": 0.0, "stableModeSlotStart": slot_start, "activeModeSlots": [mode["stableSlot"] for mode in modes], "unusedReservedModeSlots": unused_slots, "interfaceActionEquation": "effectiveRhs=f_s(u_ref)+Kc*u_ref", "referenceInterfaceDisplacementMaximumMm": max((_norm(reference_retained_displacements[node]) for node in plane_state["interfaceNodes"]), default=0.0)}  # Publish current-tangent mechanics and stable auxiliary-slot evidence.
    return {"sign": plane_state["sign"], "nodes": set(plane_state["nodes"]), "elements": list(plane_state["elements"]), "interfaceNodes": set(plane_state["interfaceNodes"]), "internalNodes": set(plane_state["internalNodes"]), "anchorNodes": set(plane_state["anchorNodes"]), "interfaceDofs": interface_dofs, "internalDofs": internal_dofs, "condensed": condensed, "recovery": recovery, "modes": modes, "baseActions": plane_state["actionsN"], "physicalInterfaceActions": physical_interface_actions, "effectiveInterfaceActions": effective_interface_actions, "selfWeightActions": plane_state["selfWeightActionsN"], "elementTangents": element_tangents, "referenceInterfaceVectorMm": interface_vector, "receipt": receipt}  # Return a legacy-renderer-compatible plane plus nonlinear Newton metadata.


def build_current_condensation(context: dict, suspension_state: dict, retained_displacements: dict[int, tuple[float, float, float]]) -> dict:  # Build an exact current-tangent condensation whose effective RHS is directly consumable by adapter.build_fine_deck.
    normalized_retained = {int(node): _validate_finite_vector(vector, f"condensation retained node {node}") for node, vector in retained_displacements.items()}  # Normalize the outer Newton reference field.
    if not context["interfaceNodes"].issubset(normalized_retained):  # Require every active interface translation explicitly.
        raise RuntimeError("current condensation is missing retained interface displacements")  # Stop before an inconsistent effective load is built.
    plane_by_sign = {int(plane["sign"]): plane for plane in suspension_state["planes"]}  # Index accepted physical plane states without positional copying.
    planes = [_condense_plane(context, plane_by_sign[int(plane["sign"])], normalized_retained) for plane in context["planes"]]  # Condense both current physical tangents independently.
    effective_loads: dict[tuple[int, int], float] = {}  # Assemble the exact Newton-equivalent CLOAD map consumed by the adapter.
    physical_loads: dict[tuple[int, int], float] = {}  # Preserve actual nonlinear interface actions independently for physical force balance.
    for plane in planes:  # Visit both signed current condensations.
        for node in sorted(plane["interfaceNodes"]):  # Visit every active retained interface exactly once.
            for axis in range(3):  # Transfer every global action component.
                effective_loads[(node, axis + 1)] = float(plane["effectiveInterfaceActions"][node][axis])  # Publish f_s(u_ref)+Kc*u_ref for the homogeneous modal solve.
                physical_loads[(node, axis + 1)] = float(plane["physicalInterfaceActions"][node][axis])  # Publish actual f_s(u_ref) for nonlinear closure evidence.
    mode_count = sum(len(plane["modes"]) for plane in planes)  # Count active stable-slot modal equations.
    expected_mode_count = LC08_MODE_COUNT if context["removedElementIds"] else NOMINAL_MODE_COUNT  # Recover the reviewed intact or damaged count.
    if mode_count != expected_mode_count:  # Require exact renderer and physical topology agreement.
        raise RuntimeError(f"current nonlinear condensation expected {expected_mode_count} modes, found {mode_count}")  # Stop before a partial tangent reaches CalculiX.
    receipt = {"schema": NONLINEAR_SCHEMA, "representation": "current fixed-L0 co-rotational suspension tangent statically condensed to the linear retained structure", "interfaceNodeCount": len(context["interfaceNodes"]), "internalNodeCount": len(context["internalNodes"]), "anchorNodeCount": len(context["anchorNodes"]), "suspensionNodeCount": len(context["suspensionNodes"]), "suspensionElementCount": len(context["activeElementIds"]), "activeCondensedModeCount": mode_count, "stableModeSlotContract": {"positivePlaneSlots": [1, 81], "negativePlaneSlots": [82, 162], "auxiliaryNodeId": "100000+stableSlot", "auxiliaryElementId": "200000+stableSlot", "unusedSlots": sorted(slot for plane in planes for slot in plane["receipt"]["unusedReservedModeSlots"])}, "interfaceLoadEquation": "effectiveRhs=f_s(u_ref)+Kc*u_ref", "physicalInterfaceLoadResultantN": [math.fsum(value for (_node, dof), value in physical_loads.items() if dof == axis + 1) for axis in range(3)], "effectiveInterfaceRhsResultantN": [math.fsum(value for (_node, dof), value in effective_loads.items() if dof == axis + 1) for axis in range(3)], "regularizationAddedNPerMm": 0.0, "removedElementIds": sorted(context["removedElementIds"]), "planes": [plane["receipt"] for plane in planes]}  # Publish exact tangent, stable slots, actual action, and effective RHS evidence.
    result = {"planes": planes, "retainedNodes": set(context["retainedNodes"]), "suspensionNodes": set(context["suspensionNodes"]), "interfaceNodes": set(context["interfaceNodes"]), "internalNodes": set(context["internalNodes"]), "anchorNodes": set(context["anchorNodes"]), "interfaceLoads": effective_loads, "physicalInterfaceLoads": physical_loads, "referenceRetainedDisplacementsMm": normalized_retained, "activeSuspensionElementIds": set(context["activeElementIds"]), "removedSuspensionElementIds": set(context["removedElementIds"]), "receipt": receipt}  # Preserve legacy adapter keys while exposing nonlinear physical action separately.
    if context["damageContract"] is not None:  # Mark the reviewed LC08 path for the adapter's 159-mode topology check.
        result["damageContract"] = context["damageContract"]  # Preserve explicit event identity without synthesizing response for e1033.
    return result  # Return the exact homogeneous-modal Newton representation.


def recover_nonlinear_response(context: dict, suspension_state: dict, raw_retained_displacements: dict[int, tuple[float, float, float]]) -> dict:  # Compose total fixed-L0 suspension response, increments from F3, anchor reactions, and removed-member ghost evidence.
    raw = {int(node): _validate_finite_vector(vector, f"raw retained response node {node}") for node, vector in raw_retained_displacements.items()}  # Normalize native retained translations without changing physical meaning.
    if set(raw) != set(context["retainedNodes"]):  # Require exact native retained physical-node coverage.
        missing = sorted(set(context["retainedNodes"]) - set(raw))  # Identify missing native nodes.
        surplus = sorted(set(raw) - set(context["retainedNodes"]))  # Identify unexpected native or auxiliary nodes.
        raise RuntimeError(f"nonlinear raw retained displacement coverage mismatch missing={missing[:8]} surplus={surplus[:8]}")  # Stop before filling any response value.
    displacements = dict(raw)  # Begin the complete physical response with native retained translations.
    for node, vector in suspension_state["displacementsMm"].items():  # Add internal and fixed-anchor suspension translations while checking shared interfaces.
        if node in displacements and _norm(tuple(displacements[node][axis] - vector[axis] for axis in range(3))) > 5.0e-6:  # Require accepted nonlinear interface geometry to match the native outer solve.
            raise RuntimeError(f"nonlinear interface displacement mismatch at node {node}")  # Stop before mixing two iteration states.
        displacements[node] = tuple(vector)  # Preserve the accepted current physical translation.
    expected_nodes = set(context["retainedNodes"]) | set(context["suspensionNodes"])  # Freeze complete active primary node coverage.
    if set(displacements) != expected_nodes:  # Require every retained, interface, internal, and anchor node exactly once.
        raise RuntimeError("nonlinear composed displacement coverage differs from active primary nodes")  # Stop before a zero-filled cloud.
    total_tensors: dict[int, tuple[float, float, float, float, float, float]] = {}  # Store one current total tensor per active suspension member.
    incremental_tensors: dict[int, tuple[float, float, float, float, float, float]] = {}  # Store the exact current-minus-nominal-F3 tensor per active member.
    element_forces: dict[int, float] = {}  # Preserve current signed axial force under stable source ids.
    minimum_stress = float("inf")  # Track the final active tension floor.
    maximum_increment_ratio = 0.0  # Track the largest force change relative to nominal F3.
    for element_id in sorted(context["activeElementIds"]):  # Recover every active survivor once.
        response = suspension_state["elementResponses"][element_id]  # Read current fixed-L0 co-rotational mechanics.
        total = tuple(float(value) for value in response["totalTensorMPa"])  # Freeze current total global stress tensor.
        base = tuple(float(value) for value in context["elementData"][element_id]["baseTensorMPa"])  # Recover nominal-F3 total tensor in its original direction.
        total_tensors[element_id] = total  # Publish current total response for canonical VTK.
        incremental_tensors[element_id] = tuple(total[index] - base[index] for index in range(6))  # Publish the real nonlinear tensor increment without scalar projection shortcuts.
        force = float(response["axialForceN"])  # Recover current signed axial force.
        base_force = float(context["elementData"][element_id]["baseForceN"])  # Recover pre-case nominal force.
        element_forces[element_id] = force  # Preserve stable survivor identity.
        minimum_stress = min(minimum_stress, float(response["axialStressMPa"]))  # Update the final active tension Gate.
        maximum_increment_ratio = max(maximum_increment_ratio, abs(force - base_force) / max(abs(base_force), 1.0))  # Measure actual nonlinear force change without using a tangent screening surrogate.
    removed_release_tensors = {element_id: tuple(-float(value) for value in context["elementData"][element_id]["baseTensorMPa"]) for element_id in sorted(context["removedElementIds"])}  # Preserve stable ghost topology through an exact negative-base increment while excluding the member from active mechanics.
    removed_total_tensors = {element_id: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0) for element_id in sorted(context["removedElementIds"])}  # Publish explicit zero total stress only for reviewed removed ghost cells retained by canonical serialization.
    anchor_reactions: dict[int, list[float]] = {}  # Recover physical support-on-suspension anchor reactions from actual current actions.
    for plane in suspension_state["planes"]:  # Visit both accepted physical signed planes.
        for node in plane["anchorNodes"]:  # Recover every fixed cable anchor once.
            anchor_reactions[node] = [-float(value) for value in plane["actionsN"][node]]  # Apply support reaction equals minus suspension action including active half self-weight.
    anchor_resultant = [math.fsum(vector[axis] for vector in anchor_reactions.values()) for axis in range(3)]  # Form the complete physical cable-anchor support resultant.
    suspension_weight = math.fsum(float(context["elementData"][element_id]["constantSelfWeightN"]) for element_id in context["activeElementIds"])  # Integrate only active constant element gravity once.
    receipt = {"schema": NONLINEAR_SCHEMA, "responseMode": "total fixed-L0 co-rotational survivor response", "displacementNodeCount": len(displacements), "activeStressElementCount": len(total_tensors), "removedStableGhostElementCount": len(removed_total_tensors), "maximumInternalResidualN": float(suspension_state["maximumInternalResidualN"]), "minimumFinalSuspensionAxialStressMPa": minimum_stress, "maximumSuspensionForceIncrementToF3Ratio": maximum_increment_ratio, "anchorReactionConvention": "support-on-suspension equals minus actual current survivor element action and active constant half self-weight", "anchorReactionsN": {str(node): vector for node, vector in sorted(anchor_reactions.items())}, "anchorReactionResultantN": anchor_resultant, "suspensionSelfWeightN": suspension_weight, "removedGhosts": [context["removedGhosts"][element_id] for element_id in sorted(context["removedGhosts"])], "removedMembersExcludedFromStiffnessSelfWeightAndActiveStress": True, "removedMembersRetainedOnlyAsZeroTotalVtkGhostCells": bool(removed_total_tensors)}  # Publish physical recovery, force, topology, and truthful stable-ghost visualization semantics.
    return {"displacements": displacements, "incrementalTensors": incremental_tensors, "totalTensors": total_tensors, "removedReleaseTensors": removed_release_tensors, "removedTotalTensors": removed_total_tensors, "elementForcesN": element_forces, "anchorReactions": anchor_reactions, "removedGhosts": context["removedGhosts"], "receipt": receipt}  # Return canonical-composition-ready survivor response and explicit zero-total stable ghost tensors.


def _interface_remainder(current_condensation: dict, current_state: dict, candidate_state: dict, current_retained: dict[int, tuple[float, float, float]], candidate_retained: dict[int, tuple[float, float, float]]) -> tuple[float, dict[str, float]]:  # Measure the actual nonlinear action minus the action applied by the retained Newton linearization.
    current_by_sign = {int(plane["sign"]): plane for plane in current_state["planes"]}  # Index current physical interface actions by signed plane.
    candidate_by_sign = {int(plane["sign"]): plane for plane in candidate_state["planes"]}  # Index candidate actual interface actions by signed plane.
    maximum = 0.0  # Track the decisive Cartesian physical coupling residual.
    by_plane: dict[str, float] = {}  # Preserve the maximum on each independent plane.
    for condensed_plane in current_condensation["planes"]:  # Visit each retained Newton operator exactly once.
        sign = int(condensed_plane["sign"])  # Recover explicit plane identity.
        current_plane = current_by_sign[sign]  # Recover actual current actions used to build the RHS.
        candidate_plane = candidate_by_sign[sign]  # Recover actual actions at the native solver candidate displacement.
        delta = [candidate_retained[node][axis] - current_retained[node][axis] for node, axis in condensed_plane["interfaceDofs"]]  # Form the retained Newton correction in Schur order.
        predicted_change = _matrix_vector(condensed_plane["condensed"], delta)  # Form positive Kc*du while physical suspension action changes by minus this vector.
        plane_maximum = 0.0  # Track this plane's action linearization remainder.
        for index, (node, axis) in enumerate(condensed_plane["interfaceDofs"]):  # Compare every physical Cartesian interface action.
            predicted_action = float(current_plane["actionsN"][node][axis]) - predicted_change[index]  # Recover the exact action applied by the retained Newton deck.
            actual_action = float(candidate_plane["actionsN"][node][axis])  # Recover the co-rotational action at the solver candidate geometry.
            plane_maximum = max(plane_maximum, abs(actual_action - predicted_action))  # Preserve the largest unbalanced interface component.
        by_plane[str(sign)] = plane_maximum  # Publish the signed-plane residual independently.
        maximum = max(maximum, plane_maximum)  # Update the decisive global residual.
    return maximum, by_plane  # Return the actual retained/suspension physical coupling closure evidence.


def run_coupled_equilibrium(adapter, ccx: str, output: Path, stem: str, base_text: str, coordinated_nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], element_states: dict[int, dict], delta_cloads: dict[tuple[int, int], float] | None = None, removed_element_ids: set[int] | None = None, damage_contract: dict | None = None, initial_retained_displacements: dict[int, tuple[float, float, float]] | None = None, initial_suspension_displacements: dict[int, tuple[float, float, float]] | None = None, reaction_sensor_stiffness_n_per_mm: float | None = None, internal_residual_tolerance_n: float = DEFAULT_INTERNAL_RESIDUAL_TOL_N, coupling_residual_tolerance_n: float = DEFAULT_COUPLING_RESIDUAL_TOL_N, interface_correction_tolerance_mm: float = DEFAULT_INTERFACE_CORRECTION_TOL_MM, maximum_internal_iterations: int = DEFAULT_MAXIMUM_INTERNAL_ITERATIONS, maximum_outer_iterations: int = DEFAULT_MAXIMUM_OUTER_ITERATIONS, outer_relaxation: float = 1.0) -> dict:  # Couple the nonlinear fixed-L0 suspension to the unchanged linear retained CalculiX model through repeated exact current-tangent decks.
    if not re.fullmatch(r"[A-Za-z0-9_]+", stem):  # Keep every native basename deterministic and shell-independent.
        raise RuntimeError(f"invalid nonlinear CalculiX stem: {stem}")  # Reject path separators, whitespace, and ambiguous punctuation.
    if not (0.0 < outer_relaxation <= 1.0):  # Require an explicit bounded Newton relaxation.
        raise RuntimeError("outer_relaxation must lie in (0,1]")  # Stop before divergence or sign reversal.
    if min(internal_residual_tolerance_n, coupling_residual_tolerance_n, interface_correction_tolerance_mm) <= 0.0 or maximum_outer_iterations < 2:  # Require meaningful positive convergence controls and a confirmatory iteration.
        raise RuntimeError("coupled nonlinear convergence controls are invalid")  # Reject disabled physical closure.
    output.mkdir(parents=True, exist_ok=True)  # Create one isolated case or reaction-audit evidence directory.
    context = build_fixed_l0_context(adapter, base_text, coordinated_nodes, groups, element_states, removed_element_ids=removed_element_ids, damage_contract=damage_contract)  # Freeze active topology, material lengths, nominal state, and removed ghosts before solver invocation.
    current_retained = {node: _validate_finite_vector((initial_retained_displacements or {}).get(node, (0.0, 0.0, 0.0)), f"initial retained node {node}") for node in context["retainedNodes"]}  # Initialize the complete linear retained response field, preferably from canonical LC01.
    current_seed = {int(node): _validate_finite_vector(vector, f"initial suspension node {node}") for node, vector in (initial_suspension_displacements or {}).items()}  # Preserve an optional intact pre-loss seed for LC08 alternate-path equilibrium.
    iteration_receipts: list[dict] = []  # Accumulate every native solve, nonlinear action residual, and accepted update.
    settled_iterations = 0  # Require two consecutive full Newton closures so the terminal deck is built at the accepted geometry.
    last_raw = None  # Preserve the terminal native retained response only after a successful solve.
    last_solver_log = ""  # Preserve terminal native diagnostics for the caller's independent Gate.
    last_solver_exit = -1  # Preserve terminal native exit status explicitly.
    last_deck_path = None  # Preserve the exact terminal Newton deck path.
    last_solver_condensation = None  # Preserve the exact current tangent and effective RHS used by the terminal native solve.
    for outer_iteration in range(maximum_outer_iterations):  # Execute a bounded sequence of retained/suspension Newton linearizations.
        current_state = solve_suspension_state(context, current_retained, initial_suspension_displacements=current_seed, residual_tolerance_n=internal_residual_tolerance_n, maximum_iterations=maximum_internal_iterations)  # Re-equilibrate all cable-only coordinates at the current retained geometry.
        condensation = build_current_condensation(context, current_state, current_retained)  # Build Kc and f_s(u_ref)+Kc*u_ref for this exact Newton point.
        deck = adapter.build_fine_deck(base_text, coordinated_nodes, groups, condensation, reaction_sensor_stiffness_n_per_mm=reaction_sensor_stiffness_n_per_mm, delta_cloads=delta_cloads)  # Reuse the unchanged linear retained model with the current nonlinear suspension tangent.
        iteration_stem = f"{stem}_NL_{outer_iteration + 1:02d}"  # Allocate a unique append-only native solver basename for this outer iteration.
        deck_path = output / f"{iteration_stem}.inp"  # Resolve the exact auditable current-tangent deck path.
        deck_path.write_text(deck, encoding="ascii")  # Persist solver input before invocation without rewriting earlier iterations.
        solver_exit, solver_log = adapter.run_calculix(ccx, output, iteration_stem)  # Execute the caller-supplied pinned CalculiX command through the bound adapter utility.
        fatal_hits = [token for token in getattr(adapter, "FATAL_TOKENS", ()) if token in solver_log.upper()]  # Detect canonical native fatal, pivot, singularity, and MPC diagnostics.
        dat_path = output / f"{iteration_stem}.dat"  # Resolve the immutable native response evidence for this Newton step.
        if solver_exit != 0 or fatal_hits or not dat_path.is_file():  # Fail closed before response parsing when native execution is incomplete.
            failure = {"schema": ITERATION_SCHEMA, "status": "FAIL", "outerIteration": outer_iteration + 1, "solverExitCode": solver_exit, "fatalDiagnostics": fatal_hits, "deckSha256": _sha256_path(deck_path), "reason": "native retained current-tangent solve did not complete"}  # Preserve exact native failure evidence.
            failure_sha = _write_json(output / f"{iteration_stem}.iteration.json", failure)  # Publish the terminal iteration failure before raising.
            _write_json(output / f"{stem}.outer-iterations.json", {"schema": NONLINEAR_SCHEMA, "status": "FAIL", "context": context["receipt"], "iterations": [*iteration_receipts, {**failure, "receiptSha256": failure_sha}]})  # Publish aggregate failure provenance without a response claim.
            raise RuntimeError(f"nonlinear retained solve failed at outer iteration {outer_iteration + 1}: exit={solver_exit} fatal={fatal_hits}")  # Stop before inventing a candidate state.
        raw = adapter.parse_raw_response(dat_path)  # Parse exact native retained displacements, stresses, and optional reaction sensors.
        if set(raw["displacements"]) != set(context["retainedNodes"]):  # Require exact physical retained response coverage at every Newton step.
            raise RuntimeError(f"outer iteration {outer_iteration + 1} retained displacement coverage mismatch")  # Stop before a partial interface update.
        native_candidate = {node: tuple(float(value) for value in raw["displacements"][node]) for node in context["retainedNodes"]}  # Recover the full native Newton candidate without truncation.
        correction_vectors = {node: tuple(native_candidate[node][axis] - current_retained[node][axis] for axis in range(3)) for node in context["interfaceNodes"]}  # Form exact retained-interface Newton corrections.
        maximum_correction = max((_norm(vector) for vector in correction_vectors.values()), default=float("inf"))  # Measure the decisive full physical interface update before damping.
        accepted_state = None  # Hold the first inner-equilibrated tension-safe retained trial along the native Newton direction.
        accepted_retained = None  # Hold matching complete retained translations for the accepted trial.
        accepted_scale = 1.0  # Start every outer line search from the full native Newton candidate.
        outer_line_search_trials = 0  # Count attempted retained corrections for transparent slack-cable avoidance.
        last_outer_error = ""  # Preserve the terminal rejected inner-solve diagnostic without hiding it.
        for outer_line_search in range(DEFAULT_LINE_SEARCH_STEPS + 1):  # Backtrack the retained Newton correction until the fixed-L0 suspension remains stable and in tension.
            accepted_scale = 1.0 if outer_line_search == 0 else min(outer_relaxation, 0.5 ** outer_line_search)  # Use the caller ceiling and deterministic powers of two after the full trial.
            trial_retained = {node: tuple(current_retained[node][axis] + accepted_scale * (native_candidate[node][axis] - current_retained[node][axis]) for axis in range(3)) for node in context["retainedNodes"]}  # Form one complete damped retained candidate.
            outer_line_search_trials = outer_line_search + 1  # Publish every attempted physical candidate including the full step.
            try:  # Treat lost tension, an indefinite KJJ, or inner nonconvergence as a rejected Newton trial rather than a final response.
                trial_state = solve_suspension_state(context, trial_retained, initial_suspension_displacements=current_state["displacementsMm"], residual_tolerance_n=internal_residual_tolerance_n, maximum_iterations=maximum_internal_iterations)  # Re-equilibrate cable-only coordinates before accepting retained damping.
            except RuntimeError as error:  # Preserve fail-closed physical diagnostics while permitting deterministic outer backtracking.
                last_outer_error = str(error)  # Retain the exact rejected-state reason for a terminal failure message.
                continue  # Try the next smaller retained Newton correction without changing the accepted state.
            accepted_retained = trial_retained  # Promote the first stable, tension-safe, inner-equilibrated retained state.
            accepted_state = trial_state  # Preserve its matching physical suspension mechanics.
            break  # Stop at the largest acceptable deterministic retained step.
        if accepted_state is None or accepted_retained is None:  # Refuse hidden regularization after exhausting explicit retained backtracking.
            raise RuntimeError(f"outer retained Newton line search failed at iteration {outer_iteration + 1}: {last_outer_error}")  # Expose the physical reason no stable step exists.
        coupling_residual, plane_residuals = _interface_remainder(condensation, current_state, accepted_state, current_retained, accepted_retained)  # Measure actual action minus the Newton action at the accepted retained trial.
        accepted_correction = max((_norm(tuple(accepted_retained[node][axis] - current_retained[node][axis] for axis in range(3))) for node in context["interfaceNodes"]), default=float("inf"))  # Measure the actual accepted interface update.
        full_step_closed = accepted_scale == 1.0 and accepted_correction <= interface_correction_tolerance_mm and coupling_residual <= coupling_residual_tolerance_n and float(accepted_state["maximumInternalResidualN"]) <= internal_residual_tolerance_n  # Require an undamped terminal Newton correction plus all physical closure Gates.
        iteration_receipt = {"schema": ITERATION_SCHEMA, "status": "CLOSED" if full_step_closed else "ITERATING", "outerIteration": outer_iteration + 1, "analysisClass": "linear retained structure plus nonlinear fixed-L0 suspension", "solverExitCode": solver_exit, "fatalDiagnostics": fatal_hits, "reactionSensorStiffnessNPerMm": reaction_sensor_stiffness_n_per_mm, "deckSha256": _sha256_path(deck_path), "rawDatSha256": _sha256_path(dat_path), "activeSuspensionElementCount": len(context["activeElementIds"]), "removedElementIds": sorted(context["removedElementIds"]), "condensedModeCount": sum(len(plane["modes"]) for plane in condensation["planes"]), "maximumFullInterfaceNewtonCorrectionMm": maximum_correction, "maximumAcceptedInterfaceCorrectionMm": accepted_correction, "interfaceCorrectionToleranceMm": interface_correction_tolerance_mm, "maximumPhysicalCouplingResidualN": coupling_residual, "physicalCouplingResidualByPlaneN": plane_residuals, "couplingResidualToleranceN": coupling_residual_tolerance_n, "maximumInternalResidualN": float(accepted_state["maximumInternalResidualN"]), "internalResidualToleranceN": internal_residual_tolerance_n, "minimumActiveSuspensionStressMPa": float(accepted_state["minimumAxialStressMPa"]), "acceptedOuterStepScale": accepted_scale, "outerLineSearchTrials": outer_line_search_trials, "effectiveInterfaceRhsEquation": "f_s(u_ref)+Kc*u_ref", "retainedStructureLinear": True, "suspensionGeometryRelinearized": True, "stableModeSlotContract": condensation["receipt"]["stableModeSlotContract"]}  # Publish complete physical and numerical closure evidence for this outer iteration.
        iteration_sha = _write_json(output / f"{iteration_stem}.iteration.json", iteration_receipt)  # Persist the append-only per-iteration receipt.
        iteration_receipts.append({**iteration_receipt, "receiptSha256": iteration_sha})  # Bind the aggregate receipt to the exact per-iteration bytes.
        last_raw = raw  # Preserve this successful native result as the current terminal candidate.
        last_solver_log = solver_log  # Preserve matching native diagnostics.
        last_solver_exit = solver_exit  # Preserve matching native exit status.
        last_deck_path = deck_path  # Preserve matching exact solver input.
        last_solver_condensation = condensation  # Preserve matching tangent and effective RHS.
        current_retained = accepted_retained  # Advance the coupled Newton reference only after all physical evidence is published.
        current_seed = accepted_state["displacementsMm"]  # Seed the next inner solve from the accepted fixed-L0 geometry without retargeting L0.
        if full_step_closed:  # Count consecutive full-step physical closures.
            settled_iterations += 1  # Require a second deck built at the already closed geometry.
        else:  # Reset confirmation after any nonclosed iteration.
            settled_iterations = 0  # Prevent a stale earlier closure from accepting a later drift.
        if settled_iterations >= 2:  # Accept only two consecutive full Newton closures.
            final_state = accepted_state  # Preserve actual nonlinear suspension mechanics at the terminal native displacement field.
            physical_condensation = build_current_condensation(context, final_state, accepted_retained)  # Publish the terminal physical tangent independently from the tangent used one correction earlier.
            recovery = recover_nonlinear_response(context, final_state, raw["displacements"])  # Compose survivor total/increment tensors, anchor reactions, and e1033 ghost evidence.
            aggregate = {"schema": NONLINEAR_SCHEMA, "status": "PASS", "analysisClass": "linear retained structure coupled to nonlinear fixed-L0 co-rotational suspension", "context": context["receipt"], "outerIterationCount": len(iteration_receipts), "confirmedClosedIterationCount": settled_iterations, "terminalDeckSha256": _sha256_path(deck_path), "terminalRawDatSha256": _sha256_path(dat_path), "terminalMaximumInterfaceCorrectionMm": accepted_correction, "terminalMaximumPhysicalCouplingResidualN": coupling_residual, "terminalMaximumInternalResidualN": float(final_state["maximumInternalResidualN"]), "terminalMinimumActiveSuspensionStressMPa": float(final_state["minimumAxialStressMPa"]), "removedGhosts": list(context["removedGhosts"].values()), "retainedStructureRemainedLinear": True, "suspensionWasRelinearized": True, "iterations": iteration_receipts}  # Publish the decisive coupled convergence and evidence-boundary contract.
            aggregate_path = output / f"{stem}.outer-iterations.json"  # Resolve the unique aggregate nonlinear receipt.
            aggregate_sha = _write_json(aggregate_path, aggregate)  # Persist complete append-only iteration provenance.
            return {"schema": NONLINEAR_SCHEMA, "status": "PASS", "context": context, "suspensionState": final_state, "solverCondensation": last_solver_condensation, "physicalCondensation": physical_condensation, "raw": last_raw, "recovery": recovery, "solverExitCode": last_solver_exit, "solverLog": last_solver_log, "terminalDeckPath": last_deck_path, "terminalDeckSha256": _sha256_path(last_deck_path), "terminalRawDatSha256": _sha256_path(dat_path), "iterationReceiptPath": aggregate_path, "iterationReceiptSha256": aggregate_sha, "iterations": iteration_receipts}  # Return canonical-case-ready native and nonlinear response evidence.
    failure = {"schema": NONLINEAR_SCHEMA, "status": "FAIL", "reason": "coupled retained/suspension Newton iteration limit reached", "maximumOuterIterations": maximum_outer_iterations, "context": context["receipt"], "iterations": iteration_receipts}  # Preserve every completed solve without promoting an unconverged response.
    _write_json(output / f"{stem}.outer-iterations.json", failure)  # Publish terminal nonconvergence evidence before raising.
    raise RuntimeError(f"coupled nonlinear equilibrium did not converge after {maximum_outer_iterations} outer iterations")  # Fail closed without a formal response artifact claim.


def _compose_nonlinear_reaction_audit(adapter, result: dict, stiffness_n_per_mm: float, label: str) -> dict:  # Convert one converged sensor-supported nonlinear solve to the canonical clean-collector reaction receipt shape.
    deck_path = Path(result["terminalDeckPath"])  # Recover the exact terminal sensor deck used by the converged nonlinear solve.
    deck_text = deck_path.read_text(encoding="ascii")  # Parse only the persisted terminal bytes for topology and load-free evidence.
    raw = result["raw"]  # Recover matching native physical, proxy, and clean-collector response tables.
    mapping = adapter.reaction_collector_contract(deck_text)  # Reconstruct the exact physical-degree-to-scalar-sensor contract independently from response values.
    collector_nodes = {int(record["collectorNode"]) for record in mapping}  # Freeze the expected clean RF node population.
    proxy_nodes = {int(record["proxyNode"]) for record in mapping}  # Freeze the expected scalar support-proxy displacement population.
    collector_coverage = set(raw["collectorForces"]) == collector_nodes and set(raw["proxyDisplacements"]) == proxy_nodes and all(math.isfinite(value) for vector in [*raw["collectorForces"].values(), *raw["proxyDisplacements"].values()] for value in vector)  # Require exact finite sensor result coverage.
    audit_nodes, audit_groups, _audit_ownership = adapter.parse_model(deck_text)  # Parse complete persisted sensor topology independently.
    sensor_ids = {int(record["sensorElement"]) for record in mapping}  # Freeze every generated SPRING2 identity.
    gravity_ids = adapter.explicit_set_members(deck_text, "*ELSET", "ELSET", "E_GRAV")  # Recover the exact physical gravity set.
    loaded_nodes = adapter.explicit_cload_nodes(deck_text)  # Recover every explicit permanent, case, and effective-interface CLOAD node.
    collector_members = adapter.explicit_set_members(deck_text, "*NSET", "NSET", "P3_REACTION_COLLECTORS")  # Recover the exact clean-node set.
    proxy_members = adapter.explicit_set_members(deck_text, "*NSET", "NSET", "P3_REACTION_PROXIES")  # Recover the exact scalar-proxy set.
    expected_topology = {int(record["sensorElement"]): [int(record["collectorNode"]), int(record["proxyNode"])] for record in mapping}  # Build required collector-first sensor connectivity.
    actual_topology = {element_id: connectivity for group_name, elements in audit_groups.items() if group_name.startswith("P3_RF_") for element_id, connectivity in elements}  # Recover all generated sensors without relying on ids alone.
    collector_incidence = {collector: sorted(element_id for elements in audit_groups.values() for element_id, connectivity in elements if collector in connectivity) for collector in collector_nodes}  # Enumerate every element touching a supposedly clean collector.
    proxy_incidence = {proxy: sorted(element_id for elements in audit_groups.values() for element_id, connectivity in elements if proxy in connectivity) for proxy in proxy_nodes}  # Enumerate every element touching a scalar proxy.
    load_free = collector_members == collector_nodes and proxy_members == proxy_nodes and not ((collector_nodes | proxy_nodes) & loaded_nodes) and not (sensor_ids & gravity_ids) and actual_topology == expected_topology and all(collector_incidence[int(record["collectorNode"])] == [int(record["sensorElement"])] and proxy_incidence[int(record["proxyNode"])] == [int(record["sensorElement"])] for record in mapping)  # Require each sensor endpoint to carry no physical load or unrelated finite element.
    retained_components = [0.0, 0.0, 0.0]  # Accumulate support-on-retained-structure RF into bridge axes.
    constitutive_relative = 0.0  # Track RFcollector plus K times scalar proxy extension at printed precision.
    maximum_support_translation = 0.0  # Track the largest directly connected scalar SPRING2 extension used by the precommitted support-limit Gate.
    maximum_reported_physical_knot_translation = 0.0  # Preserve expanded physical-knot output separately because it is not the scalar sensor extension.
    for record in mapping:  # Visit every physical constrained translation and its unique sensor once.
        physical_node = int(record["physicalNode"])  # Recover the physical support node identity.
        physical_dof = int(record["physicalDof"])  # Recover its bridge direction.
        collector_node = int(record["collectorNode"])  # Recover the load-free RF endpoint.
        proxy_node = int(record["proxyNode"])  # Recover the knot-isolated scalar displacement endpoint.
        collector_force = float(raw["collectorForces"][collector_node][0]) if collector_coverage else float("inf")  # Read only clean RF1 or preserve fail-closed nonfinite evidence.
        proxy_displacement = float(raw["proxyDisplacements"][proxy_node][0]) if collector_coverage else float("inf")  # Read actual SPRING2 scalar extension.
        physical_displacement = float(raw["displacements"][physical_node][physical_dof - 1])  # Read the physical support approximation movement.
        retained_components[physical_dof - 1] += collector_force  # Map scalar RF back to the physical bridge axis.
        constitutive_relative = max(constitutive_relative, abs(collector_force + stiffness_n_per_mm * proxy_displacement) / max(abs(collector_force), 1.0))  # Enforce the clean sensor constitutive identity.
        maximum_support_translation = max(maximum_support_translation, abs(proxy_displacement))  # Screen the actual scalar SPRING2 support extension consumed by the reaction constitutive equation.
        maximum_reported_physical_knot_translation = max(maximum_reported_physical_knot_translation, abs(physical_displacement))  # Retain the expanded physical support-knot translation as a nondecisive diagnostic.
    retained_resultant = tuple(retained_components)  # Freeze complete retained support-on-structure resultant.
    anchor_resultant = tuple(float(value) for value in result["recovery"]["receipt"]["anchorReactionResultantN"])  # Recover actual nonlinear cable-anchor reactions from the same sensor-supported geometry.
    physical_resultant = tuple(retained_resultant[axis] + anchor_resultant[axis] for axis in range(3))  # Form the complete bridge support resultant.
    stdout_path = deck_path.with_suffix(".stdout.log")  # Resolve the matching native stdout evidence path.
    fatal_hits = [token for token in getattr(adapter, "FATAL_TOKENS", ()) if token in result["solverLog"].upper()]  # Reapply canonical fatal diagnostic screening.
    return {"label": label, "stiffnessNPerMm": stiffness_n_per_mm, "solverExitCode": int(result["solverExitCode"]), "fatalDiagnostics": fatal_hits, "deckSha256": _sha256_path(deck_path), "rawDatSha256": result["terminalRawDatSha256"], "stdoutSha256": _sha256_path(stdout_path) if stdout_path.is_file() else None, "collectorMap": mapping, "collectorNodeIds": sorted(collector_nodes), "proxyNodeIds": sorted(proxy_nodes), "collectorCoveragePass": collector_coverage, "collectorsLoadFreePass": load_free, "maximumConstitutiveResidualRelative": constitutive_relative, "maximumSupportTranslationMm": maximum_support_translation, "maximumReportedPhysicalKnotTranslationMm": maximum_reported_physical_knot_translation, "retainedSupportResultantN": retained_resultant, "analyticAnchorReactionResultantN": anchor_resultant, "physicalSupportResultantN": physical_resultant, "anchorRecovery": result["recovery"]["receipt"], "nonlinearIterationReceiptSha256": result["iterationReceiptSha256"]}  # Return a canonical-Gate-compatible clean reaction receipt plus nonlinear convergence provenance.


def run_fixed_l0_corotational_case(pipeline, adapter, ccx: str, output: Path, base_text: str, coordinated_nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], element_states: dict[int, dict], state: dict, target_stress: dict[int, float], delta_cloads: dict[tuple[int, int], float], case_id: str, removed_ids: set[int] | None = None, damage_contract: dict | None = None, initial_retained_displacements: dict[int, tuple[float, float, float]] | None = None, initial_suspension_displacements: dict[int, tuple[float, float, float]] | None = None) -> dict:  # Execute one complete nonlinear case, two nonlinear reaction limits, stable canonical DAT, and 1070-cell total-stress VTK.
    if not re.fullmatch(r"LC\d\d_[A-Z0-9_]+", case_id):  # Require a registry-style immutable case identity before creating evidence paths.
        raise RuntimeError(f"invalid nonlinear case id: {case_id}")  # Stop before an ambiguous output namespace is created.
    if state.get("schema") != "zhaqing-equilibrium-state-v3" or state.get("status") != "PASS":  # Require the accepted persisted LC01/F3 fabrication parent.
        raise RuntimeError("fixed-L0 nonlinear case requires an accepted equilibrium-state v3 parent")  # Stop before solving from an unevidenced prestress state.
    if not hasattr(adapter, "run_calculix") or adapter.run_calculix is not pipeline.run_calculix:  # Require the adapter to share the caller's pinned native execution utility after bind_globals.
        raise RuntimeError("loaded adapter is not bound to the pipeline run_calculix utility")  # Refuse a missing or substituted native execution utility rather than silently mixing solver launch semantics.
    output.mkdir(parents=True, exist_ok=True)  # Create one isolated complete case evidence root.
    main_result = run_coupled_equilibrium(adapter, ccx, output, f"ZQ_{case_id}", base_text, coordinated_nodes, groups, element_states, delta_cloads=delta_cloads, removed_element_ids=removed_ids, damage_contract=damage_contract, initial_retained_displacements=initial_retained_displacements, initial_suspension_displacements=initial_suspension_displacements)  # Solve the direct-support physical U/S state through repeated current tangents.
    reaction_results: list[dict] = []  # Accumulate both precommitted nonlinear finite-support limits.
    for stiffness, label in zip(getattr(adapter, "REACTION_AUDIT_STIFFNESSES_N_PER_MM", (1.0e9, 1.0e10)), ("K1E9", "K1E10")):  # Preserve canonical K and 10K order and exact stiffness values.
        audit_root = output / f"reaction-{label}"  # Isolate each nonlinear sensor Newton sequence and native basenames.
        audit_result = run_coupled_equilibrium(adapter, ccx, audit_root, f"ZQ_{case_id}_{label}", base_text, coordinated_nodes, groups, element_states, delta_cloads=delta_cloads, removed_element_ids=removed_ids, damage_contract=damage_contract, initial_retained_displacements=main_result["raw"]["displacements"], initial_suspension_displacements=main_result["suspensionState"]["displacementsMm"], reaction_sensor_stiffness_n_per_mm=float(stiffness))  # Re-equilibrate the nonlinear suspension at the matching finite-support displacement field.
        reaction_results.append(_compose_nonlinear_reaction_audit(adapter, audit_result, float(stiffness), label))  # Convert native sensors and actual anchor action to the canonical audit contract.
    raw_path = Path(main_result["terminalDeckPath"]).with_suffix(".dat")  # Resolve the immutable terminal native response before composition.
    raw_sha_before = _sha256_path(raw_path)  # Freeze native evidence identity before canonical DAT and VTK writes.
    removed = set(removed_ids or set())  # Freeze the reviewed stable ghost source identities for both serializers.
    canonical_path = output / "canonical-response.dat"  # Resolve the complete stable 783-node/1070-element response stream.
    canonical_receipt = adapter.write_canonical_response(canonical_path, main_result["raw"], main_result["recovery"], groups, removed_suspension_element_ids=removed)  # Serialize native retained tokens, nonlinear survivor increments, and exact removed negative-base release tensors.
    if _sha256_path(raw_path) != raw_sha_before:  # Prove response composition did not mutate the native terminal DAT.
        raise RuntimeError(f"{case_id} nonlinear native DAT changed during canonical response composition")  # Stop before publishing a broken provenance chain.
    retained_total = {element_id: adapter.average_stress_records(records) for element_id, records in main_result["raw"]["stressTokens"].items()}  # Average complete native retained total tensors under the established VTK convention.
    total_stresses = {**retained_total, **main_result["recovery"]["totalTensors"], **main_result["recovery"]["removedTotalTensors"]}  # Compose exact retained totals, nonlinear survivor totals, and explicit zero-total stable ghosts.
    wind_receipt = adapter.write_wind_exclusion(output / "wind-exclusion.json", groups)  # Preserve the unchanged formal G3/G5 wind-response boundary.
    vtk_receipt = adapter.write_primary_vtk(output / "stress-coordinated.vtk", coordinated_nodes, groups, main_result["recovery"]["displacements"], total_stresses, target_stress)  # Serialize the stable 783-point/1070-cell total-response cloud.
    fine_deck = Path(main_result["terminalDeckPath"]).read_text(encoding="ascii")  # Recover the exact terminal direct-support deck for independent load accounting.
    fine_nodes, fine_groups, _fine_ownership = adapter.parse_model(fine_deck)  # Parse terminal retained topology independently from in-memory context.
    retained_external, retained_load_audit = adapter.permanent_external_resultant(fine_deck, fine_nodes, fine_groups)  # Recover permanent, case-delta, and effective-interface loads from exact solver input.
    effective_interface = tuple(math.fsum(value for (_node, dof), value in main_result["solverCondensation"]["interfaceLoads"].items() if dof == axis + 1) for axis in range(3))  # Sum the homogeneous-modal Newton RHS transfer included in retained load accounting.
    suspension_weight = float(main_result["recovery"]["receipt"]["suspensionSelfWeightN"])  # Recover complete active constant suspension gravity.
    full_external = (retained_external[0] - effective_interface[0], retained_external[1] - effective_interface[1], retained_external[2] - effective_interface[2] - suspension_weight)  # Replace the internal Newton transfer by actual whole-suspension external gravity for bridge force balance.
    ordered_audits = sorted(reaction_results, key=lambda record: float(record["stiffnessNPerMm"]))  # Order K before 10K independently from execution order.
    low_audit, selected_audit = ordered_audits  # Use K for convergence and the frozen 10K level for formal support resultant.
    physical_support = tuple(float(value) for value in selected_audit["physicalSupportResultantN"])  # Recover retained clean RF plus matching actual nonlinear anchor reactions.
    force_balance_residual = tuple(physical_support[axis] + full_external[axis] for axis in range(3))  # Apply support-on-structure plus physical external load equals zero.
    vertical_balance_relative = abs(force_balance_residual[2]) / max(abs(full_external[2]), 1.0)  # Normalize vertical closure by complete primary vertical load.
    global_force_balance_relative = _norm(force_balance_residual) / max(_norm(full_external), 1.0)  # Normalize complete Cartesian force closure by the complete physical external resultant.
    convergence_difference = tuple(float(selected_audit["physicalSupportResultantN"][axis]) - float(low_audit["physicalSupportResultantN"][axis]) for axis in range(3))  # Compare complete K and 10K support resultants.
    reaction_convergence_relative = _norm(convergence_difference) / max(_norm(physical_support), abs(full_external[2]), 1.0)  # Normalize sensor-limit convergence by the full bridge force scale.
    maximum_displacement = max(_norm(vector) for vector in main_result["recovery"]["displacements"].values())  # Measure the largest actual retained or nonlinear suspension translation.
    support_translation_tolerance = float(getattr(adapter, "REACTION_AUDIT_SUPPORT_TRANSLATION_TOL_MM", 1.0e-2))  # Preserve the canonical precommitted finite-support approximation limit without relaxation.
    gates = {"solverExitZero": int(main_result["solverExitCode"]) == 0, "fatalDiagnosticsAbsent": not [token for token in getattr(adapter, "FATAL_TOKENS", ()) if token in main_result["solverLog"].upper()], "fixedL0InternalEquilibriumPass": float(main_result["suspensionState"]["maximumInternalResidualN"]) <= DEFAULT_INTERNAL_RESIDUAL_TOL_N, "positiveFinalSuspensionTension": float(main_result["recovery"]["receipt"]["minimumFinalSuspensionAxialStressMPa"]) >= float(getattr(adapter, "MIN_TENSION_MPA", 0.0)), "reactionAuditBothSolversExitZero": all(int(level["solverExitCode"]) == 0 for level in ordered_audits), "reactionAuditFatalDiagnosticsAbsent": all(not level["fatalDiagnostics"] for level in ordered_audits), "reactionCollectorCoveragePass": all(level["collectorCoveragePass"] for level in ordered_audits), "reactionCollectorsLoadFreePass": all(level["collectorsLoadFreePass"] for level in ordered_audits), "reactionCollectorConstitutivePass": all(float(level["maximumConstitutiveResidualRelative"]) <= 1.0e-5 for level in ordered_audits), "reactionAuditKConvergencePass": reaction_convergence_relative <= float(getattr(adapter, "REACTION_AUDIT_CONVERGENCE_REL_TOL", 1.0e-3)), "reactionAuditSupportLimitPass": float(selected_audit["maximumSupportTranslationMm"]) <= support_translation_tolerance, "verticalReactionBalancePass": vertical_balance_relative <= float(getattr(adapter, "FORCE_BALANCE_REL_TOL", 1.0e-3)), "globalForceBalancePass": global_force_balance_relative <= float(getattr(adapter, "FORCE_BALANCE_REL_TOL", 1.0e-3)), "maximumDisplacementScreeningPass": math.isfinite(maximum_displacement) and maximum_displacement <= 1000.0, "canonicalPrimaryCoveragePass": canonical_receipt["nodeCount"] == 783 and canonical_receipt["elementCount"] == 1070, "vtkPrimaryCoveragePass": vtk_receipt["pointCount"] == 783 and vtk_receipt["cellCount"] == 1070, "removedGhostReleasePass": set(main_result["recovery"]["removedReleaseTensors"]) == removed and all(all(value == 0.0 for value in tensor) for tensor in main_result["recovery"]["removedTotalTensors"].values())}  # Publish every numerical, all-axis force, physical, sensor, topology, and stable-ghost Gate without a tangent-range screen.
    summary_receipt = {"schema": "zhaqing-fixed-l0-corotational-case-summary-v1", "caseId": case_id, "status": "PASS" if all(gates.values()) else "FAIL", "analysisMode": "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION", "gates": gates, "failedGates": sorted(name for name, passed in gates.items() if not passed), "maximumDisplacementMm": maximum_displacement, "minimumFinalSuspensionAxialStressMPa": main_result["recovery"]["receipt"]["minimumFinalSuspensionAxialStressMPa"], "maximumSuspensionForceIncrementToF3Ratio": main_result["recovery"]["receipt"]["maximumSuspensionForceIncrementToF3Ratio"], "forceBalanceResidualN": force_balance_residual, "verticalReactionBalanceRelative": vertical_balance_relative, "globalForceBalanceRelative": global_force_balance_relative, "reactionAuditResultantConvergenceRelative": reaction_convergence_relative, "reactionAuditSupportTranslationToleranceMm": support_translation_tolerance, "selectedReactionAuditSupportTranslationMm": selected_audit["maximumSupportTranslationMm"], "supportTranslationGateDisposition": "PRECOMMITTED_GATE_RETAINED_WITHOUT_RELAXATION", "fullPrimaryExternalLoadResultantN": full_external, "physicalSupportReactionResultantN": physical_support, "retainedLoadAudit": retained_load_audit, "removedElementIds": sorted(removed), "canonicalResponseDatSha256": canonical_receipt["sha256"], "vtkSha256": vtk_receipt["sha256"], "windExclusionSha256": wind_receipt["sha256"], "nonlinearIterationReceiptSha256": main_result["iterationReceiptSha256"], "engineeringReleaseStatus": "BLOCKED_G3_G5"}  # Return a runner-ready decisive receipt while keeping all-axis balance and support-translation thresholds explicit.
    return {"raw": main_result["raw"], "recovery": main_result["recovery"], "condensation": main_result["solverCondensation"], "physicalCondensation": main_result["physicalCondensation"], "fineDeck": fine_deck, "solverExit": main_result["solverExitCode"], "solverLog": main_result["solverLog"], "reactionAudits": ordered_audits, "canonicalReceipt": canonical_receipt, "vtkReceipt": vtk_receipt, "windReceipt": wind_receipt, "summaryReadyReceipt": summary_receipt, "nonlinearResult": main_result}  # Expose the practical high-level API requested by the case runner without owning its final summary filename.
