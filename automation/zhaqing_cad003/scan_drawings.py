#!/usr/bin/env python3
"""Deterministically inventory, convert, inspect, and render the Zhaqing DWG inputs.

This is an N02/N03 diagnostic adapter, not a Gate authority.  It never assigns
PASS/PASS_WITH_BOUNDS/BLOCKED.  It records tool output and evidence candidates
so the independent gate evaluator can make that decision later.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import ezdxf
    from ezdxf import bbox as ezbbox
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
except Exception as exc:  # pragma: no cover - dependency gate
    raise SystemExit(f"ezdxf import failed: {exc}")

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover - dependency gate
    raise SystemExit(f"Pillow import failed: {exc}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class CommandAttempt:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class DrawingRecord:
    source_relpath: str
    source_sha256: str
    source_bytes: int
    conversion_status: str
    dxf_relpath: str | None
    dxf_sha256: str | None
    dxf_bytes: int | None
    dxf_version: str | None
    insunits: int | None
    layouts: list[dict[str, Any]]
    entity_counts: dict[str, int]
    layers: list[str]
    dimension_count: int
    text_count: int
    warning_count: int
    errors: list[str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return " ".join(text.replace("\\P", " ").replace("\n", " ").split())


def run_command(argv: list[str], cwd: Path) -> CommandAttempt:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        errors="replace",
        check=False,
    )
    return CommandAttempt(
        argv=argv,
        returncode=proc.returncode,
        stdout=proc.stdout[-100_000:],
        stderr=proc.stderr[-100_000:],
    )


def convert_dwg(source: Path, target: Path, log_path: Path) -> tuple[bool, list[CommandAttempt]]:
    """Convert DWG to DXF using deterministic approved fallbacks.

    The first successful output wins; every attempt is logged.  No source file is
    modified.  Different converters can be compared later because the exact
    executable, arguments, status, and bytes are retained.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[CommandAttempt] = []
    tools = {name: shutil.which(name) for name in ("dwg2dxf", "dwgread")}

    candidates: list[list[str]] = []
    if tools["dwg2dxf"]:
        candidates.extend(
            [
                [tools["dwg2dxf"], "-o", str(target), str(source)],
                [tools["dwg2dxf"], str(source), "-o", str(target)],
            ]
        )
    if tools["dwgread"]:
        candidates.extend(
            [
                [tools["dwgread"], "-O", "DXF", "-o", str(target), str(source)],
                [tools["dwgread"], "-o", str(target), "-O", "DXF", str(source)],
            ]
        )

    working = target.parent / (target.stem + "_conversion")
    working.mkdir(parents=True, exist_ok=True)

    for argv in candidates:
        target.unlink(missing_ok=True)
        attempt = run_command(argv, working)
        attempts.append(attempt)
        if target.exists() and target.stat().st_size > 0:
            break
        # Some LibreDWG versions ignore -o and emit beside the input/current dir.
        emitted = sorted(
            [p for p in working.glob("*.dxf") if p.stat().st_size > 0],
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
        if emitted:
            shutil.move(str(emitted[0]), str(target))
            break

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "source": str(source),
                "target": str(target),
                "available_tools": tools,
                "attempts": [asdict(a) for a in attempts],
                "success": target.exists() and target.stat().st_size > 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return target.exists() and target.stat().st_size > 0, attempts


def safe_bbox(entities: Iterable[Any]) -> dict[str, list[float]] | None:
    try:
        box = ezbbox.extents(entities, fast=True)
        if not box.has_data:
            return None
        return {
            "min": [float(box.extmin.x), float(box.extmin.y), float(box.extmin.z)],
            "max": [float(box.extmax.x), float(box.extmax.y), float(box.extmax.z)],
            "size": [float(box.size.x), float(box.size.y), float(box.size.z)],
        }
    except Exception:
        return None


def dimension_measurement(entity: Any) -> float | None:
    for getter in (
        lambda: entity.get_measurement(),
        lambda: entity.dxf.actual_measurement,
    ):
        try:
            value = getter()
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def extract_text(entity: Any) -> str:
    kind = entity.dxftype()
    try:
        if kind == "TEXT":
            return clean_text(entity.dxf.text)
        if kind == "MTEXT":
            try:
                return clean_text(entity.plain_text())
            except Exception:
                return clean_text(entity.text)
        if kind == "ATTRIB":
            return clean_text(entity.dxf.text)
        if kind == "DIMENSION":
            return clean_text(entity.dxf.text)
    except Exception:
        return ""
    return ""


def point_tuple(value: Any) -> list[float] | None:
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        try:
            vals = list(value)
            while len(vals) < 3:
                vals.append(0.0)
            return [float(vals[0]), float(vals[1]), float(vals[2])]
        except Exception:
            return None


def entity_location(entity: Any) -> list[float] | None:
    for attr in ("insert", "location", "center", "defpoint"):
        try:
            return point_tuple(getattr(entity.dxf, attr))
        except Exception:
            pass
    return None


def render_layout(doc: Any, layout: Any, output: Path, warnings: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig = plt.figure(figsize=(16, 10), dpi=160)
        ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(layout, finalize=True)
        ax.set_aspect("equal", adjustable="datalim")
        ax.margins(0.02)
        ax.axis("off")
        fig.savefig(output, dpi=160, bbox_inches="tight", pad_inches=0.03)
        plt.close(fig)
    except Exception as exc:
        warnings.append(f"render {layout.name}: {type(exc).__name__}: {exc}")
        plt.close("all")


def inspect_dxf(
    dxf_path: Path,
    rel_source: str,
    render_dir: Path,
    dimension_rows: list[dict[str, Any]],
    text_rows: list[dict[str, Any]],
    entity_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:
        return {}, warnings, [f"DXF read failed: {type(exc).__name__}: {exc}"]

    layers = sorted({layer.dxf.name for layer in doc.layers})
    all_counts: Counter[str] = Counter()
    layout_summaries: list[dict[str, Any]] = []

    for layout in doc.layouts:
        layout_counts: Counter[str] = Counter()
        entities = list(layout)
        for entity in entities:
            kind = entity.dxftype()
            layout_counts[kind] += 1
            all_counts[kind] += 1
            entity_rows.append(
                {
                    "source": rel_source,
                    "layout": layout.name,
                    "handle": getattr(entity.dxf, "handle", ""),
                    "type": kind,
                    "layer": getattr(entity.dxf, "layer", ""),
                    "location": json.dumps(entity_location(entity), ensure_ascii=False),
                }
            )
            text = extract_text(entity)
            if text:
                text_rows.append(
                    {
                        "source": rel_source,
                        "layout": layout.name,
                        "handle": getattr(entity.dxf, "handle", ""),
                        "type": kind,
                        "layer": getattr(entity.dxf, "layer", ""),
                        "text": text,
                        "location": json.dumps(entity_location(entity), ensure_ascii=False),
                    }
                )
            if kind == "DIMENSION":
                dimension_rows.append(
                    {
                        "source": rel_source,
                        "layout": layout.name,
                        "handle": getattr(entity.dxf, "handle", ""),
                        "layer": getattr(entity.dxf, "layer", ""),
                        "dimtype": getattr(entity.dxf, "dimtype", ""),
                        "measurement": dimension_measurement(entity),
                        "text_override": clean_text(getattr(entity.dxf, "text", "")),
                        "defpoint": json.dumps(point_tuple(getattr(entity.dxf, "defpoint", None)), ensure_ascii=False),
                        "defpoint2": json.dumps(point_tuple(getattr(entity.dxf, "defpoint2", None)), ensure_ascii=False),
                        "defpoint3": json.dumps(point_tuple(getattr(entity.dxf, "defpoint3", None)), ensure_ascii=False),
                    }
                )

        image_name = f"{Path(rel_source).stem}__{layout.name.replace('/', '_')}.png"
        render_layout(doc, layout, render_dir / image_name, warnings)
        layout_summaries.append(
            {
                "name": layout.name,
                "entity_counts": dict(sorted(layout_counts.items())),
                "bbox": safe_bbox(entities),
                "render": str((render_dir / image_name).name),
            }
        )

    header = doc.header
    summary = {
        "dxf_version": getattr(doc, "dxfversion", None),
        "insunits": int(header.get("$INSUNITS", 0) or 0),
        "measurement": int(header.get("$MEASUREMENT", 0) or 0),
        "extmin": point_tuple(header.get("$EXTMIN")),
        "extmax": point_tuple(header.get("$EXTMAX")),
        "layers": layers,
        "entity_counts": dict(sorted(all_counts.items())),
        "layouts": layout_summaries,
    }
    return summary, warnings, errors


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_contact_sheets(render_dir: Path, output_dir: Path) -> list[str]:
    images = sorted(render_dir.glob("*.png"))
    if not images:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    page_size = 4
    thumb_w, thumb_h = 1200, 760
    label_h = 54
    canvas_w, canvas_h = thumb_w * 2, (thumb_h + label_h) * 2
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 26)
    except Exception:
        font = ImageFont.load_default()

    for page_index in range(0, len(images), page_size):
        canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, path in enumerate(images[page_index : page_index + page_size]):
            row, col = divmod(slot, 2)
            with Image.open(path) as source:
                source = source.convert("RGB")
                source.thumbnail((thumb_w - 20, thumb_h - 20))
                x = col * thumb_w + (thumb_w - source.width) // 2
                y = row * (thumb_h + label_h) + label_h + (thumb_h - source.height) // 2
                canvas.paste(source, (x, y))
            draw.text((col * thumb_w + 12, row * (thumb_h + label_h) + 10), path.stem, fill="black", font=font)
        out = output_dir / f"contact-sheet-{page_index // page_size + 1:02d}.jpg"
        canvas.save(out, quality=90, optimize=True)
        generated.append(out.name)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    converted_dir = output_dir / "converted_dxf"
    render_dir = output_dir / "renders"
    logs_dir = output_dir / "conversion_logs"

    drawings = sorted(source_dir.rglob("*.dwg"), key=lambda p: p.as_posix())
    if not drawings:
        raise SystemExit(f"No DWG files found below {source_dir}")

    records: list[DrawingRecord] = []
    dimension_rows: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    entity_rows: list[dict[str, Any]] = []

    for index, source in enumerate(drawings, start=1):
        rel = source.relative_to(source_dir).as_posix()
        safe_stem = f"{index:02d}-{source.stem}"
        target = converted_dir / f"{safe_stem}.dxf"
        conversion_ok, _ = convert_dwg(source, target, logs_dir / f"{safe_stem}.json")
        errors: list[str] = []
        warnings: list[str] = []
        summary: dict[str, Any] = {}
        if conversion_ok:
            try:
                summary, warnings, errors = inspect_dxf(
                    target,
                    rel,
                    render_dir,
                    dimension_rows,
                    text_rows,
                    entity_rows,
                )
            except Exception:
                errors.append(traceback.format_exc())
        else:
            errors.append("No approved converter produced a non-empty DXF")

        records.append(
            DrawingRecord(
                source_relpath=rel,
                source_sha256=sha256_file(source),
                source_bytes=source.stat().st_size,
                conversion_status="SUCCESS" if conversion_ok else "FAILED",
                dxf_relpath=target.relative_to(output_dir).as_posix() if conversion_ok else None,
                dxf_sha256=sha256_file(target) if conversion_ok else None,
                dxf_bytes=target.stat().st_size if conversion_ok else None,
                dxf_version=summary.get("dxf_version"),
                insunits=summary.get("insunits"),
                layouts=summary.get("layouts", []),
                entity_counts=summary.get("entity_counts", {}),
                layers=summary.get("layers", []),
                dimension_count=sum(1 for row in dimension_rows if row["source"] == rel),
                text_count=sum(1 for row in text_rows if row["source"] == rel),
                warning_count=len(warnings),
                errors=errors + warnings,
            )
        )

    write_csv(
        output_dir / "dimension_candidates.csv",
        dimension_rows,
        ["source", "layout", "handle", "layer", "dimtype", "measurement", "text_override", "defpoint", "defpoint2", "defpoint3"],
    )
    write_csv(
        output_dir / "text_index.csv",
        text_rows,
        ["source", "layout", "handle", "type", "layer", "text", "location"],
    )
    write_csv(
        output_dir / "entity_index.csv",
        entity_rows,
        ["source", "layout", "handle", "type", "layer", "location"],
    )
    contact_sheets = make_contact_sheets(render_dir, output_dir / "contact_sheets")

    report = {
        "adapter_role": "N02_N03_DIAGNOSTIC_ONLY",
        "gate_authority": False,
        "source_dir": str(source_dir),
        "drawing_count": len(drawings),
        "successful_conversions": sum(r.conversion_status == "SUCCESS" for r in records),
        "failed_conversions": sum(r.conversion_status != "SUCCESS" for r in records),
        "total_dimension_candidates": len(dimension_rows),
        "total_text_records": len(text_rows),
        "contact_sheets": contact_sheets,
        "drawings": [asdict(record) for record in records],
        "tool_versions": {
            "python": sys.version,
            "ezdxf": getattr(ezdxf, "__version__", "unknown"),
            "dwg2dxf": shutil.which("dwg2dxf"),
            "dwgread": shutil.which("dwgread"),
        },
    }
    (output_dir / "scan_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # A failed conversion blocks model generation; warnings remain evidence issues.
    if report["failed_conversions"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({k: report[k] for k in ("drawing_count", "successful_conversions", "total_dimension_candidates", "total_text_records")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
