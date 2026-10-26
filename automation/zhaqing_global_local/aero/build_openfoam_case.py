"""Generate a native Gmsh/OpenFOAM1912 section case from source-bound polygons."""  # No coefficient values are assumed.
import argparse  # Provide reproducible case inputs.
import hashlib  # Bind each generated case to source geometry.
import json  # Read the geometry evidence contract.
import math  # Convert angle and turbulence scales.
from pathlib import Path  # Write the native solver case tree.
import numpy as np  # Validate source polygons without plotting.


def write_foam(path, object_name, body, kind="dictionary"):  # Emit standard OpenFOAM dictionaries.
    path.parent.mkdir(parents=True, exist_ok=True)  # Create only the requested case tree.
    header = f"FoamFile {{ version 2.0; format ascii; class {kind}; object {object_name}; }}"  # Name the native dictionary object.
    path.write_text(header + " // Native OpenFOAM header.\n" + "\n".join(line + " // Generated source-bound case entry." for line in body) + "\n", encoding="utf-8")  # Annotate every generated solver-code line.


def build_case(contract_path, output, angle_deg=0.0, speed_mps=10.0, mesh_size_m=0.004, convective_times=40.0, allow_partial=False, max_co=0.5):  # Parameterize the actual section calculation.
    contract_path, output = Path(contract_path), Path(output)  # Normalize paths for provenance.
    geometry = json.loads(contract_path.read_text(encoding="utf-8"))  # Load actual drawing-derived outlines.
    if geometry.get("geometry_verified") is not True or not geometry.get("source_dwg_sha256") or not geometry.get("entity_handles"):  # Require source-backed geometry even for a partial section.
        raise ValueError("source drawing, outline entity handles and geometry verification are required")  # Refuse invented bluff bodies.
    if geometry.get("scope") != "FULL_BRIDGE_AERODYNAMIC_SECTION" and not allow_partial:  # Separate a real component from the full bridge section.
        raise ValueError("PARTIAL_SECTION: explicit --allow-partial is required; coefficients cannot represent full bridge")  # Prevent accidental production use.
    width = float(geometry["reference_width_m"])  # Define the coefficient reference width.
    if min(width, speed_mps, mesh_size_m, convective_times, max_co) <= 0:  # Reject invalid flow and mesh scales.
        raise ValueError("width, speed, mesh size and duration must be positive")  # Preserve valid nondimensional quantities.
    polygons = [np.asarray(points, dtype=float) for points in geometry["polygons_m"]]  # Keep every source component as an obstacle.
    for points in polygons:  # Check all source components independently.
        if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.all(np.isfinite(points)):  # Enforce finite planar loops.
            raise ValueError("each polygon needs at least three finite xy vertices")  # Reject unusable outlines.
    output.mkdir(parents=True, exist_ok=True)  # Create the complete native CFD case.
    span = width * 0.1  # Use a one-cell extrusion with explicitly known force normalization.
    point_id, line_id, loops, obstacle_lines = 1, 1, [], []  # Track deterministic Gmsh entity identifiers.
    geo = ["Mesh.MshFileVersion = 2.2;", "Mesh.Algorithm = 6;"]  # Generate a portable first-order Gmsh mesh.
    outer = np.array([[-10 * width, -10 * width], [20 * width, -10 * width], [20 * width, 10 * width], [-10 * width, 10 * width]])  # Keep far boundaries well outside the source section.
    for index, vertices in enumerate([outer] + polygons):  # Create the farfield and each physical obstacle loop.
        native = geometry.get("native_curves") if index == 1 and len(polygons) == 1 else None  # Prefer exact source line/circle primitives when supplied.
        if native:  # Source CAD arcs should not force tiny chord cells.
            vertices = np.array([curve["start_m"] for curve in native])  # Each connected primitive contributes its starting point.
        if np.allclose(vertices[0], vertices[-1]):  # Avoid duplicate terminal points.
            vertices = vertices[:-1]  # Gmsh closes the curve loop explicitly.
        area = np.sum(vertices[:, 0] * np.roll(vertices[:, 1], -1) - vertices[:, 1] * np.roll(vertices[:, 0], -1)) / 2  # Compute loop orientation.
        if area == 0:  # Refuse zero-area source geometry.
            raise ValueError("zero-area source polygon")  # Avoid invalid mesh domains.
        if (index == 0 and area < 0) or (index > 0 and area > 0):  # Orient outer loop counterclockwise and holes clockwise.
            if native:  # Reversing native arcs requires an explicit source-order correction.
                raise ValueError("native source curves must form a clockwise hole boundary")  # Do not silently reverse circular geometry.
            vertices = vertices[::-1]  # Change ordering only, retaining exact points.
        ids = list(range(point_id, point_id + len(vertices)))  # Allocate this loop's points.
        for pid, point in zip(ids, vertices):  # Write source-bound point coordinates.
            geo.append(f"Point({pid}) = {{{point[0]:.15g},{point[1]:.15g},0,{width / 3 if index == 0 else mesh_size_m:.15g}}};")  # Refine each physical section boundary.
        edges = list(range(line_id, line_id + len(vertices)))  # Allocate this loop's line identifiers.
        center_count = 0  # Allocate separate exact arc-center points.
        for local_index, (eid, first, second) in enumerate(zip(edges, ids, ids[1:] + ids[:1])):  # Connect consecutive source vertices.
            if native and native[local_index]["kind"] == "ARC":  # Keep source root fillets exactly circular.
                center_id = point_id + len(vertices) + center_count  # Allocate the next arc-center point.
                center = native[local_index]["center_m"]  # Read the original source arc center.
                geo.append(f"Point({center_id}) = {{{center[0]:.15g},{center[1]:.15g},0,{mesh_size_m:.15g}}};")  # Preserve SI source coordinates.
                geo.append(f"Circle({eid}) = {{{first},{center_id},{second}}};")  # Mesh the actual source curve directly.
                center_count += 1  # Advance native arc-center allocation.
            else:  # Original straight source edges remain straight.
                geo.append(f"Line({eid}) = {{{first},{second}}};")  # Preserve concave section topology.
        loop = index + 1  # Give each component a stable loop identifier.
        geo.append(f"Curve Loop({loop}) = {{{','.join(map(str, edges))}}};")  # Close the loop without inventing material.
        loops.append(loop)  # Record the outer boundary and holes.
        if index > 0:  # Only physical obstacles enter the near-wall refinement list.
            obstacle_lines.extend(edges)  # Track all source edges.
        point_id += len(vertices) + center_count  # Advance point allocation including native arc centers.
        line_id += len(vertices)  # Advance edge allocation.
    geo.extend([f"Plane Surface(1000) = {{{','.join(map(str, loops))}}};", f"Field[1] = Distance;", f"Field[1].EdgesList = {{{','.join(map(str, obstacle_lines))}}};", "Field[2] = Threshold;", "Field[2].InField = 1;", f"Field[2].SizeMin = {mesh_size_m};", f"Field[2].SizeMax = {width / 3};", f"Field[2].DistMin = {width / 20};", f"Field[2].DistMax = {3 * width};", "Background Field = 2;"])  # Retain useful resolution through the near wake without tessellation-induced point refinement.
    geo.append(f"ext[] = Extrude {{0,0,{span}}} {{ Surface{{1000}}; Layers{{1}}; Recombine; }};")  # Make the native one-layer2D computational volume.
    geo.extend(['Physical Surface("frontBack") = {1000,ext[0]};', 'Physical Surface("farfield") = {ext[2],ext[3],ext[4],ext[5]};', f'Physical Surface("section") = {{{",".join(f"ext[{6 + i}]" for i in range(len(obstacle_lines)))}}};', 'Physical Volume("fluid") = {ext[1]};'])  # Name all OpenFOAM boundary patches.
    (output / "section.geo").write_text("\n".join(line + " // Source-bound CFD mesh entry." for line in geo) + "\n", encoding="utf-8")  # Save reproducible native mesher input.
    angle = math.radians(angle_deg)  # Use the same sign convention as the load-transfer module.
    cx, cy = math.cos(angle), math.sin(angle)  # Set freestream direction explicitly.
    vector = f"({speed_mps * cx:.12g} {speed_mps * cy:.12g} 0)"  # Native CFDx/y correspond to bridgey/z.
    turbulence_k = 1.5 * (0.01 * speed_mps) ** 2  # Use stated1%inlet turbulence solely as a declared CFD scenario.
    turbulence_omega = math.sqrt(turbulence_k) / (0.09 ** 0.25 * 0.07 * width)  # Use declared0.07B turbulence length for this sensitivity case.
    fields = {"U": ("volVectorField", "[0 1 -1 0 0 0 0]", vector, f"type freestream; freestreamValue uniform {vector}; value uniform {vector};", "type noSlip;"), "p": ("volScalarField", "[0 2 -2 0 0 0 0]", "0", "type freestreamPressure; freestreamValue uniform 0; value uniform 0;", "type zeroGradient;"), "k": ("volScalarField", "[0 2 -2 0 0 0 0]", str(turbulence_k), f"type inletOutlet; inletValue uniform {turbulence_k}; value uniform {turbulence_k};", f"type kqRWallFunction; value uniform {turbulence_k};"), "omega": ("volScalarField", "[0 0 -1 0 0 0 0]", str(turbulence_omega), f"type inletOutlet; inletValue uniform {turbulence_omega}; value uniform {turbulence_omega};", f"type omegaWallFunction; value uniform {turbulence_omega};"), "nut": ("volScalarField", "[0 2 -1 0 0 0 0]", "0", "type calculated; value uniform 0;", "type nutkWallFunction; value uniform 0;")}  # Define explicit physical boundary conditions.
    for name, (kind, dimensions, internal, farfield, wall) in fields.items():  # Emit all incompressible URANS fields.
        write_foam(output / "0" / name, name, [f"dimensions {dimensions};", f"internalField uniform {internal};", "boundaryField", "{", f"farfield {{ {farfield} }}", f"section {{ {wall} }}", "frontBack { type empty; }", "}"], kind)  # Keep2D boundaries and wall treatment explicit.
    write_foam(output / "constant/transportProperties", "transportProperties", ["transportModel Newtonian;", "nu [0 2 -1 0 0 0 0] 1.5e-5;"])  # Declare molecular viscosity in SI.
    write_foam(output / "constant/turbulenceProperties", "turbulenceProperties", ["simulationType RAS;", "RAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }"])  # Use the nativeSST URANS closure.
    end_time = convective_times * width / speed_mps  # Duration is expressed in flow-through section-width times.
    dt = width / speed_mps / 500  # Start with a conservative timestep before Courant adjustment.
    force = f"aero {{ type forceCoeffs; libs (\"libforces.so\"); writeControl timeStep; writeInterval 1; patches (section); rho rhoInf; rhoInf 1.225; CofR (0 0 0); liftDir ({-cy:.12g} {cx:.12g} 0); dragDir ({cx:.12g} {cy:.12g} 0); pitchAxis (0 0 1); magUInf {speed_mps}; lRef {width}; Aref {width * span}; }}"  # Use a documented commonB reference for all force components.
    write_foam(output / "system/controlDict", "controlDict", ["application pimpleFoam;", "startFrom startTime;", "startTime 0;", "stopAt endTime;", f"endTime {end_time};", f"deltaT {dt};", "writeControl adjustableRunTime;", f"writeInterval {end_time / 10};", "purgeWrite 2;", "writeFormat binary;", "writePrecision 10;", "writeCompression off;", "timeFormat general;", "timePrecision 10;", "runTimeModifiable true;", "adjustTimeStep yes;", f"maxCo {max_co};", f"maxDeltaT {width / speed_mps / 100};", "functions", "{", force, "yPlus { type yPlus; libs (\"libfieldFunctionObjects.so\"); writeControl writeTime; }", "}"])  # Persist aerodynamic coefficient and wall-resolution evidence.
    write_foam(output / "system/fvSchemes", "fvSchemes", ["ddtSchemes { default backward; }", "gradSchemes { default Gauss linear; }", "divSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); div(phi,k) Gauss upwind; div(phi,omega) Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }", "laplacianSchemes { default Gauss linear corrected; }", "interpolationSchemes { default linear; }", "snGradSchemes { default corrected; }", "wallDist { method meshWave; }"])  # Specify spatial and temporal discretization explicitly.
    write_foam(output / "system/fvSolution", "fvSolution", ["solvers", "{", "p { solver GAMG; tolerance 1e-8; relTol 0.01; smoother GaussSeidel; }", "pFinal { $p; relTol 0; }", "\"(U|k|omega)\" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.01; }", "\"(U|k|omega)Final\" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0; }", "}", "PIMPLE { nOuterCorrectors 2; nCorrectors 2; nNonOrthogonalCorrectors 1; momentumPredictor yes; }", "relaxationFactors { equations { \".*\" 1; } }"])  # Retain nonlinear pressure-velocity corrections.
    write_foam(output / "system/changeDictionaryDict", "changeDictionaryDict", ["boundary", "{", "frontBack { type empty; }", "section { type wall; }", "}"])  # OpenFOAM1912 accepts replacement dictionary names directly.
    run = ["#!/usr/bin/env bash", "set -euo pipefail", "cd -- \"$(dirname -- \"$0\")\"", "gmsh -3 -format msh2 section.geo -o section.msh > log.gmsh 2>&1", "gmshToFoam section.msh > log.gmshToFoam 2>&1", "changeDictionary > log.changeDictionary 2>&1", "checkMesh -allGeometry -allTopology > log.checkMesh 2>&1", "grep -q 'Mesh OK' log.checkMesh", "pimpleFoam > log.pimpleFoam 2>&1"]  # Fail before solving when any mesh step fails.
    (output / "Allrun").write_text(run[0] + "\n" + "\n".join(line + " # Execute native CFD stage." for line in run[1:]) + "\n", encoding="utf-8")  # Save a restartable command sequence.
    (output / "Allrun").chmod(0o755)  # Permit an explicit native execution.
    record = {"status": "GENERATED_NOT_SOLVED", "geometry_contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(), "geometry_scope": geometry["scope"], "is_full_bridge_coefficient": False, "solver": "OpenFOAM1912 pimpleFoam kOmegaSST", "angle_deg": angle_deg, "speed_mps": speed_mps, "mesh_size_m": mesh_size_m, "reference_width_m": width, "extruded_span_m": span, "duration_s": end_time, "convective_times": convective_times, "reynolds_number": speed_mps * width / 1.5e-5, "inlet_turbulence_intensity": 0.01, "inlet_turbulence_length_over_width": 0.07, "production_acceptance_requires": ["complete actual bridge silhouette including rails/gaps/cut station", "mesh/domain/timestep refinement", "stationary coefficient averaging with uncertainty", "wall-yPlus applicability", "appropriate Reynolds-number range", "3D/spanwise sensitivity and benchmark validation"]}  # Never treat case generation as convergence or full bridge evidence.
    (output / "case_contract.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")  # Preserve limitations with the native model.
    record["max_courant"] = max_co  # Record the actual Courant timestep setting.
    record["time_step_refinement_passed"] = False  # Case generation never constitutes temporal validation.
    (output / "case_contract.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")  # Save the complete numerical-control provenance.
    return record  # Let callers report the exact generated scenario.


if __name__ == "__main__":  # Support reproducible command-line case creation.
    parser = argparse.ArgumentParser()  # Document all essential physical inputs.
    parser.add_argument("geometry")  # Require source geometry.
    parser.add_argument("output")  # Require a destination case directory.
    parser.add_argument("--angle", type=float, default=0)  # Set the actual incident wind angle.
    parser.add_argument("--speed", type=float, default=10)  # Set the incident wind speed in SI.
    parser.add_argument("--mesh-size", type=float, default=0.004)  # Set the boundary cell scale.
    parser.add_argument("--convective-times", type=float, default=40)  # Set physical duration inB/U units.
    parser.add_argument("--allow-partial", action="store_true")  # Explicitly acknowledge component-only CFD.
    parser.add_argument("--max-co", type=float, default=0.5)  # Make exploratory timestep settings reproducible.
    args = parser.parse_args()  # Read the scenario parameters.
    print(json.dumps(build_case(args.geometry, args.output, args.angle, args.speed, args.mesh_size, args.convective_times, args.allow_partial, args.max_co), indent=2))  # Report generation status without claiming a solution.
