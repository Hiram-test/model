#!/usr/bin/env python3  # Build a two-step equilibrium path that first balances native cable prestress and then transfers smoothly to the verified permanent loads.
import argparse  # Parse deterministic baseline, output and CalculiX executable paths.
import csv  # Persist a compact scalar comparison table for all prestress scales.
import json  # Persist the complete force construction, balancing-load audit and selection receipt.
import math  # Evaluate line-element direction cosines and completed-geometry RMS metrics.
import shutil  # Package the objectively selected converged research-baseline model and solver outputs.
from pathlib import Path  # Use explicit filesystem paths for every generated numerical artifact.
import initial_stress_prestress as direct  # Reuse the audited native-stress tensor conversion and nonlinear result-selection loop concepts.
import elementwise_prestress as forces  # Reuse the mechanics-derived segment-wise main-cable and hanger target-force construction.
import prestress_isolation as core  # Reuse the verified-L2 parser and CalculiX result parser.

SCALES = (0.90, 1.00, 1.10, 1.18, 1.25)  # Probe a bounded family around the mechanics-derived and residual-minimum prestress levels.
MAIN_CABLE_AREA_MM2 = forces.MAIN_AREA_MM2  # Preserve exactly the axial area of the original equal-area PR9 B31 main-cable section.
CONSTRAINED_SET_DOFS = {"TOWER_BASES": (1, 2, 3), "MAIN_CABLE_ANCHORS": (1, 2, 3), "WIND_ANCHORS": (1, 2, 3), "DECK_LEFT_PIN": (1, 2, 3), "DECK_RIGHT_ROLLER": (2, 3)}  # Freeze the verified PR9 translational constraints relevant to balancing point loads.


def parse_nsets(text: str) -> dict[str, set[int]]:  # Parse explicit node sets needed to exclude constrained translational degrees of freedom from artificial balancing loads.
    sets: dict[str, set[int]] = {}  # Store every explicit NSET by normalized uppercase name.
    active: str | None = None  # Track the current node-set keyword while scanning the verified input deck.
    for raw in text.splitlines():  # Visit the input deck once in source order.
        line = raw.strip()  # Normalize surrounding whitespace without altering numeric tokens.
        if line.upper().startswith("*NSET"):  # Detect a node-set definition keyword.
            name = None  # Initialize the extracted set name defensively.
            for field in line.split(",")[1:]:  # Inspect optional keyword parameters after *NSET.
                if "=" in field and field.split("=", 1)[0].strip().upper() == "NSET":  # Select the NSET=name parameter only.
                    name = field.split("=", 1)[1].strip().upper()  # Normalize the node-set name for deterministic lookup.
            active = name  # Enter explicit node-set data mode when a name was found.
            if active:  # Initialize storage only for a valid named set.
                sets.setdefault(active, set())  # Preserve existing entries if the set is continued in a later block.
            continue  # Advance to node labels under the set keyword.
        if line.startswith("*"):  # Detect every other keyword boundary.
            active = None  # Leave node-set parsing mode at the next keyword.
            continue  # Advance to data associated with the new keyword.
        if active and line and not line.startswith("**"):  # Parse explicit comma-separated node labels inside an active node set.
            for token in line.split(","):  # Visit every comma-separated node token on this row.
                token = token.strip()  # Remove surrounding whitespace from the candidate node label.
                if token.isdigit():  # Keep only explicit integer node labels used by this verified baseline.
                    sets[active].add(int(token))  # Add the original node label to the normalized node set.
    return sets  # Return all parsed explicit node sets for constraint lookup and auditing.


def constrained_dofs(text: str) -> set[tuple[int, int]]:  # Build the exact original translational degree-of-freedom set that cannot receive balancing CLOAD entries.
    nsets = parse_nsets(text)  # Recover the verified named support node sets from the baseline deck.
    constrained: set[tuple[int, int]] = set()  # Store each constrained original node and translational direction pair.
    for set_name, dofs in CONSTRAINED_SET_DOFS.items():  # Apply the frozen verified support semantics to their original node sets.
        if set_name not in nsets:  # Require every support set used by the baseline constraint contract.
            raise RuntimeError(f"required support node set {set_name} not found")  # Stop rather than inventing support membership.
        for node in nsets[set_name]:  # Visit every original node in the verified support set.
            for dof in dofs:  # Visit every constrained translational direction for this support set.
                constrained.add((node, dof))  # Mark the node/direction pair as unavailable for artificial point loading.
    return constrained  # Return the complete translational constraint mask.


def split_verified_step(text: str) -> tuple[str, list[str], dict[tuple[int, int], float], str]:  # Separate the verified permanent-load data and output requests without changing their numerical values.
    prefix, step_text = text.split("*STEP\n", 1)  # Separate the complete verified model definition from its single linear static step.
    if "*DLOAD\n" not in step_text or "*CLOAD\n" not in step_text or "*NODE PRINT" not in step_text:  # Require the expected verified LC01 step structure.
        raise RuntimeError("verified LC01 permanent-load step structure not found")  # Stop instead of parsing an incompatible analysis deck.
    after_dload = step_text.split("*DLOAD\n", 1)[1]  # Enter the verified gravity-load data block.
    dload_text, after_cload = after_dload.split("*CLOAD\n", 1)  # Separate gravity data from the verified nodal permanent-load block.
    cload_text, output_tail_without_marker = after_cload.split("*NODE PRINT", 1)  # Separate nodal permanent loads from all verified output requests.
    dload_lines = [line.strip() for line in dload_text.splitlines() if line.strip() and not line.strip().startswith("**")]  # Preserve every noncomment gravity-load data row exactly as text.
    final_cloads: dict[tuple[int, int], float] = {}  # Store the verified final nodal permanent loads by original node and global direction.
    for raw in cload_text.splitlines():  # Parse every original permanent nodal load record.
        line = raw.strip()  # Normalize surrounding whitespace only.
        if not line or line.startswith("**"):  # Ignore empty and comment rows inside the load block.
            continue  # Advance to the next verified nodal load record.
        fields = [field.strip() for field in line.split(")] if False else [field.strip() for field in line.split(",")]  # Parse the verified comma-separated CLOAD row while keeping the code path explicit.
        if len(fields) < 3:  # Reject malformed load records rather than silently dropping them.
            raise RuntimeError(f"malformed verified CLOAD row: {line}")  # Preserve fail-closed behavior for the baseline permanent actions.
        key = (int(fields[0]), int(fields[1]))  # Build the original node/direction key for this permanent point load.
        final_cloads[key] = final_cloads.get(key, 0.0) + float(fields[2])  # Preserve additive same-step load semantics if duplicate records ever occur.
    output_tail = "*NODE PRINT" + output_tail_without_marker  # Restore the first output keyword removed by the split operation.
    return prefix, dload_lines, final_cloads, output_tail  # Return frozen model data, verified gravity rows, verified point loads and original output requests.


def prestress_state(base_text: str, scale: float) -> tuple[str, dict[tuple[int, int], float], int, dict]:  # Build native initial stress and the exactly opposite free-DOF balancing point-load field for one scale.
    truss_text = base_text.replace("*ELEMENT, TYPE=B31, ELSET=MAIN_CABLES", "*ELEMENT, TYPE=T3D2, ELSET=MAIN_CABLES", 1)  # Remove artificial main-cable bending kinematics while preserving every original cable node and element label.
    old_section = "*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n"  # Match the verified equal-area B31 main-cable section exactly.
    new_section = f"*SOLID SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN\n{MAIN_CABLE_AREA_MM2:.12g}\n"  # Preserve identical axial area after the minimum B31-to-T3D2 representation change.
    if old_section not in truss_text:  # Require the exact verified section card before modifying cable kinematics.
        raise RuntimeError("verified MAIN_CABLES B31 section not found")  # Stop rather than silently changing an incompatible model.
    truss_text = truss_text.replace(old_section, new_section, 1)  # Apply the equal-area axial main-cable section.
    nodes, groups = core.parse_topology(truss_text)  # Recover unchanged original coordinates and line-element connectivity.
    items, _pretension_nodes, calibration_nodes, midspan_node, metadata = forces.elementwise_items(truss_text)  # Reuse the mechanics-derived scale-one segment and hanger tensions.
    item_by_element = {int(item["elementId"]): item for item in items}  # Index every prestress target by its original element label.
    blocked = constrained_dofs(truss_text)  # Recover original constrained translational degrees of freedom that must be balanced by support reactions instead of CLOADs.
    balance: dict[tuple[int, int], float] = {}  # Accumulate external point loads exactly opposite to the free-node prestress nodal forces.
    stress_lines = ["*INITIAL CONDITIONS, TYPE=STRESS"]  # Start the native CalculiX initial-stress block.
    stress_audit: list[dict] = []  # Preserve every element force, unit vector and stress tensor independently of solver results.
    for group_name in ("MAIN_CABLES", "HANGERS"):  # Prestress only the vertical suspension system requested for the isolated correction.
        for element_id, connectivity in groups[group_name]:  # Visit every unchanged main-cable and hanger element exactly once.
            node_1, node_2 = connectivity[:2]  # Recover the two original line-element endpoint labels.
            p1 = nodes[node_1]  # Recover the first endpoint coordinate.
            p2 = nodes[node_2]  # Recover the second endpoint coordinate.
            chord = tuple(p2[index] - p1[index] for index in range(3))  # Build the original element chord vector.
            length = math.sqrt(sum(value * value for value in chord))  # Compute the original three-dimensional element length.
            unit = tuple(value / length for value in chord)  # Normalize the chord into global direction cosines.
            item = item_by_element[element_id]  # Recover the mechanics-derived scale-one axial tension target.
            target_force = float(item["targetForceNAtScale1"]) * scale  # Scale the target tensile force for this calibration trial.
            axial_stress = float(item["targetStressMPaAtScale1"]) * scale  # Scale the associated uniform axial stress consistently.
            tensor = direct.axial_stress_tensor(axial_stress, p1, p2)  # Convert the axial tensile stress to a global Cartesian second-order tensor.
            for integration_point in range(1, 9):  # Match the eight integration points observed directly in verified PR9 T3D2 line-element output.
                stress_lines.append(f"{element_id}, {integration_point}, " + ", ".join(f"{value:.12g}" for value in tensor))  # Assign uniform native initial stress at every expanded truss integration point.
            element_on_node_1 = tuple(target_force * value for value in unit)  # Compute the tensile element force pulling node one toward node two.
            element_on_node_2 = tuple(-value for value in element_on_node_1)  # Compute the equal opposite tensile force pulling node two toward node one.
            for dof, component in enumerate(element_on_node_1, 1):  # Visit global translational components acting on node one.
                if (node_1, dof) not in blocked:  # Let verified supports provide reactions on constrained directions.
                    balance[(node_1, dof)] = balance.get((node_1, dof), 0.0) - component  # Apply the exact opposite external load on each free node-one direction.
            for dof, component in enumerate(element_on_node_2, 1):  # Visit global translational components acting on node two.
                if (node_2, dof) not in blocked:  # Let verified supports provide reactions on constrained directions.
                    balance[(node_2, dof)] = balance.get((node_2, dof), 0.0) - component  # Apply the exact opposite external load on each free node-two direction.
            stress_audit.append({"elementId": element_id, "group": group_name, "scale": scale, "targetForceN": target_force, "axialStressMPa": axial_stress, "unitVector": unit, "tensorGlobalMPa": tensor, "integrationPoints": list(range(1, 9))})  # Record the exact prestress construction used to generate both stress and balancing loads.
    balance = {key: value for key, value in balance.items() if abs(value) > 1.0e-9}  # Remove numerically zero point loads while preserving all meaningful balancing components.
    calibration_set = core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define unchanged interior deck-centerline nodes for completed-geometry selection.
    modified_prefix, dload_lines, final_cloads, output_tail = split_verified_step(truss_text)  # Recover the frozen model definition and verified final permanent actions.
    modified_prefix = modified_prefix.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge balanced-transfer prestressed equilibrium - scale {scale:.6g}", 1)  # Relabel the isolated completed-state calibration for provenance.
    modified_prefix = modified_prefix.replace("** No calibrated fabrication-state cable prestress is included.", "** Equal-area T3D2 main cables use native initial stress and an exact balancing-load transfer to the verified permanent-load state.", 1)  # Record the isolated prestress treatment in the model header.
    modified_prefix = modified_prefix.replace("** MATERIALS\n", calibration_set + "** MATERIALS\n", 1)  # Insert only the completed-geometry observation set into the frozen model definition.
    final_targets = dict(final_cloads)  # Start the transfer target with every verified final nodal permanent load.
    for key in balance:  # Ensure every artificial balancing load is explicitly replaced in the transfer step.
        final_targets.setdefault(key, 0.0)  # Set its final point-load target to zero unless a verified permanent CLOAD exists on the same node and direction.
    balance_lines = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(balance.items())]  # Serialize deterministic prestress-balancing CLOAD records.
    final_target_lines = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(final_targets.items())]  # Serialize deterministic final point-load targets for the static ramp from balance to permanent loading.
    setup_step = "*STEP, NAME=PRESTRESS_BALANCE, NLGEOM=YES, AMPLITUDE=STEP, INC=100\n*STATIC\n1.0, 1.0\n*CLOAD\n" + "\n".join(balance_lines) + "\n*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*END STEP\n"  # Establish a fully prestressed state held exactly by opposite free-node point loads before any physical dead-load transfer.
    transfer_step = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n*STATIC\n0.005, 1.0, 1.E-8, 0.01\n*DLOAD\n" + "\n".join(dload_lines) + "\n*CLOAD\n" + "\n".join(final_target_lines) + "\n" + output_tail  # Use default static ramp semantics to move every point load from its previous balancing value to the verified final target while gravity ramps from zero to full.
    deck = modified_prefix + "\n".join(stress_lines) + "\n" + setup_step + transfer_step  # Assemble the two-step balanced-transfer completed-state input deck.
    initial_balance_norm = math.sqrt(sum(value * value for value in balance.values()))  # Record the Euclidean norm of all free-DOF balancing point-load components as a reproducibility diagnostic.
    audit = {"scale": scale, "metadata": metadata, "mainCableRepresentationBefore": "B31 equal-area square", "mainCableRepresentationAfter": "T3D2 identical axial area", "stressAssignments": stress_audit, "balancingLoads": [{"node": node, "dof": dof, "loadN": value} for (node, dof), value in sorted(balance.items())], "balancingLoadComponentCount": len(balance), "balancingLoadVectorNormN": initial_balance_norm, "constrainedBalanceComponentsOmitted": len(blocked), "finalVerifiedCloadComponentCount": len(final_cloads), "transferTargetComponentCount": len(final_targets), "transferMethod": "Step 1 applies full balancing CLOAD with AMPLITUDE=STEP against full native initial stress; Step 2 uses default STATIC ramp from those previous CLOAD values to the verified final CLOAD values while verified DLOAD ramps from zero to full.", "temperaturePrestressUsed": False}  # Persist the complete equilibrium path and isolated model-change scope.
    return deck, midspan_node, audit  # Return the complete balanced-transfer deck and immutable audit metadata.


def main() -> int:  # Execute the bounded balanced-transfer scale sweep and package the clean completed state closest to the frozen bridge geometry.
    parser = argparse.ArgumentParser()  # Build the deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the successful verified PR9 L2 dead-load input deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated output root for all scales and receipts.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable resolved by GitHub Actions.
    args = parser.parse_args()  # Parse all required inputs before generating or solving any model.
    base_text = args.base.read_text(encoding="ascii")  # Read the verified baseline deck exactly once as ASCII.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before launching CalculiX.
    rows: list[dict] = []  # Accumulate convergence and completed-geometry metrics across all balanced-transfer scales.
    audits: dict[str, dict] = {}  # Preserve each exact prestress and balancing-load field independently of solver outcome.
    for scale in SCALES:  # Probe the bounded prestress scale family.
        deck, midspan_node, audit = prestress_state(base_text, scale)  # Generate one exactly balanced initial-prestress path on the frozen bridge model.
        audits[f"{scale:.2f}"] = audit  # Persist the exact construction for later inspection and reproducibility.
        stem = f"ZQ_L2BT_S{int(round(scale * 100)):03d}"  # Build a deterministic short CalculiX case identifier.
        trial_dir = args.output / "trials" / f"scale_{scale:.2f}".replace(".", "p")  # Isolate every solver run so failed trials cannot contaminate later scales.
        outcome = core.solve_trial(args.ccx, trial_dir, deck, stem, midspan_node)  # Execute both equilibrium steps and parse the final centerline completed-state displacement metrics.
        rows.append({"scale": scale, "stem": stem, "trialDir": str(trial_dir.relative_to(args.output)), **outcome})  # Record convergence, displacement and output-file evidence for this trial.
    converged = [row for row in rows if row["cleanConvergence"] and row["rmsCenterlineU3Mm"] is not None]  # Keep only clean completed nonlinear states with a final geometry objective.
    selected = min(converged, key=lambda row: row["rmsCenterlineU3Mm"]) if converged else None  # Select the converged prestress scale requiring the least movement from the frozen completed bridge geometry.
    summary = {"schemaVersion": "5.0.0-balanced-transfer-prestress", "status": "PASS" if selected else "FAIL", "baseModel": str(args.base), "intervention": "Native initial stress on equal-area T3D2 MAIN_CABLES and original T3D2 HANGERS plus exact free-DOF balancing-load initialization and a static ramp to the unchanged verified PR9 permanent loads.", "trials": rows, "selected": selected, "audits": audits, "selectionObjective": "minimum final RMS U3 over unchanged interior deck-centerline nodes among clean converged balanced-transfer trials", "engineeringRelease": "BLOCKED pending accepted unstressed cable lengths or measured erection/finished-state cable forces; PASS qualifies only a reproducible numerical research baseline."}  # Assemble the complete qualification receipt before any CI gate.
    (args.output / "balanced_transfer_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist all prestress, balancing-load and numerical evidence.
    with (args.output / "balanced_transfer_trials.csv").open("w", encoding="utf-8-sig", newline="") as stream:  # Create a compact spreadsheet-friendly scale comparison table.
        fields = ["scale", "cleanConvergence", "exitCode", "rmsCenterlineU3Mm", "maxAbsCenterlineU3Mm", "midspanU3Mm", "datBytes", "frdBytes", "stem", "trialDir"]  # Freeze stable scalar CSV columns.
        writer = csv.DictWriter(stream, fieldnames=fields)  # Create the deterministic row writer.
        writer.writeheader()  # Emit the explicit table schema.
        for row in rows:  # Serialize every trial regardless of convergence outcome.
            writer.writerow({field: row.get(field) for field in fields})  # Exclude nested solver log tails from the compact comparison table.
    if selected:  # Package the objectively selected clean completed-state research baseline.
        best = args.output / "best"  # Define the direct-use selected-model package directory.
        best.mkdir(exist_ok=True)  # Create the selected-model package directory.
        source_dir = args.output / selected["trialDir"]  # Resolve the selected trial's isolated CalculiX directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve input, field results and convergence evidence together.
            source = source_dir / f"{selected['stem']}.{suffix}"  # Resolve one selected numerical artifact by deterministic stem.
            if source.exists():  # Copy only artifacts actually emitted by CalculiX.
                shutil.copy2(source, best / source.name)  # Preserve the selected numerical bytes and metadata.
        (best / "selection.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")  # Place final selection metrics next to the accepted model.
    print(json.dumps({"status": summary["status"], "selected": selected, "trials": [{"scale": row["scale"], "cleanConvergence": row["cleanConvergence"], "midspanU3Mm": row["midspanU3Mm"], "rmsCenterlineU3Mm": row["rmsCenterlineU3Mm"]} for row in rows]}, ensure_ascii=False, indent=2))  # Surface the decisive balanced-transfer comparison in the Actions log.
    return 0 if selected else 2  # Pass CI only after at least one clean completed-state balanced-transfer equilibrium exists.


if __name__ == "__main__":  # Execute the calibration only when this file is invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the balanced-transfer qualification status to GitHub Actions.
