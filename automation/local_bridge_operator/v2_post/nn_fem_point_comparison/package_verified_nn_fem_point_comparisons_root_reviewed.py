from pathlib import Path # Package verified point-value figures while preserving all historical source and failed layout evidence.
import hashlib,json,zipfile,io,ast,tokenize,datetime # Use standard-library streaming only, with no numerical or rendering libraries.
HERE=Path(__file__).resolve().parent # All outputs belong to this independent visualization bundle.
def read(path): # Read an explicitly selected small receipt.
    return json.loads(Path(path).read_text()) # Do not discover or deserialize scientific arrays.
def ref(path): # Stream file identity without materializing arrays or images.
    path=Path(path) # Preserve exact source paths in the portable archive manifest.
    with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest() # Bind all bytes with bounded memory.
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha} # A filename alone never establishes scientific provenance.
def checked(item): # Verify a previously recorded source identity before packaging.
    path=Path(item['path']);assert ref(path)['sha256']==item['sha256'];return path # Unexpected source mutations stop the bundle.
def write(path,value): # Create fresh packaging artifacts without changing prior rendering receipts.
    assert not path.exists();path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n') # Every lifecycle stage stays separately inspectable.
def main(): # Only completed image-by-image QA authorizes the final visualization archive.
    code=Path(__file__).read_text();ast.parse(code);comments={t.start[0] for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type==tokenize.COMMENT};assert all(not line.strip() or i in comments for i,line in enumerate(code.splitlines(),1)) # Check actual comment tokens on all authored Python lines.
    qa_path=HERE/'final_visual_qa.json';qa=read(qa_path);assert qa['status']=='PASS_FOUR_FIXED_FIGURES_VISUAL_QA_ONLY' and qa['scientific_accuracy_pass_claimed'] is False;index_path=checked(qa['render_index']);index=read(index_path);assert index['rendered_figures']==4 and index['point_arrays_changed'] is False # Rendering success does not override neural or continuum accuracy HOLD.
    root_review_path=HERE/'root_visual_review.json';root_review=read(root_review_path);assert root_review['status']=='PASS_ROOT_FOUR_FIXED_FIGURES_VISUAL_REVIEW_ONLY' and root_review['inspected_images']==qa['inspected_images'] and root_review['scientific_accuracy_pass_claimed'] is False;checked(root_review['author_visual_qa']) # Require the actual independent parent image-by-image review and unchanged final PNG identities.
    for row in index['cases']:assert row['image'] in qa['inspected_images'];checked(row['image']);checked(row['point_values']) # The delivered images and original thin scientific point payloads must match QA exactly.
    sources={} # Explicit member paths prevent accidental inclusion of caches or unrelated training outputs.
    def add(path,member): # Reject duplicate archive names and path traversal.
        path=Path(path);assert path.is_file() and member not in sources and not member.startswith('/') and '..' not in Path(member).parts;sources[member]=ref(path) # Every archive member retains its original file identity.
    for path in sorted(HERE.iterdir()): # Include only authored source, review and lifecycle metadata from this visualization task.
        if path.is_file() and path.suffix in ('.py','.json','.md','.diff') and path.name not in ('publication_manifest.json','posttest_audit_adapter_publication_manifest.json','point_comparison_reviewed_bundle_manifest.json','point_comparison_reviewed_bundle_receipt.json','point_comparison_delivery_manifest.json','point_comparison_bundle_manifest.json','point_comparison_bundle_receipt.json'):add(path,'sources/'+path.name) # No scientific source outside this task is discovered by a broad directory traversal.
    for name in ['rendered','rendered_layout_v2']: # Preserve the failed first images as explicit history alongside corrected deliverables.
        for path in sorted((HERE/name).iterdir()): # Matplotlib caches are directories and therefore excluded.
            if path.is_file() and path.suffix in ('.png','.json','.npz'):add(path,name+'/'+path.name) # Thin point payloads are packaged verbatim without numerical decoding.
    audit_files={'fullfield_audit':index['audit_bindings']['fullfield_audit'],'selected_native_audit':index['audit_bindings']['selected_native_audit']} # These two actual scientific audits remain part of the final provenance chain.
    for key,item in audit_files.items():add(checked(item),'evidence/'+key+'.json') # Recheck exact source hashes before adding each audit.
    adapter=read(HERE/'posttest_audit_adapter_addendum.json') # Retain original failure and narrowly corrected auditor lineage.
    for key in ['original_native_auditor','corrected_native_auditor','original_failure','correction','correction_verification_source','independent_native_correction_review']:add(checked(adapter[key]),'evidence/audit_adapter/'+Path(adapter[key]['path']).name) # Historical metadata repair is never hidden from the delivered bundle.
    freeze=read(HERE/'pretest_source_freeze.json') # Include the unchanged producer interfaces required to interpret saved fields.
    for key,item in freeze['dependencies'].items(): # The old auditor is already included at its preserved historical path.
        if key!='native_auditor':add(checked(item),'evidence/frozen_dependencies/'+Path(item['path']).name) # Keep all other original dependency identities unchanged.
    for row in index['cases']: # Native and official export receipts remain accessible per fixed registered example.
        for key in ['native_source_receipt','metadata','export_receipt','official_metrics']:add(checked(row[key]),'evidence/'+row['id']+'/'+key+'.json') # Large full-history fields and checkpoints are referenced, not silently duplicated into a plotting bundle.
    manifest_path=HERE/'point_comparison_reviewed_bundle_manifest.json';manifest={'schema':'bridge.v2.nn_fem_native_point_plots.bundle_manifest.v1','status':'INPUTS_HASH_VERIFIED_BEFORE_ZIP','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scientific_accuracy_pass_claimed':False,'engineering_release':'NOT_CERTIFIED','contents_scope':'Four fixed terminal-frame native-location point plots, exact thin plotted arrays, all source/review/receipt lineage and preserved initial layout failures. Full historical arrays and checkpoints remain externally SHA-bound in source receipts.','root_visual_review':ref(root_review_path),'final_visual_qa':ref(qa_path),'final_images':[row['image'] for row in index['cases']],'original_point_values':[row['point_values'] for row in index['cases']],'members':[{'member':name,'source':item} for name,item in sorted(sources.items())]};write(manifest_path,manifest);add(manifest_path,'point_comparison_reviewed_bundle_manifest.json') # The archive carries its own complete source inventory without a recursive self-hash.
    archive=HERE/'v2_nn_fem_point_comparisons_root_reviewed.zip';assert not archive.exists() # Preserve any earlier complete package rather than overwriting it.
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as stream: # Create one portable archive from immutable verified bytes.
        for name,item in sorted(sources.items()):stream.write(checked(item),name) # Check identity immediately before adding each member.
    verified=[] # Independently reopen the complete resulting archive instead of trusting the writer.
    with zipfile.ZipFile(archive) as stream: # Verify every stored member's full decompressed content and CRC.
        assert stream.testzip() is None and set(stream.namelist())==set(sources) and len(stream.namelist())==len(sources) # Reject corruption, duplicate names, omissions or unexpected additions.
        for info in stream.infolist(): # Stream data to keep packaging memory independent of archive size.
            with stream.open(info) as member:sha=hashlib.file_digest(member,'sha256').hexdigest() # ZIP reading also validates each decompressed CRC.
            source=sources[info.filename];assert sha==source['sha256'] and info.file_size==source['bytes'];checked(source);verified.append({'name':info.filename,'bytes':info.file_size,'compressed_bytes':info.compress_size,'crc32_hex':format(info.CRC,'08x'),'sha256':sha}) # Compare against the original source before and after archive creation.
    receipt={'schema':'bridge.v2.nn_fem_native_point_plots.bundle_receipt.v1','status':'PASS_COMPLETE_ZIP_VERIFICATION','archive':ref(archive),'manifest':ref(manifest_path),'root_visual_review':ref(root_review_path),'visual_qa':ref(qa_path),'member_count':len(verified),'members':verified,'all_original_source_bytes_stable':True,'actual_decompressed_CRC_and_SHA_verified':True,'scientific_accuracy_pass_claimed':False,'engineering_release':'NOT_CERTIFIED','packager_source':ref(__file__)};write(HERE/'point_comparison_reviewed_bundle_receipt.json',receipt);print(json.dumps({'status':receipt['status'],'archive':receipt['archive'],'member_count':len(verified)})) # Packaging PASS describes integrity only and does not convert NN HOLD into an engineering release.
if __name__=='__main__':main() # A source-only review never writes an archive.
