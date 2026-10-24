import argparse,hashlib,json,zipfile # Build independently verifiable result bundles without copying GitHub-backed source code.
from pathlib import Path # Preserve repository-relative evidence paths in every archive.
from fem import REPO,write_json # Reuse the declared repository root and exact JSON writer.
DEST=REPO.parent/'deliverables' # Place final downloadable result archives alongside the readable report.
GROUPS={'static':['coupling_completed','local-contact-20261024','residual-online-20261024','unified-topology-20261024'],'nonlinear':['local-nonlinear-20261024'],'dynamics':['local-dynamics-20261024','completion-audit-20261024']} # Keep independently completed physics streams in distinct bounded-size bundles.
def digest(path): # Hash exact archived file bytes with bounded memory.
    h=hashlib.sha256() # Create a fresh SHA-256 accumulator.
    with path.open('rb') as stream: # Read every evidence byte in stable order.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Include full input, output, weight and metadata content.
    return h.hexdigest() # Return an independently reproducible byte identity.
def pack(group): # Archive only final result directories and record all included native evidence.
    DEST.mkdir(exist_ok=True);files=sorted(p for folder in GROUPS[group] for p in (REPO/'build'/folder).rglob('*') if p.is_file() and '.rsync-tmp' not in p.parts and '__pycache__' not in p.parts);parts=[];index=0;archive=None;members=[] # Exclude synchronization scratch and Python caches without dropping historical numerical failures.
    def close(): # Seal and verify one complete archive before recording success.
        if archive is None: return # Ignore the pre-opening state.
        archive.writestr('archive_manifest.json',json.dumps({'schema':'bridge.completion.evidence.v1','group':group,'members':members,'source_code':'Hiram-test/model branch codex/local-bridge-operator-20261024; code is stored separately in GitHub'},indent=2));archive.close() # Embed original relative paths, file identities and source-code location.
        with zipfile.ZipFile(output) as verify: assert verify.testzip() is None # Check every compressed member's CRC before delivery.
        parts.append({'name':output.name,'local_path':str(output),'bytes':output.stat().st_size,'sha256':digest(output),'member_count':len(members)}) # Record a completed downloadable bundle with its own hash.
    for path in files: # Preserve the entire selected evidence set in deterministic path order.
        if archive is None or archive.fp.tell()>330000000: # Bound upload size while allowing only one final member beyond the soft threshold.
            close();index+=1;output=DEST/f'bridge_completion_{group}_{index:02d}.zip';archive=zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True);members=[] # Start a separately usable complete ZIP rather than a split binary stream.
        before=path.stat();identity=digest(path);relative=str(path.relative_to(REPO));archive.write(path,relative);after=path.stat();assert before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,f'Concurrent evidence mutation: {path}';members.append({'path':relative,'bytes':before.st_size,'sha256':identity}) # Reject any file changed while being packaged.
    close();write_json(DEST/f'bridge_completion_{group}_archives.json',parts);print(json.dumps(parts),flush=True) # Publish only fully written and CRC-verified bundles.
if __name__=='__main__': # Expose explicit per-stream packaging after each producer has finished.
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=GROUPS);args=parser.parse_args();pack(args.group) # Require a known evidence group and avoid uncontrolled directory collection.
