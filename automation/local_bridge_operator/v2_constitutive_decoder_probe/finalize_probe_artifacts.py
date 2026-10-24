import ast,hashlib,io,json,tokenize,zipfile # Finalize completed evidence with standard-library tools only.
from pathlib import Path # Keep the final bundle inside the independently owned research folder.
HERE=Path(__file__).resolve().parent # Resolve provenance paths from this packaging source.
def digest(path): # Hash actual closed artifact bytes without loading scientific libraries.
    h=hashlib.sha256() # Maintain a streaming checksum for checkpoints and logs.
    with path.open('rb') as stream: # Bound temporary memory while hashing each artifact.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Preserve exact byte identity.
    return h.hexdigest() # Return the content identifier stored in the final whitelist.
result=json.loads((HERE/'training/probe_result.json').read_text());status=json.loads((HERE/'probe_status.json').read_text()) # Accept only the already completed, independently stopped experiment.
assert result['status']=='TWO_EPOCH_DEVELOPMENT_PROBE_COMPLETE_NOT_FORMAL_TEST' and status['decision']=='NOT_PROMOTED' and status['actual_process_exit_code']==0 # Reject an incomplete or promoted run.
assert result['work']['actual_optimizer_steps']==96 and result['work']['actual_loss_calls']==384 and result['work']['actual_complete_cold_histories']==16 # Preserve the exact bounded development workload.
assert (HERE/'training/independent_review.json').exists() and (HERE/'training/checkpoint_tensor_audit.json').exists() # Require both independent integrity checks before freezing the evidence.
old_manifest=json.loads((HERE/'publication_manifest.json').read_text()) # Preserve rather than rewrite the historical pretraining publication receipt.
assert len(old_manifest['stable_files'])==7 and all(digest(HERE/item['relative_path'])==item['sha256'] for item in old_manifest['stable_files']) # Confirm every originally frozen source and plan is byte-identical.
source=Path(__file__).read_text();ast.parse(source);comment_lines={token.start[0] for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type==tokenize.COMMENT} # Check the same genuine-comment rule used for every new Python source.
assert all(index in comment_lines for index,line in enumerate(source.splitlines(),1) if line.strip()) # Do not satisfy the rule with strings that merely contain hash characters.
manifest_path=HERE/'final_result_manifest.json';archive_path=HERE/'constitutive_decoder_probe_complete.zip';receipt_path=HERE/'bundle_receipt.json' # Keep manifest, archive and receipt names stable for the parent publisher.
assert not any(path.exists() for path in [manifest_path,archive_path,receipt_path]) # Never silently replace a previously finalized evidence bundle.
files=sorted(path for path in HERE.rglob('*') if path.is_file() and '__pycache__' not in path.parts) # Exclude interpreter cache files while preserving every actual source, log, model and result.
entries=[{'relative_path':str(path.relative_to(HERE)),'bytes':path.stat().st_size,'sha256':digest(path),'status':'CLOSED_FROZEN_SAFE_TO_COPY'} for path in files] # Enumerate exact final artifacts, including selected and epoch checkpoints.
manifest={'schema':'bridge.research.constitutive_decoder.final_result_manifest.v1','decision':'NOT_PROMOTED','scope':'Independent completed original-development architecture; not one of six formal V2 models and not a new-test result.','training_process_exit_code':0,'original_seven_frozen_files_unchanged':True,'historical_publication_commit':'3699854be363c8bcb41b4440038f21d67b0801d5','historical_publication_manifest_pending_status_is_superseded':True,'actual_development_optimizer_steps':96,'actual_loss_calls':384,'actual_complete_cold_histories':16,'checkpoint_sha256':result['checkpoint']['sha256'],'stable_files':entries,'scientific_response_arrays_added':False,'formal_V2_or_new_tests_modified':False} # Make final status explicit without rewriting any pretraining source or plan.
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n') # Freeze the copy whitelist only after all inputs have closed.
with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive: # Produce a small deterministic evidence archive.
    for path in files+[manifest_path]: # Include the final manifest alongside every listed payload.
        info=zipfile.ZipInfo('constitutive_decoder_probe/'+str(path.relative_to(HERE)),date_time=(2000,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16 # Stabilize archive metadata independently of filesystem timestamps.
        archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9) # Write exact source and result bytes without editing their content.
with zipfile.ZipFile(archive_path) as archive: # Verify the actual final archive rather than assuming packaging succeeded.
    assert archive.testzip() is None and len(archive.namelist())==len(entries)+1 # Check CRC integrity and the exact entry count.
    assert all(hashlib.sha256(archive.read('constitutive_decoder_probe/'+item['relative_path'])).hexdigest()==item['sha256'] for item in entries) # Compare every archived payload against the closed source manifest.
    assert hashlib.sha256(archive.read('constitutive_decoder_probe/final_result_manifest.json')).hexdigest()==digest(manifest_path) # Verify the embedded whitelist itself.
receipt={'schema':'bridge.research.constitutive_decoder.bundle_receipt.v1','decision':'NOT_PROMOTED','archive_path':str(archive_path),'archive_bytes':archive_path.stat().st_size,'archive_sha256':digest(archive_path),'manifest_path':str(manifest_path),'manifest_sha256':digest(manifest_path),'payload_file_count':len(entries),'zip_entry_count':len(entries)+1,'all_zip_payload_hashes_verified':True,'training_process_closed':True,'original_seven_frozen_files_unchanged':True,'independent_tensor_audit_sha256':digest(HERE/'training/checkpoint_tensor_audit.json'),'no_new_training_or_solver_calls':True} # Provide a noncircular receipt for transport and persistence.
receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2)) # Return only compact final identifiers to the parent publisher.
