import json  # Keep the refinement contract machine-readable.
import sys  # Resolve the local operator modules from this repository.
from pathlib import Path  # Keep all generated evidence under the repository build tree.
import numpy as np  # Record exact mesh-size and entity-count invariants.

ROOT = Path(__file__).resolve().parents[2]  # Resolve the checked-out repository root.
MODULE_DIR = Path(__file__).resolve().parent  # Resolve the local finite-element module directory.
sys.path.insert(0, str(MODULE_DIR))  # Make the frozen contact modules importable without installation.
import complex_friction as native  # Reuse the complete native finite-sliding nonlinear path.
from contact_solver import mesh  # Reuse the exact geometry generator used by the solver deck.

REFINED_MESH = [22, 11, 5]  # Increase the deformable block subdivisions until physical nodes exceed ten times the baseline.
BASELINE_MESH = [8, 4, 2]  # Freeze the previously used reference mesh for an explicit factor check.
OUT = ROOT / 'build' / 'complex-nonlinear-20261024' / 'friction_mesh10x'  # Keep refined evidence separate from the small-mesh archive.

def counts(mesh_spec):  # Compute physical nodes, elements, and graph entities from the native geometry.
    xyz, elements, _ = mesh(*mesh_spec)  # Generate the actual two-body contact geometry.
    return {'physical_nodes': int(len(xyz)), 'elements': int(len(elements)), 'graph_entities': int(len(xyz) + 8 * len(elements))}  # Count every node and every eight-point volume location.

def main():  # Solve the registered training and validation histories on the refined mesh.
    OUT.mkdir(parents=True, exist_ok=True)  # Create the isolated refined dataset directory.
    baseline = counts(BASELINE_MESH)  # Measure the old discretization from the same geometry generator.
    refined = counts(REFINED_MESH)  # Measure the new discretization before any solver call.
    assert refined['physical_nodes'] >= 10 * baseline['physical_nodes']  # Reject a refinement that does not meet the requested node factor.
    assert refined['graph_entities'] >= 10 * baseline['graph_entities']  # Reject a refinement that does not meet the operator entity factor.
    native.OUT = OUT  # Route native decks, responses, and immutable receipts into the refined archive.
    descriptors = native.design()[:11]  # Keep the original eight training and three validation physical groups.
    rows = []  # Collect only actual solver outcomes.
    for source in descriptors:  # Solve each registered train or validation history once.
        descriptor = dict(source)  # Preserve the original physical path and parameter identity.
        descriptor['mesh'] = list(REFINED_MESH)  # Replace only the spatial discretization with the ten-times contract.
        descriptor['id'] = 'mesh10x_' + str(source['id'])  # Give every refined case a collision-free immutable namespace.
        descriptor['group_id'] = descriptor['id']  # Keep refined cases isolated from the small-mesh groups.
        rows.append(native.solve_candidate(descriptor))  # Run and independently audit the full native nonlinear history.
    manifest = {'schema': 'bridge.friction.mesh_refinement.v1', 'baseline_mesh': BASELINE_MESH, 'refined_mesh': REFINED_MESH, 'baseline_counts': baseline, 'refined_counts': refined, 'node_factor': refined['physical_nodes'] / baseline['physical_nodes'], 'graph_entity_factor': refined['graph_entities'] / baseline['graph_entities'], 'cases': rows, 'training_cases': 8, 'validation_cases': 3, 'solver_scope': 'native CalculiX full-field contact; no response interpolation or spatial reduction'}  # Publish the exact refinement and native quality denominator.
    (OUT / 'mesh10x_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')  # Flush the auditable refinement result.
    print(json.dumps({'out': str(OUT), 'baseline': baseline, 'refined': refined, 'node_factor': manifest['node_factor'], 'graph_entity_factor': manifest['graph_entity_factor'], 'qualities': [row['quality'] for row in rows]}, ensure_ascii=False), flush=True)  # Expose concise live status.

if __name__ == '__main__':  # Keep imports free from solver execution.
    main()  # Execute only when the refinement driver is called directly.
