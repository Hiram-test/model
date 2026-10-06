#!/usr/bin/env python3
"""Summarize the second geometry from native forceCoeffs, retaining failed checks."""
import csv
import json
import math
import subprocess
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from assess_results import assess

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'results/user_drawing'
out.mkdir(parents=True,exist_ok=True)
ref=np.genfromtxt(ROOT/'sources/table_5_8_user.csv',delimiter=',',names=True)
a=np.deg2rad(ref['alpha_deg']); c=np.cos(a); s=np.sin(a)
def residual(r):
    return np.r_[ref['CH']*c+r[0]*ref['CV']*s-ref['CD'],
                 ref['CV']*c-ref['CH']*s/r[0]-ref['CL']]
ratio=float(least_squares(residual,[2.7]).x[0])
audit=dict(source='Manual transcription of user image, Table 5.8; 25 rows, original 0.001 precision',
           inferred_reference_B_over_H=ratio,max_rotation_residual=float(max(abs(residual([ratio])))),
           selected_drawing_B_over_H=4.17/1.5,
           geometry_or_normalization_fitted=False,
           interpretation='Diagnostic of coefficient conventions only; original reference dimensions remain unconfirmed')
(out/'table_convention_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
rows=[]
for prefix in ['user_urans','user_timber']:
    for case in (ROOT/'cases').glob(prefix+'*'):
        if not (case/'case.json').exists(): continue
        r=assess(case)
        if not r: continue
        cfg=json.loads((case/'case.json').read_text())
        r['requested_end_time_s']=cfg.get('physical_end_time')
        r['user_stop']=json.loads((case/'user_stop.json').read_text()) if (case/'user_stop.json').exists() else None
        target=ref[np.argmin(abs(ref['alpha_deg']-r['alpha_deg']))]
        rad=math.radians(r['alpha_deg']); co=math.cos(rad); si=math.sin(rad)
        B,H=cfg['B_reference'],cfg['H_reference']; q=.5*cfg['rho']*cfg['speed']**2
        r.update(section=cfg['section_name'],B_reference_m=B,H_reference_m=H,
                 CH=r['CD']*co-B/H*r['CL']*si,CV=H/B*r['CD']*si+r['CL']*co,
                 drag_N_per_m=r['CD']*q*H,lift_N_per_m=r['CL']*q*B,
                 clockwise_moment_Nm_per_m=r['CM']*q*B**2,
                 reference={k:float(target[k]) for k in ['CH','CV','CM','CD','CL']},
                 errors={k:r[k]-float(target[k]) for k in ['CD','CL','CM']})
        rows.append(r)
rows.sort(key=lambda r:(r['case'].startswith('user_timber'),r['alpha_deg']))
summary=dict(scope='Second user drawing, midspan, prototype-scale 2-D trials; 3-D held',
             mesh_independence_demonstrated=False,time_step_independence_demonstrated=False,
             reproduction_validated=False,skill_created=False,
             table_conventions=audit,cases=rows)
try:
    summary['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
except (FileNotFoundError,subprocess.CalledProcessError):
    version=ROOT/'CODE_VERSION.json'
    summary['source_commit']=json.loads(version.read_text())['commit'] if version.exists() else 'unversioned-worktree'
summary['saved_mesh_checks']={name:json.loads((ROOT/'results'/folder/'saved_mesh_audit.json').read_text())
                             for name,folder in [('regular','user_drawing'),('timber','user_timber')]}
(out/'trial_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
fields=['case','section','alpha_deg','B_reference_m','H_reference_m','CH','CV','CM','CD','CL',
        'drag_N_per_m','lift_N_per_m','clockwise_moment_Nm_per_m',
        'iteration','requested_end_time_s','ended','stopped_early','solver_converged','coefficients_stable','sample_duration_BU']
with (out/'loads_and_coefficients.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows)
lines=['# 新增图纸：二维试算结果','',
       '**已按用户图片建立独立的8索二维简化模型，并使用Gmsh和OpenFOAM实际计算。尚未验证为成功复现表5.8。**','',
       '采用推定1:8还原的原型尺寸：净宽4.000m、外宽4.170m、中跨名义高度1.500m、索距0.420m、中央索距1.300m。完整来源与假设见[建模说明](../../report/user_drawing_assumptions.md)。','',
       '普通截面25,048个单元，C-C截面25,222个单元；均通过OpenFOAM原生checkMesh和MSH实际索数、位置、尺寸、挤出厚度的反查。','',
       '表5.8原值按图片转录，保留三位小数。普通截面为横向离散构件之间的网片及索；0°另算C-C木踏板局部截面，不代表整段猫道平均。来流15m/s，URANS SST，计划计算至1.5s，自0.75s至实际末时刻作短时加权统计。用户要求停止并上传时，+6°与+12°尚未到达目标时间，已通过原生stopAt writeNow保存场并正常退出；其实际时长见下表及user_stop.json。','',
       '|截面|攻角|CD试算|CD表值|CL试算|CL表值|CM试算|CM表值|',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
    label='C-C木条' if r['case'].startswith('user_timber') else '网片与索'
    t=r['reference']
    lines.append(f"|{label}|{r['alpha_deg']:+g}°|{r['CD']:.5f}|{t['CD']:.3f}|{r['CL']:.5f}|{t['CL']:.3f}|{r['CM']:.5f}|{t['CM']:.3f}|")
lines += ['','## 原生求解与统计检查','',
          '|算例|已到时间/s|正常结束|提前停止|记录的最大Co|时间步数值检查|采样长度B/U|统计稳定检查|',
          '|---|---:|---|---|---:|---|---:|---|']
for r in rows:
    lines.append(f"|{r['case']}|{r['iteration']:.8g}|{r['ended']}|{r['stopped_early']}|{r['max_recorded_Co']:.3f}|{r['solver_converged']}|{r['sample_duration_BU']:.3f}|{r['coefficients_stable']}|")
lines += ['','原生网格检查通过不等于网格独立性验证，正常结束也不等于均值已稳定。时间步检查读取末步线性残差、目标时间和全程Courant数；统计检查至少需要20个B/U及分块均值稳定。本次统计最长0.75s，仅约2.70个B/U；+6°与+12°按用户要求提前保存，其窗口更短，各点统计长度不同。未做网格与时间步独立性。原3s终止时间在统计窗口前统一调整为1.5s，原始启动记录和变更原因保存在各例pilot_scope_update.json；本次用户停止另记于user_stop.json。',
          '',f'表中两套力轴反映的参考B/H约为{ratio:.4f}，本轮明确采用图纸外宽/名义高度=2.7800。原表的分母及力矩轴没有完整题注，未通过反求系数来调模型。`loads_and_coefficients.csv`同时给出按当前轴定义的CH、CV和每延米力/矩，便于有确切定义后重新归一化。',
          '', '三维未运行。图中连接五个已计算点的虚线只用于读图，其余攻角没有进行CFD求解。完整25点黑线来自用户表格，不能误认为CFD结果。',
          '', '文件：`comparison.png/pdf/csv`、`time_histories.png/pdf`、`geometry_2d.png`、`trial_summary.json`及每个算例的全时间历史CSV；木踏板对照在相邻`user_timber`目录。原生网格、字典、末时刻场、完整forceCoeffs和日志另随结果包保存。', '']
(out/'stage_report.md').write_text('\n'.join(lines))
print('Summarized native cases:',len(rows),'reproduction_validated=False')
