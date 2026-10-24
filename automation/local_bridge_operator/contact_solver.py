import os # Bound independent native runs and numerical resource use.
os.environ['OPENBLAS_NUM_THREADS']='1' # Avoid contention with other verification jobs.
import argparse,json,subprocess,hashlib,time # Keep explicit inputs and native execution receipts.
from pathlib import Path # Resolve outputs relative to the checked out repository.
REPO=Path(__file__).resolve().parents[2] # Resolve the repository independently of the current directory.
OUT=REPO/'build/local-contact-20261024' # Isolate true contact calculations from bonded splice proxies.
CCX=Path('/workspace/scratch/500ec816102b/solver-runtime/ccx-precision-v2') # Use the installed actual CalculiX executable wrapper.
def sha(path): # Fingerprint complete native evidence.
    return hashlib.sha256(path.read_bytes()).hexdigest() # Avoid inference from metadata or filenames.
def mesh(nx=4,ny=2,nz=1): # Make independent rigid support and deformable upper contact blocks in millimetres.
    xyz=[];elements=[];blocks=[] # Keep source node and element identifiers explicit.
    for x0,y0,z0,L,W,H,ax,ay,az in [(-10.,-10.,-10.,120.,70.,10.,2,2,1),(0.,0.,0.,100.,50.,10.,nx,ny,nz)]: # Cover the sliding footprint with a larger fixed lower body.
        node0=len(xyz);elem0=len(elements);ids={} # Do not merge contacting nodes across the interface.
        for k in range(az+1): # Generate independent through-thickness node planes.
            for j in range(ay+1): # Generate transverse grid stations.
                for i in range(ax+1): # Generate longitudinal grid stations.
                    xyz.append((x0+L*i/ax,y0+W*j/ay,z0+H*k/az));ids[i,j,k]=len(xyz) # Store stable one-based solver node identifiers.
        for k in range(az): # Form conventional positively oriented C3D8 cells.
            for j in range(ay): # Form each row of cells.
                for i in range(ax): elements.append(tuple(ids[i+di,j+dj,k+dk] for di,dj,dk in [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)])) # Preserve CalculiX face numbering S1 bottom and S2 top.
        blocks.append({'nodes':list(range(node0+1,len(xyz)+1)),'elements':list(range(elem0+1,len(elements)+1)),'bottom_nodes':[ids[i,j,0] for j in range(ay+1) for i in range(ax+1)],'top_nodes':[ids[i,j,az] for j in range(ay+1) for i in range(ax+1)],'bottom_elements':list(range(elem0+1,elem0+ax*ay+1)),'top_elements':list(range(elem0+ax*ay*(az-1)+1,len(elements)+1))}) # Retain exact contact and loading surfaces.
    return xyz,elements,blocks # Return only geometry generated from declared specimen dimensions.
def deck(pressure=10.,mu=.3,nx=4,ny=2,nz=1,normal_stiffness=1.e6,stick_stiffness=1.e4): # Define a repeatable frictional contact path without any tie constraints.
    xyz,elements,blocks=mesh(nx,ny,nz);lower,upper=blocks;lines=['*HEADING','Two-block friction verification specimen; mm,N,MPa; not an as-built bridge joint','*NODE,NSET=ALL'] # Identify the limited engineering scope inside the native input.
    lines.extend(f'{i},'+','.join(f'{v:.15g}' for v in p) for i,p in enumerate(xyz,1));lines.append('*ELEMENT,TYPE=C3D8,ELSET=BODY') # Write exact independent block geometry.
    lines.extend(f'{i},'+','.join(map(str,e)) for i,e in enumerate(elements,1)) # Write full integration hexahedra with no reduced-integration hourglass mode.
    for name,nodes in [('LOWER',lower['nodes']),('DRIVE',upper['top_nodes']),('SLAVENODES',upper['bottom_nodes'])]: # Define independently auditable boundary and observation sets.
        lines.append('*NSET,NSET='+name);lines.extend(','.join(map(str,nodes[i:i+12])) for i in range(0,len(nodes),12)) # Keep native input line lengths bounded.
    lines.append('*SURFACE,NAME=MASTER,TYPE=ELEMENT');lines.extend(f'{e},S2' for e in lower['top_elements']);lines.append('*SURFACE,NAME=SLAVE,TYPE=ELEMENT');lines.extend(f'{e},S1' for e in upper['bottom_elements']) # Pair upper bottom faces with lower top faces.
    lines.extend(['*MATERIAL,NAME=STEEL','*ELASTIC','200000.,0.3','*SOLID SECTION,ELSET=BODY,MATERIAL=STEEL','*BOUNDARY','LOWER,1,3,0.','DRIVE,1,2,0.','*CONTACT PAIR,INTERACTION=FRICTIONAL,TYPE=SURFACE TO SURFACE','SLAVE,MASTER','*SURFACE INTERACTION,NAME=FRICTIONAL','*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=LINEAR',f'{normal_stiffness:.9g}','*FRICTION',f'{mu:.9g},{stick_stiffness:.9g}']) # Use genuine finite-sliding penalty normal contact and Coulomb friction.
    for stage,target in enumerate([0.,1.e-5,.1,-.1],1): # Compress first, sample pre-slip response, slide forward, then reverse the path.
        lines.extend(['*STEP,NLGEOM,INC=300','*STATIC','0.05,1.,1.e-8,0.1','*DLOAD']) # Use automatic increments with bounded maximum load/time advance.
        lines.extend(f'{e},P2,{pressure:.9g}' for e in upper['top_elements']);lines.extend(['*BOUNDARY',f'DRIVE,1,1,{target:.12g}','DRIVE,2,2,0.','*NODE PRINT,NSET=ALL','U,RF','*CONTACT PRINT,SLAVE=SLAVE,MASTER=MASTER','CDIS,CSTR,CF,CFN,CFS,CNUM','*NODE FILE','U,RF','*EL FILE','S','*CONTACT FILE','CDIS,CSTR','*END STEP']) # Save every native increment including pressure, overlap, sliding, and contact resultants.
    meta={'pressure_MPa':pressure,'mu':mu,'E_MPa':200000.,'nu':.3,'normal_stiffness_N_per_mm3':normal_stiffness,'stick_stiffness_N_per_mm3':stick_stiffness,'dimensions_mm':{'upper':[100.,50.,10.],'lower':[120.,70.,10.]},'mesh_upper':[nx,ny,nz],'node_count':len(xyz),'element_count':len(elements),'blocks':blocks,'stage_targets_ux_mm':[0.,1.e-5,.1,-.1],'stage_end_times':[1.,2.,3.,4.],'contact':'surface-to-surface finite sliding penalty; no ties or shared interface nodes','lower_body':'all nodes fixed to represent a rigid support','material':'linear PK2 elasticity with NLGEOM; no plasticity','normal_load':'uniform follower pressure on deformable upper top','scope':'verification specimen; geometry and friction are explicit assumptions, not measured Zhaqing bridge data'} # Store units and all assumptions with the native deck.
    return '\n'.join(lines)+'\n',meta # Return fully reproducible input text and its interpretation.
def solve(name,pressure=10.,mu=.3,nx=4,ny=2,nz=1,normal_stiffness=1.e6,stick_stiffness=1.e4): # Execute a distinct immutable native case directory.
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True);inp,meta=deck(pressure,mu,nx,ny,nz,normal_stiffness,stick_stiffness);path=folder/'contact.inp' # Keep all native files under one identifiable case.
    if (folder/'receipt.json').exists(): raise FileExistsError(f'Refusing to overwrite completed evidence: {folder}') # Preserve existing success or failure evidence on reruns.
    lock=folder/'run.lock';lock_fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL);os.write(lock_fd,f'pid={os.getpid()}\n'.encode());os.close(lock_fd) # Prevent concurrent same-directory runs from corrupting source evidence.
    path.write_text(inp);(folder/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n');start=time.monotonic() # Persist exact inputs before launching the solver.
    env=os.environ.copy();env.update({'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','CCX_NPROC_STIFFNESS':'1','CCX_NPROC_RESULTS':'1'}) # Bound actual native CPU use deterministically.
    try: result=subprocess.run([str(CCX),'contact'],cwd=folder,env=env,capture_output=True,text=True,timeout=240);log=result.stdout+result.stderr;returncode=result.returncode # Capture real solver status and complete diagnostic output.
    except subprocess.TimeoutExpired as exc: log=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '');log+='\nCONTACT_TIMEOUT_240_SECONDS\n';returncode=-999 # Retain a real timeout as failed evidence without calling it convergence.
    (folder/'solver.log').write_text(log);receipt={'case':name,'returncode':returncode,'elapsed_s':time.monotonic()-start,'job_finished':'Job finished' in log,'error_marker':'*ERROR' in log,'solver_wrapper':str(CCX),'solver_wrapper_sha256':sha(CCX),'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='receipt.json'}} # Fingerprint raw outputs without a circular receipt self-hash.
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['case','returncode','elapsed_s','job_finished','error_marker']}),flush=True) # Expose a short actual status for monitoring.
    return receipt # Keep convergence decisions separate from physical validation.
if __name__=='__main__': # Support a complete native solve from the command line.
    parser=argparse.ArgumentParser();parser.add_argument('name');parser.add_argument('--pressure',type=float,default=10.);parser.add_argument('--mu',type=float,default=.3);parser.add_argument('--nx',type=int,default=4);parser.add_argument('--ny',type=int,default=2);parser.add_argument('--nz',type=int,default=1);parser.add_argument('--normal-stiffness',type=float,default=1.e6);parser.add_argument('--stick-stiffness',type=float,default=1.e4);args=parser.parse_args() # Make every specimen parameter reviewable and repeatable.
    solve(args.name,args.pressure,args.mu,args.nx,args.ny,args.nz,args.normal_stiffness,args.stick_stiffness) # Run only the explicitly named case.
