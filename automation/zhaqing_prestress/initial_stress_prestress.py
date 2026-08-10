#!/usr/bin/env python3  # Execute direct initial-stress prestress calibration on the verified PR9 L2 bridge.
import argparse  # Parse deterministic baseline, output and CalculiX executable inputs.
import csv  # Persist a compact scale-comparison table for the nonlinear trials.
import json  # Persist the complete prestress construction and numerical qualification receipt.
import math  # Build axial global stress tensors and completed-geometry RMS metrics.
import shutil  # Package the objectively selected converged research-baseline model and results.
from pathlib import Path  # Use explicit platform-independent filesystem paths throughout.
import elementwise_prestress as force_model  # Reuse the audited segment-wise main-cable and hanger target-force construction.
import prestress_isolation as core  # Reuse the audited verified-L2 topology parser and CalculiX result parser.

SCALES = (0.90, 1.00, 1.10, 1.18, 1.25)  # Probe a bounded neighborhood around the mechanics and residual-calibrated prestress levels.
SPAN_MM = 82000.0  # Preserve the frozen PR9 main-span tower spacing used by the geometry objective.


def axial_stress_tensor(stress_mpa: float, p1: tuple[float, float, float], p2: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:  # Convert one tensile axial stress into the global second-order tensor required by CalculiX.
    direction = tuple(p2[index] - p1[index] for index in range(3))  # Build the element chord vector from the unchanged original coordinates.
    length = math.sqrt(sum(value * value for value in direction))  # Compute the three-dimensional chord length.
    if length <= 0.0:  # Reject degenerate line elements explicitly.
        raise RuntimeError("zero-length prestressed line element")  # Prevent undefined direction cosines from entering the input deck.
    nx, ny, nz = (value / length for value in direction)  # Normalize the chord into global direction cosines.
    return (stress_mpa * nx * nx, stress_mpa * ny * ny, stress_mpa * nz * nz, stress_mpa * nx * ny, stress_mpa * nx * nz, stress_mpa * ny * nz)  # Return sigma times the dyadic product n tensor n in CalculiX xx,yy,zz,xy,xz,yz order.


def initial_stress_block(base_text: str, scale: float) -> tuple[str, int, dict]:  # Build a direct prestress field without thermal expansion or section-property changes.
    nodes, groups = core.parse_topology(base_text)  # Recover the immutable verified-L2 coordinates and line-element connectivity.
    items, _pretension_nodes, calibration_nodes, midspan_node, metadata = force_model.elementwise_items(base_text)  # Reuse the audited target tension for all 196 cable and 50 hanger elements.
    item_by_element = {int(item["elementId"]): item for item in items}  # Index prestress targets by original element label for deterministic stress generation.
    lines = ["*INITIAL CONDITIONS, TYPE=STRESS"]  # Start one native CalculiX initial-stress model-definition block.
    stress_audit: list[dict] = []  # Preserve every tensor written to the solver deck for independent review.
    for group_name in ("MAIN_CABLES", "HANGERS"):  # Apply direct initial stress only to the vertical suspension system requested for this isolation study.
        for element_id, connectivity in groups[group_name]:  # Visit every unchanged main-cable and hanger line element exactly once.
            item = item_by_element[element_id]  # Recover the element's mechanics-derived scale-one axial tension target.
            p1 = nodes[connectivity[0]]  # Recover the first original endpoint coordinate.
            p2 = nodes[connectivity[1]]  # Recover the second original endpoint coordinate.
            axial_stress = float(item["targetStressMPaAtScale1"]) * scale  # Scale the element-specific tensile stress without changing material or geometry.
            tensor = axial_stress_tensor(axial_stress, p1, p2)  # Express the axial prestress as a global Cartesian stress tensor.
            lines.append(f"{element_id}, 1, " + ", ".join(f"{value:.12g}" for value in tensor))  # Assign the stress at integration point one using the native CalculiX initial-stress syntax.
            stress_audit.append({"elementId": element_id, "group": group_name, "scale": scale, "axialStressMPa": axial_stress, "tensorGlobalMPa": tensor, "targetForceN": float(item["targetForceNAtScale1"]) * scale})  # Record the physical target and exact global tensor independently of solver output.
    calibration_set = core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Define unchanged deck-centerline nodes used to measure completed-geometry drift.
    patched = base_text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge L2 direct initial-stress equilibrium - scale {scale:.6g}", 1)  # Relabel the isolated trial for provenance.
    patched = patched.replace("** No calibrated fabrication-state cable prestress is included.", "** Direct element-wise initial stress is assigned to main cables and hangers; all other verified PR9 L2 model choices remain unchanged.", 1)  # Record the sole physical intervention in the input header.
    patched = patched.replace("** MATERIALS\n", calibration_set + "** MATERIALS\n", 1)  # Insert only the geometry-observation node set into the model definition.
    prefix, old_step = patched.split("*STEP\n", 1)  # Separate the verified L2 model definition from its original linear dead-load step.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve the original gravity, nodal permanent loads and result requests verbatim.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add the completed-geometry observation output without removing existing monitor output.
    step = "*STEP, NLGEOM=YES, AMPLITUDE=STEP, INC=500\n*STATIC\n0.1, 1.0, 1.E-8, 1.0\n" + dead_tail  # Apply the complete permanent load from the first equilibrium state so it can balance the fully present initial stress field.
    deck = prefix + "\n".join(lines) + "\n" + step  # Assemble the native initial-stress model and nonlinear completed-state equilibrium step.
    audit = {"scale": scale, "metadata": metadata, "stressAssignments": stress_audit, "initialStressAssignmentCount": len(stress_audit), "loading": "STEP amplitude so full permanent load is present from the first nonlinear equilibrium iteration", "temperaturePrestressUsed": False, "sectionPropertiesChanged": False}  # Record every modeling choice required to interpret the trial.
    return deck, midspan_node, audit  # Return the complete CalculiX deck and immutable prestress audit metadata.


def main() -> int:  # Execute the bounded direct initial-stress scale sweep and package the best clean completed state.
    parser = argparse.ArgumentParser()  # Build a minimal deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the successful verified PR9 L2 dead-load input deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated output root for all scale trials and receipts.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable resolved by the workflow.
    args = parser.parse_args()  # Parse all required inputs before generating or solving any model.
    base_text = args.base.read_text(encoding="ascii")  # Read the verified baseline deck exactly once as ASCII.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before launching any solver process.
    rows: list[dict] = []  # Accumulate solver and completed-geometry metrics across all direct-stress scales.
    audits: dict[str, dict] = {}  # Preserve the exact initial-stress field generated for every trial scale.
    for scale in SCALES:  # Probe the bounded direct-prestress scale family.
        deck, midspan_node, audit = initial_stress_block(base_text, scale)  # Generate one native initial-stress bridge model without thermal strains.
        audits[f"{scale:.2f}"] = audit  # Persist the exact stress construction independently of convergence outcome.
        stem = f"ZQ_L2IS_S{int(round(scale * 100)):03d}"  # Build a deterministic short solver case identifier.
        trial_dir = args.output / "trials" / f"scale_{scale:.2f}".replace(".", "p")  # Isolate every solver run so failed trials cannot contaminate later scales.
        outcome = core.solve_trial(args.ccx, trial_dir, deck, stem, midspan_node)  # Execute the nonlinear completed-state equilibrium and parse centerline displacement output.
        rows.append({"scale": scale, "stem": stem, "trialDir": str(trial_dir.relative_to(args.output)), **outcome})  # Record convergence, displacement and output-file evidence for this scale.
    converged = [row for row in rows if row["cleanConvergence"] and row["rmsCenterlineU3Mm"] is not None]  # Keep only clean completed nonlinear states with an observable geometry objective.
    selected = min(converged, key=lambda row: row["rmsCenterlineU3Mm"]) if converged else None  # Select the converged scale that requires the least movement from the frozen completed bridge geometry.
    summary = {"schemaVersion": "4.0.0-direct-initial-stress", "status": "PASS" if selected else "FAIL", "baseModel": str(args.base), "intervention": "Only direct native initial stress on original MAIN_CABLES and HANGERS plus NLGEOM; verified PR9 L2 topology, mesh, sections, supports and permanent loads remain frozen.", "trials": rows, "selected": selected, "audits": audits, "selectionObjective": "minimum final RMS U3 over unchanged interior deck-centerline nodes among clean converged direct-initial-stress trials", "engineeringRelease": "BLOCKED pending accepted unstressed cable lengths or measured erection/finished-state cable forces; a PASS qualifies only the numerical research baseline."}  # Assemble the complete qualification receipt before any CI gate.
    (args.output / "direct_initial_stress_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the complete direct-prestress evidence and selection decision.
    with (args.output / "direct_initial_stress_trials.csv").open("w", encoding="utf-8-sig", newline="") as stream:  # Create a compact spreadsheet-friendly scale comparison.
        fields = ["scale", "cleanConvergence", "exitCode", "rmsCenterlineU3Mm", "maxAbsCenterlineU3Mm", "midspanU3Mm", "datBytes", "frdBytes", "stem", "trialDir"]  # Freeze stable scalar CSV columns.
        writer = csv.DictWriter(stream, fieldnames=fields)  # Create the deterministic row writer.
        writer.writeheader()  # Emit the explicit table schema.
        for row in rows:  # Serialize every trial regardless of convergence status.
            writer.writerow({field: row.get(field) for field in fields})  # Exclude nested solver log tails from the compact table.
    if selected:  # Package the objectively selected clean direct-prestress research baseline.
        best = args.output / "best"  # Define the direct-use selected-model package directory.
        best.mkdir(exist_ok=True)  # Create the selected-model package directory.
        source_dir = args.output / selected["trialDir"]  # Resolve the selected trial's isolated CalculiX directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve input, field results and convergence evidence together.
            source = source_dir / f"{selected['stem']}.{suffix}"  # Resolve one selected numerical artifact.
            if source.exists():  # Copy only artifacts actually emitted by CalculiX.
                shutil.copy2(source, best / source.name)  # Preserve the selected numerical bytes and metadata.
        (best / "selection.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")  # Place the final selection metrics next to the accepted model.
    print(json.dumps({"status": summary["status"], "selected": selected, "trials": [{"scale": row["scale"], "cleanConvergence": row["cleanConvergence"], "midspanU3Mm": row["midspanU3Mm"], "rmsCenterlineU3Mm": row["rmsCenterlineU3Mm"]} for row in rows]}, ensure_ascii=False, indent=2))  # Surface the decisive scale comparison in the workflow log.
    return 0 if selected else 2  # Pass CI only after at least one clean direct-initial-stress completed equilibrium exists.


if __name__ == "__main__":  # Execute the calibration only when this file is invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the direct-prestress qualification status to GitHub Actions.
