from __future__ import annotations  # Enable modern type annotations on all supported Python versions.
import argparse  # Parse explicit input and output paths for reproducible execution.
from pathlib import Path  # Represent all paths portably.
from formal_update import compile_svg_drawing, formalize_and_update, write_outputs  # Import drawing compilation and deterministic updating.
def main() -> int:  # Run the command-line demonstration and return a shell status.
    parser = argparse.ArgumentParser(description="Formalize raw drawing, point-cloud, and sensor evidence before updating a beam parameter.")  # Define the command-line interface.
    parser.add_argument("--drawing", type=Path, default=Path("examples/beam_static_drawing.svg"))  # Accept either a raw SVG drawing or a verified semantic JSON contract.
    parser.add_argument("--point-cloud", type=Path, default=Path("examples/pointcloud.csv"))  # Accept the registered raw point cloud.
    parser.add_argument("--sensors", type=Path, default=Path("examples/sensors_static.csv"))  # Accept the bounded static sensor measurements.
    parser.add_argument("--output", type=Path, default=Path("results/demo"))  # Accept the evidence output directory.
    parser.add_argument("--initial-modulus-pa", type=float, default=230.0e9)  # Accept the current model modulus supplied by the baseline model.
    parser.add_argument("--reference-modulus-pa", type=float, default=200.0e9)  # Accept the numerical reference modulus used for dimensionless updating.
    args = parser.parse_args()  # Parse the supplied command-line values.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the evidence directory before compiling a raw drawing.
    drawing_suffix = args.drawing.suffix.lower()  # Inspect the drawing source type explicitly.
    if drawing_suffix == ".svg":  # Compile a source-native vector drawing into structural semantics.
        drawing_ir_path = args.output / "drawing_semantics.generated.json"  # Keep the generated intermediate representation beside the update receipt.
        compile_svg_drawing(args.drawing, drawing_ir_path, args.initial_modulus_pa, args.reference_modulus_pa)  # Extract and verify beam, support, load, section, and sensor semantics.
    elif drawing_suffix == ".json":  # Accept an externally verified VLM or human semantic contract.
        drawing_ir_path = args.drawing  # Reuse the supplied semantic intermediate representation.
    else:  # Reject source types without an implemented or verified adapter.
        raise ValueError(f"unsupported drawing source type: {drawing_suffix}")  # Stop instead of silently bypassing drawing analysis.
    receipt = formalize_and_update(drawing_ir_path, args.point_cloud, args.sensors)  # Execute the complete formal parameter update.
    write_outputs(receipt, args.output)  # Persist the machine and human receipts.
    print(f"status={receipt['status']}")  # Print the fail-closed decision for CI logs.
    if receipt["parameter_update"].get("feasible"):  # Print the accepted representative update when one exists.
        print(f"selected_modulus_gpa={receipt['parameter_update']['selected_modulus_pa'] / 1.0e9:.6f}")  # Print the modulus in engineering units.
    print(f"drawing_ir={drawing_ir_path}")  # Print the exact compiled or supplied semantic contract.
    print(f"receipt={args.output / 'formal_update_receipt.json'}")  # Print the exact evidence path.
    return 0 if receipt["status"] == "UPDATED" else 2  # Return success only when the formal rule authorizes updating.
if __name__ == "__main__":  # Run the entry point only for direct execution.
    raise SystemExit(main())  # Propagate the deterministic status to the shell.
