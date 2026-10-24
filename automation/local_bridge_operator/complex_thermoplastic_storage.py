import argparse,hashlib,json,os,zipfile # Preserve exact native evidence with verified lossless compression under the shared disk budget.
from pathlib import Path # Keep original native basenames and their immutable case directory.
def digest_stream(stream): # Hash native bytes incrementally without loading an entire large field file into memory.
    h=hashlib.sha256() # Preserve the same SHA256 identity already recorded in each native receipt.
    while True: # Read bounded chunks from either a native file or a lossless archive member.
        chunk=stream.read(1024*1024) # Bound extra memory independently of mesh size and field count.
        if not chunk: break # Stop only after the complete native byte stream is included.
        h.update(chunk) # Preserve every source byte, including native formatting and convergence diagnostics.
    return h.hexdigest() # Return a directly comparable immutable byte identity.
def archive_case(folder): # Losslessly package a completed case without deleting any unique native evidence.
    folder=Path(folder);assert (folder/'receipt.json').exists(),'Only completed immutable native cases may be compressed';target=folder/'native_outputs.zip';manifest=folder/'native_archive.json' # Never touch a running private workspace or incomplete result publication.
    if target.exists(): assert manifest.exists();return json.loads(manifest.read_text()) # Reuse an already verified immutable archive instead of recompressing or mutating it.
    files=sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in ['.inp','.dat','.frd','.sta','.cvg','.12d','.log'] and p.name.startswith(('heat.','mechanical.')));records=[];pending=folder/'native_outputs.zip.pending' # Keep all requested native inputs and outputs, including failed diagnostics.
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive: # Use a standard lossless container compatible with independent tools.
        for path in files: # Preserve exact original basenames and physical bytes.
            with path.open('rb') as stream: digest=digest_stream(stream) # Record each original file identity before archival.
            records.append({'name':path.name,'bytes':path.stat().st_size,'sha256':digest});archive.write(path,path.name) # Store the complete native file without reformatting a result or reducing a field.
    with zipfile.ZipFile(pending) as archive: # Independently verify every member before any raw duplicate can be removed.
        assert archive.testzip() is None,'Native archive CRC verification failed' # Verify every standard ZIP member checksum before checking the stronger original SHA256 identity.
        for row in records: # Check complete extracted bytes against original source identities.
            with archive.open(row['name']) as stream: assert digest_stream(stream)==row['sha256'],'Lossless native archive verification failed' # Fail closed while retaining every original on any mismatch.
    with pending.open('rb') as stream: os.fsync(stream.fileno());archive_sha=digest_stream(stream) # Flush the completed archive and record its own immutable identity.
    pending.replace(target);record={'status':'VERIFIED_LOSSLESS_NATIVE_ARCHIVE','archive':str(target),'archive_sha256':archive_sha,'original_bytes':sum(r['bytes'] for r in records),'archive_bytes':target.stat().st_size,'files':records,'semantics':'Every original native byte is preserved; original per-job receipt hashes still apply to extracted members. Full-field NPZ and all entity identities remain unchanged.'};temporary=manifest.with_suffix('.json.pending');temporary.write_text(json.dumps(record,indent=2)+'\n');temporary.replace(manifest) # Publish complete verified archive provenance before releasing duplicate disk space.
    for path in files: path.unlink() # Remove only byte-for-byte redundant raw copies after durable archive and manifest verification.
    return record # Return actual storage savings without altering any solver or learning outcome.
def read_text(path): # Read the exact native source bytes from either their raw file or verified lossless archive.
    path=Path(path) # Resolve archive membership from the unchanged native basename.
    try: return path.read_text(errors='replace') # Prefer a currently materialized original while tolerating concurrent verified archival publication.
    except FileNotFoundError: pass # The archive is published and verified before any raw duplicate is removed.
    with zipfile.ZipFile(path.parent/'native_outputs.zip') as archive: return archive.read(path.name).decode(errors='replace') # Restore exact original text without synthesizing or modifying any result.
def materialize(path): # Restore one exact native file for an external reader that requires a filesystem path.
    path=Path(path) # Keep the original native filename and relative case ownership.
    if path.exists(): return path # Avoid unnecessary extracted duplicates.
    manifest=json.loads((path.parent/'native_archive.json').read_text());row=next(r for r in manifest['files'] if r['name']==path.name);pending=path.with_suffix(path.suffix+'.pending') # Select the independently verified original member identity.
    with zipfile.ZipFile(path.parent/'native_outputs.zip') as archive,archive.open(path.name) as source,pending.open('wb') as target: # Stream a complete exact original back into a temporary file.
        while True: # Bound extra memory even for a large full-order native field file.
            chunk=source.read(1024*1024) # Use ordinary lossless streaming decompression.
            if not chunk: break # Stop at the exact original member boundary.
            target.write(chunk) # Preserve all bytes and native precision.
    with pending.open('rb') as stream: assert digest_stream(stream)==row['sha256'],'Materialized native hash mismatch' # Refuse any corrupted native restoration.
    pending.replace(path);return path # Make only a complete verified original visible to the external reader.
if __name__=='__main__': # Expose explicit lossless packaging and exact materialization actions.
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['archive','materialize']);parser.add_argument('path');args=parser.parse_args();print(json.dumps(archive_case(args.path),indent=2) if args.action=='archive' else str(materialize(args.path))) # Keep storage operations separate from numerical qualification and training.
