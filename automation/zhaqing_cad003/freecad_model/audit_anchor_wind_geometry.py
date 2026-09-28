#!/usr/bin/env python3
"""Independently audit the corrected main-anchor and wind-system geometry.

This script runs in a fresh FreeCADCmd process after the corrected FCStd is
saved. It does not import the model builder or correction implementation. The
checks are derived from the frozen contract and object metadata:

* main-anchor extents, volume, three underside levels, transverse recess and
  two raised strips;
* side-span main-cable endpoint coordinates and anchor/tower transverse splay;
* wind-cable B stations, endpoint offsets, plan length, 3-D chord and angles;
* stepped wind-anchor volume, top/bottom elevations and eye coordinates;
* left/right symmetry and explicit propagation of the unresolved conflicts.
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

import FreeCAD as App

PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
TOL = 1e-4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: Any) -> None:
    checks.append({"checkId": check_id, "status": "PASS" if passed else "FAIL", "details": details})


def close(a: float, b: float, tolerance: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def vector_close(actual: list[float], expected: list[float], tolerance: float = TOL) -> bool:
    return len(actual) == len(expected) and all(close(a, b, tolerance) for a, b in zip(actual, expected))


def control(obj: App.DocumentObject) -> dict[str, Any]:
    raw = getattr(obj, "GeometryControlJson", "")
    if not raw:
        raise ValueError(f"{obj.Name} has no GeometryControlJson")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{obj.Name} GeometryControlJson is not an object")
    return value


def expected_main_anchor_volume(anchor: dict[str, Any]) -> float:
    length = float(anchor["longitudinal"])
    width = float(anchor["transverse"])
    top = float(anchor["topZ"])
    shoulder_top = top - float(anchor["shoulderTopDrop"])
    recess_bottom = shoulder_top - float(anchor["centralRecessDepthBelowShoulder"])
    lower = 0.0
    for region, drop in zip(anchor["bottomRegionsFromBridge"], anchor["bottomDropsBelowTop"]):
        bottom = top - float(drop)
        lower += float(region) * width * (recess_bottom - bottom)
    central = float(anchor["transversePartitions"][3])
    outer_width = width - central
    shoulders = length * outer_width * (shoulder_top - recess_bottom)
    strips = 2.0 * length * float(anchor["raisedStripWidth"]) * (top - shoulder_top)
    return lower + shoulders + strips


def inside(shape, point: list[float]) -> bool:
    return bool(shape.isInside(App.Vector(*point), 1e-5, False))


def audit() -> dict[str, Any]:
    if not PARAMS_PATH.exists() or not FCSTD_PATH.exists():
        raise FileNotFoundError(f"missing contract or FCStd: {PARAMS_PATH}, {FCSTD_PATH}")
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    g = params["geometry"]
    doc = App.openDocument(str(FCSTD_PATH))
    checks: list[dict[str, Any]] = []

    anchor = g["mainAnchor"]
    expected_volume = expected_main_anchor_volume(anchor)
    main_anchor_results: dict[str, Any] = {}
    for name, bridge_x, direction in (
        ("MainAnchorage_Left", -float(g["sideSpan"]), -1.0),
        ("MainAnchorage_Right", float(g["span"]) + float(g["sideSpan"]), 1.0),
    ):
        obj = doc.getObject(name)
        if obj is None:
            main_anchor_results[name] = {"missing": True}
            continue
        box = obj.Shape.BoundBox
        expected_x = (
            [bridge_x - float(anchor["longitudinal"]), bridge_x]
            if direction < 0
            else [bridge_x, bridge_x + float(anchor["longitudinal"])]
        )
        expected_bbox = {
            "min": [expected_x[0], -float(anchor["transverse"]) / 2.0, float(anchor["topZ"]) - float(anchor["totalHeight"])],
            "max": [expected_x[1], float(anchor["transverse"]) / 2.0, float(anchor["topZ"])],
        }
        actual_bbox = {
            "min": [box.XMin, box.YMin, box.ZMin],
            "max": [box.XMax, box.YMax, box.ZMax],
        }
        shoulder_top = float(anchor["topZ"]) - float(anchor["shoulderTopDrop"])
        recess_bottom = shoulder_top - float(anchor["centralRecessDepthBelowShoulder"])
        u_centres = []
        cursor = 0.0
        for region in anchor["bottomRegionsFromBridge"]:
            u_centres.append(cursor + float(region) / 2.0)
            cursor += float(region)
        def global_x(u: float) -> float:
            return bridge_x + direction * u
        bottom_samples = []
        for u, drop in zip(u_centres, anchor["bottomDropsBelowTop"]):
            bottom = float(anchor["topZ"]) - float(drop)
            p_inside = [global_x(u), -float(anchor["transverse"]) / 2.0 + 100.0, bottom + 1.0]
            p_below = [global_x(u), -float(anchor["transverse"]) / 2.0 + 100.0, bottom - 1.0]
            bottom_samples.append({
                "uMm": u,
                "bottomZmm": bottom,
                "insideAbove": inside(obj.Shape, p_inside),
                "insideBelow": inside(obj.Shape, p_below),
            })
        recess_point = [global_x(float(anchor["longitudinal"]) / 2.0), 0.0, (recess_bottom + shoulder_top) / 2.0]
        shoulder_point = [global_x(float(anchor["longitudinal"]) / 2.0), float(anchor["transverse"]) / 2.0 - 100.0, (recess_bottom + shoulder_top) / 2.0]
        strip_point = [global_x(float(anchor["longitudinal"]) / 2.0), float(anchor["anchorCablePlaneY"]), (shoulder_top + float(anchor["topZ"])) / 2.0]
        nonstrip_top_point = [global_x(float(anchor["longitudinal"]) / 2.0), 0.0, (shoulder_top + float(anchor["topZ"])) / 2.0]
        main_anchor_results[name] = {
            "bbox": actual_bbox,
            "expectedBBox": expected_bbox,
            "volumeMm3": float(obj.Shape.Volume),
            "expectedVolumeMm3": expected_volume,
            "volumeDifferenceMm3": float(obj.Shape.Volume) - expected_volume,
            "bottomSamples": bottom_samples,
            "recessOpen": not inside(obj.Shape, recess_point),
            "outerShoulderPresent": inside(obj.Shape, shoulder_point),
            "raisedStripPresent": inside(obj.Shape, strip_point),
            "nonStripTopOpen": not inside(obj.Shape, nonstrip_top_point),
            "representation": getattr(obj, "Representation", ""),
        }
    main_anchor_ok = all(
        not item.get("missing")
        and vector_close(item["bbox"]["min"], item["expectedBBox"]["min"])
        and vector_close(item["bbox"]["max"], item["expectedBBox"]["max"])
        and abs(item["volumeDifferenceMm3"]) <= 1e-2
        and all(sample["insideAbove"] and not sample["insideBelow"] for sample in item["bottomSamples"])
        and item["recessOpen"]
        and item["outerShoulderPresent"]
        and item["raisedStripPresent"]
        and item["nonStripTopOpen"]
        and item["representation"] == "STEPPED_RECESSED_DISPLAY_ENVELOPE"
        for item in main_anchor_results.values()
    )
    add_check(checks, "MAIN_ANCHOR_ORTHOGRAPHIC_PROFILE", main_anchor_ok, main_anchor_results)

    main_cable_results: dict[str, Any] = {}
    for side_name, sign in (("L", 1.0), ("R", -1.0)):
        obj = doc.getObject(f"MainCable_{side_name}")
        data = control(obj) if obj else {}
        expected = {
            "leftAnchorPointMm": [-float(g["sideSpan"]), sign * float(anchor["anchorCablePlaneY"]), float(anchor["topZ"])],
            "leftTowerPointMm": [0.0, sign * float(g["cablePlaneY"]), float(g["mainCable"]["towerZ"])],
            "rightTowerPointMm": [float(g["span"]), sign * float(g["cablePlaneY"]), float(g["mainCable"]["towerZ"])],
            "rightAnchorPointMm": [float(g["span"]) + float(g["sideSpan"]), sign * float(anchor["anchorCablePlaneY"]), float(anchor["topZ"])],
        }
        main_cable_results[side_name] = {"actual": data, "expected": expected}
    main_cable_ok = all(
        all(vector_close(item["actual"].get(key, []), value) for key, value in item["expected"].items())
        for item in main_cable_results.values()
    )
    add_check(checks, "MAIN_CABLE_ANCHOR_SPLAY", main_cable_ok, main_cable_results)

    wind = g["windCable"]
    wind_anchor = g["windAnchor"]
    wind_results: list[dict[str, Any]] = []
    cable_counter = 0
    for order, x_attach in enumerate(wind["attachStations"]):
        x_sign = -1.0 if order == 0 else 1.0
        for side_name, y_sign in (("L", 1.0), ("R", -1.0)):
            cable_counter += 1
            cable_obj = doc.getObject(f"WindCable_{cable_counter:02d}")
            anchor_obj = doc.getObject(f"WindAnchorage_{cable_counter:02d}")
            cable_data = control(cable_obj) if cable_obj else {}
            anchor_data = control(anchor_obj) if anchor_obj else {}
            expected_attach = [float(x_attach), y_sign * float(g["cablePlaneY"]), float(wind["attachmentZ"])]
            expected_eye = [
                float(x_attach) + x_sign * float(wind["candidateLongitudinalOffset"]),
                y_sign * (float(g["cablePlaneY"]) + float(wind["candidateLateralOffset"])),
                float(wind["anchorEyeZ"]),
            ]
            vector = [expected_eye[i] - expected_attach[i] for i in range(3)]
            plan_length = math.hypot(vector[0], vector[1])
            chord = math.sqrt(sum(value * value for value in vector))
            plan_angle = math.degrees(math.atan2(abs(vector[1]), abs(vector[0])))
            vertical_angle = math.degrees(math.atan2(abs(vector[2]), plan_length))
            expected_volume = (
                float(wind_anchor["baseLength"]) * float(wind_anchor["baseWidth"]) * float(wind_anchor["baseHeight"])
                + float(wind_anchor["pedestalLength"]) * float(wind_anchor["pedestalWidth"]) * float(wind_anchor["pedestalHeight"])
            )
            anchor_bbox = None
            anchor_volume = None
            if anchor_obj:
                box = anchor_obj.Shape.BoundBox
                anchor_bbox = {
                    "min": [box.XMin, box.YMin, box.ZMin],
                    "max": [box.XMax, box.YMax, box.ZMax],
                }
                anchor_volume = float(anchor_obj.Shape.Volume)
            wind_results.append({
                "cable": cable_obj.Name if cable_obj else None,
                "anchor": anchor_obj.Name if anchor_obj else None,
                "hangerCrossbeamNumber": wind["attachHangerCrossbeamNumbers"][order],
                "actualCableControl": cable_data,
                "actualAnchorControl": anchor_data,
                "expectedAttachmentPointMm": expected_attach,
                "expectedAnchorEyePointMm": expected_eye,
                "expectedPlanLengthMm": plan_length,
                "expectedStraightChordMm": chord,
                "expectedPlanAngleDeg": plan_angle,
                "expectedVerticalAngleDeg": vertical_angle,
                "anchorVolumeMm3": anchor_volume,
                "expectedAnchorVolumeMm3": expected_volume,
                "anchorBBox": anchor_bbox,
            })

    wind_ok = True
    for item in wind_results:
        cd = item["actualCableControl"]
        ad = item["actualAnchorControl"]
        wind_ok = wind_ok and bool(item["cable"] and item["anchor"])
        wind_ok = wind_ok and vector_close(cd.get("attachmentPointMm", []), item["expectedAttachmentPointMm"])
        wind_ok = wind_ok and vector_close(cd.get("anchorEyePointMm", []), item["expectedAnchorEyePointMm"])
        wind_ok = wind_ok and close(cd.get("planLengthMm", float("nan")), item["expectedPlanLengthMm"])
        wind_ok = wind_ok and close(cd.get("straightChordLengthMm", float("nan")), item["expectedStraightChordMm"])
        wind_ok = wind_ok and close(cd.get("planAngleDeg", float("nan")), item["expectedPlanAngleDeg"])
        wind_ok = wind_ok and close(cd.get("verticalAngleDeg", float("nan")), item["expectedVerticalAngleDeg"])
        wind_ok = wind_ok and vector_close(ad.get("eyePointMm", []), item["expectedAnchorEyePointMm"])
        wind_ok = wind_ok and close(item["anchorVolumeMm3"], item["expectedAnchorVolumeMm3"], 1e-2)
        wind_ok = wind_ok and close(item["anchorBBox"]["max"][2], item["expectedAnchorEyePointMm"][2])
        wind_ok = wind_ok and close(item["anchorBBox"]["min"][2], item["expectedAnchorEyePointMm"][2] - float(wind_anchor["totalHeight"]))
    add_check(checks, "WIND_CABLE_AND_ANCHOR_CONTROL_GEOMETRY", wind_ok, wind_results)

    number_conflict = wind["attachHangerCrossbeamNumbers"] != wind["conflictingNoteCrossbeamNumbers"]
    plan_rounding_ok = abs(float(wind["derivedPlanLength"]) - float(wind["materialPlanLength"])) <= 10.0
    vertical_requirement_ok = float(wind["candidateVerticalAngleDeg"]) >= float(wind["verticalAngleMinimumDeg"])
    horizontal_conflict = float(wind["candidatePlanAngleDeg"]) < float(wind["horizontalAngleMinimumDeg"])
    blockers = set(params.get("blockingIssueIds", []))
    conflict_record_ok = (
        number_conflict
        and horizontal_conflict
        and "C-WIND-ATTACH-NUMBER-001" in blockers
        and "C-WIND-HORIZONTAL-ANGLE-001" in blockers
    )
    add_check(checks, "WIND_DRAWING_CONFLICTS_RECORDED", conflict_record_ok, {
        "selectedViewNumbers": wind["attachHangerCrossbeamNumbers"],
        "conflictingNoteNumbers": wind["conflictingNoteCrossbeamNumbers"],
        "derivedPlanAngleDeg": wind["candidatePlanAngleDeg"],
        "drawingMinimumDeg": wind["horizontalAngleMinimumDeg"],
        "derivedVerticalAngleDeg": wind["candidateVerticalAngleDeg"],
        "verticalMinimumDeg": wind["verticalAngleMinimumDeg"],
        "planLengthMm": wind["derivedPlanLength"],
        "materialPlanLengthMm": wind["materialPlanLength"],
        "planLengthRoundingOkWithin10mm": plan_rounding_ok,
        "verticalRequirementSatisfied": vertical_requirement_ok,
        "blockingIssueIds": sorted(blockers),
    })

    technical_pass = all(check["status"] == "PASS" for check in checks)
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS" if technical_pass else "FAIL",
        "engineeringReleaseStatus": params.get("engineeringReleaseStatus", "BLOCKED"),
        "checks": checks,
        "summary": {
            "mainAnchorCount": 2,
            "windCableCount": 4,
            "windAnchorCount": 4,
            "selectedWindCrossbeams": wind["attachHangerCrossbeamNumbers"],
            "windAttachStationsMm": wind["attachStations"],
        },
        "engineeringBlockersRemain": sorted(blockers),
    }
    (OUTPUT_DIR / "anchor_wind_geometry_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    App.closeDocument(doc.Name)
    return report


def main() -> int:
    try:
        report = audit()
        print(json.dumps({
            "status": report["status"],
            "engineeringReleaseStatus": report["engineeringReleaseStatus"],
            "failedChecks": [c["checkId"] for c in report["checks"] if c["status"] != "PASS"],
            "summary": report["summary"],
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
        (OUTPUT_DIR / "logs" / "anchor-wind-audit-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
