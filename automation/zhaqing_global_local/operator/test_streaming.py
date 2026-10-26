"""Streaming and continuation tests on explicit mathematical fixtures only.""" # None of these tests are finite-element training or engineering accuracy evidence.
import argparse, copy, json, shutil, tempfile, unittest # Isolate analytic fixtures and verify real executable state restoration.
from pathlib import Path # Keep all artificial reference files in temporary test directories.
import h5py # Exercise the actual native scientific-storage interface used for complete histories.
import numpy as np # Construct deterministic mathematical input/output functions without plotting.
import torch # Compare exact trained tensor states across uninterrupted and resumed test executions.
from data import LazyHistory, load_split, sha256 # Exercise actual file-backed complete-history loading and provenance gates.
from gno import FullFieldGNO, OperatorConfig # Verify the deployed learned integral operator under nonuniform quadrature duplication.
from test_gno import fixture # Reuse an explicitly mathematical tiny graph, never a bridge reference.
from train import evaluate, fit_normalization, main, normalize, rollout, verify_checkpoint_contract # Exercise actual production streaming, normalization, and checkpoint interfaces.
from adapt_global import adapt # Verify the actual cloud-facing lossless native-field conversion entry point.
class FramesOnly: # Fail if production code requests a whole mathematical history or broad time slice.
    def __init__(self, source): # Preserve the complete native-compatible shape without exposing dense arithmetic.
        self.source, self.shape, self.ndim = source, source.shape, source.ndim # Keep the underlying small test fixture and its dimensions.
    def __len__(self): # Match the complete history's actual time count.
        return self.shape[0] # No sampling or time-window reduction is permitted by this test guard.
    def __getitem__(self, index): # Permit only bounded single-frame access during training normalization and inference.
        if not isinstance(index, int): # Dense whole-history operations violate the intended production-memory contract.
            raise AssertionError('Whole-history access is forbidden') # Detect hidden full-history reads independently of available RAM.
        return self.source[index] # Return the complete original spatial frame.
def write_fixture(root): # Write a tiny analytic three-way experiment solely for software execution tests.
    common = {'schema': 'zhaqing_fullfield_gno_dataset_v1', 'family': 'global', 'scientific_scope': 'research_simulation_with_assumptions', 'field_names': ['analytic_x', 'analytic_y'], 'field_scale_floor': [.01, .01], 'relation_names': ['analytic_measure'], 'relation_reference_measures': [1.], 'coordinate_scale': 1., 'time_scale': 1., 'cases': []} # Explicit names prevent these fixtures from masquerading as real bridge measurements.
    for number, split in enumerate(('train', 'validation', 'test')): # Give each mathematical complete history its own immutable payload and split.
        mesh = fixture(3) # Use a deliberately tiny mathematical graph outside real training namespaces.
        mesh['targets'][0] = mesh['initial_state'] # Make the analytic initial frame exactly consistent with its known initial condition.
        mesh['targets'][1:] *= number + 1 # Avoid identical payload hashes across distinct analytic test partitions.
        path = root / (split + '.h5') # Store one complete actual HDF5 test history per partition.
        with h5py.File(path, 'w') as output: # Exercise lossless file-backed history loading with actual storage bytes.
            for key, value in mesh.items(): # Preserve the complete mathematical fixture's graph, time samples, and output channels.
                output.create_dataset(key, data=(value[:, 0] if key == 'controls' else value).numpy()) # Exercise spatially uniform native controls without storing redundant copies.
            output.create_dataset('native_entity_ids', data=np.arange(3)) # Preserve unique explicit mathematical native entity identities.
        evidence = root / (split + '_evidence.txt') # Keep test provenance separate from any real solver archive.
        evidence.write_text('ANALYTIC_UNIT_FIXTURE_NOT_FEM_OR_BRIDGE_EVIDENCE\n' + split) # State the exact limited scope in the fixture's own bytes.
        row = dict(id=split, history_group=split, split=split, quality='VALID_CONVERGED', geometry_status='DRAWING_DERIVED_ASSUMPTIONS', geometry_assumptions=['ANALYTIC_UNIT_FIXTURE_ONLY_NOT_ENGINEERING_EVIDENCE'], all_native_entities_retained=True, native_entity_count=3, solver_exit_code=0, convergence_verified=True, relation_support=[{'domain': 'analytic_unit_interval'}], dataset_format='hdf5') # Supply schema-valid metadata only to exercise software gates in an isolated temporary fixture.
        for key, artifact in [('fields', path), ('solver_input', evidence), ('solver_result', path), ('convergence_report', evidence), ('geometry_evidence', evidence)]: # Freeze exact bytes required by the actual data loader.
            row[key], row[key + '_sha256'] = artifact.name, sha256(artifact) # Use portable relative paths for relocation tests.
        common['cases'].append(row) # Preserve the independent mathematical history partition.
    manifest = root / 'dataset_manifest.json' # Keep the synthetic software-test experiment fully isolated.
    manifest.write_text(json.dumps(common)) # Freeze exact payload hashes and split definitions before training tests.
    return manifest # Return only the temporary software-fixture manifest.
class StreamingTests(unittest.TestCase): # Verify executable streaming, physical-measure consistency, and exact resumption.
    def setUp(self): # Keep test results deterministic and inexpensive on shared CPU resources.
        torch.set_num_threads(1) # Avoid contention with real native finite-element calculations.
        torch.manual_seed(19) # Reproduce every mathematical fixture initialization.
    def test_frame_only_normalization_and_evaluation_match_dense(self): # Production streaming must agree numerically with an equivalent small dense history.
        mesh = fixture(4) # Use an analytic graph only for exact interface comparison.
        mesh['targets'][0] = mesh['initial_state'] # Preserve a physically consistent analytic initial frame.
        mesh['id'] = 'analytic_only' # Identify the result as a software fixture rather than a bridge case.
        manifest = dict(field_names=['a', 'b'], field_scale_floor=[.01, .01], coordinate_scale=1., time_scale=1.) # Freeze physical-unit normalization scales for this mathematical test.
        streamed = dict(mesh) # Replace only the storage interface, keeping every underlying value identical.
        for key in ('targets', 'controls'): # Guard the two large history fields against hidden dense reads.
            streamed[key] = FramesOnly(mesh[key]) # Raise immediately if implementation attempts any complete-history arithmetic.
        norm = fit_normalization([mesh], manifest) # Establish the exact dense mathematical reference statistics.
        self.assertEqual(norm, fit_normalization([streamed], manifest)) # Statistics must match using single-frame-only access.
        model = FullFieldGNO(OperatorConfig('global', 7, 1, 2, 1, 4, 1, 7, 'separable', 2)) # Use the actual factorized integral architecture with all native fixture entities retained.
        self.assertEqual(evaluate(model, [mesh], norm, manifest), evaluate(model, [streamed], norm, manifest)) # Complete cold inference and every per-field metric must remain numerically identical.
    def test_hdf5_loader_uniform_inputs_and_portable_resume(self): # A moved standalone dataset and an interrupted training process must preserve exact scientific state.
        with tempfile.TemporaryDirectory() as folder: # Keep artificial training and checkpoints out of real bridge result directories.
            root = Path(folder) # Resolve the isolated temporary software-test workspace.
            data = root / 'data' # Place the synthetic portable dataset in its own relocatable subtree.
            data.mkdir() # Create only a temporary test artifact directory.
            manifest = write_fixture(data) # Produce exact HDF5 fixture bytes and independent complete-history partitions.
            _, cases = load_split(manifest, 'global', 'train') # Exercise the actual production file-backed loader.
            self.assertIsInstance(cases[0]['targets'], LazyHistory) # Verify targets remained on disk instead of becoming a dense history tensor.
            self.assertEqual(tuple(cases[0]['controls'][1].shape), (3, 1)) # Uniform native controls must broadcast to every complete physical entity at frame access.
            arguments = dict(command='train', manifest=str(manifest), family='global', epochs=3, width=4, depth=1, edge_chunk=7, window=2, learning_rate=.001, seed=17, threads=1, device='cpu', kernel_mode='separable', kernel_rank=2, checkpoint=None, resume=None, stop_after_epoch=None) # Three test epochs exercise restoration arithmetic only and never substitute for the real 300-epoch request.
            main(argparse.Namespace(**arguments, output=str(root / 'continuous'))) # Complete an uninterrupted small analytic reference execution.
            arguments['stop_after_epoch'] = 1 # Stop after one fully validated analytic epoch without changing its frozen total budget.
            main(argparse.Namespace(**arguments, output=str(root / 'split'))) # Produce an actual complete checkpoint through the production CLI function.
            completion = json.loads((root / 'split/completion.json').read_text()) # Inspect truthful segment-completion semantics.
            self.assertEqual(completion['status'], 'CHECKPOINTED_SEGMENT_TOTAL_BUDGET_INCOMPLETE') # A short segment must not claim the complete total budget finished.
            moved = root / 'relocated' # Simulate transport between independent persistent compute jobs.
            shutil.move(data, moved) # Preserve exact portable payload bytes while changing the absolute workspace path.
            arguments.update(manifest=str(moved / 'dataset_manifest.json'), stop_after_epoch=3, resume=str(root / 'split/progress.pt')) # Resume the same frozen experiment from its relocated relative-path dataset.
            main(argparse.Namespace(**arguments, output=str(root / 'split'))) # Complete the remaining declared analytic epochs with restored model, optimizer, and RNG state.
            expected = torch.load(root / 'continuous/progress.pt', weights_only=False) # Load the actual uninterrupted analytic control checkpoint.
            resumed = torch.load(root / 'split/progress.pt', weights_only=False) # Load the actual production-resumed analytic checkpoint.
            for key, value in expected['model'].items(): # Compare every deployed neural parameter after exact continuation.
                torch.testing.assert_close(value, resumed['model'][key], rtol=0, atol=0) # CPU continuation with the same code and data must be bit-identical.
            self.assertEqual(expected['steps'], resumed['steps']) # Resumption must neither skip nor double-count optimizer updates.
            self.assertEqual(resumed['contract']['epochs'], 3) # Process segment boundaries must not change the frozen total training budget.
            test_args = argparse.Namespace(**{**arguments, 'command': 'evaluate', 'checkpoint': str(root / 'split/progress.pt')}, output=str(root / 'test')) # Evaluate only the independently held-out analytic partition after training selection.
            main(test_args) # Exercise actual streamed independent prediction output through the production evaluation path.
            with h5py.File(root / 'test/test_prediction.h5', 'r') as result: # Inspect the real numeric prediction stream produced by the deployed evaluator.
                self.assertEqual(result.attrs['status'], 'COMPLETE') # Only a full finite four-frame prediction is published as complete.
                self.assertEqual(result['prediction'].shape, (4, 3, 2)) # Retain every original analytic time sample, native node, and field channel.
            bad = copy.deepcopy(resumed) # Test changed inference-code rejection without touching real source files.
            bad['contract']['sources']['gno.py'] = 'changed' # Simulate a different executable architecture under the same checkpoint filename.
            with self.assertRaisesRegex(ValueError, 'source hashes'): # Source drift must fail independent evaluation rather than silently changing semantics.
                verify_checkpoint_contract(bad, moved / 'dataset_manifest.json', 'global') # Check the actual production source-identity guard.
    def test_separable_nonuniform_duplication_preserves_integral(self): # Physical centroid and quadrature must remain unchanged under uneven native sample duplication.
        mesh = fixture(3) # Start with a complete analytic physical domain.
        model = FullFieldGNO(OperatorConfig('local', 2, 1, 2, 1, 4, 1, 7, 'separable', 2)) # Exercise the actual optional factorized integral implementation.
        original = rollout(model, mesh) # Evaluate the original complete analytic discretization.
        old = torch.tensor([0, 0, 1, 2]) # Duplicate only one physical point to expose node-mean centroid bias.
        changed = dict(mesh) # Preserve all original physical values while changing their quadrature representation.
        for key in ('coordinates', 'static_features', 'initial_state', 'output_mask'): # These static functions are indexed by native spatial entity.
            changed[key] = mesh[key][old] # Copy the exact represented physical function at the duplicated point.
        changed['quadrature'] = torch.tensor([1/6, 1/6, 1/3, 1/3]) # Split only the duplicated source's physical measure, keeping the original physical centroid exactly.
        changed['edges'] = torch.stack((torch.arange(4).repeat(4), torch.arange(4).repeat_interleave(4))) # Retain the complete unchanged physical integral support at the new representation.
        changed['edge_types'] = torch.zeros(16, dtype=torch.long) # Preserve the original analytic relation vocabulary.
        changed['edge_measure'] = changed['quadrature'][changed['edges'][0]] # Split duplicate source quadrature consistently on every target integral.
        for key in ('controls', 'targets'): # Preserve every actual temporal input and reference value on the changed representation.
            changed[key] = mesh[key][:, old] # Keep causal history and complete physical response unchanged.
        torch.testing.assert_close(rollout(model, changed), original[:, old], rtol=2.e-5, atol=2.e-6) # Uneven mesh sampling must not move the factor origin or alter the represented physical integral.
    def test_standalone_adapter_is_lossless_and_relocatable(self): # Cloud training must use every exact native supervision value without depending on unavailable raw audit arrays.
        with tempfile.TemporaryDirectory() as folder: # Keep intentionally artificial solver receipts outside real engineering evidence namespaces.
            root, native = Path(folder), Path(folder) / 'native' # Use a separately removable artificial native-case directory.
            native.mkdir() # Create only a mathematical software-test source directory.
            (native / 'prestate').mkdir() # Exercise the real native evidence directory layout.
            (native / 'prestate/equilibrium_summary.json').write_text(json.dumps({'status': 'VALID_CONVERGED', 'scope': 'ANALYTIC_SOFTWARE_FIXTURE_ONLY'})) # State explicitly that this receipt is a unit fixture, never engineering qualification.
            source = native / 'source.inp' # Give the artificial native input a concrete byte identity.
            source.write_text('ANALYTIC_ADAPTER_UNIT_FIXTURE_NOT_FEM\n') # Prevent accidental interpretation as a native bridge input deck.
            raw = native / 'fields.h5' # Exercise the actual complete HDF5 storage format consumed by production conversion.
            expected = np.arange(4 * 3 * 12, dtype=np.float64).reshape(4, 3, 12) / 7. # Use nontrivial double precision that would reveal silent float32 conversion.
            with h5py.File(raw, 'w') as output: # Store a deterministic analytic native-compatible complete history.
                output.attrs.update(status='COMPLETE', expected_frames=4, written_frames=4) # Exercise the real completion consistency gate in isolation.
                arrays = dict(coordinates=np.c_[np.arange(3.), np.zeros((3, 2))], quadrature=np.ones(3), static_features=np.c_[np.ones(3), np.zeros((3, 6)), np.ones(3)], times=np.arange(4.), output_mask=np.ones((3, 12)), initial_state=expected[0], native_entity_ids=np.arange(3), targets=expected, controls=np.zeros((4, 3, 2)), relation_edges=np.array([[0, 1, 1, 2], [1, 0, 2, 1]]), relation_types=np.zeros(4, dtype=np.int64), acceleration=np.ones((4, 3, 6))) # Include an unrelated raw audit array to verify standalone extraction's declared training-only scope.
                for key, value in arrays.items(): # Preserve every analytic native source value under its actual expected field name.
                    output.create_dataset(key, data=value) # Keep original float64 numeric precision.
            receipt = dict(quality='VALID_CONVERGED', case_id='analytic_adapter', history_group='analytic_adapter', split='train', dataset=str(raw), dataset_sha256=sha256(raw), source_input_sha256=sha256(source), storage_format='hdf5', time_steps=3, relation_types=['DECK_PLATES'], output_channels=['analytic_' + str(i) for i in range(12)], control_channels=['external_transverse_wind_m_s', 'external_vertical_wind_m_s'], model_assumptions=['ANALYTIC_UNIT_FIXTURE_ONLY_NOT_ENGINEERING_EVIDENCE']) # Supply explicit analytic-only native metadata solely to test conversion mechanics.
            manifest_path = native / 'case_manifest.json' # Preserve exact original success receipt bytes before conversion.
            manifest_path.write_text(json.dumps(receipt)) # Bind actual source and result hashes for the production adapter.
            converted = adapt([manifest_path], root / 'dataset', source, 'ANALYTIC_SOFTWARE_FIXTURE_ONLY', 'standalone') # Exercise the real bounded-memory cloud extraction CLI function.
            moved = root / 'moved' # Simulate transport to an unrelated compute-job working directory.
            shutil.move(converted.parent, moved) # Preserve dataset bytes while changing absolute location.
            shutil.rmtree(native) # Remove only the temporary artificial source so hidden absolute-path dependencies become test failures.
            _, cases = load_split(moved / 'dataset_manifest.json', 'global', 'train') # Load the relocated standalone result through the actual production provenance gates.
            self.assertEqual(cases[0]['targets'].shape, (4, 3, 12)) # Retain every original native frame, node, and output channel.
            with h5py.File(moved / 'analytic_adapter.h5', 'r') as result: # Independently inspect exact packaged reference precision and values.
                self.assertEqual(result['targets'].dtype, np.dtype('float64')) # Native supervision must not be silently reduced to float32 on disk.
                np.testing.assert_array_equal(result['targets'][...], expected) # All native supervised values must match bit-for-bit after extraction and relocation.
                self.assertNotIn('acceleration', result) # Raw non-supervised audits are deliberately archived separately and never mislabeled as training outputs.
            evidence = json.loads((moved / 'evidence/analytic_adapter/input_evidence.json').read_text()) # Inspect the explicit original-container versus extracted-supervision provenance distinction.
            self.assertEqual(evidence['solver_result_kind'], 'extracted_supervision') # The extracted training array must not masquerade as the complete original native container.
            self.assertTrue(evidence['all_frames_verified_array_equal']) # Every native frame must have passed the actual identity check during conversion.
if __name__ == '__main__': # Execute mathematical software checks only when explicitly requested.
    unittest.main(verbosity=2) # Report exact streaming and continuation tests independently of real bridge training status.
