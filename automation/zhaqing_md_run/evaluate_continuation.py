import json  # Publish complete fixed-denominator comparisons and robustness tests.
from pathlib import Path  # Resolve actual saved weights and true FEM response fields.
import numpy as np  # Summarize independent per-case errors without changing denominators.
import torch  # Reuse the verified differentiable physical residual and saved graph inference.
import graph_surrogate as g  # Evaluate the exact trained architecture and original mechanics.
ROOT = Path(__file__).resolve().parents[2]  # Locate this existing bridge repository.
OUT = ROOT / 'build/zhaqing-md-20261024/continuation'  # Preserve the continuation namespace.
def grouped(rows):  # Aggregate case metrics by their original immutable role.
    return {s: {'count': sum(r['split'] == s for r in rows), 'mean_relative_l2': float(np.mean([r['relative_l2'] for r in rows if r['split'] == s])), 'mean_rmse_mm': float(np.mean([r['rmse_mm'] for r in rows if r['split'] == s])), 'max_physical_residual_N': max(r['max_free_suspension_residual_N'] for r in rows if r['split'] == s)} for s in sorted({r['split'] for r in rows})}  # Expose actual dimensional errors and supported residuals separately.
def evaluate_fields(payload, manifest):  # Compare saved full fields to independently audited native truth.
    graph = g.BridgeGraph(manifest)  # Reconstruct the original source-node graph and fixed-L0 physics.
    source_rows = {r['case_id']: r for r in manifest['samples']}  # Resolve each prediction to its frozen scientific case.
    rows = []  # Keep individual errors visible for small or difficult reference responses.
    for item in payload.get('candidates', payload.get('cases', [])):  # Support ordinary held-out and candidate inference payloads.
        sample = source_rows[item['case_id']]  # Refuse ungrounded predictions with no real reference.
        assert g.digest(sample['canonical_dat']) == sample['canonical_dat_sha256']  # Verify true field identity at the time of testing.
        displacement = graph.pipeline.parse_dat_nodes(Path(sample['canonical_dat']))[0]  # Parse the actual native-compatible response without re-solving.
        truth = torch.tensor([[displacement[n] for n in graph.node_ids]], dtype=torch.float64)  # Preserve all reference digits and source mapping.
        predicted = torch.tensor([item['mean_displacement']], dtype=torch.float64)  # Read actual saved neural field values.
        uncertainty = torch.tensor([item.get('ensemble_std', np.zeros_like(item['mean_displacement']).tolist())], dtype=torch.float64)  # Preserve ensemble spread without labeling it a calibrated interval.
        rows.append({'case_id': item['case_id'], 'split': sample['split'], 'factors': sample['factors'], **g.metrics_for(predicted, truth, uncertainty, graph)[0]})  # Compute all metrics with the same independent implementation.
    return {'splits': grouped(rows), 'cases': rows, 're_equilibrated': False}  # Keep raw-network assessment distinct from corrective finite-element solving.
def main():  # Select by validation alone, then run common-holdout and independent-boundary assessment.
    torch.set_num_threads(2)  # Bound numerical assessment resource use.
    summary = g.read_json(OUT / 'continuation-summary.json')  # Require both requested active rounds to have actually completed.
    initial = Path(summary['selected_architecture']['model_directory'])  # Include the chosen configuration before added FEM feedback.
    options = [initial] + [Path(r['model_directory']) for r in summary['active_rounds']]  # Compare only already trained real generations.
    chosen = min(options, key=lambda p: g.read_json(p / 'metrics.json')['splits']['validation']['mean_relative_l2'])  # Freeze the output checkpoint using development accuracy alone.
    selection = {'model_directory': str(chosen), 'criterion': 'lowest_validation_mean_relative_l2', 'test_used': False, 'candidates': [{'path': str(p), 'validation_mean_relative_l2': g.read_json(p / 'metrics.json')['splits']['validation']['mean_relative_l2']} for p in options]}  # Record the decision before inspecting final test errors.
    g.write_json(OUT / 'final-checkpoint-selection.json', selection)  # Persist the selected publication checkpoint independently from the latest round.
    manifest = g.read_json(summary['final_dataset'])  # Read the complete true-label population with frozen held-out membership.
    previous = evaluate_fields(g.read_json(OUT / 'previous-model-full-holdout/predictions.json'), manifest)  # Reevaluate the prior-turn model on the restored full four-case test set.
    g.write_json(OUT / 'previous-full-holdout-metrics.json', previous)  # Preserve the fair baseline comparison rather than reuse its earlier two-case denominator.
    boundary = g.read_json(OUT / 'boundary-final/accepted.json')  # Require independently audited robustness references.
    assert len(boundary['samples']) == 4 and not boundary['excluded_samples']  # Demand all precommitted boundary tests before reporting coverage.
    candidates = {'candidates': [{'case_id': r['case_id'], 'factors': r['factors']} for r in boundary['samples']]}  # Pass boundary inputs alone to the frozen predictor.
    g.write_json(OUT / 'boundary-candidates.json', candidates)  # Preserve the inference request separately from FEM truth.
    g.predict_existing(chosen, OUT / 'boundary-candidates.json', OUT / 'boundary-predictions')  # Evaluate actual saved graph weights without optimization or correction.
    robustness = evaluate_fields(g.read_json(OUT / 'boundary-predictions/predictions.json'), boundary)  # Compare predicted full fields to independent boundary FEM solutions.
    g.write_json(OUT / 'boundary-metrics.json', robustness)  # Report every corner and edge case separately.
    g.predict_existing(chosen, OUT / 'holdout-candidates.json', OUT / 'checkpoint-reload')  # Recompute the same held-out predictions from independently loaded saved weights.
    loaded = {r['case_id']: r for r in g.read_json(OUT / 'checkpoint-reload/predictions.json')['candidates']}  # Preserve reloaded source-node responses.
    original = {r['case_id']: r for r in g.read_json(chosen / 'predictions.json')['cases']}  # Read the actual fields used for the reported training-generation metrics.
    maximum_difference = max(float(np.max(np.abs(np.asarray(r['mean_displacement']) - np.asarray(original[k]['mean_displacement'])))) for k, r in loaded.items())  # Allow only ordinary float32 batch-order roundoff.
    assert maximum_difference < 1e-4  # Reject a checkpoint whose saved inference materially differs from its reported predictions.
    initial_holdouts = {r['case_id']: r for r in g.read_json(OUT / 'accepted-round2.json')['samples'] if r['split'] in ('validation', 'test')}  # Freeze all eight restored original held-out labels.
    for row in manifest['samples']:  # Verify final training expansion did not relabel or replace a holdout.
        if row['case_id'] in initial_holdouts:  # Check only the originally frozen evaluation population.
            assert all(row[k] == initial_holdouts[row['case_id']][k] for k in ('split', 'factors', 'canonical_dat_sha256', 'summary_sha256'))  # Demand exact identity and partition preservation.
    g.write_json(OUT / 'checkpoint-verification.json', {'status': 'PASS', 'holdout_count': len(loaded), 'maximum_reload_field_difference_mm': maximum_difference, 'tolerance_mm': 1e-4, 'all_eight_holdouts_unchanged': True})  # Persist meaningful inference and data-leakage safeguards.
    selected_metrics = g.read_json(chosen / 'metrics.json')  # Read final common-holdout results only after selection is frozen.
    contract = g.read_json(chosen / 'model_contract.json')  # Determine the actual selected architecture and its physical scope.
    ablation = None  # Keep baseline-only comparisons absent for the unchanged no-lift architecture.
    if contract.get('lifting_order'):  # Explicitly measure how much accuracy comes from the training-only polynomial lift.
        lift = g.read_json(chosen / 'lifting.json')  # Read the saved training-only spatial coefficients.
        coefficients = torch.tensor(lift['coefficients'], dtype=torch.float64)  # Preserve fitted coefficient precision.
        rows = [r for r in manifest['samples'] if r['split'] in ('validation', 'test')]  # Use the exact same held-out truth for the ablation comparison.
        factors = torch.tensor([r['factors'] for r in rows], dtype=torch.float64)  # Preserve exact declared load coordinates.
        fields = torch.einsum('bk,knc->bnc', g.lifting_features(factors, contract['lifting_order']), coefficients)  # Evaluate the polynomial baseline with graph residual disabled.
        ablation = evaluate_fields({'cases': [{'case_id': r['case_id'], 'mean_displacement': fields[i].tolist()} for i, r in enumerate(rows)]}, manifest)  # Do not attribute baseline accuracy to learned messages.
        g.write_json(OUT / 'lift-only-ablation.json', ablation)  # Save the essential architecture attribution check.
    report = {'status': 'COMPLETED_ENGINEERING_HOLD', 'repair_count': 3, 'repair_tolerances_relaxed': False, 'final_reference_counts': manifest['expected_split_counts'], 'selected_model': selection, 'previous_common_holdout': previous, 'selected_model_metrics': selected_metrics, 'boundary_robustness': robustness, 'lift_only_ablation': ablation, 'active_search_candidates': sum(r['candidate_count'] for r in summary['active_rounds']), 'new_active_fem_cases': sum(r['new_native_cases'] for r in summary['active_rounds']), 'physics_complete': False, 'prediction_intervals_calibrated': False, 'cross_bridge_validated': False}  # Report complete actual scope without engineering acceptance claims.
    g.write_json(OUT / 'final-evaluation.json', report)  # Freeze the full user-facing evidence base.
    print(json.dumps({'selected': str(chosen), 'previous': previous['splits'], 'current': selected_metrics['splits'], 'boundary': robustness['splits']}, ensure_ascii=False), flush=True)  # Expose concise completed findings.
if __name__ == '__main__':  # Keep imports free of expensive evaluation work.
    main()  # Execute only after all dependent native and neural stages finish.
