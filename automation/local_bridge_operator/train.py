import os # Freeze thread policy before loading numerical runtimes.
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1' # Keep finite-element and training workers bounded.
import copy, itertools, json, time, argparse # Preserve model versions, polynomial ablation and timing.
import numpy as np # Form training-only reduced bases and graph descriptors.
import torch # Train independent neural graph operator ensemble members.
from torch import nn # Build explicit message passing and global response decoders.
from scipy.sparse import load_npz # Read actual assembled physical stiffness.
from scipy.stats import qmc # Generate reproducible unlabelled acquisition candidates.
from run import * # Reuse fixed family definitions and actual solver jobs.
torch.set_num_threads(2) # Bound CPU training parallelism.
def polynomial(p): # Define a reproducible non-neural response baseline.
    x=(np.asarray(p)[:,[0,1,2,3,5]]-np.array([1,1,1,1,.5]))/np.array([.2,.15,.15,.1,.35]) # Normalize only with fixed registered input-domain constants.
    return np.column_stack([np.ones(len(x))]+[x[:,i] for i in range(5)]+[x[:,i]*x[:,j] for i in range(5) for j in range(i,5)]) # Include all quadratic input interactions without fitted test statistics.
def graph_template(base): # Coarsen the real element graph while retaining physical group relations.
    xyz,tet,groups,meta=base; extent=np.maximum(np.ptp(xyz,axis=0),1.); unit=(xyz-xyz.min(axis=0))/extent # Define source-linked geometric bins.
    bins=np.minimum((unit*np.array([4,3,3])).astype(int),[3,2,2]); raw=bins[:,0]*9+bins[:,1]*3+bins[:,2]; labels,inverse=np.unique(raw,return_inverse=True); count=len(labels) # Construct deterministic coarse nodes with reversible fine-node membership.
    coords=np.array([unit[inverse==i].mean(axis=0) for i in range(count)]); adj=np.zeros((2,count,count)); material=np.zeros((count,2)) # Allocate heterogeneous coarse relations and material memberships.
    for nodes,group in zip(tet,groups): # Derive graph relations exclusively from actual solid connectivity.
        ids=np.unique(inverse[nodes]); material[ids,int(group)]=1 # Retain mixed material membership at interfaces.
        for a,b in itertools.product(ids,ids): adj[int(group),a,b]=1 # Connect coarse bins sharing a real finite element.
    for relation in range(2): adj[relation]/=np.maximum(adj[relation].sum(axis=1,keepdims=True),1.) # Normalize each relation without inventing absent steel/rubber edges.
    axis=2 if meta['family']=='bearing' else 0; support=np.array([np.mean(unit[inverse==i,axis]<1e-8) for i in range(count)]) # Preserve actual constrained-node fraction per coarse node.
    return {'xyz':coords,'adj':adj,'material':material,'support':support,'fine_to_coarse':inverse,'extent':extent} # Return graph coarsening map and physical attributes.
def graph_features(template,params): # Encode candidate geometry, constitutive state and spatial load pattern on actual graph.
    p=np.asarray(params); coords=template['xyz']; b=len(p); n=len(coords); values=[] # Allocate candidate-wise physical graph descriptors.
    for row in p: # Preserve each independent geometric instance.
        spatial=coords*row[:3]; load=np.exp(-((coords[:,1]-row[5])/.35)**2)*row[4]; repeated=np.broadcast_to(row,(n,6)) # Encode coordinates, force amplitude and spatial load center.
        values.append(np.column_stack([spatial,coords,template['material'],template['support'],load,repeated])) # Keep geometry, materials, constraints and global inputs distinct.
    return np.asarray(values,dtype=np.float32) # Return batch-by-node physical features.
class GraphOperator(nn.Module): # Learn coefficients of a training-only displacement basis from a heterogeneous physical graph.
    def __init__(self,input_size,rank): # Declare explicit graph encoder and global interaction dimensions.
        super().__init__(); self.encoder=nn.Sequential(nn.Linear(input_size,48),nn.SiLU(),nn.Linear(48,32)); self.local=nn.ModuleList([nn.Linear(32,32) for _ in range(2)]); self.relations=nn.ModuleList([nn.ModuleList([nn.Linear(32,32,bias=False) for _ in range(2)]) for _ in range(2)]); self.global_layers=nn.ModuleList([nn.Linear(32,32) for _ in range(2)]); self.decoder=nn.Sequential(nn.Linear(32+6,64),nn.SiLU(),nn.Linear(64,rank)) # Define two relation-aware message layers with global pooling.
        nn.init.zeros_(self.decoder[-1].weight); nn.init.zeros_(self.decoder[-1].bias) # Start from the explicit polynomial baseline rather than a random displacement field.
    def forward(self,features,adj,parameters,baseline): # Apply graph message passing and global response correction.
        h=self.encoder(features) # Encode all physical coarse graph nodes.
        for layer in range(2): # Propagate independent relation-specific messages twice.
            local=self.local[layer](h)+self.global_layers[layer](h.mean(dim=1,keepdim=True)) # Combine local and complete-structure context.
            for relation in range(2): local=local+torch.matmul(adj[relation],self.relations[layer][relation](h)) # Aggregate actual element/material relations.
            h=torch.nn.functional.silu(local) # Update graph node latent states.
        return baseline+.1*self.decoder(torch.cat([h.mean(dim=1),parameters],dim=-1)) # Decode a learned reduced-field correction and preserve ablation visibility.
def prepare(family,manifest,round_id): # Build all learned representations exclusively from current training cases.
    entries=[m for m in manifest if m['family']==family]; accepted=[]; excluded=[] # Separate qualified labels and explicit failures.
    for item in entries: # Inspect every fixed split case without silently changing test denominators.
        receipt=json.loads((RUN/'cases'/item['id']/'receipt.json').read_text()) # Read actual FEM qualification.
        (accepted if receipt['status']=='VALID_CONVERGED' else excluded).append(item) # Enforce solver-quality gate.
    p=np.array([m['params'] for m in accepted]); field=np.array([np.load(RUN/'cases'/m['id']/'fields.npz')['u'].ravel() for m in accepted]); train=np.array([m['split']=='train' for m in accepted]); validation=np.array([m['split']=='validation' for m in accepted]) # Preserve grouped splits and full field targets.
    snapshots=field[train]/p[train,4,None]; _,singular,Vt=np.linalg.svd(snapshots,full_matrices=False); rank=min(16,len(singular)); basis=Vt[:rank].T; scale=max(float(singular[0]/np.sqrt(train.sum())),1e-12) # Fit reduced displacement basis only to training fields.
    coefficients=(field/p[:,4,None])@basis/scale; design=polynomial(p); ridge=1e-4*np.eye(design.shape[1]); ridge[0,0]=0; fit=np.linalg.solve(design[train].T@design[train]+ridge,design[train].T@coefficients[train]) # Fit explicitly recorded quadratic baseline on identical training cases.
    baseline=design@fit; base=load_base(family); template=graph_template(base); features=graph_features(template,p); reduced=[]; rhs=[] # Prepare true projected equilibrium operators and graph features.
    for item,row in zip(accepted,p): # Assemble reduced equilibrium directly from each full physical stiffness matrix.
        data=np.load(RUN/'cases'/item['id']/'fields.npz'); K=load_npz(RUN/'cases'/item['id']/'stiffness.npz'); kb=K@basis; A=basis.T@kb; f=basis.T@data['f'].ravel()/(row[4]*scale); normal=max(np.linalg.norm(f),1e-12) # Keep physical units consistent with normalized basis coefficients.
        reduced.append(A/normal); rhs.append(f/normal) # Normalize by projected applied force with recorded scalar convention.
    directory=RUN/'training'/f'round_{round_id}'/family; directory.mkdir(parents=True,exist_ok=True); np.savez_compressed(directory/'representation.npz',basis=basis,scale=scale,polynomial=fit,adj=template['adj'],coarse_xyz=template['xyz'],fine_to_coarse=template['fine_to_coarse'],singular_values=singular) # Persist reproducible learned basis and exact graph map.
    write_json(directory/'data_identity.json',{'accepted':[m['id'] for m in accepted],'training':[m['id'] for m in accepted if m['split']=='train'],'validation':[m['id'] for m in accepted if m['split']=='validation'],'excluded':excluded,'basis_training_only':True,'rank':rank,'architecture':'heterogeneous coarsened graph + global interaction + training-only POD displacement decoder; family-specific fixed fine topology','fidelity':'linear elastic C3D10 discretization; not a universal cross-topology HGNO','physical_loss':'projected B^T(Ku-f), full residual evaluated independently'}) # Describe actual architecture without overstating universality.
    return {'entries':accepted,'p':p,'field':field,'train':train,'validation':validation,'basis':basis,'scale':scale,'coeff':coefficients,'baseline':baseline,'fit':fit,'features':features,'template':template,'A':np.asarray(reduced),'rhs':np.asarray(rhs),'directory':directory,'excluded':excluded} # Return complete versioned learning state.
def train_ensemble(data,epochs=300): # Train three independently initialized graph models with validation-only checkpoint selection.
    tensors={key:torch.tensor(data[key],dtype=torch.float32) for key in ['features','p','baseline','coeff','A','rhs']}; adj=torch.tensor(data['template']['adj'],dtype=torch.float32); it=np.where(data['train'])[0]; iv=np.where(data['validation'])[0]; predictions=[]; models=[] # Prepare reproducible small-graph operator batches.
    for seed in [17,41,73]: # Preserve independent stochastic initializations for uncertainty estimation.
        torch.manual_seed(seed); model=GraphOperator(data['features'].shape[-1],data['coeff'].shape[-1]); optimizer=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=1e-5); scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,epochs,eta_min=1e-5); best=None; best_error=float('inf'); history=[]; started=time.time() # Initialize independently trained model and fixed learning-rate schedule.
        for epoch in range(epochs): # Execute real optimizer steps over all qualified training geometries.
            model.train(); optimizer.zero_grad(); c=model(tensors['features'][it],adj,tensors['p'][it],tensors['baseline'][it]); diff=c-tensors['coeff'][it]; supervised=(diff.square().sum(dim=1)/tensors['coeff'][it].square().sum(dim=1).clamp_min(1e-12)).mean() # Normalize each sample field-space error equally.
            residual=torch.bmm(tensors['A'][it],c[:,:,None]).squeeze(-1)-tensors['rhs'][it]; physical=residual.square().sum(dim=1).mean(); weight=min(.01,.001+.009*epoch/max(epochs-1,1)); loss=supervised+weight*physical # Use bounded explicit projected-equilibrium regularization.
            loss.backward(); gradient=torch.nn.utils.clip_grad_norm_(model.parameters(),1.); optimizer.step(); scheduler.step(); model.eval() # Stabilize updates and record actual gradient scale.
            with torch.no_grad(): val=model(tensors['features'][iv],adj,tensors['p'][iv],tensors['baseline'][iv]); error=float(((val-tensors['coeff'][iv]).square().sum(dim=1)/tensors['coeff'][iv].square().sum(dim=1).clamp_min(1e-12)).sqrt().mean()) # Select checkpoint using validation geometries alone.
            if error<best_error: best_error=error; best=copy.deepcopy(model.state_dict()); best_epoch=epoch # Preserve best validated neural parameters.
            if epoch%10==0 or epoch==epochs-1: history.append({'epoch':epoch,'data_loss':float(supervised.detach()),'projected_equilibrium_loss':float(physical.detach()),'physical_weight':weight,'gradient_norm':float(gradient),'validation_coefficient_relative':error}) # Store evidence rather than only terminal loss.
        model.load_state_dict(best); model.eval() # Restore validation-selected member.
        with torch.no_grad(): prediction=model(tensors['features'],adj,tensors['p'],tensors['baseline']).numpy() # Evaluate frozen member on every retained split only after fitting.
        torch.save({'state_dict':best,'optimizer_state':optimizer.state_dict(),'optimizer_state_epoch':epochs-1,'selected_weight_epoch':best_epoch,'seed':seed,'input_size':data['features'].shape[-1],'rank':data['coeff'].shape[-1],'epochs':epochs},data['directory']/f'model_seed_{seed}.pt'); write_json(data['directory']/f'history_seed_{seed}.json',{'history':history,'selected_epoch':best_epoch,'seconds':time.time()-started,'validation_relative':best_error}) # Save weights, optimizer lineage, runtime and complete sampled logs.
        predictions.append(prediction); models.append(model) # Retain independent members for uncertainty and acquisition.
    return np.asarray(predictions),models # Return actual ensemble predictions and frozen models.
def evaluate(data,predictions): # Assess full-field displacement, physical residual and polynomial ablation on fixed denominators.
    coefficients=predictions.mean(axis=0); predicted=(coefficients@data['basis'].T)*data['scale']*data['p'][:,4,None]; polynomial_field=(data['baseline']@data['basis'].T)*data['scale']*data['p'][:,4,None]; rows=[] # Reconstruct full original nodal fields from training-only decoder.
    for i,item in enumerate(data['entries']): # Evaluate every independent case without modifying weights or acquisition decisions.
        raw=np.load(RUN/'cases'/item['id']/'fields.npz'); K=load_npz(RUN/'cases'/item['id']/'stiffness.npz'); f=raw['f'].ravel(); free=raw['free']; u=data['field'][i]; up=predicted[i]; residual=K@up-f # Compute true unreduced finite-element residual.
        relative=float(np.linalg.norm(up-u)/max(np.linalg.norm(u),1e-12)); physics=float(np.linalg.norm(residual[free])/max(np.linalg.norm(f[free]),1e-12)); peak=float(np.linalg.norm(up.reshape(-1,3),axis=1).max()); truth=float(np.linalg.norm(u.reshape(-1,3),axis=1).max()); spread=float(np.sqrt(np.mean(np.var(predictions[:,i],axis=0)))*data['scale']*data['p'][i,4]) # Keep absolute, relative and uncertainty metrics separate.
        rows.append(dict(item,relative_L2=relative,RMSE_mm=float(np.sqrt(np.mean((up-u)**2))),peak_relative=abs(peak-truth)/max(truth,1e-12),full_equilibrium_relative=physics,boundary_max_mm=float(np.max(np.abs(up[raw['fixed']]))),polynomial_only_relative=float(np.linalg.norm(polynomial_field[i]-u)/max(np.linalg.norm(u),1e-12)),ensemble_coefficient_spread_mm=spread,prediction_accepted=relative<=.05 and physics<=.05 and item['split']!='ood')) # Apply frozen research error and physical gates without claiming bridge safety.
    np.savez_compressed(data['directory']/'predictions.npz',predicted=predicted,reference=data['field'],polynomial=polynomial_field,ensemble_coefficients=predictions) # Save full auditable predictions and ablations.
    summary={} # Report each split with full original sample denominator.
    for split in ['train','validation','test','ood']: # Keep fitting, selection, independent and domain-shift outcomes distinct.
        group=[r for r in rows if r['split']==split]; summary[split]={'count':len(group),'mean_relative_L2':float(np.mean([r['relative_L2'] for r in group])),'max_relative_L2':float(max(r['relative_L2'] for r in group)),'mean_polynomial_relative':float(np.mean([r['polynomial_only_relative'] for r in group])),'max_full_equilibrium_relative':float(max(r['full_equilibrium_relative'] for r in group)),'accepted':sum(r['prediction_accepted'] for r in group)} # Preserve both accuracy and physical admissibility.
    write_json(data['directory']/'evaluation.json',{'summary':summary,'cases':rows,'excluded':data['excluded'],'engineering_release':'HOLD; research models lack calibrated complete project inputs'}); return summary # Persist honest release decision and all case metrics.
def acquire(data,models,family,round_id,manifest): # Search unlabelled geometry/load candidates using ensemble disagreement and geometric coverage.
    unit=qmc.Sobol(6,scramble=True,seed=700+FAMILIES.index(family)*10+round_id).random_base2(8); candidates=np.array([.8,.85,.85,.9,.4,.15])+unit*np.array([.4,.3,.3,.2,1.2,.7]); baseline=polynomial(candidates)@data['fit']; features=graph_features(data['template'],candidates); adj=torch.tensor(data['template']['adj'],dtype=torch.float32) # Generate 256 in-domain candidates without FEM labels.
    with torch.no_grad(): members=np.array([m(torch.tensor(features),adj,torch.tensor(candidates,dtype=torch.float32),torch.tensor(baseline,dtype=torch.float32)).numpy() for m in models]) # Use actual independently trained member disagreement.
    disagreement=np.linalg.norm(members.std(axis=0),axis=1)/np.maximum(np.linalg.norm(members.mean(axis=0),axis=1),1e-12); training=data['p'][data['train']]; widths=np.array([.4,.3,.3,.2,1.2,.7]); distance=np.linalg.norm((candidates[:,None,:]-training[None,:,:])/widths,axis=2).min(axis=1); score=.7*disagreement/max(disagreement.max(),1e-12)+.3*distance/max(distance.max(),1e-12) # Fix an acquisition objective with uncertainty and actual coverage.
    chosen=[]; working=score.copy() # Select diverse high-score candidates without reading any test labels.
    for _ in range(2): # Execute two new geometric calculations per family per feedback round.
        index=int(np.argmax(working)); chosen.append(index); separation=np.linalg.norm((candidates-candidates[index])/widths,axis=1); working[separation<.3]=-np.inf # Avoid duplicate acquisitions in the same local region.
    ledger=[{'index':i,'params':row.tolist(),'disagreement':float(disagreement[i]),'coverage_distance':float(distance[i]),'score':float(score[i]),'selected':i in chosen} for i,row in enumerate(candidates)] # Preserve every candidate and objective score.
    write_json(data['directory']/'acquisition.json',{'objective':'0.7 normalized ensemble disagreement + 0.3 normalized distance to training cases; family-specific fixed mesh cost','candidates':ledger,'test_labels_used':False}) # Distinguish objective-driven search from random sampling.
    for index in chosen: # Turn each selected candidate into actual finite-element evidence.
        identity=f'{family}_active_r{round_id+1}_c{index:03d}'; result=work((family,candidates[index].tolist(),identity)); item={'id':identity,'geometry_id':identity,'family':family,'split':'train','params':candidates[index].tolist(),'round':round_id+1}; manifest.append(item) # Append acquired geometry with explicit new version lineage.
        print('ACQUIRED',identity,result['status'],flush=True) # Report actual completed physical calculation.
    return manifest # Return full experiment ledger including any failed acquisitions.
def execute(family,rounds,epochs): # Complete training-search-solve-retraining cycle for one topology family.
    manifest=json.loads((RUN/'manifest.json').read_text()); manifest=[m for m in manifest if m['family']==family]; outcomes=[] # Keep family experiments independent and safely parallelizable.
    for round_id in range(rounds+1): # Train initial model and every acquired-data continuation.
        data=prepare(family,manifest,round_id); predictions,models=train_ensemble(data,epochs); summary=evaluate(data,predictions); outcomes.append({'round':round_id,'summary':summary}); print(family,round_id,json.dumps(summary),flush=True) # Record actual generalization and physical performance.
        if round_id<rounds: manifest=acquire(data,models,family,round_id,manifest) # Feed objective-driven new FEM labels into next model version.
        write_json(RUN/f'manifest_{family}.json',manifest); write_json(RUN/f'training_{family}.json',outcomes) # Persist complete closed-loop state after each iteration.
    selected=min(outcomes,key=lambda row:row['summary']['validation']['mean_relative_L2']); write_json(RUN/f'selected_{family}.json',{'selected_round':selected['round'],'selection_uses':'validation mean relative displacement only; test does not choose model','result':selected,'release':'HOLD unless all physical and project-validation gates pass'}) # Select final candidate without test leakage.
if __name__=='__main__': # Run explicit family training and feedback budget.
    parser=argparse.ArgumentParser(); parser.add_argument('--family',required=True,choices=FAMILIES); parser.add_argument('--rounds',type=int,default=2); parser.add_argument('--epochs',type=int,default=300); args=parser.parse_args() # Freeze executable experiment configuration.
    execute(args.family,args.rounds,args.epochs) # Carry every requested loop through physical solve and independent evaluation.
