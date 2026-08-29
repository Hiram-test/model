#!/usr/bin/env python3
"""在新的 FreeCADCmd 进程中独立验证 CAD-003。

本脚本不信任 builder 的退出码或自报计数：重新打开 FCStd、重新导入 STEP，
检查稳定 ID、来源、数量、形状、装配可达性、FEM-IR 与包围盒。它没有 Gate
判定权，几何检查通过也不会关闭 U-WIND-001。
"""
from __future__ import annotations
import argparse, hashlib, json, math, os
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import FreeCAD as App
import Import

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def env_path(name:str)->Path|None:
 value=os.environ.get(name);return Path(value) if value else None
def say(step,msg,**details):print(json.dumps({'timeUtc':now(),'stepId':step,'message':msg,'details':details},ensure_ascii=False),flush=True)
def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):d.update(b)
 return d.hexdigest()
def finite(point:Iterable[Any])->bool:
 try:
  v=[float(x) for x in point];return len(v)==3 and all(math.isfinite(x) for x in v)
 except Exception:return False
def prop(obj,name,default=None):
 try:return getattr(obj,name)
 except Exception:return default
def check(items,cid,passed,observed,expected,severity='CRITICAL'):items.append({'checkId':cid,'passed':bool(passed),'severity':severity,'observed':observed,'expected':expected})
def bbox(objects):
 boxes=[o.Shape.BoundBox for o in objects if hasattr(o,'Shape') and not o.Shape.isNull()]
 if not boxes:raise RuntimeError('no shapes for bbox')
 return {'xmin':min(b.XMin for b in boxes),'xmax':max(b.XMax for b in boxes),'ymin':min(b.YMin for b in boxes),'ymax':max(b.YMax for b in boxes),'zmin':min(b.ZMin for b in boxes),'zmax':max(b.ZMax for b in boxes)}
def bbox_delta(a,b):return max(abs(float(a[k])-float(b[k])) for k in a)
def components(nodes:set[str],edges:list[dict[str,Any]])->list[set[str]]:
 adj=defaultdict(set)
 for e in edges:
  a,b=e.get('from'),e.get('to')
  if a in nodes and b in nodes:adj[a].add(b);adj[b].add(a)
 unseen=set(nodes);out=[]
 while unseen:
  start=next(iter(unseen));q=deque([start]);group={start};unseen.remove(start)
  while q:
   cur=q.popleft()
   for other in adj.get(cur,set()):
    if other in unseen:unseen.remove(other);group.add(other);q.append(other)
  out.append(group)
 return out

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--contract',type=Path,default=env_path('CAD003_CONTRACT'));ap.add_argument('--assembly-graph',type=Path,default=env_path('CAD003_ASSEMBLY_GRAPH'));ap.add_argument('--build-dir',type=Path,default=env_path('CAD003_BUILD_DIR'));ap.add_argument('--output-dir',type=Path,default=env_path('CAD003_VALIDATION_DIR'));a=ap.parse_args()
 if not all((a.contract,a.assembly_graph,a.build_dir,a.output_dir)):ap.error('contract, assembly graph, build dir and output dir required')
 started=now();say('V00','独立 FreeCAD 校验进程启动',freecadVersion=list(App.Version()));contract=json.loads(a.contract.read_text(encoding='utf-8'));assembly=json.loads(a.assembly_graph.read_text(encoding='utf-8'));build=a.build_dir.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((build/'freecad_build_manifest.json').read_text(encoding='utf-8'));fc=build/'Zhaqing_CAD-003.FCStd';step=build/'Zhaqing_CAD-003-display.step';ir_path=build/'fem_geometry_ir.json';node_path=build/'interface_nodes.json';checks=[]
 say('V01','核对构建清单与四个关键文件哈希',buildDir=str(build))
 for name,path in [(fc.name,fc),(step.name,step),(ir_path.name,ir_path),(node_path.name,node_path)]:
  exists=path.exists() and path.stat().st_size>0;check(checks,f'FILE-{name}-EXISTS',exists,path.stat().st_size if exists else 0,'>0 bytes')
  if exists:
   actual=sha(path);expected=manifest.get('files',{}).get(name);check(checks,f'FILE-{name}-HASH',actual==expected,actual,expected)
 contract_sha=sha(a.contract);check(checks,'CONTRACT-HASH',manifest.get('contractSha256')==contract_sha,manifest.get('contractSha256'),contract_sha);check(checks,'RELEASE-FAIL-CLOSED',contract.get('overallEngineeringRelease')=='BLOCKED' and manifest.get('overallEngineeringRelease')=='BLOCKED',[contract.get('overallEngineeringRelease'),manifest.get('overallEngineeringRelease')],['BLOCKED','BLOCKED'])
 say('V10','在新进程中重新打开 FCStd',file=str(fc));doc=App.openDocument(str(fc));roots=[o for o in doc.Objects if prop(o,'IsComponentRoot',False)];displays=[o for o in doc.Objects if prop(o,'RepresentationRole','')=='DISPLAY_SOLID'];ids=[str(prop(o,'StableId','')) for o in roots];counts=Counter(str(prop(o,'ComponentGroup','')) for o in roots)
 check(checks,'ROOT-COUNT-BY-GROUP',dict(counts)==contract['expectedCounts'],dict(counts),contract['expectedCounts']);check(checks,'ROOT-STABLE-ID-UNIQUE',len(ids)==len(set(ids)) and all(ids),{'count':len(ids),'unique':len(set(ids))},'all nonempty and unique');check(checks,'ROOT-SOURCE-REFS',all(bool(str(prop(o,'SourceRefs',''))) for o in roots),sum(bool(str(prop(o,'SourceRefs',''))) for o in roots),len(roots))
 invalid=[prop(o,'StableId',o.Name) for o in roots if getattr(o,'Shape',None) is None or o.Shape.isNull() or not o.Shape.isValid()];check(checks,'ROOT-SHAPES-VALID',not invalid,invalid,[])
 invalid_display=[];nonpositive=[];parents=Counter()
 for o in displays:
  parents[str(prop(o,'ParentStableId',''))]+=1;shape=getattr(o,'Shape',None)
  if shape is None or shape.isNull() or not shape.isValid():invalid_display.append(o.Name)
  elif shape.Volume<=1e-6:nonpositive.append(o.Name)
 check(checks,'DISPLAY-SHAPES-VALID',not invalid_display,invalid_display,[]);check(checks,'DISPLAY-SOLIDS-POSITIVE-VOLUME',not nonpositive,nonpositive,[]);check(checks,'ONE-DISPLAY-PER-COMPONENT',set(parents)==set(ids) and all(parents[x]==1 for x in ids),{'parents':len(parents),'nonUnit':{k:v for k,v in parents.items() if v!=1}},{'parents':len(ids),'each':1})
 actual_bbox=bbox(displays);check(checks,'FCSTD-BOUNDING-BOX',bbox_delta(actual_bbox,manifest['displayBoundingBoxMm'])<=1e-6,actual_bbox,manifest['displayBoundingBoxMm']);say('V11','构件数量、ID、来源、形状与显示实体通过基础检查',rootCount=len(roots),displayCount=len(displays))
 wind_length=float(contract['parameters']['windCable']['lengthMm']);bad_w=[]
 for o in roots:
  if prop(o,'ComponentGroup','')=='wind_cables':
   if abs(float(o.Shape.Length)-wind_length)>1e-5 or abs(float(prop(o,'LengthMm',0))-wind_length)>1e-5:bad_w.append({'id':o.StableId,'shapeLength':o.Shape.Length,'propertyLength':prop(o,'LengthMm',0)})
 check(checks,'WIND-CABLE-EXACT-LENGTH',not bad_w,bad_w,f'{wind_length} mm')
 bad_h=[]
 for o in roots:
  if prop(o,'ComponentGroup','')=='hangers':
   L=float(prop(o,'RodLengthMm',0));edge_lengths=[e.Length for e in o.Shape.Edges]
   if not any(abs(x-L)<=1e-5 for x in edge_lengths):bad_h.append({'id':o.StableId,'rodLength':L,'edgeLengths':edge_lengths})
 check(checks,'HANGER-ROD-LENGTH-IN-SHAPE',not bad_h,bad_h,'one edge equals exact table L');say('V12','吊杆杆长与风缆精确长度检查完成')
 node_set=set(ids);missing=sorted({x for e in assembly.get('edges',[]) for x in (e.get('from'),e.get('to')) if x not in node_set});check(checks,'ASSEMBLY-EDGE-ENDPOINTS',not missing,missing,[]);groups=components(node_set,assembly.get('edges',[]));supports={x for x in ids if x.startswith('TOWER-') or x.startswith('ANCHOR-') or x.startswith('WA-')};unsupported=[sorted(g) for g in groups if not(g&supports)];check(checks,'ASSEMBLY-SUPPORT-REACHABILITY',not unsupported,unsupported,'every connected component reaches tower/anchor');say('V13','装配图端点和支承可达性检查完成',componentCount=len(groups))
 ir=json.loads(ir_path.read_text(encoding='utf-8'));ir_ids=[x.get('componentId','') for x in ir.get('objects',[])];check(checks,'IR-CONTRACT-HASH',ir.get('contractSha256')==contract_sha,ir.get('contractSha256'),contract_sha);check(checks,'IR-COMPONENT-COVERAGE',set(ir_ids)==node_set and len(ir_ids)==len(set(ir_ids)),{'count':len(ir_ids),'unique':len(set(ir_ids)),'missing':sorted(node_set-set(ir_ids)),'extra':sorted(set(ir_ids)-node_set)},{'count':len(ids),'sameIds':True})
 bad_points=[];zero=[]
 for item in ir.get('objects',[]):
  points=item.get('pointsMm',[])
  if not points or not all(finite(p) for p in points):bad_points.append(item.get('componentId'));continue
  for i,(p1,p2) in enumerate(zip(points,points[1:])):
   if math.dist([float(x) for x in p1],[float(x) for x in p2])<=1e-8:zero.append({'componentId':item.get('componentId'),'segment':i})
 check(checks,'IR-POINTS-FINITE',not bad_points,bad_points,[]);check(checks,'IR-ZERO-LENGTH-SEGMENTS',not zero,zero,[])
 register=json.loads(node_path.read_text(encoding='utf-8'));node_ids=[n.get('nodeId','') for n in register.get('nodes',[])];bad_nodes=[n.get('nodeId') for n in register.get('nodes',[]) if not finite(n.get('xyzMm',[]))];check(checks,'INTERFACE-NODE-COUNT',len(node_ids)==150,len(node_ids),150);check(checks,'INTERFACE-NODE-UNIQUE',len(node_ids)==len(set(node_ids)) and all(node_ids),{'count':len(node_ids),'unique':len(set(node_ids))},'all unique');check(checks,'INTERFACE-NODE-FINITE',not bad_nodes,bad_nodes,[]);say('V14','FEM 几何 IR 与 150 个接口节点检查完成')
 say('V15','在独立文档中重新导入 STEP',file=str(step));step_doc=App.newDocument('StepValidation');Import.insert(str(step),step_doc.Name);step_doc.recompute();step_shapes=[o for o in step_doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull()];bad_step=[o.Name for o in step_shapes if not o.Shape.isValid()];check(checks,'STEP-REIMPORT-NONEMPTY',bool(step_shapes),len(step_shapes),'>0');check(checks,'STEP-REIMPORT-VALID',not bad_step,bad_step,[])
 if step_shapes:step_bbox=bbox(step_shapes);check(checks,'STEP-BOUNDING-BOX',bbox_delta(step_bbox,actual_bbox)<=1.0,step_bbox,{'withinMm':1.0,'fcstd':actual_bbox})
 else:check(checks,'STEP-BOUNDING-BOX',False,None,actual_bbox)
 failed=[c for c in checks if c['severity']=='CRITICAL' and not c['passed']];status='CHECKS_PASSED' if not failed else 'CHECKS_FAILED';report={'validatorRole':'N07_INDEPENDENT_DETERMINISTIC_CHECKER','gateAuthority':False,'status':status,'freecadVersion':list(App.Version()),'contractSha256':contract_sha,'fcstdSha256':sha(fc),'stepSha256':sha(step),'checkerScriptSha256':sha(Path(__file__).resolve()),'checks':checks,'criticalFailureCount':len(failed),'overallEngineeringReleaseObserved':contract.get('overallEngineeringRelease'),'scopeNote':'Geometry/traceability checks do not resolve U-WIND-001 and do not authorize engineering release.','startedAtUtc':started,'finishedAtUtc':now()};report_path=out/'n07_geometry_validation.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');receipt={'receiptVersion':'1.0.0','checker':'validate_freecad_model.py','checkerSha256':report['checkerScriptSha256'],'inputHashes':{'contract':contract_sha,'fcstd':report['fcstdSha256'],'step':report['stepSha256'],'ir':sha(ir_path),'assemblyGraph':sha(a.assembly_graph)},'outputReport':report_path.name,'outputReportSha256':sha(report_path),'status':status,'gateAuthority':False};(out/'validator_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');say('V99','独立校验完成',status=status,checkCount=len(checks),criticalFailureCount=len(failed));print(json.dumps({'status':status,'checkCount':len(checks),'criticalFailureCount':len(failed)},ensure_ascii=False,indent=2));App.closeDocument(step_doc.Name);App.closeDocument(doc.Name);return 0 if status=='CHECKS_PASSED' else 2
if __name__=='__main__':raise SystemExit(main())
