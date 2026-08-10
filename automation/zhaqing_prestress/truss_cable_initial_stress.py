#!/usr/bin/env python3  # Calibrate the Zhaqing completed state after the minimum necessary main-cable change from B31 to axial T3D2.
import initial_stress_prestress as direct  # Reuse the audited nonlinear scale sweep, result parser and geometry-based selector.
import elementwise_prestress as forces  # Reuse the mechanics-derived segment-wise main-cable and hanger target-force construction.

MAIN_CABLE_AREA_MM2 = direct.force_model.MAIN_CABLE_AREA_MM2  # Preserve exactly the equal area already used by the verified PR9 B31 main-cable section.


def truss_cable_block(base_text: str, scale: float) -> tuple[str, int, dict]:  # Build a direct-prestress completed-state model with only MAIN_CABLES changed from beam to axial truss elements.
    truss_text = base_text.replace("*ELEMENT, TYPE=B31, ELSET=MAIN_CABLES", "*ELEMENT, TYPE=T3D2, ELSET=MAIN_CABLES", 1)  # Remove artificial main-cable bending kinematics while preserving every original cable node and element label.
    old_section = "*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n"  # Match the verified PR9 equal-area B31 main-cable section exactly.
    new_section = f"*SOLID SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN\n{MAIN_CABLE_AREA_MM2:.12g}\n"  # Preserve the same axial area while eliminating cable bending stiffness.
    if old_section not in truss_text:  # Require the exact baseline section before changing representation.
        raise RuntimeError("verified L2 MAIN_CABLES B31 section not found")  # Stop rather than silently modifying an incompatible model.
    truss_text = truss_text.replace(old_section, new_section, 1)  # Apply the sole representation change required for a tension-dominated suspension cable.
    nodes, groups = direct.core.parse_topology(truss_text)  # Recover unchanged coordinates and connectivity after the element-type substitution.
    items, _pretension_nodes, calibration_nodes, midspan_node, metadata = forces.elementwise_items(truss_text)  # Recompute the same target forces on the unchanged geometric cable segments and hangers.
    item_by_element = {int(item["elementId"]): item for item in items}  # Index each target tension by original element label.
    lines = ["*INITIAL CONDITIONS, TYPE=STRESS"]  # Start the native CalculiX initial-stress block for the all-truss suspension system.
    stress_audit: list[dict] = []  # Preserve every element tensor and integration-point assignment independently of solver convergence.
    for group_name in ("MAIN_CABLES", "HANGERS"):  # Apply completed-state prestress only to main cables and vertical hangers.
        for element_id, connectivity in groups[group_name]:  # Visit every original suspension-system element exactly once.
            item = item_by_element[element_id]  # Recover the mechanics-derived scale-one target tension.
            p1 = nodes[connectivity[0]]  # Recover the first unchanged endpoint coordinate.
            p2 = nodes[connectivity[1]]  # Recover the second unchanged endpoint coordinate.
            axial_stress = float(item["targetStressMPaAtScale1"]) * scale  # Scale the target tensile stress without changing material stiffness or section area.
            tensor = direct.axial_stress_tensor(axial_stress, p1, p2)  # Express the axial tension as the global stress tensor required by CalculiX.
            for integration_point in range(1, 9):  # Match the eight integration points observed in the verified PR9 T3D2 DAT output.
                lines.append(f"{element_id}, {integration_point}, " + ", ".join(f"{value:.12g}" for value in tensor))  # Assign the same uniform axial stress through every expanded truss integration point.
            stress_audit.append({"elementId": element_id, "group": group_name, "scale": scale, "integrationPoints": list(range(1, 9)), "axialStressMPa": axial_stress, "tensorGlobalMPa": tensor, "targetForceN": float(item["targetForceNAtScale1"]) * scale})  # Record the physical target and exact solver tensor.
    calibration_set = direct.core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define unchanged interior deck-centerline nodes for completed-geometry calibration.
    patched = truss_text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge axial-main-cable prestressed equilibrium - scale {scale:.6g}", 1)  # Relabel the isolated trial for provenance.
    patched = patched.replace("** No calibrated fabrication-state cable prestress is included.", "** MAIN_CABLES use equal-area T3D2 axial representation with direct initial stress; all other verified PR9 L2 bridge choices remain frozen.", 1)  # Record the minimum necessary cable-model intervention explicitly.
    patched = patched.replace("** MATERIALS\n", calibration_set + "** MATERIALS\n", 1)  # Insert only the centerline observation set into the frozen model definition.
    prefix, old_step = patched.split("*STEP\n", 1)  # Separate the modified model definition from the original linear dead-load step.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve every original gravity load, nodal permanent action and result request verbatim.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add completed-geometry observations without removing the existing monitor output.
    step = "*STEP, NLGEOM=YES, AMPLITUDE=STEP, INC=500\n*STATIC\n0.1, 1.0, 1.E-8, 1.0\n" + dead_tail  # Present the full permanent loading from the first equilibrium state together with the fully present initial cable/hanger stress field.
    deck = prefix + "\n".join(lines) + "\n" + step  # Assemble the completed-state truss-cable nonlinear equilibrium deck.
    audit = {"scale": scale, "metadata": metadata, "stressAssignments": stress_audit, "mainCableRepresentationBefore": "B31 equal-area square 74.5432224 mm by 74.5432224 mm", "mainCableRepresentationAfter": "T3D2 with identical axial area", "mainCableAreaMm2": MAIN_CABLE_AREA_MM2, "mainCableNodesChanged": False, "mainCableElementLabelsChanged": False, "hangerRepresentationChanged": False, "otherModelChoicesChanged": False, "integrationPointsPerPrestressedElement": 8, "loading": "STEP amplitude so full permanent load and full initial stress coexist from the first nonlinear equilibrium iteration", "temperaturePrestressUsed": False}  # Persist the exact scope of the minimum representation change and prestress field.
    return deck, midspan_node, audit  # Return the all-truss suspension-system deck and immutable audit metadata.


direct.initial_stress_block = truss_cable_block  # Replace only the direct-stress model constructor while retaining the same bounded scale sweep and geometry selector.
if __name__ == "__main__":  # Execute the truss-cable calibration only when invoked as its workflow entry point.
    raise SystemExit(direct.main())  # Propagate the existing native-prestress qualification status after the minimal main-cable representation change.
