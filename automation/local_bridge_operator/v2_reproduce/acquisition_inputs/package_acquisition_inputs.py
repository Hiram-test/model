import ast, hashlib, io, json, os, resource, shutil, stat, sys, time, tokenize, zipfile, zlib # Audit and preserve only closed candidate inputs with bounded standard-library I/O.
from pathlib import Path # Never import numerical libraries, controller modules or native adapters.
ROOT=Path('/dev/shm/bridge_complex_v2_20261025'); HERE=Path(__file__).resolve().parent; BUFFER=1048576; LIMIT=30*1024*1024 # Keep each I/O block at one MiB and peak RSS below thirty MiB.
def require(condition,message): # Fail closed without relying on removable Python assertions.
    if not condition: raise RuntimeError(message) # Preserve partial artifacts for diagnosis instead of overwriting them.
def read(path): # Read only explicit small metadata and archive member inventories.
    require(Path(path).stat().st_size<8*1024*1024,'Unexpected large JSON metadata'); return json.loads(Path(path).read_text()) # Exclude array and model parsing.
def digest_stream(stream): # Calculate independent SHA256, CRC32 and byte length in a single bounded pass.
    h=hashlib.sha256(); crc=0; size=0 # Reset exact content accumulators.
    while True: # Consume every source byte without numerical interpretation.
        block=stream.read(BUFFER) # Bound temporary memory even for input NPZ containers.
        if not block: break # Require EOF before accepting identity.
        h.update(block); crc=zlib.crc32(block,crc); size+=len(block) # Bind SHA, CRC and full length.
    return {'sha256':h.hexdigest(),'crc32':f'{crc&0xffffffff:08x}','bytes':size} # Return raw-byte identity only.
def identity(path): # Detect source changes while computing complete opaque-byte identities.
    path=Path(path); require(path.is_file() and not path.is_symlink(),'Expected a regular original file'); before=path.stat() # Refuse path aliases and missing files.
    with path.open('rb') as stream: value=digest_stream(stream) # Never decode NPZ arrays.
    after=path.stat(); keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'); require(all(getattr(before,k)==getattr(after,k) for k in keys),'Source changed during hashing') # Bind stable original filesystem metadata.
    return {'path':str(path),**value,'stat':{k:getattr(after,k) for k in keys}} # Preserve original absolute paths and exact stat evidence.
def objects(value): # Traverse manifest metadata without opening any listed scientific payload.
    if isinstance(value,dict): # Yield dictionary records before their children.
        yield value # Permit heterogeneous earlier manifest formats.
        for child in value.values(): yield from objects(child) # Recursively inspect metadata only.
    elif isinstance(value,list): # Lists contain previous archive member inventories.
        for child in value: yield from objects(child) # Avoid retaining a second copy of the manifest.
def inventory(): # Limit source discovery to thirty-two candidate IDs and eight completed acquisition markers.
    files={}; candidates=[]; closures=[]; missing_decks=[] # Store small provenance records only.
    def add(path,role,expected=None): # Collect explicit paths rather than walking any live formal or native response tree.
        path=Path(path); rel=str(path.relative_to(ROOT)); require(not any(x in rel for x in ('sealed','newtest','heldout')),'Forbidden source scope'); item=identity(path) # Hash only authorized original input bytes.
        if expected is not None: require(item['sha256']==expected,'Original input SHA binding mismatch: '+rel) # Keep frozen receipt identities authoritative.
        if rel in files: require(files[rel]['sha256']==item['sha256'],'Repeated path identity changed'); return files[rel] # Reuse identical logical files.
        item.update({'relative_path':rel,'member':'payload/'+rel,'role':role}); files[rel]=item; return item # Preserve original paths for isolated restoration.
    for family in ('friction','rebar'): # Each family has precisely sixteen pre-generated acquisition candidates.
        for arm in ('active','random'): # Require both completed acquisition strategies.
            for number in (1,2): # Read no training stage or worker data.
                path=ROOT/f'operator/formal/{family}/{arm}/round_{number}/acquisition_complete.json'; data=read(path); require(data['status']=='COMPLETE_FINITE_ROUND' and data['family']==family and data['strategy']==arm and data['round']==number,'Acquisition not closed'); closures.append(identity(path)) # Record closure identity without copying label references or response payloads.
        paths=sorted((ROOT/f'operator/formal/{family}/prepared_inputs').glob('*.json')); require([p.stem for p in paths]==[f'v2_{family}_candidate_{i:02d}' for i in range(16)],'Unexpected prepared input IDs') # Reject test/OOD additions even if names share a directory.
        for path in paths: # Bind each preserved preparation record to the exact original input container.
            record=read(path); desc=record['descriptor']; row=record['row']; cid=path.stem; require(desc['id']==cid and desc['family']==family and desc['split']=='candidate' and desc['future_native_fields_present'] is False and row['split']=='candidate','Not an input-only candidate'); add(path,'ORIGINAL_PREPARED_RECORD') # Never reserialize the frozen source record.
            require(row['npz']==record['npz']['path'] and row['metadata']==record['metadata']['path'],'Prepared path mismatch'); folder=ROOT/(f'friction/prepared/{cid}' if family=='friction' else f'rebar/native/candidates/{cid}'); names={'descriptor.json','input_identity.json','metadata.json','fields.npz'} if family=='friction' else {'inputs.npz','metadata.json','model.inp','prepared_row.json','prepared_receipt.json'} # Declare the exact authorized per-case directory whitelist.
            require({p.name for p in folder.iterdir()}==names,'Unexpected candidate directory contents'); require(Path(row['npz']).parent==folder and Path(row['metadata']).parent==folder,'Input path escaped candidate directory') # Refuse native/cases response exports and hidden added files.
            for key in ('npz','metadata'): add(record[key]['path'],'INPUT_ONLY_GRAPH' if key=='npz' else 'INPUT_METADATA',record[key]['sha256']) # Match all sixty-four direct frozen SHA bindings.
            if family=='rebar': # Rebar retains an immutable source receipt and all original native decks.
                card=read(folder/'prepared_receipt.json'); saved_row=read(folder/'prepared_row.json'); require(card['status']=='COMMITTED_INPUT_ONLY' and card['input_identity']==row['input_identity'] and saved_row==row and row['quality']=='UNSOLVED_CANDIDATE','Rebar original receipt mismatch') # Preserve the historical v3 candidate-zero receipt without rewriting it to v4.
                for name,sha in card['files'].items(): require(name in names,'Unexpected receipt member'); add(folder/name,'INPUT_DECK' if name=='model.inp' else 'INPUT_DIRECTORY_EVIDENCE',sha) # Include complete original candidate-directory evidence.
                add(folder/'prepared_receipt.json','ORIGINAL_INPUT_COMMIT'); require(files[str((folder/'model.inp').relative_to(ROOT))]['sha256']==row['input_deck_sha256']==row['input_identity']['native_input_sha256'],'Rebar original deck identity mismatch') # Bind actual deck bytes to both original identities.
                source=ROOT/('rebar/v2_native_rebar_v3.py' if cid.endswith('_00') else 'rebar/v2_native_rebar_v4.py'); add(source,'ORIGINAL_PREPARATION_SOURCE',card['adapter_source_sha256']) # Retain the exact two historical adapter versions used by committed inputs.
            else: # Friction intentionally uses a fields.npz filename for zero-future input placeholders.
                require(row['quality']=='INPUT_ONLY_UNSOLVED' and read(folder/'descriptor.json')==desc and read(folder/'input_identity.json')==row['input_identity'],'Friction input-only identity mismatch') # The filename must never be treated as a qualified FEM label.
                for name in ('descriptor.json','input_identity.json'): add(folder/name,'INPUT_DIRECTORY_EVIDENCE') # Preserve controls and immutable identity without regeneration.
                deck=ROOT/f'friction/native/cases/{cid}/contact.inp' # Only the actual native input deck is eligible from a solved-case directory.
                if deck.exists(): add(deck,'EXISTING_INPUT_DECK_ONLY',row['input_identity']['native_input_sha256']) # Do not open adjacent native outputs or exported responses.
                else: missing_decks.append({'id':cid,'native_input_sha256':row['input_identity']['native_input_sha256'],'reason':'Original prepare_candidate never persisted a deck; candidate has no canonical solved deck. No deck regeneration performed.'}) # Report unavailable historical bytes honestly.
            add(record['adapter']['path'],'FROZEN_PREPARED_ADAPTER_SOURCE',record['adapter']['sha256']); candidates.append({'id':cid,'family':family,'prepared_record':str(path.relative_to(ROOT)),'input_graph':str(Path(row['npz']).relative_to(ROOT)),'metadata':str(Path(row['metadata']).relative_to(ROOT)),'quality':row['quality'],'input_only':True}) # Preserve current adapter reference separately from the historical generation receipt.
    require(len(candidates)==32 and len(closures)==8 and len(missing_decks)==9,'Unexpected original candidate scope'); records=list(files.values()); targets={row['sha256'] for row in records}; hits={sha:[] for sha in targets} # Compare byte coverage without holding all previous archive records.
    prior=read(ROOT/'reproduce/closed_development_inventory_review.json')['external_comparison_manifests']; manifest_paths={x['manifest_path'] for x in prior} # Reuse independently reviewed V1/V2 archive inventory paths.
    for reference in prior: require(identity(reference['manifest_path'])['sha256']==reference['manifest_sha256'],'Previously audited archive/source manifest changed') # Bind previously persisted coverage claims to their earlier independently reviewed metadata bytes.
    manifest_paths.update(str(p) for p in (ROOT/'checkpoints').glob('*.receipt.json')); manifest_paths.update(str(p) for p in (ROOT/'checkpoints').glob('*/checkpoint_receipt.json')); manifest_paths.update(str(p) for p in (ROOT/'checkpoints').glob('*checkpoint_manifest.json')) # Include subsequently saved closed stage/native checkpoints without inspecting any training tree.
    manifest_paths.update(str(ROOT/p) for p in ('reproduce/closed_development_supplement/supplement_manifest.json','reproduce/native_runtime/runtime_manifest.json')) # Cover the two already saved reproduction supplements.
    checked=[] # Record exact compared metadata identities.
    for name in sorted(manifest_paths): # Parse one bounded earlier manifest at a time.
        p=Path(name); data=read(p); matched=0; total=0 # Do not open listed payloads, including any archived response fields.
        for obj in objects(data): # Compare raw member SHA values against authorized candidate sources only.
            member=obj.get('member') or obj.get('archive_member') or obj.get('relative_path') or obj.get('repo_path'); sha=obj.get('sha256') # Accommodate multiple existing archive schemas.
            if not isinstance(member,str) or not isinstance(sha,str): continue # Ignore non-member narrative and receipt objects.
            total+=1 # Count inspected original metadata records.
            if sha in targets: hits[sha].append({'manifest_path':str(p),'member':member}); matched+=1 # Store only actual candidate byte matches.
        checked.append({'path':str(p),'sha256':identity(p)['sha256'],'member_records':total,'matching_records':matched}); del data # Release every earlier manifest before opening the next one.
    for row in records: # Distinguish original pathname recovery from equal bytes found at another source path.
        row['prior_content_matches']=hits[row['sha256']]; row['prior_exact_path_matches']=[hit for hit in row['prior_content_matches'] if hit['member'].removeprefix('payload/')==row['relative_path']] # A solved-case metadata duplicate alone does not reconstruct an omitted candidates path.
    return {'schema':'bridge.v2.closed_acquisition_inputs.snapshot.v1','classification':'INPUT_ONLY_NOT_FEM_LABELS','candidate_count':32,'closed_acquisition_rounds':closures,'candidates':candidates,'files':records,'prior_manifest_comparison':checked,'missing_original_friction_decks':missing_decks,'original_files':len(records),'original_bytes':sum(x['bytes'] for x in records),'input_graphs_without_prior_content_coverage':[x['relative_path'] for x in records if x['role']=='INPUT_ONLY_GRAPH' and not x['prior_content_matches']],'original_paths_without_prior_exact_coverage':[x['relative_path'] for x in records if not x['prior_exact_path_matches']],'scope':'All 32 original prepared records and input-directory bytes, existing input decks only, three exact adapter source versions. No FEM labels, live training artifacts, test/OOD/sealed data, new solves or regenerated inputs.','buffer_bytes':BUFFER,'numerical_array_deserialization':False,'torch_imports':0,'solver_calls':0} # Preserve explicit restoration limitations rather than overstating completeness.
def main(): # Separate read-only inventory from one-shot immutable package creation.
    require(len(sys.argv)==2 and sys.argv[1] in ('inventory','package'),'Use inventory or package'); started=time.monotonic(); value=inventory(); manifest=HERE/'snapshot_manifest.json' # Revalidate current original byte bindings on every explicit run.
    if sys.argv[1]=='inventory': # Freeze a reviewable inventory without compressing payloads.
        require(not manifest.exists(),'Inventory already exists'); manifest.write_text(json.dumps(value,indent=2)+'\n'); print(json.dumps({'manifest':str(manifest),'files':value['original_files'],'bytes':value['original_bytes'],'graphs_missing':len(value['input_graphs_without_prior_content_coverage']),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})); return # Leave source contents unchanged.
    require(read(manifest)==value,'Source scope or identity changed after inventory'); archive_path=HERE.parent/'closed_acquisition_inputs_snapshot.zip'; require(not archive_path.exists(),'Existing ZIP immutable') # Reject unreviewed changes and accidental package replacement.
    metadata=[(manifest,'snapshot_manifest.json'),(Path(__file__),'package_acquisition_inputs.py'),(HERE/'restore_acquisition_inputs.py','restore_acquisition_inputs.py'),(HERE/'README.md','README.md')]; expected={row['member']:row for row in value['files']} # Include recovery instructions and exact source used for packaging.
    for path,name in metadata: expected[name]=identity(path) # Bind generated documentation and helper bytes.
    for path in (Path(__file__),HERE/'restore_acquisition_inputs.py'): # Apply the requested actual-comment rule to all newly authored Python.
        source=path.read_text(); ast.parse(source); comments={t.start[0] for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type==tokenize.COMMENT}; require(all(i in comments for i,line in enumerate(source.splitlines(),1) if line.strip()),'Missing Python COMMENT token') # String literals containing a hash are not sufficient.
    with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive: # Use bounded streaming and deterministic metadata for a compact independent input snapshot.
        for name,row in expected.items(): # Copy each original byte stream exactly once per logical path.
            info=zipfile.ZipInfo(name,date_time=(2000,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(stat.S_IFREG|0o644)<<16 # Store neutral regular-file permissions for isolated evidence restoration.
            with Path(row['path']).open('rb') as source,archive.open(info,'w') as target: shutil.copyfileobj(source,target,length=BUFFER) # Never load whole NPZ files into memory.
    verified=[] # Retain compact full-member verification evidence.
    with zipfile.ZipFile(archive_path) as archive: # Independently decompress the completed archive, enforcing its own CRC checks as well.
        require(len(archive.infolist())==len(expected) and set(archive.namelist())==set(expected),'Unexpected archive members') # Disallow duplicate or omitted members.
        for name,row in expected.items(): # Recompute actual SHA, CRC and length from every decompressed member.
            with archive.open(name) as stream: observed=digest_stream(stream) # Read through EOF in one-MiB chunks.
            require(all(observed[k]==row[k] for k in ('sha256','crc32','bytes')) and archive.getinfo(name).CRC==int(observed['crc32'],16),'Member CRC/SHA/length mismatch'); verified.append({'member':name,**observed}) # Reject any silent compression or transport corruption.
    for row in value['files']+value['closed_acquisition_rounds']: require(identity(row['path'])=={k:row[k] for k in ('path','sha256','crc32','bytes','stat')},'Original source changed during packaging') # Confirm complete pre/post hashes and filesystem stability without touching training files.
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024; require(peak<LIMIT,'Memory ceiling exceeded'); receipt={'status':'PASS_CLOSED_INPUT_ONLY_SNAPSHOT_FULL_CRC_SHA_AND_STABLE_SOURCES','archive':identity(archive_path),'manifest':identity(manifest),'source_files':value['original_files'],'source_bytes':value['original_bytes'],'prepared_records':32,'input_only_graphs':32,'closed_acquisition_rounds':8,'rebar_original_decks':16,'existing_friction_original_decks':7,'friction_decks_never_persisted':9,'verified_members':verified,'source_bytes_and_stats_unchanged':True,'buffer_bytes':BUFFER,'peak_rss_bytes':peak,'elapsed_seconds':time.monotonic()-started,'torch_imports':0,'solver_calls':0,'FEM_label_payloads':0,'live_training_files_opened':0,'sealed_or_newtest_files_opened':0}; output=HERE/'snapshot_receipt.json'; require(not output.exists(),'Receipt already exists'); output.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps({k:v for k,v in receipt.items() if k!='verified_members'},indent=2)) # Report actual package facts, never new scientific performance.
if __name__=='__main__': main() # Explicit CLI only; importing this source does not run an audit or package job.
