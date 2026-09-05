from pathlib import Path  # Restrict reconstruction to the original sources recovered in this turn.
import json, collections, traceback, pymupdf  # Preserve exact source pages and actual numerical execution evidence.
ROOT=Path(__file__).parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)  # Keep every new calculation on the isolated reconstruction branch.
raw=(ROOT/'sources/original.mct').read_bytes()  # Read the immutable engineering MCT, not a previous reconstructed model.
try:text=raw.decode('utf-8-sig')  # Accept an original Unicode export.
except UnicodeDecodeError:text=raw.decode('gb18030')  # Decode the original Chinese Windows export when required.
case='';key='';cases=collections.defaultdict(list)  # Preserve each original permanent and construction load case separately.
for line in text.splitlines():  # Inspect the original load-case switches.
    s=line.split(';')[0].strip()  # Remove comments only for parsing.
    if s.startswith('*USE-STLD'):case=s.split(',',1)[1].strip() if ',' in s else '';key='*USE-STLD'  # Retain the actual original case identity.
    elif s.startswith('*'):key=s.split(',')[0]  # Preserve source section boundaries.
    elif s and key=='*CONLOAD':cases[case].append(s)  # Associate point forces with their true active case.
(ROOT/'sources/loadcases.json').write_text(json.dumps(cases,ensure_ascii=False))  # Save the original case map for independent and native calculations.
original=pymupdf.open(ROOT/'sources/original_drawing_1225.pdf');pages=OUT/'original_pages';pages.mkdir(exist_ok=True)  # Keep original connection drawings available as native vector PDF excerpts.
for page in [91,92,93,94,98,99,100,101,102]:  # Extract only relevant original gantry and passage construction pages.
    doc=pymupdf.open();doc.insert_pdf(original,from_page=page-1,to_page=page-1);doc.save(pages/f'drawing_{page:03d}.pdf',garbage=4,deflate=True)  # Preserve the original page contents without redrawing engineering details.
    original[page-1].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(pages/f'drawing_{page:03d}.png')  # Save an image of the exact original source page.
try:  # Preserve genuine build or solver failures rather than losing their evidence.
    from run_workstate import execute  # Verify the original working state using the unmodified upstream CCX executable.
    source,state=execute()  # Solve the MCT equilibrium independently and in native CCX first.
    from build_joint_solver import build  # Compile only the explicit native joint-coordinate preprocessing correction.
    build()  # Keep native element, material, nonlinear and eigensolver routines unchanged.
    from native_checks import execute_checks  # Test the actual hollow sections, open HW section, finite offsets and relative pins.
    checks=execute_checks()  # Verify the mechanical action of every connector type used below.
    if (ROOT/'spatial_native.py').exists():  # Run the complete physical model when its new source has been committed.
        from spatial_native import compute  # Import only this reconstruction's physical model builder.
        compute(source,state)  # Execute full static equilibrium and modal extraction, preserving complete native outputs.
    else:print('Original work state and native connection tests executed; complete spatial source is being assembled.',flush=True)  # Do not claim an unexecuted full-bridge calculation.
except Exception:  # Retain an exact diagnostic for any actual execution failure.
    detail=traceback.format_exc();(OUT/'execution_error.txt').write_text(detail);print(detail,flush=True);raise  # Propagate the failure without fabricating success.
