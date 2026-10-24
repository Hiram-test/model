import os # Bound optional cache regeneration cost.
os.environ['OPENBLAS_NUM_THREADS']='1' # Avoid oversubscribing independent sparse assembly.
import argparse,json # Parse explicit evidence root and preserved material metadata.
from fem import * # Reuse identical audited quadratic-tetrahedron assembly.
def rebuild(): # Restore excluded reproducible stiffness caches from delivered mesh and material records.
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='*');args=parser.parse_args() # Allow one selected case or the complete evidence collection.
    for path in sorted((RUN/'cases').glob(args.case+'/fields.npz')): # Visit only actual delivered physical field archives.
        target=path.parent/'stiffness.npz' # Resolve optional deterministic matrix cache.
        if target.exists(): continue # Preserve already available evidence and any explicit repair history.
        receipt=json.loads((path.parent/'receipt.json').read_text());meta=json.loads((RUN/'meshes'/f"{receipt['family']}.json").read_text());data=np.load(path);E=meta['E_MPa']*receipt['params'][3] # Restore exact source material and geometric state.
        K,volume=assemble(data['xyz'],data['tet'],data['groups'],E,meta['nu']);residual=np.linalg.norm((K@data['u'].ravel()-data['f'].ravel())[data['free']])/max(np.linalg.norm(data['f'].ravel()),1.) # Independently reconcile regenerated stiffness with preserved linear companion field.
        assert residual<1e-7;save_npz(target,K);print(path.parent.name,residual,flush=True) # Accept only physically consistent cache reconstruction.
if __name__=='__main__': rebuild() # Regenerate caches without changing solver labels or neural weights.
