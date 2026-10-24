import os # Bound computational thread use before importing numerical libraries.
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1' # Avoid oversubscribing concurrent dataset calculations.
from run import * # Reuse exact physical model and source identities.
def mesh_checks(): # Compare genuine independently meshed physical problems.
    reports=[] # Preserve all successive refinement levels.
    for family in FAMILIES: # Check every structural family separately.
        previous=json.loads((RUN/'cases'/f'{family}_reference/receipt.json').read_text()); values=[{'factor':1.,'receipt':previous}] # Keep original mesh reference unchanged.
        for factor in [.7,.5]: # Refine actual geometry rather than rescale a plotted result.
            base=mesh_family(family,factor); identity=f'{family}_mesh_{factor:g}'; current=solve_case(base,[1,1,1,1,1,.5],identity) # Solve new quadratic mesh with identical physical traction.
            displacement=abs(current['max_displacement_mm']-previous['max_displacement_mm'])/max(current['max_displacement_mm'],1e-15); energy=abs(current['strain_energy_Nmm']-previous['strain_energy_Nmm'])/max(current['strain_energy_Nmm'],1e-15) # Measure physically comparable response convergence.
            values.append({'factor':factor,'displacement_change':displacement,'energy_change':energy,'receipt':current}); previous=current # Retain complete refinement sequence.
            print(family,factor,displacement,energy,current['status'],flush=True) # Expose actual evidence while calculations continue.
        reports.append({'family':family,'levels':values,'fine_pair_pass':values[-1]['displacement_change']<.05 and values[-1]['energy_change']<.05,'training_mesh_vs_finest_displacement':abs(values[0]['receipt']['max_displacement_mm']-values[-1]['receipt']['max_displacement_mm'])/values[-1]['receipt']['max_displacement_mm']}) # Distinguish reference mesh convergence from training mesh fidelity.
        write_json(RUN/'mesh_convergence.json',reports) # Checkpoint each completed family independently.
def nonlinear_checks(): # Probe actual geometric nonlinearity without using linear residuals as nonlinear proof.
    results=[] # Keep each native continuation record.
    for family in FAMILIES: # Test all accepted local reference models.
        p=[1,1,1,1,5.,.5]; result=solve_case(load_base(family),p,family+'_nlgeom_probe',nonlinear=True) # Run five-times-load nonlinear native solve with declared increment bounds.
        result['status']='NATIVE_NONLINEAR_COMPLETED_UNQUALIFIED' if result['ccx']['completed'] else 'NUMERICAL_FAILURE'; result['note']='Linear companion is only a comparison; no matching finite-strain residual adapter or nonlinear training label.' # Keep nonlinear physical qualification separate from linear stiffness checks.
        write_json(RUN/'cases'/result['id']/'receipt.json',result); results.append(result); write_json(RUN/'nonlinear_probes.json',results); print(result['id'],result['status'],flush=True) # Preserve native solver results and explicit adapter boundary.
if __name__=='__main__': # Execute a selected numerical verification suite.
    import argparse # Parse reproducible verification mode.
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['mesh','nonlinear']); args=parser.parse_args() # Select independent evidence task.
    mesh_checks() if args.mode=='mesh' else nonlinear_checks() # Run requested solver-backed checks.
