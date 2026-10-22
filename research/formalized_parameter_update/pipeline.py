from __future__ import annotations  # Enable postponed evaluation of type annotations for Python 3.11+ compatibility.
import json  # Serialize the complete formal update receipt and human-readable report.
from pathlib import Path  # Represent all input and output paths portably.
from typing import Any  # Type JSON-shaped result dictionaries.
import numpy as np  # Build deterministic analysis grids and geometry interpolants.
from contracts import _sha256, load_drawing_ir, load_point_cloud, load_sensors  # Compile and trace all three source modalities.
from mechanics import _check_boundary_form, _check_symmetry_form, _solve_with_inertia  # Apply mechanics-form checks and interval updating.
def formalize_and_update(drawing_path: Path, point_cloud_path: Path, sensor_path: Path) -> dict[str, Any]:  # Execute the complete drawing-point-cloud-sensor pipeline.
    drawing = load_drawing_ir(drawing_path)  # Formalize drawing semantics first.
    geometry = load_point_cloud(point_cloud_path, drawing)  # Formalize actual geometry second.
    sensors = load_sensors(sensor_path, drawing)  # Formalize bounded sensor observations third.
    boundary_ok, boundary_checks = _check_boundary_form(sensors, drawing.span_m)  # Test whether the error field respects support conditions.
    symmetry_ok, symmetry_checks = _check_symmetry_form(sensors, drawing.span_m) if drawing.symmetry_expected else (True, [])  # Test drawing-implied mirror symmetry.
    analysis_x_m = np.linspace(0.0, drawing.span_m, 2001)  # Create a deterministic integration grid independent of the sensor layout.
    actual_inertia_m4 = np.interp(analysis_x_m, geometry.x_m, geometry.inertia_m4)  # Interpolate measured section inertia onto the mechanics grid.
    nominal_inertia_value_m4 = drawing.nominal_width_m * drawing.nominal_depth_m ** 3.0 / 12.0  # Compute the drawing-only section inertia.
    nominal_inertia_m4 = np.full_like(analysis_x_m, nominal_inertia_value_m4)  # Create the counterfactual drawing-only inertia field.
    geometry_symmetric = bool(np.max(np.abs(actual_inertia_m4 - actual_inertia_m4[::-1])) <= 1.0e-8 * max(float(np.max(actual_inertia_m4)), 1.0e-18))  # Test whether point-cloud geometry preserves expected symmetry.
    max_camber_ratio = float(np.max(np.abs(geometry.centerline_z_m)) / drawing.span_m)  # Measure unloaded camber relative to span.
    actual_result = _solve_with_inertia(drawing, sensors, analysis_x_m, actual_inertia_m4) if boundary_ok and symmetry_ok and geometry_symmetric else {"feasible": False, "blocked_by_form": True}  # Apply the update only after form checks pass.
    nominal_result = _solve_with_inertia(drawing, sensors, analysis_x_m, nominal_inertia_m4) if boundary_ok and symmetry_ok else {"feasible": False, "blocked_by_form": True}  # Compute a diagnostic counterfactual using drawing geometry only.
    width_mean_m = float(np.mean(geometry.width_m))  # Summarize the measured section width.
    depth_mean_m = float(np.mean(geometry.depth_m))  # Summarize the measured section depth.
    inertia_mean_m4 = float(np.mean(geometry.inertia_m4))  # Summarize the measured section inertia.
    geometry_changed = bool(abs(width_mean_m - drawing.nominal_width_m) > 1.0e-6 or abs(depth_mean_m - drawing.nominal_depth_m) > 1.0e-6)  # Determine whether geometry must precede material updating.
    status = "UPDATED" if actual_result.get("feasible") and actual_result.get("postcondition_all_measurements_satisfied") else "REJECTED"  # Set the final fail-closed decision.
    reason = "global modulus error form is mechanically consistent" if status == "UPDATED" else "measurement error is not admissible for a global modulus update"  # State the decision in direct engineering language.
    return {  # Build the complete machine-readable update receipt.
        "schema_version": "0.1",  # Version the result contract.
        "status": status,  # Record whether the parameter update was executed or rejected.
        "decision_reason": reason,  # Record the mechanics-level reason.
        "sources": {"drawing_contract_sha256": _sha256(drawing_path), "drawing_source_name": drawing.source_name, "drawing_source_declared_sha256": drawing.source_sha256, "point_cloud_sha256": geometry.source_sha256, "sensor_sha256": sensors.source_sha256},  # Bind the receipt to exact inputs.
        "formal_structure": {"type": "simply_supported_euler_bernoulli_beam", "span_m": drawing.span_m, "supports": [drawing.left_support, drawing.right_support], "load": {"type": "full_span_udl", "q_n_per_m": drawing.load_q_n_per_m}, "parameter_candidate": "uniform_youngs_modulus", "initial_modulus_pa": drawing.initial_modulus_pa, "reference_modulus_pa": drawing.reference_modulus_pa},  # Record the mechanics object compiled from visual semantics.
        "geometry_form": {"precedence": "point_cloud_geometry_before_material_update", "geometry_changed_from_drawing": geometry_changed, "nominal_width_m": drawing.nominal_width_m, "measured_mean_width_m": width_mean_m, "nominal_depth_m": drawing.nominal_depth_m, "measured_mean_depth_m": depth_mean_m, "nominal_inertia_m4": nominal_inertia_value_m4, "measured_mean_inertia_m4": inertia_mean_m4, "inertia_ratio_measured_to_nominal": inertia_mean_m4 / nominal_inertia_value_m4, "max_unloaded_camber_to_span": max_camber_ratio, "mirror_symmetric": geometry_symmetric},  # Record how point cloud changed the mechanics geometry.
        "measurement_error_form": {"boundary_form": "zero_displacement_admitted_at_both_supports", "boundary_form_satisfied": boundary_ok, "boundary_checks": boundary_checks, "symmetry_form": "mirror_about_midspan", "symmetry_form_satisfied": symmetry_ok, "symmetry_checks": symmetry_checks, "mechanical_signature": "error belongs to span of the reference global-compliance response"},  # Record the typed measured-error object.
        "parameter_update": actual_result,  # Record the accepted interval update or explicit rejection.
        "drawing_only_counterfactual": nominal_result,  # Show the material bias that would result from ignoring point-cloud geometry.
        "postcondition": {"target_error_form_removed_within_measurement_bounds": bool(actual_result.get("postcondition_all_measurements_satisfied", False)), "unexplained_error_preserved_instead_of_forced_into_parameter": status == "REJECTED"},  # Record the update rule's formal postcondition.
    }  # Finish the update receipt.
def render_markdown(receipt: dict[str, Any]) -> str:  # Render a compact human-readable engineering report.
    lines: list[str] = []  # Accumulate report lines.
    lines.append("# 实测误差形式化参数更新结果")  # Add the report title.
    lines.append("")  # Add a readable separator.
    lines.append(f"- 状态：**{receipt['status']}**")  # State the fail-closed decision.
    lines.append(f"- 判定：{receipt['decision_reason']}")  # State the mechanics reason.
    geometry = receipt["geometry_form"]  # Read the geometry formalization block.
    lines.append(f"- 图纸截面：{geometry['nominal_width_m']:.3f} m × {geometry['nominal_depth_m']:.3f} m")  # Report nominal geometry.
    lines.append(f"- 点云截面均值：{geometry['measured_mean_width_m']:.3f} m × {geometry['measured_mean_depth_m']:.3f} m")  # Report measured geometry.
    lines.append(f"- 点云/图纸惯性矩比：{geometry['inertia_ratio_measured_to_nominal']:.6f}")  # Report the geometric correction magnitude.
    update = receipt["parameter_update"]  # Read the actual-geometry update block.
    if update.get("feasible"):  # Render accepted parameter bounds.
        interval = update["modulus_interval_pa"]  # Read the feasible modulus interval.
        selected = update["selected_modulus_pa"]  # Read the deterministic representative modulus.
        lines.append(f"- 更新前弹性模量：{receipt['formal_structure']['initial_modulus_pa'] / 1.0e9:.3f} GPa")  # Report the current model parameter before updating.
        lines.append(f"- 更新后弹性模量区间：[{interval[0] / 1.0e9:.3f}, {interval[1] / 1.0e9:.3f}] GPa")  # Report the deterministic feasible modulus interval.
        lines.append(f"- 执行代表值：{selected / 1.0e9:.3f} GPa")  # Report the executable centre of the feasible set.
        lines.append(f"- 后置条件：所有更新后响应均落入传感器确定性误差带 = {update['postcondition_all_measurements_satisfied']}")  # Report the formal postcondition.
    else:  # Render a formal rejection.
        lines.append("- 参数更新被拒绝：不存在同时满足全部传感器误差带的全局弹性模量增量。")  # Explain why no best-fit value is returned.
    counterfactual = receipt["drawing_only_counterfactual"]  # Read the drawing-only diagnostic.
    if counterfactual.get("feasible"):  # Render the geometry-misattribution comparison.
        lines.append(f"- 忽略点云、只用图纸截面时会得到：{counterfactual['selected_modulus_pa'] / 1.0e9:.3f} GPa")  # Show the causal value of point-cloud geometry.
    lines.append("")  # Add a readable separator.
    lines.append("该结果不是最小化残差得到的最优点，而是图纸约束、点云几何和传感器误差带共同允许的参数更新区间。")  # State the core methodological distinction.
    return "\n".join(lines) + "\n"  # Return a newline-terminated Markdown report.
def write_outputs(receipt: dict[str, Any], output_dir: Path) -> None:  # Persist both machine-readable and human-readable evidence.
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory deterministically.
    (output_dir / "formal_update_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")  # Write the full formal receipt.
    (output_dir / "REPORT.md").write_text(render_markdown(receipt), encoding="utf-8")  # Write the concise engineering report.
