#!/usr/bin/env python3  # Build independent L2, G3-G6, manifest, and canonical Gate evidence for the PR9 qualification workflow.
import argparse  # Parse one explicit evidence operation and its immutable input paths.
import hashlib  # Bind every source and generated artifact to exact bytes.
import json  # Read and write deterministic machine-readable evidence receipts.
import math  # Evaluate independent vector norms, stress invariants, and finite-value checks.
import os  # Record workflow run identity without shell interpolation in evidence payloads.
import platform  # Record the exact operating-system and machine identity used by the numerical run.
import re  # Parse the restricted CalculiX INP and DAT records used by the independent L2 comparison.
import subprocess  # Execute and receipt calculation commands without hiding native exit codes.
import sys  # Record the exact Python runtime and mirror captured command output.
from datetime import datetime, timezone  # Timestamp recorded command boundaries in UTC.
from pathlib import Path  # Resolve all evidence files without implicit working-directory guesses.

STRUCTURAL_GROUPS = ("DECK_SHELLS", "CROSSBEAMS", "LONG_GIRDERS", "TOWER_COLUMNS", "TOWER_TOP_BEAMS", "MAIN_CABLES", "HANGERS", "WIND_ATTACH_LINKS", "WIND_CABLES")  # Freeze the source engineering component order independently of the main pipeline.
BLOCKING_ISSUES = ("A-MAIN-ANCHOR-INTERFACE-002", "A-MAIN-ANCHOR-Z-001", "A-TOWER-FOUNDATION-001", "C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001", "U-WIND-001")  # Freeze the six unresolved source-contract issues that code cannot close.
GATE_REQUIREMENTS = {"G3": ("critical-view units and coordinate transform", "accepted dimensions materials quantities and elevations", "zero unresolved critical conflicts", "dimension-chain error within approved tolerance", "source version and supersession", "accepted-value traceability", "critical-point overlay within tolerance", "bounded high-sensitivity assumptions"), "G4": ("manufacturing Part mapping", "component role position and source", "continuous primary load path", "no isolated supports connections cable systems or temporary works", "assembly and material schedule reconciliation", "zero critical orphans", "bounded low-confidence high-criticality objects", "inventory directly drives abstraction"), "G5": ("unique disposition for every component group", "Part-to-group-to-representation traceability", "continuous load path support anchorage initial force and control geometry", "equivalent-item source effect omission and validation", "no duplicated mass gravity accessory load or wind area", "response-based exclusion rationale", "parameterized high-sensitivity omissions", "representation contract drives downstream analysis", "unsupported solver features blocked or approved", "responsible approval bound to artifact digest"), "G6": ("stable geometry and interfaces", "closed right-handed coordinate systems", "critical coordinate and elevation tolerance", "zero invalid or disconnected topology", "explicit offsets and eccentricities", "complete merge log", "continuous topology load path", "drawing overlay pass", "bounded high-sensitivity geometry scenarios")}  # Enumerate every G3-G6 check required by the frozen bridge workflow.
REQUIRED_UPSTREAM = {"G3": ("evidence_graph", "dimension_register", "material_register", "conflict_register"), "G4": ("component_inventory", "part_component_map", "load_path_graph"), "G5": ("abstraction_decisions", "abstraction_validation_plan"), "G6": ("fem_geometry_ir", "topology_audit", "geometry_overlay_report")}  # Freeze the formal work products needed before any engineering Gate can pass.
SEMANTIC_EXCLUSIONS = (("generatedAtUtc",), ("anchorWindReconciliation", "generatedAtUtc"), ("contractCompatibilityAliases", "generatedAtUtc"))  # Exclude only three explicitly audited volatile metadata pointers from the semantic digest.
RUNNABLE_CASE_IDS = ("LC02_G_Q_SERVICE", "LC03_G_Q_ASYM_SERVICE", "LC04_G_W_SERVICE", "LC05_G_Q_EXTREME", "LC06_G_W_EXTREME", "LC07_G_Q_W_EXTREME", "LC08_ACC_HANGER_LOSS")  # Freeze the seven response-bearing cases required after the nominal LC01 qualification.
EXPECTED_BLOCKED_CASE_ID = "LC09_ACC_WIND_CABLE_LOSS"  # Freeze the sole solver-free expected block while formal wind-cable G3/G5 evidence remains unresolved.


def sha256_path(path: Path) -> str:  # Compute a deterministic SHA-256 digest from exact file bytes.
    digest = hashlib.sha256()  # Initialize an isolated digest for this file.
    with path.open("rb") as stream:  # Read bytes without newline or character normalization.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Bound memory use while consuming the complete file.
            digest.update(chunk)  # Extend the digest with this exact byte chunk.
    return digest.hexdigest()  # Return the lowercase hexadecimal identity.


def load_json(path: Path) -> object:  # Load strict JSON while rejecting duplicate keys and non-finite constants.
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:  # Convert one JSON object only after proving all keys are unique.
        result: dict[str, object] = {}  # Allocate the validated mapping.
        for key, value in items:  # Visit source-order key-value pairs exactly once.
            if key in result:  # Detect a duplicate key that ordinary json.loads would silently overwrite.
                raise RuntimeError(f"duplicate JSON key {key} in {path}")  # Fail closed on ambiguous evidence.
            result[key] = value  # Preserve the unique parsed field.
        return result  # Return the validated object mapping.
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(RuntimeError(f"non-finite JSON constant {value} in {path}")))  # Parse the entire UTF-8 evidence document strictly.


def write_json(path: Path, payload: object) -> None:  # Persist one deterministic newline-terminated JSON evidence file.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the explicit evidence parent path.
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Serialize finite data with stable key ordering.


def parse_inp(path: Path) -> tuple[dict[int, tuple[float, float, float]], dict[str, list[tuple[int, tuple[int, ...]]]], dict[str, set[int]]]:  # Independently parse nodes, primary element blocks, and explicit node sets from one CalculiX deck.
    nodes: dict[int, tuple[float, float, float]] = {}  # Store exact source coordinates by node id.
    groups: dict[str, list[tuple[int, tuple[int, ...]]]] = {}  # Store explicit primary element connectivity by ELSET.
    nsets: dict[str, set[int]] = {}  # Store explicit node-set membership for L2 selectors.
    mode = ""  # Track NODE, ELEMENT, NSET, or inactive parsing mode.
    active = ""  # Track the normalized active ELSET or NSET name.
    for raw in path.read_text(encoding="ascii", errors="strict").splitlines():  # Scan every immutable deck row in source order.
        line = raw.strip()  # Normalize surrounding whitespace for keyword decisions only.
        upper = line.upper()  # Cache a normalized keyword view.
        if re.match(r"^\*NODE(?:,|\s|$)", upper) and not re.match(r"^\*NODE\s+(PRINT|FILE)", upper):  # Detect the model node definition rather than output requests.
            mode, active = "NODE", ""  # Enter model-node parsing mode.
            continue  # Advance to node records.
        if upper.startswith("*ELEMENT"):  # Detect an explicit primary connectivity block.
            match = re.search(r"ELSET=([^,\s]+)", upper)  # Recover the primary ELSET label.
            active = match.group(1) if match else ""  # Normalize the component label.
            mode = "ELEMENT" if active else ""  # Enter element parsing only for a named group.
            groups.setdefault(active, []) if active else None  # Preserve continued explicit blocks.
            continue  # Advance to connectivity rows.
        if upper.startswith("*NSET"):  # Detect an explicit node-set block.
            match = re.search(r"NSET=([^,\s]+)", upper)  # Recover the source set label.
            active = match.group(1) if match else ""  # Normalize the set label.
            mode = "NSET" if active else ""  # Enter set parsing only for a named set.
            nsets.setdefault(active, set()) if active else None  # Preserve continued explicit sets.
            continue  # Advance to set member rows.
        if line.startswith("*"):  # Treat every other solver keyword as a data-block boundary.
            mode, active = "", ""  # Leave the previous data mode.
            continue  # Advance to the next source row.
        if not line or line.startswith("**"):  # Ignore blank rows and model comments.
            continue  # Preserve parser state across harmless comments.
        fields = [field.strip() for field in line.split(",") if field.strip()]  # Tokenize one restricted numeric data row.
        if mode == "NODE" and len(fields) >= 4 and fields[0].isdigit():  # Accept one complete Cartesian node record.
            nodes[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Preserve its exact coordinates.
        elif mode == "ELEMENT" and fields and fields[0].isdigit():  # Accept one explicit element connectivity row.
            groups[active].append((int(fields[0]), tuple(int(value) for value in fields[1:])))  # Preserve id and source node order.
        elif mode == "NSET":  # Consume explicit integer NSET members.
            nsets[active].update(int(value) for value in fields if value.isdigit())  # Add every explicit member exactly once.
    return nodes, groups, nsets  # Return the independent immutable model contract.


def parse_dat(path: Path) -> tuple[dict[int, tuple[float, float, float]], dict[int, list[tuple[float, float, float, float, float, float]]]]:  # Independently select the final complete displacement and stress records from a CalculiX DAT file.
    displacement_frames: list[dict[int, tuple[float, float, float]]] = []  # Preserve each printed displacement frame separately.
    stress_frames: list[dict[int, list[tuple[float, float, float, float, float, float]]]] = []  # Preserve each printed stress table separately without averaging frames.
    active_kind = ""  # Track the current DAT table type.
    active_displacements: dict[int, tuple[float, float, float]] | None = None  # Hold the current displacement frame.
    active_stresses: dict[int, list[tuple[float, float, float, float, float, float]]] | None = None  # Hold the current stress table.
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():  # Scan the complete solver output in source order.
        lower = raw.lower()  # Cache a case-normalized header view.
        if "displacements (vx,vy,vz)" in lower:  # Detect one displacement table header regardless of set label.
            active_displacements = {}  # Start a new independent displacement frame.
            displacement_frames.append(active_displacements)  # Preserve it in output order.
            active_stresses = None  # Leave stress parsing mode.
            active_kind = "U"  # Enter displacement row mode.
            continue  # Advance through the optional header spacing.
        if "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)" in lower:  # Detect one six-component stress table header.
            active_stresses = {}  # Start a new independent stress table.
            stress_frames.append(active_stresses)  # Preserve it in output order.
            active_displacements = None  # Leave displacement parsing mode.
            active_kind = "S"  # Enter stress row mode.
            continue  # Advance through the optional header spacing.
        if active_kind == "U":  # Parse numeric displacement rows under the active header.
            match = re.match(r"^\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s*$", raw)  # Match one node and three components exactly.
            if match and active_displacements is not None:  # Accept only a complete numeric result row.
                active_displacements[int(match.group(1))] = tuple(float(match.group(index)) for index in range(2, 5))  # Preserve the final vector by source node id.
            elif raw.strip() and active_displacements:  # End a populated table on the first unrelated nonblank row.
                active_kind = ""  # Leave displacement parsing until a new header.
        elif active_kind == "S":  # Parse numeric stress rows under the active header.
            match = re.match(r"^\s*(\d+)\s+(\d+)\s+" + r"\s+".join([r"([-+0-9.Ee]+)"] * 6) + r"\s*$", raw)  # Match element, integration point, and six stress components.
            if match and active_stresses is not None:  # Accept only a complete numeric stress row.
                active_stresses.setdefault(int(match.group(1)), []).append(tuple(float(match.group(index)) for index in range(3, 9)))  # Preserve every integration-point tensor sample.
            elif raw.strip() and active_stresses:  # End a populated stress table on unrelated nonblank content.
                active_kind = ""  # Leave stress parsing until a new header.
    displacements: dict[int, tuple[float, float, float]] = {}  # Allocate the merged final displacement result.
    for frame in displacement_frames:  # Visit frames in chronological print order.
        displacements.update(frame)  # Keep the latest printed value for each node without mixing numeric samples.
    stresses: dict[int, list[tuple[float, float, float, float, float, float]]] = {}  # Allocate the merged final stress result by element.
    for frame in stress_frames:  # Visit separate ELSET tables in source output order.
        for element_id, samples in frame.items():  # Preserve the latest complete table for each element id.
            stresses[element_id] = list(samples)  # Replace rather than average across frames.
    return displacements, stresses  # Return independent final-result records.


def vector_metrics(reference: list[float], candidate: list[float], zero_floor: float = 1.0e-12) -> dict[str, float | int]:  # Compute transparent scale, trend, and difference measures without turning L2 into a calibration target.
    if len(reference) != len(candidate) or not reference:  # Require identical nonempty selector populations.
        raise RuntimeError("L2 vectors must have identical nonzero length")  # Fail closed before hiding missing output.
    if not all(math.isfinite(value) for value in reference + candidate):  # Require finite solver evidence for every selected value.
        raise RuntimeError("L2 vectors contain non-finite values")  # Reject NaN and infinity explicitly.
    norm_reference = math.sqrt(sum(value * value for value in reference))  # Compute the reference Euclidean norm.
    norm_candidate = math.sqrt(sum(value * value for value in candidate))  # Compute the candidate Euclidean norm.
    difference = [candidate[index] - reference[index] for index in range(len(reference))]  # Preserve signed pointwise deviation.
    norm_difference = math.sqrt(sum(value * value for value in difference))  # Compute the absolute L2 deviation.
    denominator = max(norm_reference * norm_candidate, zero_floor)  # Stabilize only the trend denominator near zero.
    cosine = sum(reference[index] * candidate[index] for index in range(len(reference))) / denominator  # Compute signed response-shape similarity.
    active = [index for index, value in enumerate(reference) if abs(value) > zero_floor]  # Exclude only numerically zero reference values from sign agreement.
    sign_agreement = sum(1 for index in active if reference[index] * candidate[index] > 0.0) / len(active) if active else 1.0  # Report the fraction of comparable values with matching response sign.
    return {"count": len(reference), "normReference": norm_reference, "normCandidate": norm_candidate, "scaleRatio": norm_candidate / max(norm_reference, zero_floor), "absoluteL2Difference": norm_difference, "relativeL2Difference": norm_difference / max(norm_reference, zero_floor), "cosineTrend": cosine, "signAgreement": sign_agreement, "maximumAbsoluteDifference": max(abs(value) for value in difference)}  # Return all metrics without an after-the-fact similarity threshold.


def von_mises(tensor: tuple[float, float, float, float, float, float]) -> float:  # Compute the invariant stress magnitude from a six-component symmetric tensor.
    sxx, syy, szz, sxy, sxz, syz = tensor  # Unpack global Cartesian tensor components.
    return math.sqrt(max(0.0, 0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * (sxy * sxy + sxz * sxz + syz * syz)))  # Evaluate the standard von Mises invariant in MPa.


def build_l2(args: argparse.Namespace) -> int:  # Generate the independent L2 trend-and-order cross-check receipt.
    reference_nodes, reference_groups, reference_nsets = parse_inp(args.reference_inp)  # Parse the frozen L2 model independently.
    candidate_nodes, candidate_groups, _candidate_nsets = parse_inp(args.candidate_inp)  # Parse the candidate response deck independently.
    reference_u, reference_s = parse_dat(args.reference_dat)  # Parse the frozen L2 result independently.
    candidate_u, candidate_s = parse_dat(args.candidate_dat)  # Parse the candidate result independently.
    monitor_ids = reference_nsets.get("MONITOR", set())  # Recover the frozen monitor selector.
    deck_ids = sorted(node for node in monitor_ids if node in reference_nodes and node in candidate_nodes and abs(reference_nodes[node][1]) <= 1.0e-6 and -1.0e-6 <= reference_nodes[node][0] <= 82000.0 + 1.0e-6)  # Select the common deck centerline deterministically.
    if len(deck_ids) != 83 or not set(deck_ids).issubset(reference_u) or not set(deck_ids).issubset(candidate_u):  # Require exact frozen centerline output coverage.
        raise RuntimeError(f"expected 83 complete deck centerline displacement nodes, got {len(deck_ids)}")  # Fail closed on a selector or output mismatch.
    reference_vertical = [reference_u[node][2] for node in deck_ids]  # Extract the frozen deck vertical response in source order.
    candidate_vertical = [candidate_u[node][2] for node in deck_ids]  # Extract the candidate deck vertical response on identical ids.
    reference_vector = [value for node in deck_ids for value in reference_u[node]]  # Flatten all three frozen displacement components.
    candidate_vector = [value for node in deck_ids for value in candidate_u[node]]  # Flatten all three candidate displacement components.
    reference_girders = {element_id for element_id, _connectivity in reference_groups.get("LONG_GIRDERS", [])}  # Freeze the L2 long-girder element selector.
    candidate_girders = {element_id for element_id, _connectivity in candidate_groups.get("LONG_GIRDERS", [])}  # Recover the candidate long-girder selector independently.
    if reference_girders != candidate_girders or len(reference_girders) != 164:  # Require exact common girder topology.
        raise RuntimeError("long-girder selector differs from the frozen 164-element contract")  # Refuse a topology-mismatched stress comparison.
    if not reference_girders.issubset(reference_s) or not reference_girders.issubset(candidate_s):  # Require raw stress output for every selected girder.
        raise RuntimeError("long-girder stress output is incomplete")  # Reject zero-fill or missing-result substitution.
    if any(len(reference_s[element]) != 8 or len(candidate_s[element]) != 8 for element in reference_girders):  # Require the frozen eight integration-point records per beam.
        raise RuntimeError("long-girder stress integration-point coverage is not exactly eight")  # Fail closed on truncated or mixed stress frames.
    reference_envelope = [max(von_mises(sample) for sample in reference_s[element]) for element in sorted(reference_girders)]  # Compute the bending-preserving frozen maximum-IP envelope.
    candidate_envelope = [max(von_mises(sample) for sample in candidate_s[element]) for element in sorted(candidate_girders)]  # Compute the candidate maximum-IP envelope on identical ids.
    receipt = {"schema": "zhaqing-l2-cross-check-v1", "status": "PASS", "qualificationRole": "independent trend and order-of-magnitude evidence only; never a calibration target", "inputSha256": {"referenceInp": sha256_path(args.reference_inp), "referenceDat": sha256_path(args.reference_dat), "candidateInp": sha256_path(args.candidate_inp), "candidateDat": sha256_path(args.candidate_dat)}, "basis": {"units": "N-mm-MPa", "coordinateSystemId": "CS-BRIDGE-001", "loadCase": "LC01_G_DEAD permanent-load response", "referenceLimitation": "screening model has no calibrated fabrication-state prestress", "candidateStage": "response about accepted equilibrium_state", "similarityThresholdApplied": False}, "selectors": {"deckCenterlineNodeIds": deck_ids, "longGirderElementIds": sorted(reference_girders)}, "metrics": {"deckVerticalDisplacement": vector_metrics(reference_vertical, candidate_vertical), "deckDisplacementVector": vector_metrics(reference_vector, candidate_vector), "longGirderMaxIntegrationPointVonMises": vector_metrics(reference_envelope, candidate_envelope)}, "referenceGolden": {"deckVerticalL2Mm": math.sqrt(sum(value * value for value in reference_vertical)), "deckMinimumU3Mm": min(reference_vertical), "deckMinimumU3Node": deck_ids[reference_vertical.index(min(reference_vertical))], "longGirderEnvelopeL2MPa": math.sqrt(sum(value * value for value in reference_envelope)), "longGirderMaximumEnvelopeMPa": max(reference_envelope), "longGirderMaximumEnvelopeElement": sorted(reference_girders)[reference_envelope.index(max(reference_envelope))]}}  # Publish full transparent comparison metrics without declaring L3 correct because it resembles L2.
    write_json(args.output, receipt)  # Persist the independent comparison receipt.
    return 0  # Report successful evidence generation.


def build_semantic_digest(args: argparse.Namespace) -> int:  # Generate full and semantic source-contract identities from an explicit exclusion list.
    payload = load_json(args.contract)  # Strictly parse the frozen contract without silently overwriting duplicate keys.
    if not isinstance(payload, dict):  # Require the expected top-level object contract.
        raise RuntimeError("source contract must be a JSON object")  # Fail closed on an incompatible evidence file.
    canonical = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))  # Deep-copy the finite JSON value before applying semantic exclusions.
    removed: list[str] = []  # Preserve every excluded pointer for independent review.
    for pointer in SEMANTIC_EXCLUSIONS:  # Apply only the three predeclared volatile metadata exclusions.
        target: object = canonical  # Start pointer traversal at the copied contract root.
        for token in pointer[:-1]:  # Traverse every parent object in the explicit pointer.
            if not isinstance(target, dict) or token not in target:  # Require the audited contract shape before deleting a field.
                raise RuntimeError(f"semantic exclusion pointer missing: {'/'.join(pointer)}")  # Stop instead of broadening the exclusion rule.
            target = target[token]  # Advance to the next explicit parent object.
        if not isinstance(target, dict) or pointer[-1] not in target:  # Require the final volatile key exactly once.
            raise RuntimeError(f"semantic exclusion key missing: {'/'.join(pointer)}")  # Fail closed on contract-shape drift.
        del target[pointer[-1]]  # Remove only the explicitly audited volatile field.
        removed.append("/" + "/".join(pointer))  # Record its JSON Pointer in the receipt.
    semantic_bytes = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")  # Canonically serialize all remaining engineering content.
    receipt = {"schema": "zhaqing-source-contract-digest-v1", "status": "PASS", "contractPath": str(args.contract), "fullSha256": sha256_path(args.contract), "semanticSha256": hashlib.sha256(semantic_bytes).hexdigest(), "canonicalizer": "json-sort-keys-utf8-compact-v1", "excludedJsonPointers": removed, "semanticIdentityRole": "change classification only; fullSha256 remains authoritative"}  # Publish both identities and exact exclusion semantics.
    write_json(args.output, receipt)  # Persist the digest receipt beside the frozen contract.
    return 0  # Report successful deterministic digest generation.


def build_toolchain(args: argparse.Namespace) -> int:  # Capture exact runner, Python, CalculiX, and linked-library identities for provenance.
    ccx_requested = Path(args.ccx)  # Preserve the caller-provided solver path.
    ccx_real = ccx_requested.resolve(strict=True)  # Resolve the exact executable bytes used by calculation.
    python_real = Path(sys.executable).resolve(strict=True)  # Resolve the exact Python interpreter bytes running this recorder.
    os_release = Path("/etc/os-release")  # Resolve the hosted-runner operating-system identity file.
    version_result = subprocess.run([str(ccx_real), "-v"], text=True, capture_output=True, check=False)  # Query the native solver version without shell parsing.
    version_identity_pass = version_result.returncode == 201 and version_result.stdout == "\nThis is Version 2.17\n\n" and not version_result.stderr  # Accept only the exact Ubuntu 22.04 CalculiX 2.17 information response observed from the pinned binary.
    package_result = subprocess.run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n", "calculix-ccx"], text=True, capture_output=True, check=False)  # Query the exact installed package identity.
    ldd_result = subprocess.run(["ldd", str(ccx_real)], text=True, capture_output=True, check=False)  # Resolve dynamic runtime dependencies through the system loader tool.
    library_records: list[dict[str, object]] = []  # Accumulate exact linked-library paths and digests.
    for raw in ldd_result.stdout.splitlines():  # Inspect every loader dependency row deterministically.
        tokens = raw.replace("=>", " ").split()  # Normalize the two ordinary ldd row forms without invoking a shell.
        candidates = [Path(token) for token in tokens if token.startswith("/")]  # Select only absolute resolved library paths.
        if candidates and candidates[0].is_file():  # Preserve one real file record for each resolved dependency row.
            path = candidates[0].resolve()  # Normalize symlinked system library paths.
            library_records.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)})  # Bind the dynamic library to exact bytes.
    thread_keys = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")  # Freeze numerical thread-control environment names.
    receipt = {"schema": "zhaqing-toolchain-v1", "status": "PASS" if version_identity_pass and package_result.returncode == 0 and package_result.stdout == "calculix-ccx\t2.17-3\tamd64\n" and not package_result.stderr and ldd_result.returncode == 0 else "FAIL", "runner": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "platform": platform.platform(), "runnerOs": os.environ.get("RUNNER_OS"), "runnerArch": os.environ.get("RUNNER_ARCH"), "imageOs": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion"), "locale": os.environ.get("LANG"), "timezone": os.environ.get("TZ"), "threadEnvironment": {key: os.environ.get(key) for key in thread_keys}, "osReleaseSha256": sha256_path(os_release) if os_release.is_file() else None, "osReleaseText": os_release.read_text(encoding="utf-8") if os_release.is_file() else None}, "python": {"executable": sys.executable, "realpath": str(python_real), "version": sys.version, "implementation": platform.python_implementation(), "bytes": python_real.stat().st_size, "sha256": sha256_path(python_real)}, "calculix": {"requestedPath": str(ccx_requested), "realpath": str(ccx_real), "versionIdentityPass": version_identity_pass, "versionExitCode": version_result.returncode, "versionStdout": version_result.stdout, "versionStderr": version_result.stderr, "packageExitCode": package_result.returncode, "packageStdout": package_result.stdout, "packageStderr": package_result.stderr, "packageRecord": package_result.stdout.rstrip("\n"), "bytes": ccx_real.stat().st_size, "sha256": sha256_path(ccx_real), "lddExitCode": ldd_result.returncode, "lddText": ldd_result.stdout, "libraries": library_records}}  # Publish complete reproducible runtime identity while preserving every raw version and package stream byte decoded by the fixed locale.
    write_json(args.output, receipt)  # Persist the exact toolchain receipt before calculation.
    return 0 if receipt["status"] == "PASS" else 2  # Fail preflight if any required tool identity query failed.


def run_recorded(args: argparse.Namespace) -> int:  # Execute one command and persist argv, time bounds, exit status, and exact stdout/stderr digests.
    if not args.argv:  # Require a concrete executable and argument vector after the separator.
        raise RuntimeError("run-recorded requires a command after --")  # Stop before recording an empty operation.
    argv = list(args.argv)  # Copy the exact argument vector without shell token reconstruction.
    if argv[0] == "--":  # Accept the conventional explicit option terminator emitted by workflow calls.
        argv = argv[1:]  # Remove only the separator, not any command argument.
    if not argv:  # Recheck after removing the optional separator.
        raise RuntimeError("run-recorded received no executable")  # Stop before an undefined subprocess call.
    cwd = args.cwd.resolve()  # Resolve the exact command working directory.
    start = datetime.now(timezone.utc)  # Capture the UTC start boundary immediately before process creation.
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)  # Execute directly without shell expansion and preserve the native exit code.
    end = datetime.now(timezone.utc)  # Capture the UTC completion boundary immediately after process exit.
    args.stdout.parent.mkdir(parents=True, exist_ok=True)  # Create the explicit stdout evidence directory.
    args.stderr.parent.mkdir(parents=True, exist_ok=True)  # Create the explicit stderr evidence directory.
    args.stdout.write_text(result.stdout, encoding="utf-8")  # Persist exact decoded standard output from the child process.
    args.stderr.write_text(result.stderr, encoding="utf-8")  # Persist exact decoded standard error from the child process.
    sys.stdout.write(result.stdout)  # Mirror child standard output into the Actions job log.
    sys.stderr.write(result.stderr)  # Mirror child standard error into the Actions job log.
    receipt = {"schema": "zhaqing-command-receipt-v1", "status": "PASS" if result.returncode == 0 else "FAIL", "id": args.id, "argv": argv, "cwd": str(cwd), "startUtc": start.isoformat(), "endUtc": end.isoformat(), "exitCode": result.returncode, "stdout": {"path": str(args.stdout), "bytes": args.stdout.stat().st_size, "sha256": sha256_path(args.stdout)}, "stderr": {"path": str(args.stderr), "bytes": args.stderr.stat().st_size, "sha256": sha256_path(args.stderr)}}  # Publish every command fact needed to reproduce and audit its native outcome.
    write_json(args.receipt, receipt)  # Persist the command receipt after both streams are durable.
    return result.returncode  # Propagate the child's native status to the workflow.


def build_comment_gate(args: argparse.Namespace) -> int:  # Prove that every nonblank source line added by the qualification commit carries an explicit hash comment.
    command = ["git", "diff", "--unified=0", args.parent, args.child, "--", *args.paths]  # Build one non-shell diff command over only the declared auditable source paths.
    result = subprocess.run(command, cwd=args.cwd.resolve(), text=True, capture_output=True, check=False)  # Read the exact commit delta without invoking shell expansion.
    if result.returncode != 0:  # Require the repository and both audited revisions to be available.
        raise RuntimeError(f"comment Gate could not read commit diff: {result.stderr.strip()}")  # Fail closed rather than silently skipping source coverage.
    violations: list[dict[str, object]] = []  # Accumulate every uncommented added line with its diff location.
    active_path = ""  # Track the current repository path from the unified diff header.
    for line_number, raw in enumerate(result.stdout.splitlines(), 1):  # Inspect every diff row once while preserving diagnostic order.
        if raw.startswith("+++ b/"):  # Detect the destination path for the following added rows.
            active_path = raw[6:]  # Preserve the normalized repository-relative path.
            continue  # Exclude diff metadata from the source-line rule.
        if raw.startswith("+") and not raw.startswith("+++"):  # Select only newly added source content.
            content = raw[1:]  # Remove the unified-diff marker without altering source whitespace.
            if content.strip() and "#" not in content:  # Require every nonblank addition to contain an explicit hash comment marker.
                violations.append({"path": active_path, "diffLine": line_number, "content": content})  # Preserve the exact rejected line for review.
    receipt = {"schema": "zhaqing-added-line-comment-gate-v1", "status": "PASS" if not violations else "FAIL", "parent": args.parent, "child": args.child, "paths": list(args.paths), "addedLineCount": sum(1 for raw in result.stdout.splitlines() if raw.startswith("+") and not raw.startswith("+++") and raw[1:].strip()), "violations": violations}  # Publish deterministic coverage and all violations.
    write_json(args.output, receipt)  # Persist the Gate receipt even when a source line is rejected.
    return 0 if not violations else 2  # Make process success follow complete per-line comment coverage.


def build_ledger(args: argparse.Namespace) -> int:  # Generate the auditable G3-G6 engineering release ledger from frozen source evidence.
    contract = load_json(args.contract)  # Strictly parse the source contract carrying unresolved issues.
    schema = load_json(args.schema)  # Strictly parse the repository-owned formal gate-ledger JSON Schema.
    if not isinstance(schema, dict) or schema.get("$id") != "https://example.invalid/bridge-fem/schemas/gate_ledger.schema.json":  # Require the exact formal schema family before evaluating its profile.
        raise RuntimeError("unexpected formal gate-ledger schema identity")  # Reject a substituted or unrelated schema.
    contract_digest = sha256_path(args.contract)  # Bind every ledger check to exact source bytes.
    issue_ids = tuple(contract.get("blockingIssueIds", [])) if isinstance(contract, dict) else ()  # Recover declared blockers without inventing closure evidence.
    missing_declared = [issue for issue in BLOCKING_ISSUES if issue not in issue_ids]  # Detect any expected blocker missing from the current contract.
    gates: list[dict[str, object]] = []  # Accumulate G3 through G6 in workflow order.
    node_ids = {"G3": "N04", "G4": "N05", "G5": "N06", "G6": "N07"}  # Bind engineering Gates to the frozen workflow nodes.
    for gate_id in ("G3", "G4", "G5", "G6"):  # Evaluate every formal engineering Gate independently.
        checks: list[dict[str, object]] = []  # Accumulate one evidence-based record per required clause.
        required_products = REQUIRED_UPSTREAM[gate_id]  # Recover formal upstream artifact requirements.
        for index, requirement in enumerate(GATE_REQUIREMENTS[gate_id], 1):  # Visit every clause exactly once.
            product = required_products[min(index - 1, len(required_products) - 1)]  # Associate each clause with at least one formal upstream evidence class.
            checks.append({"checkId": f"{gate_id}-{index:02d}", "requirement": requirement, "metric": "formal accepted upstream evidence available and digest-bound", "operator": "all-required-evidence-present", "threshold": True, "actual": False, "status": "BLOCKED", "evidenceRefs": [{"path": str(args.contract), "sha256": contract_digest, "jsonPointer": "/blockingIssueIds"}], "assumptionRefs": [], "issueRefs": list(BLOCKING_ISSUES), "missingEvidenceClasses": [product], "blocking": True, "evaluator": "stress_coordination_evidence.py", "evaluatorVersion": "1"})  # Record absence rather than converting a missing approval into PASS.
        gates.append({"gateId": gate_id, "nodeId": node_ids[gate_id], "status": "BLOCKED", "checks": checks, "issueRefs": list(BLOCKING_ISSUES), "approvalRefs": []})  # Derive this Gate as blocked from its clause records.
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")  # Bind CI evidence to the Actions run while retaining a deterministic local fallback.
    ledger = {"artifactType": "gate_ledger", "schemaVersion": "1.0.0", "schemaRef": str(schema.get("$id")), "schemaSha256": sha256_path(args.schema), "projectId": "PRJ-ZHAQING-SUSPENSION-BRIDGE", "runId": f"RUN-{run_id}", "artifactId": f"ART-G3-G6-{contract_digest[:12]}", "status": "BLOCKED", "gateId": "G3-G6", "unitsPolicy": "UNIT-POLICY-001", "coordinateSystemId": "CS-BRIDGE-001", "inputArtifacts": [{"artifactId": "ART-SOURCE-CONTRACT", "sha256": contract_digest}], "assumptionRefs": [], "issueRefs": list(BLOCKING_ISSUES), "data": {"workflowId": "bridge-fem-static-review", "overallStatus": "BLOCKED", "gates": gates, "missingExpectedBlockingIssues": missing_declared, "releaseRule": "numerical qualification never overrides blocked G3-G6 evidence"}}  # Publish schema-bound engineering status independently of solver convergence.
    required_top = set(schema.get("required", []))  # Recover the formal top-level required-property profile directly from the schema.
    allowed_status = set(schema.get("$defs", {}).get("status", {}).get("enum", []))  # Recover the formal status enumeration directly from the schema.
    if not required_top.issubset(ledger) or ledger["status"] not in allowed_status or ledger["data"]["overallStatus"] not in allowed_status:  # Validate decisive formal top-level requirements without a floating third-party validator.
        raise RuntimeError("generated G3-G6 ledger violates the formal schema profile")  # Fail before publishing structurally invalid release evidence.
    if [gate["gateId"] for gate in gates] != ["G3", "G4", "G5", "G6"] or any(gate["status"] not in allowed_status for gate in gates):  # Require exact gate order and formal status values.
        raise RuntimeError("generated G3-G6 gate array violates the formal schema profile")  # Reject missing, reordered, or invalid gate records.
    write_json(args.output, ledger)  # Persist the single authoritative G3-G6 ledger.
    return 0  # Report successful ledger generation even though engineering release is truthfully blocked.


def build_case_matrix_gate(args: argparse.Namespace) -> int:  # Independently bind all seven runnable case summaries and VTK receipts plus the exact solver-free LC09 disposition.
    matrix = load_json(args.matrix)  # Read the producer matrix through duplicate-key and finite-value rejection.
    if not isinstance(matrix, dict) or matrix.get("schema") != "zhaqing-f3-load-case-matrix-v1":  # Require the exact reviewed aggregate schema before inspecting rows.
        raise RuntimeError("load-case matrix schema is missing or substituted")  # Stop before accepting an unrelated status file.
    acceptance = load_json(args.acceptance_contract)  # Read the source-controlled frozen load-case charter independently from producer output.
    load_case_contract = acceptance.get("loadCaseMatrixContract") if isinstance(acceptance, dict) else None  # Recover the exact approved matrix identities, thresholds, and dispositions.
    if not isinstance(acceptance, dict) or acceptance.get("schema") != "zhaqing-stress-coordination-acceptance-v1" or acceptance.get("status") != "FROZEN" or not isinstance(load_case_contract, dict) or load_case_contract.get("schema") != "zhaqing-load-case-matrix-contract-v1":  # Require both frozen charter schema identities before evaluating any case.
        raise RuntimeError("load-case acceptance contract is missing or substituted")  # Reject a matrix evaluated without its source-controlled numerical charter.
    contract_case_sha = load_case_contract.get("caseInputSha256")  # Recover each immutable source INP identity from the charter.
    contract_dispositions = load_case_contract.get("caseDisposition")  # Recover each reviewed run, screening, damage, or expected-block disposition.
    contract_thresholds = load_case_contract.get("caseThresholds")  # Recover the precommitted tangent trigger and final numerical limits.
    expected_thresholds = {"directTangentRelinearizationTriggerMaximumSuspensionIncrementToBaseRatio": 0.50, "directTangentTriggerIsNotANonlinearFinalAcceptanceLimit": True, "minimumActiveSuspensionTensionMPa": 1.0, "globalForceBalanceRelativeMaximum": 0.001, "maximumDetailedDisplacementMm": 1000.0, "exactNodalCoverage": 1.0, "exactStressCoverage": 1.0}  # Freeze the complete case numerical charter without allowing a partial threshold profile.
    case_short_ids = {"LC02_G_Q_SERVICE": "LC02", "LC03_G_Q_ASYM_SERVICE": "LC03", "LC04_G_W_SERVICE": "LC04", "LC05_G_Q_EXTREME": "LC05", "LC06_G_W_EXTREME": "LC06", "LC07_G_Q_W_EXTREME": "LC07", "LC08_ACC_HANGER_LOSS": "LC08", "LC09_ACC_WIND_CABLE_LOSS": "LC09"}  # Freeze explicit full-heading to charter-id mappings without fuzzy string inference.
    expected_dispositions = {"LC02": "RUN_F3_INCREMENT", "LC03": "RUN_F3_INCREMENT", "LC04": "RUN_PRIMARY_SYSTEM_WIND_SCREENING", "LC05": "RUN_F3_INCREMENT", "LC06": "RUN_PRIMARY_SYSTEM_WIND_SCREENING", "LC07": "RUN_PRIMARY_SYSTEM_WIND_SCREENING", "LC08": "RUN_STATIC_ALTERNATE_PATH_HANGER_1033", "LC09": "BLOCKED_EXPECTED_G3_G5"}  # Freeze the exact reviewed analysis disposition for every source case.
    expected_lc08_damage = {"group": "HANGERS", "sourceElementId": 1033, "orderedNodeIds": [294, 638], "survivorRenumbering": False}  # Freeze the stable source identity and no-renumber damage contract.
    expected_lc09_damage = {"group": "WIND_CABLES", "sourceElementId": 1072, "orderedNodeIds": [784, 785], "formalPreLossStateRequired": True}  # Freeze the blocked wind-cable identity and required unavailable pre-loss state.
    contract_complete = isinstance(contract_case_sha, dict) and isinstance(contract_dispositions, dict) and contract_thresholds == expected_thresholds and load_case_contract.get("referenceCaseId") == "LC01" and load_case_contract.get("runnableCaseIds") == [case_short_ids[case_id] for case_id in RUNNABLE_CASE_IDS] and load_case_contract.get("expectedBlockedCaseIds") == [case_short_ids[EXPECTED_BLOCKED_CASE_ID]] and contract_dispositions == expected_dispositions and load_case_contract.get("damageSelector", {}).get("LC08") == expected_lc08_damage and load_case_contract.get("damageSelector", {}).get("LC09") == expected_lc09_damage  # Require exact reviewed case coverage, all thresholds, dispositions, damage identities, and nonlinear trigger semantics.
    if not contract_complete:  # Detect incomplete case identities, thresholds, or disposition families before touching solver claims.
        raise RuntimeError("load-case acceptance contract matrix profile is incomplete or altered")  # Fail closed on a narrowed or result-adjusted qualification charter.
    baseline_sha = sha256_path(args.baseline)  # Bind every source and validator receipt to the exact archived LC01 mother deck.
    equilibrium_sha = sha256_path(args.equilibrium)  # Bind every case to the one persisted accepted F3 equilibrium state.
    acceptance_sha = sha256_path(args.acceptance_contract)  # Preserve the exact charter bytes used by this independent decision.
    load_cases_csv_sha = sha256_path(args.load_cases_csv)  # Bind the actual archived case registry bytes consumed by the producer and sealed package.
    if baseline_sha != load_case_contract.get("referenceInputSha256") or baseline_sha != acceptance.get("baseline", {}).get("inputSha256"):  # Require both charter locations to identify the same actual LC01 bytes.
        raise RuntimeError("load-case acceptance baseline identity does not match the archived LC01 input")  # Reject a detached or substituted mother deck.
    if load_cases_csv_sha != load_case_contract.get("loadCasesCsvSha256"):  # Require the actual registry bytes to match the precommitted charter identity.
        raise RuntimeError("load-case registry identity does not match the frozen acceptance contract")  # Reject a substituted registry even when producer receipts repeat the expected digest text.
    rows = matrix.get("cases")  # Recover compact producer rows for exact identity and digest checks.
    if not isinstance(rows, list) or len(rows) != len(RUNNABLE_CASE_IDS) + 1 or any(not isinstance(row, dict) for row in rows):  # Require one row per reviewed LC02-LC09 case.
        raise RuntimeError("load-case matrix row population is incomplete or malformed")  # Reject missing, surplus, or scalar rows.
    row_index = {str(row.get("caseId")): row for row in rows}  # Index each row by its explicit source case identity.
    expected_ids = {*RUNNABLE_CASE_IDS, EXPECTED_BLOCKED_CASE_ID}  # Freeze the complete matrix identity set independently from producer order.
    if set(row_index) != expected_ids or len(row_index) != len(rows):  # Reject duplicate aliases, omissions, and unreviewed cases.
        raise RuntimeError("load-case matrix case identities are incomplete, duplicated, or substituted")  # Stop before a valid case can hide another result.
    checks: dict[str, bool] = {}  # Accumulate one explicit independent decision for every runnable response and expected block.
    input_digests: dict[str, dict[str, str]] = {}  # Bind each case Gate to its exact summary, canonical DAT, VTK, exclusion, and validator bytes.
    for case_id in RUNNABLE_CASE_IDS:  # Verify every response-bearing case under the same strict VTK contract.
        case_root = args.calculation_root / "cases" / case_id  # Resolve the deterministic isolated solver and response directory.
        summary_path = case_root / "summary.json"  # Resolve the producer numerical and provenance receipt.
        canonical_path = case_root / "canonical-response.dat"  # Resolve the complete 783-node and 1070-cell response table.
        vtk_path = case_root / "stress-coordinated.vtk"  # Resolve the strict primary visualization bytes.
        wind_path = case_root / "wind-exclusion.json"  # Resolve the unchanged formal wind-system boundary.
        validation_path = args.receipts_root / f"{case_id}-vtk-validation.json"  # Resolve the independently parsed full-content VTK receipt.
        summary = load_json(summary_path)  # Strictly parse the producer case summary.
        validation = load_json(validation_path)  # Strictly parse the independent visualization receipt.
        row = row_index[case_id]  # Recover the matching compact matrix row.
        source_path = args.case_source_root / f"{case_id}.inp"  # Resolve the exact archived source INP whose CLOAD delta defines this case.
        ledger_path = case_root / "load-ledger.json"  # Resolve the independently inspectable source-minus-LC01 load ledger used by the solver path.
        case_inputs = {"sourceCase": source_path, "loadLedger": ledger_path, "summary": summary_path, "canonicalResponse": canonical_path, "vtk": vtk_path, "windExclusion": wind_path, "vtkValidation": validation_path}  # Freeze the source, load ledger, and complete decisive response file set for this case.
        if not all(path.is_file() for path in case_inputs.values()):  # Require every response artifact before digest computation.
            raise RuntimeError(f"case {case_id} is missing one or more decisive response files")  # Reject partial producer output without placeholder acceptance.
        input_digests[case_id] = {name: sha256_path(path) for name, path in case_inputs.items()}  # Recompute all case identities from exact sealed bytes.
        ledger = load_json(ledger_path)  # Strictly parse the audited source-only CLOAD delta receipt.
        short_id = case_short_ids[case_id]  # Resolve the charter key paired with this full immutable source heading.
        expected_source_sha = contract_case_sha.get(short_id) if isinstance(contract_case_sha, dict) else None  # Recover the approved exact INP digest for this case.
        source_bound = expected_source_sha == input_digests[case_id]["sourceCase"] and isinstance(summary, dict) and summary.get("schema") == "zhaqing-load-case-summary-v1" and summary.get("caseId") == case_id and summary.get("sourceCaseSha256") == expected_source_sha and isinstance(ledger, dict) and ledger.get("schema") == "zhaqing-f3-load-delta-ledger-v1" and ledger.get("status") == "PASS" and ledger.get("caseId") == case_id and ledger.get("sourceCaseSha256") == expected_source_sha and ledger.get("baseSourceSha256") == baseline_sha and ledger.get("loadCasesCsvSha256") == load_case_contract.get("loadCasesCsvSha256") and summary.get("loadLedgerSha256") == input_digests[case_id]["loadLedger"]  # Bind source bytes, case identity, load ledger, and producer summary without permitting cross-case relabeling.
        common_f3_bound = isinstance(summary, dict) and summary.get("sourceBaselineSha256") == baseline_sha and summary.get("equilibriumStateSha256") == equilibrium_sha and isinstance(summary.get("parentEvidence"), dict) and summary["parentEvidence"].get("baseSha256") == baseline_sha and summary["parentEvidence"].get("equilibriumStateSha256") == equilibrium_sha and isinstance(ledger, dict) and isinstance(ledger.get("parentEvidence"), dict) and ledger["parentEvidence"].get("equilibriumStateSha256") == equilibrium_sha  # Require every result and its load ledger to inherit the same accepted F3 mother state.
        validation_inputs = validation.get("inputs") if isinstance(validation, dict) else None  # Recover the independent validator-to-input digest bindings.
        validator_bound = isinstance(validation_inputs, dict) and set(validation_inputs) == {"baselineSha256", "datSha256", "equilibriumStateSha256", "summarySha256", "vtkSha256", "windExclusionSha256"} and validation_inputs.get("baselineSha256") == baseline_sha and validation_inputs.get("equilibriumStateSha256") == equilibrium_sha and validation_inputs.get("summarySha256") == input_digests[case_id]["summary"] and validation_inputs.get("datSha256") == input_digests[case_id]["canonicalResponse"] and validation_inputs.get("vtkSha256") == input_digests[case_id]["vtk"] and validation_inputs.get("windExclusionSha256") == input_digests[case_id]["windExclusion"]  # Require the PASS receipt to describe these exact source, common F3, and current response bytes with no omitted input identity.
        nonlinear_seed = summary.get("directTangentSeed") if isinstance(summary, dict) else None  # Recover any direct-tangent trigger evidence before accepting a nonlinear replacement.
        if case_id == "LC08_ACC_HANGER_LOSS":  # Treat alternate-path damage as an inherently nonlinear path without inventing a direct tangent seed.
            nonlinear_contract_pass = summary.get("corotationalRelinearizationRequired") is True and row.get("corotationalRelinearizationRequired") is True and summary.get("analysisMode") == "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION" and summary.get("corotationalRelinearizationCompleted") is True and row.get("corotationalRelinearizationCompleted") is True and nonlinear_seed is None  # Require the explicit completed damage re-equilibration contract and no fictitious seed.
        elif summary.get("corotationalRelinearizationRequired") is True:  # Enforce a complete seed-to-fixed-L0 replacement chain for every out-of-range intact case.
            nonlinear_contract_pass = row.get("corotationalRelinearizationRequired") is True and isinstance(nonlinear_seed, dict) and float(nonlinear_seed.get("maximumSuspensionIncrementToBaseRatio", 0.0)) > float(contract_thresholds["directTangentRelinearizationTriggerMaximumSuspensionIncrementToBaseRatio"]) and summary.get("analysisMode") == "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION" and summary.get("corotationalRelinearizationCompleted") is True and row.get("corotationalRelinearizationCompleted") is True and isinstance(summary.get("corotationalRelinearizationRequestSha256"), str) and summary.get("corotationalRelinearizationRequestSha256") == nonlinear_seed.get("requestSha256") == row.get("corotationalRelinearizationRequestSha256")  # Require matching trigger, request identity, declared analysis mode, and completion in summary and matrix row.
        else:  # Enforce the direct tangent profile only when the frozen trigger did not require nonlinear replacement.
            nonlinear_contract_pass = row.get("corotationalRelinearizationRequired") is False and nonlinear_seed is None and summary.get("analysisMode") == "F3_FIXED_L0_TANGENT_INCREMENT" and summary.get("corotationalRelinearizationCompleted") is not True and summary.get("corotationalRelinearizationRequestSha256") is None  # Reject hidden nonlinear claims, missing seeds, or mismatched direct-case disposition.
        if summary.get("analysisMode") == "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION":  # Bind every formal nonlinear response to its converged iteration receipt and terminal native solver bytes.
            iteration_paths = sorted(case_root.glob("*.outer-iterations.json"))  # Resolve the one terminal main-response convergence receipt without including nested reaction or pre-loss histories.
            nonlinear_evidence_bound = len(iteration_paths) == 1  # Require one unambiguous formal outer-iteration history in the case root.
            if nonlinear_evidence_bound:  # Parse and bind terminal native files only after unique history identity is established.
                iteration_path = iteration_paths[0]  # Select the sole case-root nonlinear convergence receipt.
                iteration_receipt = load_json(iteration_path)  # Strictly parse the complete fixed-L0 outer history.
                terminal_iteration = int(iteration_receipt.get("outerIterationCount", 0)) if isinstance(iteration_receipt, dict) else 0  # Recover the deterministic final native iteration number from the sole convergence receipt.
                terminal_stem = f"ZQ_{case_id}_NL_{terminal_iteration:02d}"  # Reconstruct the producer's exact terminal basename even when two confirmed iterations have identical bytes.
                terminal_deck_paths = [case_root / f"{terminal_stem}.inp"]  # Resolve the exact terminal native deck from convergence sequence identity.
                terminal_dat_paths = [case_root / f"{terminal_stem}.dat"]  # Resolve the exact terminal native DAT from convergence sequence identity.
                iteration_records = iteration_receipt.get("iterations") if isinstance(iteration_receipt, dict) else None  # Recover the declared ordered native outer-iteration records safely.
                nonlinear_evidence_bound = isinstance(iteration_receipt, dict) and iteration_receipt.get("schema") == "zhaqing-fixed-l0-corotational-v1" and iteration_receipt.get("status") == "PASS" and terminal_iteration >= 1 and isinstance(iteration_records, list) and bool(iteration_records) and iteration_records[-1].get("outerIteration") == terminal_iteration and sha256_path(iteration_path) == summary.get("nonlinearIterationReceiptSha256") and iteration_receipt.get("terminalDeckSha256") == summary.get("fineDeckSha256") and iteration_receipt.get("terminalRawDatSha256") == summary.get("rawDatSha256") and all(path.is_file() for path in (*terminal_deck_paths, *terminal_dat_paths)) and sha256_path(terminal_deck_paths[0]) == summary.get("fineDeckSha256") and sha256_path(terminal_dat_paths[0]) == summary.get("rawDatSha256")  # Prove the declared closed sequence terminates at the exact deterministically named native deck and response summarized downstream.
                if nonlinear_evidence_bound:  # Extend sealed digest inventory only for a complete unique terminal chain.
                    input_digests[case_id].update({"nonlinearIteration": sha256_path(iteration_path), "terminalDeck": sha256_path(terminal_deck_paths[0]), "terminalRawDat": sha256_path(terminal_dat_paths[0])})  # Bind nonlinear history and terminal native source/result bytes into the matrix Gate and manifest.
        else:  # Direct tangent cases must not carry a nonlinear history masquerading as unused evidence.
            nonlinear_evidence_bound = not list(case_root.glob("*.outer-iterations.json")) and summary.get("nonlinearIterationReceiptSha256") is None  # Require the declared direct profile to have no formal nonlinear terminal receipt.
        summary_gates = summary.get("gates") if isinstance(summary, dict) else None  # Recover the complete producer numerical Gate map, including all-axis force balance.
        checks[f"{case_id}.sourceAndLoadLedgerPass"] = source_bound and common_f3_bound and nonlinear_evidence_bound  # Require one reviewed archived input, its exact load ledger, shared F3 state, and any declared nonlinear terminal chain.
        global_force_relative = summary.get("globalForceBalanceRelative") if isinstance(summary, dict) else None  # Recover the decisive all-axis closure metric added for every direct and nonlinear case.
        global_force_bound = isinstance(global_force_relative, (int, float)) and math.isfinite(float(global_force_relative)) and float(global_force_relative) <= float(contract_thresholds["globalForceBalanceRelativeMaximum"])  # Apply the exact frozen all-axis force tolerance independently from producer status.
        minimum_tension = summary.get("minimumFinalSuspensionAxialStressMPa") if isinstance(summary, dict) else None  # Recover the lowest active main-cable or hanger tensile stress under this final case state when published directly.
        if minimum_tension is None and isinstance(summary_gates, dict) and summary_gates.get("positiveFinalSuspensionTension") is True:  # Direct tangent summaries publish the positive-tension decision and detailed recovery inside reaction levels without duplicating the scalar at top level.
            selected_label = summary.get("reactionAudit", {}).get("selectedLevel") if isinstance(summary, dict) else None  # Recover the precommitted formal 10K reaction level identity.
            selected_levels = [level for level in summary.get("reactionAudit", {}).get("levels", []) if isinstance(level, dict) and level.get("label") == selected_label] if isinstance(summary, dict) else []  # Locate the unique selected audit recovery receipt.
            minimum_tension = selected_levels[0].get("anchorRecovery", {}).get("minimumFinalSuspensionAxialStressMPa") if len(selected_levels) == 1 else None  # Recover the same detailed suspension state consumed by the formal direct support audit.
        maximum_displacement = summary.get("maximumDisplacementMm") if isinstance(summary, dict) else None  # Recover the largest final structural translation under this case.
        response_bounds = isinstance(minimum_tension, (int, float)) and math.isfinite(float(minimum_tension)) and float(minimum_tension) >= float(contract_thresholds["minimumActiveSuspensionTensionMPa"]) and isinstance(maximum_displacement, (int, float)) and math.isfinite(float(maximum_displacement)) and float(maximum_displacement) <= float(contract_thresholds["maximumDetailedDisplacementMm"])  # Reapply frozen positive-tension and displacement limits independently from producer booleans.
        checks[f"{case_id}.summaryPass"] = isinstance(summary, dict) and summary.get("status") == "PASS" and isinstance(summary_gates, dict) and bool(summary_gates) and summary_gates.get("globalForceBalancePass") is True and all(value is True for value in summary_gates.values()) and global_force_bound and response_bounds and summary.get("formalPrimarySystemResponseComputed") is True and nonlinear_contract_pass and summary.get("canonicalResponseDatSha256") == input_digests[case_id]["canonicalResponse"] and summary.get("vtkSha256") == input_digests[case_id]["vtk"] and summary.get("windExclusionSha256") == input_digests[case_id]["windExclusion"]  # Require every producer numerical Gate, explicit frozen all-axis closure, final tension and displacement bounds, qualified primary response, mandatory fixed-L0 re-equilibration, and exact response digest binding.
        checks[f"{case_id}.matrixRowPass"] = row.get("status") == "PASS" and row.get("summarySha256") == input_digests[case_id]["summary"] and row.get("vtkSha256") == input_digests[case_id]["vtk"]  # Bind compact matrix status and visualization identity to the exact detailed receipt.
        checks[f"{case_id}.strictVtkPass"] = isinstance(validation, dict) and validation.get("status") == "PASS" and validator_bound  # Require complete independently reconstructed VTK semantics rather than a producer hash alone.
        if case_id == "LC08_ACC_HANGER_LOSS":  # Apply stable source-ID damage identity checks only to the alternate-path case.
            damage_event = summary.get("damageEvent") if isinstance(summary, dict) else None  # Recover the explicit pre-loss and removal contract.
            checks[f"{case_id}.damageIdentityPass"] = isinstance(damage_event, dict) and damage_event.get("group") == "HANGERS" and damage_event.get("sourceElementId") == 1033 and damage_event.get("orderedNodeIds") == [294, 638] and damage_event.get("survivorRenumbering") is False and damage_event.get("postLossActiveSuspensionElementCount") == 245 and damage_event.get("postLossRemovedSuspensionElementIds") == [1033] and float(damage_event.get("canonicalGhostTotalStressMPa", float("nan"))) == 0.0 and summary.get("removedElementIds") == [1033] and summary.get("analysisMode") == "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION" and summary.get("corotationalRelinearizationCompleted") is True  # Require the reviewed source member, exact 245-survivor topology, stable zero-total ghost, completed fixed-L0 nonlinear path, and no renumbering.
    blocked_root = args.calculation_root / "cases" / EXPECTED_BLOCKED_CASE_ID  # Resolve the isolated expected-block directory.
    disposition_path = blocked_root / "case-disposition.json"  # Resolve the sole decisive LC09 case-state receipt.
    blocked_source_path = args.case_source_root / f"{EXPECTED_BLOCKED_CASE_ID}.inp"  # Resolve the exact archived LC09 source whose formal response remains prohibited.
    blocked_ledger_path = blocked_root / "load-ledger.json"  # Resolve the audited LC09 source-load receipt published without invoking a solver.
    disposition = load_json(disposition_path)  # Strictly parse the expected G3/G5 block.
    blocked_ledger = load_json(blocked_ledger_path)  # Strictly parse the solver-free source identity and load ledger.
    blocked_row = row_index[EXPECTED_BLOCKED_CASE_ID]  # Recover the compact matching matrix row.
    prohibited_suffixes = {".dat", ".frd", ".sta", ".cvg", ".vtk"}  # Freeze response file types forbidden on the unsolved wind-cable loss path.
    prohibited_files = sorted(path.relative_to(blocked_root).as_posix() for path in blocked_root.rglob("*") if path.is_file() and path.suffix.lower() in prohibited_suffixes)  # Recursively enumerate any disguised numerical response after producer completion.
    blocked_source_sha = sha256_path(blocked_source_path)  # Recompute the LC09 input identity from archived source bytes.
    blocked_ledger_sha = sha256_path(blocked_ledger_path)  # Recompute the solver-free load ledger identity from exact bytes.
    expected_blockers = load_case_contract.get("windResponseBoundary", {}).get("blockedIssueIds")  # Recover the exact G3/G5 issue set precommitted by the charter.
    checks[f"{EXPECTED_BLOCKED_CASE_ID}.expectedBlockPass"] = isinstance(disposition, dict) and disposition.get("schema") == "zhaqing-case-disposition-v1" and disposition.get("caseId") == EXPECTED_BLOCKED_CASE_ID and disposition.get("status") == "BLOCKED_G3_G5" and disposition.get("matrixStatus") == "BLOCKED_EXPECTED" and disposition.get("numericalStatus") == "NOT_RUN" and disposition.get("engineeringStatus") == "BLOCKED" and disposition.get("formalResponseComputed") is False and disposition.get("solverInvocationCount") == 0 and disposition.get("sourceCaseSha256") == blocked_source_sha == contract_case_sha.get("LC09") and disposition.get("loadLedgerSha256") == blocked_ledger_sha and disposition.get("blockerIssueIds") == expected_blockers and disposition.get("responseArtifactsProduced") == [] and disposition.get("requestedDamage", {}).get("sourceStableElementId") == 1072 and disposition.get("requestedDamage", {}).get("sourceConnectivity") == [784, 785] and isinstance(disposition.get("parentEvidence"), dict) and disposition["parentEvidence"].get("baseSha256") == baseline_sha and disposition["parentEvidence"].get("equilibriumStateSha256") == equilibrium_sha and isinstance(blocked_ledger, dict) and blocked_ledger.get("schema") == "zhaqing-f3-load-delta-ledger-v1" and blocked_ledger.get("status") == "NOT_APPLIED_BLOCKED_G3_G5" and blocked_ledger.get("caseId") == EXPECTED_BLOCKED_CASE_ID and blocked_ledger.get("sourceCaseSha256") == blocked_source_sha and blocked_ledger.get("baseSourceSha256") == baseline_sha and blocked_ledger.get("loadCasesCsvSha256") == load_case_contract.get("loadCasesCsvSha256") and blocked_ledger.get("parentEvidence", {}).get("equilibriumStateSha256") == equilibrium_sha and not prohibited_files  # Require exact source, common F3, solver-free statuses, load ledger, blocker set, damage identity, empty response inventory, and complete absence of solver files.
    checks[f"{EXPECTED_BLOCKED_CASE_ID}.matrixRowPass"] = blocked_row.get("status") == "BLOCKED_EXPECTED" and blocked_row.get("solverInvocationCount") == 0 and blocked_row.get("loadLedgerSha256") == blocked_ledger_sha and blocked_row.get("dispositionSha256") == sha256_path(disposition_path)  # Bind aggregate expected-block status to the exact source-load and disposition bytes.
    matrix_declared_complete = matrix.get("status") == "COMPLETE_WITH_EXPECTED_BLOCKS" and matrix.get("numericalQualificationStatus") == "PASS" and matrix.get("engineeringReleaseStatus") == "BLOCKED" and matrix.get("loadCasesCsvSha256") == load_case_contract.get("loadCasesCsvSha256") and matrix.get("requiredRunnableCaseIds") == list(RUNNABLE_CASE_IDS) and matrix.get("expectedBlockedCaseIds") == [EXPECTED_BLOCKED_CASE_ID] and matrix.get("scopeComplete") is True and matrix.get("missingCaseIds") == [] and matrix.get("numericalFailureCaseIds") == [] and isinstance(matrix.get("parentEvidence"), dict) and matrix["parentEvidence"].get("baseSha256") == baseline_sha and matrix["parentEvidence"].get("equilibriumStateSha256") == equilibrium_sha  # Require producer status, exact scope, frozen registry, and common mother-state identity to agree with independently verified outcomes.
    checks["matrixProducerStatusConsistent"] = matrix_declared_complete  # Preserve the aggregate producer claim as one independently checked condition.
    numerical_status = "PASS" if all(checks.values()) else "FAIL"  # Accept only complete response, VTK, damage, and expected-block evidence simultaneously.
    receipt = {"schema": "zhaqing-load-case-matrix-gate-v1", "status": "PASS" if numerical_status == "PASS" else "FAIL", "numericalQualificationStatus": numerical_status, "engineeringReleaseStatus": "BLOCKED", "checks": checks, "matrixSha256": sha256_path(args.matrix), "acceptanceContractSha256": acceptance_sha, "baselineSha256": baseline_sha, "equilibriumStateSha256": equilibrium_sha, "loadCasesCsvSha256": load_cases_csv_sha, "caseInputSha256": input_digests, "lc09InputSha256": {"sourceCase": blocked_source_sha, "loadLedger": blocked_ledger_sha, "disposition": sha256_path(disposition_path)}, "meaning": "LC02-LC08 numerical qualification is complete while LC09 remains a verified solver-free expected block until G3/G5 closes"}  # Publish the independent charter, registry, mother state, every runnable input, and exact solver-free expected-block binding.
    write_json(args.output, receipt)  # Persist the matrix Gate before canonical Gate and manifest construction.
    return 0 if numerical_status == "PASS" else 2  # Make command status follow every independent case check.


def build_canonical_gate(args: argparse.Namespace) -> int:  # Combine numerical receipts while keeping engineering release status independent.
    equilibrium = load_json(args.equilibrium)  # Read the accepted P1/P2 state contract strictly.
    summary = load_json(args.summary)  # Read the P3/P4 numerical summary strictly.
    vtk = load_json(args.vtk_receipt)  # Read the independent strict VTK receipt strictly.
    l2 = load_json(args.l2_receipt)  # Read the independent L2 cross-check receipt strictly.
    ledger = load_json(args.ledger)  # Read the independent engineering Gate ledger strictly.
    case_matrix = load_json(args.case_matrix_gate)  # Read the independent LC02-LC09 Gate after every runnable case, strict VTK receipt, and expected blocker is evaluated.
    matrix_complete = isinstance(case_matrix, dict) and case_matrix.get("schema") == "zhaqing-load-case-matrix-gate-v1" and case_matrix.get("status") == "PASS" and case_matrix.get("numericalQualificationStatus") == "PASS" and case_matrix.get("engineeringReleaseStatus") == "BLOCKED"  # Require all runnable cases to qualify while the exact LC09 G3/G5 blocker remains visible.
    checks = {"equilibriumStatePass": isinstance(equilibrium, dict) and equilibrium.get("status") == "PASS", "detailedResponsePass": isinstance(summary, dict) and summary.get("status") == "PASS", "strictVtkPass": isinstance(vtk, dict) and vtk.get("status") == "PASS", "l2CrossCheckProduced": isinstance(l2, dict) and l2.get("status") == "PASS", "loadCaseMatrixComplete": matrix_complete, "engineeringLedgerBlockedAsExpected": isinstance(ledger, dict) and ledger.get("status") == "BLOCKED"}  # Evaluate nominal and matrix numerical evidence plus the release boundary without conflating them.
    numerical_status = "PASS" if all(value for key, value in checks.items() if key != "engineeringLedgerBlockedAsExpected") else "FAIL"  # Derive numerical qualification solely from numerical evidence.
    engineering_status = str(ledger.get("status")) if isinstance(ledger, dict) else "BLOCKED"  # Derive engineering status only from the ledger.
    receipt = {"schema": "zhaqing-canonical-gate-v1", "numericalQualificationStatus": numerical_status, "engineeringReleaseStatus": engineering_status, "checks": checks, "inputSha256": {"equilibriumState": sha256_path(args.equilibrium), "summary": sha256_path(args.summary), "vtkValidation": sha256_path(args.vtk_receipt), "l2Comparison": sha256_path(args.l2_receipt), "loadCaseMatrixGate": sha256_path(args.case_matrix_gate), "g3G6Ledger": sha256_path(args.ledger)}, "releaseBoundary": "PASS numerical qualification covers LC01 through LC08 numerical evidence while engineering release and LC09 formal wind-cable response remain blocked by G3/G5"}  # Publish the decisive nominal, independent case-matrix, and dual-status receipt.
    write_json(args.output, receipt)  # Persist the canonical Gate receipt before manifest enumeration.
    return 0 if numerical_status == "PASS" and engineering_status == "BLOCKED" else 2  # Require numerical acceptance and truthful blocked release state.


def artifact_role(relative: str) -> str:  # Assign stable semantic roles to decisive canonical artifact paths while retaining a generic role for auxiliary evidence.
    exact_roles = {"calculation/equilibrium_state.json": "equilibrium-state", "calculation/summary.json": "detailed-response-summary", "calculation/ZQ_STRESS_COORDINATED.inp": "detailed-response-input", "calculation/ZQ_STRESS_COORDINATED.dat": "raw-calculix-response", "calculation/canonical-response.dat": "canonical-primary-response", "calculation/stress-coordinated.vtk": "canonical-stress-vtk", "calculation/wind-exclusion.json": "wind-exclusion", "calculation/case-matrix.json": "load-case-matrix", "evidence/case-matrix-gate.json": "load-case-matrix-gate", "evidence/vtk-validation.json": "strict-vtk-validation", "evidence/l2-comparison.json": "l2-comparison", "evidence/g3-g6-ledger.json": "engineering-gate-ledger", "evidence/canonical-gate.json": "canonical-gate", "evidence/acceptance-contract.json": "acceptance-contract", "evidence/baseline/LC01_G_DEAD.inp": "frozen-baseline-input", "evidence/baseline/LC01_G_DEAD.dat": "frozen-baseline-response", "evidence/baseline/source_frozen_model_contract.json": "frozen-source-contract", "provenance/toolchain.json": "toolchain", "provenance/source-contract-digest.json": "source-contract-digest", "provenance/baseline-artifact.json": "baseline-artifact-metadata", "provenance/added-line-comment-gate.json": "added-line-comment-gate"}  # Freeze unique nominal, load-case-matrix, independent matrix-Gate, and provenance roles used by manifest cross-checks.
    exact_roles.update({"calculation/ZQ_REACTION_AUDIT_K1E9.inp": "reaction-audit-k-input", "calculation/ZQ_REACTION_AUDIT_K1E9.dat": "reaction-audit-k-response", "calculation/ZQ_REACTION_AUDIT_K1E9.stdout.log": "reaction-audit-k-log", "calculation/ZQ_REACTION_AUDIT_K1E10.inp": "reaction-audit-10k-input", "calculation/ZQ_REACTION_AUDIT_K1E10.dat": "reaction-audit-10k-response", "calculation/ZQ_REACTION_AUDIT_K1E10.stdout.log": "reaction-audit-10k-log"})  # Give both source-frozen reaction-audit decks, native responses, and solver logs unique decisive roles.
    if relative in exact_roles:  # Prefer one decisive unique role for a known canonical file.
        return exact_roles[relative]  # Return the frozen semantic role.
    if relative.startswith("provenance/sources/"):  # Identify exact checkout copies independently of generated concatenations.
        return "calculation-source"  # Mark source bytes for checkout equality verification.
    if relative.startswith("provenance/commands/") and relative.endswith(".json"):  # Identify command execution receipts.
        return "command-receipt"  # Mark explicit argv/time/exit/log evidence.
    if relative.startswith("logs/"):  # Identify human-readable command streams.
        return "command-log"  # Preserve logs as auxiliary evidence.
    return "evidence"  # Retain every other generated solver or provenance file without inventing a unique role.


def build_manifest(args: argparse.Namespace) -> int:  # Enumerate and hash every evidence file without creating a circular manifest digest.
    root = args.root.resolve()  # Resolve the exact artifact root once.
    output = args.output.resolve()  # Resolve the manifest path excluded from its own file list.
    detached = output.with_suffix(output.suffix + ".sha256")  # Resolve the detached manifest digest excluded from the file list.
    files: list[dict[str, object]] = []  # Accumulate exact artifact records in normalized path order.
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):  # Enumerate every regular artifact file recursively.
        resolved = path.resolve()  # Normalize the candidate path before containment checks.
        if resolved in (output, detached):  # Exclude only the manifest and its detached digest to avoid self-reference.
            continue  # Advance to ordinary evidence files.
        relative = resolved.relative_to(root).as_posix()  # Convert to one portable artifact-relative path.
        if relative.startswith("../") or path.is_symlink():  # Reject path traversal and symlink ambiguity.
            raise RuntimeError(f"unsafe artifact path {path}")  # Fail closed before hashing an external target.
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_path(path), "role": artifact_role(relative), "required": True})  # Bind every file to exact bytes, size, and stable evidence role.
    toolchain_path = root / "provenance" / "toolchain.json"  # Resolve the required exact runtime receipt inside the artifact.
    acceptance_path = root / "evidence" / "acceptance-contract.json"  # Resolve the frozen numerical charter inside the artifact.
    semantic_path = root / "provenance" / "source-contract-digest.json"  # Resolve the full and semantic contract identity receipt.
    artifact_metadata_path = root / "provenance" / "baseline-artifact.json"  # Resolve the immutable GitHub artifact identity used for baseline retrieval.
    comment_gate_path = root / "provenance" / "added-line-comment-gate.json"  # Resolve the user-required per-added-line comment receipt.
    command_paths = sorted((root / "provenance" / "commands").glob("*.json"))  # Recover every recorded calculation and validator command receipt.
    if not toolchain_path.is_file() or not acceptance_path.is_file() or not semantic_path.is_file() or not artifact_metadata_path.is_file() or not comment_gate_path.is_file() or not command_paths:  # Require all non-file-list provenance classes before manifest publication.
        raise RuntimeError("toolchain, acceptance, semantic digest, baseline artifact metadata, comment Gate, and command receipts are required before manifest generation")  # Fail closed on incomplete provenance.
    artifact_metadata = load_json(artifact_metadata_path)  # Strictly parse the selected GitHub artifact identity.
    if not isinstance(artifact_metadata, dict) or artifact_metadata.get("id") != 8587036796 or artifact_metadata.get("name") != "verified-zhaqing-s4-static-shell-9531999012bd4a94bd937e59f74443c12bcb4b23" or artifact_metadata.get("digest") != "sha256:fadcd8ec455c90a429f69001f2ba98b04c7840c64d5d37f5f3cd90c766745a20":  # Require the exact baseline artifact id, name, and service-computed digest.
        raise RuntimeError("baseline GitHub artifact metadata is incomplete or mismatched")  # Reject a floating or unbound baseline package.
    calculation_sources = [{**record, "repoPath": str(record["path"])[len("provenance/sources/"):]} for record in files if str(record["path"]).startswith("provenance/sources/")]  # Map every archived source copy back to its exact checkout path.
    manifest = {"schema": "zhaqing-canonical-provenance-v1", "status": "PASS", "github": {"repository": os.environ.get("GITHUB_REPOSITORY", "LOCAL"), "sha": os.environ.get("GITHUB_SHA", "LOCAL"), "workflow": os.environ.get("GITHUB_WORKFLOW", "LOCAL"), "workflowPath": ".github/workflows/zhaqing-stress-coordination.yml", "workflowRef": os.environ.get("GITHUB_WORKFLOW_REF", "LOCAL"), "runId": os.environ.get("GITHUB_RUN_ID", "LOCAL"), "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"), "job": os.environ.get("GITHUB_JOB", "LOCAL"), "event": os.environ.get("GITHUB_EVENT_NAME", "LOCAL"), "ref": os.environ.get("GITHUB_REF", "LOCAL"), "refName": os.environ.get("GITHUB_REF_NAME", "LOCAL"), "headRef": os.environ.get("GITHUB_HEAD_REF", ""), "baseRef": os.environ.get("GITHUB_BASE_REF", ""), "checkoutActionSha": "11bd71901bbe5b1630ceea73d27597364c9af683", "uploadArtifactActionSha": "ea165f8d65b6e75b540449e92b4886f43607fa02"}, "baseline": {"runId": 30068283053, "artifactName": "verified-zhaqing-s4-static-shell-9531999012bd4a94bd937e59f74443c12bcb4b23", "artifactId": 8587036796, "artifactDigest": "sha256:fadcd8ec455c90a429f69001f2ba98b04c7840c64d5d37f5f3cd90c766745a20", "sourceCommit": "9531999012bd4a94bd937e59f74443c12bcb4b23", "inputSha256": "1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d", "sourceContractFullSha256": "4f3128df6885e504ec413dac19a452048fd2035fe2eafd69148d42036972b692", "sourceContract": load_json(semantic_path)}, "toolchain": load_json(toolchain_path), "commands": [load_json(path) for path in command_paths], "acceptanceContract": {"path": acceptance_path.relative_to(root).as_posix(), "sha256": sha256_path(acceptance_path), "contract": load_json(acceptance_path)}, "calculationSources": calculation_sources, "fileCount": len(files), "files": files, "manifestRule": "manifest and detached manifest digest are the only excluded files"}  # Publish complete source, runtime, command, threshold, baseline, and file provenance.
    write_json(output, manifest)  # Persist the manifest after all prior evidence exists.
    detached.write_text(f"{sha256_path(output)}  {output.name}\n", encoding="ascii")  # Bind the manifest itself with a detached SHA-256 record.
    return 0  # Report successful provenance generation.


def verify_manifest(args: argparse.Namespace) -> int:  # Independently verify manifest coverage, sizes, hashes, and detached digest.
    root = args.root.resolve()  # Resolve the artifact root exactly once.
    repository = args.repository.resolve()  # Resolve the exact checked-out source repository used by calculation.
    manifest_path = args.manifest.resolve()  # Resolve the manifest file under review.
    detached_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")  # Resolve its detached digest record.
    manifest = load_json(manifest_path)  # Parse the manifest with duplicate-key and finite-number checks.
    if not isinstance(manifest, dict) or manifest.get("schema") != "zhaqing-canonical-provenance-v1":  # Require the canonical schema identity.
        raise RuntimeError("unexpected provenance manifest schema")  # Fail closed on an unrelated file.
    records = manifest.get("files")  # Recover the declared file inventory.
    if not isinstance(records, list):  # Require an explicit file array.
        raise RuntimeError("provenance manifest files is not an array")  # Reject ambiguous inventory data.
    declared = {str(record["path"]): record for record in records if isinstance(record, dict)}  # Index unique declared normalized paths.
    if len(declared) != len(records):  # Detect duplicate or malformed manifest records.
        raise RuntimeError("provenance manifest contains duplicate or malformed file records")  # Fail before a duplicate can hide an artifact.
    actual = {path.resolve().relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file() and path.resolve() not in (manifest_path, detached_path, args.output.resolve())}  # Enumerate current artifact files excluding manifest mechanics and this verifier receipt.
    if set(declared) != set(actual):  # Require exact bidirectional artifact coverage.
        raise RuntimeError(f"manifest coverage mismatch missing={sorted(set(actual) - set(declared))} extra={sorted(set(declared) - set(actual))}")  # Report precise inventory drift.
    for relative, record in declared.items():  # Verify every declared file independently.
        path = actual[relative]  # Resolve the exact current file.
        if path.is_symlink() or int(record["bytes"]) != path.stat().st_size or str(record["sha256"]) != sha256_path(path):  # Check safe path, byte count, and exact digest.
            raise RuntimeError(f"manifest file mismatch {relative}")  # Fail closed on any mutated evidence.
    required_roles = ("equilibrium-state", "detailed-response-summary", "detailed-response-input", "raw-calculix-response", "canonical-primary-response", "canonical-stress-vtk", "wind-exclusion", "load-case-matrix", "load-case-matrix-gate", "strict-vtk-validation", "l2-comparison", "engineering-gate-ledger", "canonical-gate", "acceptance-contract", "frozen-baseline-input", "frozen-baseline-response", "frozen-source-contract", "toolchain", "source-contract-digest", "baseline-artifact-metadata", "added-line-comment-gate", "reaction-audit-k-input", "reaction-audit-k-response", "reaction-audit-k-log", "reaction-audit-10k-input", "reaction-audit-10k-response", "reaction-audit-10k-log")  # Freeze every unique canonical, matrix, independent matrix-Gate, and two-level reaction-audit artifact role required for qualification.
    for role in required_roles:  # Verify unique decisive artifact identity independently of filenames alone.
        if sum(1 for record in records if isinstance(record, dict) and record.get("role") == role) != 1:  # Require exactly one file for each decisive role.
            raise RuntimeError(f"manifest role must occur exactly once: {role}")  # Reject missing or ambiguous canonical evidence.
    sources = manifest.get("calculationSources")  # Recover archived checkout source identities.
    if not isinstance(sources, list) or not sources:  # Require at least the canonical calculation and workflow sources.
        raise RuntimeError("manifest calculationSources is empty or malformed")  # Reject unverifiable generated-code provenance.
    for record in sources:  # Compare every archived source file back to the checked-out repository bytes.
        if not isinstance(record, dict) or not isinstance(record.get("repoPath"), str):  # Require an explicit checkout-relative source path.
            raise RuntimeError("manifest calculation source record is malformed")  # Reject a source that cannot be traced to checkout bytes.
        source_path = repository / str(record["repoPath"])  # Resolve the original source path under the exact checkout.
        archived_path = root / str(record["path"])  # Resolve the archived source copy inside evidence.
        if not source_path.is_file() or sha256_path(source_path) != sha256_path(archived_path):  # Require byte-for-byte equality after staging.
            raise RuntimeError(f"archived calculation source differs from checkout: {record['repoPath']}")  # Reject untracked workflow-time source mutation.
    baseline = manifest.get("baseline")  # Recover immutable baseline identity fields.
    if not isinstance(baseline, dict) or baseline.get("runId") != 30068283053 or baseline.get("artifactId") != 8587036796 or baseline.get("artifactDigest") != "sha256:fadcd8ec455c90a429f69001f2ba98b04c7840c64d5d37f5f3cd90c766745a20" or baseline.get("inputSha256") != "1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d" or baseline.get("sourceContractFullSha256") != "4f3128df6885e504ec413dac19a452048fd2035fe2eafd69148d42036972b692":  # Reassert all frozen baseline identities independently.
        raise RuntimeError("manifest frozen baseline identity mismatch")  # Reject substitution after manifest generation.
    github = manifest.get("github")  # Recover Actions source identity fields.
    expected_sha = os.environ.get("GITHUB_SHA")  # Recover the currently verified Actions checkout identity when available.
    if not isinstance(github, dict) or github.get("workflowPath") != ".github/workflows/zhaqing-stress-coordination.yml" or (expected_sha and github.get("sha") != expected_sha):  # Require the canonical workflow and current source revision.
        raise RuntimeError("manifest GitHub source identity mismatch")  # Reject evidence bound to another workflow or commit.
    summary_path = root / "calculation" / "summary.json"  # Resolve the producer summary for cross-artifact digest verification.
    summary = load_json(summary_path)  # Strictly parse the detailed-response receipt.
    if not isinstance(summary, dict):  # Require the producer summary object contract.
        raise RuntimeError("detailed response summary is not an object")  # Reject malformed producer evidence.
    summary_digest_paths = {"equilibriumStateSha256": root / "calculation" / "equilibrium_state.json", "fineDeckSha256": root / "calculation" / "ZQ_STRESS_COORDINATED.inp", "rawDatSha256": root / "calculation" / "ZQ_STRESS_COORDINATED.dat", "canonicalResponseDatSha256": root / "calculation" / "canonical-response.dat", "vtkSha256": root / "calculation" / "stress-coordinated.vtk", "windExclusionSha256": root / "calculation" / "wind-exclusion.json"}  # Freeze every producer cross-artifact digest binding including immutable native response bytes.
    for field, path in summary_digest_paths.items():  # Recompute each producer identity from exact evidence bytes.
        if not path.is_file() or summary.get(field) != sha256_path(path):  # Require the declared digest to equal the actual artifact.
            raise RuntimeError(f"summary digest mismatch: {field}")  # Reject a detached or substituted response artifact.
    vtk_receipt = summary.get("vtk")  # Recover the nested visualization producer receipt.
    if not isinstance(vtk_receipt, dict) or vtk_receipt.get("sha256") != summary.get("vtkSha256"):  # Require both summary locations to bind the same VTK bytes.
        raise RuntimeError("nested and top-level VTK summary digests differ")  # Reject inconsistent visualization identity.
    reaction_audit = summary.get("reactionAudit")  # Recover the nested two-level independent force-audit receipt.
    reaction_levels = reaction_audit.get("levels", []) if isinstance(reaction_audit, dict) else []  # Resolve its ordered K and 10K records fail closed.
    expected_reaction_levels = {"K1E9": 1.0e9, "K1E10": 1.0e10}  # Freeze the exact source-approved audit labels and stiffnesses independently.
    if not isinstance(reaction_levels, list) or len(reaction_levels) != len(expected_reaction_levels) or {level.get("label") for level in reaction_levels if isinstance(level, dict)} != set(expected_reaction_levels):  # Require both audit levels exactly once so a duplicate cannot hide an extra or substituted solve.
        raise RuntimeError("summary reaction audit levels are incomplete or substituted")  # Reject a missing, duplicate, or tuned support audit.
    if reaction_audit.get("selectedLevel") != "K1E10" or float(reaction_audit.get("selectedStiffnessNPerMm", float("nan"))) != expected_reaction_levels["K1E10"]:  # Require the precommitted higher-stiffness audit to remain the unique formal reaction source.
        raise RuntimeError("summary selected reaction audit is not the frozen K1E10 level")  # Reject result-driven audit selection or stiffness substitution.
    for level in reaction_levels:  # Recompute each audit deck, native response, and solver-log identity from artifact bytes.
        label = str(level.get("label"))  # Recover the exact source-frozen audit label.
        if float(level.get("stiffnessNPerMm", float("nan"))) != expected_reaction_levels[label]:  # Require its approved numeric stiffness without rounding or tuning.
            raise RuntimeError(f"summary reaction audit stiffness mismatch: {label}")  # Reject a post-result support approximation change.
        audit_paths = {"deckSha256": root / "calculation" / f"ZQ_REACTION_AUDIT_{label}.inp", "rawDatSha256": root / "calculation" / f"ZQ_REACTION_AUDIT_{label}.dat", "stdoutSha256": root / "calculation" / f"ZQ_REACTION_AUDIT_{label}.stdout.log"}  # Bind every audit source and native output path deterministically.
        for field, path in audit_paths.items():  # Verify each nested audit digest against exact sealed bytes.
            if not path.is_file() or level.get(field) != sha256_path(path):  # Require file presence and digest equality.
                raise RuntimeError(f"summary reaction audit digest mismatch: {label}.{field}")  # Reject detached or substituted support-reaction evidence.
    canonical_gate_path = root / "evidence" / "canonical-gate.json"  # Resolve the decisive dual-status receipt.
    canonical_gate = load_json(canonical_gate_path)  # Strictly parse the canonical Gate evidence.
    if not isinstance(canonical_gate, dict) or canonical_gate.get("schema") != "zhaqing-canonical-gate-v1" or canonical_gate.get("numericalQualificationStatus") != "PASS" or canonical_gate.get("engineeringReleaseStatus") != "BLOCKED":  # Require the exact canonical receipt schema, numerical acceptance, and truthful release boundary.
        raise RuntimeError("canonical Gate does not record PASS numerical qualification and BLOCKED engineering release")  # Reject a failed or boundary-violating evidence package.
    canonical_checks = canonical_gate.get("checks")  # Recover the independently enumerated decisive Gate checks.
    if not isinstance(canonical_checks, dict) or set(canonical_checks) != {"equilibriumStatePass", "detailedResponsePass", "strictVtkPass", "l2CrossCheckProduced", "loadCaseMatrixComplete", "engineeringLedgerBlockedAsExpected"} or not all(value is True for value in canonical_checks.values()):  # Require every nominal, matrix, and boundary check exactly once and explicitly true.
        raise RuntimeError("canonical Gate checks are incomplete, substituted, or failed")  # Reject a status-only receipt without its complete decision basis.
    canonical_input_paths = {"equilibriumState": root / "calculation" / "equilibrium_state.json", "summary": root / "calculation" / "summary.json", "vtkValidation": root / "evidence" / "vtk-validation.json", "l2Comparison": root / "evidence" / "l2-comparison.json", "loadCaseMatrixGate": root / "evidence" / "case-matrix-gate.json", "g3G6Ledger": root / "evidence" / "g3-g6-ledger.json"}  # Freeze every exact nominal, independent matrix, and engineering input that the canonical Gate claims to combine.
    canonical_input_digests = canonical_gate.get("inputSha256")  # Recover the Gate-to-input digest bindings.
    if not isinstance(canonical_input_digests, dict) or set(canonical_input_digests) != set(canonical_input_paths):  # Require the exact complete input digest key set without aliases or omissions.
        raise RuntimeError("canonical Gate input digest set is incomplete or substituted")  # Reject a detached or ambiguous qualification receipt.
    for field, path in canonical_input_paths.items():  # Recompute each decisive Gate input identity from the sealed package.
        if not path.is_file() or canonical_input_digests.get(field) != sha256_path(path):  # Bind the final decision to current evidence bytes rather than stale filenames.
            raise RuntimeError(f"canonical Gate input digest mismatch: {field}")  # Reject any stale, detached, or substituted Gate input.
    matrix_path = root / "calculation" / "case-matrix.json"  # Resolve the producer LC02-LC09 matrix independently from its Gate receipt.
    matrix_gate_path = root / "evidence" / "case-matrix-gate.json"  # Resolve the independent per-case and VTK aggregation Gate.
    matrix_gate = load_json(matrix_gate_path)  # Strictly parse the sealed matrix Gate for digest revalidation.
    if not isinstance(matrix_gate, dict) or matrix_gate.get("schema") != "zhaqing-load-case-matrix-gate-v1" or matrix_gate.get("status") != "PASS" or matrix_gate.get("numericalQualificationStatus") != "PASS" or matrix_gate.get("engineeringReleaseStatus") != "BLOCKED" or matrix_gate.get("matrixSha256") != sha256_path(matrix_path):  # Require exact schema, statuses, and producer-matrix byte binding.
        raise RuntimeError("load-case matrix Gate is failed, stale, or detached from the producer matrix")  # Reject a status-only or substituted case qualification.
    acceptance_contract_path = root / "evidence" / "acceptance-contract.json"  # Resolve the frozen charter consumed by the independent matrix Gate.
    baseline_input_path = root / "evidence" / "baseline" / "LC01_G_DEAD.inp"  # Resolve the immutable mother input consumed by every case.
    equilibrium_state_path = root / "calculation" / "equilibrium_state.json"  # Resolve the one accepted F3 state inherited by the complete matrix.
    load_cases_csv_path = root / "evidence" / "baseline" / "load_cases.csv"  # Resolve the exact archived case registry consumed by the matrix producer.
    sealed_acceptance = load_json(acceptance_contract_path)  # Strictly parse the sealed charter before cross-binding its registry identity.
    sealed_load_case_contract = sealed_acceptance.get("loadCaseMatrixContract") if isinstance(sealed_acceptance, dict) else None  # Recover the sealed matrix contract safely.
    sealed_registry_sha = sealed_load_case_contract.get("loadCasesCsvSha256") if isinstance(sealed_load_case_contract, dict) else None  # Recover the precommitted case-registry digest.
    if matrix_gate.get("acceptanceContractSha256") != sha256_path(acceptance_contract_path) or matrix_gate.get("baselineSha256") != sha256_path(baseline_input_path) or matrix_gate.get("equilibriumStateSha256") != sha256_path(equilibrium_state_path) or matrix_gate.get("loadCasesCsvSha256") != sha256_path(load_cases_csv_path) or matrix_gate.get("loadCasesCsvSha256") != sealed_registry_sha:  # Rebind the matrix decision to its exact charter, LC01 source, common F3 state, and archived registry bytes.
        raise RuntimeError("load-case matrix Gate charter, registry, or common mother-state digest mismatch")  # Reject a case matrix evaluated against stale or substituted governing evidence.
    matrix_checks = matrix_gate.get("checks")  # Recover every independently evaluated case, damage, VTK, and expected-block decision.
    expected_matrix_checks = {f"{case_id}.{suffix}" for case_id in RUNNABLE_CASE_IDS for suffix in ("sourceAndLoadLedgerPass", "summaryPass", "matrixRowPass", "strictVtkPass")} | {"LC08_ACC_HANGER_LOSS.damageIdentityPass", f"{EXPECTED_BLOCKED_CASE_ID}.expectedBlockPass", f"{EXPECTED_BLOCKED_CASE_ID}.matrixRowPass", "matrixProducerStatusConsistent"}  # Reconstruct the exact independent decision set required for seven runnable cases, one damage identity, and one expected block.
    if not isinstance(matrix_checks, dict) or set(matrix_checks) != expected_matrix_checks or not all(value is True for value in matrix_checks.values()):  # Require every expected matrix check exactly once and explicitly true.
        raise RuntimeError("load-case matrix Gate contains a missing or failed independent check")  # Reject a status-only receipt or a hidden failed case condition.
    matrix_case_digests = matrix_gate.get("caseInputSha256")  # Recover every runnable case input binding published by the independent Gate.
    if not isinstance(matrix_case_digests, dict) or set(matrix_case_digests) != set(RUNNABLE_CASE_IDS):  # Require exact LC02-LC08 response coverage.
        raise RuntimeError("load-case matrix Gate input digest case set is incomplete or substituted")  # Reject missing or surplus case evidence.
    for case_id in RUNNABLE_CASE_IDS:  # Recompute every decisive runnable-case identity from sealed bytes.
        declared_case_digests = matrix_case_digests.get(case_id)  # Recover the sealed Gate's digest map for this case.
        case_root = root / "calculation" / "cases" / case_id  # Resolve the isolated sealed calculation directory for this case.
        case_paths = {"sourceCase": root / "evidence" / "baseline" / "cases" / f"{case_id}.inp", "loadLedger": case_root / "load-ledger.json", "summary": case_root / "summary.json", "canonicalResponse": case_root / "canonical-response.dat", "vtk": case_root / "stress-coordinated.vtk", "windExclusion": case_root / "wind-exclusion.json", "vtkValidation": root / "evidence" / "cases" / f"{case_id}-vtk-validation.json"}  # Freeze the archived source, audited load ledger, and exact response path map used by the independent matrix Gate.
        sealed_case_summary = load_json(case_paths["summary"])  # Strictly recover the declared direct or nonlinear case profile from sealed bytes.
        nonlinear_digest_fields = {"nonlinearIteration", "terminalDeck", "terminalRawDat"}  # Freeze the three additional fields required only for a formal fixed-L0 nonlinear response.
        declared_nonlinear_fields = nonlinear_digest_fields.intersection(declared_case_digests) if isinstance(declared_case_digests, dict) else set()  # Recover any nonlinear terminal evidence claims from the sealed Gate.
        summary_is_nonlinear = isinstance(sealed_case_summary, dict) and sealed_case_summary.get("analysisMode") == "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION"  # Derive required terminal evidence from the actual sealed case summary.
        if summary_is_nonlinear != (declared_nonlinear_fields == nonlinear_digest_fields) or (declared_nonlinear_fields and declared_nonlinear_fields != nonlinear_digest_fields):  # Require all and only the nonlinear digest triplet exactly when the summary declares nonlinear analysis.
            raise RuntimeError(f"load-case matrix Gate nonlinear digest profile does not match summary analysis mode for {case_id}")  # Reject deletion, partial declaration, or injection of nonlinear terminal evidence.
        if isinstance(declared_case_digests, dict) and "nonlinearIteration" in declared_case_digests:  # Reconstruct the declared nonlinear history and native terminal files by their exact digests.
            iteration_matches = [path for path in case_root.glob("*.outer-iterations.json") if sha256_path(path) == declared_case_digests.get("nonlinearIteration")]  # Locate the unique sealed convergence history.
            iteration_receipt = load_json(iteration_matches[0]) if len(iteration_matches) == 1 else None  # Strictly parse the uniquely digest-bound outer history before resolving terminal filenames.
            terminal_iteration = int(iteration_receipt.get("outerIterationCount", 0)) if isinstance(iteration_receipt, dict) else 0  # Recover the final deterministic native iteration number.
            terminal_stem = f"ZQ_{case_id}_NL_{terminal_iteration:02d}"  # Reconstruct the exact producer terminal basename from convergence sequence identity.
            terminal_deck_matches = [case_root / f"{terminal_stem}.inp"] if terminal_iteration >= 1 else []  # Resolve one exact terminal native input without digest-alias ambiguity.
            terminal_dat_matches = [case_root / f"{terminal_stem}.dat"] if terminal_iteration >= 1 else []  # Resolve one exact terminal native response without digest-alias ambiguity.
            if len(iteration_matches) != 1 or len(terminal_deck_matches) != 1 or len(terminal_dat_matches) != 1 or not terminal_deck_matches[0].is_file() or not terminal_dat_matches[0].is_file():  # Reject missing nonlinear history or deterministic terminal files before field comparison.
                raise RuntimeError(f"load-case matrix Gate nonlinear terminal files are missing or ambiguous for {case_id}")  # Report exact case identity whose convergence chain cannot be reconstructed.
            case_paths.update({"nonlinearIteration": iteration_matches[0], "terminalDeck": terminal_deck_matches[0], "terminalRawDat": terminal_dat_matches[0]})  # Extend the sealed path map with the unique nonlinear native chain.
        if not isinstance(declared_case_digests, dict) or set(declared_case_digests) != set(case_paths):  # Require the exact direct or nonlinear response-file identity set.
            raise RuntimeError(f"load-case matrix Gate digest fields are incomplete for {case_id}")  # Reject omissions or aliases before byte comparison.
        for field, path in case_paths.items():  # Recompute every summary, response, VTK, exclusion, and validator digest.
            if not path.is_file() or declared_case_digests.get(field) != sha256_path(path):  # Require exact current sealed bytes.
                raise RuntimeError(f"load-case matrix Gate digest mismatch: {case_id}.{field}")  # Reject stale or substituted case evidence.
    lc09_paths = {"sourceCase": root / "evidence" / "baseline" / "cases" / f"{EXPECTED_BLOCKED_CASE_ID}.inp", "loadLedger": root / "calculation" / "cases" / EXPECTED_BLOCKED_CASE_ID / "load-ledger.json", "disposition": root / "calculation" / "cases" / EXPECTED_BLOCKED_CASE_ID / "case-disposition.json"}  # Resolve the exact source, solver-free load ledger, and expected-block disposition.
    lc09_digests = matrix_gate.get("lc09InputSha256")  # Recover the independent Gate's complete LC09 source and disposition binding.
    if not isinstance(lc09_digests, dict) or set(lc09_digests) != set(lc09_paths) or any(not path.is_file() or lc09_digests.get(field) != sha256_path(path) for field, path in lc09_paths.items()):  # Require every solver-free expected-block input to match sealed bytes.
        raise RuntimeError("LC09 expected-block source, load ledger, or disposition digest mismatch")  # Reject a stale, substituted, or response-free-by-assertion-only wind-cable block.
    sealed_lc09_root = root / "calculation" / "cases" / EXPECTED_BLOCKED_CASE_ID  # Resolve the complete expected-block directory for recursive response exclusion.
    sealed_lc09_prohibited = sorted(path.relative_to(sealed_lc09_root).as_posix() for path in sealed_lc09_root.rglob("*") if path.is_file() and path.suffix.lower() in {".dat", ".frd", ".sta", ".cvg", ".vtk"})  # Recompute the complete prohibited numerical-response inventory from sealed bytes.
    if sealed_lc09_prohibited:  # Detect numerical response files hidden anywhere below the formally unsolved LC09 directory.
        raise RuntimeError("LC09 expected-block package contains prohibited solver response artifacts")  # Reject a manifest that seals hidden calculations behind a solver-free disposition.
    detached_fields = detached_path.read_text(encoding="ascii").split()  # Parse the detached manifest digest record.
    if not detached_fields or detached_fields[0] != sha256_path(manifest_path):  # Bind the manifest bytes themselves.
        raise RuntimeError("detached provenance manifest digest mismatch")  # Reject a modified or unbound manifest.
    receipt = {"schema": "zhaqing-provenance-verification-v1", "status": "PASS", "manifestSha256": sha256_path(manifest_path), "verifiedFileCount": len(declared), "coverageExact": True, "allFileDigestsMatch": True}  # Publish the independent verification result.
    write_json(args.output, receipt)  # Persist the verifier receipt outside the self-contained manifest inventory.
    return 0  # Report successful provenance verification.


def parser() -> argparse.ArgumentParser:  # Build the deterministic evidence command-line interface.
    root = argparse.ArgumentParser()  # Create the top-level operation parser.
    commands = root.add_subparsers(dest="command", required=True)  # Require exactly one evidence operation.
    semantic = commands.add_parser("semantic-digest")  # Register explicit source-contract digest generation.
    semantic.add_argument("--contract", type=Path, required=True)  # Require the exact frozen source contract.
    semantic.add_argument("--output", type=Path, required=True)  # Require the digest receipt output path.
    toolchain = commands.add_parser("toolchain")  # Register exact runtime identity capture.
    toolchain.add_argument("--ccx", required=True)  # Require the solver executable used by calculation.
    toolchain.add_argument("--output", type=Path, required=True)  # Require the toolchain receipt output path.
    recorded = commands.add_parser("run-recorded")  # Register native command execution with complete receipts.
    recorded.add_argument("--id", required=True)  # Require one stable command identifier.
    recorded.add_argument("--cwd", type=Path, required=True)  # Require an explicit working directory.
    recorded.add_argument("--stdout", type=Path, required=True)  # Require an explicit standard-output evidence path.
    recorded.add_argument("--stderr", type=Path, required=True)  # Require an explicit standard-error evidence path.
    recorded.add_argument("--receipt", type=Path, required=True)  # Require an explicit command receipt path.
    recorded.add_argument("argv", nargs=argparse.REMAINDER)  # Preserve the exact remaining executable argument vector.
    comment_gate = commands.add_parser("comment-gate")  # Register the user-required per-added-line source comment audit.
    comment_gate.add_argument("--cwd", type=Path, required=True)  # Require the exact repository working directory.
    comment_gate.add_argument("--parent", default="HEAD^")  # Compare against the qualification commit's first parent by default.
    comment_gate.add_argument("--child", default="HEAD")  # Audit the exact checked-out qualification commit by default.
    comment_gate.add_argument("--output", type=Path, required=True)  # Require an explicit machine-readable Gate receipt path.
    comment_gate.add_argument("paths", nargs="+", help="repository paths included in the comment audit")  # Require one or more explicit source paths rather than silently scanning generated artifacts.
    l2 = commands.add_parser("l2")  # Register independent L2 comparison generation.
    l2.add_argument("--reference-inp", type=Path, required=True)  # Require frozen reference input.
    l2.add_argument("--reference-dat", type=Path, required=True)  # Require frozen reference result.
    l2.add_argument("--candidate-inp", type=Path, required=True)  # Require candidate input.
    l2.add_argument("--candidate-dat", type=Path, required=True)  # Require candidate result.
    l2.add_argument("--output", type=Path, required=True)  # Require explicit comparison receipt path.
    ledger = commands.add_parser("ledger")  # Register G3-G6 ledger generation.
    ledger.add_argument("--contract", type=Path, required=True)  # Require frozen source contract.
    ledger.add_argument("--schema", type=Path, required=True)  # Require the repository-owned formal gate-ledger JSON Schema.
    ledger.add_argument("--output", type=Path, required=True)  # Require explicit ledger path.
    matrix_gate = commands.add_parser("case-matrix-gate")  # Register independent LC02-LC09 response, VTK, damage, and expected-block aggregation.
    matrix_gate.add_argument("--matrix", type=Path, required=True)  # Require the producer aggregate case-matrix receipt.
    matrix_gate.add_argument("--calculation-root", type=Path, required=True)  # Require the common calculation root containing isolated case directories.
    matrix_gate.add_argument("--receipts-root", type=Path, required=True)  # Require the independent per-case strict VTK receipt directory.
    matrix_gate.add_argument("--acceptance-contract", type=Path, required=True)  # Require the exact source-controlled load-case identities, trigger, dispositions, and thresholds.
    matrix_gate.add_argument("--baseline", type=Path, required=True)  # Require the immutable archived LC01 mother input shared by every case.
    matrix_gate.add_argument("--equilibrium", type=Path, required=True)  # Require the single persisted accepted F3 state inherited by every runnable case.
    matrix_gate.add_argument("--case-source-root", type=Path, required=True)  # Require the archived directory containing every exact LC02-LC09 source INP.
    matrix_gate.add_argument("--load-cases-csv", type=Path, required=True)  # Require the exact archived registry whose digest is frozen by the acceptance contract.
    matrix_gate.add_argument("--output", type=Path, required=True)  # Require the independent matrix-Gate receipt path.
    gate = commands.add_parser("gate")  # Register canonical numerical/engineering Gate composition.
    gate.add_argument("--equilibrium", type=Path, required=True)  # Require equilibrium receipt.
    gate.add_argument("--summary", type=Path, required=True)  # Require detailed response receipt.
    gate.add_argument("--vtk-receipt", type=Path, required=True)  # Require strict VTK receipt.
    gate.add_argument("--l2-receipt", type=Path, required=True)  # Require L2 cross-check receipt.
    gate.add_argument("--ledger", type=Path, required=True)  # Require engineering ledger.
    gate.add_argument("--case-matrix-gate", type=Path, required=True)  # Require the independent LC02-LC09 numerical, strict VTK, damage, and expected-block Gate receipt.
    gate.add_argument("--output", type=Path, required=True)  # Require canonical Gate output.
    manifest = commands.add_parser("manifest")  # Register provenance manifest generation.
    manifest.add_argument("--root", type=Path, required=True)  # Require exact artifact root.
    manifest.add_argument("--output", type=Path, required=True)  # Require manifest path inside that root.
    verify = commands.add_parser("verify-manifest")  # Register independent provenance verification.
    verify.add_argument("--root", type=Path, required=True)  # Require exact artifact root.
    verify.add_argument("--manifest", type=Path, required=True)  # Require manifest path.
    verify.add_argument("--repository", type=Path, required=True)  # Require the exact checkout for archived-source byte comparison.
    verify.add_argument("--output", type=Path, required=True)  # Require verifier receipt path.
    return root  # Return the complete CLI parser.


def main() -> int:  # Dispatch the selected independent evidence operation.
    args = parser().parse_args()  # Parse all required paths before reading evidence.
    operations = {"semantic-digest": build_semantic_digest, "toolchain": build_toolchain, "run-recorded": run_recorded, "comment-gate": build_comment_gate, "l2": build_l2, "ledger": build_ledger, "case-matrix-gate": build_case_matrix_gate, "gate": build_canonical_gate, "manifest": build_manifest, "verify-manifest": verify_manifest}  # Bind explicit command names to pure operation entry points.
    return operations[args.command](args)  # Execute exactly the requested operation and return its native status.


if __name__ == "__main__":  # Run only when invoked as the workflow evidence entry point.
    raise SystemExit(main())  # Return evidence success or failure to the workflow.
