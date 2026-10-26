"""Candidate scoring and genuine FEM-discrepancy hard-sample registration.""" # Failed FEM convergence is not a neural prediction error label.
import numpy as np # Compare numeric fields without generating any figures.

def shortlist(ensemble, output_scales, parameters, observed_parameters, limit): # Rank unsolved candidates using uncertainty and parameter-space coverage.
    prediction = np.asarray(ensemble, dtype=float) # Use independently trained model emissions on the same native candidate fields.
    if prediction.ndim < 4 or prediction.shape[0] < 2 or not np.isfinite(prediction).all(): # A single network or invalid field cannot supply meaningful ensemble disagreement.
        raise ValueError('Need at least two independent models and candidate/native/output axes') # Do not disguise one model's magnitude as epistemic uncertainty.
    scales = np.asarray(output_scales, dtype=float) # Reuse training-derived physical output scales.
    if scales.ndim != 1 or not np.isfinite(scales).all() or np.any(scales <= 0) or prediction.shape[-1] != len(scales): # Keep dimensional channels comparable without test-derived tuning.
        raise ValueError('Invalid fixed output scales') # Reject ambiguous field units.
    disagreement = np.sqrt(np.mean((prediction.std(axis=0) / scales).reshape(prediction.shape[1], -1) ** 2, axis=1)) # Compute normalized whole-native-field ensemble disagreement per candidate.
    coordinates = np.asarray(parameters, dtype=float) # Require caller-normalized bounded physical parameter coordinates.
    known = np.asarray(observed_parameters, dtype=float) # Use only already observed training parameter locations.
    if coordinates.ndim != 2 or known.ndim != 2 or coordinates.shape[1] != known.shape[1] or len(coordinates) != len(disagreement) or len(known) == 0 or not np.isfinite(coordinates).all() or not np.isfinite(known).all() or int(limit) < 1: # Validate candidate/training parameter-space alignment and numerical validity.
        raise ValueError('Invalid candidate or observed parameter coordinates') # Prevent accidental mismatch between model and parameter scores.
    novelty = np.linalg.norm(coordinates[:, None] - known[None], axis=-1).min(axis=1) # Favor physical regions not already covered by training solves.
    remaining, chosen = set(range(len(coordinates))), [] # Greedily avoid selecting only near-duplicate candidates.
    for _ in range(min(int(limit), len(coordinates))): # Respect the actual finite-element supplementation budget.
        choice = max(remaining, key=lambda i: (disagreement[i] * (1 + novelty[i]), novelty[i], -i)) # Use a declared uncertainty-times-coverage score, with coverage breaking zero-uncertainty ties.
        chosen.append({'candidate_index': choice, 'uncertainty_score': float(disagreement[choice]), 'novelty': float(novelty[choice]), 'selection_score': float(disagreement[choice] * (1 + novelty[choice])), 'true_FEM_error_known': False}) # Clearly separate acquisition heuristic from actual neural/FEM error.
        remaining.remove(choice) # Spend at most one solve on each selected parameter realization.
        novelty = np.minimum(novelty, np.linalg.norm(coordinates - coordinates[choice], axis=1)) # Discount candidates duplicated by the current batch selections.
    return chosen # These are requests for FEM calculations, not already validated error negatives.

def reconcile_reference(row, prediction, reference, measure, mask, scales, threshold, times): # Register hard examples only after an actual candidate FEM solve succeeds.
    if row.get('split') != 'candidate': # Held-out test cases cannot enter an active learning update.
        raise ValueError('Acquisition may not relabel training/validation/test histories') # Preserve the frozen independent evaluation boundary.
    if row.get('quality') != 'VALID_CONVERGED' or not row.get('convergence_verified'): # Nonconverged FEM outputs cannot define neural error.
        return {'id': row['id'], 'status': 'FEM_FAILURE_REQUIRES_SOLVER_REPAIR', 'use_as_training_label': False, 'is_error_negative': False} # Keep numerical failure evidence outside the supervised label pool.
    prediction, reference = np.asarray(prediction), np.asarray(reference) # Compare complete fields from the same original native mesh and history.
    if prediction.shape != reference.shape or prediction.ndim != 3: # Require time-by-entity-by-field alignment before computing discrepancies.
        raise ValueError('Prediction and native FEM history are not aligned') # Avoid meaningless errors from interpolated or incomplete fields.
    space, observed, fixed_scales = np.asarray(measure), np.asarray(mask), np.asarray(scales) # Validate each physical integration and field observation input independently.
    if len(reference) < 2 or space.shape != (reference.shape[1],) or observed.shape != reference.shape[1:] or fixed_scales.shape != (reference.shape[2],): # Require complete physical-space and output-channel alignment.
        raise ValueError('Invalid full-field comparison shapes') # Prevent accidental broadcasting from silently changing the measured domain.
    if not all(np.isfinite(value).all() for value in (prediction, reference, space, observed, fixed_scales)) or not np.isfinite(threshold): # A NaN mismatch cannot become a supposedly valid training label.
        raise ValueError('Nonfinite prediction, reference, measure or threshold') # Preserve invalid numerical evidence as an explicit failure.
    if np.any(space <= 0) or np.any(fixed_scales <= 0) or threshold < 0 or not np.isin(observed, [0, 1]).all() or np.any(observed.sum(0) == 0): # Every declared physical field needs positive integration support and valid scales.
        raise ValueError('Invalid physical comparison measures, masks or threshold') # Missing channels must not score as perfectly predicted.
    durations = np.diff(np.asarray(times)) # Weight the complete error trajectory by physical elapsed time.
    if durations.shape != (len(reference) - 1,) or not np.isfinite(durations).all() or np.any(durations <= 0): # Validate native time alignment before comparing response histories.
        raise ValueError('Invalid native time axis') # Do not silently treat adaptive time steps as equal duration.
    weights = np.asarray(measure)[None, :, None] * np.asarray(mask)[None] * durations[:, None, None] # Preserve physical space-time quadrature and field masks.
    error = np.sqrt(((prediction[1:] - reference[1:]) ** 2 * weights).sum(axis=(0, 1))) # Exclude the supplied initial state from prediction-error scoring.
    floor = np.asarray(scales) * np.sqrt(weights.sum(axis=(0, 1))) # Reuse fixed training scales over the actual physical duration.
    denominator = np.maximum(np.sqrt(((reference[1:] - reference[0]) ** 2 * weights).sum(axis=(0, 1))), floor) # Match training/validation's transient-change metric so permanent response cannot hide a failed dynamic prediction.
    score = float(np.mean(error / np.maximum(denominator, 1.e-12))) # Use a frozen explicit aggregation instead of a subjective visual label.
    return {'id': row['id'], 'status': 'FEM_COMPARED', 'field_error_ratio': score, 'threshold_ratio': float(threshold), 'is_error_negative': score > threshold, 'use_as_training_label': True, 'promotion_requires_new_frozen_manifest': True} # A negative example means a verified large neural/FEM discrepancy, not a fabricated failed solve.
