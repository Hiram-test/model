#!/usr/bin/env python3  # Execute native initial-stress calibration with uniform stress assigned at all eight CalculiX line-element integration points.
import initial_stress_prestress as model  # Reuse the audited direct-stress solver loop, target-force construction and result selection logic.


def all_integration_point_block(base_text: str, scale: float) -> tuple[str, int, dict]:  # Replace the one-integration-point prototype with the observed eight-point B31/T3D2 stress representation.
    nodes, groups = model.core.parse_topology(base_text)  # Recover immutable verified-L2 coordinates and original line-element connectivity.
    items, _pretension_nodes, calibration_nodes, midspan_node, metadata = model.force_model.elementwise_items(base_text)  # Reuse the mechanics-derived cable and hanger tension targets.
    item_by_element = {int(item["elementId"]): item for item in items}  # Index every scale-one tension target by its original element label.
    lines = ["*INITIAL CONDITIONS, TYPE=STRESS"]  # Start the native CalculiX initial-stress model-definition block.
    stress_audit: list[dict] = []  # Preserve the exact tensor and all integration-point assignments for review.
    for group_name in ("MAIN_CABLES", "HANGERS"):  # Apply initial stress only to the vertical suspension system under study.
        for element_id, connectivity in groups[group_name]:  # Visit every unchanged main-cable and hanger line element exactly once.
            item = item_by_element[element_id]  # Recover the mechanics-derived scale-one axial force and stress for this element.
            p1 = nodes[connectivity[0]]  # Recover the first original endpoint coordinate.
            p2 = nodes[connectivity[1]]  # Recover the second original endpoint coordinate.
            axial_stress = float(item["targetStressMPaAtScale1"]) * scale  # Scale the element's tensile prestress without changing its section or elastic material.
            tensor = model.axial_stress_tensor(axial_stress, p1, p2)  # Express the tensile prestress as a global Cartesian stress tensor.
            for integration_point in range(1, 9):  # Match the eight integration points observed directly in the verified PR9 B31 and T3D2 DAT output.
                lines.append(f"{element_id}, {integration_point}, " + ", ".join(f"{value:.12g}" for value in tensor))  # Assign the identical uniform axial tensor across the entire expanded line-element section.
            stress_audit.append({"elementId": element_id, "group": group_name, "scale": scale, "integrationPoints": list(range(1, 9)), "axialStressMPa": axial_stress, "tensorGlobalMPa": tensor, "targetForceN": float(item["targetForceNAtScale1"]) * scale})  # Record the physical target and all eight solver assignments independently of convergence.
    calibration_set = model.core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define unchanged deck-centerline nodes used for completed-geometry calibration.
    patched = base_text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge L2 all-IP initial-stress equilibrium - scale {scale:.6g}", 1)  # Relabel the isolated direct-stress trial for provenance.
    patched = patched.replace("** No calibrated fabrication-state cable prestress is included.", "** Uniform direct initial stress is assigned at all eight observed B31/T3D2 integration points; all other verified PR9 L2 choices remain unchanged.", 1)  # Record the sole physical intervention in the input header.
    patched = patched.replace("** MATERIALS\n", calibration_set + "** MATERIALS\n", 1)  # Insert only the centerline observation set into the original model definition.
    prefix, old_step = patched.split("*STEP\n", 1)  # Separate the verified model definition from its original linear dead-load procedure.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve all original gravity, nodal permanent actions and result requests verbatim.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add completed-geometry output without removing existing monitoring output.
    step = "*STEP, NLGEOM=YES, AMPLITUDE=STEP, INC=500\n*STATIC\n0.1, 1.0, 1.E-8, 1.0\n" + dead_tail  # Present full permanent loading from the first equilibrium state so it acts together with the fully present initial stress field.
    deck = prefix + "\n".join(lines) + "\n" + step  # Assemble the native all-integration-point initial-stress completed-state model.
    audit = {"scale": scale, "metadata": metadata, "stressAssignments": stress_audit, "initialStressElementCount": len(stress_audit), "integrationPointsPerPrestressedElement": 8, "integrationPointEvidence": "Verified PR9 LC01_G_DEAD.dat prints integration points 1 through 8 for both MAIN_CABLES B31 and HANGERS T3D2.", "loading": "STEP amplitude so full permanent load and full initial stress coexist from the first equilibrium iteration", "temperaturePrestressUsed": False, "sectionPropertiesChanged": False}  # Persist the complete numerical interpretation of the trial.
    return deck, midspan_node, audit  # Return the corrected direct-stress deck and immutable audit metadata.


model.initial_stress_block = all_integration_point_block  # Replace only the flawed one-point stress assignment while retaining the existing bounded scale sweep and selection logic.
if __name__ == "__main__":  # Execute the corrected calibration only when invoked as its workflow entry point.
    raise SystemExit(model.main())  # Propagate the original direct-stress qualification status after using all eight integration points.
