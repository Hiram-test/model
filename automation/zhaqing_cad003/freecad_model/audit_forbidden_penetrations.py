#!/usr/bin/env python3
"""独立检查最终 FCStd 中的禁止实体穿透。

只对工程上应采用端面接触、显式间隙或通道的对象族做检查。先以包围盒筛选，
再调用 OpenCASCADE `common()` 计算公共体积；公共体积超过 1e-3 mm³ 即失败。
锚固端因当前接口仍为有界假定，不在本技术穿透检查中假装已经闭合。
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import FreeCAD as App


OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
VOLUME_TOLERANCE = 1e-3
PAIR_FAMILIES = [
    ("Crossbeam", "LongGirder"),
    ("Crossbeam", "TowerColumn"),
    ("LongGirder", "TowerColumn"),
    ("DeckPanel", "TowerColumn"),
    ("TowerColumn", "TowerTopBeam"),
    ("TowerTopBeam", "Saddle"),
    ("Saddle", "MainCable"),
    ("Hanger", "MainCable"),
    ("TowerPile", "TowerCap"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def positive_bbox_overlap(a: App.DocumentObject, b: App.DocumentObject, tolerance: float = 1e-6) -> bool:
    ba = a.Shape.BoundBox
    bb = b.Shape.BoundBox
    overlaps = (
        min(ba.XMax, bb.XMax) - max(ba.XMin, bb.XMin),
        min(ba.YMax, bb.YMax) - max(ba.YMin, bb.YMin),
        min(ba.ZMax, bb.ZMax) - max(ba.ZMin, bb.ZMin),
    )
    return all(value > tolerance for value in overlaps)


def run_audit() -> dict[str, Any]:
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    doc = App.openDocument(str(FCSTD_PATH))
    objects = [
        obj for obj in doc.Objects
        if obj.TypeId == "Part::Feature" and getattr(obj, "DisplayRole", "") != "REFERENCE"
    ]
    prefixes = sorted({prefix for pair in PAIR_FAMILIES for prefix in pair})
    by_prefix = {
        prefix: [obj for obj in objects if obj.Name.startswith(prefix + "_")]
        for prefix in prefixes
    }

    candidate_count = 0
    bbox_overlap_count = 0
    penetrations: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    family_stats: list[dict[str, Any]] = []

    for prefix_a, prefix_b in PAIR_FAMILIES:
        family_candidates = 0
        family_evaluated = 0
        family_penetrations = 0
        for obj_a in by_prefix[prefix_a]:
            for obj_b in by_prefix[prefix_b]:
                candidate_count += 1
                family_candidates += 1
                if not positive_bbox_overlap(obj_a, obj_b):
                    continue
                bbox_overlap_count += 1
                family_evaluated += 1
                try:
                    common = obj_a.Shape.common(obj_b.Shape)
                    volume = float(common.Volume)
                    if volume > VOLUME_TOLERANCE:
                        family_penetrations += 1
                        penetrations.append({
                            "objectA": obj_a.Name,
                            "objectB": obj_b.Name,
                            "commonVolumeMm3": volume,
                            "family": [prefix_a, prefix_b],
                        })
                except Exception as exc:
                    errors.append({
                        "objectA": obj_a.Name,
                        "objectB": obj_b.Name,
                        "family": [prefix_a, prefix_b],
                        "exception": type(exc).__name__,
                        "message": str(exc),
                    })
        family_stats.append({
            "family": [prefix_a, prefix_b],
            "candidatePairs": family_candidates,
            "occEvaluatedPairs": family_evaluated,
            "penetrationCount": family_penetrations,
        })

    status = "PASS" if not penetrations and not errors else "FAIL"
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": status,
        "volumeToleranceMm3": VOLUME_TOLERANCE,
        "pairFamilies": [list(pair) for pair in PAIR_FAMILIES],
        "candidatePairs": candidate_count,
        "occEvaluatedPairs": bbox_overlap_count,
        "familyStatistics": family_stats,
        "penetrations": penetrations,
        "errors": errors,
        "excludedInterfaces": [
            "主缆—主锚碇：A-MAIN-ANCHOR-Z-001 未关闭",
            "风缆—风缆锚碇：U-WIND-001 未关闭",
            "风缆—横梁：局部连接件尚未形成独立 Part/representation contract"
        ]
    }
    (OUTPUT_DIR / "forbidden_penetration_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    App.closeDocument(doc.Name)
    return report


def main() -> int:
    try:
        report = run_audit()
        print(json.dumps({
            "status": report["status"],
            "candidatePairs": report["candidatePairs"],
            "occEvaluatedPairs": report["occEvaluatedPairs"],
            "penetrationCount": len(report["penetrations"]),
            "errorCount": len(report["errors"]),
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
        (OUTPUT_DIR / "logs" / "penetration-audit-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
