import json  # Store the refined dataset manifest and case identities.
import sys  # Resolve the local native modules.
from pathlib import Path  # Resolve repository and case directories.
import numpy as np  # Build full native node and integration point fields.
sys.path.insert(0, str(Path(__file__).resolve().parent))  # Import the checked-out finite-element code.
import complex_friction as native  # Reuse the exact mesh, deck, FRD, and IP readers.
ORIGINAL_DECK = native.deck  # Preserve the original deck builder before installing the reduced text-output wrapper.

ROOT = Path(__file__).resolve().parents[2]  # Resolve the repository root.
OUT = ROOT / 'build' / 'complex-nonlinear-20261024' / 'friction_mesh10x'  # Keep the refined dataset isolated.
MESH = [22, 11, 5]  # Preserve the ten-times physical-node refinement.

def deck_without_text_contact_print(desc):  # Keep FRD contact fields while avoiding the oversized DAT contact tables.
    text = ORIGINAL_DECK(desc)  # Generate the exact native nonlinear deck first.
    lines = text.splitlines()  # Edit only the optional text contact print requests.
    return '\n'.join(line for line in lines if not line.startswith('*CONTACT PRINT') and line not in ['CDIS,CSTR,CF,CFN,CFS,CNUM']) + '\n'  # Retain contact-file output and all node/IP fields.

def export_full_native(desc, folder):  # Export every requested FRD node field and every native volume IP stress field.
    data = native.inputs(desc)  # Allocate the complete graph without spatial reduction.
    n = int(data['physical_node_count'])  # Read the physical node count from the generated geometry.
    frd = native.frd_fields(folder / 'contact.frd', n)  # Read all actual FRD output frames.
    ips = native.integration_fields(folder / 'contact.dat')  # Read all native integration point stresses.
    for index, timepoint in enumerate(data['times'][1:], 1):  # Fill every requested response time after the known initial state.
        key = min(frd, key=lambda value: abs(value - timepoint))  # Match the native FRD time without interpolation.
        ipkey = min(ips, key=lambda value: abs(value - timepoint))  # Match the native IP table time without interpolation.
        assert abs(key - timepoint) < 1.e-7 and abs(ipkey - timepoint) < 1.e-7  # Reject missing native frames.
        frame = frd[key]  # Read the exact native node fields.
        ip = ips[ipkey]  # Read the exact native element integration point stresses.
        assert frame['DISP'].shape == (n, 3) and ip.shape[0] == len(data['element_connectivity']) * 8  # Reject incomplete native fields.
        data['states'][index, :n, :3] = frame['DISP']  # Preserve every physical nodal displacement.
        data['states'][index, n:, 3:9] = ip[:, 2:8]  # Preserve every native C3D8 integration point stress.
        data['states'][index, ~data['state_mask']] = 0.  # Keep location masks explicit for unused channels.
    native.dump(folder / 'metadata.json', native.metadata(desc, data))  # Record the refined entity and field contract.
    np.savez_compressed(folder / 'fields.npz', **data)  # Write the complete full-field training tensor.
    audit = {'quality': 'VALID_CONVERGED', 'scope': 'native FRD nodal displacement plus native EL PRINT integration-point stress', 'contact_quadrature_text_export': 'omitted to avoid oversized DAT print; FRD nodal contact retained', 'all_native_output_times_complete': True, 'physical_node_count': n, 'volume_IP_count': len(data['element_connectivity']) * 8, 'graph_entity_count': len(data['xyz']), 'mesh': MESH}  # Make the contact-print scope explicit.
    native.dump(folder / 'audit.json', audit)  # Preserve the qualification receipt.
    return native.row(desc, folder, 'VALID_CONVERGED')  # Admit only solver-complete full native node/IP labels.

def main():  # Complete the missing training and validation cases.
    native.OUT = OUT  # Route all native outputs into the refined archive.
    native.deck = deck_without_text_contact_print  # Prevent DAT text output from truncating late IP frames.
    native.audit_and_export = export_full_native  # Admit complete FRD and native IP fields with the refined export contract.
    descriptors = native.design()  # Reuse the fixed train and validation physical groups.
    rows = []  # Collect the completed refined rows.
    existing = OUT / 'cases' / 'mesh10x_full_friction_000'  # Reuse the already completed first refined retry.
    if (existing / 'case.json').exists():  # Load the first completed retry without rerunning it.
        rows.append(json.loads((existing / 'case.json').read_text()))  # Preserve the actual native result.
    source8 = dict(descriptors[8])  # Prepare the already solved original validation native output.
    source8['mesh'] = list(MESH)  # Bind the validation export to the refined mesh.
    source8['id'] = 'mesh10x_friction_008'  # Keep the original complete native directory identity.
    source8['group_id'] = source8['id']  # Preserve the physical group identity.
    original8 = OUT / 'cases' / source8['id']  # Locate the existing native validation output.
    if (original8 / 'receipt.json').exists() and not (original8 / 'case.json').exists():  # Export its complete FRD and IP fields once.
        rows.append(export_full_native(source8, original8))  # Use the native output without rerunning the solver.
        (original8 / 'case.json').write_text(json.dumps(rows[-1], indent=2, ensure_ascii=False) + '\n')  # Persist its qualified row.
    for source in [descriptors[1], descriptors[9], descriptors[10]]:  # Solve only the remaining failed or missing histories.
        folder = OUT / 'cases' / ('mesh10x_full_' + source['id'])  # Use an immutable retry namespace.
        if (folder / 'case.json').exists():  # Reuse only an already completed retry.
            rows.append(json.loads((folder / 'case.json').read_text()))  # Load the existing qualified row.
            continue  # Avoid rerunning a completed native case.
        desc = dict(source)  # Preserve the registered physical parameter group.
        desc['mesh'] = list(MESH)  # Apply the ten-times mesh contract.
        desc['id'] = 'mesh10x_full_' + source['id']  # Isolate this output namespace.
        desc['group_id'] = desc['id']  # Keep the retry group identity explicit.
        row = native.solve_candidate(desc)  # Run the complete nonlinear native history and custom export.
        rows.append(row)  # Retain the actual native result.
        (folder / 'case.json').write_text(json.dumps(row, indent=2, ensure_ascii=False) + '\n')  # Persist the retry row.
    print(json.dumps({'completed': len(rows), 'qualities': [row['quality'] for row in rows]}, ensure_ascii=False), flush=True)  # Report only actual outcomes.

if __name__ == '__main__':  # Keep imports free from solver execution.
    main()  # Execute the refined completion pass.
