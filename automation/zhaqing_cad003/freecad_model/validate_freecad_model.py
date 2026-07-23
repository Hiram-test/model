#!/usr/bin/env python3
"""独立回读 CAD-003 FCStd/STEP，并生成技术校验与 Gate receipt。

该脚本与建模脚本分离，禁止调用 ModelBuilder。它只读取已保存文件并检查：
- 稳定对象 ID、证据属性和预期构件数量；
- OpenCASCADE shape validity、正体积和重复同位实体；
- 模型总体范围、主缆/吊杆/风缆的基本几何不变量；
- STEP 重新导入、非空实体和 FCStd/STEP 包围盒一致性。

FreeCAD 0.19 的 ``Import.insert`` 会走 OCAF/STEPCAF 装配导入路径；本项目的多实体
STEP 在 Ubuntu 22.04 实跑中于 100% 后发生 SIGSEGV。这里改用 ``Part.insert``，
只回读几何拓扑，不恢复名称/颜色/装配标签，恰好符合本校验器的目标，并把该工具
选择写入报告。技术校验通过仍不能覆盖上游 G3-G5 的工程阻断。
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
STEP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-display.step"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aggregate_bbox(objects: list[App.DocumentObject]) -> dict[str, list[float]]:
    bounds = []
    for obj in objects:
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        b = shape.BoundBox
        bounds.append((b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax))
    if not bounds:
        raise ValueError("无法从对象集合计算包围盒")
    return {
        "min": [min(x[0] for x in bounds), min(x[1] for x in bounds), min(x[2] for x in bounds)],
        "max": [max(x[3] for x in bounds), max(x[4] for x in bounds), max(x[5] for x in bounds)]
    }


def bbox_delta(a: dict[str, list[float]], b: dict[str, list[float]]) -> float:
    values = []
    for key in ("min", "max"):
        values.extend(abs(x - y) for x, y in zip(a[key], b[key]))
    return max(values)


def prefix_count(objects: list[App.DocumentObject], prefix: str) -> int:
    return sum(1 for obj in objects if obj.Name.startswith(prefix + "_"))


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: Any) -> None:
    checks.append({"checkId": check_id, "status": "PASS" if passed else "FAIL", "details": details})


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    add_check(checks, "FILES_EXIST", FCSTD_PATH.exists() and STEP_PATH.exists(), {
        "fcstd": str(FCSTD_PATH), "step": str(STEP_PATH)
    })
    if not FCSTD_PATH.exists() or not STEP_PATH.exists():
        raise FileNotFoundError("FCStd 或 STEP 不存在")

    doc = App.openDocument(str(FCSTD_PATH))
    part_objects = [obj for obj in doc.Objects if obj.TypeId == "Part::Feature"]
    display_objects = [obj for obj in part_objects if getattr(obj, "DisplayRole", "") != "REFERENCE"]
    reference_objects = [obj for obj in part_objects if getattr(obj, "DisplayRole", "") == "REFERENCE"]

    stable_ids: set[str] = set()
    signatures: dict[tuple[float, ...], str] = {}
    invalid_shapes: list[str] = []
    zero_volume_display: list[str] = []
    missing_metadata: list[str] = []
    duplicate_ids: list[str] = []
    duplicate_signatures: list[tuple[str, str]] = []
    malformed_json: list[str] = []
    bounded_without_assumption: list[str] = []

    for obj in part_objects:
        required = ["StableObjectId", "ComponentGroupId", "SourceRefsJson", "EvidenceStatus", "Representation", "AssumptionRefsJson", "DisplayRole"]
        for prop in required:
            if prop not in obj.PropertiesList:
                missing_metadata.append(f"{obj.Name}:{prop}")
        sid = getattr(obj, "StableObjectId", "")
        if sid in stable_ids:
            duplicate_ids.append(sid)
        stable_ids.add(sid)
        try:
            source_refs = json.loads(getattr(obj, "SourceRefsJson", "[]"))
            assumption_refs = json.loads(getattr(obj, "AssumptionRefsJson", "[]"))
            if not isinstance(source_refs, list) or not source_refs:
                missing_metadata.append(f"{obj.Name}:empty SourceRefsJson")
            if ("BOUNDED" in getattr(obj, "EvidenceStatus", "") or "WITH_BOUNDS" in getattr(obj, "EvidenceStatus", "")) and not assumption_refs:
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
            b = shape.BoundBox
            signature = tuple(round(x, 5) for x in (
                b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax, shape.Volume
            ))
            if signature in signatures:
                duplicate_signatures.append((signatures[signature], obj.Name))
            else:
                signatures[signature] = obj.Name

    add_check(checks, "OBJECT_METADATA_COMPLETE", not missing_metadata and not malformed_json, {
        "missing": missing_metadata, "malformedJson": malformed_json
    })
    add_check(checks, "STABLE_IDS_UNIQUE", not duplicate_ids, duplicate_ids)
    add_check(checks, "SHAPES_VALID", not invalid_shapes, invalid_shapes)
    add_check(checks, "DISPLAY_VOLUME_POSITIVE", not zero_volume_display, zero_volume_display)
    add_check(checks, "BOUNDED_ASSUMPTIONS_LINKED", not bounded_without_assumption, bounded_without_assumption)
    add_check(checks, "NO_SAME_LOCATION_DUPLICATE", not duplicate_signatures, duplicate_signatures)

    count_results: dict[str, Any] = {}
    count_ok = True
    for key, expected in params["expectedCounts"].items():
        actual = prefix_count(part_objects, key)
        count_results[key] = {"expected": expected, "actual": actual}
        count_ok = count_ok and actual == expected
    add_check(checks, "EXPECTED_COMPONENT_COUNTS", count_ok, count_results)

    forbidden = [obj.Name for obj in part_objects if "AssemblyCopy" in obj.Name or "FullAssembly" in obj.Name]
    add_check(checks, "NO_FULL_ASSEMBLY_DUPLICATE", not forbidden, forbidden)

    fc_bbox = aggregate_bbox(display_objects)
    g = params["geometry"]
    broad_bbox_ok = (
        fc_bbox["min"][0] < -g["sideSpan"]
        and fc_bbox["max"][0] > g["span"] + g["sideSpan"]
        and fc_bbox["min"][1] < -g["cablePlaneY"]
        and fc_bbox["max"][1] > g["cablePlaneY"]
        and fc_bbox["min"][2] <= -12000.0
        and fc_bbox["max"][2] >= g["tower"]["cableZ"]
    )
    add_check(checks, "GLOBAL_BBOX_COVERS_SYSTEMS", broad_bbox_ok, fc_bbox)

    wind_lengths: dict[str, float] = {}
    wind_ok = True
    wind_area = math.pi * (g["windCable"]["diameter"] / 2.0) ** 2
    for obj in part_objects:
        if obj.Name.startswith("WindCable_"):
            length = obj.Shape.Volume / wind_area
            wind_lengths[obj.Name] = length
            wind_ok = wind_ok and abs(length - g["windCable"]["length"]) < 1e-4
    add_check(checks, "WIND_CABLE_LENGTHS", wind_ok and len(wind_lengths) == 4, wind_lengths)

    hanger_lengths = {}
    hanger_ok = True
    hanger_area = math.pi * (g["hanger"]["diameter"] / 2.0) ** 2
    for obj in part_objects:
        if obj.Name.startswith("Hanger_"):
            length = obj.Shape.Volume / hanger_area
            hanger_lengths[obj.Name] = length
            hanger_ok = hanger_ok and length > 900.0
    add_check(checks, "HANGER_POSITIVE_LENGTHS", hanger_ok and len(hanger_lengths) == 50, {
        "count": len(hanger_lengths),
        "min": min(hanger_lengths.values()) if hanger_lengths else None,
        "max": max(hanger_lengths.values()) if hanger_lengths else None
    })

    main_cables = [obj for obj in part_objects if obj.Name.startswith("MainCable_")]
    cable_ok = len(main_cables) == 2 and all(
        obj.Shape.BoundBox.ZMax >= g["mainCable"]["towerZ"] - 1e-3
        and obj.Shape.BoundBox.ZMin <= -1200.0 + g["mainCable"]["equivalentDiameter"]
        for obj in main_cables
    )
    add_check(checks, "MAIN_CABLE_CONTROL_RANGE", cable_ok, {
        obj.Name: {"zMin": obj.Shape.BoundBox.ZMin, "zMax": obj.Shape.BoundBox.ZMax}
        for obj in main_cables
    })

    # FreeCAD 0.19 的 Import.insert 使用 OCAF/STEPCAF，实跑在本多实体 STEP 上崩溃。
    # Part.insert 只恢复几何 Part::Feature，避免颜色/名称装配恢复路径，并满足本检查目标。
    step_doc = App.newDocument("Zhaqing_STEP_RoundTrip")
    Part.insert(str(STEP_PATH), step_doc.Name)
    step_doc.recompute()
    step_objects = [obj for obj in step_doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    step_valid = [obj.Name for obj in step_objects if obj.Shape.isValid()]
    step_invalid = [obj.Name for obj in step_objects if not obj.Shape.isValid()]
    step_bbox = aggregate_bbox(step_objects)
    delta = bbox_delta(fc_bbox, step_bbox)
    add_check(checks, "STEP_REIMPORT_NONEMPTY", bool(step_objects), {
        "objects": len(step_objects), "valid": len(step_valid), "invalid": step_invalid,
        "reader": "Part.insert (geometry-only, non-OCAF assembly path)"
    })
    add_check(checks, "STEP_REIMPORT_VALID", not step_invalid, step_invalid)
    add_check(checks, "STEP_FCSTD_BBOX_MATCH", delta <= 0.5, {
        "maxAbsoluteDeltaMm": delta, "fcstd": fc_bbox, "step": step_bbox
    })
    roundtrip_path = OUTPUT_DIR / "Zhaqing_CAD-003-STEP-roundtrip.FCStd"
    step_doc.saveAs(str(roundtrip_path))

    technical_pass = all(item["status"] == "PASS" for item in checks)
    if not technical_pass:
        for check in checks:
            if check["status"] == "FAIL":
                issues.append({
                    "issueId": f"TECH-{check['checkId']}",
                    "severity": "CRITICAL",
                    "ownerNode": "N07",
                    "details": check["details"]
                })

    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "technicalStatus": "PASS" if technical_pass else "FAIL",
        "engineeringReleaseStatus": params["engineeringReleaseStatus"],
        "freecadVersion": ".".join(App.Version()[:3]),
        "stepReader": "Part.insert geometry-only path; Import.insert OCAF path excluded after reproducible SIGSEGV in run 29984424279",
        "files": {
            "fcstd": {"path": str(FCSTD_PATH), "sha256": sha256_file(FCSTD_PATH), "bytes": FCSTD_PATH.stat().st_size},
            "step": {"path": str(STEP_PATH), "sha256": sha256_file(STEP_PATH), "bytes": STEP_PATH.stat().st_size},
            "stepRoundtrip": {"path": str(roundtrip_path), "sha256": sha256_file(roundtrip_path), "bytes": roundtrip_path.stat().st_size}
        },
        "statistics": {
            "partObjects": len(part_objects),
            "displayObjects": len(display_objects),
            "referenceObjects": len(reference_objects),
            "stepObjects": len(step_objects),
            "fcstdBBox": fc_bbox,
            "stepBBox": step_bbox
        },
        "checks": checks,
        "issues": issues
    }

    gate_receipt = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "runId": params["runId"],
        "technicalGeometryValidation": report["technicalStatus"],
        "gates": [
            {
                "gateId": "G3",
                "status": "BLOCKED",
                "reason": "关键视图的完整坐标变换、逐控制点 round-trip overlay 和风缆锚点唯一坐标尚未闭合。",
                "blockingIssues": ["U-WIND-001"]
            },
            {
                "gateId": "G4",
                "status": "BLOCKED",
                "reason": "当前模型覆盖主要系统，但制造 Part 全量映射、装配图和 orphan audit 尚未形成正式工件。",
                "blockingIssues": ["N05-PART-COVERAGE-INCOMPLETE"]
            },
            {
                "gateId": "G5",
                "status": "BLOCKED",
                "reason": "显示实体 representation 已固定，但基础、锚固和风缆关键接口仍含高敏感有界假定。",
                "blockingIssues": params["blockingIssueIds"]
            },
            {
                "gateId": "G6",
                "status": "BLOCKED",
                "reason": "FreeCAD/STEP 技术几何可以通过，但上游 G3-G5 未通过且正式图纸回投未完整，因此不得工程放行。",
                "blockingIssues": ["UPSTREAM-GATES-BLOCKED"]
            }
        ],
        "allowedUse": ["整体装配查看", "STEP 交换测试", "后续证据回投和 FEM 几何接口开发"],
        "forbiddenUse": ["施工放样", "加工下料", "工程量", "正式结构计算", "安全结论"]
    }
    return report, gate_receipt


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# CAD-003 独立技术校验",
        "",
        f"- 技术状态：`{report['technicalStatus']}`",
        f"- 工程发布状态：`{report['engineeringReleaseStatus']}`",
        f"- FreeCAD：`{report['freecadVersion']}`",
        f"- STEP 读取器：`{report['stepReader']}`",
        f"- DISPLAY 对象：{report['statistics']['displayObjects']}",
        f"- STEP 回读对象：{report['statistics']['stepObjects']}",
        "",
        "| 检查 | 状态 |",
        "|---|---|"
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['checkId']}` | {check['status']} |")
    lines += [
        "",
        "技术状态只说明文件、对象、OpenCASCADE 形状和 STEP 回读满足本次机器检查；",
        "它不替代 N04-N06 的工程证据、装配和抽象 Gate。"
    ]
    (OUTPUT_DIR / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        report, gate_receipt = validate()
        (OUTPUT_DIR / "validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (OUTPUT_DIR / "gate_receipt.json").write_text(
            json.dumps(gate_receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_markdown(report)
        print(json.dumps({
            "technicalStatus": report["technicalStatus"],
            "engineeringReleaseStatus": report["engineeringReleaseStatus"],
            "checks": len(report["checks"]),
            "failedChecks": [c["checkId"] for c in report["checks"] if c["status"] == "FAIL"]
        }, ensure_ascii=False, indent=2))
        return 0 if report["technicalStatus"] == "PASS" else 1
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "validation-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
