from __future__ import annotations  # Enable stable modern type annotations.
import json  # Write deterministic target-free calculation receipts.
import os  # Record the exact GitHub source revision.
from pathlib import Path  # Resolve the isolated output directory safely.
import solve_modal_branch_clean as core  # Reuse the full inverse, assembly, eigen, and branch-metric implementation.

OUT = Path(__file__).resolve().parent / "modal_results_branch_clean_v2"  # Isolate the corrected branch-ranking results from every prior run.
OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated output directory idempotently.
core.OUT = OUT  # Redirect the shared output writer to the corrected result directory.
core.base.OUT = OUT  # Redirect the reused base solver output to the corrected result directory.
core.v2.OUT = OUT  # Redirect the reused mass-consistent assembly output to the corrected result directory.
core.v4.OUT = OUT  # Redirect the reused drawing-corrected output to the corrected result directory.


def select_branches(raw: list[dict]) -> dict[str, dict]:  # Select physical branches from one immutable candidate set per family and parity.
    selected: dict[str, dict] = {}  # Initialize the complete fourteen-family result table.
    side_used: set[int] = set()  # Track only numerical modes already assigned to side-span families.
    side_definitions = [("SIDE1", "south717_fraction"), ("SIDE2", "north_fraction"), ("SIDE3", "south503_fraction")]  # Declare the three physical side-span labels.
    for label, fraction_key in side_definitions:  # Traverse every predeclared side-span family.
        candidates = [record for record in raw if record["mode"] not in side_used and record[fraction_key] >= core.SIDE_FRACTION_MIN and record["floor_participation"] >= core.FLOOR_PARTICIPATION_MIN and record["localization"] <= core.LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Apply only span, participation, localization, and frequency-band conditions.
        if candidates:  # Test whether a physical side-span mode exists.
            choice = min(candidates, key=lambda record: (record["frequency_hz"], -record[fraction_key]))  # Select the lowest global branch localized in the declared span.
            selected[label] = {**choice, "selection_rule": f"lowest global branch with {fraction_key}>={core.SIDE_FRACTION_MIN:.2f}"}  # Store the selected side-span branch and its target-free rule.
            side_used.add(int(choice["mode"]))  # Prevent the same numerical mode from receiving another side-span label.
        else:  # Handle an absent side-span candidate honestly.
            selected[label] = {"status": "unidentified", "selection_rule": f"no global branch with {fraction_key}>={core.SIDE_FRACTION_MIN:.2f}"}  # Preserve an explicit unidentified state.
    main_candidates = [record for record in raw if record["mode"] not in side_used and record["main_fraction"] >= core.MAIN_FRACTION_MIN and record["floor_gantry_acoustic_coherence"] >= core.ACOUSTIC_COHERENCE_MIN and record["floor_participation"] >= core.FLOOR_PARTICIPATION_MIN and record["localization"] <= core.LOCALIZATION_MAX and record["frequency_hz"] <= 0.60]  # Freeze the global acoustic main-span candidate set before assigning any rank.
    branch_groups = {("L", "common", "S"): [("LS1", 1), ("LS2", 2)], ("L", "common", "A"): [("LA1", 1), ("LA2", 2)], ("V", "common", "S"): [("VS1", 1), ("VS2", 2)], ("V", "common", "A"): [("VA1", 1), ("VA2", 2)], ("T", "differential", "S"): [("TS1", 1), ("TS2", 2)], ("T", "differential", "A"): [("TA1", 1)]}  # Define each label only by global family, two-catwalk relation, parity, and ascending branch rank.
    for (family, relation, parity_label), labels in branch_groups.items():  # Traverse every disjoint physical branch group.
        candidates = sorted([record for record in main_candidates if record["family"] == family and record["catwalk_relation"] == relation and record["parity_label"] == parity_label], key=lambda record: record["frequency_hz"])  # Sort the immutable physical candidate set once by computed frequency.
        for label, rank in labels:  # Assign every requested rank inside the current disjoint group.
            if len(candidates) >= rank:  # Test whether the requested physical branch rank exists.
                choice = candidates[rank - 1]  # Select the requested branch without removing lower ranks from the candidate list.
                selected[label] = {**choice, "selection_rule": f"rank {rank} by frequency among acoustic main-span {family}-{relation}-{parity_label} branches; harmonic order is descriptive only"}  # Store the selected branch and its target-free rule.
            else:  # Handle a missing branch rank honestly.
                selected[label] = {"status": "unidentified", "selection_rule": f"fewer than {rank} acoustic main-span {family}-{relation}-{parity_label} branches"}  # Preserve an explicit unidentified state.
    return selected  # Return the complete corrected fourteen-family assignment.


def main() -> int:  # Execute the complete inverse-static, matrix, eigen, and corrected branch-ranking recalculation.
    core.v4.apply_drawing_corrections()  # Apply only independently documented drawing corrections before assembly.
    model = core.base.load_mct()  # Parse and hash-check the sole MCT geometry, topology, support, and load source.
    floor_nodes, floor_elements = core.base.chain(model, [int(element_id) for element_id in model["groups"]["ZJG04_bcs"]["elems"]])  # Recover the complete formed lower-chain topology.
    top_nodes, top_elements = core.base.chain(model, [int(element_id) for element_id in model["groups"]["门架索"]["elems"]])  # Recover the complete formed gantry-rope topology.
    static = core.previous.recover_static_state(model)  # Recompute the unique MCT-geometry inverse axial-force state from scratch.
    if not bool(static["success"]):  # Reject any inverse-solver failure before modal assembly.
        raise RuntimeError(str(static["message"]))  # Report the exact inverse-solver failure.
    if int(static["nullity"]) != 0:  # Require a unique aggregate force field.
        raise RuntimeError(f"Inverse equilibrium nullity is {static['nullity']}")  # Reject an unresolved self-stress branch.
    if float(static["min_cable_force_kN"]) <= 0.0:  # Require every cable member to remain in tension.
        raise RuntimeError(f"Minimum recovered cable force is {static['min_cable_force_kN']:.6f} kN")  # Reject cable compression before geometric-stiffness assembly.
    if float(static["max_abs_force_error_percent"]) > 0.5:  # Preserve the declared elementwise initial-force agreement threshold.
        raise RuntimeError(f"Maximum MCT initial-force mismatch is {static['max_abs_force_error_percent']:.6f}%")  # Elementwise |Δ| is a comparison diagnostic, not the 1e-8 residual gate.
    system = core.v2.assemble_v2(model, static, floor_nodes, floor_elements, top_nodes, top_elements)  # Reassemble the complete drawing-corrected rope, portal, passage, and mass matrices.
    frequencies, vectors, residuals, matrix_checks = core.base.solve_eigen(system)  # Recompute and verify the low generalized eigenpairs.
    raw, shapes = core.modal_records(model, system, floor_nodes, top_nodes, frequencies, vectors, residuals)  # Recompute every target-free global branch metric including floor-gantry acoustic coherence.
    selected = select_branches(raw)  # Assign the fourteen physical labels without fixed harmonic-order conditions.
    identified = {label: float(record["frequency_hz"]) for label, record in selected.items() if "frequency_hz" in record}  # Build the concise identified-frequency map.
    frozen = {"kind": "mct_inverse_prestress_modal_branch_clean_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False, "mct_initial_force_used_in_inverse": False, "mct_initial_force_loaded_after_inverse_for_verification": True, "inverse_force_verified": False, "not_recovered_iniforce": True, "frequency_reproduced": False, "not_attach_ta1": True, "not_ccx_job_finished": True, "classification_uses_fixed_harmonic_order": False, "classification_rule": "global L/V/T field plus common/differential catwalk relation, midpoint parity, floor-gantry acoustic coherence, span localization, then ascending branch rank; sine order and zero crossings are descriptors only", "thresholds": {"acoustic_coherence_min": core.ACOUSTIC_COHERENCE_MIN, "main_fraction_min": core.MAIN_FRACTION_MIN, "side_fraction_min": core.SIDE_FRACTION_MIN, "localization_max": core.LOCALIZATION_MAX, "floor_participation_min": core.FLOOR_PARTICIPATION_MIN}, "inverse_static": {key: value for key, value in static.items() if key != "force_kN"}, "matrix_checks": matrix_checks, "mass_audit": system["mass_audit_v2"], "first_40_frequencies_hz": [float(value) for value in frequencies[:40]], "raw_modes": raw, "classified_14": selected}  # Assemble the immutable target-free recalculation record.
    frozen_path = OUT / "frozen_results_branch_clean_v2.json"  # Define the immutable target-free result path.
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Freeze the complete recalculation before any external comparison.
    frozen_sha256 = core.base.sha(frozen_path)  # Compute the immutable result digest.
    summary = {"kind": "mct_inverse_prestress_modal_branch_clean_summary_v2", "git_sha": os.environ.get("GITHUB_SHA", "local"), "source_mct_sha256": model["source"]["sha256"], "frozen_sha256": frozen_sha256, "inverse_static": frozen["inverse_static"], "matrix_checks": matrix_checks, "identified_count": int(len(identified)), "identified_frequencies_hz": identified, "classification_uses_fixed_harmonic_order": False, "target_frequency_used_in_solve": False, "target_frequency_used_in_classification": False, "inverse_force_verified": False, "not_recovered_iniforce": True, "frequency_reproduced": False, "not_attach_ta1": True, "not_ccx_job_finished": True, "absolute_recovered_residual_limit": 1.0e-8, "absolute_stored_residual_limit": 1.0e-4}  # Build the concise target-free calculation receipt.
    core.write_outputs(raw, selected, shapes, summary)  # Write the raw branch table, corrected fourteen-family table, shape fields, and summary.
    core.base.dump(OUT / "unstressed_lengths.json", system["recovered"])  # Preserve every explicit rope force and recovered unstressed length.
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{core.base.sha(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file()) + "\n", encoding="utf-8")  # Hash every generated result file.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))  # Print the complete corrected recalculation summary into the workflow log.
    return 0  # Report successful recalculation completion.


if __name__ == "__main__":  # Execute only when invoked as the main calculation program.
    raise SystemExit(main())  # Return the numerical status to the operating system.
