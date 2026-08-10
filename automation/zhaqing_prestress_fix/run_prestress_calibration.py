from pathlib import Path  # Use pathlib for deterministic baseline and generated-model paths.
import math  # Evaluate cable and hanger lengths, slopes, and elastic strain targets.
import re  # Parse original element connectivity and replace only cable/hanger section definitions.
import sys  # Receive the validated PR9 LC01 input deck and output path from CI.
if len(sys.argv) != 3:  # Require one source INP and one generated INP path.
    raise SystemExit('usage: build_prestress_compact.py BASELINE_INP OUTPUT_INP')  # Fail clearly when workflow arguments are incomplete.
source = Path(sys.argv[1]).resolve()  # Resolve the validated zero-prestress LC01 mother model.
out = Path(sys.argv[2]).resolve()  # Resolve the final force-found nonlinear CalculiX deck path.
out.parent.mkdir(parents=True, exist_ok=True)  # Create the generated-model directory before writing evidence.
text = source.read_text()  # Read the validated mother deck once so all unchanged records remain byte-identical.
lines = text.splitlines()  # Split lines only for extracting node coordinates and cable/hanger connectivity.
nodes = {}  # Store original global node coordinates without modification.
elements = {}  # Store original element type, semantic set, and connectivity without modification.
sets = {}  # Store original element identifiers grouped by semantic set.
i = 0  # Start a single-pass source parser at the first line.
while i < len(lines):  # Parse only the geometric records required to convert solved forces into free lengths.
    line = lines[i].strip()  # Normalize whitespace around the current input record.
    upper = line.upper()  # Compare Abaqus/CalculiX keywords case-insensitively.
    if upper == '*NODE, NSET=NALL' or upper == '*NODE':  # Enter the original node block while excluding output keywords.
        i += 1  # Advance from the node keyword to its first coordinate record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every validated node until the next keyword.
            row = [field.strip() for field in lines[i].split(',')]  # Split node identifier and global coordinates.
            nodes[int(row[0])] = (float(row[1]), float(row[2]), float(row[3]))  # Preserve the original global coordinate tuple exactly.
            i += 1  # Move to the next node or keyword record.
        continue  # Resume parsing from the keyword already reached by the inner loop.
    if upper.startswith('*ELEMENT,'):  # Enter an original element block.
        type_match = re.search(r'TYPE=([^,]+)', line, re.I)  # Extract the original element formulation.
        set_match = re.search(r'ELSET=([^,]+)', line, re.I)  # Extract the original semantic element-set name.
        element_type = type_match.group(1).strip() if type_match else ''  # Preserve the original element formulation string.
        element_set = set_match.group(1).strip() if set_match else ''  # Preserve the original semantic set string.
        sets.setdefault(element_set, [])  # Initialize the semantic set before reading its connectivity rows.
        i += 1  # Advance from the element keyword to its first connectivity record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every element in the current block.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Remove empty comma fields without changing node order.
            element_id = int(row[0])  # Parse the original globally unique element identifier.
            elements[element_id] = (element_type, element_set, [int(value) for value in row[1:]])  # Preserve original connectivity unchanged.
            sets[element_set].append(element_id)  # Register the element under its original semantic set.
            i += 1  # Move to the next connectivity row or keyword.
        continue  # Resume parsing from the keyword already reached by the inner loop.
    i += 1  # Skip all source records that are not needed for free-length generation.
def length(element_id):  # Return one original two-node element length in millimetres.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve the original element end-node identifiers.
    return math.dist(nodes[node_a], nodes[node_b])  # Evaluate length directly from the validated global coordinates.
H_KN = 716.1502048515677  # Use the force-found horizontal main-cable component obtained from exact PR9 dead-load/global-equilibrium decomposition.
A_MAIN = 74.5432224 * 74.5432224  # Preserve the original equivalent main-cable area in square millimetres.
E_MAIN = 195000.0  # Preserve the original main-cable elastic modulus in MPa.
A_HANGER = 804.247719  # Preserve the original hanger area in square millimetres.
E_HANGER = 200000.0  # Preserve the original hanger elastic modulus in MPa.
RHO_HANGER = 7.85e-9  # Preserve the original hanger density in tonnes per cubic millimetre.
G = 9810.0  # Preserve the original N-mm-tonne-s gravitational acceleration.
mainspan = []  # Identify one positive-y tower-to-tower cable chain to recover the actual endpoint segment slope.
for element_id in sets['MAIN_CABLES']:  # Inspect every original main-cable B31 element.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve original element end nodes.
    point_a, point_b = nodes[node_a], nodes[node_b]  # Recover original end-node coordinates.
    if abs(point_a[1] - 2750.0) < 1.0e-6 and abs(point_b[1] - 2750.0) < 1.0e-6 and min(point_a[0], point_b[0]) >= 0.0 and max(point_a[0], point_b[0]) <= 82000.0:  # Select the positive-y main-span chain.
        mainspan.append(element_id)  # Preserve the original main-span element for end-slope detection.
mainspan.sort(key=lambda element_id: min(nodes[elements[element_id][2][0]][0], nodes[elements[element_id][2][1]][0]))  # Sort the selected chain from left tower to right tower.
first_a, first_b = elements[mainspan[0]][2][:2]  # Retrieve the actual first 1 m B31 segment adjacent to the left tower.
end_slope = abs((nodes[first_b][2] - nodes[first_a][2]) / (nodes[first_b][0] - nodes[first_a][0]))  # Evaluate the discretized tower-adjacent cable slope.
T_TOWER_KN = H_KN * math.sqrt(1.0 + end_slope * end_slope)  # Recover the target tower-adjacent cable tension used for straight side spans.
materials = []  # Accumulate segment/station-specific materials carrying equivalent thermal free contractions.
elsets = []  # Accumulate disjoint prestress assignment sets while retaining original semantic sets for output.
sections = []  # Accumulate replacement B31/T3D2 section definitions with unchanged geometry.
for sequence, element_id in enumerate(sets['MAIN_CABLES'], start=1):  # Generate one free-length correction for each original main-cable element.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve original cable-segment end nodes.
    point_a, point_b = nodes[node_a], nodes[node_b]  # Recover original segment coordinates.
    dx = point_b[0] - point_a[0]  # Compute the original longitudinal segment projection.
    dz = point_b[2] - point_a[2]  # Compute the original vertical segment projection.
    midpoint_x = 0.5 * (point_a[0] + point_b[0])  # Locate this segment along the bridge axis.
    in_mainspan = 0.0 <= midpoint_x <= 82000.0 and abs(dx) > 1.0e-12 and abs(abs(point_a[1]) - 2750.0) < 1.0e-6 and abs(abs(point_b[1]) - 2750.0) < 1.0e-6  # Detect a tower-to-tower segment in either cable plane.
    tension_kN = H_KN * math.sqrt(1.0 + (dz / dx) ** 2) if in_mainspan else T_TOWER_KN  # Apply constant horizontal force in the main span and tension continuity in straight side spans.
    strain = tension_kN * 1000.0 / (A_MAIN * E_MAIN)  # Convert target axial force into completed-state elastic strain.
    material = f'MC_PRE_{sequence:03d}'  # Create a deterministic material name for this original cable segment.
    elset = f'MCSEG_{sequence:03d}'  # Create a deterministic disjoint section-assignment set for this cable segment.
    materials.append(f'*MATERIAL, NAME={material}\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n*EXPANSION, ZERO=0.\n{strain:.12e}\n')  # Encode target elastic strain as equal thermal free contraction at DeltaT=-1.
    elsets.append(f'*ELSET, ELSET={elset}\n{element_id}\n')  # Assign exactly this original cable element to its unique prestress group.
    sections.append(f'*BEAM SECTION, ELSET={elset}, MATERIAL={material}, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n')  # Preserve original B31 equivalent section and orientation while changing only free length.
for station in range(25):  # Generate one target free length for each symmetric hanger station.
    positive = 1021 + station  # Identify the positive-y original hanger element at this station.
    negative = 1046 + station  # Identify the symmetric negative-y original hanger element at this station.
    hanger_length = length(positive)  # Recover the exact existing geometric hanger length.
    deck_force_kN = 26.1924675 if station in (0, 24) else 20.5652030  # Use the exact PR9 tributary deck-load solution rounded below one newton at end/interior stations.
    half_self_weight_kN = 0.5 * hanger_length * A_HANGER * RHO_HANGER * G / 1000.0  # Add the lower-node half of the one-element hanger consistent gravity load.
    tension_kN = deck_force_kN + half_self_weight_kN  # Recover the uniform completed-state hanger axial force.
    strain = tension_kN * 1000.0 / (A_HANGER * E_HANGER)  # Convert target hanger force into completed-state elastic strain.
    material = f'HG_PRE_{station + 1:02d}'  # Create a deterministic station-specific hanger material name.
    elset = f'HGSTA_{station + 1:02d}'  # Create a deterministic section-assignment set shared by both cable planes.
    materials.append(f'*MATERIAL, NAME={material}\n*ELASTIC\n200000., 0.30\n*DENSITY\n7.85e-9\n*EXPANSION, ZERO=0.\n{strain:.12e}\n')  # Encode the solved hanger extension as equal thermal free contraction at DeltaT=-1.
    elsets.append(f'*ELSET, ELSET={elset}\n{positive}, {negative}\n')  # Assign the symmetric hanger pair to the same solved target force.
    sections.append(f'*SOLID SECTION, ELSET={elset}, MATERIAL={material}\n804.247719\n')  # Preserve the original T3D2 area while changing only unstressed length.
material_anchor = '*MATERIAL, NAME=MAIN_CABLE_WIRE_SCREEN\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n'  # Identify the exact original cable material block for deterministic insertion.
if material_anchor not in text:  # Refuse to modify an unexpected baseline model.
    raise RuntimeError('main-cable material anchor missing')  # Stop rather than silently patching a changed bridge model.
generated = text.replace(material_anchor, material_anchor + ''.join(materials), 1)  # Insert all prestress materials while retaining every original material definition.
pattern = re.compile(r'\*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74\.5432224, 74\.5432224\n0\., 1\., 0\.\n\*SOLID SECTION, ELSET=HANGERS, MATERIAL=HANGER_BAR_SCREEN\n804\.247719\n', re.I)  # Match exactly the original uniform main-cable and hanger section assignments.
generated, replacements = pattern.subn(''.join(elsets) + ''.join(sections), generated, count=1)  # Replace only those two uniform assignments with disjoint free-length groups.
if replacements != 1:  # Verify the validated source structure matched exactly once.
    raise RuntimeError('cable/hanger section anchor replacement failed')  # Stop before producing an ambiguous model if the source structure changed.
step_start = generated.index('*STEP')  # Locate the original single linear LC01 step.
prefix = generated[:step_start]  # Preserve all validated model definitions and boundary conditions before the analysis step.
old_step = generated[step_start:]  # Isolate the original load/output step for exact reuse of permanent actions.
load_start = old_step.index('*DLOAD')  # Locate original gravity and accessory CLOAD records.
output_start = old_step.index('*NODE PRINT')  # Locate original displacement, reaction, cable, hanger, and girder output requests.
end_step = old_step.index('*END STEP')  # Locate the original linear step terminator.
loads = old_step[load_start:output_start]  # Preserve the original permanent actions byte-for-byte.
outputs = old_step[output_start:end_step]  # Preserve the original requested solver outputs byte-for-byte.
initial = '*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 0.\n'  # Define zero as the free-length reference temperature before loading begins.
step = '*STEP, NAME=COMPLETED_STATE, NLGEOM=YES, INC=5000\n*STATIC\n1.0E-3, 1.0, 1.0E-10, 2.0E-2\n*TEMPERATURE\nNALL, -1.\n' + loads + outputs + '*END STEP\n'  # Ramp force-found free-length contractions and unchanged dead load simultaneously under geometric nonlinearity.
provenance = f'** FORCE_FOUND_PRESTRESS H_MAIN={H_KN:.6f}kN T_TOWER={T_TOWER_KN:.6f}kN\n'  # Embed the solved principal cable forces directly in the generated deck.
generated = prefix.replace('** ----------------------------------------------------------------\n** NODES', provenance + '** ----------------------------------------------------------------\n** NODES', 1) + initial + step  # Assemble the nonlinear completed-state model without changing nodes, elements, supports, or dead load.
out.write_text(generated)  # Persist the exact force-found model that CalculiX will solve.
print(f'generated={out} H_kN={H_KN:.9f} tower_kN={T_TOWER_KN:.9f} cable_groups={len(sets["MAIN_CABLES"])} hanger_groups=25')  # Emit a compact generation receipt to the CI log.
