import os, sys, json, time, hashlib, subprocess, re # Preserve solver inputs, runtime and provenance.
from pathlib import Path # Resolve repository-relative resources.
import numpy as np # Assemble physical coordinates and finite elements.
from scipy.sparse import coo_matrix, save_npz # Store full physical stiffness operators.
from scipy.sparse.linalg import spsolve # Solve independently assembled constrained systems.
REPO = Path(__file__).resolve().parents[2]; ROOT = Path(os.environ.get('LOCAL_BRIDGE_RUNTIME_ROOT',str(REPO.parent))) # Resolve checkout independently from optional external runtime root.
sys.path.insert(0, str(ROOT / 'local-fem-runtime')) # Load explicitly pinned geometry dependency.
FAMILIES = ['girder','splice','crossframe','diaphragm','stiffener','deck','concrete','bearing'] # Define eight distinct structural topologies.
RUN = REPO / 'build/local-bridge-20261024'; CCX = Path(os.environ.get('CCX_EXECUTABLE',str(ROOT/'solver-runtime/ccx-precision-v2'))) # Keep evidence in this checkout and allow an explicit native solver executable.
EDGES = [(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)] # Use CalculiX C3D10 midside ordering.
def write_json(path, value): # Persist finite machine-readable evidence.
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) # Reject invalid numeric records.
def sha(path): # Freeze original file identity.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() # Hash exact bytes.
def mesh_family(name, size=1.0): # Construct explicit local solid geometry and conforming quadratic tetrahedra.
    if name not in FAMILIES or size<=0: raise ValueError('Unknown structural family or nonpositive mesh-size factor') # Reject unsupported topology rather than silently constructing a bearing.
    import gmsh # Use pinned OpenCASCADE geometry and tetrahedral meshing.
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal',0); gmsh.model.add(name) # Start an isolated deterministic geometry model.
    occ = gmsh.model.occ; parts = []; E = 200000.; nu = .3; source = ''; assumptions = [] # Initialize physical and provenance metadata.
    def box(x,y,z,dx,dy,dz): # Add one exact prismatic structural component.
        tag=occ.addBox(x,y,z,dx,dy,dz); parts.append((3,tag)); return tag # Register solid component for Boolean union.
    if name in ['girder','stiffener','concrete']: # Generate explicit I-section solids.
        L,H,B,tw,tf = (2400.,1676.4,558.8,19.05,25.4) if name!='concrete' else (2400.,1200.,600.,180.,160.) # Read steel dimensions where available and declare concrete research dimensions.
        box(0,-B/2,0,L,B,tf); box(0,-tw/2,tf,L,tw,H-2*tf); box(0,-B/2,H-tf,L,B,tf) # Construct flange/web/flange without beam substitution.
        if name=='stiffener': box(L/2-9.525,-B/2,tf,19.05,B,H-2*tf) # Add full transverse stiffener with conforming solid interfaces.
        E=35000. if name=='concrete' else E; nu=.2 if name=='concrete' else nu # Declare uncracked concrete elastic law separately.
        source='WSDOT 6.4_A2/A3; Caltrans xs1-410-2' if name!='concrete' else 'WSDOT 5.6_A4_1–5 (topology only)' # Link geometry lineage without inventing dimensions.
        assumptions=['Research segment length 2400 mm; fixed cut face; no global bridge boundary transfer','Steel web 19.05 mm and both flanges 25.4 mm selected research section; see parameter ledger','Concrete section dimensions and elastic modulus are research assumptions; reinforcement, prestress and cracking are NOT represented'] if name=='concrete' else ['Research segment length 2400 mm; fixed cut face; no global bridge boundary transfer','Flange width 22 in and thickness 1 in follow one source segment; web thickness 19.05 mm chosen explicitly','Perfectly bonded plate intersections; no weld-toe radius or plasticity'] # Declare fidelity honestly.
        h=420.*size # Set mesh resolution independently of geometry.
    elif name=='splice': # Model a finite web-splice coupon including explicit bolt solids.
        L,H,t,gap=609.6,228.6,12.7,6.35 # Adopt source pitch/thickness/gap for a declared reduced coupon.
        box(0,0,0,(L-gap)/2,H,t); box((L+gap)/2,0,0,(L-gap)/2,H,t) # Preserve the actual central plate gap.
        box(76.2,0,-t,L-152.4,H,t); box(76.2,0,t,L-152.4,H,t) # Add both cover plates outside main web.
        bolt_centers=[(x,y) for x in [152.4,228.6,381.,457.2] for y in [38.1,114.3,190.5]] # Use explicit 3-in pitch and 1.5-in edge distance.
        holes=[(3,occ.addCylinder(x,y,-t,0,0,3*t,11.1)) for x,y in bolt_centers] # Cut geometric bolt holes through assembled plate stack.
        cut,_=occ.cut(parts,holes); parts=list(cut) # Retain plate solids after hole removal.
        for x,y in bolt_centers: parts.append((3,occ.addCylinder(x,y,-t,0,0,3*t,11.1))) # Fill holes with explicit snug-fit bonded bolt solids.
        source='WSDOT 6.4_A4'; assumptions=['Reduced 12-bolt research coupon, not the complete source field splice','Pitch 76.2 mm, gap 6.35 mm, plate thickness 12.7 mm follow source details','Bolt diameter 22.2 mm assumed; bolt-hole interfaces bonded, no preload, clearance, slip, friction or yielding']; h=75.*size # State exact connection idealization.
    elif name=='crossframe': # Build solid horizontal members and diagonal crossing members.
        L,H,w,t=1800.,1200.,120.,19.05 # Declare missing project dimensions rather than claiming source WT section equivalence.
        box(0,-t/2,0,L,t,w); box(0,-t/2,H-w,L,t,w) # Add solid upper and lower chords.
        for z0,z1 in [(w/2,H-w/2),(H-w/2,w/2)]: # Build two inclined flat members as solid extrusions.
            p=[occ.addPoint(*v) for v in [(0,-t/2,z0-w/2),(L,-t/2,z1-w/2),(L,-t/2,z1+w/2),(0,-t/2,z0+w/2)]] # Define exact diagonal polygon vertices.
            lines=[occ.addLine(p[i],p[(i+1)%4]) for i in range(4)]; surface=occ.addPlaneSurface([occ.addCurveLoop(lines)]) # Close each diagonal planar profile.
            parts.extend(entity for entity in occ.extrude([(2,surface)],0,t,0) if entity[0]==3) # Extrude finite member thickness.
        source='WSDOT 6.4_A5 (arrangement only)'; assumptions=['Research flat-member crossframe; source WT sections and gusset details not reconstructed','Perfectly bonded crossing and chord connections; fixed left cut faces; no seismic/fatigue assessment']; h=300.*size # Mark section simplification as an explicit model version.
    elif name=='diaphragm': # Form a plate with the source-size rounded inspection opening.
        L,H,t=2400.,1800.,19.05; box(0,0,0,L,H,t) # Choose explicit outer plate research dimensions.
        r=381.; cy=H/2; cx=L/2; straight=304.8 # Reproduce 30-by-42-inch capsule opening.
        void=[(3,occ.addBox(cx-r,cy-straight/2,-1,2*r,straight,t+2))] # Define middle straight opening section.
        void.extend((3,occ.addCylinder(cx,y,-1,0,0,t+2,r)) for y in [cy-straight/2,cy+straight/2]) # Add round upper and lower ends.
        united,_=occ.fuse(void[:1],void[1:]); parts,_=occ.cut(parts,united) # Cut continuous capsule opening from diaphragm plate.
        source='WSDOT 6.4_A12/A14'; assumptions=['Opening 762 by 1066.8 mm source-derived; outer dimensions and thickness are research assumptions','Fixed left cut edge and applied in-plane shear on right edge; no enclosing box or weld ring']; h=300.*size # Record independent local boundary problem.
    elif name=='deck': # Construct actual steel deck plate and two closed trapezoidal ribs.
        L,W,td,tr,depth,bottom=2400.,1219.2,15.875,9.525,266.7,165.1 # Use FHWA closed-rib option 1 dimensions and explicit shorter segment length.
        box(0,0,0,L,W,td); offset=depth/np.tan(np.deg2rad(72.)) # Obtain rib side offset from the specified 72-degree angle.
        for c in [W/4,3*W/4]: # Place two ribs with 609.6-mm spacing.
            polygon=[(c-bottom/2,-depth),(c+bottom/2,-depth),(c+bottom/2+offset,0),(c+bottom/2+offset-tr,0),(c+bottom/2-tr,-depth+tr),(c-bottom/2+tr,-depth+tr),(c-bottom/2-offset+tr,0),(c-bottom/2-offset,0)] # Define finite rib wall thickness with shared top contact.
            p=[occ.addPoint(0,y,z) for y,z in polygon]; lines=[occ.addLine(p[i],p[(i+1)%8]) for i in range(8)] # Create exact rib profile wire.
            surf=occ.addPlaneSurface([occ.addCurveLoop(lines)]); parts.extend(e for e in occ.extrude([(2,surf)],L,0,0) if e[0]==3) # Extrude continuous ribs along the deck.
        source='FHWA-HIF-22-056 printed page 8, Figures 3–4'; assumptions=['Two-rib research segment; source option-1 plate/rib dimensions; segment length assumed','Rib bends sharp rather than 31.75-mm corner radii; welds perfectly bonded; no wearing surface or floorbeam','Fixed left cut face and downward Gaussian right-face loading; not a wheel patch on a full bridge']; h=300.*size # State supported local response interpretation.
    else: # Build a laminated bearing research specimen with resolved steel layers.
        L,W,H=300.,250.,80.; levels=[0.,6.35,25.4,26.919,45.969,47.488,73.65,80.] # Use explicitly enumerated elastomer and 14-gauge shim elevations.
        for z0,z1 in zip(levels[:-1],levels[1:]): box(0,0,z0,L,W,z1-z0) # Preserve separate layer volume tags for heterogeneous materials.
        E=3.35; nu=.47; source='WSDOT 5.6_A4_12'; assumptions=['Plan size and total height assumed; shim thickness 1.519 mm; source rubber shear modulus 165 psi gives approximately 1.138 MPa','Research linear rubber E=3.35 MPa and nu=0.47; no calibrated hyperelasticity, incompressibility or contact','Layer interfaces perfectly bonded; base clamped and top compression/shear applied']; h=85.*size # Declare independent bearing constitutive approximation.
    if name=='bearing': merged,_=occ.fragment(parts[:1],parts[1:]) # Conform interfaces without deleting material separation.
    else: merged,_=occ.fuse(parts[:1],parts[1:]) if len(parts)>1 else (parts,None) # Form connected physical solid without duplicate overlapping stiffness.
    occ.synchronize(); gmsh.option.setNumber('Mesh.MeshSizeMin',h*.65); gmsh.option.setNumber('Mesh.MeshSizeMax',h) # Bound mesh edge sizes for reproducibility.
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',10); gmsh.option.setNumber('General.NumThreads',1); gmsh.option.setNumber('Mesh.RandomSeed',42) # Keep thin curved geometry resolution deterministic.
    gmsh.model.mesh.generate(3) # Mesh explicit solid volumes with linear tetrahedra.
    tags,coords,_=gmsh.model.mesh.getNodes(); lookup={int(v):i for i,v in enumerate(tags)}; xyz=coords.reshape(-1,3) # Preserve geometric node identity.
    all_tets=[]; groups=[] # Collect material/component labels on actual elements.
    for dim,tag in gmsh.model.getEntities(3): # Visit every connected material volume.
        types,etags,conns=gmsh.model.mesh.getElements(3,tag) # Read tetrahedral volume connectivity.
        for typ,conn in zip(types,conns): # Require supported linear base tetrahedra.
            assert typ==4, 'Unsupported base element'; arr=np.array([lookup[int(v)] for v in conn]).reshape(-1,4) # Map source node IDs to deterministic dense indices.
            all_tets.extend(arr); center=xyz[arr].mean(axis=1) # Compute true material locations.
            groups.extend(((center[:,2]>25.4)&(center[:,2]<26.919)|(center[:,2]>45.969)&(center[:,2]<47.488)).astype(int) if name=='bearing' else np.zeros(len(arr),dtype=int)) # Mark steel shims independently from rubber.
    gmsh.write(str(RUN/'meshes'/f'{name}_{size:g}.brep')); gmsh.finalize() # Save editable boundary geometry before closing native context.
    tet=np.asarray(all_tets,dtype=int); used=np.unique(tet); remap=np.full(len(xyz),-1); remap[used]=np.arange(len(used)); xyz=xyz[used]; tet=remap[tet] # Remove non-volume bookkeeping nodes.
    volume=np.linalg.det(xyz[tet[:,1:]]-xyz[tet[:,0,None]]) # Check orientation of linear reference tetrahedra.
    neg=volume<0; tet[neg,1],tet[neg,2]=tet[neg,2].copy(),tet[neg,1].copy() # Orient every reference Jacobian positively.
    points=xyz.tolist(); mids={}; quadratic=[] # Upgrade to exact straight-sided quadratic tetrahedra.
    for nodes in tet: # Generate unique shared edge nodes.
        row=list(nodes) # Preserve four positively oriented corners.
        for a,b in EDGES: # Follow C3D10 documented ordering.
            key=tuple(sorted((int(nodes[a]),int(nodes[b])))) # Deduplicate midsides across element interfaces.
            if key not in mids: mids[key]=len(points); points.append(((xyz[key[0]]+xyz[key[1]])/2).tolist()) # Create physical edge midpoint exactly once.
            row.append(mids[key]) # Connect the shared midpoint.
        quadratic.append(row) # Record complete ten-node connectivity.
    meta={'family':name,'source':source,'assumptions':assumptions,'E_MPa':E,'nu':nu,'mesh_size_factor':size,'units':'N-mm-MPa','element':'C3D10','geometry':'straight-sided quadratic tetrahedra; curved boundaries polygonally approximated','node_count':len(points),'element_count':len(quadratic)} # Freeze exact modeling choices and resolution.
    return np.asarray(points),np.asarray(quadratic),np.asarray(groups),meta # Return real solid model and auditable metadata.
def assemble(xyz,tet,groups,E,nu): # Assemble full quadratic tetrahedral linear elasticity stiffness independently of CalculiX.
    a=.5854101966249685; b=.1381966011250105; quadrature=np.full((4,4),b); np.fill_diagonal(quadrature,a) # Integrate quadratic strain energy exactly with four tetrahedral points.
    corners=xyz[tet[:,:4]]; J=np.stack([corners[:,i]-corners[:,0] for i in [1,2,3]],axis=2); det=np.linalg.det(J) # Form affine element Jacobians.
    assert np.all(det>1e-10),'Inverted or degenerate tetrahedron'; inv=np.linalg.inv(J) # Refuse invalid geometry before solving.
    dL=np.einsum('ij,ejk->eik',np.array([[-1,-1,-1],[1,0,0],[0,1,0],[0,0,1.]]),inv) # Compute barycentric gradients in physical coordinates.
    ev=np.where(groups==1,200000.,E); nv=np.where(groups==1,.3,nu); mu=ev/(2*(1+nv)); lam=ev*nv/((1+nv)*(1-2*nv)) # Preserve heterogeneous isotropic material fields.
    D=np.zeros((len(tet),6,6)); D[:,:3,:3]=lam[:,None,None] # Initialize elastic constitutive tensors in engineering-shear convention.
    for i in range(6): D[:,i,i]+=2*mu if i<3 else mu # Set normal and engineering-shear moduli.
    ke=np.zeros((len(tet),30,30)); lastB=None # Allocate element stiffness and final diagnostic gradient.
    for L in quadrature: # Integrate each physical tetrahedral element.
        grad=np.empty((len(tet),10,3)); grad[:,:4]=(4*L-1)[None,:,None]*dL # Differentiate quadratic vertex shape functions.
        for j,(i,k) in enumerate(EDGES): grad[:,4+j]=4*(L[i]*dL[:,k]+L[k]*dL[:,i]) # Differentiate quadratic edge shape functions.
        B=np.zeros((len(tet),6,30)); B[:,0,0::3]=grad[:,:,0]; B[:,1,1::3]=grad[:,:,1]; B[:,2,2::3]=grad[:,:,2] # Build normal strain-displacement rows.
        B[:,3,0::3]=grad[:,:,1]; B[:,3,1::3]=grad[:,:,0]; B[:,4,1::3]=grad[:,:,2]; B[:,4,2::3]=grad[:,:,1]; B[:,5,0::3]=grad[:,:,2]; B[:,5,2::3]=grad[:,:,0] # Build xy/yz/xz engineering-shear rows.
        ke+=np.einsum('eia,eij,ejb->eab',B,D,B,optimize=True)*(det/24)[:,None,None]; lastB=B # Integrate actual stiffness with volume weights.
    dofs=(tet[:,:,None]*3+np.arange(3)).reshape(-1,30); rows=np.repeat(dofs,30,axis=1).ravel(); cols=np.tile(dofs,(1,30)).ravel() # Map element matrices to global degrees of freedom.
    K=coo_matrix((ke.ravel(),(rows,cols)),shape=(3*len(xyz),3*len(xyz))).tocsr(); K.sum_duplicates() # Assemble symmetric global physical operator.
    return K,det/6 # Return exact discrete operator and element volumes.
def make_case(base,params): # Apply explicit geometric/material parameters and physical nodal loads.
    xyz0,tet,groups,meta=base; p=np.asarray(params,dtype=float) # Parse explicit physical parameter vector.
    if p.shape!=(6,) or not np.isfinite(p).all() or np.any(p[:4]<=0) or p[4]<0 or not 0<=p[5]<=1: raise ValueError('Physically infeasible geometry/material/load parameters') # Reject negative dimensions/moduli and malformed cases before numerical assembly.
    scales=np.array([p[0],p[1],p[2]]); xyz=xyz0*scales # Construct a distinct affine geometric instance.
    E=meta['E_MPa']*p[3]; axis=2 if meta['family']=='bearing' else 0; lo=xyz[:,axis].min(); hi=xyz[:,axis].max() # Choose physically declared clamped and loaded faces.
    fixed=np.where(np.isclose(xyz[:,axis],lo,atol=1e-6))[0]; loaded=np.where(np.isclose(xyz[:,axis],hi,atol=1e-6))[0] # Preserve full quadratic boundary-face nodes.
    transverse=0 if axis==2 else 1; y=xyz[loaded,transverse]; ymin=y.min(); width=max(np.ptp(y),1.); weights=np.zeros(len(xyz)) # Allocate consistent quadratic nodal forces for a physical surface traction.
    quadrature=[([1/3,1/3,1/3],.225)] # Start seven-point degree-five triangle integration.
    for aa,bb,ww in [(.05971587178977,.470142064105115,.132394152788506),(.797426985353087,.101286507323456,.125939180544827)]: # Define exact symmetric quadrature rules.
        quadrature.extend(([aa,bb,bb][k:]+[aa,bb,bb][:k],ww) for k in range(3)) # Generate barycentric permutations with equal weights.
    for nodes in tet: # Locate true boundary faces of the quadratic volume mesh.
        local=[i for i in range(4) if abs(xyz[nodes[i],axis]-hi)<1e-6] # Select tetrahedral corners on loaded cut plane.
        if len(local)!=3: continue # Ignore interior and other exterior faces.
        face=[int(nodes[i]) for i in local]; mids=[int(nodes[4+EDGES.index(pair)]) if pair in EDGES else int(nodes[4+EDGES.index(pair[::-1])]) for pair in [(local[0],local[1]),(local[1],local[2]),(local[2],local[0])]] # Map six face nodes to correct solid degrees.
        coords=xyz[face]; area=np.linalg.norm(np.cross(coords[1]-coords[0],coords[2]-coords[0]))/2 # Compute exact planar triangle area.
        for bary,weight in quadrature: # Integrate prescribed smooth traction over actual surface area.
            q=np.asarray(bary); yn=(q@coords[:,transverse]-ymin)/width; density=np.exp(-((yn-p[5])/.35)**2); N=np.r_[q*(2*q-1),4*q[0]*q[1],4*q[1]*q[2],4*q[2]*q[0]] # Evaluate quadratic face interpolation and Gaussian traction.
            weights[face+mids]+=area*weight*density*N # Assemble consistent nodal forces without mesh-density bias.
    weights/=weights.sum() # Normalize traction to the prescribed total force.
    force=np.zeros_like(xyz); magnitude=p[4]*(1000. if meta['family']=='bearing' else 10000.) # Set explicit total load in newtons.
    direction=np.array([.15,0.,-1.]) if meta['family']=='bearing' else (np.array([0.,1.,0.]) if meta['family']=='diaphragm' else np.array([0.,0.,-1.])) # Use declared shear/compression or transverse bending.
    force=weights[:,None]*magnitude*direction; fixed_dof=(fixed[:,None]*3+np.arange(3)).ravel(); free=np.setdiff1d(np.arange(xyz.size),fixed_dof) # Assemble consistent surface loads and constrained degrees.
    K,vol=assemble(xyz,tet,groups,E,meta['nu']); return xyz,K,force.ravel(),fixed_dof,free,E,vol # Return independently auditable case state.
def solve_case(base,params,case_id,run_ccx=True,nonlinear=False): # Solve one genuine finite-element case and cross-check solver evidence.
    directory=RUN/'cases'/case_id; directory.mkdir(parents=True,exist_ok=True); started=time.time() # Create immutable per-case evidence folder.
    xyz,K,f,fixed,free,E,vol=make_case(base,params); tet,groups,meta=base[1:] # Reconstruct full physics from parameters.
    u=np.zeros(len(f)); u[free]=spsolve(K[free][:,free],f[free]); residual=K@u-f # Obtain independent reference field and reactions.
    norm=max(np.linalg.norm(f),1.); rel=float(np.linalg.norm(residual[free])/norm); reactions=residual.reshape(-1,3); forces=f.reshape(-1,3) # Quantify true discrete force balance.
    force_error=float(np.linalg.norm((reactions+forces).sum(axis=0))/max(np.linalg.norm(forces.sum(axis=0)),1.)); moment_error=float(np.linalg.norm(np.cross(xyz,reactions+forces).sum(axis=0))/max(np.linalg.norm(np.cross(xyz,forces).sum(axis=0)),1.)) # Check global force and moment independently.
    np.savez_compressed(directory/'fields.npz',xyz=xyz,tet=tet,groups=groups,u=u.reshape(-1,3),f=forces,fixed=fixed,free=free,params=params,volume=vol,reaction=reactions) # Save every nodal field and geometry needed to replay.
    save_npz(directory/'stiffness.npz',K) # Preserve the full physical operator for training residuals and verification.
    lines=['*HEADING',case_id,'*NODE']+[f'{i+1},'+','.join(f'{v:.12g}' for v in point) for i,point in enumerate(xyz)] # Serialize actual coordinates with stable source IDs.
    for group in np.unique(groups): # Preserve heterogeneous region material identity.
        lines.append(f'*ELEMENT,TYPE=C3D10,ELSET=G{group}'); lines.extend(f'{i+1},'+','.join(str(n+1) for n in tet[i]) for i in np.where(groups==group)[0]) # Write exact quadratic connectivity.
        modulus,poisson=(200000.,.3) if group==1 else (E,meta['nu']); lines.extend([f'*MATERIAL,NAME=M{group}','*ELASTIC',f'{modulus:.12g},{poisson:.12g}',f'*SOLID SECTION,ELSET=G{group},MATERIAL=M{group}']) # Bind correct elastic material to each region.
    lines.extend(['*NSET,NSET=ALL,GENERATE',f'1,{len(xyz)},1','*BOUNDARY']); lines.extend(f'{i//3+1},{i%3+1},{i%3+1},0.' for i in fixed) # Declare physical zero displacement constraints.
    lines.extend(['*STEP,NLGEOM,INC=100' if nonlinear else '*STEP','*STATIC','0.1,1.,1e-6,0.2' if nonlinear else '1.,1.,1e-6,1.','*CLOAD']); lines.extend(f'{i//3+1},{i%3+1},{value:.12g}' for i,value in enumerate(f) if value!=0) # Apply exactly the same nodal forces with explicit valid increment bounds.
    lines.extend(['*NODE PRINT,NSET=ALL','U,RF','*NODE FILE','U,RF','*EL FILE','S','*END STEP']); inp=directory/'model.inp'; inp.write_text('\n'.join(lines)+'\n') # Preserve native input and real solver fields.
    evidence={'id':case_id,'family':meta['family'],'params':list(map(float,params)),'node_count':len(xyz),'element_count':len(tet),'independent_residual_relative':rel,'global_force_relative':force_error,'global_moment_relative':moment_error,'strain_energy_Nmm':float(.5*u@(K@u)),'max_displacement_mm':float(np.linalg.norm(u.reshape(-1,3),axis=1).max()),'input_sha256':sha(inp),'nonlinear':nonlinear,'ccx':None} # Record model and independent qualification.
    if run_ccx: # Execute actual native solver instead of presenting own assembly as CalculiX.
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',CCX_NPROC_RESULTS='1'); native=time.time() # Restrict each concurrent solve to one compute thread.
        with (directory/'solver.log').open('w') as log: completed=subprocess.run([str(CCX),'-i','model'],cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180) # Run explicitly selected native solver and preserve raw log.
        log=(directory/'solver.log').read_text(); dat=(directory/'model.dat').read_text() if (directory/'model.dat').exists() else ''; parsed=[]; active=False # Read only actual solver-produced displacement data.
        for line in dat.splitlines(): # Parse each displacement block, retaining final increment.
            if 'displacements (' in line.lower(): parsed=[]; active=True; continue # Identify a new native final-frame displacement table.
            if active and ('forces (' in line.lower() or 'total force' in line.lower()): active=False # Stop at the next result quantity.
            if active and re.match(r'^\s*\d+\s+',line): # Read complete node-vector records only.
                fields=line.split(); parsed.append([int(fields[0])]+[float(v.replace('D','E')) for v in fields[1:4]]) # Decode native numeric output precisely.
        native_u=np.full_like(u,np.nan) # Prevent missing records from being treated as zero displacement.
        for row in parsed: native_u[3*(int(row[0])-1):3*int(row[0])]=row[1:] # Restore source-node field identity.
        valid=completed.returncode==0 and 'Job finished' in log and np.isfinite(native_u).all() and '*ERROR' not in log # Require successful solve and complete native result coverage.
        error=float(np.linalg.norm(native_u-u)/max(np.linalg.norm(u),1e-12)) if valid else None # Compare independently assembled linear solution against native solver.
        evidence['ccx']={'returncode':completed.returncode,'completed':bool(valid),'cross_solver_relative':error,'seconds':time.time()-native,'dat_sha256':sha(directory/'model.dat') if dat else None,'frd_sha256':sha(directory/'model.frd') if (directory/'model.frd').exists() else None,'warnings':[line for line in log.splitlines() if '*WARNING' in line]} # Preserve solver-specific qualification.
        if valid: np.save(directory/'ccx_displacement.npy',native_u.reshape(-1,3)) # Save native vector independently from reference solution.
    evidence['status']='VALID_CONVERGED' if rel<1e-7 and force_error<1e-7 and moment_error<1e-7 and (not run_ccx or evidence['ccx']['completed'] and (nonlinear or evidence['ccx']['cross_solver_relative']<1e-5)) else 'QUARANTINED' # Gate training labels on predefined independent thresholds.
    evidence['seconds']=time.time()-started; write_json(directory/'receipt.json',evidence); return evidence # Finish full traceable case record.
