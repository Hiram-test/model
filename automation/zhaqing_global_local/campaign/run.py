#!/usr/bin/env python3  # Execute durable full-field generation, qualification, training and independent testing.
import argparse, ast, hashlib, json, os, re, shutil, signal, subprocess, sys, time, zipfile  # Preserve actual subprocess outcomes and immutable numerical identities.
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
    if len({case['seed'] for case in cases}) != len(cases): raise ValueError('Loading realization seed reused across the frozen population')  # Keep independent phases and pulse locations across all complete histories.
    if [sum(case['split'] == split for case in cases) for split in ('train', 'validation', 'test')] != [6, 2, 2]: raise ValueError('Expected frozen 6/2/2 history partition')  # Freeze every independent test case before training.
    if value['epochs'] != 300 or value['steps'] * value['dt_s'] != 20.0: raise ValueError('Changed complete training or physical-duration budget')  # Refuse silent short-run substitution.
    return value  # Return a fully checked complete campaign contract.
def launch():  # Select validation, reference generation or later training without changing the scientific experiment hash.
    value = json.loads((HERE / 'launch.json').read_text())  # Keep run routing separate from fixed loads, partitions and model parameters.
    if value['mode'] not in ('validation', 'references', 'training'): raise ValueError('Unknown campaign launch mode')  # Keep software validation explicitly separate from expensive physical and learning stages.
    reference = str(value.get('reference_run_id') or '')  # Preserve a concrete previously observed native-reference workflow identity.
    if value['mode'] == 'training' and (not reference.isdigit() or int(reference) <= 0): raise ValueError('Training needs a concrete completed reference workflow run ID')  # Never guess or fetch an unrelated artifact population.
    if value['mode'] == 'references':  # Refuse the currently measured job budget and nonlinear state before launching a ten-case matrix.
        readiness = json.loads((HERE / 'readiness.json').read_text())  # Keep the checked numerical execution qualification visible beside launch routing.
        if not readiness.get('reference_execution_qualified', False): raise ValueError('Reference execution remains blocked: qualify nonlinear convergence and a complete-history runtime or exact restart path first')  # Changing only the mode cannot start known-unqualified expensive native work.
    if os.environ.get('GITHUB_OUTPUT'):  # Publish only validated routing data to the current workflow's own job outputs.
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream: stream.write(f'mode={value["mode"]}\nreference_run_id={reference}\n')  # Avoid external messages and preserve read-only repository permissions.
    print(json.dumps(value), flush=True)  # Make the actual launch decision inspectable before expensive work.
def workflow_contract():  # Verify the published workflow cannot run numerical production stages in validation mode.
    import yaml  # Load workflow YAML only in the lightweight implementation-validation stage.
    parent = yaml.load((ROOT / '.github/workflows/zhaqing-global-local-training.yml').read_text(), Loader=yaml.BaseLoader)  # Preserve GitHub's literal on key independently of YAML 1.1 boolean inference.
    jobs = parent['jobs']  # Inspect actual checked-in job routing rather than a separate generated approximation.
    if jobs['validation']['if'] != "needs.prepare.outputs.mode == 'validation'": raise ValueError('Validation job routing changed')  # Restrict bounded implementation tests to their explicitly named mode.
    for name in ('global-reference', 'local-reference'):  # Both native producers must remain disabled in validation mode.
        if jobs[name]['if'] != "needs.prepare.outputs.mode == 'references'": raise ValueError('Native job is not isolated to reference mode')  # Prevent a software-only source push from starting known-unqualified expensive solves.
    for epoch in range(4, 301, 4):  # Inspect every actual four-epoch continuation job, not only the first dependency.
        job = jobs[f'train-{epoch}']  # Require the complete finite 300-epoch chain to remain present.
        if job['if'] != "needs.prepare.outputs.mode == 'training'" or int(job['with']['target-epoch']) != epoch or int(job['with']['previous-epoch']) != epoch - 4: raise ValueError('Training continuation routing or epoch boundary changed')  # Explicitly disable all optimization in validation and reference modes.
    if jobs['independent-test']['if'] != "needs.prepare.outputs.mode == 'training'": raise ValueError('Independent-test routing changed')  # Do not treat unit-test execution as a held-out real-bridge evaluation.
    return {'job_count': len(jobs), 'continuation_segments': 75, 'native_and_training_jobs_disabled_in_validation': True}  # Report only properties independently checked against the actual workflow.
def validate():  # Execute implementation and data-interface checks without claiming any new physical history or trained weight.
    setup = config(); folder = OUT / 'implementation_validation'; folder.mkdir(parents=True, exist_ok=True)  # Keep software-test artifacts outside actual native and learned result directories.
    routing = json.loads((HERE / 'launch.json').read_text())  # Require the published software-only routing for this validation execution.
    if routing['mode'] != 'validation': raise ValueError('Implementation validation requires explicit validation mode')  # Prevent this command from being substituted for a requested production campaign.
    workflow = workflow_contract(); restore_inputs()  # Check every job gate and authenticate the original input archive before interface tests.
    paths = sorted(SOURCE.rglob('*.py')); sources = {}  # Freeze every numerical implementation identity used by this validation run.
    for path in paths: ast.parse(path.read_text(), filename=str(path)); sources[str(path.relative_to(ROOT))] = digest(path)  # Check syntax without launching native solvers or generating any artificial field label.
    suites = [('campaign', 'test_campaign.py'), ('global', 'test_field_stream.py'), ('operator', 'test_gno.py'), ('operator', 'test_streaming.py'), ('local', 'test_quadratic_solid.py'), ('local', 'test_local_physics.py'), ('aero', 'test_aero_loads.py'), ('', 'test_coupling.py')]  # Declare bounded analytic, conservation, storage and continuation tests explicitly.
    checks = []; started = time.time()  # Preserve real elapsed time and individual subprocess outcomes.
    for directory, filename in suites:  # Continue through independent suites so one failure does not hide other diagnostics.
        path = SOURCE / directory / filename; label = (directory or 'coupling') + '_' + filename  # Keep one unique log namespace for each actual test executable.
        code = invoke([sys.executable, path], folder, label + '.log', 300)  # Run actual test assertions with a finite five-minute per-suite budget.
        output = (folder / (label + '.log')).read_text(); counts = re.findall(r'Ran (\d+) tests? in ', output)  # Read unittest's genuine completed-test count rather than assuming every declared test ran.
        checks.append({'source': str(path.relative_to(ROOT)), 'exit_code': code, 'completed_tests': int(counts[-1]) if counts else 0, 'log': label + '.log'})  # Retain partial or failed suite evidence without promoting it to engineering validation.
    blockers = json.loads((HERE / 'readiness.json').read_text())  # Copy the dated physical/resource findings separately from this new software-test execution.
    resources = {'logical_cpus_visible': os.cpu_count(), 'physical_memory_bytes_visible': os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'), 'disk_free_bytes': shutil.disk_usage(ROOT).free}  # Report actual runner resource observations without assuming physical CPU or container quotas.
    for name in ('memory.max', 'cpu.max'):  # Record container limits when the host exposes cgroup v2 controls.
        path = Path('/sys/fs/cgroup') / name  # Read only the current process environment's resource-limit declaration.
        if path.is_file(): resources['cgroup_' + name.replace('.', '_')] = path.read_text().strip()  # Keep quota text explicit instead of claiming visible host resources are allocatable.
    passed = all(row['exit_code'] == 0 and row['completed_tests'] > 0 for row in checks)  # Require every declared suite to execute and pass actual assertions.
    report = {'status': 'IMPLEMENTATION_TESTS_PASSED_NOT_BRIDGE_TRAINING' if passed else 'IMPLEMENTATION_TESTS_FAILED', 'test_suites': checks, 'completed_test_count': sum(row['completed_tests'] for row in checks), 'workflow_contract': workflow, 'sources_sha256': sources, 'experiment_sha256': digest(HERE / 'experiment.json'), 'readiness_sha256': digest(HERE / 'readiness.json'), 'readiness_snapshot': blockers, 'runner_resources': resources, 'elapsed_seconds': time.time() - started, 'native_solves_launched': 0, 'actual_new_bridge_training_epochs_completed': 0, 'qualified_reference_dataset_created': False, 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}  # Distinguish software correctness and observed resources from unresolved physical data generation.
    write(folder / 'validation_report.json', report); print(json.dumps(report), flush=True)  # Persist complete provenance and failures as one inspectable workflow artifact.
    if not passed: raise RuntimeError('One or more implementation or interface suites failed')  # A failing assertion must cause a failed validation job.
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
    environment.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', MPIR_CVAR_CH3_NETWORK_IFACE='lo', MPICH_INTERFACE_HOSTNAME='127.0.0.1', PYTHONUNBUFFERED='1', GFORTRAN_UNBUFFERED_ALL='y', GFORTRAN_UNBUFFERED_PRECONNECTED='y')  # Bound workers and flush real native factorization progress before a resource failure.
    record = {'command': [str(x) for x in command], 'working_directory': str(ROOT), 'started_unix_s': started, 'timeout_s': seconds, 'experiment_sha256': digest(HERE / 'experiment.json'), 'status': 'RUNNING'}  # Persist the real launch command before starting numerical work.
    receipt = folder / (log_name + '.execution.json'); write(receipt, record)  # Make launch and resource budget externally inspectable.
    with (folder / log_name).open('w') as log:  # Keep complete stdout and stderr without flooding a compact status view.
        process = subprocess.Popen([str(x) for x in command], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)  # Start exactly the requested native or training command.
        try:  # Enforce the documented finite stage budget while exposing real native progress.
            deadline = time.monotonic() + seconds; heartbeat = time.monotonic() + 60  # Keep the subprocess deadline independent of wall-clock adjustments.
            while process.poll() is None:  # Monitor the actual process rather than implying work continues after it exits.
                if time.monotonic() >= deadline: raise subprocess.TimeoutExpired(command, seconds)  # Stop early enough to publish complete partial-work evidence.
                if time.monotonic() >= heartbeat:  # Expose one concise native log tail per minute.
                    with (folder / log_name).open('rb') as current: current.seek(max(0, (folder / log_name).stat().st_size - 1200)); tail = current.read().decode(errors='replace')  # Read only a bounded suffix of the actual numerical process log.
                    print(json.dumps({'status': 'RUNNING', 'elapsed_seconds': time.time() - started, 'native_log_tail': tail}), flush=True); heartbeat = time.monotonic() + 60  # Report observed native iterations or training progress without invented percentages.
                time.sleep(5)  # Bound monitoring overhead while retaining frequent durable progress reports.
            code = process.returncode  # Preserve the actual native or learning-process exit code.
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
    if receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('case_id') != case_id or receipt.get('split') != case['split'] or receipt.get('dt_s') != setup['dt_s'] or receipt.get('time_steps') != setup['steps'] or receipt.get('node_count', 0) < 30000: raise ValueError('Native completion, physical duration, or detailed mesh gate failed')  # Prevent old equivalent-deck, changed partitions or shortened runs entering the new dataset.
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
def adapt_case(case_id):  # Produce a portable full-node full-time supervised field archive on the native producer runner.
    setup = config(); case = next(row for row in setup['cases'] if row['id'] == case_id)  # Preserve the original independent loading realization and split.
    path = OUT / 'global' / case_id / 'case_manifest.json'; receipt = json.loads(path.read_text())  # Require a genuine native completion receipt before opening labels.
    if receipt.get('case_id') != case_id or receipt.get('split') != case['split'] or receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('dt_s') != setup['dt_s'] or receipt.get('time_steps') != setup['steps'] or receipt.get('node_count', 0) < 30000: raise ValueError('Complete frozen population qualification failed')  # Reject missing duration, old geometry, changed partitions, or failed solves.
    destination = OUT / 'datasets' / case_id  # Package all supervised arrays and their evidence in a standalone per-history directory.
    command = [sys.executable, SOURCE / 'operator/adapt_global.py', '--case-manifests', relocate_receipt(path), '--source-input', BASE / 'LC01_G_DEAD.inp', '--output', destination, '--scope-label', setup['scientific_scope'], '--storage-mode', 'standalone']  # Preserve all target and control values while archiving separate native audit fields independently.
    if invoke(command, destination, 'adapt.log', 3600) != 0: raise RuntimeError('Full-field per-case adaptation failed')  # A failed converter cannot create a usable training artifact.
    write(destination / 'campaign_case.json', {'case_id': case_id, 'split': case['split'], 'time_steps': setup['steps'], 'dt_s': setup['dt_s'], 'native_nodes': receipt['node_count'], 'experiment_sha256': digest(HERE / 'experiment.json'), 'native_receipt_sha256': digest(path), 'native_dataset_sha256': receipt['dataset_sha256'], 'native_artifact_name': 'global-native-' + case_id, 'native_fields_subsampled': False})  # Bind the compact supervised artifact to the separately preserved complete native evidence.
def assemble():  # Join portable case manifests without copying multi-gigabyte response arrays.
    setup = config(); destination = OUT / 'datasets'; combined = None; rows = []  # Freeze the complete population and one common field vocabulary.
    for case in setup['cases']:  # Include every declared complete realization exactly once.
        folder = destination / ('global-dataset-' + case['id'])  # Match download-artifact's deterministic named-artifact subdirectory.
        path = folder / 'dataset_manifest.json'; one = json.loads(path.read_text())  # A missing or failed case prevents the whole dataset from being assembled.
        audit = json.loads((folder / 'campaign_case.json').read_text())  # Require the producer campaign's independent duration and provenance record.
        if audit['experiment_sha256'] != digest(HERE / 'experiment.json') or audit['time_steps'] != setup['steps'] or audit['dt_s'] != setup['dt_s'] or audit['native_nodes'] < 30000: raise ValueError('Per-case experiment or numerical scope mismatch')  # Prevent an old or shortened artifact being mixed into this frozen run.
        if len(one['cases']) != 1 or one['cases'][0]['id'] != case['id'] or one['cases'][0]['split'] != case['split']: raise ValueError('Per-case identity or frozen partition mismatch')  # Keep complete histories and independent tests intact.
        header = {key: value for key, value in one.items() if key != 'cases'}  # Compare all shared physical fields, units, graph relations and scope declarations.
        if combined is not None and header != combined: raise ValueError('Incompatible physical field or graph contracts')  # Do not silently combine different output meanings or discretization policies.
        combined = header; row = dict(one['cases'][0])  # Preserve source qualification and native entity population.
        for key in ('npz', 'hdf5', 'fields', 'solver_input', 'solver_result', 'convergence_report', 'geometry_evidence'):  # Relocate only declared case-local artifact references.
            if key not in row: continue  # Respect the converter's explicit NPZ/HDF5 representation.
            source = (folder / row[key]).resolve()  # Resolve the producer's relative portable artifact path.
            if not source.is_relative_to(folder.resolve()) or not source.is_file(): raise ValueError('Nonportable or missing per-case evidence')  # Refuse external absolute links and absent native proof.
            if digest(source) != row[key + '_sha256']: raise ValueError('Per-case artifact content identity changed')  # Verify exact labels and evidence after artifact transport.
            row[key] = str(source.relative_to(destination.resolve()))  # Prefix only the artifact directory without changing any hashed bytes.
        rows.append(row)  # Append one unchanged complete native history to its frozen partition.
    combined['cases'] = rows; write(destination / 'dataset_manifest.json', combined)  # Publish one portable cross-job dataset contract after the entire population is present.
    write(destination / 'dataset_ready.json', {'status': 'DATASET_ASSEMBLED', 'experiment_sha256': digest(HERE / 'experiment.json'), 'manifest_sha256': digest(destination / 'dataset_manifest.json'), 'history_ids': [row['id'] for row in setup['cases']], 'native_fields_subsampled': False, 'training_completed': False})  # Dataset preparation alone never claims learned accuracy or complete training.
def checkpoint_epoch(folder):  # Inspect only locally produced trusted training checkpoints.
    path = folder / 'progress.pt'  # Use the trainer's atomically published completed-epoch checkpoint.
    if not path.exists(): return 0  # No checkpoint means no completed trained-and-validated epoch.
    import torch  # Avoid importing the training runtime in native finite-element jobs.
    return int(torch.load(path, map_location='cpu', weights_only=False)['epoch']) + 1  # Convert the recorded zero-based epoch index to completed epoch count.
def train_stage(target):  # Continue the same frozen 300-epoch experiment in a bounded hosted job.
    setup = config(); folder = OUT / 'training'; folder.mkdir(parents=True, exist_ok=True)  # Keep selected and latest weights with their true complete-history execution evidence.
    if target not in range(4, 301, 4): raise ValueError('Unsupported declared training stage')  # Keep 75 measured four-epoch continuation segments explicit and finite.
    start = checkpoint_epoch(folder)  # Preserve actual completed work instead of inferring progress from job labels.
    command = [sys.executable, SOURCE / 'operator/train.py', 'train', '--manifest', OUT / 'datasets/dataset_manifest.json', '--family', 'global', '--output', folder, '--epochs', '300', '--stop-after-epoch', str(target), '--width', str(setup['width']), '--depth', str(setup['depth']), '--window', str(setup['window']), '--threads', '2', '--seed', str(setup['training_seed']), '--kernel-mode', setup['kernel_mode'], '--kernel-rank', str(setup['kernel_rank'])]  # Keep the full budget, graph, model family, source hashes and RNG contract unchanged across segments.
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
    command = [sys.executable, SOURCE / 'operator/train.py', 'evaluate', '--manifest', OUT / 'datasets/dataset_manifest.json', '--family', 'global', '--output', destination, '--checkpoint', folder / 'progress.pt', '--threads', '2']  # Evaluate only the validation-selected weights without fitting to held-out outcomes.
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
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['plan', 'launch', 'validate', 'global-case', 'adapt-case', 'assemble', 'train-stage', 'evaluate', 'local-case']); parser.add_argument('--case-id'); parser.add_argument('--target-epoch', type=int)  # Keep software-only checks and every expensive action explicit.
    args = parser.parse_args()  # Parse one documented stage invocation.
    if args.stage == 'plan': print(json.dumps(config(), indent=2)); return  # Inspect the exact frozen contract without launching a computation.
    if args.stage == 'launch': launch(); return  # Select execution routing independently from the scientific data contract.
    try: {'validate': validate, 'global-case': lambda: global_case(args.case_id), 'adapt-case': lambda: adapt_case(args.case_id), 'assemble': assemble, 'train-stage': lambda: train_stage(args.target_epoch), 'evaluate': evaluate, 'local-case': local_case}[args.stage]()  # Run exactly the selected phase.
    except BaseException as error: write(OUT / 'stage_failures' / f'{args.stage}_{args.case_id or args.target_epoch or "default"}.json', {'stage': args.stage, 'status': 'FAILED_OR_UNFINISHED', 'error': str(error), 'training_completed': False, 'unix_time_s': time.time()}); raise  # Preserve failure details for always-upload artifacts before returning a failing exit.
if __name__ == '__main__': main()  # Avoid launching native or training processes when imported by tests.
