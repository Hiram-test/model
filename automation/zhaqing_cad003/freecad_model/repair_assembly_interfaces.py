#!/usr/bin/env python3
"""在初次实体生成后修正装配接口，并重新封存 FCStd/STEP。

为什么单独保留这一阶段：
- 初次显示实体有助于暴露“用体积搭接代替连接”的自动建模常见错误；
- 修正过程必须可见、可复核，不能静默覆盖失败经验；
- 最终模型中的横梁—纵梁、桥面—塔柱、柱—塔梁、塔梁—索鞍和
  吊杆—主缆接口均采用端面接触、显式间隙或通道，不保留非设计穿透。

本脚本打开已经保存的 FCStd，修改指定对象 Shape，保存第 08 阶段快照，
然后覆盖最终 FCStd 和 STEP。原 01–07 阶段快照保持不变，供过程复盘。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import FreeCAD as App
import Import
import Part


PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
STEP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-display.step"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def event(event_type: str, **payload: Any) -> None:
    record = {"timeUtc": utc_now(), "event": event_type, **payload}
    log_path = OUTPUT_DIR / "logs" / "build-events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)


def h_beam_x(
    x0: float,
    length: float,
    y_center: float,
    base_z: float,
    depth: float,
    width: float,
    web: float,
    flange: float,
) -> Part.Shape:
    bottom = Part.makeBox(length, width, flange, App.Vector(x0, y_center - width / 2.0, base_z))
    top = Part.makeBox(length, width, flange, App.Vector(x0, y_center - width / 2.0, base_z + depth - flange))
    web_shape = Part.makeBox(
        length,
        web,
        depth - 2.0 * flange,
        App.Vector(x0, y_center - web / 2.0, base_z + flange),
    )
    return Part.makeCompound([bottom, top, web_shape])


def cylinder_between(p1: App.Vector, p2: App.Vector, radius: float) -> Part.Shape:
    direction = p2.sub(p1)
    if direction.Length <= 1e-7:
        raise ValueError(f"零长度圆柱: {p1} -> {p2}")
    return Part.makeCylinder(radius, direction.Length, p1, direction)


def main_cable_z(g: dict[str, Any], x: float) -> float:
    span = g["span"]
    mid = g["mainCable"]["midspanZ"]
    rise = g["mainCable"]["mainspanRise"]
    u = x / span - 0.5
    return mid + 4.0 * rise * u * u


def shape_summary(shape: Part.Shape) -> dict[str, Any]:
    box = shape.BoundBox
    return {
        "shapeType": shape.ShapeType,
        "solids": len(shape.Solids),
        "volume": float(shape.Volume),
        "bbox": {
            "min": [box.XMin, box.YMin, box.ZMin],
            "max": [box.XMax, box.YMax, box.ZMax],
        },
    }


def set_shape(obj: App.DocumentObject, shape: Part.Shape, representation: str) -> dict[str, Any]:
    before = shape_summary(obj.Shape)
    obj.Shape = shape
    obj.Representation = representation
    after = shape_summary(shape)
    event("interface_repaired", object=obj.Name, before=before, after=after, representation=representation)
    return {"object": obj.Name, "before": before, "after": after, "representation": representation}


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
            **shape_summary(obj.Shape),
        })
    return rows


def repair() -> dict[str, Any]:
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    g = params["geometry"]
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    doc = App.openDocument(str(FCSTD_PATH))
    event("stage_start", stageId="08", title="assembly_interface_repair", purpose="消除显示实体中的非设计体积穿透")
    changes: list[dict[str, Any]] = []

    cross = g["crossbeam"]
    girder = g["longGirder"]
    stations = g["crossbeamStations"]
    girder_half_width = girder["width"] / 2.0
    girder_centers = (-g["girderSpacing"] / 2.0, g["girderSpacing"] / 2.0)
    tower_inner_face = g["cablePlaneY"] - g["tower"]["columnTransverse"] / 2.0

    # 1. 横梁在纵梁包围盒处断开；塔位横梁只延伸到两塔柱内侧面。
    for index, x in enumerate(stations, 1):
        obj = doc.getObject(f"Crossbeam_{index:02d}")
        if obj is None:
            raise KeyError(f"缺少横梁对象 {index}")
        x0 = x - cross["longitudinalWidth"] / 2.0
        if index in (1, len(stations)):
            y_segments = [(-tower_inner_face, tower_inner_face)]
        else:
            left, right = girder_centers
            y_segments = [
                (-cross["length"] / 2.0, left - girder_half_width),
                (left + girder_half_width, right - girder_half_width),
                (right + girder_half_width, cross["length"] / 2.0),
            ]
        pieces = [
            Part.makeBox(
                cross["longitudinalWidth"], y1 - y0, cross["depth"],
                App.Vector(x0, y0, -cross["depth"]),
            )
            for y0, y1 in y_segments
            if y1 - y0 > 1e-6
        ]
        changes.append(set_shape(obj, Part.makeCompound(pieces), "SEGMENTED_DISPLAY_ENVELOPE"))

    # 2. 首末跨纵梁缩回塔柱纵桥向端面。
    tower_face_offset = g["tower"]["columnLongitudinal"] / 2.0
    for side_name, y in (("L", g["girderSpacing"] / 2.0), ("R", -g["girderSpacing"] / 2.0)):
        for seg, (station_x0, station_x1) in enumerate(zip(stations[:-1], stations[1:]), 1):
            x0 = station_x0 + (tower_face_offset if seg == 1 else 0.0)
            x1 = station_x1 - (tower_face_offset if seg == len(stations) - 1 else 0.0)
            if x1 <= x0:
                raise ValueError(f"纵梁净长非正: {side_name}-{seg}")
            obj = doc.getObject(f"LongGirder_{side_name}_{seg:02d}")
            shape = h_beam_x(
                x0, x1 - x0, y, -girder["depth"],
                girder["depth"], girder["width"], girder["web"], girder["flange"],
            )
            changes.append(set_shape(obj, shape, "EXPLICIT_H_SECTION_TOWER_TRIMMED"))

    # 3. 塔区桥面板缩回塔柱端面，其余仍按站点净长显示。
    panel_width = g["deckPanelWidth"]
    thickness = g["deckPanelDisplayThickness"]
    panel_y0 = -1.5 * panel_width
    for bay, (station_x0, station_x1) in enumerate(zip(stations[:-1], stations[1:]), 1):
        clearance = min(160.0, (station_x1 - station_x0) * 0.04)
        x0 = station_x0 + clearance
        x1 = station_x1 - clearance
        if bay == 1:
            x0 = max(x0, tower_face_offset)
        if bay == len(stations) - 1:
            x1 = min(x1, g["span"] - tower_face_offset)
        if x1 <= x0:
            raise ValueError(f"桥面板净长非正: bay={bay}")
        for across in range(1, 4):
            obj = doc.getObject(f"DeckPanel_{bay:02d}_{across:02d}")
            y0 = panel_y0 + (across - 1) * panel_width
            shape = Part.makeBox(x1 - x0, panel_width, thickness, App.Vector(x0, y0, 0.0))
            changes.append(set_shape(obj, shape, "DISPLAY_ENVELOPE_TOWER_TRIMMED"))

    # 4. 塔柱止于塔顶横梁底面；横梁止于索鞍底板。
    tower = g["tower"]
    for tower_index, x in enumerate(g["towerStations"], 1):
        column_top_z = tower["cableZ"] - 1000.0
        for side_name, y in (("L", g["cablePlaneY"]), ("R", -g["cablePlaneY"])):
            obj = doc.getObject(f"TowerColumn_T{tower_index}_{side_name}")
            shape = Part.makeBox(
                tower["columnLongitudinal"], tower["columnTransverse"], column_top_z + 2500.0,
                App.Vector(x - tower["columnLongitudinal"] / 2.0, y - tower["columnTransverse"] / 2.0, -2500.0),
            )
            changes.append(set_shape(obj, shape, "DISPLAY_ENVELOPE_FACE_CONNECTED"))
        beam = doc.getObject(f"TowerTopBeam_T{tower_index}")
        beam_shape = Part.makeBox(
            tower["columnLongitudinal"], tower["capTransverse"], 500.0,
            App.Vector(x - tower["columnLongitudinal"] / 2.0, -tower["capTransverse"] / 2.0, tower["cableZ"] - 1000.0),
        )
        changes.append(set_shape(beam, beam_shape, "DISPLAY_ENVELOPE_FACE_CONNECTED"))

    # 5. 索鞍改为 U 形显示包络，中央通道不与主缆相交。
    saddle = g["saddle"]
    cable = g["mainCable"]
    for tower_index, x in enumerate(g["towerStations"], 1):
        for side_name, y in (("L", g["cablePlaneY"]), ("R", -g["cablePlaneY"])):
            plate = saddle["plateThickness"]
            z0 = cable["towerZ"] - 500.0
            base = Part.makeBox(
                saddle["length"], saddle["width"], plate,
                App.Vector(x - saddle["length"] / 2.0, y - saddle["width"] / 2.0, z0),
            )
            rail_height = 950.0
            left_rail = Part.makeBox(
                saddle["length"], plate, rail_height,
                App.Vector(x - saddle["length"] / 2.0, y - saddle["width"] / 2.0, z0 + plate),
            )
            right_rail = Part.makeBox(
                saddle["length"], plate, rail_height,
                App.Vector(x - saddle["length"] / 2.0, y + saddle["width"] / 2.0 - plate, z0 + plate),
            )
            obj = doc.getObject(f"Saddle_T{tower_index}_{side_name}")
            changes.append(set_shape(obj, Part.makeCompound([base, left_rail, right_rail]), "U_CHANNEL_DISPLAY_ENVELOPE"))

    # 6. 吊杆止于主缆下表面，不再插到主缆中心线。
    cable_radius = cable["equivalentDiameter"] / 2.0
    hanger_radius = g["hanger"]["diameter"] / 2.0
    for side_name, y in (("L", g["cablePlaneY"]), ("R", -g["cablePlaneY"])):
        for index, x in enumerate(g["hangerStations"], 1):
            p1 = App.Vector(x, y, 0.0)
            p2 = App.Vector(x, y, main_cable_z(g, x) - cable_radius)
            obj = doc.getObject(f"Hanger_{side_name}_{index:02d}")
            changes.append(set_shape(obj, cylinder_between(p1, p2, hanger_radius), "CIRCULAR_SOLID_SURFACE_TERMINATED"))

    doc.recompute()
    stage_path = OUTPUT_DIR / "stages" / "08_assembly_interface_repair.FCStd"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(stage_path))
    doc.saveAs(str(FCSTD_PATH))

    display_objects = sorted(
        [obj for obj in doc.Objects if obj.TypeId == "Part::Feature" and getattr(obj, "DisplayRole", "") != "REFERENCE"],
        key=lambda item: item.Name,
    )
    Import.export(display_objects, str(STEP_PATH))
    if not STEP_PATH.exists() or STEP_PATH.stat().st_size == 0:
        raise IOError("修正后 STEP 导出为空")

    manifest = rebuild_manifest(doc)
    (OUTPUT_DIR / "object_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS",
        "changedObjects": len(changes),
        "changes": changes,
        "stageSnapshot": {"path": str(stage_path.relative_to(OUTPUT_DIR)), "sha256": sha256_file(stage_path)},
        "finalFcstd": {"sha256": sha256_file(FCSTD_PATH), "bytes": FCSTD_PATH.stat().st_size},
        "finalStep": {"sha256": sha256_file(STEP_PATH), "bytes": STEP_PATH.stat().st_size},
    }
    (OUTPUT_DIR / "assembly_interface_repair_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    artifact_manifest_path = OUTPUT_DIR / "artifact_manifest.json"
    artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8")) if artifact_manifest_path.exists() else {}
    artifact_manifest["assemblyInterfaceRepair"] = {
        "scriptSha256": sha256_file(Path(__file__)),
        "reportSha256": sha256_file(OUTPUT_DIR / "assembly_interface_repair_report.json"),
        "changedObjects": len(changes),
    }
    artifact_manifest.setdefault("files", {})[FCSTD_PATH.name] = {"sha256": sha256_file(FCSTD_PATH), "bytes": FCSTD_PATH.stat().st_size}
    artifact_manifest["files"][STEP_PATH.name] = {"sha256": sha256_file(STEP_PATH), "bytes": STEP_PATH.stat().st_size}
    artifact_manifest_path.write_text(json.dumps(artifact_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    process_path = OUTPUT_DIR / "BUILD_PROCESS.md"
    with process_path.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## 08 装配接口修正\n\n"
            "独立复核发现，初次显示包络若直接相交，会重现 CAD-001 中‘用公共体积表达连接’的问题。"
            "本阶段保留早期快照作为失败经验，同时修正最终 FCStd/STEP：横梁在纵梁处断开、塔区桥面缩回柱面、"
            "柱梁和梁鞍采用端面接触、索鞍中央留出主缆通道、吊杆止于主缆下表面。"
            f"共修改 `{len(changes)}` 个对象，详细前后包围盒和体积见 `assembly_interface_repair_report.json`。\n"
        )

    event(
        "stage_complete",
        stageId="08",
        title="assembly_interface_repair",
        status="PASS",
        changedObjects=len(changes),
        snapshot=str(stage_path.relative_to(OUTPUT_DIR)),
        snapshotSha256=sha256_file(stage_path),
    )
    return report


def main() -> int:
    try:
        report = repair()
        print(json.dumps({
            "status": report["status"],
            "changedObjects": report["changedObjects"],
            "finalFcstd": report["finalFcstd"],
            "finalStep": report["finalStep"],
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
        (OUTPUT_DIR / "logs" / "assembly-repair-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
