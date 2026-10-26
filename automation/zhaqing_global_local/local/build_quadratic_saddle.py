#!/usr/bin/env python3
"""Upgrade every explicit wire and saddle brick to curved C3D20R geometry without merging wires.""" # Scope.
from __future__ import annotations # Stable annotations.
import argparse # Reproducible settings.
import hashlib # Exact source hashes.
import json # Metadata contracts.
import math # Circular geometry.
from pathlib import Path # Filesystem paths.
import numpy as np # Numerical construction, never rendering.
from build_saddle import build # Preserve drawing-derived geometry and contact relationships.
from quadratic_solid import EDGES, gauss_shape, shape # Native twenty-node interpolation.
def blocks(text: str) -> list[list[str]]: # Split a native deck into keyword blocks.
    out = [] # Ordered native keyword groups.
    for line in text.splitlines(): # Preserve exact keyword order.
        if line.startswith('*') and not line.startswith('**'): out.append([line]) # Start actual keyword.
        elif out: out[-1].append(line) # Retain keyword data.
    return out # Native groups.
def disk(u: float, v: float, radius: float) -> tuple[float,float]: # Same source disk map at fractional natural coordinates.
    if abs(u)+abs(v) < 1e-14: return (0.,0.) # Disk center.
    if abs(u) > abs(v): r, angle = u, math.pi*.25*v/u # First mapping sector.
    else: r, angle = v, math.pi*.5-math.pi*.25*u/v # Remaining mapping sectors.
    return radius*r*math.cos(angle), radius*r*math.sin(angle) # Circular mapped coordinates.
def build_quadratic(out: Path, nx: int, nc: int, count: int, tension: float, mu: float, forming: bool, prestressed: bool, smoke: bool, penalty: float, exponential_clearance: float=0.0, exponential_pressure: float=.1, staged_seating: bool=False, packing_clearance: float=0.0) -> dict: # Fully explicit quadratic builder with identified contact, candidate packing, and initial-state branches.
    seating_factors=tuple(10.**i for i in range(-8,1))+(1.1,.9,1.) if staged_seating else None # Start genuinely stress-free curved wires with a tiny load before raising tension geometrically.
    if staged_seating and (forming or prestressed or smoke): raise ValueError('Staged seating is a separate complete stress-free preformed-wire research branch') # Never disguise removal of an imported forming state.
    seed = out/'linear_seed'; build(seed,nx,nc,count,tension,mu,smoke,forming,True,None,prestressed,seating_factors,packing_clearance) # Preserve exact reproducible linear seed, explicit packing gap, and load path.
    old = np.load(seed/'geometry.npz'); meta = json.loads((seed/'metadata.json').read_text()); interface = json.loads((seed/'boundary_interface.json').read_text()) # Existing source geometry.
    xyz = old['coordinates'].tolist(); cells = old['connectivity']; centers = old['wire_centers']; nwire = int(meta['wire_nodes']); radius = 1500. # Keep original entity identity.
    per_wire = (nx+1)*(nc+1)**2; theta = np.linspace(math.radians(90.-127.8890430192378),math.radians(90.-63.23495198354442),nx+1) # Source longitudinal span.
    edges = {}; upgraded = []; node_wire = [i//per_wire+1 if i<nwire else 0 for i in range(len(xyz))] # Separate wire node identities.
    left = set(np.asarray(interface['left']['node_ids'])-1); right = set(np.asarray(interface['right']['node_ids'])-1); base = set() # Physical cuts and support.
    original = blocks((seed/'saddle.inp').read_text()) # Editable native representation.
    for group in original: # Recover concrete support node identities.
        if group[0].upper() == '*NSET,NSET=BASE': base.update(int(v)-1 for line in group[1:] for v in line.split(',') if v.strip()) # Exact base nodes.
    def middle(a: int,b: int) -> int: # Deduplicate only within actual element topology.
        key = tuple(sorted((a,b))) # Wire interfaces have distinct endpoint IDs.
        if key in edges: return edges[key] # Same solid shares its midside node.
        if a<nwire and b<nwire: # Map steel wire edge midpoint exactly in source parameters.
            wa,wb = a//per_wire,b//per_wire # Preserve separate wires.
            if wa != wb: raise ValueError('Element edge crosses two distinct wires') # Never create artificial inter-wire bonds.
            ka,rem = divmod(a%per_wire,(nc+1)**2); ja,ia = divmod(rem,nc+1) # First reference grid coordinate.
            kb,rem = divmod(b%per_wire,(nc+1)**2); jb,ib = divmod(rem,nc+1) # Second reference grid coordinate.
            y,z = disk(-1.+(ia+ib)/nc,-1.+(ja+jb)/nc,2.5); y += centers[wa,0]; z += centers[wa,1] # Curved cross-section midpoint.
            angle = (theta[ka]+theta[kb])/2; p = [(radius+z)*math.sin(angle),y,(radius+z)*math.cos(angle)-radius]; w=wa+1 # Curved axial midpoint.
        else: # Preserve source saddle arc with vertical plate offsets.
            pa,pb = np.asarray(xyz[a]),np.asarray(xyz[b]); aa,ab = math.asin(pa[0]/radius),math.asin(pb[0]/radius) # Saddle source angles.
            za,zb = pa[2]-(radius*math.cos(aa)-radius),pb[2]-(radius*math.cos(ab)-radius) # Vertical plate thickness coordinates.
            angle=(aa+ab)/2; p=[radius*math.sin(angle),(pa[1]+pb[1])/2,radius*math.cos(angle)-radius+(za+zb)/2]; w=0 # Exact saddle midpoint.
        idx=len(xyz); edges[key]=idx; xyz.append(p); node_wire.append(w) # Append actual quadratic node.
        for node_set in (left,right,base): # Extend all boundary conditions to real midside nodes.
            if a in node_set and b in node_set: node_set.add(idx) # Topology-based boundary extension.
        return idx # Zero-based native node.
    for cell in cells: upgraded.append(list(cell)+[middle(int(cell[a]),int(cell[b])) for a,b in EDGES]) # Upgrade every wire and saddle cell.
    xyz=np.asarray(xyz); conn=np.asarray(upgraded); nodal_wire=np.asarray(node_wire); shapes,gradients=gauss_shape() # Final physical geometry and interpolation.
    minimum=float('inf'); maximum=0.; volumes=[] # Independent full integration-point audit.
    for start in range(0,len(conn),4096): # Bound temporary Jacobian memory.
        jac=np.einsum('eni,gnj->egij',xyz[conn[start:start+4096]],gradients); det=np.linalg.det(jac) # Every native Gauss determinant.
        minimum=min(minimum,float(det.min())); maximum=max(maximum,float(det.max())); volumes.extend(det.sum(axis=1)) # Positive physical volumes.
    if minimum <= 0: raise ValueError(f'Nonpositive quadratic Jacobian {minimum}') # Never run inverted geometry.
    cuts = [sorted(left),sorted(right)]; weights=[] # Consistent actual quadratic cap tractions.
    abscissa,gw=np.polynomial.legendre.leggauss(4) # Fourth-order tensor integration for curved cap area.
    for k,nodes in enumerate(cuts): # Integrate both source cuts independently.
        acc={n:0. for n in nodes}; signed=-1. if k==0 else 1. # Constant natural axial coordinate.
        for e,cell in enumerate(conn[:int(meta['wire_hexahedra'])]): # Every actual wire cell touching the selected cut.
            corners=cell[:4] if k==0 else cell[4:8] # Correct local cut face.
            if not all(int(n) in acc for n in corners): continue # Skip interior axial cells.
            for ix,x in enumerate(abscissa): # First surface integration coordinate.
                for iy,y in enumerate(abscissa): # Second surface integration coordinate.
                    val,grad=shape(np.array([x,y,signed])); tang=xyz[cell].T@grad[:,:2]; area=np.linalg.norm(np.cross(tang[:,0],tang[:,1]))*gw[ix]*gw[iy] # True curved face metric.
                    for n,v in zip(cell,val): # Equivalent nodal traction includes signed corner weights.
                        if int(n) in acc: acc[int(n)] += float(v*area) # Work-consistent integration.
        weights.append(np.asarray([acc[n] for n in nodes])) # Preserve exact cut ordering.
    by_wire=[np.flatnonzero(nodal_wire[cuts[1]]==w) for w in range(1,count+1)] # Separate physical end caps.
    for q in by_wire: # Verify every wire has its full end area.
        if abs(weights[1][q].sum()-math.pi*2.5**2)/(math.pi*2.5**2) > .02: raise ValueError('Quadratic wire area error exceeds 2 percent') # Coarse geometry admission, not fatigue mesh qualification.
    result=[]; factors=iter(meta['requested_load_factors']) # Reuse the exact source load path, including every deliberately small seating stage.
    def set_block(name: str,ids: list[int]) -> list[str]: # Compact valid native node-set output.
        return ['*NSET,NSET='+name]+[','.join(str(n+1) for n in ids[k:k+16]) for k in range(0,len(ids),16)] # Native one-based IDs.
    for group in original: # Replace geometry-sensitive native blocks only.
        keyword=group[0].upper() # Native keyword classifier.
        if keyword.startswith('*NODE,'): result += [group[0]]+[str(i+1)+','+','.join(f'{v:.12g}' for v in p) for i,p in enumerate(xyz)] # Every physical quadratic node.
        elif keyword.startswith('*ELEMENT,'): # Write legal multi-line twenty-node connectivity.
            result.append('*ELEMENT,TYPE=C3D20R,ELSET=BODY') # Native quadratic reduced-integration solids.
            for i,cell in enumerate(conn): result += [str(i+1)+','+','.join(str(n+1) for n in cell[:15])+',',','.join(str(n+1) for n in cell[15:])] # Sixteen items on the first record.
        elif keyword in ('*NSET,NSET=LEFT','*NSET,NSET=RIGHT','*NSET,NSET=BASE'): name=keyword.split('=')[-1]; result += set_block(name,{'LEFT':cuts[0],'RIGHT':cuts[1],'BASE':sorted(base)}[name]) # Actual boundary midsides.
        elif keyword == '*EQUATION': continue # Rebuild all cut MPCs once below.
        elif keyword.startswith('*SURFACE INTERACTION'): # Insert updated cut MPCs before material interaction.
            for node in cuts[1]: result += ['*EQUATION','2',f'{node+1},1,{math.sin(theta[-1]):.12g},{node+1},3,{math.cos(theta[-1]):.12g}'] # Radial cut restraint only.
            for q in by_wire: # Independent planar cap on each wire.
                reference=cuts[1][int(q[0])] # Retained cap tangent degree of freedom.
                for i in q[1:]: result += ['*EQUATION','2',f'{cuts[1][int(i)]+1},3,1.,{reference+1},3,-1.'] # Equal tangent displacement under radial MPC.
            result += group # Preserve material interaction name.
        elif keyword.startswith('*SURFACE BEHAVIOR'): result += ['*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=EXPONENTIAL',f'{exponential_clearance:.12g},{exponential_pressure:.12g}'] if exponential_clearance>0 else [group[0],f'{penalty:.12g}'] # Explicit smooth-contact branch uses native c0,p0 and never silently adjusts coordinates.
        elif keyword.startswith('*INITIAL CONDITIONS,TYPE=STRESS'): # Recompute stress at true quadratic integration points.
            result.append(group[0]) # Native initial stress field.
            for e,cell in enumerate(conn[:int(meta['wire_hexahedra'])]): # Every actual wire cell.
                w=int(old['wire_id'][e])-1; pos=shapes@xyz[cell]; offsets=shapes@(np.hypot(xyz[cell,0],xyz[cell,2]+radius)-radius-centers[w,1]) # Physical fiber offsets.
                for ip,p in enumerate(pos,1): # Eight native integration points.
                    angle=math.atan2(p[0],p[2]+radius); sig=200000.*offsets[ip-1]/(radius+centers[w,1])+(tension/count/weights[1][by_wire[w]].sum() if prestressed else 0.); co,si=math.cos(angle),math.sin(angle) # Assumed elastic wrapping plus optional axial import.
                    result.append(f'{e+1},{ip},{sig*co*co:.12g},0.,{sig*si*si:.12g},0.,{-sig*co*si:.12g},0.') # Native XX YY ZZ XY XZ YZ stress ordering.
        elif keyword.startswith('*CLOAD'): # Distribute requested axial resultant through exact quadratic cap integrals.
            factor=next(factors); result.append(group[0]) # Prescribed load-path stage.
            for q in by_wire: # Per-wire equal resultant, candidate packing assumption.
                forces=tension*factor/count*weights[1][q]/weights[1][q].sum() # Exact total applied traction resultant.
                for i,force in zip(q,forces): n=cuts[1][int(i)]+1; result += [f'{n},1,{force*math.cos(theta[-1]):.12g}',f'{n},3,{-force*math.sin(theta[-1]):.12g}'] # Correct tangent components.
        else: result += group # Preserve contact surfaces, loads, and complete output settings.
    inp=out/'saddle.inp'; inp.write_text('\n'.join(result)+'\n') # Final executable native deck.
    np.savez_compressed(out/'geometry.npz',coordinates=xyz,connectivity=conn,wire_id=old['wire_id'],wire_centers=centers,wire_neighbor_pairs=old['wire_neighbor_pairs'],node_wire_id=nodal_wire,element_volume_mm3=np.asarray(volumes),element_type=np.asarray('C3D20R')) # All nodes/elements retained.
    with (out/'saddle_mesh.vtk').open('w') as stream: # Solver geometry export only, without drawing.
        stream.write(f'# vtk DataFile Version 3.0\nExplicit {count}-wire quadratic saddle\nASCII\nDATASET UNSTRUCTURED_GRID\nPOINTS {len(xyz)} double\n') # Native geometry header.
        for p in xyz: stream.write(' '.join(f'{v:.12g}' for v in p)+'\n') # Actual native coordinates.
        stream.write(f'CELLS {len(conn)} {21*len(conn)}\n') # Twenty-node cell record count.
        for cell in conn: stream.write('20 '+' '.join(map(str,cell))+'\n') # VTK quadratic hexahedron node order.
        stream.write(f'CELL_TYPES {len(conn)}\n'+'25\n'*len(conn)+f'CELL_DATA {len(conn)}\nSCALARS wire_id int 1\nLOOKUP_TABLE default\n'+'\n'.join(map(str,old['wire_id']))+'\n') # Physical identity, not response data.
    for k,name in enumerate(('left','right')): interface[name]={'node_ids':[int(n)+1 for n in cuts[k]],'coordinates_mm':xyz[cuts[k]].tolist()}; interface[name+'_traction_integrals_mm2']=weights[k].tolist(); interface[name+'_area_weights_mm2']=(abs(weights[k])*weights[k].sum()/abs(weights[k]).sum()).tolist() # Separate signed consistent loads and positive conservative transfer measure; serialize native integer identities.
    interface['traction_note']='Signed quadratic consistent traction integrals are distinct from positive transfer quadrature weights'; interface['source_input_sha256']=hashlib.sha256(inp.read_bytes()).hexdigest() # Explicit numerical distinction.
    (out/'boundary_interface.json').write_text(json.dumps(interface,indent=2)+'\n') # Full quadratic coupling contract.
    meta.update({'element_type':'C3D20R','physical_nodes':len(xyz),'physical_hexahedra':len(conn),'wire_nodes':int(np.count_nonzero(nodal_wire)),'gauss_jacobian_min_mm3':minimum,'gauss_jacobian_max_mm3':maximum,'gauss_points_checked':8*len(conn),'normal_penalty_n_per_mm3':penalty,'native_input_sha256':interface['source_input_sha256'],'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'quadratic_area_mm2_per_wire':[float(weights[1][q].sum()) for q in by_wire],'real_bridge_training_eligible':False,'status':'QUADRATIC_GEOMETRY_VERIFIED_SOLVE_REQUIRED'}) # Geometry cannot authorize training by itself.
    source_dir=out/'model_sources'; source_dir.mkdir(exist_ok=True); source_hashes={} # Preserve all code that determines the actual native geometry and IP stresses.
    for name in ('build_quadratic_saddle.py','build_saddle.py','quadratic_solid.py'): source=Path(__file__).with_name(name).read_bytes(); (source_dir/name).write_bytes(source); source_hashes[name]=hashlib.sha256(source).hexdigest() # Include imported interpolation so a changed Gauss order cannot retain the same sole-builder identity.
    meta.update({'source_hashes':source_hashes,'integration_point_order':'CalculiX2.21gauss.f:gauss3d2:x-fast-then-y-then-z','tension_provenance':'Explicit assumed axial research load; not yet supplied by the corrected detailed-bridge saddle-port history','forming_method':'Imported elastic axial T/A plus wrapping E*z/R stress, equilibrated with matching full end tension' if prestressed else ('Imported elastic wrapping E*z/R stress followed by zero-load equilibrium' if forming else 'Stress-free curved reference')}) # State actual initialization and current coupling scope.
    meta['normal_contact_law']={'type':'EXPONENTIAL','clearance_at_one_percent_pressure_mm':exponential_clearance,'pressure_at_zero_gap_mpa':exponential_pressure,'law':'p=p0*exp(-ln(100)*gap/c0)','scope':'Research smoothing; penetration/contact-law sensitivity required; no native geometry adjustment'} if exponential_clearance>0 else {'type':'LINEAR','penalty_n_per_mm3':penalty} # Preserve the actual constitutive approximation in every dataset provenance chain.
    meta.update({'staged_seating':staged_seating,'cycle_load_parameter_bounds':[9.,12.] if staged_seating else ([1.,4.] if not forming or prestressed else [2.,5.]),'initial_state_branch':'STRESS_FREE_PREFORMED_CURVE_STAGED_TENSION' if staged_seating else ('IMPORTED_ELASTIC_WRAPPING_AND_AXIAL_STRESS' if prestressed else ('IMPORTED_ELASTIC_WRAPPING_STRESS' if forming else 'STRESS_FREE_PREFORMED_CURVE'))}) # Distinguish a numerical/model-assumption branch from actual manufacturing residual stress.
    meta['unverified_assumptions']=[s for s in meta['unverified_assumptions'] if 'C3D8' not in s]+['C3D20R curved geometry still requires axial/circumferential/contact mesh convergence before fatigue qualification'] # Correct interpolation limitation.
    (out/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n'); return meta # Preserve exact counts and scope.
def main() -> None: # Reproducible native model CLI.
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('output',type=Path); p.add_argument('--nx',type=int,default=16); p.add_argument('--nc',type=int,default=2); p.add_argument('--wires',type=int,default=283); p.add_argument('--tension',type=float,default=801490.); p.add_argument('--mu',type=float,default=.2); p.add_argument('--penalty',type=float,default=200000.); p.add_argument('--exponential-clearance-mm',type=float,default=0.); p.add_argument('--exponential-pressure-mpa',type=float,default=.1); p.add_argument('--staged-seating',action='store_true'); p.add_argument('--packing-clearance-mm',type=float,default=0.); p.add_argument('--elastic-forming-stress',action='store_true'); p.add_argument('--prestressed-equilibrium',action='store_true'); p.add_argument('--smoke',action='store_true'); a=p.parse_args() # Explicit research settings; a zero smoothing clearance preserves the original linear penalty branch.
    if a.nx<2 or a.nc<2 or a.nc%2 or not 1<=a.wires<=360 or a.tension<=0 or not 0<=a.mu<=1 or a.penalty<=0: raise ValueError('Invalid explicit quadratic model settings') # Fail closed before generating input.
    if a.prestressed_equilibrium and not a.elastic_forming_stress: raise ValueError('Prestressed equilibrium requires elastic forming stress flag') # Avoid silently omitted axial prestress.
    if not np.isfinite([a.exponential_clearance_mm,a.exponential_pressure_mpa]).all() or a.exponential_clearance_mm<0 or a.exponential_pressure_mpa<=0: raise ValueError('Invalid smooth-contact constitutive parameters') # Fail before generating a nonphysical research law.
    print(json.dumps(build_quadratic(a.output,a.nx,a.nc,a.wires,a.tension,a.mu,a.elastic_forming_stress,a.prestressed_equilibrium,a.smoke,a.penalty,a.exponential_clearance_mm,a.exponential_pressure_mpa,a.staged_seating,a.packing_clearance_mm),ensure_ascii=False)) # Actual model counts and explicitly selected initialization/normal law.
if __name__=='__main__': main() # Run requested native model generation.
