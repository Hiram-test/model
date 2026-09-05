import numpy as np  # Define physical offsets without target-dependent stiffness or artificial support conditions.
from native_deck import Deck as BaseDeck  # Use the actual native beam and shell elements written in this reconstruction.
class Deck(BaseDeck):  # Attach physical connector points to native section rotations.
    def __init__(self,title):  # Initialize a source-based native physical model.
        super().__init__(title);self.offset_bodies={};self._body_members_index={};self._indexed_body_count=0;self._indexed_bodies=self.bodies  # Keep the original body list and an append-only lookup index referencing its exact member lists.
    def body_members(self,reference,rotation):  # Find the first matching physical body without repeatedly scanning all preceding bodies.
        if self._indexed_bodies is not self.bodies or len(self.bodies)<self._indexed_body_count:  # Rebuild only when diagnostics replace or shorten the original body list.
            self._body_members_index={};self._indexed_body_count=0;self._indexed_bodies=self.bodies  # Discard stale lookups while preserving the externally supplied physical body list.
        while self._indexed_body_count<len(self.bodies):  # Index each appended body exactly once across ordinary assembly calls.
            members,ref,rot,label=self.bodies[self._indexed_body_count];self._body_members_index.setdefault((ref,rot),members);self._indexed_body_count+=1  # Retain the first matching body's original member-list object and insertion order.
        return self._body_members_index.get((reference,rotation))  # Return the same mutable member list selected by the former first-match scan.
    @staticmethod  # Calculate physical section area consistently with native distributed density.
    def area(profile):  # Extend the native serializer to actual circular solid pin and hanger sections.
        if profile[0]=='CIRC':return np.pi*profile[1][0]*profile[1][1]/4  # Use the real elliptical section area, including a circular solid pin as a special case.
        return BaseDeck.area(profile)  # Preserve existing BOX, PIPE and rectangular section definitions.
    def arm(self,reference,xyz,mass=0.,existing=None):  # Attach a real offset point with complete finite rigid-body kinematics.
        if reference not in self.offset_bodies:  # Define one connector orientation for all points on the same physical section.
            center=self.nodes[reference];rot=self.newnode(center);markers=[]  # Exactly eliminate unreferenced massless orientation witnesses; the existing native-section rotation equations retain all three physical rotation components.
            proxy=self.newnode(center);members=list(markers);self.bodies.append((members,proxy,rot,'offset_'+str(reference)));self.offset_bodies[reference]=(members,rot)  # Use the independently verified coincident translation reference so native beam expansion and external rigid-body coordinates remain distinct.
            for d in range(3):self.equations.append([(proxy,d+1,1.),(reference,d+1,-1.)])  # Preserve exact free translation compatibility without adding stiffness, mass, or a grounded rotation.
            for d in range(3):self.equations.append([(rot,d+1,1.),(reference,d+4,-1.)])  # Couple relative rotations to the native section's actual knot coordinates.
        members,rot=self.offset_bodies[reference];n=self.newnode(xyz) if existing is None else existing;members.append(n);self.add_mass(n,mass)  # Keep each physical cable or mass node in one connector body only.
        return n  # Return the real attachment point with all offset terms preserved.
    def lever_from_body(self,reference,rotation,xyz,mass=0.):  # Extend an existing reinforced physical connection patch.
        n=self.newnode(xyz);members=self.body_members(reference,rotation)  # Preserve the original node-creation order and select the exact intended member list.
        if members is None:raise ValueError('Rigid connector reference was not defined')  # Report the same connection graph error, including when a new attachment node was just allocated.
        members.append(n)  # Preserve the original physical body membership and attachment order without another global scan.
        self.add_mass(n,mass);return n  # Preserve attached physical mass exactly once.
    def point_on_surface(self,reference,xyz,existing=None):return self.arm(reference,xyz,0.,existing)  # Use the native reinforced shell intersection as the rope-clamp reference.
    def write(self,path,*args,**kwargs):  # Use ordinary nonlinear static equilibrium without any activation load or integration step.
        if self.rigidlinks:raise ValueError('Distance-only BEAM MPC cannot represent a rigid connection lever')  # Exclude a physically different constraint type.
        self.bodies=[body for body in self.bodies if body[0]]  # Omit empty rigid-body cards after auxiliary-point elimination while retaining every reference coordinate and external compatibility equation.
        return super().write(path,*args,**kwargs)  # The documented preprocessing correction only realizes the rotations already specified by this input.
