#!/usr/bin/env python3  # Verify lossless full-field persistence and incomplete-history rejection independently of bridge mechanics.
import tempfile  # Isolate analytic storage fixtures from real engineering histories.
import unittest  # Assert numerical storage and qualification behavior explicitly.
from pathlib import Path  # Keep all fixture outputs inside their temporary case directories.
import h5py  # Inspect the exact persisted native-array representation.
import numpy as np  # Construct deterministic arithmetic fixtures without plotting.
from field_stream import FieldStream,verify_complete  # Exercise the same streaming implementation used by actual FEM campaigns.
class NativeStreamTests(unittest.TestCase):  # Keep software assertions separate from finite-element physical acceptance.
    def fixture(self,path):  # Declare a complete two-node storage fixture with one explicit axial-member channel.
        initial=np.arange(24,dtype=float).reshape(2,12)/17.  # Use nonzero unequal channels to detect loss or implicit zero filling.
        static={'coordinates':np.array([[0.,0.,0.],[3.,0.,0.]]),'initial_state':initial,'native_entity_ids':np.array([100,900]),'cable_native_element_ids':np.array([71])}  # Preserve nonconsecutive physical identities in the fixture.
        return FieldStream(path,static,3,{'scope':'ANALYTIC_STORAGE_FIXTURE_NOT_FEM'}),initial  # Require an initial frame and two subsequent complete frames.
    def append(self,stream,initial,index):  # Supply deterministic complete data at one strictly increasing fixture time.
        stream.append(index*.2,initial+index/11.,np.full((2,2),index/3.),np.full((2,6),index/5.),np.full((2,6),index/7.),{'time_s':index*.2},{'supports':{}},np.array([42.+index/13.]))  # Persist all motion, control, force, acceleration, and axial-force values.
    def test_lossless_fields_and_native_identities(self):  # Require every original value and source association to survive compression.
        with tempfile.TemporaryDirectory() as directory:  # Avoid altering any actual solver evidence.
            path=Path(directory)/'fields.h5'  # Select an isolated final numerical artifact.
            stream,initial=self.fixture(path)  # Freeze the complete analytic storage contract.
            for index in range(3):  # Write the exact declared frame population without temporal decimation.
                self.append(stream,initial,index)  # Exercise actual atomic frame persistence.
            stream.finish()  # Publish only the complete three-frame history.
            self.assertEqual(verify_complete(path)['frames'],3)  # Verify finalized lengths and exact causal initial state.
            with h5py.File(path,'r') as data:  # Inspect actual persisted bytes through their numerical representation.
                np.testing.assert_array_equal(data['targets'][2],initial+2/11.)  # Require lossless double-precision motion fields.
                np.testing.assert_array_equal(data['native_entity_ids'][...],[100,900])  # Preserve original nonconsecutive node identities.
                np.testing.assert_array_equal(data['cable_axial_force_N'][:,0],[42.+index/13. for index in range(3)])  # Preserve every independent axial-force time sample.
    def test_partial_history_is_rejected(self):  # Ensure an interrupted solve cannot silently enter supervised training.
        with tempfile.TemporaryDirectory() as directory:  # Keep rejected fixture evidence separate from real failures.
            path=Path(directory)/'fields.h5'  # Reserve a final artifact that must never be published.
            stream,initial=self.fixture(path)  # Require all three frames before acceptance.
            self.append(stream,initial,0)  # Retain one genuinely persisted fixture state.
            stream.abort('intentional interruption fixture')  # Record failure explicitly after partial progress.
            self.assertFalse(path.exists())  # An incomplete history must not acquire the final accepted path.
            with self.assertRaises(ValueError):  # Independent verification must reject the failed partial artifact.
                verify_complete(stream.partial)  # Inspect its actual persisted status and shape contract.
    def test_declared_cable_force_cannot_be_missing(self):  # Require actual native force output instead of invented zero labels.
        with tempfile.TemporaryDirectory() as directory:  # Isolate validation failures from actual simulation histories.
            stream,initial=self.fixture(Path(directory)/'fields.h5')  # Declare one required axial-member response.
            with self.assertRaises(ValueError):  # Missing declared force data must fail before any frame is accepted.
                stream.append(0.,initial,np.zeros((2,2)),np.zeros((2,6)),np.zeros((2,6)),{}, {})  # Deliberately omit the required native force array.
            self.assertEqual(stream.frames,0)  # No partially supplied frame may count toward completion.
            stream.abort('missing force fixture')  # Close rejected fixture resources without publishing valid data.
if __name__=='__main__':  # Run these bounded storage tests only when explicitly invoked.
    unittest.main()  # Report software pass/fail without claiming physical bridge validation.
