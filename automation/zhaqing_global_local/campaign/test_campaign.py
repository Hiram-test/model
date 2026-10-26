#!/usr/bin/env python3  # Verify orchestration integrity only; these fixtures are not finite-element or training evidence.
import copy, json, tempfile, unittest  # Isolate reversible campaign fixture files and explicit gate assertions.
from pathlib import Path  # Keep all artificial integrity fixtures outside native result directories.
from unittest.mock import patch  # Redirect output and launch contracts without changing real scientific artifacts.
import run as campaign  # Test the actual durable orchestration implementation.
class CampaignIntegrityTests(unittest.TestCase):  # Exercise cross-job evidence and interruption behavior independently of solver accuracy.
    def test_duplicate_realization_seed_is_rejected(self):  # Ensure differently named cases cannot silently reuse one loading realization seed.
        value = copy.deepcopy(campaign.config()); value['cases'][1]['seed'] = value['cases'][0]['seed']  # Introduce one deliberate population-integrity defect.
        with tempfile.TemporaryDirectory() as name:  # Keep the malformed contract outside the real checked-in campaign.
            folder = Path(name); (folder / 'experiment.json').write_text(json.dumps(value))  # Persist only the synthetic invalid contract.
            with patch.object(campaign, 'HERE', folder):  # Restrict the mutation to this test's configuration lookup.
                with self.assertRaisesRegex(ValueError, 'seed reused'): campaign.config()  # Require the actual campaign gate to reject the repeated realization.
    def test_portable_fields_manifest_preserves_bytes(self):  # Verify complete per-case artifact references remain valid after hosted-job relocation.
        setup = campaign.config()  # Reuse the true frozen population schema while making clearly artificial artifact bytes.
        with tempfile.TemporaryDirectory() as name:  # Avoid creating any apparent real bridge reference fields.
            output = Path(name); dataset = output / 'datasets'  # Reproduce the artifact downloader's deterministic directory convention.
            for case in setup['cases']:  # Cover all ten declared complete-history partitions in the orchestration fixture.
                folder = dataset / ('global-dataset-' + case['id']); folder.mkdir(parents=True)  # Retain each case as a separate artifact namespace.
                field = folder / 'synthetic_integrity_fixture.bin'; field.write_bytes(b'ORCHESTRATION_FIXTURE_NOT_FEM')  # Use unmistakably nonphysical bytes for path and hash tests only.
                row = {'id': case['id'], 'split': case['split']}  # Preserve only the identity fields inspected by the joiner.
                for key in ('fields', 'solver_input', 'solver_result', 'convergence_report', 'geometry_evidence'): row.update({key: field.name, key + '_sha256': campaign.digest(field)})  # Exercise all actual portable evidence-reference keys.
                campaign.write(folder / 'dataset_manifest.json', {'schema': 'ORCHESTRATION_FIXTURE_NOT_FEM', 'cases': [row]})  # This synthetic schema cannot enter the real data loader.
                campaign.write(folder / 'campaign_case.json', {'experiment_sha256': campaign.digest(campaign.HERE / 'experiment.json'), 'time_steps': setup['steps'], 'dt_s': setup['dt_s'], 'native_nodes': 30000})  # Provide artificial metadata solely to test the orchestration integrity branches.
            with patch.object(campaign, 'OUT', output): campaign.assemble()  # Execute the real relative-path join against isolated fixture files.
            result = json.loads((dataset / 'dataset_manifest.json').read_text())  # Inspect the actual joined contract produced by the tested function.
            self.assertEqual(len(result['cases']), 10)  # No complete-history fixture may be silently dropped.
            for row in result['cases']:  # Verify every declared physical artifact key receives its portable case prefix.
                for key in ('fields', 'solver_input', 'solver_result', 'convergence_report', 'geometry_evidence'): self.assertEqual(campaign.digest(dataset / row[key]), row[key + '_sha256'])  # Relocation changes references only and preserves all exact bytes.
    def test_changed_numerical_artifact_is_rejected(self):  # Detect corrupted native field bytes during explicit receipt relocation.
        with tempfile.TemporaryDirectory() as name:  # Keep malformed native-looking metadata outside every actual solver result.
            folder = Path(name); field = folder / 'fields.h5'; field.write_bytes(b'ORCHESTRATION_FIXTURE_NOT_HDF5')  # The test checks immutable content identity without pretending this is a solver field.
            receipt = folder / 'case_manifest.json'; campaign.write(receipt, {'dataset': '/old-run/fields.h5', 'dataset_sha256': '0' * 64})  # Deliberately mismatch the actual artifact hash.
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): campaign.relocate_receipt(receipt)  # Reject substituted bytes before adaptation or training.
    def test_training_launch_requires_real_run_identity(self):  # Prevent a training-only launch from guessing a prior reference workflow.
        with tempfile.TemporaryDirectory() as name:  # Isolate launch-routing validation from the live workflow configuration.
            folder = Path(name); campaign.write(folder / 'launch.json', {'mode': 'training', 'reference_run_id': None})  # Supply the exact missing-reference defect this gate must catch.
            with patch.object(campaign, 'HERE', folder):  # Override only the launch file location for this fixture.
                with self.assertRaisesRegex(ValueError, 'concrete completed reference'): campaign.launch()  # Require an observed concrete reference run before cross-job data reuse.
    def test_validation_route_is_explicit_and_nonproduction(self):  # Check the actual committed default does not select known-unqualified native jobs.
        routing = json.loads((campaign.HERE / 'launch.json').read_text())  # Read the real launch contract rather than reproducing its intended value in a fixture.
        self.assertEqual(routing['mode'], 'validation')  # Default source pushes must execute only bounded implementation checks while current blockers persist.
        contract = campaign.workflow_contract()  # Inspect all actual published workflow gates and continuation boundaries.
        self.assertTrue(contract['native_and_training_jobs_disabled_in_validation'])  # Every native and learning stage must be explicitly excluded from validation mode.
        self.assertEqual(contract['continuation_segments'], 75)  # Preserve all 300 planned epochs rather than silently shortening the experiment.
    def test_known_unqualified_reference_execution_is_rejected(self):  # Prevent a mode-only edit from starting the known-over-budget native matrix.
        with tempfile.TemporaryDirectory() as name:  # Isolate deliberate invalid routing from the committed safe default.
            folder = Path(name); campaign.write(folder / 'launch.json', {'mode': 'references', 'reference_run_id': None}); campaign.write(folder / 'readiness.json', {'reference_execution_qualified': False})  # Reproduce the unresolved physical/runtime execution state explicitly.
            with patch.object(campaign, 'HERE', folder):  # Read only the synthetic readiness and routing for this failure assertion.
                with self.assertRaisesRegex(ValueError, 'Reference execution remains blocked'): campaign.launch()  # Reject before publishing any routing output or launching a solver.
    def test_workflow_rejects_unguarded_training_segment(self):  # Inspect every segment instead of relying on an implicit predecessor skip.
        with tempfile.TemporaryDirectory() as name:  # Keep the deliberately unsafe workflow fixture outside the real execution tree.
            root = Path(name); folder = root / '.github/workflows'; folder.mkdir(parents=True)  # Reproduce only the workflow location needed by the actual validator.
            source = (campaign.ROOT / '.github/workflows/zhaqing-global-local-training.yml').read_text(); source = source.replace("    if: needs.prepare.outputs.mode == 'training' # Keep optimization", "    if: always() # Keep optimization", 1)  # Deliberately introduce one expensive stage that could ignore routing.
            (folder / 'zhaqing-global-local-training.yml').write_text(source)  # Store clearly isolated workflow text for the negative regression test.
            with patch.object(campaign, 'ROOT', root):  # Point only the workflow reader at this invalid fixture.
                with self.assertRaisesRegex(ValueError, 'Training continuation routing'): campaign.workflow_contract()  # Reject one unguarded stage even when the other 74 remain correct.
if __name__ == '__main__': unittest.main()  # Run genuine orchestration tests without launching any native solver or optimization.
