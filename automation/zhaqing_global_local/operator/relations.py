"""Physical-radius integration supports on every original mesh entity.""" # A fixed metric radius avoids shrinking support when the mesh is refined.
import numpy as np # Preserve explicit native source and target arrays.
from scipy.spatial import cKDTree # Find physical neighborhoods without a dense all-pairs distance matrix.

def radius_relation(coordinates, source_indices, target_indices, radius, source_measure, relation_type): # Integrate one declared physical domain over a mesh-independent metric ball.
    coordinates = np.asarray(coordinates, dtype=float) # Use original physical coordinates in a single declared length unit.
    source, target = np.asarray(source_indices, dtype=np.int64), np.asarray(target_indices, dtype=np.int64) # Keep all supplied native entity IDs without coarsening.
    if not np.isfinite(radius) or radius <= 0 or len(source) == 0 or len(target) == 0: # A physical support needs a finite positive radius and nonempty domains.
        raise ValueError('Invalid physical integration support') # Refuse implicit or mesh-dependent radius defaults.
    measure = np.asarray(source_measure, dtype=float) # Use positive nodal dual volumes, areas or line lengths for the relevant domain.
    if measure.shape != (len(coordinates),) or not np.isfinite(measure).all() or np.any(measure[source] <= 0): # Require a physical quadrature weight for every source sample.
        raise ValueError('Invalid source quadrature measure') # Do not substitute node degree or nearest-neighbor count.
    tree = cKDTree(coordinates[source]) # Index all original source entities in this physical domain.
    neighbors = tree.query_ball_point(coordinates[target], r=float(radius), return_sorted=True) # Include every source inside the fixed physical metric support.
    source_edges = np.concatenate([source[indices] for indices in neighbors]) # Retain every discovered integration sample.
    target_edges = np.repeat(target, [len(indices) for indices in neighbors]) # Map each quadrature contribution to its evaluation entity.
    edges = np.stack((source_edges, target_edges)) # Preserve a source-to-target relation table without graph pooling.
    return edges, np.full(len(source_edges), int(relation_type), dtype=np.int64), measure[source_edges] # Return actual physical measures for later fixed-reference nondimensionalization.
