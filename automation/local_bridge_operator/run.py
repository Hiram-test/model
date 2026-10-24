import argparse, concurrent.futures, json, os, sys, time # Orchestrate bounded independent physical solves.
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1' # Prevent nested solver oversubscription.
from fem import * # Reuse audited geometry, physics and evidence definitions.
from scipy.stats import qmc # Generate reproducible low-discrepancy parameter coverage.
def load_base(name): # Load immutable family reference geometry.
    data=np.load(RUN/'meshes'/f'{name}.npz'); meta=json.loads((RUN/'meshes'/f'{name}.json').read_text()) # Read exact saved topology and material metadata.
    return data['xyz'],data['tet'],data['groups'],meta # Preserve node and element ordering.
def work(task): # Execute a single isolated native and independent finite-element calculation.
    name,parameters,identity=task # Unpack immutable job specification.
    try: return solve_case(load_base(name),parameters,identity) # Compute actual physical labels.
    except Exception as error: # Preserve configuration/resource failures without inventing results.
        receipt={'id':identity,'family':name,'status':'FAILED_CONFIGURATION_OR_RESOURCE','error':repr(error)}; path=RUN/'cases'/identity; path.mkdir(parents=True,exist_ok=True); write_json(path/'receipt.json',receipt); return receipt # Record failed task explicitly.
def build(name): # Create and solve a family reference mesh.
    (RUN/'meshes').mkdir(exist_ok=True); base=mesh_family(name) # Generate source-linked local solid topology.
    np.savez_compressed(RUN/'meshes'/f'{name}.npz',xyz=base[0],tet=base[1],groups=base[2]); write_json(RUN/'meshes'/f'{name}.json',base[3]) # Freeze exact family geometry and assumptions.
    result=solve_case(base,[1,1,1,1,1,.5],name+'_reference'); print(json.dumps(result),flush=True); return result # Cross-check actual reference solve immediately.
def initial(): # Build grouped geometry splits before any learned model is fitted.
    tasks=[]; manifest=[] # Allocate physical job ledger and fixed split identities.
    for number,name in enumerate(FAMILIES): # Keep topology families separate and named.
        parameters=qmc.Sobol(6,scramble=True,seed=100+number).random_base2(5) # Fix 32 geometry/load parameter seeds independently of results.
        for i,row in enumerate(parameters[:28]): # Use sixteen training, four validation, four testing and four OOD geometries.
            split='train' if i<16 else ('validation' if i<20 else ('test' if i<24 else 'ood')) # Separate all loads of the same geometry into one partition.
            p=np.array([.8,.85,.85,.9,.4,.15])+row*np.array([.4,.3,.3,.2,1.2,.7]) # Set disclosed research parameter domain.
            if split=='ood': p[0]=1.45+.2*row[0] # Define independent outside-domain longitudinal geometries.
            for load in range(2): # Generate two distinct load patterns for each geometric instance.
                pl=p.copy(); pl[4]=.5+.9*row[4] if load==0 else 1.0+.6*row[4]; pl[5]=.15+.3*row[5] if load==0 else .55+.3*row[5] # Vary amplitudes and spatial pattern without changing structure identity.
                identity=f'{name}_g{i:02d}_l{load}'; tasks.append((name,pl.tolist(),identity)); manifest.append({'id':identity,'geometry_id':f'{name}_g{i:02d}','family':name,'split':split,'params':pl.tolist(),'round':0}) # Freeze source geometry and case identity.
    write_json(RUN/'manifest.json',manifest); write_json(RUN/'contract.json',{'thresholds':{'fem_residual':1e-7,'cross_solver':1e-5,'research_displacement_relative':.05,'research_neural_residual_relative':.05,'mesh_displacement_relative':.05},'parameter_order':['x_scale','y_scale','z_scale','E_scale','force_scale','load_center'],'parameter_domain':[[.8,1.2],[.85,1.15],[.85,1.15],[.9,1.1],[.4,1.6],[.15,.85]],'split':'geometry IDs isolated; two load patterns per geometry; eight component families, not eight bridges','status':'research thresholds, not engineering acceptance limits','native_solver_sha256':sha(ROOT/'solver-runtime/root/usr/bin/ccx-precision-v2'),'md_sha256':sha(ROOT/'inputs/bridge_group_three_module_autoregressive_design.md')}) # Register gates and scope before training.
    results=[] # Accumulate every outcome, including failures.
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool: # Bound independent CPU finite-element tasks.
        for index,result in enumerate(pool.map(work,tasks)): # Consume every completed task in stable order.
            results.append(result) # Keep all results rather than dropping difficult cases.
            if index%8==0: print(index+1,len(tasks),result['id'],result['status'],flush=True) # Report concrete progress for active monitoring.
    write_json(RUN/'initial_results.json',results); print('COMPLETE',len(results),flush=True) # Persist full qualification ledger.
if __name__=='__main__': # Run only the explicitly selected orchestration stage.
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['build','initial']); parser.add_argument('--family',choices=FAMILIES); args=parser.parse_args() # Parse controlled task scope.
    if args.stage=='build': # Generate a single family or all named topologies.
        for name in ([args.family] if args.family else FAMILIES): build(name) # Complete each requested source-to-solver reference.
    else: initial() # Execute the complete fixed initial experiment ledger.
