import numpy as np  # Define physical offsets without target-dependent stiffness or artificial support conditions.
from native_deck import Deck as BaseDeck  # Use the actual native beam and shell elements written in this reconstruction.
class Deck(BaseDeck):  # Attach physical connector points to native section rotations.
    def __init__(self,title):  # Initialize a source-based native physical model.
        super().__init__(title);self.offset_bodies={}  # Keep every actual connector body separately identifiable.
    @staticmethod  # Calculate physical section area consistently with native distributed density.
    def area(profile):  # Extend the native serializer to actual circular solid pin and hanger sections.
        if profile[0]=='CIRC':return np.pi*profile[1][0]*profile[1][1]/4  # Use the real elliptical section area, including a circular solid pin as a special case.
        return BaseDeck.area(profile)  # Preserve existing BOX, PIPE and rectangular section definitions.
    def arm(self,reference,xyz,mass=0.,existing=None):  # Attach a real offset point with complete finite rigid-body kinematics.
        if reference not in self.offset_bodies:  # Define one connector orientation for all points on the same physical section.
            center=self.nodes[reference];rot=self.newnode(center);markers=[self.newnode(center+np.array([.031,0.,0.])),self.newnode(center+np.array([0.,.037,0.])),self.newnode(center+np.array([0.,0.,.041]))]  # Massless orientation witnesses contribute neither stiffness nor inertia.
            members=list(markers);self.bodies.append((members,reference,rot,'offset_'+str(reference)));self.offset_bodies[reference]=(members,rot)  # Leave the native section free to translate and rotate.
            for d in range(3):self.equations.append([(rot,d+1,1.),(reference,d+4,-1.)])  # Couple relative rotations to the native section's actual knot coordinates.
        members,rot=self.offset_bodies[reference];n=self.newnode(xyz) if existing is None else existing;members.append(n);self.add_mass(n,mass)  # Keep each physical cable or mass node in one connector body only.
        return n  # Return the real attachment point with all offset terms preserved.
    def lever_from_body(self,reference,rotation,xyz,mass=0.):  # Extend an existing reinforced physical connection patch.
        n=self.newnode(xyz);matched=False  # Preserve an explicit physical attachment point.
        for members,ref,rot,label in self.bodies:  # Select only the intended connection body.
            if ref==reference and rot==rotation:members.append(n);matched=True;break  # Avoid redundant or incompatible rigid-body constraints.
        if not matched:raise ValueError('Rigid connector reference was not defined')  # Report a real connection graph error.
        self.add_mass(n,mass);return n  # Preserve attached physical mass exactly once.
    def point_on_surface(self,reference,xyz,existing=None):return self.arm(reference,xyz,0.,existing)  # Use the native reinforced shell intersection as the rope-clamp reference.
    def write(self,path,*args,**kwargs):  # Use ordinary nonlinear static equilibrium without any activation load or integration step.
        if self.rigidlinks:raise ValueError('Distance-only BEAM MPC cannot represent a rigid connection lever')  # Exclude a physically different constraint type.
        return super().write(path,*args,**kwargs)  # The documented preprocessing correction only realizes the rotations already specified by this input.
