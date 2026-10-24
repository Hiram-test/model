import argparse,hashlib,json,shutil # Restore verified closed development evidence without executing numerical software.
from pathlib import Path,PurePosixPath # Restrict materialization to the recorded nonformal development directories.
HERE=Path(__file__).resolve().parent;parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True);parser.add_argument('--external-root',action='append',default=[]);args=parser.parse_args() # External roots are already extracted old archives or the restored repository.
manifest=json.loads((HERE/'supplement_manifest.json').read_text());destination=Path(args.destination).resolve();roots=[Path(p).resolve() for p in args.external_root];prepared=[];missing=[] # Complete all source checks before creating destination files.
def sha(path): # Stream complete artifact bytes without parsing checkpoints or arrays.
    h=hashlib.sha256() # Keep storage identity separate from scientific verification.
    with Path(path).open('rb') as stream: # Bound the copy preparation memory footprint.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Read complete files in one-MiB buffers.
    return h.hexdigest() # Return the recorded SHA256 identifier.
for item in manifest['logical_files']: # Resolve both payload aliases and previously persisted external references.
    relative=PurePosixPath(item['relative_path']);assert not relative.is_absolute() and '..' not in relative.parts and '/'.join(relative.parts[:2]) in manifest['whitelist_directories'] # Reject path traversal and all formal/live destinations.
    target=destination/relative;assert target.resolve().is_relative_to(destination);assert not target.exists() or target.is_file() and sha(target)==item['sha256'] # Refuse conflicting existing artifacts instead of overwriting them.
    if item['bytes']==0: source=None # Reconstruct the explicitly hashed zero-length file exactly.
    elif item.get('archive_member'): source=HERE/item['archive_member'] # Internal aliases point to the same packaged immutable bytes.
    else: source=next((root/item['external_reference']['member'] for root in roots if (root/item['external_reference']['member']).is_file() and sha(root/item['external_reference']['member'])==item['sha256']),None) # Search only explicit known member paths in supplied source roots.
    if item['bytes'] and (source is None or not source.is_file() or sha(source)!=item['sha256']): missing.append({'relative_path':item['relative_path'],'external_reference':item.get('external_reference')}) # Report missing prerequisites before any write.
    prepared.append((item,target,source)) # Preserve the verified source-to-destination mapping.
assert not missing,json.dumps({'missing_dependencies':missing},indent=2) # Never manufacture missing scientific evidence.
for item,target,source in prepared: # Materialize the closed evidence only after all required bytes are available.
    if not target.exists(): # Keep matching existing files verbatim.
        target.parent.mkdir(parents=True,exist_ok=True) # Create only the recorded safe parent directories.
        if source is None: target.write_bytes(b'') # Exact empty-file restoration is fully determined by the manifest.
        else: shutil.copyfile(source,target) # Copy opaque bytes without deserialization or numerical work.
    assert sha(target)==item['sha256'] # Recheck every logical file after restoration.
print(json.dumps({'status':'CLOSED_DEVELOPMENT_BYTES_RESTORED','logical_files':len(prepared),'destination':str(destination),'solver_calls':0,'torch_imports':0,'formal_paths_written':False},indent=2)) # Byte restoration is not a new training or scientific PASS claim.
