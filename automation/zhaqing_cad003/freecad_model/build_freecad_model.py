#!/usr/bin/env python3
"""在 FreeCAD 虚拟机中逐阶段建立扎青吊桥 CAD-003。

运行方式（由 run_freecad_pipeline.sh 设置环境变量）：
    freecadcmd build_freecad_model.py

设计边界：
- 数值只来自 frozen_model_contract.json；本脚本不读取 DWG，也不允许语言模型
  在建模阶段临时补数值。
- 生成的是带证据属性的整体装配/显示模型，制造孔、钢筋、螺栓和局部节点不建模。
- 风缆锚点、基础桩长和部分锚固接口仍为显式有界假定，工程发布状态保持 BLOCKED。
- 每个阶段保存 FCStd 快照、JSONL 事件和对象清单，失败不会覆盖旧快照。
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
import Import


PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bbox_dict(shape: Part.Shape) -> dict[str, Any] | None:
    if shape.isNull():
        return None
    b = shape.BoundBox
    return {
        "min": [b.XMin, b.YMin, b.ZMin],
        "max": [b.XMax, b.YMax, b.ZMax],
        "size": [b.XLength, b.YLength, b.ZLength]
    }


class BuildRecorder:
    """把每个建模动作写入不可变 JSONL，并生成面向人的过程说明。"""

    def __init__(self, output_dir: Path, document: App.Document):
        self.output_dir = output_dir
        self.document = document
        self.log_path = output_dir / "logs" / "build-events.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.stage_dir = output_dir / "stages"
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        self.stages: list[dict[str, Any]] = []
        self._stage_start_count = 0

    def event(self, event_type: str, **payload: Any) -> None:
        record = {"timeUtc": utc_now(), "event": event_type, **payload}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)

    def start_stage(self, stage_id: str, title: str, purpose: str) -> None:
        self._stage_start_count = len(self.document.Objects)
        self.event("stage_start", stageId=stage_id, title=title, purpose=purpose)

    def complete_stage(self, stage_id: str, title: str, note: str) -> None:
        self.document.recompute()
        snapshot = self.stage_dir / f"{stage_id}_{title}.FCStd"
        self.document.saveAs(str(snapshot))
        new_count = len(self.document.Objects) - self._stage_start_count
        stage = {
            "stageId": stage_id,
            "title": title,
            "status": "PASS",
            "newDocumentObjects": new_count,
            "totalDocumentObjects": len(self.document.Objects),
            "snapshot": str(snapshot.relative_to(self.output_dir)),
            "snapshotSha256": sha256_file(snapshot),
            "note": note
        }
        self.stages.append(stage)
        self.event("stage_complete", **stage)

    def write_process_markdown(self, params_sha: str) -> None:
        lines = [
            "# 扎青吊桥 CAD-003 FreeCAD 虚拟机建模过程",
            "",
            f"- 运行时间（UTC）：`{utc_now()}`",
            f"- FreeCAD：`{'.'.join(App.Version()[:3])}`",
            f"- 参数合同 SHA-256：`{params_sha}`",
            f"- 建模脚本 SHA-256：`{sha256_file(Path(__file__))}`",
            "- 技术用途：整体装配、证据定位、STEP 交换和后续 FEM 几何接口准备。",
            "- 工程发布：`BLOCKED`，详见 `gate_receipt.json` 与参数合同中的有界假定。",
            "",
            "## 阶段记录",
            "",
            "| 阶段 | 内容 | 新增对象 | 快照 | 说明 |",
            "|---|---|---:|---|---|"
        ]
        for stage in self.stages:
            lines.append(
                f"| {stage['stageId']} | {stage['title']} | {stage['newDocumentObjects']} | "
                f"`{stage['snapshot']}` | {stage['note']} |"
            )
        lines += [
            "",
            "## 解释原则",
            "",
            "1. `REFERENCE` 对象是中心线、站点和候选接口，不导出 STEP。",
            "2. `DISPLAY_ENVELOPE` 对象保留图纸控制外包络，不代表制造细节。",
            "3. 每个对象均带 `ComponentGroupId`、`SourceRefsJson`、`EvidenceStatus`、",
            "   `Representation` 和 `AssumptionRefsJson` 属性。",
            "4. STEP 由独立校验脚本重新导入并比较包围盒；脚本退出码为零仍不等于工程 Gate 通过。"
        ]
        (self.output_dir / "BUILD_PROCESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class ModelBuilder:
    def __init__(self, params: dict[str, Any], output_dir: Path):
        self.params = params
        self.g = params["geometry"]
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.doc = App.newDocument("Zhaqing_CAD_003")
        self.rec = BuildRecorder(output_dir, self.doc)
        self.groups: dict[str, App.DocumentObject] = {}
        self.display_objects: list[App.DocumentObject] = []
        self.reference_objects: list[App.DocumentObject] = []
        self.object_manifest: list[dict[str, Any]] = []
        self._create_groups_and_metadata()

    def _create_groups_and_metadata(self) -> None:
        for name, label in [
            ("Metadata", "00 元数据与假定"),
            ("ReferenceSkeleton", "01 权威参考骨架"),
            ("DeckSystem", "02 桥面与梁系"),
            ("TowerFoundationSystem", "03 索塔与基础"),
            ("CableSystem", "04 主缆、索鞍与吊杆"),
            ("AnchorageSystem", "05 主缆锚碇"),
            ("WindSystem", "06 风缆与风缆锚碇（有界候选）")
        ]:
            group = self.doc.addObject("App::DocumentObjectGroup", name)
            group.Label = label
            self.groups[name] = group

        metadata = self.doc.addObject("App::FeaturePython", "ModelMetadata")
        metadata.Label = "CAD-003 模型元数据"
        metadata.addProperty("App::PropertyString", "ProjectId").ProjectId = self.params["projectId"]
        metadata.addProperty("App::PropertyString", "RunId").RunId = self.params["runId"]
        metadata.addProperty("App::PropertyString", "CoordinateSystemId").CoordinateSystemId = self.params["coordinateSystem"]["id"]
        metadata.addProperty("App::PropertyString", "EngineeringReleaseStatus").EngineeringReleaseStatus = self.params["engineeringReleaseStatus"]
        metadata.addProperty("App::PropertyString", "BlockingIssueIdsJson").BlockingIssueIdsJson = json.dumps(self.params["blockingIssueIds"], ensure_ascii=False)
        metadata.addProperty("App::PropertyString", "BoundedAssumptionsJson").BoundedAssumptionsJson = json.dumps(self.params["boundedAssumptions"], ensure_ascii=False)
        metadata.addProperty("App::PropertyString", "ParameterContractSha256").ParameterContractSha256 = sha256_file(PARAMS_PATH)
        metadata.addProperty("App::PropertyString", "FreeCADVersion").FreeCADVersion = ".".join(App.Version()[:3])
        self.groups["Metadata"].addObject(metadata)

    def add_feature(
        self,
        name: str,
        label: str,
        shape: Part.Shape,
        group: str,
        component_group_id: str,
        source_refs: Iterable[str],
        evidence_status: str,
        representation: str,
        assumption_refs: Iterable[str] = (),
        display_role: str = "DISPLAY"
    ) -> App.DocumentObject:
        if self.doc.getObject(name) is not None:
            raise ValueError(f"重复对象 Name: {name}")
        obj = self.doc.addObject("Part::Feature", name)
        obj.Label = label
        obj.Shape = shape
        obj.addProperty("App::PropertyString", "StableObjectId").StableObjectId = f"CAD003::{name}"
        obj.addProperty("App::PropertyString", "ComponentGroupId").ComponentGroupId = component_group_id
        obj.addProperty("App::PropertyString", "SourceRefsJson").SourceRefsJson = json.dumps(sorted(set(source_refs)), ensure_ascii=False)
        obj.addProperty("App::PropertyString", "EvidenceStatus").EvidenceStatus = evidence_status
        obj.addProperty("App::PropertyString", "Representation").Representation = representation
        obj.addProperty("App::PropertyString", "AssumptionRefsJson").AssumptionRefsJson = json.dumps(sorted(set(assumption_refs)), ensure_ascii=False)
        obj.addProperty("App::PropertyString", "DisplayRole").DisplayRole = display_role
        self.groups[group].addObject(obj)
        if display_role == "REFERENCE":
            self.reference_objects.append(obj)
        else:
            self.display_objects.append(obj)
        self.object_manifest.append({
            "name": name,
            "label": label,
            "group": group,
            "componentGroupId": component_group_id,
            "sourceRefs": sorted(set(source_refs)),
            "assumptionRefs": sorted(set(assumption_refs)),
            "evidenceStatus": evidence_status,
            "representation": representation,
            "displayRole": display_role,
            "shapeType": shape.ShapeType,
            "solids": len(shape.Solids),
            "volume": float(shape.Volume),
            "bbox": bbox_dict(shape)
        })
        self.rec.event(
            "object_created",
            name=name,
            group=group,
            componentGroupId=component_group_id,
            displayRole=display_role,
            solids=len(shape.Solids),
            volume=float(shape.Volume)
        )
        return obj

    @staticmethod
    def line(p1: tuple[float, float, float], p2: tuple[float, float, float]) -> Part.Shape:
        return Part.makeLine(App.Vector(*p1), App.Vector(*p2))

    @staticmethod
    def cylinder_between(p1: App.Vector, p2: App.Vector, radius: float) -> Part.Shape:
        direction = p2.sub(p1)
        length = direction.Length
        if length <= 1e-7:
            raise ValueError(f"零长度圆柱: {p1} -> {p2}")
        return Part.makeCylinder(radius, length, p1, direction)

    @classmethod
    def segmented_cable(cls, points: list[App.Vector], radius: float) -> Part.Shape:
        solids = [cls.cylinder_between(a, b, radius) for a, b in zip(points[:-1], points[1:])]
        return Part.makeCompound(solids)

    @staticmethod
    def h_beam_x(
        x0: float,
        length: float,
        y_center: float,
        base_z: float,
        depth: float,
        width: float,
        web: float,
        flange: float
    ) -> Part.Shape:
        bottom = Part.makeBox(length, width, flange, App.Vector(x0, y_center - width / 2.0, base_z))
        top = Part.makeBox(length, width, flange, App.Vector(x0, y_center - width / 2.0, base_z + depth - flange))
        web_shape = Part.makeBox(
            length,
            web,
            depth - 2.0 * flange,
            App.Vector(x0, y_center - web / 2.0, base_z + flange)
        )
        return Part.makeCompound([bottom, top, web_shape])

    def stage_01_reference_skeleton(self) -> None:
        self.rec.start_stage("01", "reference_skeleton", "建立桥轴、横梁站点、索面和锚固/风缆候选接口。")
        span = self.g["span"]
        deck_y = self.g["deckWidth"] / 2.0
        tower_z = self.g["tower"]["cableZ"]
        side = self.g["sideSpan"]

        self.add_feature(
            "BridgeAxis", "桥轴线 X=0~82m", self.line((0, 0, 0), (span, 0, 0)),
            "ReferenceSkeleton", "CG-REFERENCE-AXIS",
            [self.params["acceptedFacts"]["SPAN_M"]["sourceRef"]],
            "ACCEPTED", "REFERENCE_LINE", display_role="REFERENCE"
        )
        station_edges = [
            self.line((x, -deck_y - 250, 0), (x, deck_y + 250, 0))
            for x in self.g["crossbeamStations"]
        ]
        self.add_feature(
            "CrossbeamStations", "27 道横梁站点", Part.makeCompound(station_edges),
            "ReferenceSkeleton", "CG-REFERENCE-STATIONS",
            [
                self.params["acceptedFacts"]["SPAN_M"]["sourceRef"],
                self.params["acceptedFacts"]["HANGER_ZONE_M"]["sourceRef"],
                self.params["acceptedFacts"]["END_ZONE_M"]["sourceRef"]
            ],
            "ACCEPTED_DERIVED", "REFERENCE_LINES", display_role="REFERENCE"
        )
        cable_planes = [self.line((-side, y, -1200), (span + side, y, -1200)) for y in (-deck_y, deck_y)]
        self.add_feature(
            "CablePlaneReferences", "左右主缆索面参考", Part.makeCompound(cable_planes),
            "ReferenceSkeleton", "CG-REFERENCE-CABLE-PLANES",
            [self.params["acceptedFacts"]["DECK_WIDTH_CM"]["sourceRef"]],
            "ACCEPTED_DERIVED", "REFERENCE_LINES", display_role="REFERENCE"
        )
        control_points = []
        for x in (0.0, span / 2.0, span):
            z = tower_z if x != span / 2.0 else self.g["mainCable"]["midspanZ"]
            for y in (-deck_y, deck_y):
                control_points.append(Part.makeSphere(80.0, App.Vector(x, y, z)))
        self.add_feature(
            "CableControlPoints", "主缆塔顶与跨中控制点", Part.makeCompound(control_points),
            "ReferenceSkeleton", "CG-REFERENCE-CABLE-CONTROL",
            [
                self.params["acceptedFacts"]["TOWER_CABLE_HEIGHT_CM"]["sourceRef"],
                self.params["acceptedFacts"]["CABLE_MAINSPAN_RISE_CM"]["sourceRef"]
            ],
            "ACCEPTED_DERIVED", "REFERENCE_POINTS", display_role="REFERENCE"
        )
        self.rec.complete_stage("01", "reference_skeleton", "所有后续实体均引用本坐标系和站点，不从显示几何反量尺寸。")

    def stage_02_deck_system(self) -> None:
        self.rec.start_stage("02", "deck_system", "生成 27 道横梁、52 段 HW 纵梁和 78 块桥面板显示实体。")
        cross = self.g["crossbeam"]
        girder = self.g["longGirder"]
        station_ref = [
            self.params["acceptedFacts"]["SPAN_M"]["sourceRef"],
            self.params["acceptedFacts"]["HANGER_ZONE_M"]["sourceRef"],
            self.params["acceptedFacts"]["END_ZONE_M"]["sourceRef"]
        ]
        cross_refs = [
            self.params["acceptedFacts"]["CROSSBEAM_LENGTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["CROSSBEAM_DEPTH_CM"]["sourceRef"],
            self.params["acceptedFacts"]["CROSSBEAM_LONGITUDINAL_WIDTH_MM"]["sourceRef"],
            *station_ref
        ]
        for index, x in enumerate(self.g["crossbeamStations"], 1):
            shape = Part.makeBox(
                cross["longitudinalWidth"], cross["length"], cross["depth"],
                App.Vector(x - cross["longitudinalWidth"] / 2.0, -cross["length"] / 2.0, -cross["depth"])
            )
            self.add_feature(
                f"Crossbeam_{index:02d}", f"横梁 {index:02d}", shape,
                "DeckSystem", "CG-CROSSBEAM", cross_refs,
                "ACCEPTED_ENVELOPE", "DISPLAY_ENVELOPE", ["A-CAD-DISPLAY-001"]
            )

        girder_refs = [
            self.params["acceptedFacts"]["LONG_GIRDER_DEPTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["LONG_GIRDER_WIDTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["LONG_GIRDER_WEB_MM"]["sourceRef"],
            self.params["acceptedFacts"]["LONG_GIRDER_FLANGE_MM"]["sourceRef"],
            self.params["acceptedFacts"]["GIRDER_SPACING_CM"]["sourceRef"],
            *station_ref
        ]
        half_spacing = self.g["girderSpacing"] / 2.0
        stations = self.g["crossbeamStations"]
        for side_name, y in (("L", half_spacing), ("R", -half_spacing)):
            for seg, (x0, x1) in enumerate(zip(stations[:-1], stations[1:]), 1):
                shape = self.h_beam_x(
                    x0, x1 - x0, y, -girder["depth"],
                    girder["depth"], girder["width"], girder["web"], girder["flange"]
                )
                self.add_feature(
                    f"LongGirder_{side_name}_{seg:02d}", f"纵梁 {side_name}-{seg:02d}", shape,
                    "DeckSystem", "CG-LONG-GIRDER", girder_refs,
                    "ACCEPTED_ENVELOPE", "EXPLICIT_H_SECTION", ["A-CAD-DISPLAY-001"]
                )

        panel_refs = [
            self.params["acceptedFacts"]["DECK_PANEL_WIDTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["DECK_PANEL_SOURCE_LENGTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["DECK_PANEL_DISPLAY_THICKNESS_MM"]["sourceRef"],
            self.params["acceptedFacts"]["GIRDER_SPACING_CM"]["sourceRef"],
            *station_ref
        ]
        panel_width = self.g["deckPanelWidth"]
        thickness = self.g["deckPanelDisplayThickness"]
        panel_y0 = -1.5 * panel_width
        for bay, (x0, x1) in enumerate(zip(stations[:-1], stations[1:]), 1):
            clearance = min(160.0, (x1 - x0) * 0.04)
            panel_length = x1 - x0 - 2.0 * clearance
            for across in range(3):
                y0 = panel_y0 + across * panel_width
                shape = Part.makeBox(panel_length, panel_width, thickness, App.Vector(x0 + clearance, y0, 0.0))
                self.add_feature(
                    f"DeckPanel_{bay:02d}_{across + 1:02d}", f"桥面板 bay {bay:02d}-{across + 1}", shape,
                    "DeckSystem", "CG-DECK-PANEL", panel_refs,
                    "ACCEPTED_ENVELOPE_WITH_BOUNDS", "DISPLAY_ENVELOPE", ["A-CAD-DISPLAY-001"]
                )
        self.rec.complete_stage("02", "deck_system", "梁系中心距、桥宽和站点闭合；板件仅表达整体外包络。")

    def stage_03_tower_and_foundations(self) -> None:
        self.rec.start_stage("03", "tower_foundations", "生成两座双柱索塔、塔顶横梁、承台和显示桩基。")
        tower = self.g["tower"]
        cable_y = self.g["cablePlaneY"]
        tower_refs = [
            self.params["acceptedFacts"]["TOWER_CABLE_HEIGHT_CM"]["sourceRef"],
            self.params["acceptedFacts"]["TOWER_CAP_TRANSVERSE_CM"]["sourceRef"],
            self.params["acceptedFacts"]["TOWER_CAP_LONGITUDINAL_CM"]["sourceRef"],
            self.params["acceptedFacts"]["TOWER_COLUMN_LONGITUDINAL_CM"]["sourceRef"],
            self.params["acceptedFacts"]["TOWER_COLUMN_TRANSVERSE_CM"]["sourceRef"]
        ]
        pile_refs = [self.params["acceptedFacts"]["TOWER_PILE_DIAMETER_CM"]["sourceRef"]]
        for tower_index, x in enumerate(self.g["towerStations"], 1):
            cap = Part.makeBox(
                tower["capLongitudinal"], tower["capTransverse"], 1500.0,
                App.Vector(x - tower["capLongitudinal"] / 2.0, -tower["capTransverse"] / 2.0, -4000.0)
            )
            self.add_feature(
                f"TowerCap_T{tower_index}", f"索塔 T{tower_index} 承台", cap,
                "TowerFoundationSystem", "CG-TOWER-CAP", tower_refs,
                "ACCEPTED_ENVELOPE_WITH_BOUNDS", "DISPLAY_ENVELOPE",
                ["A-CAD-DISPLAY-001", "A-TOWER-FOUNDATION-001"]
            )
            for side_name, y in (("L", cable_y), ("R", -cable_y)):
                column = Part.makeBox(
                    tower["columnLongitudinal"], tower["columnTransverse"],
                    tower["cableZ"] + 2500.0 - 800.0,
                    App.Vector(
                        x - tower["columnLongitudinal"] / 2.0,
                        y - tower["columnTransverse"] / 2.0,
                        -2500.0
                    )
                )
                self.add_feature(
                    f"TowerColumn_T{tower_index}_{side_name}", f"索塔 T{tower_index} 柱 {side_name}", column,
                    "TowerFoundationSystem", "CG-TOWER-COLUMN", tower_refs,
                    "ACCEPTED_ENVELOPE", "DISPLAY_ENVELOPE", ["A-CAD-DISPLAY-001"]
                )
            top_beam = Part.makeBox(
                tower["columnLongitudinal"], tower["capTransverse"], 800.0,
                App.Vector(
                    x - tower["columnLongitudinal"] / 2.0,
                    -tower["capTransverse"] / 2.0,
                    tower["cableZ"] - 800.0
                )
            )
            self.add_feature(
                f"TowerTopBeam_T{tower_index}", f"索塔 T{tower_index} 塔顶横梁", top_beam,
                "TowerFoundationSystem", "CG-TOWER-TOP-BEAM", tower_refs,
                "ACCEPTED_ENVELOPE", "DISPLAY_ENVELOPE", ["A-CAD-DISPLAY-001"]
            )
            pile_positions = [
                (x - 1000.0, -1800.0), (x - 1000.0, 1800.0),
                (x + 1000.0, -1800.0), (x + 1000.0, 1800.0)
            ]
            for p_index, (px, py) in enumerate(pile_positions, 1):
                pile = Part.makeCylinder(tower["pileDiameter"] / 2.0, 8000.0, App.Vector(px, py, -12000.0))
                self.add_feature(
                    f"TowerPile_T{tower_index}_{p_index}", f"索塔 T{tower_index} 显示桩 {p_index}", pile,
                    "TowerFoundationSystem", "CG-TOWER-PILE", pile_refs,
                    "BOUNDED_ASSUMPTION", "DISPLAY_ENVELOPE", ["A-TOWER-FOUNDATION-001"]
                )
        self.rec.complete_stage("03", "tower_foundations", "塔顶索面位置采用已接受标高；桩长和承台底标高显式标记为假定。")

    def main_cable_z(self, x: float) -> float:
        span = self.g["span"]
        mid = self.g["mainCable"]["midspanZ"]
        rise = self.g["mainCable"]["mainspanRise"]
        u = x / span - 0.5
        return mid + 4.0 * rise * u * u

    def stage_04_saddles_main_cables_hangers(self) -> None:
        self.rec.start_stage("04", "cable_system", "生成 4 个索鞍、2 条分段实体主缆和 50 根吊杆。")
        span = self.g["span"]
        side_span = self.g["sideSpan"]
        cable_y = self.g["cablePlaneY"]
        cable = self.g["mainCable"]
        saddle = self.g["saddle"]
        cable_radius = cable["equivalentDiameter"] / 2.0
        cable_refs = [
            self.params["acceptedFacts"]["CABLE_FORM_COEFFICIENT"]["sourceRef"],
            self.params["acceptedFacts"]["CABLE_MAINSPAN_RISE_CM"]["sourceRef"],
            self.params["acceptedFacts"]["MAIN_CABLE_WIRE_COUNT"]["sourceRef"],
            self.params["acceptedFacts"]["MAIN_CABLE_WIRE_DIAM_MM"]["sourceRef"],
            self.params["acceptedFacts"]["SIDE_SPAN_M"]["sourceRef"]
        ]
        saddle_refs = [
            self.params["acceptedFacts"]["SADDLE_WIDTH_MM"]["sourceRef"],
            self.params["acceptedFacts"]["SADDLE_PLATE_THICKNESS_MM"]["sourceRef"],
            self.params["acceptedFacts"]["SADDLE_LENGTH_MM"]["sourceRef"]
        ]
        for tower_index, x in enumerate(self.g["towerStations"], 1):
            for side_name, y in (("L", cable_y), ("R", -cable_y)):
                shape = Part.makeBox(
                    saddle["length"], saddle["width"], 300.0,
                    App.Vector(x - saddle["length"] / 2.0, y - saddle["width"] / 2.0, cable["towerZ"] - 150.0)
                )
                self.add_feature(
                    f"Saddle_T{tower_index}_{side_name}", f"索鞍 T{tower_index}-{side_name}", shape,
                    "CableSystem", "CG-SADDLE", saddle_refs,
                    "ACCEPTED_ENVELOPE", "DISPLAY_ENVELOPE", ["A-CAD-DISPLAY-001"]
                )

        for side_name, y in (("L", cable_y), ("R", -cable_y)):
            points: list[App.Vector] = []
            for i in range(cable["segmentsSideSpan"] + 1):
                t = i / cable["segmentsSideSpan"]
                points.append(App.Vector(-side_span * (1.0 - t), y, -1200.0 * (1.0 - t) + cable["towerZ"] * t))
            for i in range(1, cable["segmentsMainspan"] + 1):
                x = span * i / cable["segmentsMainspan"]
                points.append(App.Vector(x, y, self.main_cable_z(x)))
            for i in range(1, cable["segmentsSideSpan"] + 1):
                t = i / cable["segmentsSideSpan"]
                points.append(App.Vector(span + side_span * t, y, cable["towerZ"] * (1.0 - t) - 1200.0 * t))
            shape = self.segmented_cable(points, cable_radius)
            self.add_feature(
                f"MainCable_{side_name}", f"主缆 {side_name}", shape,
                "CableSystem", "CG-MAIN-CABLE", cable_refs,
                "ACCEPTED_MAINSPAN_WITH_BOUNDED_SIDE_INTERFACE", "SEGMENTED_CIRCULAR_SOLID",
                ["A-MAIN-ANCHOR-Z-001"]
            )

        hanger_refs = [
            self.params["acceptedFacts"]["HANGER_DIAMETER_MM"]["sourceRef"],
            self.params["acceptedFacts"]["HANGER_ZONE_M"]["sourceRef"],
            self.params["acceptedFacts"]["END_ZONE_M"]["sourceRef"],
            *cable_refs[:2]
        ]
        radius = self.g["hanger"]["diameter"] / 2.0
        for side_name, y in (("L", cable_y), ("R", -cable_y)):
            for index, x in enumerate(self.g["hangerStations"], 1):
                p1 = App.Vector(x, y, 0.0)
                p2 = App.Vector(x, y, self.main_cable_z(x))
                shape = self.cylinder_between(p1, p2, radius)
                self.add_feature(
                    f"Hanger_{side_name}_{index:02d}", f"吊杆 {side_name}-{index:02d}", shape,
                    "CableSystem", "CG-HANGER", hanger_refs,
                    "ACCEPTED_GEOMETRY", "CIRCULAR_SOLID"
                )
        self.rec.complete_stage("04", "cable_system", "主跨线形按塔顶/跨中闭合；侧跨锚固接口继续携带 A-MAIN-ANCHOR-Z-001。")

    def stage_05_main_anchorages(self) -> None:
        self.rec.start_stage("05", "main_anchorages", "按 720×1050×310cm 控制外包络生成两座主缆锚碇。")
        anchor = self.g["mainAnchor"]
        side = self.g["sideSpan"]
        span = self.g["span"]
        refs = [
            self.params["acceptedFacts"]["MAIN_ANCHOR_WIDTH_CM"]["sourceRef"],
            self.params["acceptedFacts"]["MAIN_ANCHOR_LENGTH_CM"]["sourceRef"],
            self.params["acceptedFacts"]["MAIN_ANCHOR_HEIGHT_CM"]["sourceRef"],
            self.params["acceptedFacts"]["SIDE_SPAN_M"]["sourceRef"]
        ]
        left_base = Part.makeBox(anchor["length"], anchor["width"], anchor["height"], App.Vector(-side - anchor["length"], -anchor["width"] / 2.0, -anchor["height"]))
        left_upper = Part.makeBox(anchor["length"] * 0.58, anchor["width"] * 0.72, anchor["height"] * 0.45, App.Vector(-side - anchor["length"] * 0.72, -anchor["width"] * 0.36, 0.0))
        right_base = Part.makeBox(anchor["length"], anchor["width"], anchor["height"], App.Vector(span + side, -anchor["width"] / 2.0, -anchor["height"]))
        right_upper = Part.makeBox(anchor["length"] * 0.58, anchor["width"] * 0.72, anchor["height"] * 0.45, App.Vector(span + side + anchor["length"] * 0.14, -anchor["width"] * 0.36, 0.0))
        self.add_feature(
            "MainAnchorage_Left", "左岸主缆锚碇", Part.makeCompound([left_base, left_upper]),
            "AnchorageSystem", "CG-MAIN-ANCHORAGE", refs,
            "ACCEPTED_ENVELOPE_WITH_BOUNDED_INTERFACE", "DISPLAY_ENVELOPE",
            ["A-CAD-DISPLAY-001", "A-MAIN-ANCHOR-Z-001"]
        )
        self.add_feature(
            "MainAnchorage_Right", "右岸主缆锚碇", Part.makeCompound([right_base, right_upper]),
            "AnchorageSystem", "CG-MAIN-ANCHORAGE", refs,
            "ACCEPTED_ENVELOPE_WITH_BOUNDED_INTERFACE", "DISPLAY_ENVELOPE",
            ["A-CAD-DISPLAY-001", "A-MAIN-ANCHOR-Z-001"]
        )
        self.rec.complete_stage("05", "main_anchorages", "外包络尺寸有源；内部锚室和主缆精确入口不作制造表达。")

    def stage_06_wind_system(self) -> None:
        self.rec.start_stage("06", "wind_system", "生成 4 条 21.91m 风缆及 4 座有界候选风缆锚碇。")
        wind = self.g["windCable"]
        anchor = self.g["windAnchor"]
        stations = self.g["crossbeamStations"]
        cable_y = self.g["cablePlaneY"]
        attach_indices = wind["attachBeamIndices"]
        for index in attach_indices:
            if index < 1 or index > len(stations):
                raise ValueError(f"风缆横梁编号超界: {index}")
        refs = [
            self.params["acceptedFacts"]["WIND_CABLE_DIAMETER_MM"]["sourceRef"],
            self.params["acceptedFacts"]["WIND_CABLE_LENGTH_M"]["sourceRef"],
            self.params["acceptedFacts"]["WIND_ATTACH_BEAM_A"]["sourceRef"],
            self.params["acceptedFacts"]["WIND_ATTACH_BEAM_B"]["sourceRef"]
        ]
        anchor_refs = [
            self.params["acceptedFacts"]["WIND_ANCHOR_LENGTH_CM"]["sourceRef"],
            self.params["acceptedFacts"]["WIND_ANCHOR_WIDTH_CM"]["sourceRef"],
            self.params["acceptedFacts"]["WIND_ANCHOR_HEIGHT_CM"]["sourceRef"]
        ]
        cable_counter = 0
        for attach_order, beam_index in enumerate(attach_indices):
            x_attach = stations[beam_index - 1]
            x_sign = -1.0 if attach_order == 0 else 1.0
            for side_name, y_sign in (("L", 1.0), ("R", -1.0)):
                cable_counter += 1
                p_attach = App.Vector(x_attach, y_sign * cable_y, -self.g["crossbeam"]["depth"])
                p_anchor = App.Vector(
                    x_attach + x_sign * wind["candidateLongitudinalOffset"],
                    y_sign * (cable_y + wind["candidateLateralOffset"]),
                    p_attach.z - wind["candidateVerticalDrop"]
                )
                actual_length = p_anchor.sub(p_attach).Length
                if abs(actual_length - wind["length"]) > 1e-6:
                    raise ValueError(f"风缆候选长度不闭合: {actual_length} != {wind['length']}")
                shape = self.cylinder_between(p_attach, p_anchor, wind["diameter"] / 2.0)
                self.add_feature(
                    f"WindCable_{cable_counter:02d}", f"风缆 beam{beam_index}-{side_name}", shape,
                    "WindSystem", "CG-WIND-CABLE", refs,
                    "BOUNDED_CANDIDATE", "CIRCULAR_SOLID", ["U-WIND-001"]
                )
                direction = p_anchor.sub(p_attach)
                angle = math.degrees(math.atan2(direction.y, direction.x))
                block = Part.makeBox(
                    anchor["length"], anchor["width"], anchor["height"],
                    App.Vector(-anchor["length"] / 2.0, -anchor["width"] / 2.0, -anchor["height"])
                )
                block.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
                block.translate(p_anchor)
                self.add_feature(
                    f"WindAnchorage_{cable_counter:02d}", f"风缆锚碇候选 {cable_counter:02d}", block,
                    "WindSystem", "CG-WIND-ANCHORAGE", anchor_refs,
                    "BOUNDED_CANDIDATE", "DISPLAY_ENVELOPE",
                    ["U-WIND-001", "A-CAD-DISPLAY-001"]
                )
        self.rec.complete_stage("06", "wind_system", "长度与夹角由程序复算；平面坐标未获唯一地形证据，状态保持 BLOCKED。")

    def stage_07_save_and_export(self) -> None:
        self.rec.start_stage("07", "save_export", "保存最终 FCStd，导出只含 DISPLAY 对象的 STEP，并封存对象清单。")
        self.doc.recompute()
        final_fcstd = self.output_dir / "Zhaqing_CAD-003.FCStd"
        step_path = self.output_dir / "Zhaqing_CAD-003-display.step"
        self.doc.saveAs(str(final_fcstd))
        export_objects = sorted(self.display_objects, key=lambda obj: obj.Name)
        if not export_objects:
            raise ValueError("没有可导出的 DISPLAY 对象")
        Import.export(export_objects, str(step_path))
        if not step_path.exists() or step_path.stat().st_size == 0:
            raise IOError("STEP 导出为空")
        (self.output_dir / "object_manifest.json").write_text(
            json.dumps(self.object_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / "artifact_manifest.json").write_text(
            json.dumps(
                {
                    "generatedAtUtc": utc_now(),
                    "freecadVersion": ".".join(App.Version()[:3]),
                    "parameterContract": {"path": PARAMS_PATH.name, "sha256": sha256_file(PARAMS_PATH)},
                    "files": {
                        final_fcstd.name: {"sha256": sha256_file(final_fcstd), "bytes": final_fcstd.stat().st_size},
                        step_path.name: {"sha256": sha256_file(step_path), "bytes": step_path.stat().st_size}
                    },
                    "displayObjectCount": len(self.display_objects),
                    "referenceObjectCount": len(self.reference_objects),
                    "engineeringReleaseStatus": self.params["engineeringReleaseStatus"]
                },
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )
        self.rec.complete_stage("07", "save_export", "STEP 排除参考骨架；最终文件仍需独立回读校验。")
        self.rec.write_process_markdown(sha256_file(PARAMS_PATH))

    def run(self) -> None:
        self.rec.event(
            "build_start",
            params=str(PARAMS_PATH),
            paramsSha256=sha256_file(PARAMS_PATH),
            freecadVersion=".".join(App.Version()[:3]),
            output=str(self.output_dir)
        )
        self.stage_01_reference_skeleton()
        self.stage_02_deck_system()
        self.stage_03_tower_and_foundations()
        self.stage_04_saddles_main_cables_hangers()
        self.stage_05_main_anchorages()
        self.stage_06_wind_system()
        self.stage_07_save_and_export()
        self.rec.event(
            "build_complete",
            status="PASS",
            displayObjects=len(self.display_objects),
            referenceObjects=len(self.reference_objects),
            engineeringReleaseStatus=self.params["engineeringReleaseStatus"]
        )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
        builder = ModelBuilder(params, OUTPUT_DIR)
        builder.run()
        return 0
    except Exception as exc:
        error = {
            "timeUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "build-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
