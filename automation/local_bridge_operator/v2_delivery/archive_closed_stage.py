from pathlib import Path # Preserve one genuinely closed training stage without including another live worker.
import argparse,hashlib,json,zipfile # Bind exact stage artifacts and verify every archived member.
parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True);parser.add_argument('--archive',required=True);args=parser.parse_args() # Require an explicit closed stage and a new independent output path.
ROOT=Path('/dev/shm/bridge_complex_v2_20261025');stage=Path(args.stage).resolve();archive=Path(args.archive).resolve() # Keep snapshot paths scoped to this V2 campaign.
assert stage.is_relative_to(ROOT/'operator/formal') and archive.is_relative_to(ROOT/'checkpoints') and not archive.exists() # Reject arbitrary sources, live-parent snapshots and replacement of prior evidence.
work=json.loads((stage/'actual_work.json').read_text());assert work['status']=='COMPLETE' and (stage/'stage_commit.json').is_file() # A partially completed worker cannot be packaged as a closed stage.
def sha(path): # Compute complete content identities using bounded-memory reads.
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest() # Never substitute a pathname or timestamp for content verification.
files=sorted(path for path in stage.rglob('*') if path.is_file() and '__pycache__' not in path.parts) # Include all scientific stage data while excluding reproducible interpreter cache files.
records=[{'source':str(path),'member':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns,'sha256':sha(path)} for path in files] # Capture exact source identity before any archive write.
manifest={'scope':'One completed formal training stage; final held-out evaluation remains pending.','stage':str(stage),'actual_updates':work['actual_optimizer_steps'],'actual_loss_calls':work['actual_loss_calls'],'actual_complete_cold_histories':work['actual_complete_cold_histories'],'members':records} # Separate actual optimizer work from test or scientific acceptance claims.
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as writer: # Create an immutable bounded archive rather than updating an in-progress family package.
    for path,item in zip(files,records): writer.write(path,item['member']) # Preserve each stage member's original relative path for reconstruction.
    writer.writestr('CLOSED_STAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)) # Include the exact member list and actual work counts inside the archive.
with zipfile.ZipFile(archive) as reader: # Fully read and verify the archive before making it available for saving.
    assert reader.testzip() is None and len(reader.infolist())==len(records)+1 # Test all member CRCs and reject unexpected membership.
    for item in records: # Verify all scientific bytes after decompression, including model checkpoints and event traces.
        with reader.open(item['member']) as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest() # Stream each potentially large member without loading the full archive.
        assert actual==item['sha256'] and reader.getinfo(item['member']).file_size==item['bytes'] # Reject partial copies, truncation or member substitution.
for path,item in zip(files,records): assert path.stat().st_size==item['bytes'] and path.stat().st_mtime_ns==item['mtime_ns'] and sha(path)==item['sha256'] # Prove the declared closed stage stayed unchanged throughout packaging.
receipt={'status':'ARCHIVE_INTEGRITY_PASS','archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'source_members':len(records),'verified_members':len(records)+1,'manifest':manifest} # Archive integrity does not imply final prediction accuracy.
receipt_path=archive.with_suffix('.receipt.json');assert not receipt_path.exists();receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps({key:value for key,value in receipt.items() if key!='manifest'})) # Preserve exact transfer metadata beside the immutable archive.
