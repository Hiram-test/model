#!/usr/bin/env python3  # Solve the completed Zhaqing bridge directly by co-ramping verified dead load and element-specific cable/hanger unstressed-length contraction.
import argparse  # Parse deterministic baseline, output and CalculiX executable paths.
import csv  # Persist a compact prestress-scale comparison table.
import json  # Persist the complete form-finding construction and qualification receipt.
import shutil  # Package the objectively selected converged completed-state model and results.
from pathlib import Path  # Use explicit filesystem paths for every numerical artifact.
import elementwise_prestress as source  # Reuse the audited mechanics-derived segment and hanger prestress targets plus result parser helpers.
SCALES = (0.70, 0.85, 1.00, 1.18, 1.35)  # Probe a bounded range around the analytical and prior residual-minimum prestress levels.
MAIN_AREA_MM2 = source.MAIN_AREA_MM2  # Preserve exactly the axial area of the verified PR9 equal-area main-cable section.
HANGER_AREA_MM2 = source.HANGER_AREA_MM2  # Preserve exactly the verified PR9 hanger axial area.
def property_block(items: list[dict]) -> str:  # Generate one T3D2-compatible constitutive contraction property for every original main-cable and hanger element.
    lines: list[str] = []  # Accumulate deterministic CalculiX model-definition rows.
    for index, item in enumerate(items, 1):  # Visit every prestressed suspension-system element once in stable order.
        eset = f"ZQFF_{index:04d}"  # Build a compact one-element set name for independent property assignment.
        material = f"ZQFM_{index:04d}"  # Build a compact element-specific material name for independent unstressed-length control.
        is_main = item["kind"] == "MAIN_CABLE"  # Distinguish main-cable and hanger original elastic properties.
        modulus = source.MAIN_E_MPA if is_main else source.HANGER_E_MPA  # Preserve the verified Young modulus of the original element family.
        area = MAIN_AREA_MM2 if is_main else HANGER_AREA_MM2  # Preserve the verified axial area of the original element family.
        alpha = float(item["targetStressMPaAtScale1"]) / modulus  # Choose expansion so temperature minus one corresponds to the mechanics-derived scale-one axial contraction at fixed geometry.
        lines.append(f"*ELSET, ELSET={eset}")  # Define a one-element set while retaining the original engineering element sets.
        lines.append(str(item["elementId"]))  # Place the unchanged original element label into the unique set.
        lines.append(f"*MATERIAL, NAME={material}")  # Define the element-specific elastic and thermal material.
        lines.append("*ELASTIC")  # Preserve linear elastic constitutive behavior for this screening bridge model.
        lines.append(f"{modulus:.12g}, 0.30")  # Preserve the verified Young modulus and Poisson ratio.
        lines.append("*DENSITY")  # Preserve suspension-element self-weight under the unchanged gravity load.
        lines.append("7.85e-9")  # Preserve the verified steel density in N-mm-tonne-s units.
        lines.append("*EXPANSION, ZERO=0.")  # Encode unstressed-length shortening through a transparent thermal-strain proxy.
        lines.append(f"{alpha:.12g}")  # Store the element-specific scale-one contraction coefficient.
        lines.append(f"*SOLID SECTION, ELSET={eset}, MATERIAL={material}")  # Assign T3D2-compatible axial section data using the unique material.
        lines.append(f"{area:.12g}")  # Preserve the original verified axial section area exactly.
    return "\n".join(lines) + "\n"  # Return the complete unique suspension-system property block.
def formfind_deck(base_text: str, scale: float) -> tuple[str, int, dict]:  # Build one direct nonlinear completed-state trial with no artificial balancing loads or injected initial stress.
    text = base_text.replace("*ELEMENT, TYPE=B31, ELSET=MAIN_CABLES", "*ELEMENT, TYPE=T3D2, ELSET=MAIN_CABLES", 1)  # Remove artificial main-cable bending while preserving every original cable node and element label.
    main_section = "*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n"  # Match the frozen PR9 broad main-cable section card exactly.
    hanger_section = "*SOLID SECTION, ELSET=HANGERS, MATERIAL=HANGER_BAR_SCREEN\n804.247719\n"  # Match the frozen PR9 broad hanger section card exactly.
    if main_section not in text or hanger_section not in text:  # Require both verified suspension-system section cards before changing their constitutive representation.
        raise RuntimeError("verified suspension-system section cards not found")  # Fail closed if the baseline representation contract changed.
    text = text.replace(main_section, "", 1)  # Remove the broad main-cable property before element-specific T3D2 assignments.
    text = text.replace(hanger_section, "", 1)  # Remove the broad hanger property before element-specific T3D2 assignments.
    items, prestress_nodes, calibration_nodes, midspan_node, metadata = source.elementwise_items(text)  # Recover mechanics-derived target forces and unchanged completed-geometry observation nodes.
    unique_properties = property_block(items)  # Build element-specific unstressed-length contraction properties for all main-cable and hanger elements.
    wind_marker = "*SOLID SECTION, ELSET=WIND_CABLES, MATERIAL=WIND_ROPE_SCREEN\n"  # Use the unchanged wind-cable section as a deterministic insertion anchor.
    if wind_marker not in text:  # Require the exact verified wind-cable section marker before inserting new properties.
        raise RuntimeError("verified wind-cable section marker not found")  # Fail closed instead of altering an incompatible deck.
    text = text.replace(wind_marker, unique_properties + wind_marker, 1)  # Insert the element-specific suspension properties without changing wind-cable assumptions.
    added_sets = source.core.write_nset("PRETENSION_NODES", prestress_nodes) + source.core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define only the thermal suspension nodes and completed-geometry observation nodes.
    text = text.replace("** MATERIALS\n", added_sets + "** MATERIALS\n", 1)  # Insert the additional node sets before unchanged baseline material definitions.
    text = text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge direct nonlinear form-find - scale {scale:.6g}", 1)  # Relabel the isolated trial for provenance.
    text = text.replace("** No calibrated fabrication-state cable prestress is included.", "** Direct form-find: equal-area T3D2 main cables and original T3D2 hangers co-ramp element-specific unstressed-length contraction with the verified PR9 dead load.", 1)  # Record the sole physical intervention in the input header.
    prefix, old_step = text.split("*STEP\n", 1)  # Separate the frozen model definition from the original verified linear dead-load step.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve every verified gravity load, nodal permanent action and result request verbatim.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add completed-geometry output without removing the original monitoring output.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n"  # Define zero initial contraction before the direct nonlinear form-finding step.
    step = f"*STEP, NAME=FORM_FIND_DEAD, NLGEOM=YES, INC=2000\n*STATIC\n0.001, 1.0, 1.E-9, 0.01\n*TEMPERATURE\nPRETENSION_NODES, {-scale:.12g}\n" + dead_tail  # Co-ramp unstressed-length contraction and every unchanged verified permanent load from zero to the target completed state.
    audit = {"scale": scale, "metadata": metadata, "mainCableRepresentationBefore": "B31 equal-area square", "mainCableRepresentationAfter": "T3D2 with identical axial area", "mainCableNodesChanged": False, "mainCableElementLabelsChanged": False, "hangerRepresentationChanged": False, "artificialBalancingLoadsUsed": False, "nativeInitialStressUsed": False, "formFindingMethod": "single NLGEOM static step co-ramping element-specific constitutive contraction and unchanged verified PR9 dead load", "verifiedPermanentLoadsChanged": False}  # Persist the complete scope of the direct form-finding intervention.
    return prefix + initial + step, midspan_node, audit  # Return the complete form-finding deck, observation node and immutable audit metadata.
def main() -> int:  # Execute the bounded direct nonlinear form-finding sweep and package the converged completed state closest to the frozen bridge geometry.
    parser = argparse.ArgumentParser()  # Build the deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the successful verified PR9 LC01 dead-load input deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated output root for all scale trials and receipts.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable resolved by GitHub Actions.
    args = parser.parse_args()  # Parse all required inputs before generating or solving any model.
    base_text = args.base.read_text(encoding="ascii")  # Read the verified baseline deck exactly once as ASCII.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before launching CalculiX.
    rows: list[dict] = []  # Accumulate solver and completed-geometry metrics across all form-finding scales.
    audits: dict[str, dict] = {}  # Preserve each exact form-finding construction independently of convergence outcome.
    for scale in SCALES:  # Probe the bounded contraction/prestress scale family.
        deck, midspan_node, audit = formfind_deck(base_text, scale)  # Generate one direct nonlinear completed-state trial.
        audits[f"{scale:.2f}"] = audit  # Persist the exact model construction for later audit.
        stem = f"ZQ_L2FF_S{int(round(scale * 100)):03d}"  # Build a deterministic short solver identifier.
        trial_dir = args.output / "trials" / f"scale_{scale:.2f}".replace(".", "p")  # Isolate every solver run so failed scales cannot contaminate later cases.
        outcome = source.solve_trial(args.ccx, trial_dir, deck, stem, midspan_node)  # Execute the nonlinear form-find and parse final completed-geometry displacement metrics.
        rows.append({"scale": scale, "stem": stem, "trialDir": str(trial_dir.relative_to(args.output)), **outcome})  # Record convergence, displacement and result-file evidence for this scale.
    converged = [row for row in rows if row["cleanConvergence"] and row["rmsCenterlineU3Mm"] is not None]  # Keep only clean completed nonlinear states with an observable geometry objective.
    selected = min(converged, key=lambda row: row["rmsCenterlineU3Mm"]) if converged else None  # Select the converged scale requiring the least movement from the frozen completed bridge coordinates.
    summary = {"schemaVersion": "7.0.0-direct-truss-formfind", "status": "PASS" if selected else "FAIL", "baseModel": str(args.base), "intervention": "Only MAIN_CABLES B31-to-equal-area T3D2 plus element-specific main-cable/hanger unstressed-length contraction and NLGEOM; PR9 geometry, nodes, element labels, supports and permanent loads remain frozen.", "trials": rows, "selected": selected, "audits": audits, "selectionObjective": "minimum final RMS U3 over unchanged interior deck-centerline nodes among clean converged form-finding trials", "engineeringRelease": "BLOCKED pending accepted unstressed lengths or measured erection/finished-state cable forces; PASS qualifies only a reproducible numerical research baseline."}  # Assemble the complete numerical qualification receipt before workflow gating.
    (args.output / "truss_formfind_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist all form-finding and numerical evidence.
    with (args.output / "truss_formfind_trials.csv").open("w", encoding="utf-8-sig", newline="") as stream:  # Create a compact spreadsheet-friendly scale comparison table.
        fields = ["scale", "cleanConvergence", "exitCode", "rmsCenterlineU3Mm", "maxAbsCenterlineU3Mm", "midspanU3Mm", "datBytes", "frdBytes", "stem", "trialDir"]  # Freeze stable scalar CSV columns.
        writer = csv.DictWriter(stream, fieldnames=fields)  # Create the deterministic row writer.
        writer.writeheader()  # Emit the explicit table schema.
        for row in rows:  # Serialize every trial regardless of convergence outcome.
            writer.writerow({field: row.get(field) for field in fields})  # Exclude nested log tails from the compact comparison table.
    if selected:  # Package the objectively selected clean completed-state research baseline.
        best = args.output / "best"  # Define the direct-use selected-model package directory.
        best.mkdir(exist_ok=True)  # Create the selected-model package directory.
        source_dir = args.output / selected["trialDir"]  # Resolve the selected trial's isolated CalculiX directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve input, field results and convergence evidence together.
            source_path = source_dir / f"{selected['stem']}.{suffix}"  # Resolve one selected numerical artifact by deterministic stem.
            if source_path.exists():  # Copy only artifacts actually emitted by CalculiX.
                shutil.copy2(source_path, best / source_path.name)  # Preserve the selected numerical bytes and metadata.
        (best / "selection.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")  # Place the final selection metrics beside the accepted model.
    print(json.dumps({"status": summary["status"], "selected": selected, "trials": [{"scale": row["scale"], "cleanConvergence": row["cleanConvergence"], "midspanU3Mm": row["midspanU3Mm"], "rmsCenterlineU3Mm": row["rmsCenterlineU3Mm"]} for row in rows]}, ensure_ascii=False, indent=2))  # Surface the decisive form-finding comparison in the Actions log.
    return 0 if selected else 2  # Pass CI only after at least one clean direct form-finding completed equilibrium exists.
if __name__ == "__main__":  # Execute the calibration only when this file is invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the direct form-finding qualification status to GitHub Actions.
