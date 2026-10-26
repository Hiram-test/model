"""Export source-backed N4/N5 plate contours for finite-element meshing.""" # Extract actual drawing geometry, never graphics.
import argparse # Read explicit source and result paths.
import json # Preserve exact contour provenance and mesh coordinates.
import math # Sample actual source arcs with bounded chord length.
from pathlib import Path # Resolve requested paths.
import ezdxf # Read original CAD entities.
def contour(doc, handles): # Connect actual source edges into a closed boundary.
    edges = [] # Keep each source edge and its traceable handle.
    for handle in handles: # Visit only explicitly identified physical outline edges.
        entity = doc.entitydb[handle] # Resolve the original entity.
        if entity.dxftype() == "LINE": # Preserve straight edges exactly.
            points = [list(entity.dxf.start)[:2], list(entity.dxf.end)[:2]] # Store unmodified endpoints.
        else: # Sample actual source circular arcs.
            start = math.radians(entity.dxf.start_angle) # Convert native starting angle.
            span = math.radians((entity.dxf.end_angle - entity.dxf.start_angle) % 360) # Preserve the CAD counterclockwise arc.
            count = max(2, math.ceil(span * entity.dxf.radius * (40 / 3) / 1.0)) # Keep arc chord length at most1mm in physical units.
            points = [[entity.dxf.center.x + entity.dxf.radius * math.cos(start + span * index / count), entity.dxf.center.y + entity.dxf.radius * math.sin(start + span * index / count)] for index in range(count + 1)] # Evaluate source arcs without inventing curvature.
        edges.append({"handle": handle, "type": entity.dxftype(), "points": points}) # Retain edge identity.
    ordered = edges.pop(0)["points"] # Start with an actual native boundary edge.
    order = [handles[0]] # Record the topological ordering used.
    while edges: # Walk the connected physical boundary.
        candidates = [(math.dist(ordered[-1], edge["points"][end]), index, end) for index, edge in enumerate(edges) for end in (0, -1)] # Find an adjoining endpoint.
        distance, index, end = min(candidates) # Select the exact geometric connection.
        assert distance < 1e-7, (distance, order) # Fail on disconnected or incorrectly selected source edges.
        edge = edges.pop(index) # Consume each edge exactly once.
        points = edge["points"] if end == 0 else edge["points"][::-1] # Preserve the walk direction.
        ordered.extend(points[1:]) # Avoid duplicate vertices at joined endpoints.
        order.append(edge["handle"]) # Retain the traced native handle sequence.
    assert math.dist(ordered[0], ordered[-1]) < 1e-7 # Require a genuinely closed source loop.
    origin = [min(point[axis] for point in ordered) for axis in (0, 1)] # Normalize only the coordinate datum.
    mm = [[(point[axis] - origin[axis]) * (40 / 3) for axis in (0, 1)] for point in ordered[:-1]] # Apply verified source dimension scale.
    return {"source_handles_in_boundary_order": order, "source_origin": origin, "scale_mm_per_source_unit": 40 / 3, "points_native_mm": mm, "native_extent_mm": [max(point[axis] for point in mm) for axis in (0, 1)]} # Preserve raw physical geometry separately from any annotated fit.
def main(): # Execute deterministic profile extraction.
    parser = argparse.ArgumentParser(description=__doc__) # Explain the mechanical-source scope.
    parser.add_argument("--source", type=Path, required=True) # Require the actual converted deck drawing.
    parser.add_argument("--output", type=Path, required=True) # Preserve a new result artifact.
    args = parser.parse_args() # Parse explicit paths.
    doc = ezdxf.readfile(args.source) # Load true CAD entities.
    n4 = contour(doc, ["440F", "4411", "4412", "4413", "4414", "4415", "4417", "4418", "4419", "4424", "4425", "4426", "4427", "4428", "4429", "442A", "442B", "442C", "442D", "442E"]) # Trace the exact tapered and filleted N4 boundary.
    n5 = contour(doc, ["443D", "443E", "443F", "4440"]) # Trace the native rectangular N5 boundary.
    n4["annotated_extent_mm"] = [295, 160] # Preserve explicit source dimension labels5D3Dand5AD0.
    n4["points_annotation_fitted_mm"] = [[point[0] * 295 / n4["native_extent_mm"][0], point[1]] for point in n4["points_native_mm"]] # Offer a separately named horizontal fit to the stated295mmgap.
    n4["fit_status"] = "Explicit horizontal rescale only: native width295.16831683168mm versus annotated295mm; do not call this an unchanged native contour." # Disclose the source-dimension discrepancy.
    n4["native_arc_radii_mm"] = [10, 5] # Preserve true source fillets0.75and0.375sourceunits.
    n4["nominal_notch_shoulder_mm"] = 56.5 # Preserve annotations5D72and5E2D.
    n4["nominal_middle_width_mm"] = 182 # Preserve the scaled dimension5D5C.
    result = {"schema": "zhaqing-panel-stiffener-source-profiles-v1", "source": "04-05-桥面板构造.dwg", "plane_coordinates": "First coordinate across channel gap; second upward from channel bottom. Shift globalzby−170mm.", "plate_thickness_mm": 10, "N4": n4, "N5": n5} # Retain exact source geometry and optional declared normalization.
    args.output.parent.mkdir(parents=True, exist_ok=True) # Create only the requested output directory.
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8") # Save mesh-ready source-backed contours.
    print(json.dumps({"N4_vertices": len(n4["points_native_mm"]), "N4_extent": n4["native_extent_mm"], "N5_extent": n5["native_extent_mm"]})) # Report actual extracted extents.
if __name__ == "__main__": # Execute only on direct invocation.
    main() # Build contour evidence without Python plotting.
