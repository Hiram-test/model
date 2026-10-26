"""Export existing native audit values for a non-Python scientific plot."""  # This script extracts data only; Gnuplot performs rendering.
import json  # Parse the recorded native solver audit without manufacturing response fields.
from pathlib import Path  # Resolve paths relative to the repository rather than a transient working directory.
ROOT = Path(__file__).resolve().parents[3]  # Locate the existing GitHub-backed project root.
CASE = ROOT / "results/zhaqing_global_local_20261026/global/detailed_wind_train01_recovery"  # Select the explicitly failed wind history.
OUT = ROOT / "results/zhaqing_global_local_20261026/progress"  # Keep reproducible plot inputs beside their provenance.
OUT.mkdir(parents=True, exist_ok=True)  # Create the report output without modifying native solver evidence.
rows = [json.loads(line) for line in (CASE / "step_audits.jsonl").read_text().splitlines()]  # Read every accepted native audit including the initial static state.
failure = json.loads((CASE / "case_failure.json").read_text())  # Read the rejection rather than pretending the 20-second history completed.
failed_residual = float(failure["error"].split("residual", 1)[1].split(",", 1)[0])  # Recover the independently evaluated failing residual from the saved exception.
lines = ["# time_s independent_equilibrium_residual_N accepted_frame"]  # Name the exact numerical quantity and acceptance flag.
lines.extend(f'{row["time_s"]:.17g} {row["free_residual_equivalent_N"]:.17g} 1' for row in rows)  # Preserve original double-precision numerical audit values.
lines.append(f'{14 * 0.00625:.17g} {failed_residual:.17g} 0')  # Append the failed fourteenth attempted step without counting it as a valid field frame.
(OUT / "failed_dynamic_equilibrium.dat").write_text("\n".join(lines) + "\n")  # Save a plain text dataset suitable for Gnuplot, Origin, or other scientific plotting tools.
print(json.dumps({"accepted_dynamic_steps": len(rows) - 1, "rejected_step": 14, "training_eligible": False, "data": str(OUT / "failed_dynamic_equilibrium.dat")}))  # Report the honest scope of this diagnostic curve.
