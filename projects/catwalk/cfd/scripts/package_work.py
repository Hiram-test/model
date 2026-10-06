#!/usr/bin/env python3
"""Export committed source/history and selected completed native OpenFOAM cases."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', nargs='*', default=[])
    ap.add_argument('--label', default='checkpoint')
    ap.add_argument('--diagnostics',action='store_true',help='Archive other saved cases and geometry separately, with no validation claim')
    ap.add_argument('--sources',action='store_true',help='Include user-supplied and upstream repository evidence; not third-party papers')
    ap.add_argument('--allow-user-stopped', action='store_true', help='Archive gracefully ended partial runs only when user_stop.json records the request')
    args = ap.parse_args()
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    code = dist / f'catwalk-cfd-code-{args.label}.zip'
    bundle = dist / 'catwalk-cfd-history.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), '--all'], cwd=ROOT, check=True)
    subprocess.run(['git', 'archive', '--format=zip', '--prefix=catwalk-cfd/', '-o', str(code), commit], cwd=ROOT, check=True)
    with zipfile.ZipFile(code, 'a', compression=zipfile.ZIP_DEFLATED) as z:
        z.write(bundle, 'catwalk-cfd/catwalk-cfd-history.bundle')
        z.writestr('catwalk-cfd/CODE_VERSION.json', json.dumps(dict(commit=commit, status='Source snapshot; consult case results for numerical validity'), indent=2))
    exported = [code]
    if args.cases:
        selected = []
        run_status = {}
        for name in args.cases:
            case = ROOT / 'cases' / name
            cfg = json.loads((case / 'case.json').read_text())
            log = case / ('log.pimpleFoam' if cfg.get('transient') else 'log.simpleFoam')
            content=log.read_text()
            times_logged=re.findall(r'^Time = ([\deE+.-]+)',content,re.M)
            target=cfg.get('physical_end_time',0)
            ended = bool(re.search(r'^End\s*$', content, re.M))
            reached = float(times_logged[-1]) if times_logged else None
            partial = reached is not None and reached < target*(1-1e-6)
            stop_file = case / 'user_stop.json'
            stop = json.loads(stop_file.read_text()) if stop_file.exists() else None
            if not ended or reached is None or (partial and not (args.allow_user_stopped and stop)):
                raise RuntimeError(f'Refusing to package unfinished native run: {name}')
            run_status[name] = dict(native_ended=ended, actual_end_time=reached, requested_end_time=target,
                                    stopped_early=partial, user_stop=stop)
            for folder in ['0', 'constant', 'system', 'postProcessing']:
                selected.extend(p for p in (case / folder).rglob('*') if p.is_file())
            selected.extend(p for p in case.iterdir() if p.is_file())
            times = []
            for p in case.iterdir():
                if p.is_dir():
                    try: times.append((float(p.name), p))
                    except ValueError: pass
            if times:
                selected.extend(p for p in max(times)[1].rglob('*') if p.is_file())
        for folder in ['zhangjinggao','user_drawing','user_timber','porous_diagnostic']:
            selected.extend(p for p in (ROOT/'results'/folder).rglob('*') if p.is_file())
        selected.extend(p for p in (ROOT/'results').glob('*.json') if p.name.endswith('_campaign.json') or p.name=='portable_code_check.json')
        for name in ['proto2d_f170', 'user2d_f170','user2d_timber_f170_v2','porous2d_f100', 'porous2d_f160', 'qa_porous_duct','prototype_9m']:
            selected.extend(p for p in (ROOT / 'geometry' / name).glob('*') if p.is_file() and (p.suffix in ['.json','.msh','.brep','.step'] or p.name.startswith('log.')))
        selected = sorted(set(selected))
        manifest = {str(p.relative_to(ROOT)): digest(p) for p in selected}
        result = dist / f'catwalk-cfd-results-{args.label}.zip'
        with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in selected:
                z.write(p, 'catwalk-cfd/' + str(p.relative_to(ROOT)))
            z.writestr('catwalk-cfd/RESULTS_MANIFEST.json', json.dumps(dict(source_commit=commit, cases=args.cases, run_status=run_status, sha256=manifest), indent=2))
        exported.append(result)
    if args.diagnostics:
        # Retain unsuccessful/superseded work as evidence, outside the accepted pilot set.
        # No VTK duplication, MPI processor copies, cache or upstream PDF/archive is required.
        selected=[]
        for base in ['cases','geometry']:
            for folder in (ROOT/base).iterdir():
                if folder.name in args.cases: continue
                if not folder.is_dir(): continue
                for p in folder.rglob('*'):
                    if not p.is_file(): continue
                    rel=p.relative_to(folder)
                    if any(part=='VTK' or part=='__pycache__' or part.startswith('processor') for part in rel.parts): continue
                    selected.append(p)
        manifest={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(selected))}
        diagnostic=dist/f'catwalk-cfd-diagnostics-{args.label}.zip'
        with zipfile.ZipFile(diagnostic,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in manifest: z.write(ROOT/name,'catwalk-cfd/'+name)
            z.writestr('catwalk-cfd/DIAGNOSTICS_MANIFEST.json',json.dumps(dict(
                source_commit=commit,status='Historical, failed, stopped and superseded experiments; not validated results',
                three_d_flow_solved=False,excluded_primary_cases=args.cases,sha256=manifest),indent=2))
        exported.append(diagnostic)
    if args.sources:
        names=['wind_report_user.pdf','wind_report.txt','catwalk_drawings_1225.pdf','catwalk_drawings_1225.txt',
               'full_line_beam4_crossbeam_mesh_xlong.inp','catwalk_structural_review.pdf','catwalk_structural_review.txt',
               'table_3_1.csv','table_5_8_user.csv','source_audit.json','README.md']
        files=[ROOT/'sources'/name for name in names]
        if not all(p.is_file() for p in files): raise FileNotFoundError('Some source evidence files are not present; see sources/README.md')
        archive=dist/f'catwalk-cfd-source-evidence-{args.label}.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in files: z.write(p,'catwalk-cfd/sources/'+p.name)
            z.writestr('catwalk-cfd/SOURCE_EVIDENCE_MANIFEST.json',json.dumps(dict(
                source_commit=commit,
                provenance='User report PDF and public Hiram-test/model drawing/INP evidence. Second drawing is a conversation image; its transcription is in code/CSV.',
                sha256={p.name:digest(p) for p in files}),indent=2))
        exported.append(archive)
    records = [dict(file=p.name, bytes=p.stat().st_size, sha256=digest(p)) for p in exported]
    (dist / f'packages-{args.label}.json').write_text(json.dumps(records, indent=2))
    for record in records:
        print(json.dumps(record))


if __name__ == '__main__':
    main()
