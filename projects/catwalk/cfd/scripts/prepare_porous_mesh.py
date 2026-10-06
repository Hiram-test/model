#!/usr/bin/env python3
"""Use native topoSet/createBaffles; never modify cell connectivity ourselves."""
import argparse,json,subprocess
from pathlib import Path
from prepare_case import header,create_case

ap=argparse.ArgumentParser();ap.add_argument('--mesh',required=True);a=ap.parse_args()
p=Path(a.mesh);cfg=json.loads((p/'geometry.json').read_text())
selection=cfg.get('selection_inside_box',[[-2.78,.043,-1],[2.78,.96,1]])
v0=' '.join(map(str,selection[0]));v1=' '.join(map(str,selection[1]))
actions=f'''{{ name interiorCells; type cellSet; action new; source boxToCell;
sourceInfo {{ box ({v0}) ({v1}); }} }}
'''
baffles=''
for scr in cfg['screens']:
    name=scr['name'];p0=scr['start'];p1=scr['end'];eps=1e-5
    lo=[min(p0[i],p1[i])-eps for i in [0,1]];hi=[max(p0[i],p1[i])+eps for i in [0,1]]
    actions+=f'''{{ name {name}Faces; type faceSet; action new; source boxToFace;
sourceInfo {{ box ({lo[0]} {lo[1]} 0.00001) ({hi[0]} {hi[1]} {cfg['span_2d']-.00001}); }} }}
{{ name {name}; type faceZoneSet; action new; source setsToFaceZone;
sourceInfo {{ faceSet {name}Faces; cellSet interiorCells; flip false; }} }}
'''
    baffles+=f'''{name} {{ type faceZone; zoneName {name};
patches {{ master {{ name {name}0; type cyclic; neighbourPatch {name}1; }}
slave {{ name {name}1; type cyclic; neighbourPatch {name}0; }} }} }}
'''
(p/'system/topoSetDict').write_text(header('topoSetDict')+'actions (\n'+actions+');\n')
(p/'system/createBafflesDict').write_text(header('createBafflesDict')+'internalFacesOnly true; noFields true;\nbaffles {\n'+baffles+'}\n')
for program in ['topoSet','createBaffles']:
    with (p/f'log.{program}').open('w') as log:
        subprocess.run([program,'-case',str(p),'-overwrite'] if program=='createBaffles' else [program,'-case',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True)
cfg['baffles_created']=True
(p/'geometry.json').write_text(json.dumps(cfg,indent=2))
create_case(p,p,0,13.8,2000)
with (p/'log.checkMesh').open('w') as log:subprocess.run(['checkMesh','-case',str(p),'-allTopology','-allGeometry'],stdout=log,stderr=subprocess.STDOUT,check=True)
if 'Mesh OK.' not in (p/'log.checkMesh').read_text():raise RuntimeError('checkMesh did not pass')
print('Baffles created and checked:',[s['name'] for s in cfg['screens']])
