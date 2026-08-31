#!/usr/bin/env bash
# Extra convergence file: COARSEN=2. Does not overwrite the COARSEN=4 deck.
set -euo pipefail
cd "$(dirname "$0")/.."
export COARSEN=2 MODES=100
export CCX_JOB=true3d_ccx_c2
export MANIFEST_NAME=true3d_model_manifest_c2.json
export MODE_TABLE=true3d_mode_table_c2.csv
export BASIS_NAME=modal_basis_c2.npz
echo "COARSEN=2 extra file  job=$CCX_JOB"
test -f artifacts/s10_model.npz || python3 code/parse_s10.py
python3 code/build_true3d_ccx.py
python3 - <<'EOF'
import json
m = json.load(open('artifacts/true3d_model_manifest_c2.json'))
t = m['mass_ledger_t']
rel = abs(t['total'] - t['s10_reference']) / t['s10_reference']
print(f"C2 mass {t['total']:.3f} t rel {rel:.2e}")
assert rel < 0.01
print('G-P2 C2 PASS')
EOF
python3 code/audit_uy_bc.py
cd solver
time ccx -i true3d_ccx_c2 2>&1 | tee true3d_ccx_c2.stdout.txt
grep -q "Job finished" true3d_ccx_c2.stdout.txt
cd ..
python3 code/postprocess_modes.py
python3 - <<'EOF'
import csv, json
from pathlib import Path
def first_struct(path):
    rows = list(csv.DictReader(open(path)))
    out = []
    for r in rows:
        if r.get('residual_zero','False') in ('True','true','1'):
            continue
        out.append((r['family'], r.get('parity',''), float(r['f_hz'])))
    return out
c4 = first_struct('artifacts/true3d_mode_table.csv')
c2 = first_struct('artifacts/true3d_mode_table_c2.csv')
def first(fam, par, rows):
    for f,p,hz in rows:
        if f==fam and (not par or p==par):
            return hz
    return None
rep = {"coarsen4": {}, "coarsen2": {}, "T_shift": {}}
for fam, par, key in (("L","S","LS1"), ("V","A","VA1"), ("T","A","TA1"), ("T","S","TS1")):
    a, b = first(fam, par, c4), first(fam, par, c2)
    rep["coarsen4"][key] = a
    rep["coarsen2"][key] = b
    if a and b:
        rep["T_shift"][key] = (b-a)/a
(Path('artifacts')/'coarsen2_shift.json').write_text(json.dumps(rep, indent=2))
print(json.dumps(rep, indent=2))
EOF
echo "COARSEN=2 extra file done"
