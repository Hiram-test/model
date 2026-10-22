from __future__ import annotations  # Enable postponed evaluation of re-exported type annotations.
from contracts import DrawingIR, GeometryField, SensorField, load_drawing_ir, load_point_cloud, load_sensors  # Re-export typed source contracts and parsers.
from drawing_adapter import compile_svg_drawing  # Re-export the source-native drawing semantic compiler.
from mechanics import beam_deflection  # Re-export the deterministic simple-beam field solver.
from pipeline import formalize_and_update, render_markdown, write_outputs  # Re-export the complete formal update pipeline.
__all__ = ["DrawingIR", "GeometryField", "SensorField", "compile_svg_drawing", "load_drawing_ir", "load_point_cloud", "load_sensors", "beam_deflection", "formalize_and_update", "render_markdown", "write_outputs"]  # Declare the stable public prototype API.
