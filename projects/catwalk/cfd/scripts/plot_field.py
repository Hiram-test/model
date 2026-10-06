#!/usr/bin/env python3
"""Display native Gmsh cells exported by foamToVTK; never generate a new mesh."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.python-deps'))
import meshio

ap = argparse.ArgumentParser()
ap.add_argument('vtu')
ap.add_argument('--case', help='Case directory; default inferred from VTK path')
ap.add_argument('--prefix', default='flow_snapshot')
ap.add_argument('--output',default='results')
a = ap.parse_args()
out=ROOT/a.output
out.mkdir(parents=True,exist_ok=True)
path = Path(a.vtu).resolve()
case = Path(a.case) if a.case else path.parents[2]
cfg = json.loads((case / 'case.json').read_text())
m = meshio.read(path)
xy, index = np.unique(m.points[:, :2], axis=0, return_inverse=True)
tris, speed, pressure = [], [], []
for i, block in enumerate(m.cells):
    if block.type != 'wedge':
        raise ValueError('This plot expects the original one-layer 2-D prism mesh')
    tris.extend(index[block.data[:, :3]])
    speed.extend(np.linalg.norm(m.cell_data['U'][i], axis=1))
    pressure.extend(m.cell_data['p'][i])
tri = mtri.Triangulation(xy[:, 0], xy[:, 1], np.asarray(tris))
speed = np.asarray(speed) / cfg['speed']
cp = 2 * np.asarray(pressure) / cfg['speed']**2
physical_time = float(m.field_data['TimeValue'][0])
fig, axs = plt.subplots(3, 1, figsize=(11, 8.8), height_ratios=[2, 2, 1])
for ax, value, cmap, label, vmin, vmax in [
        (axs[0], speed, 'turbo', 'Speed / inlet speed', 0, 1.5),
        (axs[1], cp, 'coolwarm', 'Pressure coefficient', -1, 1)]:
    pc = ax.tripcolor(tri, facecolors=value, cmap=cmap, vmin=vmin, vmax=vmax, rasterized=True)
    ax.set(xlim=(-3.5, 7), ylim=(-1.25, 2.4), aspect='equal', xlabel='Across catwalk x (m)', ylabel='Height y (m)')
    for screen in cfg.get('screens', []):
        seg = np.asarray([screen['start'], screen['end']])
        ax.plot(seg[:, 0], seg[:, 1], color='black', lw=.6)
    fig.colorbar(pc, ax=ax, label=label, shrink=.82, pad=.015)
axs[2].triplot(tri, color='#405463', lw=.35)
edge=-cfg['B_geometry']/2
axs[2].set(xlim=(edge-.04, edge+.5), ylim=(-.065, .14), aspect='equal', xlabel='Across catwalk x (m)', ylabel='Height y (m)')
axs[2].set_title('Original Gmsh mesh near side screen and carrier ropes', fontsize=10)
fig.suptitle(f"Native OpenFOAM instantaneous field: angle {cfg['alpha_deg']:+g} deg, t = {physical_time:.3f} s\nSnapshot only; not a time-averaged result", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, .95))
for suffix in ['png', 'pdf']:
    fig.savefig(out / (a.prefix + '.' + suffix), dpi=180)
plt.close(fig)
(out / (a.prefix + '.json')).write_text(json.dumps(dict(source=str(path.relative_to(ROOT)), physical_time_s=physical_time, case=case.name, field_type='instantaneous', mesh_cells=len(tris)), indent=2))
print('Rendered native cells:', len(tris), 'time:', physical_time)
