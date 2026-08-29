#!/usr/bin/env python3
"""Reconcile anchorage geometry and wind-cable placement from frozen DWG evidence.

This deterministic N04/N06 adapter exists because the first CAD-003 contract
misclassified several drawing dimensions:

* main-anchor handle ``1A93`` is a 310 cm horizontal segment, not the total
  anchorage height;
* the wind-cable B points are labelled as hanger/crossbeam Nos. 8 and 18 in the
  plan view, while a note says 13 and 27; the conflict must be recorded rather
  than silently choosing one string;
* 21.91 m is the plan/material length implied by 18.00 m and 12.50 m offsets,
  not the 3-D straight chord after the drawing elevations are applied;
* the wind anchorage is a 150 cm base plus a 150 cm pedestal, not a single
  220 x 120 x 200 cm box.

The script reads only N03 CSV rows addressed by ``source + handle``, updates the
frozen model contract atomically, and writes an explicit reconciliation report.
It has no Gate authority: conflicts remain BLOCKED and are propagated.
"""
from __future__ import annotations

import csv
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

SCAN_DIR = Path(os.environ.get("ZHAQING_SCAN_DIR", "build/zhaqing-cad003/scan")).resolve()
PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", PARAMS_PATH.parent)).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_index(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[tuple[str, str], dict[str, str]] = {}
    duplicates: list[tuple[str, str]] = []
    for row in rows:
        key = (row["source"], row["handle"].upper())
        if key in result:
            duplicates.append(key)
        result[key] = row
    if duplicates:
        raise ValueError(f"duplicate source+handle rows in {path.name}: {duplicates[:8]}")
    return result


def finite_number(raw: str, label: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{label} is not finite: {raw!r}")
    return value


def dimension_fact(
    index: dict[tuple[str, str], dict[str, str]],
    fact_id: str,
    source: str,
    handle: str,
    *,
    field: str = "measurement",
    expected: float | None = None,
    tolerance: float = 1e-6,
    regex: str | None = None,
    group: int = 1,
    unit: str,
) -> dict[str, Any]:
    row = index.get((source, handle.upper()))
    if row is None:
        raise KeyError(f"missing dimension fact {fact_id}: {source}:{handle}")
    raw = str(row.get(field, "")).strip()
    if not raw or raw.lower() == "nan":
        raise ValueError(f"empty dimension field {fact_id}: {source}:{handle}:{field}")
    if regex:
        match = re.search(regex, raw)
        if not match:
            raise ValueError(f"dimension regex mismatch {fact_id}: {raw!r} / {regex!r}")
        value = finite_number(match.group(group), fact_id)
    else:
        value = finite_number(raw, fact_id)
    if expected is not None and abs(value - expected) > tolerance:
        raise ValueError(f"{fact_id}: {value} != {expected} +/- {tolerance}")
    return {
        "factId": fact_id,
        "value": value,
        "unit": unit,
        "raw": raw,
        "sourceRef": f"{source}:dimension:{handle.upper()}:{field}",
    }


def text_fact(
    index: dict[tuple[str, str], dict[str, str]],
    fact_id: str,
    source: str,
    handle: str,
    regex: str,
    *,
    group: int = 1,
    unit: str,
) -> dict[str, Any]:
    row = index.get((source, handle.upper()))
    if row is None:
        raise KeyError(f"missing text fact {fact_id}: {source}:{handle}")
    raw = str(row.get("text", "")).strip()
    match = re.search(regex, raw)
    if not match:
        raise ValueError(f"text regex mismatch {fact_id}: {raw!r} / {regex!r}")
    value = finite_number(match.group(group), fact_id)
    return {
        "factId": fact_id,
        "value": value,
        "unit": unit,
        "raw": raw,
        "sourceRef": f"{source}:text:{handle.upper()}:text",
    }


def mm(value: float, unit: str) -> float:
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10.0
    if unit == "m":
        return value * 1000.0
    raise ValueError(f"unsupported length unit: {unit}")


def add_assumption(contract: dict[str, Any], record: dict[str, Any]) -> None:
    assumptions = contract.setdefault("boundedAssumptions", [])
    assumptions[:] = [item for item in assumptions if item.get("assumptionId") != record["assumptionId"]]
    assumptions.append(record)


def reconcile() -> dict[str, Any]:
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(PARAMS_PATH)
    dim_path = SCAN_DIR / "dimension_candidates.csv"
    text_path = SCAN_DIR / "text_index.csv"
    dim_index = load_index(dim_path)
    text_index = load_index(text_path)
    contract = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))

    facts: dict[str, dict[str, Any]] = {}

    # Main anchorage: longitudinal elevation, plan width, stepped underside and
    # transverse recess/anchor strips. All values are centimetres in SGT-26.
    main_dim_specs = [
        ("MAIN_ANCHOR_LONGITUDINAL_CM", "1B7C", 1050.0),
        ("MAIN_ANCHOR_TRANSVERSE_CM", "1C02", 720.0),
        ("MAIN_ANCHOR_TOTAL_HEIGHT_CM", "1B9F", 700.0),
        ("MAIN_ANCHOR_BODY_TOP_DROP_CM", "1B2D", 100.0),
        ("MAIN_ANCHOR_RECESS_DEPTH_CM", "1B39", 211.435935),
        ("MAIN_ANCHOR_REAR_NIB_CM", "1AEE", 120.0),
        ("MAIN_ANCHOR_BOTTOM_SEGMENT_A_CM", "1A93", 310.0),
        ("MAIN_ANCHOR_BOTTOM_SEGMENT_B_CM", "1AA0", 310.0),
        ("MAIN_ANCHOR_BOTTOM_SEGMENT_C_CM", "1AAD", 310.0),
        ("MAIN_ANCHOR_BOTTOM_STEP_CM", "1AD4", 100.0),
        ("MAIN_ANCHOR_EDGE_BAND_CM", "1DC1", 95.0),
        ("MAIN_ANCHOR_RAISED_STRIP_CM", "1DCD", 60.0),
        ("MAIN_ANCHOR_SHOULDER_BAND_CM", "1DD9", 95.0),
        ("MAIN_ANCHOR_CENTRAL_RECESS_CM", "1DE5", 220.0),
        ("MAIN_ANCHOR_CABLE_SPACING_CM", "1D1A", 470.0),
    ]
    for fact_id, handle, expected in main_dim_specs:
        facts[fact_id] = dimension_fact(
            dim_index, fact_id, "26-锚碇一般构造.dwg", handle,
            expected=expected, unit="cm"
        )
    facts["MAIN_ANCHOR_TOP_ELEV_M"] = text_fact(
        text_index, "MAIN_ANCHOR_TOP_ELEV_M", "26-锚碇一般构造.dwg", "3D6A",
        r"([0-9]+\.[0-9]+)", unit="m"
    )
    facts["MAIN_ANCHOR_LOW_CONTROL_ELEV_M"] = text_fact(
        text_index, "MAIN_ANCHOR_LOW_CONTROL_ELEV_M", "26-锚碇一般构造.dwg", "3D6D",
        r"([0-9]+\.[0-9]+)", unit="m"
    )

    # Wind cable: the view label gives 8/18, while the general note gives
    # 13/27. Both are retained and the direct B-point view label plus the 15 m
    # centreline offset drive the display scenario.
    facts["WIND_ATTACH_VIEW_A"] = text_fact(
        text_index, "WIND_ATTACH_VIEW_A", "32-风缆构造.dwg", "A03E",
        r"([0-9]+)号横梁.*?([0-9]+)号横梁", group=1, unit="hanger_crossbeam_number"
    )
    facts["WIND_ATTACH_VIEW_B"] = text_fact(
        text_index, "WIND_ATTACH_VIEW_B", "32-风缆构造.dwg", "A03E",
        r"([0-9]+)号横梁.*?([0-9]+)号横梁", group=2, unit="hanger_crossbeam_number"
    )
    facts["WIND_ATTACH_NOTE_A"] = text_fact(
        text_index, "WIND_ATTACH_NOTE_A", "32-风缆构造.dwg", "A00C",
        r"([0-9]+)号、([0-9]+)号", group=1, unit="crossbeam_number"
    )
    facts["WIND_ATTACH_NOTE_B"] = text_fact(
        text_index, "WIND_ATTACH_NOTE_B", "32-风缆构造.dwg", "A00C",
        r"([0-9]+)号、([0-9]+)号", group=2, unit="crossbeam_number"
    )
    facts["WIND_LONGITUDINAL_OFFSET_CM"] = dimension_fact(
        dim_index, "WIND_LONGITUDINAL_OFFSET_CM", "32-风缆构造.dwg", "9F3B",
        field="text_override", regex=r"^([0-9]+)$", expected=1800.0, unit="cm"
    )
    facts["WIND_TRANSVERSE_TOTAL_CM"] = dimension_fact(
        dim_index, "WIND_TRANSVERSE_TOTAL_CM", "32-风缆构造.dwg", "9F9F",
        field="text_override", regex=r"^([0-9]+)/2$", expected=2500.0, unit="cm"
    )
    facts["WIND_B_TO_BRIDGE_CENTER_CM"] = dimension_fact(
        dim_index, "WIND_B_TO_BRIDGE_CENTER_CM", "32-风缆构造.dwg", "A017",
        field="text_override", regex=r"^([0-9]+)$", expected=1500.0, unit="cm"
    )
    facts["WIND_HORIZONTAL_ANGLE_MIN_DEG"] = text_fact(
        text_index, "WIND_HORIZONTAL_ANGLE_MIN_DEG", "32-风缆构造.dwg", "A06A",
        r"([0-9]+)%%D", unit="deg"
    )
    facts["WIND_VERTICAL_ANGLE_MIN_DEG"] = text_fact(
        text_index, "WIND_VERTICAL_ANGLE_MIN_DEG", "32-风缆构造.dwg", "A00B",
        r"([0-9]+)%%D", unit="deg"
    )
    facts["WIND_ANCHOR_EYE_ELEV_M"] = text_fact(
        text_index, "WIND_ANCHOR_EYE_ELEV_M", "32-风缆构造.dwg", "9FED",
        r"([0-9]+\.[0-9]+)", unit="m"
    )
    facts["BRIDGE_DECK_ELEV_M"] = text_fact(
        text_index, "BRIDGE_DECK_ELEV_M", "32-风缆构造.dwg", "A0D0",
        r"([0-9]+\.[0-9]+)", unit="m"
    )

    # Wind anchorage concrete envelope from the orthogonal elevation/side
    # views: 220 x 200 x 150 cm base plus 120 x 100 x 150 cm pedestal.
    wind_anchor_specs = [
        ("WIND_ANCHOR_BASE_LENGTH_CM", "AB34", 220.0),
        ("WIND_ANCHOR_BASE_WIDTH_CM", "AB94", 200.0),
        ("WIND_ANCHOR_BASE_HEIGHT_CM", "AB3B", 150.0),
        ("WIND_ANCHOR_PEDESTAL_LENGTH_CM", "AC03", 120.0),
        ("WIND_ANCHOR_PEDESTAL_WIDTH_CM", "AC0A", 100.0),
        ("WIND_ANCHOR_PEDESTAL_HEIGHT_CM", "AB2C", 150.0),
    ]
    for fact_id, handle, expected in wind_anchor_specs:
        facts[fact_id] = dimension_fact(
            dim_index, fact_id, "33-风缆锚碇.dwg", handle,
            expected=expected, unit="cm"
        )
    facts["WIND_ANCHOR_BASE_ELEV_M"] = text_fact(
        text_index, "WIND_ANCHOR_BASE_ELEV_M", "33-风缆锚碇.dwg", "AB44",
        r"([0-9]+\.[0-9]+)", unit="m"
    )
    facts["WIND_ANCHOR_TOP_ELEV_M"] = text_fact(
        text_index, "WIND_ANCHOR_TOP_ELEV_M", "33-风缆锚碇.dwg", "ABF5",
        r"([0-9]+\.[0-9]+)", unit="m"
    )

    accepted = contract.setdefault("acceptedFacts", {})
    superseded_ids = [
        "MAIN_ANCHOR_WIDTH_CM", "MAIN_ANCHOR_LENGTH_CM", "MAIN_ANCHOR_HEIGHT_CM",
        "WIND_ATTACH_BEAM_A", "WIND_ATTACH_BEAM_B",
        "WIND_ANCHOR_LENGTH_CM", "WIND_ANCHOR_WIDTH_CM", "WIND_ANCHOR_HEIGHT_CM",
    ]
    superseded = {key: accepted.pop(key) for key in superseded_ids if key in accepted}
    accepted.update(facts)

    geometry = contract["geometry"]
    deck_elev = facts["BRIDGE_DECK_ELEV_M"]["value"]
    main_top_z = mm(facts["MAIN_ANCHOR_TOP_ELEV_M"]["value"] - deck_elev, "m")
    main_low_z = mm(facts["MAIN_ANCHOR_LOW_CONTROL_ELEV_M"]["value"] - deck_elev, "m")

    longitudinal = mm(facts["MAIN_ANCHOR_LONGITUDINAL_CM"]["value"], "cm")
    transverse = mm(facts["MAIN_ANCHOR_TRANSVERSE_CM"]["value"], "cm")
    total_height = mm(facts["MAIN_ANCHOR_TOTAL_HEIGHT_CM"]["value"], "cm")
    shoulder_drop = mm(facts["MAIN_ANCHOR_BODY_TOP_DROP_CM"]["value"], "cm")
    recess_depth = mm(facts["MAIN_ANCHOR_RECESS_DEPTH_CM"]["value"], "cm")
    rear_region = mm(
        facts["MAIN_ANCHOR_REAR_NIB_CM"]["value"]
        + facts["MAIN_ANCHOR_BOTTOM_SEGMENT_A_CM"]["value"], "cm"
    )
    mid_region = mm(facts["MAIN_ANCHOR_BOTTOM_SEGMENT_B_CM"]["value"], "cm")
    bridge_region = mm(facts["MAIN_ANCHOR_BOTTOM_SEGMENT_C_CM"]["value"], "cm")
    if abs(rear_region + mid_region + bridge_region - longitudinal) > 1e-6:
        raise ValueError("main-anchor longitudinal segment chain does not close")

    edge_band = mm(facts["MAIN_ANCHOR_EDGE_BAND_CM"]["value"], "cm")
    strip_width = mm(facts["MAIN_ANCHOR_RAISED_STRIP_CM"]["value"], "cm")
    shoulder_band = mm(facts["MAIN_ANCHOR_SHOULDER_BAND_CM"]["value"], "cm")
    central_recess = mm(facts["MAIN_ANCHOR_CENTRAL_RECESS_CM"]["value"], "cm")
    transverse_chain = 2.0 * (edge_band + strip_width + shoulder_band) + central_recess
    if abs(transverse_chain - transverse) > 1e-6:
        raise ValueError("main-anchor transverse chain does not close")
    anchor_cable_spacing = mm(facts["MAIN_ANCHOR_CABLE_SPACING_CM"]["value"], "cm")

    geometry["mainAnchor"] = {
        # Legacy aliases retained so the original candidate stage can run; the
        # dedicated correction stage replaces that candidate with the profile.
        "length": longitudinal,
        "width": transverse,
        "height": total_height,
        "longitudinal": longitudinal,
        "transverse": transverse,
        "totalHeight": total_height,
        "topZ": main_top_z,
        "lowCableControlZ": main_low_z,
        "shoulderTopDrop": shoulder_drop,
        "centralRecessDepthBelowShoulder": recess_depth,
        "bottomRegionsFromBridge": [bridge_region, mid_region, rear_region],
        "bottomDropsBelowTop": [5000.0, 6000.0, total_height],
        "transversePartitions": [
            edge_band, strip_width, shoulder_band, central_recess,
            shoulder_band, strip_width, edge_band,
        ],
        "raisedStripWidth": strip_width,
        "anchorCableSpacing": anchor_cable_spacing,
        "anchorCablePlaneY": anchor_cable_spacing / 2.0,
    }

    hanger_numbers = [int(facts["WIND_ATTACH_VIEW_A"]["value"]), int(facts["WIND_ATTACH_VIEW_B"]["value"])]
    note_numbers = [int(facts["WIND_ATTACH_NOTE_A"]["value"]), int(facts["WIND_ATTACH_NOTE_B"]["value"])]
    hanger_stations = geometry["hangerStations"]
    attach_stations = [hanger_stations[number - 1] for number in hanger_numbers]
    bridge_center = geometry["span"] / 2.0
    b_offset = mm(facts["WIND_B_TO_BRIDGE_CENTER_CM"]["value"], "cm")
    if any(abs(abs(x - bridge_center) - b_offset) > 1e-6 for x in attach_stations):
        raise ValueError(f"wind B points do not close to +/-15 m from bridge centre: {attach_stations}")

    dx = mm(facts["WIND_LONGITUDINAL_OFFSET_CM"]["value"], "cm")
    dy = mm(facts["WIND_TRANSVERSE_TOTAL_CM"]["value"] / 2.0, "cm")
    plan_length = math.hypot(dx, dy)
    material_plan_length = mm(contract["acceptedFacts"]["WIND_CABLE_LENGTH_M"]["value"], "m")
    attach_z = -float(geometry["crossbeam"]["depth"])
    eye_z = mm(facts["WIND_ANCHOR_EYE_ELEV_M"]["value"] - deck_elev, "m")
    vertical_drop = attach_z - eye_z
    straight_chord = math.sqrt(plan_length**2 + vertical_drop**2)
    plan_angle = math.degrees(math.atan2(dy, dx))
    vertical_angle = math.degrees(math.atan2(vertical_drop, plan_length))

    geometry["windCable"] = {
        "diameter": contract["acceptedFacts"]["WIND_CABLE_DIAMETER_MM"]["value"],
        # Legacy length now means the actual 3-D display chord. Material/cut
        # length is preserved separately and is not misused as endpoint distance.
        "length": straight_chord,
        "straightChordLength": straight_chord,
        "materialPlanLength": material_plan_length,
        "derivedPlanLength": plan_length,
        "attachHangerCrossbeamNumbers": hanger_numbers,
        "conflictingNoteCrossbeamNumbers": note_numbers,
        "attachBeamIndices": [number + 1 for number in hanger_numbers],
        "attachStations": attach_stations,
        "candidateLongitudinalOffset": dx,
        "candidateLateralOffset": dy,
        "candidateVerticalDrop": vertical_drop,
        "anchorEyeZ": eye_z,
        "attachmentZ": attach_z,
        "candidatePlanAngleDeg": plan_angle,
        "candidateVerticalAngleDeg": vertical_angle,
        "horizontalAngleMinimumDeg": facts["WIND_HORIZONTAL_ANGLE_MIN_DEG"]["value"],
        "verticalAngleMinimumDeg": facts["WIND_VERTICAL_ANGLE_MIN_DEG"]["value"],
        "planLengthDifferenceFromMaterialMm": plan_length - material_plan_length,
        "straightChordExcessOverPlanMaterialMm": straight_chord - material_plan_length,
    }

    base_length = mm(facts["WIND_ANCHOR_BASE_LENGTH_CM"]["value"], "cm")
    base_width = mm(facts["WIND_ANCHOR_BASE_WIDTH_CM"]["value"], "cm")
    base_height = mm(facts["WIND_ANCHOR_BASE_HEIGHT_CM"]["value"], "cm")
    pedestal_length = mm(facts["WIND_ANCHOR_PEDESTAL_LENGTH_CM"]["value"], "cm")
    pedestal_width = mm(facts["WIND_ANCHOR_PEDESTAL_WIDTH_CM"]["value"], "cm")
    pedestal_height = mm(facts["WIND_ANCHOR_PEDESTAL_HEIGHT_CM"]["value"], "cm")
    total_wind_anchor_height = base_height + pedestal_height
    drawing_total = mm(
        facts["WIND_ANCHOR_TOP_ELEV_M"]["value"] - facts["WIND_ANCHOR_BASE_ELEV_M"]["value"], "m"
    )
    if abs(total_wind_anchor_height - drawing_total) > 1e-6:
        raise ValueError("wind-anchor 150+150 cm chain does not match 4122.506 to 4125.506")
    geometry["windAnchor"] = {
        "length": base_length,
        "width": base_width,
        "height": total_wind_anchor_height,
        "baseLength": base_length,
        "baseWidth": base_width,
        "baseHeight": base_height,
        "pedestalLength": pedestal_length,
        "pedestalWidth": pedestal_width,
        "pedestalHeight": pedestal_height,
        "totalHeight": total_wind_anchor_height,
        "baseZ": mm(facts["WIND_ANCHOR_BASE_ELEV_M"]["value"] - deck_elev, "m"),
        "topZ": eye_z,
    }

    add_assumption(contract, {
        "assumptionId": "C-WIND-ATTACH-NUMBER-001",
        "severity": "CRITICAL",
        "statement": f"风缆平面图 B 点标注为 {hanger_numbers[0]}/{hanger_numbers[1]} 号横梁，说明文字为 {note_numbers[0]}/{note_numbers[1]} 号；显示模型采用与桥中心 +/-15m 尺寸闭合的前者。",
        "effect": "编号冲突未由正式修订关闭，G3-G6 保持 BLOCKED。",
    })
    add_assumption(contract, {
        "assumptionId": "C-WIND-HORIZONTAL-ANGLE-001",
        "severity": "MAJOR",
        "statement": f"18.00m 与 12.50m 平面尺寸导出夹角 {plan_angle:.6f}deg，与图注大于35deg相差 {35.0-plan_angle:.6f}deg。",
        "effect": "不通过移动锚点反向凑角度；等待地形坐标/正式确认。",
    })
    add_assumption(contract, {
        "assumptionId": "A-MAIN-ANCHOR-INTERFACE-002",
        "severity": "MAJOR",
        "statement": "主锚碇外包络、台阶、横向槽和470cm锚索间距按SGT-26重建；主缆显示接口暂取桥侧顶面，内部锚固构造仍不表达。",
        "effect": "锚碇外形可用于装配查看，内部锚固、索长和找形仍不得使用。",
    })

    blockers = set(contract.setdefault("blockingIssueIds", []))
    blockers.update({"C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001", "A-MAIN-ANCHOR-INTERFACE-002"})
    contract["blockingIssueIds"] = sorted(blockers)
    contract["sourceRefs"] = sorted(set(contract.get("sourceRefs", [])) | {item["sourceRef"] for item in facts.values()})
    contract["anchorWindReconciliation"] = {
        "generatedAtUtc": utc_now(),
        "adapter": Path(__file__).name,
        "adapterSha256": sha256_file(Path(__file__)),
        "supersededFacts": superseded,
        "acceptedReplacementFactIds": sorted(facts),
        "windAttachmentDecision": {
            "selected": hanger_numbers,
            "rejectedUntilResolved": note_numbers,
            "basis": ["A03E direct B-point label", "A017 +/-15m centreline dimension", "hanger station table"],
        },
        "windGeometry": {
            "planLengthMm": plan_length,
            "materialPlanLengthMm": material_plan_length,
            "straightChordLengthMm": straight_chord,
            "planAngleDeg": plan_angle,
            "verticalAngleDeg": vertical_angle,
        },
    }

    temporary = PARAMS_PATH.with_suffix(PARAMS_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, PARAMS_PATH)

    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS_WITH_BLOCKED_CONFLICTS",
        "contractPath": str(PARAMS_PATH),
        "contractSha256": sha256_file(PARAMS_PATH),
        "scanInputs": {
            "dimensionCandidates": {"path": str(dim_path), "sha256": sha256_file(dim_path)},
            "textIndex": {"path": str(text_path), "sha256": sha256_file(text_path)},
        },
        "supersededFacts": superseded,
        "acceptedFacts": facts,
        "mainAnchor": geometry["mainAnchor"],
        "windCable": geometry["windCable"],
        "windAnchor": geometry["windAnchor"],
        "blockingConflicts": ["C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001"],
    }
    report_path = OUTPUT_DIR / "anchor_wind_contract_reconciliation.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    try:
        report = reconcile()
        print(json.dumps({
            "status": report["status"],
            "contractSha256": report["contractSha256"],
            "mainAnchorHeightMm": report["mainAnchor"]["totalHeight"],
            "windAttachStationsMm": report["windCable"]["attachStations"],
            "windPlanOffsetsMm": [
                report["windCable"]["candidateLongitudinalOffset"],
                report["windCable"]["candidateLateralOffset"],
            ],
            "windStraightChordMm": report["windCable"]["straightChordLength"],
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
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "anchor-wind-reconciliation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
