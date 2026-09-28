#!/usr/bin/env python3
"""使用 FreeCAD GUI（Xvfb 虚拟显示）保存四个可复核视图。

本脚本不修改 BRep 几何，只设置临时显示属性：
- 隐藏 REFERENCE 骨架；
- 显式打开全部 DISPLAY 对象，不能依赖 FreeCADCmd 保存时的可见性默认值；
- 按系统设置区分色；
- 保存轴测、立面、平面和横断面 PNG；
- 使用 Pillow 逐像素检查，纯白图或内容比例过低必须失败。

文件存在或大于某个字节数并不能证明视图里真的有模型，因此像素检查是正式
fail-closed Hook 的一部分。
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PIL import Image


OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
RENDER_DIR = OUTPUT_DIR / "renders"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_display(obj) -> None:
    """Set deterministic temporary visibility and colour for one Part object."""
    role = getattr(obj, "DisplayRole", "")
    if role == "REFERENCE":
        obj.ViewObject.Visibility = False
        return

    # Headless FreeCADCmd documents can persist all Part objects as hidden.
    # Explicitly restoring visibility is required before fitAll/saveImage.
    obj.ViewObject.Visibility = True
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
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"
    except Exception:
        # Some imported or compound objects expose a different mode list.
        pass


def image_health(path: Path) -> dict:
    """Return deterministic non-white pixel statistics for a saved PNG."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        # A pixel is treated as content when at least one channel is below 245.
        # This ignores white background and near-white antialiasing noise.
        nonwhite = sum(1 for r, g, b in rgb.getdata() if min(r, g, b) < 245)
        total = width * height
        fraction = nonwhite / total if total else 0.0
        extrema = [list(x) for x in rgb.getextrema()]
    return {
        "widthPx": width,
        "heightPx": height,
        "nonWhitePixelCount": nonwhite,
        "nonWhiteFraction": fraction,
        "channelExtrema": extrema,
    }


def save_view(view, name: str, width: int = 2400, height: int = 1400) -> dict:
    path = RENDER_DIR / name
    view.fitAll()
    Gui.updateGui()
    # Coin3D scene updates are asynchronous under Xvfb; a short deterministic
    # delay avoids capturing the white background before the scene is drawn.
    time.sleep(1.0)
    view.saveImage(str(path), width, height, "White")
    if not path.exists() or path.stat().st_size < 10_000:
        raise IOError(f"渲染图不存在或过小: {path}")
    health = image_health(path)
    # Require both an absolute amount of model ink and a small image fraction.
    # For a 2400×1400 view this is intentionally modest but rejects pure white.
    if health["nonWhitePixelCount"] < 2_000 or health["nonWhiteFraction"] < 0.0005:
        raise IOError(f"渲染图无有效模型内容: {path}; health={health}")
    return {"path": str(path.relative_to(OUTPUT_DIR)), "bytes": path.stat().st_size, **health}


def main() -> int:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    if not FCSTD_PATH.exists():
        raise FileNotFoundError(FCSTD_PATH)
    doc = App.openDocument(str(FCSTD_PATH))
    gui_doc = Gui.activeDocument()
    if gui_doc is None:
        raise RuntimeError("FreeCADGui 未创建活动文档；检查 Xvfb/xcb 初始化")

    display_count = 0
    reference_count = 0
    for obj in doc.Objects:
        if hasattr(obj, "ViewObject") and obj.TypeId == "Part::Feature":
            set_display(obj)
            if getattr(obj, "DisplayRole", "") == "REFERENCE":
                reference_count += 1
            else:
                display_count += 1
    if display_count == 0:
        raise RuntimeError("没有可见 DISPLAY Part 对象")

    doc.recompute()
    Gui.updateGui()
    time.sleep(1.0)
    view = gui_doc.activeView()
    results = {}

    try:
        view.setCameraType("Perspective")
    except Exception:
        pass
    view.viewAxonometric()
    results["axonometric"] = save_view(view, "01-axonometric.png")

    try:
        view.setCameraType("Orthographic")
    except Exception:
        pass
    view.viewFront()
    results["elevation"] = save_view(view, "02-elevation.png")
    view.viewTop()
    results["plan"] = save_view(view, "03-plan.png")
    view.viewRight()
    results["crossSection"] = save_view(view, "04-cross-section.png", 1800, 1400)

    report = {
        "generatedAtUtc": utc_now(),
        "freecadVersion": ".".join(App.Version()[:3]),
        "visibleDisplayObjectCount": display_count,
        "hiddenReferenceObjectCount": reference_count,
        "pixelGate": {
            "minimumNonWhitePixelCount": 2_000,
            "minimumNonWhiteFraction": 0.0005,
            "whiteThresholdPerChannel": 245,
        },
        "renders": results,
        "status": "PASS",
        "note": "图片来自修正后 FCStd BRep 的 FreeCAD GUI 视图；像素健康已通过，但图片不用于尺寸量测。",
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
        "traceback": traceback.format_exc(),
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
