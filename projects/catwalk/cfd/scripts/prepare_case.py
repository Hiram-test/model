#!/usr/bin/env python3
"""Write OpenFOAM dictionaries. No fluid discretization or flow solver lives here."""
import argparse,json,math,shutil
from pathlib import Path

def header(name,cls='dictionary'):
    return f'FoamFile\n{{ version 2.0; format ascii; class {cls}; object {name}; }}\n'

def create_case(out,mesh,angle=0,speed=13.8,iterations=1500,intensity=.01):
    out=Path(out);mesh=Path(mesh)
    for d in ['0','constant','system']: (out/d).mkdir(parents=True,exist_ok=True)
    cfg=json.loads((mesh/'geometry.json').read_text())
    if (mesh/'constant/polyMesh').exists() and out.resolve()!=mesh.resolve():
        shutil.copytree(mesh/'constant/polyMesh',out/'constant/polyMesh',dirs_exist_ok=True)
    rad=math.radians(angle);c,s=math.cos(rad),math.sin(rad)
    vel=f'({speed*c:.12g} {speed*s:.12g} 0)'
    drag=f'({c:.12g} {s:.12g} 0)'; lift=f'({-s:.12g} {c:.12g} 0)'
    length_scale=cfg.get('inlet_length_scale',.01)
    k=1.5*(speed*intensity)**2;omega=math.sqrt(k)/(.09**.25*length_scale)
    origin=cfg.get('moment_origin',[0,0,0])
    def write(d,name,text,cls='dictionary'):(out/d/name).write_text(header(name,cls)+text+'\n')
    bcommon='frontAndBack { type '+('symmetry' if cfg.get('dimension',2)==3 else 'empty')+'; }'
    write('0','U',f'''dimensions [0 1 -1 0 0 0 0];
internalField uniform {vel};
boundaryField {{
inlet {{ type fixedValue; value uniform {vel}; }}
outlet {{ type inletOutlet; inletValue uniform {vel}; value uniform {vel}; }}
farfield {{ type inletOutlet; inletValue uniform {vel}; value uniform {vel}; }}
body {{ type noSlip; }}
{bcommon}
}}''','volVectorField')
    write('0','p',f'''dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField {{
inlet {{ type zeroGradient; }}
outlet {{ type fixedValue; value uniform 0; }}
farfield {{ type zeroGradient; }}
body {{ type zeroGradient; }}
{bcommon}
}}''','volScalarField')
    for name,dim,val,wall in [('k','[0 2 -2 0 0 0 0]',k,'kqRWallFunction'),('omega','[0 0 -1 0 0 0 0]',omega,'omegaWallFunction'),('nut','[0 2 -1 0 0 0 0]',0,'nutUSpaldingWallFunction')]:
        wallval=val
        if cfg.get('wall_treatment')=='lowRe':
            if name=='k':wall='fixedValue';wallval=0
            if name=='nut':wall='nutLowReWallFunction';wallval=0
        bcs=f'inlet {{ type fixedValue; value uniform {val}; }}' if name!='nut' else 'inlet { type calculated; value uniform 0; }'
        for patch in ['outlet','farfield']:
            bcs+=f'\n{patch} {{ type inletOutlet; inletValue uniform {val}; value uniform {val}; }}' if name!='nut' else f'\n{patch} {{ type calculated; value uniform 0; }}'
        bcs+=f'\nbody {{ type {wall}; value uniform {wallval}; }}\n{bcommon}'
        write('0',name,f'dimensions {dim};\ninternalField uniform {val};\nboundaryField {{ {bcs} }}','volScalarField')
    force_patches=['body']
    if cfg.get('baffles_created'):
        additions={name:'' for name in ['U','p','k','omega','nut']}
        for screen in cfg['screens']:
            # Brundrett's screen correlation, momentum/energy correction ratio=1.
            # Linear term is retained exactly; inertial term is frozen at reference U.
            D=I=0.0
            for layer in screen['layers']:
                beta=layer['open_area'];dia=layer['diameter'];G=(1-beta**2)/beta**2
                Re=speed*dia/cfg['nu']
                D+=G*7.125/(2*dia)
                I+=G*(.88/math.log(Re+1.25)+.055*math.log(Re))
            screen.update(D=D,I=I,length=1.0,correlation='Brundrett1993; natural logarithm; inertial factor at reference speed; layer pressure losses added')
            for side in [0,1]:
                patch=screen['name']+str(side);force_patches.append(patch)
                for fld in ['U','k','omega','nut']:additions[fld]+=f'\n{patch} {{ type cyclic; }}\n'
                additions['p']+=f'\n{patch} {{ type porousBafflePressure; patchType cyclic; D {D}; I {I}; length 1; value uniform 0; }}\n'
        for fld,addition in additions.items():
            p=out/'0'/fld;s=p.read_text();end=s.rfind('}');p.write_text(s[:end]+addition+s[end:])
    write('constant','transportProperties','transportModel Newtonian;\nnu [0 2 -1 0 0 0 0] '+str(cfg['nu'])+';')
    write('constant','turbulenceProperties','simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }')
    functions=''
    for name,area in [('coeffsB',cfg['B_reference']*cfg['span_2d']),('coeffsH',cfg['H_reference']*cfg['span_2d'])]:
        functions+=f'''{name}
{{
type forceCoeffs; libs ("libforces.so"); patches ({' '.join(force_patches)});
rho rhoInf; rhoInf {cfg['rho']}; log false;
CofR ({origin[0]} {origin[1]} {cfg['span_2d']/2});
dragDir {drag}; liftDir {lift}; pitchAxis (0 0 -1);
magUInf {speed}; lRef {cfg['B_reference']}; Aref {area};
writeControl timeStep; writeInterval 5;
}}
'''
    functions+='yPlus { type yPlus; libs ("libfieldFunctionObjects.so"); writeControl writeTime; log false; }\n'
    write('system','controlDict',f'''application simpleFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime {iterations}; deltaT 1;
writeControl timeStep; writeInterval {iterations}; purgeWrite 1;
writeFormat binary; writePrecision 9; timeFormat general; timePrecision 8;
runTimeModifiable true;
functions {{ {functions} }}''')
    write('system','fvSchemes','''ddtSchemes { default steadyState; }
gradSchemes { default cellLimited Gauss linear 1; }
divSchemes {
default none;
div(phi,U) bounded Gauss linearUpwind grad(U);
div(phi,k) bounded Gauss upwind;
div(phi,omega) bounded Gauss upwind;
div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
fluxRequired { default no; p; }''')
    write('system','fvSolution','''solvers {
p { solver GAMG; tolerance 1e-8; relTol 0.05; smoother GaussSeidel; }
"(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.05; }
}
SIMPLE { nNonOrthogonalCorrectors 0; consistent no;
residualControl { p 1e-5; U 1e-6; k 1e-6; omega 1e-6; }
}
relaxationFactors { fields { p 0.15; } equations { U 0.3; k 0.3; omega 0.3; } }''')
    write('system','decomposeParDict','numberOfSubdomains 4;\nmethod hierarchical;\nhierarchicalCoeffs { n (4 1 1); delta 0.001; order xyz; }')
    cfg.update(alpha_deg=angle,speed=speed,inlet_turbulence_intensity=intensity,inlet_length_scale=length_scale,iterations_requested=iterations,solver='OpenFOAM simpleFoam kOmegaSST',status='INPUT_PREPARED')
    (out/'case.json').write_text(json.dumps(cfg,indent=2))
    (out/(out.name+'.foam')).touch()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--mesh',required=True);p.add_argument('--angle',type=float,default=0);p.add_argument('--speed',type=float,default=13.8);p.add_argument('--iterations',type=int,default=1500);p.add_argument('--intensity',type=float,default=.01)
    a=p.parse_args();create_case(a.out,a.mesh,a.angle,a.speed,a.iterations,a.intensity)
