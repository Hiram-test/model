from pathlib import Path # Preserve a completed native discretization without touching the next live experiment.
import hashlib,json,time,zipfile # Verify exact member bytes and retain numerical qualification separately from archive integrity.
ROOT=Path('/dev/shm/bridge_complex_v2_20261025');THERMAL=ROOT/'thermal/hex8';OUT=ROOT/'checkpoints';OUT.mkdir(exist_ok=True) # Keep the evidence checkpoint inside the V2 namespace.
def digest(path): # Hash complete stable files with bounded memory.
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest() # Record actual bytes rather than filenames or timestamps.
files=sorted((THERMAL/'cases/tv2_hex_l1').glob('*'))+[THERMAL/name for name in ['tv2_hex_l1.row.json','mesh_l0_l1_comparison.json','mesh_l0_l1_error_localization_v2.json','same_CAD_physics_identity.json','qualification_specification.json','bidirectional_comparison_specification.json','bidirectional_comparison_identity_check.json','native_energy_semantics.json']] # Include only the closed fine case and completed comparisons, not the live third-level work.
files+=[ROOT/'audit/v2_thermal_fine_native_identity.json',Path(__file__)] # Retain the independent identity audit and this reproducible packaging recipe.
assert all(path.is_file() for path in files) and len(files)==len(set(files)) # Reject missing or duplicate sources before publishing an incomplete package.
records=[{'path':str(path),'archive_path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns,'sha256':digest(path)} for path in files] # Capture immutable pre-copy identities for every scientific source.
manifest={'schema':'bridge.v2.thermal.fine.checkpoint.v1','scope':'Completed fine discretization and real bidirectional comparison only; no neural-operator training or test result.','native_completion':'VALID_CONVERGED','spatial_qualification':'HOLD','source_files':records} # Keep solver completion distinct from full-field mesh accuracy.
archive=OUT/'bridge_v2_thermal_fine_checkpoint.zip';assert not archive.exists() # Never overwrite a previously published evidence identity.
with zipfile.ZipFile(archive,'x') as writer: # Create a new archive only once after the complete source inventory is known.
    for path,item in zip(files,records): writer.write(path,item['archive_path'],compress_type=zipfile.ZIP_STORED if path.suffix in {'.zip','.npz'} else zipfile.ZIP_DEFLATED) # Avoid recompressing already compressed native and field payloads.
    writer.writestr('CHECKPOINT_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2),compress_type=zipfile.ZIP_DEFLATED) # Bind the exact source list and scientific status inside the package.
with zipfile.ZipFile(archive) as reader: # Fully read every archive member instead of testing only the central directory.
    assert reader.testzip() is None and len(reader.infolist())==len(records)+1 # Verify every CRC and ensure complete expected membership.
    for item in records: # Recompute each member's complete content identity after compression and decompression.
        with reader.open(item['archive_path']) as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest() # Stream large native files without duplicating them in memory.
        assert actual==item['sha256'] and reader.getinfo(item['archive_path']).file_size==item['bytes'] # Reject any truncation or accidental content substitution.
for path,item in zip(files,records): assert path.stat().st_size==item['bytes'] and path.stat().st_mtime_ns==item['mtime_ns'] and digest(path)==item['sha256'] # Prove no supposedly closed source changed while packaging.
receipt={'status':'ARCHIVE_INTEGRITY_PASS','scientific_spatial_qualification':'HOLD','archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest(archive),'source_members':len(records),'verified_members':len(records)+1,'sources_stable_before_after':True,'manifest':manifest} # Archive correctness never upgrades the physical qualification.
(OUT/'thermal_fine_checkpoint_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps({key:value for key,value in receipt.items() if key!='manifest'})) # Emit only concise verified transfer metadata.
