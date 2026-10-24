import json,os,shutil,time,uuid,zipfile # Publish closed derived evidence without changing predictions or metrics.
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
    staging.rmdir();return records # Remove only the now-empty staging directory after all files pass.
def evaluate_atomic(model,cases,norm,destination): # Change serialization publication only; retain the original exact evaluator and all fields.
    destination=Path(destination);experiment=destination.parents[1];token=uuid.uuid4().hex;staging=experiment/'final_export_staging'/f'{destination.name}_{token}';staging.mkdir(parents=True);started=time.time() # Use a visible unique staging directory that remains inspectable after abrupt interruption.
    try: # Preserve every partial file and the original error when any export stage fails.
        rows=base.evaluate(model,cases,norm,staging);records=publish_closed_files(staging,destination) # Invoke the unchanged numerical and metric path exactly once per strategy.
        receipt={'status':'COMPLETE_CRC_CHECKED_ATOMIC_PUBLICATION','strategy':destination.name,'started_epoch':started,'finished_epoch':time.time(),'source_sha256':base.digest(__file__),'numerical_evaluator_source_sha256':base.digest(base.__file__),'records':records,'numerical_path':'unchanged complex_operator.evaluate','temporary_storage_scope':'one strategy; each closed archive CRC checked before and after os.replace','initial_model_and_native_fields_changed':False};receipt_path=experiment/'final_export_receipts'/f'{destination.name}.json';receipt_path.parent.mkdir(parents=True,exist_ok=True);temporary=receipt_path.with_name(receipt_path.name+'.pending');base.write(temporary,receipt);sync_file(temporary);os.replace(temporary,receipt_path);sync_directory(receipt_path.parent);return rows # Mark complete only after all final archive bytes are validated.
    except BaseException as error: # Include interruption failures while avoiding any scientific-result relabeling.
        evidence=experiment/'artifact_export_evidence'/f'{destination.name}_{token}';evidence.parent.mkdir(parents=True,exist_ok=True);partial=[{'original_path':str(path),'bytes':path.stat().st_size,'sha256':base.digest(path)} for path in staging.iterdir() if path.is_file()] if staging.exists() else [];shutil.move(str(staging),str(evidence)) if staging.exists() else evidence.mkdir();base.write(evidence/'failure_receipt.json',{'status':'DERIVED_EXPORT_FAILURE_NOT_NEURAL_NEGATIVE','error_type':type(error).__name__,'error':str(error),'original_staging_path':str(staging),'destination':str(destination),'source_sha256':base.digest(__file__),'partial_files':partial,'preserved_epoch':time.time()});raise # Preserve failed bytes in a nonhidden evidence path and stop without changing model or metrics.
