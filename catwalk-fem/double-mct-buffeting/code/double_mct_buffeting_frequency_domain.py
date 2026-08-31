from __future__ import annotations  # Enable modern type annotations.

import argparse  # Parse reproducible case controls.
import json  # Write a machine-readable audit.
import math  # Supply constants and spectral formulas.
import os  # Configure a writable plotting cache.
from pathlib import Path  # Handle input and output paths safely.

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-double-mct-buffeting")  # Avoid a read-only home cache.

import matplotlib  # Configure non-interactive plotting.

matplotlib.use("Agg")  # Render figures without a display.

import matplotlib.pyplot as plt  # Draw comparison and time-history figures.
from matplotlib import font_manager  # Register the bundled Chinese font.
import numpy as np  # Evaluate modal and stochastic response.
import pandas as pd  # Read aerodynamic coefficients and write result tables.
from scipy.interpolate import PchipInterpolator  # Interpolate the measured coefficient table.

import double_mct_equivalent_passage_model as structure  # Reuse the audited double-MCT assembler.

RHO_AIR_KG_M3 = 1.225  # Adopt an explicit density because Attachment 2-3 omits it.
SECTION_WIDTH_M = 5.4  # Use the wind-tunnel prototype lift and moment reference width.
SECTION_HEIGHT_M = 1.5  # Use the wind-tunnel prototype drag reference height.
REFERENCE_HEIGHT_M = 169.54  # Use the Attachment 2-3 mean catwalk elevation above terrain reference.
ROUGHNESS_LENGTH_M = 0.01  # Adopt an explicit open-water roughness assumption.
PEAK_FACTOR = 3.5  # Match Attachment 2-3.
BREAK_FORCE_PER_ROPE_KN = 2380.0  # Use the stated single-rope breaking force.
N_CARRYING_ROPES_PER_WIDTH = 16  # Preserve the physical bundle count represented by MCT section 1.
N_GANTRY_ROPES_PER_WIDTH = 6  # Preserve the reviewed six Phi54 gantry ropes represented by MCT section 2.
CHINESE_FONT_PATH = Path("tmp/pdfs/fonts/NotoSansCJKsc-Regular.otf")  # Reuse the verified report font.

if CHINESE_FONT_PATH.exists():  # Register Chinese glyphs when the bundled font is present.
    font_manager.fontManager.addfont(str(CHINESE_FONT_PATH))  # Add the font to the runtime registry.
    plt.rcParams["font.family"] = "Noto Sans CJK SC"  # Select the CJK family globally.
plt.rcParams["axes.unicode_minus"] = False  # Preserve readable minus signs.


def load_coefficients(path: Path) -> dict[str, object]:  # Read and interpolate measured three-force coefficients.
    table = pd.read_csv(path, encoding="utf-8-sig")  # Read the frozen coefficient table.
    alpha_rad = np.deg2rad(table["alpha_deg"].to_numpy(dtype=float))  # Convert attack angles to radians.
    bundle: dict[str, object] = {"table": table, "alpha_rad": alpha_rad}  # Start the coefficient bundle.
    for name in ("CD", "CL", "CM"):  # Build one shape-preserving interpolator per coefficient.
        bundle[name] = PchipInterpolator(alpha_rad, table[name].to_numpy(dtype=float), extrapolate=False)  # Avoid invented extrapolation.
    return bundle  # Return raw and interpolated data.


def coefficient_kernel(coefficients: dict[str, object], mean_speed_mps: float) -> dict[str, float]:  # Linearize exact quasi-steady loads at alpha=0.
    zero = 0.0  # Define the reference attack angle in radians.
    cd = float(coefficients["CD"](zero))  # Evaluate zero-degree drag.
    cl = float(coefficients["CL"](zero))  # Evaluate zero-degree lift.
    cm = float(coefficients["CM"](zero))  # Evaluate zero-degree pitching moment.
    cd_prime = float(coefficients["CD"].derivative()(zero))  # Differentiate drag per radian.
    cl_prime = float(coefficients["CL"].derivative()(zero))  # Differentiate lift per radian.
    cm_prime = float(coefficients["CM"].derivative()(zero))  # Differentiate moment per radian.
    dynamic_pressure = 0.5 * RHO_AIR_KG_M3 * mean_speed_mps**2  # Compute mean dynamic pressure.
    kernel = {  # Assemble mean and gust derivatives per width and per unit span.
        "CD": cd,  # Record zero-degree drag.
        "CL": cl,  # Record zero-degree lift.
        "CM": cm,  # Record zero-degree moment.
        "CD_prime_per_rad": cd_prime,  # Record drag slope.
        "CL_prime_per_rad": cl_prime,  # Record lift slope.
        "CM_prime_per_rad": cm_prime,  # Record moment slope.
        "mean_FH_N_per_m": dynamic_pressure * SECTION_HEIGHT_M * cd,  # Mean horizontal drag.
        "mean_FV_N_per_m": dynamic_pressure * SECTION_WIDTH_M * cl,  # Mean vertical lift.
        "mean_M_Nm_per_m": dynamic_pressure * SECTION_WIDTH_M**2 * cm,  # Mean pitching moment.
        "b_H_u_N_per_m_per_mps": dynamic_pressure * SECTION_HEIGHT_M * 2.0 * cd / mean_speed_mps,  # Horizontal response to u.
        "b_H_w_N_per_m_per_mps": dynamic_pressure * SECTION_HEIGHT_M * (cd_prime - SECTION_WIDTH_M / SECTION_HEIGHT_M * cl) / mean_speed_mps,  # Horizontal response to w.
        "b_V_u_N_per_m_per_mps": dynamic_pressure * SECTION_WIDTH_M * 2.0 * cl / mean_speed_mps,  # Vertical response to u.
        "b_V_w_N_per_m_per_mps": dynamic_pressure * SECTION_WIDTH_M * (cl_prime + SECTION_HEIGHT_M / SECTION_WIDTH_M * cd) / mean_speed_mps,  # Vertical response to w.
        "b_M_u_Nm_per_m_per_mps": dynamic_pressure * SECTION_WIDTH_M**2 * 2.0 * cm / mean_speed_mps,  # Moment response to u.
        "b_M_w_Nm_per_m_per_mps": dynamic_pressure * SECTION_WIDTH_M**2 * cm_prime / mean_speed_mps,  # Moment response to w.
    }  # Finish the aerodynamic kernel.
    return kernel  # Return the explicit linearization.


def trap_weights(x: np.ndarray) -> np.ndarray:  # Form nonuniform trapezoidal tributary lengths.
    weights = np.zeros_like(x, dtype=float)  # Allocate weights.
    weights[1:-1] = 0.5 * (x[2:] - x[:-2])  # Give interior points half adjacent intervals.
    weights[0] = 0.5 * (x[1] - x[0])  # Give the first endpoint half one interval.
    weights[-1] = 0.5 * (x[-1] - x[-2])  # Give the last endpoint half one interval.
    return weights  # Return weights whose sum is the sampled span length.


def modal_station_fields(parsed: dict[str, object], model: dict[str, object], modes: np.ndarray, station_count: int = 277) -> dict[str, np.ndarray]:  # Interpolate full FE modes to Attachment 2-3 wind stations.
    source_nodes = parsed["nodes"]  # Read source MCT coordinates.
    index = model["index"]  # Read width and source-node mapping.
    support_left = 157  # Use the reviewed north main-span sliding support.
    support_right = 447  # Use the reviewed south main-span sliding support.
    chain_ids = [node_id for node_id in sorted(source_nodes) if support_left <= node_id <= support_right]  # Retain the continuous carrying chain.
    chain_x = np.array([source_nodes[node_id][0] - structure.MCT_X_ORIGIN_M for node_id in chain_ids], dtype=float)  # Form shifted chain coordinates.
    station_x = np.linspace(chain_x[0], chain_x[-1], station_count)  # Match the report's 277 positions.
    gantry_ids = [node_id for node_id in sorted(source_nodes) if 1001 <= node_id <= 1395]  # Retain the complete explicit gantry-rope chain.
    gantry_x = np.array([source_nodes[node_id][0] - structure.MCT_X_ORIGIN_M for node_id in gantry_ids], dtype=float)  # Form shifted gantry-rope coordinates.
    bottom_z = np.interp(station_x, chain_x, np.array([source_nodes[node_id][2] for node_id in chain_ids], dtype=float))  # Interpolate carrying-rope elevation.
    gantry_z = np.interp(station_x, gantry_x, np.array([source_nodes[node_id][2] for node_id in gantry_ids], dtype=float))  # Interpolate gantry-rope elevation.
    gate_height = gantry_z - bottom_z  # Form the local carrying-to-gantry rope lever arm.
    if np.min(gate_height) <= 0.0:  # Reject a reversed or collapsed local portal before dividing by height.
        raise ValueError("The interpolated gantry-rope height must remain positive over the wind span.")  # Stop on an invalid rope pairing.
    vector = modes.reshape((-1, 3, modes.shape[1]))  # Reshape mode vectors by node and component.
    fields: dict[str, np.ndarray] = {"x_m": station_x, "weights_m": trap_weights(station_x), "gate_height_m": gate_height}  # Start the station bundle.
    for width, tag in ((0, "L"), (1, "R")):  # Interpolate each complete MCT plane separately.
        for component, axis in ((0, "x"), (1, "y"), (2, "z")):  # Interpolate all three translations.
            chain_values = np.vstack([vector[index[(width, node_id)], component, :] for node_id in chain_ids])  # Read node-by-mode values.
            interpolated = np.column_stack([np.interp(station_x, chain_x, chain_values[:, mode_index]) for mode_index in range(modes.shape[1])])  # Interpolate every mode.
            fields[f"phi_{axis}_{tag}"] = interpolated  # Store station-by-mode values.
        gantry_y_values = np.vstack([vector[index[(width, node_id)], 1, :] for node_id in gantry_ids])  # Read explicit gantry-rope lateral mode values.
        fields[f"phi_y_gantry_{tag}"] = np.column_stack([np.interp(station_x, gantry_x, gantry_y_values[:, mode_index]) for mode_index in range(modes.shape[1])])  # Interpolate every gantry-rope mode.
        fields[f"theta_local_{tag}"] = (fields[f"phi_y_{tag}"] - fields[f"phi_y_gantry_{tag}"]) / gate_height[:, None]  # Use positive rotation about +X: bottom minus upper lateral translation divided by positive height.
    fields["theta_system"] = (fields["phi_z_R"] - fields["phi_z_L"]) / (2.0 * structure.HALF_CATWALK_SPACING_M)  # Form the distinct cross-width system-roll observation shape.
    return fields  # Return all modal station fields.


def build_load_matrices(fields: dict[str, np.ndarray], kernel: dict[str, float]) -> dict[str, np.ndarray]:  # Map four gust fields to generalized force.
    weights = np.asarray(fields["weights_m"], dtype=float)  # Read station tributary lengths.
    phi_y_l = np.asarray(fields["phi_y_L"], dtype=float)  # Read left lateral modal fields.
    phi_y_r = np.asarray(fields["phi_y_R"], dtype=float)  # Read right lateral modal fields.
    phi_z_l = np.asarray(fields["phi_z_L"], dtype=float)  # Read left vertical modal fields.
    phi_z_r = np.asarray(fields["phi_z_R"], dtype=float)  # Read right vertical modal fields.
    theta_l = np.asarray(fields["theta_local_L"], dtype=float)  # Read left local gate/catwalk rotation fields.
    theta_r = np.asarray(fields["theta_local_R"], dtype=float)  # Read right local gate/catwalk rotation fields.
    weighted_y_l = phi_y_l.T * weights[None, :]  # Form left horizontal virtual-work weights.
    weighted_y_r = phi_y_r.T * weights[None, :]  # Form right horizontal virtual-work weights.
    weighted_z_l = phi_z_l.T * weights[None, :]  # Form left vertical virtual-work weights.
    weighted_z_r = phi_z_r.T * weights[None, :]  # Form right vertical virtual-work weights.
    weighted_theta_l = theta_l.T * weights[None, :]  # Form left local-moment virtual-work weights.
    weighted_theta_r = theta_r.T * weights[None, :]  # Form right local-moment virtual-work weights.
    matrices = {  # Assemble one modal-force matrix for each gust field.
        "u_L": weighted_y_l * kernel["b_H_u_N_per_m_per_mps"] + weighted_z_l * kernel["b_V_u_N_per_m_per_mps"] + weighted_theta_l * kernel["b_M_u_Nm_per_m_per_mps"],  # Map left horizontal gust and left local moment.
        "u_R": weighted_y_r * kernel["b_H_u_N_per_m_per_mps"] + weighted_z_r * kernel["b_V_u_N_per_m_per_mps"] + weighted_theta_r * kernel["b_M_u_Nm_per_m_per_mps"],  # Map right horizontal gust and right local moment.
        "w_L": weighted_y_l * kernel["b_H_w_N_per_m_per_mps"] + weighted_z_l * kernel["b_V_w_N_per_m_per_mps"] + weighted_theta_l * kernel["b_M_w_Nm_per_m_per_mps"],  # Map left vertical gust and left local moment.
        "w_R": weighted_y_r * kernel["b_H_w_N_per_m_per_mps"] + weighted_z_r * kernel["b_V_w_N_per_m_per_mps"] + weighted_theta_r * kernel["b_M_w_Nm_per_m_per_mps"],  # Map right vertical gust and right local moment.
    }  # Finish gust matrices.
    matrices["mean_Q"] = np.sum(weighted_y_l + weighted_y_r, axis=1) * kernel["mean_FH_N_per_m"] + np.sum(weighted_z_l + weighted_z_r, axis=1) * kernel["mean_FV_N_per_m"] + np.sum(weighted_theta_l + weighted_theta_r, axis=1) * kernel["mean_M_Nm_per_m"]  # Map mean loads and each width's local moment by virtual work.
    return matrices  # Return generalized load maps.


def wind_spectra(frequency_hz: np.ndarray, mean_speed_mps: float) -> tuple[np.ndarray, np.ndarray, float]:  # Evaluate Attachment 2-3 Simiu and Panofsky spectra.
    friction_velocity = 0.4 * mean_speed_mps / math.log(REFERENCE_HEIGHT_M / ROUGHNESS_LENGTH_M)  # Infer missing u-star by an explicit log law.
    reduced = frequency_hz * REFERENCE_HEIGHT_M / mean_speed_mps  # Use x=fz/U.
    su = 200.0 * friction_velocity**2 * REFERENCE_HEIGHT_M / mean_speed_mps / (1.0 + 50.0 * reduced) ** (5.0 / 3.0)  # Evaluate one-sided horizontal PSD.
    sw = 6.0 * friction_velocity**2 * REFERENCE_HEIGHT_M / mean_speed_mps / (1.0 + 4.0 * reduced) ** 2  # Evaluate one-sided vertical PSD.
    return su, sw, friction_velocity  # Return spectra and inferred u-star.


def generate_wind_component(station_x: np.ndarray, duration_s: float, dt_s: float, mean_speed_mps: float, minimum_frequency_hz: float, maximum_frequency_hz: float, coherence_decay: float, cross_width_mode: str, seed: int, component: str) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:  # Generate a two-width stationary periodic field.
    sample_count = int(round(duration_s / dt_s))  # Use an integer number of samples.
    frequency_hz = np.fft.rfftfreq(sample_count, dt_s)  # Build the exact FFT grid.
    df_hz = 1.0 / duration_s  # Record its spacing.
    active = np.flatnonzero((frequency_hz >= minimum_frequency_hz) & (frequency_hz <= maximum_frequency_hz) & (frequency_hz < frequency_hz[-1]))  # Select active non-Nyquist bins.
    su, sw, friction_velocity = wind_spectra(frequency_hz[active], mean_speed_mps)  # Evaluate target PSDs.
    target = su if component == "u" else sw  # Select the requested component.
    station_count = len(station_x)  # Count spanwise positions.
    random = np.random.default_rng(seed)  # Create a deterministic independent phase source.
    left_fft = np.zeros((station_count, len(frequency_hz)), dtype=np.complex128)  # Allocate left-width Fourier coefficients.
    right_fft = np.zeros_like(left_fft)  # Allocate right-width coefficients.
    spacing_m = float(np.mean(np.diff(station_x)))  # Use the uniform report station spacing.
    for local_index, frequency_index in enumerate(active):  # Generate each spectral line independently.
        frequency = float(frequency_hz[frequency_index])  # Read the active frequency.
        rho_x = math.exp(-coherence_decay * frequency * spacing_m / mean_speed_mps)  # Evaluate adjacent-station coherence.
        innovation = math.sqrt(max(0.0, 1.0 - rho_x**2))  # Form the AR(1) Cholesky factor.
        epsilon_left = (random.standard_normal(station_count) + 1j * random.standard_normal(station_count)) / math.sqrt(2.0)  # Draw left complex normals.
        epsilon_aux = (random.standard_normal(station_count) + 1j * random.standard_normal(station_count)) / math.sqrt(2.0)  # Draw an independent auxiliary field.
        field_left = np.empty(station_count, dtype=np.complex128)  # Allocate correlated left samples.
        field_aux = np.empty(station_count, dtype=np.complex128)  # Allocate correlated auxiliary samples.
        field_left[0] = epsilon_left[0]  # Seed the left recursion.
        field_aux[0] = epsilon_aux[0]  # Seed the auxiliary recursion.
        for station in range(1, station_count):  # March along the span.
            field_left[station] = rho_x * field_left[station - 1] + innovation * epsilon_left[station]  # Generate the left field.
            field_aux[station] = rho_x * field_aux[station - 1] + innovation * epsilon_aux[station]  # Generate the auxiliary field.
        if cross_width_mode == "coherent":  # Match the attachment's implicit single 277-point line.
            field_right = field_left.copy()  # Apply identical gusts to both widths.
        elif cross_width_mode == "independent":  # Provide a lower-coherence bound.
            field_right = field_aux  # Use independent width fields.
        else:  # Apply the same Davenport decay across 42.9 m.
            rho_y = math.exp(-coherence_decay * frequency * 2.0 * structure.HALF_CATWALK_SPACING_M / mean_speed_mps)  # Evaluate cross-width coherence.
            field_right = rho_y * field_left + math.sqrt(max(0.0, 1.0 - rho_y**2)) * field_aux  # Mix correlated and independent parts.
        amplitude = sample_count * math.sqrt(float(target[local_index]) * df_hz / 2.0)  # Normalize for numpy irfft and one-sided PSD.
        left_fft[:, frequency_index] = amplitude * field_left  # Store left coefficients.
        right_fft[:, frequency_index] = amplitude * field_right  # Store right coefficients.
    left = np.fft.irfft(left_fft, n=sample_count, axis=1)  # Transform the left field to time.
    right = np.fft.irfft(right_fft, n=sample_count, axis=1)  # Transform the right field to time.
    left -= np.mean(left, axis=1, keepdims=True)  # Remove finite-record means.
    right -= np.mean(right, axis=1, keepdims=True)  # Remove finite-record means.
    target_sigma = math.sqrt(float(np.sum(target) * df_hz))  # Integrate the discrete target PSD.
    pre_left = np.sqrt(np.mean(left**2, axis=1))  # Measure left station energies.
    pre_right = np.sqrt(np.mean(right**2, axis=1))  # Measure right station energies.
    left *= (target_sigma / np.maximum(pre_left, 1.0e-12))[:, None]  # Enforce the target marginal variance.
    right *= (target_sigma / np.maximum(pre_right, 1.0e-12))[:, None]  # Enforce the right marginal variance.
    metadata = {"target_sigma_mps": target_sigma, "friction_velocity_mps": friction_velocity, "df_hz": df_hz, "active_bins": float(len(active)), "pre_scale_midspan_sigma_mps": float(pre_left[station_count // 2])}  # Record generation checks.
    return left, right, metadata  # Return two width histories and checks.


def solve_periodic_response(generalized_force: np.ndarray, frequencies_hz: np.ndarray, damping_ratio: float, dt_s: float) -> np.ndarray:  # Apply modal transfer functions in the frequency domain.
    sample_count = generalized_force.shape[1]  # Read record length.
    force_fft = np.fft.rfft(generalized_force, axis=1)  # Transform modal forces.
    forcing_frequency = np.fft.rfftfreq(sample_count, dt_s)  # Build matching frequency bins.
    omega_n = 2.0 * math.pi * frequencies_hz[:, None]  # Form modal circular frequencies.
    omega = 2.0 * math.pi * forcing_frequency[None, :]  # Form forcing circular frequencies.
    denominator = omega_n**2 - omega**2 + 2.0j * damping_ratio * omega_n * omega  # Form unit-modal-mass dynamic stiffness.
    coordinate_fft = force_fft / denominator  # Solve each uncoupled mass-normalized modal equation.
    return np.fft.irfft(coordinate_fft, n=sample_count, axis=1)  # Return the exact periodic steady response.


def observation_shapes(fields: dict[str, np.ndarray], fractions: tuple[float, ...] = (0.25, 0.5, 0.75)) -> dict[str, np.ndarray]:  # Interpolate modal response shapes at report stations.
    x = np.asarray(fields["x_m"], dtype=float)  # Read wind-station coordinates.
    targets = x[0] + np.asarray(fractions) * (x[-1] - x[0])  # Form quarter-span targets.
    result: dict[str, np.ndarray] = {"x_m": targets}  # Start the observation bundle.
    for key in ("phi_y_L", "phi_y_R", "phi_z_L", "phi_z_R", "theta_local_L", "theta_local_R", "theta_system"):  # Interpolate each observable.
        values = np.asarray(fields[key], dtype=float)  # Read station-by-mode values.
        result[key] = np.column_stack([np.interp(targets, x, values[:, mode_index]) for mode_index in range(values.shape[1])])  # Interpolate every mode.
    return result  # Return target-by-mode observation matrices.


def statistics_rows(observations: dict[str, np.ndarray], q_static: np.ndarray, q_history: np.ndarray, seed: int) -> list[dict[str, object]]:  # Compute like-for-like response statistics.
    rows: list[dict[str, object]] = []  # Collect statistics.
    station_labels = ("L/4", "L/2", "3L/4")  # Match Attachment 2-3 locations.
    mappings = {  # Define common-section observables.
        "lateral_common_m": 0.5 * (observations["phi_y_L"] + observations["phi_y_R"]),  # Common lateral displacement.
        "vertical_common_m": 0.5 * (observations["phi_z_L"] + observations["phi_z_R"]),  # Common vertical displacement.
        "local_roll_L_deg": observations["theta_local_L"] * 180.0 / math.pi,  # Left local gate/catwalk rotation about +X.
        "local_roll_R_deg": observations["theta_local_R"] * 180.0 / math.pi,  # Right local gate/catwalk rotation about +X.
        "system_roll_deg": observations["theta_system"] * 180.0 / math.pi,  # Distinct cross-width system roll in degrees.
    }  # Finish observable mappings.
    for response_name, shape in mappings.items():  # Evaluate every response component.
        static = shape @ q_static  # Compute mean static response.
        dynamic = shape @ q_history  # Compute zero-mean periodic response.
        for station_index, station_label in enumerate(station_labels):  # Record all three stations.
            signal = dynamic[station_index]  # Read one stationary series.
            sigma = float(np.std(signal, ddof=1))  # Compute de-meaned buffeting standard deviation.
            mean = float(static[station_index])  # Read the static mean.
            rows.append({"seed": seed, "station": station_label, "response": response_name, "mean": mean, "sigma": sigma, "raw_rms": math.sqrt(mean**2 + sigma**2), "mean_plus_3p5sigma": mean + PEAK_FACTOR * sigma, "mean_minus_3p5sigma": mean - PEAK_FACTOR * sigma, "sample_max": mean + float(np.max(signal)), "sample_min": mean + float(np.min(signal))})  # Store complete statistics.
    return rows  # Return one seed's rows.


def axial_force_shapes(parsed: dict[str, object], model: dict[str, object], modes: np.ndarray, element_ids: list[int], divisor: int) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:  # Build linear axial-force recovery matrices.
    vector = modes.reshape((-1, 3, modes.shape[1]))  # Reshape modal translations.
    shapes: list[np.ndarray] = []  # Collect force per modal coordinate.
    initial_per_rope_kn: list[float] = []  # Collect initial force per physical rope.
    records: list[dict[str, object]] = []  # Preserve source identity.
    for width in (0, 1):  # Recover both MCT planes.
        for element_id in element_ids:  # Visit the requested source element family.
            element = parsed["elements"][element_id]  # Read connectivity.
            n1 = int(element["n1"])  # Read node one.
            n2 = int(element["n2"])  # Read node two.
            i = model["index"][(width, n1)]  # Resolve global node one.
            j = model["index"][(width, n2)]  # Resolve global node two.
            chord = np.asarray(model["xyz"])[j] - np.asarray(model["xyz"])[i]  # Form the SI chord.
            length = float(np.linalg.norm(chord))  # Compute length.
            direction = chord / length  # Form the unit vector.
            elastic_modulus, area, _ = structure.material_and_section(element)  # Read reviewed axial properties.
            force_shape = elastic_modulus * area / length * (direction @ (vector[j] - vector[i])) / float(divisor) / 1000.0  # Convert bundle N to physical-rope kN.
            shapes.append(force_shape)  # Append modal recovery coefficients.
            initial_per_rope_kn.append(float(parsed["initial_force_kn"].get(element_id, 0.0)) / float(divisor))  # Divide reviewed bundle tension.
            records.append({"width": "L" if width == 0 else "R", "element_id": element_id, "n1": n1, "n2": n2})  # Record identity.
    return np.vstack(shapes), np.asarray(initial_per_rope_kn), records  # Return recovery matrix, initial force, and identity.


def recover_force_summary(force_shape: np.ndarray, initial_kn: np.ndarray, records: list[dict[str, object]], q_static: np.ndarray, modal_covariance: np.ndarray, family: str, break_force_kn: float | None) -> pd.DataFrame:  # Recover mean and correlated RMS element forces.
    mean_kn = initial_kn + force_shape @ q_static  # Add static wind increments to reviewed initial tension.
    variance = np.einsum("im,mn,in->i", force_shape, modal_covariance, force_shape, optimize=True)  # Retain complete modal covariance.
    sigma_kn = np.sqrt(np.maximum(variance, 0.0))  # Convert variance to standard deviation.
    peak_kn = mean_kn + PEAK_FACTOR * sigma_kn  # Form the report-design peak.
    table = pd.DataFrame(records)  # Start with source identity.
    table["family"] = family  # Label the rope family.
    table["mean_tension_per_rope_kn"] = mean_kn  # Store mean force.
    table["sigma_per_rope_kn"] = sigma_kn  # Store buffeting RMS.
    table["peak_mean_plus_3p5sigma_kn"] = peak_kn  # Store peak force.
    table["capacity_ratio_to_break"] = float(break_force_kn) / peak_kn if break_force_kn is not None else np.nan  # Compare only when the physical rope-family breaking force is documented.
    return table  # Return every recovered element.


def recover_support_reactions(model: dict[str, object], modes: np.ndarray, q_static: np.ndarray, modal_covariance: np.ndarray) -> pd.DataFrame:  # Recover static-wind increments and elastic buffeting RMS at constrained DOFs.
    total_dofs = len(np.asarray(model["dof_mass_kg"]))  # Count all assembled translational DOFs.
    free_dofs = np.asarray(model["free_dofs"], dtype=int)  # Read the authoritative free set.
    constrained_mask = np.ones(total_dofs, dtype=bool)  # Start by marking every DOF constrained.
    constrained_mask[free_dofs] = False  # Remove all free coordinates.
    constrained_dofs = np.flatnonzero(constrained_mask)  # Form the fixed coordinate list.
    operator = np.asarray(model["stiffness"][constrained_dofs][:, free_dofs] @ modes[free_dofs, :], dtype=float)  # Form A=Kcf*Phi for support-on-structure force.
    static_increment_n = operator @ np.asarray(q_static, dtype=float)  # Recover the static-wind reaction increment with no direct support load.
    variance_n2 = np.einsum("im,mn,in->i", operator, modal_covariance, operator, optimize=True)  # Preserve all modal cross-covariances.
    sigma_n = np.sqrt(np.maximum(variance_n2, 0.0))  # Convert diagonal variance to buffeting RMS.
    node_lookup = {int(row["global_index"]): row for row in model["node_records"]}  # Index node provenance by compact global node.
    axis_names = ("X_longitudinal", "Y_transverse", "Z_vertical")  # Fix the global direction convention.
    rows: list[dict[str, object]] = []  # Collect one row per constrained direction.
    for dof, mean_n, rms_n in zip(constrained_dofs, static_increment_n, sigma_n):  # Map every support quantity to source identity.
        global_node = int(dof // 3)  # Recover the compact node index.
        component = int(dof % 3)  # Recover X, Y, or Z.
        source = node_lookup[global_node]  # Read width and MCT node.
        rows.append({"width": source["width"], "mct_node": int(source["mct_node"]), "global_node_index": global_node, "global_dof": int(dof), "global_axis": axis_names[component], "static_wind_reaction_increment_kN": float(mean_n) / 1000.0, "buffeting_reaction_sigma_kN": float(rms_n) / 1000.0, "reaction_sign": "support action on structure", "direct_support_wind_load": 0.0})  # Record the elastic-only reaction recovery.
    return pd.DataFrame(rows)  # Return all 108 constrained-DOF results.


def attachment_support_comparison(reactions: pd.DataFrame, mapping_path: Path, reference_path: Path) -> pd.DataFrame:  # Match recoverable support components to Attachment Tables 5-2 and 5-3.
    mapping = pd.read_csv(mapping_path, encoding="utf-8-sig")  # Read the reviewed eight-location node map.
    reference = pd.read_csv(reference_path, encoding="utf-8-sig")  # Read the transcribed and axis-reordered attachment table.
    rows: list[dict[str, object]] = []  # Collect one row per width, location, and recoverable axis.
    for station in mapping.itertuples(index=False):  # Traverse eight attachment locations.
        node_id = int(station.mct_node)  # Read the candidate MCT node.
        for width in ("L", "R"):  # Keep the attachment's single-width comparison separate.
            station_reactions = reactions[(reactions["width"] == width) & (reactions["mct_node"] == node_id)]  # Select its constrained axes.
            for reaction in station_reactions.itertuples(index=False):  # Traverse only physically constrained directions.
                matched = reference[(reference["attachment_row"] == station.attachment_row) & (reference["global_axis"] == reaction.global_axis)]  # Find the like-for-like attachment component.
                if len(matched) != 1:  # Skip blank or absent attachment values.
                    continue  # Preserve only one-to-one evidence.
                source = matched.iloc[0]  # Read the attachment row.
                attachment_sigma = pd.to_numeric(pd.Series([source["buffeting_RMS_kN"]]), errors="coerce").iloc[0]  # Normalize blank cells to NaN.
                attachment_increment = pd.to_numeric(pd.Series([source["static_wind_increment_kN"]]), errors="coerce").iloc[0]  # Normalize the static-wind increment.
                rows.append({"attachment_row": station.attachment_row, "width": width, "mct_node": node_id, "global_axis": reaction.global_axis, "model_static_wind_increment_kN": float(reaction.static_wind_reaction_increment_kN), "attachment_static_wind_increment_kN": float(attachment_increment) if pd.notna(attachment_increment) else np.nan, "model_buffeting_sigma_kN": float(reaction.buffeting_reaction_sigma_kN), "attachment_buffeting_RMS_kN": float(attachment_sigma) if pd.notna(attachment_sigma) else np.nan, "model_to_attachment_sigma_ratio": float(reaction.buffeting_reaction_sigma_kN) / float(attachment_sigma) if pd.notna(attachment_sigma) and float(attachment_sigma) != 0.0 else np.nan, "comparison_boundary": station.comparison_boundary, "sign_note": "model is support-on-structure; attachment sign convention requires confirmation; RMS has no sign"})  # Record transparent comparison limits.
    return pd.DataFrame(rows)  # Return the recoverable subset.


def aggregate_seed_statistics(rows: pd.DataFrame) -> pd.DataFrame:  # Combine independent seed variances without averaging standard deviations incorrectly.
    aggregated: list[dict[str, object]] = []  # Collect one row per station and response.
    for (station, response), group in rows.groupby(["station", "response"], sort=False):  # Group like observations.
        mean = float(group["mean"].iloc[0])  # Static mean is seed-independent.
        sigma = math.sqrt(float(np.mean(group["sigma"].to_numpy(dtype=float) ** 2)))  # Average variances across seeds.
        aggregated.append({"station": station, "response": response, "mean": mean, "sigma_multiseed": sigma, "raw_rms": math.sqrt(mean**2 + sigma**2), "mean_plus_3p5sigma": mean + PEAK_FACTOR * sigma, "mean_minus_3p5sigma": mean - PEAK_FACTOR * sigma, "seed_count": len(group), "sigma_seed_min": float(group["sigma"].min()), "sigma_seed_max": float(group["sigma"].max())})  # Record uncertainty range.
    return pd.DataFrame(aggregated)  # Return the combined table.


def attachment_comparison(aggregate: pd.DataFrame) -> pd.DataFrame:  # Compare audited Attachment 2-3 displacement statistics.
    attachment = {  # Store corrected row directions and de-meaned sigma values.
        ("L/4", "lateral_common_m"): (-55.41, 14.198),  # Corrected lateral quarter-span result.
        ("L/2", "lateral_common_m"): (-72.33, 19.452),  # Corrected lateral midspan result.
        ("3L/4", "lateral_common_m"): (-56.32, 14.433),  # Corrected lateral three-quarter result.
        ("L/4", "vertical_common_m"): (0.21, 2.280),  # Corrected vertical quarter-span result.
        ("L/2", "vertical_common_m"): (0.29, 1.216),  # Corrected vertical midspan result.
        ("3L/4", "vertical_common_m"): (-0.85, 2.330),  # Corrected vertical three-quarter result.
    }  # Finish attachment reference values.
    rows: list[dict[str, object]] = []  # Collect comparison rows.
    for (station, response), (attachment_mean, attachment_sigma) in attachment.items():  # Match each like-for-like channel.
        model_row = aggregate[(aggregate["station"] == station) & (aggregate["response"] == response)].iloc[0]  # Select model statistics.
        rows.append({"station": station, "response": response, "attachment_mean": attachment_mean, "model_mean": float(model_row["mean"]), "absolute_mean_ratio": abs(float(model_row["mean"])) / max(abs(attachment_mean), 1.0e-12), "attachment_sigma": attachment_sigma, "model_sigma": float(model_row["sigma_multiseed"]), "sigma_ratio": float(model_row["sigma_multiseed"]) / attachment_sigma, "comparison_note": "Attachment directions corrected from Figures 5-7 to 5-9; sigma inferred from sqrt(rawRMS^2-mean^2)."})  # Record transparent ratios.
    attachment_torsion = {"L/4": (2.24, 0.604), "L/2": (-0.08, 0.139), "3L/4": (2.72, 0.706)}  # Store the audited Attachment 2-3 local-torsion mean and sigma in degrees.
    for station, (attachment_mean, attachment_sigma) in attachment_torsion.items():  # Compare attachment torsion only with local width rotations.
        left = aggregate[(aggregate["station"] == station) & (aggregate["response"] == "local_roll_L_deg")].iloc[0]  # Select the left-width local rotation.
        right = aggregate[(aggregate["station"] == station) & (aggregate["response"] == "local_roll_R_deg")].iloc[0]  # Select the right-width local rotation.
        mean_left = float(left["mean"])  # Read the left static mean.
        mean_right = float(right["mean"])  # Read the right static mean.
        sigma_left = float(left["sigma_multiseed"])  # Read the left buffeting sigma.
        sigma_right = float(right["sigma_multiseed"])  # Read the right buffeting sigma.
        model_mean = 0.5 * (mean_left + mean_right)  # Average the two width means for one attachment comparison ordinate.
        model_sigma = math.sqrt(0.5 * (sigma_left**2 + sigma_right**2))  # Combine width variances by their root mean square.
        rows.append({"station": station, "response": "local_roll_width_combined_deg", "attachment_mean": attachment_mean, "model_mean": model_mean, "absolute_mean_ratio": abs(model_mean) / max(abs(attachment_mean), 1.0e-12), "attachment_sigma": attachment_sigma, "model_sigma": model_sigma, "sigma_ratio": model_sigma / attachment_sigma, "model_mean_L": mean_left, "model_mean_R": mean_right, "model_mean_L_minus_R": mean_left - mean_right, "model_mean_LR_absolute_difference": abs(mean_left - mean_right), "model_sigma_L": sigma_left, "model_sigma_R": sigma_right, "model_sigma_L_minus_R": sigma_left - sigma_right, "model_sigma_LR_absolute_difference": abs(sigma_left - sigma_right), "comparison_note": "Attachment local torsion is compared with the mean of left/right local-roll means and RMS of left/right local-roll sigmas; system_roll is excluded."})  # Record the combined comparison and explicit inter-width differences.
    return pd.DataFrame(rows)  # Return comparison table.


def plot_results(aggregate: pd.DataFrame, comparison: pd.DataFrame, first_seed_time: np.ndarray, first_seed_signals: dict[str, np.ndarray], output_dir: Path) -> None:  # Render concise result figures.
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)  # Create mean and sigma comparison panels.
    lateral = comparison[comparison["response"] == "lateral_common_m"]  # Select lateral rows.
    positions = np.arange(len(lateral))  # Create station positions.
    width = 0.36  # Set paired bar width.
    axes[0].bar(positions - width / 2.0, np.abs(lateral["attachment_mean"]), width, label="附件 |均值|")  # Plot attachment means.
    axes[0].bar(positions + width / 2.0, np.abs(lateral["model_mean"]), width, label="双MCT |均值|")  # Plot model means.
    axes[0].set_xticks(positions, lateral["station"])  # Label stations.
    axes[0].set_ylabel("横向位移均值绝对值 / m")  # Label mean response.
    axes[0].grid(axis="y", alpha=0.2)  # Add a light grid.
    axes[0].legend()  # Show data sources.
    axes[1].bar(positions - width / 2.0, lateral["attachment_sigma"], width, label="附件反推 σ")  # Plot attachment buffeting sigma.
    axes[1].bar(positions + width / 2.0, lateral["model_sigma"], width, label="双MCT 多种子 σ")  # Plot model sigma.
    axes[1].set_xticks(positions, lateral["station"])  # Label stations.
    axes[1].set_ylabel("横向抖振标准差 / m")  # Label sigma response.
    axes[1].grid(axis="y", alpha=0.2)  # Add a light grid.
    axes[1].legend()  # Show data sources.
    fig.savefig(output_dir / "attachment_lateral_comparison.png", dpi=180)  # Save comparison figure.
    plt.close(fig)  # Release memory.
    fig, axes = plt.subplots(5, 1, figsize=(13, 12), sharex=True, constrained_layout=True)  # Create first-seed displacement and rotation histories.
    for axis, key, ylabel in zip(axes, ("mid_lateral_m", "mid_vertical_m", "mid_local_roll_L_deg", "mid_local_roll_R_deg", "mid_system_roll_deg"), ("中跨横移 / m", "中跨竖移 / m", "左幅局部转角 / deg", "右幅局部转角 / deg", "跨幅系统滚转 / deg")):  # Plot five distinct observables.
        axis.plot(first_seed_time, first_seed_signals[key], linewidth=0.65)  # Draw the stationary periodic response.
        axis.set_ylabel(ylabel)  # Label the response.
        axis.grid(alpha=0.2)  # Add a light grid.
    axes[-1].set_xlabel("时间 / s")  # Label time.
    fig.savefig(output_dir / "nominal_first_seed_timeseries.png", dpi=180)  # Save the time-history figure.
    plt.close(fig)  # Release memory.


def run_case(args: argparse.Namespace) -> None:  # Assemble structure, generate wind, and solve steady periodic response.
    args.output.mkdir(parents=True, exist_ok=True)  # Create the dedicated result directory.
    parsed = structure.parse_mct(args.mct)  # Parse the reviewed MCT.
    station_map = pd.read_csv(args.stations, encoding="utf-8-sig")  # Read exact passage stations.
    model = structure.build_double_model(parsed, station_map, args.passage_matrix)  # Assemble two complete MCT planes with the reviewed four-port condensation.
    frequencies_hz, modes = structure.solve_modes(model, args.modes)  # Solve low displacement modes.
    modal_table = structure.classify_modes(parsed, model, frequencies_hz, modes)  # Classify families and edge modes.
    fields = modal_station_fields(parsed, model, modes, 277)  # Interpolate modes to wind stations.
    coefficients = load_coefficients(args.coefficients)  # Load measured aerodynamic data.
    kernel = coefficient_kernel(coefficients, args.mean_speed_mps)  # Build the linear quasi-steady kernel.
    load_matrices = build_load_matrices(fields, kernel)  # Build modal load maps.
    omega_squared = (2.0 * math.pi * frequencies_hz) ** 2  # Form unit-mass modal stiffness.
    q_static = np.asarray(load_matrices["mean_Q"], dtype=float) / omega_squared  # Solve the linear prestressed static response.
    observations = observation_shapes(fields)  # Build report-station response maps.
    all_stat_rows: list[dict[str, object]] = []  # Collect independent-seed statistics.
    modal_covariance = np.zeros((args.modes, args.modes), dtype=float)  # Accumulate complete modal covariance.
    first_seed_time = np.array([], dtype=float)  # Reserve the first-seed time axis.
    first_seed_signals: dict[str, np.ndarray] = {}  # Reserve first-seed response signals.
    wind_checks: list[dict[str, object]] = []  # Collect wind metadata.
    for realization in range(args.seed_count):  # Run independent random-phase realizations.
        seed = args.seed_base + 100 * realization  # Separate realization seeds deterministically.
        u_l, u_r, u_meta = generate_wind_component(fields["x_m"], args.duration_s, args.dt_s, args.mean_speed_mps, args.minimum_frequency_hz, args.maximum_frequency_hz, args.coherence_decay, args.cross_width_mode, seed + 11, "u")  # Generate horizontal gusts.
        w_l, w_r, w_meta = generate_wind_component(fields["x_m"], args.duration_s, args.dt_s, args.mean_speed_mps, args.minimum_frequency_hz, args.maximum_frequency_hz, args.coherence_decay, args.cross_width_mode, seed + 29, "w")  # Generate independent vertical gusts.
        generalized_force = load_matrices["u_L"] @ u_l + load_matrices["u_R"] @ u_r + load_matrices["w_L"] @ w_l + load_matrices["w_R"] @ w_r  # Project all gust fields.
        q_history = solve_periodic_response(generalized_force, frequencies_hz, args.damping_ratio, args.dt_s)  # Solve stationary modal response.
        q_history -= np.mean(q_history, axis=1, keepdims=True)  # Remove residual FFT roundoff means.
        modal_covariance += q_history @ q_history.T / float(q_history.shape[1] - 1) / float(args.seed_count)  # Average full covariance across seeds.
        all_stat_rows.extend(statistics_rows(observations, q_static, q_history, seed))  # Record response statistics.
        wind_checks.append({"seed": seed, "u_target_sigma_mps": u_meta["target_sigma_mps"], "u_pre_scale_midspan_sigma_mps": u_meta["pre_scale_midspan_sigma_mps"], "w_target_sigma_mps": w_meta["target_sigma_mps"], "w_pre_scale_midspan_sigma_mps": w_meta["pre_scale_midspan_sigma_mps"], "friction_velocity_mps": u_meta["friction_velocity_mps"], "df_hz": u_meta["df_hz"], "active_bins": u_meta["active_bins"]})  # Record wind checks.
        if realization == 0:  # Save one trace for visual inspection only.
            first_seed_time = np.arange(q_history.shape[1], dtype=float) * args.dt_s  # Build its time axis.
            lateral_shape = 0.5 * (observations["phi_y_L"][1] + observations["phi_y_R"][1])  # Read midspan common lateral shape.
            vertical_shape = 0.5 * (observations["phi_z_L"][1] + observations["phi_z_R"][1])  # Read midspan common vertical shape.
            local_roll_l_shape_deg = observations["theta_local_L"][1] * 180.0 / math.pi  # Read left midspan local-roll shape.
            local_roll_r_shape_deg = observations["theta_local_R"][1] * 180.0 / math.pi  # Read right midspan local-roll shape.
            system_roll_shape_deg = observations["theta_system"][1] * 180.0 / math.pi  # Read the distinct cross-width system-roll shape.
            first_seed_signals = {"mid_lateral_m": float(lateral_shape @ q_static) + lateral_shape @ q_history, "mid_vertical_m": float(vertical_shape @ q_static) + vertical_shape @ q_history, "mid_local_roll_L_deg": float(local_roll_l_shape_deg @ q_static) + local_roll_l_shape_deg @ q_history, "mid_local_roll_R_deg": float(local_roll_r_shape_deg @ q_static) + local_roll_r_shape_deg @ q_history, "mid_system_roll_deg": float(system_roll_shape_deg @ q_static) + system_roll_shape_deg @ q_history}  # Reconstruct total signals without conflating local and system rotations.
    seed_table = pd.DataFrame(all_stat_rows)  # Form all realization statistics.
    aggregate = aggregate_seed_statistics(seed_table)  # Combine variances across seeds.
    comparison = attachment_comparison(aggregate)  # Compare corrected attachment displacements.
    carrying_shape, carrying_initial, carrying_records = axial_force_shapes(parsed, model, modes, list(range(1, 730)), N_CARRYING_ROPES_PER_WIDTH)  # Build carrying-rope recovery.
    gantry_shape, gantry_initial, gantry_records = axial_force_shapes(parsed, model, modes, list(range(1001, 1395)), N_GANTRY_ROPES_PER_WIDTH)  # Build gantry-rope recovery.
    carrying_forces = recover_force_summary(carrying_shape, carrying_initial, carrying_records, q_static, modal_covariance, "carrying_rope", BREAK_FORCE_PER_ROPE_KN)  # Recover physical carrying-rope force and its documented capacity ratio.
    gantry_forces = recover_force_summary(gantry_shape, gantry_initial, gantry_records, q_static, modal_covariance, "gantry_rope", None)  # Recover gantry-rope force without inventing a breaking strength.
    support_reactions = recover_support_reactions(model, modes, q_static, modal_covariance)  # Recover all constrained-DOF static-wind increments and buffeting RMS.
    support_comparison = attachment_support_comparison(support_reactions, args.support_mapping, args.support_reference)  # Compare only axes that exist in both models.
    modal_table.to_csv(args.output / "modal_properties.csv", index=False)  # Write retained mode data.
    seed_table.to_csv(args.output / "station_statistics_by_seed.csv", index=False)  # Write realization statistics.
    aggregate.to_csv(args.output / "station_statistics_multiseed.csv", index=False)  # Write aggregate statistics.
    comparison.to_csv(args.output / "attachment_table5_1_comparison.csv", index=False)  # Write attachment comparison.
    carrying_forces.to_csv(args.output / "carrying_rope_force_recovery.csv", index=False)  # Write every carrying element force.
    gantry_forces.to_csv(args.output / "gantry_rope_force_recovery.csv", index=False)  # Write every gantry element force.
    support_reactions.to_csv(args.output / "support_reaction_recovery.csv", index=False)  # Write every constrained support direction.
    support_comparison.to_csv(args.output / "attachment_support_reaction_comparison.csv", index=False)  # Write the recoverable Attachment 2-3 subset.
    pd.DataFrame(wind_checks).to_csv(args.output / "wind_generation_checks.csv", index=False)  # Write wind controls.
    first_seed_frame = pd.DataFrame({"time_s": first_seed_time, **first_seed_signals})  # Build first-seed trace table.
    first_seed_frame.to_csv(args.output / "nominal_first_seed_timeseries.csv", index=False)  # Write the visual trace.
    np.savez_compressed(args.output / "reduced_response_state.npz", frequencies_hz=frequencies_hz, modes=modes, q_static=q_static, modal_covariance=modal_covariance, free_dofs=model["free_dofs"])  # Preserve the exact reduced state needed for independent force and reaction recovery.
    plot_results(aggregate, comparison, first_seed_time, first_seed_signals, args.output)  # Render result figures.
    carrying_critical = carrying_forces.loc[carrying_forces["peak_mean_plus_3p5sigma_kn"].idxmax()].to_dict()  # Select the critical carrying-rope element.
    carrying_main = carrying_forces[carrying_forces["element_id"].between(155, 447)]  # Isolate the wind-loaded main-span carrying chain.
    carrying_main_critical = carrying_main.loc[carrying_main["peak_mean_plus_3p5sigma_kn"].idxmax()].to_dict()  # Select its controlling mean-plus-3.5-sigma element.
    carrying_dynamic = carrying_forces[carrying_forces["sigma_per_rope_kn"] > 1.0e-6]  # Exclude fixed short segments with zero modal force variation.
    carrying_dynamic_critical = carrying_dynamic.loc[carrying_dynamic["peak_mean_plus_3p5sigma_kn"].idxmax()].to_dict()  # Select the controlling wind-responsive element.
    gantry_critical = gantry_forces.loc[gantry_forces["peak_mean_plus_3p5sigma_kn"].idxmax()].to_dict()  # Select the critical gantry-rope element.
    audit = {  # Build the calculation audit.
        "status": "SIMPLIFIED_LINEAR_BUFFETING_WITH_EXPLICIT_ASSUMPTIONS",  # Prevent a strict-reproduction claim.
        "structural_model": "two complete MCT planes with explicit carrying and gantry ropes, 50 audited rank-one finite-gate replacements per width, and 21 four-port condensed gate-and-passage assemblies",  # State corrected topology.
        "mct_sha256": structure.sha256_file(args.mct),  # Bind the reviewed MCT.
        "station_map_sha256": structure.sha256_file(args.stations),  # Bind exact station mapping.
        "passage_matrix_path": str(args.passage_matrix),  # Record the labelled twelve-DOF four-port matrix source.
        "passage_matrix_sha256": str(model["passage_matrix_sha256"]),  # Bind the complete non-diagonal condensed matrix.
        "mass_tonne": float(np.sum(model["nodal_mass_kg"])) / 1000.0,  # Record full model mass.
        "passage_assembly": {"count": len(model["passage_records"]), "ports_per_station": ["bottom_left", "gantry_left", "bottom_right", "gantry_right"], "replaced_planar_truss_count": len(model["replaced_gate_elements"]), "replaced_planar_truss_elements": [int(value) for value in model["replaced_gate_elements"]], "replacement_rule": "At each of the 21 authoritative stations, remove the duplicated source property-3 gate TRUSS and assemble one transformed 12x12 four-port condensed gate-plus-passage matrix."},  # Audit the 21 station-specific TRUSS replacements.
        "ordinary_gate_assembly": {"count_per_width": len(model["ordinary_gate_elements"]), "count_double_model": 2 * len(model["ordinary_gate_elements"]), "source_audit_path": str(model["gate_only_audit_path"]), "source_audit_sha256": str(model["gate_only_audit_sha256"]), "equivalent_ea_n": float(model["gate_only_equivalent_ea_n"]), "translation_port_rank": 1, "replacement_rule": "Delete each remaining source property-3 TRUSS and assemble (EAeq/L) nn^T along its actual bottom-to-gantry chord; add no portal shear or mass."},  # Audit the 50-per-width ordinary finite-gate replacements.
        "aerodynamics": {"coefficient_file": str(args.coefficients), "air_density_kg_m3": RHO_AIR_KG_M3, "B_m": SECTION_WIDTH_M, "H_m": SECTION_HEIGHT_M, "kernel": kernel, "method": "linear quasi-steady, no aerodynamic damping/admittance; each width's local moment is mapped by virtual work to its own carrying-rope/gantry-rope relative lateral rotation"},  # Record force convention.
        "rotation_convention": {"local_roll_L_rad": "(u_y,bottom,L - u_y,gantry,L) / (z_gantry - z_bottom)", "local_roll_R_rad": "(u_y,bottom,R - u_y,gantry,R) / (z_gantry - z_bottom)", "sign": "positive rotation about global +X by the right-hand rule", "bottom_interpolation_nodes": "carrying-rope MCT nodes 157-447", "gantry_interpolation_nodes": "gantry-rope MCT nodes 1001-1395", "gate_height_min_m": float(np.min(fields["gate_height_m"])), "gate_height_max_m": float(np.max(fields["gate_height_m"])), "system_roll_rad": "(u_z,R - u_z,L) / 42.9", "interpretation": "local_roll_L/R are the moment-conjugate gate/catwalk section rotations; system_roll is a separate cross-width observation and is not Attachment 2-3 local torsion"},  # Audit rotation definitions and prevent torsion conflation.
        "wind": {"mean_speed_mps": args.mean_speed_mps, "minimum_frequency_hz": args.minimum_frequency_hz, "maximum_frequency_hz": args.maximum_frequency_hz, "duration_s": args.duration_s, "dt_s": args.dt_s, "coherence_decay": args.coherence_decay, "cross_width_mode": args.cross_width_mode, "seed_count": args.seed_count, "roughness_length_m": ROUGHNESS_LENGTH_M},  # Record stochastic assumptions.
        "structure_dynamics": {"mode_count": args.modes, "highest_retained_frequency_hz": float(frequencies_hz[-1]), "modal_damping_ratio": args.damping_ratio, "response_solution": "FFT periodic steady state; no startup transient", "static_solution": "linear about MCT prestressed equilibrium"},  # Record dynamic solution.
        "critical_carrying_rope": carrying_critical,  # Record critical carrying force.
        "critical_main_span_carrying_rope": carrying_main_critical,  # Record the like-for-like wind-loaded main-span result.
        "critical_wind_responsive_carrying_rope": carrying_dynamic_critical,  # Distinguish dynamic control from fixed initial-force control.
        "critical_gantry_rope": gantry_critical,  # Record critical gantry force.
        "support_reaction_recovery": {"formula": "R_c=K_cf*Phi*q-f_c; f_c=0 for this main-span wind application", "lumped_mass_cross_block": "M_cf=0", "physical_damping_cross_block": "not defined; no C_cf term invented", "static_result_scope": "static-wind increment only, excluding dead-load baseline", "buffeting_covariance": "A*Sigma_q*A^T with full modal cross-covariance", "attachment_mapping_path": str(args.support_mapping), "attachment_reference_path": str(args.support_reference), "constrained_dof_count": len(support_reactions), "recoverable_attachment_rows": len(support_comparison)},  # Record the partitioned-equilibrium convention.
        "limitations": [  # State boundaries that control interpretation.
            "The four-port stiffness is a static condensation of the finite gate-plus-passage model; local internal passage stresses require recovery from that detailed model and are not available from the twelve interface translations alone.",  # State condensation recovery boundary.
            "The ordinary-gate translation-only condensation retains one objective axial mode and five free-port mechanisms; finite portal shear requires retained rotational interfaces, so local-roll response is reported with a modal-convergence warning rather than hidden artificial shear.",  # State the gate-reduction boundary.
            "The reported local_roll_L/R are carrying-rope versus gantry-rope portal rotations, while system_roll is the differential vertical movement of the two MCT planes; neither is silently equated with Attachment 2-3 local deck torsion.",  # State the distinct rotation meanings.
            "Only displacement and low-frequency rope-force response are reported; retained modes do not support acceleration, comfort, fatigue, or local passage stress acceptance.",  # State modal truncation boundary.
            "The stated 2380 kN breaking force is applied only to each physical carrying rope; no gantry-rope capacity ratio is reported because its breaking force is absent from Attachment 2-3.",  # Prevent a cross-family capacity error.
            "Attachment omits structural damping, u-star, coherence constants, air density, random phases, and several force-mapping details; this is a stated-assumption recalculation, not an exact reproduction.",  # State missing source inputs.
            "At six mapped sliding saddle nodes UX is free, so Attachment horizontal-X values cannot be represented as nodal support reactions; adjacent cable cut forces would be a different quantity.",  # State the table 5-2/5-3 mapping boundary.
        ],  # Finish limitations.
    }  # Finish the audit object.
    (args.output / "calculation_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")  # Write machine-readable audit.
    print(aggregate.to_string(index=False))  # Show response statistics in the run log.
    print("\nCritical carrying rope:")  # Label the critical-force output.
    print(pd.Series(carrying_critical).to_string())  # Show the critical carrying result.
    print("\nCritical wind-loaded main-span carrying rope:")  # Label the like-for-like main-span output.
    print(pd.Series(carrying_main_critical).to_string())  # Show the main-span result.


def parse_args() -> argparse.Namespace:  # Define the reproducible command-line interface.
    parser = argparse.ArgumentParser(description="Linear steady-periodic buffeting response of the corrected double-MCT catwalk ROM.")  # Create the parser.
    parser.add_argument("--mct", type=Path, default=Path("tmp/mct_pair_sources/catwalk_gantry_rope_combined_2.mct"))  # Accept the reviewed MCT.
    parser.add_argument("--stations", type=Path, default=Path("tmp/mct_pair_sources/passage_station_authoritative_map.csv"))  # Accept exact 21-station mapping.
    parser.add_argument("--passage-matrix", type=Path, default=Path("tmp/gate_passage_condensation/K12_translation_ports.csv"))  # Accept the labelled four-rope-port 12x12 condensed matrix.
    parser.add_argument("--coefficients", type=Path, default=Path("output/data/zjg_wind_tunnel_coefficients.csv"))  # Accept measured coefficient data.
    parser.add_argument("--support-mapping", type=Path, default=Path("tmp/reaction_recovery/attachment_table5_support_mapping.csv"))  # Accept the reviewed eight-location MCT support map.
    parser.add_argument("--support-reference", type=Path, default=Path("tmp/reaction_recovery/attachment_table5_2_5_3_reference.csv"))  # Accept the transcribed Attachment 2-3 reaction table.
    parser.add_argument("--output", type=Path, default=Path("output/double_mct_buffeting_results"))  # Accept a dedicated result directory.
    parser.add_argument("--modes", type=int, default=50)  # Retain low modes for displacement response.
    parser.add_argument("--mean-speed-mps", type=float, default=44.9)  # Use mean-height design speed by default.
    parser.add_argument("--minimum-frequency-hz", type=float, default=1.0 / 600.0)  # Include low modes in the nominal wind band.
    parser.add_argument("--maximum-frequency-hz", type=float, default=2.0)  # Retain the attachment upper band.
    parser.add_argument("--duration-s", type=float, default=600.0)  # Match the attachment record length.
    parser.add_argument("--dt-s", type=float, default=0.05)  # Avoid nonlinear-aliasing and resolve retained modes.
    parser.add_argument("--damping-ratio", type=float, default=0.01)  # State the missing structural damping assumption.
    parser.add_argument("--coherence-decay", type=float, default=7.0)  # State the missing Davenport decay assumption.
    parser.add_argument("--cross-width-mode", choices=("coherent", "davenport", "independent"), default="coherent")  # Match the report's implicit shared wind line by default.
    parser.add_argument("--seed-base", type=int, default=20260805)  # Freeze the first stochastic realization.
    parser.add_argument("--seed-count", type=int, default=5)  # Average independent response variances.
    return parser.parse_args()  # Return parsed options.


if __name__ == "__main__":  # Run only when invoked directly.
    run_case(parse_args())  # Execute the selected calculation.
