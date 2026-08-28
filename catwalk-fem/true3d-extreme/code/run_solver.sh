#!/usr/bin/env bash
# ============================================================================
# 真实三维猫道 ccx 求解链 runbook（S1–S4 段）。计算由外部执行者运行本脚本。
# 前置：git 仓库在 /workspace，origin/main 含 ultra_runs S10 源；ccx 2.21；
#       python3 + numpy scipy pandas matplotlib。
# 预计资源：4 核 15 GB 内存足够（模型 ~7k B31 单元，膨胀后 ~10^5 节点）。
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."          # -> catwalk-fem/true3d-extreme
ROOT=$(git rev-parse --show-toplevel)

# --- S1: 导出 S10 冻结源（哈希已在 U00 封板） --------------------------------
mkdir -p /tmp/s10
P=ultra_runs/S10_SECTION_SHEAR_20260716T050342389124Z/solver
git -C "$ROOT" show origin/main:$P/full_line_beam4_crossbeam_mesh_xlong.inp > /tmp/s10/mesh.inp
for f in apply_finite_gates_and_passages_v2.inp apply_dynamic_mass21_spatialized_v2.inp \
         apply_mct_authoritative_initial_state_link180.inp apply_mct_constraints_xlong.inp \
         apply_mct_downpull_equivalent_xlong.inp s10_section_shear_main.inp \
         convert_crossbeams_beam4_to_beam188.inp apply_authoritative_mct_deadload_v1.inp \
         apply_authoritative_mct_gravity_v1.inp apply_modal_roty_stabilization_xlong.inp; do
  git -C "$ROOT" show origin/main:$P/$f > /tmp/s10/$f
done
git -C "$ROOT" show origin/main:mass21_spatialized_v2_nodes.csv > /tmp/s10/mass21_nodes.csv

# --- S2: 解析（产出 artifacts/s10_model.npz；门 G-P1: 44 索线 / 963.811 t 恒等） ---
python3 code/parse_s10.py
python3 - <<'EOF'
import json
r = json.load(open('artifacts/s10_parse_report.json'))
assert len(r['lines']) == 44, r['counts']
assert abs(r['sums']['F_over_g_t'] - r['sums']['mass21_total_t']) < 1e-3
print('G-P1 PASS: 44 lines, F/g == mass21 ==', r['sums']['mass21_total_t'], 't')
EOF

# --- S3: 建模（产出 solver/true3d_ccx.inp；门 G-P2: 质量台账对 4108.467 t） ------
python3 code/build_true3d_ccx.py
python3 - <<'EOF'
import json
m = json.load(open('artifacts/true3d_model_manifest.json'))
t = m['mass_ledger_t']
rel = abs(t['total'] - t['s10_reference']) / t['s10_reference']
print(f"mass total {t['total']:.3f} t vs S10 {t['s10_reference']:.3f} t rel {rel:.2e}")
assert rel < 0.01, "G-P2 FAIL: mass ledger off by >1%"
print('G-P2 PASS')
EOF

# --- S4: ccx 静力+摄动模态（门 G-P3: 静力收敛 exit 0；G-P4: 无伪模态低频段） -----
cd solver
time ccx -i true3d_ccx 2>&1 | tee true3d_ccx.stdout.txt
grep -q "Job finished" true3d_ccx.stdout.txt || { echo 'G-P3 FAIL'; exit 1; }
cd ..

# --- S5: 模态后处理 + 表 4-1 配对（锁定规则；产出 modal_basis.npz） --------------
python3 code/postprocess_modes.py

echo "solver chain done; next: python3 code/buffeting.py --scenario site_sutong_100yr_obs"
echo "then: python3 code/sweep_extreme.py && python3 code/make_atlas.py"
