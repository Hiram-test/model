#!/usr/bin/env python3  # Execute the frozen LC02-LC07 F3-increment matrix and publish the expected LC09 evidence block.
import argparse  # Parse only explicit frozen source, state, solver, and output paths.
import csv  # Validate the immutable load-case registry without external dependencies.
import hashlib  # Bind every consumed and generated evidence file to exact bytes.
import importlib.util  # Load the workflow-reconstructed pipeline and adapter without path mutation.
import inspect  # Verify that the adapter exposes the required additive-load call contract.
import json  # Read and publish deterministic machine-auditable receipts.
import math  # Reject nonfinite load and response evidence explicitly.
import re  # Recover the exact load-case identifier from each frozen heading safely.
import shutil  # Copy byte-identical formal response artifacts from isolated screening namespaces without rewriting numerical tokens.
from pathlib import Path  # Keep every calculation input and output path explicit.

BASE_CASE_ID = "LC01_G_DEAD"  # Freeze the sole completed F3 permanent-state source used by every intact increment case.
INTACT_CASE_IDS = ("LC02_G_Q_SERVICE", "LC03_G_Q_ASYM_SERVICE", "LC04_G_W_SERVICE", "LC05_G_Q_EXTREME", "LC06_G_W_EXTREME", "LC07_G_Q_W_EXTREME")  # Freeze all intact post-F3 screening cases in registry order.
BLOCKED_CASE_ID = "LC09_ACC_WIND_CABLE_LOSS"  # Freeze the accidental wind-cable-loss case that remains outside formal G3/G5 evidence.
DAMAGE_CASE_ID = "LC08_ACC_HANGER_LOSS"  # Freeze the static alternate-path hanger-loss case with stable source e1033 identity.
RUNNABLE_CASE_IDS = (*INTACT_CASE_IDS, DAMAGE_CASE_ID)  # Require six intact increments and one explicit source-ID damage response before the expected wind-cable block.
SUPPORTED_CASE_IDS = (*RUNNABLE_CASE_IDS, BLOCKED_CASE_ID)  # Freeze the complete LC02-LC09 matrix scope in source registry order.
FROZEN_SOURCE_SHA256 = {"LC01_G_DEAD": "1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d", "LC02_G_Q_SERVICE": "c97727f568479e4572cbf9825a1af539d760ce8bf371868b899cf050a8a465f3", "LC03_G_Q_ASYM_SERVICE": "6f6c3f35466380bac49c653da65ab26e0a4ab469540029d211d16a4577566a2e", "LC04_G_W_SERVICE": "139738b450669768c63d1599a7a59bb723f2ac80ef3be2d94eb0ee7a8d264ce4", "LC05_G_Q_EXTREME": "375928a38f8205f0b56cd1e5578cd6b3f572f484388bc230290f57bf97862577", "LC06_G_W_EXTREME": "00ddf2556a1fdf67f8f9a72a4e36beb2a5183291a6b51d1219edef5c61118931", "LC07_G_Q_W_EXTREME": "f4e1612296afb704c99cb6868605a8a686dcd38b8c6262a9aca23beb9b255745", "LC08_ACC_HANGER_LOSS": "2a15263cedeb5b5b79d643655482703653eb7319212755b9a67c6e425dbc6b3f", "LC09_ACC_WIND_CABLE_LOSS": "b00195361c9bad8093ca023d2586f38af0bc05ea69b5ceaf98259bec37851455"}  # Preserve exact bytes of every source allowed by this runner.
FROZEN_LOAD_CASES_CSV_SHA256 = "772c9b8282042f474998553d80af3a10cec0d784b38dfdbce4f3e53c9156bd7d"  # Bind case meaning to the reviewed UTF-8 registry.
EXPECTED_DELTA = {"LC02_G_Q_SERVICE": {"countsByDof": {1: 0, 2: 0, 3: 581}, "resultantN": (0.0, 0.0, -1578500.0006038)}, "LC03_G_Q_ASYM_SERVICE": {"countsByDof": {1: 0, 2: 0, 3: 332}, "resultantN": (0.0, 0.0, -789250.000386)}, "LC04_G_W_SERVICE": {"countsByDof": {1: 0, 2: 83, 3: 0}, "resultantN": (0.0, 123000.0, 0.0)}, "LC05_G_Q_EXTREME": {"countsByDof": {1: 0, 2: 0, 3: 581}, "resultantN": (0.0, 0.0, -2255000.0002798)}, "LC06_G_W_EXTREME": {"countsByDof": {1: 0, 2: 83, 3: 581}, "resultantN": (0.0, 307500.0, 225500.0000804)}, "LC07_G_Q_W_EXTREME": {"countsByDof": {1: 0, 2: 83, 3: 581}, "resultantN": (0.0, 246000.0, -2029500.0006238)}}  # Freeze the independently audited source-minus-LC01 nodal-load ledgers.
EXPECTED_DELTA[DAMAGE_CASE_ID] = {"countsByDof": {1: 0, 2: 0, 3: 581}, "resultantN": (0.0, 0.0, -1578500.0006038)}  # Freeze LC08 crowd loading independently from its separate stable-ID topology damage event.
LOAD_RESULTANT_ABS_TOL_N = 1.0e-6  # Require the frozen decimal source ledger to close within one micro-newton after deterministic summation.
ZERO_LOAD_ABS_TOL_N = 1.0e-12  # Remove only arithmetic zeros while retaining every physically declared delta record.
FATAL_TOKENS = ("*ERROR", "SINGULAR", "NEGATIVE PIVOT", "LINEAR MPCS AND NONLINEAR MPCS DEPEND ON EACH OTHER")  # Fail closed on the native diagnostics already frozen by the canonical adapter.
REACTION_LEVELS = ((1.0e9, "K1E9"), (1.0e10, "K1E10"))  # Preserve both precommitted load-free support-sensor levels for every numerical case.
PROHIBITED_BLOCKED_RESPONSE_SUFFIXES = (".dat", ".frd", ".sta", ".cvg", ".vtk")  # Prove that LC09 publishes no disguised numerical response artifact.
COROTATIONAL_HOOK_SCHEMA = "zhaqing-fixed-l0-corotational-request-v1"  # Freeze the handoff contract for cases outside the direct F3 tangent range.


def sha256_path(path: Path) -> str:  # Compute one exact SHA-256 identity without text normalization.
    digest = hashlib.sha256()  # Allocate a fresh digest for the requested evidence file.
    with path.open("rb") as stream:  # Read exact bytes so encoding and line endings remain part of provenance.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Bound memory while preserving byte order.
            digest.update(chunk)  # Extend the digest with the next exact byte block.
    return digest.hexdigest()  # Return the lowercase immutable identity.


def write_json(path: Path, payload: dict) -> str:  # Persist one deterministic UTF-8 JSON receipt and return its byte identity.
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Use one stable indentation and final newline contract.
    return sha256_path(path)  # Bind downstream evidence to the exact persisted receipt.


def load_python_module(path: Path, module_name: str):  # Load one workflow-reconstructed source file from its explicit path.
    spec = importlib.util.spec_from_file_location(module_name, path)  # Construct an isolated source-file import specification.
    if spec is None or spec.loader is None:  # Refuse an undefined import before any calculation starts.
        raise RuntimeError(f"cannot load Python module from {path}")  # Report the exact unusable module path.
    module = importlib.util.module_from_spec(spec)  # Allocate the isolated module namespace.
    spec.loader.exec_module(module)  # Execute definitions under their guarded-main contract.
    return module  # Return the loaded audited implementation.


def parse_case_id(text: str, path: Path) -> str:  # Recover the exact registry id from the immutable source heading.
    match = re.search(r"(?m)^Zhaqing suspension bridge global screening model - (LC\d\d_[A-Z0-9_]+)\s", text)  # Match only the reviewed heading grammar.
    if match is None:  # Reject filenames as a substitute for missing in-file identity.
        raise RuntimeError(f"cannot recover frozen case id from heading: {path}")  # Identify the malformed source explicitly.
    return match.group(1)  # Return the heading-bound case identifier.


def keyword_blocks(text: str, keyword: str) -> list[list[str]]:  # Recover all data rows belonging to one exact Abaqus keyword family.
    blocks: list[list[str]] = []  # Preserve multiple occurrences so duplicates cannot be hidden.
    active: list[str] | None = None  # Track the current requested-keyword body.
    for raw in text.splitlines():  # Scan source order without rewriting numeric spelling.
        line = raw.strip()  # Normalize only surrounding whitespace for grammar recognition.
        if line.startswith("*"):  # Detect every keyword or comment boundary.
            if active is not None:  # Close the prior requested block before processing the new keyword.
                blocks.append(active)  # Preserve the complete requested body in source order.
                active = None  # Leave requested-keyword parsing mode.
            if not line.startswith("**") and line.split(",", 1)[0].upper() == keyword.upper():  # Match the exact keyword name without accepting prefixes.
                active = []  # Enter a new requested-keyword body.
            continue  # Advance past every keyword or comment row.
        if active is not None and line:  # Preserve every nonempty data row under the active requested keyword.
            active.append(line)  # Store normalized data spelling for exact semantic comparison.
    if active is not None:  # Close a requested block that reaches end of file.
        blocks.append(active)  # Preserve its final data rows.
    return blocks  # Return every requested block without silent concatenation.


def parse_cloads(text: str, source: Path) -> dict[tuple[int, int], float]:  # Parse the sole explicit nodal-load block into an exact degree ledger.
    blocks = keyword_blocks(text, "*CLOAD")  # Recover all concentrated-load blocks independently.
    if len(blocks) != 1:  # Require the reviewed one-step one-block source convention.
        raise RuntimeError(f"expected exactly one CLOAD block in {source}, found {len(blocks)}")  # Refuse ambiguous accumulation semantics.
    loads: dict[tuple[int, int], float] = {}  # Preserve one declared value for every node and translational direction.
    for raw in blocks[0]:  # Parse each immutable CLOAD data record exactly once.
        fields = [field.strip() for field in raw.split(",")]  # Tokenize standard node,dof,value syntax.
        if len(fields) != 3 or not fields[0].isdigit() or not fields[1].isdigit():  # Reject named sets, amplitudes, and malformed records outside the reviewed contract.
            raise RuntimeError(f"unexpected CLOAD record in {source}: {raw}")  # Expose the exact record that cannot be audited.
        key = (int(fields[0]), int(fields[1]))  # Recover the physical loaded degree.
        value = float(fields[2])  # Parse the immutable decimal magnitude in newtons.
        if key in loads:  # Refuse duplicate degrees so case-minus-base subtraction is unique.
            raise RuntimeError(f"duplicate CLOAD degree in {source}: {key}")  # Stop before silently selecting an accumulation convention.
        if key[1] not in (1, 2, 3) or not math.isfinite(value):  # Require finite translational load evidence only.
            raise RuntimeError(f"invalid CLOAD degree or value in {source}: {raw}")  # Reject rotational or nonfinite data.
        loads[key] = value  # Preserve the exact finite source value.
    return loads  # Return the unique source nodal-load mapping.


def semantic_skeleton(text: str) -> str:  # Remove only the permitted heading value and CLOAD body before byte-level model comparison.
    output: list[str] = []  # Preserve all non-load model and step rows in exact source order.
    active_keyword = ""  # Track whether the scanner is inside HEADING or CLOAD data.
    heading_value_replaced = False  # Allow exactly one variable case-title row after HEADING.
    cload_blocks = 0  # Require exactly one removable CLOAD body.
    for raw in text.splitlines():  # Visit every normalized line while preserving its exact content elsewhere.
        stripped = raw.strip()  # Recognize keyword boundaries without changing preserved rows.
        if stripped.startswith("*"):  # Detect a keyword or comment row.
            if stripped.startswith("**"):  # Keep comments byte-for-byte and retain the current keyword data context.
                output.append(raw)  # Preserve the immutable explanatory source comment.
                continue  # Advance without changing the active data keyword.
            active_keyword = stripped.split(",", 1)[0].upper()  # Recover the exact active keyword family.
            if active_keyword == "*CLOAD":  # Count the only permitted variable data block.
                cload_blocks += 1  # Record this CLOAD occurrence for uniqueness validation.
            output.append(raw)  # Preserve every keyword row including CLOAD itself.
            continue  # Advance to its data body.
        if active_keyword == "*CLOAD" and stripped:  # Omit only explicit concentrated-load data records.
            continue  # Remove source-case load values from the structural semantic identity comparison.
        if active_keyword == "*HEADING" and stripped and not heading_value_replaced:  # Replace the sole case-specific title value.
            output.append("<FROZEN_CASE_HEADING>")  # Preserve the presence and position of one heading value.
            heading_value_replaced = True  # Reject any later attempt to treat arbitrary heading data as variable.
            continue  # Advance after canonicalizing the title.
        output.append(raw)  # Preserve every other model, material, topology, boundary, load, and output row exactly.
    if cload_blocks != 1 or not heading_value_replaced:  # Require both allowed variability boundaries explicitly.
        raise RuntimeError("source does not satisfy the one-heading and one-CLOAD semantic comparison contract")  # Stop before weakening non-load identity.
    return "\n".join(output) + "\n"  # Return one deterministic comparison stream.


def load_delta(base_loads: dict[tuple[int, int], float], case_loads: dict[tuple[int, int], float]) -> dict[tuple[int, int], float]:  # Compute CASE minus LC01 on the union of declared degrees.
    keys = sorted(set(base_loads) | set(case_loads))  # Preserve deterministic node-then-direction order.
    return {key: case_loads.get(key, 0.0) - base_loads.get(key, 0.0) for key in keys if abs(case_loads.get(key, 0.0) - base_loads.get(key, 0.0)) > ZERO_LOAD_ABS_TOL_N}  # Keep every nonzero source delta exactly once.


def validate_delta(case_id: str, delta: dict[tuple[int, int], float]) -> tuple[dict[int, int], tuple[float, float, float]]:  # Enforce the frozen independent record-count and resultant ledger.
    expected = EXPECTED_DELTA[case_id]  # Select the precommitted evidence for this intact case.
    counts = {dof: sum(1 for _node, direction in delta if direction == dof) for dof in (1, 2, 3)}  # Count every loaded degree by bridge axis.
    resultant = tuple(math.fsum(value for (_node, direction), value in delta.items() if direction == dof) for dof in (1, 2, 3))  # Sum source deltas with stable compensated arithmetic.
    if counts != expected["countsByDof"]:  # Require exact record population rather than resultant-only agreement.
        raise RuntimeError(f"{case_id} delta CLOAD record counts changed: {counts}")  # Expose topology or distribution drift.
    if any(abs(resultant[index] - expected["resultantN"][index]) > LOAD_RESULTANT_ABS_TOL_N for index in range(3)):  # Require exact independent resultant closure.
        raise RuntimeError(f"{case_id} delta CLOAD resultant changed: {resultant}")  # Expose magnitude or sign drift.
    return counts, resultant  # Return validated ledger aggregates for publication.


def validate_registry(path: Path) -> dict[str, dict[str, str]]:  # Verify and parse the frozen nine-row case registry.
    if sha256_path(path) != FROZEN_LOAD_CASES_CSV_SHA256:  # Reject any metadata drift before interpreting case meaning.
        raise RuntimeError("load_cases.csv SHA-256 does not match the frozen PR9 registry")  # Report the immutable registry boundary.
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # Consume the reviewed BOM-bearing UTF-8 source deterministically.
        rows = list(csv.DictReader(stream))  # Parse named fields without locale-dependent conversion.
    registry = {str(row.get("case_id", "")): row for row in rows}  # Key every row by its explicit case id.
    required = {BASE_CASE_ID, *INTACT_CASE_IDS, "LC08_ACC_HANGER_LOSS", BLOCKED_CASE_ID}  # Require the complete reviewed case inventory even when this runner handles a subset.
    if set(registry) != required or len(rows) != len(required):  # Reject missing, duplicate, or unreviewed case definitions.
        raise RuntimeError("load_cases.csv does not contain exactly the frozen LC01-LC09 registry")  # Stop before mapping a case to ambiguous metadata.
    return registry  # Return exact string metadata for provenance receipts.


def validate_parent_identity(base: Path, equilibrium_state: Path, base_summary: Path, base_canonical_dat: Path) -> tuple[dict, dict, dict]:  # Prove every case inherits one successful persisted LC01/F3 chain.
    base_sha = sha256_path(base)  # Freeze the supplied LC01 source identity.
    if base_sha != FROZEN_SOURCE_SHA256[BASE_CASE_ID]:  # Require the reviewed baseline bytes exactly.
        raise RuntimeError("LC01 base SHA-256 does not match the frozen source")  # Reject any alternate permanent load or topology.
    state = json.loads(equilibrium_state.read_text(encoding="utf-8"))  # Read only the persisted F3 state bytes supplied by the workflow.
    summary = json.loads(base_summary.read_text(encoding="utf-8"))  # Read the successful canonical LC01 response receipt.
    identities = {"baseSha256": base_sha, "equilibriumStateSha256": sha256_path(equilibrium_state), "baseSummarySha256": sha256_path(base_summary), "baseCanonicalDatSha256": sha256_path(base_canonical_dat)}  # Bind the complete inherited chain.
    checks = (state.get("schema") == "zhaqing-equilibrium-state-v3", state.get("status") == "PASS", state.get("sourceBaselineSha256") == base_sha, summary.get("status") == "PASS", summary.get("sourceBaselineSha256") == base_sha, summary.get("equilibriumStateSchema") == state.get("schema"), summary.get("equilibriumStateSha256") == identities["equilibriumStateSha256"], summary.get("canonicalResponseDatSha256") == identities["baseCanonicalDatSha256"])  # Evaluate every persisted parent identity without regeneration.
    if not all(checks):  # Refuse a case run when any parent byte or PASS contract is disconnected.
        raise RuntimeError("persisted LC01/F3 state, summary, and canonical DAT identity chain is incomplete")  # Stop before silently rebuilding or retargeting prestress.
    return state, summary, identities  # Return the byte-verified parent evidence only.


def require_case_adapter_api(adapter) -> None:  # Require additive delta-load support in both canonical and reaction-audit deck builders.
    required = (("build_fine_deck", "delta_cloads"), ("run_reaction_audit_level", "delta_cloads"))  # Freeze the two adapter extension points consumed by this runner.
    missing = [f"{name}(..., {parameter}=...)" for name, parameter in required if not hasattr(adapter, name) or parameter not in inspect.signature(getattr(adapter, name)).parameters]  # Detect an older canonical-only adapter before solver invocation.
    if missing:  # Fail with a direct implementation contract rather than a Python keyword error.
        raise RuntimeError("adapter lacks additive case-load API: " + ", ".join(missing) + "; each function must superpose CASE-minus-LC01 CLOADs exactly once while preserving its zero-delta output bytes")  # State the required backward-compatible extension.


def build_load_ledger(case_id: str, source: Path, base: Path, delta: dict[tuple[int, int], float], counts: dict[int, int] | None, resultant: tuple[float, float, float], parent_identities: dict, registry_row: dict[str, str], dload_identity: bool, non_load_identity: bool | None) -> dict:  # Compose the complete auditable source-to-F3 increment ledger.
    records = [{"nodeId": node, "dof": dof, "deltaN": value} for (node, dof), value in sorted(delta.items())]  # Preserve every physical degree and signed delta without aggregation loss.
    return {"schema": "zhaqing-f3-load-delta-ledger-v1", "caseId": case_id, "status": "PASS" if dload_identity and non_load_identity is not False else "NOT_APPLIED_BLOCKED", "baseCaseId": BASE_CASE_ID, "sourceCaseSha256": sha256_path(source), "baseSourceSha256": sha256_path(base), "loadCasesCsvSha256": FROZEN_LOAD_CASES_CSV_SHA256, "parentEvidence": parent_identities, "caseMetadata": registry_row, "semantics": "case response inherits persisted LC01/F3 coordinates, fixed unstressed lengths, and base axial force; only source CASE-minus-LC01 CLOAD records are superposed", "dloadByteIdentityPass": dload_identity, "nonLoadSemanticIdentityPass": non_load_identity, "recordCount": len(records), "countsByDof": {str(key): value for key, value in (counts or {1: 0, 2: 0, 3: 0}).items()}, "resultantN": list(resultant), "records": records}  # Publish identity, meaning, distribution, and totals in one deterministic contract.


def blocked_response_files(output: Path) -> list[str]:  # Enumerate response-like artifacts prohibited for the expected LC09 block.
    return sorted(path.name for path in output.iterdir() if path.is_file() and path.suffix.lower() in PROHIBITED_BLOCKED_RESPONSE_SUFFIXES) if output.exists() else []  # Inspect only the isolated case directory without deletion.


def publish_corotational_request(path: Path, case_id: str, parent_identities: dict, ledger_sha: str, fine_path: Path, raw_path: Path, canonical_receipt: dict, vtk_receipt: dict, recovery: dict) -> str:  # Publish a deterministic fixed-L0 outer-relinearization handoff for an invalid direct-tangent endpoint.
    request = {"schema": COROTATIONAL_HOOK_SCHEMA, "caseId": case_id, "status": "REQUIRED", "formalResponseComputed": False, "trigger": {"gate": "suspensionIncrementScreeningPass", "maximumSuspensionIncrementToBaseRatio": recovery["receipt"]["maximumSuspensionIncrementToBaseRatio"], "directTangentLimit": 0.50}, "inheritedState": {"equilibriumStateSha256": parent_identities["equilibriumStateSha256"], "fixedUnstressedLengths": True, "prestressRetargetingPermitted": False, "baseCoordinates": "persisted zhaqing-equilibrium-state-v3 nodeCoordinatesMm"}, "loadInput": {"semantics": "validated CASE-minus-LC01 concentrated-load increment", "loadLedgerSha256": ledger_sha}, "tangentSeedEvidence": {"fineDeckSha256": sha256_path(fine_path), "rawDatSha256": sha256_path(raw_path), "canonicalResponseDatSha256": canonical_receipt["sha256"], "vtkSha256": vtk_receipt["sha256"], "formalCaseResponse": False}, "requiredHook": {"callable": "stress_coordination_nonlinear.run_fixed_l0_corotational_case invoked by stress_coordination_load_cases.py with digest-bound inherited state and load inputs", "algorithm": "alternate retained-structure solve and geometrically exact suspension internal equilibrium, rebuilding the fixed-L0 tangent and interface action until displacement, interface-action, and all-axis force residuals close", "requiredOutputs": ["summary.json", "canonical-response.dat", "stress-coordinated.vtk", "K and 10K load-free reaction audits", "case-specific *.outer-iterations.json bound by summary.nonlinearIterationReceiptSha256"], "acceptance": ["all suspension members remain in positive tension", "outer displacement and interface-action residuals converge", "global all-axis force balance closes", "K and 10K reactions converge", "complete finite U/S/VTK coverage"]}, "prohibitedFallbacks": ["claim direct tangent endpoint as PASS", "split the same fixed tangent into cosmetic load steps", "retarget any L0 or initial force", "relax the 0.50 trigger", "reuse the tangent-seed VTK as formal nonlinear response"]}  # Keep the tangent seed auditable while requiring a physically distinct final solver path and only claiming implemented force checks.
    return write_json(path, request)  # Persist the hook request and return its exact byte identity.


def copy_exact_artifact(source: Path, target: Path, expected_sha256: str) -> None:  # Promote one isolated response artifact to its stable case-root name while proving byte identity.
    target.parent.mkdir(parents=True, exist_ok=True)  # Create only the deterministic destination namespace before copying exact bytes.
    shutil.copyfile(source, target)  # Copy without decoding or numerically reserializing any solver or visualization token.
    if sha256_path(target) != expected_sha256:  # Recompute the promoted artifact identity independently from the copy operation.
        raise RuntimeError(f"promoted artifact digest mismatch: {source} -> {target}")  # Stop before a summary can bind altered formal bytes.


def finalize_nonlinear_case(case_id: str, case_source: Path, output: Path, nonlinear_result: dict, parent_identities: dict, ledger_sha: str, delta: dict[tuple[int, int], float], resultant: tuple[float, float, float], registry_row: dict[str, str], direct_seed: dict | None = None, damage_event: dict | None = None, pre_loss_state_sha256: str | None = None) -> dict:  # Convert the complete fixed-L0 high-level result into the shared strict-VTK and case-matrix summary contract.
    summary = dict(nonlinear_result["summaryReadyReceipt"])  # Begin with the nonlinear core's independently evaluated solver, equilibrium, reaction, balance, topology, and coverage Gates.
    nonlinear_state = nonlinear_result["nonlinearResult"]  # Recover terminal native and iteration identities from the same high-level solve.
    canonical_receipt = nonlinear_result["canonicalReceipt"]  # Recover the stable 783-node and 1070-element canonical response receipt.
    vtk_receipt = nonlinear_result["vtkReceipt"]  # Recover the complete deterministic primary-cloud receipt.
    wind_receipt = nonlinear_result["windReceipt"]  # Recover the unchanged explicit G3/G5 formal wind-system exclusion.
    passed = summary.get("status") == "PASS"  # Treat only the nonlinear core's complete Gate conjunction as a formal primary response.
    wind_load_requested = abs(float(registry_row["wind_kPa"])) > 0.0  # Distinguish retained-primary wind screening from an unavailable formal wind-cable-system result.
    reaction_levels = nonlinear_result["reactionAudits"]  # Preserve both independently converged nonlinear K and 10K sensor limits.
    summary.update({"schema": "zhaqing-load-case-summary-v1", "caseId": case_id, "status": "PASS" if passed else "FAIL", "solverExitCode": nonlinear_result["solverExit"], "fatalDiagnostics": [token for token in FATAL_TOKENS if token in nonlinear_result["solverLog"].upper()], "screeningResponseComputed": passed, "formalResponseComputed": passed and not wind_load_requested, "formalPrimarySystemResponseComputed": passed, "formalWindCableResponseComputed": False, "responseScope": "PRIMARY_RETAINED_PLUS_MAIN_SUSPENSION_WITH_WIND_SYSTEM_EXCLUDED", "windLoadRequested": wind_load_requested, "windFormalResponseExcluded": True, "sourceCaseSha256": sha256_path(case_source), "sourceBaselineSha256": parent_identities["baseSha256"], "equilibriumStateSchema": "zhaqing-equilibrium-state-v3", "equilibriumStateSha256": parent_identities["equilibriumStateSha256"], "parentEvidence": parent_identities, "loadLedgerSha256": ledger_sha, "fineDeckSha256": nonlinear_state["terminalDeckSha256"], "rawDatSha256": nonlinear_state["terminalRawDatSha256"], "canonicalResponseDatSha256": canonical_receipt["sha256"], "windExclusionSha256": wind_receipt["sha256"], "vtkSha256": vtk_receipt["sha256"], "canonicalResponse": canonical_receipt, "vtk": vtk_receipt, "reactionAudit": {"levels": reaction_levels, "selectedLevel": "K1E10", "selectedStiffnessNPerMm": 1.0e10}, "deltaLoadResultantN": list(resultant), "deltaLoadRecordCount": len(delta), "corotationalRelinearizationRequired": True, "corotationalRelinearizationCompleted": passed, "corotationalRelinearizationRequestSchema": COROTATIONAL_HOOK_SCHEMA if direct_seed is not None else None, "corotationalRelinearizationRequestSha256": direct_seed.get("requestSha256") if direct_seed is not None else None, "directTangentSeed": direct_seed, "preLossStateSha256": pre_loss_state_sha256, "engineeringReleaseStatus": "BLOCKED_G3_G5"})  # Bind formal nonlinear output bytes to the inherited F3 state and retain the formal wind-evidence boundary without relaxing a numerical Gate.
    if damage_event is not None:  # Publish stable source-ID loss evidence only for the reviewed LC08 alternate path.
        summary["damageEvent"] = damage_event  # Bind pre-loss force and exact source topology removal to the post-loss equilibrium summary.
    summary_sha = write_json(output / "summary.json", summary)  # Persist the decisive summary only after every formal response artifact exists.
    return {"caseId": case_id, "status": summary["status"], "screeningResponseComputed": summary["screeningResponseComputed"], "formalResponseComputed": summary["formalResponseComputed"], "formalPrimarySystemResponseComputed": summary["formalPrimarySystemResponseComputed"], "responseScope": summary["responseScope"], "solverExitCode": summary["solverExitCode"], "fatalDiagnostics": summary["fatalDiagnostics"], "maximumDisplacementMm": summary.get("maximumDisplacementMm"), "minimumFinalSuspensionAxialStressMPa": summary.get("minimumFinalSuspensionAxialStressMPa"), "maximumSuspensionIncrementToBaseRatio": summary.get("maximumSuspensionForceIncrementToF3Ratio"), "verticalReactionBalanceRelative": summary.get("verticalReactionBalanceRelative"), "corotationalRelinearizationRequired": True, "corotationalRelinearizationCompleted": passed, "corotationalRelinearizationRequestSha256": summary.get("corotationalRelinearizationRequestSha256"), "summarySha256": summary_sha, "vtkSha256": vtk_receipt["sha256"], "damageEvent": damage_event, "outputDirectory": str(output)}  # Return the compact matrix row bound to the exact formal nonlinear summary and optional stable damage identity.


def publish_lc09_block(case_source: Path, output: Path, base: Path, base_text: str, parent_identities: dict, registry_row: dict[str, str]) -> dict:  # Publish the expected G3/G5 block without invoking any solver.
    output.mkdir(parents=True, exist_ok=True)  # Create the isolated evidence directory only.
    stale = blocked_response_files(output)  # Detect stale numerical artifacts before writing a new disposition.
    if stale:  # Refuse to relabel any prior response as a valid blocked result.
        raise RuntimeError(f"LC09 blocked directory already contains prohibited response artifacts: {stale}")  # Preserve the zero-response-artifact invariant.
    case_text = case_source.read_text(encoding="ascii")  # Read the exact frozen accidental-case source for load provenance only.
    base_loads = parse_cloads(base_text, base)  # Recover the inherited permanent CLOAD ledger.
    case_loads = parse_cloads(case_text, case_source)  # Recover the requested but unevaluated accidental loading.
    delta = load_delta(base_loads, case_loads)  # Record the requested source delta without applying it.
    resultant = tuple(math.fsum(value for (_node, direction), value in delta.items() if direction == dof) for dof in (1, 2, 3))  # Publish the unapplied requested load resultant.
    dload_identity = keyword_blocks(case_text, "*DLOAD") == keyword_blocks(base_text, "*DLOAD") and len(keyword_blocks(base_text, "*DLOAD")) == 1  # Prove gravity itself did not change.
    ledger = build_load_ledger(BLOCKED_CASE_ID, case_source, base, delta, {dof: sum(1 for _node, direction in delta if direction == dof) for dof in (1, 2, 3)}, resultant, parent_identities, registry_row, dload_identity, None)  # Describe the request while marking non-load identity inapplicable to deliberate damage.
    ledger["status"] = "NOT_APPLIED_BLOCKED_G3_G5"  # Make absence of a numerical load application explicit.
    ledger["nonLoadSemanticIdentityPass"] = None  # Record deliberate topology change without pretending intact-model identity.
    ledger_sha = write_json(output / "load-ledger.json", ledger)  # Persist requested load provenance independently from a response.
    disposition = {"schema": "zhaqing-case-disposition-v1", "caseId": BLOCKED_CASE_ID, "status": "BLOCKED_G3_G5", "matrixStatus": "BLOCKED_EXPECTED", "numericalStatus": "NOT_RUN", "engineeringStatus": "BLOCKED", "formalResponseComputed": False, "solverInvocationCount": 0, "sourceCaseSha256": sha256_path(case_source), "loadLedgerSha256": ledger_sha, "requestedDamage": {"component": "WIND_CABLES", "sourceStableElementId": 1072, "sourceConnectivity": [784, 785], "requestedCableOrdinal": 1}, "preLossState": {"status": "UNAVAILABLE", "reason": "formal wind-system fabrication and completed-state evidence is absent"}, "missingInputs": ["wind-cable fabrication length L0", "wind-cable completed-state axial force N0", "verified wind attachment numbering and geometry", "verified horizontal wind-cable angle", "approved wind-system load-path evidence"], "blockerIssueIds": ["C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001", "U-WIND-001"], "responseArtifactsProduced": [], "prohibitedFallbacks": ["zero response", "NaN response", "LC01 response relabeled as LC09", "unevidenced wind stiffness or prestress"], "parentEvidence": parent_identities, "reason": "LC09 cannot establish a pre-loss wind-cable state or a defensible removal release until G3/G5 source evidence closes"}  # Publish an explicit expected block with no fabricated force, displacement, stress, or VTK field.
    disposition_sha = write_json(output / "case-disposition.json", disposition)  # Persist the only decisive LC09 case-state receipt.
    stale_after = blocked_response_files(output)  # Recheck the directory after receipt publication.
    if stale_after:  # Prove the blocked path remained solver-free.
        raise RuntimeError(f"LC09 unexpectedly produced response artifacts: {stale_after}")  # Fail closed on any response-like file.
    return {"caseId": BLOCKED_CASE_ID, "status": "BLOCKED_EXPECTED", "numericalStatus": "NOT_RUN", "engineeringStatus": "BLOCKED_G3_G5", "solverInvocationCount": 0, "loadLedgerSha256": ledger_sha, "dispositionSha256": disposition_sha, "outputDirectory": str(output)}  # Return the matrix row without response metrics.


def execute_intact_case(case_id: str, case_source: Path, output: Path, base: Path, base_text: str, state: dict, pipeline, adapter, nonlinear, coordinated_nodes: dict, source_groups: dict, element_states: dict, target_axial_stress: dict, condensation: dict, parent_identities: dict, registry_row: dict[str, str]) -> dict:  # Screen one intact increment with the F3 tangent and complete every out-of-range endpoint through fixed-L0 co-rotational equilibrium.
    case_text = case_source.read_text(encoding="ascii")  # Read exact frozen case bytes without replacement.
    if semantic_skeleton(case_text) != semantic_skeleton(base_text):  # Permit only heading and CLOAD-body differences for intact cases.
        raise RuntimeError(f"{case_id} changes non-load model semantics relative to LC01")  # Stop before inheriting F3 into a changed topology or boundary system.
    dload_identity = keyword_blocks(case_text, "*DLOAD") == keyword_blocks(base_text, "*DLOAD") and len(keyword_blocks(base_text, "*DLOAD")) == 1  # Require the same sole gravity instruction byte-for-byte.
    if not dload_identity:  # Reject gravity drift before CASE-minus-LC01 concentrated-load subtraction.
        raise RuntimeError(f"{case_id} DLOAD differs from LC01")  # Prevent double gravity or altered acceleration.
    delta = load_delta(parse_cloads(base_text, base), parse_cloads(case_text, case_source))  # Derive only source CASE-minus-LC01 nodal increments.
    counts, resultant = validate_delta(case_id, delta)  # Enforce independently frozen distribution and resultant evidence.
    output.mkdir(parents=True, exist_ok=True)  # Create one isolated directory so native solver basenames cannot collide across cases.
    seed_output = output / "tangent-seed"  # Isolate the direct F3 tangent response so any mandatory nonlinear formal response cannot overwrite its audit trail.
    seed_output.mkdir(parents=True, exist_ok=True)  # Create the deterministic seed namespace before any native solver invocation.
    ledger = build_load_ledger(case_id, case_source, base, delta, counts, resultant, parent_identities, registry_row, True, True)  # Bind the exact source delta to the persisted F3 parent chain.
    ledger_sha = write_json(output / "load-ledger.json", ledger)  # Persist the complete load distribution before solver execution.
    fine_deck = adapter.build_fine_deck(base_text, coordinated_nodes, source_groups, condensation, delta_cloads=delta)  # Superpose the validated increment exactly once through the adapter's case API.
    fine_stem = f"ZQ_{case_id}"  # Use a deterministic case-specific native CalculiX basename.
    fine_path = seed_output / f"{fine_stem}.inp"  # Resolve the exact retained tangent-seed solver input evidence path.
    fine_path.write_text(fine_deck, encoding="ascii")  # Persist the auditable case deck before native execution.
    solver_exit, solver_log = pipeline.run_calculix(str(ARGS_CCX), seed_output, fine_stem)  # Execute through the same explicit pinned solver command as LC01 while preserving a separate formal-response namespace.
    fatal_hits = [token for token in FATAL_TOKENS if token in solver_log.upper()]  # Detect known fatal diagnostics independently before parsing response.
    if solver_exit != 0 or fatal_hits or not (seed_output / f"{fine_stem}.dat").is_file():  # Preserve a finite failure receipt when native response is unavailable.
        failure = {"schema": "zhaqing-load-case-summary-v1", "caseId": case_id, "status": "FAIL", "solverExitCode": solver_exit, "fatalDiagnostics": fatal_hits, "loadLedgerSha256": ledger_sha, "fineDeckSha256": sha256_path(fine_path), "parentEvidence": parent_identities, "reason": "native retained response did not complete"}  # Report native failure without inventing response fields.
        summary_sha = write_json(output / "summary.json", failure)  # Persist the fail-closed case receipt.
        return {"caseId": case_id, "status": "FAIL", "solverExitCode": solver_exit, "fatalDiagnostics": fatal_hits, "summarySha256": summary_sha, "outputDirectory": str(output)}  # Continue matrix publication with explicit failure.
    raw_path = seed_output / f"{fine_stem}.dat"  # Resolve the immutable native tangent-seed response path.
    raw_sha_before = sha256_path(raw_path)  # Freeze its identity before composed response serialization.
    raw = adapter.parse_raw_response(raw_path)  # Parse exact retained U, RF, and eight-point stress tokens.
    recovery = adapter.recover_suspension_response(raw["displacements"], coordinated_nodes, source_groups, element_states, condensation)  # Recover eliminated suspension increments from the same fixed-L0 tangent.
    audits = [adapter.run_reaction_audit_level(str(ARGS_CCX), seed_output, base_text, coordinated_nodes, source_groups, element_states, condensation, stiffness, label, delta_cloads=delta) for stiffness, label in REACTION_LEVELS]  # Run both precommitted load-free reaction limits with the identical case delta inside the preserved tangent namespace.
    canonical_path = seed_output / "canonical-response.dat"  # Resolve the complete retained-plus-suspension tangent-seed response table.
    canonical_receipt = adapter.write_canonical_response(canonical_path, raw, recovery, source_groups)  # Compose real retained tokens and analytic suspension increments.
    raw_sha_after = sha256_path(raw_path)  # Recompute native identity after every audit and composed-response write.
    if raw_sha_after != raw_sha_before:  # Prove composition left native CalculiX evidence untouched.
        raise RuntimeError(f"{case_id} native DAT changed during canonical composition: before={raw_sha_before} after={raw_sha_after}")  # Reject a broken provenance chain with both observed identities.
    retained_total = {element_id: adapter.average_stress_records(records) for element_id, records in raw["stressTokens"].items()}  # Average complete native retained integration-point tensors for VTK.
    total_stresses = {**retained_total, **recovery["totalTensors"]}  # Compose retained totals and F3-base-plus-increment suspension totals.
    wind_receipt = adapter.write_wind_exclusion(seed_output / "wind-exclusion.json", source_groups)  # Preserve the same formal G3/G5 boundary for every deck-load screening case.
    vtk_receipt = adapter.write_primary_vtk(seed_output / "stress-coordinated.vtk", coordinated_nodes, source_groups, recovery["displacements"], total_stresses, target_axial_stress)  # Serialize complete primary U and total S seed fields without fallback values.
    gate = adapter.evaluate_canonical_gate(fine_deck, coordinated_nodes, source_groups, state, condensation, solver_exit, solver_log, raw, recovery, audits, canonical_receipt, vtk_receipt, wind_receipt)  # Apply the unchanged numerical, tension, tangent-range, reaction, balance, and topology Gates.
    failed_gates = sorted(name for name, passed in gate["gates"].items() if not passed)  # Preserve every decisive direct-tangent failure before classification.
    relinearization_required = not bool(gate["gates"]["suspensionIncrementScreeningPass"])  # Delegate every endpoint beyond the precommitted tangent range while retaining any additional failed Gates explicitly.
    additional_failed_gates = [name for name in failed_gates if name != "suspensionIncrementScreeningPass"]  # Prevent the nonlinear handoff label from hiding reaction, balance, coverage, or solver failures.
    request_sha = publish_corotational_request(output / "corotational-relinearization-request.json", case_id, parent_identities, ledger_sha, fine_path, raw_path, canonical_receipt, vtk_receipt, recovery) if relinearization_required else None  # Publish the fixed-L0 outer-solve hook only when the direct endpoint exceeds its precommitted range.
    if relinearization_required:  # Replace every invalid tangent endpoint by a converged fixed-fabrication nonlinear response under unchanged case loads.
        direct_seed = {"status": "OUT_OF_LINEARIZATION_RANGE", "analysisMode": "F3_FIXED_L0_TANGENT_INCREMENT", "failedGates": failed_gates, "additionalFailedGates": additional_failed_gates, "maximumSuspensionIncrementToBaseRatio": recovery["receipt"]["maximumSuspensionIncrementToBaseRatio"], "fineDeckSha256": sha256_path(fine_path), "rawDatSha256": raw_sha_before, "canonicalResponseDatSha256": canonical_receipt["sha256"], "vtkSha256": vtk_receipt["sha256"], "requestSha256": request_sha, "artifactDirectory": str(seed_output)}  # Preserve why nonlinear re-equilibration was mandatory and bind every screening artifact independently.
        nonlinear_result = nonlinear.run_fixed_l0_corotational_case(pipeline, adapter, str(ARGS_CCX), output, base_text, coordinated_nodes, source_groups, element_states, state, target_axial_stress, delta, case_id)  # Solve the retained structure and geometrically exact fixed-L0 suspension until displacement, action, reaction, and balance Gates close.
        return finalize_nonlinear_case(case_id, case_source, output, nonlinear_result, parent_identities, ledger_sha, delta, resultant, registry_row, direct_seed=direct_seed)  # Publish the formal nonlinear response instead of the invalid tangent endpoint.
    classified_status = "OUT_OF_LINEARIZATION_RANGE" if relinearization_required else gate["status"]  # Keep an invalid tangent endpoint distinct from both physical FAIL and PASS.
    wind_load_requested = abs(float(registry_row["wind_kPa"])) > 0.0  # Distinguish retained-primary wind screening from a formally evidenced wind-system response.
    screening_response_computed = not relinearization_required and gate["status"] == "PASS"  # Accept a direct endpoint only when every numerical screening Gate passes.
    formal_response_computed = screening_response_computed and not wind_load_requested  # Keep every wind-loaded result explicitly nonformal while G3/G5 inventory remains excluded.
    copy_exact_artifact(canonical_path, output / "canonical-response.dat", canonical_receipt["sha256"])  # Promote the accepted direct canonical response to the stable case-matrix path.
    copy_exact_artifact(seed_output / "stress-coordinated.vtk", output / "stress-coordinated.vtk", vtk_receipt["sha256"])  # Promote the accepted direct VTK without changing any field token.
    copy_exact_artifact(seed_output / "wind-exclusion.json", output / "wind-exclusion.json", wind_receipt["sha256"])  # Promote the exact formal exclusion receipt alongside the accepted primary response.
    gate.update({"schema": "zhaqing-load-case-summary-v1", "caseId": case_id, "status": classified_status, "directTangentGateStatus": "PASS" if not failed_gates else "FAIL", "failedDirectTangentGates": failed_gates, "additionalFailedDirectTangentGates": additional_failed_gates, "screeningResponseComputed": screening_response_computed, "formalResponseComputed": formal_response_computed, "formalPrimarySystemResponseComputed": screening_response_computed, "formalWindCableResponseComputed": False, "responseScope": "PRIMARY_RETAINED_PLUS_MAIN_SUSPENSION_WITH_WIND_SYSTEM_EXCLUDED", "windLoadRequested": wind_load_requested, "windFormalResponseExcluded": True, "analysisMode": "F3_FIXED_L0_TANGENT_INCREMENT", "sourceCaseSha256": sha256_path(case_source), "sourceBaselineSha256": parent_identities["baseSha256"], "equilibriumStateSha256": parent_identities["equilibriumStateSha256"], "parentEvidence": parent_identities, "loadLedgerSha256": ledger_sha, "fineDeckSha256": sha256_path(fine_path), "rawDatSha256": raw_sha_before, "canonicalResponseDatSha256": canonical_receipt["sha256"], "windExclusionSha256": wind_receipt["sha256"], "vtkSha256": vtk_receipt["sha256"], "canonicalResponse": canonical_receipt, "vtk": vtk_receipt, "deltaLoadResultantN": list(resultant), "deltaLoadRecordCount": len(delta), "corotationalRelinearizationRequired": relinearization_required, "corotationalRelinearizationRequestSchema": COROTATIONAL_HOOK_SCHEMA if relinearization_required else None, "corotationalRelinearizationRequestSha256": request_sha, "engineeringReleaseStatus": "BLOCKED_G3_G5"})  # Bind case identity, VTK validation fields, wind boundary, every failed seed Gate, and additive-load provenance to the unchanged Gate result.
    summary_sha = write_json(output / "summary.json", gate)  # Persist the decisive per-case result after all response digests exist.
    return {"caseId": case_id, "status": classified_status, "screeningResponseComputed": gate["screeningResponseComputed"], "formalResponseComputed": gate["formalResponseComputed"], "responseScope": gate["responseScope"], "solverExitCode": solver_exit, "fatalDiagnostics": fatal_hits, "maximumDisplacementMm": gate.get("maximumDisplacementMm"), "minimumFinalSuspensionAxialStressMPa": recovery["receipt"].get("minimumFinalSuspensionAxialStressMPa"), "maximumSuspensionIncrementToBaseRatio": recovery["receipt"].get("maximumSuspensionIncrementToBaseRatio"), "verticalReactionBalanceRelative": gate.get("verticalReactionBalanceRelative"), "corotationalRelinearizationRequired": relinearization_required, "corotationalRelinearizationRequestSha256": request_sha, "summarySha256": summary_sha, "vtkSha256": vtk_receipt["sha256"], "outputDirectory": str(output)}  # Return the compact aggregate-matrix row without promoting an invalid tangent seed or blocked wind subsystem.


def execute_damage_case(case_id: str, case_source: Path, output: Path, base: Path, base_text: str, state: dict, pipeline, adapter, nonlinear, coordinated_nodes: dict, source_groups: dict, element_states: dict, target_axial_stress: dict, parent_identities: dict, registry_row: dict[str, str]) -> dict:  # Execute LC08 as an explicit intact-service pre-loss equilibrium followed by stable e1033 removal and survivor re-equilibration.
    case_text = case_source.read_text(encoding="ascii")  # Read the exact frozen accidental-case bytes for load and legacy topology provenance.
    dload_identity = keyword_blocks(case_text, "*DLOAD") == keyword_blocks(base_text, "*DLOAD") and len(keyword_blocks(base_text, "*DLOAD")) == 1  # Require unchanged gravity declaration before any member-loss operation.
    if not dload_identity:  # Refuse an accidental case that silently alters both topology and gravity.
        raise RuntimeError("LC08 DLOAD differs from LC01")  # Stop before applying an ambiguous pre-loss loading state.
    delta = load_delta(parse_cloads(base_text, base), parse_cloads(case_text, case_source))  # Recover the exact LC08 service-crowd increment independently from its topology change.
    counts, resultant = validate_delta(case_id, delta)  # Enforce the frozen LC02-equivalent load distribution and resultant.
    base_source_nodes, base_source_groups, _base_ownership = pipeline.parse_model(base_text)  # Recover immutable stable topology directly from LC01 source bytes.
    case_source_nodes, case_source_groups, _case_ownership = pipeline.parse_model(case_text)  # Recover the legacy LC08 topology only to prove its physical deletion identity.
    if case_source_nodes != base_source_nodes:  # Require member loss without any coordinate or node-label drift.
        raise RuntimeError("LC08 source node geometry differs from LC01")  # Stop before mapping a deleted member between incompatible meshes.
    base_hanger_connectivity = {tuple(connectivity) for _element_id, connectivity in base_source_groups["HANGERS"]}  # Index stable nominal hanger connectivity independently from source numbering after the deletion.
    case_hanger_connectivity = {tuple(connectivity) for _element_id, connectivity in case_source_groups["HANGERS"]}  # Index legacy accidental hanger connectivity while deliberately ignoring its downstream renumbering.
    if base_hanger_connectivity - case_hanger_connectivity != {(294, 638)} or case_hanger_connectivity - base_hanger_connectivity:  # Require one and only one physical hanger deletion at the reviewed ordered endpoints.
        raise RuntimeError("LC08 source does not delete exactly the nominal hanger connectivity (294,638)")  # Reject any alternate or multiple damage topology.
    for group_name in set(base_source_groups) - {"HANGERS"}:  # Prove every nondamaged component retains the same physical connectivity despite legacy element-label shifting.
        if {tuple(connectivity) for _element_id, connectivity in case_source_groups[group_name]} != {tuple(connectivity) for _element_id, connectivity in base_source_groups[group_name]}:  # Compare physical topology independently from unstable post-deletion labels.
            raise RuntimeError(f"LC08 changes nondamaged physical connectivity in {group_name}")  # Stop before treating broader topology drift as one hanger loss.
    stable_record = next(((group_name, connectivity) for group_name in ("MAIN_CABLES", "HANGERS") for element_id, connectivity in source_groups[group_name] if element_id == 1033), None)  # Resolve the stable pre-loss source member from LC01 rather than the renumbered accidental deck.
    if stable_record != ("HANGERS", [294, 638]):  # Require the exact reviewed source label, ownership, and ordered connectivity together.
        raise RuntimeError("stable LC01 source e1033 is not HANGERS (294,638)")  # Stop before deleting a label whose physical meaning has drifted.
    output.mkdir(parents=True, exist_ok=True)  # Create the isolated alternate-path evidence namespace only after source validation closes.
    ledger = build_load_ledger(case_id, case_source, base, delta, counts, resultant, parent_identities, registry_row, True, None)  # Bind the exact service increment while treating the deliberate topology delta under its separate damage contract.
    ledger.update({"status": "PASS", "nonLoadSemanticIdentityPass": None, "damageTopology": {"stableTopologySource": BASE_CASE_ID, "legacyAccidentalSourcePhysicalDeletion": {"group": "HANGERS", "orderedNodeIds": [294, 638]}, "legacyPostDeletionElementRenumberingUsed": False, "stableRemovedSourceElementId": 1033}})  # Make the stable-ID correction explicit without relabeling the frozen legacy source bytes.
    ledger_sha = write_json(output / "load-ledger.json", ledger)  # Persist load and topology provenance before either nonlinear solve begins.
    damage_contract = {"schema": "zhaqing-static-alternate-path-damage-v1", "caseId": "LC08", "analysisClass": "STATIC_ALTERNATE_PATH", "removedElements": [{"elementId": 1033, "group": "HANGERS", "nodeIds": [294, 638]}]}  # Freeze the sole topology exception accepted by the nonlinear core and canonical serializer.
    pre_loss_output = output / "pre-loss-lc02"  # Isolate the complete intact service-load equilibrium from the subsequent damaged response.
    pre_loss = nonlinear.run_coupled_equilibrium(adapter, str(ARGS_CCX), pre_loss_output, "ZQ_LC08_PRELOSS_LC02", base_text, coordinated_nodes, source_groups, element_states, delta_cloads=delta)  # Establish the actual LC02 fixed-L0 nonlinear state before removing any stiffness, self-weight, or force path.
    pre_loss_element = pre_loss["suspensionState"]["elementResponses"][1033]  # Recover the actual event-time force state of the exact stable source hanger.
    pre_loss_l0 = float(pre_loss["context"]["elementData"][1033]["unstressedLengthMm"])  # Recover immutable fabrication length from the accepted F3 parent.
    pre_loss_extension = float(pre_loss_element["lengthMm"]) - pre_loss_l0  # Evaluate actual event-time elastic extension without retargeting L0.
    pre_loss_energy = 0.5 * float(pre_loss_element["axialForceN"]) * pre_loss_extension  # Evaluate the linear-elastic fixed-L0 strain energy released by the static removal in N-mm.
    pre_loss_receipt = {"schema": "zhaqing-lc08-pre-loss-state-v1", "status": "PASS", "caseId": case_id, "preLossLoadCaseId": "LC02_G_Q_SERVICE", "analysisMode": "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION", "equilibriumStateSha256": parent_identities["equilibriumStateSha256"], "loadLedgerSha256": ledger_sha, "nonlinearIterationReceiptSha256": pre_loss["iterationReceiptSha256"], "terminalDeckSha256": pre_loss["terminalDeckSha256"], "terminalRawDatSha256": pre_loss["terminalRawDatSha256"], "stableSourceElement": {"elementId": 1033, "group": "HANGERS", "orderedNodeIds": [294, 638], "unstressedLengthMm": pre_loss_l0, "currentLengthMm": pre_loss_element["lengthMm"], "axialForceN": pre_loss_element["axialForceN"], "axialStressMPa": pre_loss_element["axialStressMPa"], "strainEnergyNmm": pre_loss_energy, "constantSelfWeightN": pre_loss_element["constantSelfWeightN"]}, "maximumInternalResidualN": pre_loss["recovery"]["receipt"]["maximumInternalResidualN"], "minimumSuspensionAxialStressMPa": pre_loss["recovery"]["receipt"]["minimumFinalSuspensionAxialStressMPa"]}  # Bind the damage event to a converged physical pre-loss force, geometry, energy, and exact solver evidence.
    pre_loss_state_sha256 = write_json(pre_loss_output / "pre-loss-state.json", pre_loss_receipt)  # Seal the pre-loss state before constructing any damaged tangent or load transfer.
    post_loss = nonlinear.run_fixed_l0_corotational_case(pipeline, adapter, str(ARGS_CCX), output, base_text, coordinated_nodes, source_groups, element_states, state, target_axial_stress, delta, case_id, removed_ids={1033}, damage_contract=damage_contract, initial_retained_displacements=pre_loss["raw"]["displacements"], initial_suspension_displacements=pre_loss["suspensionState"]["displacementsMm"])  # Remove stable e1033 stiffness and self-weight at the established service state and re-equilibrate all 245 survivors without renumbering or L0 retargeting.
    damage_event = {"schema": "zhaqing-static-alternate-path-damage-v1", "analysisClass": "STATIC_ALTERNATE_PATH", "group": "HANGERS", "sourceElementId": 1033, "orderedNodeIds": [294, 638], "survivorRenumbering": False, "survivorConnectivityRetargeting": False, "survivorUnstressedLengthRetargeting": False, "legacyAccidentalDeckRenumberingUsed": False, "preLossLoadCaseId": "LC02_G_Q_SERVICE", "preLossStateSha256": pre_loss_state_sha256, "preLossAxialForceN": pre_loss_element["axialForceN"], "preLossAxialStressMPa": pre_loss_element["axialStressMPa"], "preLossStrainEnergyNmm": pre_loss_energy, "preLossConstantSelfWeightN": pre_loss_element["constantSelfWeightN"], "eventSequence": ["solve intact LC02 fixed-L0 nonlinear equilibrium", "remove stable LC01 source HANGERS e1033=(294,638)", "exclude removed stiffness and self-weight", "solve 245-survivor fixed-L0 nonlinear equilibrium"], "dynamicAmplificationApplied": False, "postLossActiveSuspensionElementCount": 245, "postLossRemovedSuspensionElementIds": [1033], "canonicalGhostTotalStressMPa": 0.0}  # Publish the exact physical loss sequence, pre-loss demand, survivor invariants, and stable zero-total visualization ghost.
    return finalize_nonlinear_case(case_id, case_source, output, post_loss, parent_identities, ledger_sha, delta, resultant, registry_row, damage_event=damage_event, pre_loss_state_sha256=pre_loss_state_sha256)  # Bind post-loss canonical DAT, VTK, reactions, and all nonlinear Gates to the sealed pre-loss event state.


def resolve_cases(case_ids: list[str], sources: list[Path]) -> list[tuple[str, Path]]:  # Pair explicit ids and sources or infer ids from immutable headings.
    if case_ids and len(case_ids) != len(sources):  # Require positional identity without guessing when ids are supplied.
        raise RuntimeError("--case-id count must equal --case-source count")  # Report the fixed CLI pairing rule.
    resolved: list[tuple[str, Path]] = []  # Preserve invocation order for deterministic execution and matrix rows.
    for index, source in enumerate(sources):  # Validate every requested frozen case source.
        text = source.read_text(encoding="ascii")  # Recover in-file identity from exact source bytes.
        heading_id = parse_case_id(text, source)  # Parse the authoritative heading id.
        case_id = case_ids[index] if case_ids else heading_id  # Use an explicit id only when it agrees with the source.
        if case_id != heading_id:  # Reject filename or CLI relabeling of immutable case bytes.
            raise RuntimeError(f"case id {case_id} does not match source heading {heading_id}")  # Expose the exact identity mismatch.
        if case_id not in SUPPORTED_CASE_IDS:  # Keep every unreviewed source outside the frozen complete matrix path.
            raise RuntimeError(f"unsupported case {case_id}; expected one of {SUPPORTED_CASE_IDS}")  # Report the exact reviewed matrix scope without relabeling another input.
        if sha256_path(source) != FROZEN_SOURCE_SHA256[case_id]:  # Require reviewed source bytes before parsing loads.
            raise RuntimeError(f"{case_id} source SHA-256 does not match the frozen PR9 artifact")  # Reject drift in load, topology, or text provenance.
        resolved.append((case_id, source))  # Preserve the verified case-source pair.
    if len({case_id for case_id, _source in resolved}) != len(resolved):  # Reject duplicate execution or receipt overwrite.
        raise RuntimeError("duplicate case ids are not allowed")  # Preserve one result identity per matrix row.
    return resolved  # Return only byte-verified supported cases.


def main() -> int:  # Validate the inherited LC01/F3 chain, execute intact deltas, and publish an expected LC09 block.
    parser = argparse.ArgumentParser()  # Build the deterministic multi-case command line.
    parser.add_argument("--module", type=Path, required=True)  # Require the exact reconstructed P0-P2 pipeline source.
    parser.add_argument("--adapter-module", type=Path, required=True)  # Require the exact reconstructed canonical P3 adapter source.
    parser.add_argument("--nonlinear-module", type=Path, required=True)  # Require the reviewed fixed-L0 co-rotational suspension implementation for mandatory large-increment and damage paths.
    parser.add_argument("--base", type=Path, required=True)  # Require immutable frozen LC01_G_DEAD.inp bytes.
    parser.add_argument("--equilibrium-state", type=Path, required=True)  # Require the persisted successful F3 v3 state rather than regeneration.
    parser.add_argument("--base-summary", type=Path, required=True)  # Require the successful canonical LC01 Gate receipt.
    parser.add_argument("--base-canonical-dat", type=Path, required=True)  # Require the canonical LC01 response bytes named by the receipt.
    parser.add_argument("--load-cases-csv", type=Path, required=True)  # Require the immutable reviewed case registry.
    parser.add_argument("--case-id", action="append", default=[])  # Optionally pair an explicit id with each repeated source.
    parser.add_argument("--case-source", type=Path, action="append", required=True)  # Accept one or more frozen LC02-LC09 sources under their reviewed case-specific disposition.
    parser.add_argument("--output", type=Path, required=True)  # Require the common calculation root containing isolated cases and the aggregate matrix receipt.
    parser.add_argument("--ccx", required=True)  # Require the pinned native CalculiX executable or command.
    args = parser.parse_args()  # Resolve all paths before evidence publication.
    global ARGS_CCX  # Bind the explicit solver command for the narrow per-case execution helper.
    ARGS_CCX = args.ccx  # Preserve the exact caller-supplied CalculiX command without environment discovery.
    registry = validate_registry(args.load_cases_csv)  # Freeze the meaning of every requested case before source interpretation.
    resolved = resolve_cases(args.case_id, args.case_source)  # Bind each requested id to exact source bytes.
    state, _base_summary, parent_identities = validate_parent_identity(args.base, args.equilibrium_state, args.base_summary, args.base_canonical_dat)  # Consume only the proven persisted LC01/F3 parent chain.
    pipeline = load_python_module(args.module, "zhaqing_case_pipeline")  # Load audited shared model parsers and native solver wrapper.
    adapter = load_python_module(args.adapter_module, "zhaqing_case_adapter")  # Load audited condensation, recovery, Gate, and serialization functions.
    adapter.bind_globals(pipeline)  # Bind the adapter to the same pipeline constants and utilities used by canonical LC01.
    nonlinear = load_python_module(args.nonlinear_module, "zhaqing_case_nonlinear")  # Load the explicit fixed-fabrication nonlinear core without mutating import search paths.
    required_nonlinear_api = ("run_coupled_equilibrium", "run_fixed_l0_corotational_case")  # Freeze the two high-level operations required by intact relinearization and LC08 sequencing.
    if any(not callable(getattr(nonlinear, name, None)) for name in required_nonlinear_api):  # Reject a partial or older nonlinear module before any solver invocation.
        raise RuntimeError(f"nonlinear module must expose callable APIs {required_nonlinear_api}")  # Report the exact implementation boundary required by this runner.
    base_text = args.base.read_text(encoding="ascii")  # Read immutable LC01 source once for all exact subtractions.
    source_nodes, source_groups, _ownership = pipeline.parse_model(base_text)  # Recover the reviewed complete source topology.
    coordinated_nodes, element_states, target_axial_stress = adapter.validate_state_v3(state, args.base, source_nodes, source_groups)  # Validate complete persisted F3 geometry, L0, force, and topology coverage.
    condensation = adapter.build_suspension_condensation(base_text, source_nodes, source_groups, coordinated_nodes, element_states, state)  # Reconstruct the unchanged F3 tangent once for all intact cases.
    if any(case_id in INTACT_CASE_IDS for case_id, _source in resolved):  # Require the additive adapter API only when a numerical intact case is requested.
        require_case_adapter_api(adapter)  # Fail before solver invocation when the canonical adapter has not been extended safely.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the aggregate evidence root after all parent validations pass.
    rows: list[dict] = []  # Accumulate compact result rows without losing per-case detailed receipts.
    for case_id, source in resolved:  # Execute each byte-verified source in caller order.
        case_output = args.output / "cases" / case_id  # Isolate every native solver and receipt namespace below the common calculation root.
        if case_id == BLOCKED_CASE_ID:  # Keep the unresolved wind-system damage path strictly solver-free.
            rows.append(publish_lc09_block(source, case_output, args.base, base_text, parent_identities, registry[case_id]))  # Publish only the expected block disposition.
        elif case_id == DAMAGE_CASE_ID:  # Route stable source hanger e1033 loss to its explicit alternate-path implementation.
            rows.append(execute_damage_case(case_id, source, case_output, args.base, base_text, state, pipeline, adapter, nonlinear, coordinated_nodes, source_groups, element_states, target_axial_stress, parent_identities, registry[case_id]))  # Run intact LC02 pre-loss equilibrium, stable-ID release, survivor recovery, and damage-specific Gates.
        else:  # Execute one intact post-F3 load increment.
            rows.append(execute_intact_case(case_id, source, case_output, args.base, base_text, state, pipeline, adapter, nonlinear, coordinated_nodes, source_groups, element_states, target_axial_stress, condensation, parent_identities, registry[case_id]))  # Run real tangent screening followed by mandatory fixed-L0 nonlinear equilibrium when required.
    numerical_failures = [row["caseId"] for row in rows if row["status"] not in ("PASS", "BLOCKED_EXPECTED")]  # Treat only direct PASS or the predeclared LC09 block as final completion.
    relinearization_cases = [row["caseId"] for row in rows if row.get("corotationalRelinearizationRequired") is True]  # Expose every case that completed or still requires the fixed-L0 co-rotational path independently from its final PASS status.
    requested_ids = [case_id for case_id, _source in resolved]  # Preserve exact requested matrix scope.
    scope_complete = set(requested_ids) == set(SUPPORTED_CASE_IDS)  # Require LC02-LC09 exactly before calling the aggregate matrix complete.
    missing_case_ids = sorted(set(SUPPORTED_CASE_IDS) - set(requested_ids))  # Publish every omitted required result explicitly.
    matrix_status = "COMPLETE_WITH_EXPECTED_BLOCKS" if not numerical_failures and scope_complete else "FAIL"  # Require full scope and final valid case responses without converting expected evidence gaps to numerical PASS.
    matrix = {"schema": "zhaqing-f3-load-case-matrix-v1", "status": matrix_status, "numericalQualificationStatus": "PASS" if matrix_status == "COMPLETE_WITH_EXPECTED_BLOCKS" else "FAIL", "requestedCaseIds": requested_ids, "requiredRunnableCaseIds": list(RUNNABLE_CASE_IDS), "expectedBlockedCaseIds": [BLOCKED_CASE_ID], "scopeComplete": scope_complete, "missingCaseIds": missing_case_ids, "numericalFailureCaseIds": numerical_failures, "corotationalRelinearizationRequiredCaseIds": relinearization_cases, "corotationalHookSchema": COROTATIONAL_HOOK_SCHEMA, "parentEvidence": parent_identities, "loadCasesCsvSha256": FROZEN_LOAD_CASES_CSV_SHA256, "cases": rows, "engineeringReleaseStatus": "BLOCKED", "meaning": "LC02-LC07 inherit one persisted F3 fixed-L0 state and LC08 applies a stable-ID alternate-path release; any direct range failure must complete the fixed-L0 co-rotational hook; LC09 remains an expected solver-free G3/G5 block"}  # Bind all runnable results, nonlinear handoffs, damage event, and expected engineering block into one matrix receipt.
    matrix_sha = write_json(args.output / "case-matrix.json", matrix)  # Persist the decisive aggregate result after every per-case receipt exists.
    print(json.dumps({**matrix, "caseMatrixSha256": matrix_sha}, ensure_ascii=False, indent=2))  # Mirror the complete matrix receipt and its byte identity to the workflow log.
    return 0 if matrix_status == "COMPLETE_WITH_EXPECTED_BLOCKS" else 2  # Make process success follow all requested numerical Gates plus the expected LC09 block.


ARGS_CCX = ""  # Initialize the explicit solver command before guarded CLI execution.


if __name__ == "__main__":  # Execute only when the dedicated workflow invokes this runner directly.
    raise SystemExit(main())  # Propagate the fail-closed matrix status through the native process exit code.
