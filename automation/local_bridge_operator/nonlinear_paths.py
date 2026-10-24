import json,concurrent.futures # Freeze independent continuation-path tests and execute genuine native solves.
import numpy as np # Specify unseen endpoint amplitudes and compute increment sensitivity.
from nonlinear_data import run_case,PATH # Reuse exactly the same physical formulation and audited native writer.
from nonlinear_mechanics import OUT # Preserve all experiment evidence under one nonlinear package.
from fem import write_json # Store strict JSON numerical receipts.
def main(): # Evaluate independent paths and finer continuation increments after the geometry manifest is frozen.
    manifest=json.loads((OUT/'manifest.json').read_text());alternate=[0.,.2,.65,1.,.3,-.45,-.15,0.,.7,.1,.4,0.];tasks=[] # Keep new path amplitudes within the declared physical envelope.
    for item in manifest: # Select only test geometries so no path-test field can enter fitting.
        if item['split']=='test': tasks.append({**item,'id':item['id']+'_unseen_path','source_geometry_id':item['id'],'load_path':alternate,'split':'independent_path_test'}) # Hold out both the actual endpoint sequence and its states from training.
        if item['id'] in ['splice_g11','deck_g11']: tasks.append({**item,'id':item['id']+'_fine_increment','source_geometry_id':item['id'],'load_path':PATH.tolist(),'increment':.125,'split':'increment_verification'}) # Halve native continuation increments on two independent geometries.
    write_json(OUT/'independent_path_manifest.json',tasks);records=[] # Freeze all independent tests before reading their solutions.
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool: # Bound native solver resources across eight additional physical paths.
        for record in pool.map(run_case,tasks): records.append(record);write_json(OUT/'independent_path_native_results.json',records);print(record['id'],record['status'],record['max_nonlinear_residual'],flush=True) # Save every outcome as it completes.
    refinement=[] # Compare only matching actual endpoint solutions.
    for item in tasks: # Audit native increment sensitivity separately from surrogate accuracy.
        if item['split']!='increment_verification': continue # Exclude intentionally different load paths from refinement comparisons.
        original=np.load(OUT/'cases'/item['source_geometry_id']/'trajectory.npz')['displacement'];fine=np.load(OUT/'cases'/item['id']/'trajectory.npz')['displacement'];refinement.append({'geometry_id':item['source_geometry_id'],'coarse_increment':.25,'fine_increment':.125,'trajectory_relative_L2':float(np.linalg.norm(fine-original)/np.linalg.norm(fine)),'max_endpoint_difference_mm':float(np.max(np.abs(fine-original))),'coarse_evidence':f"build/local-nonlinear-20261024/cases/{item['source_geometry_id']}/model.dat",'fine_evidence':f"build/local-nonlinear-20261024/cases/{item['id']}/model.dat"}) # Quantify actual continuation discretization independence.
    write_json(OUT/'increment_sensitivity.json',refinement) # Publish native numerical verification evidence.
if __name__=='__main__': main() # Execute every declared independent path and increment refinement.
