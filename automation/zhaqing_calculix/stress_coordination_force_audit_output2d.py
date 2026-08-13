#!/usr/bin/env python3  # Apply only the P4 OUTPUT=2D original-node force-audit correction on top of the already exercised final force-audit adapter.
import importlib.util  # Load the existing audited final adapter from the same workflow provenance directory without executing its guarded main block.
from pathlib import Path  # Resolve the sibling legacy adapter and audit FRD result paths deterministically.


def load_sibling(path: Path):  # Load one sibling Python source module without changing the prior P0-P3 implementation.
    spec = importlib.util.spec_from_file_location("zhaqing_force_audit_legacy", path)  # Build an explicit module specification for the already exercised force-audit adapter.
    if spec is None or spec.loader is None:  # Refuse to continue when Python cannot construct a loader for the frozen sibling source.
        raise RuntimeError(f"cannot load legacy force-audit adapter from {path}")  # Stop before monkey-patching an undefined P4 implementation.
    module = importlib.util.module_from_spec(spec)  # Create the isolated module object exposing the existing P4 functions and guarded main entry point.
    spec.loader.exec_module(module)  # Execute definitions only because the imported adapter is not loaded under the __main__ name.
    return module  # Return the fully loaded prior adapter for minimal P4 measurement correction.


def parse_frd_forc(path: Path) -> dict[int, tuple[float, float, float]]:  # Parse the final CalculiX legacy-FRD FORC dataset emitted under NODE FILE OUTPUT=2D.
    datasets: list[dict[int, tuple[float, float, float]]] = []  # Preserve each chronological FORC result state so the final static state can be selected deterministically.
    active: dict[int, tuple[float, float, float]] | None = None  # Track the currently parsed FORC result block while scanning fixed-width FRD records.
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():  # Scan every FRD record exactly once without numeric reformatting.
        if raw.startswith(" -4  FORC"):  # Detect the start of one nodal-force result dataset in the CalculiX legacy FRD format.
            active = {}  # Initialize a fresh force map for this result state.
            continue  # Advance to the component descriptors and fixed-width nodal records.
        if active is not None and raw.startswith(" -1"):  # Parse one fixed-width nodal force record only while a FORC dataset is active.
            if len(raw) < 49:  # Require the standard ten-character node field plus three twelve-character floating-point fields.
                raise RuntimeError(f"malformed FORC FRD record: {raw}")  # Stop before silently dropping a force component from the P4 audit.
            node = int(raw[3:13])  # Recover the original or helper node id from the fixed-width node field.
            values = (float(raw[13:25]), float(raw[25:37]), float(raw[37:49]))  # Recover F1,F2,F3 from the three fixed-width scientific-notation fields.
            active[node] = values  # Preserve the complete nodal force vector for this FRD result state.
            continue  # Advance to the next fixed-width nodal force record.
        if active is not None and raw.startswith(" -3"):  # Detect the end of the current result dataset after all nodal force records have been read.
            datasets.append(active)  # Preserve this complete FORC state for deterministic final-state selection.
            active = None  # Leave FORC parsing mode before scanning later datasets.
    if not datasets:  # Require at least one complete FORC result dataset from the audit-only solve.
        raise RuntimeError(f"no FORC dataset found in {path}")  # Stop before falling back to the known contaminated DAT RF diagnostic.
    return datasets[-1]  # Return the final static FORC state generated under OUTPUT=2D.


legacy = load_sibling(Path(__file__).with_name("stress_coordination_force_audit_adapter.py"))  # Load the exact prior P4 adapter copied beside this thin correction layer by the workflow.
legacy_load_module = legacy.load_module  # Preserve the prior adapter's module loader so only the audit DAT parser can be intercepted.
legacy_build_force_audit_deck = legacy.build_force_audit_deck  # Preserve the already exercised explicit-load audit deck constructor before changing its output request only.
legacy_evaluate_force_audit = legacy.evaluate_force_audit  # Preserve the already exercised 0.1-percent pure-reaction Gate calculation before changing its force-record source only.


def patched_load_module(name: str, path: Path):  # Intercept only the base module's audit-result parser while preserving every P0-P3 function implementation.
    module = legacy_load_module(name, path)  # Load the exact requested prior calculation module through the existing audited loader.
    if name == "zhaqing_stress_coordination_base":  # Patch only the reconstructed base module used by the prior final adapter.
        original_parse_dat_nodes = module.parse_dat_nodes  # Preserve the base DAT parser for the main P3 stress solve and audit displacement diagnostics.
        def patched_parse_dat_nodes(result_path: Path):  # Route only ZQ_FORCE_AUDIT nodal force recovery to OUTPUT=2D FRD while leaving all other result parsing unchanged.
            displacements, reactions = original_parse_dat_nodes(result_path)  # Parse the existing DAT output first so audit displacements remain available exactly as before.
            if result_path.name == "ZQ_FORCE_AUDIT.dat":  # Detect only the independent P4 explicit-load audit subcase.
                return displacements, parse_frd_forc(result_path.with_suffix(".frd"))  # Replace contaminated expanded DAT RF with the final original-node OUTPUT=2D FRD FORC map.
            return displacements, reactions  # Preserve the original parser output for the primary P3 stress calculation and every other result path.
        module.parse_dat_nodes = patched_parse_dat_nodes  # Install the narrow audit-only parser override on this loaded base module instance.
    return module  # Return the loaded module with no other behavioral changes.


def patched_build_force_audit_deck(fine_deck: str):  # Change only the independent audit subcase node-file output representation from expanded 3D to original-node 2D.
    audit_deck, audit_loads, audit_mass = legacy_build_force_audit_deck(fine_deck)  # Build the exact same explicit-load P4 audit model already exercised in the prior real Actions run.
    old_request = "*NODE FILE, FREQUENCY=1\nU, RF\n"  # Match the prior default expanded-node FRD output request exactly.
    new_request = "*NODE FILE, OUTPUT=2D, FREQUENCY=1\nU, RF\n"  # Request CalculiX mapping of expanded beam/shell nodal results back onto the original model nodes for the audit only.
    if old_request not in audit_deck:  # Require the exact prior audit output request before applying the P4 measurement correction.
        raise RuntimeError("legacy force-audit NODE FILE request not found")  # Stop rather than modifying an unknown audit solver deck.
    return audit_deck.replace(old_request, new_request, 1), audit_loads, audit_mass  # Return the unchanged audit topology and loads with only OUTPUT=2D force recording enabled.


def patched_evaluate_force_audit(condensed, audit_deck, audit_loads, audit_mass_by_group, audit_exit, audit_log, audit_reactions):  # Reuse the unchanged 0.1-percent Gate calculation with the corrected original-node force-record source.
    receipt = legacy_evaluate_force_audit(condensed, audit_deck, audit_loads, audit_mass_by_group, audit_exit, audit_log, audit_reactions)  # Apply the exact prior pure-reaction subtraction and force-balance threshold to the OUTPUT=2D force map.
    receipt["forceRecordSource"] = "FRD FORC from NODE FILE OUTPUT=2D"  # Record the corrected original-node force source explicitly in the final machine-readable audit receipt.
    receipt["forceRecordCount"] = len(audit_reactions)  # Record the number of final FORC node records used by the P4 audit for independent review.
    receipt["method"] = "same explicit-load retained-structure audit and unchanged 0.1% Gate; only force recovery changed from expanded DAT RF to original-node FRD FORC via NODE FILE OUTPUT=2D"  # State the intentionally narrow P4 correction without changing the repair-plan acceptance threshold.
    return receipt  # Return the corrected-source force-audit receipt to the existing final adapter main function.


legacy.load_module = patched_load_module  # Route only the audit subcase force parsing through original-node OUTPUT=2D FRD records.
legacy.build_force_audit_deck = patched_build_force_audit_deck  # Route only the audit node-file output representation through OUTPUT=2D.
legacy.evaluate_force_audit = patched_evaluate_force_audit  # Preserve the prior force-balance mathematics while annotating the corrected force source.
raise SystemExit(legacy.main())  # Execute the exact prior final P0-P4 adapter with only the three narrow P4 audit hooks above replaced.
