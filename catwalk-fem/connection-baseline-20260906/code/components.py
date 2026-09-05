import numpy as np # Construct spatial components from actual drawing dimensions and MCT station geometry.
from native_model import Model # Use native hollow-section beams, physical clamps and relative pin releases.
YLOW=np.r_[-(.85+.26*np.arange(7,-1,-1)),.85+.26*np.arange(8)] # Preserve the16 actual lower-rope positions across each catwalk.
YUP=np.array([-2.26,-2.,-1.74,1.74,2.,2.26]) # Preserve the6 actual upper-rope positions rather than one merged top point.
def ordinary(m,lower,upper,cy,pin=5): # Build one ordinary elastic gantry, not the passage's forked support.
    x0=m.X[lower[0]-1][0];z0=m.X[lower[0]-1][2];xt=m.X[upper[0]-1][0];zt=m.X[upper[0]-1][2];H=zt-z0;start=len(m.beams) # Use actual upper and lower MCT attachment locations.
    low=[m.node([x0,cy+y,z0],'ordinary_H') for y in [-3.075,0.,3.075]];m.hbeam(low[0],low[2],'ordinary_H170',mid=low[1]);hb=list(range(start,len(m.beams))) # Retain the elastic bottom beam and real width.
    for n,y in zip(lower,YLOW):m.interpolate(n,low,[-3.075,0.,3.075],y) # Attach all16 distinct lower ropes to their actual transverse positions.
    bot=[] # Preserve the two separate column-foot locations.
    for y in [-2.95,2.95]:n=m.node([x0,cy+y,z0],'ordinary_foot');m.interpolate(n,low,[-3.075,0.,3.075],y,dirs=range(1,7));bot.append(n) # Keep the actual column base offsets on the bottom beam.
    ys=sorted(set([-3.73,-3.65,-2.95,*YUP,2.95,3.65,3.73]));top={} # Retain upper clamps, column heads and brace attachments.
    for y in ys:top[y]=upper[int(np.argmin(abs(YUP-y)))] if min(abs(YUP-y))<1e-7 else m.node([xt,cy+y,zt],'ordinary_top') # Never merge distinct upper ropes by proximity to the centreline.
    st=len(m.beams) # Separate top-frame mass from bottom-beam mass.
    for a,b in zip(ys[:-1],ys[1:]):m.shs(top[a],top[b],.16,.006,'ordinary_top160x6') # Use the selected current drawing's actual hollow top-beam section.
    for sign,foot in zip([-1,1],bot): # Build each column, inserted inner member and brace separately.
        y=sign*2.95;head=top[y];Linner=max(.5,H-6.423);zi=z0+Linner;zb=zt-1.67;mid=m.node([x0,cy+y,zi],'ordinary_overlap');brace=m.node([x0,cy+y,zb],'ordinary_brace_joint') # Preserve documented dimensions and explicitly interpolated overlap geometry.
        m.shs(foot,mid,.14,.006,'ordinary_inner140x6',pin_i=True,pin=pin);m.shs(mid,brace,.16,.004,'ordinary_outer160x4');m.shs(brace,head,.16,.004,'ordinary_outer160x4',pin_j=True,pin=pin);m.shs(brace,top[sign*3.65],.16,.004,'ordinary_brace160x4',pin_i=True,pin_j=True,pin=pin) # Release local relative pin rotation rather than grounding a frame rotation.
    m.distribute_weight(list(range(st,len(m.beams))),8927.);m.distribute_weight(hb,3180.) # Transfer the original permanent component weights once to the actual elastic members.
    for n in upper:m.mass[n]-=8927./9.806/6 # Remove source mass already transferred to the constructed frame.
    for n in lower:m.mass[n]-=3180./9.806/16 # Remove source mass already transferred to the bottom beam.
    m.logs.append(dict(kind='ordinary',x=x0,upper_x=xt,height=H,pin_global_axis=pin,beam_range=[start,len(m.beams)])) # Retain actual construction decisions for subsequent audit.
def passage(m,x,lower_at,upper_at,zfloor,centres,shift=0.,pin=5): # Construct an actual modular triangular truss with its two different support systems.
    start=len(m.beams);B=42.9;L=49.655;y0=-L/2;zv=np.array([zfloor(x-.75),zfloor(x+.75)]);base=float(min(zv)-.101);high=int(zv[1]>zv[0]);rise=float(abs(np.diff(zv)[0])) # Keep true fore/aft rope heights and clamp-to-tube-centre offset.
    modules=[];s=0. # Preserve the actual module lengths and their internal panel positions.
    for kind,length in [('tail',7.435),('mid',9.54),('mid',9.54),('short',6.165),('mid',9.54),('tailR',7.435)]: # Do not replace the passage by a uniform equivalent shear beam.
        if kind.startswith('tail'):t=np.array([0,.15,.6,1.725,3.3775,5.03,6.155,7.165,7.435]);b=np.array([.4,.6,2.85,3.905,6.155,7.165,7.435]);diag=[(.6,.6),(1.725,.6),(1.725,2.85),(3.3775,2.85),(3.3775,3.905),(5.03,3.905),(5.03,6.155),(6.155,6.155),(7.165,7.165),(7.435,7.435)] # Retain the documented tail-module panel geometry.
        elif kind=='mid':t=np.array([0,.27,2.52,4.77,7.02,9.27,9.54]);b=np.array([0,.27,1.395,3.645,5.895,8.145,9.27,9.54]);diag=[(0,0),(.27,.27),(.27,1.395),(2.52,1.395),(2.52,3.645),(4.77,3.645),(4.77,5.895),(7.02,5.895),(7.02,8.145),(9.27,8.145),(9.27,9.27),(9.54,9.54)] # Retain the middle module's staggered Warren web.
        else:t=np.array([0,.27,2.52,4.77,5.895,6.165]);b=np.array([0,.27,1.395,3.645,5.895,6.165]);diag=[(0,0),(.27,.27),(.27,1.395),(2.52,1.395),(2.52,3.645),(4.77,3.645),(4.77,5.895),(5.895,5.895),(6.165,6.165)] # Keep the actual shorter additional module.
        if kind=='tailR':t=length-t;b=length-b;diag=[(length-a,length-c) for a,c in diag] # Mirror the opposite tail's actual connectivity.
        modules.append(dict(t=np.sort(t+s+y0),b=np.sort(b+s+y0),diag=[(a+s+y0,c+s+y0) for a,c in diag],left=s+y0,right=s+length+y0));s+=length # Preserve actual global transverse module locations.
    def node(side,y):return m.node([x+[-.75,.75,0][side],y,base if side<2 else base-1.7],f'passage_{side}',merge=True) # Keep both top chords and the separate lower chord.
    topstations=set(round(v,8) for q in modules for v in q['t']);bottomstations=set(round(v,8) for q in modules for v in q['b']) # Start from real module joints.
    ya=np.array([-2.54,-2.02,-1.50,-.98,0.,.98,1.50,2.02,2.54]);yd=np.array([-2.7775,-2.02,-1.50,-.5275,0.,.5275,1.50,2.02,2.7775]) # Retain distinct vertical and sloping connector positions.
    for cy in centres:topstations.update(round(cy+v,8) for v in np.r_[YLOW,[-2.95,2.95,-2.82,2.82],ya,yd]) # Insert actual clamp and support locations without snapping them to panel joints.
    ts=sorted(topstations);bs=sorted(bottomstations) # Preserve native beam connectivity along each separate chord.
    for side in [0,1]: # Retain both longitudinal edges of the passage top plane.
        for a,b in zip(ts[:-1],ts[1:]):m.pipe(node(side,a),node(side,b),.152,.006,'passage_top152x6') # Use actual elastic tube sections.
    for a,b in zip(bs[:-1],bs[1:]):m.pipe(node(2,a),node(2,b),.152,.006,'passage_bottom152x6') # Preserve the lower chord's separate axial-force couple.
    seen=set() # Avoid double-creating a shared module-end member.
    def bar(a,b,D,t,label): # Create one physical truss member at a documented connection.
        key=tuple(sorted([a,b])) # Identify the actual member endpoints.
        if key in seen or a==b:return # Do not count shared module joints twice.
        seen.add(key);m.pipe(a,b,D,t,label) # Keep welded tubular truss joints as shared beam nodes.
    for q in modules: # Build every triangular module explicitly.
        for a,c in q['diag']: # Retain actual staggered face-web connections.
            for side in [0,1]:bar(node(side,round(a,8)),node(2,round(c,8)),.102 if abs(a-c)<1e-7 else .051,.004,'passage_web') # Distinguish transverse posts from diagonal web tubes.
        for yy in q['t']:bar(node(0,round(yy,8)),node(1,round(yy,8)),.102,.004,'passage_top_cross') # Keep actual top-plane cross members.
        for a,b in zip(q['t'][1:-2],q['t'][2:-1]):bar(node(0,round(a,8)),node(1,round(b,8)),.051,.004,'passage_plan_diag');bar(node(1,round(a,8)),node(0,round(b,8)),.051,.004,'passage_plan_diag') # Retain top-plane triangulation rather than a shear-only surrogate.
    for deck,cy in enumerate(centres): # Construct each catwalk's separate clamp and inclined connection frame.
        if rise>1e-6: # Never create a zero-length connector on the flat central passage.
            ys=sorted(set(round(cy+v,8) for v in np.r_[YLOW,[-2.82,2.82],ya,yd]));raised={y:m.node([x+[-.75,.75][high],y,base+rise],'raised_clamp_pipe') for y in ys} # Retain the actual raised tubular support under the higher rope row.
            for a,b in zip(ys[:-1],ys[1:]):m.pipe(raised[a],raised[b],.152,.006,'inclination_pipe152x6') # Preserve the sloping catwalk's physical transverse attachment frame.
            for y in ya:bar(node(high,round(cy+y,8)),raised[round(cy+y,8)],.06,.006,'inclination_vertical60x6') # Keep the nine vertical linking members.
            for y in yd:bar(node(1-high,round(cy+y,8)),raised[round(cy+y,8)],.06,.006,'inclination_slant60x6') # Keep the nine spatial sloping members.
        for side in [0,1]: # Keep front and rear rope rows physically separate.
            for rn,y in zip(lower_at[deck,side],YLOW): # Attach each of the16 ropes at its own location.
                beam=raised[round(cy+y,8)] if rise>1e-6 and side==high else node(side,round(cy+y,8));m.clamp(rn,beam) # Preserve the clamp's real offset instead of merging rope and chord centreline nodes.
    core=list(range(start,len(m.beams)));m.distribute_weight(core,2*49690.) # Retain the design-institute permanent passage weight without adding a duplicate density load.
    for deck,cy in enumerate(centres): # Build the separate forked passage gantry on each catwalk.
        u=upper_at[deck];xt=m.X[u[0]-1][0];zt=m.X[u[0]-1][2];ys=sorted(set([-4.06,-3.65,-2.95,*YUP,2.95,3.65,4.06]));top={};st=len(m.beams) # Preserve actual upper-clamp coordinates and the special gantry width.
        for y in ys:top[y]=u[int(np.argmin(abs(YUP-y)))] if min(abs(YUP-y))<1e-7 else m.node([xt,cy+y,zt],'special_top') # Keep six distinct upper rope attachments.
        for a,b in zip(ys[:-1],ys[1:]):m.shs(top[a],top[b],.16,.006,'special_top160x6') # Retain the special gantry's actual top member.
        for sign in [-1,1]: # Construct both spatial forked column assemblies.
            y=sign*2.95;head=top[y];branch=m.node([xt,cy+y,zt-2.265],'special_branch');m.shs(branch,head,.14,.005,'special_upper140x5',pin_j=True,pin=pin) # Keep the real upper pin and branch point.
            for side in [0,1]: # Preserve both front and rear legs instead of a single planar column.
                foot=node(side,round(cy+y,8));P=m.X[foot-1];Q=m.X[branch-1];ell=np.linalg.norm(Q-P);mid=m.node(P+(Q-P)*min(1.5/ell,.45),'special_inner_joint');m.shs(foot,mid,.12,.005,'special_inner120x5',pin_i=True,pin=pin);m.shs(mid,branch,.14,.005,'special_leg140x5') # Keep separately declared telescopic-member geometry and local foot release.
            brace=m.node([xt,cy+y,zt-1.67],'special_brace_attach');m.interpolate(brace,[branch,m.beams[-5]['m'] if False else branch,head],[0,1,2],1) if False else None # Retain the explicit split rather than introducing a nonexistent interpolation constraint.
            old_index=st+(len(ys)-1)+(0 if sign==-1 else 7);target=next(b for b in m.beams[st:] if b['i']==branch and b['name']=='special_upper140x5');oldmid=target['m'];target['j']=brace;target['m']=m.node((m.X[branch-1]+m.X[brace-1])/2,'special_upper_mid');m.shs(brace,head,.14,.005,'special_upper140x5',pin_j=True,pin=pin);m.shs(brace,top[sign*3.65],.16,.004,'special_brace160x4',pin_i=True,pin_j=True,pin=pin) # Split the actual upright at the brace attachment without grounding its rotation.
        m.distribute_weight(list(range(st,len(m.beams))),12360.) # Preserve the source's special gantry permanent weight.
        for n in u:m.mass[n]-=12360./9.806/6 # Remove only mass already transferred onto the constructed special gantry.
    m.logs.append(dict(kind='passage',x=x,rise=rise,high_side=high,beam_range=[start,len(m.beams)],pin_global_axis=pin,physical_clamp_offset_m=.101)) # Retain the actual module, slope and connector decisions for verification.
