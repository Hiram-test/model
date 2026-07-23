#!/usr/bin/env python3
"""使用 FreeCAD GUI（Xvfb 虚拟显示）保存四个可复核视图。

本脚本不修改几何，只设置临时显示属性：
- 隐藏 REFERENCE 骨架；
- 按系统设置区分色；
- 保存轴测、立面、平面和横断面 PNG；
- 每张图片都在日志中记录文件大小。
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui


OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
RENDER_DIR = OUTPUT_DIR / "renders"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_display(obj) -> None:
    role = getattr(obj, "DisplayRole", "")
    if role == "REFERENCE":
        obj.ViewObject.Visibility = False
        return
    name = obj.Name
    if name.startswith("DeckPanel_"):
        obj.ViewObject.ShapeColor = (0.76, 0.62, 0.35)
    elif name.startswith(("LongGirder_", "Crossbeam_")):
        obj.ViewObject.ShapeColor = (0.35, 0.45, 0.58)
    elif name.startswith(("TowerColumn_", "TowerTopBeam_", "TowerCap_", "TowerPile_")):
        obj.ViewObject.ShapeColor = (0.72, 0.72, 0.72)
    elif name.startswith(("MainCable_", "Hanger_", "WindCable_")):
        obj.ViewObject.ShapeColor = (0.18, 0.18, 0.18)
    elif name.startswith("Saddle_"):
        obj.ViewObject.ShapeColor = (0.50, 0.34, 0.16)
    elif name.startswith(("MainAnchorage_", "WindAnchorage_")):
        obj.ViewObject.ShapeColor = (0.60, 0.60, 0.60)
    obj.ViewObject.LineColor = (0.12, 0.12, 0.12)
    obj.ViewObject.DisplayMode = "Flat Lines"


def save_view(view, name: str, width: int = 2400, height: int = 1400) -> dict:
    path = RENDER_DIR / name
    view.fitAll()
    Gui.updateGui()
    view.saveImage(str(path), width, height, "White")
    if not path.exists() or path.stat().st_size < 10_000:
        raise IOError(f"渲染图为空或过小: {path}")
    return {"path": str(path.relative_to(OUTPUT_DIR)), "bytes": path.stat().st_size}


def main() -> int:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    doc = App.openDocument(str(FCSTD_PATH))
    Gui.activeDocument().activeView().setAnimationEnabled(False)
    for obj in doc.Objects:
        if hasattr(obj, "ViewObject") and obj.TypeId == "Part::Feature":
            set_display(obj)
    Gui.updateGui()
    view = Gui.activeDocument().activeView()
    view.setCameraType("Perspective")

    results = {}
    view.viewAxonometric()
    results["axonometric"] = save_view(view, "01-axonometric.png")
    view.setCameraType("Orthographic")
    view.viewFront()
    results["elevation"] = save_view(view, "02-elevation.png")
    view.viewTop()
    results["plan"] = save_view(view, "03-plan.png")
    view.viewRight()
    results["crossSection"] = save_view(view, "04-cross-section.png", 1800, 1400)

    report = {
        "generatedAtUtc": utc_now(),
        "freecadVersion": ".".join(App.Version()[:3]),
        "renders": results,
        "note": "图片来自 FCStd BRep 的 FreeCAD GUI 视图，不用于尺寸量测。"
    }
    (RENDER_DIR / "render_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()
    return 0


try:
    raise SystemExit(main())
except SystemExit:
    raise
except Exception as exc:
    error = {
        "generatedAtUtc": utc_now(),
        "status": "FAIL",
        "exception": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc()
    }
    (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "logs" / "render-failure.json").write_text(
        json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
    try:
        Gui.getMainWindow().close()
    except Exception:
        pass
    raise SystemExit(1)
