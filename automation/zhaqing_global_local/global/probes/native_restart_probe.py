#!/usr/bin/env python3  # Verify native database restart against uninterrupted finite-element continuation.
import argparse  # Select the exact native fixture and evidence destination.
import hashlib  # Bind observed evidence to the executed source bytes.
import json  # Preserve all native return codes and state comparisons.
import os  # Select an explicitly identified native runtime for serialization comparisons.
from pathlib import Path  # Keep checkpoint files and reports in the requested result namespace.
import numpy as np  # Compare actual native fields numerically without creating plots.
if os.environ.get('ZHAQING_NATIVE_BACKEND')=='xara':  # Exercise the alternative native Tcl-backed engine without loading two incompatible solver runtimes.
    import opensees.openseespy as ops  # Preserve the same physical API while testing the recovered Tcl8 runtime.
else:  # Keep the original bridge backend as the explicit default control.
    import openseespy.opensees as ops  # Exercise the compiled engine used by the bridge rather than a surrogate.
def build(kind):  # Build a stable small fixture containing the exact relevant native element families.
    ops.wipe()  # Begin with a genuinely empty native domain.
    ops.model('basic','-ndm',3,'-ndf',6)  # Keep all physical three-dimensional translations and rotations.
    coordinates={1:(0.,0.,0.),2:(1000.,0.,0.),3:(1000.,500.,0.),4:(0.,500.,0.),5:(2000.,0.,100.),6:(2000.,200.,100.),7:(3000.,500.,1000.)}  # Use a shell panel, attached beam, eccentric load point, and prestressed cable anchor.
    for tag,coordinate in coordinates.items():  # Instantiate every explicit physical fixture node.
        ops.node(tag,*coordinate)  # Retain the declared millimetre geometry.
        ops.mass(tag,.01,.01,.01,0.,0.,0.)  # Preserve nonzero translational inertia and no artificial rotational mass.
    for tag in (1,4,7):  # Fix only real fixture supports and the cable anchor.
        ops.fix(tag,1,1,1,1,1,1)  # Remove all six degrees at the corresponding prescribed support.
    ops.geomTransf('Corotational',1,0.,0.,1.)  # Use the original bridge's native large-rotation beam transformation.
    ops.element('elasticBeamColumn',2,2,5,8000.,200000.,200000./2.6,1.e6,2.e8,1.e8,1)  # Include the actual bridge beam formulation and full internal state.
    if kind=='beam':  # Provide a serialization control without any shell element.
        ops.element('elasticBeamColumn',1,1,2,8000.,200000.,200000./2.6,1.e6,2.e8,1.e8,1)  # Restrain the loaded beam through a second full three-dimensional member.
        ops.fix(3,1,1,1,1,1,1)  # Remove the unused shell-only control node explicitly.
    else:  # Include the exact nonlinear shell implementation under investigation.
        ops.section('ElasticMembranePlateSection',1,200000.,.3,10.,0.)  # Match the detailed bridge's elastic steel plate constitutive family.
        options=['-corotational'] if kind=='ASDShellQ4' else []  # Activate actual large-rotation ASD behavior when selected.
        ops.element(kind,1,1,2,3,4,1,*options)  # Preserve native shell integration-point and geometric histories.
    ops.rigidLink('beam',5,6)  # Exercise restoration of the eccentric six-degree multipoint constraint.
    ops.uniaxialMaterial('Elastic',1,195000.)  # Use the native cable steel elastic constituent.
    ops.uniaxialMaterial('InitStressMaterial',2,1,100.)  # Include actual initial-stress wrapper state used by the detailed bridge.
    ops.element('corotTruss',3,5,7,200.,2,'-doRayleigh',1)  # Preserve large-displacement cable force and mass-damping participation.
    ops.timeSeries('Linear',1)  # Define the permanent static loading path.
    ops.pattern('Plain',1,1)  # Keep an independent native permanent load pattern.
    ops.load(6,0.,100.,-300.,0.,0.,0.)  # Apply nontrivial forces at the real eccentric loading point.
    ops.constraints('Transformation')  # Enforce native rigid-arm constraints exactly as the bridge does.
    ops.numberer('RCM')  # Reorder complete equations without reducing physical degrees.
    ops.system('UmfPack')  # Solve the full sparse fixture system.
    ops.test('NormDispIncr',1.e-10,100,0)  # Require tightly converged fixture increments before testing serialization.
    ops.algorithm('Newton')  # Use full native equilibrium iterations at each declared increment.
    ops.integrator('LoadControl',.1)  # Ramp the full permanent load over ten physical increments.
    ops.analysis('Static')  # Establish nonzero static internal force and geometry history.
    code=int(ops.analyze(10))  # Preserve the actual native convergence code.
    if code!=0:  # Exclude unresolved static fixtures from any restart claim.
        raise RuntimeError(f'fixture static initialization failed: {code}')  # Expose the true numerical failure.
    ops.loadConst('-time',0.)  # Freeze actual permanent loads while resetting only the dynamic clock.
    ops.timeSeries('Path',2,'-dt',.01,'-values',0.,.2,.5,1.,.3,-.8,-1.,-.4,.2,.7,.4,-.3,0.,.1,.2,-.1,0.,0.,0.)  # Include a nonconstant future native time-series history that must survive restoration.
    ops.pattern('Plain',2,2)  # Add an independently varying wind-like force pattern.
    ops.load(6,0.,1000.,-400.,200.,0.,0.)  # Exercise all retained geometric and eccentric load couplings.
    ops.rayleigh(.02,0.,0.,0.)  # Include the same explicit mass-proportional damping law as the detailed bridge.
    configure_transient()  # Recreate only analysis machinery while retaining the solved model domain.
def configure_transient():  # Rebuild nonserialized analysis objects for both continuous and restarted execution.
    ops.wipeAnalysis()  # Preserve the physical domain, loads, materials, and committed state.
    ops.constraints('Transformation')  # Rebuild the identical actual multipoint constraint handler.
    ops.numberer('RCM')  # Apply the same full-equation numbering on both paths.
    ops.system('UmfPack')  # Use the identical complete sparse native solver.
    ops.test('NormDispIncr',1.e-11,100,0)  # Keep identical strict native nonlinear termination criteria.
    ops.algorithm('Newton')  # Preserve the nonlinear update algorithm on continuation.
    ops.integrator('Newmark',.5,.25)  # Reinitialize from restored committed displacement, velocity, and acceleration.
    ops.analysis('Transient')  # Create a fresh transient analysis over the existing native domain.
def snapshot():  # Capture the complete small fixture state available through the native public API.
    nodes=sorted(map(int,ops.getNodeTags()))  # Preserve all actual physical node identities.
    elements=sorted(map(int,ops.getEleTags()))  # Preserve all actual physical element identities.
    return {'time':float(ops.getTime()),'nodes':nodes,'elements':elements,'coordinates':[ops.nodeCoord(n) for n in nodes],'displacement':[ops.nodeDisp(n) for n in nodes],'velocity':[ops.nodeVel(n) for n in nodes],'acceleration':[ops.nodeAccel(n) for n in nodes],'mass':[ops.nodeMass(n) for n in nodes],'element_forces':{str(e):ops.eleForce(e) for e in elements},'cable_stress':ops.eleResponse(3,'material','stress'),'cable_strain':ops.eleResponse(3,'material','strain'),'load_factors':[ops.getLoadFactor(1),ops.getLoadFactor(2)]}  # Include material-wrapper response and both permanent and future load histories.
def compare(expected,actual):  # Evaluate physical state preservation instead of accepting an exit code alone.
    tolerances={'time':1.e-12,'coordinates':1.e-12,'displacement':1.e-9,'velocity':1.e-9,'acceleration':1.e-7,'mass':1.e-15,'cable_stress':1.e-8,'cable_strain':1.e-12,'load_factors':1.e-12}  # Declare quantity-specific absolute tolerances in native N-mm-tonne units.
    differences={}  # Preserve the maximum observed discrepancy of each distinct physical quantity.
    for key,tolerance in tolerances.items():  # Compare every exposed physical state category.
        left,right=np.asarray(expected[key],dtype=float),np.asarray(actual[key],dtype=float)  # Keep original native numeric values without rounding.
        error=float(np.max(np.abs(left-right))) if left.shape==right.shape and left.size else (0. if left.shape==right.shape else float('inf'))  # Reject missing or reshaped state instead of broadcasting it.
        differences[key]={'max_abs':error if np.isfinite(error) else None,'absolute_tolerance':tolerance,'passed':bool(np.isfinite(error) and error<=tolerance)}  # Preserve invalid or missing states as JSON-safe failed comparisons.
    identities=expected['nodes']==actual['nodes'] and expected['elements']==actual['elements']  # Require unchanged native mesh identities after restore.
    same_forces=set(expected['element_forces'])==set(actual['element_forces'])  # Reject absent or added native physical elements.
    same_shapes=same_forces and all(np.asarray(expected['element_forces'][e]).shape==np.asarray(actual['element_forces'][e]).shape for e in expected['element_forces'])  # Reject element response truncation before array subtraction can broadcast it.
    force_error=max((float(np.max(np.abs(np.asarray(expected['element_forces'][e])-np.asarray(actual['element_forces'][e])))) for e in expected['element_forces']),default=0.) if same_shapes else float('inf')  # Include all shell, beam, and prestressed-cable resisting actions.
    differences['element_forces']={'max_abs':force_error if np.isfinite(force_error) else None,'absolute_tolerance':1.e-5,'passed':bool(np.isfinite(force_error) and force_error<=1.e-5)}  # Keep missing or nonfinite force state as an explicit JSON-safe failure.
    return {'passed':bool(identities and all(value['passed'] for value in differences.values())),'identities_equal':identities,'quantities':differences}  # Require all physical checks to pass together.
def run(kind,directory):  # Execute independent continuous and restarted branches of the same actual native history.
    directory.mkdir(parents=True,exist_ok=True)  # Create the explicit checkpoint and evidence directory.
    report={'status':'FAILED','scope':'SMALL_NATIVE_RESTART_FIXTURE_NOT_FULL_BRIDGE_VALIDATION','fixture':kind,'native_backend':os.environ.get('ZHAQING_NATIVE_BACKEND','openseespy'),'native_version':ops.version(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'full_bridge_restart_qualified':False}  # Keep diagnostic qualification distinct from detailed-bridge evidence.
    try:  # Preserve exact failure stage and state without inventing a successful checkpoint.
        report['stage']='build'  # Identify any native element or initialization failure.
        build(kind)  # Construct and equilibrate the actual native element mixture.
        report['stage']='transient_before_save'  # Separate initial dynamics from file serialization.
        if int(ops.analyze(4,.01))!=0:  # Require nonzero velocity and acceleration before saving the domain.
            raise RuntimeError('fixture transient initialization failed')  # Do not test restore from a failed trial state.
        checkpoint=snapshot()  # Freeze every observed committed physical state before serialization.
        report['checkpoint_state']=checkpoint  # Preserve evidence of actual motion and nonzero prestress.
        report['stage']='save'  # Mark native serialization as a distinct evidence boundary.
        prefix=directory/'native_state'  # Place all native database fragments in a portable isolated directory.
        ops.database('File',str(prefix))  # Use the engine's real domain serialization rather than rebuilding from nodal fields.
        report['save_return']=ops.save(19)  # Preserve the actual save API result even when it reports no numeric status.
        continuous=[]  # Record every future frame of the uninterrupted physical history.
        for unused in range(12):  # Complete a declared subsequent history that includes load reversal.
            if int(ops.analyze(1,.01))!=0:  # Reject any continuous-branch native failure.
                raise RuntimeError('continuous branch failed')  # Prevent a failed reference from qualifying restart.
            continuous.append(snapshot())  # Preserve all actual state quantities for each committed future frame.
        report['continuous_final_state']=continuous[-1]  # Save nontrivial final response for independent inspection.
        ops.wipe()  # Destroy the entire original domain so restore cannot reuse surviving physical state.
        report['empty_domain_before_restore']=len(ops.getNodeTags())==0 and len(ops.getEleTags())==0  # Prove the restored path starts without the old mesh or elements.
        report['stage']='restore'  # Identify failures in the engine's actual receiver and object broker.
        ops.database('File',str(prefix))  # Reopen the actual persisted native fragments after domain destruction.
        report['restore_return']=ops.restore(19)  # Require real native reconstruction of materials, constraints, loads, and elements.
        report['checkpoint_comparison']=compare(checkpoint,snapshot())  # Test original committed state before any corrective solve can hide corruption.
        report['stage']='continued_transient'  # Identify new failure after successful domain restoration.
        configure_transient()  # Recreate only necessary analysis machinery from the restored domain.
        comparisons=[]  # Preserve every post-restart frame comparison rather than only the final response.
        for expected in continuous:  # Apply exactly the same known future native load history.
            if int(ops.analyze(1,.01))!=0:  # Reject native divergence on the restored path.
                raise RuntimeError('restored branch failed')  # Keep failed restart histories out of durable execution.
            comparisons.append(compare(expected,snapshot()))  # Check displacement, velocity, acceleration, material, and forces at every frame.
        report['continuation_comparisons']=comparisons  # Preserve measured discrepancies of the complete restarted history.
        report['status']='PASSED_FIXTURE' if report['checkpoint_comparison']['passed'] and all(item['passed'] for item in comparisons) else 'FAILED_STATE_EQUIVALENCE'  # Do not promote a successful API return into a physical qualification.
        report['stage']='complete'  # Mark only an actually finished comparison as complete.
    except Exception as error:  # Preserve reproducible unsupported API, material, or native file failures.
        report['error']=repr(error)  # Keep exact failure information available to the campaign author.
    finally:  # Always persist the diagnostic receipt even when native Python raises an error.
        report['database_files']=[{'name':p.name,'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(directory.glob('native_state*')) if p.is_file()]  # Bind every persisted domain fragment to immutable bytes.
        (directory/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')  # Save an auditable standalone diagnostic without plotting or synthetic fields.
        ops.wipe()  # Release only this diagnostic process's native domain.
    return report  # Allow command-line and integration tests to inspect truthful qualification.
if __name__=='__main__':  # Keep direct execution independent from test importing.
    parser=argparse.ArgumentParser()  # Define explicit native experiment inputs.
    parser.add_argument('--fixture',choices=['beam','ShellNLDKGQ','ASDShellQ4'],required=True)  # Prevent accidental substitution of the intended element family.
    parser.add_argument('--output',type=Path,required=True)  # Require a persistent evidence destination.
    args=parser.parse_args()  # Parse exactly the declared reproducible experiment.
    result=run(args.fixture,args.output)  # Execute the complete save, destroy, restore, and continuation comparison.
    print(json.dumps({key:result.get(key) for key in ('status','fixture','native_version','stage','error','full_bridge_restart_qualified')},indent=2))  # Expose concise truthful evidence to orchestration logs.
    raise SystemExit(0 if result['status']=='PASSED_FIXTURE' else 1)  # Return failure when any actual state or trajectory check fails.
