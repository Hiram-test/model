#!/usr/bin/env python3
"""Transcribe the second user drawing into SI geometry; never infer from CFD targets."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
S=.008  # interpreted 1:8 drawing, dimensions on supplied image treated as mm
carrier_x=[v*S for v in [-238.75,-186.25,-133.75,-81.25,81.25,133.75,186.25,238.75]]
checks={
    'eight_carriers': len(carrier_x)==8,
    'drawing_chain_closes_500': abs(2*11.25+2*157.5+162.5-500)<1e-9,
    'outer_width_521_25': abs(500+2*10.625-521.25)<1e-9,
    'carrier_middle_gap_1_3m': abs(carrier_x[4]-carrier_x[3]-1.3)<1e-9,
    'carrier_group_pitch_0_42m': all(abs(carrier_x[i+1]-carrier_x[i]-.42)<1e-9 for i in [0,1,2,4,5,6]),
    'timber_span_chain_490': 170+150+170==490,
    'square_beam_80x80x4': [v*8 for v in [10,10,.5]]==[80,80,4],
    'post_L75x75x6': [v*8 for v in [9.375,9.375,.75]]==[75,75,6],
    'tube_48x3_is_crossbeam_not_carrier': [v*8 for v in [6,.375]]==[48,3],
    'timber_60x40_pitch500': [v*8 for v in [7.5,5,62.5]]==[60,40,500],
}
assert all(checks.values())
cfg=dict(
    model_id='user_drawing_8rope_midspan',
    description='Second user-supplied A-A/B-B/C-C drawing; independent prototype-scale 2-D trial',
    section_name='between transverse members',
    scale=1, drawing_to_prototype_scale=8, drawing_unit='assumed mm',
    scale_status='INFERRED from three standard member sizes; source caption absent',
    B_geometry=4.0, B_reference=4.17, H_reference=1.5,
    reference_dimensions_status='Outer A-A width 521.25*8 mm and nominal midspan height 187.5*8 mm; table reference dimensions unconfirmed',
    rho=1.225, nu=1.5e-5, carrier_x=carrier_x, carrier_diameter=.05,
    carrier_diameter_status='ASSUMED 50 mm; supplied image does not label rope diameter; phi6x0.375 labels a transverse tube',
    handrails=[[.5,.02],[1.0,.02],[1.5,.02]],
    handrails_status='ASSUMED three 20 mm ropes per side at 0.5/1.0/1.5 m; gross railing envelope only',
    screen_height=1.5, side_open_area=.85, coarse_floor_open_area=.75, fine_floor_open_area=1.0,
    screen_status='ASSUMED 85% side and 75% total floor open area, supported as trial values by Yuan 2026, not identified as the same bridge',
    equivalent_pitch=.1, floor_combined_y=.043,
    fine_strip_inner_x=.6, fine_strip_outer_x=1.96,
    floor_layer_gap_status='One equivalent row for total floor open area; no artificial second physical layer',
    domain=[-20.,40.,-20.,20.], span_2d=.1,
    moment_origin=[0,.7375,0],
    moment_origin_status='ASSUMED nominal midspan envelope centre, (-0.025+1.5)/2; table moment axis absent',
    moment_positive='clockwise, minus OpenFOAM z moment; adopted convention, new table diagram is cropped',
    inlet_length_scale=.1, speed_assumption=15.,
    speed_status='Trial value 15 m/s from comparable literature, not a measured speed from user image',
    geometry_audit='geometry/user_drawing_audit.json',
    model_status='ENGINEERING_SIMPLIFICATION',
    scope='2-D only; 3-D held. Ordinary slice between discrete transverse timber, tubes, square beams and posts.',
    omitted_discrete_members={
        'square_crossbeam': {'section_mm':[80,80,4],'pitch_m':6.0},
        'tube_crossbeam': {'section_mm':[48,3],'pitch_m':6.0,'relative_axial_offset':'unknown'},
        'timber': {'section_mm':[60,40],'pitch_m':.5,'transverse_intervals_m':[[-1.96,-.6],[.6,1.96]]},
        'post': {'section_mm':[75,75,6],'pitch_m':'unknown'},
    },
)
audit=dict(model_id=cfg['model_id'],production_ready=False,engineering_runs_allowed=True,
           authorization='User allows gross drawing geometry, 2-D trial, 3-D held; push all work to GitHub',
           source='Two user-supplied images: A-A/B-B/C-C drawing and Table 5.8',
           scale_is_inferred=True,checks=checks,
           limitations=['No original drawing caption/scale available','Unlabelled rope/rail/net details are explicit assumptions',
                        'Table reference width, height and moment axis not identified','No 3-D or axial station averaging claimed'],
           excluded_source_match='Yuan2026 uses 340 mm carrier spacing and 4200 mm width, different from supplied 420 mm spacing and 4170 mm outer width')
(ROOT/'geometry/user_drawing_model.json').write_text(json.dumps(cfg,indent=2)+'\n')
(ROOT/'geometry/user_drawing_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
timber=dict(cfg)
timber.update(model_id='user_drawing_8rope_C_C',section_name='C-C timber station (sensitivity only)',
              timber_sections=[[-1.96,.05,1.36,.04],[.6,.05,1.36,.04]],
              timber_replaces_net=True,
              timber_status='Actual 40 mm thickness and 1.36 m lengths retained; covered equivalent net rods omitted at timber station; no axial homogenization',
              scope='2-D C-C local timber station; not the whole-section mean, 3-D held')
(ROOT/'geometry/user_drawing_timber_model.json').write_text(json.dumps(timber,indent=2)+'\n')
print('Independent model written:',len(carrier_x),'ropes;',sum(checks.values()),'dimension checks passed')
