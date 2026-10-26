#!/usr/bin/env python3  # Generate native full-field nonlinear transient research labels with explicit provisional aerodynamic inputs.
import argparse  # Select case identity and time-grid settings.
import hashlib  # Bind datasets to exact source, solver code, and numerical result bytes.
import inspect  # Identify a dynamically selected detailed physical model's actual source implementation.
import json  # Preserve numerical quality and modeling assumptions.
import math  # Generate deterministic spatial gust functions.
import sys  # Import the sibling aerodynamic implementation explicitly.
from pathlib import Path  # Keep all model and result paths reproducible.
from types import SimpleNamespace  # Reuse the audited equilibrium runner interface.
import numpy as np  # Store exact numerical arrays without generating images.
import openseespy.opensees as ops  # Drive actual full-order nonlinear finite elements.
import opensees_bridge as bridge_module  # Preserve the executed bridge implementation alongside each complete case.
from opensees_bridge import run  # Establish the source-backed nonlinear preloaded state before dynamics.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'aero'))  # Resolve the common physical aerodynamic API.
from aero_loads import CoefficientTable,quasi_steady_loads  # Use dimensional, motion-relative three-force loading.
def assemble_constraint_actions(m,nodes,values):  # Apply the exact transpose of declared rigid-arm kinematics to nodal actions without discarding physical response fields.
    result=np.asarray(values,dtype=float).copy()  # Keep the independent unassembled force field unchanged.
    lookup={node:index for index,node in enumerate(nodes)}  # Preserve actual native node identities.
    connections=m.get('rigid_connections',[])  # Use only explicit native multipoint constraints.
    slaves=[connection['slave'] for connection in connections]  # Collect dependent degrees by their physical node.
    slave_set=set(slaves)  # Index the complete dependent-node set once for linear-time validation.
    if len(slave_set)!=len(slaves) or any(connection['master'] in slave_set for connection in connections):  # Require the model generator to flatten constraint chains consistently with its native domain.
        raise ValueError('Dynamic audit requires unique slaves and flattened rigid-arm constraints')  # Refuse order-dependent or double-counted force transfer.
    for connection in connections:  # Each dependent node contributes once to its physical retained master.
        master,slave=connection['master'],connection['slave']  # Read exact native constraint ownership.
        imaster,islave=lookup[master],lookup[slave]  # Resolve corresponding complete-field rows.
        arm=m['nodes'][slave]-m['nodes'][master]  # Use the same reference arm as the declared linearized rigidLink beam constraint.
        result[imaster,:3]+=result[islave,:3]  # Preserve all transferred force resultants.
        result[imaster,3:]+=result[islave,3:]+np.cross(arm,result[islave,:3])  # Preserve moment and virtual work under the reference-arm constraint.
        result[islave]=0.  # This nodal balance is accounted at its retained equation; its physical displacement remains exported.
    return result  # Return assembled independent equation actions in the full native node ordering.
def saddle_interfaces(m,reference=None):  # Export actual adjacent cable actions and compatible local frames for downstream explicit-wire submodels.
    result={}  # Preserve each distinct physical saddle support node.
    for saddle in m['sets']['TOWER_TOPS']:  # Use the original drawing-derived saddle/tower-top identities.
        displacement=np.asarray(ops.nodeDisp(saddle),dtype=float)  # Read full physical support translation and rotation.
        origin=m['nodes'][saddle]+displacement[:3]  # Locate the current saddle support in global millimetres.
        adjacent=[]  # Retain both cable sides separately instead of inventing one horizontal tension.
        for tag,(group,conn) in m['elements'].items():  # Search actual native adjacency at this mesh resolution.
            if group!='MAIN_CABLES' or saddle not in conn:  # Restrict transfer actions to directly connected main-cable members.
                continue  # Leave tower, deck and hanger actions outside the cable cut interface.
            other=conn[1] if conn[0]==saddle else conn[0]  # Orient each cut tangent away from the saddle.
            endpoint=m['nodes'][other]+np.asarray(ops.nodeDisp(other)[:3],dtype=float)  # Recover the native adjacent node's current position.
            tangent=endpoint-origin  # Form the physical current cable chord.
            length=float(np.linalg.norm(tangent))  # Preserve the actual adjacent-member length.
            if length<=0:  # Refuse a collapsed member before defining orientation.
                raise RuntimeError('Collapsed main-cable member at saddle interface')  # Prevent undefined local boundary directions.
            tangent/=length  # Normalize the outward cable direction.
            transverse=np.asarray([0.,1.,0.])-tangent*tangent[1]  # Project bridge transverse direction onto the cut plane.
            if np.linalg.norm(transverse)<1.e-10:  # Handle an unexpected near-transverse cable without a singular frame.
                transverse=np.asarray([0.,0.,1.])-tangent*tangent[2]  # Use a documented alternate global reference axis.
            transverse/=np.linalg.norm(transverse)  # Normalize the transverse local cut direction.
            frame=np.column_stack((tangent,transverse,np.cross(tangent,transverse)))  # Construct a proper orthonormal local-to-global matrix.
            tension=float(ops.eleResponse(tag,'axialForce')[0])  # Read the actual native tensile force at this accepted state.
            key=f'{saddle}:{tag}'  # Keep stable case-local identity across temporal frames.
            baseline=frame if reference is None else np.asarray(reference[key],dtype=float)  # Compare orientation to the actual permanent equilibrium frame.
            adjacent.append({'interface_id':key,'native_element_id':tag,'source_element_id':m['source_ids'][tag],'saddle_node_id':saddle,'adjacent_node_id':other,'adjacent_node_position_mm':endpoint.tolist(),'adjacent_node_displacement_mm_rotation_rad':ops.nodeDisp(other),'current_member_length_mm':length,'tension_N':tension,'outward_tangent_global':tangent.tolist(),'cable_force_on_saddle_N':(tension*tangent).tolist(),'local_to_global_frame':frame.tolist(),'rotation_from_initial_global':(frame@baseline.T).tolist()})  # Preserve both physical force vectors and finite orientation change.
        result[str(saddle)]={'saddle_node_id':saddle,'current_position_mm':origin.tolist(),'displacement_mm_rotation_rad':displacement.tolist(),'velocity_mm_s_rad_s':ops.nodeVel(saddle),'acceleration_mm_s2_rad_s2':ops.nodeAccel(saddle),'adjacent_main_cable_members':adjacent,'cut_location_scope':'Native adjacent-member chord; local solid cut location must be mapped explicitly and is not assumed identical to this node.'}  # Keep unresolved cut-placement interpolation explicit.
    return result  # Return actual native support and cable data, never a reused historical horizontal-force constant.
def dynamic_balance(m,nodes,index,applied,alpha):  # Independently assemble the physical dynamic residual instead of trusting one native status flag.
    internal=np.zeros((len(nodes),6))  # Retain every physical force and moment degree.
    for tag,(group,conn) in m['elements'].items():  # Visit every native finite element without response reduction.
        force=np.asarray(ops.eleForce(tag),dtype=float).reshape(len(conn),6)  # Read the actual global element resisting vector.
        for node,value in zip(conn,force):  # Preserve original connectivity during independent force assembly.
            internal[index[node]]+=value  # Sum each physical element contribution at its native node.
    mass=np.asarray([m['mass'][node] for node in nodes])[:,None]  # Recover the explicit lumped physical mass.
    velocity=np.asarray([ops.nodeVel(node) for node in nodes])  # Read actual committed translational and angular velocity.
    acceleration=np.asarray([ops.nodeAccel(node) for node in nodes])  # Read actual committed physical acceleration.
    residual=internal-applied-np.asarray([m['gravity'][node] for node in nodes])  # Subtract both variable and permanent external actions.
    residual[:,:3]+=mass*(acceleration[:,:3]+alpha*velocity[:,:3])  # Add independent inertia and declared mass-proportional damping; element masses are zero by construction.
    ops.reactions('-dynamic')  # Ask the native engine for the same full dynamic nodal balance.
    native=np.asarray([ops.nodeReaction(node) for node in nodes])  # Retain native reactions and free residuals independently.
    residual=assemble_constraint_actions(m,nodes,residual)  # Include physical MPC reactions in the independently assembled equation residual.
    native=assemble_constraint_actions(m,nodes,native)  # Compare native reactions under the same exact constraint transpose.
    scales=np.asarray([1.,1.,1.,5500.,5500.,5500.])  # Convert moments to equivalent forces using the declared bridge width.
    free=np.asarray([[not value for value in m['fixities'][node]] for node in nodes])  # Exclude support reactions from the equilibrium-error norm.
    disagreement=float(np.max(np.abs((residual-native)/scales)))  # Check every constrained and free degree for assembly consistency.
    if disagreement>1.e-4:  # Require agreement much tighter than the transient acceptance threshold.
        raise RuntimeError(f'Independent/native dynamic balance mismatch {disagreement} equivalent N')  # Do not publish labels under an unidentified force law.
    force_max=float(np.max(np.abs(residual[:,:3])[free[:,:3]]))  # Report physical force residuals separately from moments.
    moment_max=float(np.max(np.abs(residual[:,3:])[free[:,3:]]))  # Report physical moment residuals in Nmm.
    return max(force_max,moment_max/5500.),{'independent_assembly_difference_equivalent_N':disagreement,'free_force_max_N':force_max,'free_moment_max_Nmm':moment_max,'moment_reference_mm':5500.}  # Return independently verified dimensional equilibrium evidence.
def execute(args):  # Execute one independent whole-history case with a frozen split.
    args.output.mkdir(parents=True,exist_ok=True)  # Save source identity before any potentially long native calculation.
    snapshots={}  # Retain exact case-start implementation snapshots rather than hashing mutable files after the solve.
    source_paths={Path(__file__),Path(bridge_module.__file__),Path(__file__).resolve().parents[1]/'aero'/'aero_loads.py',Path(inspect.getsourcefile(bridge_module.model))}  # Include the actual dynamically selected detailed model generator as well as common mechanics.
    for path in source_paths:  # Freeze every executed source dependency known at case start.
        content=path.read_bytes()  # Read one immutable byte image at case start.
        (args.output/path.name).write_bytes(content)  # Preserve the actual source snapshot with case evidence.
        snapshots[path.name]=hashlib.sha256(content).hexdigest()  # Bind the receipt to that saved code revision.
    m,eq=run(SimpleNamespace(source=args.source,state=args.state,subdivision=args.subdivision,output=args.output/'prestate'))  # Solve genuine complete permanent equilibrium.
    if eq['status']!='VALID_CONVERGED':  # Never generate training labels from an invalid permanent state.
        raise RuntimeError('Permanent equilibrium rejected; transient labels not produced')  # Preserve the decisive numerical blocker.
    nodes=sorted(m['nodes'])  # Freeze full mesh output order.
    index={n:i for i,n in enumerate(nodes)}  # Map stable physical nodes to contiguous array slots.
    coordinates=np.array([m['nodes'][n] for n in nodes])  # Retain every physical mesh point.
    initial=np.array([ops.nodeDisp(n)+ops.nodeVel(n) for n in nodes])  # Save all native displacement/rotation and velocity/angular-velocity components as the true causal initial state.
    initial_saddles=saddle_interfaces(m)  # Capture actual support and cable actions before variable wind loading.
    reference_frames={entry['interface_id']:entry['local_to_global_frame'] for saddle in initial_saddles.values() for entry in saddle['adjacent_main_cable_members']}  # Freeze finite cut-frame references at permanent equilibrium.
    groups=sorted(set(g for g,c in m['elements'].values()))  # Assign deterministic physical relation types.
    features=np.zeros((len(nodes),len(groups)+7))  # Store member incidence, mass and boundary conditions explicitly.
    for n in nodes:  # Add actual nodal mass and source support semantics.
        features[index[n],0]=m['mass'][n]  # Record physical mass in tonnes.
        features[index[n],1:7]=m['fixities'][n]  # Preserve constrained translations/rotations.
    deckarea=np.zeros(len(nodes))  # Assemble actual shell tributary area for conservative aerodynamic loads.
    native_dof_mask=np.zeros((len(nodes),6))  # Distinguish real rotational outputs from unused pure-truss rotations.
    native_dof_mask[:,:3]=1.  # Every physical node retains all three translations.
    relation={}  # Deduplicate physical directed element-neighbor relations.
    for tag,(group,conn) in m['elements'].items():  # Build graph semantics directly from complete finite-element topology.
        for n in conn:  # Flag physical member classes at shared mesh interfaces.
            features[index[n],7+groups.index(group)]=1.  # Preserve multi-membership at cable/beam/shell connections.
            if group not in ('MAIN_CABLES','HANGERS','WIND_CABLES'):  # Beam and shell attachments carry actual physical rotational degrees.
                native_dof_mask[index[n],3:]=1.  # Mark rotational outputs observed only where the native element formulation defines them.
        if group in ('DECK_SHELLS','DECK_PLATES'):  # Load both archived screening shells and actual independently meshed steel panels using their actual areas.
            p=[m['nodes'][n] for n in conn]  # Recover exact mesh coordinates.
            area=np.linalg.norm(np.cross(p[1]-p[0],p[3]-p[0]))  # Integrate planar source shell area.
            for n in conn:  # Share a bilinear cell's area among its vertices.
                deckarea[index[n]]+=area/4  # Preserve exact total loaded deck area.
        for a in conn:  # Keep all local physical cell interactions.
            for b in conn:  # Form directed relations for source integration.
                if a!=b:  # Exclude duplicate self-relations handled by local operator updates.
                    relation[(index[a],index[b],groups.index(group))]=1.  # Deduplicate incident elements without dropping physical nodes.
    edges=np.array([[a,b] for a,b,t in relation],dtype=np.int64).T  # Export complete element-neighbor graph.
    edge_types=np.array([t for a,b,t in relation],dtype=np.int64)  # Preserve beam/cable/shell relation ownership.
    quad=np.array([m['mass'][n] for n in nodes])  # Use positive lumped physical mass as quadrature measure.
    if np.any(quad<=0):  # Reject missing physical integration mass instead of filling arbitrary weights.
        raise RuntimeError('Zero nodal mass in full mesh')  # Stop before exporting an ill-defined integral measure.
    evidence={'normalization':'Cd=Fy/(q*B*L);Cl=Fz/(q*B*L);Cm=Mx/(q*B^2*L)','axes':'wind_drag,wind_lift,positive_bridge_x_pitch','geometry_verified':False,'coefficient_validation_passed':False,'reynolds_applicability_verified':False,'status':'ASSUMED_RESEARCH_COEFFICIENTS_NOT_BRIDGE_AERODYNAMIC_DATA','coefficients':[.35,.05,.02]}  # Explicitly prohibit interpreting illustrative coefficients as measured Zhaqing aerodynamics.
    table=CoefficientTable([-45.,45.],[.35,.35],[-.20,.30],[-.05,.09],5.5,evidence,allow_unverified=True)  # Use explicit bounded provisional angular coefficients for numerical workflow development only.
    ops.loadConst('-time',0.)  # Hold converged permanent forces and reset physical dynamic time.
    ops.wipeAnalysis()  # Keep the full solved structural domain while replacing only the analysis procedure.
    ops.constraints('Transformation')  # Preserve exact source constraints.
    ops.numberer('RCM')  # Reorder complete sparse equations without truncating modes.
    ops.system('UmfPack')  # Factor every physical free degree at each nonlinear iteration.
    ops.test('NormUnbalance',.01,40,0)  # Require small raw dynamic force/moment residual before independent audit.
    ops.algorithm('NewtonLineSearch',.8)  # Use native Newton line search under motion-dependent wind forcing.
    alpha=.02  # Declare an uncalibrated research mass-damping coefficient in inverse seconds.
    ops.rayleigh(alpha,0.,0.,0.)  # Use directly auditable C=alpha*M damping; no ambiguous postcommit stiffness-damping update enters the force law.
    ops.integrator('Newmark',.5,.25)  # Use implicit average-acceleration time integration without modal reduction.
    ops.analysis('Transient')  # Solve complete physical inertia and structural nonlinearity.
    frames,wind_inputs,loads,times,audits,saddles=[initial.copy()],[np.zeros((len(nodes),2))],[np.zeros((len(nodes),6))],[0.],[],[{'time_s':0.,'supports':initial_saddles}]  # Separate prescribed external wind from response-dependent force audit data.
    accelerations=[np.asarray([ops.nodeAccel(n) for n in nodes],dtype=float)]  # Retain native acceleration history independently from learned targets.
    deck=np.flatnonzero(deckarea>0)  # Apply aerodynamic loads to every actual loaded deck node.
    phase=.37*args.seed  # Freeze deterministic phase without random frame-level splitting.
    for step in range(1,args.steps+1):  # Advance one complete independent temporal history.
        t=step*args.dt  # Define actual physical time in seconds.
        if step>1:  # Replace only the previous variable wind load pattern.
            ops.remove('loadPattern',2)  # Keep permanent gravity unchanged.
            ops.remove('timeSeries',2)  # Avoid stale transient load definitions.
        ops.timeSeries('Constant',2)  # Hold the external aerodynamic iterate over one small structural time step.
        ops.pattern('Plain',2,2)  # Apply current full nonlinear relative-flow forces.
        state=np.array([ops.nodeDisp(nodes[i]) for i in deck])  # Read committed physical deck rotations.
        velocity=np.array([ops.nodeVel(nodes[i]) for i in deck])  # Read committed translational and rotational velocity.
        x=coordinates[deck,0]/82000.  # Preserve spatial variation across the real82m main span.
        ramp=min(t/.4,1.)  # Introduce wind gradually to avoid an artificial impulse at prestate time zero.
        speed=ramp*args.speed*(1+.18*np.sin(2*np.pi*.55*t+phase+x*2.3)+.12*np.exp(-((t-.7-.02*args.seed)/.18)**2))  # Generate explicit nonstationary spatial gust input, not measured wind.
        wind=np.column_stack([speed,.08*speed*np.sin(2*np.pi*.7*t+2*x+phase)])  # Supply correlated transverse and vertical wind components.
        prescribed_wind=np.zeros((len(nodes),2))  # Retain one exogenous wind input function on the entire native node set.
        prescribed_wind[deck]=wind  # The declared deck aerodynamic model has no tower/cable direct wind input; the deck mask makes these zeros explicit.
        a=quasi_steady_loads(table,wind,velocity[:,1:3]/1000,state[:,3],velocity[:,3],1.225)  # Include motion-relative velocity, nonlinear squared speed and finite pitch.
        applied=np.zeros((len(nodes),6))  # Preserve every actual external node-force/moment applied this step.
        applied[deck,1]=a['force_y_Npm']*deckarea[deck]/5500/1000  # Convert spanN/m into exact nodalN through shell tributary lengths.
        applied[deck,2]=a['force_z_Npm']*deckarea[deck]/5500/1000  # Apply vertical aerodynamic force consistently.
        applied[deck,3]=a['moment_x_Nm_per_m']*deckarea[deck]/5500  # Convert line moment toNmm using consistent millimetre span tributaries.
        for i in deck:  # Apply loads at every actual deck node.
            ops.load(nodes[i],*applied[i].tolist())  # Pass all physical forces and moments to native dynamic FEM.
        code=ops.analyze(1,args.dt)  # Solve one actual implicit nonlinear structural step.
        if code!=0:  # Reject the whole case when an implicit time increment fails.
            raise RuntimeError(f'Native transient failed step{step},code{code}')  # Prevent incomplete history from entering training.
        residual,balance=dynamic_balance(m,nodes,index,applied,alpha)  # Independently sum all native resisting, inertial, damping, and external actions.
        tension=min(float(ops.eleResponse(tag,'axialForce')[0]) for tag,(g,c) in m['elements'].items() if g in ('MAIN_CABLES','HANGERS','WIND_CABLES'))  # Require tension-only physical cable applicability.
        if residual>.02 or tension<=0:  # Screen numerical equilibrium and invalid compressed cables independently.
            raise RuntimeError(f'Dynamic physical gate failed residual{residual},minimumtension{tension}')  # Do not relabel invalid mechanics as training references.
        frames.append(np.array([ops.nodeDisp(n)+ops.nodeVel(n) for n in nodes],dtype=float))  # Preserve every native displacement/rotation and velocity/angular-velocity output without spatial reduction.
        wind_inputs.append(prescribed_wind)  # Save only externally prescribed wind as operator input, never target-derived aerodynamic forces.
        loads.append(applied.copy())  # Retain the exact double-precision force and moment controls.
        accelerations.append(np.asarray([ops.nodeAccel(n) for n in nodes],dtype=float))  # Preserve acceleration for independent dynamics and future response checks.
        times.append(t)  # Preserve actual accepted frame time.
        audits.append({'time_s':t,'free_residual_equivalent_N':residual,'minimum_cable_force_N':tension,**balance})  # Save native-independent force agreement at every accepted step.
        saddles.append({'time_s':t,'supports':saddle_interfaces(m,reference_frames)})  # Link actual accepted support motion, both cable tensions, and finite cut orientations to local solid boundary inputs.
        print(json.dumps({'case_id':args.case_id,'step':step,'time':t,'residual_N':residual}),flush=True)  # Expose real accepted progress.
    dataset=args.output/'fields.npz'  # Select immutable complete-case training artifact.
    np.savez_compressed(dataset,coordinates=coordinates,quadrature=quad,static_features=features,controls=np.array(wind_inputs),targets=np.array(frames),times=times,output_mask=np.tile(native_dof_mask,(1,2)),initial_state=initial,relation_edges=edges,relation_types=edge_types,edge_measure=quad[edges[0]],native_entity_ids=np.array(nodes),applied_force_moment=np.array(loads),acceleration=np.array(accelerations),native_dof_mask=native_dof_mask,aerodynamic_deck_mask=(deckarea>0).astype(float))  # Preserve true wind-to-state learning inputs; response-derived loads remain separate audit arrays.
    receipt={'case_id':args.case_id,'split':args.split,'quality':'VALID_CONVERGED','quality_status':'VALID_CONVERGED','dataset':str(dataset.resolve()),'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),'solver':'OpenSees '+ops.version(),'source_input_sha256':eq['source_sha256'],'source_result_sha256':hashlib.sha256((args.output/'prestate/equilibrium_summary.json').read_bytes()).hexdigest(),'geometry_evidence_status':'DRAWING_DERIVED_ASSUMPTIONS','geometry_evidence_sha256':eq['source_sha256'],'model_assumptions':eq['physical_limitations']+['source shell offset-0.5 changed to centered common shell surface','lagged partitioned quasi-steady loads; timestep sensitivity required','provisional mass-proportional damping C=0.02/s*M; no calibrated site damping data'],'aerodynamic_evidence':evidence,'time_steps':args.steps,'dt_s':args.dt,'wind_speed_parameter_m_s':args.speed,'node_count':len(nodes),'source_code_sha256':snapshots[Path(__file__).name],'source_snapshots_sha256':snapshots,'relation_types':groups,'relation_reference_measures':{str(i):{'measure':'source_nodal_lumped_mass_tonne','reference_value':1.0} for i in range(len(groups))},'control_channels':['external_transverse_wind_m_s','external_vertical_wind_m_s'],'output_channels':['displacement_x_mm','displacement_y_mm','displacement_z_mm','rotation_x_rad','rotation_y_rad','rotation_z_rad','velocity_x_mm_s','velocity_y_mm_s','velocity_z_mm_s','angular_velocity_x_rad_s','angular_velocity_y_rad_s','angular_velocity_z_rad_s'],'force_input_policy':'Response-dependent aerodynamic force/moment stored only in applied_force_moment audit array; never an operator input','output_mask_policy':'Translation and velocity observed on all nodes; rotation and angular velocity observed only on actual shell/beam nodes','step_audits':audits,'saddle_motion':saddles,'physical_validation':'NOT_REAL_BRIDGE_WIND_COEFFICIENTS_OR_FATIGUE_LIFE','training_eligible':args.split=='train'}  # Keep numerical success distinct from aerodynamic/engineering validation; integration references are fixed across mesh refinements.
    (args.output/'case_manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')  # Publish complete-case metadata only after all requested steps pass.
    return receipt  # Return actual case evidence for dataset assembly.
if __name__=='__main__':  # Run one whole-history experiment from a frozen external configuration.
    p=argparse.ArgumentParser()  # Define explicit case and numerical settings.
    p.add_argument('--source',type=Path,required=True)  # Select authentic whole-bridge source.
    p.add_argument('--state',type=Path,required=True)  # Select authenticated F3 cable state.
    p.add_argument('--output',type=Path,required=True)  # Keep independent-case results isolated.
    p.add_argument('--subdivision',type=int,default=4)  # Default to actual dense spatial refinement.
    p.add_argument('--case-id',required=True)  # Preserve one complete scenario identity.
    p.add_argument('--split',choices=['train','validation','test'],required=True)  # Freeze partitions by complete history.
    p.add_argument('--steps',type=int,default=40)  # Control complete physical history length.
    p.add_argument('--dt',type=float,default=.025)  # Set actual structural integration time step.
    p.add_argument('--speed',type=float,default=15.)  # Set provisional nonstationary wind speed parameter.
    p.add_argument('--seed',type=int,default=0)  # Set deterministic whole-history phase.
    args=p.parse_args()  # Parse the complete native experiment contract.
    execute(args)  # Compute actual full-field dynamic FEM labels.
