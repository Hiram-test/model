#!/usr/bin/env python3
"""Build the simplified TRUE-3D catwalk CalculiX deck from the parsed S10 model.

Simplification contract (recorded in manifest):
  R1  Per catwalk two walkway bands; each band's 8 bearing ropes merge into ONE
      equivalent line (A,T x8) at the band's mean Y; each band's 3 gantry ropes
      merge into ONE line (A,T x3) at their mean Y, keeping their real elevated
      profile (~+8.5 m).  8 rope lines total + 4 downpull links.
  R2  Longitudinal coarsening: keep every 4th bearing node (~7.9 m) plus forced
      stations (gates, passages, D-constraint x, CP rings, saddles, ends).
  R3  142 gate frames -> parametric portal per catwalk station: bottom H175 beam
      (innerB-outerB), 2 posts RHS160 (B->G), top RHS160 (innerG-outerG).
      Real CERIG UXYZ pin replaced by shared node (rope I is negligible).
  R4  Crossbeam ladder (1430 rows, alternating box100/box50 @2.95 m) -> one
      smeared beam innerB-outerB per kept station, section scaled by
      (tributary dx / 2.948 m); mass stays in MASS21 (density zero, as in S10).
  R5  21 passages -> one 2-chord-equivalent beam each across the full width,
      welded at the 4 bearing-line crossings (real: pin), chord-only Iz.
  R6  33,003 MASS21 folded into per-element densities (binned); the 23,028
      static F loads are dropped because sum(F)/g == sum(MASS21) (963.811 t).
  R7  ROTY stabilization file skipped (B31 expansion provides rotary DOFs).
Units N/mm/tonne/s.  X longitudinal, Y transverse, Z vertical.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ART = Path(__file__).resolve().parent.parent / "artifacts"
SOL = Path(__file__).resolve().parent.parent / "solver"
SOL.mkdir(parents=True, exist_ok=True)
UY_FRAC_MAX = 0.05          # hard lock: catwalk UY must NOT be all-mesh pinned
BUILDER_SCHEME_MIN = 100000  # nid = 100000*(g+1)+k ; S10 raw ids collide above this
IMPORT_SHIFT = 2_000_000
PASSAGE_CLUSTER_GAP_MM = 5000.0


def deck_id_from_s10(n: int) -> int:
    """Keep 100000*(g+1)+k reserved. S10 ids in that range are shifted."""
    n = int(n)
    if n < BUILDER_SCHEME_MIN:
        return n
    return IMPORT_SHIFT + n


def cluster_x_stations(xs, gap: float = PASSAGE_CLUSTER_GAP_MM) -> list[float]:
    """R5: one equivalent beam per passage, not one per sec-63 depth sample."""
    xs = sorted(float(x) for x in xs)
    if not xs:
        return []
    clusters = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] < gap:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [float(sum(c) / len(c)) for c in clusters]

BEARING_A = 1393.668228093791
GANTRY_A = 1400.496622996084
DOWNPULL_A = 22298.691649500659
RHO = {"bearing": 1.264848052212931e-08, "gantry": 8.598817050785234e-09,
       "downpull": 1.264848052212931e-08}
RHO_STEEL_NIL = 1.0e-17
E_ROPE, NU_ROPE = 120000.0, 0.3
E_STEEL, NU_STEEL = 206000.0, 0.31
G_MM = 9806.0
MODES = int(os.environ.get("MODES", "100"))
COARSEN = int(os.environ.get("COARSEN", "4"))          # keep every Nth bearing node (~7.9 m at 4)
CCX_JOB = os.environ.get("CCX_JOB", "true3d_ccx")
MANIFEST_NAME = os.environ.get("MANIFEST_NAME", "true3d_model_manifest.json")

# ASEC (A, I_vert, I_lat, J) from S10 include
SEC_H175 = (4997.5, 28164706.4583, 9830899.73958, 176798.958333)
SEC_RHS160 = (2496.0, 10130432.0, 10130432.0, 15185664.0)
CROSS_LARGE = (1536.0, 2363392.0, 2363392.0, 3538944.0)
CROSS_SMALL = (736.0, 261525.333333, 261525.333333, 389344.0)
CROSS_SPACING = 2948.0
PASS_CHORD_A = 2752.03516454
PASS_CHORD_I = 7345181.85417
