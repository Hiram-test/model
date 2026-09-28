#!/usr/bin/env python3
"""Deterministic fallback renderer for N03 source-located DXF geometry.

The ezdxf drawing add-on can legitimately fail to display legacy CAD color /
plot-style combinations even when entity extraction is complete.  This adapter
renders the serialized geometry records directly, black on white, and checks
that every source drawing's model space contains visible ink.  It makes no
engineering interpretation and has no Gate authority.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

DRAWABLE = {"LINE", "ARC", "CIRCLE", "ELLIPSE", "LWPOLYLINE", "POLYLINE", "SPLINE", "SOLID", "TRACE", "3DFACE"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def xy(value: Any) -> tuple[float, float] | None:
    try:
        return float(value[0]), float(value[1])
    except Exception:
        return None


def sample_arc(center: Any, radius: float, start_deg: float, end_deg: float, count: int = 80) -> tuple[list[float], list[float]]:
    c = xy(center)
    if c is None or radius <= 0:
        return [], []
    while end_deg < start_deg:
        end_deg += 360.0
    span = end_deg - start_deg
    count = max(12, min(240, int(abs(span) / 3.0) + 2, count))
    angles = [math.radians(start_deg + span * i / (count - 1)) for i in range(count)]
    return [c[0] + radius * math.cos(a) for a in angles], [c[1] + radius * math.sin(a) for a in angles]


def sample_ellipse(payload: dict[str, Any], count: int = 100) -> tuple[list[float], list[float]]:
    center = xy(payload.get("center"))
    major = xy(payload.get("majorAxis"))
    if center is None or major is None:
        return [], []
    ratio = float(payload.get("ratio", 1.0) or 1.0)
    start = float(payload.get("startParam", 0.0) or 0.0)
    end = float(payload.get("endParam", 2 * math.pi) or 2 * math.pi)
    while end < start:
        end += 2 * math.pi
    mx, my = major
    minor = (-my * ratio, mx * ratio)
    params = [start + (end - start) * i / (count - 1) for i in range(count)]
    return (
        [center[0] + mx * math.cos(t) + minor[0] * math.sin(t) for t in params],
        [center[1] + my * math.cos(t) + minor[1] * math.sin(t) for t in params],
    )


def draw_row(ax: Any, row: dict[str, Any]) -> bool:
    kind = row.get("type")
    payload = row.get("geometry") or {}
    try:
        if kind == "LINE":
            p1, p2 = xy(payload.get("start")), xy(payload.get("end"))
            if p1 and p2:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], linewidth=0.35)
                return True
        elif kind == "CIRCLE":
            xs, ys = sample_arc(payload.get("center"), float(payload.get("radius", 0.0)), 0.0, 360.0, 120)
            if xs:
                ax.plot(xs, ys, linewidth=0.35)
                return True
        elif kind == "ARC":
            xs, ys = sample_arc(payload.get("center"), float(payload.get("radius", 0.0)), float(payload.get("startAngleDeg", 0.0)), float(payload.get("endAngleDeg", 0.0)), 120)
            if xs:
                ax.plot(xs, ys, linewidth=0.35)
                return True
        elif kind == "ELLIPSE":
            xs, ys = sample_ellipse(payload)
            if xs:
                ax.plot(xs, ys, linewidth=0.35)
                return True
        elif kind in {"LWPOLYLINE", "POLYLINE"}:
            vertices = [xy(v.get("point")) for v in payload.get("vertices", [])]
            vertices = [p for p in vertices if p is not None]
            if len(vertices) >= 2:
                if payload.get("closed"):
                    vertices.append(vertices[0])
                ax.plot([p[0] for p in vertices], [p[1] for p in vertices], linewidth=0.35)
                return True
        elif kind == "SPLINE":
            values = payload.get("fitPoints") or payload.get("controlPoints") or []
            vertices = [xy(v) for v in values]
            vertices = [p for p in vertices if p is not None]
            if len(vertices) >= 2:
                ax.plot([p[0] for p in vertices], [p[1] for p in vertices], linewidth=0.35)
                return True
        elif kind in {"SOLID", "TRACE", "3DFACE"}:
            vertices = [xy(v) for v in payload.get("vertices", [])]
            vertices = [p for p in vertices if p is not None]
            if len(vertices) >= 3:
                vertices.append(vertices[0])
                ax.plot([p[0] for p in vertices], [p[1] for p in vertices], linewidth=0.25)
                return True
    except (TypeError, ValueError, OverflowError):
        return False
    return False


def bbox_for_rows(rows: Iterable[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    mins_x: list[float] = []
    mins_y: list[float] = []
    maxs_x: list[float] = []
    maxs_y: list[float] = []
    for row in rows:
        if row.get("type") not in DRAWABLE:
            continue
        bbox = row.get("bbox") or {}
        pmin, pmax = xy(bbox.get("min")), xy(bbox.get("max"))
        if pmin and pmax and all(math.isfinite(v) for v in (*pmin, *pmax)):
            mins_x.append(pmin[0]); mins_y.append(pmin[1]); maxs_x.append(pmax[0]); maxs_y.append(pmax[1])
    if not mins_x:
        return None
    return min(mins_x), min(mins_y), max(maxs_x), max(maxs_y)


def render_source(source: str, rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    box = bbox_for_rows(rows)
    if box is None:
        raise RuntimeError(f"no drawable geometry for {source}")
    min_x, min_y, max_x, max_y = box
    width, height = max_x - min_x, max_y - min_y
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid drawing extent for {source}: {box}")
    pad = max(width, height) * 0.015

    fig = plt.figure(figsize=(18, 12), dpi=180, facecolor="white")
    ax = fig.add_axes([0.005, 0.005, 0.99, 0.99], facecolor="white")
    counts: Counter[str] = Counter()
    drawn = 0
    for row in rows:
        counts[row.get("type", "UNKNOWN")] += 1
        if draw_row(ax, row):
            drawn += 1
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.set_ylim(min_y - pad, max_y + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)

    with Image.open(output) as image:
        gray = image.convert("L")
        histogram = gray.histogram()
        nonwhite = int(sum(histogram[:250]))
        total = int(image.width * image.height)
        return {
            "sourceRelpath": source,
            "layout": "Model",
            "png": output.name,
            "svg": output.with_suffix(".svg").name,
            "widthPx": image.width,
            "heightPx": image.height,
            "drawableEntityCount": drawn,
            "directEntityCounts": dict(sorted(counts.items())),
            "drawingExtent": [min_x, min_y, max_x, max_y],
            "nonWhitePixelCount": nonwhite,
            "nonWhiteFraction": nonwhite / total if total else 0.0,
            "sha256": sha256_file(output),
        }


def make_contact_sheet(images: list[Path], output: Path) -> None:
    if not images:
        return
    tile_w, tile_h, label_h = 1100, 700, 54
    cols = 2
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (tile_w * cols, (tile_h + label_h) * rows), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
    for index, path in enumerate(images):
        row, col = divmod(index, cols)
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((tile_w - 20, tile_h - 20))
            x = col * tile_w + (tile_w - image.width) // 2
            y = row * (tile_h + label_h) + label_h + (tile_h - image.height) // 2
            canvas.paste(image, (x, y))
        draw.text((col * tile_w + 12, row * (tile_h + label_h) + 10), path.stem, fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=90, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-jsonl-gz", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    render_dir = output_dir / "modelspace_renders"
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with gzip.open(args.geometry_jsonl_gz, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("layout", "")).lower() == "model":
                grouped[row.get("sourceRelpath", "UNKNOWN")].append(row)

    failures: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    images: list[Path] = []
    for index, source in enumerate(sorted(grouped), start=1):
        output = render_dir / f"{index:02d}-{Path(source).stem}.png"
        try:
            record = render_source(source, grouped[source], output)
            records.append(record)
            images.append(output)
            if record["drawableEntityCount"] <= 0 or record["nonWhitePixelCount"] < 100:
                failures.append({"sourceRelpath": source, "error": "model-space render lacks visible geometry", "record": record})
        except Exception as exc:
            failures.append({"sourceRelpath": source, "error": f"{type(exc).__name__}: {exc}"})

    make_contact_sheet(images, output_dir / "modelspace_contact_sheet.jpg")
    report = {
        "adapterRole": "N03_MANUAL_GEOMETRY_RENDER_HEALTH",
        "gateAuthority": False,
        "inputSha256": sha256_file(args.geometry_jsonl_gz),
        "sourceDrawingCount": len(grouped),
        "successfulRenderCount": len(records),
        "requiredSourceDrawingCount": 12,
        "records": records,
        "failures": failures,
    }
    (output_dir / "manual_render_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sourceDrawingCount": len(grouped), "successfulRenderCount": len(records), "failureCount": len(failures)}, ensure_ascii=False, indent=2))
    return 0 if len(grouped) == 12 and len(records) == 12 and not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
