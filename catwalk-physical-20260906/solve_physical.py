from pathlib import Path  # Restrict reconstruction to the source files recovered in this turn.
import json, collections, subprocess, shutil, traceback  # Preserve both numerical evidence and genuine failure diagnostics.
ROOT=Path(__file__).parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)  # Keep all new calculations on the isolated branch.
raw=(ROOT/'sources/original.mct').read_bytes()  # Read the exact original engineering MCT.
try:text=raw.decode('utf-8-sig')  # Accept an original Unicode export.
except UnicodeDecodeError:text=raw.decode('gb18030')  # Decode the original Chinese Windows encoding when required.
case='';key='';cases=collections.defaultdict(list)  # Preserve static-load case switches, not merely load-group labels.
for line in text.splitlines():  # Read original loads without importing historical work states.
    s=line.split(';')[0].strip()  # Remove comments only from the parser input.
    if s.startswith('*USE-STLD'):case=s.split(',',1)[1].strip() if ',' in s else '';key='*USE-STLD'  # Retain the original active load case.
    elif s.startswith('*'):key=s.split(',')[0]  # Track actual source section boundaries.
    elif s and key=='*CONLOAD':cases[case].append(s)  # Associate every point load with its own original case.
(ROOT/'sources/loadcases.json').write_text(json.dumps(cases,ensure_ascii=False))  # Save the original case map for both independent implementations.
shutil.copy2(ROOT/'sources/original_drawing_1225.pdf',OUT/'original_drawing_1225.pdf')  # Expose exact original design bytes for detailed page verification.
subprocess.run(['git','add','-f',str(OUT/'original_drawing_1225.pdf')],check=True)  # Preserve the already-public original drawing in the authorized reconstruction branch.
try:  # Preserve native input errors and numerical diagnostics rather than losing the run.
    from mct_workstate import execute  # Import only the newly written original-state solver.
    source,state=execute()  # Execute both independent and native equilibrium calculations now.
    if (ROOT/'spatial_native.py').exists():  # Run the real full model as soon as its source is committed.
        from spatial_native import compute  # Import only this turn's source-based physical reconstruction.
        compute(source,state)  # Run complete static, modal and connection-response calculations.
    else:print('MCT work state executed; spatial model source is not yet committed.',flush=True)  # State precisely what has actually run.
except Exception:  # Save the full exception as actual execution evidence.
    detail=traceback.format_exc();(OUT/'execution_error.txt').write_text(detail);print(detail,flush=True);raise  # Propagate failure without fabricating a completed calculation.
