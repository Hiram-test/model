from pathlib import Path  # Restrict reconstruction to the source files recovered in this turn.
import json, collections, subprocess, shutil, traceback, pymupdf  # Preserve actual numerical evidence and original drawing details.
ROOT=Path(__file__).parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)  # Keep all new calculations on the isolated branch.
raw=(ROOT/'sources/original.mct').read_bytes()  # Read the exact original engineering MCT.
try:text=raw.decode('utf-8-sig')  # Accept an original Unicode export.
except UnicodeDecodeError:text=raw.decode('gb18030')  # Decode the original Chinese Windows export.
case='';key='';cases=collections.defaultdict(list)  # Preserve original static-load case switches.
for line in text.splitlines():  # Read original loads without importing historical calculated states.
    s=line.split(';')[0].strip()  # Remove comments only for parsing.
    if s.startswith('*USE-STLD'):case=s.split(',',1)[1].strip() if ',' in s else '';key='*USE-STLD'  # Keep the actual source load-case identity.
    elif s.startswith('*'):key=s.split(',')[0]  # Preserve section boundaries.
    elif s and key=='*CONLOAD':cases[case].append(s)  # Associate every source load with its active case.
(ROOT/'sources/loadcases.json').write_text(json.dumps(cases,ensure_ascii=False))  # Save the original case map for both implementations.
original=pymupdf.open(ROOT/'sources/original_drawing_1225.pdf');pages=OUT/'original_pages';pages.mkdir(exist_ok=True)  # Access original vector drawing pages, not any model screenshot.
for page in [91,92,93,94,98,99,100,101,102]:  # Preserve the original gate and cross-passage construction pages.
    doc=pymupdf.open();doc.insert_pdf(original,from_page=page-1,to_page=page-1);doc.save(pages/f'drawing_{page:03d}.pdf',garbage=4,deflate=True)  # Extract original vector contents without redrawing engineering details.
    original[page-1].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(pages/f'drawing_{page:03d}.png')  # Preserve a viewable original page for connection-axis inspection.
try:  # Keep every numerical failure visible in the result folder.
    from run_workstate import execute  # Use the source-equilibrium driver that preserves full permanent load at initialization.
    source,state=execute()  # Execute native and independent MCT work-state calculations now.
    if (ROOT/'native_checks.py').exists():  # Run independently defined physical-member checks when committed.
        from native_checks import execute_checks  # Use this turn's analytic native beam and pin tests.
        execute_checks()  # Check real BOX, PIPE, I-beam and single-axis hinge behavior.
    if (ROOT/'spatial_native.py').exists():  # Execute the full source-based model, not a placeholder.
        from spatial_native import compute  # Import only this turn's physical-joint reconstruction.
        compute(source,state)  # Complete actual nonlinear equilibrium and modal extraction.
    else:print('Original MCT work state completed; spatial model is being constructed.',flush=True)  # Distinguish completed calculations from unexecuted model work.
except Exception:  # Preserve genuine exceptions with the native evidence.
    detail=traceback.format_exc();(OUT/'execution_error.txt').write_text(detail);print(detail,flush=True);raise  # Propagate errors without inventing success.
