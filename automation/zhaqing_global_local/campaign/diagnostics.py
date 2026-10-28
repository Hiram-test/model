#!/usr/bin/env python3  # Execute a bounded real detailed-bridge diagnostic on a durable hosted worker.
import argparse, importlib.metadata, json, os, shutil, sys, time  # Preserve exact native commands, runtime versions, and observed outcomes.
from pathlib import Path  # Keep every source and result path inside the checked-out project.
import run as campaign  # Reuse authenticated baseline restoration and bounded subprocess execution.
ROOT = campaign.ROOT  # Bind the same repository identity used by the full experiment.
OUT = ROOT / 'results/扎青吊桥求解诊断'  # Give the user-facing diagnostic result a natural descriptive directory name.
DEFAULT_SHELL='ASDShellQ4'  # 与完整动力入口一致的候选共回转非线性壳默认值。
DEFAULT_NATIVE_TEST='NormDispIncr'  # 默认以内位移停止和外部独立力验收组合求解。
def make_command(tolerance, folder, steps=32, internal_substeps=2, shell_element=DEFAULT_SHELL, native_test=DEFAULT_NATIVE_TEST, displacement_tolerance=1e-8):  # 默认与完整动力入口一致；原公式和判据必须明确指定。
    if tolerance not in (.01, .005, .002, .0001) or steps not in (32, 160) or internal_substeps not in (2, 4, 8) or shell_element not in ('ShellNLDKGQ', 'ASDShellQ4'): raise ValueError('Unsupported paired diagnostic contract')  # 仅允许预先声明的时间网格和两种非线性公式，禁止缩小模型或偷偷换线性壳。
    name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Keep independent baseline, production default, and tightened native solves identifiable.
    name += '' if shell_element == 'ShellNLDKGQ' else '_asdshellq4'  # 用不同算例身份区分壳公式，禁止把替代公式结果冒充原公式。
    if native_test not in ('NormUnbalance','NormDispIncr') or not 0<displacement_tolerance<=1e-8: raise ValueError('Unsupported diagnostic convergence test')  # 位移停止阈值只能比1e-8更严，最终力门槛仍固定。
    name += '' if native_test == 'NormUnbalance' else f'_disp{displacement_tolerance:g}'  # 位移停止实验使用独立身份，不冒充原力范数对照。
    predictor_tolerance = '1e-8' if shell_element == 'ASDShellQ4' else '1e-9'  # 全桥ASD预测增量实测停在约6.6e-9mm；仅让预测阶段进入既有独立0.001N静力精化，原壳仍用1e-9mm。
    return [sys.executable, campaign.SOURCE / 'global/transient_cases.py', '--source', campaign.BASE / 'LC01_G_DEAD.inp', '--state', campaign.BASE / 'equilibrium_state.json', '--output', folder, '--detailed-model', '--subdivision', '1', '--case-id', 'diagnostic_' + name, '--split', 'validation', '--steps', str(steps), '--dt', '.00625', '--internal-substeps', str(internal_substeps), '--speed', '8', '--seed', '11', '--storage', 'hdf5', '--shell-element', shell_element, '--initial-displacement-tolerance', predictor_tolerance, '--native-force-tolerance', str(tolerance), '--native-convergence-test', native_test, '--native-displacement-tolerance', str(displacement_tolerance)]  # 两种内部判据分别标明阈值，最终静力0.001N与动力0.02N验收不变。
def verify_completion(receipt, stream, case_id, steps, internal_substeps=2, shell_element=DEFAULT_SHELL, native_test=DEFAULT_NATIVE_TEST):  # 按实际请求核对完整时程、公式和内部停止判据，不沿用错误默认身份。
    if receipt.get('quality') != 'VALID_CONVERGED' or receipt.get('case_id') != case_id or receipt.get('split') != 'validation' or receipt.get('training_eligible') is not False: raise ValueError('Native diagnostic identity or acceptance mismatch')  # Do not admit a differently scoped or training-eligible result.
    if receipt.get('node_count') != 30555 or receipt.get('time_steps') != steps or receipt.get('dt_s') != .00625 or receipt.get('internal_substeps') != internal_substeps: raise ValueError('Native mesh or requested history/integration grid changed')  # 仍要求完整30555节点、原输出间隔及实际子步数与运行前声明严格一致；不得缩短时程。
    if stream.get('status') != 'COMPLETE' or stream.get('written_frames') != steps + 1 or abs(stream.get('last_time_s', -1) - steps * .00625) > 1e-12: raise ValueError('Native diagnostic field stream is incomplete')  # Require every expected frame and the true terminal physical time.
    if receipt.get('shell_element', 'ShellNLDKGQ') != shell_element: raise ValueError('Native shell formulation changed')  # 旧原壳回执保留兼容，但替代公式必须明确记录并匹配预先请求。
    if receipt.get('native_convergence_test','NormUnbalance') != native_test: raise ValueError('Native convergence test changed')  # 不允许用不同内部判据的成功替代请求的试验。
def execute(tolerance, steps=32, internal_substeps=2, shell_element=DEFAULT_SHELL, native_budget_seconds=3600, native_test=DEFAULT_NATIVE_TEST, displacement_tolerance=1e-8):  # 完整诊断与生产入口使用同一候选默认，所有数值设置和有限预算仍显式记录。
    if native_budget_seconds not in (3600, 15000): raise ValueError('Unsupported diagnostic native budget')  # 禁止无限或隐式延长；此参数不改生产预算与训练准入。
    campaign.restore_inputs(); name = 'original' if tolerance == .01 else ('default' if tolerance == .005 else ('tight' if tolerance == .002 else 'strict'))  # Authenticate the original model inputs before starting the selected native case.
    name += '' if shell_element == 'ShellNLDKGQ' else '_asdshellq4'  # 替代壳采用独立身份和目录，不覆盖历史原壳失败证据。
    name += '' if native_test == 'NormUnbalance' else f'_disp{displacement_tolerance:g}'  # 位移停止实验在目录和算例身份中显式区别。
    folder = OUT / (name if internal_substeps == 2 else f'{name}-substeps{internal_substeps}'); folder.mkdir(parents=True, exist_ok=True)  # 保留原2子步路径；不同公式和网格均隔离。
    command = make_command(tolerance, folder, steps, internal_substeps, shell_element, native_test, displacement_tolerance); started = time.time()  # 启动前固定实际公式、内部判据和完整时间网格。
    sources = {str(path.relative_to(ROOT)): campaign.digest(path) for path in sorted(campaign.SOURCE.rglob('*.py'))}  # Bind the diagnostic to every checked-in numerical source file used by this checkout.
    versions = {package: importlib.metadata.version(package) for package in ('numpy', 'scipy', 'h5py', 'openseespy', 'openseespylinux')}  # Record actual installed native and data-runtime versions instead of assuming the dependency resolver chose the requested backend.
    report = {'status': 'RUNNING', 'native_force_tolerance_mixed_N_Nmm': tolerance, 'independent_acceptance_gate_N': .02, 'requested_steps': steps, 'dt_s': .00625, 'internal_substeps': internal_substeps, 'requested_duration_s': steps * .00625, 'expected_nodes': 30555, 'command': [str(item) for item in command], 'git_commit': os.environ.get('GITHUB_SHA'), 'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'sources_sha256': sources, 'runtime_versions': versions, 'native_budget_seconds': native_budget_seconds, 'diagnostic_only': True, 'training_eligible': False, 'actual_new_bridge_training_epochs_completed': 0}  # 完整记录运行前声明的有限预算、固定0.02N门槛及零训练轮次。
    report['shell_element'] = shell_element  # 在启动回执明确标记原壳或替代非线性壳，避免后处理混用。
    report.update(native_convergence_test=native_test,native_active_tolerance=tolerance if native_test=='NormUnbalance' else displacement_tolerance)  # 对位移停止试验明确说明原生力容差参数未用作内部停止条件。
    campaign.write(folder / '计算状态.json', report)  # Publish inspectable launch evidence before the expensive native subprocess.
    source_folder = folder / '执行程序'; source_folder.mkdir(exist_ok=True)  # Preserve orchestration source beside the solver's own model snapshots.
    for path in (Path(__file__), Path(campaign.__file__)): shutil.copy2(path, source_folder / path.name)  # Keep the exact runner and authenticated-input helper used by this execution.
    try:  # Always finalize diagnostic status even when the native solve fails or reaches its budget.
        code = campaign.invoke(command, folder, '原生求解.log', native_budget_seconds); report['exit_code'] = code  # 执行声明的有限原生预算并保留完整日志及真实返回码。
        if code != 0: raise RuntimeError(f'Native diagnostic exited with {code}')  # A failed solver cannot be promoted to a completed history.
        receipt = json.loads((folder / 'case_manifest.json').read_text()); stream = json.loads((folder / 'fields_stream_status.json').read_text())  # Read the native producer's actual completion evidence.
        verify_completion(receipt, stream, 'diagnostic_' + name, steps, internal_substeps, shell_element, native_test)  # 完整历史必须匹配全部已声明数值设置。
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
    parser.add_argument('--shell-element', choices=('ShellNLDKGQ', 'ASDShellQ4'), default=DEFAULT_SHELL)  # 默认共回转壳，原公式作为可明确复现的对照保留。
    parser.add_argument('--native-budget-seconds', type=int, choices=(3600, 15000), default=3600)  # 3600s保持原短诊断；15000s用于160帧延长诊断，不超过生产已声明单次预算。
    parser.add_argument('--native-convergence-test', choices=('NormUnbalance','NormDispIncr'), default=DEFAULT_NATIVE_TEST)  # 默认位移停止，原力范数实验通过显式参数保留。
    parser.add_argument('--native-displacement-tolerance', type=float, default=1e-8)  # 位移模式的严格内部预测阈值，单位为mm/rad混合增量。
    args = parser.parse_args(); execute(args.native_force_tolerance, args.steps, args.internal_substeps, args.shell_element, args.native_budget_seconds, args.native_convergence_test, args.native_displacement_tolerance)  # 运行完整声明的数值试验，不改训练资格。
