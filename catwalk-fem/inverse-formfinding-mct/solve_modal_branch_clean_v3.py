from __future__ import annotations  # Enable stable modern type annotations.
import json  # Write deterministic target-free calculation receipts and branch audits.
import os  # Record the exact GitHub source revision used by the calculation.
from pathlib import Path  # Resolve the isolated output directory safely.
import solve_modal_branch_clean as core  # Reuse the complete branch-metric implementation.
import solve_modal_branch_clean_v2 as ranked  # Reuse the corrected immutable branch-rank selector.

OUT = Path(__file__).resolve().parent / "modal_results_branch_clean_v3"  # Isolate the final branch-clean recalculation from all earlier results.
OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated result directory idempotently.
core.OUT = OUT  # Redirect the shared result writer into the final result directory.
core.base.OUT = OUT  # Redirect the reused matrix solver outputs into the final result directory.
core.v2.OUT = OUT  # Redirect the reused mass-consistent assembly outputs into the final result directory.
core.v4.OUT = OUT  # Redirect the reused drawing-corrected outputs into the final result directory.
ranked.OUT = OUT  # Redirect the ranked wrapper outputs into the final result directory.


def select_side_branches(raw: list[dict]) -> dict[str, dict]:  # Select the lowest global branch localized in each declared side span.
    selected: dict[str, dict] = {}  # Initialize the three side-span assignments.
    used: set[int] = set()  # Prevent one numerical mode from receiving two side-span labels.
    definitions = [("SIDE1", "south717_fraction"), ("SIDE2", "north_fraction"), ("SIDE3", "south503_fraction")]  # Map each SIDE label to its predeclared physical span.
    for label, fraction_key in definitions:  # Traverse all three physical side spans.
        candidates = [record for record in raw if record["mode"] not in used and record[fraction_key] >= core.SIDE_FRACTION_MIN and record["localization"] <= core.LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Apply only span localization, global-mode localization, and the low-frequency band.
        if candidates:  # Test whether the declared side span contains a global branch.
            choice = min(candidates, key=lambda record: (record["frequency_hz"], -record[fraction_key]))  # Select the lowest computed global branch in that span.
            selected[label] = {**choice, "selection_rule": f"lowest global branch with {fraction_key}>={core.SIDE_FRACTION_MIN:.2f}; no floor-gantry coherence gate for a side-localized branch"}  # Store the selected side branch and its explicit rule.
            used.add(int(choice["mode"]))  # Mark the numerical mode as consumed by a side label.
        else:  # Handle a physically absent side branch honestly.
            selected[label] = {"status": "unidentified", "selection_rule": f"no global branch with {fraction_key}>={core.SIDE_FRACTION_MIN:.2f}"}  # Preserve an explicit unidentified state.
    return selected  # Return all three side-span assignments.


def harmonic_candidate(raw: list[dict], family: str, relation: str, parity_label: str, harmonic_order: int) -> dict | None:  # Find a main-span candidate under the older harmonic-sequence convention for audit only.
    candidates = [record for record in raw if record["family"] == family and record["catwalk_relation"] == relation and record["parity_label"] == parity_label and record["harmonic_order_descriptor"] == harmonic_order and record["main_fraction"] >= core.MAIN_FRACTION_MIN and record["floor_gantry_acoustic_coherence"] >= core.ACOUSTIC_COHERENCE_MIN and record["localization"] <= core.LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Apply the same physical main-span filters plus the requested descriptive harmonic order.
    if not candidates:  # Test whether the requested harmonic descriptor is absent.
        return None  # Return an explicit missing candidate.
    return min(candidates, key=lambda record: record["frequency_hz"])  # Return the lowest physical candidate carrying that descriptor.


def main() -> int:  # Execute the complete inverse-static, matrix, eigen, branch-rank, and ambiguity-audit recalculation.
    core.v4.apply_drawing_corrections()  # Apply only independently documented drawing corrections before assembly.
    model = core.base.load_mct()  # Parse and hash-check the sole MCT geometry, topology, support, and load source.
    floor_nodes, floor_elements = core.base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-chain topology.
    top_nodes, top_elements = core.base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope topology.
    static = core.previous.recover_static_state(model)  # Recompute the unique MCT-geometry inverse axial-force state from scratch.
    if not bool(static["success"]):  # Reject any inverse-solver failure before dynamic assembly.
        raise RuntimeError(str(static["message"]))  # Report the exact inverse-solver failure.
    if int(static["nullity"]) != 0:  # Require a unique aggregate force field.
        raise RuntimeError(f"Inverse equilibrium nullity is {static['nullity']}")  # Reject an unresolved self-stress branch.
    if float(static["min_cable_force_kN"]) <= 0.0:  # Require every cable member to remain in tension.
        raise RuntimeError(f"Minimum recovered cable force is {static['min_cable_force_kN']:.6f} kN")  # Reject cable compression before geometric-stiffness assembly.
    if float(static["max_abs_force_error_percent"]) > 0.5:  # Preserve the declared elementwise initial-force agreement threshold.
        raise RuntimeError(f"Maximum MCT initial-force mismatch is {static['max_abs_force_error_percent']:.6f}%")  # Reject an inverse state that no longer matches the verified MCT force field.
    system = core.v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Reassemble the complete drawing-corrected rope, portal, passage, and mass matrices.
    frequencies, vectors, residuals, matrix_checks = core.base.solve_eigen(system)  # Recompute and verify the low generalized eigenpairs.
    raw, shapes = core.modal_records(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Recompute every target-free global branch metric.
    selected = ranked.select_branches(raw)  # Select all main-span branches by family, relation, parity, and ascending physical branch rank.
    selected.update(select_side_branches(raw))  # Replace the three SIDE labels with the lowest global branch in each declared physical side span.
    alternate_vs2 = harmonic_candidate(raw, "V", "common", "S", 5)  # Record the main-span symmetric vertical n=5 candidate for audit only.
    alternate_ts2 = harmonic_candidate(raw, "T", "differential", "S", 5)  # Record the main-span symmetric torsional n=5 candidate for audit only.
    ambiguity_audit = {"VS2": {"branch_rank_candidate": selected.get("VS2"), "harmonic_sequence_n5_candidate": alternate_vs2, "interpretation": "VS2 is selected as the second acoustic main-span common-vertical symmetric branch; the n=5 mode is retained separately because harmonic order is not the branch definition."}, "TS2": {"branch_rank_candidate": selected.get("TS2"), "harmonic_sequence_n5_candidate": alternate_ts2, "interpretation": "TS2 is selected as the second acoustic main-span differential-vertical symmetric branch; the n=5 mode is retained separately because the attachment does not provide a machine-readable TS2 mode vector."}}  # Preserve both branch-rank and older harmonic-sequence candidates without frequency-based adjudication.
    identified = {label: float(record["frequency_hz"]) for label, record in selected.items() if "frequency_hz" in record}  # Build the concise final identified-frequency map.
    frozen = {"kind": "mct_inverse_prestress_modal_branch_clean_v3", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False, "mct_initial_force_used_in_inverse": False, "mct_initial_force_loaded_after_inverse_for_verification": True, "classification_uses_fixed_harmonic_order": False, "classification_rule": "main-span labels use global L/V/T field, common or differential catwalk relation, midpoint parity, floor-gantry acoustic coherence, and ascending physical branch rank; SIDE labels use the lowest global branch in each predeclared side span; harmonic order is descriptive only", "thresholds": {"acoustic_coherence_min_main": core.ACOUSTIC_COHERENCE_MIN, "main_fraction_min": core.MAIN_FRACTION_MIN, "side_fraction_min": core.SIDE_FRACTION_MIN, "localization_max": core.LOCALIZATION_MAX, "floor_participation_min_main": core.FLOOR_PARTICIPATION_MIN}, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": matrix_checks, "mass_audit": system["mass_audit_v2"], "first_40_frequencies_hz": [float(value) for value in frequencies[:40]], "raw_modes": raw, "classified_14": selected, "classification_ambiguity_audit": ambiguity_audit}  # Assemble the immutable target-free final recalculation record.
    frozen_path = OUT / "frozen_results_branch_clean_v3.json"  # Define the immutable target-free result path.
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Freeze the complete recalculation before external comparison.
    frozen_sha256 = core.base.sha(frozen_path)  # Compute the immutable result digest.
    summary = {"kind": "mct_inverse_prestress_modal_branch_clean_summary_v3", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha256, "inverse_static": frozen["inverse_static"], "matrix_checks": matrix_checks, "identified_count": int(len(identified)), "identified_frequencies_hz": identified, "alternate_candidates_hz": {"VS2_n5": None if alternate_vs2 is None else float(alternate_vs2["frequency_hz"]), "TS2_n5": None if alternate_ts2 is None else float(alternate_ts2["frequency_hz"])}, "classification_uses_fixed_harmonic_order": False, "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False}  # Build the concise target-free final receipt.
    core.write_outputs(raw, selected, shapes, summary)  # Write the raw branch table, final fourteen-family table, shape fields, and summary.
    (OUT / "classification_ambiguity_audit.json").write_text(json.dumps(ambiguity_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the VS2 and TS2 candidate audit separately.
    core.base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve every explicit rope force and recovered unstressed length.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{core.base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every generated target-free result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete final recalculation summary into the workflow log.
    return 0  # Report successful final recalculation completion.


if __name__ == "__main__":  # Execute only when invoked as the main calculation program.
    raise SystemExit(main())  # Return the numerical status to the operating system.
