from __future__ import annotations  # Enable modern annotation behavior.
import argparse  # Parse the explicit controller command line.
import csv  # Read and write deterministic coordinate tables.
import json  # Write machine-readable iteration metrics.
from pathlib import Path  # Build platform-independent file paths.

ROOT = Path(__file__).resolve().parents[1]  # Resolve the trial package root.
DEFAULT_REFERENCE = ROOT / "ir" / "target_reference_nodes.csv"  # Point to the frozen iteration-zero reference table.
DEFAULT_CONFIG = ROOT / "config" / "trial_config.json"  # Point to the frozen controller settings.
DEFAULT_OUTPUT = ROOT / "tests" / "outer_update_smoke.csv"  # Point to the default smoke output table.
DEFAULT_REPORT = ROOT / "tests" / "outer_update_smoke.json"  # Point to the default smoke metrics file.


def parse_args() -> argparse.Namespace:  # Define the fail-closed controller interface.
    parser = argparse.ArgumentParser(description="Update unstressed reference coordinates from a loaded-coordinate result without importing prestress.")  # Create the command-line parser.
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)  # Allow an explicit current reference table.
    parser.add_argument("--loaded", type=Path, default=None)  # Accept a solver-derived loaded-coordinate table when available.
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)  # Allow an explicit next-reference output path.
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)  # Allow an explicit metrics-report output path.
    parser.add_argument("--smoke", action="store_true")  # Permit a synthetic sign test that is never accepted as an engineering iteration.
    return parser.parse_args()  # Return the parsed arguments.


def read_rows(path: Path) -> list[dict]:  # Read one coordinate CSV table.
    with path.open("r", encoding="utf-8", newline="") as handle:  # Open the table without newline ambiguity.
        return list(csv.DictReader(handle))  # Materialize all records in file order.


def read_config(path: Path) -> dict:  # Read the frozen controller configuration.
    return json.loads(path.read_text(encoding="utf-8"))  # Parse and return the configuration object.


def loaded_map_from_file(path: Path) -> dict[int, tuple[float, float, float]]:  # Parse a solver-derived loaded-coordinate table.
    rows = read_rows(path)  # Load every loaded-coordinate record.
    return {int(row["node_id"]): (float(row["x_loaded_m"]), float(row["y_loaded_m"]), float(row["z_loaded_m"])) for row in rows}  # Build a stable node-to-coordinate map.


def synthetic_loaded_map(reference_rows: list[dict]) -> dict[int, tuple[float, float, float]]:  # Create a controlled sign-only smoke case.
    loaded: dict[int, tuple[float, float, float]] = {}  # Create the synthetic loaded-coordinate map.
    for row in reference_rows:  # Traverse every reference node.
        node_id = int(row["node_id"])  # Read the stable node identifier.
        x_target = float(row["x_m"])  # Read the target longitudinal coordinate.
        y_target = float(row["y_m"])  # Read the target transverse coordinate.
        z_target = float(row["z_target_m"])  # Read the target vertical coordinate.
        z_loaded = z_target if int(row["is_support"]) == 1 else z_target - 1.0  # Put internal nodes one metre too low while keeping supports exact.
        loaded[node_id] = (x_target, y_target, z_loaded)  # Register the synthetic loaded coordinate.
    return loaded  # Return the sign-test map.


def update_reference(reference_rows: list[dict], loaded: dict[int, tuple[float, float, float]], alpha: float) -> tuple[list[dict], dict]:  # Apply the inverse unloaded-geometry update.
    output_rows: list[dict] = []  # Create the next-reference record list.
    squared_error = 0.0  # Accumulate the loaded-to-target squared coordinate error.
    max_error = 0.0  # Track the largest loaded-to-target coordinate error.
    support_change = 0.0  # Track any prohibited support-coordinate modification.
    internal_z_update_sum = 0.0  # Track the average internal vertical reference update for the sign test.
    internal_count = 0  # Count internal nodes used in the sign test.
    for row in reference_rows:  # Update every node exactly once.
        node_id = int(row["node_id"])  # Read the stable node identifier.
        if node_id not in loaded:  # Detect incomplete solver result tables.
            raise ValueError(f"loaded coordinate missing for node {node_id}")  # Stop rather than silently retaining an old coordinate.
        current = (float(row["x_m"]), float(row["y_m"]), float(row["z_reference_m"]))  # Read the current unstressed reference coordinate.
        target = (float(row["x_m"]), float(row["y_m"]), float(row["z_target_m"]))  # Read the loaded target coordinate.
        loaded_xyz = loaded[node_id]  # Read the actual or synthetic loaded coordinate.
        error = tuple(loaded_xyz[index] - target[index] for index in range(3))  # Compute loaded-minus-target error in all directions.
        error_norm = sum(value * value for value in error) ** 0.5  # Compute the Euclidean coordinate error.
        squared_error += error_norm * error_norm  # Add the squared error to the global norm.
        max_error = max(max_error, error_norm)  # Update the maximum coordinate error.
        is_support = int(row["is_support"]) == 1  # Identify physical support nodes.
        next_xyz = current if is_support else tuple(current[index] - alpha * error[index] for index in range(3))  # Keep supports fixed and update free reference coordinates.
        support_change = max(support_change, max(abs(next_xyz[index] - current[index]) for index in range(3)) if is_support else 0.0)  # Prove support coordinates remain unchanged.
        if not is_support:  # Accumulate the internal vertical update direction.
            internal_z_update_sum += next_xyz[2] - current[2]  # Add the vertical reference-coordinate update.
            internal_count += 1  # Count the updated internal node.
        output_rows.append({"node_id": node_id, "deck_id": row["deck_id"], "station_index": int(row["station_index"]), "x_m": next_xyz[0], "y_m": next_xyz[1], "z_reference_m": next_xyz[2], "z_target_m": target[2], "is_support": int(is_support)})  # Register the next reference record.
    metrics = {"loaded_target_l2_m": squared_error ** 0.5, "loaded_target_max_m": max_error, "support_reference_change_max_m": support_change, "mean_internal_z_reference_update_m": internal_z_update_sum / max(internal_count, 1), "relaxation": alpha}  # Build machine-readable update metrics.
    return output_rows, metrics  # Return the next reference and its metrics.


def write_rows(path: Path, rows: list[dict]) -> None:  # Write the next-reference coordinate table.
    path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the output directory exists.
    fieldnames = ["node_id", "deck_id", "station_index", "x_m", "y_m", "z_reference_m", "z_target_m", "is_support"]  # Freeze the output column order.
    with path.open("w", encoding="utf-8", newline="") as handle:  # Open the output table deterministically.
        writer = csv.DictWriter(handle, fieldnames=fieldnames)  # Create the deterministic CSV writer.
        writer.writeheader()  # Write the frozen header.
        writer.writerows(rows)  # Write all next-reference records.


def main() -> None:  # Execute one actual or synthetic outer-loop update.
    args = parse_args()  # Parse the explicit controller arguments.
    config = read_config(DEFAULT_CONFIG)  # Read the frozen relaxation and gate settings.
    reference_rows = read_rows(args.reference)  # Read the current unstressed reference geometry.
    if args.smoke:  # Select the synthetic sign-only smoke path.
        loaded = synthetic_loaded_map(reference_rows)  # Build a controlled one-metre-too-low loaded shape.
        result_kind = "SYNTHETIC_SIGN_SMOKE_ONLY"  # Mark the result as nonengineering evidence.
    elif args.loaded is not None:  # Select a real solver-derived loaded-coordinate table.
        loaded = loaded_map_from_file(args.loaded)  # Parse the external solver result.
        result_kind = "SOLVER_DERIVED_COORDINATE_UPDATE"  # Mark the result as an actual outer-loop update input.
    else:  # Reject an ambiguous invocation.
        raise SystemExit("Provide --loaded for an actual update or --smoke for the synthetic sign test.")  # Stop before fabricating loaded coordinates.
    next_rows, metrics = update_reference(reference_rows, loaded, float(config["formFinding"]["relaxation"]))  # Apply the frozen inverse update equation.
    write_rows(args.output, next_rows)  # Write the next unstressed reference geometry.
    report = {"projectId": config["projectId"], "runId": config["runId"], "kind": result_kind, "engineeringConclusionAllowed": False if args.smoke else None, "equation": config["formFinding"]["outerUpdate"], "metrics": metrics, "status": "PASS_SIGN_TEST" if args.smoke and metrics["mean_internal_z_reference_update_m"] > 0.0 and metrics["support_reference_change_max_m"] == 0.0 else "UPDATE_WRITTEN_NOT_VALIDATED"}  # Build the update report without claiming equilibrium.
    args.report.parent.mkdir(parents=True, exist_ok=True)  # Ensure the report directory exists.
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write the machine-readable update report.


if __name__ == "__main__":  # Execute the controller only when called directly.
    main()  # Run one fail-closed outer-loop update.
