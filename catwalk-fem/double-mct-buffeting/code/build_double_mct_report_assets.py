from __future__ import annotations  # Enable modern type annotations.

import json  # Read machine-auditable scenario metadata.
import math  # Combine independent variances correctly.
import os  # Configure a writable plotting cache.
from pathlib import Path  # Handle result directories safely.

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-double-mct-report")  # Avoid a read-only home cache.

import matplotlib  # Configure non-interactive rendering.

matplotlib.use("Agg")  # Render figures without a display.

import matplotlib.pyplot as plt  # Draw report-ready technical charts.
from matplotlib import font_manager  # Register the bundled Chinese font.
import numpy as np  # Perform variance aggregation and plotting transforms.
import pandas as pd  # Read and write the calculation tables.

ROOT = Path("output")  # Locate calculation outputs from the workspace root.
ASSET_DIR = ROOT / "double_mct_report_assets_gate_corrected"  # Keep final gate-corrected report figures and tables together.
FONT_PATH = Path("tmp/pdfs/fonts/NotoSansCJKsc-Regular.otf")  # Reuse the verified CJK font.

if FONT_PATH.exists():  # Register Chinese glyphs when available.
    font_manager.fontManager.addfont(str(FONT_PATH))  # Add the font to Matplotlib.
    plt.rcParams["font.family"] = "Noto Sans CJK SC"  # Select the CJK family.
plt.rcParams["axes.unicode_minus"] = False  # Keep minus signs readable.

SCENARIOS = [  # Define the auditable sensitivity cases in report order.
    ("名义：44.9/full/1%/同风", ROOT / "double_mct_buffeting_results_gate_corrected_final"),  # Use 150 modes, five seeds, and full support-reaction recovery for the corrected nominal result.
    ("30.1 m/s", ROOT / "double_mct_buffeting_gate_corrected_final_U30p1"),  # Test the literal U10 speed.
    ("0.1–2 Hz", ROOT / "double_mct_buffeting_gate_corrected_final_literal_0p1_2Hz"),  # Test the attachment's literal band.
    ("跨宽相干 C=7", ROOT / "double_mct_buffeting_gate_corrected_final_Cy7"),  # Test finite cross-width coherence.
    ("阻尼 0.5%", ROOT / "double_mct_buffeting_gate_corrected_final_zeta0p5pct"),  # Test lower structural damping.
    ("阻尼 2%", ROOT / "double_mct_buffeting_gate_corrected_final_zeta2pct"),  # Test higher structural damping.
]  # Finish scenario definitions.


def select_stat(table: pd.DataFrame, station: str, response: str) -> pd.Series:  # Select exactly one station-response row.
    selected = table[(table["station"] == station) & (table["response"] == response)]  # Apply both keys.
    if len(selected) != 1:  # Guard against missing or duplicate results.
        raise ValueError(f"Expected one row for {station}/{response}, found {len(selected)}")  # Stop on result drift.
    return selected.iloc[0]  # Return the unique row.


def combined_local_roll(table: pd.DataFrame, station: str) -> tuple[float, float]:  # Combine left/right local-roll channels without losing variance.
    left = select_stat(table, station, "local_roll_L_deg")  # Read the left-width result.
    right = select_stat(table, station, "local_roll_R_deg")  # Read the right-width result.
    mean = 0.5 * (float(left["mean"]) + float(right["mean"]))  # Average the two static means.
    sigma = math.sqrt(0.5 * (float(left["sigma_multiseed"]) ** 2 + float(right["sigma_multiseed"]) ** 2))  # RMS-combine the two width variances.
    return mean, sigma  # Return the width-combined local rotation.


def build_scenario_summary() -> pd.DataFrame:  # Aggregate the response controls needed in the PDF.
    rows: list[dict[str, object]] = []  # Collect one row per scenario.
    for name, directory in SCENARIOS:  # Traverse the frozen case list.
        statistics = pd.read_csv(directory / "station_statistics_multiseed.csv")  # Read multiseed response statistics.
        audit = json.loads((directory / "calculation_audit.json").read_text(encoding="utf-8"))  # Read inputs and force controls.
        lateral = select_stat(statistics, "L/2", "lateral_common_m")  # Read midspan lateral response.
        vertical = select_stat(statistics, "L/2", "vertical_common_m")  # Read midspan vertical response.
        system_roll = select_stat(statistics, "L/2", "system_roll_deg")  # Read the separate two-width roll.
        local_mean, local_sigma = combined_local_roll(statistics, "L/2")  # Read the physically mapped local rotation.
        main_force = audit["critical_main_span_carrying_rope"]  # Read the wind-loaded main-span carrying-rope control.
        rows.append({"scenario": name, "mean_speed_mps": audit["wind"]["mean_speed_mps"], "minimum_frequency_hz": audit["wind"]["minimum_frequency_hz"], "damping_ratio": audit["structure_dynamics"]["modal_damping_ratio"], "cross_width_mode": audit["wind"]["cross_width_mode"], "seed_count": audit["wind"]["seed_count"], "mid_lateral_mean_m": float(lateral["mean"]), "mid_lateral_sigma_m": float(lateral["sigma_multiseed"]), "mid_vertical_mean_m": float(vertical["mean"]), "mid_vertical_sigma_m": float(vertical["sigma_multiseed"]), "mid_local_roll_mean_deg": local_mean, "mid_local_roll_sigma_deg": local_sigma, "mid_system_roll_mean_deg": float(system_roll["mean"]), "mid_system_roll_sigma_deg": float(system_roll["sigma_multiseed"]), "main_span_rope_peak_kn": float(main_force["peak_mean_plus_3p5sigma_kn"]), "main_span_rope_capacity_ratio": float(main_force["capacity_ratio_to_break"])})  # Record inputs and outputs together.
    return pd.DataFrame(rows)  # Return the scenario table.


def aggregate_first_three_seeds(directory: Path) -> pd.DataFrame:  # Recompute a like-for-like three-seed aggregate from a larger run.
    table = pd.read_csv(directory / "station_statistics_by_seed.csv")  # Read per-realization statistics.
    seeds = sorted(table["seed"].unique())[:3]  # Select the same first three deterministic seeds.
    table = table[table["seed"].isin(seeds)]  # Restrict to the convergence sample.
    rows: list[dict[str, object]] = []  # Collect aggregated channels.
    for (station, response), group in table.groupby(["station", "response"], sort=False):  # Group like observations.
        rows.append({"station": station, "response": response, "mean": float(group["mean"].iloc[0]), "sigma_multiseed": math.sqrt(float(np.mean(group["sigma"].to_numpy(dtype=float) ** 2)))})  # Average variances, not standard deviations.
    return pd.DataFrame(rows)  # Return the comparable aggregate.


def build_mode_convergence() -> pd.DataFrame:  # Compare 30, 50, 100, and 150 retained modes with the same first three seeds.
    cases = [(30, ROOT / "double_mct_buffeting_gate_corrected_modes30", "first3"), (50, ROOT / "double_mct_buffeting_results_gate_corrected", "first3"), (100, ROOT / "double_mct_buffeting_gate_corrected_modes100", None), (150, ROOT / "double_mct_buffeting_results_gate_corrected_final", "first3")]  # Define convergence cases.
    rows: list[dict[str, object]] = []  # Collect one row per mode count.
    for count, directory, special in cases:  # Traverse mode counts.
        table = aggregate_first_three_seeds(directory) if special == "first3" else pd.read_csv(directory / "station_statistics_multiseed.csv")  # Match three-seed statistics.
        lateral = select_stat(table, "L/2", "lateral_common_m")  # Read lateral response.
        vertical = select_stat(table, "L/2", "vertical_common_m")  # Read vertical response.
        system = select_stat(table, "L/2", "system_roll_deg")  # Read system roll.
        local_mean, local_sigma = combined_local_roll(table, "L/2")  # Read local roll.
        audit = json.loads((directory / "calculation_audit.json").read_text(encoding="utf-8"))  # Read highest retained frequency.
        rows.append({"mode_count": count, "highest_frequency_hz": float(audit["structure_dynamics"]["highest_retained_frequency_hz"]), "mid_lateral_mean_m": float(lateral["mean"]), "mid_lateral_sigma_m": float(lateral["sigma_multiseed"]), "mid_vertical_mean_m": float(vertical["mean"]), "mid_vertical_sigma_m": float(vertical["sigma_multiseed"]), "mid_local_roll_mean_deg": local_mean, "mid_local_roll_sigma_deg": local_sigma, "mid_system_roll_mean_deg": float(system["mean"]), "mid_system_roll_sigma_deg": float(system["sigma_multiseed"])})  # Record convergence metrics.
    return pd.DataFrame(rows)  # Return the convergence table.


def plot_modal_validation() -> None:  # Plot the fourteen Attachment 2-3 frequency pairs and errors.
    table = pd.read_csv("tmp/modal_validation_gate_corrected/gate_corrected_reference_table4_1_matching.csv")  # Read the independent gate-corrected one-to-one match.
    positions = np.arange(len(table))  # Create categorical positions.
    width = 0.38  # Set paired bar width.
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True, gridspec_kw={"height_ratios": [1.35, 1.0]})  # Create frequency and error panels.
    axes[0].bar(positions - width / 2.0, table["reference_frequency_hz"], width, label="附件表4-1", color="#6baed6")  # Plot reference frequencies.
    axes[0].bar(positions + width / 2.0, table["matched_frequency_hz"], width, label="双MCT四端口", color="#fd8d3c")  # Plot model frequencies.
    axes[0].set_xticks(positions, table["reference_id"], rotation=35, ha="right")  # Label mode families.
    axes[0].set_ylabel("频率 / Hz")  # Label the frequency axis.
    axes[0].grid(axis="y", alpha=0.22)  # Add a light grid.
    axes[0].legend()  # Show data sources.
    colors = np.where(table["relative_error_percent"] >= 0.0, "#3182bd", "#e6550d")  # Distinguish positive and negative errors.
    axes[1].bar(positions, table["relative_error_percent"], color=colors)  # Plot signed relative errors.
    axes[1].axhline(0.0, color="#555555", linewidth=0.8)  # Mark exact agreement.
    axes[1].set_xticks(positions, table["reference_id"], rotation=35, ha="right")  # Repeat mode labels.
    axes[1].set_ylabel("相对误差 / %")  # Label the error axis.
    axes[1].grid(axis="y", alpha=0.22)  # Add a light grid.
    fig.savefig(ASSET_DIR / "modal_14_mode_validation.png", dpi=190)  # Save the report figure.
    plt.close(fig)  # Release memory.


def plot_response_comparison() -> None:  # Plot attachment versus nominal mean and sigma for three response families.
    table = pd.read_csv(ROOT / "double_mct_buffeting_results_gate_corrected_final" / "attachment_table5_1_comparison.csv")  # Read audited comparison rows.
    families = [("lateral_common_m", "横向位移 / m"), ("vertical_common_m", "竖向位移 / m"), ("local_roll_width_combined_deg", "局部转角 / deg")]  # Define comparison panels.
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5), constrained_layout=True)  # Create mean and sigma rows.
    for column, (family, ylabel) in enumerate(families):  # Draw each physical family.
        subset = table[table["response"] == family]  # Select its three stations.
        positions = np.arange(len(subset))  # Create station positions.
        width = 0.36  # Set paired bar width.
        axes[0, column].bar(positions - width / 2.0, np.abs(subset["attachment_mean"]), width, label="附件", color="#6baed6")  # Plot absolute reference means.
        axes[0, column].bar(positions + width / 2.0, np.abs(subset["model_mean"]), width, label="模型", color="#fd8d3c")  # Plot absolute model means.
        axes[0, column].set_title(f"{ylabel}：|均值|")  # Label the mean panel.
        axes[1, column].bar(positions - width / 2.0, subset["attachment_sigma"], width, label="附件", color="#6baed6")  # Plot reference sigma.
        axes[1, column].bar(positions + width / 2.0, subset["model_sigma"], width, label="模型", color="#fd8d3c")  # Plot model sigma.
        axes[1, column].set_title(f"{ylabel}：抖振 σ")  # Label the sigma panel.
        for row in range(2):  # Format both panels.
            axes[row, column].set_xticks(positions, subset["station"])  # Label stations.
            axes[row, column].grid(axis="y", alpha=0.2)  # Add a light grid.
            axes[row, column].legend(fontsize=8)  # Show sources.
    fig.savefig(ASSET_DIR / "attachment_three_response_comparison.png", dpi=190)  # Save the comparison figure.
    plt.close(fig)  # Release memory.


def plot_sensitivity(summary: pd.DataFrame) -> None:  # Plot response sensitivity without mixing incompatible units.
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), constrained_layout=True)  # Create four response panels.
    positions = np.arange(len(summary))  # Create scenario positions.
    panels = [("mid_lateral_sigma_m", "跨中横向 σ / m"), ("mid_vertical_sigma_m", "跨中竖向 σ / m"), ("mid_local_roll_sigma_deg", "跨中局部转角 σ / deg"), ("mid_system_roll_sigma_deg", "跨中双幅滚转 σ / deg")]  # Define plotted metrics.
    for axis, (column, ylabel) in zip(axes.flat, panels):  # Draw each sensitivity metric.
        axis.bar(positions, summary[column], color="#4c78a8")  # Plot scenario values.
        axis.set_xticks(positions, summary["scenario"], rotation=24, ha="right", fontsize=8)  # Label cases compactly.
        axis.set_ylabel(ylabel)  # Label units.
        axis.grid(axis="y", alpha=0.2)  # Add a light grid.
    fig.savefig(ASSET_DIR / "buffeting_sensitivity.png", dpi=190)  # Save the sensitivity figure.
    plt.close(fig)  # Release memory.


def plot_mode_convergence(table: pd.DataFrame) -> None:  # Plot the 30/50/100/150 mode convergence check.
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.3), constrained_layout=True)  # Create three response panels.
    axes[0].plot(table["mode_count"], table["mid_lateral_sigma_m"], marker="o")  # Plot lateral sigma convergence.
    axes[0].set_ylabel("跨中横向 σ / m")  # Label lateral response.
    axes[1].plot(table["mode_count"], table["mid_vertical_sigma_m"], marker="o")  # Plot vertical sigma convergence.
    axes[1].set_ylabel("跨中竖向 σ / m")  # Label vertical response.
    axes[2].plot(table["mode_count"], table["mid_local_roll_sigma_deg"], marker="o")  # Plot local-roll sigma convergence.
    axes[2].set_ylabel("跨中局部转角 σ / deg")  # Label local rotation.
    for axis in axes:  # Format all convergence panels.
        axis.set_xlabel("保留模态数")  # Label the common abscissa.
        axis.set_xticks(table["mode_count"])  # Show tested counts.
        axis.grid(alpha=0.22)  # Add a light grid.
    fig.savefig(ASSET_DIR / "mode_count_convergence.png", dpi=190)  # Save the convergence figure.
    plt.close(fig)  # Release memory.


def plot_rope_forces() -> None:  # Plot full-line physical-rope mean and design-peak recovery.
    directory = ROOT / "double_mct_buffeting_results_gate_corrected_final"  # Locate the 150-mode corrected nominal force and reaction recovery.
    carrying = pd.read_csv(directory / "carrying_rope_force_recovery.csv")  # Read carrying ropes.
    gantry = pd.read_csv(directory / "gantry_rope_force_recovery.csv")  # Read gantry ropes.
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), constrained_layout=True)  # Create one panel per rope family.
    for axis, table, title in ((axes[0], carrying, "承重索：单根等效恢复"), (axes[1], gantry, "门架索：单根等效恢复")):  # Draw both families.
        for width, color in (("L", "#3182bd"), ("R", "#e6550d")):  # Separate the two MCT planes.
            subset = table[table["width"] == width].sort_values("element_id")  # Select and order one width.
            axis.plot(subset["element_id"], subset["mean_tension_per_rope_kn"], color=color, linewidth=0.8, alpha=0.75, label=f"{width} 均值")  # Plot mean tension.
            axis.plot(subset["element_id"], subset["peak_mean_plus_3p5sigma_kn"], color=color, linewidth=1.2, label=f"{width} 均值+3.5σ")  # Plot design peak.
        axis.set_ylabel("轴力 / kN·根$^{-1}$")  # Label the physical-rope force.
        axis.set_title(title)  # Label the family.
        axis.grid(alpha=0.2)  # Add a light grid.
        axis.legend(ncol=4, fontsize=8)  # Show line meanings.
    axes[-1].set_xlabel("MCT 源单元号")  # Label the source identity axis.
    fig.savefig(ASSET_DIR / "rope_force_recovery.png", dpi=190)  # Save the force figure.
    plt.close(fig)  # Release memory.


def plot_measured_coefficients() -> None:  # Plot the measured Attachment 2-3 three-force table without refitting it.
    table = pd.read_csv(ROOT / "data" / "zjg_wind_tunnel_coefficients.csv")  # Read the frozen coefficient table.
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0), constrained_layout=True)  # Create one panel per coefficient.
    for axis, column, label, color in zip(axes, ("CD", "CL", "CM"), (r"$C_D$", r"$C_L$", r"$C_M$"), ("#3182bd", "#31a354", "#e6550d")):  # Draw all measured curves.
        axis.plot(table["alpha_deg"], table[column], marker="o", markersize=2.8, linewidth=1.2, color=color)  # Plot the discrete one-degree data.
        axis.axvline(0.0, color="#666666", linewidth=0.7)  # Mark zero attack angle.
        axis.set_xlabel("攻角 / deg")  # Label the abscissa.
        axis.set_ylabel(label)  # Label the coefficient.
        axis.grid(alpha=0.22)  # Add a light grid.
    fig.savefig(ASSET_DIR / "measured_three_force_coefficients.png", dpi=190)  # Save the coefficient figure.
    plt.close(fig)  # Release memory.


def main() -> None:  # Build every final report table and figure.
    ASSET_DIR.mkdir(parents=True, exist_ok=True)  # Create the dedicated asset directory.
    summary = build_scenario_summary()  # Aggregate sensitivity results.
    summary.to_csv(ASSET_DIR / "scenario_summary.csv", index=False)  # Freeze the scenario table.
    convergence = build_mode_convergence()  # Aggregate mode-count convergence.
    convergence.to_csv(ASSET_DIR / "mode_count_convergence.csv", index=False)  # Freeze the convergence table.
    plot_modal_validation()  # Draw the fourteen-mode comparison.
    plot_response_comparison()  # Draw attachment response comparisons.
    plot_sensitivity(summary)  # Draw stochastic-input sensitivity.
    plot_mode_convergence(convergence)  # Draw modal truncation convergence.
    plot_rope_forces()  # Draw full-line rope force recovery.
    plot_measured_coefficients()  # Draw the measured aerodynamic inputs.
    print(summary.to_string(index=False))  # Show the final sensitivity table.
    print("\nMode-count convergence:")  # Label the convergence log.
    print(convergence.to_string(index=False))  # Show the convergence table.


if __name__ == "__main__":  # Run only when invoked directly.
    main()  # Build final report assets.
