#!/usr/bin/env python3
"""在 FreeCADCmd 中建立扎青吊桥 CAD-003，并导出显示实体 STEP。

数值工程输入只能来自 ``model_contract.json``。FreeCAD 文档严格分层：
1. 权威参考几何：中心线、中面、接口点；
2. 非权威显示实体：便于查看和 STEP 交换的外包络。

本 builder 没有 Gate 判定权；它必须保留契约中的 BLOCKED 发布状态。
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import FreeCAD as App
import Part
import Import

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):d.update(b)
 return d.hexdigest()
def env_path(name:str)->Path|None:
 value=os.environ.get(name);return Path(value) if value else None

def clean(value:str)->str:return re.sub(r'[^A-Za-z0-9_]','_',value.replace('-','_'))
def vec(p:Iterable[float])->App.Vector:
 v=list(p);return App.Vector(float(v[0]),float(v[1]),float(v[2]))
def line(a:Iterable[float],b:Iterable[float]):
 p,q=vec(a),vec(b)
 if (q-p).Length<=1e-9:raise ValueError(f'zero-length line {a}->{b}')
 return Part.makeLine(p,q)
def polyline(points:list[list[float]]):
 if len(points)<2:raise ValueError('polyline needs >=2 points')
 return Part.makePolygon([vec(p) for p in points])
def compound(shapes:Iterable[Any]):
 values=[s for s in shapes if s is not None and not s.isNull()]
 if not values:return Part.Shape()
 return values[0] if len(values)==1 else Part.makeCompound(values)
def cylinder(a:Iterable[float],b:Iterable[float],radius:float):
 p,q=vec(a),vec(b);direction=q-p
 if direction.Length<=1e-9:raise ValueError(f'zero-length cylinder {a}->{b}')
 return Part.makeCylinder(float(radius),direction.Length,p,direction)
def pipe(points:list[list[float]],radius:float):return compound(cylinder(a,b,radius) for a,b in zip(points,points[1:]))
def rectangle_face(x0:float,y0:float,z:float,length:float,width:float):
 pts=[App.Vector(x0,y0,z),App.Vector(x0+length,y0,z),App.Vector(x0+length,y0+width,z),App.Vector(x0,y0+width,z),App.Vector(x0,y0,z)]
 return Part.Face(Part.makePolygon(pts))
def h_beam(x0:float,y:float,top_z:float,length:float,s:dict[str,float]):
 d=float(s['depthMm']);fw=float(s['flangeWidthMm']);wt=float(s['webThicknessMm']);ft=float(s['flangeThicknessMm']);bottom=top_z-d;y0=y-fw/2
 return compound([Part.makeBox(length,fw,ft,App.Vector(x0,y0,bottom)),Part.makeBox(length,fw,ft,App.Vector(x0,y0,top_z-ft)),Part.makeBox(length,wt,d-2*ft,App.Vector(x0,y-wt/2,bottom+ft))])
def crossbeam_solid(x:float,y0:float,top_z:float,p:dict[str,float]):
 length=float(p['lengthMm']);overall=float(p['overallDepthMm']);web_t=float(p['webThicknessMm']);web_d=float(p['webDepthMm']);show_w=float(p['displayLongitudinalWidthMm']);bottom=top_z-overall;ft=max(.1,(overall-web_d)/2)
 return compound([Part.makeBox(web_t,length,web_d,App.Vector(x-web_t/2,y0,bottom+ft)),Part.makeBox(show_w,length,ft,App.Vector(x-show_w/2,y0,bottom)),Part.makeBox(show_w,length,ft,App.Vector(x-show_w/2,y0,top_z-ft))])
def tapered_column(x:float,y:float,z0:float,z1:float,base_x:float,top_x:float,width_y:float):
 y0=y-width_y/2;pts=[App.Vector(x-base_x/2,y0,z0),App.Vector(x+base_x/2,y0,z0),App.Vector(x+top_x/2,y0,z1),App.Vector(x-top_x/2,y0,z1),App.Vector(x-base_x/2,y0,z0)]
 return Part.Face(Part.makePolygon(pts)).extrude(App.Vector(0,width_y,0))

class Journal:
 def __init__(self):self.started=now();self.events=[]
 def add(self,step,msg,**details):
  rec={'timeUtc':now(),'stepId':step,'message':msg,'details':details};self.events.append(rec);print(json.dumps(rec,ensure_ascii=False),flush=True)
 def write(self,path:Path,status:str):path.write_text(json.dumps({'journalVersion':'1.0.0','startedAtUtc':self.started,'finishedAtUtc':now(),'status':status,'events':self.events},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def add_string(obj,name,value,group='Traceability'):
 obj.addProperty('App::PropertyString',name,group);setattr(obj,name,str(value))
def add_float(obj,name,value,group='Engineering'):
 obj.addProperty('App::PropertyFloat',name,group);setattr(obj,name,float(value))
def add_bool(obj,name,value,group='Traceability'):
 obj.addProperty('App::PropertyBool',name,group);setattr(obj,name,bool(value))
def decorate(obj,stable_id,component_group,role,source_refs,evidence_state,is_root,parent_stable_id='',representation=''):
 obj.Label=stable_id if is_root else f'{stable_id} [{role}]';add_string(obj,'StableId',stable_id);add_string(obj,'ComponentGroup',component_group);add_string(obj,'RepresentationRole',role);add_string(obj,'EvidenceState',evidence_state);add_string(obj,'SourceRefs',';'.join(source_refs));add_string(obj,'ParentStableId',parent_stable_id);add_string(obj,'Representation',representation);add_bool(obj,'IsComponentRoot',is_root);add_bool(obj,'Authoritative',role in {'REFERENCE','BOUNDED_REFERENCE'})
def add_part(doc,group,name,shape,**metadata):
 obj=doc.addObject('Part::Feature',clean(name));obj.Shape=shape;decorate(obj,**metadata);group.addObject(obj);return obj
def metadata(doc,group,name,values):
 obj=doc.addObject('App::Feature',clean(name));obj.Label=name
 for key,value in values.items():add_string(obj,key,json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else value,'Metadata')
 group.addObject(obj);return obj
def refs(contract,*fact_ids):
 wanted=set(fact_ids);out=[]
 for f in contract.get('facts',[]):
  if f.get('factId') in wanted:out.extend(f.get('sourceRefs',[]))
 return sorted(dict.fromkeys(out))
def ir(cid,group,kind,points,source_refs,state,extra=None):
 item={'componentId':cid,'componentGroup':group,'geometryType':kind,'coordinateSystemId':'CS-ZQ-001','pointsMm':points,'sourceRefs':source_refs,'evidenceState':state}
 if extra:item.update(extra)
 return item

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--contract',type=Path,default=env_path('CAD003_CONTRACT'));ap.add_argument('--assembly-graph',type=Path,default=env_path('CAD003_ASSEMBLY_GRAPH'));ap.add_argument('--output-dir',type=Path,default=env_path('CAD003_OUTPUT_DIR'));a=ap.parse_args()
 if not all((a.contract,a.assembly_graph,a.output_dir)):ap.error('contract, assembly graph and output dir required')
 out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True);journal=Journal();journal.add('B00','FreeCAD 建模进程启动',freecadVersion=list(App.Version()))
 contract_path=a.contract.resolve();contract=json.loads(contract_path.read_text(encoding='utf-8'));contract_sha=sha(contract_path);assembly=json.loads(a.assembly_graph.read_text(encoding='utf-8'))
 sidecar=contract_path.with_suffix('.sha256')
 if sidecar.exists() and sidecar.read_text(encoding='utf-8').split()[0]!=contract_sha:raise RuntimeError('contract SHA sidecar mismatch')
 if contract.get('modelId')!='CAD-003' or contract.get('gateAuthority') is not False:raise RuntimeError('unexpected/self-authorizing contract')
 journal.add('B01','数值契约与装配图已冻结',contractSha256=contract_sha,engineeringRelease=contract['overallEngineeringRelease'])
 p=contract['parameters'];doc=App.newDocument('Zhaqing_CAD_003')
 g0=doc.addObject('App::DocumentObjectGroup','G00_SourceEvidence');g1=doc.addObject('App::DocumentObjectGroup','G10_AuthoritativeReferenceGeometry');g2=doc.addObject('App::DocumentObjectGroup','G20_DisplaySolids');g3=doc.addObject('App::DocumentObjectGroup','G30_InterfaceNodes');g4=doc.addObject('App::DocumentObjectGroup','G40_BoundedConstructionCandidates')
 metadata(doc,g0,'CAD-003 Contract Metadata',{'ProjectId':contract['projectId'],'ModelId':contract['modelId'],'ContractSha256':contract_sha,'OverallEngineeringRelease':contract['overallEngineeringRelease'],'BlockReason':contract['blockReason'],'CoordinateSystem':contract['coordinateSystem'],'GateAuthority':False})
 for item in contract.get('uncertainties',[]):metadata(doc,g4,item['uncertaintyId'],item)
 roots=[];displays=[];objects=[];nodes=[]
 def root(name,shape,group,source,state='ACCEPTED',representation='reference'):
  obj=add_part(doc,g1,name,shape,stable_id=name,component_group=group,role='BOUNDED_REFERENCE' if state.startswith('OPEN') else 'REFERENCE',source_refs=source,evidence_state=state,is_root=True,representation=representation);roots.append(obj);return obj
 def display(name,shape,group,source,parent,state='ACCEPTED',representation='display_solid'):
  obj=add_part(doc,g2,name+'_DISPLAY',shape,stable_id=name+'-DISPLAY',component_group=group,role='DISPLAY_SOLID',source_refs=source,evidence_state=state,is_root=False,parent_stable_id=parent,representation=representation);displays.append(obj);return obj

 # 01：桥面板。权威对象是板中面；10 mm 实体仅供显示/STEP。
 journal.add('B10','建立 78 块桥面板中面与显示板')
 deck=p['deckPanel'];cb=p['crossbeam'];deck_refs=refs(contract,'F-DECK-PANEL-PLATE','F-DECK-OVERALL-WIDTH','F-DECK-INNER-WIDTH');across=deck['panelsAcross']*deck['widthMm'];ystart=-across/2
 for bay in range(1,27):
  x0=cb['stationsMm'][bay-1]+deck['bayEndClearanceMm']
  for panel in range(1,4):
   sid=f'DECK-{bay:02d}-{panel}';y0=ystart+(panel-1)*deck['widthMm'];zm=-deck['thicknessMm']/2
   o=root(sid,rectangle_face(x0,y0,zm,deck['lengthMm'],deck['widthMm']),'deck_panels',deck_refs,representation='plate_midsurface');add_float(o,'LengthMm',deck['lengthMm']);add_float(o,'WidthMm',deck['widthMm']);add_float(o,'ThicknessMm',deck['thicknessMm'])
   display(sid,Part.makeBox(deck['lengthMm'],deck['widthMm'],deck['thicknessMm'],App.Vector(x0,y0,-deck['thicknessMm'])),'deck_panels',deck_refs,sid,representation='source_plate_solid')
   objects.append(ir(sid,'deck_panels','midsurface',[[x0,y0,zm],[x0+deck['lengthMm'],y0,zm],[x0+deck['lengthMm'],y0+deck['widthMm'],zm],[x0,y0+deck['widthMm'],zm]],deck_refs,'ACCEPTED',{'thicknessMm':deck['thicknessMm']}))

 # 02：横梁。站点序列是有界解释，因此状态保持 BOUNDED。
 journal.add('B11','建立 27 根横梁参考线与外包络')
 cb_refs=refs(contract,'F-CROSSBEAM-WEB','F-CROSSBEAM-OVERALL-DEPTH','F-CROSSBEAM-STATIONS');y0=-cb['lengthMm']/2;zc=(cb['topZMm']+cb['bottomZMm'])/2
 for n,x in enumerate(cb['stationsMm'],1):
  sid=f'CB-{n:02d}';pts=[[x,y0,zc],[x,-y0,zc]];o=root(sid,line(*pts),'crossbeams',cb_refs,'BOUNDED','beam_reference_line');add_float(o,'StationMm',x);add_float(o,'LengthMm',cb['lengthMm']);add_float(o,'DepthMm',cb['overallDepthMm']);display(sid,crossbeam_solid(x,y0,cb['topZMm'],cb),'crossbeams',cb_refs,sid,'BOUNDED','source_web_plus_envelope_flange');objects.append(ir(sid,'crossbeams','reference_line',pts,cb_refs,'BOUNDED',{'stationMm':x,'depthMm':cb['overallDepthMm']}))

 # 03：纵梁。每个 3 m 跨段左右各一根 HW400。
 journal.add('B12','建立 52 根纵梁参考线与 H 型显示实体')
 lp=p['longitudinalBeam'];long_refs=refs(contract,'F-LONGITUDINAL-BEAM-SECTION','F-LONGITUDINAL-BEAM-LENGTH','F-CROSSBEAM-STATIONS');top_z=-deck['thicknessMm']
 for bay in range(1,27):
  left,right=cb['stationsMm'][bay-1],cb['stationsMm'][bay];x0=left+(right-left-lp['pieceLengthMm'])/2
  for side,y in zip(('L','R'),lp['yCentersMm']):
   sid=f'LONG-{bay:02d}-{side}';za=top_z-lp['section']['depthMm']/2;pts=[[x0,y,za],[x0+lp['pieceLengthMm'],y,za]];o=root(sid,line(*pts),'longitudinal_beams',long_refs,representation='beam_reference_line');add_float(o,'LengthMm',lp['pieceLengthMm']);add_string(o,'Section','HW400x400x13x21','Engineering');display(sid,h_beam(x0,y,top_z,lp['pieceLengthMm'],lp['section']),'longitudinal_beams',long_refs,sid,representation='source_H_section_solid');objects.append(ir(sid,'longitudinal_beams','reference_line',pts,long_refs,'ACCEPTED',{'section':'HW400x400x13x21'}))

 # 04：索塔。参考几何保存柱/桩轴；实体只表达图纸闭合的锥形柱和桩径。
 journal.add('B13','建立两座索塔轴线与有依据的显示外包络')
 tower=p['tower'];tower_refs=refs(contract,'F-TOWER-TOP-Z','F-TOWER-FOUNDATION-TOP-Z','F-TOWER-WEST-PILE-BOTTOM-Z','F-TOWER-EAST-PILE-BOTTOM-Z','F-TOWER-TRANSVERSE-CLOSURE');ys=[-tower['outerWidthMm']/2+tower['columnTransverseWidthMm']/2,tower['outerWidthMm']/2-tower['columnTransverseWidthMm']/2]
 for side,x,pile_bottom in zip(('W','E'),p['towerStationsMm'],(tower['westPileBottomZMm'],tower['eastPileBottomZMm'])):
  sid=f'TOWER-{side}';axes=[line([x,y,pile_bottom],[x,y,tower['topZMm']]) for y in ys]+[line([x,ys[0],tower['topZMm']],[x,ys[1],tower['topZMm']])];o=root(sid,compound(axes),'towers',tower_refs,representation='column_and_pile_axes');add_float(o,'StationMm',x);add_float(o,'TopZMm',tower['topZMm']);add_float(o,'PileBottomZMm',pile_bottom)
  solids=[]
  for y in ys:
   solids.append(tapered_column(x,y,tower['foundationTopZMm'],tower['topZMm'],tower['columnBaseLongitudinalMm'],tower['columnTopLongitudinalMm'],tower['columnTransverseWidthMm']));solids.append(Part.makeCylinder(tower['pileDiameterMm']/2,tower['foundationTopZMm']-pile_bottom,App.Vector(x,y,pile_bottom),App.Vector(0,0,1)))
  display(sid,compound(solids),'towers',tower_refs,sid,representation='tapered_columns_and_source_diameter_piles');objects.append(ir(sid,'towers','axis_system',[[x,y,pile_bottom] for y in ys]+[[x,y,tower['topZMm']] for y in ys],tower_refs,'ACCEPTED',{'archRadiusMm':tower['archRadiusMm']}))

 # 05：主缆锚碇和索鞍。内部构造未闭合，只建立接口点与外包络。
 journal.add('B14','建立主缆锚碇接口及四个索鞍接口')
 anch=p['mainAnchorage'];anchor_refs=refs(contract,'F-GA-ANCHOR-STATIONS','F-MAIN-ANCHOR-TOP-Z','F-MAIN-ANCHOR-CABLE-ENTRY-Z','F-MAIN-ANCHOR-ENVELOPE');planes=p['mainCable']['planesYMm']
 for side,station in zip(('W','E'),p['mainAnchorStationsMm']):
  sid=f'ANCHOR-{side}';eps=[[station,y,anch['entryZMm']] for y in planes];o=root(sid,compound(Part.Vertex(vec(q)) for q in eps),'main_anchorages',anchor_refs,representation='cable_entry_points_and_source_envelope');add_float(o,'StationMm',station);add_float(o,'EntryZMm',anch['entryZMm']);x0=station-anch['lengthMm'] if side=='W' else station;display(sid,Part.makeBox(anch['lengthMm'],anch['widthMm'],anch['heightMm'],App.Vector(x0,-anch['widthMm']/2,anch['topZMm']-anch['heightMm'])),'main_anchorages',anchor_refs,sid,representation='source_envelope_box_internal_detail_omitted');objects.append(ir(sid,'main_anchorages','entry_points',eps,anchor_refs,'ACCEPTED',{'envelopeMm':[anch['lengthMm'],anch['widthMm'],anch['heightMm']]}))
 saddle=p['saddle'];saddle_refs=refs(contract,'F-SADDLE-DISPLAY-ENVELOPE','F-TOWER-TOP-Z')
 for ts,x in zip(('W','E'),p['towerStationsMm']):
  for cs,y in zip(('L','R'),planes):
   sid=f'SADDLE-{ts}-{cs}';pt=[x,y,tower['topZMm']];root(sid,Part.Vertex(vec(pt)),'saddles',saddle_refs,representation='tower_cable_interface_point');display(sid,Part.makeBox(saddle['lengthMm'],saddle['widthMm'],saddle['heightMm'],App.Vector(x-saddle['lengthMm']/2,y-saddle['widthMm']/2,tower['topZMm']-saddle['heightMm']/2)),'saddles',saddle_refs,sid,representation='material_table_envelope');objects.append(ir(sid,'saddles','interface_point',[pt],saddle_refs,'ACCEPTED'))

 # 06：主缆。中心跨来自控制点表，边跨只用锚点和塔顶接口作直线显示。
 journal.add('B15','建立两条主缆参考折线与面积等效显示管')
 cable=p['mainCable'];cable_refs=refs(contract,'F-CABLE-THEORETICAL-HALF-PROFILE','F-CABLE-PARABOLA-COEFFICIENT','F-CABLE-EQUIVALENT-DIAMETER','F-MAIN-ANCHOR-CABLE-ENTRY-Z','F-GA-ANCHOR-STATIONS')
 for side,y in zip(('L','R'),planes):
  sid=f'MAIN-CABLE-{side}';central=[[q['xMm'],y,q['zMm']] for q in cable['fullProfile']];pts=[[p['mainAnchorStationsMm'][0],y,cable['anchorEntryZMm']]]+central+[[p['mainAnchorStationsMm'][1],y,cable['anchorEntryZMm']]];o=root(sid,polyline(pts),'main_cables',cable_refs,representation='source_table_polyline_plus_side_spans');add_float(o,'EquivalentDiameterMm',cable['equivalentDiameterMm']);add_float(o,'StrengthMPa',cable['strengthMPa']);display(sid,pipe(pts,cable['equivalentDiameterMm']/2),'main_cables',cable_refs,sid,representation='area_equivalent_segmented_pipe');objects.append(ir(sid,'main_cables','polyline',pts,cable_refs,'ACCEPTED',{'equivalentDiameterMm':cable['equivalentDiameterMm'],'tensionOnlyRequired':True}))

 # 07：吊杆。精确杆长与下端等效连接段明确分开，避免把套筒细节画成已确认装配。
 journal.add('B16','建立 50 根精确杆长吊杆与显式下端等效连接段')
 hp=p['hangers'];hanger_refs=refs(contract,'F-HANGER-ROD-LENGTHS','F-HANGER-ROD-DIAMETER','F-HANGER-SLEEVES','F-HANGER-LOWER-END-RECONCILIATION','F-CABLE-PARABOLA-COEFFICIENT')
 for st in hp['stations']:
  for side,y in zip(('L','R'),hp['planesYMm']):
   sid=f"HANGER-{int(st['stationNumber']):02d}-{side}";upper=[st['xMm'],y,st['upperZMm']];rod_lower=[st['xMm'],y,st['lowerZMm']];conn=[st['xMm'],y,hp['crossbeamConnectionZMm']];o=root(sid,compound([line(upper,rod_lower),line(rod_lower,conn)]),'hangers',hanger_refs,'BOUNDED','exact_rod_plus_equivalent_collinear_connector');add_float(o,'RodLengthMm',st['rodLengthMm']);add_float(o,'EquivalentConnectorLengthMm',abs(st['lowerZMm']-hp['crossbeamConnectionZMm']));display(sid,compound([cylinder(upper,rod_lower,hp['rodDiameterMm']/2),cylinder(rod_lower,conn,hp['lowerSleeveDiameterMm']/2)]),'hangers',hanger_refs,sid,'BOUNDED','source_diameter_rod_plus_equivalent_lower_sleeve');objects.append(ir(sid,'hangers','rod_and_interface_line',[upper,rod_lower,conn],hanger_refs,'BOUNDED',{'rodLengthMm':st['rodLengthMm'],'tensionOnlyRequired':True,'interfaceTreatment':hp['interfaceTreatment']}));nodes += [{'nodeId':sid+'-UPPER','componentId':sid,'role':'main_cable_interface','xyzMm':upper},{'nodeId':sid+'-ROD-LOWER','componentId':sid,'role':'exact_rod_endpoint','xyzMm':rod_lower},{'nodeId':sid+'-CB','componentId':sid,'role':'crossbeam_interface','xyzMm':conn}]

 # 08：风缆/风缆锚碇。只建立精确长度候选，所有对象显式标记 U-WIND-001。
 journal.add('B17','建立 4 条风缆和 4 个风缆锚碇有界候选')
 wind=p['windCable'];wind_refs=refs(contract,'F-WIND-CABLE-LENGTH','F-WIND-CABLE-DIAMETER','F-WIND-CABLE-B-END-BEAMS','F-WIND-ANGLE-BOUNDS');wa=p['windAnchorage'];wa_refs=refs(contract,'F-WIND-ANCHOR-ELEVATIONS','F-WIND-ANCHOR-ENVELOPE')
 for item in wind['cables']:
  sid=item['id'];pts=[item['b'],item['a']];o=root(sid,line(*pts),'wind_cables',wind_refs,'OPEN_BOUNDED','exact_length_candidate_line');add_float(o,'LengthMm',item['lengthMm']);add_float(o,'CandidatePlanAngleDeg',item['candidatePlanAngleDeg']);add_string(o,'BoundedBy','U-WIND-001','Engineering');display(sid,cylinder(*pts,wind['diameterMm']/2),'wind_cables',wind_refs,sid,'OPEN_BOUNDED','source_diameter_candidate_pipe');objects.append(ir(sid,'wind_cables','bounded_line',pts,wind_refs,'OPEN_BOUNDED',{'lengthMm':item['lengthMm'],'boundedBy':'U-WIND-001','tensionOnlyRequired':True}))
  suffix='L' if sid.endswith('L') else 'R';aid=f"WA-{int(item['beamNumber']):02d}-{suffix}";pt=item['a'];ao=root(aid,Part.Vertex(vec(pt)),'wind_anchorages',wa_refs,'OPEN_BOUNDED','candidate_anchor_top_interface');add_string(ao,'BoundedBy','U-WIND-001','Engineering');x0=pt[0]-wa['lengthMm'] if int(item['beamNumber'])==13 else pt[0];display(aid,Part.makeBox(wa['lengthMm'],wa['widthMm'],wa['heightMm'],App.Vector(x0,pt[1]-wa['widthMm']/2,wa['bottomZMm'])),'wind_anchorages',wa_refs,aid,'OPEN_BOUNDED','source_envelope_at_candidate_plan_position');objects.append(ir(aid,'wind_anchorages','bounded_interface_point',[pt],wa_refs,'OPEN_BOUNDED',{'envelopeMm':[wa['lengthMm'],wa['widthMm'],wa['heightMm']],'boundedBy':'U-WIND-001'}))

 # 09：把 150 个接口点压缩成一个 FreeCAD compound，同时保存可审计 JSON register。
 journal.add('B18','创建吊杆接口节点登记',nodeCount=len(nodes));io=add_part(doc,g3,'InterfaceNodeRegister',compound(Part.Vertex(vec(n['xyzMm'])) for n in nodes),stable_id='INTERFACE-NODE-REGISTER',component_group='interface_nodes',role='REFERENCE',source_refs=[],evidence_state='MIXED',is_root=False,representation='compound_vertices_external_JSON_authoritative');add_string(io,'RegisterFile','interface_nodes.json','Metadata');add_float(io,'NodeCount',len(nodes),'Metadata')
 doc.recompute();journal.add('B19','FreeCAD recompute 完成',rootCount=len(roots),displayCount=len(displays),documentObjectCount=len(doc.Objects))
 fc=out/'Zhaqing_CAD-003.FCStd';step=out/'Zhaqing_CAD-003-display.step';doc.saveAs(str(fc));journal.add('B20','FCStd 已保存',path=str(fc),bytes=fc.stat().st_size);Import.export(displays,str(step));journal.add('B21','STEP 已导出',path=str(step),objectCount=len(displays),bytes=step.stat().st_size)
 node_path=out/'interface_nodes.json';node_path.write_text(json.dumps({'registerVersion':'1.0.0','coordinateSystemId':'CS-ZQ-001','nodes':nodes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 ir_path=out/'fem_geometry_ir.json';ir_path.write_text(json.dumps({'irVersion':'1.0.0','projectId':contract['projectId'],'modelId':contract['modelId'],'coordinateSystem':contract['coordinateSystem'],'contractSha256':contract_sha,'gateAuthority':False,'engineeringRelease':contract['overallEngineeringRelease'],'objects':objects,'interfaceNodeRegister':node_path.name,'assemblyGraphSha256':sha(a.assembly_graph)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 boxes=[o.Shape.BoundBox for o in displays if hasattr(o,'Shape') and not o.Shape.isNull()];bbox={'xmin':min(b.XMin for b in boxes),'xmax':max(b.XMax for b in boxes),'ymin':min(b.YMin for b in boxes),'ymax':max(b.YMax for b in boxes),'zmin':min(b.ZMin for b in boxes),'zmax':max(b.ZMax for b in boxes)};counts={}
 for o in roots:counts[o.ComponentGroup]=counts.get(o.ComponentGroup,0)+1
 manifest={'builderRole':'FREECAD_CAD003_BUILDER_NO_GATE_AUTHORITY','gateAuthority':False,'freecadVersion':list(App.Version()),'contractSha256':contract_sha,'expectedCounts':contract['expectedCounts'],'rootCounts':counts,'rootObjectCount':len(roots),'displayObjectCount':len(displays),'documentObjectCount':len(doc.Objects),'displayBoundingBoxMm':bbox,'files':{fc.name:sha(fc),step.name:sha(step),ir_path.name:sha(ir_path),node_path.name:sha(node_path)},'overallEngineeringRelease':contract['overallEngineeringRelease'],'blockReason':contract['blockReason'],'assemblyEdgeCount':len(assembly.get('edges',[]))}
 (out/'freecad_build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');journal.add('B22','构建清单和所有哈希已写入',files=manifest['files']);journal.write(out/'freecad_build_journal.json','BUILT_AWAITING_INDEPENDENT_VALIDATION');print(json.dumps(manifest,ensure_ascii=False,indent=2));App.closeDocument(doc.Name);return 0
if __name__=='__main__':raise SystemExit(main())
