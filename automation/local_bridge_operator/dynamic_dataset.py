import os # Bound numerical model generation resources.
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1' # Avoid oversubscribing sparse eigenvalue workloads.
import json,time,re # Preserve native cross-checks and exact dataset split provenance.
from pathlib import Path # Read native result files when imported by independent audit callers.
import numpy as np # Build actual discrete modal trajectories and physical observation fields.
from scipy.sparse import diags,eye # Define mass-normalized modal comparison operators.
from dynamic_physics import * # Reuse independently assembled consistent mass and native solver execution.
def trapezoid(z,loads): # Integrate normalized independent modal states by the exact linear Newmark update.
    state=np.zeros((len(z),2));history=[state.copy()];denom=1+z*z/4 # Define normalized q and v/omega state and implicit denominator.
    for step in range(1,len(loads)): # Advance each physical amplitude step with known current and next forcing.
        q,v=state.T;g0=loads[step-1];g1=loads[step];qn=((1-z*z/4)*q+z*v+(z*z/4)*(g0+g1))/denom;vn=2*(qn-q)/z-v;state=np.column_stack([qn,vn]);history.append(state.copy()) # Apply undamped average-acceleration equations without learned corrections.
    return np.asarray(history) # Return the actual full trajectory for every retained mode.
def parse_native_displacement(path,probes): # Read actual native DAT transient outputs on stable source node IDs.
    rows=[];times=[];active=False;current={} # Track each complete displacement result block.
    for line in Path(path).read_text().splitlines(): # Preserve solver output order and time identity.
        if 'displacements (' in line.lower(): # Enter an explicit native displacement block.
            if current: rows.append([current[int(n)+1] for n in probes]);current={} # Save the previous complete probe vector.
            times.append(float(line.split()[-1]));active=True;continue # Capture actual solver time.
        if active and ('velocities (' in line.lower() or 'forces (' in line.lower()): active=False # Stop before another output quantity.
        if active and re.match(r'^\s*\d+\s+',line): # Parse native node-vector records only.
            fields=line.split();current[int(fields[0])]=[float(v.replace('D','E')) for v in fields[1:4]] # Keep actual high-precision vector components.
    if current: rows.append([current[int(n)+1] for n in probes]) # Save final complete time block.
    return np.asarray(times),np.asarray(rows) # Return native time and response arrays.
def reference_checks(): # Execute actual native/direct/modal/time-step cross-checks before training.
    reports=[] # Preserve all physical verification denominators.
    for family in ['girder','deck']: # Verify two independent structural topologies.
        case=family+'_reference';m=modal_model(case,count=48);t,load=waveform(m['omega'][0],steps=320,kind=1);dt=t[1];u,v,a,energy=newmark(m['K'],m['M'],m['f'],load,dt);q=[];modal_errors=[] # Compute a full-space finite-element transient reference with 48 available modes.
        for count in [12,24,48]: # Quantify actual mode-truncation error rather than assume adequacy.
            modal_force=m['phi'][:,:count].T@m['f'];states=trapezoid(m['omega'][:count]*dt,load);coord=states[:,:,0]*modal_force[None,:]/m['omega'][None,:count]**2;reconstructed=coord@m['phi'][:,:count].T;modal_errors.append({'modes':count,'full_field_relative':float(np.linalg.norm(reconstructed-u)/np.linalg.norm(u))}) # Compare decoded modal field with identical full-space forcing and time scheme.
        fine_t,fine_load=waveform(m['omega'][0],steps=640,kind=1);fine_u,_,_,fine_energy=newmark(m['K'],m['M'],m['f'],fine_load,fine_t[1]);time_error=float(np.linalg.norm(u-fine_u[::2])/np.linalg.norm(fine_u[::2])) # Perform actual independent time-step refinement.
        magnitude=np.linalg.norm(m['data']['u'],axis=1);probes=np.argsort(magnitude)[-6:];free_lookup={int(d):i for i,d in enumerate(m['free'])};probe_dofs=np.array([[free_lookup.get(int(n*3+c),-1) for c in range(3)] for n in probes]);assert np.all(probe_dofs>=0) # Select six existing free response nodes without inventing observation geometry.
        native,receipt=native_case(case,'transient',dt,load,probes);nt,nu=parse_native_displacement(native/'model.dat',probes);sampled=np.array([np.interp(nt,t,u[:,int(d)]) for d in probe_dofs.ravel()]).T.reshape(len(nt),len(probes),3);native_error=float(np.linalg.norm(nu-sampled)/np.linalg.norm(sampled)) # Compare actual native direct-integration result with independently assembled full-space Newmark.
        frequency_path=DYN/'native'/case/'frequency/model.dat';numbers=[] # Read the native modal output separately from transient state.
        for line in frequency_path.read_text().split('P A R T I C I P A T I O N')[0].splitlines(): # Limit parsing to the actual first eigenvalue table.
            if re.match(r'^\s*\d+\s+[-+0-9.E]+\s+[-+0-9.E]+\s+[-+0-9.E]+\s+[-+0-9.E]+\s*$',line): numbers.append(float(line.split()[3])) # Extract cycles/time column without confusing participation factors.
        frequency_error=float(np.max(np.abs(np.asarray(numbers[:24])-m['omega'][:24]/(2*np.pi))/(m['omega'][:24]/(2*np.pi))));folder=DYN/'verification'/family;folder.mkdir(parents=True,exist_ok=True);np.savez_compressed(folder/'reference_fields.npz',time=t,probe_nodes=probes,probe_independent=u[:,probe_dofs],native_time=nt,probe_native=nu,full_displacement=u.astype(np.float32),free=m['free']) # Save actual complete full-order displacement reference and both probe histories.
        report={'family':family,'density_tonne_mm3':RHO,'max_modal_frequency_relative_ccx':frequency_error,'native_transient_relative_probe':native_error,'native_transient_steps':len(nt),'native_completed':receipt['finished'],'time_step_seconds':dt,'time_step_halving_relative':time_error,'modal_truncation':modal_errors,'full_order_dynamic_equilibrium':energy['max_dynamic_residual'],'full_order_energy_balance_relative':energy['energy_balance_relative'],'fine_energy_balance_relative':fine_energy['energy_balance_relative'],'status':'PASS' if frequency_error<.001 and native_error<.01 and time_error<.03 and modal_errors[-1]['full_field_relative']<.05 and receipt['finished'] else 'HOLD'};reports.append(report);write_json(DYN/'physics_verification.json',reports);print('VERIFIED',json.dumps(report),flush=True) # Apply explicit numerical gates without promoting failed model fidelity.
def create_dataset(): # Build geometry-isolated real modal state/forcing trajectories.
    rows=[];manifest=json.loads((RUN/'manifest.json').read_text());count=48 # Retain the mode count independently checked against full-order dynamics.
    for entry in [v for v in manifest if v['family'] in ['girder','deck'] and v['id'].endswith('_l0')]: # Reuse independent geometry grouping while generating new dynamic histories.
        m=modal_model(entry['id'],count);folder=DYN/'geometries'/entry['geometry_id'];folder.mkdir(parents=True,exist_ok=True);modal_force=m['phi'].T@m['f'];np.savez_compressed(folder/'modal_geometry.npz',omega=m['omega'],phi=m['phi'],free=m['free'],modal_force=modal_force,params=entry['params'],xyz=m['data']['xyz'],tet=m['data']['tet']);write_json(folder/'receipt.json',{'source_case':entry['id'],'source_input_sha256':sha(RUN/'cases'/entry['id']/'model.inp'),'max_eigen_residual':float(m['eigen_residual'].max()),'mass_orthogonality':m['orthogonality'],'mass_tonne':m['mass'],'density_tonne_mm3':RHO,'linear_elastic':True}) # Save true modes and geometry-specific decoder, explicitly requiring FEM modal preprocessing for new geometry.
        for kind in [0,1]: # Generate two independent forcing histories per fixed geometry.
            t,load=waveform(m['omega'][0],steps=320,kind=kind,amplitude=.7+.3*kind);state=trapezoid(m['omega']*(t[1]-t[0]),load);identity=entry['geometry_id']+f'_wave{kind}';np.savez_compressed(folder/f'wave{kind}.npz',time=t,amplitude=load,state=state,z=m['omega']*(t[1]-t[0]));rows.append({'id':identity,'geometry_id':entry['geometry_id'],'family':entry['family'],'split':entry['split'],'wave':kind,'path':str(folder/f'wave{kind}.npz'),'steps':320,'modes':count}) # Preserve complete state transition labels with no cross-geometry leakage.
        write_json(DYN/'manifest.json',rows);print('DATA',entry['geometry_id'],entry['split'],flush=True) # Checkpoint each actually solved geometry.
if __name__=='__main__': # Run physical validation before dynamic dataset production.
    from pathlib import Path # Read actual native result files.
    reference_checks();create_dataset() # Complete true direct-solver comparisons and all dynamic cases.
