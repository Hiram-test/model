from __future__ import annotations  # Enable modern type annotations on all supported Python versions.
import hashlib  # Bind generated semantics to the exact drawing bytes.
import json  # Persist the drawing semantic intermediate representation.
import re  # Extract dimensions and loads from visible drawing labels.
import xml.etree.ElementTree as ET  # Read source-native SVG geometry without rasterization.
from pathlib import Path  # Represent drawing and output locations portably.
from typing import Any  # Type JSON-shaped semantic records.
def _sha256(path: Path) -> str:  # Compute one reproducible source digest.
    return hashlib.sha256(path.read_bytes()).hexdigest()  # Hash the exact SVG bytes.
def _name(tag: str) -> str:  # Strip an optional XML namespace from an SVG tag.
    return tag.rsplit("}", maxsplit=1)[-1]  # Return the local element name.
def _num(value: str | None, label: str) -> float:  # Parse one required SVG number with optional units.
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value or "")  # Find the first numeric token.
    if match is None:  # Detect a missing or malformed attribute.
        raise ValueError(f"SVG value {label} is missing or nonnumeric")  # Fail closed instead of guessing geometry.
    return float(match.group(0))  # Return the validated number.
def _label(texts: list[str], pattern: str, label: str) -> float:  # Extract one required engineering label.
    for text in texts:  # Search every visible text node.
        match = re.search(pattern, text, flags=re.IGNORECASE)  # Match the requested label independent of case.
        if match is not None:  # Accept the first visible match.
            return float(match.group(1))  # Return the engineering value.
    raise ValueError(f"drawing label {label} was not found")  # Preserve missing information as a hard conflict.
def _box(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> list[float]:  # Normalize one visual evidence box.
    return [x0 / width, y0 / height, x1 / width, y1 / height]  # Return contract-ready normalized coordinates.
def compile_svg_drawing(svg_path: Path, output_path: Path, initial_modulus_pa: float = 230.0e9, reference_modulus_pa: float = 200.0e9) -> dict[str, Any]:  # Compile a vector beam drawing into verified structural semantics.
    root = ET.parse(svg_path).getroot()  # Parse the source-native SVG tree.
    view = [_num(value, "viewBox") for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", root.get("viewBox", ""))]  # Parse the declared viewport.
    view_width = view[2] if len(view) == 4 else _num(root.get("width"), "root width")  # Resolve viewport width.
    view_height = view[3] if len(view) == 4 else _num(root.get("height"), "root height")  # Resolve viewport height.
    texts = [" ".join((element.text or "").split()) for element in root.iter() if _name(element.tag) == "text"]  # Collect normalized visible labels.
    span_m = _label(texts, r"\bL\s*=\s*([0-9.]+)\s*m\b", "span L")  # Extract the support-to-support span.
    load_n_per_m = 1000.0 * _label(texts, r"\bq\s*=\s*([0-9.]+)\s*kN\s*/\s*m\b", "UDL q")  # Extract and convert the distributed load.
    width_m = _label(texts, r"\bb\s*=\s*([0-9.]+)\s*m\b", "section width b")  # Extract nominal section width.
    depth_m = _label(texts, r"\bh\s*=\s*([0-9.]+)\s*m\b", "section depth h")  # Extract nominal section depth.
    lines = [{"x1": _num(element.get("x1"), "x1"), "y1": _num(element.get("y1"), "y1"), "x2": _num(element.get("x2"), "x2"), "y2": _num(element.get("y2"), "y2"), "sw": _num(element.get("stroke-width", "1"), "stroke-width")} for element in root.iter() if _name(element.tag) == "line"]  # Parse all line primitives.
    circles = [{"cx": _num(element.get("cx"), "cx"), "cy": _num(element.get("cy"), "cy"), "r": _num(element.get("r"), "r")} for element in root.iter() if _name(element.tag) == "circle"]  # Parse sensor and roller circles.
    rectangles = [{"x": _num(element.get("x"), "rect x"), "y": _num(element.get("y"), "rect y"), "w": _num(element.get("width"), "rect width"), "h": _num(element.get("height"), "rect height")} for element in root.iter() if _name(element.tag) == "rect"]  # Parse section and page rectangles.
    polygons = [[(float(values[index]), float(values[index + 1])) for index in range(0, len(values), 2)] for values in [re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", element.get("points", "")) for element in root.iter() if _name(element.tag) == "polygon"] if len(values) % 2 == 0]  # Parse support polygons.
    horizontal = [line for line in lines if abs(line["y2"] - line["y1"]) <= 1.0e-9]  # Keep horizontal beam and load candidates.
    if not horizontal:  # Detect a missing beam axis.
        raise ValueError("drawing contains no horizontal structural line")  # Stop instead of inventing topology.
    beam = max(horizontal, key=lambda line: (line["sw"], abs(line["x2"] - line["x1"])))  # Select the visually dominant horizontal line.
    beam_x0 = min(beam["x1"], beam["x2"])  # Normalize the left drawing coordinate.
    beam_x1 = max(beam["x1"], beam["x2"])  # Normalize the right drawing coordinate.
    beam_y = 0.5 * (beam["y1"] + beam["y2"])  # Record the beam-axis elevation.
    triangles = sorted([{"x": sum(point[0] for point in polygon) / 3.0, "y": sum(point[1] for point in polygon) / 3.0} for polygon in polygons if len(polygon) == 3 and sum(point[1] for point in polygon) / 3.0 > beam_y], key=lambda item: item["x"])  # Recognize support triangles below the beam.
    if len(triangles) != 2:  # Require exactly two simple supports.
        raise ValueError(f"expected two support triangles, found {len(triangles)}")  # Preserve topology ambiguity explicitly.
    rollers = [circle for circle in circles if circle["cy"] > beam_y + 20.0 and abs(circle["cx"] - triangles[1]["x"]) <= 60.0]  # Recognize rollers beneath the right support.
    if len(rollers) < 2:  # Require visual proof of the roller support.
        raise ValueError("right support lacks two roller symbols")  # Reject an unsupported semantic label.
    sensors = sorted([circle for circle in circles if beam_x0 - 1.0e-9 <= circle["cx"] <= beam_x1 + 1.0e-9 and abs(circle["cy"] - beam_y) <= 2.0], key=lambda item: item["cx"])  # Recognize circular measurement markers on the beam axis.
    if len(sensors) < 3:  # Require enough observations to test an error form.
        raise ValueError("fewer than three beam-axis sensors were recognized")  # Stop when the test layout is under-specified.
    sensor_positions_m = [round((circle["cx"] - beam_x0) * span_m / (beam_x1 - beam_x0), 9) for circle in sensors]  # Map drawing coordinates into physical positions.
    section_candidates = [rectangle for rectangle in rectangles if rectangle["x"] > beam_x1 and rectangle["w"] < 0.5 * view_width and rectangle["h"] < 0.5 * view_height]  # Locate the separate section sketch.
    if not section_candidates:  # Detect a missing section visual.
        raise ValueError("section rectangle was not recognized")  # Refuse text-only section inference.
    section = max(section_candidates, key=lambda rectangle: rectangle["w"] * rectangle["h"])  # Select the dominant section sketch.
    load_candidates = [line for line in horizontal if line is not beam and line["y1"] < beam_y and abs(line["x2"] - line["x1"]) >= 0.8 * (beam_x1 - beam_x0)]  # Locate a full-span load line above the beam.
    if not load_candidates:  # Detect missing load geometry.
        raise ValueError("full-span load line was not recognized")  # Reject label-only load inference.
    load_line = max(load_candidates, key=lambda line: abs(line["x2"] - line["x1"]))  # Select the longest load distribution line.
    source_sha = _sha256(svg_path)  # Bind semantics to the exact raw drawing.
    data: dict[str, Any] = {"schema_version": "0.1", "extraction_status": "COMPILED_FROM_SVG", "drawing_human_reviewed": False, "compiler": "deterministic_svg_v0", "source": {"type": "vector_engineering_drawing", "name": svg_path.name, "sha256": source_sha, "page": 1}, "units": {"length": "m", "force": "N", "modulus": "Pa"}}  # Start a compiler IR, not a human-reviewed drawing audit.
    data["beam"] = {"id": "B1", "type": "euler_bernoulli_beam", "span_m": span_m, "section": {"id": "SEC1", "shape": "rectangle", "width_m": width_m, "depth_m": depth_m}}  # Record beam and section semantics.
    data["supports"] = [{"id": "SUP-L", "type": "pin", "x_m": 0.0}, {"id": "SUP-R", "type": "roller", "x_m": span_m}]  # Record support topology from symbols.
    data["loads"] = [{"id": "LOAD-1", "type": "full_span_udl", "start_x_m": 0.0, "end_x_m": span_m, "q_n_per_m": load_n_per_m}]  # Record load semantics in SI units.
    data["sensor_layout_m"] = sensor_positions_m  # Record the visual test layout.
    data["expected_symmetry"] = "mirror_about_midspan"  # Record symmetry implied by the structure and load.
    data["parameter_update"] = {"candidate": "uniform_youngs_modulus", "initial_value_pa": initial_modulus_pa, "reference_value_pa": reference_modulus_pa}  # Attach current-model parameter configuration.
    data["relations"] = [{"subject": "SUP-L", "predicate": "supports", "object": "B1"}, {"subject": "SUP-R", "predicate": "supports", "object": "B1"}, {"subject": "LOAD-1", "predicate": "acts_on", "object": "B1"}, {"subject": "SEC1", "predicate": "section_of", "object": "B1"}]  # Record the minimal structural graph.
    data["visual_evidence"] = [{"entity_id": "B1", "bbox_norm": _box(beam_x0, beam_y - 12.0, beam_x1, beam_y + 12.0, view_width, view_height)}, {"entity_id": "SUP-L", "bbox_norm": _box(triangles[0]["x"] - 55.0, beam_y, triangles[0]["x"] + 55.0, triangles[0]["y"] + 50.0, view_width, view_height)}, {"entity_id": "SUP-R", "bbox_norm": _box(triangles[1]["x"] - 55.0, beam_y, triangles[1]["x"] + 55.0, max(circle["cy"] + circle["r"] for circle in rollers) + 20.0, view_width, view_height)}, {"entity_id": "LOAD-1", "bbox_norm": _box(min(load_line["x1"], load_line["x2"]), load_line["y1"] - 20.0, max(load_line["x1"], load_line["x2"]), beam_y - 25.0, view_width, view_height)}, {"entity_id": "SEC1", "bbox_norm": _box(section["x"] - 45.0, section["y"] - 20.0, section["x"] + section["w"] + 45.0, section["y"] + section["h"] + 90.0, view_width, view_height)}]  # Preserve source evidence for every load-bearing fact.
    data["extraction_rules"] = {"beam": "dominant horizontal line", "pin": "triangle without rollers", "roller": "triangle with rollers", "sensors": "circles on beam axis", "dimensions": "visible labels"}  # Make the semantic compilation auditable.
    output_path.parent.mkdir(parents=True, exist_ok=True)  # Create the semantic output directory.
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist the compiler IR for the mechanics gate.
    return data  # Return the same semantics for immediate downstream use.
