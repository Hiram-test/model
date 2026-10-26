"""Conservative global/local boundary transfer in N, mm, s; no field reduction."""  # State units and scope.
from __future__ import annotations  # Keep type annotations independent of import order.
import numpy as np  # Use numerical algebra only; this module never renders figures.


def _array(value, shape, name):  # Validate finite physical arrays before any boundary calculation.
    result = np.asarray(value, dtype=float)  # Normalize caller data without changing units.
    if result.shape != shape or not np.isfinite(result).all():  # Refuse missing components and invalid numbers.
        raise ValueError(f"{name} must have finite shape {shape}")  # Identify the offending boundary input.
    return result  # Return the validated physical array.


def rigid_cut_displacements(points_mm, center_mm, translation_mm, rotation):  # Transfer a finite rigid-section motion to every explicit cut node.
    points = np.asarray(points_mm, dtype=float)  # Preserve all physical cut nodes rather than choosing representatives.
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():  # Require complete Cartesian locations.
        raise ValueError("points_mm must be a finite N by 3 array")  # Reject malformed mesh data.
    center = _array(center_mm, (3,), "center_mm")  # Locate the parent section reference point.
    translation = _array(translation_mm, (3,), "translation_mm")  # Read the reference-point translation.
    matrix = _array(rotation, (3, 3), "rotation")  # Read the exact finite rotation matrix.
    if not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-10, rtol=0) or abs(np.linalg.det(matrix) - 1) > 1e-10:  # Require a proper rotation, excluding shear and reflection.
        raise ValueError("rotation must be proper orthogonal")  # Avoid distorting a cut under the name of rotation.
    return translation + (points - center) @ (matrix - np.eye(3)).T  # Compute finite-displacement kinematics for every node.


def conservative_cut_forces(points_mm, area_weights_mm2, center_mm, force_n, moment_nmm):  # Distribute section actions while preserving both force and moment.
    points = np.asarray(points_mm, dtype=float)  # Retain every explicitly modelled cut location.
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or len(points) < 3:  # Require a finite spatial cross-section.
        raise ValueError("at least three finite Cartesian cut points are required")  # Refuse a single equivalent cable node.
    areas = _array(area_weights_mm2, (len(points),), "area_weights_mm2")  # Read tributary areas from the actual mesh.
    if np.any(areas <= 0):  # Ensure positive integration measures.
        raise ValueError("all cut tributary areas must be positive")  # Avoid negative quadrature or unloaded placeholder wires.
    center = _array(center_mm, (3,), "center_mm")  # Set the common origin for moment conservation.
    target = np.concatenate((_array(force_n, (3,), "force_n"), _array(moment_nmm, (3,), "moment_nmm")))  # Assemble requested physical section actions.
    radius = points - center  # Form each moment arm in millimetres.
    characteristic = max(float(np.sqrt(np.average(np.sum(radius ** 2, axis=1), weights=areas))), 1e-9)  # Scale force and moment constraints consistently.
    operator = np.zeros((6, 3 * len(points)))  # Allocate the exact resultant map without deleting cut degrees of freedom.
    for index, (x, y, z) in enumerate(radius):  # Assemble the contribution of each explicit force vector.
        operator[:3, 3 * index:3 * index + 3] = np.eye(3)  # Sum all nodal forces.
        operator[3:, 3 * index:3 * index + 3] = np.array(((0, -z, y), (z, 0, -x), (-y, x, 0))) / characteristic  # Sum r cross f with dimensionally balanced rows.
    scaled_target = target.copy()  # Preserve the original physical target for output checks.
    scaled_target[3:] /= characteristic  # Match the moment-row scaling.
    weights = np.repeat(areas / areas.sum(), 3)  # Use tributary area as the minimum complementary-norm weight.
    gram = (operator * weights) @ operator.T  # Form the six-constraint system, not a reduced structural model.
    if np.linalg.matrix_rank(gram, tol=1e-12 * np.linalg.norm(gram, 2)) != 6:  # Require the cross-section to support arbitrary section actions.
        raise ValueError("cut geometry cannot independently transmit all six resultants")  # Refuse a rank-deficient boundary transfer.
    nodal = (weights * (operator.T @ np.linalg.solve(gram, scaled_target))).reshape(-1, 3)  # Recover area-weighted least-norm nodal traction forces.
    residual = operator @ nodal.ravel() - scaled_target  # Independently check every conserved section action.
    if np.linalg.norm(residual) > 1e-9 * max(np.linalg.norm(scaled_target), 1):  # Reject unstable numerical transfer.
        raise ArithmeticError("boundary force/moment conservation failed")  # Prevent loading an inconsistent local problem.
    return nodal  # Return every cut force, retaining local contact and warping degrees of freedom.


def validate_boundary_constraints(prescribed_dofs, force_dofs):  # Prohibit simultaneously driving one cut degree with prescribed motion and a target traction.
    prescribed = {tuple(item) for item in prescribed_dofs}  # Normalize explicit node/direction pairs.
    loaded = {tuple(item) for item in force_dofs}  # Normalize the force-driven pairs.
    overlap = prescribed & loaded  # Detect target forces that would only become support reactions.
    if overlap:  # Fail before launching a falsely coupled solve.
        raise ValueError(f"force and displacement prescribed on the same degrees: {sorted(overlap)[:10]}")  # Expose conflicting degrees without hiding them.
    return True  # Confirm the boundary declaration is not overconstrained by this coupling interface.
