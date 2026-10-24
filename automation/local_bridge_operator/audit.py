import os # Fix numerical thread policy for deterministic verification.
os.environ['OPENBLAS_NUM_THREADS']='1' # Keep independent test cost bounded.
import ast,json,zipfile # Validate actual code, experiment identities and file integrity.
import numpy as np # Evaluate rigid-body and constitutive invariants.
from scipy.sparse import load_npz # Load physical operators preserved from real solves.
from run import * # Reuse exact model definitions and declared parameter feasibility rules.
def main(): # Audit scientific assumptions and execution evidence without changing results.
    checks=[];mesh_report=[] # Collect explicit pass/fail records for every numerical invariant.
    for family in FAMILIES: # Test each distinct physical topology independently.
        base=load_base(family);path=RUN/'cases'/f'{family}_reference';data=np.load(path/'fields.npz');K=load_npz(path/'stiffness.npz');xyz=data['xyz'];centered=xyz-xyz.mean(axis=0);modes=[] # Use the actual full unconstrained stiffness operator.
        for axis in range(3): # Generate three translations and three infinitesimal rotations.
            direction=np.eye(3)[axis];modes.extend([np.tile(direction,(len(xyz),1)).ravel(),np.cross(np.tile(direction,(len(xyz),1)),centered).ravel()]) # Construct exact solid rigid-body motions.
        rigid=max(float(np.linalg.norm(K@mode)/max(np.linalg.norm(K.data)*np.linalg.norm(mode),1e-30)) for mode in modes);asymmetry=float(np.linalg.norm((K-K.T).data)/max(np.linalg.norm(K.data),1e-30)) # Check material-frame invariance and energy symmetry.
        checks.append({'test':'rigid_body_and_symmetry','family':family,'rigid_relative':rigid,'symmetry_relative':asymmetry,'pass':rigid<1e-12 and asymmetry<1e-12}) # Preserve physical invariants independently from solved label error.
        rejected=[] # Check physically invalid model proposals are quarantined before assembly.
        for p in [[-1,1,1,1,1,.5],[1,1,1,-1,1,.5],[1,1,1,1,-1,.5],[1,1,1,1,1,1.5]]: # Exercise dimension, modulus, force and load-location invalidity.
            try: make_case(base,p); rejected.append(False) # Treat accidental accepted infeasible input as a test failure.
            except ValueError: rejected.append(True) # Verify explicit feasibility rejection.
        checks.append({'test':'invalid_parameter_rejection','family':family,'pass':all(rejected),'count':len(rejected)}) # Report exact negative test denominator.
        levels=[json.loads((path/'receipt.json').read_text())]+[json.loads(p.read_text()) for p in sorted((RUN/'cases').glob(f'{family}_mesh_*/receipt.json'),key=lambda p:float(p.parent.name.split('_')[-1]),reverse=True)] # Preserve all actual mesh levels in decreasing element-size order.
        distinct=[] # Exclude unchanged meshes from refinement evidence.
        for record in levels: # Track genuine topology-resolution changes.
            if not distinct or record['element_count']!=distinct[-1]['element_count']: distinct.append(record) # Never report identical meshes as proof of convergence.
        last,prior=distinct[-1],distinct[-2];du=abs(last['max_displacement_mm']-prior['max_displacement_mm'])/last['max_displacement_mm'];de=abs(last['strain_energy_Nmm']-prior['strain_energy_Nmm'])/last['strain_energy_Nmm'];coarse=abs(last['max_displacement_mm']-levels[0]['max_displacement_mm'])/last['max_displacement_mm'] # Separate final fine-pair convergence from coarse training-label bias.
        mesh_report.append({'family':family,'levels':[{'id':v['id'],'nodes':v['node_count'],'elements':v['element_count'],'peak_mm':v['max_displacement_mm'],'energy_Nmm':v['strain_energy_Nmm']} for v in levels],'distinct_meshes':len(distinct),'final_peak_change':du,'final_energy_change':de,'fine_pair_pass':du<.05 and de<.05,'coarse_training_peak_vs_finest':coarse,'coarse_mesh_qualified_for_peak':coarse<.05,'scope':'reference geometry only; this does not certify every sampled geometry'}) # Document unresolved discretization limitations explicitly.
    files=[];issues=[] # Audit all generated physical experiment files.
    for manifest in ['manifest.json','calibration_manifest.json']+[f'manifest_{name}.json' for name in FAMILIES]: # Include initial, acquired and independent calibration cases.
        files.extend(m['id'] for m in json.loads((RUN/manifest).read_text())) # Preserve all declared experiment IDs.
    for identity in sorted(set(files)): # Avoid double-counting initial cases repeated in family manifests.
        path=RUN/'cases'/identity;receipt=json.loads((path/'receipt.json').read_text()) # Load exact scientific qualification.
        for name,expected in [('model.inp',receipt['input_sha256']),('model.dat',receipt['ccx']['dat_sha256']),('model.frd',receipt['ccx']['frd_sha256'])]: # Validate exact source and native output identity.
            if sha(path/name)!=expected: issues.append({'id':identity,'file':name,'issue':'hash_mismatch'}) # Flag any silently changed evidence.
        for name in ['fields.npz','stiffness.npz']: # Verify complete compressed numerical archives.
            try: # Preserve corrupt-file diagnostics without aborting the rest of the audit.
                with zipfile.ZipFile(path/name) as archive: assert archive.testzip() is None # Check all ZIP members and CRCs.
            except Exception as error: issues.append({'id':identity,'file':name,'issue':repr(error)}) # Record actual missing or corrupt numerical data.
    source=Path(__file__).parent;source_hashes={} # Freeze every authored scientific script after testing.
    for path in source.glob('*.py'): # Check user-requested per-line comments and Python syntax.
        ast.parse(path.read_text());source_hashes[path.name]=sha(path) # Require parseable code and exact provenance.
        for number,line in enumerate(path.read_text().splitlines(),1): # Inspect all nonblank authored code lines.
            if line.strip() and '#' not in line: issues.append({'file':path.name,'line':number,'issue':'missing_line_comment'}) # Enforce explicit source-code documentation requirement.
    write_json(RUN/'mesh_convergence_final.json',mesh_report);write_json(RUN/'audit.json',{'physical_invariants':checks,'dataset_cases':len(set(files)),'integrity_issues':issues,'source_sha256':source_hashes,'all_invariants_pass':all(x['pass'] for x in checks),'status':'PASS' if not issues and all(x['pass'] for x in checks) else 'FAIL'}) # Preserve complete numerical and storage audit independently of engineering release.
    print('AUDIT',len(set(files)),len(issues),all(x['pass'] for x in checks),flush=True) # Report completed audit outcome.
if __name__=='__main__': main() # Execute declared scientific validation suite.
