"""Quadrature graph neural operator; no mesh coarsening or response basis.""" # The architecture implements an integral operator rather than degree-averaged messages.
from dataclasses import asdict, dataclass # Serialize the exact architecture needed to restore a checkpoint.
import torch # Differentiate the learned kernel integral on all original finite-element entities.
from torch import nn # Use ordinary matrix-valued kernels without an external graph library.
from torch.utils.checkpoint import checkpoint # Recompute matrix-kernel chunks during backpropagation instead of retaining every edge matrix.

@dataclass(frozen=True) # Freeze architecture dimensions before training or test selection.
class OperatorConfig: # Keep separate global and local checkpoint identities.
    family: str # Record which physical problem supplies this operator's training labels.
    static_features: int # Count material, geometry, boundary and entity-semantic input channels.
    controls: int # Count nodal time-dependent load or boundary input channels.
    outputs: int # Count full-field response channels at every native entity.
    relations: int # Count separately defined volume, surface and structural relation measures.
    width: int = 24 # Change latent channels without changing the spatial discretization.
    depth: int = 3 # Compose several local kernel integrals to propagate physical information.
    edge_chunk: int = 4096 # Bound temporary kernel matrices while retaining every declared edge.
    kernel_mode: str = 'matrix' # Keep the original full edge matrix kernel as the explicit baseline.
    kernel_rank: int = 4 # Declare the channel rank of the optional separable integral kernel.

class SeparableQuadratureKernel(nn.Module): # Approximate K_r(x,y)=A_r(x)B_r(y) on the exact original physical relation supports.
    def __init__(self, width, features, relations, rank): # Factor only the learned kernel, never the finite-element displacement field or mesh.
        super().__init__() # Register every learned source and target factor.
        self.width, self.rank, self.relations = width, rank, relations # Freeze the disclosed kernel approximation dimensions.
        self.relation = nn.Embedding(relations, 8) # Retain the exact semantic relation vocabulary of the matrix-kernel baseline.
        self.source_factor = nn.Sequential(nn.Linear(features + 3 + 8, width), nn.SiLU(), nn.Linear(width, rank * width)) # Map each physical source location to a complete rank-by-channel matrix.
        self.target_factor = nn.Sequential(nn.Linear(features + 3 + 8, width), nn.SiLU(), nn.Linear(width, width * rank)) # Map every actual target location to a channel-by-rank matrix.
        self.pointwise = nn.Linear(width, width) # Preserve one independent full latent state at every native entity.
    def integration_domains(self, coordinates, features, edges, edge_types, edge_measure): # Build only parameter-independent original topology, physical quadrature, and input descriptors.
        centered = coordinates # The model supplies coordinates centered by physical quadrature, never a node-count mean.
        domains = [] # Share immutable sparse relation structure across layers and optimizer updates.
        for relation in range(self.relations): # Different physical relation domains retain independent learned semantic embeddings.
            selected = edge_types == relation # Preserve the entire declared physical support for this relation.
            if not bool(selected.any()): # Some meshes legitimately lack one vocabulary member.
                continue # Do not fabricate a relation or an artificial sample for an absent physical domain.
            source, source_inverse = torch.unique(edges[0, selected], sorted=True, return_inverse=True) # Retain every source entity while mapping its repeated edge appearances to a sparse integral index.
            target, target_inverse = torch.unique(edges[1, selected], sorted=True, return_inverse=True) # Keep every actual evaluation entity and all its incoming quadrature terms.
            source_base = torch.cat((centered[source], features[source]), -1) # Preserve immutable physical source descriptors without learned relation embeddings.
            target_base = torch.cat((centered[target], features[target]), -1) # Preserve immutable physical target descriptors without any reference-response input.
            adjacency = torch.sparse_coo_tensor(torch.stack((target_inverse, source_inverse)), edge_measure[selected], (len(target), len(source)), device=coordinates.device, check_invariants=True).coalesce() # Validate and retain every exact physical edge weight once, summing duplicate quadrature contributions only.
            domains.append((relation, source, target, source_base, target_base, adjacency)) # Cache only parameter-independent O(E+NF) geometry and sparse quadrature structure.
        return domains # No model parameter or predicted state is stored in this persistent mesh cache.
    def kernel_chunks(self, coordinates, features, edges, edge_types, edge_measure, domains=None): # Recompute learned factors at the current parameter iterate while reusing immutable physical topology.
        domains = self.integration_domains(coordinates, features, edges, edge_types, edge_measure) if domains is None else domains # Direct callers retain the same exact physical integral semantics.
        chunks = [] # Store only current-iterate learned source and target factors for this temporal update window.
        for relation, source, target, source_base, target_base, adjacency in domains: # Every actual original relation and quadrature edge remains present.
            semantic = self.relation.weight[relation] # Refresh the actual learned relation embedding after each optimizer update.
            source_descriptor = torch.cat((source_base, semantic.expand(len(source), -1)), -1) # Append only current learned semantics to immutable physical source descriptors.
            target_descriptor = torch.cat((target_base, semantic.expand(len(target), -1)), -1) # Preserve actual complete target coordinates and known static fields.
            left = self.target_factor(target_descriptor).reshape(-1, self.width, self.rank) # Refresh every current-iterate learned target factor.
            right = self.source_factor(source_descriptor).reshape(-1, self.rank, self.width) # Refresh every current-iterate learned source factor.
            chunks.append((source, target, left, right, adjacency)) # Retain O(NWr+E) exact current factors without recomputing fixed native topology.
        return chunks # All original nodes, relations, time steps and response channels remain present.
    def integral(self, h, coordinates, features, edges, edge_types, edge_measure, cached=None): # Evaluate the separable Nyström integral on every physical relation edge.
        chunks = self.kernel_chunks(coordinates, features, edges, edge_types, edge_measure) if cached is None else cached # Reuse only factors formed at the current parameter iterate.
        total = torch.zeros_like(h) # Preserve every native evaluation entity independently.
        for source, target, left, right, adjacency in chunks: # Integrate each semantic relation on its original support.
            projected = torch.bmm(right, h[source, :, None]).squeeze(-1) # Apply the learned source kernel factor without reducing stored physical response degrees.
            integrated = torch.sparse.mm(adjacency, projected) # Sum every physical quadrature edge exactly using a sparse matrix product.
            messages = torch.bmm(left, integrated[:, :, None]).squeeze(-1) # Apply the learned target factor to recover every full latent channel.
            total = total.index_add(0, target, messages) # Combine semantic integrals at all original target entities.
        return total # This is a finite-rank kernel approximation, with no finite-element or modal reduction.
    def forward(self, h, coordinates, features, edges, edge_types, edge_measure, cached=None): # Use the same nonlinear integral-layer contract as the full matrix baseline.
        return torch.nn.functional.silu(self.pointwise(h) + self.integral(h, coordinates, features, edges, edge_types, edge_measure, cached)) # Preserve pointwise nonlinear response capacity at every native entity.

class QuadratureKernel(nn.Module): # Approximate integral K(x,y,a(x),a(y),r) v(y) dmu_r(y).
    def __init__(self, width, features, relations, edge_chunk=4096): # Receive dimensions independently of mesh node count.
        super().__init__() # Register all learned kernel parameters with PyTorch.
        self.width, self.edge_chunk = width, edge_chunk # Chunking changes execution memory only.
        self.relation = nn.Embedding(relations, 8) # Encode physical relation semantics using a declared vocabulary.
        self.kernel = nn.Sequential(nn.Linear(4 + 2 * features + 8, width), nn.SiLU(), nn.Linear(width, width * width)) # Produce the complete channel-to-channel matrix at each quadrature edge.
        self.pointwise = nn.Linear(width, width) # Represent the local Wv term of a neural-operator layer.
    def kernel_chunks(self, coordinates, features, edges, edge_types): # Evaluate geometry-conditioned kernels once per optimizer window or complete inference history.
        chunks = [] # Preserve exact kernels for every edge without recomputing unchanged geometry at each time step.
        for first in range(0, edges.shape[1], self.edge_chunk): # Bound temporary descriptor allocations while retaining the complete graph.
            last = first + self.edge_chunk # Keep cache boundaries identical to integration boundaries.
            source, target = edges[:, first:last] # Retrieve the actual physical integration pair indices.
            delta = coordinates[source] - coordinates[target] # Relative geometry remains fixed over this reference-domain operator evaluation.
            descriptor = torch.cat((delta, delta.square().sum(-1, keepdim=True).sqrt(), features[source], features[target], self.relation(edge_types[first:last])), dim=-1) # Reuse only known geometric/material inputs, not response targets.
            chunks.append(self.kernel(descriptor).reshape(-1, self.width, self.width)) # Retain differentiable matrix kernels until the current optimizer update completes.
        return chunks # Caching changes arithmetic reuse only, not the learned integral or spatial resolution.
    def integral(self, h, coordinates, features, edges, edge_types, edge_measure, cached=None): # Accumulate source quadrature measures without dividing by graph degree.
        total = torch.zeros_like(h) # Preserve one full latent vector for every original entity.
        def messages_for_chunk(state, positions, semantics, source, target, types, measure): # Keep the differentiable matrix allocation bounded by one complete edge chunk.
            delta = positions[source] - positions[target] # Use exact physical pair geometry with translation-independent descriptors.
            descriptor = torch.cat((delta, delta.square().sum(-1, keepdim=True).sqrt(), semantics[source], semantics[target], self.relation(types)), dim=-1) # Recompute known geometry descriptors during checkpointed backward when needed.
            matrices = self.kernel(descriptor).reshape(-1, self.width, self.width) # Evaluate every complete channel-to-channel matrix in this chunk.
            return torch.bmm(matrices, state[source].unsqueeze(-1)).squeeze(-1) * measure[:, None] # Integrate the unchanged native source values using their physical measures.
        for first in range(0, edges.shape[1], self.edge_chunk): # Visit every edge in bounded temporary chunks.
            last = first + self.edge_chunk # Use the same exact sum regardless of chunk size.
            source, target = edges[:, first:last] # Edges point from integration/source entities to evaluation/target entities.
            if cached is not None: # Permit explicitly supplied small diagnostic caches without using them in production preparation.
                matrices = cached[first // self.edge_chunk] # Read only the caller's declared exact current-iterate matrix cache.
                messages = torch.bmm(matrices, h[source].unsqueeze(-1)).squeeze(-1) * edge_measure[first:last, None] # Keep diagnostic arithmetic identical to uncached integration.
            elif torch.is_grad_enabled(): # Bound saved backward activations while retaining every physical edge and response degree.
                messages = checkpoint(messages_for_chunk, h, coordinates, features, source, target, edge_types[first:last], edge_measure[first:last], use_reentrant=False) # Recompute per-chunk matrices during differentiation instead of caching O(EW²) tensors.
            else: # Independent inference never needs to save matrix-kernel activations.
                messages = messages_for_chunk(h, coordinates, features, source, target, edge_types[first:last], edge_measure[first:last]) # Allocate and release one complete edge chunk at a time.
            total = total.index_add(0, target, messages) # Sum contributions at every original target without mesh-dependent degree normalization.
        return total # Return the discrete Nyström quadrature of the learned continuum kernel.
    def forward(self, h, coordinates, features, edges, edge_types, edge_measure, cached=None): # Compose local and nonlocal operators at the same physical entities.
        return torch.nn.functional.silu(self.pointwise(h) + self.integral(h, coordinates, features, edges, edge_types, edge_measure, cached)) # Apply the pointwise nonlinearity after the complete integral.

class FullFieldGNO(nn.Module): # A causal recurrent GNO with an explicit spatial integral at every layer.
    architecture = 'quadrature_matrix_kernel_gno_v1' # Never load old mean-message/GRU tensors under this identity.
    def __init__(self, config): # Allocate weights that are independent of the number of finite-element entities.
        super().__init__() # Register the entire learned operator.
        self.config = config # Preserve a reconstructible architecture contract.
        if config.kernel_mode not in ('matrix', 'separable') or config.kernel_rank < 1: # Reject unsupported or degenerate learned-kernel approximations.
            raise ValueError('Invalid kernel_mode or kernel_rank') # Never silently reinterpret a checkpoint architecture.
        self.architecture = 'quadrature_matrix_kernel_gno_v1' if config.kernel_mode == 'matrix' else 'quadrature_separable_kernel_gno_v1' # Give the optional accelerated operator its own explicit reconstructible identity.
        inputs = config.static_features + config.controls + config.outputs + 1 # Append previous physical response and elapsed time as causal inputs.
        self.lift = nn.Sequential(nn.Linear(inputs, config.width), nn.SiLU()) # Lift input functions pointwise without reducing spatial degrees of freedom.
        self.memory_gate = nn.Linear(config.width * 2, config.width) # Retain local path-dependent memory between external time samples.
        self.layers = nn.ModuleList([QuadratureKernel(config.width, config.static_features, config.relations, config.edge_chunk) if config.kernel_mode == 'matrix' else SeparableQuadratureKernel(config.width, config.static_features, config.relations, config.kernel_rank) for _ in range(config.depth)]) # Both alternatives integrate on every supplied physical graph edge.
        self.global_integrals = nn.ModuleList([nn.Linear(config.width, config.width, bias=False) for _ in range(config.depth)]) # Integrate a constant matrix-valued kernel over the complete physical domain for long-range coupling.
        self.channel_norms = nn.ModuleList([nn.LayerNorm(config.width) for _ in range(config.depth)]) # Stabilize long causal memory in latent channels without spatial averaging or field correction.
        self.readout = nn.Sequential(nn.Linear(config.width, config.width), nn.SiLU(), nn.Linear(config.width, config.outputs)) # Decode every native output channel at every original entity.
    def forward(self, mesh, controls, previous, hidden, dt): # Advance from known inputs and predicted history only.
        if self.config.kernel_mode == 'separable' and 'kernel_cache' not in mesh: # Direct inference must use the same physical-centroid factor descriptors as prepared production integration.
            mesh = self.prepare_mesh(mesh) # Prepare current-iterate compact factors without relying on node-count-dependent coordinate centering.
        elapsed = previous.new_full((previous.shape[0], 1), float(dt)) # Supply the actual sampling interval rather than assuming a fixed time grid.
        lifted = self.lift(torch.cat((mesh['static_features'], controls, previous, elapsed), dim=-1)) # No future reference state enters this input function.
        hidden = torch.zeros_like(lifted) if hidden is None else hidden # Start every independent history from empty learned memory.
        gate = torch.sigmoid(self.memory_gate(torch.cat((lifted, hidden), dim=-1))) # Use a declared causal memory extension of GNO, not a renamed standard architecture.
        state = gate * hidden + (1 - gate) * lifted # Carry nonlinear contact or plastic loading-path information locally.
        measure = mesh['quadrature'] / mesh['quadrature'].sum() # Define the full-domain probability measure from physical quadrature, never from node count.
        for index, (layer, global_integral) in enumerate(zip(self.layers, self.global_integrals)): # Preserve every native entity through local and complete-domain integral layers.
            global_state = global_integral((state * measure[:, None]).sum(0)) # Evaluate the constant-kernel all-domain integral exactly in linear work, with every source entity retained.
            cache = mesh.get('kernel_cache', [None] * self.config.depth)[index] # Reuse the exact current iterate's static geometric kernels when available.
            state = self.channel_norms[index](state + layer(state, mesh['coordinates'], mesh['static_features'], mesh['edges'], mesh['edge_types'], mesh['edge_measure'], cache) + global_state) # Normalize only latent channels at each original entity to keep long autoregression numerically bounded.
        return self.readout(state) * mesh['output_mask'], state # Keep structurally nonexistent entity channels zero while emitting every declared observable field and causal latent memory.
    def prepare_mesh(self, mesh): # Refresh cached kernels after every parameter update while retaining all native graph entities.
        prepared = dict(mesh) # Keep the caller's immutable mesh and provenance fields intact.
        if self.config.kernel_mode == 'separable': # Separable factors need a common mesh-independent physical coordinate origin.
            centroid = (mesh['coordinates'] * mesh['quadrature'][:, None]).sum(0) / mesh['quadrature'].sum() # Use the declared physical quadrature rather than giving dense mesh regions extra influence.
            prepared['coordinates'] = mesh['coordinates'] - centroid # Preserve common-translation invariance under consistent physical measure refinement.
            signature = tuple((name, mesh[name].data_ptr(), mesh[name]._version, tuple(mesh[name].shape)) for name in ('coordinates', 'quadrature', 'static_features', 'edges', 'edge_types', 'edge_measure')) # Invalidate static domains on tensor replacement, renumbering, device transfer, or in-place physical input changes.
            cached = mesh.get('_separable_domain_cache') # Reuse only immutable geometry and quadrature metadata from this exact native input function.
            if cached is None or cached[0] != signature: # Every changed physical mesh must rebuild its exact native topology and physical-centroid descriptors.
                domains = self.layers[0].integration_domains(prepared['coordinates'], mesh['static_features'], mesh['edges'], mesh['edge_types'], mesh['edge_measure']) # Compute fixed native sparse supports once for all integral layers and future optimizer windows.
                mesh['_separable_domain_cache'] = (signature, domains) # Cache no learned parameter, target field, or future response value.
            prepared['kernel_cache'] = [layer.kernel_chunks(prepared['coordinates'], mesh['static_features'], mesh['edges'], mesh['edge_types'], mesh['edge_measure'], mesh['_separable_domain_cache'][1]) for layer in self.layers] # Refresh all differentiable factors after every parameter update while sharing exact unchanged geometry.
        else: # The matrix-kernel baseline retains complete channel matrices computed in bounded edge chunks.
            prepared['kernel_cache'] = [None] * self.config.depth # Avoid a persistent O(EW²) cache in the full learned matrix baseline.
        return prepared # Never reuse these matrices after changing learned parameters.
    def specification(self): # Export enough metadata to instantiate exactly this prediction function.
        return {'architecture': self.architecture, 'config': asdict(self.config), 'spatial_reduction': False, 'quadrature_degree_normalization': False} # State the actual operator rather than an unverified marketing name.
