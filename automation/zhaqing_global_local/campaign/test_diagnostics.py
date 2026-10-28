#!/usr/bin/env python3  # Verify genuine diagnostic completion gates without launching a bridge solve.
import copy, unittest  # Isolate deliberate receipt corruption and assert the actual admission behavior.
import diagnostics  # Exercise the concrete hosted diagnostic runner's integrity checks.
class DiagnosticCompletionTests(unittest.TestCase):  # Protect against incomplete or incorrectly scoped native results being called complete.
    def setUp(self):  # Create a clearly isolated completion-contract fixture.
        self.receipt = {'quality': 'VALID_CONVERGED', 'case_id': 'diagnostic_strict', 'split': 'validation', 'training_eligible': False, 'node_count': 30555, 'time_steps': 32, 'dt_s': .00625, 'internal_substeps': 2}  # Use metadata only, without inventing any finite-element response arrays.
        self.stream = {'status': 'COMPLETE', 'written_frames': 33, 'last_time_s': .2}  # Describe the exact required frame/time contract for an isolated unit test.
    def test_complete_diagnostic_contract(self):  # Accept only the declared complete short diagnostic schema.
        diagnostics.verify_completion(self.receipt, self.stream, 'diagnostic_strict', 32)  # Exercise the real metadata admission gate.
    def test_partial_native_stream_is_rejected(self):  # Detect an interrupted history even if its manifest claims native convergence.
        stream = copy.deepcopy(self.stream); stream['written_frames'] = 14; stream['last_time_s'] = .08125  # Reproduce the real earlier incomplete-history shape in metadata only.
        with self.assertRaisesRegex(ValueError, 'incomplete'): diagnostics.verify_completion(self.receipt, stream, 'diagnostic_strict', 32)  # Require all requested accepted steps rather than a process-success guess.
    def test_training_eligible_result_is_rejected(self):  # Keep controlled solver diagnoses outside the complete training population.
        receipt = copy.deepcopy(self.receipt); receipt['training_eligible'] = True  # Deliberately violate the diagnostic-only producer contract.
        with self.assertRaisesRegex(ValueError, 'identity or acceptance'): diagnostics.verify_completion(receipt, self.stream, 'diagnostic_strict', 32)  # Refuse a differently scoped artifact even when its frame count matches.
    def test_substituted_smaller_mesh_is_rejected(self):  # Prevent the old small bridge from satisfying a full detailed-mesh diagnostic.
        receipt = copy.deepcopy(self.receipt); receipt['node_count'] = 589  # Reproduce the unrelated older static model's node count as an invalid metadata fixture.
        with self.assertRaisesRegex(ValueError, 'mesh or requested history'): diagnostics.verify_completion(receipt, self.stream, 'diagnostic_strict', 32)  # Preserve the user-requested actual mesh population.
    def test_refined_substeps_require_explicit_matching_request(self):  # 更细内部网格必须与运行前请求相同，不能事后改变原诊断契约。
        receipt = copy.deepcopy(self.receipt); receipt['internal_substeps'] = 4  # 构造完整32帧但每帧4子步的独立元数据夹具，不生成物理结果。
        with self.assertRaisesRegex(ValueError, 'mesh or requested history'): diagnostics.verify_completion(receipt, self.stream, 'diagnostic_strict', 32)  # 默认2子步运行拒绝未经声明的4子步结果。
        diagnostics.verify_completion(receipt, self.stream, 'diagnostic_strict', 32, 4)  # 只有明确请求4子步且保持全32帧/0.2s时通过诊断完整性检查。
    def test_refinement_preserves_export_horizon_and_validation_split(self):  # 防止内部加密同时缩短声明时程或把诊断结果变成训练样本。
        command = diagnostics.make_command(.01, 'isolated-diagnostic', 32, 4)  # 原0.01容差配4子步，目录仅用于命令构造，不运行全桥。
        for option, expected in (('--steps', '32'), ('--dt', '.00625'), ('--internal-substeps', '4'), ('--split', 'validation')):  # 固定完整帧数、输出间隔、显式加密与非训练分区。
            self.assertEqual(command[command.index(option) + 1], expected)  # 验证送入真实求解器的参数与完整诊断契约一致。
    def test_unplanned_internal_grid_is_rejected(self):  # 禁止任意内部离散值悄悄进入已声明的2/4/8子步对照。
        with self.assertRaisesRegex(ValueError, 'Unsupported'): diagnostics.make_command(.01, 'isolated-diagnostic', 32, 3)  # 3子步不在预先声明的减半序列，命令构造必须失败。
if __name__ == '__main__': unittest.main()  # Execute integrity assertions only, with zero trained epochs and no artificial solver fields.
