"""Export actual DXF entities as Gnuplot data; Python performs no rendering."""  # Keep native data plotting separate.
import argparse  # Provide explicit input/output paths.
from pathlib import Path  # Persist the extracted source geometry.
import ezdxf  # Read the LibreDWG converted drawing.
from ezdxf import path as cad_path  # Tessellate true drawing arcs only.

parser = argparse.ArgumentParser()  # Define the small extraction command.
parser.add_argument("dxf")  # Accept an actual DXF drawing.
parser.add_argument("output")  # Accept the auditable coordinate output.
arguments = parser.parse_args()  # Read paths from the caller.
document = ezdxf.readfile(arguments.dxf)  # Preserve source geometry coordinates.
rows = []  # Collect linework without labels or dimension reinterpretation.
for entity in document.modelspace():  # Inspect every source model-space entity.
    if entity.dxftype() in {"LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE"}:  # Include native drawing curves only.
        points = list(cad_path.make_path(entity).flattening(0.02))  # Approximate genuine arcs to0.02drawing-unit tolerance.
        rows.append(f"# source_handle={entity.dxf.handle} type={entity.dxftype()} layer={entity.dxf.layer}")  # Retain provenance per polyline.
        rows.extend(f"{point.x:.12g} {point.y:.12g}" for point in points)  # Export source coordinates without geometry edits.
        rows.append("")  # Keep independent entities disconnected.
Path(arguments.output).write_text("\n".join(rows), encoding="utf-8")  # Save only numerical data, never a rendered plot.
