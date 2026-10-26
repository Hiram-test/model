#!/usr/bin/env python3
"""Compute fatigue indicators from complete physical stress/strain histories; never invent fatigue life.""" # Scope.
from __future__ import annotations # Stable annotations.
import argparse # Command line interface.
import json # Structured provenance.
from pathlib import Path # File paths.
import numpy as np # Tensor calculations, no plotting.

def tensor_from_six(values: np.ndarray, engineering_shear: bool = False) -> np.ndarray: # Convert XX,YY,ZZ,XY,YZ,ZX convention.
    a = np.asarray(values, dtype=float) # Preserve all physical samples.
    if a.shape[-1] != 6 or not np.isfinite(a).all(): raise ValueError("Expected finite six-component tensors") # Reject missing/corrupt fields.
    out = np.zeros(a.shape[:-1] + (3, 3)) # Allocate symmetric tensors.
    out[..., 0, 0], out[..., 1, 1], out[..., 2, 2] = a[..., 0], a[..., 1], a[..., 2] # Diagonal components.
    factor = 0.5 if engineering_shear else 1.0 # Convert engineering strain if explicitly declared.
    for k, i, j in ((3, 0, 1), (4, 1, 2), (5, 2, 0)): out[..., i, j] = out[..., j, i] = factor * a[..., k] # Fill shear symmetrically.
    return out # Return tensor field.

def normals_fibonacci(count: int = 181) -> np.ndarray: # Deterministic hemisphere for critical-plane search.
    if count < 8: raise ValueError("Use at least eight plane normals") # Prevent meaningless angular search.
    z = (np.arange(count) + 0.5) / count # Uniform hemisphere area.
    phi = np.arange(count) * (np.pi * (3.0 - np.sqrt(5.0))) # Golden-angle azimuth.
    r = np.sqrt(1.0 - z * z) # Unit-sphere radius.
    return np.vstack((np.eye(3), np.column_stack((r * np.cos(phi), r * np.sin(phi), z)))) # Include exact Cartesian normals.

def fatigue_indicators(stress: np.ndarray, strain: np.ndarray, normals: np.ndarray | None = None) -> dict: # Evaluate a complete declared load cycle.
    sig, eps = tensor_from_six(stress), tensor_from_six(strain) # Both use tensor shear convention.
    if sig.shape != eps.shape or sig.ndim != 4 or sig.shape[0] < 3: raise ValueError("Expected matching [time, integration_point, 6] fields with >=3 frames") # Require full histories.
    planes = normals_fibonacci() if normals is None else np.asarray(normals, dtype=float) # Permit angular refinement studies.
    if planes.ndim != 2 or planes.shape[0] == 0 or planes.shape[1] != 3 or not np.isfinite(planes).all() or np.any(np.linalg.norm(planes, axis=1) <= 0): raise ValueError("Plane normals must be finite nonzero 3D vectors") # Reject invalid directions.
    planes = planes / np.linalg.norm(planes, axis=1, keepdims=True) # Normalize plane vectors.
    count = sig.shape[1] # Number of actual integration points.
    best = np.full(count, -np.inf) # Initialize peak search.
    plane = np.zeros((count, 3)) # Store governing orientation.
    amplitude = np.zeros(count) # Store governing strain amplitude.
    maximum = np.zeros(count) # Store governing tensile normal stress.
    for normal in planes: # Stream planes to avoid huge tensor memory.
        sn = np.einsum("i,tnij,j->tn", normal, sig, normal) # Normal stress in MPa.
        en = np.einsum("i,tnij,j->tn", normal, eps, normal) # Normal total strain.
        ea = 0.5 * np.ptp(en, axis=0) # Strain amplitude for the supplied complete cycle.
        sm = np.maximum(0.0, np.max(sn, axis=0)) # SWT tensile maximum clipping.
        swt = sm * ea # SWT parameter in MPa.
        update = swt > best # Preserve deterministic first tie.
        best[update], plane[update], amplitude[update], maximum[update] = swt[update], normal, ea[update], sm[update] # Store governing plane data.
    stress_amplitude = 0.5 * np.ptp(np.asarray(stress), axis=0) # Component stress amplitudes, not a scalar fatigue criterion.
    return {"swt_mpa": best, "critical_normal": plane, "normal_strain_amplitude": amplitude, "normal_stress_max_mpa": maximum, "component_stress_amplitude_mpa": stress_amplitude, "plane_count": len(planes)} # Indicators, not life.

def friction_dissipation(traction: np.ndarray, irreversible_slip: np.ndarray, area: np.ndarray, traction_opposes_slip: bool) -> np.ndarray: # Integrate only verified irreversible contact slip.
    tau, slip, weight = np.asarray(traction, float), np.asarray(irreversible_slip, float), np.asarray(area, float) # Contact quadrature inputs.
    if tau.shape != slip.shape or tau.ndim != 3 or tau.shape[0] < 2 or tau.shape[-1] != 2 or weight.shape != tau.shape[1:2]: raise ValueError("Expected [time, contact_point, 2] tractions/slips and [contact_point] area") # Enforce contact-native alignment.
    if not np.isfinite(tau).all() or not np.isfinite(slip).all() or not np.isfinite(weight).all() or np.any(weight <= 0): raise ValueError("Invalid contact fields or quadrature") # Reject dummy contacts.
    sign = -1.0 if traction_opposes_slip else 1.0 # Explicit native sign convention.
    increments = sign * np.sum(0.5 * (tau[1:] + tau[:-1]) * np.diff(slip, axis=0), axis=-1) # Trapezoidal work per area MPa*mm.
    tolerance = 1e-9 * max(1.0, float(np.max(np.abs(increments)))) # Numerical sign tolerance only.
    if float(np.min(increments)) < -tolerance: raise ValueError("Negative dissipation: verify irreversible slip, traction sign, contact frame and sampling") # Do not hide energy inconsistency.
    return np.cumsum(np.sum(np.maximum(increments, 0.0) * weight, axis=1)) # Cumulative N mm work over genuine interface area.

def swt_life(swt: np.ndarray, calibration: dict | None) -> np.ndarray: # Life calculation requires explicit calibrated strain-life constants.
    if calibration is None or not calibration.get("source") or not calibration.get("material_batch"): raise ValueError("Fatigue life requires traceable material-batch calibration") # Never invent life constants.
    required = ("sigma_f_mpa", "epsilon_f", "b", "c", "young_mpa") # Manson-Coffin/Basquin inputs.
    if any(k not in calibration for k in required): raise ValueError("Missing strain-life calibration parameters") # Fail on incomplete data.
    sf, ef, b, c, young = (float(calibration[k]) for k in required) # Parse supplied constants.
    if not np.isfinite([sf, ef, young, b, c]).all() or min(sf, ef, young) <= 0 or b >= 0 or c >= 0: raise ValueError("Calibration requires positive strengths/moduli and negative exponents") # Basic physical admissibility.
    target = np.asarray(swt, float) # Convert requested indicators.
    if not np.isfinite(target).all() or np.any(target <= 0): raise ValueError("Finite positive SWT required; zero indicator does not establish infinite life") # No unsupported infinite life.
    cycle_range = calibration.get("validated_cycle_range") # Require experimental applicability range.
    if not cycle_range or len(cycle_range) != 2 or not np.isfinite(cycle_range).all() or not 0 < cycle_range[0] < cycle_range[1]: raise ValueError("Require finite positive calibrated cycle range") # Disallow unbounded extrapolation.
    lo, hi = np.full(target.shape, np.log10(2.0 * cycle_range[0])), np.full(target.shape, np.log10(2.0 * cycle_range[1])) # Bracket only calibrated reversals.
    def relation(x): return sf * sf / young * x ** (2.0 * b) + sf * ef * x ** (b + c) # Calibrated SWT relation.
    if np.any(target > relation(2.0 * cycle_range[0])) or np.any(target < relation(2.0 * cycle_range[1])): raise ValueError("SWT outside experimentally validated life range") # No extrapolated lifetime.
    for _ in range(100): # Stable monotone bisection.
        mid = 0.5 * (lo + hi) # Candidate logarithmic reversal count.
        rev = np.power(10.0, mid) # Reversal count equals twice cycle count.
        predicted = sf * sf / young * rev ** (2.0 * b) + sf * ef * rev ** (b + c) # SWT strain-life relation.
        lo, hi = np.where(predicted > target, mid, lo), np.where(predicted > target, hi, mid) # Narrow bracket.
    return 0.5 * np.power(10.0, 0.5 * (lo + hi)) # Cycles, subject to calibration applicability.

def main() -> None: # Command line postprocessor.
    parser = argparse.ArgumentParser(description=__doc__) # Explain scope.
    parser.add_argument("input", type=Path) # NPZ stress/strain/times.
    parser.add_argument("output", type=Path) # Output indicators and provenance.
    parser.add_argument("--metadata", required=True, type=Path) # Complete-cycle and field metadata.
    args = parser.parse_args() # Parse arguments.
    meta = json.loads(args.metadata.read_text()) # Read authoritative field metadata.
    if meta.get("solver_status") != "CONVERGED" or not meta.get("complete_cycle") or meta.get("strain_shear_convention") != "tensor": raise ValueError("Need converged complete-cycle physical fields with tensor strain shear") # Training/fatigue gate.
    if not meta.get("source_input_sha256") or not meta.get("source_result_sha256"): raise ValueError("Missing native source hashes") # Provenance gate.
    if meta.get("tensor_component_order") != ["XX", "YY", "ZZ", "XY", "YZ", "ZX"]: raise ValueError("Explicit tensor component order XX YY ZZ XY YZ ZX required; reorder native fields first") # Prevent silent shear swap.
    if meta.get("tensor_frame") != "material_corotated" or meta.get("stress_measure") != "Cauchy" or meta.get("strain_measure") != "Hencky_log_U": raise ValueError("Native NLGEOM stress and strain require objective same-frame conversion before SWT") # Do not project incompatible spatial/reference tensors.
    data = np.load(args.input, allow_pickle=False) # Safe numeric data.
    result = fatigue_indicators(data["stress"], data["strain"]) # Preserve all integration points.
    args.output.parent.mkdir(parents=True, exist_ok=True) # Create output folder.
    np.savez_compressed(args.output, **result) # Save actual indicator arrays.
    summary = {"status": "INDICATORS_ONLY", "source_metadata": meta, "peak_swt_mpa": float(np.max(result["swt_mpa"])), "fatigue_life_cycles": None, "life_blocker": "No calibrated wire fatigue/material-batch input supplied; SWT is not fatigue life.", "fretting_work": "Requires irreversible slip and native contact quadrature; CDIS alone is insufficient."} # Honest field semantics.
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n") # Save machine-readable limitations.

if __name__ == "__main__": main() # Execute CLI only on direct invocation.
