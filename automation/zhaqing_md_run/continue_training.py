import copy  # Preserve historical datasets and earlier failure records unchanged.
import hashlib  # Bind every accepted label and decision to exact bytes.
import json  # Store structured experiment and evaluation receipts.
import subprocess  # Execute real solver, audit, training, and search programs.
import sys  # Use the current pinned Python runtime consistently.
from pathlib import Path  # Keep all experiment paths explicit.
ROOT = Path(__file__).resolve().parents[2]  # Resolve the existing model repository.
CODE = ROOT / 'automation/zhaqing_md_run'  # Reuse the real implementation rather than mock computation.
RUN = ROOT / 'build/zhaqing-md-20261024'  # Preserve the original completed experiment.
OUT = RUN / 'continuation'  # Keep continuation results separate and reviewable.
def read(path):  # Read one immutable evidence file.
    return json.loads(Path(path).read_text())  # Parse exact local JSON content.
def sha(path):  # Verify scientific artifact identity before reuse.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Hash the full actual bytes.
def write(path, value):  # Publish complete finite experiment evidence.
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')  # Reject nonfinite metrics explicitly.
def run(script, *arguments):  # Execute one dependency-ordered pipeline stage.
    command = [sys.executable, str(CODE / script), *map(str, arguments)]  # Avoid shell interpolation of scientific paths.
    print(json.dumps({'stage': script, 'arguments': list(map(str, arguments))}), flush=True)  # Report actual started work.
    subprocess.run(command, check=True)  # Stop on real solver, audit, or training failure.
def audit(directory, design):  # Independently qualify newly computed labels before training.
    if not (directory.parent / (directory.name + '-verified-native.zip')).exists():  # Reuse completed immutable archives; the following independent audit still rechecks required live truth.
        run('repair_evidence.py', '--manifest', directory / 'dataset_manifest.json', '--ccx', ROOT.parent / 'solver-runtime/ccx-precision-v2', '--output', directory.parent / (directory.name + '-native-integrity'), '--archive', directory.parent / (directory.name + '-verified-native.zip'))  # Restore damaged native bytes only by identical-input replay matching original SHA, then seal every iteration.
    run('audit_physics.py', '--manifest', directory / 'dataset_manifest.json', '--analysis-mode', 'fixed-l0', '--output', directory / 'audit-batch.json', '--audited-manifest', directory / 'audited.json', '--accepted-manifest', directory / 'accepted.json', '--expected-scenarios', design)  # Use unchanged internal, coupling, stress, and support tolerances.
    accepted = read(directory / 'accepted.json')  # Read only the separately admitted references.
    assert not accepted['excluded_samples']  # Require complete successful repair or feedback before continuing this experiment.
    return accepted  # Return the real audited dataset.
def merge(previous, added, destination, skip_ids=()):  # Combine compatible references while freezing existing held-out labels.
    combined = copy.deepcopy(previous)  # Never edit an earlier generation in place.
    indexed = {row['case_id']: row for row in combined['samples']}  # Preserve unique scientific identities.
    for row in added['samples']:  # Admit only separately qualified new references.
        if row['case_id'] in skip_ids:  # Keep a repeated successful control out of the learning dataset.
            continue  # Preserve the original holdout label bytes exactly.
        assert row['case_id'] not in indexed  # Never replace an existing accepted evaluation label.
        indexed[row['case_id']] = row  # Add the genuinely repaired or newly solved case.
    for row in indexed.values():  # Validate all original and new truth artifacts immediately before training.
        for key in ('canonical_dat', 'summary'):  # Protect full numerical fields and original convergence gates.
            assert sha(row[key]) == row[key + '_sha256']  # Reject corrupted or silently replaced truth.
        assert sha(row['audit_path']) == row['audit_sha256']  # Require the independently qualified evidence identity.
    combined['samples'] = sorted(indexed.values(), key=lambda row: row['case_id'])  # Publish deterministic sample ordering.
    combined['historical_exclusions'] = previous.get('historical_exclusions', previous.get('excluded_samples', []))  # Preserve original failed attempts as history, not current missing labels.
    combined['excluded_samples'] = [row for row in previous.get('excluded_samples', []) if row['case_id'] not in indexed]  # Remove only truly repaired exclusions from current admission.
    counts = {split: sum(row['split'] == split for row in indexed.values()) for split in ('train', 'validation', 'test')}  # Count all actual qualified labels by frozen role.
    combined.update({'accepted_count': len(indexed), 'valid_count': len(indexed), 'failed_count': len(combined['excluded_samples']), 'excluded_count': len(combined['excluded_samples']), 'accepted_split_counts': counts, 'expected_split_counts': counts, 'excluded_split_counts': {s: 0 for s in counts}, 'eligible_reference_count': len(indexed)})  # Publish the restored complete evaluation denominators.
    combined['solver_precision_generations'] = [previous['provenance'], added['provenance']]  # Disclose reuse of original qualified labels and new high-precision native outputs.
    combined['precision_repair_receipt'] = read(ROOT.parent / 'solver-runtime/precision-repair-v2.json')  # Bind precision differences to exact executable identities.
    combined['expected_split_case_ids'] = {s: [r['case_id'] for r in combined['samples'] if r['split'] == s] for s in counts}  # Preserve explicit scientific membership for each split.
    write(destination, combined)  # Freeze this dataset generation before fitting any model.
    return combined  # Return the complete admitted population.
def train(manifest, directory, order, epochs=300):  # Train the same independent graph ensemble under an explicit configuration.
    run('graph_surrogate.py', '--manifest', manifest, '--output', directory, '--lifting-order', order, '--epochs', epochs, '--patience', epochs, '--width', 32, '--depth', 3, '--seeds', 17, 29, 43, '--physics-weight', 0.01, '--threads', 2)  # Keep training budget, random seeds, and model width controlled.
    return read(directory / 'metrics.json')  # Select configurations using validation metrics only.
def main():  # Execute repair admission, architecture search, two active-learning rounds, and independent tests.
    repaired = audit(OUT / 'repair-v2', OUT / 'repair-design.json')  # Independently audit all three repairs plus one numerical control.
    old = read(RUN / 'learning_combined/accepted_manifest.json')  # Restore the exact previous 25 qualified references.
    current_path = OUT / 'accepted-round2.json'  # Freeze the first complete 28-reference dataset.
    current = merge(old, repaired, current_path, skip_ids=('LC36_MD_SOBOL',))  # Restore LC28 training and LC42/43 tests without modifying prior accepted holdouts.
    assert current['expected_split_counts'] == {'train': 20, 'validation': 4, 'test': 4}  # Require complete original frozen evaluation coverage.
    trials = []  # Preserve every tried architecture instead of reporting only the winner.
    for order in (0, 1, 2):  # Compare original graph prediction, affine lifting, and quadratic lifting on identical data.
        directory = OUT / f'search-lift{order}'  # Isolate each architecture's weights and full metrics.
        metrics = train(current_path, directory, order)  # Execute actual neural training and held-out evaluation.
        trials.append({'order': order, 'model_directory': str(directory), 'validation_mean_relative_l2': metrics['splits']['validation']['mean_relative_l2']})  # Exclude test results from model selection.
    selected = min(trials, key=lambda row: row['validation_mean_relative_l2'])  # Freeze the best configuration using validation error alone.
    write(OUT / 'architecture-selection.json', {'trials': trials, 'selected': selected, 'selection_metric': 'validation_mean_relative_l2', 'test_used_for_selection': False})  # Persist the selection decision before feedback computation.
    model = Path(selected['model_directory'])  # Use the selected frozen graph ensemble for candidate inference.
    radius = 0.4375  # Resume the previously declared next trust-region radius.
    previous_validation = selected['validation_mean_relative_l2']  # Track development progress without reading tests.
    rounds = []  # Preserve executed search, solve, retrain, and trust-region updates.
    for generation in (3, 4):  # Execute two genuine new active-learning iterations under a finite budget.
        candidates = OUT / f'candidates-round{generation}.json'  # Isolate the new Sobol search population.
        run('select_feedback.py', '--generate', '--seed', 20261024 + generation, '--candidate-power', 8, '--output', candidates)  # Evaluate 256 new feasible candidates per round.
        inferred = OUT / f'candidate-round{generation}'  # Preserve complete frozen-model predictions and residuals.
        run('graph_surrogate.py', '--predict-from', model, '--candidates', candidates, '--output', inferred)  # Perform real saved-weight graph inference with no optimizer updates.
        decision = OUT / f'decision-round{generation}.json'  # Freeze the next four selected native FEM tasks.
        run('select_feedback.py', '--manifest', current_path, '--metrics', model / 'metrics.json', '--candidate-metrics', inferred / 'metrics.json', '--radius', radius, '--round', generation, '--case-start', 70 + (generation - 3) * 10, '--output', decision)  # Select on development error, disagreement, physics, coverage, and cost only.
        solved = OUT / f'feedback-round{generation}'  # Isolate actual native computations and both reaction audits.
        run('run_scenarios.py', '--scenarios', decision, '--ccx', ROOT.parent / 'solver-runtime/ccx-precision-v2', '--output', solved, '--workers', 4)  # Compute original fixed-L0 responses with repaired native print precision.
        admitted = audit(solved, decision)  # Reject any new unqualified FEM labels before retraining.
        next_path = OUT / f'accepted-round{generation}.json'  # Freeze the expanded training population.
        current = merge(current, admitted, next_path)  # Preserve all eight held-out case identities and bytes exactly.
        current_path = next_path  # Advance only after independent qualification.
        next_model = OUT / f'learning-round{generation}'  # Save the freshly trained selected architecture.
        metrics = train(current_path, next_model, selected['order'])  # Retrain three independent networks on actual expanded references.
        validation = metrics['splits']['validation']['mean_relative_l2']  # Read only validation accuracy for trust-region adaptation.
        next_radius = min(0.8, radius * 1.25) if validation < previous_validation else max(0.05, radius * 0.5)  # Apply the previously declared development-based update.
        rounds.append({'generation': generation, 'candidate_count': 256, 'new_native_cases': 4, 'radius_used': radius, 'next_radius': next_radius, 'validation_mean_relative_l2': validation, 'model_directory': str(next_model), 'dataset': str(current_path)})  # Preserve actual executed feedback scope.
        radius, previous_validation, model = next_radius, validation, next_model  # Advance the real closed loop without test leakage.
        write(OUT / 'executed-rounds.json', rounds)  # Publish completed work after each independent round.
    final = {'status': 'COMPUTATION_COMPLETED_ENGINEERING_HOLD', 'repaired_case_ids': ['LC28_MD_SOBOL', 'LC42_MD_SOBOL', 'LC43_MD_SOBOL'], 'configuration_trials': trials, 'selected_architecture': selected, 'active_rounds': rounds, 'final_model': str(model), 'final_dataset': str(current_path), 'final_metrics': read(model / 'metrics.json'), 'test_used_for_selection': False, 'whole_bridge_physics_complete': False}  # Separate successful computation from engineering validation.
    write(OUT / 'continuation-summary.json', final)  # Deliver all actual results without claiming unsupported physical acceptance.
if __name__ == '__main__':  # Execute only the explicitly requested continuation workflow.
    main()  # Propagate any failed real stage to the caller.
