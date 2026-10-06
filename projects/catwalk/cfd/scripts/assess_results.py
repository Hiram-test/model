#!/usr/bin/env python3
"""Read native OpenFOAM coefficients; separate numerical checks from agreement."""
import csv
import json
import re
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DRIFT_LIMIT = np.array([0.005, 0.001, 0.0005])


def read_coeff(path):
    return np.loadtxt(path, comments='#', ndmin=2)


def load_history(case):
    """Merge restarts chronologically; the later restart wins at repeated times."""
    rows = {}
    folder = case / 'postProcessing/coeffsB'
    # OpenFOAM 1912 creates coefficient_0.dat etc. if the output already exists.
    # Select the newest complete invocation in each time directory, not stale files.
    latest = {}
    for candidate in folder.glob('*/coefficient*.dat'):
        old = latest.get(candidate.parent.name)
        if old is None or candidate.stat().st_mtime_ns > old.stat().st_mtime_ns:
            latest[candidate.parent.name] = candidate
    for fb in sorted(latest.values(), key=lambda p: float(p.parent.name)):
        fh = case / 'postProcessing/coeffsH' / fb.parent.name / fb.name
        if not fh.exists():
            continue
        b, h = read_coeff(fb), read_coeff(fh)
        bm = {r[0]: r for r in b}
        hm = {r[0]: r for r in h}
        for t in bm.keys() & hm.keys():
            rows[t] = [t, hm[t][1], bm[t][3], bm[t][5]]
    return np.array([rows[t] for t in sorted(rows)], dtype=float).reshape((-1, 4))


def time_window(data, start, end):
    """Include interpolated time endpoints, for time-weighted statistics only."""
    start, end = max(start, data[0, 0]), min(end, data[-1, 0])
    if end <= start:
        return np.empty((0, 4))
    t = np.r_[start, data[(data[:, 0] > start) & (data[:, 0] < end), 0], end]
    return np.column_stack([t] + [np.interp(t, data[:, 0], data[:, j]) for j in range(1, 4)])


def time_mean(data):
    integrate = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz
    return integrate(data[:, 1:], data[:, 0], axis=0) / (data[-1, 0] - data[0, 0])


def assess(case):
    cfg = json.loads((case / 'case.json').read_text())
    data = load_history(case)
    if not len(data):
        return None
    transient = cfg.get('transient', False)
    logname = 'log.pimpleFoam' if transient else 'log.simpleFoam'
    log = (case / logname).read_text(errors='replace') if (case / logname).exists() else ''
    ended = bool(re.search(r'^End\s*$', log, re.M))
    times = re.findall(r'^Time = ([\deE+.-]+)', log, re.M)
    reached = float(times[-1]) if times else float(data[-1, 0])
    residual, final_residual = {}, {}
    for name, initial, final in re.findall(r'Solving for (\w+), Initial residual = ([\deE+.-]+), Final residual = ([\deE+.-]+)', log):
        residual[name], final_residual[name] = float(initial), float(final)
    target = cfg.get('physical_end_time', 0) if transient else cfg.get('iterations_requested', 0)
    sampling_reached = not transient or data[-1, 0] > cfg['average_start']
    if transient and sampling_reached:
        tail = time_window(data, cfg['average_start'], data[-1, 0])
    else:
        tail = data[-200:]
    n = len(tail)
    mean = time_mean(tail) if transient and n > 1 else tail[:, 1:].mean(axis=0)
    if transient and n > 1:
        mid = (tail[0, 0] + tail[-1, 0]) / 2
        drift = np.abs(time_mean(time_window(tail, tail[0, 0], mid)) - time_mean(time_window(tail, mid, tail[-1, 0])))
    else:
        half = n // 2
        drift = np.abs(tail[:half, 1:].mean(axis=0) - tail[half:, 1:].mean(axis=0)) if half else np.full(3, np.inf)
    spread = np.ptp(tail[:, 1:], axis=0)
    solver_converged = 'SIMPLE solution converged' in log
    stable = bool(n >= 200 and np.all(drift < DRIFT_LIMIT) and np.all(spread < [0.02, 0.004, 0.002]))
    extra = {}
    if transient:
        cos = [float(x) for x in re.findall(r'Courant Number mean: .*? max: ([\deE+.-]+)', log)]
        maximum_co = max(cos[1:] or cos) if cos else None
        finished_target = reached >= target * (1 - 1e-6)
        linear_ok = bool(final_residual) and all(v <= 1.1e-6 for v in final_residual.values())
        solver_converged = bool(ended and finished_target and linear_ok and maximum_co is not None and maximum_co < 1.05 * cfg.get('maxCo', 2))
        duration = float(tail[-1, 0] - tail[0, 0]) if n > 1 and sampling_reached else 0
        duration_BU = duration * cfg['speed'] / cfg['B_reference']
        blocks = []
        if duration > 0:
            edges = np.linspace(tail[0, 0], tail[-1, 0], 9)
            blocks = [time_mean(time_window(tail, lo, hi)).tolist() for lo, hi in zip(edges[:-1], edges[1:])]
        stable = bool(sampling_reached and n >= 200 and duration_BU >= 20 and np.all(drift < DRIFT_LIMIT))
        extra = dict(sampling_reached=bool(sampling_reached), sample_start=float(tail[0, 0]) if sampling_reached else None,
                     sample_duration_s=duration, sample_duration_BU=duration_BU, block_means=blocks,
                     max_recorded_Co=maximum_co, final_linear_residual=final_residual,
                     statistics_warning='Time-step/grid sensitivity and correlated-sample uncertainty remain separate checks.')
    values = {key: float(value) for key, value in zip(['CD', 'CL', 'CM'], mean)}
    values.update({'last_' + key: float(value) for key, value in zip(['CD', 'CL', 'CM'], data[-1, 1:])})
    return dict(case=case.name, model_status=cfg.get('model_status', 'CURRENT'), alpha_deg=cfg['alpha_deg'],
                speed=cfg['speed'], dimension=cfg.get('dimension', 2), iteration=reached, **values,
                ended=ended, stopped_early=bool(ended and reached < target * (1 - 1e-6) and not solver_converged),
                solver_converged=solver_converged, coefficients_stable=stable, drift=drift.tolist(),
                spread=spread.tolist(), residual=residual, transient=transient, **extra,
                interpretation=('Physical-time-weighted mean; see sampling, mesh and time-step checks' if transient and sampling_reached else
                                'Startup diagnostic only; specified sampling window not reached' if transient else
                                'Steady iteration window; not a physical-time average'))


def main():
    rows = []
    for case in sorted((ROOT / 'cases').iterdir()):
        if (case / 'case.json').exists():
            try:
                r = assess(case)
            except Exception as exc:
                print(case.name, type(exc).__name__, str(exc))
                continue
            if r:
                rows.append(r)
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/status.json').write_text(json.dumps(rows, indent=2))
    fields = ['case', 'model_status', 'dimension', 'alpha_deg', 'speed', 'iteration', 'CD', 'CL', 'CM', 'ended', 'solver_converged', 'coefficients_stable']
    with (ROOT / 'results/coefficients.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore',lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        if r['case'].startswith('porous'):
            print({k: r[k] for k in fields})


if __name__ == '__main__':
    main()
