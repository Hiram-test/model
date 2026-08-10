from pathlib import Path  # Use deterministic filesystem paths for the validated PR9 mother model and generated hanger-interface control.
import math  # Compute each validated hanger length and its equivalent axial spring stiffness EA/L.
import re  # Parse the original hanger connectivity and replace only its element formulation and property card.
import sys  # Receive the immutable baseline input and generated control output paths from GitHub Actions.
if len(sys.argv) != 3:  # Require exactly one validated baseline and one generated output deck.
    raise SystemExit('usage: spring_hanger_control_generate.py BASELINE_INP OUTPUT_INP')  # Stop explicitly when the workflow invocation is incomplete.
source = Path(sys.argv[1]).resolve()  # Resolve the immutable validated PR9 LC01 dead-load mother model.
out = Path(sys.argv[2]).resolve()  # Resolve the generated SPRINGA-hanger nonlinear control deck.
out.parent.mkdir(parents=True, exist_ok=True)  # Create the numerical output directory before writing the generated model.
text = source.read_text()  # Load the exact validated mother model so all unrelated bridge definitions remain byte-equivalent.
lines = text.splitlines()  # Split the deck only for extracting node coordinates and hanger connectivity.
nodes = {}  # Store original global node coordinates keyed by validated node identifier.
hangers = []  # Store original hanger element identifiers and two-node connectivity in source order.
i = 0  # Begin one deterministic pass through the source deck.
while i < len(lines):  # Parse only the node block and the original HANGERS element block needed for equivalent stiffness calculation.
    line = lines[i].strip()  # Normalize whitespace on the current input record.
    upper = line.upper()  # Compare input keywords without depending on capitalization.
    if upper == '*NODE, NSET=NALL' or upper == '*NODE':  # Enter the validated global node coordinate block.
        i += 1  # Advance to the first node record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read nodes until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Split node identifier and its three global coordinates.
            nodes[int(row[0])] = (float(row[1]), float(row[2]), float(row[3]))  # Preserve the exact validated coordinate tuple numerically.
            i += 1  # Move to the next coordinate row or following keyword.
        continue  # Resume parsing from the keyword reached by the inner loop.
    if upper.startswith('*ELEMENT') and 'ELSET=HANGERS' in upper:  # Enter the validated fifty-element T3D2 hanger block.
        i += 1  # Advance to the first hanger connectivity row.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every hanger element until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Split element identifier and its two end-node identifiers.
            hangers.append((int(row[0]), int(row[1]), int(row[2])))  # Preserve the exact original hanger topology and element numbering.
            i += 1  # Move to the next hanger or following keyword.
        continue  # Resume parsing from the keyword already reached by the inner loop.
    i += 1  # Skip all source records unrelated to this local hanger-interface repair.
if len(hangers) != 50:  # Require the validated PR9 hanger count before changing element formulation.
    raise RuntimeError(f'expected 50 validated hangers, found {len(hangers)}')  # Refuse to generate a model from an unexpected source topology.
A_HANGER = 804.247719  # Preserve the validated hanger axial area in square millimetres.
E_HANGER = 200000.0  # Preserve the validated hanger elastic modulus in newtons per square millimetre.
property_blocks = []  # Accumulate one symmetric two-element SPRINGA property set per hanger station.
for station in range(25):  # Process the twenty-five symmetric longitudinal hanger stations.
    positive = hangers[station]  # Retrieve the positive-y hanger in the original source ordering.
    negative = hangers[station + 25]  # Retrieve the corresponding negative-y hanger in the original source ordering.
    point_a = nodes[positive[1]]  # Recover the positive-y hanger lower or upper endpoint coordinate.
    point_b = nodes[positive[2]]  # Recover the positive-y hanger opposite endpoint coordinate.
    length = math.sqrt(sum((point_b[j] - point_a[j]) ** 2 for j in range(3)))  # Evaluate the exact validated three-dimensional hanger chord length.
    stiffness = E_HANGER * A_HANGER / length  # Compute the linear axial tangent stiffness EA/L in newtons per millimetre.
    set_name = f'HSPR_{station + 1:02d}'  # Create a deterministic station property set shared by the symmetric hanger pair.
    property_blocks.append(f'*ELSET, ELSET={set_name}\n{positive[0]}, {negative[0]}\n*SPRING, ELSET={set_name}\n\n{stiffness:.12e}\n')  # Assign each symmetric SPRINGA pair its exact validated axial stiffness.
text = re.sub(r'\*ELEMENT,\s*TYPE=T3D2,\s*ELSET=HANGERS', '*ELEMENT, TYPE=SPRINGA, ELSET=HANGERS', text, count=1, flags=re.I)  # Replace only the fifty original hanger elements with native large-displacement axial springs while preserving IDs and connectivity.
solid_pattern = re.compile(r'\*SOLID SECTION,\s*ELSET=HANGERS,\s*MATERIAL=HANGER_BAR_SCREEN\s*\n804\.247719\s*\n', re.I)  # Match exactly the obsolete T3D2 hanger section assignment.
text, section_count = solid_pattern.subn(''.join(property_blocks), text, count=1)  # Replace the T3D2 section with twenty-five station-specific native SPRINGA properties.
if section_count != 1:  # Require exactly one validated hanger section replacement.
    raise RuntimeError('validated HANGERS solid-section anchor was not found exactly once')  # Refuse a partial or ambiguous local repair.
text = text.replace('*STEP\n*STATIC\n1.0, 1.0\n', '*STEP, NLGEOM=YES, INC=5000\n*STATIC\n1.0E-4, 1.0, 1.0E-6, 5.0E-3\n', 1)  # Change only the original analysis step to geometrically nonlinear static with conservative automatic increments.
if '*STEP, NLGEOM=YES' not in text:  # Verify the expected original linear step was successfully replaced.
    raise RuntimeError('validated LC01 static-step anchor was not found')  # Stop rather than solve an unchanged linear control by accident.
text = text.replace('Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD', 'Zhaqing suspension bridge NLGEOM control - native SPRINGA hangers on validated L2 topology', 1)  # Mark the single local formulation change directly in the generated model heading.
out.write_text(text)  # Persist the exact local-interface control model for the CalculiX nonlinear solve.
print(f'generated={out} hanger_count={len(hangers)} station_properties={len(property_blocks)} formulation=SPRINGA thermal_keywords={text.upper().count("*TEMPERATURE")}')  # Emit a compact auditable generation receipt proving no thermal prestress is present.
