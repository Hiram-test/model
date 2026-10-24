import argparse, hashlib, json, resource, zipfile, zlib # Restore original candidate-input bytes without importing numerical libraries or running producers.
from pathlib import Path, PurePosixPath # Treat original absolute identities separately from an isolated extraction destination.
BUFFER=1048576 # Bound every decompression/copy block at one MiB.
def require(condition,message): # Keep safety and identity checks active under ordinary and optimized Python alike.
    if not condition: raise RuntimeError(message) # Never silently replace an existing source or ignore corruption.
def consume(stream,target=None): # Verify exact byte content while optionally copying to a newly created destination.
    h=hashlib.sha256(); crc=0; count=0 # Accumulate independent byte identity without decoding arrays.
    while True: # Read complete members through EOF for the ZIP library CRC check too.
        block=stream.read(BUFFER) # Bound memory for scientific input containers.
        if not block: break # Accept only complete decompression.
        h.update(block); crc=zlib.crc32(block,crc); count+=len(block) # Hash the entire original byte stream.
        if target is not None: target.write(block) # Write only after preflight verified every source member.
    return {'sha256':h.hexdigest(),'crc32':f'{crc&0xffffffff:08x}','bytes':count} # Return exact reconstruction evidence.
def main(): # Default operation verifies a complete saved ZIP without writing anything.
    parser=argparse.ArgumentParser(); parser.add_argument('archive'); parser.add_argument('--restore-root'); args=parser.parse_args(); archive_path=Path(args.archive); output=Path(args.restore_root).absolute() if args.restore_root else None # A destination is an explicit opt-in to isolated byte restoration.
    if output is not None: # Never restore over this session's live runtime or any existing directory.
        require(not output.exists() and not output.is_symlink(),'Restore root must not exist; use a fresh isolated path'); require(all(not p.is_symlink() for p in output.parents),'Restore ancestor cannot be a symlink') # Avoid aliasing a protected or concurrent source tree.
    with zipfile.ZipFile(archive_path) as archive: # Inspect small package metadata before authorizing exact payload paths.
        require(archive.getinfo('snapshot_manifest.json').file_size<2*1024*1024,'Unexpected manifest size'); manifest=json.loads(archive.read('snapshot_manifest.json')); require(manifest['schema']=='bridge.v2.closed_acquisition_inputs.snapshot.v1' and manifest['classification']=='INPUT_ONLY_NOT_FEM_LABELS' and manifest['candidate_count']==32,'Wrong snapshot schema/scope'); rows=manifest['files'] # An intact archive is not a FEM label dataset.
        require(len(archive.namelist())==len(set(archive.namelist())),'Duplicate archive members'); expected={row['member'] for row in rows}|{'snapshot_manifest.json','package_acquisition_inputs.py','restore_acquisition_inputs.py','README.md'}; require(set(archive.namelist())==expected,'Unexpected package member') # Reject omitted or added payloads before writing.
        for row in rows: # Validate every member path and hash before creating even the destination root.
            rel=PurePosixPath(row['relative_path']); require(not rel.is_absolute() and '..' not in rel.parts and row['member']=='payload/'+str(rel),'Unsafe original relative path') # Keep extracted payloads inside the new isolated tree.
            with archive.open(row['member']) as stream: actual=consume(stream) # Verify original input bytes without loading any arrays.
            require(all(actual[k]==row[k] for k in ('sha256','crc32','bytes')),'Candidate source identity mismatch') # Original frozen SHA bindings remain authoritative.
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<30*1024*1024,'Preflight memory limit exceeded') # Enforce the same small-process recovery bound.
        if output is not None: # Copy the exact original bytes only after all source members passed verification.
            output.mkdir(parents=True,exist_ok=False) # Claim a new isolated root and refuse concurrent pre-existing targets.
            for row in rows: # Preserve every recorded relative path without rewriting embedded absolute references.
                target=output/row['relative_path']; target.parent.mkdir(parents=True,exist_ok=True); require(not target.exists() and not any(p.is_symlink() for p in target.parents),'Restore path conflict') # Never replace any existing source file.
                with archive.open(row['member']) as stream,target.open('xb') as destination: actual=consume(stream,destination) # Copy complete original bytes in bounded chunks.
                require(all(actual[k]==row[k] for k in ('sha256','crc32','bytes')),'Restored source identity mismatch') # Recheck after each actual write without numerical interpretation.
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024; require(peak<30*1024*1024,'Final memory limit exceeded'); print(json.dumps({'status':'RESTORED_EXACT_INPUT_BYTES' if output else 'VERIFIED_INPUT_BYTES_NO_WRITES','files':len(rows),'input_graphs':32,'restore_root':str(output) if output else None,'embedded_absolute_paths_unchanged':True,'new_run_release_or_freeze_issued':False,'peak_rss_bytes':peak,'buffer_bytes':BUFFER,'solver_calls':0,'torch_imports':0},indent=2)) # Relocation does not validate old path-bound execution locks or release tests.
if __name__=='__main__': main() # Importing this helper never restores files or invokes computation.
