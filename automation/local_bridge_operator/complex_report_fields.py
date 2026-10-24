from pathlib import Path  # Resolve frozen test predictions and their exact source reference.
import argparse  # Require an explicit completed learning experiment.
import hashlib  # Preserve the result identities behind each scientific curve.
import json  # Save curve locations and plotting provenance for independent inspection.
import numpy as np  # Compare actual complete native and neural histories numerically.
import matplotlib  # Use conventional reproducible scientific plotting.
matplotlib.use('Agg')  # Render figures without a browser or desktop.
import matplotlib.pyplot as plt  # Draw measured FEM and neural response histories.
REPO = Path(__file__).resolve().parents[2]  # Resolve exact repository evidence locations.
def sha(path):  # Identify each complete input result independently of its filename.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Hash the actual stored prediction bytes.
def render(folder):  # Plot the first registered independent test case only after final evaluation exists.
    folder = Path(folder).resolve()  # Preserve the explicit selected experiment identity for absolute and relative CLI paths.
    metrics = json.loads((folder / 'final_test/active/metrics.json').read_text())  # Refuse to open development data and label it as final testing.
    row = next(item for item in metrics['cases'] if item['split'] == 'test')  # Use a deterministic test history without choosing the best-performing case.
    path = folder / 'final_test/active' / (row['id'] + '.npz')  # Load the saved raw prediction and matching native reference.
    with np.load(path) as archive: data = {name: archive[name] for name in archive.files}  # Materialize only this completed held-out field result.
    fields = data['fields'].tolist()  # Read actual producer field names without inventing units or channels.
    schemas = [('ux_mm', 'IP_sxy_MPa', 'nodal_CSLIP1_mm'), ('ux', 'sxx', 'peeq')]  # Use explicitly supported native friction and material field schemas.
    selected = next((list(schema) for schema in schemas if all(name in fields for name in schema)), [])  # Keep three measured displacement, nonlinear stress and interface or plastic-history channels.
    assert selected  # Refuse a plot whose registered field schema is unsupported.
    fig, axes = plt.subplots(1, len(selected), figsize=(5 * len(selected), 4.3), layout='constrained', squeeze=False)  # Use independent axes because physical units differ.
    curves = []  # Retain every selected physical entity and its actual curve values.
    for axis, field in zip(axes[0], selected):  # Render a native-versus-neural comparison for each selected quantity.
        channel = fields.index(field)  # Preserve the exact source channel mapping.
        mask = data['state_mask'][:, channel].astype(bool)  # Restrict comparison to entities where this physical quantity is defined.
        errors = np.sum((data['prediction'][1:, :, channel] - data['reference'][1:, :, channel]) ** 2, axis=0)  # Find the largest observed trajectory error within this fixed test history.
        errors[~mask] = -1.0  # Exclude undefined nodes and integration points without dropping any defined comparison.
        entity = int(np.argmax(errors))  # Explicitly choose a difficult location rather than a visually favorable curve.
        native = data['reference'][:, entity, channel]  # Read the genuine same-location finite-element response.
        neural = data['prediction'][:, entity, channel]  # Read the uncorrected cold-rollout neural response.
        frame = np.arange(len(native))  # Use the recorded observation index without inventing a physical time unit.
        axis.plot(frame, native, color='#283d4b', linewidth=1.8, label='Native FEM')  # Show the source finite-element history directly.
        axis.plot(frame, neural, color='#bc672f', linewidth=1.5, linestyle='--', label='Raw neural rollout')  # Keep the neural prediction visibly distinguishable.
        labels = {'ux':'ux (mm)', 'sxx':'Cauchy sxx (MPa)', 'peeq':'Accumulated equivalent plastic strain'}  # State verified material-field units when the native producer uses short channel names.
        axis.set(title=field, xlabel='Recorded history frame', ylabel=labels.get(field, field))  # Preserve exact channel identity and declared physical units without inventing physical time.
        axis.grid(alpha=.2)  # Provide restrained visual references for the measured response.
        axis.spines[['top', 'right']].set_visible(False)  # Avoid decorative plot borders.
        axis.legend(fontsize=8)  # Identify both actual calculation sources.
        curves.append({'field': field, 'entity_index': entity, 'reference_xyz_mm': data['xyz'][entity].tolist(), 'selection_rule': 'largest summed squared trajectory mismatch among defined entities in the first registered test history', 'observation_frames': frame.tolist(), 'native_FEM': native.tolist(), 'raw_neural': neural.tolist()})  # Preserve the complete reproducible location and curve data.
    fig.suptitle(row['id'] + ': actual held-out history at difficult field locations', fontsize=12)  # Identify the exact independently held-out physical history.
    output = folder / 'fullfield_history_comparison.png'  # Keep the figure inside the archived learning evidence.
    fig.savefig(output, dpi=180)  # Save a standalone scientific figure for readable report embedding.
    plt.close(fig)  # Release rendering memory before subsequent native computations.
    receipt = {'case_id': row['id'], 'split': row['split'], 'field_result': str(path.relative_to(REPO)), 'field_result_sha256': sha(path), 'figure': str(output.relative_to(REPO)), 'curves': curves, 'scope': 'Post-freeze descriptive test visualization; no model selection or retraining uses these locations.'}  # Distinguish post-test reporting from model development.
    output.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n')  # Save exact figure provenance and raw curve data beside the image.
    return output  # Let the final report embed the real measured figure.
if __name__ == '__main__':  # Expose a reproducible final-report command.
    parser = argparse.ArgumentParser(); parser.add_argument('experiment'); args = parser.parse_args(); print(render(args.experiment))  # Require a specific completed experiment and report the saved figure.
