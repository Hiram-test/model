from __future__ import annotations  # Enable modern type annotations on all supported Python versions.
import argparse  # Parse explicit input and output paths for reproducible execution.
from pathlib import Path  # Represent all paths portably.
from formal_update import formalize_and_update, write_outputs  # Import the deterministic formalization pipeline.
def main() -> int:  # Run the command-line demonstration and return a shell status.
    parser = argparse.ArgumentParser(description="Formalize drawing, point-cloud, and sensor evidence before updating a beam parameter.")  # Define the command-line interface.
    parser.add_argument("--drawing", type=Path, default=Path("examples/drawing_semantics.json"))  # Accept the verified visual-semantic contract.
    parser.add_argument("--point-cloud", type=Path, default=Path("examples/pointcloud.csv"))  # Accept the registered raw point cloud.
    parser.add_argument("--sensors", type=Path, default=Path("examples/sensors_static.csv"))  # Accept the bounded static sensor measurements.
    parser.add_argument("--output", type=Path, default=Path("results/demo"))  # Accept the evidence output directory.
    args = parser.parse_args()  # Parse the supplied command-line values.
    receipt = formalize_and_update(args.drawing, args.point_cloud, args.sensors)  # Execute the complete formal parameter update.
    write_outputs(receipt, args.output)  # Persist the machine and human receipts.
    print(f"status={receipt['status']}")  # Print the fail-closed decision for CI logs.
    if receipt["parameter_update"].get("feasible"):  # Print the accepted representative update when one exists.
        print(f"selected_modulus_gpa={receipt['parameter_update']['selected_modulus_pa'] / 1.0e9:.6f}")  # Print the modulus in engineering units.
    print(f"receipt={args.output / 'formal_update_receipt.json'}")  # Print the exact evidence path.
    return 0 if receipt["status"] == "UPDATED" else 2  # Return success only when the formal rule authorizes updating.
if __name__ == "__main__":  # Run the entry point only for direct execution.
    raise SystemExit(main())  # Propagate the deterministic status to the shell.
