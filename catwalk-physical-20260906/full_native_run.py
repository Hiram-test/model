from pathlib import Path  # Preserve a complete source-based full-bridge calculation and its explicit physical assumptions.
import json, hashlib, gc, numpy as np  # Audit geometry, original mass budgets and release completed assembly objects before native factorization.
from types import SimpleNamespace  # Preserve only the observation map and mass ledger required by the native-result parser.
import spatial_native as base  # Reuse only the spatial assembly written during this reconstruction, not historical model data.
from physical_members import BeamLine  # Retain flexible native beams everywhere except the explicitly identified stiff deformation frames.
from run_workstate import run_native  # Execute a fresh native calculation with input and executable provenance.
ROOT=Path(__file__).parent  # Keep all actual outputs on the dedicated physical-joint branch.
class SourceSpreader:  # Represent a source-located deformation frame as a finite-rotation rigid spreader, never as a grounded rotation or a thin floor crossbeam.
    def __init__(self,deck,x,z,ys,profile,owner,tag):  # Preserve the source support location and all separate physical rope ports.
        self.d=deck;self.x=float(x);self.z=float(z);self.owner=owner;self.tag=tag;self.mass=0.;self.ref=deck.newnode((x,0.,z));self.rot=deck.newnode((x,0.,z));self.ports={};center=np.mean(ys);deck.nodes[self.ref][1]=center;deck.nodes[self.rot][1]=center  # Keep the entire frame free to move and rotate under rope and down-pull forces.
        self.members=[];deck.bodies.append((self.members,self.ref,self.rot,tag+'_source_spreader'));deck.owners[owner]+=0.  # Exactly eliminate unreferenced massless orientation witnesses while retaining all real rope, down-pull and mass points with the same free reference translation and rotation.
    def section(self,y):  # Return a physical force-application point and the same free finite body rotation.
        key=round(float(y),9)  # Preserve distinct source rope and down-pull positions.
        if key not in self.ports:self.ports[key]=self.d.lever_from_body(self.ref,self.rot,(self.x,float(y),self.z))  # Retain the full lever-arm kinematics rather than coupling equal translations.
        return self.ports[key],self.rot  # Supply compatible local translation and common body rotation.
    def attach(self,y,xyz,existing=None,mass=0.):  # Connect an actual rope or mass point to the source deformation frame.
        if existing is not None:self.members.append(existing);self.d.add_mass(existing,mass);return existing  # Preserve actual multi-rope connections without duplicate constraints.
        return self.d.lever_from_body(self.ref,self.rot,xyz,mass)  # Add a true finite-offset physical point.
    def mass_at(self,y,z,mass):return self.attach(y,(self.x,float(y),float(z)),mass=mass)  # Preserve spatial inertia and gravity leverage.
class Reconstruction(base.Reconstruction):  # Complete the new physical assembly without altering its original MCT state or fitting a target spectrum.
    def make_members(self):  # Select the explicit source deformation-frame idealization while retaining all native ordinary and passage members.
        previous=base.BeamLine  # Keep the native flexible beam constructor for ordinary floor rows.
        def floor_member(deck,x,z,ys,profile,owner,tag):  # Distinguish source deformation frames from ordinary thin floor crossbeams by source node location.
            frame=tag.startswith('F') and any(abs(float(x)-v)<1.e-7 for v in self.frame_x)  # Use only the original MCT deformation-frame group, not modal behavior.
            return SourceSpreader(deck,x,z,ys,profile,owner,tag) if frame else BeamLine(deck,x,z,ys,profile,owner,tag)  # Preserve actual finite rigid-body spreader action as an explicit stiff-frame approximation.
        base.BeamLine=floor_member  # Supply the declared physical family mapping to this turn's existing source graph builder.
        try:super().make_members()  # Build all native ropes, floor members, fifty ordinary gantries and twenty-one passage assemblies.
        finally:base.BeamLine=previous  # Keep later independent models and tests unaffected by this constructor selection.
    def allocate_points(self):  # Account for original permanent masses after subtracting actual native distributed steel density.
        s=self.s;d=self.d;passages={n:obj for n,u,obj in self.passages}  # Keep the original twenty-one shared passage mass budgets.
        for deck,center in enumerate(base.CENTERS):  # Preserve each original one-deck source budget separately.
            for node,budget in self.budget.items():  # Retain every source point load, not only the dominant ones.
                remainder=budget-self.used[(deck,node)]  # Subtract only actual native steel already charged to this exact object.
                if remainder<-.01:raise ValueError(f'Native steel exceeds original permanent-mass budget at source node {node}: remaining={remainder}, used={self.used[(deck,node)]}, budget={budget}')  # Diagnose a real source/geometry inconsistency rather than introduce negative inertia or rescale to fit frequencies.
                remainder=max(remainder,0.)  # Remove only insignificant floating-point roundoff.
                if node in passages:  # Distribute passage mesh and hardware mass symmetrically over both physical upper chords.
                    obj=passages[node];ys=np.linspace(-24.825,24.825,34);weights=np.ones(34);weights[[0,-1]]=.5;weights/=weights.sum()  # Preserve the original total passage mass with trapezoidal line integration.
                    for chord in obj['chords'][:2]:  # Avoid a spurious longitudinal eccentricity from placing all passage mass on only one chord.
                        for y,w in zip(ys,weights):chord.mass_at(float(y),chord.z+.12,remainder*float(w)/2)  # Keep gravity and inertia at actual symmetric passage locations.
                elif node>=1001 and (deck,node) in self.upper_rows:  # Place original pulley and hardware mass on the corresponding upper gantry.
                    row=self.upper_rows[(deck,node)];zu=s['nodes'][node][2]  # Preserve the upper and floor source elevations separately.
                    for sign in (-1,1):row.mass_at(center+sign*1.60,zu-.50,remainder/2)  # Keep symmetric physical mass offsets rather than a high artificial master node.
                else:  # Retain remaining original masses at their source physical rope or down-pull locations.
                    count=6 if node>=1001 else (4 if node in (729,730) else 16)  # Respect the source object family.
                    mapped=[self.source_map[(deck,node,j)] for j in range(count) if (deck,node,j) in self.source_map]  # Use the actual source-to-physical-node mapping.
                    if remainder>1.e-6 and len(mapped)!=count:raise ValueError(f'Original point mass has missing physical attachments: node={node}, expected={count}, found={len(mapped)}')  # Never silently drop a source point mass.
                    for target in mapped:d.add_mass(target,remainder/count)  # Preserve the complete original mass once.
        self.mass_ledger.extend({'source_node':n,'deck':deck,'budget_kg':budget,'native_steel_charged_kg':self.used[(deck,n)],'remaining_kg':budget-self.used[(deck,n)]} for deck in range(2) for n,budget in self.budget.items())  # Save all source mass balances for independent inspection.
    def save(self,folder):  # Preserve physical assumptions with every executable model, not just in an eventual narrative.
        self.d.bodies=[body for body in self.d.bodies if body[0]]  # Omit sections having no physical rigid-body members; their interpolated reference coordinates and all pin or weld equations remain unchanged.
        super().save(folder);p=folder/'physical_assumptions.json';data=json.loads(p.read_text());data['deformation_frames']='Finite-rotation, ungrounded rigid spreader at each original MCT deformation-frame station; all sixteen rope ports and four down-pull force ports remain separate. Local built-up plate flexibility is not resolved, so this is an explicit stiff-frame approximation, not a detailed frame-shell model.';data['passage_mass_distribution']='Symmetric over both actual upper chords; no artificial mass eccentricity.';data['native_solver']='Official CCX 2.23 with a documented joint-coordinate preprocessing correction; native element, material and eigensolver formulas unchanged.';p.write_text(json.dumps(data,ensure_ascii=False,indent=2))  # Avoid calling unresolved drawing details uniquely verified physical facts.
        data['auxiliary_witness_elimination']='Exactly eliminated massless, unloaded orientation witness points referenced only by their own rigid-body MPCs. All physical members, attachment offsets, masses, supports, reference translation and rotation coordinates, and external compatibility equations are retained. Empty rigid-body cards are omitted; real HW connection patches remain.';data['requested_native_modes']=20;p.write_text(json.dumps(data,ensure_ascii=False,indent=2))  # Record exact auxiliary-coordinate elimination separately from the twenty-root extraction request; neither changes the physical stiffness or mass.
def compute(source,state):  # Execute the complete source-based native static-plus-modal model.
    from read_drawing_dimensions import inspect  # Read otherwise unavailable original raster dimension labels once, preserving their uncertainty.
    inspect();folder=ROOT/'results/full_spatial_native';folder.mkdir(parents=True,exist_ok=True);model=Reconstruction(source,cells=4,pin_axis=0,fork_axis=1)  # Select physical connector axes and a declared discretization before loading any target spectrum.
    model.make_members();model.make_ropes_and_mass();model.save(folder);model.d.write(folder/'bridge.inp',modes=20,gravity=source['g'])  # Request twenty native roots near CCX's numerical shift; this is not yet a verified selection of the lowest fourteen roots.
    (folder/'input_sha256.txt').write_text(hashlib.sha256((folder/'bridge.inp').read_bytes()).hexdigest());print('FULL_MODEL_ASSEMBLED',json.dumps({'nodes':len(model.d.nodes),'native_beams':len(model.d.beams),'native_shells':len(model.d.shells),'native_axial':len(model.d.axial),'mass':model.mass_summary}),flush=True)  # Publish actual model counts and source-mass conservation.
    observation=SimpleNamespace(observe=model.observe,mass_summary=model.mass_summary);del model;gc.collect()  # Release the full Python assembly while retaining the exact serialized input and required output mapping.
    code=run_native(folder,'bridge',3600);status=base.analyze(folder,observation,code)  # Run a real fresh nonlinear equilibrium and native eigensolution, retaining every output.
    if code!=0 or status['native_eigenvalue_count']<14:raise RuntimeError('Full native calculation did not produce fourteen verified roots; inspect its fresh invocation and solver diagnostics')  # Do not relabel an input build or partial solver run as a completed frequency calculation.
    return status  # Keep numerical completion separate from target reproduction and physical-model certainty.
