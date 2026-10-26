#!/usr/bin/env python3
"""Independent invariants for fatigue tensor algebra, energy integration and source-derived solid topology.""" # Test scope.
import importlib.util # Import local module without packaging.
import json # Test receipts.
from pathlib import Path # Repository paths.
import unittest # Deterministic numerical tests.
import numpy as np # Numeric checks only.
from fatigue_indicators import fatigue_indicators, friction_dissipation, swt_life # Physical postprocessors.
from corotate_native_history import corotate, six # Objective stress/strain conversion.

class FatigueTests(unittest.TestCase): # Independent closed-form physical checks.
    def test_rigid_rotation_objectivity(self): # Pure rotation produces zero strain and returns material stress orientation.
        angle = 0.7; r = np.array([[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]]) # Independent rigid rotation.
        reference = np.diag([100., 0., 0.]); spatial = r @ reference @ r.T # Cauchy tensor in rotated spatial axes.
        stress, strain = corotate(six(spatial)[None], r[None]) # Convert both fields back to material axes.
        np.testing.assert_allclose(stress[0], [100, 0, 0, 0, 0, 0], atol=1e-12) # No artificial stress-plane rotation.
        np.testing.assert_allclose(strain, 0., atol=1e-14) # No false strain under rigid motion.
    def test_finite_stretch(self): # Logarithmic strain must equal exact principal log stretch.
        f = np.diag([1.01, 1., 1.]); stress, strain = corotate(np.array([[100.,0.,0.,0.,0.,0.]]), f[None]) # Exact homogeneous extension.
        self.assertAlmostEqual(strain[0,0], np.log(1.01), places=13) # Hencky strain rather than Green-Lagrange mixing.
    def test_uniaxial_swt(self): # Known elastic cycle gives exact Cartesian-plane SWT.
        stress = np.zeros((3, 1, 6)); stress[:, 0, 0] = [-100.0, 100.0, -100.0] # Closed±100MPa cycle.
        strain = np.zeros_like(stress); strain[..., 0] = stress[..., 0] / 200000.0 # E200GPa axial strain.
        result = fatigue_indicators(stress, strain) # Evaluate full tensor projection.
        self.assertAlmostEqual(result["swt_mpa"][0], 0.05, places=12) # 100*(200/200000/2)=0.05MPa.
        np.testing.assert_array_equal(result["critical_normal"][0], [1, 0, 0]) # Governing normal is axial.
    def test_irreversible_contact_energy(self): # Exact Coulomb sliding path with known traction and area.
        traction = np.zeros((3, 2, 2)); traction[..., 0] = -20.0 # Opposing shear in MPa.
        slip = np.zeros_like(traction); slip[1, :, 0] = 0.1; slip[2, :, 0] = 0.2 # Irreversible monotonic slip inmm.
        result = friction_dissipation(traction, slip, np.array([2.0, 3.0]), True) # Integrate five squaremm contact area.
        np.testing.assert_allclose(result, [10.0, 20.0]) # Work=Nmm, equals20*.2*5.
    def test_energy_sign_mismatch_fails(self): # Wrong traction/slip sign must not be silently absolutized.
        with self.assertRaises(ValueError): friction_dissipation(np.ones((2, 1, 2)), np.array([[[0., 0.]], [[1., 1.]]]), np.ones(1), True) # Negative dissipation rejected.
    def test_no_uncalibrated_life(self): # Fatigue indicator cannot become invented life.
        with self.assertRaises(ValueError): swt_life(np.ones(1), None) # Requires traceable material tests.
    def test_nan_calibration_fails(self): # Numerical corruption cannot map to a finite life.
        with self.assertRaises(ValueError): swt_life(np.ones(1), dict(source="test", material_batch="test", sigma_f_mpa=float("nan"), epsilon_f=.1, b=-.1, c=-.5, young_mpa=2e5, validated_cycle_range=[1, 1e8])) # Validate finite scalars.
    def test_empty_planes_fail(self): # Empty critical-plane search is invalid.
        with self.assertRaises(ValueError): fatigue_indicators(np.zeros((3, 1, 6)), np.zeros((3, 1, 6)), np.empty((0, 3))) # No-inf output from absent search.

if __name__ == "__main__": unittest.main(verbosity=2) # Reproducible test entrypoint.
