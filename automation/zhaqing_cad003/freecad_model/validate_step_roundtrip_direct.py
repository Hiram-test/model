#!/usr/bin/env python3
"""Read the final STEP directly into one TopoShape and compare it with FCStd.

This process intentionally does not open the native 239-object FCStd. It reads
only the previously written ``fcstd_validation_report.json`` and the STEP file,
thereby avoiding the FreeCAD 0.19 memory/crash path caused by holding both large
BReps and expanding 675 solids into hundreds of document objects at once.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import FreeCAD as App
import Part

OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
STEP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-display.step"
FCSTD_REPORT_PATH = OUTPUT_DIR / "fcstd_validation_report.json"
ROUNDTRIP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-STEP-roundtrip.FCStd"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bbox(shape: Part.Shape) -> dict[str, list[float]]:
    box = shape.BoundBox
    return {
        "min": [box.XMin, box.YMin, box.ZMin],
        "max": [box.XMax, box.YMax, box.ZMax],
    }


def bbox_delta(a: dict[str, list[float]], b: dict[str, list[float]]) -> float:
    return max(
        abs(float(x) - float(y))
        for key in ("min", "max")
        for x, y in zip(a[key], b[key])
    )


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: Any) -> None:
    checks.append({"checkId": check_id, "status": "PASS" if passed else "FAIL", "details": details})


def validate() -> dict[str, Any]:
    if not STEP_PATH.exists() or not FCSTD_REPORT_PATH.exists():
        raise FileNotFoundError(f"missing STEP or FCStd report: {STEP_PATH}, {FCSTD_REPORT_PATH}")
    fcstd_report = json.loads(FCSTD_REPORT_PATH.read_text(encoding="utf-8"))
    if fcstd_report.get("status") != "PASS":
        raise ValueError("native FCStd validation did not pass before STEP read")

    # TopoShape.read supports STEP/IGES/BREP and returns one shape without OCAF
    # labels or per-solid document expansion.
    shape = Part.Shape()
    shape.read(str(STEP_PATH))
    step_bbox = bbox(shape) if not shape.isNull() else {"min": [], "max": []}
    fcstd_bbox = fcstd_report["statistics"]["fcstdBBox"]
    expected_volume = float(fcstd_report["statistics"]["displayVolumeMm3"])
    expected_solids = int(fcstd_report["statistics"]["displaySolidCount"])
    actual_volume = float(shape.Volume) if not shape.isNull() else 0.0
    actual_solids = len(shape.Solids) if not shape.isNull() else 0
    delta = bbox_delta(fcstd_bbox, step_bbox) if not shape.isNull() else float("inf")
    volume_delta = actual_volume - expected_volume
    volume_tolerance = max(1e-2, abs(expected_volume) * 1e-10)

    checks: list[dict[str, Any]] = []
    add_check(checks, "STEP_DIRECT_READ_NONEMPTY", not shape.isNull(), {
        "reader": "Part.TopoShape.read",
        "path": str(STEP_PATH),
    })
    add_check(checks, "STEP_DIRECT_READ_VALID", not shape.isNull() and shape.isValid(), {
        "shapeType": shape.ShapeType if not shape.isNull() else None,
        "solidCount": actual_solids,
        "volumeMm3": actual_volume,
    })
    add_check(checks, "STEP_SOLID_COUNT_MATCH", actual_solids == expected_solids, {
        "expected": expected_solids,
        "actual": actual_solids,
    })
    add_check(checks, "STEP_FCSTD_BBOX_MATCH", delta <= 0.5, {
        "maximumAbsoluteDeltaMm": delta,
        "fcstd": fcstd_bbox,
        "step": step_bbox,
        "toleranceMm": 0.5,
    })
    add_check(checks, "STEP_FCSTD_VOLUME_MATCH", abs(volume_delta) <= volume_tolerance, {
        "fcstdDisplayVolumeMm3": expected_volume,
        "stepVolumeMm3": actual_volume,
        "differenceMm3": volume_delta,
        "toleranceMm3": volume_tolerance,
    })

    if not shape.isNull():
        document = App.newDocument("Zhaqing_STEP_Direct_RoundTrip")
        obj = document.addObject("Part::Feature", "StepDirectTopoShape")
        obj.Label = "CAD-003 STEP direct TopoShape round-trip"
        obj.Shape = shape
        obj.addProperty("App::PropertyString", "ReaderPath")
        obj.ReaderPath = "Part.TopoShape.read"
        document.recompute()
        document.saveAs(str(ROUNDTRIP_PATH))
        App.closeDocument(document.Name)

    technical_pass = all(check["status"] == "PASS" for check in checks)
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS" if technical_pass else "FAIL",
        "reader": {
            "api": "Part.TopoShape.read",
            "mode": "single compound shape; isolated process; no OCAF and no per-solid document expansion",
        },
        "files": {
            "step": {"path": str(STEP_PATH), "sha256": sha256_file(STEP_PATH), "bytes": STEP_PATH.stat().st_size},
            "roundtripFcstd": {
                "path": str(ROUNDTRIP_PATH),
                "sha256": sha256_file(ROUNDTRIP_PATH) if ROUNDTRIP_PATH.exists() else None,
                "bytes": ROUNDTRIP_PATH.stat().st_size if ROUNDTRIP_PATH.exists() else 0,
            },
        },
        "statistics": {
            "shapeType": shape.ShapeType if not shape.isNull() else None,
            "solidCount": actual_solids,
            "faceCount": len(shape.Faces) if not shape.isNull() else 0,
            "edgeCount": len(shape.Edges) if not shape.isNull() else 0,
            "volumeMm3": actual_volume,
            "stepBBox": step_bbox,
        },
        "checks": checks,
        "failedChecks": [check["checkId"] for check in checks if check["status"] != "PASS"],
    }
    (OUTPUT_DIR / "step_roundtrip_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    try:
        report = validate()
        print(json.dumps({
            "status": report["status"],
            "reader": report["reader"],
            "statistics": report["statistics"],
            "failedChecks": report["failedChecks"],
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
        (OUTPUT_DIR / "logs" / "step-roundtrip-direct-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
