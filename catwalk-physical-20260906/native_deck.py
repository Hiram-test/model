from pathlib import Path  # Preserve complete native models rather than external stiffness surrogates.
import math, json, collections, numpy as np  # Build explicit physical geometry and auditable native input records.
from mct_workstate import number  # Use decimal-safe native numeric serialization.
class Deck:  # Hold physical nodes, native members, concentrated masses and real connection equations.
    def __init__(self,title):  # Initialize an isolated physical model.
        self.title=title;self.nodes={};self.cache={};self.beams=[];self.shells=[];self.axial=[];self.mass=collections.defaultdict(float);self.fixed=set();self.equations=[];self.rigidlinks=[];self.bodies=[];self.labels={};self.owners=collections.defaultdict(float);self.members=[];self.observation=[];self.joints=[]  # Keep topology, mass provenance and all relative freedoms explicit.
    def node(self,xyz,tag=''):  # Merge only deliberately identical physical vertices.
        xyz=np.asarray(xyz,dtype=float);key=(tag,)+tuple(np.round(xyz,10))  # Do not merge different sides of a hinge merely because coordinates coincide.
        if key not in self.cache:self.cache[key]=len(self.nodes)+1;self.nodes[self.cache[key]]=xyz  # Preserve new physical nodes and exact coordinates.
        return self.cache[key]  # Return the declared physical node.
    def newnode(self,xyz):return self.node(xyz,'independent_'+str(len(self.nodes)+1))  # Create a distinct node for a pin side or mass attachment.
    def add_mass(self,n,value):  # Add a real nonstructural or rope mass to a physical point.
        if value<-1.e-5:raise ValueError('Negative residual physical mass at node '+str(n)+': '+str(value))  # Diagnose double-counted structural mass instead of inserting negative inertia.
        self.mass[n]+=max(0.,float(value))  # Ignore roundoff-size negative remainders only.
    def arm(self,reference,xyz,mass=0.):  # Connect an offset point using the native finite-rotation BEAM MPC.
        n=self.newnode(xyz);self.rigidlinks.append((reference,n));self.add_mass(n,mass)  # Preserve the physical lever arm and its spatial inertia.
        return n  # Return a point whose motion includes the native rotational lever term.
    def pin(self,slave,master,axis=0,rotation_node=None,label=''):  # Model a relative one-axis pin without grounding any real rotation.
        for d in range(1,4):self.equations.append([(slave,d,1.),(master,d,-1.)])  # Enforce coincident translations at the actual pin center.
        for d in range(3):  # Preserve the other two relative rotation components.
            if d!=axis:self.equations.append([(slave,d+4,1.),(rotation_node,d+1,-1.)] if rotation_node else [(slave,d+4,1.),(master,d+4,-1.)])  # Release only rotation about the stated physical pin axis.
        self.joints.append({'name':label,'slave':slave,'master':master,'free_axis_xyz':axis,'rotation_node':rotation_node})  # Save every modeled pin direction for audit.
    def weld(self,slave,master,rotation_node=None):  # Connect distinct component reference nodes without changing their coordinates.
        for d in range(1,4):self.equations.append([(slave,d,1.),(master,d,-1.)])  # Enforce compatible translations only between the intended endpoints.
        for d in range(3):self.equations.append([(slave,d+4,1.),(rotation_node,d+1,-1.)] if rotation_node else [(slave,d+4,1.),(master,d+4,-1.)])  # Enforce relative rotation continuity, not absolute rotation constraints.
    @staticmethod
    def area(profile):  # Calculate physical cross-section area from drawing dimensions.
        if profile[0]=='BOX':b,h,t1,t2,t3,t4=profile[1];return b*h-(b-t1-t3)*(h-t2-t4)  # Retain hollow box walls rather than a solid rectangular substitute.
        if profile[0]=='PIPE':r,t=profile[1];return math.pi*(r*r-(r-t)**2)  # Native PIPE input uses outer radius, not diameter.
        if profile[0]=='RECT':b,h=profile[1];return b*h  # Use a rectangle only when the physical member is rectangular.
        raise ValueError(profile)  # Do not silently replace an unsupported section.
    def beam(self,a,b,profile,owner,subdivisions=1,tag=''):  # Build actual B32R members with intermediate nodes and the drawn section.
        x1=self.nodes[a];x2=self.nodes[b];direction=x2-x1;length=float(np.linalg.norm(direction));axis=direction/length;trial=np.array([1.,0.,0.]) if abs(axis[0])<.9 else np.array([0.,1.,0.]);n1=trial-axis*np.dot(trial,axis);n1/=np.linalg.norm(n1)  # Define a valid local section axis independently of member direction.
        line=[a]+[self.node(x1+(x2-x1)*j/subdivisions,tag) for j in range(1,subdivisions)]+[b]  # Preserve the actual endpoints, including duplicate hinge-side nodes.
        for j in range(subdivisions):  # Use native quadratic interpolation along each beam segment.
            mid=self.node((self.nodes[line[j]]+self.nodes[line[j+1]])/2,tag);self.beams.append((line[j],mid,line[j+1],profile,tuple(n1),owner))  # Keep BOX and PIPE as their native physical sections.
        m=7850.*self.area(profile)*length;self.owners[owner]+=m;self.members.append({'kind':'beam','a':a,'b':b,'section':profile,'mass_kg':m,'owner':owner})  # Account for actual distributed steel mass exactly once.
        return line,m  # Return physical discretization and its source mass contribution.
    def shell(self,corners,thickness,owner,tag=''):  # Build a true S8R plate with shared edge nodes to preserve open-section warping.
        p=[np.asarray(v,float) for v in corners];ids=[self.node(v,tag) for v in p]+[self.node((p[j]+p[(j+1)%4])/2,tag) for j in range(4)]  # Use the native eight-node perimeter ordering.
        self.shells.append((ids,float(thickness),owner));area=np.linalg.norm(np.cross(p[1]-p[0],p[3]-p[0]));m=area*thickness*7850.;self.owners[owner]+=float(m)  # Retain physical plate area and density.
        return ids,float(m)  # Return the actual shell topology and steel mass.
    def cap(self,nodes,xyz,label):  # Represent a reinforced connection patch as a native rigid body, not a grounded reference.
        ref=self.newnode(xyz);rot=self.newnode(xyz);self.bodies.append((list(dict.fromkeys(nodes)),ref,rot,label))  # Use an explicit free rotational reference and a non-collinear physical patch.
        return ref,rot  # Expose translation and rotation references for the actual pin connection.
    def irow(self,x,z,ys,b=.17,h=.17,tw=.007,tf=.011,owner='I',tag=''):  # Model an open HW section with web and flange shells instead of locking its warping through composite solid beams.
        ys=sorted(set(float(y) for y in ys));top=z+(h-tf)/2;bottom=z-(h-tf)/2;mass0=self.owners[owner]  # Use physical flange mid-surfaces and source drawing dimensions.
        for y1,y2 in zip(ys[:-1],ys[1:]):  # Mesh at all real attachment locations along the transverse member.
            self.shell([(x,y1,bottom),(x,y2,bottom),(x,y2,top),(x,y1,top)],tw,owner,tag)  # Connect the web continuously to both flanges.
            for zz in (top,bottom):  # Keep upper and lower flanges distinct physical plates.
                for xl,xr in ((x-b/2,x),(x,x+b/2)):self.shell([(xl,y1,zz),(xl,y2,zz),(xr,y2,zz),(xr,y1,zz)],tf,owner,tag)  # Preserve open-section torsional and warping freedom.
        topnodes={y:self.node((x,y,top),tag) for y in ys};caps={}  # Retain actual upper-flange rope attachment references.
        for y in (ys[0],ys[-1]):  # Add stiff local end connection patches only where the physical post connection occurs.
            ring=[self.node((xx,y,zz),tag) for xx in (x-b/2,x,x+b/2) for zz in (top,bottom)];ring.append(self.node((x,y,z),tag));caps[y]=self.cap(ring,(x,y,z),tag+'_cap')  # Do not enforce a rigid cross-section at every interior mesh station.
        return topnodes,caps,self.owners[owner]-mass0  # Return physical supports, pin references and actual steel mass.
    def axial_member(self,a,b,EA,N,only_tension,owner,source_eid=None):  # Add a native finite-rotation axial member at its actual physical endpoints.
        L=float(np.linalg.norm(self.nodes[b]-self.nodes[a]));self.axial.append((a,b,float(EA),float(N),L,bool(only_tension),owner,source_eid))  # Preserve source axial stiffness and force instead of a fitted scalar transverse spring.
    def section_row(self,x,z,ys,profile,owner,tag=''):  # Mesh a transverse beam at every real rope or pin location.
        ys=sorted(set(float(y) for y in ys));nodes={y:self.node((x,y,z),tag) for y in ys};mass0=self.owners[owner]  # Keep exact attachment coordinates.
        for a,b in zip(ys[:-1],ys[1:]):self.beam(nodes[a],nodes[b],profile,owner,1,tag)  # Use actual flexible native beam segments, not a rigid-section assumption.
        return nodes,self.owners[owner]-mass0  # Return an attachment map and the distributed steel mass.
    def save_manifest(self,path):  # Preserve source-to-model topology and mass accounting for reproduction.
        data={'title':self.title,'node_count':len(self.nodes),'native_beams':len(self.beams),'native_shells':len(self.shells),'axial_members':len(self.axial),'relative_pins':self.joints,'rigid_offset_count':len(self.rigidlinks),'connection_patches':len(self.bodies),'steel_mass_by_owner_kg':dict(self.owners),'steel_mass_kg':sum(self.owners.values()),'lumped_mass_kg':sum(self.mass.values()),'total_mass_kg':sum(self.owners.values())+sum(self.mass.values()),'prescribed_translations_or_rotations':[list(x) for x in sorted(self.fixed)],'labels':self.labels}  # Include every physical simplification explicitly in the manifest.
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2))  # Save actual assembled counts, not intended counts.
    def write(self,path,modes=40,gravity=9.806,loads=None,prescribed=None,nonlinear=True):  # Serialize a complete native static-plus-modal calculation.
        lines=['*HEADING',self.title,'*NODE,NSET=ALL']  # Keep the actual physical model identity in the solver input.
        for n,x in self.nodes.items():lines.append(str(n)+','+','.join(number(v) for v in x))  # Preserve physical node coordinates with adequate precision.
        profiles=collections.defaultdict(list);eid=0  # Group identical native sections and orientations without altering them.
        for a,m,b,profile,n1,owner in self.beams:  # Write every real BOX or PIPE member.
            eid+=1;key=(profile[0],tuple(profile[1]),tuple(round(v,11) for v in n1));profiles[key].append((eid,a,m,b))  # Preserve each unique physical section orientation.
        lines.extend(['*MATERIAL,NAME=STEEL','*ELASTIC',number(206e9)+',0.31','*DENSITY','7850.0'])  # Use design-institute steel properties and real distributed density.
        for j,(key,rows) in enumerate(profiles.items()):  # Use native B32R section integration for hollow members.
            name=f'B{j}';lines.append(f'*ELEMENT,TYPE=B32R,ELSET={name}')  # Define the actual quadratic beam elements.
            for row in rows:lines.append(','.join(map(str,row)))  # Write physical node connectivity in start-middle-end order.
            lines.extend([f'*BEAM SECTION,ELSET={name},MATERIAL=STEEL,SECTION={key[0]}',','.join(number(v) for v in key[1]),','.join(number(v) for v in key[2])])  # Supply real dimensions rather than equivalent solid rectangles.
        shellgroups=collections.defaultdict(list)  # Group physical shell thicknesses.
        for ids,t,owner in self.shells:eid+=1;shellgroups[t].append((eid,ids))  # Retain every web and flange element.
        for j,(t,rows) in enumerate(shellgroups.items()):  # Preserve open HW sections as connected shells.
            name=f'S{j}';lines.append(f'*ELEMENT,TYPE=S8R,ELSET={name}')  # Use native reduced-integration quadratic shells.
            for element,ids in rows:lines.append(str(element)+','+','.join(map(str,ids)))  # Preserve all eight physical nodes.
            lines.extend([f'*SHELL SECTION,ELSET={name},MATERIAL=STEEL',number(t)])  # Retain actual plate thickness.
        steel_eids=list(range(1,eid+1));laws=collections.defaultdict(list)  # Separate distributed steel gravity from preloaded axial members.
        for a,b,EA,N,L,tension,owner,source_eid in self.axial:  # Group identical original-state axial laws only.
            eid+=1;key=(round(EA/L,5),round(N,7),round(L,10),tension);laws[key].append((eid,a,b))  # Keep physical endpoints and initial-force equivalence.
        for j,(key,rows) in enumerate(laws.items()):  # Write source-based nonlinear axial laws directly to CalculiX.
            name=f'C{j}';lines.append(f'*ELEMENT,TYPE=SPRINGA,ELSET={name}')  # Use native spatial force directions and initial-force stiffness.
            for row in rows:lines.append(','.join(map(str,row)))  # Keep all actual cable segments present.
            k,N,L,tension=key;extent=max(.02*L,2*abs(N)/k+.001);pairs=[(0.,-N/k-extent),(0.,-N/k),(N,0.),(N+k*extent,extent)] if tension else [(N-k*extent,-extent),(N,0.),(N+k*extent,extent)]  # Keep ropes tension-only and other rods bidirectional.
            lines.append(f'*SPRING,ELSET={name},NONLINEAR')  # Specify the physical force-extension relation, not a frequency-dependent spring.
            for force,u in pairs:lines.append(number(force)+','+number(u))  # Include a decimal point in the first native field.
        massgroups=collections.defaultdict(list)  # Preserve concentrated physical masses while reducing redundant native property cards.
        for n,m in self.mass.items():  # Group masses only below physically negligible serialization roundoff.
            if m>0:eid+=1;massgroups[round(m,8)].append((eid,n))  # Keep every nonstructural mass and rope mass at its actual point.
        for j,(m,rows) in enumerate(massgroups.items()):  # Add physical inertia exactly once.
            name=f'M{j}';lines.append(f'*ELEMENT,TYPE=MASS,ELSET={name}')  # Use native concentrated-mass elements.
            for row in rows:lines.append(','.join(map(str,row)))  # Preserve mass-point node identity.
            lines.extend([f'*MASS,ELSET={name}',number(m)])  # Store mass in kilograms.
        if steel_eids:lines.extend(['*ELSET,ELSET=STEELALL,GENERATE',f'1,{max(steel_eids)},1'])  # Select native steel elements for their physical gravity load.
        for j,(members,ref,rot,label) in enumerate(self.bodies):  # Preserve only actual local rigid connection patches.
            lines.append(f'*NSET,NSET=RB{j}')  # Name the physical patch without attaching it to ground.
            for start in range(0,len(members),12):lines.append(','.join(map(str,members[start:start+12])))  # Stay within native line-length limits.
            lines.append(f'*RIGID BODY,NSET=RB{j},REF NODE={ref},ROT NODE={rot}')  # Use native finite-rotation rigid-body equations.
        for reference,slave in self.rigidlinks:lines.extend(['*MPC',f'BEAM,{reference},{slave}'])  # Preserve offset translation-rotation coupling with native nonlinear kinematics.
        if self.equations:lines.append('*EQUATION')  # Enforce relative joint freedoms rather than artificial absolute rotational supports.
        for terms in self.equations:  # Write every intended physical compatibility equation.
            lines.append(str(len(terms)))  # Declare the exact number of nonzero coefficients.
            for start in range(0,len(terms),3):lines.append(','.join(f'{n},{d},{number(c)}' for n,d,c in terms[start:start+3]))  # Keep each native line within its parser width.
        if self.fixed:lines.append('*BOUNDARY')  # Apply only actual source supports and explicitly identified unit-test supports.
        for n,d in sorted(self.fixed):lines.append(f'{n},{d},{d}')  # Do not add rotation locks for numerical convenience.
        obs=self.observation or sorted(self.nodes);lines.append('*NSET,NSET=OBS')  # Preserve physical observation points and complete mode fields.
        for start in range(0,len(obs),12):lines.append(','.join(map(str,obs[start:start+12])))  # Write bounded-length set records.
        lines.extend(['*STEP,NLGEOM,INC=100' if nonlinear else '*STEP','*STATIC','1.,1.,1.e-8,1.'])  # Equilibrate at the full permanent-load state rather than unloading a prestressed model.
        if gravity and steel_eids:lines.extend(['*DLOAD',f'STEELALL,GRAV,{number(gravity)},0.,0.,-1.'])  # Apply steel selfweight once through its real density.
        f=collections.defaultdict(float)  # Accumulate explicit point forces separately from steel gravity.
        for n,m in self.mass.items():f[(n,3)]-=m*gravity  # Apply gravity consistently with each physical concentrated mass.
        for n,d,v in loads or []:f[(n,d)]+=v  # Add only declared unit-test or external physical loads.
        if f:lines.append('*CLOAD')  # Write the actual concentrated force vector.
        for (n,d),value in f.items():  # Keep point forces in their intended Cartesian direction.
            if value:lines.append(f'{n},{d},{number(value)}')  # Preserve physical signs and SI units.
        if prescribed:lines.append('*BOUNDARY')  # Use prescribed displacements only for explicitly labeled local connection tests.
        for n,d,v in prescribed or []:lines.append(f'{n},{d},{d},{number(v)}')  # Do not insert these diagnostic displacements into the full bridge baseline.
        lines.extend(['*NODE PRINT,NSET=OBS','U,RF','*NODE FILE,OUTPUT=2D','U','*END STEP'])  # Save physical centerline and shell-node responses at equilibrium.
        if modes:lines.extend(['*STEP,PERTURBATION','*FREQUENCY',str(modes),'*NODE PRINT,NSET=OBS','U','*NODE FILE,OUTPUT=2D','U','*END STEP'])  # Keep every computed eigenvalue and displacement field, including unstable negative roots; numerical extraction order still requires separate verification.
        path.write_text('\n'.join(lines)+'\n')  # Save the complete executable native input.
