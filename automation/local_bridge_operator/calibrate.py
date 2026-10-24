import os # Freeze numerical worker resource policy.
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1' # Bound sparse-solve concurrency.
import concurrent.futures,json,time # Preserve independent calibration jobs and evidence.
from train import * # Reuse frozen graph architecture without retraining any member.
def main(): # Generate fresh calibration geometries after all model selection is frozen.
    tasks=[]; entries=[] # Keep calibration separate from training, validation and test.
    for number,family in enumerate(FAMILIES): # Sample each physical topology independently.
        rows=np.random.default_rng(9000+number).random((9,6)) # Draw nine fresh independent geometry seeds rather than reusing validation cases.
        for i,row in enumerate(rows): # Construct independent calibration structures.
            p=np.array([.8,.85,.85,.9,.4,.15])+row*np.array([.4,.3,.3,.2,1.2,.7]) # Match the declared initial in-domain design distribution.
            for load in range(2): # Preserve the same paired load patterns within each new geometry.
                pl=p.copy();pl[4]=.5+.9*row[4] if load==0 else 1.+.6*row[4];pl[5]=.15+.3*row[5] if load==0 else .55+.3*row[5];identity=f'{family}_cal_g{i:02d}_l{load}' # Keep exact conditional-load generation consistent with test construction.
                tasks.append((family,pl.tolist(),identity));entries.append({'id':identity,'family':family,'geometry_id':f'{family}_cal_g{i:02d}','params':pl.tolist(),'split':'calibration'}) # Freeze fresh calibration IDs.
    write_json(RUN/'calibration_manifest.json',entries) # Record unseen calibration identities before any solves or interval fitting.
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool: # Compute only real independently verified FEM labels.
        results=list(pool.map(work,tasks)) # Preserve all numerical outcomes, including failures.
    write_json(RUN/'calibration_fem.json',results); report=[] # Store exact label qualification and calibration ledger.
    for family in FAMILIES: # Calibrate each independently selected structural operator.
        selected=json.loads((RUN/f'selected_{family}.json').read_text());directory=RUN/'training'/f"round_{selected['selected_round']}"/family;representation=np.load(directory/'representation.npz');basis=representation['basis'];scale=float(representation['scale']);template=graph_template(load_base(family));models=[] # Load frozen training-only representations.
        for seed in [17,41,73]: # Restore independent model weights without refitting.
            checkpoint=torch.load(directory/f'model_seed_{seed}.pt',weights_only=False);model=GraphOperator(checkpoint['input_size'],checkpoint['rank']);model.load_state_dict(checkpoint['state_dict']);model.eval();models.append(model) # Keep selection and calibration logically separate.
        items=[m for m in entries if m['family']==family];p=np.array([m['params'] for m in items]);features=graph_features(template,p);baseline=polynomial(p)@representation['polynomial'];adj=torch.tensor(template['adj'],dtype=torch.float32) # Encode only new calibration inputs.
        with torch.no_grad(): members=np.array([model(torch.tensor(features),adj,torch.tensor(p,dtype=torch.float32),torch.tensor(baseline,dtype=torch.float32)).numpy() for model in models]) # Evaluate frozen ensemble on calibration cases.
        mean=members.mean(axis=0);predicted=mean@basis.T*scale*p[:,4,None];spread=np.linalg.norm(members-mean,axis=2).mean(axis=0)*scale*p[:,4];scores={};case_scores=[] # Construct displacement-field L2 uncertainty scale from real ensemble spread.
        for i,item in enumerate(items): # Build nonconformity using new FEM evidence only.
            receipt=json.loads((RUN/'cases'/item['id']/'receipt.json').read_text());assert receipt['status']=='VALID_CONVERGED';truth=np.load(RUN/'cases'/item['id']/'fields.npz')['u'].ravel();error=float(np.linalg.norm(predicted[i]-truth));score=error/max(spread[i],1e-12);scores.setdefault(item['geometry_id'],[]).append(score);case_scores.append(dict(item,field_error_L2_mm=error,spread_L2_mm=float(spread[i]),score=score)) # Group correlated load cases under one geometric calibration unit.
        grouped=np.array([max(v) for v in scores.values()]);threshold=float(np.max(grouped));evaluation=json.loads((directory/'evaluation.json').read_text());saved=np.load(directory/'predictions.npz');test_groups={};coverage=[] # Use the ninth order statistic for nominal 90-percent grouped calibration.
        for i,item in enumerate(evaluation['cases']): # Evaluate intervals only after threshold is frozen.
            if item['split'] not in ['test','ood']: continue # Keep fitting/selection cases out of coverage reporting.
            ensemble=saved['ensemble_coefficients'][:,i];center=ensemble.mean(axis=0);uncertainty=float(np.linalg.norm(ensemble-center,axis=1).mean()*scale*item['params'][4]);error=float(np.linalg.norm(saved['predicted'][i]-saved['reference'][i]));radius=threshold*max(uncertainty,1e-12);covered=error<=radius;ood=item['split']=='ood' # Compute actual held-out field norm coverage and domain rejection.
            coverage.append({'id':item['id'],'geometry_id':item['geometry_id'],'split':item['split'],'covered':bool(covered),'radius_L2_mm':radius,'error_L2_mm':error,'reject_ood':ood});test_groups.setdefault((item['split'],item['geometry_id']),[]).append(covered) # Preserve per-case and joint-per-geometry coverage.
        permutation=np.random.default_rng(7).permutation(features.shape[1]) # Independently test coarse graph node renumbering equivariance.
        with torch.no_grad(): original=models[0](torch.tensor(features[:1]),adj,torch.tensor(p[:1],dtype=torch.float32),torch.tensor(baseline[:1],dtype=torch.float32));shuffled=models[0](torch.tensor(features[:1,permutation]),adj[:,permutation][:,:,permutation],torch.tensor(p[:1],dtype=torch.float32),torch.tensor(baseline[:1],dtype=torch.float32));difference=float(torch.max(torch.abs(original-shuffled))) # Compare same physical graph under different node ordering.
        report.append({'family':family,'calibration_geometries':9,'calibration_cases':18,'nominal_group_coverage':.9,'calibration_order_statistic':9,'threshold':threshold,'calibration_cases_detail':case_scores,'test_coverage':coverage,'independent_test_geometry_coverage':float(np.mean([all(v) for (split,g),v in test_groups.items() if split=='test'])),'ood_rejection_count':sum(x['reject_ood'] for x in coverage),'permutation_max_coefficient_difference':difference,'qualification':'Empirical coverage only: Sobol test design and small sample do not prove exchangeability or universal finite-sample guarantees.'}) # State statistical limitations without conflating uncertainty and OOD.
        write_json(RUN/'calibration_evaluation.json',report);print(family,report[-1]['independent_test_geometry_coverage'],difference,flush=True) # Checkpoint each completed independent calibration.
if __name__=='__main__': main() # Execute the complete independent calibration experiment.
