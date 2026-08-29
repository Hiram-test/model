#!/usr/bin/env python3
"""Export source-located DXF geometry and run a diagnostic generic render.

The first scanner intentionally performs a broad fidelity scan. This N03
adapter serializes the geometry needed by N04 without interpreting any entity
as an engineering component. The ezdxf drawing add-on render is retained as a
diagnostic only: legacy CAD plot/color combinations can produce a blank image
even when entity export is complete. Blank generic renders therefore request
the independent ``manual_render_geometry.py`` fallback; they do not erase or
invalidate successfully exported source-located geometry.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf.addons.drawing import Frontend, RenderContext, config
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import LayoutProperties


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def point(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        try:
            values = list(value)
            while len(values) < 3:
                values.append(0.0)
            return [float(values[0]), float(values[1]), float(values[2])]
        except Exception:
            return None


def points(values: Iterable[Any]) -> list[list[float]]:
    output = []
    for value in values:
        converted = point(value)
        if converted is not None:
            output.append(converted)
    return output


def entity_bbox(entity: Any) -> dict[str, list[float]] | None:
    try:
        box = ezbbox.extents([entity], fast=False)
        if not box.has_data:
            return None
        return {"min": point(box.extmin), "max": point(box.extmax), "size": point(box.size)}
    except Exception:
        return None


def text_value(entity: Any) -> str | None:
    kind = entity.dxftype()
    try:
        if kind in {"TEXT", "ATTRIB", "ATTDEF"}:
            return str(entity.dxf.text)
        if kind == "MTEXT":
            return str(entity.plain_text())
        if kind == "DIMENSION":
            return str(entity.dxf.text)
    except Exception:
        return None
    return None


def safe_attr(namespace: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(namespace, name)
    except Exception:
        return default


def geometry(entity: Any) -> tuple[dict[str, Any], bool]:
    kind = entity.dxftype()
    dxf = entity.dxf
    try:
        if kind == "LINE":
            return {"start": point(dxf.start), "end": point(dxf.end)}, True
        if kind in {"XLINE", "RAY"}:
            return {"start": point(dxf.start), "unitVector": point(dxf.unitvector)}, True
        if kind == "CIRCLE":
            return {"center": point(dxf.center), "radius": float(dxf.radius), "extrusion": point(safe_attr(dxf, "extrusion"))}, True
        if kind == "ARC":
            return {"center": point(dxf.center), "radius": float(dxf.radius), "startAngleDeg": float(dxf.start_angle), "endAngleDeg": float(dxf.end_angle), "extrusion": point(safe_attr(dxf, "extrusion"))}, True
        if kind == "ELLIPSE":
            return {"center": point(dxf.center), "majorAxis": point(dxf.major_axis), "ratio": float(dxf.ratio), "startParam": float(dxf.start_param), "endParam": float(dxf.end_param), "extrusion": point(safe_attr(dxf, "extrusion"))}, True
        if kind == "LWPOLYLINE":
            values = []
            for x, y, start_width, end_width, bulge in entity.get_points("xyseb"):
                values.append({"point": [float(x), float(y), float(safe_attr(dxf, "elevation", 0.0) or 0.0)], "startWidth": float(start_width), "endWidth": float(end_width), "bulge": float(bulge)})
            return {"closed": bool(entity.closed), "vertices": values, "extrusion": point(safe_attr(dxf, "extrusion"))}, True
        if kind == "POLYLINE":
            values = []
            for vertex in entity.vertices:
                values.append({"point": point(vertex.dxf.location), "startWidth": float(safe_attr(vertex.dxf, "start_width", 0.0) or 0.0), "endWidth": float(safe_attr(vertex.dxf, "end_width", 0.0) or 0.0), "bulge": float(safe_attr(vertex.dxf, "bulge", 0.0) or 0.0)})
            return {"closed": bool(entity.is_closed), "vertices": values, "mode": entity.get_mode()}, True
        if kind == "SPLINE":
            return {"degree": int(dxf.degree), "closed": bool(entity.closed), "periodic": bool(entity.is_periodic), "controlPoints": points(entity.control_points), "fitPoints": points(entity.fit_points), "knots": [float(x) for x in entity.knots()], "weights": [float(x) for x in entity.weights()]}, True
        if kind in {"3DFACE", "SOLID", "TRACE"}:
            return {"vertices": [point(safe_attr(dxf, f"vtx{i}")) for i in range(4)]}, True
        if kind == "POINT":
            return {"location": point(dxf.location)}, True
        if kind in {"TEXT", "ATTRIB", "ATTDEF"}:
            return {"insert": point(dxf.insert), "alignPoint": point(safe_attr(dxf, "align_point")), "height": float(safe_attr(dxf, "height", 0.0) or 0.0), "rotationDeg": float(safe_attr(dxf, "rotation", 0.0) or 0.0), "text": text_value(entity), "style": str(safe_attr(dxf, "style", ""))}, True
        if kind == "MTEXT":
            return {"insert": point(dxf.insert), "charHeight": float(dxf.char_height), "width": float(safe_attr(dxf, "width", 0.0) or 0.0), "rotationDeg": float(safe_attr(dxf, "rotation", 0.0) or 0.0), "text": text_value(entity), "style": str(safe_attr(dxf, "style", ""))}, True
        if kind == "DIMENSION":
            try:
                measurement = float(entity.get_measurement())
            except Exception:
                measurement = None
            return {"dimtype": int(safe_attr(dxf, "dimtype", 0) or 0), "measurement": measurement, "textOverride": text_value(entity), "defpoint": point(safe_attr(dxf, "defpoint")), "defpoint2": point(safe_attr(dxf, "defpoint2")), "defpoint3": point(safe_attr(dxf, "defpoint3")), "defpoint4": point(safe_attr(dxf, "defpoint4")), "defpoint5": point(safe_attr(dxf, "defpoint5")), "angleDeg": float(safe_attr(dxf, "angle", 0.0) or 0.0), "dimstyle": str(safe_attr(dxf, "dimstyle", ""))}, True
        if kind == "INSERT":
            attributes = []
            for attrib in entity.attribs:
                attributes.append({"handle": safe_attr(attrib.dxf, "handle", ""), "tag": str(safe_attr(attrib.dxf, "tag", "")), "text": str(safe_attr(attrib.dxf, "text", "")), "insert": point(safe_attr(attrib.dxf, "insert"))})
            return {"blockName": str(dxf.name), "insert": point(dxf.insert), "xScale": float(safe_attr(dxf, "xscale", 1.0) or 1.0), "yScale": float(safe_attr(dxf, "yscale", 1.0) or 1.0), "zScale": float(safe_attr(dxf, "zscale", 1.0) or 1.0), "rotationDeg": float(safe_attr(dxf, "rotation", 0.0) or 0.0), "attributes": attributes}, True
        if kind in {"LEADER", "MLEADER"}:
            values = points(getattr(entity, "vertices", [])) if kind == "LEADER" else []
            return {"vertices": values}, kind == "LEADER"
        if kind == "HATCH":
            return {"boundaryPathCount": len(entity.paths), "patternName": str(safe_attr(dxf, "pattern_name", ""))}, False
        if kind == "VIEWPORT":
            return {"center": point(safe_attr(dxf, "center")), "width": float(safe_attr(dxf, "width", 0.0) or 0.0), "height": float(safe_attr(dxf, "height", 0.0) or 0.0), "viewCenterPoint": point(safe_attr(dxf, "view_center_point")), "viewTargetPoint": point(safe_attr(dxf, "view_target_point")), "viewHeight": float(safe_attr(dxf, "view_height", 0.0) or 0.0), "twistAngleRad": float(safe_attr(dxf, "view_twist_angle", 0.0) or 0.0)}, True
    except Exception as exc:
        return {"serializationError": f"{type(exc).__name__}: {exc}"}, False
    return {}, False


def render_layout(doc: Any, layout: Any, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(18, 12), dpi=180, facecolor="white")
    ax = fig.add_axes([0.005, 0.005, 0.99, 0.99], facecolor="white")
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE, color_policy=config.ColorPolicy.BLACK, lineweight_policy=config.LineweightPolicy.RELATIVE_FIXED, min_lineweight=0.12)
    properties = LayoutProperties.from_layout(layout)
    properties.set_colors("#ffffffff")
    Frontend(ctx, backend, config=cfg).draw_layout(layout, finalize=True, layout_properties=properties)
    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(0.015)
    ax.axis("off")
    fig.savefig(output, dpi=180, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)

    with Image.open(output) as image:
        gray = image.convert("L")
        extrema = gray.getextrema()
        histogram = gray.histogram()
        nonwhite = int(sum(histogram[:250]))
        total = int(image.width * image.height)
        return {"png": output.name, "svg": output.with_suffix(".svg").name, "widthPx": image.width, "heightPx": image.height, "grayExtrema": list(extrema), "nonWhitePixelCount": nonwhite, "nonWhiteFraction": nonwhite / total if total else 0.0, "sha256": sha256_file(output)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-report", type=Path, required=True)
    parser.add_argument("--converted-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    scan_report = json.loads(args.scan_report.read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    render_dir = output_dir / "renders_black_on_white"
    output_dir.mkdir(parents=True, exist_ok=True)
    by_dxf = {Path(item["dxf_relpath"]).name: item for item in scan_report.get("drawings", []) if item.get("dxf_relpath")}
    geometry_path = output_dir / "geometry_entities.jsonl.gz"
    render_records = []
    unsupported_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    failures = []
    geometry_record_count = 0

    with gzip.open(geometry_path, "wt", encoding="utf-8") as stream:
        for dxf_path in sorted(args.converted_dir.glob("*.dxf"), key=lambda p: p.name):
            source_record = by_dxf.get(dxf_path.name, {})
            source_relpath = source_record.get("source_relpath", dxf_path.name)
            try:
                doc = ezdxf.readfile(dxf_path)
            except Exception as exc:
                failures.append({"dxf": dxf_path.name, "stage": "read", "error": f"{type(exc).__name__}: {exc}"})
                continue

            for layout in doc.layouts:
                direct_entities = list(layout)
                for entity in direct_entities:
                    kind = entity.dxftype()
                    entity_counts[kind] += 1
                    geometry_record_count += 1
                    payload, supported = geometry(entity)
                    if not supported:
                        unsupported_counts[kind] += 1
                    record = {"recordVersion": "1.0.0", "sourceRelpath": source_relpath, "derivedDxf": dxf_path.name, "layout": layout.name, "handle": str(safe_attr(entity.dxf, "handle", "")), "ownerHandle": str(safe_attr(entity.dxf, "owner", "")), "type": kind, "layer": str(safe_attr(entity.dxf, "layer", "")), "linetype": str(safe_attr(entity.dxf, "linetype", "BYLAYER")), "color": int(safe_attr(entity.dxf, "color", 256) or 256), "trueColor": safe_attr(entity.dxf, "true_color"), "invisible": int(safe_attr(entity.dxf, "invisible", 0) or 0), "bbox": entity_bbox(entity), "supportedForGeometry": supported, "geometry": payload}
                    stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

                image_name = f"{Path(source_relpath).stem}__{layout.name.replace('/', '_')}.png"
                try:
                    render = render_layout(doc, layout, render_dir / image_name)
                    render.update({"sourceRelpath": source_relpath, "derivedDxf": dxf_path.name, "layout": layout.name, "directEntityCount": len(direct_entities), "criticalRender": layout.name.lower() == "model"})
                    render_records.append(render)
                    if render["criticalRender"] and render["nonWhitePixelCount"] == 0:
                        failures.append({"dxf": dxf_path.name, "layout": layout.name, "stage": "generic_render", "error": "critical model-space render is blank"})
                except Exception as exc:
                    failures.append({"dxf": dxf_path.name, "layout": layout.name, "stage": "generic_render", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})

    dxf_count = len(list(args.converted_dir.glob("*.dxf")))
    expected_dxf_count = len(by_dxf)
    hard_failures = [item for item in failures if item.get("stage") == "read"]
    generic_render_warnings = [item for item in failures if item.get("stage") == "generic_render"]
    geometry_export_ok = dxf_count == expected_dxf_count and geometry_record_count > 0 and not hard_failures
    report = {
        "adapterRole": "N03_SOURCE_LOCATED_GEOMETRY_EXPORT_WITH_DIAGNOSTIC_RENDER",
        "gateAuthority": False,
        "ezdxfVersion": getattr(ezdxf, "__version__", "unknown"),
        "dxfCount": dxf_count,
        "expectedDxfCount": expected_dxf_count,
        "geometryRecordCount": geometry_record_count,
        "geometryExportOk": geometry_export_ok,
        "unsupportedGeometryCounts": dict(sorted(unsupported_counts.items())),
        "entityCounts": dict(sorted(entity_counts.items())),
        "geometryJsonlGz": geometry_path.name,
        "geometryJsonlGzSha256": sha256_file(geometry_path),
        "renders": render_records,
        "criticalBlankRenderCount": sum(1 for item in generic_render_warnings if item.get("error") == "critical model-space render is blank"),
        "fallbackRenderRequired": bool(generic_render_warnings),
        "genericRenderWarnings": generic_render_warnings,
        "hardFailures": hard_failures,
        "failures": failures,
        "separationOfResponsibilities": "This adapter gates source-located geometry export. manual_render_geometry.py separately gates visible model-space evidence.",
    }
    (output_dir / "geometry_export_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dxfCount": dxf_count, "geometryRecords": geometry_record_count, "geometryExportOk": geometry_export_ok, "genericRenderWarningCount": len(generic_render_warnings), "hardFailureCount": len(hard_failures)}, ensure_ascii=False, indent=2))
    return 0 if geometry_export_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
