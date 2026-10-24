import ast,hashlib,io,json,tokenize # Independently validate final source syntax and native artifact identities.
from pathlib import Path # Resolve evidence from the relocated repository rather than saved absolute paths.
from fem import REPO,write_json # Reuse the declared repository location and JSON writer only.
BUILD=REPO/'build';OUT=BUILD/'completion-audit-20261024' # Keep integration checks separate from producer-generated receipts.
def digest(path): # Hash exact evidence bytes without rewriting native output.
    h=hashlib.sha256() # Initialize an independently computed byte identity.
    with path.open('rb') as stream: # Bound memory while checking large native outputs.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Include every original file byte.
    return h.hexdigest() # Return the complete SHA-256 identity.
def read(path): # Load the producer's declared evidence record without modifying it.
    return json.loads(path.read_text()) # Fail visibly if a final record is missing or malformed.
def main(): # Verify the final accepted evidence set while retaining historical failures separately.
    checks=[];syntax=[];missing_comments=[] # Maintain explicit denominators for every independent check.
    def check(path,expected,role): # Compare recorded identity with the actual current evidence.
        exists=path.is_file();actual=digest(path) if exists else None;checks.append({'path':str(path.relative_to(REPO)),'role':role,'expected_sha256':expected,'actual_sha256':actual,'pass':exists and actual==expected}) # Reject missing, truncated or altered native files.
    source=Path(__file__).parent # Audit the complete authored local-operator implementation.
    for p in sorted(source.glob('*.py')): # Check each runnable source independently.
        text=p.read_text();ast.parse(text);syntax.append({'path':str(p.relative_to(REPO)),'sha256':digest(p)});comment_lines={t.start[0] for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type==tokenize.COMMENT} # Use real Python tokens rather than searching for a hash inside strings.
        missing_comments.extend({'file':p.name,'line':i} for i,line in enumerate(text.splitlines(),1) if line.strip() and i not in comment_lines) # Enforce the user's every-nonblank-code-line comment convention.
    coupling=read(BUILD/'coupling_completed/summary.json') # Inspect the finalized one-way submodel scope and case list.
    for row in coupling['local_solves']: # Check every accepted local mesh without dropping difficult refinements.
        for extension,key in [('inp','native_input_sha256'),('dat','native_dat_sha256'),('frd','native_frd_sha256')]: check(BUILD/'coupling_completed'/row['case']/('local.'+extension),row[key],'coupling_native') # Bind actual local solve output to its solver receipt.
    nonlinear=BUILD/'local-nonlinear-20261024';paths=read(nonlinear/'manifest.json')+read(nonlinear/'independent_path_manifest.json') # Include original and independently varied native load paths.
    for item in paths: # Audit each qualified native path exactly once by its manifest identity.
        folder=nonlinear/'cases'/item['id'];receipt=read(folder/'receipt.json') # Resolve evidence locally to support unpacking on another machine.
        for extension,key in [('inp','input_sha256'),('dat','dat_sha256'),('frd','frd_sha256')]: check(folder/('model.'+extension),receipt[key],'nonlinear_native') # Verify original input and both original result formats.
    contact=BUILD/'local-contact-20261024';report=read(contact/'REPORT.json') # Follow only the explicitly selected final seven contact cases.
    for row in report['cases']: # Exclude superseded replay failures from the accepted denominator without deleting their files.
        folder=contact/row['case'];receipt=read(folder/'receipt.json') # Read the final selected case receipt.
        for name in ['contact.inp','contact.dat','contact.frd']: check(folder/name,receipt['files'][name],'contact_native') # Verify original contact input and result bytes independently.
    selection=read(BUILD/'local-dynamics-20261024/native_receipt_selection.json');historical=[] # Follow the explicit final receipt selection and retain known historical integrity failures.
    for row in selection['selected_receipts']: # Include all authoritative native modal and transient solver comparisons.
        path=REPO/row['selected_receipt'];receipt=read(path) # Use the independently executed final native run identity.
        for extension,key in [('inp','input_sha256'),('dat','dat_sha256')]: check(path.with_name('model.'+extension),receipt[key],'dynamic_native') # Audit every selected original input and result file.
        if row['superseded_receipt']: # Require explicit evidence for every replacement of an inconsistent historical output.
            old_path=REPO/row['superseded_receipt'];old=read(old_path);observed=digest(old_path.with_name('model.dat'));verified=receipt['input_sha256']==old['input_sha256'] and receipt['dat_sha256']==old['dat_sha256'] and observed==receipt['observed_old_dat_sha256'];historical.append({'superseded_receipt':row['superseded_receipt'],'selected_receipt':row['selected_receipt'],'original_expected_dat_sha256':old['dat_sha256'],'preserved_old_actual_sha256':observed,'new_replay_matches_original_expected':verified,'reason':row['reason']}) # Require identical-input real replay restoring the original expected bytes rather than silently changing the expected hash.
            check(old_path.with_name('model.dat'),receipt['observed_old_dat_sha256'],'preserved_historical_mismatch') # Verify the damaged historical evidence remains preserved and distinctly classified.
    invariants=read(OUT/'physical_invariants.json');residual=read(BUILD/'residual-online-20261024/summary.json');unified=read(BUILD/'unified-topology-20261024/summary.json') # Require completed numerical and neural evaluation records.
    gates={'physical_invariants':invariants['status']=='PASS','one_way_coupling':coupling['status']=='PASS_ONE_WAY_SUBMODEL','residual_384_comparisons':residual['comparisons']==384 and residual['accepted']==384,'native_hashes':all(x['pass'] for x in checks),'historical_replay_restores_original':all(x['new_replay_matches_original_expected'] for x in historical),'source_comments':not missing_comments,'shared_topology_release_remains_hold':str(unified['release']).startswith('HOLD')} # Keep evidence validity separate from neural release qualification.
    result={'status':'PASS' if all(gates.values()) else 'FAIL','gates':gates,'native_hash_checks':len(checks),'native_hash_failures':[x for x in checks if not x['pass']],'historical_integrity_events':historical,'checks':checks,'parsed_source_files':len(syntax),'sources':syntax,'comment_violations':missing_comments,'scope':'Independent integration checks verify provenance and declared denominators; numerical and neural accuracy remain separately reported by each task.'};write_json(OUT/'integration_audit.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['checks','sources']}),flush=True) # Save complete evidence and concise failure diagnostics.
if __name__=='__main__': main() # Run the audit only after all delegated outputs are finalized.
