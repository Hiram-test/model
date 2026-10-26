#!/usr/bin/env python3  # Persist complete native histories with memory bounded by one accepted time frame.
import hashlib  # Compute file identities without reading multi-gigabyte histories into memory.
import json  # Serialize explicit status, provenance, and variable-size interface histories.
import os  # Commit complete artifacts atomically on the same filesystem.
from pathlib import Path  # Keep each stream and its evidence inside one case directory.
import h5py  # Store exact numerical values with lossless chunk compression.
import numpy as np  # Validate physical array shapes and finite numerical values.
def file_sha256(path):  # Hash large completed histories using bounded-memory sequential reads.
    digest=hashlib.sha256()  # Initialize an independent content identity.
    with Path(path).open('rb') as stream:  # Open the actual artifact rather than a summary surrogate.
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):  # Bound temporary hash storage to four megabytes.
            digest.update(chunk)  # Include every persisted byte in order.
    return digest.hexdigest()  # Return the immutable file identity.
def atomic_json(path,value):  # Replace status only after a complete JSON document reaches disk.
    path=Path(path)  # Normalize the selected case-local destination.
    temporary=path.with_name(path.name+'.tmp')  # Use the same filesystem for atomic rename.
    with temporary.open('w') as stream:  # Write a complete new receipt separately from the visible previous state.
        json.dump(value,stream,indent=2,allow_nan=False)  # Reject nonfinite status values instead of publishing invalid JSON.
        stream.write('\n')  # Keep the receipt directly inspectable with text tools.
        stream.flush()  # Flush Python buffers before the filesystem durability request.
        os.fsync(stream.fileno())  # Persist the exact receipt contents before replacement.
    os.replace(temporary,path)  # Expose the complete receipt atomically.
def verify_complete(path):  # Reject interrupted streams before any downstream training consumes them.
    with h5py.File(path,'r') as data:  # Inspect persisted attributes and actual array lengths independently.
        expected=int(data.attrs['expected_frames'])  # Read the explicitly requested complete history length.
        names=('times','targets','controls','applied_force_moment','acceleration')+(('cable_axial_force_N',) if 'cable_native_element_ids' in data else ())  # Require every declared physical temporal array, including full cable forces where exported.
        if data.attrs.get('status')!='COMPLETE' or int(data.attrs.get('written_frames',-1))!=expected:  # Require a successful explicit finalization receipt.
            raise ValueError('Incomplete native history cannot enter training')  # Prevent failed or truncated histories from becoming labels.
        if any(len(data[name])!=expected for name in names):  # Cross-check actual array shapes rather than trusting the receipt alone.
            raise ValueError('Native history frame counts do not match its completion receipt')  # Expose corrupted or partially written data.
        if not np.array_equal(data['targets'][0],data['initial_state'][...] ) or float(data['times'][0])!=0.:  # Preserve the actual causal initial state exactly.
            raise ValueError('Native initial state is missing or inconsistent')  # Reject silently shifted or synthetic initial conditions.
        return {'frames':expected,'nodes':len(data['coordinates']),'metadata':json.loads(data.attrs['metadata_json'])}  # Return small verified provenance without loading full fields.
class FieldStream:  # Keep every native entity and accepted time step while bounding transient storage memory.
    def __init__(self,path,static,expected_frames,metadata):  # Open an isolated new stream with immutable mesh and provenance.
        self.path=Path(path)  # Preserve the exact requested final artifact identity.
        self.path.parent.mkdir(parents=True,exist_ok=True)  # Create only the selected case output directory.
        self.partial=self.path.with_name(self.path.stem+'.partial'+self.path.suffix)  # Keep unfinished histories visibly distinct from accepted data.
        self.status_path=self.path.with_name(self.path.stem+'_stream_status.json')  # Publish bounded progress and failure evidence separately.
        self.audit_path=self.path.with_name('step_audits.jsonl')  # Stream one accepted physical-balance audit per frame.
        self.saddle_path=self.path.with_name('saddle_motion.jsonl')  # Stream every actual cable-cut interface state without growing RAM.
        self.expected=int(expected_frames)  # Freeze the requested complete frame count before writing.
        self.frames=0  # Count only fully appended native time frames.
        self.last_time=None  # Enforce a strictly increasing physical time grid.
        self.closed=False  # Track ownership of live HDF5 and JSONL handles.
        self.metadata=dict(metadata)  # Bind source and mesh identities to the immutable stream.
        if self.expected<2:  # Require an initial state plus at least one physical evolution step.
            raise ValueError('A native history requires at least two frames')  # Reject a static field mislabeled as transient training data.
        if self.path.exists() or self.partial.exists() or self.audit_path.exists() or self.saddle_path.exists():  # Protect previous case evidence from accidental overwrite.
            raise FileExistsError('Use a new native case output directory for each history')  # Preserve exact experiment identities across retries.
        self.nodes=len(static['coordinates'])  # Freeze the complete physical node population.
        self.initial=np.asarray(static['initial_state'],dtype=np.float64)  # Retain the actual preloaded displacement and velocity field.
        if self.initial.shape!=(self.nodes,12) or not np.isfinite(self.initial).all():  # Validate the declared twelve-channel native state.
            raise ValueError('Initial state must contain twelve finite channels at every node')  # Refuse an ambiguous response layout.
        self.file=h5py.File(self.partial,'x')  # Never overwrite a partial solver history from a previous run.
        self.audit=self.audit_path.open('x')  # Preserve every accepted independent dynamic balance.
        self.saddles=self.saddle_path.open('x')  # Preserve complete local-submodel forcing history.
        self.file.attrs.update(status='RUNNING',expected_frames=self.expected,written_frames=0,metadata_json=json.dumps(self.metadata,allow_nan=False),format_version=1)  # Publish truthful native stream state and provenance.
        for name,value in static.items():  # Store all complete native mesh, semantic, and initial arrays once.
            array=np.asarray(value)  # Preserve original integer identities and floating-point field precision.
            if array.dtype.kind not in 'biuf' or not np.isfinite(array).all():  # Require explicit finite numeric metadata.
                self.abort('Invalid static numerical field '+name)  # Preserve the actual rejection without manufacturing a completed artifact.
                raise ValueError('Invalid static numerical field '+name)  # Stop before accepting any response labels.
            self.file.create_dataset(name,data=array,compression='gzip',compression_opts=1,shuffle=True)  # Use only lossless native compression.
        for name,channels in [('targets',12),('controls',2),('applied_force_moment',6),('acceleration',6)]:  # Preserve every native output, exogenous input, and force audit component.
            self.file.create_dataset(name,shape=(0,self.nodes,channels),maxshape=(None,self.nodes,channels),dtype='f8',chunks=(1,min(self.nodes,2048),channels),compression='gzip',compression_opts=1,shuffle=True)  # Bound compression memory while retaining exact float64 values.
        self.file.create_dataset('times',shape=(0,),maxshape=(None,),dtype='f8',chunks=(256,))  # Preserve the complete accepted physical time grid.
        if 'cable_native_element_ids' in static:  # Preserve complete physical cable forces separately from motion-response training targets.
            count=len(static['cable_native_element_ids'])  # Freeze the complete native axial-member population.
            self.file.create_dataset('cable_axial_force_N',shape=(0,count),maxshape=(None,count),dtype='f8',chunks=(1,count),compression='gzip',compression_opts=1,shuffle=True)  # Store every native axial-force response without synthetic interpolation.
        self.file.flush()  # Expose a readable partial artifact before the first nonlinear evolution step.
        self._status('RUNNING')  # Publish the initial zero-frame progress receipt atomically.
    def _status(self,status,error=None):  # Keep status small regardless of physical history duration.
        value={'status':status,'expected_frames':self.expected,'written_frames':self.frames,'last_time_s':self.last_time,'dataset':str(self.path),'partial_dataset':str(self.partial),'step_audits':str(self.audit_path),'saddle_motion':str(self.saddle_path),'metadata':self.metadata}  # Record actual progress with exact evidence locations.
        if error is not None:  # Preserve an observed failure reason when present.
            value['error']=str(error)  # Keep the original solver or validation error legible.
        atomic_json(self.status_path,value)  # Publish only a complete valid status document.
    def append(self,time,targets,controls,applied_force_moment,acceleration,audit,saddles,cable_axial_force_N=None):  # Append one independently accepted physical time frame with optional declared full cable outputs.
        if self.closed or self.frames>=self.expected:  # Refuse writes after closure or beyond the requested physical history.
            raise ValueError('Native stream is closed or its requested frame count is exhausted')  # Preserve exact case duration.
        time=float(time)  # Retain physical time in double precision.
        if not np.isfinite(time) or (self.last_time is None and time!=0.) or (self.last_time is not None and time<=self.last_time):  # Enforce initial time and monotone causal ordering.
            raise ValueError('Native history times must start at zero and strictly increase')  # Prevent reordered or duplicated time slices.
        arrays={'targets':targets,'controls':controls,'applied_force_moment':applied_force_moment,'acceleration':acceleration}  # Name every complete physical frame array.
        if 'cable_axial_force_N' in self.file:  # Require actual force values whenever the static contract declares native axial-member IDs.
            arrays['cable_axial_force_N']=cable_axial_force_N  # Shape and finite checks below reject missing or incomplete force labels.
        for name,value in arrays.items():  # Validate all components before mutating any dataset.
            arrays[name]=np.asarray(value,dtype=np.float64)  # Preserve complete native double precision.
            if arrays[name].shape!=self.file[name].shape[1:] or not np.isfinite(arrays[name]).all():  # Require full matching finite node fields.
                raise ValueError('Invalid native time-frame field '+name)  # Never silently drop invalid nodes or output channels.
        if self.frames==0 and not np.array_equal(arrays['targets'],self.initial):  # Require a byte-equivalent numeric actual initial response.
            raise ValueError('First native target must equal the actual initial state')  # Block target leakage through an invented initial state.
        audit_line=json.dumps(audit,allow_nan=False)+'\n'  # Validate the complete independent force audit before array writes.
        saddle_line=json.dumps(saddles,allow_nan=False)+'\n'  # Validate actual interface records without lossy simplification.
        for name,array in arrays.items():  # Write all channels at every physical mesh node.
            self.file[name].resize(self.frames+1,axis=0)  # Extend exactly one accepted temporal frame.
            self.file[name][self.frames]=array  # Preserve exact native values under lossless compression.
        self.file['times'].resize(self.frames+1,axis=0)  # Extend the complete causal time grid.
        self.file['times'][self.frames]=time  # Record actual accepted physical time.
        self.audit.write(audit_line)  # Append the matching independent equilibrium evidence.
        self.saddles.write(saddle_line)  # Append the matching global-to-local physical interface.
        self.audit.flush()  # Keep accepted audit evidence visible during long solves.
        self.saddles.flush()  # Keep accepted local-boundary history visible during long solves.
        self.frames+=1  # Count the fully stored frame only after all outputs succeed.
        self.last_time=time  # Advance the causal history boundary after successful writes.
        self.file.attrs['written_frames']=self.frames  # Preserve exact committed progress inside the numerical artifact.
        self.file.flush()  # Flush each accepted frame so interruptions retain prior physical results.
        self._status('RUNNING')  # Update the bounded progress receipt atomically.
    def finish(self):  # Publish a final data artifact only after the full requested history exists.
        if self.closed or self.frames!=self.expected:  # Refuse partial time histories even when their individual frames converged.
            raise ValueError('Cannot complete an incomplete native history')  # Keep unfinished experiments ineligible for training.
        self.file.attrs['status']='COMPLETE'  # Mark completion only after checking exact requested frame count.
        self.file.flush()  # Flush the successful completion marker and all numerical fields.
        self.file.close()  # Release HDF5 before publishing its final path.
        for stream in (self.audit,self.saddles):  # Persist the complete corresponding variable-size histories.
            stream.flush()  # Flush Python buffers before durability confirmation.
            os.fsync(stream.fileno())  # Persist interface and force-audit records before data publication.
            stream.close()  # Release the completed evidence stream.
        self.closed=True  # Prevent any accidental subsequent mutation.
        os.replace(self.partial,self.path)  # Atomically publish a fully completed native numerical artifact.
        self._status('COMPLETE')  # Publish successful completion with exact accepted frame count.
        return self.path  # Return the actual final dataset location.
    def abort(self,error):  # Preserve failed native progress without exposing accepted training data.
        if not self.closed:  # Close only handles still owned by this writer.
            self.file.attrs['status']='FAILED'  # Record that this solver history did not complete its contract.
            self.file.attrs['failure_reason']=str(error)  # Preserve the exact observed numerical or execution failure.
            self.file.flush()  # Flush already accepted physical frames and the rejection marker.
            self.file.close()  # Release the partial numerical evidence.
            self.audit.close()  # Preserve accumulated physical-balance records.
            self.saddles.close()  # Preserve accumulated cable-cut records.
            self.closed=True  # Prevent writes after a rejected native experiment.
            self._status('FAILED',error)  # Publish truthful failure with exact retained progress.
