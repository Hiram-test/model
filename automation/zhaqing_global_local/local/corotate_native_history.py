#!/usr/bin/env python3
"""Put native Cauchy stress and finite strain in one material-corotated frame before fatigue projection.""" # Scope.
import argparse # CLI.
import hashlib # Native field provenance.
import json # Metadata.
from pathlib import Path # Paths.
import numpy as np # Tensor algebra, no visualization.
from fatigue_indicators import tensor_from_six # Explicit public shear convention.
from quadratic_solid import gauss_shape # Exact native C3D20R kinematics when quadratic nodes are present.

def six(tensor: np.ndarray) -> np.ndarray: # Return XX YY ZZ XY YZ ZX tensor components.
    return np.stack([tensor[..., 0, 0], tensor[..., 1, 1], tensor[..., 2, 2], tensor[..., 0, 1], tensor[..., 1, 2], tensor[..., 2, 0]], axis=-1) # Preserve public order.

def corotate(stress: np.ndarray, deformation: np.ndarray) -> tuple[np.ndarray, np.ndarray]: # Objective finite-rotation material-frame fields.
    f = np.asarray(deformation, float) # Deformation gradient in reference basis.
    if not np.isfinite(f).all() or np.any(np.linalg.det(f) <= 0): raise ValueError("Invalid deformation gradient") # Reject inverted/degenerated kinematics.
    c = np.swapaxes(f, -1, -2) @ f # Right Cauchy-Green tensor.
    eigenvalues, eigenvectors = np.linalg.eigh(c) # Principal squared stretches.
    if np.any(eigenvalues <= 0): raise ValueError("Nonpositive principal stretch") # Logarithmic strain requires positive stretch.
    inverse_u = (eigenvectors * (1.0 / np.sqrt(eigenvalues))[..., None, :]) @ np.swapaxes(eigenvectors, -1, -2) # Inverse right stretch.
    rotation = f @ inverse_u # Polar rotation R.
    sig = tensor_from_six(stress) # Native Cauchy stress as symmetric tensor.
    sigma_material = np.swapaxes(rotation, -1, -2) @ sig @ rotation # Corotated Cauchy stress in material axes.
    hencky = (eigenvectors * (0.5 * np.log(eigenvalues))[..., None, :]) @ np.swapaxes(eigenvectors, -1, -2) # Material logarithmic strain log(U).
    return six(sigma_material), six(hencky) # Compatible tensors for plane projections.

def read_displacements(frd: Path, requested: np.ndarray, node_count: int) -> dict: # Native FRD displacement extraction.
    result, time, active, values, seen = {}, None, False, None, None # Stream parser state.
    with frd.open() as stream: # Full native result source.
        for line in stream: # Preserve result frames without interpolation.
            if line.startswith("  100CL"): time = float(line.split()[2]) # Native result time.
            elif line.startswith(" -4"): # Result-field selection.
                active = line.split()[1] == "DISP" and time is not None and np.min(np.abs(requested - time)) < 1e-6 # Select matching full cycle.
                if active: values = np.zeros((node_count, 3)); seen = np.zeros(node_count, dtype=bool) # Track every physical node.
            elif active and line.startswith(" -1"): # Native fixed-width nodal record.
                idx = int(line[3:13]) - 1 # Convert one-based actual node identifier.
                if not 0 <= idx < node_count: raise ValueError("FRD node outside mesh") # Reject mismatched model.
                values[idx] = [float(line[13 + 12 * j:25 + 12 * j]) for j in range(3)]; seen[idx] = True # Decode three displacements.
            elif active and line.startswith(" -3"): # End of actual displacement field.
                if not seen.all(): raise ValueError("Incomplete physical nodal displacements") # No zero-filling absent outputs.
                result[float(requested[np.argmin(abs(requested - time))])] = values; active = False # Bind exact requested native time.
    if len(result) != len(requested): raise ValueError("Missing displacement frames needed for objective fatigue tensors") # Require complete same-time kinematics.
    return result # Return full physical fields.

def main() -> None: # Native finite-kinematics conversion.
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("folder", type=Path); p.add_argument("--job", default="saddle") # Source folder and result stem.
    a = p.parse_args(); d = np.load(a.folder / "cycle_fields.npz", allow_pickle=False); mesh = np.load(a.folder / "geometry.npz", allow_pickle=False) # Load native-derived tensors and actual mesh.
    meta = json.loads((a.folder / "cycle_fields.json").read_text()); points = d["element_ip_ids"] # Stable actual element/IP identities.
    nodes, cells, times = mesh["coordinates"], mesh["connectivity"], d["times"] # Full physical mesh and time coordinates.
    displacement = read_displacements(a.folder / f"{a.job}.frd", times, len(nodes)) # No inferred nodal kinematics.
    signs = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], float) # Native C3D8 reference ordering.
    gradients = [] # Natural derivatives for all8 integration points.
    for q in signs[[0,1,3,2,4,5,7,6]] / np.sqrt(3.0): # Exact CalculiX gauss3d2 point order, not the corner-node order.
        g = np.empty((8, 3)) # Shape derivative matrix.
        for k in range(3): axes = [j for j in range(3) if j != k]; g[:, k] = signs[:, k] / 8.0 * np.prod(1.0 + signs[:, axes] * q[axes], axis=1) # Tensor-product derivatives.
        gradients.append(g) # Preserve native IP order.
    if cells.shape[1] == 20: _, gradients = gauss_shape() # Replace corner-only kinematics with all twenty actual quadratic nodes.
    elif cells.shape[1] != 8: raise ValueError('Only validated C3D8 and C3D20R kinematics are supported') # Refuse unknown element interpolation.
    conn = cells[points[:, 0] - 1]; grad_nat = np.asarray(gradients)[points[:, 1] - 1] # All actual integration-point geometry.
    jac = np.einsum("eni,enj->eij", nodes[conn], grad_nat) # Reference geometric Jacobians.
    grad = grad_nat @ np.linalg.inv(jac) # Physical reference shape gradients.
    all_stress, all_strain, max_j = [], [], [] # Objective field histories.
    for k, time in enumerate(times): # Every complete-cycle time frame.
        f = np.eye(3) + np.einsum("eni,enj->eij", displacement[float(time)][conn], grad) # F=I+Grad(u), no small-rotation approximation.
        s, e = corotate(d["stress"][k], f); all_stress.append(s); all_strain.append(e); max_j.append([float(np.min(np.linalg.det(f))), float(np.max(np.linalg.det(f)))]) # Store compatible fields and kinematic check.
    output = a.folder / "cycle_corotated.npz"; np.savez_compressed(output, stress=np.asarray(all_stress), strain=np.asarray(all_strain), times=times, element_ip_ids=points) # Preserve all IP/time fields.
    meta.update({"tensor_frame": "material_corotated", "stress_measure": "Cauchy", "strain_measure": "Hencky_log_U", "kinematics": f"F from all native nodal displacements and {'C3D20R' if cells.shape[1] == 20 else 'C3D8'} reference shape gradients; polar decomposition", "native_frd_sha256": hashlib.sha256((a.folder / f"{a.job}.frd").read_bytes()).hexdigest(), "jacobian_determinant_range_by_frame": max_j, "cycle_stabilized": False, "cycle_scope": "first complete prescribed load cycle; no repeated-cycle stabilization claim"}) # Explicit finite-rotation semantics.
    output.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n") # Save corrected field contract.
    print(json.dumps({"frames": len(times), "integration_points": len(points), "output": str(output)})) # Summarize actual conversion.

if __name__ == "__main__": main() # Execute CLI.
