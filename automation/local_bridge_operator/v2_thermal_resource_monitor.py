import os # Resolve the actual mounted-proc PID namespace before recording resident memory.
from pathlib import Path # Read kernel evidence without modifying or signalling any solver.
def self_host_pid(): # The executor exposes host proc while os.getpid returns an inner namespace PID.
    return int(Path('/proc/self').resolve().name) # Use the kernel-resolved mounted proc identity rather than assuming PID namespaces match.
def snapshot(): # The kernel omits task children files here, so derive descendants from actual PPid fields.
    records={} # Preserve only minimal process identity and real resident memory.
    for entry in os.scandir('/proc'): # Read process identities without depending on the inaccessible children pseudo-file.
        if not entry.name.isdigit():continue # Ignore non-process kernel resources.
        try:lines=(Path(entry.path)/'status').read_text().splitlines();fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in lines if ':' in line};records[int(entry.name)]={'ppid':int(fields['PPid']),'rss':int(fields.get('VmRSS','0 kB').split()[0])*1024,'namespace':int(fields.get('NSpid',entry.name).split()[-1])} # PPid and RSS belong to the mounted proc namespace, while NSpid records the inner identity.
        except (FileNotFoundError,ProcessLookupError,PermissionError,KeyError):continue # Natural process exit during sampling is not a failed solver.
    return records # Keep the entire read-only snapshot consistent for one tree traversal.
def resolve_child(namespace_pid): # Resolve only this launcher's actual child, not another task sharing its inner PID.
    parent=self_host_pid();records=snapshot();matches=[pid for pid,value in records.items() if value['ppid']==parent and value['namespace']==int(namespace_pid)] # Bind both parent identity and the innermost namespace number.
    if len(matches)!=1:raise ProcessLookupError(f'Cannot uniquely resolve child{namespace_pid} under mounted-proc parent{parent}') # Never report a false zero RSS by confusing host and container PIDs.
    return matches[0] # Return the exact mounted-proc child used for all subsequent measurements.
def rss_tree(host_pid): # Sum the real resident memory of this mounted-proc process tree conservatively.
    records=snapshot();active=[host_pid];total=0;seen=set() # Traverse descendants from one consistent actual kernel snapshot.
    while active: # Include both the Python field producer and every genuine native child.
        pid=active.pop() # Visit one mounted-proc process identity.
        if pid in seen:continue # Guard against duplicate traversal without deleting legitimate child memory.
        seen.add(pid);total+=records.get(pid,{}).get('rss',0);active.extend(key for key,value in records.items() if value['ppid']==pid) # Shared resident pages may be counted twice, which is conservative for this budget.
    return total # A naturally exited tree contributes zero current RSS.
def own_rss_tree(): # Monitor this Python worker through native solve, parsing and archival.
    return rss_tree(self_host_pid()) # Resolve the namespace boundary explicitly for every root snapshot.
