"""Physical conservation and finite-rotation tests for all-wire boundary transfer."""  # Describe independent mechanics checks.
import unittest  # Use the standard-library test runner.
import numpy as np  # Evaluate physical conservation independently from the implementation.
from coupling import conservative_cut_forces, rigid_cut_displacements, validate_boundary_constraints  # Import the public boundary interface.


class CouplingTests(unittest.TestCase):  # Group independent cut-boundary validation checks.
    def test_all_283_wires_force_and_moment(self):  # Exercise the complete provisional wire count, not a two-point surrogate.
        angle = np.linspace(0, 2 * np.pi, 283, endpoint=False)  # Construct a nondegenerate test cross-section, not bridge evidence.
        points = np.column_stack((np.zeros(283), 40 * np.cos(angle), 40 * np.sin(angle)))  # Supply distinct physical cut locations.
        areas = np.full(283, np.pi * 2.5 ** 2)  # Use equal5mm-wire areas only as a transfer unit test.
        force = np.array((700000.0, 1000.0, -2000.0))  # Specify an independently chosen three-axis force target.
        moment = np.array((8000.0, -20000.0, 30000.0))  # Specify independent torsion and bending targets.
        nodal = conservative_cut_forces(points, areas, np.zeros(3), force, moment)  # Apply the full-node transfer.
        np.testing.assert_allclose(nodal.sum(axis=0), force, rtol=1e-11, atol=1e-8)  # Check all force resultants directly.
        np.testing.assert_allclose(np.cross(points, nodal).sum(axis=0), moment, rtol=1e-10, atol=1e-7)  # Check moments using an independent cross product.
        self.assertEqual(nodal.shape, (283, 3))  # Verify no wire was dropped.

    def test_finite_rotation_preserves_distances(self):  # Ensure large rigid motion does not introduce artificial strain.
        points = np.array(((0, 0, 0), (0, 3, 0), (0, 0, 4)), dtype=float)  # Choose a known3-4-5triangle.
        rotation = np.array(((0, -1, 0), (1, 0, 0), (0, 0, 1)), dtype=float)  # Rotate90degrees about the third axis.
        motion = rigid_cut_displacements(points, np.zeros(3), np.array((7, 8, 9)), rotation)  # Transfer finite motion.
        final = points + motion  # Reconstruct the deformed cut coordinates.
        np.testing.assert_allclose(np.linalg.norm(final[:, None] - final[None, :], axis=-1), np.linalg.norm(points[:, None] - points[None, :], axis=-1))  # Verify all pairwise distances.

    def test_rejects_conflicting_boundary_targets(self):  # Check the physically invalid mixed prescription is blocked.
        with self.assertRaises(ValueError):  # Expect a diagnostic rather than a silent overwritten force.
            validate_boundary_constraints([(1, 1)], [(1, 1)])  # Attempt both axial force and axial displacement at one node.

    def test_rejects_nonrotation(self):  # Exclude a deformation gradient incorrectly labelled as rigid motion.
        with self.assertRaises(ValueError):  # Require an explicit invalid-matrix error.
            rigid_cut_displacements(np.zeros((3, 3)), np.zeros(3), np.zeros(3), 2 * np.eye(3))  # Try a uniformly scaled frame.

    def test_rejects_degenerate_cut(self):  # Reject a collapsed mesh that cannot transmit arbitrary moments.
        with self.assertRaises(ValueError):  # Require a rank-deficiency diagnosis.
            conservative_cut_forces(np.zeros((283, 3)), np.ones(283), np.zeros(3), np.ones(3), np.ones(3))  # Attempt six-resultant transfer at coincident points.


if __name__ == "__main__":  # Support a direct reproducible verification command.
    unittest.main()  # Run every declared physical-transfer test.
