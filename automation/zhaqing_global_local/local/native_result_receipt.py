#!/usr/bin/env python3
"""Record native solver completion against all requested steps; partial convergence never becomes training success.""" # Scope.
import argparse # CLI.
import hashlib # Input/output identities.
import json # Machine-readable receipt.
import re # Native log and step parsing.
from pathlib import Path # Source paths.

def sha(path: Path) -> str: # Stream large native files without loading them into memory.
    h = hashlib.sha256() # Digest accumulator.
    with path.open("rb") as stream: # Read existing native artifact.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk) # Bounded-memory hashing.
    return h.hexdigest() # Exact source/result identity.

def receipt(folder: Path, job: str, log_name: str, exit_code: int | None) -> dict: # Audit requested and completed solve path.
    inp, sta, log = folder / f"{job}.inp", folder / f"{job}.sta", folder / log_name # Native evidence paths.
    source, messages = inp.read_text(), log.read_text(errors="replace") if log.exists() else "" # Actual requested problem and solver output.
    expected_steps = len(re.findall(r"^\*STEP[,\n]", source, re.M)) # Requested native step count.
    completed = [] # Converged increments only.
    if sta.exists(): # Running/failed jobs may have no status file.
        for line in sta.read_text(errors="replace").splitlines(): # Parse real solver status rows.
            fields = line.split() # Status columns.
            if len(fields) == 7 and fields[0].isdigit() and fields[2].isdigit(): completed.append({"step": int(fields[0]), "increment": int(fields[1]), "attempt": int(fields[2]), "iterations": int(fields[3]), "total_time": float(fields[4]), "step_time": float(fields[5]), "increment_time": float(fields[6])}) # Exclude failed U attempts.
    last = completed[-1] if completed else None # Actual terminal converged state.
    terminal = bool(last and last["step"] == expected_steps and abs(last["step_time"] - 1.0) < 1e-6) # Builder emits unit-time load-path steps.
    complete = exit_code == 0 and "Job finished" in messages and "*ERROR" not in messages and terminal # All independent conditions required.
    status = "SOLVER_COMPLETE_RESEARCH_CASE" if complete else ("RUNNING_OR_UNCONFIRMED" if exit_code is None else "FAILED_OR_PARTIAL") # Never promote incomplete paths.
    result = {"status": status, "exit_code": exit_code, "requested_steps": expected_steps, "last_converged_increment": last, "converged_increment_count": len(completed), "full_requested_path_completed": complete, "input_sha256": sha(inp), "errors": re.findall(r".*\*ERROR.*", messages), "field_export_admitted": complete, "engineering_validation": "NOT_ESTABLISHED", "fatigue_life_validated": False, "admission_note": "Native solver completion is necessary; physical mesh/contact/force checks and complete field extraction remain required for dataset admission."} # Distinguish numerical completion and physical validation.
    if complete: result["native_result_hashes"] = {path.name: sha(path) for path in (folder / f"{job}.dat", folder / f"{job}.frd", sta) if path.exists()} # Hash expensive full results once complete.
    return result # Machine-readable audit.

def main() -> None: # Receipt CLI.
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("folder", type=Path); p.add_argument("--job", default="saddle"); p.add_argument("--log", default="native.log"); p.add_argument("--exit-code", type=int) # Require actual external process receipt.
    a = p.parse_args(); result = receipt(a.folder, a.job, a.log, a.exit_code) # Inspect native evidence.
    (a.folder / "native_completion.json").write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2)) # Persist verifiable completion status.

if __name__ == "__main__": main() # Execute only requested receipt generation.
