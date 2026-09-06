from pathlib import Path  # Preserve this causal mesh study separately from the first ten native probes.
import json  # Record genuine successful and failed native outcomes without replacing earlier evidence.
import diagnose_loaded_connections as native  # Reuse the already audited invocation and physical-vector parsing.
from research_floor_mesh_cases import cases  # Compare identical physical clips and support spans across mesh and connection choices.
def execute():  # Determine whether mesh resolution or the section connection controls the observed failure.
    native.OUT=Path(__file__).parent/'results/connection_mesh_research'; native.OUT.mkdir(parents=True,exist_ok=True); report={'scope':'Local floor mesh and connection study; no production supports, materials or source inputs changed.','cases':{}}  # Distinguish fixture convergence from complete bridge equilibrium and stability.
    for name,factory in cases():  # Run only the bounded second-stage discriminating cases.
        report['cases'][name]=native.solve_case(name,factory); (native.OUT/'summary.json').write_text(json.dumps(report,indent=2))  # Preserve each genuine outcome before the next attempt.
    report['native_completed']=sum(r['completed'] for r in report['cases'].values()); report['native_failed']=len(report['cases'])-report['native_completed']; (native.OUT/'summary.json').write_text(json.dumps(report,indent=2)); print('MESH_RESEARCH_COMPLETE',json.dumps({'completed':report['native_completed'],'failed':report['native_failed']}),flush=True)  # Workflow completion is not a claim that all cases converged.
if __name__=='__main__':execute()  # Execute the concrete isolated research only on explicit script invocation.
