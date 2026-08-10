#!/usr/bin/env python3  # Use the workflow Python interpreter.
import argparse  # Parse deterministic command-line inputs.
import csv  # Write a compact machine-readable trial table.
import json  # Write the complete calibration receipt.
import math  # Evaluate RMS displacement objectives.
import re  # Parse Abaqus/CalculiX keyword text safely.
import shutil  # Copy the selected model and solver results.
import subprocess  # Invoke CalculiX synchronously for every trial.
from pathlib import Path  # Use explicit filesystem paths throughout.

SPAN_MM = 82000.0  # Main-span length frozen by the PR9 bridge contract.
SAG_MM = 8200.0  # Main-cable tower-to-midspan sag frozen by the PR9 geometry.
GRAVITY_MM_S2 = 9810.0  # Gravity in the model N-mm-tonne-s unit system.
STEEL_DENSITY_T_MM3 = 7.85e-9  # Steel density used by the verified L2 input deck.
LONG_GIRDER_AREA_MM2 = 604.64126 * 35.4821965  # Equivalent longitudinal-girder area from the L2 deck.
CROSSBEAM_AREA_MM2 = 420.0 * 41.4123032  # Equivalent crossbeam area from the L2 deck.
DECK_PANEL_MASS_T = 60.41334  # Verified deck-panel mass closure from the L2 artifact.
DECK_ACCESSORY_MASS_T = 6.041334  # Verified deck-accessory mass allowance from the L2 artifact.
MAIN_CABLE_AREA_MM2 = 74.5432224 * 74.5432224  # Equal-area main-cable section used by the L2 input deck.
HANGER_AREA_MM2 = 804.247719  # Hanger area used by the L2 input deck.
MAIN_CABLE_E_MPA = 195000.0  # Main-cable elastic modulus used by the L2 input deck.
HANGER_E_MPA = 200000.0  # Hanger elastic modulus used by the L2 input deck.
TRIAL_SCALES = (0.0, 0.50, 0.75, 1.00, 1.25, 1.50)  # Bounded global prestress factors for isolation calibration.
STRATEGIES = ("simultaneous", "prestress_first")  # Two conservative load paths ending at the same final state.


def prestress_basis() -> dict:  # Derive first-order suspension-system force targets from the frozen L2 model.
    girder_mass_t = 2.0 * SPAN_MM * LONG_GIRDER_AREA_MM2 * STEEL_DENSITY_T_MM3  # Compute two-girder permanent mass.
    crossbeam_mass_t = 27.0 * 5500.0 * CROSSBEAM_AREA_MM2 * STEEL_DENSITY_T_MM3  # Compute 27 full-width crossbeam masses.
    suspended_mass_t = girder_mass_t + crossbeam_mass_t + DECK_PANEL_MASS_T + DECK_ACCESSORY_MASS_T  # Sum suspended permanent mass only.
    permanent_weight_n = suspended_mass_t * GRAVITY_MM_S2  # Convert the suspended permanent mass to weight.
    one_cable_line_load_n_per_mm = permanent_weight_n / SPAN_MM / 2.0  # Split vertical permanent line load between two cable planes.
    horizontal_force_n = one_cable_line_load_n_per_mm * SPAN_MM * SPAN_MM / (8.0 * SAG_MM)  # Apply H=wL^2/(8f) to the main span.
    main_alpha = horizontal_force_n / MAIN_CABLE_AREA_MM2 / MAIN_CABLE_E_MPA  # Convert horizontal-force stress to a unit-temperature contraction proxy.
    hanger_interior_force_n = one_cable_line_load_n_per_mm * 3000.0  # Use the 3 m interior hanger tributary length.
    hanger_alpha = hanger_interior_force_n / HANGER_AREA_MM2 / HANGER_E_MPA  # Convert representative hanger stress to contraction proxy.
    return {"suspendedMassTonne": suspended_mass_t, "permanentWeightN": permanent_weight_n, "oneCableLineLoadNPerMm": one_cable_line_load_n_per_mm, "mainCableHorizontalForceTargetN": horizontal_force_n, "mainCableExpansionPerC": main_alpha, "hangerInteriorForceTargetN": hanger_interior_force_n, "hangerExpansionPerC": hanger_alpha}  # Return the auditable target basis.


def parse_topology(text: str) -> tuple[dict[int, tuple[float, float, float]], dict[str, list[tuple[int, list[int]]]]]:  # Read nodes and element groups from the existing INP.
    nodes: dict[int, tuple[float, float, float]] = {}  # Store original nodal coordinates without modification.
    groups: dict[str, list[tuple[int, list[int]]]] = {}  # Store element connectivity keyed by ELSET.
    in_nodes = False  # Track whether the parser is inside the node block.
    active_group: str | None = None  # Track the current element ELSET.
    for raw in text.splitlines():  # Scan the deck once in source order.
        line = raw.strip()  # Normalize surrounding whitespace only.
        if re.match(r"^\*NODE(?:,|\s|$)", line, re.I) and not re.match(r"^\*NODE\s+(PRINT|FILE)", line, re.I):  # Detect the model node keyword only.
            in_nodes = True  # Enter node parsing mode.
            active_group = None  # Leave any previous element block.
            continue  # Advance to the first node record.
        if line.upper().startswith("*ELEMENT"):  # Detect a new element block.
            in_nodes = False  # Leave node parsing mode.
            match = re.search(r"ELSET=([^,\s]+)", line, re.I)  # Extract the element-set name.
            active_group = match.group(1).upper() if match else ""  # Normalize the set name for lookup.
            groups.setdefault(active_group, [])  # Ensure the group has a deterministic list.
            continue  # Advance to element records.
        if line.startswith("*"):  # Detect every other keyword boundary.
            in_nodes = False  # Leave node parsing mode at keyword boundaries.
            active_group = None  # Leave element parsing mode at keyword boundaries.
            continue  # Advance to data under the new keyword.
        if in_nodes and line and not line.startswith("**"):  # Parse a node data record.
            fields = [value.strip() for value in line.split(",")]  # Split comma-separated values.
            if len(fields) >= 4 and fields[0].isdigit():  # Guard against malformed or non-node text.
                nodes[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Preserve the original node coordinate.
            continue  # Finish this node record.
        if active_group and line and not line.startswith("**"):  # Parse an element data record.
            fields = [value.strip() for value in line.split(",") if value.strip()]  # Remove empty comma fields.
            if fields and fields[0].isdigit():  # Guard against malformed or non-element text.
                groups[active_group].append((int(fields[0]), [int(value) for value in fields[1:]]))  # Preserve element id and connectivity.
    return nodes, groups  # Return the frozen topology for node-set construction.


def write_nset(name: str, node_ids: list[int]) -> str:  # Serialize a CalculiX node set without long input lines.
    rows = [node_ids[index:index + 16] for index in range(0, len(node_ids), 16)]  # Limit each row to sixteen node ids.
    body = "\n".join(", ".join(str(node) for node in row) for row in rows)  # Serialize deterministic comma-separated rows.
    return f"*NSET, NSET={name}\n{body}\n"  # Return a complete model-definition node set.


def prepare_prefix(text: str, scale: float) -> tuple[str, str, int, dict]:  # Add only the prestress model definitions while preserving the L2 mesh.
    basis = prestress_basis()  # Compute the transparent first-order force basis.
    nodes, groups = parse_topology(text)  # Read the immutable L2 topology.
    pretension_nodes = sorted({node for group in ("MAIN_CABLES", "HANGERS") for _eid, conn in groups[group] for node in conn})  # Collect vertical suspension-system nodes only.
    calibration_nodes = sorted(node for node, (x, y, z) in nodes.items() if 0.0 < x < SPAN_MM and abs(y) < 1.0e-9 and abs(z) < 1.0e-9)  # Use interior deck-centerline nodes as the completed-geometry objective.
    midspan_node = min(calibration_nodes, key=lambda node: abs(nodes[node][0] - SPAN_MM / 2.0))  # Identify the original midspan centerline node.
    sets = write_nset("PRETENSION_NODES", pretension_nodes) + write_nset("PRESTRESS_CALIBRATION", calibration_nodes)  # Build the two added node sets.
    patched = text.replace("Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD", f"Zhaqing suspension bridge L2 prestress-isolation trial - scale {scale:.6g}", 1)  # Relabel the trial without changing topology.
    patched = patched.replace("** No calibrated fabrication-state cable prestress is included.", "** Prestress isolation: original PR9 L2 topology, sections, offsets, supports and permanent loads retained.", 1)  # Record the isolated intervention.
    patched = patched.replace("** MATERIALS\n", sets + "** MATERIALS\n", 1)  # Insert node sets before material definitions.
    main_material = "*MATERIAL, NAME=MAIN_CABLE_WIRE_SCREEN\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n"  # Match the original main-cable material block exactly.
    main_material_new = main_material + f"*EXPANSION, ZERO=0.\n{basis['mainCableExpansionPerC']:.12g}\n"  # Add main-cable contraction without changing elastic constants.
    patched = patched.replace(main_material, main_material_new, 1)  # Apply the main-cable thermal-prestrain proxy once.
    hanger_material = "*MATERIAL, NAME=HANGER_BAR_SCREEN\n*ELASTIC\n200000., 0.30\n*DENSITY\n7.85e-9\n"  # Match the original hanger material block exactly.
    hanger_material_new = hanger_material + f"*EXPANSION, ZERO=0.\n{basis['hangerExpansionPerC']:.12g}\n"  # Add representative hanger contraction without changing elastic constants.
    patched = patched.replace(hanger_material, hanger_material_new, 1)  # Apply the hanger thermal-prestrain proxy once.
    if "*STEP\n" not in patched:  # Require the expected single verified L2 static step.
        raise RuntimeError("verified L2 step marker not found")  # Stop rather than silently patch an incompatible model.
    prefix, old_step = patched.split("*STEP\n", 1)  # Separate the immutable model block from the old analysis step.
    if "*DLOAD\n" not in old_step:  # Require the verified permanent-load block.
        raise RuntimeError("verified L2 dead-load block not found")  # Stop rather than inventing permanent actions.
    dead_tail = "*DLOAD\n" + old_step.split("*DLOAD\n", 1)[1]  # Preserve all original gravity, nodal loads and output requests.
    dead_tail = dead_tail.replace("*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\n", 1)  # Add centerline calibration output while retaining existing output.
    metadata = {"pretensionNodeCount": len(pretension_nodes), "calibrationNodeCount": len(calibration_nodes), "midspanNode": midspan_node, "basis": basis}  # Record every inserted modeling assumption.
    return prefix, dead_tail, midspan_node, metadata  # Return reusable blocks for alternate nonlinear load paths.


def build_trial(text: str, scale: float, strategy: str) -> tuple[str, int, dict]:  # Build one final-state-equivalent nonlinear prestress trial.
    prefix, dead_tail, midspan_node, metadata = prepare_prefix(text, scale)  # Prepare common model definitions.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n"  # Define a zero thermal-strain reference before loading.
    temperature = f"*TEMPERATURE\nPRETENSION_NODES, {-scale:.12g}\n"  # Convert the global prestress scale to cable/hanger contraction.
    controls = "*STATIC\n0.001, 1.0, 1.E-09, 0.02\n"  # Use conservative automatic increments for large-displacement equilibrium.
    if strategy == "simultaneous":  # Ramp prestress and permanent load through one equilibrium path.
        step = "*STEP, NAME=FORM_FIND_DEAD, NLGEOM=YES, INC=1000\n" + controls + temperature + dead_tail  # End directly at the completed permanent-load state.
    elif strategy == "prestress_first":  # Establish cable/hanger contraction before adding the permanent actions.
        first = "*STEP, NAME=PRESTRESS_ONLY, NLGEOM=YES, INC=1000\n" + controls + temperature + "*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*END STEP\n"  # Solve the numerical prestress initialization state.
        second = "*STEP, NAME=DEAD_EQUILIBRIUM, NLGEOM=YES, INC=1000\n" + controls + dead_tail  # Add the unchanged PR9 permanent loads with prestress inherited.
        step = first + second  # Concatenate both conservative static steps.
    else:  # Reject unknown solution paths explicitly.
        raise ValueError(strategy)  # Prevent accidental use of an unreviewed initialization strategy.
    return prefix + initial + step, midspan_node, metadata  # Return the complete trial deck and audit metadata.


def displacement_blocks(dat_path: Path, set_name: str) -> list[dict[int, tuple[float, float, float]]]:  # Parse CalculiX nodal displacement print blocks for one set.
    if not dat_path.exists() or dat_path.stat().st_size == 0:  # Handle failed solves without parser errors.
        return []  # Return no observations when the result file is absent or empty.
    lines = dat_path.read_text(encoding="utf-8", errors="replace").splitlines()  # Read solver text defensively.
    blocks: list[dict[int, tuple[float, float, float]]] = []  # Store every printed increment for the requested set.
    index = 0  # Start at the first result line.
    while index < len(lines):  # Scan all solver result blocks.
        header = lines[index].strip()  # Normalize the candidate header line.
        if "displacements" not in header.lower() or f"set {set_name}" not in header.lower():  # Skip unrelated print blocks.
            index += 1  # Advance one line when the header does not match.
            continue  # Continue searching for the requested set.
        index += 1  # Move to data following the matched header.
        rows: dict[int, tuple[float, float, float]] = {}  # Collect one displacement block.
        while index < len(lines):  # Read rows until the next blank separator after data.
            row = lines[index].strip()  # Normalize the result row.
            if not row and rows:  # End the block after at least one parsed row.
                break  # Preserve the complete current block.
            fields = row.split()  # Parse whitespace-separated CalculiX result columns.
            if len(fields) >= 4:  # Require node id plus three translations.
                try:  # Attempt numeric conversion only for result rows.
                    rows[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Store U1, U2 and U3 by original node id.
                except ValueError:  # Ignore column headers or unrelated text inside the print section.
                    pass  # Keep scanning until a valid data block ends.
            index += 1  # Advance to the next result row.
        if rows:  # Keep only nonempty displacement blocks.
            blocks.append(rows)  # Preserve the solver increment in source order.
        index += 1  # Advance beyond the block separator.
    return blocks  # Return all matched increments so the caller can use the final state.


def solve_trial(ccx: str, trial_dir: Path, inp_text: str, stem: str, midspan_node: int) -> dict:  # Execute one CalculiX trial and extract final geometry metrics.
    trial_dir.mkdir(parents=True, exist_ok=True)  # Create an isolated solver directory for deterministic outputs.
    inp_path = trial_dir / f"{stem}.inp"  # Define the exact trial input path.
    inp_path.write_text(inp_text, encoding="ascii", newline="\n")  # Write the common-keyword ASCII input deck.
    result = subprocess.run([ccx, "-i", stem], cwd=trial_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # Run CalculiX synchronously and capture its complete console log.
    log_path = trial_dir / f"{stem}.stdout.log"  # Preserve the solver console output alongside result files.
    log_path.write_text(result.stdout, encoding="utf-8", errors="replace")  # Store the exact convergence/error trace.
    clean = result.returncode == 0 and "Job finished" in result.stdout and "*ERROR" not in result.stdout  # Require both clean process termination and clean solver log semantics.
    blocks = displacement_blocks(trial_dir / f"{stem}.dat", "PRESTRESS_CALIBRATION")  # Read centerline geometry observations.
    final = blocks[-1] if blocks else {}  # Use the last converged printed state only.
    u3_values = [value[2] for value in final.values()]  # Extract vertical displacement at every calibration node.
    rms_u3 = math.sqrt(sum(value * value for value in u3_values) / len(u3_values)) if u3_values else None  # Compute completed-geometry RMS error in millimetres.
    max_abs_u3 = max((abs(value) for value in u3_values), default=None)  # Compute the worst centerline vertical deviation.
    mid_u3 = final.get(midspan_node, (None, None, None))[2] if midspan_node in final else None  # Record the familiar midspan vertical displacement.
    return {"exitCode": result.returncode, "cleanConvergence": clean, "rmsCenterlineU3Mm": rms_u3, "maxAbsCenterlineU3Mm": max_abs_u3, "midspanU3Mm": mid_u3, "datBytes": (trial_dir / f"{stem}.dat").stat().st_size if (trial_dir / f"{stem}.dat").exists() else 0, "frdBytes": (trial_dir / f"{stem}.frd").stat().st_size if (trial_dir / f"{stem}.frd").exists() else 0, "logTail": result.stdout.splitlines()[-30:]}  # Return convergence and geometry diagnostics.


def main() -> int:  # Run the complete bounded prestress-isolation calibration.
    parser = argparse.ArgumentParser()  # Create the deterministic CLI.
    parser.add_argument("--base", type=Path, required=True)  # Accept the verified PR9 LC01 input deck.
    parser.add_argument("--output", type=Path, required=True)  # Accept an isolated result directory.
    parser.add_argument("--ccx", required=True)  # Accept the exact CalculiX executable path.
    args = parser.parse_args()  # Parse all required arguments.
    base_text = args.base.read_text(encoding="ascii")  # Read the verified baseline deck exactly once.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the calibration result root.
    rows: list[dict] = []  # Accumulate every strategy/scale outcome.
    model_metadata: dict | None = None  # Preserve common modeling metadata from the first generated case.
    for strategy in STRATEGIES:  # Test both final-state-equivalent nonlinear load paths.
        for scale in TRIAL_SCALES:  # Sweep a bounded prestress range around the mechanics-based target.
            inp_text, midspan_node, metadata = build_trial(base_text, scale, strategy)  # Generate one isolated intervention deck.
            model_metadata = model_metadata or metadata  # Store common assumptions once.
            stem = f"ZQ_L2P_{strategy.upper()}_S{int(round(scale * 100)):03d}"  # Build a deterministic case identifier.
            trial_dir = args.output / "trials" / strategy / f"scale_{scale:.2f}".replace(".", "p")  # Keep every solver run independent.
            outcome = solve_trial(args.ccx, trial_dir, inp_text, stem, midspan_node)  # Execute the trial and collect final geometry metrics.
            rows.append({"strategy": strategy, "scale": scale, "stem": stem, "trialDir": str(trial_dir.relative_to(args.output)), **outcome})  # Append the complete auditable outcome.
    converged_positive = [row for row in rows if row["cleanConvergence"] and row["scale"] > 0.0 and row["rmsCenterlineU3Mm"] is not None]  # Restrict selection to actual prestressed converged cases.
    selected = min(converged_positive, key=lambda row: row["rmsCenterlineU3Mm"]) if converged_positive else None  # Select the prestressed case closest to the frozen completed geometry.
    zero_cases = [row for row in rows if row["cleanConvergence"] and row["scale"] == 0.0 and row["rmsCenterlineU3Mm"] is not None]  # Preserve nonlinear zero-prestress controls for causal comparison.
    best_zero = min(zero_cases, key=lambda row: row["rmsCenterlineU3Mm"]) if zero_cases else None  # Select the cleanest zero-prestress nonlinear control if available.
    summary = {"schemaVersion": "1.0.0-prestress-isolation", "status": "PASS" if selected else "FAIL", "baseModel": str(args.base), "intervention": "Only main-cable/hanger thermal-prestrain proxy and NLGEOM are added to the verified PR9 L2 LC01 model; topology, mesh, sections, supports and permanent loads are frozen.", "modelMetadata": model_metadata, "trials": rows, "selected": selected, "zeroPrestressControl": best_zero, "selectionObjective": "minimum RMS U3 over all interior deck-centerline nodes in the final permanent-load equilibrium", "engineeringRelease": "BLOCKED until accepted unstressed cable lengths or measured erection/finished-state cable forces are available."}  # Assemble the complete calibration receipt.
    (args.output / "prestress_calibration_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the detailed receipt before final gating.
    with (args.output / "prestress_calibration_trials.csv").open("w", encoding="utf-8-sig", newline="") as stream:  # Create a compact comparison table.
        writer = csv.DictWriter(stream, fieldnames=["strategy", "scale", "cleanConvergence", "exitCode", "rmsCenterlineU3Mm", "maxAbsCenterlineU3Mm", "midspanU3Mm", "datBytes", "frdBytes", "stem", "trialDir"])  # Freeze stable CSV columns.
        writer.writeheader()  # Write the CSV schema first.
        for row in rows:  # Serialize every trial without nested log tails.
            writer.writerow({key: row.get(key) for key in writer.fieldnames})  # Write only the stable scalar columns.
    if selected:  # Package the best converged prestressed equilibrium for direct use.
        best_dir = args.output / "best"  # Define the selected-model package directory.
        best_dir.mkdir(exist_ok=True)  # Create the selected-model package directory.
        source_dir = args.output / selected["trialDir"]  # Resolve the selected trial directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve input, field results and convergence evidence.
            source = source_dir / f"{selected['stem']}.{suffix}"  # Resolve one selected trial artifact.
            if source.exists():  # Copy only artifacts actually emitted by the solver.
                shutil.copy2(source, best_dir / source.name)  # Preserve metadata while copying the selected artifact.
        (best_dir / "selection.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")  # Store the selected scale and geometry metrics next to the model.
    print(json.dumps({"status": summary["status"], "selected": selected, "zeroPrestressControl": best_zero}, ensure_ascii=False, indent=2))  # Surface the decisive result in the workflow log.
    return 0 if selected else 2  # Fail CI only when no positive prestress trial reaches a clean equilibrium.


if __name__ == "__main__":  # Run the CLI only when invoked as the workflow program.
    raise SystemExit(main())  # Propagate the calibration gate status to GitHub Actions.
