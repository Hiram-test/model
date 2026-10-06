#!/usr/bin/env python3
"""Trace geometry to sources; never infer dimensions by fitting aerodynamic data."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    nodes, reals, elements = {}, {}, []
    etype = real = None
    source = ROOT / 'sources/full_line_beam4_crossbeam_mesh_xlong.inp'
    for line in source.read_text().splitlines():
        fields = line.strip().split(',')
        command = fields[0].upper()
        if command == 'N':
            nodes[int(fields[1])] = tuple(map(float, fields[2:5]))
        elif command == 'R':
            reals[int(fields[1])] = list(map(float, fields[2:]))
        elif command == 'TYPE':
            etype = int(fields[1])
        elif command == 'REAL':
            real = int(fields[1])
        elif command == 'E':
            elements.append((int(fields[1]), int(fields[2]), etype, real))
    # Select by actual LINK10 + real-constant membership, not all nodes in a band.
    carrier_nodes = {n for a, b, t, r in elements if t == 1 and r == 1 for n in (a, b)}
    transverse = sorted({nodes[n][1] for n in carrier_nodes if nodes[n][1] > 0})
    center = (transverse[0] + transverse[-1]) / 2
    xcoords = [y - center for y in transverse]
    expected = sorted(sign * (850 + 260 * n) for sign in (-1, 1) for n in range(8))
    checks = {
        'sixteen_carrier_lines': len(xcoords) == 16,
        'matches_MD0_03_and_MD1_03': xcoords == expected,
        'transverse_symmetry': all(a == -b for a, b in zip(xcoords, reversed(xcoords))),
        'carrier_diameter_50': math.isclose(math.sqrt(4 * reals[1][0] / math.pi), 50),
        'big_tube_area_100x100x4': math.isclose(reals[3][0], 100**2 - 92**2),
        'small_tube_area_50x50x4': math.isclose(reals[4][0], 50**2 - 42**2),
        'big_tube_I': math.isclose(reals[3][1], (100**4 - 92**4) / 12),
        'small_tube_I': math.isclose(reals[4][1], (50**4 - 42**4) / 12),
    }
    assert all(checks.values()), checks

    dims = {
        'status': 'VERIFIED_PROTOTYPE_DIMENSIONS_ONLY_NOT_A_TUNNEL_ASSEMBLY',
        'units': 'mm',
        'coordinate_convention': 'x transverse; y vertical; z along bridge; component local origins only',
        'source_commit': '9b62c3e2c882bf2dd0001cb3b81943df7d4f5fea',
        'carrier': {'count': 16, 'diameter': 50, 'x': xcoords,
                    'inp_single_catwalk_center_y': center, 'source': 'INP ET1/R1 + MD0-03 + MD1-03'},
        'nominal_width': {'value': 5600, 'meaning': 'clear width between post inner faces; not total envelope',
                          'source': 'MD1-01; report Fig2-2 also labels 5600'},
        'big_beam': {'outer': 100, 'thickness': 4, 'tube_length': 5772,
                     'end_cap': 4, 'overall_length': 5780, 'source': 'MD1-01/MD1-02'},
        'small_beam': {'outer': 50, 'thickness': 4, 'tube_length': 5520,
                       'end_cap': 2, 'overall_length': 5524, 'source': 'MD1-03'},
        'timber': {'transverse_length': 2000, 'vertical_height': 30, 'axial_width': 50,
                   'axial_pitch': 500, 'x_ranges': [[-2760, -760], [760, 2760]],
                   'vertical_datum': None, 'axial_phase': None, 'source': 'MD1-03'},
        'post': {'leg': 75, 'thickness': 6, 'component_length': 1340,
                 'connector_length': 270, 'assembly_foot_to_top': 1450,
                 'source': 'MD1-01/MD1-02; 1340 is a component length, 1450 is an assembly dimension'},
        'rails': {'top_diameter': 36, 'middle_lower_diameter': 20,
                  'drawing_vertical_dimension_chain': [500, 460, 460],
                  'absolute_centers_relative_to_carrier': None,
                  'source': 'MD0-03, MD1-01; drawing diameter preferred over conflicting review load table'},
        'screens': {
            'coarse_floor': {'diameter': 5, 'quoted_opening': [50, 70], 'sheet_width': 5600},
            'fine_floor': {'diameter': 2, 'quoted_opening': [25, 25], 'sheet_width': 2000},
            'side': {'diameter': 5, 'quoted_opening': [50, 100], 'stock_sheet_width': 1500},
            'source': 'MD1-02 notes 5,6',
            'clear_opening_or_center_pitch': None, 'wire_orientation': None,
            'woven_layer_positions': None, 'fine_strip_installed_x_ranges': None,
            'installed_side_height': None,
            'note': 'Photo and elevation support mesh terminating at middle rail. Stock width is not installed height.'},
        'main_span_pattern': {'repeat_length': 9000, 'big_beam_at': [0, 9000],
                              'small_beam_at': [3000, 6000], 'source': 'MD0-03 note2'},
        'side_span_pattern': {'repeat_length': 6000, 'big_beam_at': [0, 6000],
                              'small_beam_at': [3000], 'source': 'MD0-03 note2'},
        'tunnel_report': {'scale': .1, 'B': 540, 'H': 150, 'L': 2100,
                          'actual_speed_m_per_s': None, 'actual_turbulence': None,
                          'measured_screen_geometry': None, 'moment_axis_height': None,
                          'represented_span_and_member_phase': None, 'end_plate_geometry': None,
                          'source': 'Report section3.1/3.2; these B,H are reported reference values, not reconciled geometry'},
    }
    (ROOT / 'geometry/verified_dimensions.json').write_text(json.dumps(dims, indent=2, ensure_ascii=False))

    issues = [
        ('G01', 'OPEN', '试件宽高及归一化尺寸', '报告§3.1写540×150；报告图2-2和MD1-01净宽5600，1:10为560；表3-1两坐标系还隐含不同B/H', '须核实实际试件与归一化所用B、H，不能把几何缩成540以追曲线'),
        ('G02', 'OPEN', '实测筛网及网孔定义', 'MD1-02只有名义规格；报告只说保持透风率尽量一致', '需试件丝径、净孔或中心节距、纵横方向和双层网相位/间距'),
        ('G03', 'OPEN', '竖向定位基准', 'MD1-01有局部装配和尺寸链；图中未明确给出所有网丝中心到承重索中心的坐标', '不得将500、460、460直接拼成已经核实的全套中心坐标；保留待核实'),
        ('G04', 'OPEN', '侧网实际范围', 'MD0-03与报告图3-2支持只到中扶手；MD1-02标的是1.5m网片；旧脚本却取1.15m并对齐上扶手', '按试件核定蒙网范围和折边；不能用整高实心板代替'),
        ('G05', 'OPEN', '风洞节段构件布置', '原型中跨大梁9m、边跨6m，小梁3m、木条0.5m；试件长21m原型尺度', '需试件对应跨度、起止相位、梁柱数量、端部附加件；不能自动套3m重复单元'),
        ('G06', 'OPEN', '测力轴O', '报告图3-4示意O位于底网之上但无轴高；先前CFD轴在承重索中心面', '核定轴点后用软件积分输出做明确的力矩平移；禁止从目标CM反求'),
        ('G07', 'OPEN', '试验风速及来流', '报告给设计风速和风洞设备量程，没有本次测力实际U、I、湍流尺度', '不能用13.8、34.3或44.9m/s设计值冒充试验来流；10m/s仅为试算假设'),
        ('G08', 'OPEN', '端板、支撑与风洞边界', '报告图3-1可见端板与支撑，风洞2.4m×2m', '核实尺寸、测力扣除、阻塞修正；模型旋转和风向旋转在有限风洞中不等价'),
        ('D01', 'RESOLVED_FOR_PROTOTYPE', '承重索', 'INP按ET1/R1筛选到16根φ50，坐标与MD0-03、MD1-03一致', '采用可追溯的原型索线；尚不能证明每根试件丝径完全按1:10制作'),
        ('D02', 'RESOLVED_FOR_PROTOTYPE', '木条', 'MD1-03明确50×30×2000、间距500、横向边界±760至±2760', '三维显式保留；二维横断面不可把离散木条无限挤出'),
        ('D03', 'RESOLVED_FOR_PROTOTYPE', '大小横梁', 'MD1-02:100×100×4×5772；MD1-03:50×50×4×5520；端板后总长5780、5524', '原型9m或6m完整节段正确计数；中跨3m平移并非结构周期'),
        ('D04', 'RESOLVED_FOR_PROTOTYPE', '扶手立柱', 'MD1-02材料表L75×75×6×1340，另有270连接角钢；1450是装配尺寸', '1340构件与连接角钢分别建模，不把1450当单根构件长度'),
        ('D05', 'CONFLICT_RECORDED', '中下扶手直径', 'MD0-03/MD1-01写φ20；结构复核表1-1写φ22', '原型采用有详细构造的φ20；试件仍需核定'),
        ('D06', 'CONFLICT_RECORDED', '粗网规格', 'MD1-02和结构复核表1-1写50×70，复核§1.4文字写50×75', '原型按MD1-02的50×70；不混用不同版本'),
        ('M01', 'REJECTED_FOR_VALIDATION', '既有GitHub节段STEP', '其脚本在500、1000、1500、2000、2500布小梁，两端布大梁', '间距不符MD0-03，且侧网、木条标高待核实；只作参考，不能直接用于复现'),
        ('M02', 'REJECTED_FOR_VALIDATION', '首版二维双层网', '两排放大等效圆杆及其间距没有试件依据', '已有V1结果全部标为SUPERSEDED'),
        ('M03', 'AUDIT_PENDING', '修订二维等效网', '开孔率乘积取决于独立相位假设；为避扶手而删等效杆还会改变遮挡', '逐项量化模型误差；相同开孔率不等于相同压降或斜向透风'),
        ('M04', 'LOCAL_CELL_ONLY', '已生成三维微胞', '5mm轴向、对称端面、仅网丝和绳索，无木条梁柱和端板', '是三维几何微胞，不是2.1m风洞节段，也不能用于三维效果结论'),
    ]
    with (ROOT / 'geometry/audit_register.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['id', 'status', 'item', 'evidence', 'required_action']); w.writerows(issues)
    files = ['sources/full_line_beam4_crossbeam_mesh_xlong.inp', 'sources/catwalk_drawings_1225.pdf',
             'sources/catwalk_structural_review.pdf', 'sources/table_3_1.csv',
             'sources/github_segment_reference/build_catwalk_segment_6x500_explicit_mesh.py',
             'sources/yuan_catwalk_static_wind.pdf']
    audit = {'status': 'DRAWING_GROSS_GEOMETRY_REVIEWED_ENGINEERING_CFD_ALLOWED', 'production_ready': False,
             'engineering_runs_allowed': True, 'drawing_model_runs_allowed': True,
             'drawing_dimension_review_passed': all(checks.values()),
             'scope_update': 'User requires prototype drawing geometry, gross dimensions, 2-D first; 3-D held.',
             'tunnel_issues_outside_current_scope': ['G01','G02','G05','G06','G07','G08'],
             'engineering_assumptions_documented': ['G03','G04'],
             'prototype_dimension_checks': checks, 'open_critical_issues': [],
             'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
             'case_policy': 'Drawing-scale engineering CFD allowed. production_ready denotes validated reproduction, not permission to compute.',
             'skill_status': 'NOT_CREATED_BECAUSE_REPRODUCTION_NOT_VALIDATED'}
    (ROOT / 'geometry/audit_status.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    print(json.dumps({'prototype_checks': checks, 'production_ready': False, 'open_issues': audit['open_critical_issues']}, indent=2))


if __name__ == '__main__':
    main()
