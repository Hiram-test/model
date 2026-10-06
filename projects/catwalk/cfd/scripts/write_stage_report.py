#!/usr/bin/env python3
"""Build a factual stage report from native output; never replace failed criteria."""
import argparse
import json
from pathlib import Path
import subprocess
import numpy as np
from assess_results import assess

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--prefix', default='rod_urans')
ap.add_argument('--output',default='results/zhangjinggao')
a = ap.parse_args()
out=ROOT/a.output
out.mkdir(parents=True,exist_ok=True)
rows = [assess(p) for p in sorted((ROOT / 'cases').glob(a.prefix + '*')) if (p / 'case.json').exists()]
rows = sorted([r for r in rows if r], key=lambda r: r['alpha_deg'])
if not rows:
    raise RuntimeError('No native output found')
ref = np.genfromtxt(ROOT / 'sources/table_3_1.csv', delimiter=',', names=True)
limits = {'CD': .08, 'CL': .01, 'CM': .003}
comparisons = []
for r in rows:
    target = ref[np.argmin(abs(ref['alpha_deg'] - r['alpha_deg']))]
    comparisons.append(dict(case=r['case'], alpha_deg=r['alpha_deg'],
        values={k: r[k] for k in limits}, reference={k: float(target[k]) for k in limits},
        errors={k: r[k] - float(target[k]) for k in limits},
        within_comparison_limits=all(abs(r[k] - target[k]) <= limit for k, limit in limits.items())))
passed_numerical = all(r['solver_converged'] and r['coefficients_stable'] for r in rows)
# Neither mesh nor time-step independence has been demonstrated for this primary pilot.
try:
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
except (subprocess.CalledProcessError, FileNotFoundError):
    version_file = ROOT / 'CODE_VERSION.json'
    source_commit = json.loads(version_file.read_text())['commit'] if version_file.exists() else 'unversioned-worktree'
result = dict(scope='Drawing-scale prototype, 2-D pilot; 3-D held',
              source_commit=source_commit,
              cases=rows, comparisons=comparisons, comparison_limits=limits,
              numerical_checks_passed=passed_numerical, mesh_independence_demonstrated=False,
              time_step_independence_demonstrated=False, reproduction_validated=False,
              skill_created=False, reason='Short pilot only; full numerical and physical-model validation not completed')
(out / 'primary_summary.json').write_text(json.dumps(result, indent=2))
lines = ['# 二维原型 CFD 阶段结果', '',
    '**二维建模—网格—求解—三分力输出流程已实际执行；尚未验证为成功复现风洞曲线。** 三维继续暂停，未运行三维流场。', '',
    '本轮采用图纸原型净宽5.6 m、参考高度1.477 m，16根φ50承重索及6根扶手索；网片按等开孔率圆杆简化。沿桥长离散的横梁、立柱、木条未在本二维截面中等效，故这是网片与索的截面试算，不是完整猫道构件的等效结果。', '',
    '软件为Gmsh 4.8.4和OpenFOAM 1912，未自写网格或流体求解器。采用30,278个单元，原生checkMesh及实际MSH中的16根承重索、位置、尺寸、挤出厚度反查均通过。攻角正向、力方向和顺时针力矩定义按报告图3-4设置。来流13.8 m/s为所选原型工况。', '',
    '## 三个攻角的短时统计', '',
    '以下值从原生forceCoeffs按物理时间加权得到。1–2 s窗口只有约2.46个B/U，不满足当前20个B/U的最低统计检查；这些是初算值，不能作为已收敛的设计系数。未计算的攻角不能用连线视为已经求解。', '',
    '|攻角|CD初算|CD报告|CL初算|CL报告|CM初算|CM报告|', '|---:|---:|---:|---:|---:|---:|---:|']
for c in comparisons:
    v, t = c['values'], c['reference']
    lines.append(f"|{c['alpha_deg']:+g}°|{v['CD']:.5f}|{t['CD']:.5f}|{v['CL']:.5f}|{t['CL']:.5f}|{v['CM']:.5f}|{t['CM']:.5f}|")
lines += ['', '## 数值状态', '', '|算例|已到时间/s|正常结束|记录的最大Co|时间步数值检查|统计稳定检查|', '|---|---:|---|---:|---|---|']
for r in rows:
    lines.append(f"|{r['case']}|{r['iteration']:.6g}|{r['ended']}|{r['max_recorded_Co']:.3f}|{r['solver_converged']}|{r['coefficients_stable']}|")
lines += ['',
    '网格已通过原生checkMesh检查；这不等于完成网格独立性验证。时间步检查同时要求正常达到目标时间、末步线性残差不大于1.1e-6、记录的最大Co小于设置上限的1.05倍；正常结束但Co短暂超过检查范围的算例仍标为false。初算误差与统计不足均保留，不通过改符号、改分母或拟合目标曲线消除。当前不足以分离二维网片等效、离散构件省略、雷诺数和统计时长各自造成的影响。', '',
    '纯多孔薄面另作过对照。其原生压降及力矩积分通过解析直管核验，但它遗漏沿网面方向的网丝阻力，因此没有作为主复现模型；对照及旧版本保留供追溯。', '',
    '## 文件与后续计算入口', '',
    '- `comparison.csv/png/pdf`：三点初算与报告对比。',
    '- `time_histories.png/pdf`、`rod_urans_*_history.csv`：实际非定常记录。',
    '- `selected_case_assessments.json`、`primary_summary.json`：逐项判定。',
    '- 原生算例含初始场、polyMesh、求解字典、时间场、日志和forceCoeffs输出。',
    '- 源码、配置、模型假设和运行方法见README与Git历史；源代码压缩包已独立解压复跑检查。', '',
    '若继续复现，应先延长同一主模型的统计并检查网格/时间步，再评估沿桥长离散构件的二维等效影响；不能把当前三点连线当作完整风洞复现。未创建“复现成功”的skill。', '']
(out / 'stage_report.md').write_text('\n'.join(lines))
print('Stage report written from', len(rows), 'native cases; reproduction_validated=False')
