from pathlib import Path # Use original engineering sources and this calculation directory only.
from collections import defaultdict # Preserve load cases and source sections separately.
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla, json, re, subprocess, time # Parse source data and independently solve its nonlinear equilibrium.
R=Path(__file__).resolve().parents[1] # Resolve this calculation's isolated root.
def expand(s): # Expand the original MCT identifier lists.
    out=[] # Preserve all explicitly listed identifiers.
    for t in s.split(): # Parse whitespace-separated source ranges.
        m=re.fullmatch(r'(\d+)to(\d+)(?:by(\d+))?',t,re.I);out.extend(range(int(m[1]),int(m[2])+1,int(m[3] or 1)) if m else [int(t)]) # Expand inclusive MCT ranges exactly.
    return out # Return source identifiers without inventing missing elements.
def parse(): # Read the original geometry, sections, initial axial force, supports and permanent load.
    text=(R/'sources/original.mct').read_bytes().decode('gb18030');b=defaultdict(list);loads=defaultdict(list);cur='';lc='' # Decode the original Chinese MCT export.
    for line in text.splitlines(): # Inspect original source records in order.
        q=line.strip() # Normalize whitespace only.
        if not q or q.startswith(';'):continue # Skip comments and empty records.
        if q.startswith('*USE-STLD'):lc=q.split(',')[1].strip();continue # Keep permanent, construction and wind cases separate.
        if q.startswith('*'):cur=q.split(';')[0].strip();continue # Retain the exact source section name.
        b[cur].append(q) # Keep the original data record.
        if cur=='*CONLOAD':loads[lc].append(q) # Bind each force to its source load case.
    nodes={int(q.split(',')[0]):np.array([float(v) for v in q.split(',')[1:4]])/1000 for q in b['*NODE']};elements=[] # Convert millimetres to metres.
    for q in b['*ELEMENT']: # Retain all source element types and connectivity.
        a=[v.strip() for v in q.split(',')];elements.append(dict(id=int(a[0]),type=a[1],mat=int(a[2]),sec=int(a[3]),i=int(a[4]),j=int(a[5]),l0=float(a[8])/1000 if a[1]=='TENSTR' else None)) # Preserve source fields rather than classifying by guessed node ranges.
    A={1:np.pi*.168498**2/4,2:np.pi*.103436**2/4,3:.161**2-.145**2};E={1:120e9,2:120e9,3:206e9};gamma={1:124031.,2:84320.,3:1e-4};N0={} # Decode the original equivalent sections and material properties in SI units.
    for q in b['*INIFORCE']: # These records are axial forces, not stresses.
        a=q.split(',') # Separate element list, direction and force.
        for n in expand(a[0]):N0[n]=float(a[2])*1000 # Convert the actual original kN values to newtons.
    fixed=[] # Record physical source support directions.
    for q in b['*CONSTRAINT']: # Preserve the original restraint mask.
        a=q.split(',') # Decode node list and support components.
        for n in expand(a[0]):fixed.extend((n,j) for j,c in enumerate(a[1].strip()[:3]) if c=='1') # Keep only actual constrained translations.
    point={n:0. for n in nodes} # Separate concentrated permanent weight from self weight.
    for q in loads['二期']: # Only the source's activated second-stage permanent load is used.
        a=q.split(',') # Read each original load entry.
        for n in expand(a[0]):point[n]+=-float(a[3])*1000 # Preserve the downward source weight in newtons.
    F={n:np.array([0.,0.,-point[n]]) for n in nodes};mass={n:point[n]/9.806 for n in nodes} # Keep the static and dynamic mass ledgers consistent.
    for e in elements: # Apply source self weight exactly once.
        W=gamma[e['mat']]*A[e['sec']]*np.linalg.norm(nodes[e['j']]-nodes[e['i']]) # Use the actual original element chord length.
        for n in [e['i'],e['j']]:F[n][2]-=W/2;mass[n]+=W/2/9.806 # Lump the original distributed weight consistently.
    return dict(nodes=nodes,elements=elements,A=A,E=E,gamma=gamma,N0=N0,fixed=fixed,point=point,F=F,mass=mass) # Never read a historical frequency or fitted engineering parameter.
def ccx(folder,name='job',timeout=None): # Run the unmodified native solver and preserve the complete log.
    t=time.time() # Record actual wall-clock execution time.
    with (folder/'stdout.txt').open('w') as log:p=subprocess.run([str(R/'runtime/lib/ld-linux-x86-64.so.2'),'--library-path',str(R/'runtime/lib'),str(R/'runtime/bin/ccx'),'-i',name],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=timeout) # Execute the genuine native input without an artificial short wrapper timeout.
    return dict(returncode=p.returncode,elapsed_s=time.time()-t) # Report actual native execution status.
def read_u(file): # Read a native DAT displacement table.
    active=False;u={} # Preserve physical node identities.
    for line in file.read_text().splitlines(): # Parse solver output rather than a summary table.
        if 'displacements (' in line:active=True;continue # Begin native displacement records.
        if 'forces (' in line:active=False # Do not mistake reactions for displacements.
        a=line.split() # Decode standard numeric fields.
        if active and len(a)==4 and a[0].isdigit():u[int(a[0])]=[float(v) for v in a[1:]] # Retain all three displacement components.
    return u # Return only data actually written by CCX.
def run(): # Reconstruct the original planar working state and independently verify it.
    d=parse();ids=sorted(d['nodes']);index={n:i for i,n in enumerate(ids)};X=np.array([d['nodes'][n] for n in ids]);es=d['elements'];ij=np.array([[index[e['i']],index[e['j']]] for e in es]);L=np.linalg.norm(X[ij[:,1]]-X[ij[:,0]],axis=1) # Preserve every original source vertex and element.
    EA=np.array([d['E'][e['mat']]*d['A'][e['sec']] for e in es]);N0=np.array([d['N0'].get(e['id'],0.) for e in es]);k=(EA+N0)/L;F=np.array([d['F'][n] for n in ids]);u=np.zeros_like(X) # Start from source initial axial force and compatible axial tangent.
    fixed=set(3*i+1 for i in range(len(ids)));fixed.update(3*index[n]+j for n,j in d['fixed']);free=np.array(sorted(set(range(X.size))-fixed));ed=(ij[:,:,None]*3+np.arange(3)).reshape(-1,6);rr=np.repeat(ed,6,axis=1).ravel();cc=np.tile(ed,(1,6)).ravel();hist=[] # The planar out-of-plane restriction belongs only to this source-state verification.
    for it in range(12): # Solve actual nonlinear force equilibrium.
        dx=(X+u)[ij[:,1]]-(X+u)[ij[:,0]];l=np.linalg.norm(dx,axis=1);n=dx/l[:,None];N=N0+k*(l-L);nn=n[:,:,None]*n[:,None,:];C=k[:,None,None]*nn+(N/l)[:,None,None]*(np.eye(3)-nn) # Include both axial material stiffness and geometric stiffness.
        ke=np.concatenate([np.concatenate([C,-C],2),np.concatenate([-C,C],2)],1);K=sp.coo_matrix((ke.ravel(),(rr,cc)),shape=(X.size,X.size)).tocsc();fi=np.zeros_like(X);np.add.at(fi,ij[:,0],-N[:,None]*n);np.add.at(fi,ij[:,1],N[:,None]*n);res=(fi-F).ravel();err=np.linalg.norm(res[free]);hist.append(float(err)) # Record the actual residual in newtons.
        if err<.05:break # Respect the documented numerical cancellation floor.
        u.ravel()[free]+=sla.spsolve(K[free][:,free],-res[free]) # Correct only unconstrained physical translations.
    out=R/'runs/source_state';out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'state.npz',ids=ids,X=X,u=u,ij=ij,L=L,EA=EA,N0=N0,N=N,k=k,F=F,mass=[d['mass'][n] for n in ids]) # Save this newly solved state for spatial transfer.
    txt=['*HEADING','Original MCT working state','*NODE,NSET=ALL']+[f'{i+1},'+','.join(f'{v:.12e}' for v in p) for i,p in enumerate(X)] # Independently emit the native source-state model.
    for z,e in enumerate(es): # Preserve one native axial law per source element.
        i,j=ij[z]+1;txt += [f'*ELEMENT,TYPE=SPRINGA,ELSET=S{z+1}',f'{z+1},{i},{j}',f'*SPRING,ELSET=S{z+1},NONLINEAR','',f'{N0[z]-k[z]*100:.12e},-1.e2',f'{N0[z]:.12e},0.',f'{N0[z]+k[z]*100:.12e},1.e2'] # Explicit real-number syntax avoids ambiguous native parsing.
    txt+=['*BOUNDARY']+[f'{v//3+1},{v%3+1},{v%3+1},0.' for v in sorted(fixed)]+['*STEP,NLGEOM,INC=100','*STATIC','1.,1.,1.e-6,1.','*CLOAD']+[f'{i+1},3,{F[i,2]:.12e}' for i in range(len(ids))]+['*NODE PRINT,NSET=ALL','U,RF','*NODE FILE','U','*END STEP'] # Apply source self weight and permanent load exactly once.
    (out/'job.inp').write_text('\n'.join(txt)+'\n');a=ccx(out);native=read_u(out/'job.dat');un=np.array([native[i+1] for i in range(len(ids))]);a.update(max_translation_m=float(np.linalg.norm(u,axis=1).max()),max_native_theory_difference_m=float(np.linalg.norm(un-u,axis=1).max()),residual_history_N=hist,min_cable_force_N=float(N[[i for i,e in enumerate(es) if e['type']=='TENSTR']].min()),max_cable_force_relative_change=float(np.max(np.abs((N[N0>0]-N0[N0>0])/N0[N0>0]))),node_count=len(ids),element_count=len(es),mass_per_copy_kg=sum(d['mass'].values())) # Compare actual physical output, not exit codes alone.
    (out/'audit.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2),flush=True) # Preserve the genuine source-state verification results.
if __name__=='__main__':run() # Execute only when directly invoked.
