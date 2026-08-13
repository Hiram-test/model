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
    receipt = {"schema": "zhaqing-toolchain-v1", "status": "PASS" if version_result.returncode == 0 and package_result.returncode == 0 and ldd_result.returncode == 0 else "FAIL", "runner": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "platform": platform.platform(), "runnerOs": os.environ.get("RUNNER_OS"), "runnerArch": os.environ.get("RUNNER_ARCH"), "imageOs": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion"), "locale": os.environ.get("LANG"), "timezone": os.environ.get("TZ"), "threadEnvironment": {key: os.environ.get(key) for key in thread_keys}, "osReleaseSha256": sha256_path(os_release) if os_release.is_file() else None, "osReleaseText": os_release.read_text(encoding="utf-8") if os_release.is_file() else None}, "python": {"executable": sys.executable, "realpath": str(python_real), "version": sys.version, "implementation": platform.python_implementation(), "bytes": python_real.stat().st_size, "sha256": sha256_path(python_real)}, "calculix": {"requestedPath": str(ccx_requested), "realpath": str(ccx_real), "versionExitCode": version_result.returncode, "versionStdout": version_result.stdout, "versionStderr": version_result.stderr, "packageExitCode": package_result.returncode, "packageRecord": package_result.stdout.strip(), "bytes": ccx_real.stat().st_size, "sha256": sha256_path(ccx_real), "lddExitCode": ldd_result.returncode, "lddText": ldd_result.stdout, "libraries": library_records}}  # Publish complete reproducible runtime identity without treating a package-family name as sufficient.
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


def build_canonical_gate(args: argparse.Namespace) -> int:  # Combine numerical receipts while keeping engineering release status independent.
    equilibrium = load_json(args.equilibrium)  # Read the accepted P1/P2 state contract strictly.
    summary = load_json(args.summary)  # Read the P3/P4 numerical summary strictly.
    vtk = load_json(args.vtk_receipt)  # Read the independent strict VTK receipt strictly.
    l2 = load_json(args.l2_receipt)  # Read the independent L2 cross-check receipt strictly.
    ledger = load_json(args.ledger)  # Read the independent engineering Gate ledger strictly.
    checks = {"equilibriumStatePass": isinstance(equilibrium, dict) and equilibrium.get("status") == "PASS", "detailedResponsePass": isinstance(summary, dict) and summary.get("status") == "PASS", "strictVtkPass": isinstance(vtk, dict) and vtk.get("status") == "PASS", "l2CrossCheckProduced": isinstance(l2, dict) and l2.get("status") == "PASS", "engineeringLedgerBlockedAsExpected": isinstance(ledger, dict) and ledger.get("status") == "BLOCKED"}  # Evaluate numerical evidence and release boundary without conflating them.
    numerical_status = "PASS" if all(value for key, value in checks.items() if key != "engineeringLedgerBlockedAsExpected") else "FAIL"  # Derive numerical qualification solely from numerical evidence.
    engineering_status = str(ledger.get("status")) if isinstance(ledger, dict) else "BLOCKED"  # Derive engineering status only from the ledger.
    receipt = {"schema": "zhaqing-canonical-gate-v1", "numericalQualificationStatus": numerical_status, "engineeringReleaseStatus": engineering_status, "checks": checks, "inputSha256": {"equilibriumState": sha256_path(args.equilibrium), "summary": sha256_path(args.summary), "vtkValidation": sha256_path(args.vtk_receipt), "l2Comparison": sha256_path(args.l2_receipt), "g3G6Ledger": sha256_path(args.ledger)}, "releaseBoundary": "PASS numerical qualification is not an engineering release while G3-G6 is BLOCKED"}  # Publish the decisive dual-status receipt.
    write_json(args.output, receipt)  # Persist the canonical Gate receipt before manifest enumeration.
    return 0 if numerical_status == "PASS" and engineering_status == "BLOCKED" else 2  # Require numerical acceptance and truthful blocked release state.


def artifact_role(relative: str) -> str:  # Assign stable semantic roles to decisive canonical artifact paths while retaining a generic role for auxiliary evidence.
    exact_roles = {"calculation/equilibrium_state.json": "equilibrium-state", "calculation/summary.json": "detailed-response-summary", "calculation/ZQ_STRESS_COORDINATED.inp": "detailed-response-input", "calculation/ZQ_STRESS_COORDINATED.dat": "raw-calculix-response", "calculation/canonical-response.dat": "canonical-primary-response", "calculation/stress-coordinated.vtk": "canonical-stress-vtk", "calculation/wind-exclusion.json": "wind-exclusion", "evidence/vtk-validation.json": "strict-vtk-validation", "evidence/l2-comparison.json": "l2-comparison", "evidence/g3-g6-ledger.json": "engineering-gate-ledger", "evidence/canonical-gate.json": "canonical-gate", "evidence/acceptance-contract.json": "acceptance-contract", "evidence/baseline/LC01_G_DEAD.inp": "frozen-baseline-input", "evidence/baseline/LC01_G_DEAD.dat": "frozen-baseline-response", "evidence/baseline/source_frozen_model_contract.json": "frozen-source-contract", "provenance/toolchain.json": "toolchain", "provenance/source-contract-digest.json": "source-contract-digest", "provenance/baseline-artifact.json": "baseline-artifact-metadata", "provenance/added-line-comment-gate.json": "added-line-comment-gate"}  # Freeze unique roles used by manifest cross-checks.
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
    required_roles = ("equilibrium-state", "detailed-response-summary", "detailed-response-input", "raw-calculix-response", "canonical-primary-response", "canonical-stress-vtk", "wind-exclusion", "strict-vtk-validation", "l2-comparison", "engineering-gate-ledger", "canonical-gate", "acceptance-contract", "frozen-baseline-input", "frozen-baseline-response", "frozen-source-contract", "toolchain", "source-contract-digest", "baseline-artifact-metadata", "added-line-comment-gate", "reaction-audit-k-input", "reaction-audit-k-response", "reaction-audit-k-log", "reaction-audit-10k-input", "reaction-audit-10k-response", "reaction-audit-10k-log")  # Freeze every unique canonical and two-level reaction-audit artifact role required for qualification.
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
    if not isinstance(canonical_checks, dict) or set(canonical_checks) != {"equilibriumStatePass", "detailedResponsePass", "strictVtkPass", "l2CrossCheckProduced", "engineeringLedgerBlockedAsExpected"} or not all(value is True for value in canonical_checks.values()):  # Require every expected check exactly once and explicitly true.
        raise RuntimeError("canonical Gate checks are incomplete, substituted, or failed")  # Reject a status-only receipt without its complete decision basis.
    canonical_input_paths = {"equilibriumState": root / "calculation" / "equilibrium_state.json", "summary": root / "calculation" / "summary.json", "vtkValidation": root / "evidence" / "vtk-validation.json", "l2Comparison": root / "evidence" / "l2-comparison.json", "g3G6Ledger": root / "evidence" / "g3-g6-ledger.json"}  # Freeze every exact input that the canonical Gate claims to combine.
    canonical_input_digests = canonical_gate.get("inputSha256")  # Recover the Gate-to-input digest bindings.
    if not isinstance(canonical_input_digests, dict) or set(canonical_input_digests) != set(canonical_input_paths):  # Require the exact complete input digest key set without aliases or omissions.
        raise RuntimeError("canonical Gate input digest set is incomplete or substituted")  # Reject a detached or ambiguous qualification receipt.
    for field, path in canonical_input_paths.items():  # Recompute each decisive Gate input identity from the sealed package.
        if not path.is_file() or canonical_input_digests.get(field) != sha256_path(path):  # Bind the final decision to current evidence bytes rather than stale filenames.
            raise RuntimeError(f"canonical Gate input digest mismatch: {field}")  # Reject any stale, detached, or substituted Gate input.
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
    gate = commands.add_parser("gate")  # Register canonical numerical/engineering Gate composition.
    gate.add_argument("--equilibrium", type=Path, required=True)  # Require equilibrium receipt.
    gate.add_argument("--summary", type=Path, required=True)  # Require detailed response receipt.
    gate.add_argument("--vtk-receipt", type=Path, required=True)  # Require strict VTK receipt.
    gate.add_argument("--l2-receipt", type=Path, required=True)  # Require L2 cross-check receipt.
    gate.add_argument("--ledger", type=Path, required=True)  # Require engineering ledger.
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
    operations = {"semantic-digest": build_semantic_digest, "toolchain": build_toolchain, "run-recorded": run_recorded, "comment-gate": build_comment_gate, "l2": build_l2, "ledger": build_ledger, "gate": build_canonical_gate, "manifest": build_manifest, "verify-manifest": verify_manifest}  # Bind explicit command names to pure operation entry points.
    return operations[args.command](args)  # Execute exactly the requested operation and return its native status.


if __name__ == "__main__":  # Run only when invoked as the workflow evidence entry point.
    raise SystemExit(main())  # Return evidence success or failure to the workflow.
