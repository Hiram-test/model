#!/usr/bin/env python3  # Train a source-topology graph surrogate only from qualified native FEM responses.
import argparse  # Parse explicit data, training-budget, and output arguments.
import copy  # Retain the best validation checkpoint without mutating optimizer state.
import hashlib  # Bind model and training records to immutable input bytes.
import importlib.util  # Reuse the original model and mechanics parsers without executing their main programs.
import itertools  # Expand each shell connectivity into typed pairwise graph relations.
import json  # Read dataset manifests and publish reproducible metrics and predictions.
import math  # Build deterministic geometric Fourier features and finite-value checks.
import random  # Freeze the Python random seed for each independent ensemble member.
import re  # Parse material, section, and boundary keyword attributes from the original input.
import time  # Record the actual training cost independently of FEM cost.
from pathlib import Path  # Resolve all inputs and generated model artifacts explicitly.
import numpy as np  # Assemble source-indexed graph arrays and numerical reference comparisons.
import torch  # Implement differentiable graph message passing and axial equilibrium residuals.
from torch import nn  # Define relation-specific encoders, global interaction, and response decoding.


def digest(path):  # Compute the identity of an exact source or data file.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Preserve line endings and every numeric token in the identity.


def read_json(path):  # Read one explicit UTF-8 JSON record.
    return json.loads(Path(path).read_text(encoding="utf-8"))  # Avoid implicit encoding or silent fallback data.


def write_json(path, value):  # Persist finite reproducible structured output.
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")  # Reject nonfinite model evidence rather than writing invalid JSON.


def load_module(path, name):  # Load a frozen repository implementation for exact parser and mechanics reuse.
    spec = importlib.util.spec_from_file_location(name, path)  # Construct the loader from the manifest's explicit source path.
    if spec is None or spec.loader is None:  # Refuse a missing or malformed Python module.
        raise RuntimeError(f"Cannot load source module: {path}")  # Identify the unavailable physical dependency.
    module = importlib.util.module_from_spec(spec)  # Allocate an isolated module namespace.
    spec.loader.exec_module(module)  # Execute definitions while preserving the module's guarded main entry point.
    return module  # Return only the explicitly loaded implementation.


def keyword_value(line, key):  # Read one comma-delimited source keyword parameter.
    match = re.search(r"(?:^|,)\s*" + re.escape(key) + r"\s*=\s*([^,]+)", line, re.I)  # Match a complete parameter name without partial substring ambiguity.
    return match.group(1).strip().upper() if match else None  # Normalize symbolic names while preserving numeric text for later conversion.


def source_cloads(text):  # Parse the original single explicit nodal-force block without inferring any load distribution.
    active, blocks, loads = False, 0, {}  # Track source keyword ownership and exact nodal-force records.
    for raw in text.splitlines():  # Inspect every source row without changing record order.
        line = raw.strip()  # Remove only insignificant surrounding whitespace.
        if not line or line.startswith("**"):  # Ignore comments and blank lines within the original block.
            continue  # Preserve the current keyword-body state.
        if line.startswith("*"):  # Detect source keyword transitions.
            active = line.upper().split(",")[0] == "*CLOAD"  # Accept only the original concentrated nodal-force keyword.
            blocks += int(active)  # Count blocks to reject unsupported multi-step or replacement semantics.
            continue  # Advance to the keyword's data rows.
        if active:  # Parse an explicitly declared node, translation direction, and force.
            fields = [value.strip() for value in line.split(",")]  # Preserve the original CLOAD tuple semantics.
            if len(fields) != 3 or not fields[0].isdigit() or not fields[1].isdigit():  # Require the reviewed direct-node concentrated-load format.
                raise RuntimeError(f"Unsupported source CLOAD row: {raw}")  # Refuse interpolation or guessed named-set expansion.
            key, value = (int(fields[0]), int(fields[1])), float(fields[2])  # Recover the actual source degree and force in newtons.
            if key in loads or key[1] not in (1, 2, 3) or not math.isfinite(value):  # Reject ambiguous duplicate, rotational, or nonfinite load records.
                raise RuntimeError(f"Unsupported or repeated source CLOAD degree: {key}")  # Keep the model's load input meaning explicit.
            loads[key] = value  # Preserve the original scalar force on this source degree.
    if blocks != 1:  # Require the same one-load-block baseline semantics as the original case generator.
        raise RuntimeError(f"Expected one source CLOAD block, received {blocks}")  # Stop before silently mixing loading steps.
    return loads  # Return the exact source nodal-force ledger.


def section_properties(text, group_names):  # Recover actual elastic, density, and section attributes for each graph relation.
    lines = text.splitlines()  # Preserve original input ordering for keyword-body association.
    materials, sections, current = {}, {}, None  # Maintain explicit material ownership and section mappings.
    for index, raw in enumerate(lines):  # Inspect every keyword and its immediate parameter body.
        line = raw.strip().upper()  # Normalize source keyword capitalization only.
        if line.startswith("*MATERIAL,"):  # Enter a named original material block.
            current = keyword_value(line, "NAME")  # Capture the exact symbolic material identifier.
            materials[current] = {}  # Begin a separate property dictionary for this source material.
        elif line == "*ELASTIC" and current is not None:  # Read the explicitly declared isotropic elastic law.
            values = [float(value) for value in lines[index + 1].split(",") if value.strip()]  # Parse the original elastic modulus and Poisson ratio.
            materials[current].update(E=values[0], nu=values[1])  # Preserve the actual material values in N-mm units.
        elif line == "*DENSITY" and current is not None:  # Read the original tonne-per-cubic-millimetre density.
            materials[current]["density"] = float(lines[index + 1].strip())  # Avoid substituting generic material defaults.
        elif any(line.startswith(prefix) for prefix in ("*BEAM SECTION", "*SHELL SECTION", "*SOLID SECTION")):  # Recognize all source stiffness-carrying section families.
            group = keyword_value(line, "ELSET")  # Identify which stable element group owns this section.
            values = [float(value) for value in lines[index + 1].split(",") if value.strip()]  # Read the original cross-section dimensions or thickness or area.
            sections[group] = {"material": keyword_value(line, "MATERIAL"), "kind": line.split(",")[0], "values": values}  # Keep section family separate from its dimensions.
    output = {}  # Allocate per-relation normalized material and section features.
    for group in group_names:  # Require physical attributes for each response-bearing relation.
        source = sections[group]  # Fail explicitly if the source does not define the requested section.
        material = materials[source["material"]]  # Bind section attributes to their exact named material.
        dims = source["values"]  # Read the unmodified section dimensions.
        measure = dims[0] * dims[1] if source["kind"] == "*BEAM SECTION" else dims[0]  # Use area for rectangular beams and original thickness or area for shells or axial solids.
        output[group] = [material["E"] / 200000.0, material["nu"], material["density"] / 7.85e-9, math.log1p(measure) / 15.0, dims[0] / 1500.0, dims[1] / 1500.0 if len(dims) > 1 else 0.0]  # Encode source-scale attributes with fixed documented physical reference scales.
    return output  # Return source-grounded per-component features.


class BridgeGraph:  # Preserve the original retained bridge and suspension topology for graph prediction and residual checks.
    def __init__(self, manifest):  # Assemble graph attributes only from frozen model and equilibrium-state inputs.
        self.pipeline = load_module(manifest["pipeline_module"], "zhaqing_surrogate_pipeline")  # Reuse the exact original model and DAT parsers.
        self.adapter = load_module(manifest["adapter_module"], "zhaqing_surrogate_adapter")  # Reuse the original canonical retained-structure contract.
        self.adapter.bind_globals(self.pipeline)  # Bind the source material constants and utilities into the original adapter.
        self.nonlinear = load_module(manifest["nonlinear_module"], "zhaqing_surrogate_nonlinear")  # Load the fixed-L0 mechanics for independent residual agreement checks.
        self.text = Path(manifest["baseline"]).read_text(encoding="utf-8")  # Read the original mother deck without rewriting any parameter.
        nodes, self.groups, ownership = self.pipeline.parse_model(self.text)  # Recover original stable nodes, element families, and ownership.
        state = read_json(manifest["equilibrium_state"])  # Consume the persisted accepted F3 equilibrium state.
        self.coordinates, element_states, target = self.adapter.validate_state_v3(state, Path(manifest["baseline"]), nodes, self.groups)  # Verify complete topology and constitutive identity before constructing a graph.
        self.context = self.nonlinear.build_fixed_l0_context(self.adapter, self.text, self.coordinates, self.groups, element_states)  # Build the same immutable suspension law used by the original nonlinear solver.
        self.group_names = list(self.adapter.PRIMARY_VTK_GROUPS)  # Retain all seven response-bearing source relation types.
        self.node_ids = sorted({node for group in self.group_names for element, connectivity in self.groups[group] for node in connectivity})  # Derive complete source-node coverage from physical connectivity.
        self.index = {node: index for index, node in enumerate(self.node_ids)}  # Keep an explicit reversible source-node-to-tensor map.
        self.xyz = torch.tensor([self.coordinates[node] for node in self.node_ids], dtype=torch.float64)  # Preserve millimetre geometry in double precision for small-displacement axial residuals.
        nsets = self.adapter.parse_nsets(self.text)  # Recover original named boundary sets.
        mask = np.zeros((len(self.node_ids), 3), dtype=np.float32)  # Allocate prescribed translational degree flags without constraining free rotations.
        boundary_active = False  # Track the original explicit boundary block.
        for raw in self.text.splitlines():  # Inspect the source boundary records directly.
            line = raw.strip()  # Normalize only surrounding whitespace.
            if line.startswith("**"):  # Skip comments without ending a boundary block.
                continue  # Preserve the current keyword-body context.
            if line.startswith("*"):  # Detect source keyword transitions.
                boundary_active = line.upper().startswith("*BOUNDARY")  # Enter only original boundary blocks.
                continue  # Advance to the next potential data row.
            if boundary_active and line:  # Parse each prescribed source degree row.
                fields = [value.strip() for value in line.split(",")]  # Split the source set, degree range, and prescribed value.
                first = int(fields[1])  # Read the first prescribed degree of freedom.
                last = int(fields[2]) if len(fields) > 2 and fields[2] else first  # Read the inclusive original degree range.
                value = float(fields[3]) if len(fields) > 3 and fields[3] else 0.0  # Read the original prescribed displacement.
                if value != 0.0 and first <= 3:  # Refuse unsupported nonzero displacement boundary semantics.
                    raise RuntimeError("This graph adapter requires the source zero translational supports")  # Stop instead of silently changing a prescribed displacement.
                selected = {int(fields[0])} if fields[0].isdigit() else nsets[fields[0].upper()]  # Resolve direct node labels or the exact named node set.
                for node in selected & set(self.node_ids):  # Limit masks to source nodes actually represented in the canonical response.
                    for axis in range(max(first, 1) - 1, min(last, 3)):  # Mask only physical translational degrees one through three.
                        mask[self.index[node], axis] = 1.0  # Record the original prescribed zero displacement.
        self.declared_boundary = torch.from_numpy(mask)  # Preserve declared supports as attributes without equating expanded CalculiX knot constraints to original source-node translations.
        hard = np.zeros_like(mask)  # Reserve hard constraints for source degrees whose output semantics prove exact zero displacement.
        for node in self.context["anchorNodes"]:  # Select only explicitly fixed original cable anchors from the analytic suspension contract.
            hard[self.index[node], :] = 1.0  # Enforce the original anchor coordinates that the nonlinear solver fixes exactly.
        self.boundary = torch.from_numpy(hard)  # Apply hard source-node constraints only where the source-to-output mapping is established.
        memberships = np.zeros((len(self.node_ids), len(self.group_names)), dtype=np.float32)  # Encode mixed node roles without forcing one exclusive type.
        properties = section_properties(self.text, self.group_names)  # Read material and section features from the actual model.
        relations = []  # Collect directed relation edges and geometry attributes by source type.
        for relation_id, group in enumerate(self.group_names):  # Retain distinct shell, beam, tower, cable, and hanger transformations.
            source, target, features = [], [], []  # Build one typed directed multigraph edge table.
            for element, connectivity in self.groups[group]:  # Preserve every original source member, including shared shell and beam connections.
                for node in connectivity:  # Record all mixed engineering roles of each physical node.
                    memberships[self.index[node], relation_id] = 1.0  # Set the source component membership flag.
                for node_a, node_b in itertools.combinations(connectivity, 2):  # Represent complete element membership including both S4 diagonals as graph relations, not additional FE members.
                    for first, second in ((node_a, node_b), (node_b, node_a)):  # Include both message directions without changing the original physical model.
                        delta = np.array(self.coordinates[second]) - np.array(self.coordinates[first])  # Compute actual equilibrium relative geometry.
                        length = float(np.linalg.norm(delta))  # Measure the source-node separation in millimetres.
                        source.append(self.index[first])  # Append the reversible sender index.
                        target.append(self.index[second])  # Append the reversible receiver index.
                        features.append(list(delta / max(length, 1e-9)) + [length / 82000.0] + properties[group])  # Encode direction, relative length, and source material and section properties.
            relations.append((torch.tensor(source, dtype=torch.long), torch.tensor(target, dtype=torch.long), torch.tensor(features, dtype=torch.float32)))  # Keep typed edge tables separate for heterogeneous message transformations.
        self.relations = relations  # Retain the complete graph edge structure for training and inference.
        centered = self.xyz.float() / torch.tensor([82000.0, 4000.0, 10000.0])  # Normalize geometry using fixed bridge-unit reference scales.
        fourier = [function(centered * frequency * math.pi) for frequency in (1.0, 2.0, 4.0) for function in (torch.sin, torch.cos)]  # Add smooth positional features without node-identity embeddings.
        self.features = torch.cat([centered, torch.from_numpy(memberships), self.declared_boundary] + fourier, dim=-1)  # Encode all declared support types while only cable anchors receive a hard output mask.
        self.edge_count = sum(len(source) for source, target, features in relations)  # Record graph size independently of the 1070 physical finite elements.
        basis_paths = manifest["load_basis_files"]  # Require exact source-case load distributions in the declared factor-coordinate order.
        base_loads = source_cloads(self.text)  # Recover the original baseline concentrated loads once.
        basis = np.zeros((len(basis_paths), len(self.node_ids), 3), dtype=np.float32)  # Allocate each actual source nodal-load increment without touching the FEM model.
        source_hashes = manifest.get("provenance", {}).get("source_load_sha256", {})  # Read the generator's frozen source load-file identities.
        self.load_basis_sha256 = []  # Bind every represented load-pattern basis to exact source bytes.
        for factor, path in enumerate(basis_paths):  # Preserve the declared uniform, wind, and asymmetric coordinate order.
            if path is None:  # Keep an intentionally inactive domain direction explicit rather than inventing its load pattern.
                self.load_basis_sha256.append(None)  # Record the unsupported inactive factor as absent source data.
                continue  # Leave this factor's nodal basis zero only because the scenario domain fixes it to zero.
            path = Path(path)  # Resolve the explicit original source-case input.
            identity = digest(path)  # Freeze every original load-pattern source byte.
            if path.stem in source_hashes and source_hashes[path.stem] != identity:  # Verify source load files against the actual FEM generator's frozen identities.
                raise RuntimeError(f"Load-pattern source differs from FEM data provenance: {path}")  # Refuse graph input semantics that differ from the response-label calculations.
            self.load_basis_sha256.append(identity)  # Preserve the exact basis source identity for the model contract.
            selected = source_cloads(path.read_text(encoding="utf-8"))  # Read this source case's explicit nodal-force ledger.
            for degree in set(base_loads) | set(selected):  # Calculate the source-case-minus-baseline force increment on every declared degree.
                value = selected.get(degree, 0.0) - base_loads.get(degree, 0.0)  # Reproduce the original case generator's additive load definition.
                if degree[0] not in self.index and abs(value) > 1e-9:  # Reject nonzero loading on excluded or unmapped graph nodes.
                    raise RuntimeError(f"Load basis references a noncanonical source node: {degree}")  # Stop before silently dropping part of an applied load.
                if degree[0] in self.index:  # Preserve every represented physical force component.
                    basis[factor, self.index[degree[0]], degree[1] - 1] = value  # Assign the actual source increment in newtons.
        self.load_basis = torch.from_numpy(basis)  # Keep physical load patterns independent of learned neural parameters.
        self.load_scale_N = max(float(np.max(np.abs(basis))), 1.0)  # Normalize nodal force inputs by the largest original basis-force magnitude.
        self.factor_mean = torch.zeros(len(basis_paths), dtype=torch.float32)  # Initialize reversible scenario normalization for source-only mechanics checks.
        self.factor_scale = torch.ones(len(basis_paths), dtype=torch.float32)  # Use identity scaling until training-only normalizers are assigned.
        self.suspension = sorted(self.context["activeElementIds"])  # Freeze the intact original suspension member order.
        records = [self.context["elementData"][element] for element in self.suspension]  # Read every member's immutable material-length law.
        self.axial_a = torch.tensor([self.index[record["nodeIds"][0]] for record in records], dtype=torch.long)  # Resolve ordered axial endpoint A.
        self.axial_b = torch.tensor([self.index[record["nodeIds"][1]] for record in records], dtype=torch.long)  # Resolve ordered axial endpoint B.
        self.l0 = torch.tensor([record["unstressedLengthMm"] for record in records], dtype=torch.float64)  # Preserve each fixed unstressed fabrication length.
        self.ea = torch.tensor([record["axialRigidityN"] for record in records], dtype=torch.float64)  # Preserve each source axial rigidity in newtons.
        self.weight = torch.tensor([record["constantSelfWeightN"] for record in records], dtype=torch.float64)  # Preserve the original constant nominal-F3 self-weight convention.
        self.internal_ids = sorted(self.context["internalNodes"])  # Identify free suspension nodes only; retained interfaces are not zero-force boundaries.
        self.internal = torch.tensor([self.index[node] for node in self.internal_ids], dtype=torch.long)  # Resolve the exact rows where suspension equilibrium applies independently.
        self.force_scale = float(np.median([record["baseForceN"] for record in records]))  # Normalize residuals by the source median positive prestress force.

    def forces(self, displacement):  # Assemble differentiable actual-geometry suspension forces without re-equilibrating predictions.
        coordinates = self.xyz.unsqueeze(0) + displacement.double()  # Apply the predicted total displacement to accepted nominal-F3 coordinates.
        chord = coordinates[:, self.axial_b] - coordinates[:, self.axial_a]  # Compute current member vectors with source orientation.
        length = torch.linalg.vector_norm(chord, dim=-1).clamp_min(1e-9)  # Compute current lengths while avoiding undefined division during rejected training trials.
        force = self.ea.unsqueeze(0) / self.l0.unsqueeze(0) * (length - self.l0.unsqueeze(0))  # Apply the exact original N=EA/L0*(L-L0) law.
        axial = force.unsqueeze(-1) * chord / length.unsqueeze(-1)  # Form tensile action at endpoint A in global coordinates.
        gravity = torch.zeros_like(axial)  # Allocate constant half-element gravity in the original global axes.
        gravity[:, :, 2] = -0.5 * self.weight.unsqueeze(0)  # Apply the same downward nominal-F3 half-element weight at both endpoints.
        actions = torch.zeros_like(coordinates)  # Allocate all source-node suspension actions in newtons.
        actions.index_add_(1, self.axial_a, axial + gravity)  # Assemble endpoint-A tensile and gravity action.
        actions.index_add_(1, self.axial_b, -axial + gravity)  # Assemble equal-and-opposite axial action and endpoint-B gravity.
        return actions  # Return actual predicted-state actions without solving away errors.

    def physics_loss(self, displacement):  # Penalize only the documented free-suspension-node equilibrium equations.
        return (self.forces(displacement)[:, self.internal] / self.force_scale).square().mean()  # Keep the residual dimensionless and its physical scope explicit.

    def physics_metrics(self, displacement):  # Report dimensional physical residuals for each predicted or reference sample.
        actions = self.forces(displacement)[:, self.internal]  # Select actual free suspension equilibrium equations.
        norms = torch.linalg.vector_norm(actions, dim=-1)  # Compute the physical vector imbalance at each free suspension node.
        return [{"max_free_suspension_residual_N": float(norms[index].max()), "rms_free_suspension_residual_N": float(actions[index].square().mean().sqrt())} for index in range(len(displacement))]  # Publish newton residuals independently from training normalization.

    def verify_physics(self):  # Cross-check the differentiable residual against the original nonlinear mechanics implementation.
        generator = torch.Generator().manual_seed(9810)  # Freeze a repeatable nontrivial displacement perturbation.
        trials = [torch.zeros((1, len(self.node_ids), 3), dtype=torch.float64), torch.randn((1, len(self.node_ids), 3), generator=generator, dtype=torch.float64) * 0.01]  # Check both nominal equilibrium and arbitrary nonequilibrium geometry.
        maximum = 0.0  # Track the largest discrepancy across every source suspension node.
        for trial in trials:  # Independently check both mechanics states.
            ours = self.forces(trial)[0].detach().numpy()  # Evaluate the new differentiable formula without gradients for comparison.
            coordinates = {node: tuple(self.coordinates[node][axis] + float(trial[0, self.index[node], axis]) for axis in range(3)) for node in self.node_ids}  # Build the original mechanics API's source-keyed current geometry.
            for plane in self.context["planes"]:  # Compare both physical suspension planes independently.
                original = self.nonlinear._assemble_plane_response(self.context, plane, coordinates, assemble_internal_tangent=False)  # Evaluate original actions without solving or changing coordinates.
                maximum = max(maximum, max(float(np.max(np.abs(ours[self.index[node]] - np.array(action)))) for node, action in original["actionsN"].items()))  # Compare all dimensional action components directly.
        if maximum > 1e-4:  # Require sub-millinewton agreement despite finite arithmetic ordering differences.
            raise RuntimeError(f"Differentiable mechanics disagree with original actions by {maximum} N")  # Reject training on a mismatched physics implementation.
        return {"status": "PASS", "maximum_action_difference_N": maximum, "tolerance_N": 1e-4, "tested_states": ["nominal_F3", "deterministic_nonequilibrium_0.01mm_perturbation"], "re_equilibrated_predictions": False}  # Retain the meaningful mechanics verification evidence.


def lifting_features(physical, order):  # Build a declared low-order load basis without consulting any response labels.
    q, a = physical[:, 0].double(), physical[:, 2].double()  # Preserve the two physically active load coordinates.
    terms = [torch.ones_like(q), q, a]  # Represent affine retained response dependence explicitly.
    if order == 2:  # Add a controlled quadratic approximation for geometric response curvature.
        terms += [q.square(), q * a, a.square()]  # Keep the exact basis identical during training and inference.
    return torch.stack(terms, dim=1)  # Return one row per actual load scenario.


class HeterogeneousLayer(nn.Module):  # Perform relation-specific local communication followed by whole-bridge interaction.
    def __init__(self, width, relations, edge_width):  # Create independent parameters for every engineering relation.
        super().__init__()  # Initialize the PyTorch module registry.
        self.messages = nn.ModuleList([nn.Sequential(nn.Linear(width + edge_width, width), nn.SiLU(), nn.Linear(width, width)) for relation in range(relations)])  # Encode each edge type with its own learned message function.
        self.local = nn.Linear(width, width)  # Transform the aggregated local neighborhood state.
        self.global_interaction = nn.Sequential(nn.Linear(width * 2, width), nn.SiLU(), nn.Linear(width, width))  # Couple each node to the pooled whole-bridge state.
        self.norm = nn.LayerNorm(width)  # Stabilize feature scales across repeated local-global layers.

    def forward(self, features, graph):  # Update a batched graph state without depending on arbitrary node ordering.
        aggregate = torch.zeros_like(features)  # Allocate typed neighbor messages in the receiver-node layout.
        degree = torch.zeros((len(graph.node_ids), 1), dtype=features.dtype)  # Count incoming graph relations for degree-normalized aggregation.
        for network, (source, target, edge) in zip(self.messages, graph.relations):  # Keep relation parameters attached to their physical engineering type.
            edge_batch = edge.unsqueeze(0).expand(features.shape[0], -1, -1)  # Share fixed geometry across actual load scenarios.
            message = network(torch.cat([features[:, source], edge_batch], dim=-1))  # Encode sender state and source-derived edge properties.
            aggregate.index_add_(1, target, message)  # Sum incoming messages under the explicit source-node mapping.
            degree.index_add_(0, target, torch.ones((len(target), 1), dtype=features.dtype))  # Track multiplicity of the original typed connectivity.
        aggregate = aggregate / degree.clamp_min(1.0).unsqueeze(0)  # Avoid making high-valence nodes dominate merely because of relation count.
        pooled = features.mean(dim=1, keepdim=True).expand_as(features)  # Provide a permutation-invariant whole-bridge context.
        return self.norm(features + torch.nn.functional.silu(self.local(aggregate)) + self.global_interaction(torch.cat([features, pooled], dim=-1)))  # Combine local and global effects through a residual update.


class GraphSurrogate(nn.Module):  # Map bridge geometry, material relations, supports, and scenario factors to displacement fields.
    def __init__(self, graph, factor_count, width, depth):  # Configure a genuine typed graph model rather than a tabular surrogate.
        super().__init__()  # Register network parameters and nested modules.
        if factor_count != graph.load_basis.shape[0]:  # Require the exact declared load-factor dimension and source-pattern basis count.
            raise RuntimeError("Scenario factor count differs from the source nodal-load basis")  # Refuse a mismatched physical input schema.
        self.encoder = nn.Sequential(nn.Linear(graph.features.shape[1] + factor_count + 3, width), nn.SiLU(), nn.Linear(width, width))  # Encode actual node loads, source geometry, and global physical scenario coordinates jointly.
        self.layers = nn.ModuleList([HeterogeneousLayer(width, len(graph.group_names), graph.relations[0][2].shape[1]) for layer in range(depth)])  # Stack explicit relation-specific local and whole-bridge updates.
        self.decoder = nn.Sequential(nn.Linear(width, width), nn.SiLU(), nn.Linear(width, 3))  # Decode three global translational response components per physical node.

    def forward(self, factors, graph, response_scale):  # Predict full source-node displacements while enforcing proven fixed cable-anchor outputs.
        node = graph.features.unsqueeze(0).expand(factors.shape[0], -1, -1)  # Broadcast fixed source topology attributes over scenarios.
        loads = factors.unsqueeze(1).expand(-1, len(graph.node_ids), -1)  # Attach normalized scenario coordinates to each node query.
        physical = factors * graph.factor_scale.unsqueeze(0) + graph.factor_mean.unsqueeze(0)  # Recover actual load multipliers before applying the frozen source force patterns.
        nodal_forces = torch.einsum("bd,dnc->bnc", physical, graph.load_basis) / graph.load_scale_N  # Encode each node's actual scenario-specific added load vector from original source CLOAD differences.
        hidden = self.encoder(torch.cat([node, loads, nodal_forces], dim=-1))  # Lift source geometry, global scenario coordinates, and actual nodal-load distribution into graph features.
        for layer in self.layers:  # Apply every actual message-passing layer.
            hidden = layer(hidden, graph)  # Propagate local mechanics-related context and long-range bridge context.
        raw = self.decoder(hidden)  # Produce normalized unconstrained response components for boundary supervision.
        displacement = raw * response_scale.reshape(1, 1, 3) * (1.0 - graph.boundary.unsqueeze(0))  # Enforce exact zero cable-anchor translations in dimensional millimetres without forcing beam-shell source-node outputs to zero.
        if getattr(graph, "lifting_order", 0):  # Use only the declared lift fitted on training cases.
            lifted = torch.einsum("bk,knc->bnc", lifting_features(physical, graph.lifting_order), graph.lifting_coefficients)  # Evaluate saved training-only coefficients without a FEM solve.
            displacement = lifted + 0.01 * displacement  # Train genuine typed graph messages to predict the smaller nonlinear correction.
        return displacement, raw  # Return dimensional predictions with an explicit graph residual and its raw precursor.


def load_samples(manifest, graph):  # Accept only actual qualified source-topology FEM response files.
    samples, values, factors, identities = [], [], [], []  # Allocate explicit scenario metadata, labels, inputs, and provenance.
    seen = set()  # Detect scenario-id leakage before making any split.
    for sample in manifest["samples"]:  # Read every manifest-declared scenario exactly once.
        case = sample["case_id"]  # Preserve the stable calculation and scenario identifier.
        if case in seen:  # Refuse repeated identities across training and held-out partitions.
            raise RuntimeError(f"Repeated case id across dataset: {case}")  # Stop before duplicate-case leakage can enter evaluation.
        seen.add(case)  # Reserve this scenario identity.
        if sample.get("quality_flag") != "VALID_CONVERGED" or read_json(sample["summary"]).get("status") != "PASS":  # Require both the MD eligibility label and a real solver quality receipt.
            raise RuntimeError(f"Unqualified FEM label: {case}")  # Never turn numerical failures into supervised response truth.
        if (sample.get("split") == "train" and sample.get("eligible_for_training") is False) or sample.get("reference_label_available") is False:  # Respect actual-reference eligibility while preserving intentional nontraining status of validation and test samples.
            raise RuntimeError(f"Generator marked FEM label unavailable or inadmissible: {case}")  # Keep quarantined calculations outside all supervised partitions.
        for field in ("canonical_dat", "summary"):  # Validate immutable native-result identities when the generator supplies them.
            if sample.get(field + "_sha256") and digest(sample[field]) != sample[field + "_sha256"]:  # Compare the current exact response and Gate bytes with their persisted receipts.
                raise RuntimeError(f"Qualified source bytes changed for {case}: {field}")  # Refuse edited labels under an old convergence or quality status.
        if sample.get("removed_element_ids"):  # Refuse training on unimplemented member-deletion topology changes.
            raise RuntimeError(f"Damage topology requires a separate graph adapter: {case}")  # Preserve intact source topology semantics explicitly.
        if not sample.get("audit_path"):  # Require an explicit independent mechanics audit for every FEM reference in this run.
            raise RuntimeError(f"Independent physical audit is missing for label: {case}")  # Refuse training directly from the producer's self-reported PASS manifest.
        audit = read_json(sample["audit_path"])  # Read actual independent mechanics qualification evidence.
        if audit.get("eligibleForModuleB") is not True or audit.get("labelEligible") is False:  # Require an explicit positive independent decision and honor any subsidiary rejection.
            raise RuntimeError(f"Independent physical audit rejected label: {case}")  # Keep rejected data outside training and evaluation.
        if sample.get("audit_sha256") and digest(sample["audit_path"]) != sample["audit_sha256"]:  # Verify independent qualification bytes against the audited snapshot.
            raise RuntimeError(f"Independent physical audit changed after snapshot: {case}")  # Prevent stale admission under revised quality evidence.
        if sample["split"] not in ("train", "validation", "test"):  # Require a precommitted split for every scenario.
            raise RuntimeError(f"Unknown dataset split for {case}")  # Refuse automatic test-set creation after viewing results.
        displacement, reactions = graph.pipeline.parse_dat_nodes(Path(sample["canonical_dat"]))  # Read actual canonical solver response values through the original parser.
        if set(displacement) != set(graph.node_ids):  # Require complete and exact source-node coverage without zero filling.
            raise RuntimeError(f"Canonical node coverage mismatch for {case}")  # Reject labels from another topology or an incomplete calculation.
        labels = np.array([displacement[node] for node in graph.node_ids], dtype=np.float64)  # Preserve every parsed FEM reference value in double precision for supervision, dimensional error, and strict physical residual audit.
        coordinates = np.asarray(sample["factors"], dtype=np.float32)  # Read explicitly declared physical scenario-factor coordinates.
        if len(coordinates) != graph.load_basis.shape[0] or any(path is None and abs(float(coordinates[index])) > 1e-9 for index, path in enumerate(manifest["load_basis_files"])):  # Reject unsupported nonzero load factors and inconsistent source-pattern dimensions.
            raise RuntimeError(f"Scenario activates a missing nodal-load basis: {case}")  # Never predict an inactive wind pattern as if a force field had been provided.
        if not np.isfinite(labels).all() or not np.isfinite(coordinates).all():  # Reject nonfinite solver values and load coordinates.
            raise RuntimeError(f"Nonfinite response or factor in {case}")  # Stop before invalid values contaminate normalization.
        samples.append(sample)  # Retain exact scenario and split metadata.
        values.append(labels)  # Store actual FEM displacement labels only.
        factors.append(coordinates)  # Store the matching declared load coordinates.
        identities.append({"case_id": case, "split": sample["split"], "canonical_dat_sha256": digest(sample["canonical_dat"]), "summary_sha256": digest(sample["summary"]), "audit_sha256": digest(sample["audit_path"]) if sample.get("audit_path") else None})  # Freeze data and gate evidence identity.
    counts = {split: sum(sample["split"] == split for sample in samples) for split in ("train", "validation", "test")}  # Count independently assigned within-bridge scenario partitions.
    if counts["train"] < 2 or counts["validation"] < 1 or counts["test"] < 1:  # Require actual training diversity and both independent evaluation roles.
        raise RuntimeError(f"Need at least 2 train, 1 validation, and 1 test cases; received {counts}")  # Refuse to describe fitting one baseline as surrogate validation.
    return samples, torch.tensor(np.stack(values)), torch.tensor(np.stack(factors)), identities  # Return aligned real labels, physical coordinates, and provenance.


def evaluate(model, factors, graph, response_scale, labels):  # Compute normalized predictive loss without updating parameters.
    model.eval()  # Freeze stochastic training behavior during model selection.
    with torch.no_grad():  # Exclude evaluation from the optimization graph.
        predicted, raw = model(factors, graph, response_scale)  # Predict the preassigned validation scenarios.
        return float(((predicted - labels) / response_scale.reshape(1, 1, 3)).square().mean())  # Select checkpoints using only held-out development response error.


def metrics_for(predicted, labels, uncertainty, graph):  # Separate dimensional accuracy, physical consistency, and ensemble disagreement.
    physical = graph.physics_metrics(predicted)  # Evaluate actual geometry residuals without correcting network output.
    result = []  # Build one complete metric record per actual scenario.
    for index in range(len(predicted)):  # Report metrics separately so large-response cases cannot hide small-response failures.
        error = predicted[index] - labels[index]  # Compute dimensional three-component source-node error.
        norm = float(torch.linalg.vector_norm(labels[index]))  # Preserve the actual reference-field magnitude.
        target_peak = float(torch.linalg.vector_norm(labels[index], dim=-1).max())  # Evaluate the FEM maximum displacement-vector magnitude.
        predicted_peak = float(torch.linalg.vector_norm(predicted[index], dim=-1).max())  # Evaluate the network maximum displacement-vector magnitude.
        row = {"rmse_mm": float(error.square().mean().sqrt()), "mae_mm": float(error.abs().mean()), "relative_l2": float(torch.linalg.vector_norm(error)) / max(norm, 1e-12), "reference_peak_mm": target_peak, "predicted_peak_mm": predicted_peak, "peak_absolute_error_mm": abs(predicted_peak - target_peak), "ensemble_rms_std_mm": float(uncertainty[index].square().mean().sqrt()), "maximum_anchor_displacement_mm": float((predicted[index] * graph.boundary).abs().max()), **physical[index]}  # Keep response error, boundary enforcement, uncertainty, and physical residual conceptually separate.
        result.append(row)  # Preserve this sample's independent metrics.
    return result  # Return no pooled engineering safety claim.


def predict_existing(model_directory, candidates_path, output_directory, threads=2):  # Evaluate new candidates using frozen saved ensemble weights without any training or test feedback.
    torch.set_num_threads(threads)  # Bound inference resource use independently of ongoing finite-element calculation.
    model_directory = Path(model_directory).resolve()  # Resolve the selected already-trained ensemble generation.
    manifest = read_json(model_directory / "dataset_manifest.json")  # Recover the exact source graph and training-factor inventory used by this ensemble.
    contract = read_json(model_directory / "model_contract.json")  # Recover the saved source and architecture identity contract.
    for key, expected in contract["source_sha256"].items():  # Verify every physical model and mechanics source before inference.
        if digest(manifest[key]) != expected:  # Detect a changed model, equilibrium state, or physics adapter.
            raise RuntimeError(f"Saved-ensemble source changed before prediction: {key}")  # Refuse mixing old trained weights with a revised physical model.
    graph = BridgeGraph(manifest)  # Reconstruct the same source-ID graph and fixed fabrication-length mechanics.
    if graph.load_basis_sha256 != contract["load_basis_sha256"]:  # Verify saved graph load-pattern semantics independently from the baseline geometry.
        raise RuntimeError("Saved ensemble nodal-load basis changed before prediction")  # Refuse old weights under revised source loading patterns.
    normalization = read_json(model_directory / "normalization.json")  # Read only training-fitted normalization constants.
    if normalization["node_ids"] != graph.node_ids:  # Prove preserved source-node response ordering.
        raise RuntimeError("Saved ensemble node mapping differs from the reconstructed source graph")  # Reject accidental output relabeling.
    mean = torch.tensor(normalization["factor_mean"], dtype=torch.float32)  # Restore fixed physical load-coordinate centering.
    scale = torch.tensor(normalization["factor_scale"], dtype=torch.float32)  # Restore fixed physical load-coordinate scaling.
    response_scale = torch.tensor(normalization["response_scale_mm"], dtype=torch.float64)  # Restore the double-precision dimensional response transformation without truncating the true FEM-derived scale.
    graph.factor_mean, graph.factor_scale = mean, scale  # Restore the reversible physical-factor transform used to form actual nodal loads.
    training_factors = torch.tensor([sample["factors"] for sample in manifest["samples"] if sample["split"] == "train"], dtype=torch.float32)  # Use training inputs alone for coverage and extrapolation diagnostics.
    graph.lifting_order = contract.get("lifting_order", 0)  # Restore the architecture selected using development data only.
    if graph.lifting_order:  # Restore the saved train-only lifting matrix without refitting on candidates.
        lift = read_json(model_directory / "lifting.json")  # Read the frozen coefficient artifact.
        if digest(model_directory / "lifting.json") != contract["lifting_sha256"]:  # Reject changed lifting coefficients.
            raise RuntimeError("Saved lifting identity changed")  # Preserve inference provenance.
        graph.lifting_coefficients = torch.tensor(lift["coefficients"], dtype=torch.float64)  # Restore full-precision spatial coefficients.
    models = []  # Load each actually selected independent graph model.
    for seed in contract["seeds"]:  # Preserve the saved ensemble membership exactly.
        checkpoint = torch.load(model_directory / f"ensemble_seed_{seed}.pt", map_location="cpu", weights_only=False)  # Read this task's own trusted generated model and optimizer checkpoint.
        model = GraphSurrogate(graph, checkpoint["factor_count"], checkpoint["width"], checkpoint["depth"])  # Instantiate the checkpoint's actual architecture.
        model.load_state_dict(checkpoint["state_dict"])  # Load the best validation-selected weights saved during training.
        model.eval()  # Keep candidate inference independent of optimizer or training behavior.
        models.append(model)  # Retain the frozen independently initialized predictor.
    requested = read_json(candidates_path)  # Read explicitly requested unsolved scenario coordinates.
    candidates = requested["candidates"] if isinstance(requested, dict) else requested  # Support either the documented object wrapper or an explicit candidate list.
    if not candidates:  # Require at least one scenario to assess.
        raise RuntimeError("Candidate prediction requires a nonempty candidate list")  # Refuse meaningless empty uncertainty evidence.
    output = Path(output_directory).resolve()  # Isolate this candidate assessment from existing training and prior candidate files.
    output.mkdir(parents=True, exist_ok=False)  # Preserve every earlier inference result and its decision evidence.
    rows, predictions = [], []  # Store compact decision metrics separately from full source-mapped response fields.
    start = time.perf_counter()  # Measure actual ensemble-inference and residual cost.
    with torch.no_grad():  # Ensure candidate assessment cannot update the trained model.
        for candidate in candidates:  # Evaluate each explicitly declared physical load-factor candidate.
            physical = torch.tensor([candidate["factors"]], dtype=torch.float32)  # Preserve the original candidate coordinate ordering.
            if physical.shape[1] != len(mean) or not torch.isfinite(physical).all():  # Enforce the trained input schema and finite candidate data.
                raise RuntimeError(f"Invalid candidate factors: {candidate['case_id']}")  # Stop before extrapolating a malformed physical scenario.
            if any(path is None and abs(float(physical[0, index])) > 1e-9 for index, path in enumerate(manifest["load_basis_files"])):  # Require every active candidate factor to have its real original nodal-load pattern.
                raise RuntimeError(f"Candidate activates unsupported load basis: {candidate['case_id']}")  # Refuse inventing formal wind response from a zero wind-input basis.
            normalized = (physical - mean) / scale  # Apply the saved training-only input transformation.
            stack = torch.stack([model(normalized, graph, response_scale)[0] for model in models])  # Produce actual independent graph predictions from the frozen ensemble.
            average, deviation = stack.mean(dim=0), stack.std(dim=0, unbiased=True)  # Compute distinct mean prediction and between-model disagreement.
            distance = float(torch.linalg.vector_norm((training_factors - mean) / scale - normalized, dim=1).min())  # Quantify nearest training-input coverage separately from network disagreement.
            outside = bool(((physical < training_factors.min(dim=0).values) | (physical > training_factors.max(dim=0).values)).any())  # Mark extrapolation beyond each observed training coordinate range.
            row = {"case_id": candidate["case_id"], "factors": candidate["factors"], "predicted_peak_mm": float(torch.linalg.vector_norm(average[0], dim=-1).max()), "ensemble_rms_std_mm": float(deviation.square().mean().sqrt()), "nearest_training_distance": distance, "outside_training_box": outside, **graph.physics_metrics(average)[0]}  # Expose the independent quantities consumed by module C's acquisition rule.
            rows.append(row)  # Preserve one compact assessment per candidate.
            predictions.append({"case_id": candidate["case_id"], "factors": candidate["factors"], "mean_displacement": average[0].tolist(), "ensemble_std": deviation[0].tolist()})  # Store complete source-node predicted displacement and uncertainty fields.
    elapsed = time.perf_counter() - start  # Record actual candidate assessment cost without counting prior training.
    write_json(output / "predictions.json", {"node_ids": graph.node_ids, "unit": "mm", "candidates": predictions})  # Persist all response fields using the explicit source-node map.
    report = {"status": "PREDICTED_HOLD", "model_directory": str(model_directory), "model_contract_sha256": digest(model_directory / "model_contract.json"), "candidate_input_sha256": digest(candidates_path), "inference_seconds": elapsed, "candidate_predictions": rows, "whole_bridge_equilibrium_residual_implemented": False, "prediction_intervals_calibrated": False}  # Preserve frozen-model provenance and actual implemented residual scope.
    write_json(output / "metrics.json", report)  # Publish the exact acquisition evidence for module A and module C.
    return report  # Return structured actual predictions without fabricating FEM responses or safety labels.


def main():  # Train and evaluate a reproducible single-bridge typed graph ensemble.
    parser = argparse.ArgumentParser()  # Expose explicit finite training and output controls.
    parser.add_argument("--manifest", type=Path)  # Require a frozen actual-FEM dataset and split manifest in training mode.
    parser.add_argument("--predict-from", type=Path)  # Select saved frozen ensemble inference without running any optimization.
    parser.add_argument("--candidates", type=Path)  # Supply explicit new candidate physical coordinates in saved-model inference mode.
    parser.add_argument("--output", type=Path, required=True)  # Isolate every model generation and its evidence.
    parser.add_argument("--lifting-order", type=int, choices=(0, 1, 2), default=0)  # Compare unchanged graph prediction against training-only affine or quadratic lifts.
    parser.add_argument("--epochs", type=int, default=250)  # Bound CPU training without implying a guaranteed accuracy.
    parser.add_argument("--width", type=int, default=32)  # Configure latent graph representation width explicitly.
    parser.add_argument("--depth", type=int, default=3)  # Configure actual typed message-passing depth explicitly.
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 43])  # Require independent initialization for ensemble disagreement.
    parser.add_argument("--physics-weight", type=float, default=0.01)  # Expose the normalized suspension-equilibrium training contribution.
    parser.add_argument("--learning-rate", type=float, default=0.002)  # Make the AdamW step size reproducible.
    parser.add_argument("--patience", type=int, default=80)  # Stop after a fixed number of epochs without validation improvement.
    parser.add_argument("--threads", type=int, default=2)  # Bound CPU training parallelism independently from solver execution.
    args = parser.parse_args()  # Parse the complete run configuration before loading labels.
    if args.predict_from is not None:  # Route explicit saved-model candidate inference before any training state is created.
        if args.candidates is None or args.manifest is not None:  # Require an unambiguous frozen-model inference request.
            raise RuntimeError("Use --predict-from MODEL_DIRECTORY --candidates CANDIDATES_JSON --output NEW_DIRECTORY")  # State the exact nontraining invocation.
        report = predict_existing(args.predict_from, args.candidates, args.output, args.threads)  # Evaluate actual saved graph weights and dimensional residuals.
        print(json.dumps({"status": report["status"], "candidates": len(report["candidate_predictions"]), "inference_seconds": report["inference_seconds"], "output": str(args.output)}, ensure_ascii=False), flush=True)  # Emit concise completed inference evidence.
        return 0  # Finish without touching model weights or held-out labels.
    if args.manifest is None:  # Require the actual FEM dataset manifest for optimization mode.
        raise RuntimeError("Training requires --manifest DATASET_JSON")  # Refuse ambiguous data discovery or implicit model generation.
    if args.epochs < 1 or len(set(args.seeds)) < 2:  # Refuse empty training or a falsely named one-member ensemble.
        raise RuntimeError("Positive training epochs and at least two distinct seeds are required")  # Preserve the claimed ensemble contract.
    torch.set_num_threads(args.threads)  # Limit CPU cost and avoid oversubscription with native FEM jobs.
    torch.use_deterministic_algorithms(True)  # Require repeatable supported operators for the fixed software environment.
    output = args.output.resolve()  # Freeze the absolute model artifact destination.
    output.mkdir(parents=True, exist_ok=False)  # Refuse to overwrite prior training evidence silently.
    manifest = read_json(args.manifest)  # Read one immutable data and scenario contract.
    graph = BridgeGraph(manifest)  # Build the exact source-derived retained bridge and suspension graph.
    physics_check = graph.verify_physics()  # Verify formula agreement against original mechanics before optimization.
    samples, labels, physical_factors, identities = load_samples(manifest, graph)  # Reject inadmissible, incomplete, or leaked FEM labels.
    excluded = manifest.get("excluded_samples", [])  # Preserve independently quarantined solver or audit failures rather than manufacturing labels.
    if {sample["case_id"] for sample in samples} & {sample["case_id"] for sample in excluded}:  # Require disjoint accepted and quarantined scenario identities.
        raise RuntimeError("A scenario appears in both accepted and excluded samples")  # Reject inconsistent qualification bookkeeping before training.
    expected_counts = manifest.get("expected_split_counts", {split: sum(sample.get("split") == split for sample in samples + excluded) for split in ("train", "validation", "test")})  # Retain the original declared design denominator including missing held-out references.
    train = torch.tensor([index for index, sample in enumerate(samples) if sample["split"] == "train"], dtype=torch.long)  # Freeze training indices before fitting any scale.
    validation = torch.tensor([index for index, sample in enumerate(samples) if sample["split"] == "validation"], dtype=torch.long)  # Freeze development indices used only for checkpoint selection.
    factor_mean = physical_factors[train].mean(dim=0)  # Fit scenario normalization using training inputs only.
    factor_scale = physical_factors[train].std(dim=0, unbiased=False).clamp_min(1.0)  # Preserve constant or tiny-variation axes without magnifying numerical noise.
    factors = (physical_factors - factor_mean) / factor_scale  # Apply the frozen input transformation to every preassigned split.
    graph.factor_mean, graph.factor_scale = factor_mean, factor_scale  # Preserve the true physical load-factor values inside the source nodal-load encoder.
    response_scale = labels[train].square().mean(dim=(0, 1)).sqrt().clamp_min(0.01)  # Fit componentwise displacement scales from training labels only.
    graph.lifting_order = args.lifting_order  # Freeze the selected response-lifting architecture.
    if graph.lifting_order:  # Fit spatial lifting coefficients from training FEM responses only.
        design = lifting_features(physical_factors[train], graph.lifting_order)  # Exclude validation and test coordinates from fitting.
        graph.lifting_coefficients = (torch.linalg.pinv(design) @ labels[train].flatten(1)).reshape(design.shape[1], len(graph.node_ids), 3)  # Fit a finite low-order load-to-field baseline using only training labels.
        write_json(output / "lifting.json", {"order": graph.lifting_order, "training_case_ids": [samples[i]["case_id"] for i in train.tolist()], "coefficients": graph.lifting_coefficients.tolist(), "graph_residual_scale": 0.01})  # Save reproducible lifting weights and their training-only lineage.
    reference_physics = graph.physics_metrics(labels)  # Report dimensional label residuals independently from numerical solver PASS.
    source_paths = {key: manifest[key] for key in ("baseline", "equilibrium_state", "pipeline_module", "adapter_module", "nonlinear_module")}  # Freeze all model and mechanics source dependencies.
    contract = {"architecture": "typed_relation_message_passing_with_global_mean_interaction", "bridge_id": "zhaqing", "node_count": len(graph.node_ids), "source_element_count": sum(len(graph.groups[group]) for group in graph.group_names), "directed_graph_edge_count": graph.edge_count, "relation_types": graph.group_names, "response": "global source-node displacement in mm relative to nominal F3", "physics_equations": "fixed-L0 co-rotational axial action balance on free suspension nodes and exact analytic cable-anchor translations", "whole_bridge_equilibrium_residual_implemented": False, "missing_physics": ["retained CalculiX shell/beam/tower internal equilibrium residual", "retained-to-suspension interface equilibrium residual"], "multi_fidelity_training_implemented": False, "cross_bridge_validation": "NOT_RUN_SINGLE_BRIDGE", "engineering_release": "HOLD_UNVALIDATED_SURROGATE", "source_sha256": {key: digest(path) for key, path in source_paths.items()}, "dataset_sha256": digest(args.manifest), "code_sha256": digest(__file__), "physics_self_check": physics_check, "torch_version": torch.__version__, "training_only_normalization": True, "test_set_used_for_model_selection": False, "hidden_width": args.width, "message_passing_depth": args.depth, "seeds": args.seeds, "physics_weight": args.physics_weight, "epochs_budget": args.epochs}  # State implemented scope and unsupported claims explicitly.
    contract.update({"load_basis_sha256": graph.load_basis_sha256, "nodal_load_input": "original source-case CLOAD minus baseline CLOAD, multiplied by physical scenario factors", "nodal_load_normalization_N": graph.load_scale_N, "hard_boundary_scope": "analytic main-cable anchor translations only", "declared_beam_shell_supports": "encoded as source attributes; expanded-node source translations are not forced to zero"})  # Record actual spatial load encoding and exact source-boundary semantics.
    contract.update({"fem_reference_dtype": "float64_without_float32_round_trip", "physics_residual_dtype": "float64", "dimensional_error_dtype": "float64", "neural_parameter_dtype": "float32", "neural_input_feature_dtype": "float32", "response_scale_dtype": "float64"})  # Separate finite neural representation from preserved native FEM references and dimensional evidence.
    contract.update({"expected_split_counts": expected_counts, "excluded_sample_count": len(excluded), "excluded_samples": excluded, "missing_reference_policy": "quarantined cases are never labels; held-out missing references remain explicit in evaluation denominators"})  # Preserve the frozen split intent and every independently rejected calculation.
    contract.update({"lifting_order": graph.lifting_order, "lifting_sha256": digest(output / "lifting.json") if graph.lifting_order else None, "lifting_fit_scope": "training_only", "graph_residual_scale": 0.01 if graph.lifting_order else 1.0})  # Disclose the fitted lift separately from learned graph messages.
    write_json(output / "model_contract.json", contract)  # Publish architectural and physics scope before model fitting.
    write_json(output / "data_identity.json", identities)  # Persist the exact data split and source identities.
    write_json(output / "normalization.json", {"factor_mean": factor_mean.tolist(), "factor_scale": factor_scale.tolist(), "response_scale_mm": response_scale.tolist(), "suspension_force_scale_N": graph.force_scale, "node_ids": graph.node_ids})  # Preserve inference transformations and stable source-node mapping.
    write_json(output / "dataset_manifest.json", manifest)  # Archive the exact declared samples and candidate coordinates.
    models, histories, seed_receipts = [], [], []  # Accumulate independent trained members and actual optimization records.
    start = time.perf_counter()  # Begin the combined training-and-development evaluation cost timer.
    for seed in args.seeds:  # Fit independently initialized neural graph models on the same frozen data split.
        random.seed(seed)  # Freeze Python initialization and any future sampling helpers.
        np.random.seed(seed)  # Freeze NumPy operations used during this member's run.
        torch.manual_seed(seed)  # Independently and reproducibly initialize all graph network parameters.
        model = GraphSurrogate(graph, factors.shape[1], args.width, args.depth)  # Allocate a fresh typed graph network for this ensemble member.
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-5)  # Optimize all network parameters with the requested AdamW mechanism.
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.learning_rate * 0.05)  # Reduce step size over the precommitted finite training budget.
        best_loss, best_epoch, best_state, best_optimizer, stale = float("inf"), -1, None, None, 0  # Track development-selected state without reading test labels.
        history = []  # Record this member's separate supervised, boundary, and physics losses.
        for epoch in range(args.epochs):  # Iterate only within the declared finite optimization budget.
            model.train()  # Enable training behavior for this gradient step.
            optimizer.zero_grad(set_to_none=True)  # Clear previous gradients before computing the new actual graph loss.
            predicted, raw = model(factors[train], graph, response_scale)  # Predict the true FEM training scenarios only.
            supervised = ((predicted - labels[train]) / response_scale.reshape(1, 1, 3)).square().mean()  # Compute dimensionless three-axis displacement supervision.
            boundary = (raw * graph.boundary.unsqueeze(0)).square().sum() / max(float(graph.boundary.sum()) * len(train), 1.0)  # Encourage raw predictions to respect analytic cable-anchor conditions in addition to the hard constraint.
            physics = graph.physics_loss(predicted)  # Compute source-consistent free-suspension actual-geometry residuals without any corrective solve.
            ramp = min(1.0, (epoch + 1) / 30.0)  # Introduce the predeclared physics weight smoothly during early parameter fitting.
            loss = supervised + 0.1 * boundary + args.physics_weight * ramp * physics  # Combine individually normalized supervision, boundary, and supported physical constraints.
            if not torch.isfinite(loss):  # Reject divergence immediately instead of saving a misleading model.
                raise RuntimeError(f"Nonfinite training loss at seed {seed} epoch {epoch}")  # Preserve the exact failed training stage.
            loss.backward()  # Differentiate through actual graph communication and the fixed-L0 mechanics equations.
            gradient = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)  # Bound unstable update magnitude without clipping physical labels.
            optimizer.step()  # Apply one AdamW parameter update.
            scheduler.step()  # Advance the declared learning-rate schedule.
            val_loss = evaluate(model, factors[validation], graph, response_scale, labels[validation])  # Select progress using only the fixed development partition.
            history.append({"epoch": epoch, "supervised_loss": float(supervised.detach()), "boundary_loss": float(boundary.detach()), "suspension_physics_loss": float(physics.detach()), "combined_loss": float(loss.detach()), "validation_loss": val_loss, "gradient_norm_before_clipping": float(gradient), "learning_rate": optimizer.param_groups[0]["lr"]})  # Preserve all optimization terms and selection evidence.
            if val_loss < best_loss - 1e-8:  # Accept a strictly improved development result under the fixed selection rule.
                best_loss, best_epoch, best_state, best_optimizer, stale = val_loss, epoch, copy.deepcopy(model.state_dict()), copy.deepcopy(optimizer.state_dict()), 0  # Freeze selected weights and matching optimizer state.
            else:  # Track consecutive updates that do not improve the development error.
                stale += 1  # Advance the predeclared early-stopping counter.
            if stale >= args.patience:  # Stop only according to development progress, never test response.
                break  # Preserve the best earlier model and actual consumed epoch count.
        model.load_state_dict(best_state)  # Restore the independently selected best development checkpoint.
        model.eval()  # Freeze the model for ensemble predictions and final held-out evaluation.
        checkpoint = {"state_dict": best_state, "optimizer_state": best_optimizer, "seed": seed, "best_epoch": best_epoch, "validation_loss": best_loss, "factor_count": factors.shape[1], "width": args.width, "depth": args.depth, "contract": contract, "normalization": {"factor_mean": factor_mean, "factor_scale": factor_scale, "response_scale": response_scale}}  # Save everything needed to recover the selected model and its data contract.
        torch.save(checkpoint, output / f"ensemble_seed_{seed}.pt")  # Persist the actual trained neural graph parameters.
        models.append(model)  # Retain this independently initialized trained predictor for ensemble statistics.
        histories.append({"seed": seed, "epochs": history})  # Preserve full per-member optimization histories.
        seed_receipts.append({"seed": seed, "best_epoch": best_epoch, "epochs_executed": len(history), "best_validation_loss": best_loss})  # Publish finite actual training progress without promising accuracy.
        print(json.dumps(seed_receipts[-1]), flush=True)  # Expose compact progress to the running task without dumping model weights.
    training_seconds = time.perf_counter() - start  # Record the actual ensemble fitting and development cost.
    with torch.no_grad():  # Evaluate every split after all model selection decisions are frozen.
        ensemble = torch.stack([model(factors, graph, response_scale)[0] for model in models])  # Predict actual data from each independent graph model.
        average, deviation = ensemble.mean(dim=0), ensemble.std(dim=0, unbiased=True)  # Separate the ensemble mean response from inter-model disagreement.
        metrics = metrics_for(average, labels, deviation, graph)  # Compute final held-out errors and physical consistency without another update.
        cases = [{"case_id": sample["case_id"], "split": sample["split"], "factors": sample["factors"], **metrics[index], "reference_physics": reference_physics[index]} for index, sample in enumerate(samples)]  # Preserve sample-level evidence and the actual reference residual.
        prediction_payload = {"node_ids": graph.node_ids, "unit": "mm", "cases": [{"case_id": sample["case_id"], "split": sample["split"], "mean_displacement": average[index].tolist(), "ensemble_std": deviation[index].tolist()} for index, sample in enumerate(samples)]}  # Store full source-mapped neural predictions rather than summary-only results.
        candidate_results = []  # Allocate actual ensemble predictions for future active-selection candidates.
        for candidate in manifest.get("candidates", []):  # Evaluate only explicitly declared candidate scenario coordinates.
            physical = torch.tensor([candidate["factors"]], dtype=torch.float32)  # Read the exact candidate's physical load-factor coordinates.
            if physical.shape[1] != graph.load_basis.shape[0] or any(path is None and abs(float(physical[0, index])) > 1e-9 for index, path in enumerate(manifest["load_basis_files"])):  # Require all candidate coordinates to use available source force distributions.
                raise RuntimeError(f"Candidate load pattern is not implemented: {candidate['case_id']}")  # Reject unsupported active wind or malformed scenario vectors.
            normalized = (physical - factor_mean) / factor_scale  # Apply training-only normalization to the unsolved candidate.
            stack = torch.stack([model(normalized, graph, response_scale)[0] for model in models])  # Produce independent candidate graph predictions without FEM labels.
            mean, std = stack.mean(dim=0), stack.std(dim=0, unbiased=True)  # Calculate actual epistemic disagreement across independently trained members.
            distance = float(torch.linalg.vector_norm(factors[train] - normalized, dim=1).min())  # Measure nearest training-input distance as a separately reported coverage diagnostic.
            outside = bool(((physical < physical_factors[train].min(dim=0).values) | (physical > physical_factors[train].max(dim=0).values)).any())  # Flag explicit extrapolation outside the training factor box.
            candidate_results.append({"case_id": candidate["case_id"], "factors": candidate["factors"], "predicted_peak_mm": float(torch.linalg.vector_norm(mean[0], dim=-1).max()), "ensemble_rms_std_mm": float(std.square().mean().sqrt()), "nearest_training_distance": distance, "outside_training_box": outside, **graph.physics_metrics(mean)[0]})  # Publish separate uncertainty, coverage, extrapolation, and mechanics indicators for module C.
    grouped = {split: {"case_count": sum(row["split"] == split for row in cases), "mean_relative_l2": float(np.mean([row["relative_l2"] for row in cases if row["split"] == split])), "mean_rmse_mm": float(np.mean([row["rmse_mm"] for row in cases if row["split"] == split]))} for split in ("train", "validation", "test")}  # Report within-bridge partitions separately without inventing cross-bridge evidence.
    for split, values in grouped.items():  # Attach the original design denominator to every evaluated partition.
        values.update({"expected_case_count": int(expected_counts[split]), "excluded_case_count": sum(sample.get("split") == split for sample in excluded), "complete_reference_coverage": values["case_count"] == int(expected_counts[split])})  # Expose unavailable validation or test references rather than silently shrinking the evaluation population.
    report = {"status": "TRAINED_EVALUATED_HOLD", "engineering_release": "HOLD_UNVALIDATED_SURROGATE", "training_seconds": training_seconds, "seed_receipts": seed_receipts, "splits": grouped, "cases": cases, "candidate_predictions": candidate_results, "cross_bridge_validation": "NOT_RUN_SINGLE_BRIDGE", "physics_scope": contract["physics_equations"], "whole_bridge_equilibrium_residual_implemented": False, "prediction_intervals_calibrated": False}  # Keep model execution success distinct from engineering validity and calibration.
    report.update({"excluded_samples": excluded, "held_out_reference_coverage_complete": all(grouped[split]["complete_reference_coverage"] for split in ("validation", "test"))})  # Retain quarantined cases and explicitly qualify any incomplete held-out evidence.
    write_json(output / "training_history.json", histories)  # Preserve the actual optimizer trajectory for every ensemble member.
    write_json(output / "predictions.json", prediction_payload)  # Save complete source-node response predictions and ensemble spread.
    write_json(output / "metrics.json", report)  # Publish all accuracy, physics, uncertainty, and scope evidence.
    print(json.dumps({"status": report["status"], "training_seconds": training_seconds, "splits": grouped, "output": str(output)}, ensure_ascii=False), flush=True)  # Emit the compact actual run result for orchestration.
    return 0  # Signal completed model execution without equating it with engineering release.


if __name__ == "__main__":  # Keep imports side-effect free for orchestration and meaningful verification.
    raise SystemExit(main())  # Return the actual execution status to the parent runner.
