"""Read native force coefficients with explicit axis signs and time-weighted statistics."""  # No FEM or CFD fields are synthesized.
import argparse  # Expose reproducible postprocessing paths.
import hashlib  # Hash the exact native output bytes.
import json  # Persist solver status and limitations.
from pathlib import Path  # Read native result files.
import re  # Read the solver's actual axis declarations.
import numpy as np  # Calculate numerical statistics without rendering.


def read_coefficients(path):  # Interpret the actual native header rather than assuming a moment sign.
    lines = Path(path).read_text(encoding="utf-8").splitlines()  # Read completed native text records.
    axes, scalars, names, data = {}, {}, None, []  # Collect declared axes, reference scales, columns and rows.
    for line_number, line in enumerate(lines):  # Process the native output in order.
        match = re.match(r"#\s*(\w+)\s*:\s*\(([^)]+)\)", line)  # Find the actual native reference vectors.
        if match:  # Store the solver's direction convention.
            axes[match.group(1)] = np.fromstring(match.group(2), sep=" ")  # Parse direction components.
        reference = re.match(r"#\s*(magUInf|lRef|Aref)\s*:\s*(\S+)", line)  # Read the actual native coefficient normalization.
        if reference:  # Preserve solverdeclared reference quantities.
            scalars[reference.group(1)] = float(reference.group(2))  # Parse the physical reference value.
        if line.startswith("# Time"):  # Read version-dependent coefficient column names.
            names = line[1:].split()  # Avoid relying on hardcoded numerical column offsets.
        if line and not line.startswith("#"):  # Read native values only.
            values = np.fromstring(line, sep=" ")  # Parse a complete native data row.
            if names is None or len(values) != len(names):  # Detect truncated or incompatible output.
                if line_number == len(lines) - 1:  # A live solver may currently be writing its last line.
                    continue  # Ignore only the incomplete trailing live record.
                raise ValueError("malformed native coefficient record")  # Preserve corruption visibility.
            data.append(values)  # Retain every complete physical timestep.
    if not data or not all(key in axes for key in ("rollAxis", "pitchAxis", "yawAxis")):  # Require complete moment-frame evidence.
        raise ValueError("native coefficient data or moment-axis metadata missing")  # Reject untraceable moment signs.
    array = np.asarray(data)  # Keep native adaptive timestep samples.
    columns = {name: array[:, index] for index, name in enumerate(names)}  # Resolve values by native column names.
    moment = sum(columns[column] * axes[axis][2] for column, axis in (("CmRoll", "rollAxis"), ("CmPitch", "pitchAxis"), ("CmYaw", "yawAxis")))  # Project the total coefficient moment onto positiveCFDz=positivebridgeX.
    output = np.column_stack((columns["Time"], columns["Cd"], columns["Cl"], moment))  # Expose a single explicit common reference convention.
    if not np.all(np.isfinite(output)) or np.any(np.diff(output[:, 0]) <= 0):  # Reject divergent fields or duplicate snapshots.
        raise ValueError("invalid native coefficient time series")  # Never average invalid numerical states.
    return output, {**{key: value.tolist() for key, value in axes.items()}, **scalars}  # Preserve the exact axes and coefficient normalization.


def time_average(data, start, stop):  # Integrate adaptive samples using physical time weights.
    if start < data[0, 0] or stop > data[-1, 0] or stop <= start:  # Require actual temporal support.
        raise ValueError("averaging interval is outside native output support")  # Refuse invented startup or future samples.
    inner = data[(data[:, 0] > start) & (data[:, 0] < stop)]  # Keep internal physical samples.
    endpoints = np.array([[time] + [np.interp(time, data[:, 0], data[:, column]) for column in range(1, data.shape[1])] for time in (start, stop)])  # Integrate precise requested interval endpoints.
    block = np.vstack((endpoints[0], inner, endpoints[1]))  # Form the complete interval.
    integrate = getattr(np, "trapezoid", np.trapz)  # Support installedNumPyversions without changing the rule.
    return integrate(block[:, 1:], block[:, 0], axis=0) / (stop - start)  # Return a true time mean rather than sample-count mean.


def summarize(case_path):  # Audit a solved or running native component case.
    case = Path(case_path)  # Locate the actual solver case.
    contract = json.loads((case / "case_contract.json").read_text())  # Retrieve the declared physical scenario.
    native = case / "postProcessing/aero/0/coefficient.dat"  # Read the actual native integrated forces.
    data, axes = read_coefficients(native)  # Apply the solver's declared coordinate convention.
    expected = {"magUInf": contract["speed_mps"], "lRef": contract["reference_width_m"], "Aref": contract["reference_width_m"] * contract["extruded_span_m"]}  # Reconstruct reference scales from committed physical inputs.
    if any(key not in axes or not np.isclose(axes[key], value, rtol=1e-8, atol=1e-12) for key, value in expected.items()):  # Detect native coefficient normalization drift.
        raise ValueError("native coefficient references do not match the case contract")  # Prevent silentlymisnormalized bridge loads.
    np.savetxt(case / "coefficients_common_axes.csv", data, delimiter=",", header="time_s,Cd,Cl,Cm_positive_bridge_x", comments="")  # Export traceable native results forGnuplot/Origin.
    log = (case / "log.pimpleFoam").read_text(errors="replace")  # Inspect actual solver completion.
    requested = float(contract["duration_s"])  # Use the committed requested final time.
    completed = "\nEnd\n" in log and data[-1, 0] >= requested * (1 - 1e-7)  # A graceful earlystop does not count as full completion.
    result = {"status": "SOLVED_COMPONENT_UNVALIDATED" if completed else "RUNNING_OR_PARTIAL_COMPONENT", "full_bridge_wind_coefficients_available": False, "case_scope": contract["geometry_scope"], "requested_final_time_s": requested, "last_native_sample_time_s": float(data[-1, 0]), "native_samples": len(data), "native_coefficient_sha256": hashlib.sha256(native.read_bytes()).hexdigest(), "raw_axis_conventions": axes, "common_moment_definition": "positive CFD z equals positive bridge longitudinal x; projected from raw moment axes", "mesh_check_passed": "Mesh OK." in (case / "log.checkMesh").read_text(), "coefficients_validated_for_bridge_use": False, "mesh_refinement_passed": False, "time_step_refinement_passed": False, "domain_refinement_passed": False, "statistical_stationarity_passed": False}  # Separate execution from physical validation.
    convective_time = float(contract["reference_width_m"]) / float(contract["speed_mps"])  # Convert time into section-width flow-through units.
    result["simulated_convective_times"] = float(data[-1, 0] / convective_time)  # Report actual physical coverage.
    start = requested * 0.5  # Predetermine startup removal before inspecting coefficient values.
    if completed and start >= data[0, 0]:  # Compute means only after the requested duration exists.
        mean = time_average(data, start, requested)  # Use all post-startup time at correct adaptive weights.
        bounds = np.linspace(start, requested, 5)  # Split the averaging window into four predetermined time blocks.
        means = np.array([time_average(data, lower, upper) for lower, upper in zip(bounds[:-1], bounds[1:])])  # Inspect low-frequency drift honestly.
        normalized_spread = np.ptp(means, axis=0) / np.maximum(np.abs(mean), 0.05)  # Avoid dividing near-zero symmetriclift/moment byzero.
        result["averaging_window_s"] = [start, requested]  # Preserve startup-exclusion provenance.
        result["time_mean_Cd_Cl_Cm"] = mean.tolist()  # Report component-only integrated coefficients.
        result["four_block_means_Cd_Cl_Cm"] = means.tolist()  # Keep the descriptive stationarity evidence.
        result["block_spread_normalized_by_max_mean_or_0p05"] = normalized_spread.tolist()  # State the exact normalization rather than vague convergence.
        result["statistical_stationarity_passed"] = bool(np.all(normalized_spread < 0.05) and (requested - start) >= 20 * convective_time)  # Require both minimumcoverage and explicit drift bound.
    (case / "result_summary.json").write_text(json.dumps(result, indent=2) + "\n")  # Keep the result status alongside native output.
    return result  # Permit concise progress reporting.


if __name__ == "__main__":  # Provide a reproducible numerical postprocessor.
    parser = argparse.ArgumentParser()  # Define the nativecase input.
    parser.add_argument("case")  # Accept only an existing solver case.
    arguments = parser.parse_args()  # Read the requestedcase.
    print(json.dumps(summarize(arguments.case), indent=2))  # Report exact solve status without substituting a result.
