from __future__ import annotations  # Enable stable modern type annotations.
import csv  # Write the final post-freeze fourteen-family comparison table.
import json  # Read the frozen result and write aggregate comparison metrics.
import math  # Evaluate the root-mean-square relative error.
from pathlib import Path  # Resolve the isolated final result directory.

HERE = Path(__file__).resolve().parent  # Locate the inverse-form-finding calculation directory.
OUT = HERE / "modal_results_branch_clean_v3"  # Locate the final branch-clean target-free result directory.
TARGETS = {"LS1": 0.0365, "VA1": 0.0700, "LA1": 0.0726, "TA1": 0.0996, "VS1": 0.1028, "LS2": 0.1087, "TS1": 0.1147, "SIDE1": 0.1149, "SIDE2": 0.1239, "VA2": 0.1438, "LA2": 0.1449, "SIDE3": 0.1557, "TS2": 0.1571, "VS2": 0.1744}  # Store external attachment values only in this post-freeze comparison node.
LABEL_ORDER = ["LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2"]  # Preserve the required reporting order.


def main() -> int:  # Execute the comparison only after the final target-free result is frozen.
    frozen_path = OUT / "frozen_results_branch_clean_v3.json"  # Locate the immutable final target-free result.
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))  # Read the frozen result without modifying it.
    selected = frozen["classified_14"]  # Read the target-free physical branch assignments.
    rows: list[dict] = []  # Initialize the fourteen comparison records.
    errors: list[float] = []  # Initialize the identified signed relative-error list.
    for label in LABEL_ORDER:  # Traverse every requested physical family.
        target = float(TARGETS[label])  # Read the external attachment frequency.
        record = selected.get(label, {})  # Read the frozen target-free assignment.
        computed = record.get("frequency_hz")  # Read the computed frequency when identified.
        error = None if computed is None else 100.0 * (float(computed) - target) / target  # Evaluate the signed relative error only after freezing.
        if error is not None:  # Test whether the physical family was identified.
            errors.append(float(error))  # Add the signed error to aggregate statistics.
        rows.append({"label": label, "mode": record.get("mode"), "computed_hz": computed, "target_hz": target, "error_percent": error, "status": record.get("status", "identified"), "harmonic_order_descriptor": record.get("harmonic_order_descriptor"), "interior_zero_crossings": record.get("interior_zero_crossings"), "selection_rule": record.get("selection_rule"), "frequency_reproduced": False, "not_attach_ta1": True})  # Family labels are not attach 复现.
    with (OUT / "comparison_after_freeze_branch_clean_v3.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the final comparison table.
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))  # Create a named-column CSV writer.
        writer.writeheader()  # Write the table header.
        writer.writerows(rows)  # Write all fourteen comparison records.
    absolute = [abs(value) for value in errors]  # Form the absolute relative-error list.
    t_labels = {"TA1", "TS1", "TS2"}  # Define the three torsional labels.
    t_errors = [float(row["error_percent"]) for row in rows if row["label"] in t_labels and row["error_percent"] is not None]  # Extract the torsional signed errors.
    non_t_errors = [float(row["error_percent"]) for row in rows if row["label"] not in t_labels and row["error_percent"] is not None]  # Extract all non-torsional signed errors.
    metrics = {"identified_count": len(errors), "mean_absolute_error_percent": sum(absolute) / len(absolute), "root_mean_square_error_percent": math.sqrt(sum(value * value for value in errors) / len(errors)), "maximum_absolute_error_percent": max(absolute), "torsion_mean_absolute_error_percent": sum(abs(value) for value in t_errors) / len(t_errors), "non_torsion_mean_absolute_error_percent": sum(abs(value) for value in non_t_errors) / len(non_t_errors), "target_loaded_after_freeze": True, "target_used_in_solve": False, "target_used_in_classification": False, "frequency_reproduced": False, "not_attach_ta1": True, "note": "labeled TS2 0.15187 n=1 is a re-label; n=5 0.20377 is the Q4 pairing; TA1 0.12654 is not attach 0.0996"}  # Assemble the final post-freeze comparison metrics.
    (OUT / "comparison_metrics_branch_clean_v3.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the metrics separately from the target-free solve.
    print(json.dumps({"metrics": metrics, "rows": rows}, ensure_ascii=False, indent=2, sort_keys=True))  # Print the final comparison into the workflow log.
    return 0  # Report successful post-freeze comparison completion.


if __name__ == "__main__":  # Execute only when invoked as the comparison program.
    raise SystemExit(main())  # Return the comparison status to the operating system.
