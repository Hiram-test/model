import os # Bound reproducible CPU training before numerical imports.
os.environ['OPENBLAS_NUM_THREADS']='1' # Avoid nested parallelism with native finite-element solves.
import json,time # Preserve independent run metadata and elapsed computation.
from pathlib import Path # Locate repository-local reproducible evidence.
import numpy as np # Build a training-only spatial POD operator basis.
import torch # Train actual neural coefficient operators and save their weights.
from torch import nn # Define the conditional neural operator architecture.
from nonlinear_mechanics import OUT,FiniteStrain # Audit predictions with the compatible full nonlinear mechanics.
from fem import write_json,sha # Reuse deterministic artifact receipts.
torch.set_num_threads(1) # Bound each training process to one CPU thread.
class Operator(nn.Module): # Map geometry and signed load to a full spatial displacement expansion.
    def __init__(self,rank): # Specify a small reproducible nonlinear coefficient network.
        super().__init__();self.net=nn.Sequential(nn.Linear(5,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh(),nn.Linear(64,rank)) # Retain smooth derivatives for load continuation.
    def forward(self,geometry,q): # Enforce the unloaded reference state exactly for the stable elastic branch.
        return q[...,None]*self.net(torch.cat([geometry,q[...,None]],dim=-1)) # Factor the known force-to-modulus scaling without suppressing geometric nonlinearity.
def features(params): # Separate homogeneous material scaling from independent geometry and load-pattern variables.
    return np.asarray([*(np.asarray(params[:3])-1)/.1,(params[5]-.5)/.25],dtype=np.float32) # Standardize only declared physical input bounds.
def load_family(family): # Load qualified cases without crossing geometry partitions.
    manifest=json.loads((OUT/'manifest.json').read_text());items=[] # Use the frozen pre-solve partition manifest.
    for record in manifest: # Preserve all and only the current family's qualified native labels.
        if record['family']!=family: continue # Keep distinct topologies in separate spatial bases.
        directory=OUT/'cases'/record['id'];receipt=json.loads((directory/'receipt.json').read_text()) # Require native qualification before any network use.
        if receipt['status']!='VALID_CONVERGED': raise RuntimeError(f"unqualified label: {record['id']}") # Never train on failed or synthetic repair labels.
        data=dict(np.load(directory/'trajectory.npz'));items.append({**record,**data,'directory':directory}) # Preserve physical data and source identity together.
    return items # Return all disjoint fitting, validation and test cases.
def prepare(items): # Fit the operator's spatial representation using training geometries alone.
    training=[item for item in items if item['split']=='train'];snapshots=np.concatenate([item['displacement'][1:].reshape(11,-1) for item in training]);_,singular,vectors=np.linalg.svd(snapshots,full_matrices=False);rank=min(24,len(vectors));basis=vectors[:rank].T;scale=float(np.sqrt(np.mean(np.sum(snapshots*snapshots,axis=1))));batches={} # Freeze training-only modes and physical output normalization.
    for split in ['train','validation','test']: # Construct geometry-isolated batches without fitting any validation statistics.
        selected=[item for item in items if item['split']==split];geometry=np.asarray([features(item['params']) for item in selected]);q=np.asarray([item['load_path']*item['params'][4]/item['params'][3] for item in selected],dtype=np.float32);values=np.asarray([item['displacement'].reshape(12,-1)@basis/scale for item in selected],dtype=np.float32);batches[split]=(torch.tensor(geometry),torch.tensor(q),torch.tensor(values),selected) # Encode signed continuation amplitude and exact native endpoint states.
    return basis,scale,singular,batches # Keep test data entirely outside basis and checkpoint selection.
def predict(model,batch): # Evaluate the neural spatial operator at every requested continuation state.
    geometry,q,truth,items=batch;return model(geometry[:,None,:].expand(-1,q.shape[1],-1),q) # Apply identical network weights over the load-path function.
def metrics(prediction,truth): # Normalize all path errors by the complete true path energy.
    return float(np.linalg.norm(prediction-truth)/max(np.linalg.norm(truth),1e-30)) # Avoid undefined relative errors at unloaded endpoints.
def train_one(family,seed,basis,scale,batches): # Train and select one fully independent initialization using validation alone.
    torch.manual_seed(seed);model=Operator(basis.shape[1]);optimizer=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=1e-6);schedule=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=2200,eta_min=2e-5);best=float('inf');history=[];directory=OUT/'models'/family/f'seed_{seed}';directory.mkdir(parents=True,exist_ok=True);started=time.time() # Freeze architecture, optimizer and selection procedure.
    for epoch in range(2200): # Complete actual supervised continuation training rather than reporting only initialization.
        model.train();optimizer.zero_grad();estimate=predict(model,batches['train']);target=batches['train'][2];loss=torch.mean((estimate-target)**2);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();schedule.step() # Fit the native-derived spatial response while bounding optimizer updates.
        if epoch%20==0 or epoch==2199: # Select checkpoints at a fixed validation-only cadence.
            model.eval() # Disable training behavior before validation.
            with torch.no_grad(): validation=float(torch.mean((predict(model,batches['validation'])-batches['validation'][2])**2)) # Never inspect test errors during optimization.
            history.append({'epoch':epoch+1,'training_mse':float(loss),'validation_mse':validation}) # Preserve training and selection curves.
            if validation<best: best=validation;torch.save({'state_dict':model.state_dict(),'rank':basis.shape[1],'scale':scale,'family':family,'seed':seed,'epoch':epoch+1},directory/'best.pt') # Keep the actual best validation weights.
    checkpoint=torch.load(directory/'best.pt',weights_only=False);model.load_state_dict(checkpoint['state_dict']);model.eval();records=[];predictions=[] # Evaluate held-out geometries once after model selection.
    with torch.no_grad(): coefficient=predict(model,batches['test']).numpy() # Obtain actual independent neural predictions.
    for i,item in enumerate(batches['test'][3]): # Audit every native-matched test trajectory and every state.
        field=(coefficient[i]*scale@basis.T).reshape(item['displacement'].shape);native=item['displacement'];adapter=FiniteStrain(item['xyz'],item['tet'],item['groups'],float(item['E']),float(item['nu']));residual=[];minimum=[];energy=[] # Reconstruct full nodal predictions for physical checks.
        for j,amplitude in enumerate(item['load_path']): # Evaluate genuine nonlinear equilibrium at every predicted endpoint.
            internal,diagnostics=adapter.internal(field[j]);imbalance=(internal.ravel()-item['force']*amplitude)[item['free']];residual.append(float(np.linalg.norm(imbalance)/np.linalg.norm(item['force'])));minimum.append(diagnostics['min_J']);energy.append(diagnostics['energy_Nmm']) # Use the complete consistent finite-strain force vector, never K u minus f.
        zero=np.flatnonzero(np.abs(item['load_path'])<1e-12);prediction_path=directory/f"{item['id']}_prediction.npz";np.savez_compressed(prediction_path,prediction=field,truth=native,load_path=item['load_path'],nonlinear_residual=residual) # Save independently reconstructable field evidence.
        records.append({'geometry_id':item['id'],'path_relative_L2':metrics(field,native),'pod_truncation_relative_L2':metrics((native.reshape(12,-1)@basis@basis.T).reshape(native.shape),native),'max_full_nonlinear_residual':max(residual),'endpoint_residuals':residual,'minimum_J':min(minimum),'zero_load_drift_mm':float(np.max(np.abs(field[zero]))),'prediction_evidence':str(prediction_path.relative_to(OUT.parent.parent)),'native_evidence':str((item['directory']/'model.dat').relative_to(OUT.parent.parent))});predictions.append(field) # Distinguish spatial accuracy from independent equilibrium acceptance.
    report={'family':family,'seed':seed,'epochs_completed':2200,'selected_epoch':checkpoint['epoch'],'best_validation_mse':best,'seconds':time.time()-started,'mean_test_path_relative_L2':float(np.mean([r['path_relative_L2'] for r in records])),'max_test_full_nonlinear_residual':max(r['max_full_nonlinear_residual'] for r in records),'raw_physics_gate':'PASS' if max(r['max_full_nonlinear_residual'] for r in records)<1e-6 else 'HOLD','test_cases':records,'checkpoint_sha256':sha(directory/'best.pt'),'state_definition':'quasi-static reversible elastic branch: current displacement field, current signed load and reference geometry; absolute load response has no material memory','recurrence':'u_next = u_prev + (G(p,a_next)-G(p,a_prev)); from the zero reference the recurrence telescopes exactly; no accumulated drift or fictitious hysteresis','limitations':['Load sequence is pseudo-time, with no mass, damping or inertial dynamics.','No plasticity, damage, contact opening, friction state or hysteresis is represented.','A trained spatial POD neural operator is a reduced surrogate; its raw nonlinear residual is reported and may fail the strict gate.']};write_json(directory/'training_history.json',history);write_json(directory/'metrics.json',report);print(family,seed,report['mean_test_path_relative_L2'],report['max_test_full_nonlinear_residual'],flush=True);return report # Publish actual held-out metrics without upgrading applicability.
def main(): # Complete all architecture-identical independent seeds and preserve a single aggregate receipt.
    loaded={family:load_family(family) for family in ['splice','deck']};reports=[] # Require all qualified receipts before starting any training run.
    for family in ['splice','deck']: # Train both topology-specific spatial operators.
        items=loaded[family];basis,scale,singular,batches=prepare(items);directory=OUT/'models'/family;directory.mkdir(parents=True,exist_ok=True);np.savez_compressed(directory/'basis.npz',basis=basis,scale=scale,singular_values=singular) # Persist only training-derived spatial modes.
        for seed in [17,43,89]: # Resume completed seeds without discarding their real checkpoints or test evidence.
            previous=directory/f'seed_{seed}'/'metrics.json';reports.append(json.loads(previous.read_text()) if previous.exists() else train_one(family,seed,basis,scale,batches));write_json(OUT/'training_results.json',reports) # Execute missing optimizations and preserve exactly six independent actual runs.
if __name__=='__main__': main() # Run the complete nonlinear neural-operator experiment.
