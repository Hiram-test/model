"""Lossless portable extraction of complete native motion supervision.""" # Raw acceleration, forces, and audit arrays remain in separately archived native results.
import hashlib, json, os, shutil # Preserve exact field identity and relocatable scientific evidence.
from pathlib import Path # Resolve original and relocated native case artifacts explicitly.
import h5py # Read and write original float64 response histories one native frame at a time.
import numpy as np # Build physical graph metadata without reducing responses or plotting.
from scipy.sparse import coo_matrix # Represent actual element and constraint connectivity.
from scipy.sparse.csgraph import connected_components # Separate disconnected physical bodies sharing one material label.
from data import sha256 # Reuse the trainer's bounded-memory artifact identity function.
from relations import radius_relation # Construct fixed physical-radius integral supports on all original entities.
STATIC = ('coordinates', 'quadrature', 'static_features', 'times', 'output_mask', 'initial_state', 'native_entity_ids') # Preserve every static array required by the complete native operator contract.
def copy_exact(source, destination): # Copy small source and success evidence without rewriting its contents.
    destination.parent.mkdir(parents=True, exist_ok=True) # Keep evidence beneath the declared portable dataset root.
    if destination.exists() and sha256(destination) != sha256(source): # Refuse a conflicting prior experiment under the same filename.
        raise ValueError('Conflicting existing evidence: ' + str(destination)) # Preserve the original frozen artifact identity.
    if not destination.exists(): # Identical already-copied source inputs can be shared between native histories.
        shutil.copy2(source, destination) # Preserve exact native evidence bytes.
    return destination # Return the portable copy used in the dataset manifest.
def build_graph(arrays, groups): # Define the physical integration graph from actual native material and interface topology.
    xyz, features, q = arrays['coordinates'], arrays['static_features'], arrays['quadrature'] # Retain complete original native entities and positive physical quadrature.
    native, kinds = arrays['relation_edges'], arrays['relation_types'] # Keep solver-exported material and real-connection relations distinct.
    parts, labels, weights, supports = [], [], [], [] # Preserve all physical domains with explicit integration conventions.
    for kind, group in enumerate(groups): # Retain the original solver's complete relation vocabulary and ordering.
        selected = native[:, kinds == kind] # Restrict topology to the current physical material or interface family.
        if group == 'RIGID_CONNECTIONS': # Real master/slave interfaces are defined by topology rather than metric proximity.
            exact = arrays.get('rigid_connection_edges', np.empty((2, 0), dtype=np.int64)) # Read original physical rigid-arm ownership when exported separately.
            selected = np.unique(np.concatenate((selected, exact, exact[::-1]), axis=1), axis=1) # Preserve every actual constraint in both information-flow directions without duplicate contributions.
            parts.append(selected) # Retain real long or short rigid arms exactly.
            labels.append(np.full(selected.shape[1], kind, dtype=np.int64)) # Preserve separate native interface semantics.
            weights.append(q[selected[0]]) # Use declared physical source nodal mass for every actual interface.
            supports.append({'name': group, 'domain': 'exact_native_master_slave_interfaces_bidirectional', 'quadrature': 'source_total_lumped_mass_tonne', 'reference_measure_tonne': 1.}) # Disclose exact topology-based physical interface support.
            continue # This exact interface domain needs no spatial-radius replacement.
        members = np.flatnonzero(features[:, 7 + kind] > 0) # Select actual native incidence semantics instead of inferred proximity.
        adjacency = coo_matrix((np.ones(selected.shape[1]), (selected[0], selected[1])), shape=(len(xyz), len(xyz))).tocsr()[members][:, members] # Keep disconnected cables, panels, and members physically separate.
        count, components = connected_components(adjacency, directed=False) # Recover real connected material domains before neighborhood integration.
        radius = 2500. if group in ('MAIN_CABLES', 'HANGERS', 'WIND_CABLES') else 500. # Freeze support radius in physical millimetres independently of mesh spacing.
        for component in range(count): # Include every original connected body and every native integration point.
            ids = members[components == component] # Preserve the complete original native body membership.
            edge, label, measure = radius_relation(xyz, ids, ids, radius, q, kind) # Integrate all original physical sources inside the declared metric neighborhood.
            parts.append(edge) # Retain complete directed source-to-target quadrature relations.
            labels.append(label) # Preserve material-family semantic identities.
            weights.append(measure) # Retain exact positive source physical measures.
        supports.append({'name': group, 'metric_radius_mm': radius, 'domain': 'same_native_connected_member_component', 'quadrature': 'source_total_lumped_mass_tonne', 'reference_measure_tonne': 1.}) # State the actual mass-based physical integration convention explicitly.
    return np.concatenate(parts, axis=1), np.concatenate(labels), np.concatenate(weights), supports # Return all original native entities' actual integral supports.
def adapt_stream(case_paths, destination, source_input, scope_label, storage_mode='external'): # Preserve complete accepted native histories under an explicit storage policy.
    destination, source_input = Path(destination).resolve(), Path(source_input).resolve() # Fix one portable dataset root and one recovered bridge input identity.
    destination.mkdir(parents=True, exist_ok=True) # Preserve converted fields and independent native evidence together.
    source_copy = copy_exact(source_input, destination / 'evidence/source_input.inp') # Copy the exact small native input once for this dataset.
    rows, names, groups, previous_key, cached = [], None, None, None, None # Reuse graph work only for byte-identical geometry and physical topology.
    for receipt_name in case_paths: # Keep original complete-history split assignments unchanged.
        path = Path(receipt_name).resolve() # Bind every label to an actual native case success receipt.
        receipt = json.loads(path.read_text()) # Inspect native numerical completion before opening its field store.
        if receipt.get('quality') != 'VALID_CONVERGED': # Failed or partial native solutions are never supervised reference labels.
            raise ValueError('Unqualified native solve: ' + str(path)) # Preserve native failure honestly.
        local_raw = path.parent / Path(receipt['dataset']).name # Prefer the case-local artifact after relocation between compute jobs.
        raw_path = local_raw if local_raw.is_file() else Path(receipt['dataset']) # Retain original absolute resolution only as an explicitly verified fallback.
        raw_hash = sha256(raw_path) # Identify every original native output and audit byte.
        if raw_hash != receipt['dataset_sha256'] or receipt.get('source_input_sha256', sha256(source_copy)) != sha256(source_copy): # Reject mismatched native fields or an unrelated source bridge input.
            raise ValueError('Native result or source input identity changed') # Do not combine mixed physical experiments under one scenario label.
        if receipt.get('control_channels') != ['external_transverse_wind_m_s', 'external_vertical_wind_m_s']: # Exogenous wind is distinct from response-dependent applied force histories.
            raise ValueError('Expected external wind controls') # Block response-feedback leakage into the claimed prediction inputs.
        if (names is not None and names != receipt['output_channels']) or (groups is not None and groups != receipt['relation_types']): # Every case must retain exactly the same output and relation meanings.
            raise ValueError('Inconsistent native vocabularies') # Reject silently mixed historical response contracts.
        names, groups, name = receipt['output_channels'], receipt['relation_types'], receipt['case_id'] # Freeze exact native semantic vocabularies and scenario identity.
        if Path(name).name != name or name in ('.', '..'): # Case names must not escape the portable dataset directory.
            raise ValueError('Unsafe native case identifier') # Prevent malformed receipt paths from changing artifact locations.
        output = destination / (name + '.h5') # Keep one independently hashable numerical supervision artifact per complete native history.
        with h5py.File(raw_path, 'r') as native: # Keep long numerical histories file-backed throughout conversion.
            arrays = {key: np.asarray(native[key]) for key in STATIC} # Load only static mesh metadata and the small complete native time vector.
            for key, alias in [('relation_edges', 'edges'), ('relation_types', 'edge_types')]: # Accept explicit native and historical topology key spellings.
                arrays[key] = np.asarray(native[key if key in native else alias]) # Retain complete actual native material and connection topology.
            if 'rigid_connection_edges' in native: # Preserve exact separately exported multi-point constraint incidence.
                arrays['rigid_connection_edges'] = np.asarray(native['rigid_connection_edges']) # Include every native master/slave connection in graph identity.
            frames, nodes = len(arrays['times']), len(arrays['coordinates']) # Preserve full accepted temporal and spatial resolution.
            if native.attrs.get('status') != 'COMPLETE' or int(native.attrs.get('expected_frames', -1)) != frames or int(native.attrs.get('written_frames', -1)) != frames or frames != receipt['time_steps'] + 1: # Cross-check native success metadata against actual full array lengths.
                raise ValueError('Incomplete native HDF5 history') # Never train from an interrupted solver stream.
            if arrays['times'][0] != 0. or not np.array_equal(native['targets'][0], arrays['initial_state']): # Preserve the actual known native prestate exactly.
                raise ValueError('Native initial state mismatch') # Do not fabricate an initial frame or borrow future labels.
            identity = hashlib.sha256() # Bind graph reuse to actual geometry, physical measures, and native connectivity.
            for key in ('coordinates', 'static_features', 'quadrature', 'relation_edges', 'relation_types', 'rigid_connection_edges'): # Include topology and rigid-arm identity rather than only coordinate arrays.
                if key in arrays: # Optional rigid-arm metadata can be absent for domains with no such interfaces.
                    identity.update(key.encode() + str(arrays[key].shape).encode() + arrays[key].tobytes()) # Distinguish same-node models with different physical connectivity.
            current_key = identity.hexdigest() # Freeze exact native graph identity for this complete case.
            if current_key != previous_key: # Rebuild physical integration supports when any graph-defining data changes.
                cached, previous_key = build_graph(arrays, groups), current_key # Share only the same exact native physical graph.
            edge, label, measure, supports = cached # Retain complete source measures and interface topology.
            comparison = hashlib.sha256() # Record exact native supervision values independently of HDF5 container encoding.
            with h5py.File(output, 'x') as target: # Never overwrite a previously frozen adapted dataset.
                target.attrs.update(status='RUNNING', storage_mode=storage_mode, native_source_sha256=raw_hash, numerical_conversion='lossless_native_supervision_extraction', spatial_reduction=False, temporal_reduction=False) # State actual provenance and retained resolution before conversion.
                for key in STATIC: # Copy all native static metadata without reducing physical degrees of freedom.
                    target.create_dataset(key, data=arrays[key], compression='gzip', compression_opts=1, shuffle=True) # Preserve exact original numeric types with lossless compression.
                for key, value in [('edges', edge), ('edge_types', label), ('edge_measure', measure)]: # Freeze actual continuum kernel supports beside the real native fields.
                    target.create_dataset(key, data=value, compression='gzip', compression_opts=1, shuffle=True) # Retain every physical source-to-target quadrature contribution.
                for key in ('targets', 'controls'): # Preserve complete supervised response and prescribed external wind histories.
                    source = native[key] # Keep original native field values on disk until their individual frame is needed.
                    if storage_mode == 'external': # Local adaptation can reuse immutable solver fields without duplicating large numerical arrays.
                        target[key] = h5py.ExternalLink(os.path.relpath(raw_path.resolve(), output.parent), '/' + key) # Keep the external link relative so the complete case tree can move intact.
                    else: # Standalone cloud datasets contain exact supervised arrays independently of large unrelated audit fields.
                        chunks = (1, min(nodes, 2048), source.shape[-1]) if source.ndim == 3 else (1, source.shape[-1]) # Bound each compression chunk while preserving every native frame.
                        target.create_dataset(key, shape=source.shape, dtype=source.dtype, chunks=chunks, compression='gzip', compression_opts=1, shuffle=True) # Preserve original float64 values without lossy quantization or sampling.
                    for index in range(frames): # Independently verify every complete native frame after transfer or external-link access.
                        value = np.asarray(source[index]) # Read one original full spatial field into bounded memory.
                        if not np.isfinite(value).all(): # A success receipt cannot make nonfinite field values acceptable.
                            raise ValueError('Nonfinite native supervision') # Reject invalid native reference fields before training.
                        if storage_mode == 'standalone': # Copy only actual supervised fields for independent cloud training storage.
                            target[key][index] = value # Retain original native precision, complete nodes, and original time ordering.
                        if not np.array_equal(target[key][index], value): # Verify every actual reference value after conversion.
                            raise ValueError('Native lossless extraction mismatch') # Never silently alter native arrays while packaging them.
                        comparison.update(key.encode() + str(index).encode() + value.tobytes()) # Bind the extraction receipt to every copied native supervised value.
                target.attrs.update(status='COMPLETE', expected_frames=frames, written_frames=frames, native_supervision_sha256=comparison.hexdigest()) # Mark completion only after full numerical identity verification.
        evidence_dir = destination / 'evidence' / name # Keep exact small native success and source evidence with the training case.
        receipt_copy = copy_exact(path, evidence_dir / 'case_manifest.json') # Preserve the original solver receipt and its full native-container hash unchanged.
        prestate_copy = copy_exact(path.parent / 'prestate/equilibrium_summary.json', evidence_dir / 'equilibrium_summary.json') # Preserve independent permanent-equilibrium and geometry-assumption evidence.
        snapshots = receipt.get('source_snapshots_sha256', {}) # Bind extraction to the actual executed native code when recorded by the solver.
        for filename, expected in snapshots.items(): # Preserve every explicitly hashed native source snapshot.
            source = path.parent / filename # Native executors archive exact source bytes beside case evidence.
            if not source.is_file() or sha256(source) != expected: # Reject missing or altered original execution code.
                raise ValueError('Native source snapshot missing or changed: ' + filename) # Do not substitute the latest checkout for the original executed source.
            copy_exact(source, evidence_dir / filename) # Persist the exact native execution snapshot as a small portable artifact.
        input_contract = evidence_dir / 'input_evidence.json' # Describe actual lossless extraction and distinct native archival scope.
        input_contract.write_text(json.dumps({'source_input': os.path.relpath(source_copy, destination), 'source_input_sha256': sha256(source_copy), 'native_receipt': os.path.relpath(receipt_copy, destination), 'native_receipt_sha256': sha256(receipt_copy), 'original_native_container_sha256': raw_hash, 'original_native_container_basename': raw_path.name, 'native_source_snapshots_sha256': snapshots, 'conversion_source_sha256': sha256(__file__), 'native_supervision_sha256': comparison.hexdigest(), 'all_frames_verified_array_equal': True, 'native_frames': frames, 'native_entities': nodes, 'supervision_dtype': str(arrays['initial_state'].dtype), 'solver_result_kind': 'extracted_supervision' if storage_mode == 'standalone' else 'original_native_container', 'separate_native_archive_required_for_audit_acceleration_and_cable_force': storage_mode == 'standalone', 'storage_mode': storage_mode, 'scientific_scope_label': scope_label}, indent=2) + '\n') # Never mislabel extracted true motion fields as the full original native audit container.
        row = {'id': name, 'history_group': receipt.get('history_group', name), 'split': receipt['split'], 'quality': 'VALID_CONVERGED', 'geometry_status': 'DRAWING_DERIVED_ASSUMPTIONS', 'geometry_assumptions': receipt['model_assumptions'], 'all_native_entities_retained': True, 'native_entity_count': nodes, 'solver_exit_code': 0, 'convergence_verified': True, 'relation_support': supports, 'dataset_format': 'hdf5', 'solver_result_kind': 'extracted_supervision' if storage_mode == 'standalone' else 'original_native_container'} # Preserve declared research assumptions and original independent-history split.
        for key, value in [('fields', output), ('solver_input', input_contract), ('solver_result', output if storage_mode == 'standalone' else raw_path), ('convergence_report', receipt_copy), ('geometry_evidence', prestate_copy)]: # Freeze actual supervised numerical fields and independent solver success evidence.
            row[key], row[key + '_sha256'] = os.path.relpath(value, destination), sha256(value) # Keep portable relative paths and exact immutable bytes.
        rows.append(row) # Retain every supplied complete physical scenario without dropping difficult histories.
    if not rows: # An empty experiment cannot become a completed training dataset.
        raise ValueError('No complete native histories supplied') # Reject zero-work success explicitly.
    manifest = {'schema': 'zhaqing_fullfield_gno_dataset_v1', 'family': 'global', 'scientific_scope': 'research_simulation_with_assumptions', 'scope_label': scope_label, 'field_names': names, 'field_scale_floor': [1.e-7 if 'rad' in name else .001 for name in names], 'control_channels': ['external_transverse_wind_m_s', 'external_vertical_wind_m_s'], 'relation_names': groups, 'relation_reference_measures': [1.] * len(groups), 'coordinate_scale': 10000., 'time_scale': 1., 'cases': rows, 'graph_support_source_sha256': sha256(Path(__file__).with_name('relations.py')), 'conversion_source_sha256': sha256(__file__), 'no_real_bridge_aerodynamic_validation': True, 'feedback_applied_loads_used_as_network_inputs': False, 'supervision_scope': 'complete_native_motion_fields_12_channels_cable_forces_are_separate_native_audit', 'storage_mode': storage_mode} # Preserve scientific scope and every full native motion output degree.
    result = destination / 'dataset_manifest.json' # Freeze a portable complete-history experiment definition.
    result.write_text(json.dumps(manifest, indent=2) + '\n') # Publish the manifest only after every supplied case converted successfully.
    return result # Return the actual portable dataset accepted by the trainer.
