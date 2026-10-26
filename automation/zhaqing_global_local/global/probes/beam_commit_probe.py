#!/usr/bin/env python3  # Compare native postcommit equilibrium for full 3D beam and rigid-arm fixtures without altering the bridge model.
import argparse,json,math,sys # Select an explicit native runtime and preserve observed diagnostic results.
from pathlib import Path # Store evidence beside independently executed solver fixtures.
import numpy as np # Assemble actual native force, inertia, and damping balance without plotting.
def run(ops,transformation,with_arm): # Exercise one native beam geometry transformation and optional actual multipoint constraint.
    ops.wipe() # Isolate native domains between physical fixture variants.
    ops.model('basic','-ndm',3,'-ndf',6) # Preserve all three translations and three rotations at every beam node.
    count,length=12,2696. # Use an actual bridge-girder-scale length and explicit finite-element segments.
    nodes=list(range(1,count+2)) # Preserve stable identities for all physical beam mesh points.
    coordinates={n:np.array([(n-1)*length/count,0.,0.]) for n in nodes} # Define the complete straight reference beam geometry.
    for n,p in coordinates.items(): # Instantiate every physical mesh point without modal reduction.
        ops.node(n,*p.tolist()) # Pass real millimetre coordinates to the native engine.
        ops.mass(n,.01,.01,.01,0.,0.,0.) # Supply known physical lumped mass for a subsequent transient balance test.
    ops.fix(1,1,1,1,1,1,1) # Apply one actual fixed cantilever support.
    ops.geomTransf(transformation,1,0.,0.,1.) # Select either original or corrected full large-rotation coordinates explicitly.
    connectivity={} # Preserve exact native element incidence for independent force assembly.
    for tag in range(1,count+1): # Retain all actual beam elements in the fixture.
        conn=[tag,tag+1] # Connect adjacent physical beam nodes.
        ops.element('elasticBeamColumn',tag,*conn,20000.,200000.,200000./2.6,1.e6,3.e8,2.e8,1) # Keep actual axial, bending, and torsional stiffness with native corotational geometry.
        connectivity[tag]=conn # Record source association for the independent residual calculation.
    master,slave=count+1,1000 # Reserve separate actual rigid-arm identities.
    if with_arm: # Include the exact linearized beam-arm constraint used in the detailed bridge model.
        coordinates[slave]=coordinates[master]+np.array([0.,200.,100.]) # Preserve a nonzero physical three-dimensional connection offset.
        nodes.append(slave) # Keep the dependent physical node in all exported fields.
        ops.node(slave,*coordinates[slave].tolist()) # Instantiate the real loading point at its reference coordinates.
        ops.mass(slave,.01,.01,.01,0.,0.,0.) # Include its known physical mass rather than silently dropping inertia.
        ops.rigidLink('beam',master,slave) # Use the same native rigid-arm assumption as the full bridge.
    target=slave if with_arm else master # Apply one known external point load at the selected physical point.
    load=np.array([0.,80000.,-120000.,200000.,0.,0.]) # Produce appreciable 3D bending and torsion to exercise finite rotations.
    ops.timeSeries('Linear',1) # Define a complete proportional static loading path.
    ops.pattern('Plain',1,1) # Create one actual external load pattern.
    ops.load(target,*load.tolist()) # Apply all known physical force and moment components.
    ops.constraints('Transformation') # Enforce the exact native multipoint kinematics.
    ops.numberer('RCM') # Reorder full equations without removing any physical degrees.
    ops.system('UmfPack') # Factor the complete sparse native system.
    ops.test('NormDispIncr',1.e-10,100,0) # Require a small global displacement correction before postcommit force verification.
    ops.algorithm('NewtonLineSearch',.8) # Match the bridge's original native Newton-line-search solver.
    ops.integrator('LoadControl',.1) # Apply ten physical load increments to avoid an artificial one-step failure.
    ops.analysis('Static') # Solve the complete geometrically nonlinear fixture.
    codes=[] # Preserve every actual native return code.
    for unused in range(10): # Complete the declared loading history without truncating successful increments.
        codes.append(int(ops.analyze(1))) # Record the actual native convergence decision.
        if codes[-1]!=0: # Stop at the first failed native load increment.
            break # Keep the failure evidence rather than forcing subsequent increments.
    def residual(dynamic=False): # Assemble actual element, load, inertia, and mass-damping balance after commit.
        values={n:np.zeros(6) for n in nodes} # Preserve every physical nodal action before constraint assembly.
        for tag,conn in connectivity.items(): # Visit every actual beam element.
            force=np.asarray(ops.eleForce(tag),dtype=float).reshape(2,6) # Read full native resisting actions after commit.
            for n,row in zip(conn,force): # Use exact native element incidence.
                values[n]+=row # Sum all internal physical forces and moments.
        values[target]-=load # Subtract the complete known permanent external action.
        if dynamic: # Include the independently known native inertia and damping law during transient verification.
            for n in nodes: # Retain all physical nodal masses, including any rigid-arm loading point.
                values[n][:3]+=.01*(np.asarray(ops.nodeAccel(n)[:3])+.02*np.asarray(ops.nodeVel(n)[:3])) # Add exact translational inertia and mass-proportional damping.
        if with_arm: # Apply the transpose of the actual linearized beam-arm constraint.
            values[master][:3]+=values[slave][:3] # Transfer all physical force components to retained equations.
            values[master][3:]+=values[slave][3:]+np.cross(coordinates[slave]-coordinates[master],values[slave][:3]) # Preserve force moments about the retained reference point.
            values[slave][:]=0. # Count dependent contributions once while retaining their physical response values.
        free=np.asarray([values[n] for n in nodes if n!=1]) # Remove actual support reactions from the free-equation norm.
        return float(np.max(np.abs(free)/np.array([1.,1.,1.,5500.,5500.,5500.]))) # Compare force and moment in declared equivalent-newton units.
    first=residual() if codes[-1]==0 else None # Report only a complete accepted static loading history as a postcommit test.
    cleanup=[] # Preserve fixed-load repeated native commits independently of the first result.
    if codes[-1]==0: # Diagnose postcommit consistency only after successful native equilibrium.
        ops.integrator('LoadControl',0.) # Hold the physical external loading exactly unchanged.
        ops.test('FixedNumIter',2,0) # Perform two actual native Newton corrections per committed diagnostic step.
        for unused in range(5): # Detect drift or force changes under identical physical loading.
            code=int(ops.analyze(1)) # Execute actual full-equation updates rather than projecting any response.
            cleanup.append({'native_code':code,'equivalent_residual_N':residual()}) # Preserve independently assembled postcommit equilibrium.
    response=np.asarray(ops.nodeDisp(master),dtype=float).tolist() # Retain actual large-displacement and rotation evidence.
    ops.wipe() # Release the isolated native domain before returning numeric evidence.
    return {'transformation':transformation,'rigid_arm':with_arm,'native_codes':codes,'initial_postcommit_residual_equivalent_N':first,'cleanup':cleanup,'tip_displacement_mm_rotation_rad':response,'scope':'SMALL_NATIVE_SOLVER_FIXTURE_NOT_BRIDGE_VALIDATION'} # Keep software-mechanics diagnosis distinct from full-bridge validation.
if __name__=='__main__': # Make runtime selection explicit and reproducible.
    parser=argparse.ArgumentParser() # Define one isolated diagnostic experiment.
    parser.add_argument('--backend',choices=['openseespy','xara'],required=True) # Keep old and new native runtime identities separate.
    parser.add_argument('--output',type=Path,required=True) # Require a persistent evidence destination.
    args=parser.parse_args() # Parse the exact runtime and evidence contract.
    if args.backend=='xara': # Use the developer-documented OpenSeesPy compatibility module.
        import opensees.openseespy as ops # Load the independent OpenSeesRT implementation from its selected environment.
    else: # Preserve the historical native runtime as an independently executed control.
        import openseespy.opensees as ops # Load the current bridge's original compiled OpenSees engine.
    results=[] # Preserve all actual successes and unsupported-runtime failures.
    for kind in ['Corotational','Corotational02']: # Compare only the two explicit full large-rotation transformation families.
        for arm in [False,True]: # Distinguish native beam behavior from actual multipoint-constraint effects.
            try: # Keep one unsupported formulation from suppressing other actual diagnostics.
                results.append(run(ops,kind,arm)) # Execute the complete nonlinear fixture and postcommit balance check.
            except Exception as error: # Record actual API or native execution failures as failures.
                results.append({'transformation':kind,'rigid_arm':arm,'error':repr(error)}) # Do not synthesize numerical output for unsupported commands.
    args.output.parent.mkdir(parents=True,exist_ok=True) # Create only the declared diagnostic output namespace.
    args.output.write_text(json.dumps({'backend':args.backend,'results':results},indent=2)+'\n') # Save exact observed results without plotting or smoothing.
    print(json.dumps({'backend':args.backend,'results':results},indent=2)) # Expose concise complete diagnostic evidence to the calling agent.
