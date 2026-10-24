#!/usr/bin/env python3  # Execute real fixed-L0 bridge scenarios and publish audited learning labels.
import argparse  # Parse explicit original-model, scenario, solver, and output locations.
import hashlib  # Bind every scenario to the exact frozen original inputs.
import importlib.util  # Import the existing solver modules without changing their source.
import json  # Read scenario lists and write reproducible evidence manifests.
import math  # Validate finite load factors and compute stable load resultants.
import os  # Atomically replace complete manifest files after each finished scenario.
import re  # Enforce the original nonlinear solver's case identifier grammar.
import subprocess  # Record the actual native solver version and classify timeouts.
import shutil  # Publish completed immutable native case trees after solving.
import tempfile  # Stage live native writes outside synchronized workspace paths.
import sys  # Support ordinary command-line execution and clean status propagation.
import time  # Measure real elapsed computation cost for each scenario.
import traceback  # Preserve complete failure diagnostics without promoting failed labels.
import zipfile  # Preserve immutable native solver evidence inside one complete case snapshot.
from concurrent.futures import ProcessPoolExecutor, as_completed  # Isolate original mutable module globals while solving independent cases concurrently.
from pathlib import Path  # Keep every consumed and generated file path explicit.
ROOT = Path(__file__).resolve().parents[2]  # Resolve the shared Git repository independently of the caller directory.
WORKSPACE = ROOT.parent  # Resolve the current task workspace without assuming a user home directory.
SCHEMA = "zhaqing-md-real-fem-dataset-v1"  # Identify the single-bridge actual-solver dataset contract.
SPLITS = {"train", "validation", "test", "calibration", "ood"}  # Keep frozen evaluation partitions separate from training.
WORKER_ARGS, WORKER_CONTEXT = None, None  # Hold one independently validated original solver context per worker process.
def sha256(path):  # Compute the exact identity of one evidence file.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Include original numeric spelling and line endings in provenance.
def write_json(path, payload):  # Publish a complete deterministic JSON record atomically.
    path = Path(path)  # Accept explicit string or Path destinations consistently.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the intended evidence namespace.
    temporary = path.with_name(path.name + ".tmp")  # Avoid exposing partially written manifests to the training process.
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Reject nonfinite metadata and preserve readable records.
    os.replace(temporary, path)  # Install the completed record without changing its intended identity.
    return sha256(path)  # Return the exact persisted identity for downstream linkage.
def load_module(path, name):  # Load an existing audited module from its explicit path.
    specification = importlib.util.spec_from_file_location(name, path)  # Bind import execution to the caller's frozen source file.
    if specification is None or specification.loader is None:  # Reject missing import machinery before running a solver.
        raise RuntimeError(f"Cannot import {path}")  # Identify the unavailable source file directly.
    module = importlib.util.module_from_spec(specification)  # Allocate an isolated module namespace.
    specification.loader.exec_module(module)  # Execute original definitions without rewriting the source.
    return module  # Return the existing implementation and constants unchanged.
def validate_scenarios(path):  # Validate the entire requested domain and split list before any numerical execution.
    supplied = json.loads(Path(path).read_text(encoding="utf-8"))  # Read the explicit scenario configuration once.
    records = supplied.get("scenarios") if isinstance(supplied, dict) else supplied  # Support a direct list or a named list inside a configuration object.
    if not isinstance(records, list) or not records:  # Require at least one concrete scenario.
        raise ValueError("Scenario JSON must contain a nonempty list or a scenarios list")  # Reject ambiguous or empty work requests.
    normalized = []  # Accumulate validated independent load cases in caller order.
    identifiers = set()  # Prevent case-directory collisions inside one execution request.
    for item in records:  # Validate every scenario before creating any calculation output.
        if not isinstance(item, dict):  # Require named fields for physical meaning.
            raise ValueError("Each scenario must be an object")  # Reject anonymous parameter vectors.
        case_id = str(item.get("case_id", item.get("id", "")))  # Permit the two explicit case-identifier spellings.
        if re.fullmatch(r"LC\d\d_[A-Z0-9_]+", case_id) is None or case_id in identifiers:  # Preserve the original nonlinear grammar and unique directories.
            raise ValueError(f"Invalid or duplicate original-style case id: {case_id}")  # Stop before any filesystem or solver mutation.
        q, asym = float(item.get("q", 0.0)), float(item.get("asym", 0.0))  # Read the uniform and asymmetric source-load multipliers.
        if not all(math.isfinite(value) for value in (q, asym)) or min(q, asym) < 0.0 or q + asym > 1.0 + 1.0e-12:  # Limit interpolation to the declared nonnegative service-load triangle.
            raise ValueError(f"{case_id} requires q>=0, asym>=0, q+asym<=1")  # Reject loads outside the approved scenario domain.
        split = str(item.get("split", "train"))  # Preserve an explicit training or evaluation assignment.
        if split not in SPLITS:  # Refuse arbitrary split names that could leak evaluation labels.
            raise ValueError(f"Unsupported split {split} for {case_id}")  # Identify the invalid partition directly.
        factors = [q, 0.0, asym]  # Freeze feature order as uniform-live, wind, asymmetric-live multipliers.
        if "factors" in item and list(item["factors"]) != factors:  # Reject conflicting redundant load-factor representations.
            raise ValueError(f"factors disagrees with q/asym for {case_id}")  # Preserve one authoritative physical load definition.
        normalized.append({"case_id": case_id, "q": q, "asym": asym, "factors": factors, "split": split, "round": int(item.get("round", 0)), "selection_reason": str(item.get("selection_reason", "declared_initial_design"))})  # Preserve scientific split and acquisition provenance.
        identifiers.add(case_id)  # Reserve this output identity before later validation.
    return normalized  # Return only a complete validated request.
def prepare_context(args):  # Validate the original LC01/F3 chain and two immutable service-load directions.
    cases_path = ROOT / "automation/zhaqing_calculix/stress_coordination_load_cases.py"  # Locate the original source and identity validation helpers.
    nonlinear_path = ROOT / "automation/zhaqing_calculix/stress_coordination_nonlinear.py"  # Locate the actual original fixed-L0 nonlinear solver.
    pipeline_path = args.generated / "stress_coordination_pipeline.py"  # Resolve the already reconstructed original pipeline.
    adapter_path = args.generated / "stress_coordination_condensed_adapter.py"  # Resolve the already reconstructed original adapter.
    cases = load_module(cases_path, "md_existing_cases")  # Reuse original immutable source contracts.
    state, baseline_summary, parent = cases.validate_parent_identity(args.base, args.calculation / "equilibrium_state.json", args.calculation / "summary.json", args.calculation / "canonical-response.dat")  # Reject disconnected or unqualified parent-state evidence.
    pipeline = load_module(pipeline_path, "md_existing_pipeline")  # Load original model parsing and native execution code.
    adapter = load_module(adapter_path, "md_existing_adapter")  # Load original condensation and dual-reaction quality gates.
    adapter.bind_globals(pipeline)  # Bind the adapter to the exact original pipeline implementation.
    nonlinear = load_module(nonlinear_path, "md_existing_nonlinear")  # Load the exact current-tangent nonlinear suspension algorithm.
    cases.require_case_adapter_api(adapter)  # Verify both response and reaction paths accept physical load increments.
    base_text = args.base.read_text(encoding="ascii")  # Retain every original structural, material, and boundary definition.
    nodes, groups, ownership = pipeline.parse_model(base_text)  # Recover original stable node and element identities.
    coordinated, elements, target_stress = adapter.validate_state_v3(state, args.base, nodes, groups)  # Freeze accepted F3 geometry, axial force, and unstressed lengths.
    base_loads = cases.parse_cloads(base_text, args.base)  # Recover the original permanent nodal-load ledger.
    deltas, source_identity = {}, {}  # Accumulate independently validated physical live-load increments.
    for name in ("LC02_G_Q_SERVICE", "LC03_G_Q_ASYM_SERVICE"):  # Use only the user's original uniform and asymmetric service patterns.
        source = args.source_cases / f"{name}.inp"  # Resolve the recovered exact source input.
        source_identity[name] = sha256(source)  # Preserve the source byte identity in every dataset generation.
        if source_identity[name] != cases.FROZEN_SOURCE_SHA256[name]:  # Reject replaced geometry or silently edited load patterns.
            raise RuntimeError(f"Frozen original source mismatch: {source}")  # Stop before generating misleading labels.
        source_text = source.read_text(encoding="ascii")  # Read the original source case without reserialization.
        if cases.semantic_skeleton(source_text) != cases.semantic_skeleton(base_text):  # Require identical original topology, boundary, material, gravity, and analysis semantics.
            raise RuntimeError(f"Non-load model differs from LC01 in {source}")  # Reject model drift during load-domain construction.
        deltas[name] = cases.load_delta(base_loads, cases.parse_cloads(source_text, source))  # Subtract permanent loading exactly once from each original case.
        cases.validate_delta(name, deltas[name])  # Apply original record-count and resultant checks to each source direction.
    version = subprocess.run([str(args.ccx), "-v"], capture_output=True, text=True, check=False)  # Read the real native version without assuming a zero version-query exit code.
    provenance = {"parent_evidence": parent, "source_load_sha256": source_identity, "module_sha256": {str(path): sha256(path) for path in (cases_path, nonlinear_path, pipeline_path, adapter_path)}, "solver_entry": str(args.ccx), "solver_entry_sha256": sha256(args.ccx), "solver_version": (version.stdout + version.stderr).strip(), "solver_version_query_exit": version.returncode, "bridge_id": "zhaqing-suspension-bridge", "response_scope": "PRIMARY_RETAINED_PLUS_MAIN_SUSPENSION_WITH_WIND_SYSTEM_EXCLUDED", "analysis_mode": "LINEAR_RETAINED_PLUS_FIXED_L0_COROTATIONAL_SUSPENSION", "units": {"length": "mm", "force": "N", "stress": "MPa"}, "fixed_parameters": ["F3_coordinates", "unstressed_lengths_L0", "materials", "sections", "connectivity", "supports", "permanent_load"], "factor_order": ["uniform_service_live_load", "wind_load", "asymmetric_service_live_load"]}  # Describe actual mechanics, executable, and source identity explicitly.
    return {"cases": cases, "state": state, "pipeline": pipeline, "adapter": adapter, "nonlinear": nonlinear, "base_text": base_text, "groups": groups, "coordinated": coordinated, "elements": elements, "target_stress": target_stress, "deltas": deltas, "provenance": provenance}  # Share immutable validated inputs across scenarios.
def snapshot_native_evidence(output):  # Capture native bytes inside the solving process before other readers inspect loose artifacts.
    archive_path = output / "native-evidence.zip"  # Keep one independent immutable evidence container per case.
    entries = sorted(path for path in output.rglob("*") if ".rsync-tmp" not in path.parts and path.is_file() and path.suffix in {".inp", ".dat", ".json", ".log"})  # Preserve native decks, responses, iteration receipts, and execution traces.
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:  # Write the complete snapshot before exposing its receipt.
        for path in entries:  # Store each existing evidence file under its exact relative namespace.
            archive.write(path, path.relative_to(output).as_posix())  # Preserve original bytes rather than reconstructing numerical output.
    checked, mismatches = 0, []  # Independently compare archived numerical bytes to original iteration receipts.
    with zipfile.ZipFile(archive_path, "r") as archive:  # Verify the completed archive without consulting mutable loose result files.
        names = set(archive.namelist())  # Resolve exact internal evidence names for deterministic matching.
        for name in sorted(names):  # Inspect every recorded original nonlinear iteration.
            if not name.endswith(".iteration.json"):  # Restrict byte identities to original iteration receipt contracts.
                continue  # Leave unrelated metadata inside the snapshot without guessing its schema.
            receipt = json.loads(archive.read(name))  # Read the archived original receipt as authoritative expected identities.
            prefix = name.removesuffix(".iteration.json")  # Recover the exact native solver file stem.
            for suffix, key in ((".inp", "deckSha256"), (".dat", "rawDatSha256")):  # Check original input and numerical output independently.
                target = prefix + suffix  # Resolve the native archive member corresponding to this iteration.
                actual = hashlib.sha256(archive.read(target)).hexdigest() if target in names else None  # Compute the archived bytes' actual identity or explicit absence.
                checked += 1  # Account for every required native input/output comparison.
                if actual != receipt.get(key):  # Report any damaged or missing bytes instead of silently claiming a complete snapshot.
                    mismatches.append({"path": target, "expected_sha256": receipt.get(key), "actual_sha256": actual})  # Retain exact repair requirements for independent replay.
    return {"path": str(archive_path.resolve()), "sha256": sha256(archive_path), "checked_native_files": checked, "status": "PASS" if not mismatches else "INCOMPLETE", "mismatches": mismatches}  # Publish actual snapshot integrity without altering original solver receipts.
def execute_scenario(args, context, scenario):  # Compute one genuine nonlinear response and its independent reaction audits.
    output = args.native_workdir / "cases" / scenario["case_id"]  # Isolate native solver evidence by immutable case identity.
    request = {"scenario": scenario, "provenance": context["provenance"]}  # Bind the exact scientific request and physical parent state.
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, allow_nan=False).encode()).hexdigest()  # Construct a reproducible request identity independent of formatting.
    receipt_path = output / "label_receipt.json"  # Resolve the stable scientific label record.
    if receipt_path.exists():  # Permit reproducible resumption without silently overwriting previous solver evidence.
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))  # Recover the prior completed record.
        if existing.get("request_fingerprint") != fingerprint:  # Refuse an identifier reused for another load or parent model.
            raise RuntimeError(f"Existing scenario identity conflicts at {output}; choose a new case_id")  # Preserve the original evidence namespace.
        if existing.get("quality_status") == "VALID_CONVERGED" and sha256(existing["canonical_dat"]) != existing["canonical_dat_sha256"]:  # Recheck label bytes before reusing a successful receipt.
            raise RuntimeError(f"Existing canonical response changed at {output}")  # Reject stale or modified successful labels.
        return existing  # Reuse the completed case without inventing a second solve cost.
    output.mkdir(parents=True, exist_ok=True)  # Create a new isolated case namespace after identity validation.
    write_json(output / "request.json", {**request, "request_fingerprint": fingerprint})  # Preserve the requested factors and source chain before solving.
    uniform = context["deltas"]["LC02_G_Q_SERVICE"]  # Select the original uniform service live-load increment.
    asymmetric = context["deltas"]["LC03_G_Q_ASYM_SERVICE"]  # Select the original asymmetric service live-load increment.
    keys = sorted(set(uniform) | set(asymmetric))  # Preserve stable node-degree order for physical load assembly.
    delta = {key: scenario["q"] * uniform.get(key, 0.0) + scenario["asym"] * asymmetric.get(key, 0.0) for key in keys}  # Combine load vectors only, never combine response labels.
    delta = {key: value for key, value in delta.items() if abs(value) > 1.0e-12}  # Remove arithmetic zeros under the original source threshold.
    resultant = [math.fsum(value for (node, dof), value in delta.items() if dof == direction) for direction in (1, 2, 3)]  # Audit the complete applied external-load increment.
    ledger_sha = write_json(output / "load-ledger.json", {"case_id": scenario["case_id"], "factors": scenario["factors"], "source_load_sha256": context["provenance"]["source_load_sha256"], "delta_resultant_N": resultant, "records": [{"node_id": node, "dof": dof, "delta_N": value} for (node, dof), value in delta.items()], "operation": "q*(LC02-LC01)+asym*(LC03-LC01)", "response_superposition": False})  # Persist every applied physical nodal load.
    start = time.perf_counter()  # Start actual wall-time accounting immediately before numerical execution.
    result, error = None, None  # Keep successful numerical output distinct from failure diagnostics.
    try:  # Preserve complete failure evidence while allowing later requested cases to execute.
        result = context["nonlinear"].run_fixed_l0_corotational_case(context["pipeline"], context["adapter"], str(args.ccx), output, context["base_text"], context["coordinated"], context["groups"], context["elements"], context["state"], context["target_stress"], delta, scenario["case_id"])  # Execute original nonlinear equilibrium plus both original K and 10K support-reaction audits.
        summary = dict(result["summaryReadyReceipt"])  # Preserve every original numerical gate and its unmodified tolerance.
        quality = "VALID_CONVERGED" if summary.get("status") == "PASS" else "NUMERICAL_FAILURE"  # Isolate rejected numerical labels without declaring structural failure.
    except (MemoryError, subprocess.TimeoutExpired) as exception:  # Distinguish resource interruption from numerical or structural behavior.
        quality, error = "RESOURCE_INTERRUPTED", str(exception)  # Publish only the observed execution failure type.
        summary = {"status": "FAIL", "failedGates": ["execution_resource"], "error": error}  # Keep unsuccessful solves out of valid labels.
        (output / "failure_traceback.log").write_text(traceback.format_exc(), encoding="utf-8")  # Preserve full diagnostic evidence for repair.
    except Exception as exception:  # Capture real original-solver failures without manufacturing a response.
        quality, error = "NUMERICAL_FAILURE", str(exception)  # Treat failed computation as a numerical sample disposition.
        summary = {"status": "FAIL", "failedGates": ["original_solver_execution"], "error": error}  # Record the missing numerical qualification explicitly.
        (output / "failure_traceback.log").write_text(traceback.format_exc(), encoding="utf-8")  # Preserve the exact original solver diagnostic stack.
    snapshot = snapshot_native_evidence(output)  # Preserve and verify actual native bytes immediately in the solving process.
    elapsed = time.perf_counter() - start  # Record actual complete solve, reaction audit, and evidence-snapshot elapsed time.
    canonical = output / "canonical-response.dat"  # Identify the original serializer's actual computed response artifact.
    summary.update({"case_id": scenario["case_id"], "quality_status": quality, "factors": scenario["factors"], "split": scenario["split"], "round": scenario["round"], "wall_time_s": elapsed, "parent_evidence": context["provenance"]["parent_evidence"], "load_ledger_sha256": ledger_sha, "request_fingerprint": fingerprint, "native_evidence_snapshot": snapshot, "engineeringReleaseStatus": "BLOCKED_G3_G5", "structural_failure_label": None})  # Add provenance and dataset disposition without changing original mechanics or gate results.
    if result is not None:  # Preserve full independent reaction and native-terminal evidence when the original API returned normally.
        summary.update({"reactionAudit": {"levels": result["reactionAudits"], "selectedLevel": "K1E10"}, "canonicalResponse": result["canonicalReceipt"], "vtk": result["vtkReceipt"], "terminal_deck": str(result["nonlinearResult"]["terminalDeckPath"]), "solverExitCode": result["solverExit"]})  # Retain both support levels and exact native output identities.
    summary_path = output / "summary.json"  # Resolve the final complete numerical qualification record.
    summary_sha = write_json(summary_path, summary)  # Publish the complete result before making the label discoverable.
    receipt = {**scenario, "bridge_id": "zhaqing-suspension-bridge", "quality_status": quality, "quality_flag": quality, "eligible_for_training": quality == "VALID_CONVERGED" and scenario["split"] == "train", "reference_label_available": quality == "VALID_CONVERGED", "canonical_dat": str(canonical.resolve()) if quality == "VALID_CONVERGED" else None, "canonical_dat_sha256": sha256(canonical) if quality == "VALID_CONVERGED" else None, "summary": str(summary_path.resolve()), "summary_path": str(summary_path.resolve()), "summary_sha256": summary_sha, "label_receipt_path": str(receipt_path.resolve()), "output_directory": str(output.resolve()), "wall_time_s": elapsed, "request_fingerprint": fingerprint, "load_ledger_sha256": ledger_sha, "delta_resultant_N": resultant, "source_sha256": context["provenance"]["source_load_sha256"], "parent_evidence": context["provenance"]["parent_evidence"], "removed_element_ids": [], "structural_failure_label": None, "error": error}  # Offer only qualified references to downstream training and evaluation.
    write_json(receipt_path, receipt)  # Finalize the case label receipt only after all linked evidence exists.
    print(json.dumps({key: receipt[key] for key in ("case_id", "factors", "split", "quality_status", "wall_time_s", "canonical_dat")}), flush=True)  # Stream compact actual progress without large solver traces.
    return receipt  # Return the immutable manifest row for this finished scenario.
def initialize_worker(args):  # Give each process its own original solver modules and immutable physical context.
    global WORKER_ARGS, WORKER_CONTEXT  # Bind only process-local state, never shared mutable module globals.
    WORKER_ARGS, WORKER_CONTEXT = args, prepare_context(args)  # Independently validate the same frozen input chain once per worker.
def worker_scenario(scenario):  # Compute one assigned case inside an isolated worker process.
    return execute_scenario(WORKER_ARGS, WORKER_CONTEXT, scenario)  # Reuse only that process's validated original solver context.
def completed_scenarios(args, context, scenarios):  # Stream finished independent numerical cases while the parent owns all manifest writes.
    if args.workers == 1:  # Preserve ordinary sequential execution for inspection or constrained resources.
        for scenario in scenarios:  # Visit the frozen requested case order without sharing solver state.
            yield execute_scenario(args, context, scenario)  # Return each complete result to the sole manifest writer.
        return  # Avoid starting a redundant process pool after sequential completion.
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize_worker, initargs=(args,)) as executor:  # Use at most four isolated solver processes as explicitly configured.
        pending = {executor.submit(worker_scenario, scenario): scenario["case_id"] for scenario in scenarios}  # Queue unique independent output directories only.
        for future in as_completed(pending):  # Publish finished results without waiting for the slowest unrelated case.
            yield future.result()  # Preserve original exceptions when initialization or receipt validation fails.
def main():  # Execute the full configured single-bridge numerical dataset generation.
    parser = argparse.ArgumentParser(description="Run real original fixed-L0 Zhaqing scenarios and both reaction audits")  # Define the executable scientific entry point.
    parser.add_argument("--scenarios", type=Path, required=True)  # Require an explicit frozen scenario list.
    parser.add_argument("--base", type=Path, default=WORKSPACE / "zhaqing-inputs/LC01_G_DEAD.inp")  # Default to the exact recovered original mother model.
    parser.add_argument("--source-cases", type=Path, default=WORKSPACE / "zhaqing-inputs/recovered_cases/flat")  # Locate the exact recovered original load cases.
    parser.add_argument("--calculation", type=Path, default=ROOT / "build/zhaqing-md-20261024/calculation")  # Consume the existing qualified LC01/F3 evidence chain.
    parser.add_argument("--generated", type=Path, default=ROOT / "build/zhaqing-md-20261024/generated")  # Consume the existing original reconstructed solver modules.
    parser.add_argument("--ccx", type=Path, default=WORKSPACE / "solver-runtime/ccx")  # Execute the real available CalculiX 2.21 entry point.
    parser.add_argument("--output", type=Path, default=ROOT / "build/zhaqing-md-20261024/learning")  # Keep new learning scenarios separate from original case-matrix results.
    parser.add_argument("--manifest", type=Path)  # Optionally maintain one shared sequentially updated dataset manifest.
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)  # Bound true process-based solver concurrency to four independent cases.
    args = parser.parse_args()  # Resolve concrete caller choices before numerical validation.
    for name in ("scenarios", "base", "source_cases", "calculation", "generated", "ccx", "output"):  # Normalize all scientific file locations consistently.
        setattr(args, name, getattr(args, name).resolve())  # Preserve absolute artifact references for downstream agents.
    args.native_workdir = Path(tempfile.gettempdir()) / "zhaqing-native-v3" / hashlib.sha256(str(args.output).encode()).hexdigest()[:20]  # Use a stable isolated execution directory per requested dataset for safe resume.
    manifest_path = args.manifest.resolve() if args.manifest else args.output / "dataset_manifest.json"  # Select the complete dataset record destination.
    scenarios = validate_scenarios(args.scenarios)  # Reject invalid domains or partitions before numerical work begins.
    context = prepare_context(args)  # Prove original model, state, load, and solver identity before solving.
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}  # Resume the same declared dataset without losing earlier rounds.
    if previous and previous.get("provenance") != context["provenance"]:  # Require one immutable physical and executable parent across merged samples.
        raise RuntimeError("Existing manifest has different model or solver provenance; use a new output")  # Avoid silent mixing of incompatible scientific datasets.
    samples = {row["case_id"]: row for row in previous.get("samples", [])}  # Preserve prior completed cases keyed by stable identity.
    for receipt in completed_scenarios(args, context, scenarios):  # Run isolated real solves while keeping all manifest updates in the parent process.
        case_id = receipt["case_id"]  # Recover the completed case independently of process completion order.
        shutil.copytree(Path(receipt["output_directory"]), args.output / "cases" / case_id, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".rsync-tmp"))  # Publish only complete solver evidence; authoritative raw paths remain isolated and immutable.
        if case_id in samples and samples[case_id]["request_fingerprint"] != receipt["request_fingerprint"]:  # Protect existing split and load assignments from mutation.
            raise RuntimeError(f"Manifest identity conflict: {case_id}")  # Reject overwriting another scientific case under the same identifier.
        samples[case_id] = receipt  # Add the finished immutable case to the cumulative dataset.
        rows = [samples[key] for key in sorted(samples)]  # Publish stable deterministic sample order independent of acquisition timing.
        manifest = {"schema": SCHEMA, "bridge_id": "zhaqing-suspension-bridge", "baseline": str(args.base), "equilibrium_state": str(args.calculation / "equilibrium_state.json"), "pipeline_module": str(args.generated / "stress_coordination_pipeline.py"), "adapter_module": str(args.generated / "stress_coordination_condensed_adapter.py"), "nonlinear_module": str(ROOT / "automation/zhaqing_calculix/stress_coordination_nonlinear.py"), "provenance": context["provenance"], "domain": {"q_min": 0.0, "asym_min": 0.0, "q_plus_asym_max": 1.0, "wind_factor": 0.0}, "factor_order": context["provenance"]["factor_order"], "samples": rows, "valid_count": sum(row["quality_status"] == "VALID_CONVERGED" for row in rows), "failed_count": sum(row["quality_status"] != "VALID_CONVERGED" for row in rows), "total_wall_time_s": math.fsum(row["wall_time_s"] for row in rows), "cross_bridge_validation": "NOT_RUN_SINGLE_BRIDGE", "structural_safety_release": "NOT_EVALUATED", "engineering_release": "BLOCKED_G3_G5"}  # Summarize actual coverage and cost without inventing engineering safety claims.
        write_json(manifest_path, manifest)  # Expose each fully completed case atomically for incremental training.
    return 0 if all(samples[item["case_id"]]["quality_status"] == "VALID_CONVERGED" for item in scenarios) else 2  # Make process success depend on all requested numerical qualifications.
if __name__ == "__main__":  # Keep imports free of model execution side effects.
    raise SystemExit(main())  # Propagate the actual requested-scenario qualification status.
