#!/usr/bin/env python3  # Guard against incorrectly qualifying a corrupted native restart state.
import copy  # Change one independent physical state quantity per rejection test.
import json  # Require failure receipts to remain portable JSON evidence.
import os  # Enable costly native integration checks only when explicitly requested.
from pathlib import Path  # Bind native tests to an isolated disposable checkpoint directory.
import tempfile  # Avoid changing genuine solver evidence during regression tests.
import unittest  # Report independent physical restart guards with standard tooling.
from native_restart_probe import compare,run  # Test the actual physical comparison and native serialization path.
def state():  # Supply a known complete state contract for corruption-detection tests.
    return {'time':.04,'nodes':[1,2],'elements':[3],'coordinates':[[0.,0.,0.],[1.,0.,0.]],'displacement':[[0.]*6,[.01,0.,0.,0.,0.,0.]],'velocity':[[0.]*6,[.2,0.,0.,0.,0.,0.]],'acceleration':[[0.]*6,[-3.,0.,0.,0.,0.,0.]],'mass':[[.01,.01,.01,0.,0.,0.]]*2,'element_forces':{'3':[-20.,0.,0.,20.,0.,0.]},'cable_stress':[100.],'cable_strain':[.0005],'load_factors':[1.,.3]}  # Preserve independent motion, inertia, material, and load quantities.
class RestartPhysicalGuards(unittest.TestCase):  # Require corrupted physical states to fail even if native restore returns success.
    def test_changed_acceleration_or_future_load_rejected(self):  # Catch restart implementations that restore displacement alone.
        baseline=state()  # Freeze known committed response before corruption.
        for key,index,delta in [('acceleration',(1,0),.1),('load_factors',(1,),.01),('cable_stress',(0,),1.)]:  # Exercise inertia, future forcing, and prestress independently.
            with self.subTest(quantity=key):  # Identify precisely which physical guard could regress.
                actual=copy.deepcopy(baseline)  # Isolate this one quantity from other checks.
                if len(index)==2:  # Handle the full nodal degree array without flattening it.
                    actual[key][index[0]][index[1]]+=delta  # Inject a physically consequential restart error.
                else:  # Handle independently stored load or material quantities.
                    actual[key][index[0]]+=delta  # Change only the selected physical scalar.
                self.assertFalse(compare(baseline,actual)['passed'])  # Reject incomplete state restoration independently of API success.
    def test_missing_element_and_truncated_state_rejected(self):  # Ensure a missing native component cannot silently qualify.
        baseline=state()  # Keep the full reference domain contract.
        actual=copy.deepcopy(baseline)  # Prepare a response with a corrupted native force vector.
        actual['element_forces']['3']=actual['element_forces']['3'][:3]  # Simulate incomplete element serialization.
        result=compare(baseline,actual)  # Evaluate without crashing on incompatible response arrays.
        self.assertFalse(result['passed'])  # Reject missing physical element force components.
        json.dumps(result,allow_nan=False)  # Require portable strict-JSON failure evidence rather than NaN or infinity.
    def test_preserved_state_and_nonfinite_failure(self):  # Accept preserved state while rejecting invalid numeric output.
        baseline=state()  # Define known finite physical quantities.
        self.assertTrue(compare(baseline,copy.deepcopy(baseline))['passed'])  # Verify exact restoration remains admissible.
        actual=copy.deepcopy(baseline)  # Isolate an invalid restored material response.
        actual['cable_stress'][0]=float('nan')  # Simulate a native material state that cannot be interpreted physically.
        result=compare(baseline,actual)  # Preserve this corruption as a failed physical comparison.
        self.assertFalse(result['passed'])  # Forbid nonfinite restart output from entering later simulation.
        json.dumps(result,allow_nan=False)  # Keep the failure report serializable for remote campaign receipts.
    @unittest.skipUnless(os.environ.get('RESTART_NATIVE_INTEGRATION')=='1','Set RESTART_NATIVE_INTEGRATION=1 to require native backend qualification.')  # Keep an intentionally blocked backend qualification separate from deterministic guard tests.
    def test_native_mixed_element_continuation(self):  # Qualify actual save, destruction, restore, and future response in all required families.
        with tempfile.TemporaryDirectory() as directory:  # Isolate every native database fragment from genuine work products.
            for kind in ('beam','ShellNLDKGQ','ASDShellQ4'):  # Cover the control and both bridge shell candidates explicitly.
                with self.subTest(fixture=kind):  # Report unsupported native element families independently.
                    result=run(kind,Path(directory)/kind)  # Execute actual nonzero native history on both continuation paths.
                    self.assertEqual(result['status'],'PASSED_FIXTURE',result.get('error',result.get('stage')))  # Reject API-only or physically different restart behavior.
if __name__=='__main__':  # Allow standard command-line regression execution.
    unittest.main()  # Return nonzero whenever any enabled physical qualification fails.
