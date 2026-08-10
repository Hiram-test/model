#!/usr/bin/env python3  # Build suspension-system prestress constitutively from zero strain while exact balancing loads hold the completed geometry.
import argparse  # Parse deterministic baseline, output and CalculiX executable paths.
import json  # Persist the complete prestress-construction and nonlinear-equilibrium receipt.
import math  # Compute line-element direction cosines and balancing-force diagnostics.
from pathlib import Path  # Use explicit filesystem paths for every numerical artifact.
import balanced_transfer_v2 as bt  # Reuse the audited support mask, verified permanent-load parser and CalculiX execution contract.
import elementwise_prestress as forces  # Reuse the mechanics-derived scale-one cable-segment and hanger tension targets.
import prestress_isolation as core  # Reuse verified-L2 topology parsing and final displacement result extraction.
SCALE = 1.18  # Start from the previously identified minimum-residual global suspension-system prestress scale.
MAIN_AREA_MM2 = forces.MAIN_AREA_MM2  # Preserve exactly the axial area of the original equal-area main-cable section.
HANGER_AREA_MM2 = forces.HANGER_AREA_MM2  # Preserve exactly the original verified hanger axial area.
def unique_prestress_properties(items: list[dict]) -> str:  # Assign one elastic thermal-prestrain material to each original main-cable and hanger element.
    lines: list[str] = []  # Accumulate deterministic CalculiX model-definition rows.
    for index, item in enumerate(items, 1):  # Visit every prestressed line element once in a stable order.
        eset = f"ZQTE_{index:04d}"  # Build a compact one-element set name for independent section/material assignment.
        material = f"ZQTM_{index:04d}"  # Build a compact element-specific material name for independent thermal strain.
        is_main = item["kind"] == "MAIN_CABLE"  # Distinguish main-cable and hanger elastic properties while preserving original values.
        modulus = forces.MAIN_E_MPA if is_main else forces.HANGER_E_MPA  # Preserve the original verified Young modulus for this suspension-system element.
        area = MAIN_AREA_MM2 if is_main else HANGER_AREA_MM2  # Preserve the original verified axial area for this suspension-system element.
        alpha = float(item["targetStressMPaAtScale1"]) / modulus  # Choose expansion so temperature -1 generates the mechanics-derived scale-one tensile stress at fixed geometry.
        lines.append(f"*ELSET, ELSET={eset}")  # Define a one-element set without changing the original broad engineering element sets.
        lines.append(str(item["elementId"]))  # Place the unchanged original element label in the unique property set.
        lines.append(f"*MATERIAL, NAME={material}")  # Define the element-specific constitutive property card.
        lines.append("*ELASTIC")  # Preserve linear elastic material behavior in this screening bridge model.
        lines.append(f"{modulus:.12g}, 0.30")  # Preserve the verified elastic modulus and Poisson ratio.
        lines.append("*DENSITY")  # Preserve line-element self-weight under the unchanged gravity load.
        lines.append("7.85e-9")  # Preserve the verified steel density in N-mm-tonne-s units.
        lines.append("*EXPANSION, ZERO=0.")  # Define zero thermal strain at the original geometry and zero temperature.
        lines.append(f"{alpha:.12g}")  # Encode the target axial prestress as a constitutive contraction coefficient.
        lines.append(f"*SOLID SECTION, ELSET={eset}, MATERIAL={material}")  # Assign the unchanged axial area using T3D2-compatible section syntax.
        lines.append(f"{area:.12g}")  # Preserve the original verified axial section area exactly.
    return "\n".join(lines) + "\n"  # Return the complete element-specific property block with deterministic line endings.
def build_deck(base_text: str) -> tuple[str, int, dict]:  # Build a zero-to-prestress equilibrium step followed by a prestress-to-dead-load transfer step.
    text = base_text.replace("*ELEMENT, TYPE=B31, ELSET=MAIN_CABLES", "*ELEMENT, TYPE=T3D2, ELSET=MAIN_CABLES", 1)  # Remove artificial main-cable bending while preserving every original cable node and element label.
    main_section = "*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n"  # Match the frozen PR9 main-cable B31 section card exactly.
    hanger_section = "*SOLID SECTION, ELSET=HANGERS, MATERIAL=HANGER_BAR_SCREEN\n804.247719\n"  # Match the frozen PR9 broad hanger section card exactly.
    if main_section not in text or hanger_section not in text: raise RuntimeError("verified suspension-system section cards not found")  # Fail closed if the baseline representation contract changed.
    text = text.replace(main_section, "", 1)  # Remove the broad main-cable section before assigning element-specific T3D2 properties.
    text = text.replace(hanger_section, "", 1)  # Remove the broad hanger section before assigning element-specific T3D2 properties.
    nodes, groups = core.parse_topology(text)  # Recover unchanged original coordinates and connectivity after the main-cable element-type substitution.
    items, prestress_nodes, calibration_nodes, midspan_node, metadata = forces.elementwise_items(text)  # Recover mechanics-derived target tensions and observation nodes on the unchanged geometry.
    property_block = unique_prestress_properties(items)  # Build constitutive element-specific contraction properties for all main-cable and hanger elements.
    wind_section_marker = "*SOLID SECTION, ELSET=WIND_CABLES, MATERIAL=WIND_ROPE_SCREEN\n"  # Use the unchanged wind-cable section card as a deterministic property insertion anchor.
    if wind_section_marker not in text: raise RuntimeError("verified wind-cable section marker not found")  # Fail closed if the baseline section ordering changes.
    text = text.replace(wind_section_marker, property_block + wind_section_marker, 1)  # Insert unique suspension-system properties without changing wind-cable assumptions.
    blocked = bt.blocked_dofs(text)  # Recover verified constrained translational directions that must react prestress through supports.
    by_element = {int(item["elementId"]): item for item in items}  # Index mechanics-derived element force targets by unchanged original element label.
    balance: dict[tuple[int, int], float] = {}  # Accumulate exact opposite free-node point loads for the full target prestress state.
    force_audit: list[dict] = []  # Preserve every target force and direction independently of the constitutive implementation.
    for group in ("MAIN_CABLES", "HANGERS"):  # Build balancing loads only for the vertical suspension system being prestressed.
        for eid, conn in groups[group]:  # Visit every unchanged main-cable and hanger element once.
            n1, n2 = conn[:2]  # Recover the two original endpoint labels.
            p1, p2 = nodes[n1], nodes[n2]  # Recover the unchanged original endpoint coordinates.
            chord = tuple(p2[i] - p1[i] for i in range(3))  # Build the original line-element chord vector.
            length = math.sqrt(sum(value * value for value in chord))  # Compute the original three-dimensional chord length.
            unit = tuple(value / length for value in chord)  # Normalize the chord into global direction cosines.
            target = float(by_element[eid]["targetForceNAtScale1"]) * SCALE  # Apply the selected global scale to the mechanics-derived target tensile force.
            endpoint_forces = ((n1, tuple(target * value for value in unit)), (n2, tuple(-target * value for value in unit)))  # Compute the tensile element force acting on each original endpoint.
            for node, vector in endpoint_forces:  # Convert prestress endpoint forces into exact opposite external balancing loads.
                for dof, component in enumerate(vector, 1):  # Visit each global translational component.
                    if (node, dof) not in blocked: balance[(node, dof)] = balance.get((node, dof), 0.0) - component  # Hold every free prestressed endpoint at its original completed-state coordinate.
            force_audit.append({"elementId": eid, "group": group, "targetForceN": target, "unitVector": unit})  # Record the exact physical force target independently of thermal-strain implementation.
    balance = {key: value for key, value in balance.items() if abs(value) > 1.0e-8}  # Remove only numerically zero balancing components.
    prefix, dload_rows, final_cloads, output_tail = bt.split_loads(text)  # Recover the unchanged verified permanent actions and output requests.
    prefix = prefix.replace("** No calibrated fabrication-state cable prestress is included.", "** Balanced constitutive prestress: T3D2 main cables and hangers are contracted from zero strain while exact balancing loads preserve completed geometry.", 1)  # Record the isolated prestress construction in the model header.
    added_sets = core.write_nset("PRETENSION_NODES", prestress_nodes) + core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define only the suspension-temperature and completed-geometry observation node sets.
    prefix = prefix.replace("** MATERIALS\n", added_sets + "** MATERIALS\n", 1)  # Insert the two additional node sets before unchanged baseline material definitions.
    final_targets = dict(final_cloads)  # Start the transfer target from every verified final nodal permanent load.
    for key in balance: final_targets.setdefault(key, 0.0)  # Explicitly ramp each artificial balancing load to zero unless a verified final load exists on the same degree of freedom.
    balance_rows = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(balance.items())]  # Serialize deterministic full-prestress balancing point loads.
    target_rows = [f"{node}, {dof}, {value:.12g}" for (node, dof), value in sorted(final_targets.items())]  # Serialize deterministic final verified point-load targets including explicit balancing-load removals.
    build_step = "*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, INC=1000\n*STATIC\n0.01, 1.0, 1.E-8, 0.02\n*TEMPERATURE\nPRETENSION_NODES, -1.18\n*CLOAD\n" + "\n".join(balance_rows) + "\n*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*END STEP\n"  # Ramp constitutive contraction and exact opposite balancing loads together from zero so prestress is generated without initial-stress injection.
    transfer_step = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n*STATIC\n0.005, 1.0, 1.E-8, 0.01\n*DLOAD\n" + "\n".join(dload_rows) + "\n*CLOAD\n" + "\n".join(target_rows) + "\n" + output_tail  # Hold the completed prestress temperature from step one while default static ramping replaces balancing CLOADs with verified final CLOADs and introduces unchanged gravity.
    deck = prefix + build_step + transfer_step  # Assemble the complete two-step constitutive-prestress and permanent-load equilibrium model.
    audit = {"scale": SCALE, "metadata": metadata, "forceTargets": force_audit, "balancingLoadComponents": len(balance), "balancingLoadNormN": math.sqrt(sum(value * value for value in balance.values())), "mainCableRepresentation": "equal-area T3D2", "prestressMethod": "element-specific thermal contraction ramped from zero with proportional exact balancing CLOADs", "temperatureAtEndPrestressStep": -SCALE, "nativeInitialStressUsed": False, "verifiedPermanentLoadsChanged": False}  # Persist the complete physical and numerical scope of the prestress correction.
    return deck, midspan_node, audit  # Return the complete bridge deck, midspan observation node and audit metadata.
def main() -> int:  # Execute the constitutive-prestress diagnostic and persist all numerical evidence.
    parser = argparse.ArgumentParser()  # Build the deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the verified PR9 LC01 baseline deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated evidence root.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable path.
    args = parser.parse_args()  # Parse all required inputs before generating the model.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before numerical execution.
    deck, midspan_node, audit = build_deck(args.base.read_text(encoding="ascii"))  # Generate the two-step constitutive-prestress model from the immutable verified baseline.
    outcome = core.solve_trial(args.ccx, args.output / "solve", deck, "ZQ_L2TH_S118", midspan_node)  # Execute both nonlinear steps and parse final completed-geometry displacement metrics.
    receipt = {"schemaVersion": "6.0.0-balanced-constitutive-prestress", "status": "PASS" if outcome["cleanConvergence"] and outcome["rmsCenterlineU3Mm"] is not None else "FAIL", "audit": audit, "outcome": outcome, "engineeringRelease": "BLOCKED pending accepted unstressed lengths or measured erection/finished-state cable forces."}  # Assemble the complete numerical qualification receipt.
    (args.output / "balanced_thermal_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the diagnostic decision before returning workflow status.
    print(json.dumps(receipt, ensure_ascii=False, indent=2))  # Surface the complete result in the Actions log.
    return 0 if receipt["status"] == "PASS" else 2  # Pass only after both nonlinear steps complete cleanly and final completed-state geometry is observable.
if __name__ == "__main__": raise SystemExit(main())  # Execute the diagnostic only when invoked as its workflow entry point and propagate qualification status.
