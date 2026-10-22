from __future__ import annotations  # Enable postponed evaluation of type annotations for Python 3.11+ compatibility.
from typing import Any  # Type JSON-shaped mechanics receipts without hiding their dynamic fields.
import numpy as np  # Perform deterministic beam-field algebra and numerical integration.
from contracts import DrawingIR, SensorField, _require  # Import typed source contracts and fail-closed validation.
def _cumtrapz(values: np.ndarray, x_m: np.ndarray) -> np.ndarray:  # Compute a cumulative trapezoidal integral without hidden smoothing.
    increments = 0.5 * (values[1:] + values[:-1]) * np.diff(x_m)  # Integrate each adjacent interval.
    return np.concatenate((np.asarray([0.0]), np.cumsum(increments)))  # Prefix the exact zero integral at the left boundary.
def beam_deflection(x_m: np.ndarray, inertia_m4: np.ndarray, load_q_n_per_m: float, modulus_pa: float) -> np.ndarray:  # Solve the static simple-beam field.
    _require(x_m.ndim == 1 and inertia_m4.shape == x_m.shape, "beam field arrays are inconsistent")  # Validate the discretized field.
    _require(bool(np.all(np.diff(x_m) > 0.0)), "beam grid must be strictly increasing")  # Require a valid integration coordinate.
    _require(bool(np.all(inertia_m4 > 0.0) and modulus_pa > 0.0), "beam stiffness must be positive")  # Enforce physical stiffness.
    span_m = float(x_m[-1] - x_m[0])  # Read the support-to-support span from the grid.
    local_x = x_m - x_m[0]  # Express the grid in the simple-beam coordinate system.
    moment_nm = 0.5 * load_q_n_per_m * local_x * (span_m - local_x)  # Evaluate the statically determinate bending moment field.
    second_derivative = -moment_nm / (modulus_pa * inertia_m4)  # Apply the Euler-Bernoulli relation with downward displacement positive.
    integral_second = _cumtrapz(second_derivative, local_x)  # Integrate the second derivative once.
    integral_x_second = _cumtrapz(local_x * second_derivative, local_x)  # Integrate x times the second derivative once.
    slope_constant = -(span_m * integral_second[-1] - integral_x_second[-1]) / span_m  # Enforce zero displacement at the right support.
    displacement_m = local_x * integral_second - integral_x_second + slope_constant * local_x  # Reconstruct the displacement field satisfying both support conditions.
    return displacement_m  # Return the downward static displacement field.
def _intervals_overlap(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:  # Test deterministic interval consistency.
    return max(low_a, low_b) <= min(high_a, high_b) + 1.0e-15  # Allow only machine-scale slack.
def _check_boundary_form(sensors: SensorField, span_m: float) -> tuple[bool, list[dict[str, Any]]]:  # Verify that support measurements admit zero displacement.
    checks: list[dict[str, Any]] = []  # Accumulate explicit boundary receipts.
    for target, label in ((0.0, "left_support"), (span_m, "right_support")):  # Check both simple supports.
        index = int(np.argmin(np.abs(sensors.x_m - target)))  # Locate the sensor nearest the support coordinate.
        _require(abs(float(sensors.x_m[index]) - target) <= 1.0e-9, f"missing sensor at {label}")  # Require direct boundary evidence.
        low = float(sensors.displacement_m[index] - sensors.bound_m[index])  # Form the lower displacement bound.
        high = float(sensors.displacement_m[index] + sensors.bound_m[index])  # Form the upper displacement bound.
        admits_zero = low <= 0.0 <= high  # Test the simple-support boundary condition.
        checks.append({"location": label, "sensor_id": sensors.sensor_id[index], "interval_m": [low, high], "admits_zero": admits_zero})  # Record the result.
    return all(item["admits_zero"] for item in checks), checks  # Return the combined boundary decision and its evidence.
def _check_symmetry_form(sensors: SensorField, span_m: float) -> tuple[bool, list[dict[str, Any]]]:  # Verify mirror symmetry implied by drawing and loading.
    checks: list[dict[str, Any]] = []  # Accumulate explicit pairwise symmetry receipts.
    visited: set[int] = set()  # Avoid checking the same mirror pair twice.
    for index, x_value in enumerate(sensors.x_m):  # Visit sensors in longitudinal order.
        if index in visited:  # Skip a sensor already consumed by a mirror pair.
            continue  # Move to the next sensor.
        mirror_x = span_m - float(x_value)  # Compute the drawing-implied mirror coordinate.
        mirror_index = int(np.argmin(np.abs(sensors.x_m - mirror_x)))  # Locate the measured mirror sensor.
        _require(abs(float(sensors.x_m[mirror_index]) - mirror_x) <= 1.0e-9, "sensor layout lacks a mirror pair")  # Require complete symmetric coverage.
        visited.add(index)  # Mark the current sensor as checked.
        visited.add(mirror_index)  # Mark the mirror sensor as checked.
        low_a = float(sensors.displacement_m[index] - sensors.bound_m[index])  # Form the first sensor lower bound.
        high_a = float(sensors.displacement_m[index] + sensors.bound_m[index])  # Form the first sensor upper bound.
        low_b = float(sensors.displacement_m[mirror_index] - sensors.bound_m[mirror_index])  # Form the mirror lower bound.
        high_b = float(sensors.displacement_m[mirror_index] + sensors.bound_m[mirror_index])  # Form the mirror upper bound.
        overlaps = _intervals_overlap(low_a, high_a, low_b, high_b)  # Test whether a symmetric true response can satisfy both measurements.
        checks.append({"sensor_a": sensors.sensor_id[index], "sensor_b": sensors.sensor_id[mirror_index], "overlaps": overlaps})  # Record the pairwise result.
    return all(item["overlaps"] for item in checks), checks  # Return the combined symmetry decision and its evidence.
def _parameter_interval(basis_m: np.ndarray, current_prediction_m: np.ndarray, sensors: SensorField) -> tuple[bool, float, float, list[dict[str, Any]]]:  # Convert measurement bounds into a feasible dimensionless compliance increment.
    interval_rows: list[dict[str, Any]] = []  # Store each sensor's admissible parameter interval.
    lower_values: list[float] = []  # Accumulate lower interval endpoints.
    upper_values: list[float] = []  # Accumulate upper interval endpoints.
    for index, basis_value in enumerate(basis_m):  # Process every measured response equation.
        if abs(float(basis_value)) <= 1.0e-14:  # Treat support locations as boundary checks rather than parameter equations.
            continue  # Skip the zero response signature.
        measurement_low = float(sensors.displacement_m[index] - sensors.bound_m[index])  # Form the deterministic lower response bound.
        measurement_high = float(sensors.displacement_m[index] + sensors.bound_m[index])  # Form the deterministic upper response bound.
        raw_a = (measurement_low - float(current_prediction_m[index])) / float(basis_value)  # Map the lower response bound into parameter space.
        raw_b = (measurement_high - float(current_prediction_m[index])) / float(basis_value)  # Map the upper response bound into parameter space.
        interval_low = min(raw_a, raw_b)  # Preserve interval orientation for any response sign.
        interval_high = max(raw_a, raw_b)  # Preserve interval orientation for any response sign.
        lower_values.append(interval_low)  # Add the sensor lower bound to the global intersection.
        upper_values.append(interval_high)  # Add the sensor upper bound to the global intersection.
        interval_rows.append({"sensor_id": sensors.sensor_id[index], "delta_p_interval": [interval_low, interval_high]})  # Record the sensor-level parameter evidence.
    _require(len(lower_values) > 0, "no interior sensor has a usable response signature")  # Reject a boundary-only measurement layout.
    global_low = max(lower_values)  # Intersect all sensor lower bounds.
    global_high = min(upper_values)  # Intersect all sensor upper bounds.
    return global_low <= global_high + 1.0e-15, global_low, global_high, interval_rows  # Return feasibility and the exact deterministic intersection.
def _solve_with_inertia(drawing: DrawingIR, sensors: SensorField, analysis_x_m: np.ndarray, inertia_m4: np.ndarray) -> dict[str, Any]:  # Apply the formal global-modulus update rule to a fixed geometry field.
    basis_field_m = beam_deflection(analysis_x_m, inertia_m4, drawing.load_q_n_per_m, drawing.reference_modulus_pa)  # Compute the response signature for p=E_ref/E.
    basis_sensor_m = np.interp(sensors.x_m, analysis_x_m, basis_field_m)  # Restrict the response signature to measurement coordinates.
    current_p = drawing.reference_modulus_pa / drawing.initial_modulus_pa  # Express the current modulus as a dimensionless compliance multiplier.
    current_prediction_m = current_p * basis_sensor_m  # Evaluate the current model response without refitting anything.
    feasible, delta_low, delta_high, sensor_intervals = _parameter_interval(basis_sensor_m, current_prediction_m, sensors)  # Intersect all bounded-error equations.
    result: dict[str, Any] = {"feasible": feasible, "current_p": current_p, "delta_p_interval": [delta_low, delta_high], "sensor_parameter_intervals": sensor_intervals}  # Start the formal update result.
    if not feasible:  # Handle an error field outside the global-modulus response signature.
        return result  # Return a rejection without inventing a best-fit modulus.
    p_low = current_p + delta_low  # Form the lower feasible updated multiplier.
    p_high = current_p + delta_high  # Form the upper feasible updated multiplier.
    _require(p_low > 0.0 and p_high > 0.0, "feasible update would produce non-positive modulus")  # Enforce physical admissibility.
    selected_p = 0.5 * (p_low + p_high)  # Choose the deterministic centre of the feasible interval for an executable representative.
    modulus_low_pa = drawing.reference_modulus_pa / p_high  # Invert the upper multiplier to obtain the lower modulus bound.
    modulus_high_pa = drawing.reference_modulus_pa / p_low  # Invert the lower multiplier to obtain the upper modulus bound.
    selected_modulus_pa = drawing.reference_modulus_pa / selected_p  # Convert the representative multiplier back to Young's modulus.
    selected_prediction_m = selected_p * basis_sensor_m  # Evaluate the representative updated response.
    measurement_low_m = sensors.displacement_m - sensors.bound_m  # Form all lower measurement bounds.
    measurement_high_m = sensors.displacement_m + sensors.bound_m  # Form all upper measurement bounds.
    postcondition = bool(np.all(selected_prediction_m >= measurement_low_m - 1.0e-15) and np.all(selected_prediction_m <= measurement_high_m + 1.0e-15))  # Check interval consistency after updating.
    result.update({"updated_p_interval": [p_low, p_high], "modulus_interval_pa": [modulus_low_pa, modulus_high_pa], "selected_modulus_pa": selected_modulus_pa, "postcondition_all_measurements_satisfied": postcondition, "basis_sensor_m": basis_sensor_m.tolist(), "current_prediction_m": current_prediction_m.tolist(), "updated_prediction_m": selected_prediction_m.tolist()})  # Complete the accepted update receipt.
    return result  # Return the formal parameter update result.
