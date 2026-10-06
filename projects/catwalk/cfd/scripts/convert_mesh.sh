#!/bin/bash
set -euo pipefail
mesh_dir="$1"
cd "$mesh_dir"
gmshToFoam mesh.msh > log.gmshToFoam 2>&1
# Patch metadata only; no points, faces, or cell connectivity are generated here.
python3 - <<'PY'
import re,json
from pathlib import Path
p=Path('constant/polyMesh/boundary');s=p.read_text()
cfg=json.loads(Path('geometry.json').read_text())
endtype='symmetry' if cfg.get('dimension',2)==3 else 'empty'
for name,typ in [('frontAndBack',endtype),('body','wall')]:
    s,n=re.subn(r'('+name+r'\s*\{\s*type\s+)\w+',r'\g<1>'+typ,s)
    if n!=1: raise ValueError((name,n))
p.write_text(s)
PY
checkMesh -allTopology -allGeometry > log.checkMesh 2>&1
python3 - <<'PY'
from pathlib import Path
if 'Mesh OK.' not in Path('log.checkMesh').read_text():
    raise SystemExit('Native checkMesh did not pass; see log.checkMesh. No CFD launch allowed.')
PY
