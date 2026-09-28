from pathlib import Path  # Use deterministic filesystem paths for the validated L2 baseline and generated nonlinear control deck.
import sys  # Receive the immutable baseline INP path and generated control INP path from GitHub Actions.
if len(sys.argv) != 3:  # Require one validated mother model and one explicit output path.
    raise SystemExit('usage: nlgeom_control_generate.py BASELINE_INP OUTPUT_INP')  # Stop clearly when workflow invocation is incomplete.
source = Path(sys.argv[1]).resolve()  # Resolve the previously validated PR9 LC01 dead-load input file.
out = Path(sys.argv[2]).resolve()  # Resolve the pure-NLGEOM control model output file.
out.parent.mkdir(parents=True, exist_ok=True)  # Create the numerical output directory before writing the control model.
text = source.read_text()  # Load the exact validated baseline without introducing any thermal or prestress keywords.
text = text.replace('*STEP\n*STATIC\n1.0, 1.0\n', '*STEP, NLGEOM=YES, INC=5000\n*STATIC\n1.0E-4, 1.0, 1.0E-6, 5.0E-3\n', 1)  # Change only the original static step to geometric nonlinearity with conservative automatic increments.
if '*STEP, NLGEOM=YES' not in text:  # Verify that the expected original linear step was found and replaced exactly once.
    raise RuntimeError('validated LC01 step anchor was not found')  # Refuse to solve an ambiguous or structurally drifted mother model.
text = text.replace('Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD', 'Zhaqing suspension bridge pure NLGEOM control - validated L2 topology and dead load', 1)  # Mark the diagnostic purpose directly in the generated deck heading.
out.write_text(text)  # Persist the pure nonlinear control model with no expansion, temperature, or initial-stress definitions.
print(f'generated={out} thermal_keywords={text.upper().count("*TEMPERATURE")} expansion_keywords={text.upper().count("*EXPANSION")}')  # Emit an auditable proof that the control deck contains no thermal prestress mechanism.
