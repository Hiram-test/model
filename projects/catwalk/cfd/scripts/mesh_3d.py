#!/usr/bin/env python3
"""Gmsh/OpenCASCADE 3-D resolved-wire representative segment (10 cm prototype)."""
import argparse,json
from pathlib import Path
import numpy as np
import gmsh

p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--factor',type=float,default=1);a=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'geometry/model.json').read_text())
if cfg.get('scale') != .1:
    raise RuntimeError('Legacy 1:10 wire-cell generator. Current task uses drawing-scale prototype; see build_prototype_stage.py. Do not mix the two coordinate systems.')
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
gmsh.initialize();gmsh.model.add('catwalk_resolved_wire_3d');occ=gmsh.model.occ
span=.005;shapes=[];members=[]
def rod(x,y,z,dx,dy,dz,d,group):
    shapes.append((3,occ.addCylinder(x,y,z,dx,dy,dz,d/2)))
    members.append(dict(x=x,y=y,z=z,dx=dx,dy=dy,dz=dz,diameter=d,group=group))
for v in [18780+260*i for i in range(8)]+[22300+260*i for i in range(8)]:
    rod((v-21450)*1e-4,0,0,0,0,span,.005,'carrier')
# 70 mm spacing across deck; 50 mm spacing along bridge (prototype).
for x in np.arange(-.2765,.28,.007):rod(float(x),.004,0,0,0,span,.0005,'coarse_longitudinal')
for z in [.0025]:rod(-.28,.004,z,.56,0,0,.0005,'coarse_transverse')
for side in [-1,1]:
    lo,hi=(.08,.28) if side==1 else (-.28,-.08)
    for x in np.arange(lo+.00125,hi,.0025):rod(float(x),cfg['floor_fine_y'],0,0,0,span,.0002,'fine_longitudinal')
    for z in [.00125,.00375]:rod(lo,cfg['floor_fine_y'],z,.2,0,0,.0002,'fine_transverse')
    for y in np.arange(.005,.096,.01):rod(side*.28,float(y),0,0,0,span,.0005,'side_longitudinal')
    for z in [.0025]:rod(side*.28,0,z,0,.096,0,.0005,'side_vertical')
    for y,d in cfg['handrails']:rod(side*.28,y,0,0,0,span,d,'handrail')
x0,x1,y0,y1=cfg['domain']
box=occ.addBox(x0,y0,0,x1-x0,y1-y0,span)
fluid,_=occ.cut([(3,box)],shapes)
occ.synchronize();assert len(fluid)==1
gmsh.model.addPhysicalGroup(3,[fluid[0][1]],1);gmsh.model.setPhysicalName(3,1,'fluid')
groups={'frontAndBack':[],'inlet':[],'outlet':[],'farfield':[],'body':[]}
for d,t in gmsh.model.getBoundary(fluid,oriented=False):
    b=gmsh.model.getBoundingBox(d,t)
    if abs(b[5]-b[2])<1e-6:name='frontAndBack'
    elif abs(b[0]-x0)<1e-6 and abs(b[3]-x0)<1e-6:name='inlet'
    elif abs(b[0]-x1)<1e-6 and abs(b[3]-x1)<1e-6:name='outlet'
    elif (abs(b[1]-y0)<1e-6 and abs(b[4]-y0)<1e-6) or (abs(b[1]-y1)<1e-6 and abs(b[4]-y1)<1e-6):name='farfield'
    else:name='body'
    groups[name].append(t)
for i,(name,tags) in enumerate(groups.items(),2):
    assert tags,name
    gmsh.model.addPhysicalGroup(2,tags,i);gmsh.model.setPhysicalName(2,i,name)
f=gmsh.model.mesh.field
f.add('Distance',1);f.setNumbers(1,'SurfacesList',groups['body']);f.setNumber(1,'NNodesByEdge',15)
f.add('MathEval',2);f.setString(2,'F',f'Min(0.16*{a.factor}, {a.factor}*(0.00010+0.28*F1))');f.setAsBackgroundMesh(2)
gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary',0)
gmsh.option.setNumber('Mesh.MeshSizeFromPoints',0)
gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',10/a.factor)
gmsh.option.setNumber('Mesh.Algorithm',6);gmsh.option.setNumber('Mesh.Algorithm3D',10)
gmsh.option.setNumber('Mesh.Optimize',1)
gmsh.option.setNumber('Mesh.MshFileVersion',2.2);gmsh.option.setNumber('General.NumThreads',3)
cfg.update(dimension=3,span_2d=span,mesh_factor=a.factor,members=members,description='Resolved-wire 3-D representative cell; symmetry ends; no discrete battens/posts/crossbeams',physical_surface_counts={k:len(v) for k,v in groups.items()})
(out/'geometry.json').write_text(json.dumps(cfg,indent=2))
gmsh.write(str(out/'geometry.brep'))
gmsh.model.mesh.generate(2);gmsh.write(str(out/'surface.msh'))
gmsh.model.mesh.generate(3)
gmsh.write(str(out/'mesh.msh'))
gmsh.finalize()
