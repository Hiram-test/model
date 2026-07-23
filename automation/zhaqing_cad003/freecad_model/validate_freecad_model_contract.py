#!/usr/bin/env python3
"""Run the independent FCStd/STEP validator with a contract-derived hanger check.

The original validator used ``length > 900 mm`` as a coarse smoke test. A later,
explicitly registered 20 mm display gap for the omitted hanger clamp makes the
shortest centre hanger about 887.94 mm. There is no drawing or Skill basis for
900 mm, so this adapter removes that magic threshold and replaces it with a
stronger deterministic check for every one of the 50 hangers:

``actual solid length == cable_axis_z(x) - equivalent cable radius
                       - registered clamp display gap``

All other checks—including STEP geometry reimport, metadata, object counts,
bounding boxes and shape validity—come from ``validate_freecad_model.py``.
This adapter cannot change the engineering release status; G3–G6 remain
``BLOCKED`` while the upstream evidence and interface assumptions are open.
"""
from __future__ import annotations

import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# FreeCADCmd executes an absolute script path without consistently adding that
# script's directory to sys.path. Resolve it explicitly so this adapter remains
# standalone and can always load the adjacent independent base validator.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_freecad_model as base


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main_cable_z(geometry: dict[str, Any], x_mm: float) -> float:
    """Accepted parabolic main-span cable axis elevation at one station."""
    span = float(geometry["span"])
    mid = float(geometry["mainCable"]["midspanZ"])
    rise = float(geometry["mainCable"]["mainspanRise"])
    u = x_mm / span - 0.5
    return mid + 4.0 * rise * u * u


def contract_hanger_check() -> dict[str, Any]:
    """Recompute every display hanger length from frozen inputs and gap report."""
    params = json.loads(base.PARAMS_PATH.read_text(encoding="utf-8"))
    geometry = params["geometry"]
    manifest_path = base.OUTPUT_DIR / "object_manifest.json"
    gap_report_path = base.OUTPUT_DIR / "hanger_clamp_gap_report.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if not gap_report_path.exists():
        raise FileNotFoundError(gap_report_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gap_report = json.loads(gap_report_path.read_text(encoding="utf-8"))
    changes = gap_report.get("changes", [])
    if len(changes) != 50:
        raise ValueError(f"hanger gap report expected 50 changes, got {len(changes)}")
    display_gap = float(changes[0]["displayGapMm"])
    if any(abs(float(item["displayGapMm"]) - display_gap) > 1e-12 for item in changes):
        raise ValueError("hanger display gap is not uniform across the 50 records")

    diameter = float(geometry["hanger"]["diameter"])
    area = math.pi * (diameter / 2.0) ** 2
    cable_radius = float(geometry["mainCable"]["equivalentDiameter"]) / 2.0
    stations = [float(value) for value in geometry["hangerStations"]]

    hanger_rows = [row for row in manifest if str(row.get("name", "")).startswith("Hanger_")]
    actual: dict[str, float] = {}
    expected: dict[str, float] = {}
    differences: dict[str, float] = {}
    for row in hanger_rows:
        name = str(row["name"])
        index = int(name.rsplit("_", 1)[1])
        x_mm = stations[index - 1]
        actual_length = float(row["volume"]) / area
        expected_length = main_cable_z(geometry, x_mm) - cable_radius - display_gap
        actual[name] = actual_length
        expected[name] = expected_length
        differences[name] = actual_length - expected_length

    max_abs = max((abs(value) for value in differences.values()), default=float("inf"))
    passed = (
        len(hanger_rows) == 50
        and len(actual) == 50
        and all(value > 0.0 for value in actual.values())
        and max_abs <= 1e-4
    )
    return {
        "checkId": "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
        "status": "PASS" if passed else "FAIL",
        "details": {
            "count": len(actual),
            "displayGapMm": display_gap,
            "minimumActualLengthMm": min(actual.values()) if actual else None,
            "maximumActualLengthMm": max(actual.values()) if actual else None,
            "maximumAbsoluteDifferenceMm": max_abs,
            "differencesMm": differences,
            "basis": "main_cable_z(x) - equivalentCableRadius - registeredClampDisplayGap",
            "toleranceMm": 1e-4,
        },
    }


def corrected_validation() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run base validation, replacing only the unsupported hanger threshold."""
    report, gate_receipt = base.validate()
    replacement = contract_hanger_check()
    old_ids = {"HANGER_POSITIVE_LENGTHS", "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT"}
    replaced = False
    new_checks = []
    for check in report.get("checks", []):
        if check.get("checkId") in old_ids:
            if not replaced:
                new_checks.append(replacement)
                replaced = True
        else:
            new_checks.append(check)
    if not replaced:
        raise RuntimeError("base validator did not expose a hanger length check")
    report["checks"] = new_checks

    report["issues"] = [
        issue for issue in report.get("issues", [])
        if issue.get("issueId") not in {
            "TECH-HANGER_POSITIVE_LENGTHS",
            "TECH-HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
        }
    ]
    if replacement["status"] != "PASS":
        report["issues"].append({
            "issueId": "TECH-HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
            "severity": "CRITICAL",
            "ownerNode": "N07",
            "details": replacement["details"],
        })

    technical_pass = all(item.get("status") == "PASS" for item in new_checks)
    report["technicalStatus"] = "PASS" if technical_pass else "FAIL"
    report["hangerValidationPolicy"] = {
        "replacedCheck": "HANGER_POSITIVE_LENGTHS (>900 mm magic threshold)",
        "activeCheck": replacement["checkId"],
        "reason": "No source, charter or Skill threshold supports 900 mm; all 50 values are recomputed from the frozen contract.",
    }
    gate_receipt["technicalGeometryValidation"] = report["technicalStatus"]
    return report, gate_receipt


def main() -> int:
    try:
        report, gate_receipt = corrected_validation()
        report_path = base.OUTPUT_DIR / "validation_report.json"
        gate_path = base.OUTPUT_DIR / "gate_receipt.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        gate_path.write_text(json.dumps(gate_receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        base.write_markdown(report)
        failed = [item["checkId"] for item in report["checks"] if item["status"] != "PASS"]
        print(json.dumps({
            "technicalStatus": report["technicalStatus"],
            "engineeringReleaseStatus": report["engineeringReleaseStatus"],
            "checks": len(report["checks"]),
            "failedChecks": failed,
            "hangerCheck": "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
        }, ensure_ascii=False, indent=2))
        return 0 if report["technicalStatus"] == "PASS" else 1
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        # Use a fallback path if the adjacent base module itself failed to load.
        output_dir = getattr(base, "OUTPUT_DIR", Path(os.environ.get("ZHAQING_OUT", ".")).resolve())
        (output_dir / "logs").mkdir(parents=True, exist_ok=True)
        (output_dir / "logs" / "contract-validation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
