"""Exact UCAB3 small-motion operators.

Matches the coupon-verified kernel in
catwalk-fem/c0-c5-reproduction/artifacts/ucab3_kernel/UCAB3_C3U_RECEIPT.md:

    Q = EA/L n n^T + N0/L (I - n n^T)
    K = [[Q, -Q], [-Q, Q]]
    M = mu L/6 [[2I, I], [I, 2I]]
    r0 = [-N0 n, +N0 n]
    r  = r0 + K d
    Sxx = N0 + EA/L * n · (uJ - uI)
    gravity consistent load = M @ [g, g]
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Ucab3Member:
    """One two-node translational cable."""

    point_i: tuple[float, float, float]
    point_j: tuple[float, float, float]
    ea_n: float
    n0_n: float
    mu_t_per_mm: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.ea_n) or self.ea_n <= 0.0:
            raise ValueError("EA_N must be finite and positive")
        if not math.isfinite(self.n0_n) or self.n0_n < 0.0:
            raise ValueError("N0_N must be finite and nonnegative")
        if not math.isfinite(self.mu_t_per_mm) or self.mu_t_per_mm < 0.0:
            raise ValueError("mu_t_per_mm must be finite and nonnegative")
        if self.length <= 1.0e-18:
            raise ValueError("member length must be positive")

    @property
    def chord(self) -> np.ndarray:
        return np.asarray(self.point_j, dtype=float) - np.asarray(self.point_i, dtype=float)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.chord))

    @property
    def direction(self) -> np.ndarray:
        return self.chord / self.length

    def q_matrix(self) -> np.ndarray:
        n = self.direction.reshape(3, 1)
        eye = np.eye(3)
        return (self.ea_n / self.length) * (n @ n.T) + (self.n0_n / self.length) * (eye - n @ n.T)

    def stiffness(self) -> np.ndarray:
        q = self.q_matrix()
        k = np.zeros((6, 6), dtype=float)
        k[0:3, 0:3] = q
        k[0:3, 3:6] = -q
        k[3:6, 0:3] = -q
        k[3:6, 3:6] = q
        return k

    def mass(self) -> np.ndarray:
        scale = self.mu_t_per_mm * self.length / 6.0
        m = np.zeros((6, 6), dtype=float)
        for i in range(3):
            m[i, i] = 2.0 * scale
            m[i, i + 3] = scale
            m[i + 3, i] = scale
            m[i + 3, i + 3] = 2.0 * scale
        return m

    def frozen_residual(self) -> np.ndarray:
        n = self.direction
        return np.concatenate((-self.n0_n * n, self.n0_n * n))

    def internal_force(self, disp: np.ndarray) -> np.ndarray:
        d = np.asarray(disp, dtype=float).reshape(6)
        return self.frozen_residual() + self.stiffness() @ d

    def axial_force(self, disp: np.ndarray) -> float:
        d = np.asarray(disp, dtype=float).reshape(6)
        rel = d[3:6] - d[0:3]
        return self.n0_n + self.ea_n / self.length * float(self.direction @ rel)

    def gravity_load(self, body_acc: tuple[float, float, float]) -> np.ndarray:
        g = np.asarray(body_acc, dtype=float).reshape(3)
        return self.mass() @ np.concatenate((g, g))
