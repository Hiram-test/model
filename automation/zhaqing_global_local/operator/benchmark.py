"""Actual detailed-bridge graph throughput only; no finite-element labels or trained weights.""" # Synthetic channel values measure execution cost and cannot qualify a physical model.
import argparse, json, time # Record exact workload size and measured forward/backward wall time.
from pathlib import Path # Preserve the actual detailed native mesh identity.
import numpy as np # Construct physical incidence metadata without plotting.
import torch # Measure the deployed integral operator rather than a simplified cost formula.
from adapt_stream import build_graph # Use actual production physical-radius and exact rigid-interface graph construction.
from data import sha256 # Bind benchmark evidence to the actual native model contract and architecture source.
from gno import FullFieldGNO, OperatorConfig # Benchmark both explicitly named genuine integral-kernel candidates.
def benchmark(path, output, steps=4, threads=2, modes=('matrix', 'separable')): # Measure a complete actual spatial graph without claiming any trained engineering response.
    torch.set_num_threads(threads) # Bound CPU resource use to the declared reproducible budget.
    raw = json.loads(Path(path).read_text()) # Load the real native detailed geometry and original physical topology.
    ids = sorted(map(int, raw['nodes'])) # Preserve every actual native node.
    index = {value: i for i, value in enumerate(ids)} # Keep exact original node incidence under contiguous tensor indexing.
    xyz = np.asarray([raw['nodes'][str(value)] for value in ids]) # Retain actual spatial coordinates of the complete detailed bridge.
    groups = sorted({value['group'] for value in raw['elements'].values()} | {'RIGID_CONNECTIONS'}) # Keep all real element-family and physical-interface semantics.
    features = np.zeros((len(ids), 7 + len(groups))) # Synthetic material/BC magnitudes are explicitly excluded from engineering interpretation.
    relations = set() # Deduplicate only repeated directed incidence pairs of the same actual physical family.
    for element in raw['elements'].values(): # Preserve complete real material connectivity from the native detailed model.
        kind = groups.index(element['group']) # Keep actual physical relation vocabulary indices.
        nodes = [index[value] for value in element['nodes']] # Map every native element node to its complete tensor slot.
        features[nodes, 7 + kind] = 1. # Retain actual material-family incidence even though numerical channel values are benchmark fixtures.
        relations.update((a, b, kind) for a in nodes for b in nodes if a != b) # Include all original native element-neighbor relations.
    rigid = np.asarray([[index[item['master']], index[item['slave']]] for item in raw['rigid_connections']], dtype=np.int64).T # Preserve every actual master/slave constraint without radius replacement.
    for a, b in rigid.T: # Retain complete actual interface relations and endpoint semantics.
        kind = groups.index('RIGID_CONNECTIONS') # Keep physical constraints separate from material bodies.
        features[[a, b], 7 + kind] = 1. # Preserve both original rigid-arm endpoints.
        relations.update(((a, b, kind), (b, a, kind))) # Keep exact reciprocal information access across every real interface.
    edges = np.asarray(sorted(relations), dtype=np.int64) # Freeze deterministic actual native relation ordering.
    quadrature = np.ones(len(ids)) / len(ids) # Use explicitly synthetic positive magnitudes solely to measure operator work without native mass fields.
    arrays = dict(coordinates=xyz, static_features=features, quadrature=quadrature, relation_edges=edges[:, :2].T, relation_types=edges[:, 2], rigid_connection_edges=rigid) # Preserve actual native spatial and semantic graph sizes in the production builder.
    links, kinds, weights, supports = build_graph(arrays, groups) # Build exactly the production complete physical integration supports.
    mesh = {key: torch.as_tensor(value, dtype=torch.float32) for key, value in dict(coordinates=xyz / 10000., static_features=np.c_[features, xyz / 10000., np.zeros((len(ids), 12))], quadrature=quadrature, edge_measure=weights, initial_state=np.zeros((len(ids), 12)), output_mask=np.ones((len(ids), 12))).items()} # Retain complete actual node count and twelve-channel output width with explicitly synthetic state values.
    mesh.update(edges=torch.as_tensor(links, dtype=torch.long), edge_types=torch.as_tensor(kinds, dtype=torch.long)) # Preserve every actual production integral edge.
    controls = torch.zeros(len(ids), 2) # Supply external-input shape only, not simulated wind-response labels.
    records = [] # Compare actual measured execution of the two explicitly named learned-kernel forms.
    for mode in modes: # Retain explicitly requested complete learned matrix or disclosed finite-rank kernel candidates.
        torch.manual_seed(17) # Make initialization deterministic without presenting random weights as trained results.
        model = FullFieldGNO(OperatorConfig('global', mesh['static_features'].shape[-1], 2, 12, len(groups), 8, 2, 4096, mode, 4)) # Benchmark the actual proposed full-native architecture and frozen latent dimensions.
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001) # Include the actual optimizer update in throughput measurement.
        first = time.perf_counter() # Measure one-time immutable topology preparation separately from repeated optimizer windows.
        preparation = model.prepare_mesh(mesh) # Populate only immutable geometry cache before measuring repeated full-native training work.
        cold_topology_seconds = time.perf_counter() - first # Report the exact initial topology setup cost rather than multiplying it by every temporal window.
        del preparation # Release unneeded learned factors before measuring the actual current optimizer window.
        started = time.perf_counter() # Time current-iterate learned-factor preparation and full forward/backward execution together.
        prepared, previous, hidden = model.prepare_mesh(mesh), mesh['initial_state'], None # Use the actual production geometry preparation and complete native recurrent state.
        objective = previous.new_tensor(0.) # Define a purely numerical fixture objective unrelated to bridge truth.
        for _ in range(steps): # Preserve every measured sequential recurrence step and all native entities.
            previous, hidden = model(prepared, controls, previous, hidden, .00625) # Execute the full production integral and causal memory transition.
            objective = objective + previous.square().mean() / steps # Differentiate a finite synthetic value solely to measure backward cost.
        objective.backward() # Exercise real kernel, factor, memory, and readout gradients.
        optimizer.step() # Include actual optimization arithmetic in the measured training window.
        train_seconds = time.perf_counter() - started # Measure complete native-graph forward/backward window wall time.
        started = time.perf_counter() # Measure independent cold inference separately from optimization.
        with torch.no_grad(): # Validation does not allocate or update gradient history.
            prepared, previous, hidden = model.prepare_mesh(mesh), mesh['initial_state'], None # Rebuild current-iterate geometry kernels exactly as production validation does.
            for _ in range(steps): # Measure the same complete spatial workload over explicit sequential steps.
                previous, hidden = model(prepared, controls, previous, hidden, .00625) # Preserve actual full-native inference arithmetic.
        inference_seconds = time.perf_counter() - started # Record real complete-field inference throughput.
        estimate = 300 * (6 * 3200 / steps * train_seconds + 2 * 3200 / steps * inference_seconds) / 3600 # Extrapolate the declared six-training/two-validation twenty-second 300-epoch protocol without claiming an observed long run.
        records.append({'kernel_mode': mode, 'kernel_rank': 4 if mode == 'separable' else None, 'measured_steps': steps, 'one_time_static_topology_seconds': cold_topology_seconds, 'forward_backward_optimizer_seconds': train_seconds, 'cold_inference_seconds': inference_seconds, 'extrapolated_300_epoch_hours_6_train_2_validation_3200_steps': estimate}) # Distinguish actual measured timing from workload extrapolation explicitly.
        del prepared, previous, hidden, objective, optimizer, model # Release retained autograd graphs before benchmarking the next full-native candidate.
    result = {'status': 'THROUGHPUT_ONLY_NOT_FEM_TRAINING', 'native_nodes': len(ids), 'physical_integral_edges': len(kinds), 'native_mesh_sha256': sha256(path), 'gno_source_sha256': sha256(Path(__file__).with_name('gno.py')), 'threads': threads, 'synthetic_fields_and_quadrature_magnitudes': True, 'all_actual_native_geometry_and_topology_retained': True, 'records': records} # Preserve actual resource evidence without any physical-accuracy claim.
    Path(output).parent.mkdir(parents=True, exist_ok=True) # Keep the resource estimate with actual experiment evidence.
    Path(output).write_text(json.dumps(result, indent=2) + '\n') # Persist exact measured timing for honest scheduling.
    print(json.dumps(result, indent=2), flush=True) # Report actual throughput and explicitly labeled extrapolation.
if __name__ == '__main__': # Require an explicit native geometry contract and benchmark output path.
    parser = argparse.ArgumentParser() # Keep benchmark workload auditable and reproducible.
    parser.add_argument('--mesh', required=True) # Select the actual complete detailed native mesh contract.
    parser.add_argument('--output', required=True) # Save measured resource evidence outside training-weight namespaces.
    parser.add_argument('--steps', type=int, default=4) # Declare the measured complete spatial-window length.
    parser.add_argument('--modes', nargs='+', choices=['matrix', 'separable'], default=['matrix', 'separable']) # Benchmark selected explicitly named operator candidates without hidden architecture changes.
    args = parser.parse_args() # Parse one explicit throughput-only experiment.
    benchmark(args.mesh, args.output, args.steps, modes=args.modes) # Execute the actual full-spatial graph with no physical training claim.
