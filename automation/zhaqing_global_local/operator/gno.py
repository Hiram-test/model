"""Quadrature graph neural operator; no mesh coarsening or response basis.""" # The architecture implements an integral operator rather than degree-averaged messages.
from dataclasses import asdict, dataclass # Serialize the exact architecture needed to restore a checkpoint.
import torch # Differentiate the learned kernel integral on all original finite-element entities.
from torch import nn # Use ordinary matrix-valued kernels without an external graph library.

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
        chunks = self.kernel_chunks(coordinates, features, edges, edge_types) if cached is None else cached # Reuse only kernels produced by the same current parameter iterate.
        for first in range(0, edges.shape[1], self.edge_chunk): # Visit every edge in bounded temporary chunks.
            last = first + self.edge_chunk # Use the same exact sum regardless of chunk size.
            source, target = edges[:, first:last] # Edges point from integration/source entities to evaluation/target entities.
            matrices = chunks[first // self.edge_chunk] # Keep the complete matrix-valued learned kernel at each quadrature edge.
            messages = torch.bmm(matrices, h[source].unsqueeze(-1)).squeeze(-1) * edge_measure[first:last, None] # Multiply by the declared physical quadrature measure before integration.
            total = total.index_add(0, target, messages) # Sum contributions at every original target without mesh-dependent degree normalization.
        return total # Return the discrete Nyström quadrature of the learned continuum kernel.
    def forward(self, h, coordinates, features, edges, edge_types, edge_measure, cached=None): # Compose local and nonlocal operators at the same physical entities.
        return torch.nn.functional.silu(self.pointwise(h) + self.integral(h, coordinates, features, edges, edge_types, edge_measure, cached)) # Apply the pointwise nonlinearity after the complete integral.

class FullFieldGNO(nn.Module): # A causal recurrent GNO with an explicit spatial integral at every layer.
    architecture = 'quadrature_matrix_kernel_gno_v1' # Never load old mean-message/GRU tensors under this identity.
    def __init__(self, config): # Allocate weights that are independent of the number of finite-element entities.
        super().__init__() # Register the entire learned operator.
        self.config = config # Preserve a reconstructible architecture contract.
        inputs = config.static_features + config.controls + config.outputs + 1 # Append previous physical response and elapsed time as causal inputs.
        self.lift = nn.Sequential(nn.Linear(inputs, config.width), nn.SiLU()) # Lift input functions pointwise without reducing spatial degrees of freedom.
        self.memory_gate = nn.Linear(config.width * 2, config.width) # Retain local path-dependent memory between external time samples.
        self.layers = nn.ModuleList([QuadratureKernel(config.width, config.static_features, config.relations, config.edge_chunk) for _ in range(config.depth)]) # Each layer integrates on all supplied physical graph edges.
        self.global_integrals = nn.ModuleList([nn.Linear(config.width, config.width, bias=False) for _ in range(config.depth)]) # Integrate a constant matrix-valued kernel over the complete physical domain for long-range coupling.
        self.channel_norms = nn.ModuleList([nn.LayerNorm(config.width) for _ in range(config.depth)]) # Stabilize long causal memory in latent channels without spatial averaging or field correction.
        self.readout = nn.Sequential(nn.Linear(config.width, config.width), nn.SiLU(), nn.Linear(config.width, config.outputs)) # Decode every native output channel at every original entity.
    def forward(self, mesh, controls, previous, hidden, dt): # Advance from known inputs and predicted history only.
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
        prepared['kernel_cache'] = [layer.kernel_chunks(mesh['coordinates'], mesh['static_features'], mesh['edges'], mesh['edge_types']) for layer in self.layers] # Share differentiable geometry-only matrix evaluations across the current temporal gradient window.
        return prepared # Never reuse these matrices after changing learned parameters.
    def specification(self): # Export enough metadata to instantiate exactly this prediction function.
        return {'architecture': self.architecture, 'config': asdict(self.config), 'spatial_reduction': False, 'quadrature_degree_normalization': False} # State the actual operator rather than an unverified marketing name.
