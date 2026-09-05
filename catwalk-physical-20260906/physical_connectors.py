import numpy as np  # Define physical offset vectors without fitting any structural stiffness.
from native_deck import Deck as BaseDeck  # Reuse only the native member serializer written in this reconstruction.
class Deck(BaseDeck):  # Add exact finite-rotation connector kinematics to native beams and shells.
    def __init__(self,title):  # Initialize a new physical model with independently tracked connector bodies.
        super().__init__(title);self.offset_bodies={}  # Never use the distance-only native BEAM MPC as a rigid lever.
    def arm(self,reference,xyz,mass=0.,existing=None):  # Attach an actual offset point to a beam or shell cross-section reference.
        if reference not in self.offset_bodies:  # Give all offsets at this section one common finite-rotation body.
            center=self.nodes[reference];rot=self.newnode(center);markers=[self.newnode(center+np.array([.031,0.,0.])),self.newnode(center+np.array([0.,.037,0.])),self.newnode(center+np.array([0.,0.,.041]))]  # Use massless geometric witnesses to define orientation, not extra structural springs.
            members=list(markers);self.bodies.append((members,reference,rot,'offset_'+str(reference)));self.offset_bodies[reference]=(members,rot)  # Keep the reference attached to its real native beam or shell.
            for d in range(3):self.equations.append([(rot,d+1,1.),(reference,d+4,-1.)])  # Match finite body rotation to the real section rotation without fixing either to ground.
        members,rot=self.offset_bodies[reference];n=self.newnode(xyz) if existing is None else existing  # Reuse a declared physical rope node only when it has no other dependent constraint.
        members.append(n);self.add_mass(n,mass)  # The rigid-body equations retain all three translation-rotation lever terms.
        return n  # Return the actual mass or rope attachment point.
    def lever_from_body(self,reference,rotation,xyz,mass=0.):  # Add an offset attachment to an existing native rigid connection patch.
        n=self.newnode(xyz);matched=False  # Keep the added physical point separate until its body is identified.
        for members,ref,rot,label in self.bodies:  # Extend the actual connector instead of creating incompatible duplicate bodies.
            if ref==reference and rot==rotation:members.append(n);matched=True;break  # Preserve one finite-rotation body for all points on this connector.
        if not matched:raise ValueError('Rigid connector reference was not defined')  # Report an actual topology error instead of silently grounding a reference.
        self.add_mass(n,mass);return n  # Add the physical point and its real inertia once.
    def point_on_surface(self,reference,xyz,existing=None):  # Place a rope clamp on a reinforced native shell intersection.
        return self.arm(reference,xyz,0.,existing)  # Use the shell intersection's three rotations and exact finite offset.
    def check_no_distance_levers(self):  # Prevent the documented distance-only MPC from reentering a rigid-offset model.
        if self.rigidlinks:raise ValueError('Distance-only BEAM MPC cannot represent a rigid connection lever')  # Detect a genuinely wrong physical constraint, not a numerical convergence condition.
    def write(self,*args,**kwargs):  # Serialize the same model only after its connector types are physically unambiguous.
        self.check_no_distance_levers();return super().write(*args,**kwargs)  # Preserve the complete native input and all actual relative joint freedoms.
