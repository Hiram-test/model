import json # Read the completed model receipts without changing selection decisions.
import numpy as np # Compare replayed full fields with preserved independent test predictions.
import torch # Reload every actual saved neural checkpoint.
from nonlinear_train import Operator,load_family,prepare,predict # Reuse the identical geometry-isolated prediction pipeline.
from nonlinear_mechanics import OUT # Locate the independent nonlinear research package.
from fem import write_json,sha # Verify model provenance before replay.
def main(): # Verify all six trained checkpoints and all their held-out field predictions.
    training=json.loads((OUT/'training_results.json').read_text());results=[] # Preserve one reproducibility result per independent seed.
    for family in ['splice','deck']: # Reconstruct only training-derived bases and fixed independent inputs.
        basis,scale,singular,batches=prepare(load_family(family));saved=np.load(OUT/'models'/family/'basis.npz');basis_difference=float(np.max(np.abs(basis-saved['basis']))) # Check the persisted spatial operator basis against its deterministic construction.
        for receipt in (r for r in training if r['family']==family): # Reload every completed optimization rather than only the selected model.
            directory=OUT/'models'/family/f"seed_{receipt['seed']}";path=directory/'best.pt';checkpoint=torch.load(path,weights_only=False);model=Operator(checkpoint['rank']);model.load_state_dict(checkpoint['state_dict']);model.eval();hash_match=sha(path)==receipt['checkpoint_sha256'] # Require exact checkpoint identity and architecture agreement.
            with torch.no_grad(): coefficients=predict(model,batches['test']).numpy() # Replay the same complete held-out batch with no optimization.
            differences=[] # Compare every source geometry and load state independently.
            for i,item in enumerate(batches['test'][3]): actual=(coefficients[i]*scale@basis.T).reshape(item['displacement'].shape);reference=np.load(directory/f"{item['id']}_prediction.npz")['prediction'];differences.append(float(np.max(np.abs(actual-reference)))) # Confirm saved raw full-field predictions match the actual loaded weights.
            maximum=max(differences);results.append({'family':family,'seed':receipt['seed'],'checkpoint_hash_matches':hash_match,'training_basis_max_abs_difference':basis_difference,'replayed_field_frames':36,'max_abs_prediction_difference_mm':maximum,'status':'PASS' if hash_match and basis_difference==0 and maximum==0 else 'FAIL','checkpoint':str(path.relative_to(OUT.parent.parent))}) # Preserve a strict bitwise numerical-replay gate.
    write_json(OUT/'checkpoint_reload_verification.json',results);assert all(r['status']=='PASS' for r in results);print('PASS',sum(r['replayed_field_frames'] for r in results)) # Require all six neural runs to reproduce all 216 saved test fields exactly.
if __name__=='__main__': main() # Execute the final neural checkpoint and prediction provenance audit.
