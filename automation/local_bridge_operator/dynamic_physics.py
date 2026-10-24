import os # Bound sparse dynamic solver resources.
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1' # Avoid CPU oversubscription across structural tasks.
import json,time,math,re,subprocess # Preserve actual physical computations and native evidence.
import numpy as np # Assemble consistent mass and full transient states.
from scipy.sparse import coo_matrix,load_npz,save_npz # Preserve sparse physical operators.
from scipy.sparse.linalg import eigsh,splu # Solve true generalized eigenproblems and full dynamic systems.
from fem import ROOT,REPO,RUN,CCX,EDGES,sha,write_json # Reuse exact static mesh and solver identities.
DYN=REPO/'build/local-dynamics-20261024';DYN.mkdir(exist_ok=True) # Separate all dynamic evidence from prior static runs.
RHO=7.85e-9 # Declare conventional research steel density in tonne/mm^3, equal to 7850 kg/m^3; not inferred from the drawings.
def mass_matrix(xyz,tet,rho=RHO): # Integrate quadratic-tetrahedron consistent mass exactly over straight-sided volumes.
    polynomials=[] # Represent shape functions as explicit barycentric monomials.
    for i in range(4): # Add vertex shape functions Ni=2Li^2-Li.
        first=[0]*4;second=[0]*4;first[i]=1;second[i]=2;polynomials.append([(2.,second),(-1.,first)]) # Preserve exact polynomial coefficients.
    for i,j in EDGES: # Add midside shape functions Nij=4LiLj.
        powers=[0]*4;powers[i]=powers[j]=1;polynomials.append([(4.,powers)]) # Follow the same C3D10 edge ordering as stiffness.
    C=np.zeros((10,10)) # Allocate exact normalized scalar element mass.
    for i in range(10): # Integrate all quadratic interpolation products.
        for j in range(10): # Preserve symmetry by evaluating the same exact monomial formula.
            for ci,pi in polynomials[i]: # Expand the first shape polynomial.
                for cj,pj in polynomials[j]: # Expand the second shape polynomial.
                    powers=np.asarray(pi)+np.asarray(pj);C[i,j]+=ci*cj*6*math.prod(math.factorial(int(p)) for p in powers)/math.factorial(int(powers.sum())+3) # Use exact simplex integral divided by physical volume.
    assert abs(C.sum()-1)<1e-12 and np.linalg.eigvalsh(C).min()>0 # Check mass conservation and element positive definiteness.
    corners=xyz[tet[:,:4]];vol=np.abs(np.linalg.det(np.stack([corners[:,i]-corners[:,0] for i in [1,2,3]],axis=2)))/6;me=np.kron(C,np.eye(3))[None,:,:]*(rho*vol)[:,None,None] # Form exact three-direction consistent mass.
    dofs=(tet[:,:,None]*3+np.arange(3)).reshape(-1,30);rows=np.repeat(dofs,30,axis=1).ravel();cols=np.tile(dofs,(1,30)).ravel();M=coo_matrix((me.ravel(),(rows,cols)),shape=(xyz.size,xyz.size)).tocsr() # Assemble original source-node mass topology.
    return M,float(rho*vol.sum()) # Return physical mass operator and independent total mass.
def modal_model(case_id,count=24): # Obtain source-specific modes from actual full finite-element matrices.
    path=RUN/'cases'/case_id;data=np.load(path/'fields.npz');K=load_npz(path/'stiffness.npz');M,total=mass_matrix(data['xyz'],data['tet']);free=data['free'];k=K[free][:,free].tocsc();m=M[free][:,free].tocsc();eigen,vectors=eigsh(k,k=count,M=m,sigma=0.,which='LM',tol=1e-10) # Solve constrained generalized eigenproblem with a reproducible shift.
    order=np.argsort(eigen);eigen=eigen[order];vectors=vectors[:,order] # Sort actual eigenvalues without inventing cross-geometry mode correspondence.
    for i in range(count): # Normalize modal sign deterministically for saved fields.
        if vectors[np.argmax(np.abs(vectors[:,i])),i]<0: vectors[:,i]*=-1 # Remove arbitrary eigenvector sign flips.
    residual=np.linalg.norm(k@vectors-(m@vectors)*eigen,axis=0)/np.maximum(np.linalg.norm(k@vectors,axis=0),1e-30);orth=np.linalg.norm(vectors.T@(m@vectors)-np.eye(count)) # Verify actual eigenpair equations and modal normalization.
    return {'data':data,'K':k,'M':m,'mass':total,'free':free,'f':data['f'].ravel()[free],'omega':np.sqrt(eigen),'phi':vectors,'eigen_residual':residual,'orthogonality':orth} # Return full and reduced physical definitions separately.
def newmark(K,M,f,amplitude,dt,damping=None): # Integrate full or reduced linear dynamics with average acceleration.
    n=K.shape[0];C=M*0 if damping is None else damping;A=(K+4*M/dt**2+2*C/dt).tocsc();factor=splu(A);u=np.zeros(n);v=np.zeros(n);a=np.zeros(n);states=[u.copy()];velocities=[v.copy()];accelerations=[a.copy()];residuals=[];absolute_residuals=[];energies=[0.];work=[0.];characteristic_force=max(np.linalg.norm(f)*np.max(np.abs(amplitude)),1e-15) # Start from explicit zero initial conditions and fixed whole-history force scale.
    for step in range(1,len(amplitude)): # Advance every real forcing increment.
        target=f*amplitude[step];rhs=target+M@(4*u/dt**2+4*v/dt+a)+C@(2*u/dt+v);next_u=factor.solve(rhs);next_a=4*(next_u-u)/dt**2-4*v/dt-a;next_v=v+dt*(a+next_a)/2 # Solve average-acceleration Newmark equations.
        absolute_residuals.append(float(np.linalg.norm(M@next_a+C@next_v+K@next_u-target)));residuals.append(absolute_residuals[-1]/max(np.linalg.norm(target),np.linalg.norm(f)*1e-8,1e-15));work.append(work[-1]+float(.5*f*(amplitude[step]+amplitude[step-1])@(next_u-u)));energies.append(float(.5*next_u@(K@next_u)+.5*next_v@(M@next_v)));u,v,a=next_u,next_v,next_a;states.append(u.copy());velocities.append(v.copy());accelerations.append(a.copy()) # Preserve physical equilibrium, discrete work and state history, including absolute force residual near force zero crossings.
    return np.asarray(states),np.asarray(velocities),np.asarray(accelerations),{'max_dynamic_residual':max(residuals),'max_absolute_dynamic_residual_N':max(absolute_residuals),'max_fixed_force_dynamic_residual':max(absolute_residuals)/characteristic_force,'characteristic_force_N':characteristic_force,'energy_Nmm':energies,'external_work_Nmm':work,'energy_balance_relative':float(np.max(np.abs(np.asarray(energies)-work))/max(np.max(np.abs(energies)),1e-20))} # Keep integration checks separate from modal truncation.
def waveform(omega0,steps=320,kind=0,amplitude=1.): # Define smooth finite-duration excitation in seconds with zero initial force.
    duration=5*2*np.pi/omega0;t=np.linspace(0,duration,steps+1);phase=omega0*t;load=amplitude*np.sin(.7*phase)*np.sin(np.pi*t/duration)**2 if kind==0 else amplitude*(np.sin(1.05*phase)+.3*np.sin(1.8*phase))*np.sin(np.pi*t/duration)**2 # Generate sub-resonant and mixed near-resonant independent loads.
    return t,load # Return physical time and dimensionless amplitude.
def native_case(case_id,mode,dt=None,amplitude=None,probes=None): # Generate and execute actual CalculiX modal or direct-integration analyses.
    source=RUN/'cases'/case_id/'model.inp';text=source.read_text().split('*STEP')[0];text=text.replace('*SOLID SECTION','*DENSITY\n7.85e-9\n*SOLID SECTION');out=DYN/'native'/case_id/mode;out.mkdir(parents=True,exist_ok=True) # Reuse identical source geometry/material/support and add explicitly assumed steel density.
    if mode=='frequency': text+='*STEP\n*FREQUENCY\n24\n*END STEP\n' # Solve native generalized modal problem without changing support conditions.
    else: # Define a separate zero-initial-state transient deck to avoid frequency-step state contamination.
        data=np.load(source.parent/'fields.npz');force=data['f'].ravel();text+='*NSET,NSET=PROBES\n'+','.join(str(int(v)+1) for v in probes)+'\n*AMPLITUDE,NAME=HISTORY\n'+'\n'.join(f'{i*dt:.14g},{v:.14g}' for i,v in enumerate(amplitude))+'\n*STEP,INC=10000\n*DYNAMIC,DIRECT,ALPHA=0\n'+f'{dt:.14g},{dt*(len(amplitude)-1):.14g}\n*CLOAD,AMPLITUDE=HISTORY\n'+'\n'.join(f'{i//3+1},{i%3+1},{v:.14g}' for i,v in enumerate(force) if v!=0)+'\n*NODE PRINT,NSET=PROBES,FREQUENCY=1\nU,V\n*END STEP\n' # Match full-space undamped Newmark loading and requested observation nodes.
    (out/'model.inp').write_text(text);start=time.time() # Freeze exact native dynamic input.
    with (out/'solver.log').open('w') as log: result=subprocess.run([str(CCX),'-i','model'],cwd=out,env=dict(os.environ,OMP_NUM_THREADS='1'),stdout=log,stderr=subprocess.STDOUT,timeout=300) # Execute native physics and retain complete original logs.
    log=(out/'solver.log').read_text();receipt={'case':case_id,'mode':mode,'returncode':result.returncode,'finished':'Job finished' in log and '*ERROR' not in log,'seconds':time.time()-start,'input_sha256':sha(out/'model.inp'),'dat_sha256':sha(out/'model.dat') if (out/'model.dat').exists() else None};write_json(out/'receipt.json',receipt);return out,receipt # Return actual native evidence without assuming successful convergence.
if __name__=='__main__': # Establish source-matched modal and transient numerical validation.
    results=[] # Record both structural-family checks.
    for family in ['girder','deck']: # Validate two source-grounded steel structural topologies.
        case=family+'_reference';model=modal_model(case);out,receipt=native_case(case,'frequency');print(family,'frequencies',model['omega'][:6]/(2*np.pi),receipt,flush=True);np.savez_compressed(DYN/f'{family}_reference_modes.npz',omega=model['omega'],phi=model['phi'],free=model['free'],eigen_residual=model['eigen_residual']);write_json(DYN/f'{family}_reference_modes.json',{'mass_tonne':model['mass'],'max_eigen_residual':float(model['eigen_residual'].max()),'mass_orthogonality':float(model['orthogonality']),'density_tonne_mm3':RHO,'density_provenance':'Declared conventional research steel density 7850 kg/m3, not an extracted drawing parameter','model':'linear elastic consistent-mass C3D10; no nonlinear modal reduction claim'});results.append(receipt) # Preserve actual modal fields and explicit model scope.
    write_json(DYN/'native_frequency_runs.json',results) # Save complete native modal execution outcomes.
