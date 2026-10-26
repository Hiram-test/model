"""Strict native-FEM dataset contract for the Zhaqing global/local GNO.""" # Failed solves and unverified toy geometry are not training labels.
import hashlib, json # Freeze exact solver files and split definitions before opening response arrays.
from pathlib import Path # Resolve provenance paths relative to the manifest location.
import numpy as np # Read physical full-field data without generating figures.
import torch # Transfer every declared entity to the requested compute device.

def sha256(path): # Identify files by content rather than by an editable filename.
    digest = hashlib.sha256() # Preserve exact identity without reading multigigabyte field archives into RAM.
    with Path(path).open('rb') as handle: # Stream complete artifact bytes in bounded memory.
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''): # Read every byte using an eight-megabyte buffer.
            digest.update(chunk) # Accumulate the complete cryptographic provenance identity.
    return digest.hexdigest() # Return the same SHA256 as an unbounded whole-file read.

class LazyHistory: # Read complete native spatial fields one temporal slice at a time from lossless HDF5.
    def __init__(self, dataset, handle, device, nodes=None): # Retain the owning HDF5 handle for the full training lifetime.
        self.dataset, self.handle, self.device, self.nodes = dataset, handle, device, nodes # Keep only a file-backed array reference, never a full history copy.
        self.shape = (dataset.shape[0], nodes, dataset.shape[-1]) if nodes is not None and dataset.ndim == 2 else dataset.shape # Expose spatially uniform controls through the same full-native shape contract.
        self.ndim = len(self.shape) # Support shape checks without reading large numerical arrays.
    def __len__(self): # Expose the number of actual native time samples.
        return self.shape[0] # Do not decimate the original history.
    def __getitem__(self, key): # Load only the requested temporal frame or contiguous time window.
        value = np.asarray(self.dataset[key]) # HDF5 reads only the selected compressed chunks.
        if self.nodes is not None and self.dataset.ndim == 2: # Expand spatially uniform prescribed inputs after loading their small time slice.
            value = np.broadcast_to(value[..., None, :], value.shape[:-1] + (self.nodes, value.shape[-1])) # Preserve all original physical targets without duplicating uniform data on disk.
        return torch.tensor(value, dtype=torch.float32, device=self.device) # Copy one bounded temporal slice into differentiable numeric storage.

class AffineHistory: # Apply frozen physical normalization lazily without allocating a full normalized history.
    def __init__(self, source, scale, offset=None): # Keep the original time indexing and all physical entities.
        self.source, self.scale, self.offset = source, scale, offset # Store only small channel scales and one known initial field.
        self.shape, self.ndim = source.shape, source.ndim # Preserve the complete native array contract.
    def __len__(self): # Expose every original native output sample.
        return self.shape[0] # No temporal subsampling is introduced by streaming.
    def __getitem__(self, key): # Normalize only the current temporal slice.
        value = self.source[key] # Read exactly the requested original physical data.
        return (value - self.offset) / self.scale if self.offset is not None else value / self.scale # Preserve the reversible physical-unit transformation pointwise.

def validate_manifest(manifest, base, family): # Check all case metadata before reading any withheld field arrays.
    if manifest.get('schema') != 'zhaqing_fullfield_gno_dataset_v1' or manifest.get('family') != family: # Avoid silently mixing global, local or historical block problems.
        raise ValueError('Wrong dataset schema or physical family') # Fail before fitting an incorrectly labeled architecture.
    ids, groups, digests = set(), {}, {} # Detect duplicates at both case and complete-history level.
    for row in manifest['cases']: # Inspect split identities for every case, including withheld cases.
        if row['id'] in ids or row['split'] not in ('train', 'validation', 'test', 'candidate'): # Keep complete case IDs unique and the partitions explicit.
            raise ValueError('Duplicate case ID or unsupported split') # Reject ambiguous partition ownership.
        ids.add(row['id']) # Record this immutable full-history identity.
        group = row['history_group'] # Group all windows, restarts and mesh variants of the same loading realization together.
        if group in groups and groups[group] != row['split']: # A time window of a training history must never become an independent test.
            raise ValueError('Whole-history group leaks across splits') # Refuse temporal or remesh leakage.
        groups[group] = row['split'] # Freeze the owner of this loading realization.
        digest = row.get('fields_sha256', row.get('npz_sha256')) # Use either lossless HDF5 or historical NPZ identity to detect renamed duplicate histories.
        if not digest: # A complete field payload must have a frozen byte identity before selection.
            raise ValueError('Missing native field artifact hash') # Do not accept an untracked streaming store.
        if digest in digests and digests[digest] != row['split']: # A renamed exact payload must not cross a partition boundary.
            raise ValueError('Duplicate field payload leaks across splits') # Reject direct duplicate leakage independently of IDs.
        digests[digest] = row['split'] # Retain provenance without opening the withheld arrays.
    if not manifest.get('field_names') or not manifest.get('relation_names'): # Require declared physical response channels and edge semantics.
        raise ValueError('Field and relation vocabularies are required') # Do not infer mechanics from numeric indices after training.
    if manifest.get('scientific_scope') not in ('research_simulation_with_assumptions', 'drawing_verified_production'): # Preserve the distinction between model-specific research and verified bridge fidelity.
        raise ValueError('Explicit scientific_scope is required') # Never turn assumptions into silently verified geometric facts.
    for key in ('coordinate_scale', 'time_scale'): # Require finite physical reference units rather than arbitrary node-count normalization.
        if not np.isfinite(manifest.get(key, np.nan)) or manifest[key] <= 0: # Reject invalid fixed physical scales before loading field arrays.
            raise ValueError(f'Invalid {key}') # Preserve dimensional consistency in the learned kernel.
    for key, count in (('field_scale_floor', len(manifest['field_names'])), ('relation_reference_measures', len(manifest['relation_names']))): # Declare mesh-independent reference measures for heterogeneous integral domains.
        values = np.asarray(manifest.get(key, []), dtype=float) # Convert explicit unit-aware scale tables for validation.
        if values.shape != (count,) or not np.isfinite(values).all() or np.any(values <= 0): # Every physical field/relation requires its own positive finite reference.
            raise ValueError(f'Invalid {key}') # Do not permit raw millimeter cubed weights to destabilize dimensionless integration.
    return manifest # Return only after all whole-history partitions have passed validation.

def load_case(row, base, manifest, device='cpu'): # Load one explicitly selected partition after metadata filtering.
    required = {'quality': 'VALID_CONVERGED', 'all_native_entities_retained': True, 'solver_exit_code': 0, 'convergence_verified': True} # Model-specific fitting always requires actual native solver convergence and coverage evidence.
    for key, value in required.items(): # Enforce every independent evidence gate rather than trusting one success string.
        if row.get(key) != value: # An exit code alone does not prove equilibrium, full outputs or correct geometry.
            raise ValueError(f"Case {row['id']} fails training gate {key}: {row.get(key)!r}") # Leave provisional meshes and failed contact solves as diagnostics only.
    research = manifest.get('scientific_scope') == 'research_simulation_with_assumptions' # Allow useful model-specific learning without promoting assumptions to real-bridge verification.
    allowed = ('DRAWING_VERIFIED', 'DRAWING_DERIVED_ASSUMPTIONS') if research else ('DRAWING_VERIFIED',) # Keep unverified blocks and arbitrary toy models excluded from both scopes.
    if row.get('geometry_status') not in allowed or (row.get('geometry_status') == 'DRAWING_DERIVED_ASSUMPTIONS' and not row.get('geometry_assumptions')): # Research geometry needs a drawing-derived identity and a nonempty explicit assumption ledger.
        raise ValueError(f"Case {row['id']} fails training gate geometry_status or assumptions") # The report must disclose the exact physical model the network learned.
    field_key = 'fields' if 'fields' in row else 'npz' # Support bounded-memory lossless field stores without misnaming them as NPZ archives.
    for key in (field_key, 'solver_input', 'solver_result', 'convergence_report', 'geometry_evidence'): # Verify native source and audit artifacts before accepting labels.
        path = Path(base) / row[key] # Resolve an explicitly recorded artifact path.
        if sha256(path) != row[key + '_sha256']: # Detect changed inputs, outputs or evidence after split registration.
            raise ValueError(f"Case {row['id']} changed artifact: {key}") # Never silently train against an altered reference.
    streaming = row.get('dataset_format') == 'hdf5' # Long histories must remain file-backed instead of consuming multiple full-case copies in RAM.
    if streaming: # Open only the explicitly selected partition's native field store.
        import h5py # Load the lossless compressed scientific-array reader only for streaming datasets.
        archive = h5py.File(Path(base) / row[field_key], 'r') # Keep the file handle attached to lazy target/control views below.
        data = {key: archive[key] for key in archive.keys()} # Inspect dataset metadata without reading large response histories.
    else: # Retain compatibility with small explicitly recorded NPZ experiments.
        with np.load(Path(base) / row[field_key], allow_pickle=False) as archive: # Avoid executable objects in non-streaming array archives.
            data = {key: archive[key] for key in archive.files} # Load only this selected complete small-case history.
    needed = ('coordinates', 'quadrature', 'static_features', 'controls', 'targets', 'times', 'output_mask', 'initial_state', 'edges', 'edge_types', 'edge_measure', 'native_entity_ids') # Require physical integration weights and native identity explicitly.
    if any(key not in data for key in needed): # Missing contact channels or integration measures must not be filled with fabricated zeros.
        raise ValueError('Missing required native array') # Require the exporter to declare the actual complete field contract.
    n, outputs = data['initial_state'].shape # Determine dimensions from the actual initial physical state.
    t = len(data['times']) # Preserve the complete solver-exported history length.
    checks = [data['coordinates'].shape == (n, 3), data['quadrature'].shape == (n,), data['targets'].shape == (t, n, outputs), data['output_mask'].shape == (n, outputs), len(data['native_entity_ids']) == n, n == row['native_entity_count'], outputs == len(manifest['field_names'])] # Validate full native spatial and temporal coverage.
    if not all(checks) or t < 2 or data['static_features'].ndim != 2 or not np.all(np.diff(data['times']) > 0): # Do not train on truncated fields, repeated times or a single static scalar.
        raise ValueError('Invalid full-field dimensions or time axis') # The trainer needs a complete strictly ordered history.
    if len(set(map(str, data['native_entity_ids']))) != n: # Nodes and integration points must have distinct prefixed identities.
        raise ValueError('Native entity identities are not unique') # Avoid accidental merging of different physical entities.
    for key in needed: # Validate every numerical value before it can enter normalization or gradients.
        if key in ('targets', 'controls') and streaming: # Validate huge histories in bounded temporal chunks.
            for first in range(0, t, 16): # Inspect every native time sample without allocating an entire Boolean history mask.
                if not np.isfinite(data[key][first:first + 16]).all(): # Check actual loaded solver values before they can enter normalization or gradients.
                    raise ValueError(f'Nonfinite native array: {key}') # Invalid native fields remain excluded from the training pool.
        elif key != 'native_entity_ids' and not np.isfinite(np.asarray(data[key])).all(): # Static arrays are small enough to validate in one bounded mesh-sized operation.
            raise ValueError(f'Nonfinite native array: {key}') # Invalid solver fields cannot become useful error samples.
    for key in needed: # Materialize only static mesh metadata, retaining large response and control histories on disk.
        if key not in ('targets', 'controls'): # Every other required array is independent of the total history length except the small time vector.
            data[key] = np.asarray(data[key]) # Keep at most the complete native spatial mesh in memory.
    if np.any(data['quadrature'] <= 0) or np.any(data['edge_measure'] <= 0): # Integral weights must be physically positive before the learned kernel multiplies them.
        raise ValueError('Quadrature measures must be positive') # Zero placeholders and signed FE coefficients are not integration measures.
    edges = data['edges'] # Use explicitly exported relation topology rather than an arbitrary nearest-neighbor graph.
    if not np.issubdtype(edges.dtype, np.integer) or not np.issubdtype(data['edge_types'].dtype, np.integer): # Fractional indices must never be silently truncated into different physical topology.
        raise ValueError('Relation topology must use integer indices') # Preserve exactly the exported native relation identities.
    e = edges.shape[1] if edges.ndim == 2 else -1 # Reject malformed edge tables before indexing them.
    if edges.shape != (2, e) or data['edge_types'].shape != (e,) or data['edge_measure'].shape != (e,) or np.any(edges < 0) or np.any(edges >= n): # Check source/target and physical-measure correspondence.
        raise ValueError('Invalid relation topology') # Keep all relation arrays aligned.
    if e == 0 or np.any(data['edge_types'] < 0) or np.any(data['edge_types'] >= len(manifest['relation_names'])): # Each relation type must refer to the frozen physical vocabulary.
        raise ValueError('Missing or unknown physical relations') # Fail instead of assigning a generic hidden semantic class.
    if not np.all(np.isin(data['output_mask'], [0, 1])) or not np.allclose(data['targets'][0], data['initial_state']): # The initial condition must be an actual known solver state.
        raise ValueError('Invalid observation mask or inconsistent initial state') # Do not initialize from a future or incompatible physical response.
    if np.any(data['output_mask'].sum(0) == 0): # A missing physical channel must not score as perfectly predicted.
        raise ValueError('Every declared field needs observed native entities in every case') # Explicitly omit absent channels from that dataset family instead of inserting zero labels.
    if len(row.get('relation_support', [])) != len(manifest['relation_names']): # A relation must declare a physical support rule independent of FE numbering.
        raise ValueError('Every relation needs an explicit physical support description') # Do not claim remesh consistency for undocumented one-ring adjacency.
    data['edge_measure'] = data['edge_measure'] / np.asarray(manifest['relation_reference_measures'])[data['edge_types']] # Nondimensionalize each physical integration domain using fixed mesh-independent references.
    if data['controls'].ndim == 2 and not streaming: # Permit small spatially uniform input histories without duplicating them on disk.
        data['controls'] = np.broadcast_to(data['controls'][:, None, :], (t, n, data['controls'].shape[-1])).copy() # Expand controls to every retained native entity.
    control_valid = data['controls'].shape[0] == t and (data['controls'].ndim == 2 or data['controls'].shape[1] == n) # Uniform and nodal input functions both retain the full native response mesh.
    if not control_valid or data['static_features'].shape[0] != n: # Verify the input functions align with every native output entity.
        raise ValueError('Input fields do not match the full native mesh') # Prevent accidental graph or field downsampling.
    tensors = {key: torch.as_tensor(data[key], dtype=torch.long if key in ('edges', 'edge_types') else torch.float32, device=device) for key in needed if key not in ('native_entity_ids', 'targets', 'controls')} # Load only complete static native fields onto the compute device.
    for key in ('targets', 'controls'): # Keep time-varying arrays file-backed for long scientific histories.
        tensors[key] = LazyHistory(data[key], archive, device, n if key == 'controls' else None) if streaming else torch.as_tensor(data[key], dtype=torch.float32, device=device) # Decode only one requested temporal slice in the streaming path.
    tensors['streaming'] = streaming # Let normalization and independent evaluation retain bounded-memory behavior.
    tensors['id'], tensors['row'] = row['id'], row # Carry exact case provenance through training and validation.
    return tensors # No spatial pooling, modal projection or time decimation occurs here.

def load_split(path, family, split, device='cpu'): # Select complete histories without opening another partition's labels.
    path = Path(path) # Keep manifest identity independent of the current working directory.
    manifest = validate_manifest(json.loads(path.read_text()), path.parent, family) # Check cross-partition leakage before selecting payloads.
    cases = [load_case(row, path.parent, manifest, device) for row in manifest['cases'] if row['split'] == split] # Read only the explicitly requested full-history partition.
    if not cases: # A trained or tested claim requires actual solver histories in that partition.
        raise ValueError(f'No qualified {family} {split} histories') # Empty datasets cannot produce a completion checkpoint.
    return manifest, cases # Return a schema and the exact retained native tensors.
