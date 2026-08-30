from __future__ import annotations  # Keep annotations deterministic.

import hashlib  # Bind exact file identities.
import json  # Publish a machine-readable receipt.
import re  # Parse CalculiX DAT frequency rows.
from pathlib import Path  # Resolve committed artifacts.

BASE = Path(__file__).resolve().parent.parent  # Anchor the C0-C5 project.
DAT = BASE / "solver" / "runs" / "C3UBFT14_PARSER_SAFE_667c5047" / "job.dat"  # Frozen C3 DAT table.
CSV = BASE / "artifacts" / "C3-UB-FT14-PARSER-SAFE_mode_classification_ff1d792e8af0d31f.csv"  # Frozen classification.
RECEIPT = BASE / "artifacts" / "C3_UB_FT14_PARSER_SAFE_RESULT.md"  # Frozen human receipt.
EXPECTED_DAT_SHA256 = "329a017f0356504ea5a360488ae0f87adfa39dae507119bdb9e622fb139c1208"  # Receipt identity.
EXPECTED_CSV_SHA256 = "ff1d792e8af0d31fd20d46fed8468c1ac0dde066e7a8406ff4af72275ab76d1d"  # Receipt identity.
EXPECTED_INP_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"  # Missing 27 MB deck identity.
EXPECTED_HZ = [  # Fourteen frozen roots from the DAT and receipt.
    0.03677346,
    0.07144416,
    0.07267216,
    0.07356089,
    0.1012149,
    0.1028555,
    0.1101283,
    0.1161726,
    0.1248024,
    0.1456783,
    0.1464436,
    0.1465091,
    0.1465538,
    0.1491063,
]
ROW = re.compile(r"^\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$")  # DAT eigenvalue table row.


def sha256_file(path: Path) -> str:  # Stream one exact file identity.
    digest = hashlib.sha256()  # Fresh digest.
    with path.open("rb") as handle:  # Read without loading twice.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # One MiB blocks.
            digest.update(block)  # Fold every byte.
    return digest.hexdigest()  # Lowercase hex.


def parse_dat(path: Path) -> list[float]:  # Extract ordered cycle frequencies.
    modes: list[float] = []  # Preserve DAT order.
    for raw in path.read_text(encoding="ascii", errors="replace").splitlines():  # Traverse exact rows.
        match = ROW.match(raw)  # Admit only table rows.
        if not match:  # Skip headers and participation blocks.
            continue  # Next line.
        index = int(match.group(1))  # Mode number.
        if index != len(modes) + 1:  # Require contiguous numbering.
            continue  # Ignore later tables.
        modes.append(float(match.group(4)))  # Cycles/time column.
        if len(modes) == 14:  # Stop after the frozen request.
            break  # Fourteen roots only.
    return modes  # Ordered frequencies.


def parse_csv(path: Path) -> list[float]:  # Extract classification frequencies.
    lines = path.read_text(encoding="utf-8").splitlines()  # Include header.
    values: list[float] = []  # Preserve CSV order.
    for line in lines[1:]:  # Skip header.
        if not line.strip():  # Ignore blanks.
            continue  # Next row.
        values.append(float(line.split(",", 2)[1]))  # frequency_hz column.
    return values  # Ordered classification frequencies.


def main() -> None:  # Verify frozen C3 identities; do not claim a live solve.
    missing_inp = not any((BASE / "solver").rglob("C3-UB-FT14-PARSER-SAFE_m14_667c5047*.inp"))  # Look for the 27 MB deck.
    dat_sha = sha256_file(DAT)  # Hash committed DAT.
    csv_sha = sha256_file(CSV)  # Hash committed CSV.
    dat_hz = parse_dat(DAT)  # Parse DAT roots.
    csv_hz = parse_csv(CSV)  # Parse classification roots.
    assert dat_sha == EXPECTED_DAT_SHA256, dat_sha  # Reject DAT drift.
    assert csv_sha == EXPECTED_CSV_SHA256, csv_sha  # Reject CSV drift.
    assert RECEIPT.is_file(), str(RECEIPT)  # Require the human receipt.
    assert len(dat_hz) == 14 and len(csv_hz) == 14, (len(dat_hz), len(csv_hz))  # Fourteen roots.
    for index, expected in enumerate(EXPECTED_HZ, start=1):  # Compare each frozen root.
        assert abs(dat_hz[index - 1] - expected) <= 5.0e-8, (index, dat_hz[index - 1], expected)  # DAT vs receipt.
        assert abs(csv_hz[index - 1] - expected) <= 5.0e-8, (index, csv_hz[index - 1], expected)  # CSV vs receipt.
    report = {  # Publish exact runner scope.
        "schema": "catwalk.c3-ub-ft14.actions-verify.v1",
        "status": "FROZEN_DAT_VERIFIED_LIVE_SOLVE_BLOCKED" if missing_inp else "FROZEN_DAT_VERIFIED",
        "live_solve": False,
        "claims": {"frequency_reproduced": False, "equilibrium_validated": False, "production": False},
        "dat": {"path": str(DAT.relative_to(BASE)), "sha256": dat_sha, "hz": dat_hz},
        "csv": {"path": str(CSV.relative_to(BASE)), "sha256": csv_sha, "hz": csv_hz},
        "missing_for_live_solve": {
            "parser_safe_inp_sha256": EXPECTED_INP_SHA256,
            "parent_inp_sha256": "b2a8f01c9864c0f72f5fe2e0aa3cce45e78a9267a560d8ce10dcfc19aa97048e",
            "c0sm_source_tree": True,
            "patched_ccx_sha256": "b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e",
        },
        "physical_negative_result": {
            "m3_is_differential_vertical": True,
            "m4_is_lateral_not_ta1": True,
            "ta1_0_0996_absent": True,
        },
    }  # Close the exact evidence object.
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))  # Emit the runner receipt.
    if missing_inp:  # Keep the job green only for verification; surface the blocker clearly.
        print("LIVE_SOLVE_BLOCKED: 27MB C3-UB-FT14-PARSER-SAFE inp is not in git")  # Explicit next action.


if __name__ == "__main__":  # Execute only as the Actions verifier.
    main()  # Verify frozen identities.
