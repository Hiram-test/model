#!/usr/bin/env python3
"""按源文件和 CAD 句柄冻结 CAD-003 建模合同。

该脚本属于 N04/N06 的确定性适配层：
1. 只读取 N03 导出的 CSV；
2. 每个数值必须精确命中 source + handle；
3. 对数值执行预设容差检查，对文字执行正则提取；
4. 生成 FreeCAD 只能读取的 frozen_model_contract.json。

脚本不宣布 G3-G6 通过。无法唯一读取任何控制事实时立即非零退出。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv_index(path: Path, key_fields: tuple[str, str]) -> dict[tuple[str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    index: dict[tuple[str, str], dict[str, str]] = {}
    duplicates: list[tuple[str, str]] = []
    for row in rows:
        key = (row[key_fields[0]], row[key_fields[1]].upper())
        if key in index:
            duplicates.append(key)
        index[key] = row
    if duplicates:
        raise ValueError(f"CSV 中存在重复 source+handle: {duplicates[:10]}")
    return index


def parse_numeric(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"不是有限数: {text!r}")
    return value


def to_mm(value: float, unit: str) -> float:
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10.0
    if unit == "m":
        return value * 1000.0
    raise ValueError(f"不能换算到 mm 的单位: {unit}")


def resolve_fact(spec: dict[str, Any], dim_index: dict, text_index: dict) -> dict[str, Any]:
    source = spec["source"]
    handle = spec["handle"].upper()
    table = spec["table"]
    index = dim_index if table == "dimension" else text_index
    row = index.get((source, handle))
    if row is None:
        raise KeyError(f"未找到控制事实 {spec['fact_id']}: {source}:{handle}")

    field = spec.get("field", "text")
    raw = str(row.get(field, "")).strip()
    if not raw:
        raise ValueError(f"控制事实字段为空 {spec['fact_id']}: {source}:{handle}:{field}")

    if "regex" in spec:
        match = re.search(spec["regex"], raw)
        if not match:
            raise ValueError(
                f"文字/覆盖值不匹配 {spec['fact_id']}: raw={raw!r}, regex={spec['regex']!r}"
            )
        extracted = match.group(int(spec.get("group", 0)))
        number_match = re.search(r"[-+]?[0-9]*\.?[0-9]+", extracted)
        if not number_match:
            raise ValueError(f"无法从匹配内容提取数值 {spec['fact_id']}: {extracted!r}")
        value = parse_numeric(number_match.group(0))
    else:
        value = parse_numeric(raw)

    if "expected" in spec:
        expected = float(spec["expected"])
        tolerance = float(spec.get("tolerance", 0.0))
        if abs(value - expected) > tolerance:
            raise ValueError(
                f"控制事实偏离冻结值 {spec['fact_id']}: {value} != {expected} ± {tolerance}"
            )

    return {
        "factId": spec["fact_id"],
        "value": value,
        "unit": spec["unit"],
        "raw": raw,
        "sourceRef": f"{source}:{table}:{handle}:{field}",
    }


def build_contract(facts: dict[str, dict[str, Any]], inputs: dict[str, str]) -> dict[str, Any]:
    v = {k: item["value"] for k, item in facts.items()}

    span = round(to_mm(v["SPAN_M"], "m"), 6)
    hanger_zone = round(to_mm(v["HANGER_ZONE_M"], "m"), 6)
    end_zone = round(to_mm(v["END_ZONE_M"], "m"), 6)
    side_span = round(to_mm(v["SIDE_SPAN_M"], "m"), 6)
    hanger_count_per_side = 25
    hanger_interval = round(hanger_zone / (hanger_count_per_side - 1), 6)
    if abs((2 * end_zone + hanger_zone) - span) > 1e-6:
        raise ValueError("总体尺寸链 5m + 72m + 5m 未闭合到 82m")
    if abs(hanger_interval - 3000.0) > 1e-6:
        raise ValueError("吊杆站点未闭合为 3m 间距")

    hanger_stations = [round(end_zone + i * hanger_interval, 6) for i in range(hanger_count_per_side)]
    crossbeam_stations = [0.0, *hanger_stations, span]
    if len(crossbeam_stations) != 27 or len(set(crossbeam_stations)) != 27:
        raise ValueError("横梁站点必须为 27 个唯一位置")

    tower_z = round(to_mm(v["TOWER_CABLE_HEIGHT_CM"], "cm"), 6)
    cable_rise = round(to_mm(v["CABLE_MAINSPAN_RISE_CM"], "cm"), 6)
    cable_mid_z = round(tower_z - cable_rise, 6)
    if abs(cable_mid_z - 950.0) > 1e-6:
        raise ValueError("主缆跨中高度应由 915cm - 820cm 闭合为 95cm")

    wire_count = int(v["MAIN_CABLE_WIRE_COUNT"])
    wire_d = v["MAIN_CABLE_WIRE_DIAM_MM"]
    equivalent_d = wire_d * math.sqrt(wire_count)

    deck_width = round(to_mm(v["DECK_WIDTH_CM"], "cm"), 6)
    girder_spacing = round(to_mm(v["GIRDER_SPACING_CM"], "cm"), 6)
    edge_overhang = round(to_mm(v["EDGE_OVERHANG_CM"], "cm"), 6)
    if abs(girder_spacing + 2 * edge_overhang - deck_width) > 1e-6:
        raise ValueError("横断面尺寸链 470cm + 2×40cm 未闭合到 550cm")

    wind_length = round(to_mm(v["WIND_CABLE_LENGTH_M"], "m"), 6)
    wind_longitudinal_offset = 12000.0
    wind_vertical_drop = 4000.0
    wind_lateral_offset = math.sqrt(
        wind_length**2 - wind_longitudinal_offset**2 - wind_vertical_drop**2
    )
    wind_plan_angle = math.degrees(math.atan2(wind_lateral_offset, wind_longitudinal_offset))
    if wind_plan_angle <= 50.0:
        raise ValueError("风缆候选平面夹角未满足图示 >50°")

    source_refs = sorted(item["sourceRef"] for item in facts.values())
    return {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "ZHAQING-SUSPENSION-BRIDGE",
        "runId": "CAD-003-VM",
        "internalUnits": "mm",
        "inputHashes": inputs,
        "acceptedFacts": facts,
        "sourceRefs": source_refs,
        "coordinateSystem": {
            "id": "CS-BRIDGE-001",
            "origin": "左塔桥轴线与桥面基准交点",
            "x": "沿桥轴向右塔",
            "y": "面向右塔时横桥向左为正",
            "z": "竖向向上"
        },
        "geometry": {
            "span": span,
            "sideSpan": side_span,
            "deckWidth": deck_width,
            "girderSpacing": girder_spacing,
            "cablePlaneY": deck_width / 2.0,
            "towerStations": [0.0, span],
            "hangerStations": hanger_stations,
            "crossbeamStations": crossbeam_stations,
            "deckPanelAcrossCount": 3,
            "deckPanelWidth": v["DECK_PANEL_WIDTH_MM"],
            "deckPanelSourceLength": v["DECK_PANEL_SOURCE_LENGTH_MM"],
            "deckPanelDisplayThickness": v["DECK_PANEL_DISPLAY_THICKNESS_MM"],
            "longGirder": {
                "depth": v["LONG_GIRDER_DEPTH_MM"],
                "width": v["LONG_GIRDER_WIDTH_MM"],
                "web": v["LONG_GIRDER_WEB_MM"],
                "flange": v["LONG_GIRDER_FLANGE_MM"]
            },
            "crossbeam": {
                "length": v["CROSSBEAM_LENGTH_MM"],
                "depth": to_mm(v["CROSSBEAM_DEPTH_CM"], "cm"),
                "longitudinalWidth": v["CROSSBEAM_LONGITUDINAL_WIDTH_MM"]
            },
            "tower": {
                "cableZ": tower_z,
                "capTransverse": to_mm(v["TOWER_CAP_TRANSVERSE_CM"], "cm"),
                "capLongitudinal": to_mm(v["TOWER_CAP_LONGITUDINAL_CM"], "cm"),
                "columnLongitudinal": to_mm(v["TOWER_COLUMN_LONGITUDINAL_CM"], "cm"),
                "columnTransverse": to_mm(v["TOWER_COLUMN_TRANSVERSE_CM"], "cm"),
                "pileDiameter": to_mm(v["TOWER_PILE_DIAMETER_CM"], "cm")
            },
            "mainCable": {
                "midspanZ": cable_mid_z,
                "towerZ": tower_z,
                "mainspanRise": cable_rise,
                "formulaCoefficient": v["CABLE_FORM_COEFFICIENT"],
                "equivalentDiameter": equivalent_d,
                "wireCount": wire_count,
                "wireDiameter": wire_d,
                "segmentsMainspan": 82,
                "segmentsSideSpan": 24
            },
            "hanger": {"diameter": v["HANGER_DIAMETER_MM"], "count": 50},
            "mainAnchor": {
                "width": to_mm(v["MAIN_ANCHOR_WIDTH_CM"], "cm"),
                "length": to_mm(v["MAIN_ANCHOR_LENGTH_CM"], "cm"),
                "height": to_mm(v["MAIN_ANCHOR_HEIGHT_CM"], "cm")
            },
            "saddle": {
                "width": v["SADDLE_WIDTH_MM"],
                "plateThickness": v["SADDLE_PLATE_THICKNESS_MM"],
                "length": v["SADDLE_LENGTH_MM"]
            },
            "windCable": {
                "diameter": v["WIND_CABLE_DIAMETER_MM"],
                "length": wind_length,
                "attachBeamIndices": [int(v["WIND_ATTACH_BEAM_A"]), int(v["WIND_ATTACH_BEAM_B"])],
                "candidateLongitudinalOffset": wind_longitudinal_offset,
                "candidateLateralOffset": wind_lateral_offset,
                "candidateVerticalDrop": wind_vertical_drop,
                "candidatePlanAngleDeg": wind_plan_angle
            },
            "windAnchor": {
                "length": to_mm(v["WIND_ANCHOR_LENGTH_CM"], "cm"),
                "width": to_mm(v["WIND_ANCHOR_WIDTH_CM"], "cm"),
                "height": to_mm(v["WIND_ANCHOR_HEIGHT_CM"], "cm")
            }
        },
        "boundedAssumptions": [
            {
                "assumptionId": "A-CAD-DISPLAY-001",
                "severity": "MAJOR",
                "statement": "桥面板、横梁、塔柱、基础及锚碇采用图纸控制外包络的显示实体；不表达制造孔、钢筋、螺栓、焊缝和内部构造。",
                "effect": "仅适用于整体装配检查和可视化，不适用于加工、工程量或局部应力。"
            },
            {
                "assumptionId": "A-TOWER-FOUNDATION-001",
                "severity": "MAJOR",
                "statement": "塔基础桩长和承台底标高缺少唯一地质控制值；显示模型采用 8m 桩长和固定承台底标高。",
                "effect": "基础竖向外形为显示假定。"
            },
            {
                "assumptionId": "A-MAIN-ANCHOR-Z-001",
                "severity": "MAJOR",
                "statement": "主缆进入锚碇的三维精确接口未由当前配准闭合；采用桥面下 1.2m 的对称显示接口。",
                "effect": "侧跨索线为显示线，不得作为找形或索长依据。"
            },
            {
                "assumptionId": "U-WIND-001",
                "severity": "CRITICAL",
                "statement": "风缆锚碇平面坐标可随地形调整且当前无唯一测量坐标；采用满足 21.91m 长度和 >50° 平面夹角的对称候选坐标。",
                "effect": "G3-G6 与工程发布保持 BLOCKED；候选实体仅用于展示和后续替换。"
            }
        ],
        "expectedCounts": {
            "DeckPanel": 78,
            "LongGirder": 52,
            "Crossbeam": 27,
            "TowerColumn": 4,
            "TowerTopBeam": 2,
            "TowerCap": 2,
            "TowerPile": 8,
            "Saddle": 4,
            "MainCable": 2,
            "Hanger": 50,
            "MainAnchorage": 2,
            "WindCable": 4,
            "WindAnchorage": 4
        },
        "engineeringReleaseStatus": "BLOCKED",
        "blockingIssueIds": ["U-WIND-001", "A-TOWER-FOUNDATION-001", "A-MAIN-ANCHOR-Z-001"]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dim_path = args.scan_dir / "dimension_candidates.csv"
    text_path = args.scan_dir / "text_index.csv"
    manifest = json.loads(args.facts.read_text(encoding="utf-8"))
    dim_index = load_csv_index(dim_path, ("source", "handle"))
    text_index = load_csv_index(text_path, ("source", "handle"))

    resolved: dict[str, dict[str, Any]] = {}
    for spec in manifest["facts"]:
        item = resolve_fact(spec, dim_index, text_index)
        if item["factId"] in resolved:
            raise ValueError(f"重复 factId: {item['factId']}")
        resolved[item["factId"]] = item

    contract = build_contract(
        resolved,
        {
            "dimensionCandidatesSha256": sha256_file(dim_path),
            "textIndexSha256": sha256_file(text_path),
            "sourceFactsSha256": sha256_file(args.facts),
            "freezeScriptSha256": sha256_file(Path(__file__))
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "fact_count": len(resolved),
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "engineering_release_status": contract["engineeringReleaseStatus"]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
