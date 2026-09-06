from pathlib import Path  # Keep this research run separate from previous diagnostic evidence.
import json  # Preserve actual incremental case outcomes.
import diagnose_loaded_connections as native  # Reuse fresh native invocation and result parsing without altering production inputs.
from research_floor_cases import cases as floor_cases  # Test source-drawing corrections and section interpolation separately.
from torsion_probe_cases import cases as torsion_cases  # Check the previously untested beam-axis torsion path.
def execute():  # Execute bounded causal probes before considering another full-bridge run.
    native.OUT=Path(__file__).parent/'results/connection_research'; native.OUT.mkdir(parents=True,exist_ok=True); report={'scope':'Causal local native research only; no full-bridge model replaced or rotational restraint added.','cases':{}}  # Explicitly distinguish fixture evidence from a completed fourteen-mode bridge result.
    for name,factory in torsion_cases()+floor_cases():  # Solve the independent torsion controls before corrected floor variants.
        report['cases'][name]=native.solve_case(name,factory); (native.OUT/'summary.json').write_text(json.dumps(report,indent=2))  # Save each actual success or failure immediately.
    report['native_completed']=sum(r['completed'] for r in report['cases'].values()); report['native_failed']=len(report['cases'])-report['native_completed']; (native.OUT/'summary.json').write_text(json.dumps(report,indent=2)); print('CONNECTION_RESEARCH_COMPLETE',json.dumps({'completed':report['native_completed'],'failed':report['native_failed']}),flush=True)  # A completed workflow never implies that every physical test converged.
if __name__=='__main__':execute()  # Run the concrete research when invoked by its dedicated workflow.
