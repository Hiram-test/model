"""Analytical checks of units, frame changes, integration and evidence gates."""  # Test purpose.
import hashlib  # Create evidence-bound temporary tables.
import json  # Write explicit test metadata.
from pathlib import Path  # Work with temporary files.
import tempfile  # Keep synthetic checks separate from production inputs.
import unittest  # Use the standard test runner.
import numpy as np  # Compare numerical values without plotting.
from aero_loads import CoefficientTable, quasi_steady_loads, consistent_nodal_loads, interpolate_wind_history  # Import the actual production functions.
from summarize_cfd import read_coefficients, time_average  # Test native coefficient sign and adaptive-time weighting.


def evidence():  # Mark all fixture coefficients as nonphysical test data.
    return {"status": "ANALYTIC_UNIT_TEST_ONLY", "geometry_verified": False, "coefficient_validation_passed": False, "reynolds_applicability_verified": False, "normalization": "Cd=Fy/(q*B*L);Cl=Fz/(q*B*L);Cm=Mx/(q*B^2*L)", "axes": "wind_drag,wind_lift,positive_bridge_x_pitch", "reference_width_m": 5.5}  # No fixture can pass the production gate.


def table(cd=1.0, cl=0.0, cm=0.0):  # Make a mathematically transparent fixture.
    return CoefficientTable([-180, 0, 180], [cd] * 3, [cl] * 3, [cm] * 3, 5.5, evidence(), allow_unverified=True)  # Explicitly allow unit-test-only coefficients.


class AeroTests(unittest.TestCase):  # Exercise physical identities rather than implementation details.
    def test_adaptive_time_average(self):  # Adaptive sampling must not bias an integral toward smaller timesteps.
        data = np.array([[0, 0], [0.01, 0.01], [0.1, 0.1], [1, 1]])  # Sample a linear trace unevenly in time.
        np.testing.assert_allclose(time_average(data, 0, 1), [0.5])  # Compare with its exact continuous-time mean.

    def test_native_pitch_axis_projection(self):  # OpenFOAM1912 derives a negativez pitch axis despite a legacydictionarykey.
        with tempfile.TemporaryDirectory() as directory:  # Keep nonphysical native-header fixtures out of production.
            path = Path(directory) / "coefficient.dat"  # Create a temporary native-format test file.
            path.write_text("# rollAxis : (1 0 0)\n# pitchAxis : (0 0 -1)\n# yawAxis : (0 1 0)\n# Time Cd Cl CmRoll CmPitch CmYaw\n0 1 0 4 2 3\n1 2 1 5 -3 6\n")  # Exercise the actualaxisconvention ratherthan assumingCmPitchsign.
            data, axes = read_coefficients(path)  # Run theproductionparser.
            np.testing.assert_allclose(data[:, 3], [-2, 3])  # RecoverpositiveCFDz=positivebridgeXmoment.

    def test_square_speed_scaling(self):  # Nonlinear pressure must scale with speed squared.
        first = quasi_steady_loads(table(), [10, 0], [0, 0], 0, 0, 1.2)  # Evaluate the lower wind speed.
        second = quasi_steady_loads(table(), [20, 0], [0, 0], 0, 0, 1.2)  # Evaluate double wind speed.
        self.assertAlmostEqual(float(first["force_y_Npm"]), 330.0)  # Verify SI force normalization.
        self.assertAlmostEqual(float(second["force_y_Npm"]), 4 * float(first["force_y_Npm"]))  # Verify nonlinear scaling.

    def test_relative_velocity(self):  # A moving structure changes the actual aerodynamic speed.
        result = quasi_steady_loads(table(), [10, 0], [3, 0], 0, 0, 1.2)  # Move with the wind.
        self.assertAlmostEqual(float(result["relative_speed_mps"]), 7.0)  # Confirm relative motion is retained.

    def test_lift_rotation(self):  # Lift must rotate with the incoming flow frame.
        result = quasi_steady_loads(table(cd=0, cl=1), [0, 10], [0, 0], 0, 0, 1.2)  # Turn the incident wind ninety degrees.
        self.assertAlmostEqual(float(result["force_y_Npm"]), -330.0)  # Check transverse lift sign.
        self.assertAlmostEqual(float(result["force_z_Npm"]), 0.0, places=10)  # Check vertical projection.

    def test_moment_transfer(self):  # Aerodynamic force offsets must contribute to structural torsion.
        result = quasi_steady_loads(table(cd=1, cl=2, cm=0.1), [10, 0], [0, 0], 0, 0, 1.2, [1, 2])  # Use a known eccentricity.
        self.assertAlmostEqual(float(result["moment_x_Nm_per_m"]), 60 * 5.5 ** 2 * 0.1 + 660 - 660)  # Check exact moment transfer.

    def test_rotational_velocity(self):  # Rotation induces velocity at an eccentric aero center.
        result = quasi_steady_loads(table(), [10, 0], [0, 0], 0, 2, 1.2, [0, 1])  # Aero center moves against the incoming wind.
        self.assertAlmostEqual(float(result["relative_speed_mps"]), 12)  # Check omega-cross-r sign.

    def test_section_pitch_incidence(self):  # Incidence must include finite deck pitch.
        result = quasi_steady_loads(table(), [10, 0], [0, 0], np.pi / 6, 0, 1.2)  # Pitch the deck upward.
        self.assertAlmostEqual(float(result["effective_angle_deg"]), -30)  # Verify declared convention.

    def test_zero_flow(self):  # Zero flow should not fail because of an arbitrary flow angle.
        limited = CoefficientTable([2, 4], [1, 1], [0, 0], [0, 0], 5.5, evidence(), True)  # Use a table excluding zero incidence.
        result = quasi_steady_loads(limited, [0, 0], [0, 0], 10, 0, 1.2)  # Evaluate still relative air.
        self.assertEqual(float(result["force_y_Npm"]), 0)  # There is no aerodynamic force.

    def test_angle_extrapolation_refused(self):  # Missing angular data must trigger extra CFD rather than clamping.
        limited = CoefficientTable([-5, 5], [1, 1], [0, 0], [0, 0], 5.5, evidence(), True)  # Limit support to tested angles.
        with self.assertRaisesRegex(ValueError, "ANGLE_OUT_OF_TABLE"):  # Verify a clear failure reason.
            limited.evaluate(6)  # Query beyond the actual data.

    def test_unverified_coefficients_refused(self):  # Synthetic or unvalidated coefficients must never silently enter production.
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_COEFFICIENTS"):  # Exercise the production default.
            CoefficientTable([-5, 5], [1, 1], [0, 0], [0, 0], 5.5, evidence())  # Omit the explicit test override.

    def test_reference_area_refused(self):  # Frontal-area drag cannot be treated as width-normalized drag.
        wrong = evidence()  # Copy the test evidence.
        wrong["normalization"] = "frontal_area"  # Introduce a plausible integration error.
        with self.assertRaisesRegex(ValueError, "normalization"):  # Require a deliberate conversion.
            CoefficientTable([-5, 5], [1, 1], [0, 0], [0, 0], 5.5, wrong, True)  # Reject incompatible definitions.

    def test_linear_load_force_and_moment_conservation(self):  # Exact weak-form mapping should preserve resultant and bending moment.
        x = np.array([0, 0.2, 0.9, 2.0])  # Use nonuniform physical station spacing.
        force = np.column_stack((3 + 2 * x, np.zeros_like(x)))  # Apply an analytically integrable varying force.
        result, moment = consistent_nodal_loads(x, force, 4 + x)  # Integrate force and torsion consistently.
        self.assertAlmostEqual(float(result[:, 0].sum()), 10)  # Integral of (3+2x) on[0,2].
        self.assertAlmostEqual(float(np.dot(x, result[:, 0])), 34 / 3)  # Integral of x(3+2x) on[0,2].
        self.assertAlmostEqual(float(moment.sum()), 10)  # Integral of (4+x) on[0,2].

    def test_temporal_spatial_interpolation(self):  # A bilinear wind field should transfer exactly.
        times, x = np.array([0, 2]), np.array([0, 5])  # Define sparse wind observations.
        wind = np.stack([np.column_stack((3 + time + 2 * x, 4 - time + x)) for time in times])  # Define a known bilinear field.
        result = interpolate_wind_history(times, x, wind, [0, 1, 2], [0, 1, 3, 5])  # Transfer onto the full target grid.
        self.assertEqual(result.shape, (3, 4, 2))  # Verify time,station,component order.
        np.testing.assert_allclose(result[1, :, 0], [4, 6, 10, 14])  # Verify transverse interpolation.
        np.testing.assert_allclose(result[1, :, 1], [3, 4, 6, 8])  # Verify vertical interpolation.

    def test_wind_extrapolation_refused(self):  # Do not fabricate wind outside available support.
        with self.assertRaisesRegex(ValueError, "WIND_OUT_OF_SUPPORT"):  # Check physical support gate.
            interpolate_wind_history([0, 1], [0, 2], np.zeros((2, 2, 2)), [2], [1])  # Request an unavailable future sample.

    def test_csv_hash_integrity(self):  # An edited coefficient file must invalidate its provenance.
        with tempfile.TemporaryDirectory() as temporary:  # Isolate the nonphysical table fixture.
            path = Path(temporary) / "coefficients.csv"  # Choose the temporary coefficient filename.
            path.write_text("angle_deg,Cd,Cl,Cm\n-5,1,0,0\n5,1,0,0\n", encoding="utf-8")  # Write fixture data.
            metadata = evidence()  # Mark fixture provenance as unverified.
            metadata["coefficient_csv_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()  # Bind the initial bytes.
            companion = path.with_suffix(".json")  # Store the metadata next to its CSV.
            companion.write_text(json.dumps(metadata), encoding="utf-8")  # Persist test metadata.
            CoefficientTable.from_files(path, companion, True)  # Verify correct hash passes in test mode.
            path.write_text(path.read_text() + "10,2,0,0\n", encoding="utf-8")  # Simulate unnoticed data changes.
            with self.assertRaisesRegex(ValueError, "hash"):  # Require an updated provenance record.
                CoefficientTable.from_files(path, companion, True)  # Detect the stale evidence.


if __name__ == "__main__":  # Support a standalone reproducible test invocation.
    unittest.main(verbosity=2)  # Print each analytical check and its status.
