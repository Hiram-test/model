#!/usr/bin/env python3
"""Extract complete converged native integration-point histories, with explicit shear order and cycle bounds.""" # Scope.
from __future__ import annotations # Stable annotations.
import argparse # CLI options.
import hashlib # Source identity.
import json # Metadata.
import re # Native header parsing.
from pathlib import Path # File paths.
import numpy as np # Numeric extraction, no plots.

def extract(dat: Path, inp: Path, log: Path, output: Path, cycle_start: float, cycle_end: float, wire_count: int) -> dict: # Native history admission boundary.
    text = log.read_text(errors="replace") # Final solver receipt.
    if "Job finished" not in text or "*ERROR" in text: raise ValueError("Native solver has not completed successfully; partial fields cannot be fatigue/training labels") # Reject failed or running solver.
    completion=json.loads((dat.parent/'native_completion.json').read_text()); identity=hashlib.sha256(inp.read_bytes()).hexdigest() # Require the actual process exit and terminal-increment audit.
    if not completion.get('field_export_admitted') or completion.get('input_sha256')!=identity: raise ValueError('Complete native process receipt does not match this input') # Prevent stale result admission.
    mesh=np.load(dat.parent/'geometry.npz',allow_pickle=False); physical_wire_ids=mesh['wire_id']; native_wire_elements=np.flatnonzero(physical_wire_ids>0)+1 # Recover every declared wire element from the exact physical mesh.
    if len(np.unique(physical_wire_ids[physical_wire_ids>0]))!=wire_count or mesh['connectivity'].shape[1] not in (8,20): raise ValueError('Wire count or solid interpolation does not match the physical mesh') # Do not let a caller rename a one-wire diagnostic as283wires.
    expected_ids=np.column_stack((np.repeat(native_wire_elements,8),np.tile(np.arange(1,9),len(native_wire_elements)))) # C3D8 and C3D20R both report eight native integration points per element.
    fields = {"stress": {}, "strain": {}} # Separate physical integration-point tensors.
    ids = None; current = None; time = None; rows = []; keys = [] # Streaming parser state.
    def flush() -> None: # Save only complete native tensor blocks.
        nonlocal ids, rows, keys # Maintain reference integration-point ordering.
        if current is not None and rows and time is not None and cycle_start - 1e-8 <= time <= cycle_end + 1e-8: # Limit to declared complete cycle.
            now = np.asarray(keys, dtype=int) # Native element/IP coordinates.
            if not np.array_equal(now,expected_ids): raise ValueError('Missing, duplicated, reordered or unexpected native wire integration points') # Require the complete physical mesh, not merely mutually consistent truncated frames.
            if ids is None: ids = now # Freeze full physical point identity.
            elif not np.array_equal(ids, now): raise ValueError("Native integration-point identity changed or output block truncated") # No silent missing-point zeros.
            fields[current][time] = np.asarray(rows, dtype=float)[:, [0, 1, 2, 3, 5, 4]] # Reorder nativeXXYYZZXYXZYZ to publicXXYYZZXYYZZX.
        rows, keys = [], [] # Reset after each block.
    with dat.open() as stream: # Avoid loading huge native DAT text in memory.
        for line in stream: # Native field records.
            match = re.match(r"\s*(stresses|strains) \(elem, integ.pnt.,.*for set WIRES and time\s+([0-9.E+-]+)", line) # Only actual wire IP blocks.
            if match: # Start next physical tensor block.
                flush(); current = "stress" if match[1] == "stresses" else "strain"; time = float(match[2]); continue # Preserve exact native time.
            if current is not None: # Parse data rows until the next header.
                tokens = line.split() # Split fixed-width scientific output safely.
                if len(tokens) == 8 and tokens[0].isdigit() and tokens[1].isdigit(): keys.append((int(tokens[0]), int(tokens[1]))); rows.append([float(v) for v in tokens[2:]]) # Complete six-component IP tensor.
                elif rows: flush(); current = None # Blank separator ends populated block.
    flush() # Preserve final block.
    times = sorted(fields["stress"]) # Actual converged sample times.
    if times != sorted(fields["strain"]) or len(times) < 3 or abs(times[0] - cycle_start) > 1e-7 or abs(times[-1] - cycle_end) > 1e-7: raise ValueError("Missing complete-cycle stress/strain endpoints") # Strict cycle coverage gate.
    stress, strain = np.stack([fields["stress"][t] for t in times]), np.stack([fields["strain"][t] for t in times]) # No basis reduction or point subsampling.
    if not np.isfinite(stress).all() or not np.isfinite(strain).all(): raise ValueError("Nonfinite native fields") # Reject corrupted history.
    output.parent.mkdir(parents=True, exist_ok=True) # Output location.
    np.savez_compressed(output, stress=stress, strain=strain, times=np.asarray(times), element_ip_ids=ids) # All complete physical tensors.
    meta = {"solver_status": "CONVERGED", "complete_cycle": True, "cycle_time_bounds": [cycle_start, cycle_end], "strain_shear_convention": "tensor", "tensor_component_order": ["XX", "YY", "ZZ", "XY", "YZ", "ZX"], "native_component_order": ["XX", "YY", "ZZ", "XY", "XZ", "YZ"], "source_input_sha256": identity, "source_result_sha256": hashlib.sha256(dat.read_bytes()).hexdigest(), "frame_count": len(times), "integration_point_count": int(stress.shape[1]), "wire_count": wire_count, "native_element_type": 'C3D20R' if mesh['connectivity'].shape[1]==20 else 'C3D8', "integration_point_order": 'CalculiX2.21gauss.f:gauss3d2:x-fast-then-y-then-z', "all_native_wire_integration_points_verified": True, "scope": "native complete-cycle elastic/contact research history; physical fidelity requires independent source/material/mesh validation", "contact_dissipation": "Not inferred from CDIS; requires irreversible slip and local contact-frame area quadrature"} # Explicit field contract.
    output.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n") # Save provenance.
    return meta # Report actual counts.

def main() -> None: # Native extraction CLI.
    p = argparse.ArgumentParser(description=__doc__) # Arguments.
    p.add_argument("folder", type=Path); p.add_argument("--job", default="saddle"); p.add_argument("--log", default="native.log"); p.add_argument("--start", type=float, required=True); p.add_argument("--end", type=float, required=True); p.add_argument("--wires", type=int, required=True) # Explicit native paths and complete-cycle scope.
    a = p.parse_args() # Parse command line.
    print(json.dumps(extract(a.folder / f"{a.job}.dat", a.folder / f"{a.job}.inp", a.folder / a.log, a.folder / "cycle_fields.npz", a.start, a.end, a.wires), indent=2)) # Preserve machine-readable result.

if __name__ == "__main__": main() # Execute only requested extraction.
