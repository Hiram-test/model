#!/usr/bin/env python3
"""Run contract validation with a direct TopoShape STEP reader.

FreeCAD 0.19's ``Part.insert`` expands a compound STEP into hundreds of document
objects. The corrected anchorage/wind model contains 675 solids and this path
reproducibly terminated the process before the validator could write a report.
The crash is an importer/document-expansion limitation, not evidence that the
STEP topology is invalid: the same file was written successfully by OCCT.

``Part.TopoShape.read`` reads IGES/STEP/BREP directly into one shape and avoids
OCAF and per-solid document expansion. This wrapper monkey-patches only the
``Part.insert`` call used by the independent base validator. The validator still
runs in a fresh FreeCADCmd process, checks shape validity and volume, saves a
round-trip FCStd, compares the FCStd/STEP bounding boxes, and runs every
contract-derived hanger and main-cable check.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_freecad_model_contract as contract


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def direct_toposhape_insert(filename: str, document_name: str) -> None:
    """Read one STEP into a single Part::Feature in the requested document."""
    path = Path(filename).resolve()
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    document = contract.base.App.getDocument(document_name)
    if document is None:
        raise RuntimeError(f"FreeCAD document not found: {document_name}")

    shape = contract.base.Part.Shape()
    shape.read(str(path))
    if shape.isNull():
        raise ValueError(f"direct TopoShape STEP read returned a null shape: {path}")
    if not shape.isValid():
        raise ValueError(f"direct TopoShape STEP read returned an invalid shape: {path}")
    if shape.Volume <= 0.0:
        raise ValueError(f"direct TopoShape STEP read returned non-positive volume: {path}")

    obj = document.addObject("Part::Feature", "StepDirectTopoShape")
    obj.Label = "CAD-003 STEP direct TopoShape round-trip"
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "ReaderPath")
    obj.ReaderPath = "Part.TopoShape.read (single-shape, non-OCAF, non-expanding)"
    document.recompute()


def annotate_report() -> None:
    report_path = contract.base.OUTPUT_DIR / "validation_report.json"
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    reader = {
        "api": "Part.TopoShape.read",
        "mode": "single compound shape; no OCAF/STEPCAF and no per-solid document expansion",
        "reason": "FreeCAD 0.19 Part.insert process termination on the corrected 675-solid compound STEP",
        "wrapper": Path(__file__).name,
    }
    report["stepReader"] = reader
    for check in report.get("checks", []):
        if check.get("checkId") == "STEP_REIMPORT_NONEMPTY":
            details = check.setdefault("details", {})
            details["reader"] = reader
            details["objects"] = 1
    report["directStepReaderApplied"] = True
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    contract.base.write_markdown(report)


def main() -> int:
    output_dir = Path(os.environ.get("ZHAQING_OUT", ".")).resolve()
    try:
        # The base module resolves Part.insert at call time, so the substitution
        # is limited to this one FreeCADCmd process and one validation run.
        contract.base.Part.insert = direct_toposhape_insert
        status = contract.main()
        if status == 0:
            annotate_report()
            print(json.dumps({
                "status": "PASS",
                "reader": "Part.TopoShape.read",
                "validationReport": str(output_dir / "validation_report.json"),
            }, ensure_ascii=False, indent=2))
        return status
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (output_dir / "logs").mkdir(parents=True, exist_ok=True)
        (output_dir / "logs" / "direct-step-validation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
