#!/usr/bin/env python3
"""Validate the final native FCStd in an isolated FreeCADCmd process.

The native model and the STEP exchange model are deliberately validated in
separate processes so FreeCAD 0.19 never has to hold both 675-solid BReps at the
same time. This process checks only the saved FCStd:

* object metadata, stable IDs, shape validity, positive display volume;
* expected component counts and absence of full-assembly duplicates;
* global bounding box and aggregate display volume;
* all four wind-cable solid lengths against the reconciled 3-D chord;
* all 50 hanger lengths against the accepted cable axis and registered clamp
  display gap;
* both main-cable anchor/tower control points and transverse side-span splay.

A separate process reads the STEP into one TopoShape and compares its BRep to
this report. Neither process has Gate authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import FreeCAD as App

PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: Any) -> None:
    checks.append({"checkId": check_id, "status": "PASS" if passed else "FAIL", "details": details})


def close(a: float, b: float, tolerance: float = 1e-4) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def vector_close(actual: Any, expected: Any, tolerance: float = 1e-4) -> bool:
    return (
        isinstance(actual, list)
        and isinstance(expected, list)
        and len(actual) == len(expected)
        and all(close(a, b, tolerance) for a, b in zip(actual, expected))
    )


def aggregate_bbox(objects: list[App.DocumentObject]) -> dict[str, list[float]]:
    bounds = []
    for obj in objects:
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        box = shape.BoundBox
        bounds.append((box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax))
    if not bounds:
        raise ValueError("no non-null objects for aggregate bounding box")
    return {
        "min": [min(row[0] for row in bounds), min(row[1] for row in bounds), min(row[2] for row in bounds)],
        "max": [max(row[3] for row in bounds), max(row[4] for row in bounds), max(row[5] for row in bounds)],
    }


def prefix_count(objects: list[App.DocumentObject], prefix: str) -> int:
    return sum(1 for obj in objects if obj.Name.startswith(prefix + "_"))


def main_cable_z(geometry: dict[str, Any], x_mm: float) -> float:
    span = float(geometry["span"])
    mid = float(geometry["mainCable"]["midspanZ"])
    rise = float(geometry["mainCable"]["mainspanRise"])
    u = x_mm / span - 0.5
    return mid + 4.0 * rise * u * u


def geometry_control(obj: App.DocumentObject) -> dict[str, Any]:
    raw = getattr(obj, "GeometryControlJson", "")
    if not raw:
        return {}
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


def validate() -> dict[str, Any]:
    if not PARAMS_PATH.exists() or not FCSTD_PATH.exists():
        raise FileNotFoundError(f"missing contract or FCStd: {PARAMS_PATH}, {FCSTD_PATH}")
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    geometry = params["geometry"]
    gap_report_path = OUTPUT_DIR / "hanger_clamp_gap_report.json"
    if not gap_report_path.exists():
        raise FileNotFoundError(gap_report_path)
    gap_report = json.loads(gap_report_path.read_text(encoding="utf-8"))
    gap_changes = gap_report.get("changes", [])
    if len(gap_changes) != 50:
        raise ValueError(f"hanger gap report expected 50 records, got {len(gap_changes)}")
    display_gap = float(gap_changes[0]["displayGapMm"])

    document = App.openDocument(str(FCSTD_PATH))
    part_objects = [obj for obj in document.Objects if obj.TypeId == "Part::Feature"]
    display_objects = [obj for obj in part_objects if getattr(obj, "DisplayRole", "") != "REFERENCE"]
    reference_objects = [obj for obj in part_objects if getattr(obj, "DisplayRole", "") == "REFERENCE"]
    checks: list[dict[str, Any]] = []

    required = [
        "StableObjectId", "ComponentGroupId", "SourceRefsJson", "EvidenceStatus",
        "Representation", "AssumptionRefsJson", "DisplayRole",
    ]
    missing_metadata: list[str] = []
    malformed_json: list[str] = []
    bounded_without_assumption: list[str] = []
    stable_ids: set[str] = set()
    duplicate_ids: list[str] = []
    invalid_shapes: list[str] = []
    zero_volume_display: list[str] = []
    signatures: dict[tuple[float, ...], str] = {}
    duplicate_signatures: list[tuple[str, str]] = []

    for obj in part_objects:
        for prop in required:
            if prop not in obj.PropertiesList:
                missing_metadata.append(f"{obj.Name}:{prop}")
        stable_id = getattr(obj, "StableObjectId", "")
        if stable_id in stable_ids:
            duplicate_ids.append(stable_id)
        stable_ids.add(stable_id)
        try:
            source_refs = json.loads(getattr(obj, "SourceRefsJson", "[]"))
            assumption_refs = json.loads(getattr(obj, "AssumptionRefsJson", "[]"))
            if not isinstance(source_refs, list) or not source_refs:
                missing_metadata.append(f"{obj.Name}:empty SourceRefsJson")
            evidence_status = getattr(obj, "EvidenceStatus", "")
            if ("BOUNDED" in evidence_status or "WITH_BOUNDS" in evidence_status) and not assumption_refs:
                bounded_without_assumption.append(obj.Name)
        except Exception:
            malformed_json.append(obj.Name)

        shape = obj.Shape
        if shape.isNull() or not shape.isValid():
            invalid_shapes.append(obj.Name)
            continue
        if getattr(obj, "DisplayRole", "") != "REFERENCE" and shape.Volume <= 0.0:
            zero_volume_display.append(obj.Name)
        if getattr(obj, "DisplayRole", "") != "REFERENCE":
            box = shape.BoundBox
            signature = tuple(round(value, 5) for value in (
                box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax, shape.Volume,
            ))
            if signature in signatures:
                duplicate_signatures.append((signatures[signature], obj.Name))
            else:
                signatures[signature] = obj.Name

    add_check(checks, "OBJECT_METADATA_COMPLETE", not missing_metadata and not malformed_json, {
        "missing": missing_metadata, "malformedJson": malformed_json,
    })
    add_check(checks, "STABLE_IDS_UNIQUE", not duplicate_ids, duplicate_ids)
    add_check(checks, "SHAPES_VALID", not invalid_shapes, invalid_shapes)
    add_check(checks, "DISPLAY_VOLUME_POSITIVE", not zero_volume_display, zero_volume_display)
    add_check(checks, "BOUNDED_ASSUMPTIONS_LINKED", not bounded_without_assumption, bounded_without_assumption)
    add_check(checks, "NO_SAME_LOCATION_DUPLICATE", not duplicate_signatures, duplicate_signatures)

    count_results: dict[str, Any] = {}
    count_ok = True
    for prefix, expected in params["expectedCounts"].items():
        actual = prefix_count(part_objects, prefix)
        count_results[prefix] = {"expected": expected, "actual": actual}
        count_ok = count_ok and actual == expected
    add_check(checks, "EXPECTED_COMPONENT_COUNTS", count_ok, count_results)

    forbidden = [obj.Name for obj in part_objects if "AssemblyCopy" in obj.Name or "FullAssembly" in obj.Name]
    add_check(checks, "NO_FULL_ASSEMBLY_DUPLICATE", not forbidden, forbidden)

    model_bbox = aggregate_bbox(display_objects)
    broad_bbox_ok = (
        model_bbox["min"][0] < -float(geometry["sideSpan"])
        and model_bbox["max"][0] > float(geometry["span"]) + float(geometry["sideSpan"])
        and model_bbox["min"][1] < -float(geometry["cablePlaneY"])
        and model_bbox["max"][1] > float(geometry["cablePlaneY"])
        and model_bbox["min"][2] <= -12000.0
        and model_bbox["max"][2] >= float(geometry["tower"]["cableZ"])
    )
    add_check(checks, "GLOBAL_BBOX_COVERS_SYSTEMS", broad_bbox_ok, model_bbox)

    wind_area = math.pi * (float(geometry["windCable"]["diameter"]) / 2.0) ** 2
    wind_lengths: dict[str, float] = {}
    wind_ok = True
    for obj in part_objects:
        if obj.Name.startswith("WindCable_"):
            length = float(obj.Shape.Volume) / wind_area
            wind_lengths[obj.Name] = length
            wind_ok = wind_ok and close(length, geometry["windCable"]["straightChordLength"])
    add_check(checks, "WIND_CABLE_LENGTHS_MATCH_RECONCILED_CHORD", wind_ok and len(wind_lengths) == 4, {
        "expectedLengthMm": geometry["windCable"]["straightChordLength"],
        "actualLengthsMm": wind_lengths,
        "toleranceMm": 1e-4,
    })

    hanger_area = math.pi * (float(geometry["hanger"]["diameter"]) / 2.0) ** 2
    cable_radius = float(geometry["mainCable"]["equivalentDiameter"]) / 2.0
    stations = [float(value) for value in geometry["hangerStations"]]
    hanger_results: dict[str, Any] = {}
    hanger_ok = True
    for obj in part_objects:
        if not obj.Name.startswith("Hanger_"):
            continue
        index = int(obj.Name.rsplit("_", 1)[1])
        x_mm = stations[index - 1]
        actual = float(obj.Shape.Volume) / hanger_area
        expected = main_cable_z(geometry, x_mm) - cable_radius - display_gap
        difference = actual - expected
        hanger_results[obj.Name] = {
            "actualLengthMm": actual,
            "expectedLengthMm": expected,
            "differenceMm": difference,
        }
        hanger_ok = hanger_ok and actual > 0.0 and abs(difference) <= 1e-4
    add_check(checks, "HANGER_DISPLAY_LENGTHS_MATCH_CONTRACT", hanger_ok and len(hanger_results) == 50, {
        "count": len(hanger_results),
        "displayGapMm": display_gap,
        "maximumAbsoluteDifferenceMm": max((abs(row["differenceMm"]) for row in hanger_results.values()), default=None),
        "results": hanger_results,
    })

    anchor = geometry["mainAnchor"]
    cable = geometry["mainCable"]
    main_cable_results: dict[str, Any] = {}
    main_cable_ok = True
    for side_name, sign in (("L", 1.0), ("R", -1.0)):
        obj = document.getObject(f"MainCable_{side_name}")
        expected = {
            "leftAnchorPointMm": [-float(geometry["sideSpan"]), sign * float(anchor["anchorCablePlaneY"]), float(anchor["topZ"])],
            "leftTowerPointMm": [0.0, sign * float(geometry["cablePlaneY"]), float(cable["towerZ"])],
            "rightTowerPointMm": [float(geometry["span"]), sign * float(geometry["cablePlaneY"]), float(cable["towerZ"])],
            "rightAnchorPointMm": [float(geometry["span"]) + float(geometry["sideSpan"]), sign * float(anchor["anchorCablePlaneY"]), float(anchor["topZ"])],
        }
        actual = geometry_control(obj) if obj else {}
        control_ok = bool(obj) and all(vector_close(actual.get(key), value) for key, value in expected.items())
        representation_ok = bool(obj) and getattr(obj, "Representation", "") == "SEGMENTED_CIRCULAR_SOLID_WITH_SIDE_SPLAY"
        row_ok = control_ok and representation_ok and obj.Shape.isValid()
        main_cable_ok = main_cable_ok and row_ok
        main_cable_results[side_name] = {
            "expected": expected,
            "actual": actual,
            "controlOk": control_ok,
            "representation": getattr(obj, "Representation", "") if obj else None,
            "representationOk": representation_ok,
        }
    add_check(checks, "MAIN_CABLE_ANCHOR_SPLAY_MATCH_CONTRACT", main_cable_ok, main_cable_results)

    display_volume = sum(float(obj.Shape.Volume) for obj in display_objects)
    technical_pass = all(check["status"] == "PASS" for check in checks)
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS" if technical_pass else "FAIL",
        "engineeringReleaseStatus": params["engineeringReleaseStatus"],
        "freecadVersion": ".".join(App.Version()[:3]),
        "files": {
            "fcstd": {"path": str(FCSTD_PATH), "sha256": sha256_file(FCSTD_PATH), "bytes": FCSTD_PATH.stat().st_size},
        },
        "statistics": {
            "partObjects": len(part_objects),
            "displayObjects": len(display_objects),
            "referenceObjects": len(reference_objects),
            "displaySolidCount": sum(len(obj.Shape.Solids) for obj in display_objects),
            "displayVolumeMm3": display_volume,
            "fcstdBBox": model_bbox,
        },
        "checks": checks,
        "failedChecks": [check["checkId"] for check in checks if check["status"] != "PASS"],
    }
    report_path = OUTPUT_DIR / "fcstd_validation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    App.closeDocument(document.Name)
    return report


def main() -> int:
    try:
        report = validate()
        print(json.dumps({
            "status": report["status"],
            "engineeringReleaseStatus": report["engineeringReleaseStatus"],
            "failedChecks": report["failedChecks"],
            "statistics": report["statistics"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "fcstd-validation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
