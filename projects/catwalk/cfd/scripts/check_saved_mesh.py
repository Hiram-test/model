#!/usr/bin/env python3
"""Inspect the generated Gmsh mesh and native OpenFOAM check; generate no cells."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import gmsh
import numpy as np

ap=argparse.ArgumentParser()
ap.add_argument('--mesh',required=True)
a=ap.parse_args(); folder=Path(a.mesh)
cfg=json.loads((folder/'geometry.json').read_text())
native=(folder/'log.checkMesh').read_text()
gmsh.initialize();gmsh.option.setNumber('General.Terminal',0)
gmsh.open(str(folder/'mesh.msh'))
tags={gmsh.model.getPhysicalName(d,t):(d,t) for d,t in gmsh.model.getPhysicalGroups()}
_,bodytag=tags['body']
node_ids,node_xyz,_=gmsh.model.mesh.getNodes()
coordinates={int(n):xyz for n,xyz in zip(node_ids,np.asarray(node_xyz).reshape(-1,3))}
surface_nodes={}
for entity in gmsh.model.getEntitiesForPhysicalGroup(2,bodytag):
    # In imported MSH2, nodes shared with another entity may be classified there.
    # Read the actual surface element connectivity, not node classification alone.
    _,_,connectivity=gmsh.model.mesh.getElements(2,int(entity))
    ids=np.unique(np.concatenate(connectivity))
    surface_nodes[int(entity)]=set(map(int,ids))
parents={e:e for e in surface_nodes}
def root(e):
    while parents[e]!=e:
        parents[e]=parents[parents[e]]; e=parents[e]
    return e
owners={}
for e,nodes in surface_nodes.items():
    for n in nodes:
        if n in owners: parents[root(e)]=root(owners[n])
        else: owners[n]=e
groups={}
for e,nodes in surface_nodes.items():
    item=groups.setdefault(root(e),{'entities':[],'nodes':set()})
    item['entities'].append(e);item['nodes'].update(nodes)
components=[]
for group in groups.values():
    xyz=np.asarray([coordinates[n] for n in group['nodes']])
    if not len(xyz): raise RuntimeError('Empty body entity')
    lo,hi=xyz.min(axis=0),xyz.max(axis=0)
    components.append(dict(entities=group['entities'],minimum=lo.tolist(),maximum=hi.tolist(),centre=((lo+hi)/2).tolist(),z_levels=np.unique(np.round(xyz[:,2],8)).tolist()))
carrier=[]
for comp in components:
    # Only carrier cross sections extend below y=0 in these models.
    if comp['minimum'][1]<-.001: carrier.append(comp)
carrier.sort(key=lambda c:c['centre'][0])
tol=max(.002,.04*cfg['carrier_diameter'])
if 'carrier_x' in cfg:
    expected=sorted(cfg['carrier_x'])
else:
    verified=json.loads((Path(__file__).resolve().parents[1]/'geometry/verified_dimensions.json').read_text())
    expected=sorted(v*cfg['scale']/1000 for v in verified['carrier']['x'])
checks=dict(native_check_mesh_passed='Mesh OK.' in native,
            empty_front_back='empty' in (folder/'constant/polyMesh/boundary').read_text(),
            component_count_matches_model=len(components)==len(cfg['members']),
            actual_carrier_count=len(carrier)==len(expected),
            carrier_positions=len(carrier)==len(expected) and all(abs(c['centre'][0]-x)<tol and abs(c['centre'][1])<tol for c,x in zip(carrier,expected)),
            carrier_diameters=all(abs(c['maximum'][0]-c['minimum'][0]-cfg['carrier_diameter'])<2*tol for c in carrier),
            span_is_one_extruded_layer=all(len(c['z_levels'])==2 and abs(c['minimum'][2])<1e-8 and abs(c['maximum'][2]-cfg['span_2d'])<1e-8 for c in components))
match=re.search(r'Overall domain bounding box\s+\(([^)]+)\)\s+\(([^)]+)\)',native)
if match:
    lo=np.fromstring(match[1],sep=' ');hi=np.fromstring(match[2],sep=' ')
    x0,x1,y0,y1=[v*cfg.get('domain_factor',1) for v in cfg['domain']]
    checks['native_coordinates_in_metres']=bool(np.allclose(lo,[x0,y0,0]) and np.allclose(hi,[x1,y1,cfg['span_2d']]))
else: checks['native_coordinates_in_metres']=False
result=dict(passed=all(checks.values()),checks=checks,
            cells=int(re.search(r'^\s*cells:\s+(\d+)',native,re.M)[1]),
            actual_body_components=len(components),actual_carriers=carrier,
            msh_sha256=hashlib.sha256((folder/'mesh.msh').read_bytes()).hexdigest(),
            geometry_sha256=hashlib.sha256((folder/'geometry.json').read_bytes()).hexdigest(),
            check_scope='Generated mesh identity, scale and carrier layout only; no physical/mesh-independence validation')
(folder/'saved_mesh_audit.json').write_text(json.dumps(result,indent=2)+'\n')
gmsh.finalize(); print(json.dumps(result))
if not result['passed']: raise SystemExit(1)
