from pathlib import Path  # Keep the exact upstream source and the small preprocessing change with the run evidence.
import subprocess, requests, tarfile, io, re, json, hashlib, os  # Build a real solver without modifying element stiffness or engineering inputs.
ROOT=Path(__file__).parent  # Isolate the native build from all historical project solvers.
def build():  # Activate existing native knot kinematics where the input explicitly requests rotations or a rigid connector.
    folder=ROOT/'runtime_joint';folder.mkdir(exist_ok=True);evidence=ROOT/'results/solver_correction';evidence.mkdir(parents=True,exist_ok=True)  # Preserve all original and changed files for source-level review.
    original_url='https://www.dhondt.de/ccx_2.23.src.tar.bz2';response=requests.get(original_url,timeout=120);response.raise_for_status();archive_bytes=response.content  # Obtain the upstream version matching the independently tested executable.
    with tarfile.open(fileobj=io.BytesIO(archive_bytes),mode='r:bz2') as archive:archive.extractall(folder,filter='data')  # Extract official source files rather than any previous engineering model.
    src=next(folder.rglob('gen3dnor.f')).parent;p=src/'gen3dnor.f';original=p.read_text();(evidence/'gen3dnor_upstream.f').write_text(original)  # Preserve the exact upstream preprocessing routine before changing it.
    declaration='      integer, allocatable :: requestedknots(:)\n';original_marker='      logical fixed,composite,beam';patched=original.replace(original_marker,declaration+original_marker,1)  # Allocate a per-node indicator of already-declared physical rotational constraints.
    mark='''      allocate(requestedknots(nkold))
      requestedknots=0
      do j=1,nmpc
         index=ipompc(j)
         do while(index.ne.0)
            node=nodempc(1,index)
            if((node.gt.0).and.(node.le.nkold)) then
               if((nodempc(2,index).gt.3).or.
     &              (labmpc(j)(1:5).eq.'RIGID')) then
                  requestedknots(node)=1
               endif
            endif
            index=nodempc(3,index)
         enddo
      enddo
'''  # Identify source-requested rotations once before generated MPCs enlarge the arrays.
    patched=patched.replace('      nkold=nk','      nkold=nk\n'+mark,1)  # Scan original input constraints without changing their coefficients or supported freedoms.
    knot='''        if((requestedknots(i).eq.1).and.(nexp.eq.1).and.
     &       (nnor.gt.0)) nexp=2
'''  # Select the existing native rigid-section knot representation only for explicitly requested connectors.
    patched=patched.replace('        if(nexp.gt.1) then',knot+'        if(nexp.gt.1) then',1)  # Reuse upstream knotmpc and its finite-rotation tangent rather than introduce a new beam formula.
    if patched==original or 'requestedknots=0' not in patched or 'requestedknots(i).eq.1' not in patched:raise RuntimeError('Upstream preprocessing layout did not match the audited patch')  # Do not silently compile an unrelated or unpatched solver.
    p.write_text(patched);(evidence/'gen3dnor_patched.f').write_text(patched)  # Preserve the exact compiled preprocessing routine.
    import difflib  # Record a minimal source diff that can be reviewed independently.
    (evidence/'preprocessor_only.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),fromfile='upstream/gen3dnor.f',tofile='joint-coordinate/gen3dnor.f')))  # Demonstrate that element matrices and material routines are unchanged.
    commands=[['sudo','apt-get','update','-qq'],['sudo','apt-get','install','-y','gfortran','libspooles-dev','libarpack2-dev','liblapack-dev']]  # Use distribution-maintained native compiler and sparse-eigensolver libraries.
    with (evidence/'build.log').open('w') as log:  # Keep every compiler and link diagnostic.
        for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)  # Surface actual package failures rather than substitute a different solver.
        main=next(src.glob('ccx_2.23.c'));make='''CC=gcc
FC=gfortran
CFLAGS=-O2 -fopenmp -DARCH=\"Linux\" -DSPOOLES -DARPACK -DMATRIXSTORAGE -I/usr/include/spooles
FFLAGS=-O2 -fopenmp -fallow-argument-mismatch
include Makefile.inc
OBJS=$(SCCXF:.f=.o) $(SCCXC:.c=.o)
all: ccx_joint
%.o: %.c
\t$(CC) $(CFLAGS) -c $< -o $@
%.o: %.f
\t$(FC) $(FFLAGS) -c $< -o $@
ccx_joint: ccx_2.23.o $(OBJS)
\t$(FC) -fopenmp -o $@ ccx_2.23.o $(OBJS) -lspooles -larpack -llapack -lblas -lpthread -lm
'''  # Compile unchanged upstream element and nonlinear-solver routines with the explicit preprocessing correction.
        (src/'Makefile.joint').write_text(make);subprocess.run(['make','-f','Makefile.joint','-j4'],cwd=src,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)  # Build the actual native executable and retain compiler evidence.
    exe=(src/'ccx_joint').resolve();wrapper=ROOT/'ccx';wrapper.write_text('#!/bin/sh\n# Run the upstream CCX 2.23 solver with only the documented joint-coordinate preprocessing correction.\nexec "'+str(exe)+'" "$@" # Preserve all native element, nonlinear and modal routines.\n');wrapper.chmod(0o755)  # Use the new build only after successful compilation.
    info={'upstream_url':original_url,'upstream_archive_sha256':hashlib.sha256(archive_bytes).hexdigest(),'original_preprocessor_sha256':hashlib.sha256(original.encode()).hexdigest(),'patched_preprocessor_sha256':hashlib.sha256(patched.encode()).hexdigest(),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'scope':'Activate existing native rotational knots at input-declared rotational equations and rigid-body connectors; no element, material, load, stiffness or mass formula changed.'}  # State the exact numerical implementation change and its boundary.
    (evidence/'provenance.json').write_text(json.dumps(info,indent=2));print('NATIVE_JOINT_SOLVER',json.dumps(info),flush=True)  # Publish actual compiled-binary provenance, not a claim about bridge correctness.
    return exe  # Return a runnable, source-auditable native solver.
