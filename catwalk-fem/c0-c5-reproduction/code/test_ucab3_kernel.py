"""Receipt coupons that do not need the patched CCX binary."""
from __future__ import annotations
import math
import unittest
import numpy as np
from ucab3_kernel import Ucab3Member
G_MM_S2 = 9810.0
class Ucab3KernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.member = Ucab3Member((0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), 1.0e6, 1000.0, 1.0e-6)
    def test_frozen_residual_end_reactions(self) -> None:
        np.testing.assert_allclose(self.member.frozen_residual(), [-1000.0, 0.0, 0.0, 1000.0, 0.0, 0.0], atol=1e-12)
    def test_axial_stiffness_reaction(self) -> None:
        force = self.member.internal_force(np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0]))
        self.assertAlmostEqual(force[3], 1100.0, places=9)
    def test_geometric_stiffness_transverse_reaction(self) -> None:
        force = self.member.internal_force(np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
        self.assertAlmostEqual(force[4], 1.0, places=12)
    def test_zero_tension_transverse_null(self) -> None:
        slack = Ucab3Member(self.member.point_i, self.member.point_j, 1.0e6, 0.0, 1.0e-6)
        force = slack.internal_force(np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
        self.assertAlmostEqual(force[4], 0.0, places=12)
    def test_consistent_gravity_free_end(self) -> None:
        hanging = Ucab3Member((0.0, 0.0, 0.0), (0.0, -1000.0, 0.0), 1.0e6, 0.0, 1.0e-6)
        load = hanging.gravity_load((0.0, -G_MM_S2, 0.0))
        self.assertAlmostEqual(load[4] / hanging.stiffness()[4, 4], -0.004905, places=12)
    def test_stock_t3d2_delta_lambda(self) -> None:
        total_mass = self.member.mu_t_per_mm * self.member.length
        self.assertAlmostEqual(2.0 * self.member.n0_n / (self.member.length * total_mass), 2000.0, places=9)
if __name__ == "__main__":
    unittest.main()
