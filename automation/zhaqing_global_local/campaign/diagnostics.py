#!/usr/bin/env python3  # Execute a bounded real detailed-bridge diagnostic on a durable hosted worker.
import argparse, importlib.metadata, json, os, shutil, sys, time  # Preserve exact native commands, runtime versions, and observed outcomes.
from pathlib import Path  # Keep every source and result path inside the checked-out project.
import run as campaign  # Reuse authenticated baseline restoration and bounded subprocess execution.
ROOT = campaign.ROOT  # Bind the same repository identity used by the full experiment.
OUT = ROOT / 'results/扎青吊桥求解诊断'  # Give the user-facing diagnostic result a natural descriptive directory name.
def make_command(tolerance, folder, steps=32, internal_substeps=2, shell_element='ShellNLDKGQ'):  # 输入原生容差、输出目录、完整帧数、每帧子步和明确的非线性壳公式；返回完整模型命令。
    if tolerance not in (.01, .005, .002, .0001) or steps not in (32, 160) or internal_substeps not in (2, 4, 8) or shell_element not in ('ShellNLDKGQ', 'ASDShellQ4'): raise ValueError('Unsupported paired diagnostic contract')  # 仅允许预先声明的时间网格和两种非线性公式，禁止缩小模型或偷偷换线性壳。
    name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Keep independent baseline, production default, and tightened native solves identifiable.
    name += '' if shell_element == 'ShellNLDKGQ' else '_asdshellq4'  # 用不同算例身份区分壳公式，禁止把替代公式结果冒充原公式。
    return [sys.executable, campaign.SOURCE / 'global/transient_cases.py', '--source', campaign.BASE / 'LC01_G_DEAD.inp', '--state', campaign.BASE / 'equilibrium_state.json', '--output', folder, '--detailed-model', '--subdivision', '1', '--case-id', 'diagnostic_' + name, '--split', 'validation', '--steps', str(steps), '--dt', '.00625', '--internal-substeps', str(internal_substeps), '--speed', '8', '--seed', '11', '--storage', 'hdf5', '--shell-element', shell_element, '--initial-displacement-tolerance', '1e-9', '--native-force-tolerance', str(tolerance)]  # 两个公式保持相同源几何、质量、预应力初猜、风载和完整输出网格；ASDShellQ4由既有建模器显式启用corotational。
def verify_completion(receipt, stream, case_id, steps, internal_substeps=2, shell_element='ShellNLDKGQ'):  # 核对回执、完整时程、内部网格和壳公式；默认保持原诊断契约。
    if receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('case_id') != case_id or receipt.get('split') != 'validation' or receipt.get('training_eligible') is not False: raise ValueError('Native diagnostic identity or acceptance mismatch')  # Do not admit a differently scoped or training-eligible result.
    if receipt.get('node_count') != 30555 or receipt.get('time_steps') != steps or receipt.get('dt_s') != .00625 or receipt.get('internal_substeps') != internal_substeps: raise ValueError('Native mesh or requested history/integration grid changed')  # 仍要求完整30555节点、原输出间隔及实际子步数与运行前声明严格一致；不得缩短时程。
    if stream.get('status') != 'COMPLETE' or stream.get('written_frames') != steps + 1 or abs(stream.get('last_time_s', -1) - steps * .00625) > 1e-12: raise ValueError('Native diagnostic field stream is incomplete')  # Require every expected frame and the true terminal physical time.
    if receipt.get('shell_element', 'ShellNLDKGQ') != shell_element: raise ValueError('Native shell formulation changed')  # 旧原壳回执保留兼容，但替代公式必须明确记录并匹配预先请求。
def execute(tolerance, steps=32, internal_substeps=2, shell_element='ShellNLDKGQ'):  # 执行明确容差、帧数、子步数和非线性壳公式的真实全桥对照。
    campaign.restore_inputs(); name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Authenticate the original model inputs before starting the selected native case.
    name += '' if shell_element == 'ShellNLDKGQ' else '_asdshellq4'  # 替代壳采用独立身份和目录，不覆盖历史原壳失败证据。
    folder = OUT / (name if internal_substeps == 2 else f'{name}-substeps{internal_substeps}'); folder.mkdir(parents=True, exist_ok=True)  # 保留原2子步路径；不同公式和网格均隔离。
    command = make_command(tolerance, folder, steps, internal_substeps, shell_element); started = time.time()  # 启动前固定实际公式、时间网格和墙钟计时。
    sources = {str(path.relative_to(ROOT)): campaign.digest(path) for path in sorted(campaign.SOURCE.rglob('*.py'))}  # Bind the diagnostic to every checked-in numerical source file used by this checkout.
    versions = {package: importlib.metadata.version(package) for package in ('numpy', 'scipy', 'h5py', 'openseespy', 'openseespylinux')}  # Record actual installed native and data-runtime versions instead of assuming the dependency resolver chose the requested backend.
    report = {'status': 'RUNNING', 'native_force_tolerance_mixed_N_Nmm': tolerance, 'independent_acceptance_gate_N': .02, 'requested_steps': steps, 'dt_s': .00625, 'internal_substeps': internal_substeps, 'requested_duration_s': steps * .00625, 'expected_nodes': 30555, 'command': [str(item) for item in command], 'git_commit': os.environ.get('GITHUB_SHA'), 'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'sources_sha256': sources, 'runtime_versions': versions, 'native_budget_seconds': 3600, 'diagnostic_only': True, 'training_eligible': False, 'actual_new_bridge_training_epochs_completed': 0}  # 记录精确离散设置；独立0.02N门槛、完整诊断时程、3600s预算及零训练轮次均不变。
    report['shell_element'] = shell_element  # 在启动回执明确标记原壳或替代非线性壳，避免后处理混用。
    campaign.write(folder / '计算状态.json', report)  # Publish inspectable launch evidence before the expensive native subprocess.
    source_folder = folder / '执行程序'; source_folder.mkdir(exist_ok=True)  # Preserve orchestration source beside the solver's own model snapshots.
    for path in (Path(__file__), Path(campaign.__file__)): shutil.copy2(path, source_folder / path.name)  # Keep the exact runner and authenticated-input helper used by this execution.
    try:  # Always finalize diagnostic status even when the native solve fails or reaches its budget.
        code = campaign.invoke(command, folder, '原生求解.log', 3600); report['exit_code'] = code  # Retain a full native stdout/stderr log and the real subprocess outcome.
        if code != 0: raise RuntimeError(f'Native diagnostic exited with {code}')  # A failed solver cannot be promoted to a completed history.
        receipt = json.loads((folder / 'case_manifest.json').read_text()); stream = json.loads((folder / 'fields_stream_status.json').read_text())  # Read the native producer's actual completion evidence.
        verify_completion(receipt, stream, 'diagnostic_' + name, steps, internal_substeps, shell_element)  # 必须完成请求的全部帧并使用已声明的壳公式。
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
    parser.add_argument('--internal-substeps', type=int, choices=(2, 4, 8), default=2)  # 默认保留原2子步；4/8用于检验提交后残差对内部dt减半/减为四分之一的敏感性。
    parser.add_argument('--shell-element', choices=('ShellNLDKGQ', 'ASDShellQ4'), default='ShellNLDKGQ')  # 原公式仍为默认；替代壳必须显式选择并启用既有共回转实现。
    args = parser.parse_args(); execute(args.native_force_tolerance, args.steps, args.internal_substeps, args.shell_element)  # 执行完整诊断，不启用参考数据或训练模式。
