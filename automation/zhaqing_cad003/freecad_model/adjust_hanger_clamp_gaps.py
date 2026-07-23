#!/usr/bin/env python3
"""为吊杆—主缆之间预留未建索夹/连接件的显示间隙。

第 08 阶段已经把吊杆端点移到主缆名义下表面，但主缆是倾斜圆柱分段，
吊杆本身也有 16 mm 半径；在吊杆站点附近，两实体仍可能产生小公共体积。

正式结构中吊杆不会靠实体互穿连接到主缆，而是通过索夹和连接件传力。当前资料
尚未闭合索夹制造几何，因此本阶段：
- 将每根吊杆显示实体顶部再下移 20 mm；
- 把这 20 mm 明确标为“未建索夹接口的显示间隙”，不是图纸净距；
- 保留吊杆中心线、站点和直径事实；
- 保存独立阶段快照及逐对象前后记录。

该处理只改善 CAD 装配表达，不关闭 G4/G5 的连接件与 representation contract 缺口。
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
import Part


PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
DISPLAY_GAP_MM = 20.0
ASSUMPTION_ID = "A-HANGER-CLAMP-DISPLAY-001"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main_cable_z(g: dict[str, Any], x: float) -> float:
    span = g["span"]
    mid = g["mainCable"]["midspanZ"]
    rise = g["mainCable"]["mainspanRise"]
    u = x / span - 0.5
    return mid + 4.0 * rise * u * u


def cylinder_between(p1: App.Vector, p2: App.Vector, radius: float) -> Part.Shape:
    direction = p2.sub(p1)
    if direction.Length <= 1e-7:
        raise ValueError(f"零长度吊杆: {p1} -> {p2}")
    return Part.makeCylinder(radius, direction.Length, p1, direction)


def shape_summary(shape: Part.Shape) -> dict[str, Any]:
    b = shape.BoundBox
    return {
        "volumeMm3": float(shape.Volume),
        "bbox": {
            "min": [b.XMin, b.YMin, b.ZMin],
            "max": [b.XMax, b.YMax, b.ZMax],
        },
    }


def rebuild_manifest(doc: App.Document) -> list[dict[str, Any]]:
    rows = []
    for obj in doc.Objects:
        if obj.TypeId != "Part::Feature":
            continue
        b = obj.Shape.BoundBox
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
            "bbox": {
                "min": [b.XMin, b.YMin, b.ZMin],
                "max": [b.XMax, b.YMax, b.ZMax],
                "size": [b.XLength, b.YLength, b.ZLength],
            },
        })
    return rows


def adjust() -> dict[str, Any]:
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    g = params["geometry"]
    doc = App.openDocument(str(FCSTD_PATH))

    cable_radius = g["mainCable"]["equivalentDiameter"] / 2.0
    hanger_radius = g["hanger"]["diameter"] / 2.0
    changes: list[dict[str, Any]] = []

    for side_name, y in (("L", g["cablePlaneY"]), ("R", -g["cablePlaneY"])):
        for index, x in enumerate(g["hangerStations"], 1):
            obj = doc.getObject(f"Hanger_{side_name}_{index:02d}")
            if obj is None:
                raise KeyError(f"缺少吊杆对象: {side_name}-{index:02d}")
            before = shape_summary(obj.Shape)
            cable_center_z = main_cable_z(g, x)
            top_z = cable_center_z - cable_radius - DISPLAY_GAP_MM
            p1 = App.Vector(x, y, 0.0)
            p2 = App.Vector(x, y, top_z)
            obj.Shape = cylinder_between(p1, p2, hanger_radius)
            obj.EvidenceStatus = "ACCEPTED_CENTERLINE_WITH_OMITTED_CLAMP"
            obj.Representation = "CIRCULAR_SOLID_WITH_CLAMP_DISPLAY_GAP"
            assumptions = json.loads(getattr(obj, "AssumptionRefsJson", "[]"))
            if ASSUMPTION_ID not in assumptions:
                assumptions.append(ASSUMPTION_ID)
            obj.AssumptionRefsJson = json.dumps(sorted(assumptions), ensure_ascii=False)
            after = shape_summary(obj.Shape)
            changes.append({
                "object": obj.Name,
                "stationXmm": x,
                "cableCenterZmm": cable_center_z,
                "equivalentCableRadiusMm": cable_radius,
                "displayGapMm": DISPLAY_GAP_MM,
                "hangerTopZmm": top_z,
                "before": before,
                "after": after,
            })

    doc.recompute()
    stage_path = OUTPUT_DIR / "stages" / "08B_hanger_clamp_display_gap.FCStd"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(stage_path))
    doc.saveAs(str(FCSTD_PATH))

    (OUTPUT_DIR / "object_manifest.json").write_text(
        json.dumps(rebuild_manifest(doc), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS",
        "assumption": {
            "assumptionId": ASSUMPTION_ID,
            "severity": "MAJOR",
            "statement": "吊杆实体顶部与主缆名义下表面保留 20 mm 显示间隙，用于代表未建模的索夹/连接件；该值不是图纸净距。",
            "effect": "避免以公共体积表达连接；吊杆—主缆真实连接刚度、偏心和局部构造仍未闭合。",
        },
        "changedObjectCount": len(changes),
        "changes": changes,
        "stageSnapshot": {
            "path": str(stage_path.relative_to(OUTPUT_DIR)),
            "sha256": sha256_file(stage_path),
            "bytes": stage_path.stat().st_size,
        },
        "finalFcstd": {
            "sha256": sha256_file(FCSTD_PATH),
            "bytes": FCSTD_PATH.stat().st_size,
        },
    }
    report_path = OUTPUT_DIR / "hanger_clamp_gap_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_path = OUTPUT_DIR / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8")) if artifact_path.exists() else {}
    artifact["hangerClampDisplayGap"] = {
        "scriptSha256": sha256_file(Path(__file__)),
        "reportSha256": sha256_file(report_path),
        "assumptionId": ASSUMPTION_ID,
        "changedObjectCount": len(changes),
        "displayGapMm": DISPLAY_GAP_MM,
    }
    artifact.setdefault("files", {})[FCSTD_PATH.name] = {
        "sha256": sha256_file(FCSTD_PATH),
        "bytes": FCSTD_PATH.stat().st_size,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUTPUT_DIR / "BUILD_PROCESS.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## 08B 吊杆—主缆索夹显示间隙\n\n"
            "公共体积审计发现，吊杆止于斜主缆名义下表面时，吊杆自身半径仍会与相邻斜索段产生小体积交叠。"
            "正式连接应由索夹和连接件承担，不能靠实体互穿表达。"
            f"因此 50 根吊杆顶部统一保留 `{DISPLAY_GAP_MM:.1f} mm` 显示间隙，并登记 `{ASSUMPTION_ID}`。"
            "该间隙不是图纸尺寸，真实连接接口仍保持工程 Gate 阻断。\n"
        )

    with (OUTPUT_DIR / "logs" / "build-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "timeUtc": utc_now(),
            "event": "stage_complete",
            "stageId": "08B",
            "title": "hanger_clamp_display_gap",
            "status": "PASS",
            "changedObjects": len(changes),
            "assumptionId": ASSUMPTION_ID,
            "displayGapMm": DISPLAY_GAP_MM,
            "snapshot": str(stage_path.relative_to(OUTPUT_DIR)),
            "snapshotSha256": sha256_file(stage_path),
        }, ensure_ascii=False, sort_keys=True) + "\n")

    App.closeDocument(doc.Name)
    return report


def main() -> int:
    try:
        report = adjust()
        print(json.dumps({
            "status": report["status"],
            "changedObjectCount": report["changedObjectCount"],
            "assumptionId": report["assumption"]["assumptionId"],
            "displayGapMm": DISPLAY_GAP_MM,
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
        (OUTPUT_DIR / "logs" / "hanger-clamp-gap-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
