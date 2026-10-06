#!/usr/bin/env python3
"""Plot native CFD outputs, with separate steady diagnostics and time histories."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from assess_results import assess, load_history

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='rod_urans', help='Select CFD cases by directory prefix')
    ap.add_argument('--geometry', default='geometry/proto2d_f170/geometry.json')
    ap.add_argument('--output', default='results')
    ap.add_argument('--reference', default='sources/table_3_1.csv')
    ap.add_argument('--reference-label', default='Report Table 3-1')
    args = ap.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'savefig.dpi': 180})
    ref = np.genfromtxt(ROOT / args.reference, delimiter=',', names=True)
    cases = []
    for p in (ROOT / 'cases').glob(args.prefix + '*'):
        if (p / 'case.json').exists():
            result = assess(p)
            if result:
                cases.append((p, result))
    cases.sort(key=lambda pair: pair[1]['alpha_deg'])
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
    comparisons = []
    for p, r in cases:
        target = ref[np.argmin(np.abs(ref['alpha_deg'] - r['alpha_deg']))]
        comparisons.append(dict(case=p.name, alpha_deg=r['alpha_deg'], solver_converged=r['solver_converged'],
                                coefficients_stable=r['coefficients_stable'], **{k: r[k] for k in ['CD', 'CL', 'CM']},
                                **{'report_' + k: float(target[k]) for k in ['CD', 'CL', 'CM']},
                                **{'error_' + k: r[k] - float(target[k]) for k in ['CD', 'CL', 'CM']}))
    for ax, key in zip(axs, ['CD', 'CL', 'CM']):
        ax.plot(ref['alpha_deg'], ref[key], 'k.-', label=args.reference_label, lw=1)
        if cases:
            ax.plot([r['alpha_deg'] for _, r in cases], [r[key] for _, r in cases], '--', color='#a86439', lw=.8)
        for p, r in cases:
            valid = r['solver_converged'] and r['coefficients_stable']
            ax.scatter([r['alpha_deg']], [r[key]], marker='o' if valid else 'x', color='#177b57' if valid else '#c35d29', s=45, zorder=5)
        ax.set(xlabel='Angle of attack (deg)', ylabel=key, xticks=np.arange(-12, 13, 4))
        ax.grid(alpha=.2)
    if any(r['solver_converged'] and r['coefficients_stable'] for _, r in cases):
        axs[0].plot([], [], 'o', color='#177b57', label='CFD: numerical checks passed')
    if any(not (r['solver_converged'] and r['coefficients_stable']) for _, r in cases):
        axs[0].plot([], [], 'x', color='#c35d29', label='CFD: numerical checks incomplete')
    axs[0].legend(fontsize=7, loc='best')
    axs[2].set_title('CFD moment about nominal section centre', fontsize=9)
    fig.suptitle('Prototype 2-D pilot comparison; not a validated wind-tunnel reproduction', fontsize=11)
    fig.tight_layout()
    for suffix in ['png', 'pdf']:
        fig.savefig(out / ('comparison.' + suffix))
    plt.close(fig)
    if comparisons:
        with (out / 'comparison.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(comparisons[0]),lineterminator='\n')
            writer.writeheader()
            writer.writerows(comparisons)
    for transient in [False, True]:
        selected = [(p, r) for p, r in cases if r['transient'] == transient]
        if not selected:
            continue
        fig, axs = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True)
        for p, r in selected:
            d = load_history(p)
            # Make post-startup oscillations legible; retain all original samples in CSV.
            cfg = json.loads((p / 'case.json').read_text())
            cutoff = min(.1 * cfg.get('physical_end_time', 0), .2 * d[-1, 0]) if transient else 0
            visible = d[d[:, 0] >= cutoff]
            for j, (ax, key) in enumerate(zip(axs, ['CD', 'CL', 'CM']), 1):
                ax.plot(visible[:, 0], visible[:, j], label=f"{r['alpha_deg']:+g} deg", lw=.7)
                ax.set_ylabel(key)
                ax.grid(alpha=.2)
            if transient and r.get('sampling_reached'):
                for ax in axs:
                    ax.axvline(r['sample_start'], color='0.6', lw=.6, ls=':')
            np.savetxt(out / (p.name + '_history.csv'), d, delimiter=',', header='time_s,CD,CL,CM' if transient else 'iteration,CD,CL,CM', comments='')
        axs[0].legend(ncol=3, fontsize=8)
        axs[-1].set_xlabel('Physical time (s)' if transient else 'SIMPLE iteration; not physical time')
        fig.suptitle('Native OpenFOAM histories; initial transient omitted from plot, complete samples in CSV' if transient else 'Native OpenFOAM coefficient histories', fontsize=10)
        fig.tight_layout()
        filename = 'time_histories' if transient else 'steady_histories'
        for suffix in ['png', 'pdf']:
            fig.savefig(out / (filename + '.' + suffix))
        plt.close(fig)
    cfg = json.loads((ROOT / args.geometry).read_text())
    fig, ax = plt.subplots(figsize=(12, 4.7))
    colors = {'carrier': '#3d4855', 'handrail': '#236c9d', 'side_equivalent': '#168d88', 'floor_combined_equivalent': '#be7731', 'floor_coarse_equivalent': '#168d88'}
    uniform_floor=cfg.get('fine_floor_open_area')==1
    if uniform_floor: colors['floor_combined_equivalent']='#168d88'
    for m in cfg['members']:
        if m.get('shape')=='rectangle':
            ax.add_patch(plt.Rectangle((m['x'],m['y']),m['width'],m['height'],color=colors.get(m['group'],'#a86439')))
        else:
            ax.add_patch(plt.Circle((m['x'], m['y']), m['diameter'] / 2, color=colors.get(m['group'], '#a86439')))
    for screen in cfg.get('screens', []):
        xy = np.array([screen['start'], screen['end']])
        ax.plot(xy[:, 0], xy[:, 1], color='#168d88' if len(screen['layers']) == 1 else '#be7731', lw=2)
    counts={g:sum(m['group']==g for m in cfg['members']) for g in ['carrier','handrail']}
    legend_items=[(f"{counts['carrier']} carrier ropes", '#3d4855'), (f"{counts['handrail']} handrail ropes", '#236c9d')]
    legend_items += [('Net equivalent', '#168d88')] if uniform_floor else [('Single mesh equivalent', '#168d88'), ('Double mesh equivalent', '#be7731')]
    if cfg.get('timber_sections'): legend_items.append(('Timber at C-C', '#a86439'))
    for label, color in legend_items:
        ax.plot([], [], '-', color=color, label=label)
    ax.plot(cfg['moment_origin'][0], cfg['moment_origin'][1], '+', color='#bd3429', ms=10, label='Moment reference')
    half_width=cfg['B_reference']/2
    top=max(cfg['screen_height'],max(y+d/2 for y,d in cfg['handrails']))
    ax.set(xlim=(-half_width-.2, half_width+.2), ylim=(-.12, top+.1), xlabel='Across catwalk (m)', ylabel='Height (m)', aspect='equal')
    fig.legend(*ax.get_legend_handles_labels(), fontsize=8, ncol=3, loc='upper center', bbox_to_anchor=(.5, .92))
    fig.suptitle(f"Drawing prototype, clear width = {cfg['B_geometry']:g} m; {cfg.get('section_name','net and rope section')}", y=.98, fontsize=11)
    fig.subplots_adjust(top=.76, bottom=.14, left=.07, right=.98)
    fig.savefig(out / 'geometry_2d.png')
    plt.close(fig)
    (out / 'selected_case_assessments.json').write_text(json.dumps([r for _, r in cases], indent=2))
    print('Saved figures and native coefficient histories for', len(cases), 'cases.')


if __name__ == '__main__':
    main()
