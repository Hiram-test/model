#!/usr/bin/env python3
"""Resume a saved transient case with native OpenFOAM MPI and reconstruct it."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from assess_results import assess

ap = argparse.ArgumentParser()
ap.add_argument('--case', required=True)
ap.add_argument('--ranks', type=int, default=3)
a = ap.parse_args()
case = Path(a.case).resolve()
if a.ranks < 2:
    raise ValueError('Use at least two MPI ranks')
log = case / 'log.pimpleFoam'
footer = log.read_text().rstrip()
if not (footer.endswith('End') or footer.endswith('Finalising parallel run')):
    raise RuntimeError('First stop the active serial run with stopAt writeNow and wait for End')
cfg = json.loads((case / 'case.json').read_text())
if not cfg.get('transient'):
    raise RuntimeError('This helper is for saved pimpleFoam transient runs')
record_path = case / 'parallel_resume.json'
if record_path.exists():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    record_path.rename(case / f'parallel_resume.{stamp}.json')
control = case / 'system/controlDict'
text = control.read_text().replace('stopAt writeNow', 'stopAt endTime')
text = re.sub(r'startFrom\s+[^;]+;', 'startFrom latestTime;', text)
control.write_text(text)
dict_path = case / 'system/decomposeParDict'
from prepare_case import header
# Debian's OpenFOAM package contains a dummy scotchDecomp library.
# Use the bundled hierarchical decomposition, without optional libraries.
dict_path.write_text(header('decomposeParDict') + f'numberOfSubdomains {a.ranks};\nmethod hierarchical;\nhierarchicalCoeffs {{ n ({a.ranks} 1 1); delta 0.001; order xyz; }}\n')
record = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), ranks=a.ranks,
              control_sha256=hashlib.sha256(control.read_bytes()).hexdigest(), commands=[])
record_path.write_text(json.dumps(record, indent=2))

def run(command, output, mode='w'):
    record['commands'].append(command)
    record_path.write_text(json.dumps(record, indent=2))
    with output.open(mode) as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)

run(['decomposePar', '-case', str(case), '-latestTime', '-force'], case / 'log.decomposePar')
# Some container runtimes lack process_vm_readv (CMA); use shared-memory copies.
run(['mpirun', '--mca', 'btl_vader_single_copy_mechanism', 'none', '-np', str(a.ranks),
     'pimpleFoam', '-case', str(case), '-parallel'], log, 'a')
run(['reconstructPar', '-case', str(case), '-latestTime'], case / 'log.reconstructPar')
record.update(finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), returncode=0, assessment=assess(case))
record_path.write_text(json.dumps(record, indent=2))
print(json.dumps(dict(case=case.name, ranks=a.ranks, completed=True, assessment=record['assessment'])), flush=True)
