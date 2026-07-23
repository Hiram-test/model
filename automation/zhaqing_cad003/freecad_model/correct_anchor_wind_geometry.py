#!/usr/bin/env python3
"""Rebuild the final main-anchor and wind-system geometry after evidence review.

The initial CAD-003 stages are intentionally retained because they expose the
mistakes that prompted this review. This script opens the saved FCStd and creates
an additional immutable stage in which:

* each main anchorage uses the SGT-26 10.50 m x 7.20 m stepped concrete profile,
  7.00 m total height, 2.20 m transverse recess and two 0.60 m raised strips;
* side-span main cables splay from the 5.50 m tower spacing to the 4.70 m anchor
  spacing and terminate at the drawing-controlled anchorage top elevation;
* wind-cable B points move to hanger/crossbeam Nos. 8 and 18 (26 m and 56 m),
  consistent with the direct plan-view label and the +/-15 m centre dimension;
* wind-anchor eye points use the 18.00 m longitudinal and 12.50 m transverse
  offsets plus the 4125.506/4129.04 elevations;
* each wind anchorage becomes a 220 x 200 x 150 cm base plus a
  120 x 100 x 150 cm pedestal, oriented along the cable plan direction.

Conflicting drawing notes and unresolved local hardware remain explicit in the
contract and do not become PASS merely because the display geometry is improved.
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
from typing import Any, Iterable

import FreeCAD as App
import Part

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


def bbox(shape: Part.Shape) -> dict[str, list[float]]:
    box = shape.BoundBox
    return {
        "min": [box.XMin, box.YMin, box.ZMin],
        "max": [box.XMax, box.YMax, box.ZMax],
        "size": [box.XLength, box.YLength, box.ZLength],
    }


def cylinder_between(p1: App.Vector, p2: App.Vector, radius: float) -> Part.Shape:
    direction = p2.sub(p1)
    if direction.Length <= 1e-7:
        raise ValueError(f"zero-length cylinder: {p1} -> {p2}")
    return Part.makeCylinder(radius, direction.Length, p1, direction)


def segmented_cable(points: Iterable[App.Vector], radius: float) -> Part.Shape:
    values = list(points)
    return Part.makeCompound([
        cylinder_between(a, b, radius) for a, b in zip(values[:-1], values[1:])
    ])


def outward_box(
    bridge_x: float,
    direction_sign: float,
    u0: float,
    length: float,
    y0: float,
    width: float,
    z0: float,
    height: float,
) -> Part.Shape:
    """Create a box where local +u points away from the bridge."""
    if direction_sign > 0:
        x0 = bridge_x + u0
    else:
        x0 = bridge_x - (u0 + length)
    return Part.makeBox(length, width, height, App.Vector(x0, y0, z0))


def main_anchor_shape(g: dict[str, Any], bridge_x: float, direction_sign: float) -> Part.Shape:
    anchor = g["mainAnchor"]
    length = float(anchor["longitudinal"])
    width = float(anchor["transverse"])
    top_z = float(anchor["topZ"])
    shoulder_top = top_z - float(anchor["shoulderTopDrop"])
    recess_bottom = shoulder_top - float(anchor["centralRecessDepthBelowShoulder"])
    regions = [float(value) for value in anchor["bottomRegionsFromBridge"]]
    drops = [float(value) for value in anchor["bottomDropsBelowTop"]]
    if len(regions) != 3 or len(drops) != 3:
        raise ValueError("mainAnchor bottom profile must contain three regions")
    if abs(sum(regions) - length) > 1e-6:
        raise ValueError("mainAnchor region chain does not close")

    pieces: list[Part.Shape] = []
    u = 0.0
    for region_length, drop in zip(regions, drops):
        bottom_z = top_z - drop
        height = recess_bottom - bottom_z
        if height <= 0.0:
            raise ValueError("mainAnchor lower-body height is non-positive")
        pieces.append(outward_box(
            bridge_x, direction_sign, u, region_length,
            -width / 2.0, width, bottom_z, height,
        ))
        u += region_length

    central = float(anchor["transversePartitions"][3])
    side_band_width = (width - central) / 2.0
    shoulder_height = shoulder_top - recess_bottom
    pieces.append(outward_box(
        bridge_x, direction_sign, 0.0, length,
        -width / 2.0, side_band_width, recess_bottom, shoulder_height,
    ))
    pieces.append(outward_box(
        bridge_x, direction_sign, 0.0, length,
        central / 2.0, side_band_width, recess_bottom, shoulder_height,
    ))

    strip_width = float(anchor["raisedStripWidth"])
    strip_height = top_z - shoulder_top
    for y_center in (-float(anchor["anchorCablePlaneY"]), float(anchor["anchorCablePlaneY"])):
        pieces.append(outward_box(
            bridge_x, direction_sign, 0.0, length,
            y_center - strip_width / 2.0, strip_width,
            shoulder_top, strip_height,
        ))

    shape = Part.makeCompound(pieces)
    if shape.isNull() or not shape.isValid():
        raise ValueError("constructed main-anchor compound is invalid")
    return shape


def wind_anchor_shape(wind_anchor: dict[str, Any], eye: App.Vector, angle_deg: float) -> Part.Shape:
    base = Part.makeBox(
        float(wind_anchor["baseLength"]),
        float(wind_anchor["baseWidth"]),
        float(wind_anchor["baseHeight"]),
        App.Vector(
            -float(wind_anchor["baseLength"]) / 2.0,
            -float(wind_anchor["baseWidth"]) / 2.0,
            -float(wind_anchor["totalHeight"]),
        ),
    )
    pedestal = Part.makeBox(
        float(wind_anchor["pedestalLength"]),
        float(wind_anchor["pedestalWidth"]),
        float(wind_anchor["pedestalHeight"]),
        App.Vector(
            -float(wind_anchor["pedestalLength"]) / 2.0,
            -float(wind_anchor["pedestalWidth"]) / 2.0,
            -float(wind_anchor["pedestalHeight"]),
        ),
    )
    shape = Part.makeCompound([base, pedestal])
    shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle_deg)
    shape.translate(eye)
    if shape.isNull() or not shape.isValid():
        raise ValueError("constructed wind-anchor compound is invalid")
    return shape


def ensure_property(obj: App.DocumentObject, kind: str, name: str) -> None:
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name)


def update_metadata(
    obj: App.DocumentObject,
    *,
    evidence_status: str,
    representation: str,
    assumption_ids: Iterable[str],
    control_data: dict[str, Any],
) -> None:
    obj.EvidenceStatus = evidence_status
    obj.Representation = representation
    assumptions = set(json.loads(getattr(obj, "AssumptionRefsJson", "[]")))
    assumptions.update(assumption_ids)
    obj.AssumptionRefsJson = json.dumps(sorted(assumptions), ensure_ascii=False)
    ensure_property(obj, "App::PropertyString", "GeometryControlJson")
    obj.GeometryControlJson = json.dumps(control_data, ensure_ascii=False, sort_keys=True)


def rebuild_manifest(doc: App.Document) -> list[dict[str, Any]]:
    rows = []
    for obj in doc.Objects:
        if obj.TypeId != "Part::Feature":
            continue
        rows.append({
            "name": obj.Name,
            "label": obj.Label,
            "componentGroupId": getattr(obj, "ComponentGroupId", ""),
            "sourceRefs": json.loads(getattr(obj, "SourceRefsJson", "[]")),
            "assumptionRefs": json.loads(getattr(obj, "AssumptionRefsJson", "[]")),
            "evidenceStatus": getattr(obj, "EvidenceStatus", ""),
            "representation": getattr(obj, "Representation", ""),
            "displayRole": getattr(obj, "DisplayRole", ""),
            "shapeType": obj.Shape.ShapeType,
            "solids": len(obj.Shape.Solids),
            "volume": float(obj.Shape.Volume),
            "bbox": bbox(obj.Shape),
            "geometryControl": json.loads(getattr(obj, "GeometryControlJson", "{}")),
        })
    return rows


def main_cable_z(g: dict[str, Any], x: float) -> float:
    span = float(g["span"])
    mid = float(g["mainCable"]["midspanZ"])
    rise = float(g["mainCable"]["mainspanRise"])
    u = x / span - 0.5
    return mid + 4.0 * rise * u * u


def rebuild() -> dict[str, Any]:
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(PARAMS_PATH)
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    g = params["geometry"]
    if "anchorWindReconciliation" not in params:
        raise ValueError("anchor/wind contract reconciliation has not been run")

    doc = App.openDocument(str(FCSTD_PATH))
    changes: list[dict[str, Any]] = []

    left_bridge_x = -float(g["sideSpan"])
    right_bridge_x = float(g["span"]) + float(g["sideSpan"])
    for name, bridge_x, direction in (
        ("MainAnchorage_Left", left_bridge_x, -1.0),
        ("MainAnchorage_Right", right_bridge_x, 1.0),
    ):
        obj = doc.getObject(name)
        if obj is None:
            raise KeyError(name)
        before = {"bbox": bbox(obj.Shape), "volume": float(obj.Shape.Volume)}
        obj.Shape = main_anchor_shape(g, bridge_x, direction)
        update_metadata(
            obj,
            evidence_status="ACCEPTED_ORTHOGRAPHIC_ENVELOPE_WITH_BOUNDED_INTERFACE",
            representation="STEPPED_RECESSED_DISPLAY_ENVELOPE",
            assumption_ids=["A-CAD-DISPLAY-001", "A-MAIN-ANCHOR-INTERFACE-002"],
            control_data={
                "bridgeFaceXmm": bridge_x,
                "outwardDirection": direction,
                "topZmm": g["mainAnchor"]["topZ"],
                "bottomRegionsFromBridgeMm": g["mainAnchor"]["bottomRegionsFromBridge"],
                "bottomDropsBelowTopMm": g["mainAnchor"]["bottomDropsBelowTop"],
                "transversePartitionsMm": g["mainAnchor"]["transversePartitions"],
            },
        )
        changes.append({
            "object": name,
            "kind": "main_anchor_profile",
            "before": before,
            "after": {"bbox": bbox(obj.Shape), "volume": float(obj.Shape.Volume)},
        })

    # Rebuild each complete main cable so that only the side spans splay from
    # the anchor's 4.70 m cable spacing to the tower's 5.50 m spacing.
    cable = g["mainCable"]
    cable_radius = float(cable["equivalentDiameter"]) / 2.0
    anchor_y = float(g["mainAnchor"]["anchorCablePlaneY"])
    tower_y = float(g["cablePlaneY"])
    anchor_z = float(g["mainAnchor"]["topZ"])
    for side_name, sign in (("L", 1.0), ("R", -1.0)):
        obj = doc.getObject(f"MainCable_{side_name}")
        if obj is None:
            raise KeyError(f"MainCable_{side_name}")
        points: list[App.Vector] = []
        side_segments = int(cable["segmentsSideSpan"])
        main_segments = int(cable["segmentsMainspan"])
        side_span = float(g["sideSpan"])
        span = float(g["span"])
        for i in range(side_segments + 1):
            t = i / side_segments
            points.append(App.Vector(
                left_bridge_x * (1.0 - t),
                sign * (anchor_y * (1.0 - t) + tower_y * t),
                anchor_z * (1.0 - t) + float(cable["towerZ"]) * t,
            ))
        for i in range(1, main_segments + 1):
            x = span * i / main_segments
            points.append(App.Vector(x, sign * tower_y, main_cable_z(g, x)))
        for i in range(1, side_segments + 1):
            t = i / side_segments
            points.append(App.Vector(
                span + side_span * t,
                sign * (tower_y * (1.0 - t) + anchor_y * t),
                float(cable["towerZ"]) * (1.0 - t) + anchor_z * t,
            ))
        before = {"bbox": bbox(obj.Shape), "volume": float(obj.Shape.Volume)}
        obj.Shape = segmented_cable(points, cable_radius)
        update_metadata(
            obj,
            evidence_status="ACCEPTED_MAINSPAN_WITH_RECONCILED_ANCHOR_DISPLAY_INTERFACE",
            representation="SEGMENTED_CIRCULAR_SOLID_WITH_SIDE_SPLAY",
            assumption_ids=["A-MAIN-ANCHOR-INTERFACE-002"],
            control_data={
                "leftAnchorPointMm": [left_bridge_x, sign * anchor_y, anchor_z],
                "leftTowerPointMm": [0.0, sign * tower_y, cable["towerZ"]],
                "rightTowerPointMm": [g["span"], sign * tower_y, cable["towerZ"]],
                "rightAnchorPointMm": [right_bridge_x, sign * anchor_y, anchor_z],
            },
        )
        changes.append({
            "object": obj.Name,
            "kind": "main_cable_anchor_splay",
            "before": before,
            "after": {"bbox": bbox(obj.Shape), "volume": float(obj.Shape.Volume)},
        })

    wind = g["windCable"]
    wind_anchor = g["windAnchor"]
    cable_counter = 0
    wind_controls: list[dict[str, Any]] = []
    for order, x_attach in enumerate(wind["attachStations"]):
        x_sign = -1.0 if order == 0 else 1.0
        for side_name, y_sign in (("L", 1.0), ("R", -1.0)):
            cable_counter += 1
            p_attach = App.Vector(
                float(x_attach),
                y_sign * float(g["cablePlaneY"]),
                float(wind["attachmentZ"]),
            )
            p_eye = App.Vector(
                float(x_attach) + x_sign * float(wind["candidateLongitudinalOffset"]),
                y_sign * (float(g["cablePlaneY"]) + float(wind["candidateLateralOffset"])),
                float(wind["anchorEyeZ"]),
            )
            vector = p_eye.sub(p_attach)
            plan_length = math.hypot(vector.x, vector.y)
            chord = vector.Length
            plan_angle = math.degrees(math.atan2(abs(vector.y), abs(vector.x)))
            vertical_angle = math.degrees(math.atan2(abs(vector.z), plan_length))

            cable_obj = doc.getObject(f"WindCable_{cable_counter:02d}")
            anchor_obj = doc.getObject(f"WindAnchorage_{cable_counter:02d}")
            if cable_obj is None or anchor_obj is None:
                raise KeyError(f"missing wind objects for {cable_counter}")
            cable_before = {"bbox": bbox(cable_obj.Shape), "volume": float(cable_obj.Shape.Volume)}
            cable_obj.Shape = cylinder_between(p_attach, p_eye, float(wind["diameter"]) / 2.0)
            update_metadata(
                cable_obj,
                evidence_status="DRAWING_OFFSETS_WITH_RECORDED_NUMBER_AND_ANGLE_CONFLICTS",
                representation="CIRCULAR_SOLID_DRAWING_CHORD",
                assumption_ids=["U-WIND-001", "C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001"],
                control_data={
                    "attachmentPointMm": [p_attach.x, p_attach.y, p_attach.z],
                    "anchorEyePointMm": [p_eye.x, p_eye.y, p_eye.z],
                    "planLengthMm": plan_length,
                    "straightChordLengthMm": chord,
                    "materialPlanLengthMm": wind["materialPlanLength"],
                    "planAngleDeg": plan_angle,
                    "verticalAngleDeg": vertical_angle,
                },
            )
            changes.append({
                "object": cable_obj.Name,
                "kind": "wind_cable_reposition",
                "before": cable_before,
                "after": {"bbox": bbox(cable_obj.Shape), "volume": float(cable_obj.Shape.Volume)},
            })

            # Orient the concrete pedestal's long direction toward the bridge.
            toward_bridge = p_attach.sub(p_eye)
            angle_deg = math.degrees(math.atan2(toward_bridge.y, toward_bridge.x))
            anchor_before = {"bbox": bbox(anchor_obj.Shape), "volume": float(anchor_obj.Shape.Volume)}
            anchor_obj.Shape = wind_anchor_shape(wind_anchor, p_eye, angle_deg)
            update_metadata(
                anchor_obj,
                evidence_status="ACCEPTED_STEPPED_ENVELOPE_WITH_BOUNDED_TERRAIN_COORDINATE",
                representation="STEPPED_BASE_AND_PEDESTAL_DISPLAY_ENVELOPE",
                assumption_ids=["U-WIND-001", "A-CAD-DISPLAY-001"],
                control_data={
                    "eyePointMm": [p_eye.x, p_eye.y, p_eye.z],
                    "orientationTowardBridgeDeg": angle_deg,
                    "baseDimensionsMm": [
                        wind_anchor["baseLength"], wind_anchor["baseWidth"], wind_anchor["baseHeight"],
                    ],
                    "pedestalDimensionsMm": [
                        wind_anchor["pedestalLength"], wind_anchor["pedestalWidth"], wind_anchor["pedestalHeight"],
                    ],
                },
            )
            changes.append({
                "object": anchor_obj.Name,
                "kind": "wind_anchor_stepped_profile",
                "before": anchor_before,
                "after": {"bbox": bbox(anchor_obj.Shape), "volume": float(anchor_obj.Shape.Volume)},
            })
            wind_controls.append({
                "cable": cable_obj.Name,
                "anchor": anchor_obj.Name,
                "hangerCrossbeamNumber": wind["attachHangerCrossbeamNumbers"][order],
                "attachmentPointMm": [p_attach.x, p_attach.y, p_attach.z],
                "anchorEyePointMm": [p_eye.x, p_eye.y, p_eye.z],
                "planLengthMm": plan_length,
                "straightChordLengthMm": chord,
                "planAngleDeg": plan_angle,
                "verticalAngleDeg": vertical_angle,
            })

    doc.recompute()
    stage_path = OUTPUT_DIR / "stages" / "10_anchor_wind_geometry_reconciliation.FCStd"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(stage_path))
    doc.saveAs(str(FCSTD_PATH))

    manifest = rebuild_manifest(doc)
    (OUTPUT_DIR / "object_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS_WITH_ENGINEERING_BLOCKERS",
        "changedObjectCount": len(changes),
        "changes": changes,
        "windControls": wind_controls,
        "mainAnchorControl": g["mainAnchor"],
        "stageSnapshot": {
            "path": str(stage_path.relative_to(OUTPUT_DIR)),
            "sha256": sha256_file(stage_path),
            "bytes": stage_path.stat().st_size,
        },
        "finalFcstd": {
            "sha256": sha256_file(FCSTD_PATH),
            "bytes": FCSTD_PATH.stat().st_size,
        },
        "engineeringBlockers": [
            "C-WIND-ATTACH-NUMBER-001",
            "C-WIND-HORIZONTAL-ANGLE-001",
            "U-WIND-001",
            "A-MAIN-ANCHOR-INTERFACE-002",
        ],
    }
    report_path = OUTPUT_DIR / "anchor_wind_geometry_correction_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_path = OUTPUT_DIR / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8")) if artifact_path.exists() else {}
    artifact["anchorWindGeometryCorrection"] = {
        "scriptSha256": sha256_file(Path(__file__)),
        "reportSha256": sha256_file(report_path),
        "changedObjectCount": len(changes),
        "stageSnapshotSha256": sha256_file(stage_path),
    }
    artifact.setdefault("files", {})[FCSTD_PATH.name] = {
        "sha256": sha256_file(FCSTD_PATH),
        "bytes": FCSTD_PATH.stat().st_size,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUTPUT_DIR / "BUILD_PROCESS.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## 10 锚碇与风缆复核修正\n\n"
            "复核确认原合同把主锚碇的 310 cm 水平分段误作总高度，并把风缆说明中的"
            "13/27号直接当作 B 点，未采用平面图直接标注的8/18号及桥中心正负15 m尺寸。"
            "本阶段不删除早期错误快照，而是新增最终修正快照：主锚碇改为10.50 m x 7.20 m、"
            "总高7.00 m的分级底面和横向槽形；风缆B点改到26 m/56 m站，锚点采用18.00 m、"
            "12.50 m和标高差控制；风缆锚座改为150 cm底座加150 cm台座。"
            "编号冲突、35度图注差异和地形坐标仍保留为BLOCKED。\n"
        )

    with (OUTPUT_DIR / "logs" / "build-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "timeUtc": utc_now(),
            "event": "stage_complete",
            "stageId": "10",
            "title": "anchor_wind_geometry_reconciliation",
            "status": "PASS_WITH_ENGINEERING_BLOCKERS",
            "changedObjects": len(changes),
            "snapshot": str(stage_path.relative_to(OUTPUT_DIR)),
            "snapshotSha256": sha256_file(stage_path),
        }, ensure_ascii=False, sort_keys=True) + "\n")

    App.closeDocument(doc.Name)
    return report


def main() -> int:
    try:
        report = rebuild()
        print(json.dumps({
            "status": report["status"],
            "changedObjectCount": report["changedObjectCount"],
            "windControls": report["windControls"],
            "stageSnapshot": report["stageSnapshot"],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "anchor-wind-geometry-correction-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
