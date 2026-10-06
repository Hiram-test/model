#!/usr/bin/env python3
"""Create an analytic slip-duct verification case using Gmsh/OpenFOAM only."""
from pathlib import Path
import json,subprocess
import gmsh
from prepare_case import create_case

import argparse
ap=argparse.ArgumentParser();ap.add_argument('--out',default='geometry/qa_porous_duct');args=ap.parse_args()
root=Path(__file__).resolve().parents[1];out=root/args.out
if (out/'constant').exists():raise RuntimeError('Refusing to overwrite a QA run; supply a new --out directory')
out.mkdir(parents=True,exist_ok=True)
gmsh.initialize();gmsh.option.setNumber('General.Terminal',0);gmsh.model.add('porous_duct_QA');o=gmsh.model.occ
r1=o.addRectangle(-1,0,0,1,1);r2=o.addRectangle(0,0,0,1,1)
areas,_=o.fragment([(2,r1)],[(2,r2)]);o.synchronize()
ex=o.extrude([x for x in areas if x[0]==2],0,0,.1,numElements=[1],recombine=True);o.synchronize()
vols=[t for d,t in ex if d==3];gmsh.model.addPhysicalGroup(3,vols,1);gmsh.model.setPhysicalName(3,1,'fluid')
surfs=gmsh.model.getBoundary([(3,t) for t in vols],combined=True,oriented=False)
patches={x:[] for x in ['inlet','outlet','body','frontAndBack']}
for d,t in surfs:
 b=gmsh.model.getBoundingBox(d,t)
 if abs(b[5]-b[2])<1e-6:n='frontAndBack'
 elif abs(b[0]+1)<1e-6 and abs(b[3]+1)<1e-6:n='inlet'
 elif abs(b[0]-1)<1e-6 and abs(b[3]-1)<1e-6:n='outlet'
 else:n='body'
 patches[n].append(t)
for i,(n,ts) in enumerate(patches.items(),2):gmsh.model.addPhysicalGroup(2,ts,i);gmsh.model.setPhysicalName(2,i,n)
gmsh.option.setNumber('Mesh.MeshSizeMin',.1);gmsh.option.setNumber('Mesh.MeshSizeMax',.1);gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
gmsh.model.mesh.generate(3);gmsh.write(str(out/'mesh.msh'));gmsh.finalize()
cfg=json.loads((root/'geometry/model.json').read_text());cfg.update(B_reference=1,H_reference=1,span_2d=.1,domain=[-1,1,0,1],moment_origin=[0,.7,0],mesh_factor=1,screens=[dict(name='screen',start=[0,0],end=[0,1],layers=[dict(open_area=.8,diameter=.005)])],selection_inside_box=[[-1.01,-.01,-1],[0,1.01,1]])
(out/'geometry.json').write_text(json.dumps(cfg,indent=2));create_case(out,out,0,13.8,1000)
subprocess.run(['bash',str(root/'scripts/convert_mesh.sh'),str(out)],check=True)
subprocess.run(['python3',str(root/'scripts/prepare_porous_mesh.py'),'--mesh',str(out)],check=True)
p=out/'0/U';p.write_text(p.read_text().replace('body { type noSlip; }','body { type slip; }'))
for fld in ['k','omega','nut']:
 p=out/'0'/fld;s=p.read_text()
 import re
 s=re.sub(r'body \{[^}]+\}', 'body { type zeroGradient; }',s);p.write_text(s)
with (out/'log.simpleFoam').open('w') as f:subprocess.run(['simpleFoam','-case',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
import numpy as np
c=json.loads((out/'case.json').read_text());scr=c['screens'][0]
expected=scr['I']+2*scr['D']*c['nu']/13.8
data=np.loadtxt(out/'postProcessing/coeffsH/0/coefficient.dat');measured=float(data[-1,1])
measured_CM=float(data[-1,5]); expected_CM=-.2*expected
check=dict(expected_CD=expected,native_forceCoeffs_CD=measured,relative_error=abs(measured-expected)/expected,expected_CM=expected_CM,native_forceCoeffs_CM=measured_CM,passed=abs(measured-expected)/expected<.005 and abs(measured_CM-expected_CM)<1e-6)
(out/'verification.json').write_text(json.dumps(check,indent=2));print(check)
if not check['passed']:raise SystemExit(1)
