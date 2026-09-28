#!/usr/bin/env python3  # Provide the P0 fixed local compatibility module for the previously broken balanced-transfer parser.
from pathlib import Path  # Use explicit paths for the optional standalone smoke test.
import sys  # Read an optional verified input-deck path for parser validation.

SOURCE_NATIVE_COMMIT = "d743edeb6079bdf61c8cf176016f275bd2b60b95"  # Freeze the audited native source commit that exposed the original line-67 parser regression.


def split_verified_cload_rows(text: str) -> list[tuple[int, int, float]]:  # Parse verified comma-separated CLOAD rows without the unterminated-string regression.
    if "*CLOAD\n" not in text:  # Require a deterministic permanent nodal-load block before parsing.
        raise RuntimeError("verified CLOAD block not found")  # Stop before returning an incomplete load set.
    body = text.split("*CLOAD\n", 1)[1]  # Enter the first verified CLOAD block in source order.
    rows: list[tuple[int, int, float]] = []  # Accumulate explicit node, direction, and force records.
    for raw in body.splitlines():  # Scan the CLOAD body until the next solver keyword.
        line = raw.strip()  # Normalize surrounding whitespace only.
        if line.startswith("*"):  # Stop at the keyword following the CLOAD data.
            break  # Leave the verified load block without consuming result requests.
        if not line or line.startswith("**"):  # Ignore comments and empty records inside the load block.
            continue  # Advance to the next candidate load row.
        fields = [field.strip() for field in line.split(",")]  # Correct the former line-67 syntax error by using one explicit comma split.
        if len(fields) < 3:  # Reject malformed load records rather than silently dropping them.
            raise RuntimeError(f"malformed verified CLOAD row: {line}")  # Preserve fail-closed P0 behavior.
        rows.append((int(fields[0]), int(fields[1]), float(fields[2])))  # Preserve the exact verified nodal load record.
    return rows  # Return all parsed permanent CLOAD records for smoke tests and compatibility checks.


def smoke_test(path: Path) -> int:  # Validate the corrected parser against one immutable verified baseline deck.
    text = path.read_text(encoding="ascii")  # Read the baseline deck without text normalization.
    rows = split_verified_cload_rows(text)  # Exercise the corrected comma parser on real PR9 load data.
    if not rows:  # Require at least one permanent nodal load in the verified baseline.
        raise RuntimeError("corrected balanced-transfer parser found no CLOAD rows")  # Fail P0 smoke testing on an empty parse.
    print(f"P0 balanced-transfer parser PASS: {len(rows)} CLOAD rows; source={SOURCE_NATIVE_COMMIT}")  # Emit one compact machine-readable smoke-test trace.
    return 0  # Return native process success only after real baseline parsing passes.


if __name__ == "__main__":  # Execute the compatibility smoke test only when a baseline path is supplied directly.
    if len(sys.argv) != 2:  # Require exactly one verified baseline deck for standalone validation.
        raise SystemExit("usage: balanced_transfer_prestress.py VERIFIED_LC01_INP")  # Stop clearly when invocation is incomplete.
    raise SystemExit(smoke_test(Path(sys.argv[1])))  # Return the corrected parser smoke-test status to the workflow.
