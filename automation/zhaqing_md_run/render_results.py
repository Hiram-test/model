#!/usr/bin/env python3  # Render the verified Zhaqing solver field without reconstructing geometry or inventing response values.
import argparse  # Accept explicit input and output paths for a reproducible rendering scene.
import hashlib  # Bind source, scene and image bytes to exact identities.
import json  # Save machine-readable data inventories and rendering receipts.
import os  # Select the probed headless EGL backend before importing VTK.
import sys  # Permit an isolated pinned VTK environment without altering the solver environment.
from pathlib import Path  # Resolve all source and rendering destinations explicitly.
import warnings  # Fail closed on unexpected Python reader or renderer warnings.
def sha(path):  # Compute exact byte identity for one evidence file.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Preserve the unmodified file content in the digest.
def main():  # Inspect verified solver data and render deterministic displacement views.
    repo = Path(__file__).resolve().parents[2]  # Locate the existing model repository from this source file.
    run = repo / 'build/zhaqing-md-20261024'  # Keep this run's post-processing separate from source model inputs.
    parser = argparse.ArgumentParser()  # Expose the reproducible scene parameters.
    parser.add_argument('--source', type=Path, default=run / 'calculation/cases/LC02_G_Q_SERVICE/stress-coordinated.vtk')  # Read the actual combined solver-backed primary response.
    parser.add_argument('--output', type=Path, default=run / 'figures/zhaqing_service_displacement.png')  # Name the high-resolution image requested for this run.
    parser.add_argument('--post', type=Path, default=run / 'post')  # Place inventory, environment and rendering evidence in the dedicated post folder.
    parser.add_argument('--deformation-scale', type=float, default=10.0)  # Magnify real nodal displacement only for visibility and disclose the factor in each view.
    parser.add_argument('--vtk-runtime', type=Path, default=repo.parent / 'render-runtime')  # Locate the isolated pinned EGL-capable VTK installation when present.
    args = parser.parse_args()  # Freeze every scene setting before loading the result.
    if args.vtk_runtime.is_dir():  # Prefer the isolated validated VTK package when supplied.
        sys.path.insert(0, str(args.vtk_runtime.resolve()))  # Avoid mixing the older GLX-only runtime with this scene.
    os.environ['VTK_DEFAULT_OPENGL_WINDOW'] = 'vtkEGLRenderWindow'  # Require the backend that passed the explicit off-screen probe.
    import numpy as np  # Compute only exact norms and unit conversions of existing solver vectors.
    import pyvista as pv  # Use the pinned finite-element VTK reader and renderer.
    import vtk  # Record the exact underlying geometry and OpenGL backend version.
    if pv.__version__ != '0.48.4' or vtk.vtkVersion.GetVTKVersion() != '9.5.2':  # Reject silently changed rendering software.
        raise RuntimeError('This scene requires PyVista 0.48.4 and VTK 9.5.2')  # Keep render reproducibility separate from package discovery.
    for name in ('data', 'scripts', 'figures', 'state', 'receipts'):  # Create the complete post-processing directory contract.
        (args.post / name).mkdir(parents=True, exist_ok=True)  # Preserve raw solver files outside the rendering tree.
    args.output.parent.mkdir(parents=True, exist_ok=True)  # Ensure the final image destination exists.
    summary_path = args.source.parent / 'summary.json'  # Read numerical acceptance from the actual corresponding solve.
    summary = json.loads(summary_path.read_text())  # Load the producer's field hashes and solve status.
    validation_path = args.post / 'receipts/service-vtk-validation.json'  # Require the independent strict VTK reconstruction already executed for this case.
    validation = json.loads(validation_path.read_text())  # Read independent topology, coordinate and field coverage evidence.
    if summary.get('status') != 'PASS' or validation.get('status') != 'PASS':  # Refuse an unqualified result or unverified conversion.
        raise RuntimeError('Numerical and independent VTK checks must pass before rendering')  # Avoid upgrading failed analysis through appearance.
    if sha(args.source) != summary['vtkSha256'] or sha(args.source) != validation['inputs']['vtkSha256']:  # Bind rendering to both verified identities.
        raise RuntimeError('VTK hash does not match numerical evidence')  # Stop on any stale or mutated mesh.
    with warnings.catch_warnings(record=True) as caught:  # Classify every reader warning before proceeding.
        warnings.simplefilter('always')  # Retain warnings that could indicate skipped geometry or incomplete fields.
        mesh = pv.read(args.source)  # Read the actual unstructured finite-element grid.
    if caught:  # Treat unexplained reader diagnostics as a blocked data gate.
        raise RuntimeError('VTK reader warnings: ' + '; '.join(str(w.message) for w in caught))  # Preserve the diagnostic rather than drawing an approximate picture.
    if mesh.n_points != 783 or mesh.n_cells != 1070 or set(np.unique(mesh.celltypes)) != {3, 9}:  # Verify the canonical primary node and line/shell populations.
        raise RuntimeError('Unexpected primary topology or cell families')  # Reject accidental whole-model/excluded-wind substitutions.
    arrays = []  # Inventory every published point and cell field before styling.
    for association, data in (('points', mesh.point_data), ('cells', mesh.cell_data)):  # Keep each field's actual association explicit.
        for name in data.keys():  # Inspect all arrays without assuming names from another case.
            values = np.asarray(data[name])  # Read the complete source array without interpolation.
            if not np.isfinite(values).all():  # Refuse NaN or partial numerical coverage.
                raise RuntimeError(f'Nonfinite source field: {name}')  # Identify the exact invalid source field.
            arrays.append({'name': name, 'association': association, 'shape': list(values.shape), 'components': int(values.shape[1]) if values.ndim > 1 else 1, 'finite_count': int(np.isfinite(values).sum()), 'coverage_count': int(len(values)), 'minimum': float(values.min()), 'maximum': float(values.max()), 'units': 'mm' if name == 'displacement_mm' else ('MPa' if 'mpa' in name else 'dimensionless_or_identifier')})  # Preserve full data coverage and extrema.
    displacement = np.asarray(mesh.point_data['displacement_mm'])  # Use the verified native/recovered three-component nodal displacement field.
    if displacement.shape != (783, 3):  # Demand one complete displacement vector per rendered point.
        raise RuntimeError('Incomplete displacement vectors')  # Refuse a fabricated or padded deformation field.
    magnitude = np.linalg.norm(displacement, axis=1)  # Derive nodal displacement magnitude exactly from the source vector.
    if not np.isclose(magnitude.max(), summary['maximumDisplacementMm'], rtol=1e-9, atol=1e-7):  # Cross-check field extrema against the numerical receipt.
        raise RuntimeError('Displacement magnitude differs from the solver summary')  # Reject mismatched response cases.
    limits = [float(magnitude.min()), float(magnitude.max())]  # Freeze the full finite range without visual percentile clipping.
    inventory = {'schema': 'calculix-contour-inventory-v1', 'source': str(args.source.resolve()), 'bytes': args.source.stat().st_size, 'sha256': sha(args.source), 'format': 'legacy_ascii_vtk', 'reader': 'PyVista legacy VTK reader', 'pyvista_version': pv.__version__, 'vtk_version': vtk.vtkVersion.GetVTKVersion(), 'point_count': mesh.n_points, 'cell_count': mesh.n_cells, 'cell_types': {str(t): int(np.sum(mesh.celltypes == t)) for t in np.unique(mesh.celltypes)}, 'bounds_mm': list(mesh.bounds), 'time_steps': [{'frame': 'final_static_equilibrium', 'pseudo_time': 1.0}], 'arrays': arrays, 'selected_field': 'displacement_magnitude_mm', 'association': 'points', 'formula': 'sqrt(U1**2 + U2**2 + U3**2)', 'source_vector': 'displacement_mm', 'coordinate_contract': 'source VTK points = F3 equilibrium coordinates + displacement_mm', 'coordinate_units': 'mm', 'display_coordinate_units': 'm', 'display_conversion': 'source coordinates / 1000', 'selected_range_mm': limits, 'derivation_receipt': str(validation_path.resolve()), 'status': 'PASS'}  # Record the complete data inspection contract before creating a scene.
    (args.post / 'receipts/service-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')  # Publish the accepted inventory independently from the image.
    probe = pv.Plotter(off_screen=True, window_size=(300, 200))  # Reconfirm the exact rendering environment before the full bridge scene.
    probe.set_background('white')  # Make a nonblank backend probe easy to verify numerically.
    probe.add_mesh(pv.Sphere(), color='navy')  # Use a standard probe object solely to test OpenGL output.
    probe_image = probe.screenshot(return_img=True)  # Capture the real off-screen framebuffer.
    backend = probe.render_window.GetClassName()  # Record the selected OpenGL implementation.
    probe_variance = float(probe_image.std())  # Check that geometry reached the image instead of a blank screen.
    probe.close()  # Release the independent probe context before rendering the actual result.
    if backend != 'vtkEGLRenderWindow' or probe_variance < 10.0:  # Require the approved nonblank EGL path.
        raise RuntimeError('Pinned off-screen rendering probe failed')  # Produce no contour with an unverified renderer.
    (args.post / 'receipts/backend-probe.json').write_text(json.dumps({'pyvista': pv.__version__, 'vtk': vtk.vtkVersion.GetVTKVersion(), 'backend': backend, 'pixel_standard_deviation': probe_variance, 'status': 'PASS'}, indent=2) + '\n')  # Preserve the actual backend probe evidence.
    reference = mesh.copy(deep=True)  # Keep an exact topology copy for the undeformed F3 overlay.
    reference.points = (mesh.points - displacement) / 1000.0  # Remove the already-applied source deformation once and convert mm to metres.
    displayed = mesh.copy(deep=True)  # Keep the identical result cells for the visible deformed field.
    displayed.points = (mesh.points - displacement + args.deformation_scale * displacement) / 1000.0  # Apply the disclosed display magnification exactly once.
    displayed.point_data['displacement_magnitude_mm'] = magnitude  # Preserve physical displacement magnitude despite cosmetic geometry magnification.
    panel_images = []  # Collect independent verified framebuffer images to avoid EGL multi-viewport compositing defects.
    camera_records = []  # Record the exact fitted camera of each view.
    center = np.asarray(reference.center)  # Derive camera targets from this actual bridge geometry.
    span = reference.bounds[1] - reference.bounds[0]  # Derive view distance from the longitudinal extent of this model.
    for row, title in enumerate(('ZHAQING SUSPENSION BRIDGE  |  LC02 service load', 'SIDE ELEVATION  |  same full displacement range')):  # Render two complementary views from the same verified field.
        plotter = pv.Plotter(off_screen=True, window_size=(3200, 900))  # Render each source-data view in its own proven single-viewport EGL context.
        plotter.set_background('white')  # Use the required clean white engineering presentation.
        plotter.add_mesh(reference, color='#a5a8ad', opacity=0.22, line_width=2.0, show_scalar_bar=False, lighting=False)  # Overlay the true undeformed geometry in faint gray.
        bar = {'title': 'Nodal |U| (mm)\nFinal static frame', 'vertical': True, 'position_x': 0.88, 'position_y': 0.18, 'height': 0.57, 'width': 0.055, 'n_labels': 6, 'fmt': '%.1f', 'title_font_size': 22, 'label_font_size': 20, 'color': '#202630'}  # Fix the readable field legend and exact full range.
        plotter.add_mesh(displayed, scalars='displacement_magnitude_mm', preference='point', cmap='viridis', clim=limits, line_width=4.5, render_lines_as_tubes=True, show_edges=False, lighting=False, scalar_bar_args=bar, show_scalar_bar=(row == 0))  # Draw only source cells with the real point-associated response field.
        plotter.add_text(title, position='upper_left', font_size=24, color='#161b22', font='arial')  # Label the exact bridge and case without covering the span.
        caption = f'Deformation x{args.deformation_scale:g}  |  gray = F3 reference  |  max |U| = {limits[1]:.3f} mm'  # State physical extrema and cosmetic magnification explicitly.
        plotter.add_text(caption, position='lower_left', font_size=18, color='#404750', font='arial')  # Keep the deformation convention visible next to each view.
        plotter.add_axes(line_width=2, labels_off=False, color='#404750', viewport=(0.02, 0.13, 0.10, 0.36))  # Show the verified global x/y/z orientation.
        if row == 0:  # Fit an oblique view of the complete source primary structure.
            plotter.camera_position = [tuple(center + np.array([0.12 * span, -0.95 * span, 0.33 * span])), tuple(center), (0.0, 0.0, 1.0)]  # Derive an isometric camera from the actual model bounds.
        else:  # Fit a true side elevation with longitudinal axis horizontal and vertical axis up.
            plotter.camera_position = [tuple(center + np.array([0.0, -span, 0.0])), tuple(center), (0.0, 0.0, 1.0)]  # Look along the negative global-y axis without rotating the physical bridge.
        plotter.enable_parallel_projection()  # Preserve engineering scale and avoid perspective distortion.
        plotter.reset_camera()  # Fit all deformed and undeformed cells with no geometry clipping.
        plotter.camera.parallel_scale = max(19.0, span / (2.0 * (3200.0 / 900.0) * 0.68))  # Reserve room for both the complete span and a non-overlapping right legend.
        if row == 1:  # Add an explicit geometric length reference only to the elevation.
            x0, x1, _y0, _y1, z0, _z1 = reference.bounds  # Read the true reference bounds in display metres.
            plotter.add_ruler((x0 + 0.08 * (x1 - x0), 0.0, z0 - 7.5), (x0 + 0.08 * (x1 - x0) + 20.0, 0.0, z0 - 7.5), title='Length (m)', number_labels=3, font_size_factor=0.6, label_size_factor=0.8, label_color='#404750', tick_color='#404750')  # Show a true 20-m scale bar without modifying the result mesh.
        shift = np.array([0.06 * span, 0.0, 0.0])  # Place the full model left of the legend without clipping any anchor or tower.
        plotter.camera.position = tuple(np.asarray(plotter.camera.position) + shift)  # Translate the eye and target together to preserve the intended viewing direction.
        plotter.camera.focal_point = tuple(np.asarray(plotter.camera.focal_point) + shift)  # Keep the reference geometry centered in the dedicated model area.
        plotter.camera.parallel_scale = max(19.0, span / (2.0 * (3200.0 / 900.0) * 0.68))  # Restore the explicit wide-panel scale after adding the ruler's automatic camera actor.
        plotter.reset_camera_clipping_range()  # Include every displayed source cell and geometric ruler within the depth range.
        camera_records.append({'view': 'isometric' if row == 0 else 'side_elevation', 'position': list(plotter.camera.position), 'focal_point': list(plotter.camera.focal_point), 'view_up': list(plotter.camera.up), 'parallel_scale': plotter.camera.parallel_scale, 'projection': 'parallel'})  # Persist each exact camera for reproducibility.
        plotter.enable_anti_aliasing('msaa', multi_samples=8)  # Use EGL-compatible multisampling without the defective multi-viewport SSAA compositor.
        panel_image = plotter.screenshot(return_img=True)  # Capture this independent source-data scene without any synthetic geometry.
        panel_images.append(panel_image)  # Retain the exact rendered pixels for simple vertical publication layout.
        plotter.close()  # Release each full-scene OpenGL context before starting another.
    from PIL import Image  # Assemble already rendered scientific panels without changing any field or geometry.
    image = np.concatenate(panel_images, axis=0)  # Place the two unchanged framebuffer images vertically in the final figure.
    Image.fromarray(image).save(args.output)  # Save the exact solver-rendered panel pixels as one high-resolution PNG.
    if image.shape[:2] != (1800, 3200) or image.std() < 3.0:  # Reject blank, clipped-buffer or wrong-sized output before delivery.
        raise RuntimeError('Final contour image is blank or has unexpected size')  # Preserve failure rather than publishing a misleading image.
    recipe = {'schema': 'calculix-render-scene-v1', 'source': str(args.source.resolve()), 'output': str(args.output.resolve()), 'views': camera_records, 'deformation_scale': args.deformation_scale, 'full_range_mm': limits, 'palette': 'viridis', 'resolution': [3200, 1800], 'line_width_pixels': 4.5, 'render_lines_as_tubes': True, 'cosmetic_tube_radius': None, 'coordinate_display_scale': 0.001, 'undeformed_opacity': 0.22}  # Store every visual choice independently of the rendered pixels.
    recipe_path = args.post / 'state/service-scene.json'  # Use a portable explicit JSON scene recipe for the PyVista backend.
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')  # Persist the scene recipe without changing solver files.
    receipt = {'schema': 'calculix-contour-render-v1', 'status': 'RENDERED_PENDING_VISUAL_QA', 'source_vtk_sha256': sha(args.source), 'source_canonical_dat_sha256': summary['canonicalResponseDatSha256'], 'independent_validation_sha256': sha(validation_path), 'numerical_summary_sha256': sha(summary_path), 'pyvista': pv.__version__, 'vtk': vtk.vtkVersion.GetVTKVersion(), 'backend': backend, 'field': 'displacement_magnitude_mm', 'association': 'points', 'frame': 'final_static_equilibrium', 'pseudo_time': 1.0, 'units': 'mm', 'formula': 'sqrt(U1**2 + U2**2 + U3**2)', 'averaging': 'none; direct nodal vector norm', 'range_policy': 'FULL', 'limits': limits, 'palette': 'viridis', 'deformation_vector': 'displacement_mm', 'deformation_scale': args.deformation_scale, 'representation': 'opaque shells and source line cells; display-only screen-space tube rendering', 'line_width_pixels': 4.5, 'cosmetic_radius': None, 'source_coordinates_already_deformed': True, 'reference_reconstruction': 'source points minus U', 'display_coordinate_units': 'm', 'camera': camera_records, 'dimensions': [3200, 1800], 'scene_script': str(Path(__file__).resolve()), 'scene_script_sha256': sha(__file__), 'scene_state_sha256': sha(recipe_path), 'image': str(args.output.resolve()), 'image_sha256': sha(args.output), 'numerical_qualification': summary['status'], 'engineering_release': summary['engineeringReleaseStatus'], 'excluded_groups': ['WIND_CABLES', 'WIND_ATTACH_LINKS'], 'caption': 'CalculiX solver-data contour: nodal displacement magnitude (mm), final static LC02, full range, deformation x10; primary system with wind-system exclusions inherited from the source contract.'}  # Keep render validity and engineering qualification separate and auditable.
    iteration_paths = sorted(args.source.parent.glob('*.outer-iterations.json'))  # Locate the main physical solve receipt without traversing support-audit subdirectories.
    if len(iteration_paths) != 1:  # Require one unambiguous nonlinear solve for this rendered case.
        raise RuntimeError('Expected one primary nonlinear iteration receipt')  # Reject missing or ambiguous native solver lineage.
    iteration_receipt = json.loads(iteration_paths[0].read_text())  # Read the actual terminal solver input and DAT identities.
    native_stem = iteration_paths[0].name.removesuffix('.outer-iterations.json') + f"_NL_{iteration_receipt['outerIterationCount']:02d}"  # Derive the final native step basename from the recorded iteration count.
    native_dat = args.source.parent / (native_stem + '.dat')  # Resolve the actual final CalculiX response table.
    native_frd = args.source.parent / (native_stem + '.frd')  # Resolve the same final native retained-structure FRD.
    if sha(native_dat) != iteration_receipt['terminalRawDatSha256']:  # Verify native solver lineage before linking it to a contour receipt.
        raise RuntimeError('Terminal native DAT hash differs from the nonlinear receipt')  # Refuse a stale or mixed final response.
    receipt['native_solver_lineage'] = {'iteration_receipt': str(iteration_paths[0]), 'iteration_sha256': sha(iteration_paths[0]), 'dat': str(native_dat), 'dat_sha256': sha(native_dat), 'frd': str(native_frd), 'frd_sha256': sha(native_frd), 'vtk_derivation': 'native CalculiX retained response plus original fixed-L0 corotational suspension recovery, independently reconciled against canonical DAT; not a standalone FRD-only conversion'}  # Preserve the full mixed-solver derivation without mislabeling analytic suspension fields as raw CCX values.
    receipt['anti_aliasing'] = {'mode': 'msaa', 'samples': 8, 'layout': 'two independent single-viewport framebuffer renders vertically concatenated without pixel modification'}  # Record the verified EGL display choice and exact panel composition.
    receipt_path = args.post / 'receipts/service-render.json'  # Preserve the required complete render evidence alongside inventory and scene state.
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')  # Require visual inspection before upgrading the image receipt to PASS.
    print(json.dumps({'image': str(args.output), 'receipt': str(receipt_path), 'max_displacement_mm': limits[1], 'status': receipt['status']}))  # Report actual generated artifacts for visual QA.
if __name__ == '__main__':  # Execute the renderer only when called explicitly.
    main()  # Run inspection, backend probe, scene generation and receipt creation in order.
