#!/usr/bin/env python3  # Independently audit the published Zhaqing response without changing or re-solving it.
import argparse  # Read explicit immutable input and output paths.
import hashlib  # Bind every audit input to its exact file bytes.
import importlib.util  # Load the existing mechanics implementations without invoking their mains.
import json  # Read existing receipts and write one structured independent audit.
import math  # Compute finite norms and residuals using the existing unit system.
from pathlib import Path  # Keep all file operations explicit and reproducible.
# This audit evaluates the published displacement field directly; it never calls solve_suspension_state.
def digest(path):  # Identify one input without normalizing its bytes.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Return the deterministic SHA-256 identity.
def load_module(path, name):  # Import one already reconstructed source module.
    spec = importlib.util.spec_from_file_location(name, path)  # Resolve the exact caller-specified source.
    module = importlib.util.module_from_spec(spec)  # Allocate a distinct module namespace.
    spec.loader.exec_module(module)  # Execute definitions without running the guarded command entry point.
    return module  # Expose the original audited numerical functions.
def norm(values):  # Compute a Euclidean magnitude for one physical vector.
    return math.sqrt(math.fsum(float(value) ** 2 for value in values))  # Preserve accurate accumulation for small residuals.
def add(target, node, values):  # Assemble one signed action into a stable source-node map.
    target.setdefault(node, [0.0, 0.0, 0.0])  # Initialize a vector only for a physically visited node.
    for axis in range(3):  # Accumulate all three Cartesian components.
        target[node][axis] += float(values[axis])  # Preserve the existing suspension-on-node sign convention.
def write_audit_result(path, result):  # Preserve earlier audit decisions when repaired evidence changes a later disposition.
    payload = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")  # Serialize one deterministic finite review record.
    if path.exists() and path.read_bytes() != payload:  # Keep a prior failed decision rather than erasing its evidence history.
        previous = path.read_bytes()  # Capture exactly the prior immutable audit bytes.
        history = path.with_name(path.stem + ".previous-" + hashlib.sha256(previous).hexdigest()[:12] + path.suffix)  # Give the earlier review a content-addressed sibling filename.
        if not history.exists():  # Reuse an already archived identical decision on repeated verification.
            history.write_bytes(previous)  # Preserve the earlier review before publishing a new result.
    path.write_bytes(payload)  # Install the current result without changing any solver-produced artifact.
def evaluate(args):  # Evaluate source identity, coverage, actual geometry, supports, and reaction evidence.
    pipeline = load_module(args.pipeline, "zhaqing_md_audit_pipeline")  # Load the existing source parser and constants.
    adapter = load_module(args.adapter, "zhaqing_md_audit_adapter")  # Load the original retained-structure adapter.
    nonlinear = load_module(args.nonlinear, "zhaqing_md_audit_nonlinear")  # Load the fixed-L0 constitutive and assembly functions.
    adapter.bind_globals(pipeline)  # Reuse exactly the original mechanical constants and solver-independent utilities.
    base_text = args.base.read_text(encoding="ascii")  # Read the unchanged source finite-element model.
    state = json.loads(args.state.read_text(encoding="utf-8"))  # Read the persisted F3 fabrication state.
    summary = json.loads(args.summary.read_text(encoding="utf-8"))  # Read the original quality decision as evidence rather than truth.
    source_nodes, groups, ownership = pipeline.parse_model(base_text)  # Recover the stable source graph and component families.
    coordinates, element_states, targets = adapter.validate_state_v3(state, args.base, source_nodes, groups)  # Enforce exact topology and constitutive provenance before physics calculations.
    response = adapter.parse_raw_response(args.canonical_dat)  # Read the actual published displacement and mixed-stress field.
    context = nonlinear.build_fixed_l0_context(adapter, base_text, coordinates, groups, element_states)  # Reconstruct the same intact fixed-fabrication suspension context.
    primary_elements = {element_id for group in adapter.PRIMARY_VTK_GROUPS for element_id, connectivity in groups[group]}  # Identify every physical response element independently from the DAT counts.
    primary_nodes = {node for group in adapter.PRIMARY_VTK_GROUPS for element_id, connectivity in groups[group] for node in connectivity}  # Identify every response-bearing physical node independently from source numbering assumptions.
    node_coverage = set(response["displacements"]) == primary_nodes  # Require exact physical nodal output coverage.
    stress_coverage = set(response["stressTokens"]) == primary_elements and all(set(records) == set(range(1, 9)) for records in response["stressTokens"].values())  # Require every source element and every expected published record.
    if not node_coverage or not stress_coverage:  # Do not fabricate missing labels or evaluate an incomplete geometry.
        raise RuntimeError("canonical response lacks exact source-node or element-record coverage")  # Preserve an explicit configuration failure.
    displacements = response["displacements"]  # Keep the published field unchanged throughout the audit.
    current_coordinates = {node: tuple(coordinates[node][axis] + displacements[node][axis] for axis in range(3)) for node in context["suspensionNodes"]}  # Evaluate the actual current geometry directly from the published translations.
    actual_actions = {}  # Assemble exact fixed-L0 element actions and gravity at the published geometry.
    element_responses = {}  # Retain constitutively consistent current member responses for comparisons.
    plane_results = []  # Retain both signed-plane residuals independently.
    for plane in context["planes"]:  # Audit each existing physical suspension plane without solving it.
        actual = nonlinear._assemble_plane_response(context, plane, current_coordinates, assemble_internal_tangent=False)  # Evaluate actual nonlinear actions at the unmodified field.
        actual_actions.update(actual["actionsN"])  # Combine disjoint physical plane actions.
        element_responses.update(actual["elementResponses"])  # Preserve source-indexed current element mechanics.
        worst_node = max(plane["internalNodes"], key=lambda node: norm(actual["actionsN"][node]))  # Identify the worst physical free-node imbalance.
        plane_results.append({"sign": plane["sign"], "maximumInternalResidualN": actual["maximumInternalResidualN"], "worstInternalNodeId": worst_node, "worstInternalResidualVectorN": actual["actionsN"][worst_node], "minimumAxialStressMPa": actual["minimumAxialStressMPa"]})  # Preserve explanatory evidence for each plane.
    linear_actions = {}  # Reconstruct actions belonging to the published F3 tangent approximation.
    material_tangent_discrepancies = []  # Compare the linear adapter tangent with the derivative of the fixed-L0 constitutive law.
    for element_id in sorted(context["activeElementIds"]):  # Visit every actual suspension element once.
        record = context["elementData"][element_id]  # Recover immutable fabricated length, EA, area, and base force.
        node_a, node_b = record["nodeIds"]  # Preserve source orientation for action signs.
        tangent, unit = adapter.suspension_element_tangent(element_id, element_states, coordinates)  # Evaluate the original F3 linearized element operator.
        relative = [displacements[node_b][axis] - displacements[node_a][axis] for axis in range(3)]  # Form the actual relative endpoint displacement.
        increment = [math.fsum(tangent[row][column] * relative[column] for column in range(3)) for row in range(3)]  # Apply the original tangent exactly once.
        force_a = [record["baseForceN"] * unit[axis] + increment[axis] for axis in range(3)]  # Recover the action implicitly represented by the accepted linear label.
        add(linear_actions, node_a, force_a)  # Assemble the endpoint-A tangent action.
        add(linear_actions, node_b, [-value for value in force_a])  # Assemble the equal-and-opposite endpoint-B tangent action.
        gravity = [0.0, 0.0, -0.5 * record["constantSelfWeightN"]]  # Reuse the same frozen gravity convention.
        add(linear_actions, node_a, gravity)  # Add the endpoint-A half weight.
        add(linear_actions, node_b, gravity)  # Add the endpoint-B half weight.
        exact_material = record["axialRigidityN"] / record["unstressedLengthMm"]  # Differentiate the nonlinear force law at the reference geometry.
        published_material = float(element_states[element_id]["materialTangentNPerMm"])  # Read the F3 adapter's EA divided by current length.
        material_tangent_discrepancies.append(abs(exact_material - published_material) / exact_material)  # Quantify their actual relative inconsistency.
    maximum_internal = max(item["maximumInternalResidualN"] for item in plane_results)  # Recover the decisive actual-geometry equilibrium residual.
    maximum_linear_internal = max(norm(linear_actions[node]) for node in context["internalNodes"])  # Independently check the same field against its original linearized mechanics.
    interface_errors = {node: norm([actual_actions[node][axis] - linear_actions[node][axis] for axis in range(3)]) for node in context["interfaceNodes"]}  # Measure the action error the retained model receives when a nonlinear field is interpreted as a tangent label.
    worst_interface = max(interface_errors, key=interface_errors.get)  # Identify the decisive coupling interface.
    minimum_tension = min(item["minimumAxialStressMPa"] for item in plane_results)  # Recover the actual fixed-L0 tension floor.
    anchor_error = max(norm(displacements[node]) for node in context["anchorNodes"])  # Check the exact anchored translations visible in the canonical field.
    support_map = adapter.reaction_collector_contract(base_text)  # Recover intended retained support degrees from the unchanged source model.
    support_rows = [{"nodeId": row["physicalNode"], "dof": row["physicalDof"], "publishedDisplacementMm": displacements[row["physicalNode"]][row["physicalDof"] - 1]} for row in support_map]  # Compare printed physical-source translations with prescribed support degrees.
    maximum_printed_support = max(abs(row["publishedDisplacementMm"]) for row in support_rows)  # Expose possible source-node versus expanded-knot output mismatch.
    reaction_levels = summary.get("reactionAudit", {}).get("levels", [])  # Retain existing two-level audit evidence when this is the canonical linear result.
    reaction_vectors = []  # Independently reconstruct every measured support force, not only their resultant.
    reaction_checks = []  # Track source hashes and exact collector coverage per audited stiffness.
    for level in sorted(reaction_levels, key=lambda row: row["stiffnessNPerMm"]):  # Process both already executed audit levels without launching a solver.
        audit_path = args.summary.parent / ("ZQ_REACTION_AUDIT_" + level["label"] + ".dat")  # Resolve the baseline adapter's deterministic native audit response.
        audit_raw = adapter.parse_raw_response(audit_path)  # Read the unchanged native collector and proxy results.
        expected_collectors = {row["collectorNode"] for row in level["collectorMap"]}  # Identify exact expected sensor records.
        expected_proxies = {row["proxyNode"] for row in level["collectorMap"]}  # Identify exact expected proxy displacement records.
        coverage = set(audit_raw["collectorForces"]) == expected_collectors and set(audit_raw["proxyDisplacements"]) == expected_proxies  # Require complete independent sensor evidence.
        vector = {(row["physicalNode"], row["physicalDof"]): audit_raw["collectorForces"][row["collectorNode"]][0] for row in level["collectorMap"]}  # Map scalar collector readings back to physical source degrees.
        constitutive = max(abs(audit_raw["collectorForces"][row["collectorNode"]][0] + level["stiffnessNPerMm"] * audit_raw["proxyDisplacements"][row["proxyNode"]][0]) / max(abs(audit_raw["collectorForces"][row["collectorNode"]][0]), 1.0) for row in level["collectorMap"])  # Recompute each spring sensor identity independently.
        reaction_vectors.append(vector)  # Preserve individual support forces for a meaningful convergence comparison.
        reaction_checks.append({"label": level["label"], "rawShaMatches": digest(audit_path) == level["rawDatSha256"], "exactCollectorCoverage": coverage, "maximumConstitutiveResidualRelative": constitutive})  # Keep numerical and provenance evidence separate.
    reaction_convergence = None  # Avoid inventing a two-level convergence claim when the necessary files are absent.
    if len(reaction_vectors) == 2 and set(reaction_vectors[0]) == set(reaction_vectors[1]):  # Compare the same complete physical support-degree population.
        keys = sorted(reaction_vectors[0])  # Freeze deterministic degree ordering.
        differences = [reaction_vectors[1][key] - reaction_vectors[0][key] for key in keys]  # Retain cancellation-free individual support differences.
        reaction_convergence = {"individualSupportL2Relative": norm(differences) / max(norm(reaction_vectors[1].values()), 1.0), "maximumIndividualSupportDifferenceN": max(abs(value) for value in differences), "reportedResultantRelative": summary["reactionAudit"]["resultantConvergenceRelative"]}  # Distinguish actual distribution convergence from the weaker global resultant check.
    source_hashes = {"baseline": digest(args.base), "state": digest(args.state), "canonicalDat": digest(args.canonical_dat), "summary": digest(args.summary), "pipeline": digest(args.pipeline), "adapter": digest(args.adapter), "nonlinear": digest(args.nonlinear)}  # Bind the complete audit to reproducible evidence.
    identities_pass = source_hashes["baseline"] == summary["sourceBaselineSha256"] and source_hashes["state"] == summary["equilibriumStateSha256"] and source_hashes["canonicalDat"] == summary["canonicalResponseDatSha256"]  # Independently enforce the original result's parent identities.
    original_pass = summary.get("status") == "PASS" and bool(summary.get("gates")) and all(summary["gates"].values())  # Preserve the exact original acceptance result.
    reaction_pass = len(reaction_checks) == 2 and all(row["rawShaMatches"] and row["exactCollectorCoverage"] and row["maximumConstitutiveResidualRelative"] <= 1.0e-5 for row in reaction_checks)  # Require actual unchanged reaction files and their constitutive consistency.
    nonlinear_internal_pass = maximum_internal <= args.internal_tolerance_n  # Apply the existing fixed-L0 internal Newton tolerance to the actual published field.
    nonlinear_interface_pass = interface_errors[worst_interface] <= args.coupling_tolerance_n  # Apply the existing nonlinear coupling tolerance to actual-versus-applied interface actions.
    source_support_zero = maximum_printed_support <= args.boundary_tolerance_mm  # Report whether printed source translations can directly support zero-boundary training.
    checks = {"sourceIdentityPass": identities_pass, "originalNumericalGatePass": original_pass, "exactNodeCoveragePass": node_coverage, "exactStressCoveragePass": stress_coverage, "independentReactionEvidencePass": reaction_pass, "fixedL0ActualInternalEquilibriumPass": nonlinear_internal_pass, "actualVersusLinearInterfaceActionPass": nonlinear_interface_pass, "actualPositiveTensionPass": minimum_tension >= float(adapter.MIN_TENSION_MPA), "anchorTranslationPass": anchor_error <= args.boundary_tolerance_mm, "printedSourceSupportZeroPass": source_support_zero}  # Publish each criterion separately without an opaque aggregate score.
    eligible = all(checks.values())  # Allow this exact field into the requested nonlinear training path only when every applicable independent check passes.
    failures = sorted(name for name, passed in checks.items() if not passed)  # Preserve decisive failures for a concrete next action.
    disposition = "ELIGIBLE_FOR_SCOPED_SUSPENSION_PHYSICS_TRAINING" if eligible else "QUARANTINED_FOR_NONLINEAR_MODULE_B"  # Avoid interpreting an original linear gate as nonlinear-label validity.
    next_action = "RETRAIN_MODEL" if eligible else "REPAIR_FE_MODEL"  # Feed the observed quality result back into the MD's action vocabulary.
    return {"schema": "zhaqing-md-independent-physics-audit-v1", "status": "PASS" if eligible else "FAIL", "labelDisposition": disposition, "eligibleForModuleB": eligible, "failedChecks": failures, "checks": checks, "sourceSha256": source_hashes, "units": {"length": "mm", "force": "N", "stress": "MPa"}, "method": "Evaluate fixed-L0 nonlinear actions at published coordinates plus published displacements; no equilibrium solve or displacement projection is performed.", "actualGeometryAudit": {"planes": plane_results, "maximumInternalResidualN": maximum_internal, "internalToleranceN": args.internal_tolerance_n, "independentLinearInternalResidualN": maximum_linear_internal, "maximumInterfaceActionMismatchN": interface_errors[worst_interface], "worstInterfaceNodeId": worst_interface, "couplingToleranceN": args.coupling_tolerance_n, "minimumAxialStressMPa": minimum_tension, "maximumMaterialTangentRelativeDifference": max(material_tangent_discrepancies)}, "supportAudit": {"maximumAnchorTranslationMm": anchor_error, "maximumPrintedRetainedSupportTranslationMm": maximum_printed_support, "boundaryToleranceMm": args.boundary_tolerance_mm, "sourceDofRows": support_rows, "interpretation": "Nonzero source-node printed displacement requires verification of CalculiX shell/beam expanded-knot output mapping before imposing this label as a zero-boundary graph target."}, "reactionAudit": {"levels": reaction_checks, "distributionConvergence": reaction_convergence, "originalGlobalForceBalanceRelative": summary.get("globalForceBalanceRelative"), "momentBalanceEvaluated": False}, "scope": {"suspensionConstitutiveAndInternalEquilibriumEvaluated": True, "retainedShellBeamLocalResidualEvaluated": False, "fullBridgeNonlinearCertification": False, "windSystemExcluded": True, "crossBridgeValidationPerformed": False, "stressSemantics": "Canonical DAT retained tensors are total; suspension tensors are current-minus-F3 increments repeated into eight compatibility records. These records are not eight independent axial samples."}, "nextAction": {"type": next_action, "evidence": failures, "recommendedExecution": "Run fixed-L0 coupled re-equilibration for the same unchanged loads and independently review support output mapping before any nonlinear training." if not eligible else "Use the declared suspension-only physical adapter and independently held-out same-bridge cases."}}  # Return a complete evidence-led disposition with explicit untested scope.
def audit_newton_receipt(path, expected_sha, args):  # Verify the last two full Newton closures and their native evidence without solving again.
    receipt = json.loads(path.read_text(encoding="utf-8"))  # Read the completed immutable nonlinear iteration aggregate.
    iterations = receipt.get("iterations", [])  # Preserve the complete recorded sequence before checking its terminal pair.
    stem = path.name.removesuffix(".outer-iterations.json")  # Recover the recorded deterministic native basename.
    checks = {"aggregateShaMatches": digest(path) == expected_sha, "aggregateStatusPass": receipt.get("status") == "PASS", "twoConfirmedClosures": receipt.get("confirmedClosedIterationCount", 0) >= 2 and len(iterations) >= 2, "retainedStructureDeclaredLinear": receipt.get("retainedStructureRemainedLinear") is True, "suspensionRelinearized": receipt.get("suspensionWasRelinearized") is True}  # Separate provenance and actual analysis semantics.
    rows = []  # Record each independently checked final iteration.
    for iteration in iterations[-2:]:  # Require both final iterations to close under an undamped full Newton step.
        prefix = path.parent / f"{stem}_NL_{int(iteration['outerIteration']):02d}"  # Resolve native evidence from the original iteration number.
        iteration_path = prefix.with_suffix(".iteration.json")  # Locate the separately persisted source iteration receipt.
        native_dat = prefix.with_suffix(".dat")  # Locate the exact native response used for this Newton step.
        native_deck = prefix.with_suffix(".inp")  # Locate the matching current-tangent input deck.
        persisted = json.loads(iteration_path.read_text(encoding="utf-8"))  # Read the independently saved iteration values.
        same_payload = persisted == {key: value for key, value in iteration.items() if key != "receiptSha256"}  # Reject aggregate metrics that differ from their signed source receipt.
        row_checks = {"iterationShaMatches": digest(iteration_path) == iteration["receiptSha256"], "iterationPayloadMatches": same_payload, "deckShaMatches": digest(native_deck) == iteration["deckSha256"], "rawDatShaMatches": digest(native_dat) == iteration["rawDatSha256"], "statusClosed": iteration.get("status") == "CLOSED", "fullStep": iteration.get("acceptedOuterStepScale") == 1.0, "solverExitZero": iteration.get("solverExitCode") == 0, "fatalDiagnosticsAbsent": iteration.get("fatalDiagnostics") == [], "couplingPass": float(iteration["maximumPhysicalCouplingResidualN"]) <= min(float(iteration["couplingResidualToleranceN"]), args.coupling_tolerance_n), "internalPass": float(iteration["maximumInternalResidualN"]) <= min(float(iteration["internalResidualToleranceN"]), args.internal_tolerance_n), "correctionPass": float(iteration["maximumAcceptedInterfaceCorrectionMm"]) <= float(iteration["interfaceCorrectionToleranceMm"])}  # Verify native files and each decisive nonlinear convergence quantity.
        rows.append({"outerIteration": iteration["outerIteration"], "checks": row_checks, "couplingResidualN": iteration["maximumPhysicalCouplingResidualN"], "internalResidualN": iteration["maximumInternalResidualN"], "interfaceCorrectionMm": iteration["maximumAcceptedInterfaceCorrectionMm"], "nativeDat": str(native_dat), "nativeDeck": str(native_deck)})  # Preserve actionable verification evidence.
    checks["bothLastIterationsPass"] = len(rows) == 2 and all(all(row["checks"].values()) for row in rows)  # Require the complete two-iteration evidence rather than a declared terminal status alone.
    terminal_dat = Path(rows[-1]["nativeDat"]) if rows else None  # Expose the verified terminal native field for token comparisons.
    checks["terminalDigestMatches"] = terminal_dat is not None and digest(terminal_dat) == receipt.get("terminalRawDatSha256") and digest(Path(rows[-1]["nativeDeck"])) == receipt.get("terminalDeckSha256")  # Bind the aggregate terminal fields to actual final files.
    return {"path": str(path), "sha256": digest(path), "checks": checks, "passed": all(checks.values()), "finalIterations": rows, "terminalDat": str(terminal_dat) if terminal_dat else None}  # Return the exact closure decision and its supporting evidence.
def evaluate_fixed_l0(args):  # Audit a genuine nonlinear label without requiring equality to the obsolete F3 tangent action.
    pipeline = load_module(args.pipeline, "zhaqing_md_fixed_pipeline")  # Load the unchanged physical source parser and constants.
    adapter = load_module(args.adapter, "zhaqing_md_fixed_adapter")  # Load the original response and support interpretation.
    nonlinear = load_module(args.nonlinear, "zhaqing_md_fixed_nonlinear")  # Load the same fixed-L0 constitutive and assembly routines.
    adapter.bind_globals(pipeline)  # Reuse the original model's exact properties and units.
    text = args.base.read_text(encoding="ascii")  # Read the immutable baseline deck.
    state = json.loads(args.state.read_text(encoding="utf-8"))  # Read the original frozen F3 state.
    summary = json.loads(args.summary.read_text(encoding="utf-8"))  # Read the existing nonlinear final gate and source lineage.
    case_id = summary.get("case_id", summary.get("caseId"))  # Preserve the runner or original API case identifier.
    source_nodes, groups, ownership = pipeline.parse_model(text)  # Recover all actual source nodes and component incidence.
    coordinates, element_states, targets = adapter.validate_state_v3(state, args.base, source_nodes, groups)  # Verify the same source graph and fixed fabrication contract.
    context = nonlinear.build_fixed_l0_context(adapter, text, coordinates, groups, element_states)  # Construct an intact suspension context without performing an equilibrium solve.
    response = adapter.parse_raw_response(args.canonical_dat)  # Read the published physical label without replacing any value.
    nodes = {node for group in adapter.PRIMARY_VTK_GROUPS for element_id, connectivity in groups[group] for node in connectivity}  # Independently derive exact primary nodal coverage.
    elements = {element_id for group in adapter.PRIMARY_VTK_GROUPS for element_id, connectivity in groups[group]}  # Independently derive exact primary element coverage.
    node_coverage = set(response["displacements"]) == nodes  # Reject missing, extra, or renumbered nodal labels.
    stress_coverage = set(response["stressTokens"]) == elements and all(set(records) == set(range(1, 9)) for records in response["stressTokens"].values())  # Reject incomplete source-element records.
    if not node_coverage or not stress_coverage:  # Prevent a partial geometry from entering actual residual evaluation.
        raise RuntimeError("nonlinear canonical response does not cover the exact primary source graph")  # Preserve missing data as an audit error.
    displacements = response["displacements"]  # Freeze the actual already published label field.
    current = {node: tuple(coordinates[node][axis] + displacements[node][axis] for axis in range(3)) for node in context["suspensionNodes"]}  # Build current coordinates from the original geometry plus this exact field.
    planes = []  # Preserve both actual-geometry residual populations.
    current_elements = {}  # Collect independently recomputed nonlinear member stresses.
    for plane in context["planes"]:  # Visit both physical signed planes without seeking a better solution.
        actual = nonlinear._assemble_plane_response(context, plane, current, assemble_internal_tangent=False)  # Evaluate true fixed-L0 actions directly at published coordinates.
        worst = max(plane["internalNodes"], key=lambda node: norm(actual["actionsN"][node]))  # Identify the decisive physical free node.
        planes.append({"sign": plane["sign"], "maximumInternalResidualN": actual["maximumInternalResidualN"], "worstInternalNodeId": worst, "worstResidualVectorN": actual["actionsN"][worst], "minimumAxialStressMPa": actual["minimumAxialStressMPa"]})  # Publish numerical residuals with source locations.
        current_elements.update(actual["elementResponses"])  # Preserve actual member values for an independent label consistency check.
    maximum_internal = max(row["maximumInternalResidualN"] for row in planes)  # Recover the true worst internal imbalance.
    minimum_tension = min(row["minimumAxialStressMPa"] for row in planes)  # Recover the actual positive-tension margin.
    stress_error = 0.0  # Compare total current member stress with the canonical current-minus-F3 convention.
    for element_id, actual in current_elements.items():  # Visit each real axial member once regardless of the eight compatibility records.
        base_tensor = context["elementData"][element_id]["baseTensorMPa"]  # Recover the exact original F3 tensor.
        increment = adapter.average_stress_records(response["stressTokens"][element_id])  # Read the canonical analytical increment without treating repeats as independent samples.
        stress_error = max(stress_error, max(abs(float(actual["totalTensorMPa"][axis]) - base_tensor[axis] - increment[axis]) for axis in range(6)))  # Test constitutive label consistency in the declared global tensor convention.
    main_receipt = args.summary.parent / f"ZQ_{case_id}.outer-iterations.json"  # Resolve the complete direct-support Newton history.
    newton = audit_newton_receipt(main_receipt, summary["nonlinearIterationReceiptSha256"], args)  # Verify the last two actual full Newton closures and their hashes.
    native = adapter.parse_raw_response(Path(newton["terminalDat"]))  # Read the exact native retained field at the verified terminal iteration.
    retained = context["retainedNodes"]  # Identify physical retained nodes independently from canonical coverage.
    native_identity = set(native["displacements"]) == retained and all(response["displacementTokens"][node] == token for node, token in native["displacementTokens"].items()) and all(response["stressTokens"][element] == records for element, records in native["stressTokens"].items())  # Require verbatim native U/S labels for every retained source result.
    reaction_checks = []  # Preserve independent native verification of both original sensor-supported limits.
    reaction_vectors = []  # Compare individual retained support reactions without cancellation.
    levels = summary.get("reactionAudit", {}).get("levels", [])  # Read only the original two-level reaction receipts.
    for level in sorted(levels, key=lambda row: row["stiffnessNPerMm"]):  # Verify both prescribed original stiffness levels in deterministic order.
        reaction_root = args.summary.parent / ("reaction-" + level["label"])  # Resolve this physically separate support approximation.
        iteration_path = reaction_root / f"ZQ_{case_id}_{level['label']}.outer-iterations.json"  # Locate its own nonlinear convergence evidence.
        closure = audit_newton_receipt(iteration_path, level["nonlinearIterationReceiptSha256"], args)  # Require two full Newton closures for each support-supported audit.
        raw_path = Path(closure["terminalDat"])  # Recover the exact terminal sensor output from verified evidence.
        raw = adapter.parse_raw_response(raw_path)  # Parse actual proxy displacements and load-free collector forces.
        mapping = level["collectorMap"]  # Preserve the declared source-node and Cartesian-degree correspondence.
        collector_coverage = set(raw["collectorForces"]) == {row["collectorNode"] for row in mapping} and set(raw["proxyDisplacements"]) == {row["proxyNode"] for row in mapping}  # Require complete sensor and proxy coverage independently.
        if not collector_coverage:  # Preserve precise missing-native-evidence diagnostics without an opaque dictionary lookup failure.
            reaction_checks.append({"label": level["label"], "stiffnessNPerMm": level["stiffnessNPerMm"], "newton": closure, "passed": False, "collectorCoveragePass": False, "missingCollectorNodeIds": sorted({row["collectorNode"] for row in mapping} - set(raw["collectorForces"])), "missingProxyNodeIds": sorted({row["proxyNode"] for row in mapping} - set(raw["proxyDisplacements"])), "nativeDat": str(raw_path), "nativeDatBytes": raw_path.stat().st_size, "actualScalarSupportExtensionMm": None})  # Keep truncated raw files isolated even when the producer previously passed.
            continue  # Avoid inventing missing scalar support forces or extensions.
        residual = max(abs(raw["collectorForces"][row["collectorNode"]][0] + float(level["stiffnessNPerMm"]) * raw["proxyDisplacements"][row["proxyNode"]][0]) / max(abs(raw["collectorForces"][row["collectorNode"]][0]), 1.0) for row in mapping)  # Recompute the actual sensor constitutive identity.
        extension = max(abs(raw["proxyDisplacements"][row["proxyNode"]][0]) for row in mapping)  # Evaluate the true scalar support extension rather than expanded-knot output.
        vector = {(row["physicalNode"], row["physicalDof"]): raw["collectorForces"][row["collectorNode"]][0] for row in mapping}  # Restore all measured support-force components under physical source identities.
        reaction_vectors.append(vector)  # Preserve actual reaction distributions for a stronger convergence diagnostic.
        hashes_pass = digest(raw_path) == level["rawDatSha256"] and digest(raw_path.with_suffix(".inp")) == level["deckSha256"] and digest(raw_path.with_suffix(".stdout.log")) == level["stdoutSha256"]  # Bind sensor values to original deck, response, and log evidence.
        reaction_checks.append({"label": level["label"], "stiffnessNPerMm": level["stiffnessNPerMm"], "newton": closure, "hashesPass": hashes_pass, "collectorCoveragePass": collector_coverage, "sensorConstitutiveResidualRelative": residual, "actualScalarSupportExtensionMm": extension, "sourceKnotDisplacementIsRejectionCriterion": False, "passed": closure["passed"] and hashes_pass and collector_coverage and residual <= 1.0e-5 and level.get("collectorsLoadFreePass") is True})  # Keep knot diagnostics separate from physical scalar support qualification.
    reaction_pass = len(reaction_checks) == 2 and sorted(float(row["stiffnessNPerMm"]) for row in reaction_checks) == [1.0e9, 1.0e10] and all(row["passed"] for row in reaction_checks) and reaction_checks[-1]["actualScalarSupportExtensionMm"] <= float(adapter.REACTION_AUDIT_SUPPORT_TRANSLATION_TOL_MM)  # Enforce both exact frozen stiffnesses and the original selected-support approximation bound.
    reaction_distribution = None  # Keep unsupported convergence quantities absent when records are incomplete.
    if len(reaction_vectors) == 2 and set(reaction_vectors[0]) == set(reaction_vectors[1]):  # Compare the same measured physical support population.
        differences = [reaction_vectors[1][key] - reaction_vectors[0][key] for key in sorted(reaction_vectors[0])]  # Prevent cancellation of opposite support errors.
        reaction_distribution = norm(differences) / max(norm(reaction_vectors[1].values()), 1.0)  # Report the actual support distribution's relative change.
    source_sha = {"baseline": digest(args.base), "state": digest(args.state), "canonicalDat": digest(args.canonical_dat), "summary": digest(args.summary), "pipeline": digest(args.pipeline), "adapter": digest(args.adapter), "nonlinear": digest(args.nonlinear)}  # Bind the completed audit to its exact model and implementation.
    parent = summary.get("parent_evidence", summary.get("parentEvidence", {}))  # Support both the learning runner and the original case executor's lineage spelling.
    parent_base_sha = summary.get("sourceBaselineSha256", parent.get("baseSha256"))  # Resolve the original baseline identity without guessing.
    parent_state_sha = summary.get("equilibriumStateSha256", parent.get("equilibriumStateSha256"))  # Resolve the frozen fabricated-state identity.
    identities = source_sha["baseline"] == parent_base_sha and source_sha["state"] == parent_state_sha and source_sha["canonicalDat"] == summary["canonicalResponseDatSha256"]  # Require the same baseline, F3 state, and generated label claimed by the source receipt.
    original_pass = summary.get("status") == "PASS" and bool(summary.get("gates")) and all(summary["gates"].values())  # Recheck all original numerical gates without weakening any threshold.
    anchor_error = max(norm(displacements[node]) for node in context["anchorNodes"])  # Retain the exact prescribed-anchor check on actual physical suspension nodes.
    support_map = adapter.reaction_collector_contract(text)  # Recover the intended retained support degrees.
    printed_support = max(abs(displacements[row["physicalNode"]][row["physicalDof"] - 1]) for row in support_map)  # Record source/knot output movement purely as a representation diagnostic.
    checks = {"sourceIdentityPass": identities, "originalNumericalGatePass": original_pass, "exactNodeCoveragePass": node_coverage, "exactStressCoveragePass": stress_coverage, "nativeRetainedTokenIdentityPass": native_identity, "fixedL0ActualInternalEquilibriumPass": maximum_internal <= args.internal_tolerance_n, "fixedL0ConstitutiveStressLabelPass": stress_error <= args.stress_tolerance_mpa, "actualPositiveTensionPass": minimum_tension >= float(adapter.MIN_TENSION_MPA), "anchorTranslationPass": anchor_error <= args.boundary_tolerance_mm, "twoFullNewtonClosuresPass": newton["passed"], "independentReactionEvidencePass": reaction_pass}  # Decide only from applicable actual nonlinear mechanics and independently verified source evidence.
    eligible = all(checks.values())  # Admit a label only after every declared nonlinear quality criterion passes.
    failures = sorted(name for name, passed in checks.items() if not passed)  # Preserve exact rejection reasons for module C.
    return {"schema": "zhaqing-md-independent-physics-audit-v2", "analysisMode": "fixed-l0", "caseId": case_id, "status": "PASS" if eligible else "FAIL", "eligibleForModuleB": eligible, "labelEligible": eligible, "labelDisposition": "ELIGIBLE_FOR_SCOPED_SUSPENSION_PHYSICS_TRAINING" if eligible else "QUARANTINED_FOR_NONLINEAR_MODULE_B", "checks": checks, "failedChecks": failures, "sourceSha256": source_sha, "method": "Evaluate fixed-L0 forces at published actual coordinates without any solve; verify two terminal full Newton closures from independently hashed source iterations.", "actualGeometryAudit": {"planes": planes, "maximumInternalResidualN": maximum_internal, "internalToleranceN": args.internal_tolerance_n, "maximumConstitutiveStressErrorMPa": stress_error, "constitutiveStressToleranceMPa": args.stress_tolerance_mpa, "minimumAxialStressMPa": minimum_tension, "comparisonToOriginalLinearTangentRequired": False}, "newtonAudit": newton, "reactionAudit": {"levels": reaction_checks, "individualSupportDistributionL2Relative": reaction_distribution}, "supportAudit": {"maximumAnchorTranslationMm": anchor_error, "maximumPrintedSourceSupportTranslationMm": printed_support, "printedSourceSupportTranslationIsRejectionCriterion": False, "physicalSupportEvidence": "Prescribed anchors and verified scalar proxy/collector support audit; source beam/shell knot output is kept separately."}, "scope": {"retainedStructureLinear": True, "suspensionGeometryNonlinear": True, "suspensionPhysicalResidualEvaluated": True, "retainedShellBeamLocalResidualEvaluated": False, "windSystemExcluded": True, "crossBridgeValidationPerformed": False}, "nextAction": {"type": "RETRAIN_MODEL" if eligible else "REPAIR_FE_MODEL", "evidence": failures}}  # Return a concrete eligible label decision while retaining the actual model's scope.
def evaluate_manifest(args):  # Create an audited snapshot without racing the numerical runner's live manifest writer.
    manifest_payload = args.manifest.read_bytes()  # Read one complete atomically published source dataset exactly once.
    manifest = json.loads(manifest_payload.decode("utf-8"))  # Parse the captured snapshot independently from later live updates.
    source_manifest_sha = hashlib.sha256(manifest_payload).hexdigest()  # Hash the same captured bytes rather than a potentially newer live manifest.
    expected = None  # Keep the original frozen evaluation denominator explicit when supplied.
    if args.expected_scenarios is not None:  # Read the precommitted scenario design before selecting accepted labels.
        design = json.loads(args.expected_scenarios.read_text(encoding="utf-8"))  # Recover original case identities, factor assignments, and split roles.
        expected = design["scenarios"] if isinstance(design, dict) else design  # Support the existing design wrapper without renaming cases.
        expected_map = {row["case_id"]: row for row in expected}  # Preserve the exact frozen source identity for every requested case.
        if len(expected_map) != len(expected):  # Reject a design whose duplicate identities would hide missing evidence.
            raise RuntimeError("frozen scenario design contains duplicate case ids")  # Preserve a well-defined original evaluation population.
        for sample in manifest["samples"]:  # Verify that runtime samples have not silently changed the original scientific design.
            if sample["case_id"] not in expected_map or sample["split"] != expected_map[sample["case_id"]]["split"] or sample["factors"] != expected_map[sample["case_id"]]["factors"]:  # Require exact case, split, and load-factor identity.
                raise RuntimeError("runtime sample differs from frozen scenario design: " + sample["case_id"])  # Reject hidden case replacement or test-to-training reassignment.
        manifest["expected_split_counts"] = {split: sum(row["split"] == split for row in expected) for split in ("train", "validation", "test")}  # Preserve the complete original split denominators even when some solves fail.
        manifest["expected_split_case_ids"] = {split: [row["case_id"] for row in expected if row["split"] == split] for split in ("train", "validation", "test")}  # Preserve every omitted case's original role explicitly.
        manifest["frozen_scenario_design"] = {"path": str(args.expected_scenarios.resolve()), "sha256": digest(args.expected_scenarios)}  # Bind denominator and split claims to the original design file.
    basis_names = ("LC02_G_Q_SERVICE", "LC03_G_Q_ASYM_SERVICE")  # Preserve the two original nodal-load source directions used by this learning run.
    basis_files = [Path(manifest["baseline"]).parent / "recovered_cases" / "flat" / (name + ".inp") for name in basis_names]  # Resolve the known recovered source files next to the immutable project inputs.
    if all(path.is_file() for path in basis_files):  # Publish spatial-load encodings only when the complete original inputs are present.
        if any(digest(path) != manifest["provenance"]["source_load_sha256"][name] for path, name in zip(basis_files, basis_names)):  # Bind each spatial force basis to the same source bytes used by the numerical generator.
            raise RuntimeError("original spatial load-basis source identity changed")  # Reject a graph input that differs from the solved load basis.
        manifest["load_basis_files"] = [str(basis_files[0].resolve()), None, str(basis_files[1].resolve())]  # Preserve the agreed uniform-wind-asymmetric factor order with no invented wind pattern.
    rows = []  # Preserve the requested dataset ordering and split membership.
    audits = []  # Summarize actual independent qualification rather than original success counts alone.
    for sample in manifest["samples"]:  # Audit each available physical reference exactly once.
        row = dict(sample)  # Leave the runner's in-memory and on-disk row unchanged.
        if row.get("quality_status", row.get("quality_flag")) != "VALID_CONVERGED" or not row.get("canonical_dat"):  # Preserve failed or interrupted solver samples without inventing reference fields.
            row.update({"eligible_for_training": False, "reference_label_available": False, "independent_audit_status": "NOT_APPLICABLE_NO_VALID_REFERENCE"})  # Explicitly exclude missing numerical labels.
            rows.append(row)  # Keep failures visible in the complete dataset ledger.
            continue  # Advance without treating an unsolved response as an audit success.
        audit_path = Path(row["canonical_dat"]).parent / "independent-physics-audit.json"  # Save a distinct review result beside this case's original evidence.
        case_args = argparse.Namespace(base=Path(manifest["baseline"]), state=Path(manifest["equilibrium_state"]), canonical_dat=Path(row["canonical_dat"]), summary=Path(row["summary"]), pipeline=Path(manifest["pipeline_module"]), adapter=Path(manifest["adapter_module"]), nonlinear=Path(manifest["nonlinear_module"]), internal_tolerance_n=args.internal_tolerance_n, coupling_tolerance_n=args.coupling_tolerance_n, boundary_tolerance_mm=args.boundary_tolerance_mm, stress_tolerance_mpa=args.stress_tolerance_mpa)  # Reuse only source-declared paths and the explicit audit controls.
        try:  # Preserve a per-case audit error without hiding other independently available evidence.
            result = evaluate_fixed_l0(case_args)  # Evaluate the actual solved nonlinear label.
        except Exception as error:  # Reject unavailable or inconsistent evidence without fabricating residuals.
            result = {"schema": "zhaqing-md-independent-physics-audit-v2", "status": "ERROR", "eligibleForModuleB": False, "labelEligible": False, "errorType": type(error).__name__, "error": str(error)}  # Keep audit execution error distinct from failed physical equilibrium.
        write_audit_result(audit_path, result)  # Publish independent evidence while preserving earlier decisions after an exact native-file repair.
        admitted = result.get("eligibleForModuleB") is True  # Treat an explicit positive independent decision as the only admission route.
        row.update({"audit_path": str(audit_path.resolve()), "audit_sha256": digest(audit_path), "independent_audit_status": result["status"], "eligible_for_training": admitted and row["split"] == "train", "reference_label_available": admitted})  # Attach audit identity while preserving original numerical status separately.
        rows.append(row)  # Preserve this immutable case and split in the audited snapshot.
        audits.append({"case_id": row["case_id"], "status": result["status"], "eligibleForModuleB": admitted, "audit_path": row["audit_path"], "maximumInternalResidualN": result.get("actualGeometryAudit", {}).get("maximumInternalResidualN"), "failedChecks": result.get("failedChecks", []), "error": result.get("error")})  # Keep a concise evidence-led batch summary.
    manifest.update({"samples": rows, "independent_audit": {"source_manifest": str(args.manifest.resolve()), "source_manifest_sha256": source_manifest_sha, "audit_script_sha256": digest(Path(__file__)), "eligible_reference_count": sum(row.get("reference_label_available") is True for row in rows), "audited_case_count": len(audits)}, "eligible_reference_count": sum(row.get("reference_label_available") is True for row in rows)})  # Add independent quality metadata without redefining original solver counts.
    args.audited_manifest.parent.mkdir(parents=True, exist_ok=True)  # Create only the requested snapshot destination.
    args.audited_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Publish a separate snapshot for module B instead of modifying the live runner manifest.
    accepted_info = None  # Describe an optional explicitly filtered training manifest separately from the complete audited ledger.
    if args.accepted_manifest is not None:  # Build the authorized accepted-only view while retaining every excluded case and reason.
        accepted_rows = [row for row in rows if row.get("reference_label_available") is True and row.get("independent_audit_status") == "PASS"]  # Admit only genuine independently verified numerical references.
        accepted_ids = {row["case_id"] for row in accepted_rows}  # Preserve exact accepted identities without altering split membership.
        audit_index = {row["case_id"]: row for row in audits}  # Recover explanatory physical or source-evidence rejection details.
        excluded = [{"case_id": row["case_id"], "split": row["split"], "quality_status": row.get("quality_status", row.get("quality_flag")), "audit_path": row.get("audit_path"), "reason": audit_index[row["case_id"]].get("error") or audit_index[row["case_id"]].get("failedChecks") if row["case_id"] in audit_index else row.get("error") or "NO_VALID_NUMERICAL_REFERENCE", "original_summary": row.get("summary"), "original_canonical_dat": row.get("canonical_dat"), "structural_failure_label": row.get("structural_failure_label")} for row in rows if row["case_id"] not in accepted_ids]  # Keep original numeric status, split, and files for every excluded completed attempt.
        seen = {row["case_id"] for row in rows}  # Distinguish never-finished design cases from completed rejected attempts.
        excluded.extend({"case_id": row["case_id"], "split": row["split"], "quality_status": "NOT_COMPLETED", "audit_path": None, "reason": "No completed source manifest row exists for this frozen case.", "structural_failure_label": None} for row in expected if row["case_id"] not in seen)  # Keep missing validation or test cases visible in the fixed denominator.
        accepted = dict(manifest)  # Preserve model, source, load basis, and expected evaluation population.
        accepted.update({"samples": accepted_rows, "excluded_samples": excluded, "accepted_count": len(accepted_rows), "excluded_count": len(excluded), "accepted_split_counts": {split: sum(row["split"] == split for row in accepted_rows) for split in ("train", "validation", "test")}, "excluded_split_counts": {split: sum(row["split"] == split for row in excluded) for split in ("train", "validation", "test")}, "source_audited_manifest": str(args.audited_manifest.resolve()), "source_audited_manifest_sha256": digest(args.audited_manifest), "selection_policy": "Only independently accepted reference labels are exposed; all original failures and missing split assignments remain in excluded_samples and expected_split_counts."})  # Define an explicit admission view without rewriting original truth labels.
        args.accepted_manifest.parent.mkdir(parents=True, exist_ok=True)  # Create only the authorized accepted-view destination.
        args.accepted_manifest.write_text(json.dumps(accepted, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Publish the separate downstream manifest after the complete review ledger is saved.
        accepted_info = {"path": str(args.accepted_manifest.resolve()), "sha256": digest(args.accepted_manifest), "acceptedCount": len(accepted_rows), "excludedCount": len(excluded), "expectedSplitCounts": accepted["expected_split_counts"], "acceptedSplitCounts": accepted["accepted_split_counts"], "excludedSplitCounts": accepted["excluded_split_counts"]}  # Report exact scientific coverage rather than treating rejection as disappearance.
    passed = bool(audits) and all(row["eligibleForModuleB"] for row in audits)  # Refuse to claim a successful audit for an empty or rejected reference collection.
    return {"schema": "zhaqing-md-independent-audit-batch-v1", "status": "PASS" if passed else "FAIL", "eligibleForModuleB": passed, "auditedManifest": str(args.audited_manifest.resolve()), "auditedManifestSha256": digest(args.audited_manifest), "acceptedManifest": accepted_info, "caseCount": len(rows), "auditedCount": len(audits), "eligibleReferenceCount": sum(row["eligibleForModuleB"] for row in audits), "cases": audits}  # Return a transparent complete dataset qualification summary and any explicitly filtered view.
def main():  # Expose a reproducible audit command that fails closed.
    parser = argparse.ArgumentParser(description="Independently audit a Zhaqing canonical baseline response at its published geometry.")  # Describe the command's deliberately solver-free behavior.
    for flag in ("base", "state", "canonical-dat", "summary", "pipeline", "adapter", "nonlinear", "output"):  # Require all source and evidence paths explicitly.
        parser.add_argument("--" + flag, type=Path, required=flag == "output")  # Require individual paths only after selecting single-case versus manifest mode.
    parser.add_argument("--analysis-mode", choices=("linear-tangent", "fixed-l0"), default="linear-tangent")  # Preserve the original baseline audit while adding a genuine nonlinear-label path.
    parser.add_argument("--manifest", type=Path)  # Optionally inspect an atomically published live dataset snapshot.
    parser.add_argument("--audited-manifest", type=Path)  # Require a distinct output manifest when auditing a dataset.
    parser.add_argument("--accepted-manifest", type=Path)  # Optionally publish only independently admissible references while preserving excluded cases.
    parser.add_argument("--expected-scenarios", type=Path)  # Bind original sample counts and split membership to a frozen scenario-design file.
    parser.add_argument("--internal-tolerance-n", type=float, default=1.0e-4)  # Match the existing fixed-L0 internal convergence requirement.
    parser.add_argument("--coupling-tolerance-n", type=float, default=1.0e-2)  # Match the existing fixed-L0 interface convergence requirement.
    parser.add_argument("--boundary-tolerance-mm", type=float, default=1.0e-6)  # Use an explicit tight translation check and disclose its output-mapping caveat.
    parser.add_argument("--stress-tolerance-mpa", type=float, default=1.0e-5)  # Set an explicit fixed-L0 tensor consistency tolerance above the analytic serializer's roundoff.
    args = parser.parse_args()  # Resolve paths and audit controls once.
    if args.manifest and (args.audited_manifest is None or args.manifest.resolve() == args.audited_manifest.resolve()):  # Protect the numerical runner's live dataset identity and concurrent writes.
        parser.error("--manifest requires a distinct --audited-manifest output")  # Require an independently reviewable dataset snapshot.
    if args.accepted_manifest is not None and (args.manifest is None or args.expected_scenarios is None or args.accepted_manifest.resolve() in {args.manifest.resolve(), args.audited_manifest.resolve()}):  # Require a complete frozen denominator and a separate destination for any filtered admission view.
        parser.error("--accepted-manifest requires --manifest, --expected-scenarios, and a distinct output path")  # Prevent silent replacement of the original or complete audited dataset.
    if not args.manifest and any(getattr(args, name) is None for name in ("base", "state", "canonical_dat", "summary", "pipeline", "adapter", "nonlinear")):  # Require every immutable dependency for a single-case audit.
        parser.error("single-case mode requires --base --state --canonical-dat --summary --pipeline --adapter --nonlinear")  # Stop before resolving missing inputs implicitly.
    try:  # Preserve machine-readable evidence even when an input contract cannot be evaluated.
        result = evaluate_manifest(args) if args.manifest else (evaluate_fixed_l0(args) if args.analysis_mode == "fixed-l0" else evaluate(args))  # Route explicit nonlinear and original tangent contracts separately.
    except Exception as error:  # Classify missing or incompatible evidence without inventing numerical quantities.
        result = {"schema": "zhaqing-md-independent-physics-audit-v1", "status": "ERROR", "eligibleForModuleB": False, "labelDisposition": "QUARANTINED_INCOMPLETE_AUDIT", "errorType": type(error).__name__, "error": str(error), "nextAction": {"type": "REPAIR_FE_MODEL"}}  # Keep configuration failure distinct from physical non-equilibrium.
    args.output.parent.mkdir(parents=True, exist_ok=True)  # Create only the requested audit destination directory.
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Persist finite auditable JSON without modifying original results.
    print(json.dumps({"status": result["status"], "eligibleForModuleB": result["eligibleForModuleB"], "output": str(args.output), "failedChecks": result.get("failedChecks", []), "error": result.get("error")}, ensure_ascii=False))  # Emit a concise terminal summary.
    return 0 if result["status"] == "PASS" else (2 if result["status"] == "FAIL" else 3)  # Return distinct pass, physical-quality failure, and audit-error statuses.
if __name__ == "__main__":  # Execute only for an explicit command invocation.
    raise SystemExit(main())  # Propagate the actual quality decision to orchestration.
