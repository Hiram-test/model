#!/usr/bin/env python3
"""Run the independent FCStd/STEP validator with contract-derived checks.

The base validator intentionally contains broad smoke tests. Two of those tests
became invalid after evidence-driven geometry corrections:

* a hanger was required to be longer than an unsupported 900 mm magic value;
* a main cable was required to descend to the old, assumed -1200 mm anchor
  elevation even after SGT-26 established a different display interface.

This adapter retains every other base check, but replaces those two assumptions
with deterministic checks derived from ``frozen_model_contract.json`` and the
actual post-correction object manifest. It cannot change the engineering release
status: G3-G6 remain BLOCKED while drawing conflicts and local interfaces remain
open.
"""
from __future__ import annotations

import json
import math
import os
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


def close(a: float, b: float, tolerance: float = 1e-4) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def vector_close(actual: Any, expected: Any, tolerance: float = 1e-4) -> bool:
    return (
        isinstance(actual, list)
        and isinstance(expected, list)
        and len(actual) == len(expected)
        and all(close(a, b, tolerance) for a, b in zip(actual, expected))
    )


def load_manifest() -> list[dict[str, Any]]:
    manifest_path = base.OUTPUT_DIR / "object_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("object_manifest.json must contain an array")
    return value


def contract_hanger_check() -> dict[str, Any]:
    """Recompute every display hanger length from frozen inputs and gap report."""
    params = json.loads(base.PARAMS_PATH.read_text(encoding="utf-8"))
    geometry = params["geometry"]
    manifest = load_manifest()
    gap_report_path = base.OUTPUT_DIR / "hanger_clamp_gap_report.json"
    if not gap_report_path.exists():
        raise FileNotFoundError(gap_report_path)

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


def contract_main_cable_check() -> dict[str, Any]:
    """Check both cable side-span interfaces against the reconciled contract."""
    params = json.loads(base.PARAMS_PATH.read_text(encoding="utf-8"))
    geometry = params["geometry"]
    manifest = load_manifest()
    cable_rows = {
        str(row.get("name")): row
        for row in manifest
        if str(row.get("name", "")).startswith("MainCable_")
    }
    anchor = geometry["mainAnchor"]
    cable = geometry["mainCable"]
    side_span = float(geometry["sideSpan"])
    span = float(geometry["span"])
    tower_y = float(geometry["cablePlaneY"])
    anchor_y = float(anchor["anchorCablePlaneY"])
    anchor_z = float(anchor["topZ"])
    radius = float(cable["equivalentDiameter"]) / 2.0

    results: dict[str, Any] = {}
    all_ok = len(cable_rows) == 2
    for side_name, sign in (("L", 1.0), ("R", -1.0)):
        name = f"MainCable_{side_name}"
        row = cable_rows.get(name)
        expected_control = {
            "leftAnchorPointMm": [-side_span, sign * anchor_y, anchor_z],
            "leftTowerPointMm": [0.0, sign * tower_y, float(cable["towerZ"])],
            "rightTowerPointMm": [span, sign * tower_y, float(cable["towerZ"])],
            "rightAnchorPointMm": [span + side_span, sign * anchor_y, anchor_z],
        }
        if row is None:
            results[name] = {"missing": True, "expected": expected_control}
            all_ok = False
            continue
        actual_control = row.get("geometryControl") or {}
        bbox = row.get("bbox") or {}
        bbox_min = bbox.get("min") or []
        bbox_max = bbox.get("max") or []
        control_ok = all(
            vector_close(actual_control.get(key), value)
            for key, value in expected_control.items()
        )
        # Cylindrical solids extend roughly one radius beyond centreline control
        # points. This envelope check ties the manifest to the actual saved BRep.
        envelope_ok = (
            len(bbox_min) == 3
            and len(bbox_max) == 3
            and float(bbox_min[0]) <= -side_span + radius + 1e-3
            and float(bbox_max[0]) >= span + side_span - radius - 1e-3
            and float(bbox_min[2]) <= anchor_z + radius + 1e-3
            and float(bbox_max[2]) >= float(cable["towerZ"]) - radius - 1e-3
        )
        representation_ok = row.get("representation") == "SEGMENTED_CIRCULAR_SOLID_WITH_SIDE_SPLAY"
        row_ok = control_ok and envelope_ok and representation_ok
        all_ok = all_ok and row_ok
        results[name] = {
            "expectedControl": expected_control,
            "actualControl": actual_control,
            "bbox": bbox,
            "controlOk": control_ok,
            "envelopeOk": envelope_ok,
            "representation": row.get("representation"),
            "representationOk": representation_ok,
        }

    return {
        "checkId": "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT",
        "status": "PASS" if all_ok else "FAIL",
        "details": {
            "cableCount": len(cable_rows),
            "anchorCablePlaneYmm": anchor_y,
            "towerCablePlaneYmm": tower_y,
            "anchorTopZmm": anchor_z,
            "results": results,
            "toleranceMm": 1e-4,
        },
    }


def corrected_validation() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run base validation and replace only source-unsupported smoke tests."""
    report, gate_receipt = base.validate()
    replacements = {
        "HANGER_POSITIVE_LENGTHS": contract_hanger_check(),
        "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT": contract_hanger_check(),
        "MAIN_CABLE_CONTROL_RANGE": contract_main_cable_check(),
        "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT": contract_main_cable_check(),
    }
    replacement_groups = {
        "hanger": {"HANGER_POSITIVE_LENGTHS", "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT"},
        "mainCable": {"MAIN_CABLE_CONTROL_RANGE", "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT"},
    }
    inserted = {key: False for key in replacement_groups}
    new_checks: list[dict[str, Any]] = []
    for check in report.get("checks", []):
        check_id = check.get("checkId")
        group_name = next(
            (name for name, ids in replacement_groups.items() if check_id in ids),
            None,
        )
        if group_name is None:
            new_checks.append(check)
            continue
        if not inserted[group_name]:
            replacement_id = (
                "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT"
                if group_name == "hanger"
                else "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT"
            )
            new_checks.append(replacements[replacement_id])
            inserted[group_name] = True
    missing_groups = [name for name, value in inserted.items() if not value]
    if missing_groups:
        raise RuntimeError(f"base validator did not expose replaceable checks: {missing_groups}")
    report["checks"] = new_checks

    removed_issue_ids = {
        "TECH-HANGER_POSITIVE_LENGTHS",
        "TECH-HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
        "TECH-MAIN_CABLE_CONTROL_RANGE",
        "TECH-MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT",
    }
    report["issues"] = [
        issue for issue in report.get("issues", [])
        if issue.get("issueId") not in removed_issue_ids
    ]
    active_replacements = [
        replacements["HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT"],
        replacements["MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT"],
    ]
    for replacement in active_replacements:
        if replacement["status"] != "PASS":
            report["issues"].append({
                "issueId": f"TECH-{replacement['checkId']}",
                "severity": "CRITICAL",
                "ownerNode": "N07",
                "details": replacement["details"],
            })

    technical_pass = all(item.get("status") == "PASS" for item in new_checks)
    report["technicalStatus"] = "PASS" if technical_pass else "FAIL"
    report["contractValidationPolicy"] = {
        "replacedChecks": [
            {
                "old": "HANGER_POSITIVE_LENGTHS (>900 mm magic threshold)",
                "active": "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
                "reason": "All 50 values are recomputed from the frozen cable axis, equivalent radius and registered clamp gap.",
            },
            {
                "old": "MAIN_CABLE_CONTROL_RANGE (old -1200 mm anchor assumption)",
                "active": "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT",
                "reason": "SGT-26 now controls the anchorage top elevation and 470 cm anchor cable spacing.",
            },
        ]
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
            "activeContractChecks": [
                "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT",
                "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT",
            ],
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
        output_dir = getattr(base, "OUTPUT_DIR", Path(os.environ.get("ZHAQING_OUT", ".")).resolve())
        (output_dir / "logs").mkdir(parents=True, exist_ok=True)
        (output_dir / "logs" / "contract-validation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
