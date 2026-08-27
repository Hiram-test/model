#!/usr/bin/env python3
"""C20 pairing independent verification using probe displacement signs.
Does NOT trust existing pairing. Classifies modes 1-20 from probe data only."""
import csv, os, sys

solver = r'D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs\C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z\solver'
qa = os.path.join(os.path.dirname(solver), 'qa')

# Probe layout (from c20_probe_nodes.txt):
# P+ (catwalk +Y): K=1..5 at XS1..XS5 (north, Q1, mid, Q3, south)
# P- (catwalk -Y): K=6..10 at same XS1..XS5
# K=11: GATE_TOPPOST_NODE
# XS2=Q1, XS3=midspan, XS4=Q3
# Columns in c20_mode_probes.csv:
# mode, freq, probe_k, node_id, UX, UY, UZ, ROTX, ROTY, ROTZ

probes = {}  # (mode, k) -> dict
with open(os.path.join(solver, 'c20_mode_probes.csv'), 'r') as f:
    for line in f:
        parts = line.split(',')
        if len(parts) < 10:
            continue
        try:
            mode = int(float(parts[0]))
            freq = float(parts[1])
            k = int(float(parts[2]))
            nid = int(float(parts[3]))
            ux = float(parts[4]); uy = float(parts[5]); uz = float(parts[6])
            rx = float(parts[7]); ry = float(parts[8]); rz = float(parts[9])
        except (ValueError, IndexError):
            continue
        probes[(mode, k)] = dict(freq=freq, nid=nid, ux=ux, uy=uy, uz=uz, rx=rx, ry=ry, rz=rz)

def classify_mode(mode):
    """Classify a single mode from probe signs."""
    p = {k: probes.get((mode, k)) for k in range(1, 12)}
    if not all(p[k] is not None for k in range(1, 12)):
        return None

    freq = p[1]['freq']

    # Max amplitudes across all cable probes (K=1..10) for each DOF
    max_uy = max(abs(p[k]['uy']) for k in range(1, 11))
    max_uz = max(abs(p[k]['uz']) for k in range(1, 11))
    max_ux = max(abs(p[k]['ux']) for k in range(1, 11))
    max_rz = max(abs(p[k]['rz']) for k in range(1, 11))
    max_rx = max(abs(p[k]['rx']) for k in range(1, 11))
    max_ry = max(abs(p[k]['ry']) for k in range(1, 11))

    # Gate node displacement
    gate_uy = abs(p[11]['uy']); gate_uz = abs(p[11]['uz'])
    gate_rz = abs(p[11]['rz']); gate_rx = abs(p[11]['rx'])
    gate_max = max(gate_uy, gate_uz, gate_rz, gate_rx)

    # Cable max
    cable_max = max(max_uy, max_uz, max_rz)

    # Dominant direction
    dofs = {'UY(lat)': max_uy, 'UZ(vert)': max_uz, 'ROTZ(tors)': max_rz, 'UX(long)': max_ux}
    dominant = max(dofs, key=dofs.get)
    dominant_val = dofs[dominant]

    # Symmetry: compare Q1 (K=2,7) vs Q3 (K=4,9) for dominant DOF
    # For UZ (vertical): P+ Q1=K2, P+ Q3=K4; P- Q1=K7, P- Q3=K9
    # For UY (lateral): same probes
    def get_dof(pd, dof):
        return pd[dof]

    sym_signs = []
    for k_q1, k_q3 in [(2,4), (7,9)]:  # P+ and P-
        v_q1 = abs(p[k_q1][dominant.split('(')[0].lower()]) if dominant != 'ROTZ(tors)' else abs(p[k_q1]['rz'])
        v_q3 = abs(p[k_q3][dominant.split('(')[0].lower()]) if dominant != 'ROTZ(tors)' else abs(p[k_q3]['rz'])
        s_q1 = p[k_q1][dominant.split('(')[0].lower()] if dominant != 'ROTZ(tors)' else p[k_q1]['rz']
        s_q3 = p[k_q3][dominant.split('(')[0].lower()] if dominant != 'ROTZ(tors)' else p[k_q3]['rz']
        if v_q1 > 1e-12 and v_q3 > 1e-12:
            if s_q1 * s_q3 > 0:
                sym_signs.append('S')  # same sign = symmetric
            else:
                sym_signs.append('A')  # opposite = antisymmetric
        elif v_q1 > 1e-12 or v_q3 > 1e-12:
            sym_signs.append('?')  # one side zero

    symmetry = sym_signs[0] if sym_signs else '?'
    if len(sym_signs) > 1 and sym_signs[0] != sym_signs[1]:
        symmetry = sym_signs[0] + '/' + sym_signs[1]

    # Midspan (K=3,8) displacement for dominant DOF
    dkey = dominant.split('(')[0].lower() if dominant != 'ROTZ(tors)' else 'rz'
    mid_vals = [abs(p[3][dkey]), abs(p[8][dkey])]
    mid_max = max(mid_vals)
    mid_near_zero = mid_max < 0.05 * dominant_val if dominant_val > 0 else True

    # Two catwalks in-phase or out-of-phase at same X (Q1: K2 vs K7)
    cat_phase = []
    for k_p, k_m in [(2,7), (3,8), (4,9)]:
        vp = abs(p[k_p][dkey]); vm = abs(p[k_m][dkey])
        sp = p[k_p][dkey]; sm = p[k_m][dkey]
        if vp > 1e-12 and vm > 1e-12:
            if sp * sm > 0:
                cat_phase.append('in')
            else:
                cat_phase.append('out')
        elif vp > 1e-10 or vm > 1e-10:
            cat_phase.append('?')
    phase = cat_phase[0] if cat_phase else '?'
    if len(set(cat_phase)) > 1:
        phase = '/'.join(cat_phase)

    # Global vs local
    if cable_max < 1e-12:
        global_local = 'LOCAL(no cable motion)'
    elif gate_max > 10 * cable_max and cable_max < 1e-6:
        global_local = 'LOCAL(gate only)'
    elif gate_max > 5 * cable_max:
        global_local = 'GATE_DOMINATED'
    else:
        global_local = 'GLOBAL'

    # Torsion check: if P+ and P- have opposite UZ at same X = torsion
    torsion_evidence = False
    for k_p, k_m in [(2,7), (4,9)]:
        if abs(p[k_p]['uz']) > 1e-10 and abs(p[k_m]['uz']) > 1e-10:
            if p[k_p]['uz'] * p[k_m]['uz'] < 0:
                torsion_evidence = True

    return dict(
        mode=mode, freq=freq,
        max_uy=max_uy, max_uz=max_uz, max_rz=max_rz, max_ux=max_ux,
        dominant=dominant, symmetry=symmetry, mid_near_zero=mid_near_zero,
        phase=phase, global_local=global_local,
        torsion_evidence=torsion_evidence,
        gate_max=gate_max, cable_max=cable_max,
        p_plus_q1_uz=p[2]['uz'], p_plus_q3_uz=p[4]['uz'],
        p_minus_q1_uz=p[7]['uz'], p_minus_q3_uz=p[9]['uz'],
        p_plus_mid_uy=p[3]['uy'], p_plus_mid_uz=p[3]['uz'],
    )

# Read existing pairing
existing = {}
pair_csv = os.path.join(qa, 'c20_table41_pairing.csv')
if os.path.exists(pair_csv):
    with open(pair_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                existing[int(row.get('fem_mode', row.get('FEM阶', 0)))] = row
            except (ValueError, KeyError):
                pass

# Classify modes 1-20
results = []
for m in range(1, 21):
    r = classify_mode(m)
    if r:
        results.append(r)

# Print classification table
print("=" * 120)
print("C20 INDEPENDENT MODE CLASSIFICATION FROM PROBE SIGNS (modes 1-20)")
print("=" * 120)
print(f"{'阶':>3} {'Hz':>10} {'主导':>10} {'对称':>5} {'跨中≈0':>6} {'猫道相位':>8} {'全局/局部':>16} {'扭转证据':>8} {'门架幅值':>12} {'索幅值':>12}")
print("-" * 120)
for r in results:
    print(f"{r['mode']:>3} {r['freq']:>10.5f} {r['dominant']:>10} {r['symmetry']:>5} {str(r['mid_near_zero']):>6} {r['phase']:>8} {r['global_local']:>16} {str(r['torsion_evidence']):>8} {r['gate_max']:>12.2e} {r['cable_max']:>12.2e}")

print()
print("=" * 120)
print("DETAILED PROBE SIGN DATA (UZ at Q1/Q3 for symmetry, UY for lateral, ROTZ for torsion)")
print("=" * 120)
print(f"{'阶':>3} {'Hz':>10} | {'P+Q1_UZ':>12} {'P+Q3_UZ':>12} {'P-Q1_UZ':>12} {'P-Q3_UZ':>12} | {'P+Q1_UY':>12} {'P+Q3_UY':>12} | {'P+Q1_RZ':>12} {'P+Q3_RZ':>12} | {'P+mid_UZ':>12} {'P-mid_UZ':>12}")
print("-" * 120)
for r in results:
    print(f"{r['mode']:>3} {r['freq']:>10.5f} | {r['p_plus_q1_uz']:>12.4e} {r['p_plus_q3_uz']:>12.4e} {r['p_minus_q1_uz']:>12.4e} {r['p_minus_q3_uz']:>12.4e} | {r['max_uy']:>12.4e} {r['max_uy']:>12.4e} | {'':>12} {'':>12} | {r['p_plus_mid_uz']:>12.4e} {0:>12.4e}")

# Key checks
print()
print("=" * 120)
print("KEY VERIFICATION CHECKS")
print("=" * 120)

for r in results:
    m = r['mode']
    if m in [3, 4]:
        print(f"\n--- 阶{m} ({r['freq']:.5f} Hz) ---")
        print(f"  主导方向: {r['dominant']}")
        print(f"  对称性: {r['symmetry']} (mid_near_zero={r['mid_near_zero']})")
        print(f"  猫道相位: {r['phase']}")
        print(f"  全局/局部: {r['global_local']}")
        print(f"  索最大位移: {r['cable_max']:.4e}, 门架最大位移: {r['gate_max']:.4e}")
        print(f"  扭转证据(P+和P-竖向反相): {r['torsion_evidence']}")
        if r['cable_max'] > 0.001:
            print(f"  >>> 索测点有显著位移({r['cable_max']:.4e})，是全桥模态")
        else:
            print(f"  >>> 索测点位移极小({r['cable_max']:.4e})，可能是门架局部模态")

    if m == 5:
        print(f"\n--- 阶{m} ({r['freq']:.5f} Hz) ---")
        print(f"  主导方向: {r['dominant']} (max_uy={r['max_uy']:.4e}, max_uz={r['max_uz']:.4e}, max_rz={r['max_rz']:.4e})")
        print(f"  对称性: {r['symmetry']}")
        print(f"  猫道相位: {r['phase']}")
        print(f"  扭转证据: {r['torsion_evidence']}")

    if m == 6:
        print(f"\n--- 阶{m} ({r['freq']:.5f} Hz) ---")
        print(f"  主导方向: {r['dominant']} (max_uy={r['max_uy']:.4e}, max_uz={r['max_uz']:.4e}, max_rz={r['max_rz']:.4e})")
        print(f"  对称性: {r['symmetry']} (Q1 vs Q3 sign)")
        print(f"  猫道相位: {r['phase']}")
        print(f"  扭转证据(P+和P-竖向反相): {r['torsion_evidence']}")
        print(f"  P+Q1_UZ={r['p_plus_q1_uz']:.4e}, P+Q3_UZ={r['p_plus_q3_uz']:.4e}")
        print(f"  P-Q1_UZ={r['p_minus_q1_uz']:.4e}, P-Q3_UZ={r['p_minus_q3_uz']:.4e}")
        if r['symmetry'] == 'S':
            print(f"  >>> Q1和Q3同号 = 正对称扭转(TS)")
        elif r['symmetry'] == 'A':
            print(f"  >>> Q1和Q3异号 = 反对称扭转(TA)")
