#!/usr/bin/env python3  # Execute a bounded real detailed-bridge diagnostic on a durable hosted worker.
import argparse, importlib.metadata, json, os, shutil, sys, time  # Preserve exact native commands, runtime versions, and observed outcomes.
from pathlib import Path  # Keep every source and result path inside the checked-out project.
import run as campaign  # Reuse authenticated baseline restoration and bounded subprocess execution.
ROOT = campaign.ROOT  # Bind the same repository identity used by the full experiment.
OUT = ROOT / 'results/扎青吊桥求解诊断'  # Give the user-facing diagnostic result a natural descriptive directory name.
def make_command(tolerance, folder, steps=32):  # Freeze the physical experiment while varying only the native stopping tolerance.
    if tolerance not in (.01, .005, .002, .0001) or steps not in (32, 160): raise ValueError('Unsupported paired diagnostic contract')  # Prevent accidental production-length or unplanned solver changes.
    name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Keep independent baseline, production default, and tightened native solves identifiable.
    return [sys.executable, campaign.SOURCE / 'global/transient_cases.py', '--source', campaign.BASE / 'LC01_G_DEAD.inp', '--state', campaign.BASE / 'equilibrium_state.json', '--output', folder, '--detailed-model', '--subdivision', '1', '--case-id', 'diagnostic_' + name, '--split', 'validation', '--steps', str(steps), '--dt', '.00625', '--internal-substeps', '2', '--speed', '8', '--seed', '11', '--storage', 'hdf5', '--shell-element', 'ShellNLDKGQ', '--initial-displacement-tolerance', '1e-9', '--native-force-tolerance', str(tolerance)]  # Retain all detailed nodes and physical time steps while preventing training-eligible case publication.
def verify_completion(receipt, stream, case_id, steps):  # Distinguish a fully completed diagnostic from an interrupted or substituted native history.
    if receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('case_id') != case_id or receipt.get('split') != 'validation' or receipt.get('training_eligible') is not False: raise ValueError('Native diagnostic identity or acceptance mismatch')  # Do not admit a differently scoped or training-eligible result.
    if receipt.get('node_count') != 30555 or receipt.get('time_steps') != steps or receipt.get('dt_s') != .00625: raise ValueError('Native mesh or requested history changed')  # Preserve the exact full detailed mesh and declared short diagnostic duration.
    if stream.get('status') != 'COMPLETE' or stream.get('written_frames') != steps + 1 or abs(stream.get('last_time_s', -1) - steps * .00625) > 1e-12: raise ValueError('Native diagnostic field stream is incomplete')  # Require every expected frame and the true terminal physical time.
def execute(tolerance, steps=32):  # Run actual finite-element equilibrium and wind steps rather than implementation fixtures.
    campaign.restore_inputs(); name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Authenticate the original model inputs before starting the selected native case.
    folder = OUT / name; folder.mkdir(parents=True, exist_ok=True)  # Isolate all raw numerical evidence by the one varied native parameter.
    command = make_command(tolerance, folder, steps); started = time.time()  # Freeze the exact executable arguments and observed start time.
    sources = {str(path.relative_to(ROOT)): campaign.digest(path) for path in sorted(campaign.SOURCE.rglob('*.py'))}  # Bind the diagnostic to every checked-in numerical source file used by this checkout.
    versions = {package: importlib.metadata.version(package) for package in ('numpy', 'scipy', 'h5py', 'openseespy', 'openseespylinux')}  # Record actual installed native and data-runtime versions instead of assuming the dependency resolver chose the requested backend.
    report = {'status': 'RUNNING', 'native_force_tolerance_mixed_N_Nmm': tolerance, 'independent_acceptance_gate_N': .02, 'requested_steps': steps, 'dt_s': .00625, 'internal_substeps': 2, 'requested_duration_s': steps * .00625, 'expected_nodes': 30555, 'command': [str(item) for item in command], 'git_commit': os.environ.get('GITHUB_SHA'), 'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'sources_sha256': sources, 'runtime_versions': versions, 'native_budget_seconds': 3600, 'diagnostic_only': True, 'training_eligible': False, 'actual_new_bridge_training_epochs_completed': 0}  # State the real diagnostic scope without changing the frozen 300-epoch campaign.
    campaign.write(folder / '计算状态.json', report)  # Publish inspectable launch evidence before the expensive native subprocess.
    source_folder = folder / '执行程序'; source_folder.mkdir(exist_ok=True)  # Preserve orchestration source beside the solver's own model snapshots.
    for path in (Path(__file__), Path(campaign.__file__)): shutil.copy2(path, source_folder / path.name)  # Keep the exact runner and authenticated-input helper used by this execution.
    try:  # Always finalize diagnostic status even when the native solve fails or reaches its budget.
        code = campaign.invoke(command, folder, '原生求解.log', 3600); report['exit_code'] = code  # Retain a full native stdout/stderr log and the real subprocess outcome.
        if code != 0: raise RuntimeError(f'Native diagnostic exited with {code}')  # A failed solver cannot be promoted to a completed history.
        receipt = json.loads((folder / 'case_manifest.json').read_text()); stream = json.loads((folder / 'fields_stream_status.json').read_text())  # Read the native producer's actual completion evidence.
        verify_completion(receipt, stream, 'diagnostic_' + name, steps)  # Require the complete requested diagnostic and exact full mesh.
        dataset = Path(receipt['dataset'])  # Select the field file published by the successful native exporter.
        if not dataset.resolve().is_relative_to(folder.resolve()) or campaign.digest(dataset) != receipt['dataset_sha256']: raise ValueError('Native field artifact location or hash mismatch')  # Verify real complete field bytes before reporting success.
        report.update(status='DIAGNOSTIC_COMPLETE', accepted_dynamic_steps=steps, native_dataset_sha256=receipt['dataset_sha256'])  # Report only the short diagnostic outcome rather than the complete production training population.
    except BaseException as error:  # Keep the actual failure inspectable through hosted artifact publication.
        report.update(status='DIAGNOSTIC_FAILED', error=str(error))  # Preserve the original native or admission error without weakening its gate.
        for filename in ('rejected_step.json', 'case_failure.json', 'fields_stream_status.json'):  # Carry small exact failure and accepted-frame evidence into the top-level status.
            path = folder / filename  # Keep every status lookup scoped to this actual native case.
            if path.is_file(): report[filename] = json.loads(path.read_text())  # Read only solver-published evidence and never manufacture a successful field frame.
        raise  # Propagate the failure so GitHub displays the real unsuccessful numerical result.
    finally:  # Preserve launch, elapsed time, failure, and completed source identities on every Python exit path.
        report['elapsed_seconds'] = time.time() - started; campaign.write(folder / '计算状态.json', report)  # Atomically expose the actual final diagnostic outcome.
        print(json.dumps({key: value for key, value in report.items() if key != 'sources_sha256'}, ensure_ascii=False), flush=True)  # Show a readable actual result while leaving the complete source identity table in the artifact.
if __name__ == '__main__':  # Keep diagnostics explicit and separate from the full campaign's guarded mode selection.
    parser = argparse.ArgumentParser(); parser.add_argument('--native-force-tolerance', type=float, choices=(.01, .005, .002, .0001), required=True); parser.add_argument('--steps', type=int, choices=(32, 160), default=32)  # Expose the original, production-default, and strict stopping thresholds plus two bounded diagnostic lengths.
    args = parser.parse_args(); execute(args.native_force_tolerance, args.steps)  # Execute the concrete full-mesh native diagnostic requested by the hosted job.
