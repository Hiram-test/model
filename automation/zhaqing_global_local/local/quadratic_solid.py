#!/usr/bin/env python3
"""Twenty-node serendipity brick interpolation and exact natural derivatives.""" # Numerical interpolation only.
from __future__ import annotations # Stable annotations.
import numpy as np # Numerical arrays, without plotting.
SIGNS = np.asarray([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], dtype=float) # Native corner order.
EDGES = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)) # Native midside order.
NATURAL = np.vstack((SIGNS, np.asarray([(SIGNS[a] + SIGNS[b]) / 2 for a,b in EDGES]))) # Every nodal natural coordinate.
GAUSS = SIGNS[[0,1,3,2,4,5,7,6]] / np.sqrt(3.0) # CalculiX 2.21 gauss.f gauss3d2 order differs from corner-node order at points3/4and7/8.
def shape(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]: # Evaluate a single natural position.
    q = np.asarray(q, dtype=float) # Three natural coordinates.
    values = np.zeros(20); grad = np.zeros((20,3)) # Shape and derivative arrays.
    for i, s in enumerate(SIGNS): # Quadratic corner shape functions.
        factors = 1 + s * q; linear = np.dot(s,q) - 2 # Serendipity corner factors.
        values[i] = np.prod(factors) * linear / 8 # Corner interpolation value.
        for a in range(3): grad[i,a] = s[a] * np.prod(np.delete(factors,a)) * (linear + factors[a]) / 8 # Analytic natural derivative.
    for i, s in enumerate(NATURAL[8:],8): # Quadratic midside shape functions.
        a = int(np.flatnonzero(s == 0)[0]); others = [b for b in range(3) if b != a] # Edge direction and transverse directions.
        values[i] = (1-q[a]**2) * np.prod(1+s[others]*q[others]) / 4 # Midside interpolation value.
        grad[i,a] = -q[a] * np.prod(1+s[others]*q[others]) / 2 # Derivative along edge.
        for b in others: c = next(k for k in others if k != b); grad[i,b] = (1-q[a]**2)*s[b]*(1+s[c]*q[c])/4 # Derivatives transverse to edge.
    return values, grad # Exact twenty-node shape data.
def gauss_shape() -> tuple[np.ndarray,np.ndarray]: # Eight native integration-point interpolation arrays.
    values, gradients = zip(*(shape(q) for q in GAUSS)) # Preserve integration-point order.
    return np.asarray(values), np.asarray(gradients) # Arrays usable by stress and kinematic routines.
