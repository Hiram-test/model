#!/usr/bin/env python3  # Execute durable full-field generation, qualification, training and independent testing.
import argparse, hashlib, json, os, signal, subprocess, sys, time, zipfile  # Preserve actual subprocess outcomes and immutable numerical identities.
from pathlib import Path  # Resolve every job path against the checked-out repository.
ROOT = Path(__file__).resolve().parents[3]  # Locate the model repository independently of the hosted runner prefix.
HERE = Path(__file__).resolve().parent  # Keep the frozen experiment definition beside its executable orchestration.
SOURCE = ROOT / 'automation/zhaqing_global_local'  # Use only the new detailed bridge and explicit-wire implementation.
OUT = ROOT / 'results/full_training_20261026'  # Preserve each stage in a stable repository-relative artifact namespace.
BASE = ROOT / 'results/zhaqing_global_local_20261026/evidence/baseline'  # Restore the authenticated original input and F3 state here.
def digest(path):  # Hash complete artifacts with bounded memory.
    value = hashlib.sha256()  # Allocate one independent content identity.
    with Path(path).open('rb') as stream:  # Read actual bytes without executing serialized objects.
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''): value.update(chunk)  # Include every file byte in order.
    return value.hexdigest()  # Return the complete SHA256 identity.
def write(path, value):  # Publish a complete status atomically.
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the selected case directory exists.
    pending = path.with_name(path.name + '.pending')  # Distinguish incomplete filesystem writes from accepted evidence.
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')  # Reject nonfinite metrics before publication.
    pending.replace(path)  # Expose one complete machine-readable record.
def config():  # Validate the frozen scenario population before any expensive job.
    value = json.loads((HERE / 'experiment.json').read_text())  # Read the single published training budget and partition contract.
    cases = value['cases']  # Keep complete loading realizations as the partition unit.
    if len({case['id'] for case in cases}) != len(cases): raise ValueError('Duplicate complete-history ID')  # Prevent accidentally reusing one realization across partitions.
    if [sum(case['split'] == split for case in cases) for split in ('train', 'validation', 'test')] != [6, 2, 2]: raise ValueError('Expected frozen 6/2/2 history partition')  # Freeze every independent test case before training.
    if value['epochs'] != 300 or value['steps'] * value['dt_s'] != 20.0: raise ValueError('Changed complete training or physical-duration budget')  # Refuse silent short-run substitution.
    return value  # Return a fully checked complete campaign contract.
def restore_inputs():  # Recover only the known original global input asset into this checkout.
    archive = SOURCE / 'assets/global_baseline_inputs.zip'  # Select the already committed compact baseline bundle.
    if digest(archive) != config()['baseline_asset_sha256']: raise ValueError('Baseline archive identity changed')  # Refuse a different source model under the same experiment name.
    with zipfile.ZipFile(archive) as bundle:  # Open the authenticated archive without shell expansion.
        for item in bundle.infolist():  # Validate every archive path before extracting any file.
            destination = (ROOT / item.filename).resolve()  # Determine the actual extraction target.
            if not destination.is_relative_to(BASE): raise ValueError('Unexpected baseline archive destination')  # Limit extraction to the explicit original-input subtree.
            destination.parent.mkdir(parents=True, exist_ok=True); payload = bundle.read(item)  # Read the exact archived source bytes.
            if destination.exists() and destination.read_bytes() != payload: raise ValueError('Existing baseline differs from archived source')  # Protect manually altered or mismatched model evidence.
            destination.write_bytes(payload)  # Restore the original input with byte-for-byte identity.
def invoke(command, folder, log_name, seconds):  # Run a bounded actual subprocess while preserving interruption evidence.
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)  # Prepare the exact stage-local log namespace.
    started = time.time(); environment = os.environ.copy()  # Record real elapsed time and inherit the selected runtime.
    environment.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', MPIR_CVAR_CH3_NETWORK_IFACE='lo', MPICH_INTERFACE_HOSTNAME='127.0.0.1', PYTHONUNBUFFERED='1')  # Bound worker resources and use an available MPI interface.
    record = {'command': [str(x) for x in command], 'working_directory': str(ROOT), 'started_unix_s': started, 'timeout_s': seconds, 'experiment_sha256': digest(HERE / 'experiment.json'), 'status': 'RUNNING'}  # Persist the real launch command before starting numerical work.
    receipt = folder / (log_name + '.execution.json'); write(receipt, record)  # Make launch and resource budget externally inspectable.
    with (folder / log_name).open('w') as log:  # Keep complete stdout and stderr without flooding a compact status view.
        process = subprocess.Popen([str(x) for x in command], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)  # Start exactly the requested native or training command.
        try: code = process.wait(timeout=seconds)  # Enforce the documented finite stage budget.
        except subprocess.TimeoutExpired:  # Preserve checkpointed work before the hosted runner's hard timeout.
            os.killpg(process.pid, signal.SIGTERM)  # Ask the complete subprocess group to terminate cleanly.
            try: process.wait(timeout=15)  # Give the native process a short opportunity to close its output.
            except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait()  # Stop an unresponsive native solve before losing artifact-upload time.
            code = 124  # Distinguish a stage wall-time limit from numerical nonconvergence.
    record.update(exit_code=code, elapsed_seconds=time.time() - started, status='COMPLETED' if code == 0 else ('TIME_BUDGET_EXHAUSTED' if code == 124 else 'FAILED'))  # Report only the actual observed execution outcome.
    write(receipt, record); print(json.dumps(record), flush=True)  # Publish real completion evidence and one concise job-log message.
    return code  # Let the physical or training gate decide whether this outcome is admissible.
def global_case(case_id):  # Generate one independent full-order detailed bridge loading history.
    setup = config(); restore_inputs()  # Freeze the experiment and recover authenticated original source files.
    case = next(row for row in setup['cases'] if row['id'] == case_id)  # Select one previously declared complete realization.
    folder = OUT / 'global' / case_id  # Isolate native input, output, failure, and state evidence for this realization.
    command = [sys.executable, SOURCE / 'global/transient_cases.py', '--source', BASE / 'LC01_G_DEAD.inp', '--state', BASE / 'equilibrium_state.json', '--output', folder, '--detailed-model', '--subdivision', '1', '--case-id', case_id, '--split', case['split'], '--steps', str(setup['steps']), '--dt', str(setup['dt_s']), '--speed', str(case['speed_m_s']), '--seed', str(case['seed']), '--storage', 'hdf5']  # Retain every detailed-model node and every declared physical time step.
    code = invoke(command, folder, 'campaign_native.log', setup['native_job_seconds'])  # Run the actual nonlinear permanent equilibrium and full wind history.
    manifest = folder / 'case_manifest.json'  # Require the native exporter to publish its completed-history receipt.
    if code != 0 or not manifest.exists(): raise RuntimeError(f'Global case {case_id} did not complete; native exit {code}')  # Reject failed, interrupted and missing histories before adaptation.
    receipt = json.loads(manifest.read_text())  # Inspect actual numerical completion rather than process exit alone.
    if receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('time_steps') != setup['steps'] or receipt.get('node_count', 0) < 30000: raise ValueError('Native completion, physical duration, or detailed mesh gate failed')  # Prevent old equivalent-deck or shortened runs entering the new dataset.
def relocate_receipt(path):  # Preserve numerical bytes while relocating job-local evidence paths.
    path = Path(path); original = json.loads(path.read_text()); updated = dict(original)  # Keep the producer's original receipt unmodified.
    for key in ('dataset', 'step_audits_file', 'saddle_motion_file', 'stream_status_file'):  # Relocate only recognized producer-owned case-local files.
        if key not in original: continue  # Preserve compatibility with explicitly declared exporter versions.
        candidate = path.parent / Path(original[key]).name  # Artifact extraction preserves each native case's internal names.
        if not candidate.is_file(): raise FileNotFoundError(candidate)  # Never manufacture absent native evidence.
        hash_key = {'dataset': 'dataset_sha256', 'step_audits_file': 'step_audits_sha256', 'saddle_motion_file': 'saddle_motion_sha256'}.get(key)  # Retain the producer's exact numerical identities where declared.
        if hash_key and digest(candidate) != original[hash_key]: raise ValueError('Relocated numerical artifact hash mismatch')  # Reject corrupted or substituted results.
        updated[key] = str(candidate.resolve())  # Point the adapter at the same bytes in the receiving job.
    updated['original_receipt_sha256'] = digest(path)  # Preserve a verifiable link to the unchanged producer receipt.
    updated['relocation_policy'] = 'Paths only; original physical result and audit hashes unchanged'  # Disclose filesystem relocation separately from numerical computation.
    destination = path.with_name('case_manifest.relocated.json'); write(destination, updated)  # Publish the relocation as a distinct derived document.
    return destination  # Feed only explicitly rebased complete-history evidence to adaptation.
def assemble():  # Build one frozen learning dataset only after all declared histories pass.
    setup = config(); restore_inputs(); cases = []  # Reconstruct the immutable scenario contract and original input evidence.
    for case in setup['cases']:  # Include every declared train, validation and test realization exactly once.
        path = OUT / 'global' / case['id'] / 'case_manifest.json'  # Locate the actual matrix-job artifact after deterministic extraction.
        receipt = json.loads(path.read_text())  # A missing case fails the whole experiment rather than shrinking the data population.
        if receipt.get('case_id') != case['id'] or receipt.get('split') != case['split'] or receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('time_steps') != setup['steps'] or receipt.get('node_count', 0) < 30000: raise ValueError('Complete frozen population qualification failed')  # Enforce identity, partition, completeness and detailed spatial scope.
        cases.append(relocate_receipt(path))  # Bind the same actual numerical bytes at this receiving runner location.
    destination = OUT / 'dataset'  # Keep all adapted contracts beside the original case results within one portable artifact tree.
    command = [sys.executable, SOURCE / 'operator/adapt_global.py', '--case-manifests', *cases, '--source-input', BASE / 'LC01_G_DEAD.inp', '--output', destination, '--scope-label', setup['scientific_scope']]  # Convert genuine detailed-model fields while retaining all native nodes and accepted times.
    if invoke(command, destination, 'adapt.log', 3600) != 0: raise RuntimeError('Full-field dataset adaptation failed')  # Preserve adaptation failure rather than training an incomplete archive.
    write(OUT / 'dataset_ready.json', {'status': 'DATASET_ASSEMBLED', 'experiment_sha256': digest(HERE / 'experiment.json'), 'manifest_sha256': digest(destination / 'dataset_manifest.json'), 'history_ids': [row['id'] for row in setup['cases']], 'native_fields_subsampled': False, 'training_completed': False})  # Distinguish genuine dataset preparation from learned weights.
def checkpoint_epoch(folder):  # Inspect only locally produced trusted training checkpoints.
    path = folder / 'progress.pt'  # Use the trainer's atomically published completed-epoch checkpoint.
    if not path.exists(): return 0  # No checkpoint means no completed trained-and-validated epoch.
    import torch  # Avoid importing the training runtime in native finite-element jobs.
    return int(torch.load(path, map_location='cpu', weights_only=False)['epoch']) + 1  # Convert the recorded zero-based epoch index to completed epoch count.
def train_stage(target):  # Continue the same frozen 300-epoch experiment in a bounded hosted job.
    setup = config(); folder = OUT / 'training'; folder.mkdir(parents=True, exist_ok=True)  # Keep selected and latest weights with their true complete-history execution evidence.
    if target not in (50, 100, 150, 200, 250, 300): raise ValueError('Unsupported declared training stage')  # Keep hosted segmentation explicit and finite.
    start = checkpoint_epoch(folder)  # Preserve actual completed work instead of inferring progress from job labels.
    command = [sys.executable, SOURCE / 'operator/train.py', 'train', '--manifest', OUT / 'dataset/dataset_manifest.json', '--family', 'global', '--output', folder, '--epochs', '300', '--stop-after-epoch', str(target), '--width', str(setup['width']), '--depth', str(setup['depth']), '--window', str(setup['window']), '--threads', '2', '--seed', str(setup['training_seed']), '--kernel-mode', setup['kernel_mode'], '--kernel-rank', str(setup['kernel_rank'])]  # Keep the full budget, graph, model family, source hashes and RNG contract unchanged across segments.
    if start: command.extend(['--resume', folder / 'progress.pt'])  # Restore exact optimizer, latest weights and stochastic state after a genuine completed epoch.
    code = invoke(command, folder, f'stage_{target}.log', setup['training_job_seconds'])  # Allow enough upload time before the hosted runner's independent hard limit.
    completed = checkpoint_epoch(folder)  # Read actual trained-and-validated progress after this invocation.
    write(folder / f'stage_{target}.json', {'status': 'TRAINING_BUDGET_COMPLETE' if completed == 300 else ('STAGE_COMPLETE' if completed >= target else 'PARTIAL'), 'requested_total_epochs': 300, 'stage_target_epoch': target, 'starting_completed_epochs': start, 'completed_epochs': completed, 'exit_code': code, 'prediction_accuracy_accepted': False, 'kernel_mode': setup['kernel_mode'], 'kernel_rank': setup['kernel_rank']})  # Training work and physical predictive accuracy are separate outcomes.
    plot_curves(folder)  # Render only actually logged numerical training and validation data through Gnuplot.
    if code not in (0, 124) or completed <= start: raise RuntimeError('Training failed or completed no resumable epoch')  # Stop the job chain on numerical failures or unusable time budgets.
    if target == 300 and completed != 300: raise RuntimeError('Full 300-epoch budget is unfinished')  # Refuse to call a partially trained checkpoint complete.
def plot_curves(folder):  # Use native Gnuplot rather than a Python graphics backend.
    if not (folder / 'training_history.csv').exists(): return  # No recorded updates means there is no genuine curve to draw.
    script = folder / 'training_curves.gp'  # Save the exact renderer commands beside their input data.
    lines = ['set terminal pngcairo size 1800,1100 font "DejaVu Sans,18" # Native Gnuplot raster output.', 'set output "training_curves.png" # Render only the actual logged optimization history.', 'set datafile separator comma # Read the trainer numeric CSV unchanged.', 'set multiplot layout 2,1 title "Detailed Zhaqing operator: observed training history" # Separate loss and validation quantities.', 'set grid back # Keep the quantitative scales readable.', 'set xlabel "Completed epoch" # Use true completed-epoch counts.', 'set ylabel "Training loss" # Preserve the recorded normalized training objective.', 'plot "training_history.csv" using 1:2 with lines lw 2 lc rgb "#2563eb" title "Training" # Draw actual finite logged values.', 'set ylabel "Validation error ratio" # This ratio is not a percent or an engineering acceptance claim.', 'plot "training_history.csv" using 1:3 with lines lw 2 lc rgb "#dc2626" title "Independent validation histories" # Validation selects weights, test data remain unopened.', 'unset multiplot # Finish the two-panel native rendering.']  # Keep every plotting command separately inspectable.
    script.write_text('\n'.join(lines) + '\n')  # Persist a reproducible non-Python plotting specification.
    try: result = subprocess.run(['gnuplot', script.name], cwd=folder, capture_output=True, text=True, timeout=60); write(folder / 'plot_receipt.json', {'renderer': 'gnuplot', 'exit_code': result.returncode, 'data_sha256': digest(folder / 'training_history.csv'), 'script_sha256': digest(script), 'stderr': result.stderr})  # Record the actual graphics renderer and source identities.
    except (OSError, subprocess.TimeoutExpired) as error: write(folder / 'plot_receipt.json', {'renderer': 'gnuplot', 'status': 'FAILED', 'error': str(error)})  # Keep graph failure distinct from numerical training work.
def evaluate():  # Open the frozen held-out test fields only after the complete training budget.
    folder = OUT / 'training'  # Select the exact stage-chain checkpoint directory.
    if checkpoint_epoch(folder) != 300: raise ValueError('Independent final test requires the completed 300-epoch experiment')  # Prevent a short training run being reported as the requested final experiment.
    destination = OUT / 'independent_test'  # Preserve unseen-history predictions and individual error tables independently.
    command = [sys.executable, SOURCE / 'operator/train.py', 'evaluate', '--manifest', OUT / 'dataset/dataset_manifest.json', '--family', 'global', '--output', destination, '--checkpoint', folder / 'progress.pt', '--threads', '2']  # Evaluate only the validation-selected weights without fitting to held-out outcomes.
    if invoke(command, destination, 'test.log', config()['training_job_seconds']) != 0: raise RuntimeError('Independent full-history test failed')  # Do not infer test success from completion of optimizer updates.
    result = json.loads((destination / 'independent_test.json').read_text())  # Read actual test metrics from the complete held-out population.
    write(destination / 'completion.json', {'status': 'GLOBAL_TRAINING_AND_TEST_EXECUTED', 'completed_epochs': 300, 'test_history_count': len(result['records']), 'scientific_scope': config()['scientific_scope'], 'kernel_mode': config()['kernel_mode'], 'kernel_rank': config()['kernel_rank'], 'engineering_accuracy_accepted': False, 'local_saddle_training_completed': False, 'test_metrics_sha256': digest(destination / 'independent_test.json')})  # Preserve the precise motion-field research scope and separate local incompleteness.
def local_case():  # Attempt the real 283-wire source-dimensional nonlinear cyclic problem.
    setup = config(); folder = OUT / 'local/explicit_283_wires'  # Keep native local results separate from whole-bridge training artifacts.
    command = [sys.executable, SOURCE / 'local/build_quadratic_saddle.py', folder, '--wires', '283', '--nx', '16', '--nc', '2', '--tension', '801490', '--mu', '.2', '--elastic-forming-stress', '--prestressed-equilibrium']  # Preserve every wire and the complete declared four-stage cycle.
    if invoke(command, folder, 'build.log', 900) != 0: raise RuntimeError('Explicit 283-wire quadratic model generation failed')  # Geometry failure must block native solving and learning.
    solver = os.environ.get('CCX_EXECUTABLE', 'ccx')  # Use a declared native executable and record its actual identity.
    version = subprocess.run([solver, '-v'], capture_output=True, text=True, timeout=20)  # Capture native solver version without interpreting its nonstandard version exit as a solve result.
    write(folder / 'solver_identity.json', {'executable': solver, 'version_stdout': version.stdout, 'version_stderr': version.stderr, 'version_command_exit': version.returncode, 'runtime_source': 'GitHub runner Ubuntu calculix-ccx package unless CCX_EXECUTABLE explicitly supplied', 'load_provenance': 'Assumed research tension 801490 N; not a new global-history transfer'})  # Do not mislabel the provisional loading or a relocated runtime.
    code = invoke([solver, '-i', folder / 'saddle'], folder, 'native.log', setup['native_job_seconds'])  # Execute actual all-wire friction/contact and geometric nonlinearity.
    audit = [sys.executable, SOURCE / 'local/native_result_receipt.py', folder, '--exit-code', str(code), '--log', 'native.log']  # Record the genuine terminal increment and solver exit.
    if invoke(audit, folder, 'completion_audit.log', 300) != 0: raise RuntimeError('Native local completion audit failed')  # Require an independent parser of the real native status evidence.
    receipt = json.loads((folder / 'native_completion.json').read_text())  # Read actual full-cycle native completion.
    write(folder / 'training_status.json', {'status': 'BLOCKED_PENDING_LOCAL_FIELD_QUALIFICATION' if receipt['full_requested_path_completed'] else 'BLOCKED_NATIVE_CYCLE_INCOMPLETE', 'native_cycle_complete': receipt['full_requested_path_completed'], 'trained_epochs': 0, 'all_wires': 283, 'fatigue_life_calibrated': False, 'reason': 'Full-cycle native completion is necessary; contact/force/mesh checks, quadratic field extraction and independent local histories are required before training.'})  # Keep absence of qualified local training data explicit even after a native solver success.
    if not receipt['full_requested_path_completed']: raise RuntimeError('All-wire cyclic native problem did not complete')  # Retain failed reference solves without promoting them to supervised labels.
def main():  # Expose reproducible finite stages for local and hosted execution.
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['plan', 'global-case', 'assemble', 'train-stage', 'evaluate', 'local-case']); parser.add_argument('--case-id'); parser.add_argument('--target-epoch', type=int)  # Keep every expensive action explicit.
    args = parser.parse_args()  # Parse one documented stage invocation.
    if args.stage == 'plan': print(json.dumps(config(), indent=2)); return  # Inspect the exact frozen contract without launching a computation.
    try: {'global-case': lambda: global_case(args.case_id), 'assemble': assemble, 'train-stage': lambda: train_stage(args.target_epoch), 'evaluate': evaluate, 'local-case': local_case}[args.stage]()  # Run exactly the selected phase.
    except BaseException as error: write(OUT / 'stage_failures' / f'{args.stage}_{args.case_id or args.target_epoch or "default"}.json', {'stage': args.stage, 'status': 'FAILED_OR_UNFINISHED', 'error': str(error), 'training_completed': False, 'unix_time_s': time.time()}); raise  # Preserve failure details for always-upload artifacts before returning a failing exit.
if __name__ == '__main__': main()  # Avoid launching native or training processes when imported by tests.
