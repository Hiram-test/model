from __future__ import annotations  # Keep annotations deterministic on the supported Python runtime.

import csv  # Read reversible source identities and publish one property row per physical axial member.
import hashlib  # Bind every parent, ledger, deck, and manifest byte stream.
import json  # Read frozen build evidence and publish deterministic reports.
import math  # Validate finite geometry, stress projections, and element properties.
import os  # Publish large immutable artifacts by same-filesystem hard link.
import re  # Parse exact CalculiX keyword attributes without broad substitutions.
import sys  # Select the preregistered C3 upper-bound parent explicitly.
import tempfile  # Stage complete decks and ledgers before atomic publication.
from collections import Counter  # Audit exact element, material, stress, and transformation cardinalities.
from datetime import datetime, timezone  # Timestamp every trapped failure in UTC.
from pathlib import Path  # Resolve repository-controlled inputs independently of caller cwd.
from typing import Iterable  # Describe deterministic streamed records.

BASE = Path(__file__).resolve().parent.parent  # Anchor the C0-C5 reproduction project.
ARTIFACTS = BASE / "artifacts"  # Store immutable ledgers, manifests, and audit evidence.
UPPER_BOUND = "--upper-bound" in sys.argv[1:]  # Convert only the original prestressed axial family when passage members retain six ports.
SOLVER = BASE / "solver" / ("c3_ub_ucab3_diag" if UPPER_BOUND else "c3_ucab3_diag")  # Isolate each physical representation's condensed diagnostic decks.
ERROR_LOG = ARTIFACTS / "error_log.jsonl"  # Append every failed build without replacement.
R2_MANIFEST = ARTIFACTS / ("C3-UB-SM_build_8f039e34a7355d8e.json" if UPPER_BOUND else "C3-SM_build_f7e8ef767a127bc6.json")  # Bind the exact selected C3 source deck pair.
ELEMENT_MAP = ARTIFACTS / "C0-SM_f12ad9b701f63efe_element_map_796f5826f873c30e.csv"  # Recover every source element identity reversibly.
EXPECTED_R2_MANIFEST_SHA256 = "8f039e34a7355d8e35cd0df534bb2501d3ae7292d814efaa446239d1d6374165" if UPPER_BOUND else "f7e8ef767a127bc693d086f601bda33c1f932a2b5192c8024d3de4eca0f8161d"  # Freeze the exact selected C3 manifest bytes.
EXPECTED_ELEMENT_MAP_SHA256 = "796f5826f873c30ef0e7fd0ed961f9e78d5914b12c2aee665736b7dd48346e73"  # Freeze the exact dense element ledger.
CANDIDATE_BINARY = Path("/tmp/ucab3-contingency-dmcXjg/work/CalculiX/ccx_2.23/src/ccx_2.23")  # Select the solver-backed UCAB3 candidate pending final receipt.
CANDIDATE_BINARY_SHA256 = "2a7b985edd66e7db401f7ecceebff13fa8551fa312e8187fe4366a0f564e2061"  # Bind the coupon-passed candidate executable.
EXPECTED_NODES = 91415  # Preserve C3-R2 physical plus eight coincident downpull split nodes.
EXPECTED_ELEMENTS = 172998  # Preserve all source elements plus four disclosed equalizer activators.
EXPECTED_UCAB3 = 73692 if UPPER_BOUND else 85221  # Replace only original ropes/downpulls in the upper-bound branch.
EXPECTED_UCOR6 = 66303 if UPPER_BOUND else 54774  # Preserve all passage six-port members in the upper-bound branch.
EXPECTED_MASS = 33003  # Preserve every authoritative native MASS element.
EXPECTED_ORIGINAL_AXIAL = 73692  # Preserve all source prestressed ropes including four downpulls.
EXPECTED_C2_AXIAL = 0 if UPPER_BOUND else 11529  # Require no released passage axial members in the upper-bound branch.
EXPECTED_INITIAL_ROWS = 589536  # Consume and audit eight global stress rows for each original axial member.
EXPECTED_EQUATIONS = 21312 if UPPER_BOUND else 17280  # Restore every passage rotation equation in the upper-bound branch.
EXPECTED_BOUNDARY = 4116  # Preserve all C3-R2 support and numerical gauge rows.
EXPECTED_UCOR_SECTIONS = 987 if UPPER_BOUND else 187  # Preserve all 986 parent groups plus one activator in the upper-bound branch.
EXPECTED_AXIAL_SECTIONS = 3 if UPPER_BOUND else 803  # Preserve only the three original axial groups when no passage members are released.
EXPECTED_GRAVITY_GROUPS = {"E_BEARING", "E_GANTRY", "E_DOWNPULL", "E_MASS"}  # Freeze the only four directly loaded families.


class BuildError(RuntimeError):  # Represent one stable fail-closed C3-U violation.
    pass  # Keep the semantic exception intentionally behavior-free.


def require(condition: bool, code: str, detail: str) -> None:  # Enforce one explicit build contract.
    if not condition:  # Reject every condition not positively established.
        raise BuildError(f"{code}: {detail}")  # Surface a stable code with bounded context.


def sha256_file(path: Path) -> str:  # Compute one exact file identity by streaming.
    digest = hashlib.sha256()  # Initialize a fresh SHA-256 state.
    with path.open("rb") as handle:  # Read large artifacts without retaining them.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Traverse fixed blocks to EOF.
            digest.update(block)  # Bind every exact byte once.
    return digest.hexdigest()  # Return the lowercase hexadecimal identity.


def append_error(error: BaseException) -> None:  # Persist every trapped failure in the common append-only ledger.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)  # Ensure the bounded evidence directory exists.
    record = {"at_utc": datetime.now(timezone.utc).isoformat(), "script": Path(__file__).name, "type": type(error).__name__, "message": str(error)}  # Build one compact error record.
    with ERROR_LOG.open("a", encoding="utf-8") as handle:  # Open only in append mode.
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")  # Append exactly one complete JSON record.


def load_json(path: Path) -> dict[str, object]:  # Read one reviewed JSON mapping under an explicit gate.
    require(path.is_file(), "JSON_INPUT_MISSING", str(path))  # Require the selected input artifact.
    try:  # Convert malformed bytes into a stable build failure.
        value = json.loads(path.read_text(encoding="utf-8"))  # Decode exact UTF-8 content.
    except json.JSONDecodeError as error:  # Catch malformed JSON explicitly.
        raise BuildError(f"JSON_INPUT_INVALID: {path}: {error}") from error  # Preserve a fail-closed diagnostic.
    require(isinstance(value, dict), "JSON_INPUT_NOT_MAPPING", str(path))  # Require a top-level mapping.
    return value  # Return the reviewed document.


def keyword_attributes(line: str) -> dict[str, str]:  # Parse comma-separated CalculiX keyword attributes.
    fields = [field.strip() for field in line.split(",")]  # Preserve the leading keyword separately.
    attributes: dict[str, str] = {}  # Accumulate normalized key-value attributes.
    for field in fields[1:]:  # Traverse optional attributes only.
        if "=" in field:  # Admit only explicit key-value fields.
            key, value = field.split("=", 1)  # Split at the first equals sign.
            attributes[key.strip().upper()] = value.strip().upper()  # Normalize identifiers case-insensitively.
    return attributes  # Return the exact attribute mapping.


def read_element_inverse() -> dict[int, int]:  # Recover dense-to-source element identity from the frozen ledger.
    require(sha256_file(ELEMENT_MAP) == EXPECTED_ELEMENT_MAP_SHA256, "ELEMENT_MAP_SHA256_MISMATCH", str(ELEMENT_MAP))  # Reject ledger drift.
    inverse: dict[int, int] = {}  # Map dense solver identifiers back to source labels.
    with ELEMENT_MAP.open(encoding="utf-8", newline="") as handle:  # Decode the deterministic CSV ledger.
        reader = csv.DictReader(handle)  # Bind named columns.
        require(reader.fieldnames == ["source_element", "solver_element"], "ELEMENT_MAP_HEADER_MISMATCH", repr(reader.fieldnames))  # Require the exact schema.
        for row in reader:  # Traverse every source element once.
            source, solver = int(row["source_element"]), int(row["solver_element"])  # Parse both reversible labels.
            require(solver not in inverse, "ELEMENT_MAP_DENSE_DUPLICATE", str(solver))  # Reject dense collisions.
            inverse[solver] = source  # Preserve the inverse mapping.
    require(len(inverse) == 172994 and set(inverse) == set(range(1, 172995)), "ELEMENT_MAP_DOMAIN_MISMATCH", str(len(inverse)))  # Require the complete source-element range.
    return inverse  # Return the frozen inverse identity.


def project_stress(direction: tuple[float, float, float], tensor: tuple[float, float, float, float, float, float]) -> float:  # Project one global symmetric stress tensor onto the current member axis.
    nx, ny, nz = direction  # Select direction cosines.
    sxx, syy, szz, sxy, sxz, syz = tensor  # Select Sxx,Syy,Szz,Sxy,Sxz,Syz ordering.
    return sxx * nx * nx + syy * ny * ny + szz * nz * nz + 2.0 * sxy * nx * ny + 2.0 * sxz * nx * nz + 2.0 * syz * ny * nz  # Evaluate n transpose S n.


def unit_direction(point_i: tuple[float, float, float], point_j: tuple[float, float, float], eid: int) -> tuple[float, float, float]:  # Form one frozen member direction.
    vector = tuple(point_j[index] - point_i[index] for index in range(3))  # Form the I-to-J chord.
    length = math.sqrt(sum(value * value for value in vector))  # Measure frozen length.
    require(length > 1.0e-9 and math.isfinite(length), "UCAB3_MEMBER_LENGTH_INVALID", str(eid))  # Reject a zero or nonfinite member.
    return tuple(value / length for value in vector)  # Return normalized direction cosines.


def parse_r2(path: Path) -> dict[str, object]:  # Reread the complete C3-R2 static deck and derive every UCAB3 property independently.
    nodes: dict[int, tuple[float, float, float]] = {}  # Index all dense frozen coordinates.
    axial: dict[int, dict[str, object]] = {}  # Index all T3D2 members before conversion.
    solid_sections: dict[str, tuple[str, float]] = {}  # Map each T3D2 elset to material and area.
    elastic: dict[str, float] = {}  # Map material names to axial modulus.
    density: dict[str, float] = {}  # Map material names to tonne-per-volume density.
    stress: dict[int, list[tuple[float, float, float, float, float, float]]] = {}  # Preserve all eight global stress tensors per original member.
    element_counts: Counter[str] = Counter()  # Count exact source element types.
    boundary_rows = 0  # Count exact boundary DOFs.
    equation_rows = 0  # Count exact equation cards.
    gravity_groups: set[str] = set()  # Collect directly loaded element sets.
    user_sections = 0  # Count inherited UCOR6 property groups.
    current_node = False  # Track coordinate rows.
    current_element_type: str | None = None  # Track one element connectivity block.
    current_element_elset: str | None = None  # Track its exact elset.
    current_material: str | None = None  # Track the active material definition.
    current_data: str | None = None  # Track ELASTIC or DENSITY data rows.
    current_solid: tuple[str, str] | None = None  # Track one pending solid-section area row.
    current_initial = False  # Track global integration-point stress rows.
    current_boundary = False  # Track model-level boundary rows.
    with path.open("r", encoding="ascii", newline="") as handle:  # Stream the reviewed large deck once.
        iterator = iter(handle)  # Permit exact equation block consumption.
        for raw in iterator:  # Traverse every record.
            line = raw.strip()  # Normalize surrounding whitespace for parsing only.
            upper = line.upper()  # Parse keywords case-insensitively.
            if not line or line.startswith("**"):  # Ignore blank and comment records.
                continue  # Preserve no state changes for comments.
            if upper.startswith("*"):  # Enter one new keyword context.
                current_node = upper == "*NODE" or upper.startswith("*NODE,")  # Admit only coordinate NODE cards, not NODE PRINT/FILE.
                current_element_type = None  # Close any prior connectivity block.
                current_element_elset = None  # Close its elset.
                current_data = None  # Close material data unless reset below.
                current_solid = None  # Close a pending section unless reset below.
                current_initial = upper.startswith("*INITIAL CONDITIONS, TYPE=STRESS")  # Select only the prestress block.
                current_boundary = upper == "*BOUNDARY"  # Select only the model-level boundary block.
                if upper.startswith("*ELEMENT,"):  # Parse one element header.
                    attributes = keyword_attributes(line)  # Recover exact TYPE and ELSET fields.
                    current_element_type = attributes.get("TYPE")  # Select its element type.
                    current_element_elset = attributes.get("ELSET")  # Select its element set.
                    require(current_element_type is not None and current_element_elset is not None, "ELEMENT_HEADER_INVALID", line)  # Require both attributes.
                elif upper.startswith("*MATERIAL,"):  # Start one material definition.
                    current_material = keyword_attributes(line).get("NAME")  # Select its normalized name.
                    require(current_material is not None, "MATERIAL_NAME_MISSING", line)  # Require an explicit name.
                elif upper == "*ELASTIC":  # Select the next elastic data row.
                    require(current_material is not None, "ELASTIC_WITHOUT_MATERIAL", line)  # Require an active material.
                    current_data = "ELASTIC"  # Mark one pending modulus row.
                elif upper == "*DENSITY":  # Select the next density data row.
                    require(current_material is not None, "DENSITY_WITHOUT_MATERIAL", line)  # Require an active material.
                    current_data = "DENSITY"  # Mark one pending density row.
                elif upper.startswith("*SOLID SECTION,"):  # Select one T3D2 section assignment.
                    attributes = keyword_attributes(line)  # Recover ELSET and MATERIAL.
                    group, material = attributes.get("ELSET"), attributes.get("MATERIAL")  # Select both identities.
                    require(group is not None and material is not None, "SOLID_SECTION_HEADER_INVALID", line)  # Require complete ownership.
                    current_solid = (group, material)  # Mark the next area row.
                elif upper.startswith("*USER SECTION,"):  # Count inherited UCOR sections only.
                    user_sections += 1  # Preserve exact parent group count.
                elif upper == "*EQUATION":  # Consume one complete equation block.
                    try:  # Convert truncation into a stable failure.
                        term_count = int(next(iterator).strip())  # Read its declared arity.
                        term_fields = [field.strip() for field in next(iterator).split(",")]  # Read its single generated body row.
                    except StopIteration as error:  # Catch unexpected EOF.
                        raise BuildError("TRUNCATED_EQUATION_BLOCK") from error  # Fail before publication.
                    require(len(term_fields) == 3 * term_count, "EQUATION_ARITY_MISMATCH", str(term_count))  # Require complete sparse terms.
                    equation_rows += 1  # Count one equation.
                continue  # Complete keyword handling.
            if current_node:  # Parse one dense coordinate row.
                fields = [field.strip() for field in line.split(",")]  # Split node and XYZ.
                require(len(fields) == 4, "NODE_ROW_INVALID", line[:120])  # Require three coordinates.
                node = int(fields[0])  # Parse the dense node label.
                require(node not in nodes, "NODE_DUPLICATE", str(node))  # Reject coordinate collisions.
                nodes[node] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Preserve frozen coordinates.
            elif current_element_type is not None:  # Parse one connectivity row.
                fields = [int(field.strip()) for field in line.split(",")]  # Parse element and nodes.
                eid = fields[0]  # Select dense element identity.
                element_counts[current_element_type] += 1  # Count its type.
                if current_element_type == "T3D2":  # Preserve only axial members for conversion.
                    require(len(fields) == 3 and eid not in axial, "T3D2_CONNECTIVITY_INVALID", line)  # Require one unique two-node member.
                    axial[eid] = {"source_elset": current_element_elset, "node_i": fields[1], "node_j": fields[2]}  # Preserve exact ownership and topology.
            elif current_data == "ELASTIC":  # Parse one isotropic material row.
                require(current_material is not None, "ELASTIC_MATERIAL_STATE_LOST", line)  # Require the active material.
                values = [float(field.strip()) for field in line.split(",")]  # Parse modulus and optional Poisson ratio.
                require(values and values[0] > 0.0, "ELASTIC_DATA_INVALID", line)  # Require positive modulus.
                elastic[current_material] = values[0]  # Preserve only axial modulus.
                current_data = None  # Consume one data row.
            elif current_data == "DENSITY":  # Parse one density row.
                require(current_material is not None, "DENSITY_MATERIAL_STATE_LOST", line)  # Require the active material.
                value = float(line.split(",")[0].strip())  # Parse the first density value.
                require(value >= 0.0 and math.isfinite(value), "DENSITY_DATA_INVALID", line)  # Require finite nonnegative density.
                density[current_material] = value  # Preserve tonne-per-volume density.
                current_data = None  # Consume one data row.
            elif current_solid is not None:  # Parse one axial area row.
                group, material = current_solid  # Recover pending ownership.
                area = float(line.split(",")[0].strip())  # Parse area in square millimetres.
                require(area > 0.0 and group not in solid_sections, "SOLID_SECTION_AREA_INVALID", repr((group, area)))  # Require one positive assignment.
                solid_sections[group] = (material, area)  # Preserve exact section data.
                current_solid = None  # Consume one area row.
            elif current_initial:  # Parse one global stress tensor row.
                fields = [field.strip() for field in line.split(",")]  # Split eid, IP, and six tensor components.
                require(len(fields) == 8, "INITIAL_STRESS_ROW_INVALID", line[:160])  # Require exact tensor arity.
                eid, integration_point = int(fields[0]), int(fields[1])  # Parse identity and IP.
                require(eid in axial and 1 <= integration_point <= 8, "INITIAL_STRESS_IDENTITY_INVALID", repr((eid, integration_point)))  # Restrict stress to original axial members.
                tensor = tuple(float(value) for value in fields[2:8])  # Parse Sxx,Syy,Szz,Sxy,Sxz,Syz.
                require(all(math.isfinite(value) for value in tensor), "INITIAL_STRESS_NONFINITE", str(eid))  # Reject invalid state.
                stress.setdefault(eid, []).append(tensor)  # Preserve every expanded integration-point tensor.
            elif current_boundary:  # Count one explicit boundary range.
                fields = [int(field.strip()) for field in line.split(",")]  # Parse node and DOF range.
                require(len(fields) in (2, 3), "BOUNDARY_ROW_INVALID", line)  # Require supported zero-value syntax.
                boundary_rows += (fields[2] if len(fields) == 3 else fields[1]) - fields[1] + 1  # Count each constrained DOF.
            elif upper.startswith("E_") and ", GRAV," in upper:  # Parse one emitted gravity data row.
                gravity_groups.add(line.split(",", 1)[0].strip().upper())  # Preserve its exact elset.
    require(len(nodes) == EXPECTED_NODES and set(nodes) == set(range(1, EXPECTED_NODES + 1)), "R2_NODE_DOMAIN_MISMATCH", str(len(nodes)))  # Preserve dense geometry including splits.
    require(element_counts == Counter({"T3D2": EXPECTED_UCAB3, "UCOR6": EXPECTED_UCOR6, "MASS": EXPECTED_MASS}), "R2_ELEMENT_COUNTS_MISMATCH", repr(element_counts))  # Require exact parent representation.
    require(len(axial) == EXPECTED_UCAB3 and len(solid_sections) == EXPECTED_AXIAL_SECTIONS, "R2_AXIAL_SECTION_COUNT_MISMATCH", repr((len(axial), len(solid_sections))))  # Preserve every selected axial group.
    require(sum(len(values) for values in stress.values()) == EXPECTED_INITIAL_ROWS and len(stress) == EXPECTED_ORIGINAL_AXIAL, "R2_INITIAL_STRESS_COUNT_MISMATCH", repr((len(stress), sum(len(values) for values in stress.values()))))  # Require eight rows for every original axial member.
    require(equation_rows == EXPECTED_EQUATIONS and boundary_rows == EXPECTED_BOUNDARY and user_sections == EXPECTED_UCOR_SECTIONS, "R2_CONSTRAINT_OR_UCOR_SECTION_COUNT_MISMATCH", repr((equation_rows, boundary_rows, user_sections)))  # Preserve non-axial topology.
    require(gravity_groups == EXPECTED_GRAVITY_GROUPS, "R2_GRAVITY_GROUP_MISMATCH", repr(gravity_groups))  # Require exact gravity scope.
    for eid, record in axial.items():  # Derive one exact UCAB3 property record per physical member.
        group = str(record["source_elset"])  # Select its parent axial group.
        require(group in solid_sections, "AXIAL_SOLID_SECTION_MISSING", repr((eid, group)))  # Require physical area/material ownership.
        material, area = solid_sections[group]  # Recover source material and area.
        require(material in elastic and material in density, "AXIAL_MATERIAL_DATA_MISSING", repr((eid, material)))  # Require E and density.
        node_i, node_j = int(record["node_i"]), int(record["node_j"])  # Select dense endpoints.
        direction = unit_direction(nodes[node_i], nodes[node_j], eid)  # Recover current frozen chord direction.
        tensors = stress.get(eid, [])  # Select original prestress or the empty C2 state.
        projected = [project_stress(direction, tensor) for tensor in tensors]  # Project every global tensor independently.
        require(len(projected) in (0, 8), "AXIAL_STRESS_IP_COUNT_INVALID", repr((eid, len(projected))))  # Admit only C2 zero-force or complete original state.
        if projected:  # Derive one frozen initial axial force.
            spread = max(projected) - min(projected)  # Measure eight-IP projection drift.
            scale = max(1.0, max(abs(value) for value in projected))  # Form a stable relative scale.
            require(spread <= 1.0e-9 * scale and min(projected) > 0.0, "AXIAL_STRESS_PROJECTION_INVALID", repr((eid, min(projected), max(projected))))  # Require consistent positive tension.
            sigma = sum(projected) / len(projected)  # Average only numerically identical projected values.
        else:  # Assign the released passage state.
            sigma = 0.0  # Preserve zero initial force exactly.
        ea = elastic[material] * area  # Form axial rigidity in newtons.
        initial_force = sigma * area  # Form positive frozen tension in newtons.
        line_mass = density[material] * area  # Form line mass in tonnes per millimetre.
        require(ea > 0.0 and initial_force >= 0.0 and line_mass >= 0.0 and all(math.isfinite(value) for value in (ea, initial_force, line_mass)), "UCAB3_PROPERTY_INVALID", str(eid))  # Require the kernel contract.
        record.update({"material": material, "area_mm2": area, "E_mpa": elastic[material], "density_t_per_mm3": density[material], "EA_N": ea, "N0_N": initial_force, "mu_t_per_mm": line_mass, "stress_ip_count": len(projected), "projected_sigma_mpa_min": min(projected) if projected else 0.0, "projected_sigma_mpa_max": max(projected) if projected else 0.0, "gravity": group in EXPECTED_GRAVITY_GROUPS})  # Bind complete physical and audit properties.
    require(sum(1 for record in axial.values() if int(record["stress_ip_count"]) == 8) == EXPECTED_ORIGINAL_AXIAL and sum(1 for record in axial.values() if int(record["stress_ip_count"]) == 0) == EXPECTED_C2_AXIAL, "UCAB3_PRESTRESS_FAMILY_COUNT_MISMATCH", str(len(axial)))  # Preserve original/C2 partition.
    return {"nodes": nodes, "axial": axial, "element_counts": element_counts, "solid_sections": solid_sections, "initial_rows": EXPECTED_INITIAL_ROWS, "equations": equation_rows, "boundary": boundary_rows, "gravity_groups": sorted(gravity_groups), "ucor_sections": user_sections}  # Return complete transformation data.


def publish_ledger(axial: dict[int, dict[str, object]], inverse: dict[int, int]) -> dict[str, object]:  # Publish one reversible UCAB3 property ledger.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)  # Ensure the evidence directory exists.
    descriptor, temporary_name = tempfile.mkstemp(prefix=".C3-U-properties.", suffix=".csv.tmp", dir=ARTIFACTS)  # Allocate a private same-filesystem stage.
    temporary = Path(temporary_name)  # Normalize the staging path.
    fields = ["solver_eid", "source_eid", "kind", "source_elset", "property_elset", "node_i", "node_j", "area_mm2", "E_mpa", "density_t_per_mm3", "EA_N", "N0_N", "mu_t_per_mm", "gravity", "stress_ip_count", "projected_sigma_mpa_min", "projected_sigma_mpa_max"]  # Freeze the independent preflight schema.
    try:  # Prevent partial ledger publication.
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:  # Own and close the stage descriptor once.
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")  # Emit deterministic CSV records.
            writer.writeheader()  # Publish the exact schema first.
            for eid in sorted(axial):  # Traverse dense physical elements deterministically.
                record = axial[eid]  # Select derived properties.
                source_eid = inverse.get(eid)  # Recover original source identity.
                require(source_eid is not None, "UCAB3_SOURCE_IDENTITY_MISSING", str(eid))  # Exclude synthetic non-source members.
                group = str(record["source_elset"])  # Select source family.
                kind = "original_prestressed_axial" if int(record["stress_ip_count"]) == 8 else "c2_released_passage_axial"  # Distinguish the physical state partition.
                row = {"solver_eid": eid, "source_eid": source_eid, "kind": kind, "source_elset": group, "property_elset": f"CAB{eid}", "node_i": record["node_i"], "node_j": record["node_j"], "area_mm2": f"{float(record['area_mm2']):.12e}", "E_mpa": f"{float(record['E_mpa']):.12e}", "density_t_per_mm3": f"{float(record['density_t_per_mm3']):.15e}", "EA_N": f"{float(record['EA_N']):.12e}", "N0_N": f"{float(record['N0_N']):.12e}", "mu_t_per_mm": f"{float(record['mu_t_per_mm']):.15e}", "gravity": "1" if bool(record["gravity"]) else "0", "stress_ip_count": record["stress_ip_count"], "projected_sigma_mpa_min": f"{float(record['projected_sigma_mpa_min']):.12e}", "projected_sigma_mpa_max": f"{float(record['projected_sigma_mpa_max']):.12e}"}  # Serialize stable physical digits.
                writer.writerow(row)  # Emit one complete member record.
            handle.flush()  # Flush Python buffers.
            os.fsync(handle.fileno())  # Sync staged bytes before publication.
        digest = sha256_file(temporary)  # Bind the complete ledger.
        destination = ARTIFACTS / f"{'C3-UB-U' if UPPER_BOUND else 'C3-U'}_UCAB3_properties_{digest[:16]}.csv"  # Select a representation-specific content-addressed name.
        if destination.exists():  # Preserve a prior identical artifact.
            require(sha256_file(destination) == digest, "UCAB3_LEDGER_COLLISION", str(destination))  # Reject differing bytes under one name.
        else:  # Publish the first exact instance.
            os.link(temporary, destination)  # Publish atomically without replacement.
        return {"path": str(destination.relative_to(BASE)), "sha256": digest, "bytes": destination.stat().st_size, "rows": len(axial), "fields": fields}  # Return immutable ledger evidence.
    finally:  # Remove only this invocation's private stage.
        temporary.unlink(missing_ok=True)  # Prevent orphaned incomplete bytes.


class DeckWriter:  # Stream deterministic ASCII while tracking exact bytes and lines.
    def __init__(self, handle) -> None:  # Bind one private binary stage.
        self.handle = handle  # Preserve the open staging handle.
        self.digest = hashlib.sha256()  # Initialize exact deck identity.
        self.bytes = 0  # Count serialized bytes.
        self.lines = 0  # Count serialized lines.

    def line(self, value: object = "") -> None:  # Serialize one newline-terminated ASCII record.
        payload = (str(value) + "\n").encode("ascii")  # Encode deterministic solver text.
        self.handle.write(payload)  # Stream without retaining the full deck.
        self.digest.update(payload)  # Bind exact serialized bytes.
        self.bytes += len(payload)  # Accumulate exact bytes.
        self.lines += 1  # Accumulate exact lines.


def emit_ucab_properties(writer: DeckWriter, axial: dict[int, dict[str, object]]) -> None:  # Emit one exact three-constant property set per physical axial member.
    for eid in sorted(axial):  # Traverse dense element identities deterministically.
        record = axial[eid]  # Select its derived property record.
        property_elset = f"CAB{eid}"  # Form one unique property set without changing topology sets.
        writer.line(f"*ELSET, ELSET={property_elset}")  # Declare one member-specific property set.
        writer.line(str(eid))  # Bind exactly one physical UCAB3 member.
        writer.line(f"*USER SECTION, ELSET={property_elset}, MATERIAL={record['material']}, CONSTANTS=3")  # Bind the frozen kernel contract.
        writer.line(f"{float(record['EA_N']):.12e}, {float(record['N0_N']):.12e}, {float(record['mu_t_per_mm']):.12e}")  # Keep every USER SECTION token within CalculiX's f20.0 reader while preserving twelve significant decimals.


def transform_deck(source: Path, expected_sha256: str, stage_name: str, axial: dict[int, dict[str, object]]) -> dict[str, object]:  # Convert one C3-R2 deck to target-free C3-U without changing non-axial topology.
    require(sha256_file(source) == expected_sha256, "R2_DECK_SHA256_MISMATCH", str(source))  # Reject parent drift.
    SOLVER.mkdir(parents=True, exist_ok=True)  # Ensure the isolated output directory exists.
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".C3-U-{stage_name}.", suffix=".inp.tmp", dir=SOLVER)  # Allocate a private same-filesystem stage.
    temporary = Path(temporary_name)  # Normalize the stage path.
    handle_out = os.fdopen(descriptor, "wb")  # Bind the stage in binary mode.
    writer = DeckWriter(handle_out)  # Track every emitted byte.
    stats: Counter[str] = Counter()  # Count every transformation independently.
    axial_groups = {str(record["source_elset"]).upper() for record in axial.values()}  # Precompute the exact 803 stock section groups once.
    skip_initial = False  # Track removal of the stock expanded-element stress block.
    skip_solid_data = False  # Track removal of one T3D2 area row.
    inserted_properties = False  # Track the complete member-property insertion.
    try:  # Ensure any failure removes only the private stage.
        with source.open("r", encoding="ascii", newline="") as handle_in:  # Stream exact parent ASCII records.
            for raw in handle_in:  # Traverse every parent line once.
                line = raw.rstrip("\r\n")  # Normalize only the record terminator.
                upper = line.strip().upper()  # Parse keywords case-insensitively.
                if skip_solid_data:  # Consume one removed area row.
                    require(not upper.startswith("*"), "SOLID_SECTION_DATA_MISSING", line)  # Require the expected scalar data.
                    skip_solid_data = False  # Close the one-row removal state.
                    stats["solid_section_data_removed"] += 1  # Count exact removed area rows.
                    continue  # Do not emit stock T3D2 section data.
                if skip_initial and not upper.startswith("*"):  # Consume one stock integration-point stress row.
                    stats["initial_rows_removed"] += 1  # Count exact expanded-element state rows.
                    continue  # Do not emit stock-only initial conditions.
                if skip_initial and upper.startswith("*"):  # Close stress removal at the next keyword.
                    skip_initial = False  # Resume normal keyword transformation.
                if writer.lines == 1 and (line.startswith("C3-UB-SM_DIAGNOSTIC C3-UB") if UPPER_BOUND else line.startswith("C3-SM_DIAGNOSTIC C3-R2")):  # Replace only the exact selected parent title line.
                    writer.line("C3-UB-U_DIAGNOSTIC; exact UCAB3 prestressed axial ports; C1 sticky; all passage UCOR6 six-port upper bound; C3 rigid equalizers" if UPPER_BOUND else "C3-U_DIAGNOSTIC C3; exact small-motion UCAB3 axial ports; C1 sticky; C2 released passage trusses; C3 rigid equalizers")  # Publish accurate diagnostic identity.
                    writer.line("** UCAB3 preserves every physical member EA, frozen positive tension, consistent line mass, residual end force, and direct gravity; it is not a ROM.")  # Disclose the physical condensation scope.
                    stats["title_replaced"] += 1  # Count the exact title delta.
                    continue  # Do not copy the stale title.
                if upper.startswith("*USER ELEMENT,") and "TYPE=UCOR6" in upper:  # Extend the reviewed custom-element declarations.
                    writer.line(line)  # Preserve the exact UCOR6 declaration.
                    writer.line("*USER ELEMENT, TYPE=UCAB3, NODES=2, INTEGRATION POINTS=1, MAXDOF=3")  # Declare the coupon-passed axial kernel contract.
                    stats["ucab3_declarations"] += 1  # Count one exact declaration.
                    continue  # Avoid writing the UCOR6 line twice.
                element_match = re.match(r"^\*ELEMENT,\s*TYPE=T3D2,\s*ELSET=([^,\s]+)\s*$", upper)  # Parse one axial connectivity header.
                if element_match:  # Convert every stock axial block.
                    writer.line(f"*ELEMENT, TYPE=UCAB3, ELSET={element_match.group(1)}")  # Preserve elset/connectivity with translation-only native topology.
                    stats["t3d2_headers_converted"] += 1  # Count all 803 exact axial groups.
                    continue  # Do not copy the stock header.
                if upper.startswith("*SOLID SECTION,"):  # Inspect one possible stock axial section.
                    attributes = keyword_attributes(line)  # Recover its elset.
                    if attributes.get("ELSET") in axial_groups:  # Remove only reviewed axial group assignments.
                        skip_solid_data = True  # Consume its following area row.
                        stats["solid_section_headers_removed"] += 1  # Count one exact removal.
                        continue  # Do not emit the stock section header.
                if upper.startswith("*INITIAL CONDITIONS, TYPE=STRESS"):  # Remove the expanded T3D2 prestress representation.
                    skip_initial = True  # Consume all following tensor rows.
                    stats["initial_headers_removed"] += 1  # Count the sole parent header.
                    continue  # Do not emit the stock-only card.
                if re.match(r"^\*ELSET,\s*ELSET=M\d+\s*$", upper) and not inserted_properties:  # Insert UCAB3 properties before native MASS scalar sets.
                    emit_ucab_properties(writer, axial)  # Emit one independently auditable property set per physical member.
                    inserted_properties = True  # Close the insertion gate.
                    stats["ucab3_user_sections"] += len(axial)  # Count all physical members.
                writer.line(line)  # Preserve every unmodified parent record exactly.
        require(not skip_solid_data and not skip_initial, "TRANSFORM_BLOCK_UNTERMINATED", repr((skip_solid_data, skip_initial)))  # Reject truncated parent blocks.
        handle_out.flush()  # Flush all staged bytes.
        os.fsync(handle_out.fileno())  # Sync complete bytes before publication.
        handle_out.close()  # Close the stage before hashing.
    except BaseException:  # Remove only this private stage on any failure.
        try:  # Attempt bounded descriptor cleanup without masking the original failure.
            handle_out.close()  # Close the stage if still open.
        finally:  # Always remove the explicit private path.
            temporary.unlink(missing_ok=True)  # Prevent incomplete bytes from appearing runnable.
        raise  # Preserve the original traceback and nonzero exit.
    require(inserted_properties and stats["ucab3_declarations"] == 1 and stats["t3d2_headers_converted"] == EXPECTED_AXIAL_SECTIONS, "UCAB3_INSERTION_OR_HEADER_COUNT_MISMATCH", repr(dict(stats)))  # Require complete selected axial conversion.
    require(stats["solid_section_headers_removed"] == EXPECTED_AXIAL_SECTIONS and stats["solid_section_data_removed"] == EXPECTED_AXIAL_SECTIONS, "UCAB3_SOLID_SECTION_REMOVAL_MISMATCH", repr(dict(stats)))  # Remove every selected stock axial assignment once.
    require(stats["initial_headers_removed"] == 1 and stats["initial_rows_removed"] == EXPECTED_INITIAL_ROWS and stats["ucab3_user_sections"] == EXPECTED_UCAB3, "UCAB3_PROPERTY_OR_STRESS_REMOVAL_MISMATCH", repr(dict(stats)))  # Require complete property transfer.
    digest = sha256_file(temporary)  # Bind the complete staged deck.
    destination = SOLVER / f"{'C3-UB-U_DIAGNOSTIC' if UPPER_BOUND else 'C3-U_DIAGNOSTIC'}_{stage_name}_{digest[:16]}.inp"  # Select a content-addressed representation-specific name.
    if destination.exists():  # Preserve a prior identical artifact.
        require(sha256_file(destination) == digest, "C3U_DECK_COLLISION", str(destination))  # Reject differing bytes under one name.
    else:  # Publish the first exact instance.
        os.link(temporary, destination)  # Publish atomically without replacement.
    temporary.unlink(missing_ok=True)  # Remove only this invocation's stage.
    return {"path": str(destination.relative_to(BASE)), "sha256": digest, "bytes": destination.stat().st_size, "lines": writer.lines, "stage": stage_name, "transform_counts": dict(sorted(stats.items()))}  # Return immutable deck evidence.


def publish_json(prefix: str, value: object) -> dict[str, object]:  # Publish one deterministic content-addressed JSON artifact.
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")  # Serialize complete stable bytes.
    digest = hashlib.sha256(payload).hexdigest()  # Bind exact content.
    destination = ARTIFACTS / f"{prefix}_{digest[:16]}.json"  # Select an immutable destination.
    if destination.exists():  # Preserve a prior identical artifact.
        require(destination.read_bytes() == payload, "JSON_OUTPUT_COLLISION", str(destination))  # Reject differing bytes under one name.
    else:  # Publish the first exact instance.
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{prefix}.", suffix=".json.tmp", dir=ARTIFACTS)  # Allocate a private stage.
        temporary = Path(temporary_name)  # Normalize its path.
        try:  # Prevent partial JSON publication.
            with os.fdopen(descriptor, "wb") as handle:  # Own and close the descriptor exactly once.
                handle.write(payload)  # Write all deterministic bytes.
                handle.flush()  # Flush Python buffers.
                os.fsync(handle.fileno())  # Sync the staged evidence.
            os.link(temporary, destination)  # Publish without replacement.
        finally:  # Remove only this invocation's stage.
            temporary.unlink(missing_ok=True)  # Prevent orphaned partial bytes.
    return {"path": str(destination.relative_to(BASE)), "sha256": digest, "bytes": len(payload)}  # Return immutable evidence identity.


def inline_comment_audit(path: Path) -> dict[str, object]:  # Enforce the user-required same-line comment rule on this generator.
    violations: list[int] = []  # Collect nonempty physical lines lacking a hash comment.
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # Traverse every source line once.
        if line.strip() and "#" not in line:  # Detect a nonempty uncommented physical line.
            violations.append(number)  # Preserve its exact line number.
    require(not violations, "INLINE_COMMENT_AUDIT_FAILED", repr(violations[:20]))  # Fail before deck generation on any violation.
    return {"path": str(path.relative_to(BASE)), "nonempty_lines": sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()), "violations": violations, "status": "PASS"}  # Publish bounded lint evidence.


def main() -> None:  # Build paired target-free C3-U decks without executing the candidate solver.
    script_audit = inline_comment_audit(Path(__file__))  # Enforce same-line comments before any output.
    require(sha256_file(R2_MANIFEST) == EXPECTED_R2_MANIFEST_SHA256, "R2_MANIFEST_SHA256_MISMATCH", str(R2_MANIFEST))  # Bind the exact preflight-passed source state.
    require(CANDIDATE_BINARY.is_file() and os.access(CANDIDATE_BINARY, os.X_OK) and sha256_file(CANDIDATE_BINARY) == CANDIDATE_BINARY_SHA256, "UCAB3_CANDIDATE_BINARY_MISMATCH", str(CANDIDATE_BINARY))  # Bind but never execute the candidate.
    r2 = load_json(R2_MANIFEST)  # Read the exact C3-R2 build record.
    expected_parent_variant = "C3-UB-SM_DIAGNOSTIC" if UPPER_BOUND else "C3-SM_DIAGNOSTIC_C3_R2"  # Freeze the exact selected parent identity.
    require(r2.get("variant") == expected_parent_variant and r2.get("target_access") == "NONE", "R2_MANIFEST_SCOPE_INVALID", repr((r2.get("variant"), r2.get("target_access"))))  # Preserve no-target scope.
    static_source = BASE / str(r2["decks"]["static_only"]["path"])  # Resolve the static parent deck.
    modal_source = BASE / str(r2["decks"]["static_plus_6"]["path"])  # Resolve the six-mode parent deck.
    parsed = parse_r2(static_source)  # Derive all physical UCAB3 properties from frozen geometry and global stress.
    inverse = read_element_inverse()  # Recover every original source element identity.
    ledger = publish_ledger(parsed["axial"], inverse)  # Publish the reversible property ledger before decks.
    static_deck = transform_deck(static_source, str(r2["decks"]["static_only"]["sha256"]), "static", parsed["axial"])  # Generate the static pause deck.
    modal_deck = transform_deck(modal_source, str(r2["decks"]["static_plus_6"]["sha256"]), "m06", parsed["axial"])  # Generate the six-mode resource gate deck.
    static_bytes = (BASE / str(static_deck["path"])).read_bytes()  # Read exact static prefix bytes.
    with (BASE / str(modal_deck["path"])).open("rb") as handle:  # Read only the corresponding modal prefix.
        modal_prefix = handle.read(len(static_bytes))  # Select exact static-length bytes.
    require(modal_prefix == static_bytes, "C3U_STATIC_PREFIX_MISMATCH", repr((static_deck["sha256"], modal_deck["sha256"])))  # Require identical topology, properties, loads, and reference step.
    manifest = {"schema": "catwalk.c3-ub-ucab3.build.v1" if UPPER_BOUND else "catwalk.c3-ucab3.build.v1", "status": "DECKS_GENERATED_TARGET_FREE_PREFLIGHT_REQUIRED_NOT_SOLVED", "runnable": False, "variant": "C3-UB-U_DIAGNOSTIC" if UPPER_BOUND else "C3-U_DIAGNOSTIC", "claims": {"production": False, "independent_reproduction": False, "frequency_reproduced": False, "ROM": False}, "parent_c3_r2": {"path": str(R2_MANIFEST.relative_to(BASE)), "sha256": EXPECTED_R2_MANIFEST_SHA256, "manifest_sha256": EXPECTED_R2_MANIFEST_SHA256, "static_sha256": r2["decks"]["static_only"]["sha256"], "modal_sha256": r2["decks"]["static_plus_6"]["sha256"]}, "decks": {"static_only": static_deck, "static_plus_6": modal_deck}, "static_prefix": {"byte_identical": True, "sha256": static_deck["sha256"]}, "representation": {"nodes": EXPECTED_NODES, "elements": EXPECTED_ELEMENTS, "UCAB3": EXPECTED_UCAB3, "UCOR6": EXPECTED_UCOR6, "MASS": EXPECTED_MASS, "stock_T3D2": 0, "stock_SOLID_SECTION": 0, "original_prestressed_axial": EXPECTED_ORIGINAL_AXIAL, "C2_zero_force_axial": EXPECTED_C2_AXIAL, "C2_restored_six_port_UCOR6": 11529 if UPPER_BOUND else 0, "initial_stress_rows_transferred_to_N0": EXPECTED_INITIAL_ROWS, "equations": EXPECTED_EQUATIONS, "boundary_rows": EXPECTED_BOUNDARY, "gravity_families": sorted(EXPECTED_GRAVITY_GROUPS)}, "ucab3_contract": {"type": "UCAB3", "nodes": 2, "integration_points": 1, "maxdof": 3, "constants": ["EA_N", "N0_N_positive_tension", "mu_t_per_mm"], "stiffness": "(EA/L) nnT + (N/L) (I-nnT)", "mass": "mu*L/6 [[2I,I],[I,2I]]", "initial_residual": "[-N*n,+N*n]", "gravity": "direct UCAB3 body load; no duplicate distributed mass"}, "property_ledger": ledger, "solver_candidate": {"path": str(CANDIDATE_BINARY), "sha256": CANDIDATE_BINARY_SHA256, "executed": False, "release": "RELEASED_COUPON_VERIFIED"}, "solver_binary": {"path": str(CANDIDATE_BINARY), "sha256": CANDIDATE_BINARY_SHA256, "status": "RELEASED_COUPON_VERIFIED", "executed": False, "receipt": {"path": "/tmp/ucab3-contingency-dmcXjg/evidence/UCAB3_C3U_RECEIPT.md", "sha256": "b5733d9b2871118cd17329685b521cd471d629c8bdaa4070e3dfe2ac1d39180c"}, "manifest": {"path": "/tmp/ucab3-contingency-dmcXjg/evidence/UCAB3_C3U_MANIFEST.json", "sha256": "d4dc09553c8b46d9ee35ce9c9f5b085f9d778c10d502967f8e80d9d93a4de709"}, "minimal_patch": {"path": "/tmp/ucab3-contingency-dmcXjg/evidence/ucab3_on_c0sm_final.minimal.patch", "sha256": "70852b902934494288a770e618db58328ee251188577dfdecac213e7e91c9171"}}, "generator": {"path": str(Path(__file__).relative_to(BASE)), "sha256": sha256_file(Path(__file__))}, "source_stress_audit": {"global_tensor_rows": EXPECTED_INITIAL_ROWS, "projection": "n^T S n at frozen selected C3 chord", "eight_ip_consistency": "PASS_IN_BUILDER", "positive_original_tension": True, "C2_N0": 0.0}, "code_audit": script_audit, "target_access": "NONE", "next_gate": "independent full-deck preflight; then one-thread assembly-only resource probe"}  # Bind topology, physics, released solver evidence, claim limits, and next gate.
    manifest_artifact = publish_json("C3-UB-U_build" if UPPER_BOUND else "C3-U_build", manifest)  # Publish representation-specific immutable build evidence.
    print(json.dumps({"status": manifest["status"], "manifest": manifest_artifact, "static_deck": static_deck, "modal_deck": modal_deck, "property_ledger": ledger}, ensure_ascii=False, indent=2, sort_keys=True))  # Publish one bounded machine-readable result.


if __name__ == "__main__":  # Execute only as the independent C3-U build entry point.
    try:  # Convert deliberate and unexpected failures into append-only evidence.
        main()  # Generate paired target-free decks and immutable ledgers.
    except BaseException as error:  # Capture every failed build.
        append_error(error)  # Persist the failure before termination.
        raise  # Preserve nonzero exit and full traceback.
