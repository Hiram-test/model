from pathlib import Path  # Keep this implementation diagnosis separate from the bridge's physical assumptions.
import json, numpy as np  # Compare actual native kinematics without target frequencies.
from scipy.spatial.transform import Rotation  # Compute finite rigid-point motion independently.
from physical_connectors import Deck  # Test the exact native connector representation under controlled alternatives.
from native_checks import solve, BOX  # Reuse this turn's native beam fixture and fresh solver invocation.
ROOT=Path(__file__).parent  # Preserve all current diagnosis inputs and outputs.
def execute():  # Compare equivalent representations to distinguish physical freedom from a solver-coordinate artifact.
    results={}  # Record all alternatives, including unsuccessful ones.
    for variant in ['actual_point_mass','reverse_rotation_equations','reverse_with_mass','mass_on_all_witnesses','no_witnesses','free_tip_load','separate_translation_reference']:  # Each change concerns only this local kinematic test.
        d=Deck('Native finite-offset coordinate probe: '+variant);a=d.node((0.,0.,0.));b=d.node((0.,2.,0.));d.beam(a,b,BOX,'fixture',8);d.fixed.update((a,i) for i in range(1,7));r=np.array([.23,.17,.41]);theta=np.array([.03,.02,-.04]);p=d.arm(b,d.nodes[b]+r,mass=1. if variant in ('actual_point_mass','reverse_with_mass','free_tip_load') else 0.);members,rot=d.offset_bodies[b]  # Use identical beam geometry, finite rotation and rigid attachment offset.
        if variant.startswith('reverse'):d.equations=[[(b,k+4,1.),(rot,k+1,-1.)] for k in range(3)]  # Reverse only the algebraic dependent variable; the physical relative rotation condition is unchanged.
        if variant=='mass_on_all_witnesses':  # Activate actual static structural-node bookkeeping without adding elastic stiffness or gravity.
            for n in members:d.add_mass(n,1.)  # Test masses have no influence on a zero-gravity static kinematic relation.
        if variant=='no_witnesses':members[:]=[p]  # Test whether redundant massless orientation points cause a native coordinate singularity.
        if variant=='separate_translation_reference':  # Avoid using a physical beam node directly as an external rigid body's reference.
            reference=d.newnode(d.nodes[b]);d.bodies=[(nodes,reference,q,label) if oldref==b else (nodes,oldref,q,label) for nodes,oldref,q,label in d.bodies]  # Preserve the same physical position with a distinct coordinate proxy.
            for k in range(3):d.equations.append([(reference,k+1,1.),(b,k+1,-1.)])  # Impose exact translation equivalence without grounding either reference.
        d.labels={'tip':b,'point':p,'rotation':rot};prescribed=[(b,k+1,0.) for k in range(3)]+[(b,k+4,float(theta[k])) for k in range(3)] if variant!='free_tip_load' else None;loads=[(p,3,-10.)] if variant=='free_tip_load' else None  # Compare prescribed-motion and load-driven kinematics independently.
        native=solve(d,'probe_'+variant,loads=loads,prescribed=prescribed);actual=np.array(native['displacements'][p])-np.array(native['displacements'][b]) if p in native['displacements'] and b in native['displacements'] else None;angle=np.array(native['displacements'][rot]) if rot in native['displacements'] else theta;prediction=Rotation.from_rotvec(angle).apply(r)-r  # Use the actual native control rotation in the load-driven case.
        results[variant]={'native_exit':native['exit'],'relative_point_displacement_m':actual.tolist() if actual is not None else None,'native_rotation_vector_rad':angle.tolist(),'independent_finite_rotation_prediction_m':prediction.tolist(),'max_kinematic_error_m':float(np.max(np.abs(actual-prediction))) if actual is not None else None}  # Do not infer success from a solver exit code alone.
    (ROOT/'results/native_checks/offset_probes.json').write_text(json.dumps(results,indent=2));print('FINITE_OFFSET_REPRESENTATION_PROBES',json.dumps(results),flush=True);return results  # Preserve actual numerical evidence for selecting a physically equivalent representation.
