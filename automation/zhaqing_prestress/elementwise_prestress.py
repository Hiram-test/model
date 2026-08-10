#!/usr/bin/env python3  # Execute the element-wise prestress calibration with the workflow Python interpreter.
import argparse  # Parse deterministic command-line paths and the CalculiX executable.
import csv  # Persist a compact scalar comparison table for every prestress scale.
import json  # Persist the complete auditable calibration receipt.
import math  # Evaluate cable segment lengths and completed-geometry RMS error metrics.
import re  # Replace only the targeted cable/hanger section cards and parse solver residuals.
import shutil  # Package the objectively selected converged input and result files.
from pathlib import Path  # Use explicit platform-independent filesystem paths.
import prestress_isolation as core  # Reuse the already audited L2 topology parser and CalculiX result parser.

SCALES = (0.80, 0.90, 1.00, 1.10, 1.20)  # Probe tightly around the mechanics-based scale-one target indicated by the earlier L3 residual minimum.
MAIN_E_MPA = 195000.0  # Preserve the verified PR9 L2 main-cable elastic modulus.
HANGER_E_MPA = 200000.0  # Preserve the verified PR9 L2 hanger elastic modulus.
MAIN_SIDE_MM = 74.5432224  # Preserve the verified PR9 L2 equal-area square main-cable section side.
MAIN_AREA_MM2 = MAIN_SIDE_MM * MAIN_SIDE_MM  # Compute the main-cable section area from the frozen L2 section.
HANGER_AREA_MM2 = 804.247719  # Preserve the verified PR9 L2 hanger section area.
SPAN_MM = 82000.0  # Preserve the frozen main-span tower spacing.


def tributary_lengths(stations: list[float]) -> dict[float, float]:  # Compute boundary-aware tributary lengths for the 25 hanger stations.
    supports = [0.0, *stations, SPAN_MM]  # Include the two deck end supports when partitioning permanent load.
    result: dict[float, float] = {}  # Store one tributary length for each hanger station.
    for index, station in enumerate(stations, 1):  # Visit the hanger supports in increasing longitudinal order.
        result[station] = 0.5 * (supports[index + 1] - supports[index - 1])  # Assign half of each adjacent support interval to the hanger.
    return result  # Return 4 m at the two edge hangers and 3 m at interior hangers.


def elementwise_items(text: str) -> tuple[list[dict], list[int], list[int], int, dict]:  # Derive self-consistent segment and hanger target forces on the unchanged L2 topology.
    nodes, groups = core.parse_topology(text)  # Parse original coordinates and element connectivity without changing any mesh entity.
    basis = core.prestress_basis()  # Reuse the transparent permanent-load horizontal-force target derived from the L2 masses.
    horizontal_n = float(basis["mainCableHorizontalForceTargetN"])  # Freeze the parabolic main-span horizontal cable-force component.
    one_line_load = float(basis["oneCableLineLoadNPerMm"])  # Freeze the permanent vertical line load carried by one cable plane.
    items: list[dict] = []  # Collect one unique prestress material/section assignment per line element.
    pretension_nodes: set[int] = set()  # Collect only nodes belonging to main cables or vertical hangers.
    for eid, conn in groups["MAIN_CABLES"]:  # Process every original B31 main-cable segment individually.
        n1, n2 = conn[:2]  # Read the two original cable segment endpoint node labels.
        p1 = nodes[n1]  # Recover the first endpoint coordinate from the frozen L2 model.
        p2 = nodes[n2]  # Recover the second endpoint coordinate from the frozen L2 model.
        dx = abs(p2[0] - p1[0])  # Compute the horizontal longitudinal projection of the cable segment.
        length = math.dist(p1, p2)  # Compute the actual three-dimensional cable segment length.
        if dx <= 1.0e-9:  # Reject a vertical main-cable segment because the constant-horizontal-force construction would be undefined.
            raise RuntimeError(f"main cable element {eid} has zero longitudinal projection")  # Fail explicitly rather than inventing a segment force.
        target_force_n = horizontal_n * length / dx  # Enforce the same horizontal component H while allowing tension magnitude to vary with cable slope.
        target_stress_mpa = target_force_n / MAIN_AREA_MM2  # Convert the segment target tension to an axial stress.
        alpha_per_c = target_stress_mpa / MAIN_E_MPA  # Convert the axial stress to a unit-temperature contraction coefficient proxy.
        items.append({"elementId": eid, "kind": "MAIN_CABLE", "targetForceNAtScale1": target_force_n, "targetStressMPaAtScale1": target_stress_mpa, "thermalExpansionPerC": alpha_per_c, "areaMm2": MAIN_AREA_MM2})  # Preserve every segment target for audit and generation.
        pretension_nodes.update((n1, n2))  # Apply temperature only at nodes touched by prestressed suspension elements.
    hanger_records = groups["HANGERS"]  # Recover the 50 original T3D2 hanger elements from the verified L2 deck.
    hanger_stations = sorted({round(nodes[conn[0]][0], 9) for _eid, conn in hanger_records})  # Recover the 25 unique longitudinal hanger stations directly from model coordinates.
    tributaries = tributary_lengths(hanger_stations)  # Compute 4 m edge and 3 m interior permanent-load tributary lengths.
    for eid, conn in hanger_records:  # Process every original hanger independently while preserving its connectivity.
        n1, n2 = conn[:2]  # Read the two original hanger endpoint node labels.
        station = round(nodes[n1][0], 9)  # Recover the hanger longitudinal station from its unchanged bottom endpoint.
        target_force_n = one_line_load * tributaries[station]  # Assign the vertical permanent load belonging to this hanger's tributary strip.
        target_stress_mpa = target_force_n / HANGER_AREA_MM2  # Convert the target hanger force to axial stress.
        alpha_per_c = target_stress_mpa / HANGER_E_MPA  # Convert the axial stress to a unit-temperature contraction coefficient proxy.
        items.append({"elementId": eid, "kind": "HANGER", "targetForceNAtScale1": target_force_n, "targetStressMPaAtScale1": target_stress_mpa, "thermalExpansionPerC": alpha_per_c, "areaMm2": HANGER_AREA_MM2, "tributaryLengthMm": tributaries[station]})  # Preserve the boundary-aware hanger target for audit and generation.
        pretension_nodes.update((n1, n2))  # Include both hanger endpoints in the common temperature field.
    calibration_nodes = sorted(node for node, (x, y, z) in nodes.items() if 0.0 < x < SPAN_MM and abs(y) < 1.0e-9 and abs(z) < 1.0e-9)  # Use unchanged interior deck-centerline nodes to measure completed-geometry drift.
    midspan_node = min(calibration_nodes, key=lambda node: abs(nodes[node][0] - SPAN_MM / 2.0))  # Identify the original centerline node closest to geometric midspan.
    metadata = {"basis": basis, "mainCableElementCount": len(groups["MAIN_CABLES"]), "hangerElementCount": len(hanger_records), "hangerStationsMm": hanger_stations, "hangerTributaryLengthsMm": {str(key): value for key, value in tributaries.items()}, "pretensionNodeCount": len(pretension_nodes), "calibrationNodeCount": len(calibration_nodes), "midspanNode": midspan_node}  # Record the complete force-construction basis independently of any solver result.
    return items, sorted(pretension_nodes), calibration_nodes, midspan_node, metadata  # Return immutable generation data for every trial scale.


def assignment_block(items: list[dict]) -> str:  # Generate unique material and section assignments while retaining the original cable/hanger element groups.
    lines: list[str] = []  # Accumulate deterministic ASCII keyword lines.
    for index, item in enumerate(items, 1):  # Assign one material and one section property to every prestressed line element.
        eset = f"ZQP_{index:04d}"  # Build a compact unique element-set name accepted by CalculiX.
        material = f"ZQM_{index:04d}"  # Build a compact unique material name accepted by CalculiX.
        lines.append(f"*ELSET, ELSET={eset}")  # Define an additional one-element set without altering the broad MAIN_CABLES/HANGERS sets.
        lines.append(str(item["elementId"]))  # Put the original element label into the unique assignment set.
        lines.append(f"*MATERIAL, NAME={material}")  # Define the element-specific elastic/thermal material.
        lines.append("*ELASTIC")  # Preserve linear elastic constitutive behavior for this screening model.
        if item["kind"] == "MAIN_CABLE":  # Use the verified main-cable modulus and density for cable segments.
            lines.append("195000., 0.30")  # Preserve the original cable Young modulus and Poisson ratio.
            lines.append("*DENSITY")  # Preserve cable self-weight under the existing gravity load.
            lines.append("7.85e-9")  # Preserve the original steel density in N-mm-tonne-s units.
        else:  # Use the verified hanger modulus and density for vertical hanger elements.
            lines.append("200000., 0.30")  # Preserve the original hanger Young modulus and Poisson ratio.
            lines.append("*DENSITY")  # Preserve hanger self-weight under the existing gravity load.
            lines.append("7.85e-9")  # Preserve the original hanger steel density in N-mm-tonne-s units.
        lines.append("*EXPANSION, ZERO=0.")  # Represent missing unstressed length by a transparent thermal-prestrain proxy.
        lines.append(f"{item['thermalExpansionPerC']:.12g}")  # Store the scale-one element-specific contraction coefficient.
        if item["kind"] == "MAIN_CABLE":  # Reassign the unchanged B31 main-cable section using the unique material.
            lines.append(f"*BEAM SECTION, ELSET={eset}, MATERIAL={material}, SECTION=RECT")  # Preserve the original equal-area rectangular B31 representation.
            lines.append(f"{MAIN_SIDE_MM:.10g}, {MAIN_SIDE_MM:.10g}")  # Preserve the exact L2 cable section dimensions.
            lines.append("0., 1., 0.")  # Preserve the original B31 section orientation vector.
        else:  # Reassign the unchanged T3D2 hanger section using the unique material.
            lines.append(f"*SOLID SECTION, ELSET={eset}, MATERIAL={material}")  # Preserve the original truss solid-section representation.
            lines.append(f"{HANGER_AREA_MM2:.12g}")  # Preserve the exact verified L2 hanger area.
    return "\n".join(lines) + "\n"  # Return one complete model-definition block with deterministic line endings.


def patch_model(text: str, items: list[dict], pretension_nodes: list[int], calibration_nodes: list[int], scale: float) -> str:  # Add element-wise prestress while freezing all other L2 modeling choices.
    patched = text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge L2 elementwise prestress equilibrium - scale {scale:.6g}", 1)  # Relabel the isolated trial for provenance.
    patched = patched.replace("** No calibrated fabrication-state cable prestress is included.", "** Element-wise main-cable and hanger prestress proxy added; all other verified PR9 L2 model choices retained.", 1)  # Record the sole modeling intervention in the deck header.
    patched = re.sub(r"\*BEAM SECTION, ELSET=MAIN_CABLES[^\n]*\n[^\n]*\n[^\n]*\n", "", patched, count=1, flags=re.I)  # Remove only the broad main-cable section assignment so unique assignments cannot conflict.
    patched = re.sub(r"\*SOLID SECTION, ELSET=HANGERS[^\n]*\n[^\n]*\n", "", patched, count=1, flags=re.I)  # Remove only the broad hanger section assignment so unique assignments cannot conflict.
    unique_properties = assignment_block(items)  # Generate segment-specific cable tension and hanger-force proxies.
    wind_marker = "*SOLID SECTION, ELSET=WIND_CABLES, MATERIAL=WIND_ROPE_SCREEN\n"  # Use the unchanged wind-cable section as an insertion anchor.
    if wind_marker not in patched:  # Require the exact verified L2 section marker before patching.
        raise RuntimeError("verified L2 wind-cable section marker not found")  # Stop rather than silently changing an incompatible model.
    patched = patched.replace(wind_marker, unique_properties + wind_marker, 1)  # Insert unique cable/hanger properties without changing wind-cable assumptions.
    added_sets = core.write_nset("PRETENSION_NODES", pretension_nodes) + core.write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Build the shared thermal node set and completed-geometry observation set.
    patched = patched.replace("** MATERIALS\n", added_sets + "** MATERIALS\n", 1)  # Insert only the two additional node sets into the model definition.
    prefix, old_step = patched.split("*STEP\n", 1)  # Separate the frozen model definition from the original verified linear dead-load step.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve every original gravity load, nodal permanent load and result request verbatim.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add centerline geometry output without removing the original monitor output.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n"  # Define the unstressed thermal reference before the equilibrium step.
    step = f"*STEP, NLGEOM=YES, INC=500\n*STATIC\n0.001, 1.0, 1.E-6, 0.01\n*TEMPERATURE\nPRETENSION_NODES, {-scale:.12g}\n" + dead_tail  # Ramp element-wise cable/hanger contraction and unchanged permanent loads together to the completed state.
    return prefix + initial + step  # Return the complete CalculiX input deck for this scale.


def final_residual(log_tail: list[str]) -> tuple[float | None, float | None, int | None, int | None]:  # Recover the final CalculiX force residual even from a nonconverged trial.
    text = "\n".join(log_tail)  # Join the retained solver log tail for regular-expression parsing.
    residuals = re.findall(r"largest residual force=\s*([0-9.eE+\-]+) in node\s+(\d+) and dof\s+(\d+)", text)  # Locate all retained residual reports.
    averages = re.findall(r"average force=\s*([0-9.eE+\-]+)", text)  # Locate all retained average-force reports.
    if not residuals:  # Handle syntax or solver failures before Newton residual reporting.
        return None, float(averages[-1]) if averages else None, None, None  # Preserve any available average force and return no residual location.
    value, node, dof = residuals[-1]  # Use the final reported Newton residual after all cutbacks.
    return float(value), float(averages[-1]) if averages else None, int(node), int(dof)  # Return scalar magnitude, force scale and solver location.


def main() -> int:  # Execute the element-wise equilibrium calibration against the verified L2 artifact.
    parser = argparse.ArgumentParser()  # Build a minimal deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the verified PR9 L2 LC01 input deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated output root for all scales and receipts.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable resolved by the workflow.
    args = parser.parse_args()  # Parse all required inputs before modifying or solving any model.
    text = args.base.read_text(encoding="ascii")  # Read the verified ASCII baseline deck without normalization.
    items, pretension_nodes, calibration_nodes, midspan_node, metadata = elementwise_items(text)  # Build the self-consistent discrete cable/hanger force field once.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the auditable output root before launching CalculiX.
    rows: list[dict] = []  # Accumulate convergence, residual and completed-geometry metrics across the bounded scale sweep.
    for scale in SCALES:  # Probe the narrow neighborhood around the mechanics-based nominal target.
        inp_text = patch_model(text, items, pretension_nodes, calibration_nodes, scale)  # Generate one model differing from L2 only through element-wise prestress and NLGEOM.
        stem = f"ZQ_L2PE_S{int(round(scale * 100)):03d}"  # Build a deterministic short case identifier.
        trial_dir = args.output / "trials" / f"scale_{scale:.2f}".replace(".", "p")  # Isolate every CalculiX run so failed cases cannot contaminate later cases.
        outcome = core.solve_trial(args.ccx, trial_dir, inp_text, stem, midspan_node)  # Execute the nonlinear equilibrium and parse final centerline displacement when converged.
        residual_n, average_n, residual_node, residual_dof = final_residual(outcome["logTail"])  # Preserve force-balance information even when the default gate rejects the step.
        rows.append({"scale": scale, "stem": stem, "trialDir": str(trial_dir.relative_to(args.output)), "finalResidualN": residual_n, "finalAverageForceN": average_n, "residualNode": residual_node, "residualDof": residual_dof, **outcome})  # Record all solver evidence needed for selection and diagnosis.
    converged = [row for row in rows if row["cleanConvergence"] and row["rmsCenterlineU3Mm"] is not None]  # Keep only clean nonlinear completed states for geometry-based selection.
    selected = min(converged, key=lambda row: row["rmsCenterlineU3Mm"]) if converged else None  # Select the converged prestress scale requiring the least completed-geometry correction.
    residual_candidates = [row for row in rows if row["finalResidualN"] is not None]  # Retain nonconverged cases for objective residual diagnosis.
    best_residual = min(residual_candidates, key=lambda row: row["finalResidualN"]) if residual_candidates else None  # Identify the scale closest to discrete equilibrium even if CalculiX default convergence rejects it.
    summary = {"schemaVersion": "2.0.0-elementwise-prestress-isolation", "status": "PASS" if selected else "FAIL", "baseModel": str(args.base), "intervention": "Verified PR9 L2 topology, mesh, sections, supports and permanent loads frozen; only element-wise main-cable/hanger prestress proxy plus NLGEOM added.", "metadata": metadata, "prestressItems": items, "trials": rows, "selected": selected, "bestResidual": best_residual, "selectionObjective": "minimum final RMS U3 on the unchanged interior deck centerline among clean converged trials", "engineeringRelease": "BLOCKED pending accepted unstressed lengths or measured erection/finished-state cable forces."}  # Assemble the complete evidence receipt before any CI gate.
    (args.output / "elementwise_prestress_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the complete force construction and nonlinear trial evidence.
    with (args.output / "elementwise_prestress_trials.csv").open("w", encoding="utf-8-sig", newline="") as stream:  # Create a compact spreadsheet-friendly trial table.
        fields = ["scale", "cleanConvergence", "exitCode", "finalResidualN", "finalAverageForceN", "residualNode", "residualDof", "rmsCenterlineU3Mm", "maxAbsCenterlineU3Mm", "midspanU3Mm", "datBytes", "frdBytes", "stem", "trialDir"]  # Freeze stable scalar CSV columns.
        writer = csv.DictWriter(stream, fieldnames=fields)  # Create a deterministic dictionary writer.
        writer.writeheader()  # Emit the explicit trial-table schema.
        for row in rows:  # Serialize every scale regardless of convergence outcome.
            writer.writerow({field: row.get(field) for field in fields})  # Exclude nested log tails from the compact comparison table.
    if selected:  # Package the best clean completed equilibrium for direct downstream use.
        best_dir = args.output / "best"  # Define the selected-model package location.
        best_dir.mkdir(exist_ok=True)  # Create the selected-model package directory.
        source_dir = args.output / selected["trialDir"]  # Resolve the selected trial's isolated solver directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve input, field output and convergence evidence together.
            source = source_dir / f"{selected['stem']}.{suffix}"  # Resolve one selected artifact by deterministic stem.
            if source.exists():  # Copy only files actually created by CalculiX.
                shutil.copy2(source, best_dir / source.name)  # Preserve the original numerical artifact bytes and timestamps.
        (best_dir / "selection.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the exact selection metrics next to the accepted deck.
    print(json.dumps({"status": summary["status"], "selected": selected, "bestResidual": best_residual}, ensure_ascii=False, indent=2))  # Surface the decisive calibration result in the workflow log.
    return 0 if selected else 2  # Pass CI only after a clean positive element-wise prestressed nonlinear equilibrium exists.


if __name__ == "__main__":  # Execute the calibration only when this file is invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the evidence gate status to GitHub Actions.
