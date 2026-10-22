from __future__ import annotations  # Enable modern type annotations in the test environment.
import csv  # Rewrite one sensor table for a rejection test.
import json  # Rewrite one drawing contract for a fail-closed test.
from pathlib import Path  # Represent fixture and temporary paths portably.
import pytest  # Assert expected failures and numerical conditions.
from formal_update import formalize_and_update, load_drawing_ir  # Exercise the public prototype API.
ROOT = Path(__file__).resolve().parents[1]  # Locate the prototype root independently of the working directory.
def test_point_cloud_geometry_precedes_modulus_update() -> None:  # Verify that actual geometry prevents material misattribution.
    receipt = formalize_and_update(ROOT / "examples/drawing_semantics.json", ROOT / "examples/pointcloud.csv", ROOT / "examples/sensors_static.csv")  # Run the complete evidence pipeline.
    assert receipt["status"] == "UPDATED"  # Require the global modulus error form to be accepted.
    selected_gpa = receipt["parameter_update"]["selected_modulus_pa"] / 1.0e9  # Convert the accepted representative modulus to GPa.
    counterfactual_gpa = receipt["drawing_only_counterfactual"]["selected_modulus_pa"] / 1.0e9  # Convert the drawing-only result to GPa.
    assert 199.0 <= selected_gpa <= 201.0  # Require recovery of the physical 200 GPa modulus within deterministic sensor bounds.
    assert 175.0 <= counterfactual_gpa <= 179.0  # Require the known bias when measured section depth is ignored.
    assert receipt["geometry_form"]["geometry_changed_from_drawing"] is True  # Require explicit geometry-first updating.
    assert receipt["postcondition"]["target_error_form_removed_within_measurement_bounds"] is True  # Require the formal postcondition.
def test_asymmetric_measurement_error_is_rejected(tmp_path: Path) -> None:  # Verify that a non-admissible error form is not forced into Young's modulus.
    source_path = ROOT / "examples/sensors_static.csv"  # Locate the valid sensor fixture.
    target_path = tmp_path / "sensors_asymmetric.csv"  # Create an isolated modified fixture.
    with source_path.open("r", encoding="utf-8", newline="") as source_stream:  # Read the valid bounded measurements.
        rows = list(csv.DictReader(source_stream))  # Materialize rows for one deterministic modification.
    for row in rows:  # Visit every sensor record.
        if abs(float(row["x_m"]) - 3.0) <= 1.0e-9:  # Select one side of a mirror pair.
            row["displacement_mm"] = str(float(row["displacement_mm"]) + 0.5)  # Add an error far outside the declared bound.
    with target_path.open("w", encoding="utf-8", newline="") as target_stream:  # Write the modified bounded-error table.
        writer = csv.DictWriter(target_stream, fieldnames=["sensor_id", "x_m", "displacement_mm", "bound_mm"])  # Preserve the production schema.
        writer.writeheader()  # Write the explicit unit-bearing columns.
        writer.writerows(rows)  # Write all modified measurements.
    receipt = formalize_and_update(ROOT / "examples/drawing_semantics.json", ROOT / "examples/pointcloud.csv", target_path)  # Run the formal update against incompatible evidence.
    assert receipt["status"] == "REJECTED"  # Require a refusal rather than a best-fit modulus.
    assert receipt["measurement_error_form"]["symmetry_form_satisfied"] is False  # Require the detected error-form conflict.
    assert receipt["postcondition"]["unexplained_error_preserved_instead_of_forced_into_parameter"] is True  # Require unexplained evidence to remain visible.
def test_visual_semantic_contract_fails_closed(tmp_path: Path) -> None:  # Verify that unverified visual output cannot drive mechanics.
    source = json.loads((ROOT / "examples/drawing_semantics.json").read_text(encoding="utf-8"))  # Load the verified drawing contract.
    source["extraction_status"] = "DRAFT"  # Mark the visual-semantic output as unverified.
    target = tmp_path / "draft_drawing.json"  # Create an isolated draft contract.
    target.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the invalid contract.
    with pytest.raises(ValueError, match="not verified"):  # Require an explicit fail-closed error.
        load_drawing_ir(target)  # Attempt to compile the draft visual output.
def test_every_nonempty_python_line_has_a_comment() -> None:  # Enforce the user's source-code annotation requirement.
    python_files = sorted(ROOT.glob("*.py")) + [ROOT / "tests/test_formal_update.py"]  # Enumerate every Python source module in this prototype.
    failures: list[str] = []  # Accumulate uncommented source locations.
    for path in python_files:  # Scan each Python source file.
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # Scan each source line with its stable number.
            if line.strip() and "#" not in line:  # Treat every nonempty source line as requiring an inline or full-line comment.
                failures.append(f"{path.name}:{line_number}:{line}")  # Record the exact violation.
    assert not failures, "\n".join(failures)  # Fail CI with all annotation violations at once.
