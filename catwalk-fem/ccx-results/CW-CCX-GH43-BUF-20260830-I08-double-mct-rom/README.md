# CW-CCX-GH43-BUF-20260830-I08 — double-MCT / 150-mode ROM baseline

## Status

`FROZEN_NUMERICAL_EVIDENCE_DOUBLE_MCT_ROM`

This directory publishes the current CalculiX baseline before the element-level true-3D rebuild. It is intentionally labelled as a bounded reference and must not be interpreted as a true-3D cable-system result.

## Model identity

- Physical source: double-MCT catwalk representation with two catwalk widths, carrying ropes, gantry ropes, ordinary gantries and condensed passage stations.
- Production dynamics: 150 source-basis prestressed tangent modes.
- CalculiX role: actual `*FREQUENCY` and modal-dynamic execution in generalized coordinates.
- CalculiX deck topology: 51 bookkeeping nodes, 153 generalized equations, zero physical `*ELEMENT` records, 150 modal coordinates and 3 dummy coordinates.
- Physical recovery: absolute station responses and rope-force statistics recovered from the locked source basis.
- Missing true-3D capability: no element-level geometry update, cable slack/contact redistribution or direct three-dimensional connectivity solve during the 600 s cases.

Therefore:

`double-MCT physical source -> 150-mode ROM -> CalculiX execution` is not equivalent to `true-3D elements -> nonlinear equilibrium -> prestressed eigenproblem -> direct dynamic solve`.

## Authority

- Repository source: `Hiram-test/model`
- Source branch: `cursor/agentic-catwalk-fea-d416`
- Source commit: `c1dfa02e12d82b20a1d34c389c501ce782befb49`
- Exact 43-case source: `catwalk-fem/true3d-extreme/artifacts/extreme_weather_library.json`
- Source blob SHA-1: `9b708839baf8e6ccf76df292556c4d5387bf9da4`

The `true3d-extreme` directory name identifies where the authoritative 43-case weather library is stored; it does not make this result a true-3D finite-element calculation. Likewise, `FULLMCT` in retained filenames is a historical label for the complete imported double-MCT source and must not be read as element-level true 3D.

`authority/AUTHORITY.json` is the frozen pre-execution authority snapshot, so its `execution_scope` correctly records zero invocations at that point. The later 43 executions are evidenced by `execution/I08_JOB_MANIFEST.json`, `execution/I08_RESULT_MANIFEST.json` and `results/I08_43CASE_ACCEPTANCE.json`.

## Frozen numerical result

- 43/43 new CalculiX cases returned zero.
- Independent per-case QA: 43/43 `PASS`.
- Case classes: 35 `stationary_ok`; 8 `reference_only`.
- Knowledge graph: 2520 nodes; 2953 edges.
- Agent decisions: 12 `STOP_AND_NONLINEAR_REVIEW`, 4 `REFERENCE_ONLY_NONSTATIONARY`, 27 `NUMERICAL_EVIDENCE_READY_HUMAN_REVIEW`, 0 waiting.
- Warning policy: 43/43 `NOT_ARMED`; `dispatch=false`.

The 5 s interval recorded in `model/FULLMCT_ROM_BUILD_AUDIT.json` is the ROM gate check; each of the 43 production cases uses the 600 s duration recorded by the job/result manifests.

The word `PASS` only denotes numerical evidence completeness and exact-FOH/computation-chain closure. It is not a structural-safety, construction-release or operational-warning approval.

## Published contents

- `authority/`: exact GitHub case authority and ordered 43-case matrix.
- `execution/`: root gate, atomic stability audit, job manifest and result manifest.
- `model/`: exact 150-mode coordinate map, ROM audit, and frequency/dynamic/static gate evidence.
- `results/`: acceptance, 43-case master table, station table, category envelopes and the 493-entry source SHA ledger.
- `kg/`: deterministic four-agent traces, graph build status, self-check and graph SHA ledger.
- `document/`: result summary and delivery SHA references.
- `errors/`: solver/publishing/KG/PDF error histories.

The 28 MB row-level rope table, 6.9 MB covariance payload, 5 MB PDF and 38.5 MB evidence ZIP are identified by their frozen SHA ledgers but are not duplicated into this Git tree. The master table contains every case-level response, critical rope result, slack-screen count and interpretation boundary needed to review the present baseline. Large binary evidence remains a release-scale artifact.

## Public-copy normalization

This Git view preserves numerical values, case identities and evidence hashes while removing private conversation text and normalizing ephemeral runtime prefixes to `<RUN_ROOT>` and `<PYTHON_RUNTIME>`. The private frozen evidence package retains the original run-local paths. Public-copy file integrity is recorded by this directory's `SHA256SUMS.txt`.

## Supersession rule

Future true-3D results must use a separate run ID and must pass all of the following before comparison:

1. topology closure and connected-component gate;
2. node/element/section/material identity gate;
3. mass and gravity-resultant gate;
4. boundary and reaction-closure gate;
5. prestress and static-shape gate;
6. frequency, MAC and modal-subspace gate;
7. load-projection/work-equivalence gate;
8. direct physical-response recovery gate.

Until those gates pass, this directory remains the frozen current baseline rather than a true-3D validation target.
