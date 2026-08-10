#!/usr/bin/env python3  # Validate a physically balanced initial-prestress state before transferring to the verified Zhaqing permanent loads.
import argparse  # Parse deterministic baseline, output and CalculiX executable paths.
import json  # Persist the complete prestress and nonlinear-equilibrium receipt.
import math  # Compute line-element unit vectors and balancing-force norms.
from pathlib import Path  # Use explicit filesystem paths for all numerical artifacts.
import initial_stress_prestress as direct  # Reuse the audited global stress-tensor conversion helper.
import elementwise_prestress as forces  # Reuse the mechanics-derived segment-wise cable and hanger force targets.
import prestress_isolation as core  # Reuse the verified-L2 topology parser and CalculiX execution/result parser.
SCALE = 1.18  # Start from the minimum-residual scale identified by the prior isolated prestress sweep.
MAIN_AREA_MM2 = forces.MAIN_AREA_MM2  # Preserve exactly the original PR9 main-cable axial area.
SUPPORTS = {"TOWER_BASES": (1, 2, 3), "MAIN_CABLE_ANCHORS": (1, 2, 3), "WIND_ANCHORS": (1, 2, 3), "DECK_LEFT_PIN": (1, 2, 3), "DECK_RIGHT_ROLLER": (2, 3)}  # Freeze the verified translational support contract.
def read_nsets(text: str) -> dict[str, set[int]]:  # Parse the explicit support node sets from the verified input deck.
    result: dict[str, set[int]] = {}  # Store normalized explicit node sets.
    active: str | None = None  # Track the current NSET block while scanning the deck.
    for raw in text.splitlines():  # Visit every input line once in source order.
        line = raw.strip()  # Normalize surrounding whitespace only.
        if line.upper().startswith("*NSET"):  # Detect an explicit node-set keyword.
            active = next((field.split("=", 1)[1].strip().upper() for field in line.split(",")[1:] if "=" in field and field.split("=", 1)[0].strip().upper() == "NSET"), None)  # Extract the normalized NSET name.
            if active: result.setdefault(active, set())  # Initialize storage for the active named set.
            continue  # Advance to the set data rows.
        if line.startswith("*"): active = None; continue  # End NSET parsing at the next keyword boundary.
        if active and line and not line.startswith("**"):  # Parse explicit node labels inside the active set.
            for token in line.split(","):  # Visit each comma-separated node token.
                if token.strip().isdigit(): result[active].add(int(token.strip()))  # Store explicit original node labels only.
    return result  # Return all explicit node sets required by the support mask.
def blocked_dofs(text: str) -> set[tuple[int, int]]:  # Convert verified support sets into constrained translational node/direction pairs.
    nsets = read_nsets(text)  # Recover the explicit support-set membership.
    blocked: set[tuple[int, int]] = set()  # Store constrained translational degree-of-freedom keys.
    for name, dofs in SUPPORTS.items():  # Apply the frozen support semantics to each named set.
        if name not in nsets: raise RuntimeError(f"missing support set {name}")  # Fail closed if a required verified support set is absent.
        for node in nsets[name]:  # Visit every support node in the named set.
            for dof in dofs: blocked.add((node, dof))  # Mark each constrained translational direction.
    return blocked  # Return the complete translational support mask.
def split_loads(text: str) -> tuple[str, list[str], dict[tuple[int, int], float], str]:  # Recover the exact verified gravity, point loads and output requests from LC01.
    prefix, step = text.split("*STEP\n", 1)  # Separate model definition from the single verified baseline step.
    after_dload = step.split("*DLOAD\n", 1)[1]  # Enter the verified gravity-load section.
    dload_text, after_cload = after_dload.split("*CLOAD\n", 1)  # Separate gravity rows from nodal permanent loads.
    cload_text, output_rest = after_cload.split("*NODE PRINT", 1)  # Separate nodal permanent loads from output requests.
    dload_rows = [row.strip() for row in dload_text.splitlines() if row.strip() and not row.strip().startswith("**")]  # Preserve every verified gravity row.
    cloads: dict[tuple[int, int], float] = {}  # Store final verified nodal loads by node and direction.
    for raw in cload_text.splitlines():  # Parse every original nodal permanent-load row.
        row = raw.strip()  # Normalize surrounding whitespace only.
        if not row or row.startswith("**"): continue  # Skip only empty and comment rows.
        fields = [field.strip() for field in row.split(",")]  # Parse the verified comma-separated CLOAD record.
        key = (int(fields[0]), int(fields[1]))  # Build the node/direction key.
        cloads[key] = cloads.get(key, 0.0) + float(fields[2])  # Preserve additive same-step load semantics.
    return prefix, dload_rows, cloads, "*NODE PRINT" + output_rest  # Return frozen model data, permanent actions and original output requests.
def build_deck(base_text: str) -> tuple[str, int, dict]:  # Construct the balanced initial-prestress state and smooth permanent-load transfer path.
    text = base_text.replace("*ELEMENT, TYPE=B31, ELSET=MAIN_CABLES", "*ELEMENT, TYPE=T3D2, ELSET=MAIN_CABLES", 1)  # Convert only the main cable from bending beam to equal-node axial truss kinematics.
    old_section = "*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n"  # Match the frozen PR9 main-cable section card exactly.
    new_section = f"*SOLID SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN\n{MAIN_AREA_MM2:.12g}\n"  # Preserve identical axial area in T3D2 form.
    if old_section not in text: raise RuntimeError("main-cable section card not found")  # Fail closed if the baseline section contract changed.
    text = text.replace(old_section, new_section, 1)  # Apply the minimum main-cable representation correction.
    nodes, groups = core.parse_topology(text)  # Recover unchanged original coordinates and connectivity.
    items, _prestress_nodes, calibration_nodes, midspan_node, metadata = forces.elementwise_items(text)  # Recover the mechanics-derived element force targets and geometry-observation nodes.
    by_element = {int(item["elementId"]): item for item in items}  # Index every prestress target by original element label.
    blocked = blocked_dofs(text)  # Recover constrained translational directions that must react prestress through supports.
    balance: dict[tuple[int, int], float] = {}  # Accumulate exact opposite point loads on every free prestressed endpoint degree of freedom.
    stress_rows = ["*INITIAL CONDITIONS, TYPE=STRESS"]  # Start the native initial-stress model-definition block.
    stress_audit: list[dict] = []  # Preserve every physical target and solver stress tensor.
    for group in ("MAIN_CABLES", "HANGERS"):  # Prestress only the vertical suspension system in this isolated correction.
        for eid, conn in groups[group]:  # Visit every original main-cable and hanger element once.
            n1, n2 = conn[:2]  # Recover the original endpoint labels.
            p1, p2 = nodes[n1], nodes[n2]  # Recover the unchanged endpoint coordinates.
            chord = tuple(p2[i] - p1[i] for i in range(3))  # Build the original element chord vector.
            length = math.sqrt(sum(value * value for value in chord))  # Compute the original element length.
            unit = tuple(value / length for value in chord)  # Normalize the chord into global direction cosines.
            target = float(by_element[eid]["targetForceNAtScale1"]) * SCALE  # Apply the calibrated global prestress scale to this element's mechanics-derived target force.
            stress = float(by_element[eid]["targetStressMPaAtScale1"]) * SCALE  # Apply the same scale to the associated uniform tensile stress.
            tensor = direct.axial_stress_tensor(stress, p1, p2)  # Express the axial tensile stress as a global Cartesian tensor.
            for ip in range(1, 9): stress_rows.append(f"{eid}, {ip}, " + ", ".join(f"{value:.12g}" for value in tensor))  # Assign uniform initial stress at all eight observed expanded-truss integration points.
            node_forces = ((n1, tuple(target * value for value in unit)), (n2, tuple(-target * value for value in unit)))  # Compute the tensile element forces acting on both original endpoints.
            for node, vector in node_forces:  # Convert element endpoint forces into opposite external balancing loads.
                for dof, component in enumerate(vector, 1):  # Visit each global translational component.
                    if (node, dof) not in blocked: balance[(node, dof)] = balance.get((node, dof), 0.0) - component  # Balance every free prestress endpoint component exactly while supports carry constrained reactions.
            stress_audit.append({"elementId": eid, "group": group, "targetForceN": target, "axialStressMPa": stress, "unitVector": unit, "tensorGlobalMPa": tensor})  # Preserve the exact prestress construction for audit.
    balance = {key: value for key, value in balance.items() if abs(value) > 1.0e-8}  # Drop only numerically zero balancing components.
    prefix, dload_rows, final_cloads, output_tail = split_loads(text)  # Recover the frozen verified final permanent actions and output requests.
    prefix = prefix.replace("** No calibrated fabrication-state cable prestress is included.", "** Balanced-transfer native prestress: equal-area T3D2 main cables and original T3D2 hangers.", 1)  # Record the isolated prestress intervention in the model header.
    prefix = prefix.replace("** MATERIALS\n", core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes) + "** MATERIALS\n", 1)  # Add only the completed-geometry observation node set.
    final_targets = dict(final_cloads)  # Start transfer targets from the verified final nodal permanent loads.
    for key in balance: final_targets.setdefault(key, 0.0)  # Explicitly ramp every artificial balancing load to zero unless a verified final load occupies the same degree of freedom.
    balance_rows = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(balance.items())]  # Serialize deterministic exact balancing point loads.
    target_rows = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(final_targets.items())]  # Serialize deterministic verified final point-load targets including explicit zeros for removed balancing loads.
    step_balance = "*STEP, NAME=PRESTRESS_BALANCE, NLGEOM=YES, AMPLITUDE=STEP, INC=100\n*STATIC\n1.0, 1.0\n*CLOAD\n" + "\n".join(balance_rows) + "\n*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*END STEP\n"  # Establish a fully prestressed state held by exact opposite free-node point loads with no ramp mismatch.
    step_transfer = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n*STATIC\n0.005, 1.0, 1.E-8, 0.01\n*DLOAD\n" + "\n".join(dload_rows) + "\n*CLOAD\n" + "\n".join(target_rows) + "\n" + output_tail  # Let default STATIC ramp semantics move previous balancing CLOADs to final verified CLOAD targets while gravity ramps from zero to full.
    deck = prefix + "\n".join(stress_rows) + "\n" + step_balance + step_transfer  # Assemble the complete two-step balanced-transfer nonlinear model.
    audit = {"scale": SCALE, "metadata": metadata, "stressAssignments": stress_audit, "balancingLoadComponents": len(balance), "balancingLoadNormN": math.sqrt(sum(value * value for value in balance.values())), "finalVerifiedCloadComponents": len(final_cloads), "transferTargetComponents": len(final_targets), "mainCableRepresentation": "equal-area T3D2", "temperaturePrestressUsed": False}  # Record every physical and numerical assumption in the diagnostic receipt.
    return deck, midspan_node, audit  # Return the complete model, midspan observation node and auditable prestress construction.
def main() -> int:  # Execute the single-scale balanced-transfer diagnostic and persist all numerical evidence.
    parser = argparse.ArgumentParser()  # Build the deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the verified PR9 LC01 input deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated output root.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable path.
    args = parser.parse_args()  # Parse all required inputs before model generation.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before solver execution.
    deck, midspan_node, audit = build_deck(args.base.read_text(encoding="ascii"))  # Generate the balanced-transfer model from the immutable verified baseline.
    outcome = core.solve_trial(args.ccx, args.output / "solve", deck, "ZQ_L2BT_S118", midspan_node)  # Execute both nonlinear steps and parse final completed-geometry metrics.
    receipt = {"schemaVersion": "5.1.0-balanced-transfer-diagnostic", "status": "PASS" if outcome["cleanConvergence"] and outcome["rmsCenterlineU3Mm"] is not None else "FAIL", "audit": audit, "outcome": outcome, "engineeringRelease": "BLOCKED pending accepted unstressed lengths or measured cable forces."}  # Assemble the complete numerical qualification receipt.
    (args.output / "balanced_transfer_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the diagnostic decision before returning CI status.
    print(json.dumps(receipt, ensure_ascii=False, indent=2))  # Surface the complete diagnostic outcome in the Actions log.
    return 0 if receipt["status"] == "PASS" else 2  # Pass only when both nonlinear equilibrium steps complete cleanly and final geometry is observable.
if __name__ == "__main__": raise SystemExit(main())  # Execute the diagnostic only when invoked as the workflow entry point and propagate its qualification status.
