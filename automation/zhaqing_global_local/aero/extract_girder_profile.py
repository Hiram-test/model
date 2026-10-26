"""Recover the actual SGT12 rolled-girder outline, including source fillet arcs."""  # Component-only geometry is not a bridge aerodynamic section.
import argparse  # Accept exact source files and output directory.
import hashlib  # Preserve immutable drawing provenance.
import json  # Write the geometric contract.
from pathlib import Path  # Manage local source paths.
import ezdxf  # Read actual source CAD entities.
from ezdxf import path as cad_path  # Evaluate original line/arc geometry.
import numpy as np  # Validate outline continuity and dimensions.


def extract(dxf_path, dwg_path, output):  # Require both converted entities and original DWG bytes.
    document = ezdxf.readfile(dxf_path)  # Read the authentic Zhaqing girder drawing.
    if "扎青" not in document.entitydb["135A"].dxf.text:  # Verify the project identifier before accepting a section.
        raise ValueError("SGT12 project identity does not match Zhaqing")  # Avoid the mixed-project cross-section mistake.
    handles = ["491E", "4920", "4925", "4926", "4927", "4928", "4929", "492A", "492B", "492C", "492D", "492E", "492F", "4930", "4931", "4932"]  # Select the actual rolled-H boundary only, excluding splice plates, bolts and annotation.
    segments = [(handle, np.array([(point.x, point.y) for point in cad_path.make_path(document.entitydb[handle]).flattening(0.025)])) for handle in handles]  # Resolve true source arcs with25micrometer maximum geometric tolerance.
    first_handle, first_points = segments.pop(0)  # Select the source upper flange.
    ordered = list(first_points)  # Start the sampled boundary at the source upper flange.
    ordered_curves = [(first_handle, first_points[0], first_points[-1])]  # Retain original native primitives for meshing.
    while segments:  # Connect source boundary curves by their exact endpoints.
        found = False  # Detect missing or contradictory boundary entities.
        for index, (handle, points) in enumerate(segments):  # Locate the next source-connected segment.
            if np.linalg.norm(ordered[-1] - points[-1]) < 1e-7:  # Reverse a segment only to preserve path connectivity.
                points = points[::-1]  # Retain identical geometric coordinates.
            if np.linalg.norm(ordered[-1] - points[0]) < 1e-7:  # Match the next source endpoint.
                ordered.extend(points[1:])  # Avoid duplicated joins.
                ordered_curves.append((handle, points[0], points[-1]))  # Preserve each original line or circular arc.
                segments.pop(index)  # Consume exactly this boundary entity.
                found = True  # Record successful connectivity.
                break  # Continue from the new boundary endpoint.
        if not found:  # Never repair a missing curve with invented material.
            raise ValueError("source girder outline is disconnected")  # Require an actual source correction.
    points = np.asarray(ordered)  # Preserve every recovered boundary sample.
    if np.linalg.norm(points[0] - points[-1]) > 1e-7:  # Validate closed material geometry.
        raise ValueError("source girder outline is not closed")  # Reject an open aerodynamic obstacle.
    lower, upper = points.min(axis=0), points.max(axis=0)  # Determine source dimensions without assumptions.
    np.testing.assert_allclose(upper - lower, [400, 400], atol=1e-6)  # Corroborate source geometry against HW400*400 metadata.
    if document.entitydb["5161"].dxf.text != "HW400*400*13*21":  # Require the original specification text.
        raise ValueError("rolled section specification changed")  # Prevent stale entity selections.
    center = (lower + upper) / 2  # Use the centroid of the doubly symmetric physical outline.
    points_m = (points - center) * 0.001  # Convert the drawing's declared millimeters into SI.
    native_curves = []  # Keep exact arcs separate from visualization tessellation.
    for handle, start, end in ordered_curves:  # Convert every source primitive into SI.
        entity = document.entitydb[handle]  # Read the original curve type.
        curve = {"handle": handle, "kind": entity.dxftype(), "start_m": ((start - center) * 0.001).tolist(), "end_m": ((end - center) * 0.001).tolist()}  # Preserve actual endpoints and identity.
        if entity.dxftype() == "ARC":  # Circular arcs require a true center for nativeGmsh.
            curve["center_m"] = ((np.asarray(entity.dxf.center)[:2] - center) * 0.001).tolist()  # Retain exact24mm root curvature.
        native_curves.append(curve)  # Save the connected native boundary.
    output = Path(output)  # Normalize the destination.
    output.mkdir(parents=True, exist_ok=True)  # Keep evidence with its later CFD results.
    contract = {"scope": "PARTIAL_LONGITUDINAL_GIRDER_ONLY", "geometry_verified": True, "full_bridge_section_verified": False, "project": "ZHAQING", "source_dwg": "source-inputs/zhaqing-suspension-bridge/drawings/12-纵梁构造.dwg", "source_dwg_sha256": hashlib.sha256(Path(dwg_path).read_bytes()).hexdigest(), "source_dxf_sha256": hashlib.sha256(Path(dxf_path).read_bytes()).hexdigest(), "entity_handles": handles, "project_title_handle": "135A", "specification_handle": "5161", "specification": "HW400*400*13*21", "source_root_fillet_radius_mm": 24.0, "arc_max_chord_error_mm": 0.025, "source_units": "mm", "source_origin_xy_mm": center.tolist(), "reference_width_m": 0.4, "polygons_m": [points_m[:-1].tolist()], "excluded_from_this_component_model": ["bridge deck panels and stiffeners", "second longitudinal girder", "transverse beams", "guardrails", "hangers and main cables", "girder splice plates and bolts"], "permitted_use": "component CFD and solver development only; never use these coefficients as whole-bridge CdClCm"}  # Keep geometric truth separate from whole-bridge applicability.
    contract["native_curves"] = native_curves  # Native meshing uses exact circular arcs, not polygon chord approximations.
    (output / "sgt12_girder_geometry.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Save the exact input contract.
    np.savetxt(output / "sgt12_girder_outline_m.dat", points_m, header="SGT12 source-derived HW400*400*13*21 outline; NOT whole bridge section; SI m")  # Export source coordinates for native Gnuplot visualization.
    return contract  # Permit automated evidence reporting.


if __name__ == "__main__":  # Provide a repeatable source-recovery entry point.
    parser = argparse.ArgumentParser()  # Define explicit source inputs.
    parser.add_argument("dxf")  # Require the native converted drawing.
    parser.add_argument("dwg")  # Require the original drawing for provenance.
    parser.add_argument("output")  # Choose the result directory.
    args = parser.parse_args()  # Read command-line paths.
    result = extract(args.dxf, args.dwg, args.output)  # Extract and validate the actual component outline.
    print(json.dumps({"scope": result["scope"], "source_dwg_sha256": result["source_dwg_sha256"], "outline_vertex_count": len(result["polygons_m"][0])}, indent=2))  # Report source truth without aerodynamic claims.
