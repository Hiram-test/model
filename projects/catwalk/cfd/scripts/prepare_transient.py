#!/usr/bin/env python3
"""Warm-start a native OpenFOAM pimpleFoam URANS pilot from a completed steady run."""
import argparse,json,re,shutil
from pathlib import Path
from prepare_case import header

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--end',type=float,default=.12);p.add_argument('--average-start',type=float,default=.06)
p.add_argument('--max-dt',type=float,default=.00002);p.add_argument('--max-co',type=float,default=2);p.add_argument('--outer',type=int,default=2)
p.add_argument('--cold-start',action='store_true')
a=p.parse_args()
src=Path(a.source);out=Path(a.out)
source_cfg=json.loads((src/'case.json').read_text())
audit=json.loads((Path(__file__).resolve().parents[1]/source_cfg.get('geometry_audit','geometry/audit_status.json')).read_text())
if not (audit.get('production_ready') or audit.get('engineering_runs_allowed')):
    raise RuntimeError('Geometry audit is open; no further CFD launch. See geometry/audit_register.csv.')
if out.exists():raise RuntimeError('Refusing to overwrite a transient run')
times=[]
for q in src.iterdir():
    if not q.is_dir():continue
    try:t=float(q.name)
    except ValueError:continue
    if t>0:times.append((t,q))
if not times and not a.cold_start:raise RuntimeError('No completed steady field output available')
latest=src/'0' if a.cold_start else max(times)[1]
out.mkdir(parents=True)
for name in ['constant','system']:shutil.copytree(src/name,out/name)
out.joinpath('0').mkdir()
for name in ['U','p','k','omega','nut']:
    data=(latest/name).read_bytes()
    # OpenFOAM reads by directory; location metadata is updated without changing binary field payload.
    data=re.sub(rb'location\s+"[^"]+";',b'location "0";',data,count=1)
    (out/'0'/name).write_bytes(data)
cfg=json.loads((src/'case.json').read_text());cfg.update(solver='OpenFOAM pimpleFoam URANS kOmegaSST',transient=True,physical_end_time=a.end,average_start=a.average_start,warm_start=str(latest),status='NUMERICAL_VALIDATION_PENDING',maxCo=a.max_co,maxDeltaT=a.max_dt,outer_correctors=a.outer)
(out/'case.json').write_text(json.dumps(cfg,indent=2))
control=(out/'system/controlDict').read_text()
control=control.replace('application simpleFoam','application pimpleFoam')
control=re.sub(r'endTime\s+[^;]+;',f'endTime {a.end};',control)
control=re.sub(r'deltaT\s+[^;]+;',f'deltaT {a.max_dt/10};',control)
control=control.replace('stopAt writeNow','stopAt endTime')
control=re.sub(r'writeControl\s+[^;]+;', 'writeControl adjustableRunTime;', control, count=1)
control=re.sub(r'writeInterval\s+[^;]+;', f'writeInterval {a.end/4};', control, count=1)
control+='\nadjustTimeStep yes; maxCo '+str(a.max_co)+'; maxDeltaT '+str(a.max_dt)+';\n'
(out/'system/controlDict').write_text(control)
schemes=(out/'system/fvSchemes').read_text().replace('default steadyState','default backward')
schemes=schemes.replace('bounded Gauss linearUpwind','Gauss linearUpwind').replace('bounded Gauss upwind','Gauss upwind')
(out/'system/fvSchemes').write_text(schemes)
(out/'system/fvSolution').write_text(header('fvSolution')+'''solvers {
p { solver GAMG; tolerance 1e-6; relTol 0.02; smoother GaussSeidel; }
pFinal { $p; relTol 0; }
"(U|k|omega).*" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0; }
}
PIMPLE { momentumPredictor yes; nOuterCorrectors OUTER_COUNT; nCorrectors 2; nNonOrthogonalCorrectors 0; }
relaxationFactors { equations { ".*" 1; } }
'''.replace('OUTER_COUNT',str(a.outer)))
print(out)
(out / (out.name + '.foam')).touch()
