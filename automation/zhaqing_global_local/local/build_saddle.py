#!/usr/bin/env python3
"""Build explicit 283-wire solids on drawing-derived saddle plates; candidate wire packing remains identified.""" # Scope.
from __future__ import annotations # Consistent type annotations.
import argparse # CLI settings.
import hashlib # Input provenance.
import json # Structured metadata.
import math # Geometry operations.
from pathlib import Path # Filesystem paths.
import numpy as np # Numeric arrays, never plotting.

def packing(count: int, diameter: float, clearance: float = 0.0) -> np.ndarray: # Candidate parallel-wire hexagonal packing with an explicit research gap.
    if not np.isfinite(clearance) or clearance < 0: raise ValueError('Packing clearance must be finite and nonnegative') # Reject hidden overlaps or invalid geometry.
    pitch = diameter + clearance # Preserve actual wire diameter while changing only the declared candidate packing gap.
    points = [(pitch * (q + 0.5 * r), pitch * math.sqrt(3) * 0.5 * r) for q in range(-20, 21) for r in range(-20, 21)] # Explicit physical wire centers.
    points.sort(key=lambda p: (round(p[0] ** 2 + p[1] ** 2, 7), math.atan2(p[1], p[0]))) # Compact deterministic radial ordering.
    chosen = np.asarray(points[:count], dtype=float) # Preserve exact requested wire count.
    chosen[:, 1] -= np.min(chosen[:, 1]) - diameter * 0.5 # Place lowest wire tangent to base bearing plate.
    return chosen # Return candidate transverse positions.

def disk_grid(n: int, radius: float) -> np.ndarray: # Square-to-disk quadrilateral mesh, not a square wire.
    pts = [] # Per-slice physical cross-section nodes.
    for j in range(n + 1): # Vertical cross-section subdivisions.
        for i in range(n + 1): # Transverse cross-section subdivisions.
            u, v = -1.0 + 2.0 * i / n, -1.0 + 2.0 * j / n # Unit-square coordinates.
            if abs(u) + abs(v) == 0: pts.append((0.0, 0.0)); continue # Exact center.
            if abs(u) > abs(v): r, angle = u, math.pi * 0.25 * v / u # Concentric disk map first sector.
            else: r, angle = v, math.pi * 0.5 - math.pi * 0.25 * u / v # Remaining sectors.
            pts.append((radius * r * math.cos(angle), radius * r * math.sin(angle))) # Circle boundary stays circular at nodes.
    return np.asarray(pts) # Return actual disk nodes.

def build(out: Path, nx: int, nc: int, count: int, load_n: float, mu: float, smoke: bool, elastic_forming: bool = False, planar_right: bool = True, wire_material: dict | None = None, prestressed_equilibrium: bool = False, load_factors: tuple[float,...] | None = None, packing_clearance: float = 0.0) -> dict: # Generate complete native mesh plus explicitly declared transfer and seating paths.
    out.mkdir(parents=True, exist_ok=True) # Preserve generated model.
    radius, diameter = 1500.0, 5.0 # Drawing ARC4D8B and cable TEXT16B5.
    material = wire_material or {"young_mpa": 200000.0, "poisson": 0.3, "source": "Assumed elastic research material; no plastic calibration"} # Explicit material provenance.
    young, poisson = float(material["young_mpa"]), float(material["poisson"]) # Unit-qualified elastic constants.
    if not np.isfinite([young, poisson]).all() or young <= 0 or not -1 < poisson < 0.5 or not material.get("source"): raise ValueError("Invalid or untraceable wire material") # Physical/provenance validation.
    plastic = material.get("plastic_curve_mpa_equivalent_strain") # Optional actual calibrated monotone plastic data.
    if plastic is not None: # Do not infer yield from ultimate strength.
        curve = np.asarray(plastic, dtype=float) # Native true stress/equivalent plastic strain pairs.
        if curve.ndim != 2 or curve.shape[1] != 2 or len(curve) < 2 or not np.isfinite(curve).all() or np.any(curve[:, 0] <= 0) or curve[0, 1] != 0 or np.any(np.diff(curve[:, 1]) <= 0) or np.any(np.diff(curve[:, 0]) < 0): raise ValueError("Require calibrated positive monotone true-stress/plastic-strain curve starting atzero plastic strain") # Reject bogus constitutive inputs.
    theta = np.linspace(math.radians(90.0 - 127.8890430192378), math.radians(90.0 - 63.23495198354442), nx + 1) # Source longitudinal ARC endpoints, left to right.
    centers = packing(count, diameter, packing_clearance) # Explicit wire identities and optional research clearance; internal packing remains unmeasured.
    cross = disk_grid(nc, diameter / 2.0) # Structured solid cross-section.
    cap_area = np.zeros(len(cross)) # Consistent nodal cut-surface area weights.
    for j in range(nc): # Integrate actual disk quadrilateral areas.
        for i in range(nc): # Every cross-section cell contributes to four cap nodes.
            ids = [j * (nc + 1) + i, j * (nc + 1) + i + 1, (j + 1) * (nc + 1) + i + 1, (j + 1) * (nc + 1) + i] # Ordered cap quad.
            poly = cross[ids] # Physical cross-section coordinates.
            area = 0.5 * abs(np.dot(poly[:, 0], np.roll(poly[:, 1], -1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], -1))) # Polygon area in mm2.
            cap_area[ids] += area / 4.0 # Lumped consistent nodal traction weights.
    nodes, elements, wire_id, surfaces, left, right = [], [], [], {}, [], [] # Full native mesh storage.
    quadrature = [] # Element volume quadrature for operators.
    def point(t: float, y: float, z: float) -> tuple: return ((radius + z) * math.sin(t), y, (radius + z) * math.cos(t) - radius) # Sweep around source saddle arc.
    for w, (yc, zc) in enumerate(centers, 1): # Every wire has separate mesh and contact topology.
        offset = len(nodes) # Wire-local node block.
        nodes.extend(point(t, yc + y, zc + z) for t in theta for y, z in cross) # Sweep circular wire solids.
        index = lambda k, j, i: offset + k * (nc + 1) ** 2 + j * (nc + 1) + i + 1 # One-based native numbering.
        left.extend(index(0, j, i) for j in range(nc + 1) for i in range(nc + 1)) # Physical cut-surface nodes.
        right.extend(index(nx, j, i) for j in range(nc + 1) for i in range(nc + 1)) # Physical cut-surface nodes.
        face = [] # Actual outer wire surface element faces.
        for k in range(nx): # Axial slices.
            for j in range(nc): # Vertical cells.
                for i in range(nc): # Transverse cells.
                    conn = [index(k, j, i), index(k, j, i + 1), index(k, j + 1, i + 1), index(k, j + 1, i)] # Start face nodes.
                    conn += [index(k + 1, j, i), index(k + 1, j, i + 1), index(k + 1, j + 1, i + 1), index(k + 1, j + 1, i)] # End face nodes.
                    elements.append(conn); wire_id.append(w) # Retain per-wire material association.
                    eid = len(elements) # One-based element identifier.
                    if j == 0: face.append((eid, 3)) # Bottom outer boundary.
                    if i == nc - 1: face.append((eid, 4)) # Positive transverse boundary.
                    if j == nc - 1: face.append((eid, 5)) # Top outer boundary.
                    if i == 0: face.append((eid, 6)) # Negative transverse boundary.
        surfaces[f"W{w}"] = face # Never merge adjacent wires.
    wire_nodes, wire_elements = len(nodes), len(elements) # Preserve explicit wire mesh extent.
    saddle_node_map = {} # Merge only the physical welded saddle plate interfaces.
    fixed = [] # Base support nodes.
    saddle_faces = [] # Top plate and inner rail contact faces.
    def snode(k: int, y: float, z: float) -> int: # Saddle node deduplication by source geometry coordinates.
        key = (k, round(y, 8), round(z, 8)) # Stable exact interface key.
        if key not in saddle_node_map: saddle_node_map[key] = len(nodes) + 1; p = point(theta[k], y, 0.0); nodes.append((p[0], p[1], p[2] + z)) # Source saddle arcs use vertical plate offsets.
        return saddle_node_map[key] # Existing interface nodes are reused.
    ys = sorted(set([-200.0, -75.0, -55.0, 55.0, 75.0, 200.0] + list(np.linspace(-55.0, 55.0, 23)))) # Source400mm width,20mm rails,110mm opening.
    for k in range(nx): # Bearing and rail strips along actual arc.
        for i, (ya, yb) in enumerate(zip(ys[:-1], ys[1:])): # Base mesh conforming to rail boundaries.
            conn = [snode(k, ya, -30.0), snode(k, yb, -30.0), snode(k, yb, 0.0), snode(k, ya, 0.0), snode(k + 1, ya, -30.0), snode(k + 1, yb, -30.0), snode(k + 1, yb, 0.0), snode(k + 1, ya, 0.0)] # Thirty-mm source plate.
            elements.append(conn); wire_id.append(0); fixed.extend((conn[0], conn[1], conn[4], conn[5])) # Concrete-supported base boundary assumption.
            if ya >= -55.0 and yb <= 55.0: saddle_faces.append((len(elements), 5)) # Central bearing surface only.
        for side, (ya, yb) in enumerate(((-75.0, -55.0), (55.0, 75.0))): # Two real20mm guide plates.
            for za, zb in zip(np.linspace(0.0, 110.0, 6)[:-1], np.linspace(0.0, 110.0, 6)[1:]): # Source110mm rail height.
                conn = [snode(k, ya, za), snode(k, yb, za), snode(k, yb, zb), snode(k, ya, zb), snode(k + 1, ya, za), snode(k + 1, yb, za), snode(k + 1, yb, zb), snode(k + 1, ya, zb)] # Solid rail cells.
                elements.append(conn); wire_id.append(0) # Rail belongs to saddle material.
                saddle_faces.append((len(elements), 4 if side == 0 else 6)) # Actual inner channel walls.
    surfaces["SADDLE"] = saddle_faces # Real contact geometry.
    pairs = [(i + 1, j + 1) for i in range(count) for j in range(i + 1, count) if np.linalg.norm(centers[i] - centers[j]) < (diameter + packing_clearance) * 1.01] # Preserve every nearest-neighbor contact relationship when a candidate gap is explicitly selected.
    xyz, conn = np.asarray(nodes), np.asarray(elements, dtype=np.int64) # Full physical mesh arrays.
    vtkpath = out / "saddle_mesh.vtk" # Native VTK geometry for ParaView/CGX, no synthetic result field.
    with vtkpath.open("w") as f: # Export topology directly from actual solver mesh.
        f.write(f"# vtk DataFile Version 3.0\nExplicit {count}-wire saddle; geometry only\nASCII\nDATASET UNSTRUCTURED_GRID\nPOINTS {len(nodes)} double\n") # Native geometry header.
        for p in nodes: f.write(" ".join(f"{v:.10g}" for v in p) + "\n") # Physical node coordinates.
        f.write(f"CELLS {len(elements)} {9 * len(elements)}\n") # Exact connectivity count.
        for c in elements: f.write("8 " + " ".join(str(v - 1) for v in c) + "\n") # Convert to zero-based VTK numbering.
        f.write(f"CELL_TYPES {len(elements)}\n" + "12\n" * len(elements)) # VTK hexahedra.
        f.write(f"CELL_DATA {len(elements)}\nSCALARS wire_id int 1\nLOOKUP_TABLE default\n" + "\n".join(map(str, wire_id)) + "\n") # Material/component identities, not computed stress.
    lines = ["*HEADING", f"Zhaqing source-derived saddle, {count} explicit wires; packing/support assumptions retained; mm N MPa", "*NODE,NSET=ALL"] # Native solver model header.
    lines += [f"{i}," + ",".join(f"{v:.12g}" for v in p) for i, p in enumerate(nodes, 1)] # All physical nodes.
    lines += ["*ELEMENT,TYPE=C3D8,ELSET=BODY"] + [f"{i}," + ",".join(map(str, c)) for i, c in enumerate(elements, 1)] # Full integrated solid elements.
    def nset(name: str, ids: list[int]) -> None: # Explicit boundary node identifiers.
        lines.append(f"*NSET,NSET={name}") # Native node set.
        for start in range(0, len(ids), 16): lines.append(",".join(map(str, ids[start:start + 16]))) # Valid native line lengths.
    nset("LEFT", left); nset("RIGHT", right); nset("BASE", sorted(set(fixed))) # Transfer cuts and concrete support.
    lines += ["*ELSET,ELSET=WIRES,GENERATE", f"1,{wire_elements},1", "*ELSET,ELSET=PLATES,GENERATE", f"{wire_elements + 1},{len(elements)},1"] # Separate material regions.
    for name, faces in surfaces.items(): lines.extend([f"*SURFACE,NAME={name},TYPE=ELEMENT"] + [f"{eid},S{face}" for eid, face in faces]) # Actual contact facets.
    lines += ["*MATERIAL,NAME=WIRESTEEL", "*ELASTIC", f"{young:.12g},{poisson:.12g}", "*MATERIAL,NAME=SADDLE16MN", "*ELASTIC", "206000.,0.3", "*SOLID SECTION,ELSET=WIRES,MATERIAL=WIRESTEEL", "*SOLID SECTION,ELSET=PLATES,MATERIAL=SADDLE16MN", "*BOUNDARY", "BASE,1,3,0.", "LEFT,1,3,0."] # Elastic properties are declared assumptions; ultimate1670 is not used as yield.
    if plastic is not None: # Insert real material plasticity in the correct material block.
        at = lines.index("*MATERIAL,NAME=SADDLE16MN"); lines[at:at] = ["*PLASTIC"] + [f"{stress:.12g},{strain:.12g}" for stress, strain in curve] # Native nonlinear isotropic hardening, not an arbitrary neural proxy.
    for node in right: lines.extend(["*EQUATION", "2", f"{node},1,{math.sin(theta[-1]):.12g},{node},3,{math.cos(theta[-1]):.12g}"]) # Right cut radial constraint leaves tangential axial force free.
    if planar_right: # Match rigid-section global interface kinematics while keeping resultant axial force free.
        for w in range(count): # Separate cap for each explicit wire.
            cap = right[w * len(cross):(w + 1) * len(cross)]; reference = cap[0] # One independent tangential cut motion.
            for node in cap[1:]: lines.extend(["*EQUATION", "2", f"{node},3,1.,{reference},3,-1."]) # Existing radial MPC then makes tangential displacement equal across cap.
    lines += ["*BOUNDARY", "RIGHT,2,2,0.", "*SURFACE INTERACTION,NAME=FRICTIONAL", "*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=LINEAR", "200000.", "*FRICTION", f"{mu},10000."] # Research contact penalty/friction, not site-calibrated values.
    for w in range(1, count + 1): # One slave surface per wire avoids repeated-slave parser pathology.
        masters = ["SADDLE"] + [f"W{i}" for i, j in pairs if j == w] # Each neighboring pair appears exactly once.
        lines.append(f"*SURFACE,NAME=ENV{w},TYPE=ELEMENT") # Disjoint candidate master facets for this wire.
        for master in masters: lines.extend(f"{eid},S{face}" for eid, face in surfaces[master]) # Preserve all physical wire/plate interfaces.
        lines.extend(["*CONTACT PAIR,INTERACTION=FRICTIONAL,TYPE=SURFACE TO SURFACE", f"W{w},ENV{w}"]) # Grouping changes bookkeeping, not neighboring interaction coverage.
    if elastic_forming: # Optional compatible elastic bending import, not a fabricated plastic history.
        lines.append("*INITIAL CONDITIONS,TYPE=STRESS") # Native integration-point initial stresses.
        signs = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], dtype=float) # C3D8 natural node ordering.
        gauss = signs[[0,1,3,2,4,5,7,6]] / math.sqrt(3.0) # Preserve native CalculiX gauss3d2 order, which differs from corner-node order.
        shapes = np.prod(1.0 + gauss[:, None, :] * signs[None, :, :], axis=2) / 8.0 # Trilinear shape values.
        for e, cell in enumerate(conn[:wire_elements], 1): # Every actual wire solid receives a physical stress tensor.
            gp = shapes @ xyz[cell - 1] # Native element integration-point coordinates.
            wire = (e - 1) // (nx * nc * nc) # Exact explicit wire identity.
            for ip, pos in enumerate(gp, 1): # Per-integration-point bending field.
                angle = math.atan2(pos[0], pos[2] + radius) # Local longitudinal tangent angle.
                offset = float(shapes[ip - 1] @ (np.hypot(xyz[cell - 1, 0], xyz[cell - 1, 2] + radius) - radius - centers[wire, 1])) # Interpolate true nodal fiber offsets; avoid spurious chord-sag membrane stress.
                sigma = young * offset / (radius + centers[wire, 1]) + (load_n / count / np.sum(cap_area) if prestressed_equilibrium else 0.0) # Elastic bending plus consistently imported research axial prestress T/A when requested.
                co, si = math.cos(angle), math.sin(angle) # Rotate tangent stress to global frame.
                lines.append(f"{e},{ip},{sigma*co*co:.12g},0.,{sigma*si*si:.12g},0.,{-sigma*co*si:.12g},0.") # Native order XX YY ZZ XY XZ YZ.
    if prestressed_equilibrium: lines.extend(["*AMPLITUDE,NAME=INITIAL_TENSION", "0.,1.,1.,1."]) # Matching end resultant acts fully during imported-prestress equilibration, not ramped from zero.
    factors = ([1.0] if smoke else [1.0, 1.1, 0.9, 1.0]) if prestressed_equilibrium else (([0.0, 0.1] if smoke else [0.0, 1.0, 1.1, 0.9, 1.0]) if elastic_forming else ([0.1] if smoke else [1.0, 1.1, 0.9, 1.0])) # Clearly distinguish prestressed equilibrium from unloaded forming diagnostic.
    if load_factors is not None: factors=list(load_factors) # A controlled seating branch must preserve its complete actual loading sequence.
    if not factors or not np.isfinite(factors).all() or min(factors)<0 or (prestressed_equilibrium and factors[0]!=1.): raise ValueError('Invalid or inconsistent native load factors') # Do not stage an imported full prestress against a mismatched initial resultant.
    for step, factor in enumerate(factors): # Prestress then cyclic force modulation.
        lines += ["*STEP,NLGEOM,INC=1000", "*STATIC", "0.05,1.,1.e-7,0.1", "*CLOAD,OP=NEW,AMPLITUDE=INITIAL_TENSION" if prestressed_equilibrium and step == 0 else "*CLOAD,OP=NEW"] # Native nonlinear contact equilibrium path.
        for w in range(count): # Every wire receives its explicit share of end force.
            base = w * len(cross) # Right-cap index block.
            for q in range(len(cross)): # Initial uniform cap quadrature replaced below by consistent physical weights.
                node = right[base + q] # Actual node identifier.
                force = load_n * factor / count * cap_area[q] / np.sum(cap_area) # Consistent native traction weights sum to requested cable force.
                lines.extend([f"{node},1,{force * math.cos(theta[-1]):.12g}", f"{node},3,{-force * math.sin(theta[-1]):.12g}"]) # Tangential applied cable tension, no axial displacement constraint.
        lines += ["*NODE PRINT,NSET=RIGHT,FREQUENCY=1", "U,RF", "*EL PRINT,ELSET=WIRES,FREQUENCY=1", "S,E", "*NODE FILE,FREQUENCY=1", "U,RF", "*EL FILE,FREQUENCY=1", "S,E", "*CONTACT FILE,FREQUENCY=1", "CDIS,CSTR", "*END STEP"] # Native stress/strain/contact output, no placeholder fields.
    inp = out / "saddle.inp"; inp.write_text("\n".join(lines) + "\n") # Preserve reproducible complete native input.
    interface = {"units": {"length": "mm", "force": "N", "time": "s"}, "coordinate_system": "x longitudinal, y transverse, z up; saddle crown at z=0", "left": {"node_ids": left, "coordinates_mm": xyz[np.asarray(left) - 1].tolist()}, "right": {"node_ids": right, "coordinates_mm": xyz[np.asarray(right) - 1].tolist()}, "load_mode": "left displacement + right transverse/radial displacement and tangential force; never impose right tangential displacement simultaneously", "right_area_weights_mm2": np.tile(cap_area, count).tolist(), "left_area_weights_mm2": np.tile(cap_area, count).tolist(), "right_tangent": [math.cos(theta[-1]), 0.0, -math.sin(theta[-1])], "source_input_sha256": hashlib.sha256(inp.read_bytes()).hexdigest()} # Coupling contract.
    (out / "boundary_interface.json").write_text(json.dumps(interface, indent=2)) # Export true cut nodes.
    np.savez_compressed(out / "geometry.npz", coordinates=xyz, connectivity=conn - 1, wire_id=np.asarray(wire_id), wire_centers=centers, wire_neighbor_pairs=np.asarray(pairs)) # Actual full mesh for operator topology.
    meta = {"status": "GEOMETRY_AND_CONTACT_DECK_GENERATED", "wire_count": count, "wire_diameter_mm": diameter, "physical_nodes": len(nodes), "physical_hexahedra": len(elements), "wire_hexahedra": wire_elements, "wire_wire_contact_pairs": len(pairs), "wire_saddle_contact_pairs": count, "native_grouped_contact_definitions": count, "longitudinal_segments": nx, "cross_section_quads_per_wire": nc * nc, "wire_nodes": wire_nodes, "nominal_total_tension_n": load_n, "tension_provenance": "Explicit assumed research tension; default comes from old horizontal-force control and is NOT latest global saddle axial force", "friction_mu_assumed": mu, "wire_material": material, "plasticity_enabled": plastic is not None, "native_input_sha256": interface["source_input_sha256"], "drawing_evidence": {"wire": "03-缆索布置.dwg TEXT16B5:283根^5,1670MPa ultimate", "longitudinal_arc": "29-索鞍构造.dwg ARC4D8B radius150CADunit x10=1500mm", "bearing_plate": "29 TEXT20BB:400x30x1600", "rails": "29 TEXT2097:110x20x1600; cross-section LINE4EC5/4ED9 innergap110mm"}, "unverified_assumptions": ["283-wire cross-section packing order/compaction is an explicit hexagonal candidate, not measured", "Conformal plate-rail joins approximate welded assembly; weld toe geometry not modeled", "Saddle base fully fixed represents prescribed concrete support; concrete/anchors not resolved", "E,Poisson,friction,penalty and applied tension require calibrated inputs", "Source ARC span and nominal1600 plate length differ slightly; preserve ARC geometry without silent rescaling", "C3D8 discretization requires axial/cross-section/contact mesh convergence; coarse smoke is not fatigue-qualified", "No plasticity curve, fretting wear law, corrosion or calibrated strain-life data supplied", ("Elastic E*z/R imported bending is an approximation; actual forming/plastic residual stresses require validation" if elastic_forming else "Wires start curved and stress-free; wrapping residual bending stress is absent and must be resolved before fatigue qualification"), "Circumferential facet gaps and actual closed-contact counts require independent contact/mesh convergence"], "elastic_wrapping_initial_stress_requested": elastic_forming, "right_cut_planar": planar_right, "prestressed_equilibrium": prestressed_equilibrium, "equilibrium_boundary_note": "Initial axial T/A plus bending, matched full end resultant at first increment" if prestressed_equilibrium else "No imported axial prestress", "forming_method": "Imported elastic E*z/R bending stress followed by zero-load equilibration" if elastic_forming else "stress-free curved reference", "complete_cycle_requested": not smoke, "real_bridge_training_eligible": False, "fatigue_life_cycles": None} # Never promote an unvalidated mesh to bridge truth.
    meta['requested_load_factors']=factors; meta['load_path_coordinate']='Dimensionless static step parameter, not physical dynamic time'; meta['candidate_wire_clearance_mm']=packing_clearance # Preserve the complete path and any deliberately changed packing assumption.
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n") # Persist source and scope.
    return meta # Return machine-readable counts.

def main() -> None: # Command-line builder.
    p = argparse.ArgumentParser(description=__doc__) # Native workflow entrypoint.
    p.add_argument("output", type=Path); p.add_argument("--nx", type=int, default=64); p.add_argument("--nc", type=int, default=4) # Explicit mesh controls.
    p.add_argument("--prestressed-equilibrium", action="store_true"); p.add_argument("--wire-material-json", type=Path); p.add_argument("--free-warping-right-cut", action="store_true"); p.add_argument("--elastic-forming-stress", action="store_true"); p.add_argument("--wires", type=int, default=283); p.add_argument("--tension", type=float, default=716150.20485); p.add_argument("--mu", type=float, default=0.2); p.add_argument("--smoke", action="store_true") # Separate research load/diagnostic scope.
    a = p.parse_args() # Parse request.
    if a.nx < 2 or a.nc < 2 or a.nc % 2 or not 1 <= a.wires <= 360 or a.tension <= 0 or not 0 <= a.mu <= 1: raise ValueError("Invalid explicit mesh/load settings") # Fail closed on invalid inputs.
    if a.prestressed_equilibrium and not a.elastic_forming_stress: raise ValueError("Prestressed equilibrium requires explicit imported-stress construction") # Do not silently omit initial axial stress.
    print(json.dumps(build(a.output, a.nx, a.nc, a.wires, a.tension, a.mu, a.smoke, a.elastic_forming_stress, not a.free_warping_right_cut, json.loads(a.wire_material_json.read_text()) if a.wire_material_json else None, a.prestressed_equilibrium), ensure_ascii=False)) # Report genuine generated counts.

if __name__ == "__main__": main() # Run reproducible CLI.
