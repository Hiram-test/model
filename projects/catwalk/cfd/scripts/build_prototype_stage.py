#!/usr/bin/env python3
"""Gmsh/OpenCASCADE gross 9 m prototype geometry for review, not a solved CFD case.

Screens are named zero-thickness porous surfaces. A 3-D solver must supply a
validated screen pressure-loss law before this geometry can be used for CFD.
"""
import json
from pathlib import Path
import gmsh

root = Path(__file__).resolve().parents[1]
out = root / 'geometry/prototype_9m'
out.mkdir(exist_ok=True)
cfg = json.loads((root / 'geometry/model.json').read_text())
gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('prototype_9m_gross_geometry')
occ = gmsh.model.occ
groups = {}
members = []


def add(group, tag, **data):
    groups.setdefault(group, []).append(tag)
    members.append(dict(group=group, tag=tag, **data))


def rod(x, y, diameter, group):
    tag = occ.addCylinder(x, y, 0, 0, 0, 9, diameter / 2)
    add(group, tag, type='cylinder', x=x, y=y, z=0, dz=9, diameter=diameter)


def rect(x, y, z, dx, dy, dz, group):
    tag = occ.addBox(x, y, z, dx, dy, dz)
    add(group, tag, type='box', x=x, y=y, z=z, dx=dx, dy=dy, dz=dz)


for x in sorted(s * (.85 + .26 * n) for s in [-1, 1] for n in range(8)):
    rod(x, 0, .05, 'carrier')
for side in [-1, 1]:
    for y, d in cfg['handrails']:
        rod(side * 2.8, y, d, 'handrail')

# End members are clipped to the 0..9m representative length: two halves = one.
# Small beams at 3m and 6m, not at the 0.5m timber spacing.
floor = .043
for z in [0, 9]:
    lo, hi = max(0, z - .05), min(9, z + .05)
    rect(-2.89, floor, lo, 5.78, .1, hi - lo, 'big_beam_envelope')
    for side in [-1, 1]:
        x = 2.8 if side == 1 else -2.875
        zlo, zhi = max(0, z - .0375), min(9, z + .0375)
        # Nominal angle silhouette; fasteners and lap details intentionally omitted.
        rect(x, .002, zlo, .075, 1.45, min(.006, zhi - zlo), 'post_angle_leg')
        rect(x if side == -1 else x + .069, .002, zlo, .006, 1.45, zhi - zlo, 'post_angle_leg')
for z in [3, 6]:
    rect(-2.762, floor, z - .025, 5.524, .05, .05, 'small_beam_envelope')
for n in range(18):
    z = .25 + .5 * n
    for xmin in [-2.76, .76]:
        rect(xmin, .05, z - .025, 2, .03, .05, 'timber')


def porous(name, corners, beta):
    pts = [occ.addPoint(*p) for p in corners]
    edges = [occ.addLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    surface = occ.addPlaneSurface([occ.addCurveLoop(edges)])
    members.append(dict(group=name, tag=surface, type='porous_surface', open_area=beta,
                        pressure_loss_law=None, corners=corners))
    return surface


surfaces = {}
beta = cfg['coarse_floor_open_area']
for name, lo, hi, porosity in [('floor_left', -2.8, -.8, beta * cfg['fine_floor_open_area']),
                              ('floor_centre', -.8, .8, beta),
                              ('floor_right', .8, 2.8, beta * cfg['fine_floor_open_area'])]:
    surfaces[name] = porous(name, [(lo, floor, 0), (hi, floor, 0), (hi, floor, 9), (lo, floor, 9)], porosity)
for side in [-1, 1]:
    name = 'side_left' if side == -1 else 'side_right'
    x = side * 2.8
    surfaces[name] = porous(name, [(x, floor, 0), (x, .96, 0), (x, .96, 9), (x, floor, 9)], cfg['side_open_area'])
occ.synchronize()
for name, tags in groups.items():
    g = gmsh.model.addPhysicalGroup(3, tags); gmsh.model.setPhysicalName(3, g, name)
for name, tag in surfaces.items():
    g = gmsh.model.addPhysicalGroup(2, [tag]); gmsh.model.setPhysicalName(2, g, name)
gmsh.write(str(out / 'prototype_9m.brep'))
top_entities = [(3, t) for ts in groups.values() for t in ts] + [(2, t) for t in surfaces.values()]
# STEP embeds millimetres; convert the metre-valued geometry before export.
occ.dilate(top_entities, 0, 0, 0, 1000, 1000, 1000)
occ.synchronize()
gmsh.write(str(out / 'prototype_9m.step'))
data = dict(status='GROSS_GEOMETRY_REVIEW_ONLY_3D_FLOW_NOT_RUN', units='m',
            step_native_unit='mm; exported coordinates multiplied by1000; a 9m span is 9000mm',
            scope='9m main-span reference: half big beams/posts at ends, small beams at3m/6m, timber pitch0.5m',
            simplifications='Smooth ropes, external beam envelopes, nominal angle posts; no fasteners/weave. Screen surfaces are not solid walls.',
            floor_level_assumed=floor, timber_phase_assumed=.25,
            members=members, counts={name: len(tags) for name, tags in groups.items()})
(out / 'geometry.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
gmsh.finalize()
print(json.dumps(data['counts']))
