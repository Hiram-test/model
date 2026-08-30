from __future__ import annotations  # Keep annotations deterministic on the supported Python runtime.

import hashlib  # Bind the immutable parent and corrected deck bytes.
import json  # Publish a machine-readable interface-fix record.
import re  # Select only the three-constant UCAB3 section payloads.
from pathlib import Path  # Resolve project artifacts independently of the invoking shell.

BASE = Path(__file__).resolve().parent.parent  # Anchor the C0-C5 reproduction project.
PARENT = BASE / "solver" / "c3_ub_frozen_tangent_diag" / "C3-UB-FT_DIAGNOSTIC_m06_b2a8f01c9864c0f7.inp"  # Select the exact original C3 frozen-tangent deck.
OUTPUT_DIR = BASE / "solver" / "c3_ub_frozen_tangent_diag"  # Keep the corrected deck beside its exact parent.
ARTIFACTS = BASE / "artifacts"  # Store immutable build evidence beside prior gates.
EXPECTED_PARENT_SHA256 = "b2a8f01c9864c0f72f5fe2e0aa3cce45e78a9267a560d8ce10dcfc19aa97048e"  # Freeze exact parent bytes.
EXPECTED_UCAB3_COUNT = 73692  # Require every original prestressed axial member exactly once.
OLD_FREQUENCY_BLOCK = "*FREQUENCY\n6\n"  # Select the unique six-root request.
NEW_FREQUENCY_BLOCK = "*FREQUENCY\n14\n"  # Request exactly the first fourteen fixed-order roots required for the strict comparison.
OLD_SCOPE = "** C3-UB-FT frozen-tangent modal-only diagnostic; no static correction, no equilibrium claim, target data not loaded."  # Select the unique parent scope annotation.
NEW_SCOPE = "** C3-UB-FT14-PARSER-SAFE frozen-tangent modal diagnostic; UCAB3 mu numeric tokens shortened from .15e to .12e for CalculiX f20.0 parsing, physical values unchanged within 5e-13 relative; fourteen roots; target data not loaded."  # Disclose the parser-only correction.
SECTION_PATTERN = re.compile(r"(?m)^(\*USER SECTION, ELSET=CAB\d+, MATERIAL=M(?:BEARING|GANTRY|DOWNPULL), CONSTANTS=3\n)([-+0-9.eE]+), ([-+0-9.eE]+), ([-+0-9.eE]+)$")  # Capture each exact UCAB3 property block.


class BuildError(RuntimeError):  # Represent one stable fail-closed transformation violation.
    pass  # Keep the semantic exception behavior-free.


def require(condition: bool, code: str, detail: str) -> None:  # Enforce one exact build contract.
    if not condition:  # Reject every condition not positively established.
        raise BuildError(f"{code}: {detail}")  # Surface a stable bounded diagnostic.


def sha256_file(path: Path) -> str:  # Hash a potentially large deck without duplicate memory.
    digest = hashlib.sha256()  # Allocate a fresh exact-byte digest.
    with path.open("rb") as handle:  # Stream the selected file to EOF.
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # Bound transient hashing memory to one MiB.
            digest.update(block)  # Fold every byte into the identity.
    return digest.hexdigest()  # Return the complete lowercase identity.


def audit_comments(path: Path) -> dict[str, object]:  # Enforce a comment on every nonempty generator line.
    lines = path.read_text(encoding="utf-8").splitlines()  # Read the generator source exactly once.
    violations = [index for index, line in enumerate(lines, 1) if line.strip() and "#" not in line]  # Locate every uncommented nonempty line.
    require(not violations, "GENERATOR_COMMENT_AUDIT_FAILED", repr(violations[:20]))  # Reject publication on any user-style violation.
    return {"path": str(path.relative_to(BASE)), "nonempty_lines": sum(bool(line.strip()) for line in lines), "violations": violations, "status": "PASS"}  # Return complete source-audit evidence.


def main() -> None:  # Correct the CalculiX numeric interface and request thirty roots without physical tuning.
    require(PARENT.is_file(), "PARENT_DECK_MISSING", str(PARENT))  # Require the exact frozen-tangent parent.
    parent_sha256 = sha256_file(PARENT)  # Hash exact parent bytes independently.
    require(parent_sha256 == EXPECTED_PARENT_SHA256, "PARENT_DECK_SHA256_MISMATCH", parent_sha256)  # Reject any parent drift.
    source = PARENT.read_text(encoding="utf-8")  # Read deterministic deck text for bounded replacements.
    require(source.count(OLD_FREQUENCY_BLOCK) == 1 and source.count(OLD_SCOPE) == 1, "PARENT_MODAL_SIGNATURE_INVALID", repr((source.count(OLD_FREQUENCY_BLOCK), source.count(OLD_SCOPE))))  # Require one exact modal request and scope annotation.
    changed = 0  # Count corrected UCAB3 line-mass tokens.
    maximum_relative_delta = 0.0  # Bound numerical rounding from fifteen to twelve decimals.
    original_mu_sum = 0.0  # Accumulate source line-mass constants for evidence.
    corrected_mu_sum = 0.0  # Accumulate parser-safe line-mass constants for evidence.

    def correct_match(match: re.Match[str]) -> str:  # Shorten only the UCAB3 line-mass token.
        nonlocal changed, maximum_relative_delta, original_mu_sum, corrected_mu_sum  # Update enclosing transformation evidence.
        original = float(match.group(4))  # Parse the intended physical line mass.
        corrected_text = f"{original:.12e}"  # Serialize within the f20.0 field width.
        corrected = float(corrected_text)  # Recover the exact parser-safe numerical value.
        require(len(corrected_text) <= 20 and len(match.group(2)) <= 20 and len(match.group(3)) <= 20, "USER_SECTION_TOKEN_WIDTH_INVALID", repr((match.group(2), match.group(3), corrected_text)))  # Require all three runtime tokens within CalculiX's reader width.
        changed += 1  # Count this exact UCAB3 property once.
        original_mu_sum += original  # Accumulate intended property constants.
        corrected_mu_sum += corrected  # Accumulate parser-safe property constants.
        maximum_relative_delta = max(maximum_relative_delta, abs(corrected - original) / original)  # Track the worst rounding change.
        return f"{match.group(1)}{match.group(2)}, {match.group(3)}, {corrected_text}"  # Preserve EA and N0 bytes and replace only the overwidth mu token.

    transformed = SECTION_PATTERN.sub(correct_match, source)  # Apply the bounded parser-interface correction.
    require(changed == EXPECTED_UCAB3_COUNT, "UCAB3_SECTION_COUNT_MISMATCH", str(changed))  # Reject incomplete or overbroad selection.
    require(maximum_relative_delta <= 5.0e-13, "UCAB3_MU_ROUNDING_EXCESS", f"{maximum_relative_delta:.16e}")  # Prove this is serialization repair rather than mass tuning.
    transformed = transformed.replace(OLD_FREQUENCY_BLOCK, NEW_FREQUENCY_BLOCK, 1)  # Expand only the requested root count.
    transformed = transformed.replace(OLD_SCOPE, NEW_SCOPE, 1)  # Mark the exact parser repair.
    output_bytes = transformed.encode("utf-8")  # Freeze deterministic output bytes before naming.
    output_sha256 = hashlib.sha256(output_bytes).hexdigest()  # Compute the complete generated-deck identity.
    output_path = OUTPUT_DIR / f"C3-UB-FT14-PARSER-SAFE_m14_{output_sha256[:16]}.inp"  # Address the corrected deck by exact content.
    require(not output_path.exists(), "OUTPUT_DECK_COLLISION", str(output_path))  # Preserve immutable earlier inputs.
    output_path.write_bytes(output_bytes)  # Publish only after complete transformation checks.
    script_audit = audit_comments(Path(__file__).resolve())  # Bind the user-required line-comment audit.
    report = {"schema": "catwalk.c3-ub-ft14-parser-safe.build.v1", "status": "PARSER_SAFE_DECK_GENERATED_NOT_SOLVED", "variant": "C3-UB-FT14-PARSER-SAFE", "target_access": "NONE", "claims": {"production": False, "frequency_reproduced": False, "equilibrium_validated": False, "mass_tuned": False}, "parent": {"path": str(PARENT.relative_to(BASE)), "sha256": parent_sha256}, "deck": {"path": str(output_path.relative_to(BASE)), "sha256": output_sha256, "bytes": len(output_bytes), "modes": 14}, "delta": {"geometry_changed": False, "stiffness_changed": False, "prestress_changed": False, "constraints_changed": False, "physical_mass_target_changed": False, "ucab3_mu_tokens_corrected": changed, "token_format": [".15e", ".12e"], "maximum_relative_rounding_delta": maximum_relative_delta, "source_mu_constant_sum": original_mu_sum, "corrected_mu_constant_sum": corrected_mu_sum, "modal_root_request": [6, 14]}, "root_cause": "CalculiX usersections.f reads each constant with f20.0; the 21-character .15e mu token loses the final exponent digit and turns e-05/e-04 into e-00.", "solver_requirement": {"symmetric_shift": -0.001, "reason": "regularize the high-condition-number tangent while keeping the shift below the physical spectrum"}, "generator": script_audit}  # Publish exact correction evidence without target data.
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")  # Serialize deterministic readable evidence.
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()  # Bind every exact report byte.
    report_path = ARTIFACTS / f"C3-UB-FT14-PARSER-SAFE_build_{report_sha256[:16]}.json"  # Address build evidence by content.
    require(not report_path.exists(), "BUILD_REPORT_COLLISION", str(report_path))  # Preserve immutable earlier evidence.
    report_path.write_bytes(report_bytes)  # Publish only after the deck and source audit pass.
    print(json.dumps({"event": "C3UB_FT14_PARSER_SAFE_DECK_GENERATED", "deck": str(output_path.relative_to(BASE)), "deck_sha256": output_sha256, "report": str(report_path.relative_to(BASE)), "report_sha256": report_sha256, "ucab3_mu_tokens": changed, "max_relative_delta": maximum_relative_delta, "target_access": "NONE"}, sort_keys=True), flush=True)  # Emit concise solver handoff facts.


if __name__ == "__main__":  # Execute only when invoked as the parser-safe C3 builder.
    main()  # Generate exact target-free solver input.
