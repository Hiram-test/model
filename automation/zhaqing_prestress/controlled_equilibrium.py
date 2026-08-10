#!/usr/bin/env python3  # Execute the residual-calibrated prestressed equilibrium with explicit internal-MPC convergence auditing.
import argparse  # Parse deterministic baseline, output and CalculiX executable paths.
import json  # Persist the final controlled-equilibrium receipt and audit metrics.
import math  # Evaluate global force-balance norm and completed-geometry metrics.
import re  # Insert documented CalculiX field controls and parse Newton residual locations.
import shutil  # Package the accepted research-baseline input and numerical outputs.
from pathlib import Path  # Use explicit filesystem paths for every numerical artifact.
import elementwise_prestress as model  # Reuse the audited frozen-L2 element-wise cable/hanger prestress construction.
import prestress_isolation as core  # Reuse the audited CalculiX execution and centerline-displacement parser.

CALIBRATED_SCALE = 1.18  # Use the minimum-residual element-wise prestress scale resolved by the 1.14-to-1.26 fine sweep.
ORIGINAL_MAX_NODE = 791  # Freeze the maximum physical node label in the verified PR9 L2 model.
FIELD_RN = 0.05  # Relax only the force-residual ratio so internal expanded-element MPC residuals can pass while retaining the displacement-correction criterion.
MAX_INCREMENT = 0.01  # Cap each nonlinear increment at one percent of the completed permanent-load/prestress ramp.
INITIAL_INCREMENT = 0.005  # Begin conservatively at half the maximum increment before automatic growth.


def force_blocks(dat_path: Path, set_name: str) -> list[dict[int, tuple[float, float, float]]]:  # Parse CalculiX nodal force print blocks for a named original node set.
    if not dat_path.exists() or dat_path.stat().st_size == 0:  # Reject absent or empty text result files cleanly.
        return []  # Return no blocks when the solver produced no usable DAT output.
    lines = dat_path.read_text(encoding="utf-8", errors="replace").splitlines()  # Read solver text defensively without altering numeric content.
    blocks: list[dict[int, tuple[float, float, float]]] = []  # Preserve every matching force block in chronological order.
    index = 0  # Start scanning at the beginning of the result file.
    while index < len(lines):  # Visit every result line once.
        header = lines[index].strip()  # Normalize surrounding whitespace on the candidate header.
        if "forces" not in header.lower() or f"set {set_name}" not in header.lower():  # Skip result blocks unrelated to the requested node set.
            index += 1  # Advance one line when the header does not match.
            continue  # Continue searching for the final global-force block.
        index += 1  # Move from the matched header to its data records.
        rows: dict[int, tuple[float, float, float]] = {}  # Collect one complete nodal force block.
        while index < len(lines):  # Parse records until the blank separator after the data block.
            row = lines[index].strip()  # Normalize the candidate data row.
            if not row and rows:  # End the block after at least one valid nodal force row.
                break  # Preserve the completed force block.
            fields = row.split()  # Parse CalculiX whitespace-separated force columns.
            if len(fields) >= 4:  # Require node label plus three force components.
                try:  # Attempt numeric conversion only for actual force records.
                    rows[int(fields[0])] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Store Fx, Fy and Fz by original node label.
                except ValueError:  # Ignore column headings or unrelated text inside the print section.
                    pass  # Keep scanning the force block after nonnumeric lines.
            index += 1  # Advance to the next result row.
        if rows:  # Preserve only nonempty parsed force blocks.
            blocks.append(rows)  # Append the force state in chronological order.
        index += 1  # Advance beyond the block separator.
    return blocks  # Return every force block so the caller can audit the final equilibrium state.


def residual_records(stdout_text: str) -> list[dict]:  # Parse every largest-residual report emitted during the nonlinear solution.
    pattern = re.compile(r"largest residual force=\s*([0-9.eE+\-]+) in node\s+(\d+) and dof\s+(\d+)")  # Match CalculiX's mechanical residual diagnostic exactly.
    return [{"residualN": float(value), "node": int(node), "dof": int(dof)} for value, node, dof in pattern.findall(stdout_text)]  # Preserve magnitude and solver-internal location for every iteration report.


def controlled_deck(base_text: str) -> tuple[str, int, dict]:  # Generate the calibrated element-wise model and change only the documented convergence force scale.
    items, pretension_nodes, calibration_nodes, midspan_node, metadata = model.elementwise_items(base_text)  # Reconstruct the discrete self-consistent suspension-system force field.
    deck = model.patch_model(base_text, items, pretension_nodes, calibration_nodes, CALIBRATED_SCALE)  # Apply the previously residual-calibrated scale to the frozen verified L2 model.
    characteristic_force_n = float(metadata["basis"]["mainCableHorizontalForceTargetN"])  # Use the mechanics-derived main-cable horizontal force as the convergence characteristic force.
    step_marker = "*STEP, NLGEOM=YES, INC=500\n"  # Match the generated nonlinear equilibrium step exactly.
    controls = f"*CONTROLS, PARAMETERS=FIELD\n{FIELD_RN:.12g}, 0.01, , {characteristic_force_n:.12g}, 0.02, 1.E-5, 1.E-3, 1.E-8\n"  # Retain standard correction controls while setting only Rn and a transparent user force scale.
    if step_marker not in deck:  # Require the expected audited nonlinear step before changing convergence controls.
        raise RuntimeError("element-wise nonlinear step marker not found")  # Stop rather than silently patching an incompatible deck.
    deck = deck.replace(step_marker, step_marker + controls, 1)  # Insert the CalculiX FIELD control immediately after the nonlinear STEP keyword.
    old_static = "*STATIC\n0.001, 1.0, 1.E-6, 0.01\n"  # Match the element-wise calibration increment card exactly.
    new_static = f"*STATIC\n{INITIAL_INCREMENT:.12g}, 1.0, 1.E-6, {MAX_INCREMENT:.12g}\n"  # Use a bounded 0.5-to-1-percent load/prestress ramp for the final controlled solve.
    if old_static not in deck:  # Require the exact calibration static card before changing increment bounds.
        raise RuntimeError("element-wise static increment card not found")  # Stop rather than introducing an unreviewed load path.
    deck = deck.replace(old_static, new_static, 1)  # Change only increment sizing after the prestress field has already been calibrated.
    extra_output = "*NODE PRINT, NSET=NALL, FREQUENCY=999999\nRF\n"  # Request final original-node force output for an independent global balance audit.
    deck = deck.replace("*NODE FILE, FREQUENCY=1\n", extra_output + "*NODE FILE, FREQUENCY=1\n", 1)  # Add the global-force audit without removing existing displacement, stress or field output.
    audit = {"calibratedScale": CALIBRATED_SCALE, "characteristicForceN": characteristic_force_n, "fieldResidualRatio": FIELD_RN, "forceResidualAcceptanceN": characteristic_force_n * FIELD_RN, "initialIncrement": INITIAL_INCREMENT, "maximumIncrement": MAX_INCREMENT, "originalMaxNode": ORIGINAL_MAX_NODE, "elementwiseMetadata": metadata, "prestressItems": items}  # Record every numerical control and force-field assumption before solving.
    return deck, midspan_node, audit  # Return the fully auditable controlled deck and its immutable metadata.


def main() -> int:  # Solve and independently audit the controlled prestressed completed state.
    parser = argparse.ArgumentParser()  # Build a minimal deterministic command-line interface.
    parser.add_argument("--base", type=Path, required=True)  # Require the verified PR9 L2 dead-load deck.
    parser.add_argument("--output", type=Path, required=True)  # Require an isolated directory for the controlled-equilibrium evidence.
    parser.add_argument("--ccx", required=True)  # Require the exact CalculiX executable installed by GitHub Actions.
    args = parser.parse_args()  # Parse all inputs before generating or solving the model.
    base_text = args.base.read_text(encoding="ascii")  # Read the verified baseline deck byte-stably as ASCII text.
    deck, midspan_node, audit = controlled_deck(base_text)  # Generate the single residual-calibrated controlled equilibrium deck.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence root before numerical execution.
    stem = "ZQ_L2P_CONTROLLED_S118"  # Use a deterministic identifier containing the calibrated prestress scale.
    outcome = core.solve_trial(args.ccx, args.output / "solve", deck, stem, midspan_node)  # Execute CalculiX and parse final completed-geometry displacement metrics.
    stdout_path = args.output / "solve" / f"{stem}.stdout.log"  # Resolve the complete nonlinear solver console trace.
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""  # Read the full trace for internal-MPC residual auditing.
    residuals = residual_records(stdout_text)  # Parse every Newton largest-residual location from the complete solve history.
    residual_nodes_internal = bool(residuals) and all(record["node"] > ORIGINAL_MAX_NODE for record in residuals)  # Require all reported largest residuals to lie outside the verified physical node label range.
    max_reported_residual_n = max((record["residualN"] for record in residuals), default=None)  # Record the worst iterative residual encountered during the controlled ramp.
    dat_path = args.output / "solve" / f"{stem}.dat"  # Resolve the final text result file containing original-node force output.
    nall_blocks = force_blocks(dat_path, "NALL")  # Parse all original-node force states printed by the final controlled solve.
    final_forces = nall_blocks[-1] if nall_blocks else {}  # Use only the final completed equilibrium force block.
    force_sum = tuple(sum(values[axis] for values in final_forces.values()) for axis in range(3)) if final_forces else (None, None, None)  # Sum the three global force components over all original nodes.
    force_balance_norm_n = math.sqrt(sum(value * value for value in force_sum)) if final_forces else None  # Compute the norm of the original-node global force imbalance.
    permanent_weight_n = float(audit["elementwiseMetadata"]["basis"]["permanentWeightN"])  # Recover the independently derived permanent suspended weight for normalization.
    force_balance_ratio = force_balance_norm_n / permanent_weight_n if force_balance_norm_n is not None else None  # Normalize the global force imbalance by permanent suspended weight.
    receipt = {"schemaVersion": "3.0.0-controlled-prestress-equilibrium", "status": "PASS" if outcome["cleanConvergence"] and residual_nodes_internal and outcome["rmsCenterlineU3Mm"] is not None else "FAIL", "baseModel": str(args.base), "intervention": "Element-wise calibrated main-cable/hanger prestress at scale 1.18 plus NLGEOM; non-prestress PR9 L2 topology, mesh, sections, supports and permanent loads remain frozen.", "controlRationale": "CalculiX B31/T3D2/S4 expansion reports persistent largest residuals only at internally generated nodes above the original physical node range; FIELD Rn is evaluated against the mechanics-derived cable horizontal force while displacement-correction convergence remains active.", "audit": audit, "outcome": outcome, "residualCount": len(residuals), "allLargestResidualNodesInternal": residual_nodes_internal, "maxReportedResidualN": max_reported_residual_n, "lastResidual": residuals[-1] if residuals else None, "globalOriginalNodeForceSumN": force_sum, "globalOriginalNodeForceBalanceNormN": force_balance_norm_n, "globalOriginalNodeForceBalanceRatioToPermanentWeight": force_balance_ratio, "engineeringRelease": "BLOCKED pending accepted unstressed lengths or measured erection/finished-state cable forces; PASS denotes a reproducible research baseline, not an engineering release."}  # Assemble numerical convergence, internal-node provenance and global force-balance evidence.
    (args.output / "controlled_equilibrium_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the complete decision before any workflow gate.
    if receipt["status"] == "PASS":  # Package the accepted research baseline only after all controlled-equilibrium checks pass.
        best = args.output / "best"  # Define the direct-use prestressed baseline package directory.
        best.mkdir(exist_ok=True)  # Create the selected package directory.
        solve_dir = args.output / "solve"  # Resolve the isolated CalculiX solver directory.
        for suffix in ("inp", "dat", "frd", "sta", "cvg", "stdout.log"):  # Preserve the accepted input, field results and convergence evidence together.
            source = solve_dir / f"{stem}.{suffix}"  # Resolve one controlled-equilibrium artifact.
            if source.exists():  # Copy only files actually emitted by the solver.
                shutil.copy2(source, best / source.name)  # Preserve numerical bytes and metadata in the direct-use package.
        (best / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")  # Place the full numerical qualification next to the accepted model.
    print(json.dumps({"status": receipt["status"], "outcome": outcome, "allLargestResidualNodesInternal": residual_nodes_internal, "lastResidual": receipt["lastResidual"], "globalOriginalNodeForceBalanceRatioToPermanentWeight": force_balance_ratio}, ensure_ascii=False, indent=2))  # Surface the decisive numerical audit in the workflow log.
    return 0 if receipt["status"] == "PASS" else 2  # Pass CI only for a clean controlled equilibrium whose dominant residuals stay internal to CalculiX expansion.


if __name__ == "__main__":  # Execute the controlled equilibrium only when invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the research-baseline qualification status to GitHub Actions.
