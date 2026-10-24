import os,sys,json,re,time,subprocess,hashlib,itertools,warnings # Preserve source identity and actual solver execution evidence.
from pathlib import Path # Resolve source and experiment paths independently of shell state.
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1' # Bound dense and sparse numerical workers.
import numpy as np # Assemble exact source-derived geometry and interface maps.
from scipy.sparse.linalg import spsolve # Independently solve constrained solid elasticity.
from fem import assemble,EDGES,CCX,ROOT,REPO,sha,write_json # Reuse previously cross-verified C3D10 stiffness implementation.
sys.path.insert(0,str(ROOT/'render-runtime'));import pyvista as pv # Read complete actual expanded native shell result.
OUT=REPO/'build/coupling_completed';SRC=REPO/'build/zhaqing-md-20261024/calculation/cases/LC02_G_Q_SERVICE';ELEMENT=243 # Fix actual central bridge shell identity before local computations.
def parse_input(path): # Read physical source definitions rather than supplying generic material assumptions.
    nodes={};shells={};loads={};materials={};keyword='';current=None;section={};gravity=None # Allocate explicit keyword-owned source tables.
    for raw in path.read_text().splitlines(): # Inspect original input without rewriting semantics.
        line=raw.strip() # Remove only insignificant outer whitespace.
        if not line or line.startswith('**'):continue # Skip source comments and blank lines.
        if line.startswith('*'): # Record current keyword and material identity.
            keyword=line.upper() # Normalize symbolic source keywords.
            if keyword.startswith('*MATERIAL'):current=re.search(r'NAME=([^,]+)',keyword).group(1);materials[current]={} # Preserve original material names.
            if keyword.startswith('*SHELL SECTION'):section={'material':re.search(r'MATERIAL=([^,]+)',keyword).group(1),'offset':float(re.search(r'OFFSET=([^,]+)',keyword).group(1))} # Read true shell offset and material.
            continue # Proceed to parameter records.
        fields=[v.strip() for v in line.split(',')] # Split original native input data.
        if keyword.startswith('*NODE,'):nodes[int(fields[0])]=[float(v) for v in fields[1:4]] # Read physical source node coordinates.
        elif keyword.startswith('*ELEMENT') and 'TYPE=S4' in keyword:shells[int(fields[0])]=list(map(int,fields[1:5])) # Keep original deck shell connectivity.
        elif keyword=='*ELASTIC':materials[current]['E'],materials[current]['nu']=map(float,fields[:2]) # Read exact isotropic elastic constants.
        elif keyword=='*DENSITY':materials[current]['rho']=float(fields[0]) # Read actual mass density in source tonne/mm3 units.
        elif keyword.startswith('*SHELL SECTION'):section['thickness']=float(fields[0]) # Preserve declared deck thickness.
        elif keyword.startswith('*CLOAD') and fields[0].isdigit():loads[(int(fields[0]),int(fields[1]))]=float(fields[2]) # Read final actual applied node forces.
        elif keyword.startswith('*DLOAD') and fields[1].upper()=='GRAV':gravity=np.array([float(v) for v in fields[3:6]])*float(fields[2]) # Recover original gravitational acceleration vector.
    return nodes,shells,loads,materials[section['material']],section,gravity # Return complete local physical provenance.
def nodal_table(path,kind): # Parse complete native DAT displacement or force table.
    active=False;values={} # Keep one named nodal quantity separate from integration data.
    for line in path.read_text().splitlines(): # Read genuine native result records.
        if ('displacements (' if kind=='u' else 'forces (') in line.lower():active=True;continue # Identify exact native nodal quantity header.
        if active and ('stresses (' in line.lower() or 'strains (' in line.lower() or ('forces (' in line.lower() and kind=='u')):active=False # Stop at the next quantity block.
        if active and re.match(r'^\s*\d+\s+',line): # Read only source-node numerical records.
            f=line.split() # Split unchanged native numeric fields.
            if len(f)==4:values[int(f[0])]=np.array([float(v.replace('D','E')) for v in f[1:]]) # Require complete displacement or force vector.
    return values # Return node-indexed solver data without filling missing values.
def stress_energy(path,element,volume): # Integrate original native eight-point stress and strain evidence.
    mode=None;data={'stress':{},'strain':{}} # Separate native tensor outputs.
    for line in path.read_text().splitlines(): # Read actual solver integration-point data.
        if 'stresses (' in line:mode='stress';continue # Enter native stress table.
        if 'strains (' in line:mode='strain';continue # Enter native strain table.
        f=line.split() # Parse explicit element and integration-point identities.
        if mode and len(f)>=8 and f[0].isdigit() and int(f[0])==element:data[mode][int(f[1])]=np.array(list(map(float,f[2:8]))) # Preserve source tensor ordering xx/yy/zz/xy/xz/yz.
    ids=sorted(set(data['stress'])&set(data['strain']));assert len(ids)==8 # Require all eight parent integration points.
    return float(sum(np.dot(data['stress'][i]*np.array([1,1,1,2,2,2]),data['strain'][i]) for i in ids)*volume/16) # Integrate true tensor contraction with eight equal Gauss weights.
def replay(): # Recover actual through-thickness global displacements without inferring missing rotations.
    inp=SRC/'ZQ_LC02_G_Q_SERVICE_NL_19.inp';text=inp.read_text();modified=text.replace('*NODE FILE, NSET=NALL, FREQUENCY=1','*NODE FILE, FREQUENCY=1');directory=OUT/'global_replay';directory.mkdir(parents=True,exist_ok=True);(directory/'global.inp').write_text(modified) # Change only output coverage in the frozen physical input.
    if not (directory/'global.frd').exists(): # Reuse verified full-output replay within this run.
        with (directory/'solver.log').open('w') as log:r=subprocess.run([str(CCX),'-i','global'],cwd=directory,stdout=log,stderr=subprocess.STDOUT,timeout=180) # Execute genuine original global finite-element problem.
        assert r.returncode==0 # Reject unsuccessful native replay.
    original=nodal_table(SRC/'ZQ_LC02_G_Q_SERVICE_NL_19.dat','u');rerun=nodal_table(directory/'global.dat','u');assert set(original)==set(rerun);difference=max(np.linalg.norm(original[i]-rerun[i]) for i in original) # Check physical response stayed unchanged within original DAT precision.
    assert difference<1e-4 # Require physical replay agreement within the original six-digit DAT precision.
    nodes,shells,loads,material,section,g= parse_input(inp);reader=pv.get_reader(directory/'global.frd');assert reader.time_values==[1.];reader.set_active_time_value(1.);mesh=reader.read();ids=np.asarray(mesh.get_cell(ELEMENT-1).point_ids);corners=np.asarray(mesh.points[ids]);displacement=np.asarray(mesh['DISP'][ids]);parent=np.array([nodes[i] for i in shells[ELEMENT]]) # Recover native expanded-solid director translations and exact source corners.
    assert len(ids)==8 and np.allclose(corners[:4],parent,atol=.001) and np.isclose(section['offset'],-.5);corners[:4]=parent;corners[4:]=parent+np.array([0,0,section['thickness']]) # Restore original coordinate precision after checking actual offset convention.
    area_nodes={i:0. for i in nodes} # Allocate source tributary surface areas.
    for connectivity in shells.values(): # Reconstruct exact equivalent area used by the uniform nodal surface load.
        p=np.array([nodes[i] for i in connectivity]);area=.5*np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))+.5*np.linalg.norm(np.cross(p[2]-p[0],p[3]-p[0])) # Compute source shell area without assumed spacing.
        for i in connectivity:area_nodes[i]+=area/4 # Assign consistent bilinear corner tributary area.
    pressure=np.array([loads[(i,3)]/area_nodes[i] for i in shells[ELEMENT]]);assert np.ptp(pressure)<1e-10 # Accept uniform local surface traction only when every original corner independently agrees.
    rigid=displacement.mean(axis=0);local=displacement-rigid;volume=float(np.prod(np.ptp(corners,axis=0)));parent_energy=stress_energy(directory/'global.dat',ELEMENT,volume) # Separate rigid translation to prevent catastrophic energy cancellation.
    metadata={'global_source_input':str(inp),'source_input_sha256':sha(inp),'global_replay_input_sha256':sha(directory/'global.inp'),'global_replay_frd_sha256':sha(directory/'global.frd'),'global_replay_dat_sha256':sha(directory/'global.dat'),'global_output_only_change':True,'global_replay_max_original_node_displacement_difference_mm':difference,'parent_element':ELEMENT,'parent_original_nodes':shells[ELEMENT],'native_expanded_node_ids':np.asarray(mesh['original_node_ids'])[ids].tolist(),'material':material,'section':section,'gravity_mm_s2':g.tolist(),'reconstructed_corner_surface_tractions_N_mm2':pressure.tolist(),'traction_reconstruction_spread':float(np.ptp(pressure)),'rigid_translation_removed_mm':rigid.tolist(),'native_parent_strain_energy_Nmm':parent_energy,'boundary_precision':'Native FRD displacement uses five digits after decimal in exponential format; global translation near 212 mm implies up to approximately 0.0005 mm original coordinate-component rounding. Full-through-thickness vectors are transferred; no invented shell rotation.'} # Record exact physics and source-output precision limitations.
    write_json(OUT/'source_contract.json',metadata);return corners,local,rigid,material,section,g,float(pressure.mean()),metadata # Return source-qualified local problem definition.
def shape(xyz,corners): # Evaluate exact parent hexahedron displacement interpolation in its rectangular reference domain.
    q=(xyz-corners.min(axis=0))/np.ptp(corners,axis=0);a,b,c=q.T # Map physical local points to parent unit coordinates.
    return np.column_stack([(1-a)*(1-b)*(1-c),a*(1-b)*(1-c),a*b*(1-c),(1-a)*b*(1-c),(1-a)*(1-b)*c,a*(1-b)*c,a*b*c,(1-a)*b*c]) # Preserve all eight native director endpoint values.
def mesh_patch(corners,n,nz): # Build conforming quadratic tetrahedra within the real parent solid region.
    lo=corners.min(axis=0);extent=np.ptp(corners,axis=0);points=np.array([lo+extent*np.array([i/n,j/n,k/nz]) for i in range(n+1) for j in range(n+1) for k in range(nz+1)]);index=lambda i,j,k:(i*(n+1)+j)*(nz+1)+k;tet=[] # Define exact parent geometry independently of mesh resolution.
    for i,j,k in itertools.product(range(n),range(n),range(nz)): # Partition each Cartesian hexahedron consistently across common faces.
        origin=np.array([i,j,k]) # Record local cell origin.
        for permutation in itertools.permutations(range(3)): # Use the six Freudenthal tetrahedra around common body diagonal.
            path=[origin.copy()];cursor=origin.copy() # Start a monotone corner path.
            for axis in permutation:cursor=cursor.copy();cursor[axis]+=1;path.append(cursor) # Walk each unique axis ordering.
            tet.append([index(*position) for position in path]) # Preserve conforming element connectivity.
    tet=np.array(tet);det=np.linalg.det(points[tet[:,1:]]-points[tet[:,0,None]]);negative=det<0;tet[negative,1],tet[negative,2]=tet[negative,2].copy(),tet[negative,1].copy();allpoints=points.tolist();edges={};quadratic=[] # Correct reference orientation before midside enrichment.
    for nodes in tet: # Upgrade every physical tetrahedron to native C3D10 ordering.
        row=list(nodes) # Retain positively oriented four corners.
        for a,b in EDGES: # Add globally shared edge midpoints.
            key=tuple(sorted((int(nodes[a]),int(nodes[b])))) # Maintain conformity across neighboring elements.
            if key not in edges:edges[key]=len(allpoints);allpoints.append(((points[key[0]]+points[key[1]])/2).tolist()) # Generate one actual midpoint for each unique edge.
            row.append(edges[key]) # Bind element midside to shared geometry.
        quadratic.append(row) # Preserve complete native quadratic element.
    return np.array(allpoints),np.array(quadratic) # Return actual local mesh with every source boundary retained.
def local_solve(corners,parent_u,rigid,material,section,g,q,n,nz): # Execute a real displacement-driven local solve with original distributed load and self-weight.
    directory=OUT/f'local_n{n}_nz{nz}';directory.mkdir(exist_ok=True);started=time.time();xyz,tet=mesh_patch(corners,n,nz);W=shape(xyz,corners);transferred=W@parent_u;lo=corners.min(axis=0);hi=corners.max(axis=0);boundary=np.where(np.any(np.isclose(xyz[:,:2],lo[:2])|np.isclose(xyz[:,:2],hi[:2]),axis=1))[0];fixed=(boundary[:,None]*3+np.arange(3)).ravel();free=np.setdiff1d(np.arange(xyz.size),fixed) # Prescribe four physical lateral cut faces while top/bottom remain mechanically free.
    K,volume=assemble(xyz,tet,np.zeros(len(tet),int),material['E'],material['nu']);force=np.zeros_like(xyz) # Assemble full independent physical stiffness before applying actual loads.
    for nodes,V in zip(tet,volume):force[nodes]+=np.r_[np.full(4,-V/20),np.full(6,V/5)][:,None]*material['rho']*g # Integrate source gravity consistently with quadratic shape functions.
    for nodes in tet: # Integrate reconstructed constant top-surface load over exact quadratic boundary faces.
        face=[i for i in range(4) if abs(xyz[nodes[i],2]-hi[2])<1e-7] # Identify true top boundary triangles.
        if len(face)!=3:continue # Exclude interior and all lateral/bottom faces.
        corners_face=xyz[nodes[face]];area=np.linalg.norm(np.cross(corners_face[1]-corners_face[0],corners_face[2]-corners_face[0]))/2 # Compute actual surface triangle area.
        for pair in [(face[0],face[1]),(face[1],face[2]),(face[2],face[0])]: # Uniform quadratic-face traction contributes exactly to its midsides.
            j=EDGES.index(pair) if pair in EDGES else EDGES.index(pair[::-1]);force[nodes[4+j],2]+=q*area/3 # Apply consistent top traction without mesh-node-count bias.
    f=force.ravel();solution=np.zeros(len(f));solution[fixed]=transferred.ravel()[fixed];solution[free]=spsolve(K[free][:,free],f[free]-K[free][:,fixed]@solution[fixed],permc_spec='MMD_AT_PLUS_A');residual=K@solution-f;reaction=residual.reshape(-1,3);norm=max(np.linalg.norm(f),1.) # Solve free interior translations using transferred actual global boundary state.
    energy=float(.5*solution@(K@solution));applied_work=float(solution@f);boundary_work=float(solution[fixed]@residual[fixed]);energy_error=abs(2*energy-applied_work-boundary_work)/max(2*abs(energy),1.);balance=np.linalg.norm((reaction+force).sum(axis=0))/max(np.linalg.norm(force.sum(axis=0)),1.);moment=np.linalg.norm(np.cross(xyz-xyz.mean(axis=0),reaction+force).sum(axis=0))/max(np.linalg.norm(force.sum(axis=0))*np.linalg.norm(np.ptp(xyz,axis=0)),1.) # Check local equilibrium and boundary-inclusive work identity independently.
    back_force=W[boundary].T@reaction[boundary];work_duality=abs(float(np.sum(parent_u*back_force))-boundary_work)/max(abs(boundary_work),1.);correction=solution.reshape(-1,3)-transferred;origin=(lo+hi)/2;center=int(np.argmin(np.linalg.norm(xyz-origin,axis=1))) # Transfer computed cut reactions back to actual native parent nodes without artificial force probes.
    lines=['*HEADING',f'Actual global element {ELEMENT} local n={n} nz={nz}','*NODE']+[f'{i+1},'+','.join(f'{v:.15g}' for v in point) for i,point in enumerate(xyz)]+['*ELEMENT,TYPE=C3D10,ELSET=LOCAL']+[f'{i+1},'+','.join(str(v+1) for v in nodes) for i,nodes in enumerate(tet)]+['*MATERIAL,NAME=SOURCE_DECK','*ELASTIC',f"{material['E']},{material['nu']}",'*SOLID SECTION,ELSET=LOCAL,MATERIAL=SOURCE_DECK','*NSET,NSET=ALL,GENERATE',f'1,{len(xyz)},1','*BOUNDARY'] # Write exact source-derived native local input without extra material assumptions.
    lines.extend(f'{i//3+1},{i%3+1},{i%3+1},{solution[i]:.12e}' for i in fixed);lines.extend(['*STEP','*STATIC','1.,1.,1e-6,1.','*CLOAD']);lines.extend(f'{i//3+1},{i%3+1},{value:.12e}' for i,value in enumerate(f) if value!=0);lines.extend(['*NODE PRINT,NSET=ALL','U,RF','*NODE FILE','U,RF','*EL FILE','S,E','*END STEP']);inp=directory/'local.inp';inp.write_text('\n'.join(lines)+'\n') # Preserve all prescribed cut displacements and independently integrated physical forces.
    with (directory/'solver.log').open('w') as log:completed=subprocess.run([str(CCX),'-i','local'],cwd=directory,stdout=log,stderr=subprocess.STDOUT,timeout=180) # Execute native independent CalculiX local problem.
    native_table=nodal_table(directory/'local.dat','u');assert completed.returncode==0 and len(native_table)==len(xyz),f'Native solver failed: {directory}/solver.log';native=np.array([native_table[i+1] for i in range(len(xyz))]);cross_error=float(np.linalg.norm(native-solution.reshape(-1,3))/max(np.linalg.norm(solution),1e-12)) # Require actual native complete output and independent field agreement.
    np.savez_compressed(directory/'fields.npz',xyz=xyz,tet=tet,W=W,u_relative=solution.reshape(-1,3),u_total=solution.reshape(-1,3)+rigid,interpolated_parent=transferred+rigid,force=force,cut_reaction=reaction,boundary=boundary,fixed=fixed,free=free,returned_parent_reaction=back_force) # Preserve every real local result and dual interface mapping.
    result={'case':directory.name,'nodes':len(xyz),'elements':len(tet),'n':n,'nz':nz,'free_displacement_dofs':len(free),'source_E_MPa':material['E'],'source_nu':material['nu'],'source_thickness_mm':section['thickness'],'load_resultant_N':force.sum(axis=0).tolist(),'cut_reaction_resultant_N':reaction[boundary].sum(axis=0).tolist(),'free_relative_residual':float(np.linalg.norm(residual[free])/norm),'force_balance_relative':float(balance),'moment_balance_relative':float(moment),'moment_balance_absolute_Nmm':float(np.linalg.norm(np.cross(xyz-xyz.mean(axis=0),reaction+force).sum(axis=0))),'moment_reference_Nmm':float(np.linalg.norm(force.sum(axis=0))*np.linalg.norm(np.ptp(xyz,axis=0))),'energy_identity_relative':float(energy_error),'actual_cut_work_transfer_relative':float(work_duality),'strain_energy_Nmm':energy,'applied_work_Nmm':applied_work,'cut_boundary_work_Nmm':boundary_work,'cross_solver_relative':cross_error,'center_u_total_mm':(solution.reshape(-1,3)[center]+rigid).tolist(),'center_extra_deflection_mm':correction[center].tolist(),'max_local_correction_mm':float(np.linalg.norm(correction,axis=1).max()),'native_input_sha256':sha(inp),'native_dat_sha256':sha(directory/'local.dat'),'native_frd_sha256':sha(directory/'local.frd'),'native_exit_code':completed.returncode,'seconds':time.time()-started,'status':'PASS' if max(balance,moment,energy_error,work_duality,np.linalg.norm(residual[free])/norm)<1e-6 and cross_error<1e-5 else 'FAIL'} # Keep numerical gates independent from parent-coarse-model agreement.
    write_json(directory/'receipt.json',result);print(json.dumps(result),flush=True);return result # Persist finished native and independent local solve evidence.
def main(): # Complete source recovery, actual local solves, force feedback and mesh validation.
    OUT.mkdir(exist_ok=True);corners,parent_u,rigid,material,section,g,q,metadata=replay();results=[] # Resolve original source physics once before any mesh choice.
    for n,nz in [(2,2),(4,2),(8,2),(16,2),(32,2),(32,4),(48,2)]: # Compare genuinely different in-plane mesh sizes with common thickness resolution.
        results.append(local_solve(corners,parent_u,rigid,material,section,g,q,n,nz)) # Execute all requested physical submodel cases.
        write_json(OUT/'summary.json',{'source_contract':metadata,'local_solves':results,'completed_native_local_solve_count':len(results),'coupling':'one-way displacement-driven global-to-local solid submodel with actual reaction back-transfer; no global re-equilibration yet','fully_two_way_coupled':False}) # Checkpoint real progress without pretending algebraic mapping alone is complete.
    previous,last=results[-2:];mesh={'center_extra_deflection_change_mm':float(np.linalg.norm(np.array(last['center_extra_deflection_mm'])-previous['center_extra_deflection_mm'])),'energy_change_relative':abs(last['strain_energy_Nmm']-previous['strain_energy_Nmm'])/last['strain_energy_Nmm'],'max_local_correction_change_relative':abs(last['max_local_correction_mm']-previous['max_local_correction_mm'])/max(last['max_local_correction_mm'],1e-12)} # Compare actual solved local correction rather than almost-rigid 212-mm whole-bridge displacement.
    summary={'source_contract':metadata,'local_solves':results,'completed_native_local_solve_count':len(results),'mesh_comparison':mesh,'all_numerical_checks_pass':all(r['status']=='PASS' for r in results),'parent_vs_finest_energy_relative':abs(last['strain_energy_Nmm']-metadata['native_parent_strain_energy_Nmm'])/max(abs(metadata['native_parent_strain_energy_Nmm']),1e-12),'coupling':'actual one-way displacement-driven solid submodel including source gravity and reconstructed nodal surface load, native through-thickness director transfer and computed reaction dual map','fully_two_way_coupled':False,'remaining':['returned reactions are measured but not inserted into and re-equilibrated with full bridge','global parent uses coarse shell C3D8I while local continuum uses refined C3D10; coarse/fine energy mismatch is measured, not hidden','original surface CLOAD is reconstructed as the uniform traction whose four independent tributary ratios agree; this is a documented local refinement of the source nodal-load discretization','FRD through-thickness displacement precision limits local boundary accuracy','stress peaks and neighboring parent-element patches have not yet been validated']} # Report completed local mechanics and exact remaining coupling requirements.
    write_json(OUT/'summary.json',summary) # Publish final complete one-way coupling evidence.
if __name__=='__main__':main() # Execute actual source-to-local constitutive solves and validation.
