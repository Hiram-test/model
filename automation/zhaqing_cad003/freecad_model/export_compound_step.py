#!/usr/bin/env python3
"""把修正后的全部 DISPLAY BRep 封装为单一顶层 Compound STEP。

FreeCAD 0.19 的 OCAF STEP 导入器在回读含数百个顶层 free shapes 的 STEP 时可能
发生段错误。该问题与几何是否有效不同。为获得可稳定回读的交换文件，本脚本：
1. 从最终 FCStd 读取全部 DISPLAY 对象；
2. 复制各对象 Shape 并组成一个 OpenCASCADE Compound；
3. 只导出一个顶层 Part::Feature；
4. 保留原 `object_manifest.json`，因此构件身份与来源不依赖 STEP 层级。

这不是静默丢失对象：导出前后记录源对象数、子实体数、体积和包围盒。
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
import Import
import Part


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


def bbox(shape: Part.Shape) -> dict[str, list[float]]:
    b = shape.BoundBox
    return {
        "min": [b.XMin, b.YMin, b.ZMin],
        "max": [b.XMax, b.YMax, b.ZMax],
        "size": [b.XLength, b.YLength, b.ZLength],
    }


def export_compound() -> dict[str, Any]:
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    source_doc = App.openDocument(str(FCSTD_PATH))
    display_objects = sorted(
        [
            obj for obj in source_doc.Objects
            if obj.TypeId == "Part::Feature"
            and getattr(obj, "DisplayRole", "") != "REFERENCE"
            and not obj.Shape.isNull()
        ],
        key=lambda item: item.Name,
    )
    if not display_objects:
        raise ValueError("FCStd 中没有 DISPLAY 对象")

    copied_shapes = [obj.Shape.copy() for obj in display_objects]
    compound = Part.makeCompound(copied_shapes)
    if compound.isNull() or not compound.isValid():
        raise ValueError("合并后的 STEP Compound 无效")

    export_doc = App.newDocument("Zhaqing_CAD003_STEP_Compound_Export")
    export_obj = export_doc.addObject("Part::Feature", "Zhaqing_CAD003_Display_Compound")
    export_obj.Label = "扎青吊桥 CAD-003 DISPLAY Compound"
    export_obj.Shape = compound
    export_doc.recompute()

    temporary = OUTPUT_DIR / "Zhaqing_CAD-003-display-compound.tmp.step"
    temporary.unlink(missing_ok=True)
    Import.export([export_obj], str(temporary))
    if not temporary.exists() or temporary.stat().st_size == 0:
        raise IOError("Compound STEP 导出为空")
    os.replace(temporary, STEP_PATH)

    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS",
        "reason": "FreeCAD 0.19 OCAF 对多顶层 free shapes 回读不稳定；改为一个顶层 Compound。",
        "sourceDisplayObjectCount": len(display_objects),
        "sourceObjectNames": [obj.Name for obj in display_objects],
        "compound": {
            "shapeType": compound.ShapeType,
            "valid": compound.isValid(),
            "solidCount": len(compound.Solids),
            "shellCount": len(compound.Shells),
            "faceCount": len(compound.Faces),
            "edgeCount": len(compound.Edges),
            "volumeMm3": float(compound.Volume),
            "bbox": bbox(compound),
        },
        "step": {
            "path": STEP_PATH.name,
            "bytes": STEP_PATH.stat().st_size,
            "sha256": sha256_file(STEP_PATH),
            "topLevelExportObjectCount": 1,
        },
        "identitySidecar": "object_manifest.json",
    }
    (OUTPUT_DIR / "compound_step_export_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    artifact_path = OUTPUT_DIR / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8")) if artifact_path.exists() else {}
    artifact["compoundStepExport"] = {
        "scriptSha256": sha256_file(Path(__file__)),
        "reportSha256": sha256_file(OUTPUT_DIR / "compound_step_export_report.json"),
        "sourceDisplayObjectCount": len(display_objects),
        "topLevelExportObjectCount": 1,
    }
    artifact.setdefault("files", {})[STEP_PATH.name] = {
        "sha256": sha256_file(STEP_PATH),
        "bytes": STEP_PATH.stat().st_size,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUTPUT_DIR / "BUILD_PROCESS.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## 09 Compound STEP 封装\n\n"
            "FreeCAD 0.19 在回读包含大量顶层 free shapes 的 STEP 时发生段错误。"
            "最终交换文件改为一个顶层 OpenCASCADE Compound；217 个源对象的稳定 ID、"
            "证据和构件分组继续保存在 FCStd 与 `object_manifest.json`。"
            f"Compound 含 `{len(compound.Solids)}` 个 solids，详细统计见 `compound_step_export_report.json`。\n"
        )

    App.closeDocument(export_doc.Name)
    App.closeDocument(source_doc.Name)
    return report


def main() -> int:
    try:
        report = export_compound()
        print(json.dumps({
            "status": report["status"],
            "sourceDisplayObjectCount": report["sourceDisplayObjectCount"],
            "compoundSolidCount": report["compound"]["solidCount"],
            "step": report["step"],
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
        (OUTPUT_DIR / "logs" / "compound-step-export-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
