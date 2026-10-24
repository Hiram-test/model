#!/usr/bin/env python3  # Restore native DAT evidence only after an exact original-input replay reproduces its recorded digest.
import argparse  # Parse explicit dataset, solver, and evidence-output locations.
import hashlib  # Verify exact input and native-response byte identities.
import json  # Read original immutable receipts and publish separate repair evidence.
import os  # Atomically install verified bytes and preserve completed snapshots.
import shutil  # Copy only original source inputs into isolated replay directories.
import subprocess  # Execute the same real CalculiX solver without changing its inputs.
import time  # Record actual replay duration and unique repair evidence identities.
import zipfile  # Preserve self-contained exact native replay evidence after verification.
from pathlib import Path  # Keep original, replay, and repaired file identities explicit.
ROOT = Path(__file__).resolve().parents[2]  # Resolve the shared repository from this independent utility.
def digest(path):  # Compute a present evidence file's exact immutable byte identity.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).is_file() else None  # Distinguish missing bytes from a zero-byte artifact.
def write_json(path, data):  # Publish one complete separate repair record atomically.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the intended independent repair namespace.
    temporary = path.with_name(path.name + ".tmp")  # Avoid exposing incomplete repair metadata.
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Preserve complete readable finite provenance.
    os.replace(temporary, path)  # Install the completed repair evidence without touching original solver receipts.
def collect_targets(manifest_path):  # Inspect only cases with completed immutable label receipts.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))  # Read one fixed dataset snapshot without changing it.
    targets, inspected, rejected = [], 0, []  # Track repair candidates and unrepairable original-input identity changes.
    for sample in manifest.get("samples", []):  # Examine only cases already published as completed by the runner.
        case_root = Path(sample["output_directory"])  # Resolve the case's original isolated numerical evidence.
        if not (case_root / "label_receipt.json").is_file():  # Exclude any still-running or incomplete case.
            continue  # Avoid racing a solver that may still be writing its response.
        for receipt_path in sorted(p for p in case_root.rglob("*.iteration.json") if ".rsync-tmp" not in p.parts):  # Check every original recorded iteration, including historical steps.
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))  # Read the original unmodified expected input and DAT hashes.
            stem = receipt_path.name.removesuffix(".iteration.json")  # Recover the exact original native solver basename.
            deck, dat = receipt_path.parent / f"{stem}.inp", receipt_path.parent / f"{stem}.dat"  # Resolve the receipt's real source and output.
            inspected += 1  # Count every checked original iteration, including already intact evidence.
            expected_dat, expected_deck = receipt["rawDatSha256"], receipt["deckSha256"]  # Preserve the immutable original numerical identities.
            if digest(dat) == expected_dat:  # Leave all intact native response artifacts unchanged.
                continue  # Avoid unnecessary repeated scientific computation.
            if digest(deck) != expected_deck:  # Never replay a changed input and present it as the original calculation.
                rejected.append({"case_id": sample["case_id"], "receipt": str(receipt_path), "reason": "ORIGINAL_INP_SHA_MISMATCH", "expected_inp_sha256": expected_deck, "actual_inp_sha256": digest(deck)})  # Record the unrecoverable source identity discrepancy separately.
                continue  # Preserve the damaged evidence for investigation without fabricating a replacement.
            targets.append({"case_id": sample["case_id"], "quality_status": sample["quality_status"], "receipt": str(receipt_path), "receipt_sha256": digest(receipt_path), "deck": str(deck), "dat": str(dat), "expected_dat_sha256": expected_dat, "expected_inp_sha256": expected_deck, "closed": receipt.get("status") == "CLOSED"})  # Bind every replay target to actual original evidence.
        for dat in (p for p in case_root.rglob("*.dat") if ".rsync-tmp" not in p.parts):  # Check for truncated native files that lack any original iteration identity.
            if dat.name != "canonical-response.dat" and dat.stat().st_size == 0 and not dat.with_suffix(".iteration.json").exists():  # Refuse to invent a digest for an unrecorded failed native output.
                rejected.append({"case_id": sample["case_id"], "dat": str(dat), "reason": "NO_ORIGINAL_INDEPENDENT_DAT_SHA"})  # Preserve the unrecoverable evidence gap explicitly without fabricating a response.
    return sorted(targets, key=lambda item: (not item["closed"], item["case_id"], item["dat"])), inspected, rejected  # Prioritize terminal closed steps needed by independent qualification.
def collect_matrix_targets(calculation):  # Recover native evidence from completed original matrix receipts, including direct-tangent seeds.
    claims = {}  # Index only original recorded native-response identities by exact original input hash.
    def visit(value, receipt_path, pointer):  # Recursively inspect original receipt fields while retaining their exact metadata location.
        if isinstance(value, dict):  # Read only named original evidence records.
            inp_sha = value.get("deckSha256", value.get("fineDeckSha256"))  # Support original iteration and complete-summary input-hash conventions.
            dat_sha = value.get("rawDatSha256")  # Require an original independent raw native-response digest.
            if isinstance(inp_sha, str) and isinstance(dat_sha, str):  # Exclude inferred, canonical, or incomplete response identities.
                claims.setdefault(inp_sha, []).append({"receipt": str(receipt_path), "receipt_sha256": digest(receipt_path), "pointer": pointer, "expected_dat_sha256": dat_sha, "closed": value.get("status") == "CLOSED"})  # Bind every available original native identity to its unmodified receipt.
            for key, child in value.items():  # Inspect original nested reaction-audit and tangent-seed records.
                visit(child, receipt_path, f"{pointer}/{key}")  # Preserve the metadata path used to recover this independent hash.
        elif isinstance(value, list):  # Preserve every original reaction or iteration record separately.
            for index, child in enumerate(value):  # Visit original sequence elements in their recorded order.
                visit(child, receipt_path, f"{pointer}/{index}")  # Retain the exact source-list position for audit.
    for receipt_path in sorted(p for p in calculation.rglob("*.json") if ".rsync-tmp" not in p.parts):  # Inspect original matrix output metadata after the matrix run has completed.
        if receipt_path.name == "summary.json" or receipt_path.name.endswith(".iteration.json") or receipt_path.name == "corotational-relinearization-request.json":  # Admit only original numerical receipts and the original tangent handoff.
            visit(json.loads(receipt_path.read_text(encoding="utf-8")), receipt_path, "")  # Extract original native identities without consulting derived audits.
    targets, inspected, rejected = [], 0, []  # Separate exact replay targets from missing independent source evidence.
    for deck in sorted(p for p in calculation.rglob("*.inp") if ".rsync-tmp" not in p.parts):  # Inspect every actual original native solver input, including nested tangent seeds.
        dat = deck.with_suffix(".dat")  # Resolve the matching original native output basename.
        if not dat.exists():  # Exclude inputs that were generated without a native run or response artifact.
            continue  # Avoid inventing a missing numerical output absent an original recorded identity.
        inspected += 1  # Count every original input/output pair encountered.
        inp_sha = digest(deck)  # Read the current original input identity independently.
        matched = claims.get(inp_sha, [])  # Require an original receipt naming exactly these unchanged input bytes.
        if not matched:  # Keep unavailable original digest evidence distinct from a reproducible truncation.
            if dat.stat().st_size == 0:  # Report empty native artifacts that cannot be restored under the exact-hash rule.
                rejected.append({"dat": str(dat), "deck": str(deck), "reason": "NO_ORIGINAL_INDEPENDENT_DAT_SHA", "actual_inp_sha256": inp_sha})  # Preserve the evidence gap without manufacturing a target digest.
            continue  # Leave every unhashed native output untouched.
        expected_hashes = {claim["expected_dat_sha256"] for claim in matched}  # Detect conflicting original native results for identical input bytes.
        if len(expected_hashes) != 1:  # Refuse to choose arbitrarily among inconsistent original evidence identities.
            rejected.append({"dat": str(dat), "deck": str(deck), "reason": "CONFLICTING_ORIGINAL_DAT_SHA", "expected_hashes": sorted(expected_hashes)})  # Publish the original provenance conflict separately.
            continue  # Preserve all original files until the conflict is resolved.
        expected = next(iter(expected_hashes))  # Recover the sole independently recorded original native identity.
        if digest(dat) == expected:  # Leave correctly preserved original outputs unchanged.
            continue  # Avoid unnecessary replays of intact numerical evidence.
        claim = sorted(matched, key=lambda item: not item["closed"])[0]  # Prefer a terminal closed-step receipt when several original records agree.
        relative_parts = deck.relative_to(calculation).parts  # Recover the original case directory from its established path.
        case_id = next((part for part in relative_parts if part.startswith("LC")), "LC01_G_DEAD")  # Preserve original case identity while supporting the completed LC01 parent.
        targets.append({**claim, "case_id": case_id, "quality_status": "ORIGINAL_MATRIX_STATUS_UNCHANGED", "deck": str(deck), "dat": str(dat), "expected_inp_sha256": inp_sha})  # Build an exact native replay target without altering qualification.
    return sorted(targets, key=lambda item: (not item["closed"], item["case_id"], item["dat"])), inspected, rejected  # Prioritize critical terminal evidence before historical source outputs.
def replay_target(target, ccx, replay_root):  # Recompute one unchanged native input and restore DAT only on exact recorded-hash equality.
    deck, original_dat = Path(target["deck"]), Path(target["dat"])  # Resolve the already validated original paths.
    replay = replay_root / target["case_id"] / f"{deck.stem}_{time.time_ns()}"  # Allocate a new replay namespace without reusing original output files.
    replay.mkdir(parents=True, exist_ok=False)  # Fail on a collision rather than overwrite prior evidence.
    original_hash = digest(original_dat)  # Record the actual damaged-byte identity immediately before replay.
    original_size = original_dat.stat().st_size if original_dat.exists() else None  # Distinguish a truncated artifact from absent evidence.
    if original_hash == target["expected_dat_sha256"]:  # Respect another exact repair that completed after target collection.
        return {**target, "status": "ALREADY_INTACT", "original_dat_sha256": original_hash, "original_size_bytes": original_size}  # Avoid duplicating a valid replacement.
    if original_dat.is_file():  # Preserve every damaged original byte before any successful restoration.
        shutil.copyfile(original_dat, replay / "damaged-original.dat.bin")  # Keep the original empty or corrupted evidence for audit.
    shutil.copyfile(deck, replay / deck.name)  # Copy exact original input bytes into the isolated native execution directory.
    if digest(replay / deck.name) != target["expected_inp_sha256"]:  # Recheck source identity after the physical copy.
        raise RuntimeError(f"Replay INP copy changed: {deck}")  # Stop before running an altered model.
    environment = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}  # Keep replay execution deterministic without changing model equations.
    started = time.perf_counter()  # Measure actual replay computation cost.
    process = subprocess.run([str(ccx), "-i", deck.stem], cwd=replay, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)  # Execute the same real native solver on the unchanged original input.
    elapsed = time.perf_counter() - started  # Record actual native execution wall time.
    (replay / "replay.stdout.log").write_text(process.stdout or "", encoding="utf-8")  # Preserve the exact solver diagnostic stream separately from original logs.
    replay_dat = replay / f"{deck.stem}.dat"  # Resolve the actual newly computed native response.
    replay_hash = digest(replay_dat)  # Compare real numerical bytes without reconstructing them from canonical output.
    matching = process.returncode == 0 and replay_hash == target["expected_dat_sha256"]  # Require both successful execution and exact original response reproduction.
    receipt = {**target, "status": "RESTORED_EXACT_REPLAY" if matching else "REPLAY_HASH_MISMATCH_NOT_RESTORED", "original_dat_sha256": original_hash, "original_size_bytes": original_size, "replay_dat_sha256": replay_hash, "replay_inp_sha256": digest(replay / deck.name), "solver": str(ccx), "solver_exit_code": process.returncode, "wall_time_s": elapsed, "replay_directory": str(replay), "original_receipt_modified": False, "original_quality_status_modified": False, "source": "REAL_CALCULIX_REPLAY_OF_IDENTICAL_INP"}  # Publish precise recovery semantics with no qualification upgrade.
    if matching:  # Restore only when real solver bytes exactly reproduce the original recorded identity.
        temporary = original_dat.with_name(original_dat.name + ".verified-replay.tmp")  # Prepare an atomic replacement beside the damaged artifact.
        with temporary.open("wb") as stream:  # Open only the new replacement path until all bytes are complete.
            stream.write(replay_dat.read_bytes())  # Copy real verified native bytes without decoding or reformatting.
            stream.flush()  # Flush Python's userspace buffer before installation.
            os.fsync(stream.fileno())  # Request persistence of the complete verified replacement bytes.
        if digest(temporary) != target["expected_dat_sha256"]:  # Recheck exact bytes before touching the original path.
            raise RuntimeError(f"Verified replacement bytes changed: {temporary}")  # Preserve the damaged original if the transfer is inconsistent.
        os.replace(temporary, original_dat)  # Replace only the damaged DAT after exact replay reproduction.
        receipt["restored_dat_sha256"] = digest(original_dat)  # Verify the installed native bytes at their original evidence path.
        if receipt["restored_dat_sha256"] != target["expected_dat_sha256"]:  # Detect filesystem inconsistency immediately after atomic replacement.
            raise RuntimeError(f"Restored DAT failed verification: {original_dat}")  # Refuse a false repair-success record.
    if digest(target["receipt"]) != target["receipt_sha256"]:  # Confirm no original iteration receipt changed during replay or restoration.
        raise RuntimeError(f"Original immutable receipt changed: {target['receipt']}")  # Preserve the evidence-boundary violation explicitly.
    write_json(replay / "repair_receipt.json", receipt)  # Save the complete independent repair receipt in the replay namespace.
    archive = replay.with_suffix(".zip")  # Create one self-contained exact-byte native replay snapshot.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:  # Preserve verified source, native output, and recovery metadata together.
        for path in sorted(replay.iterdir()):  # Enumerate only completed local replay artifacts.
            if path.is_file():  # Exclude directories and unrelated filesystem objects.
                bundle.write(path, path.name)  # Preserve each native file's actual bytes without interpretation.
    with zipfile.ZipFile(archive) as bundle:  # Reopen the finished snapshot for independent byte verification.
        if matching and hashlib.sha256(bundle.read(replay_dat.name)).hexdigest() != target["expected_dat_sha256"]:  # Ensure the snapshot retains the exact restored scientific response.
            raise RuntimeError(f"Replay archive verification failed: {archive}")  # Reject a corrupted persistent recovery snapshot.
    receipt["replay_archive"], receipt["replay_archive_sha256"] = str(archive), digest(archive)  # Bind the independent recovery snapshot in the aggregate repair record.
    print(json.dumps({key: receipt[key] for key in ("case_id", "status", "dat", "wall_time_s")}), flush=True)  # Stream compact repair progress without large native logs.
    return receipt  # Return precise restoration evidence for the separate aggregate report.
def archive_native_tree(source_root, archive_path):  # Preserve a complete numerical evidence tree with independently verified exact-byte snapshot contents.
    archive_path.parent.mkdir(parents=True, exist_ok=True)  # Create only the explicit final archive destination.
    if archive_path.exists():  # Preserve earlier complete evidence snapshots instead of overwriting them.
        raise RuntimeError(f"Archive already exists; choose a new path: {archive_path}")  # Require a distinct snapshot identity for later reruns.
    temporary = archive_path.with_name(archive_path.name + ".tmp")  # Build the complete snapshot before exposing it at its final path.
    inventory = []  # Record actual archived bytes independently from mutable loose-file metadata.
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as bundle:  # Preserve the complete source tree in one verified standalone artifact.
        for path in sorted(source_root.rglob("*")):  # Capture original numerical evidence in stable relative-path order.
            if ".rsync-tmp" in path.parts or not path.is_file() or path.name.endswith(".tmp") or path.name == "native-evidence.zip" or path.resolve() in (archive_path.resolve(), temporary.resolve()):  # Exclude incomplete writes, duplicate early per-case snapshots, and the archive itself while retaining their original integrity receipts.
                continue  # Keep every complete original artifact without recursively embedding the output.
            relative = path.relative_to(source_root).as_posix()  # Preserve original case and reaction subdirectory relationships.
            data = path.read_bytes()  # Capture each file once so its recorded hash describes exactly the archived bytes.
            bundle.writestr(relative, data)  # Persist the captured exact native bytes without decoding or normalization.
            inventory.append({"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})  # Bind every complete source artifact to its snapshot identity.
        bundle.writestr("_snapshot_manifest.json", json.dumps({"source_root": str(source_root), "file_count": len(inventory), "files": inventory}, indent=2) + "\n")  # Embed the complete standalone snapshot inventory.
    failures = []  # Accumulate archive integrity or original receipt identity mismatches without silently accepting them.
    with zipfile.ZipFile(temporary) as bundle:  # Independently reopen the completed archive to verify all captured bytes.
        names = set(bundle.namelist())  # Resolve original evidence relationships within the immutable snapshot only.
        for entry in inventory:  # Verify every compressed file independently of its source filesystem copy.
            if hashlib.sha256(bundle.read(entry["path"])).hexdigest() != entry["sha256"]:  # Require exact decompressed-byte agreement with the captured inventory.
                failures.append({"path": entry["path"], "reason": "ARCHIVE_BYTE_HASH_MISMATCH"})  # Preserve the specific corrupted snapshot member.
        for name in sorted(names):  # Check every original per-iteration numerical receipt inside the same immutable archive.
            if not name.endswith(".iteration.json"):  # Restrict exact native checks to recorded original iteration identities.
                continue  # Leave derived metadata outside this original native-evidence relation.
            receipt = json.loads(bundle.read(name))  # Read the archived original receipt rather than a mutable loose copy.
            stem = name.removesuffix(".iteration.json")  # Recover the corresponding archived native input and response basename.
            for suffix, field in ((".inp", "deckSha256"), (".dat", "rawDatSha256")):  # Verify both physical input and native output under original hash identities.
                candidate = stem + suffix  # Resolve the exact archived counterpart path.
                actual = hashlib.sha256(bundle.read(candidate)).hexdigest() if candidate in names else None  # Detect missing or changed native bytes within the snapshot.
                if actual != receipt[field]:  # Refuse a self-consistent inventory that still violates the original scientific receipt.
                    failures.append({"path": candidate, "reason": "ORIGINAL_ITERATION_SHA_MISMATCH", "expected_sha256": receipt[field], "actual_sha256": actual})  # Record exact evidence mismatch without altering the original receipt.
    if failures:  # Preserve an unqualified temporary snapshot for diagnosis without publishing it as complete evidence.
        write_json(archive_path.with_suffix(".failed-verification.json"), {"source_root": str(source_root), "failures": failures, "temporary_archive": str(temporary)})  # Expose every remaining original-identity failure explicitly.
        raise RuntimeError(f"Archive original-evidence verification failed: {len(failures)} mismatches")  # Require repair and a new complete snapshot before delivery.
    os.replace(temporary, archive_path)  # Publish the verified complete numerical evidence archive atomically.
    return {"path": str(archive_path), "sha256": digest(archive_path), "file_count": len(inventory), "source_byte_count": sum(item["size_bytes"] for item in inventory), "archive_byte_count": archive_path.stat().st_size, "original_iteration_hashes_verified": True, "all_snapshot_entry_hashes_verified": True}  # Return precise final archive identity and integrity evidence.
def main():  # Inspect a completed dataset snapshot and recover only reproducible damaged native DAT evidence.
    parser = argparse.ArgumentParser()  # Define the independent evidence-repair command line.
    sources = parser.add_mutually_exclusive_group(required=True)  # Require exactly one explicit original scientific evidence source.
    sources.add_argument("--manifest", type=Path)  # Accept an existing learning dataset whose original receipts remain authoritative.
    sources.add_argument("--calculation", type=Path)  # Accept a completed original case-matrix calculation tree with original hash receipts.
    parser.add_argument("--ccx", type=Path, default=ROOT.parent / "solver-runtime/ccx")  # Use the same real native solver as the primary run.
    parser.add_argument("--output", type=Path, default=ROOT / "build/zhaqing-md-20261024/native-evidence-repair")  # Keep all replay and repair artifacts separate from original solver evidence.
    parser.add_argument("--archive", type=Path)  # Optionally seal the complete qualified numerical source tree into a new verified standalone ZIP.
    args = parser.parse_args()  # Resolve requested source and destination paths.
    source = (args.manifest or args.calculation).resolve()  # Resolve the one caller-selected scientific evidence source.
    args.ccx, args.output = args.ccx.resolve(), args.output.resolve()  # Preserve absolute solver and independent repair locations.
    collector = collect_targets if args.manifest else collect_matrix_targets  # Select only the appropriate original-receipt discovery route.
    source_kind = "dataset_manifest" if args.manifest else "original_calculation_tree"  # Preserve the exact type of scientific evidence being restored.
    targets, inspected, rejected = collector(source)  # Identify mismatches without mutating original data or qualification.
    previous = json.loads((args.output / "repair-report.json").read_text(encoding="utf-8")) if (args.output / "repair-report.json").exists() else {}  # Preserve prior exact recovery records across later dataset snapshots.
    if previous and previous.get("source", previous.get("manifest")) != str(source):  # Prevent accidentally mixing recoveries from unrelated scientific datasets.
        raise RuntimeError("Repair output already belongs to another dataset manifest")  # Require a separate explicit evidence directory for a different dataset.
    records = list(previous.get("repairs", []))  # Append new exact recoveries without losing earlier real replay provenance.
    for target in targets:  # Execute priority-ordered real replays for all eligible damaged outputs.
        records.append(replay_target(target, args.ccx, args.output / "replays"))  # Restore only exact-hash matches and preserve all replay evidence.
        write_json(args.output / "repair-report.json", {"schema": "zhaqing-exact-native-replay-repair-v1", "source": str(source), "source_kind": source_kind, "manifest": str(source) if args.manifest else None, "inspected_iteration_count": inspected, "target_count": len(targets), "unrecoverable_input_mismatches": rejected, "repairs": records, "original_receipts_modified": False, "original_quality_status_modified": False})  # Checkpoint completed repairs without modifying source manifests.
    remaining, final_inspected, final_rejected = collector(source)  # Recheck the current published evidence after all replay restorations.
    report = {"schema": "zhaqing-exact-native-replay-repair-v1", "source": str(source), "source_kind": source_kind, "manifest": str(source) if args.manifest else None, "inspected_iteration_count": final_inspected, "target_count": len(targets), "unrecoverable_input_mismatches": final_rejected, "repairs": records, "remaining_targets": remaining, "original_receipts_modified": False, "original_quality_status_modified": False}  # Preserve remaining newly completed or irreproducible evidence discrepancies explicitly.
    if args.archive and not remaining and not final_rejected:  # Seal evidence only after all discovered original hash mismatches are resolved.
        archive_source = source.parent if args.manifest else source  # Preserve original routing for earlier already completed runs.
        if args.manifest:  # Discover the actual authoritative native root recorded by the new runner.
            payload = json.loads(source.read_text())  # Read the complete final producer manifest.
            roots = {Path(row["output_directory"]).parent.parent for row in payload["samples"]}  # Require one coherent isolated native dataset root.
            if len(roots) == 1 and "zhaqing-native-v3" in next(iter(roots)).parts:  # Apply isolated routing only to the explicit new execution namespace.
                archive_source = next(iter(roots))  # Read immutable solver-owned bytes directly.
                (archive_source / "dataset_manifest.json").write_bytes(source.read_bytes())  # Include the exact producer ledger in its native archive.
        report["native_archive"] = archive_native_tree(archive_source, args.archive.resolve())  # Preserve a complete standalone tree whose native receipts verify inside the archive.
    report["actual_native_replay_count"] = sum(record.get("status") in ("RESTORED_EXACT_REPLAY", "REPLAY_HASH_MISMATCH_NOT_RESTORED") for record in records)  # Count actual native execution attempts without counting already-intact skips.
    report["successful_exact_replay_count"] = sum(record.get("status") == "RESTORED_EXACT_REPLAY" for record in records)  # Record exact-reproduction restorations separately from attempts.
    write_json(args.output / "repair-report.json", report)  # Publish the final separate exact-byte recovery report.
    print(json.dumps({"inspected": final_inspected, "replayed": len(records), "remaining": len(remaining), "input_mismatches": len(final_rejected)}), flush=True)  # Return a compact inventory of actual recovery and outstanding evidence.
    return 0 if not remaining and not final_rejected else 2  # Require complete native-evidence integrity for process success.
if __name__ == "__main__":  # Keep imports free of repair or native execution side effects.
    raise SystemExit(main())  # Propagate actual original-evidence recovery status.
