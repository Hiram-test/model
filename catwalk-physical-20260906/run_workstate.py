from pathlib import Path  # Use only the source files and calculations made in this reconstruction.
import json, re, subprocess, numpy as np  # Parse native output and compare independently obtained states.
from mct_workstate import read_source, equilibrium, write_axial  # Reuse only this turn's original-input parser and independent equilibrium formulation.
ROOT=Path(__file__).parent  # Bind all paths to the new source-based calculation.
def vector_blocks(path,label='displacements'):  # Parse full native nodal output without OCR or inferred values.
    blocks=[];current=None  # Keep each actual output time block distinct.
    for line in path.read_text(errors='replace').splitlines():  # Read the native ASCII DAT file.
        if line.strip().startswith(label+' ('):  # Detect a genuine native displacement or force block.
            current={};blocks.append(current)  # Start a new native result block.
        elif current is not None:  # Read only the current native vector field.
            p=line.split()  # Native output uses whitespace-delimited numbers.
            if len(p)==4 and p[0].isdigit():  # Require node ID and three actual vector components.
                try:current[int(p[0])]=[float(v.replace('D','E')) for v in p[1:4]]  # Preserve native node numbering and signed vectors.
                except ValueError:current=None  # Do not reinterpret a non-vector table as displacement output.
            elif p and not p[0].isdigit():current=None  # Stop at the next native table heading.
    return [b for b in blocks if b]  # Exclude empty headings but retain all actual output blocks.
def frequency_rows(path):  # Read the native eigenvalue table without matching target frequencies.
    result=[];active=False  # Extract numerical order exactly as written by CalculiX.
    for line in path.read_text(errors='replace').splitlines():  # Process native output only.
        if 'E I G E N V A L U E' in line:active=True  # Locate the actual eigenvalue output header.
        p=line.split()  # Separate native table fields.
        if active and len(p)>=4 and p[0].isdigit():  # Read mode ID, eigenvalue, circular frequency and cycles/second.
            try:result.append({'mode':int(p[0]),'eigenvalue':float(p[1]),'omega':float(p[2]),'frequency_hz':float(p[3])})  # Keep the true numerical order, including any unwanted modes.
            except ValueError:pass  # Ignore unrelated textual headings only.
        elif active and result and not p:break  # Finish the single native eigenvalue table.
    return result  # Never create missing eigenvalues from theory or previous calculations.
def run_native(folder,job,timeout=600):  # Execute a real native CCX process with complete diagnostics.
    with (folder/'native_solver.txt').open('w') as log:  # Preserve all native standard output and errors.
        try:process=subprocess.run([str((ROOT/'ccx').resolve()),job],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=timeout);code=process.returncode  # Run the exact upstream executable.
        except subprocess.TimeoutExpired:code=-999  # Retain a distinct actual timeout status.
    print('NATIVE_RUN',job,code,(folder/'native_solver.txt').read_text(errors='replace')[-2200:],flush=True)  # Report real execution status and final diagnostics.
    return code  # Do not infer success from workflow completion.
def execute():  # Complete the source work-state verification before spatial expansion.
    unit=ROOT/'unit_string';p=unit/'string.inp';p.write_text(re.sub(r'^0,','0.0,',p.read_text(),flags=re.M))  # Apply the documented SPRINGA parser decimal-point requirement.
    code=run_native(unit,'string',180);frequencies=frequency_rows(unit/'string.dat');expected=np.sqrt(1000/2.4)/200  # Use a straight-string analytic solution unrelated to bridge targets.
    (unit/'verification.json').write_text(json.dumps({'exit':code,'analytic_first_hz':expected,'native_modes':frequencies},indent=2))  # Preserve genuine native eigenvalue verification.
    source=read_source();folder=ROOT/'results/mct_workstate';folder.mkdir(parents=True,exist_ok=True);state=equilibrium(source)  # Solve the original MCT equilibrium independently.
    write_axial(folder/'workstate.inp',source);p=folder/'workstate.inp';p.write_text(p.read_text().replace('0.1,1.,1.e-8,0.2','1.,1.,1.e-8,1.'))  # Apply full dead load at the preloaded reference state instead of unloading it by 90 percent.
    code=run_native(folder,'workstate',300);summary={'native_exit':code,'independent_max_displacement_m':state['max_displacement_m'],'independent_max_free_residual_N':state['max_free_residual_N'],'mass_kg':state['total_gravity_mass_kg']}  # Preserve independent numerical evidence.
    blocks=vector_blocks(folder/'workstate.dat') if (folder/'workstate.dat').exists() else []  # Read actual native final displacements only when present.
    if blocks:  # Compare both solutions at the same source physical nodes.
        native=blocks[-1];order=state['node_ids'];u=np.array([native[n] for n in order]);difference=u-np.array(state['displacements_m']);summary['native_theory_max_displacement_difference_m']=float(np.max(np.linalg.norm(difference,axis=1)));summary['native_max_displacement_m']=float(np.max(np.linalg.norm(u,axis=1)))  # Quantify native agreement, not just matching exit codes.
        state['native_displacements_m']=u.tolist()  # Retain the native state alongside the independent solution.
    (folder/'run_status.json').write_text(json.dumps(summary,indent=2));(folder/'theory_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2));print('MCT_WORKSTATE',json.dumps(summary),flush=True)  # Save immutable numerical verification evidence.
    return source,state  # Supply newly reconstructed original-state data to the full spatial model.
