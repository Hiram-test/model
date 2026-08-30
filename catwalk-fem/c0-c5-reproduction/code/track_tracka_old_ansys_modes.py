#!/usr/bin/env python3  # Execute the strict Track A mode tracker with the active Python interpreter.
from __future__ import annotations  # Keep annotations deterministic on the supported Python runtime.
from pathlib import Path  # Resolve native result and output paths independently of caller cwd.
import argparse  # Read baseline, test, and output locations explicitly.
import csv  # Publish the complete one-to-one mode-tracking table.
import hashlib  # Bind native result and generated evidence byte streams.
import json  # Publish the complete machine-readable tracking record.
import math  # Evaluate frequencies, angular frequencies, and finite modal metrics.
import re  # Parse CalculiX DAT and FRD numerical records.
import numpy as np  # Compute mode-vector norms, correlations, and the MAC matrix.
from scipy.optimize import linear_sum_assignment  # Compute the global one-to-one maximum-MAC assignment.
LABELS = {1: "C3_M1", 2: "C3_M2", 3: "C3_M3", 4: "C3_M4", 5: "C3_M5", 6: "C3_M6", 7: "C3_M7", 8: "C3_M8", 9: "C3_M9", 11: "C3_M11", 12: "C3_M12", 13: "C3_M13", 15: "C3_M15", 21: "C3_M21"}  # C3 native order only; C3_M3=0.07267 is NOT attach TA1 0.0996.
FORENSIC_LABELS = ("C3_M3", "C3_M6", "C3_M13", "C3_M15", "C3_M21")  # Same five C3 indices; not attach TA1/TS1/TS2/SIDE3/VS2.
class TrackingError(RuntimeError):  # Represent one stable mode-tracking failure.
    pass  # Keep the semantic exception behavior-free.
def require(condition: bool, code: str, detail: str) -> None:  # Enforce one explicit tracking invariant.
    if not condition:  # Reject every condition not positively established.
        raise TrackingError(f"{code}: {detail}")  # Surface a stable code with bounded context.
def sha256_file(path: Path) -> str:  # Compute one exact file identity by streaming.
    digest = hashlib.sha256()  # Initialize a fresh SHA-256 state.
    with path.open("rb") as handle:  # Open the complete file without decoding.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Traverse fixed-size blocks to EOF.
            digest.update(block)  # Bind each exact byte once.
    return digest.hexdigest()  # Return the lowercase hexadecimal identity.
def largest_file(directory: Path, suffix: str) -> Path:  # Select the largest complete native file with one suffix.
    files = [path for path in directory.rglob(f"*{suffix}") if path.is_file()]  # Collect matching files recursively.
    require(bool(files), "NATIVE_FILE_MISSING", f"{directory} {suffix}")  # Require at least one matching native file.
    return max(files, key=lambda path: path.stat().st_size)  # Return the largest matching file.
def parse_frequencies(path: Path) -> list[float]:  # Parse the ordered CalculiX eigenfrequency table.
    text = path.read_text(encoding="ascii", errors="ignore")  # Decode the native DAT output.
    frequencies: dict[int, float] = {}  # Map one-based modes to frequencies.
    active = False  # Track entry into an eigenvalue-output table.
    for raw in text.splitlines():  # Traverse every DAT line.
        upper = raw.upper()  # Normalize header matching.
        if "E I G E N V A L U E" in upper or ("MODE" in upper and "FREQUENCY" in upper):  # Detect an eigenvalue-table header.
            active = True  # Enable numeric-row parsing.
            continue  # Continue to the next line.
        if not active:  # Ignore output preceding the table.
            continue  # Continue scanning.
        tokens = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?", raw)  # Extract numeric tokens.
        if len(tokens) < 3:  # Require a mode number and numerical columns.
            continue  # Skip nonnumeric table lines.
        try:  # Parse candidate columns defensively.
            values = [float(token.replace("D", "E").replace("d", "e")) for token in tokens]  # Convert Fortran-style exponents.
        except ValueError:  # Ignore malformed rows.
            continue  # Continue scanning.
        mode = int(round(values[0]))  # Interpret the first column as a one-based mode number.
        if abs(values[0] - mode) > 1.0e-9 or not 1 <= mode <= 500:  # Reject nonintegral or implausible mode labels.
            continue  # Continue scanning.
        plausible = [value for value in values[1:] if math.isfinite(value) and 0.0 < value < 10.0]  # Retain plausible catwalk frequency columns.
        if plausible and mode not in frequencies:  # Preserve the first complete row per mode.
            frequencies[mode] = plausible[-1]  # Store the final positive sub-ten column as frequency in hertz.
    require(bool(frequencies), "FREQUENCY_TABLE_UNPARSED", str(path))  # Require at least one parsed eigenfrequency.
    ordered_modes = sorted(frequencies)  # Select parsed mode labels in ascending order.
    require(ordered_modes == list(range(1, max(ordered_modes) + 1)), "FREQUENCY_MODE_GAP", repr(ordered_modes[:10]))  # Require a contiguous one-based spectrum.
    return [frequencies[mode] for mode in ordered_modes]  # Return the complete ordered frequency list.
def parse_frd_modes(path: Path) -> tuple[list[dict[int, np.ndarray]], dict[int, np.ndarray]]:  # Parse sequential displacement datasets and available coordinates from one FRD file.
    modes: list[dict[int, np.ndarray]] = []  # Accumulate one node-vector mapping per displacement dataset.
    coordinates: dict[int, np.ndarray] = {}  # Accumulate available node coordinates.
    current: dict[int, np.ndarray] | None = None  # Hold the active displacement dataset.
    in_coordinates = False  # Track the initial coordinate block.
    in_displacement = False  # Track one displacement result block.
    with path.open("r", encoding="ascii", errors="ignore") as handle:  # Stream the native FRD file once.
        for raw in handle:  # Traverse every FRD record.
            code = raw[:3]  # Read the standard three-character record code.
            upper = raw.upper()  # Normalize result labels.
            if "2C" in raw[:10] and not coordinates and not modes:  # Detect the initial coordinate block.
                in_coordinates = True  # Enable coordinate parsing.
                continue  # Continue to coordinate data rows.
            if code == " -3" and in_coordinates:  # Detect the coordinate terminator.
                in_coordinates = False  # Close coordinate parsing.
                continue  # Continue to result blocks.
            if code == " -4" and "DISP" in upper:  # Detect one displacement dataset.
                if current:  # Preserve a nonempty unterminated prior dataset defensively.
                    modes.append(current)  # Append the prior displacement mapping.
                current = {}  # Start a fresh displacement mapping.
                in_displacement = True  # Enable displacement parsing.
                continue  # Continue to component and data rows.
            if code == " -3" and in_displacement:  # Detect the displacement dataset terminator.
                if current:  # Preserve the complete dataset.
                    modes.append(current)  # Append the displacement mapping.
                current = None  # Clear the active mapping.
                in_displacement = False  # Close displacement parsing.
                continue  # Continue to the next result dataset.
            if code != " -1":  # Admit data rows only.
                continue  # Skip metadata and component records.
            tokens = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?", raw[3:])  # Extract node and vector values.
            if len(tokens) < 4:  # Require a node label and three components.
                continue  # Skip incomplete rows.
            try:  # Parse the data row defensively.
                node = int(tokens[0])  # Parse the node label.
                vector = np.asarray([float(token.replace("D", "E").replace("d", "e")) for token in tokens[1:4]], dtype=float)  # Parse XYZ components.
            except ValueError:  # Ignore malformed rows.
                continue  # Continue scanning.
            if in_coordinates:  # Store coordinate rows.
                coordinates[node] = vector  # Preserve the node coordinate.
            elif in_displacement and current is not None:  # Store displacement rows.
                current[node] = vector  # Preserve the nodal result vector.
    if current:  # Preserve an unterminated final displacement dataset defensively.
        modes.append(current)  # Append the final mapping.
    require(bool(modes), "FRD_DISPLACEMENT_UNPARSED", str(path))  # Require at least one displacement dataset.
    return modes, coordinates  # Return ordered displacement datasets and coordinates.
def select_modal_datasets(datasets: list[dict[int, np.ndarray]], frequency_count: int) -> list[dict[int, np.ndarray]]:  # Select the modal displacement datasets after any preceding static output.
    require(len(datasets) >= frequency_count, "FRD_DATASET_COUNT_TOO_SMALL", f"datasets={len(datasets)} frequencies={frequency_count}")  # Require at least one dataset per eigenfrequency.
    return datasets[-frequency_count:]  # Use the final frequency-count datasets because the modal step is appended last.
def flatten(mode: dict[int, np.ndarray], nodes: list[int]) -> np.ndarray:  # Flatten one mode on a frozen common node set.
    return np.concatenate([mode[node] for node in nodes]).astype(float, copy=False)  # Concatenate XYZ vectors in node order.
def infer_pairs(coordinates: dict[int, np.ndarray], nodes: list[int]) -> list[tuple[int, int, float]]:  # Infer left-right observation stations from geometry.
    available = [(node, coordinates[node]) for node in nodes if node in coordinates]  # Retain common observation nodes with coordinates.
    negative = [(node, xyz) for node, xyz in available if xyz[1] < 0.0]  # Select one transverse side.
    positive = [(node, xyz) for node, xyz in available if xyz[1] > 0.0]  # Select the opposite transverse side.
    pairs: list[tuple[int, int, float]] = []  # Accumulate paired stations.
    used: set[int] = set()  # Prevent repeated opposite-side assignments.
    for left, left_xyz in sorted(negative, key=lambda item: item[1][0]):  # Traverse negative-side nodes along the bridge.
        candidates: list[tuple[float, int, np.ndarray]] = []  # Accumulate symmetric geometry candidates.
        for right, right_xyz in positive:  # Compare unused opposite-side nodes.
            if right in used:  # Skip already assigned nodes.
                continue  # Continue to the next candidate.
            longitudinal = abs(float(left_xyz[0] - right_xyz[0])) / max(1.0, abs(float(left_xyz[0])), abs(float(right_xyz[0])))  # Measure normalized station mismatch.
            elevation = abs(float(left_xyz[2] - right_xyz[2])) / max(1.0, abs(float(left_xyz[2])), abs(float(right_xyz[2])))  # Measure normalized elevation mismatch.
            symmetry = abs(abs(float(left_xyz[1])) - abs(float(right_xyz[1]))) / max(1.0, abs(float(left_xyz[1])), abs(float(right_xyz[1])))  # Measure transverse symmetry mismatch.
            candidates.append((longitudinal + elevation + symmetry, right, right_xyz))  # Preserve the total geometric mismatch.
        if not candidates:  # Stop when no opposite-side nodes remain.
            break  # Exit the pairing loop.
        score, right, right_xyz = min(candidates, key=lambda item: item[0])  # Select the closest symmetric partner.
        if score <= 0.05:  # Admit a reasonably symmetric observation pair.
            used.add(right)  # Reserve the opposite-side node.
            pairs.append((left, right, 0.5 * float(left_xyz[0] + right_xyz[0])))  # Preserve the pair and longitudinal station.
    return sorted(pairs, key=lambda item: item[2])  # Return longitudinally ordered pairs.
def visible_signature(mode: dict[int, np.ndarray], pairs: list[tuple[int, int, float]]) -> dict[str, float | int | None]:  # Compute signatures visible to an old ANSYS user inspecting deformed shapes.
    if len(pairs) < 3:  # Require several stations for longitudinal interpretation.
        return {"pair_count": len(pairs), "lr_vertical_correlation": None, "roll_participation": None, "half_wave_sign_changes": None}  # Return explicit missing indicators.
    left = np.asarray([mode[first][2] for first, _, _ in pairs], dtype=float)  # Collect one-side vertical components.
    right = np.asarray([mode[second][2] for _, second, _ in pairs], dtype=float)  # Collect opposite-side vertical components.
    differential = right - left  # Form the roll-sensitive differential signal.
    common = 0.5 * (right + left)  # Form the common vertical-bending signal.
    correlation = float(np.corrcoef(left, right)[0, 1]) if np.std(left) > 0.0 and np.std(right) > 0.0 else None  # Compute left-right vertical phase correlation.
    roll_norm = float(np.linalg.norm(differential))  # Measure roll-sensitive amplitude.
    common_norm = float(np.linalg.norm(common))  # Measure common vertical amplitude.
    participation = roll_norm / max(roll_norm + common_norm, 1.0e-30)  # Form a bounded roll participation indicator.
    threshold = 0.05 * float(np.max(np.abs(differential))) if differential.size else 0.0  # Define a relative nodal-noise threshold.
    signs = [int(np.sign(value)) for value in differential if abs(float(value)) > threshold]  # Remove near-zero station values.
    changes = sum(first != second for first, second in zip(signs, signs[1:]))  # Count longitudinal sign changes.
    return {"pair_count": len(pairs), "lr_vertical_correlation": correlation, "roll_participation": participation, "half_wave_sign_changes": changes}  # Return the complete visible signature.
def main() -> None:  # Execute global C3-to-Track-A mode tracking.
    parser = argparse.ArgumentParser(description="Track a hypothesized command-path Track A daughter against unchanged C3. C3 M3 is not attach TA1.")  # Define the command-line interface.
    parser.add_argument("--baseline-dir", required=True, type=Path)  # Select the extracted unchanged-C3 baseline artifact directory.
    parser.add_argument("--test-dat", required=True, type=Path)  # Select the strict Track A native DAT output.
    parser.add_argument("--test-frd", required=True, type=Path)  # Select the strict Track A native FRD output.
    parser.add_argument("--output-dir", required=True, type=Path)  # Select the stable analysis output directory.
    parser.add_argument("--baseline-count", type=int, default=40)  # Select the C3 comparison range.
    arguments = parser.parse_args()  # Parse the explicit command-line arguments.
    arguments.output_dir.mkdir(parents=True, exist_ok=True)  # Create the stable tracking output directory.
    baseline_dat = largest_file(arguments.baseline_dir, ".dat")  # Select the unchanged C3 DAT output.
    baseline_frd = largest_file(arguments.baseline_dir, ".frd")  # Select the unchanged C3 FRD output.
    baseline_frequency_all = parse_frequencies(baseline_dat)  # Parse the baseline eigenfrequency spectrum.
    test_frequency = parse_frequencies(arguments.test_dat)  # Parse the strict Track A eigenfrequency spectrum.
    baseline_datasets, baseline_coordinates = parse_frd_modes(baseline_frd)  # Parse baseline displacement datasets and coordinates.
    test_datasets, test_coordinates = parse_frd_modes(arguments.test_frd)  # Parse Track A displacement datasets and coordinates.
    baseline_count = min(arguments.baseline_count, len(baseline_frequency_all))  # Bound the baseline comparison range by available modes.
    require(baseline_count >= 21, "BASELINE_RANGE_TOO_SMALL", str(baseline_count))  # Retain all five forensic C3 branches.
    require(len(test_frequency) >= baseline_count, "TEST_RANGE_TOO_SMALL", f"test={len(test_frequency)} baseline={baseline_count}")  # Require enough Track A candidates for one-to-one assignment.
    baseline_frequency = baseline_frequency_all[:baseline_count]  # Select the frozen baseline comparison spectrum.
    baseline_modes_all = select_modal_datasets(baseline_datasets, len(baseline_frequency_all))  # Remove any preceding nonmodal baseline datasets.
    test_modes = select_modal_datasets(test_datasets, len(test_frequency))  # Remove preceding static result datasets from the appended modal run.
    baseline_modes = baseline_modes_all[:baseline_count]  # Select the frozen baseline comparison modes.
    common_nodes = sorted(set.intersection(*(set(mode) for mode in baseline_modes + test_modes)))  # Require observation nodes available in every compared mode.
    require(bool(common_nodes), "COMMON_OBSERVATION_SET_EMPTY", f"baseline={baseline_frd} test={arguments.test_frd}")  # Reject disjoint result fields.
    baseline_vectors = np.vstack([flatten(mode, common_nodes) for mode in baseline_modes])  # Form the baseline mode matrix.
    test_vectors = np.vstack([flatten(mode, common_nodes) for mode in test_modes])  # Form the Track A mode matrix.
    numerator = np.abs(baseline_vectors @ test_vectors.T) ** 2  # Compute squared modal cross products.
    denominator = np.sum(baseline_vectors * baseline_vectors, axis=1)[:, None] * np.sum(test_vectors * test_vectors, axis=1)[None, :]  # Form MAC denominators.
    mac = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0.0)  # Evaluate the complete rectangular MAC matrix safely.
    baseline_indices, test_indices = linear_sum_assignment(-mac)  # Compute the global maximum-MAC one-to-one assignment.
    assignment = {int(first): int(second) for first, second in zip(baseline_indices, test_indices)}  # Map zero-based baseline modes to unique Track A modes.
    require(set(assignment) == set(range(baseline_count)), "ASSIGNMENT_INCOMPLETE", str(len(assignment)))  # Require every baseline mode to receive one unique Track A partner.
    coordinates = dict(baseline_coordinates)  # Start with baseline observation coordinates.
    coordinates.update(test_coordinates)  # Fill coordinates available only in the Track A result.
    pairs = infer_pairs(coordinates, common_nodes)  # Infer left-right stations for visible-shape interpretation.
    rows: list[dict[str, object]] = []  # Initialize the complete tracking table.
    for baseline_index in range(baseline_count):  # Traverse every baseline mode in order.
        track_index = assignment[baseline_index]  # Select its globally assigned Track A partner.
        baseline_mode = baseline_index + 1  # Convert to one-based baseline numbering.
        track_mode = track_index + 1  # Convert to one-based Track A numbering.
        baseline_hz = baseline_frequency[baseline_index]  # Select the baseline frequency.
        track_hz = test_frequency[track_index]  # Select the Track A frequency.
        baseline_signature = visible_signature(baseline_modes[baseline_index], pairs)  # Compute baseline visible-shape signatures.
        track_signature = visible_signature(test_modes[track_index], pairs)  # Compute Track A visible-shape signatures.
        baseline_omega_squared = (2.0 * math.pi * baseline_hz) ** 2  # Convert the baseline frequency to squared angular frequency.
        track_omega_squared = (2.0 * math.pi * track_hz) ** 2  # Convert the Track A frequency to squared angular frequency.
        rows.append({"baseline_mode": baseline_mode, "label": LABELS.get(baseline_mode, ""), "baseline_frequency_hz": baseline_hz, "track_mode": track_mode, "track_frequency_hz": track_hz, "frequency_change_percent": 100.0 * (track_hz / baseline_hz - 1.0), "delta_omega_squared_rad2_per_s2": track_omega_squared - baseline_omega_squared, "relative_delta_omega_squared": (track_omega_squared - baseline_omega_squared) / baseline_omega_squared, "mac": float(mac[baseline_index, track_index]), "within_first_14_track_modes": track_mode <= 14, "baseline_lr_vertical_correlation": baseline_signature["lr_vertical_correlation"], "track_lr_vertical_correlation": track_signature["lr_vertical_correlation"], "baseline_roll_participation": baseline_signature["roll_participation"], "track_roll_participation": track_signature["roll_participation"], "baseline_half_wave_sign_changes": baseline_signature["half_wave_sign_changes"], "track_half_wave_sign_changes": track_signature["half_wave_sign_changes"]})  # Preserve one complete one-to-one tracking row.
    csv_path = arguments.output_dir / "all40_global_one_to_one_tracking.csv"  # Resolve the complete tracking table path.
    with csv_path.open("w", encoding="utf-8", newline="") as handle:  # Open the complete CSV output.
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))  # Bind the stable output schema.
        writer.writeheader()  # Write the CSV header.
        writer.writerows(rows)  # Write all tracking rows.
    np.savetxt(arguments.output_dir / "mac_matrix_40x80.csv", mac, delimiter=",", fmt="%.12g")  # Publish the complete rectangular MAC matrix.
    selected = [row for row in rows if row["label"] in FORENSIC_LABELS]  # Select the five forensic physical branches.
    first14 = [{"mode": index + 1, "frequency_hz": frequency} for index, frequency in enumerate(test_frequency[:14])]  # Preserve the natural first-fourteen solver order visible in old ANSYS.
    report = {"status": "TRACKED", "human_apdl": False, "frequency_reproduced": False, "not_attach_ta1": True, "c3_m3_hz": 0.07267216, "attach_ta1_hz": 0.0996, "c3_m3_is_not_attach_ta1": True, "source": "agent_constructed_hypothesized_command_path", "assignment_method": "global one-to-one maximum MAC on common observation DOFs; 40 C3 modes assigned uniquely into 80 Track A candidates", "target_frequency_used_for_assignment": False, "nearest_frequency_assignment_used": False, "baseline_mode_count": baseline_count, "test_mode_count": len(test_frequency), "common_observation_node_count": len(common_nodes), "left_right_pair_count": len(pairs), "first14_solver_order": first14, "selected_branches": selected, "native_inputs": {"baseline_dat": {"path": str(baseline_dat), "sha256": sha256_file(baseline_dat)}, "baseline_frd": {"path": str(baseline_frd), "sha256": sha256_file(baseline_frd)}, "test_dat": {"path": str(arguments.test_dat), "sha256": sha256_file(arguments.test_dat)}, "test_frd": {"path": str(arguments.test_frd), "sha256": sha256_file(arguments.test_frd)}}}  # Build the complete machine-readable tracking record.
    (arguments.output_dir / "TRACK_A_OLD_ANSYS_MODE_TRACKING.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")  # Publish the complete JSON tracking record.
    lines = ["# C3 至假设命令路径 Track A 的全局一对一模态追踪", "", "frequency_reproduced=false. human_apdl=false. C3 M3 0.07267 is not attach TA1 0.0996. Do not write 复现 or 一致.", "", "分支配对不读取附件目标频率，也不采用逐项最近频率。C3 前 40 阶通过矩形 MAC 矩阵唯一分配到 Track A 前 80 阶。C3_M* 是原生阶次标签，不是附件家族名。", "", "| C3 index | C3阶次/Hz | daughter阶次/Hz | 频率变化 | Δω² | MAC | 前14阶内 | 左右幅相关 | 滚转参与率 | 纵向符号变化 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]  # Initialize the compact human-readable report.
    for row in selected:  # Format the five selected branches.
        lines.append(f"| {row['label']} | M{row['baseline_mode']} / {row['baseline_frequency_hz']:.8f} | M{row['track_mode']} / {row['track_frequency_hz']:.8f} | {row['frequency_change_percent']:+.3f}% | {row['delta_omega_squared_rad2_per_s2']:+.8g} | {row['mac']:.4f} | {'是' if row['within_first_14_track_modes'] else '否'} | {row['track_lr_vertical_correlation']} | {row['track_roll_participation']} | {row['track_half_wave_sign_changes']} |")  # Append one complete branch row.
    lines.extend(["", "## daughter 求解器自然前14阶（不是附件家族）", "", "| 阶次 | 频率/Hz |", "|---:|---:|"])  # Add the natural solver-order table header.
    for item in first14:  # Format every natural-order mode.
        lines.append(f"| {item['mode']} | {item['frequency_hz']:.8f} |")  # Append one frequency row.
    (arguments.output_dir / "TRACK_A_OLD_ANSYS_MODE_TRACKING.md").write_text("\n".join(lines) + "\n", encoding="utf-8")  # Publish the compact Markdown report.
if __name__ == "__main__":  # Execute only when invoked as a script.
    main()  # Run global C3-to-Track-A mode tracking.
