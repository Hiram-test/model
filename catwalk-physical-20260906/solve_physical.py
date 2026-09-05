from pathlib import Path  # Restrict every input to the originals recovered for this reconstruction.
import json, collections, traceback, pymupdf, py_compile  # Preserve original source pages and actual execution diagnostics.
ROOT=Path(__file__).parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)  # Store all native outputs in the dedicated calculation branch.
error_file=OUT/'execution_error.txt'  # Keep this invocation's status separate from an earlier failed run.
if error_file.exists():error_file.unlink()  # Do not leave a stale failure record beside newly successful numerical evidence.
for script in ROOT.glob('*.py'):py_compile.compile(str(script),doraise=True)  # Check source syntax before spending time in native compilation or factorization.
raw=(ROOT/'sources/original.mct').read_bytes()  # Read the exact original engineering MCT.
try:text=raw.decode('utf-8-sig')  # Accept a Unicode original export.
except UnicodeDecodeError:text=raw.decode('gb18030')  # Decode the original Chinese Windows export when required.
case='';key='';cases=collections.defaultdict(list)  # Preserve original static-load cases instead of merging unrelated loads.
for line in text.splitlines():  # Inspect only original section boundaries and load records.
    s=line.split(';')[0].strip()  # Remove comments only for parsing.
    if s.startswith('*USE-STLD'):case=s.split(',',1)[1].strip() if ',' in s else '';key='*USE-STLD'  # Retain the active original load-case identity.
    elif s.startswith('*'):key=s.split(',')[0]  # Preserve source section boundaries.
    elif s and key=='*CONLOAD':cases[case].append(s)  # Associate point forces with their actual active case.
(ROOT/'sources/loadcases.json').write_text(json.dumps(cases,ensure_ascii=False))  # Save the original load map for both independent and native calculations.
original=pymupdf.open(ROOT/'sources/original_drawing_1225.pdf');pages=OUT/'original_pages';pages.mkdir(exist_ok=True)  # Preserve the selected original connection drawings as vector PDF excerpts.
for page in [91,92,93,94,98,99,100,101,102]:  # Keep original ordinary-gantry and passage details available for inspection.
    doc=pymupdf.open();doc.insert_pdf(original,from_page=page-1,to_page=page-1);doc.save(pages/f'drawing_{page:03d}.pdf',garbage=4,deflate=True)  # Extract the exact original contents without drawing replacement details.
    original[page-1].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(pages/f'drawing_{page:03d}.png')  # Preserve an image of the exact original page.
try:  # Keep a genuine native build, connection or global-solver failure visible.
    from run_workstate import execute  # Use the unmodified official executable for the independent MCT-state verification first.
    source,state=execute()  # Solve the original permanent-load equilibrium independently and in native CCX.
    from read_drawing_dimensions import inspect  # Read the three otherwise unavailable original raster pages once only.
    inspect()  # Preserve uncertain numeric transcription without treating OCR as authoritative construction evidence.
    from build_joint_solver import build  # Compile the small, auditable native joint-coordinate preprocessing correction.
    build()  # Keep all original element, material, nonlinear and eigenvalue formulas unchanged.
    from native_checks import execute_checks  # Exercise real native hollow sections, open HW shells, finite offsets and directional pins.
    checks=execute_checks()  # Verify actual connector action rather than rely on an element or command name.
    failed=[name for name,value in checks.items() if value['native_exit']!=0]  # Identify genuine failed physical-member or connector executions.
    if failed:raise RuntimeError('Native connection implementation is still invalid in tests: '+','.join(failed))  # Do not knowingly carry a failed physical connection into the full-bridge model.
    from full_native_run import compute  # Use the complete source-based assembly with symmetric passage mass and actual deformation-frame spreader ports.
    status=compute(source,state)  # Execute the complete real nonlinear equilibrium and eighty-root native eigensolution.
    (OUT/'completion.json').write_text(json.dumps({'full_native_status':status,'source_state':'original MCT permanent state independently reconstructed','model_scope':'see full_spatial_native/physical_assumptions.json','target_reproduction':'not inferred merely from native completion'},indent=2))  # Preserve an exact numerical completion record without declaring the original target right or wrong.
except Exception:  # Retain full diagnostics for any actual execution failure.
    detail=traceback.format_exc();error_file.write_text(detail);print(detail,flush=True);raise  # Propagate failure rather than fabricate full calculation success.
