# I08 error and authority-mismatch ledger

## E-I08-AUTH-001 — I07 is not the GitHub 43-scenario library

- Status: `CONTAINED`; disposition: `DEPRECATED_FOR_GITHUB43_AUTHORITY_MATRIX_RETAINED_GATE_REVOKED`.
- Compared I07 matrix: `ccx_run/runs/CW-CCX-MCT-BUF-20260829-I07/I07_EXTREME_CASE_MATRIX.csv`; SHA-256 `53c5274b1d1ee04001325b329ac757547f09757aef5357638fb9101707cb26ca`.
- Exact case-ID overlap: `0/43`; matched IDs: `[]`.
- The I07 case matrix remains byte-for-byte unchanged for provenance; its root execution gate was revoked and its error ledger was annotated after the user correction. It is prohibited from being labelled or reported as the GitHub 43-event library.
- Corrective action: I08 binds the GitHub repository, branch, commit, source blob metadata, exact ordered IDs, and source/derived parameter boundary.

## E-I08-DIAG-001 — post-build I07 preservation probe used one extra parent directory

- Status: `RESOLVED`; the first read-only `sha256sum` probe used `../../CW-...` from the I08 run directory and returned `No such file or directory`.
- Correction: the probe path is `../CW-CCX-MCT-BUF-20260829-I07/I07_EXTREME_CASE_MATRIX.csv`; the corrected read-only hash check confirms the frozen I07 SHA-256.
- Effect: none; no file was created, modified, materialized, or executed by the failed path probe.

## I08 build/runtime status

- Matrix construction errors: none.
- CCX decks materialized: 0.
- CCX solver invocations: 0.
- New response results: none; the I08 outputs are authority and mapping evidence only.

## E-I08-ROOT-001 — optional GNU time wrapper unavailable

- Status: `RESOLVED`; the first pilot materialization command did not enter the production pipeline because `/usr/bin/time` is not installed (`exit 127`).
- Effect: no case directory, load payload, or CCX process was created by this failed wrapper invocation.
- Correction: rerun the identical gated pipeline command without the optional timing wrapper.

## E-I08-ROOT-002 — duplicate pilot staging was left incomplete

- Status: `CONTAINED_QUARANTINED`; a concurrent duplicate materialization attempt left a 14 MB staging directory containing only stiffness, mass, eig, and `LOAD_STATE`, with no deck, audit, ledger, or solver output.
- Effect: none on the published pilot; the official case directory has a complete build ledger and a completed CCX execution audit.
- Corrective action: the exact partial directory was moved, without deletion, to `I08_QUARANTINE/E-I08-PARTIAL-DUPLICATE-PILOT-STAGING.csuxmta6` and is prohibited from result ingestion.

## E-I08-ROOT-003 — preparation self-check could reset a live job record

- Status: `RESOLVED_IN_CODE_PENDING_FINAL_REGRESSION`; the first `write_job_manifest` implementation rebuilt every job entry during self-check and could overwrite live `status` and `artifact_sha256` fields.
- Effect: the official pilot payload, result manifest, and execution evidence remained intact; the solver completed once. The job manifest was restored to `CCX_FINISHED_PENDING_INDEPENDENT_QA` with eight artifact hashes.
- Corrective action: job-manifest publication now uses an exclusive lock and preserves existing per-case production fields. No further self-check is allowed until the regression test confirms retention.

## E-I08-ROOT-004 — first pilot-QA dispatch was intercepted by full-batch preflight

- Status: `OPEN_FIX_IN_PROGRESS`; the first `--mode pilot --case-id ...` call returned `WAITING_FOR_CCX_ARTIFACTS` for the other 42 jobs and did not parse the completed pilot DAT.
- Effect: no false numerical PASS or physical result was produced; solver evidence remains `CCX_FINISHED_PENDING_INDEPENDENT_QA`.
- Corrective action: pilot dispatch must validate and process only its exact manifest mapping while retaining the same per-case hash, FOH, deck, console, DAT, and physical-recovery gates; full-batch aggregation remains all-or-nothing.

## E-I08-ROOT-005 — first pilot wind field did not match the GitHub Davenport contract

- Status: `CONTAINED_SUPERSEDED_PILOT_PENDING_REBUILD`; the first pilot used separable/L1 two-width coherence `exp[-C f (|dx|+W)/U]`, whereas the bound GitHub implementation uses Euclidean separation `exp[-C f sqrt(dx^2+dy^2+dz^2)/U]`.
- A second mismatch was found: independent station-by-station rescaling forced each realized record to the PSD parameter sigma and thereby changed the target Kaimal PSD and cross-spectral coherence.
- Effect: the first pilot may be used only to diagnose deck/FOH/CCX mechanics; it is prohibited from the GitHub-43 result set, knowledge graph metrics, warning simulation, and report response values.
- Corrective action: rebuild the field from the full two-width Euclidean covariance at every active frequency, remove station-wise rescaling, state the finite-band ensemble-sigma contract explicitly, quarantine the first pilot without deletion, then rematerialize and rerun the same GitHub case before releasing the remaining 42.

## E-I08-POST-SELF-CHECK

```text
{
  "status": "FAIL_STATIC_SELF_CHECK",
  "run_id": "CW-CCX-GH43-BUF-20260830-I08",
  "solver_invocations": 0,
  "checks": {
    "authority_hashes_and_order": true,
    "github_original_result_rejected": true,
    "category_schema": true,
    "stationarity_boundary": true,
    "every_nonblank_python_line_commented": true,
    "no_solver_launch_implementation": false,
    "relative_history_gate_is_1e_minus_6": true,
    "ccx_endpoint_gate_uses_print_scaled_absolute_and_1e_minus_6_relative": true,
    "one_e_minus_12_reserved_for_independent_foh_card_closure": true,
    "job_paths_never_inferred": true,
    "job_manifest_optional_during_static_wait": true,
    "master_downstream_contract_declared": true,
    "load_state_contract_declared": true,
    "job_hash_contract_declared": true
  },
  "diagnostics": {
    "uncommented_nonblank_lines": [],
    "forbidden_launch_tokens": [
      "import subprocess",
      "subprocess.run(",
      "os.system(",
      "Popen("
    ]
  },
  "authority": {
    "path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/AUTHORITY.json",
    "sha256": "df10da1c759cea9e93c065d9456e583a1944b7b3eb1a730ea048f1821dddc5b7",
    "repository": "Hiram-test/model",
    "commit": "c1dfa02e12d82b20a1d34c389c501ce782befb49",
    "source_blob_sha1": "9b708839baf8e6ccf76df292556c4d5387bf9da4"
  },
  "matrix": {
    "csv_sha256": "12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f",
    "json_sha256": "8f0ed5a30625b998b982caa32453518abd374f1c2c6312989b2548786e2a7b72",
    "case_count": 43,
    "category_count": 11
  },
  "threshold_contract": {
    "q_v_history_relative_limit": 1e-06,
    "q_v_ccx_endpoint_relative_limit": 1e-06,
    "dat_absolute_limit": "max(1e-2,5e-7*exact_FOH_reference_peak)",
    "exact_independent_foh_card_closure_relative_limit": 1e-12,
    "ccx_output_closure_does_not_use_1e-12": true
  },
  "waiting_behavior": {
    "job_manifest_present": true,
    "when_absent": "WAITING_FOR_EXPLICIT_I08_JOB_MANIFEST",
    "when_any_path_or_hash_missing": "WAITING_FOR_CCX_ARTIFACTS",
    "partial_aggregation_allowed": false
  },
  "stable_output_contract": {
    "case_master_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_MASTER.csv",
    "case_master_required_columns": [
      "github_scenario_id",
      "i08_case_id",
      "category",
      "confidence",
      "stationarity",
      "qa_status",
      "slack_screen_flag",
      "linearity_boundary_status",
      "rope_capacity_status"
    ],
    "rope_results_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ROPE_RESULTS.csv",
    "category_summary_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_CATEGORY_SUMMARY.csv",
    "knowledge_graph_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_KNOWLEDGE_GRAPH.jsonld",
    "triples_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_TRIPLES.csv",
    "completion_signal_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ACCEPTANCE.json",
    "completion_signal": "status=PASS and checks.case_count=43 and checks.all_case_qa_pass=true"
  },
  "input_contract": {
    "job_path_fields": [
      "load_state_path",
      "deck_path",
      "dat_path",
      "console_path",
      "eig_path"
    ],
    "job_artifact_sha256_roles": [
      "load_state",
      "deck",
      "dat",
      "console",
      "eig"
    ],
    "load_state_keys": [
      "time_s",
      "generalized_force",
      "periodic_q0",
      "periodic_v0",
      "frequencies_hz",
      "production_basis_sha256",
      "mean_generalized_force",
      "static_modal_mean"
    ]
  },
  "original_github_response_values_consumed": false
}
```

## E-I08-WIND-005 — Superseded pilot quarantined intact

The 136 MiB first-pilot directory was moved without deletion to `I08_QUARANTINE/E-I08-PILOT-L1-COHERENCE-SUPERSEDED` before corrected rematerialization. It is retained only for traceability and numerical solver diagnostics; it is excluded from final case results, knowledge-graph facts, agent decisions, and Chapter 2 evidence.

## E-I08-FREEZE-006 — Corrected pre-freeze pilot withheld

A final metadata-only `production_controls` patch changed the pipeline SHA after a corrected pilot had been generated and solved. Although that pilot's numerical QA passed, its case and postprocess artifacts were moved intact to `I08_QUARANTINE/E-I08-PILOT-PRE-FREEZE-METADATA*`; release requires a fresh run from frozen pipeline SHA `41ee431b90203697a30f7224ba025a30bbc15af445eda52fe360ca29309ae247`.

## E-I08-STAGING-007 — Dormant staging directory contained

The 14 MiB orphan staging directory `.I08-site_gb50009_50yr-S20260805.staging.p1pk_v86` had no owning process and was moved without deletion to `I08_QUARANTINE/E-I08-ORPHAN-STAGING-p1pk_v86` before final rematerialization.

## E-I08-BATCH-STAGING-008 — Unpublished batch staging residue quarantined

The 42-case materialization command and both locked manifests completed successfully, but a separate directory audit found 33 hidden, unpublished staging directories totaling 554 MiB. They had no owning process and no manifest reference. All were moved intact to `I08_QUARANTINE/E-I08-BATCH-ORPHAN-STAGING-20260830T0321JST`; none is eligible for solving or downstream evidence. Solver launch is conditioned on independent hash-ledger verification of all 43 published case directories.

## E-I08-NPZ-009 — Two semantically corrupt load states blocked before CCX

`I08-ss_cat2-S20260805` and `I08-funing_2016_ef4-S20260805` each contained a 23,055-byte truncated `LOAD_STATE.npz`. Their ledgers matched the corrupt bytes, but `numpy.load` and ZIP central-directory validation failed; therefore CCX was never launched for either case. Both complete directories were moved intact to `I08_QUARANTINE/E-I08-CORRUPT-NPZ-*`. The other 41 published archives passed ZIP integrity validation. The two rejected cases must be rematerialized sequentially and semantically revalidated before execution.

## E-I08-STAGING-010 — Sequential-rerun staging residue quarantined

The two sequential rematerializations left two unpublished 14 MiB staging residues with valid duplicate NPZ files but no complete payload. They were not manifest-referenced and were moved intact to `I08_QUARANTINE/E-I08-RERUN-ORPHAN-STAGING-20260830T0328JST`. Both official replacement cases then passed semantic NPZ checks and completed CCX with return code 0; the read-only 43-case completion screen now passes for every official directory.

## E-I08-QA-READ-011 — Active-output diagnostic read abandoned

A root-side `jq` diagnostic briefly read a case-acceptance file while the frozen full-process writer was still emitting it, producing a null/partial-document query error. No artifact was modified and the read was immediately abandoned; downstream consumption remained locked until process exit and final SHA verification.

## E-I08-DAT-HASH-012 — Five cases rejected for post-audit DAT drift

The first complete frozen QA pass returned `FAIL_CASE_GATES`: 38 cases passed and five were rejected before numerical DAT parsing because their current DAT SHA-256 differed from both manifest and execution-audit hashes. All other nine artifact roles matched. The affected cases were `doksuri_2023_jinjiang`, `mangkhut_2018_peak`, `dorian_2019_landfall`, `andrews_afb_1983_microburst`, and `mt_washington_1934`. Their complete failed runtime evidence and aggregate FAIL record were moved intact to `I08_QUARANTINE/E-I08-DAT-HASH-DRIFT-RERUN-20260830T0338JST`. The build payloads were not altered; remediation is five strictly sequential CCX executions followed by stable-hash checks and one new frozen full QA run.

## E-I08-RSYNC-013 — Scratch synchronization identified as root cause

Filesystem forensics identified a high-confidence synchronization race. Scratch is watched by a two-second-debounced rsync process using `--delay-updates --partial-dir=.rsync-tmp --update --times`; `.I08-*.staging.*` was not excluded. The corrupt NPZ ctime shifts, identical 23,055-byte prefix truncation, preserved-mtime/different-inode ghost files, and an rsync receive-temporary artifact match this mechanism. OOM, disk exhaustion, duplicate root dispatch, and `TemporaryDirectory` behavior were excluded by direct evidence. A later Dorian sequential DAT was again overwritten 2.289 seconds after its preserved mtime, proving that simple serial execution is insufficient. All future CCX runtime and deliverable files must be completed and fsynced outside the synchronized tree (or in exact `.rsync-tmp`) and atomically published, followed by two SHA and semantic checks at least ten seconds apart.

## E-I08-ATOMIC-014 — Pre-remediation runtime evidence isolated

Before the safe executor transition, all 43 current runtime-output sets and the 38 first-pass case acceptances were moved intact to `I08_QUARANTINE/E-I08-PRE-ATOMIC-PUBLISH-RUNTIME-20260830T0343JST` (2.7 GiB). No build payload or authority file was changed. The next accepted evidence set must come entirely from all-43 CCX runs completed under `/tmp` and atomically published after closure.

## E-I08-POST-SELF-CHECK

```text
{
  "status": "FAIL_STATIC_SELF_CHECK",
  "run_id": "CW-CCX-GH43-BUF-20260830-I08",
  "solver_invocations": 0,
  "checks": {
    "authority_hashes_and_order": true,
    "github_original_result_rejected": true,
    "category_schema": true,
    "stationarity_boundary": true,
    "every_nonblank_python_line_commented": true,
    "no_solver_launch_implementation": false,
    "relative_history_gate_is_1e_minus_6": true,
    "ccx_endpoint_gate_uses_print_scaled_absolute_and_1e_minus_6_relative": true,
    "one_e_minus_12_reserved_for_independent_foh_card_closure": true,
    "job_paths_never_inferred": true,
    "job_manifest_optional_during_static_wait": true,
    "master_downstream_contract_declared": true,
    "load_state_contract_declared": true,
    "job_hash_contract_declared": true
  },
  "diagnostics": {
    "uncommented_nonblank_lines": [],
    "forbidden_launch_tokens": [
      "import subprocess",
      "subprocess.run(",
      "os.system(",
      "Popen("
    ]
  },
  "authority": {
    "path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/AUTHORITY.json",
    "sha256": "df10da1c759cea9e93c065d9456e583a1944b7b3eb1a730ea048f1821dddc5b7",
    "repository": "Hiram-test/model",
    "commit": "c1dfa02e12d82b20a1d34c389c501ce782befb49",
    "source_blob_sha1": "9b708839baf8e6ccf76df292556c4d5387bf9da4"
  },
  "matrix": {
    "csv_sha256": "12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f",
    "json_sha256": "8f0ed5a30625b998b982caa32453518abd374f1c2c6312989b2548786e2a7b72",
    "case_count": 43,
    "category_count": 11
  },
  "threshold_contract": {
    "q_v_history_relative_limit": 1e-06,
    "q_v_ccx_endpoint_relative_limit": 1e-06,
    "dat_absolute_limit": "max(1e-2,5e-7*exact_FOH_reference_peak)",
    "exact_independent_foh_card_closure_relative_limit": 1e-12,
    "ccx_output_closure_does_not_use_1e-12": true
  },
  "waiting_behavior": {
    "job_manifest_present": true,
    "when_absent": "WAITING_FOR_EXPLICIT_I08_JOB_MANIFEST",
    "when_any_path_or_hash_missing": "WAITING_FOR_CCX_ARTIFACTS",
    "partial_aggregation_allowed": false
  },
  "stable_output_contract": {
    "case_master_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_MASTER.csv",
    "case_master_required_columns": [
      "github_scenario_id",
      "i08_case_id",
      "category",
      "confidence",
      "stationarity",
      "qa_status",
      "slack_screen_flag",
      "linearity_boundary_status",
      "rope_capacity_status"
    ],
    "rope_results_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ROPE_RESULTS.csv",
    "category_summary_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_CATEGORY_SUMMARY.csv",
    "knowledge_graph_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_KNOWLEDGE_GRAPH.jsonld",
    "triples_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_TRIPLES.csv",
    "completion_signal_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ACCEPTANCE.json",
    "completion_signal": "status=PASS and checks.case_count=43 and checks.all_case_qa_pass=true"
  },
  "input_contract": {
    "job_path_fields": [
      "load_state_path",
      "deck_path",
      "dat_path",
      "console_path",
      "eig_path"
    ],
    "job_artifact_sha256_roles": [
      "load_state",
      "deck",
      "dat",
      "console",
      "eig"
    ],
    "load_state_keys": [
      "time_s",
      "generalized_force",
      "periodic_q0",
      "periodic_v0",
      "frequencies_hz",
      "production_basis_sha256",
      "mean_generalized_force",
      "static_modal_mean"
    ]
  },
  "original_github_response_values_consumed": false
}
```

## E-I08-POST-SELF-CHECK

```text
{
  "status": "FAIL_STATIC_SELF_CHECK",
  "run_id": "CW-CCX-GH43-BUF-20260830-I08",
  "solver_invocations": 0,
  "checks": {
    "authority_hashes_and_order": true,
    "github_original_result_rejected": true,
    "category_schema": true,
    "stationarity_boundary": true,
    "every_nonblank_python_line_commented": true,
    "no_solver_launch_implementation": false,
    "relative_history_gate_is_1e_minus_6": true,
    "ccx_endpoint_gate_uses_print_scaled_absolute_and_1e_minus_6_relative": true,
    "one_e_minus_12_reserved_for_independent_foh_card_closure": true,
    "job_paths_never_inferred": true,
    "job_manifest_optional_during_static_wait": true,
    "master_downstream_contract_declared": true,
    "load_state_contract_declared": true,
    "job_hash_contract_declared": true
  },
  "diagnostics": {
    "uncommented_nonblank_lines": [],
    "forbidden_launch_tokens": [
      "import subprocess",
      "subprocess.run(",
      "os.system(",
      "Popen("
    ]
  },
  "authority": {
    "path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/AUTHORITY.json",
    "sha256": "df10da1c759cea9e93c065d9456e583a1944b7b3eb1a730ea048f1821dddc5b7",
    "repository": "Hiram-test/model",
    "commit": "c1dfa02e12d82b20a1d34c389c501ce782befb49",
    "source_blob_sha1": "9b708839baf8e6ccf76df292556c4d5387bf9da4"
  },
  "matrix": {
    "csv_sha256": "12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f",
    "json_sha256": "8f0ed5a30625b998b982caa32453518abd374f1c2c6312989b2548786e2a7b72",
    "case_count": 43,
    "category_count": 11
  },
  "threshold_contract": {
    "q_v_history_relative_limit": 1e-06,
    "q_v_ccx_endpoint_relative_limit": 1e-06,
    "dat_absolute_limit": "max(1e-2,5e-7*exact_FOH_reference_peak)",
    "exact_independent_foh_card_closure_relative_limit": 1e-12,
    "ccx_output_closure_does_not_use_1e-12": true
  },
  "waiting_behavior": {
    "job_manifest_present": true,
    "when_absent": "WAITING_FOR_EXPLICIT_I08_JOB_MANIFEST",
    "when_any_path_or_hash_missing": "WAITING_FOR_CCX_ARTIFACTS",
    "partial_aggregation_allowed": false
  },
  "stable_output_contract": {
    "case_master_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_MASTER.csv",
    "case_master_required_columns": [
      "github_scenario_id",
      "i08_case_id",
      "category",
      "confidence",
      "stationarity",
      "qa_status",
      "slack_screen_flag",
      "linearity_boundary_status",
      "rope_capacity_status"
    ],
    "rope_results_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ROPE_RESULTS.csv",
    "category_summary_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_CATEGORY_SUMMARY.csv",
    "knowledge_graph_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_KNOWLEDGE_GRAPH.jsonld",
    "triples_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_TRIPLES.csv",
    "completion_signal_path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/I08_POSTPROCESS/I08_43CASE_ACCEPTANCE.json",
    "completion_signal": "status=PASS and checks.case_count=43 and checks.all_case_qa_pass=true"
  },
  "input_contract": {
    "job_path_fields": [
      "load_state_path",
      "deck_path",
      "dat_path",
      "console_path",
      "eig_path"
    ],
    "job_artifact_sha256_roles": [
      "load_state",
      "deck",
      "dat",
      "console",
      "eig"
    ],
    "load_state_keys": [
      "time_s",
      "generalized_force",
      "periodic_q0",
      "periodic_v0",
      "frequencies_hz",
      "production_basis_sha256",
      "mean_generalized_force",
      "static_modal_mean"
    ]
  },
  "original_github_response_values_consumed": false
}
```

## E-I08-PILOT-GATE-I08-site_gb50009_50yr-S20260805

```text
{
  "checks": {
    "job_manifest_hash_binding": true,
    "github_wind_contract": false,
    "complete_time_grid": true,
    "force_endpoint_closed": true,
    "foh_card_periodic": true,
    "q_accuracy": true,
    "v_accuracy": true,
    "periodic_endpoint": true,
    "dummy_q_isolation": true,
    "dummy_v_isolation": true,
    "dynamic_only_deck": true,
    "ccx_2p21_completed": true,
    "accepted_eig_reuse": true,
    "accepted_stiff_reuse": true,
    "accepted_mass_reuse": true,
    "static_modal_solution": true,
    "covariance_symmetric": true
  },
  "metrics": {
    "increment_count": 12000,
    "time_max_abs_error_s": 1.1368683772161603e-13,
    "q_max_abs_error": 0.004998752305255039,
    "q_absolute_error_limit": 0.015490937076643427,
    "q_relative_frobenius_error": 1.380140479677308e-07,
    "v_max_abs_error": 0.000499913634484983,
    "v_absolute_error_limit": 0.01,
    "v_relative_frobenius_error": 8.287093932901121e-08,
    "q_periodic_endpoint_max_abs": 4.117829996630462e-05,
    "q_periodic_endpoint_relative_to_reference_peak": 1.3291093935302178e-09,
    "v_periodic_endpoint_max_abs": 0.0002319679999800428,
    "v_periodic_endpoint_relative_to_reference_peak": 3.4081514257177657e-08,
    "dummy_q_max_abs": 5.79378e-14,
    "dummy_v_max_abs": 1.227474e-13,
    "output_set": "ROM_NODES",
    "force_endpoint_max_abs": 0.0,
    "force_time_mean_max_abs": 1.2854191785057386e-13,
    "force_max_abs": 243.2840034652,
    "static_force_solution_relative_error": 0.0,
    "modal_covariance_trace": 323304831.62783515,
    "modal_covariance_symmetry_max_abs": 0.0,
    "printed_modal_mean_max_abs": 3.6102913863336046e-05,
    "stationarity_half_sigma_relative_difference_max": 0.26280351591976026,
    "stationarity_half_mean_difference_over_sigma_max": 0.2725244408651299
  },
  "wind_build_audit": {
    "status": "FAIL_UPSTREAM_WIND_CONTRACT",
    "explicit_contract_present": false,
    "spatial_distance_metric": null,
    "per_station_sigma_rescaling": null,
    "kaimal_davenport_contract_pass_declared": null,
    "wind_u_spatial_coherence": "separable exp[-C*f*(|dx|+width_indicator*W)/Udeck]",
    "wind_w_spatial_coherence": "separable exp[-C*f*(|dx|+width_indicator*W)/Udeck]",
    "pass": false,
    "failure_meaning": "Solver-state QA may be interpreted only as FOH/deck/DAT closure; the event is not an accepted GitHub Kaimal-Davenport result."
  }
}
```

## E-I08-POST-EXCEPTION-I08-doksuri_2023_jinjiang-S20260805

```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 843, in process_all
    shared_result = evaluate_case_mapping(mapping, source_frequencies, recovery, coefficients)  # Apply the exact same case evaluator used by pilot mode.
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 732, in evaluate_case_mapping
    raise ValueError(f"I08 artifact SHA binding failed for {case_id}: {json.dumps(hash_binding, ensure_ascii=False)}")  # Preserve every expected and actual fingerprint.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I08 artifact SHA binding failed for I08-doksuri_2023_jinjiang-S20260805: {"load_state": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805_LOAD_STATE.npz", "expected_sha256": "e12ed2bf1601454d774696ec89bc013a9e5bdead290265c3fbe7cc61c6605d44", "actual_sha256": "e12ed2bf1601454d774696ec89bc013a9e5bdead290265c3fbe7cc61c6605d44", "match": true}, "deck": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805.inp", "expected_sha256": "b73a835dad6853c54f9b9354e86468bdf45b4d1cf2995b37c17ca44221bcd01c", "actual_sha256": "b73a835dad6853c54f9b9354e86468bdf45b4d1cf2995b37c17ca44221bcd01c", "match": true}, "stiff": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/F01_ROM150_SINGLE.stiff", "expected_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "actual_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "match": true}, "mass": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/F01_ROM150_SINGLE.mass", "expected_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "actual_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "match": true}, "eig": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805.eig", "expected_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "actual_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}, "dat": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805.dat", "expected_sha256": "a97a2451b388b1d8c13059ae9fb5c0aa1c35653cfbb3938877bcff949f18b89f", "actual_sha256": "6a11d92ce9f19473b76e86831220bff1f4c75b586ff14a8e9526bd516742977f", "match": false}, "sta": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805.sta", "expected_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "actual_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "match": true}, "console": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805.console.log", "expected_sha256": "0225a3684cac804a6c74bd0dfd49e7c39fbd4bc948c232284b440ac0b664750c", "actual_sha256": "0225a3684cac804a6c74bd0dfd49e7c39fbd4bc948c232284b440ac0b664750c", "match": true}, "build_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805_BUILD_AUDIT.json", "expected_sha256": "1a6e8738804502d1e7dbbf47bec3d671863a1f6c358848ae5f11f49bcb40e90b", "actual_sha256": "1a6e8738804502d1e7dbbf47bec3d671863a1f6c358848ae5f11f49bcb40e90b", "match": true}, "execution_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-doksuri_2023_jinjiang-S20260805/I08-doksuri_2023_jinjiang-S20260805_EXECUTION_AUDIT.json", "expected_sha256": "45dd321babaf475b38e0dbe2b68eda1c870065e14d2a337c400dcc76ab985d18", "actual_sha256": "45dd321babaf475b38e0dbe2b68eda1c870065e14d2a337c400dcc76ab985d18", "match": true}, "accepted_rom_payloads": {"stiff_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "mass_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "eig_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}}
```

## E-I08-POST-EXCEPTION-I08-mangkhut_2018_peak-S20260805

```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 843, in process_all
    shared_result = evaluate_case_mapping(mapping, source_frequencies, recovery, coefficients)  # Apply the exact same case evaluator used by pilot mode.
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 732, in evaluate_case_mapping
    raise ValueError(f"I08 artifact SHA binding failed for {case_id}: {json.dumps(hash_binding, ensure_ascii=False)}")  # Preserve every expected and actual fingerprint.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I08 artifact SHA binding failed for I08-mangkhut_2018_peak-S20260805: {"load_state": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805_LOAD_STATE.npz", "expected_sha256": "444f52b55de9bb2e566360c689c12bf9c0d60d31646e230c3a88de32858aaafc", "actual_sha256": "444f52b55de9bb2e566360c689c12bf9c0d60d31646e230c3a88de32858aaafc", "match": true}, "deck": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805.inp", "expected_sha256": "46891086c3f772051fc4808af6d5926ce87b55255a7a64112d7d273bf306dd59", "actual_sha256": "46891086c3f772051fc4808af6d5926ce87b55255a7a64112d7d273bf306dd59", "match": true}, "stiff": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/F01_ROM150_SINGLE.stiff", "expected_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "actual_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "match": true}, "mass": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/F01_ROM150_SINGLE.mass", "expected_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "actual_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "match": true}, "eig": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805.eig", "expected_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "actual_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}, "dat": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805.dat", "expected_sha256": "f93300fe5a130c929dd12385e7955f1563262794c5098e1e7215e055680fd44d", "actual_sha256": "d1af0aaff1821716a77fad300d03f90aeb9952287efe2e85c98fd4e1e1caa626", "match": false}, "sta": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805.sta", "expected_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "actual_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "match": true}, "console": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805.console.log", "expected_sha256": "7559b1f7958525424a9a09f190d2f31235838855212ead08e6be122f56802805", "actual_sha256": "7559b1f7958525424a9a09f190d2f31235838855212ead08e6be122f56802805", "match": true}, "build_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805_BUILD_AUDIT.json", "expected_sha256": "9994766a2d6f3aedef2223e178775810ee4c621b36e570d9d8b7d8d9c2e03ec4", "actual_sha256": "9994766a2d6f3aedef2223e178775810ee4c621b36e570d9d8b7d8d9c2e03ec4", "match": true}, "execution_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mangkhut_2018_peak-S20260805/I08-mangkhut_2018_peak-S20260805_EXECUTION_AUDIT.json", "expected_sha256": "1fa199a3fb9dbc6083d28b98d17e5a2e93c2b4cf2f0fee966c56b1f7209e62ac", "actual_sha256": "1fa199a3fb9dbc6083d28b98d17e5a2e93c2b4cf2f0fee966c56b1f7209e62ac", "match": true}, "accepted_rom_payloads": {"stiff_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "mass_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "eig_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}}
```

## E-I08-POST-EXCEPTION-I08-dorian_2019_landfall-S20260805

```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 843, in process_all
    shared_result = evaluate_case_mapping(mapping, source_frequencies, recovery, coefficients)  # Apply the exact same case evaluator used by pilot mode.
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 732, in evaluate_case_mapping
    raise ValueError(f"I08 artifact SHA binding failed for {case_id}: {json.dumps(hash_binding, ensure_ascii=False)}")  # Preserve every expected and actual fingerprint.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I08 artifact SHA binding failed for I08-dorian_2019_landfall-S20260805: {"load_state": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805_LOAD_STATE.npz", "expected_sha256": "0d620637c7d1ba4023965ac9e45c020918126e09624a4dbd22fe2843a58dbcf1", "actual_sha256": "0d620637c7d1ba4023965ac9e45c020918126e09624a4dbd22fe2843a58dbcf1", "match": true}, "deck": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805.inp", "expected_sha256": "244f74177951697a7c689beefe0229b17fee43b63e30947633bc88cbbc91dfca", "actual_sha256": "244f74177951697a7c689beefe0229b17fee43b63e30947633bc88cbbc91dfca", "match": true}, "stiff": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/F01_ROM150_SINGLE.stiff", "expected_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "actual_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "match": true}, "mass": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/F01_ROM150_SINGLE.mass", "expected_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "actual_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "match": true}, "eig": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805.eig", "expected_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "actual_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}, "dat": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805.dat", "expected_sha256": "42f2354df34d4bd941c229853422a0031492757428dbdf297f37b9aa10889afa", "actual_sha256": "5e3befff3ee253eb962e0592d3ea3075c29fccc18e49d3b20cd6ee077dc318f6", "match": false}, "sta": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805.sta", "expected_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "actual_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "match": true}, "console": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805.console.log", "expected_sha256": "e2dd239b1b3f6520dd63241a0d54d0ee1f63a6ba8dc9be16d593d452e07dbb93", "actual_sha256": "e2dd239b1b3f6520dd63241a0d54d0ee1f63a6ba8dc9be16d593d452e07dbb93", "match": true}, "build_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805_BUILD_AUDIT.json", "expected_sha256": "1e118a1a449d64fe514114f96c687037256fb213ffbe7645acd949408ac75b16", "actual_sha256": "1e118a1a449d64fe514114f96c687037256fb213ffbe7645acd949408ac75b16", "match": true}, "execution_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-dorian_2019_landfall-S20260805/I08-dorian_2019_landfall-S20260805_EXECUTION_AUDIT.json", "expected_sha256": "f581635d1ddbef146993712e6d026f5f8727b8588463765b4a22b18d58453b51", "actual_sha256": "f581635d1ddbef146993712e6d026f5f8727b8588463765b4a22b18d58453b51", "match": true}, "accepted_rom_payloads": {"stiff_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "mass_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "eig_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}}
```

## E-I08-POST-EXCEPTION-I08-andrews_afb_1983_microburst-S20260805

```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 843, in process_all
    shared_result = evaluate_case_mapping(mapping, source_frequencies, recovery, coefficients)  # Apply the exact same case evaluator used by pilot mode.
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 732, in evaluate_case_mapping
    raise ValueError(f"I08 artifact SHA binding failed for {case_id}: {json.dumps(hash_binding, ensure_ascii=False)}")  # Preserve every expected and actual fingerprint.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I08 artifact SHA binding failed for I08-andrews_afb_1983_microburst-S20260805: {"load_state": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805_LOAD_STATE.npz", "expected_sha256": "6e4b6ae8ab590ec8a4b06123802b4bf7486695dfeb9370440042f92385905a3a", "actual_sha256": "6e4b6ae8ab590ec8a4b06123802b4bf7486695dfeb9370440042f92385905a3a", "match": true}, "deck": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805.inp", "expected_sha256": "a0838657158c3b21c842c3e817f8d903722219a4f7148d25501aa8e43d65f27c", "actual_sha256": "a0838657158c3b21c842c3e817f8d903722219a4f7148d25501aa8e43d65f27c", "match": true}, "stiff": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/F01_ROM150_SINGLE.stiff", "expected_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "actual_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "match": true}, "mass": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/F01_ROM150_SINGLE.mass", "expected_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "actual_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "match": true}, "eig": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805.eig", "expected_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "actual_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}, "dat": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805.dat", "expected_sha256": "6decba91e90538156d4dff9f63b15c35efaa7032a7337e1fdc8e02d33df96956", "actual_sha256": "f98a194acbd6eec29a1f89ca22699c52974782dd0cc0163033142f516581115c", "match": false}, "sta": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805.sta", "expected_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "actual_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "match": true}, "console": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805.console.log", "expected_sha256": "fcd954aa5db7566cfef408eec093843472ca20a4282ce5be8c2fdbd6aafa503e", "actual_sha256": "fcd954aa5db7566cfef408eec093843472ca20a4282ce5be8c2fdbd6aafa503e", "match": true}, "build_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805_BUILD_AUDIT.json", "expected_sha256": "4386e0877f8e151b5edfddaed79f31b48d29e20c1d7fcd3dcfc3c91003a3fcac", "actual_sha256": "4386e0877f8e151b5edfddaed79f31b48d29e20c1d7fcd3dcfc3c91003a3fcac", "match": true}, "execution_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-andrews_afb_1983_microburst-S20260805/I08-andrews_afb_1983_microburst-S20260805_EXECUTION_AUDIT.json", "expected_sha256": "0db38f1f259a3a26d59b53ef4defbe32ef77466e8cd6c64c9b9568a29fb4e591", "actual_sha256": "0db38f1f259a3a26d59b53ef4defbe32ef77466e8cd6c64c9b9568a29fb4e591", "match": true}, "accepted_rom_payloads": {"stiff_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "mass_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "eig_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}}
```

## E-I08-POST-EXCEPTION-I08-mt_washington_1934-S20260805

```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 843, in process_all
    shared_result = evaluate_case_mapping(mapping, source_frequencies, recovery, coefficients)  # Apply the exact same case evaluator used by pilot mode.
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/audit_i08_github43_dat_postprocess.py", line 732, in evaluate_case_mapping
    raise ValueError(f"I08 artifact SHA binding failed for {case_id}: {json.dumps(hash_binding, ensure_ascii=False)}")  # Preserve every expected and actual fingerprint.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I08 artifact SHA binding failed for I08-mt_washington_1934-S20260805: {"load_state": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805_LOAD_STATE.npz", "expected_sha256": "8311371b496260e535d3101fd45029656f20408211b3d39163f4e9f2f794fa2f", "actual_sha256": "8311371b496260e535d3101fd45029656f20408211b3d39163f4e9f2f794fa2f", "match": true}, "deck": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805.inp", "expected_sha256": "bf6bedd5e80d7d1c32de41bc78281f5c43d84d210fc3ba3216462678a127d913", "actual_sha256": "bf6bedd5e80d7d1c32de41bc78281f5c43d84d210fc3ba3216462678a127d913", "match": true}, "stiff": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/F01_ROM150_SINGLE.stiff", "expected_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "actual_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "match": true}, "mass": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/F01_ROM150_SINGLE.mass", "expected_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "actual_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "match": true}, "eig": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805.eig", "expected_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "actual_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}, "dat": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805.dat", "expected_sha256": "454bfefe18353f137e388126f859e764cbf42706cc17eb97d8517f883e4c0716", "actual_sha256": "f9c49e294a4223e4a7459b3d7ecf8c3b4f6b48043eec91f18dc87bce382c3be9", "match": false}, "sta": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805.sta", "expected_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "actual_sha256": "20946efba93047e4092386fb9fedd29e43961806698459a19066356660f2e1a9", "match": true}, "console": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805.console.log", "expected_sha256": "1bc630f7158a205382ef5cf3dba0b7d87e6b93e86c86ee2c8e6b7558bed13197", "actual_sha256": "1bc630f7158a205382ef5cf3dba0b7d87e6b93e86c86ee2c8e6b7558bed13197", "match": true}, "build_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805_BUILD_AUDIT.json", "expected_sha256": "1e23f5509c77444f0731fa02df11b63d024522bda2d35f0ce443c832a578f963", "actual_sha256": "1e23f5509c77444f0731fa02df11b63d024522bda2d35f0ce443c832a578f963", "match": true}, "execution_audit": {"path": "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/cases/I08-mt_washington_1934-S20260805/I08-mt_washington_1934-S20260805_EXECUTION_AUDIT.json", "expected_sha256": "9b31b5c32191c4de043be1fb19c94470f8a4d7f11d3984eb6d3b2b76dcce0546", "actual_sha256": "9b31b5c32191c4de043be1fb19c94470f8a4d7f11d3984eb6d3b2b76dcce0546", "match": true}, "accepted_rom_payloads": {"stiff_sha256": "22d7650d18e2168bb32880a7ad0508b5bdea7b811334c7988372ecc4f25ed385", "mass_sha256": "3dffa1d256cdf3863ebf43cdd215a606eace56cbc3cca90671ba499d2ade97b5", "eig_sha256": "f8862ea2de59568850a2cbaee35a37c29e85d54941a6d454edd4afae5e90cea0", "match": true}}
```

## E-I08-POST-READONLY-STATS-001

```text
A read-only final-statistics probe selected response labels without their explicit unit suffixes (lateral_common instead of lateral_common_m, etc.) and raised ValueError: attempt to get argmax of an empty sequence after already printing valid global response extrema. No accepted artifact, solver result, QA gate, or aggregate CSV was modified. Correction: rerun the read-only probe using exact response labels from I08_43CASE_STATION_RESULTS.csv.
```
