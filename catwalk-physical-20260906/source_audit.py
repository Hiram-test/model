from pathlib import Path  # Keep this run isolated from historical engineering calculations.
import os, re, json, io, zipfile, tarfile, hashlib, subprocess, shutil  # Use explicit native-file and process operations.
import requests, numpy as np  # Download original inputs and inspect numerical coordinates.
ROOT = Path('catwalk-physical-20260906')  # Store newly generated evidence in a dedicated directory.
OUT = ROOT / 'evidence'; OUT.mkdir(parents=True, exist_ok=True)  # Preserve a complete source audit.
SRC = ROOT / 'sources'; SRC.mkdir(parents=True, exist_ok=True)  # Separate immutable sources from solver outputs.
URL = 'https://raw.githubusercontent.com/Hiram-test/model/cfbf39ef51a5bb86f13372553cee122d02df0f57/catwalk-fem/mct-from-zero/source/01_设计资料与规范/猫道 - 门架索合建模型2.mct'  # Use the original engineering MCT, not a rebuilt numerical model.
r = requests.get(URL, timeout=90); r.raise_for_status(); raw = r.content  # Require actual source retrieval.
(SRC / 'original.mct').write_bytes(raw)  # Preserve exact source bytes.
try: text = raw.decode('utf-8-sig')  # First accept a Unicode original export.
except UnicodeDecodeError: text = raw.decode('gb18030')  # Decode Chinese Windows exports without altering values.
sections = {}; key = ''; section_lines = {}; counter = 0  # Record every section and its actual source line number.
for counter, line in enumerate(text.splitlines(), 1):  # Inspect only the original engineering input.
    value = line.split(';')[0].strip()  # Remove MCT comments for parsing, not from preserved source.
    if value.startswith('*'): key = value.split(',')[0].strip().upper(); sections.setdefault(key, []); section_lines.setdefault(key, counter)  # Retain original section boundaries.
    elif value: sections.setdefault(key, []).append(value)  # Retain all nonempty original data records.
nodes = {int(s.split(',')[0]): [float(x) for x in s.split(',')[1:4]] for s in sections.get('*NODE', [])}  # Parse original coordinate triples in source units.
elements = {int(s.split(',')[0]): [x.strip() for x in s.split(',')[1:]] for s in sections.get('*ELEMENT', [])}  # Parse material, section, topology, and cable settings without reinterpretation.
important = ['*UNIT','*PROJINFO','*STRUCTYPE','*MATERIAL','*SECTION','*CONSTRAINT','*ELASTICLINK','*INIFORCE','*INITIAL-ELEMENT-FORCE','*USE-STLD','*SELFWEIGHT','*STLDCASE','*CONLOAD','*BEAMLOAD','*STAGE','*STAGE-CTRL','*GROUP','*BNDR-GROUP','*LOAD-GROUP']  # Read the complete source-state definition.
short = {k: sections.get(k, []) for k in important}  # Preserve source records, not fitted values.
short['section_counts'] = {k: len(v) for k,v in sections.items()}; short['section_lines'] = section_lines  # Facilitate exact subsequent reads.
short['sha256'] = hashlib.sha256(raw).hexdigest(); short['source_url'] = URL  # Bind the audit to immutable original bytes.
short['node_count'] = len(nodes); short['element_count'] = len(elements)  # Count actual source objects.
short['node_bounds_mm'] = [np.min(list(nodes.values()), axis=0).tolist(), np.max(list(nodes.values()), axis=0).tolist()]  # Diagnose the source plane and longitudinal extent.
short['elements_sample'] = dict(list(elements.items())[:12]); short['truss_elements'] = {i:e for i,e in elements.items() if e[0]=='TRUSS'}  # Locate the actual gantry attachment pairs.
(OUT / 'mct_audit.json').write_text(json.dumps(short, ensure_ascii=False, indent=2))  # Save citable original-input inspection.
(SRC / 'mct_sections.json').write_text(json.dumps({'sections':sections,'nodes':nodes,'elements':elements}, ensure_ascii=False))  # Preserve complete parsed source for the new model builder.
headers = {'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json'}  # Use the runner's standard authorized artifact transport.
provenance = []  # Track exact original documents recovered in this run.
for artifact, label in [(9966033839,'original_reports'),(9966311612,'original_drawing_1225')]:  # Retrieve only original engineering PDFs already identified in the archive.
    response = requests.get(f'https://api.github.com/repos/Hiram-test/model/actions/artifacts/{artifact}/zip', headers=headers, timeout=120); response.raise_for_status()  # Fetch original-source artifacts, not numerical histories.
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:  # Inspect the original-source archive.
        for name in z.namelist():  # Read selected original PDFs only.
            if not name.lower().endswith('.pdf'): continue  # Do not load any historical generated engineering script or result.
            data = z.read(name); target = SRC / Path(name).name; target.write_bytes(data)  # Preserve the exact PDF bytes.
            provenance.append({'artifact':artifact,'member':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})  # Bind each original to its archive member.
(OUT / 'original_pdf_provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2))  # Save only provenance, not borrowed numerical conclusions.
import fitz  # Use PDF text directly; do not perform OCR.
for pdf in SRC.glob('*.pdf'):  # Extract source parameters for auditable transcription.
    document = fitz.open(pdf); pages = []  # Keep page indices and source names explicit.
    for p in document: pages.append(f'\n--- PDF PAGE {p.number+1} ---\n'+p.get_text())  # Extract native text with original page provenance.
    (OUT / (pdf.stem+'_text.txt')).write_text(''.join(pages))  # Store original-document text, never a generated interpretation.
    print('SOURCE_PDF',pdf.name,len(document),flush=True)  # Report actual original-document counts.
print('SOURCE_AUDIT',json.dumps({'nodes':len(nodes),'elements':len(elements),'sections':short['section_counts'],'pdfs':provenance},ensure_ascii=False),flush=True)  # Publish a concise source-state audit.
RUNTIME = ROOT / 'runtime'; RUNTIME.mkdir(exist_ok=True)  # Keep solver acquisition separate from engineering inputs.
response = requests.get('https://www.dhondt.de/ccx_2.23.tar.bz2', timeout=120); response.raise_for_status()  # Obtain the upstream executable rather than an old project-specific binary.
with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:bz2') as archive: archive.extractall(RUNTIME, filter='data')  # Extract official executable files.
exe = next(p for p in RUNTIME.rglob('ccx_2.23') if p.is_file()); exe.chmod(0o755)  # Select the exact upstream executable.
response = requests.get('https://archive.ubuntu.com/ubuntu/pool/main/g/gcc-7/libgfortran4_7.5.0-3ubuntu1~18.04_amd64.deb', timeout=90); response.raise_for_status()  # Recover the library ABI required by the official binary.
(RUNTIME / 'fortran.deb').write_bytes(response.content); subprocess.run(['dpkg-deb','-x',str(RUNTIME/'fortran.deb'),str(RUNTIME/'compat')],check=True)  # Extract locally without changing system libraries.
lib = next((RUNTIME/'compat').rglob('libgfortran.so.4')).parent.resolve()  # Locate the extracted runtime library.
wrapper = ROOT / 'ccx'; wrapper.write_text('#!/bin/sh\n# Launch the upstream CalculiX executable with its compatibility library.\nexport LD_LIBRARY_PATH="'+str(lib)+':${LD_LIBRARY_PATH:-}" # Use only the required library path.\nexec "'+str(exe.resolve())+'" "$@" # Execute the actual upstream solver.\n'); wrapper.chmod(0o755)  # Provide a reproducible native invocation.
(OUT/'solver_provenance.json').write_text(json.dumps({'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'upstream':'https://www.dhondt.de/ccx_2.23.tar.bz2'},indent=2))  # Bind calculations to the real solver binary.
unit = ROOT/'unit_string'; unit.mkdir(exist_ok=True)  # Test only the new solver-element implementation.
n=100; L=100.; N=1000.; EA=1.e6; mu=2.4; d=L/n; a=['*HEADING','Independent taut-string prestress verification','*NODE,NSET=ALL']  # Define an analytic test unrelated to the target bridge frequencies.
for i in range(n+1): a.append(f'{i+1},{i*d:.12g},0,0')  # Generate the straight string nodes.
a.extend(['*ELEMENT,TYPE=SPRINGA,ELSET=CABLE'])  # Use native axial springs with current spatial directions.
for i in range(n): a.append(f'{i+1},{i+1},{i+2}')  # Connect the cable segments.
a.extend(['*SPRING,ELSET=CABLE,NONLINEAR','',f'0,{-N*d/EA-1:.12g}',f'0,{-N*d/EA:.12g}',f'{N:.12g},0',f'{N+EA/d:.12g},1','*ELEMENT,TYPE=MASS,ELSET=INTERIOR'])  # Specify exact initial tension and axial tangent at zero displacement.
for i in range(1,n): a.append(f'{n+i},{i+1}')  # Assign physical interior line mass.
a.extend(['*MASS,ELSET=INTERIOR',str(mu*d),'*ELEMENT,TYPE=MASS,ELSET=ENDS',f'{2*n},1',f'{2*n+1},{n+1}','*MASS,ELSET=ENDS',str(mu*d/2),'*BOUNDARY','1,1,3',f'{n+1},1,3','*STEP,NLGEOM','*STATIC','1,1','*NODE PRINT,NSET=ALL','U,RF','*END STEP','*STEP,PERTURBATION','*FREQUENCY','12,0,10','*NODE FILE','U','*END STEP'])  # Establish prestress and extract its actual tangent modes.
(unit/'string.inp').write_text('\n'.join(a)+'\n')  # Preserve the complete unit-test input.
with (unit/'solver.log').open('w') as log: result=subprocess.run([str(wrapper.resolve()),'string'],cwd=unit,stdout=log,stderr=subprocess.STDOUT,timeout=180)  # Execute the real CCX process and keep the full log.
print('STRING_TEST_EXIT',result.returncode,flush=True); print((unit/'string.dat').read_text()[:4500] if (unit/'string.dat').exists() else (unit/'solver.log').read_text()[-4000:],flush=True)  # Report actual solver output, not a predicted success.
