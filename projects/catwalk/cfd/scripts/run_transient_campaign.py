#!/usr/bin/env python3
"""Run native pimpleFoam cases from saved warm-up fields, with input provenance."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from assess_results import assess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sources', nargs='+', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--end', type=float, default=12)
    ap.add_argument('--average-start', type=float, default=3)
    ap.add_argument('--max-dt', type=float, default=.001)
    ap.add_argument('--max-co', type=float, default=5)
    ap.add_argument('--outer', type=int, default=2)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--cold-start', action='store_true')
    args = ap.parse_args()
    if not 0 <= args.average_start < args.end:
        ap.error('Require 0 <= average-start < end')
    root = Path(__file__).resolve().parents[1]

    def one(source):
        source = Path(source).resolve()
        cfg = json.loads((source / 'case.json').read_text())
        angle = cfg['alpha_deg']
        sign = 'm' if angle < 0 else 'p'
        name = f'{args.prefix}_{sign}{abs(angle):05.1f}'.replace('.', '_')
        case = root / 'cases' / name
        prep = [sys.executable, str(root / 'scripts/prepare_transient.py'), '--source', str(source), '--out', str(case),
                '--end', str(args.end), '--average-start', str(args.average_start), '--max-dt', str(args.max_dt),
                '--max-co', str(args.max_co), '--outer', str(args.outer)]
        if args.cold_start:
            prep.append('--cold-start')
        subprocess.run(prep, check=True)
        hashes = {str(p.relative_to(case)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for d in ['0', 'constant', 'system'] for p in (case / d).rglob('*') if p.is_file()}
        record = dict(preparation_command=prep, command=['pimpleFoam', '-case', str(case)],
                      started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), input_sha256=hashes)
        (case / 'execution.json').write_text(json.dumps(record, indent=2))
        with (case / 'log.pimpleFoam').open('w') as log:
            result = subprocess.run(record['command'], stdout=log, stderr=subprocess.STDOUT)
        record.update(returncode=result.returncode, finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      assessment=assess(case))
        (case / 'execution.json').write_text(json.dumps(record, indent=2))
        print(name, result.returncode, flush=True)
        return record

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(one, args.sources))
    (root / 'results' / f'{args.prefix}_campaign.json').write_text(json.dumps(records, indent=2))
    if any(r['returncode'] != 0 for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
