#!/usr/bin/env python3
import unittest # Verify numerical identities independently of a bridge solve.
import tempfile # Isolate deliberately invalid provenance fixtures.
import hashlib # Bind the fixture's explicit native input receipt.
import json # Write the minimal process evidence used by the admission test.
from pathlib import Path # Keep temporary evidence scoped to the test.
import numpy as np # Exact numerical geometry and tensor tests without visualization.
from quadratic_solid import NATURAL, GAUSS, shape, gauss_shape # Actual native interpolation under test.
from corotate_native_history import corotate # Objective material-frame tensor conversion.
from extract_native_history import extract # Verify physical identity gates before accepting any native field.
class QuadraticSolidTests(unittest.TestCase): # Tests target physical identities and solver conventions.
    def test_nodal_and_affine_reproduction(self): # A twenty-node solid must reproduce nodal values and affine motion.
        for i,q in enumerate(NATURAL): # Include all corner and midside coordinates.
            np.testing.assert_allclose(shape(q)[0],np.eye(20)[i],atol=1e-14) # Exact Kronecker interpolation.
        for q in np.random.default_rng(73).uniform(-1,1,(30,3)): # Check independent interior points.
            n,d=shape(q) # Obtain actual shape and analytic derivatives.
            np.testing.assert_allclose(n.sum(),1.,atol=1e-13) # Partition of unity.
            np.testing.assert_allclose(n@NATURAL,q,atol=1e-13) # Affine coordinates are exact.
            np.testing.assert_allclose(NATURAL.T@d,np.eye(3),atol=1e-13) # Affine gradients are exact.
    def test_native_gauss_order(self): # Guard the actual CalculiX 2.21 gauss.f convention.
        expected=np.array([[-1,-1,-1],[1,-1,-1],[-1,1,-1],[1,1,-1],[-1,-1,1],[1,-1,1],[-1,1,1],[1,1,1]])/np.sqrt(3.) # gauss3d2 is x-fast, then y, then z.
        np.testing.assert_array_equal(GAUSS,expected) # An unordered-equivalence test would miss wrong stress/IP matching.
    def test_gradient_finite_difference(self): # Analytic derivatives must match independent central differences.
        for q in np.random.default_rng(74).uniform(-.8,.8,(12,3)): # Avoid roundoff-dominated endpoint differences.
            _,d=shape(q) # Analytic derivative under test.
            fd=np.column_stack([(shape(q+np.eye(3)[k]*1e-6)[0]-shape(q-np.eye(3)[k]*1e-6)[0])/2e-6 for k in range(3)]) # Independent numerical derivatives.
            np.testing.assert_allclose(d,fd,atol=1e-9) # Tight first-derivative agreement.
    def test_rigid_rotation_all_twenty_nodes(self): # All quadratic nodes must recover an objective finite rotation.
        _,grad=gauss_shape(); xyz=NATURAL@np.diag([4.,3.,2.])+[3.,7.,9.] # Independent affine physical brick.
        rotation=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]) # Finite ninety-degree rotation.
        displacement=xyz@rotation.T+[7.,-2.,4.]-xyz # Include a rigid translation to test gradient cancellation.
        jac=np.einsum('ni,gnj->gij',xyz,grad); physical=grad@np.linalg.inv(jac) # Actual quadratic reference gradients.
        deformation=np.eye(3)+np.einsum('ni,gnj->gij',displacement,physical) # Recover F from all twenty nodal motions.
        np.testing.assert_allclose(deformation,np.broadcast_to(rotation,deformation.shape),atol=2e-14) # Exact rigid kinematics.
        _,strain=corotate(np.zeros((8,6)),deformation) # Corotated zero-stress material frame.
        np.testing.assert_allclose(strain,0.,atol=2e-14) # A finite rigid rotation must not create fatigue strain.
    def test_diagnostic_cannot_be_relabeled_full_bundle(self): # A one-wire mesh must never be admitted by passing a283-wire CLI value.
        with tempfile.TemporaryDirectory() as directory: # Keep the synthetic invalid-input fixture separate from real results.
            folder=Path(directory); source=folder/'saddle.inp'; source.write_text('*HEADING\nAdmission regression fixture\n') # This fixture is never a finite-element solve.
            (folder/'native.log').write_text('Job finished\n') # Deliberately insufficient textual completion marker.
            (folder/'native_completion.json').write_text(json.dumps({'field_export_admitted':True,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})) # A matching input hash still cannot override mesh identity.
            np.savez(folder/'geometry.npz',wire_id=np.array([1]),connectivity=np.arange(20)[None,:]) # Exactly one actual wire element.
            with self.assertRaisesRegex(ValueError,'Wire count'): extract(folder/'saddle.dat',source,folder/'native.log',folder/'cycle.npz',1.,4.,283) # Refuse before reading or allocating any claimed full-bundle history.
if __name__=='__main__': unittest.main() # Run only explicitly requested regression tests.
