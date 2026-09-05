from pathlib import Path  # Keep every work-state input and output local to this new reconstruction.
import json, re, subprocess, collections, numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla  # Independently assemble cable equilibrium and run native CalculiX.
ROOT=Path(__file__).parent; RESULT=ROOT/'results'; RESULT.mkdir(exist_ok=True)  # Preserve actual numerical evidence.
def expand(s):  # Parse original MIDAS integer lists including stride ranges.
    ans=[]  # Store source identifiers without guessing omitted ones.
    for token in s.replace('\\',' ').split():  # Handle wrapped source records.
        m=re.fullmatch(r'(\d+)to(\d+)(?:by(\d+))?',token,re.I)  # Recognize the complete inclusive MIDAS range syntax.
        ans.extend(range(int(m[1]),int(m[2])+1,int(m[3] or 1))) if m else ans.append(int(token))  # Expand exactly the listed range or integer.
    return ans  # Return source identifiers in order.
def number(x): return f'{float(x):.11e}'  # Include a decimal point and stay within the native 20-character numeric field.
def read_source():  # Construct an auditable representation of the original engineering state.
    data=json.loads((ROOT/'sources/mct_sections.json').read_text()); sec=data['sections']; nodes={int(k):np.array(v,dtype=float)/1000 for k,v in data['nodes'].items()}; elems={int(k):v for k,v in data['elements'].items()}  # Convert only original geometry from mm to m.
    forces={}  # Preserve original initial axial forces in N.
    for row in sec['*INIFORCE']:  # Read source force ranges rather than infer tension from target frequencies.
        p=[s.strip() for s in row.split(',')]  # Decode original axial-force records.
        for eid in expand(p[0]): forces[eid]=float(p[2])*1000  # Convert original kN to N once.
    area={1:np.pi*.168498**2/4,2:np.pi*.103436**2/4,3:.161**2-.145**2}; E={1:120e9,2:120e9,3:206e9}; weight={1:124031.,2:84320.,3:1.e-4}  # Use original effective-section definitions and original material cards.
    g=9.806; f={i:np.zeros(3) for i in nodes}; mass={i:0. for i in nodes}; cables=[]; posts=[]  # Separate rope prestress, gantry rods, external loads and inertia.
    for eid,e in elems.items():  # Read every physical source element.
        mat=int(e[1]); n1,n2=int(e[3]),int(e[4]); length=float(np.linalg.norm(nodes[n2]-nodes[n1])); record=[eid,n1,n2,mat,area[mat]*E[mat],forces.get(eid,0.),length]  # Bind axial stiffness and preload to exact source endpoints.
        (posts if e[0]=='TRUSS' else cables).append(record)  # Preserve the source distinction between frame equivalents and cables.
        for n in (n1,n2): f[n][2]-=weight[mat]*area[mat]*length/2;mass[n]+=weight[mat]*area[mat]*length/(2*g)  # Reproduce source selfweight without adding a second physical-density load.
    cases=json.loads((ROOT/'sources/loadcases.json').read_text()); dead=cases.get('二期',[])  # Use the actual active permanent-load case only.
    point={}  # Preserve original concentrated loads for later spatial redistribution.
    for row in dead:  # Do not mix construction, wind or temperature loads into the working state.
        p=[s.strip() for s in row.split(',')]; load=np.array([float(s) for s in p[1:4]])*1000  # Convert the original source force vector.
        for n in expand(p[0]): f[n]+=load;mass[n]+=-load[2]/g;point[n]=point.get(n,np.zeros(3))+load  # Associate gravity mass and force with its exact source node.
    fixed=[]  # Retain the original translational boundary conditions.
    for row in sec['*CONSTRAINT']:  # Interpret original zero/one freedom flags explicitly.
        p=[s.strip() for s in row.split(',')]  # Keep longitudinal sliding where the source permits it.
        for n in expand(p[0]): fixed.extend((n,k) for k,v in enumerate(p[1][:3]) if v=='1')  # Do not constrain additional source translations.
    return {'nodes':nodes,'elements':elems,'cables':cables,'posts':posts,'mass':mass,'force':f,'point':point,'fixed':fixed,'g':g,'area':area,'E':E,'weight':weight,'sections':sec}  # Return a complete mechanically defined source state.
def equilibrium(source):  # Independently solve the original planar model before building its spatial expansion.
    order=sorted(source['nodes']); index={n:i for i,n in enumerate(order)}; X=np.array([source['nodes'][n] for n in order]); F=np.array([source['force'][n] for n in order]); records=source['cables']+source['posts']  # Use the actual source graph.
    ends=np.array([[index[r[1]],index[r[2]]] for r in records]); L0=np.array([r[6] for r in records]); EA=np.array([r[4] for r in records]); N0=np.array([r[5] for r in records]); cable=np.array([r in source['cables'] for r in records]); k=EA/L0  # Preserve source reference lengths and axial force at the supplied coordinates.
    locked=set(3*index[n]+d for n,d in source['fixed']);locked.update(3*i+1 for i in range(len(order))); free=np.array(sorted(set(range(3*len(order)))-locked))  # Suppress out-of-plane motion only for the original planar-state verification.
    dofs=(3*ends[:,:,None]+np.arange(3)).reshape(-1,6); rows=np.repeat(dofs,6,axis=1).ravel();cols=np.tile(dofs,(1,6)).ravel(); u=np.zeros_like(X); history=[]  # Prepare an independent sparse geometric-nonlinear tangent assembly.
    def evaluate(v, matrix=True):  # Compute actual finite-rotation axial forces and exact spatial tangent.
        delta=X[ends[:,1]]+v[ends[:,1]]-X[ends[:,0]]-v[ends[:,0]]; L=np.linalg.norm(delta,axis=1); t=delta/L[:,None]; N=N0+k*(L-L0);N=np.where(cable,np.maximum(N,0.),N)  # Keep ropes tension-only, not compression springs.
        internal=np.zeros_like(X); np.add.at(internal,ends[:,0],-N[:,None]*t);np.add.at(internal,ends[:,1],N[:,None]*t);r=(F-internal).ravel()  # Form equilibrium residual in the physical Cartesian coordinates.
        if not matrix:return r,N  # Permit an inexpensive residual-only line-search evaluation.
        outer=t[:,:,None]*t[:,None,:]; ke=k[:,None,None]*outer+N[:,None,None]/L[:,None,None]*(np.eye(3)-outer);ke[cable&(N<=0)]=0  # Derive material and initial-force stiffness separately.
        blocks=np.concatenate((np.concatenate((ke,-ke),axis=2),np.concatenate((-ke,ke),axis=2)),axis=1); K=sp.coo_matrix((blocks.ravel(),(rows,cols)),shape=(X.size,X.size)).tocsc()  # Assemble the physical tangent without reading any historical matrix.
        return r,N,K  # Return all quantities needed for an auditable Newton update.
    for it in range(60):  # Complete the equilibrium iteration, retaining every residual.
        r,N,K=evaluate(u); err=float(np.max(np.abs(r[free])));history.append({'iteration':it,'max_free_residual_N':err});print('MCT_NEWTON',it,err,flush=True)  # Report actual convergence, not merely the solver exit code.
        if err<2.e-4:break  # Terminate when further displacement corrections are below physical roundoff significance.
        step=np.zeros(X.size);step[free]=spla.spsolve(K[free][:,free],r[free]);alpha=1.;base=np.linalg.norm(r[free])  # Solve the independent tangent equation.
        while alpha>1/128 and np.linalg.norm(evaluate(u+alpha*step.reshape(-1,3),False)[0][free])>base:alpha/=2  # Dampen only numerical Newton updates, never modify physical stiffness.
        u+=alpha*step.reshape(-1,3)  # Advance the physical configuration.
    r,N,K=evaluate(u); state={'node_ids':order,'element_ids':[r0[0] for r0 in records],'displacements_m':u.tolist(),'equilibrium_coordinates_m':(X+u).tolist(),'forces_N':N.tolist(),'max_displacement_m':float(np.max(np.linalg.norm(u,axis=1))),'max_free_residual_N':float(np.max(np.abs(r[free]))),'total_gravity_mass_kg':float(sum(source['mass'].values())),'total_external_force_N':F.sum(axis=0).tolist(),'history':history}  # Save source-based work-state evidence.
    return state  # Do not infer modal success from this static calculation.
def write_axial(path,source):  # Generate a complete native input for the original planar verification.
    lines=['*HEADING','Original MCT independent native equilibrium verification','*NODE,NSET=ALL']  # Label this as a source-state test, not the complete spatial bridge.
    for n,x in source['nodes'].items():lines.append(str(n)+','+','.join(number(v) for v in x))  # Retain every original coordinate.
    for r in source['cables']+source['posts']:  # Generate one native law for each original axial member.
        eid,n1,n2,mat,EA,N,L=r;k=EA/L;end=max(L*.05,N/k*2+.001);lines.extend([f'*ELEMENT,TYPE=SPRINGA,ELSET=E{eid}',f'{eid},{n1},{n2}',f'*SPRING,ELSET=E{eid},NONLINEAR'])  # Preserve initial force and axial tangent independently.
        pairs=[(0.,-N/k-end),(0.,-N/k),(N,0.),(N+k*end,end)] if mat!=3 else [(-k*end,-end),(0.,0.),(k*end,end)]  # Use tension-only cables and bidirectional gantry rods.
        for force,extension in pairs:lines.append(number(force)+','+number(extension))  # Use parser-safe floating point fields.
    for j,(n,m) in enumerate(source['mass'].items(),20000):lines.extend([f'*ELEMENT,TYPE=MASS,ELSET=M{n}',f'{j},{n}',f'*MASS,ELSET=M{n}',number(max(m,1.e-12))])  # Reproduce physical gravity mass without double-counting effective rope density.
    lines.append('*BOUNDARY');fixed=set(source['fixed'])|{(n,1) for n in source['nodes']}  # Impose original boundaries and explicitly planar test kinematics.
    for n,d in sorted(fixed):lines.append(f'{n},{d+1},{d+1}')  # Preserve free longitudinal saddle translations.
    lines.extend(['*STEP,NLGEOM,INC=100','*STATIC','0.1,1.,1.e-8,0.2','*CLOAD'])  # Equilibrate preload and actual permanent gravity loads.
    for n,f in source['force'].items():  # Apply the original source load vector once.
        for d,value in enumerate(f):  # Write nonzero Cartesian load components only.
            if value:lines.append(f'{n},{d+1},{number(value)}')  # Preserve the source load sign and units.
    lines.extend(['*NODE PRINT,NSET=ALL','U,RF','*NODE FILE','U','*END STEP'])  # Save actual equilibrium displacements and support reactions.
    path.write_text('\n'.join(lines)+'\n')  # Preserve the exact native input bytes.
def execute():  # Run numerical work-state checks rather than stopping at data inspection.
    unit=ROOT/'unit_string';p=unit/'string.inp';text=p.read_text();text=re.sub(r'^0,','0.0,',text,flags=re.M);p.write_text(text)  # Fix the documented native parser's decimal-point distinction, not the physical spring law.
    with (unit/'verified_solver.txt').open('w') as log: run=subprocess.run([str((ROOT/'ccx').resolve()),'string'],cwd=unit,stdout=log,stderr=subprocess.STDOUT,timeout=180)  # Execute the corrected native prestressed-string test.
    print('VERIFIED_STRING_EXIT',run.returncode,flush=True); print((unit/'verified_solver.txt').read_text()[-2500:],flush=True); print((unit/'string.dat').read_text()[:2200],flush=True)  # Expose both actual errors and actual eigenvalues.
    source=read_source();out=RESULT/'mct_workstate';out.mkdir(exist_ok=True);state=equilibrium(source);(out/'theory_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))  # Complete an independent nonlinear solution of the engineering MCT.
    write_axial(out/'workstate.inp',source)  # Save the corresponding independently parsed native CCX model.
    with (out/'native_solver.txt').open('w') as log: run=subprocess.run([str((ROOT/'ccx').resolve()),'workstate'],cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=480)  # Run actual native static equilibrium on the same original input.
    print('MCT_NATIVE_EXIT',run.returncode,flush=True);print((out/'native_solver.txt').read_text()[-4500:],flush=True)  # Do not conceal solver nonconvergence.
    (out/'run_status.json').write_text(json.dumps({'native_exit':run.returncode,'theory_max_displacement_m':state['max_displacement_m'],'theory_max_residual_N':state['max_free_residual_N'],'mass_kg':state['total_gravity_mass_kg']},indent=2))  # Retain precise status with each native calculation.
    return source,state  # Provide only this turn's newly verified engineering state to the spatial builder.
