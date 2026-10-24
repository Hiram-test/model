import ast,hashlib,json,struct,sys,zipfile # Independently inspect completed released friction slots using only the standard library.
from pathlib import Path # Keep all evidence under the independent audit directory and never write native results.
sys.dont_write_bytecode=True;ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audit';BUFFER=1024*1024 # Bound each streaming read to one MiB while other native jobs are running.
def stream_digest(stream): # Consume every byte so compressed members also undergo their native ZIP CRC verification.
    digest=hashlib.sha256();size=0 # Record actual byte counts instead of trusting the directory alone.
    while True: # A complete read is mandatory for each raw file or archive member.
        block=stream.read(BUFFER) # Avoid retaining large reference fields or solver output in memory.
        if not block: break # Exit only at the actual end of the member.
        digest.update(block);size+=len(block) # Hash the original bytes without changing their representation.
    return digest.hexdigest(),size # Keep independent full-member SHA identities beside CRC validation.
def reference(path): # Bind all observations to concrete paths and current unchanged bytes.
    path=Path(path) # Normalize file access without changing the native location.
    with path.open('rb') as stream: digest,size=stream_digest(stream) # Stream the original file once.
    return {'path':str(path),'sha256':digest,'bytes':size} # Byte counts distinguish complete files from truncated artifacts.
def checked(ref): # Validate producer or release expectations before using the referenced JSON.
    actual=reference(ref['path']);assert actual['sha256']==ref['sha256'],ref['path'];return Path(ref['path']) # Never reset expected hashes after observing a different file.
def read(path): return json.loads(Path(path).read_text()) # JSON metadata is small and contains no deserialized neural response tensor.
def signature(path): # Detect producer changes during the independent read.
    value=Path(path).stat();return (value.st_size,value.st_mtime_ns,value.st_ino) # Both byte hash and file metadata are checked at closure.
def npy_header(stream): # Parse NPY metadata directly without importing NumPy or Torch.
    assert stream.read(6)==b'\x93NUMPY';major,minor=stream.read(2);assert major in (1,2,3) # Reject non-NPY payloads or unknown format revisions.
    width=2 if major==1 else 4;length=int.from_bytes(stream.read(width),'little');assert length<65536 # Bound untrusted header allocation.
    header=ast.literal_eval(stream.read(length).decode('utf-8' if major==3 else 'latin1'));assert set(header)=={'descr','fortran_order','shape'} # Read only literal array metadata with no executable interpretation.
    return header # Full tensor interpretation belongs to the later complete selected-reference audit.
def audit(): # Audit eight already closed friction slots without consulting the mutable aggregate index.
    proof=read(OUT/'v2_test_release_verification.json');assert proof['status']=='PASS_BEFORE_FIRST_NEW_TEST_REFERENCE';checked(proof['release']) # Native inspection is allowed only after the actual training and selection release.
    envelope_path=OUT/'v2_released_evaluation_descriptors.json';envelope=read(envelope_path);checked(envelope['release']);descriptors=envelope['families']['friction'];assert len(descriptors)==8 # Preserve the registered four test plus four OOD denominator.
    assert sorted(d['split'] for d in descriptors)==['ood']*4+['test']*4;assert len({d['id'] for d in descriptors})==8 and len({d['group_id'] for d in descriptors})==8 # No duplicated physical history or renamed replacement is admitted.
    observed={};records=[] # Save immutable source observations and per-slot independent checks.
    def observe(path,expected=None): # Remember every read source so its final SHA and stat can be compared.
        path=Path(path);before=signature(path);ref=reference(path);assert before==signature(path) # Reject a file changing during its read.
        if expected is not None: assert ref['sha256']==expected,str(path) # Original producer expectations remain authoritative.
        if str(path) in observed: assert observed[str(path)]=={'ref':ref,'stat':before},str(path) # A repeated reference must retain identical bytes.
        observed[str(path)]={'ref':ref,'stat':before};return ref # Do not modify or relabel the original source.
    for desc in descriptors: # Only paths explicitly enumerated by the released inputs are inspected.
        folder=ROOT/'operator/evaluation_native/attempts'/desc['id'];completion_path=folder/'completion.json';completion=read(completion_path);observe(completion_path) # A slot must have a closed completion, not a merely started process.
        assert completion['status']=='CLOSED_NATIVE_SLOT' and completion['descriptor']==desc;intent_ref=completion['intent'];result_ref=completion['callback_result'];observe(intent_ref['path'],intent_ref['sha256']);observe(result_ref['path'],result_ref['sha256']) # Bind exact original intent and callback result.
        intent=read(intent_ref['path']);result=read(result_ref['path']);row=completion['row'];assert intent['descriptor']==desc and result['descriptor']==desc and row['descriptor']==desc # Loaded physical inputs must match the pre-registered released descriptor exactly.
        assert row['id']==desc['id'] and row['group_id']==desc['group_id'] and row['quality']=='VALID_CONVERGED' and row['native_execution_state']=='CLOSED' # Numerical qualification is not a claim about neural prediction quality.
        for ref in completion['evidence']: observe(ref['path'],ref['sha256']) # Check each original completion link, including derived arrays and callback timing.
        native=Path(row['npz']).parent;receipt_path=native/'receipt.json';receipt=read(receipt_path);observe(receipt_path) # Use the original native receipt rather than any mutable campaign summary.
        assert receipt['returncode']==0 and receipt['job_finished'] and not receipt['error_marker'];observe(receipt['solver'],receipt['solver_wrapper_sha256']) # Actual native normal exit and solver identity remain required.
        native_checks=[] # Record every original input and output SHA independently.
        for name,expected in receipt['native_files'].items(): native_checks.append({'name':name,**observe(native/name,expected)}) # Current raw native files must match the producer's unchanged original expectations.
        archive_path=native/'native_snapshot.zip';archive_ref=observe(archive_path);archive_members=[] # The immediate native archive provides an independent complete-byte snapshot.
        with zipfile.ZipFile(archive_path) as archive: # Consume all native members, including the receipt itself.
            assert len(archive.namelist())==len(set(archive.namelist())) and set(archive.namelist())==set(receipt['native_files'])|{'receipt.json'} # Reject missing, duplicate or extra unaccounted snapshot members.
            for member in archive.infolist(): # Full decompression verifies CRC in addition to each cryptographic hash.
                with archive.open(member) as stream: digest,size=stream_digest(stream) # No large archive member is buffered in memory.
                expected=reference(receipt_path)['sha256'] if member.filename=='receipt.json' else receipt['native_files'][member.filename];assert digest==expected and size==member.file_size # Every member must reproduce exactly the original source identity.
                archive_members.append({'name':member.filename,'sha256':digest,'bytes':size}) # Preserve actual independently read member identities.
        for name,expected in result['export_sha256'].items(): observe(native/name,expected) # All derived field and metadata hashes are bound to the closed callback result.
        metadata=read(row['metadata']);qualification=read(native/'audit.json');assert metadata['descriptor']==desc and metadata['entity_count']==697 and metadata['physical_node_count']==153 and metadata['volume_IP_count']==544 and len(metadata['fields'])==15 # Retain all original node and eight-point element entities.
        assert qualification['quality']=='VALID_CONVERGED' and qualification['checks'] and all(qualification['checks'].values()) and len(qualification['records'])==32 # Verify the original reference qualification report is complete for all solved observation frames.
        containers=[] # Stream every member of both native tables and full-field containers.
        for name in ['fields.npz','native_tables.npz']: # These immutable original exports are inspected without performing neural inference.
            members=[];headers={} # Store only compact array headers and member hashes.
            with zipfile.ZipFile(native/name) as archive: # ZIP member reads validate the complete encoded field data.
                assert len(archive.namelist())==len(set(archive.namelist())) # Duplicate array keys could conceal a changed reference.
                for member in archive.infolist(): # All arrays, not merely the primary state tensor, receive complete CRC and SHA reads.
                    with archive.open(member) as stream: digest,size=stream_digest(stream) # Preserve low memory use while checking all compressed bytes.
                    assert size==member.file_size;members.append({'name':member.filename,'sha256':digest,'bytes':size}) # Record complete payload size and hash.
                    if member.filename.endswith('.npy'): # Array metadata is read in a separate bounded pass.
                        with archive.open(member) as stream: headers[member.filename]=npy_header(stream) # The state values themselves are not loaded into an array library.
            if name=='fields.npz': assert tuple(headers['states.npy']['shape'])==(33,697,15) and tuple(headers['state_mask.npy']['shape'])==(697,15) and tuple(headers['native_node_ids.npy']['shape'])==(153,) # Exact header coverage must match the native graph and complete history.
            containers.append({'file':observe(native/name),'members':members,'headers':headers}) # Full numerical finite-value and exact native-ID checks follow in the final selected-reference audit.
        chain=row['cost_evidence']['actual_fresh_native_receipts'];seconds=0.0 # Account only documented actual original invocation timing.
        for item in chain: # Preserve complete replay chains if a valid same-input native replay was necessary.
            observe(item['receipt'],item['receipt_sha256']);observe(item['input_deck'],item['input_deck_sha256']);native_receipt=read(item['receipt']);assert native_receipt['seconds']==item['measured_seconds'];seconds+=native_receipt['seconds'] # Timing comes from original native receipts, never a guessed fallback.
        assert seconds==row['fresh_native_seconds_total'] and len(chain)==row['fresh_native_execution_count'] # Separate actual native execution count from registered physical history count.
        records.append({'id':desc['id'],'split':desc['split'],'group_id':desc['group_id'],'completion':observe(completion_path),'native_receipt':observe(receipt_path),'native_files':native_checks,'native_archive':archive_ref,'native_archive_members':archive_members,'field_containers':containers,'actual_fresh_native_seconds':seconds,'actual_fresh_native_executions':len(chain),'status':'PASS_CLOSED_SLOT_NATIVE_BYTES_ALL_CONTAINER_MEMBERS_AND_DECLARED_COVERAGE'}) # This partial receipt does not report neural error or a completed sixteen-slot campaign.
    for value in observed.values(): assert reference(value['ref']['path'])==value['ref'] and signature(value['ref']['path'])==value['stat'],value['ref']['path'] # Recheck every original source after the entire inspection.
    result={'schema':'bridge.v2.friction.closed.evaluation.native.audit.v1','status':'PASS_EIGHT_CLOSED_FRICTION_NATIVE_SLOTS_BYTE_IDENTITY_AND_CONTAINER_CRC','source':reference(__file__),'release_verification':reference(OUT/'v2_test_release_verification.json'),'released_descriptors':reference(envelope_path),'registered_histories':8,'registered_test_histories':4,'registered_ood_histories':4,'native_reference_qualified_histories':8,'records':records,'all_observed_sources_stable':True,'observed_source_count':len(observed),'actual_fresh_native_seconds':sum(x['actual_fresh_native_seconds'] for x in records),'native_solver_calls_by_auditor':0,'neural_calls_by_auditor':0,'numpy_or_torch_imported':False,'mutable_campaign_index_read':False,'full_campaign_complete_claimed':False,'scientific_accuracy_evaluated':False,'scope':'Partial native-byte and container-integrity audit only. Full numerical identity and model-error audits remain separate; rebar slots were not inspected.'} # Distinguish execution integrity from unresolved scientific prediction accuracy.
    target=OUT/'v2_friction_closed_evaluation_native_audit.json';assert not target.exists();target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(reference(target))) # Publish a new independent receipt without changing any producer artifact.
if __name__=='__main__': audit() # No training, finite-element solver, reference repair or test selection is exposed.
