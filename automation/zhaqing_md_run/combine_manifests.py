#!/usr/bin/env python3  # Merge genuine initial and feedback attempts without changing frozen holdout identities.
import argparse  # Read explicit scientific input and output paths.
import hashlib  # Preserve exact source and label identities.
import json  # Read existing manifests and write reproducible combined snapshots.
import math  # Sum actual numerical execution costs accurately.
from pathlib import Path  # Keep all filesystem operations explicit and local to the requested project.
def read(path):  # Read one immutable snapshot and its identity from the same captured bytes.
    payload = Path(path).read_bytes()  # Avoid races between parsing a live file and hashing a later version.
    return json.loads(payload.decode("utf-8")), hashlib.sha256(payload).hexdigest()  # Return parsed content bound to the exact original snapshot.
def digest(path):  # Identify a numerical evidence file without normalizing its bytes.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Preserve exact source and response spelling.
def write(path, value):  # Publish a deterministic complete JSON snapshot.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the explicitly requested destination directory.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Reject nonfinite provenance instead of silently corrupting evidence.
def main():  # Enforce complete actual attempts and unchanged initial holdouts before publishing a combined run.
    parser = argparse.ArgumentParser(description="Combine initial and feedback FEM attempts with an unchanged validation/test contract")  # Describe the concrete provenance-preserving operation.
    for name in ("initial", "feedback", "initial-design", "feedback-decision", "initial-accepted", "output", "combined-design"):  # Require every data source and output destination explicitly.
        parser.add_argument("--" + name, type=Path, required=True)  # Prevent implicit modification of either existing run.
    args = parser.parse_args()  # Resolve all requested scientific snapshots once.
    initial, initial_sha = read(args.initial)  # Capture the complete initial producer ledger including failed attempts.
    feedback, feedback_sha = read(args.feedback)  # Capture the complete actual feedback producer ledger.
    original_design, design_sha = read(args.initial_design)  # Read the precommitted initial bridge and split design.
    decision, decision_sha = read(args.feedback_decision)  # Read the evidence-driven selected feedback cases without selecting new ones.
    first_accepted, first_accepted_sha = read(args.initial_accepted)  # Freeze the exact initial labels used for the first training round.
    protected = {path.resolve() for path in (args.initial, args.feedback, args.initial_design, args.feedback_decision, args.initial_accepted)}  # Preserve every original source file independently from combined artifacts.
    if args.output.resolve() in protected or args.combined_design.resolve() in protected or args.output.resolve() == args.combined_design.resolve():  # Refuse source replacement or collision between the two new outputs.
        raise RuntimeError("combined outputs must be distinct from all original source snapshots")  # Protect the completed first round and live feedback provenance.
    for key in ("baseline", "equilibrium_state", "pipeline_module", "adapter_module", "nonlinear_module", "provenance", "domain", "factor_order"):  # Require identical mechanics, materials, solver, load interpretation, and allowable parameter domain.
        if initial[key] != feedback[key]:  # Reject incompatible numerical references rather than silently mixing them.
            raise RuntimeError("initial and feedback numerical provenance differs: " + key)  # Expose the exact model contract mismatch.
    added_design = decision["scenarios"]  # Preserve only the four cases actually selected by the completed first-round feedback.
    if decision.get("test_errors_used") is not False or any(row["split"] != "train" for row in added_design):  # Require explicit exclusion of frozen test errors from feedback and prohibit new holdout assignments.
        raise RuntimeError("feedback must declare no test-error use and add training cases only")  # Preserve independent comparison of the two learning rounds.
    expected = original_design["scenarios"] + added_design  # Retain every initial attempt and append exactly the selected training additions.
    expected_by_id = {row["case_id"]: row for row in expected}  # Build the unambiguous original scientific case identity map.
    rows = initial["samples"] + feedback["samples"]  # Preserve original numerical status and source paths for every actual attempt.
    actual_by_id = {row["case_id"]: row for row in rows}  # Detect duplicate or missing runtime attempts before publishing.
    if len(expected_by_id) != len(expected) or len(actual_by_id) != len(rows) or set(actual_by_id) != set(expected_by_id):  # Require all requested attempts exactly once, including failures.
        raise RuntimeError("combined attempts are incomplete, duplicated, or differ from the frozen initial-plus-feedback design")  # Refuse a misleading denominator produced during partial execution.
    for row in rows:  # Verify exact scientific identity and surviving source evidence for every completed attempt.
        expected_row = expected_by_id[row["case_id"]]  # Recover this case's precommitted split and load factors.
        if row["split"] != expected_row["split"] or row["factors"] != expected_row["factors"]:  # Prohibit relabeling a test case or replacing its actual loading.
            raise RuntimeError("case split or factors changed: " + row["case_id"])  # Preserve the original train/validation/test assignment.
        if digest(row["summary"]) != row["summary_sha256"]:  # Require the original producer's final receipt bytes to remain unchanged.
            raise RuntimeError("source numerical summary identity changed: " + row["case_id"])  # Reject post-hoc qualification edits.
        if row.get("quality_status") == "VALID_CONVERGED" and digest(row["canonical_dat"]) != row["canonical_dat_sha256"]:  # Validate every actual available numerical label before independent physics auditing.
            raise RuntimeError("source canonical label identity changed: " + row["case_id"])  # Prevent silent replacement of a reference solution.
    holdouts = []  # Preserve the precise first-round validation and test population available for the second-round comparison.
    for row in first_accepted["samples"]:  # Read only accepted first-round references without modifying their snapshot.
        if row["split"] not in ("validation", "test"):  # Restrict immutable comparison checks to the independent evaluation roles.
            continue  # Allow new training data to be added without treating it as a changed holdout.
        current = actual_by_id[row["case_id"]]  # Recover the same original runtime attempt from the combined source ledger.
        if current["split"] != row["split"] or current["canonical_dat_sha256"] != row["canonical_dat_sha256"] or current["summary_sha256"] != row["summary_sha256"]:  # Require identical case identity, numerical truth, and qualification evidence across rounds.
            raise RuntimeError("first-round holdout identity changed: " + row["case_id"])  # Stop before computing an invalid before/after metric.
        holdouts.append({"case_id": row["case_id"], "split": row["split"], "canonical_dat_sha256": row["canonical_dat_sha256"], "summary_sha256": row["summary_sha256"]})  # Publish explicit comparison invariants for the second training stage.
    expected_counts = {split: sum(row["split"] == split for row in expected) for split in ("train", "validation", "test")}  # Preserve the full intended denominator including unsuccessful reference solves.
    sources = {"initial_manifest": {"path": str(args.initial.resolve()), "sha256": initial_sha}, "feedback_manifest": {"path": str(args.feedback.resolve()), "sha256": feedback_sha}, "initial_design": {"path": str(args.initial_design.resolve()), "sha256": design_sha}, "feedback_decision": {"path": str(args.feedback_decision.resolve()), "sha256": decision_sha}, "initial_accepted_manifest": {"path": str(args.initial_accepted.resolve()), "sha256": first_accepted_sha}}  # Record the complete actual lineage of the merged learning dataset.
    design = {"schema": "zhaqing-md-combined-scenario-design-v1", "scenarios": expected, "expected_split_counts": expected_counts, "source_snapshots": sources, "holdout_cases_unchanged": holdouts, "test_errors_used_for_feedback": False}  # Preserve initial frozen cases and genuine selected additions as a separately auditable design.
    combined = dict(initial)  # Retain all unchanged model, domain, solver, and physical interpretation metadata.
    combined.update({"samples": rows, "valid_count": sum(row["quality_status"] == "VALID_CONVERGED" for row in rows), "failed_count": sum(row["quality_status"] != "VALID_CONVERGED" for row in rows), "total_wall_time_s": math.fsum(float(row["wall_time_s"]) for row in rows), "source_snapshots": sources, "expected_split_counts": expected_counts, "holdout_cases_unchanged": holdouts, "round_count": 2})  # Count every actual computation once while preserving original failure status.
    write(args.combined_design, design)  # Publish the full unchanged-plus-feedback scientific design first.
    write(args.output, combined)  # Publish the complete combined producer ledger before independent physics filtering.
    if digest(args.initial_accepted) != first_accepted_sha:  # Prove that combining data did not change the completed first-round snapshot.
        raise RuntimeError("initial accepted snapshot changed during combination")  # Fail explicitly rather than concealing broken comparison provenance.
    print(json.dumps({"status": "COMBINED_FOR_INDEPENDENT_AUDIT", "attempt_count": len(rows), "valid_count": combined["valid_count"], "failed_count": combined["failed_count"], "expected_split_counts": expected_counts, "unchanged_holdout_count": len(holdouts), "output": str(args.output), "combined_design": str(args.combined_design)}, ensure_ascii=False))  # Report actual scope and pending independent qualification.
    return 0  # Confirm only that source-preserving combination succeeded.
if __name__ == "__main__":  # Execute only on an explicit command invocation.
    raise SystemExit(main())  # Return the actual combination outcome to the workflow.
