from pathlib import Path  # Operate only on this newly recovered set of original inputs.
import json, re, subprocess, numpy as np, collections  # Inspect source-state definitions and actual solver diagnostics.
ROOT=Path(__file__).parent; OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)  # Save all new diagnostic outputs in the calculation branch.
log=(ROOT/'unit_string/solver.log').read_text(errors='replace')  # Read the actual failed native invocation, not a guessed error explanation.
(OUT/'native_string_diagnostic.txt').write_text(log); print(log[-7000:],flush=True)  # Preserve and expose the complete native input failure.
a=json.loads((ROOT/'sources/mct_sections.json').read_text()); sections=a['sections']; nodes={int(k):np.array(v)/1000 for k,v in a['nodes'].items()}; elems={int(k):v for k,v in a['elements'].items()}  # Decode the immutable MCT in metre units.
def ids(value):  # Expand the MCT integer-list syntax without inventing node ranges.
    out=[]  # Accumulate exactly listed identifiers.
    for token in value.split():  # MCT range lists are whitespace delimited.
        if 'to' in token.lower():  # Expand inclusive source ranges.
            ends=re.split('to',token,flags=re.I);out.extend(range(int(ends[0]),int(ends[1])+1))  # Preserve range endpoint inclusion.
        else: out.append(int(token))  # Preserve explicitly listed identifiers.
    return out  # Return the source sequence.
truss=[]  # List all actual upper/lower attachment pairs from the source model.
for i,e in elems.items():  # Inspect real topology rather than identifying connections by coordinate proximity.
    if e[0]=='TRUSS': truss.append({'eid':i,'fields':e,'ends_m':[nodes[int(e[3])].tolist(),nodes[int(e[4])].tolist()]})  # Record both longitudinal coordinates and height.
constraints=[]  # Decode the original support set.
for line in sections['*CONSTRAINT']:  # Retain prescribed translational freedoms from the engineering source.
    p=[x.strip() for x in line.split(',')]  # Preserve source flags verbatim.
    for i in ids(p[0]): constraints.append({'node':i,'flags':p[1],'xyz_m':nodes[i].tolist()})  # Report exact boundary location and source freedom code.
raw=(ROOT/'sources/original.mct').read_bytes()  # Read original case headers to avoid losing repeated load cases.
try: text=raw.decode('utf-8-sig')  # Decode the original export.
except UnicodeDecodeError:text=raw.decode('gb18030')  # Support the original Chinese Windows encoding.
case='';key='';cases=collections.defaultdict(list);headers=[]  # Group forces by actual active case, not merely by load-group name.
for j,line in enumerate(text.splitlines(),1):  # Inspect exact original section headers and their line numbers.
    s=line.split(';')[0].strip()  # Remove comments only for parsing.
    if s.startswith('*USE-STLD'): case=s.split(',',1)[1].strip() if ',' in s else '';headers.append([j,s]);key='*USE-STLD'  # Preserve the original static-load case switch.
    elif s.startswith('*'): key=s.split(',')[0];headers.append([j,s]) if key in ['*INI-EFORCE','*EQUI-MFORCE','*STAGE','*INIFORCE'] else None  # Record source initial-state blocks.
    elif s and key=='*CONLOAD': cases[case].append(s)  # Assign each source load to its true case.
case_info={}  # Quantify every original load-case resultant.
for name,lines in cases.items():  # Compare dead and construction states without mixing them.
    force=np.zeros(3);unique=collections.Counter()  # Accumulate physical nodal loads.
    for s in lines:  # Parse original point forces in kN.
        p=[x.strip() for x in s.split(',')];force+=np.array([float(x) for x in p[1:4]])*len(ids(p[0]));unique[float(p[3])]+=len(ids(p[0]))  # Preserve ranges and multiplicities.
    case_info[name]={'rows':len(lines),'resultant_kN':force.tolist(),'common_vertical_loads':unique.most_common(24)}  # Identify passage and frame loads by their actual occurrence.
info={'source_headers':headers,'initial_force_samples':{k:sections.get(k,[])[:12] for k in ['*INIFORCE','*EQUI-MFORCE','*INI-EFORCE']},'source_groups':sections.get('*GROUP',[]),'boundary_nodes':constraints,'gantries':truss,'element_samples':{str(i):elems[i] for i in [1,2,3,154,155,447,448,728,729,1001,1066,1280,1395] if i in elems},'case_info':case_info}  # Make the complete mapping auditable before constructing the spatial system.
(OUT/'source_state_detail.json').write_text(json.dumps(info,ensure_ascii=False,indent=2));print('SOURCE_STATE',json.dumps(info,ensure_ascii=False),flush=True)  # Save a readable original-state ledger.
(ROOT/'sources/loadcases.json').write_text(json.dumps(cases,ensure_ascii=False))  # Preserve actual case grouping for the physical builder.
