#!/usr/bin/env python3  # Publish the source-controlled numerical acceptance charter used by the canonical PR9 workflow.
import json  # Serialize the finite threshold contract deterministically.
import sys  # Receive the explicit output path from the workflow.
from pathlib import Path  # Resolve the output file without implicit directory assumptions.

CONTRACT = {"schema": "zhaqing-stress-coordination-acceptance-v1", "status": "FROZEN", "source": "PR #9 issue comment 5277838372 plus explicit initial numerical screening limits committed before qualification", "units": {"force": "N", "length": "mm", "stress": "MPa", "ratio": "dimensionless"}, "baseline": {"runId": 30068283053, "artifactName": "verified-zhaqing-s4-static-shell-9531999012bd4a94bd937e59f74443c12bcb4b23", "sourceCommit": "9531999012bd4a94bd937e59f74443c12bcb4b23", "inputSha256": "1a6578cacf02fa2f32b6922f3385aa55220b0f0bd4025c9d334ab80e21f4a50d", "sourceContractSha256": "4f3128df6885e504ec413dac19a452048fd2035fe2eafd69148d42036972b692"}, "primaryResponseContract": {"equilibriumSchema": "zhaqing-equilibrium-state-v3", "pointCount": 783, "cellCount": 1070, "connectivityIntegerCount": 4194, "integrationPointCountPerElement": 8, "reactionCollectorCount": 22, "reactionConvention": "load-free collector support-on-structure plus full physical external load equals zero with no sign fallback", "excludedGroups": ["WIND_ATTACH_LINKS", "WIND_CABLES"], "excludedElementIds": list(range(1071, 1079)), "excludedWindOnlyNodeIds": list(range(784, 792)), "windExclusionStatus": "BLOCKED_G3_G5", "windBlockerIssueIds": ["C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001", "U-WIND-001"]}, "thresholds": {"formFindingFreeNodeResidualMaximumN": 0.001, "globalForceBalanceRelativeMaximum": 0.001, "minimumSuspensionTensionMPa": 1.0, "maximumEquilibriumCoordinateCorrectionMm": 50.0, "maximumDetailedDisplacementMm": 1000.0, "maximumSuspensionStressCoordinationRelativeError": 0.50, "nodalResultCoverage": 1.0, "structuralStressResultCoverage": 1.0}, "diagnosticRules": {"solverExitCode": 0, "fatalTokenCount": 0, "mpcDependencyCount": 0, "rigidBodySingularityCount": 0, "negativePivotCount": 0, "nonFiniteResultCount": 0}, "l2Role": "trend and order-of-magnitude cross-check only; no response-fitting acceptance threshold", "engineeringReleaseRule": "G3-G6 ledger controls engineering release independently and remains BLOCKED until formal evidence closes"}  # Freeze every baseline, topology, numerical Gate, load-free reaction convention, L2, wind-exclusion, and release-boundary value before qualification.
CONTRACT["baseline"].update({"artifactId": 8587036796, "artifactDigest": "sha256:fadcd8ec455c90a429f69001f2ba98b04c7840c64d5d37f5f3cd90c766745a20"})  # Freeze the GitHub service artifact identity and digest in addition to the run, name, source commit, and inner-file hashes.
CONTRACT["primaryResponseContract"].update({"reactionAuditStiffnessLevelsNPerMm": [1.0e9, 1.0e10], "reactionAuditConvergenceRelativeMaximum": 0.001, "reactionAuditSelectedSupportTranslationMaximumMm": 0.01, "reactionCollectorConstitutiveResidualRelativeMaximum": 1.0e-5})  # Freeze both independent SPRING2 sensor levels and all audit-specific numerical limits before native qualification.


def main() -> int:  # Write the immutable charter to the explicit workflow evidence path.
    if len(sys.argv) != 2:  # Require one and only one destination argument.
        raise SystemExit("usage: stress_coordination_acceptance_contract.py OUTPUT.json")  # Stop before writing to a guessed location.
    destination = Path(sys.argv[1])  # Resolve the caller-provided evidence path.
    destination.parent.mkdir(parents=True, exist_ok=True)  # Create only its explicit parent directory.
    destination.write_text(json.dumps(CONTRACT, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Persist stable finite JSON bytes.
    return 0  # Report successful charter publication.


if __name__ == "__main__":  # Execute only as the workflow charter entry point.
    raise SystemExit(main())  # Return the native publication status.
