from pathlib import Path  # Use only original inputs and newly executed calculations in this reconstruction.
import json, re, subprocess, os, time, hashlib, numpy as np  # Preserve native execution identity and independently compare actual nodal results.
from mct_workstate import read_source, equilibrium, write_axial  # Reuse this turn's original-MCT parser and independent nonlinear mechanics.
ROOT=Path(__file__).parent  # Keep native inputs and results on the reconstruction branch.
def vector_blocks(path,label='displacements'):  # Read actual native Cartesian nodal vectors.
    blocks=[];current=None  # Keep every time or mode block separate.
    for line in path.read_text(errors='replace').splitlines():  # Parse only the current native DAT file.
        if line.strip().startswith(label+' ('):current={};blocks.append(current)  # Start a genuine native vector-output block.
        elif current is not None:  # Read only node and vector rows under that heading.
            p=line.split()  # Native tables are whitespace delimited.
            if len(p)==4 and p[0].isdigit():  # Require a real node number and three vector components.
                try:current[int(p[0])]=[float(v.replace('D','E')) for v in p[1:4]]  # Preserve signed physical values and native node IDs.
                except ValueError:current=None  # Do not reinterpret another native table as displacement.
            elif p and not p[0].isdigit():current=None  # Stop at the next non-vector heading.
    return [b for b in blocks if b]  # Keep only fields actually written by the native solver.
def frequency_rows(path):  # Read the original numerical order of the native eigenvalue table.
    result=[];active=False  # Do not match or sort against target frequencies.
    for line in path.read_text(errors='replace').splitlines():  # Inspect actual native text output.
        if 'E I G E N V A L U E' in line:active=True  # Identify the genuine CalculiX eigenvalue heading.
        p=line.split()  # Read native table fields directly.
        if active and len(p)>=4 and p[0].isdigit():  # Require the complete mode, eigenvalue and frequency row.
            try:result.append({'mode':int(p[0]),'eigenvalue':float(p[1]),'omega':float(p[2]),'frequency_hz':float(p[3])})  # Retain every root, including unwanted low modes.
            except ValueError:pass  # Ignore textual headings, not numerical mismatches.
        elif active and result and not p:break  # End this native eigenvalue table.
    return result  # Never fill missing native eigenvalues with theory or older files.
def run_native(folder,job,timeout=600):  # Execute real CCX after removing output files from earlier invocations.
    for suffix in ('.dat','.frd','.sta','.cvg','.eig','.12d','.rout','.out','.err'):  # Avoid stale output when preprocessing fails before opening a result file.
        p=folder/(job+suffix)  # Restrict deletion to generated output for this exact job name.
        if p.exists():p.unlink()  # Preserve the original INP while removing only superseded run output.
    started=time.time();wrapper=(ROOT/'ccx').resolve();input_path=folder/(job+'.inp');info={'job':job,'workflow_run':os.environ.get('GITHUB_RUN_ID'),'source_commit':os.environ.get('GITHUB_SHA'),'start_unix':started,'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'solver_launcher':wrapper.read_text()}  # Bind numerical evidence to exact input bytes and the executable invocation.
    with (folder/'native_solver.txt').open('w') as log:  # Preserve complete standard output and diagnostic errors.
        process=subprocess.Popen([str(wrapper),job],cwd=folder,stdout=log,stderr=subprocess.STDOUT)  # Execute the same native solver while exposing progress before a possible runner interruption.
        while True:  # Keep the existing native timeout while periodically preserving current solver diagnostics.
            remaining=timeout-(time.time()-started)  # Measure the actual elapsed native invocation time.
            if remaining<=0:process.kill();process.wait();code=-999;break  # Preserve the existing timeout status and stop only this native process.
            try:code=process.wait(timeout=min(20.,remaining));break  # Return the real native exit code as soon as the process completes.
            except subprocess.TimeoutExpired:  # A heartbeat is observational and does not change solver inputs or tolerances.
                with (folder/'native_solver.txt').open('rb') as current:current.seek(max(0,(folder/'native_solver.txt').stat().st_size-2200));tail=current.read().decode(errors='replace')  # Read only the current log tail without loading a growing solver log into memory.
                status_path=Path('/proc')/str(process.pid)/'status';memory=status_path.read_text() if status_path.exists() else ''  # Inspect this exact native process without searching or exposing unrelated processes.
                memory_lines=[line for line in memory.splitlines() if line.startswith(('VmRSS:','VmPeak:','VmSize:'))]  # Record native resident and virtual memory to diagnose resource interruption.
                available=[line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))]  # Record the execution machine's available physical memory.
                info['heartbeat']={'elapsed_seconds':time.time()-started,'native_memory':memory_lines,'machine_memory':available};(folder/'invocation.json').write_text(json.dumps(info,indent=2))  # Preserve a truthful incomplete invocation if the machine stops before native completion.
                print('NATIVE_HEARTBEAT',job,json.dumps(info['heartbeat']),tail,flush=True)  # Put current solver diagnostics into durable workflow logs before final artifact upload.
    info['exit_code']=code;info['elapsed_seconds']=time.time()-started;info['native_outputs']={p.name:{'bytes':p.stat().st_size,'modified_unix':p.stat().st_mtime} for p in folder.glob(job+'.*') if p.suffix!='.inp'}  # Preserve output freshness and process status.
    (folder/'invocation.json').write_text(json.dumps(info,indent=2));print('NATIVE_RUN',job,code,(folder/'native_solver.txt').read_text(errors='replace')[-2200:],flush=True)  # Report actual native status rather than a workflow completion label.
    return code  # Keep scientific interpretation separate from execution status.
def execute():  # Complete the original source-state check before spatial expansion.
    unit=ROOT/'unit_string';p=unit/'string.inp';p.write_text(re.sub(r'^0,','0.0,',p.read_text(),flags=re.M))  # Apply the native SPRINGA parser's decimal-point requirement without changing its force law.
    code=run_native(unit,'string',180);frequencies=frequency_rows(unit/'string.dat') if (unit/'string.dat').exists() else [];expected=np.sqrt(1000/2.4)/200  # Compare against an unrelated analytic straight-string problem.
    (unit/'verification.json').write_text(json.dumps({'exit':code,'analytic_first_hz':expected,'native_modes':frequencies},indent=2))  # Preserve actual native eigenvalue verification.
    source=read_source();folder=ROOT/'results/mct_workstate';folder.mkdir(parents=True,exist_ok=True);state=equilibrium(source)  # Independently solve the original MCT at its full permanent-load state.
    write_axial(folder/'workstate.inp',source);p=folder/'workstate.inp';p.write_text(p.read_text().replace('0.1,1.,1.e-8,0.2','1.,1.,1.e-8,1.'))  # Apply full dead load to an already preloaded reference configuration.
    code=run_native(folder,'workstate',300);summary={'native_exit':code,'independent_max_displacement_m':state['max_displacement_m'],'independent_max_free_residual_N':state['max_free_residual_N'],'mass_kg':state['total_gravity_mass_kg']}  # Preserve actual source-state quantities.
    blocks=vector_blocks(folder/'workstate.dat') if (folder/'workstate.dat').exists() else []  # Use only fresh native output from this invocation.
    if code==0 and blocks:  # Compare complete successful native equilibrium with the independent solution.
        native=blocks[-1];order=state['node_ids'];u=np.array([native[n] for n in order]);difference=u-np.array(state['displacements_m']);summary['native_theory_max_displacement_difference_m']=float(np.max(np.linalg.norm(difference,axis=1)));summary['native_max_displacement_m']=float(np.max(np.linalg.norm(u,axis=1)));state['native_displacements_m']=u.tolist()  # Compare physical node vectors rather than frequencies or exit codes alone.
    (folder/'run_status.json').write_text(json.dumps(summary,indent=2));(folder/'theory_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2));print('MCT_WORKSTATE',json.dumps(summary),flush=True)  # Save verifiable source-state evidence.
    if code!=0:raise RuntimeError('Original MCT native equilibrium did not complete; consult its fresh invocation and native solver log')  # Do not substitute an older successful source state.
    return source,state  # Supply only this invocation's newly computed original-state data to the full model.
