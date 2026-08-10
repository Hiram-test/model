from __future__ import annotations  # Enable postponed evaluation of annotations for runner compatibility.
import json  # Serialize every nonlinear trial and the selected completed-state result.
import re  # Parse CalculiX displacement tables and patch the baseline input deterministically.
import shutil  # Copy the selected converged solver evidence into a stable delivery location.
import subprocess  # Execute CalculiX synchronously for every prestress candidate.
import sys  # Read the baseline and output paths supplied by the workflow.
from pathlib import Path  # Handle model and evidence paths without platform-dependent string operations.
E_MAIN = 195000.0  # Use the main-cable elastic modulus already defined by the validated PR9 L2 input deck in MPa.
SIGMA_REF = 126.180  # Use the analytically recovered midspan cable stress H/A from the PR9 dead-load model in MPa.
TARGET_NODE = 291  # Use the geometric bridge-deck midspan centerline node as the completed-state displacement monitor.
TARGET_UZ = 0.0  # Treat the supplied PR9 geometry as the target completed bridge configuration under permanent load.
TARGET_TOL = 1.0  # Require the final vertical residual at deck midspan to be no more than one millimetre.
SCALES = [0.0, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0]  # Bracket the equilibrium around the analytical cable-force estimate while retaining a zero-prestress control.
def split_baseline(text: str) -> tuple[str, str, str]:  # Separate the validated model definition, permanent actions, and requested output blocks.
    step_start = text.index("*STEP")  # Locate the sole original linear load step in the validated LC01 baseline.
    prefix = text[:step_start]  # Preserve all validated nodes, elements, sections, sets, and boundary conditions unchanged.
    step = text[step_start:]  # Isolate the original permanent-load step for controlled nonlinear reconstruction.
    load_start = step.index("*DLOAD")  # Locate gravity so the original permanent actions can be reused byte-for-byte.
    output_start = step.index("*NODE PRINT")  # Locate the original monitor and element output requests.
    end_step = step.index("*END STEP")  # Locate the original step terminator so stale linear controls are discarded.
    loads = step[load_start:output_start]  # Preserve the original gravity and nodal permanent loads exactly.
    outputs = step[output_start:end_step]  # Preserve the original displacement, reaction, stress, and strain requests exactly.
    return prefix, loads, outputs  # Return the immutable model pieces needed to build each nonlinear trial.
def build_model(base_text: str, scale: float) -> str:  # Construct one L2-topology model with cable prestrain and permanent load ramped together.
    prefix, loads, outputs = split_baseline(base_text)  # Recover validated geometry/properties and the original permanent actions.
    anchor = "*MATERIAL, NAME=MAIN_CABLE_WIRE_SCREEN\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n"  # Match the exclusive main-cable material definition exactly.
    if anchor not in prefix:  # Refuse to patch an unexpected baseline because silent material mismatch would invalidate calibration.
        raise RuntimeError("main-cable material anchor not found")  # Stop with an auditable error when the expected validated material block is absent.
    epsilon = (SIGMA_REF / E_MAIN) * scale  # Convert the desired tensile stress scale into an equivalent cable free-length contraction strain.
    patched = anchor + "*EXPANSION, ZERO=0.\n" + f"{epsilon:.12e}\n"  # Add thermal expansion only to the main-cable material so temperature becomes a transparent prestrain proxy.
    prefix = prefix.replace(anchor, patched, 1)  # Modify only the main-cable material and leave all other L2 properties untouched.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 0.\n"  # Define the supplied geometry as the zero-temperature reference configuration.
    step = "*STEP, NAME=COMPLETED_STATE, NLGEOM=YES, INC=2000\n"  # Activate geometric nonlinearity so cable force contributes geometric stiffness.
    step += "*STATIC\n1.0E-3, 1.0, 1.0E-10, 2.0E-2\n"  # Use aggressive automatic cutback while allowing a fine path to the completed equilibrium state.
    step += "*TEMPERATURE\nNALL, -1.\n"  # Ramp cable contraction over the same normalized step time as permanent actions to avoid an unbalanced prestress-only stage.
    step += loads  # Ramp the original PR9 gravity and nodal permanent loads synchronously with the cable contraction.
    step += outputs  # Preserve the original output requests so displacement and cable stress remain directly comparable with PR9.
    step += "*END STEP\n"  # Close the single completed-state nonlinear equilibrium step explicitly.
    note = f"** L2_PRESTRESS_SCALE={scale:.8f}; MIDSPAN_SIGMA_REF_MPA={SIGMA_REF:.6f}; EQUIV_CONTRACTION={epsilon:.12e}\n"  # Embed the exact inverse-analysis parameter in each solver deck for auditability.
    return prefix.replace("** ----------------------------------------------------------------\n** NODES", note + "** ----------------------------------------------------------------\n** NODES", 1) + initial + step  # Assemble the complete trial without changing the validated PR9 L2 topology.
def parse_uz(dat_path: Path) -> float | None:  # Read the final printed vertical displacement at the completed-state monitor node.
    if not dat_path.exists():  # Treat a missing CalculiX DAT file as an unusable nonlinear trial.
        return None  # Return no displacement rather than inventing a value from incomplete output.
    value = None  # Keep the last matching displacement row in case CalculiX prints several increments.
    in_table = False  # Track whether the parser is currently inside a displacement table.
    for line in dat_path.read_text(errors="ignore").splitlines():  # Scan the complete text result in chronological order.
        if "displacements (vx,vy,vz)" in line.lower():  # Detect the start of a standard CalculiX nodal-displacement table.
            in_table = True  # Enable numeric row parsing after the table header.
            continue  # Advance directly to the first possible data row.
        if in_table and line.strip().lower().startswith("forces ("):  # Detect the reaction-force header that terminates the displacement table.
            in_table = False  # Stop interpreting subsequent rows as displacements.
        if in_table:  # Parse only rows inside a displacement table.
            match = re.match(r"\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s*$", line)  # Match one standard node and three displacement components.
            if match and int(match.group(1)) == TARGET_NODE:  # Select only the bridge-deck midspan centerline node.
                value = float(match.group(4))  # Store the global vertical displacement in millimetres.
    return value  # Return the final available completed-state vertical displacement.
def converged(sta_path: Path, stdout_text: str) -> bool:  # Determine whether CalculiX accepted the entire single nonlinear equilibrium step.
    upper = stdout_text.upper()  # Normalize the console text for robust solver-error screening.
    if "*ERROR" in upper or "TOO MANY CUTBACKS" in upper:  # Reject explicit nonlinear solver failure messages.
        return False  # Mark the trial as nonconverged immediately when CalculiX reports a fatal path failure.
    if not sta_path.exists():  # Require status history as numerical evidence that increments were actually accepted.
        return False  # Reject runs that terminated before producing an STA file.
    accepted = []  # Collect accepted step-one increment records from the CalculiX status history.
    for line in sta_path.read_text(errors="ignore").splitlines():  # Scan every increment attempt reported by CalculiX.
        fields = line.split()  # Tokenize the compact STA row using whitespace.
        if len(fields) >= 7 and fields[0] == "1" and "U" not in fields[2]:  # Retain only successful increments belonging to the completed-state step.
            try:  # Guard numeric conversion against headers and nonstandard diagnostic lines.
                accepted.append(float(fields[5]))  # Record normalized step time for each successfully accepted increment.
            except ValueError:  # Ignore lines that resemble increment records but contain nonnumeric text.
                pass  # Continue scanning because one malformed diagnostic line does not invalidate later valid evidence.
    return bool(accepted) and max(accepted) >= 0.999999  # Require the nonlinear step to reach its full normalized time of one.
def solve_one(base_text: str, out_dir: Path, scale: float) -> dict[str, object]:  # Generate, execute, and summarize one cable-prestress trial.
    label = f"scale_{scale:.8f}".replace(".", "p")  # Build a filesystem-safe deterministic label from the tested prestress scale.
    run_dir = out_dir / label  # Isolate every CalculiX job so result files from different prestress states cannot collide.
    run_dir.mkdir(parents=True, exist_ok=True)  # Create the candidate evidence directory before writing any numerical files.
    model = build_model(base_text, scale)  # Build the exact L2-topology nonlinear candidate for this prestress scale.
    (run_dir / "model.inp").write_text(model)  # Persist the complete solver deck as auditable calibration evidence.
    proc = subprocess.run(["ccx", "-i", "model"], cwd=run_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # Execute CalculiX synchronously and capture all diagnostics.
    (run_dir / "solver.stdout.log").write_text(proc.stdout)  # Save the complete CalculiX console trace beside the numerical result files.
    ok = converged(run_dir / "model.sta", proc.stdout)  # Apply the strict full-step convergence screen to the solver evidence.
    uz = parse_uz(run_dir / "model.dat") if ok else None  # Read completed-state displacement only from a fully converged trial.
    return {"scale": scale, "equivContraction": (SIGMA_REF / E_MAIN) * scale, "nominalMidspanCableStressMPa": SIGMA_REF * scale, "solverExitCode": proc.returncode, "converged": ok, "midspanUzMm": uz, "directory": label}  # Return all scalar calibration evidence for this trial.
def choose_refinement(rows: list[dict[str, object]]) -> float | None:  # Find a secant interpolation scale when converged displacements bracket the completed geometry.
    valid = sorted([row for row in rows if row["converged"] and row["midspanUzMm"] is not None], key=lambda row: float(row["scale"]))  # Keep only physical converged states in increasing prestress order.
    for left, right in zip(valid, valid[1:]):  # Search adjacent states for a vertical-displacement sign change.
        ul = float(left["midspanUzMm"]) - TARGET_UZ  # Compute the lower-scale completed-state residual.
        ur = float(right["midspanUzMm"]) - TARGET_UZ  # Compute the upper-scale completed-state residual.
        if ul == 0.0:  # Recognize an exact lower-end equilibrium state without further solving.
            return float(left["scale"])  # Return the already solved exact root scale.
        if ur == 0.0:  # Recognize an exact upper-end equilibrium state without further solving.
            return float(right["scale"])  # Return the already solved exact root scale.
        if ul * ur < 0.0:  # Detect a genuine completed-state zero crossing between adjacent converged trials.
            secant = float(left["scale"]) - ul * (float(right["scale"]) - float(left["scale"])) / (ur - ul)  # Interpolate the scale expected to cancel the midspan vertical residual.
            return max(float(left["scale"]) + 1.0e-4, min(float(right["scale"]) - 1.0e-4, secant))  # Keep the trial strictly inside the physical bracket.
    return None  # Report that the initial scan did not bracket the target geometry.
def main() -> int:  # Run the complete L2-topology completed-state prestress calibration workflow.
    if len(sys.argv) != 3:  # Require an explicit validated LC01 baseline and an explicit output directory.
        raise SystemExit("usage: prestress_l2_calibrate.py BASELINE_INP OUTPUT_DIR")  # Fail clearly when workflow invocation is incomplete.
    base_path = Path(sys.argv[1]).resolve()  # Resolve the archived PR9 LC01 mother-model path.
    out_dir = Path(sys.argv[2]).resolve()  # Resolve the append-only nonlinear calibration evidence directory.
    out_dir.mkdir(parents=True, exist_ok=True)  # Create the output root before any CalculiX trials are executed.
    base_text = base_path.read_text()  # Load the exact validated L2 baseline once so every trial shares identical non-prestress content.
    rows = [solve_one(base_text, out_dir, scale) for scale in SCALES]  # Solve the broad analytical-prestress scan including the zero-prestress control.
    valid = [row for row in rows if row["converged"] and row["midspanUzMm"] is not None]  # Collect all completed nonlinear states that can support inverse calibration.
    best = min(valid, key=lambda row: abs(float(row["midspanUzMm"]) - TARGET_UZ)) if valid else None  # Identify the closest completed geometry from the initial scan.
    trial = choose_refinement(rows)  # Request one secant refinement when the converged scan brackets zero vertical residual.
    attempted = {round(float(row["scale"]), 8) for row in rows}  # Record all scales already solved to prevent duplicate refinement work.
    if trial is not None and round(trial, 8) not in attempted:  # Execute refinement only when interpolation produces a genuinely new scale.
        rows.append(solve_one(base_text, out_dir, trial))  # Solve the interpolated completed-state candidate using the same validated L2 topology.
        valid = [row for row in rows if row["converged"] and row["midspanUzMm"] is not None]  # Refresh the set of physical converged states after refinement.
        best = min(valid, key=lambda row: abs(float(row["midspanUzMm"]) - TARGET_UZ)) if valid else None  # Re-select the closest completed state after the secant trial.
    status = "PASS" if best is not None and abs(float(best["midspanUzMm"]) - TARGET_UZ) <= TARGET_TOL else "NO_CALIBRATED_SOLUTION"  # Apply the one-millimetre completed-geometry acceptance gate.
    summary = {"status": status, "analyticalHorizontalCableForceN": 701109.685339507, "analyticalMidspanCableStressMPa": SIGMA_REF, "targetNode": TARGET_NODE, "targetUzMm": TARGET_UZ, "toleranceMm": TARGET_TOL, "selected": best, "runs": rows}  # Assemble the complete machine-readable calibration receipt.
    (out_dir / "calibration_summary.json").write_text(json.dumps(summary, indent=2))  # Persist every accepted and rejected nonlinear trial for numerical audit.
    if best is not None:  # Copy the best physical nonlinear trial into stable delivery filenames even when it misses the final tolerance.
        source = out_dir / str(best["directory"])  # Resolve the evidence directory of the closest completed-state solution.
        for suffix in ["inp", "dat", "frd", "sta", "cvg", "12d"]:  # Preserve the model deck and all common CalculiX result formats that exist.
            candidate = source / f"model.{suffix}"  # Locate one result file inside the selected candidate directory.
            if candidate.exists():  # Copy only files actually generated by this CalculiX build.
                shutil.copy2(candidate, out_dir / f"SELECTED_MODEL.{suffix}")  # Publish the selected evidence under a stable filename for downstream AFEM work.
    print(json.dumps(summary, indent=2))  # Emit the complete calibration receipt into the GitHub Actions log for immediate inspection.
    return 0 if status == "PASS" else 2  # Let CI distinguish a quantitatively calibrated model from a diagnostic-only nonlinear solve.
if __name__ == "__main__":  # Execute calibration only when this file is invoked as the workflow entry point.
    raise SystemExit(main())  # Propagate the numerical calibration status to GitHub Actions while retaining uploaded evidence.
