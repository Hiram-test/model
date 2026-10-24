import errno,hashlib,io,json,os,shutil,time,uuid,zipfile # Publish closed derived evidence without changing predictions or metrics.
from pathlib import Path # Keep interrupted and failed exports in visible evidence directories.
import complex_operator as base # Reuse the unchanged numerical evaluator and source digest.
def sync_file(path): # Flush an already closed serialized file before its atomic publication.
    with Path(path).open('rb') as stream: os.fsync(stream.fileno()) # Synchronize the completed bytes without rewriting them.
def sync_directory(path): # Persist publication directory entries where the host supports directory synchronization.
    descriptor=os.open(str(path),os.O_RDONLY) # Open only the parent directory holding published evidence.
    try: os.fsync(descriptor) # Make completed rename operations durable before marking export complete.
    finally: os.close(descriptor) # Release the directory handle on every path.
def check_file(path): # Reject truncated archives and malformed metadata before exposing final evidence.
    path=Path(path) # Resolve both archive and JSON evidence uniformly.
    if path.suffix=='.npz': # Validate every ZIP member rather than only reading the central directory.
        with zipfile.ZipFile(path) as archive: assert archive.testzip() is None,f'Failed archive CRC: {path}' # Require a complete readable full-field archive.
    elif path.suffix=='.json': json.loads(path.read_text()) # Require complete parseable metrics before publication.
    return {'name':path.name,'bytes':path.stat().st_size,'sha256':base.digest(path)} # Record exact serialized identity independently of numerical metrics.
def publish_closed_files(staging,destination): # Atomically publish complete files while retaining any unexpected conflicting evidence.
    staging=Path(staging);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);records=[] # Limit temporary duplication to one strategy at a time.
    for source in sorted(staging.iterdir()): # Each source was completely closed by the unchanged evaluator.
        assert source.is_file(),f'Unexpected nested export entry: {source}';record=check_file(source);sync_file(source);target=destination/source.name # Validate exact bytes before the atomic rename.
        if target.exists(): # Permit exact idempotent replay but never silently overwrite different evidence.
            assert base.digest(target)==record['sha256'],f'Conflicting final export already exists: {target}';source.unlink() # Preserve an existing byte-identical artifact without a redundant copy.
        else: os.replace(source,target) # Publish the fully closed file with one same-filesystem rename.
        sync_directory(destination);assert check_file(target)==record,f'Published evidence changed: {target}';records.append(record) # Verify actual published bytes rather than assuming a successful write is sufficient.
    try: staging.rmdir() # Remove the empty directory without deleting any unexpected residual byte evidence.
    except OSError as error: # Preserve a nonempty staging cleanup anomaly after successful per-file publication.
        if error.errno!=errno.ENOTEMPTY: raise # Do not hide unrelated storage failures or permission errors.
        residual=[] # Retain original identities of every observed residual entry before moving the directory.
        for source in sorted(staging.iterdir()): # Only verified duplicates may coexist with a successful final publication.
            record=check_file(source);target=destination/source.name;assert target.exists() and check_file(target)==record,f'Unverified residual export: {source}';residual.append({'original_path':str(source),'published_path':str(target),**record}) # Any different or truncated residue remains a stopped failed export.
        evidence=destination.parents[1]/'artifact_export_evidence'/f'residual_{staging.name}';evidence.parent.mkdir(parents=True,exist_ok=True);os.replace(staging,evidence);base.write(evidence/'residual_duplicate_receipt.json',{'status':'VERIFIED_RESIDUAL_DUPLICATE_BYTES_PRESERVED','original_staging_path':str(staging),'source_sha256':base.digest(__file__),'observed_cleanup_error':str(error),'records':residual,'classification':'Derived-storage cleanup anomaly; no model change or neural-negative classification.'});sync_directory(evidence.parent) # Preserve the entire residual directory visibly rather than repeatedly deleting reappearing files.
    return records # Successful numerical results require every published file to retain the already checked exact bytes.
def publish_payloads(payloads,staging,destination): # Publish the exact retained serialized bytes, retrying storage only without recomputing neural fields.
    staging=Path(staging);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);experiment=destination.parents[1];records=[];repairs=[] # Keep one strategy's complete serialized payloads in memory until all published files pass.
    for name,payload in payloads.items(): # Preserve the evaluator's case order and publish its metrics only after the complete archives.
        expected=hashlib.sha256(payload).hexdigest();target=destination/name;record={'name':name,'bytes':len(payload),'sha256':expected} # The reference identity is the in-memory complete ZIP, never a possibly truncated filesystem copy.
        if name.endswith('.npz'): # Check the complete ZIP before any filesystem operation.
            with zipfile.ZipFile(io.BytesIO(payload)) as archive: assert archive.testzip() is None # A corrupt in-memory archive cannot be admitted as an authoritative payload.
        if target.exists() and base.digest(target)!=expected: # An already published complete different result may indicate a numerical change and must not be silently overwritten.
            try: check_file(target);valid_existing=True # Distinguish a damaged archive from an unexpected different valid numerical export.
            except (zipfile.BadZipFile,AssertionError,json.JSONDecodeError): valid_existing=False # Storage damage is not a neural prediction discrepancy.
            assert not valid_existing,f'Existing complete output differs from frozen-model replay: {target}' # Preserve exact deterministic replay as a required invariant.
        for attempt in range(3): # Bound storage retries while retaining the identical authoritative bytes across every attempt.
            if target.exists() and base.digest(target)==expected: check_file(target);break # Reuse an exact valid existing archive without generating another independent scientific result.
            if target.exists(): # Preserve any actually observed damaged target before a byte-exact storage repair.
                evidence=experiment/'artifact_export_evidence'/f'damaged_target_{uuid.uuid4().hex}';evidence.mkdir(parents=True);observed={'original_path':str(target),'bytes':target.stat().st_size,'sha256':base.digest(target),'expected_sha256':expected,'attempt':attempt};shutil.copyfile(target,evidence/target.name);base.write(evidence/'damage_receipt.json',observed);repairs.append(observed) # Retain the original bad bytes separately from the complete payload.
            temporary=staging/f'{name}.{uuid.uuid4().hex}.pending' # Give each closed-write transaction a unique visible path.
            with temporary.open('xb') as stream: stream.write(payload);stream.flush();os.fsync(stream.fileno()) # Write only the complete retained serialized bytes and flush before publication.
            assert base.digest(temporary)==expected,'Temporary write differs from retained complete payload';os.replace(temporary,target);sync_directory(destination) # Atomically publish exactly the bytes whose expected SHA was fixed in memory.
        assert target.exists() and base.digest(target)==expected,f'Final publication differs after bounded byte-identical retries: {target}';assert check_file(target)==record;records.append(record) # Verify the complete actual target independently of the successful write return code.
    leftovers=list(staging.iterdir()) # Residual transaction paths are preserved rather than repeatedly deleted or called neural failures.
    if leftovers: # A duplicated or partial temporary path does not replace a separately verified final archive.
        evidence=experiment/'artifact_export_evidence'/f'transaction_residue_{staging.name}';evidence.parent.mkdir(parents=True,exist_ok=True);observed=[{'original_path':str(path),'bytes':path.stat().st_size,'sha256':base.digest(path)} for path in leftovers];os.replace(staging,evidence);base.write(evidence/'residue_receipt.json',{'status':'TRANSACTION_RESIDUE_PRESERVED_FINAL_TARGETS_MATCH_RETAINED_PAYLOADS','records':observed,'expected_payload_records':records}) # Keep all real leftover bytes outside the fixed final-test denominator.
    else: # Empty-directory cleanup is optional housekeeping, never part of the numerical result.
        try: staging.rmdir() # Remove an empty transaction directory if no asynchronous residue appears.
        except OSError as error: # Preserve a late nonempty directory without weakening the already completed target verification.
            if error.errno!=errno.ENOTEMPTY: raise # Do not silently ignore unrelated filesystem errors.
            evidence=experiment/'artifact_export_evidence'/f'late_transaction_residue_{staging.name}';evidence.parent.mkdir(parents=True,exist_ok=True);os.replace(staging,evidence);base.write(evidence/'residue_receipt.json',{'status':'LATE_TRANSACTION_RESIDUE_PRESERVED','expected_payload_records':records}) # Preserve the entire late residue visibly for independent inspection.
    return records,repairs # Report publication and any real observed storage repairs without changing model or reference arrays.
def evaluate_atomic(model,cases,norm,destination): # Change serialization publication only; retain the original exact evaluator and all fields.
    destination=Path(destination);experiment=destination.parents[1];receipt_path=experiment/'final_export_receipts'/f'{destination.name}.json';token=uuid.uuid4().hex;staging=experiment/'final_export_staging'/f'{destination.name}_{token}';started=time.time();payloads={} # Retain one complete strategy's serialized bytes until its final targets are validated.
    if receipt_path.exists(): # Reuse only a fully completed exact-byte export from these unchanged frozen comparison models.
        receipt=json.loads(receipt_path.read_text());assert receipt['status']=='COMPLETE_CRC_CHECKED_ATOMIC_PUBLICATION';assert all(check_file(destination/record['name'])==record for record in receipt['records']);metrics=json.loads((destination/'metrics.json').read_text());assert [row['id'] for row in metrics['cases']]==[case['id'] for case in cases];base.write(experiment/'final_export_reuse_events'/f'{destination.name}_{token}.json',{'original_receipt_sha256':base.digest(receipt_path),'all_complete_archive_bytes_unchanged':True,'source_sha256':base.digest(__file__),'new_numerical_evaluation':False,'time':started});return metrics['cases'] # Do not recount repeated storage recovery as new test histories or new training.
    staging.mkdir(parents=True);original_savez=base.np.savez_compressed;original_write=base.write # Capture only serialization functions; rollout, physical metrics and all field tensors remain unchanged.
    def memory_savez(path,*args,**kwargs): # Serialize the exact original NumPy archive into memory before touching a path.
        path=Path(path);assert path.parent==staging;buffer=io.BytesIO();original_savez(buffer,*args,**kwargs);payloads[path.name]=buffer.getvalue() # Preserve NumPy's exact archive bytes and original argument order.
    def memory_write(path,value): # Capture the evaluator's ordinary metrics JSON without changing its serialization format.
        path=Path(path) # Only this evaluator's staging metadata is intercepted.
        if path.parent==staging: payloads[path.name]=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode() # Match the original base.write encoding, newlines and finite-value checks exactly.
        else: original_write(path,value) # Leave unrelated provenance writes untouched.
    try: # Preserve every partial file and the original error when any export stage fails.
        base.np.savez_compressed=memory_savez;base.write=memory_write # Capture only final serialization while the original evaluator computes the same cold predictions and errors.
        try: rows=base.evaluate(model,cases,norm,staging) # Invoke the unchanged numerical and metric path exactly once for an unfinished strategy.
        finally: base.np.savez_compressed=original_savez;base.write=original_write # Never leave global serialization hooks installed after an exception or normal return.
        records,repairs=publish_payloads(payloads,staging,destination) # Publish exact retained complete bytes without rerunning a model to repair storage.
        receipt={'status':'COMPLETE_CRC_CHECKED_ATOMIC_PUBLICATION','strategy':destination.name,'started_epoch':started,'finished_epoch':time.time(),'source_sha256':base.digest(__file__),'numerical_evaluator_source_sha256':base.digest(base.__file__),'records':records,'numerical_path':'unchanged complex_operator.evaluate; original NumPy and JSON serialization captured in memory','temporary_storage_scope':'one strategy complete retained byte payloads; unique closed temp writes, fsync, atomic replace and full expected-SHA verification','storage_repairs':repairs,'initial_model_and_native_fields_changed':False};receipt_path.parent.mkdir(parents=True,exist_ok=True);temporary=receipt_path.with_name(receipt_path.name+'.pending');base.write(temporary,receipt);sync_file(temporary);os.replace(temporary,receipt_path);sync_directory(receipt_path.parent);return rows # Mark complete only after all final archive bytes are validated.
    except BaseException as error: # Include interruption failures while avoiding any scientific-result relabeling.
        evidence=experiment/'artifact_export_evidence'/f'{destination.name}_{token}';evidence.parent.mkdir(parents=True,exist_ok=True);partial=[{'original_path':str(path),'bytes':path.stat().st_size,'sha256':base.digest(path)} for path in staging.iterdir() if path.is_file()] if staging.exists() else [];shutil.move(str(staging),str(evidence)) if staging.exists() else evidence.mkdir();complete_payloads=[] # Preserve actual failed transaction bytes separately from the authoritative retained serialized payloads.
        for name,payload in payloads.items(): sha=hashlib.sha256(payload).hexdigest();saved=evidence/f'complete_payload_{sha}_{name}';saved.write_bytes(payload);complete_payloads.append({'name':name,'path':str(saved),'bytes':len(payload),'expected_sha256':sha}) # Make a failed complete payload recoverable without another model evaluation.
        base.write(evidence/'failure_receipt.json',{'status':'DERIVED_EXPORT_FAILURE_NOT_NEURAL_NEGATIVE','error_type':type(error).__name__,'error':str(error),'original_staging_path':str(staging),'destination':str(destination),'source_sha256':base.digest(__file__),'partial_files':partial,'complete_in_memory_payloads':complete_payloads,'preserved_epoch':time.time()});raise # Preserve failed bytes in a nonhidden evidence path and stop without changing model or metrics.
