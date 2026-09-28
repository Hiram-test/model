#!/usr/bin/env python3
"""把冻结 DWG 提取结果编译为 CAD-003 唯一数值契约。

规则：每个 accepted 数值必须来自稳定 DXF handle、具名公式，或被隔离为
有界候选。本脚本只生成 N04–N06 诊断工件，没有 Gate 判定权。
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DRAWINGS=["01-扎青桥总体布置1.dwg","03-缆索布置.dwg","04-05-桥面板构造.dwg","06-11-横梁构造.dwg","12-纵梁构造.dwg","14-吊杆布置.dwg","19-索塔一般构造.dwg","26-锚碇一般构造.dwg","29-索鞍构造.dwg","32-风缆构造.dwg","33-风缆锚碇.dwg","桥跨横断面图.dwg"]
HANGER_HANDLES=["372B","3735","373F","3749","3753","372D","3737","3741","374B","3755","372F","3739","3743","374D","3757","3731","373B","3745","374F","3759","3733","373D","3747","3751","375B"]
CABLE_X_HANDLES=["1DD2","1DD4","1DD5","1DD3","1DD6","1DD1","1DD7","1DD8","1DD9","1DDA","1DDC","1DDD","1DDB","1DDE"]
CABLE_Y_HANDLES=["172F","172B","1733","176E","176B","1771","1778","177B","1757","1786","1789","1790","178D","1794"]
CABLE_YP_HANDLES=["1736","1735","1737","1774","1773","1775","177D","177E","1756","178B","178C","1783","1796","1797"]

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def say(step,msg,**data): print(json.dumps({'timeUtc':now(),'stepId':step,'message':msg,'details':data},ensure_ascii=False),flush=True)
def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): d.update(b)
 return d.hexdigest()
def rows(path:Path)->list[dict[str,str]]:
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def point(raw:str|None)->list[float]|None:
 if not raw:return None
 v=json.loads(raw);return [float(v[0]),float(v[1]),float(v[2] if len(v)>2 else 0)] if v else None
def number_token(raw:str)->float:
 m=re.search(r'[-+]?\d+(?:\.\d+)?',raw)
 if not m:raise AssertionError(f'no numeric token: {raw!r}')
 return float(m.group())

class Source:
 def __init__(self,scan:Path,geometry:Path):
  self.scan_dir=scan;self.geometry_dir=geometry
  self.report=json.loads((scan/'scan_report.json').read_text(encoding='utf-8'))
  self.texts=rows(scan/'text_index.csv');self.dims=rows(scan/'dimension_candidates.csv')
  self.geometry=geometry/'geometry_entities.jsonl.gz'
 def _one(self,data:list[dict[str,str]],source:str,handle:str)->dict[str,str]:
  hit=[r for r in data if Path(r['source']).name==source and r['handle'].upper()==handle.upper()]
  if len(hit)!=1:raise AssertionError(f'{source}:{handle} expected one row, got {len(hit)}')
  return hit[0]
 def text(self,source:str,handle:str,expected:str|None=None)->tuple[str,str]:
  r=self._one(self.texts,source,handle);v=' '.join((r['text'] or '').replace('\\P',' ').split())
  if expected is not None and v!=expected:raise AssertionError(f'{source}:{handle} text {v!r} != {expected!r}')
  return v,f"{source}:{r['layout']}:{r['type']}:{handle.upper()}:text"
 def num(self,source:str,handle:str,expected:float|None=None,tol:float=1e-6)->tuple[float,str]:
  raw,ref=self.text(source,handle);parsed=number_token(raw)
  if expected is not None and abs(parsed-expected)>tol:raise AssertionError(f'{source}:{handle} {parsed} != {expected}')
  return (float(expected) if expected is not None else parsed),ref
 def dim(self,source:str,handle:str,expected:float,tol:float=1e-6)->tuple[dict[str,Any],str]:
  r=self._one(self.dims,source,handle);raw=float(r['measurement'])
  if abs(raw-expected)>tol:raise AssertionError(f'{source}:{handle} dimension {raw} != {expected}')
  return {'measurement':float(expected),'rawMeasurement':raw,'defpoint':point(r.get('defpoint')),'defpoint2':point(r.get('defpoint2')),'defpoint3':point(r.get('defpoint3'))},f"{source}:{r['layout']}:DIMENSION:{handle.upper()}:measurement"

def fact(out:list[dict[str,Any]],fid:str,value:Any,unit:str,refs:list[str],formula:str,criticality:str='AUTHORITATIVE')->Any:
 out.append({'factId':fid,'value':value,'unit':unit,'sourceRefs':refs,'formula':formula,'criticality':criticality});return value
def write_csv(path:Path,data:list[dict[str,Any]],fields:list[str]):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--scan-dir',type=Path,required=True);ap.add_argument('--geometry-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
 a.output_dir.mkdir(parents=True,exist_ok=True);say('C00','开始读取冻结扫描证据',scanDir=str(a.scan_dir),geometryDir=str(a.geometry_dir));s=Source(a.scan_dir,a.geometry_dir)
 names=[Path(x['source_relpath']).name for x in s.report['drawings']]
 if names!=DRAWINGS or (s.report['drawing_count'],s.report['successful_conversions'],s.report['failed_conversions'])!=(12,12,0):raise AssertionError('incomplete or reordered drawing roster')
 say('C01','12 张 DWG 清单与转换状态闭合',drawingCount=12)
 F=[];ga,cable,deck,cb,lon,hanger,tower,anchor,saddle,wind,wa,section=DRAWINGS
 dspan,rspan=s.dim(ga,'44D9',82.0);span=fact(F,'F-GA-SPAN',82000.0,'mm',[rspan],'82 m ×1000');source_x0=dspan['defpoint2'][0]
 dhf,rhf=s.dim(ga,'44DA',72.0);dw,rw=s.dim(ga,'44E6',5.0);de,re_=s.dim(ga,'455C',5.0)
 pitch=fact(F,'F-GA-HANGER-PITCH',dhf['measurement']*1000/24,'mm',[rhf],'72 m /24');stations=[dw['measurement']*1000+i*pitch for i in range(25)]
 if abs(stations[-1]-(span-de['measurement']*1000))>1e-6:raise AssertionError('hanger station closure')
 daw,raw=s.dim(ga,'4465',25.548942);dae,rae=s.dim(ga,'44D4',24.237303);anchor_stations=[-daw['measurement']*1000,span+dae['measurement']*1000];fact(F,'F-GA-ANCHOR-STATIONS',anchor_stations,'mm',[raw,rae],'tower datum plus source distances')
 top,rtop=s.num(tower,'6721',4138.19);deck_el,rdeck=s.num(tower,'6743',4129.04);found,rfound=s.num(tower,'673E',4124.54);wp,rwp=s.num(tower,'66FD',4118.04);wp2,rwp2=s.num(ga,'44C6',4118.04);ep,rep=s.num(ga,'4592',4115.04)
 if wp!=wp2:raise AssertionError('west pile elevation conflict')
 topz=fact(F,'F-TOWER-TOP-Z',(top-deck_el)*1000,'mm',[rtop,rdeck],'elevation difference');foundz=fact(F,'F-TOWER-FOUNDATION-TOP-Z',(found-deck_el)*1000,'mm',[rfound,rdeck],'elevation difference');wpz=fact(F,'F-TOWER-WEST-PILE-BOTTOM-Z',(wp-deck_el)*1000,'mm',[rwp,rwp2,rdeck],'corroborated elevation difference');epz=fact(F,'F-TOWER-EAST-PILE-BOTTOM-Z',(ep-deck_el)*1000,'mm',[rep,rdeck],'elevation difference')
 tw,rtw=s.dim(tower,'6757',650);tc,rtc=s.dim(tower,'67A1',450);tcol,rtcol=s.dim(tower,'6759',100);tt,rtt=s.dim(tower,'67C5',170);tb,rtb=s.dim(tower,'13514',299.54,.02);pd,rpd=s.dim(tower,'6728',150);ar,rar=s.dim(tower,'67D5',303.125,.01)
 tower_width=tw['measurement']*10;tower_clear=tc['measurement']*10;column_width=tcol['measurement']*10
 if tower_clear+2*column_width!=tower_width:raise AssertionError('tower transverse closure')
 fact(F,'F-TOWER-TRANSVERSE-CLOSURE',{'outer':tower_width,'clear':tower_clear,'column':column_width},'mm',[rtw,rtc,rtcol],'4500+2×1000=6500')
 xs=[];ys=[];yps=[];cable_refs=[]
 for hx,hy,hp in zip(CABLE_X_HANDLES,CABLE_Y_HANDLES,CABLE_YP_HANDLES):
  x,rx=s.num(cable,hx);y,ry=s.num(cable,hy);yp,rp=s.num(cable,hp);xs.append(x);ys.append(y);yps.append(yp);cable_refs += [rx,ry,rp]
 ex=[0,500,800,1100,1400,1700,2000,2300,2600,2900,3200,3500,3800,4100];ey=[0,12.20,31.22,59.02,95.61,140.98,195.12,258.05,329.76,410.24,499.51,597.56,704.39,820.00]
 if xs!=ex or any(abs(x-y)>1e-9 for x,y in zip(ys,ey)):raise AssertionError('cable table mismatch')
 half=[{'xMmFromMidspan':x*10,'yMmAboveMidspan':y*10,'constructionYMmAboveMidspan':yp*10} for x,y,yp in zip(xs,ys,yps)];fact(F,'F-CABLE-THEORETICAL-HALF-PROFILE',half,'mm',cable_refs,'direct cm table ×10')
 eq,req=s.text(cable,'17E8')
 if '0.004878' not in eq:raise AssertionError('cable equation changed')
 coeff=fact(F,'F-CABLE-PARABOLA-COEFFICIENT',0.004878,'m/m^2',[req],'numeric token');midz=topz-8200
 mat,rmat=s.text(cable,'16B5');nums={float(x) for x in re.findall(r'\d+(?:\.\d+)?',mat)}
 if not {283.0,5.0,1670.0}<=nums:raise AssertionError('cable material row changed')
 eqd=fact(F,'F-CABLE-EQUIVALENT-DIAMETER',math.sqrt(283)*5,'mm',[rmat],'sqrt(283)×5','DISPLAY')
 full=[{'xMm':span/2-p['xMmFromMidspan'],'zMm':midz+p['yMmAboveMidspan']} for p in reversed(half[1:])]+[{'xMm':span/2,'zMm':midz}]+[{'xMm':span/2+p['xMmFromMidspan'],'zMm':midz+p['yMmAboveMidspan']} for p in half[1:]]
 if full[0]['xMm']!=0 or full[-1]['xMm']!=span:raise AssertionError('cable profile closure')
 lengths=[];hrefs=[]
 for h in HANGER_HANDLES:v,r=s.num(hanger,h);lengths.append(v);hrefs.append(r)
 expected=[8400.6,7392.6,6472.3,5639.6,4894.6,4237.3,3667.6,3185.5,2791.1,2484.4,2265.3,2133.8,2090,2133.8,2265.3,2484.4,2791.1,3185.5,3667.6,4237.3,4894.6,5639.6,6472.3,7392.6,8400.6]
 if lengths!=expected:raise AssertionError('hanger length table mismatch')
 mass,rmass=s.num(hanger,'28BE',6.31);dia,rdia=s.num(hanger,'28FC',32);upper,ru=s.text(hanger,'28C5',"%%c63.5xL'mm");lower,rl=s.text(hanger,'28C3','%%c70x500mm')
 if abs(math.sqrt(mass*162)-dia)>.05:raise AssertionError('hanger diameter conflict')
 fact(F,'F-HANGER-ROD-LENGTHS',lengths,'mm',hrefs,'direct table');fact(F,'F-HANGER-ROD-DIAMETER',dia,'mm',[rdia,rmass],'direct plus unit-mass check');fact(F,'F-HANGER-SLEEVES',{'upper':upper,'lower':lower},'text',[ru,rl],'direct table','INTERFACE')
 hangers=[];low=[]
 for i,(x,L) in enumerate(zip(stations,lengths),1):
  d=(x-span/2)/1000;uz=midz+coeff*d*d*1000;lz=uz-L;low.append(lz);hangers.append({'stationNumber':i,'crossbeamNumber':i+1,'xMm':x,'upperZMm':uz,'lowerZMm':lz,'rodLengthMm':L})
 spread=max(low)-min(low)
 if spread>12:raise AssertionError('hanger lower endpoints do not reconcile')
 fact(F,'F-HANGER-LOWER-END-RECONCILIATION',{'meanZ':sum(low)/len(low),'minZ':min(low),'maxZ':max(low),'spread':spread},'mm',hrefs+[req,rtop],'equation plus exact L','CHECK')
 width,rwidth=s.num(section,'C78',550);inner,rinner=s.num(section,'C79',470);e1,re1=s.num(section,'C80',40);e2,re2=s.num(section,'CC6',40);deck_width=width*10;deck_inner=inner*10
 if deck_inner+(e1+e2)*10!=deck_width:raise AssertionError('deck width closure')
 fact(F,'F-DECK-OVERALL-WIDTH',deck_width,'mm',[rwidth],'cm×10');fact(F,'F-DECK-INNER-WIDTH',deck_inner,'mm',[rinner],'cm×10')
 web,rweb=s.text(cb,'56A8','5500*10*416');depth,rdepth=s.num(cb,'5BA5',420);lspec,rlspec=s.text(lon,'5161','HW400*400*13*21');llen,rllen=s.num(lon,'5165',2696);plate,rplate=s.text(deck,'762F','10*1560*2690')
 fact(F,'F-CROSSBEAM-WEB',web,'spec',[rweb],'direct');fact(F,'F-CROSSBEAM-OVERALL-DEPTH',depth,'mm',[rdepth],'direct');fact(F,'F-LONGITUDINAL-BEAM-SECTION',lspec,'spec',[rlspec],'direct');fact(F,'F-LONGITUDINAL-BEAM-LENGTH',llen,'mm',[rllen],'direct');fact(F,'F-DECK-PANEL-PLATE',plate,'spec',[rplate],'direct')
 cb_stations=[2000+3000*i for i in range(27)]
 if any(abs(a-b)>1e-6 for a,b in zip(cb_stations[1:26],stations)):raise AssertionError('crossbeam station inference')
 fact(F,'F-CROSSBEAM-STATIONS',cb_stations,'mm',[rhf,rw,rllen],'beam2=first hanger; 3m pitch','BOUNDED')
 atop,ratop=s.num(anchor,'3D6A',4130.05);entry,rentry=s.num(anchor,'3D6D',4125.52);al,ral=s.dim(anchor,'1B7C',1050);awid,rawid=s.dim(anchor,'1C02',720);ah,rah=s.dim(anchor,'1B9F',700)
 atopz=(atop-deck_el)*1000;entryz=(entry-deck_el)*1000;fact(F,'F-MAIN-ANCHOR-TOP-Z',atopz,'mm',[ratop,rdeck],'elevation difference');fact(F,'F-MAIN-ANCHOR-CABLE-ENTRY-Z',entryz,'mm',[rentry,rdeck],'elevation difference');fact(F,'F-MAIN-ANCHOR-ENVELOPE',{'length':al['measurement']*10,'width':awid['measurement']*10,'height':ah['measurement']*10},'mm',[ral,rawid,rah],'cm×10','DISPLAY')
 spl,rspl=s.text(saddle,'20BB','400x30x1600');fact(F,'F-SADDLE-DISPLAY-ENVELOPE',{'length':1600,'width':400,'height':300,'raw':spl},'mm',[rspl],'material table','DISPLAY')
 wspec,rws=s.text(wind,'A047')
 if '24.0' not in wspec or '6x37' not in wspec:raise AssertionError('wind cable specification')
 wl,rwl=s.text(wind,'A018','21.91*4');wlen=float(wl.split('*')[0])*1000;note,rnote=s.text(wind,'A00C')
 if '13号' not in note or '27号' not in note:raise AssertionError('wind beam note')
 hang,rhang=s.num(wind,'A06A',35);vang,rvang=s.num(wind,'A00B',8);wat,rwat=s.num(wa,'ABF5',4125.506);wab,rwab=s.num(wa,'AB44',4122.506);wal,rwal=s.num(wa,'AAF0',622);wal2,rwal2=s.num(wa,'AC2B',622);waw,rwaw=s.num(wa,'AAEE',227);waw2,rwaw2=s.num(wa,'AB99',227)
 fact(F,'F-WIND-CABLE-LENGTH',wlen,'mm',[rwl],'m×1000');fact(F,'F-WIND-CABLE-DIAMETER',24,'mm',[rws],'parsed');fact(F,'F-WIND-CABLE-B-END-BEAMS',[13,27],'beam',[rnote],'parsed');fact(F,'F-WIND-ANGLE-BOUNDS',{'horizontalMin':hang,'verticalMin':vang},'deg',[rhang,rvang],'direct');watz=(wat-deck_el)*1000;wabz=(wab-deck_el)*1000;fact(F,'F-WIND-ANCHOR-ELEVATIONS',{'topZ':watz,'bottomZ':wabz},'mm',[rwat,rwab,rdeck],'elevation difference');fact(F,'F-WIND-ANCHOR-ENVELOPE',{'length':wal*10,'width':waw*10,'height':watz-wabz},'mm',[rwal,rwal2,rwaw,rwaw2],'corroborated cm×10','DISPLAY')
 b_z=-10-depth;vertical=watz-b_z;plan=math.sqrt(wlen*wlen-vertical*vertical);angle=35.5
 if angle<=hang:raise AssertionError('candidate angle bound')
 dx=plan*math.cos(math.radians(angle));dy=plan*math.sin(math.radians(angle));planes=[-deck_width/2,deck_width/2];wc=[]
 for side in (-1,1):
  for beam,x,sign in [(13,cb_stations[12],-1),(27,cb_stations[26],1)]:
   item={'id':f"WC-{beam}-{'L' if side<0 else 'R'}",'beamNumber':beam,'b':[x,side*deck_width/2,b_z],'a':[x+sign*dx,side*(deck_width/2+dy),watz],'lengthMm':wlen,'candidatePlanAngleDeg':angle,'status':'BOUNDED_CANDIDATE'}
   if abs(math.dist(item['a'],item['b'])-wlen)>1e-6:raise AssertionError('wind length closure')
   wc.append(item)
 uncertainties=[{'uncertaintyId':'U-WIND-001','severity':'CRITICAL','status':'OPEN_BOUNDED','subject':'wind-anchor surveyed plan coordinates','sourceRefs':[rnote,rhang,rvang],'modelTreatment':'four exact-length candidates at 35.5 degrees; not surveyed coordinates','releaseEffect':'overall engineering release remains BLOCKED'},{'uncertaintyId':'U-HANGER-001','severity':'MEDIUM','status':'BOUNDED_BY_ABSTRACTION','subject':'hanger sleeve/clevis local geometry','sourceRefs':[ru,rl]+hrefs,'modelTreatment':'exact rod plus equivalent collinear connector to crossbeam bottom','releaseEffect':'local connection/fabrication use excluded'},{'uncertaintyId':'U-CB-001','severity':'MEDIUM','status':'BOUNDED','subject':'crossbeam station numbering','sourceRefs':[rhf,rw,rllen,rnote],'modelTreatment':'27 stations X=2..80m, beams2-26 at hangers','releaseEffect':'confirm before fabrication'},{'uncertaintyId':'U-XS-001','severity':'MEDIUM','status':'BOUNDED_BY_CORROBORATION','subject':'cross-section title-block mismatch','sourceRefs':[rwidth,rweb],'modelTreatment':'only width 5500 accepted, corroborated by crossbeam web','releaseEffect':'other uncorroborated section facts excluded'}]
 representations=[{'componentGroup':'main_cables','count':2,'representation':'line_plus_equivalent_pipe','authoritativeGeometry':'theoretical table/equation and side spans','displayOnly':'area-equivalent pipe'},{'componentGroup':'hangers','count':50,'representation':'exact_rod_plus_equivalent_connector','authoritativeGeometry':'station, upper node, exact L, crossbeam interface','displayOnly':'Ø32 rod and Ø70 connector'},{'componentGroup':'crossbeams','count':27,'representation':'beam_line_plus_web_envelope','authoritativeGeometry':'bounded station series and 5500 web','displayOnly':'2mm closure flanges'},{'componentGroup':'longitudinal_beams','count':52,'representation':'beam_line_plus_H_solid','authoritativeGeometry':'26 bays × 2','displayOnly':'HW400 solid'},{'componentGroup':'deck_panels','count':78,'representation':'midsurface_plus_plate','authoritativeGeometry':'26×3 panels','displayOnly':'10mm plate'},{'componentGroup':'towers','count':2,'representation':'axis_plus_tapered_envelope','authoritativeGeometry':'elevations and transverse closure','displayOnly':'arch local detail omitted'},{'componentGroup':'main_anchorages','count':2,'representation':'entry_points_plus_envelope_box','authoritativeGeometry':'entry elevation/envelope','displayOnly':'internal/step detail omitted'},{'componentGroup':'saddles','count':4,'representation':'interface_point_plus_block','authoritativeGeometry':'tower/cable interface','displayOnly':'material-table envelope'},{'componentGroup':'wind_cables','count':4,'representation':'bounded_line_plus_pipe','authoritativeGeometry':'length/diameter/B-end','displayOnly':'candidate A position'},{'componentGroup':'wind_anchorages','count':4,'representation':'bounded_interface_plus_box','authoritativeGeometry':'elevations','displayOnly':'candidate plan position'}]
 expected_counts={x['componentGroup']:x['count'] for x in representations};edges=[]
 for bay in range(1,27):
  for side in 'LR':edges += [{'from':f'LONG-{bay:02d}-{side}','to':f'CB-{bay:02d}','path':'vertical'},{'from':f'LONG-{bay:02d}-{side}','to':f'CB-{bay+1:02d}','path':'vertical'}]
  for panel in range(1,4):edges += [{'from':f'DECK-{bay:02d}-{panel}','to':f'CB-{bay:02d}','path':'vertical'},{'from':f'DECK-{bay:02d}-{panel}','to':f'CB-{bay+1:02d}','path':'vertical'}]
 for i in range(1,26):
  for side in 'LR':edges += [{'from':f'CB-{i+1:02d}','to':f'HANGER-{i:02d}-{side}','path':'vertical'},{'from':f'HANGER-{i:02d}-{side}','to':f'MAIN-CABLE-{side}','path':'tension'}]
 for side in 'LR':edges += [{'from':f'MAIN-CABLE-{side}','to':f'SADDLE-W-{side}','path':'tension'},{'from':f'MAIN-CABLE-{side}','to':f'SADDLE-E-{side}','path':'tension'},{'from':f'SADDLE-W-{side}','to':'TOWER-W','path':'bearing'},{'from':f'SADDLE-E-{side}','to':'TOWER-E','path':'bearing'},{'from':f'MAIN-CABLE-{side}','to':'ANCHOR-W','path':'side_span'},{'from':f'MAIN-CABLE-{side}','to':'ANCHOR-E','path':'side_span'}]
 for x in wc:
  side='L' if x['id'].endswith('L') else 'R';edges += [{'from':f"CB-{x['beamNumber']:02d}",'to':x['id'],'path':'lateral'},{'from':x['id'],'to':f"WA-{x['beamNumber']:02d}-{side}",'path':'lateral_tension'}]
 params={'spanMm':span,'towerStationsMm':[0,span],'mainAnchorStationsMm':anchor_stations,'deckWidthMm':deck_width,'deckInnerWidthMm':deck_inner,'deckTopZMm':0,'deckPanel':{'lengthMm':2690,'widthMm':1560,'thicknessMm':10,'panelsAcross':3,'bayEndClearanceMm':155},'crossbeam':{'stationsMm':cb_stations,'lengthMm':5500,'webThicknessMm':10,'webDepthMm':416,'overallDepthMm':depth,'topZMm':-10,'bottomZMm':-10-depth,'displayLongitudinalWidthMm':200},'longitudinalBeam':{'pieceLengthMm':llen,'section':{'depthMm':400,'flangeWidthMm':400,'webThicknessMm':13,'flangeThicknessMm':21},'yCentersMm':[-2550,2550]},'tower':{'topZMm':topz,'foundationTopZMm':foundz,'westPileBottomZMm':wpz,'eastPileBottomZMm':epz,'outerWidthMm':tower_width,'clearWidthMm':tower_clear,'columnTransverseWidthMm':column_width,'columnTopLongitudinalMm':tt['measurement']*10,'columnBaseLongitudinalMm':tb['measurement']*10,'pileDiameterMm':pd['measurement']*10,'archRadiusMm':ar['measurement']*10},'mainCable':{'planesYMm':planes,'towerZMm':topz,'midspanZMm':midz,'halfProfile':half,'fullProfile':full,'parabolaCoefficientMPerM2':coeff,'wireCount':283,'wireDiameterMm':5,'equivalentDiameterMm':eqd,'strengthMPa':1670,'anchorEntryZMm':entryz},'hangers':{'planesYMm':planes,'rodDiameterMm':dia,'lowerSleeveDiameterMm':70,'stations':hangers,'rodLowerReferenceZMm':sum(low)/len(low),'crossbeamConnectionZMm':-10-depth,'interfaceTreatment':'exact rod plus equivalent connector; U-HANGER-001'},'mainAnchorage':{'topZMm':atopz,'entryZMm':entryz,'lengthMm':al['measurement']*10,'widthMm':awid['measurement']*10,'heightMm':ah['measurement']*10},'saddle':{'lengthMm':1600,'widthMm':400,'heightMm':300},'windCable':{'diameterMm':24,'lengthMm':wlen,'candidatePlanAngleDeg':angle,'minimumHorizontalAngleDeg':hang,'minimumVerticalAngleDeg':vang,'cables':wc},'windAnchorage':{'topZMm':watz,'bottomZMm':wabz,'lengthMm':wal*10,'widthMm':waw*10,'heightMm':watz-wabz}}
 contract={'contractVersion':'1.0.0','projectId':'ZHAQING-SUSPENSION-BRIDGE','modelId':'CAD-003','scope':'source-bound overall bridge reference/FEM-abstraction CAD; not fabrication release','gateAuthority':False,'overallEngineeringRelease':'BLOCKED','blockReason':'U-WIND-001 surveyed wind-anchor plan coordinates remain open','coordinateSystem':{'lengthUnit':'mm','xAxis':'longitudinal west-to-east','yAxis':'transverse, positive right looking east','zAxis':'up','origin':'west tower centerline, bridge centerline, deck elevation 4129.04m','absoluteDeckElevationM':deck_el,'sourceToProject':{'overallArrangementSourceXAtProjectZero':source_x0,'scaleMmPerSourceUnit':1000}},'parameters':params,'expectedCounts':expected_counts,'facts':F,'uncertainties':uncertainties,'drawingManifest':[{'sourceRelpath':x['source_relpath'],'sha256':x['source_sha256'],'bytes':x['source_bytes'],'dxfSha256':x.get('dxf_sha256'),'conversionStatus':x.get('conversion_status')} for x in s.report['drawings']],'inputs':{'scanReportSha256':sha(a.scan_dir/'scan_report.json'),'dimensionCsvSha256':sha(a.scan_dir/'dimension_candidates.csv'),'textCsvSha256':sha(a.scan_dir/'text_index.csv'),'geometryJsonlGzSha256':sha(s.geometry)}}
 cp=a.output_dir/'model_contract.json';cp.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');csha=sha(cp);(a.output_dir/'model_contract.sha256').write_text(f'{csha}  model_contract.json\n',encoding='utf-8')
 write_csv(a.output_dir/'representation_contract.csv',representations,['componentGroup','count','representation','authoritativeGeometry','displayOnly']);(a.output_dir/'assembly_graph.json').write_text(json.dumps({'graphVersion':'1.0.0','nodesExpectedByGroup':expected_counts,'edges':edges},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(a.output_dir/'uncertainty_register.json').write_text(json.dumps({'registerVersion':'1.0.0','items':uncertainties},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (a.output_dir/'n04_reconciliation_report.json').write_text(json.dumps({'adapterRole':'N04_RECONCILIATION_DIAGNOSTIC','gateAuthority':False,'coordinateClosure':'OK','dimensionClosure':{'span':'OK','hangerField':'OK','towerWidth':'OK','deckWidth':'OK','hangerLowerEndSpreadMm':spread},'criticalOpenUncertainties':['U-WIND-001'],'contractSha256':csha},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (a.output_dir/'n05_assembly_inventory.json').write_text(json.dumps({'adapterRole':'N05_ASSEMBLY_DIAGNOSTIC','gateAuthority':False,'expectedCounts':expected_counts,'edgeCount':len(edges),'assemblyGraph':'assembly_graph.json'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(a.output_dir/'n06_abstraction_report.json').write_text(json.dumps({'adapterRole':'N06_ABSTRACTION_DIAGNOSTIC','gateAuthority':False,'componentGroupCount':len(representations),'exactlyOneDispositionPerGroup':True,'representationContract':'representation_contract.csv','boundedGroups':['crossbeams','hangers','wind_cables','wind_anchorages']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 record={'recordVersion':'1.0.0','generatedAtUtc':now(),'scriptSha256':sha(Path(__file__)),'inputHashes':contract['inputs'],'contractSha256':csha,'factCount':len(F),'expectedCounts':expected_counts,'assemblyEdgeCount':len(edges),'criticalOpenUncertainties':['U-WIND-001']};(a.output_dir/'contract_compile_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 say('C99','模型契约编译完成',contract=str(cp),contractSha256=csha,factCount=len(F),expectedCounts=expected_counts,criticalOpen=['U-WIND-001']);return 0
if __name__=='__main__':raise SystemExit(main())
