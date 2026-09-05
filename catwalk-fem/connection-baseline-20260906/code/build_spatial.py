from source_state import R,parse,ccx # Use original source geometry, initial force and permanent loads only.
from native_model import Model # Assemble actual native hollow-section beams and physical attachments.
from components import YLOW,YUP,ordinary,passage # Keep ordinary and forked passage gantries structurally distinct.
import numpy as np,json,sys,hashlib,time,shutil # Preserve source provenance and actual native solver evidence.
def build(spacing=3.,pin=5): # Keep small crossbeams at their real3m spacing in the formal model.
    d=parse();state=np.load(R/'runs/source_state/state.npz');ids=state['ids'];xeq=state['X']+state['u'];xyz={int(n):p for n,p in zip(ids,xeq)};m=Model();centres=[-21.45,21.45] # Transfer this run's independently solved MCT state into both actual catwalk locations.
    nid_index={n:i for i,n in enumerate(ids)};N=state['N'];kk=state['k'];L=state['L'];lower_orig=sorted([n for n in ids if n<1000 and n<=728],key=lambda n:xyz[n][0]);xa=np.array([xyz[n][0] for n in lower_orig]);za=np.array([xyz[n][2] for n in lower_orig]) # Preserve all source lower-rope vertices, including short saddle and anchor transitions.
    def zf(x):return float(np.interp(x,xa,za)) # Interpolate only within the actual source polyline.
    portals=[e for e in d['elements'] if e['type']=='TRUSS'];passages=[];pairs=[] # Classify actual source members rather than hard-coding a guessed frame count.
    for e in portals: # Preserve exact upper/lower attachment pairs.
        lo,up=sorted([e['i'],e['j']]);x=xyz[lo][0];special=abs(d['point'][up]-21556.)<1 # The original permanent load identifies the special passage support stations.
        pairs.append((lo,up,x,special)) # Keep the source station pairing.
        if special:passages.append((lo,up,x)) # Retain all21 actual cross-passage locations.
    arcs=np.r_[0,np.cumsum(np.hypot(np.diff(xa),np.diff(za)))];stations=np.arange(spacing/2,arcs[-1],spacing);smallx=np.interp(stations,arcs,xa) # Locate the real small beams by lower-rope arc distance rather than rounding horizontal stations.
    specialx=[x for lo,up,x in passages];smallx=np.array([x for x in smallx if min(abs(x-np.array(specialx)))>.9]);insert=np.unique(np.r_[smallx,np.ravel([[x-.75,x+.75] for x in specialx])]);lnodes={n:xyz[n] for n in ids if n<1000};next_id=2000;atx={} # Keep separate front/rear passage connections and avoid coincident duplicate beams.
    for x in insert: # Insert only actual structural attachment and discretization stations.
        j=np.argmin(abs(xa-x)) # Identify a genuinely coincident original station.
        if abs(xa[j]-x)<1e-7:n=lower_orig[j] # Never replace an original source vertex.
        else:n=next_id;next_id+=1;lnodes[n]=np.array([x,0.,zf(x)]) # Preserve the source polyline between existing vertices.
        atx[round(x,8)]=n # Record the exact inserted station mapping.
    copies={};source_lower_ids=set(n for n in ids if n<1000);source_upper_ids=set(n for n in ids if n>=1000) # Keep both original rope layers and all source support nodes.
    for deck,cy in enumerate(centres): # Expand each original layer into its actual number of spatial ropes.
        for n,p in list(lnodes.items())+[(n,xyz[n]) for n in source_upper_ids]: # Preserve all original geometry and newly required physical intersections.
            offsets=YLOW if n in lnodes else YUP;copies[n,deck]=[m.node(p+[0,cy+y,0],f'source{n}_deck{deck}_rope{j}') for j,y in enumerate(offsets)] # Keep every transverse rope position explicit.
            for rn in copies[n,deck]:m.mass[rn]+=d['point'].get(n,0)/9.806/len(offsets) # Split the original aggregate point weight once among that source bundle.
    all_lower=sorted(lnodes,key=lambda n:lnodes[n][0]);xall=np.array([lnodes[n][0] for n in all_lower]);parent_elements=[] # Retain an auditable source-parent map for each native rope segment.
    for ei,e in enumerate(d['elements']): # Transfer initial force and axial tangent from the same newly solved source state.
        if e['type']!='TENSTR':continue # Physical gantries are rebuilt as real spatial beam structures below.
        i,j=e['i'],e['j'];P,Q=xyz[i],xyz[j];Leq=np.linalg.norm(Q-P);count=16 if e['mat']==1 else 6 # Preserve source aggregation and the actual number of corresponding ropes.
        if e['mat']==1 and abs(Q[0]-P[0])>1e-7: # Refine along the existing source element, not along a new fitted curve.
            a,b=sorted([P[0],Q[0]]);sel=[all_lower[q] for q in np.where((xall>a+1e-7)&(xall<b-1e-7))[0]];chain=[i]+sel+[j] if P[0]<Q[0] else [i]+sel[::-1]+[j] # Keep original element endpoints and orientation.
        else:chain=[i,j] # Preserve vertical equivalent downpull links and original upper-rope segments.
        for aa,bb in zip(chain[:-1],chain[1:]): # Split force and rest-length compatibility consistently.
            Pa=lnodes[aa] if aa in lnodes else xyz[aa];Pb=lnodes[bb] if bb in lnodes else xyz[bb];fraction=np.linalg.norm(Pb-Pa)/Leq;W=d['gamma'][e['mat']]*d['A'][e['sec']]*L[ei]*fraction # Preserve original self weight along the source parent element.
            for deck in range(2): # Keep both catwalks physically independent except at their actual connecting structure.
                for ni,nj in zip(copies[aa,deck],copies[bb,deck]):m.ropes.append((ni,nj,float(N[ei]/count),float(kk[ei]/fraction/count)));m.mass[ni]+=W/9.806/count/2;m.mass[nj]+=W/9.806/count/2;parent_elements.append(e['id']) # Preserve tension, axial compliance and mass on every native segment.
    for n,axis in d['fixed']: # Map only the original physical support directions into space.
        for deck in range(2): # Do not transfer the planar verification's artificial out-of-plane restriction.
            for rn in copies[n,deck]:m.fixed[rn,axis+1]=0. # Leave unrestrained spatial translations and rotations free.
    portal_lower={lo for lo,up,x,special in pairs} # Avoid building the same gantry-support beam twice.
    for x in smallx: # Keep every physical small beam.
        lo=atx[round(x,8)] # Use its actual source-polyline station.
        if lo in portal_lower:continue # A gantry support takes its own explicitly modeled bottom beam.
        for deck,cy in enumerate(centres): # Build each catwalk separately.
            ns=copies[lo,deck];x0=m.X[ns[0]-1][0];z0=m.X[ns[0]-1][2];n=[m.node([x0,cy+y,z0],'smallbeam') for y in [-2.89,0,2.89]];st=len(m.beams);m.shs(n[0],n[2],.05,.004,'small50x4',mid=n[1],offset=-1.) # Preserve the elastic hollow beam and its actual centreline offset.
            for rn,y in zip(ns,YLOW):m.interpolate(rn,n,[-2.89,0,2.89],y) # Attach all16 ropes at their own transverse positions.
            w=10.06*spacing # Reallocate only the small-beam mass already included in the source distributed load.
            for rn in ns:m.mass[rn]-=w/16 # Avoid adding duplicate permanent weight.
            m.distribute_weight(list(range(st,len(m.beams))),w*9.806) # Put that same mass on the actual small beam.
    for lo in lower_orig: # Rebuild the separately loaded large beams at their actual MCT locations.
        if lo in portal_lower or d['point'][lo] not in [1320.,2530.]:continue # Keep original source load identity and avoid duplicate gantry beams.
        for deck,cy in enumerate(centres): # Retain the current drawing's three longitudinally spaced hollow members.
            ns=copies[lo,deck];x0,z0=xyz[lo][[0,2]];n=[m.node([x0,cy+y,z0],'largebeam') for y in [-2.89,0,2.89]];st=len(m.beams) # Keep the physical large-beam reference and rope contacts.
            for offset1 in [-11.5,0.,11.5]:m.member(n[0],n[2],'BOX',[.1,.1,.004,.004,.004,.004],'large100x4',mid=n[1],offset=-.75,offset1=offset1) # Preserve actual longitudinal lever arms of the three members.
            for rn,y in zip(ns,YLOW):m.interpolate(rn,n,[-2.89,0,2.89],y);m.mass[rn]-=1320/9.806/16 # Reallocate the original large-beam weight exactly once.
            m.distribute_weight(list(range(st,len(m.beams))),1320.) # Keep the selected design-institute mass, with the drawing-version difference documented separately.
    for lo,up,x,special in pairs: # Construct ordinary and special source stations separately.
        if special:continue # A passage station receives its actual forked spatial support below.
        for deck,cy in enumerate(centres):ordinary(m,copies[lo,deck],copies[up,deck],cy,pin=pin) # Do not reuse a planar ordinary gantry at a passage station.
    for lo,up,x in passages: # Connect each actual passage through its two real longitudinal rope rows.
        low={} # Keep front and rear contact sets distinct.
        for deck in range(2): # Preserve the actual mass and geometry of both catwalks.
            for side,xx in enumerate([x-.75,x+.75]):low[deck,side]=copies[atx[round(xx,8)],deck] # Use actual passage-chord contact locations.
            for rn in copies[lo,deck]:m.mass[rn]-=49690/9.806/16 # Remove the source passage load before distributing it onto the actual truss.
        passage(m,x,low,{deck:copies[up,deck] for deck in range(2)},zf,centres,pin=pin) # Retain finite clamp offsets, inclined links and both forked gantries.
    return m,copies,dict(portals=len(pairs),passages=len(passages),ordinary_gantries=2*(len(pairs)-len(passages)),special_gantries=2*len(passages),parent_elements=parent_elements) # Derive inventory from the actual source rather than hard-coded totals.
if __name__=='__main__': # Start a genuine complete native solve only under explicit execution.
    spacing=float(sys.argv[1]) if len(sys.argv)>1 else 3.;pin=int(sys.argv[2]) if len(sys.argv)>2 else 5;m,copies,meta=build(spacing,pin);out=R/f'runs/spatial_s{spacing:g}_pin{pin}';audit=m.emit(out,80);meta.update(audit);meta.update(pin_global_axis=pin,spacing_m=spacing,numerical_status='INPUT_WRITTEN_NOT_YET_SOLVED');(out/'inventory.json').write_text(json.dumps(meta,indent=2));np.savez_compressed(out/'observation.npz',copy_keys=np.array(list(copies)),copy_values=np.array([v+[0]*(16-len(v)) for v in copies.values()]),X=np.array(m.X)) # Freeze complete physical input and observation mapping before solving.
    gen=out/'generator';gen.mkdir(exist_ok=True) # Preserve the exact new source used by this execution.
    for p in (R/'code').glob('*.py'):shutil.copy2(p,gen/p.name) # Copy only this new calculation's generator, not any historical engineering model.
    provenance=dict(created_unix=time.time(),files={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((R/'sources').glob('*'))+list(gen.glob('*.py'))+[out/'job.inp'] if p.is_file()});(out/'provenance.json').write_text(json.dumps(provenance,indent=2));print('Native spatial input',audit,flush=True);result=ccx(out,timeout=None);print(result,flush=True);(out/'native_execution.json').write_text(json.dumps(result,indent=2)) # Report actual solver termination and keep failed runs distinct from valid modal results.
