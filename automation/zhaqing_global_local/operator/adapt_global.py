"""Adapt genuine OpenSees bridge histories to the complete GNO data contract.""" # This is an explicit provenance-preserving data conversion, never a replacement FEM solve.
import argparse, hashlib, json # Freeze every actual solver artifact and transformation rule.
from pathlib import Path # Store adapted full fields next to the corresponding experiment evidence.
import numpy as np # Retain complete native arrays without generating any plot.
from scipy.sparse import coo_matrix # Represent actual member connectivity sparsely during body-component detection.
from scipy.sparse.csgraph import connected_components # Prevent metric neighborhoods from crossing disconnected members of the same label.
from data import sha256 # Reuse the trainer's exact content identity function.
from relations import radius_relation # Build mesh-independent physical integration supports on every native entity.

def adapt(case_paths, destination, source_input, scope_label): # Convert all explicitly supplied whole histories without opening arbitrary test cases during fitting.
    destination = Path(destination).resolve() # Resolve one persistent dataset location for all relative artifact paths.
    destination.mkdir(parents=True, exist_ok=True) # Preserve complete adapted arrays and conversion evidence.
    rows, relation_names, field_names, cached_graph, graph_key = [], None, None, None, None # Reuse topology only when original coordinate and feature arrays are identical.
    for manifest_path in case_paths: # Preserve the caller's explicit independent whole-history assignments.
        path = Path(manifest_path).resolve() # Record exact native solver provenance.
        receipt = json.loads(path.read_text()) # Read numerical quality and model assumptions before opening fields.
        if receipt.get('quality') != 'VALID_CONVERGED': # A failed or partial solve cannot become an adapted training label.
            raise ValueError(f'Unqualified native solve: {path}') # Leave numerical failures outside the learning dataset.
        raw_path = Path(receipt['dataset']) # Locate the actual complete native solver output.
        if sha256(raw_path) != receipt['dataset_sha256']: # Ensure the exporter metadata describes these exact numerical labels.
            raise ValueError('Native dataset changed after solve') # Refuse stale or mixed result provenance.
        with np.load(raw_path, allow_pickle=False) as archive: # Load one complete native history without executable serialized objects.
            arrays = {key: archive[key] for key in archive.files} # Preserve every recorded input and output entity.
        groups = receipt['relation_types'] # Use the physical element-family vocabulary exported by the native model.
        outputs = receipt['output_channels'] # Retain all native displacement/rotation/velocity channels actually exported by this source version.
        if field_names is not None and outputs != field_names: # Do not mix old force-conditioned three-output histories with new external-wind complete-state histories.
            raise ValueError('Inconsistent native physical output vocabulary') # Require one unambiguous full-field prediction contract.
        field_names = outputs # Freeze the source's exact physical field and unit meanings.
        if receipt.get('control_channels') != ['external_transverse_wind_m_s', 'external_vertical_wind_m_s']: # Refuse FEM-feedback force histories as exogenous wind inputs.
            raise ValueError('Expected external wind controls; feedback-force-conditioned cases require a separately named experiment') # Prevent response-dependent applied loads from leaking into a claimed external-wind-to-response operator.
        if relation_names is not None and groups != relation_names: # Global datasets must keep relation indices consistent between cases.
            raise ValueError('Inconsistent physical relation vocabulary') # Do not silently reuse embeddings for another member class.
        relation_names = groups # Freeze the exact global physical semantic vocabulary.
        coordinates, features, quad = arrays['coordinates'], arrays['static_features'], arrays['quadrature'] # Retain native coordinates, member features and positive mass measures.
        current_key = hashlib.sha256(coordinates.tobytes() + features.tobytes() + quad.tobytes()).hexdigest() # Bind cached graph supports to the exact native discretization and measures.
        if cached_graph is None or current_key != graph_key: # Rebuild physical integration support when any native domain input changes.
            native_edges = arrays.get('edges', arrays.get('relation_edges')) # Accept either native exporter spelling while retaining its original topology evidence.
            native_types = arrays.get('edge_types', arrays.get('relation_types')) # Read matching original relation identities.
            graph_parts, type_parts, measure_parts, supports = [], [], [], [] # Keep every relation's physical integration convention explicit.
            for relation, group in enumerate(groups): # Separate mechanical member domains before geometric neighbor search.
                members = np.flatnonzero(features[:, 7 + relation] > 0) # Use explicit element-incidence semantics from the full FEM model.
                selected = native_edges[:, native_types == relation] # Restrict original connectivity to this actual physical family.
                adjacency = coo_matrix((np.ones(selected.shape[1]), (selected[0], selected[1])), shape=(len(coordinates), len(coordinates))).tocsr()[members][:, members] # Identify disconnected bodies without inferring contact from geometric proximity.
                count, components = connected_components(adjacency, directed=False) # Keep each disconnected cable or hanger as an independent integration domain.
                radius = 2500. if group in ('MAIN_CABLES', 'HANGERS', 'WIND_CABLES') else 500. # Freeze physical millimetre support radii independent of mesh spacing while the complete-domain integral supplies long-range context.
                for component in range(count): # Include every retained body component and every original source node.
                    ids = members[components == component] # Select one actual connected structural domain.
                    edges, types, measure = radius_relation(coordinates, ids, ids, radius, quad, relation) # Integrate all physical source mass within the fixed metric support.
                    graph_parts.append(edges) # Preserve every directed source-to-target quadrature contribution.
                    type_parts.append(types) # Retain the physical relation semantic label.
                    measure_parts.append(measure) # Preserve actual source mass before fixed-reference scaling.
                supports.append({'name': group, 'metric_radius_mm': radius, 'domain': 'same_native_connected_member_component', 'quadrature': 'source_total_lumped_mass_tonne', 'reference_measure_tonne': 1.}) # Disclose mass-weighted rather than volume-weighted integration explicitly.
            cached_graph = (np.concatenate(graph_parts, axis=1), np.concatenate(type_parts), np.concatenate(measure_parts), supports) # Keep every original entity while sharing reusable integration topology.
            graph_key = current_key # Associate the cache only with this exact native mesh identity.
        arrays['edges'], arrays['edge_types'], arrays['edge_measure'], supports = cached_graph # Replace shrinking FE one-ring supports with fixed physical kernel integration domains.
        arrays.pop('relation_edges', None) # Remove only the obsolete duplicate key, not any native entity.
        arrays.pop('relation_types', None) # Keep one unambiguous relation-index table.
        if arrays['times'][0] > 0: # Older native exporters kept prestate separately from transient frames.
            arrays['times'] = np.r_[0., arrays['times']] # Restore the true already-solved prestate at time zero.
            arrays['targets'] = np.concatenate((arrays['initial_state'][None], arrays['targets']), axis=0) # Prepend actual known prestate fields rather than a fabricated zero label.
            arrays['controls'] = np.concatenate((np.zeros_like(arrays['controls'][:1]), arrays['controls']), axis=0) # Variable aerodynamic force is zero at the permanent prestate.
        if not np.allclose(arrays['targets'][0], arrays['initial_state']): # Time-zero physical response must match the exact supplied known initial condition.
            raise ValueError('Native initial state mismatch after conversion') # Fail instead of silently overwriting an inconsistent label.
        name = receipt['case_id'] # Retain the original independent physical scenario identity.
        output = destination / (name + '.npz') # Store the exact full-field converted native case.
        np.savez_compressed(output, **arrays) # Preserve every native node and accepted solver time sample.
        input_contract = destination / (name + '_input_evidence.json') # Describe the complete native source identity behind the labels.
        input_contract.write_text(json.dumps({'source_input': str(Path(source_input).resolve()), 'source_input_sha256': sha256(source_input), 'source_native_receipt': str(path), 'source_native_receipt_sha256': sha256(path), 'native_exporter_sha256': receipt['source_code_sha256'], 'prestate_evidence': str(path.parent / 'prestate/equilibrium_summary.json'), 'prestate_sha256': sha256(path.parent / 'prestate/equilibrium_summary.json'), 'conversion_source_sha256': sha256(__file__), 'conversion': 'all_native_nodes;actual_initial_frame;fixed_physical_radius_mass_kernel_support', 'scientific_scope_label': scope_label}, indent=2) + '\n') # Preserve the exact hypotheses and converter that define these model-specific labels.
        row = {'id': name, 'history_group': name, 'split': receipt['split'], 'quality': 'VALID_CONVERGED', 'geometry_status': 'DRAWING_DERIVED_ASSUMPTIONS', 'geometry_assumptions': receipt['model_assumptions'], 'all_native_entities_retained': True, 'native_entity_count': len(coordinates), 'solver_exit_code': 0, 'convergence_verified': True, 'relation_support': supports} # Keep research qualification distinct from as-built or aerodynamic validation.
        for key, value in [('npz', output), ('solver_input', input_contract), ('solver_result', raw_path), ('convergence_report', path), ('geometry_evidence', path.parent / 'prestate/equilibrium_summary.json')]: # Bind every training label to independent source and audit artifacts.
            row[key], row[key + '_sha256'] = str(value.resolve()), sha256(value) # Use exact content hashes even for artifacts stored outside the adapted directory.
        rows.append(row) # Preserve the originally registered case-level split.
    floors = [1.e-7 if 'rad' in name else .001 for name in field_names] # Keep rotation/angular-velocity and translation/velocity numerical floors in their actual native units.
    manifest = {'schema': 'zhaqing_fullfield_gno_dataset_v1', 'family': 'global', 'scientific_scope': 'research_simulation_with_assumptions', 'scope_label': scope_label, 'field_names': field_names, 'field_scale_floor': floors, 'control_channels': ['external_transverse_wind_m_s', 'external_vertical_wind_m_s'], 'relation_names': relation_names, 'relation_reference_measures': [1.] * len(relation_names), 'coordinate_scale': 10000., 'time_scale': 1., 'cases': rows, 'graph_support_source_sha256': sha256(Path(__file__).with_name('relations.py')), 'no_real_bridge_aerodynamic_validation': True, 'feedback_applied_loads_used_as_network_inputs': False} # Learn the complete response to external wind functions under documented provisional aerodynamic coefficients.
    target = destination / 'dataset_manifest.json' # Freeze the complete train/validation/test experiment definition.
    target.write_text(json.dumps(manifest, indent=2) + '\n') # Make every qualification and partition inspectable before training.
    return target # Return the exact manifest used by the actual GNO trainer.

if __name__ == '__main__': # Keep conversion explicit and independently reproducible.
    parser = argparse.ArgumentParser() # Require native case receipts and source identity rather than discovering arbitrary labels.
    parser.add_argument('--case-manifests', nargs='+', required=True) # Supply the complete frozen set of native whole-history artifacts.
    parser.add_argument('--source-input', required=True) # Identify the original drawing-derived bridge FEM input.
    parser.add_argument('--output', required=True) # Select a persistent adapted dataset directory.
    parser.add_argument('--scope-label', required=True) # Distinguish old-equivalent-deck diagnostics from corrected actual-deck research runs.
    args = parser.parse_args() # Parse exact conversion inputs once.
    print(adapt(args.case_manifests, args.output, args.source_input, args.scope_label)) # Report the actual frozen dataset manifest path.
