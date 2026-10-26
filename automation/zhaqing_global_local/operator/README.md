# Zhaqing global / saddle neural operators

This directory implements a **graph neural operator (GNO)** with a learned matrix-valued spatial integral kernel. It does not rename the older degree-averaged message-passing/GRU model. Global and local problems use independent datasets, normalization, checkpoints, and output contracts.

At each layer the numerical integral is

\[
v_{l+1}(x_i)=\sigma\left(W_lv_l(x_i)+\sum_{r}\sum_{j\in B_r(x_i)}K_{l,\theta}(x_i-x_j,a_i,a_j,r)\,v_l(x_j)\,\frac{q_{r,j}}{\mu_{r,\mathrm{ref}}}\right).
\]

`q` is an exported physical quadrature measure, and `mu_ref` is a declared fixed reference measure for that physical relation. It is not node degree. The learned kernel returns a full channel-to-channel matrix. Every original native entity remains present through all layers; edge chunking changes temporary memory only. There is no modal basis, spatial pooling, sampled node subset, or reduced-order finite-element solve inside this network.

Each layer also adds an exact complete-domain constant-kernel integral `W_global sum(q_j v_j) / sum(q_j)`. It gives distant bridge regions a shared loading context without a dense all-pairs matrix; the integration uses every physical source entity and physical mass/volume measures, not an unweighted node mean. Every entity's individual latent state remains present beside this global integral.

The operator family is grounded in [Graph Kernel Network for PDEs](https://arxiv.org/abs/2003.03485) and [Neural Operator: Learning Maps Between Function Spaces](https://jmlr.org/papers/v24/21-1524.html). The **causal pointwise memory gate is this repository's extension**, not a separately established architecture name. It carries path information between input time samples; the spatial operator itself is the explicit integral above. Physics semantics are input fields and relation types. This version does **not** enforce the entire bridge equilibrium, contact complementarity, or a fatigue law inside its loss, so it must not be described as a fully physics-certified operator.

`relations.py` builds fixed physical-radius integration supports. Material/body/structure domains must be selected explicitly by the exporter, and true contact relations come from physical candidate surfaces. Finite-element adjacency alone has shrinking physical support on refinement and does not justify a discretization-invariance claim. The implemented tests check quadrature consistency and relabeling; rotation equivariance of vector/tensor outputs is not implemented. Transfer accuracy on genuinely different bridge meshes still requires independent FEM tests.

## Data qualification

`data.py` verifies complete-history partitions and exact source/input/result/evidence hashes. Training accepts actual converged native histories with every declared native entity retained. Two distinct scopes are supported:

- `drawing_verified_production`: every case declares `DRAWING_VERIFIED` geometry.
- `research_simulation_with_assumptions`: a case may declare `DRAWING_DERIVED_ASSUMPTIONS`, but must supply drawing evidence and an explicit nonempty `geometry_assumptions` list. Successful learning then concerns that documented simulation model, not independently verified as-built response.

Failed FEM solves, arbitrary old two-block friction labels, missing zero-filled contact channels, and unqualified geometry are excluded. Geometry/solver status fields are declarations backed by hashed evidence artifacts; this loader cannot independently certify that a drawing interpretation or material law is correct.

Every case supplies:

| NPZ field | Shape / meaning |
|---|---|
| `coordinates` | `[N,3]`, native physical entity locations |
| `native_entity_ids` | `[N]`, unique node/IP/interface identities |
| `quadrature` | `[N]`, positive declared physical-domain loss measures |
| `static_features` | `[N,F]`, geometry/material/BC/body semantics |
| `controls` | `[T,N,C]` or `[T,C]`, prescribed physical load/boundary functions |
| `targets` | `[T,N,O]`, actual FEM response fields |
| `initial_state` | `[N,O]`, known physical state at initial time |
| `output_mask` | `[N,O]`, actual observed output channels; every declared channel must have coverage |
| `times` | `[T]`, strictly increasing native times |
| `edges` | integer `[2,E]`, source-to-target relation indices |
| `edge_types` | integer `[E]`, declared physical relation vocabulary |
| `edge_measure` | `[E]`, positive physical integration measure before fixed-reference nondimensionalization |

The JSON manifest uses schema `zhaqing_fullfield_gno_dataset_v1`, `family` (`global` or `local`), `scientific_scope`, `field_names`, `field_scale_floor`, `relation_names`, `relation_reference_measures`, `coordinate_scale`, `time_scale`, and `cases`. Each case records `id`, `history_group`, `split`, `quality`, `geometry_status`, `geometry_assumptions` where applicable, `all_native_entities_retained`, `native_entity_count`, `solver_exit_code`, `convergence_verified`, and a `relation_support` description for every relation. Artifact path keys `npz`, `solver_input`, `solver_result`, `convergence_report`, and `geometry_evidence` each have a corresponding `<key>_sha256`.

Train, validation, test, and acquisition-candidate partitions are assigned by **entire loading realization**. Windows, mesh variants, and restarts of the same history group cannot cross partitions. Only the requested partition's arrays are opened. Normalization uses training histories alone. Nonuniform times are weighted by physical elapsed duration; output error includes dynamic-response error and comparison with holding the initial permanent-load response constant.

The predicted function is the change from each native entity's known initial physical state. The entire initial state is also a pointwise input; the decoder adds it back to recover the complete physical field. This is a reversible shift of the state origin, not a reduced displacement basis. Output scales and checkpoint selection use transient-change error, so a large permanent displacement cannot make an unlearned wind response appear accurate. Constant-prestate prediction is reported explicitly as a baseline.

## Execution

Run with a Python environment containing NumPy, SciPy, and PyTorch. The validated environment here uses PyTorch `2.14.1+cpu`, NumPy `2.3.5`, and SciPy `1.17.0`.

```bash
python automation/zhaqing_global_local/operator/test_gno.py # Verify implementation mathematics and execution guards, not bridge fidelity.
python automation/zhaqing_global_local/operator/train.py train --manifest DATASET.json --family global --output RESULTS --epochs 300 --width 8 --depth 2 --window 4 # Train every retained native entity on complete causal histories.
python automation/zhaqing_global_local/operator/train.py train --manifest DATASET.json --family global --output RESULTS --epochs 300 --width 8 --depth 2 --window 4 --resume RESULTS/progress.pt # Resume the exact same frozen experiment and optimizer state.
python automation/zhaqing_global_local/operator/train.py evaluate --manifest DATASET.json --family global --output TEST_RESULTS --checkpoint RESULTS/progress.pt # Evaluate the validation-selected checkpoint on the independent test partition.
```

The requested epoch budget is explicit. An epoch means one visit to every complete training history. Temporal truncated backpropagation bounds gradient memory, while predictions still propagate through every original time step without teacher forcing. Actual optimizer-update counts, source hashes, data hashes, losses, normalization, CPU/GPU RNG, optimizer state, selected weights, and latest weights are saved every completed epoch. A checkpoint is **not** produced when there are no qualified histories.

`training_history.csv` is suitable for Origin or Gnuplot; no Python plot is created. Full numeric predictions are saved as NPZ for independent native field rendering. Ratios are labeled as ratios, not percentages. Independent test evaluation is a separate explicit command; training completion never claims tests or engineering safety passed.

## Error-driven supplementation

`acquisition.shortlist` ranks unsolved candidates by independent-ensemble disagreement multiplied by parameter-space coverage, with diversity within the selected batch. This is a heuristic for deciding what deserves FEM computation, not measured FEM error.

After a successful candidate FEM solve, `reconcile_reference` compares every observed native field over physical time. A **negative / difficult sample** means the actual neural/FEM discrepancy exceeds a predeclared threshold. A nonconverged FEM case is recorded as a solver failure and cannot be a supervised label. Test and validation histories cannot be promoted into training by this function. Incorporating newly solved candidates requires a new frozen manifest and separately recorded training stage.

## Current evidence

Implementation tests are recorded under `results/zhaqing_global_local_20261026/operator/unit_tests.log`. These analytic/unit fixtures establish software behavior only; they do not replace actual global-wind or explicit-wire-saddle training and independent FEM testing. Consult the run-specific completion/status JSON for the actual training state and scientific scope.
