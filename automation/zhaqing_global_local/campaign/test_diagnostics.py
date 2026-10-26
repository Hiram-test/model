#!/usr/bin/env python3  # Verify genuine diagnostic completion gates without launching a bridge solve.
import copy, unittest  # Isolate deliberate receipt corruption and assert the actual admission behavior.
import diagnostics  # Exercise the concrete hosted diagnostic runner's integrity checks.
class DiagnosticCompletionTests(unittest.TestCase):  # Protect against incomplete or incorrectly scoped native results being called complete.
    def setUp(self):  # Create a clearly isolated completion-contract fixture.
        self.receipt = {'quality': 'VALID_CONVERGED', 'case_id': 'diagnostic_strict', 'split': 'validation', 'training_eligible': False, 'node_count': 30555, 'time_steps': 32, 'dt_s': .00625}  # Use metadata only, without inventing any finite-element response arrays.
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
if __name__ == '__main__': unittest.main()  # Execute integrity assertions only, with zero trained epochs and no artificial solver fields.
