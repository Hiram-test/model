import os # Limit independent numerical experiment resources.
os.environ['OPENBLAS_NUM_THREADS']='1' # Avoid nested BLAS oversubscription.
import time,json # Preserve measured offline and online numerical costs.
import numpy as np # Construct physical response subspaces from training data only.
from scipy.sparse import load_npz # Read actual finite-element operators.
from scipy.sparse.linalg import splu # Factor only training operators during offline enrichment.
from fem import RUN,FAMILIES,write_json # Reuse frozen scientific experiment identities.
for family in FAMILIES: # Evaluate every structural family under the same residual criterion.
    entries=json.loads((RUN/f'manifest_{family}.json').read_text());training=[x for x in entries if x['split']=='train'];testing=[x for x in entries if x['split'] in ['validation','test','ood']];out=RUN/'residual_basis_v2'/family;out.mkdir(parents=True,exist_ok=True);started=time.time() # Keep new experiment separate from published models.
    first=np.load(RUN/'cases'/training[0]['id']/'fields.npz');free=first['free'];snapshots=np.column_stack([np.load(RUN/'cases'/x['id']/'fields.npz')['u'].ravel()[free] for x in training]);u,s,_=np.linalg.svd(snapshots,full_matrices=False);basis=u[:,s>s[0]*1e-10];levels=[] # Fit only current training displacement span.
    reference=load_npz(RUN/'cases'/training[0]['id']/'stiffness.npz')[free][:,free].tocsc();factor=splu(reference) # Charge one offline training-geometry factorization explicitly.
    for level in range(3): # Test two training-operator-driven subspace enrichment rounds.
        if level: # Enrich using stiffness actions without inspecting test solutions.
            additions=[basis] # Retain already represented training responses.
            for item in training[::max(1,len(training)//6)][:6]: # Choose fixed training geometries independently of test outcomes.
                path=RUN/'cases'/item['id'];K=load_npz(path/'stiffness.npz')[free][:,free];f=np.load(path/'fields.npz')['f'].ravel()[free];additions.extend([factor.solve(K@basis),factor.solve(f)[:,None]]) # Generate offline operator-action directions and force responses.
            vectors=np.column_stack(additions[1:]);vectors-=basis@(basis.T@vectors);vectors-=basis@(basis.T@vectors);norms=np.linalg.norm(vectors,axis=0);vectors/=np.maximum(norms,1e-30);u,s,_=np.linalg.svd(vectors,full_matrices=False);extra=min(384-basis.shape[1],int(np.sum(s>s[0]*1e-9)));basis=np.linalg.qr(np.column_stack([basis,u[:,:extra]]),mode='reduced')[0];np.save(out/f'basis_level_{level}.npy',basis) # Retain every accepted basis direction and append only orthogonal enrichment directions.
        rows=[] # Keep fixed validation, test and OOD denominators.
        for item in testing: # Evaluate new subspace without test-dependent fitting or online full factorization.
            path=RUN/'cases'/item['id'];data=np.load(path/'fields.npz');K=load_npz(path/'stiffness.npz')[free][:,free];f=data['f'].ravel()[free];truth=data['u'].ravel()[free];clock=time.time();action=K@basis;coeff=np.linalg.lstsq(action,f,rcond=1e-12)[0];prediction=basis@coeff;elapsed=time.time()-clock # Minimize the full free-node residual in the frozen reduced span.
            residual=float(np.linalg.norm(K@prediction-f)/max(np.linalg.norm(f),1e-12));error=float(np.linalg.norm(prediction-truth)/max(np.linalg.norm(truth),1e-12));rows.append({'id':item['id'],'split':item['split'],'residual':residual,'relative_error':error,'online_seconds':elapsed,'accepted':residual<1e-7 and error<1e-5}) # Apply unchanged physical and reference-solution thresholds.
        levels.append({'level':level,'rank':basis.shape[1],'cases':rows});write_json(out/'evaluation.json',{'family':family,'training_ids':[x['id'] for x in training],'offline_and_evaluation_seconds':time.time()-started,'method':'training-only operator-induced basis enrichment plus online reduced least-squares full residual minimization; not a standalone neural prediction','online_full_factorization':False,'levels':levels});group=[x for x in rows if x['split']=='test'];print(family,level,basis.shape[1],max(x['residual'] for x in group),np.mean([x['relative_error'] for x in group]),flush=True) # Checkpoint genuine results without conflating physical correction with neural gains.
