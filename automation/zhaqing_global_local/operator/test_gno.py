"""Mathematical and execution unit tests; these are not bridge training results.""" # Keep implementation verification separate from engineering validation.
import copy, io, json, tempfile, unittest # Exercise checkpoint identity and data gates without external solver claims.
from pathlib import Path # Isolate temporary unit fixtures from native bridge datasets.
from unittest.mock import patch # Verify partition filtering without opening any withheld payload.
import numpy as np # Construct analytic quadrature fixtures only.
import torch # Check differentiability and exact CPU restoration of the actual architecture.
from acquisition import reconcile_reference, shortlist # Test active-learning error semantics.
from data import load_case, load_split, validate_manifest # Test provenance and full-history guards.
from gno import FullFieldGNO, OperatorConfig, QuadratureKernel # Verify the exact deployed kernel implementation.
from train import rollout, train_epoch, time_weights # Exercise genuine causal iteration and duration-aware optimizer work.
from relations import radius_relation # Verify fixed physical support under real spatial refinement.

def fixture(n=5): # Build a mathematical fixture that is explicitly not a finite-element bridge label.
    coordinates = torch.stack((torch.linspace(0, 1, n), torch.zeros(n), torch.zeros(n)), -1) # Define simple integration coordinates for deterministic unit calculations.
    source = torch.arange(n).repeat(n) # Integrate over every source point for each evaluation target.
    target = torch.arange(n).repeat_interleave(n) # Keep a complete analytic test graph.
    return {'coordinates': coordinates, 'quadrature': torch.ones(n) / n, 'static_features': torch.zeros(n, 2), 'edges': torch.stack((source, target)), 'edge_types': torch.zeros(n * n, dtype=torch.long), 'edge_measure': torch.ones(n * n) / n, 'initial_state': torch.zeros(n, 2), 'targets': torch.ones(4, n, 2), 'controls': torch.ones(4, n, 1), 'times': torch.arange(4).float(), 'output_mask': torch.ones(n, 2)} # Preserve all fixture entities without suggesting production provenance.

class GNOTests(unittest.TestCase): # Test operator mathematics, leakage guards and persistence behavior.
    def setUp(self): # Keep CPU unit tests reproducible and inexpensive.
        torch.set_num_threads(1) # Avoid test latency from oversized thread pools.
        torch.manual_seed(7) # Reproduce every learned-kernel initialization in the suite.
    def model(self): # Allocate the actual production architecture at a small unit-test width.
        return FullFieldGNO(OperatorConfig('local', 2, 1, 2, 1, width=4, depth=2, edge_chunk=7)) # Only latent capacity changes; architecture semantics remain identical.
    def test_nonuniform_quadrature_is_not_degree_average(self): # A constant kernel should integrate by physical measure, not neighbor count.
        kernel = QuadratureKernel(1, 0, 1, 2) # Use a scalar special case of the actual matrix kernel.
        for parameter in kernel.kernel.parameters(): # Force an exactly known continuum kernel for the analytic assertion.
            parameter.data.zero_() # Remove all learned spatial variation in this mathematical test.
        kernel.kernel[-1].bias.data.fill_(1.) # Set K(x,y)=1 exactly.
        answer = kernel.integral(torch.tensor([[2.], [10.]]), torch.zeros(2, 3), torch.empty(2, 0), torch.tensor([[0, 1], [0, 0]]), torch.zeros(2, dtype=torch.long), torch.tensor([.9, .1])) # Integrate with deliberately unequal source cell measures.
        self.assertAlmostEqual(float(answer[0, 0].detach()), 2.8, places=6) # A degree mean would incorrectly produce 6 instead of 2.8.
    def test_quadrature_refinement_converges(self): # Verify midpoint quadrature tends to a known continuum integral.
        kernel = QuadratureKernel(1, 0, 1, 64) # Exercise the actual integral accumulator with no graph downsampling.
        for parameter in kernel.kernel.parameters(): # Replace the learned kernel by an analytic constant only for this test.
            parameter.data.zero_() # Make the quadrature error independent of network approximation error.
        kernel.kernel[-1].bias.data.fill_(1.) # Set the integrand kernel to one.
        errors = [] # Compare two increasingly resolved representations of the same function.
        for n in (8, 32): # Refinement retains all integration points at each resolution.
            x = (torch.arange(n).float() + .5) / n # Use exact midpoint locations on [0,1].
            value = kernel.integral(x.square()[:, None], torch.zeros(n, 3), torch.empty(n, 0), torch.stack((torch.arange(n), torch.zeros(n, dtype=torch.long))), torch.zeros(n, dtype=torch.long), torch.ones(n) / n) # Integrate f(y)=y² using source quadrature weights.
            errors.append(abs(float(value[0, 0].detach()) - 1 / 3)) # Compare directly against the analytic integral.
        self.assertLess(errors[1], errors[0] / 10) # Midpoint quadrature must improve substantially under refinement.
    def test_source_duplication_splits_measure_exactly(self): # Duplicating quadrature samples must not change the represented integral.
        kernel = QuadratureKernel(3, 2, 1, 9) # Check a fully learned matrix kernel, not only a constant special case.
        mesh = fixture(4) # Construct a complete analytic domain with fixed total measure.
        h = torch.randn(4, 3) # Supply a generic latent function.
        original = kernel.integral(h, mesh['coordinates'], mesh['static_features'], mesh['edges'], mesh['edge_types'], mesh['edge_measure']) # Integrate the original quadrature representation.
        duplicated = kernel.integral(h.repeat_interleave(2, 0), mesh['coordinates'].repeat_interleave(2, 0), mesh['static_features'].repeat_interleave(2, 0), torch.stack((mesh['edges'][0].repeat_interleave(2) * 2 + torch.tensor([0, 1]).repeat(16), mesh['edges'][1].repeat_interleave(2) * 2)), mesh['edge_types'].repeat_interleave(2), mesh['edge_measure'].repeat_interleave(2) / 2) # Split each source measure equally among identical point copies.
        torch.testing.assert_close(original, duplicated[::2], rtol=1.e-5, atol=1.e-6) # Equivalent discretizations must give the same integral.
    def test_node_permutation_equivariance(self): # Renumbering native entities must only renumber predicted fields.
        mesh, model = fixture(), self.model() # Preserve the same learned function and physical mesh.
        prediction = rollout(model, mesh) # Evaluate the original entity ordering.
        permutation = torch.tensor([3, 0, 4, 1, 2]) # Define a nontrivial native-ID renumbering.
        inverse = torch.argsort(permutation) # Map old edge indices into the new order.
        changed = dict(mesh) # Reorder entity-indexed arrays consistently.
        for key in ('coordinates', 'quadrature', 'static_features', 'initial_state', 'output_mask'): # These fields use the entity axis first.
            changed[key] = mesh[key][permutation] # Apply the exact same renumbering to physical input functions.
        for key in ('controls', 'targets'): # Complete histories place the entity axis second.
            changed[key] = mesh[key][:, permutation] # Preserve temporal ordering while renumbering space.
        changed['edges'] = inverse[mesh['edges']] # Remap connectivity without changing any physical relation.
        torch.testing.assert_close(rollout(model, changed), prediction[:, permutation], rtol=1.e-5, atol=1.e-6) # Kernel integration must respect arbitrary native numbering.
    def test_translation_invariance_of_relative_kernel(self): # Rigid coordinate translation does not change local kernel descriptors.
        mesh, model = fixture(), self.model() # Keep physical vector channels in the same fixed engineering frame.
        shifted = dict(mesh) # Change only the coordinate origin.
        shifted['coordinates'] = mesh['coordinates'] + torch.tensor([4., -2., 7.]) # Apply a common translation to every entity.
        torch.testing.assert_close(rollout(model, mesh), rollout(model, shifted), rtol=1.e-5, atol=1.e-6) # This does not claim unimplemented rotation equivariance for vector or tensor outputs.
    def test_no_future_target_leakage(self): # Cold prediction must not use reference responses after the initial state.
        mesh, model = fixture(), self.model() # Evaluate a fixed model from known inputs.
        changed = dict(mesh) # Alter only withheld reference fields.
        changed['targets'] = torch.randn_like(mesh['targets']) * 1.e6 # A drastic future-reference change should have no effect on inference.
        torch.testing.assert_close(rollout(model, mesh), rollout(model, changed), rtol=0, atol=0) # Prove targets are absent from the prediction path.
    def test_matrix_kernel_receives_gradients(self): # The explicit integral must participate in optimization.
        mesh, model = fixture(), self.model() # Use a known mathematical target solely for differentiation testing.
        rollout(model, mesh)[-1].square().sum().backward() # Differentiate the complete causal integral composition.
        gradient = model.layers[0].kernel[-1].weight.grad # Inspect an actual matrix-kernel parameter rather than only the output head.
        self.assertTrue(torch.isfinite(gradient).all() and bool(gradient.abs().sum() > 0)) # Reject a disconnected or nonfinite integral implementation.
    def test_exact_checkpoint_optimizer_resume(self): # A closed-epoch restore must reproduce the next actual CPU update.
        mesh, model = fixture(), self.model() # Create a deterministic mathematical execution fixture.
        optimizer = torch.optim.AdamW(model.parameters(), lr=1.e-3) # Exercise the same optimizer family as production training.
        train_epoch(model, optimizer, [mesh, mesh], 2) # Populate model and optimizer state without a bridge-validation claim.
        payload = copy.deepcopy({'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'rng': torch.get_rng_state()}) # Capture a complete closed-epoch state.
        train_epoch(model, optimizer, [mesh, mesh], 2) # Continue the first execution exactly one more epoch.
        expected = copy.deepcopy(model.state_dict()) # Preserve the uninterrupted continuation as the reference.
        resumed = self.model() # Instantiate a fresh prediction function as a restarted process would.
        resumed.load_state_dict(payload['model']) # Restore the last actual iterate.
        next_optimizer = torch.optim.AdamW(resumed.parameters(), lr=1.e-3) # Allocate optimizer tensors before restoring them.
        next_optimizer.load_state_dict(payload['optimizer']) # Restore momentum and variance state.
        torch.set_rng_state(payload['rng']) # Restore whole-history shuffle state after initialization consumed RNG.
        train_epoch(resumed, next_optimizer, [mesh, mesh], 2) # Execute the same continuation after recovery.
        for name, value in expected.items(): # Compare every learned tensor, including matrix kernels and memory.
            torch.testing.assert_close(value, resumed.state_dict()[name], rtol=0, atol=0) # Exact CPU continuation must be bit-identical.
    def test_history_group_leakage_rejected(self): # Windows and mesh variants from one loading realization must share a partition.
        manifest = {'schema': 'zhaqing_fullfield_gno_dataset_v1', 'family': 'global', 'field_names': ['U1'], 'relation_names': ['beam'], 'cases': [{'id': 'a', 'split': 'train', 'history_group': 'wind_seed_8', 'npz_sha256': 'one'}, {'id': 'b', 'split': 'test', 'history_group': 'wind_seed_8', 'npz_sha256': 'two'}]} # Deliberately create temporal-source leakage.
        with self.assertRaisesRegex(ValueError, 'group leaks'): # Require a hard failure before any field payload opens.
            validate_manifest(manifest, '.', 'global') # Validate complete history ownership.
    def test_unverified_geometry_and_failed_solver_rejected(self): # Native-looking arrays do not substitute for geometric and convergence evidence.
        row = {'id': 'not_bridge', 'quality': 'VALID_CONVERGED', 'geometry_status': 'PROVISIONAL', 'all_native_entities_retained': True, 'solver_exit_code': 0, 'convergence_verified': True} # Represent a solver-successful but unverified geometry draft.
        with self.assertRaisesRegex(ValueError, 'geometry_status'): # Geometry fidelity is an independent production training gate.
            load_case(row, '.', {}) # Refuse before any nonexistent array can be opened.
        with self.assertRaisesRegex(ValueError, 'quality'): # A failed FEM solve is not a valid neural training target.
            load_case({'id': 'failed', 'quality': 'FAILED'}, '.', {}) # Preserve failure as a solver diagnostic.
    def test_loader_never_opens_withheld_payload(self): # Metadata validation may inspect split names but must not read test responses while fitting.
        rows = [{'id': 'train', 'split': 'train', 'history_group': 'one', 'npz_sha256': 'a'}, {'id': 'test', 'split': 'test', 'history_group': 'two', 'npz_sha256': 'b'}] # Give withheld and training cases independent identities.
        manifest = {'schema': 'zhaqing_fullfield_gno_dataset_v1', 'family': 'global', 'field_names': ['U1'], 'relation_names': ['beam'], 'cases': rows, 'scientific_scope': 'research_simulation_with_assumptions', 'coordinate_scale': 1., 'time_scale': 1., 'field_scale_floor': [.001], 'relation_reference_measures': [1.]} # Only metadata is needed to test filtering order.
        with tempfile.TemporaryDirectory() as directory: # Isolate the deliberately incomplete unit manifest from production evidence.
            path = Path(directory) / 'manifest.json' # Create a transient mathematical test input.
            path.write_text(json.dumps(manifest)) # Preserve actual JSON partition semantics.
            with patch('data.load_case', side_effect=lambda row, *args: {'id': row['id']}) as loader: # Observe exactly which partition would open its arrays.
                _, loaded = load_split(path, 'global', 'train') # Request only training histories.
                self.assertEqual([row['id'] for row in loaded], ['train']) # Return no withheld field data.
                self.assertEqual(loader.call_count, 1) # The test case's array loader must never be invoked.
    def test_negative_sample_means_real_discrepancy(self): # Distinguish a wrong neural prediction from an invalid FEM reference.
        arrays = np.zeros((3, 4, 2)) # Use a mathematical comparison fixture, not bridge response evidence.
        arguments = (arrays + 2, arrays, np.ones(4), np.ones((4, 2)), np.ones(2), .1, np.array([0., .1, 1.])) # Define a large prediction mismatch on an adaptive physical time grid.
        row = {'id': 'candidate_1', 'split': 'candidate', 'quality': 'VALID_CONVERGED', 'convergence_verified': True} # Represent metadata required after a genuine oracle solve.
        result = reconcile_reference(row, *arguments) # Register the measured discrepancy using the frozen error rule.
        self.assertTrue(result['is_error_negative']) # High finite-element/NN mismatch is the user's intended negative sample.
        row['quality'] = 'FAILED' # Change only the solver validity condition.
        self.assertFalse(reconcile_reference(row, *arguments)['use_as_training_label']) # Failed FEM fields must never become hard-example labels.
        row['split'] = 'test' # Simulate an attempt to mine independent test outcomes for training.
        with self.assertRaisesRegex(ValueError, 'may not relabel'): # Preserve the independent test partition.
            reconcile_reference(row, *arguments) # Reject leakage even when the candidate error is large.
    def test_acquisition_uncertainty_is_not_true_error(self): # Unsolved candidate scores must be explicitly labeled as heuristics.
        ensemble = np.zeros((2, 3, 4, 2)) # Construct an ensemble fixture with three distinct candidate domains.
        ensemble[1, 1] = 4 # Give the second candidate higher predictive disagreement.
        selected = shortlist(ensemble, np.ones(2), np.array([[0.], [.5], [1.]]), np.array([[0.]]), 2) # Request two diverse candidate FEM calculations.
        self.assertEqual(selected[0]['candidate_index'], 1) # The high-uncertainty candidate should be evaluated first.
        self.assertFalse(selected[0]['true_FEM_error_known']) # Do not confuse uncertainty with an already observed reference mismatch.
    def test_fixed_radius_support_preserves_measure_on_refinement(self): # Actual new mesh samples should approximate the same physical integration domain.
        totals = [] # Compare discretizations without merely duplicating existing graph vertices.
        for n in (20, 80): # Refine the same physical line domain by four times.
            points = np.zeros((n, 3)) # Keep a one-dimensional physical domain embedded in three dimensions.
            points[:, 0] = (np.arange(n) + .5) / n # Use uniformly spaced cell midpoint quadrature.
            edges, types, measure = radius_relation(points, np.arange(n), np.arange(n), .21, np.ones(n) / n, 0) # Keep support radius fixed in physical length across the two meshes.
            central = int(np.argmin(abs(points[:, 0] - .5))) # Inspect an interior target away from domain boundaries.
            totals.append(measure[edges[1] == central].sum()) # Integrate a constant function over the same metric neighborhood.
        self.assertLess(abs(totals[1] - .42), abs(totals[0] - .42)) # The integral support should converge toward the fixed physical length2r rather than collapse with mesh size.
    def test_adaptive_time_weights_integrate_duration(self): # Duration weighting must account for unequal native solver intervals.
        weights = time_weights(torch.tensor([0., .1, 1.])) # Use one short interval and one long interval.
        torch.testing.assert_close(weights, torch.tensor([.05, .5, .45])) # Trapezoidal weights must preserve the complete one-second duration.
    def test_nonfinite_acquisition_is_rejected(self): # Invalid predictions must never be promoted to valid negative training samples.
        prediction = np.zeros((3, 4, 2)) # Construct a mathematical comparison fixture only.
        prediction[1, 0, 0] = np.nan # Simulate an invalid autoregressive emission.
        row = {'id': 'candidate_nan', 'split': 'candidate', 'quality': 'VALID_CONVERGED', 'convergence_verified': True} # Keep FEM provenance valid to isolate neural numerical failure.
        with self.assertRaisesRegex(ValueError, 'Nonfinite'): # Invalid neural values must cause an explicit comparison failure.
            reconcile_reference(row, prediction, np.zeros_like(prediction), np.ones(4), np.ones((4, 2)), np.ones(2), .1, np.arange(3)) # Do not convert NaN into a false no-error label.
        with self.assertRaisesRegex(ValueError, 'independent models'): # Candidate uncertainty has the same numerical-validity requirement.
            shortlist(np.full((2, 2, 4, 2), np.nan), np.ones(2), np.ones((2, 1)), np.ones((1, 1)), 1) # Reject a nonfinite uncertainty field before ranking candidates.
    def test_cached_kernel_matches_fresh_integral(self): # Arithmetic reuse must not change the learned matrix integral.
        mesh, model = fixture(), self.model() # Hold the parameter iterate and physical geometry fixed.
        fresh = model(mesh, mesh['controls'][1], mesh['initial_state'], None, 1.) # Evaluate by freshly computing every matrix kernel.
        cached = model(model.prepare_mesh(mesh), mesh['controls'][1], mesh['initial_state'], None, 1.) # Reuse the exact current-iterate geometry-conditioned kernels.
        torch.testing.assert_close(fresh[0], cached[0], rtol=0, atol=0) # Complete physical predictions must remain identical.
        torch.testing.assert_close(fresh[1], cached[1], rtol=0, atol=0) # Causal latent memory must also remain identical.
    def test_long_causal_fixture_remains_finite(self): # Guard numerical recurrence behavior before launching expensive native histories.
        mesh, model = fixture(3), self.model() # Use a tiny mathematical graph solely for a long-memory implementation check.
        mesh['times'] = torch.linspace(0., 20., 801) # Retain800actual sequential updates in this arithmetic stress test.
        mesh['controls'] = torch.ones(801, 3, 1) # Supply a bounded known external input at every time sample.
        with torch.no_grad(): # This is an inference stability test, not a trained engineering result.
            values = rollout(model, mesh) # Autoregress for the full declared horizon without resetting memory.
        self.assertTrue(torch.isfinite(values).all()) # Reject nonfinite latent-memory growth before native bridge evaluation.

if __name__ == '__main__': # Run only mathematical implementation checks in this script.
    unittest.main(verbosity=2) # Print explicit test names and failure evidence.
