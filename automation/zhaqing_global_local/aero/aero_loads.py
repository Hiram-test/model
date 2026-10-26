"""SI section aerodynamics; no bridge coefficients are embedded in this module."""  # Module scope.
from __future__ import annotations  # Permit modern return annotations.
import csv  # Read auditable coefficient tables.
import hashlib  # Bind provenance to exact table bytes.
import json  # Read explicit coefficient evidence.
from pathlib import Path  # Resolve portable file paths.
import numpy as np  # Calculate loads without plotting.


def _finite(value, name):  # Centralize input validation.
    array = np.asarray(value, dtype=float)  # Preserve station/time broadcasting.
    if not np.all(np.isfinite(array)):  # Reject invalid solver states.
        raise ValueError(f"{name} contains nonfinite values")  # Fail instead of hiding divergence.
    return array  # Return the validated numerical data.


class CoefficientTable:  # Keep coefficient values and evidence inseparable.
    def __init__(self, angle_deg, cd, cl, cm, width_m, evidence, allow_unverified=False):  # Explicitly expose any unverified use.
        self.angle = _finite(angle_deg, "angle_deg")  # Validate angular coordinates.
        self.values = np.column_stack([_finite(cd, "Cd"), _finite(cl, "Cl"), _finite(cm, "Cm")])  # Store three wind-axis coefficients.
        self.width_m = float(width_m)  # Use one consistent reference width.
        self.evidence = dict(evidence)  # Retain source identity for downstream records.
        if self.angle.ndim != 1 or len(self.angle) < 2 or self.values.shape != (len(self.angle), 3):  # Require a usable table.
            raise ValueError("coefficient arrays must share at least two angle samples")  # Reject malformed tables.
        if np.any(np.diff(self.angle) <= 0) or not np.isfinite(self.width_m) or self.width_m <= 0:  # Enforce strict interpolation coordinates and dimensions.
            raise ValueError("angles must increase strictly and width_m must be positive")  # Reject duplicates and invalid dimensions.
        if evidence.get("normalization") != "Cd=Fy/(q*B*L);Cl=Fz/(q*B*L);Cm=Mx/(q*B^2*L)":  # Avoid confusing frontal-area and deck-width drag coefficients.
            raise ValueError("normalization must use B for both force coefficients and B^2 for moment")  # Prevent silent reference-area errors.
        if evidence.get("axes") != "wind_drag,wind_lift,positive_bridge_x_pitch":  # Require explicit signs and frame.
            raise ValueError("coefficient axes/sign convention is missing or incompatible")  # Prevent lift or torsion sign reversal.
        if not allow_unverified:  # Production calculations require validated data.
            required = ("geometry_verified", "coefficient_validation_passed", "reynolds_applicability_verified")  # Separate geometry, numerics and applicability.
            if not all(evidence.get(key) is True for key in required):  # Check every production gate independently.
                raise ValueError("UNVERIFIED_COEFFICIENTS: geometry, coefficients and Reynolds applicability must pass")  # Do not fabricate physical credibility.
            if not evidence.get("source_artifact_sha256") or not evidence.get("validation_report_sha256"):  # Require immutable provenance identifiers.
                raise ValueError("verified coefficients require source and validation report hashes")  # Reject unsupported verification flags.

    @classmethod  # Provide the reproducible file interface.
    def from_files(cls, csv_path, evidence_path, allow_unverified=False):  # Load a table only with its evidence.
        csv_path = Path(csv_path)  # Normalize the coefficient path.
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))  # Load source and validation metadata.
        actual = hashlib.sha256(csv_path.read_bytes()).hexdigest()  # Compute the exact data fingerprint.
        if evidence.get("coefficient_csv_sha256") != actual:  # Detect stale or edited coefficient tables.
            raise ValueError("coefficient CSV hash does not match its provenance")  # Preserve auditability.
        with csv_path.open(newline="", encoding="utf-8") as stream:  # Use the documented CSV interchange format.
            rows = list(csv.DictReader(stream))  # Preserve the stored angle order.
        columns = [[float(row[key]) for row in rows] for key in ("angle_deg", "Cd", "Cl", "Cm")]  # Read explicitly named columns.
        return cls(*columns, evidence["reference_width_m"], evidence, allow_unverified)  # Apply numerical and evidence gates.

    def evaluate(self, angle_deg):  # Interpolate without inventing extrapolated aerodynamic behavior.
        angles = _finite(angle_deg, "effective_angle_deg")  # Validate coupled structural states.
        if np.any(angles < self.angle[0] - 1e-10) or np.any(angles > self.angle[-1] + 1e-10):  # Treat unsupported angles as missing data.
            raise ValueError("ANGLE_OUT_OF_TABLE: add verified CFD/wind-tunnel angle samples")  # Request an actual additional calculation.
        return np.stack([np.interp(angles, self.angle, self.values[:, index]) for index in range(3)], axis=-1)  # Use local shape-preserving linear interpolation.


def quasi_steady_loads(table, wind_yz_mps, velocity_yz_mps, theta_rad, omega_radps, rho_kgm3, aero_offset_yz_m=(0.0, 0.0)):  # Evaluate nonlinear loads at all physical stations.
    wind = _finite(wind_yz_mps, "wind_yz_mps")  # Use bridge transverse and vertical wind components.
    velocity = _finite(velocity_yz_mps, "velocity_yz_mps")  # Use the current structural velocity.
    theta = _finite(theta_rad, "theta_rad")  # Keep finite section rotation.
    omega = _finite(omega_radps, "omega_radps")  # Include aero-center rotational velocity.
    offset = _finite(aero_offset_yz_m, "aero_offset_yz_m")  # Offset is specified in the unrotated section frame.
    rho = float(rho_kgm3)  # Retain explicit air-density units.
    if wind.shape[-1:] != (2,) or velocity.shape[-1:] != (2,) or offset.shape[-1:] != (2,) or not np.isfinite(rho) or rho <= 0:  # Validate vectors and density.
        raise ValueError("wind, velocity and offset require two components; rho must be positive")  # Reject incompatible data.
    cosine, sine = np.cos(theta), np.sin(theta)  # Rotate the reference offset with the section.
    ry = cosine * offset[..., 0] - sine * offset[..., 1]  # Current transverse aero-center offset.
    rz = sine * offset[..., 0] + cosine * offset[..., 1]  # Current vertical aero-center offset.
    relative_y = wind[..., 0] - velocity[..., 0] + omega * rz  # Subtract translation and omega-cross-r transverse velocity.
    relative_z = wind[..., 1] - velocity[..., 1] - omega * ry  # Subtract translation and omega-cross-r vertical velocity.
    speed = np.hypot(relative_y, relative_z)  # Retain the nonlinear squared speed.
    beta = np.arctan2(relative_z, relative_y)  # Calculate actual wind direction in bridge coordinates.
    angle = np.rad2deg(np.arctan2(np.sin(beta - theta), np.cos(beta - theta)))  # Effective incidence is wind angle minus finite pitch.
    active = speed > 1e-12  # Avoid an arbitrary angle failure at zero relative flow.
    safe_angle = np.where(active, angle, table.angle[0])  # Use an in-range sample only when loads will be zero.
    coefficients = table.evaluate(safe_angle)  # Respect the measured/simulated angular support.
    q = 0.5 * rho * speed ** 2  # Dynamic pressure in pascals.
    drag = q * table.width_m * coefficients[..., 0]  # Wind-axis drag per unit bridge span in N/m.
    lift = q * table.width_m * coefficients[..., 1]  # Wind-axis lift per unit bridge span in N/m.
    fy = drag * np.cos(beta) - lift * np.sin(beta)  # Rotate wind-axis loads into bridge transverse force.
    fz = drag * np.sin(beta) + lift * np.cos(beta)  # Rotate wind-axis loads into bridge vertical force.
    moment = q * table.width_m ** 2 * coefficients[..., 2] + ry * fz - rz * fy  # Transfer aerodynamic moment to the structural reference axis.
    return {"force_y_Npm": fy, "force_z_Npm": fz, "moment_x_Nm_per_m": moment, "effective_angle_deg": angle, "relative_speed_mps": speed, "coefficient_evidence": table.evidence}  # Carry provenance into global calculations.


def consistent_nodal_loads(station_x_m, line_force_Npm, line_moment_Nm_per_m):  # Integrate linearly varying loads without dropping physical stations.
    x = _finite(station_x_m, "station_x_m")  # Use actual bridge span positions.
    force = _finite(line_force_Npm, "line_force_Npm")  # Shape is (..., station, 2).
    moment = _finite(line_moment_Nm_per_m, "line_moment_Nm_per_m")  # Shape is (..., station).
    if x.ndim != 1 or len(x) < 2 or np.any(np.diff(x) <= 0) or force.shape[-2:] != (len(x), 2) or moment.shape[-1:] != (len(x),):  # Check station ordering and dimensions.
        raise ValueError("span stations must increase and match force/moment station axes")  # Prevent load mapping to unrelated nodes.
    length = np.diff(x)  # Integrate each physical span segment separately.
    nodal_force = np.zeros_like(force)  # Store forces at every retained station.
    nodal_moment = np.zeros_like(moment)  # Store torsional moments at every retained station.
    nodal_force[..., :-1, :] += length[:, None] * (2 * force[..., :-1, :] + force[..., 1:, :]) / 6  # Exact left linear-shape-function integral.
    nodal_force[..., 1:, :] += length[:, None] * (force[..., :-1, :] + 2 * force[..., 1:, :]) / 6  # Exact right linear-shape-function integral.
    nodal_moment[..., :-1] += length * (2 * moment[..., :-1] + moment[..., 1:]) / 6  # Exact left torsional integral.
    nodal_moment[..., 1:] += length * (moment[..., :-1] + 2 * moment[..., 1:]) / 6  # Exact right torsional integral.
    return nodal_force, nodal_moment  # Preserve net force and first moment of the line load.


def interpolate_wind_history(times_s, station_x_m, wind_yz_mps, target_times_s, target_x_m):  # Transfer a recorded or independently specified wind field conservatively in time support.
    times = _finite(times_s, "times_s")  # Keep measured or generated time coordinates.
    stations = _finite(station_x_m, "station_x_m")  # Keep spatial sampling coordinates.
    wind = _finite(wind_yz_mps, "wind_yz_mps")  # Preserve both correlated wind components.
    target_times = _finite(target_times_s, "target_times_s")  # Accept adaptive structural integration times.
    target_x = _finite(target_x_m, "target_x_m")  # Interpolate onto all physical aerodynamic stations.
    if times.ndim != 1 or stations.ndim != 1 or len(times) < 2 or len(stations) < 2 or wind.shape != (len(times), len(stations), 2):  # Validate a complete field rather than a single uniform trace.
        raise ValueError("wind shape must be (time, station, 2) with at least two coordinates each")  # Reject ambiguous field shapes.
    if np.any(np.diff(times) <= 0) or np.any(np.diff(stations) <= 0):  # Ensure a unique interpolation grid.
        raise ValueError("wind times and stations must increase strictly")  # Reject repeated snapshots.
    if target_times.ndim != 1 or target_x.ndim != 1 or not len(target_times) or not len(target_x):  # Validate query arrays.
        raise ValueError("target times/stations must be nonempty one-dimensional arrays")  # Keep output axes explicit.
    if target_times.min() < times[0] or target_times.max() > times[-1] or target_x.min() < stations[0] or target_x.max() > stations[-1]:  # Never silently invent wind beyond recorded support.
        raise ValueError("WIND_OUT_OF_SUPPORT: no temporal or spatial extrapolation allowed")  # Require additional wind data.
    spatial = np.stack([[np.interp(target_x, stations, row[:, component]) for component in range(2)] for row in wind], axis=0).transpose(0, 2, 1)  # Piecewise linear spatial transfer.
    return np.stack([[np.interp(target_times, times, spatial[:, index, component]) for component in range(2)] for index in range(len(target_x))], axis=1).transpose(2, 1, 0)  # Return (target_time,target_station,2).
