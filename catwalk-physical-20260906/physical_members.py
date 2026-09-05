import numpy as np  # Use actual physical positions and native finite-element interpolation.
BOX50=('BOX',(.05,.05,.004,.004,.004,.004))  # Small floor crossbeam from the original drawing family.
BOX100=('BOX',(.10,.10,.004,.004,.004,.004))  # Large floor crossbeam from the original drawing family.
BOX160=('BOX',(.16,.16,.004,.004,.004,.004))  # Ordinary and passage gantry steel tube from the original review.
CHORD=('PIPE',(.076,.006));WEB=('PIPE',(.051,.004));DIAGONAL=('PIPE',(.0255,.004));HANGER=('CIRC',(.02,.02))  # Preserve the original truss member sizes and an explicitly declared hanger-rod idealization.
class BeamLine:  # Mesh one actual flexible native transverse member and attach ports at their true coordinates.
    def __init__(self,deck,x,z,ys,profile,owner,tag):  # Use quadratic physical beam elements rather than rigid cross-section translation ties.
        self.d=deck;self.x=float(x);self.z=float(z);self.ys=np.array(sorted(set(float(v) for v in ys)));self.profile=profile;self.owner=owner;self.tag=tag;self.segments=[];self.ports={};start=deck.owners[owner]  # Retain the real member identity and its mass contribution.
        for y1,y2 in zip(self.ys[:-1],self.ys[1:]):  # Preserve actual flexible element spans.
            a=deck.node((x,y1,z),tag);b=deck.node((x,y2,z),tag);deck.beam(a,b,profile,owner,1,tag);m=deck.node((x,(y1+y2)/2,z),tag);self.segments.append((a,m,b))  # Reuse the native B32R start-middle-end nodes.
        self.mass=deck.owners[owner]-start  # Record actual native distributed steel mass once.
    def section(self,y):  # Interpolate section motion at an actual rope clamp or connection position without moving that position onto a mesh node.
        y=float(y);key=round(y,9)  # Preserve sub-millimetre port geometry.
        if key in self.ports:return self.ports[key]  # Use one section motion for all points on the same physical clamp.
        i=int(np.clip(np.searchsorted(self.ys,y,side='right')-1,0,len(self.segments)-1));a,b=self.ys[i:i+2];xi=2*(y-a)/(b-a)-1.;weights=np.array([xi*(xi-1)/2,1-xi*xi,xi*(xi+1)/2]);nodes=self.segments[i]  # Use the native quadratic beam interpolation, preserving partition of unity and the physical lever arm.
        ref=self.d.newnode((self.x,y,self.z));rot=self.d.newnode((self.x,y,self.z))  # Create section reference coordinates without an added support, spring or mass.
        for direction in range(3):  # Interpolate both translations and actual native section rotations.
            self.d.equations.append([(ref,direction+1,1.)]+[(n,direction+1,-float(w)) for n,w in zip(nodes,weights) if abs(w)>1.e-13])  # Transfer physical point forces by virtual-work-consistent interpolation.
            self.d.equations.append([(rot,direction+1,1.)]+[(n,direction+4,-float(w)) for n,w in zip(nodes,weights) if abs(w)>1.e-13])  # Retain flexible beam rotation instead of setting it equal to zero.
        members=[];self.d.bodies.append((members,ref,rot,self.tag+'_section'))  # Exactly eliminate unreferenced massless orientation witnesses; actual attachments still receive the same finite-offset rigid-body equations from the independently interpolated section coordinates.
        self.ports[key]=(ref,rot);return ref,rot  # Return the physical section's free translational and rotational references.
    def attach(self,y,xyz,existing=None,mass=0.):  # Attach a rope, clamp or nonstructural mass at its actual physical position.
        ref,rot=self.section(y)  # Preserve the local flexible beam response at the requested physical station.
        if existing is None:return self.d.lever_from_body(ref,rot,xyz,mass)  # Use the real finite-rotation lever arm.
        members=self.d.body_members(ref,rot)  # Resolve the same physical clamp's original member list through the append-only body index.
        if members is None:raise RuntimeError('Native connection body was not found')  # Preserve the original missing-body error without creating a replacement connection.
        members.append(existing);self.d.add_mass(existing,mass);return existing  # Preserve the existing physical cable node, insertion order and exactly-once mass allocation.
    def mass_at(self,y,z,mass):return self.attach(y,(self.x,y,z),mass=mass)  # Keep spatial inertia at the actual component elevation.
def ordinary_gantry(d,xf,zf,xu,zu,center,upper_points,lower_points,tag,post_axis=0,beam_cells=6):  # Build an ordinary gantry from actual upper/lower source stations and relative pin joints.
    top_owner=tag+'_upper';bottom_owner=tag+'_bottom';top=BeamLine(d,xu,zu-.105,np.linspace(center-3.73,center+3.73,beam_cells+1),BOX160,top_owner,tag+'_top')  # Preserve the actual upper beam width and its rope-bearing offset.
    for y,node in upper_points:top.attach(y,d.nodes[node],existing=node)  # Keep all six independent upper ropes at separate physical clamps.
    ys=sorted(set([center-2.95,center+2.95]+[float(y) for y,node in lower_points]));tops,caps,bottom_mass=d.irow(xf,zf-.110,ys,owner=bottom_owner,tag=tag+'_HW')  # Use a true open HW shell section, not an arbitrarily rigid floor reference.
    for y,node in lower_points:d.point_on_surface(tops[float(y)],d.nodes[node],existing=node)  # Connect all sixteen floor ropes with their actual vertical clamp offset.
    for sign in (-1,1):  # Preserve both columns and their separate upper and lower force paths.
        y=center+sign*2.95;upref,uprot=top.section(y);up=d.newnode(d.nodes[upref]);footref,footrot=caps[y];foot=d.newnode(d.nodes[footref]);knee=d.node(d.nodes[up]+(d.nodes[foot]-d.nodes[up])*min(.32,2.5/np.linalg.norm(d.nodes[foot]-d.nodes[up])),tag+'_post')  # Retain the source's slight longitudinal upper/lower station offset.
        d.beam(up,knee,BOX160,top_owner,2,tag+'_post');d.beam(knee,foot,BOX160,top_owner,3,tag+'_post');d.pin(up,upref,post_axis,uprot,tag+'_upper_pin');d.pin(foot,footref,post_axis,footrot,tag+'_lower_pin')  # Release only relative rotation about the stated pin axis.
        bref,brot=top.section(center+sign*3.73);brace_top=d.newnode(d.nodes[bref]);d.beam(brace_top,knee,BOX160,top_owner,2,tag+'_brace');d.pin(brace_top,bref,post_axis,brot,tag+'_brace_pin')  # Preserve the knee brace's force couple through a second separated top connection.
    return top,{'upper_owner':top_owner,'bottom_owner':bottom_owner,'bottom_mass_kg':bottom_mass,'caps':caps}  # Expose mass ownership and physical connections for source-budget accounting.
def passage(d,xf,zf,slope,upper_geometry,upper_ports,floor_port,centers,tag,post_axis=0,fork_axis=1,bay_count=33,beam_cells=6):  # Build one entire 49.65 m inverted-triangle truss, its collectors and two forked gantries.
    direction=np.array([1.,0.,slope]);direction/=np.linalg.norm(direction);normal=np.cross(direction,np.array([0.,1.,0.]));origin=np.array([xf,0.,zf])-.4*normal  # Preserve physical cross-passage depth and grade-following orientation; the 0.4 m mounting depth is an explicit connection-detail assumption.
    top_coordinates=[origin+sign*.75*direction for sign in (-1,1)];bottom_coordinate=origin-1.75*normal;ys=np.linspace(-24.825,24.825,bay_count+1);owner=tag+'_truss';chords=[]  # Use the original overall length, width and truss depth.
    for k,p in enumerate(top_coordinates+[bottom_coordinate]):chords.append(BeamLine(d,p[0],p[2],ys,CHORD,owner,tag+'_chord'+str(k)))  # Preserve three separate physical tubular chords.
    for j,y in enumerate(ys):  # Add the transverse triangular frames at actual declared module panel boundaries.
        p=[d.node((line.x,y,line.z),line.tag) for line in chords]  # Share only the intended welded tubular joints.
        d.beam(p[0],p[1],WEB,owner,1,tag+'_cross');d.beam(p[0],p[2],WEB,owner,1,tag+'_cross');d.beam(p[1],p[2],WEB,owner,1,tag+'_cross')  # Preserve the real spatial triangular section instead of a scalar transverse spring.
        if j<bay_count:  # Connect the longitudinal truss panels without inserting extra braces at interpolation-only rope ports.
            yn=ys[j+1];pn=[d.node((line.x,yn,line.z),line.tag) for line in chords];low=p[2] if j%2==0 else pn[2];high=pn[:2] if j%2==0 else p[:2]  # Use an explicitly declared alternating diagonal panel idealization.
            for n in high:d.beam(low,n,DIAGONAL,owner,1,tag+'_diagonal')  # Retain both inclined longitudinal webs.
            d.beam(p[0] if j%2==0 else p[1],pn[1] if j%2==0 else pn[0],DIAGONAL,owner,1,tag+'_top_diagonal')  # Include top-plane triangulation rather than leaving a shear mechanism.
    collectors=[];tops=[];gate_owners=[]  # Keep passage hangers and gantries distinct from the ordinary gate family.
    for deck,center in enumerate(centers):  # Build each catwalk's actual multi-point connection to the common truss.
        collector_owner=tag+'_collectors';deck_collectors=[]  # Attribute collector steel to the cross-passage's original mass budget.
        for k,line in enumerate(chords[:2]):  # Connect both longitudinal sides of the 1.5 m wide truss to the floor-rope array.
            points=floor_port(deck,line.x);floorz=float(np.mean([d.nodes[n][2] for y,n in points]));collector=BeamLine(d,line.x,floorz-.075,np.linspace(center-2.89,center+2.89,beam_cells+1),BOX100,collector_owner,tag+f'_collector{deck}_{k}')  # Model a flexible actual collector beam at the physical rope station.
            for y,node in points:  # Preserve sixteen separate rope clamps at each collector rather than two abstract supports.
                collector.attach(y,d.nodes[node],existing=node);upref,uprot=collector.section(y);lowref,lowrot=line.section(y);a=d.newnode(d.nodes[upref]);b=d.newnode(d.nodes[lowref]);d.beam(a,b,HANGER,collector_owner,1,tag+'_hanger');d.weld(a,upref,uprot);d.weld(b,lowref,lowrot)  # Carry load through explicit finite hanger rods and relative connection kinematics.
            deck_collectors.append(collector)  # Retain the two fore/aft physical collectors independently.
        xu,zu=upper_geometry[deck];gate_owner=tag+f'_gate{deck}';top=BeamLine(d,xu,zu-.105,np.linspace(center-3.73,center+3.73,beam_cells+1),BOX160,gate_owner,tag+f'_top{deck}')  # Preserve the MCT upper rope station independently of the floor station.
        for y,node in upper_ports[deck]:top.attach(y,d.nodes[node],existing=node)  # Keep all six upper rope attachments physically distinct.
        for sign in (-1,1):  # Build the two forked column assemblies, not an ordinary two-column rectangle.
            y=center+sign*2.95;upref,uprot=top.section(y);apex=d.newnode(d.nodes[upref]);d.pin(apex,upref,post_axis,uprot,tag+'_fork_top')  # Use the stated upper pin axis with relative rather than absolute rotation release.
            knee_nodes=[]  # Preserve two separate longitudinal fork legs and their brace attachment points.
            for k,line in enumerate(chords[:2]):  # Connect the fork to both real truss upper chords.
                ref,rot=line.section(y);foot=d.newnode(d.nodes[ref]);knee=d.node(d.nodes[apex]+(d.nodes[foot]-d.nodes[apex])*.28,tag+f'_fork{deck}_{sign}_{k}');d.beam(apex,knee,BOX160,gate_owner,2,tag+'_fork');d.beam(knee,foot,BOX160,gate_owner,3,tag+'_fork');d.pin(foot,ref,fork_axis,rot,tag+'_fork_foot');knee_nodes.append(knee)  # Retain the physical longitudinal fork spread and lower chord clamp pins.
            ref,rot=top.section(center+sign*3.73)  # Preserve the knee-brace connection outside the vertical column centerline.
            for knee in knee_nodes:  # Connect both fork branches to the outer upper-beam pin through actual diagonal steel.
                a=d.newnode(d.nodes[ref]);d.beam(a,knee,BOX160,gate_owner,2,tag+'_fork_brace');d.pin(a,ref,post_axis,rot,tag+'_fork_brace_pin')  # Do not remove the second physical fork branch to reduce the model size.
        collectors.append(deck_collectors);tops.append(top);gate_owners.append(gate_owner)  # Expose each real gantry and its mass source separately.
    return {'chords':chords,'collectors':collectors,'tops':tops,'gate_owners':gate_owners,'truss_owner':owner,'collector_owner':tag+'_collectors','mounting_offset_m':.4,'panel_count':bay_count,'panelization_status':'Declared idealization pending complete numeric reading of raster module detail drawing'}  # Keep uncertain local details explicit rather than mislabel them as verified drawing dimensions.
