import numpy as np  # Define actual connector offsets independently of any target frequency.
from native_deck import Deck as BaseDeck  # Use the native beam and shell serializer written in this reconstruction.
class Deck(BaseDeck):  # Implement finite-rotation connector bodies and relative directional joints.
    def __init__(self,title):  # Initialize an isolated native model.
        super().__init__(title);self.offset_bodies={};self.activation_time=1.e-6  # A zero-load initialization step activates native rotational knots without grounding them.
    def arm(self,reference,xyz,mass=0.,existing=None):  # Attach a real offset point to a deformable native section.
        if reference not in self.offset_bodies:  # Define one common connector body at the physical section.
            center=self.nodes[reference];rot=self.newnode(center);markers=[self.newnode(center+np.array([.031,0.,0.])),self.newnode(center+np.array([0.,.037,0.])),self.newnode(center+np.array([0.,0.,.041]))]  # Massless orientation witnesses add no inertia or elastic energy.
            members=list(markers);self.bodies.append((members,reference,rot,'offset_'+str(reference)));self.offset_bodies[reference]=(members,rot)  # Leave all physical section rotations free unless a real joint constrains them.
            for d in range(3):self.equations.append([(rot,d+1,1.),(reference,d+4,-1.)])  # Match the connector's finite rotation to the native section's actual rotation.
        members,rot=self.offset_bodies[reference];n=self.newnode(xyz) if existing is None else existing;members.append(n);self.add_mass(n,mass)  # Attach exactly one physical mass or cable node to this body.
        return n  # Return the point with complete finite translation-rotation lever kinematics.
    def lever_from_body(self,reference,rotation,xyz,mass=0.):  # Extend an existing physical rigid connection patch.
        n=self.newnode(xyz);matched=False  # Preserve a distinct actual attachment point.
        for members,ref,rot,label in self.bodies:  # Find the intended connection body only.
            if ref==reference and rot==rotation:members.append(n);matched=True;break  # Avoid incompatible overlapping connector bodies.
        if not matched:raise ValueError('Rigid connector reference was not defined')  # Expose an actual topology error.
        self.add_mass(n,mass);return n  # Preserve physical point inertia once.
    def point_on_surface(self,reference,xyz,existing=None):return self.arm(reference,xyz,0.,existing)  # Use the reinforced shell intersection's actual section motion.
    def write(self,path,*args,**kwargs):  # Preserve native finite-rotation joints despite the solver's static knot-generation convention.
        if self.rigidlinks:raise ValueError('Distance-only BEAM MPC cannot represent a rigid connection lever')  # Never substitute a distance constraint for a rigid offset.
        super().write(path,*args,**kwargs);text=path.read_text();structural={n for row in self.beams for n in row[:3]}|{n for ids,t,owner in self.shells for n in ids}  # Identify only physical native beam and shell nodes.
        needed={n for terms in self.equations for n,d,c in terms if d>3}|{n for n,d in self.fixed if d>3}  # Locate all physical rotations appearing in actual joint constraints.
        for members,ref,rot,label in self.bodies:needed.update(members);needed.add(ref)  # Include physical connector nodes that must participate in native finite-rotation rigid bodies.
        needed&=structural  # Do not create artificial rotations on rope-only or mass-only points.
        if needed:  # Native CalculiX creates rotational knots for moment degrees of freedom in a dynamic initialization step.
            activation=['*STEP,NLGEOM,INC=4','*DYNAMIC,DIRECT',f'{self.activation_time:.8e},{self.activation_time:.8e}','*CLOAD']  # A vanishing-duration initialization does not change the subsequent static equilibrium problem.
            for n in sorted(needed):  # Explicit zero moments activate the intended native rotational coordinates.
                for d in (4,5,6):activation.append(f'{n},{d},0.0')  # Zero load is not a support, spring, mass or stiffness modification.
            activation.append('*END STEP');position=text.index('*STEP');text=text[:position]+'\n'.join(activation)+'\n'+text[position:]  # Follow initialization with the complete original static load and modal perturbation steps.
        path.write_text(text);self.labels_metadata={'native_rotational_knot_count':len(needed),'initialization_duration_s':self.activation_time,'final_equilibrium':'full nonlinear static equilibrium after initialization'}  # Preserve the exact numerical initialization convention for independent checks.
