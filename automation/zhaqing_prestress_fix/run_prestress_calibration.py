from __future__ import annotations  # Enable modern typing behavior while keeping the script compatible with the GitHub runner.
import json  # Serialize the complete calibration history and the selected prestress state.
import re  # Parse CalculiX text output and patch the input deck deterministically.
import subprocess  # Execute the CalculiX solver for every prestress candidate.
import sys  # Read command-line arguments and propagate a meaningful process status.
from pathlib import Path  # Handle all input, output, and solver-result paths safely.
BASE_ALPHA = 130.0 / 195000.0  # Use 130 MPa as the first-order main-cable stress scale for the inverse search.
INITIAL_SCALES = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]  # Span zero prestress through a deliberately broad tensile range.
TARGET_NODE = 291  # Use the centerline deck node at midspan as the completed-geometry vertical-displacement target.
TARGET_UZ_MM = 0.0  # Define the supplied bridge geometry as the desired dead-load completed configuration.
TARGET_TOL_MM = 1.0  # Accept a prestress calibration when the midspan vertical residual is within one millimetre.
MAX_REFINEMENT_RUNS = 5  # Limit secant/bisection refinement while still resolving the zero-displacement crossing tightly.
def split_baseline(text: str) -> tuple[str, str, str]:  # Separate the validated model definition, permanent loads, and requested outputs.
    step_start = text.index("*STEP")  # Locate the only original linear static analysis step.
    prefix = text[:step_start]  # Preserve every validated node, element, property, set, boundary, and connection definition unchanged.
    original_step = text[step_start:]  # Isolate the original loading and output block for controlled nonlinear reconstruction.
    load_start = original_step.index("*DLOAD")  # Locate the validated gravity-plus-concentrated permanent-load definition.
    output_start = original_step.index("*NODE PRINT")  # Locate the original monitoring and element-output requests.
    end_step = original_step.index("*END STEP")  # Locate the original step terminator so no stale linear controls survive.
    loads = original_step[load_start:output_start]  # Reuse the original permanent actions byte-for-byte.
    outputs = original_step[output_start:end_step]  # Reuse the original displacement, reaction, stress, and strain requests.
    return prefix, loads, outputs  # Return the three immutable building blocks needed by every candidate model.
def build_candidate(base_text: str, scale: float) -> str:  # Build one two-stage geometrically nonlinear prestress/dead-load candidate.
    prefix, loads, outputs = split_baseline(base_text)  # Recover the validated model definition and original permanent actions.
    material_anchor = "*MATERIAL, NAME=MAIN_CABLE_WIRE_SCREEN\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n"  # Match the exclusive main-cable material block exactly.
    alpha = BASE_ALPHA * scale  # Convert the dimensionless search scale into an equivalent thermal contraction coefficient.
    expansion_block = material_anchor + "*EXPANSION, ZERO=0.\n" + f"{alpha:.12e}\n"  # Encode the main-cable free contraction without modifying any other material.
    if material_anchor not in prefix:  # Refuse to silently patch an unexpected or changed baseline deck.
        raise RuntimeError("main-cable material anchor not found")  # Stop immediately if the validated material contract has changed.
    prefix = prefix.replace(material_anchor, expansion_block, 1)  # Add thermal strain capability only to the main-cable material.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 0.\n"  # Establish a zero-strain thermal reference before analysis begins.
    prestress_step = "*STEP, NAME=PRESTRESS, NLGEOM=YES, INC=1000\n*STATIC\n1.0E-3, 1.0, 1.0E-10, 2.0E-2\n*TEMPERATURE\nNALL, -1.\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\nU, RF\n*EL PRINT, ELSET=MAIN_CABLES, FREQUENCY=1\nS, E\n*END STEP\n"  # Ramp cable contraction alone to establish geometric stiffness before gravity is introduced.
    dead_step = "*STEP, NAME=DEAD_EQUILIBRIUM, NLGEOM=YES, INC=2000\n*STATIC\n1.0E-3, 1.0, 1.0E-10, 2.0E-2\n*TEMPERATURE\nNALL, -1.\n" + loads + outputs + "*END STEP\n"  # Hold the same cable contraction explicitly while ramping the validated permanent actions to completed-state equilibrium.
    heading_note = f"** PRESTRESS_CALIBRATION_SCALE={scale:.12g}; MAIN_CABLE_ALPHA={alpha:.12e}; TARGET_NODE={TARGET_NODE}; TARGET_UZ_MM={TARGET_UZ_MM:.6f}\n"  # Embed full calibration provenance directly in the solver deck.
    return prefix.replace("** ----------------------------------------------------------------\n** NODES", heading_note + "** ----------------------------------------------------------------\n** NODES", 1) + initial + prestress_step + dead_step  # Assemble the final candidate without changing geometry or non-cable properties.
def parse_last_displacement(dat_path: Path, node_id: int) -> float | None:  # Extract the final-step vertical displacement of the selected completed-state monitor node.
    if not dat_path.exists():  # Treat missing solver output as a failed candidate rather than inventing a value.
        return None  # Signal that no displacement can be trusted for this run.
    lines = dat_path.read_text(errors="ignore").splitlines()  # Load the CalculiX text output while tolerating platform encoding details.
    value = None  # Keep the most recent matching displacement so the second step supersedes the prestress-only step.
    in_disp = False  # Track whether the parser is currently inside a displacement table.
    for line in lines:  # Scan every output line in chronological order.
        if "displacements (vx,vy,vz)" in line.lower():  # Detect the beginning of each nodal displacement table.
            in_disp = True  # Enable numeric row parsing for the current table.
            continue  # Move to the first data row after the table heading.
        if in_disp and line.strip().startswith("forces ("):  # Detect the end of the displacement table when reaction-force output begins.
            in_disp = False  # Stop interpreting subsequent rows as displacement values.
        if in_disp:  # Parse only rows belonging to an active displacement table.
            match = re.match(r"\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s*$", line)  # Match one CalculiX node-displacement row.
            if match and int(match.group(1)) == node_id:  # Select only the specified bridge midspan monitoring node.
                value = float(match.group(4))  # Store its global vertical displacement component in millimetres.
    return value  # Return the completed-state displacement from the last successfully printed table.
def converged(sta_path: Path, log_text: str) -> bool:  # Apply a strict but solver-version-tolerant convergence screen.
    if "*ERROR" in log_text.upper() or "TOO MANY CUTBACKS" in log_text.upper():  # Reject explicit CalculiX nonlinear failure messages.
        return False  # Mark the candidate unusable for inverse calibration.
    if not sta_path.exists():  # Require the nonlinear status file as solver evidence.
        return False  # Reject runs that terminated before producing status history.
    sta = sta_path.read_text(errors="ignore")  # Read increment history for the final-step completion check.
    successful_lines = [line for line in sta.splitlines() if re.match(r"\s*2\s+\d+\s+\d+\s+\d+\s+", line) and "U" not in line]  # Find accepted increments belonging to the dead-load equilibrium step.
    return bool(successful_lines) and any(float(line.split()[5]) >= 0.999999 for line in successful_lines if len(line.split()) > 5)  # Require the second step to reach its full normalized step time.
def run_scale(base_text: str, output_dir: Path, scale: float) -> dict[str, object]:  # Generate, solve, and audit one prestress scale.
    label = f"s{scale:.8f}".replace("-", "m").replace(".", "p")  # Create a filesystem-safe deterministic candidate label.
    run_dir = output_dir / label  # Isolate every solver run so files cannot overwrite one another.
    run_dir.mkdir(parents=True, exist_ok=True)  # Create the candidate evidence directory before writing the model.
    model_text = build_candidate(base_text, scale)  # Construct the two-stage nonlinear input deck for this prestress level.
    inp_path = run_dir / "model.inp"  # Use a short stable CalculiX job name inside each isolated directory.
    inp_path.write_text(model_text)  # Preserve the exact candidate deck as part of the calibration evidence.
    proc = subprocess.run(["ccx", "-i", "model"], cwd=run_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # Execute CalculiX synchronously and capture its complete diagnostic stream.
    log_text = proc.stdout  # Retain the solver console output for convergence diagnostics and later audit.
    (run_dir / "solver.stdout.log").write_text(log_text)  # Save the raw CalculiX console trace next to the numerical result files.
    is_converged = converged(run_dir / "model.sta", log_text)  # Determine whether the full dead-load equilibrium step was accepted.
    uz = parse_last_displacement(run_dir / "model.dat", TARGET_NODE) if is_converged else None  # Read the completed-state displacement only from a converged solution.
    return {"scale": scale, "alpha": BASE_ALPHA * scale, "nominalMainCableStressMPa": 130.0 * scale, "solverExitCode": proc.returncode, "converged": is_converged, "midspanUzMm": uz, "directory": label}  # Return the complete scalar evidence needed by the inverse search.
def find_bracket(rows: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, object]] | None:  # Locate two converged prestress states whose completed-state vertical displacements straddle zero.
    valid = sorted([row for row in rows if row["converged"] and row["midspanUzMm"] is not None], key=lambda row: float(row["scale"]))  # Keep only physically evaluable candidates in scale order.
    for left, right in zip(valid, valid[1:]):  # Test every adjacent converged pair for a sign change.
        ul = float(left["midspanUzMm"]) - TARGET_UZ_MM  # Compute the left candidate's signed target residual.
        ur = float(right["midspanUzMm"]) - TARGET_UZ_MM  # Compute the right candidate's signed target residual.
        if ul == 0.0 or ur == 0.0 or ul * ur < 0.0:  # Accept exact hits and genuine zero crossings alike.
            return left, right  # Return the tightest available local bracket in the current sampled set.
    return None  # Signal that the sampled prestress range has not yet crossed the completed-state target.
def choose_next(left: dict[str, object], right: dict[str, object]) -> float:  # Compute a safeguarded secant estimate inside a zero-displacement bracket.
    sl = float(left["scale"])  # Read the lower bracket prestress scale.
    sr = float(right["scale"])  # Read the upper bracket prestress scale.
    ul = float(left["midspanUzMm"]) - TARGET_UZ_MM  # Read the lower bracket completed-state displacement residual.
    ur = float(right["midspanUzMm"]) - TARGET_UZ_MM  # Read the upper bracket completed-state displacement residual.
    if abs(ur - ul) < 1.0e-12:  # Avoid numerical division by an almost flat displacement response.
        return 0.5 * (sl + sr)  # Fall back to bisection when secant interpolation is ill-conditioned.
    secant = sl - ul * (sr - sl) / (ur - ul)  # Interpolate the prestress scale expected to drive completed-state displacement to zero.
    margin = 0.05 * (sr - sl)  # Keep the trial safely away from either bracket endpoint to ensure useful refinement.
    return min(sr - margin, max(sl + margin, secant))  # Safeguard the secant estimate within the current physical bracket.
def main() -> int:  # Execute the complete nonlinear inverse calibration and persist its solver evidence.
    if len(sys.argv) != 3:  # Require an explicit validated baseline deck and an explicit output directory.
        raise SystemExit("usage: run_prestress_calibration.py BASELINE_INP OUTPUT_DIR")  # Fail clearly when workflow arguments are incomplete.
    base_path = Path(sys.argv[1]).resolve()  # Resolve the validated PR9 LC01 baseline input deck path.
    output_dir = Path(sys.argv[2]).resolve()  # Resolve the append-only calibration evidence directory.
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the top-level evidence directory before any solver run.
    base_text = base_path.read_text()  # Load the exact validated L2 shell-beam-cable model once for deterministic candidate generation.
    rows: list[dict[str, object]] = []  # Accumulate every attempted prestress state, including nonconvergent runs.
    attempted: set[float] = set()  # Prevent duplicate solver calls when refinement reproduces a sampled scale.
    for scale in INITIAL_SCALES:  # Establish a broad initial displacement-versus-prestress response curve.
        row = run_scale(base_text, output_dir, scale)  # Solve one nonlinear completed-state candidate.
        rows.append(row)  # Preserve the result regardless of convergence outcome.
        attempted.add(round(scale, 10))  # Register the scale so later interpolation cannot repeat it accidentally.
    for _ in range(MAX_REFINEMENT_RUNS):  # Refine only after the initial broad response curve has been solved.
        valid = [row for row in rows if row["converged"] and row["midspanUzMm"] is not None]  # Gather all currently usable completed-state solutions.
        if valid and min(abs(float(row["midspanUzMm"]) - TARGET_UZ_MM) for row in valid) <= TARGET_TOL_MM:  # Stop once the completed geometry is recovered to the requested tolerance.
            break  # Preserve compute while retaining the already adequate calibrated state.
        bracket = find_bracket(rows)  # Search the current solution set for a physical zero-displacement bracket.
        if bracket is None:  # Avoid uncontrolled extrapolation when the solved prestress range never reaches the target.
            break  # Leave the best sampled candidate explicit for diagnosis rather than inventing an unbounded prestress.
        trial = choose_next(*bracket)  # Compute a safeguarded secant/bisection refinement scale.
        if round(trial, 10) in attempted:  # Detect a numerically repeated trial that cannot add information.
            trial = 0.5 * (float(bracket[0]["scale"]) + float(bracket[1]["scale"]))  # Force a strict bisection point inside the current bracket.
        if round(trial, 10) in attempted:  # Detect a fully exhausted bracket caused by floating-point coincidence.
            break  # Stop refinement because another identical solve would provide no new evidence.
        row = run_scale(base_text, output_dir, trial)  # Solve the refined prestress candidate in the same validated L2 topology.
        rows.append(row)  # Preserve the refined result in chronological calibration history.
        attempted.add(round(trial, 10))  # Register the new scale before the next refinement iteration.
    valid = [row for row in rows if row["converged"] and row["midspanUzMm"] is not None]  # Collect all converged completed-state candidates for final selection.
    selected = min(valid, key=lambda row: abs(float(row["midspanUzMm"]) - TARGET_UZ_MM)) if valid else None  # Select the converged state closest to the supplied completed geometry.
    status = "PASS" if selected is not None and abs(float(selected["midspanUzMm"]) - TARGET_UZ_MM) <= TARGET_TOL_MM else "NO_CALIBRATED_SOLUTION"  # Distinguish a quantitatively recovered completed state from an incomplete search.
    summary = {"status": status, "targetNode": TARGET_NODE, "targetUzMm": TARGET_UZ_MM, "toleranceMm": TARGET_TOL_MM, "baseAlpha": BASE_ALPHA, "selected": selected, "runs": rows}  # Assemble a complete machine-readable calibration receipt.
    (output_dir / "calibration_summary.json").write_text(json.dumps(summary, indent=2))  # Save the final result and all rejected candidates for audit and reproduction.
    print(json.dumps(summary, indent=2))  # Emit the same receipt into the GitHub Actions log for immediate inspection.
    if selected is not None:  # Export a stable final model filename whenever at least one converged candidate exists.
        selected_dir = output_dir / str(selected["directory"])  # Resolve the evidence directory belonging to the selected prestress state.
        (output_dir / "CALIBRATED_MODEL.inp").write_text((selected_dir / "model.inp").read_text())  # Copy the exact selected input deck without regenerating it.
        for suffix in ["dat", "frd", "sta", "cvg", "12d"]:  # Preserve the principal CalculiX numerical evidence next to the calibrated deck.
            source = selected_dir / f"model.{suffix}"  # Resolve one possible solver output associated with the selected state.
            if source.exists():  # Copy only files actually produced by the installed CalculiX build.
                (output_dir / f"CALIBRATED_MODEL.{suffix}").write_bytes(source.read_bytes())  # Preserve solver bytes exactly for later inspection.
    return 0 if status == "PASS" else 2  # Make the workflow gate fail unless the completed-state geometry is recovered quantitatively.
if __name__ == "__main__":  # Execute the calibration only when the file is run as the workflow entry point.
    raise SystemExit(main())  # Propagate the calibrated-state gate status back to GitHub Actions.
