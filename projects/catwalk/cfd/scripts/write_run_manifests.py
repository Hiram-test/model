#!/usr/bin/env python3
"""Add repository-standard identity/provenance files without renaming native cases."""
import argparse
import csv
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from assess_results import assess

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--cases',nargs='+',required=True)
args=ap.parse_args()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
rows=[]
for index,name in enumerate(args.cases,1):
    case=ROOT/'cases'/name
    cfg=json.loads((case/'case.json').read_text())
    execution=json.loads((case/'execution.json').read_text())
    r=assess(case)
    user_stop=json.loads((case/'user_stop.json').read_text()) if (case/'user_stop.json').exists() else None
    timestamp=datetime.datetime.fromisoformat(execution['started_utc']).strftime('%Y%m%dT%H%M%SZ')
    identity=f'CATWALK-OPENFOAM-EXP-P{index:02d}-{timestamp}'
    status='RUNNING' if not r['ended'] else 'PASSED_GATE' if r['solver_converged'] and r['coefficients_stable'] else 'FAILED_GATE'
    files={str(p.relative_to(case)):hashlib.sha256(p.read_bytes()).hexdigest()
           for d in ['0','constant','system'] for p in (case/d).rglob('*') if p.is_file()}
    (case/'INPUT_SHA256SUMS.txt').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(files.items())))
    (case/'STATUS.txt').write_text(status+'\n')
    model=cfg.get('model_id','zhangjinggao_16rope_drawing_prototype')
    lines=[f'# {identity}','',f'- Status: `{status}`. This is a validation-gate status, not the solver exit status.',
        f'- Native case path: `cases/{name}`. Existing paths retained for restarts and code compatibility.',
        f'- Model: `{model}`; angle: {cfg["alpha_deg"]:g} degrees; speed: {cfg["speed"]:g} m/s.',
        '- Solver: OpenFOAM 1912 (1912.200626), native pimpleFoam URANS kOmegaSST; mesher: Gmsh 4.8.4.',
        '- Units: m, s, kg, Pa; p field is kinematic pressure (m²/s²).',
        '- Coordinates: x transverse, y upward, z along bridge. Positive incidence has upward velocity; clockwise moment positive.',
        f'- Reference dimensions: B={cfg["B_reference"]:g} m, H={cfg["H_reference"]:g} m, L={cfg["span_2d"]:g} m.',
        f'- Moment origin (x,y): {cfg["moment_origin"][:2]}.',
        f'- Upstream fields: `{cfg["warm_start"]}`. Native solver command and original launch hashes: `execution.json`.',
        '- Current saved-input checksums: `INPUT_SHA256SUMS.txt`; original launch hashes remain in `execution.json`.',
        '- Parallel continuation, if present, is recorded in `parallel_resume*.json` with native decompose/reconstruct commands.',
        '- If present, `pilot_scope_update.json` records the declared pilot-duration change; it does not overwrite the original launch evidence.',
        f'- User-requested stop: {bool(user_stop)}; stopped before planned end: {r["stopped_early"]}. Details: `user_stop.json` when present. A graceful user stop is not a solver crash; validation gates remain separate.',
        '- Native outputs: `postProcessing/coeffsH` (CD), `postProcessing/coeffsB` (CL, clockwise CM), final numeric time directory.',
        f'- Source snapshot used to write this manifest: `{commit}`; publication branch: `exp/catwalk-openfoam-2d-pilot-20261006`.',
        '- Geometry/input evidence is in geometry JSON, per-model audit and the two modeling reports.',
        f'- Native run ended: {r["ended"]}; reached: {r["iteration"]:g} s; numerical check: {r["solver_converged"]}; statistical check: {r["coefficients_stable"]}.',
        '- Mesh and time-step independence: not demonstrated. Source/geometry uncertainties remain.',
        '- Permitted interpretation: reproducible 2-D engineering trial and sensitivity evidence.',
        '- Not permitted: validated wind-tunnel reproduction or design coefficients; no 3-D CFD result is claimed.','']
    (case/'RUN_MANIFEST.md').write_text('\n'.join(lines))
    rows.append(dict(run_id=identity,native_case_path='cases/'+name,model=model,alpha_deg=cfg['alpha_deg'],status=status,source_snapshot=commit))
out=ROOT/'report/catwalk_openfoam_run_register_20261006.csv'
with out.open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
print('Saved native manifests:',len(rows))
