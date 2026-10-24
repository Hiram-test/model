import hashlib,json,os,shutil,time,zipfile # Recover packaging only; never launch or modify any scientific calculation.
from pathlib import Path # Preserve explicit absolute source and output boundaries.
BASE=Path('/workspace/scratch/500ec816102b');REPO=BASE/'model-repo';SOURCE=REPO/'build/complex-nonlinear-20261024';OLD=BASE/'deliverables';RECEIPTS=OLD/'complex_upload_receipts';DEST=Path('/dev/shm/bridge_complex_delivery') # Separate recovery outputs from every original producer pathname.
DEST.mkdir(exist_ok=False);PREFIX_COUNT=10;PARTIAL=OLD/'bridge_complex_fullfield_11.zip';ORIGINAL_GLOBAL=OLD/'bridge_complex_fullfield_archives.json' # Exclusively create the recovery directory and refuse an unsafe restart over previously written evidence.
def digest(path): # Compute complete identities without loading large files into memory.
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest() # Include every byte in the identity.
def snapshot(path): # Watch the original interrupted output for any continuing producer activity.
    stat=path.stat();return [stat.st_size,stat.st_mtime_ns,digest(path)] # Record both metadata and full content for the original incomplete object.
def write_json(path,value): # Publish small recovery records atomically in the independent filesystem.
    temporary=path.with_suffix(path.suffix+'.tmp') # Keep incomplete metadata out of stable receipt names.
    with temporary.open('w') as stream: json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno()) # Durably finish the exact JSON bytes before renaming.
    temporary.replace(path) # Publish the completed record in one operation.
def available_memory(): # Honor the actual process memory budget as well as the separate temporary-filesystem capacity.
    maximum=int(Path('/sys/fs/cgroup/memory.max').read_text());current=int(Path('/sys/fs/cgroup/memory.current').read_text());return maximum-current # Use the observed finite container budget without assuming host-wide free memory is available.
original_partial=snapshot(PARTIAL);assert not ORIGINAL_GLOBAL.exists();publication=json.loads((SOURCE/'github_publication.json').read_text());assert publication['verified'] # Bind recovery to the original immutable scientific source commit.
def guard(): # Refuse overlapping output if the original producer starts changing evidence again.
    stat=PARTIAL.stat();assert [stat.st_size,stat.st_mtime_ns]==original_partial[:2] and not ORIGINAL_GLOBAL.exists(),'Original producer evidence changed during independent recovery' # Stop rather than choose between concurrent outputs silently.
    assert not PARTIAL.with_suffix('.sealed.json').exists() and not any(int(path.name.split('_')[-1].split('.')[0])>11 for path in OLD.glob('bridge_complex_fullfield_[0-9][0-9]*') if path.suffix in {'.zip','.json'}),'Later original producer evidence appeared during recovery' # Watch successor parts and seals even if the incomplete pathname itself did not change.
selection=json.loads((SOURCE/'archive_selection.json').read_text());exclusions={REPO/item['path']:item for item in selection['excluded_original_paths']};files=[] # Reconstruct the original explicit byte-based selection without rewriting its evidence receipt.
for path in sorted(SOURCE.rglob('*')): # Keep the original deterministic order and every otherwise unclassified artifact.
    if not path.is_file() or '__pycache__' in path.parts or path.name in {'ccx_2.21.pdf','ccx_2.21.txt'}: continue # Apply the original documented cache and copyright exclusions only.
    item=exclusions.get(path) # A pathname alone never proves duplicate identity.
    if item and path.stat().st_size==item['bytes'] and digest(path)==item['sha256']: continue # Omit exactly the previously reviewed unchanged duplicate bytes.
    files.append(path) # Retain every unique or changed item.
parts=[];prefix=[] # Recover complete declared member lists from the independently saved original ZIPs.
for number in range(1,PREFIX_COUNT+1): # Require a contiguous sealed prefix without missing part numbers.
    name=f'bridge_complex_fullfield_{number:02d}';sealed=json.loads((OLD/(name+'.sealed.json')).read_text());manifest=json.loads((RECEIPTS/'member_manifests'/(name+'.json')).read_text()) # Load exact original producer and archived metadata independently.
    assert sealed['crc_and_every_member_sha256_verified'] and sealed['source_code']==publication and manifest['source_code']==publication and len(manifest['members'])==sealed['part']['members'] # Keep byte identities and scientific source binding unchanged.
    parts.append(sealed['part']);prefix.extend(manifest['members']) # Preserve original SHA and size rather than recompressing completed pieces.
assert len(prefix)<=len(files) and [item['path'] for item in prefix]==[str(path.relative_to(REPO)) for path in files[:len(prefix)]] # Require an exact ordered prefix, not approximate filename matching.
records=[] # Anchor the entire recovered scientific selection before writing another archive.
for index,path in enumerate(files): # Bind both completed members and every remaining source object.
    guard();stat=path.stat();item={'path':str(path.relative_to(REPO)),'bytes':stat.st_size,'sha256':digest(path),'mtime_ns':stat.st_mtime_ns};records.append(item) # Retain the current exact source identity and concurrent-change sentinel.
    if index<len(prefix): assert all(item[key]==prefix[index][key] for key in ['path','bytes','sha256']),f'Completed source identity changed: {path}' # Previously packaged evidence must still match the native source bytes.
assert snapshot(PARTIAL)==original_partial;partial_copy=DEST/'interrupted_original_part_11.zip';shutil.copyfile(PARTIAL,partial_copy);assert digest(partial_copy)==original_partial[2] # Preserve the complete observed incomplete ZIP as failure evidence, without modifying its original.
plan={'schema':'bridge.complex.archive.recovery.v1','scientific_source':publication,'outer_exec_observation':{'session_id':67964,'reported_exit_code':120,'stdout_bytes':(OLD/'complex_archive_process.stdout.json').stat().st_size,'stderr_bytes':(OLD/'complex_archive_process.stderr.log').stat().st_size,'cause':'Unknown; outer execution result is separate from independently verified archive integrity.'},'interrupted_original':{'path':str(PARTIAL),'bytes':original_partial[0],'mtime_ns':original_partial[1],'sha256':original_partial[2]},'sealed_prefix_count':PREFIX_COUNT,'sealed_prefix_members':len(prefix),'complete_scientific_members':len(records),'complete_source_records':records,'packaging_only':True,'scientific_retraining_or_retesting':False,'recovery_script_sha256':digest(Path(__file__))} # Disclose observed transport/storage symptoms without inventing their cause.
write_json(DEST/'recovery_plan.json',plan);extra=[(partial_copy,'delivery_recovery/interrupted_original_part_11.zip'),(DEST/'recovery_plan.json','delivery_recovery/recovery_plan.json'),(Path(__file__),'delivery_recovery/bridge_complex_archive_recovery.py')] # Include the actual failed bytes, complete source map and executable recovery instructions.
pending=[(path,item['path']) for path,item in zip(files[len(prefix):],records[len(prefix):])]+extra;by_path={item['path']:item for item in records};archive=None;members=[];number=PREFIX_COUNT;all_new_members=[] # Resume exactly after the verified prefix and add clearly separated recovery evidence.
def close(): # Seal and independently inspect a newly completed ordinary ZIP.
    if archive is None: return # Skip the unopened initial state.
    guard() # Detect original producer activity at every sealing boundary as well as every member boundary.
    archive.writestr('evidence_manifests/'+output.stem+'.json',json.dumps({'schema':'bridge.complex.evidence.archive.v1','source_code':publication,'members':members,'recovery_plan_sha256':digest(DEST/'recovery_plan.json')},ensure_ascii=False,indent=2));archive.close() # Embed exact original-source identities and explicit recovery provenance.
    with zipfile.ZipFile(output) as verify: # Read the actual completed bytes before making a sealing claim.
        assert verify.testzip() is None # Reject any compression or stream corruption.
        for item in members: # Verify every stored scientific or recovery object independently of current filesystem contents.
            with verify.open(item['path']) as stream: assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256'] and verify.getinfo(item['path']).file_size==item['bytes'] # Require complete member identity and uncompressed length.
    part={'name':output.name,'local_path':str(output),'bytes':output.stat().st_size,'sha256':digest(output),'members':len(members)};parts.append(part);all_new_members.extend(members) # Retain exact sealed output identities for final total-coverage verification.
    guard() # Refuse a stable sealing receipt if original producer evidence changed during compression verification.
    write_json(output.with_suffix('.sealed.json'),{'source_code':publication,'part':part,'crc_and_every_member_sha256_verified':True,'recovery_plan_sha256':digest(DEST/'recovery_plan.json')});print(json.dumps({'sealed':part}),flush=True) # Let the uploader consume only an explicitly complete, verified object.
for path,relative in pending: # Write remaining sources only; completed prefix bytes remain untouched.
    guard() # Recheck the original producer sentinel before every member.
    if archive is None or archive.fp.tell()>280000000: # Keep ordinary archives within the established transfer target.
        close() # Finish verification of the previous part before allocating another.
        number+=1;output=DEST/f'bridge_complex_fullfield_{number:02d}.zip';archive=zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True);members=[] # Exclusively create every output and refuse collisions with any previously preserved evidence.
    while shutil.disk_usage(DEST).free<650000000 or available_memory()<max(400000000,min(path.stat().st_size,200000000)+300000000): guard();time.sleep(1) # Wait for verified uploads to release sealed predecessor bytes before consuming temporary memory; the empty successor remains an unsealed progress marker.
    before=path.stat();identity=digest(path);anchor=by_path.get(relative) # Bind the actual source bytes immediately before serialization.
    if anchor: assert (before.st_size,before.st_mtime_ns,identity)==(anchor['bytes'],anchor['mtime_ns'],anchor['sha256']) # Refuse a modified source rather than silently changing scientific results.
    archive.write(path,relative);after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);members.append({'path':relative,'bytes':before.st_size,'sha256':identity}) # Protect the entire write from concurrent changes.
close();guard();assert snapshot(PARTIAL)==original_partial # Require the original interrupted output to remain exactly unchanged throughout recovery.
combined=prefix+all_new_members;scientific=[item for item in combined if not item['path'].startswith('delivery_recovery/')];assert len({item['path'] for item in combined})==len(combined) # Prove no duplicate extraction paths across all final pieces.
assert [{key:item[key] for key in ['path','bytes','sha256']} for item in scientific]==[{key:item[key] for key in ['path','bytes','sha256']} for item in records] # Prove exact total source coverage and order, with no omitted or replaced member.
write_json(DEST/'bridge_complex_fullfield_archives.json',parts);write_json(DEST/'recovery_completion.json',{'status':'PASS_COMPLETE_ARCHIVE_COVERAGE','source_commit':publication['commit'],'parts':len(parts),'scientific_members':len(scientific),'recovery_members':len(extra),'sealed_prefix_unchanged':True,'original_partial_unchanged':True,'no_scientific_computation_repeated':True,'global_manifest_sha256':digest(DEST/'bridge_complex_fullfield_archives.json'),'plan_sha256':digest(DEST/'recovery_plan.json')});print(json.dumps({'completed':True,'parts':len(parts),'scientific_members':len(scientific)}),flush=True) # Separate successful evidence recovery from the earlier outer-session anomaly.
