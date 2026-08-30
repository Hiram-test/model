# I08 error log

- E-I08-PATCH-001: Initial monolithic pipeline patch was rejected atomically because the authority agent concurrently changed the expected I08_BUILD_LOG heading. No partial pipeline or payload was created; the pipeline was reissued in smaller patches against the corrected authority hashes.

- E-I08-PIPELINE: ```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 626, in main
    gate = validate_root_gate(args.gate.resolve(), args.action, args.case_id)  # Bind the exact action, case, authority, and gate SHA.
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 308, in validate_root_gate
    raise PermissionError(f"I08 root gate does not allow case {case_id}")  # Block the remaining forty-two cases.
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: I08 root gate does not allow case I08-site_gb50009_100yr-S20260805
```

- E-I08-WIND-CONTRACT-001: The first pilot payload used separable L1 span-plus-width Davenport coherence and per-station realization sigma rescaling. It is invalid for the GitHub Euclidean Kaimal-Davenport contract and must be quarantined; it may be retained only for solver-numerical diagnostics. Pipeline SHA-256 02b88fe409d2c343bb4ac9507153f7c769351a92c225ac0192adc488c57c56cc replaces it with fixed-M=2048 exact two-line Euclidean joint covariance and no realization rescaling.

- E-I08-WIND-CONTRACT-002: The complete 136 MiB superseded pilot directory was moved without deletion from `cases/I08-site_gb50009_50yr-S20260805` to `I08_QUARANTINE/E-I08-PILOT-L1-COHERENCE-SUPERSEDED` before corrected rematerialization. Its solver outputs remain diagnostic-only and are prohibited from the final 43-case manifest, knowledge graph, agent simulation, and Chapter 2.

- E-I08-SOURCE-FREEZE-001: A numerically valid corrected pilot was generated and solved immediately before a final metadata-only `production_controls` addition changed the frozen pipeline SHA-256 from `02b88fe409d2c343bb4ac9507153f7c769351a92c225ac0192adc488c57c56cc` to `41ee431b90203697a30f7224ba025a30bbc15af445eda52fe360ca29309ae247`. To keep generation source, manifest, and evidence provenance identical, the 136 MiB case and its pilot postprocess were moved intact to `I08_QUARANTINE/E-I08-PILOT-PRE-FREEZE-METADATA` and `I08_QUARANTINE/E-I08-PILOT-PRE-FREEZE-METADATA-POSTPROCESS`; their otherwise passing QA is trace-only and not a release basis.

- E-I08-STAGING-002: A dormant 14 MiB orphan staging directory `.I08-site_gb50009_50yr-S20260805.staging.p1pk_v86` contained only mass, stiffness, eigenvalue, and LOAD_STATE files and no running process owned it. It was moved without deletion to `I08_QUARANTINE/E-I08-ORPHAN-STAGING-p1pk_v86` before the final frozen-source pilot.

- E-I08-BATCH-STAGING-003: After the 42-case parallel materialization returned zero and both locked manifests reported exactly one `CCX_FINISHED_PENDING_INDEPENDENT_QA` plus forty-two `MATERIALIZED_NOT_EXECUTED`, a separate filesystem check found 33 unpublished hidden staging directories (554 MiB total). No production or CCX process owned them; none was referenced by either manifest. All 33 were moved without deletion to `I08_QUARANTINE/E-I08-BATCH-ORPHAN-STAGING-20260830T0321JST`. The 43 published case directories remain subject to independent ledger/hash verification before solver launch.

- E-I08-NPZ-004: Pre-execution semantic loading rejected `I08-ss_cat2-S20260805` and `I08-funing_2016_ef4-S20260805`: each published `LOAD_STATE.npz` was a truncated 23,055-byte ZIP without an end-of-central-directory record. Their byte ledgers matched the already-corrupt files, so byte hashing alone could not establish semantic readability. CCX was never launched for either case. Both complete case directories were moved intact to `I08_QUARANTINE/E-I08-CORRUPT-NPZ-I08-ss_cat2-S20260805` and `I08_QUARANTINE/E-I08-CORRUPT-NPZ-I08-funing_2016_ef4-S20260805`. The remaining 41 published NPZ archives passed `unzip -t`; only these two cases will be rematerialized sequentially and revalidated before execution.

- E-I08-STAGING-005: Sequential rematerialization of the two rejected cases produced two additional unpublished 14 MiB staging residues containing byte-identical valid `LOAD_STATE.npz` files but no deck/audit/ledger. Neither residue was manifest-referenced or process-owned. They were moved intact to `I08_QUARANTINE/E-I08-RERUN-ORPHAN-STAGING-20260830T0328JST`. The published replacements passed ZIP integrity, NumPy schema/shape checks, CCX return code 0, execution-audit status, and `Job finished`; all 43 official cases now pass the same read-only semantic and solver-completion screen.

- E-I08-DAT-HASH-006: The first frozen full-process QA correctly emitted `FAIL_CASE_GATES` (38 accepted, 5 rejected) because DAT bytes no longer matched the hashes recorded atomically after solver completion for `doksuri_2023_jinjiang`, `mangkhut_2018_peak`, `dorian_2019_landfall`, `andrews_afb_1983_microburst`, and `mt_washington_1934`. All nine other artifact roles matched; the five cases were rejected before DAT numerical parsing. This pattern is consistent with a same-basename writer race but is not asserted as proven root cause. Every failed runtime output, execution audit, failed case acceptance, and the aggregate FAIL record was moved intact to `I08_QUARANTINE/E-I08-DAT-HASH-DRIFT-RERUN-20260830T0338JST`. The immutable build payloads remain in place; each of the five cases will be re-executed strictly sequentially, with post-run hash stability verified before one new full QA run.

- E-I08-RSYNC-ROOT-007: Read-only forensics established high-confidence root cause as the workspace scratch synchronization layer, not duplicate pipeline dispatch, `TemporaryDirectory`, OOM, disk capacity, or CalculiX numerics. `/usr/local/scripts/sync_share.sh` watches scratch, waits two seconds, then runs `rsync -a --delay-updates --partial-dir=.rsync-tmp --update --times`; the production `.I08-*.staging.*` names were not excluded. The two truncated NPZ files had ctime shifts of +2.342 s and +2.380 s relative to preserved mtimes, and both were the identical first 23,055 bytes ending exactly after the first ZIP member. Ghost staging files preserved source mtime but had later ctime and different inodes, including an rsync receive-temporary file. After five sequential CCX reruns, Dorian DAT was again replaced +2.289 s after its preserved mtime, directly confirming that direct writes under scratch remain unsafe. Remediation is therefore upgraded: CCX must finish and fsync in `/tmp`, then atomically publish complete runtime files; QA/PDF/KG outputs must likewise stage outside sync or in exact `.rsync-tmp`, atomically replace final names, and pass two stable SHA/semantic checks at least ten seconds apart.

- E-I08-ATOMIC-TRANSITION-008: Before deploying the `/tmp` atomic-publication executor, all 43 current runtime sets (`dat`, `sta`, `console`, optional `frd/cvg/12d`, and execution audit) plus the 38 first-pass case acceptances were moved without deletion to `I08_QUARANTINE/E-I08-PRE-ATOMIC-PUBLISH-RUNTIME-20260830T0343JST` (2.7 GiB). Build payloads, authority, and manifests were not altered. This prevents any pre-remediation runtime byte from being mistaken for the forthcoming all-43 atomic rerun.

- E-I08-PIPELINE: ```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 760, in main
    return_code = execute_case(case, gate)  # Launch CCX only after the exact gate and payload hash checks pass.
                  ^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 640, in execute_case
    payload_hashes = verify_materialized_case(case)  # Revalidate every prepared artifact.
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 631, in verify_materialized_case
    with np.load(case_dir / f"{case_id}_LOAD_STATE.npz") as state:  # Inspect the exact QA interface keys.
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 471, in load
    ret = NpzFile(fid, own_fid=own_fid, allow_pickle=allow_pickle,
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 197, in __init__
    _zip = zipfile_factory(fid)
           ^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 112, in zipfile_factory
    return zipfile.ZipFile(file, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/zipfile/__init__.py", line 1370, in __init__
    self._RealGetContents()
  File "<PYTHON_RUNTIME>/lib/python3.12/zipfile/__init__.py", line 1437, in _RealGetContents
    raise BadZipFile("File is not a zip file")
zipfile.BadZipFile: File is not a zip file
```

- E-I08-QA-VALIDATOR-009 (resolved): The first root-level postprocess stability assertion treated the mere existence of the two empty atomic-publication directories `I08_POSTPROCESS/.rsync-tmp` and `I08_POSTPROCESS/case_acceptance/.rsync-tmp` as staging residue. The assertion stopped after all 493 SHA-ledger entries had already matched. Read-only inspection confirmed both directories contained zero payload files. The release check was corrected to reject temporary payloads, not the intentionally persistent empty staging directories; no QA artifact was changed or regenerated.

- E-I08-PIPELINE: ```text
Traceback (most recent call last):
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 760, in main
    return_code = execute_case(case, gate)  # Launch CCX only after the exact gate and payload hash checks pass.
                  ^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 640, in execute_case
    payload_hashes = verify_materialized_case(case)  # Revalidate every prepared artifact.
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<RUN_ROOT>/ccx_run/runs/CW-CCX-GH43-BUF-20260830-I08/i08_production_pipeline.py", line 631, in verify_materialized_case
    with np.load(case_dir / f"{case_id}_LOAD_STATE.npz") as state:  # Inspect the exact QA interface keys.
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 471, in load
    ret = NpzFile(fid, own_fid=own_fid, allow_pickle=allow_pickle,
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 197, in __init__
    _zip = zipfile_factory(fid)
           ^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/site-packages/numpy/lib/_npyio_impl.py", line 112, in zipfile_factory
    return zipfile.ZipFile(file, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<PYTHON_RUNTIME>/lib/python3.12/zipfile/__init__.py", line 1370, in __init__
    self._RealGetContents()
  File "<PYTHON_RUNTIME>/lib/python3.12/zipfile/__init__.py", line 1437, in _RealGetContents
    raise BadZipFile("File is not a zip file")
zipfile.BadZipFile: File is not a zip file
```
