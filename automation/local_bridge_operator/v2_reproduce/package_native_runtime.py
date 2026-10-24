import ast,hashlib,io,json,os,resource,shutil,stat,tarfile,tokenize,zipfile # Package the already observed runtime without loading Torch or invoking the solver.
from pathlib import Path # Preserve every original path and SHA while keeping the archive isolated.
HERE=Path(__file__).resolve().parent;OUT=HERE/'native_runtime';PREFIX=Path('/workspace/scratch/500ec816102b/solver-runtime') # The numerical sources and original runtime remain read-only.
def digest(path): # Hash original payloads with bounded temporary memory.
    h=hashlib.sha256() # Keep byte identity separate from runtime compatibility claims.
    with path.open('rb') as stream: # Stream even the larger binary and library payloads.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Avoid whole-archive memory allocation.
    return h.hexdigest() # Return the immutable content identifier.
plan=json.loads((OUT/'provenance_filelist.json').read_text());dependencies=json.loads((OUT/'ldd_paths.json').read_text());files=[];aliases=[];seen=set() # Use only the explicitly inspected dependency and provenance lists.
def add(path,archive_path,kind): # Record one exact regular payload and reject ambiguous archive names.
    path=Path(path);assert path.is_file() and archive_path not in seen;seen.add(archive_path);files.append({'source_path':str(path),'resolved_source_path':str(path.resolve()),'archive_path':archive_path,'kind':kind,'bytes':path.stat().st_size,'sha256':digest(path),'mode':stat.S_IMODE(path.stat().st_mode)}) # Bind each member to its actual source bytes and filesystem identity.
add(PREFIX/'ccx-precision-v2','runtime_prefix/ccx-precision-v2','unchanged_solver_wrapper');add(PREFIX/'root/usr/bin/ccx-precision-v2','runtime_prefix/root/usr/bin/ccx-precision-v2','unchanged_solver_binary') # Preserve the exact wrapper and formal v2 executable without patching either.
for dependency in dependencies: # Include the actual ldd startup closure, with system objects explicitly segregated.
    path=Path(dependency['path']);resolved=Path(dependency['resolved']);private=resolved.is_relative_to(PREFIX);archive_path=('runtime_prefix/'+str(resolved.relative_to(PREFIX))) if private else ('system_dependency_snapshots/'+str(resolved).lstrip('/')) # Never place host system objects in an automatically installable private prefix.
    add(resolved,archive_path,'private_runtime_dependency' if private else 'system_ABI_dependency_snapshot');dependency.update({'archive_path':archive_path,'sha256':digest(resolved),'private_prefix':private}) # Retain both the loader-visible name and canonical target path.
    if private and path.is_symlink(): aliases.append({'original_path':str(path),'relative_path':str(path.relative_to(PREFIX)),'link_target':os.readlink(path),'resolved_target':str(resolved),'target_sha256':digest(resolved)}) # Record rather than silently flatten original private-library aliases.
for entry in plan['files']: add(entry['path'],entry['archive_path'],entry['kind']) # Include inspected source provenance, original package and local license notices.
for path in sorted(OUT.iterdir()): # Add observation metadata and the constrained restore utility, not active result files.
    if path.is_file() and path.name not in ['runtime_manifest.json','runtime_bundle_receipt.json']: add(path,path.name,'bundle_metadata_or_restore_utility') # The archive is written outside this metadata directory.
add(Path(__file__),'package_native_runtime.py','packaging_source') # Preserve the exact standard-library packaging implementation.
assert sum(item['bytes'] for item in files)<200*1024**2 # Enforce the parent-authorized small evidence budget before compression.
assert digest(PREFIX/'ccx-precision-v2')=='a8a30eb4b03293a783bc27bd8d14d9a9f6fcbc9cc59bdb9574e0456f8cd6af60' # Reject an unobserved wrapper change.
assert digest(PREFIX/'root/usr/bin/ccx-precision-v2')=='bc6714fcb1cfc10827115c166f04c47b7f9ebda6521786c8a5d42c3f751a786d' # Reject an unobserved solver change.
for path in [Path(__file__),OUT/'restore_runtime_prefix.py']: # Apply the true-comment rule to newly authored Python sources.
    source=path.read_text();ast.parse(source);comments={token.start[0] for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type==tokenize.COMMENT};assert all(index in comments for index,line in enumerate(source.splitlines(),1) if line.strip()) # Verify actual COMMENT tokens rather than hashes inside string literals.
manifest={'schema':'bridge.v2.native_runtime.bundle.v1','scope':'Byte-preserved formal-v2 wrapper, binary and observed ldd startup dependency closure; source provenance and local notices; no solver execution.','original_runtime_prefix':str(PREFIX),'ldd_dependency_count':len(dependencies),'dependencies':dependencies,'private_prefix_symlinks':aliases,'files':files,'source_bytes':sum(item['bytes'] for item in files),'limitations':plan['limitations'],'system_dependency_policy':'Snapshots for isolated ABI inspection only; restore utility never writes /lib, /usr/lib or system loader paths.','python_environment_status':'Observed versions only; not a complete installable lock.','native_solver_calls':0,'torch_imports':0} # Keep provenance coverage and compatibility limitations explicit.
manifest_path=OUT/'runtime_manifest.json';assert not manifest_path.exists();manifest_path.write_text(json.dumps(manifest,indent=2)+'\n') # Freeze the member whitelist once, after all observations are closed.
archive_path=HERE/'bridge_v2_native_runtime.zip';assert not archive_path.exists() # Preserve every prior archive and avoid silent replacement.
with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive: # Stream a deterministic small runtime evidence archive.
    for item in files+[{'source_path':str(manifest_path),'archive_path':'runtime_manifest.json','mode':0o644}]: # Include the manifest itself without creating a circular self-hash.
        info=zipfile.ZipInfo(item['archive_path'],date_time=(2000,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|item['mode'])<<16 # Preserve executable permission bits with stable archive metadata.
        with Path(item['source_path']).open('rb') as source,archive.open(info,'w') as target: shutil.copyfileobj(source,target,length=1024*1024) # Limit archive-write buffers to one MiB per transfer.
with zipfile.ZipFile(archive_path) as archive: # Re-read every archived member and verify the actual packaged bytes.
    assert archive.testzip() is None and len(archive.namelist())==len(files)+1 # Require complete CRC verification and exact coverage.
    for item in files+[{'archive_path':'runtime_manifest.json','sha256':digest(manifest_path)}]: # Check full-stream SHA256 in addition to ZIP CRC.
        h=hashlib.sha256() # Reset the member checksum before each read.
        with archive.open(item['archive_path']) as source: # Decompress the member with bounded buffers.
            for block in iter(lambda:source.read(1024*1024),b''): h.update(block) # Visit all payload bytes, not only archive headers.
        assert h.hexdigest()==item['sha256'] # Reject any packaged payload mismatch.
assert all(digest(Path(item['source_path']))==item['sha256'] for item in files) # Confirm the original wrapper, binary, libraries and evidence were not changed during packaging.
peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;assert peak<200*1024**2 # Verify the actual packaging process respected the memory ceiling.
receipt={'schema':'bridge.v2.native_runtime.receipt.v1','status':'PASS_SOURCE_STABILITY_FULL_MEMBER_CRC_AND_SHA','archive_path':str(archive_path),'archive_bytes':archive_path.stat().st_size,'archive_sha256':digest(archive_path),'manifest_path':str(manifest_path),'manifest_sha256':digest(manifest_path),'member_count':len(files)+1,'source_bytes':manifest['source_bytes'],'peak_rss_bytes':peak,'ldd_dependency_count':len(dependencies),'native_solver_calls':0,'torch_imports':0,'system_libraries_modified':False,'limitations':plan['limitations']};(OUT/'runtime_bundle_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2)) # Deliver a transport receipt without making a numerical or licensing claim beyond recorded evidence.
