"""Full-native-history GNO training, exact resume, and held-out evaluation.""" # The CLI refuses unqualified finite-element references.
import argparse, copy, csv, hashlib, json, os, time # Record complete execution and atomically preserve checkpoints.
from pathlib import Path # Store durable repository-backed results rather than volatile shared memory.
import numpy as np # Export numeric predictions for independent native or Gnuplot rendering.
import torch # Train the explicit quadrature integral operator.
from data import load_split, sha256 # Enforce geometry, convergence, provenance and complete-history partition gates.
from gno import FullFieldGNO, OperatorConfig # Instantiate only the new matrix-kernel architecture.

def write_json(path, value): # Publish complete evidence only after successful serialization.
    path = Path(path) # Permit both CLI strings and constructed output paths.
    path.parent.mkdir(parents=True, exist_ok=True) # Preserve intermediate progress in the actual output directory.
    temporary = path.with_suffix(path.suffix + '.pending') # Keep incomplete writes out of the published namespace.
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n') # Reject nonfinite scientific metrics during publication.
    os.replace(temporary, path) # Atomically expose the completed record.

def save_checkpoint(path, value): # Save model, optimizer, RNG and selection state together.
    path = Path(path) # Normalize the destination before constructing the temporary sibling.
    temporary = path.with_suffix('.pending') # A partial checkpoint must never be mistaken for a resumable epoch.
    torch.save(value, temporary) # Serialize complete tensors and execution metadata.
    os.replace(temporary, path) # Commit a completed epoch with one atomic replacement.

def fit_normalization(cases, manifest): # Derive scales solely from the declared training histories.
    weights = torch.cat([case['quadrature'] for case in cases]) # Use physical measures rather than counting discretization entities equally.
    static = torch.cat([case['static_features'] for case in cases]) # Retain every original training entity.
    static_mean = (static * weights[:, None]).sum(0) / weights.sum() # Estimate physical-domain input means.
    static_scale = (((static - static_mean).square() * weights[:, None]).sum(0) / weights.sum()).sqrt().clamp_min(1.e-6) # Avoid division by zero for constant semantic input channels.
    numerator = torch.zeros(cases[0]['targets'].shape[-1], device=weights.device) # Keep one independent scale for each physical output channel.
    denominator = torch.zeros_like(numerator) # Normalize only over observed native output entities.
    control_num = torch.zeros(cases[0]['controls'].shape[-1], device=weights.device) # Preserve units for every load input channel.
    control_den = weights.new_tensor(0.) # Accumulate actual physical sample measures.
    initial_num, initial_den = torch.zeros_like(numerator), torch.zeros_like(numerator) # Scale the known permanent initial state separately from the learned transient response.
    for case in cases: # Only training labels participate in this loop.
        temporal = time_weights(case['times'])[:, None, None] # Weight adaptive native time samples by physical elapsed time.
        measure = case['quadrature'][None, :, None] * case['output_mask'][None] * temporal # Account for actual duration and entity-specific field availability.
        numerator += ((case['targets'] - case['initial_state']).square() * measure).sum((0, 1)) # Normalize the actual transient change so large permanent-load deformation cannot hide wind-response errors.
        denominator += measure.sum((0, 1)) # Count exactly the observed physical measure through physical time.
        initial_num += (case['initial_state'].square() * case['quadrature'][:, None] * case['output_mask']).sum(0) # Preserve the known prestressed initial response as a separate input function.
        initial_den += (case['quadrature'][:, None] * case['output_mask']).sum(0) # Count only physically observed native initial fields.
        control_num += (case['controls'].square() * case['quadrature'][None, :, None] * temporal).sum((0, 1)) # Use a duration-weighted origin-preserving RMS for prescribed controls.
        control_den += case['quadrature'].sum() * temporal.sum() # Preserve the actual duration under adaptive time refinement.
    if torch.any(denominator == 0): # Missing physical channels must be removed explicitly from the declared output contract.
        raise ValueError('A declared output has no training observations') # Do not learn unavailable contact pressure from all-zero placeholders.
    floors = weights.new_tensor(manifest['field_scale_floor']) # Freeze physically meaningful minimum scales in the dataset manifest.
    if floors.shape != numerator.shape or torch.any(floors <= 0): # Every field needs a positive unit-aware error floor.
        raise ValueError('Invalid field_scale_floor') # Prevent unstable relative errors near zero reference response.
    return {'static_mean': static_mean.tolist(), 'static_scale': static_scale.tolist(), 'initial_condition_scale': torch.maximum((initial_num / initial_den).sqrt(), floors).tolist(), 'output_scale': torch.maximum((numerator / denominator).sqrt(), floors).tolist(), 'control_scale': (control_num / control_den).sqrt().clamp_min(1.e-9).tolist(), 'coordinate_scale': float(manifest['coordinate_scale']), 'time_scale': float(manifest['time_scale']), 'prediction_reference': 'known_initial_state_at_each_native_entity'} # Save actual train-derived transient scales without a physical response basis or spatial reduction.

def time_weights(times): # Integrate sampled histories with trapezoidal physical-time quadrature.
    intervals = times[1:] - times[:-1] # Respect adaptive solver sample spacing rather than sample count.
    weights = torch.zeros_like(times) # Preserve all original time samples.
    weights[:-1] += intervals / 2 # Assign half of each interval to its earlier endpoint.
    weights[1:] += intervals / 2 # Assign the other half to its later endpoint.
    return weights # The weights sum to actual elapsed duration.

def normalize(case, norm): # Apply one frozen training normalization to any complete history.
    result = dict(case) # Preserve physical labels and provenance in the caller's original tensors.
    tensor = lambda key: case['targets'].new_tensor(norm[key]) # Construct device- and dtype-compatible normalization constants.
    if norm['coordinate_scale'] <= 0 or norm['time_scale'] <= 0: # A physical scale is positive and independent of mesh density.
        raise ValueError('Coordinate and time scales must be positive') # Fail before corrupting the kernel's physical metric.
    result['coordinates'] = case['coordinates'] / norm['coordinate_scale'] # Use the same physical length normalization on every mesh.
    centroid = (case['coordinates'] * case['quadrature'][:, None]).sum(0) / case['quadrature'].sum() # Locate each entity relative to the physical mass/volume centroid without a mesh-degree bias.
    position = (case['coordinates'] - centroid) / norm['coordinate_scale'] # Supply native longitudinal/transverse/vertical geometry while preserving common-translation independence.
    result['static_features'] = torch.cat(((case['static_features'] - tensor('static_mean')) / tensor('static_scale'), position, case['initial_state'] / tensor('initial_condition_scale')), dim=-1) # Preserve physical semantic, centered geometry and complete known-initial-state input functions.
    result['controls'] = case['controls'] / tensor('control_scale') # Normalize the complete nodal loading history.
    result['targets'] = (case['targets'] - case['initial_state']) / tensor('output_scale') # Learn every native response change relative to the known solved prestate, retaining every physical degree.
    result['initial_state'] = torch.zeros_like(case['initial_state']) # The known initial response change is exactly zero; its physical state remains an explicit static input above.
    result['times'] = case['times'] / norm['time_scale'] # Expose actual normalized elapsed time to the causal operator.
    return result # Quadrature measures and edge topology are unchanged by normalization.

def field_loss(prediction, target, case): # Balance channels in their training-derived physical units.
    measure = case['quadrature'][:, None] * case['output_mask'] # Retain the complete native domain of every observed output field.
    return (((prediction - target).square() * measure).sum(0) / measure.sum(0).clamp_min(1.e-12)).mean() # Equal normalized channel weighting cannot erase unobserved-field masks.

def rollout(model, case): # Generate a full cold history without teacher forcing.
    case = model.prepare_mesh(case) # Compute exact geometry-only kernels once for this unchanged inference function.
    previous, hidden = case['initial_state'], None # Reset physical and learned memory at the known initial condition.
    states = [previous] # Preserve the native initial frame as part of the complete output history.
    for index in range(1, len(case['times'])): # Visit every native time sample exactly once.
        previous, hidden = model(case, case['controls'][index], previous, hidden, case['times'][index] - case['times'][index - 1]) # Feed only previously predicted response into the next operator step.
        states.append(previous) # Keep all native spatial outputs at every step.
    return torch.stack(states) # Return time-by-entity-by-field output without a response basis.

def metrics(predicted, case, output_scale, field_names): # Report physical error and robust relative error separately.
    duration = (case['times'][1:] - case['times'][:-1])[:, None, None] # Use right-endpoint interval integration over predicted frames, excluding the supplied initial state.
    measure = case['quadrature'][None, :, None] * case['output_mask'][None] * duration # Respect physical elapsed time and entity-specific observations.
    error = ((predicted[1:] - case['targets'][1:]).square() * measure).sum((0, 1)).sqrt() # Score every predicted interval with its actual duration.
    reference = (case['targets'][1:].square() * measure).sum((0, 1)).sqrt() # Preserve each complete duration-weighted reference norm.
    scale = error.new_tensor(output_scale) # Use only train-derived fixed scales for small-response stabilization.
    floor = scale * measure.sum((0, 1)).sqrt() # Normalize by the physical domain and actual predicted duration.
    dynamic = ((case['targets'][1:] - case['initial_state']).square() * measure).sum((0, 1)).sqrt() # Separate the wind-induced change from a potentially dominant permanent-load initial shape.
    normalized = error / torch.maximum(dynamic, floor).clamp_min(1.e-12) # Select on actual transient-change accuracy instead of the potentially dominant permanent response.
    rows = {name: {'weighted_L2_absolute': float(error[i]), 'reference_weighted_L2': float(reference[i]), 'relative_L2': float(error[i] / reference[i]) if reference[i] > 0 else None, 'scale_normalized_L2': float(normalized[i]), 'dynamic_reference_weighted_L2': float(dynamic[i]), 'dynamic_relative_L2': float(error[i] / dynamic[i]) if dynamic[i] > 0 else None, 'beats_hold_initial_baseline': bool(error[i] < dynamic[i])} for i, name in enumerate(field_names)} # Expose dynamic error and the constant-prestate baseline instead of hiding poor dynamics behind large static responses.
    return {'id': case['id'], 'mean_scale_normalized_L2': float(normalized.mean()), 'fields': rows, 'native_entities': len(case['coordinates']), 'predicted_time_steps': len(case['times']) - 1, 'physical_equilibrium_residual_evaluated': False} # Field accuracy alone is not an equilibrium certificate.

@torch.no_grad() # Validation cannot change model weights or read future states during rollout.
def evaluate(model, physical_cases, norm, manifest, destination=None): # Evaluate complete histories independently of training state.
    model.eval() # Freeze the prediction function during metric collection.
    records = [] # Keep individual difficult cases instead of reporting only a convenient average.
    for physical in physical_cases: # Visit every case in the explicitly selected partition.
        case = normalize(physical, norm) # Reuse training-only scales without refitting to validation or test labels.
        prediction = rollout(model, case) * physical['targets'].new_tensor(norm['output_scale']) + physical['initial_state'] # Restore the complete physical response by adding the known full native initial state.
        records.append(metrics(prediction, physical, norm['output_scale'], manifest['field_names'])) # Record the entire retained field error.
        if destination is not None: # Write exact numeric arrays for separate native scientific rendering.
            np.savez_compressed(Path(destination) / (physical['id'] + '_prediction.npz'), prediction=prediction.cpu().numpy(), times=physical['times'].cpu().numpy(), coordinates=physical['coordinates'].cpu().numpy()) # Do not make any Python data plot.
    return {'mean_scale_normalized_L2': float(np.mean([row['mean_scale_normalized_L2'] for row in records])), 'records': records, 'teacher_forcing': False, 'spatial_reduction': False} # Expose the exact metric and inference policy.

def train_epoch(model, optimizer, cases, window): # Train each full loading history once in a seeded random order.
    model.train() # Enable ordinary training behavior without mesh sampling.
    losses, updates = [], 0 # Count actual objective evaluations and optimizer work.
    for index in torch.randperm(len(cases)).tolist(): # Shuffle independent histories, never their internal time sequence.
        case = cases[index] # Retain the full physical graph for this history.
        previous, hidden = case['initial_state'], None # Start each history from its known initial response.
        for start in range(1, len(case['times']), window): # Bound temporal backpropagation memory while preserving causal prediction across every frame.
            optimizer.zero_grad(set_to_none=True) # Begin one actual temporal-window optimizer update.
            prepared = model.prepare_mesh(case) # Refresh differentiable kernels for the current parameter iterate before the temporal segment.
            loss = previous.new_tensor(0.) # Accumulate equally weighted field errors for the current causal segment.
            stop = min(len(case['times']), start + window) # Include the final shorter segment instead of discarding it.
            duration = case['times'][stop - 1] - case['times'][start - 1] # Weight errors by actual elapsed time within this temporal segment.
            for t in range(start, stop): # Use every original time frame inside this segment.
                previous, hidden = model(prepared, case['controls'][t], previous, hidden, case['times'][t] - case['times'][t - 1]) # Autoregress on predictions while reusing only unchanged geometry-conditioned kernels within this update.
                loss = loss + field_loss(previous, case['targets'][t], case) * (case['times'][t] - case['times'][t - 1]) / duration # Reference fields affect only the duration-weighted supervised objective.
            if not torch.isfinite(loss): # An unstable autoregression must not emit a successful checkpoint.
                raise FloatingPointError('Nonfinite full-history training loss') # Preserve failure rather than masking it with clipping or dropped cases.
            loss.backward() # Differentiate the explicit kernel integral through the retained temporal segment.
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.) # Bound gradients without changing spatial or physical labels.
            optimizer.step() # Perform one counted optimizer update.
            previous, hidden = previous.detach(), hidden.detach() # Carry the predicted state across segments while truncating only gradient history.
            losses.append(float(loss.detach())) # Record each actual loss evaluation.
            updates += 1 # Expose work beyond the ambiguous term epoch.
    return float(np.mean(losses)), updates # Return actual optimization work and its training objective.

def main(args): # Dispatch explicit training or independent test evaluation.
    torch.set_num_threads(args.threads) # Avoid uncontrolled CPU oversubscription during full-field integration.
    torch.manual_seed(args.seed) # Reproduce initialization and whole-history shuffling.
    directory = Path(args.output) # Persist results in a caller-chosen repository-backed path.
    directory.mkdir(parents=True, exist_ok=True) # Preserve checkpoints and evidence through interruptions.
    if args.command == 'evaluate': # Test is deliberately separate from checkpoint selection.
        checkpoint = torch.load(args.checkpoint, map_location=args.device, weights_only=False) # Load only a trusted locally produced checkpoint.
        manifest, cases = load_split(args.manifest, args.family, 'test', args.device) # Open held-out response arrays only in this explicit command.
        if checkpoint['contract']['manifest_sha256'] != sha256(args.manifest): # Prevent post-training reassignment of cases to easier test partitions.
            raise ValueError('Test manifest differs from training contract') # Require a single frozen experiment definition.
        model = FullFieldGNO(OperatorConfig(**checkpoint['config'])).to(args.device) # Reconstruct the exact full-field prediction function.
        model.load_state_dict(checkpoint['best_model']) # Evaluate the validation-selected checkpoint rather than selecting on test outcomes.
        result = evaluate(model, cases, checkpoint['normalization'], manifest, directory) # Export independent full-field error and predictions.
        write_json(directory / 'independent_test.json', result) # Preserve test outcomes including poor predictions.
        return # Do not perform updates or change the selected checkpoint during testing.
    manifest, training = load_split(args.manifest, args.family, 'train', args.device) # Validate native FEM evidence before opening training fields.
    _, validation = load_split(args.manifest, args.family, 'validation', args.device) # Keep complete independent development histories for model selection.
    normalization = fit_normalization(training, manifest) # Freeze input and output scales using training data only.
    config = OperatorConfig(args.family, training[0]['static_features'].shape[-1] + 3 + len(manifest['field_names']), training[0]['controls'].shape[-1], len(manifest['field_names']), len(manifest['relation_names']), args.width, args.depth, args.edge_chunk) # Include centered native geometry and every known initial response channel as causal physical inputs.
    model = FullFieldGNO(config).to(args.device) # Allocate a genuine matrix-kernel neural operator from scratch.
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1.e-5) # Use a recorded optimizer and no historical incompatible weight migration.
    contract = {'manifest_sha256': sha256(args.manifest), 'sources': {name: sha256(Path(__file__).with_name(name)) for name in ['gno.py', 'data.py', 'train.py', 'relations.py', 'acquisition.py']}, 'specification': model.specification(), 'seed': args.seed, 'epochs': args.epochs, 'window': args.window, 'learning_rate': args.learning_rate, 'train_ids': [case['id'] for case in training], 'validation_ids': [case['id'] for case in validation], 'normalization': normalization, 'torch_version': torch.__version__, 'test_fields_opened': False, 'selection_metric': 'mean_scale_normalized_L2'} # Freeze exact executable, data identities and requested work.
    histories, start, steps, best_score, best = [], 0, 0, float('inf'), None # Retain selection and execution state for exact interruption recovery.
    if args.resume: # Resume only an exactly matching training contract.
        saved = torch.load(args.resume, map_location=args.device, weights_only=False) # Restore a complete closed-epoch state, not only selected weights.
        if saved['contract'] != contract: # A changed graph, dataset, normalization or budget is a different experiment.
            raise ValueError('Resume contract mismatch') # Preserve the original evidence instead of silently continuing an altered run.
        model.load_state_dict(saved['model']) # Resume the last actual training iterate.
        optimizer.load_state_dict(saved['optimizer']) # Preserve momentum and variance estimates exactly.
        torch.set_rng_state(saved['rng'].cpu()) # Reproduce subsequent whole-history shuffling on CPU.
        if args.device.startswith('cuda'): # Restore device RNG states when executing on an accelerator.
            torch.cuda.set_rng_state_all(saved['cuda_rng']) # Avoid silently different stochastic continuation.
        histories, start, steps, best_score, best = saved['history'], saved['epoch'] + 1, saved['steps'], saved['best_score'], saved['best_model'] # Resume counters and validation-only selection.
    normalized = [normalize(case, normalization) for case in training] # Cache complete normalized inputs without copying or opening any test fields.
    write_json(directory / 'training_contract.json', contract) # Make the exact requested experiment inspectable before the first update.
    started = time.monotonic() # Record elapsed execution for each completed epoch.
    for epoch in range(start, args.epochs): # Run the full explicitly requested budget without an implicit two-epoch shortcut.
        loss, updates = train_epoch(model, optimizer, normalized, args.window) # Train on every complete history and every original spatial entity.
        steps += updates # Retain cumulative actual optimizer updates.
        validation_result = evaluate(model, validation, normalization, manifest) # Select using complete cold validation trajectories only.
        score = validation_result['mean_scale_normalized_L2'] # Keep the selection metric predeclared and separately interpretable.
        if score < best_score: # Save the best actual validation iterate without consulting test fields.
            best_score, best = score, copy.deepcopy(model.state_dict()) # Preserve the complete selected prediction function.
        histories.append({'epoch': epoch + 1, 'training_loss': loss, 'validation_error_ratio': score, 'optimizer_updates': steps, 'elapsed_this_attempt_seconds': time.monotonic() - started}) # Store true ratios and actual work with every epoch.
        payload = {'contract': contract, 'config': config.__dict__, 'normalization': normalization, 'model': model.state_dict(), 'best_model': best, 'best_score': best_score, 'optimizer': optimizer.state_dict(), 'rng': torch.get_rng_state(), 'cuda_rng': torch.cuda.get_rng_state_all() if args.device.startswith('cuda') else [], 'epoch': epoch, 'steps': steps, 'history': histories} # Include everything needed for exact continuation and held-out inference.
        save_checkpoint(directory / 'progress.pt', payload) # Commit only a complete trained and validated epoch.
        write_json(directory / 'history.json', histories) # Keep inspectable progress even if a later epoch is interrupted.
        with (directory / 'training_history.csv').open('w', newline='') as handle: # Export Origin/Gnuplot-ready numeric curves without a Python plot.
            writer = csv.DictWriter(handle, fieldnames=list(histories[0])) # Preserve stable explicit column labels.
            writer.writeheader() # Include units/ratio semantics in readable headers.
            writer.writerows(histories) # Reproduce the complete actual optimization trajectory.
        print(json.dumps(histories[-1]), flush=True) # Report real progress while the full requested training executes.
    write_json(directory / 'completion.json', {'status': 'TRAIN_VALIDATION_COMPLETE_TEST_NOT_RUN', 'epochs': args.epochs, 'optimizer_updates': steps, 'selected_validation_error_ratio': best_score, 'checkpoint_sha256': sha256(directory / 'progress.pt')}) # Training completion never implies an independent test or physical safety pass.

if __name__ == '__main__': # Keep dataset loading and optimization explicit when imported by tests.
    parser = argparse.ArgumentParser() # Expose a reproducible command rather than hidden notebook state.
    parser.add_argument('command', choices=['train', 'evaluate']) # Separate checkpoint fitting from independent test release.
    parser.add_argument('--manifest', required=True) # Require a frozen native-FEM manifest.
    parser.add_argument('--family', choices=['global', 'local'], required=True) # Keep whole-bridge and saddle operators separate.
    parser.add_argument('--output', required=True) # Persist every result in a visible chosen directory.
    parser.add_argument('--checkpoint') # Test evaluation requires an actual selected trained checkpoint.
    parser.add_argument('--resume') # Resume a complete exact closed-epoch payload when present.
    parser.add_argument('--epochs', type=int, default=500) # Provide a sustained configurable budget without claiming convergence from epoch count.
    parser.add_argument('--width', type=int, default=24) # Set latent channel capacity independently of mesh resolution.
    parser.add_argument('--depth', type=int, default=3) # Set the number of composed integral layers.
    parser.add_argument('--edge-chunk', type=int, default=4096) # Bound temporary matrix-kernel allocation without sampling edges.
    parser.add_argument('--window', type=int, default=8) # Declare the temporal gradient truncation while retaining the complete causal rollout.
    parser.add_argument('--learning-rate', type=float, default=1.e-3) # Record the actual AdamW step size.
    parser.add_argument('--seed', type=int, default=17) # Reproduce initialization and complete-history order.
    parser.add_argument('--threads', type=int, default=2) # Avoid contention with native FEM solvers.
    parser.add_argument('--device', default='cpu') # Permit a documented CPU or accelerator execution target.
    arguments = parser.parse_args() # Parse the exact requested scientific run once.
    if arguments.epochs < 1 or arguments.window < 1 or arguments.edge_chunk < 1: # Prevent zero-work completion claims or invalid memory chunking.
        parser.error('epochs, window and edge-chunk must be positive') # Reject a malformed execution budget explicitly.
    if arguments.command == 'evaluate' and not arguments.checkpoint: # Independent inference requires actual weights.
        parser.error('--checkpoint is required for evaluate') # Do not evaluate a randomly initialized operator as a trained result.
    main(arguments) # Execute only after command-line and scientific evidence gates pass.
