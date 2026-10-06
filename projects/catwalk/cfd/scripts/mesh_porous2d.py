#!/usr/bin/env python3
"""Gmsh generates a 2-D prototype mesh with internal, conforming screen edges."""
import argparse
import json
from pathlib import Path
import gmsh

ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--factor',type=float,default=1);a=ap.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'geometry/model.json').read_text())
if a.factor <= 0:raise ValueError('Mesh factor must be positive')
if cfg['scale'] != 1:raise ValueError('This entry point uses drawing prototype metres, scale=1')
out=Path(a.out)
if (out/'mesh.msh').exists():raise RuntimeError('Refusing to overwrite a generated mesh; choose a new --out')
out.mkdir(parents=True,exist_ok=True)
gmsh.initialize();gmsh.model.add('prototype_porous_screen_section');occ=gmsh.model.occ
holes=[];members=[]
def disk(x,y,d,group):
    holes.append((2,occ.addDisk(x,y,0,d/2,d/2)))
    members.append(dict(x=x,y=y,diameter=d,group=group))
carrier_x=cfg.get('carrier_x',sorted(s*(.85+.26*n) for s in [-1,1] for n in range(8)))
for x in carrier_x:disk(x,0,cfg['carrier_diameter'],'carrier')
half_width=cfg['B_geometry']/2
for s in [-1,1]:
    for y,d in cfg['handrails']:disk(s*half_width,y,d,'handrail')
x0,x1,y0,y1=cfg['domain'];span=cfg['span_2d']
rectangle=occ.addRectangle(x0,y0,0,x1-x0,y1-y0)
fluid,_=occ.cut([(2,rectangle)],holes);base=fluid[0][1]
# Offset mesh from rope centres by 20mm, within the drawing attachment envelope.
inset=cfg.get('porous_side_inset',.02)
side_x=half_width-inset;inner_x=cfg['fine_strip_inner_x']+inset
floor_y=cfg['floor_combined_y'];side_top=cfg['screen_height']
points=[(-side_x,side_top),(-side_x,floor_y),(-inner_x,floor_y),(inner_x,floor_y),(side_x,floor_y),(side_x,side_top)]
cfg['selection_inside_box']=[[-side_x,floor_y,-1],[side_x,side_top,1]]
tags=[occ.addPoint(x,y,0) for x,y in points]
lines=[occ.addLine(tags[i],tags[i+1]) for i in range(5)]
names=['side_left','floor_left','floor_centre','floor_right','side_right']
screens=[]
for name,p0,p1 in zip(names,points,points[1:]):
    beta=cfg['side_open_area'] if 'side' in name else cfg['coarse_floor_open_area']
    layers=[dict(diameter=cfg.get('screen_wire_diameters',{}).get('coarse',.005),open_area=beta)]
    if name in ['floor_left','floor_right']:
        layers.append(dict(diameter=cfg.get('screen_wire_diameters',{}).get('fine',.002),open_area=cfg['fine_floor_open_area']))
    screens.append(dict(name=name,start=p0,end=p1,layers=layers))
occ.synchronize()
gmsh.model.mesh.embed(1,lines,2,base)
ext=occ.extrude(fluid,0,0,span,numElements=[1],recombine=True);occ.synchronize()
vols=[t for d,t in ext if d==3]
gmsh.model.addPhysicalGroup(3,vols,1);gmsh.model.setPhysicalName(3,1,'fluid')
groups={k:[] for k in ['frontAndBack','inlet','outlet','farfield','body']}
body_edges=[]
for d,t in gmsh.model.getBoundary(fluid,oriented=False):
    b=gmsh.model.getBoundingBox(d,t)
    if b[0]>x0+1e-5 and b[3]<x1-1e-5 and b[1]>y0+1e-5 and b[4]<y1-1e-5:body_edges.append(t)
for d,t in gmsh.model.getBoundary([(3,t) for t in vols],oriented=False):
    b=gmsh.model.getBoundingBox(d,t)
    if abs(b[5]-b[2])<1e-6:name='frontAndBack'
    elif abs(b[0]-x0)<1e-6 and abs(b[3]-x0)<1e-6:name='inlet'
    elif abs(b[0]-x1)<1e-6 and abs(b[3]-x1)<1e-6:name='outlet'
    elif (abs(b[1]-y0)<1e-6 and abs(b[4]-y0)<1e-6) or (abs(b[1]-y1)<1e-6 and abs(b[4]-y1)<1e-6):name='farfield'
    else:name='body'
    groups[name].append(t)
for i,(name,items) in enumerate(groups.items(),2):
    gmsh.model.addPhysicalGroup(2,items,i);gmsh.model.setPhysicalName(2,i,name)
f=gmsh.model.mesh.field
f.add('Distance',1);f.setNumbers(1,'CurvesList',body_edges);f.setNumber(1,'NNodesByEdge',40)
f.add('Distance',2);f.setNumbers(2,'CurvesList',lines);f.setNumber(2,'NNodesByEdge',100)
f.add('MathEval',3);f.setString(3,'F',f'Min(2.0*{a.factor},Min({a.factor}*(0.003+0.18*F1),{a.factor}*(0.035+0.2*F2)))');f.setAsBackgroundMesh(3)
gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary',0);gmsh.option.setNumber('Mesh.MeshSizeFromPoints',0)
gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',20/a.factor)
gmsh.option.setNumber('Mesh.Algorithm',6);gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
gmsh.model.mesh.generate(3);gmsh.write(str(out/'mesh.msh'));gmsh.write(str(out/'geometry.brep'))
cfg.update(screens=screens,members=members,mesh_factor=a.factor,span_2d=span,wall_treatment='Spalding',screen_model='native porousBafflePressure',description='Drawing-scale prototype: physical ropes and zero-thickness porous screens')
(out/'geometry.json').write_text(json.dumps(cfg,indent=2))
gmsh.finalize()
