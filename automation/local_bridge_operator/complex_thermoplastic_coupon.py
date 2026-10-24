import os,sys # Resolve pinned mesher dependencies and bound numerical threads.
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1' # Limit every actual finite-element worker.
import argparse,concurrent.futures,json # Manage explicitly versioned coupon tasks and candidate identities.
from pathlib import Path # Preserve source and result provenance.
import numpy as np # Store all source nodes, integration points, and full-field histories.
from scipy.stats import qmc # Generate input-only stratified nonlinear challenges.
import complex_thermoplastic as base # Reuse full-order heat/plastic solvers and complete native state extraction.
OUT=base.OUT/'notched_connector' # Keep this distinct physical model separate without changing another module's output directory at import time.
def generate_mesh(factor=1.): # Build an explicit finite-radius double-notched solid without beam, shell, modal or response-space substitution.
    sys.path.insert(0,str(base.REPO.parent/'local-fem-runtime'));import gmsh # Use the already installed pinned OpenCASCADE/Gmsh runtime.
    folder=OUT/'meshes';folder.mkdir(parents=True,exist_ok=True);path=folder/f'notched_{factor:g}.npz' # Freeze separate actual meshes for refinement studies.
    if path.exists(): return path # Reuse exact existing mesh bytes rather than silently regenerate them.
    gmsh.initialize();gmsh.option.setNumber('General.Terminal',0);gmsh.model.add('notched_connector');occ=gmsh.model.occ;solid=occ.addBox(0,0,0,100.,30.,20.);cutters=[(3,occ.addCylinder(50.,y,-1.,0.,0.,22.,6.)) for y in [0.,30.]];volumes,_=occ.cut([(3,solid)],cutters);occ.synchronize() # Resolve both 6 mm-radius circular side notches through the full20 mm thickness.
    gmsh.option.setNumber('Mesh.MeshSizeMin',3.*factor);gmsh.option.setNumber('Mesh.MeshSizeMax',10.*factor);gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',12);gmsh.option.setNumber('Mesh.RandomSeed',171);gmsh.option.setNumber('General.NumThreads',1);gmsh.model.mesh.generate(3) # Generate deterministic actual3D tetrahedral discretizations.
    tags,coords,_=gmsh.model.mesh.getNodes();lookup={int(tag):i for i,tag in enumerate(tags)};xyz=coords.reshape(-1,3);tet=[] # Preserve all mesher vertex identities.
    for _,volume in volumes: # Collect only actual solid-volume elements.
        types,_,connectivities=gmsh.model.mesh.getElements(3,volume) # Preserve native volume topology.
        for typ,connections in zip(types,connectivities): assert typ==4;tet.extend(np.asarray([lookup[int(v)] for v in connections]).reshape(-1,4)) # Refuse unsupported element representations.
    gmsh.write(str(folder/f'notched_{factor:g}.brep'));gmsh.finalize();tet=np.asarray(tet,int);used=np.unique(tet);remap=np.full(len(xyz),-1);remap[used]=np.arange(len(used));xyz=xyz[used];tet=remap[tet];negative=np.linalg.det(xyz[tet[:,1:]]-xyz[tet[:,0,None]])<0;tet[negative,1],tet[negative,2]=tet[negative,2].copy(),tet[negative,1].copy();points=xyz.tolist();mids={};quadratic=[] # Orient every real element and remove only unused CAD bookkeeping nodes.
    for vertices in tet: # Upgrade the complete straight-sided mesh to native C3D10 interpolation.
        row=vertices.tolist() # Retain the actual four positively oriented corners.
        for a,b in [(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)]: # Use CalculiX native midside ordering.
            edge=tuple(sorted((int(vertices[a]),int(vertices[b])))) # Share midsides exactly between adjacent finite elements.
            if edge not in mids: mids[edge]=len(points);points.append(((xyz[edge[0]]+xyz[edge[1]])/2).tolist()) # Add physical displacement/temperature DOFs without response-space compression.
            row.append(mids[edge]) # Preserve each full quadratic element's interpolation graph.
        quadratic.append(row) # Append the complete ten-node element.
    np.savez_compressed(path,xyz=np.asarray(points),tet=np.asarray(quadratic),groups=np.zeros(len(quadratic),int));base.write_json(folder/f'notched_{factor:g}.json',{'model':'full3Dfinite-radius-double-notched-connector','dimensions_mm':[100.,30.,20.],'notch_radius_mm':6.,'net_width_mm':18.,'mesh_factor':factor,'nodes':len(points),'elements':len(quadratic),'element':'C3D10 straight-sided quadratic tetrahedra; finite-radius CAD surface approximation checked by actual mesh refinement','source':'Declared research connector specimen, not an as-built Zhaqing detail; designed to isolate thermoplastic stress concentration without unresolved slender-girder buckling.','brep_sha256':base.sha(folder/f'notched_{factor:g}.brep'),'mesh_sha256':base.sha(path)}) # Declare exact geometry and source assumptions with editable CAD evidence.
    return path # Return the immutable full-mesh source.
def descriptors(): # Freeze nonlinear coupon history groups independently of observed responses.
    draws=qmc.Sobol(8,scramble=True,seed=142901).random_base2(6);mesh=OUT/'meshes/notched_1.npz';tasks=[] # Separate this parameter design from the original girder studies.
    for i,v in enumerate(draws[:35]): # Keep8training/3validation/4test/4OOD and16unlabelled candidates.
        split='train' if i<8 else ('validation' if i<11 else ('test' if i<15 else ('ood' if i<19 else 'candidate')));p=[.9+.2*v[0],.9+.2*v[1],200.+250.*v[2],.7+1.3*v[3],.85+.3*v[4],.8+.4*v[5],int(v[6]*4),2400.+2400.*v[7]] # Vary actual geometry, nonlinear loading, temperature, strength, conductivity and protocol.
        if split=='ood': p[2]=500.+150.*v[2];p[3]=2.3+.7*v[3] # Hold out higher temperature and larger cyclic strains as independently solved domain shifts.
        tasks.append({'id':f'tc_{i:03d}','group_id':f'tc_{i:03d}','split':split,'family':'thermoplastic_notched_connector','mesh':str(mesh),'geometry_source':'Explicit100x30x20 mm3Dresearchconnectorwithtwo6mmradiusnotches; all dimensions declared assumptions; no bridge-as-built claim.','params':p}) # Keep every state from a physical path in one immutable split.
    return tasks # Return solved tasks and input-only candidates.
def prepare_candidate(descriptor): # Expose the generic input-only callback expected by the dynamic training loop.
    previous=base.OUT;base.OUT=OUT # Scope the shared solver output path to this explicit physical-family call.
    try: return base.prepare_candidate(descriptor) # Preserve all node/IP entities, imposed histories, and known initial state.
    finally: base.OUT=previous # Restore the original girder output path even after a failed candidate preparation.
def solve_candidate(descriptor): # Expose actual finite-element acquisition with immutable native receipts.
    previous=base.OUT;base.OUT=OUT # Scope native result paths to this explicit physical-family call.
    try: return base.solve_candidate(descriptor) # Reuse exact full-order thermal and plastic state calculations.
    finally: base.OUT=previous # Prevent this callback from contaminating other research-family paths.
def publish(rows): # Atomically expose complete accepted and quarantined coupon records.
    path=OUT/'index.json';old=json.loads(path.read_text())['cases'] if path.exists() else [];merged={r['id']:r for r in old+rows};release_path=OUT/'refinement_release.json';released=release_path.exists() and json.loads(release_path.read_text()).get('status')=='PASS' # Require an independently reviewable actual mesh/time release before admitting any training history.
    for row in merged.values(): row['learning_eligible']=released and row['quality']=='VALID_CONVERGED' and row['split']!='verification' # Keep a native converged calculation distinct from a qualified training reference.
    base.write_json(path,{'cases':list(merged.values()),'candidates':[d for d in descriptors() if d['split']=='candidate'],'solver_callback':'complex_thermoplastic_coupon.solve_candidate','prepare_callback':'complex_thermoplastic_coupon.prepare_candidate','physical_model':'full3Dfinite-radiusnotchedconnector','response_reduction':'NONE','learning_eligible':released,'physical_release':'PASS' if released else 'HOLD_REFINEMENT'}) # Keep old completed outcomes and immutable split membership behind the explicit physical release gate.
def main(): # Run the declared geometry, validation, data, or acquisition action.
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['mesh','pilot','initial','prepare','solve','refine']);parser.add_argument('--id',default='tc_000');parser.add_argument('--workers',type=int,default=2);args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True) # Make every action reviewable from its command line.
    if args.action=='mesh': # Generate independent real discretizations before comparing their results.
        for factor in [1.,.7,.5]: print(generate_mesh(factor),flush=True) # Preserve all nodes at each refinement level.
        return # Do not launch unrequested finite-element calculations.
    tasks=descriptors();base.write_json(OUT/'plan.json',{'cases':[d for d in tasks if d['split']!='candidate'],'candidates':[d for d in tasks if d['split']=='candidate'],'gates':{'full_mechanical_residual':1.e-4,'Fourier_flux_relative':5.e-4,'thermal_global_bound_relative':.0005},'physics':'One-way actual transientconduction totemperature-dependentfinite-strainJ2plasticity; all13nativeinternalvariables; no creep/plasticheating/radiation feedback.','response_reduction':'NONE'}) # Freeze model and data contract before observing any field.
    if args.action=='prepare': # Prepare candidate inputs without calculating or exposing their future reference fields.
        rows=[prepare_candidate(d) for d in tasks if d['split']=='candidate'];base.write_json(OUT/'candidate_inputs.json',{'cases':rows});return # Keep all expensive future labels unavailable to acquisition.
    selected=tasks[:1] if args.action=='pilot' else ([d for d in tasks if d['id']==args.id] if args.action=='solve' else [d for d in tasks if d['split']!='candidate']) # Select only explicitly requested full physical histories.
    if args.action=='refine': # Refine the identical continuous physical path in time and space.
        selected=[] # Exclude refinement labels from all fitting partitions.
        for suffix,extra in [('time2',{'coupling_refinement':2}),('mesh07',{'mesh':str(OUT/'meshes/notched_0.7.npz')}),('mesh05',{'mesh':str(OUT/'meshes/notched_0.5.npz')})]: # Preserve coarse and fine actual evidence.
            d=dict(tasks[0]);d.update(extra);d['id']='tc_verify_'+suffix;d['split']='verification';selected.append(d) # Retain the same underlying physical parameter group.
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool: # Bound independent native full-order jobs.
        futures=[pool.submit(solve_candidate,d) for d in selected] # Launch each immutable history exactly once.
        for future in concurrent.futures.as_completed(futures): publish([future.result()]) # Make only completed result records visible to consumers.
if __name__=='__main__': main() # Execute only the selected real finite-element action.
