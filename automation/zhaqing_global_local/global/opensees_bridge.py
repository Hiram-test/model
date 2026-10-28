#!/usr/bin/env python3  # Solve every physical bridge degree with OpenSees native nonlinear elements.
import argparse  # Expose reproducible source, mesh, and time-integration settings.
import hashlib  # Preserve exact identity of source FEM and prestress state.
import inspect  # Preserve the exact dynamically selected physical model implementation before execution.
import json  # Save auditable model and convergence receipts.
import math  # Compute geometric section and tributary measures.
import time  # Measure actual native solve wall time.
from pathlib import Path  # Keep result paths explicit.
import numpy as np  # Store numerical fields without generating plots.
import openseespy.opensees as ops  # Drive the compiled native finite-element engine, not a learned surrogate.
from kinematic_audit import rigid_kinematic_audit  # 独立检查刚臂运动相容性，防止力平衡掩盖约束错误。
def parse(path):  # Decode the frozen source model definitions needed for explicit engine translation.
    blocks, current = [], None  # Preserve keyword scope and order.
    for raw in path.read_text().splitlines():  # Scan original CalculiX records.
        line = raw.strip()  # Normalize whitespace only.
        if not line or line.startswith('**'):  # Skip comments and blanks.
            continue  # Advance to the next source record.
        if line.startswith('*'):  # Begin a new native keyword.
            parts = line.upper().split(',')  # Separate keyword from parameters.
            opts = dict(p.strip().split('=',1) for p in parts[1:] if '=' in p)  # Decode named keyword parameters.
            current = (parts[0],opts,[])  # Retain the block in mutable data storage.
            blocks.append(current)  # Preserve original block ordering.
        elif current:  # Associate data with its native keyword.
            current[2].append([x.strip() for x in line.split(',') if x.strip()])  # Split only nonempty CSV fields.
    nodes, groups, sets, cload, masses, properties = {}, {}, {}, {}, {}, {}  # Allocate semantic physical inventories.
    material = None  # Track the enclosing source material.
    for keyword,opts,data in blocks:  # Interpret native model blocks.
        if keyword == '*NODE':  # Decode all original user nodes.
            nodes.update({int(r[0]):np.array(list(map(float,r[1:4]))) for r in data})  # Preserve global source coordinates.
        elif keyword == '*ELEMENT':  # Decode original topology and stable source element IDs.
            groups.setdefault(opts['ELSET'],[]).extend((int(r[0]),list(map(int,r[1:]))) for r in data)  # Keep physical group membership.
        elif keyword == '*NSET':  # Decode explicit native node-set membership.
            sets.setdefault(opts['NSET'],[]).extend(int(x) for r in data for x in r)  # Preserve stable source nodes.
        elif keyword == '*CLOAD':  # Preserve original accessory permanent-load actions.
            for r in data:  # Retain every native nodal action.
                cload[(int(r[0]),int(r[1]))]=float(r[2])  # Original LC01 has one nonduplicate load per node-degree.
        elif keyword == '*MASS':  # Associate one accessory mass with its stable MASS element.
            eid=int(opts['ELSET'].removeprefix('MASS_'))  # Recover the native accessory element identity.
            masses[eid]=float(data[0][0])  # Preserve tonne units.
        elif keyword == '*MATERIAL':  # Track the following elastic and density definitions.
            material=opts['NAME']  # Preserve the source material identity.
            properties[material]={}  # Allocate its property record.
        elif keyword == '*ELASTIC':  # Decode linear material constants used by the archived bridge.
            properties[material].update(E=float(data[0][0]),nu=float(data[0][1]))  # Keep MPa modulus and dimensionless Poisson ratio.
        elif keyword == '*DENSITY':  # Decode original physical mass density.
            properties[material]['rho']=float(data[0][0])  # Keep tonne/mm³ units.
    return nodes,groups,sets,cload,masses,properties  # Return the explicit source topology and physical properties.
def model(source,statepath,subdivision=1):  # Construct the full nonlinear mesh without modal or response reduction.
    nodes,groups,sets,cload,masses,materials=parse(source)  # Decode authentic LC01 input bytes.
    state=json.loads(statepath.read_text())  # Read recovered cable fabrication state.
    nodes.update({int(k):np.array(v) for k,v in state['nodeCoordinatesMm'].items()})  # Apply the evidenced F3 main-cable coordinate corrections.
    source_nodes={k:v.copy() for k,v in nodes.items()}  # Retain source coordinates for geometric provenance.
    lookup={tuple(np.round(p,6)):k for k,p in nodes.items()}  # Share refined physical intersections by coordinate.
    def node_at(p):  # Reuse a physical node or create one refinement node.
        key=tuple(np.round(p,6))  # Match only identical points to micrometre precision.
        if key not in lookup:  # Allocate a new physical coordinate.
            lookup[key]=max(nodes)+1  # Avoid source-ID collisions.
            nodes[lookup[key]]=np.array(p)  # Preserve exact generated coordinates.
        return lookup[key]  # Return the physical full-order node.
    elements, original_ids={},{}  # Map new solver elements to source elements and semantic groups.
    for group,items in groups.items():  # Refine every native structural group.
        if group=='DECK_ACCESSORY_MASS':  # Accessory mass remains attached at original physical points.
            continue  # Do not treat point mass as a structural cell.
        for eid,conn in items:  # Refine each source cell independently with shared edge coordinates.
            corners=[nodes[n].copy() for n in conn]  # Freeze source corner geometry before allocating midsides.
            if group=='DECK_SHELLS':  # Use a tensor grid in every original four-node shell.
                grid={}  # Map source-parametric cell vertices to physical node IDs.
                for i in range(subdivision+1):  # Visit longitudinal refinement coordinates.
                    for j in range(subdivision+1):  # Visit transverse refinement coordinates.
                        u,v=i/subdivision,j/subdivision  # Compute exact bilinear source coordinates.
                        grid[i,j]=node_at((1-u)*(1-v)*corners[0]+u*(1-v)*corners[1]+u*v*corners[2]+(1-u)*v*corners[3])  # Share compatible source edges.
                local=[[grid[i,j],grid[i+1,j],grid[i+1,j+1],grid[i,j+1]] for i in range(subdivision) for j in range(subdivision)]  # Preserve counterclockwise shell incidence.
            else:  # Refine line members using their real physical centreline geometry.
                chain=[node_at(corners[0]+i/subdivision*(corners[1]-corners[0])) for i in range(subdivision+1)]  # Preserve original end points and member direction.
                local=[chain[i:i+2] for i in range(subdivision)]  # Keep every segment as an explicit native element.
            for conn2 in local:  # Assign unique native solver cells after physical refinement.
                tag=len(elements)+1  # Use deterministic sequential solver element IDs.
                elements[tag]=(group,conn2)  # Preserve semantic group and actual full mesh topology.
                original_ids[tag]=eid  # Record immutable parent source element.
    ops.wipe()  # Clear only this process's prior OpenSees domain.
    ops.model('basic','-ndm',3,'-ndf',6)  # Retain six physical translations/rotations at shell and beam nodes.
    for nid,p in sorted(nodes.items()):  # Create every physical full-order mesh node.
        ops.node(nid,*p.tolist())  # Keep source N-mm-tonne units unchanged.
    ops.section('ElasticMembranePlateSection',1,30000.,.2,50.,0.)  # Preserve archived continuous50mm deck constitutive screening assumption.
    nodalmass={n:0. for n in nodes}  # Assemble lumped physical mass directly from cells.
    gravity={n:np.zeros(6) for n in nodes}  # Assemble consistent complete permanent actions.
    structural=set()  # Track nodes with physical rotational stiffness.
    area=283*math.pi*2.5**2  # Use verified283×5mm main cable steel area.
    for tag,(group,conn) in elements.items():  # Instantiate each native structural cell.
        eid=original_ids[tag]  # Recover the immutable original source member.
        p=[nodes[n] for n in conn]  # Recover actual cell coordinates.
        if group=='DECK_SHELLS':  # Use updated-Lagrangian nonlinear shell kinematics.
            ops.element('ShellNLDKGQ',tag,*conn,1)  # Keep geometric nonlinearity in the entire deck.
            structural.update(conn)  # Shell nodes carry all six physical degrees.
            cellarea=np.linalg.norm(np.cross(p[1]-p[0],p[3]-p[0]))  # Evaluate actual planar source-cell area.
            mass=cellarea*50*2.6790838137472287e-9  # Preserve original78-panel total mass.
        elif group in ('MAIN_CABLES','HANGERS','WIND_CABLES'):  # Use axial cable elements without artificial bending stiffness.
            section=area if group=='MAIN_CABLES' else (math.pi*16**2 if group=='HANGERS' else math.pi*12**2)  # Preserve source steel areas.
            E=195000. if group=='MAIN_CABLES' else (200000. if group=='HANGERS' else 100000.)  # Preserve source elastic moduli.
            entry=state['elementStates'].get(str(eid))  # Bind main-cable and hanger constitutive state by exact source ID.
            sigma=float(entry['axialStressMPa']) if entry else 10000./section  # Use recovered F3 stress; explicitly provisional10kN wind-cable pretension.
            ratio=float(entry['equilibriumLengthMm'])/float(entry['unstressedLengthMm']) if entry else 1.  # Reproduce fixed-L0 cable tangent in geometric-reference strain coordinates.
            ops.uniaxialMaterial('Elastic',2*tag,E*ratio)  # Preserve exact fixed-fabrication dN/dL.
            ops.uniaxialMaterial('InitStressMaterial',2*tag+1,2*tag,sigma)  # Apply recovered initial cable stress without thermal ramp artifacts.
            ops.element('corotTruss',tag,*conn,section,2*tag+1,'-doRayleigh',1)  # Retain full3D geometric stiffness with all physical cable nodes.
            mass=np.linalg.norm(p[1]-p[0])*section*7.85e-9  # Compute source-consistent steel mass.
        else:  # Construct native corotational beam members including tower and wind attachment links.
            E,nu,rho=200000.,.3,7.85e-9  # Default to source steel properties.
            if group=='LONG_GIRDERS':  # Use actual HW400×400×13×21 weak and strong axes instead of equivalent rectangular weak axis.
                b,h,tw,tf=400.,400.,13.,21.  # Read verified source section dimensions in millimetres.
                A=2*b*tf+(h-2*tf)*tw  # Compute exact H-section area.
                Iy=(b*h**3-(b-tw)*(h-2*tf)**3)/12  # Compute strong-axis bending inertia.
                Iz=(2*tf*b**3+(h-2*tf)*tw**3)/12  # Compute weak-axis bending inertia.
                J=(2*b*tf**3+(h-2*tf)*tw**3)/3  # Use thin-wall open-section Saint-Venant torsion approximation explicitly.
                vec=[0.,0.,1.]  # Align local strong bending with vertical global z.
            else:  # Preserve other archived rectangular screening sections pending full connection/plate audit.
                b,h=(41.412303195742695,420.) if group=='CROSSBEAMS' else ((1000.,1500.) if group=='TOWER_COLUMNS' else ((1500.,500.) if group=='TOWER_TOP_BEAMS' else (160.,160.)))  # Retain each documented source section envelope.
                E,nu,rho=(30000.,.2,2.5e-9) if group.startswith('TOWER') else (E,nu,rho)  # Preserve source tower concrete properties.
                A,Iy,Iz=b*h,b*h**3/12,h*b**3/12  # Compute rectangular section inertia about actual local axes.
                a,c=max(b,h),min(b,h)  # Order rectangle sides for torsional constant.
                J=a*c**3*(1/3-.21*c/a*(1-c**4/(12*a**4)))  # Use standard Saint-Venant rectangular torsional approximation.
                vec=[1.,0.,0.] if abs((p[1]-p[0])[2])>0.9*np.linalg.norm(p[1]-p[0]) else [0.,0.,1.]  # Avoid transformation reference vector parallel to member tangent.
            ops.geomTransf('Corotational',tag,*vec)  # Update each complete beam's geometry in the native engine.
            ops.element('elasticBeamColumn',tag,*conn,A,E,E/(2*(1+nu)),J,Iy,Iz,tag)  # Retain both bending axes, torsion, axial response, and large rotations.
            structural.update(conn)  # Beam nodes carry physical rotational stiffness.
            mass=np.linalg.norm(p[1]-p[0])*A*rho  # Compute actual source-compatible line-member mass.
        for node in conn:  # Distribute each cell's physical lumped mass and self weight.
            nodalmass[node]+=mass/len(conn)  # Preserve total structural mass independently of mesh density.
            gravity[node][2]-=9810.*mass/len(conn)  # Assemble complete native gravity load at physical nodes.
    for eid,conn in groups['DECK_ACCESSORY_MASS']:  # Restore original accessory point masses.
        nodalmass[conn[0]]+=masses[eid]  # Preserve source mass for dynamic inertia.
    for (node,dof),value in cload.items():  # Restore original accessory permanent CLOAD records once.
        gravity[node][dof-1]+=value  # Preserve source total external load exactly.
    fixities={n:[0]*6 for n in nodes}  # Collect constraints before calling native fix once per node.
    for n in nodes:  # Eliminate only physically unused rotations on pure cable nodes.
        if n not in structural:  # Pure truss nodes have no rotational degrees in the physical formulation.
            fixities[n][3:]=[1,1,1]  # Remove zero-stiffness rotations without restraining cable translation.
    for name,dofs in [('TOWER_BASES',range(6)),('MAIN_CABLE_ANCHORS',range(3)),('WIND_ANCHORS',range(3)),('DECK_LEFT_PIN',range(3)),('DECK_RIGHT_ROLLER',range(1,3))]:  # Reproduce source support kinematics.
        for n in sets[name]:  # Visit each exact source support node.
            for d in dofs:  # Apply only the source-constrained physical directions.
                fixities[n][d]=1  # Merge with pure cable rotational constraints.
    for n in nodes:  # Apply complete support conditions and physical mass.
        ops.fix(n,*fixities[n])  # Assign each prescribed physical degree once.
        ops.mass(n,nodalmass[n],nodalmass[n],nodalmass[n],0.,0.,0.)  # Retain translational lumped inertia without fictitious rotational mass.
    return {'nodes':nodes,'elements':elements,'source_ids':original_ids,'sets':sets,'mass':nodalmass,'gravity':gravity,'state':state,'source_nodes':source_nodes,'fixities':fixities}  # Return all full-mesh fields for export and audit.
def physical_reactions(m,nodes):  # Assemble independent physical residuals including exact rigid-arm constraint force transfer.
    values={n:np.array(ops.nodeReaction(n),dtype=float) for n in nodes}  # Read native unconstrained nodal resisting-force balances.
    connections=m.get('rigid_connections',[])  # Read only explicitly modeled physical connection kinematics.
    for connection in reversed(connections):  # Transfer dependent-node force and moment to its retained physical master.
        master,slave=connection['master'],connection['slave']  # Preserve exact native MP constraint ownership.
        arm=m['nodes'][slave]-m['nodes'][master]  # Use the same reference arm as OpenSees rigidLink beam transformation.
        values[master][:3]+=values[slave][:3]  # Transfer all dependent translation-force residuals.
        values[master][3:]+=values[slave][3:]+np.cross(arm,values[slave][:3])  # Preserve total moment about the retained physical node.
        values[slave][:]=0.  # Dependent nodal forces are accounted once, not interpreted as independent free equations.
    return np.array([values[n] for n in nodes])  # Return complete ordered nodal fields with physical MP equilibrium assembled.
def configure(displacement_tolerance=1e-9):  # Configure a declared native predictor stopping tolerance independently from the final dimensional force gate.
    ops.constraints('Transformation')  # Enforce only exact prescribed source degrees.
    ops.numberer('RCM')  # Reduce sparse matrix bandwidth without model reduction.
    ops.system('UmfPack')  # Use native sparse direct factorization of every free physical degree.
    ops.test('NormDispIncr',displacement_tolerance,60,0)  # Require the declared native global increment norm, then independently audit actual dimensional force and moment residuals.
    ops.algorithm('NewtonLineSearch',.8)  # Use line search for large-deflection prestressed equilibrium.
    ops.integrator('LoadControl',1.)  # Apply complete dead load against full initial prestress.
    ops.analysis('Static')  # Establish actual nonlinear permanent equilibrium before dynamics.
def write_vtk(path,m,displacement=None):  # Export exact native mesh/results as VTK interchange data without drawing or syntheticgeometry.
    ids=sorted(m['nodes'])  # Freezeallphysicalnodeidentities.
    index={n:i for i,n in enumerate(ids)}  # MapnativeidentitiestoVTKconnectivity.
    groups=sorted(set(g for g,c in m['elements'].values()))  # Preservephysicalmembercategories.
    cells=list(m['elements'].values())  # Retainallphysicalnativeelements.
    with path.open('w') as stream:  # WriteportableASCIIgeometryfornativeParaView/Gmsh/CGXviewers.
        stream.write('# vtk DataFile Version 3.0\nZhaqing native full-order FEM\nASCII\nDATASET UNSTRUCTURED_GRID\n')  # Identifynativephysicalmeshprovenance.
        stream.write(f'POINTS {len(ids)} double\n')  # Declarethecompletepointpopulation.
        for n in ids:  # Exporteveryactualphysicalcoordinatewithoutresampling.
            stream.write(' '.join(f'{v:.12g}' for v in m['nodes'][n])+'\n')  # Preservephysicalmillimetres.
        stream.write(f'CELLS {len(cells)} {sum(len(c)+1 for g,c in cells)}\n')  # Preservecompleteactualtopology.
        for g,c in cells:  # Serializeactualshellandbeam/cablecellincidence.
            stream.write(str(len(c))+' '+' '.join(str(index[n]) for n in c)+'\n')  # Keeporiginalnodeassociation.
        stream.write(f'CELL_TYPES {len(cells)}\n')  # SelectnativeVTKcellfamilies.
        stream.write('\n'.join('9' if len(c)==4 else '3' for g,c in cells)+'\n')  # Mapphysicalquadsandlineswithoutinventedsolids.
        stream.write(f'CELL_DATA {len(cells)}\nSCALARS member_group int 1\nLOOKUP_TABLE default\n')  # PreserveauditablephysicalgroupIDs.
        stream.write('\n'.join(str(groups.index(g)) for g,c in cells)+'\n')  # Labelsource-backedmemberfamilies.
        stream.write(f'POINT_DATA {len(ids)}\nSCALARS native_node_id int 1\nLOOKUP_TABLE default\n')  # Retainstablesolveridentityateverypoint.
        stream.write('\n'.join(map(str,ids))+'\n')  # Allowindependentmesh/resultcrosschecks.
        if displacement is not None:  # Exportonlyactualnativefieldsprovidedbythesolverrunner.
            stream.write('VECTORS displacement_mm double\n')  # Declarecorrectphysicalvectorunits.
            for row in displacement:  # Serializecompleteactualdisplacementfieldinthenativepointorder.
                stream.write(' '.join(f'{v:.12g}' for v in row[:3])+'\n')  # Preservecomputedcomponentswithoutplottingorsmoothing.
def run(args):  # Execute the requested full-order bridge model and archive only observed results.
    args.output.mkdir(parents=True,exist_ok=True)  # Create isolated native result namespace.
    snapshots={}  # Bind every physical run to immutable model and solver implementation bytes.
    for label,path in [('model_source_snapshot.py',Path(inspect.getsourcefile(model))),('solver_source_snapshot.py',Path(__file__)),('kinematic_audit.py',Path(inspect.getsourcefile(rigid_kinematic_audit)))]:  # 冻结真实几何、原生求解流程和新增相容性审计，防止回执与源码脱节。
        content=path.read_bytes()  # Read the exact source at launch before subsequent edits can occur.
        (args.output/label).write_bytes(content)  # Retain the executed source alongside its real numerical results.
        snapshots[label]=hashlib.sha256(content).hexdigest()  # Preserve exact execution identity for audit and resume policies.
    (args.output/'source_snapshots.json').write_text(json.dumps(snapshots,indent=2)+'\n')  # Save source hashes before a potentially interrupted long native solve.
    start=time.perf_counter()  # Begin real elapsed-time accounting.
    m=model(args.source,args.state,args.subdivision)  # Construct all source-backed physical degrees.
    write_vtk(args.output/'native_mesh.vtk',m)  # Preserveactualphysicalgeometryevenifthenonlinearsolvefails.
    (args.output/'mesh_contract.json').write_text(json.dumps({'nodes':{str(n):v.tolist() for n,v in m['nodes'].items()},'elements':{str(e):{'group':g,'nodes':c,'source':m['source_ids'][e]} for e,(g,c) in m['elements'].items()},'rigid_connections':m.get('rigid_connections',[]),'physical_limitations':m.get('physical_limitations',[])},indent=2)+'\n')  # Preserveactualgeometryandexplicitconnectionassumptionsbeforeanynumericalexecution.
    ops.timeSeries('Linear',1)  # Define the permanent load parameter.
    ops.pattern('Plain',1,1)  # Create a complete physical gravity load pattern.
    for n,load in m['gravity'].items():  # Apply structural gravity and archived permanent nodal actions.
        ops.load(n,*load.tolist())  # Pass all six physical force/moment components to native FEM.
    native_displacement_tolerance=float(getattr(args,'initial_displacement_tolerance',1e-9))  # Freeze the explicit native predictor threshold before any numerical iteration.
    configure(native_displacement_tolerance)  # Initialize the full nonlinear equilibrium solver without altering the independent1e-3N final force gate.
    code=ops.analyze(1)  # Solve complete dead load and initial prestress simultaneously.
    if code==0:  # Refine the accepted native state using independent physical force and moment residuals.
        ops.integrator('LoadControl',0.)  # Hold all actual forces and fabrication prestress unchanged.
        ops.test('FixedNumIter',2,0)  # Execute exactly two genuine Newton updates before external dimensional acceptance checks.
        ordered_nodes=list(m['nodes'])  # Freeze the full native ordering for residual-hotspot and correction evidence.
        previous_displacement=np.asarray([ops.nodeDisp(n) for n in ordered_nodes])  # Retain the preceding committed full state solely for convergence diagnostics.
        load_reference=max(1.,sum(float(np.linalg.norm(load[:3])) for load in m['gravity'].values()))  # Report a physical total external-force reference without using it to relax the fixed acceptance tolerance.
        for cleanup in range(120):  # Bound residual cleanup without accepting unconverged state automatically.
            update=ops.analyze(1)  # Solve native tangent corrections at unchanged load, never project predicted fields.
            ops.reactions()  # Reassemble physical internal forces after the native updates.
            residual=physical_reactions(m,ordered_nodes)  # Preserve actual assembled free-equation force and moment residuals after native commits.
            candidates=[(abs(row[d])/(1. if d<3 else 5500.),n,d,float(row[d])) for n,row in zip(ordered_nodes,residual) for d in range(6) if not m['fixities'][n][d]]  # Record physical hotspot identity rather than only an unexplained scalar norm.
            hotspot=max(candidates)  # Locate the largest independent equivalent-force residual.
            error=hotspot[0]  # Apply exactly the original declared absolute equilibrium tolerance.
            current_displacement=np.asarray([ops.nodeDisp(n) for n in ordered_nodes])  # Read the actual complete committed state for correction evidence.
            change=current_displacement-previous_displacement  # Distinguish decreasing force residual from continued significant motion.
            previous_displacement=current_displacement  # Preserve the current full native state for the next diagnostic comparison.
            print(json.dumps({'equilibrium_cleanup':cleanup,'equivalent_residual_N':error,'native_update':update,'hotspot_native_node':hotspot[1],'hotspot_dof_1based':hotspot[2]+1,'hotspot_residual_N_or_Nmm':hotspot[3],'relative_to_total_gravity_force':error/load_reference,'total_gravity_force_N':load_reference,'maximum_committed_translation_change_mm':float(np.max(np.abs(change[:,:3]))),'maximum_committed_rotation_change_rad':float(np.max(np.abs(change[:,3:])))}),flush=True)  # Preserve force, moment, scale, location, and actual correction evidence without weakening acceptance.
            if update==0 and error<1e-3:  # Require independent physical equilibrium with the original declared tolerance.
                break  # Stop only after all free physical degrees satisfy the audit.
        else:  # Reject exhaustion even if the native fixed-iteration test committed each trial.
            code=-99  # Expose failed independent physical convergence to every downstream label guard.
    nodes=sorted(m['nodes'])  # Freeze output ordering for every physical node.
    disp=np.array([ops.nodeDisp(n) for n in nodes])  # Read native converged or rejected trial displacements explicitly.
    ops.reactions()  # Form physical support reactions from actual native internal resisting forces.
    reaction=physical_reactions(m,nodes)  # Store all full-order nodal residual/reaction components.
    free_res=max(abs(reaction[i,d])/(1. if d<3 else 5500.) for i,n in enumerate(nodes) for d in range(6) if not m['fixities'][n][d])  # Audit translations inN and rotations as moment/5500mm equivalent force without mixing dimensions.
    axial={str(tag):float(ops.eleResponse(tag,'axialForce')[0]) for tag,(group,conn) in m['elements'].items() if group in ('MAIN_CABLES','HANGERS','WIND_CABLES')}  # Check actual cable force sign after solution.
    minimum=min(axial.values())  # Reject physically compressed cable solutions from valid labels.
    kinematics=rigid_kinematic_audit(m,nodes,disp)  # 使用所有原生位移核对全部真实刚臂，不投影或修正任何节点。
    (args.output/'rigid_kinematic_audit.json').write_text(json.dumps(kinematics,indent=2)+'\n')  # 在拒绝之前保存带单位和节点号的独立相容性证据。
    status='VALID_CONVERGED' if code==0 and free_res<1e-3 and minimum>0 and kinematics['passed'] else 'REJECTED'  # 保留既有力和索力门槛，同时拒绝不满足模型声明约束的解。
    write_vtk(args.output/'native_equilibrium.vtk',m,disp)  # Exportactualnativefull-fieldsolutionwithoutclaimingarejectedstateisvalid.
    np.savez_compressed(args.output/'equilibrium_fields.npz',node_ids=nodes,coordinates=np.array([m['nodes'][n] for n in nodes]),displacement=disp,reaction=reaction)  # Persist actual full-field arrays without plotting or smoothing.
    receipt={'status':status,'solver':'OpenSees '+ops.version(),'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'state_sha256':hashlib.sha256(args.state.read_bytes()).hexdigest(),'subdivision':args.subdivision,'node_count':len(nodes),'element_count':len(m['elements']),'native_exit':code,'free_residual_max_equivalent_N':free_res,'force_tolerance_N':1e-3,'moment_scale_mm':5500.,'initial_native_displacement_test_tolerance_mm':native_displacement_tolerance,'postcommit_displacement_correction_gate_enforced':False,'minimum_cable_force_N':minimum,'maximum_translation_mm':float(np.linalg.norm(disp[:,:3],axis=1).max()),'midspan_monitor_u_mm':disp[min(range(len(nodes)),key=lambda i:np.linalg.norm(m['nodes'][nodes[i]]-np.array([41000.,0.,-5.]))),:3].tolist(),'mass_tonne':sum(m['mass'].values()),'elapsed_s':time.perf_counter()-start,'scope':'Full-order geometric nonlinear '+m.get('shell_element','ShellNLDKGQ')+'+corotational beam+corotTruss; no modal or response reduction','shell_element':m.get('shell_element','ShellNLDKGQ'),'physical_limitations':m.get('physical_limitations',['continuous50mm deck and crossbeam equivalent section remain uncalibrated','10kN wind-cable prestress provisional','F3 nominal prestress from earlier frictionless saddle model; new whole-model equilibrium solved','longitudinal girder actual HW400x400x13x21; thin-wall J approximation','elastic material; no material plasticity','source shell offset-0.5 changed to centered common shell surface']),'elements':{str(k):{'group':g,'nodes':c,'source_element_id':m['source_ids'][k]} for k,(g,c) in m['elements'].items()},'cable_axial_force_N':axial}  # Publish mechanics, actual residuals, and honest modeling limits.
    (args.output/'equilibrium_summary.json').write_text(json.dumps(receipt,indent=2)+'\n')  # Preserve complete numeric result even when rejected.
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('elements','cable_axial_force_N')},indent=2),flush=True)  # Stream concise actual solver outcome.
    return m,receipt  # Return live domain for verified transient continuation only.
if __name__=='__main__':  # Run native bridge equilibrium from explicit command-line settings.
    p=argparse.ArgumentParser()  # Define reproducible source and refinement choices.
    p.add_argument('--source',type=Path,required=True)  # Select authentic LC01 native input.
    p.add_argument('--state',type=Path,required=True)  # Select recovered F3 fabrication state.
    p.add_argument('--output',type=Path,required=True)  # Select isolated result namespace.
    p.add_argument('--subdivision',type=int,default=1)  # Refine each shell edge and line member without reduction.
    a=p.parse_args()  # Parse the complete reproducible experiment request.
    run(a)  # Execute actual native nonlinear equilibrium and field export.
