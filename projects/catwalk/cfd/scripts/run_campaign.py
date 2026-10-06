#!/usr/bin/env python3
"""Run under sourced OpenFOAM environment; numerical work stays in simpleFoam."""
import argparse,concurrent.futures,datetime,hashlib,json,subprocess
from pathlib import Path
from prepare_case import create_case
from assess_results import assess
from geometry_gate import require_geometry_ready

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--mesh',required=True)
    ap.add_argument('--angles',default='-12,-6,0,6,12')
    ap.add_argument('--speed',type=float,default=13.8)
    ap.add_argument('--iterations',type=int,default=1500)
    ap.add_argument('--workers',type=int,default=1)
    ap.add_argument('--prefix',required=True)
    args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    mesh=Path(args.mesh).resolve()
    require_geometry_ready(mesh)
    qa=mesh/'log.checkMesh'
    if not qa.exists() or 'Mesh OK.' not in qa.read_text():raise RuntimeError('A passing checkMesh log is required')
    angles=[float(x) for x in args.angles.split(',')]
    def one(angle):
        sign='m' if angle<0 else 'p';name=f'{args.prefix}_{sign}{abs(angle):05.1f}'.replace('.','_')
        case=root/'cases'/name
        if case.exists():raise RuntimeError(f'Refusing to overwrite {case}')
        create_case(case,mesh,angle,args.speed,args.iterations)
        hashes={str(p.relative_to(case)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['0','constant','system'] for p in (case/d).rglob('*') if p.is_file()}
        record={'command':['simpleFoam','-case',str(case)],'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_sha256':hashes}
        (case/'execution.json').write_text(json.dumps(record,indent=2))
        with (case/'log.simpleFoam').open('w') as f:
            result=subprocess.run(record['command'],stdout=f,stderr=subprocess.STDOUT)
        record.update(returncode=result.returncode,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),assessment=assess(case))
        (case/'execution.json').write_text(json.dumps(record,indent=2))
        print(name,result.returncode,flush=True)
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        records=list(pool.map(one,angles))
    (root/'results'/f'{args.prefix}_campaign.json').write_text(json.dumps(records,indent=2))
    if any(r['returncode']!=0 for r in records):raise SystemExit(1)

if __name__=='__main__':main()
