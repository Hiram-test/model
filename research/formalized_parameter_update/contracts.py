from __future__ import annotations  # Enable postponed evaluation of type annotations for Python 3.11+ compatibility.
import csv  # Read deterministic sensor and point-cloud tables without a dataframe dependency.
import hashlib  # Compute source digests so every update receipt is traceable to exact inputs.
import json  # Read and write the visual-semantic intermediate representation and update receipt.
from dataclasses import dataclass  # Define explicit immutable contracts for each source modality.
from pathlib import Path  # Represent all input and output locations with portable path objects.
from typing import Any  # Type JSON-shaped dictionaries without hiding their dynamic fields.
import numpy as np  # Perform deterministic array algebra and numerical integration.
@dataclass(frozen=True)  # Prevent downstream code from silently mutating drawing facts.
class DrawingIR:  # Store the typed facts extracted once from an engineering drawing.
    span_m: float  # Record the nominal support-to-support span in metres.
    left_support: str  # Record the left support semantic type.
    right_support: str  # Record the right support semantic type.
    load_q_n_per_m: float  # Record the full-span uniformly distributed load in newtons per metre.
    nominal_width_m: float  # Record the drawing width of the rectangular section.
    nominal_depth_m: float  # Record the drawing depth of the rectangular section.
    initial_modulus_pa: float  # Record the modulus used by the current computational model.
    reference_modulus_pa: float  # Record a numerical scale used to create a dimensionless update parameter.
    sensor_positions_m: tuple[float, ...]  # Record the measurement positions declared by the drawing or test plan.
    symmetry_expected: bool  # Record whether drawing topology and loading imply mirror symmetry.
    source_name: str  # Record the drawing source identifier used by the visual-semantic adapter.
    source_sha256: str  # Record the digest declared for the drawing source when available.
@dataclass(frozen=True)  # Prevent geometry facts from changing after point-cloud formalization.
class GeometryField:  # Store the actual section and centreline field recovered from the point cloud.
    x_m: np.ndarray  # Store longitudinal stations in the registered drawing coordinate system.
    width_m: np.ndarray  # Store measured section widths at each station.
    depth_m: np.ndarray  # Store measured section depths at each station.
    inertia_m4: np.ndarray  # Store the measured second moment of area at each station.
    centerline_z_m: np.ndarray  # Store the unloaded centreline elevation at each station.
    span_m: float  # Store the measured support-to-support point-cloud extent.
    source_sha256: str  # Store the digest of the point-cloud table.
@dataclass(frozen=True)  # Prevent measurement data from being overwritten during updating.
class SensorField:  # Store deterministic displacement measurements and their certified bounds.
    sensor_id: tuple[str, ...]  # Store stable sensor identifiers.
    x_m: np.ndarray  # Store sensor positions in the registered drawing coordinate system.
    displacement_m: np.ndarray  # Store measured downward displacement in metres.
    bound_m: np.ndarray  # Store absolute deterministic error bounds in metres.
    source_sha256: str  # Store the digest of the sensor table.
def _sha256(path: Path) -> str:  # Return a reproducible digest for an input file.
    digest = hashlib.sha256()  # Create a fresh SHA-256 accumulator.
    with path.open("rb") as stream:  # Read bytes so text encoding cannot change the digest.
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):  # Process large inputs in bounded memory.
            digest.update(chunk)  # Add the current byte block to the digest state.
    return digest.hexdigest()  # Return the lowercase hexadecimal digest.
def _require(condition: bool, message: str) -> None:  # Enforce fail-closed source and mechanics contracts.
    if not condition:  # Detect a violated precondition.
        raise ValueError(message)  # Stop immediately instead of fabricating a parameter update.
def load_drawing_ir(path: Path) -> DrawingIR:  # Parse and validate the visual-semantic drawing contract.
    data = json.loads(path.read_text(encoding="utf-8"))  # Load the structured output produced by the drawing parser.
    _require(data.get("schema_version") == "0.1", "unsupported drawing semantic schema")  # Freeze the prototype schema.
    _require(data.get("extraction_status") == "VERIFIED", "drawing semantics are not verified")  # Reject draft visual output.
    _require(data.get("units") == {"length": "m", "force": "N", "modulus": "Pa"}, "drawing units are not explicit SI")  # Reject implicit units.
    beam = data.get("beam", {})  # Read the beam entity from the semantic graph.
    section = beam.get("section", {})  # Read the cross-section entity linked to the beam.
    supports = data.get("supports", [])  # Read the support entities extracted from the drawing.
    loads = data.get("loads", [])  # Read the load entities extracted from the drawing.
    update = data.get("parameter_update", {})  # Read the declared parameter class and initial value.
    evidence = data.get("visual_evidence", [])  # Read source-region evidence for visual facts.
    _require(beam.get("type") == "euler_bernoulli_beam", "prototype requires an Euler-Bernoulli beam")  # Lock the mechanics theory.
    _require(section.get("shape") == "rectangle", "prototype requires a rectangular section")  # Lock the section formula.
    _require(len(supports) == 2, "exactly two supports are required")  # Reject incomplete support extraction.
    ordered_supports = sorted(supports, key=lambda item: float(item["x_m"]))  # Put supports into longitudinal order.
    _require(ordered_supports[0].get("type") == "pin", "left support must be a pin")  # Require the simple-beam left boundary.
    _require(ordered_supports[1].get("type") == "roller", "right support must be a roller")  # Require the simple-beam right boundary.
    _require(len(loads) == 1 and loads[0].get("type") == "full_span_udl", "prototype requires one full-span UDL")  # Reject ambiguous loading.
    _require(update.get("candidate") == "uniform_youngs_modulus", "prototype updates only uniform Young's modulus")  # Keep one explicit parameter class.
    _require(len(evidence) >= 4, "visual evidence must cover beam, supports, load, and section")  # Require visual grounding rather than free text.
    span_m = float(beam["span_m"])  # Convert the span to a numeric SI value.
    _require(abs(float(ordered_supports[0]["x_m"])) <= 1.0e-9, "left support must define x=0")  # Anchor the coordinate system.
    _require(abs(float(ordered_supports[1]["x_m"]) - span_m) <= 1.0e-9, "right support must define x=L")  # Close the span definition.
    sensor_positions_m = tuple(float(value) for value in data.get("sensor_layout_m", []))  # Convert the declared sensor layout to an immutable tuple.
    _require(len(sensor_positions_m) >= 3, "at least three sensor positions are required")  # Require enough information to test an error form.
    source = data.get("source", {})  # Read the drawing source metadata.
    return DrawingIR(  # Build the immutable drawing intermediate representation.
        span_m=span_m,  # Store the validated span.
        left_support=str(ordered_supports[0]["type"]),  # Store the validated left support type.
        right_support=str(ordered_supports[1]["type"]),  # Store the validated right support type.
        load_q_n_per_m=float(loads[0]["q_n_per_m"]),  # Store the validated load magnitude.
        nominal_width_m=float(section["width_m"]),  # Store the drawing section width.
        nominal_depth_m=float(section["depth_m"]),  # Store the drawing section depth.
        initial_modulus_pa=float(update["initial_value_pa"]),  # Store the current model modulus.
        reference_modulus_pa=float(update["reference_value_pa"]),  # Store the scaling modulus.
        sensor_positions_m=sensor_positions_m,  # Store the declared measurement layout.
        symmetry_expected=bool(data.get("expected_symmetry") == "mirror_about_midspan"),  # Convert symmetry semantics to a Boolean contract.
        source_name=str(source.get("name", path.name)),  # Store the source name or fall back to the contract file name.
        source_sha256=str(source.get("sha256", "UNDECLARED")),  # Preserve the declared source digest without inventing one.
    )  # Finish the immutable drawing representation.
def load_point_cloud(path: Path, drawing: DrawingIR) -> GeometryField:  # Convert registered raw points into a section field.
    rows = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")  # Read numeric point records with named columns.
    _require(rows.size > 0, "point cloud is empty")  # Reject absent geometry evidence.
    names = set(rows.dtype.names or ())  # Collect available columns for explicit validation.
    _require({"x_m", "y_m", "z_m"}.issubset(names), "point cloud requires x_m,y_m,z_m")  # Reject unregistered or unitless inputs.
    raw_x = np.atleast_1d(rows["x_m"]).astype(float)  # Read longitudinal coordinates.
    raw_y = np.atleast_1d(rows["y_m"]).astype(float)  # Read transverse coordinates.
    raw_z = np.atleast_1d(rows["z_m"]).astype(float)  # Read vertical coordinates.
    x_origin = float(np.min(raw_x))  # Determine the measured left extent.
    x_registered = raw_x - x_origin  # Register the point cloud to the drawing x=0 support convention.
    stations = np.unique(np.round(x_registered, decimals=9))  # Create deterministic section stations.
    _require(stations.size >= 11, "point cloud requires at least eleven longitudinal stations")  # Require adequate geometric coverage.
    widths: list[float] = []  # Accumulate measured section widths.
    depths: list[float] = []  # Accumulate measured section depths.
    centers: list[float] = []  # Accumulate unloaded centreline elevations.
    for station in stations:  # Process each measured cross section independently.
        mask = np.isclose(x_registered, station, atol=1.0e-9, rtol=0.0)  # Select points belonging to the current section.
        section_y = raw_y[mask]  # Extract transverse coordinates for the section.
        section_z = raw_z[mask]  # Extract vertical coordinates for the section.
        _require(section_y.size >= 4, f"station {station} has insufficient section points")  # Reject under-resolved sections.
        widths.append(float(np.max(section_y) - np.min(section_y)))  # Measure width from the outer point-cloud envelope.
        depths.append(float(np.max(section_z) - np.min(section_z)))  # Measure depth from the outer point-cloud envelope.
        centers.append(float(0.5 * (np.max(section_z) + np.min(section_z))))  # Measure the section centreline elevation.
    width_m = np.asarray(widths, dtype=float)  # Convert width observations to an array.
    depth_m = np.asarray(depths, dtype=float)  # Convert depth observations to an array.
    centerline_z_m = np.asarray(centers, dtype=float)  # Convert centreline observations to an array.
    _require(bool(np.all(width_m > 0.0) and np.all(depth_m > 0.0)), "point cloud produced non-positive section dimensions")  # Enforce physical geometry.
    inertia_m4 = width_m * np.power(depth_m, 3.0) / 12.0  # Compute the rectangular second moment of area about the transverse axis.
    span_m = float(stations[-1] - stations[0])  # Compute the measured longitudinal extent.
    _require(abs(span_m - drawing.span_m) <= 0.01, "point-cloud span conflicts with drawing by more than 10 mm")  # Stop on unresolved registration conflict.
    return GeometryField(  # Build the immutable point-cloud geometry field.
        x_m=stations,  # Store registered longitudinal stations.
        width_m=width_m,  # Store measured widths.
        depth_m=depth_m,  # Store measured depths.
        inertia_m4=inertia_m4,  # Store measured section inertias.
        centerline_z_m=centerline_z_m,  # Store measured unloaded centreline elevations.
        span_m=span_m,  # Store the measured span.
        source_sha256=_sha256(path),  # Bind the geometry field to the exact point-cloud file.
    )  # Finish the immutable geometry representation.
def load_sensors(path: Path, drawing: DrawingIR) -> SensorField:  # Parse deterministic displacement measurements.
    sensor_id: list[str] = []  # Accumulate stable sensor identifiers.
    x_m: list[float] = []  # Accumulate sensor positions.
    displacement_m: list[float] = []  # Accumulate measured displacements in metres.
    bound_m: list[float] = []  # Accumulate certified absolute bounds in metres.
    with path.open("r", encoding="utf-8", newline="") as stream:  # Open the sensor table with explicit encoding.
        reader = csv.DictReader(stream)  # Read rows by column name.
        _require(reader.fieldnames is not None, "sensor table has no header")  # Reject malformed tables.
        _require({"sensor_id", "x_m", "displacement_mm", "bound_mm"}.issubset(set(reader.fieldnames)), "sensor table columns are incomplete")  # Require explicit units.
        for row in reader:  # Parse every sensor record.
            sensor_id.append(str(row["sensor_id"]))  # Preserve the declared sensor identifier.
            x_m.append(float(row["x_m"]))  # Convert the coordinate to metres.
            displacement_m.append(float(row["displacement_mm"]) / 1000.0)  # Convert millimetres to metres.
            bound_m.append(float(row["bound_mm"]) / 1000.0)  # Convert the deterministic bound to metres.
    order = np.argsort(np.asarray(x_m, dtype=float))  # Sort sensors in longitudinal order.
    x_array = np.asarray(x_m, dtype=float)[order]  # Reorder positions.
    displacement_array = np.asarray(displacement_m, dtype=float)[order]  # Reorder measurements.
    bound_array = np.asarray(bound_m, dtype=float)[order]  # Reorder bounds.
    id_array = np.asarray(sensor_id, dtype=object)[order]  # Reorder identifiers.
    _require(bool(np.all(bound_array >= 0.0)), "sensor bounds must be non-negative")  # Reject invalid uncertainty contracts.
    _require(x_array.size == len(drawing.sensor_positions_m), "sensor count conflicts with drawing layout")  # Require source agreement.
    _require(bool(np.allclose(x_array, np.asarray(drawing.sensor_positions_m), atol=1.0e-9, rtol=0.0)), "sensor positions conflict with drawing layout")  # Require exact registration.
    _require(float(np.min(x_array)) >= -1.0e-9 and float(np.max(x_array)) <= drawing.span_m + 1.0e-9, "sensor lies outside the span")  # Reject out-of-domain data.
    return SensorField(  # Build the immutable sensor field.
        sensor_id=tuple(str(value) for value in id_array.tolist()),  # Store ordered sensor identifiers.
        x_m=x_array,  # Store ordered sensor positions.
        displacement_m=displacement_array,  # Store ordered measured displacements.
        bound_m=bound_array,  # Store ordered deterministic bounds.
        source_sha256=_sha256(path),  # Bind the measurements to the exact sensor file.
    )  # Finish the immutable sensor representation.
