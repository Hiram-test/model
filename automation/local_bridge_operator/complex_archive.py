import argparse,hashlib,json,os,zipfile # Package actual complex-physics evidence with byte identities and CRC verification.
from pathlib import Path # Preserve exact repository-relative input and result locations.
REPO=Path(__file__).resolve().parents[2] # Resolve the current repository without relying on a user-specific home directory.
SOURCE=REPO/'build/complex-nonlinear-20261024';DEST=REPO.parent/'deliverables' # Separate scientific evidence from final delivery packaging.
def digest(path): # Hash large raw finite-element outputs with bounded memory.
    h=hashlib.sha256() # Initialize a fresh digest for each evidence object.
    with path.open('rb') as stream: # Read the complete file in stable byte order.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Include every byte rather than a metadata approximation.
    return h.hexdigest() # Return the exact file fingerprint.
def evidence_path(raw): # Relocate preserved evidence metadata to the current extracted repository without reading another workspace copy.
    marker='/build/'+SOURCE.name+'/';text=str(raw);path=SOURCE/text.split(marker,1)[1] if marker in text else Path(raw) # Preserve the exact evidence-relative suffix from the original immutable receipt.
    if not path.is_absolute(): path=REPO/path # Resolve stored repository-relative contracts independently of the caller's current directory.
    path=path.resolve();assert path.is_relative_to(SOURCE.resolve());return path # Restrict every reviewed preservation mapping to this campaign's evidence tree and normalize dictionary identities.
def expected_result_hashes(): # Keep final audited output identities binding even if a source pathname changes after the last independent audit.
    registry=json.loads((SOURCE/'learning/campaign_learning_index.json').read_text());expected={} # Read the explicitly chosen completed families rather than old diagnostic directories.
    for family in ['friction','rebar']: # Both completed learning branches must retain every audited final field and selected weight.
        folder=SOURCE/registry['families'][family];integrity=json.loads((folder/'final_artifact_integrity.json').read_text());assert integrity['all_zip_crc_shape_and_reference_checks_passed'] and not integrity['failures'] # Require the actual full-field archive checks to have completed successfully.
        for item in integrity['archives']: expected[(folder/item['path']).resolve()]=item['sha256'];expected[evidence_path(item['native_npz'])]=item['native_sha256'] # Bind all final and existing fine-mesh prediction bytes to their exact native references.
        for item in json.loads((folder/'frozen_models_before_test.json').read_text()).values(): expected[evidence_path(item['checkpoint'])]=item['sha256'] # Preserve the exact model versions frozen before independent test exposure.
        contract=json.loads((folder/'experiment_contract.json').read_text());expected[evidence_path(contract['source_index'])]=contract['source_index_sha256'] # Bind the original selected reference index as well as learned outputs.
        receipt=folder/'final_delivery_receipt.json' # Some branches provide an additional complete final-stage evidence index.
        if receipt.exists(): # Preserve each explicitly indexed final metric, recovery or physical-check file.
            for item in json.loads(receipt.read_text())['sources'].values(): expected[(folder/item['path']).resolve()]=item['sha256'] # A later storage change cannot silently alter an already indexed scientific result.
        aliases=folder/'artifact_export_evidence/late_staging_alias_manifest.json' # Retain exact successful and failed payload aliases when omitting old staging duplicates.
        if aliases.exists(): # Failure bytes remain protected even though they are intentionally invalid inner ZIP files.
            for item in json.loads(aliases.read_text())['records']: expected[(folder/item['retained_identical_evidence_alias']).resolve()]=item['sha256'] # Require each preservation representation to retain its original observed bytes.
    return expected # Final packaging separately hashes the actual ZIP members against these identities.
def selected_files(): # Package authoritative evidence once while retaining every separately preserved failure and unknown fragment.
    policies=sorted((SOURCE/'thermoplastic/temporary_evidence').glob('*/package_exclusions.json'));assert len(policies)==1;policy_path=policies[0];policy=json.loads(policy_path.read_text());assert policy['status']=='PASS' and not policy['aborts'];excluded={};records=[] # Use the completed explicit identity review rather than treating all similarly named files as duplicates.
    for item in policy['authority_archives']: assert digest(evidence_path(item['archive']))==item['sha256'] # Require all authoritative archives to retain their reviewed byte identity before omitting any duplicate.
    for item in policy['retained_unproven_copies']: assert evidence_path(item['path']).stat().st_size==item['bytes'] and digest(evidence_path(item['path']))==item['sha256'] # Preserve each observed nonequivalent temporary fragment as an exact nonhidden evidence copy.
    for item in policy['temporary_original_paths']: excluded[evidence_path(item['path'])]={'sha256':item['sha256'],'bytes':item['bytes'],'reason':'Reviewed temporary original; exact copy or authoritative prefix reconstruction is preserved in the temporary identity manifest.'} # Keep the original files untouched while packaging their independently reviewed preservation representation.
    verification=json.loads((policy_path.parent/'archive_verification.json').read_text());assert verification['protected_documents_unchanged'] and all(value is True for value in verification['protected_documents_unchanged'].values()) # Require every protected document identity check, rather than merely a nonempty mapping, to have passed.
    for raw,expected in verification['protected_document_sha256'].items(): assert digest(evidence_path(raw))==expected # Recheck the current protected documents when packaging instead of relying only on the earlier review timestamp.
    for archive in verification['archives']: # Recognize native output duplicates even when a previously removed identical path has reappeared.
        for member in archive['members']: # Retain small input decks directly for convenient inspection while avoiding duplicate large native output streams.
            path=evidence_path(archive['archive']).parent/member['name'] # Resolve only a member of an explicitly verified authoritative archive.
            if path.suffix!='.inp': excluded[path]={'sha256':member['sha256'],'bytes':member['bytes'],'reason':'Exact native output retained in authoritative archive','archive':archive['archive'],'member':member['name']} # A differing current file will remain included rather than being silently omitted.
    for manifest in (SOURCE/'learning').glob('*/artifact_export_evidence/late_staging_alias_manifest.json'): # Omit a late staging duplicate only when its retained successful or failed payload is still byte-identical.
        folder=manifest.parent.parent;aliases=json.loads(manifest.read_text()) # Keep the original observation manifest itself inside the delivered evidence.
        for item in aliases['records']: # Never classify an unlisted staging object by filename alone.
            alias=folder/item['retained_identical_evidence_alias'];assert alias.stat().st_size==item['bytes'] and digest(alias)==item['sha256'];excluded[folder/item['observed_staging_path']]={'sha256':item['sha256'],'bytes':item['bytes'],'reason':'Exact staging bytes retained under independently verified evidence alias','retained_alias':str(alias.relative_to(REPO))} # Preserve actual failed bytes without storing identical duplicates as additional test histories.
    files=[] # Build a finite snapshot of actual scientific artifacts rather than recursively copying active workspace housekeeping.
    for path in sorted(SOURCE.rglob('*')): # Preserve deterministic delivery order and every unique scientific object or unclassified fragment.
        if not path.is_file() or '__pycache__' in path.parts or path.name in {'ccx_2.21.pdf','ccx_2.21.txt'}: continue # Exclude compiled caches and the externally linked copyrighted manual from redistribution.
        if path in excluded and path.stat().st_size==excluded[path]['bytes'] and digest(path)==excluded[path]['sha256']: records.append({'path':str(path.relative_to(REPO)),**excluded[path]});continue # Omit only byte-identical explicitly reviewed duplicates, including temporary paths, with an exact preservation mapping.
        files.append(path) # Keep every unlisted or changed object, including hidden unknown fragments, unique failures and every separately preserved copy.
    receipt=SOURCE/'archive_selection.json';receipt.write_text(json.dumps({'policy_sha256':digest(policy_path),'policy':str(policy_path.relative_to(REPO)),'excluded_original_paths':records,'scientific_evidence_policy':'All authoritative archives, native fields, model outputs and unique preserved failures retained. Original temporary paths are not formal FEM samples; no source file is deleted by packaging.'},ensure_ascii=False,indent=2)+'\n');files=[path for path in files if path!=receipt]+[receipt];return sorted(files) # Store the exact delivery boundary inside the resulting evidence set.
def package(): # Create individually usable ZIP archives only after producers and audits finish.
    publication=json.loads((SOURCE/'github_publication.json').read_text());assert publication['commit'] and publication['verified'];DEST.mkdir(exist_ok=True);files=selected_files();expected=expected_result_hashes();assert all(path in files for path in expected);parts=[];archive=None;members=[];index=0 # Require a verified immutable source commit and retain every anchored final field, native reference and frozen model.
    def close(): # Seal each standalone archive and inspect its complete compression integrity.
        if archive is None: return # Handle the initial unopened archive state.
        archive.writestr('evidence_manifests/'+output.stem+'.json',json.dumps({'schema':'bridge.complex.evidence.archive.v1','members':members,'source_code':publication,'solver_manual':'https://www.dhondt.de/ccx_2.21.pdf','scope':'Native cases, immutable source receipts, full fields, model checkpoints, active-learning histories and independent audits; failed attempts are retained.'},ensure_ascii=False,indent=2));archive.close() # Record every packaged member and the exact verified immutable source commit.
        with zipfile.ZipFile(output) as verify: # Verify both compression integrity and the complete bytes actually packaged under every declared source identity.
            assert verify.testzip() is None # Reject damaged archives before upload.
            for member in members: # A concurrent same-size replacement must not pass merely because filesystem timestamps happen to match.
                fingerprint=hashlib.sha256() # Recompute each manifest identity from the archive bytes themselves.
                with verify.open(member['path']) as stream: # Read every stored native or learned field without trusting the current source pathname.
                    for block in iter(lambda:stream.read(1024*1024),b''): fingerprint.update(block) # Bound memory while covering the full archived object.
                assert fingerprint.hexdigest()==member['sha256'],f"Archived member identity mismatch: {member['path']}" # Refuse publication of an archive whose claimed source bytes differ from its actual payload.
        part={'name':output.name,'local_path':str(output),'bytes':output.stat().st_size,'sha256':digest(output),'members':len(members)};parts.append(part);receipt=output.with_suffix('.sealed.json');temporary=receipt.with_suffix('.json.tmp') # Persist each verified sealed-part identity before creating the next archive so a streaming upload can check the original producer digest.
        with temporary.open('w') as stream: stream.write(json.dumps({'source_code':publication,'part':part,'crc_and_every_member_sha256_verified':True},ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno()) # Complete the small sealing receipt before publishing its stable pathname.
        temporary.replace(receipt) # Publish the completed identity atomically; the next numbered ZIP is opened only after this succeeds.
    for path in files: # Include all scientific evidence in deterministic path order.
        if archive is None or archive.fp.tell()>280000000: # Keep each complete ZIP below the transfer soft limit apart from its final member.
            close();index+=1;output=DEST/f'bridge_complex_fullfield_{index:02d}.zip';archive=zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True);members=[] # Create a normal standalone ZIP instead of an opaque split volume.
        before=path.stat();identity=digest(path);assert path not in expected or identity==expected[path],f'Final audited result identity changed: {path}';relative=str(path.relative_to(REPO));archive.write(path,relative);after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),f'Concurrent producer changed {path}';members.append({'path':relative,'bytes':before.st_size,'sha256':identity}) # Refuse changes both during collection and between final audit and packaging.
    close();(DEST/'bridge_complex_fullfield_archives.json').write_text(json.dumps(parts,indent=2)+'\n');return parts # Preserve exact upload inputs alongside the archives.
if __name__=='__main__': # Require an explicit final packaging action.
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true',required=True);parser.parse_args();print(json.dumps(package(),indent=2),flush=True) # Do not launch training or silently imply that unfinished evidence is final.
